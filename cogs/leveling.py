import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import math

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a specific level"""
        return math.floor(100 * (level ** 1.5))

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP"""
        return math.floor((xp / 100) ** (1/1.5))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        if message.author.bot or not message.guild:
            return

        try:
            # Get XP settings
            settings = await self.bot.db_manager.get_section(message.guild.id, 'xp_settings')
            if not settings.get('enabled', True):
                return

            # Get user's XP data
            data = await self.bot.db_manager.get_user_level_data(message.guild.id, message.author.id)
            
            # Check cooldown
            now = datetime.utcnow()
            if data.get('last_xp'):
                last_xp = datetime.fromisoformat(data['last_xp'])
                if now - last_xp < timedelta(seconds=settings.get('cooldown', 60)):
                    return

            # Calculate XP gain
            xp_gain = settings.get('rate', 15)
            current_xp = data.get('xp', 0) + xp_gain
            old_level = data.get('level', 0)
            new_level = self.calculate_level_from_xp(current_xp)

            # Update user's XP/level
            await self.bot.db_manager.update_user_level_data(
                message.guild.id,
                message.author.id,
                current_xp,
                new_level,
                now
            )

            # Handle level up
            if new_level > old_level:
                # Check for role rewards
                level_roles = await self.bot.db_manager.get_level_roles(message.guild.id)
                for level, role_id in level_roles:
                    if old_level < level <= new_level:
                        role = message.guild.get_role(int(role_id))
                        if role:
                            try:
                                await message.author.add_roles(role)
                                embed = self.bot.ui_manager.xp_embed(
                                    "Level Up!",
                                    f"🎉 {message.author.mention} reached level {new_level} and earned the {role.mention} role!"
                                )
                            except discord.Forbidden:
                                embed = self.bot.ui_manager.xp_embed(
                                    "Level Up!",
                                    f"🎉 {message.author.mention} reached level {new_level}!\n⚠️ Could not assign role {role.mention} - missing permissions."
                                )
                            await message.channel.send(embed=embed)
                            return

                # If no role rewards, just show level up message
                embed = self.bot.ui_manager.xp_embed(
                    "Level Up!",
                    f"🎉 {message.author.mention} reached level {new_level}!"
                )
                await message.channel.send(embed=embed)

        except Exception as e:
            print(f"Error in XP handling: {e}")

    @app_commands.command(
        name='rank',
        description="Show your or another user's rank"
    )
    @app_commands.describe(
        user="The user to check (leave empty for yourself)"
    )
    async def rank(self, interaction: discord.Interaction, user: discord.Member = None):
        """Show rank information for a user"""
        try:
            target = user or interaction.user
            
            # Get XP settings and data
            settings = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
            if not settings.get('enabled', True):
                raise self.bot.XPNotEnabled("The leveling system is disabled in this server")

            data = await self.bot.db_manager.get_user_level_data(interaction.guild_id, target.id)
            if not data:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "No Data",
                        f"{target.display_name} hasn't earned any XP yet!"
                    ),
                    ephemeral=True
                )
                return

            # Calculate progress to next level
            current_xp = data.get('xp', 0)
            current_level = data.get('level', 0)
            xp_for_next = self.calculate_xp_for_level(current_level + 1)
            xp_from_current = self.calculate_xp_for_level(current_level)
            progress = (current_xp - xp_from_current) / (xp_for_next - xp_from_current)

            # Create progress bar
            progress_bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))

            embed = self.bot.ui_manager.xp_embed(
                f"Rank: {target.display_name}",
                f"Level Progress"
            )
            embed.add_field(
                name="Current Level",
                value=str(current_level),
                inline=True
            )
            embed.add_field(
                name="Total XP",
                value=str(current_xp),
                inline=True
            )
            embed.add_field(
                name="Progress to Next Level",
                value=f"`{progress_bar}` {progress:.1%}",
                inline=False
            )
            embed.set_thumbnail(url=target.display_avatar.url)

            await interaction.response.send_message(embed=embed)

        except self.bot.LevelingError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name='leaderboard',
        description='Show the XP leaderboard'
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Show server XP leaderboard"""
        try:
            # Get XP settings
            settings = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
            if not settings.get('enabled', True):
                raise self.bot.XPNotEnabled("The leveling system is disabled in this server")

            # Get all user levels
            all_data = await self.bot.db_manager.get_all_levels(interaction.guild_id)
            if not all_data:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.info_embed(
                        "Leaderboard Empty",
                        "No XP data found for this server yet!"
                    )
                )
                return

            # Sort users by XP
            sorted_users = sorted(
                all_data.items(),
                key=lambda x: (x[1].get('xp', 0), x[1].get('level', 0)),
                reverse=True
            )[:10]  # Top 10

            # Create leaderboard embed
            embed = self.bot.ui_manager.xp_embed(
                f"XP Leaderboard - {interaction.guild.name}",
                "Top 10 Members"
            )

            for idx, (user_id, data) in enumerate(sorted_users, 1):
                member = interaction.guild.get_member(int(user_id))
                if member:
                    name = f"{idx}. {member.display_name}"
                    value = f"Level {data['level']} • {data['xp']} XP"
                    embed.add_field(name=name, value=value, inline=False)

            await interaction.response.send_message(embed=embed)

        except self.bot.LevelingError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_to_embed(e),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name='xp_config',
        description='Configure the XP system'
    )
    @app_commands.describe(
        rate="XP gained per message (default: 15)",
        cooldown="Seconds between XP gains (default: 60)",
        enabled="Enable or disable the XP system"
    )
    @app_commands.default_permissions(administrator=True)
    async def xp_config(
        self,
        interaction: discord.Interaction,
        rate: int = None,
        cooldown: int = None,
        enabled: bool = None
    ):
        """Configure XP system settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            settings = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
            updated = False

            if rate is not None:
                if rate < 1:
                    raise ValueError("XP rate must be at least 1")
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'rate', rate)
                updated = True

            if cooldown is not None:
                if cooldown < 0:
                    raise ValueError("Cooldown cannot be negative")
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'cooldown', cooldown)
                updated = True

            if enabled is not None:
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'enabled', enabled)
                updated = True

            if not updated:
                # Show current settings
                embed = self.bot.ui_manager.info_embed(
                    "XP System Configuration",
                    "Current settings:"
                )
                embed.add_field(
                    name="XP Rate",
                    value=f"{settings.get('rate', 15)} XP per message",
                    inline=True
                )
                embed.add_field(
                    name="Cooldown",
                    value=f"{settings.get('cooldown', 60)} seconds",
                    inline=True
                )
                embed.add_field(
                    name="System Enabled",
                    value="Yes" if settings.get('enabled', True) else "No",
                    inline=True
                )
            else:
                embed = self.bot.ui_manager.success_embed(
                    "Configuration Updated",
                    "The XP system settings have been updated."
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name='level_role',
        description='Add or remove a level-up role reward'
    )
    @app_commands.describe(
        level="The level to assign this role at",
        role="The role to assign (leave empty to remove)"
    )
    @app_commands.default_permissions(administrator=True)
    async def level_role(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role = None
    ):
        """Configure level-up role rewards"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if level < 1:
                raise ValueError("Level must be at least 1")

            if role:
                # Add role reward
                await self.bot.db_manager.add_level_role(interaction.guild_id, level, role.id)
                embed = self.bot.ui_manager.success_embed(
                    "Role Reward Added",
                    f"Members will receive the {role.mention} role when they reach level {level}"
                )
            else:
                # Remove role reward
                if await self.bot.db_manager.remove_level_role(interaction.guild_id, level):
                    embed = self.bot.ui_manager.success_embed(
                        "Role Reward Removed",
                        f"The role reward for level {level} has been removed"
                    )
                else:
                    embed = self.bot.ui_manager.error_embed(
                        "Not Found",
                        f"No role reward found for level {level}"
                    )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))