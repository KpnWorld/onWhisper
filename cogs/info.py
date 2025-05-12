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
                    title="🤖 Bot Information",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                # Basic Info
                embed.add_field(
                    name="📊 Bot Stats",
                    value=f"""```
                🌐 Servers: {len(self.bot.guilds):,}
                👥 Users: {sum(g.member_count for g in self.bot.guilds):,}
                ⚡ Commands: {len(self.bot.commands):,}
                ⏰ Uptime: {self._get_bot_uptime()}```""",
                    inline=True
                )

                # System Info
                process = psutil.Process()
                embed.add_field(
                    name="💻 System Info",
                    value=f"""```
                🐍 Python: {platform.python_version()}
                📱 Discord.py: {discord.__version__}
                📊 Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB
                ⚡ CPU: {psutil.cpu_percent()}%```""",
                    inline=True
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

                # Basic Info
                embed.add_field(
                    name="📌 General",
                    value=f"""```
                👑 Owner: {guild.owner}
                📅 Created: {discord.utils.format_dt(guild.created_at, 'R')}
                👥 Members: {guild.member_count:,}
                🎭 Roles: {len(guild.roles):,}```""",
                    inline=True
                )

                # Channel Stats
                channels = {
                    "💬 Text": len([c for c in guild.channels if isinstance(c, discord.TextChannel)]),
                    "🔊 Voice": len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)]),
                    "📁 Categories": len(guild.categories),
                    "🧵 Threads": len([t for t in guild.threads if t.archived is False])
                }
                
                embed.add_field(
                    name="📊 Channels",
                    value="```" + "\n".join(f"{k}: {v:,}" for k, v in channels.items()) + "```",
                    inline=True
                )

                # Member Stats
                members = {
                    "👤 Humans": len([m for m in guild.members if not m.bot]),
                    "🤖 Bots": len([m for m in guild.members if m.bot]),
                    "🟢 Online": len([m for m in guild.members if m.status != discord.Status.offline])
                }
                
                embed.add_field(
                    name="👥 Members",
                    value="```" + "\n".join(f"{k}: {v:,}" for k, v in members.items()) + "```",
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
                    title=f"👤 User Information - {member.display_name}",
                    color=member.color,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)

                # Basic Info
                embed.add_field(
                    name="📌 User Info",
                    value=f"""```
                🆔 ID: {member.id}
                📅 Created: {discord.utils.format_dt(member.created_at, 'R')}
                📥 Joined: {discord.utils.format_dt(member.joined_at, 'R')}
                🤖 Bot: {'Yes' if member.bot else 'No'}```""",
                    inline=True
                )

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

                embed.add_field(
                    name="📊 Status",
                    value=f"```{status_field}```",
                    inline=True
                )

                # Roles
                roles = [role.mention for role in reversed(member.roles[1:])]
                if roles:
                    embed.add_field(
                        name=f"🎭 Roles ({len(roles)})",
                        value=" ".join(roles) if len(roles) <= 10 else " ".join(roles[:10]) + f" (+{len(roles) - 10} more)",
                        inline=False
                    )

                # Permissions
                key_perms = []
                permissions = member.guild_permissions
                if permissions.administrator:
                    key_perms.append("👑 Administrator")
                else:
                    if permissions.manage_guild:
                        key_perms.append("🏰 Manage Server")
                    if permissions.ban_members:
                        key_perms.append("🔨 Ban Members")
                    if permissions.kick_members:
                        key_perms.append("👢 Kick Members")
                    if permissions.manage_channels:
                        key_perms.append("📁 Manage Channels")
                    if permissions.manage_roles:
                        key_perms.append("🎭 Manage Roles")

                if key_perms:
                    embed.add_field(
                        name="🔑 Key Permissions",
                        value="```" + "\n".join(key_perms) + "```",
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
                embed.add_field(
                    name="📌 Role Info",
                    value=f"""```
                🆔 ID: {role.id}
                📅 Created: {discord.utils.format_dt(role.created_at, 'R')}
                👥 Members: {len(role.members):,}
                🎨 Color: {str(role.color)}
                📊 Position: {role.position}
                🔒 Hoisted: {'Yes' if role.hoist else 'No'}
                🎭 Mentionable: {'Yes' if role.mentionable else 'No'}```""",
                    inline=False
                )

                # Permissions
                key_perms = []
                permissions = role.permissions
                if permissions.administrator:
                    key_perms.append("👑 Administrator")
                else:
                    if permissions.manage_guild:
                        key_perms.append("🏰 Manage Server")
                    if permissions.ban_members:
                        key_perms.append("🔨 Ban Members")
                    if permissions.kick_members:
                        key_perms.append("👢 Kick Members")
                    if permissions.manage_channels:
                        key_perms.append("📁 Manage Channels")
                    if permissions.manage_roles:
                        key_perms.append("🎭 Manage Roles")

                if key_perms:
                    embed.add_field(
                        name="🔑 Permissions",
                        value="```" + "\n".join(key_perms) + "```",
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
                embed.add_field(
                    name="📌 Channel Info",
                    value=f"""```
🆔 ID: {channel.id}
📅 Created: {discord.utils.format_dt(channel.created_at, 'R')}
📁 Category: {channel.category.name if channel.category else 'None'}
🔒 Private: {'Yes' if not channel.permissions_for(channel.guild.default_role).view_channel else 'No'}
📊 Position: {channel.position}```""",
                    inline=False
                )

                # Channel-specific info
                if isinstance(channel, discord.TextChannel):
                    embed.add_field(
                        name="💬 Text Channel Info",
                        value=f"""```
                    📝 Topic: {channel.topic or 'No topic set'}
                    🐌 Slowmode: {channel.slowmode_delay}s
                    🔞 NSFW: {'Yes' if channel.is_nsfw() else 'No'}```""",
                        inline=False
                    )
                elif isinstance(channel, discord.VoiceChannel):
                    embed.add_field(
                        name="🔊 Voice Channel Info",
                        value=f"""```
                    👥 User Limit: {channel.user_limit if channel.user_limit else 'Unlimited'}
                    🎵 Bitrate: {channel.bitrate // 1000}kbps```""",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
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