import discord 
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

class CloseButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Verify this is a ticket channel
            if not interaction.channel.name.startswith('ticket-'):
                await interaction.response.send_message("This is not a ticket channel!", ephemeral=True)
                return

            # Send confirmation
            await interaction.response.send_message("🔒 Closing ticket...")

            # Close and lock the thread
            await interaction.channel.edit(archived=True, locked=True)

            # Log ticket closure
            try:
                await interaction.client.db_manager.log_event(
                    interaction.guild.id,
                    interaction.user.id,
                    "ticket_close",
                    f"Ticket {interaction.channel.name} closed by {interaction.user}"
                )
            except:
                pass  # Don't stop execution if logging fails

        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

class Tickets(commands.Cog):
    """Manage server support tickets"""
    
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

    async def check_inactive_tickets(self):
        """Check and close inactive tickets"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                for guild in self.bot.guilds:
                    settings = await self.db_manager.get_guild_data(guild.id)
                    ticket_settings = settings.get('tickets', {}).get('settings', {})
                    
                    if not ticket_settings.get('auto_close', False):
                        continue
                        
                    inactive_hours = ticket_settings.get('close_hours', 24)
                    cutoff = datetime.utcnow() - timedelta(hours=inactive_hours)
                    
                    for channel in guild.channels:
                        if isinstance(channel, discord.ForumChannel) and channel.name == 'tickets':
                            async for thread in channel.archived_threads(limit=None):
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

    @commands.hybrid_group(name="ticket")
    async def ticket(self, ctx):
        """Ticket management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ticket.command(name="open")
    async def ticket_open(self, ctx, *, reason: str):
        """Open a new support ticket"""
        try:
            # Get ticket settings
            settings = await self.db_manager.get_guild_data(ctx.guild.id)
            ticket_settings = settings.get('tickets', {}).get('settings', {})
            
            # Find or create tickets category
            category_id = ticket_settings.get('category_id')
            category = ctx.guild.get_channel(category_id) if category_id else None
            
            if not category:
                # Create category if not exists
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
                }
                
                # Add support role permissions if configured
                if 'staff_role_id' in ticket_settings:
                    support_role = ctx.guild.get_role(ticket_settings['staff_role_id'])
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True)

                category = await ctx.guild.create_category("Support Tickets", overwrites=overwrites)
                
                # Save category
                ticket_settings['category_id'] = category.id
                await self.db_manager.update_guild_data(
                    ctx.guild.id,
                    ticket_settings,
                    ['tickets', 'settings']
                )

            # Create ticket channel
            channel_name = f"ticket-{ctx.author.name}"
            channel = await category.create_text_channel(
                channel_name,
                topic=f"Support ticket for {ctx.author}"
            )

            # Add user to ticket channel
            await channel.set_permissions(ctx.author, read_messages=True, send_messages=True)

            # Send initial message
            embed = self.ui.info_embed(
                "Support Ticket Created",
                f"**User:** {ctx.author.mention}\n**Reason:** {reason}"
            )
            view = CloseButton()
            await channel.send(embed=embed, view=view)

            # Log ticket creation
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "ticket_open",
                f"Opened ticket: {reason}"
            )

            # Send confirmation
            confirm = self.ui.success_embed(
                "Ticket Created",
                f"Your ticket has been created in {channel.mention}"
            )
            await ctx.send(embed=confirm, ephemeral=True)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @ticket.command(name="close")
    async def ticket_close(self, ctx):
        """Close the current ticket"""
        try:
            if not ctx.channel.name.startswith('ticket-'):
                await ctx.send("This command can only be used in ticket channels!", ephemeral=True)
                return

            await ctx.channel.edit(archived=True, locked=True)
            
            # Log ticket closure
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "ticket_close",
                f"Closed ticket {ctx.channel.name}"
            )

            await ctx.send("🔒 Ticket closed!")

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @ticket.command(name="logs")
    @commands.has_permissions(manage_messages=True)
    async def ticket_logs(self, ctx, user: discord.Member = None):
        """View past tickets by user"""
        try:
            logs = await self.db_manager.get_ticket_logs(ctx.guild.id, user.id if user else None)
            
            if not logs:
                await ctx.send("No ticket logs found!")
                return

            # Format logs
            description = ""
            for log in logs:
                action = log.get('action')
                details = log.get('details', '')
                timestamp = datetime.fromisoformat(log.get('timestamp'))
                description += f"**{action}** - <t:{int(timestamp.timestamp())}:R>\n{details}\n\n"

            embed = self.ui.info_embed(
                f"Ticket Logs for {user.display_name if user else 'All Users'}",
                description
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @ticket.command(name="transcript")
    async def ticket_transcript(self, ctx):
        """Export the current ticket transcript"""
        try:
            if not ctx.channel.name.startswith('ticket-'):
                await ctx.send("This command can only be used in ticket channels!", ephemeral=True)
                return

            messages = []
            async for message in ctx.channel.history(limit=None, oldest_first=True):
                timestamp = int(message.created_at.timestamp())
                messages.append(
                    f"[<t:{timestamp}:F>] {message.author}: {message.content}"
                )

            transcript = "\n".join(messages)
            
            # Create file
            file = discord.File(
                fp=transcript.encode('utf-8'),
                filename=f"transcript-{ctx.channel.name}.txt"
            )
            
            await ctx.send(
                "Here's the ticket transcript:",
                file=file
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))