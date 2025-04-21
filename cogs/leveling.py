import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)
        self.xp_rate = 10  # Default XP per message
        self.xp_cooldown = 10  # Cooldown in seconds
        self.level_roles = {}  # level: role_name

    # =========================
    # 🎮 Core Leveling Logic
    # =========================

    def calculate_level(self, xp: int) -> int:
        return int(xp ** 0.5)

    async def check_role_assignment(self, user: discord.Member, level: int):
        if level in self.level_roles:
            role = discord.utils.get(user.guild.roles, name=self.level_roles[level])
            if role and role not in user.roles:
                await user.add_roles(role)
                await self.remove_lower_level_roles(user, level)

    async def remove_lower_level_roles(self, user: discord.Member, new_level: int):
        for level, role_name in self.level_roles.items():
            if level < new_level:
                role = discord.utils.get(user.guild.roles, name=role_name)
                if role in user.roles:
                    await user.remove_roles(role)

    # =========================
    # 📝 Event Listeners
    # =========================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        try:
            user_id = message.author.id
            guild_id = message.guild.id
            now = datetime.utcnow()

            # Get current XP data
            result = await self.db_manager.get_user_leveling(user_id, guild_id)
            if not result:
                await self.db_manager.add_user_leveling(user_id, guild_id, 1, 0)
                return

            xp, level = result
            # Check cooldown
            if now - datetime.fromisoformat(str(result[2])) < timedelta(seconds=self.xp_cooldown):
                return

            # Add XP and check level up
            xp += self.xp_rate
            new_level = self.calculate_level(xp)
            await self.db_manager.add_user_leveling(user_id, guild_id, new_level, xp)

            # Handle level up
            if new_level > level:
                await self.check_role_assignment(message.author, new_level)
                await message.channel.send(
                    f"🎉 Congratulations {message.author.mention}! You've reached level {new_level}!"
                )
        except Exception as e:
            print(f"Error in leveling: {e}")

    # =========================
    # ⚙️ Admin Commands
    # =========================

    @app_commands.command(name="set-xp-rate", description="Set how much XP users earn per message")
    @app_commands.describe(rate="The amount of XP to award per message")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_xp_rate(self, interaction: discord.Interaction, rate: int):
        try:
            self.xp_rate = max(1, min(rate, 100))  # Clamp between 1-100
            await self.ui_manager.send_embed(
                interaction,
                title="XP Rate Updated",
                description=f"XP per message is now set to **{self.xp_rate}**",
                command_type="Administrator"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="Error",
                description=f"Failed to update XP rate: {str(e)}",
                command_type="Administrator"
            )

    @app_commands.command(name="set-xp-cooldown", description="Set the cooldown between XP gains")
    @app_commands.describe(seconds="The cooldown in seconds between XP gains")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_xp_cooldown(self, interaction: discord.Interaction, seconds: int):
        try:
            self.xp_cooldown = max(1, min(seconds, 3600))  # Clamp between 1-3600
            await self.ui_manager.send_embed(
                interaction,
                title="XP Cooldown Updated",
                description=f"Users can now gain XP every **{self.xp_cooldown}** seconds",
                command_type="Administrator"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="Error",
                description=f"Failed to update cooldown: {str(e)}",
                command_type="Administrator"
            )

    # =========================
    # 👤 User Commands
    # =========================

    @app_commands.command(name="level", description="Check your or another user's level")
    @app_commands.describe(user="The user to check (optional)")
    async def level(self, interaction: discord.Interaction, user: discord.User = None):
        try:
            target = user or interaction.user
            result = await self.db_manager.get_user_leveling(target.id, interaction.guild.id)
            
            if not result:
                await self.ui_manager.send_embed(
                    interaction,
                    title="No Level Data",
                    description=f"{target.name} hasn't earned any XP yet!",
                    command_type="User"
                )
                return

            level, xp = result
            next_level_xp = (level + 1) ** 2
            progress = f"{xp}/{next_level_xp}"

            await self.ui_manager.send_embed(
                interaction,
                title=f"{target.name}'s Level Stats",
                description=f"**Level:** {level}\n**XP:** {progress}\n**Total XP:** {xp}",
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="Error",
                description=f"Failed to get level info: {str(e)}",
                command_type="User"
            )

async def setup(bot):
    await bot.add_cog(Leveling(bot))
