import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_threads.start()
        self._cd = commands.CooldownMapping.from_cooldown(1, 300, commands.BucketType.member)  # 5 min cooldown

    def cog_unload(self):
        self.check_threads.cancel()

    @tasks.loop(minutes=5.0)
    async def check_threads(self):
        """Check and close inactive whisper threads"""
        try:
            for guild in self.bot.guilds:
                whispers = await self.bot.db_manager.get_active_whispers(guild.id)
                for whisper in whispers:
                    thread_id = int(whisper['thread_id'])
                    thread = self.bot.get_channel(thread_id)
                    
                    if not thread:
                        continue

                    # Get config for auto-close
                    config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                    auto_close_minutes = config.get('auto_close_minutes', 1440)  # Default 24h
                    
                    last_message = None
                    async for message in thread.history(limit=1):
                        last_message = message
                    
                    if last_message:
                        inactive_time = datetime.utcnow() - last_message.created_at
                        if inactive_time > timedelta(minutes=auto_close_minutes):
                            await thread.send(embed=self.bot.ui_manager.warning_embed(
                                "Thread Auto-Closing",
                                f"This thread has been inactive for {auto_close_minutes//60} hours and will be archived."
                            ))
                            await thread.edit(archived=True, locked=True)
                            await self.bot.db_manager.close_whisper(guild.id, str(thread_id))
        except Exception as e:
            print(f"Error in check_threads: {e}")

    @app_commands.command(
        name="whisper",
        description="Start a private thread to talk with staff"
    )
    @app_commands.describe(
        message="Your initial message to staff"
    )
    async def whisper(self, interaction: discord.Interaction, message: str):
        """Create a private thread for user-staff communication"""
        try:
            # Check cooldown
            retry_after = self._cd.get_bucket(interaction).update_rate_limit()
            if retry_after:
                raise commands.CommandOnCooldown(self._cd, retry_after, commands.BucketType.member)

            # Get whisper config
            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            
            if not config.get('enabled', True):
                raise self.bot.WhisperNotEnabled("The whisper system is disabled in this server")
                
            staff_role_id = config.get('staff_role')
            if not staff_role_id:
                raise self.bot.WhisperNotConfigured("No staff role has been configured for whispers")

            # Create thread name with timestamp for uniqueness
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
            thread_name = f"whisper-{interaction.user.name}-{timestamp}"

            # Create the initial embed
            embed = self.bot.ui_manager.whisper_embed(
                "New Whisper Thread",
                f"**From:** {interaction.user.mention}\n**Message:** {message}"
            )

            # Create thread
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                invitable=False
            )

            # Add initial members
            await thread.add_user(interaction.user)
            
            # Send initial message
            await thread.send(
                content=f"<@&{staff_role_id}>",
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )

            # Store in database
            await self.bot.db_manager.create_whisper_thread(
                interaction.guild_id,
                interaction.user.id,
                thread.id,
                message
            )

            # Respond to interaction
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Created",
                    f"Your thread has been created: {thread.mention}\nA staff member will be with you shortly."
                ),
                ephemeral=True
            )

        except self.bot.WhisperError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Permission Error",
                    "I don't have permission to create private threads. Please contact a server administrator."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    f"An unexpected error occurred: {str(e)}"
                ),
                ephemeral=True
            )

    @app_commands.command(
        name="whisper_config",
        description="Configure the whisper system"
    )
    @app_commands.describe(
        staff_role="The role that can view and respond to whispers",
        auto_close="Minutes of inactivity before auto-closing threads (default: 1440)",
        enabled="Enable or disable the whisper system"
    )
    @app_commands.default_permissions(administrator=True)
    async def whisper_config(
        self,
        interaction: discord.Interaction,
        staff_role: discord.Role = None,
        auto_close: int = None,
        enabled: bool = None
    ):
        """Configure whisper system settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            updated = False

            if staff_role is not None:
                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'staff_role', str(staff_role.id))
                updated = True

            if auto_close is not None:
                if auto_close < 5:
                    raise ValueError("Auto-close time must be at least 5 minutes")
                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'auto_close_minutes', auto_close)
                updated = True

            if enabled is not None:
                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'enabled', enabled)
                updated = True

            if not updated:
                # Show current config
                embed = self.bot.ui_manager.info_embed(
                    "Whisper System Configuration",
                    "Current settings:"
                )
                embed.add_field(
                    name="Staff Role",
                    value=f"<@&{config.get('staff_role', 'Not set')}>" if config.get('staff_role') else "Not set",
                    inline=True
                )
                embed.add_field(
                    name="Auto-close",
                    value=f"{config.get('auto_close_minutes', 1440)} minutes",
                    inline=True
                )
                embed.add_field(
                    name="System Enabled",
                    value="Yes" if config.get('enabled', True) else "No",
                    inline=True
                )
            else:
                embed = self.bot.ui_manager.success_embed(
                    "Configuration Updated",
                    "The whisper system settings have been updated."
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

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))