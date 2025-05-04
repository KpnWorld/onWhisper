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
        self._cd = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.member)  # 1 min cooldown

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

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))