import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
from utils.db_manager import DBManager

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.log_channels = {}  # Cache for log channels

    async def get_log_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """Get the logging channel for a guild"""
        if guild_id in self.log_channels:
            return self.log_channels[guild_id]
            
        # Fetch from database
        channel_id = await self.db_manager.fetch_one(
            "SELECT channel_id FROM logging_config WHERE guild_id = ?",
            (guild_id,)
        )
        
        if not channel_id:
            return None
            
        channel = self.bot.get_channel(channel_id[0])
        if channel:
            self.log_channels[guild_id] = channel
            
        return channel

    @commands.slash_command(description="Set the channel for logging events")
    @commands.default_member_permissions(administrator=True)
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel for logging events"""
        try:
            # Verify bot permissions in the channel
            if not channel.permissions_for(interaction.guild.me).send_messages:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "I need permission to send messages in that channel!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await self.db_manager.execute(
                """
                INSERT OR REPLACE INTO logging_config (guild_id, channel_id)
                VALUES (?, ?)
                """,
                (interaction.guild.id, channel.id)
            )
            
            self.log_channels[interaction.guild.id] = channel
            
            description = f"Server logs will now be sent to {channel.mention}"
            embed = self.bot.create_embed(
                "Log Channel Set",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
            # Send test log to verify
            await self.log_to_channel(
                interaction.guild,
                "Logging Channel Set",
                f"Logging channel set to {channel.mention} by {interaction.user.mention}",
                discord.Color.green()
            )
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def log_to_channel(self, guild: discord.Guild, title: str, description: str, color: discord.Color = None):
        """Send a log embed to the guild's logging channel"""
        try:
            channel = await self.get_log_channel(guild.id)
            if channel:
                embed = self.bot.create_embed(
                    title,
                    description,
                    command_type="Logging"
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

async def setup(bot):
    await bot.add_cog(Logging(bot))