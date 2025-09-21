# utils/logging_manager.py

import discord
from discord.ext import commands
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from utils.config import ConfigManager

logger = logging.getLogger("LoggingManager")

class LogCategory:
    """Represents a logging category with its configuration"""
    
    def __init__(self, name: str, emoji: str, color: discord.Color, 
                 enabled_key: str, channel_key: str):
        self.name = name
        self.emoji = emoji
        self.color = color
        self.enabled_key = enabled_key
        self.channel_key = channel_key

# Define all logging categories
LOG_CATEGORIES = {
    "member": LogCategory("Member Events", "🚪", discord.Color.green(), 
                         "log_member_events", "log_member_channel"),
    "message": LogCategory("Message Events", "💬", discord.Color.blue(),
                          "log_message_events", "log_message_channel"),
    "moderation": LogCategory("Moderation Events", "🛡️", discord.Color.red(),
                             "log_moderation_events", "log_moderation_channel"),
    "voice": LogCategory("Voice Events", "🔊", discord.Color.purple(),
                        "log_voice_events", "log_voice_channel"),
    "channel": LogCategory("Channel Events", "📂", discord.Color.orange(),
                          "log_channel_events", "log_channel_channel"),
    "role": LogCategory("Role Events", "🎭", discord.Color.gold(),
                       "log_role_events", "log_role_channel"),
    "bot": LogCategory("Bot Events", "🤖", discord.Color.dark_gray(),
                      "log_bot_events", "log_bot_channel"),
    "whisper": LogCategory("Whisper Events", "🤫", discord.Color.blurple(),
                          "log_whisper_events", "log_whisper_channel")
}


