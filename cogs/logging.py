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
                "Database connection is not available.",
                ephemeral=True
            )        
        try:
            log_types = ["mod", "member", "message", "server"] if log_type == "all" else [log_type]

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
                            "Please provide a channel when enabling logging.",
                            ephemeral=True
                        )
                else:
                    current_enabled = enabled

                await self.bot.db_manager.set_logging_channel(
                    interaction.guild_id,
                    current_type,
                    channel.id if current_enabled else None
                )
                
                # Update cache
                if interaction.guild_id not in self._log_cache:
                    self._log_cache[interaction.guild_id] = {}
                
                if current_enabled:
                    self._log_cache[interaction.guild_id][current_type] = channel.id
                else:
                    self._log_cache[interaction.guild_id].pop(current_type, None)
            
            if current_enabled and channel:
                # Send confirmation message to the log channel
                embed = discord.Embed(
                    title="Logging Channel Set",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )

                info = (
                    f"```yaml\n"
                    f"Channel: #{channel.name}\n"
                    f"Set By: {interaction.user} ({interaction.user.id})\n"
                    f"Log Types:\n"
                    f"{chr(10).join(f'  - {t}' for t in log_types)}\n"
                    f"```"
                )
                embed.add_field(name="Configuration", value=info, inline=False)
                await channel.send(embed=embed)

            action = "Enabled" if current_enabled else "Disabled"
            types = ", ".join(f"`{t}`" for t in log_types)
            channel_mention = f" in {channel.mention}" if current_enabled else ""
            
            await interaction.response.send_message(
                f"{action} {types} logging{channel_mention}.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

    @logging_group.command(name="status")
    @app_commands.default_permissions(manage_guild=True)
    async def logging_status(self, interaction: discord.Interaction):
        """Show current logging settings"""
        if not self.bot.db_manager:
            return await interaction.response.send_message(
                "Database connection is not available.",
                ephemeral=True
            )

        try:
            settings = await self.bot.db_manager.get_all_logging_channels(
                interaction.guild_id
            )

            embed = discord.Embed(
                title="Logging Configuration",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            for log_type in ["mod", "member", "message", "server"]:
                channel_id = settings.get(log_type)
                channel = interaction.guild.get_channel(channel_id) if channel_id else None
                
                info = (
                    f"```yaml\n"
                    f"Status: {'Enabled' if channel else 'Disabled'}\n"
                    f"Channel: {f'#{channel.name}' if channel else 'None'}\n"
                    f"Channel ID: {channel_id if channel else 'N/A'}\n"
                    f"```"
                )
                embed.add_field(
                    name=f"{log_type.title()} Logs",
                    value=info,
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        embed = discord.Embed(
            title="Member Joined",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"User: {member} ({member.id})\n"
            f"Account Created: {discord.utils.format_dt(member.created_at, style='R')}\n"
            f"```"
        )
        embed.add_field(name="Basic Info", value=info, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await self._send_log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        embed = discord.Embed(
            title="Member Left",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"User: {member} ({member.id})\n"
            f"Joined Server: {discord.utils.format_dt(member.joined_at, style='R')}\n"
            f"Roles: {', '.join(role.name for role in member.roles[1:]) or 'None'}\n"
            f"```"
        )
        embed.add_field(name="Basic Info", value=info, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await self._send_log(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates (nickname, roles)"""
        if before.nick != after.nick:
            embed = discord.Embed(
                title="Nickname Changed",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            info = (
                f"```yaml\n"
                f"User: {after} ({after.id})\n"
                f"Previous Nickname: {before.nick or 'None'}\n"
                f"New Nickname: {after.nick or 'None'}\n"
                f"```"
            )
            embed.add_field(name="Basic Info", value=info, inline=False)
            await self._send_log(after.guild.id, "member", embed)

        # Role changes
        removed_roles = set(before.roles) - set(after.roles)
        added_roles = set(after.roles) - set(before.roles)

        if removed_roles or added_roles:
            embed = discord.Embed(
                title="Member Roles Updated",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            info = (
                f"```yaml\n"
                f"User: {after} ({after.id})\n"
                f"```"
            )
            embed.add_field(name="Basic Info", value=info, inline=False)

            if added_roles:
                details = (
                    f"```yaml\n"
                    f"Added:\n"
                    f"{chr(10).join(f'  - {role.name}' for role in added_roles)}\n"
                    f"```"
                )
                embed.add_field(name="Added Roles", value=details, inline=False)

            if removed_roles:
                details = (
                    f"```yaml\n"
                    f"Removed:\n"
                    f"{chr(10).join(f'  - {role.name}' for role in removed_roles)}\n"
                    f"```"
                )
                embed.add_field(name="Removed Roles", value=details, inline=False)

            await self._send_log(after.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions"""
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="Message Deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )

        info = (
            f"```yaml\n"
            f"Author: {message.author} ({message.author.id})\n"
            f"Channel: #{message.channel.name}\n"
            f"Created: {discord.utils.format_dt(message.created_at, style='R')}\n"
            f"```"
        )
        embed.add_field(name="Basic Info", value=info, inline=False)

        if message.content:
            content = (
                f"```yaml\n"
                f"Content: |\n  {message.content.replace(chr(10), chr(10) + '  ')}\n"
                f"```"
            )
            if len(content) > 1024:
                content = content[:1021] + "```"
            embed.add_field(name="Message Content", value=content, inline=False)

        if message.attachments:
            files = (
                f"```yaml\n"
                f"Files:\n"
                f"{chr(10).join(f'  - {a.filename}: {a.url}' for a in message.attachments)}\n"
                f"```"
            )
            embed.add_field(name="Attachments", value=files, inline=False)

        await self._send_log(message.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits"""
        if before.author.bot or not before.guild or before.content == after.content:
            return

        embed = discord.Embed(
            title="Message Edited",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        info = (
            f"```yaml\n"
            f"Author: {before.author} ({before.author.id})\n"
            f"Channel: #{before.channel.name}\n"
            f"Message Link: {after.jump_url}\n"
            f"```"
        )
        embed.add_field(name="Basic Info", value=info, inline=False)

        content = (
            f"```yaml\n"
            f"Before: |\n  {before.content.replace(chr(10), chr(10) + '  ')}\n"
            f"After: |\n  {after.content.replace(chr(10), chr(10) + '  ')}\n"
            f"```"
        )
        if len(content) > 1024:
            content = content[:1021] + "```"
        embed.add_field(name="Content Changes", value=content, inline=False)

        await self._send_log(before.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        embed = discord.Embed(
            title="Channel Created",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"Name: #{channel.name}\n"
            f"Type: {str(channel.type)}\n"
            f"Category: {channel.category.name if channel.category else 'None'}\n"
            f"Position: {channel.position}\n"
            f"```"
        )
        embed.add_field(name="Channel Details", value=info, inline=False)
        
        await self._send_log(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        embed = discord.Embed(
            title="Channel Deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"Name: #{channel.name}\n"
            f"Type: {str(channel.type)}\n"
            f"Category: {channel.category.name if channel.category else 'None'}\n"
            f"Position: {channel.position}\n"
            f"```"
        )
        embed.add_field(name="Channel Details", value=info, inline=False)
        
        await self._send_log(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        embed = discord.Embed(
            title="Role Created",
            color=role.color,
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"Name: {role.name}\n"
            f"Color: {str(role.color)}\n"
            f"Hoisted: {role.hoist}\n"
            f"Mentionable: {role.mentionable}\n"
            f"Position: {role.position}\n"
            f"```"
        )
        embed.add_field(name="Role Details", value=info, inline=False)
        
        await self._send_log(role.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        embed = discord.Embed(
            title="Role Deleted",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        info = (
            f"```yaml\n"
            f"Name: {role.name}\n"
            f"Color: {str(role.color)}\n"
            f"Hoisted: {role.hoist}\n"
            f"Mentionable: {role.mentionable}\n"
            f"Position: {role.position}\n"
            f"```"
        )
        embed.add_field(name="Role Details", value=info, inline=False)
        
        await self._send_log(role.guild.id, "server", embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))