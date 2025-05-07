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
        self._xp_locks = {}  # Lock per user for XP updates

    async def _get_user_data(self, guild_id: int, user_id: str) -> dict:
        """Safely get user XP data"""
        try:
            data = await self.bot.db_manager.safe_operation(
                'get_user_xp',
                self.bot.db_manager.get_user_xp,
                guild_id,
                user_id
            )
            if not data:
                data = {'xp': 0, 'level': 0, 'last_xp': None}
            elif 'level' not in data:
                data['level'] = await self._calculate_level(data['xp'])
            return data
        except Exception as e:
            print(f"Error getting user XP data: {e}")
            return {'xp': 0, 'level': 0, 'last_xp': None}

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
        """Award XP for messages"""
        if (not message.guild or message.author.bot or 
            message.content.startswith(self.bot.command_prefix)):
            return

        settings = await self._get_xp_settings(message.guild.id)
        if not settings['enabled']:
            return

        # Get lock for this user in this guild
        lock_key = f"{message.guild.id}:{message.author.id}"
        if lock_key not in self._xp_locks:
            self._xp_locks[lock_key] = asyncio.Lock()

        async with self._xp_locks[lock_key]:
            try:
                # Use transaction for XP updates
                async with await self.bot.db_manager.transaction(message.guild.id, 'xp') as txn:
                    user_data = await self._get_user_data(message.guild.id, str(message.author.id))
                    
                    # Check cooldown
                    if user_data['last_xp']:
                        last_xp = datetime.fromisoformat(user_data['last_xp'])
                        if (datetime.utcnow() - last_xp).total_seconds() < settings['cooldown']:
                            return

                    # Award XP
                    old_level = user_data['level']
                    user_data['xp'] += settings['rate']
                    user_data['level'] = await self._calculate_level(user_data['xp'])
                    user_data['last_xp'] = datetime.utcnow().isoformat()

                    # Update user data
                    success = await self.bot.db_manager.safe_operation(
                        'update_user_xp',
                        self.bot.db_manager.update_user_xp,
                        message.guild.id,
                        str(message.author.id),
                        user_data
                    )

                    if not success:
                        return

                    # Handle level up
                    if user_data['level'] > old_level:
                        await self._handle_level_up(message, user_data['level'])

            except Exception as e:
                print(f"Error processing XP: {e}")

    async def _handle_level_up(self, message: discord.Message, new_level: int):
        """Handle level up events with safe role assignments"""
        try:
            # Get level roles with safe operation
            roles_data = await self.bot.db_manager.safe_operation(
                'get_section',
                self.bot.db_manager.get_section,
                message.guild.id,
                'level_roles'
            )

            if not roles_data:
                return

            # Find roles to award
            role_id = roles_data.get(str(new_level))
            if not role_id:
                return

            role = message.guild.get_role(int(role_id))
            if not role:
                return

            # Award role and send notification
            try:
                await message.author.add_roles(role, reason=f"Reached level {new_level}")
                embed = self.bot.ui_manager.success_embed(
                    "Level Up!",
                    f"🎉 Congratulations {message.author.mention}!\n"
                    f"You reached level {new_level} and earned the {role.mention} role!"
                )
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                print(f"Missing permissions to assign role in {message.guild.id}")
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