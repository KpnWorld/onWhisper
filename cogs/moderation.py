import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, Union
from utils.db_manager import DBManager

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.locked_channels = set()

    @commands.slash_command(name="kick", description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        """Kick a member from the server"""
        try:
            # Check hierarchy
            if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "You cannot kick someone with a higher or equal role!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await member.kick(reason=f"Kicked by {interaction.user}: {reason}")
            
            # Log the action
            await self.db_manager.log_event(
                interaction.guild.id,
                member.id,
                "kick",
                f"Kicked by {interaction.user} for: {reason}"
            )
            
            description = f"Member: {member.mention}\nReason: {reason or 'No reason provided'}"
            
            embed = self.bot.create_embed(
                "Member Kicked",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            error_embed = self.bot.create_embed(
                "Permission Error",
                "I don't have permission to kick that member!",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="ban", description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, 
                 reason: str = None, delete_days: int = 0):
        """Ban a member from the server"""
        try:
            # Check hierarchy
            if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "You cannot ban someone with a higher or equal role!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await member.ban(reason=f"Banned by {interaction.user}: {reason}", 
                           delete_message_days=delete_days)
            
            # Log the action
            await self.db_manager.log_event(
                interaction.guild.id,
                member.id,
                "ban",
                f"Banned by {interaction.user} for: {reason}"
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Reason: {reason or 'No reason provided'}\n"
                f"Message Deletion: {delete_days} days"
            )
            
            embed = self.bot.create_embed(
                "Member Banned",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            error_embed = self.bot.create_embed(
                "Permission Error",
                "I don't have permission to ban that member!",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="timeout", description="Timeout (mute) a member")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, 
                     duration: int, unit: str, reason: str = None):
        """Timeout (mute) a member"""
        try:
            # Convert duration to timedelta
            unit = unit.lower()
            if unit in ['s', 'sec', 'seconds']:
                delta = timedelta(seconds=duration)
            elif unit in ['m', 'min', 'minutes']:
                delta = timedelta(minutes=duration)
            elif unit in ['h', 'hr', 'hours']:
                delta = timedelta(hours=duration)
            elif unit in ['d', 'day', 'days']:
                delta = timedelta(days=duration)
            else:
                embed = self.bot.create_embed(
                    "Invalid Unit",
                    "Use s/m/h/d for seconds/minutes/hours/days",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if delta > timedelta(days=28):  # Discord's maximum timeout duration
                embed = self.bot.create_embed(
                    "Invalid Duration",
                    "Timeout duration cannot exceed 28 days!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check hierarchy
            if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                embed = self.bot.create_embed(
                    "Permission Error",
                    "You cannot timeout someone with a higher or equal role!",
                    command_type="Administrative"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await member.timeout(delta, reason=f"Timeout by {interaction.user}: {reason}")
            
            # Log the action
            await self.db_manager.log_event(
                interaction.guild.id,
                member.id,
                "timeout",
                f"Timed out by {interaction.user} for {duration}{unit}: {reason}"
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Duration: {duration}{unit}\n"
                f"Reason: {reason or 'No reason provided'}"
            )
            
            embed = self.bot.create_embed(
                "Member Timed Out",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            error_embed = self.bot.create_embed(
                "Permission Error",
                "I don't have permission to timeout that member!",
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="clear", description="Clear a specified number of messages")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int, user: discord.Member = None):
        """Clear a specified number of messages"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            def check_message(m):
                return user is None or m.author == user

            deleted = await interaction.channel.purge(
                limit=amount,
                check=check_message,
                before=interaction.created_at
            )
            
            # Log the action
            await self.db_manager.log_event(
                interaction.guild.id,
                interaction.user.id,
                "clear",
                f"Cleared {len(deleted)} messages in {interaction.channel.name}"
                + (f" from {user}" if user else "")
            )
            
            description = (
                f"Messages Deleted: {len(deleted)}\n"
                f"Channel: {interaction.channel.mention}\n"
                f"Target User: {user.mention if user else 'All users'}"
            )
            
            embed = self.bot.create_embed(
                "Messages Cleared",
                description,
                command_type="Administrative"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            error_embed = self.bot.create_embed(
                "Permission Error",
                "I don't have permission to delete messages!",
                command_type="Administrative"
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @commands.slash_command(name="warn", description="Warn a member")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        """Warn a member"""
        try:
            # Log the warning
            await self.db_manager.log_event(
                interaction.guild.id,
                member.id,
                "warn",
                f"Warned by {interaction.user} for: {reason}"
            )
            
            description = (
                f"Member: {member.mention}\n"
                f"Reason: {reason}"
            )
            
            embed = self.bot.create_embed(
                "Member Warned",
                description,
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=embed)
            
            try:
                # Try to DM the user
                dm_description = (
                    f"Server: {interaction.guild.name}\n"
                    f"Reason: {reason}"
                )
                
                warn_dm = self.bot.create_embed(
                    "Warning Received",
                    dm_description,
                    command_type="Administrative"
                )
                await member.send(embed=warn_dm)
            except:
                pass  # Ignore if DM fails
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.hybrid_command(name="lock", description="Lock a channel")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock(self, ctx, channel: discord.TextChannel = None, reason: str = None):
        """Lock a channel to prevent messages from non-moderators"""
        try:
            channel = channel or ctx.channel
            
            # Don't lock if already locked
            if channel.id in self.locked_channels:
                embed = self.bot.create_embed(
                    "Channel Already Locked",
                    f"{channel.mention} is already locked!",
                    command_type="Administrative"
                )
                await ctx.send(embed=embed)
                return

            # Store current permissions and update
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            overwrites.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
            
            self.locked_channels.add(channel.id)
            
            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "lock",
                f"Channel {channel.name} locked by {ctx.author} for: {reason}"
            )
            
            description = (
                f"Channel: {channel.mention}\n"
                f"Reason: {reason or 'No reason provided'}"
            )
            
            embed = self.bot.create_embed(
                "🔒 Channel Locked",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed)

    @commands.hybrid_command(name="unlock", description="Unlock a locked channel")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        """Unlock a previously locked channel"""
        try:
            channel = channel or ctx.channel
            
            if channel.id not in self.locked_channels:
                embed = self.bot.create_embed(
                    "Channel Not Locked",
                    f"{channel.mention} is not locked!",
                    command_type="Administrative"
                )
                await ctx.send(embed=embed)
                return

            # Restore permissions
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            overwrites.send_messages = None
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
            
            self.locked_channels.remove(channel.id)
            
            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "unlock",
                f"Channel {channel.name} unlocked by {ctx.author}"
            )
            
            embed = self.bot.create_embed(
                "🔓 Channel Unlocked",
                f"Channel {channel.mention} has been unlocked.",
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed)

    @commands.hybrid_command(name="snipe", description="Show recently deleted messages")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def snipe(self, ctx, channel: discord.TextChannel = None):
        """Show the most recently deleted message in the channel"""
        try:
            channel = channel or ctx.channel
            
            # Get deleted message from database
            deleted_message = await self.db_manager.fetch_one(
                """
                SELECT user_id, content, timestamp 
                FROM logs 
                WHERE guild_id = ? AND channel_id = ? AND action = 'message_delete'
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (ctx.guild.id, channel.id)
            )
            
            if not deleted_message:
                embed = self.bot.create_embed(
                    "No Deleted Messages",
                    f"No recently deleted messages found in {channel.mention}",
                    command_type="Administrative"
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
                
            user_id, content, timestamp = deleted_message
            user = ctx.guild.get_member(user_id)
            
            description = (
                f"Author: {user.mention if user else 'Unknown User'}\n"
                f"Channel: {channel.mention}\n"
                f"Deleted: <t:{int(datetime.fromisoformat(timestamp).timestamp())}:R>\n"
                f"\nContent:\n{content}"
            )
            
            embed = self.bot.create_embed(
                "📝 Deleted Message",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed)

    @commands.hybrid_command(name="slowmode", description="Set channel slowmode")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
        """Set the slowmode delay for a channel"""
        try:
            channel = channel or ctx.channel
            
            if seconds < 0:
                embed = self.bot.create_embed(
                    "Invalid Duration",
                    "Slowmode delay must be 0 or higher!",
                    command_type="Administrative"
                )
                await ctx.send(embed=embed)
                return
                
            await channel.edit(slowmode_delay=seconds)
            
            # Log the action
            await self.db_manager.log_event(
                ctx.guild.id,
                ctx.author.id,
                "slowmode",
                f"Slowmode set to {seconds}s in {channel.name}"
            )
            
            if seconds == 0:
                description = f"Slowmode has been disabled in {channel.mention}"
            else:
                description = f"Slowmode set to {seconds} seconds in {channel.mention}"
            
            embed = self.bot.create_embed(
                "⏱️ Slowmode Updated",
                description,
                command_type="Administrative"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = self.bot.create_embed(
                "Error",
                str(e),
                command_type="Administrative"
            )
            await ctx.send(embed=error_embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Store deleted messages for snipe command"""
        if message.author.bot or not message.guild:
            return
            
        await self.db_manager.execute(
            """
            INSERT INTO logs (guild_id, channel_id, user_id, action, timestamp, details)
            VALUES (?, ?, ?, 'message_delete', ?, ?)
            """,
            (message.guild.id, message.channel.id, message.author.id, 
             datetime.utcnow().isoformat(), message.content)
        )

async def setup(bot):
    await bot.add_cog(Moderation(bot))