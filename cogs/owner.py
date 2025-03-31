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

    @app_commands.command(name="stats", description="View global bot statistics and metrics")
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed bot statistics across all guilds"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]
            
            # Get global metrics
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT guild_id) as total_guilds,
                        SUM(member_count) as total_members,
                        SUM(active_users) as total_active,
                        COUNT(DISTINCT metric_id) as data_points
                    FROM guild_metrics
                    WHERE timestamp >= datetime('now', ?)
                """, (f'-{days} days',))
                metrics = cur.fetchone()

            embed = discord.Embed(
                title=f"📊 Bot Statistics ({timeframe})",
                description=f"Global statistics across {len(self.bot.guilds)} guilds",
                color=discord.Color.blue()
            )

            # Global Activity Metrics
            total_guilds = int(metrics[0] or 0)
            total_members = int(metrics[1] or 0)
            total_active = int(metrics[2] or 0)
            data_points = int(metrics[3] or 0)
            
            # Get global command usage
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                """, (f'-{days} days',))
                total_commands = cur.fetchone()[0] or 0

            stats_text = (
                f"Total Guilds: {len(self.bot.guilds):,}\n"
                f"Total Members: {sum(g.member_count for g in self.bot.guilds):,}\n"
                f"Commands Used: {total_commands:,}\n"
                f"Active Users: {total_active:,}\n"
                f"Data Points: {data_points:,}"
            )
            embed.add_field(
                name="📈 Global Activity",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            # Most Used Commands Globally
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        command_name,
                        COUNT(*) as uses,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                    GROUP BY command_name
                    ORDER BY uses DESC
                    LIMIT 5
                """, (f'-{days} days',))
                top_commands = cur.fetchall()

            if top_commands:
                cmd_text = "\n".join(
                    f"{cmd}: {uses} uses ({pct}%)" 
                    for cmd, uses, pct in top_commands
                )
                embed.add_field(
                    name="🔧 Most Used Commands",
                    value=f"```\n{cmd_text}\n```",
                    inline=False
                )

            # Global Error Rate
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                """, (f'-{days} days',))
                result = cur.fetchone()
                total = int(result[0] or 0)
                errors = int(result[1] or 0)
                error_rate = (errors / total * 100) if total > 0 else 0

            if total > 0:
                embed.add_field(
                    name="⚠️ Error Rate",
                    value=f"```\n{error_rate:.1f}% ({errors:,}/{total:,} commands)\n```",
                    inline=False
                )

            # Most Active Guilds
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        guild_id,
                        COUNT(*) as command_count
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                    GROUP BY guild_id
                    ORDER BY command_count DESC
                    LIMIT 3
                """, (f'-{days} days',))
                active_guilds = cur.fetchall()

            if active_guilds:
                guild_text = []
                for guild_id, cmd_count in active_guilds:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        guild_text.append(f"{guild.name}: {cmd_count:,} commands")
                
                if guild_text:
                    embed.add_field(
                        name="🏆 Most Active Guilds",
                        value=f"```\n" + "\n".join(guild_text) + "\n```",
                        inline=False
                    )

            await interaction.followup.send(embed=embed)
            logger.info(f"Global stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error showing global stats: {e}")
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

    @app_commands.command(name="guildstats", description="View statistics for a specific guild")
    @app_commands.default_permissions(administrator=True)
    async def guildstats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed statistics for the current guild"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]

            # Get guild metrics
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        ROUND(AVG(CAST(member_count AS FLOAT)), 0) as avg_members,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT metric_id) as data_points,
                        ROUND(AVG(CAST(active_users AS FLOAT)), 0) as avg_active
                    FROM guild_metrics
                    WHERE guild_id = ? 
                    AND timestamp >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))
                metrics = cur.fetchone()

            embed = discord.Embed(
                title=f"📊 Guild Statistics ({timeframe})",
                description=f"Statistics for {interaction.guild.name}",
                color=discord.Color.blue()
            )

            # Activity metrics
            avg_members = int(metrics[0] or 0)
            total_messages = int(metrics[1] or 0)
            data_points = int(metrics[2] or 0)
            avg_active = int(metrics[3] or 0)

            # Get command usage count
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM command_stats
                    WHERE guild_id = ? 
                    AND used_at >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))
                total_commands = cur.fetchone()[0] or 0

            stats_text = (
                f"Average Members: {avg_members:,}\n"
                f"Total Messages: {total_messages:,}\n"
                f"Commands Used: {total_commands:,}\n"
                f"Active Users (avg): {avg_active:,}\n"
                f"Data Points: {data_points:,}"
            )
            embed.add_field(
                name="📈 Activity Metrics",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            # Command Usage with percentage
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        command_name,
                        COUNT(*) as uses,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
                    FROM command_stats
                    WHERE guild_id = ? 
                    AND used_at >= datetime('now', ?)
                    GROUP BY command_name
                    ORDER BY uses DESC
                    LIMIT 5
                """, (interaction.guild_id, f'-{days} days'))
                top_commands = cur.fetchall()

            if top_commands:
                cmd_text = "\n".join(
                    f"{cmd}: {uses} uses ({pct}%)" 
                    for cmd, uses, pct in top_commands
                )
                embed.add_field(
                    name="🔧 Most Used Commands",
                    value=f"```\n{cmd_text}\n```",
                    inline=False
                )

            # Most Active Users
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        user_id,
                        COUNT(*) as cmd_count
                    FROM command_stats
                    WHERE guild_id = ?
                    AND used_at >= datetime('now', ?)
                    GROUP BY user_id
                    ORDER BY cmd_count DESC
                    LIMIT 3
                """, (interaction.guild_id, f'-{days} days'))
                active_users = cur.fetchall()

            if active_users:
                user_text = []
                for user_id, cmd_count in active_users:
                    member = interaction.guild.get_member(user_id)
                    if member:
                        user_text.append(f"{member.display_name}: {cmd_count:,} commands")
                
                if user_text:
                    embed.add_field(
                        name="👥 Most Active Users",
                        value=f"```\n" + "\n".join(user_text) + "\n```",
                        inline=False
                    )

            # Activity Trend
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 
                        strftime('%Y-%m-%d', timestamp) as day,
                        COUNT(*) as commands,
                        AVG(active_users) as avg_active
                    FROM guild_metrics
                    WHERE guild_id = ?
                    AND timestamp >= datetime('now', ?)
                    GROUP BY day
                    ORDER BY day DESC
                """, (interaction.guild_id, f'-{days} days'))
                activity = cur.fetchall()

            if activity:
                trend = "\n".join(
                    f"{day}: {int(active):,} active, {int(cmds):,} commands"
                    for day, cmds, active in activity[:3]
                )
                embed.add_field(
                    name="📅 Recent Activity",
                    value=f"```\n{trend}\n```",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
            logger.info(f"Guild stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error showing guild stats: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching statistics.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Owner(bot))