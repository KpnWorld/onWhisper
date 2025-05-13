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
                    title=f"Bot Info: {self.bot.user.name}",
                    description="```prolog\nA multipurpose Discord bot with moderation, leveling, and whisper systems```",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                # Basic Info Section
                basic_info = (
                    f"```yaml\n"
                    f"Bot ID: {self.bot.user.id}\n"
                    f"Created: {discord.utils.format_dt(self.bot.user.created_at, style='D')}\n"
                    f"Uptime: {self._get_bot_uptime()}\n"
                    f"```"
                )
                embed.add_field(name="Basic Info", value=basic_info, inline=False)

                # Stats Section
                stats = (
                    f"```yaml\nServers: {len(self.bot.guilds):,}```\n"
                    f"```yaml\nUsers: {sum(g.member_count for g in self.bot.guilds):,}```\n"
                    f"```yaml\nCommands: {len(self.bot.commands):,}```"
                )
                embed.add_field(name="Stats", value=stats, inline=True)

                # System Info
                process = psutil.Process()
                mem_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
                sys_info = (
                    f"```yaml\nCPU: {psutil.cpu_percent()}%```\n"
                    f"```yaml\nRAM: {mem_usage:.1f} MB```\n"
                    f"```yaml\nPython: v{platform.python_version()}```\n"
                    f"```yaml\nDiscord.py: v{discord.__version__}```"
                )
                embed.add_field(name="System", value=sys_info, inline=True)

                # Usage Stats (if available from db_manager)
                usage_info = (
                    "```yaml\nCommands Used: N/A```\n"
                    "```yaml\nMessages Seen: N/A```\n"
                    "```yaml\nThreads Open: N/A```"
                )
                embed.add_field(name="Usage", value=usage_info, inline=False)

                # Set footer
                embed.set_footer(
                    text=f"{self.bot.user.name} • Powered by Py-cord",
                    icon_url=self.bot.user.display_avatar.url
                )

                await interaction.response.send_message(embed=embed)

            elif target == "server":
                guild = interaction.guild
                embed = discord.Embed(
                    title=f"🏰 Server Information - {guild.name}",
                    color=guild.me.color,
                    timestamp=discord.utils.utcnow()
                )
                
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)

                # Server Basic Info
                basic_info = (
                    f"```yaml\n"
                    f"Owner: {guild.owner} ({guild.owner.id})\n"
                    f"Created: {discord.utils.format_dt(guild.created_at, style='D')}\n"
                    f"Members: {guild.member_count:,}\n"
                    f"Roles: {len(guild.roles):,}\n"
                    f"```"
                )
                embed.add_field(name="General", value=basic_info, inline=True)

                # Channel Stats
                channels = {
                    "Text": len([c for c in guild.channels if isinstance(c, discord.TextChannel)]),
                    "Voice": len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)]),
                    "Categories": len(guild.categories),
                    "Threads": len([t for t in guild.threads if t.archived is False])
                }
                
                channels_info = "\n".join(
                    f"```yaml\n{k}: {v:,}```" for k, v in channels.items()
                )
                embed.add_field(name="Channels", value=channels_info, inline=True)

                # Member Stats
                online_count = len([m for m in guild.members if m.status != discord.Status.offline])
                members = {
                    "Humans": len([m for m in guild.members if not m.bot]),
                    "Bots": len([m for m in guild.members if m.bot]),
                    "Online": online_count
                }
                
                members_info = "\n".join(
                    f"```yaml\n{k}: {v:,}```" for k, v in members.items()
                )
                embed.add_field(name="Members", value=members_info, inline=True)

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
                    title=f"👤 User Information - {member.display_name}",
                    color=member.color,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)

                # User Basic Info
                user_info = (
                    f"```yaml\nID: {member.id}```\n"
                    f"```yaml\nCreated: {discord.utils.format_dt(member.created_at)}```\n"  # Full date format
                    f"```yaml\nJoined: {discord.utils.format_dt(member.joined_at)}```\n"  # Full date format
                    f"```yaml\nBot: {'Yes' if member.bot else 'No'}```"
                )
                embed.add_field(name="User Info", value=user_info, inline=True)

                # Status and Activity
                status_emoji = {
                    discord.Status.online: "🟢",
                    discord.Status.idle: "🌙",
                    discord.Status.dnd: "⛔",
                    discord.Status.offline: "⚫"
                }
                
                status_field = f"{status_emoji.get(member.status, '⚫')} {str(member.status).title()}"
                if member.activity:
                    activity_type = {
                        discord.ActivityType.playing: "🎮 Playing",
                        discord.ActivityType.streaming: "🎥 Streaming",
                        discord.ActivityType.listening: "🎵 Listening to",
                        discord.ActivityType.watching: "👀 Watching",
                        discord.ActivityType.custom: "💭",
                        discord.ActivityType.competing: "🏆 Competing in"
                    }
                    activity = f"{activity_type.get(member.activity.type, '❓')} {member.activity.name}"
                    status_field += f"\n{activity}"

                embed.add_field(name="Status", value=f"```yaml\n{status_field}```", inline=True)

                # Roles
                roles = [role.mention for role in reversed(member.roles[1:])]
                if roles:
                    embed.add_field(
                        name=f"Roles ({len(roles)})",
                        value=" ".join(roles) if len(roles) <= 10 else " ".join(roles[:10]) + f" (+{len(roles) - 10} more)",
                        inline=False
                    )

                # Permissions
                key_perms = []
                permissions = member.guild_permissions if target == "user" else role.permissions
                permission_mapping = {
                    "administrator": ("Administrator", "👑"),
                    "manage_guild": ("Manage Server", "🏰"),
                    "ban_members": ("Ban Members", "🔨"),
                    "kick_members": ("Kick Members", "👢"),
                    "manage_channels": ("Manage Channels", "📁"),
                    "manage_roles": ("Manage Roles", "🎭"),
                    "manage_messages": ("Manage Messages", "📝"),
                    "mention_everyone": ("Mention Everyone", "📢"),
                    "mute_members": ("Mute Members", "🔇"),
                    "deafen_members": ("Deafen Members", "🔈")
                }

                if permissions.administrator:
                    perms_info = "```yaml\nAdministrator: Full Access```"
                else:
                    perm_blocks = []
                    for perm_name, (perm_display, emoji) in permission_mapping.items():
                        if getattr(permissions, perm_name, False):
                            perm_blocks.append(f"```yaml\n{emoji} {perm_display}```")
                    perms_info = "\n".join(perm_blocks) if perm_blocks else "```yaml\nNo special permissions```"
                
                embed.add_field(
                    name="Permissions",
                    value=perms_info,
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
                    return await interaction.response.send_message("❌ Role not found.", ephemeral=True)

                embed = discord.Embed(
                    title=f"🎭 Role Information - {role.name}",
                    color=role.color,
                    timestamp=discord.utils.utcnow()
                )

                # Basic Info
                role_info = (
                    f"```yaml\nID: {role.id}```\n"
                    f"```yaml\nCreated: {discord.utils.format_dt(role.created_at)}```\n"  # Full date format
                    f"```yaml\nMembers: {len(role.members):,}```\n"
                    f"```yaml\nColor: {str(role.color)}```\n"
                    f"```yaml\nPosition: {role.position}```\n"
                    f"```yaml\nHoisted: {'Yes' if role.hoist else 'No'}```\n"
                    f"```yaml\nMentionable: {'Yes' if role.mentionable else 'No'}```"
                )
                embed.add_field(name="Role Info", value=role_info, inline=False)

                # Permissions
                key_perms = []
                permissions = member.guild_permissions if target == "user" else role.permissions
                permission_mapping = {
                    "administrator": ("Administrator", "👑"),
                    "manage_guild": ("Manage Server", "🏰"),
                    "ban_members": ("Ban Members", "🔨"),
                    "kick_members": ("Kick Members", "👢"),
                    "manage_channels": ("Manage Channels", "📁"),
                    "manage_roles": ("Manage Roles", "🎭"),
                    "manage_messages": ("Manage Messages", "📝"),
                    "mention_everyone": ("Mention Everyone", "📢"),
                    "mute_members": ("Mute Members", "🔇"),
                    "deafen_members": ("Deafen Members", "🔈")
                }

                if permissions.administrator:
                    perms_info = "```yaml\nAdministrator: Full Access```"
                else:
                    perm_blocks = []
                    for perm_name, (perm_display, emoji) in permission_mapping.items():
                        if getattr(permissions, perm_name, False):
                            perm_blocks.append(f"```yaml\n{emoji} {perm_display}```")
                    perms_info = "\n".join(perm_blocks) if perm_blocks else "```yaml\nNo special permissions```"
                
                embed.add_field(
                    name="Permissions",
                    value=perms_info,
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
                    return await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

                channel_type_emoji = {
                    discord.ChannelType.text: "💬",
                    discord.ChannelType.voice: "🔊",
                    discord.ChannelType.news: "📢",
                    discord.ChannelType.stage_voice: "🎭",
                    discord.ChannelType.forum: "📋"
                }

                embed = discord.Embed(
                    title=f"{channel_type_emoji.get(channel.type, '❓')} Channel Information - {channel.name}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )

                # Basic Info
                channel_info = (
                    f"```yaml\nID: {channel.id}```\n"
                    f"```yaml\nCreated: {discord.utils.format_dt(channel.created_at)}```\n"  # Full date format
                    f"```yaml\nCategory: {channel.category.name if channel.category else 'None'}```\n"
                    f"```yaml\nPrivate: {'Yes' if not channel.permissions_for(channel.guild.default_role).view_channel else 'No'}```\n"
                    f"```yaml\nPosition: {channel.position}```"
                )
                embed.add_field(name="Channel Info", value=channel_info, inline=False)

                # Channel-specific info for text channels
                if isinstance(channel, discord.TextChannel):
                    text_info = (
                        f"```yaml\nTopic: {channel.topic or 'No topic set'}```\n"
                        f"```yaml\nSlowmode: {channel.slowmode_delay}s```\n"
                        f"```yaml\nNSFW: {'Yes' if channel.is_nsfw() else 'No'}```"
                    )
                    embed.add_field(name="Text Channel Info", value=text_info, inline=False)
                
                # Channel-specific info for voice channels
                elif isinstance(channel, discord.VoiceChannel):
                    voice_info = (
                        f"```yaml\nUser Limit: {channel.user_limit if channel.user_limit else 'Unlimited'}```\n"
                        f"```yaml\nBitrate: {channel.bitrate // 1000}kbps```"
                    )
                    embed.add_field(name="Voice Channel Info", value=voice_info, inline=False)

                await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description=f"```\nAn error occurred: {str(e)}\n```",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

    @app_commands.command(name="help")
    @app_commands.describe(
        command="The specific command to get help for"
    )
    async def help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None
    ):
        """Get help with bot commands"""
        if command:
            # Look up specific command
            cmd = self.bot.tree.get_command(command.lower())
            if not cmd:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Command Not Found",
                        f"No command named '{command}' was found."
                    ),
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Help: /{cmd.name}",
                description=cmd.description or "No description available.",
                color=discord.Color.blue()
            )

            # Parameters
            if cmd.parameters:
                params = []
                for param in cmd.parameters:
                    is_required = param.required
                    param_desc = param.description or "No description"
                    params.append(f"• **{param.name}**{' (Optional)' if not is_required else ''}: {param_desc}")
                embed.add_field(
                    name="Parameters",
                    value="\n".join(params) or "No parameters",
                    inline=False
                )

            # Permissions
            if getattr(cmd.callback, "__commands_permissions__", None):
                perms = cmd.callback.__commands_permissions__
                embed.add_field(
                    name="Required Permissions",
                    value="\n".join(f"• {perm}" for perm in perms),
                    inline=False
                )

            # Cooldown
            if getattr(cmd.callback, "__commands_cooldown__", None):
                cooldown = cmd.callback.__commands_cooldown__
                embed.add_field(
                    name="Cooldown",
                    value=f"{cooldown.rate} uses per {cooldown.per:.0f} seconds",
                    inline=False
                )

        else:
            # Show all commands
            embed = discord.Embed(
                title="Bot Commands",
                description="Here are all available commands grouped by category. Use `/help <command>` for detailed information about a specific command.",
                color=discord.Color.blue()
            )

            # Group commands by category
            groups = {
                "💬 Whisper System": [],
                "⭐ Leveling": [],
                "👮 Moderation": [],
                "ℹ️ Information": [],
                "⚙️ Config": [],
                "🎭 Roles": [],
                "Other": []
            }

            for command in self.bot.tree.walk_commands():
                cmd_info = f"`/{command.name}` - {command.description or 'No description'}"
                
                # Handle command groups
                if isinstance(command, app_commands.Group):
                    if command.name == "whisper":
                        groups["💬 Whisper System"].append(cmd_info)
                        for subcmd in command.commands:
                            groups["💬 Whisper System"].append(
                                f"`/whisper {subcmd.name}` - {subcmd.description or 'No description'}"
                            )
                    elif command.name == "config":
                        groups["⚙️ Config"].append(cmd_info)
                        for subcmd in command.commands:
                            groups["⚙️ Config"].append(
                                f"`/config {subcmd.name}` - {subcmd.description or 'No description'}"
                            )
                    elif command.name == "roles":
                        groups["🎭 Roles"].append(cmd_info)
                        for subcmd in command.commands:
                            groups["🎭 Roles"].append(
                                f"`/roles {subcmd.name}` - {subcmd.description or 'No description'}"
                            )
                else:
                    # Categorize individual commands
                    name = command.name.lower()
                    if name in ["whisper"]:
                        groups["💬 Whisper System"].append(cmd_info)
                    elif name in ["rank", "levels", "leaderboard"]:
                        groups["⭐ Leveling"].append(cmd_info)
                    elif name in ["warn", "kick", "ban", "timeout", "clear", "slowmode"]:
                        groups["👮 Moderation"].append(cmd_info)
                    elif name in ["info", "help"]:
                        groups["ℹ️ Information"].append(cmd_info)
                    elif name in ["config", "settings"]:
                        groups["⚙️ Config"].append(cmd_info)
                    elif name in ["role", "roles"]:
                        groups["🎭 Roles"].append(cmd_info)
                    else:
                        groups["Other"].append(cmd_info)

            # Add non-empty groups to embed
            for group_name, commands_list in groups.items():
                if commands_list:
                    embed.add_field(
                        name=group_name,
                        value="\n".join(commands_list),
                        inline=False
                    )

            embed.set_footer(text="Use /help <command> for detailed information about a specific command.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))