import discord
from discord.ext import commands
from discord import app_commands
import time
import logging
import os
import psutil
import platform
from datetime import datetime
from typing import Optional, Literal
from utils.ui_manager import UIManager

# Initialize logger
logger = logging.getLogger(__name__)

def format_dt(dt: datetime) -> str:
    """Format datetime to a readable string"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_size(bytes_size: int) -> str:
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time"""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    delta = now - dt
    
    days = delta.days
    if days > 365:
        years = days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    if days > 30:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    if days > 0:
        return f"{days} day{'s' if days != 1 else ''} ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    minutes = (delta.seconds % 3600) // 60
    return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.ui = UIManager()
        self.start_time = time.time()
        bot.loop.create_task(self._init_db())
        logger.info("Info cog initialized")

    async def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            async with self.db.transaction():
                for guild in self.bot.guilds:
                    await self.db.ensure_guild_exists(guild.id)
            logger.info("Info cog database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize info cog database: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize settings when bot joins a new guild"""
        try:
            async with self.db.transaction():
                await self.db.ensure_guild_exists(guild.id)
                logger.info(f"Initialized info settings for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to initialize info settings for guild {guild.name}: {e}")

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency and API response time"""
        try:
            start_time = time.time()
            await interaction.response.defer()
            end_time = time.time()

            bot_latency = round((end_time - start_time) * 1000, 2)
            websocket_latency = round(self.bot.latency * 1000, 2)

            # Log latency metrics
            async with self.db.transaction():
                await self.db.execute("""
                    INSERT INTO guild_metrics (
                        guild_id, member_count, bot_latency
                    ) VALUES (?, ?, ?)
                """, (
                    interaction.guild_id,
                    interaction.guild.member_count,
                    bot_latency
                ))

            embed = discord.Embed(
                title="🏓 Pong!",
                color=discord.Color.green() if bot_latency < 200 else discord.Color.orange()
            )
            embed.add_field(
                name="Bot Latency",
                value=f"```{bot_latency}ms```",
                inline=True
            )
            embed.add_field(
                name="WebSocket",
                value=f"```{websocket_latency}ms```",
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Ping command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await interaction.followup.send("❌ An error occurred while checking latency.", ephemeral=True)

    @app_commands.command(name="uptime", description="Check how long the bot has been running")
    async def uptime(self, interaction: discord.Interaction):
        """Returns bot uptime and system statistics"""
        try:
            await interaction.response.defer()
            uptime_seconds = round(time.time() - self.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60

            process = psutil.Process()
            memory_usage = process.memory_info().rss
            cpu_percent = process.cpu_percent(interval=0.1)

            # Log system metrics
            async with self.db.transaction():
                await self.db.execute("""
                    INSERT INTO guild_metrics (
                        guild_id, member_count, bot_latency,
                        message_count, active_users
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    interaction.guild_id,
                    interaction.guild.member_count,
                    self.bot.latency * 1000,
                    0,  # message_count placeholder
                    len([m for m in interaction.guild.members if str(m.status) == "online"])
                ))

            embed = discord.Embed(
                title="⏳ Bot Status",
                color=discord.Color.blue()
            )
            
            # Uptime info
            uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
            embed.add_field(
                name="⌚ Uptime",
                value=f"```{uptime_str}```",
                inline=False
            )

            # System stats
            system_info = (
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory: {get_size(memory_usage)}\n"
                f"Python: {platform.python_version()}\n"
                f"OS: {platform.system()} {platform.release()}"
            )
            embed.add_field(
                name="🖥️ System",
                value=f"```{system_info}```",
                inline=False
            )

            # Database stats
            db_size = await self.db.get_database_size()
            db_stats = await self.db.get_connection_stats()
            
            db_info = (
                f"Size: {db_size / 1024 / 1024:.2f}MB\n"
                f"Mode: {db_stats.get('journal_mode', 'unknown')}\n"
                f"Cache: {db_stats.get('cache_size', 'unknown')}"
            )
            embed.add_field(
                name="💾 Database",
                value=f"```{db_info}```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Uptime command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in uptime command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching uptime.", ephemeral=True)

    @app_commands.command(name="serverinfo", description="Get details about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Displays comprehensive server information"""
        try:
            guild = interaction.guild
            total_members = len(guild.members)
            bot_count = len([m for m in guild.members if m.bot])
            human_count = total_members - bot_count
            
            embed = self.ui.info_embed(
                f"{guild.name} Information",
                f"Server ID: {guild.id}",
                "Info"
            )

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # General Info
            general_info = (
                f"Owner: {guild.owner.mention}\n"
                f"Created: <t:{int(guild.created_at.timestamp())}:R>\n"
                f"Verification: {guild.verification_level.name}"
            )
            self.ui.add_field_if_exists(
                embed,
                "📌 General",
                general_info,
                True
            )

            # Member Stats
            member_stats = (
                f"Total: {total_members:,}\n"
                f"Humans: {human_count:,}\n"
                f"Bots: {bot_count:,}"
            )
            self.ui.add_field_if_exists(
                embed,
                "👥 Members",
                member_stats,
                True
            )

            # Channel Stats
            channel_stats = (
                f"Categories: {len(guild.categories):,}\n"
                f"Text: {len(guild.text_channels):,}\n"
                f"Voice: {len(guild.voice_channels):,}"
            )
            self.ui.add_field_if_exists(
                embed,
                "📂 Channels",
                channel_stats,
                True
            )

            # Role Info
            roles = guild.roles[1:]  # Exclude @everyone
            role_stats = (
                f"Count: {len(roles):,}\n"
                f"Highest: {guild.roles[-1].mention if roles else 'None'}"
            )
            self.ui.add_field_if_exists(
                embed,
                "🎭 Roles",
                role_stats,
                True
            )

            # Boost Status
            boost_stats = (
                f"Level: {guild.premium_tier}\n"
                f"Boosts: {guild.premium_subscription_count or 0}\n"
                f"Boosters: {len(guild.premium_subscribers):,}"
            )
            self.ui.add_field_if_exists(
                embed,
                "⭐ Server Boost",
                boost_stats,
                True
            )

            # Features
            if guild.features:
                features_str = "\n".join(f"• {feature.replace('_', ' ').title()}" 
                                       for feature in guild.features)
                self.ui.add_field_if_exists(
                    embed,
                    "✨ Features",
                    features_str,
                    False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Server info viewed in {guild.name}")
        except Exception as e:
            logger.error(f"Error showing server info: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching server information.",
                    "Info"
                ),
                ephemeral=True
            )

    @app_commands.command(name="userinfo", description="Get details about a user")
    async def userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Displays detailed user information"""
        try:
            member = member or interaction.user
            
            embed = self.ui.info_embed(
                f"{member.display_name}'s Information",
                f"User ID: {member.id}",
                "Info"
            )

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

            # Account Info
            user_info = (
                f"Created: <t:{int(member.created_at.timestamp())}:R>\n"
                f"Joined: <t:{int(member.joined_at.timestamp())}:R>\n"
                f"Bot: {'Yes' if member.bot else 'No'}"
            )
            self.ui.add_field_if_exists(
                embed,
                "👤 User Info",
                user_info,
                False
            )

            # Roles
            roles = member.roles[1:]  # Exclude @everyone
            if roles:
                role_list = " ".join([role.mention for role in reversed(roles)])
                self.ui.add_field_if_exists(
                    embed,
                    f"🎭 Roles [{len(roles)}]",
                    role_list or "None",
                    False
                )

            # Permissions
            key_perms = []
            if member.guild_permissions.administrator:
                key_perms.append("Administrator")
            else:
                perm_map = {
                    "manage_guild": "Manage Server",
                    "ban_members": "Ban Members",
                    "kick_members": "Kick Members",
                    "manage_channels": "Manage Channels",
                    "manage_messages": "Manage Messages",
                    "manage_roles": "Manage Roles",
                    "manage_webhooks": "Manage Webhooks",
                    "mention_everyone": "Mention Everyone"
                }
                for perm, name in perm_map.items():
                    if getattr(member.guild_permissions, perm):
                        key_perms.append(name)

            if key_perms:
                self.ui.add_field_if_exists(
                    embed,
                    "🔑 Key Permissions",
                    "\n".join(f"• {perm}" for perm in key_perms),
                    False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"User info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in userinfo command: {e}")
            await interaction.response.send_message("❌ An error occurred while fetching user info.", ephemeral=True)

    @app_commands.command(name="botinfo", description="Get details about onWhisper")
    async def botinfo(self, interaction: discord.Interaction):
        """Displays comprehensive bot information"""
        try:
            embed = discord.Embed(
                title="🤖 Bot Info: onWhisper",
                description="A versatile Discord bot with leveling, autorole, and analytics features.",
                color=discord.Color.blue()
            )

            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

            # Version and General Info
            version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.txt")
            try:
                with open(version_path, "r") as f:
                    version = f.read().strip()
            except:
                version = "1.0.0"  # Default version if file not found

            general_info = (
                f"Version: {version}\n"
                f"Python: {platform.python_version()}\n"
                f"Discord.py: {discord.__version__}\n"
                f"Servers: {len(self.bot.guilds):,}"
            )
            embed.add_field(
                name="📊 General",
                value=f"```{general_info}```",
                inline=False
            )

            # System Info
            process = psutil.Process()
            with process.oneshot():
                memory_usage = process.memory_info().rss
                cpu_percent = process.cpu_percent(interval=0.1)
                thread_count = process.num_threads()

            system_info = (
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory: {get_size(memory_usage)}\n"
                f"Threads: {thread_count}\n"
                f"Platform: {platform.system()} {platform.release()}"
            )
            embed.add_field(
                name="🖥️ System",
                value=f"```{system_info}```",
                inline=False
            )

            # Links and Support
            links_info = (
                "Developer: @og.kpnworld\n"
                "Support: [Discord Server](https://discord.gg/DAJVS99yMq)\n"
                "GitHub: [Repository](https://github.com/KpnWorld/onWhisper-Bot)\n"
                "Invite: [Add to Server](https://discord.com/oauth2/authorize?client_id=1316917918239293543)"
            )
            embed.add_field(
                name="🔗 Links",
                value=links_info,
                inline=False
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Bot info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in botinfo command: {e}")
            await interaction.response.send_message("❌ An error occurred while fetching bot info.", ephemeral=True)

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Shows all available commands and their descriptions"""
        try:
            # Main help embed
            embed = discord.Embed(
                title="📚 onWhisper Help Menu",
                description=(
                    "A versatile Discord bot with leveling, verification, and role management features.\n"
                    "All commands use `/` slash command format."
                ),
                color=discord.Color.blue()
            )

            # Info & Utility Commands
            info_commands = (
                "`/help` • Show this help menu\n"
                "`/ping` • Check bot's latency\n"
                "`/uptime` • Check bot's uptime\n"
                "`/botinfo` • View bot information\n"
                "`/serverinfo` • View server details\n"
                "`/userinfo [user]` • View user details\n"
                "`/guildstats [timeframe]` • View server statistics (Admin)"
            )
            embed.add_field(
                name="ℹ️ Information",
                value=info_commands,
                inline=False
            )

            # Leveling System Commands
            leveling_commands = (
                "`/level [user]` • View level progress\n"
                "`/leaderboard` • View XP rankings\n"
                "`/levelconfig` • View level settings (Admin)\n"
                "`/setlevelrole` • Set level role rewards (Admin)\n"
                "`/deletelevelrole` • Remove level roles (Admin)\n"
                "`/setcooldown` • Set XP cooldown (Admin)\n"
                "`/setxprange` • Set XP gain range (Admin)"
            )
            embed.add_field(
                name="📊 Leveling System",
                value=leveling_commands,
                inline=False
            )

            # Role Management Commands
            role_commands = (
                "`/setautorole` • Set auto-roles for new members (Admin)\n"
                "`/removeautorole` • Disable auto-roles (Admin)\n"
                "`/reactrole` • Create reaction roles (Admin)\n"
                "`/removereactrole` • Remove reaction roles (Admin)\n"
                "`/listreactroles` • List all reaction roles (Admin)\n"
                "`/massrole` • Add role to all members (Admin)"
            )
            embed.add_field(
                name="👥 Role Management",
                value=role_commands,
                inline=False
            )

            # Verification System Commands
            verify_commands = (
                "`/setupverification` • Set up verification (Admin)\n"
                "`/disableverification` • Disable verification (Admin)\n"
                "`/verify` • Start verification process"
            )
            embed.add_field(
                name="✅ Verification System",
                value=verify_commands,
                inline=False
            )

            # Command Usage Notes
            notes = (
                "**Command Requirements:**\n"
                "• (Admin) - Requires administrator permissions\n"
                "• [optional] - Optional command parameters\n"
                "\n"
                "**Need Help?**\n"
                "• Join our [Support Server](https://discord.gg/DAJVS99yMq)\n"
                "• Contact: `@og.kpnworld`"
            )
            embed.add_field(
                name="📝 Additional Information",
                value=notes,
                inline=False
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Help command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching help menu.",
                ephemeral=True
            )

    @app_commands.command(name="guildstats", description="View statistics for this server")
    @app_commands.default_permissions(administrator=True)
    async def guildstats(self, interaction: discord.Interaction, timeframe: Literal["day", "week", "month"] = "week"):
        """View detailed statistics for the current guild"""
        try:
            await interaction.response.defer()

            days_map = {"day": 1, "week": 7, "month": 30}
            days = days_map[timeframe]

            async with self.db.transaction():
                # Get guild metrics with improved query efficiency
                metrics = await self.db.fetchone("""
                    SELECT 
                        ROUND(AVG(CAST(member_count AS FLOAT)), 0) as avg_members,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT metric_id) as data_points,
                        ROUND(AVG(CAST(active_users AS FLOAT)), 0) as avg_active,
                        AVG(bot_latency) as avg_latency
                    FROM guild_metrics
                    WHERE guild_id = ? 
                    AND timestamp >= datetime('now', ?)
                """, (interaction.guild_id, f'-{days} days'))

            embed = self.ui.info_embed(
                f"Server Statistics ({timeframe})",
                f"Statistics for {interaction.guild.name}",
                "Info"
            )

            # Activity metrics
            stats_text = (
                f"Average Members: {int(metrics['avg_members']):,}\n"
                f"Total Messages: {int(metrics['total_messages']):,}\n"
                f"Active Users (avg): {int(metrics['avg_active']):,}\n"
                f"Data Points: {int(metrics['data_points']):,}\n"
                f"Avg Latency: {metrics['avg_latency']:.1f}ms"
            )
            embed.add_field(
                name="📈 Activity Metrics",
                value=f"```\n{stats_text}\n```",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Guild stats viewed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in guildstats command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching guild stats.", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Info(bot))
