import discord
from discord import app_commands
from discord.ext import commands
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    async def cog_check(self, ctx: discord.Interaction) -> bool:
        return ctx.user.id == self.bot.owner_id

    # ──────────────────────────────────────────────────────────────
    # 📂 Owner Commands • Database
    # ──────────────────────────────────────────────────────────────

    @app_commands.command(name="view_table", description="View all rows from a database table.")
    @app_commands.describe(table_name="Name of the table to view.")
    async def view_table(self, interaction: discord.Interaction, table_name: str):
        rows = await self.db_manager.fetch_all(f"SELECT * FROM {table_name}")
        if not rows:
            return await self.ui_manager.send_embed(
                interaction, "That table is either empty or doesn't exist.",
                status="error", ephemeral=True
            )

        fields = rows[0].keys()
        content = ""
        for row in rows:
            content += "\n".join([f"**{k}:** {v}" for k, v in dict(row).items()]) + "\n\n"

        pages = [content[i:i + 1900] for i in range(0, len(content), 1900)]
        await self.ui_manager.send_paginated_embed(
            interaction, pages, title=f"📄 Table: `{table_name}`",
            status="default", ephemeral=True
        )

    @app_commands.command(name="user_stats", description="View a user's leveling stats.")
    @app_commands.describe(user="The user whose stats you want to view.")
    async def user_stats(self, interaction: discord.Interaction, user: discord.User):
        stats = await self.db_manager.fetch_one(
            "SELECT * FROM leveling WHERE user_id = ? AND guild_id = ?", 
            (user.id, interaction.guild_id)
        )
        if not stats:
            return await self.ui_manager.send_embed(
                interaction, f"{user.mention} has no leveling data.",
                status="error", ephemeral=True
            )

        embed = discord.Embed(
            title=f"📊 Stats for {user}",
            description=(
                f"**XP:** {stats['xp']}\n"
                f"**Level:** {stats['level']}\n"
                f"**Last Message:** <t:{int(stats['last_message'])}:R>"
            ),
            color=discord.Color.blue()
        )

        await self.ui_manager.send_embed(
            interaction, embed=embed, status="default", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
