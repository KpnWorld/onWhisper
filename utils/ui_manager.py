import discord
from discord.ext import commands
from discord import Embed
from typing import List, Dict, Any, Optional
from datetime import datetime

class CommandMultiSelectView(discord.ui.View):
    def __init__(self, options: List[Dict[str, Any]], placeholder: str, min_values: int = 1, max_values: int = 1):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Select(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=[discord.SelectOption(**opt) for opt in options]
        ))
        self.values = []
        self.message = None

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.values = select.values
        self.stop()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)
        self.stop()

class UIManager:
    """Handles consistent UI elements across the bot"""

    def __init__(self, bot):
        self.bot = bot
        # Brand colors
        self.colors = {
            'primary': 0x5865F2,    # Discord blurple for main actions
            'success': 0x57F287,    # Green for success messages
            'warning': 0xFEE75C,    # Yellow for warnings
            'error': 0xED4245,      # Red for errors
            'info': 0x5865F2,       # Blurple for info
            'whisper': 0x9C84EF,    # Purple for whisper system
            'xp': 0x2ECC71,         # Green for leveling system
            'mod': 0xF1C40F,        # Yellow for moderation
            'log': 0x95A5A6         # Gray for logs
        }

    def base_embed(self, title: str, description: Optional[str] = None, color: int = None) -> Embed:
        """Create a base embed with consistent styling"""
        embed = Embed(
            title=title,
            description=description,
            color=color or self.colors['primary']
        )
        embed.set_footer(text="onWhisper")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def success_embed(self, title: str, description: str) -> Embed:
        """Create a success embed"""
        return self.base_embed(title, description, self.colors['success'])

    def error_embed(self, title: str, description: str) -> Embed:
        """Create an error embed"""
        return self.base_embed(f"❌ {title}", description, self.colors['error'])

    def warning_embed(self, title: str, description: str) -> Embed:
        """Create a warning embed"""
        return self.base_embed(f"⚠️ {title}", description, self.colors['warning'])

    def info_embed(self, title: str, description: str) -> Embed:
        """Create an info embed"""
        return self.base_embed(title, description, self.colors['info'])

    def whisper_embed(self, title: str, description: str) -> Embed:
        """Create a whisper-themed embed"""
        embed = self.base_embed(title, description, self.colors['whisper'])
        embed.set_footer(text="onWhisper • Private Thread")
        return embed

    def xp_embed(self, title: str, description: str) -> Embed:
        """Create an XP/leveling themed embed"""
        embed = self.base_embed(title, description, self.colors['xp'])
        embed.set_footer(text="onWhisper • Leveling")
        return embed

    def mod_embed(self, title: str, description: str) -> Embed:
        """Create a moderation themed embed"""
        embed = self.base_embed(title, description, self.colors['mod'])
        embed.set_footer(text="onWhisper • Moderation")
        return embed

    def log_embed(self, title: str, description: str, author: Optional[discord.Member] = None) -> Embed:
        """Create a log-themed embed"""
        embed = self.base_embed(title, description, self.colors['log'])
        if author:
            embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        embed.set_footer(text="onWhisper • Log")
        return embed

    def feature_error_embed(self, feature: str, error_type: str, details: str) -> Embed:
        """Create an error embed for specific features"""
        titles = {
            'whisper': "Whisper System Error",
            'xp': "Leveling System Error",
            'mod': "Moderation Error",
            'roles': "Role Management Error"
        }
        colors = {
            'whisper': self.colors['whisper'],
            'xp': self.colors['xp'],
            'mod': self.colors['mod'],
            'roles': self.colors['primary']
        }
        return self.base_embed(
            f"❌ {titles.get(feature, 'System Error')}",
            f"**{error_type}**: {details}",
            colors.get(feature, self.colors['error'])
        )

    def error_to_embed(self, error: Exception) -> Embed:
        """Convert an exception to an appropriate error embed"""
        if isinstance(error, self.bot.WhisperError):
            return self.feature_error_embed(
                'whisper',
                error.__class__.__name__.replace('Whisper', ''),
                str(error)
            )
        elif isinstance(error, self.bot.LevelingError):
            return self.feature_error_embed(
                'xp',
                error.__class__.__name__.replace('XP', '').replace('Leveling', ''),
                str(error)
            )
        elif isinstance(error, self.bot.ReactionRoleError):
            return self.feature_error_embed(
                'roles',
                'Configuration Error',
                str(error)
            )
        # Generic error fallback
        return self.error_embed(
            "Error",
            str(error)
        )

    async def send_embed(self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = False):
        """Send a single embed easily."""
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    class Paginator(discord.ui.View):
        def __init__(self, pages: list[discord.Embed], *, timeout: int = 180, show_page_indicator: bool = True):
            super().__init__(timeout=timeout)
            self.pages = pages
            self.current_page = 0
            self.show_indicator = show_page_indicator
            
            # Update button states
            self.update_buttons()

        def update_buttons(self):
            # First and previous buttons
            self.first_page.disabled = self.current_page == 0
            self.prev_page.disabled = self.current_page == 0
            
            # Next and last buttons
            self.next_page.disabled = self.current_page == len(self.pages) - 1
            self.last_page.disabled = self.current_page == len(self.pages) - 1

            if self.show_indicator:
                # Update page counter
                self.page_counter.label = f"Page {self.current_page + 1}/{len(self.pages)}"

        def get_current_page(self) -> discord.Embed:
            return self.pages[self.current_page]

        @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
        async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page(), view=self)

        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = max(0, self.current_page - 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page(), view=self)

        @discord.ui.button(label="Page", style=discord.ButtonStyle.grey, disabled=True)
        async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
            pass

        @discord.ui.button(label=">", style=discord.ButtonStyle.blurple)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = min(len(self.pages) - 1, self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page(), view=self)

        @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
        async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = len(self.pages) - 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page(), view=self)

        async def on_timeout(self):
            # Disable all buttons when the view times out
            for item in self.children:
                item.disabled = True
            
            # Try to update the message with disabled buttons
            try:
                message = self.message
                await message.edit(view=self)
            except:
                pass

    async def paginate(
        self,
        interaction: discord.Interaction,
        pages: list[discord.Embed],
        *,
        timeout: int = 180,
        ephemeral: bool = False,
        show_page_indicator: bool = True
    ) -> None:
        """
        Creates and sends a paginated message with the given embeds.
        
        Args:
            interaction: The interaction to respond to
            pages: List of embeds to paginate
            timeout: How long the paginator should be active
            ephemeral: Whether the message should be ephemeral
            show_page_indicator: Whether to show the page counter button
        """
        if not pages:
            raise ValueError("Cannot paginate an empty list of pages")

        paginator = self.Paginator(
            pages=pages,
            timeout=timeout,
            show_page_indicator=show_page_indicator
        )
        
        await interaction.response.send_message(
            embed=paginator.get_current_page(),
            view=paginator,
            ephemeral=ephemeral
        )

    async def confirm_action(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        timeout: int = 60,
        ephemeral: bool = True
    ) -> bool:
        """Shows a confirmation dialog and returns True if confirmed, False otherwise."""
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=timeout)
                self.value = None
                self.message = None

            @discord.ui.button(label=confirm_label, style=discord.ButtonStyle.success)
            async def confirm(self, button: discord.ui.Button, button_interaction: discord.Interaction):
                self.value = True
                for item in self.children:
                    item.disabled = True
                await button_interaction.response.defer()
                await self.message.edit(view=self)
                self.stop()

            @discord.ui.button(label=cancel_label, style=discord.ButtonStyle.secondary)
            async def cancel(self, button: discord.ui.Button, button_interaction: discord.Interaction):
                self.value = False
                for item in self.children:
                    item.disabled = True
                await button_interaction.response.defer()
                await self.message.edit(view=self)
                self.stop()

            async def on_timeout(self):
                if self.message:
                    self.value = False
                    for item in self.children:
                        item.disabled = True
                    await self.message.edit(view=self)
                self.stop()

        view = ConfirmView()
        embed = self.info_embed(
            title=title,
            description=description
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
        view.message = await interaction.original_response()
        await view.wait()
        return view.value

    class CommandSelectView(discord.ui.View):
        def __init__(self, options: list, placeholder: str = "Select an option", timeout: int = 180):
            super().__init__(timeout=timeout)
            self.result = None
            self.message = None
            
            # Create select menu directly in view
            select_menu = discord.ui.Select(
                placeholder=placeholder,
                min_values=1,
                max_values=1,
                options=[discord.SelectOption(
                    label=option.get("label", ""),
                    description=option.get("description", ""),
                    value=option.get("value", ""),
                    emoji=option.get("emoji", None)
                ) for option in options]
            )
            
            async def select_callback(interaction: discord.Interaction):
                await interaction.response.defer()
                self.result = select_menu.values[0]
                self.stop()
            
            select_menu.callback = select_callback
            self.add_item(select_menu)

        async def on_timeout(self) -> None:
            if self.message:
                try:
                    await self.message.edit(view=None)
                except:
                    pass

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            return True

    class HelpMenuView(discord.ui.View):
        def __init__(self, bot, ui_manager):
            super().__init__(timeout=180)
            self.bot = bot
            self.ui = ui_manager
            self.message = None
            
            # Create the select menu
            select_menu = discord.ui.Select(
                placeholder="Select a category",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label="Leveling",
                        description="XP and level-related commands",
                        value="leveling",
                        emoji="📊"
                    ),
                    discord.SelectOption(
                        label="Moderation",
                        description="Server moderation commands",
                        value="moderation", 
                        emoji="🛡️"
                    ),
                    discord.SelectOption(
                        label="Configuration",
                        description="Server configuration commands",
                        value="config",
                        emoji="⚙️"
                    ),
                    discord.SelectOption(
                        label="Roles",
                        description="Role management commands",
                        value="roles",
                        emoji="👥"
                    ),
                    discord.SelectOption(
                        label="Whispers",
                        description="Private thread commands",
                        value="whispers",
                        emoji="💬"
                    ),
                    discord.SelectOption(
                        label="Information",
                        description="Bot and server info commands",
                        value="info",
                        emoji="ℹ️"
                    )
                ]
            )
            
            async def select_callback(interaction: discord.Interaction):
                # Get commands for selected category
                category = select_menu.values[0]
                commands = []
                
                # Get all application commands
                for cmd in self.bot.tree.get_commands():
                    if category == "leveling" and cmd.name.startswith(("xp_", "level_", "config_xp")):
                        commands.append(cmd)
                    elif category == "moderation" and cmd.name.startswith(("warn", "kick", "ban", "timeout", "mute", "purge", "clear", "lockdown")):
                        commands.append(cmd)
                    elif category == "config" and cmd.name.startswith("config_"):
                        commands.append(cmd)
                    elif category == "roles" and cmd.name.startswith(("roles_", "role_")):
                        commands.append(cmd)
                    elif category == "whispers" and cmd.name.startswith("whisper"):
                        commands.append(cmd)
                    elif category == "info" and cmd.name.startswith("info"):
                        commands.append(cmd)

                # Create embed for category
                embed = self.ui.info_embed(
                    f"{select_menu.values[0].title()} Commands",
                    "Use `/info help <command>` for detailed information about a specific command."
                )

                # Add commands to embed
                if commands:
                    value = "\n".join(f"• `/{cmd.name}` - {cmd.description}" for cmd in sorted(commands, key=lambda x: x.name))
                    if len(value) > 1024:
                        value = value[:1021] + "..."
                    embed.add_field(name="Available Commands", value=value, inline=False)
                else:
                    embed.add_field(name="Available Commands", value="No commands found for this category", inline=False)

                await interaction.response.edit_message(embed=embed, view=self)

            select_menu.callback = select_callback
            self.add_item(select_menu)

        async def on_timeout(self):
            if self.message:
                try:
                    await self.message.edit(view=None)
                except:
                    pass

    class WhisperControlsView(discord.ui.View):
        def __init__(self, bot):
            super().__init__(timeout=None)
            self.bot = bot

        async def handle_control(self, button: discord.ui.Button, interaction: discord.Interaction):
            """Common handler for control buttons"""
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "These controls can only be used in whisper threads"
                    ),
                    ephemeral=True
                )
                return False

            # Get whisper data
            whispers = await self.bot.db_manager.get_all_whispers(interaction.guild_id)  # Get all whispers, not just active
            whisper = next((w for w in whispers if str(w['thread_id']) == str(interaction.channel.id)), None)
            
            if not whisper:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "Unable to find whisper data for this thread"
                    ),
                    ephemeral=True
                )
                return False

            return True

        @discord.ui.button(label="Re-open Thread", style=discord.ButtonStyle.green, custom_id="reopen_whisper")
        async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.handle_control(button, interaction):
                return

            if not interaction.user.guild_permissions.manage_threads:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Permissions",
                        "You need the Manage Threads permission to re-open whispers"
                    ),
                    ephemeral=True
                )
                return

            try:
                await interaction.channel.edit(archived=False, locked=False)
                await self.bot.db_manager.reactivate_whisper(interaction.guild_id, str(interaction.channel.id))
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Thread Reopened",
                        "This whisper thread has been reopened"
                    )
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "I don't have permission to reopen this thread"
                    ),
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        f"Failed to reopen thread: {str(e)}"
                    ),
                    ephemeral=True
                )

        @discord.ui.button(label="Delete Thread", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def delete_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if not interaction.user.guild_permissions.manage_threads:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.error_embed(
                            "Unauthorized",
                            "You need manage threads permission to delete whispers"
                        ),
                        ephemeral=True
                    )
                    return

                await interaction.response.defer()

                # Log deletion first since we'll lose access to channel data
                log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                    log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                    if log_channel:
                        embed = self.bot.ui_manager.log_embed(
                            "Whisper Deleted",
                            f"Whisper thread deleted by {interaction.user.mention}",
                            interaction.user
                        )
                        embed.add_field(name="Thread", value=f"#{interaction.channel.name}")
                        await log_channel.send(embed=embed)

                # Delete from database and Discord
                await self.bot.db_manager.delete_whisper(interaction.guild_id, str(interaction.channel.id))
                await interaction.channel.delete()

            except Exception as e:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )

        @discord.ui.button(label="Save Thread", style=discord.ButtonStyle.primary, emoji="💾")
        async def save_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                if not interaction.user.guild_permissions.manage_threads:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.error_embed(
                            "Unauthorized",
                            "You need manage threads permission to save whispers"
                        ),
                        ephemeral=True
                    )
                    return

                await interaction.response.defer()

                # Save thread history
                messages = []
                async for message in interaction.channel.history(limit=None, oldest_first=True):
                    messages.append({
                        'author': str(message.author),
                        'content': message.content,
                        'timestamp': message.created_at.isoformat(),
                        'attachments': [a.url for a in message.attachments]
                    })

                # Store in database
                await self.bot.db_manager.save_whisper_history(
                    interaction.guild_id,
                    str(interaction.channel.id),
                    messages
                )

                await interaction.followup.send(
                    embed=self.bot.ui_manager.success_embed(
                        "Thread Saved",
                        f"Thread history has been saved and will be retained"
                    ),
                    ephemeral=True
                )

                # Log if enabled
                log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                    log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                    if log_channel:
                        embed = self.bot.ui_manager.log_embed(
                            "Whisper Saved",
                            f"Whisper thread history saved by {interaction.user.mention}",
                            interaction.user
                        )
                        embed.add_field(name="Thread", value=interaction.channel.mention)
                        await log_channel.send(embed=embed)

            except Exception as e:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )

    class WhisperCloseView(discord.ui.View):
        def __init__(self, bot):
            super().__init__(timeout=None)  # Persistent button
            self.bot = bot

        @discord.ui.button(label="Close Whisper", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_whisper")
        async def close_whisper(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                # Verify this is a thread and the user can close it
                if not isinstance(interaction.channel, discord.Thread):
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.error_embed(
                            "Error",
                            "This command can only be used in a whisper thread"
                        ),
                        ephemeral=True
                    )
                    return

                # Get whisper data
                whispers = await self.bot.db_manager.get_active_whispers(interaction.guild_id)
                whisper = next((w for w in whispers if int(w['thread_id']) == interaction.channel.id), None)

                if not whisper:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.error_embed(
                            "Error",
                            "This is not an active whisper thread"
                        ),
                        ephemeral=True
                    )
                    return

                # Check if user can close the thread
                if str(interaction.user.id) != whisper['user_id'] and not interaction.user.guild_permissions.manage_threads:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.error_embed(
                            "Unauthorized",
                            "You cannot close this whisper thread"
                        ),
                        ephemeral=True
                    )
                    return

                # Show confirmation dialog
                confirmed = await self.bot.ui_manager.confirm_action(
                    interaction,
                    "Close Whisper",
                    "Are you sure you want to close this whisper thread?",
                    confirm_label="Close",
                    cancel_label="Cancel",
                    ephemeral=True
                )

                if not confirmed:
                    return

                await interaction.channel.send(
                    embed=self.bot.ui_manager.warning_embed(
                        "Thread Closing",
                        f"Thread manually closed by {interaction.user.mention}"
                    )
                )

                # Archive and lock the thread
                await interaction.channel.edit(archived=True, locked=True)

                # Mark as closed in DB
                await self.bot.db_manager.close_whisper(interaction.guild_id, str(interaction.channel.id))

                # Send staff controls panel
                embed = self.bot.ui_manager.info_embed(
                    "Support Team Whisper Controls",
                    "Use these controls to manage the closed whisper thread:"
                )
                controls_view = self.bot.ui_manager.WhisperControlsView(self.bot)
                await interaction.channel.send(embed=embed, view=controls_view)

                # Log whisper closure if logging is enabled
                log_config = await self.bot.db_manager.get_logging_config(interaction.guild_id)
                if log_config.get('logging_enabled', False) and log_config.get('log_channel'):
                    log_channel = interaction.guild.get_channel(int(log_config['log_channel']))
                    if log_channel:
                        embed = self.bot.ui_manager.log_embed(
                            "Whisper Closed",
                            f"Whisper thread closed by {interaction.user.mention}",
                            interaction.user
                        )
                        embed.add_field(name="Thread", value=interaction.channel.mention)
                        await log_channel.send(embed=embed)

            except Exception as e:
                try:
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.error_embed("Error", str(e)),
                        ephemeral=True
                    )
                except:
                    pass