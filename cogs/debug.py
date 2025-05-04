import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import psutil
import platform
import os
import json
from typing import Optional, Literal

class DebugCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Only allow bot owner to use these commands"""
        return await self.bot.is_owner(ctx.author)

    async def cog_before_invoke(self, ctx: commands.Context) -> bool:
        """Log debug command usage"""
        try:
            await self.bot.db_manager.log_event(
                ctx.guild.id if ctx.guild else 0,
                ctx.author.id,
                "debug_command",
                f"Used debug command: {ctx.command.name} {ctx.message.content}"
            )
        except Exception as e:
            print(f"Failed to log debug command: {e}")
        return True

    @commands.command(name='load', hidden=True)
    async def load_cog(self, ctx, *, cog: str):
        """Load a cog"""
        confirm = await self.bot.ui_manager.confirm_action(
            ctx,
            "Load Cog",
            f"Are you sure you want to load the {cog} cog?",
            confirm_label="Load",
            cancel_label="Cancel"
        )
        
        if not confirm:
            await ctx.send("Cog load cancelled.")
            return
            
        try:
            await self.bot.load_extension(f'cogs.{cog}')
            embed = self.bot.ui_manager.success_embed(
                "Cog Loaded",
                f"Successfully loaded cog: {cog}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = self.bot.ui_manager.error_embed(
                "Load Error",
                f"Error loading cog {cog}: {str(e)}"
            )
            await ctx.send(embed=embed)

    @commands.command(name='unload', hidden=True)
    async def unload_cog(self, ctx, *, cog: str):
        """Unload a cog"""
        try:
            await self.bot.unload_extension(f'cogs.{cog}')
            embed = self.bot.ui_manager.success_embed(
                "Cog Unloaded",
                f"Successfully unloaded cog: {cog}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = self.bot.ui_manager.error_embed(
                "Unload Error",
                f"Error unloading cog {cog}: {str(e)}"
            )
            await ctx.send(embed=embed)

    @commands.command(name='reload', hidden=True)
    async def reload_cog(self, ctx, *, cog: str):
        """Reload a cog"""
        try:
            await self.bot.reload_extension(f'cogs.{cog}')
            embed = self.bot.ui_manager.success_embed(
                "Cog Reloaded",
                f"Successfully reloaded cog: {cog}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = self.bot.ui_manager.error_embed(
                "Reload Error",
                f"Error reloading cog {cog}: {str(e)}"
            )
            await ctx.send(embed=embed)

    @commands.command(name='sync', hidden=True)
    async def sync_commands(self, ctx, target: Optional[Literal["guild", "global"]] = "guild"):
        """Sync slash commands"""
        try:
            if target == "guild":
                synced = await self.bot.tree.sync(guild=ctx.guild)
            else:
                synced = await self.bot.tree.sync()

            embed = self.bot.ui_manager.success_embed(
                "Commands Synced",
                f"Successfully synced {len(synced)} commands ({target})"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = self.bot.ui_manager.error_embed(
                "Sync Error",
                f"Error syncing commands: {str(e)}"
            )
            await ctx.send(embed=embed)

    @app_commands.command(
        name="debug_db",
        description="[Owner] Get database diagnostics"
    )
    async def debug_db(self, interaction: discord.Interaction):
        """Get database diagnostics and statistics"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                ),
                ephemeral=True
            )
            return

        try:
            # Get database stats
            connection_stats = await self.bot.db_manager.get_connection_stats()
            db_size = await self.bot.db_manager.get_database_size()

            # Create stats embed
            embed = self.bot.ui_manager.info_embed(
                "Database Diagnostics",
                "Current database statistics and health information"
            )

            # Connection info
            embed.add_field(
                name="Connection Status",
                value=f"Status: {connection_stats['status']}\nPrefix: {connection_stats['prefix']}",
                inline=False
            )

            # Size info
            embed.add_field(
                name="Database Size",
                value=f"Total: {db_size/1024/1024:.2f} MB\nKeys: {connection_stats['total_keys']:,}",
                inline=True
            )

            # Collection stats
            collections = connection_stats.get('collections', {})
            if collections:
                collection_text = []
                for name, stats in collections.items():
                    collection_text.append(
                        f"**{name}**: {stats['keys']} keys ({stats['size']/1024:.1f} KB)"
                    )
                embed.add_field(
                    name="Collections",
                    value="\n".join(collection_text),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="debug_system",
        description="[Owner] Get system diagnostics"
    )
    async def debug_system(self, interaction: discord.Interaction):
        """Get system diagnostics"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                ),
                ephemeral=True
            )
            return

        try:
            # Create stats embed
            embed = self.bot.ui_manager.info_embed(
                "System Diagnostics",
                "Current system statistics and resource usage"
            )

            # System info
            embed.add_field(
                name="System",
                value=f"OS: {platform.system()} {platform.release()}\n"
                      f"Python: {platform.python_version()}\n"
                      f"Discord.py: {discord.__version__}",
                inline=False
            )

            # Process info
            process = psutil.Process()
            with process.oneshot():
                mem_info = process.memory_full_info()
                cpu_percent = process.cpu_percent(interval=0.1)
                threads = process.num_threads()
                embed.add_field(
                    name="Process",
                    value=f"CPU: {cpu_percent:.1f}%\n"
                          f"Memory: {mem_info.rss/1024/1024:.1f} MB\n"
                          f"Threads: {threads}",
                    inline=True
                )

            # System resources
            embed.add_field(
                name="System Resources",
                value=f"CPU Load: {psutil.cpu_percent()}%\n"
                      f"Memory: {psutil.virtual_memory().percent}%\n"
                      f"Disk: {psutil.disk_usage('/').percent}%",
                inline=True
            )

            # Bot info
            guilds = len(self.bot.guilds)
            users = sum(g.member_count for g in self.bot.guilds)
            latency = round(self.bot.latency * 1000)
            embed.add_field(
                name="Bot Stats",
                value=f"Guilds: {guilds:,}\n"
                      f"Users: {users:,}\n"
                      f"Latency: {latency}ms",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="guild_debug",
        description="[Owner] Debug guild data"
    )
    @app_commands.describe(
        guild_id="ID of the guild to debug (current guild if not specified)"
    )
    async def guild_debug(
        self,
        interaction: discord.Interaction,
        guild_id: Optional[str] = None
    ):
        """Debug guild data and settings"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                ),
                ephemeral=True
            )
            return

        try:
            # Get guild data
            target_guild_id = int(guild_id) if guild_id else interaction.guild_id
            guild = self.bot.get_guild(target_guild_id)
            if not guild:
                raise ValueError(f"Could not find guild with ID {target_guild_id}")

            guild_data = await self.bot.db_manager.get_guild_data(target_guild_id)

            # Create debug embed
            embed = self.bot.ui_manager.info_embed(
                f"Guild Debug: {guild.name}",
                f"ID: {guild.id}"
            )

            # Add configuration sections
            for section, data in guild_data.items():
                if isinstance(data, dict):
                    value = "\n".join(f"{k}: {v}" for k, v in data.items())
                elif isinstance(data, list):
                    value = f"{len(data)} items"
                else:
                    value = str(data)

                if len(value) > 1024:
                    value = value[:1021] + "..."

                embed.add_field(
                    name=section,
                    value=f"```{value}```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="maintenance",
        description="[Owner] Toggle maintenance mode"
    )
    async def maintenance(self, interaction: discord.Interaction):
        """Toggle bot maintenance mode"""
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                ),
                ephemeral=True
            )
            return

        try:
            # Get current maintenance status
            config = await self.bot.db_manager.get_data('bot_config', 'maintenance')
            current_mode = config.get('enabled', False) if config else False
            
            # Ask for confirmation
            confirm = await self.bot.ui_manager.confirm_action(
                interaction,
                "Maintenance Mode",
                f"Are you sure you want to {'disable' if current_mode else 'enable'} maintenance mode?",
                confirm_label="Confirm",
                cancel_label="Cancel"
            )
            
            if not confirm:
                await interaction.response.send_message("Maintenance mode change cancelled.", ephemeral=True)
                return

            # Toggle maintenance mode in database
            maintenance_mode = not current_mode

            await self.bot.db_manager.set_data(
                'bot_config',
                'maintenance',
                {
                    'enabled': maintenance_mode,
                    'timestamp': datetime.utcnow().isoformat(),
                    'toggled_by': str(interaction.user.id)
                }
            )

            if maintenance_mode:
                # Verify all important systems before entering maintenance
                db_health = await self.bot.db_manager.check_connection()
                if not db_health:
                    raise Exception("Database health check failed before entering maintenance mode")
                    
                # Set status to maintenance mode
                await self.bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching,
                        name="🔧 Maintenance Mode"
                    ),
                    status=discord.Status.dnd
                )
                embed = self.bot.ui_manager.warning_embed(
                    "Maintenance Mode Enabled",
                    "Bot is now in maintenance mode. Only owner commands will work."
                )
                
                # Log maintenance start
                await self.bot.db_manager.log_event(
                    0,  # Global event
                    interaction.user.id,
                    "maintenance_start",
                    "Bot entered maintenance mode"
                )
                
                # Notify all servers with logging enabled
                for guild in self.bot.guilds:
                    try:
                        guild_data = await self.bot.db_manager.get_guild_data(guild.id)
                        logs_config = guild_data.get('logs_config', {})
                        
                        if logs_config.get('enabled') and logs_config.get('mod_channel'):
                            log_channel = guild.get_channel(int(logs_config['mod_channel']))
                            if log_channel:
                                log_embed = self.bot.ui_manager.warning_embed(
                                    "Bot Maintenance Mode",
                                    "The bot has entered maintenance mode. Only essential functions will be available until maintenance is complete."
                                )
                                await log_channel.send(embed=log_embed)
                    except Exception as e:
                        print(f"Failed to send maintenance notification to guild {guild.id}: {e}")
            else:
                # Verify systems are healthy before exiting maintenance
                db_health = await self.bot.db_manager.check_connection()
                if not db_health:
                    raise Exception("Database health check failed, cannot exit maintenance mode")
                
                # Reset status
                await self.bot.change_presence(
                    activity=discord.Game(name="with commands"),
                    status=discord.Status.online
                )
                embed = self.bot.ui_manager.success_embed(
                    "Maintenance Mode Disabled",
                    "Bot has returned to normal operation."
                )
                
                # Log maintenance end
                await self.bot.db_manager.log_event(
                    0,  # Global event
                    interaction.user.id,
                    "maintenance_end",
                    "Bot exited maintenance mode"
                )
                
                # Notify all servers with logging enabled
                for guild in self.bot.guilds:
                    try:
                        guild_data = await self.bot.db_manager.get_guild_data(guild.id)
                        logs_config = guild_data.get('logs_config', {})
                        
                        if logs_config.get('enabled') and logs_config.get('mod_channel'):
                            log_channel = guild.get_channel(int(logs_config['mod_channel']))
                            if log_channel:
                                log_embed = self.bot.ui_manager.success_embed(
                                    "Bot Maintenance Complete",
                                    "The bot has exited maintenance mode and all functions are now available."
                                )
                                await log_channel.send(embed=log_embed)
                    except Exception as e:
                        print(f"Failed to send maintenance notification to guild {guild.id}: {e}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @commands.command(name='cleanup_db', hidden=True)
    async def cleanup_db(self, ctx, days: int = 30):
        """Clean up old database entries"""
        if days < 7:
            await ctx.send("Minimum cleanup period is 7 days for safety.")
            return
            
        confirm = await self.bot.ui_manager.confirm_action(
            ctx,
            "Database Cleanup",
            f"⚠️ This will delete data older than {days} days. This action cannot be undone.\nAre you sure?",
            confirm_label="Clean Up",
            cancel_label="Cancel"
        )
        
        if not confirm:
            await ctx.send("Database cleanup cancelled.")
            return
            
        try:
            message = await ctx.send("Starting database cleanup...")
            result = await self.bot.db_manager.cleanup_old_data(days)
            
            if result:
                stats = await self.bot.db_manager.get_connection_stats()
                embed = self.bot.ui_manager.success_embed(
                    "Database Cleanup Complete",
                    f"Cleaned up entries older than {days} days\n"
                    f"Current size: {stats['total_size']/1024/1024:.2f} MB\n"
                    f"Total keys: {stats['total_keys']:,}"
                )
            else:
                embed = self.bot.ui_manager.error_embed(
                    "Cleanup Failed",
                    "Failed to clean up database"
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error during cleanup: {e}")

    @commands.command(name='optimize_db', hidden=True)
    async def optimize_db(self, ctx):
        """Optimize database storage"""
        try:
            message = await ctx.send("Starting database optimization...")
            result = await self.bot.db_manager.optimize()
            
            if result:
                stats = await self.bot.db_manager.get_connection_stats()
                embed = self.bot.ui_manager.success_embed(
                    "Database Optimization Complete",
                    f"Current size: {stats['total_size']/1024/1024:.2f} MB\n"
                    f"Total keys: {stats['total_keys']:,}"
                )
            else:
                embed = self.bot.ui_manager.error_embed(
                    "Optimization Failed",
                    "Failed to optimize database"
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error during optimization: {e}")

async def setup(bot):
    await bot.add_cog(DebugCog(bot))