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
        self.db = bot.db  # Use bot's database instance
        self.owner_id = 895767962722660372 # Replace with your Discord user ID
        bot.loop.create_task(self._init_db())
        logger.info("Owner cog initialized")

    async def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
            logger.info("Owner cog database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize owner cog database: {e}")

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user is the bot owner"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ This command is restricted to the bot owner.", 
                ephemeral=True
            )
            return False
        return True

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize settings when bot joins a new guild"""
        try:
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
            
            # Get global metrics
            result = await self.db.fetchrow("""
                SELECT 
                    COUNT(DISTINCT guild_id) as total_guilds,
                    SUM(member_count) as total_members,
                    SUM(active_users) as total_active,
                    COUNT(DISTINCT metric_id) as data_points
                FROM guild_metrics
                WHERE timestamp >= datetime('now', ?)
            """, (f'-{days} days',))

            if result:
                total_guilds = int(result[0] or 0)
                total_members = int(result[1] or 0)
                total_active = int(result[2] or 0)
                data_points = int(result[3] or 0)
            else:
                total_guilds = total_members = total_active = data_points = 0

            # Get global command usage
            command_result = await self.db.fetchrow("""
                SELECT COUNT(*) 
                FROM command_stats
                WHERE used_at >= datetime('now', ?)
            """, (f'-{days} days',))
            total_commands = int(command_result[0] if command_result else 0)

            embed = discord.Embed(
                title=f"📊 Bot Statistics ({timeframe})",
                description=f"Global statistics across {len(self.bot.guilds)} guilds",
                color=discord.Color.blue()
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

            # Most Used Commands Globally
            async with self.db.cursor() as cur:
                await cur.execute("""
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

            # Global Error Rate
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                """, (f'-{days} days',))
                result = await cur.fetchone()
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
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        guild_id,
                        COUNT(*) as command_count
                    FROM command_stats
                    WHERE used_at >= datetime('now', ?)
                    GROUP BY guild_id
                    ORDER BY command_count DESC
                    LIMIT 3
                """, (f'-{days} days',))
                active_guilds = await cur.fetchall()

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
    async def viewguild(self, interaction: discord.Interaction, guild_id: str = None):
        """View detailed information about a guild"""
        try:
            await interaction.response.defer()
            
            target_guild_id = int(guild_id) if guild_id else interaction.guild_id
            settings = self.db.get_all_guild_settings(target_guild_id)
            
            if not settings:
                await interaction.followup.send(f"Guild {target_guild_id} not found in database.", ephemeral=True)
                return

            embed = discord.Embed(
                title="📋 Guild Information",
                color=discord.Color.blue()
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
            await interaction.followup.send("Invalid guild ID format.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error showing guild info: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching guild information.",
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
                "❌ An error occurred while fetching statistics.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Owner(bot))