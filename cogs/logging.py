import discord
from discord.ext import commands
from typing import Optional, List, Dict
from datetime import datetime
import asyncio

class Logging(commands.Cog):
    """Server event logging"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db.ensure_connection():
                print("❌ Database not available for Logging cog")
                return
            self._ready.set()
            print("✅ Logging cog ready")
        except Exception as e:
            print(f"❌ Error setting up Logging cog: {e}")

    async def get_log_channel(self, guild: discord.Guild, log_type: str) -> Optional[discord.TextChannel]:
        """Get the configured log channel for a specific type"""
        try:
            config = await self.db.get_section(guild.id, 'logs_config')
            channel_id = config.get(f'{log_type}_channel')
            return guild.get_channel(int(channel_id)) if channel_id else None
        except Exception as e:
            print(f"Error getting log channel: {e}")
            return None

    async def get_log_channels(self, guild: discord.Guild, log_type: str) -> List[discord.TextChannel]:
        """Get all channels configured for a specific log type"""
        try:
            config = await self.db.get_section(guild.id, 'logs_config')
            channels = []
            for channel_id, types in config.get('channels', {}).items():
                if log_type in types and (channel := guild.get_channel(int(channel_id))):
                    channels.append(channel)
            return channels
        except Exception as e:
            print(f"Error getting log channels: {e}")
            return []

    async def format_permission_changes(self, before: Dict, after: Dict) -> str:
        """Format permission changes for logging"""
        changes = []
        for perm, value in after.items():
            if perm in before and before[perm] != value:
                changes.append(f"{perm}: {('❌', '✅')[before[perm]]} ➜ {('❌', '✅')[value]}")
        return "\n".join(changes) if changes else "No permission changes"

    @commands.hybrid_group(name="logs")
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx):
        """Logging configuration commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @logs.command(name="view")
    async def logs_view(self, ctx):
        """View current logging configuration"""
        config = await self.db.get_section(ctx.guild.id, 'logs_config')
        
        description = []
        for log_type in ['mod', 'join', 'message', 'member', 'server']:
            channel_id = config.get(f'{log_type}_channel')
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            description.append(f"**{log_type.title()} Logs:** {channel.mention if channel else 'Disabled'}")
            
        embed = self.ui.info_embed("Logging Configuration", "\n".join(description))
        await ctx.send(embed=embed)

    @logs.command(name="channel")
    async def logs_channel(self, ctx, channel: discord.TextChannel = None):
        """Set logging channel for specific types"""
        valid_types = ['mod', 'join', 'message', 'member', 'server']
        
        if not channel:
            # Show current configuration
            config = await self.db.get_section(ctx.guild.id, 'logs_config')
            description = []
            for channel_id, types in config.get('channels', {}).items():
                if ch := ctx.guild.get_channel(int(channel_id)):
                    description.append(f"{ch.mention}: {', '.join(types)}")
            
            embed = self.ui.info_embed(
                "Logging Configuration",
                "\n".join(description) if description else "No logging channels configured"
            )
            await ctx.send(embed=embed)
            return

        # Create selection menu for log types
        options = [
            discord.SelectOption(
                label=type_.title(),
                value=type_,
                description=f"Log {type_} events"
            ) for type_ in valid_types
        ]
        
        select = discord.ui.Select(
            placeholder="Select log types...",
            min_values=1,
            max_values=len(valid_types),
            options=options
        )
        
        async def select_callback(interaction: discord.Interaction):
            try:
                config = await self.db.get_section(ctx.guild.id, 'logs_config')
                if 'channels' not in config:
                    config['channels'] = {}
                    
                config['channels'][str(channel.id)] = select.values
                await self.db.update_guild_data(ctx.guild.id, 'logs_config', config)
                
                await interaction.response.edit_message(
                    content=f"Updated logging configuration for {channel.mention}:\n" + 
                           ", ".join(select.values),
                    view=None
                )
            except Exception as e:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await ctx.send(
            f"Select log types for {channel.mention}:",
            view=view,
            ephemeral=True
        )

    @logs.command(name="set")
    async def logs_set(self, ctx, log_type: str, channel: discord.TextChannel):
        """Set a logging channel for a specific type"""
        try:
            valid_types = ['mod', 'join', 'message', 'member', 'server']
            if log_type not in valid_types:
                await ctx.send(
                    f"Invalid log type. Valid types: {', '.join(valid_types)}", 
                    ephemeral=True
                )
                return

            config = await self.db.get_section(ctx.guild.id, 'logs_config')
            config[f'{log_type}_channel'] = channel.id
            await self.db.update_guild_data(ctx.guild.id, 'logs_config', config)
            
            await ctx.send(
                f"Set {log_type} logs to {channel.mention}",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        channels = await self.get_log_channels(member.guild, 'join')
        if not channels:
            return
            
        embed = self.ui.info_embed(
            "Member Joined",
            f"**User:** {member.mention}\n"
            f"**ID:** {member.id}\n"
            f"**Created:** <t:{int(member.created_at.timestamp())}:R>"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        for channel in channels:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        channels = await self.get_log_channels(member.guild, 'join')
        if not channels:
            return
            
        embed = self.ui.warning_embed(
            "Member Left",
            f"**User:** {member.mention}\n"
            f"**ID:** {member.id}\n"
            f"**Joined:** <t:{int(member.joined_at.timestamp())}:R>"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        for channel in channels:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages"""
        if message.author.bot:
            return
            
        channels = await self.get_log_channels(message.guild, 'message')
        if not channels:
            return
            
        embed = self.ui.warning_embed(
            "Message Deleted",
            f"**Author:** {message.author.mention}\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Content:**\n{message.content}"
        )
        for channel in channels:
            await channel.send(embed=embed)
        
        # Store for snipe command
        await self.db.log_deleted_message(message.channel.id, {
            'content': message.content,
            'author_name': str(message.author),
            'author_avatar': str(message.author.display_avatar.url),
            'timestamp': message.created_at.isoformat()
        })

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages"""
        if before.author.bot:
            return
            
        if before.content == after.content:
            return
            
        channels = await self.get_log_channels(before.guild, 'message')
        if not channels:
            return
            
        embed = self.ui.info_embed(
            "Message Edited",
            f"**Author:** {before.author.mention}\n"
            f"**Channel:** {before.channel.mention}\n"
            f"**Before:**\n{before.content}\n"
            f"**After:**\n{after.content}"
        )
        for channel in channels:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates"""
        channels = await self.get_log_channels(before.guild, 'member')
        if not channels:
            return
            
        # Handle nickname changes
        if before.nick != after.nick:
            embed = self.ui.info_embed(
                "Nickname Changed",
                f"**User:** {before.mention}\n"
                f"**Before:** {before.nick or before.name}\n"
                f"**After:** {after.nick or after.name}"
            )
            for channel in channels:
                await channel.send(embed=embed)
            
        # Handle role changes
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        if added_roles or removed_roles:
            description = []
            if added_roles:
                description.append("**Added Roles:**\n" + ", ".join(r.mention for r in added_roles))
            if removed_roles:
                description.append("**Removed Roles:**\n" + ", ".join(r.mention for r in removed_roles))
                
            embed = self.ui.info_embed(
                "Roles Updated",
                f"**User:** {before.mention}\n" + "\n".join(description)
            )
            for channel in channels:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Log member bans"""
        channels = await self.get_log_channels(guild, 'mod')
        if not channels:
            return
            
        embed = self.ui.error_embed(
            "Member Banned",
            f"**User:** {user.mention}\n"
            f"**ID:** {user.id}"
        )
        for channel in channels:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log member unbans"""
        channels = await self.get_log_channels(guild, 'mod')
        if not channels:
            return
            
        embed = self.ui.success_embed(
            "Member Unbanned",
            f"**User:** {user.mention}\n"
            f"**ID:** {user.id}"
        )
        for channel in channels:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        log_channels = await self.get_log_channels(channel.guild, 'server')
        if not log_channels:
            return
            
        embed = self.ui.info_embed(
            "Channel Created",
            f"**Name:** {channel.name}\n"
            f"**Type:** {channel.type}"
        )
        for log_channel in log_channels:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        log_channels = await self.get_log_channels(channel.guild, 'server')
        if not log_channels:
            return
            
        embed = self.ui.warning_embed(
            "Channel Deleted",
            f"**Name:** {channel.name}\n"
            f"**Type:** {channel.type}"
        )
        for log_channel in log_channels:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Log detailed channel updates"""
        channels = await self.get_log_channels(before.guild, 'server')
        if not channels:
            return

        changes = []
        
        # Track name changes
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} ➜ {after.name}")
            
        # Track permission changes
        for target, after_perms in after.overwrites.items():
            before_perms = before.overwrites.get(target, None)
            if before_perms != after_perms:
                # Convert overwrites to dictionary
                before_dict = {k[0]: k[1] for k in before_perms._values} if before_perms else {}
                after_dict = {k[0]: k[1] for k in after_perms._values}
                
                changes.append(f"\nOverwrites for {target.name}:")
                changes.append(await self.format_permission_changes(before_dict, after_dict))

        if changes:
            embed = self.ui.info_embed(
                f"Channel Updated: #{after.name}",
                "\n".join(changes)
            )
            for channel in channels:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Log voice channel events"""
        channels = await self.get_log_channels(member.guild, 'voice')
        if not channels:
            return
            
        if before.channel != after.channel:
            if after.channel and not before.channel:
                action = f"joined {after.channel.mention}"
            elif before.channel and not after.channel:
                action = f"left {before.channel.mention}"
            else:
                action = f"moved from {before.channel.mention} to {after.channel.mention}"
                
            embed = self.ui.info_embed(
                "Voice Update",
                f"**Member:** {member.mention}\n"
                f"**Action:** {action}"
            )
            for channel in channels:
                await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))