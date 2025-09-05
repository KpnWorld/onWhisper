# cogs/config.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from utils.config import ConfigManager, DEFAULT_CONFIG


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
        ],
        # Automatically include all keys from DEFAULT_CONFIG
        key=[app_commands.Choice(name=k, value=k) for k in DEFAULT_CONFIG.keys()],
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


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
