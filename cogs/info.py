import discord
from discord.ext import commands
from discord import app_commands
import time
import logging
import os
import psutil
import platform
from datetime import datetime
from typing import Optional

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
                "Support: [Discord Server](https://discord.gg/64bGK2SQpX)\n"
                "GitHub: [Repository](https://github.com/your/repo)\n"
                "Invite: [Add to Server](https://discord.com/oauth2/authorize)"
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
            embed = discord.Embed(
                title="📚 onWhisper Help Menu",
                description="Here are all available commands, organized by category:",
                color=discord.Color.blue()
            )

            # Info & Utility Commands
            info_commands = (
                "`/help` • Show this help menu\n"
                "`/ping` • Check bot's latency\n"
                "`/uptime` • Check bot's uptime and system stats\n"
                "`/botinfo` • Get detailed information about the bot\n"
                "`/serverinfo` • Get comprehensive server information\n"
                "`/userinfo [user]` • Get detailed user information"
            )
            embed.add_field(
                name="ℹ️ Information & Utility",
                value=info_commands,
                inline=False
            )

            # Leveling System Commands
            leveling_commands = (
                "`/level [user]` • Check your or another user's level\n"
                "`/leaderboard` • View the server's XP leaderboard\n"
                "`/levelconfig` • View leveling system settings (Admin)\n"
                "`/setlevelrole` • Configure level-up role rewards (Admin)\n"
                "`/deletelevelrole` • Remove a level role reward (Admin)\n"
                "`/setcooldown` • Set XP gain cooldown (Admin)\n"
                "`/setxprange` • Configure min/max XP per message (Admin)"
            )
            embed.add_field(
                name="📊 Leveling System",
                value=leveling_commands,
                inline=False
            )

            # Role Management Commands
            role_commands = (
                "`/setautorole` • Configure automatic roles for new members/bots (Admin)\n"
                "`/removeautorole` • Disable autorole system (Admin)\n"
                "`/massrole` • Add a role to all members (Admin)"
            )
            embed.add_field(
                name="👥 Role Management",
                value=role_commands,
                inline=False
            )

            # Statistics & Analytics Commands
            stats_commands = (
                "`/stats [timeframe]` • View global bot statistics (Owner)\n"
                "`/guildstats [timeframe]` • View detailed server statistics (Admin)\n"
                "`/viewguild [guild_id]` • View detailed guild configuration (Admin)"
            )
            embed.add_field(
                name="📈 Statistics & Analytics",
                value=stats_commands,
                inline=False
            )

            # Command Usage Notes
            notes = (
                "**Note:**\n"
                "• Commands marked with (Admin) require administrator permissions\n"
                "• Commands marked with (Owner) are restricted to bot owner\n"
                "• Optional parameters are shown in [brackets]\n"
                "• Use </help:ID> to see this menu again"
            )
            embed.add_field(
                name="📝 Additional Information",
                value=notes,
                inline=False
            )

            # Support Information
            support_info = (
                "**Need Help?**\n"
                "• Join our [Support Server](https://discord.gg/DAJVS99yMq)\n"
                "• Report bugs to `@og.kpnworld`\n"
                "• View documentation on [GitHub](https://github.com/KpnWorld/onWhisper-Bot)"
            )
            embed.add_field(
                name="🔧 Support",
                value=support_info,
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

async def setup(bot):
    await bot.add_cog(Info(bot))
