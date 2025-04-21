import discord
from typing import Optional, List, Dict, Any
from datetime import datetime


class UIManager:
    def __init__(self, bot):
        self.bot = bot
        self.color_success = 0x2ecc71
        self.color_error = 0xff0000
        self.color_info = 0x3498db
        self.color_warning = 0xf1c40f
        self._last_interaction = {}

    # ------------------- EMBED BUILDING -------------------

    def _get_footer(self, command_name: Optional[str], is_admin: bool, context: str) -> str:
        if not context:
            context = "Success"

        type_label = "Administrative Command" if is_admin else "User Command"
        context_label = context.title()

        if command_name:
            context_label = command_name

        return f"{type_label} • {context_label}"

    def create_embed(self,
                     title: str,
                     description: str,
                     color: int,
                     *,
                     fields: Optional[List[Dict[str, Any]]] = None,
                     footer: Optional[str] = None,
                     thumbnail_url: Optional[str] = None) -> discord.Embed:

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

        if footer:
            embed.set_footer(text=footer)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        return embed

    def success_embed(self, title: str, description: str,
                      command_name: Optional[str] = None,
                      is_admin: bool = False) -> discord.Embed:
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_success,
            footer=self._get_footer(command_name, is_admin, "Success")
        )

    def error_embed(self, title: str, description: str,
                    command_name: Optional[str] = None,
                    is_admin: bool = False) -> discord.Embed:
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_error,
            footer=self._get_footer(command_name, is_admin, "Error")
        )

    def info_embed(self, title: str, description: str,
                   *,
                   fields: Optional[List[Dict[str, Any]]] = None,
                   thumbnail_url: Optional[str] = None,
                   command_name: Optional[str] = None,
                   is_admin: bool = False) -> discord.Embed:
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_info,
            fields=fields,
            thumbnail_url=thumbnail_url,
            footer=self._get_footer(command_name, is_admin, "Info")
        )

    def warning_embed(self, title: str, description: str,
                      command_name: Optional[str] = None,
                      is_admin: bool = False) -> discord.Embed:
        return self.create_embed(
            title=title,
            description=description,
            color=self.color_warning,
            footer=self._get_footer(command_name, is_admin, "Warning")
        )

    # ------------------- MESSAGE SENDING -------------------

    async def send_embed(self,
                         interaction: discord.Interaction,
                         embed: discord.Embed,
                         *,
                         ephemeral: bool = False):
        """Centralized embed sending"""
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    async def send_paginated_embeds(self,
                                    interaction: discord.Interaction,
                                    embeds: List[discord.Embed],
                                    ephemeral: bool = False):
        """Paginated embeds with navigation buttons"""
        if not embeds:
            await self.send_embed(interaction, self.error_embed("Error", "No results to display."))
            return

        current_page = 0
        view = discord.ui.View(timeout=300)

        async def update():
            await message.edit(embed=embeds[current_page], view=view)

        @discord.ui.button(label="◀", style=discord.ButtonStyle.blurple)
        async def previous(button: discord.ui.Button, i: discord.Interaction):
            nonlocal current_page
            if current_page > 0:
                current_page -= 1
                await update()
            await i.response.defer()

        @discord.ui.button(label="▶", style=discord.ButtonStyle.blurple)
        async def next(button: discord.ui.Button, i: discord.Interaction):
            nonlocal current_page
            if current_page < len(embeds) - 1:
                current_page += 1
                await update()
            await i.response.defer()

        view.add_item(previous)
        view.add_item(next)

        await interaction.response.send_message(embed=embeds[0], view=view if len(embeds) > 1 else None, ephemeral=ephemeral)
        message = await interaction.original_response()

    # ------------------- COMPONENTS -------------------

    def create_confirm_view(self, timeout: int = 60) -> discord.ui.View:
        view = discord.ui.View(timeout=timeout)

        async def confirm_callback(interaction: discord.Interaction):
            view.value = True
            view.stop()

        async def cancel_callback(interaction: discord.Interaction):
            view.value = False
            view.stop()

        confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback

        view.add_item(confirm_button)
        view.add_item(cancel_button)
        return view

    def create_select_menu(self,
                           options: List[Dict[str, str]],
                           placeholder: str = "Select an option",
                           min_values: int = 1,
                           max_values: int = 1) -> Optional[discord.ui.Select]:
        try:
            select_options = [
                discord.SelectOption(
                    label=str(option['label'])[:100],
                    value=str(option['value'])[:100],
                    description=str(option.get('description', ''))[:100]
                ) for option in options[:25]
            ]
            return discord.ui.Select(
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                options=select_options
            )
        except Exception:
            return None

    def create_modal(self, title: str,
                     fields: List[Dict[str, Any]]) -> discord.ui.Modal:
        class CustomModal(discord.ui.Modal):
            def __init__(self, modal_title, fields_data):
                super().__init__(title=modal_title[:45])
                for field in fields_data:
                    self.add_item(
                        discord.ui.TextInput(
                            label=field['label'][:45],
                            placeholder=field.get('placeholder', '')[:100],
                            required=bool(field.get('required', True)),
                            max_length=int(field.get('max_length', 4000))
                        )
                    )

        return CustomModal(title, fields)

    # ------------------- UTILS -------------------

    def throttle_interaction(self, user_id: int,
                             command_name: str,
                             cooldown: float = 3.0) -> bool:
        current_time = datetime.now().timestamp()
        key = f"{user_id}:{command_name}"

        if key in self._last_interaction:
            if current_time - self._last_interaction[key] < cooldown:
                return True

        self._last_interaction[key] = current_time
        return False

    def clean_last_interactions(self, max_age: float = 300.0):
        current_time = datetime.now().timestamp()
        self._last_interaction = {
            k: v for k, v in self._last_interaction.items()
            if current_time - v < max_age
        }
