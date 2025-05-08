import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional

class InfoCog(commands.Cog):
    """Information commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="info", description="Get information about various aspects of the server and bot")
    @app_commands.describe(
        category="What type of information to show",
        user="The user to get information about (for user info)",
        role="The role to get information about (for role info)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Bot Information", value="bot"),
        app_commands.Choice(name="Server Information", value="server"),
        app_commands.Choice(name="User Information", value="user"),
        app_commands.Choice(name="Role Information", value="role"),
        app_commands.Choice(name="Setup Information", value="setup"),
        app_commands.Choice(name="Bot Uptime", value="uptime"),
        app_commands.Choice(name="Help", value="help")
    ])
    async def info(
        self,
        interaction: discord.Interaction,
        category: str,
        user: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None
    ):
        """Get information about various aspects of the server and bot"""
        try:
            if category == "bot":
                stats = await self.bot.db_manager.get_bot_stats(self.bot.user.id) or {}
                description = [
                    "```yml",
                    "Bot Statistics:",
                    f"  Name: {self.bot.user.name}",
                    f"  ID: {self.bot.user.id}",
                    f"  Servers: {len(self.bot.guilds)}",
                    f"  Commands: {len(self.bot.tree.get_commands())}",
                    f"  Uptime: {self.bot.uptime}",
                    "```"
                ]
                
                if stats:
                    description.extend([
                        "```diff",
                        "Usage Statistics:",
                        *[f"+ {k}: {v}" for k, v in stats.items()],
                        "```"
                    ])
                
                embed = self.bot.ui_manager.info_embed(
                    "Bot Information",
                    "\n".join(description)
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            elif category == "server":
                guild = interaction.guild
                description = [
                    "```yml",
                    "Server Information:",
                    f"  Name: {guild.name}",
                    f"  ID: {guild.id}",
                    f"  Owner: {guild.owner}",
                    f"  Created: {discord.utils.format_dt(guild.created_at, style='D')}",
                    "",
                    "Member Stats:",
                    f"  Total: {guild.member_count:,}",
                    f"  Humans: {len([m for m in guild.members if not m.bot]):,}",
                    f"  Bots: {len([m for m in guild.members if m.bot]):,}",
                    "",
                    "Channel Stats:",
                    f"  Text: {len([c for c in guild.channels if isinstance(c, discord.TextChannel)]):,}",
                    f"  Voice: {len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)]):,}",
                    f"  Categories: {len(guild.categories):,}",
                    "",
                    "Other Stats:",
                    f"  Roles: {len(guild.roles) - 1:,}",  # Subtract @everyone
                    f"  Emojis: {len(guild.emojis):,}",
                    f"  Boost Level: {guild.premium_tier}",
                    f"  Boosters: {guild.premium_subscription_count or 0}",
                    "```"
                ]

                if guild.features:
                    description.extend([
                        "```diff",
                        "Server Features:",
                        *[f"+ {feature.replace('_', ' ').title()}" 
                          for feature in guild.features],
                        "```"
                    ])

                embed = self.bot.ui_manager.info_embed(
                    guild.name,
                    "\n".join(description)
                )
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)

            elif category == "user":
                member = user or interaction.user
                description = [
                    "```yml",
                    "User Information:",
                    f"  Name: {member}",
                    f"  ID: {member.id}",
                    f"  Bot: {'Yes' if member.bot else 'No'}",
                    "",
                    "Dates:",
                    f"  Joined Server: {discord.utils.format_dt(member.joined_at, style='D')}",
                    f"  Account Created: {discord.utils.format_dt(member.created_at, style='D')}",
                    "```"
                ]

                roles = [role for role in reversed(member.roles[1:])]  # Exclude @everyone
                if roles:
                    description.extend([
                        "```diff",
                        f"Roles [{len(roles)}]:",
                        *[f"+ {role.name}" for role in roles],
                        "```"
                    ])

                # Get XP data with proper error handling
                xp_data = await self.bot.db_manager.safe_operation(
                    'get_user_xp',
                    self.bot.db_manager.get_user_xp,
                    interaction.guild_id,
                    str(member.id)
                ) or {}

                if xp_data:
                    description.extend([
                        "```cs",
                        "# Level Progress",
                        f"Level: {xp_data.get('level', 0)}",
                        f"XP: {xp_data.get('xp', 0):,}",
                        f"Next Level: {((xp_data.get('level', 0) + 1) ** 2) * 100:,} XP",
                        "```"
                    ])

                embed = self.bot.ui_manager.info_embed(
                    str(member),
                    "\n".join(description)
                )
                embed.set_thumbnail(url=member.display_avatar.url)

            elif category == "role":
                if not role:
                    raise ValueError("You must specify a role to get information about")

                description = [
                    "```yml",
                    "Role Information:",
                    f"  Name: {role.name}",
                    f"  ID: {role.id}",
                    f"  Color: {role.color}",
                    f"  Position: {role.position}",
                    f"  Members: {len(role.members):,}",
                    "",
                    "Settings:",
                    f"  Mentionable: {role.mentionable}",
                    f"  Hoisted: {role.hoist}",
                    f"  Managed: {role.managed}",
                    "```"
                ]

                # Key permissions in a organized format
                perms = role.permissions
                if any(value for value in perms):
                    description.extend([
                        "```diff",
                        "Key Permissions:",
                        *[f"+ {perm.replace('_', ' ').title()}"
                          for perm, value in perms
                          if value and perm in [
                              "administrator", "manage_guild", "manage_roles",
                              "manage_channels", "manage_messages", "kick_members",
                              "ban_members", "mention_everyone"
                          ]],
                        "```"
                    ])

                # Special role types
                special_types = []
                color_roles = await self.bot.db_manager.safe_operation(
                    'get_color_roles',
                    self.bot.db_manager.get_section,
                    interaction.guild_id,
                    'color_roles'
                ) or {'roles': []}

                level_roles = await self.bot.db_manager.safe_operation(
                    'get_level_roles',
                    self.bot.db_manager.get_section,
                    interaction.guild_id,
                    'level_roles'
                ) or {}
                
                if str(role.id) in color_roles.get('roles', []):
                    special_types.append("Color Role")

                if level_roles and str(role.id) in level_roles.values():
                    level = next(k for k, v in level_roles.items() if v == str(role.id))
                    special_types.append(f"Level {level} Reward")

                if special_types:
                    description.extend([
                        "```cs",
                        "# Special Role Types",
                        *special_types,
                        "```"
                    ])

                embed = self.bot.ui_manager.info_embed(
                    role.name,
                    "\n".join(description)
                )
                embed.colour = role.color

            elif category == "setup":
                description = ["# Server Configuration Status\n"]
                
                async with await self.bot.db_manager.transaction(interaction.guild_id, 'info') as txn:
                    # Whisper System
                    whisper_config = await self.bot.db_manager.safe_operation(
                        'get_whisper_config',
                        self.bot.db_manager.get_section,
                        interaction.guild_id,
                        'whisper_config'
                    ) or {}
                    
                    description.extend([
                        "```yml",
                        "Whisper System:",
                        f"  Status: {'✅ Enabled' if whisper_config.get('enabled') else '❌ Disabled'}",
                        f"  Channel: {interaction.guild.get_channel(int(whisper_config.get('channel_id', 0))).mention if whisper_config.get('channel_id') else '❌ Not Set'}",
                        f"  Staff Role: {interaction.guild.get_role(int(whisper_config.get('staff_role', 0))).mention if whisper_config.get('staff_role') else '❌ Not Set'}",
                        f"  Anonymous: {'✅ Allowed' if whisper_config.get('anonymous_allowed') else '❌ Not Allowed'}",
                        "```"
                    ])

                    # Logging System
                    logs_config = await self.bot.db_manager.safe_operation(
                        'get_logs_config',
                        self.bot.db_manager.get_section,
                        interaction.guild_id,
                        'logs'
                    ) or {}
                    
                    description.extend([
                        "```diff",
                        "Logging System:",
                        f"- Status: {'✅ Enabled' if logs_config.get('enabled') else '❌ Disabled'}",
                        f"- Channel: {interaction.guild.get_channel(int(logs_config.get('log_channel', 0))).mention if logs_config.get('log_channel') else '❌ Not Set'}",
                        "",
                        "Logged Events:"
                    ])
                    if logs_config.get('log_types'):
                        for category, events in logs_config['log_types'].items():
                            description.append(f"+ {category.title()}: {', '.join(events)}")
                    description.append("```")

                    # XP System
                    xp_config = await self.bot.db_manager.safe_operation(
                        'get_xp_config',
                        self.bot.db_manager.get_section,
                        interaction.guild_id,
                        'xp_settings'
                    ) or {}
                    
                    description.extend([
                        "```cs",
                        "# Leveling System",
                        f"Status: {'✅ Enabled' if xp_config.get('enabled') else '❌ Disabled'}",
                        f"XP Rate: {xp_config.get('rate', 'Default')} per message",
                        f"Cooldown: {xp_config.get('cooldown', 'Default')} seconds",
                        "```"
                    ])

                    # Roles Configuration
                    roles_config = await self.bot.db_manager.safe_operation(
                        'get_roles_config',
                        self.bot.db_manager.get_section,
                        interaction.guild_id,
                        'roles'
                    ) or {}
                    
                    description.extend([
                        "```ini",
                        "[Roles Configuration]",
                        "Color Roles:"
                    ])
                    color_roles = [interaction.guild.get_role(int(r)) for r in roles_config.get('color_roles', [])]
                    color_roles = [r.name for r in color_roles if r]
                    description.extend([f"  {role}" for role in color_roles] if color_roles else ["  None configured"])
                    
                    description.append("\nLevel Roles:")
                    level_roles = roles_config.get('level_roles', {})
                    if level_roles:
                        for level, role_id in sorted(level_roles.items(), key=lambda x: int(x[0])):
                            role = interaction.guild.get_role(int(role_id))
                            if role:
                                description.append(f"  Level {level}: {role.name}")
                    else:
                        description.append("  None configured")
                    description.append("```")

                embed = self.bot.ui_manager.info_embed(
                    f"Setup Information for {interaction.guild.name}",
                    "\n".join(description)
                )

            elif category == "uptime":
                description = [
                    "```yml",
                    "Bot Uptime Information:",
                    f"  Start Time: {discord.utils.format_dt(self.bot.start_time, style='D')}",
                    f"  Time Online: {self.bot.uptime}",
                    f"  Last Restart: {discord.utils.format_dt(self.bot.start_time, style='R')}",
                    "```"
                ]
                embed = self.bot.ui_manager.info_embed(
                    "Bot Uptime",
                    "\n".join(description)
                )

            elif category == "help":
                await self.bot.ui_manager.create_help_menu(interaction, self.bot)
                return

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InfoCog(bot))