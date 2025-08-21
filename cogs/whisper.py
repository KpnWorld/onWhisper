import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict
import logging
from datetime import datetime

class WhisperCog(commands.Cog):
    """Private thread-based ticket system for anonymous communication"""

    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.whisper")
        # Cache for active whisper threads
        self._active_whispers: Dict[int, Dict[int, int]] = {}  # guild_id -> {user_id: thread_id}

    async def _setup_whisper_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Create or get the whisper management channel"""
        try:
            settings = await self.bot.db.get_feature_settings(guild.id, "whisper")

            # If channel already exists, return it
            if channel_id := settings.get('channel_id'):
                channel = guild.get_channel(channel_id)
                if channel:
                    return channel

            # Create new channel with proper permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_threads=True,
                    manage_messages=True
                )
            }

            # Add staff role permissions if configured
            if staff_role_id := settings.get('staff_role_id'):
                if staff_role := guild.get_role(staff_role_id):
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_threads=True
                    )

            channel = await guild.create_text_channel(
                name="🤫-whispers",
                topic="Private communication channel - Staff only",
                overwrites=overwrites,
                reason="Whisper system setup"
            )

            # Update settings with new channel
            settings['channel_id'] = channel.id
            await self.bot.db.update_feature_settings(guild.id, "whisper", settings)

            return channel

        except Exception as e:
            self.log.error(f"Error setting up whisper channel: {e}", exc_info=True)
            return None

    async def _create_whisper_thread(self, channel: discord.TextChannel, 
                                   user: discord.Member, reason: str) -> Optional[discord.Thread]:
        """Create a new whisper thread"""
        try:
            # Create thread with anonymous name
            thread = await channel.create_thread(
                name=f"Whisper-{user.id}",
                type=discord.ChannelType.private_thread,
                reason=f"Whisper thread for {user}"
            )

            # Create initial message with metadata
            embed = discord.Embed(
                title="New Whisper Thread",
                description=reason or "No reason provided",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} ({user.id})")
            embed.add_field(name="Created", value=discord.utils.format_dt(datetime.utcnow(), 'R'))

            await thread.send(embed=embed)

            # Store in database
            await self.bot.db.create_whisper(
                guild_id=channel.guild.id,
                user_id=user.id,
                thread_id=thread.id
            )

            # Update cache
            if channel.guild.id not in self._active_whispers:
                self._active_whispers[channel.guild.id] = {}
            self._active_whispers[channel.guild.id][user.id] = thread.id

            return thread

        except Exception as e:
            self.log.error(f"Error creating whisper thread: {e}", exc_info=True)
            return None

    @app_commands.command(name="whisper")
    @app_commands.describe(reason="Reason for opening the whisper thread")
    async def create_whisper(self, interaction: discord.Interaction, reason: Optional[str] = None):
        """Open a private whisper thread for anonymous communication with staff"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Check if whispers are enabled
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "whisper")
            if not settings or not settings.get('enabled'):
                return await interaction.response.send_message(
                    "The whisper system is not enabled in this server.",
                    ephemeral=True
                )

            # Check if user already has an active whisper
            if (active_whispers := self._active_whispers.get(interaction.guild.id)) and \
               interaction.user.id in active_whispers:
                thread_id = active_whispers[interaction.user.id]
                return await interaction.response.send_message(
                    f"You already have an active whisper thread: <#{thread_id}>",
                    ephemeral=True
                )

            await interaction.response.defer(ephemeral=True)

            # Get or create whisper channel
            channel = await self._setup_whisper_channel(interaction.guild)
            if not channel:
                return await interaction.followup.send(
                    "Failed to set up whisper channel. Please contact an administrator.",
                    ephemeral=True
                )

            # Create thread
            thread = await self._create_whisper_thread(channel, interaction.user, reason)
            if not thread:
                return await interaction.followup.send(
                    "Failed to create whisper thread. Please try again later.",
                    ephemeral=True
                )

            await interaction.followup.send(
                f"✅ Whisper thread created: {thread.mention}\n" +
                "Staff will respond to your message soon.",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error creating whisper: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while creating the whisper thread.",
                ephemeral=True
            )

    @app_commands.command(name="close")
    @app_commands.describe(reason="Reason for closing the whisper thread")
    async def close_whisper(self, interaction: discord.Interaction, reason: Optional[str] = None):
        """Close an active whisper thread"""
        if not interaction.guild or not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message(
                "This command can only be used in a whisper thread!",
                ephemeral=True
            )

        try:
            # Verify this is a whisper thread
            whisper = await self.bot.db.get_whisper_by_thread(
                interaction.guild.id,
                interaction.channel.id
            )
            if not whisper:
                return await interaction.response.send_message(
                    "This is not a whisper thread!",
                    ephemeral=True
                )

            # Check permissions
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "whisper")
            is_staff = False
            if staff_role_id := settings.get('staff_role_id'):
                is_staff = any(role.id == staff_role_id for role in interaction.user.roles)

            if not (is_staff or interaction.user.id == whisper['user_id']):
                return await interaction.response.send_message(
                    "You don't have permission to close this thread!",
                    ephemeral=True
                )

            # Send closing message
            embed = discord.Embed(
                title="Whisper Thread Closed",
                description=reason or "No reason provided",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Closed by", value=interaction.user.mention)
            await interaction.channel.send(embed=embed)

            # Update database
            await self.bot.db.close_whisper(
                guild_id=interaction.guild.id,
                thread_id=interaction.channel.id
            )

            # Update cache
            if interaction.guild.id in self._active_whispers:
                self._active_whispers[interaction.guild.id].pop(whisper['user_id'], None)

            # Archive and lock the thread
            await interaction.channel.edit(archived=True, locked=True)

            await interaction.response.send_message(
                "✅ Whisper thread closed.",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error closing whisper: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while closing the whisper thread.",
                ephemeral=True
            )

    @app_commands.command(name="whisper-setup")
    @app_commands.describe(
        staff_role="Role that can view and respond to whispers",
        enabled="Enable or disable the whisper system"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def setup_whispers(
        self,
        interaction: discord.Interaction,
        staff_role: Optional[discord.Role] = None,
        enabled: Optional[bool] = None
    ):
        """Configure the whisper system"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "whisper") or {}

            if staff_role:
                settings['staff_role_id'] = staff_role.id

            if enabled is not None:
                settings['enabled'] = enabled

            # Update settings
            await self.bot.db.update_feature_settings(
                interaction.guild.id,
                "whisper",
                settings
            )

            # Create response embed
            embed = discord.Embed(
                title="⚙️ Whisper System Settings",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Status",
                value="✅ Enabled" if settings.get('enabled') else "❌ Disabled",
                inline=True
            )

            if staff_role_id := settings.get('staff_role_id'):
                embed.add_field(
                    name="Staff Role",
                    value=f"<@&{staff_role_id}>",
                    inline=True
                )

            if channel_id := settings.get('channel_id'):
                embed.add_field(
                    name="Whisper Channel",
                    value=f"<#{channel_id}>",
                    inline=True
                )

            await interaction.response.send_message(embed=embed)

            # Setup channel if enabled
            if enabled:
                await self._setup_whisper_channel(interaction.guild)

        except Exception as e:
            self.log.error(f"Error updating whisper settings: {e}", exc_info=True)
            await interaction.response.send_message(
                f"An error occurred while updating settings: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="list-whispers")
    @app_commands.default_permissions(manage_guild=True)
    async def list_whispers(self, interaction: discord.Interaction):
        """List all active whisper threads"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Verify staff role
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "whisper")
            if not settings or not settings.get('staff_role_id'):
                return await interaction.response.send_message(
                    "Whisper system is not properly configured.",
                    ephemeral=True
                )

            if not any(role.id == settings['staff_role_id'] for role in interaction.user.roles):
                return await interaction.response.send_message(
                    "You don't have permission to view whisper threads!",
                    ephemeral=True
                )

            # Get active whispers
            whispers = await self.bot.db.get_active_whispers(interaction.guild.id)
            if not whispers:
                return await interaction.response.send_message(
                    "No active whisper threads.",
                    ephemeral=True
                )

            # Create embed
            embed = discord.Embed(
                title="📝 Active Whisper Threads",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            for whisper in whispers:
                user = interaction.guild.get_member(whisper['user_id'])
                thread = interaction.guild.get_thread(whisper['thread_id'])

                if user and thread:
                    embed.add_field(
                        name=f"Thread: {thread.name}",
                        value=f"User: {user.mention}\n" +
                              f"Created: {discord.utils.format_dt(whisper['created_at'], 'R')}",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.log.error(f"Error listing whispers: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while fetching whisper threads.",
                ephemeral=True
            )

    async def cog_load(self):
        """Load active whispers into cache on startup"""
        for guild in self.bot.guilds:
            try:
                whispers = await self.bot.db.get_active_whispers(guild.id)
                if whispers:
                    self._active_whispers[guild.id] = {
                        w['user_id']: w['thread_id'] for w in whispers
                    }
            except Exception as e:
                self.log.error(f"Error loading whispers for guild {guild.id}: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))