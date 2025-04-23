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
                    title="📊 Database Table",
                    description=f"No data found in table: `{table_name}`",
                    command_type="Owner",
                    fields=[
                        {"name": "Table Name", "value": f"`{table_name}`", "inline": True},
                        {"name": "Status", "value": "❌ Empty", "inline": True}
                    ],
                    ephemeral=True
                )
                return

            # Format rows in a more readable way
            formatted_rows = []
            for i, row in enumerate(rows[:10]):  # Limit to first 10 rows
                row_data = dict(row)
                formatted_row = "\n".join([f"{k}: `{v}`" for k, v in row_data.items()])
                formatted_rows.append(f"**Row {i+1}:**\n{formatted_row}")

            total_rows = len(rows)
            shown_rows = min(10, total_rows)

            await self.ui_manager.send_response(
                interaction,
                title="📊 Database Contents",
                description=f"Showing {shown_rows} of {total_rows} rows from table: `{table_name}`",
                command_type="Owner",
                fields=[
                    {"name": "Table Info", "value": f"Total Rows: `{total_rows}`", "inline": False},
                    {"name": "Data", "value": "\n\n".join(formatted_rows), "inline": False}
                ],
                ephemeral=True
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Database Error",
                f"Failed to read table: {str(e)}",
                command_type="Owner"
            )

    # =========================
    # 👥 User Management
    # =========================

    @app_commands.command(name="user_stats", description="View detailed user statistics")
    @app_commands.describe(user="The user to check stats for")
    async def user_stats(self, interaction: discord.Interaction, user: discord.User):
        """View comprehensive stats for a user"""
        try:
            # Get leveling stats
            level_stats = await self.db_manager.fetch_one(
                """
                SELECT xp, level, last_message, messages_sent 
                FROM leveling 
                WHERE user_id = ? AND guild_id = ?
                """,
                (user.id, interaction.guild_id)
            )

            if not level_stats:
                await self.ui_manager.send_response(
                    interaction,
                    title="👤 User Statistics",
                    description=f"No data found for {user.mention}",
                    command_type="Owner",
                    fields=[
                        {"name": "User ID", "value": f"`{user.id}`", "inline": True},
                        {"name": "Status", "value": "❌ No Data", "inline": True}
                    ],
                    ephemeral=True
                )
                return

            await self.ui_manager.send_response(
                interaction,
                title=f"👤 Stats for {user.name}",
                description="Comprehensive user statistics and information",
                command_type="Owner",
                fields=[
                    {"name": "Level Progress", "value": f"Level: `{level_stats['level']}` | XP: `{level_stats['xp']:,}`", "inline": False},
                    {"name": "Activity", "value": f"Messages: `{level_stats['messages_sent']:,}`", "inline": True},
                    {"name": "Last Active", "value": f"<t:{int(level_stats['last_message'])}:R>" if level_stats['last_message'] else "Never", "inline": True},
                    {"name": "Account Info", "value": f"Created: <t:{int(user.created_at.timestamp())}:D>\nJoined: <t:{int(user.joined_at.timestamp())}:D>", "inline": False}
                ],
                thumbnail_url=user.display_avatar.url if user.display_avatar else None,
                ephemeral=True
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Stats Error",
                f"Failed to fetch user statistics: {str(e)}",
                command_type="Owner"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
