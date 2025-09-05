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

    @commands.hybrid_command(name="config", description="View or edit guild configuration")
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
        ctx: commands.Context,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ):
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server!")
            return
            
        guild_id = ctx.guild.id

        if action == "view-all":
            # Defer for slash commands only
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            
            await self.config.load_guild(guild_id)
            data = self.config._cache[guild_id]
            embed = discord.Embed(
                title=f"⚙️ Configuration for {ctx.guild.name}",
                color=discord.Color.blurple()
            )
            for k, v in data.items():
                if isinstance(v, bool):
                    v_display = "✅ Enabled" if v else "❌ Disabled"
                else:
                    v_display = str(v) if v is not None else "None"
                embed.add_field(name=k, value=v_display, inline=False)
            
            # Send embed
            await ctx.send(embed=embed)
            return

        if action == "view":
            if not key:
                await ctx.send("You must provide a key to view.")
                return
            val = await self.config.get(guild_id, key)
            if isinstance(val, bool):
                val_display = "✅ Enabled" if val else "❌ Disabled"
            else:
                val_display = str(val)
            
            response = f"Config `{key}` = `{val_display}`"
            await ctx.send(response)
            return

        if action == "set":
            if not key or value is None:
                await ctx.send("You must provide both a key and a value to set.")
                return

            if key not in DEFAULT_CONFIG:
                await ctx.send(f"Invalid key. Valid keys: {', '.join(DEFAULT_CONFIG.keys())}")
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
                await ctx.send(f"Failed to convert value for `{key}`.")
                return

            await self.config.set(guild_id, key, parsed)
            display_val = "✅ Enabled" if isinstance(parsed, bool) and parsed else (
                "❌ Disabled" if isinstance(parsed, bool) else str(parsed)
            )
            response = f"Config key `{key}` updated to {display_val}."
            await ctx.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
