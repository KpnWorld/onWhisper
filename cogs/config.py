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
        key=[app_commands.Choice(name=k, value=k) for k in DEFAULT_CONFIG.keys()],
    )
    async def config_cmd(
        self,
        interaction: discord.Interaction,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ):
        guild_id = interaction.guild.id

        if action == "view-all":
            await interaction.response.defer(ephemeral=True)  # <-- defer first
            await self.config.load_guild(guild_id)
            data = self.config._cache[guild_id]
            embed = discord.Embed(
                title=f"Configuration for {interaction.guild.name}",
                color=discord.Color.blurple()
            )
            for k, v in data.items():
                embed.add_field(name=k, value=str(v) or "None", inline=False)
            await interaction.followup.send(embed=embed)  # <-- followup after defer
            return

        if action == "view":
            if not key:
                await interaction.response.send_message("You must provide a key to view.")
                return
            val = await self.config.get(guild_id, key)
            await interaction.response.send_message(
                f"Config `{key}` = `{val}`"
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
                    parsed = value.lower() in ("true", "1", "yes", "on")
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
            await interaction.response.send_message(
                f"Config key `{key}` updated to `{parsed}`."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
