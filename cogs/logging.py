import json
from datetime import datetime, timedelta
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice

class LoggingCog(commands.Cog):
    """Cog for managing logging settings and viewing logs"""
    
    def __init__(self, bot):
        self.bot = bot
        self.log = bot.get_logger("LoggingCog")

    async def _check_manage_server(self, interaction: discord.Interaction) -> bool:
        """Check if user has manage server permissions"""
        try:
            if not interaction.guild:
                return False
            return interaction.user.guild_permissions.manage_guild if isinstance(interaction.user, discord.Member) else False
        except Exception as e:
            self.log.error(f"Error checking server permissions: {e}", exc_info=True)
            return False

    @app_commands.command(name="logging", description="Configure logging settings.")
    @app_commands.guild_only()
    @app_commands.choices(type=[
        Choice(name="Set Channel", value="channel"),
        Choice(name="Enable Events", value="enable"),
        Choice(name="Disable Events", value="disable")
    ])
    async def logging(self, interaction: discord.Interaction, type: str, channel: Optional[discord.TextChannel] = None):
        """Configure logging settings."""
        
        try:
            if not await self._check_manage_server(interaction):
                return await interaction.response.send_message("You need the Manage Server permission to use this command!", ephemeral=True)
                
            if type == "channel":
                if not channel:
                    return await interaction.response.send_message("Please specify a channel!", ephemeral=True)
                    
                try:
                    # Test if bot can send messages in the channel
                    await channel.send("🔍 Testing logging channel permissions...", delete_after=0)
                    
                    # Get current settings or create default with whisper events
                    current_settings = {
                        "events": [
                            "message_delete", "message_edit", 
                            "member_join", "member_leave", 
                            "member_ban", "member_unban",
                            "whisper_create", "whisper_close",  # Added whisper events
                            "whisper_delete"
                        ]
                    }
                    
                    if not interaction.guild:
                        return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
                    
                    # Save settings using proper method
                    await self.bot.db.set_logging_settings(
                        interaction.guild.id,
                        channel.id,
                        json.dumps(current_settings)
                    )
                    
                    await interaction.response.send_message(f"✅ Logging channel set to {channel.mention}")
                    
                except discord.Forbidden as e:
                    self.log.warning(f"Permission error in logging command: {e}")
                    await interaction.response.send_message("❌ I don't have permission to send messages in that channel!", ephemeral=True)
                except Exception as e:
                    self.log.error(f"Error in logging command: {e}", exc_info=True)
                    await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
                    
            elif type == "enable" or type == "disable":
                # Create select menu for events
                class EventSelect(discord.ui.Select):
                    def __init__(self, options: List[str], placeholder: str):
                        super().__init__(
                            placeholder=placeholder,
                            min_values=1,
                            max_values=len(options),
                            options=[
                                discord.SelectOption(label=event.replace("_", " ").title(), value=event)
                                for event in options
                            ]
                        )
                
                class EventView(discord.ui.View):
                    def __init__(self, timeout = 180):
                        super().__init__(timeout=timeout)
                        self.selected_events = []
                        
                        all_events = [
                            # Server Events
                            "message_delete",
                            "message_edit",
                            "member_join",
                            "member_leave",
                            "member_ban",
                            "member_unban",
                            "role_create",
                            "role_delete",
                            "channel_create",
                            "channel_delete",
                            # Whisper Events
                            "whisper_create",
                            "whisper_close",
                            "whisper_delete"
                        ]
                        
                        select = EventSelect(
                            all_events,
                            f"Select events to {'enable' if type == 'enable' else 'disable'}"
                        )
                        
                        async def select_callback(interaction: discord.Interaction):
                            self.selected_events = select.values
                            self.stop()
                            
                        select.callback = select_callback
                        self.add_item(select)
                
                view = EventView()
                await interaction.response.send_message(
                    f"Please select the events you want to {'enable' if type == 'enable' else 'disable'}:",
                    view=view,
                    ephemeral=True
                )
                
                timeout = await view.wait()
                if timeout:
                    await interaction.followup.send("Selection timed out!", ephemeral=True)
                    return
                    
                try:
                    # Get current settings from logging_settings table
                    if not interaction.guild:
                        return await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
                    settings = await self.bot.db.get_logging_settings(interaction.guild.id)
                    if settings:
                        options = json.loads(settings['options_json'])
                    else:
                        options = {"events": []}
                    
                    # Update events
                    if type == "enable":
                        options["events"] = list(set(options["events"] + view.selected_events))
                    else:
                        options["events"] = [e for e in options["events"] if e not in view.selected_events]
                    
                    # Save updated settings using proper method
                    await self.bot.db.set_logging_settings(
                        interaction.guild.id,
                        settings['log_channel_id'] if settings else 0,  # Keep existing channel or use 0
                        json.dumps(options)
                    )
                    
                    events_str = ", ".join(e.replace("_", " ").title() for e in view.selected_events)
                    await interaction.followup.send(
                        f"✅ Successfully {'enabled' if type == 'enable' else 'disabled'} the following events: {events_str}",
                        ephemeral=True
                    )
                    
                except Exception as e:
                    await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

        except Exception as e:
            self.log.error(f"Unexpected error in logging command: {e}", exc_info=True)
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

    @app_commands.command(name="viewlogs", description="View event logs with filters.")
    @app_commands.guild_only()
    @app_commands.describe(
        type="Type of log to view",
        limit="Number of entries to show (default: 10)",
        user="Filter by user",
        days="Number of days to look back (default: 7)"
    )
    async def viewlogs(
        self,
        interaction: discord.Interaction,
        type: Optional[str] = None,
        limit: Optional[int] = 10,
        user: Optional[discord.User] = None,
        days: Optional[int] = 7
    ):
        """View event logs with filters."""
        
        try:
            if not await self._check_manage_server(interaction):
                return await interaction.response.send_message("You need the Manage Server permission to use this command!", ephemeral=True)
                
            if not interaction.guild:
                return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
            # Use the proper get_logs_filtered method
            logs = await self.bot.db.get_logs_filtered(
                interaction.guild.id,
                type,  # event_type
                days   # since_days
            )
            
            if not logs:
                return await interaction.response.send_message("No logs found matching the filters!", ephemeral=True)
            
            # Filter by user if specified
            if user:
                logs = [log for log in logs if str(user.id) in log['description']]
            
            # Limit results
            logs = logs[:limit]
            
            # Create embed pages
            embeds = []
            for i in range(0, len(logs), 5):
                embed = discord.Embed(
                    title=f"📋 Logs for {interaction.guild.name}",
                    color=discord.Color.blue()
                )
                
                chunk = logs[i:i+5]
                for log in chunk:
                    embed.add_field(
                        name=f"{log['event_type']} • {discord.utils.format_dt(log['timestamp'], 'R')}",
                        value=log['description'],
                        inline=False
                    )
                
                embed.set_footer(text=f"Page {i//5 + 1}/{(len(logs)-1)//5 + 1}")
                embeds.append(embed)
            
            # Create pagination view
            class LogPaginator(discord.ui.View):
                def __init__(self, embeds: List[discord.Embed]):
                    super().__init__(timeout=180)
                    self.embeds = embeds
                    self.current = 0
                    
                @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray)
                async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.current = max(0, self.current - 1)
                    await interaction.response.edit_message(embed=self.embeds[self.current])
                    
                @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray)
                async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.current = min(len(self.embeds) - 1, self.current + 1)
                    await interaction.response.edit_message(embed=self.embeds[self.current])
            
            # Send first page with pagination if needed
            if len(embeds) > 1:
                await interaction.response.send_message(embed=embeds[0], view=LogPaginator(embeds))
            else:
                await interaction.response.send_message(embed=embeds[0])
                
        except Exception as e:
            self.log.error(f"Error viewing logs: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))
