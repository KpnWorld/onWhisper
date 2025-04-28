import discord
from discord.ext import commands
import platform
from datetime import datetime
from utils.db_manager import DBManager

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.ui = self.bot.ui_manager

    @commands.hybrid_command(name="help", description="Shows all available commands")
    async def help_command(self, ctx, command: str = None):
        """Shows a list of all commands or detailed help for a specific command"""
        try:
            if command:
                cmd = self.bot.get_command(command)
                if not cmd:
                    raise commands.CommandNotFound(f"Command '{command}' not found.")

                description = (
                    f"**Description:** {cmd.description or cmd.help or 'No description available'}\n"
                    f"**Usage:**\n"
                    f"• Slash: /{cmd.qualified_name} {cmd.signature}\n"
                    f"• Prefix: !{cmd.qualified_name} {cmd.signature}"
                )
                
                embed = self.ui.info_embed(
                    f"Help: {cmd.qualified_name}",
                    description
                )

                if isinstance(ctx, discord.Interaction):
                    await ctx.response.send_message(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                    
            else:
                # Get all commands grouped by cogs
                pages = []
                current_page = []
                commands_per_page = 10
                total_commands = 0

                # First page with overview
                info_embed = self.ui.info_embed(
                    "Help System",
                    f"Use `/help <command>` or `!help <command>` for detailed information about a specific command.\n\n"
                    f"**Navigation:**\n"
                    f"• Use the buttons below to navigate pages\n"
                    f"• Each page shows {commands_per_page} commands\n"
                    f"• Both slash and prefix versions are shown"
                )
                pages.append(info_embed)

                # Group commands by cog
                for cog_name, cog in self.bot.cogs.items():
                    cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                    if not cog_commands:
                        continue

                    # Start new page for each cog
                    current_page = []
                    current_page.append(f"**{cog_name} Commands**\n")

                    for cmd in cog_commands:
                        command_info = (
                            f"**{cmd.qualified_name}**\n"
                            f"• Slash: /{cmd.qualified_name} {cmd.signature}\n"
                            f"• Prefix: !{cmd.qualified_name} {cmd.signature}\n"
                            f"• *{cmd.description or cmd.help or 'No description'}*\n"
                        )
                        current_page.append(command_info)
                        total_commands += 1

                    # Add cog commands to pages
                    embed = self.ui.info_embed(
                        f"📚 {cog_name} Commands",
                        "\n".join(current_page)
                    )
                    pages.append(embed)

                # Update first page with total commands
                pages[0].description = f"Total Commands: {total_commands}\n\n" + pages[0].description

                # Send paginated help
                if isinstance(ctx, discord.Interaction):
                    await ctx.response.send_message(
                        embed=pages[0],
                        view=self.ui.Paginator(pages=pages),
                        ephemeral=True
                    )
                else:
                    msg = await ctx.send(
                        embed=pages[0],
                        view=self.ui.Paginator(pages=pages)
                    )

        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about the bot")
    async def botinfo(self, ctx):
        try:
            uptime = datetime.utcnow() - self.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            total_commands = len(set([cmd.qualified_name for cmd in self.bot.walk_commands()]))
            
            description = (
                f"**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
                f"**Servers:** {len(self.bot.guilds):,}\n"
                f"**Users:** {len(self.bot.users):,}\n"
                f"**Commands:** {total_commands:,}\n"
                f"**Python Version:** {platform.python_version()}\n"
                f"**py-cord Version:** {discord.__version__}"
            )
            
            embed = self.ui.info_embed(
                "Bot Information",
                description
            )
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about the server")
    async def serverinfo(self, ctx):
        """Display information about the current server"""
        try:
            guild = ctx.guild
            
            text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
            voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
            categories = len(guild.categories)
            threads = len(guild.threads)
            
            total_members = guild.member_count
            online = len([m for m in guild.members if m.status != discord.Status.offline])
            bots = len([m for m in guild.members if m.bot])
            
            description = (
                f"**Owner:** {guild.owner.mention}\n"
                f"**Created:** <t:{int(guild.created_at.timestamp())}:R>\n"
                f"\n"
                f"**Members:** {total_members:,}\n"
                f"• Online: {online:,}\n"
                f"• Humans: {total_members - bots:,}\n"
                f"• Bots: {bots:,}\n"
                f"\n"
                f"**Channels:** {text_channels + voice_channels + threads:,}\n"
                f"• Text: {text_channels:,}\n"
                f"• Voice: {voice_channels:,}\n"
                f"• Categories: {categories:,}\n"
                f"• Threads: {threads:,}\n"
                f"\n"
                f"**Roles:** {len(guild.roles):,}\n"
                f"**Emojis:** {len(guild.emojis):,}\n"
                f"**Boost Level:** {guild.premium_tier}\n"
                f"**Boosters:** {guild.premium_subscription_count or 0}"
            )
            
            embed = self.ui.info_embed(
                f"{guild.name} Information",
                description
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about a user")
    async def userinfo(self, ctx, user: discord.Member = None):
        """Display information about a user"""
        try:
            user = user or ctx.author
            
            roles = [role.mention for role in reversed(user.roles[1:])]  # All roles except @everyone
            
            embed = discord.Embed(
                title=f"User Information",
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="User Details",
                value=f"**ID:** {user.id}\n"
                      f"**Created:** <t:{int(user.created_at.timestamp())}:R>\n"
                      f"**Joined:** <t:{int(user.joined_at.timestamp() if user.joined_at else 0)}:R>\n"
                      f"**Display Name:** {user.display_name}\n"
                      f"**Bot:** {'Yes' if user.bot else 'No'}",
                inline=False
            )
            
            permissions = []
            if user.guild_permissions.administrator:
                permissions.append("Administrator")
            else:
                if user.guild_permissions.manage_guild:
                    permissions.append("Manage Server")
                if user.guild_permissions.ban_members:
                    permissions.append("Ban Members")
                if user.guild_permissions.kick_members:
                    permissions.append("Kick Members")
                if user.guild_permissions.manage_channels:
                    permissions.append("Manage Channels")
                if user.guild_permissions.manage_roles:
                    permissions.append("Manage Roles")
            
            embed.add_field(
                name="Key Permissions",
                value=', '.join(permissions) or 'None',
                inline=False
            )
            
            if roles:
                embed.add_field(
                    name=f"Roles [{len(roles)}]",
                    value=' '.join(roles),
                    inline=False
                )

            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)

            embed.set_footer(text=f"Command Type • User")
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Shows how long the bot has been running")
    async def uptime(self, ctx):
        """Display the bot's current uptime"""
        try:
            uptime = datetime.utcnow() - self.start_time
            days = uptime.days
            hours, rem = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            
            description = (
                f"I have been running for:\n"
                f"**{days}** days\n"
                f"**{hours}** hours\n"
                f"**{minutes}** minutes\n"
                f"**{seconds}** seconds"
            )
            
            embed = self.ui.info_embed(
                "🕒 Bot Uptime",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
