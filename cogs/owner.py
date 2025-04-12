import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Literal
from utils.db_manager import DatabaseManager
from utils.ui_manager import UIManager
from datetime import datetime

logger = logging.getLogger(__name__)

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use bot's database instance
        self.ui = UIManager()  # Initialize UIManager
        self.owner_id = 895767962722660372 # Replace with your Discord user ID
        bot.loop.create_task(self._init_db())
        logger.info("Owner cog initialized")

    async def cog_load(self):
        """Ensure database is initialized when cog loads"""
        await self.db._ensure_initialized()  # Wait for initialization

    async def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            async with self.db.transaction():
                for guild in self.bot.guilds:
                    await self.db.ensure_guild_exists(guild.id)
            logger.info("Owner cog database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize owner cog database: {e}")

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user is the bot owner"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Access Denied",
                    "This command is restricted to the bot owner.",
                    "Owner"
                ),
                ephemeral=True
            )
            return False
        return True

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize settings when bot joins a new guild"""
        try:
            async with self.db.transaction():
                await self.db.ensure_guild_exists(guild.id)
                logger.info(f"Initialized owner settings for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to initialize owner settings for guild {guild.name}: {e}")

    @app_commands.command(name="stats", description="View global bot statistics and metrics")
    async def stats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed bot statistics across all guilds"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]
            
            async with self.db.cursor() as cur:
                # Get global metrics using efficient indexing
                result = await cur.execute("""
                    SELECT 
                        COUNT(DISTINCT guild_id) as total_guilds,
                        SUM(member_count) as total_members,
                        SUM(active_users) as total_active,
                        COUNT(DISTINCT metric_id) as data_points
                    FROM guild_metrics
                    WHERE timestamp >= datetime('now', ?)
                    """, (f'-{days} days',))
                metrics = await result.fetchone()

                if metrics:
                    total_guilds = int(metrics[0] or 0)
                    total_members = int(metrics[1] or 0)
                    total_active = int(metrics[2] or 0)
                    data_points = int(metrics[3] or 0)
                else:
                    total_guilds = total_members = total_active = data_points = 0

                # Get command usage with improved query
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total_commands,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
                        AVG(execution_time) as avg_execution_time
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                    """, (f'-{days} days',))
                cmd_stats = await cur.fetchone()
                
                total_commands = int(cmd_stats[0] if cmd_stats else 0)
                error_count = int(cmd_stats[1] if cmd_stats else 0)
                avg_exec_time = float(cmd_stats[2] if cmd_stats else 0)

                # Get top commands with execution stats
                top_commands = await cur.execute("""
                    SELECT 
                        command_name,
                        COUNT(*) as uses,
                        ROUND(AVG(execution_time), 2) as avg_time,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                    GROUP BY command_name
                    ORDER BY uses DESC
                    LIMIT 5
                    """, (f'-{days} days',))
                top_cmds = await top_commands.fetchall()

            embed = self.ui.info_embed(
                f"Bot Statistics ({timeframe})",
                f"Global statistics across {len(self.bot.guilds)} guilds",
                "Owner"
            )

            # Global Activity Metrics
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

            # Performance Metrics
            perf_text = (
                f"Success Rate: {((total_commands - error_count) / total_commands * 100):.1f}%\n"
                f"Avg Response: {avg_exec_time*1000:.1f}ms\n"
                f"Error Count: {error_count:,}"
            )
            embed.add_field(
                name="⚡ Performance",
                value=f"```\n{perf_text}\n```",
                inline=False
            )

            # Top Commands with Usage Stats
            if top_cmds:
                cmd_text = "\n".join(
                    f"{cmd[0]}: {cmd[1]:,} uses ({cmd[2]}ms avg, {cmd[3]}%)" 
                    for cmd in top_cmds
                )
                embed.add_field(
                    name="🔧 Most Used Commands",
                    value=f"```\n{cmd_text}\n```",
                    inline=False
                )

            # Database Stats
            db_size = await self.db.get_database_size()
            db_stats = await self.db.get_connection_stats()
            table_sizes = await self.db.get_table_sizes()
            
            db_text = (
                f"Size: {db_size / 1024 / 1024:.2f}MB\n"
                f"Tables: {len(table_sizes)}\n"
                f"Mode: {db_stats.get('journal_mode', 'unknown')}"
            )
            embed.add_field(
                name="💾 Database",
                value=f"```\n{db_text}\n```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Global stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error showing global stats: {e}")
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Statistics Error",
                    "An error occurred while fetching statistics.",
                    "Owner"
                ),
                ephemeral=True
            )

    @app_commands.command(name="viewguild", description="View detailed guild information")
    async def viewguild(self, interaction: discord.Interaction, guild_id: str = None):
        """View detailed information about a guild"""
        try:
            await interaction.response.defer()
            
            target_guild_id = int(guild_id) if guild_id else interaction.guild_id
            settings = self.db.get_all_guild_settings(target_guild_id)
            
            if not settings:
                await interaction.followup.send(
                    embed=self.ui.error_embed(
                        "Not Found",
                        f"Guild {target_guild_id} not found in database.",
                        "Owner"
                    ),
                    ephemeral=True
                )
                return

            embed = self.ui.info_embed(
                "Guild Information",
                f"Details for guild ID: {target_guild_id}",
                "Owner"
            )

            # Core Settings (indexes 0-3)
            core_info = (
                f"ID: {settings[0]}\n"
                f"Prefix: {settings[1]}\n"
                f"Locale: {settings[2]}\n"
                f"Timezone: {settings[3]}"
            )
            embed.add_field(
                name="⚙️ Core Settings",
                value=f"```\n{core_info}\n```",
                inline=False
            )

            # Leveling Settings (indexes 4-7)
            level_info = (
                f"XP Cooldown: {settings[4]}s\n"
                f"XP Range: {settings[5]}-{settings[6]}\n"
                f"Level Channel: {f'<#{settings[7]}>' if settings[7] else 'Default'}"
            )
            embed.add_field(
                name="📈 Leveling System",
                value=f"```\n{level_info}\n```",
                inline=False
            )

            # Database Info (indexes 8-9)
            created = datetime.fromisoformat(settings[8].replace('Z', '+00:00'))
            updated = datetime.fromisoformat(settings[9].replace('Z', '+00:00'))
            db_info = (
                f"Created: {created.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Last Updated: {updated.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            embed.add_field(
                name="📁 Database Info",
                value=f"```\n{db_info}\n```",
                inline=False
            )

            # User Stats
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_users,
                           AVG(level) as avg_level,
                           MAX(level) as max_level,
                           SUM(messages) as total_messages
                    FROM xp_data
                    WHERE guild_id = ?
                """, (target_guild_id,))
                user_stats = await cur.fetchone()

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

            await interaction.followup.send(embed=embed)
            logger.info(f"Guild info viewed by {interaction.user}")
        except ValueError:
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Invalid Input",
                    "Invalid guild ID format.",
                    "Owner"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error showing guild info: {e}")
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching guild information.",
                    "Owner"
                ),
                ephemeral=True
            )

    @app_commands.command(name="ownerserverstats", description="View statistics for a specific guild (Owner only)")
    async def ownerserverstats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed statistics for a guild (Owner only)"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]

            # Get guild metrics
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        ROUND(AVG(CAST(member_count AS FLOAT)), 0) as avg_members,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT metric_id) as data_points,
                        ROUND(AVG(CAST(active_users AS FLOAT)), 0) as avg_active
                    FROM guild_metrics
                    WHERE guild_id = ? 
                    AND timestamp >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))
                metrics = await cur.fetchone()

            embed = self.ui.info_embed(
                f"Guild Statistics ({timeframe})",
                f"Statistics for {interaction.guild.name}",
                "Owner"
            )

            # Activity metrics
            avg_members = int(metrics[0] or 0)
            total_messages = int(metrics[1] or 0)
            data_points = int(metrics[2] or 0)
            avg_active = int(metrics[3] or 0)

            # Get command usage count
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(*) 
                    FROM command_stats
                    WHERE guild_id = ? 
                    AND used_at >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))
                total_commands = await cur.fetchone()[0] or 0

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
            async with self.db.cursor() as cur:
                await cur.execute("""
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
                top_commands = await cur.fetchall()

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
            async with self.db.cursor() as cur:
                await cur.execute("""
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
                active_users = await cur.fetchall()

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
            async with self.db.cursor() as cur:
                await cur.execute("""
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
                activity = await cur.fetchall()

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
                embed=self.ui.error_embed(
                    "Statistics Error",
                    "An error occurred while fetching statistics.",
                    "Owner"
                ),
                ephemeral=True
            )

    @app_commands.command(name="databasestats", description="View detailed database statistics")
    async def databasestats(self, interaction: discord.Interaction):
        """View detailed database statistics and health metrics"""
        try:
            await interaction.response.defer()

            # Get various database statistics
            db_size = await self.db.get_database_size()
            table_sizes = await self.db.get_table_sizes()
            conn_stats = await self.db.get_connection_stats()
            integrity_ok = await self.db.check_database_integrity()

            embed = self.ui.info_embed(
                "Database Statistics",
                "Detailed database metrics and health information",
                "Owner"
            )

            # Basic Stats
            stats_text = (
                f"Size: {db_size / 1024 / 1024:.2f}MB\n"
                f"Tables: {len(table_sizes)}\n"
                f"Integrity: {'✅' if integrity_ok else '❌'}"
            )
            embed.add_field(
                name="📊 Overview",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            # Table Sizes
            tables_text = "\n".join(
                f"{table}: {count:,} rows" 
                for table, count in table_sizes.items()
            )
            embed.add_field(
                name="📑 Table Sizes",
                value=f"```\n{tables_text}\n```",
                inline=False
            )

            # Connection Settings
            settings_text = (
                f"Journal: {conn_stats.get('journal_mode', 'unknown')}\n"
                f"Cache: {conn_stats.get('cache_size', 'unknown')}\n"
                f"Foreign Keys: {'enabled' if conn_stats.get('foreign_keys') else 'disabled'}"
            )
            embed.add_field(
                name="⚙️ Settings",
                value=f"```\n{settings_text}\n```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Database stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error showing database stats: {e}")
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Statistics Error",
                    "An error occurred while fetching database statistics.",
                    "Owner"
                ),
                ephemeral=True
            )

    @app_commands.command(name="optimizedb", description="Optimize the database")
    async def optimizedb(self, interaction: discord.Interaction):
        """Run database optimization routines"""
        try:
            await interaction.response.defer()

            # Get size before optimization
            size_before = await self.db.get_database_size()

            # Run optimization
            await self.db.optimize_database()

            # Get size after optimization
            size_after = await self.db.get_database_size()
            size_saved = size_before - size_after

            embed = self.ui.success_embed(
                "Database Optimized",
                "Database optimization completed successfully",
                "Owner"
            )

            stats_text = (
                f"Size Before: {size_before / 1024 / 1024:.2f}MB\n"
                f"Size After: {size_after / 1024 / 1024:.2f}MB\n"
                f"Space Saved: {size_saved / 1024 / 1024:.2f}MB"
            )
            embed.add_field(
                name="📊 Results",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Database optimized by {interaction.user}")
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Optimization Error",
                    "An error occurred while optimizing the database.",
                    "Owner"
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Owner(bot))