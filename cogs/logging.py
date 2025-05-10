import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional, Dict
from datetime import datetime, timedelta
import asyncio

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._log_cache: Dict[int, Dict[str, int]] = {}  # guild_id -> {type: channel_id}

    logging_group = app_commands.Group(
        name="logging",
        description="Configure server logging"
    )

    async def _send_log(
        self,
        guild_id: int,
        log_type: str,
        embed: discord.Embed,
        file: Optional[discord.File] = None
    ):
        """Send a log message to the appropriate channel"""
        if not self.bot.db_manager:
            return

        try:
            # Check cache first
            channel_id = self._log_cache.get(guild_id, {}).get(log_type)
            
            if channel_id is None:
                # Not in cache, check database
                channel_id = await self.bot.db_manager.get_logging_channel(
                    guild_id,
                    log_type
                )
                if channel_id:
                    if guild_id not in self._log_cache:
                        self._log_cache[guild_id] = {}
                    self._log_cache[guild_id][log_type] = channel_id

            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed, file=file if file else None)

        except Exception as e:
            print(f"Error sending log: {e}")    
            
    @logging_group.command(name="setup")
    @app_commands.describe(
        log_type="The type of logs to configure",
        channel="The channel to send logs to",
        enabled="Whether to enable or disable logging"
    )
    @app_commands.choices(log_type=[
        app_commands.Choice(name="mod", value="mod"),
        app_commands.Choice(name="member", value="member"),
        app_commands.Choice(name="message", value="message"),
        app_commands.Choice(name="server", value="server"),
        app_commands.Choice(name="all", value="all")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def setup_logging(
        self,
        interaction: discord.Interaction,
        log_type: Literal["mod", "member", "message", "server", "all"],
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None
    ):
        """Configure logging channels and settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )        
        try:
            log_types = ["mod", "member", "message", "server"]
            if log_type == "all":
                log_types = ["mod", "member", "message", "server"]
            else:
                log_types = [log_type]

            for current_type in log_types:
                if enabled is None:
                    # Toggle current state
                    current = await self.bot.db_manager.get_logging_channel(
                        interaction.guild_id,
                        current_type
                    )
                    current_enabled = not bool(current)            
                    if current_enabled and not channel:
                        return await interaction.response.send_message(
                            "⚠️ Please provide a channel when enabling logging.",
                            ephemeral=True
                        )
                else:
                    current_enabled = enabled

                await self.bot.db_manager.set_logging_channel(
                    interaction.guild_id,
                    current_type,
                    channel.id if current_enabled else None
                )            # Update cache
            if interaction.guild_id not in self._log_cache:
                self._log_cache[interaction.guild_id] = {}
            
            if enabled:
                for current_type in log_types:
                    self._log_cache[interaction.guild_id][current_type] = channel.id
                # Send confirmation message to the log channel
                setup_embed = discord.Embed(
                    title="Logging Channel Set",
                    description=(
                        "This channel has been set as the logging channel for: " +
                        (", ".join(f"`{t}`" for t in log_types))
                    ),
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                setup_embed.add_field(
                    name="Set By",
                    value=interaction.user.mention,
                    inline=True
                )
                setup_embed.add_field(
                    name="Channel",
                    value=channel.mention,
                    inline=True
                )
                await channel.send(embed=setup_embed)
            else:
                for current_type in log_types:
                    self._log_cache[interaction.guild_id].pop(current_type, None)

            await interaction.response.send_message(
                f"✅ {'Enabled' if enabled else 'Disabled'} {log_type} logging "
                f"{f'in {channel.mention}' if enabled else ''}.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @logging_group.command(name="status")
    @app_commands.default_permissions(manage_guild=True)
    async def logging_status(self, interaction: discord.Interaction):
        """Show current logging settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "⚠️ Database connection is not available.",
                ephemeral=True
            )

        try:
            settings = await self.bot.db_manager.get_all_logging_channels(
                interaction.guild_id
            )

            embed = discord.Embed(
                title="Logging Settings",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            for log_type in ["mod", "member", "message", "server"]:
                channel_id = settings.get(log_type)
                channel = interaction.guild.get_channel(channel_id) if channel_id else None
                
                status = "✅ Enabled" if channel else "❌ Disabled"
                value = f"{status}\nChannel: {channel.mention if channel else 'None'}"
                
                embed.add_field(
                    name=f"{log_type.title()} Logs",
                    value=value,
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} joined the server",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        
        await self._send_log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} left the server",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>")
        
        await self._send_log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates (nickname, roles)"""
        if before.nick != after.nick:
            embed = discord.Embed(
                title="Nickname Changed",
                description=f"{after.mention} changed their nickname",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Before", value=before.nick or "None")
            embed.add_field(name="After", value=after.nick or "None")
            
            await self._send_log(after.guild.id, "member", embed)

        # Role changes
        removed_roles = set(before.roles) - set(after.roles)
        added_roles = set(after.roles) - set(before.roles)

        if removed_roles or added_roles:
            embed = discord.Embed(
                title="Member Roles Updated",
                description=f"Role changes for {after.mention}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            if added_roles:
                embed.add_field(
                    name="Added Roles",
                    value=", ".join(role.mention for role in added_roles),
                    inline=False
                )

            if removed_roles:
                embed.add_field(
                    name="Removed Roles",
                    value=", ".join(role.mention for role in removed_roles),
                    inline=False
                )

            await self._send_log(after.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions"""
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="Message Deleted",
            description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )

        if message.content:
            if len(message.content) > 1024:
                embed.add_field(
                    name="Content (Truncated)",
                    value=f"{message.content[:1021]}...",
                    inline=False
                )
            else:
                embed.add_field(name="Content", value=message.content, inline=False)

        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join(a.url for a in message.attachments),
                inline=False
            )

        await self._send_log(message.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits"""
        if before.author.bot or not before.guild or before.content == after.content:
            return

        embed = discord.Embed(
            title="Message Edited",
            description=f"Message by {before.author.mention} edited in {before.channel.mention}\n[Jump to Message]({after.jump_url})",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        if len(before.content) > 1024:
            embed.add_field(
                name="Before (Truncated)",
                value=f"{before.content[:1021]}...",
                inline=False
            )
        else:
            embed.add_field(name="Before", value=before.content or "Empty", inline=False)

        if len(after.content) > 1024:
            embed.add_field(
                name="After (Truncated)",
                value=f"{after.content[:1021]}...",
                inline=False
            )
        else:
            embed.add_field(name="After", value=after.content or "Empty", inline=False)

        await self._send_log(before.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        embed = discord.Embed(
            title="Channel Created",
            description=f"#{channel.name} was created",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Type", value=str(channel.type))
        
        await self._send_log(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        embed = discord.Embed(
            title="Channel Deleted",
            description=f"#{channel.name} was deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Type", value=str(channel.type))
        
        await self._send_log(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        embed = discord.Embed(
            title="Role Created",
            description=f"{role.mention} was created",
            color=role.color,
            timestamp=discord.utils.utcnow()
        )
        
        await self._send_log(role.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        embed = discord.Embed(
            title="Role Deleted",
            description=f"@{role.name} was deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        await self._send_log(role.guild.id, "server", embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))