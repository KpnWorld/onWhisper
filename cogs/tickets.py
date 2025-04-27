import discord
from discord.commands import slash_command, Option
from discord.ext import commands
from datetime import datetime
from utils.db_manager import DBManager

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.active_tickets = {}

    @discord.slash_command(description="Create a new support ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str):
        """Create a new support ticket thread"""
        try:
            # Check if user already has an open ticket
            existing_ticket = await self.db_manager.get_open_ticket(interaction.user.id, interaction.guild.id)
            if existing_ticket:
                embed = self.bot.create_embed(
                    "Ticket Already Exists",
                    "You already have an open ticket! Please close it before creating a new one.",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Create thread for the ticket
            thread = await interaction.channel.create_thread(
                name=f"ticket-{interaction.user.name}",
                type=discord.ChannelType.private_thread,
                reason=f"Support ticket for {interaction.user.name}"
            )

            # Store ticket in database
            await self.db_manager.create_ticket(
                interaction.guild.id,
                thread.id,
                interaction.user.id
            )

            # Create initial ticket message
            description = (
                f"Ticket created by {interaction.user.mention}\n"
                f"Reason: {reason}\n"
                f"\n"
                "Instructions:\n"
                "• Staff will assist you shortly\n"
                "• Please provide any additional information\n"
                "• Use `/close-ticket` when resolved"
            )
            
            embed = self.bot.create_embed(
                "Support Ticket Created",
                description,
                command_type="Support"
            )

            await thread.send(embed=embed)
            await thread.add_user(interaction.user)

            # Send confirmation to user
            confirm_embed = self.bot.create_embed(
                "Ticket Created",
                f"Your ticket has been created in {thread.mention}",
                command_type="Support"
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

            # Cache the ticket
            self.active_tickets[thread.id] = {
                'user_id': interaction.user.id,
                'created_at': datetime.utcnow()
            }

        except discord.Forbidden:
            error_embed = self.bot.create_embed(
                "Permission Error",
                "I don't have permission to create ticket threads!",
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Close your current support ticket")
    async def close_ticket(self, interaction: discord.Interaction):
        """Close an active support ticket"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                embed = self.bot.create_embed(
                    "Invalid Channel",
                    "This command can only be used in ticket threads!",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Verify it's a ticket thread
            ticket = await self.db_manager.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                embed = self.bot.create_embed(
                    "Not a Ticket",
                    "This thread is not a support ticket!",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Verify user has permission to close
            is_staff = interaction.user.guild_permissions.manage_threads
            is_ticket_owner = ticket[3] == interaction.user.id
            
            if not (is_staff or is_ticket_owner):
                embed = self.bot.create_embed(
                    "Permission Error",
                    "You don't have permission to close this ticket!",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Close the ticket
            await self.db_manager.close_ticket(interaction.channel.id)
            
            # Create closure embed
            embed = self.bot.create_embed(
                "Ticket Closed",
                f"Ticket closed by {interaction.user.mention}",
                command_type="Support"
            )
            await interaction.channel.send(embed=embed)
            
            # Archive and lock the thread
            await interaction.channel.edit(archived=True, locked=True)
            
            # Remove from cache
            self.active_tickets.pop(interaction.channel.id, None)
            
            confirm_embed = self.bot.create_embed(
                "Success",
                "Ticket has been closed successfully!",
                command_type="Support"
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Add a user to the current ticket")
    @commands.default_member_permissions(manage_threads=True)
    async def add_to_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to a ticket thread (Staff only)"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                embed = self.bot.create_embed(
                    "Invalid Channel",
                    "This command can only be used in ticket threads!",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.channel.add_user(user)
            
            description = f"Added {user.mention} to the ticket"
            embed = self.bot.create_embed(
                "User Added",
                description,
                command_type="Support"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Remove a user from the current ticket")
    @commands.default_member_permissions(manage_threads=True)
    async def remove_from_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """Remove a user from a ticket thread (Staff only)"""
        try:
            if not isinstance(interaction.channel, discord.Thread):
                embed = self.bot.create_embed(
                    "Invalid Channel",
                    "This command can only be used in ticket threads!",
                    command_type="Support"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.channel.remove_user(user)
            
            description = f"Removed {user.mention} from the ticket"
            embed = self.bot.create_embed(
                "User Removed",
                description,
                command_type="Support"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Send ticket system information")
    @commands.default_member_permissions(administrator=True)
    async def tickets_info(self, interaction: discord.Interaction):
        """Send an embed explaining the ticket system (Admin only)"""
        try:
            description = (
                "**📝 How to Use the Ticket System**\n\n"
                "**Creating a Ticket**\n"
                "• Use `/ticket [reason]` to create a new support ticket\n"
                "• Provide a clear reason for your ticket\n"
                "• You can only have one open ticket at a time\n\n"
                "**In Your Ticket**\n"
                "• Be patient and wait for staff to respond\n"
                "• Provide any additional information needed\n"
                "• Keep all support discussion in your ticket\n\n"
                "**Closing Your Ticket**\n"
                "• Use `/close-ticket` when your issue is resolved\n"
                "• Staff can also close tickets if needed\n\n"
                "**Note:** Please don't create tickets for non-support issues."
            )
            
            embed = self.bot.create_embed(
                "🎫 Server Ticket System",
                description,
                command_type="Support"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Support"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))