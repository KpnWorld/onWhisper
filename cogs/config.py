import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
from datetime import datetime

class ConfigurationCog(commands.Cog):
    """Configuration commands for server settings"""
    
    def __init__(self, bot):
        self.bot = bot

    config = app_commands.Group(name="config", description="Configure server settings")

    @config.command(name='whisper')
    @app_commands.describe(
        setting='The whisper system setting to configure',
        channel='The channel for whisper threads',
        role='Staff role that can manage whispers',
        minutes='Minutes of inactivity before auto-closing whispers',
        days='Days to keep closed whisper threads',
        enabled='Enable or disable the system'
    )
    async def config_whisper(
        self,
        interaction: discord.Interaction,
        setting: Literal['channel', 'staff', 'timeout', 'retention', 'toggle'],
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
        minutes: Optional[int] = None,
        days: Optional[int] = None,
        enabled: Optional[bool] = None
    ):
        """Configure whisper system settings"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure whispers"
                ),
                ephemeral=True
            )
            return

        try:
            match setting:
                case 'channel':
                    if not channel:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Channel",
                                "You must specify a channel for whisper threads"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'channel_id', channel.id)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Whisper Channel Set",
                            f"Whisper threads will be created in {channel.mention}"
                        )
                    )

                case 'staff':
                    if not role:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Role",
                                "You must specify a staff role"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'staff_role', role.id)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Staff Role Set",
                            f"Members with {role.mention} can now manage whispers"
                        )
                    )

                case 'timeout':
                    if not minutes or minutes < 1:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Invalid Timeout",
                                "Please specify a valid number of minutes (minimum 1)"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'auto_close_minutes', minutes)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Timeout Set",
                            f"Inactive whispers will auto-close after {minutes} minutes"
                        )
                    )

                case 'retention':
                    if not days or days < 1:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Invalid Retention Period",
                                "Please specify a valid number of days (minimum 1)"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'retention_days', days)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Retention Period Set",
                            f"Closed whispers will be kept for {days} days"
                        )
                    )

                case 'toggle':
                    config = await self.bot.db_manager.get_section(interaction.guild_id, 'whisper_config')
                    new_state = enabled if enabled is not None else not config.get('enabled', True)
                    await self.bot.db_manager.update_whisper_config(interaction.guild_id, 'enabled', new_state)
                    status = "enabled" if new_state else "disabled"
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Whisper System Toggled",
                            f"Whisper system has been {status}"
                        )
                    )

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Configuration Error",
                    f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )

    @config.command(name='xp')
    @app_commands.describe(
        setting='The XP system setting to configure',
        amount='Amount of XP per message (1-100)',
        seconds='Cooldown between XP gains in seconds',
        enabled='Enable or disable the system'
    )
    async def config_xp(
        self,
        interaction: discord.Interaction,
        setting: Literal['rate', 'cooldown', 'toggle'],
        amount: Optional[int] = None,
        seconds: Optional[int] = None,
        enabled: Optional[bool] = None
    ):
        """Configure XP system settings"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure XP settings"
                ),
                ephemeral=True
            )
            return

        try:
            match setting:
                case 'rate':
                    if not amount or not 1 <= amount <= 100:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Invalid Amount",
                                "Please specify an amount between 1 and 100"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_xp_config(interaction.guild_id, 'rate', amount)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "XP Rate Set",
                            f"Members will now gain {amount} XP per message"
                        )
                    )

                case 'cooldown':
                    if not seconds or seconds < 1:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Invalid Cooldown",
                                "Please specify a valid number of seconds (minimum 1)"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.update_xp_config(interaction.guild_id, 'cooldown', seconds)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "XP Cooldown Set",
                            f"Members must wait {seconds} seconds between XP gains"
                        )
                    )

                case 'toggle':
                    config = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
                    new_state = enabled if enabled is not None else not config.get('enabled', True)
                    await self.bot.db_manager.update_xp_config(interaction.guild_id, 'enabled', new_state)
                    status = "enabled" if new_state else "disabled"
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "XP System Toggled",
                            f"XP system has been {status}"
                        )
                    )

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Configuration Error",
                    f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )

    @config.command(name='level')
    @app_commands.describe(
        setting='The level rewards setting to configure',
        level='The level number',
        role='The role to award at this level'
    )
    async def config_level(
        self,
        interaction: discord.Interaction,
        setting: Literal['add', 'remove', 'list'],
        level: Optional[int] = None,
        role: Optional[discord.Role] = None
    ):
        """Configure level reward settings"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure level rewards"
                ),
                ephemeral=True
            )
            return

        try:
            match setting:
                case 'add':
                    if not level or not role:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Parameters",
                                "Please specify both a level and a role"
                            ),
                            ephemeral=True
                        )
                        return
                    await self.bot.db_manager.add_level_role(interaction.guild_id, level, role.id)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Level Reward Added",
                            f"Members will receive {role.mention} at level {level}"
                        )
                    )

                case 'remove':
                    if not level:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Level",
                                "Please specify the level to remove"
                            ),
                            ephemeral=True
                        )
                        return
                    success = await self.bot.db_manager.remove_level_role(interaction.guild_id, level)
                    if success:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.success_embed(
                                "Level Reward Removed",
                                f"Removed role reward for level {level}"
                            )
                        )
                    else:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Not Found",
                                f"No role reward found for level {level}"
                            ),
                            ephemeral=True
                        )

                case 'list':
                    rewards = await self.bot.db_manager.get_level_roles(interaction.guild_id)
                    if not rewards:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.info_embed(
                                "Level Rewards",
                                "No level rewards configured"
                            )
                        )
                        return

                    # Sort rewards by level
                    rewards.sort(key=lambda x: x[0])
                    
                    # Create description with role mentions
                    description = "\n".join(
                        f"Level {level}: <@&{role_id}>"
                        for level, role_id in rewards
                    )

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Level Rewards",
                            description
                        )
                    )

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Configuration Error",
                    f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )

    @config.command(name='color')
    @app_commands.describe(
        setting='The color roles setting to configure',
        role='The role to add/remove from allowed color roles'
    )
    async def config_color(
        self,
        interaction: discord.Interaction,
        setting: Literal['add', 'remove', 'list'],
        role: Optional[discord.Role] = None
    ):
        """Configure color role settings"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure color roles"
                ),
                ephemeral=True
            )
            return

        try:
            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
            
            match setting:
                case 'add':
                    if not role:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Role",
                                "Please specify a role to add"
                            ),
                            ephemeral=True
                        )
                        return
                    
                    if str(role.id) in color_roles:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Already Added",
                                f"{role.mention} is already a color role"
                            ),
                            ephemeral=True
                        )
                        return

                    color_roles.append(str(role.id))
                    await self.bot.db_manager.update_color_roles(interaction.guild_id, color_roles)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Added",
                            f"Added {role.mention} to allowed color roles"
                        )
                    )

                case 'remove':
                    if not role:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Missing Role",
                                "Please specify a role to remove"
                            ),
                            ephemeral=True
                        )
                        return
                    
                    if str(role.id) not in color_roles:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.error_embed(
                                "Not Found",
                                f"{role.mention} is not a color role"
                            ),
                            ephemeral=True
                        )
                        return

                    color_roles.remove(str(role.id))
                    await self.bot.db_manager.update_color_roles(interaction.guild_id, color_roles)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Removed",
                            f"Removed {role.mention} from allowed color roles"
                        )
                    )

                case 'list':
                    if not color_roles:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.info_embed(
                                "Color Roles",
                                "No color roles configured"
                            )
                        )
                        return

                    description = "\n".join(f"<@&{role_id}>" for role_id in color_roles)
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Color Roles",
                            description
                        )
                    )

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Configuration Error",
                    f"An error occurred: {str(e)}"
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfigurationCog(bot))