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
        try:
            if not isinstance(ctx.channel, discord.DMChannel):
                # Verify bot permissions
                if not ctx.channel.permissions_for(ctx.guild.me).embed_links:
                    await ctx.send("I need the 'Embed Links' permission to show help!")
                    return

            if command:
                cmd = self.bot.get_command(command)
                if not cmd:
                    raise commands.CommandNotFound(f"Command '{command}' not found.")

                # Add aliases if any exist
                aliases = ""
                if cmd.aliases:
                    aliases = f"\n**Aliases:** {', '.join(cmd.aliases)}"
                
                # Add group commands if it's a group
                subcommands = ""
                if isinstance(cmd, commands.Group):
                    subs = [f"• /{cmd.qualified_name} {subcmd.name} {subcmd.signature}" 
                           for subcmd in cmd.commands]
                    if subs:
                        subcommands = "\n\n**Subcommands:**\n" + "\n".join(subs)

                description = (
                    f"**Description:** {cmd.description or cmd.help or 'No description available'}\n"
                    f"**Usage:**\n"
                    f"• Slash: /{cmd.qualified_name} {cmd.signature}\n"
                    f"• Prefix: !{cmd.qualified_name} {cmd.signature}"
                    f"{aliases}"
                    f"{subcommands}"
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
                # Group commands by category
                categories = {
                    "🛠️ Configuration": ["config", "setlogs"],
                    "🔨 Moderation": ["kick", "ban", "timeout", "warn", "clear", "lock", "unlock", "slowmode", "snipe"],
                    "⭐ Leveling": ["level", "leaderboard"],
                    "🎫 Tickets": ["ticket"],
                    "👥 Roles": ["setautorole", "removeautorole", "bindreactionrole", "unbindreactionrole"],
                    "ℹ️ Information": ["help", "botinfo", "serverinfo", "userinfo", "uptime"],
                    "🔍 Debug": ["dbcheck", "dblookup", "dbstats", "guilddata", "dblist"]
                }

                pages = []
                total_commands = 0

                # Create overview page
                overview = self.ui.info_embed(
                    "Help System",
                    "Use `/help <command>` or `!help <command>` for detailed information about a specific command.\n\n"
                    "**Categories:**\n" + "\n".join(f"• {cat}" for cat in categories.keys())
                )
                pages.append(overview)

                # Create category pages
                for category, cmd_list in categories.items():
                    description = []
                    for cmd_name in cmd_list:
                        cmd = self.bot.get_command(cmd_name)
                        if cmd and not cmd.hidden:
                            total_commands += 1
                            description.append(
                                f"**/{cmd_name}**\n"
                                f"↳ {cmd.description or cmd.help or 'No description'}\n"
                            )

                    if description:
                        embed = self.ui.info_embed(
                            category,
                            "\n".join(description)
                        )
                        pages.append(embed)

                # Update overview with command count
                pages[0].description = f"Total Commands: {total_commands}\n\n" + pages[0].description

                # Send paginated help
                if isinstance(ctx, discord.Interaction):
                    await ctx.response.send_message(
                        embed=pages[0],
                        view=self.ui.Paginator(pages=pages),
                        ephemeral=True
                    )
                else:
                    await ctx.send(
                        embed=pages[0],
                        view=self.ui.Paginator(pages=pages)
                    )

        except discord.Forbidden:
            await ctx.send("I don't have permission to send embeds in this channel.")
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

    @commands.hybrid_command(description="Get information about the bot")
    async def botinfo(self, ctx):
        try:
            if not isinstance(ctx.channel, discord.DMChannel):
                # Verify bot permissions
                if not ctx.channel.permissions_for(ctx.guild.me).embed_links:
                    await ctx.send("I need the 'Embed Links' permission!")
                    return

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
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to send embeds.")
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

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
            await self.bot.on_command_error(ctx, e)

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
            await self.bot.on_command_error(ctx, e)

    @commands.hybrid_command(description="Shows how long the bot has been running")
    async def uptime(self, ctx):
        try:
            if not isinstance(ctx.channel, discord.DMChannel):
                # Verify bot permissions
                if not ctx.channel.permissions_for(ctx.guild.me).embed_links:
                    await ctx.send("I need the 'Embed Links' permission!")
                    return

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
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to send embeds.")
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

async def setup(bot):
    await bot.add_cog(Info(bot))
