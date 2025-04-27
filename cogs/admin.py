import discord
from discord.ext import commands
from utils.db_manager import DBManager
from typing import Optional
import json

class Admin(commands.Cog):
    """Server administration and configuration commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()

    @commands.hybrid_group(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        """Base command for server configuration"""
        if ctx.invoked_subcommand is None:
            embed = self.bot.create_embed(
                "Server Configuration",
                "Please specify a configuration category:\n"
                "• /config xp - XP and leveling settings\n"
                "• /config tickets - Ticket system settings\n"
                "• /config logging - Logging system settings\n"
                "• /config autorole - Automatic role settings\n"
                "• /config moderation - Moderation settings",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config.group(name="xp")
    async def config_xp(self, ctx):
        """XP system configuration"""
        if ctx.invoked_subcommand is None:
            embed = self.bot.create_embed(
                "XP System Configuration",
                "Available commands:\n"
                "• /config xp rate <amount> - Set XP per message\n"
                "• /config xp cooldown <seconds> - Set XP cooldown\n"
                "• /config xp view - View current XP settings",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_xp.command(name="view")
    async def xp_view(self, ctx):
        """View current XP system settings"""
        try:
            # Get XP settings from leveling cog
            leveling_cog = self.bot.get_cog('Leveling')
            if not leveling_cog:
                raise Exception("Leveling system is not available")

            description = (
                f"XP Rate: {leveling_cog.base_xp} XP per message\n"
                f"Cooldown: {leveling_cog.cooldown} seconds"
            )
            
            embed = self.bot.create_embed(
                "XP System Settings",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)

    @config.group(name="tickets")
    async def config_tickets(self, ctx):
        """Ticket system configuration"""
        if ctx.invoked_subcommand is None:
            # Get current settings
            settings = await self.db_manager.get_data('tickets_config', str(ctx.guild.id)) or {}
            
            description = (
                "Current Settings:\n"
                f"Support Role: {ctx.guild.get_role(settings.get('support_role_id', 0)).mention if settings.get('support_role_id') else 'Not set'}\n"
                f"Category: {ctx.guild.get_channel(settings.get('category_id', 0)).mention if settings.get('category_id') else 'Not set'}\n"
                "\nAvailable commands:\n"
                "• /config tickets support_role <role> - Set support staff role\n"
                "• /config tickets category <category> - Set tickets category"
            )
            
            embed = self.bot.create_embed(
                "Ticket System Configuration",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_tickets.command(name="support_role")
    async def tickets_support_role(self, ctx, role: discord.Role):
        """Set the support staff role for tickets"""
        try:
            settings = await self.db_manager.get_data('tickets_config', str(ctx.guild.id)) or {}
            settings['support_role_id'] = role.id
            await self.db_manager.set_data('tickets_config', str(ctx.guild.id), settings)
            
            embed = self.bot.create_embed(
                "Support Role Set",
                f"Ticket support role has been set to {role.mention}",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)

    @config.group(name="logging")
    async def config_logging(self, ctx):
        """Logging system configuration"""
        if ctx.invoked_subcommand is None:
            # Get current settings
            config = await self.db_manager.get_data('logging_config', str(ctx.guild.id)) or {}
            
            description = (
                "Current Settings:\n"
                f"Log Channel: {ctx.guild.get_channel(config.get('channel_id', 0)).mention if config.get('channel_id') else 'Not set'}\n"
                "\nAvailable commands:\n"
                "• /config logging channel <channel> - Set logging channel\n"
                "• /config logging test - Send test log"
            )
            
            embed = self.bot.create_embed(
                "Logging System Configuration",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config.group(name="autorole")
    async def config_autorole(self, ctx):
        """Auto-role configuration"""
        if ctx.invoked_subcommand is None:
            # Get current settings
            auto_role = await self.db_manager.get_auto_role(ctx.guild.id)
            
            status = "Disabled"
            role = None
            if auto_role:
                role_id, enabled = auto_role
                role = ctx.guild.get_role(role_id)
                status = "Enabled" if enabled else "Disabled"
            
            description = (
                "Current Settings:\n"
                f"Status: {status}\n"
                f"Role: {role.mention if role else 'Not set'}\n"
                "\nAvailable commands:\n"
                "• /config autorole set <role> - Set auto-role\n"
                "• /config autorole disable - Disable auto-role"
            )
            
            embed = self.bot.create_embed(
                "Auto-Role Configuration",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config.group(name="moderation")
    async def config_moderation(self, ctx):
        """Moderation system configuration"""
        if ctx.invoked_subcommand is None:
            # Get current settings
            settings = await self.db_manager.get_data('moderation_config', str(ctx.guild.id)) or {}
            
            muted_role = ctx.guild.get_role(settings.get('muted_role_id', 0))
            mod_role = ctx.guild.get_role(settings.get('mod_role_id', 0))
            
            description = (
                "Current Settings:\n"
                f"Muted Role: {muted_role.mention if muted_role else 'Not set'}\n"
                f"Moderator Role: {mod_role.mention if mod_role else 'Not set'}\n"
                f"Delete Warns After: {settings.get('warn_delete_days', 30)} days\n"
                "\nAvailable commands:\n"
                "• /config moderation muted_role <role> - Set muted role\n"
                "• /config moderation mod_role <role> - Set moderator role\n"
                "• /config moderation warn_delete_days <days> - Set warning deletion time"
            )
            
            embed = self.bot.create_embed(
                "Moderation Configuration",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_moderation.command(name="muted_role")
    async def mod_muted_role(self, ctx, role: discord.Role):
        """Set the muted role"""
        try:
            settings = await self.db_manager.get_data('moderation_config', str(ctx.guild.id)) or {}
            settings['muted_role_id'] = role.id
            await self.db_manager.set_data('moderation_config', str(ctx.guild.id), settings)
            
            embed = self.bot.create_embed(
                "Muted Role Set",
                f"Muted role has been set to {role.mention}",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)

    @config_moderation.command(name="mod_role")
    async def mod_mod_role(self, ctx, role: discord.Role):
        """Set the moderator role"""
        try:
            settings = await self.db_manager.get_data('moderation_config', str(ctx.guild.id)) or {}
            settings['mod_role_id'] = role.id
            await self.db_manager.set_data('moderation_config', str(ctx.guild.id), settings)
            
            embed = self.bot.create_embed(
                "Moderator Role Set",
                f"Moderator role has been set to {role.mention}",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)

    @config_moderation.command(name="warn_delete_days")
    async def mod_warn_delete_days(self, ctx, days: int):
        """Set how many days until warnings are deleted"""
        try:
            if days < 1:
                raise ValueError("Days must be greater than 0")
                
            settings = await self.db_manager.get_data('moderation_config', str(ctx.guild.id)) or {}
            settings['warn_delete_days'] = days
            await self.db_manager.set_data('moderation_config', str(ctx.guild.id), settings)
            
            embed = self.bot.create_embed(
                "Warning Delete Time Set",
                f"Warnings will be deleted after {days} days",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="settings", description="View all server settings")
    @commands.default_member_permissions(administrator=True)
    async def view_settings(self, ctx):
        """View all server configuration settings"""
        try:
            # Get settings from all systems
            autorole_data = await self.db_manager.get_auto_role(ctx.guild.id)
            logging_config = await self.db_manager.get_data('logging_config', str(ctx.guild.id)) or {}
            tickets_config = await self.db_manager.get_data('tickets_config', str(ctx.guild.id)) or {}
            mod_config = await self.db_manager.get_data('moderation_config', str(ctx.guild.id)) or {}
            
            # Format XP settings
            leveling_cog = self.bot.get_cog('Leveling')
            xp_settings = (
                f"XP Rate: {leveling_cog.base_xp if leveling_cog else 'N/A'}\n"
                f"Cooldown: {leveling_cog.cooldown if leveling_cog else 'N/A'} seconds"
            )
            
            # Format autorole settings
            autorole_status = "Disabled"
            autorole = None
            if autorole_data:
                role_id, enabled = autorole_data
                autorole = ctx.guild.get_role(role_id)
                autorole_status = f"{'Enabled' if enabled else 'Disabled'} - {autorole.mention if autorole else 'Invalid Role'}"
            
            description = (
                "**XP System:**\n"
                f"{xp_settings}\n\n"
                "**Ticket System:**\n"
                f"Support Role: {ctx.guild.get_role(tickets_config.get('support_role_id', 0)).mention if tickets_config.get('support_role_id') else 'Not set'}\n"
                f"Category: {ctx.guild.get_channel(tickets_config.get('category_id', 0)).mention if tickets_config.get('category_id') else 'Not set'}\n\n"
                "**Logging System:**\n"
                f"Channel: {ctx.guild.get_channel(logging_config.get('channel_id', 0)).mention if logging_config.get('channel_id') else 'Not set'}\n\n"
                "**Auto-Role:**\n"
                f"Status: {autorole_status}\n\n"
                "**Moderation:**\n"
                f"Muted Role: {ctx.guild.get_role(mod_config.get('muted_role_id', 0)).mention if mod_config.get('muted_role_id') else 'Not set'}\n"
                f"Moderator Role: {ctx.guild.get_role(mod_config.get('mod_role_id', 0)).mention if mod_config.get('mod_role_id') else 'Not set'}\n"
                f"Warning Delete Time: {mod_config.get('warn_delete_days', 30)} days"
            )
            
            embed = self.bot.create_embed(
                f"{ctx.guild.name} Settings",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))