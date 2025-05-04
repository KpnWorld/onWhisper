import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

class ConfigurationCog(commands.Cog):
    """Configuration commands for server settings"""
    
    def __init__(self, bot):
        self.bot = bot
        
    config = app_commands.Group(
        name="config",
        description="Configure server settings",
        default_permissions=discord.Permissions(administrator=True)
    )

    @config.command(
        name="logs",
        description="Configure logging settings"
    )
    @app_commands.describe(
        action="Whether to enable or disable logging",
        channel="Channel to use for logging (required when enabling)",
        type="Type of logs to configure"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable")
        ],
        type=[
            app_commands.Choice(name="All logs", value="all"),
            app_commands.Choice(name="Moderation logs", value="mod"),
            app_commands.Choice(name="Member logs", value="member"),
            app_commands.Choice(name="Message logs", value="message"),
            app_commands.Choice(name="Server logs", value="server")
        ]
    )
    async def config_logs(
        self,
        interaction: discord.Interaction,
        action: str,
        type: str,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure logging settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action == "enable" and not channel:
                raise ValueError("Channel is required when enabling logging")

            updates = {}
            if action == "enable":
                if type == "all":
                    updates = {
                        "log_channel": str(channel.id),
                        "logging_enabled": True
                    }
                elif type == "mod":
                    updates = {"mod_channel": str(channel.id)}
                elif type == "member":
                    updates = {"join_channel": str(channel.id)}
                elif type == "message":
                    updates = {"message_channel": str(channel.id)}
                elif type == "server":
                    updates = {"server_channel": str(channel.id)}

                await self.bot.db_manager.update_logging_config(interaction.guild_id, updates)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Logging Configured",
                        f"{type.title()} logs will now be sent to {channel.mention}"
                    )
                )
            else:
                if type == "all":
                    updates = {
                        "log_channel": None,
                        "logging_enabled": False
                    }
                elif type == "mod":
                    updates = {"mod_channel": None}
                elif type == "member":
                    updates = {"join_channel": None}
                elif type == "message":
                    updates = {"message_channel": None}
                elif type == "server":
                    updates = {"server_channel": None}

                await self.bot.db_manager.update_logging_config(interaction.guild_id, updates)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Logging Disabled",
                        f"{type.title()} logging has been disabled"
                    )
                )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure logging"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Configuration",
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

    @config.command(
        name="whisper",
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
                staff_role_id = config.get('staff_role_id')
                if staff_role_id:
                    staff_role = interaction.guild.get_role(int(staff_role_id))
                    if staff_role:
                        await channel.set_permissions(staff_role, view_channel=True, send_messages=True, manage_threads=True)

                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Whisper Channel Set",
                        f"Whisper threads will be created in {channel.mention}"
                    )
                )

            elif action == "staff":
                if not role:
                    raise ValueError("Role is required for staff configuration")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'staff_role_id', str(role.id))

                # Update channel permissions if channel exists
                channel_id = config.get('channel_id')
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.set_permissions(role, view_channel=True, send_messages=True, manage_threads=True)

                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Staff Role Set",
                        f"{role.mention} has been set as the staff role for whispers"
                    )
                )

            elif action == "timeout":
                if not minutes:
                    raise ValueError("Minutes value is required for timeout configuration")
                if minutes < 0:
                    raise ValueError("Timeout minutes cannot be negative")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'auto_close_minutes', minutes)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Auto-Close Timeout Set",
                        f"Inactive whisper threads will be closed after {minutes} minutes"
                    )
                )

            elif action == "retention":
                if not days:
                    raise ValueError("Days value is required for retention configuration")
                if days < 0:
                    raise ValueError("Retention days cannot be negative")

                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'retention_days', days)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Thread Retention Set",
                        f"Closed whisper threads will be kept for {days} days"
                    )
                )

            elif action == "toggle":
                enabled = not config.get('enabled', True)
                await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'enabled', enabled)
                
                status = "enabled" if enabled else "disabled"
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Whisper System Toggled",
                        f"Whisper system has been {status}"
                    )
                )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure whispers"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Configuration",
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

    @config.command(
        name="xp",
        description="Configure XP system settings"
    )
    @app_commands.describe(
        action="The setting to configure",
        value="The value to set (required for rate and cooldown)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set XP rate (1-100)", value="rate"),
        app_commands.Choice(name="Set cooldown (seconds)", value="cooldown"),
        app_commands.Choice(name="Toggle system", value="toggle")
    ])
    async def config_xp(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[int] = None
    ):
        """Configure XP system settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action in ["rate", "cooldown"] and value is None:
                raise ValueError(f"Value is required for {action} configuration")

            if action == "rate":
                if value < 1 or value > 100:
                    raise ValueError("XP rate must be between 1 and 100")
                
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'rate', value)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "XP Rate Updated",
                        f"Users will now gain {value} XP per message"
                    )
                )

            elif action == "cooldown":
                if value < 0:
                    raise ValueError("Cooldown cannot be negative")
                
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'cooldown', value)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "XP Cooldown Updated",
                        f"Users must wait {value} seconds between XP gains"
                    )
                )

            elif action == "toggle":
                config = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
                enabled = not config.get('enabled', True)
                
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'enabled', enabled)
                status = "enabled" if enabled else "disabled"
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "XP System Toggled",
                        f"XP system has been {status}"
                    )
                )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure XP settings"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Configuration",
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

    @config.command(
        name="level",
        description="Configure level-up role rewards"
    )
    @app_commands.describe(
        action="Whether to add, remove, or list level rewards",
        level="The level to configure (not needed for list)",
        role="The role to give as a reward (only needed for adding)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add reward", value="add"),
        app_commands.Choice(name="Remove reward", value="remove"),
        app_commands.Choice(name="List rewards", value="list")
    ])
    async def config_level(
        self,
        interaction: discord.Interaction,
        action: str,
        level: Optional[int] = None,
        role: Optional[discord.Role] = None
    ):
        """Configure level-up role rewards"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action in ["add", "remove"] and level is None:
                raise ValueError("Level is required for this action")

            if action == "add" and not role:
                raise ValueError("Role is required when adding a reward")

            level_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'level_roles') or {}

            if action == "list":
                if not level_roles:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Level Rewards",
                            "No level rewards have been configured"
                        )
                    )
                    return

                rewards = []
                for lvl, role_id in sorted(level_roles.items(), key=lambda x: int(x[0])):
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        rewards.append(f"Level {lvl}: {role.mention}")

                await interaction.response.send_message(
                    embed=self.bot.ui_manager.info_embed(
                        "Level Rewards",
                        "Here are the current level-up role rewards:\n\n" + "\n".join(rewards)
                    )
                )

            elif action == "add":
                level_roles[str(level)] = str(role.id)
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'level_roles', level_roles)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Level Reward Added",
                        f"Users will receive the {role.mention} role at level {level}"
                    )
                )

            elif action == "remove":
                if str(level) not in level_roles:
                    raise ValueError(f"No reward is configured for level {level}")

                del level_roles[str(level)]
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'level_roles', level_roles)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Level Reward Removed",
                        f"Removed role reward for level {level}"
                    )
                )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure level rewards"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Configuration",
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

    @config.command(
        name="color",
        description="Configure color roles"
    )
    @app_commands.describe(
        action="The action to perform",
        role="The role to configure"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add color role", value="add"),
        app_commands.Choice(name="Remove color role", value="remove"),
        app_commands.Choice(name="List color roles", value="list")
    ])
    async def config_color(
        self,
        interaction: discord.Interaction,
        action: str,
        role: Optional[discord.Role] = None
    ):
        """Configure color roles for the server"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action in ["add", "remove"] and not role:
                raise ValueError("Role is required for this action")

            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id) or []

            if action == "add":
                if str(role.id) in color_roles:
                    raise ValueError(f"{role.mention} is already a color role")

                color_roles.append(str(role.id))
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'color_roles', color_roles)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Color Role Added",
                        f"{role.mention} has been added as a color role"
                    )
                )

            elif action == "remove":
                if str(role.id) not in color_roles:
                    raise ValueError(f"{role.mention} is not a color role")

                color_roles.remove(str(role.id))
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'color_roles', color_roles)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Color Role Removed",
                        f"{role.mention} has been removed from color roles"
                    )
                )

            elif action == "list":
                if not color_roles:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Color Roles",
                            "No color roles have been configured"
                        )
                    )
                    return

                role_mentions = []
                for role_id in color_roles:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_mentions.append(role.mention)

                await interaction.response.send_message(
                    embed=self.bot.ui_manager.info_embed(
                        "Color Roles",
                        "Here are the available color roles:\n\n" + "\n".join(role_mentions)
                    )
                )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure color roles"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Configuration",
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

async def setup(bot):
    await bot.add_cog(ConfigurationCog(bot))