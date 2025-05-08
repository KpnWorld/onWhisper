import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import datetime
import platform
import psutil
import os

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    def _get_bot_uptime(self):
        """Get bot uptime as a formatted string"""
        delta = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    @app_commands.command(name="info")
    @app_commands.describe(
        target="What to get info about",
        item="The specific item to get info about (user, role, or channel mention/ID)"
    )
    @app_commands.choices(target=[
        app_commands.Choice(name="bot", value="bot"),
        app_commands.Choice(name="server", value="server"),
        app_commands.Choice(name="user", value="user"),
        app_commands.Choice(name="role", value="role"),
        app_commands.Choice(name="channel", value="channel")
    ])
    async def info(
        self,
        interaction: discord.Interaction,
        target: Literal["bot", "server", "user", "role", "channel"],
        item: Optional[str] = None
    ):
        """Get detailed information about various Discord objects"""
        try:
            if target == "bot":
                embed = discord.Embed(
                    title="Bot Information",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                # Basic Info
                embed.add_field(
                    name="Bot Stats",
                    value=f"""
                    **Servers:** {len(self.bot.guilds):,}
                    **Users:** {sum(g.member_count for g in self.bot.guilds):,}
                    **Commands:** {len(self.bot.commands):,}
                    **Uptime:** {self._get_bot_uptime()}
                    """.strip(),
                    inline=True
                )

                # System Info
                process = psutil.Process()
                embed.add_field(
                    name="System Info",
                    value=f"""
                    **Python:** {platform.python_version()}
                    **Discord.py:** {discord.__version__}
                    **Memory:** {process.memory_info().rss / 1024 / 1024:.2f} MB
                    **CPU:** {psutil.cpu_percent()}%
                    """.strip(),
                    inline=True
                )

                await interaction.response.send_message(embed=embed)

            elif target == "server":
                guild = interaction.guild
                embed = discord.Embed(
                    title=f"Server Information - {guild.name}",
                    color=guild.me.color,
                    timestamp=discord.utils.utcnow()
                )
                
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)

                # Basic Info
                embed.add_field(
                    name="General",
                    value=f"""
                    **Owner:** {guild.owner.mention}
                    **Created:** <t:{int(guild.created_at.timestamp())}:R>
                    **Members:** {guild.member_count:,}
                    **Roles:** {len(guild.roles):,}
                    """.strip(),
                    inline=True
                )

                # Channel Stats
                channels = {
                    "Text": len([c for c in guild.channels if isinstance(c, discord.TextChannel)]),
                    "Voice": len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)]),
                    "Categories": len(guild.categories),
                    "Threads": len([t for t in guild.threads if t.archived is False])
                }
                
                embed.add_field(
                    name="Channels",
                    value="\n".join(f"**{k}:** {v:,}" for k, v in channels.items()),
                    inline=True
                )

                # Member Stats
                members = {
                    "Humans": len([m for m in guild.members if not m.bot]),
                    "Bots": len([m for m in guild.members if m.bot]),
                    "Online": len([m for m in guild.members if m.status != discord.Status.offline])
                }
                
                embed.add_field(
                    name="Members",
                    value="\n".join(f"**{k}:** {v:,}" for k, v in members.items()),
                    inline=True
                )

                await interaction.response.send_message(embed=embed)

            elif target == "user":
                # Get user from mention or ID
                user_id = None
                if item:
                    if item.isdigit():
                        user_id = int(item)
                    elif item.startswith('<@') and item.endswith('>'):
                        user_id = int(item[2:-1].replace('!', ''))
                
                member = None
                if user_id:
                    member = interaction.guild.get_member(user_id)
                if not member:
                    member = interaction.user

                embed = discord.Embed(
                    title=f"User Information - {member.display_name}",
                    color=member.color,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)

                # Basic Info
                embed.add_field(
                    name="User Info",
                    value=f"""
                    **ID:** {member.id}
                    **Created:** <t:{int(member.created_at.timestamp())}:R>
                    **Joined:** <t:{int(member.joined_at.timestamp())}:R>
                    **Bot:** {'Yes' if member.bot else 'No'}
                    """.strip(),
                    inline=True
                )

                # Roles
                roles = [role.mention for role in reversed(member.roles[1:])]
                if roles:
                    embed.add_field(
                        name=f"Roles ({len(roles)})",
                        value=" ".join(roles) if len(roles) <= 10 else " ".join(roles[:10]) + f" (+{len(roles) - 10} more)",
                        inline=False
                    )

                # Activity
                if member.activity:
                    embed.add_field(
                        name="Activity",
                        value=str(member.activity.name),
                        inline=False
                    )

                # Permissions
                key_perms = []
                permissions = member.guild_permissions
                if permissions.administrator:
                    key_perms.append("Administrator")
                else:
                    if permissions.manage_guild:
                        key_perms.append("Manage Server")
                    if permissions.ban_members:
                        key_perms.append("Ban Members")
                    if permissions.kick_members:
                        key_perms.append("Kick Members")
                    if permissions.manage_channels:
                        key_perms.append("Manage Channels")
                    if permissions.manage_roles:
                        key_perms.append("Manage Roles")

                if key_perms:
                    embed.add_field(
                        name="Key Permissions",
                        value=", ".join(key_perms),
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            elif target == "role":
                # Get role from mention or ID
                role_id = None
                if item:
                    if item.isdigit():
                        role_id = int(item)
                    elif item.startswith('<@&') and item.endswith('>'):
                        role_id = int(item[3:-1])
                
                role = None
                if role_id:
                    role = interaction.guild.get_role(role_id)
                if not role:
                    await interaction.response.send_message(
                        "❌ Please provide a valid role mention or ID.",
                        ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"Role Information - {role.name}",
                    color=role.color,
                    timestamp=discord.utils.utcnow()
                )

                # Basic Info
                embed.add_field(
                    name="General",
                    value=f"""
                    **ID:** {role.id}
                    **Created:** <t:{int(role.created_at.timestamp())}:R>
                    **Color:** {str(role.color)}
                    **Members:** {len(role.members):,}
                    **Position:** {role.position}
                    **Mentionable:** {'Yes' if role.mentionable else 'No'}
                    **Hoisted:** {'Yes' if role.hoist else 'No'}
                    """.strip(),
                    inline=True
                )

                # Permissions
                key_perms = []
                permissions = role.permissions
                if permissions.administrator:
                    key_perms.append("Administrator")
                else:
                    if permissions.manage_guild:
                        key_perms.append("Manage Server")
                    if permissions.ban_members:
                        key_perms.append("Ban Members")
                    if permissions.kick_members:
                        key_perms.append("Kick Members")
                    if permissions.manage_channels:
                        key_perms.append("Manage Channels")
                    if permissions.manage_roles:
                        key_perms.append("Manage Roles")

                if key_perms:
                    embed.add_field(
                        name="Key Permissions",
                        value=", ".join(key_perms),
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            elif target == "channel":
                # Get channel from mention or ID
                channel_id = None
                if item:
                    if item.isdigit():
                        channel_id = int(item)
                    elif item.startswith('<#') and item.endswith('>'):
                        channel_id = int(item[2:-1])
                
                channel = None
                if channel_id:
                    channel = interaction.guild.get_channel(channel_id)
                if not channel:
                    channel = interaction.channel

                embed = discord.Embed(
                    title=f"Channel Information - {channel.name}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )

                # Basic Info
                info = [
                    f"**ID:** {channel.id}",
                    f"**Created:** <t:{int(channel.created_at.timestamp())}:R>",
                    f"**Type:** {str(channel.type).title()}"
                ]

                if isinstance(channel, discord.TextChannel):
                    info.extend([
                        f"**Topic:** {channel.topic or 'None'}",
                        f"**NSFW:** {'Yes' if channel.is_nsfw() else 'No'}",
                        f"**Category:** {channel.category.name if channel.category else 'None'}",
                        f"**Slowmode:** {channel.slowmode_delay}s"
                    ])
                elif isinstance(channel, discord.VoiceChannel):
                    info.extend([
                        f"**Bitrate:** {channel.bitrate // 1000}kbps",
                        f"**User Limit:** {channel.user_limit or 'Unlimited'}",
                        f"**Connected:** {len(channel.members):,}"
                    ])

                embed.add_field(
                    name="Channel Info",
                    value="\n".join(info),
                    inline=False
                )

                await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="help")
    @app_commands.describe(command="The command to get help for")
    async def help_command(self, interaction: discord.Interaction, command: Optional[str] = None):
        """Show help about commands"""
        if command:
            # Show detailed help for a specific command
            cmd = self.bot.get_command(command) or self.bot.tree.get_command(command)
            if not cmd:
                return await interaction.response.send_message(
                    f"❌ Command '{command}' not found.",
                    ephemeral=True
                )

            embed = discord.Embed(
                title=f"Help - {cmd.name}",
                description=cmd.description or cmd.help or "No description available.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            if isinstance(cmd, commands.Command) and cmd.aliases:
                embed.add_field(
                    name="Aliases",
                    value=", ".join(cmd.aliases),
                    inline=False
                )

            usage = f"/{cmd.name}"
            if isinstance(cmd, commands.Command) and cmd.signature:
                usage += f" {cmd.signature}"
            embed.add_field(name="Usage", value=f"```{usage}```", inline=False)

            if isinstance(cmd, commands.Group):
                subcommands = []
                for subcmd in cmd.commands:
                    subcommands.append(f"`{subcmd.name}` - {subcmd.description or subcmd.help or 'No description'}")
                if subcommands:
                    embed.add_field(
                        name="Subcommands",
                        value="\n".join(subcommands),
                        inline=False
                    )

        else:
            # Show general help with command categories
            embed = discord.Embed(
                title="Bot Commands",
                description="Here are all the available commands:",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            # Group commands by cog
            for cog_name, cog in self.bot.cogs.items():
                commands_list = []
                # Add slash commands
                for cmd in cog.get_app_commands():
                    if not getattr(cmd, 'hidden', False):
                        commands_list.append(
                            f"`/{cmd.name}` - {cmd.description or 'No description'}"
                        )
                
                if commands_list:
                    embed.add_field(
                        name=cog_name,
                        value="\n".join(commands_list),
                        inline=False
                    )

            embed.set_footer(text="Use /help <command> for detailed information about a command.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))