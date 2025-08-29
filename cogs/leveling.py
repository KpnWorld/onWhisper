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
        xp = row["xp"]
        level = row["level"]

        # Calculate new level
        new_level = int(xp ** 0.5 // 1)  # Example: sqrt(xp) as leveling curve
        if new_level > level:
            await self.db.set_user_level(message.guild.id, message.author.id, new_level)
            logger.info(f"{message.author} leveled up to {new_level} in guild {message.guild.id}")

            level_up_message = await self.config.get(message.guild.id, "level_up_message")
            level_up_message = level_up_message.format(user=message.author.mention, level=new_level)

            level_channel_id = await self.config.get(message.guild.id, "level_channel")
            if level_channel_id and level_channel_id != "None":
                channel = message.guild.get_channel(int(level_channel_id)) or message.channel
            else:
                channel = message.channel

            await channel.send(level_up_message)

    @app_commands.command(name="level", description="Show your current level and XP progress")
    async def level_cmd(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        user = user or interaction.user
        row = await self.db.fetchone(
            "SELECT xp, level FROM leveling_users WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, user.id)
        )
        xp = row["xp"] if row else 0
        level = row["level"] if row else 0
        next_level_xp = (level + 1) ** 2  # using same sqrt leveling curve
        progress = min(int((xp / next_level_xp) * 20), 20)
        bar = "█" * progress + "░" * (20 - progress)

        embed = discord.Embed(
            title=f"{user.display_name}'s Level",
            description=f"Level: {level}\nXP: {xp}/{next_level_xp}\n`{bar}`",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top users in the guild")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await self.db.get_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            await interaction.response.send_message("No leaderboard data available.")
            return

        description = ""
        for i, r in enumerate(rows, 1):
            user = interaction.guild.get_member(r["user_id"])
            description += f"**{i}. {user.display_name if user else 'Unknown'}** — Level {r['level']} ({r['xp']} XP)\n"

        embed = discord.Embed(
            title=f"{interaction.guild.name} Leaderboard",
            description=description,
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
