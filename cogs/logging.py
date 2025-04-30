import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from typing import Optional, List, Union

class Logging(commands.Cog):
    """Server logging and audit system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Logging cog")
                return
            self._ready.set()
            print("✅ Logging cog ready")
        except Exception as e:
            print(f"❌ Error setting up Logging cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    async def send_log(self, guild: discord.Guild, log_type: str, embed: discord.Embed):
        """Send log to appropriate channel"""
        try:
            config = await self.db_manager.get_data('logging_config', str(guild.id))
            if not config or not config.get('enabled', True):
                return

            channel_id = config.get(f'{log_type}_channel')
            if not channel_id:
                return

            channel = guild.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending log: {e}")

    def build_changes_embed(self, title: str, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> Optional[discord.Embed]:
        """Build embed for channel changes"""
        embed = self.ui.log_embed(title)
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.position != after.position:
            changes.append(f"Position: {before.position} → {after.position}")
        if isinstance(before, discord.TextChannel):
            if before.topic != after.topic:
                changes.append(f"Topic: {before.topic} → {after.topic}")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
            
            # Check permission overrides
            all_targets = set(before.overwrites.keys()) | set(after.overwrites.keys())
            for target in all_targets:
                before_overwrite = before.overwrites_for(target)
                after_overwrite = after.overwrites_for(target)
                
                if before_overwrite._values != after_overwrite._values:
                    field_value = []
                    for perm, new_value in after_overwrite._values.items():
                        old_value = before_overwrite._values.get(perm)
                        if old_value != new_value:
                            perm_name = perm.replace('_', ' ').title()
                            if new_value is True:
                                field_value.append(f"⬜ ➜ ✅ {perm_name}")
                            elif new_value is False:
                                field_value.append(f"⬜ ➜ ❌ {perm_name}")
                            elif new_value is None:
                                field_value.append(f"{'✅' if old_value else '❌'} ➜ ⬜ {perm_name}")
                    
                    if field_value:
                        embed.add_field(
                            name=f"Overwrites for {target.name}",
                            value="\n".join(field_value),
                            inline=False
                        )
        
        if changes:
            embed.description = "\n".join(changes)
        embed.add_field(name="Channel", value=after.mention)
        embed.timestamp = datetime.utcnow()
        
        return embed if changes or len(embed.fields) > 1 else None

    # Event Handlers
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages"""
        if message.author.bot:
            return

        # Store in database for snipe command
        await self.db_manager.log_deleted_message(message.channel.id, {
            'content': message.content,
            'author_id': message.author.id,
            'timestamp': datetime.utcnow().isoformat()
        })

        embed = self.ui.log_embed("Message Deleted")
        embed.add_field(name="Author", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        if message.content:
            embed.add_field(name="Content", value=message.content, inline=False)
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join(a.url for a in message.attachments),
                inline=False
            )
        embed.timestamp = datetime.utcnow()

        await self.send_log(message.guild, 'message', embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages"""
        if before.author.bot:
            return

        if before.content == after.content:
            return

        embed = self.ui.log_embed("Message Edited")
        embed.add_field(name="Author", value=before.author.mention)
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(name="Before", value=before.content or "No content", inline=False)
        embed.add_field(name="After", value=after.content or "No content", inline=False)
        embed.timestamp = datetime.utcnow()

        await self.send_log(before.guild, 'message', embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        embed = self.ui.log_embed("Channel Created")
        embed.add_field(name="Name", value=channel.mention)
        embed.add_field(name="Type", value=str(channel.type))
        
        if isinstance(channel, discord.TextChannel):
            if channel.category:
                embed.add_field(name="Category", value=channel.category.name, inline=False)
            
            # Log permission overrides
            for target, overwrite in channel.overwrites.items():
                allow, deny = [], []
                for perm, value in overwrite._values.items():
                    if value is True:
                        allow.append(perm.replace('_', ' ').title())
                    elif value is False:
                        deny.append(perm.replace('_', ' ').title())
                
                field_value = ""
                if allow:
                    field_value += "✅ " + "\n✅ ".join(allow) + "\n"
                if deny:
                    field_value += "❌ " + "\n❌ ".join(deny)
                
                if field_value:
                    embed.add_field(
                        name=f"Role override for {target.name}",
                        value=field_value,
                        inline=False
                    )
        
        embed.timestamp = datetime.utcnow()
        await self.send_log(channel.guild, 'server', embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        embed = self.ui.log_embed("Channel Deleted")
        embed.add_field(name="Name", value=f"#{channel.name}")
        embed.add_field(name="Type", value=str(channel.type))
        embed.timestamp = datetime.utcnow()

        await self.send_log(channel.guild, 'server', embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Log channel updates"""
        if embed := self.build_changes_embed("Channel Updated", before, after):
            await self.send_log(after.guild, 'server', embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        embed = self.ui.log_embed("Member Joined")
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.timestamp = datetime.utcnow()

        await self.send_log(member.guild, 'member', embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        embed = self.ui.log_embed("Member Left")
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>")
        if member.roles[1:]:  # Exclude @everyone
            embed.add_field(
                name="Roles",
                value=" ".join(r.mention for r in member.roles[1:]),
                inline=False
            )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.timestamp = datetime.utcnow()

        await self.send_log(member.guild, 'member', embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates"""
        if before.nick != after.nick:
            embed = self.ui.log_embed("Nickname Changed")
            embed.add_field(name="User", value=after.mention)
            embed.add_field(name="Before", value=before.nick or before.name)
            embed.add_field(name="After", value=after.nick or after.name)
            embed.timestamp = datetime.utcnow()
            
            await self.send_log(after.guild, 'member', embed)
            
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        if added_roles or removed_roles:
            embed = self.ui.log_embed("Roles Updated")
            embed.add_field(name="User", value=after.mention)
            
            if added_roles:
                embed.add_field(
                    name="Added",
                    value=" ".join(r.mention for r in added_roles),
                    inline=False
                )
            if removed_roles:
                embed.add_field(
                    name="Removed",
                    value=" ".join(r.mention for r in removed_roles),
                    inline=False
                )
                
            embed.timestamp = datetime.utcnow()
            await self.send_log(after.guild, 'member', embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        embed = self.ui.log_embed("Role Created")
        embed.add_field(name="Name", value=role.mention)
        embed.add_field(name="Color", value=str(role.color))
        embed.timestamp = datetime.utcnow()

        await self.send_log(role.guild, 'server', embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        embed = self.ui.log_embed("Role Deleted")
        embed.add_field(name="Name", value=role.name)
        embed.add_field(name="Color", value=str(role.color))
        embed.timestamp = datetime.utcnow()

        await self.send_log(role.guild, 'server', embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Log role updates"""
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"Color: {before.color} → {after.color}")
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: {before.hoist} → {after.hoist}")
        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: {before.mentionable} → {after.mentionable}")
        
        if changes:
            embed = self.ui.log_embed("Role Updated")
            embed.add_field(name="Role", value=after.mention)
            embed.description = "\n".join(changes)
            embed.timestamp = datetime.utcnow()
            
            await self.send_log(after.guild, 'server', embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))