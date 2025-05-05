import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import math
from typing import Optional

class LevelingCog(commands.Cog):
    """Handles user XP and leveling system"""
    
    def __init__(self, bot):
        self.bot = bot
        self._cd = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.member)

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a specific level"""
        return math.floor(100 * (level ** 1.5))

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP"""
        return math.floor((xp / 100) ** (1/1.5))

    # Main levels command group
    level = app_commands.Group(
        name="level",
        description="Level and XP related commands"
    )

    @level.command(name="check")
    @app_commands.describe(
        user="The user to check (leave empty to check yourself)"
    )
    async def level_check(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Check your or another user's level and XP"""
        try:
            target = user or interaction.user
            data = await self.bot.db_manager.get_user_level_data(interaction.guild_id, target.id)
            
            if not data:
                raise ValueError("No level data found for this user")
            
            current_xp = data.get('xp', 0)
            current_level = data.get('level', 0)
            next_level_xp = self.calculate_xp_for_level(current_level + 1)
            
            progress = (current_xp - self.calculate_xp_for_level(current_level)) / (next_level_xp - self.calculate_xp_for_level(current_level)) * 100
            
            embed = self.bot.ui_manager.xp_embed(
                f"{target.display_name}'s Level Stats",
                f"Level: {current_level}\nXP: {current_xp}/{next_level_xp}\nProgress to next level: {progress:.1f}%"
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "No Data",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @level.command(name="leaderboard")
    @app_commands.describe(
        page="Page number to view"
    )
    async def level_leaderboard(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = 1
    ):
        """View the server's level leaderboard"""
        try:
            if page < 1:
                raise ValueError("Page number must be positive")
            
            per_page = 10
            data = await self.bot.db_manager.get_guild_leaderboard(interaction.guild_id)
            
            if not data:
                raise ValueError("No level data found for this server")
            
            total_pages = math.ceil(len(data) / per_page)
            if page > total_pages:
                raise ValueError(f"Invalid page number. Maximum page is {total_pages}")
            
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_data = data[start_idx:end_idx]
            
            description = []
            for i, entry in enumerate(page_data, start=start_idx + 1):
                member = interaction.guild.get_member(int(entry['user_id']))
                if member:
                    description.append(
                        f"{i}. {member.mention} - Level {entry['level']} ({entry['xp']} XP)"
                    )
            
            if not description:
                raise ValueError("No active users found on this page")
            
            embed = self.bot.ui_manager.xp_embed(
                f"Level Leaderboard - Page {page}/{total_pages}",
                "\n".join(description)
            )
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Input",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @level.command(name="rewards")
    async def level_rewards(
        self,
        interaction: discord.Interaction
    ):
        """View available level-up role rewards"""
        try:
            rewards = await self.bot.db_manager.get_level_roles(interaction.guild_id)
            
            if not rewards:
                raise ValueError("No level rewards have been configured")
            
            # Sort rewards by level
            rewards.sort(key=lambda x: x[0])
            
            description = []
            for level, role_id in rewards:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    description.append(f"Level {level}: {role.mention}")
            
            if not description:
                raise ValueError("No valid level rewards found")
            
            embed = self.bot.ui_manager.xp_embed(
                "Level Rewards",
                "\n".join(description)
            )
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "No Rewards",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

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
                # Get level roles and sort by level to ensure roles are given in order
                level_roles = await self.bot.db_manager.get_level_roles(message.guild.id)
                level_roles.sort(key=lambda x: x[0])
                
                awarded_roles = []
                for level, role_id in level_roles:
                    # Check if this role should be awarded
                    if old_level < level <= new_level:
                        role = message.guild.get_role(int(role_id))
                        if role:
                            try:
                                await message.author.add_roles(role)
                                awarded_roles.append(role.mention)
                            except discord.Forbidden:
                                print(f"Failed to give role {role.name} due to permissions")

                # Create level up message
                if awarded_roles:
                    embed = self.bot.ui_manager.xp_embed(
                        "Level Up!",
                        f"🎉 {message.author.mention} reached level {new_level} and earned: {', '.join(awarded_roles)}!"
                    )
                else:
                    embed = self.bot.ui_manager.xp_embed(
                        "Level Up!",
                        f"🎉 {message.author.mention} reached level {new_level}!"
                    )
                await message.channel.send(embed=embed)

        except Exception as e:
            print(f"Error in XP handling: {e}")

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))