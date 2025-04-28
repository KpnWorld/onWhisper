import discord
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
    async def previous_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page])

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager
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
                embed = self.ui.user_embed(
                    "🎉 Level Up!",
                    description
                )
                await message.channel.send(embed=embed)
        
        except Exception as e:
            print(f"Error in leveling system: {e}")

    @commands.hybrid_command(description="Check your or another user's level")
    async def level(self, ctx, user: Optional[discord.Member] = None):
        """Show level and XP information for a user"""
        try:
            target = user or ctx.author
            
            # Get level data
            level_data = await self.db_manager.get_user_leveling(target.id, ctx.guild.id)
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
            
            embed = self.ui.user_embed(
                f"Level Information: {target.display_name}",
                description
            )
            
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.user_embed(
                "Error",
                str(e)
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Shows the server's XP leaderboard")
    async def leaderboard(self, ctx):
        """Shows the server's XP leaderboard"""
        # Get all leaderboard data
        leaderboard_data = await self.db_manager.get_leaderboard(ctx.guild.id, limit=100)
        
        if not leaderboard_data:
            await ctx.send("No leaderboard data available yet!")
            return

        # Create pages (10 users per page)
        pages = []
        users_per_page = 10
        for i in range(0, len(leaderboard_data), users_per_page):
            page_data = leaderboard_data[i:i + users_per_page]
            
            embed = discord.Embed(
                title=f"{ctx.guild.name}'s Leaderboard",
                color=discord.Color.blue()
            )
            
            description = ""
            for rank, (user_id, level, xp) in enumerate(page_data, start=i + 1):
                user = ctx.guild.get_member(user_id)
                username = user.display_name if user else f"User {user_id}"
                description += f"#{rank}. {username}\nLevel: {level} | XP: {xp:,}\n\n"
            
            embed.description = description
            embed.set_footer(text=f"Page {len(pages) + 1}/{-(-len(leaderboard_data) // users_per_page)}")
            pages.append(embed)
        
        if pages:
            view = LeaderboardView(pages)
            await ctx.send(embed=pages[0], view=view)
        else:
            await ctx.send("No leaderboard data available yet!")

async def setup(bot):
    await bot.add_cog(Leveling(bot))