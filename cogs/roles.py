import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

class RolesCog(commands.Cog):
    """Handles role-related commands"""
    
    def __init__(self, bot):
        self.bot = bot
        # Set all commands in this cog to "Roles" category
        for cmd in self.__cog_app_commands__:
            cmd.extras["category"] = "roles"

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
            async with await self.bot.db_manager.transaction(member.guild.id, 'color_roles') as txn:
                # Get color roles configuration
                color_config = await self.bot.db_manager.get_section(member.guild.id, 'color_roles')
                if not color_config or not color_config.get('enabled', False):
                    return False
                
                # Get list of color role IDs
                color_role_ids = [r['role_id'] for r in color_config.get('roles', [])]
                
                # Remove existing color roles
                roles_to_remove = []
                for role in member.roles:
                    if str(role.id) in color_role_ids:
                        roles_to_remove.append(role)
                
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Updating color role")
                
                # Add new color role if specified
                if new_role and str(new_role.id) in color_role_ids:
                    await member.add_roles(new_role, reason="Setting new color role")
                
                return True
                
        except Exception as e:
            print(f"Error updating color roles: {e}")
            return False

    async def _get_reaction_roles(self, guild_id: int) -> dict:
        """Get reaction roles configuration with proper parsing"""
        data = await self.bot.db_manager.get_section(guild_id, 'reaction_roles')
        return data if data else {}

    async def _update_reaction_roles(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> bool:
        """Update reaction role configuration"""
        try:
            reaction_roles = await self._get_reaction_roles(guild_id)
            msg_id = str(message_id)
            
            if msg_id not in reaction_roles:
                reaction_roles[msg_id] = {}
            reaction_roles[msg_id][str(emoji)] = str(role_id)
            
            return await self.bot.db_manager.update_section(guild_id, 'reaction_roles', reaction_roles)
        except Exception as e:
            print(f"Error updating reaction roles: {e}")
            return False

    async def _remove_reaction_role(self, guild_id: int, message_id: int, emoji: str = None) -> bool:
        """Remove a reaction role or all roles for a message"""
        try:
            reaction_roles = await self._get_reaction_roles(guild_id)
            msg_id = str(message_id)
            
            if msg_id in reaction_roles:
                if emoji:
                    if str(emoji) in reaction_roles[msg_id]:
                        del reaction_roles[msg_id][str(emoji)]
                    if not reaction_roles[msg_id]:  # If no more roles for this message
                        del reaction_roles[msg_id]
                else:
                    del reaction_roles[msg_id]
                
            return await self.bot.db_manager.update_section(guild_id, 'reaction_roles', reaction_roles)
        except Exception as e:
            print(f"Error removing reaction role: {e}")
            return False

    async def _update_auto_role(self, guild_id: int, role_id: Optional[int]) -> bool:
        """Update auto-role configuration"""
        try:
            config = await self.bot.db_manager.get_section(guild_id, 'server_config') or {}
            config['auto_role'] = str(role_id) if role_id else None
            config['auto_role_enabled'] = role_id is not None
            return await self.bot.db_manager.update_section(guild_id, 'server_config', config)
        except Exception as e:
            print(f"Error updating auto role: {e}")
            return False

    async def _get_auto_role(self, guild_id: int) -> tuple[Optional[int], bool]:
        """Get auto-role configuration"""
        try:
            config = await self.bot.db_manager.get_section(guild_id, 'server_config') or {}
            role_id = config.get('auto_role')
            enabled = config.get('auto_role_enabled', False)
            return (int(role_id) if role_id else None, enabled)
        except Exception as e:
            print(f"Error getting auto role: {e}")
            return (None, False)

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
                
            await self._update_auto_role(interaction.guild_id, role.id)
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

            await self._update_auto_role(interaction.guild_id, None)
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
            color_config = await self.bot.db_manager.get_section(interaction.guild_id, 'color_roles')
            if not color_config or not color_config.get('enabled', False):
                raise ValueError("Color roles are not enabled on this server")
            
            if not any(r['role_id'] == str(role.id) for r in color_config.get('roles', [])):
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
                
            await self._update_reaction_roles(
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

            if not message_id:
                await self.bot.db_manager.update_section(interaction.guild_id, 'reaction_roles', {})
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.success_embed(
                        "Reaction Roles Cleared",
                        "All reaction roles have been removed"
                    )
                )
            else:
                # Remove specific message's reaction roles
                await self._remove_reaction_role(interaction.guild_id, int(message_id))
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

            reaction_roles = await self._get_reaction_roles(interaction.guild_id)
            
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
            auto_role = await self._get_auto_role(member.guild.id)
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
            reaction_roles = await self._get_reaction_roles(payload.guild_id)
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
            reaction_roles = await self._get_reaction_roles(payload.guild_id)
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

class ColorRolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _validate_color(self, color_str: str) -> bool:
        """Validate hex color format"""
        if not color_str.startswith('#'):
            return False
        try:
            int(color_str[1:], 16)
            return len(color_str) == 7
        except ValueError:
            return False

    @app_commands.command(name="color")
    @app_commands.describe(
        action="The action to perform",
        color="Hex color code (e.g., #FF5733)",
        role="Role to add/remove from color roles"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create new color role", value="create"),
        app_commands.Choice(name="Add existing role", value="add"),
        app_commands.Choice(name="Remove color role", value="remove"),
        app_commands.Choice(name="List color roles", value="list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def color_roles(
        self,
        interaction: discord.Interaction,
        action: str,
        color: Optional[str] = None,
        role: Optional[discord.Role] = None
    ):
        """Manage color roles"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            color_config = await self.bot.db_manager.get_section(interaction.guild.id, 'color_roles')
            
            match action:
                case "create":
                    if not color:
                        raise ValueError("You must provide a hex color code")
                    if not await self._validate_color(color):
                        raise ValueError("Invalid hex color format. Use #RRGGBB (e.g., #FF5733)")

                    # Create new role
                    role = await interaction.guild.create_role(
                        name=f"Color-{color[1:]}",
                        color=discord.Color.from_str(color),
                        reason=f"Color role created by {interaction.user}"
                    )

                    # Add to database
                    color_config['roles'].append({
                        'color': color,
                        'role_id': str(role.id)
                    })
                    await self.bot.db_manager.set_section(interaction.guild.id, 'color_roles', color_config)

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Created",
                            f"Created role {role.mention} with color {color}"
                        )
                    )

                case "add":
                    if not role:
                        raise ValueError("You must specify a role to add")

                    # Check if role already exists
                    if any(r['role_id'] == str(role.id) for r in color_config['roles']):
                        raise ValueError(f"{role.mention} is already a color role")

                    # Add to database
                    color_config['roles'].append({
                        'color': f"#{role.color.value:06x}",
                        'role_id': str(role.id)
                    })
                    await self.bot.db_manager.set_section(interaction.guild.id, 'color_roles', color_config)

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Added",
                            f"Added {role.mention} to color roles"
                        )
                    )

                case "remove":
                    if not role:
                        raise ValueError("You must specify a role to remove")

                    # Find and remove role
                    color_config['roles'] = [
                        r for r in color_config['roles']
                        if r['role_id'] != str(role.id)
                    ]
                    await self.bot.db_manager.set_section(interaction.guild.id, 'color_roles', color_config)

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Color Role Removed",
                            f"Removed {role.mention} from color roles"
                        )
                    )

                case "list":
                    if not color_config['roles']:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.info_embed(
                                "Color Roles",
                                "No color roles configured"
                            )
                        )
                        return

                    # Create pages of 10 roles each
                    roles_per_page = 10
                    pages = []
                    
                    for i in range(0, len(color_config['roles']), roles_per_page):
                        page_roles = color_config['roles'][i:i + roles_per_page]
                        embed = discord.Embed(
                            title="Color Roles",
                            color=discord.Color.blue()
                        )
                        
                        for role_data in page_roles:
                            role_id = int(role_data['role_id'])
                            role = interaction.guild.get_role(role_id)
                            if role:
                                embed.add_field(
                                    name=role.name,
                                    value=f"Color: {role_data['color']}\nRole: {role.mention}",
                                    inline=False
                                )
                        
                        pages.append(embed)

                    if len(pages) > 1:
                        await self.bot.ui_manager.paginate(
                            interaction=interaction,
                            pages=pages
                        )
                    else:
                        await interaction.response.send_message(embed=pages[0])

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Manage Roles permission to configure color roles"
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

    @app_commands.command(name="setcolor")
    @app_commands.describe(
        role="The color role to assign"
    )
    async def set_color(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Set your color role"""
        try:
            # Check if role is a color role
            color_config = await self.bot.db_manager.get_section(interaction.guild.id, 'color_roles')
            if not color_config['enabled']:
                raise ValueError("Color roles are disabled on this server")

            if not any(r['role_id'] == str(role.id) for r in color_config['roles']):
                raise ValueError("That is not a valid color role")

            # Remove other color roles
            current_color_roles = [
                interaction.guild.get_role(int(r['role_id']))
                for r in color_config['roles']
                if interaction.guild.get_role(int(r['role_id'])) in interaction.user.roles
            ]

            if current_color_roles:
                await interaction.user.remove_roles(*current_color_roles)

            # Add new color role
            await interaction.user.add_roles(role)

            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Color Updated",
                    f"Set your color to {role.mention}"
                )
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

    @app_commands.command(name="colors")
    async def list_colors(self, interaction: discord.Interaction):
        """List available color roles"""
        try:
            color_config = await self.bot.db_manager.get_section(interaction.guild.id, 'color_roles')
            if not color_config['enabled']:
                raise ValueError("Color roles are disabled on this server")

            if not color_config['roles']:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.info_embed(
                        "Color Roles",
                        "No color roles available"
                    )
                )
                return

            # Create color role preview
            embed = discord.Embed(
                title="Available Colors",
                description="Use `/setcolor` to choose a color",
                color=discord.Color.blue()
            )

            for role_data in color_config['roles']:
                role = interaction.guild.get_role(int(role_data['role_id']))
                if role:
                    embed.add_field(
                        name=role.name,
                        value=f"{role.mention}\nHex: {role_data['color']}",
                        inline=True
                    )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
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

class ReactionRolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _check_message(self, guild_id: int, channel_id: int, message_id: int) -> Optional[discord.Message]:
        """Find and validate a message for reaction roles"""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return None
            return await channel.fetch_message(message_id)
        except:
            return None

    async def _update_reaction_role_message(self, message: discord.Message, emoji: str, action: str):
        """Update reactions on a message"""
        if action == "add":
            await message.add_reaction(emoji)
        else:
            await message.clear_reaction(emoji)

    @app_commands.command(name="reactionrole")
    @app_commands.describe(
        action="The action to perform",
        message_id="The message ID to bind to",
        emoji="The emoji to use",
        role="The role to give",
        channel="The channel containing the message"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add reaction role", value="add"),
        app_commands.Choice(name="Remove reaction role", value="remove"),
        app_commands.Choice(name="List reaction roles", value="list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def reaction_role(
        self,
        interaction: discord.Interaction,
        action: str,
        message_id: Optional[str] = None,
        emoji: Optional[str] = None,
        role: Optional[discord.Role] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Manage reaction roles"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            reaction_config = await self.bot.db_manager.get_section(interaction.guild.id, 'reaction_roles')
            
            match action:
                case "add":
                    if not all([message_id, emoji, role]):
                        raise ValueError("Message ID, emoji, and role are required")

                    # Validate message exists
                    message = await self._check_message(
                        interaction.guild.id,
                        channel.id if channel else interaction.channel.id,
                        int(message_id)
                    )
                    if not message:
                        raise ValueError("Message not found")

                    # Validate emoji
                    try:
                        await message.add_reaction(emoji)
                    except:
                        raise ValueError("Invalid emoji")

                    # Add to database
                    if message_id not in reaction_config:
                        reaction_config[message_id] = {}
                    reaction_config[message_id][emoji] = str(role.id)
                    
                    await self.bot.db_manager.set_section(
                        interaction.guild.id,
                        'reaction_roles',
                        reaction_config
                    )

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Role Added",
                            f"Added {role.mention} role for {emoji} reaction"
                        )
                    )

                case "remove":
                    if not message_id or not emoji:
                        raise ValueError("Message ID and emoji are required")

                    if (message_id not in reaction_config or 
                        emoji not in reaction_config[message_id]):
                        raise ValueError("No reaction role found for that message and emoji")

                    # Remove reaction if possible
                    message = await self._check_message(
                        interaction.guild.id,
                        channel.id if channel else interaction.channel.id,
                        int(message_id)
                    )
                    if message:
                        await self._update_reaction_role_message(message, emoji, "remove")

                    # Remove from database
                    del reaction_config[message_id][emoji]
                    if not reaction_config[message_id]:
                        del reaction_config[message_id]
                    
                    await self.bot.db_manager.set_section(
                        interaction.guild.id,
                        'reaction_roles',
                        reaction_config
                    )

                    await interaction.response.send_message(
                        embed=self.bot.ui_manager.success_embed(
                            "Reaction Role Removed",
                            f"Removed reaction role for {emoji}"
                        )
                    )

                case "list":
                    if not reaction_config:
                        await interaction.response.send_message(
                            embed=self.bot.ui_manager.info_embed(
                                "Reaction Roles",
                                "No reaction roles configured"
                            )
                        )
                        return

                    # Create pages for each message's reaction roles
                    pages = []
                    for msg_id, reactions in reaction_config.items():
                        embed = discord.Embed(
                            title="Reaction Roles",
                            description=f"Message ID: {msg_id}",
                            color=discord.Color.blue()
                        )
                        
                        for emoji, role_id in reactions.items():
                            role = interaction.guild.get_role(int(role_id))
                            embed.add_field(
                                name=emoji,
                                value=role.mention if role else f"Unknown Role ({role_id})",
                                inline=True
                            )
                        
                        pages.append(embed)

                    if len(pages) > 1:
                        await self.bot.ui_manager.paginate(
                            interaction=interaction,
                            pages=pages
                        )
                    else:
                        await interaction.response.send_message(embed=pages[0])

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Manage Roles permission to configure reaction roles"
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
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role assignments"""
        if payload.member.bot:
            return

        try:
            reaction_config = await self.bot.db_manager.get_section(payload.guild_id, 'reaction_roles')
            msg_reactions = reaction_config.get(str(payload.message_id))
            
            if msg_reactions:
                role_id = msg_reactions.get(str(payload.emoji))
                if role_id:
                    role = payload.member.guild.get_role(int(role_id))
                    if role:
                        await payload.member.add_roles(role)
        except Exception as e:
            print(f"Error in reaction role add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role removals"""
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return

            reaction_config = await self.bot.db_manager.get_section(payload.guild_id, 'reaction_roles')
            msg_reactions = reaction_config.get(str(payload.message_id))
            
            if msg_reactions:
                role_id = msg_reactions.get(str(payload.emoji))
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role and role in member.roles:
                        await member.remove_roles(role)
        except Exception as e:
            print(f"Error in reaction role remove: {e}")

async def setup(bot):
    await bot.add_cog(ColorRolesCog(bot))
    await bot.add_cog(ReactionRolesCog(bot))