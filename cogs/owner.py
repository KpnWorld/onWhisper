import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Literal
from utils.db_manager import DatabaseManager
from datetime import datetime

logger = logging.getLogger(__name__)

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager('bot')

    def cog_check(self, ctx):
        """Only allow bot owner to use these commands"""
        return ctx.author.id == self.bot.owner_id

    @app_commands.command(name="stats", description="View bot statistics and metrics")
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed bot statistics"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]

            guild_stats = self.db.get_guild_stats(interaction.guild_id, days)
            
            embed = discord.Embed(
                title=f"📊 Bot Statistics ({timeframe})",
                color=discord.Color.blue()
            )

            # Guild Activity
            stats_text = (
                f"Average Members: {int(guild_stats['avg_members']):,}\n"
                f"Total Messages: {int(guild_stats['total_messages']):,}\n"
                f"Commands Used: {int(guild_stats['total_commands']):,}\n"
                f"Active Users: {int(guild_stats['avg_active_users']):,}"
            )
            embed.add_field(
                name="📈 Activity Metrics",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            # Command Usage
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT command_name, COUNT(*) as uses
                    FROM command_stats
                    WHERE guild_id = ? 
                    AND used_at >= datetime('now', ?)
                    GROUP BY command_name
                    ORDER BY uses DESC
                    LIMIT 5
                """, (interaction.guild_id, f'-{days} days'))
                top_commands = cur.fetchall()

            if top_commands:
                cmd_text = "\n".join(f"{cmd}: {uses} uses" for cmd, uses in top_commands)
                embed.add_field(
                    name="🔧 Most Used Commands",
                    value=f"```\n{cmd_text}\n```",
                    inline=False
                )

            # Error Rate
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
                    FROM command_stats
                    WHERE guild_id = ?
                    AND used_at >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))
                total, errors = cur.fetchone()

            if total:
                error_rate = (errors / total) * 100
                embed.add_field(
                    name="⚠️ Error Rate",
                    value=f"```\n{error_rate:.1f}% ({errors}/{total} commands)\n```",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
            logger.info(f"Stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching statistics.",
                ephemeral=True
            )

    @app_commands.command(name="viewguild", description="View detailed guild information")
    @app_commands.default_permissions(administrator=True)
    async def viewguild(self, interaction: discord.Interaction, guild_id: str = None):
        """View detailed information about a guild"""
        try:
            await interaction.response.defer()
            
            target_guild_id = int(guild_id) if guild_id else interaction.guild_id
            settings = self.db.get_all_guild_settings(target_guild_id)
            
            if not settings:
                await interaction.followup.send("Guild not found in database.", ephemeral=True)
                return

            embed = discord.Embed(
                title="📋 Guild Information",
                color=discord.Color.blue()
            )

            # Core Settings
            core_info = (
                f"ID: {settings[0]}\n"
                f"Prefix: {settings[3]}\n"
                f"Locale: {settings[4]}\n"
                f"Timezone: {settings[5]}"
            )
            embed.add_field(
                name="⚙️ Core Settings",
                value=f"```\n{core_info}\n```",
                inline=False
            )

            # Leveling Settings
            level_info = (
                f"XP Cooldown: {settings[7]}s\n"
                f"XP Range: {settings[8]}-{settings[9]}\n"
                f"Level Channel: {f'<#{settings[11]}>' if settings[11] else 'Default'}"
            )
            embed.add_field(
                name="📈 Leveling System",
                value=f"```\n{level_info}\n```",
                inline=False
            )

            # User Stats
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_users,
                           AVG(level) as avg_level,
                           MAX(level) as max_level,
                           SUM(messages) as total_messages
                    FROM xp_data
                    WHERE guild_id = ?
                """, (target_guild_id,))
                user_stats = cur.fetchone()

            if user_stats and user_stats[0]:
                stats = (
                    f"Total Users: {int(user_stats[0]):,}\n"
                    f"Average Level: {user_stats[1]:.1f}\n"
                    f"Highest Level: {int(user_stats[2])}\n"
                    f"Total Messages: {int(user_stats[3]):,}"
                )
                embed.add_field(
                    name="📊 Statistics",
                    value=f"```\n{stats}\n```",
                    inline=False
                )

            # Database Info
            created = datetime.fromisoformat(settings[1].replace('Z', '+00:00'))
            updated = datetime.fromisoformat(settings[2].replace('Z', '+00:00'))
            db_info = (
                f"Created: {created.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Last Updated: {updated.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            embed.add_field(
                name="📁 Database Info",
                value=f"```\n{db_info}\n```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Guild info viewed by {interaction.user}")
        except ValueError:
            await interaction.followup.send("Invalid guild ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error showing guild info: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching guild information.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Owner(bot))