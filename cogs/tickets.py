import discord 
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

class CloseButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Get ticket thread
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.followup.send("This command can only be used in ticket threads!", ephemeral=True)
            return
            
        # Close the thread
        try:
            await thread.edit(archived=True, locked=True)
            await interaction.followup.send("🔒 Ticket closed!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to close this ticket!", ephemeral=True)

class Tickets(commands.Cog):
    """Ticket management system using threads"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())
        self.auto_close_task = self.bot.loop.create_task(self.check_inactive_tickets())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Tickets cog")
                return
                
            self._ready.set()
            print("✅ Tickets cog ready")
            
        except Exception as e:
            print(f"❌ Error setting up Tickets cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    class TicketModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title="Create Support Ticket")
            self.add_item(discord.ui.TextInput(
                label="Issue Summary",
                placeholder="Brief description of your issue",
                style=discord.TextStyle.short,
                required=True,
                max_length=100
            ))
            self.add_item(discord.ui.TextInput(
                label="Details",
                placeholder="Please provide more details about your issue",
                style=discord.TextStyle.paragraph,
                required=False,
                max_length=1000
            ))

        async def on_submit(self, interaction: discord.Interaction):
            self.interaction = interaction
            self.summary = self.children[0].value
            self.details = self.children[1].value
            await interaction.response.defer()

    async def check_inactive_tickets(self):
        """Check and close inactive tickets"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                for guild in self.bot.guilds:
                    # Get ticket data
                    guild_data = await self.db_manager.get_guild_data(guild.id)
                    ticket_settings = guild_data.get('tickets', {}).get('settings', {})
                    
                    if not ticket_settings.get('auto_close', False):
                        continue
                        
                    inactive_hours = ticket_settings.get('close_hours', 24)
                    cutoff = datetime.utcnow() - timedelta(hours=inactive_hours)
                    
                    # Check each thread in forum channels
                    for channel in guild.channels:
                        if isinstance(channel, discord.ForumChannel):
                            async for thread in channel.archived_threads():
                                if thread.name.startswith('ticket-'):
                                    last_message = await thread.fetch_message(thread.last_message_id)
                                    if last_message and last_message.created_at < cutoff:
                                        try:
                                            await thread.edit(archived=True, locked=True)
                                            await thread.send("🔒 Ticket auto-closed due to inactivity")
                                        except:
                                            continue
                                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error checking inactive tickets: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    @commands.hybrid_command(description="Create a support ticket")
    async def ticket(self, ctx: commands.Context):
        """Create a support ticket thread"""
        try:
            # Show modal for ticket details
            modal = self.TicketModal()
            await ctx.interaction.response.send_modal(modal)
            await modal.wait()
            
            # Get ticket reason from modal
            reason = f"{modal.summary}\n\n{modal.details}" if modal.details else modal.summary

            # Find or create forum channel for tickets
            forum_channel = None
            for channel in ctx.guild.channels:
                if isinstance(channel, discord.ForumChannel) and channel.name == "tickets":
                    forum_channel = channel
                    break
                    
            if not forum_channel:
                # Create forum channel
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_threads=True)
                }
                forum_channel = await ctx.guild.create_forum_channel(
                    name="tickets",
                    overwrites=overwrites,
                    topic="Support Tickets"
                )

            # Create the ticket thread
            thread = await forum_channel.create_thread(
                name=f"ticket-{ctx.author.name}",
                content=reason,
                auto_archive_duration=10080  # 7 days
            )

            # Add staff and author to thread
            await thread.add_user(ctx.author)
            for member in ctx.guild.members:
                if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
                    try:
                        await thread.add_user(member)
                    except:
                        continue

            # Send initial message
            embed = self.ui.user_embed(
                "Ticket Created",
                f"**User:** {ctx.author.mention}\n**Reason:** {reason}\n\nStaff will assist you shortly."
            )
            view = CloseButton()
            await thread.send(embed=embed, view=view)

            # Send confirmation
            confirm_embed = self.ui.user_embed(
                "Ticket Created",
                f"Your ticket has been created: {thread.mention}"
            )
            await modal.interaction.followup.send(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            error_embed = self.ui.error_embed(
                "Error Creating Ticket",
                str(e)
            )
            try:
                await modal.interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))