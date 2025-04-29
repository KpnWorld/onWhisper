import discord
from discord.ext import commands
from typing import Optional, List
from utils.db_manager import DBManager
from datetime import datetime

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui = self.bot.ui_manager

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Automatically assign roles to new members"""
        try:
            if member.bot:
                return

            # Get guild data
            guild_data = await self.db_manager.get_guild_data(member.guild.id)
            autorole_settings = guild_data.get('autorole', {})
            
            if not autorole_settings.get('enabled', False):
                return

            role_id = autorole_settings.get('role_id')
            if not role_id:
                return

            role = member.guild.get_role(role_id)
            if role and role < member.guild.me.top_role:
                await member.add_roles(role, reason="Auto Role")

        except Exception as e:
            print(f"Error in autorole: {e}")

    @commands.hybrid_command(description="Set the automatic role for new members")
    @commands.has_permissions(manage_roles=True)
    async def setautorole(self, ctx, role: discord.Role):
        try:
            # Update to use guild_data path
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {
                    'role_id': role.id,
                    'enabled': True,
                    'last_updated': datetime.utcnow().isoformat()
                },
                ['autorole']
            )
            
            embed = self.ui.admin_embed(
                "Auto Role Set",
                f"New members will now automatically receive the {role.mention} role."
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Disable the automatic role assignment")
    @commands.has_permissions(manage_roles=True)
    async def removeautorole(self, ctx):
        try:
            # Update to use guild_data path
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {
                    'role_id': None,
                    'enabled': False,
                    'last_updated': datetime.utcnow().isoformat()
                },
                ['autorole']
            )
            
            embed = self.ui.admin_embed(
                "Auto Role Disabled",
                "New members will no longer receive an automatic role."
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Bind a role to a reaction on a message")
    @commands.has_permissions(manage_roles=True)
    async def bindreactionrole(self, ctx, message_id: str, emoji: str, role: discord.Role):
        try:
            try:
                message_id = int(message_id)
            except ValueError:
                embed = self.ui.error_embed(
                    "Invalid Input",
                    "Please provide a valid message ID."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            if role >= ctx.guild.me.top_role:
                embed = self.ui.error_embed(
                    "Permission Error",
                    "I cannot assign roles that are higher than or equal to my highest role!"
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Try to find the message
            try:
                message = await ctx.channel.fetch_message(message_id)
            except discord.NotFound:
                embed = self.ui.error_embed(
                    "Message Not Found",
                    "Make sure you're using this command in the same channel as the message."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Add the reaction to verify emoji is valid
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                embed = self.ui.error_embed(
                    "Invalid Emoji",
                    "Please provide a valid emoji."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Store the reaction role binding
            await self.db_manager.add_reaction_role(message_id, str(emoji), role.id)
            
            description = (
                f"Role: {role.mention}\n"
                f"Emoji: {emoji}\n"
                f"Message: [Jump to Message]({message.jump_url})"
            )
            
            embed = self.ui.admin_embed(
                "Reaction Role Bound",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Remove reaction role bindings from a message") 
    @commands.has_permissions(manage_roles=True)
    async def unbindreactionrole(self, ctx, message_id: str):
        """Remove reaction role bindings from a message"""
        try:
            try:
                message_id = int(message_id)
            except ValueError:
                embed = self.ui.error_embed(
                    "Invalid Input",
                    "Please provide a valid message ID."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Try to find the message
            try:
                message = await ctx.channel.fetch_message(message_id)
            except discord.NotFound:
                embed = self.ui.error_embed(
                    "Message Not Found",
                    "Make sure you're using this command in the same channel as the message."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Get all reaction roles for this message
            reaction_roles = await self.db_manager.get_reaction_roles(message_id)
            
            if not reaction_roles:
                embed = self.ui.error_embed(
                    "No Reaction Roles",
                    "This message has no reaction role bindings."
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
            
            # Create select menu options
            options = []
            for emoji, role_id in reaction_roles:
                role = ctx.guild.get_role(role_id)
                role_name = role.name if role else "Unknown Role"
                options.append({
                    "label": f"Role: {role_name}",
                    "description": f"Emoji: {emoji}",
                    "value": emoji,
                    "emoji": emoji if len(emoji) == 1 else None
                })

            view = self.ui.CommandSelectView(
                options=options,
                placeholder="Select reaction role to remove"
            )

            embed = self.ui.admin_embed(
                "Remove Reaction Role",
                f"Select which reaction role binding to remove from [this message]({message.jump_url})"
            )

            sent = await ctx.send(embed=embed, view=view)
            view.message = sent

            # Wait for selection
            await view.wait()
            if view.result:
                emoji = view.result
                await self.db_manager.remove_reaction_role(message_id, emoji)
                try:
                    await message.clear_reaction(emoji)
                except:
                    pass  # Ignore if removing reaction fails

                description = (
                    f"Message: [Jump to Message]({message.jump_url})\n"
                    f"Emoji: {emoji}\n"
                    "Reaction role binding has been removed."
                )
                
                result_embed = self.ui.admin_embed(
                    "Reaction Role Unbound",
                    description
                )
                await sent.edit(embed=result_embed, view=None)
            else:
                await sent.edit(
                    embed=self.ui.error_embed("Timed Out", "Selection timed out"),
                    view=None
                )
            
        except Exception as e:
            error_embed = self.ui.error_embed("Error", str(e))
            await ctx.send(embed=error_embed, ephemeral=True)

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