import discord
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self):
        self.color_success = 0x2ecc71
        self.color_error = 0xff0000
        self.color_info = 0x3498db
        self.color_warning = 0xf1c40f
        self._last_interaction = {}

    def create_embed(self, title: str, description: str, color: int,
                    fields: Optional[List[Dict[str, Any]]] = None,
                    footer_text: Optional[str] = None,
                    thumbnail_url: Optional[str] = None) -> discord.Embed:
        """Create a standardized embed with error handling"""
        try:
            embed = discord.Embed(
                title=str(title)[:256],
                description=str(description)[:4096] if description else None,
                color=color,
                timestamp=datetime.utcnow()
            )
            
            if fields:
                for field in fields:
                    name = str(field.get('name', ''))[:256]
                    value = str(field.get('value', ''))[:1024]
                    inline = bool(field.get('inline', False))
                    if name and value:
                        embed.add_field(name=name, value=value, inline=inline)
            
            if footer_text:
                embed.set_footer(text=str(footer_text)[:2048])
                
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
                
            return embed
        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            return self.error_embed(
                "Error",
                "An error occurred while creating this message.",
                "embed_creation"
            )

    def success_embed(self, title: str, description: str, 
                     command_name: Optional[str] = None) -> discord.Embed:
        """Create a success embed"""
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_success,
            footer_text=f"Command: {command_name}" if command_name else None
        )

    def error_embed(self, title: str, description: str,
                   command_name: Optional[str] = None) -> discord.Embed:
        """Create an error embed"""
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_error,
            footer_text=f"Command: {command_name}" if command_name else None
        )

    def info_embed(self, title: str, description: str,
                  fields: Optional[List[Dict[str, Any]]] = None,
                  thumbnail_url: Optional[str] = None) -> discord.Embed:
        """Create an info embed"""
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_info,
            fields=fields,
            thumbnail_url=thumbnail_url
        )

    def warning_embed(self, title: str, description: str) -> discord.Embed:
        """Create a warning embed"""
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_warning
        )

    def create_confirm_view(self, timeout: int = 60) -> discord.ui.View:
        """Create a confirmation button view"""
        view = discord.ui.View(timeout=timeout)
        
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
        async def confirm_button(button: discord.ui.Button, 
                               interaction: discord.Interaction):
            view.value = True
            view.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
        async def cancel_button(button: discord.ui.Button, 
                              interaction: discord.Interaction):
            view.value = False
            view.stop()

        view.add_item(confirm_button)
        view.add_item(cancel_button)
        return view

    def create_paginated_embed(self, entries: List[str], 
                             per_page: int = 10,
                             title: str = "Results",
                             description: str = None) -> List[discord.Embed]:
        """Create a list of paginated embeds"""
        embeds = []
        for i in range(0, len(entries), per_page):
            page_entries = entries[i:i + per_page]
            page_num = len(embeds) + 1
            total_pages = (len(entries) + per_page - 1) // per_page
            
            embed = self.create_embed(
                title=f"{title} (Page {page_num}/{total_pages})",
                description=description,
                color=self.color_info,
                fields=[{"name": f"Entry {i+j+1}", "value": entry, "inline": False}
                       for j, entry in enumerate(page_entries)]
            )
            embeds.append(embed)
        
        return embeds

    async def send_paginated_embeds(self, ctx: discord.Interaction,
                                  embeds: List[discord.Embed]) -> None:
        """Send paginated embeds with navigation buttons"""
        if not embeds:
            await ctx.response.send_message(
                embed=self.error_embed("Error", "No results to display.")
            )
            return

        current_page = 0
        view = discord.ui.View(timeout=300)

        async def update_message():
            await message.edit(embed=embeds[current_page], view=view)

        @discord.ui.button(label="◀", style=discord.ButtonStyle.blurple)
        async def previous_button(button: discord.ui.Button, 
                                interaction: discord.Interaction):
            nonlocal current_page
            if current_page > 0:
                current_page -= 1
                await update_message()
            await interaction.response.defer()

        @discord.ui.button(label="▶", style=discord.ButtonStyle.blurple)
        async def next_button(button: discord.ui.Button, 
                            interaction: discord.Interaction):
            nonlocal current_page
            if current_page < len(embeds) - 1:
                current_page += 1
                await update_message()
            await interaction.response.defer()

        view.add_item(previous_button)
        view.add_item(next_button)

        message = await ctx.response.send_message(
            embed=embeds[0],
            view=view if len(embeds) > 1 else None
        )

    def create_select_menu(self, options: List[Dict[str, str]], 
                         placeholder: str = "Select an option",
                         min_values: int = 1,
                         max_values: int = 1) -> discord.ui.Select:
        """Create a select menu component"""
        try:
            select_options = [
                discord.SelectOption(
                    label=str(option['label'])[:100],
                    value=str(option['value'])[:100],
                    description=str(option.get('description', ''))[:100]
                )
                for option in options[:25]  # Discord limits to 25 options
            ]
            
            return discord.ui.Select(
                placeholder=str(placeholder)[:100],
                min_values=min_values,
                max_values=max_values,
                options=select_options
            )
        except Exception as e:
            logger.error(f"Error creating select menu: {e}")
            return None

    def create_modal(self, title: str, 
                    fields: List[Dict[str, Any]]) -> discord.ui.Modal:
        """Create a modal dialog"""
        class CustomModal(discord.ui.Modal):
            def __init__(self, fields_data):
                super().__init__(title=str(title)[:45])
                for field in fields_data:
                    self.add_item(
                        discord.ui.TextInput(
                            label=str(field['label'])[:45],
                            placeholder=str(field.get('placeholder', ''))[:100],
                            required=bool(field.get('required', True)),
                            max_length=int(field.get('max_length', 4000))
                        )
                    )

        return CustomModal(fields)

    def throttle_interaction(self, user_id: int, 
                           command_name: str, 
                           cooldown: float = 3.0) -> bool:
        """Check if an interaction should be throttled"""
        current_time = datetime.now().timestamp()
        key = f"{user_id}:{command_name}"
        
        if key in self._last_interaction:
            if current_time - self._last_interaction[key] < cooldown:
                return True
                
        self._last_interaction[key] = current_time
        return False

    def clean_last_interactions(self, max_age: float = 300.0):
        """Clean up old interaction records"""
        current_time = datetime.now().timestamp()
        self._last_interaction = {
            k: v for k, v in self._last_interaction.items()
            if current_time - v < max_age
        }
