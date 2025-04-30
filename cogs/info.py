import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from typing import Optional

class Info(commands.Cog):
    """Bot, user, and server info commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())
        self.start_time = datetime.utcnow()

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Info cog")
                return
            self._ready.set()
            print("✅ Info cog ready")
        except Exception as e:
            print(f"❌ Error setting up Info cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    @commands.hybrid_group(name="info")
    async def info(self, ctx):
        """Information commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @info.command(name="help")
    async def info_help(self, ctx, command: Optional[str] = None):
        """Get help with bot commands"""
        try:
            if command:
                cmd = self.bot.get_command(command)
                if not cmd:
                    await ctx.send(f"Command '{command}' not found.", ephemeral=True)
                    return

                embed = self.ui.info_embed(
                    f"Command: {cmd.qualified_name}",
                    cmd.help or "No description available."
                )

                # Add usage if available
                if cmd.usage:
                    embed.add_field(name="Usage", value=f"`{ctx.prefix}{cmd.usage}`", inline=False)

                # Add examples if available
                if hasattr(cmd, 'examples'):
                    examples = "\n".join(f"`{ctx.prefix}{ex}`" for ex in cmd.examples)
                    embed.add_field(name="Examples", value=examples, inline=False)

                await ctx.send(embed=embed)
            else:
                # Show category selection menu
                embed = self.ui.info_embed(
                    "Command Categories",
                    "Select a category below to view available commands."
                )
                embed.add_field(
                    name="Need help?",
                    value="Use `/help <command>` to get detailed information about a specific command.",
                    inline=False
                )
                
                # Create and send view with dropdown
                view = self.ui.HelpMenuView(self.bot, self.ui)
                msg = await ctx.send(embed=embed, view=view)
                view.message = msg  # Store message for timeout handling

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @info.command(name="bot")
    async def info_bot(self, ctx):
        """View bot status & ping"""
        try:
            embed = self.ui.info_embed(
                f"{self.bot.user.name} Info",
                "A versatile Discord management bot"
            )

            # Add general stats
            guild_count = len(self.bot.guilds)
            member_count = sum(g.member_count for g in self.bot.guilds)
            channel_count = sum(len(g.channels) for g in self.bot.guilds)

            embed.add_field(
                name="Stats",
                value=f"Servers: {guild_count:,}\n"
                      f"Members: {member_count:,}\n"
                      f"Channels: {channel_count:,}"
            )

            # Add version info
            embed.add_field(
                name="Version",
                value=f"Discord.py: {discord.__version__}"
            )

            # Add latency info
            latency = round(self.bot.latency * 1000)
            embed.add_field(
                name="Latency",
                value=f"{latency}ms"
            )

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @info.command(name="server")
    async def info_server(self, ctx):
        """Show server information"""
        try:
            guild = ctx.guild
            embed = self.ui.info_embed(
                f"{guild.name} Info",
                guild.description or "No description"
            )

            # General info
            created_ts = int(guild.created_at.timestamp())
            general_info = (
                f"Owner: {guild.owner.mention}\n"
                f"Created: <t:{created_ts}:R>\n"
                f"Boost Level: {guild.premium_tier}"
            )
            embed.add_field(name="General", value=general_info, inline=False)

            # Member stats
            member_stats = (
                f"Total: {guild.member_count:,}\n"
                f"Humans: {sum(not m.bot for m in guild.members):,}\n"
                f"Bots: {sum(m.bot for m in guild.members):,}"
            )
            embed.add_field(name="Members", value=member_stats)

            # Channel stats
            channel_stats = (
                f"Categories: {len(guild.categories):,}\n"
                f"Text: {len(guild.text_channels):,}\n"
                f"Voice: {len(guild.voice_channels):,}"
            )
            embed.add_field(name="Channels", value=channel_stats)

            # Role stats
            role_stats = (
                f"Count: {len(guild.roles):,}\n"
                f"Highest: {guild.roles[-1].mention}"
            )
            embed.add_field(name="Roles", value=role_stats)

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @info.command(name="user")
    async def info_user(self, ctx, user: Optional[discord.Member] = None):
        """Show user info"""
        try:
            user = user or ctx.author
            embed = self.ui.info_embed(
                f"User Info: {user}",
                f"ID: {user.id}"
            )

            # Join dates
            joined_ts = int(user.joined_at.timestamp())
            created_ts = int(user.created_at.timestamp())
            
            dates = (
                f"Joined: <t:{joined_ts}:R>\n"
                f"Created: <t:{created_ts}:R>"
            )
            embed.add_field(name="Dates", value=dates, inline=False)

            # Roles
            roles = [role.mention for role in reversed(user.roles[1:])]  # Exclude @everyone
            embed.add_field(
                name=f"Roles [{len(roles)}]",
                value=" ".join(roles) if roles else "None",
                inline=False
            )

            # Permissions
            key_perms = []
            if user.guild_permissions.administrator:
                key_perms.append("Administrator")
            if user.guild_permissions.manage_guild:
                key_perms.append("Manage Server")
            if user.guild_permissions.manage_roles:
                key_perms.append("Manage Roles")
            if user.guild_permissions.manage_channels:
                key_perms.append("Manage Channels")
            if user.guild_permissions.manage_messages:
                key_perms.append("Manage Messages")
            if user.guild_permissions.kick_members:
                key_perms.append("Kick Members")
            if user.guild_permissions.ban_members:
                key_perms.append("Ban Members")

            if key_perms:
                embed.add_field(
                    name="Key Permissions",
                    value=", ".join(key_perms),
                    inline=False
                )

            embed.set_thumbnail(url=user.display_avatar.url)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @info.command(name="role")
    async def info_role(self, ctx, role: discord.Role):
        """Display role details"""
        try:
            embed = self.ui.info_embed(
                f"Role Info: {role.name}",
                f"ID: {role.id}"
            )

            # General info
            created_ts = int(role.created_at.timestamp())
            general_info = (
                f"Created: <t:{created_ts}:R>\n"
                f"Position: {role.position}\n"
                f"Color: {role.color}\n"
                f"Mentionable: {role.mentionable}\n"
                f"Hoisted: {role.hoist}\n"
                f"Members: {len(role.members):,}"
            )
            embed.add_field(name="General", value=general_info, inline=False)

            # Key permissions
            key_perms = []
            if role.permissions.administrator:
                key_perms.append("Administrator")
            if role.permissions.manage_guild:
                key_perms.append("Manage Server")
            if role.permissions.manage_roles:
                key_perms.append("Manage Roles")
            if role.permissions.manage_channels:
                key_perms.append("Manage Channels")
            if role.permissions.manage_messages:
                key_perms.append("Manage Messages")
            if role.permissions.kick_members:
                key_perms.append("Kick Members")
            if role.permissions.ban_members:
                key_perms.append("Ban Members")

            if key_perms:
                embed.add_field(
                    name="Key Permissions",
                    value=", ".join(key_perms),
                    inline=False
                )

            embed.color = role.color
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @info.command(name="uptime")
    async def info_uptime(self, ctx):
        """Show bot uptime"""
        try:
            now = datetime.utcnow()
            delta = now - self.start_time
            
            # Format uptime
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime = []
            if days > 0:
                uptime.append(f"{days} days")
            if hours > 0:
                uptime.append(f"{hours} hours")
            if minutes > 0:
                uptime.append(f"{minutes} minutes")
            uptime.append(f"{seconds} seconds")

            embed = self.ui.info_embed(
                "Bot Uptime",
                ", ".join(uptime)
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Info(bot))
