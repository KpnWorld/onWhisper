import discord
from discord.ext import commands
from datetime import datetime, timedelta
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

    @commands.command()
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        await self.ui_manager.send_embed(
            ctx,
            title="🏓 Pong!",
            description=f"Latency is `{latency}ms`.",
            command_type="User"
        )

    @commands.command()
    async def uptime(self, ctx):
        """Check bot uptime"""
        uptime = datetime.utcnow() - datetime.fromtimestamp(self.bot.uptime)
        uptime_str = str(timedelta(seconds=int(uptime.total_seconds())))
        await self.ui_manager.send_embed(
            ctx,
            title="⏱️ Bot Uptime",
            description=f"The bot has been online for `{uptime_str}`.",
            command_type="User"
        )

    @commands.command()
    async def botinfo(self, ctx):
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

            await ctx.send(embed=embed)
        except Exception as e:
            await self.ui_manager.send_embed(
                ctx,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
            )

    @commands.command()
    async def serverinfo(self, ctx):
        """Show server information (Admins only)"""
        try:
            if not ctx.author.guild_permissions.administrator:
                return await self.ui_manager.send_embed(
                    ctx,
                    title="❌ Permission Denied",
                    description="You need administrator permissions to use this command.",
                    command_type="User"
                )

            guild = ctx.guild
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
            embed.add_field(name="Server Region", value=guild.region, inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            await self.ui_manager.send_embed(
                ctx,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
            )

    @commands.command()
    async def userinfo(self, ctx, user: discord.User = None):
        """Display user information"""
        user = user or ctx.author
        embed = self.ui_manager.create_embed(
            title=f"👤 {user.name}'s Information",
            description=f"Here are the details for {user.name}:",
            color=discord.Color.purple()
        )
        embed.add_field(name="User ID", value=user.id, inline=False)
        embed.add_field(name="Joined Discord", value=user.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
        embed.add_field(name="Joined Server", value=user.joined_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'joined_at') else "N/A", inline=False)
        embed.add_field(name="Status", value=str(user.status), inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def roleinfo(self, ctx, role: discord.Role):
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

        await ctx.send(embed=embed)

    # =========================
    # 🏆 Leaderboard Command
    # =========================

    @commands.command()
    async def leaderboard(self, ctx):
        """Show the server leaderboard of top XP earners"""
        try:
            leaderboard_data = await self.db_manager.get_leaderboard(ctx.guild.id)

            if not leaderboard_data:
                await self.ui_manager.send_embed(
                    ctx,
                    title="No XP Data Yet",
                    description="There are no users with XP data yet. Chat more to get on the leaderboard!",
                    command_type="User"
                )
                return

            leaderboard = "\n".join(
                [f"{rank + 1}. <@{row['user_id']}> - Level: {row['level']} | XP: {row['xp']}" for rank, row in enumerate(leaderboard_data)]
            )

            await self.ui_manager.send_embed(
                ctx,
                title="🏆 Server Leaderboard",
                description=f"**Top 10 Users by XP:**\n{leaderboard}",
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                ctx,
                title="❌ Error",
                description=f"An error occurred: {e}",
                command_type="User"
            )

def setup(bot):
    bot.add_cog(Info(bot))
