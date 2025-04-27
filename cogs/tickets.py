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

    @discord.slash_command(description="Create a support ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str = None):
        """Create a support ticket"""
        try:
            # Check if user already has an open ticket
            existing_ticket = await self.db_manager.get_open_ticket(interaction.user.id, interaction.guild.id)
            if existing_ticket:
                channel = interaction.guild.get_channel(existing_ticket['channel_id'])
                if channel:
                    embed = self.bot.create_embed(
                        "Ticket Already Open",
                        f"You already have an open ticket: {channel.mention}",
                        command_type="User"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            # Get ticket settings
            settings = await self.db_manager.get_data('tickets_config', str(interaction.guild.id))
            if not settings:
                embed = self.bot.create_embed(
                    "Tickets Not Configured",
                    "The ticket system has not been set up yet!",
                    command_type="User"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            category = interaction.guild.get_channel(settings.get('category_id'))
            support_role = interaction.guild.get_role(settings.get('support_role_id'))

            if not category or not support_role:
                embed = self.bot.create_embed(
                    "Configuration Error",
                    "The ticket system is not properly configured!",
                    command_type="User"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Create the ticket channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }

            channel = await interaction.guild.create_text_channel(
                f"ticket-{interaction.user.name}",
                category=category,
                overwrites=overwrites
            )

            # Create the initial message
            description = (
                f"Support will be with you shortly.\n\n"
                f"User: {interaction.user.mention}\n"
                f"Reason: {reason or 'No reason provided'}"
            )

            embed = self.bot.create_embed(
                "Ticket Created",
                description,
                command_type="User"
            )

            # Add close button
            view = CloseButton()
            await channel.send(embed=embed, view=view)

            # Store ticket in database
            await self.db_manager.create_ticket(
                interaction.guild.id,
                channel.id,
                interaction.user.id
            )

            # Send confirmation
            confirm_embed = self.bot.create_embed(
                "Ticket Created",
                f"Your ticket has been created: {channel.mention}",
                command_type="User"
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="User"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))