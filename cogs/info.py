import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import psutil
import platform
from typing import Optional

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="info_user",
        description="Show user profile information"
    )
    @app_commands.describe(
        user="The user to get info about (leave empty for yourself)"
    )
    async def info_user(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Show detailed information about a user"""
        try:
            target = user or interaction.user

            # Create embed
            embed = self.bot.ui_manager.info_embed(
                f"User Info: {target.display_name}",
                ""
            )
            embed.color = target.color  # Keep user's color
            
            # Basic info
            embed.add_field(
                name="User ID",
                value=target.id,
                inline=True
            )
            embed.add_field(
                name="Nickname",
                value=target.nick or "None",
                inline=True
            )
            embed.add_field(
                name="Account Created",
                value=discord.utils.format_dt(target.created_at, style='R'),
                inline=True
            )
            embed.add_field(
                name="Joined Server",
                value=discord.utils.format_dt(target.joined_at, style='R') if target.joined_at else "Unknown",
                inline=True
            )

            # Roles
            role_list = [role.mention for role in reversed(target.roles[1:])]  # Exclude @everyone
            roles_text = " ".join(role_list) if role_list else "No roles"
            if len(roles_text) > 1024:
                roles_text = roles_text[:1021] + "..."
            embed.add_field(
                name=f"Roles [{len(role_list)}]",
                value=roles_text,
                inline=False
            )

            # Permissions
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
            if target.guild_permissions.kick_members:
                key_perms.append("Kick Members")
            if target.guild_permissions.ban_members:
                key_perms.append("Ban Members")

            if key_perms:
                embed.add_field(
                    name="Key Permissions",
                    value=", ".join(key_perms),
                    inline=False
                )

            # Status and activity
            status_emoji = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡",
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }
            
            status_text = f"{status_emoji.get(target.status, '⚫')} {str(target.status).title()}"
            if target.activity:
                if isinstance(target.activity, discord.Game):
                    status_text += f"\nPlaying {target.activity.name}"
                elif isinstance(target.activity, discord.Streaming):
                    status_text += f"\nStreaming {target.activity.name}"
                elif isinstance(target.activity, discord.Spotify):
                    status_text += f"\nListening to {target.activity.title} by {target.activity.artist}"
                elif isinstance(target.activity, discord.CustomActivity):
                    status_text += f"\n{target.activity.name}"

            embed.add_field(
                name="Status",
                value=status_text,
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
                        value=f"Level: {data.get('level', 0)}\nXP: {data.get('xp', 0)}",
                        inline=True
                    )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="info_server",
        description="Show server statistics"
    )
    async def info_server(self, interaction: discord.Interaction):
        """Show detailed server information"""
        try:
            guild = interaction.guild

            # Create embed using UI manager
            embed = self.bot.ui_manager.info_embed(
                f"Server Info: {guild.name}",
                ""
            )

            # Basic info
            embed.add_field(
                name="Server ID",
                value=guild.id,
                inline=True
            )
            embed.add_field(
                name="Owner",
                value=guild.owner.mention if guild.owner else "Unknown",
                inline=True
            )
            embed.add_field(
                name="Created",
                value=discord.utils.format_dt(guild.created_at, style='R'),
                inline=True
            )

            # Member stats
            total_members = guild.member_count
            online_members = len([m for m in guild.members if m.status != discord.Status.offline])
            bot_count = len([m for m in guild.members if m.bot])

            embed.add_field(
                name="Members",
                value=f"Total: {total_members}\nOnline: {online_members}\nBots: {bot_count}",
                inline=True
            )

            # Channel stats
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)

            embed.add_field(
                name="Channels",
                value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}",
                inline=True
            )

            # Role stats
            embed.add_field(
                name="Roles",
                value=str(len(guild.roles)),
                inline=True
            )

            # Features
            features_list = [f.replace('_', ' ').title() for f in guild.features]
            if features_list:
                embed.add_field(
                    name="Features",
                    value='\n'.join(features_list),
                    inline=False
                )

            # Boost status
            embed.add_field(
                name="Boost Status",
                value=f"Level {guild.premium_tier}\n{guild.premium_subscription_count} Boosts",
                inline=True
            )

            # Set icon
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # Get guild settings
            whisper_config = await self.bot.db_manager.get_section(guild.id, 'whisper_config')
            xp_settings = await self.bot.db_manager.get_section(guild.id, 'xp_settings')

            # Add feature status
            features_status = []
            features_status.append(f"Whisper System: {'Enabled' if whisper_config.get('enabled', True) else 'Disabled'}")
            features_status.append(f"XP System: {'Enabled' if xp_settings.get('enabled', True) else 'Disabled'}")

            embed.add_field(
                name="Bot Features",
                value='\n'.join(features_status),
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="info_bot",
        description="Show bot stats and latency"
    )
    async def info_bot(self, interaction: discord.Interaction):
        """Show detailed bot information"""
        try:
            # Create embed using UI manager
            embed = self.bot.ui_manager.info_embed(
                f"Bot Info: {self.bot.user.name}",
                ""
            )

            # Basic info
            embed.add_field(
                name="Bot ID",
                value=self.bot.user.id,
                inline=True
            )
            embed.add_field(
                name="Created",
                value=discord.utils.format_dt(self.bot.user.created_at, style='R'),
                inline=True
            )

            # Uptime
            uptime = datetime.utcnow() - self.bot.start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

            embed.add_field(
                name="Uptime",
                value=uptime_str,
                inline=True
            )

            # Stats
            total_members = sum(g.member_count for g in self.bot.guilds)
            embed.add_field(
                name="Stats",
                value=f"Servers: {len(self.bot.guilds)}\nUsers: {total_members}\nCommands: {len(self.bot.tree.get_commands())}",
                inline=True
            )

            # System info
            cpu_percent = psutil.cpu_percent()
            mem = psutil.Process().memory_info()
            mem_total = psutil.virtual_memory().total
            mem_percent = mem.rss / mem_total * 100

            embed.add_field(
                name="System",
                value=f"CPU Usage: {cpu_percent}%\nMemory: {mem.rss/1024/1024:.1f}MB ({mem_percent:.1f}%)\nPython: {platform.python_version()}",
                inline=True
            )

            # Set bot avatar
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

            # Add command status from stats
            stats = await self.bot.db_manager.get_bot_stats(self.bot.user.id)
            if stats:
                embed.add_field(
                    name="Usage",
                    value=f"Commands Used: {stats.get('commands_used', 0):,}\nMessages Seen: {stats.get('messages_seen', 0):,}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="info_help",
        description="Show help menu or command info"
    )
    @app_commands.describe(
        command="Get help for a specific command"
    )
    async def info_help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None
    ):
        """Show help menu or command help"""
        try:
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

                # Add parameters
                if cmd.parameters:
                    params = []
                    for param in cmd.parameters:
                        param_desc = f"• **{param.name}**"
                        if param.description:
                            param_desc += f": {param.description}"
                        if not param.required:
                            param_desc += " (Optional)"
                        params.append(param_desc)
                    
                    embed.add_field(
                        name="Parameters",
                        value='\n'.join(params),
                        inline=False
                    )

                # Add permissions
                if cmd.default_permissions:
                    perms = [p.replace('_', ' ').title() for p in cmd.default_permissions]
                    embed.add_field(
                        name="Required Permissions",
                        value='\n'.join(perms),
                        inline=False
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Show category selection menu
            view = self.bot.ui_manager.HelpMenuView(self.bot, self.bot.ui_manager)
            
            # Create initial embed
            embed = self.bot.ui_manager.info_embed(
                "Bot Help",
                "Select a category from the menu below to view available commands."
            )
            embed.add_field(
                name="Need help?",
                value="If you need assistance, use the whisper command to contact staff.",
                inline=False
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            view.message = await interaction.original_response()

        except commands.CommandNotFound as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Command Not Found", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="info_role",
        description="Show detailed role information"
    )
    @app_commands.describe(
        role="The role to get info about"
    )
    async def info_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Show detailed information about a role"""
        try:
            # Create embed using UI manager
            embed = self.bot.ui_manager.info_embed(
                f"Role Info: {role.name}",
                ""
            )
            embed.color = role.color  # Keep role's color

            # Basic info
            embed.add_field(
                name="Role ID",
                value=role.id,
                inline=True
            )
            embed.add_field(
                name="Created",
                value=discord.utils.format_dt(role.created_at, style='R'),
                inline=True
            )
            embed.add_field(
                name="Color",
                value=str(role.color),
                inline=True
            )

            # Member count
            member_count = len(role.members)
            embed.add_field(
                name="Members",
                value=str(member_count),
                inline=True
            )

            # Position info
            embed.add_field(
                name="Position",
                value=f"{role.position}/{len(interaction.guild.roles)}",
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
                    value=", ".join(key_perms),
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
                    value=", ".join(properties),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="info_uptime",
        description="Show bot uptime"
    )
    async def info_uptime(self, interaction: discord.Interaction):
        """Show bot uptime"""
        try:
            uptime = datetime.utcnow() - self.bot.start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)

            embed = self.bot.ui_manager.info_embed(
                "Bot Uptime",
                f"Online for {days}d {hours}h {minutes}m {seconds}s"
            )

            # Add some basic stats
            embed.add_field(
                name="Status",
                value=f"Serving {len(self.bot.guilds):,} servers\n"
                      f"Watching {sum(g.member_count for g in self.bot.guilds):,} users\n"
                      f"Latency: {round(self.bot.latency * 1000)}ms",
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InfoCog(bot))