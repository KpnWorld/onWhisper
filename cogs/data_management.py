import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import json

class DataManagementCog(commands.Cog):
    """Cog for managing guild data and viewing database information"""
    
    def __init__(self, bot):
        self.bot = bot

    async def _check_is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.guild_permissions.administrator

    @app_commands.command(name="viewdata")
    @app_commands.describe(
        table="Table to view data from",
        limit="Number of entries to show (default: 10)",
        raw="Show raw data format"
    )
    @app_commands.choices(table=[
        app_commands.Choice(name="Guild Settings", value="guild_settings"),
        app_commands.Choice(name="Feature Settings", value="feature_settings"),
        app_commands.Choice(name="XP/Levels", value="xp"),
        app_commands.Choice(name="Logs", value="logs"),
        app_commands.Choice(name="Mod Actions", value="mod_actions"),
        app_commands.Choice(name="Whispers", value="whispers"),
        app_commands.Choice(name="Autoroles", value="autoroles"),
        app_commands.Choice(name="Reaction Roles", value="reaction_roles")
    ])
    async def viewdata(self, interaction: discord.Interaction, table: str, limit: Optional[int] = 10, raw: bool = False):
        """View data stored in the database"""
        if not await self._check_is_admin(interaction):
            return await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            # Validate limit
            if limit is None or limit <= 0 or limit > 100:
                return await interaction.followup.send("❌ Limit must be between 1 and 100!", ephemeral=True)

            # Safe table name list with friendly names
            table_info = {
                "guild_settings": {"name": "Guild Settings", "timestamp_fields": []},
                "feature_settings": {"name": "Feature Settings", "timestamp_fields": []},
                "xp": {"name": "XP/Levels", "timestamp_fields": ["last_message_ts"]},
                "logs": {"name": "Logs", "timestamp_fields": ["timestamp"]},
                "mod_actions": {"name": "Mod Actions", "timestamp_fields": ["timestamp"]},
                "whispers": {"name": "Whispers", "timestamp_fields": ["created_at", "closed_at"]},
                "autoroles": {"name": "Auto Roles", "timestamp_fields": []},
                "reaction_roles": {"name": "Reaction Roles", "timestamp_fields": []}
            }
            
            if table not in table_info:
                return await interaction.followup.send("❌ Invalid table selected!", ephemeral=True)

            # Check if interaction is in a guild
            if not interaction.guild:
                return await interaction.followup.send("This command can only be used in a guild!", ephemeral=True)

            # Get table data with guild filter
            query = f"SELECT * FROM {table} WHERE guild_id = ? ORDER BY "
            
            # Add appropriate ordering
            if "timestamp" in table_info[table]["timestamp_fields"]:
                query += "timestamp DESC"
            elif "created_at" in table_info[table]["timestamp_fields"]:
                query += "created_at DESC"
            else:
                query += "rowid DESC"  # Default ordering
                
            query += " LIMIT ?"

            async with self.bot.db.connection.execute(query, (interaction.guild.id, limit)) as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    return await interaction.followup.send(f"No data found in {table}!", ephemeral=True)

                # Create pages of embeds
                embeds = []
                for i in range(0, len(rows), 5):
                    embed = discord.Embed(
                        title=f"📊 {table_info[table]['name']} Data",
                        color=discord.Color.blue()
                    )

                    chunk = rows[i:i+5]
                    for row in chunk:
                        row_dict = dict(zip([col[0] for col in cursor.description], row))
                        
                        # Format field value based on data type and raw flag
                        if raw:
                            field_value = f"```json\n{json.dumps(row_dict, indent=2)}```"
                        else:
                            # Format timestamps
                            for ts_field in table_info[table]["timestamp_fields"]:
                                if ts_field in row_dict and row_dict[ts_field]:
                                    if isinstance(row_dict[ts_field], (int, float)):
                                        row_dict[ts_field] = f"<t:{int(row_dict[ts_field])}:R>"
                            
                            # Format special fields
                            if table == "feature_settings":
                                field_value = (
                                    f"Feature: {row_dict['feature']}\n"
                                    f"Enabled: {row_dict['enabled']}\n"
                                    f"Options: ```json\n{row_dict['options_json']}```"
                                )
                            else:
                                # Remove guild_id from display
                                row_dict.pop('guild_id', None)
                                field_value = "\n".join(f"{k}: {v}" for k, v in row_dict.items())

                        embed.add_field(
                            name=f"Entry {i + chunk.index(row) + 1}",
                            value=f"```{field_value}```",
                            inline=False
                        )

                    embed.set_footer(text=f"Page {i//5 + 1}/{(len(rows)-1)//5 + 1}")
                    embeds.append(embed)

                # Create pagination buttons if needed
                if len(embeds) > 1:
                    class DataPaginator(discord.ui.View):
                        def __init__(self):
                            super().__init__(timeout=180)
                            self.current_page = 0

                        @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
                        async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
                            self.current_page = max(0, self.current_page - 1)
                            await interaction.response.edit_message(embed=embeds[self.current_page])

                        @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
                        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                            self.current_page = min(len(embeds) - 1, self.current_page + 1)
                            await interaction.response.edit_message(embed=embeds[self.current_page])

                    await interaction.followup.send(embed=embeds[0], view=DataPaginator())
                else:
                    await interaction.followup.send(embed=embeds[0])

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="deletedata")
    @app_commands.describe(
        target="What data to delete",
        user="User to delete data for (if applicable)"
    )
    @app_commands.choices(target=[
        app_commands.Choice(name="All Guild Data", value="guild"),
        app_commands.Choice(name="User Data", value="user"),
        app_commands.Choice(name="Logs", value="logs"),
        app_commands.Choice(name="XP Data", value="xp"),
        app_commands.Choice(name="Whispers", value="whispers")
    ])
    async def deletedata(self, interaction: discord.Interaction, target: str, user: Optional[discord.User] = None):
        """Delete data from the database"""
        if not await self._check_is_admin(interaction):
            return await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)

        if target == "user":
            if not user:
                return await interaction.response.send_message("❌ Please specify a user to delete data for!", ephemeral=True)

        # Ask for confirmation
        confirm_view = discord.ui.View(timeout=60)
        confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.gray)

        async def confirm_callback(interaction: discord.Interaction):
            try:
                if not interaction.guild:
                    return await interaction.response.edit_message(content="❌ This command can only be used in a guild.", view=None)
                    
                guild_id = interaction.guild.id
                if target == "guild":
                    await self.bot.db.delete_guild_data(guild_id)
                elif target == "user" and user:
                    await self.bot.db.delete_user_data(guild_id, user.id)
                elif target == "user" and user:
                    await self.bot.db.delete_user_data(guild_id, user.id)
                elif target == "xp":
                    async with self.bot.db.transaction() as tr:
                        await tr.execute("DELETE FROM xp WHERE guild_id = ?", (guild_id,))
                elif target == "whispers":
                    async with self.bot.db.transaction() as tr:
                        await tr.execute("DELETE FROM whispers WHERE guild_id = ?", (guild_id,))

                await interaction.response.edit_message(
                    content="✅ Data has been deleted successfully.",
                    view=None
                )
            except Exception as e:
                await interaction.response.edit_message(
                    content=f"❌ An error occurred: {str(e)}",
                    view=None
                )

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(
                content="❌ Operation cancelled.",
                view=None
            )

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        # Show confirmation message
        target_desc = {
            "guild": "ALL guild data",
            "user": f"data for user {user.mention if user else 'Unknown'}",
            "logs": "all logs",
            "xp": "all XP data",
            "whispers": "all whisper data"
        }

        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete {target_desc[target]}? This cannot be undone!",
            view=confirm_view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(DataManagementCog(bot))
