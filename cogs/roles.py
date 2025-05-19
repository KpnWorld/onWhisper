import discord
from discord.ext import commands
from discord.commands import slash_command, option
from typing import Optional, Literal, List, Union, cast
import re

class Roles(commands.Cog):
    """Role management commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="autorole", description="Manage roles that are automatically assigned to new members")
    @commands.has_permissions(manage_roles=True)
    @option("action", description="The action to perform", type=str, choices=["add", "remove", "list"])
    @option("role", description="The role to add/remove (not needed for list)", type=discord.Role, required=False)
    async def autorole(
        self,
        ctx: discord.ApplicationContext,
        action: Literal["add", "remove", "list"],
        role: Optional[discord.Role] = None
    ) -> None:
        if action == "list":
            role_ids = await self.bot.db.get_autoroles(ctx.guild.id)
            if not role_ids:
                await ctx.respond("❌ No autoroles set up!")
                return
                
            roles = [ctx.guild.get_role(role_id) for role_id in role_ids]
            roles = [role for role in roles if role]  # Filter out None/deleted roles
            
            embed = discord.Embed(
                title="Autoroles",
                description="\n".join(f"• {role.mention}" for role in roles),
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return
            
        if not role:
            await ctx.respond("❌ Please provide a role!")
            return
            
        if action == "add":
            await self.bot.db.add_autorole(ctx.guild.id, role.id)
            await ctx.respond(f"✅ Added {role.mention} as an autorole")
            
        elif action == "remove":
            await self.bot.db.remove_autorole(ctx.guild.id, role.id)
            await ctx.respond(f"✅ Removed {role.mention} from autoroles")    
            
    @slash_command(name="levelrole", description="Manage roles that are awarded at specific XP levels")
    @commands.has_permissions(manage_roles=True)
    @option("action", description="The action to perform", type=str, choices=["set", "delete", "list"])
    @option("level", description="The level requirement (not needed for list)", type=int, min_value=1, required=False)
    @option("role", description="The role to award (only needed for set)", type=discord.Role, required=False)
    async def levelrole(
        self,
        ctx: discord.ApplicationContext,
        action: Literal["set", "delete", "list"],
        level: Optional[int] = None,
        role: Optional[discord.Role] = None
    ) -> None:
        if action == "list":
            roles = await self.bot.db.get_level_roles(ctx.guild.id)
            if not roles:
                await ctx.respond("❌ No level roles set up!")
                return
                
            valid_roles = []
            for role_data in roles:
                role = ctx.guild.get_role(role_data['role_id'])
                if role:
                    valid_roles.append(f"Level {role_data['level']}: {role.mention}")
            
            if not valid_roles:
                await ctx.respond("❌ No valid level roles found!")
                return

            embed = discord.Embed(
                title="Level Roles",
                description="\n".join(valid_roles),
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return
            
        if not level and action != "list":
            await ctx.respond("❌ Please provide a level!")
            return
            
        if level is not None and level < 1:
            await ctx.respond("❌ Level must be greater than 0!")
            return
            
        if action == "set":
            if not role:
                await ctx.respond("❌ Please provide a role!")
                return
                
            await self.bot.db.add_level_role(ctx.guild.id, level, role.id)
            await ctx.respond(f"✅ Set {role.mention} as the reward for level {level}")
            
        elif action == "delete":
            if level is not None:
                await self.bot.db.remove_level_role(ctx.guild.id, level)
                await ctx.respond(f"✅ Removed level {level} role reward")    
                
    @slash_command(name="reactionrole", description="Manage reaction roles")
    @commands.has_permissions(manage_roles=True)
    @option("action", description="The action to perform", type=str, choices=["add", "remove", "list"])
    @option("message_id", description="The ID of the message to add reactions to", type=str, required=False)
    @option("emoji", description="The emoji to use for the reaction", type=str, required=False)
    @option("role", description="The role to give when reacted", type=discord.Role, required=False)
    async def reactionrole(
        self,
        ctx: discord.ApplicationContext,
        action: Literal["add", "remove", "list"],
        message_id: Optional[str] = None,
        emoji: Optional[str] = None,
        role: Optional[discord.Role] = None
    ) -> None:
        if action == "list":
            reaction_roles = await self.bot.db.get_reaction_roles(ctx.guild.id)
            if not reaction_roles:
                await ctx.respond("❌ No reaction roles set up!")
                return
                
            embed = discord.Embed(
                title="Reaction Roles",
                color=discord.Color.blue()
            )
            
            for rr in reaction_roles:
                role = ctx.guild.get_role(rr['role_id'])
                if role:
                    embed.add_field(
                        name=f"Message {rr['message_id']}",
                        value=f"Emoji: {rr['emoji']}\nRole: {role.mention}",
                        inline=True
                    )
                    
            await ctx.respond(embed=embed)
            return
            
        if action in ["add", "remove"] and not all([message_id, emoji]):
            await ctx.respond("❌ Please provide message ID and emoji!")
            return

        if action == "add":
            if not role:
                await ctx.respond("❌ Please provide a role!")
                return

            if message_id is None:
                await ctx.respond("❌ Please provide a message ID!")
                return
                
            try:
                msg_id = int(message_id)
                message = await ctx.channel.fetch_message(msg_id)
            except (discord.NotFound, ValueError):
                await ctx.respond("❌ Message not found!")
                return
                
            if emoji is None:
                await ctx.respond("❌ Please provide an emoji!")
                return
                
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                await ctx.respond("❌ Invalid emoji!")
                return
                
            await self.bot.db.add_reaction_role(
                ctx.guild.id,
                str(msg_id),
                emoji,
                role.id
            )
            await ctx.respond(f"✅ Added reaction role: {emoji} → {role.mention}")
            
        elif action == "remove":
            if message_id is not None and emoji is not None:
                await self.bot.db.remove_reaction_role(
                    ctx.guild.id,
                    message_id,
                    emoji
                )
                await ctx.respond("✅ Removed reaction role")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle reaction role assignments"""
        if payload.user_id == self.bot.user.id:
            return
            
        reaction_role = await self.bot.db.get_reaction_role(
            payload.guild_id,
            str(payload.message_id),
            str(payload.emoji)
        )
        
        if not reaction_role:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        role = guild.get_role(reaction_role['role_id'])
        
        if member and role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle reaction role removals"""
        if payload.user_id == self.bot.user.id:
            return
            
        reaction_role = await self.bot.db.get_reaction_role(
            payload.guild_id,
            str(payload.message_id),
            str(payload.emoji)
        )
        
        if not reaction_role:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        role = guild.get_role(reaction_role['role_id'])
        
        if member and role:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Assign autoroles to new members"""
        role_ids = await self.bot.db.get_autoroles(member.guild.id)
        if not role_ids:
            return
            
        roles = [member.guild.get_role(role_id) for role_id in role_ids]
        roles = [role for role in roles if role]  # Filter out None/deleted roles
        
        if roles:
            try:
                await member.add_roles(*roles, reason="Autorole")
            except discord.Forbidden:
                pass

def setup(bot):
    bot.add_cog(Roles(bot))
