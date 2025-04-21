import discord
from discord.ext import commands
from discord import app_commands
from utils.DBManager import DBManager
from utils.UIManager import UIManager


class Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    async def ensure_tables(self):
        await self.db_manager.execute(
            """
            CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, message_id, emoji)
            )
            """
        )
        await self.db_manager.execute(
            """
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT
            )
            """
        )

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_tables()

    # =========================
    # 🎉 Reaction Role Logic
    # =========================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        emoji = str(payload.emoji)

        # Handle reaction role
        role_row = await self.db_manager.fetchone(
            """
            SELECT role_id FROM reaction_roles
            WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """,
            (payload.guild_id, payload.message_id, emoji)
        )

        if role_row:
            role = guild.get_role(role_row["role_id"])
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role given")
                except discord.Forbidden:
                    pass

        # Log the reaction
        await self.db_manager.execute(
            "INSERT INTO reactions (user_id, guild_id, message_id, emoji) VALUES (?, ?, ?, ?)",
            (member.id, guild.id, payload.message_id, emoji)
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        emoji = str(payload.emoji)

        role_row = await self.db_manager.fetchone(
            """
            SELECT role_id FROM reaction_roles
            WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """,
            (payload.guild_id, payload.message_id, emoji)
        )

        if role_row and member:
            role = guild.get_role(role_row["role_id"])
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                except discord.Forbidden:
                    pass

    # =========================
    # 🔧 Admin Slash Commands
    # =========================

    @app_commands.command(name="bind_reaction_role", description="Admin: Bind a reaction to a role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def bind_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role
    ):
        """Bind an emoji reaction to a role on a specific message"""
        try:
            message_id = int(message_id)
        except ValueError:
            return await self.ui_manager.send_error(interaction, "Invalid message ID.", command_type="Administrator")

        await self.db_manager.execute(
            """
            INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)
            """,
            (interaction.guild.id, message_id, emoji, role.id)
        )

        await self.ui_manager.send_embed(
            interaction,
            title="Reaction Role Bound",
            description=f"{emoji} will now assign the role {role.mention} on message `{message_id}`.",
            command_type="Administrator"
        )

    @bind_reaction_role.error
    async def bind_reaction_role_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await self.ui_manager.send_error(interaction, "You need `Manage Roles` permission to use this.", command_type="Administrator")

    # =========================
    # 👤 User Slash Command - Reaction Stats
    # =========================

    @app_commands.command(name="reaction_stats", description="Check how many reactions you've added")
    async def reaction_stats(self, interaction: discord.Interaction):
        """Show how many reactions a user has added in this server"""
        row = await self.db_manager.fetchone(
            """
            SELECT COUNT(*) as total FROM reactions
            WHERE user_id = ? AND guild_id = ?
            """,
            (interaction.user.id, interaction.guild.id)
        )

        total = row["total"] if row else 0

        await self.ui_manager.send_embed(
            interaction,
            title="Your Reaction Stats",
            description=f"You've added **{total}** reaction(s) in this server.",
            command_type="User"
        )


async def setup(bot):
    await bot.add_cog(Reactions(bot))
