import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import math
from typing import Optional

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a specific level"""
        return math.floor(100 * (level ** 1.5))

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP"""
        return math.floor((xp / 100) ** (1/1.5))

    @app_commands.command(
        name="config_xp",
        description="Configure XP system settings"
    )
    @app_commands.describe(
        action="The setting to configure",
        value="The value to set (required for rate and cooldown)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set XP rate (1-100)", value="rate"),
        app_commands.Choice(name="Set cooldown (seconds)", value="cooldown"),
        app_commands.Choice(name="Toggle system", value="toggle")
    ])
    @app_commands.default_permissions(administrator=True)
    async def config_xp(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[int] = None
    ):
        """Configure XP system settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action in ["rate", "cooldown"] and value is None:
                raise ValueError(f"Value is required for {action} configuration")

            if action == "rate":
                if value < 1 or value > 100:
                    raise ValueError("XP rate must be between 1 and 100")
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'rate', value)
                embed = self.bot.ui_manager.success_embed(
                    "XP Rate Updated",
                    f"Members will now gain {value} XP per message"
                )

            elif action == "cooldown":
                if value < 0:
                    raise ValueError("Cooldown cannot be negative")
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'cooldown', value)
                embed = self.bot.ui_manager.success_embed(
                    "XP Cooldown Updated",
                    f"Members must now wait {value} seconds between XP gains"
                )

            else:  # toggle
                settings = await self.bot.db_manager.get_section(interaction.guild_id, 'xp_settings')
                enabled = not settings.get('enabled', True)
                await self.bot.db_manager.update_xp_config(interaction.guild_id, 'enabled', enabled)
                embed = self.bot.ui_manager.success_embed(
                    "XP System Updated",
                    f"XP gain has been {'enabled' if enabled else 'disabled'}"
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_level",
        description="Configure level-up role rewards"
    )
    @app_commands.describe(
        action="Whether to add, remove, or list level rewards",
        level="The level to configure (not needed for list)",
        role="The role to give as a reward (only needed for adding)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add reward", value="add"),
        app_commands.Choice(name="Remove reward", value="remove"),
        app_commands.Choice(name="List rewards", value="list")
    ])
    @app_commands.default_permissions(administrator=True)
    async def config_level(
        self,
        interaction: discord.Interaction,
        action: str,
        level: Optional[int] = None,
        role: Optional[discord.Role] = None
    ):
        """Configure level-up role rewards"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action == "list":
                rewards = await self.bot.db_manager.get_level_roles(interaction.guild_id)

                if not rewards:
                    embed = self.bot.ui_manager.info_embed(
                        "No Level Rewards",
                        "No level-up role rewards have been set"
                    )
                    await interaction.response.send_message(embed=embed)
                    return

                embed = self.bot.ui_manager.info_embed(
                    "Level Rewards",
                    "Current level-up role rewards:"
                )

                for level, role_id in sorted(rewards):
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        embed.add_field(
                            name=f"Level {level}",
                            value=role.mention,
                            inline=False
                        )

                await interaction.response.send_message(embed=embed)
                return

            # For add/remove actions, level is required
            if level is None:
                raise ValueError("Level is required for add/remove actions")

            if level < 1:
                raise ValueError("Level must be at least 1")

            if action == "add":
                if not role:
                    raise ValueError("Role is required when adding a reward")
                
                await self.bot.db_manager.add_level_role(interaction.guild_id, level, role.id)
                embed = self.bot.ui_manager.success_embed(
                    "Level Reward Added",
                    f"Members will receive the {role.mention} role at level {level}"
                )
            else:  # remove
                if await self.bot.db_manager.remove_level_role(interaction.guild_id, level):
                    embed = self.bot.ui_manager.success_embed(
                        "Level Reward Removed",
                        f"Removed the role reward for level {level}"
                    )
                else:
                    embed = self.bot.ui_manager.error_embed(
                        "Not Found",
                        f"No role reward found for level {level}"
                    )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        if message.author.bot or not message.guild:
            return

        try:
            # Get XP settings
            settings = await self.bot.db_manager.get_section(message.guild.id, 'xp_settings')
            if not settings.get('enabled', True):
                return

            # Get user's XP data
            data = await self.bot.db_manager.get_user_level_data(message.guild.id, message.author.id)
            
            # Check cooldown
            now = datetime.utcnow()
            if data.get('last_xp'):
                last_xp = datetime.fromisoformat(data['last_xp'])
                if now - last_xp < timedelta(seconds=settings.get('cooldown', 60)):
                    return

            # Calculate XP gain
            xp_gain = settings.get('rate', 15)
            current_xp = data.get('xp', 0) + xp_gain
            old_level = data.get('level', 0)
            new_level = self.calculate_level_from_xp(current_xp)

            # Update user's XP/level
            await self.bot.db_manager.update_user_level_data(
                message.guild.id,
                message.author.id,
                current_xp,
                new_level,
                now
            )

            # Handle level up
            if new_level > old_level:
                # Check for role rewards
                level_roles = await self.bot.db_manager.get_level_roles(message.guild.id)
                for level, role_id in level_roles:
                    if old_level < level <= new_level:
                        role = message.guild.get_role(int(role_id))
                        if role:
                            try:
                                await message.author.add_roles(role)
                                embed = self.bot.ui_manager.xp_embed(
                                    "Level Up!",
                                    f"🎉 {message.author.mention} reached level {new_level} and earned the {role.mention} role!"
                                )
                            except discord.Forbidden:
                                embed = self.bot.ui_manager.xp_embed(
                                    "Level Up!",
                                    f"🎉 {message.author.mention} reached level {new_level}!\n⚠️ Could not assign role {role.mention} - missing permissions."
                                )
                            await message.channel.send(embed=embed)
                            return

                # If no role rewards, just show level up message
                embed = self.bot.ui_manager.xp_embed(
                    "Level Up!",
                    f"🎉 {message.author.mention} reached level {new_level}!"
                )
                await message.channel.send(embed=embed)

        except Exception as e:
            print(f"Error in XP handling: {e}")

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))