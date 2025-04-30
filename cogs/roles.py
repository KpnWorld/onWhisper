import discord
from discord.ext import commands
import asyncio
from typing import List

class Roles(commands.Cog):
    """Auto, reaction, and bulk role management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Roles cog")
                return
            self._ready.set()
            print("✅ Roles cog ready")
        except Exception as e:
            print(f"❌ Error setting up Roles cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    @commands.hybrid_group(name="roles")
    @commands.has_permissions(manage_roles=True)
    async def roles(self, ctx):
        """Role management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # Auto-role commands
    @roles.group(name="auto")
    async def roles_auto(self, ctx):
        """Auto-role commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles_auto.command(name="set")
    async def auto_set(self, ctx, role: discord.Role):
        """Enable auto-role"""
        try:
            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            await self.db_manager.set_auto_role(ctx.guild.id, role.id, True)
            
            embed = self.ui.admin_embed(
                "Auto-Role Set",
                f"New members will receive {role.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_auto.command(name="remove")
    async def auto_remove(self, ctx):
        """Disable auto-role"""
        try:
            await self.db_manager.set_auto_role(ctx.guild.id, None, False)
            
            embed = self.ui.admin_embed(
                "Auto-Role Disabled",
                "New members will no longer receive an automatic role"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Reaction role commands
    @roles.group(name="react")
    async def roles_react(self, ctx):
        """Reaction role commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles_react.command(name="bind")
    async def react_bind(self, ctx, message_id: str, emoji: str, role: discord.Role):
        """Bind emoji to role on message"""
        try:
            try:
                message_id = int(message_id)
            except ValueError:
                await ctx.send("Invalid message ID!", ephemeral=True)
                return

            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            # Find message
            try:
                message = await ctx.channel.fetch_message(message_id)
            except discord.NotFound:
                await ctx.send("Message not found in this channel!", ephemeral=True)
                return

            # Add reaction
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                await ctx.send("Invalid emoji!", ephemeral=True)
                return

            # Save binding
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {emoji: role.id},
                ['reaction_roles', str(message_id)]
            )
            
            embed = self.ui.admin_embed(
                "Reaction Role Bound",
                f"React with {emoji} to get {role.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_react.command(name="unbind")
    async def react_unbind(self, ctx, message_id: str):
        """Remove all reactions/roles from message"""
        try:
            try:
                message_id = int(message_id)
            except ValueError:
                await ctx.send("Invalid message ID!", ephemeral=True)
                return

            # Find message
            try:
                message = await ctx.channel.fetch_message(message_id)
            except discord.NotFound:
                await ctx.send("Message not found in this channel!", ephemeral=True)
                return

            # Remove reactions and bindings
            await message.clear_reactions()
            await self.db_manager.delete_data('reaction_roles', f"{ctx.guild.id}:{message_id}")
            
            embed = self.ui.admin_embed(
                "Reaction Roles Removed",
                "All reaction role bindings have been removed from the message"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_react.command(name="list")
    async def react_list(self, ctx):
        """Show all reaction role bindings"""
        try:
            prefix = f"{self.db_manager.prefix}reaction_roles:{ctx.guild.id}:"
            bindings = []
            
            for key in self.db_manager.db.keys():
                if key.startswith(prefix):
                    message_id = key.split(':')[-1]
                    data = self.db_manager.db[key]
                    
                    try:
                        message = await ctx.guild.fetch_message(int(message_id))
                        channel = message.channel
                        
                        for emoji, role_id in data.items():
                            role = ctx.guild.get_role(role_id)
                            if role:
                                bindings.append((channel, message_id, emoji, role))
                    except:
                        continue
            
            if not bindings:
                await ctx.send("No reaction roles configured!")
                return
                
            description = ""
            for channel, msg_id, emoji, role in bindings:
                description += f"• {channel.mention} [{msg_id}]: {emoji} → {role.mention}\n"
            
            embed = self.ui.info_embed(
                "Reaction Role Bindings",
                description
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Bulk role commands
    @roles.command(name="bulk")
    async def roles_bulk(self, ctx):
        """Bulk role management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @roles_bulk.command(name="add")
    async def bulk_add(self, ctx, role: discord.Role, users: commands.Greedy[discord.Member]):
        """Assign role to multiple users"""
        try:
            if not users:
                await ctx.send("No users specified!", ephemeral=True)
                return

            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            success = []
            failed = []

            for user in users:
                try:
                    if role not in user.roles:
                        await user.add_roles(role)
                        success.append(user)
                except:
                    failed.append(user)

            # Create status message
            description = ""
            if success:
                description += f"✅ Added to {len(success)} users\n"
            if failed:
                description += f"❌ Failed for {len(failed)} users"

            embed = self.ui.admin_embed(
                "Bulk Role Assignment",
                description
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @roles_bulk.command(name="remove")
    async def bulk_remove(self, ctx, role: discord.Role, users: commands.Greedy[discord.Member]):
        """Remove role from multiple users"""
        try:
            if not users:
                await ctx.send("No users specified!", ephemeral=True)
                return

            if role >= ctx.guild.me.top_role:
                await ctx.send("I cannot manage roles higher than my highest role", ephemeral=True)
                return

            success = []
            failed = []

            for user in users:
                try:
                    if role in user.roles:
                        await user.remove_roles(role)
                        success.append(user)
                except:
                    failed.append(user)

            # Create status message
            description = ""
            if success:
                description += f"✅ Removed from {len(success)} users\n"
            if failed:
                description += f"❌ Failed for {len(failed)} users"

            embed = self.ui.admin_embed(
                "Bulk Role Removal",
                description
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    # Event handlers
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle auto-role assignment"""
        try:
            role_data = await self.db_manager.get_auto_role(member.guild.id)
            if not role_data:
                return
                
            role_id, enabled = role_data
            if not enabled:
                return
                
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role)
        except Exception as e:
            print(f"Error assigning auto-role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction role assignments"""
        try:
            # Ignore bot reactions
            if payload.member.bot:
                return

            # Get reaction role data
            data = await self.db_manager.get_data(
                'reaction_roles',
                f"{payload.guild_id}:{payload.message_id}"
            )
            if not data:
                return

            # Check if this reaction is bound to a role
            role_id = data.get(str(payload.emoji))
            if not role_id:
                return

            # Assign role
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            
            if role and role < guild.me.top_role:
                await payload.member.add_roles(role)
        except Exception as e:
            print(f"Error handling reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction role removals"""
        try:
            # Get reaction role data
            data = await self.db_manager.get_data(
                'reaction_roles',
                f"{payload.guild_id}:{payload.message_id}"
            )
            if not data:
                return

            # Check if this reaction is bound to a role
            role_id = data.get(str(payload.emoji))
            if not role_id:
                return

            # Remove role
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(role_id)
            
            if member and role and role < guild.me.top_role:
                await member.remove_roles(role)
        except Exception as e:
            print(f"Error handling reaction role removal: {e}")

async def setup(bot):
    await bot.add_cog(Roles(bot))