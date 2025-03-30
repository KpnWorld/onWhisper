import discord
from discord.ext import commands
from discord import app_commands
import time
import logging
import os

# Initialize logger
logger = logging.getLogger(__name__)

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.start_time = time.time()  # Store bot start time
        logger.info("Info cog initialized.")

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency and API response time."""
        try:
            start_time = time.time()
            await interaction.response.send_message("Pinging...")
            end_time = time.time()
            latency = round((end_time - start_time) * 1000, 2)

            embed = discord.Embed(title="🏓 Pong!", description=f"Latency: `{latency}ms`", color=discord.Color.green())
            await interaction.edit_original_response(embed=embed)
            logger.info(f"Ping command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await interaction.followup.send("An error occurred while processing your request.")

    @app_commands.command(name="uptime", description="Check how long the bot has been running.")
    async def uptime(self, interaction: discord.Interaction):
        """Returns bot uptime in human-readable format."""
        try:
            uptime_seconds = round(time.time() - self.bot.start_time)
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)

            uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

            embed = discord.Embed(title="⏳ Bot Uptime", description=f"Running for `{uptime_str}`", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)
            logger.info(f"Uptime command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in uptime command: {e}")
            await interaction.response.send_message("An error occurred while processing your request.")

    @app_commands.command(name="serverinfo", description="Get details about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        """Displays server information."""
        try:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("This command can only be used in a server.")
                return

            embed = discord.Embed(title=f"🏠 Server Info: {guild.name}", color=discord.Color.blue())
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            embed.add_field(name="📌 Server ID", value=guild.id, inline=False)
            embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=False)
            embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            embed.add_field(name="👥 Members", value=guild.member_count, inline=False)
            embed.add_field(name="🔖 Roles", value=len(guild.roles), inline=False)
            embed.add_field(name="📢 Channels", value=len(guild.channels), inline=False)

            await interaction.response.send_message(embed=embed)
            logger.info(f"Server info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in serverinfo command: {e}")
            await interaction.response.send_message("An error occurred while processing your request.")

    @app_commands.command(name="userinfo", description="Get details about a user.")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        """Displays user information."""
        try:
            user = user or interaction.user
            embed = discord.Embed(title=f"👤 User Info: {user.name}", color=discord.Color.green())
            embed.set_thumbnail(url=user.display_avatar.url)

            embed.add_field(name="🆔 User ID", value=user.id, inline=False)
            embed.add_field(name="🔖 Nickname", value=user.nick or "None", inline=False)
            embed.add_field(name="📅 Joined", value=user.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            embed.add_field(name="🎉 Account Created", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            embed.add_field(name="🔹 Roles", value=", ".join(role.mention for role in user.roles[1:]) or "None", inline=False)

            await interaction.response.send_message(embed=embed)
            logger.info(f"User info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in userinfo command: {e}")
            await interaction.response.send_message("An error occurred while processing your request.")

    @app_commands.command(name="botinfo", description="Get details about onWhisper.")
    async def botinfo(self, interaction: discord.Interaction):
        """Displays bot information including version and support details."""
        try:
            version_path = os.path.join(os.path.dirname(__file__), "..", "version.txt")
            with open(version_path, "r") as version_file:
                bot_version = version_file.read().strip()

            embed = discord.Embed(title="🤖 Bot Info: onWhisper", color=discord.Color.gold())
            embed.add_field(name="🔢 Version", value=bot_version, inline=False)
            embed.add_field(name="👤 Owner", value="@og.kpnworld", inline=False)
            embed.add_field(name="🔗 Support Server", value="[Join Here](https://discord.gg/64bGK2SQpX)", inline=False)
            embed.add_field(name="🖥️ Language", value="Python / discord.py", inline=False)

            await interaction.response.send_message(embed=embed)
            logger.info(f"Bot info command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in botinfo command: {e}")
            await interaction.response.send_message("An error occurred while processing your request.")

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Shows all available commands and their descriptions."""
        try:
            embed = discord.Embed(
                title="📚 onWhisper Help Menu",
                description="Here are all available commands:",
                color=discord.Color.blue()
            )

            # Info Commands
            info_commands = [
                ("🔍 /help", "Show this help menu"),
                ("🏓 /ping", "Check bot's latency"),
                ("⏳ /uptime", "Check bot's uptime"),
                ("🤖 /botinfo", "Get information about the bot"),
                ("👥 /serverinfo", "Get server information"),
                ("👤 /userinfo [user]", "Get user information (defaults to you)")
            ]

            # Leveling Commands
            leveling_commands = [
                ("📊 /level [user]", "Check your or another user's level"),
                ("🏆 /leaderboard", "View the top 10 users"),
                ("⚙️ /levelconfig", "View all leveling system settings (Admin)"),
                ("⚙️ /setlevelrole", "Set level-up role rewards (Admin)"),
                ("⏱️ /setcooldown", "Set XP gain cooldown time (Admin)"),
                ("💫 /setxprange", "Set min/max XP per message (Admin)")
            ]

            # AutoRole Commands
            autorole_commands = [
                ("⚙️ /setautorole", "Set automatic role for new members/bots (Admin)"),
                ("❌ /removeautorole", "Disable automatic role assignment (Admin)"),
                ("👥 /massrole", "Assign a role to all server members (Admin)")
            ]

            # Add fields in a logical order
            embed.add_field(
                name="🛠️ General Commands",
                value="\n".join(f"`{cmd}` • {desc}" for cmd, desc in info_commands),
                inline=False
            )

            embed.add_field(
                name="📈 Leveling System",
                value="\n".join(f"`{cmd}` • {desc}" for cmd, desc in leveling_commands),
                inline=False
            )

            embed.add_field(
                name="🎭 Role Management",
                value="\n".join(f"`{cmd}` • {desc}" for cmd, desc in autorole_commands),
                inline=False
            )

            # Add footer with admin note
            embed.set_footer(text="Note: Commands marked with (Admin) require administrator permissions")

            await interaction.response.send_message(embed=embed)
            logger.info(f"Help command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await interaction.response.send_message("An error occurred while processing your request.")

async def setup(bot):
    await bot.add_cog(Info(bot))
