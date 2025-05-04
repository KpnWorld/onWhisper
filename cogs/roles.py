import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _can_manage_role(self, guild: discord.Guild, role: discord.Role) -> bool:
        """Check if the bot can manage a role"""
        if not guild.me.guild_permissions.manage_roles:
            return False
        if role >= guild.me.top_role:
            return False
        return True

    async def _handle_bulk_role_update(self, member: discord.Member, role: discord.Role, action: str) -> bool:
        """Helper method to handle role updates for a single member
        Returns True if successful, False if failed"""
        try:
            if action == "add":
                if role not in member.roles:
                    await member.add_roles(role, reason="Bulk role addition")
            else:  # remove
                if role in member.roles:
                    await member.remove_roles(role, reason="Bulk role removal")
            return True
        except Exception:
            return False

    @app_commands.command(
        name="roles",
        description="Manage server roles"
    )
    @app_commands.describe(
        action="The action to perform",
        role="The role to manage (required for most actions)",
        users="Users to update (required for bulk actions)",
        message_id="Message ID for reaction roles",
        emoji="Emoji for reaction roles",
        channel="Channel for auto-role message (optional)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set auto-role", value="auto_set"),
        app_commands.Choice(name="Disable auto-role", value="auto_disable"),
        app_commands.Choice(name="Bulk add role", value="bulk_add"),
        app_commands.Choice(name="Bulk remove role", value="bulk_remove"),
        app_commands.Choice(name="Bind reaction role", value="react_bind"),
        app_commands.Choice(name="Unbind reaction roles", value="react_unbind"),
        app_commands.Choice(name="List reaction roles", value="react_list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def roles(
        self,
        interaction: discord.Interaction,
        action: str,
        role: Optional[discord.Role] = None,
        users: Optional[str] = None,
        message_id: Optional[str] = None,
        emoji: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Unified role management command"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if action in ["auto_set", "bulk_add", "bulk_remove", "react_bind"] and not role:
                raise ValueError("Role is required for this action")

            if action in ["bulk_add", "bulk_remove"] and not users:
                raise ValueError("Users parameter is required for bulk actions")

            if action == "react_bind" and (not message_id or not emoji):
                raise ValueError("Message ID and emoji are required for reaction role binding")

            # Auto-role actions
            if action == "auto_set":
                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I cannot manage this role")

                await self.bot.db_manager.update_auto_role(interaction.guild_id, role.id)
                embed = self.bot.ui_manager.success_embed(
                    "Auto-Role Enabled",
                    f"New members will automatically receive the {role.mention} role"
                )

            elif action == "auto_disable":
                await self.bot.db_manager.update_auto_role(interaction.guild_id, None)
                embed = self.bot.ui_manager.success_embed(
                    "Auto-Role Disabled",
                    "New members will no longer automatically receive a role"
                )

            # Bulk role actions
            elif action in ["bulk_add", "bulk_remove"]:
                await interaction.response.defer()

                if not await self._can_manage_role(interaction.guild, role):
                    raise commands.CommandError("I cannot manage this role")

                # Handle @everyone case
                if users.lower() == "@everyone":
                    members = interaction.guild.members
                    user_ids = [member.id for member in members if not member.bot]
                else:
                    # Parse user IDs/mentions
                    user_ids = []
                    for word in users.split():
                        if word.startswith('<@') and word.endswith('>'):
                            user_id = ''.join(filter(str.isdigit, word))
                            if user_id:
                                user_ids.append(int(user_id))
                        elif word.isdigit():
                            user_ids.append(int(word))

                if not user_ids:
                    raise ValueError("No valid user IDs or mentions found")

                # Add confirmation for @everyone
                if users.lower() == "@everyone":
                    confirmed = await self.bot.ui_manager.confirm_action(
                        interaction,
                        "Confirm Bulk Role Update",
                        f"Are you sure you want to {'add' if action == 'bulk_add' else 'remove'} the role {role.mention} {'to' if action == 'bulk_add' else 'from'} ALL members ({len(user_ids)} users)?",
                        confirm_label="Confirm",
                        cancel_label="Cancel"
                    )
                    if not confirmed:
                        await interaction.followup.send(
                            embed=self.bot.ui_manager.info_embed(
                                "Cancelled",
                                "Bulk role update cancelled."
                            ),
                            ephemeral=True
                        )
                        return

                success = []
                failed = []

                # Process users with progress updates
                total = len(user_ids)
                for i, user_id in enumerate(user_ids, 1):
                    member = interaction.guild.get_member(user_id)
                    if member:
                        try:
                            if action == "bulk_add":
                                if role not in member.roles:
                                    await member.add_roles(role, reason=f"Bulk role addition by {interaction.user}")
                            else:
                                if role in member.roles:
                                    await member.remove_roles(role, reason=f"Bulk role removal by {interaction.user}")
                            success.append(str(member))
                        except:
                            failed.append(str(member))

                    if i % 10 == 0 or i == total:
                        progress = i / total * 100
                        await interaction.followup.send(
                            embed=self.bot.ui_manager.info_embed(
                                "Progress",
                                f"Processing... {i}/{total} users ({progress:.1f}%)"
                            ),
                            ephemeral=True
                        )

                # Final results
                embed = self.bot.ui_manager.success_embed(
                    "Bulk Role Update Complete",
                    f"Role {'added to' if action == 'bulk_add' else 'removed from'} {len(success)} users"
                )
                if success:
                    embed.add_field(
                        name="Successful",
                        value=", ".join(success[:10]) + ("..." if len(success) > 10 else ""),
                        inline=False
                    )
                if failed:
                    embed.add_field(
                        name="Failed",
                        value=", ".join(failed[:10]) + ("..." if len(failed) > 10 else ""),
                        inline=False
                    )

            # Reaction role actions
            elif action == "react_bind":
                try:
                    message = await interaction.channel.fetch_message(int(message_id))
                except:
                    raise commands.CommandError("Could not find message with that ID in this channel")

                try:
                    await message.add_reaction(emoji)
                except:
                    raise commands.CommandError("Invalid emoji or I cannot add reactions to that message")

                await interaction.response.defer()

                try:
                    await self.bot.db_manager.add_reaction_role(
                        interaction.guild_id,
                        int(message_id),
                        emoji,
                        role.id
                    )

                    embed = self.bot.ui_manager.success_embed(
                        "Reaction Role Created",
                        f"Users can now get the {role.mention} role by reacting with {emoji} to [this message]({message.jump_url})"
                    )

                except Exception as e:
                    try:
                        await message.remove_reaction(emoji, interaction.guild.me)
                    except:
                        pass
                    raise commands.CommandError(f"Failed to create reaction role: {str(e)}")

            elif action == "react_unbind":
                if not message_id:
                    raise ValueError("Message ID is required for unbinding reaction roles")

                removed = await self.bot.db_manager.remove_reaction_roles(interaction.guild_id, message_id)

                if removed:
                    try:
                        message = await interaction.channel.fetch_message(int(message_id))
                        await message.clear_reactions()
                    except:
                        pass

                    embed = self.bot.ui_manager.success_embed(
                        "Bindings Removed",
                        f"Removed all reaction role bindings from message ID: {message_id}"
                    )
                else:
                    embed = self.bot.ui_manager.error_embed(
                        "No Bindings Found",
                        f"No reaction role bindings found for message ID: {message_id}"
                    )

            elif action == "react_list":
                reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)
                
                if not reaction_roles:
                    embed = self.bot.ui_manager.info_embed(
                        "No Reaction Roles",
                        "No reaction role bindings found in this server"
                    )
                else:
                    embed = self.bot.ui_manager.info_embed(
                        "Reaction Role Bindings",
                        "Current reaction role configuration:"
                    )
                    
                    for message_id, bindings in reaction_roles.items():
                        value = []
                        for emoji, role_id in bindings.items():
                            role = interaction.guild.get_role(int(role_id))
                            if role:
                                value.append(f"{emoji} → {role.mention}")
                        
                        if value:
                            try:
                                channel = next(
                                    channel for channel in interaction.guild.channels 
                                    if isinstance(channel, discord.TextChannel) 
                                    and any(message.id == int(message_id) for message in await channel.history(limit=1).flatten())
                                )
                                message_link = f"[Message]({channel.get_partial_message(int(message_id)).jump_url})"
                            except:
                                message_link = f"Message ID: {message_id}"
                            
                            embed.add_field(
                                name=message_link,
                                value="\n".join(value),
                                inline=False
                            )

            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)

        except ValueError as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                    ephemeral=True
                )
        except commands.MissingPermissions:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Permissions",
                        "You need the Manage Roles permission to use this command."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Permissions",
                        "You need the Manage Roles permission to use this command."
                    ),
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
            role_id, enabled = await self.bot.db_manager.get_auto_role(member.guild.id)
            if role_id and enabled:
                role = member.guild.get_role(int(role_id))
                if role and await self._can_manage_role(member.guild, role):
                    await member.add_roles(role)
        except Exception as e:
            print(f"Auto-role error: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle adding roles when users react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role data
            reaction_roles = await self.bot.db_manager.get_reaction_roles(
                payload.guild_id,
                str(payload.message_id)
            )
            if not reaction_roles:
                return

            # Check if this reaction is for a role
            role_id = reaction_roles.get(str(payload.emoji))
            if not role_id:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            role = guild.get_role(int(role_id))
            if not role or not await self._can_manage_role(guild, role):
                return

            member = guild.get_member(payload.user_id)
            if member:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    print(f"Missing permissions to add role {role.id} to member {member.id}")
                except Exception as e:
                    print(f"Error adding reaction role: {e}")

        except Exception as e:
            print(f"Reaction role error: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removing roles when users un-react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role data
            reaction_roles = await self.bot.db_manager.get_reaction_roles(
                payload.guild_id,
                str(payload.message_id)
            )
            if not reaction_roles:
                return

            # Check if this reaction is for a role
            role_id = reaction_roles.get(str(payload.emoji))
            if not role_id:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            role = guild.get_role(int(role_id))
            if not role or not await self._can_manage_role(guild, role):
                return

            member = guild.get_member(payload.user_id)
            if member:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    print(f"Missing permissions to remove role {role.id} from member {member.id}")
                except Exception as e:
                    print(f"Error removing reaction role: {e}")

        except Exception as e:
            print(f"Reaction role error: {e}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot))