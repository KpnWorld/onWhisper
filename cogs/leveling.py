import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import datetime
import math

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _calculate_level(self, xp: int) -> tuple[int, int]:
        """Calculate level and XP progress from total XP"""
        level = int((xp / 100) ** 0.5)
        xp_for_next = (level + 1) ** 2 * 100
        current_xp = xp - (level ** 2 * 100)
        return level, current_xp, xp_for_next - (level ** 2 * 100)

    @app_commands.command(name="level")
    @app_commands.describe(
        action="The action to perform",
        user="The user to check (defaults to you)",
        page="Page number for leaderboard"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="show", value="show"),
        app_commands.Choice(name="leaderboard", value="leaderboard"),
    ])
    async def level(
        self,
        interaction: discord.Interaction,
        action: Literal["show", "leaderboard"],
        user: Optional[discord.Member] = None,
        page: Optional[int] = 1
    ):
        """Check levels and XP"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if action == "show":
                target = user or interaction.user
                xp_data = await self.bot.db_manager.get_user_xp(
                    interaction.guild_id,
                    target.id
                )

                if not xp_data:
                    message = "You haven't earned any XP yet!" if target == interaction.user else f"{target.display_name} hasn't earned any XP yet!"
                    return await interaction.response.send_message(
                        message,
                        ephemeral=True
                    )

                level, current_xp, xp_needed = self._calculate_level(xp_data["xp"])
                progress = current_xp / xp_needed

                # Create progress bar
                bar_length = 20
                filled = int(bar_length * progress)
                progress_bar = f"{'▰' * filled}{'▱' * (bar_length - filled)}"

                embed = discord.Embed(
                    title=f"Level Status for {target.display_name}",
                    color=target.color or discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=target.display_avatar.url)
                
                embed.add_field(
                    name="Current Level",
                    value=f"Level {level:,}",
                    inline=True
                )
                embed.add_field(
                    name="Total XP",
                    value=f"{xp_data['xp']:,} XP",
                    inline=True
                )
                embed.add_field(
                    name="Progress to Next Level",
                    value=f"{progress_bar} ({current_xp:,}/{xp_needed:,} XP)",
                    inline=False
                )

                await interaction.response.send_message(embed=embed)

            elif action == "leaderboard":
                if page < 1:
                    page = 1

                leaderboard = await self.bot.db_manager.get_leaderboard(
                    interaction.guild_id,
                    offset=(page - 1) * 10,
                    limit=10
                )

                if not leaderboard:
                    return await interaction.response.send_message(
                        "No XP data found for this server!",
                        ephemeral=True
                    )

                embed = discord.Embed(
                    title=f"XP Leaderboard - Page {page}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )

                for i, entry in enumerate(leaderboard, start=(page - 1) * 10 + 1):
                    user = interaction.guild.get_member(entry["user_id"])
                    if not user:
                        continue

                    level, current_xp, xp_needed = self._calculate_level(entry["xp"])
                    embed.add_field(
                        name=f"#{i} - {user.display_name}",
                        value=f"Level {level:,} ({entry['xp']:,} XP)",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        if not self.bot.db_manager or not message.guild or message.author.bot:
            return

        try:
            # Get guild config
            config = await self.bot.db_manager.get_guild_config(message.guild.id)
            if not config or not config.get("xp_enabled", True):
                return

            # Check cooldown
            cooldown = config.get("xp_cooldown", 60)
            last_xp = await self.bot.db_manager.get_user_last_xp(
                message.guild.id,
                message.author.id
            )

            if last_xp and (datetime.utcnow() - last_xp).total_seconds() < cooldown:
                return

            # Add XP
            xp_amount = config.get("xp_rate", 15)
            result = await self.bot.db_manager.add_xp(
                message.guild.id,
                message.author.id,
                xp_amount
            )

            if result and result.get("leveled_up"):
                # Check for level-up roles
                new_level = result["level"]
                level_role = await self.bot.db_manager.get_level_role(
                    message.guild.id,
                    new_level
                )

                embed = discord.Embed(
                    title="Level Up!",
                    description=f"🎉 Congratulations {message.author.mention}!\nYou've reached Level {new_level:,}!",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )

                if level_role:
                    role = message.guild.get_role(level_role)
                    if role:
                        try:
                            await message.author.add_roles(role)
                            embed.add_field(
                                name="Role Reward",
                                value=f"You've earned the {role.mention} role!"
                            )
                        except discord.Forbidden:
                            pass

                try:
                    await message.channel.send(embed=embed)
                except discord.Forbidden:
                    pass

        except Exception as e:
            print(f"Error in XP system: {e}")

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))