import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    config = app_commands.Group(
        name="config",
        description="Configure bot settings",
        default_permissions=discord.Permissions(administrator=True)
    )

    @config.command(name="whisper")
    @app_commands.describe(
        channel="Channel for whisper threads",
        staff_role="Role that can manage whispers",
        auto_close="Minutes of inactivity before auto-closing (0 to disable)",
        anonymous="Allow anonymous whispers"
    )
    async def config_whisper(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        staff_role: Optional[discord.Role] = None,
        auto_close: Optional[int] = None,
        anonymous: Optional[bool] = None
    ):
        """Configure whisper system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild.id, 'whisper_config')
            changes = []

            if channel is not None:
                config['channel_id'] = str(channel.id)
                changes.append(f"Whisper channel set to {channel.mention}")

            if staff_role is not None:
                config['staff_role'] = str(staff_role.id)
                changes.append(f"Staff role set to {staff_role.mention}")

            if auto_close is not None:
                config['auto_close_minutes'] = max(0, auto_close)
                changes.append(
                    "Auto-close disabled" if auto_close == 0
                    else f"Auto-close set to {auto_close} minutes"
                )

            if anonymous is not None:
                config['anonymous_allowed'] = anonymous
                changes.append(
                    "Anonymous whispers enabled" if anonymous
                    else "Anonymous whispers disabled"
                )

            if changes:
                await self.bot.db_manager.set_section(interaction.guild.id, 'whisper_config', config)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Whisper Settings Updated",
                        "\n".join(f"• {change}" for change in changes)
                    )
                )
            else:
                # Show current settings
                embed = discord.Embed(
                    title="Whisper Settings",
                    color=discord.Color.blue()
                )

                channel = interaction.guild.get_channel(
                    int(config['channel_id']) if config.get('channel_id') else 0
                )
                staff_role = interaction.guild.get_role(
                    int(config['staff_role']) if config.get('staff_role') else 0
                )

                embed.add_field(
                    name="Channel",
                    value=channel.mention if channel else "Not set",
                    inline=True
                )
                embed.add_field(
                    name="Staff Role",
                    value=staff_role.mention if staff_role else "Not set",
                    inline=True
                )
                embed.add_field(
                    name="Auto Close",
                    value=f"{config['auto_close_minutes']} minutes" if config['auto_close_minutes'] else "Disabled",
                    inline=True
                )
                embed.add_field(
                    name="Anonymous Whispers",
                    value="Enabled" if config['anonymous_allowed'] else "Disabled",
                    inline=True
                )

                await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure settings"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @config.command(name="leveling")
    @app_commands.describe(
        enabled="Enable/disable XP gain",
        rate="Base XP per message (15 recommended)",
        cooldown="Seconds between XP gains"
    )
    async def config_leveling(
        self,
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        rate: Optional[int] = None,
        cooldown: Optional[int] = None
    ):
        """Configure leveling system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            config = await self.bot.db_manager.get_section(interaction.guild.id, 'xp_settings')
            changes = []

            if enabled is not None:
                config['enabled'] = enabled
                changes.append(
                    "XP system enabled" if enabled
                    else "XP system disabled"
                )

            if rate is not None:
                if rate < 1:
                    raise ValueError("XP rate must be at least 1")
                config['rate'] = rate
                changes.append(f"XP rate set to {rate}")

            if cooldown is not None:
                if cooldown < 0:
                    raise ValueError("Cooldown cannot be negative")
                config['cooldown'] = cooldown
                changes.append(f"Cooldown set to {cooldown} seconds")

            if changes:
                await self.bot.db_manager.set_section(interaction.guild.id, 'xp_settings', config)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Leveling Settings Updated",
                        "\n".join(f"• {change}" for change in changes)
                    )
                )
            else:
                # Show current settings
                embed = discord.Embed(
                    title="Leveling Settings",
                    color=discord.Color.blue()
                )

                embed.add_field(
                    name="Status",
                    value="Enabled" if config['enabled'] else "Disabled",
                    inline=True
                )
                embed.add_field(
                    name="XP Rate",
                    value=str(config['rate']),
                    inline=True
                )
                embed.add_field(
                    name="Cooldown",
                    value=f"{config['cooldown']} seconds",
                    inline=True
                )

                await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure settings"
                ),
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

    @config.command(name="logging")
    @app_commands.describe(
        channel="Channel for logging",
        enabled="Enable/disable logging",
        event_type="Type of events to configure"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Member events", value="member"),
        app_commands.Choice(name="Server events", value="server"),
        app_commands.Choice(name="Moderation events", value="moderation")
    ])
    async def config_logging(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None,
        event_type: Optional[str] = None
    ):
        """Configure logging system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            # Get config with safe operation
            config = await self.bot.db_manager.safe_operation(
                'get_logs_config',
                self.bot.db_manager.get_section,
                interaction.guild_id,
                'logs'
            )
            changes = []

            async with await self.bot.db_manager.transaction(interaction.guild_id, 'config') as txn:
                if channel is not None:
                    config['log_channel'] = str(channel.id)
                    changes.append(f"Log channel set to {channel.mention}")

                if enabled is not None:
                    config['enabled'] = enabled
                    changes.append(
                        "Logging system enabled" if enabled
                        else "Logging system disabled"
                    )

                if event_type:
                    # Create options for event types
                    options = []
                    match event_type:
                        case "member":
                            options = [
                                discord.SelectOption(label="Join", value="join"),
                                discord.SelectOption(label="Leave", value="leave")
                            ]
                        case "server":
                            options = [
                                discord.SelectOption(label="Message Delete", value="message_delete"),
                                discord.SelectOption(label="Message Edit", value="message_edit"),
                                discord.SelectOption(label="Channel Create", value="channel_create"),
                                discord.SelectOption(label="Channel Delete", value="channel_delete"),
                                discord.SelectOption(label="Role Update", value="role_update")
                            ]
                        case "moderation":
                            options = [
                                discord.SelectOption(label="Warn", value="warn"),
                                discord.SelectOption(label="Kick", value="kick"),
                                discord.SelectOption(label="Ban", value="ban"),
                                discord.SelectOption(label="Timeout", value="timeout"),
                                discord.SelectOption(label="Lockdown", value="lockdown")
                            ]

                    selected = await self.bot.ui_manager.create_select_menu(
                        interaction,
                        [{
                            "label": opt.label,
                            "value": opt.value,
                            "default": opt.value in config['log_types'][event_type]
                        } for opt in options],
                        f"Select {event_type} events to log",
                        min_values=0,
                        max_values=len(options)
                    )

                    if selected is not None:  # None means timeout
                        config['log_types'][event_type] = selected
                        changes.append(f"Updated {event_type} event logging")

                if changes:
                    # Update config atomically
                    await self.bot.db_manager.set_section(interaction.guild_id, 'logs', config)
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.success_embed(
                            "Logging Settings Updated",
                            "\n".join(f"• {change}" for change in changes)
                        )
                    )
                else:
                    # Show current settings
                    embed = discord.Embed(
                        title="Logging Settings",
                        color=discord.Color.blue()
                    )

                    channel = interaction.guild.get_channel(
                        int(config['log_channel']) if config.get('log_channel') else 0
                    )

                    embed.add_field(
                        name="Status",
                        value="Enabled" if config['enabled'] else "Disabled",
                        inline=True
                    )
                    embed.add_field(
                        name="Channel",
                        value=channel.mention if channel else "Not set",
                        inline=True
                    )

                    for category, events in config['log_types'].items():
                        embed.add_field(
                            name=f"{category.title()} Events",
                            value=", ".join(events) if events else "None",
                            inline=False
                        )

                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=embed)
                    else:
                        await interaction.followup.send(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure settings"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @config.command(name="roles")
    @app_commands.describe(
        type="Role system to configure",
        enabled="Enable/disable the role system"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Color roles", value="color"),
        app_commands.Choice(name="Reaction roles", value="reaction"),
        app_commands.Choice(name="Auto role", value="auto")
    ])
    async def config_roles(
        self,
        interaction: discord.Interaction,
        type: str,
        enabled: Optional[bool] = None
    ):
        """Configure role systems"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            section_map = {
                'color': 'color_roles',
                'reaction': 'reaction_roles',
                'auto': 'server_config'
            }

            section = section_map[type]
            
            # Get config with safe operation
            config = await self.bot.db_manager.safe_operation(
                'get_section',
                self.bot.db_manager.get_section,
                interaction.guild_id,
                section
            )

            if enabled is not None:
                # Use transaction for atomic update
                async with await self.bot.db_manager.transaction(interaction.guild_id, 'config') as txn:
                    if type == 'auto':
                        config['auto_role_enabled'] = enabled
                        # Clear auto role if disabling
                        if not enabled:
                            config['auto_role'] = None
                    else:
                        config['enabled'] = enabled
                        # Clear role data if disabling
                        if not enabled:
                            if type == 'color':
                                config['roles'] = []
                            elif type == 'reaction':
                                config.clear()
                                config['enabled'] = False

                    await self.bot.db_manager.set_section(interaction.guild_id, section, config)

                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Role Settings Updated",
                        f"{type.title()} roles {'enabled' if enabled else 'disabled'}"
                    )
                )
            else:
                # Show current settings
                embed = discord.Embed(
                    title=f"{type.title()} Role Settings",
                    color=discord.Color.blue()
                )

                status = (config.get('auto_role_enabled', False) if type == 'auto'
                         else config.get('enabled', False))

                embed.add_field(
                    name="Status",
                    value="Enabled" if status else "Disabled",
                    inline=True
                )

                if type == 'color':
                    embed.add_field(
                        name="Available Colors",
                        value=str(len(config.get('roles', []))),
                        inline=True
                    )
                elif type == 'reaction':
                    active_bindings = sum(1 for k in config.keys() if k != 'enabled')
                    embed.add_field(
                        name="Active Bindings",
                        value=str(active_bindings),
                        inline=True
                    )
                elif type == 'auto':
                    role_id = config.get('auto_role')
                    role = interaction.guild.get_role(int(role_id)) if role_id else None
                    embed.add_field(
                        name="Auto Role",
                        value=role.mention if role else "Not set",
                        inline=True
                    )

                await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure settings"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @config.command(name="view")
    async def config_view(self, interaction: discord.Interaction):
        """View all current settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            # Collect all configurations
            whisper = await self.bot.db_manager.get_section(interaction.guild.id, 'whisper_config')
            xp = await self.bot.db_manager.get_section(interaction.guild.id, 'xp_settings')
            logs = await self.bot.db_manager.get_section(interaction.guild.id, 'logs')
            color_roles = await self.bot.db_manager.get_section(interaction.guild.id, 'color_roles')
            reaction_roles = await self.bot.db_manager.get_section(interaction.guild.id, 'reaction_roles')
            server = await self.bot.db_manager.get_section(interaction.guild.id, 'server_config')

            # Create embeds for each system
            pages = []

            # Whisper Settings
            whisper_embed = discord.Embed(
                title="Whisper System Settings",
                color=discord.Color.blue()
            )
            channel = interaction.guild.get_channel(
                int(whisper['channel_id']) if whisper.get('channel_id') else 0
            )
            staff_role = interaction.guild.get_role(
                int(whisper['staff_role']) if whisper.get('staff_role') else 0
            )

            whisper_embed.add_field(
                name="Channel",
                value=channel.mention if channel else "Not set",
                inline=True
            )
            whisper_embed.add_field(
                name="Staff Role",
                value=staff_role.mention if staff_role else "Not set",
                inline=True
            )
            whisper_embed.add_field(
                name="Auto Close",
                value=f"{whisper['auto_close_minutes']} minutes" if whisper['auto_close_minutes'] else "Disabled",
                inline=True
            )
            whisper_embed.add_field(
                name="Anonymous Whispers",
                value="Enabled" if whisper['anonymous_allowed'] else "Disabled",
                inline=True
            )
            pages.append(whisper_embed)

            # XP Settings
            xp_embed = discord.Embed(
                title="Leveling System Settings",
                color=discord.Color.blue()
            )
            xp_embed.add_field(
                name="Status",
                value="Enabled" if xp['enabled'] else "Disabled",
                inline=True
            )
            xp_embed.add_field(
                name="XP Rate",
                value=str(xp['rate']),
                inline=True
            )
            xp_embed.add_field(
                name="Cooldown",
                value=f"{xp['cooldown']} seconds",
                inline=True
            )
            pages.append(xp_embed)

            # Logging Settings
            log_embed = discord.Embed(
                title="Logging Settings",
                color=discord.Color.blue()
            )
            log_channel = interaction.guild.get_channel(
                int(logs['log_channel']) if logs.get('log_channel') else 0
            )
            log_embed.add_field(
                name="Status",
                value="Enabled" if logs['enabled'] else "Disabled",
                inline=True
            )
            log_embed.add_field(
                name="Channel",
                value=log_channel.mention if log_channel else "Not set",
                inline=True
            )
            for category, events in logs['log_types'].items():
                log_embed.add_field(
                    name=f"{category.title()} Events",
                    value=", ".join(events) if events else "None",
                    inline=False
                )
            pages.append(log_embed)

            # Role Settings
            role_embed = discord.Embed(
                title="Role System Settings",
                color=discord.Color.blue()
            )
            auto_role = interaction.guild.get_role(
                int(server['auto_role']) if server.get('auto_role') else 0
            )
            role_embed.add_field(
                name="Color Roles",
                value=(
                    f"Enabled - {len(color_roles['roles'])} colors available"
                    if color_roles['enabled'] else "Disabled"
                ),
                inline=False
            )
            role_embed.add_field(
                name="Reaction Roles",
                value=(
                    f"Enabled - {len(reaction_roles)} bindings active"
                    if reaction_roles.get('enabled') else "Disabled"
                ),
                inline=False
            )
            role_embed.add_field(
                name="Auto Role",
                value=(
                    f"Enabled - {auto_role.mention}" if server.get('auto_role_enabled') and auto_role
                    else "Disabled"
                ),
                inline=False
            )
            pages.append(role_embed)

            # Show paginated settings
            await self.bot.ui_manager.paginate(
                interaction=interaction,
                pages=pages
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to view settings"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))