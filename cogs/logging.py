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
        name="config_logs",
        description="Configure logging settings"
    )
    @app_commands.describe(
        action="Whether to enable or disable logging",
        channel="Channel to use for logging (required when enabling)",
        type="Type of logs to configure"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable")
        ],
        type=[
            app_commands.Choice(name="All logs", value="all"),
            app_commands.Choice(name="Moderation logs", value="mod"),
            app_commands.Choice(name="Member logs", value="member"),
            app_commands.Choice(name="Message logs", value="message"),
            app_commands.Choice(name="Server logs", value="server")
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def config_logs(
        self,
        interaction: discord.Interaction,
        action: str,
        type: str,
        channel: Optional[discord.TextChannel] = None
    ):
        """Configure logging settings"""
        try:
            if not interaction.user.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            if action == "enable" and not channel:
                raise ValueError("Channel is required when enabling logging")

            # Create channel if needed when enabling
            if action == "enable":
                if not channel:
                    channel = await self.create_log_channel(interaction.guild, type)
                
                # Update config in database
                updates = {}
                if type == "all":
                    updates = {
                        "log_channel": str(channel.id),
                        "logging_enabled": True
                    }
                elif type == "mod":
                    updates = {"mod_channel": str(channel.id)}
                elif type == "member":
                    updates = {"join_channel": str(channel.id)}
                elif type == "message":
                    updates = {"message_channel": str(channel.id)}
                elif type == "server":
                    updates = {"server_channel": str(channel.id)}
                
                await self.bot.db_manager.update_logging_config(interaction.guild_id, updates)
                embed = self.bot.ui_manager.success_embed(
                    "Logging Enabled",
                    f"{type.title()} logs will now be sent to {channel.mention}"
                )

            else:  # disable
                updates = {}
                if type == "all":
                    updates = {
                        "logging_enabled": False,
                        "log_channel": None
                    }
                elif type == "mod":
                    updates = {"mod_channel": None}
                elif type == "member":
                    updates = {"join_channel": None}
                elif type == "message":
                    updates = {"message_channel": None}
                elif type == "server":
                    updates = {"server_channel": None}

                await self.bot.db_manager.update_logging_config(interaction.guild_id, updates)
                embed = self.bot.ui_manager.success_embed(
                    "Logging Disabled",
                    f"{type.title()} logging has been disabled"
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Input", str(e)),
                ephemeral=True
            )
        except commands.MissingPermissions:
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
        embed = self.bot.ui_manager.success_embed(
            "Member Joined",
            f"{member.mention} joined the server"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style='R'), inline=True)
        embed.set_footer(text=f"Member ID: {member.id}")
        
        await self.log_event(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leave events"""
        embed = self.bot.ui_manager.error_embed(
            "Member Left",
            f"{member.mention} left the server"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if member.joined_at:
            embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style='R'), inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style='R'), inline=True)
        embed.set_footer(text=f"Member ID: {member.id}")
        
        await self.log_event(member.guild.id, "member", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages"""
        if message.author.bot:
            return

        embed = self.bot.ui_manager.warning_embed(
            "Message Deleted",
            f"A message was deleted in {message.channel.mention}"
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
        if message.attachments:
            embed.add_field(name="Attachments", value="\n".join(a.url for a in message.attachments)[:1024], inline=False)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Message ID: {message.id}")
        
        await self.log_event(message.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages"""
        if before.author.bot or before.content == after.content:
            return

        embed = self.bot.ui_manager.info_embed(
            "Message Edited",
            f"A message was edited in {before.channel.mention}"
        )
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] if before.content else "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] if after.content else "*Empty*", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"Message ID: {before.id}")
        
        await self.log_event(before.guild.id, "message", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        embed = self.bot.ui_manager.success_embed(
            "Channel Created",
            f"Channel {channel.mention} was created"
        )
        embed.add_field(name="Type", value=str(channel.type).title(), inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await self.log_event(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        embed = self.bot.ui_manager.error_embed(
            "Channel Deleted",
            f"Channel #{channel.name} was deleted"
        )
        embed.add_field(name="Type", value=str(channel.type).title(), inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await self.log_event(channel.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        embed = self.bot.ui_manager.success_embed(
            "Role Created",
            f"Role {role.mention} was created"
        )
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await self.log_event(role.guild.id, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        embed = self.bot.ui_manager.error_embed(
            "Role Deleted",
            f"Role @{role.name} was deleted"
        )
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await self.log_event(role.guild.id, "server", embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))