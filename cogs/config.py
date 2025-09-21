# cogs/config.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime
import logging
from utils.config import ConfigManager, DEFAULT_CONFIG
from utils.logging_manager import LOG_CATEGORIES

logger = logging.getLogger("onWhisper.Config")


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: ConfigManager = bot.config_manager  # type: ignore[attr-defined]

    @app_commands.command(
        name="config",
        description="View or edit guild configuration",
    )
    @app_commands.describe(
        action="Action to perform",
        key="Config key to set (ignored for view-all)",
        value="New value for key (ignored for view-all)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="view-all", value="view-all"),
            app_commands.Choice(name="view", value="view"),
            app_commands.Choice(name="set", value="set"),
        ]
    )
    async def config_cmd(
        self,
        interaction: discord.Interaction,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
            return
            
        guild_id = interaction.guild.id

        if action == "view-all":
            await interaction.response.defer(ephemeral=True)
            try:
                import asyncio
                # Add timeout to prevent hanging
                await asyncio.wait_for(self.config.load_guild(guild_id), timeout=5.0)
                data = self.config._cache[guild_id]
                embed = discord.Embed(
                    title=f"⚙️ Configuration for {interaction.guild.name}",
                    color=discord.Color.blurple()
                )
                for k, v in data.items():
                    if isinstance(v, bool):
                        v_display = "✅ Enabled" if v else "❌ Disabled"
                    else:
                        v_display = str(v) if v is not None else "None"
                    embed.add_field(name=k, value=v_display, inline=False)
                await interaction.followup.send(embed=embed)
            except asyncio.TimeoutError:
                await interaction.followup.send("❌ Config loading timed out. Please try again.", ephemeral=True)
            except Exception as e:
                print(f"Error in config view-all: {e}")
                await interaction.followup.send("❌ An error occurred while loading configuration.", ephemeral=True)
            return

        if action == "view":
            if not key:
                await interaction.response.send_message("You must provide a key to view.")
                return
            val = await self.config.get(guild_id, key)
            if isinstance(val, bool):
                val_display = "✅ Enabled" if val else "❌ Disabled"
            else:
                val_display = str(val)
            
            await interaction.response.send_message(
                f"Config `{key}` = `{val_display}`"
            )
            return

        if action == "set":
            if not key or value is None:
                await interaction.response.send_message(
                    "You must provide both a key and a value to set."
                )
                return

            if key not in DEFAULT_CONFIG:
                await interaction.response.send_message(
                    f"Invalid key. Valid keys: {', '.join(DEFAULT_CONFIG.keys())}"
                )
                return

            default_val = DEFAULT_CONFIG[key]
            try:
                if isinstance(default_val, bool):
                    parsed = value.lower() in ("true", "1", "yes", "on", "enabled")
                elif isinstance(default_val, int):
                    parsed = int(value)
                else:
                    parsed = value
            except Exception:
                await interaction.response.send_message(
                    f"Failed to convert value for `{key}`."
                )
                return

            await self.config.set(guild_id, key, parsed)
            display_val = "✅ Enabled" if isinstance(parsed, bool) and parsed else (
                "❌ Disabled" if isinstance(parsed, bool) else str(parsed)
            )
            await interaction.response.send_message(
                f"Config key `{key}` updated to {display_val}."
            )

    @app_commands.command(name="log-setup")
    @app_commands.describe(
        action="Action to perform on logging system",
        category="Logging category to configure",
        enabled="Enable or disable logging for this category",
        channel="Channel to send logs to for this category"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="view-all", value="view-all"),
            app_commands.Choice(name="configure", value="configure"),
            app_commands.Choice(name="enable-all", value="enable-all"),
            app_commands.Choice(name="disable-all", value="disable-all")
        ],
        category=[
            app_commands.Choice(name="🚪 Member Events", value="member"),
            app_commands.Choice(name="💬 Message Events", value="message"),
            app_commands.Choice(name="🛡️ Moderation Events", value="moderation"),
            app_commands.Choice(name="🔊 Voice Events", value="voice"),
            app_commands.Choice(name="📂 Channel Events", value="channel"),
            app_commands.Choice(name="🎭 Role Events", value="role"),
            app_commands.Choice(name="🤖 Bot Events", value="bot"),
            app_commands.Choice(name="🤫 Whisper Events", value="whisper")
        ]
    )
    @app_commands.default_permissions(manage_guild=True)
    async def log_setup(
        self,
        interaction: discord.Interaction,
        action: str,
        category: Optional[str] = None,
        enabled: Optional[bool] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure the unified logging system with easy-to-use interface"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # View all logging settings
            if action == "view-all":
                await interaction.response.defer(ephemeral=True)
                
                # Get master logging status
                master_enabled = await self.config.get(interaction.guild.id, "unified_logging_enabled", True)
                
                embed = discord.Embed(
                    title="📊 Unified Logging System Configuration",
                    description=f"**Master Status**: {'✅ Enabled' if master_enabled else '❌ Disabled'}",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                for cat_key, log_cat in LOG_CATEGORIES.items():
                    # Get category settings
                    cat_enabled = await self.config.get(interaction.guild.id, log_cat.enabled_key, True)
                    cat_channel_id = await self.config.get(interaction.guild.id, log_cat.channel_key)
                    
                    # Format channel display
                    if cat_channel_id:
                        channel_display = f"<#{cat_channel_id}>"
                    else:
                        channel_display = "Not configured"
                    
                    # Add field for this category
                    status = "✅ Enabled" if cat_enabled else "❌ Disabled"
                    embed.add_field(
                        name=f"{log_cat.emoji} {log_cat.name}",
                        value=f"**Status**: {status}\n**Channel**: {channel_display}",
                        inline=True
                    )
                
                embed.set_footer(text="Use /log-setup configure to modify settings")
                await interaction.followup.send(embed=embed)
                return
            
            # Enable all categories
            elif action == "enable-all":
                await self.config.set(interaction.guild.id, "unified_logging_enabled", True)
                for log_cat in LOG_CATEGORIES.values():
                    await self.config.set(interaction.guild.id, log_cat.enabled_key, True)
                
                await interaction.response.send_message(
                    "✅ **All logging categories enabled!**\n"
                    "Use `/log-setup configure` to set specific channels for each category.",
                    ephemeral=True
                )
                return
            
            # Disable all categories
            elif action == "disable-all":
                await self.config.set(interaction.guild.id, "unified_logging_enabled", False)
                
                await interaction.response.send_message(
                    "❌ **Unified logging system disabled!**\n"
                    "No logs will be sent until you re-enable it with `/log-setup enable-all`.",
                    ephemeral=True
                )
                return
            
            # Configure specific category
            elif action == "configure":
                if not category:
                    return await interaction.response.send_message(
                        "❌ You must specify a category to configure!",
                        ephemeral=True
                    )
                
                if category not in LOG_CATEGORIES:
                    return await interaction.response.send_message(
                        "❌ Invalid category specified!",
                        ephemeral=True
                    )
                
                log_cat = LOG_CATEGORIES[category]
                changes_made = []
                
                # Update enabled status if provided
                if enabled is not None:
                    await self.config.set(interaction.guild.id, log_cat.enabled_key, enabled)
                    status = "enabled" if enabled else "disabled"
                    changes_made.append(f"**Status**: {status}")
                
                # Update channel if provided
                if channel:
                    await self.config.set(interaction.guild.id, log_cat.channel_key, channel.id)
                    changes_made.append(f"**Channel**: {channel.mention}")
                
                if not changes_made:
                    return await interaction.response.send_message(
                        "❌ No changes specified! Use the `enabled` or `channel` parameters.",
                        ephemeral=True
                    )
                
                # Show current configuration
                current_enabled = await self.config.get(interaction.guild.id, log_cat.enabled_key, True)
                current_channel_id = await self.config.get(interaction.guild.id, log_cat.channel_key)
                current_channel_display = f"<#{current_channel_id}>" if current_channel_id else "Not configured"
                
                embed = discord.Embed(
                    title=f"{log_cat.emoji} {log_cat.name} Configuration Updated",
                    description=f"**Changes Made**:\n" + "\n".join(changes_made),
                    color=log_cat.color,
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="Current Configuration",
                    value=f"**Status**: {'✅ Enabled' if current_enabled else '❌ Disabled'}\n"
                          f"**Channel**: {current_channel_display}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        except Exception as e:
            logger.error(f"Error in log-setup command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while configuring logging settings.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
