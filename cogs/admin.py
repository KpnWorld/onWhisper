import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import json

class Admin(commands.Cog):
    """Server administration and configuration commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Admin cog")
                return
            self._ready.set()
            print("✅ Admin cog ready")
        except Exception as e:
            print(f"❌ Error setting up Admin cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    @commands.hybrid_group(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        """Base command for server configuration"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Server Configuration",
                "Available command groups:\n"
                "• /config xp - XP and leveling settings\n"
                "• /config level - Level rewards settings\n"
                "• /config logs - Logging system settings\n"
                "• /config tickets - Ticket system settings\n"
                "• /config autorole - Auto-role settings"
            )
            await ctx.send(embed=embed)

    # XP Config Commands
    @config.group(name="xp")
    @commands.has_permissions(administrator=True)
    async def config_xp(self, ctx):
        """Configure XP system settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "XP Configuration",
                "Available commands:\n"
                "• /config xp rate <amount> - Set XP per message\n"
                "• /config xp cooldown <seconds> - Set XP gain cooldown\n"
                "• /config xp toggle - Enable/disable XP system"
            )
            await ctx.send(embed=embed)

    @config_xp.command(name="rate")
    async def xp_rate(self, ctx, amount: int):
        """Set XP gain per message"""
        try:
            if amount < 1 or amount > 100:
                await ctx.send("XP rate must be between 1 and 100", ephemeral=True)
                return
            
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'rate': amount},
                ['xp_settings']
            )
            
            embed = self.ui.admin_embed(
                "XP Rate Updated",
                f"Members will now earn {amount} XP per message"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_xp.command(name="cooldown")
    async def xp_cooldown(self, ctx, seconds: int):
        """Set cooldown between XP gains"""
        try:
            if seconds < 10 or seconds > 300:
                await ctx.send("Cooldown must be between 10 and 300 seconds", ephemeral=True)
                return
            
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'cooldown': seconds},
                ['xp_settings']
            )
            
            embed = self.ui.admin_embed(
                "XP Cooldown Updated",
                f"Members will now have a {seconds} second cooldown between XP gains"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_xp.command(name="toggle")
    async def xp_toggle(self, ctx):
        """Enable/disable XP system"""
        try:
            current = await self.db_manager.get_guild_data(ctx.guild.id)
            current_state = current.get('xp_settings', {}).get('enabled', True)
            
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'enabled': not current_state},
                ['xp_settings']
            )
            
            status = "enabled" if not current_state else "disabled"
            embed = self.ui.admin_embed(
                "XP System Toggled",
                f"XP system has been {status}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Level Config Commands
    @config.group(name="level")
    @commands.has_permissions(administrator=True)
    async def config_level(self, ctx):
        """Configure level reward settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Level Configuration",
                "Available commands:\n"
                "• /config level add <level> <role> - Set role reward\n"
                "• /config level remove <level> - Remove level reward\n"
                "• /config level list - List all level rewards"
            )
            await ctx.send(embed=embed)

    @config_level.command(name="add")
    async def level_add(self, ctx, level: int, role: discord.Role):
        """Set role reward for level"""
        try:
            if level < 1:
                await ctx.send("Level must be at least 1", ephemeral=True)
                return

            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            await self.db_manager.add_level_reward(ctx.guild.id, level, role.id)
            
            embed = self.ui.admin_embed(
                "Level Reward Added",
                f"Members will receive {role.mention} at level {level}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_level.command(name="remove")
    async def level_remove(self, ctx, level: int):
        """Remove a level reward"""
        try:
            if await self.db_manager.remove_level_reward(ctx.guild.id, level):
                embed = self.ui.admin_embed(
                    "Level Reward Removed",
                    f"Removed role reward for level {level}"
                )
            else:
                embed = self.ui.error_embed(
                    "Not Found",
                    f"No role reward found for level {level}"
                )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_level.command(name="list")
    async def level_list(self, ctx):
        """List all level role rewards"""
        try:
            rewards = await self.db_manager.get_level_rewards(ctx.guild.id)
            
            if not rewards:
                await ctx.send("No level rewards configured")
                return
                
            description = "\n".join(
                f"Level {level}: {ctx.guild.get_role(role_id).mention}" 
                for level, role_id in rewards 
                if ctx.guild.get_role(role_id)
            )
            
            embed = self.ui.info_embed(
                "Level Rewards",
                description
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Logs Config Commands
    @config.group(name="logs")
    @commands.has_permissions(administrator=True)
    async def config_logs(self, ctx):
        """Configure logging settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Logging Configuration",
                "Available commands:\n"
                "• /config logs set <type> <channel> - Set log channel\n"
                "• /config logs toggle - Toggle logging system"
            )
            await ctx.send(embed=embed)

    @config_logs.command(name="set")
    async def logs_set(self, ctx, channel: discord.TextChannel):
        """Set up logging channels with type selection"""
        valid_types = {
            'mod': '🛡️ Moderation Logs',
            'member': '👥 Member Events',
            'message': '💬 Message Logs',
            'server': '⚙️ Server Events'
        }

        try:
            # Get current config
            config = await self.db_manager.get_data('logging_config', str(ctx.guild.id)) or {}
            
            # Create select menu options
            options = []
            for type_id, label in valid_types.items():
                is_active = channel.id == config.get(f'{type_id}_channel')
                options.append({
                    'label': label,
                    'value': type_id,
                    'emoji': label.split()[0],
                    'default': is_active
                })

            view = self.ui.CommandMultiSelectView(
                options=options,
                placeholder="Select log types for this channel",
                min_values=1,
                max_values=len(valid_types)
            )

            embed = self.ui.admin_embed(
                "Log Channel Setup",
                f"Select which types of logs to send to {channel.mention}\n\n"
                "Log Types:\n"
                "🛡️ Moderation - Bans, kicks, mutes, etc.\n"
                "👥 Member - Joins, leaves, role changes\n"
                "💬 Message - Edits, deletions\n"
                "⚙️ Server - Channel/role updates"
            )

            sent = await ctx.send(embed=embed, view=view)
            view.message = sent

            # Wait for selection
            await view.wait()
            if view.values:
                # Update config with selected types
                for type_id in valid_types.keys():
                    if type_id in view.values:
                        config[f'{type_id}_channel'] = channel.id
                        config[f'{type_id}_logs'] = True
                    elif config.get(f'{type_id}_channel') == channel.id:
                        config[f'{type_id}_channel'] = None
                        config[f'{type_id}_logs'] = False

                await self.db_manager.set_data('logging_config', str(ctx.guild.id), config)

                enabled_types = [valid_types[t].split(' - ')[0] for t in view.values]
                result_embed = self.ui.admin_embed(
                    "Log Channel Updated",
                    f"Channel: {channel.mention}\n"
                    f"Enabled Types: {' '.join(enabled_types)}"
                )
                await sent.edit(embed=result_embed, view=None)
            else:
                await sent.edit(
                    embed=self.ui.error_embed("Setup Cancelled", "No log types were selected"),
                    view=None
                )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_logs.command(name="toggle")
    async def logs_toggle(self, ctx):
        """Enable/disable logging"""
        try:
            config = await self.db_manager.get_data('logging_config', str(ctx.guild.id)) or {}
            current_state = config.get('enabled', True)
            
            config['enabled'] = not current_state
            await self.db_manager.set_data('logging_config', str(ctx.guild.id), config)
            
            status = "enabled" if not current_state else "disabled"
            embed = self.ui.admin_embed(
                "Logging Toggled",
                f"Logging system has been {status}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Tickets Config Commands
    @config.group(name="tickets")
    @commands.has_permissions(administrator=True)
    async def config_tickets(self, ctx):
        """Configure ticket system settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Ticket Configuration",
                "Available commands:\n"
                "• /config tickets category <channel> - Set tickets category\n"
                "• /config tickets staff <role> - Set support staff role"
            )
            await ctx.send(embed=embed)

    @config_tickets.command(name="category")
    async def tickets_category(self, ctx, channel: discord.CategoryChannel):
        """Set category for tickets"""
        try:
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'category_id': channel.id},
                ['tickets', 'settings']
            )
            
            embed = self.ui.admin_embed(
                "Ticket Category Set",
                f"New tickets will be created in {channel.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_tickets.command(name="staff")
    async def tickets_staff(self, ctx, role: discord.Role):
        """Set support staff role"""
        try:
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'staff_role_id': role.id},
                ['tickets', 'settings']
            )
            
            embed = self.ui.admin_embed(
                "Support Staff Role Set",
                f"Members with {role.mention} will have access to tickets"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Autorole Config Commands
    @config.group(name="autorole")
    @commands.has_permissions(administrator=True)
    async def config_autorole(self, ctx):
        """Configure auto-role settings"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Auto-Role Configuration",
                "Available commands:\n"
                "• /config autorole set <role> - Set auto-role\n"
                "• /config autorole remove - Disable auto-role"
            )
            await ctx.send(embed=embed)

    @config_autorole.command(name="set")
    async def autorole_set(self, ctx, role: discord.Role):
        """Set auto-role for new members"""
        try:
            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            await self.db_manager.set_auto_role(ctx.guild.id, role.id, True)
            
            embed = self.ui.admin_embed(
                "Auto-Role Set",
                f"New members will receive {role.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @config_autorole.command(name="remove")
    async def autorole_remove(self, ctx):
        """Disable auto-role"""
        try:
            await self.db_manager.set_auto_role(ctx.guild.id, None, False)
            
            embed = self.ui.admin_embed(
                "Auto-Role Disabled",
                "New members will no longer receive an automatic role"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))