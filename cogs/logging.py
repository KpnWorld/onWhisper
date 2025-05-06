import discord
from discord.ext import commands
from typing import Optional, Union
from datetime import datetime
import asyncio

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._log_locks = {}  # Prevent race conditions in log channels

    async def _get_log_channel(self, guild_id: int, log_type: str) -> Optional[discord.TextChannel]:
        """Get the configured log channel with error handling"""
        try:
            config = await self.bot.db_manager.safe_operation(
                'get_section',
                self.bot.db_manager.get_section,
                guild_id,
                'logs_config'
            )
            if not config or not config.get('enabled'):
                return None
                
            channel_id = config.get(f'{log_type}_channel')
            if not channel_id:
                return None
                
            return self.bot.get_channel(int(channel_id))
        except Exception as e:
            print(f"Error getting log channel: {e}")
            return None

    async def log_event(self, guild_id: int, log_type: str, content: Union[str, discord.Embed]) -> bool:
        """Log an event to the appropriate channel with transaction support"""
        try:
            # Use transaction to ensure atomic logging
            async with await self.bot.db_manager.transaction(guild_id, 'logs') as txn:
                channel = await self._get_log_channel(guild_id, log_type)
                if not channel:
                    return False

                # Acquire lock for this channel to prevent race conditions
                lock_key = f"{guild_id}:{channel.id}"
                if lock_key not in self._log_locks:
                    self._log_locks[lock_key] = asyncio.Lock()

                async with self._log_locks[lock_key]:
                    if isinstance(content, discord.Embed):
                        await channel.send(embed=content)
                    else:
                        await channel.send(content)

                    # Log to database with safe operation
                    await self.bot.db_manager.safe_operation(
                        'add_log',
                        self.bot.db_manager.add_log,
                        guild_id,
                        {
                            'type': log_type,
                            'content': str(content),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    return True

        except Exception as e:
            print(f"Error logging event: {e}")
            return False

    async def _should_log(self, guild_id: int, category: str, event_type: str) -> tuple[bool, Optional[discord.TextChannel]]:
        """Check if event should be logged and get log channel"""
        try:
            logs = await self.bot.db_manager.get_section(guild_id, 'logs')
            if not logs['enabled']:
                return False, None

            # Check if event type is enabled
            log_types = logs.get('log_types', {})
            if (category not in log_types or 
                event_type not in log_types[category]):
                return False, None

            # Get log channel
            channel_id = logs.get('log_channel')
            if not channel_id:
                return False, None

            channel = self.bot.get_channel(int(channel_id))
            return bool(channel), channel

        except Exception as e:
            print(f"Error checking logging status: {e}")
            return False, None

    # Member Events
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        should_log, channel = await self._should_log(member.guild.id, 'member', 'join')
        if should_log and channel:
            embed = self.bot.ui_manager.info_embed(
                "Member Joined",
                f"{member.mention} joined the server"
            ).add_field(
                name="Account Created",
                value=discord.utils.format_dt(member.created_at, style='R')
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        should_log, channel = await self._should_log(member.guild.id, 'member', 'leave')
        if should_log and channel:
            roles = [role.mention for role in member.roles if role != member.guild.default_role]
            embed = self.bot.ui_manager.info_embed(
                "Member Left",
                f"{member.mention} left the server"
            )
            if roles:
                embed.add_field(name="Roles", value=" ".join(roles))
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

    # Message Events
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        try:
            embed = discord.Embed(
                title="Message Deleted",
                description=message.content or "No content",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Channel", value=message.channel.mention)
            embed.add_field(name="Author", value=message.author.mention)
            
            if message.attachments:
                embed.add_field(
                    name="Attachments",
                    value="\n".join(a.url for a in message.attachments),
                    inline=False
                )

            await self.log_event(message.guild.id, "message", embed)
        except Exception as e:
            print(f"Error logging deleted message: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return

        try:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            embed.add_field(name="Channel", value=before.channel.mention)
            embed.add_field(name="Author", value=before.author.mention)
            embed.add_field(
                name="Jump to Message",
                value=f"[Click Here]({after.jump_url})"
            )

            await self.log_event(before.guild.id, "message", embed)
        except Exception as e:
            print(f"Error logging edited message: {e}")

    # Channel Events
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        should_log, log_channel = await self._should_log(channel.guild.id, 'server', 'channel_create')
        if should_log and log_channel:
            embed = self.bot.ui_manager.mod_embed(
                "Channel Created",
                f"Channel {channel.mention} was created"
            )
            embed.add_field(name="Type", value=str(channel.type))
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        should_log, log_channel = await self._should_log(channel.guild.id, 'server', 'channel_delete')
        if should_log and log_channel:
            embed = self.bot.ui_manager.mod_embed(
                "Channel Deleted",
                f"Channel #{channel.name} was deleted"
            )
            embed.add_field(name="Type", value=str(channel.type))
            await log_channel.send(embed=embed)

    # Role Events
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        try:
            # Use safe operation to check if we should log
            should_log, channel = await self.bot.db_manager.safe_operation(
                'check_should_log',
                self._should_log,
                role.guild.id,
                'server',
                'role_update'
            )

            if should_log and channel:
                # Get role info with error handling
                role_info = {
                    'name': role.name,
                    'color': str(role.color),
                    'permissions': role.permissions.value,
                    'position': role.position,
                    'hoisted': role.hoist,
                    'mentionable': role.mentionable
                }

                # Log event using transaction
                async with await self.bot.db_manager.transaction(role.guild.id, 'logs') as txn:
                    embed = self.bot.ui_manager.mod_embed(
                        "Role Created",
                        f"Role {role.mention} was created\n" +
                        f"Color: {role_info['color']}\n" +
                        f"Position: {role_info['position']}\n" +
                        f"Hoisted: {role_info['hoisted']}\n" +
                        f"Mentionable: {role_info['mentionable']}" 
                    )
                    await channel.send(embed=embed)

                    # Log to database
                    await self.bot.db_manager.log_event(
                        role.guild.id,
                        0,  # System event
                        "role_create",
                        role_info
                    )

        except Exception as e:
            print(f"Error logging role creation: {e}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        should_log, channel = await self._should_log(role.guild.id, 'server', 'role_update')
        if should_log and channel:
            embed = self.bot.ui_manager.mod_embed(
                "Role Deleted",
                f"Role @{role.name} was deleted"
            )
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Log role updates"""
        should_log, channel = await self._should_log(before.guild.id, 'server', 'role_update')
        if should_log and channel:
            changes = []
            if before.name != after.name:
                changes.append(f"Name: {before.name} → {after.name}")
            if before.color != after.color:
                changes.append(f"Color: {before.color} → {after.color}")
            if before.permissions != after.permissions:
                changes.append("Permissions were updated")

            if changes:
                embed = self.bot.ui_manager.mod_embed(
                    "Role Updated",
                    f"Role {after.mention} was updated"
                )
                embed.add_field(name="Changes", value="\n".join(changes))
                await channel.send(embed=embed)

    # Moderation Event Methods
    async def log_warn(self, guild_id: int, user: discord.Member, moderator: discord.Member, reason: str):
        """Log warning"""
        should_log, channel = await self._should_log(guild_id, 'moderation', 'warn')
        if should_log and channel:
            embed = self.bot.ui_manager.mod_embed(
                "Member Warned",
                f"{user.mention} was warned by {moderator.mention}",
                moderator
            )
            embed.add_field(name="Reason", value=reason)
            await channel.send(embed=embed)

    async def log_timeout(self, guild_id: int, user: discord.Member, moderator: discord.Member, duration: int, reason: str):
        """Log timeout"""
        should_log, channel = await self._should_log(guild_id, 'moderation', 'timeout')
        if should_log and channel:
            embed = self.bot.ui_manager.mod_embed(
                "Member Timed Out",
                f"{user.mention} was timed out by {moderator.mention}",
                moderator
            )
            embed.add_field(name="Duration", value=f"{duration} minutes")
            embed.add_field(name="Reason", value=reason)
            await channel.send(embed=embed)

    async def log_kick(self, guild_id: int, user: discord.Member, moderator: discord.Member, reason: str):
        """Log kick"""
        should_log, channel = await self._should_log(guild_id, 'moderation', 'kick')
        if should_log and channel:
            embed = self.bot.ui_manager.mod_embed(
                "Member Kicked",
                f"{user.mention} was kicked by {moderator.mention}",
                moderator
            )
            embed.add_field(name="Reason", value=reason)
            await channel.send(embed=embed)

    async def log_ban(self, guild_id: int, user: discord.Member, moderator: discord.Member, reason: str):
        """Log ban"""
        should_log, channel = await self._should_log(guild_id, 'moderation', 'ban')
        if should_log and channel:
            embed = self.bot.ui_manager.mod_embed(
                "Member Banned",
                f"{user.mention} was banned by {moderator.mention}",
                moderator
            )
            embed.add_field(name="Reason", value=reason)
            await channel.send(embed=embed)

    async def log_lockdown(self, guild_id: int, channel: discord.TextChannel, moderator: discord.Member, reason: str):
        """Log channel lockdown"""
        should_log, log_channel = await self._should_log(guild_id, 'moderation', 'lockdown')
        if should_log and log_channel:
            embed = self.bot.ui_manager.mod_embed(
                "Channel Locked",
                f"{channel.mention} was locked by {moderator.mention}",
                moderator
            )
            embed.add_field(name="Reason", value=reason)
            await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))