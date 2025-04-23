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

    # =========================
    # 🔒 Owner Checks
    # =========================

    async def cog_check(self, ctx: discord.Interaction) -> bool:
        """Ensure only bot owner can use these commands"""
        try:
            return ctx.user.id == self.bot.owner_id
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle owner-only errors gracefully"""
        if isinstance(error, commands.NotOwner):
            await self.ui_manager.send_response(
                ctx,
                title="🔒 Access Denied",
                description="This command is restricted to the bot owner.",
                command_type="Error",
                ephemeral=True
            )

    # =========================
    # 📊 Database Management
    # =========================

    @app_commands.command(name="view_table", description="View all rows from a database table")
    @app_commands.describe(table_name="The name of the table to view")
    async def view_table(self, interaction: discord.Interaction, table_name: str):
        """View contents of a database table"""
        try:
            rows = await self.db_manager.fetch_all(f"SELECT * FROM {table_name}")
            
            if not rows:
                await self.ui_manager.send_response(
                    interaction,
                    title="Database View",
                    description=f"Table contents for: `{table_name}`",
                    command_type="database",
                    fields=[
                        {"name": "Status", "value": "Empty Table", "inline": True},
                        {"name": "Table Name", "value": table_name, "inline": True}
                    ],
                    ephemeral=True
                )
                return

            formatted_data = {}
            for i, row in enumerate(rows[:10], 1):
                formatted_data[f"Row {i}"] = dict(row)

            await self.ui_manager.send_response(
                interaction,
                title="Database Contents",
                description=f"Showing data from table: `{table_name}`",
                command_type="database",
                fields=[
                    {"name": "Overview", "value": {
                        "Total Rows": len(rows),
                        "Shown Rows": min(10, len(rows)),
                        "Table": table_name
                    }, "inline": False},
                    {"name": "Data", "value": formatted_data, "inline": False}
                ],
                ephemeral=True
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Database View Failed",
                str(e),
                command_type="database"
            )

    # =========================
    # 👥 User Management
    # =========================

    @app_commands.command(name="user_stats", description="View detailed user statistics")
    @app_commands.describe(user="The user to check stats for")
    async def user_stats(self, interaction: discord.Interaction, user: discord.User):
        """View comprehensive stats for a user"""
        try:
            stats = await self.db_manager.fetch_one(
                """SELECT * FROM leveling WHERE user_id = ? AND guild_id = ?""",
                (user.id, interaction.guild_id)
            )
            
            if not stats:
                await self.ui_manager.send_response(
                    interaction,
                    title="User Statistics",
                    description=f"Statistics for {user.mention}",
                    command_type="stats",
                    fields=[
                        {"name": "Status", "value": "No Data Found", "inline": True},
                        {"name": "User ID", "value": user.id, "inline": True}
                    ],
                    thumbnail_url=user.display_avatar.url if user.display_avatar else None
                )
                return

            user_data = {
                "Level": stats['level'],
                "XP": f"{stats['xp']:,}",
                "Messages": f"{stats['messages_sent']:,}",
                "Last Active": f"<t:{int(stats['last_message'])}:R>" if stats['last_message'] else "Never"
            }

            account_info = {
                "Created": f"<t:{int(user.created_at.timestamp())}:F>",
                "Joined": f"<t:{int(user.joined_at.timestamp())}:F>",
                "ID": user.id
            }

            await self.ui_manager.send_response(
                interaction,
                title=f"User Statistics: {user.name}",
                description="Detailed user information and statistics",
                command_type="stats",
                fields=[
                    {"name": "📊 Activity Stats", "value": user_data, "inline": False},
                    {"name": "👤 Account Info", "value": account_info, "inline": False}
                ],
                thumbnail_url=user.display_avatar.url if user.display_avatar else None
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Stats Lookup Failed",
                str(e),
                command_type="stats"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
