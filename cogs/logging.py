import random
import discord
from discord import app_commands
from discord.ext import commands
from utils.db_manager import DBManager
from utils.config import ConfigManager


class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db  # type: ignore[attr-defined]
        self.config: ConfigManager = bot.config_manager  # type: ignore[attr-defined]
        self.logger = bot.logger  # type: ignore[attr-defined]

    # ------------------------
    # XP Gain on Messages
    # ------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        enabled = await self.config.get(guild_id, "features.leveling_enabled", True)
        if not enabled:
            return

        xp_rate = await self.config.get(guild_id, "xp_rate", 10)
        cooldown = await self.config.get(guild_id, "xp_cooldown", 60)

        gained = random.randint(1, xp_rate)
        added = await self.db.add_xp_with_cooldown(guild_id, message.author.id, gained, cooldown)

        if added:
            self.logger.info(f"[XP] {message.author} +{gained} XP (Guild {guild_id})")

            old_level, new_level = await self.db.check_level_up(guild_id, message.author.id)
            if new_level > old_level:
                self.logger.info(f"[LEVEL UP] {message.author} reached level {new_level} (Guild {guild_id})")

                msg_template = await self.config.get(guild_id, "level_up_message")
                formatted = msg_template.format(user=message.author.mention, level=new_level)
                channel_id = await self.config.get(guild_id, "level_channel")
                if channel_id:
                    channel = message.guild.get_channel(int(channel_id))
                    if channel:
                        await channel.send(formatted)
                else:
                    await message.channel.send(formatted)

                await self.handle_role_rewards(message, new_level)

    # ------------------------
    # Handle Role Rewards
    # ------------------------
    async def handle_role_rewards(self, message: discord.Message, new_level: int):
        guild_id = message.guild.id
        rewards = await self.db.get_level_rewards(guild_id)

        for level, role_id in rewards:
            if new_level >= level:
                role = message.guild.get_role(role_id)
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role, reason="Level reward")
                        self.logger.info(f"[ROLE REWARD] {message.author} awarded role {role.name} for reaching level {new_level} (Guild {guild_id})")
                    except discord.Forbidden:
                        self.logger.warning(f"[ROLE REWARD FAILED] Missing permissions to assign {role.name} to {message.author} in Guild {guild_id}")

    # ------------------------
    # Slash Commands — Level Info
    # ------------------------
    @app_commands.command(name="level", description="Check your level and XP")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        guild_id = interaction.guild.id

        enabled = await self.config.get(guild_id, "features.leveling_enabled", True)
        if not enabled:
            await interaction.response.send_message("⚠️ Leveling is disabled in this server.", ephemeral=True)
            return

        xp, level = await self.db.get_user_level(guild_id, member.id)
        await interaction.response.send_message(
            f"📊 {member.display_name} is level **{level}** with **{xp} XP**."
        )

    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        enabled = await self.config.get(guild_id, "features.leveling_enabled", True)
        if not enabled:
            await interaction.response.send_message("⚠️ Leveling is disabled in this server.", ephemeral=True)
            return

        top_users = await self.db.get_leaderboard(guild_id, limit=10)
        embed = discord.Embed(
            title=f"🏆 Leaderboard — {interaction.guild.name}",
            color=discord.Color.gold()
        )
        for i, (user_id, xp, level) in enumerate(top_users, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            embed.add_field(
                name=f"#{i} {name}",
                value=f"Level {level} — {xp} XP",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlevel", description="Manually set a member's level (Admin only)")
    @commands.has_permissions(administrator=True)
    async def setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        guild_id = interaction.guild.id
        await self.db.set_user_level(guild_id, member.id, level)
        self.logger.info(f"[SET LEVEL] {interaction.user} set {member} to level {level} (Guild {guild_id})")
        await interaction.response.send_message(
            f"✅ {member.display_name}'s level has been set to {level}."
        )

    # ------------------------
    # Slash Commands — Role Rewards
    # ------------------------
    @app_commands.command(name="add-level-role", description="Bind a role to a specific level (Admin only)")
    @commands.has_permissions(administrator=True)
    async def add_level_role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        guild_id = interaction.guild.id
        await self.db.add_level_reward(guild_id, level, role.id)
        self.logger.info(f"[ROLE REWARD ADD] {interaction.user} bound {role.name} to level {level} (Guild {guild_id})")
        await interaction.response.send_message(f"✅ Role {role.mention} will now be awarded at level {level}.")

    @app_commands.command(name="remove-level-role", description="Remove a role reward for a level (Admin only)")
    @commands.has_permissions(administrator=True)
    async def remove_level_role(self, interaction: discord.Interaction, level: int):
        guild_id = interaction.guild.id
        await self.db.remove_level_reward(guild_id, level)
        self.logger.info(f"[ROLE REWARD REMOVE] {interaction.user} removed reward for level {level} (Guild {guild_id})")
        await interaction.response.send_message(f"🗑️ Removed role reward for level {level}.")

    @app_commands.command(name="list-level-roles", description="List all configured role rewards")
    async def list_level_roles(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        rewards = await self.db.get_level_rewards(guild_id)

        if not rewards:
            await interaction.response.send_message("⚠️ No role rewards configured for this server.")
            return

        embed = discord.Embed(
            title="🎁 Level Role Rewards",
            color=discord.Color.blurple()
        )
        for level, role_id in rewards:
            role = interaction.guild.get_role(role_id)
            role_name = role.name if role else f"(deleted role {role_id})"
            embed.add_field(name=f"Level {level}", value=role_name, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
