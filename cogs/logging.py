import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import logging
from datetime import datetime, timedelta

class LoggingCog(commands.Cog):
    """Server event logging system"""

    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.logging")
        self.server_events = [
            "channel_create", "channel_delete", "channel_update",
            "role_create", "role_delete", "role_update",
            "member_join", "member_leave", "member_ban",
            "member_unban", "member_roles", "server_update",
            "emoji_update", "invite_create", "invite_delete"
        ]

    async def _log_event(self, guild_id: int, event_type: str, description: str) -> None:
        """Log a server event to the database and configured channel"""
        try:
            # Get logging settings from feature_settings table
            settings = await self.bot.db.get_feature_settings(guild_id, "logging")
            if not settings or not settings.get('enabled'):
                return

            # Add log entry to the logs table
            await self.bot.db.execute(
                """INSERT INTO logs (guild_id, event_type, description, timestamp)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (guild_id, event_type, description)
            )

            # If log channel is configured, send embed
            if channel_id := settings.get('log_channel_id'):
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    embed = discord.Embed(
                        title=f"🔍 {event_type.replace('_', ' ').title()}",
                        description=description,
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    await channel.send(embed=embed)

        except Exception as e:
            self.log.error(f"Error logging event: {e}", exc_info=True)

    # Server Event Listeners
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        await self._log_event(
            channel.guild.id,
            "channel_create",
            f"Channel {channel.mention} was created\n" +
            f"Type: {str(channel.type)}\n" +
            f"Category: {channel.category.name if channel.category else 'None'}"
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        await self._log_event(
            channel.guild.id,
            "channel_delete",
            f"Channel #{channel.name} was deleted\n" +
            f"Type: {str(channel.type)}\n" +
            f"Category: {channel.category.name if channel.category else 'None'}"
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        await self._log_event(
            role.guild.id,
            "role_create",
            f"Role {role.mention} was created\n" +
            f"Color: {str(role.color)}\n" +
            f"Hoisted: {role.hoist}\n" +
            f"Mentionable: {role.mentionable}"
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        await self._log_event(
            role.guild.id,
            "role_delete",
            f"Role @{role.name} was deleted\n" +
            f"Color: {str(role.color)}\n" +
            f"Members affected: {len(role.members)}"
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        if member.bot:
            return

        account_age = datetime.utcnow() - member.created_at
        await self._log_event(
            member.guild.id,
            "member_join",
            f"{member.mention} joined the server\n" +
            f"Account age: {account_age.days} days\n" +
            f"ID: {member.id}"
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        if member.bot:
            return

        roles = [role.name for role in member.roles[1:]]  # Exclude @everyone
        await self._log_event(
            member.guild.id,
            "member_leave",
            f"{member.mention} left the server\n" +
            f"Joined: {discord.utils.format_dt(member.joined_at) if member.joined_at else 'Unknown'}\n" +
            f"Roles: {', '.join(roles) if roles else 'None'}"
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Log server setting changes"""
        changes = []

        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.description != after.description:
            changes.append("Description updated")
        if before.icon != after.icon:
            changes.append("Server icon changed")
        if before.banner != after.banner:
            changes.append("Server banner changed")
        if before.verification_level != after.verification_level:
            changes.append(f"Verification Level: {before.verification_level} → {after.verification_level}")

        if changes:
            await self._log_event(
                after.id,
                "server_update",
                "Server settings updated:\n" + "\n".join(f"• {change}" for change in changes)
            )

    # Logging Configuration Commands
    @app_commands.command(name="logging")
    @app_commands.describe(
        channel="Channel to send server logs to",
        enabled="Enable or disable logging"
    )
    async def logging_setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None
    ):
        """Configure server logging settings"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "You need Manage Server permission to use this command!",
                ephemeral=True
            )

        try:
            # Get current settings
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "logging") or {}

            if channel:
                # Test permissions in the channel
                permissions = channel.permissions_for(interaction.guild.me)
                if not (permissions.send_messages and permissions.embed_links):
                    return await interaction.response.send_message(
                        f"I need Send Messages and Embed Links permissions in {channel.mention}!",
                        ephemeral=True
                    )
                settings['log_channel_id'] = channel.id

            if enabled is not None:
                settings['enabled'] = enabled

            # Update settings in database
            await self.bot.db.update_feature_settings(
                interaction.guild.id,
                "logging",
                settings
            )

            # Create response embed
            embed = discord.Embed(
                title="⚙️ Server Logging Settings",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Status",
                value="✅ Enabled" if settings.get('enabled') else "❌ Disabled",
                inline=True
            )

            if channel_id := settings.get('log_channel_id'):
                embed.add_field(
                    name="Log Channel",
                    value=f"<#{channel_id}>",
                    inline=True
                )

            embed.add_field(
                name="Logged Events",
                value="\n".join(f"• {e.replace('_', ' ').title()}" for e in self.server_events),
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            self.log.error(f"Error updating log settings: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred while updating settings: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="viewlogs")
    @app_commands.describe(
        event_type="Type of logs to view",
        limit="Number of entries to show (default: 10)",
        days="Number of days to look back (default: 7)"
    )
    async def view_logs(
        self,
        interaction: discord.Interaction,
        event_type: Optional[str] = None,
        limit: Optional[int] = 10,
        days: Optional[int] = 7
    ):
        """View server event logs"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        if not interaction.user.guild_permissions.view_audit_log:
            return await interaction.response.send_message(
                "You need View Audit Log permission to use this command!",
                ephemeral=True
            )

        try:
            # Get logs from database
            logs = await self.bot.db.get_logs(
                interaction.guild.id,
                event_type,
                limit,
                days
            )

            if not logs:
                return await interaction.response.send_message(
                    "No logs found matching the criteria!",
                    ephemeral=True
                )

            # Create paginated embeds
            embeds = []
            for i in range(0, len(logs), 5):
                embed = discord.Embed(
                    title=f"📋 Server Logs",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )

                for log in logs[i:i+5]:
                    embed.add_field(
                        name=f"{log['event_type']} • {discord.utils.format_dt(log['timestamp'], 'R')}",
                        value=log['description'],
                        inline=False
                    )

                embed.set_footer(text=f"Page {i//5 + 1}/{(len(logs)-1)//5 + 1}")
                embeds.append(embed)

            # Send first page
            await interaction.response.send_message(embed=embeds[0])

        except Exception as e:
            self.log.error(f"Error viewing logs: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred while fetching logs: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))