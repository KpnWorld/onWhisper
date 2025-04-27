import discord
from discord.commands import slash_command, Option
from discord.ext import commands
from typing import Optional
import math
from datetime import datetime, timedelta
from utils.db_manager import DBManager

class LeaderboardView(discord.ui.View):
    def __init__(self, pages, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.xp_cooldown = {}
        self.base_xp = 15
        self.cooldown = 60

    def calculate_level(self, xp):
        """Calculate level from XP using a logarithmic formula"""
        return int(math.sqrt(xp) // 10)

    def calculate_xp_for_level(self, level):
        """Calculate XP needed for a specific level"""
        return (level * 10) ** 2

    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages"""
        if message.author.bot or not message.guild:
            return

        # Check cooldown
        user_id = message.author.id
        guild_id = message.guild.id
        current_time = datetime.utcnow()
        cooldown_key = f"{user_id}-{guild_id}"

        if cooldown_key in self.xp_cooldown:
            if current_time < self.xp_cooldown[cooldown_key]:
                return
        
        # Award XP
        try:
            # Get current level and XP
            current_data = await self.db_manager.get_user_leveling(user_id, guild_id)
            current_level, current_xp = current_data if current_data else (0, 0)
            
            # Add XP
            new_xp = current_xp + self.base_xp
            new_level = self.calculate_level(new_xp)
            
            # Update database
            await self.db_manager.add_user_leveling(user_id, guild_id, new_level, new_xp)
            
            # Set cooldown
            self.xp_cooldown[cooldown_key] = current_time + timedelta(seconds=self.cooldown)
            
            # Level up notification
            if new_level > current_level:
                description = (
                    f"Congratulations {message.author.mention}!\n"
                    f"You've reached level {new_level}!\n\n"
                    f"Total XP: {new_xp:,}"
                )
                embed = self.bot.create_embed(
                    "🎉 Level Up!",
                    description,
                    command_type="User"
                )
                await message.channel.send(embed=embed)
        
        except Exception as e:
            print(f"Error in leveling system: {e}")

    @discord.slash_command(description="Check your or another user's level")
    async def level(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Show level and XP information for a user"""
        try:
            target = user or interaction.user
            
            # Get level data
            level_data = await self.db_manager.get_user_leveling(target.id, interaction.guild.id)
            if not level_data:
                level, xp = 0, 0
            else:
                level, xp = level_data
            
            # Calculate progress to next level
            next_level_xp = self.calculate_xp_for_level(level + 1)
            current_level_xp = self.calculate_xp_for_level(level)
            xp_needed = next_level_xp - current_level_xp
            xp_progress = xp - current_level_xp
            progress_percent = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 0
            
            # Create progress bar
            progress_bar = "█" * int(progress_percent / 10) + "░" * (10 - int(progress_percent / 10))
            
            description = (
                f"Current Level: {level}\n"
                f"Total XP: {xp:,}\n"
                f"\n"
                f"Progress to Level {level + 1}:\n"
                f"{progress_bar} ({progress_percent:.1f}%)\n"
                f"{xp_progress:,}/{xp_needed:,} XP needed"
            )
            
            embed = self.bot.create_embed(
                f"Level Information: {target.display_name}",
                description,
                command_type="User"
            )
            
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Set the base XP awarded per message")
    @commands.default_member_permissions(administrator=True)
    async def set_xp_rate(self, interaction: discord.Interaction, amount: int):
        """Set the base XP awarded per message (Admin only)"""
        try:
            if amount < 1 or amount > 100:
                embed = self.bot.create_embed(
                    "Invalid XP Rate",
                    "XP rate must be between 1 and 100",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            self.base_xp = amount
            
            embed = self.bot.create_embed(
                "XP Rate Updated",
                f"Base XP per message has been set to {amount}",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Set the cooldown between XP awards")
    @commands.default_member_permissions(administrator=True)
    async def set_xp_cooldown(self, interaction: discord.Interaction, seconds: int):
        """Set the cooldown between XP awards (Admin only)"""
        try:
            if seconds < 0 or seconds > 300:
                embed = self.bot.create_embed(
                    "Invalid Cooldown",
                    "Cooldown must be between 0 and 300 seconds",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            self.cooldown = seconds
            # Clear existing cooldowns
            self.xp_cooldown.clear()
            
            embed = self.bot.create_embed(
                "XP Cooldown Updated",
                f"XP cooldown has been set to {seconds} seconds",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Shows the server's XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Shows the server's XP leaderboard"""
        # Get all leaderboard data
        leaderboard_data = await self.db_manager.get_leaderboard(interaction.guild_id, limit=100)
        
        if not leaderboard_data:
            await interaction.response.send_message("No leaderboard data available yet!")
            return

        # Create pages (10 users per page)
        pages = []
        users_per_page = 10
        for i in range(0, len(leaderboard_data), users_per_page):
            page_data = leaderboard_data[i:i + users_per_page]
            
            embed = discord.Embed(
                title=f"{interaction.guild.name}'s Leaderboard",
                color=discord.Color.blue()
            )
            
            description = ""
            for rank, (user_id, level, xp) in enumerate(page_data, start=i + 1):
                user = interaction.guild.get_member(user_id)
                username = user.display_name if user else f"User {user_id}"
                description += f"#{rank}. {username}\nLevel: {level} | XP: {xp:,}\n\n"
            
            embed.description = description
            embed.set_footer(text=f"Page {len(pages) + 1}/{-(-len(leaderboard_data) // users_per_page)}")
            pages.append(embed)
        
        if pages:
            view = LeaderboardView(pages)
            await interaction.response.send_message(embed=pages[0], view=view)
        else:
            await interaction.response.send_message("No leaderboard data available yet!")

async def setup(bot):
    await bot.add_cog(Leveling(bot))