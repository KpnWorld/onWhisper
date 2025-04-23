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
            await self.ui_manager.send_embed(
                ctx,
                title="Access Denied",
                description="These commands are only available to the bot owner.",
                command_type="Owner",
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
                    title="📄 Database Table",
                    description="Table is empty or doesn't exist",
                    fields=[{"name": "Table", "value": table_name}],
                    command_type="Owner",
                    ephemeral=True
                )
                return

            content = "\n".join([f"Row {i+1}: {dict(row)}" for i, row in enumerate(rows)])
            await self.ui_manager.send_response(
                interaction,
                title="📄 Database Contents",
                description=f"Contents of table: {table_name}",
                fields=[{"name": "Data", "value": content}],
                command_type="Owner",
                ephemeral=True
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Database Error",
                f"Failed to read table: {str(e)}"
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
                return await self.ui_manager.send_embed(
                    interaction,
                    title="No Data Found",
                    description=f"No statistics found for {user.mention}",
                    command_type="Owner",
                    ephemeral=True
                )

            # Build detailed stats embed
            embed = discord.Embed(
                title=f"📊 Stats for {user}",
                description="Detailed user statistics and information",
                color=discord.Color.blue()
            )

            # Add stat fields
            embed.add_field(name="Level", value=str(level_stats['level']), inline=True)
            embed.add_field(name="XP", value=str(level_stats['xp']), inline=True)
            embed.add_field(name="Messages", value=str(level_stats['messages_sent']), inline=True)
            
            if level_stats['last_message']:
                embed.add_field(
                    name="Last Active",
                    value=f"<t:{int(level_stats['last_message'])}:R>",
                    inline=False
                )

            # Add user info
            embed.add_field(
                name="User Info",
                value=f"ID: {user.id}\nCreated: {user.created_at:%Y-%m-%d}\nJoined: {user.joined_at:%Y-%m-%d}",
                inline=False
            )

            await self.ui_manager.send_embed(
                interaction,
                embed=embed,
                command_type="Owner",
                ephemeral=True
            )

        except Exception as e:
            await self.ui_manager.error_embed(
                interaction,
                title="Error",
                description=f"Failed to get user stats: {str(e)}",
                command_type="Owner"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
