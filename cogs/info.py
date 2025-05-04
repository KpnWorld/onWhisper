import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import psutil
import platform
from typing import Optional

class InfoCog(commands.Cog):
    """Provides information commands for the bot"""
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="info",
        description="Get information about various aspects of the server and bot"
    )
    @app_commands.describe(
        type="The type of information to view",
        user="The user to get info about (for user info)",
        role="The role to get info about (for role info)",
        command="The command to get help for (for help info)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Help Menu", value="help"),
        app_commands.Choice(name="User Info", value="user"),
        app_commands.Choice(name="Server Info", value="server"),
        app_commands.Choice(name="Bot Info", value="bot"),
        app_commands.Choice(name="Role Info", value="role"),
        app_commands.Choice(name="Uptime", value="uptime")
    ])
    async def info(
        self,
        interaction: discord.Interaction,
        type: str,
        user: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None,
        command: Optional[str] = None
    ):
        """Get various types of information"""
        try:
            if type == "help":
                if command:
                    # Find the command
                    cmd = self.bot.tree.get_command(command)
                    if not cmd:
                        raise commands.CommandNotFound(f"Command '{command}' not found")

                    # Create command help embed
                    embed = self.bot.ui_manager.info_embed(
                        f"Command: /{cmd.name}",
                        cmd.description or "No description provided"
                    )

                    # Add parameters if they exist
                    params = []
                    for param in getattr(cmd, 'parameters', []):
                        param_desc = f"• **{param.name}**"
                        if param.description:
                            param_desc += f": {param.description}"
                        if not param.required:
                            param_desc += " (Optional)"
                        params.append(param_desc)
                    
                    if params:
                        embed.add_field(
                            name="Parameters",
                            value='\n'.join(params),
                            inline=False
                        )

                    # Add permissions if they exist
                    if hasattr(cmd, 'default_permissions') and cmd.default_permissions:
                        perms = [p.replace('_', ' ').title() for p in cmd.default_permissions]
                        embed.add_field(
                            name="Required Permissions",
                            value='\n'.join(perms),
                            inline=False
                        )

                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Updated category selection menu for general help
                categories = {
                    "Moderation": [
                        "warn - Warn a user",
                        "warnings - View warnings for a user",
                        "kick - Kick a user from the server",
                        "ban - Ban a user from the server",
                        "timeout - Timeout a user for a specified duration",
                        "lockdown - Lock a channel temporarily",
                        "unlock - Remove a channel lockdown",
                        "slowmode - Set channel slowmode",
                        "clear - Clear messages in a channel",
                        "snipe - Show recently deleted/edited messages"
                    ],
                    "Roles": [
                        "roles auto_set - Set automatic role for new members",
                        "roles auto_disable - Disable automatic role",
                        "roles bulk_add - Add role to multiple users",
                        "roles bulk_remove - Remove role from multiple users",
                        "roles react_bind - Create reaction role",
                        "roles react_unbind - Remove reaction roles",
                        "roles react_list - List reaction roles",
                        "roles color - Set or clear your color role"
                    ],
                    "Configuration": [
                        "config logs - Configure logging settings",
                        "config whisper - Configure whisper system",
                        "config xp - Configure XP system settings",
                        "config level - Configure level-up role rewards",
                        "config color - Manage color roles"
                    ],
                    "Whispers": [
                        "whisper - Manage whisper threads",
                    ],
                    "Information": [
                        "info help - Show command help",
                        "info user - Show user information", 
                        "info server - Show server information",
                        "info bot - Show bot information",
                        "info role - Show role information",
                        "info uptime - Show bot uptime"
                    ]
                }

                embed = self.bot.ui_manager.info_embed(
                    "Bot Help",
                    "Select a category to view available commands.\nUse `/info help <command>` for detailed command help."
                )

                for category, commands in categories.items():
                    embed.add_field(
                        name=category,
                        value="```" + "\n".join(commands) + "```",
                        inline=False
                    )

                embed.add_field(
                    name="Need help?",
                    value="Use `/whisper` to contact staff for assistance.",
                    inline=False
                )

                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif type == "user":
                target = user or interaction.user
                embed = self.bot.ui_manager.info_embed(
                    f"User Info: {target}",
                    ""
                )

                # Basic info
                embed.add_field(
                    name="User ID",
                    value=f"```{target.id}```",
                    inline=True
                )
                embed.add_field(
                    name="Created",
                    value=f"<t:{int(target.created_at.timestamp())}:R>",
                    inline=True
                )
                embed.add_field(
                    name="Joined",
                    value=f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "```Unknown```",
                    inline=True
                )

                # Last seen info if available
                last_seen = await self.bot.db_manager.get_user_last_seen(interaction.guild_id, target.id)
                if last_seen:
                    embed.add_field(
                        name="Last Seen",
                        value=f"<t:{int(datetime.fromisoformat(last_seen).timestamp())}:R>",
                        inline=True
                    )

                # Roles
                role_list = [role.mention for role in reversed(target.roles[1:])]
                roles_text = " ".join(role_list) if role_list else "```No roles```"
                if len(roles_text) > 1024:
                    roles_text = roles_text[:1021] + "..."
                embed.add_field(
                    name=f"Roles [{len(role_list)}]",
                    value=roles_text,
                    inline=False
                )

                # Key Permissions
                key_perms = []
                if target.guild_permissions.administrator:
                    key_perms.append("Administrator")
                if target.guild_permissions.manage_guild:
                    key_perms.append("Manage Server")
                if target.guild_permissions.manage_roles:
                    key_perms.append("Manage Roles")
                if target.guild_permissions.manage_channels:
                    key_perms.append("Manage Channels")
                if target.guild_permissions.manage_messages:
                    key_perms.append("Manage Messages")
                if target.guild_permissions.moderate_members:
                    key_perms.append("Moderate Members")
                if target.guild_permissions.kick_members:
                    key_perms.append("Kick Members")
                if target.guild_permissions.ban_members:
                    key_perms.append("Ban Members")

                if key_perms:
                    embed.add_field(
                        name="Key Permissions",
                        value=f"```{', '.join(key_perms)}```",
                        inline=False
                    )

                # Status and activity
                status_emoji = {
                    discord.Status.online: "🟢",
                    discord.Status.idle: "🟡",
                    discord.Status.dnd: "🔴",
                    discord.Status.offline: "⚫"
                }
                
                status_text = [f"{status_emoji.get(target.status, '⚫')} {str(target.status).title()}"]
                if target.activity:
                    if isinstance(target.activity, discord.Game):
                        status_text.append(f"Playing {target.activity.name}")
                    elif isinstance(target.activity, discord.Streaming):
                        status_text.append(f"Streaming {target.activity.name}")
                    elif isinstance(target.activity, discord.Spotify):
                        status_text.append(f"Listening to {target.activity.title} by {target.activity.artist}")
                    elif isinstance(target.activity, discord.CustomActivity) and target.activity.name:
                        status_text.append(target.activity.name)

                embed.add_field(
                    name="Status",
                    value=f"```{chr(10).join(status_text)}```",
                    inline=False
                )

                # Set thumbnail
                embed.set_thumbnail(url=target.display_avatar.url)

                # Get user's level if system is enabled
                settings = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
                if settings.get('enabled', True):
                    data = await self.bot.db_manager.get_user_level_data(interaction.guild_id, target.id)
                    if data:
                        embed.add_field(
                            name="Level Info",
                            value=f"```Level: {data.get('level', 0)}\nXP: {data.get('xp', 0):,}```",
                            inline=True
                        )

                # Add warning count if any
                warnings = await self.bot.db_manager.get_user_warnings(interaction.guild_id, target.id)
                if warnings:
                    embed.add_field(
                        name="Warnings",
                        value=f"```{len(warnings)} warning(s)```",
                        inline=True
                    )

                await interaction.response.send_message(embed=embed)

            elif type == "server":
                guild = interaction.guild
                embed = self.bot.ui_manager.info_embed(
                    f"Server Info: {guild.name}",
                    ""
                )

                # Basic info
                embed.add_field(
                    name="Server ID",
                    value=f"```{guild.id}```",
                    inline=True
                )
                embed.add_field(
                    name="Owner",
                    value=guild.owner.mention if guild.owner else "```Unknown```",
                    inline=True
                )
                embed.add_field(
                    name="Created",
                    value=f"<t:{int(guild.created_at.timestamp())}:R>",
                    inline=True
                )

                # Member stats
                total_members = guild.member_count
                online_members = len([m for m in guild.members if m.status != discord.Status.offline])
                bot_count = len([m for m in guild.members if m.bot])
                human_count = total_members - bot_count

                embed.add_field(
                    name="Members",
                    value=f"```Total: {total_members:,}\nHumans: {human_count:,}\nBots: {bot_count:,}\nOnline: {online_members:,}```",
                    inline=True
                )

                # Channel stats
                text_channels = len(guild.text_channels)
                voice_channels = len(guild.voice_channels)
                categories = len(guild.categories)
                threads = len(guild.threads)

                embed.add_field(
                    name="Channels",
                    value=f"```Text: {text_channels}\nVoice: {voice_channels}\nThreads: {threads}\nCategories: {categories}```",
                    inline=True
                )

                # Role stats
                managed_roles = len([r for r in guild.roles if r.managed])
                embed.add_field(
                    name="Roles",
                    value=f"```Total: {len(guild.roles):,}\nManaged: {managed_roles:,}```",
                    inline=True
                )

                # Server settings
                settings = []
                settings.append(f"Verification: {str(guild.verification_level).title()}")
                settings.append(f"Content Filter: {str(guild.explicit_content_filter).replace('_', ' ').title()}")
                settings.append(f"2FA Required: {'Yes' if guild.mfa_level else 'No'}")
                
                embed.add_field(
                    name="Settings",
                    value=f"```{chr(10).join(settings)}```",
                    inline=False
                )

                # Features
                features_list = [f.replace('_', ' ').title() for f in guild.features]
                if features_list:
                    embed.add_field(
                        name="Features",
                        value=f"```{chr(10).join(features_list)}```",
                        inline=False
                    )

                # Boost status
                boost_tier_features = {
                    0: "No bonus features",
                    1: "50 emoji slots, 128Kbps audio",
                    2: "100 emoji slots, 256Kbps audio, server banner",
                    3: "250 emoji slots, 384Kbps audio, vanity URL"
                }
                
                embed.add_field(
                    name="Boost Status",
                    value=f"```Level {guild.premium_tier}\n{guild.premium_subscription_count:,} Boosts\n{boost_tier_features[guild.premium_tier]}```",
                    inline=True
                )

                # Set icon and banner
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
                if guild.banner:
                    embed.set_image(url=guild.banner.url)

                # Get guild settings
                whisper_config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
                xp_settings = await self.bot.db_manager.get_section(guild.id, 'xp_settings')
                logging_config = await self.bot.db_manager.get_section(guild.id, 'logging_config')

                # Add feature status
                features_status = [
                    f"Whisper System: {'✅ Enabled' if whisper_config.get('enabled', True) else '❌ Disabled'}",
                    f"XP System: {'✅ Enabled' if xp_settings.get('enabled', True) else '❌ Disabled'}",
                    f"Logging: {'✅ Enabled' if logging_config.get('logging_enabled', False) else '❌ Disabled'}"
                ]

                embed.add_field(
                    name="Bot Features",
                    value=f"```{chr(10).join(features_status)}```",
                    inline=False
                )

                await interaction.response.send_message(embed=embed)

            elif type == "bot":
                embed = self.bot.ui_manager.info_embed(
                    f"Bot Info: {self.bot.user.name}",
                    self.bot.description or ""
                )

                # Basic info
                embed.add_field(
                    name="Bot ID",
                    value=f"```{self.bot.user.id}```",
                    inline=True
                )
                embed.add_field(
                    name="Created",
                    value=f"<t:{int(self.bot.user.created_at.timestamp())}:R>",
                    inline=True
                )

                # Version info if available
                try:
                    with open('version.txt', 'r') as f:
                        version = f.read().strip()
                        embed.add_field(
                            name="Version",
                            value=f"```{version}```",
                            inline=True
                        )
                except:
                    pass

                # Uptime
                uptime = datetime.utcnow() - self.bot.start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                days, hours = divmod(hours, 24)
                uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

                embed.add_field(
                    name="Uptime",
                    value=f"```{uptime_str}```",
                    inline=True
                )

                # Shard info
                if self.bot.shard_count and self.bot.shard_count > 1:
                    embed.add_field(
                        name="Shards",
                        value=f"```Current: {interaction.guild.shard_id}\nTotal: {self.bot.shard_count}```",
                        inline=True
                    )

                # Stats
                total_members = sum(g.member_count for g in self.bot.guilds)
                embed.add_field(
                    name="Stats",
                    value=f"```Servers: {len(self.bot.guilds):,}\nUsers: {total_members:,}\nCommands: {len(self.bot.tree.get_commands()):,}```",
                    inline=True
                )

                # System info
                cpu_percent = psutil.cpu_percent()
                mem = psutil.Process().memory_info()
                mem_total = psutil.virtual_memory().total
                mem_percent = mem.rss / mem_total * 100

                embed.add_field(
                    name="System",
                    value=f"```CPU Usage: {cpu_percent}%\nMemory: {mem.rss/1024/1024:.1f}MB ({mem_percent:.1f}%)\nPython: {platform.python_version()}\nDiscord.py: {discord.__version__}```",
                    inline=True
                )

                # Connection info
                embed.add_field(
                    name="Connection",
                    value=f"```Latency: {round(self.bot.latency * 1000)}ms\nWebsocket: {round(interaction.client.latency * 1000)}ms```",
                    inline=True
                )

                # Set bot avatar
                if self.bot.user.avatar:
                    embed.set_thumbnail(url=self.bot.user.avatar.url)

                # Add command stats
                stats = await self.bot.db_manager.get_bot_stats(self.bot.user.id)
                if stats:
                    embed.add_field(
                        name="Usage",
                        value=f"```Commands Used: {stats.get('commands_used', 0):,}\nMessages Seen: {stats.get('messages_seen', 0):,}```",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            elif type == "role":
                # Role info code
                if not role:
                    raise ValueError("Role is required for role info")

                embed = self.bot.ui_manager.info_embed(
                    f"Role Info: {role.name}",
                    ""
                )
                embed.color = role.color

                # Basic info
                embed.add_field(
                    name="Role ID",
                    value=f"```{role.id}```",
                    inline=True
                )
                embed.add_field(
                    name="Created",
                    value=f"<t:{int(role.created_at.timestamp())}:R>",
                    inline=True
                )
                embed.add_field(
                    name="Color",
                    value=f"```{str(role.color)}```",
                    inline=True
                )

                # Member count
                embed.add_field(
                    name="Members",
                    value=f"```{len(role.members):,} members```",
                    inline=True
                )

                # Position info
                embed.add_field(
                    name="Position",
                    value=f"```{role.position}/{len(interaction.guild.roles)}```",
                    inline=True
                )

                # Permissions
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
                        value=f"```{', '.join(key_perms)}```",
                        inline=False
                    )

                # Properties
                properties = []
                if role.hoist:
                    properties.append("Displayed separately")
                if role.mentionable:
                    properties.append("Mentionable")
                if role.managed:
                    properties.append("Managed by integration")

                if properties:
                    embed.add_field(
                        name="Properties",
                        value=f"```{', '.join(properties)}```",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            elif type == "uptime":
                # Uptime code
                uptime = datetime.utcnow() - self.bot.start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                days, hours = divmod(hours, 24)

                start_timestamp = int((datetime.utcnow() - uptime).timestamp())
                embed = self.bot.ui_manager.info_embed(
                    "Bot Uptime",
                    f"Online since <t:{start_timestamp}:R>"
                )

                embed.add_field(
                    name="Detailed Uptime",
                    value=f"```{days}d {hours}h {minutes}m {seconds}s```",
                    inline=False
                )

                # Add some basic stats
                embed.add_field(
                    name="Status",
                    value=f"```Servers: {len(self.bot.guilds):,}\nUsers: {sum(g.member_count for g in self.bot.guilds):,}\nLatency: {round(self.bot.latency * 1000)}ms```",
                    inline=False
                )

                await interaction.response.send_message(embed=embed)

        except commands.CommandNotFound as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Command Not Found", str(e)),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InfoCog(bot))