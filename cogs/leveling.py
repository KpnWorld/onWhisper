import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import datetime
import math
import random  # For XP randomization

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _calculate_level(self, xp: int) -> tuple[int, int, int, float]:
        """Calculate level and XP progress from total XP Returns (level, current_xp, xp_needed, progress_percentage)"""
        level = int((xp / 100) ** 0.5)
        total_for_current = level ** 2 * 100
        total_for_next = (level + 1) ** 2 * 100
        current_xp = xp - total_for_current
        xp_needed = total_for_next - total_for_current
        progress = current_xp / xp_needed
        return level, current_xp, xp_needed, progress

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
                
                config = await self.bot.db_manager.get_guild_config(interaction.guild_id)
                xp_enabled = config.get("xp_enabled", True)
                
                if not xp_enabled:
                    return await interaction.response.send_message(
                        "⚠️ XP system is currently disabled on this server.",
                        ephemeral=True
                    )
                
                if not xp_data:
                    message = "You haven't earned any XP yet!" if target == interaction.user else f"{target.display_name} hasn't earned any XP yet!"
                    return await interaction.response.send_message(
                        message,
                        ephemeral=True
                    )

                level, current_xp, xp_needed, progress = self._calculate_level(xp_data["xp"])

                # Create fancy progress bar
                bar_length = 20
                filled = int(bar_length * progress)
                gradient = ["▰", "▰", "▰", "▱", "▱"]  # More filled chars for better visibility
                progress_bar = ""
                
                for i in range(bar_length):
                    if i < filled:
                        progress_bar += gradient[min(int((i / filled) * 3), 2)]
                    else:
                        progress_bar += gradient[min(3 + int((i - filled) / (bar_length - filled)), 4)]

                # Calculate time until next XP gain is available
                cooldown = config.get("xp_cooldown", 60)
                last_xp = xp_data.get("last_xp_gain")
                cooldown_text = ""
                
                if last_xp:
                    try:
                        last_xp_time = datetime.strptime(last_xp, '%Y-%m-%d %H:%M:%S.%f')
                        time_passed = (datetime.utcnow() - last_xp_time).total_seconds()
                        if time_passed < cooldown:
                            cooldown_text = f"\nNext XP in: {int(cooldown - time_passed)}s"
                    except (ValueError, TypeError):
                        pass

                embed = discord.Embed(
                    title=f"Level Status for {target.display_name}",
                    color=target.color or discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=target.display_avatar.url)
                rate = config.get("xp_rate", 15)
                messages_needed = xp_needed // rate
                
                embed.add_field(
                    name="Level Status",
                    value=f"""
                    **Current Level:** {level:,}
                    **Total XP:** {xp_data['xp']:,} XP
                    **XP Rate:** {rate} XP per message
                    """.strip(),
                    inline=True
                )
                
                embed.add_field(
                    name="Progress Information",
                    value=f"""
                    **Messages until next level:** ~{messages_needed:,}
                    **XP until next level:** {xp_needed - current_xp:,} XP
                    {cooldown_text}
                    """.strip(),
                    inline=True
                )
                
                embed.add_field(
                    name=f"Level Progress - {current_xp:,}/{xp_needed:,} XP ({progress:.1%})",
                    value=progress_bar,
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

                    level = self._calculate_level(entry["xp"])[0]
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
            
        # Ignore commands
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        try:
            # Get guild config
            config = await self.bot.db_manager.get_guild_config(message.guild.id)
            if not config or not config.get("xp_enabled", True):
                return

            # Check cooldown
            cooldown = config.get("xp_cooldown", 60)
            user_data = await self.bot.db_manager.get_user_xp(message.guild.id, message.author.id)
            
            if user_data and user_data.get("last_xp_gain"):
                try:
                    last_xp = datetime.strptime(user_data["last_xp_gain"], '%Y-%m-%d %H:%M:%S.%f')
                    if (datetime.utcnow() - last_xp).total_seconds() < cooldown:
                        return
                except (ValueError, TypeError):
                    pass # Invalid date format, proceed with XP gain

            # Calculate base XP amount with random bonus
            xp_amount = config.get("xp_rate", 15)
            bonus_range = int(xp_amount * 0.2)  # ±20% variation
            if bonus_range > 0:
                xp_amount += random.randint(-bonus_range, bonus_range)
                xp_amount = max(1, xp_amount)  # Ensure at least 1 XP
            
            # Add XP and check for level up
            result = await self.bot.db_manager.add_xp(
                message.guild.id,
                message.author.id,
                xp_amount
            )

            if result and result.get("leveled_up"):
                # Check for level-up roles and rewards
                new_level = result["level"]
                level_role = await self.bot.db_manager.get_level_role(
                    message.guild.id,
                    new_level
                )

                # Calculate stats for new level
                _, current_xp, xp_needed, progress = self._calculate_level(result["xp"])
                
                # Create a celebratory progress bar
                bar_length = 10
                progress_bar = "▰" * bar_length  # Full bar for celebration
                
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"Congratulations {message.author.mention}!\nYou've reached **Level {new_level:,}**!",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(
                    name="New Level Progress",
                    value=f"{progress_bar} (0/{xp_needed:,} XP)",
                    inline=False
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