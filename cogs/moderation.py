import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
import asyncio

class Moderation(commands.Cog):
    """Server moderation and management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager

    @commands.hybrid_command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str):
        """Issue a warning to a user"""
        try:
            await self.db.add_mod_action(
                ctx.guild.id,
                'warn',
                user.id,
                reason,
                None  # No expiry for warnings
            )
            
            embed = self.ui.warning_embed(
                "User Warned",
                f"**User:** {user.mention}\n**Reason:** {reason}"
            )
            await ctx.send(embed=embed)
            
            try:
                await user.send(f"You were warned in {ctx.guild.name} for: {reason}")
            except:
                pass
                
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="warnings")
    @commands.has_permissions(manage_messages=True) 
    async def warnings(self, ctx, user: discord.Member):
        """View warnings for a user"""
        try:
            actions = await self.db.get_section(ctx.guild.id, 'mod_actions')
            warnings = [
                a for a in actions
                if a['action'] == 'warn' and a['user_id'] == str(user.id)
            ]
            
            if not warnings:
                await ctx.send(f"{user.display_name} has no warnings.", ephemeral=True)
                return
                
            description = "\n".join(
                f"**{i+1}.** {w['details']} - <t:{int(datetime.fromisoformat(w['timestamp']).timestamp())}:R>"
                for i, w in enumerate(warnings)
            )
            
            embed = self.ui.info_embed(
                f"Warnings for {user.display_name}",
                description
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Delete multiple messages at once"""
        try:
            if amount < 1:
                await ctx.send("Amount must be at least 1", ephemeral=True)
                return
                
            deleted = await ctx.channel.purge(limit=amount+1)  # +1 for command message
            await ctx.send(
                f"Deleted {len(deleted)-1} messages.",
                ephemeral=True,
                delete_after=5
            )
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="lockdown")
    @commands.has_permissions(manage_channels=True)
    async def lockdown(self, ctx, channel: Optional[discord.TextChannel] = None, duration: Optional[int] = None):
        """Temporarily lock a channel"""
        try:
            channel = channel or ctx.channel
            
            # Add to database
            await self.db.add_channel_lock(ctx.guild.id, channel.id, duration)
            
            # Lock the channel
            await channel.set_permissions(
                ctx.guild.default_role,
                send_messages=False,
                reason=f"Channel locked by {ctx.author}"
            )
            
            embed = self.ui.warning_embed(
                "Channel Locked",
                f"This channel has been locked by {ctx.author.mention}"
                + (f"\nDuration: {duration} minutes" if duration else "")
            )
            await channel.send(embed=embed)
            
            # Auto unlock if duration set
            if duration:
                await asyncio.sleep(duration * 60)
                await channel.set_permissions(
                    ctx.guild.default_role,
                    send_messages=None,
                    reason=f"Lock duration expired"
                )
                await channel.send("🔓 Channel unlocked - duration expired")
                
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int, channel: Optional[discord.TextChannel] = None):
        """Set channel slowmode delay"""
        try:
            channel = channel or ctx.channel
            await channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                await ctx.send(f"Slowmode disabled in {channel.mention}")
            else:
                await ctx.send(f"Slowmode set to {seconds} seconds in {channel.mention}")
                
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="snipe")
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        """View the last deleted message"""
        try:
            data = await self.db.get_last_deleted(ctx.channel.id)
            
            if not data:
                await ctx.send("No recently deleted messages.", ephemeral=True)
                return
                
            embed = discord.Embed(
                description=data['content'],
                color=discord.Color.blue(),
                timestamp=datetime.fromisoformat(data['timestamp'])
            )
            embed.set_author(
                name=data['author_name'],
                icon_url=data['author_avatar']
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        """Kick a member from the server"""
        try:
            await member.kick(reason=reason)
            
            embed = self.ui.warning_embed(
                "Member Kicked",
                f"**User:** {member.mention}\n**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)
            
            await self.db.add_mod_action(
                ctx.guild.id,
                'kick',
                member.id,
                reason or 'No reason provided'
            )
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = None):
        """Ban a member from the server"""
        try:
            await member.ban(reason=reason)
            
            embed = self.ui.warning_embed(
                "Member Banned",
                f"**User:** {member.mention}\n**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)
            
            await self.db.add_mod_action(
                ctx.guild.id,
                'ban',
                member.id,
                reason or 'No reason provided'
            )
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = None):
        """Timeout a member for a specified duration"""
        try:
            if minutes < 1:
                await ctx.send("Duration must be at least 1 minute", ephemeral=True)
                return
                
            duration = timedelta(minutes=minutes)
            await member.timeout_for(duration, reason=reason)
            
            embed = self.ui.warning_embed(
                "Member Timed Out",
                f"**User:** {member.mention}\n"
                f"**Duration:** {minutes} minutes\n"
                f"**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)
            
            await self.db.add_mod_action(
                ctx.guild.id,
                'timeout',
                member.id,
                reason or 'No reason provided',
                datetime.utcnow() + duration
            )
            
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))