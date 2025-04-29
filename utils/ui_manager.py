import discord
from datetime import datetime

class UIManager:
    def __init__(self, bot):
        self.bot = bot
        self.colors = {
            "info": discord.Color.blurple(),
            "success": discord.Color.green(),
            "error": discord.Color.red(),
            "admin": discord.Color.red(),
            "mod": discord.Color.orange(),
            "user": discord.Color.blurple(),
            "system": discord.Color.dark_grey()
        }
        
        self.command_types = {
            "admin": "Administrative",
            "mod": "Moderation", 
            "user": "User",
            "system": "System"
        }

    def make_embed(
        self,
        title: str = None,
        description: str = None,
        *,
        color: discord.Color = None,
        fields: list = None,
        footer_text: str = None,
        timestamp: bool = True,
        codeblock: bool = False,
        command_type: str = "user"
    ) -> discord.Embed:
        """Creates a clean, reusable embed."""
        # Normalize command type and get color
        cmd_type = command_type.lower()
        embed_color = color or self.colors.get(cmd_type, self.colors["info"])
        
        embed = discord.Embed(
            title=title,
            description=f"```{description}```" if codeblock and description else description,
            color=embed_color,
            timestamp=datetime.utcnow() if timestamp else None
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        # Set footer with command type
        footer = footer_text or "onWhisper • Powered by KpnWorld LLC"
        if cmd_type in self.command_types:
            footer = f"{self.command_types[cmd_type]} Command • {footer}"
            
        embed.set_footer(
            text=footer,
            icon_url=getattr(self.bot.user.avatar, 'url', None)
        )

        return embed

    def success_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a green success embed."""
        return self.make_embed(
            title=title,
            description=description,
            color=self.colors["success"]
        )

    def error_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a red error embed."""
        return self.make_embed(
            title=title,
            description=description,
            color=self.colors["error"]
        )

    def info_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a blurple info embed."""
        return self.make_embed(
            title=title,
            description=description,
            command_type="user"
        )

    def admin_embed(self, title=None, description=None, **kwargs):
        """Shortcut for an administrative command embed."""
        kwargs.pop('command_type', None)  # Remove command_type if present
        return self.make_embed(
            title=title,
            description=description,
            command_type="admin",
            **kwargs
        )

    def mod_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a moderation command embed."""
        return self.make_embed(
            title=title,
            description=description,
            command_type="mod",
            **kwargs
        )

    def user_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a user command embed."""
        return self.make_embed(
            title=title,
            description=description,
            command_type="user",
            **kwargs
        )

    def system_embed(self, title=None, description=None, **kwargs):
        """Shortcut for a system message embed."""
        return self.make_embed(
            title=title,
            description=description,
            command_type="system",
            **kwargs
        )

    async def send_embed(self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = False):
        """Send a single embed easily."""
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    class Paginator(discord.ui.View):
        def __init__(
            self,
            pages: list[discord.Embed],
            *,
            timeout: int = 180,
            show_page_indicator: bool = True
        ):
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
                await button_interaction.response.edit_message(view=self)
                self.stop()

            @discord.ui.button(label=cancel_label, style=discord.ButtonStyle.grey)
            async def cancel(self, button: discord.ui.Button, button_interaction: discord.Interaction):
                self.value = False
                for item in self.children:
                    item.disabled = True
                await button_interaction.response.edit_message(view=self)
                self.stop()

            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True
                try:
                    await interaction.edit_original_response(view=self)
                except:
                    pass

        view = ConfirmView()
        embed = self.make_embed(
            title=title,
            description=description,
            color=self.colors["info"]
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
                options=[
                    discord.SelectOption(
                        label=option.get("label", ""),
                        description=option.get("description", ""),
                        value=option.get("value", ""),
                        emoji=option.get("emoji", None)
                    ) for option in options
                ]
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