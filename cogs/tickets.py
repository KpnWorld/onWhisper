import discord
from discord.ext import commands
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
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager

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

    @commands.hybrid_command(description="Create a support ticket")
    async def ticket(self, ctx):
        """Create a support ticket using a form"""
        modal = self.TicketModal()
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()
        
        # Use the form data to create the ticket
        reason = f"{modal.summary}\n\n{modal.details}"

        try:
            # Verify bot permissions
            required_permissions = [
                'manage_channels',
                'send_messages',
                'embed_links',
                'manage_roles'
            ]
            
            missing_perms = []
            for perm in required_permissions:
                if not getattr(ctx.guild.me.guild_permissions, perm):
                    missing_perms.append(perm)
                    
            if missing_perms:
                await ctx.send(f"I need the following permissions: {', '.join(missing_perms)}")
                return

            # Check database connection
            try:
                existing_ticket = await self.db_manager.get_open_ticket(ctx.author.id, ctx.guild.id)
            except Exception as e:
                await ctx.send("Unable to check ticket status. Database error.")
                print(f"DB Error in tickets: {e}")
                return

            # Check if user already has an open ticket
            if existing_ticket:
                channel = ctx.guild.get_channel(existing_ticket['channel_id'])
                if channel:
                    embed = self.ui.user_embed(
                        "Ticket Already Open",
                        f"You already have an open ticket: {channel.mention}",
                    )
                    await ctx.send(embed=embed, ephemeral=True)
                    return

            # Get ticket settings
            settings = await self.db_manager.get_data('tickets_config', str(ctx.guild.id))
            if not settings:
                embed = self.ui.user_embed(
                    "Tickets Not Configured",
                    "The ticket system has not been set up yet!",
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            category = ctx.guild.get_channel(settings.get('category_id'))
            support_role = ctx.guild.get_role(settings.get('support_role_id'))

            if not category or not support_role:
                embed = self.ui.user_embed(
                    "Configuration Error",
                    "The ticket system is not properly configured!",
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Create the ticket channel
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }

            channel = await ctx.guild.create_text_channel(
                f"ticket-{ctx.author.name}",
                category=category,
                overwrites=overwrites
            )

            # Create the initial message
            description = (
                f"Support will be with you shortly.\n\n"
                f"User: {ctx.author.mention}\n"
                f"Reason: {reason or 'No reason provided'}"
            )

            embed = self.ui.user_embed(
                "Ticket Created",
                description
            )

            # Add close button
            view = CloseButton()
            await channel.send(embed=embed, view=view)

            # Store ticket in database
            await self.db_manager.create_ticket(
                ctx.guild.id,
                channel.id,
                ctx.author.id
            )

            # Send confirmation
            confirm_embed = self.ui.user_embed(
                "Ticket Created",
                f"Your ticket has been created: {channel.mention}",
            )
            await ctx.send(embed=confirm_embed, ephemeral=True)

        except discord.Forbidden:
            await ctx.send("I don't have the required permissions to create tickets.")
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

async def setup(bot):
    await bot.add_cog(Tickets(bot))