import discord
from discord.ext import commands
from typing import Optional
import psutil
import sys
from datetime import datetime

class Info(commands.Cog):
    """Bot and server information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager

    @commands.hybrid_group(name="info")
    async def info(self, ctx):
        """Information commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @info.command(name="help")
    async def info_help(self, ctx, command: Optional[str] = None):
        """Show help menu"""
        if command:
            cmd = self.bot.get_command(command)
            if not cmd:
                await ctx.send(f"Command '{command}' not found.", ephemeral=True)
                return
            embed = self.ui.info_embed(
                f"Help: {cmd.qualified_name}",
                f"{cmd.help or 'No description'}\n\n**Usage:** {cmd.usage or cmd.qualified_name}"
            )
        else:
            commands_list = []
            for cog_name, cog in self.bot.cogs.items():
                cmds = [f"`{c.qualified_name}`" for c in cog.get_commands()]
                if cmds:
                    commands_list.append(f"**{cog_name}**\n{', '.join(cmds)}")
            
            embed = self.ui.info_embed(
                "Command Help",
                "\n\n".join(commands_list)
            )
        await ctx.send(embed=embed)

    @info.command(name="bot")
    async def info_bot(self, ctx):
        """Show bot statistics"""
        stats = await self.db.get_bot_stats(self.bot.user.id)
        
        embed = self.ui.info_embed(
            "Bot Information",
            f"**Commands Used:** {stats.get('commands_used', 0):,}\n"
            f"**Messages Seen:** {stats.get('messages_seen', 0):,}\n"
            f"**Servers:** {len(self.bot.guilds):,}\n"
            f"**Users:** {len(self.bot.users):,}\n"
            f"**Latency:** {round(self.bot.latency * 1000)}ms"
        )
        await ctx.send(embed=embed)

    @info.command(name="server")
    async def info_server(self, ctx):
        """Show server statistics"""
        guild = ctx.guild
        embed = self.ui.info_embed(
            f"{guild.name} Information",
            f"**Owner:** {guild.owner.mention}\n"
            f"**Members:** {guild.member_count:,}\n"
            f"**Roles:** {len(guild.roles):,}\n"
            f"**Channels:** {len(guild.channels):,}\n"
            f"**Created:** <t:{int(guild.created_at.timestamp())}:R>"
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await ctx.send(embed=embed)

    @info.command(name="user")
    async def info_user(self, ctx, user: Optional[discord.Member] = None):
        """Show user profile"""
        user = user or ctx.author
        roles = [r.mention for r in user.roles[1:]]  # Exclude @everyone
        embed = self.ui.info_embed(
            f"{user.display_name}'s Profile",
            f"**ID:** {user.id}\n"
            f"**Joined:** <t:{int(user.joined_at.timestamp())}:R>\n"
            f"**Created:** <t:{int(user.created_at.timestamp())}:R>\n"
            f"**Roles:** {', '.join(roles) if roles else 'None'}"
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @info.command(name="role")
    async def info_role(self, ctx, role: discord.Role):
        """Show role details"""
        embed = self.ui.info_embed(
            f"{role.name} Role Information",
            f"**ID:** {role.id}\n"
            f"**Color:** {role.color}\n"
            f"**Members:** {len(role.members):,}\n"
            f"**Created:** <t:{int(role.created_at.timestamp())}:R>\n"
            f"**Position:** {role.position}\n"
            f"**Mentionable:** {role.mentionable}\n"
            f"**Hoisted:** {role.hoist}"
        )
        await ctx.send(embed=embed)

    @info.command(name="uptime")
    async def info_uptime(self, ctx):
        """Show bot uptime"""
        uptime = datetime.utcnow() - self.bot.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = self.ui.info_embed(
            "Bot Uptime",
            f"{days}d {hours}h {minutes}m {seconds}s"
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
