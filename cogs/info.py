from sys import platform
import time
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import psutil
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

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
        latency = round(self.bot.latency * 1000)
        await self.ui_manager.send_embed(
            interaction,
            title="🏓 Pong!",
            description=f"Latency is `{latency}ms`.",
            command_type="User"
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

    @app_commands.command(name="botinfo", description="Display bot information")
    async def botinfo(self, interaction: discord.Interaction):
        """Display bot information"""
        try:
            memory_usage = round(psutil.Process().memory_info().rss / (1024 ** 2), 2)
            embed = self.ui_manager.create_embed(
                title="🤖 Bot Information",
                description=f"Here are the stats for {self.bot.user.name}:",
                color=discord.Color.blue()
            )
            embed.add_field(name="Uptime", value=str(timedelta(seconds=int(time.time() - self.bot.start_time))), inline=False)
            embed.add_field(name="Memory Usage", value=f"{memory_usage} MB", inline=False)
            embed.add_field(name="Platform", value=platform.system(), inline=False)
            embed.add_field(name="Python Version", value=platform.python_version(), inline=False)
            embed.add_field(name="Discord.py Version", value=discord.__version__, inline=False)

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
            member_count = guild.member_count
            online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            role_count = len(guild.roles)

            embed = self.ui_manager.create_embed(
                title=f"📊 Server Information: {guild.name}",
                description=f"Information for the server {guild.name}",
                color=discord.Color.green()
            )
            embed.add_field(name="Total Members", value=member_count, inline=True)
            embed.add_field(name="Online Members", value=online_members, inline=True)
            embed.add_field(name="Text Channels", value=text_channels, inline=True)
            embed.add_field(name="Voice Channels", value=voice_channels, inline=True)
            embed.add_field(name="Total Roles", value=role_count, inline=True)

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
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

    @app_commands.command(name="help", description="Shows the list of available commands")
    async def help(self, interaction: discord.Interaction, command: str = None):
        """Get help about commands"""
        
        if command:
            # Show detailed help for specific command
            cmd = self.bot.tree.get_command(command)
            if not cmd:
                return await self.ui_manager.send_embed(
                    interaction,
                    title="Command Not Found",
                    description=f"Command `{command}` does not exist.",
                    command_type="User"
                )
            
            embed = discord.Embed(
                title=f"Help: /{cmd.name}",
                description=cmd.description or "No description available.",
                color=discord.Color.blue()
            )
            
            if isinstance(cmd, app_commands.Command):
                params = []
                for param in cmd.parameters:
                    required = "Required" if param.required else "Optional"
                    params.append(f"• `{param.name}`: {param.description} ({required})")
                if params:
                    embed.add_field(name="Parameters", value="\n".join(params), inline=False)
            
            await interaction.response.send_message(embed=embed)
            return

        # Show general help with command categories
        categories = {
            "🎮 General": ["help", "ping", "uptime", "botinfo"],
            "📊 Leveling": ["level", "leaderboard"],
            "🔰 Verification": ["verify"],
            "⚙️ Admin": ["set-xp-rate", "set-xp-cooldown", "set-level-role", "setautorole"],
        }

        embed = discord.Embed(
            title="Bot Help",
            description="Here are all available commands. Use `/help <command>` for detailed information about a specific command.",
            color=discord.Color.blue()
        )

        for category, commands in categories.items():
            valid_commands = []
            for cmd_name in commands:
                cmd = self.bot.tree.get_command(cmd_name)
                if cmd:
                    valid_commands.append(f"`/{cmd_name}`")
            if valid_commands:
                embed.add_field(
                    name=category,
                    value=" • ".join(valid_commands),
                    inline=False
                )

        # Add bot info and support footer
        embed.set_footer(text="Use /help <command> for more details about a specific command")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
