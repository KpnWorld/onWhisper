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
        return (
            bot_member.guild_permissions.manage_roles and 
            bot_member.top_role > role and 
            not role.managed
        )

    async def _handle_bulk_role_update(self, member: discord.Member, role: discord.Role, action: str) -> bool:
        """Handle adding/removing roles with proper error handling"""
        try:
            if action == "add":
                await member.add_roles(role)
            else:
                await member.remove_roles(role)
            return True
        except:
            return False

    async def _update_user_color_role(self, member: discord.Member, new_role: Optional[discord.Role] = None) -> bool:
        """Update a user's color role, removing any existing ones"""
        try:
            color_roles = await self.bot.db_manager.get_color_roles(member.guild.id)
            
            # Remove existing color roles
            for role in member.roles:
                if str(role.id) in color_roles:
                    await member.remove_roles(role)
            
            # Add new color role if specified
            if new_role:
                await member.add_roles(new_role)
            
            return True
        except:
            return False

    # Main roles group
    roles = app_commands.Group(
        name="roles",
        description="Manage server roles",
        default_permissions=discord.Permissions(manage_roles=True)
    )

    # Auto-role subgroup
    auto = app_commands.Group(
        name="auto",
        description="Configure automatic roles",
        parent=roles
    )

    @auto.command(name="set")
    @app_commands.describe(role="The role to give new members automatically")
    async def auto_set(self, interaction: discord.Interaction, role: discord.Role):
        """Set the automatic role for new members"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if not await self._can_manage_role(interaction.guild, role):
                raise commands.CommandError("I cannot manage that role")
                
            await self.bot.db_manager.update_auto_role(interaction.guild_id, role.id)
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Auto-Role Set",
                    f"New members will automatically receive the {role.mention} role"
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to configure auto-roles"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @auto.command(name="disable")
    async def auto_disable(self, interaction: discord.Interaction):
        """Disable the automatic role"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            await self.bot.db_manager.update_auto_role(interaction.guild_id, None)
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Auto-Role Disabled",
                    "New members will no longer receive an automatic role"
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to configure auto-roles"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    # Color role subgroup
    color = app_commands.Group(
        name="color",
        description="Manage color roles",
        parent=roles
    )

    @color.command(name="set")
    @app_commands.describe(role="The color role to set")
    async def color_set(self, interaction: discord.Interaction, role: discord.Role):
        """Set your color role"""
        try:
            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
            
            if str(role.id) not in color_roles:
                raise ValueError("That role is not configured as a color role")
                
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

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Invalid Color Role",
                    str(e)
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @color.command(name="clear")
    async def color_clear(self, interaction: discord.Interaction):
        """Clear your color role"""
        try:
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

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    # Reaction role subgroup
    reaction = app_commands.Group(
        name="reaction",
        description="Manage reaction roles",
        parent=roles
    )

    @reaction.command(name="bind")
    @app_commands.describe(
        message_id="The ID of the message to bind to",
        emoji="The emoji to react with",
        role="The role to give when reacting",
        channel="The channel containing the message (optional)"
    )
    async def reaction_bind(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
        channel: Optional[discord.TextChannel] = None
    ):
        """Create a reaction role binding"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            target_message = None
            channels = [channel] if channel else interaction.guild.text_channels
            
            for chan in channels:
                try:
                    target_message = await chan.fetch_message(int(message_id))
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
                    "Reaction Role Added",
                    f"Users who react with {emoji} will receive the {role.mention} role"
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to configure reaction roles"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @reaction.command(name="unbind")
    @app_commands.describe(message_id="The message ID to remove reaction roles from (leave empty to remove all)")
    async def reaction_unbind(
        self,
        interaction: discord.Interaction,
        message_id: Optional[str] = None
    ):
        """Remove reaction role bindings"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)

            if not message_id:
                await self.bot.db_manager.update_guild_data(interaction.guild_id, 'reaction_roles', {})
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Reaction Roles Cleared",
                        "All reaction roles have been removed"
                    )
                )
            else:
                # Remove specific message's reaction roles
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

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to configure reaction roles"
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @reaction.command(name="list")
    async def reaction_list(self, interaction: discord.Interaction):
        """List all reaction role bindings"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)
            
            if reaction_roles:
                description = []
                for message_id, bindings in reaction_roles.items():
                    description.append(f"Message: {message_id}")
                    for emoji, role_id in bindings.items():
                        role = interaction.guild.get_role(int(role_id))
                        description.append(f"- {emoji} → {role.mention if role else f'Unknown Role ({role_id})'}")
                    description.append("")
                
                embed = self.bot.ui_manager.info_embed(
                    "Reaction Roles",
                    "\n".join(description)
                )
                await interaction.response.send_message(embed=embed)
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
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    # Bulk role management subgroup
    bulk = app_commands.Group(
        name="bulk",
        description="Bulk role management",
        parent=roles
    )

    @bulk.command(name="add")
    @app_commands.describe(
        role="The role to add",
        users="Space-separated list of user mentions or IDs"
    )
    async def bulk_add(self, interaction: discord.Interaction, role: discord.Role, users: str):
        """Add a role to multiple users"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if not await self._can_manage_role(interaction.guild, role):
                raise commands.CommandError("I cannot manage that role")

            # Parse user IDs/mentions
            user_ids = [
                ''.join(filter(str.isdigit, user))
                for user in users.split()
            ]

            if not user_ids:
                raise ValueError("No valid users specified")

            # Start processing
            await interaction.response.defer()
            
            success = []
            failed = []
            
            for user_id in user_ids:
                try:
                    member = await interaction.guild.fetch_member(int(user_id))
                    if member:
                        if await self._handle_bulk_role_update(member, role, "add"):
                            success.append(member.mention)
                        else:
                            failed.append(member.mention)
                except:
                    failed.append(f"<@{user_id}>")

            # Build response message
            description = []
            if success:
                description.append(f"✅ Successfully added to: {', '.join(success)}")
            if failed:
                description.append(f"❌ Failed to add to: {', '.join(failed)}")

            await interaction.followup.send(
                embed=self.bot.ui_manager.info_embed(
                    f"Bulk Role Add: {role.name}",
                    "\n".join(description)
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission for bulk role management"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )

    @bulk.command(name="remove")
    @app_commands.describe(
        role="The role to remove",
        users="Space-separated list of user mentions or IDs"
    )
    async def bulk_remove(self, interaction: discord.Interaction, role: discord.Role, users: str):
        """Remove a role from multiple users"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if not await self._can_manage_role(interaction.guild, role):
                raise commands.CommandError("I cannot manage that role")

            # Parse user IDs/mentions
            user_ids = [
                ''.join(filter(str.isdigit, user))
                for user in users.split()
            ]

            if not user_ids:
                raise ValueError("No valid users specified")

            # Start processing
            await interaction.response.defer()
            
            success = []
            failed = []
            
            for user_id in user_ids:
                try:
                    member = await interaction.guild.fetch_member(int(user_id))
                    if member:
                        if await self._handle_bulk_role_update(member, role, "remove"):
                            success.append(member.mention)
                        else:
                            failed.append(member.mention)
                except:
                    failed.append(f"<@{user_id}>")

            # Build response message
            description = []
            if success:
                description.append(f"✅ Successfully removed from: {', '.join(success)}")
            if failed:
                description.append(f"❌ Failed to remove from: {', '.join(failed)}")

            await interaction.followup.send(
                embed=self.bot.ui_manager.info_embed(
                    f"Bulk Role Remove: {role.name}",
                    "\n".join(description)
                )
            )

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission for bulk role management"
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed("Error", str(e)),
                    ephemeral=True
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle giving auto-role to new members"""
        try:
            auto_role = await self.bot.db_manager.get_auto_role(member.guild.id)
            if auto_role[1] and auto_role[0]:  # If enabled and role is set
                role = member.guild.get_role(auto_role[0])
                if role and await self._can_manage_role(member.guild, role):
                    await member.add_roles(role)
        except Exception as e:
            print(f"Error giving auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle adding roles when users react"""
        try:
            # Ignore reactions from bots
            if payload.member.bot:
                return
                
            # Get reaction role config
            reaction_roles = await self.bot.db_manager.get_reaction_roles(payload.guild_id)
            if not reaction_roles:
                return
                
            # Check if message has reaction roles
            message_roles = reaction_roles.get(str(payload.message_id))
            if not message_roles:
                return
                
            # Check if emoji is configured
            role_id = message_roles.get(str(payload.emoji))
            if not role_id:
                return
                
            # Get role and add to member
            role = payload.member.guild.get_role(int(role_id))
            if role and await self._can_manage_role(payload.member.guild, role):
                await payload.member.add_roles(role)
                
        except Exception as e:
            print(f"Error handling reaction add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removing roles when users un-react"""
        try:
            # Get guild and member
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
                
            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return
                
            # Get reaction role config
            reaction_roles = await self.bot.db_manager.get_reaction_roles(payload.guild_id)
            if not reaction_roles:
                return
                
            # Check if message has reaction roles
            message_roles = reaction_roles.get(str(payload.message_id))
            if not message_roles:
                return
                
            # Check if emoji is configured
            role_id = message_roles.get(str(payload.emoji))
            if not role_id:
                return
                
            # Get role and remove from member
            role = guild.get_role(int(role_id))
            if role and await self._can_manage_role(guild, role):
                await member.remove_roles(role)
                
        except Exception as e:
            print(f"Error handling reaction remove: {e}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot))