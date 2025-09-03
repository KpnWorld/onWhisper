# cogs/debug.py

import discord
from discord import app_commands
from discord.ext import commands
from utils.db_manager import DBManager
from utils.config import ConfigManager

OWNER_ID = 895767962722660372  # Your Discord ID

def owner_only():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)


class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db_manager
        self.config: ConfigManager = bot.config_manager

    @owner_only()
    @app_commands.command(name="debug-db-stats", description="Show row counts for all database tables")
    async def debug_db_stats(self, interaction: discord.Interaction):
        tables = [
            "guild_settings",
            "leveling_users",
            "leveling_roles",
            "autoroles",
            "reaction_roles",
            "color_roles",
            "whispers",
        ]

        lines = []
        for t in tables:
            row = await self.db.fetchone(f"SELECT COUNT(*) as c FROM {t}")
            count = row["c"] if row else 0
            lines.append(f"{t}: {count}")

        message = "```\n" + "\n".join(lines) + "\n```"
        await interaction.response.send_message(message, ephemeral=True)

    @owner_only()
    @commands.command(name="show_config_cache")
    async def show_config_cache(self, ctx: commands.Context):
        if not self.bot.config_manager._cache:
            await ctx.send("No guilds currently cached.")
            return

        lines = [f"Total Cached Guilds: {len(self.bot.config_manager._cache)}", ""]
        for guild_id, config in self.bot.config_manager._cache.items():
            lines.append(f"Guild ID: {guild_id}")
            for k, v in config.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        message = "```\n" + "\n".join(lines) + "\n```"
        await ctx.send(message)

    @owner_only()
    @app_commands.command(name="debug-delete-global", description="Delete ALL rows from a database table (GLOBAL)")
    @app_commands.describe(table="Table to clear")
    @app_commands.choices(
        table=[
            app_commands.Choice(name=t, value=t) for t in [
                "guild_settings",
                "leveling_users",
                "leveling_roles",
                "autoroles",
                "reaction_roles",
                "color_roles",
                "whispers",
            ]
        ]
    )
    async def debug_delete_global(self, interaction: discord.Interaction, table: str):
        await self.db.execute(f"DELETE FROM {table}")
        await interaction.response.send_message(
            f"All rows deleted from `{table}` (GLOBAL).", ephemeral=True
        )

    @owner_only()
    @app_commands.command(name="debug-delete-server", description="Delete rows for this guild only from a table")
    @app_commands.describe(table="Table to clear for this server only")
    @app_commands.choices(
        table=[
            app_commands.Choice(name=t, value=t) for t in [
                "guild_settings",
                "leveling_users",
                "leveling_roles",
                "autoroles",
                "reaction_roles",
                "color_roles",
                "whispers",
            ]
        ]
    )
    async def debug_delete_server(self, interaction: discord.Interaction, table: str):
        guild_id = interaction.guild.id
        if table == "guild_settings":
            await self.db.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        elif table == "whispers":
            await self.db.execute("DELETE FROM whispers WHERE guild_id = ?", (guild_id,))
        else:
            await self.db.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
        await interaction.response.send_message(
            f"Rows deleted from `{table}` for guild `{guild_id}`.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DebugCog(bot))
