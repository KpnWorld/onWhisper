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

    # Role management command group
    roles_group = app_commands.Group(
        name="roles",
        description="Manage server roles",
        default_permissions=discord.Permissions(manage_roles=True)
    )

    @roles_group.command(
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
                raise ValueError("Role is required when setting a color")

            # Get configured color roles
            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)

            if action == "set":
                if str(role.id) not in color_roles:
                    raise ValueError(f"{role.mention} is not a configured color role")

                success = await self._update_user_color_role(interaction.user, role)
                if success:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Set",
                            f"Your color has been set to {role.mention}"
                        ),
                        ephemeral=True
                    )
                else:
                    raise commands.CommandError("Failed to update color role")

            else:  # clear
                success = await self._update_user_color_role(interaction.user)
                if success:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Cleared",
                            "Your color role has been removed"
                        ),
                        ephemeral=True
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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
                ephemeral=True
            )

    @roles_group.command(
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
                raise ValueError("Role is required for this action")

            if action in ["add", "remove"] and not users:
                raise ValueError("Users parameter is required for adding/removing roles")

            if action == "react_bind" and (not message_id or not emoji):
                raise ValueError("Message ID and emoji are required for reaction role binding")

            # Auto-role actions
            if action == "auto_set":
                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I don't have permission to manage that role")

                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'autorole', {
                    'role_id': str(role.id),
                    'enabled': True
                })
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Auto-Role Configured",
                        f"New members will automatically receive the {role.mention} role"
                    )
                )

            elif action == "auto_disable":
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'autorole', {
                    'role_id': None,
                    'enabled': False
                })
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Auto-Role Disabled",
                        "New members will no longer receive an automatic role"
                    )
                )

            # Bulk role management
            elif action in ["add", "remove"]:
                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I don't have permission to manage that role")

                # Parse user mentions/IDs
                processed = []
                failed = []
                
                for user_id in users.split():
                    try:
                        # Clean up mentions
                        user_id = user_id.strip("<@!>")
                        member = interaction.guild.get_member(int(user_id))
                        
                        if not member:
                            failed.append(user_id)
                            continue
                            
                        success = await self._handle_bulk_role_update(member, role, action)
                        if success:
                            processed.append(member.mention)
                        else:
                            failed.append(member.mention)
                            
                    except ValueError:
                        failed.append(user_id)

                # Build response message
                embed = discord.Embed(
                    title="Role Update Complete",
                    color=discord.Color.green() if processed else discord.Color.red()
                )
                
                if processed:
                    embed.add_field(
                        name="Success",
                        value=f"{'Added' if action == 'add' else 'Removed'} {role.mention} {'to' if action == 'add' else 'from'}:\n" + "\n".join(processed[:10]) + ("..." if len(processed) > 10 else ""),
                        inline=False
                    )
                    
                if failed:
                    embed.add_field(
                        name="Failed",
                        value="Could not process:\n" + "\n".join(failed[:10]) + ("..." if len(failed) > 10 else ""),
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed)

            # Reaction role management
            elif action == "react_bind":
                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I don't have permission to manage that role")

                # Find the message
                try:
                    if channel:
                        message = await channel.fetch_message(int(message_id))
                    else:
                        # Try all channels if none specified
                        message = None
                        for ch in interaction.guild.text_channels:
                            try:
                                message = await ch.fetch_message(int(message_id))
                                if message:
                                    break
                            except:
                                continue
                        
                        if not message:
                            raise ValueError("Message not found")
                except:
                    raise ValueError("Message not found")

                # Add reaction
                try:
                    await message.add_reaction(emoji)
                except:
                    raise ValueError("Invalid emoji")

                # Store binding
                reaction_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'reaction_roles') or {}
                if str(message.id) not in reaction_roles:
                    reaction_roles[str(message.id)] = {}
                reaction_roles[str(message.id)][emoji] = str(role.id)
                
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'reaction_roles', reaction_roles)
                
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Reaction Role Bound",
                        f"Users who react with {emoji} will receive the {role.mention} role"
                    )
                )

            elif action == "react_unbind":
                if not message_id:
                    raise ValueError("Message ID is required")

                reaction_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'reaction_roles') or {}
                
                if str(message_id) in reaction_roles:
                    # Try to remove reactions
                    try:
                        if channel:
                            message = await channel.fetch_message(int(message_id))
                        else:
                            message = None
                            for ch in interaction.guild.text_channels:
                                try:
                                    message = await ch.fetch_message(int(message_id))
                                    if message:
                                        break
                                except:
                                    continue
                        
                        if message:
                            await message.clear_reactions()
                    except:
                        pass  # Message might be deleted

                    del reaction_roles[str(message_id)]
                    await self.bot.db_manager.update_guild_data(interaction.guild_id, 'reaction_roles', reaction_roles)
                    
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Roles Unbound",
                            "All reaction roles have been removed from the message"
                        )
                    )
                else:
                    raise ValueError("No reaction roles found for that message")

            elif action == "react_list":
                reaction_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'reaction_roles') or {}
                
                if not reaction_roles:
                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.info_embed(
                            "Reaction Roles",
                            "No reaction roles have been configured"
                        )
                    )
                    return

                embed = discord.Embed(
                    title="Reaction Roles",
                    color=discord.Color.blue()
                )
                
                for msg_id, bindings in reaction_roles.items():
                    value = []
                    for emoji, role_id in bindings.items():
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            value.append(f"{emoji} → {role.mention}")
                    
                    if value:
                        embed.add_field(
                            name=f"Message: {msg_id}",
                            value="\n".join(value),
                            inline=False
                        )
                
                await interaction.response.send_message(embed=embed)

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
        except commands.CommandError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
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
            config = await self.bot.db_manager.get_auto_role(member.guild.id)
            if not config or not config[1]:  # Not configured or disabled
                return

            role = member.guild.get_role(config[0])
            if not role:
                return

            await member.add_roles(role)

        except Exception as e:
            print(f"Error giving auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle adding roles when users react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            reaction_roles = await self.bot.db_manager.get_section(payload.guild_id, 'reaction_roles') or {}
            
            if str(payload.message_id) in reaction_roles:
                bindings = reaction_roles[str(payload.message_id)]
                emoji = str(payload.emoji)
                
                if emoji in bindings:
                    guild = self.bot.get_guild(payload.guild_id)
                    if not guild:
                        return

                    role = guild.get_role(int(bindings[emoji]))
                    if not role:
                        # Role was deleted - clean up the binding
                        del bindings[emoji]
                        if not bindings:
                            del reaction_roles[str(payload.message_id)]
                        await self.bot.db_manager.update_guild_data(payload.guild_id, 'reaction_roles', reaction_roles)
                        return

                    member = guild.get_member(payload.user_id)
                    if not member:
                        return

                    # Check if we can manage this role
                    if not await self._can_manage_role(guild, role):
                        # Remove the reaction since we can't manage the role
                        channel = guild.get_channel(payload.channel_id)
                        if channel:
                            message = await channel.fetch_message(payload.message_id)
                            if message:
                                await message.remove_reaction(payload.emoji, member)
                        return

                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        # Remove the reaction if we don't have permission
                        channel = guild.get_channel(payload.channel_id)
                        if channel:
                            message = await channel.fetch_message(payload.message_id)
                            if message:
                                await message.remove_reaction(payload.emoji, member)

        except Exception as e:
            print(f"Error handling reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removing roles when users un-react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            reaction_roles = await self.bot.db_manager.get_section(payload.guild_id, 'reaction_roles') or {}
            
            if str(payload.message_id) in reaction_roles:
                bindings = reaction_roles[str(payload.message_id)]
                emoji = str(payload.emoji)
                
                if emoji in bindings:
                    guild = self.bot.get_guild(payload.guild_id)
                    if not guild:
                        return

                    role = guild.get_role(int(bindings[emoji]))
                    if not role:
                        # Role was deleted - clean up the binding
                        del bindings[emoji]
                        if not bindings:
                            del reaction_roles[str(payload.message_id)]
                        await self.bot.db_manager.update_guild_data(payload.guild_id, 'reaction_roles', reaction_roles)
                        return

                    member = guild.get_member(payload.user_id)
                    if not member:
                        return

                    # Check if we can manage this role before trying to remove it
                    if not await self._can_manage_role(guild, role):
                        return

                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        pass  # We already checked permissions, but handle any race conditions

        except Exception as e:
            print(f"Error handling reaction role removal: {e}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot))