import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, Union
from utils.db_manager import DBManager
import json
from replit import db
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager  # Use bot's DBManager instance
        self.ui = self.bot.ui_manager
        self.locked_channels = set()
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Moderation cog")
                return
                
            self._ready.set()
            print("✅ Moderation cog ready")
            
        except Exception as e:
            print(f"❌ Error setting up Moderation cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    async def log_mod_action(self, guild: discord.Guild, action: str, description: str):
        """Send mod action to logging channel"""
        try:
            logging_cog = self.bot.get_cog('Logging')
            if logging_cog:
                await logging_cog.log_to_channel(
                    guild,
                    f"⚔️ {action}",
                    description,
                    discord.Color.red()
                )
        except Exception as e:
            print(f"Failed to log moderation action: {e}")

    @commands.hybrid_command(description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, reason: str = None):
        """Kick a member from the server"""
        try:
            if not ctx.guild.me.guild_permissions.kick_members:
                raise commands.BotMissingPermissions(['kick_members'])

            # Check hierarchy
            if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
                embed = self.ui.mod_embed(
                    "Permission Error",
                    "You cannot kick someone with a higher or equal role!",
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            await member.kick(reason=f"Kicked by {ctx.author}: {reason}")
            
            # Log the action to database
            await self.db_manager.log_event(
                ctx.guild.id,
                member.id,
                "kick",
                f"Kicked by {ctx.author} for: {reason}"
            )
            
            description = f"Member: {member.mention}\nReason: {reason or 'No reason provided'}"
            
            # Send to mod-logs channel
            await self.log_mod_action(
                ctx.guild,
                "Member Kicked",
                description
            )
            
            # Send confirmation to command channel
            embed = self.ui.mod_embed(
                "Member Kicked",
                description
            )
            await ctx.send(embed=embed)
            
        except commands.MissingPermissions:
            await ctx.send("You don't have permission to kick members!", ephemeral=True)
        except commands.BotMissingPermissions:
            await ctx.send("I don't have permission to kick members!", ephemeral=True)
        except discord.Forbidden:
            await ctx.send("I can't kick that member due to role hierarchy!", ephemeral=True)
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

    @commands.hybrid_command(description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, reason: str = None, delete_days: int = 0):
        """Ban a member from the server"""
        try:
            # Check hierarchy
            if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
                embed = self.ui.mod_embed(
                    "Permission Error",
                    "You cannot ban someone with a higher or equal role!",
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            await member.ban(reason=f"Banned by {ctx.author}: {reason}", 
                           delete_message_days=delete_days)
            
            # Log the action to database
            await self.db_manager.log_event(
                ctx.guild.id,
                member.id,
                "ban",
                f"Banned by {ctx.author} for: {reason}"
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Reason: {reason or 'No reason provided'}\n"
                f"Message Deletion: {delete_days} days"
            )
            
            # Send to mod-logs channel
            await self.log_mod_action(
                ctx.guild,
                "Member Banned",
                description
            )
            
            # Send confirmation to command channel
            embed = self.ui.mod_embed(
                "Member Banned",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Timeout (mute) a member")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, *, reason: str = None):
        """Timeout (mute) a member"""
        try:
            # Create duration options
            duration_options = [
                {"label": "60 seconds", "description": "Timeout for 1 minute", "value": "60:s"},
                {"label": "5 minutes", "description": "Timeout for 5 minutes", "value": "5:m"},
                {"label": "10 minutes", "description": "Timeout for 10 minutes", "value": "10:m"},
                {"label": "1 hour", "description": "Timeout for 1 hour", "value": "1:h"},
                {"label": "1 day", "description": "Timeout for 24 hours", "value": "1:d"},
                {"label": "1 week", "description": "Timeout for 7 days", "value": "7:d"},
                {"label": "Custom", "description": "Set custom duration", "value": "custom"}
            ]

            view = self.ui.CommandSelectView(
                options=duration_options,
                placeholder="Select timeout duration"
            )

            embed = self.ui.mod_embed(
                "Select Timeout Duration",
                f"Choose how long to timeout {member.mention}"
            )
            
            view.message = await ctx.send(embed=embed, view=view)
            await view.wait()

            if not view.result:
                await view.message.edit(
                    embed=self.ui.error_embed("Timeout", "No duration selected"),
                    view=None
                )
                return

            if view.result == "custom":
                await view.message.edit(
                    embed=self.ui.error_embed("Custom Duration", "Custom duration not yet implemented"),
                    view=None
                )
                return
                
            duration, unit = view.result.split(":")
            duration = int(duration)

            # Convert to timedelta
            if unit == 's':
                delta = timedelta(seconds=duration)
            elif unit == 'm':
                delta = timedelta(minutes=duration)
            elif unit == 'h':
                delta = timedelta(hours=duration)
            elif unit == 'd':
                delta = timedelta(days=duration)

            # Apply timeout
            await member.timeout(delta, reason=f"Timeout by {ctx.author}: {reason}")
            
            # Log the action to database
            await self.db_manager.log_event(
                ctx.guild.id,
                member.id,
                "timeout",
                f"Timed out by {ctx.author} for {duration}{unit}: {reason}"
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Duration: {duration}{unit}\n"
                f"Reason: {reason or 'No reason provided'}"
            )
            
            # Send to mod-logs channel
            await self.log_mod_action(
                ctx.guild,
                "Member Timed Out",
                description
            )
            
            # Send confirmation to command channel
            embed = self.ui.mod_embed(
                "Member Timed Out",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Clear a specified number of messages")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int, user: discord.Member = None):
        """Clear a specified number of messages"""
        try:
            # Use ctx.defer() for both interaction and command context
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.defer(ephemeral=True)
            
            def check_message(m):
                return user is None or m.author == user

            # Get messages before deleting
            messages = await ctx.channel.purge(
                limit=amount,
                check=check_message,
                before=ctx.message.created_at if hasattr(ctx, 'message') else None
            )
            
            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "clear",
                f"Cleared {len(messages)} messages in {ctx.channel.name}"
                + (f" from {user}" if user else "")
            )
            
            description = (
                f"Messages Deleted: {len(messages)}\n"
                f"Channel: {ctx.channel.mention}\n"
                f"Target User: {user.mention if user else 'All users'}"
            )
            
            embed = self.ui.mod_embed(
                "Messages Cleared",
                description
            )

            # Send response using appropriate method
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.followup.send(embed=embed, ephemeral=True)
            else:
                msg = await ctx.send(embed=embed)
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except:
                    pass
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e)
            )
            try:
                if isinstance(ctx.interaction, discord.Interaction):
                    await ctx.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await ctx.send(embed=error_embed, ephemeral=True)
            except:
                pass

    @commands.hybrid_command(description="Warn a member")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, reason: str):
        """Warn a member"""
        try:
            # Get guild data
            guild_data = await self.db_manager.get_guild_data(ctx.guild.id)
            mod_actions = guild_data.get('mod_actions', [])
            
            # Add warning
            warning = {
                'user_id': member.id,
                'mod_id': ctx.author.id,
                'action': 'warn',
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            mod_actions.append(warning)
            
            # Update database
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {'mod_actions': mod_actions}
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Reason: {reason}"
            )
            
            embed = self.ui.mod_embed(
                "Member Warned",
                description
            )
            await ctx.send(embed=embed)
            
            try:
                # Try to DM the user
                dm_description = (
                    f"Server: {ctx.guild.name}\n"
                    f"Reason: {reason}"
                )
                
                warn_dm = self.ui.mod_embed(
                    "Warning Received",
                    dm_description
                )
                await member.send(embed=warn_dm)
            except:
                pass  # Ignore if DM fails
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Lock a channel")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None, *, reason: str = None):
        """Lock a channel to prevent messages from non-admins"""
        try:
            channel = channel or ctx.channel
            bot_member = ctx.guild.me
            
            # Permission check
            if not (ctx.author.guild_permissions.administrator or 
                   ctx.author.guild_permissions.manage_guild):
                embed = self.ui.error_embed(
                    "Missing Permissions",
                    "You need Administrator or Manage Server permission to use this command!"
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Check if already locked
            if channel.id in self.locked_channels:
                embed = self.ui.mod_embed(
                    "Channel Already Locked",
                    f"{channel.mention} is already locked!"
                )
                await ctx.send(embed=embed)
                return

            # Track affected roles for logging
            affected_roles = []
            failed_roles = []

            # Process each role
            for role in ctx.guild.roles:
                # Skip if role is higher than bot's role
                if role >= bot_member.top_role:
                    continue
                    
                # Skip admin roles
                if role.permissions.administrator:
                    continue

                try:
                    # Check current permissions
                    role_perms = channel.permissions_for(role)
                    if role_perms.send_messages:
                        # Create or update overwrite
                        overwrites = channel.overwrites_for(role)
                        overwrites.send_messages = False
                        await channel.set_permissions(
                            role, 
                            overwrite=overwrites,
                            reason=f"Channel lock by {ctx.author}"
                        )
                        affected_roles.append(role.name)
                except discord.Forbidden:
                    failed_roles.append(role.name)
                except Exception as e:
                    print(f"Error setting permissions for {role.name}: {e}")
                    failed_roles.append(role.name)

            # Add to locked channels set
            self.locked_channels.add(channel.id)
            
            # Create status message
            status = []
            if affected_roles:
                status.append(f"✅ Modified roles: {', '.join(affected_roles)}")
            if failed_roles:
                status.append(f"❌ Failed roles: {', '.join(failed_roles)}")

            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "lock",
                f"Channel {channel.name} locked by {ctx.author} for: {reason}"
            )
            
            description = (
                f"Channel: {channel.mention}\n"
                f"Reason: {reason or 'No reason provided'}\n"
                f"Locked by: {ctx.author.mention}\n\n"
                f"**Details:**\n{chr(10).join(status)}\n\n"
                f"Note: Administrators can still send messages"
            )
            
            embed = self.ui.mod_embed(
                "🔒 Channel Locked",
                description
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to manage this channel!", ephemeral=True)
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

    @commands.hybrid_command(description="Unlock a locked channel")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        """Unlock a previously locked channel"""
        try:
            channel = channel or ctx.channel
            bot_member = ctx.guild.me
            
            # Permission check
            if not (ctx.author.guild_permissions.administrator or 
                   ctx.author.guild_permissions.manage_guild):
                embed = self.ui.error_embed(
                    "Missing Permissions",
                    "You need Administrator or Manage Server permission to use this command!"
                )
                await ctx.send(embed=embed, ephemeral=True)
                return

            # Check if channel is locked
            if channel.id not in self.locked_channels:
                embed = self.ui.mod_embed(
                    "Channel Not Locked",
                    f"{channel.mention} is not locked!"
                )
                await ctx.send(embed=embed)
                return

            # Track roles for logging
            restored_roles = []
            failed_roles = []

            # Process each role
            for role in ctx.guild.roles:
                # Skip if role is higher than bot's role
                if role >= bot_member.top_role:
                    continue
                    
                # Skip admin roles
                if role.permissions.administrator:
                    continue

                try:
                    overwrites = channel.overwrites_for(role)
                    if overwrites.send_messages is False:  # Only reset if explicitly False
                        overwrites.send_messages = None
                        if overwrites.is_empty():
                            await channel.set_permissions(
                                role, 
                                overwrite=None,
                                reason=f"Channel unlock by {ctx.author}"
                            )
                        else:
                            await channel.set_permissions(
                                role, 
                                overwrite=overwrites,
                                reason=f"Channel unlock by {ctx.author}"
                            )
                        restored_roles.append(role.name)
                except discord.Forbidden:
                    failed_roles.append(role.name)
                except Exception as e:
                    print(f"Error restoring permissions for {role.name}: {e}")
                    failed_roles.append(role.name)

            # Remove from locked channels set
            self.locked_channels.remove(channel.id)
            
            # Create status message
            status = []
            if restored_roles:
                status.append(f"✅ Restored roles: {', '.join(restored_roles)}")
            if failed_roles:
                status.append(f"❌ Failed roles: {', '.join(failed_roles)}")

            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "unlock",
                f"Channel {channel.name} unlocked by {ctx.author}"
            )
            
            description = (
                f"Channel: {channel.mention}\n"
                f"Unlocked by: {ctx.author.mention}\n\n"
                f"**Details:**\n{chr(10).join(status)}"
            )
            
            embed = self.ui.mod_embed(
                "🔓 Channel Unlocked",
                description
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to manage this channel!", ephemeral=True)
        except Exception as e:
            await self.bot.on_command_error(ctx, e)

    @commands.hybrid_command(description="Show recently deleted messages")
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx, channel: discord.TextChannel = None):
        """Show the most recently deleted message in the channel"""
        try:
            channel = channel or ctx.channel
            
            # Get all logs and find the most recent deleted message
            prefix = f"{self.db_manager.prefix}logs:{ctx.guild.id}:"
            latest_deleted = None
            latest_timestamp = None
            
            # Search through logs
            for key in db.keys():
                if key.startswith(prefix):
                    log_data = json.loads(db[key])
                    if (log_data['action'] == 'message_delete' and 
                        log_data.get('channel_id') == channel.id):
                        timestamp = datetime.fromisoformat(log_data['timestamp'])
                        if not latest_timestamp or timestamp > latest_timestamp:
                            latest_timestamp = timestamp
                            latest_deleted = log_data
            
            if not latest_deleted:
                embed = self.ui.mod_embed(
                    "No Deleted Messages",
                    f"No recently deleted messages found in {channel.mention}",
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
                
            user = ctx.guild.get_member(latest_deleted['user_id'])
            
            description = (
                f"Author: {user.mention if user else 'Unknown User'}\n"
                f"Channel: {channel.mention}\n"
                f"Deleted: <t:{int(latest_timestamp.timestamp())}:R>\n"
                f"\nContent:\n{latest_deleted.get('details', 'No content')}"
            )
            
            embed = self.ui.mod_embed(
                "📝 Deleted Message",
                description
            )
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(description="Set channel slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
        """Set the slowmode delay for a channel"""
        try:
            channel = channel or ctx.channel
            
            if seconds < 0:
                embed = self.ui.mod_embed(
                    "Invalid Duration",
                    "Slowmode delay must be 0 or higher!",
                )
                await ctx.send(embed=embed)
                return
                
            await channel.edit(slowmode_delay=seconds)
            
            # Log the action to database
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "slowmode",
                f"Slowmode set to {seconds}s in {channel.name}"
            )
            
            if seconds == 0:
                description = f"Slowmode has been disabled in {channel.mention}"
            else:
                description = f"Slowmode set to {seconds} seconds in {channel.mention}"
            
            embed = self.ui.mod_embed(
                "⏱️ Slowmode Updated",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.ui.mod_embed(
                "Error",
                str(e),
            )
            await ctx.send(embed=error_embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Store deleted messages for snipe command"""
        if message.author.bot or not message.guild:
            return
            
        await self.db_manager.log_event(
            message.guild.id,
            message.author.id,
            "message_delete",
            message.content,
            channel_id=message.channel.id
        )

async def setup(bot):
    await bot.add_cog(Moderation(bot))