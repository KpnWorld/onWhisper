import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_threads.start()
        self.cleanup_old_whispers.start()
        self._cd = commands.CooldownMapping.from_cooldown(1, 300, commands.BucketType.member)  # 5 min cooldown

    def cog_unload(self):
        self.check_threads.cancel()
        self.cleanup_old_whispers.cancel()

    @tasks.loop(minutes=5.0)
    async def check_threads(self):
        """Check for inactive whisper threads"""
        try:
            for guild in self.bot.guilds:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                if not config.get('enabled', True):
                    continue
                    
                timeout = config.get('timeout', 60)  # Default 60 minutes
                whispers = await self.bot.db_manager.get_active_whispers(guild.id)
                
                for whisper in whispers:
                    try:
                        thread = self.bot.get_channel(int(whisper['thread_id']))
                        
                        # Handle deleted threads
                        if not thread:
                            print(f"Thread {whisper['thread_id']} not found, marking as closed")
                            await self.bot.db_manager.close_whisper(guild.id, whisper['thread_id'])
                            continue

                        # Skip if thread is already archived
                        if thread.archived:
                            await self.bot.db_manager.close_whisper(guild.id, str(thread.id))
                            continue

                        # Get last message properly with async for
                        last_message = None
                        try:
                            async for message in thread.history(limit=1):
                                last_message = message
                                break
                        except discord.Forbidden:
                            print(f"No permission to read thread {thread.id}")
                            continue
                        except discord.HTTPException as e:
                            print(f"Error reading thread history: {e}")
                            continue

                        if not last_message:
                            continue

                        # Use timezone-aware datetime comparison
                        inactive_time = datetime.now(timezone.utc) - last_message.created_at
                        if inactive_time > timedelta(minutes=timeout):
                            try:
                                # Attempt to send closing message
                                await thread.send(embed=self.bot.ui_manager.warning_embed(
                                    "Thread Closing",
                                    f"This thread has been inactive for {timeout} minutes and will be closed."
                                ))
                                
                                # Close the thread
                                await thread.edit(archived=True, locked=True)
                                
                                # Only mark as closed if archive was successful
                                await self.bot.db_manager.close_whisper(guild.id, str(thread.id))

                                # Log auto-closure
                                log_config = await self.bot.db_manager.get_logging_config(guild.id)
                                if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                                    log_channel = guild.get_channel(int(log_config['log_channel']))
                                    if log_channel:
                                        embed = self.bot.ui_manager.log_embed(
                                            "Whisper Auto-Closed",
                                            f"Whisper thread automatically closed due to {timeout} minutes of inactivity",
                                            self.bot.user
                                        )
                                        embed.add_field(name="Thread", value=thread.mention)
                                        await log_channel.send(embed=embed)
                            except discord.Forbidden:
                                print(f"Missing permissions to close thread {thread.id}")
                            except discord.HTTPException as e:
                                print(f"Error closing thread {thread.id}: {e}")
                    except Exception as e:
                        print(f"Error processing thread {whisper['thread_id']}: {e}")
                        continue

        except Exception as e:
            print(f"Error in thread checker: {e}")
            
    @check_threads.before_loop
    async def before_check_threads(self):
        """Wait for the bot to be ready before starting the thread checker"""
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24.0)
    async def cleanup_old_whispers(self):
        """Cleanup old whispers from the database daily"""
        try:
            for guild in self.bot.guilds:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                if not config.get('enabled', True):
                    continue
                
                retention_days = config.get('retention_days', 30)  # Default 30 days retention
                cleaned = await self.bot.db_manager.cleanup_old_whispers(guild.id, retention_days)
                
                if cleaned:
                    # Log cleanup if logging is enabled
                    log_config = await self.bot.db_manager.get_logging_config(guild.id)
                    if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                        log_channel = guild.get_channel(int(log_config['log_channel']))
                        if log_channel:
                            embed = self.bot.ui_manager.log_embed(
                                "Whispers Cleaned Up",
                                f"Old whispers (closed > {retention_days} days ago) have been cleaned from the database",
                                self.bot.user
                            )
                            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error in whisper cleanup: {e}")

    @app_commands.command(
        name="whisper",
        description="Start a private thread to talk with staff"
    )
    @app_commands.describe(
        message="Your initial message to staff"
    )
    async def whisper(self, interaction: discord.Interaction, message: str):
        """Start a private whisper thread to staff"""
        try:
            # Defer the response immediately to prevent timeout
            await interaction.response.defer(ephemeral=True)
            
            # Check if whispers are enabled
            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            if not config.get('enabled', True):
                raise self.bot.WhisperNotEnabled("The whisper system is disabled in this server")

            # Get staff role
            staff_role_id = config.get('staff_role')
            if not staff_role_id:
                raise self.bot.WhisperNotConfigured("No staff role has been set for whispers")

            staff_role = interaction.guild.get_role(int(staff_role_id))
            if not staff_role:
                raise self.bot.WhisperNotConfigured("Staff role not found")

            # Get whisper channel
            channel_id = config.get('channel_id')
            if not channel_id:
                raise self.bot.WhisperNotConfigured("No whisper channel has been configured. An admin must run /config_whisper_channel first")

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise self.bot.WhisperNotConfigured("Configured whisper channel no longer exists")

            # Check thread limit before creating
            try:
                if len(channel.threads) >= 50:  # Discord's thread limit per channel
                    raise self.bot.WhisperThreadError("Cannot create more threads in this channel. Please wait for some to be archived.")
            except discord.Forbidden:
                raise self.bot.WhisperThreadError("I don't have permission to view threads in the whisper channel")

            # Create private thread with retries for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    thread = await channel.create_thread(
                        name=f"whisper-{interaction.user.name}",
                        type=discord.ChannelType.private_thread,
                        reason=f"Whisper thread created by {interaction.user}"
                    )
                    break
                except discord.HTTPException as e:
                    if e.code == 30033:  # Active thread limit reached
                        raise self.bot.WhisperThreadError("Maximum number of active threads reached. Please wait for some to be archived.")
                    elif attempt == max_retries - 1:  # Last attempt
                        raise
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                raise self.bot.WhisperThreadError("Failed to create thread after multiple attempts")

            # Store whisper data
            try:
                success = await self.bot.db_manager.add_whisper(
                    interaction.guild_id,
                    str(thread.id),
                    str(interaction.user.id),
                    str(channel.id)
                )
                if not success:
                    # If DB storage fails, try to clean up the thread
                    try:
                        await thread.delete()
                    except:
                        pass
                    raise self.bot.WhisperThreadError("Failed to store whisper data")
            except Exception as e:
                # If DB storage fails, try to clean up the thread
                try:
                    await thread.delete()
                except:
                    pass
                raise self.bot.WhisperThreadError(f"Failed to store whisper data: {str(e)}")

            # Log whisper creation
            log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
            if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                if log_channel:
                    embed = self.bot.ui_manager.log_embed(
                        "Whisper Created",
                        f"A new whisper thread was created by {interaction.user.mention}",
                        interaction.user
                    )
                    embed.add_field(name="Thread", value=thread.mention)
                    await log_channel.send(embed=embed)

            # Send initial message in thread
            await thread.send(
                f"{staff_role.mention} New whisper from {interaction.user.mention}",
                embed=self.bot.ui_manager.whisper_embed(
                    "New Whisper Thread",
                    message
                )
            )

            # Add user and notify about auto-close
            await thread.add_user(interaction.user)
            timeout = config.get('timeout', 60)
            await thread.send(
                embed=self.bot.ui_manager.info_embed(
                    "Auto-Close Timer",
                    f"This thread will automatically close after {timeout} minutes of inactivity"
                )
            )

            # Send success message to user
            await interaction.followup.send(
                embed=self.bot.ui_manager.success_embed(
                    "Thread Created",
                    f"I've created a private thread for your message. Click here to join: {thread.mention}\n\nThe thread will close automatically after {timeout} minutes of inactivity."
                ),
                ephemeral=True
            )

        except self.bot.WhisperError as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="whisper_close",
        description="Manually close your whisper thread"
    )
    async def whisper_close(self, interaction: discord.Interaction):
        """Manually close a whisper thread"""
        try:
            # Defer response to prevent timeout
            await interaction.response.defer(ephemeral=True)

            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in a whisper thread")

            # Check if thread is already archived
            if interaction.channel.archived:
                raise commands.CommandError("This thread is already closed")

            whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
            whisper = next((w for w in whispers if int(w['thread_id']) == interaction.channel.id), None)

            if not whisper:
                raise commands.CommandError("This is not an active whisper thread")

            if str(interaction.user.id) != whisper['user_id'] and not interaction.user.guild_permissions.manage_threads:
                raise commands.MissingPermissions(["manage_threads"])

            try:
                # Send closing notification
                await interaction.channel.send(embed=self.bot.ui_manager.warning_embed(
                    "Thread Closing",
                    f"Thread manually closed by {interaction.user.mention}"
                ))
                
                # Try to archive and lock the thread
                await interaction.channel.edit(archived=True, locked=True)

                # Only mark as closed in DB if archive was successful
                await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))

                # Log whisper closure if logging is enabled
                log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                    log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                    if log_channel:
                        embed = self.bot.ui_manager.log_embed(
                            "Whisper Closed",
                            f"Whisper thread closed by {interaction.user.mention}",
                            interaction.user
                        )
                        embed.add_field(name="Thread", value=interaction.channel.mention)
                        await log_channel.send(embed=embed)

                await interaction.followup.send(
                    embed=self.bot.ui_manager.success_embed(
                        "Thread Closed",
                        "The whisper thread has been closed and archived."
                    ),
                    ephemeral=True
                )

            except discord.Forbidden:
                raise commands.CommandError("I don't have permission to close this thread")
            except discord.HTTPException as e:
                raise commands.CommandError(f"Failed to close thread: {str(e)}")

        except commands.CommandError as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_whisper",
        description="Configure whisper system settings"
    )
    @app_commands.describe(
        action="The setting to configure",
        channel="The channel for whispers (required for channel setting)",
        role="The staff role (required for staff setting)",
        minutes="Minutes for auto-close timeout (required for timeout setting)",
        days="Days to keep closed whispers (required for retention setting)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set channel", value="channel"),
        app_commands.Choice(name="Set staff role", value="staff"),
        app_commands.Choice(name="Set timeout", value="timeout"),
        app_commands.Choice(name="Set retention", value="retention"),
        app_commands.Choice(name="Toggle system", value="toggle")
    ])
    @app_commands.default_permissions(administrator=True)
    async def config_whisper(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
        minutes: Optional[int] = None,
        days: Optional[int] = None
    ):
        """Configure whisper system settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')

            if action == "channel":
                if not channel:
                    # Create new channel if none specified
                    channel = await interaction.guild.create_text_channel(
                        name="whispers",
                        topic="Private threads for communicating with staff",
                        reason="Created for whisper system"
                    )

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'channel_id', str(channel.id))
                
                # Configure channel permissions
                await channel.set_permissions(interaction.guild.default_role, view_channel=True, send_messages=False)
                await channel.edit(default_auto_archive_duration=1440)  # 24 hours

                # Set staff role permissions if configured
                staff_role_id = config.get('staff_role')
                if staff_role_id:
                    staff_role = interaction.guild.get_role(int(staff_role_id))
                    if staff_role:
                        await channel.set_permissions(staff_role, view_channel=True, send_messages=True, manage_threads=True)

                embed = self.bot.ui_manager.success_embed(
                    "Whisper Channel Set",
                    f"Successfully configured {channel.mention} as the whisper channel"
                )

                # Send welcome message in the channel
                welcome_embed = self.bot.ui_manager.info_embed(
                    "Whisper Channel",
                    "This channel is for private communication with staff members.\n\n"
                    "To start a conversation:\n"
                    "1. Use `/whisper <message>` anywhere in the server\n"
                    "2. A private thread will be created here\n"
                    "3. Staff members will be notified and can respond in the thread"
                )
                await channel.send(embed=welcome_embed)

            elif action == "staff":
                if not role:
                    raise ValueError("Role is required for staff setting")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'staff_role', str(role.id))

                # Update channel permissions if channel exists
                channel_id = config.get('channel_id')
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.set_permissions(role, view_channel=True, send_messages=True, manage_threads=True)

                embed = self.bot.ui_manager.success_embed(
                    "Staff Role Updated",
                    f"The {role.mention} role will now be notified of new whispers"
                )

            elif action == "timeout":
                if not minutes:
                    raise ValueError("Minutes is required for timeout setting")
                if minutes < 5:
                    raise ValueError("Timeout must be at least 5 minutes")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'timeout', minutes)
                hours = minutes / 60
                embed = self.bot.ui_manager.success_embed(
                    "Timeout Updated",
                    f"Whisper threads will now auto-close after {hours:.1f} hours of inactivity"
                )

            elif action == "retention":
                if not days:
                    raise ValueError("Days is required for retention setting")
                if days < 1:
                    raise ValueError("Retention period must be at least 1 day")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'retention_days', days)
                embed = self.bot.ui_manager.success_embed(
                    "Retention Period Updated",
                    f"Closed whispers will now be kept for {days} days before being automatically deleted"
                )

            else:  # toggle
                enabled = not config.get('enabled', True)
                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'enabled', enabled)
                embed = self.bot.ui_manager.success_embed(
                    "Whisper System Updated",
                    f"The whisper system has been {'enabled' if enabled else 'disabled'}"
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "I need the Manage Channels and Manage Threads permissions to set up the whisper channel."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))