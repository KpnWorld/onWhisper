import discord
from discord.ext import commands
from typing import Optional
from utils.db_manager import DBManager

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager

    @commands.hybrid_command(description="Set the logging channel for the server")
    @commands.has_permissions(administrator=True)
    async def setlogs(self, ctx, channel: discord.TextChannel):
        """Set the channel for logging events"""
        try:
            # Verify bot permissions in the channel
            if not channel.permissions_for(ctx.guild.me).send_messages:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "I need permission to send messages in that channel!",
                    command_type="Administrative"
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Store logging channel configuration
            await self.db_manager.set_data('logging_config', str(ctx.guild.id), {
                'channel_id': channel.id
            })
            
            description = f"Server logs will now be sent to {channel.mention}"
            embed = self.bot.create_embed(
                "Log Channel Set",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
            # Send test log to verify
            await self.log_to_channel(
                ctx.guild,
                "Logging Channel Set",
                f"Logging channel set to {channel.mention} by {ctx.author.mention}",
                discord.Color.green()
            )
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    async def get_log_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """Get the logging channel for a guild"""
        try:
            # Get from Replit DB
            config = await self.db_manager.get_data('logging_config', str(guild_id))
            if not config:
                return None
                
            channel = self.bot.get_channel(config['channel_id'])
            return channel
        except Exception as e:
            print(f"Error getting log channel: {e}")
            return None

    async def log_to_channel(self, guild: discord.Guild, title: str, description: str, color: discord.Color = None):
        """Send a log embed to the guild's logging channel"""
        try:
            channel = await self.get_log_channel(guild.id)
            if channel:
                embed = self.ui.system_embed(
                    title,
                    description
                )
                if color:
                    embed.color = color
                await channel.send(embed=embed)
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