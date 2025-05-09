import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional, List
from datetime import datetime

class RolesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._reaction_cache = {}

    roles_group = app_commands.Group(
        name="roles",
        description="Manage server roles"
    )

    @roles_group.command(name="auto")
    @app_commands.describe(
        action="Whether to set or disable auto-role",
        role="The role to set as auto-role"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="set", value="set"),
        app_commands.Choice(name="disable", value="disable")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def auto_role(
        self,
        interaction: discord.Interaction,
        action: Literal["set", "disable"],
        role: Optional[discord.Role] = None
    ):
        """Configure automatic role assignment for new members"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if action == "set":
                if not role:
                    return await interaction.response.send_message(
                        "⚠️ Please provide a role to set as auto-role.",
                        ephemeral=True
                    )

                if role >= interaction.guild.me.top_role:
                    return await interaction.response.send_message(
                        "❌ I cannot manage this role as it is above my highest role.",
                        ephemeral=True
                    )

                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"auto_role_id": role.id}
                )
                await interaction.response.send_message(
                    f"✅ Set {role.mention} as the auto-role for new members.",
                    ephemeral=True
                )

            else:  # disable
                await self.bot.db_manager.update_guild_config(
                    interaction.guild_id,
                    {"auto_role_id": None}
                )
                await interaction.response.send_message(
                    "✅ Disabled auto-role for new members.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True            )

    @roles_group.command(name="color")
    @app_commands.describe(
        role="The color role to set (leave empty to clear)"
    )
    async def set_color_role(
        self,
        interaction: discord.Interaction,
        role: Optional[discord.Role] = None
    ):
        """Set or clear your color role"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            await interaction.response.defer(ephemeral=True)
            
            # Clear current color role if any
            current = await self.bot.db_manager.get_user_color_role(
                interaction.guild_id,
                interaction.user.id
            )
            if current:
                current_role = interaction.guild.get_role(current)
                if current_role:
                    try:
                        await interaction.user.remove_roles(current_role)
                    except discord.Forbidden:
                        await interaction.followup.send(
                            f"⚠️ Unable to remove previous color role {current_role.mention} - missing permissions.",
                            ephemeral=True
                        )
                        return
                    except discord.HTTPException as e:
                        await interaction.followup.send(
                            f"⚠️ Failed to remove previous color role {current_role.mention}: {str(e)}",
                            ephemeral=True
                        )
                        return

            # Clear color role
            if not role:
                await self.bot.db_manager.set_user_color_role(
                    interaction.guild_id,
                    interaction.user.id,
                    None
                )
                await interaction.followup.send(
                    "✅ Cleared your color role.",
                    ephemeral=True
                )
                return

            # Verify role is a valid color role
            color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
            if role.id not in color_roles:
                await interaction.followup.send(
                    "❌ This role is not available as a color role.",
                    ephemeral=True
                )
                return

            # Check permissions
            if role >= interaction.guild.me.top_role:
                await interaction.followup.send(
                    "❌ I cannot manage this role as it is above my highest role.",
                    ephemeral=True
                )
                return

            # Check if role has a color
            if not role.color:
                await interaction.followup.send(
                    "❌ This role doesn't have a color set.",
                    ephemeral=True
                )
                return

            # Set new color role
            try:
                await interaction.user.add_roles(role)
                await self.bot.db_manager.set_user_color_role(
                    interaction.guild_id,
                    interaction.user.id,
                    role.id
                )
                await interaction.followup.send(
                    f"✅ Set your color to {role.mention}",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I don't have permission to manage that role.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                await interaction.followup.send(
                    f"❌ Failed to set color role: {str(e)}",
                    ephemeral=True
                )

        except Exception as e:
            try:
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            except:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ An error occurred: {str(e)}",
                        ephemeral=True
                    )

    @roles_group.command(name="colors")
    @app_commands.describe(
        action="The action to perform",
        role="The role to manage"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="list", value="list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def manage_color_roles(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove", "list"],
        role: Optional[discord.Role] = None
    ):
        """Manage available color roles"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if action == "list":
                await interaction.response.defer(ephemeral=True)
                
                color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
                if not color_roles:
                    await interaction.followup.send(
                        "No color roles set up in this server.",
                        ephemeral=True
                    )
                    return

                roles = []
                total_members = 0
                
                for role_id in color_roles:
                    role = interaction.guild.get_role(role_id)
                    if not role:
                        continue
                        
                    # Count members with this role as their color
                    async with self.bot.db_manager.db.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM color_roles
                            WHERE guild_id = ? AND role_id = ? AND user_id != 0
                        """, (interaction.guild_id, role_id))
                        count = (await cursor.fetchone())[0]
                        total_members += count
                        
                    roles.append({
                        'role': role,
                        'count': count
                    })

                if not roles:
                    await interaction.followup.send(
                        "No valid color roles found in this server.",
                        ephemeral=True
                    )
                    return

                # Sort roles by position (highest first)
                roles.sort(key=lambda x: x['role'].position, reverse=True)
                
                # Create a rich embed
                embed = discord.Embed(
                    title="🎨 Available Color Roles",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )                # Add role list with counts
                role_lines = []
                for role_info in roles:
                    role = role_info['role']
                    count = role_info['count']
                    role_lines.append(
                        f"{role.mention} `{str(role.color)}` ({count} member{'s' if count != 1 else ''})"
                    )
                
                embed.description = "\n".join(role_lines)
                embed.set_footer(text=f"Total members with color roles: {total_members}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if not role:
                return await interaction.response.send_message(
                    "⚠️ Please provide a role.",
                    ephemeral=True
                )

            if role >= interaction.guild.me.top_role:
                return await interaction.response.send_message(
                    "❌ I cannot manage this role as it is above my highest role.",
                    ephemeral=True
                )

            if action == "add":
                if not role.color:
                    return await interaction.response.send_message(
                        "❌ This role doesn't have a color set.",
                        ephemeral=True
                    )

                current_colors = await self.bot.db_manager.get_color_roles(interaction.guild_id)
                if role.id in current_colors:
                    return await interaction.response.send_message(
                        "❌ This role is already in the color roles list.",
                        ephemeral=True
                    )

                    await self.bot.db_manager.set_user_color_role(
                        interaction.guild_id,
                        0,  # Special user_id 0 indicates a global color role
                        role.id
                    )

                    await interaction.response.send_message(
                        f"✅ Added {role.mention} to available color roles.",
                        ephemeral=True
                    )

                elif action == "remove":
                    current_colors = await self.bot.db_manager.get_color_roles(interaction.guild_id)
                    if role.id not in current_colors:
                        return await interaction.response.send_message(
                            "❌ This role is not in the color roles list.",
                            ephemeral=True
                        )
                    
                    await self.bot.db_manager.set_user_color_role(
                        interaction.guild_id,
                        0,  # Special user_id 0 indicates a global color role
                        None
                    )

                    # Remove from users who have it
                    affectedMembers = []
                    errorMembers = []

                    async with self.bot.db_manager.db.cursor() as cursor:
                        await cursor.execute("""
                            SELECT user_id FROM color_roles
                            WHERE guild_id = ? AND role_id = ?
                        """, (interaction.guild_id, role.id))
                        
                        for row in await cursor.fetchall():
                            member = interaction.guild.get_member(row[0])
                            if member:
                                try:
                                    await member.remove_roles(role)
                                    await self.bot.db_manager.set_user_color_role(
                                        interaction.guild_id,
                                        member.id,
                                        None
                                    )
                                    affectedMembers.append(member.mention)
                                except discord.Forbidden:
                                    errorMembers.append(f"{member.mention} (missing permissions)")
                                except discord.HTTPException:
                                    errorMembers.append(f"{member.mention} (failed)")

                    # Build response message
                    msg = [f"✅ Removed {role.mention} from available color roles."]
                    if affectedMembers:
                        msg.append("\n👥 Removed from members:")
                        msg.append(", ".join(affectedMembers))
                    if errorMembers:
                        msg.append("\n⚠️ Failed to remove from:")
                        msg.append(", ".join(errorMembers))
                    await interaction.response.send_message("\n".join(msg), ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @roles_group.command(name="react")
    @app_commands.describe(
        action="The action to perform",
        message_id="The ID of the message to bind roles to",
        role="The role to bind (for bind action)",
        emoji="The emoji to bind the role to (for bind action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="bind", value="bind"),
        app_commands.Choice(name="unbind", value="unbind"),
        app_commands.Choice(name="list", value="list")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def reaction_role(
        self,
        interaction: discord.Interaction,
        action: Literal["bind", "unbind", "list"],
        message_id: Optional[str] = None,
        role: Optional[discord.Role] = None,
        emoji: Optional[str] = None
    ):
        """Manage reaction roles"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            if action == "bind":
                if not all([message_id, role, emoji]):
                    return await interaction.response.send_message(
                        "⚠️ Please provide all required parameters: message_id, role, and emoji",
                        ephemeral=True
                    )

                try:
                    message_id = int(message_id)
                except ValueError:
                    return await interaction.response.send_message(
                        "❌ Invalid message ID format.",
                        ephemeral=True
                    )

                if role >= interaction.guild.me.top_role:
                    return await interaction.response.send_message(
                        "❌ I cannot manage this role as it is above my highest role.",
                        ephemeral=True
                    )

                # Try to find the message
                try:
                    message = await interaction.channel.fetch_message(message_id)
                except discord.NotFound:
                    return await interaction.response.send_message(
                        "❌ Message not found in this channel.",
                        ephemeral=True
                    )

                await self.bot.db_manager.add_reaction_role(
                    interaction.guild_id,
                    message_id,
                    emoji,
                    role.id
                )

                # Add reaction to message
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    await interaction.response.send_message(
                        "❌ Failed to add reaction. Make sure the emoji is valid.",
                        ephemeral=True
                    )
                    return

                self._reaction_cache[f"{message.id}:{emoji}"] = role.id
                
                await interaction.response.send_message(
                    f"✅ Bound {role.mention} to {emoji} on [this message]({message.jump_url})",
                    ephemeral=True
                )

            elif action == "unbind":
                if not message_id:
                    return await interaction.response.send_message(
                        "⚠️ Please provide the message ID to unbind roles from.",
                        ephemeral=True
                    )

                try:
                    message_id = int(message_id)
                except ValueError:
                    return await interaction.response.send_message(
                        "❌ Invalid message ID format.",
                        ephemeral=True
                    )

                # Remove all reaction roles for this message
                await self.bot.db_manager.remove_reaction_roles(
                    interaction.guild_id,
                    message_id
                )

                # Try to remove reactions from message
                try:
                    message = await interaction.channel.fetch_message(message_id)
                    await message.clear_reactions()
                except discord.NotFound:
                    pass  # Message might be deleted

                # Clear cache entries for this message
                self._reaction_cache = {
                    k: v for k, v in self._reaction_cache.items()
                    if not k.startswith(f"{message_id}:")
                }

                await interaction.response.send_message(
                    "✅ Removed all reaction roles from the message.",
                    ephemeral=True
                )

            else:  # list
                reaction_roles = await self.bot.db_manager.get_reaction_roles(interaction.guild_id)
                if not reaction_roles:
                    return await interaction.response.send_message(
                        "No reaction roles set up in this server.",
                        ephemeral=True
                    )

                embed = discord.Embed(
                    title="Reaction Roles",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )

                for msg_id, bindings in reaction_roles.items():
                    try:
                        channel_id = await self.bot.db_manager.get_reaction_role_channel(
                            interaction.guild_id,
                            msg_id
                        )
                        channel = interaction.guild.get_channel(channel_id)
                        if not channel:
                            continue

                        field_value = []
                        for emoji, role_id in bindings.items():
                            role = interaction.guild.get_role(role_id)
                            if role:
                                field_value.append(f"{emoji} → {role.mention}")

                        if field_value:
                            embed.add_field(
                                name=f"Message ID: {msg_id}",
                                value="\n".join(field_value),
                                inline=False
                            )
                    except Exception:
                        continue

                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @roles_group.command(name="bulk")
    @app_commands.describe(
        action="The action to perform",
        role="The role to add/remove",
        users="The users to add/remove the role from (space-separated)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove")
    ])
    @app_commands.default_permissions(manage_roles=True)
    async def bulk_role(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove"],
        role: discord.Role,
        users: str
    ):
        """Add or remove a role from multiple users"""
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ I cannot manage this role as it is above my highest role.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        success = []
        failed = []
        
        # Parse user IDs/mentions
        user_ids = []
        for part in users.split():
            if part.isdigit():
                user_ids.append(int(part))
            elif part.startswith('<@') and part.endswith('>'):
                try:
                    user_id = int(part[2:-1].replace('!', ''))
                    user_ids.append(user_id)
                except ValueError:
                    continue

        for user_id in user_ids:
            member = interaction.guild.get_member(user_id)
            if not member:
                failed.append(f"<@{user_id}> (not found)")
                continue

            try:
                if action == "add":
                    await member.add_roles(role)
                else:
                    await member.remove_roles(role)
                success.append(member.mention)
            except Exception:
                failed.append(member.mention)        # Build response message
        msg = []
        if success:
            msg.extend([
                f"✅ Successfully {'added' if action == 'add' else 'removed'} {role.mention} {'to' if action == 'add' else 'from'}:",
                ", ".join(success)
            ])

        if failed:
            msg.extend([
                "\n❌ Failed for these users:",
                ", ".join(failed)
            ])

        await interaction.followup.send(
            msg if msg else "No valid users provided.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle auto-role assignment"""
        if not self.bot.db_manager:
            return

        try:
            config = await self.bot.db_manager.get_guild_config(member.guild.id)
            if not config or not config.get("auto_role_id"):
                return

            role = member.guild.get_role(config["auto_role_id"])
            if role and role < member.guild.me.top_role:
                await member.add_roles(role)
        except Exception as e:
            print(f"Error assigning auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role assignment"""
        if not self.bot.db_manager or payload.member.bot:
            return

        try:
            # Check cache first
            cache_key = f"{payload.message_id}:{str(payload.emoji)}"
            role_id = self._reaction_cache.get(cache_key)

            if role_id is None:
                # Not in cache, check database
                role_id = await self.bot.db_manager.get_reaction_role(
                    payload.guild_id,
                    payload.message_id,
                    str(payload.emoji)
                )
                if role_id:
                    self._reaction_cache[cache_key] = role_id

            if role_id:
                guild = self.bot.get_guild(payload.guild_id)
                if not guild:
                    return

                role = guild.get_role(role_id)
                if role and role < guild.me.top_role:
                    await payload.member.add_roles(role)

        except Exception as e:
            print(f"Error handling reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction role removal"""
        if not self.bot.db_manager:
            return

        try:
            # Check cache first
            cache_key = f"{payload.message_id}:{str(payload.emoji)}"
            role_id = self._reaction_cache.get(cache_key)

            if role_id is None:
                # Not in cache, check database
                role_id = await self.bot.db_manager.get_reaction_role(
                    payload.guild_id,
                    payload.message_id,
                    str(payload.emoji)
                )
                if role_id:
                    self._reaction_cache[cache_key] = role_id

            if role_id:
                guild = self.bot.get_guild(payload.guild_id)
                if not guild:
                    return

                member = guild.get_member(payload.user_id)
                if not member or member.bot:
                    return

                role = guild.get_role(role_id)
                if role and role < guild.me.top_role:
                    await member.remove_roles(role)

        except Exception as e:
            print(f"Error handling reaction role removal: {e}")

async def setup(bot):
    await bot.add_cog(RolesCog(bot))