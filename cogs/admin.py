import discord
from discord.ext import commands
from typing import Optional
from utils.db_manager import DBManager
import json

class Admin(commands.Cog):
    """Server administration and configuration commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager

    @commands.hybrid_group(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        """Base command for server configuration"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Server Configuration",
                "Please specify a configuration category:\n"
                "• /config xp - XP and leveling settings\n"
                "• /config tickets - Ticket system settings\n"
                "• /config logging - Logging system settings\n"
                "• /config autorole - Automatic role settings\n"
                "• /config moderation - Moderation settings"
            )
            await ctx.send(embed=embed)

    @config.group(name="xp")
    @commands.has_permissions(administrator=True)
    async def config_xp(self, ctx):
        """Configure XP system settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "XP Configuration",
                "Available commands:\n"
                "• /config xp rate <amount> - Set XP earned per message\n"
                "• /config xp cooldown <seconds> - Set cooldown between XP gains",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_xp.command(name="rate")
    async def xp_rate(self, ctx, amount: int):
        """Set the amount of XP earned per message"""
        if amount < 1 or amount > 100:
            await ctx.send("XP rate must be between 1 and 100")
            return
            
        await self.db_manager.set_data('xp_config', str(ctx.guild.id), {'rate': amount})
        embed = self.ui.admin_embed(
            "XP Rate Updated",
            f"Members will now earn {amount} XP per message",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config_xp.command(name="cooldown")
    async def xp_cooldown(self, ctx, seconds: int):
        """Set the cooldown between XP gains"""
        if seconds < 10 or seconds > 300:
            await ctx.send("Cooldown must be between 10 and 300 seconds")
            return
            
        await self.db_manager.set_data('xp_config', str(ctx.guild.id), {'cooldown': seconds})
        embed = self.ui.admin_embed(
            "XP Cooldown Updated",
            f"Members will now have a {seconds} second cooldown between XP gains",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config.group(name="tickets")
    @commands.has_permissions(administrator=True)
    async def config_tickets(self, ctx):
        """Configure ticket system settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Ticket Configuration",
                "Available commands:\n"
                "• /config tickets category <category> - Set ticket category\n"
                "• /config tickets support <role> - Set support role",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_tickets.command(name="category")
    async def tickets_category(self, ctx, category: discord.CategoryChannel):
        """Set the category for ticket channels"""
        await self.db_manager.set_data('tickets_config', str(ctx.guild.id), {'category_id': category.id})
        embed = self.ui.admin_embed(
            "Ticket Category Set",
            f"New tickets will be created in {category.mention}",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config_tickets.command(name="support")
    async def tickets_support(self, ctx, role: discord.Role):
        """Set the support team role"""
        await self.db_manager.set_data('tickets_config', str(ctx.guild.id), {'support_role_id': role.id})
        embed = self.ui.admin_embed(
            "Support Role Set",
            f"Members with {role.mention} will now have access to tickets",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config.group(name="logging")
    @commands.has_permissions(administrator=True)
    async def config_logging(self, ctx):
        """Configure logging system settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Logging Configuration",
                "Available commands:\n"
                "• /config logging channel <channel> - Set logging channel",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_logging.command(name="channel")
    async def logging_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for server logs"""
        # Verify bot permissions
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send("I need permission to send messages in that channel!")
            return
            
        await self.db_manager.set_data('logging_config', str(ctx.guild.id), {'channel_id': channel.id})
        embed = self.ui.admin_embed(
            "Logging Channel Set",
            f"Server logs will now be sent to {channel.mention}",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config.group(name="moderation")
    @commands.has_permissions(administrator=True)
    async def config_moderation(self, ctx):
        """Configure moderation settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Moderation Configuration",
                "Available commands:\n"
                "• /config moderation muterole <role> - Set muted role\n"
                "• /config moderation modrole <role> - Set moderator role\n"
                "• /config moderation warnexpire <days> - Set warning expiration",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_moderation.command(name="muterole")
    async def mod_muterole(self, ctx, role: discord.Role):
        """Set the muted role"""
        await self.db_manager.set_data('moderation_config', str(ctx.guild.id), {'muted_role_id': role.id})
        embed = self.ui.admin_embed(
            "Muted Role Set",
            f"Muted members will now receive the {role.mention} role",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config_moderation.command(name="modrole")
    async def mod_modrole(self, ctx, role: discord.Role):
        """Set the moderator role"""
        await self.db_manager.set_data('moderation_config', str(ctx.guild.id), {'mod_role_id': role.id})
        embed = self.ui.admin_embed(
            "Moderator Role Set",
            f"Members with {role.mention} will have access to moderation commands",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config_moderation.command(name="warnexpire")
    async def mod_warnexpire(self, ctx, days: int):
        """Set how many days until warnings expire"""
        if days < 1:
            await ctx.send("Warning expiration must be at least 1 day")
            return
            
        await self.db_manager.set_data('moderation_config', str(ctx.guild.id), {'warn_delete_days': days})
        embed = self.ui.admin_embed(
            "Warning Expiration Set",
            f"Warnings will now expire after {days} days",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config.group(name="autorole")
    @commands.has_permissions(administrator=True)
    async def config_autorole(self, ctx):
        """Configure automatic role assignment"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Auto-Role Configuration",
                "Available commands:\n"
                "• /config autorole set <role> - Set the auto-assigned role\n"
                "• /config autorole toggle - Enable/disable auto-role",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)

    @config_autorole.command(name="set")
    async def autorole_set(self, ctx, role: discord.Role):
        """Set the role to automatically assign to new members"""
        # Verify bot permissions
        if not role.position < ctx.guild.me.top_role.position:
            await ctx.send("That role is higher than my highest role! I need a role above it to assign it.")
            return
            
        await self.db_manager.set_auto_role(ctx.guild.id, role.id)
        embed = self.ui.admin_embed(
            "Auto-Role Set",
            f"New members will now automatically receive the {role.mention} role",
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @config_autorole.command(name="toggle")
    async def autorole_toggle(self, ctx):
        """Toggle automatic role assignment"""
        current_data = await self.db_manager.get_auto_role(ctx.guild.id)
        if not current_data:
            await ctx.send("You need to set an auto-role first!")
            return
            
        role_id, enabled = current_data
        new_state = not enabled
        
        await self.db_manager.toggle_auto_role(ctx.guild.id, new_state)
        status = "enabled" if new_state else "disabled"
        
        role = ctx.guild.get_role(role_id)
        description = f"Auto-role has been {status}"
        if role:
            description += f"\nRole: {role.mention}"
        
        embed = self.ui.admin_embed(
            "Auto-Role Toggled",
            description,
            command_type="Administrative"
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="settings", description="View all server settings")
    @commands.has_permissions(administrator=True)
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
            
            embed = self.ui.admin_embed(
                f"{ctx.guild.name} Settings",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.admin_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))