import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Optional

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_threads.start()
        self._cd = commands.CooldownMapping.from_cooldown(1, 300, commands.BucketType.member)  # 5 min cooldown

    def cog_unload(self):
        self.check_threads.cancel()

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
                    thread = self.bot.get_channel(int(whisper['thread_id']))
                    if not thread:
                        continue

                    last_message = await thread.history(limit=1).flatten()
                    if not last_message:
                        continue

                    inactive_time = datetime.utcnow() - last_message[0].created_at
                    if inactive_time > timedelta(minutes=timeout):
                        await thread.send(embed=self.bot.ui_manager.warning_embed(
                            "Thread Closing",
                            f"This thread has been inactive for {timeout} minutes and will be closed."
                        ))
                        await thread.edit(archived=True, locked=True)
                        await self.bot.db_manager.close_whisper(guild.id, str(thread.id))

        except Exception as e:
            print(f"Error in thread checker: {e}")

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

            # Create private thread in the whisper channel
            thread = await channel.create_thread(
                name=f"whisper-{interaction.user.name}",
                type=discord.ChannelType.private_thread,
                reason=f"Whisper thread created by {interaction.user}"
            )

            # Store whisper data
            await self.bot.db_manager.add_whisper(
                interaction.guild_id,
                str(thread.id),
                str(interaction.user.id),
                str(channel.id)
            )

            # Send initial messages
            await thread.send(
                f"{staff_role.mention} New whisper from {interaction.user.mention}",
                embed=self.bot.ui_manager.whisper_embed(
                    "New Whisper Thread",
                    message
                )
            )

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Thread Created",
                    f"I've created a private thread for your message: {thread.mention}"
                ),
                ephemeral=True
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

        except self.bot.WhisperError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
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
            if not isinstance(interaction.channel, discord.Thread):
                raise commands.CommandError("This command can only be used in a whisper thread")

            whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
            whisper = next((w for w in whispers if int(w['thread_id']) == interaction.channel.id), None)

            if not whisper:
                raise commands.CommandError("This is not an active whisper thread")

            if str(interaction.user.id) != whisper['user_id'] and not interaction.user.guild_permissions.manage_threads:
                raise commands.MissingPermissions(["manage_threads"])

            await interaction.channel.send(embed=self.bot.ui_manager.warning_embed(
                "Thread Closing",
                f"Thread manually closed by {interaction.user.mention}"
            ))
            await interaction.channel.edit(archived=True, locked=True)
            await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Thread Closed",
                    "The whisper thread has been closed and archived."
                ),
                ephemeral=True
            )

        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_whisper_toggle",
        description="Enable/disable the whisper system"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_whisper_toggle(self, interaction: discord.Interaction):
        """Toggle the whisper system on/off"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            enabled = not config.get('enabled', True)

            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'enabled', enabled)

            embed = self.bot.ui_manager.success_embed(
                "Whisper System Updated",
                f"The whisper system has been {'enabled' if enabled else 'disabled'}"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_whisper_staff",
        description="Set the staff role for whispers"
    )
    @app_commands.describe(
        role="The role that can view and respond to whispers"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_whisper_staff(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Set staff role for whispers"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'staff_role', str(role.id))

            embed = self.bot.ui_manager.success_embed(
                "Staff Role Updated",
                f"The {role.mention} role will now be notified of new whispers"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_whisper_timeout",
        description="Set the auto-close timeout for whispers"
    )
    @app_commands.describe(
        minutes="Minutes of inactivity before auto-closing threads (minimum: 5)"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_whisper_timeout(
        self,
        interaction: discord.Interaction,
        minutes: int
    ):
        """Set whisper thread auto-close timeout"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if minutes < 5:
                raise ValueError("Timeout must be at least 5 minutes")

            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'timeout', minutes)

            hours = minutes / 60
            embed = self.bot.ui_manager.success_embed(
                "Timeout Updated",
                f"Whisper threads will now auto-close after {hours:.1f} hours of inactivity"
            )
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_whisper_channel",
        description="Create and set up the whisper channel"
    )
    @app_commands.describe(
        channel="The channel to use for whispers (one will be created if not specified)"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_whisper_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Create and configure the whisper channel"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            
            # Create new channel if none specified
            if not channel:
                channel = await interaction.guild.create_text_channel(
                    name="whispers",
                    topic="Private threads for communicating with staff",
                    reason="Created for whisper system"
                )

            # Update whisper config with channel
            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'channel_id', str(channel.id))
            
            # Configure channel permissions
            await channel.set_permissions(interaction.guild.default_role, view_channel=True, send_messages=False)
            
            # Enable threads in channel
            await channel.edit(default_auto_archive_duration=1440) # 24 hours
            
            # Get staff role and set permissions if configured
            staff_role_id = config.get('staff_role')
            if staff_role_id:
                staff_role = interaction.guild.get_role(int(staff_role_id))
                if staff_role:
                    await channel.set_permissions(staff_role, view_channel=True, send_messages=True, manage_threads=True)

            # Send success message
            embed = self.bot.ui_manager.success_embed(
                "Whisper Channel Set",
                f"Successfully configured {channel.mention} as the whisper channel.\n\n"
                f"Users can now use `/whisper` to create private threads in this channel."
            )
            await interaction.response.send_message(embed=embed)

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