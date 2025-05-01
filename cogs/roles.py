import discord
from discord.ext import commands
from typing import List, Optional
import asyncio

class Roles(commands.Cog):
    """Role management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Auto-assign role to new members"""
        try:
            role_id, enabled = await self.db.get_auto_role(member.guild.id)
            if not enabled or not role_id:
                return
                
            role = member.guild.get_role(role_id)
            if role and role < member.guild.me.top_role:
                await member.add_roles(
                    role,
                    reason="Auto-role on join"
                )
                
                # Log the action
                await self.db.log_event(
                    member.guild.id,
                    member.id,
                    'auto_role',
                    f"Auto-role {role.name} assigned"
                )
        except Exception as e:
            print(f"Error in auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction role assignments"""
        if payload.member.bot:
            return

        try:
            # Get reaction roles for this message
            reaction_roles = await self.db.get_reaction_roles(payload.guild_id, payload.message_id)
            role_id = reaction_roles.get(str(payload.emoji))
            
            if not role_id:
                return
                
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(int(role_id))
            
            if role and role < guild.me.top_role:
                await payload.member.add_roles(
                    role,
                    reason="Reaction role"
                )
                
        except Exception as e:
            print(f"Error in reaction role add: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction role removals"""
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            if member.bot:
                return

            # Get reaction roles for this message
            reaction_roles = await self.db.get_reaction_roles(payload.guild_id, payload.message_id)
            role_id = reaction_roles.get(str(payload.emoji))
            
            if not role_id:
                return
                
            role = guild.get_role(int(role_id))
            
            if role and role < guild.me.top_role:
                await member.remove_roles(
                    role,
                    reason="Reaction role removed"
                )
                
        except Exception as e:
            print(f"Error in reaction role remove: {e}")

    @commands.hybrid_group(name="roles")
    @commands.has_permissions(manage_roles=True)
    async def roles(self, ctx):
        """Role management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles.group(name="auto")
    @commands.has_permissions(manage_roles=True)
    async def roles_auto(self, ctx):
        """Auto-role settings"""
        if ctx.invoked_subcommand is None:
            # Show current auto-role status
            role_id, enabled = await self.db.get_auto_role(ctx.guild.id)
            if role_id:
                role = ctx.guild.get_role(role_id)
                status = f"**Current auto-role:** {role.mention if role else 'Role not found'}\n**Status:** {'Enabled' if enabled else 'Disabled'}"
            else:
                status = "No auto-role configured"
                
            embed = self.ui.info_embed(
                "Auto-Role Status",
                status
            )
            await ctx.send(embed=embed)

    @roles_auto.command(name="set")
    async def auto_set(self, ctx, role: discord.Role):
        """Set the auto-role for new members"""
        try:
            # Verify bot can manage this role
            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot assign roles higher than my own role", ephemeral=True)
                return
                
            await self.db.update_auto_role(ctx.guild.id, role.id)
            
            embed = self.ui.success_embed(
                "Auto-Role Set",
                f"New members will automatically receive the {role.mention} role"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_auto.command(name="remove")
    async def auto_remove(self, ctx):
        """Disable the auto-role"""
        try:
            await self.db.update_auto_role(ctx.guild.id, None)
            
            embed = self.ui.success_embed(
                "Auto-Role Disabled",
                "New members will no longer receive an automatic role"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles.group(name="react")
    async def roles_react(self, ctx):
        """Reaction role settings"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles_react.command(name="bind")
    async def react_bind(self, ctx, message_id: int, emoji: str, role: discord.Role):
        """Bind an emoji to a role on a message"""
        try:
            message = await ctx.channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            
            reaction_roles = await self.db.get_section(ctx.guild.id, 'reaction_roles')
            if str(message_id) not in reaction_roles:
                reaction_roles[str(message_id)] = {}
            reaction_roles[str(message_id)][emoji] = str(role.id)
            await self.db.update_guild_data(ctx.guild.id, 'reaction_roles', reaction_roles)
            
            await ctx.send(
                f"Bound {emoji} to {role.mention} on [this message]({message.jump_url})",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_react.command(name="unbind")
    async def react_unbind(self, ctx, message_id: int):
        """Remove all reaction roles from a message"""
        try:
            message = await ctx.channel.fetch_message(message_id)
            await message.clear_reactions()
            
            await self.db.remove_reaction_role(ctx.guild.id, message_id)
            await ctx.send("Removed all reaction roles from the message", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles.group(name="bulk")
    async def roles_bulk(self, ctx):
        """Bulk role management"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles_bulk.command(name="add")
    async def bulk_add(self, ctx, role: discord.Role, users: commands.Greedy[discord.Member]):
        """Add a role to multiple users"""
        try:
            if not users:
                await ctx.send("No valid users provided", ephemeral=True)
                return
                
            result = await self.db.bulk_role_update(
                ctx.guild.id, role.id,
                [u.id for u in users],
                'add'
            )
            
            for user in users:
                try:
                    await user.add_roles(role)
                except:
                    continue
                    
            await ctx.send(f"Added {role.name} to {len(users)} users")
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_bulk.command(name="remove")
    async def bulk_remove(self, ctx, role: discord.Role, users: commands.Greedy[discord.Member]):
        """Remove a role from multiple users"""
        try:
            if not users:
                await ctx.send("No valid users provided", ephemeral=True)
                return
                
            result = await self.db.bulk_role_update(
                ctx.guild.id, role.id,
                [u.id for u in users],
                'remove'
            )
            
            for user in users:
                try:
                    await user.remove_roles(role)
                except:
                    continue
                    
            await ctx.send(f"Removed {role.name} from {len(users)} users")
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Roles(bot))