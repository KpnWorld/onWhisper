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

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP required for a specific level"""
        return level * level * 100

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

            # Update last message timestamp
            timestamp = int(datetime.utcnow().timestamp())
            await self.db_manager.execute(
                "UPDATE leveling SET last_message = ? WHERE user_id = ? AND guild_id = ?",
                (timestamp, user_id, guild_id)
            )

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

    @app_commands.command()
    async def set_xp_rate(self, interaction: discord.Interaction, rate: int):
        try:
            old_rate = self.xp_rate
            self.xp_rate = max(1, min(rate, 100))

            await self.ui_manager.send_config_update(
                interaction,
                "XP System Configuration",
                "XP rate has been updated",
                f"XP Rate: {old_rate}",
                f"XP Rate: {self.xp_rate}",
                "This affects how much XP users earn per message"
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "XP Config Error",
                f"Failed to update XP rate: {str(e)}"
            )

    @app_commands.command(name="set-xp-cooldown", description="Set the cooldown between XP gains")
    @app_commands.describe(seconds="The cooldown in seconds between XP gains")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_xp_cooldown(self, interaction: discord.Interaction, seconds: int):
        try:
            old_cooldown = self.xp_cooldown
            self.xp_cooldown = max(1, min(seconds, 3600))
            
            await self.ui_manager.send_config_update(
                interaction,
                "XP System Configuration",
                "Cooldown settings have been updated.",
                f"Cooldown: {old_cooldown} seconds",
                f"Cooldown: {self.xp_cooldown} seconds",
                "This change affects how frequently users can gain XP from messages."
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "XP Config Error",
                f"Failed to update XP cooldown: {str(e)}"
            )

    @app_commands.command(name="set-level-role")
    @app_commands.describe(level="Level to assign role at", role="Role to assign")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_level_role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        """Set a role to be given at a specific level"""
        try:
            self.level_roles[level] = role.name
            await self.ui_manager.send_embed(
                interaction,
                title="Level Role Set",
                description=f"Role {role.mention} will be given at level {level}",
                command_type="Administrator"
            )
        except Exception as e:
            await self.ui_manager.error_embed(
                interaction,
                title="Error",
                description=f"Failed to set level role: {str(e)}",
                command_type="Administrator" 
            )

    # =========================
    # 👤 User Commands
    # =========================

    @app_commands.command(name="level")
    async def level(self, interaction: discord.Interaction, user: discord.User = None):
        try:
            target = user or interaction.user
            result = await self.db_manager.get_user_leveling(target.id, interaction.guild.id)
            
            if not result:
                await self.ui_manager.send_response(
                    interaction,
                    title="Level Status",
                    description=f"Leveling information for {target.mention}",
                    command_type="leveling",
                    fields=[{"name": "Status", "value": "No experience earned yet"}],
                    thumbnail_url=target.display_avatar.url
                )
                return

            level, xp = result
            next_level = level + 1
            next_level_xp = self.calculate_xp_for_level(next_level)
            progress = (xp / next_level_xp) * 100

            level_info = {
                "Current Level": level,
                "Total XP": f"{xp:,}",
                "Required XP": f"{next_level_xp:,}",
                "Progress": f"{progress:.1f}%"
            }

            roles_info = self.get_level_role_progress(level)

            await self.ui_manager.send_response(
                interaction,
                title="Level Statistics",
                description=f"Level details for {target.mention}",
                command_type="leveling",
                fields=[
                    {"name": "📊 Level Info", "value": level_info, "inline": False},
                    {"name": "🏆 Role Progress", "value": roles_info, "inline": False},
                    {"name": "Next Level", "value": f"Level {next_level} - {next_level_xp - xp:,} XP remaining", "inline": False}
                ],
                thumbnail_url=target.display_avatar.url
            )
        except Exception as e:
            await self.ui_manager.send_error(interaction, "Level Check Failed", str(e))

    def get_level_role_progress(self, current_level: int) -> str:
        """Get formatted string of level roles and their unlock status"""
        role_progress = []
        for level, role_name in sorted(self.level_roles.items()):
            status = "✅" if current_level >= level else "❌"
            role_progress.append(f"{status} Level {level}: {role_name}")
        return "\n".join(role_progress) if role_progress else "No level roles configured"

async def setup(bot):
    await bot.add_cog(Leveling(bot))
