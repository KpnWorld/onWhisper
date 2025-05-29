import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
import logging

class ModerationCog(commands.Cog):
    """Cog for moderation commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.moderation")  # Use standard logging
    
    async def _check_mod_permissions(self, ctx_or_interaction) -> bool:
        """Check if user has mod permissions"""
        # Handle both Context and Interaction
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.user
        else:  # Context
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.author

        if not guild or not isinstance(user, discord.Member):
            return False
            
        # Check if user is admin or has manage server permission
        if user.guild_permissions.administrator or user.guild_permissions.manage_guild:
            return True
            
        # Check for mod role
        mod_role_id = await self.bot.db.get_guild_setting(guild.id, "mod_role")
        if mod_role_id:
            return discord.utils.get(user.roles, id=int(mod_role_id)) is not None
            
        return False

    @commands.guild_only()
    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(user="User to ban", reason="Reason for the ban", delete_days="Number of days of messages to delete")
    async def ban(self, ctx: commands.Context, user: discord.User, *, reason: str = "No reason provided", delete_days: int = 0):
        """Ban a member from the server."""
        # Check permissions first
        if not await self._check_mod_permissions(ctx):
            await ctx.send("You don't have permission to use this command!", ephemeral=True)
            return

        # Convert to interaction if it's a slash command
        interaction = ctx.interaction if hasattr(ctx, 'interaction') else None
        
        if not await self._check_mod_permissions(interaction or ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server!", ephemeral=True)
            
        try:
            await ctx.guild.ban(user, reason=reason, delete_message_days=delete_days)
            
            # Log the action
            await self.bot.db.insert_mod_action(
                ctx.guild.id,
                user.id,
                "ban",
                reason,
                ctx.author.id
            )
            
            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden as e:
            self.log.warning(f"Permission error in ban command: {e}")
            await ctx.send("I don't have permission to ban that user!", ephemeral=True)
        except Exception as e:
            self.log.error(f"Error in ban command: {e}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred.", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(user="User to kick", reason="Reason for the kick")
    async def kick(self, ctx: commands.Context, user: discord.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        try:
            await user.kick(reason=reason)
            
            await self.bot.db.insert_mod_action(
                ctx.guild,
                user.id,
                "kick",
                reason,
                ctx.author.id
            )
            
            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to kick that user!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="timeout", description="Timeout a member temporarily.")
    @app_commands.describe(
        user="User to timeout",
        duration="Duration in minutes (1-40320)", # 28 days max
        reason="Reason for the timeout"
    )
    async def timeout(self, ctx: commands.Context, user: discord.Member, duration: int, *, reason: str = "No reason provided"):
        """Timeout a member temporarily."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        # Add bounds checking for duration
        if duration < 1 or duration > 40320:  # 28 days in minutes
            return await ctx.send("Duration must be between 1 minute and 28 days!", ephemeral=True)
            
        try:
            until = datetime.utcnow() + timedelta(minutes=duration)
            await user.timeout(until, reason=reason)
            
            await self.bot.db.insert_mod_action(
                ctx.guild,
                user.id,
                "timeout",
                f"{reason} (Duration: {duration} minutes)",
                ctx.author.id
            )
            
            embed = discord.Embed(
                title="⏳ Member Timed Out",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to timeout that user!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="warn", description="Warn a member.")
    @app_commands.describe(user="User to warn", reason="Reason for the warning")
    async def warn(self, ctx: commands.Context, user: discord.Member, *, reason: str = "No reason provided"):
        """Warn a member."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        try:
            await self.bot.db.insert_mod_action(
                ctx.guild,
                user.id,
                "warn",
                reason,
                ctx.author.id
            )
            
            embed = discord.Embed(
                title="⚠️ Member Warned",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
            try:
                # Try to DM the user
                warn_dm = discord.Embed(
                    title=f"⚠️ Warning from {ctx.guild}",
                    color=discord.Color.gold(),
                    description=f"You have been warned by {ctx.author}",
                    timestamp=datetime.utcnow()
                )
                warn_dm.add_field(name="Reason", value=reason)
                await user.send(embed=warn_dm)
            except:
                pass  # Ignore if we can't DM the user
                
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="purge", description="Delete a number of messages.")
    @app_commands.describe(amount="Number of messages to delete (1-1000)")
    async def purge(self, ctx: commands.Context, amount: int):
        """Delete a number of messages."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send("This command can only be used in text channels!", ephemeral=True)
            
        # Add bounds checking for amount
        if amount < 1 or amount > 1000:
            return await ctx.send("Please provide a number between 1 and 1000.", ephemeral=True)

        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include command message
            await ctx.send(f"✨ Deleted {len(deleted) - 1} messages.", ephemeral=True)
            
            await self.bot.db.insert_mod_action(
                ctx.guild,
                ctx.author.id,
                "purge",
                f"Purged {len(deleted) - 1} messages in #{ctx.channel.name}",
                ctx.author.id
            )
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete messages!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="lockdown", description="Lock or unlock a channel.")
    @app_commands.describe(channel="Channel to lock/unlock", lock="True to lock, False to unlock")
    async def lockdown(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, lock: bool = True):
        """Lock or unlock a channel."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        channel = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("This command can only be used on text channels!", ephemeral=True)
            
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server!", ephemeral=True)
            
        try:
            await channel.set_permissions(ctx.guild.default_role,
                                       send_messages=not lock,
                                       reason=f"Channel {'locked' if lock else 'unlocked'} by {ctx.author}")
            
            await self.bot.db.insert_mod_action(
                ctx.guild.id,
                ctx.author.id,
                "lockdown",
                f"{'Locked' if lock else 'Unlocked'} channel #{channel.name}",
                ctx.author.id
            )
            
            await ctx.send(f"🔒 Channel has been {'locked' if lock else 'unlocked'}.")
            
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel permissions!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.guild_only()
    @commands.hybrid_command(name="slowmode", description="Set slowmode for a channel.")
    @app_commands.describe(seconds="Slowmode delay in seconds", channel="Channel to set slowmode for")
    async def slowmode(self, ctx: commands.Context, seconds: int, channel: Optional[discord.TextChannel] = None):
        """Set slowmode for a channel."""
        
        if not await self._check_mod_permissions(ctx.interaction if hasattr(ctx, 'interaction') else ctx):
            return await ctx.send("You don't have permission to use this command!", ephemeral=True)
            
        channel = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("This command can only be used on text channels!", ephemeral=True)
            
        try:
            await channel.edit(slowmode_delay=seconds)
            
            await self.bot.db.insert_mod_action(
                ctx.guild,
                ctx.author.id,
                "slowmode",
                f"Set slowmode to {seconds}s in #{channel.name}",
                ctx.author.id
            )
            
            if seconds == 0:
                await ctx.send(f"🕒 Slowmode has been disabled in {channel.mention}")
            else:
                await ctx.send(f"🕒 Slowmode has been set to {seconds} seconds in {channel.mention}")
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel settings!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
