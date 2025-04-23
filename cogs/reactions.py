import discord
from discord.ext import commands
from discord import app_commands
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    # =========================
    # 🎯 Setup & Initialization
    # =========================

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.ensure_tables()
            print("Reaction roles system ready")
        except Exception as e:
            print(f"Error setting up reaction roles: {e}")

    async def ensure_tables(self):
        """Initialize required database tables"""
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
                emoji TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    # =========================
    # 🔧 Admin Commands
    # =========================

    @app_commands.command(name="bind_reaction_role", description="Bind a role to a reaction on a message")
    @app_commands.describe(
        message_id="The ID of the message to bind to",
        emoji="The emoji to react with",
        role="The role to give when reacted"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def bind_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role
    ):
        try:
            message_id = int(message_id)
            
            # Verify message exists
            try:
                message = await interaction.channel.fetch_message(message_id)
            except discord.NotFound:
                raise ValueError("Message not found in this channel")

            # Add reaction role binding
            await self.db_manager.execute(
                """
                INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id)
                VALUES (?, ?, ?, ?)
                """,
                (interaction.guild.id, message_id, emoji, role.id)
            )

            # Add the initial reaction
            await message.add_reaction(emoji)

            await self.ui_manager.send_response(
                interaction,
                title="⚙️ Reaction Role Configured",
                description="The reaction role has been set up successfully.",
                fields=[
                    {"name": "Message", "value": f"[Jump to Message]({message.jump_url})", "inline": True},
                    {"name": "Emoji", "value": emoji, "inline": True},
                    {"name": "Role", "value": role.mention, "inline": True},
                    {"name": "Effect", "value": "Users who react with the specified emoji will receive this role.", "inline": False}
                ],
                command_type="Administrator"
            )

        except ValueError as e:
            await self.ui_manager.send_error(interaction, "Invalid Input", str(e))
        except Exception as e:
            await self.ui_manager.send_error(interaction, "Error", f"Failed to bind reaction role: {str(e)}")

    @app_commands.command(name="bind_reaction_role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def bind_reaction_role(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            message_id = int(message_id)
            message = await interaction.channel.fetch_message(message_id)
            
            await self.db_manager.add_reaction_role(message_id, emoji, role.id)
            await message.add_reaction(emoji)
            
            await self.ui_manager.send_response(
                interaction,
                title="🔗 Reaction Role Bound",
                description="A new reaction role has been configured",
                command_type="Administrator",
                fields=[
                    {"name": "Message", "value": f"[Jump to Message]({message.jump_url})", "inline": True},
                    {"name": "Emoji", "value": emoji, "inline": True},
                    {"name": "Role", "value": role.mention, "inline": True},
                    {"name": "Setup By", "value": interaction.user.mention, "inline": False}
                ]
            )
        except ValueError as e:
            await self.ui_manager.send_error(interaction, "Invalid Input", str(e))
        except Exception as e:
            await self.ui_manager.send_error(interaction, "Reaction Role Error", str(e))

    # =========================
    # 📝 Event Listeners
    # =========================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role assignment"""
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        try:
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

        except discord.Forbidden:
            print(f"Missing permissions to assign role in guild {payload.guild_id}")
        except Exception as e:
            print(f"Error handling reaction add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role removal"""
        if payload.guild_id is None:
            return

        try:
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

        except discord.Forbidden:
            print(f"Missing permissions to remove role in guild {payload.guild_id}")
        except Exception as e:
            print(f"Error handling reaction remove: {e}")

    # =========================
    # 👤 User Commands
    # =========================

    @app_commands.command(name="reaction_stats", description="View your reaction statistics")
    @app_commands.describe(user="The user to check stats for (optional)")
    async def reaction_stats(self, interaction: discord.Interaction, user: discord.User = None):
        """Show reaction statistics for a user"""
        try:
            target = user or interaction.user
            
            # Get reaction counts
            row = await self.db_manager.fetchone(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT message_id) as messages,
                    COUNT(DISTINCT emoji) as unique_emojis
                FROM reactions
                WHERE user_id = ? AND guild_id = ?
                """,
                (target.id, interaction.guild.id)
            )

            if not row or row["total"] == 0:
                no_reactions_msg = "You haven't" if target == interaction.user else f"{target.name} hasn't"
                await self.ui_manager.send_embed(
                    interaction,
                    title="No Reactions",
                    description=f"{no_reactions_msg} added any reactions yet!",
                    command_type="User"
                )
                return

            await self.ui_manager.send_embed(
                interaction,
                title=f"Reaction Stats for {target.name}",
                description=f"**Total Reactions:** {row['total']}\n"
                           f"**Messages Reacted To:** {row['messages']}\n"
                           f"**Unique Emojis Used:** {row['unique_emojis']}",
                command_type="User"
            )

        except Exception as e:
            await self.ui_manager.error_embed(
                interaction,
                title="Error",
                description=f"Failed to get reaction stats: {str(e)}",
                command_type="User"
            )

async def setup(bot):
    await bot.add_cog(Reactions(bot))
