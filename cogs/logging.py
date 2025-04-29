import discord
from discord.ext import commands
from typing import Optional
from utils.db_manager import DBManager
from datetime import datetime
import asyncio

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager
        self.log_channels = {}  # Cache log channel IDs
        self.bot.loop.create_task(self.load_log_channels())

    async def load_log_channels(self):
        """Load all logging channels from database on startup"""
        try:
            await self.bot.wait_until_ready()
            
            # Wait for database with exponential backoff
            max_retries = 5
            base_delay = 2  # seconds
            
            for attempt in range(max_retries):
                if self.db_manager.db:
                    if await self.db_manager.check_connection():
                        break
                        
                delay = base_delay * (2 ** attempt)
                print(f"Waiting for database... Attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(delay)
            
            if not self.db_manager.db or not await self.db_manager.check_connection():
                print("Database not available after max retries")
                return
                
            # Get all guilds with logging enabled
            guild_data_tasks = [
                self.db_manager.get_guild_data(guild.id) 
                for guild in self.bot.guilds
            ]
            
            # Wait for all guild data to load
            guild_data_results = await asyncio.gather(*guild_data_tasks, return_exceptions=True)
            
            for guild, data in zip(self.bot.guilds, guild_data_results):
                if isinstance(data, Exception):
                    print(f"Error loading data for guild {guild.id}: {data}")
                    continue
                    
                if not data:
                    continue
                    
                logs_config = data.get('logs_config', {})
                if logs_config.get('enabled', True) and logs_config.get('channel_id'):
                    self.log_channels[guild.id] = logs_config['channel_id']
                    
            print(f"Loaded {len(self.log_channels)} logging channels")

        except Exception as e:
            print(f"Error loading log channels: {e}")

    async def get_log_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """Get the logging channel for a guild"""
        try:
            # Get guild data
            guild_data = await self.db_manager.get_guild_data(guild_id)
            logs_config = guild_data.get('logs_config', {})
            
            if not logs_config.get('enabled', True):
                return None

            channel_id = logs_config.get('channel_id')
            if not channel_id:
                return None
                
            channel = self.bot.get_channel(channel_id)
            return channel
        except Exception as e:
            print(f"Error getting log channel: {e}")
            return None

    @commands.hybrid_command(description="Set the logging channel for the server")
    @commands.has_permissions(administrator=True)
    async def setlogs(self, ctx, channel: discord.TextChannel):
        try:
            # Update logs config
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {
                    'channel_id': channel.id,
                    'enabled': True,
                    'last_updated': datetime.utcnow().isoformat()
                },
                ['logs_config']
            )
            
            embed = self.ui.admin_embed(
                "Logging Channel Set",
                f"Server logs will now be sent to {channel.mention}"
            )
            await ctx.send(embed=embed)
            
            # Send test message to verify
            test_embed = self.ui.system_embed(
                "🔔 Logging System Active",
                f"Logging channel set by {ctx.author.mention}\n"
                f"Server logs will be sent here"
            )
            await channel.send(embed=test_embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    async def log_to_channel(self, guild: discord.Guild, title: str, description: str, color: discord.Color = None):
        """Send a log embed to the guild's logging channel"""
        try:
            channel = await self.get_log_channel(guild.id)
            if not channel:
                return

            # Verify all required permissions
            required_permissions = [
                'view_channel',
                'send_messages',
                'embed_links',
                'attach_files',
                'read_message_history'
            ]

            # Check bot permissions in the channel
            missing_perms = []
            channel_perms = channel.permissions_for(guild.me)
            
            for perm in required_permissions:
                if not getattr(channel_perms, perm, False):
                    missing_perms.append(perm)

            if missing_perms:
                print(f"Missing permissions in log channel ({channel.name}): {', '.join(missing_perms)}")
                
                # Try to notify in system channel or first available text channel
                notify_channel = guild.system_channel
                if not notify_channel:
                    notify_channel = next((c for c in guild.text_channels 
                                        if c.permissions_for(guild.me).send_messages), None)
                
                if notify_channel:
                    error_embed = self.ui.error_embed(
                        "Logging Channel Permission Error",
                        f"I need the following permissions in {channel.mention}:\n" +
                        "\n".join(f"• {perm}" for perm in missing_perms)
                    )
                    try:
                        await notify_channel.send(embed=error_embed)
                    except:
                        pass
                return

            # Create and send embed if we have permissions
            embed = self.ui.system_embed(title, description)
            if color:
                embed.color = color
            embed.timestamp = datetime.utcnow()
            await channel.send(embed=embed)

        except discord.Forbidden:
            print(f"Missing permissions to send logs in {guild.name}")
        except discord.HTTPException as e:
            print(f"Failed to send log message in {guild.name}: {e}")
        except Exception as e:
            print(f"Failed to log to channel: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log member joins"""
        description = (
            f"Member: {member.mention}\n"
            f"Account Age: <t:{int(member.created_at.timestamp())}:R>"
        )
        await self.log_to_channel(
            member.guild,
            "👋 Member Joined",
            description,
            discord.Color.green()
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log member leaves"""
        description = (
            f"Member: {member}\n"
            f"Joined: <t:{int(member.joined_at.timestamp())}:R>"
        )
        await self.log_to_channel(
            member.guild,
            "👋 Member Left",
            description,
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log message deletions"""
        if message.author.bot:
            return
            
        description = (
            f"Author: {message.author.mention}\n"
            f"Channel: {message.channel.mention}\n"
            f"\n"
        )
        
        if message.content:
            content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
            description += f"Content:\n{content}\n\n"
        
        if message.attachments:
            attachment_list = "\n".join([a.url for a in message.attachments])
            if len(attachment_list) > 1000:
                attachment_list = attachment_list[:997] + "..."
            description += f"Attachments:\n{attachment_list}"
            
        await self.log_to_channel(
            message.guild,
            "🗑️ Message Deleted",
            description,
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log message edits"""
        if before.author.bot or before.content == after.content:
            return
            
        description = (
            f"Author: {before.author.mention}\n"
            f"Channel: {before.channel.mention}\n"
            f"[Jump to Message]({after.jump_url})\n"
            f"\n"
            f"Before:\n{before.content[:1000] + '...' if len(before.content) > 1000 else before.content}\n"
            f"\n"
            f"After:\n{after.content[:1000] + '...' if len(after.content) > 1000 else after.content}"
        )
        
        await self.log_to_channel(
            after.guild,
            "✏️ Message Edited",
            description,
            discord.Color.blue()
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Log channel creation"""
        description = (
            f"Name: #{channel.name}\n"
            f"Type: {str(channel.type)}"
        )
        await self.log_to_channel(
            channel.guild,
            "📝 Channel Created",
            description,
            discord.Color.green()
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Log channel deletion"""
        description = (
            f"Name: #{channel.name}\n"
            f"Type: {str(channel.type)}"
        )
        await self.log_to_channel(
            channel.guild,
            "🗑️ Channel Deleted",
            description,
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Log channel updates"""
        if before.name != after.name:
            description = (
                f"Channel: #{after.name}\n"
                f"Before: #{before.name}\n"
                f"After: #{after.name}"
            )
            await self.log_to_channel(
                after.guild,
                "📝 Channel Renamed",
                description,
                discord.Color.blue()
            )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Log member updates (roles, nickname)"""
        if before.roles != after.roles:
            # Role changes
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)
            
            if added_roles or removed_roles:
                description = f"Member: {after.mention}\n\n"
                
                if added_roles:
                    description += f"Added Roles:\n{', '.join(role.mention for role in added_roles)}\n"
                if removed_roles:
                    description += f"\nRemoved Roles:\n{', '.join(role.mention for role in removed_roles)}"
                    
                await self.log_to_channel(
                    after.guild,
                    "👤 Member Roles Updated",
                    description,
                    discord.Color.blue()
                )
                
        if before.nick != after.nick:
            description = (
                f"Member: {after.mention}\n"
                f"Before: {before.nick or before.name}\n"
                f"After: {after.nick or after.name}"
            )
            await self.log_to_channel(
                after.guild,
                "📝 Nickname Changed",
                description,
                discord.Color.blue()
            )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Log role creation"""
        description = f"Role: {role.mention}"
        await self.log_to_channel(
            role.guild,
            "📝 Role Created",
            description,
            discord.Color.green()
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Log role deletion"""
        description = f"Role: {role.name}"
        await self.log_to_channel(
            role.guild,
            "🗑️ Role Deleted",
            description,
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        """Log role updates"""
        if before.name != after.name:
            description = (
                f"Role: {after.mention}\n"
                f"Before: {before.name}\n"
                f"After: {after.name}"
            )
            await self.log_to_channel(
                after.guild,
                "📝 Role Updated",
                description,
                discord.Color.blue()
            )

async def setup(bot):
    await bot.add_cog(Logging(bot))