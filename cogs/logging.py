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

    async def log_event(self, guild_id: int, event_type: str, embed: discord.Embed):
        """Send a log entry to the logging channel"""
        try:
            config = await self.bot.db_manager.get_logging_config(guild_id)
            if not config:
                return
            
            channel_id = config.get("log_channel")
            enabled = config.get("logging_enabled", False)
            
            if enabled and channel_id and str(channel_id).isdigit():
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

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member role changes"""
        # Check if roles were changed
        if before.roles != after.roles:
            # Find added and removed roles
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]

            if added_roles:
                embed = self.bot.ui_manager.success_embed(
                    "Roles Added",
                    f"Roles were added to {after.mention}"
                )
                roles_str = ", ".join([role.mention for role in added_roles])
                embed.add_field(name="Added Roles", value=roles_str, inline=False)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"Member ID: {after.id}")
                await self.log_event(after.guild.id, "role", embed)

            if removed_roles:
                embed = self.bot.ui_manager.warning_embed(
                    "Roles Removed",
                    f"Roles were removed from {after.mention}"
                )
                roles_str = ", ".join([role.mention for role in removed_roles])
                embed.add_field(name="Removed Roles", value=roles_str, inline=False)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"Member ID: {after.id}")
                await self.log_event(after.guild.id, "role", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Log role permission/configuration changes"""
        changes = []

        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"Color: {before.color} → {after.color}")
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: {before.hoist} → {after.hoist}")
        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: {before.mentionable} → {after.mentionable}")
        if before.permissions != after.permissions:
            # Find changed permissions
            for perm, value in dict(after.permissions).items():
                if dict(before.permissions).get(perm) != value:
                    changes.append(f"Permission {perm}: {dict(before.permissions).get(perm)} → {value}")

        if changes:
            embed = self.bot.ui_manager.info_embed(
                "Role Updated",
                f"Role {after.mention} was updated"
            )
            embed.add_field(name="Changes", value="\n".join(changes[:25]), inline=False)  # Limit to 25 changes
            if len(changes) > 25:
                embed.add_field(name="Note", value="Some changes were omitted due to length", inline=False)
            embed.set_footer(text=f"Role ID: {after.id}")
            await self.log_event(after.guild.id, "role", embed)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))