class LoggingManager:
    """Unified logging manager for all bot events"""
    
    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config
    
    async def is_enabled(self, guild_id: int, category: str) -> bool:
        """Check if logging is enabled for a specific category"""
        # Check master logging toggle
        master_enabled = await self.config.get(guild_id, "unified_logging_enabled", True)
        if not master_enabled:
            return False
        
        # Check category-specific toggle
        if category not in LOG_CATEGORIES:
            return False
        
        log_cat = LOG_CATEGORIES[category]
        return await self.config.get(guild_id, log_cat.enabled_key, True)
    
    async def get_log_channel(self, guild: discord.Guild, category: str) -> Optional[discord.TextChannel]:
        """Get the configured log channel for a specific category"""
        if category not in LOG_CATEGORIES:
            return None
        
        log_cat = LOG_CATEGORIES[category]
        channel_id = await self.config.get(guild.id, log_cat.channel_key)
        
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                return channel
        
        # Fallback to mod log channel for moderation events
        if category == "moderation":
            mod_log_id = await self.config.get(guild.id, "mod_log_channel")
            if mod_log_id:
                mod_channel = guild.get_channel(mod_log_id)
                if mod_channel and isinstance(mod_channel, discord.TextChannel):
                    return mod_channel
        
        return None
    
    async def log_event(self, guild: discord.Guild, category: str, title: str, 
                       description: str, fields: Optional[Dict[str, Any]] = None,
                       user: Optional[discord.Member] = None, 
                       target: Optional[discord.Member] = None) -> bool:
        """
        Log an event to the appropriate channel
        
        Args:
            guild: The guild where the event occurred
            category: The log category (member, message, moderation, etc.)
            title: The title of the log entry
            description: The description of the event
            fields: Optional dictionary of fields to add to embed
            user: Optional user who performed the action
            target: Optional target user affected by the action
            
        Returns:
            bool: True if log was sent successfully, False otherwise
        """
        try:
            # Check if logging is enabled for this category
            if not await self.is_enabled(guild.id, category):
                return False
            
            # Get the log channel
            log_channel = await self.get_log_channel(guild, category)
            if not log_channel:
                logger.debug(f"No log channel configured for category '{category}' in guild {guild.id}")
                return False
            
            # Get category configuration
            if category not in LOG_CATEGORIES:
                logger.error(f"Unknown log category: {category}")
                return False
            
            log_cat = LOG_CATEGORIES[category]
            
            # Create embed
            embed = discord.Embed(
                title=f"{log_cat.emoji} {title}",
                description=description,
                color=log_cat.color,
                timestamp=datetime.utcnow()
            )
            
            # Add user information if provided
            if user:
                embed.add_field(
                    name="User",
                    value=f"{user.mention}\n({user.display_name})",
                    inline=True
                )
            
            # Add target information if provided
            if target:
                embed.add_field(
                    name="Target",
                    value=f"{target.mention}\n({target.display_name})",
                    inline=True
                )
            
            # Add custom fields if provided
            if fields:
                for field_name, field_value in fields.items():
                    if isinstance(field_value, dict):
                        embed.add_field(
                            name=field_name,
                            value=field_value.get("value", "N/A"),
                            inline=field_value.get("inline", False)
                        )
                    else:
                        embed.add_field(
                            name=field_name,
                            value=str(field_value),
                            inline=False
                        )
            
            # Add footer with category
            embed.set_footer(text=f"Category: {log_cat.name}")
            
            # Send the log
            await log_channel.send(embed=embed)
            logger.debug(f"Sent {category} log to {log_channel.name} in guild {guild.id}")
            return True
            
        except discord.Forbidden:
            logger.warning(f"No permission to send logs to channel in guild {guild.id}")
            return False
        except discord.HTTPException as e:
            logger.error(f"HTTP error sending log in guild {guild.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending log in guild {guild.id}: {e}")
            return False
    
    async def log_member_join(self, member: discord.Member) -> bool:
        """Log when a member joins the server"""
        return await self.log_event(
            guild=member.guild,
            category="member",
            title="Member Joined",
            description=f"**{member.display_name}** joined the server",
            fields={
                "Account Created": {
                    "value": discord.utils.format_dt(member.created_at, 'R'),
                    "inline": True
                },
                "Member Count": {
                    "value": str(member.guild.member_count),
                    "inline": True
                }
            },
            target=member
        )
    
    async def log_member_leave(self, member: discord.Member) -> bool:
        """Log when a member leaves the server"""
        return await self.log_event(
            guild=member.guild,
            category="member",
            title="Member Left",
            description=f"**{member.display_name}** left the server",
            fields={
                "Joined": {
                    "value": discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Unknown",
                    "inline": True
                },
                "Member Count": {
                    "value": str(member.guild.member_count),
                    "inline": True
                }
            },
            target=member
        )
    
    async def log_message_delete(self, message: discord.Message) -> bool:
        """Log when a message is deleted"""
        if message.author.bot:
            return False  # Don't log bot message deletions
        
        content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
        if not content:
            content = "*No text content*"
        
        return await self.log_event(
            guild=message.guild,
            category="message",
            title="Message Deleted",
            description=f"Message deleted in {message.channel.mention}",
            fields={
                "Content": {"value": f"```{content}```", "inline": False},
                "Channel": {"value": message.channel.mention, "inline": True},
                "Message ID": {"value": str(message.id), "inline": True}
            },
            target=message.author
        )
    
    async def log_message_edit(self, before: discord.Message, after: discord.Message) -> bool:
        """Log when a message is edited"""
        if before.author.bot or before.content == after.content:
            return False
        
        before_content = before.content[:500] + "..." if len(before.content) > 500 else before.content
        after_content = after.content[:500] + "..." if len(after.content) > 500 else after.content
        
        return await self.log_event(
            guild=after.guild,
            category="message",
            title="Message Edited",
            description=f"Message edited in {after.channel.mention}",
            fields={
                "Before": {"value": f"```{before_content}```", "inline": False},
                "After": {"value": f"```{after_content}```", "inline": False},
                "Channel": {"value": after.channel.mention, "inline": True},
                "Jump to Message": {"value": f"[Click here]({after.jump_url})", "inline": True}
            },
            target=after.author
        )
    
    async def log_moderation_action(self, guild: discord.Guild, action: str, 
                                  moderator: discord.Member, target: discord.Member,
                                  reason: Optional[str] = None, duration: Optional[str] = None) -> bool:
        """Log moderation actions"""
        fields = {}
        if reason:
            fields["Reason"] = {"value": reason, "inline": False}
        if duration:
            fields["Duration"] = {"value": duration, "inline": True}
        
        return await self.log_event(
            guild=guild,
            category="moderation",
            title=f"Moderation: {action}",
            description=f"**{action}** action performed",
            fields=fields,
            user=moderator,
            target=target
        )
    
    async def log_whisper_created(self, guild: discord.Guild, user: discord.Member,
                                thread: discord.Thread, whisper_id: str, reason: str) -> bool:
        """Log whisper thread creation"""
        return await self.log_event(
            guild=guild,
            category="whisper",
            title="Whisper Created",
            description=f"New whisper thread **{whisper_id}** created",
            fields={
                "Thread": {"value": thread.mention, "inline": True},
                "Whisper ID": {"value": whisper_id, "inline": True},
                "Reason": {"value": reason or "No reason provided", "inline": False}
            },
            target=user
        )
    
    async def log_bot_command(self, ctx: commands.Context, command_name: str) -> bool:
        """Log bot command usage"""
        return await self.log_event(
            guild=ctx.guild,
            category="bot",
            title="Command Used",
            description=f"Command `{command_name}` executed",
            fields={
                "Channel": {"value": ctx.channel.mention, "inline": True},
                "Command": {"value": f"`{command_name}`", "inline": True}
            },
            user=ctx.author
        )