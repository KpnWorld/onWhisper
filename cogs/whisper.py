import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
import re
from better_profanity import profanity

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize profanity filter
        profanity.load_censor_words()
        # Start background tasks
        self.check_threads.start()
        self.cleanup_old_whispers.start()
        # Track active whispers
        self.active_whispers = {}

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_threads.cancel()
        self.cleanup_old_whispers.cancel()

    async def filter_content(self, content: str) -> tuple[bool, str]:
        """Filter content for inappropriate language
        Returns: (is_clean, filtered_content)"""
        if profanity.contains_profanity(content):
            return False, content
        return True, content

    async def close_whisper(self, thread_id: str, guild_id: str, user_id: str):
        whisper = await self.bot.db_manager.get_whisper(guild_id, thread_id)
        if not whisper:
            return False, "This is not an active whisper thread"
            
        # Check if user has permission to close
        if str(user_id) != whisper['author_id'] and not await self.bot.is_admin(user_id):
            return False, "You don't have permission to close this whisper"

        # Mark thread as closed in database
        await self.bot.db_manager.update_whisper_status(guild_id, thread_id, 'closed')
        
        # Update thread permissions
        thread = self.bot.get_channel(int(thread_id))
        if thread:
            await thread.edit(archived=True, locked=True)
            
        return True, "Thread closed successfully"

    @tasks.loop(minutes=5.0)
    async def check_threads(self):
        """Periodically check thread states and update database"""
        for guild_id, whispers in self.active_whispers.items():
            for thread_id, whisper in whispers.items():
                thread = self.bot.get_channel(int(thread_id))
                if not thread or thread.archived:
                    # Thread was deleted or archived externally
                    await self.bot.db_manager.update_whisper_status(
                        str(guild_id), 
                        str(thread_id), 
                        'closed'
                    )
                    del self.active_whispers[guild_id][thread_id]

    @check_threads.before_loop
    async def before_check_threads(self):
        """Wait for bot to be ready before starting loop"""
        await self.bot.wait_until_ready()
        # Load active whispers
        for guild in self.bot.guilds:
            whispers = await self.bot.db_manager.get_active_whispers(str(guild.id))
            self.active_whispers[guild.id] = {
                w['thread_id']: w for w in whispers
            }

    @tasks.loop(hours=24.0)
    async def cleanup_old_whispers(self):
        """Clean up whispers older than configured retention period"""
        retention_days = 30  # Default to 30 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        for guild in self.bot.guilds:
            old_whispers = await self.bot.db_manager.get_old_whispers(
                str(guild.id),
                cutoff_date
            )
            
            for whisper in old_whispers:
                thread_id = whisper['thread_id']
                thread = self.bot.get_channel(int(thread_id))
                
                if thread:
                    try:
                        await thread.delete()
                    except:
                        pass  # Thread may already be deleted
                        
                await self.bot.db_manager.delete_whisper(
                    str(guild.id),
                    thread_id
                )

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
            # Defer response immediately
            await interaction.response.defer(ephemeral=True)

            if action == "create":
                if not message:
                    raise ValueError("Message is required when creating a whisper")

                # Check content filter
                allowed, filtered_message = await self.filter_content(message)
                if not allowed:
                    raise commands.CommandError(filtered_message)

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
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.error_embed(
                            "Invalid Channel",
                            "This command can only be used in a whisper thread"
                        ),
                        ephemeral=True
                    )
                    return

                # Get whisper data and validate active status 
                try:
                    whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
                    whisper = next((w for w in whispers if int(w['thread_id']) == interaction.channel.id), None)
                except Exception as e:
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.error_embed(
                            "Database Error",
                            "Failed to retrieve whisper data. Please try again."
                        ),
                        ephemeral=True
                    )
                    return
                
                if not whisper:
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.error_embed(
                            "Invalid Thread",
                            "This is not an active whisper thread"
                        ),
                        ephemeral=True
                    )
                    return

                # Check permissions
                is_admin = interaction.user.guild_permissions.administrator
                is_thread_owner = str(interaction.user.id) == whisper['user_id']
                can_manage = interaction.user.guild_permissions.manage_threads

                if action == "delete" and not is_admin:
                    raise commands.MissingPermissions(["administrator"])
                elif action == "close" and not (is_thread_owner or can_manage):
                    raise commands.MissingPermissions(["manage_threads"])

                if action == "close":
                    # Send initial response quickly
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.info_embed(
                            "Closing Thread",
                            "Processing your request..."
                        ),
                        ephemeral=True
                    )

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

                    try:
                        # Archive and lock the thread first
                        await interaction.channel.edit(archived=True, locked=True)

                        # Mark as closed in DB
                        await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))

                        await interaction.channel.send(
                            embed=self.bot.ui_manager.warning_embed(
                                "Thread Closing",
                                f"Thread manually closed by {interaction.user.mention}"
                            )
                        )

                        # Send staff controls panel
                        embed = self.bot.ui_manager.info_embed(
                            "Support Team Whisper Controls",
                            "Use these controls to manage the closed whisper thread:"
                        )
                        controls_view = self.bot.ui_manager.WhisperControlsView(self.bot)
                        await interaction.channel.send(embed=embed, view=controls_view)

                        # Update the initial response
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.success_embed(
                                "Thread Closed",
                                "The whisper thread has been closed and archived."
                            )
                        )
                    except discord.NotFound:
                        # Thread was already deleted
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.error_embed(
                                "Error",
                                "The thread no longer exists."
                            )
                        )
                    except Exception as e:
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.error_embed(
                                "Error",
                                f"Failed to close thread: {str(e)}"
                            )
                        )

                else:  # delete
                    # Send initial response quickly
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.info_embed(
                            "Deleting Thread",
                            "Processing your request..."
                        ),
                        ephemeral=True
                    )

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
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.info_embed(
                                "Cancelled",
                                "Thread deletion cancelled."
                            )
                        )
                        return

                    try:
                        # Log deletion first since we'll lose access to channel data
                        log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                        if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                            try:
                                log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                                if log_channel:
                                    embed = self.bot.ui_manager.log_embed(
                                        "Whisper Deleted",
                                        f"Whisper thread deleted by {interaction.user.mention}",
                                        interaction.user
                                    )
                                    embed.add_field(name="Thread", value=f"#{interaction.channel.name}")
                                    await log_channel.send(embed=embed)
                            except Exception:
                                # Don't fail if logging fails
                                pass

                        # Delete from database first
                        await self.bot.db_manager.delete_whisper(interaction.guild_id, str(interaction.channel.id))
                        
                        # Then delete the Discord thread
                        await interaction.channel.delete()

                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.success_embed(
                                "Thread Deleted",
                                "The whisper thread has been permanently deleted."
                            )
                        )
                    except discord.NotFound:
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.error_embed(
                                "Error",
                                "The thread no longer exists."
                            )
                        )
                    except Exception as e:
                        await interaction.edit_original_response(
                            embed=self.bot.ui_manager.error_embed(
                                "Error",
                                f"Failed to delete thread: {str(e)}"
                            )
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

    @app_commands.command(
        name="support-controls",
        description="Support team controls for managing whisper threads"
    )
    @app_commands.default_permissions(administrator=True)
    async def support_controls(self, interaction: discord.Interaction):
        """Support team controls for managing whisper threads"""
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    "This command can only be used in a thread"
                ),
                ephemeral=True
            )
            return

        whisper = await self.bot.db_manager.get_whisper(interaction.guild_id, str(interaction.channel.id))
        if not whisper:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    "This is not a whisper thread"
                ),
                ephemeral=True
            )
            return

        # Create support controls UI
        embed = self.bot.ui_manager.info_embed(
            "Support Team Controls",
            "Use these controls to manage the whisper thread"
        )
        controls_view = self.bot.ui_manager.WhisperControlsView(self.bot)
        await interaction.response.send_message(embed=embed, view=controls_view)

    @commands.hybrid_command(
        name="anonymous-whisper",
        description="Start an anonymous thread in the current channel"
    )
    @commands.guild_only()
    async def anonymous_whisper(
        self, 
        ctx: commands.Context, 
        *, 
        message: str
    ):
        """Create an anonymous thread with the given message"""
        # Delete original command message for privacy
        try:
            await ctx.message.delete()
        except:
            pass

        # Check content
        is_clean, content = await self.filter_content(message)
        if not is_clean:
            await ctx.author.send(
                "Your message contains inappropriate content and cannot be posted.",
                ephemeral=True,
                delete_after=10
            )
            return

        # Create thread
        try:
            thread = await ctx.channel.create_thread(
                name=f"Anonymous Whisper",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440  # 24 hours
            )
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to create threads in this channel.",
                ephemeral=True,
                delete_after=10
            )
            return
        except discord.HTTPException as e:
            await ctx.send(
                f"Failed to create thread: {str(e)}",
                ephemeral=True,
                delete_after=10
            )
            return

        # Store whisper in database
        try:
            await self.bot.db_manager.create_whisper(
                guild_id=str(ctx.guild.id),
                channel_id=str(ctx.channel.id),
                thread_id=str(thread.id),
                author_id=str(ctx.author.id),
                content=content,
                created_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            await thread.delete()
            await ctx.send(
                f"Failed to store whisper: {str(e)}",
                ephemeral=True,
                delete_after=10
            )
            return

        # Track active whisper
        if ctx.guild.id not in self.active_whispers:
            self.active_whispers[ctx.guild.id] = {}
        self.active_whispers[ctx.guild.id][thread.id] = {
            'thread_id': str(thread.id),
            'author_id': str(ctx.author.id),
            'created_at': datetime.now(timezone.utc)
        }

        # Send initial message
        try:
            await thread.send(content)
        except:
            await thread.send("*Message content unavailable*")

        # Confirm to user
        await ctx.send(
            "Your anonymous whisper has been created!",
            ephemeral=True,
            delete_after=10
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if not isinstance(message.channel, discord.Thread):
            return
            
        # Check if this is a whisper thread
        whisper = await self.bot.db_manager.get_whisper(message.guild.id, str(message.channel.id))
        if not whisper:
            return

        # Check for inappropriate content in thread messages
        if profanity.contains_profanity(message.content):
            await message.delete()
            await message.channel.send(
                embed=self.bot.ui_manager.error_embed(
                    "Content Warning",
                    f"{message.author.mention} Your message was removed due to inappropriate language. Please keep conversations respectful."
                )
            )

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))