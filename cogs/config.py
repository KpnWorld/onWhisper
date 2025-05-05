import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class ConfigurationCog(commands.Cog):
    """Configuration commands for server settings"""
    
    def __init__(self, bot):
        self.bot = bot

    # Configuration command groups
    config = app_commands.Group(
        name="config",
        description="Configure server settings",
        default_permissions=discord.Permissions(administrator=True)
    )

    logs = app_commands.Group(
        name="logs",
        description="Configure logging settings",
        parent=config
    )

    @logs.command(
        name="set",
        description="Configure logging channels"
    )
    @app_commands.describe(
        type="Type of logs to configure",
        channel="Channel to use for logging"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="All logs", value="all"),
            app_commands.Choice(name="Moderation logs", value="mod"),
            app_commands.Choice(name="Member logs", value="member"),
            app_commands.Choice(name="Message logs", value="message"),
            app_commands.Choice(name="Server logs", value="server")
        ]
    )
    async def logs_set(
        self,
        interaction: discord.Interaction,
        type: str,
        channel: discord.TextChannel
    ):
        """Configure logging channels"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            updates = {}
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

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure logging"
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

    @logs.command(
        name="disable",
        description="Disable logging channels"
    )
    @app_commands.describe(
        type="Type of logs to disable"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="All logs", value="all"),
            app_commands.Choice(name="Moderation logs", value="mod"),
            app_commands.Choice(name="Member logs", value="member"),
            app_commands.Choice(name="Message logs", value="message"),
            app_commands.Choice(name="Server logs", value="server")
        ]
    )
    async def logs_disable(
        self,
        interaction: discord.Interaction,
        type: str
    ):
        """Disable logging channels"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            updates = {}
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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    # Whisper configuration group
    whisper = app_commands.Group(
        name="whisper",
        description="Configure whisper system settings",
        parent=config
    )

    @whisper.command(
        name="channel",
        description="Set the whisper channel"
    )
    @app_commands.describe(
        channel="The channel for whispers (optional - will create one if not specified)"
    )
    async def whisper_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure whisper channel"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')

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

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure whispers"
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
        name="staff",
        description="Set the staff role for whispers"
    )
    @app_commands.describe(
        role="The staff role that can manage whispers"
    )
    async def whisper_staff(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Configure whisper staff role"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
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

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure whispers"
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
        name="timeout",
        description="Set auto-close timeout for inactive whispers"
    )
    @app_commands.describe(
        minutes="Minutes of inactivity before auto-closing whispers"
    )
    async def whisper_timeout(
        self,
        interaction: discord.Interaction,
        minutes: int
    ):
        """Configure whisper timeout"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if minutes < 0:
                raise ValueError("Timeout minutes cannot be negative")

            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'auto_close_minutes', minutes)
            
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Auto-Close Timeout Set",
                    f"Inactive whisper threads will be closed after {minutes} minutes"
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
                    "Invalid Value",
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
        name="retention",
        description="Set how long to keep closed whispers"
    )
    @app_commands.describe(
        days="Days to keep closed whisper threads"
    )
    async def whisper_retention(
        self,
        interaction: discord.Interaction,
        days: int
    ):
        """Configure whisper retention period"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if days < 0:
                raise ValueError("Retention days cannot be negative")

            await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'retention_days', days)
            
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Thread Retention Set",
                    f"Closed whisper threads will be kept for {days} days"
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
                    "Invalid Value",
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
        name="toggle",
        description="Toggle the whisper system on/off"
    )
    async def whisper_toggle(
        self,
        interaction: discord.Interaction
    ):
        """Toggle whisper system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    # XP system configuration group
    xp = app_commands.Group(
        name="xp",
        description="Configure XP system settings",
        parent=config
    )

    @xp.command(
        name="rate",
        description="Set the XP gain rate"
    )
    @app_commands.describe(
        value="XP earned per message (1-100)"
    )
    async def xp_rate(
        self,
        interaction: discord.Interaction,
        value: int
    ):
        """Configure XP gain rate"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if value < 1 or value > 100:
                raise ValueError("XP rate must be between 1 and 100")
            
            await self.bot.db_manager.update_xp_config(interaction.guild_id, 'rate', value)
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "XP Rate Updated",
                    f"Users will now gain {value} XP per message"
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
                    "Invalid Value",
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

    @xp.command(
        name="cooldown",
        description="Set the XP gain cooldown"
    )
    @app_commands.describe(
        value="Seconds between XP gains"
    )
    async def xp_cooldown(
        self,
        interaction: discord.Interaction,
        value: int
    ):
        """Configure XP gain cooldown"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if value < 0:
                raise ValueError("Cooldown cannot be negative")
            
            await self.bot.db_manager.update_xp_config(interaction.guild_id, 'cooldown', value)
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "XP Cooldown Updated",
                    f"Users must wait {value} seconds between XP gains"
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
                    "Invalid Value",
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

    @xp.command(
        name="toggle",
        description="Toggle the XP system on/off"
    )
    async def xp_toggle(
        self,
        interaction: discord.Interaction
    ):
        """Toggle XP system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    # Level rewards configuration group  
    level = app_commands.Group(
        name="level",
        description="Configure level-up rewards",
        parent=config
    )

    @level.command(
        name="add",
        description="Add a level-up role reward"
    )
    @app_commands.describe(
        level="The level to give the role at",
        role="The role to give as a reward"
    )
    async def level_add(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role
    ):
        """Add a level-up role reward"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            level_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'level_roles') or {}
            level_roles[str(level)] = str(role.id)
            await self.bot.db_manager.update_guild_data(interaction.guild_id, 'level_roles', level_roles)
            
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Level Reward Added",
                    f"Users will receive the {role.mention} role at level {level}"
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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @level.command(
        name="remove",
        description="Remove a level-up role reward"
    )
    @app_commands.describe(
        level="The level to remove the reward from"
    )
    async def level_remove(
        self,
        interaction: discord.Interaction,
        level: int
    ):
        """Remove a level-up role reward"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            level_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'level_roles') or {}

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
                    "Invalid Level",
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

    @level.command(
        name="list",
        description="List all level-up role rewards"
    )
    async def level_list(
        self,
        interaction: discord.Interaction
    ):
        """List all level-up role rewards"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            level_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'level_roles') or {}

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

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure level rewards"
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

    # Color roles configuration group
    colors = app_commands.Group(
        name="colors",
        description="Configure color roles",
        parent=config
    )

    @colors.command(
        name="add",
        description="Add a color role"
    )
    @app_commands.describe(
        role="The role to add as a color role"
    )
    async def colors_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Add a color role"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id) or []

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
                    "Invalid Role",
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

    @colors.command(
        name="remove",
        description="Remove a color role"
    )
    @app_commands.describe(
        role="The role to remove from color roles"
    )
    async def colors_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Remove a color role"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id) or []

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
                    "Invalid Role",
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

    @colors.command(
        name="list",
        description="List all color roles"
    )
    async def colors_list(
        self,
        interaction: discord.Interaction
    ):
        """List all color roles"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id) or []

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