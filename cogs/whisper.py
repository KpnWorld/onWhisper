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
        description="Manage whisper threads"
    )
    @app_commands.describe(
        action="The action to perform",
        message="Your message to staff (required for create)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create new whisper", value="create"),
        app_commands.Choice(name="Close current whisper", value="close"),
        app_commands.Choice(name="Delete whisper (Admin only)", value="delete")
    ])
    async def whisper(
        self,
        interaction: discord.Interaction,
        action: str,
        message: Optional[str] = None
    ):
        """Unified whisper management command"""
        try:
            await interaction.response.defer(ephemeral=True)

            if action == "create":
                if not message:
                    raise ValueError("Message is required when creating a whisper")

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

                # Get next whisper ID
                next_id = await self.bot.db_manager.get_next_whisper_id(interaction.guild_id)
                
                # Format thread name with padded ID
                thread_name = f"whisper-{str(next_id).zfill(4)}"

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
                            name=thread_name,
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

                # Create close button view
                close_view = self.bot.ui_manager.WhisperCloseView(self.bot)

                # Send initial message in thread with the close button
                await thread.send(
                    f"{staff_role.mention} New whisper from {interaction.user.mention}",
                    embed=self.bot.ui_manager.whisper_embed(
                        "New Whisper Thread",
                        message
                    ),
                    view=close_view
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

            elif action in ["close", "delete"]:
                # Check if in a thread
                if not isinstance(interaction.channel, discord.Thread):
                    raise commands.CommandError("This command can only be used in a whisper thread")

                # Get whisper data
                whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
                whisper = next((w for w in whispers if int(w['thread_id']) == interaction.channel.id), None)

                if not whisper:
                    raise commands.CommandError("This is not an active whisper thread")

                # Check permissions
                is_admin = interaction.user.guild_permissions.administrator
                is_thread_owner = str(interaction.user.id) == whisper['user_id']
                can_manage = interaction.user.guild_permissions.manage_threads

                if action == "delete" and not is_admin:
                    raise commands.MissingPermissions(["administrator"])
                elif action == "close" and not (is_thread_owner or can_manage):
                    raise commands.MissingPermissions(["manage_threads"])

                if action == "close":
                    # Show confirmation dialog
                    confirmed = await self.bot.ui_manager.confirm_action(
                        interaction,
                        "Close Whisper",
                        "Are you sure you want to close this whisper thread?",
                        confirm_label="Close",
                        cancel_label="Cancel",
                        ephemeral=True
                    )

                    if not confirmed:
                        return

                    await interaction.channel.send(
                        embed=self.bot.ui_manager.warning_embed(
                            "Thread Closing",
                            f"Thread manually closed by {interaction.user.mention}"
                        )
                    )

                    # Archive and lock the thread
                    await interaction.channel.edit(archived=True, locked=True)

                    # Mark as closed in DB
                    await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))

                    # Send staff controls panel
                    embed = self.bot.ui_manager.info_embed(
                        "Support Team Whisper Controls",
                        "Use these controls to manage the closed whisper thread:"
                    )
                    controls_view = self.bot.ui_manager.WhisperControlsView(self.bot)
                    await interaction.channel.send(embed=embed, view=controls_view)

                    await interaction.followup.send(
                        embed=self.bot.ui_manager.success_embed(
                            "Thread Closed",
                            "The whisper thread has been closed and archived."
                        ),
                        ephemeral=True
                    )

                else:  # delete
                    # Show confirmation dialog
                    confirmed = await self.bot.ui_manager.confirm_action(
                        interaction,
                        "Delete Whisper",
                        "⚠️ Are you sure you want to permanently delete this whisper thread? This action cannot be undone.",
                        confirm_label="Delete",
                        cancel_label="Cancel",
                        ephemeral=True
                    )

                    if not confirmed:
                        return

                    # Log deletion first since we'll lose access to channel data
                    log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                    if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                        log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                        if log_channel:
                            embed = self.bot.ui_manager.log_embed(
                                "Whisper Deleted",
                                f"Whisper thread deleted by {interaction.user.mention}",
                                interaction.user
                            )
                            embed.add_field(name="Thread", value=f"#{interaction.channel.name}")
                            await log_channel.send(embed=embed)

                    # Delete from database and Discord
                    await self.bot.db_manager.delete_whisper(interaction.guild_id, str(interaction.channel.id))
                    await interaction.channel.delete()

                    await interaction.followup.send(
                        embed=self.bot.ui_manager.success_embed(
                            "Thread Deleted",
                            "The whisper thread has been permanently deleted."
                        ),
                        ephemeral=True
                    )

        except self.bot.WhisperError as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except commands.MissingPermissions as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))