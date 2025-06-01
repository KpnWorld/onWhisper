import json
from datetime import datetime, timedelta
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice
import logging

# Define EventSelect and EventView outside the command
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
    def __init__(self, all_events: List[str], type: str):
        super().__init__(timeout=180)
        self.selected_events = []
        
        select = EventSelect(
            all_events,
            f"Select events to {'enable' if type == 'enable' else 'disable'}"
        )
        
        async def select_callback(interaction: discord.Interaction):
            self.selected_events = select.values
            await interaction.response.defer()
            self.stop()
            
        select.callback = select_callback
        self.add_item(select)

class LoggingCog(commands.Cog):
    """Cog for managing logging settings and viewing logs"""
    
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.logging")
        self.all_events = [
            "message_delete", "message_edit",
            "member_join", "member_leave",
            "member_ban", "member_unban",
            "role_create", "role_delete",
            "channel_create", "channel_delete",
            "whisper_create", "whisper_close",
            "whisper_delete"
        ]

    # Message Events    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Called when a message is deleted"""
        if not message.guild or message.author.bot:
            return
        channel_ref = f"#{message.channel.name}" if isinstance(message.channel, discord.TextChannel) else "a channel"
        description = f"Message by {message.author.mention} deleted in {channel_ref}"
        if message.content:
            description += f"\nContent: {message.content[:1900]}"  # Truncate long messages        await self._log_event(message.guild.id, "message_delete", description)
        
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Called when a message is edited"""
        if not before.guild or before.author.bot or before.content == after.content:
            return
        channel_ref = f"#{before.channel.name}" if isinstance(before.channel, discord.TextChannel) else "a channel"
        description = (f"Message by {before.author.mention} edited in {channel_ref}\n"
                      f"Before: {before.content[:900]}\nAfter: {after.content[:900]}")  # Truncate long messages
        await self._log_event(before.guild.id, "message_edit", description)

    # Member Events
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Called when a member joins the server"""
        if member.bot:
            return
        description = f"{member.mention} joined the server"
        await self._log_event(member.guild.id, "member_join", description)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Called when a member leaves the server"""
        if member.bot:
            return
        description = f"{member.mention} left the server"
        await self._log_event(member.guild.id, "member_leave", description)

    # Ban Events
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Called when a member is banned"""
        description = f"{user.mention} was banned from the server"
        await self._log_event(guild.id, "member_ban", description)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Called when a member is unbanned"""
        description = f"{user.mention} was unbanned from the server"
        await self._log_event(guild.id, "member_unban", description)

    # Role Events
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Called when a role is created"""
        description = f"Role created: {role.mention}"
        await self._log_event(role.guild.id, "role_create", description)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Called when a role is deleted"""
        description = f"Role deleted: {role.name}"
        await self._log_event(role.guild.id, "role_delete", description)

    # Channel Events
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Called when a channel is created"""
        description = f"Channel created: {channel.mention}"
        await self._log_event(channel.guild.id, "channel_create", description)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Called when a channel is deleted"""
        description = f"Channel deleted: #{channel.name}"
        await self._log_event(channel.guild.id, "channel_delete", description)

    async def _check_manage_server(self, interaction: discord.Interaction) -> bool:
        """Check if user has manage server permissions"""
        try:
            if not interaction.guild:
                return False
            return interaction.user.guild_permissions.manage_guild if isinstance(interaction.user, discord.Member) else False
        except Exception as e:
            self.log.error(f"Error checking server permissions: {e}", exc_info=True)
            return False

    async def _check_logging_enabled(self, guild_id: int) -> bool:
        """Check if logging feature is enabled"""
        feature_settings = await self.bot.db.get_feature_settings(guild_id, "logging")
        return bool(feature_settings and feature_settings['enabled'])

    async def _log_event(self, guild_id: int, event_type: str, description: str):
        """Log an event if logging is enabled and event type is configured"""
        try:
            if not await self._check_logging_enabled(guild_id):
                return

            feature_settings = await self.bot.db.get_feature_settings(guild_id, "logging")
            options = feature_settings['options']
            enabled_events = options.get('events', [])
            if event_type not in enabled_events:
                return

            channel_id = options.get('channel_id')
            if not channel_id:
                return

            # Insert the log entry
            await self.bot.db.insert_log(guild_id, event_type, description)
            
        except Exception as e:
            self.log.error(f"Error logging event: {e}", exc_info=True)

    @app_commands.command(name="logging")
    @app_commands.guild_only()
    @app_commands.choices(type=[
        Choice(name="Set Channel", value="channel"),
        Choice(name="Enable Events", value="enable"),
        Choice(name="Disable Events", value="disable")
    ])
    async def logging(self, interaction: discord.Interaction, type: str, channel: Optional[discord.TextChannel] = None):
        """Configure logging settings."""
        # Remove toggle option and keep only channel and event settings
        if type == "toggle":
            await interaction.response.send_message(
                "❌ The toggle command has been moved to `/config setting:Toggle Logging`",
                ephemeral=True
            )
            return

        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)

        if not await self._check_manage_server(interaction):
            return await interaction.response.send_message("You need Manage Server permission!", ephemeral=True)

        try:
            if type == "channel":
                try:
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
                        
                except Exception as e:
                    self.log.error(f"Unexpected error in logging command: {e}", exc_info=True)
                    await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

            elif type == "enable" or type == "disable":
                # Create event selection view
                view = EventView(self.all_events, type)
                await interaction.response.send_message(
                    f"Please select the events you want to {type}:",
                    view=view,
                    ephemeral=True
                )
                
                # Wait for selection
                timed_out = await view.wait()
                if timed_out:
                    return await interaction.followup.send("Selection timed out!", ephemeral=True)
                
                if not view.selected_events:
                    return await interaction.followup.send("No events selected!", ephemeral=True)
                    
                try:
                    settings = await self.bot.db.get_feature_settings(interaction.guild.id, "logging")
                    current_events = settings.get('options', {}).get('events', []) if settings else []
                    channel_id = settings.get('options', {}).get('channel_id') if settings else 0
                    
                    # Ensure current_events is a list
                    if isinstance(current_events, str):
                        current_events = [current_events]
                    
                    # Update events list
                    if type == "enable":
                        # Combine lists and remove duplicates using set
                        new_events = list(set(current_events + list(view.selected_events)))
                    else:
                        # Remove selected events from current events
                        new_events = [e for e in current_events if e not in view.selected_events]
                    
                    # Save updated settings
                    await self.bot.db.set_feature_settings(
                        interaction.guild.id,
                        "logging",
                        True,
                        {
                            'channel_id': channel_id,
                            'events': new_events
                        }
                    )
                    
                    events_str = ", ".join(e.replace("_", " ").title() for e in view.selected_events)
                    await interaction.followup.send(
                        f"✅ Successfully {'enabled' if type == 'enable' else 'disabled'} the following events: {events_str}",
                        ephemeral=True
                    )
                    
                except Exception as e:
                    await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
                    self.log.error(f"Error updating logging events: {e}", exc_info=True)

        except Exception as e:
            self.log.error(f"Error in logging command: {e}", exc_info=True)
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
