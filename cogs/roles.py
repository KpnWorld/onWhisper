import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from discord.app_commands import Choice, Group

class RolesCog(commands.Cog):
    """Cog for role management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def _check_permissions(self, ctx_or_interaction) -> bool:
        """Check if user has required permissions"""
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.user
        else:  # Context
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.author
            
        if not guild or not isinstance(user, discord.Member):
            return False
            
        return user.guild_permissions.manage_roles
    
    async def _get_role_settings(self, guild_id: int) -> Optional[dict]:
        """Get role management settings"""
        feature_settings = await self.bot.db.get_feature_settings(guild_id, "roles")
        if not feature_settings or not feature_settings['enabled']:
            return None
        return feature_settings['options']

    async def _save_role_settings(self, guild_id: int, options: dict):
        """Save role management settings"""
        await self.bot.db.set_feature_settings(
            guild_id,
            "roles",
            True,
            options
        )

    roles = Group(name="roles", description="Manage server roles.")
    
    @roles.command(name="info", description="Get information about a role.")
    @app_commands.describe(role="The role to get information about")
    async def role_info(self, interaction: discord.Interaction, role: discord.Role):
        """Get information about a role."""
        embed = discord.Embed(
            title=f"Role Information: {role.name}",
            color=role.color
        )
        
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
        embed.add_field(name="Hoisted", value=role.hoist, inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, 'R'), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    autorole = Group(name="autorole", description="Manage auto roles.")
    
    @autorole.command(name="add", description="Add an auto role")
    @app_commands.describe(role="Role to add as an auto role")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        """Add an auto role."""
        # Check if bot can manage the role
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message("I don't have permission to manage roles!", ephemeral=True)
        
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("I can't manage this role as it's higher than my highest role!", ephemeral=True)
            
        try:
            await self.bot.db.add_autorole(interaction.guild.id, role.id)
            await interaction.response.send_message(f"✅ Added {role.mention} as an auto role.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @autorole.command(name="remove", description="Remove an auto role")
    @app_commands.describe(role="Role to remove from auto roles")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        """Remove an auto role."""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        if not await self._check_permissions(interaction):
            return await interaction.response.send_message("You need the Manage Roles permission to use this command!", ephemeral=True)
            
        try:
            # Fix: Pass guild.id instead of guild object
            await self.bot.db.remove_autorole(interaction.guild.id, role.id)
            await interaction.response.send_message(f"✅ Removed {role.mention} from auto roles.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @autorole.command(name="list", description="List all auto roles")
    @app_commands.guild_only()
    async def autorole_list(self, interaction: discord.Interaction):
        """List all auto roles."""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        try:
            role_ids = await self.bot.db.get_autoroles(interaction.guild.id)
            if not role_ids:
                return await interaction.response.send_message("No auto roles set up!", ephemeral=True)
                
            roles = [interaction.guild.get_role(role_id) for role_id in role_ids]
            roles = [role for role in roles if role is not None]  # Filter out deleted roles
            
            embed = discord.Embed(
                title="Auto Roles",
                description="\n".join(f"• {role.mention}" for role in roles),
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    reactionrole = Group(name="reactionrole", description="Manage reaction roles.")
    
    @reactionrole.command(name="add", description="Add a reaction role")
    @app_commands.describe(
        message_id="ID of the message to add reaction role to (Right click message -> Copy ID)",
        role="Role to give when reacting",
        emoji="Emoji to use for the reaction (Unicode emoji or custom emoji)"
    )
    async def reactionrole_add(self, interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str):
        try:
            msg_id = int(message_id)  # Convert string to int
            
            if not interaction.guild:
                return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)

            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.send_message("I don't have permission to manage roles!", ephemeral=True)
            
            if role >= interaction.guild.me.top_role:
                return await interaction.response.send_message("I can't manage this role as it's higher than my highest role!", ephemeral=True)
                
            channel = interaction.channel
            if not channel:
                return await interaction.response.send_message("Cannot find the channel!", ephemeral=True)
            if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                return await interaction.response.send_message("This command can only be used in text channels, threads, or voice channels!", ephemeral=True)
                
            try:
                message = await channel.fetch_message(msg_id)
            except discord.NotFound:
                return await interaction.response.send_message("Message not found! Make sure you're using this command in the same channel as the message.", ephemeral=True)
            except AttributeError:
                return await interaction.response.send_message("Cannot fetch messages in this type of channel!", ephemeral=True)
            
            # Validate emoji
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                return await interaction.response.send_message("Invalid emoji! Please use a standard emoji or one from this server.", ephemeral=True)
            
            # Store in database with error handling
            try:
                await self.bot.db.add_reaction_role(interaction.guild.id, message.id, str(emoji), role.id)
            except Exception as e:
                await message.clear_reaction(emoji)
                raise e
            
            await interaction.response.send_message(f"✅ Added reaction role:\nMessage: {message.jump_url}\nEmoji: {emoji}\nRole: {role.mention}")
            
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Message not found! Make sure you're using this command in the same channel as the message.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to add reactions to that message!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @reactionrole.command(name="remove", description="Remove a reaction role")
    @app_commands.describe(
        message_id="ID of the message to remove the reaction role from",
        emoji="Emoji of the reaction role to remove"
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_remove(self, interaction: discord.Interaction, message_id: int, emoji: str):
        """Remove a reaction role."""
        if not await self._check_permissions(interaction):
            return await interaction.response.send_message("You need the Manage Roles permission to use this command!", ephemeral=True)
            
        try:
            message_id = int(message_id)
            channel = interaction.channel
            if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                return await interaction.response.send_message("This command can only be used in text channels, threads, or voice channels!", ephemeral=True)
            
            try:
                message = await channel.fetch_message(message_id)
                # Remove the reaction from the message
                await message.clear_reaction(emoji)
            except AttributeError:
                return await interaction.response.send_message("Cannot fetch messages in this type of channel!", ephemeral=True)
            
            # Remove from database
            await self.bot.db.remove_reaction_role(interaction.guild, message.id, str(emoji))
            
            await interaction.response.send_message(f"✅ Removed reaction role from {message.jump_url}")
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Message not found! Make sure you're using this command in the same channel as the message.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RolesCog(bot))
