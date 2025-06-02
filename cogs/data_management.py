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
            if limit is None or limit <= 0 or limit > 100:
                return await interaction.followup.send("❌ Limit must be between 1 and 100!", ephemeral=True)

            if not interaction.guild:
                return await interaction.followup.send("❌ This command can only be used in a guild!", ephemeral=True)

            if table == "feature_settings":
                data = await self.bot.db.get_feature_settings(interaction.guild.id, "*")
            elif table == "guild_settings":
                data = await self.bot.db.get_guild_settings(interaction.guild.id)
            elif table == "xp":
                data = await self.bot.db.get_leaderboard_page(interaction.guild.id, limit=limit)
            elif table == "logs":
                data = await self.bot.db.get_logs_filtered(interaction.guild.id, since_days=None)[:limit]
            elif table == "mod_actions":
                data = await self.bot.db.get_mod_actions_page(interaction.guild.id, limit=limit, offset=0)
            elif table == "whispers":
                data = await self.bot.db.get_all_whispers(interaction.guild.id)[:limit]
            elif table == "autoroles":
                roles = await self.bot.db.get_autoroles(interaction.guild.id)
                data = [{"role_id": role_id} for role_id in roles]
            else:
                return await interaction.followup.send("❌ Invalid table selected!", ephemeral=True)

            if not data:
                return await interaction.followup.send(f"No data found in {table}!", ephemeral=True)

            # Create embeds from data
            embeds = []
            for i in range(0, len(data), 5):
                embed = discord.Embed(
                    title=f"📊 {table.replace('_', ' ').title()} Data",
                    color=discord.Color.blue()
                )

                chunk = data[i:i+5]
                for idx, entry in enumerate(chunk, start=i+1):
                    if raw:
                        field_value = f"```json\n{json.dumps(entry, indent=2)}```"
                    else:
                        field_value = "\n".join(f"{k}: {v}" for k, v in entry.items() if k != "guild_id")
                    
                    embed.add_field(
                        name=f"Entry {idx}",
                        value=f"```{field_value}```",
                        inline=False
                    )

                embed.set_footer(text=f"Page {i//5 + 1}/{(len(data)-1)//5 + 1}")
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

        if target == "user" and not user:
            return await interaction.response.send_message("❌ Please specify a user to delete data for!", ephemeral=True)

        # Ask for confirmation
        confirm_view = discord.ui.View(timeout=60)
        confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.gray)

        async def confirm_callback(interaction: discord.Interaction):
            try:
                if not interaction.guild:
                    return await interaction.response.edit_message(
                        content="❌ This command can only be used in a guild.",
                        view=None
                    )

                if target == "guild":
                    await self.bot.db.delete_guild_data(interaction.guild.id)
                elif target == "user" and user:
                    await self.bot.db.delete_user_data(interaction.guild.id, user.id)
                elif target == "logs":
                    await self.bot.db.purge_old_logs(0)  # 0 days means delete all
                elif target == "xp":
                    await self.bot.db.delete_all_xp(interaction.guild.id)
                elif target == "whispers":
                    await self.bot.db.delete_all_whispers(interaction.guild.id)

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
