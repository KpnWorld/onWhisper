import discord
from discord.ext import commands
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    # =========================
    # 🔧 Admin Slash Commands
    # =========================

    @discord.app_commands.command(name="setautorole", description="Admin: Set an auto role for the server")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_auto_role(self, interaction: discord.Interaction, role: discord.Role, enabled: bool = True):
        """Set an auto role for the server."""
        guild_id = interaction.guild.id

        # Set the auto role in the database asynchronously
        await self.db_manager.set_auto_role(guild_id, role.id, 1 if enabled else 0)

        # Send confirmation message asynchronously
        await self.ui_manager.send_embed(
            interaction,
            title="Auto Role Set",
            description=f"Auto role **{role.name}** has been {'enabled' if enabled else 'disabled'} for this server.",
            command_type="Administrator"
        )

    @discord.app_commands.command(name="listautoroles", description="Admin: List all auto roles for the server")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def list_auto_roles(self, interaction: discord.Interaction):
        """List all auto roles for the current server."""
        guild_id = interaction.guild.id

        # Fetch all auto roles from the database asynchronously
        auto_roles = await self.db_manager.get_auto_role(guild_id)

        if not auto_roles:
            await self.ui_manager.send_embed(
                interaction,
                title="No Auto Roles Set",
                description="There are no auto roles set for this server.",
                command_type="Administrator"
            )
            return

        # Build the embed listing the roles asynchronously
        roles_list = "\n".join([f"<@&{role_id}> - {'Enabled' if enabled else 'Disabled'}" for role_id, enabled in auto_roles])
        await self.ui_manager.send_embed(
            interaction,
            title="Auto Roles",
            description=roles_list,
            command_type="Administrator"
        )

    @discord.app_commands.command(name="removeautorole", description="Admin: Remove an auto role from the server")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def remove_auto_role(self, interaction: discord.Interaction, role: discord.Role):
        """Remove an auto role from the server."""
        guild_id = interaction.guild.id

        # Remove the auto role from the database asynchronously
        await self.db_manager.remove_auto_role(guild_id, role.id)

        # Send confirmation message asynchronously
        await self.ui_manager.send_embed(
            interaction,
            title="Auto Role Removed",
            description=f"Auto role **{role.name}** has been removed from this server.",
            command_type="Administrator"
        )

    @discord.app_commands.command(name="toggleautorole", description="Admin: Toggle the status of an auto role")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def toggle_auto_role(self, interaction: discord.Interaction, role: discord.Role):
        """Toggle the enabled/disabled status of an auto role."""
        guild_id = interaction.guild.id

        # Get current status of the auto role asynchronously
        auto_role = await self.db_manager.get_auto_role(guild_id)
        if auto_role:
            role_id, enabled = auto_role[0]
            new_status = 0 if enabled == 1 else 1
            await self.db_manager.set_auto_role(guild_id, role_id, new_status)

            # Send confirmation message asynchronously
            await self.ui_manager.send_embed(
                interaction,
                title="Auto Role Status Changed",
                description=f"Auto role **{role.name}** has been {'enabled' if new_status == 1 else 'disabled'} for this server.",
                command_type="Administrator"
            )
        else:
            await self.ui_manager.send_embed(
                interaction,
                title="No Auto Role Found",
                description=f"No auto role set for the role **{role.name}**.",
                command_type="Administrator"
            )

    # =========================
    # 👤 User Slash Command - Level Check
    # =========================

    @discord.app_commands.command(name="autorole", description="Check the auto role status")
    async def autorole(self, interaction: discord.Interaction):
        """Check if auto roles are enabled."""
        guild_id = interaction.guild.id

        # Fetch the current auto role status from the database asynchronously
        auto_roles = await self.db_manager.get_auto_role(guild_id)

        if not auto_roles:
            await self.ui_manager.send_embed(
                interaction,
                title="No Auto Role Set",
                description="There are no auto roles set for this server.",
                command_type="User"
            )
            return

        roles_list = "\n".join([f"<@&{role_id}> - {'Enabled' if enabled else 'Disabled'}" for role_id, enabled in auto_roles])
        await self.ui_manager.send_embed(
            interaction,
            title="Auto Roles",
            description=roles_list,
            command_type="User"
        )

def setup(bot):
    bot.add_cog(AutoRole(bot))
