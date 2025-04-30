import discord
from discord.ext import commands
from typing import Optional
import math
from datetime import datetime, timedelta
import asyncio
import json

class LeaderboardView(discord.ui.View):
    def __init__(self, users, per_page=10):
        super().__init__(timeout=180)
        self.users = users
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = math.ceil(len(users) / per_page)
        
        # Disable buttons if only one page
        if self.total_pages <= 1:
            self.children[0].disabled = True
            self.children[1].disabled = True

    async def update_message(self, interaction: discord.Interaction):
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_users = self.users[start:end]
        
        description = "\n".join(
            f"{i+1+start}. {user.mention} - Level {level} ({xp} XP)"
            for i, (user, level, xp) in enumerate(current_users)
        )
        
        embed = discord.Embed(
            title="Server Leaderboard",
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % self.total_pages
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % self.total_pages
        await self.update_message(interaction)

class Leveling(commands.Cog):
    """User XP, stats, and leaderboard"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())
        self.xp_cooldown = {}
        self.base_xp = 15
        self.cooldown = 60

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Leveling cog")
                return
            self._ready.set()
            print("✅ Leveling cog ready")
        except Exception as e:
            print(f"❌ Error setting up Leveling cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    def calculate_level(self, xp):
        """Calculate level from XP using a logarithmic formula"""
        return int(math.log(xp / 100 + 1, 1.5))

    def calculate_xp_for_level(self, level):
        """Calculate XP needed for a specific level"""
        return int(100 * (1.5 ** level - 1))

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle XP gain from messages"""
        if message.author.bot or not message.guild:
            return

        try:
            # Get guild settings
            settings = await self.db_manager.get_guild_data(message.guild.id)
            xp_settings = settings.get('xp_settings', {})
            
            if not xp_settings.get('enabled', True):
                return

            # Get XP settings
            xp_rate = xp_settings.get('rate', self.base_xp)
            cooldown = xp_settings.get('cooldown', self.cooldown)

            # Check cooldown using aware datetime
            key = f"{message.author.id}-{message.guild.id}"
            now = discord.utils.utcnow()
            if key in self.xp_cooldown:
                if now < self.xp_cooldown[key]:
                    return

            # Get user data
            user_data = await self.db_manager.get_user_level_data(message.guild.id, message.author.id)
            current_xp = user_data.get('xp', 0)
            current_level = user_data.get('level', 0)

            # Add XP and update level
            new_xp = current_xp + xp_rate
            new_level = self.calculate_level(new_xp)

            # Update user data
            await self.db_manager.update_user_level_data(
                message.guild.id,
                message.author.id,
                new_xp,
                new_level,
                now  # Use aware datetime
            )

            # Set cooldown using aware datetime
            self.xp_cooldown[key] = now + timedelta(seconds=cooldown)

            # Handle level up
            if new_level > current_level:
                # Get level up message settings
                levelup_settings = settings.get('level_up', {})
                if levelup_settings.get('enabled', True):
                    msg_format = levelup_settings.get('message', "{user} reached level {level}!")
                    msg_duration = levelup_settings.get('duration', 0)  # 0 means permanent
                    
                    # Replace placeholders
                    msg = msg_format.replace("{user}", message.author.mention)
                    msg = msg.replace("{level}", str(new_level))
                    
                    # Send in the channel where user leveled up
                    sent = await message.channel.send(msg)
                    
                    # Delete after duration if set
                    if msg_duration > 0:
                        await sent.delete(delay=msg_duration)

                # Check for role rewards
                await self.check_level_roles(message.author, new_level)

        except Exception as e:
            print(f"Error in XP processing: {e}")

    @commands.hybrid_group(name="level")
    async def level(self, ctx):
        """User XP, stats, and leaderboard commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @level.command(name="view")
    async def level_view(self, ctx, user: Optional[discord.Member] = None):
        """Check your or another user's XP level"""
        try:
            target = user or ctx.author
            data = await self.db_manager.get_user_level_data(ctx.guild.id, target.id)
            
            if not data:
                if target == ctx.author:
                    await ctx.send("You haven't earned any XP yet!")
                else:
                    await ctx.send(f"{target.display_name} hasn't earned any XP yet!")
                return

            current_xp = data.get('xp', 0)
            current_level = data.get('level', 0)
            next_level_xp = self.calculate_xp_for_level(current_level + 1)
            progress = (current_xp - self.calculate_xp_for_level(current_level)) / (next_level_xp - self.calculate_xp_for_level(current_level))
            
            # Create progress bar
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "█" * filled + "░" * (bar_length - filled)

            embed = self.ui.info_embed(
                f"{target.display_name}'s Level Stats",
                f"Level: {current_level}\n"
                f"XP: {current_xp}/{next_level_xp}\n"
                f"Progress: {bar} ({progress:.1%})"
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @level.command(name="leaderboard")
    async def level_leaderboard(self, ctx):
        """Show server XP leaderboard"""
        try:
            all_data = await self.db_manager.get_all_levels(ctx.guild.id)
            if not all_data:
                await ctx.send("No XP data available yet!")
                return

            # Sort users by XP
            user_list = []
            for user_id, data in all_data.items():
                member = ctx.guild.get_member(int(user_id))
                if member:  # Only include users still in the server
                    user_list.append((
                        member,
                        data.get('level', 0),
                        data.get('xp', 0)
                    ))
            
            user_list.sort(key=lambda x: x[2], reverse=True)
            
            if not user_list:
                await ctx.send("No active users with XP!")
                return

            view = LeaderboardView(user_list)
            await view.update_message(await ctx.send(embed=discord.Embed()))

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @level.command(name="rewards")
    async def level_rewards(self, ctx):
        """Display all level-up role rewards"""
        try:
            rewards = await self.db_manager.get_level_rewards(ctx.guild.id)
            
            if not rewards:
                await ctx.send("No level rewards configured!")
                return
                
            description = "**Level Role Rewards:**\n\n" + "\n".join(
                f"Level {level}: {ctx.guild.get_role(role_id).mention}"
                for level, role_id in rewards
                if ctx.guild.get_role(role_id)
            )
            
            embed = self.ui.info_embed(
                "Level Rewards",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    async def check_level_roles(self, member: discord.Member, new_level: int):
        """Check and assign any level roles the member should have"""
        try:
            rewards = await self.db_manager.get_level_rewards(member.guild.id)
            
            for level, role_id in rewards:
                if level <= new_level:
                    role = member.guild.get_role(role_id)
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(
                                role,
                                reason=f"Reached level {new_level}"
                            )
                        except discord.Forbidden:
                            print(f"Cannot assign level role {role.name}")
                        except Exception as e:
                            print(f"Error assigning level role: {e}")
                            
        except Exception as e:
            print(f"Error checking level roles: {e}")

async def setup(bot):
    await bot.add_cog(Leveling(bot))