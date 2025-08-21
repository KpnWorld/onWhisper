import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
import logging
from datetime import datetime

class RolesCog(commands.Cog):
    """Role management system for autoroles, reaction roles, and color roles"""

    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.roles")
        # Cache for reaction roles
        self._reaction_roles: Dict[int, Dict[int, Dict[str, int]]] = {}  # guild_id -> message_id -> emoji -> role_id

    async def _load_reaction_roles(self, guild_id: int) -> None:
        """Load reaction roles from database into cache"""
        try:
            reaction_roles = await self.bot.db.get_reaction_roles(guild_id)
            if reaction_roles:
                if guild_id not in self._reaction_roles:
                    self._reaction_roles[guild_id] = {}

                for rr in reaction_roles:
                    message_id = rr['message_id']
                    if message_id not in self._reaction_roles[guild_id]:
                        self._reaction_roles[guild_id][message_id] = {}
                    self._reaction_roles[guild_id][message_id][rr['emoji']] = rr['role_id']
        except Exception as e:
            self.log.error(f"Error loading reaction roles: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle autorole assignment"""
        if member.bot:
            return

        try:
            # Get autorole from database
            role_id = await self.bot.db.get_autorole(member.guild.id)
            if role_id:
                role = member.guild.get_role(role_id)
                if role:
                    await member.add_roles(role, reason="Autorole")
                    self.log.info(f"Added autorole {role.name} to {member}")
        except Exception as e:
            self.log.error(f"Error assigning autorole: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role assignment"""
        if payload.member.bot:
            return

        try:
            # Check if this is a reaction role message
            guild_roles = self._reaction_roles.get(payload.guild_id, {})
            message_roles = guild_roles.get(payload.message_id, {})

            emoji = str(payload.emoji)
            if role_id := message_roles.get(emoji):
                guild = self.bot.get_guild(payload.guild_id)
                if not guild:
                    return

                role = guild.get_role(role_id)
                if role:
                    await payload.member.add_roles(role, reason=f"Reaction role: {emoji}")
                    self.log.info(f"Added reaction role {role.name} to {payload.member}")

        except Exception as e:
            self.log.error(f"Error adding reaction role: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role removal"""
        try:
            # Check if this is a reaction role message
            guild_roles = self._reaction_roles.get(payload.guild_id, {})
            message_roles = guild_roles.get(payload.message_id, {})

            emoji = str(payload.emoji)
            if role_id := message_roles.get(emoji):
                guild = self.bot.get_guild(payload.guild_id)
                if not guild:
                    return

                member = guild.get_member(payload.user_id)
                if not member or member.bot:
                    return

                role = guild.get_role(role_id)
                if role:
                    await member.remove_roles(role, reason=f"Reaction role removed: {emoji}")
                    self.log.info(f"Removed reaction role {role.name} from {member}")

        except Exception as e:
            self.log.error(f"Error removing reaction role: {e}", exc_info=True)

    @app_commands.command(name="autorole")
    @app_commands.describe(
        role="Role to automatically assign to new members",
        disable="Disable autorole"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def autorole_setup(
        self,
        interaction: discord.Interaction,
        role: Optional[discord.Role] = None,
        disable: Optional[bool] = False
    ):
        """Configure the autorole system"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            if disable:
                await self.bot.db.set_autorole(interaction.guild.id, None)
                await interaction.response.send_message(
                    "✅ Autorole system disabled.",
                    ephemeral=True
                )
                return

            if not role:
                current_role_id = await self.bot.db.get_autorole(interaction.guild.id)
                if not current_role_id:
                    return await interaction.response.send_message(
                        "No autorole currently set. Specify a role to set one.",
                        ephemeral=True
                    )
                current_role = interaction.guild.get_role(current_role_id)
                return await interaction.response.send_message(
                    f"Current autorole: {current_role.mention if current_role else 'None'}",
                    ephemeral=True
                )

            # Verify bot permissions
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.send_message(
                    "I don't have permission to manage roles!",
                    ephemeral=True
                )

            # Verify role hierarchy
            if role.position >= interaction.guild.me.top_role.position:
                return await interaction.response.send_message(
                    "I can't assign roles that are higher than my highest role!",
                    ephemeral=True
                )

            # Save autorole
            await self.bot.db.set_autorole(interaction.guild.id, role.id)
            await interaction.response.send_message(
                f"✅ Autorole set to {role.mention}",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error setting autorole: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while configuring autorole.",
                ephemeral=True
            )

    @app_commands.command(name="reactionrole")
    @app_commands.describe(
        message_id="ID of the message to add reaction roles to",
        role="Role to assign",
        emoji="Emoji to use for the reaction"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def setup_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        role: discord.Role,
        emoji: str
    ):
        """Set up a reaction role"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Convert message ID to int
            try:
                message_id = int(message_id)
            except ValueError:
                return await interaction.response.send_message(
                    "Invalid message ID! Make sure to right-click the message and copy its ID.",
                    ephemeral=True
                )

            # Verify bot permissions
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.send_message(
                    "I don't have permission to manage roles!",
                    ephemeral=True
                )

            # Verify role hierarchy
            if role.position >= interaction.guild.me.top_role.position:
                return await interaction.response.send_message(
                    "I can't assign roles that are higher than my highest role!",
                    ephemeral=True
                )

            # Try to find the message
            try:
                message = None
                for channel in interaction.guild.text_channels:
                    try:
                        message = await channel.fetch_message(message_id)
                        break
                    except:
                        continue

                if not message:
                    return await interaction.response.send_message(
                        "Couldn't find the specified message in any channel!",
                        ephemeral=True
                    )
            except discord.NotFound:
                return await interaction.response.send_message(
                    "Message not found! Make sure the ID is correct.",
                    ephemeral=True
                )

            # Add reaction role to database
            await self.bot.db.add_reaction_role(
                interaction.guild.id,
                message_id,
                emoji,
                role.id
            )

            # Update cache
            if interaction.guild.id not in self._reaction_roles:
                self._reaction_roles[interaction.guild.id] = {}
            if message_id not in self._reaction_roles[interaction.guild.id]:
                self._reaction_roles[interaction.guild.id][message_id] = {}
            self._reaction_roles[interaction.guild.id][message_id][emoji] = role.id

            # Add reaction to message
            await message.add_reaction(emoji)

            await interaction.response.send_message(
                f"✅ Added reaction role:\nMessage: {message.jump_url}\nEmoji: {emoji}\nRole: {role.mention}",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error setting up reaction role: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while setting up the reaction role.",
                ephemeral=True
            )

    @app_commands.command(name="colorrole")
    @app_commands.describe(
        color="Hex color code (e.g., #FF0000)",
        name="Custom name for the color role"
    )
    async def create_color_role(
        self,
        interaction: discord.Interaction,
        color: str,
        name: Optional[str] = None
    ):
        """Create or update your color role"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Validate color format
            if not color.startswith('#') or len(color) != 7:
                return await interaction.response.send_message(
                    "Invalid color format! Use hex format (e.g., #FF0000)",
                    ephemeral=True
                )

            try:
                # Convert hex to discord.Color
                color_value = int(color[1:], 16)
                discord_color = discord.Color(color_value)
            except ValueError:
                return await interaction.response.send_message(
                    "Invalid color code! Use hex format (e.g., #FF0000)",
                    ephemeral=True
                )

            # Check if user already has a color role
            current_role_id = await self.bot.db.get_color_role(
                interaction.guild.id,
                interaction.user.id
            )

            if current_role_id:
                # Update existing role
                role = interaction.guild.get_role(current_role_id)
                if role:
                    await role.edit(
                        color=discord_color,
                        name=name or f"Color-{color[1:]}",
                        reason=f"Color role update requested by {interaction.user}"
                    )
                    await interaction.response.send_message(
                        f"✅ Updated your color role to {color}",
                        ephemeral=True
                    )
                    return

            # Create new role
            role_name = name or f"Color-{color[1:]}"
            new_role = await interaction.guild.create_role(
                name=role_name,
                color=discord_color,
                reason=f"Color role created for {interaction.user}"
            )

            # Save to database
            await self.bot.db.set_color_role(
                interaction.guild.id,
                interaction.user.id,
                new_role.id
            )

            # Assign role to user
            await interaction.user.add_roles(new_role, reason="Color role assignment")

            await interaction.response.send_message(
                f"✅ Created and assigned color role: {color}",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error creating color role: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while creating the color role.",
                ephemeral=True
            )

    @app_commands.command(name="removecolor")
    async def remove_color_role(self, interaction: discord.Interaction):
        """Remove your color role"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Get user's color role
            role_id = await self.bot.db.get_color_role(
                interaction.guild.id,
                interaction.user.id
            )

            if not role_id:
                return await interaction.response.send_message(
                    "You don't have a color role!",
                    ephemeral=True
                )

            role = interaction.guild.get_role(role_id)
            if role:
                # Remove role from user
                await interaction.user.remove_roles(role, reason="Color role removal requested")
                # Delete the role
                await role.delete(reason=f"Color role removed by {interaction.user}")

            # Remove from database
            await self.bot.db.clear_color_role(
                interaction.guild.id,
                interaction.user.id
            )

            await interaction.response.send_message(
                "✅ Removed your color role.",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error removing color role: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while removing the color role.",
                ephemeral=True
            )

    async def cog_load(self):
        """Load reaction roles into cache on startup"""
        for guild in self.bot.guilds:
            await self._load_reaction_roles(guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Load reaction roles when bot joins a new guild"""
        await self._load_reaction_roles(guild.id)

async def setup(bot):
    await bot.add_cog(RolesCog(bot))