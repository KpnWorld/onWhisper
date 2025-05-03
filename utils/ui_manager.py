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
            'mod': 0xF1C40F         # Yellow for moderation
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

            @discord.ui.button(label=confirm_label, style=discord.ButtonStyle.green)
            async def confirm(self, button: discord.ui.Button, button_interaction: discord.Interaction):
                self.value = True
                for item in self.children:
                    item.disabled = True
                try:
                    await button_interaction.response.edit_message(view=self)
                except discord.InteractionResponded:
                    await button_interaction.edit_original_response(view=self)
                self.stop()

            @discord.ui.button(label=cancel_label, style=discord.ButtonStyle.grey)
            async def cancel(self, button: discord.ui.Button, button_interaction: discord.Interaction):
                self.value = False
                for item in self.children:
                    item.disabled = True
                try:
                    await button_interaction.response.edit_message(view=self)
                except discord.InteractionResponded:
                    await button_interaction.edit_original_response(view=self)
                self.stop()

            async def on_timeout(self):
                self.value = False
                for item in self.children:
                    item.disabled = True
                try:
                    await interaction.edit_original_response(view=self)
                except:
                    pass

        view = ConfirmView()
        embed = self.info_embed(
            title=title,
            description=description
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
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
                        label="Tickets",
                        description="Ticket system commands",
                        value="tickets",
                        emoji="🎫"
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
                    if category == "leveling" and cmd.name.startswith(("xp_", "level_", "config_xp_")):
                        commands.append(cmd)
                    elif category == "moderation" and cmd.name.startswith(("warn", "kick", "ban", "timeout", "mute", "purge", "clear", "lockdown")):
                        commands.append(cmd)
                    elif category == "config" and cmd.name.startswith("config_"):
                        commands.append(cmd)
                    elif category == "roles" and cmd.name.startswith(("roles_", "role_")):
                        commands.append(cmd)
                    elif category == "tickets" and cmd.name.startswith(("whisper_", "ticket_")):
                        commands.append(cmd)
                    elif category == "info" and cmd.name.startswith("info_"):
                        commands.append(cmd)

                # Create embed for category
                embed = self.ui.info_embed(
                    f"{select_menu.values[0].title()} Commands",
                    "Use `/help <command>` for detailed information about a specific command."
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