import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import asyncio
from typing import Optional

class LevelingCog(commands.Cog):
    """Handles leveling functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self._xp_cooldowns = {}
        # Set all commands in this cog to "Leveling" category
        for cmd in self.__cog_app_commands__:
            cmd.extras["category"] = "leveling"

    async def _get_user_data(self, guild_id: int, user_id: str) -> dict:
        """Get user XP data with safe defaults"""
        data = await self.bot.db_manager.get_section(guild_id, 'xp_users') or {}
        user_data = data.get(str(user_id), {'xp': 0, 'level': 0, 'last_xp': None})
        
        # Ensure all required fields exist
        if 'xp' not in user_data:
            user_data['xp'] = 0
        if 'level' not in user_data:
            user_data['level'] = 0
            
        return user_data

    async def _update_user_data(self, guild_id: int, user_id: str, xp_data: dict) -> bool:
        """Update user XP data"""
        try:
            data = await self.bot.db_manager.get_section(guild_id, 'xp_users') or {}
            data[str(user_id)] = xp_data
            await self.bot.db_manager.update_section(guild_id, 'xp_users', data)
            return True
        except Exception as e:
            print(f"Error updating XP data: {e}")
            return False

    async def _calculate_level(self, xp: int) -> int:
        """Calculate level from XP"""
        return int((xp / 100) ** 0.5)

    async def _get_xp_settings(self, guild_id: int) -> dict:
        """Get XP settings with defaults"""
        settings = await self.bot.db_manager.get_section(guild_id, 'xp_settings') or {}
        return {
            'enabled': settings.get('enabled', True),
            'rate': settings.get('rate', 15),
            'cooldown': settings.get('cooldown', 60)
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle XP gain from messages"""
        if message.author.bot or not message.guild:
            return
            
        settings = await self._get_xp_settings(message.guild.id)
        if not settings['enabled']:
            return
            
        # Check cooldown
        now = datetime.now().timestamp()
        user_id = str(message.author.id)
        last_xp = self._xp_cooldowns.get(user_id, 0)
        
        if now - last_xp < settings['cooldown']:
            return
            
        self._xp_cooldowns[user_id] = now
        
        # Get current data
        user_data = await self._get_user_data(message.guild.id, user_id)
        current_level = user_data['level']
        
        # Add XP
        user_data['xp'] += settings['rate']
        user_data['last_xp'] = now
        
        # Calculate new level
        new_level = await self._calculate_level(user_data['xp'])
        user_data['level'] = new_level
        
        # Update data
        await self._update_user_data(message.guild.id, user_id, user_data)
        
        # Handle level up
        if new_level > current_level:
            await self._handle_level_up(message.author, new_level)

    async def _handle_level_up(self, member: discord.Member, new_level: int):
        """Handle level up events"""
        try:
            # Send level up message
            embed = self.bot.ui_manager.success_embed(
                "Level Up!",
                f"🎉 {member.mention} has reached level {new_level}!"
            )
            await member.guild.system_channel.send(embed=embed)
            
            # Check for level roles
            config = await self.bot.db_manager.get_section(member.guild.id, 'level_roles') or {}
            role_id = config.get(str(new_level))
            
            if role_id:
                role = member.guild.get_role(int(role_id))
                if role:
                    await member.add_roles(role)
                    
        except Exception as e:
            print(f"Error handling level up: {e}")

    @app_commands.command(
        name="rank",
        description="View your or another user's rank"
    )
    @app_commands.describe(user="The user to check rank for")
    async def rank(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Show a user's rank information"""
        try:
            target = user or interaction.user
            user_data = await self._get_user_data(interaction.guild_id, str(target.id))
            
            embed = discord.Embed(
                title=f"Rank - {target.display_name}",
                color=target.color
            )
            
            embed.add_field(
                name="Level",
                value=str(user_data['level']),
                inline=True
            )
            embed.add_field(
                name="XP",
                value=f"{user_data['xp']:,}",
                inline=True
            )
            
            # Calculate XP to next level
            next_level_xp = ((user_data['level'] + 1) ** 2) * 100
            embed.add_field(
                name="Next Level",
                value=f"{next_level_xp - user_data['xp']:,} XP needed",
                inline=True
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="leaderboard",
        description="View the server XP leaderboard"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Show server XP leaderboard"""
        try:
            data = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_users') or {}
            
            if not data:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.info_embed(
                        "Leaderboard",
                        "No XP data available"
                    )
                )
                return
                
            # Sort users by XP
            sorted_users = sorted(
                data.items(),
                key=lambda x: x[1]['xp'],
                reverse=True
            )[:10]  # Top 10
            
            description = []
            for i, (user_id, user_data) in enumerate(sorted_users, 1):
                member = interaction.guild.get_member(int(user_id))
                if member:
                    description.append(
                        f"{i}. {member.mention} - Level {user_data['level']} ({user_data['xp']:,} XP)"
                    )
            
            embed = discord.Embed(
                title="XP Leaderboard",
                description="\n".join(description),
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))