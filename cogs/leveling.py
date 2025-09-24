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

    @app_commands.command(name="setlevel", description="Manually set a member's level (Admin only)")
    @app_commands.describe(
        member="The member to set level for",
        level="The level to set (minimum 0)"
    )
    async def setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        if level < 0:
            await interaction.response.send_message("Level must be 0 or higher.", ephemeral=True)
            return
        
        await self.db.set_user_level(interaction.guild.id, member.id, level)
        
        embed = discord.Embed(
            title="Level Set",
            description=f"Set {member.mention}'s level to **{level}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="add-level-role", description="Add a role reward for reaching a specific level (Admin only)")
    @app_commands.describe(
        level="The level required to earn this role",
        role="The role to give when reaching this level"
    )
    async def add_level_role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        if level < 1:
            await interaction.response.send_message("Level must be 1 or higher.", ephemeral=True)
            return
        
        await self.db.add_level_reward(interaction.guild.id, level, role.id)
        
        embed = discord.Embed(
            title="Level Role Added",
            description=f"Added {role.mention} as reward for reaching level **{level}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove-level-role", description="Remove role reward for a specific level (Admin only)")
    @app_commands.describe(level="The level to remove role reward from")
    async def remove_level_role(self, interaction: discord.Interaction, level: int):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        await self.db.remove_level_reward(interaction.guild.id, level)
        
        embed = discord.Embed(
            title="Level Role Removed",
            description=f"Removed role reward for level **{level}**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="list-level-roles", description="Show all configured level role rewards")
    async def list_level_roles(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        rewards = await self.db.get_level_rewards(interaction.guild.id)
        
        if not rewards:
            await interaction.response.send_message("No level role rewards configured.", ephemeral=True)
            return
        
        description = ""
        for reward in rewards:
            role = interaction.guild.get_role(reward["role_id"])
            role_mention = role.mention if role else f"<@&{reward['role_id']}> (deleted)"
            description += f"**Level {reward['level']}**: {role_mention}\n"
        
        embed = discord.Embed(
            title="Level Role Rewards",
            description=description,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="level-settings", description="Configure leveling system settings (Admin only)")
    @app_commands.describe(
        setting="The setting to configure",
        value="The value to set (for destination: same, dm, or channel)"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Level-up destination", value="level_up_destination"),
        app_commands.Choice(name="Level-up message", value="level_up_message"),
        app_commands.Choice(name="Level announcement channel", value="level_channel"),
        app_commands.Choice(name="XP rate per message", value="xp_rate"),
        app_commands.Choice(name="XP cooldown (seconds)", value="xp_cooldown")
    ])
    async def level_settings(self, interaction: discord.Interaction, setting: str, value: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        
        # Validate level_up_destination values
        if setting == "level_up_destination":
            if value.lower() not in ["same", "dm", "channel"]:
                await interaction.response.send_message(
                    "Level-up destination must be one of: `same`, `dm`, or `channel`\n\n"
                    "• **same**: Send level-up messages in the same channel where the user gained XP\n"
                    "• **dm**: Send level-up messages directly to the user via DM\n"
                    "• **channel**: Send level-up messages to the configured level announcement channel", 
                    ephemeral=True
                )
                return
            value = value.lower()
        
        # Validate XP rate and cooldown
        elif setting in ["xp_rate", "xp_cooldown"]:
            try:
                int_value = int(value)
                if int_value < 1:
                    await interaction.response.send_message(f"{setting.replace('_', ' ').title()} must be 1 or higher.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message(f"{setting.replace('_', ' ').title()} must be a number.", ephemeral=True)
                return
        
        # Handle channel setting
        elif setting == "level_channel":
            if value.lower() in ["none", "null", "disable", "off"]:
                value = "None"
            else:
                # Try to parse as channel mention or ID
                try:
                    if value.startswith("<#") and value.endswith(">"):
                        channel_id = int(value[2:-1])
                    else:
                        channel_id = int(value)
                    
                    channel = interaction.guild.get_channel(channel_id)
                    if not channel:
                        await interaction.response.send_message("Channel not found. Please provide a valid channel ID or mention.", ephemeral=True)
                        return
                    
                    if not hasattr(channel, 'send'):
                        await interaction.response.send_message("Please select a text channel.", ephemeral=True)
                        return
                    
                    value = str(channel_id)
                except ValueError:
                    await interaction.response.send_message("Invalid channel. Please provide a channel mention or ID.", ephemeral=True)
                    return
        
        # Set the configuration
        await self.config.set(interaction.guild.id, setting, value)
        
        # Create response based on setting
        if setting == "level_up_destination":
            destination_descriptions = {
                "same": "Level-up messages will be sent in the same channel where users gain XP",
                "dm": "Level-up messages will be sent directly to users via DM",
                "channel": "Level-up messages will be sent to the configured level announcement channel"
            }
            description = destination_descriptions[value]
        elif setting == "level_channel":
            if value == "None":
                description = "Level announcement channel disabled"
            else:
                channel = interaction.guild.get_channel(int(value))
                description = f"Level announcements will be sent to {channel.mention if channel else 'the configured channel'}"
        elif setting == "level_up_message":
            description = f"Level-up message set to: {value}"
        else:
            description = f"{setting.replace('_', ' ').title()} set to **{value}**"
        
        embed = discord.Embed(
            title="Leveling Settings Updated",
            description=description,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
