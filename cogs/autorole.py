import discord
from discord.commands import slash_command, Option
from discord.ext import commands
from typing import Optional, List
from utils.db_manager import DBManager

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Automatically assign roles to new members"""
        if member.bot:
            return
            
        try:
            auto_role = await self.db_manager.get_auto_role(member.guild.id)
            if not auto_role or not auto_role[1]:  # If no role or disabled
                return
                
            role_id = auto_role[0]
            role = member.guild.get_role(role_id)
            
            if role:
                await member.add_roles(role, reason="Auto Role")
                
                # Log the action
                await self.db_manager.log_event(
                    member.guild.id,
                    member.id,
                    "autorole",
                    f"Auto role {role.name} assigned to {member}"
                )
        except Exception as e:
            print(f"Error in auto role assignment: {e}")

    @discord.slash_command(description="Set the automatic role for new members")
    @commands.default_member_permissions(manage_roles=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        """Set the automatic role for new members"""
        try:
            # Validate bot's role hierarchy
            if role >= interaction.guild.me.top_role:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "I cannot assign roles that are higher than or equal to my highest role!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await self.db_manager.set_auto_role(interaction.guild.id, role.id, True)
            
            embed = self.bot.create_embed(
                "Auto Role Set",
                f"New members will now automatically receive the {role.mention} role.",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Disable the automatic role assignment")
    @commands.default_member_permissions(manage_roles=True)
    async def removeautorole(self, interaction: discord.Interaction):
        """Disable the automatic role assignment"""
        try:
            await self.db_manager.set_auto_role(interaction.guild.id, None, False)
            
            embed = self.bot.create_embed(
                "Auto Role Disabled",
                "New members will no longer receive an automatic role.",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.slash_command(description="Bind a role to a reaction on a message")
    @commands.default_member_permissions(manage_roles=True)
    async def bind_reaction_role(
        self, 
        interaction: discord.Interaction, 
        message_id: str,
        emoji: str,
        role: discord.Role
    ):
        """Bind a role to a reaction on a message"""
        try:
            # Convert message ID to int
            try:
                message_id = int(message_id)
            except ValueError:
                embed = self.bot.create_embed(
                    "Invalid Input",
                    "Please provide a valid message ID.",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Validate role hierarchy
            if role >= interaction.guild.me.top_role:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "I cannot assign roles that are higher than or equal to my highest role!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Try to find the message
            try:
                message = await interaction.channel.fetch_message(message_id)
            except discord.NotFound:
                embed = self.bot.create_embed(
                    "Message Not Found",
                    "Make sure you're using this command in the same channel as the message.",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Add the reaction to verify emoji is valid
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                embed = self.bot.create_embed(
                    "Invalid Emoji",
                    "Please provide a valid emoji.",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Store the reaction role binding
            await self.db_manager.add_reaction_role(message_id, str(emoji), role.id)
            
            description = (
                f"Role: {role.mention}\n"
                f"Emoji: {emoji}\n"
                f"Message: [Jump to Message]({message.jump_url})"
            )
            
            embed = self.bot.create_embed(
                "Reaction Role Bound",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction role assignments"""
        if payload.member.bot:
            return

        try:
            # Get reaction role data
            reaction_roles = await self.db_manager.get_reaction_roles(payload.message_id)
            if not reaction_roles:
                return

            for emoji, role_id in reaction_roles:
                if str(payload.emoji) == emoji:
                    role = payload.member.guild.get_role(role_id)
                    if role:
                        await payload.member.add_roles(role, reason="Reaction Role")
                        
                        # Log the action
                        await self.db_manager.log_event(
                            payload.guild_id,
                            payload.user_id,
                            "reaction_role",
                            f"Role {role.name} added via reaction"
                        )
                    break
                    
        except Exception as e:
            print(f"Error in reaction role assignment: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction role removals"""
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return

            # Get reaction role data
            reaction_roles = await self.db_manager.get_reaction_roles(payload.message_id)
            if not reaction_roles:
                return

            for emoji, role_id in reaction_roles:
                if str(payload.emoji) == emoji:
                    role = guild.get_role(role_id)
                    if role:
                        await member.remove_roles(role, reason="Reaction Role Removed")
                        
                        # Log the action
                        await self.db_manager.log_event(
                            payload.guild_id,
                            payload.user_id,
                            "reaction_role",
                            f"Role {role.name} removed via reaction"
                        )
                    break
                    
        except Exception as e:
            print(f"Error in reaction role removal: {e}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))