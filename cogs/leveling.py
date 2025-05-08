import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import asyncio
from typing import Optional

class LevelingCog(commands.Cog):
    """Handles user XP and leveling system"""
    
    def __init__(self, bot):
        self.bot = bot

    async def _get_user_data(self, guild_id: int, user_id: str) -> dict:
        """Get user XP data with safe defaults"""
        data = await self.bot.db_manager.get_section(guild_id, 'xp_users') or {}
        user_data = data.get(str(user_id), {'xp': 0, 'level': 0, 'last_xp': None})
        
        # Ensure all required fields exist
        if 'xp' not in user_data:
            user_data['xp'] = 0
        if 'level' not in user_data:
            user_data['level'] = self._calculate_level(user_data['xp'])
        if 'last_xp' not in user_data:
            user_data['last_xp'] = None
            
        return user_data

    async def _update_user_data(self, guild_id: int, user_id: str, xp_data: dict) -> bool:
        """Update user XP data"""
        try:
            # Get current XP data
            data = await self.bot.db_manager.get_section(guild_id, 'xp_users') or {}
            
            # Update user data
            data[str(user_id)] = xp_data
            
            # Save back to database
            return await self.bot.db_manager.update_section(guild_id, 'xp_users', data)
        except Exception as e:
            print(f"Error updating XP data: {e}")
            return False

    async def _calculate_level(self, xp: int) -> int:
        """Calculate level from XP amount"""
        return int((xp / 100) ** 0.5)

    async def _get_xp_settings(self, guild_id: int) -> dict:
        """Safely get XP settings"""
        try:
            settings = await self.bot.db_manager.safe_operation(
                'get_section',
                self.bot.db_manager.get_section,
                guild_id,
                'xp_settings'
            )
            return settings or {'rate': 15, 'cooldown': 60, 'enabled': True}
        except Exception as e:
            print(f"Error getting XP settings: {e}")
            return {'rate': 15, 'cooldown': 60, 'enabled': True}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        if message.author.bot or not message.guild:
            return

        try:
            # Get XP settings
            settings = await self.bot.db_manager.get_section(message.guild.id, 'xp_settings') or {}
            if not settings.get('enabled', True):
                return

            rate = settings.get('rate', 15)
            cooldown = settings.get('cooldown', 60)

            # Get user data
            user_data = await self._get_user_data(message.guild.id, str(message.author.id))
            
            # Check cooldown
            if user_data['last_xp']:
                last_xp = datetime.fromisoformat(user_data['last_xp'])
                if (datetime.utcnow() - last_xp).total_seconds() < cooldown:
                    return

            # Add XP
            old_level = user_data['level']
            user_data['xp'] += rate
            user_data['level'] = self._calculate_level(user_data['xp'])
            user_data['last_xp'] = datetime.utcnow().isoformat()

            # Save updated data
            if await self._update_user_data(message.guild.id, str(message.author.id), user_data):
                # Check for level up
                if user_data['level'] > old_level:
                    await self._handle_level_up(message.author, user_data['level'])

        except Exception as e:
            print(f"Error processing XP: {e}")

    async def _handle_level_up(self, member: discord.Member, new_level: int):
        """Handle level up events with safe role assignments"""
        try:
            # Get level roles with safe operation
            roles_data = await self.bot.db_manager.safe_operation(
                'get_section',
                self.bot.db_manager.get_section,
                member.guild.id,
                'level_roles'
            )

            if not roles_data:
                return

            # Find roles to award
            role_id = roles_data.get(str(new_level))
            if not role_id:
                return

            role = member.guild.get_role(int(role_id))
            if not role:
                return

            # Award role and send notification
            try:
                await member.add_roles(role, reason=f"Reached level {new_level}")
                embed = self.bot.ui_manager.success_embed(
                    "Level Up!",
                    f"🎉 Congratulations {member.mention}!\n"
                    f"You reached level {new_level} and earned the {role.mention} role!"
                )
                await member.send(embed=embed)
            except discord.Forbidden:
                print(f"Missing permissions to assign role in {member.guild.id}")
            except Exception as e:
                print(f"Error assigning level role: {e}")

        except Exception as e:
            print(f"Error handling level up: {e}")

    @app_commands.command(
        name="rank",
        description="View your or another user's rank"
    )
    async def rank(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Show rank card for a user"""
        await interaction.response.defer()
        target = user or interaction.user

        try:
            user_data = await self._get_user_data(interaction.guild.id, str(target.id))
            
            # Calculate progress to next level
            current_xp = user_data['xp']
            current_level = user_data['level']
            next_level_xp = (current_level + 1) ** 2 * 100
            progress = (current_xp - (current_level ** 2 * 100)) / (next_level_xp - (current_level ** 2 * 100))

            embed = discord.Embed(
                title=f"{target.display_name}'s Rank",
                color=target.color
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(
                name="Level",
                value=str(current_level),
                inline=True
            )
            embed.add_field(
                name="XP",
                value=f"{current_xp:,}/{next_level_xp:,}",
                inline=True
            )

            # Add progress bar
            progress_bar = self.bot.ui_manager.create_progress_bar(progress)
            embed.add_field(
                name="Progress to Next Level",
                value=progress_bar,
                inline=False
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="leaderboard",
        description="View the server XP leaderboard"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Show server XP leaderboard"""
        await interaction.response.defer()

        try:
            # Get all user XP data with safe operation
            xp_data = await self.bot.db_manager.safe_operation(
                'get_all_xp',
                self.bot.db_manager.get_all_xp,
                interaction.guild.id
            )

            if not xp_data:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.info_embed(
                        "Leaderboard Empty",
                        "No XP data found for this server."
                    )
                )
                return

            # Sort users by XP
            sorted_users = sorted(
                xp_data.items(),
                key=lambda x: x[1]['xp'],
                reverse=True
            )[:10]  # Top 10

            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} Leaderboard",
                color=discord.Color.gold()
            )

            for i, (user_id, data) in enumerate(sorted_users, 1):
                member = interaction.guild.get_member(int(user_id))
                if not member:
                    continue

                embed.add_field(
                    name=f"{i}. {member.display_name}",
                    value=f"Level {data['level']} • {data['xp']:,} XP",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))