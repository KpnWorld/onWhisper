import discord
from discord.ext import commands
from discord import Embed
from typing import List, Dict, Any, Optional
from datetime import datetime

class CommandMultiSelectView(discord.ui.View):
    def __init__(self, options: List[Dict[str, Any]], placeholder: str, min_values: int = 1, max_values: int = 1):
        super().__init__(timeout=60)
        self.value = None

        # Create select menu
        select = discord.ui.Select(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=[discord.SelectOption(**opt) for opt in options]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle selection"""
        self.value = interaction.data['values']
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        """Handle timeout"""
        self.value = None
        self.stop()

class UIManager:
    """Manages UI components and embeds"""

    def __init__(self):
        self.colors = {
            'success': 0x57F287,  # Green
            'error': 0xED4245,    # Red
            'warning': 0xFEE75C,  # Yellow
            'info': 0x5865F2,     # Blue
            'mod': 0xEB459E       # Pink
        }

    def success_embed(self, title: str, description: str) -> discord.Embed:
        """Create a success embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=self.colors['success']
        )

    def error_embed(self, title: str, description: str) -> discord.Embed:
        """Create an error embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=self.colors['error']
        )

    def warning_embed(self, title: str, description: str) -> discord.Embed:
        """Create a warning embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=self.colors['warning']
        )

    def info_embed(self, title: str, description: str) -> discord.Embed:
        """Create an info embed"""
        return discord.Embed(
            title=title,
            description=description,
            color=self.colors['info']
        )

    def mod_embed(self, title: str, description: str, author: Optional[discord.Member] = None) -> discord.Embed:
        """Create a moderation action embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=self.colors['mod'],
            timestamp=discord.utils.utcnow()
        )
        if author:
            embed.set_author(
                name=author.display_name,
                icon_url=author.display_avatar.url
            )
        return embed

    def whisper_embed(self, title: str, description: str, user: discord.Member, anonymous: bool = False) -> discord.Embed:
        """Create a whisper message embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=self.colors['info'],
            timestamp=discord.utils.utcnow()
        )
        if not anonymous:
            embed.set_author(
                name=user.display_name,
                icon_url=user.display_avatar.url
            )
        else:
            embed.set_author(name="Anonymous User")
        return embed

    def level_up_embed(self, user: discord.Member, new_level: int, role: Optional[discord.Role] = None) -> discord.Embed:
        """Create a level up announcement embed"""
        description = f"🎉 {user.mention} has reached level {new_level}!"
        if role:
            description += f"\nYou earned the {role.mention} role!"

        embed = discord.Embed(
            title="Level Up!",
            description=description,
            color=self.colors['success']
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed

    async def paginate(
        self,
        interaction: discord.Interaction,
        pages: List[discord.Embed],
        timeout: int = 60,
        ephemeral: bool = False
    ):
        """Create a paginated message with navigation buttons"""
        if not pages:
            raise ValueError("No pages to paginate")

        # Add page numbers to embeds
        for i, embed in enumerate(pages, 1):
            embed.set_footer(text=f"Page {i}/{len(pages)}")

        # Create view with navigation buttons
        view = PaginationView(pages, timeout)
        
        # Send initial message
        await interaction.response.send_message(
            embed=pages[0],
            view=view,
            ephemeral=ephemeral
        )

    async def confirm_action(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        timeout: int = 30
    ) -> bool:
        """Create a confirmation message with buttons"""
        embed = self.warning_embed(title, description)
        view = ConfirmView(
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            timeout=timeout
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
        
        # Wait for interaction
        await view.wait()
        return view.value

    async def create_select_menu(
        self,
        interaction: discord.Interaction,
        options: List[Dict[str, Any]],
        placeholder: str = "Make a selection",
        min_values: int = 1,
        max_values: int = 1,
        ephemeral: bool = True
    ) -> Optional[List[str]]:
        """Create a selection menu"""
        view = CommandMultiSelectView(
            options=options,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values
        )

        await interaction.response.send_message(
            embed=self.info_embed("Selection", "Please make your selection:"),
            view=view,
            ephemeral=ephemeral
        )

        # Wait for interaction
        await view.wait()
        return view.value

    async def create_help_menu(
        self,
        interaction: discord.Interaction,
        bot: commands.Bot
    ):
        """Create a help menu"""
        view = HelpMenuView(bot, self)
        await interaction.response.send_message(
            embed=self.info_embed("Help Menu", "Select a category to view commands."),
            view=view,
            ephemeral=True
        )

class PaginationView(discord.ui.View):
    def __init__(self, pages: List[discord.Embed], timeout: int):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page])

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page])

    async def on_timeout(self):
        """Handle timeout"""
        self.disable_all_items()

class ConfirmView(discord.ui.View):
    def __init__(self, confirm_label: str, cancel_label: str, timeout: int):
        super().__init__(timeout=timeout)
        self.value = None
        self.confirm_button.label = confirm_label
        self.cancel_button.label = cancel_label

    @discord.ui.button(style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the action"""
        self.value = True
        self.stop()
        await interaction.response.edit_message(
            embed=interaction.message.embeds[0],
            view=None
        )

    @discord.ui.button(style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the action"""
        self.value = False
        self.stop()
        await interaction.response.edit_message(
            embed=interaction.message.embeds[0],
            view=None
        )

    async def on_timeout(self):
        """Handle timeout"""
        self.value = False
        self.stop()
        for child in self.children:
            child.disabled = True

class HelpMenuView(discord.ui.View):
    def __init__(self, bot, ui_manager):
        super().__init__(timeout=60)
        self.bot = bot
        self.ui_manager = ui_manager
        self.message = None
        
        # Create select menu with command categories
        select = discord.ui.Select(
            placeholder="Select a category",
            options=[
                discord.SelectOption(
                    label="Whisper",
                    description="Anonymous messaging system",
                    emoji="📝",
                    value="whisper"
                ),
                discord.SelectOption(
                    label="Leveling",
                    description="XP and level management",
                    emoji="⭐",
                    value="leveling"
                ),
                discord.SelectOption(
                    label="Moderation",
                    description="Server moderation commands",
                    emoji="🛡️",
                    value="moderation"
                ),
                discord.SelectOption(
                    label="Configuration",
                    description="Bot settings and setup",
                    emoji="⚙️",
                    value="config"
                ),
                discord.SelectOption(
                    label="Roles",
                    description="Role management commands",
                    emoji="👑",
                    value="roles"
                ),
                discord.SelectOption(
                    label="Information",
                    description="Server and user info",
                    emoji="ℹ️",
                    value="info"
                )
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        category = interaction.data['values'][0]
        
        # Get commands for selected category
        commands = [cmd for cmd in self.bot.tree.get_commands() 
                   if cmd.extras.get('category', '').lower() == category]
        
        if not commands:
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "No Commands",
                    "No commands found in this category."
                ),
                ephemeral=True
            )
            return

        # Create embed with command list
        embed = discord.Embed(
            title=f"{category.title()} Commands",
            color=discord.Color.blue()
        )

        for cmd in sorted(commands, key=lambda x: x.name):
            value = cmd.description or "No description available"
            if cmd.parameters:
                params = [f"[{p.name}]" if p.required else f"({p.name})" 
                         for p in cmd.parameters]
                value = f"Usage: /{cmd.name} {' '.join(params)}\n{value}"
            embed.add_field(
                name=f"/{cmd.name}",
                value=value,
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Handle timeout by disabling the select menu"""
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)