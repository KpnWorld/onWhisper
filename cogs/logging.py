import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_log_channel(self, guild: discord.Guild, channel_type: str = "mod") -> discord.TextChannel:
        """Create a new logging channel"""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel_name = f"{channel_type}-logs"
        return await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason="Automatic logging channel creation"
        )

    @app_commands.command(
        name="config_logging",
        description="Configure logging settings"
    )
    @app_commands.describe(
        channel="Channel to use for logging (will create one if not specified)",
        enabled="Enable or disable logging"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_logging(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = True
    ):
        """Configure logging settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            # Create channel if not specified and enabled
            if not channel and enabled:
                channel = await self.create_log_channel(interaction.guild)

            # Update config in database
            updates = {
                "log_channel": str(channel.id) if channel else None,
                "logging_enabled": enabled
            }
            
            await self.bot.db_manager.update_logging_config(interaction.guild_id, updates)

            # Send confirmation
            status = "enabled" if enabled else "disabled"
            channel_text = f"in {channel.mention}" if channel else ""
            embed = self.bot.ui_manager.success_embed(
                "Logging Updated",
                f"Logging has been {status} {channel_text}"
            )
            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Administrator permission to configure logging."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_mod_logs",
        description="Configure the moderation logging channel"
    )
    @app_commands.describe(
        channel="The channel to use for moderation logs (will create one if not specified)"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_mod_logs(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure moderation logging channel"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if not channel:
                channel = await self.create_log_channel(interaction.guild, "mod")

            await self.bot.db_manager.update_logging_config(interaction.guild_id, {
                "mod_channel": str(channel.id)
            })

            embed = self.bot.ui_manager.success_embed(
                "Mod Logs Configured",
                f"Moderation actions will now be logged in {channel.mention}"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_join_logs",
        description="Configure the member join/leave logging channel"
    )
    @app_commands.describe(
        channel="The channel to use for member logs (will create one if not specified)"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_join_logs(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure member join/leave logging channel"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if not channel:
                channel = await self.create_log_channel(interaction.guild, "member")

            await self.bot.db_manager.update_logging_config(interaction.guild_id, {
                "join_channel": str(channel.id)
            })

            embed = self.bot.ui_manager.success_embed(
                "Member Logs Configured",
                f"Member join/leave events will now be logged in {channel.mention}"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="config_logs_toggle",
        description="Enable or disable logging"
    )
    @app_commands.describe(
        enabled="Whether logging should be enabled"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_logs_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        """Toggle logging system"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            await self.bot.db_manager.update_logging_config(interaction.guild_id, {
                "enabled": enabled
            })

            status = "enabled" if enabled else "disabled"
            embed = self.bot.ui_manager.success_embed(
                "Logging Updated",
                f"Logging has been {status}"
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    async def log_event(self, guild_id: int, event_type: str, embed: discord.Embed):
        """Send a log entry to the logging channel"""
        try:
            config = await self.bot.db_manager.get_logging_config(guild_id)
            
            channel_id = config.get("log_channel")
            enabled = config.get("logging_enabled", False)
            
            if enabled and channel_id:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    # Add event type to embed
                    embed.add_field(name="Event Type", value=event_type.title(), inline=False)
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending log: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member join events"""
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} joined the server",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"))
        embed.set_footer(text=f"ID: {member.id}")
        
        await self.log_event(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leave events"""
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} left the server",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M UTC") if member.joined_at else "Unknown")
        embed.set_footer(text=f"ID: {member.id}")
        
        await self.log_event(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages"""
        if message.author.bot:
            return

        embed = discord.Embed(
            title="Message Deleted",
            description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
        if message.attachments:
            embed.add_field(name="Attachments", value="\n".join(a.url for a in message.attachments)[:1024], inline=False)
        embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
        
        await self.log_event(message.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages"""
        if before.author.bot or before.content == after.content:
            return

        embed = discord.Embed(
            title="Message Edited",
            description=f"Message by {before.author.mention} edited in {before.channel.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Before", value=before.content[:1024] if before.content else "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] if after.content else "*Empty*", inline=False)
        embed.set_footer(text=f"Author ID: {before.author.id} | Message ID: {before.id}")
        
        await self.log_event(before.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        embed = discord.Embed(
            title="Channel Created",
            description=f"Channel {channel.mention} was created",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Type", value=str(channel.type))
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await self.log_event(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        embed = discord.Embed(
            title="Channel Deleted",
            description=f"Channel #{channel.name} was deleted",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Type", value=str(channel.type))
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await self.log_event(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        embed = discord.Embed(
            title="Role Created",
            description=f"Role {role.mention} was created",
            color=role.color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await self.log_event(role.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        embed = discord.Embed(
            title="Role Deleted",
            description=f"Role @{role.name} was deleted",
            color=role.color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await self.log_event(role.guild.id, "server", embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))