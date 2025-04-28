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

    @commands.hybrid_command(description="Create a support ticket")
    async def ticket(self, ctx, *, reason: str = None):
        try:
            # Check if user already has an open ticket
            existing_ticket = await self.db_manager.get_open_ticket(ctx.author.id, ctx.guild.id)
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

        except Exception as e:
            error_embed = self.ui.user_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))