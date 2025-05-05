import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from better_profanity import profanity

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_threads.start()
        self.cleanup_old_threads.start()

    def cog_unload(self):
        self.check_threads.cancel()
        self.cleanup_old_threads.cancel()

    async def filter_content(self, content: str) -> tuple[bool, str]:
        """Filter message content for profanity and return (is_clean, filtered_content)"""
        filtered = profanity.censor(content)
        return (filtered == content, filtered)

    async def close_whisper(self, thread_id: str, guild_id: str, user_id: str):
        """Close a whisper thread"""
        try:
            # Mark thread as closed in database
            whispers = await self.bot.db_manager.get_section(guild_id, 'whispers')
            if not isinstance(whispers, dict):
                whispers = {
                    'active_threads': [],
                    'closed_threads': [],
                    'saved_threads': {}
                }
            
            # Find and update thread
            thread = next((t for t in whispers['active_threads'] 
                         if str(t['thread_id']) == thread_id), None)
            
            if thread:
                thread['closed_at'] = datetime.now(timezone.utc).isoformat()
                whispers['active_threads'].remove(thread)
                whispers['closed_threads'].append(thread)
                await self.bot.db_manager.update_guild_data(guild_id, 'whispers', whispers)
                
        except Exception as e:
            print(f"Error closing whisper: {e}")

    @tasks.loop(minutes=5.0)
    async def check_threads(self):
        """Check for inactive threads to auto-close"""
        for guild in self.bot.guilds:
            try:
                # Get whisper config and threads
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                whispers = await self.bot.db_manager.get_section(guild.id, 'whispers')
                
                if not config.get('enabled', True) or not whispers:
                    continue

                auto_close = config.get('auto_close_minutes', 1440)  # Default 24h
                
                # Check each active thread
                for thread_data in whispers.get('active_threads', []):
                    thread_id = thread_data.get('thread_id')
                    if not thread_id:
                        continue
                        
                    thread = guild.get_thread(int(thread_id))
                    if not thread:
                        continue

                    last_message = None
                    async for msg in thread.history(limit=1):
                        last_message = msg

                    if last_message:
                        inactive_time = datetime.now(timezone.utc) - last_message.created_at
                        if inactive_time > timedelta(minutes=auto_close):
                            await thread.edit(archived=True, locked=True)
                            await self.close_whisper(str(thread_id), str(guild.id), str(thread_data.get('user_id')))
                            
                            # Log if enabled
                            log_config = await self.bot.db_manager.get_logging_config(guild.id)
                            if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                                log_channel = guild.get_channel(int(log_config['log_channel']))
                                if log_channel:
                                    embed = self.bot.ui_manager.log_embed(
                                        "Whisper Auto-Closed",
                                        f"Thread automatically closed due to {auto_close} minutes of inactivity",
                                        self.bot.user
                                    )
                                    embed.add_field(name="Thread", value=f"#{thread.name}")
                                    await log_channel.send(embed=embed)

            except Exception as e:
                print(f"Error checking threads in guild {guild.id}: {e}")

    @check_threads.before_loop
    async def before_check_threads(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24.0)
    async def cleanup_old_threads(self):
        """Clean up old closed whisper threads"""
        for guild in self.bot.guilds:
            try:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                retention_days = config.get('retention_days', 30)
                
                cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
                whispers = await self.bot.db_manager.get_section(guild.id, 'whispers')
                
                if not isinstance(whispers, dict):
                    continue
                    
                # Filter out old threads
                whispers['closed_threads'] = [
                    thread for thread in whispers.get('closed_threads', [])
                    if (not thread.get('closed_at') or 
                        datetime.fromisoformat(thread['closed_at']) > cutoff)
                ]
                
                await self.bot.db_manager.update_guild_data(guild.id, 'whispers', whispers)
                
            except Exception as e:
                print(f"Error cleaning up threads in guild {guild.id}: {e}")

    # Main whisper command group
    whisper = app_commands.Group(
        name="whisper",
        description="Manage private whisper threads"
    )

    @whisper.command(
        name="create",
        description="Create a new whisper thread"
    )
    @app_commands.describe(
        message="Your message to staff"
    )
    async def whisper_create(
        self,
        interaction: discord.Interaction,
        message: str
    ):
        """Create a new whisper thread"""
        try:
            # Get whisper config
            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            if not config.get('enabled', True):
                raise commands.CommandError("The whisper system is currently disabled")

            # Get whisper channel
            channel_id = config.get('channel_id')
            if not channel_id:
                raise commands.CommandError("Whisper system is not configured. Please ask an admin to set it up.")

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise commands.CommandError("Could not find whisper channel. Please contact staff.")

            # Filter content
            is_clean, filtered_message = await self.filter_content(message)
            if not is_clean and not config.get('anonymous_allowed', False):
                raise commands.CommandError("Your message contains inappropriate content.")

            # Create thread
            thread = await channel.create_thread(
                name=f"Whisper - {interaction.user.name}",
                type=discord.ChannelType.private_thread,
                reason="Whisper thread creation"
            )

            # Send initial message
            embed = self.bot.ui_manager.info_embed(
                "New Whisper",
                filtered_message
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            controls = self.bot.ui_manager.WhisperControlsView(self.bot)
            await thread.send(embed=embed, view=controls)

            # Add to database
            await self.bot.db_manager.add_whisper(
                interaction.guild_id,
                str(thread.id),
                str(interaction.user.id),
                str(channel.id)
            )

            # Add staff role if configured
            staff_role_id = config.get('staff_role_id')
            if staff_role_id:
                staff_role = interaction.guild.get_role(int(staff_role_id))
                if staff_role:
                    staff_ping = await thread.send(f"{staff_role.mention}")
                    await staff_ping.delete()

            # Send confirmation
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Created",
                    f"Your whisper thread has been created: {thread.mention}\nStaff will respond as soon as possible."
                ),
                ephemeral=True
            )

            # Log if enabled
            log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
            if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                if log_channel:
                    log_embed = self.bot.ui_manager.log_embed(
                        "Whisper Created",
                        f"New whisper thread created by {interaction.user.mention}",
                        interaction.user
                    )
                    log_embed.add_field(name="Thread", value=thread.mention)
                    await log_channel.send(embed=log_embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Permission Error",
                    "I don't have permission to create private threads."
                ),
                ephemeral=True
            )
        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )

    @whisper.command(
        name="close",
        description="Close your current whisper thread"
    )
    async def whisper_close(
        self,
        interaction: discord.Interaction
    ):
        """Close the current whisper thread"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in whisper threads")

            # Get thread data
            whispers = await self.bot.db_manager.get_section(interaction.guild_id, 'whispers')
            if not whispers:
                raise commands.CommandError("No whisper data found")

            thread = next(
                (t for t in whispers.get('active_threads', [])
                 if str(t['thread_id']) == str(interaction.channel.id)),
                None
            )

            if not thread:
                raise commands.CommandError("This is not an active whisper thread")

            # Check permissions
            if (str(thread['user_id']) != str(interaction.user.id) and 
                not interaction.user.guild_permissions.manage_threads):
                raise commands.MissingPermissions(["manage_threads"])

            # Close thread
            await interaction.channel.edit(archived=True, locked=True)
            await self.close_whisper(
                str(interaction.channel.id),
                str(interaction.guild_id),
                str(thread['user_id'])
            )

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Thread Closed",
                    "This whisper thread has been closed"
                )
            )

            # Log if enabled
            log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
            if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                if log_channel:
                    embed = self.bot.ui_manager.log_embed(
                        "Whisper Closed",
                        f"Whisper thread closed by {interaction.user.mention}",
                        interaction.user
                    )
                    embed.add_field(name="Thread", value=f"#{interaction.channel.name}")
                    await log_channel.send(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You can only close your own whispers or with Manage Threads permission"
                ),
                ephemeral=True
            )
        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @whisper.command(
        name="delete",
        description="Delete a whisper thread permanently (Admin only)"
    )
    @app_commands.default_permissions(manage_threads=True)
    async def whisper_delete(
        self,
        interaction: discord.Interaction
    ):
        """Delete a whisper thread permanently"""
        try:
            if not interaction.user.guild_permissions.manage_threads:
                raise commands.MissingPermissions(["manage_threads"])

            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in whisper threads")

            # Get thread data
            whispers = await self.bot.db_manager.get_section(interaction.guild_id, 'whispers')
            if not whispers:
                raise commands.CommandError("No whisper data found")

            # Find thread in any status
            thread = (
                next((t for t in whispers.get('active_threads', [])
                      if str(t['thread_id']) == str(interaction.channel.id)), None) or
                next((t for t in whispers.get('closed_threads', [])
                      if str(t['thread_id']) == str(interaction.channel.id)), None)
            )

            if not thread:
                raise commands.CommandError("This is not a whisper thread")

            # Remove from database
            if thread in whispers.get('active_threads', []):
                whispers['active_threads'].remove(thread)
            if thread in whispers.get('closed_threads', []):
                whispers['closed_threads'].remove(thread)

            await self.bot.db_manager.update_guild_data(interaction.guild_id, 'whispers', whispers)

            # Delete saved history if any
            if str(interaction.channel.id) in whispers.get('saved_threads', {}):
                del whispers['saved_threads'][str(interaction.channel.id)]
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'whispers', whispers)

            # Log deletion
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

            # Delete the thread
            await interaction.channel.delete()

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Threads permission to delete whispers"
                ),
                ephemeral=True
            )
        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        """Handle thread state changes"""
        if before.archived != after.archived and after.archived:
            try:
                # Get whisper data
                whispers = await self.bot.db_manager.get_section(after.guild.id, 'whispers')
                if not whispers:
                    return

                thread = next(
                    (t for t in whispers.get('active_threads', [])
                     if str(t['thread_id']) == str(after.id)),
                    None
                )

                if thread:
                    await self.close_whisper(str(after.id), str(after.guild.id), str(thread['user_id']))
            except Exception as e:
                print(f"Error handling thread update: {e}")

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))