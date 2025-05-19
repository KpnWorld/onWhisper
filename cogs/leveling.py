import discord
from discord.ext import commands
from discord.commands import slash_command, option
from typing import Optional, Union
import random
import math
from datetime import datetime, timezone

def calculate_level(xp: int) -> int:
    """Calculate level from XP amount"""
    # Level = floor(square_root(XP / 100))
    return math.floor(math.sqrt(xp / 100))

def calculate_xp_for_level(level: int) -> int:
    """Calculate XP needed for a specific level"""
    return level * level * 100

class Leveling(commands.Cog):
    """XP and leveling system"""
    
    def __init__(self, bot):
        self.bot = bot    
        
    @slash_command(name="level", description="Check your or someone else's level")
    @option("member", description="The member to check (leave empty for yourself)", type=discord.Member, required=False)
    async def level(
        self,
        ctx: discord.ApplicationContext,
        member: Optional[discord.Member] = None
    ):
        target = member or ctx.author
        
        # Get XP data
        data = await self.bot.db.get_user_xp(ctx.guild.id, target.id)
        current_xp = data["xp"]
        current_level = data["level"]
        
        # Calculate progress
        xp_for_current = calculate_xp_for_level(current_level)
        xp_for_next = calculate_xp_for_level(current_level + 1)
        xp_progress = current_xp - xp_for_current
        xp_needed = xp_for_next - xp_for_current
        progress_percent = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 100
        
        # Create progress bar (20 segments)
        segments = 20
        filled = round(progress_percent / 100 * segments)
        progress_bar = '█' * filled + '░' * (segments - filled)
        
        embed = discord.Embed(
            title=f"Level Information - {target.display_name}",
            color=target.color
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(
            name="Current Level",
            value=f"Level {current_level}",
            inline=True
        )
        embed.add_field(
            name="Total XP",
            value=f"{current_xp:,} XP",
            inline=True
        )
        embed.add_field(
            name="Rank",
            value=await self._get_rank(ctx.guild.id, target.id),
            inline=True
        )
        
        embed.add_field(
            name=f"Progress to Level {current_level + 1}",
            value=f"`{progress_bar}` {progress_percent:.1f}%\n"
                  f"{xp_progress:,} / {xp_needed:,} XP needed",
            inline=False
        )
        
        # Show unlocked level roles
        level_roles = await self.bot.db.get_level_roles(ctx.guild.id)
        if level_roles:
            unlocked = []
            for role_data in sorted(level_roles, key=lambda x: x["level"]):
                if role_data["level"] <= current_level:
                    role = ctx.guild.get_role(role_data["role_id"])
                    if role:
                        unlocked.append(f"Level {role_data['level']}: {role.mention}")
            
            if unlocked:
                embed.add_field(
                    name="Unlocked Level Roles",
                    value="\n".join(unlocked),
                    inline=False
                )
        
        await ctx.respond(embed=embed)    
        
    @slash_command(name="leaderboard", description="View the XP leaderboard")
    @option("page", description="Page number to view", type=int, min_value=1, default=1)
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext,
        page: int = 1
    ):
        if page < 1:
            await ctx.respond("❌ Page number must be at least 1!")
            return
            
        per_page = 10
        leaderboard = await self.bot.db.get_leaderboard(ctx.guild.id, limit=page * per_page)
        
        if not leaderboard:
            await ctx.respond("No XP data available!")
            return
        
        # Calculate total pages
        total = len(leaderboard)
        pages = math.ceil(total / per_page)
        
        if page > pages:
            await ctx.respond(f"❌ Invalid page number! Maximum page is {pages}")
            return
        
        # Get entries for current page
        start = (page - 1) * per_page
        end = start + per_page
        entries = leaderboard[start:end]
        
        embed = discord.Embed(
            title=f"XP Leaderboard - {ctx.guild.name}",
            color=discord.Color.blue()
        )
        
        for i, entry in enumerate(entries, start=start + 1):
            member = ctx.guild.get_member(entry["user_id"])
            if not member:
                continue
                
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
            embed.add_field(
                name=f"{medal}#{i} {member.display_name}",
                value=f"Level {entry['level']} ({entry['xp']:,} XP)",
                inline=False
            )
        
        embed.set_footer(text=f"Page {page}/{pages}")
        await ctx.respond(embed=embed)
    
    async def _get_rank(self, guild_id: int, user_id: int) -> str:
        """Get user's rank on the leaderboard"""
        leaderboard = await self.bot.db.get_leaderboard(guild_id, limit=None)
        for i, entry in enumerate(leaderboard, 1):
            if entry["user_id"] == user_id:
                return f"#{i}"
        return "Unranked"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle XP gain from messages"""
        # Ignore bots, DMs, and commands
        if (
            message.author.bot or
            not message.guild or
            message.content.startswith(await self.bot.get_prefix(message))
        ):
            return
            
        # Get XP settings
        config = await self.bot.db.get_level_config(message.guild.id)
        cooldown = config["cooldown"]
        min_xp = config["min_xp"]
        max_xp = config["max_xp"]
        
        # Get user's current XP data
        data = await self.bot.db.get_user_xp(message.guild.id, message.author.id)
        last_message = data["last_message_ts"]
        
        # Check cooldown
        now = datetime.now(timezone.utc)
        if last_message:
            last_dt = datetime.fromisoformat(last_message.replace('Z', '+00:00'))
            if (now - last_dt).total_seconds() < cooldown:
                return
        
        # Award XP
        xp_gained = random.randint(min_xp, max_xp)
        old_level = data["level"]
        
        # Update XP
        await self.bot.db.add_xp(message.guild.id, message.author.id, xp_gained)
        
        # Check for level up
        new_total_xp = data["xp"] + xp_gained
        new_level = calculate_level(new_total_xp)
        
        if new_level > old_level:
            # Update level in database
            await self.bot.db.set_xp(
                message.guild.id,
                message.author.id,
                new_total_xp,
                new_level
            )
            
            # Send level up message
            embed = discord.Embed(
                title="Level Up! 🎉",
                description=f"Congratulations {message.author.mention}!\n"
                           f"You've reached **Level {new_level}**!",
                color=discord.Color.green()
            )
            
            try:
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                pass
            
            # Handle level roles
            level_roles = await self.bot.db.get_level_roles(message.guild.id)
            for role_data in level_roles:
                if role_data["level"] == new_level:
                    role = message.guild.get_role(role_data["role_id"])
                    if role:
                        try:
                            await message.author.add_roles(
                                role,
                                reason=f"Reached level {new_level}"
                            )
                        except discord.Forbidden:
                            pass
                    break

def setup(bot):
    bot.add_cog(Leveling(bot))
