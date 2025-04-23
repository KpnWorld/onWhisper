from sys import platform
import time
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import psutil
from utils.db_manager import DBManager
from utils.ui_manager import UIManager
import os
import platform
from typing import Union

def get_size(bytes: int) -> str:
    """Convert bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Increment guild stats when a member joins"""
        await self.db_manager.increment_stat(member.guild.id, "joins")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Increment guild stats when a member leaves"""
        await self.db_manager.increment_stat(member.guild.id, "leaves")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track messages for guild stats"""
        if message.author.bot or not message.guild:
            return
        await self.db_manager.increment_stat(message.guild.id, "messages")

    # =========================
    # 📊 Information Commands
    # =========================

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency"""
        try:
            latency = round(self.bot.latency * 1000)
            await self.ui_manager.send_response(
                interaction,
                title="🏓 Pong!",
                description="Current Bot Status",
                fields=[
                    {"name": "Latency", "value": f"{latency}ms", "inline": True}
                ],
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Ping Error",
                f"Failed to get latency: {str(e)}"
            )

    @app_commands.command(name="uptime", description="Check bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        """Check bot uptime"""
        uptime = datetime.utcnow() - datetime.fromtimestamp(self.bot.uptime)
        uptime_str = str(timedelta(seconds=int(uptime.total_seconds())))
        await self.ui_manager.send_embed(
            interaction,
            title="⏱️ Bot Uptime",
            description=f"The bot has been online for `{uptime_str}`.",
            command_type="User"
        )

    @app_commands.command(name="botinfo", description="Get details about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        """Displays comprehensive bot information"""
        try:
            embed = discord.Embed(
                title=f"🤖 Bot Info: {self.bot.user.name}",
                description="A versatile Discord bot with leveling, autorole, verification and reaction roles.",
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

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
            )

    @app_commands.command(name="serverinfo", description="Show server information")
    @app_commands.checks.has_permissions(administrator=True)
    async def serverinfo(self, interaction: discord.Interaction):
        """Show server information (Admins only)"""
        try:
            guild = interaction.guild
            await self.ui_manager.send_response(
                interaction,
                title=f"📊 Server Information: {guild.name}",
                description=f"Statistics for {guild.name}",
                fields=[
                    {"name": "Members", "value": str(guild.member_count), "inline": True},
                    {"name": "Online", "value": str(sum(1 for m in guild.members if m.status != discord.Status.offline)), "inline": True},
                    {"name": "Text Channels", "value": str(len(guild.text_channels)), "inline": True},
                    {"name": "Voice Channels", "value": str(len(guild.voice_channels)), "inline": True},
                    {"name": "Roles", "value": str(len(guild.roles)), "inline": True}
                ],
                command_type="Administrator"
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Server Info Error",
                f"Failed to get server info: {str(e)}"
            )

    @app_commands.command(name="userinfo", description="Display user information")
    async def userinfo(self, interaction: discord.Interaction, user: discord.User = None):
        """Display user information"""
        user = user or interaction.user
        embed = self.ui_manager.create_embed(
            title=f"👤 {user.name}'s Information",
            description=f"Here are the details for {user.name}:",
            color=discord.Color.purple()
        )
        embed.add_field(name="User ID", value=user.id, inline=False)
        embed.add_field(name="Joined Discord", value=user.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
        embed.add_field(name="Joined Server", value=user.joined_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'joined_at') else "N/A", inline=False)
        embed.add_field(name="Status", value=str(user.status), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Show information about a specific role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Show information about a specific role"""
        embed = self.ui_manager.create_embed(
            title=f"🔹 Role Information: {role.name}",
            description=f"Details for the role `{role.name}`:",
            color=role.color if role.color.value else discord.Color.blurple()
        )
        embed.add_field(name="Role ID", value=role.id, inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Created At", value=role.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        embed.add_field(name="Member Count", value=str(len(role.members)), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the server XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the server leaderboard of top XP earners"""
        try:
            leaderboard_data = await self.db_manager.get_leaderboard(interaction.guild.id)

            if not leaderboard_data:
                await self.ui_manager.send_embed(
                    interaction,
                    title="No XP Data Yet",
                    description="There are no users with XP data yet. Chat more to get on the leaderboard!",
                    command_type="User"
                )
                return

            leaderboard = "\n".join(
                [f"{rank + 1}. <@{row['user_id']}> - Level: {row['level']} | XP: {row['xp']}" for rank, row in enumerate(leaderboard_data)]
            )

            await self.ui_manager.send_embed(
                interaction,
                title="🏆 Server Leaderboard",
                description=f"**Top 10 Users by XP:**\n{leaderboard}",
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
            )

    # =========================
    # 📚 Help Commands
    # =========================

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Shows all available commands and their descriptions"""
        try:
            # Main help embed
            embed = discord.Embed(
                title="📚 Bot Help Menu",
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
                "`/serverinfo` • View server details (Admin)\n"
                "`/userinfo [user]` • View user details\n"
                "`/roleinfo [role]` • View role details"
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
                "`/set-xp-rate` • Set XP per message (Admin)\n"
                "`/set-xp-cooldown` • Set XP cooldown (Admin)\n"
                "`/set-level-role` • Set level role rewards (Admin)"
            )
            embed.add_field(
                name="📊 Leveling System",
                value=leveling_commands,
                inline=False
            )

            # Role Management Commands
            role_commands = (
                "`/setautorole` • Set auto role (Admin)\n"
                "`/listautoroles` • List auto roles (Admin)\n"
                "`/removeautorole` • Remove auto role (Admin)\n"
                "`/autorole` • View auto role status\n"
                "`/bind_reaction_role` • Create reaction role (Admin)\n"
                "`/reaction_stats` • View reaction statistics"
            )
            embed.add_field(
                name="👥 Role Management",
                value=role_commands,
                inline=False
            )

            # Verification System Commands
            verify_commands = (
                "`/set-verification` • Configure verification (Admin)\n"
                "`/verify [method]` • Start verification process"
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
                "• Use `/help` for command list\n"
                "• Required permission: Manage Server"
            )
            embed.add_field(
                name="📝 Additional Information",
                value=notes,
                inline=False
            )

            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="Error",
                description=f"An error occurred while fetching help menu: {str(e)}",
                command_type="User",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Info(bot))
