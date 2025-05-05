import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from better_profanity import profanity
from typing import Literal

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

    @app_commands.command(name="whisper")
    @app_commands.describe(
        action="The action to perform",
        message="The message to send (only required for 'create')"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create new whisper", value="create"),
        app_commands.Choice(name="Close current whisper", value="close"),
        app_commands.Choice(name="Delete whisper thread", value="delete")
    ])
    async def whisper(
        self,
        interaction: discord.Interaction,
        action: str,
        message: str = None
    ):
        """Manage whisper threads for private communication with staff"""
        if action == "create":
            if not message:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Message",
                        "You must provide a message when creating a whisper"
                    ),
                    ephemeral=True
                )
                return
            await self._handle_create(interaction, message)
        elif action == "close":
            await self._handle_close(interaction)
        elif action == "delete":
            await self._handle_delete(interaction)

    async def _handle_create(self, interaction: discord.Interaction, message: str):
        """Handle whisper creation"""
        try:
            # Get whisper config
            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            if not config.get('enabled', True):
                raise commands.CommandError("The whisper system is currently disabled")

            # Get whisper channel
            channel_id = config.get('channel_id')
            if not channel_id:
                raise commands.CommandError("No whisper channel has been configured")
            
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise commands.CommandError("Could not find the whisper channel")

            # Get staff role
            staff_role_id = config.get('staff_role_id')
            if not staff_role_id:
                raise commands.CommandError("No staff role has been configured")

            staff_role = interaction.guild.get_role(int(staff_role_id))
            if not staff_role:
                raise commands.CommandError("Could not find the staff role")

            # Check content
            is_clean, filtered_content = await self.filter_content(message)
            if not is_clean:
                raise commands.CommandError("Your message contains inappropriate content")

            # Create thread name and get next ID
            thread_id = await self.bot.db_manager.get_next_whisper_id(interaction.guild_id)
            thread_name = f"whisper-{thread_id}"

            # Create thread
            thread = await channel.create_thread(
                name=thread_name,
                auto_archive_duration=1440,  # 24 hours
                reason=f"Whisper thread created by {interaction.user}"
            )

            # Send initial message
            embed = self.bot.ui_manager.whisper_embed(
                "New Whisper",
                filtered_content
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            
            starter_msg = await thread.send(
                content=f"{staff_role.mention} New whisper from {interaction.user.mention}",
                embed=embed
            )
            await starter_msg.pin()

            # Add to database
            await self.bot.db_manager.add_whisper(
                interaction.guild_id,
                str(thread.id),
                str(interaction.user.id),
                str(channel.id)
            )

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Created",
                    f"Your whisper thread has been created in {thread.mention}"
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
                    "An error occurred while creating your whisper"
                ),
                ephemeral=True
            )

    async def _handle_close(self, interaction: discord.Interaction):
        """Handle whisper closing"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in whisper threads")

            # Get whisper data
            whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
            whisper = next((w for w in whispers if w['thread_id'] == str(interaction.channel.id)), None)

            if not whisper:
                raise commands.CommandError("This is not an active whisper thread")

            # Check if user can close thread
            if str(interaction.user.id) != whisper['user_id'] and not interaction.user.guild_permissions.manage_threads:
                raise commands.MissingPermissions(["manage_threads"])

            # Close the thread
            await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))
            await interaction.channel.edit(archived=True, locked=True)

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Closed",
                    "This whisper thread has been closed"
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You can only close your own whisper threads"
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
                    "An error occurred while closing the whisper"
                ),
                ephemeral=True
            )

    async def _handle_delete(self, interaction: discord.Interaction):
        """Handle whisper deletion"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in whisper threads")

            if not interaction.user.guild_permissions.manage_threads:
                raise commands.MissingPermissions(["manage_threads"])

            # Get whisper data
            whispers = await self.bot.db_manager.get_all_whispers(interaction.guild_id)
            whisper = next((w for w in whispers if w['thread_id'] == str(interaction.channel.id)), None)

            if not whisper:
                raise commands.CommandError("This is not a whisper thread")

            # Delete from database
            await self.bot.db_manager.delete_whisper(interaction.guild_id, str(interaction.channel.id))

            # Delete the thread
            await interaction.channel.delete()

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Deleted",
                    "The whisper thread has been permanently deleted"
                ),
                ephemeral=True
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Manage Threads permission to delete whispers"
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
                    "An error occurred while deleting the whisper"
                ),
                ephemeral=True
            )

    # Background tasks
    @tasks.loop(minutes=5)
    async def check_threads(self):
        """Check for inactive whisper threads and auto-close them"""
        try:
            for guild in self.bot.guilds:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                if not config or not config.get('enabled', True):
                    continue

                timeout = config.get('auto_close_minutes', 60)
                whispers = await self.bot.db_manager.get_active_whispers(guild.id)

                for whisper in whispers:
                    thread = guild.get_thread(int(whisper['thread_id']))
                    if not thread:
                        continue

                    messages = [msg async for msg in thread.history(limit=1)]
                    if not messages:
                        continue

                    last_message = messages[0]
                    if (datetime.now(timezone.utc) - last_message.created_at).total_seconds() > timeout * 60:
                        await self.bot.db_manager.close_whisper(guild.id, whisper['thread_id'])
                        await thread.edit(archived=True, locked=True)
                        
                        try:
                            await thread.send(
                                embed=self.bot.ui_manager.info_embed(
                                    "Thread Auto-Closed",
                                    f"This thread has been automatically closed due to {timeout} minutes of inactivity"
                                )
                            )
                        except:
                            pass

        except Exception as e:
            print(f"Error in check_threads task: {e}")

    @check_threads.before_loop
    async def before_check_threads(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def cleanup_old_threads(self):
        """Clean up old closed whisper threads"""
        try:
            for guild in self.bot.guilds:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                if not config:
                    continue

                retention_days = config.get('retention_days', 30)
                await self.bot.db_manager.cleanup_old_whispers(guild.id, retention_days)

        except Exception as e:
            print(f"Error in cleanup_old_threads task: {e}")

    @cleanup_old_threads.before_loop
    async def before_cleanup_old_threads(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))