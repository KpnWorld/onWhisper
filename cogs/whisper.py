import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
from typing import Optional

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_close_check.start()

    def cog_unload(self):
        self.auto_close_check.cancel()

    async def is_staff(self, member: discord.Member) -> bool:
        """Check if member is whisper staff"""
        config = await self.bot.db_manager.get_section(member.guild.id, 'whisper_config')
        staff_role_id = config.get('staff_role')
        if not staff_role_id:
            return member.guild_permissions.administrator
        return str(staff_role_id) in [str(role.id) for role in member.roles] or member.guild_permissions.administrator

    @app_commands.command(name="whisper")
    @app_commands.describe(
        action="The action to perform",
        message="The message for your whisper (for create only)",
        anonymous="Send whisper anonymously (for create only)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create new whisper", value="create"),
        app_commands.Choice(name="Close current whisper", value="close")
    ])
    async def whisper_command(
        self,
        interaction: discord.Interaction,
        action: str,
        message: Optional[str] = None,
        anonymous: Optional[bool] = False
    ):
        """Create or manage whisper threads"""
        try:
            # Check if system is enabled
            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
            if not config['enabled']:
                raise commands.DisabledCommand("The whisper system is currently disabled")

            # Handle different actions
            if action == "create":
                if not message:
                    raise ValueError("You must provide a message for your whisper")
                await self._create_whisper(interaction, message, anonymous and config['anonymous_allowed'])
            elif action == "close":
                await self._close_whisper(interaction)

        except commands.DisabledCommand as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("System Disabled", str(e)),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    async def _create_whisper(self, interaction: discord.Interaction, message: str, anonymous: bool):
        """Create a new whisper thread"""
        try:
            # Get whisper channel with safe operation
            config = await self.bot.db_manager.safe_operation(
                'get_whisper_config',
                self.bot.db_manager.get_section,
                interaction.guild_id,
                'whisper_config'
            )
            if not config:
                raise ValueError("Whisper system is not configured")

            channel_id = config.get('channel_id')
            if not channel_id:
                raise ValueError("No whisper channel has been configured")

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise ValueError("Could not find the whisper channel")

            # Use transaction for atomic thread creation and logging
            async with await self.bot.db_manager.transaction(interaction.guild_id, 'whisper') as txn:
                # Create thread
                whisper_id = await self.bot.db_manager.get_next_whisper_id(interaction.guild_id)
                thread = await channel.create_thread(
                    name=f"whisper-{whisper_id}",
                    type=discord.ChannelType.private_thread,
                    reason=f"Whisper thread created by {interaction.user}"
                )

                # Send initial message
                embed = discord.Embed(
                    title="New Whisper",
                    description=message,
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                
                if not anonymous:
                    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                else:
                    embed.set_author(name="Anonymous User")

                staff_ping = f"<@&{config['staff_role']}>" if config.get('staff_role') else "@Staff"
                await thread.send(f"{staff_ping} New whisper received:", embed=embed)

                # Add user to thread
                await thread.add_user(interaction.user)

                # Log whisper creation in transaction
                log_data = {
                    "thread_id": str(thread.id),
                    "user_id": str(interaction.user.id),
                    "anonymous": anonymous
                }
                await self.bot.db_manager.log_whisper(interaction.guild_id, "create", log_data)

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Whisper Created",
                    f"Your whisper thread has been created: {thread.mention}"
                ),
                ephemeral=True
            )

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Configuration Error", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    async def _close_whisper(self, interaction: discord.Interaction):
        """Close a whisper thread"""
        if not isinstance(interaction.channel, discord.Thread):
            raise ValueError("This command can only be used in whisper threads")

        if not interaction.channel.name.startswith("whisper-"):
            raise ValueError("This is not a whisper thread")

        # Check permissions
        if not await self.is_staff(interaction.user):
            raise commands.MissingPermissions(["Whisper staff role required"])

        # Archive and lock the thread
        await interaction.channel.edit(archived=True, locked=True)

        # Log whisper closure
        await self.bot.db_manager.log_whisper(
            interaction.guild_id,
            "close",
            {
                "thread_id": str(interaction.channel.id),
                "closed_by": str(interaction.user.id)
            }
        )

        await interaction.response.send_message(
            embed=self.bot.ui_manager.success_embed(
                "Whisper Closed",
                "This whisper thread has been closed and archived"
            )
        )

    @tasks.loop(minutes=5.0)
    async def auto_close_check(self):
        """Check for inactive whisper threads"""
        for guild in self.bot.guilds:
            try:
                config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                if not config['enabled'] or not config.get('channel_id'):
                    continue

                channel = guild.get_channel(int(config['channel_id']))
                if not channel:
                    continue

                for thread in channel.threads:
                    if not thread.name.startswith("whisper-") or thread.archived:
                        continue

                    # Check last message time
                    last_message = None
                    async for msg in thread.history(limit=1):
                        last_message = msg

                    if last_message:
                        inactive_time = (discord.utils.utcnow() - last_message.created_at).total_seconds() / 60
                        if inactive_time >= config['auto_close_minutes']:
                            await thread.edit(archived=True, locked=True)
                            
                            # Send closure notification
                            embed = self.bot.ui_manager.info_embed(
                                "Thread Auto-Closed",
                                f"This whisper has been automatically closed after {config['auto_close_minutes']} minutes of inactivity"
                            )
                            try:
                                await thread.send(embed=embed)
                            except:
                                pass

                            # Log auto-closure
                            await self.bot.db_manager.log_whisper(
                                guild.id,
                                "auto_close",
                                {
                                    "thread_id": str(thread.id),
                                    "inactive_minutes": config['auto_close_minutes']
                                }
                            )

            except Exception as e:
                print(f"Error in auto-close check for guild {guild.id}: {e}")

    @auto_close_check.before_loop
    async def before_auto_close(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))