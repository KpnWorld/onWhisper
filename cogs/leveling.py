import discord
from discord.ext import commands
from typing import Optional
import math
from datetime import datetime, timedelta
from utils.db_manager import DBManager
import json

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
        try:
            if message.author.bot or not message.guild:
                return

            # Verify bot permissions first
            if not message.guild.me.guild_permissions.send_messages:
                return

            # Check if leveling is enabled with DB error handling
            try:
                config = await self.db_manager.get_data('xp_config', str(message.guild.id)) or {}
            except Exception as e:
                print(f"DB Error in leveling: {e}")
                return

            if not config.get('enabled', True):
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
                    # Add this after updating XP and level
                    await self.check_level_roles(message.author, new_level)
            
            except Exception as e:
                print(f"Error in leveling system: {e}")

        except Exception as e:
            print(f"Error in leveling: {e}")

    @commands.hybrid_command(description="Check your or another user's level")
    async def level(self, ctx, user: Optional[discord.Member] = None):
        try:
            # Verify bot permissions
            if not ctx.channel.permissions_for(ctx.guild.me).embed_links:
                await ctx.send("I need the 'Embed Links' permission!")
                return

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
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to show level information.")
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

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

    async def check_level_roles(self, member: discord.Member, new_level: int):
        """Check and assign any level roles the member should have"""
        try:
            # Get all level roles for this guild
            prefix = f"{self.db_manager.prefix}level_roles:{member.guild.id}:"
            for key in self.db_manager.db.keys():
                if key.startswith(prefix):
                    data = json.loads(self.db_manager.db[key])
                    if data['level'] <= new_level:  # Member qualifies for this role
                        role = member.guild.get_role(data['role_id'])
                        if role and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Reached level {new_level}")
                                # Optionally notify the member
                                embed = self.ui.success_embed(
                                    "New Role Unlocked!",
                                    f"You received the {role.mention} role for reaching level {new_level}!"
                                )
                                try:
                                    await member.send(embed=embed)
                                except:
                                    pass  # Ignore if DM fails
                            except discord.Forbidden:
                                print(f"Cannot assign level role {role.name} to {member}")
                                
        except Exception as e:
            print(f"Error checking level roles: {e}")

async def setup(bot):
    await bot.add_cog(Leveling(bot))