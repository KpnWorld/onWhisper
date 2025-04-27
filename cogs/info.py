import discord
from discord.ext import commands
import platform
from datetime import datetime
from utils.db_manager import DBManager

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    @commands.hybrid_command(name="help", description="Shows all available commands")
    async def help_command(self, ctx, command: str = None):
        """Shows a list of all commands or detailed help for a specific command"""
        try:
            if command:
                # Show help for specific command
                cmd = self.bot.get_command(command)
                if not cmd:
                    raise commands.CommandNotFound(f"Command '{command}' not found.")

                description = (
                    f"**Description:** {cmd.description or cmd.help or 'No description available'}\n"
                    f"**Usage:** !{cmd.qualified_name} {cmd.signature}"
                )
                
                embed = self.bot.create_embed(
                    f"Help: {cmd.qualified_name}",
                    description,
                    command_type="User"
                )
                
            else:
                # Show all commands grouped by cogs
                description = ""
                
                for cog_name, cog in self.bot.cogs.items():
                    # Get all commands from the cog that the user can use
                    cog_commands = [cmd for cmd in cog.get_commands() if cmd.hidden is False]
                    
                    if cog_commands:
                        # Add cog section
                        description += f"\n**{cog_name}**\n"
                        
                        # Add each command's help
                        for cmd in cog_commands:
                            description += f"`!{cmd.name}` - {cmd.description or cmd.help or 'No description'}\n"
                
                embed = self.bot.create_embed(
                    "Command Help",
                    description.strip(),
                    command_type="User"
                )
                embed.set_footer(text="Type !help <command> for detailed information about a command")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about the bot")
    async def botinfo(self, ctx):
        """Display information about the bot"""
        try:
            uptime = datetime.utcnow() - self.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            description = (
                f"**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
                f"**Servers:** {len(self.bot.guilds):,}\n"
                f"**Users:** {len(self.bot.users):,}\n"
                f"**Commands:** {len(self.bot.application_commands):,}\n"
                f"**Python Version:** {platform.python_version()}\n"
                f"**py-cord Version:** {discord.__version__}"
            )
            
            embed = self.bot.create_embed(
                "Bot Information",
                description,
                command_type="User"
            )
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about the server")
    async def serverinfo(self, ctx):
        """Display information about the current server"""
        try:
            guild = ctx.guild
            
            # Count channels by type
            text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
            voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
            categories = len(guild.categories)
            threads = len(guild.threads)
            
            # Count member status
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
            
            embed = self.bot.create_embed(
                f"{guild.name} Information",
                description,
                command_type="User"
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Get information about a user")
    async def userinfo(self, ctx, user: discord.Member = None):
        """Display information about a user"""
        try:
            user = user or ctx.author
            
            roles = [role.mention for role in reversed(user.roles[1:])]  # All roles except @everyone
            
            created_ago = f"<t:{int(user.created_at.timestamp())}:R>"
            joined_ago = f"<t:{int(user.joined_at.timestamp())}:R>" if user.joined_at else "Unknown"
            
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
            
            description = (
                f"**ID:** {user.id}\n"
                f"**Created:** {created_ago}\n"
                f"**Joined:** {joined_ago}\n"
                f"\n"
                f"**Display Name:** {user.display_name}\n"
                f"**Bot:** {'Yes' if user.bot else 'No'}\n"
                f"\n"
                f"**Key Permissions:**\n"
                f"{', '.join(permissions) or 'None'}\n"
                f"\n"
                f"**Roles [{len(roles)}]:**\n"
                f"{' '.join(roles) if roles else 'None'}"
            )
            
            embed = self.bot.create_embed(
                f"User Information: {user}",
                description,
                command_type="User"
            )
            
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
