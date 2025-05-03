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
        name="roles_auto_set",
        description="Enable auto-role for new members"
    )
    @app_commands.describe(
        role="The role to give to new members"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def roles_auto_set(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Enable auto-role for new members"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            # Validate role hierarchy
            if role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot manage this role as it's higher than my highest role")

            # Update auto-role setting
            await self.bot.db_manager.update_auto_role(interaction.guild_id, str(role.id))

            embed = self.bot.ui_manager.success_embed(
                "Auto-Role Enabled",
                f"New members will automatically receive the {role.mention} role"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="roles_auto_remove",
        description="Disable auto-role for new members"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def roles_auto_remove(self, interaction: discord.Interaction):
        """Disable auto-role"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            # Remove auto-role setting
            await self.bot.db_manager.update_auto_role(interaction.guild_id, None)

            embed = self.bot.ui_manager.success_embed(
                "Auto-Role Disabled",
                "New members will no longer automatically receive a role"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="roles_react_bind",
        description="Create a reaction role binding"
    )
    @app_commands.describe(
        message_id="The ID of the message to bind to",
        emoji="The emoji to react with",
        role="The role to give when reacting"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def roles_react_bind(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role
    ):
        """Create an emoji-role binding"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot manage this role as it's higher than my highest role")

            # Try to find the message first
            try:
                message = await interaction.channel.fetch_message(int(message_id))
            except:
                raise commands.CommandError("Could not find message with that ID in this channel")

            # Verify the emoji by trying to add it
            try:
                await message.add_reaction(emoji)
            except:
                raise commands.CommandError("Invalid emoji or I cannot add reactions to that message")

            # Let the user know we're processing
            await interaction.response.defer()

            # Store the reaction role binding
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
                await interaction.followup.send(embed=embed)

            except Exception as e:
                # Clean up the reaction if database update failed
                try:
                    await message.remove_reaction(emoji, interaction.guild.me)
                except:
                    pass
                raise commands.CommandError(f"Failed to create reaction role: {str(e)}")

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to use this command"
                ),
                ephemeral=True
            )
        except commands.CommandError as e:
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

    @app_commands.command(
        name="roles_react_unbind",
        description="Remove all reaction role bindings from a message"
    )
    @app_commands.describe(
        message_id="The ID of the message to unbind"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def roles_react_unbind(
        self,
        interaction: discord.Interaction,
        message_id: str
    ):
        """Remove reaction role bindings"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            # Remove bindings
            removed = await self.bot.db_manager.remove_reaction_roles(interaction.guild_id, message_id)
            
            if removed:
                # Try to clear reactions from message
                try:
                    message = await interaction.channel.fetch_message(int(message_id))
                    await message.clear_reactions()
                except:
                    pass  # Message might be deleted or inaccessible

                embed = self.bot.ui_manager.success_embed(
                    "Bindings Removed",
                    f"Removed all reaction role bindings from message ID: {message_id}"
                )
            else:
                embed = self.bot.ui_manager.error_embed(
                    "No Bindings Found",
                    f"No reaction role bindings found for message ID: {message_id}"
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="roles_bulk",
        description="Add or remove a role from multiple users"
    )
    @app_commands.describe(
        action="Whether to add or remove the role",
        role="The role to add/remove",
        users="Users to update (space-separated) or '@everyone' for all members"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add role", value="add"),
        app_commands.Choice(name="Remove role", value="remove")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def roles_bulk(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role,
        users: str
    ):
        """Bulk add/remove roles"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Permissions",
                        "You need the Manage Roles permission to use this command."
                    ),
                    ephemeral=True
                )
                return

            if not interaction.guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Missing Permissions",
                        "I need the Manage Roles permission to execute this command."
                    ),
                    ephemeral=True
                )
                return

            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Invalid Role",
                        "I cannot manage this role as it's higher than my highest role"
                    ),
                    ephemeral=True
                )
                return

            # Handle @everyone case
            if users.lower() == "@everyone":
                members = interaction.guild.members
                user_ids = [member.id for member in members if not member.bot]
            else:
                # Parse user IDs/mentions
                user_ids = []
                for word in users.split():
                    if word.isdigit():
                        user_ids.append(int(word))
                    elif word.startswith('<@') and word.endswith('>'):
                        user_id = ''.join(filter(str.isdigit, word))
                        if user_id:
                            user_ids.append(int(user_id))

            if not user_ids:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "Invalid Input",
                        "No valid user IDs or mentions found"
                    ),
                    ephemeral=True
                )
                return

            # Defer the response before confirmation
            await interaction.response.defer()

            # Add confirmation for @everyone
            if users.lower() == "@everyone":
                confirmed = await self.bot.ui_manager.confirm_action(
                    interaction,
                    "Confirm Bulk Role Update",
                    f"Are you sure you want to {action} the role {role.mention} {'to' if action == 'add' else 'from'} ALL members ({len(user_ids)} users)?",
                    confirm_label="Confirm",
                    cancel_label="Cancel"
                )
                if not confirmed:
                    await interaction.followup.send(
                        embed=self.bot.ui_manager.info_embed(
                            "Action Cancelled",
                            "Bulk role update was cancelled."
                        ),
                        ephemeral=True
                    )
                    return

            total_users = len(user_ids)
            success = []
            failed = []
            last_update = 0
            update_interval = max(1, min(10, total_users // 10))

            # Create initial progress message
            progress_embed = self.bot.ui_manager.info_embed(
                "Role Update in Progress",
                f"Starting role {'assignment' if action == 'add' else 'removal'}...\n" +
                f"Progress: 0/{total_users} users processed (0%)"
            )
            progress_message = await interaction.followup.send(embed=progress_embed)

            # Process users
            for i, user_id in enumerate(user_ids, 1):
                member = interaction.guild.get_member(user_id)
                if member:
                    if await self._handle_bulk_role_update(member, role, action):
                        success.append(member.mention)
                    else:
                        failed.append(member.mention)

                if i - last_update >= update_interval:
                    progress_percent = (i / total_users) * 100
                    progress_embed = self.bot.ui_manager.info_embed(
                        "Role Update in Progress",
                        f"{'Adding' if action == 'add' else 'Removing'} role {role.mention}...\n" +
                        f"Progress: {i}/{total_users} users processed ({progress_percent:.1f}%)\n" +
                        f"Success: {len(success)} | Failed: {len(failed)}"
                    )
                    await progress_message.edit(embed=progress_embed)
                    last_update = i

            # Create final result embed
            embed = self.bot.ui_manager.success_embed(
                "Bulk Role Update Complete",
                f"Role {'added to' if action == 'add' else 'removed from'} {len(success)} users"
            )

            if success:
                if users.lower() == "@everyone":
                    embed.add_field(
                        name="Successful",
                        value=f"Updated {len(success)} members successfully",
                        inline=False
                    )
                else:
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

            await progress_message.edit(embed=embed)

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