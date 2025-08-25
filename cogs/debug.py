# cogs/debug.py

import discord
from discord import app_commands
from discord.ext import commands
from utils.db_manager import DBManager
from utils.config import ConfigManager


class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db  # type: ignore[attr-defined]
        self.config: ConfigManager = bot.config_manager  # type: ignore[attr-defined]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        app = await self.bot.application_info()
        if interaction.user.id != app.owner.id:
            await interaction.response.send_message(
                "You are not authorized to use debug commands.", ephemeral=True
            )
            return False
        return True

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
        embed = discord.Embed(title="Database Statistics", color=discord.Color.dark_gold())
        for t in tables:
            row = await self.db.fetchone(f"SELECT COUNT(*) as c FROM {t}")
            embed.add_field(name=t, value=str(row["c"] if row else 0), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="debug-config-cache", description="Inspect the in-memory config cache")
    async def debug_config_cache(self, interaction: discord.Interaction):
        data = self.config._cache
        embed = discord.Embed(
            title="Config Cache",
            description=f"{len(data)} guilds cached",
            color=discord.Color.purple()
        )
        for gid, conf in data.items():
            short = ", ".join(f"{k}={v}" for k, v in conf.items())
            if len(short) > 1000:
                short = short[:1000] + "..."
            embed.add_field(name=str(gid), value=short or "Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="debug-delete-global", description="Delete ALL rows from a database table (GLOBAL)")
    @app_commands.describe(table="Table to clear")
    @app_commands.choices(
        table=[
            app_commands.Choice(name="guild_settings", value="guild_settings"),
            app_commands.Choice(name="leveling_users", value="leveling_users"),
            app_commands.Choice(name="leveling_roles", value="leveling_roles"),
            app_commands.Choice(name="autoroles", value="autoroles"),
            app_commands.Choice(name="reaction_roles", value="reaction_roles"),
            app_commands.Choice(name="color_roles", value="color_roles"),
            app_commands.Choice(name="whispers", value="whispers"),
        ]
    )
    async def debug_delete_global(self, interaction: discord.Interaction, table: str):
        await self.db.execute(f"DELETE FROM {table}")
        await interaction.response.send_message(f"All rows deleted from `{table}` (GLOBAL).", ephemeral=True)

    @app_commands.command(name="debug-delete-server", description="Delete rows for this guild only from a table")
    @app_commands.describe(table="Table to clear for this server only")
    @app_commands.choices(
        table=[
            app_commands.Choice(name="guild_settings", value="guild_settings"),
            app_commands.Choice(name="leveling_users", value="leveling_users"),
            app_commands.Choice(name="leveling_roles", value="leveling_roles"),
            app_commands.Choice(name="autoroles", value="autoroles"),
            app_commands.Choice(name="reaction_roles", value="reaction_roles"),
            app_commands.Choice(name="color_roles", value="color_roles"),
            app_commands.Choice(name="whispers", value="whispers"),
        ]
    )
    async def debug_delete_server(self, interaction: discord.Interaction, table: str):
        guild_id = interaction.guild.id
        if table == "guild_settings":
            await self.db.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        elif table == "whispers":
            await self.db.execute("DELETE FROM whispers WHERE sender_id IN (SELECT id FROM whispers WHERE guild_id = ?)", (guild_id,))
        else:
            await self.db.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
        await interaction.response.send_message(f"Rows deleted from `{table}` for guild `{guild_id}`.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DebugCog(bot))
