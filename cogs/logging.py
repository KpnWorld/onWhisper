import discord
from discord.ext import commands
from discord.commands import slash_command, option
from typing import Dict, Optional
import json
from datetime import datetime, timedelta
import io

class Logging(commands.Cog):
    """Logging system for server events"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @slash_command(name="setlog")
    @commands.has_permissions(administrator=True)
    @option("channel", description="The channel to set for logging", type=discord.TextChannel)
    async def setlog(self, ctx, channel: discord.TextChannel):
        """Set logging channel for the server"""
        await self.bot.db.set_logging_settings(
            ctx.guild.id,
            channel.id,
            "{}"  # Default empty options
        )
        await ctx.respond(f"✅ Logging channel set to {channel.mention}")

    @slash_command(name="setlogoptions")
    @commands.has_permissions(administrator=True)
    @option("message_edits", description="Log message edits", type=bool)
    @option("message_deletes", description="Log message deletes", type=bool)
    @option("member_joins", description="Log member joins", type=bool)
    @option("member_leaves", description="Log member leaves", type=bool)
    @option("member_bans", description="Log member bans", type=bool)
    @option("member_unbans", description="Log member unbans", type=bool)
    async def setlogoptions(
        self,
        ctx: discord.ApplicationContext,
        message_edits: bool,
        message_deletes: bool,
        member_joins: bool,
        member_leaves: bool,
        member_bans: bool,
        member_unbans: bool
    ):
        """Set logging options for the server"""
        options = {
            "message_edits": message_edits,
            "message_deletes": message_deletes,
            "member_joins": member_joins,
            "member_leaves": member_leaves,
            "member_bans": member_bans,
            "member_unbans": member_unbans
        }
        
        await self.bot.db.set_logging_settings(
            ctx.guild.id,
            None,  # Don't change channel
            json.dumps(options)
        )
        
        enabled = [k for k, v in options.items() if v]
        disabled = [k for k, v in options.items() if not v]
        
        embed = discord.Embed(
            title="Logging Options Updated",
            color=discord.Color.green()
        )
        
        if enabled:
            embed.add_field(
                name="Enabled",
                value="\n".join(f"• {opt.title()}" for opt in enabled),
                inline=True
            )
            
        if disabled:
            embed.add_field(
                name="Disabled",
                value="\n".join(f"• {opt.title()}" for opt in disabled),
                inline=True
            )
            
        await ctx.respond(embed=embed)

    async def _get_log_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """Get the configured logging channel for the guild
        
        Parameters
        ----------
        guild_id: int
            The ID of the guild to get the log channel for
            
        Returns
        -------
        Optional[discord.TextChannel]
            The configured logging channel, or None if not set
        """
        settings = await self.bot.db.get_logging_settings(guild_id)
        if not settings or not settings["log_channel_id"]:
            return None
            
        channel = self.bot.get_channel(settings["log_channel_id"])
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _should_log(self, guild_id: int, event_type: str) -> bool:
        """Check if an event type should be logged based on settings
        
        Parameters
        ----------
        guild_id: int
            The ID of the guild to check settings for
        event_type: str
            The type of event to check
            
        Returns
        -------
        bool
            Whether the event should be logged
        """
        settings = await self.bot.db.get_logging_settings(guild_id)
        if not settings or not settings["options_json"]:
            return False
            
        try:
            options = json.loads(settings["options_json"])
            return options.get(event_type, False)
        except (json.JSONDecodeError, KeyError):
            return False

    async def _log_to_channel(
        self,
        guild: discord.Guild,
        event_type: str,
        embed: discord.Embed,
        file: Optional[discord.File] = None
    ) -> None:
        """Send a log entry to the logging channel
        
        Parameters
        ----------
        guild: discord.Guild
            The guild to log to
        event_type: str
            The type of event being logged
        embed: discord.Embed
            The embed containing the log information
        file: Optional[discord.File]
            Optional file attachment
        """
        channel = await self._get_log_channel(guild.id)
        if not channel or not await self._should_log(guild.id, event_type):
            return
            
        try:
            if file:
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)
                
            # Store in database for history
            await self.bot.db.log_event(
                guild.id,
                event_type,
                embed.description or "No description provided"
            )
        except discord.Forbidden:
            pass  # Bot doesn't have permission
        except discord.HTTPException:
            pass  # Failed to send message    @slash_command(name="logsummary")
    @commands.has_permissions(view_audit_log=True)
    @option("days", description="Number of days to summarize", type=int, min_value=1, max_value=30, default=7)
    async def logsummary(
        self,
        ctx: discord.ApplicationContext,
        days: int
    ):
        """Generate a summary of recent server activity"""
        async with ctx.typing():
            # Get logs for the specified period
            logs = await self.bot.db.get_logs(ctx.guild.id, limit=1000)
            
            if not logs:
                await ctx.respond("No logs found for the specified period!")
                return
                
            # Filter logs by date
            cutoff = datetime.now() - timedelta(days=days)
            recent_logs = [
                log for log in logs
                if datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00')) > cutoff
            ]
            
            if not recent_logs:
                await ctx.respond(f"No activity in the last {days} days!")
                return
            
            # Categorize events
            categories: Dict[str, int] = {
                "messages": 0,
                "members": 0,
                "roles": 0,
                "channels": 0,
                "moderation": 0,
                "voice": 0
            }
            
            for log in recent_logs:
                event_type = log["event_type"].lower()
                if "message" in event_type:
                    categories["messages"] += 1
                elif "member" in event_type:
                    categories["members"] += 1
                elif "role" in event_type:
                    categories["roles"] += 1
                elif "channel" in event_type:
                    categories["channels"] += 1
                elif any(x in event_type for x in ["ban", "kick", "mute", "warn"]):
                    categories["moderation"] += 1
                elif "voice" in event_type:
                    categories["voice"] += 1
            
            # Create summary embed
            embed = discord.Embed(
                title=f"Server Activity Summary - Last {days} Days",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for category, count in categories.items():
                if count > 0:
                    embed.add_field(
                        name=category.title(),
                        value=f"{count} events",
                        inline=True
                    )
            
            # Generate detailed log file
            if recent_logs:
                log_content = "Timestamp | Event Type | Description\n"
                log_content += "-" * 60 + "\n"
                
                for log in recent_logs:
                    timestamp = log["timestamp"].split(".")[0]  # Remove microseconds
                    log_content += f"{timestamp} | {log['event_type']} | {log['description']}\n"
                
                file = discord.File(
                    io.BytesIO(log_content.encode('utf-8')),
                    filename=f"log_summary_{ctx.guild.id}.txt"
                )
                
                await ctx.respond(embed=embed, file=file)
            else:
                await ctx.respond(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild and not message.author.bot:
            embed = discord.Embed(
                title="Message Deleted",
                description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            if message.content:
                if len(message.content) > 1024:
                    embed.add_field(
                        name="Content",
                        value=f"{message.content[:1021]}..."
                    )
                else:
                    embed.add_field(name="Content", value=message.content)
                    
            if message.attachments:
                embed.add_field(
                    name="Attachments",
                    value="\n".join(a.filename for a in message.attachments)
                )
            
            await self._log_to_channel(message.guild, "message_delete", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild and not before.author.bot and before.content != after.content:
            embed = discord.Embed(
                title="Message Edited",
                description=f"Message by {before.author.mention} edited in {before.channel.mention}\n[Jump to Message]({after.jump_url})",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if len(before.content) > 1024:
                embed.add_field(
                    name="Before",
                    value=f"{before.content[:1021]}..."
                )
            else:
                embed.add_field(name="Before", value=before.content or "*Empty*")
                
            if len(after.content) > 1024:
                embed.add_field(
                    name="After",
                    value=f"{after.content[:1021]}..."
                )
            else:
                embed.add_field(name="After", value=after.content or "*Empty*")
            
            await self._log_to_channel(before.guild, "message_edit", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} joined the server",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        
        await self._log_to_channel(member.guild, "member_join", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} left the server",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined At", value=f"<t:{int(member.joined_at.timestamp())}:R>")
        embed.add_field(name="Roles", value=" ".join(r.mention for r in member.roles[1:]) or "None")
        
        await self._log_to_channel(member.guild, "member_remove", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.display_name != after.display_name:
            embed = discord.Embed(
                title="Nickname Changed",
                description=f"{before.mention} changed their nickname",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Before", value=before.display_name)
            embed.add_field(name="After", value=after.display_name)
            await self._log_to_channel(before.guild, "member_update", embed)
            
        # Role changes
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            
            if added:
                embed = discord.Embed(
                    title="Roles Added",
                    description=f"Roles added to {before.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Added Roles", value=" ".join(r.mention for r in added))
                await self._log_to_channel(before.guild, "role_add", embed)
                
            if removed:
                embed = discord.Embed(
                    title="Roles Removed",
                    description=f"Roles removed from {before.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Removed Roles", value=" ".join(r.mention for r in removed))
                await self._log_to_channel(before.guild, "role_remove", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="Channel Created",
            description=f"Channel {channel.mention} was created",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Type", value=str(channel.type))
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None")
            
        await self._log_to_channel(channel.guild, "channel_create", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="Channel Deleted",
            description=f"Channel #{channel.name} was deleted",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Type", value=str(channel.type))
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None")
            
        await self._log_to_channel(channel.guild, "channel_delete", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            embed = discord.Embed(
                title="Channel Updated",
                description=f"Channel name changed: #{before.name} → #{after.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            await self._log_to_channel(before.guild, "channel_update", embed)
            
        if isinstance(before, discord.TextChannel):
            if before.topic != after.topic:
                embed = discord.Embed(
                    title="Channel Topic Updated",
                    description=f"Topic changed in {after.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Before", value=before.topic or "*No topic*")
                embed.add_field(name="After", value=after.topic or "*No topic*")
                await self._log_to_channel(before.guild, "channel_update", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(
            title="Role Created",
            description=f"Role {role.mention} was created",
            color=role.color,
            timestamp=datetime.now()
        )
        await self._log_to_channel(role.guild, "role_create", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(
            title="Role Deleted",
            description=f"Role @{role.name} was deleted",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await self._log_to_channel(role.guild, "role_delete", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            if after.channel and not before.channel:
                embed = discord.Embed(
                    title="Voice Channel Joined",
                    description=f"{member.mention} joined {after.channel.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await self._log_to_channel(member.guild, "voice_join", embed)
                
            elif before.channel and not after.channel:
                embed = discord.Embed(
                    title="Voice Channel Left",
                    description=f"{member.mention} left {before.channel.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await self._log_to_channel(member.guild, "voice_leave", embed)
                
            elif before.channel and after.channel:
                embed = discord.Embed(
                    title="Voice Channel Moved",
                    description=f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                await self._log_to_channel(member.guild, "voice_move", embed)

def setup(bot):
    bot.add_cog(Logging(bot))
