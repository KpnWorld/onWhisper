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
                title="Ping Status",
                description="Current bot network status",
                command_type="ping",
                fields=[
                    {"name": "Latency", "value": f"{latency}ms", "inline": True},
                    {"name": "Status", "value": "Online", "inline": True}
                ]
            )
        except Exception as e:
            await self.ui_manager.send_error(interaction, "Ping Check Failed", str(e))

    @app_commands.command(name="uptime", description="Check bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        """Check bot uptime"""
        try:
            uptime_delta = datetime.utcnow() - self.bot.start_time
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime_parts = []
            if days > 0:
                uptime_parts.append(f"{days} days")
            if hours > 0:
                uptime_parts.append(f"{hours} hours")
            if minutes > 0:
                uptime_parts.append(f"{minutes} minutes")
            if seconds > 0 or not uptime_parts:
                uptime_parts.append(f"{seconds} seconds")
                
            uptime_str = ", ".join(uptime_parts)
            
            await self.ui_manager.send_response(
                interaction,
                title="Bot Uptime",
                description="Current bot operation status",
                command_type="uptime",
                fields=[
                    {"name": "Online Since", "value": f"<t:{int(self.bot.start_time.timestamp())}:F>", "inline": True},
                    {"name": "Total Uptime", "value": uptime_str, "inline": True}
                ]
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Uptime Error",
                str(e)
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

    @app_commands.command(name="userinfo")
    async def userinfo(self, interaction: discord.Interaction, user: discord.User = None):
        """Display user information"""
        try:
            target = user or interaction.user
            
            # Format account information
            account_info = {
                "📅 Account Created": self.ui_manager.format_timestamp(target.created_at, "F"),
                "📆 Server Joined": self.ui_manager.format_timestamp(target.joined_at, "F") if hasattr(target, 'joined_at') else "Not Found",
                "🆔 User ID": target.id,
                "🎭 Status": str(target.status).title() if hasattr(target, 'status') else "Unknown"
            }

            # Get user roles if member
            roles = []
            if isinstance(target, discord.Member):
                roles = [role.mention for role in reversed(target.roles[1:])]

            await self.ui_manager.send_response(
                interaction,
                title=f"User Information",
                description=f"Viewing details for {target.mention}",
                command_type="user",
                fields=[
                    {"name": "📋 Account Information", "value": account_info, "inline": False},
                    {"name": "🏷️ Roles", "value": " ".join(roles) or "No Roles", "inline": False}
                ],
                thumbnail_url=target.display_avatar.url
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "User Info Error",
                str(e)
            )

    @app_commands.command()
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        try:
            await interaction.response.defer()
            
            role_info = {
                "ID": role.id,
                "Created": f"<t:{int(role.created_at.timestamp())}:F>",
                "Color": str(role.color),
                "Position": role.position,
                "Members": len(role.members),
                "Mentionable": "Yes" if role.mentionable else "No",
                "Hoisted": "Yes" if role.hoist else "No"
            }

            await self.ui_manager.send_response(
                interaction,
                title=f"Role Information: {role.name}",
                description=f"Details about role {role.mention}",
                command_type="roles",
                fields=[
                    {"name": "Role Details", "value": role_info, "inline": False}
                ],
                thumbnail_url=role.guild.icon.url if role.guild.icon else None
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Role Info Error",
                str(e),
                ephemeral=True
            )

    @app_commands.command(name="leaderboard", description="Show the server XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the server leaderboard of top XP earners"""
        try:
            leaderboard_data = await self.db_manager.get_leaderboard(interaction.guild.id)

            if not leaderboard_data:
                await self.ui_manager.send_embed(
                    interaction,
                    title="No XP Data Yet",
                    description="```\nThere are no users with XP data yet. Chat more to get on the leaderboard!\n```",
                    command_type="User"
                )
                return

            leaderboard_text = "\n".join(
                [f"{rank + 1}. {row['user_id']} - Level {row['level']} | {row['xp']:,} XP" 
                 for rank, row in enumerate(leaderboard_data)]
            )

            await self.ui_manager.send_embed(
                interaction,
                title="🏆 Server Leaderboard",
                description=f"**Top 10 Users by XP:**\n```\n{leaderboard_text}\n```",
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="❌ Error",
                description=f"```\nAn error occurred: {e}\n```",
                command_type="User"
            )

    # =========================
    # 📚 Help Commands
    # =========================

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Shows all available commands and their descriptions"""
        try:
            embed = discord.Embed(
                title="📚 Bot Help Menu",
                description="A versatile Discord bot with leveling, verification, and role management features.\nAll commands use `/` slash command format.",
                color=discord.Color.blue()
            )

            info_commands = (
                "help - Show this help menu\n"
                "ping - Check bot's latency\n"
                "uptime - Check bot's uptime\n"
                "botinfo - View bot information\n"
                "serverinfo - View server details (Admin)\n"
                "userinfo [user] - View user details\n"
                "roleinfo [role] - View role details"
            )
            embed.add_field(
                name="ℹ️ Information",
                value=f"```{info_commands}```",
                inline=False
            )

            leveling_commands = (
                "level [user] - View level progress\n"
                "leaderboard - View XP rankings\n"
                "set-xp-rate - Set XP per message (Admin)\n"
                "set-xp-cooldown - Set XP cooldown (Admin)\n"
                "set-level-role - Set level role rewards (Admin)"
            )
            embed.add_field(
                name="📊 Leveling System",
                value=f"```{leveling_commands}```",
                inline=False
            )

            role_commands = (
                "setautorole - Set auto role (Admin)\n"
                "listautoroles - List auto roles (Admin)\n"
                "removeautorole - Remove auto role (Admin)\n"
                "autorole - View auto role status\n"
                "bind_reaction_role - Create reaction role (Admin)\n"
                "reaction_stats - View reaction statistics"
            )
            embed.add_field(
                name="👥 Role Management",
                value=f"```{role_commands}```",
                inline=False
            )

            verify_commands = (
                "set-verification - Configure verification (Admin)\n"
                "verify [method] - Start verification process"
            )
            embed.add_field(
                name="✅ Verification System",
                value=f"```{verify_commands}```",
                inline=False
            )

            notes = (
                "Command Requirements:\n"
                "• (Admin) - Requires administrator permissions\n"
                "• [optional] - Optional command parameters\n"
                "\n"
                "Need Help?\n"
                "• Use /help for command list\n"
                "• Required permission: Manage Server"
            )
            embed.add_field(
                name="📝 Additional Information",
                value=f"```{notes}```",
                inline=False
            )

            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="Error",
                description=f"```\nAn error occurred while fetching help menu: {str(e)}\n```",
                command_type="User",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Info(bot))
