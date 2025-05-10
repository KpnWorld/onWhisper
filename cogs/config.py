import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import timedelta

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    config_group = app_commands.Group(
        name="config",
        description="Server settings and configuration"
    )

    # Whisper System Configuration
    @config_group.command(name="whisper")
    @app_commands.describe(
        setting="The whisper setting to configure",
        value="The value to set for toggle (true/false)",
        channel="The channel for whisper threads",
        role="The staff role for whispers",
        timeout="Auto-close timeout in minutes"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="toggle", value="toggle"),
        app_commands.Choice(name="staff_role", value="staff_role"),
        app_commands.Choice(name="timeout", value="timeout"),
        app_commands.Choice(name="channel", value="channel")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def config_whisper(
        self,
        interaction: discord.Interaction,
        setting: Literal["toggle", "staff_role", "timeout", "channel"],
        value: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
        timeout: Optional[int] = None
    ):
        """Configure whisper system settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if setting == "toggle":                
                config = await self.bot.db_manager.get_guild_config(interaction.guild_id)
                if not config:
                    return await interaction.response.send_message(
                        "⚠️ No configuration found for this server.",
                        ephemeral=True
                    )
                
                if value:
                    enabled = value.lower() == "true"
                else:
                    enabled = not config.get("whisper_enabled", True)
                
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"whisper_enabled": enabled}
                )
                await interaction.response.send_message(
                    f"✅ Whisper system {'enabled' if enabled else 'disabled'}.",
                    ephemeral=True
                )

            elif setting == "staff_role":
                if not role:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a role.",
                        ephemeral=True
                    )
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"staff_role_id": role.id}
                )
                await interaction.response.send_message(
                    f"✅ Set {role.mention} as the whisper staff role.",
                    ephemeral=True
                )

            elif setting == "timeout":
                if not timeout or timeout < 1:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a valid timeout in minutes (minimum 1).",
                        ephemeral=True
                    )
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"whisper_timeout": timeout}
                )
                await interaction.response.send_message(
                    f"✅ Set whisper auto-close timeout to {timeout} minutes.",
                    ephemeral=True
                )

            elif setting == "channel":
                if not channel:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a channel.",
                        ephemeral=True
                    )
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"whisper_channel_id": channel.id}
                )
                await interaction.response.send_message(
                    f"✅ Set {channel.mention} as the whisper channel.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    # XP System Configuration
    @config_group.command(name="xp")
    @app_commands.describe(
        setting="The XP setting to configure",
        value="The value to set for toggle (true/false)",
        rate="XP gain rate (1-100)",
        cooldown="XP gain cooldown in seconds"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="toggle", value="toggle"),
        app_commands.Choice(name="rate", value="rate"),
        app_commands.Choice(name="cooldown", value="cooldown")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def config_xp(
        self,
        interaction: discord.Interaction,
        setting: Literal["toggle", "rate", "cooldown"],
        value: Optional[str] = None,
        rate: Optional[int] = None,
        cooldown: Optional[int] = None
    ):
        """Configure XP system settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if setting == "toggle":
                enabled = value.lower() == "true" if value else None
                if enabled is None:
                    config = await self.bot.db_manager.get_guild_config(interaction.guild_id)
                    enabled = not config.get("xp_enabled", True)
                
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"xp_enabled": enabled}
                )
                await interaction.response.send_message(
                    f"✅ XP system {'enabled' if enabled else 'disabled'}.",
                    ephemeral=True
                )

            elif setting == "rate":
                if not rate or not 1 <= rate <= 100:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a valid XP rate (1-100).",
                        ephemeral=True
                    )
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"xp_rate": rate}
                )
                await interaction.response.send_message(
                    f"✅ Set XP gain rate to {rate}.",
                    ephemeral=True
                )

            elif setting == "cooldown":
                if not cooldown or cooldown < 1:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a valid cooldown in seconds (minimum 1).",
                        ephemeral=True
                    )
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"xp_cooldown": cooldown}
                )
                await interaction.response.send_message(
                    f"✅ Set XP gain cooldown to {cooldown} seconds.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    # Moderation Configuration
    @config_group.command(name="mod")
    @app_commands.describe(
        setting="The moderation setting to configure",
        role="The role to set"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="mod_role", value="mod_role"),
        app_commands.Choice(name="admin_role", value="admin_role")
    ])
    @app_commands.default_permissions(administrator=True)
    async def config_mod(
        self,
        interaction: discord.Interaction,
        setting: Literal["mod_role", "admin_role"],
        role: discord.Role
    ):
        """Configure moderation settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if setting == "mod_role":
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"mod_role_id": role.id}
                )
                await interaction.response.send_message(
                    f"✅ Set {role.mention} as the moderator role.",
                    ephemeral=True
                )
            elif setting == "admin_role":
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"admin_role_id": role.id}
                )
                await interaction.response.send_message(
                    f"✅ Set {role.mention} as the admin role.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )
    
    # Level Roles Configuration
    @config_group.command(name="level")
    @app_commands.describe(
        action="The action to perform",
        level="The level to configure",
        role="The role to assign at this level"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="list", value="list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def config_level(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove", "list"],
        level: Optional[int] = None,
        role: Optional[discord.Role] = None
    ):
        """Configure level-based role rewards"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if action == "add":
                if not level or level < 1:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a valid level (minimum 1).",
                        ephemeral=True
                    )
                if not role:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a role.",
                        ephemeral=True
                    )

                await self.bot.db_manager.set_level_role(
                    interaction.guild_id,
                    level,
                    role.id
                )
                await interaction.response.send_message(
                    f"✅ Set {role.mention} as the reward for level {level}.",
                    ephemeral=True
                )

            elif action == "remove":
                if not level:
                    return await interaction.response.send_message(
                        "⚠️ Please provide the level to remove.",
                        ephemeral=True
                    )

                await self.bot.db_manager.set_level_role(
                    interaction.guild_id,
                    level,
                    None
                )
                await interaction.response.send_message(
                    f"✅ Removed role reward for level {level}.",
                    ephemeral=True
                )

            elif action == "list":
                level_roles = await self.bot.db_manager.get_level_roles(interaction.guild_id)
                
                if not level_roles:
                    return await interaction.response.send_message(
                        "ℹ️ No level roles configured.",
                        ephemeral=True
                    )

                embed = discord.Embed(
                    title="Level Role Rewards",
                    color=discord.Color.blue(),
                    description="Here are all the level-based role rewards:"
                )

                for level, role_id in sorted(level_roles.items()):
                    role = interaction.guild.get_role(role_id)
                    if role:
                        embed.add_field(
                            name=f"Level {level}",
                            value=role.mention,
                            inline=True
                        )

                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    # Show All Configuration
    @config_group.command(name="show")
    @app_commands.default_permissions(manage_guild=True)
    async def show_config(self, interaction: discord.Interaction):
        """Show current server configuration"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            config = await self.bot.db_manager.get_guild_config(interaction.guild_id)
            if not config:
                return await interaction.response.send_message(
                    "⚠️ No configuration found for this server.",
                    ephemeral=True
                )

            embed = discord.Embed(
                title="Server Configuration",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            # Whisper settings
            whisper_status = "✅ Enabled" if config.get("whisper_enabled", True) else "❌ Disabled"
            staff_role = interaction.guild.get_role(config.get("staff_role_id"))
            whisper_channel = interaction.guild.get_channel(config.get("whisper_channel_id"))
            
            embed.add_field(
                name="Whisper System",
                value=f"""
                Status: {whisper_status}
                Staff Role: {staff_role.mention if staff_role else "Not set"}
                Channel: {whisper_channel.mention if whisper_channel else "Not set"}
                Timeout: {config.get('whisper_timeout', 24)} hours
                """.strip(),
                inline=False
            )

            # XP settings
            xp_status = "✅ Enabled" if config.get("xp_enabled", True) else "❌ Disabled"
            embed.add_field(
                name="XP System",
                value=f"""
                Status: {xp_status}
                Rate: {config.get('xp_rate', 15)} XP per message
                Cooldown: {config.get('xp_cooldown', 60)} seconds
                """.strip(),
                inline=False
            )

            # Mod settings
            mod_role = interaction.guild.get_role(config.get("mod_role_id"))
            admin_role = interaction.guild.get_role(config.get("admin_role_id"))
            embed.add_field(
                name="Moderation",
                value=f"""
                Mod Role: {mod_role.mention if mod_role else "Not set"}
                Admin Role: {admin_role.mention if admin_role else "Not set"}
                """.strip(),
                inline=False
            )

            # Level roles
            level_roles = await self.bot.db_manager.get_level_roles(interaction.guild_id)
            if level_roles:
                level_roles_text = "\n".join(
                    f"Level {level}: {interaction.guild.get_role(role_id).mention if interaction.guild.get_role(role_id) else 'Invalid Role'}"
                    for level, role_id in sorted(level_roles.items())
                )
            else:
                level_roles_text = "No level roles configured"

            embed.add_field(
                name="Level Roles",
                value=level_roles_text,
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))