import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import datetime, timedelta
import asyncio

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._whisper_checks = {}
        self._close_tasks = {}

    @app_commands.command(name="whisper")
    @app_commands.describe(
        action="The action to perform with the whisper system",
        message="The initial message for the whisper (required for create)",
        anonymous="Whether to make the whisper anonymous (staff can still see who sent it)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="close", value="close"),
        app_commands.Choice(name="delete", value="delete")
    ])
    async def whisper(
        self, 
        interaction: discord.Interaction, 
        action: Literal["create", "close", "delete"],
        message: Optional[str] = None,
        anonymous: bool = False
    ):
        """Manage whisper threads for private communication with staff"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.", 
                ephemeral=True
            )

        if action == "create":
            await self._handle_whisper_create(interaction, message, anonymous)
        elif action == "close":
            await self._handle_whisper_close(interaction)
        elif action == "delete":
            await self._handle_whisper_delete(interaction)

    async def _handle_whisper_create(
        self, 
        interaction: discord.Interaction, 
        message: Optional[str],
        anonymous: bool
    ):
        """Handle whisper creation"""
        if not message:
            return await interaction.response.send_message(
                "⚠️ You must provide a message when creating a whisper.",
                ephemeral=True
            )

        try:
            # Check if user already has an active whisper
            active_whispers = await self.bot.db_manager.get_user_active_whispers(
                interaction.guild_id,
                interaction.user.id
            )
            
            if active_whispers:
                return await interaction.response.send_message(
                    "⚠️ You already have an active whisper thread.",
                    ephemeral=True
                )

            # Create the thread
            thread = await interaction.channel.create_thread(
                name=f"whisper-{interaction.user.name}",
                type=discord.ChannelType.private_thread,
                reason="Whisper thread creation"
            )

            # Store in database
            await self.bot.db_manager.create_whisper(
                interaction.guild_id,
                interaction.user.id,
                thread.id
            )

            # Set up initial permissions and send first message
            embed = discord.Embed(
                title="New Whisper Thread",
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"From: {'Anonymous' if anonymous else interaction.user}")

            await thread.send(embed=embed)
            
            # Set up auto-close task
            self._setup_auto_close(thread.id)

            await interaction.response.send_message(
                f"✅ Created whisper thread {thread.mention}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create private threads.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    async def _handle_whisper_close(self, interaction: discord.Interaction):
        """Handle whisper closure"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                return await interaction.response.send_message(
                    "⚠️ This command can only be used in a whisper thread.",
                    ephemeral=True
                )

            whisper = await self.bot.db_manager.get_whisper(interaction.channel.id)
            if not whisper:
                return await interaction.response.send_message(
                    "⚠️ This is not a whisper thread.",
                    ephemeral=True
                )

            if whisper["user_id"] != interaction.user.id and not interaction.user.guild_permissions.manage_threads:
                return await interaction.response.send_message(
                    "❌ You don't have permission to close this whisper.",
                    ephemeral=True
                )

            await self.bot.db_manager.close_whisper(interaction.channel.id)
            await interaction.channel.edit(archived=True, locked=True)
            
            # Cancel auto-close task if it exists
            if interaction.channel.id in self._close_tasks:
                self._close_tasks[interaction.channel.id].cancel()
                del self._close_tasks[interaction.channel.id]

            await interaction.response.send_message(
                "✅ Whisper thread closed.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    async def _handle_whisper_delete(self, interaction: discord.Interaction):
        """Handle whisper deletion"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                return await interaction.response.send_message(
                    "⚠️ This command can only be used in a whisper thread.",
                    ephemeral=True
                )

            whisper = await self.bot.db_manager.get_whisper(interaction.channel.id)
            if not whisper:
                return await interaction.response.send_message(
                    "⚠️ This is not a whisper thread.",
                    ephemeral=True
                )

            if not interaction.user.guild_permissions.manage_threads:
                return await interaction.response.send_message(
                    "❌ You don't have permission to delete whispers.",
                    ephemeral=True
                )

            if not whisper.get("closed_at"):
                return await interaction.response.send_message(
                    "⚠️ Please close the whisper before deleting it.",
                    ephemeral=True
                )

            await self.bot.db_manager.delete_whisper(interaction.channel.id)
            await interaction.channel.delete()

            await interaction.response.send_message(
                "✅ Whisper thread deleted.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    def _setup_auto_close(self, thread_id: int):
        """Set up auto-close task for a whisper thread"""
        if thread_id in self._close_tasks:
            self._close_tasks[thread_id].cancel()

        async def auto_close_task():
            try:
                await asyncio.sleep(24 * 3600)  # 24 hours
                thread = self.bot.get_channel(thread_id)
                if thread and not thread.archived:
                    await self.bot.db_manager.close_whisper(thread_id)
                    await thread.edit(archived=True, locked=True)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"Error in auto-close task: {e}")
            finally:
                if thread_id in self._close_tasks:
                    del self._close_tasks[thread_id]

        task = asyncio.create_task(auto_close_task())
        self._close_tasks[thread_id] = task

    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        for task in self._close_tasks.values():
            task.cancel()
        self._close_tasks.clear()

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))