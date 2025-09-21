# cogs/moderation.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Union
from datetime import datetime, timedelta
import logging
import asyncio

from utils.db_manager import DBManager
from utils.config import ConfigManager

logger = logging.getLogger("onWhisper.Moderation")


class ModerationCog(commands.Cog):
    """⚔️ Moderation commands for server management"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db_manager
        self.config: ConfigManager = bot.config_manager

    async def _check_mod_permissions(self, ctx_or_interaction: Union[commands.Context, discord.Interaction]) -> bool:
        """Check if user has moderation permissions"""
        # Handle both Context and Interaction objects
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.user
        else:  # Context
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.author
            
        if not guild or not isinstance(user, discord.Member):
            return False
            
        # Check if user is admin or has manage server permission
        if user.guild_permissions.administrator or user.guild_permissions.manage_guild:
            return True
            
        # Check for mod role from config
        mod_enabled = await self.config.get(guild.id, "moderation_enabled", True)
        if not mod_enabled:
            return False
            
        return user.guild_permissions.kick_members or user.guild_permissions.ban_members

    async def _send_user_dm(self, user: discord.abc.User, guild: discord.Guild, action: str, reason: str, moderator: discord.abc.User) -> bool:
        """Attempt to DM user about moderation action. Returns True if successful."""
        try:
            embed = discord.Embed(
                title=f"⚠️ {action.title()} from {guild.name}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Action", value=action.title(), inline=True)
            embed.add_field(name="Moderator", value=str(moderator), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    # 👥 Member Management Commands
    
    @commands.hybrid_command(name="kick", description="Remove a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Kicks a member from the server"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.kick_members:
            return await ctx.send("❌ I don't have permission to kick members!", ephemeral=True)
            
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot kick this member (role hierarchy)!", ephemeral=True)
            
        try:
            # Send DM first
            dm_sent = await self._send_user_dm(member, ctx.guild, "kick", reason, ctx.author)
            
            # Kick the member
            await member.kick(reason=f"By {ctx.author}: {reason}")
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    member.id,
                    "KICK",
                    reason,
                    ctx.author.id
                )
            
            logger.info(f"Kicked {member} from {ctx.guild} by {ctx.author}: {reason}")
            
            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick that user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in kick command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    @commands.hybrid_command(name="ban", description="Ban a member permanently from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban")
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Bans a member from the server"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.ban_members:
            return await ctx.send("❌ I don't have permission to ban members!", ephemeral=True)
            
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot ban this member (role hierarchy)!", ephemeral=True)
            
        try:
            # Send DM first
            dm_sent = await self._send_user_dm(member, ctx.guild, "ban", reason, ctx.author)
            
            # Ban the member
            await member.ban(reason=f"By {ctx.author}: {reason}")
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    member.id,
                    "BAN",
                    reason,
                    ctx.author.id
                )
            
            logger.info(f"Banned {member} from {ctx.guild} by {ctx.author}: {reason}")
            
            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban that user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in ban command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Unban a user from the server")
    @app_commands.describe(user="User to unban (by ID or mention)")
    async def unban(self, ctx: commands.Context, user: discord.User):
        """Unbans a user from the server"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.ban_members:
            return await ctx.send("❌ I don't have permission to unban members!", ephemeral=True)
            
        try:
            # Check if user is actually banned
            try:
                await ctx.guild.fetch_ban(user)
            except discord.NotFound:
                return await ctx.send("❌ This user is not banned!", ephemeral=True)
            
            # Unban the user
            await ctx.guild.unban(user, reason=f"By {ctx.author}")
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    user.id,
                    "UNBAN",
                    f"Unbanned by {ctx.author}",
                    ctx.author.id
                )
            
            logger.info(f"Unbanned {user} from {ctx.guild} by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unban users!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in unban command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    # 🔇 Mute & Timeout Commands
    
    @commands.hybrid_command(name="mute", description="Timeout a member for a specified duration")
    @app_commands.describe(member="Member to timeout", duration="Duration in minutes (1-40320)", reason="Reason for the timeout")
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: int, *, reason: str = "No reason provided"):
        """Timeouts a member using Discord's built-in timeout system"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.moderate_members:
            return await ctx.send("❌ I don't have permission to timeout members!", ephemeral=True)
            
        if duration < 1 or duration > 40320:  # Discord's limit: 28 days
            return await ctx.send("❌ Duration must be between 1 minute and 28 days (40320 minutes)!", ephemeral=True)
            
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot timeout this member (role hierarchy)!", ephemeral=True)
            
        try:
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=f"By {ctx.author}: {reason}")
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    member.id,
                    "MUTE",
                    f"{reason} (Duration: {duration} minutes)",
                    ctx.author.id
                )
            
            logger.info(f"Timed out {member} for {duration} minutes by {ctx.author}: {reason}")
            
            embed = discord.Embed(
                title="🔇 Member Muted",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to timeout that user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in mute command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    @commands.hybrid_command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Removes timeout from a member"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.moderate_members:
            return await ctx.send("❌ I don't have permission to remove timeouts!", ephemeral=True)
            
        if not member.is_timed_out():
            return await ctx.send("❌ This member is not timed out!", ephemeral=True)
            
        try:
            await member.timeout(None, reason=f"Unmuted by {ctx.author}")
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    member.id,
                    "UNMUTE",
                    f"Unmuted by {ctx.author}",
                    ctx.author.id
                )
            
            logger.info(f"Unmuted {member} by {ctx.author}")
            
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unmute that user!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in unmute command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    # ⚠️ Warning Commands
    
    @commands.hybrid_command(name="warn", description="Issue a warning to a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Issues a warning to a member"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        try:
            # Send DM first
            dm_sent = await self._send_user_dm(member, ctx.guild, "warning", reason, ctx.author)
            
            # Log to database
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    member.id,
                    "WARN",
                    reason,
                    ctx.author.id
                )
            
            logger.info(f"Warned {member} by {ctx.author}: {reason}")
            
            embed = discord.Embed(
                title="⚠️ Member Warned",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in warn command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    @commands.hybrid_command(name="warnings", description="Display all warnings for a member")
    @app_commands.describe(member="Member to check warnings for")
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        """Shows all warnings for a member"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        try:
            if not ctx.guild:
                return await ctx.send("❌ This command can only be used in servers!", ephemeral=True)
                
            # Get warnings from database
            warnings = await self.db.get_moderation_logs(ctx.guild.id, member.id)
            warn_list = [log for log in warnings if log["action"] == "WARN"]
            
            if not warn_list:
                embed = discord.Embed(
                    title="📋 Member Warnings",
                    description=f"{member} has no warnings.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="📋 Member Warnings",
                    description=f"{member} has {len(warn_list)} warning(s):",
                    color=discord.Color.orange()
                )
                
                for i, warning in enumerate(warn_list[:10], 1):  # Show up to 10 warnings
                    mod = ctx.guild.get_member(warning["moderator_id"])
                    mod_name = str(mod) if mod else f"ID: {warning['moderator_id']}"
                    
                    embed.add_field(
                        name=f"Warning #{warning['case_id']}",
                        value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod_name}\n**Date:** {warning['timestamp']}",
                        inline=False
                    )
                
                if len(warn_list) > 10:
                    embed.add_field(name="Note", value=f"Showing 10 of {len(warn_list)} warnings.", inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in warnings command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    # 📜 Moderation Logs
    
    @commands.hybrid_command(name="modlogs", description="Display all moderation actions for a member")
    @app_commands.describe(member="Member to check moderation logs for")
    async def modlogs(self, ctx: commands.Context, member: discord.Member):
        """Shows all moderation actions for a member"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        try:
            if not ctx.guild:
                return await ctx.send("❌ This command can only be used in servers!", ephemeral=True)
                
            # Get all moderation logs from database
            logs = await self.db.get_moderation_logs(ctx.guild.id, member.id)
            
            if not logs:
                embed = discord.Embed(
                    title="📜 Moderation Logs",
                    description=f"{member} has no moderation history.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="📜 Moderation Logs",
                    description=f"{member} has {len(logs)} moderation action(s):",
                    color=discord.Color.blue()
                )
                
                for i, log in enumerate(logs[:10], 1):  # Show up to 10 logs
                    mod = ctx.guild.get_member(log["moderator_id"])
                    mod_name = str(mod) if mod else f"ID: {log['moderator_id']}"
                    
                    # Color code by action
                    action_emoji = {
                        "WARN": "⚠️",
                        "MUTE": "🔇", 
                        "UNMUTE": "🔊",
                        "KICK": "👢",
                        "BAN": "🔨",
                        "UNBAN": "✅",
                        "PURGE": "🧹",
                        "LOCK": "🔒",
                        "UNLOCK": "🔓"
                    }.get(log["action"], "📝")
                    
                    embed.add_field(
                        name=f"{action_emoji} Case #{log['case_id']} - {log['action']}",
                        value=f"**Reason:** {log['reason']}\n**Moderator:** {mod_name}\n**Date:** {log['timestamp']}",
                        inline=False
                    )
                
                if len(logs) > 10:
                    embed.add_field(name="Note", value=f"Showing 10 of {len(logs)} actions.", inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in modlogs command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    # 🧹 Channel Management Commands
    
    @commands.hybrid_command(name="purge", description="Bulk delete messages from the channel")
    @app_commands.describe(limit="Number of messages to delete (1-100)")
    async def purge(self, ctx: commands.Context, limit: int):
        """Bulk deletes messages from the current channel"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.manage_messages:
            return await ctx.send("❌ I don't have permission to delete messages!", ephemeral=True)
            
        if limit < 1 or limit > 100:
            return await ctx.send("❌ Please provide a number between 1 and 100.", ephemeral=True)
            
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send("❌ This command can only be used in text channels!", ephemeral=True)
            
        try:
            # Handle deferring differently for slash vs prefix commands
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            
            deleted = await ctx.channel.purge(limit=limit)
            deleted_count = len(deleted)
            
            # Log the action
            if ctx.guild and ctx.channel:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    ctx.author.id,
                    "PURGE",
                    f"Purged {deleted_count} messages in #{ctx.channel.name}",
                    ctx.author.id
                )
            
            logger.info(f"Purged {deleted_count} messages in #{ctx.channel.name} by {ctx.author}")
            
            # Send response based on command type
            response = f"✨ Successfully deleted {deleted_count} message{'s' if deleted_count != 1 else ''}."
            if ctx.interaction:
                await ctx.followup.send(response, ephemeral=True)
            else:
                await ctx.send(response)
            
        except discord.Forbidden:
            error_msg = "❌ I don't have permission to delete messages!"
            if ctx.interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)
        except Exception as e:
            logger.error(f"Error in purge command: {e}")
            error_msg = "❌ An unexpected error occurred."
            if ctx.interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @commands.hybrid_command(name="lock", description="Lock a channel to prevent @everyone from sending messages")
    @app_commands.describe(channel="Channel to lock (defaults to current channel)")
    async def lock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Locks a channel to prevent @everyone from sending messages"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.send("❌ I don't have permission to manage channels!", ephemeral=True)
            
        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            return await ctx.send("❌ This command can only be used on text channels!", ephemeral=True)
            
        try:
            await target_channel.set_permissions(
                ctx.guild.default_role,
                send_messages=False,
                reason=f"Channel locked by {ctx.author}"
            )
            
            # Log the action
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    ctx.author.id,
                    "LOCK",
                    f"Locked channel #{target_channel.name}",
                    ctx.author.id
                )
            
            logger.info(f"Locked #{target_channel.name} by {ctx.author}")
            
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description=f"{target_channel.mention} has been locked.",
                color=discord.Color.red()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to modify channel permissions!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in lock command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)

    @commands.hybrid_command(name="unlock", description="Unlock a channel to restore @everyone sending messages")
    @app_commands.describe(channel="Channel to unlock (defaults to current channel)")
    async def unlock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Unlocks a channel to restore @everyone sending messages"""
        if not await self._check_mod_permissions(ctx):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild or not ctx.guild.me or not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.send("❌ I don't have permission to manage channels!", ephemeral=True)
            
        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            return await ctx.send("❌ This command can only be used on text channels!", ephemeral=True)
            
        try:
            await target_channel.set_permissions(
                ctx.guild.default_role,
                send_messages=None,  # Reset to default
                reason=f"Channel unlocked by {ctx.author}"
            )
            
            # Log the action
            if ctx.guild:
                await self.db.log_moderation_action(
                    ctx.guild.id,
                    ctx.author.id,
                    "UNLOCK",
                    f"Unlocked channel #{target_channel.name}",
                    ctx.author.id
                )
            
            logger.info(f"Unlocked #{target_channel.name} by {ctx.author}")
            
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description=f"{target_channel.mention} has been unlocked.",
                color=discord.Color.green()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to modify channel permissions!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in unlock command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the moderation cog"""
    await bot.add_cog(ModerationCog(bot))