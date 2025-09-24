# cogs/leveling.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
from utils.db_manager import DBManager
from utils.config import ConfigManager

import logging

logger = logging.getLogger("onWhisper.Leveling")


class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db_manager
        self.config: ConfigManager = bot.config_manager

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        leveling_enabled = await self.config.get(message.guild.id, "leveling_enabled")
        if not leveling_enabled:
            return

        xp_rate = await self.config.get(message.guild.id, "xp_rate")
        await self.db.add_xp(message.guild.id, message.author.id, xp_rate)
        logger.info(f"Added {xp_rate} XP to {message.author} in guild {message.guild.id}")

        # Fetch user's XP and level
        row = await self.db.fetchone(
            "SELECT xp, level FROM leveling_users WHERE guild_id = ? AND user_id = ?",
            (message.guild.id, message.author.id)
        )
        if not row:
            return
        xp = row["xp"]
        level = row["level"]

        # Calculate new level
        new_level = int(xp ** 0.5 // 1)  # Example: sqrt(xp) as leveling curve
        if new_level > level:
            await self.db.set_user_level(message.guild.id, message.author.id, new_level)
            logger.info(f"{message.author} leveled up to {new_level} in guild {message.guild.id}")

            level_up_message = await self.config.get(message.guild.id, "level_up_message")
            level_up_message = level_up_message.format(user=message.author.mention, level=new_level)

            # Get level-up destination preference
            destination = await self.config.get(message.guild.id, "level_up_destination", "same")
            
            try:
                if destination == "dm":
                    # Send level-up message via DM
                    await message.author.send(level_up_message)
                elif destination == "channel":
                    # Send to configured level channel
                    level_channel_id = await self.config.get(message.guild.id, "level_channel")
                    if level_channel_id and level_channel_id != "None":
                        channel = message.guild.get_channel(int(level_channel_id))
                        if channel and hasattr(channel, 'send'):
                            await channel.send(level_up_message)
                        else:
                            # Fallback to same channel if level channel not found
                            await message.channel.send(level_up_message)
                    else:
                        # Fallback to same channel if no level channel configured
                        await message.channel.send(level_up_message)
                else:  # destination == "same" (default)
                    # Send to the same channel where the message was sent
                    await message.channel.send(level_up_message)
            except discord.Forbidden:
                # If DM fails or channel permissions issue, fallback to same channel
                try:
                    await message.channel.send(level_up_message)
                except discord.Forbidden:
                    logger.warning(f"Failed to send level-up message for {message.author} in guild {message.guild.id}")

    @app_commands.command(name="level", description="Show your current level and XP progress")
    async def level_cmd(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        target_user = user or interaction.user
        row = await self.db.fetchone(
            "SELECT xp, level FROM leveling_users WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, target_user.id)
        )
        xp = row["xp"] if row else 0
        level = row["level"] if row else 0
        next_level_xp = (level + 1) ** 2  # using same sqrt leveling curve
        progress = min(int((xp / next_level_xp) * 20), 20)
        bar = "█" * progress + "░" * (20 - progress)

        display_name = target_user.display_name if hasattr(target_user, 'display_name') else str(target_user)
        embed = discord.Embed(
            title=f"{display_name}'s Level",
            description=f"Level: {level}\nXP: {xp}/{next_level_xp}\n`{bar}`",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top users in the guild")
    async def leaderboard(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        rows = await self.db.get_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            await interaction.response.send_message("No leaderboard data available.")
            return

        description = ""
        for i, r in enumerate(rows, 1):
            user = interaction.guild.get_member(r["user_id"])
            description += f"**{i}. {user.display_name if user else 'Unknown'}** — Level {r['level']} ({r['xp']} XP)\n"

        guild_name = interaction.guild.name if interaction.guild else "Unknown Guild"
        embed = discord.Embed(
            title=f"{guild_name} Leaderboard",
            description=description,
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
