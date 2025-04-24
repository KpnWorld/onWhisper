from sys import platform
import time
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import psutil
from utils.db_manager import DBManager
import os
import platform
from typing import Optional, Union

def get_size(bytes: int) -> str:
    """Convert bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"

class Info(commands.Cog):
    """Information commands for the bot"""
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self._cooldowns = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)

    def _check_cooldown(self, interaction: discord.Interaction) -> Optional[int]:
        """Check if user is on cooldown. Returns remaining time if on cooldown."""
        bucket = self._cooldowns.get_bucket(interaction)
        retry_after = bucket.update_rate_limit()
        return retry_after if retry_after else None

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

    @commands.slash_command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Check the bot's current latency and connection status"""
        try:
            if retry_after := self._check_cooldown(interaction):
                embed = self.bot.create_embed(
                    "Cooldown Active",
                    f"Please wait {retry_after:.1f}s before using this command again.",
                    command_type="User"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            latency = round(self.bot.latency * 1000)
            status_emoji = "🟢" if latency < 200 else "🟡" if latency < 500 else "🔴"
            
            embed = self.bot.create_embed(
                f"{status_emoji} Bot Latency",
                f"Latency: {latency}ms\nStatus: Online",
                command_type="User"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="uptime", description="Check bot uptime")
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
            
            description = (
                f"Online Since: <t:{int(self.bot.start_time.timestamp())}:F>\n"
                f"Total Uptime: {uptime_str}"
            )
            
            embed = self.bot.create_embed(
                "Bot Uptime",
                description,
                command_type="User"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="botinfo", description="Get detailed information about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        """Display comprehensive information about the bot"""
        try:
            if retry_after := self._check_cooldown(interaction):
                embed = self.bot.create_embed(
                    "Cooldown Active",
                    f"Please wait {retry_after:.1f}s before using this command again.",
                    command_type="User"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Get system info
            process = psutil.Process()
            with process.oneshot():
                memory_usage = process.memory_info().rss
                cpu_percent = process.cpu_percent(interval=0.1)
                thread_count = process.num_threads()

            # Get version info
            version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.txt")
            try:
                with open(version_path, "r") as f:
                    version = f.read().strip()
            except:
                version = "1.0.0"
            
            description = (
                f"Version: {version}\n"
                f"Python: {platform.python_version()}\n"
                f"Py-cord: {discord.__version__}\n"
                f"Servers: {len(self.bot.guilds):,}\n"
                f"\n"
                f"System Information:\n"
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory: {get_size(memory_usage)}\n"
                f"Threads: {thread_count}\n"
                f"Platform: {platform.system()} {platform.release()}"
            )
            
            embed = self.bot.create_embed(
                f"Bot Information: {self.bot.user.name}",
                description,
                command_type="User"
            )
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="serverinfo", description="Show detailed server information")
    @commands.has_permissions(administrator=True)
    async def serverinfo(self, interaction: discord.Interaction):
        """Display detailed information about the current server (Admin only)"""
        try:
            if retry_after := self._check_cooldown(interaction):
                embed = self.bot.create_embed(
                    "Cooldown Active",
                    f"Please wait {retry_after:.1f}s before using this command again.",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            guild = interaction.guild
            created_timestamp = int(guild.created_at.timestamp())
            total_members = guild.member_count
            online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
            bot_count = sum(1 for m in guild.members if m.bot)
            
            description = (
                f"Owner: {guild.owner.mention if guild.owner else 'Unknown'}\n"
                f"Created: <t:{created_timestamp}:F>\n"
                f"Age: <t:{created_timestamp}:R>\n"
                f"\n"
                f"Members:\n"
                f"Total: {total_members:,}\n"
                f"Humans: {total_members - bot_count:,}\n"
                f"Bots: {bot_count:,}\n"
                f"Online: {online_members:,}\n"
                f"\n"
                f"Channels:\n"
                f"Text: {len(guild.text_channels)}\n"
                f"Voice: {len(guild.voice_channels)}\n"
                f"Categories: {len(guild.categories)}\n"
                f"Forums: {len([c for c in guild.channels if isinstance(c, discord.ForumChannel)])}\n"
                f"\n"
                f"Server Boost Status:\n"
                f"Level: {guild.premium_tier}\n"
                f"Boosts: {guild.premium_subscription_count:,}\n"
                f"Roles: {len(guild.roles):,}"
            )
            
            embed = self.bot.create_embed(
                f"Server Information: {guild.name}",
                description,
                command_type="Administrative"
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="userinfo", description="Show user information")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        """Display information about a user"""
        try:
            target = user or interaction.user
            
            # Format account information with consistent timestamp usage
            created_timestamp = int(target.created_at.timestamp())
            joined_timestamp = int(target.joined_at.timestamp()) if hasattr(target, 'joined_at') else None
            
            description = (
                f"Account Created: <t:{created_timestamp}:F>\n"
                f"Server Joined: {f'<t:{joined_timestamp}:F>' if joined_timestamp else 'Not Found'}\n"
                f"Account Age: <t:{created_timestamp}:R>\n"
                f"User ID: {target.id}\n"
                f"Status: {str(target.status).title() if hasattr(target, 'status') else 'Unknown'}\n"
            )
            
            # Add roles if member
            if isinstance(target, discord.Member) and target.roles[1:]:  # Exclude @everyone
                roles = [role.mention for role in reversed(target.roles[1:])]
                description += f"\nRoles: {' '.join(roles)}"
            else:
                description += "\nRoles: No Roles"
            
            embed = self.bot.create_embed(
                f"User Information: {target.display_name}",
                description,
                command_type="User"
            )
            
            if target.display_avatar:
                embed.set_thumbnail(url=target.display_avatar.url)
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="roleinfo", description="Show role information")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Display information about a role"""
        try:
            created_timestamp = int(role.created_at.timestamp())
            
            description = (
                f"Role ID: {role.id}\n"
                f"Created: <t:{created_timestamp}:F>\n"
                f"Age: <t:{created_timestamp}:R>\n"
                f"Color: {str(role.color)}\n"
                f"Position: {role.position}\n"
                f"Members: {len(role.members)}\n"
                f"Mentionable: {'Yes' if role.mentionable else 'No'}\n"
                f"Hoisted: {'Yes' if role.hoist else 'No'}"
            )
            
            embed = self.bot.create_embed(
                f"Role Information: {role.name}",
                description,
                command_type="User"
            )
            
            if role.guild.icon:
                embed.set_thumbnail(url=role.guild.icon.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="leaderboard", description="Show the server XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the server leaderboard of top XP earners"""
        try:
            leaderboard_data = await self.db_manager.get_leaderboard(interaction.guild.id)

            if not leaderboard_data:
                embed = self.bot.create_embed(
                    "Server Leaderboard",
                    "There are no users with XP data yet. Chat more to get on the leaderboard!",
                    command_type="User"
                )
                await interaction.response.send_message(embed=embed)
                return

            leaderboard_text = "\n".join(
                [f"{rank + 1}. <@{row[0]}> - Level {row[1]} | {row[2]:,} XP" 
                 for rank, row in enumerate(leaderboard_data)]
            )

            embed = self.bot.create_embed(
                "🏆 Server Leaderboard",
                leaderboard_text,
                command_type="User"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction, category: str = None):
        """Shows all available commands and their descriptions"""
        try:
            categories = {
                "info": {
                    "name": "ℹ️ Information",
                    "commands": [
                        ("/help [category]", "Show this help menu"),
                        ("/ping", "Check bot's latency"),
                        ("/uptime", "Check bot's uptime"),
                        ("/botinfo", "View detailed bot information"),
                        ("/serverinfo", "View server details (Admin)"),
                        ("/userinfo [user]", "View user details"),
                        ("/roleinfo [role]", "View role details")
                    ]
                },
                "leveling": {
                    "name": "📊 Leveling System",
                    "commands": [
                        ("/level [user]", "View level progress"),
                        ("/leaderboard", "View XP rankings"),
                        ("/set-xp-rate [amount]", "Set XP per message (Admin)"),
                        ("/set-xp-cooldown [seconds]", "Set XP cooldown (Admin)")
                    ]
                },
                "tickets": {
                    "name": "🎫 Ticket System",
                    "commands": [
                        ("/ticket [reason]", "Create a support ticket"),
                        ("/close-ticket", "Close your current ticket"),
                        ("/add-to-ticket [user]", "Add user to ticket (Staff)"),
                        ("/remove-from-ticket [user]", "Remove user from ticket (Staff)")
                    ]
                },
                "roles": {
                    "name": "👥 Role Management",
                    "commands": [
                        ("/setautorole [role]", "Set automatic role for new members (Admin)"),
                        ("/removeautorole", "Disable automatic role (Admin)"),
                        ("/bind_reaction_role [msg] [emoji] [role]", "Create reaction role (Admin)")
                    ]
                },
                "logging": {
                    "name": "📝 Logging",
                    "commands": [
                        ("/setlogchannel [channel]", "Set logging channel (Admin)")
                    ]
                },
                "moderation": {
                    "name": "🛡️ Moderation",
                    "commands": [
                        ("/kick [user] [reason]", "Kick a member"),
                        ("/ban [user] [reason] [days]", "Ban a member"),
                        ("/timeout [user] [duration] [reason]", "Timeout a member"),
                        ("/clear [amount] [user]", "Clear messages")
                    ]
                }
            }

            if category and category.lower() in categories:
                # Show specific category
                cat = categories[category.lower()]
                commands_list = "\n".join(f"{cmd} - {desc}" for cmd, desc in cat["commands"])
                
                embed = self.bot.create_embed(
                    f"{cat['name']} Commands",
                    commands_list,
                    command_type="User"
                )
                
            else:
                # Show all categories with sample commands
                description = "Use `/help [category]` to see detailed commands for each category.\n\n"
                
                for cat_id, cat in categories.items():
                    description += f"\n{cat['name']}:\n"
                    # Show first 2 commands as examples
                    for cmd, desc in cat["commands"][:2]:
                        description += f"{cmd} - {desc}\n"
                    if len(cat["commands"]) > 2:
                        description += "...and more\n"

                embed = self.bot.create_embed(
                    "📚 Help Menu",
                    description,
                    command_type="User"
                )

            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
