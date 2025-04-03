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

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use bot's database instance
        self.start_time = time.time()
        logger.info("Info cog initialized")

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency and API response time"""
        try:
            start_time = time.time()
            await interaction.response.defer()
            end_time = time.time()

            bot_latency = round((end_time - start_time) * 1000, 2)
            websocket_latency = round(self.bot.latency * 1000, 2)

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
            uptime_seconds = round(time.time() - self.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60

            process = psutil.Process()
            memory_usage = process.memory_info().rss
            cpu_percent = process.cpu_percent(interval=0.1)

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

            await interaction.response.send_message(embed=embed)
            logger.info(f"Uptime command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in uptime command: {e}")
            await interaction.response.send_message("❌ An error occurred while fetching uptime.", ephemeral=True)

    @app_commands.command(name="serverinfo", description="Get details about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Displays comprehensive server information"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
                return

            # Collect role statistics
            roles = guild.roles[1:]  # Exclude @everyone
            bot_count = len([m for m in guild.members if m.bot])
            channel_categories = {
                "Text": len([c for c in guild.channels if isinstance(c, discord.TextChannel)]),
                "Voice": len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)]),
                "Forum": len([c for c in guild.channels if isinstance(c, discord.ForumChannel)]),
                "Stage": len([c for c in guild.channels if isinstance(c, discord.StageChannel)]),
            }

            embed = discord.Embed(
                title=f"🏠 Server Info: {guild.name}",
                description=guild.description or "No description set",
                color=discord.Color.blue()
            )

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # General Info
            general_info = (
                f"ID: {guild.id}\n"
                f"Owner: {guild.owner.mention}\n"
                f"Created: {format_dt(guild.created_at)}\n"
                f"Region: {str(guild.preferred_locale)}"
            )
            embed.add_field(
                name="📌 General",
                value=f"```{general_info}```",
                inline=False
            )

            # Member Stats
            member_info = (
                f"Total: {guild.member_count:,}\n"
                f"Humans: {guild.member_count - bot_count:,}\n"
                f"Bots: {bot_count:,}\n"
                f"Online: {len([m for m in guild.members if m.status != discord.Status.offline]):,}"
            )
            embed.add_field(
                name="👥 Members",
                value=f"```{member_info}```",
                inline=True
            )

            # Channel Stats
            channel_info = "\n".join(f"{k}: {v:,}" for k, v in channel_categories.items() if v > 0)
            embed.add_field(
                name="📢 Channels",
                value=f"```{channel_info}```",
                inline=True
            )

            # Features and Boost Status
            if guild.features:
                features_str = ", ".join(f.replace('_', ' ').title() for f in guild.features)
                embed.add_field(
                    name="✨ Features",
                    value=f"```{features_str}```",
                    inline=False
                )

            if guild.premium_subscription_count > 0:
                boost_info = (
                    f"Level: {guild.premium_tier}\n"
                    f"Boosts: {guild.premium_subscription_count:,}"
                )
                embed.add_field(
                    name="📈 Boost Status",
                    value=f"```{boost_info}```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Server info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in serverinfo command: {e}")
            await interaction.response.send_message("❌ An error occurred while fetching server info.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Get details about a user")
    async def userinfo(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Displays detailed user information"""
        try:
            user = user or interaction.user
            roles = [role for role in user.roles if role.name != "@everyone"]
            
            embed = discord.Embed(
                title=f"👤 User Info: {user.name}",
                color=user.color if user.color != discord.Color.default() else discord.Color.blue()
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            # User Details
            user_info = (
                f"ID: {user.id}\n"
                f"Created: {format_dt(user.created_at)}\n"
                f"Joined: {format_dt(user.joined_at) if hasattr(user, 'joined_at') else 'N/A'}\n"
                f"Bot: {'Yes' if user.bot else 'No'}"
            )
            embed.add_field(
                name="📋 Details",
                value=f"```{user_info}```",
                inline=False
            )

            # Status and Activity
            status_emoji = {
                "online": "🟢",
                "idle": "🟡",
                "dnd": "🔴",
                "offline": "⚫"
            }

            current_status = str(user.status)
            status_info = (
                f"Status: {status_emoji.get(current_status, '⚫')} {current_status.title()}\n"
                f"Mobile: {'Yes' if user.is_on_mobile() else 'No'}\n"
                f"Activity: {user.activity.name if user.activity else 'None'}"
            )
            embed.add_field(
                name="🎮 Presence",
                value=f"```{status_info}```",
                inline=True
            )

            # Roles
            if roles:
                role_info = (
                    f"Count: {len(roles)}\n"
                    f"Highest: {user.top_role.name}\n"
                    f"Color: {str(user.color) if user.color != discord.Color.default() else 'None'}"
                )
                embed.add_field(
                    name="🎭 Roles",
                    value=f"```{role_info}```",
                    inline=True
                )

            # Permissions
            if user.guild_permissions:
                key_perms = []
                if user.guild_permissions.administrator:
                    key_perms.append("Administrator")
                else:
                    if user.guild_permissions.manage_guild: key_perms.append("Manage Server")
                    if user.guild_permissions.manage_roles: key_perms.append("Manage Roles")
                    if user.guild_permissions.manage_channels: key_perms.append("Manage Channels")
                    if user.guild_permissions.manage_messages: key_perms.append("Manage Messages")
                    if user.guild_permissions.kick_members: key_perms.append("Kick Members")
                    if user.guild_permissions.ban_members: key_perms.append("Ban Members")

                if key_perms:
                    embed.add_field(
                        name="🔑 Key Permissions",
                        value=f"```{', '.join(key_perms)}```",
                        inline=False
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
                title=f"📊 Server Statistics ({timeframe})",
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
                value=f"```{stats_text}```",
                inline=False
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Guild stats command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in guildstats command: {e}")
            await interaction.response.send_message("❌ An error occurred while fetching guild stats.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
