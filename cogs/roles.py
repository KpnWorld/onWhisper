import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="reaction_role",
        description="Create a reaction role message"
    )
    @app_commands.describe(
        role="The role to give",
        emoji="The emoji to react with",
        description="Description for the role"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def reaction_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        emoji: str,
        description: str
    ):
        """Create a reaction role message"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot manage this role as it is above my highest role.")

            # Create embed for reaction role
            embed = discord.Embed(
                title="Role Selection",
                description=f"React with {emoji} to get the {role.mention} role\n\n**Role Description:**\n{description}",
                color=role.color
            )
            embed.set_footer(text=f"Role ID: {role.id}")

            # Send message and add reaction
            msg = await interaction.channel.send(embed=embed)
            await msg.add_reaction(emoji)

            # Store in database
            await self.bot.db_manager.update_reaction_roles(
                interaction.guild_id,
                msg.id,
                emoji,
                role.id
            )

            # Respond to interaction
            await interaction.response.send_message(
                embed=self.bot.ui_manager.success_embed(
                    "Reaction Role Created",
                    f"Users can now get the {role.mention} role by reacting with {emoji}"
                ),
                ephemeral=True
            )

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle adding roles when users react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role data
            reaction_roles = await self.bot.db_manager.get_reaction_roles(payload.guild_id, payload.message_id)
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
            member = guild.get_member(payload.user_id)
            if not role or not member:
                return

            # Add role
            try:
                await member.add_roles(
                    role,
                    reason="Reaction role"
                )
            except discord.Forbidden:
                # Remove reaction if we can't add the role
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    message = await channel.fetch_message(payload.message_id)
                    await message.remove_reaction(payload.emoji, member)

        except Exception as e:
            print(f"Error in reaction role add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle removing roles when users un-react"""
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Get reaction role data
            reaction_roles = await self.bot.db_manager.get_reaction_roles(payload.guild_id, payload.message_id)
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
            member = guild.get_member(payload.user_id)
            if not role or not member:
                return

            # Remove role
            try:
                await member.remove_roles(
                    role,
                    reason="Reaction role removed"
                )
            except discord.Forbidden:
                pass

        except Exception as e:
            print(f"Error in reaction role remove: {e}")

    @app_commands.command(
        name="autorole",
        description="Configure automatic role on join"
    )
    @app_commands.describe(
        role="The role to give new members (leave empty to disable)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def autorole(
        self,
        interaction: discord.Interaction,
        role: Optional[discord.Role] = None
    ):
        """Configure auto-role for new members"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if role and role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot manage this role as it is above my highest role.")

            # Update auto-role
            await self.bot.db_manager.update_auto_role(
                interaction.guild_id,
                role.id if role else None
            )

            if role:
                embed = self.bot.ui_manager.success_embed(
                    "Auto-Role Updated",
                    f"New members will automatically receive the {role.mention} role"
                )
            else:
                embed = self.bot.ui_manager.success_embed(
                    "Auto-Role Disabled",
                    "New members will no longer receive an automatic role"
                )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle giving auto-role to new members"""
        try:
            # Get auto-role settings
            role_id, enabled = await self.bot.db_manager.get_auto_role(member.guild.id)
            if not enabled or not role_id:
                return

            role = member.guild.get_role(role_id)
            if not role:
                return

            await member.add_roles(
                role,
                reason="Auto-role on join"
            )

        except Exception as e:
            print(f"Error in auto-role: {e}")

    @app_commands.command(
        name="bulk_role",
        description="Add or remove a role from multiple users"
    )
    @app_commands.describe(
        role="The role to add/remove",
        action="Whether to add or remove the role",
        has_role="Filter users who have this role",
        missing_role="Filter users who don't have this role"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add role", value="add"),
        app_commands.Choice(name="Remove role", value="remove")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def bulk_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        action: str,
        has_role: Optional[discord.Role] = None,
        missing_role: Optional[discord.Role] = None
    ):
        """Bulk add/remove roles with filters"""
        try:
            if not interaction.user.guild_permissions.manage_roles:
                raise commands.MissingPermissions(["manage_roles"])

            if role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot manage this role as it is above my highest role.")

            await interaction.response.defer()

            # Filter members
            members = []
            async for member in interaction.guild.fetch_members():
                if member.bot:
                    continue
                    
                if has_role and has_role not in member.roles:
                    continue
                    
                if missing_role and missing_role in member.roles:
                    continue
                    
                members.append(member)

            if not members:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed(
                        "No Members Found",
                        "No members match the specified criteria."
                    )
                )
                return

            # Confirm action
            confirmed = await self.bot.ui_manager.confirm_action(
                interaction,
                "Confirm Bulk Role Update",
                f"This will {action} the {role.mention} role for {len(members)} members. Continue?",
                confirm_label="Continue",
                cancel_label="Cancel"
            )

            if not confirmed:
                return

            # Perform updates
            success = 0
            failed = 0
            
            for member in members:
                try:
                    if action == "add":
                        await member.add_roles(role, reason=f"Bulk role add by {interaction.user}")
                    else:
                        await member.remove_roles(role, reason=f"Bulk role remove by {interaction.user}")
                    success += 1
                except:
                    failed += 1

            # Log the bulk update
            await self.bot.db_manager.bulk_role_update(
                interaction.guild_id,
                role.id,
                [m.id for m in members],
                action
            )

            embed = self.bot.ui_manager.success_embed(
                "Bulk Role Update Complete",
                f"Successfully {action}ed {role.mention} for {success} members.\n"
                f"Failed: {failed}"
            )

            await interaction.followup.send(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Roles permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(RolesCog(bot))