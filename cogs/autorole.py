import discord
from discord import app_commands
from discord.ext import commands
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    # =========================
    # 🔧 Admin Commands
    # =========================

    @app_commands.command(name="setautorole", description="Set an auto role for the server")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(role="The role to automatically assign", enabled="Whether the auto role should be enabled")
    async def set_auto_role(self, interaction: discord.Interaction, role: discord.Role, enabled: bool = True):
        try:
            await self.db_manager.set_auto_role(interaction.guild.id, role.id, 1 if enabled else 0)
            
            await self.ui_manager.send_response(
                interaction,
                title="⚙️ Auto Role Configuration",
                description="Auto role settings have been updated",
                command_type="Administrator",
                fields=[
                    {"name": "Role", "value": role.mention, "inline": True},
                    {"name": "Status", "value": "✅ Enabled" if enabled else "❌ Disabled", "inline": True},
                    {"name": "Members Affected", "value": f"`{len(interaction.guild.members)}`", "inline": True}
                ]
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction, 
                "Auto Role Configuration Error",
                str(e)
            )

    @app_commands.command(name="listautoroles", description="List all auto roles for the server")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_auto_roles(self, interaction: discord.Interaction):
        try:
            auto_roles = await self.db_manager.get_auto_role(interaction.guild.id)
            if not auto_roles or not isinstance(auto_roles, tuple):
                await self.ui_manager.send_response(
                    interaction,
                    title="📋 Auto Roles List",
                    description="No auto roles are configured for this server.",
                    command_type="Administrator"
                )
                return

            role_id, enabled = auto_roles  # Unpack the tuple
            role = interaction.guild.get_role(role_id)
            
            if not role:
                await self.ui_manager.send_error(
                    interaction,
                    "Auto Role Error",
                    "The configured role no longer exists."
                )
                return

            await self.ui_manager.send_response(
                interaction,
                title="📋 Auto Roles List",
                description="Currently configured auto roles:",
                command_type="Administrator",
                fields=[
                    {"name": "Role", "value": role.mention, "inline": True},
                    {"name": "Status", "value": "✅ Enabled" if enabled else "❌ Disabled", "inline": True},
                    {"name": "Role ID", "value": f"`{role_id}`", "inline": True}
                ]
            )

        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Auto Role List Error",
                f"Failed to fetch auto roles: {str(e)}"
            )

    @app_commands.command(name="removeautorole", description="Remove an auto role from the server")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(role="The role to remove from auto roles")
    async def remove_auto_role(self, interaction: discord.Interaction, role: discord.Role):
        try:
            await self.db_manager.remove_auto_role(interaction.guild.id, role.id)
            await self.ui_manager.send_response(
                interaction,
                title="🗑️ Auto Role Removed",
                description=f"The auto role has been removed successfully.",
                command_type="Administrator",
                fields=[
                    {"name": "Removed Role", "value": role.mention, "inline": True},
                    {"name": "Action By", "value": interaction.user.mention, "inline": True}
                ]
            )
        except Exception as e:
            await self.ui_manager.send_error(
                interaction,
                "Auto Role Removal Error",
                str(e)
            )

    # =========================
    # 👤 User Commands
    # =========================

    @app_commands.command(name="autorole", description="Check the auto role status")
    async def autorole(self, interaction: discord.Interaction):
        try:
            auto_roles = await self.db_manager.get_auto_role(interaction.guild.id)
            if not auto_roles:
                await self.ui_manager.send_embed(
                    interaction,
                    title="No Auto Roles",
                    description="There are no auto roles set for this server.",
                    command_type="User"
                )
                return

            roles_list = "\n".join(
                [f"<@&{role_id}> - {'🟢 Enabled' if enabled else '🔴 Disabled'}" 
                 for role_id, enabled in auto_roles]
            )
            await self.ui_manager.send_embed(
                interaction,
                title="Server Auto Roles",
                description=roles_list,
                command_type="User"
            )
        except Exception as e:
            await self.ui_manager.send_embed(
                interaction,
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                command_type="User"
            )

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
