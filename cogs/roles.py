import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

class RolesCog(commands.Cog):
    """Handles role management commands"""
    
    def __init__(self, bot):
        self.bot = bot

    async def _can_manage_role(self, guild: discord.Guild, role: discord.Role) -> bool:
        """Check if the bot can manage a role"""
        bot_member = guild.me
        
        # Check if role is not higher than bot's highest role
        if role >= bot_member.top_role:
            return False
            
        # Check if bot has Manage Roles permission
        if not bot_member.guild_permissions.manage_roles:
            return False
            
        # Check if role is managed by integration (bot roles, etc)
        if role.managed:
            return False
            
        return True

    async def _handle_bulk_role_update(self, member: discord.Member, role: discord.Role, action: str) -> bool:
        """Handle adding/removing roles with proper error handling"""
        try:
            if action == "add":
                if role in member.roles:
                    return False
                await member.add_roles(role)
            else:  # remove
                if role not in member.roles:
                    return False
                await member.remove_roles(role)
            return True
        except discord.Forbidden:
            return False

    async def _update_user_color_role(self, member: discord.Member, new_role: Optional[discord.Role] = None) -> bool:
        """Update a user's color role, removing any existing ones"""
        try:
            # Get configured color roles
            color_roles = await self.bot.db_manager.get_color_roles(member.guild.id)
            
            # Remove existing color roles
            roles_to_remove = [role for role in member.roles if str(role.id) in color_roles]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            
            # Add new color role if specified
            if new_role:
                await member.add_roles(new_role)
            
            return True
        except discord.Forbidden:
            return False

    # Main roles group
    roles = app_commands.Group(
        name="roles",
        description="Manage server roles",
        default_permissions=discord.Permissions(manage_roles=True)
    )

    @roles.command(
        name="color",
        description="Set or clear your color role"
    )
    @app_commands.describe(
        action="The action to perform",
        role="The color role to set (only needed when setting a color)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set color role", value="set"),
        app_commands.Choice(name="Clear color role", value="clear")
    ])
    async def color_role(
        self,
        interaction: discord.Interaction,
        action: str,
        role: Optional[discord.Role] = None
    ):
        """Set or clear your color role"""
        try:
            if action == "set" and not role:
                raise ValueError("Please specify a role when setting a color")

            # Get configured color roles
            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
            
            if action == "set":
                if str(role.id) not in color_roles:
                    raise ValueError("That role is not configured as a color role")
                    
                # Update user's color role
                success = await self._update_user_color_role(interaction.member, role)
                if success:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Set",
                            f"Your color has been set to {role.mention}"
                        )
                    )
                else:
                    raise commands.CommandError("Failed to update color role")

            else:  # clear
                success = await self._update_user_color_role(interaction.member)
                if success:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Cleared",
                            "Your color role has been removed"
                        )
                    )
                else:
                    raise commands.CommandError("Failed to clear color role")

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Color Role",
                    str(e)
                ),
                ephemeral=True
            )
        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @roles.command(
        name="manage",
        description="Manage server roles"
    )
    @app_commands.describe(
        action="The action to perform",
        role="The role to manage (required for most actions)",
        users="Users to update (for add/remove actions)",
        message_id="Message ID for reaction roles",
        emoji="Emoji for reaction roles",
        channel="Channel for auto-role message (optional)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set auto-role", value="auto_set"),
        app_commands.Choice(name="Disable auto-role", value="auto_disable"),
        app_commands.Choice(name="Add role", value="add"),
        app_commands.Choice(name="Remove role", value="remove"),
        app_commands.Choice(name="Bind reaction role", value="react_bind"),
        app_commands.Choice(name="Unbind reaction roles", value="react_unbind"),
        app_commands.Choice(name="List reaction roles", value="react_list")
    ])
    async def role_manage(
        self,
        interaction: discord.Interaction,
        action: str,
        role: Optional[discord.Role] = None,
        users: Optional[str] = None,
        message_id: Optional[str] = None,
        emoji: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Manage server roles"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if action in ["auto_set", "add", "remove", "react_bind"] and not role:
                raise ValueError("Please specify a role for this action")

            if action in ["add", "remove"] and not users:
                raise ValueError("Please specify users for this action")

            if action == "react_bind" and (not message_id or not emoji):
                raise ValueError("Please specify both message ID and emoji for reaction roles")

            # Auto-role actions
            if action == "auto_set":
                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I cannot manage that role")
                    
                await self.bot.db_manager.update_auto_role(interaction.guild_id, role.id)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Auto-Role Set",
                        f"New members will automatically receive the {role.mention} role"
                    )
                )

            elif action == "auto_disable":
                await self.bot.db_manager.update_auto_role(interaction.guild_id, None)
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Auto-Role Disabled",
                        "New members will no longer receive an automatic role"
                    )
                )

            elif action in ["add", "remove"]:
                # Parse user mentions/IDs
                user_ids = [uid.strip() for uid in users.split() if uid.strip()]
                members = []
                
                for uid in user_ids:
                    try:
                        if uid.startswith('<@') and uid.endswith('>'):
                            uid = uid[2:-1]
                        if uid.startswith('!'):
                            uid = uid[1:]
                        member = interaction.guild.get_member(int(uid))
                        if member:
                            members.append(member)
                    except ValueError:
                        continue

                if not members:
                    raise ValueError("No valid members found")

                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I cannot manage that role")

                # Start bulk role update
                success = []
                failed = []
                
                for member in members:
                    if await self._handle_bulk_role_update(member, role, action):
                        success.append(member.mention)
                    else:
                        failed.append(member.mention)

                # Create result message
                action_text = "added to" if action == "add" else "removed from"
                embed = self.bot.ui_manager.info_embed(
                    "Bulk Role Update",
                    f"Role {role.mention} {action_text}:"
                )
                
                if success:
                    embed.add_field(
                        name="Success",
                        value=", ".join(success[:10]) + ("..." if len(success) > 10 else ""),
                        inline=False
                    )
                if failed:
                    embed.add_field(
                        name="Failed",
                        value=", ".join(failed[:10]) + ("..." if len(failed) > 10 else ""),
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            elif action == "react_bind":
                try:
                    target_message = None
                    for channel in interaction.guild.text_channels:
                        try:
                            target_message = await channel.fetch_message(int(message_id))
                            if target_message:
                                break
                        except:
                            continue
                            
                    if not target_message:
                        raise ValueError("Could not find the specified message")
                        
                    # Validate emoji
                    try:
                        await target_message.add_reaction(emoji)
                    except discord.errors.HTTPException:
                        raise ValueError("Invalid emoji")
                        
                    if not await self._can_manage_role(interaction.guild, role):
                        raise commands.CommandError("I cannot manage that role")
                        
                    await self.bot.db_manager.update_reaction_roles(
                        interaction.guild_id,
                        int(message_id),
                        emoji,
                        role.id
                    )
                    
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Role Created",
                            f"Users who react with {emoji} will receive {role.mention}"
                        )
                    )
                except ValueError as e:
                    raise commands.CommandError(str(e))

            elif action == "react_unbind":
                if not message_id:
                    # Remove all reaction roles
                    await self.bot.db_manager.update_guild_data(interaction.guild_id, 'reaction_roles', {})
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Roles Cleared",
                            "All reaction roles have been removed"
                        )
                    )
                else:
                    # Remove specific message's reaction roles
                    reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)
                    if message_id in reaction_roles:
                        del reaction_roles[message_id]
                        await self.bot.db_manager.update_guild_data(
                            interaction.guild_id,
                            'reaction_roles',
                            reaction_roles
                        )
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Roles Removed",
                            f"Removed all reaction roles from message {message_id}"
                        )
                    )

            elif action == "react_list":
                reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)
                if not reaction_roles:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Reaction Roles",
                            "No reaction roles are configured"
                        )
                    )
                    return

                # Create pages for each message's reaction roles
                pages = []
                for msg_id, bindings in reaction_roles.items():
                    desc = []
                    for emoji, role_id in bindings.items():
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            desc.append(f"{emoji} → {role.mention}")
                            
                    if desc:
                        embed = self.bot.ui_manager.info_embed(
                            f"Reaction Roles - Message {msg_id}",
                            "\n".join(desc)
                        )
                        pages.append(embed)

                if pages:
                    await self.bot.ui_manager.paginate(interaction, pages)
                else:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Reaction Roles",
                            "No active reaction roles found"
                        )
                    )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to use this command"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Input",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle giving auto-role to new members"""
        try:
            auto_role_id, enabled = await self.bot.db_manager.get_auto_role(member.guild.id)
            if enabled and auto_role_id:
                role = member.guild.get_role(auto_role_id)
                if role:
                    await member.add_roles(role)
        except Exception as e:
            print(f"Error applying auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle adding roles when users react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role bindings
            reaction_roles = await self.bot.db_manager.get_reaction_roles(
                payload.guild_id,
                str(payload.message_id)
            )
            
            if not reaction_roles:
                return
                
            # Check if this reaction has a role binding
            role_id = reaction_roles.get(str(payload.emoji))
            if not role_id:
                return
                
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
                
            role = guild.get_role(int(role_id))
            member = guild.get_member(payload.user_id)
            
            if role and member:
                await member.add_roles(role)
                
        except Exception as e:
            print(f"Error handling reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removing roles when users un-react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role bindings
            reaction_roles = await self.bot.db_manager.get_reaction_roles(
                payload.guild_id,
                str(payload.message_id)
            )
            
            if not reaction_roles:
                return
                
            # Check if this reaction has a role binding
            role_id = reaction_roles.get(str(payload.emoji))
            if not role_id:
                return
                
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
                
            role = guild.get_role(int(role_id))
            member = guild.get_member(payload.user_id)
            
            if role and member:
                await member.remove_roles(role)
                
        except Exception as e:
            print(f"Error handling reaction role removal: {e}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot))