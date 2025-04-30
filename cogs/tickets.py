import discord 
from discord.ext import commands
from datetime import datetime
import asyncio
from utils.db_manager import DBManager

class CloseButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Get ticket data
        db_manager = DBManager()
        ticket = await db_manager.get_ticket_by_channel(interaction.channel.id)
        
        if not ticket:
            await interaction.followup.send("This is not a ticket channel!", ephemeral=True)
            return
            
        # Close ticket
        await db_manager.close_ticket(interaction.channel.id)
        await interaction.channel.delete()

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager  # Use bot's DBManager instance
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

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

    @commands.hybrid_command(description="Create a support ticket")
    async def ticket(self, ctx):
        """Create a support ticket using a form"""
        try:
            # Check if using slash command or prefix
            if hasattr(ctx, 'interaction') and ctx.interaction:
                # Show modal for slash command
                modal = self.TicketModal()
                await ctx.interaction.response.send_modal(modal)
                await modal.wait()
                
                # Get ticket reason from modal
                reason = f"{modal.summary}\n\n{modal.details}" if modal.details else modal.summary
                followup = modal.interaction
            else:
                # For prefix command, send regular message
                embed = self.ui.info_embed(
                    "Create Ticket",
                    "Use the slash command `/ticket` to create a support ticket"
                )
                await ctx.send(embed=embed)
                return

            # Get guild data
            guild_data = await self.db_manager.get_guild_data(ctx.guild.id)
            ticket_settings = guild_data.get('tickets', {})
            
            # Check existing tickets
            open_tickets = ticket_settings.get('open_tickets', [])
            user_ticket = next(
                (t for t in open_tickets if t['user_id'] == ctx.author.id and not t.get('closed_at')),
                None
            )

            if user_ticket:
                channel = ctx.guild.get_channel(user_ticket['channel_id'])
                if channel:
                    embed = self.ui.error_embed(
                        "Ticket Already Open",
                        f"You already have an open ticket: {channel.mention}"
                    )
                    await followup.send(embed=embed, ephemeral=True)
                    return

            # Get ticket settings
            settings = await self.db_manager.get_data('tickets_config', str(ctx.guild.id))
            if not settings:
                embed = self.ui.error_embed(
                    "Tickets Not Configured",
                    "The ticket system has not been set up yet!"
                )
                await followup.send(embed=embed, ephemeral=True)
                return

            category = ctx.guild.get_channel(settings.get('category_id'))
            support_role = ctx.guild.get_role(settings.get('support_role_id'))

            if not category or not support_role:
                embed = self.ui.user_embed(
                    "Configuration Error",
                    "The ticket system is not properly configured!",
                )
                await modal.interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Create the ticket channel
            channel_name = f"ticket-{ctx.author.name}-{len(open_tickets) + 1}"
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }

            channel = await ctx.guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites
            )

            # Create ticket data
            ticket_data = {
                'channel_id': channel.id,
                'user_id': ctx.author.id,
                'created_at': datetime.utcnow().isoformat(),
                'reason': reason,
                'closed_at': None
            }
            
            # Add to open tickets
            open_tickets.append(ticket_data)
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'open_tickets': open_tickets},
                ['tickets']
            )

            # Create the initial message
            description = (
                f"Support will be with you shortly.\n\n"
                f"User: {ctx.author.mention}\n"
                f"Reason: {reason}"
            )

            embed = self.ui.user_embed(
                "Ticket Created",
                description
            )

            # Add close button and send initial message
            view = CloseButton()
            await channel.send(embed=embed, view=view)

            # Send confirmation
            confirm_embed = self.ui.user_embed(
                "Ticket Created",
                f"Your ticket has been created: {channel.mention}",
            )
            await followup.send(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            error_embed = self.ui.error_embed(
                "Error Creating Ticket",
                str(e)
            )
            # Handle response based on context
            if hasattr(ctx, 'interaction') and ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await ctx.interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await ctx.send(embed=error_embed)

async def setup(bot):
    await bot.add_cog(Tickets(bot))