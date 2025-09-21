# cogs/whisper.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Union
import logging
from datetime import datetime, timezone

from utils.db_manager import DBManager
from utils.config import ConfigManager

logger = logging.getLogger("onWhisper.Whisper")


class WhisperModal(discord.ui.Modal, title='Create Whisper Thread'):
    """Modal form for creating whisper threads with reason input"""
    
    def __init__(self, whisper_cog: 'WhisperCog'):
        super().__init__()
        self.whisper_cog = whisper_cog
    
    reason = discord.ui.TextInput(
        label='Reason for Whisper',
        style=discord.TextStyle.paragraph,
        placeholder='Please describe why you need to create a whisper thread...',
        required=True,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal form submission"""
        try:
            # Check if whispers are enabled
            whisper_enabled = await self.whisper_cog.config.get(interaction.guild.id, "whisper_enabled", True)
            if not whisper_enabled:
                return await interaction.response.send_message(
                    "❌ The whisper system is not enabled in this server.",
                    ephemeral=True
                )

            # Check if user already has an active whisper
            existing_whispers = await self.whisper_cog.db.fetchall(
                "SELECT thread_id FROM whispers WHERE guild_id = ? AND user_id = ? AND is_open = ?",
                (interaction.guild.id, interaction.user.id, 1)
            )
            if existing_whispers:
                thread_id = existing_whispers[0]['thread_id']
                return await interaction.response.send_message(
                    f"ℹ️ You already have an active whisper thread: <#{thread_id}>",
                    ephemeral=True
                )

            # Check 24-hour cooldown for closed whispers
            try:
                last_closed = await self.whisper_cog.db.fetchone(
                    "SELECT closed_at FROM whispers WHERE guild_id = ? AND user_id = ? AND is_open = ? AND closed_by_staff = ? ORDER BY closed_at DESC LIMIT 1",
                    (interaction.guild.id, interaction.user.id, 0, 1)
                )
            except:
                # Fallback if column doesn't exist yet
                last_closed = None
            
            if last_closed and last_closed['closed_at']:
                closed_time = datetime.fromisoformat(last_closed['closed_at'].replace('Z', '+00:00'))
                time_since_closed = datetime.utcnow().replace(tzinfo=timezone.utc) - closed_time
                hours_since_closed = time_since_closed.total_seconds() / 3600
                
                if hours_since_closed < 24:
                    hours_remaining = 24 - hours_since_closed
                    if hours_remaining >= 1:
                        return await interaction.response.send_message(
                            f"⏰ You must wait {hours_remaining:.1f} more hours before creating a new whisper thread (24-hour cooldown after staff closure).",
                            ephemeral=True
                        )
                    else:
                        minutes_remaining = hours_remaining * 60
                        return await interaction.response.send_message(
                            f"⏰ You must wait {minutes_remaining:.0f} more minutes before creating a new whisper thread (24-hour cooldown after staff closure).",
                            ephemeral=True
                        )

            await interaction.response.defer(ephemeral=True)

            # Get or create whisper channel
            channel = await self.whisper_cog._setup_whisper_channel(interaction.guild)
            if not channel:
                return await interaction.followup.send(
                    "❌ Failed to set up whisper channel. Please contact an administrator.",
                    ephemeral=True
                )

            # Create thread and get whisper number using the reason from the modal
            thread, whisper_number = await self.whisper_cog._create_whisper_thread(channel, interaction.user, self.reason.value)
            if not thread or whisper_number == "ERROR":
                return await interaction.followup.send(
                    "❌ Failed to create whisper thread. Please try again later.",
                    ephemeral=True
                )

            await interaction.followup.send(
                f"✅ Whisper thread **{whisper_number}** created successfully!\n" +
                f"📍 Access your whisper thread here: {thread.mention}\n" +
                "Staff will respond to your message soon.",
                ephemeral=True
            )

            logger.info(f"Created whisper thread {whisper_number} ({thread.id}) for user {interaction.user.id} in guild {interaction.guild.id}")

        except Exception as e:
            logger.error(f"Error in whisper modal submission for user {interaction.user.id} in guild {interaction.guild.id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while creating the whisper thread. Please try again later.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while creating the whisper thread. Please try again later.",
                    ephemeral=True
                )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors"""
        logger.error(f"Modal error for user {interaction.user.id}: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while processing the form. Please try again.",
                ephemeral=True
            )


class WhisperCog(commands.Cog):
    """🤫 Private thread-based whisper system for anonymous communication"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db_manager
        self.config: ConfigManager = bot.config_manager
        # Cache for active whisper threads
        self._active_whispers: Dict[int, Dict[int, int]] = {}  # guild_id -> {user_id: thread_id}

    async def _setup_whisper_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Create or get the whisper management channel"""
        try:
            # Get whisper channel from config
            whisper_channel_id = await self.config.get(guild.id, "whisper_channel")
            whisper_enabled = await self.config.get(guild.id, "whisper_enabled", True)

            # If channel already exists, return it
            if whisper_channel_id:
                # Extract channel ID from mention format or use as-is
                if isinstance(whisper_channel_id, str) and whisper_channel_id.startswith('<#'):
                    channel_id = int(whisper_channel_id[2:-1])  # Remove <# and >
                else:
                    channel_id = int(whisper_channel_id)
                    
                channel = guild.get_channel(channel_id)
                if channel:
                    return channel

            # Create new channel with proper permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,  # Users can see the channel and threads
                    send_messages=False,  # Users cannot send messages in main channel
                    create_private_threads=False  # Users cannot create threads
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_threads=True,
                    manage_messages=True
                )
            }

            channel = await guild.create_text_channel(
                name="🤫-whispers",
                topic="Private communication channel - Whisper threads visible to all, managed by staff",
                overwrites=overwrites,
                reason="Whisper system setup"
            )

            # Update config with new channel
            await self.config.set(guild.id, "whisper_channel", channel.id)
            logger.info(f"Created whisper channel {channel.name} ({channel.id}) in guild {guild.name} ({guild.id})")

            return channel

        except Exception as e:
            logger.error(f"Error setting up whisper channel in guild {guild.id}: {e}")
            return None

    async def _create_whisper_thread(self, channel: discord.TextChannel, 
                                   user: discord.Member, reason: str) -> tuple[Optional[discord.Thread], int]:
        """Create a new whisper thread"""
        try:
            # Get next whisper number first
            whisper_count = await self.db.fetchone(
                "SELECT COUNT(*) as count FROM whispers WHERE guild_id = ?",
                (channel.guild.id,)
            )
            whisper_number = (whisper_count['count'] if whisper_count else 0) + 1
            
            # Get server prefix (first two letters)
            server_prefix = channel.guild.name[:2].upper()
            
            # Create thread with server prefix + numbered name
            thread = await channel.create_thread(
                name=f"{server_prefix}{whisper_number:03d}",
                type=discord.ChannelType.private_thread,
                reason=f"Whisper thread {server_prefix}{whisper_number:03d} for {user}"
            )
            
            # Add the user to the thread so they can access it
            await thread.add_user(user)

            # Now create whisper in database with actual thread ID
            await self.db.create_whisper(channel.guild.id, user.id, thread.id)

            # Create initial message with metadata
            embed = discord.Embed(
                title="New Whisper Thread",
                description=reason or "No reason provided",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Whisper ID", value=f"{server_prefix}{whisper_number:03d}", inline=True)
            embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(datetime.utcnow(), 'R'), inline=True)

            await thread.send(embed=embed)
            
            logger.info(f"Created whisper thread {server_prefix}{whisper_number:03d} ({thread.id}) for user {user.id} in guild {channel.guild.id}")

            # Update cache
            if channel.guild.id not in self._active_whispers:
                self._active_whispers[channel.guild.id] = {}
            self._active_whispers[channel.guild.id][user.id] = thread.id

            return thread, f"{server_prefix}{whisper_number:03d}"

        except Exception as e:
            logger.error(f"Error creating whisper thread for user {user.id} in guild {channel.guild.id}: {e}")
            return None, "ERROR"

    @app_commands.command(name="whisper")
    async def create_whisper(self, interaction: discord.Interaction):
        """Open a private whisper thread for anonymous communication with staff"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Show the modal form for whisper creation
            modal = WhisperModal(self)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error showing whisper modal for user {interaction.user.id} in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while opening the whisper form. Please try again later.",
                ephemeral=True
            )


    @app_commands.command(name="whisper-setup")
    @app_commands.describe(
        enabled="Enable or disable the whisper system",
        channel="Channel for whisper threads (will create one if not specified)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def setup_whispers(
        self,
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure the whisper system"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Update configuration
            if enabled is not None:
                await self.config.set(interaction.guild.id, "whisper_enabled", enabled)
                
            if channel:
                await self.config.set(interaction.guild.id, "whisper_channel", channel.id)

            # Get current settings for display
            whisper_enabled = await self.config.get(interaction.guild.id, "whisper_enabled", True)
            whisper_channel_id = await self.config.get(interaction.guild.id, "whisper_channel")
            
            # Create response embed
            embed = discord.Embed(
                title="⚙️ Whisper System Settings",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Status",
                value="✅ Enabled" if whisper_enabled else "❌ Disabled",
                inline=True
            )

            if whisper_channel_id:
                embed.add_field(
                    name="Whisper Channel",
                    value=f"<#{whisper_channel_id}>",
                    inline=True
                )
                
            embed.add_field(
                name="Usage",
                value="Use `/whisper` to create a private thread",
                inline=False
            )

            await interaction.response.send_message(embed=embed)

            # Setup channel if enabled and no channel specified
            if enabled and not whisper_channel_id:
                await self._setup_whisper_channel(interaction.guild)
                
            logger.info(f"Updated whisper settings in guild {interaction.guild.id} by {interaction.user.id}")

        except Exception as e:
            logger.error(f"Error updating whisper settings in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred while updating settings: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="whisper-view")
    @app_commands.describe(whisper_number="Whisper number to view details for")
    @app_commands.default_permissions(manage_guild=True)
    async def view_whisper(self, interaction: discord.Interaction, whisper_number: int):
        """View details of a specific whisper thread by number"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "❌ You don't have permission to view whisper threads!",
                    ephemeral=True
                )

            # Get all whispers and find the specific one by position
            whispers = await self.db.fetchall(
                "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? ORDER BY created_at",
                (interaction.guild.id,)
            )
            
            server_prefix = interaction.guild.name[:2].upper()
            if not whispers or whisper_number < 1 or whisper_number > len(whispers):
                return await interaction.response.send_message(
                    f"❌ Whisper {server_prefix}{whisper_number:03d} not found!",
                    ephemeral=True
                )

            whisper = whispers[whisper_number - 1]
            user = interaction.guild.get_member(whisper['user_id'])
            thread = interaction.guild.get_thread(whisper['thread_id'])

            embed = discord.Embed(
                title=f"🔍 Whisper {server_prefix}{whisper_number:03d} Details",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            if user:
                embed.add_field(name="User", value=f"{user.mention} ({user.display_name})", inline=True)
            else:
                embed.add_field(name="User", value=f"User ID: {whisper['user_id']}", inline=True)

            if thread:
                embed.add_field(name="Thread", value=thread.mention, inline=True)
                embed.add_field(name="Status", value="🟢 Active" if not thread.archived else "🔴 Archived", inline=True)
            else:
                embed.add_field(name="Thread", value="Thread not found", inline=True)
                embed.add_field(name="Status", value="🔴 Deleted", inline=True)

            embed.add_field(name="Created", value=discord.utils.format_dt(whisper['created_at'], 'F'), inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            server_prefix = interaction.guild.name[:2].upper()
            logger.error(f"Error viewing whisper {server_prefix}{whisper_number:03d} in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while viewing the whisper thread.",
                ephemeral=True
            )

    @app_commands.command(name="whisper-delete")
    @app_commands.describe(
        whisper_number="Whisper number to permanently delete (leave empty to delete all closed whispers)",
        all_closed="Set to True to delete all closed whispers at once"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def delete_whisper(self, interaction: discord.Interaction, whisper_number: Optional[int] = None, all_closed: bool = False):
        """Permanently delete a whisper thread and its database record, or delete all closed whispers"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "❌ You don't have permission to delete whisper threads!",
                    ephemeral=True
                )

            server_prefix = interaction.guild.name[:2].upper()

            # Handle bulk deletion of closed whispers
            if all_closed or whisper_number is None:
                # Get all closed whispers
                closed_whispers = await self.db.fetchall(
                    "SELECT user_id, thread_id FROM whispers WHERE guild_id = ? AND is_open = ?",
                    (interaction.guild.id, 0)
                )
                
                if not closed_whispers:
                    return await interaction.response.send_message(
                        "ℹ️ No closed whispers found to delete.",
                        ephemeral=True
                    )

                deleted_count = 0
                for whisper in closed_whispers:
                    thread = interaction.guild.get_thread(whisper['thread_id'])
                    
                    # Delete the thread if it exists
                    if thread:
                        try:
                            await thread.delete(reason=f"Bulk closed whisper cleanup by {interaction.user}")
                            deleted_count += 1
                        except:
                            pass  # Thread might already be deleted
                    
                    # Remove from database
                    await self.db.execute(
                        "DELETE FROM whispers WHERE guild_id = ? AND thread_id = ?",
                        (interaction.guild.id, whisper['thread_id'])
                    )

                # Clear cache for closed whispers
                if interaction.guild.id in self._active_whispers:
                    for whisper in closed_whispers:
                        self._active_whispers[interaction.guild.id].pop(whisper['user_id'], None)

                await interaction.response.send_message(
                    f"✅ Successfully deleted {len(closed_whispers)} closed whisper threads from database ({deleted_count} threads also removed from Discord).",
                    ephemeral=True
                )
                
                logger.info(f"Bulk deleted {len(closed_whispers)} closed whispers in guild {interaction.guild.id} by {interaction.user.id}")
                return

            # Handle single whisper deletion
            if whisper_number is None:
                return await interaction.response.send_message(
                    "❌ Please specify a whisper number to delete, or use `all_closed=True` to delete all closed whispers.",
                    ephemeral=True
                )

            # Get all whispers and find the specific one by position
            whispers = await self.db.fetchall(
                "SELECT user_id, thread_id FROM whispers WHERE guild_id = ? ORDER BY created_at",
                (interaction.guild.id,)
            )
            
            if not whispers or whisper_number < 1 or whisper_number > len(whispers):
                return await interaction.response.send_message(
                    f"❌ Whisper {server_prefix}{whisper_number:03d} not found!",
                    ephemeral=True
                )

            whisper = whispers[whisper_number - 1]
            thread = interaction.guild.get_thread(whisper['thread_id'])

            # Delete the thread if it exists
            if thread:
                await thread.delete(reason=f"Whisper {server_prefix}{whisper_number:03d} deleted by {interaction.user}")

            # Remove from database
            await self.db.execute(
                "DELETE FROM whispers WHERE guild_id = ? AND thread_id = ?",
                (interaction.guild.id, whisper['thread_id'])
            )

            # Update cache
            if interaction.guild.id in self._active_whispers:
                self._active_whispers[interaction.guild.id].pop(whisper['user_id'], None)

            await interaction.response.send_message(
                f"✅ Whisper {server_prefix}{whisper_number:03d} has been permanently deleted.",
                ephemeral=True
            )
            
            logger.info(f"Deleted whisper {server_prefix}{whisper_number:03d} (thread {whisper['thread_id']}) in guild {interaction.guild.id} by {interaction.user.id}")

        except Exception as e:
            logger.error(f"Error deleting whisper #{whisper_number} in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while deleting the whisper thread.",
                ephemeral=True
            )

    @app_commands.command(name="whisper-close")
    @app_commands.describe(whisper_number="Whisper number to close (optional if used in thread)", reason="Reason for closing")
    async def close_whisper_by_number(self, interaction: discord.Interaction, whisper_number: Optional[int] = None, reason: Optional[str] = None):
        """Close a whisper thread by number or close the current thread"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            target_thread_id = None
            
            # If whisper_number is provided, find that specific whisper
            if whisper_number is not None:
                # Check permissions for closing by number
                if not interaction.user.guild_permissions.administrator:
                    return await interaction.response.send_message(
                        "❌ You don't have permission to close whisper threads by number!",
                        ephemeral=True
                    )
                    
                whispers = await self.db.fetchall(
                    "SELECT user_id, thread_id FROM whispers WHERE guild_id = ? AND is_open = ? ORDER BY created_at",
                    (interaction.guild.id, 1)
                )
                
                server_prefix = interaction.guild.name[:2].upper()
                if not whispers or whisper_number < 1 or whisper_number > len(whispers):
                    return await interaction.response.send_message(
                        f"❌ Active whisper {server_prefix}{whisper_number:03d} not found!",
                        ephemeral=True
                    )
                    
                whisper = whispers[whisper_number - 1]
                target_thread_id = whisper['thread_id']
                target_thread = interaction.guild.get_thread(target_thread_id)
                
            else:
                # Close current thread if we're in one
                if not isinstance(interaction.channel, discord.Thread):
                    return await interaction.response.send_message(
                        "❌ This command must be used in a whisper thread or with a whisper number!",
                        ephemeral=True
                    )
                target_thread_id = interaction.channel.id
                target_thread = interaction.channel

            # Verify this is a whisper thread
            whisper = await self.db.fetchone(
                "SELECT user_id FROM whispers WHERE guild_id = ? AND thread_id = ? AND is_open = ?",
                (interaction.guild.id, target_thread_id, 1)
            )
            
            if not whisper:
                return await interaction.response.send_message(
                    "❌ This is not an active whisper thread!",
                    ephemeral=True
                )

            # Check permissions (admins and thread creator can close)
            is_staff = interaction.user.guild_permissions.administrator
            if not (is_staff or interaction.user.id == whisper['user_id']):
                return await interaction.response.send_message(
                    "❌ You don't have permission to close this thread!",
                    ephemeral=True
                )

            # Send closing message to the thread
            if target_thread:
                embed = discord.Embed(
                    title="Whisper Thread Closed",
                    description=reason or "No reason provided",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Closed by", value=interaction.user.mention)
                await target_thread.send(embed=embed)
                
                # Archive and lock the thread
                await target_thread.edit(archived=True, locked=True)

            # Update database (check if closed by staff)
            is_staff = interaction.user.guild_permissions.administrator
            await self.db.execute(
                "UPDATE whispers SET is_open = ?, closed_at = ?, closed_by_staff = ? WHERE guild_id = ? AND thread_id = ?",
                (0, datetime.utcnow(), 1 if is_staff else 0, interaction.guild.id, target_thread_id)
            )

            # Send DM to user if closed by staff
            if is_staff and whisper:
                user = interaction.guild.get_member(whisper['user_id'])
                if user:
                    try:
                        embed = discord.Embed(
                            title="🔒 Whisper Thread Closed",
                            description=f"Your whisper thread in **{interaction.guild.name}** has been closed by staff.",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        embed.add_field(
                            name="Reason",
                            value=reason or "No reason provided",
                            inline=False
                        )
                        embed.add_field(
                            name="⏰ Next Whisper Available",
                            value="You can create a new whisper thread in **24 hours**.",
                            inline=False
                        )
                        embed.add_field(
                            name="Questions?",
                            value="If you have questions about this closure, please contact server staff.",
                            inline=False
                        )
                        
                        await user.send(embed=embed)
                        logger.info(f"Sent closure DM to user {user.id} for whisper in guild {interaction.guild.id}")
                    except discord.Forbidden:
                        logger.warning(f"Could not DM user {user.id} about whisper closure - DMs disabled")
                    except Exception as e:
                        logger.error(f"Error sending DM to user {user.id}: {e}")

            # Update cache
            if interaction.guild.id in self._active_whispers:
                self._active_whispers[interaction.guild.id].pop(whisper['user_id'], None)

            await interaction.response.send_message(
                f"✅ Whisper thread closed successfully.",
                ephemeral=True
            )
            
            logger.info(f"Closed whisper thread {target_thread_id} by {interaction.user.id} in guild {interaction.guild.id}")

        except Exception as e:
            logger.error(f"Error closing whisper thread in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while closing the whisper thread.",
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
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "❌ You don't have permission to view whisper threads!",
                    ephemeral=True
                )

            # Get active whispers
            whispers = await self.db.fetchall(
                "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? AND is_open = ?",
                (interaction.guild.id, 1)
            )
            if not whispers:
                return await interaction.response.send_message(
                    "ℹ️ No active whisper threads.",
                    ephemeral=True
                )

            # Create embed
            embed = discord.Embed(
                title="📝 Active Whisper Threads",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            server_prefix = interaction.guild.name[:2].upper()
            for i, whisper in enumerate(whispers, 1):
                user = interaction.guild.get_member(whisper['user_id'])
                thread = interaction.guild.get_thread(whisper['thread_id'])

                if user and thread:
                    # Parse the datetime string from database
                    created_dt = datetime.fromisoformat(whisper['created_at'].replace('Z', '+00:00'))
                    embed.add_field(
                        name=f"Whisper {server_prefix}{i:03d}: {thread.name}",
                        value=f"User: {user.mention}\n" +
                              f"Link: {thread.mention}\n" +
                              f"Created: {discord.utils.format_dt(created_dt, 'R')}",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing whispers in guild {interaction.guild.id}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching whisper threads.",
                ephemeral=True
            )

    async def cog_load(self):
        """Load active whispers into cache on startup"""
        for guild in self.bot.guilds:
            try:
                whispers = await self.db.fetchall(
                    "SELECT user_id, thread_id FROM whispers WHERE guild_id = ? AND is_open = ?",
                    (guild.id, 1)
                )
                if whispers:
                    self._active_whispers[guild.id] = {
                        w['user_id']: w['thread_id'] for w in whispers
                    }
                    logger.info(f"Loaded {len(whispers)} active whispers for guild {guild.id}")
            except Exception as e:
                logger.error(f"Error loading whispers for guild {guild.id}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(WhisperCog(bot))