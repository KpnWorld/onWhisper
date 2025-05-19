import discord
from discord.ext import commands
from discord.commands import slash_command, option
from typing import Optional, cast
from datetime import datetime, timedelta

class Moderation(commands.Cog):
    """Moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def _log_mod_action(
        self,
        guild_id: int,
        user_id: int,
        action: str,
        reason: str,
        moderator_id: int
    ) -> None:
        """Log a moderation action to the database and logging channel"""
        await self.bot.db.add_mod_action(
            guild_id,
            user_id,
            action,
            reason,
            moderator_id
        )
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
            
        user = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        moderator = guild.get_member(moderator_id) or await self.bot.fetch_user(moderator_id)
        
        if not user or not moderator:
            return
            
        embed = discord.Embed(
            title=f"Moderation Action - {action.title()}",
            description=f"{moderator.mention} {action} {user.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        try:
            cog = self.bot.get_cog("Logging")
            if cog:
                await cog._log_to_channel(guild, "moderation", embed)
        except Exception:
            pass    
        
    @slash_command(name="ban", description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    @option("member", description="The member to ban", type=discord.Member)
    @option("days", description="Number of days of messages to delete", type=int, min_value=0, max_value=7, default=1)
    @option("reason", description="Reason for the ban", type=str, default="No reason provided")
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        days: int = 1,
        reason: str = "No reason provided"
    ) -> None:
        # Validate days range
        days = max(0, min(7, days))

        try:
            # Try to DM user
            try:
                embed = discord.Embed(
                    title=f"You have been banned from {ctx.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.red()
                )
                await member.send(embed=embed)
            except:
                pass

            await ctx.guild.ban(
                member,
                clean_history_duration=timedelta(days=float(days)),
                reason=f"Banned by {ctx.author} ({ctx.author.id}) - {reason}"
            )
            await self._log_mod_action(
                ctx.guild.id,
                member.id,
                "ban",
                reason,
                ctx.author.id
            )
            await ctx.respond(f"✅ Banned {member.mention} | {reason}")
        except discord.Forbidden:
            await ctx.respond("❌ I don't have permission to ban this member!")
        except Exception as e:
            await ctx.respond(f"❌ An error occurred: {str(e)}")    
            
    @slash_command(name="kick", description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    @option("member", description="The member to kick", type=discord.Member)
    @option("reason", description="Reason for the kick", type=str, default="No reason provided")
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        reason: str = "No reason provided"
    ) -> None:
        try:
            try:
                embed = discord.Embed(
                    title=f"You have been kicked from {ctx.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.orange()
                )
                await member.send(embed=embed)
            except:
                pass

            await member.kick(reason=f"Kicked by {ctx.author} ({ctx.author.id}) - {reason}")
            await self._log_mod_action(
                ctx.guild.id,
                member.id,
                "kick",
                reason,
                ctx.author.id
            )
            await ctx.respond(f"✅ Kicked {member.mention} | {reason}")
        except discord.Forbidden:
            await ctx.respond("❌ I don't have permission to kick this member!")
        except Exception as e:
            await ctx.respond(f"❌ An error occurred: {str(e)}")    
            
    @slash_command(name="timeout", description="Timeout (mute) a member")
    @commands.has_permissions(moderate_members=True)
    @option("member", description="The member to timeout", type=discord.Member)
    @option("minutes", description="Duration in minutes", type=int, min_value=1, max_value=40320, default=5)
    @option("reason", description="Reason for the timeout", type=str, default="No reason provided")
    async def timeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        minutes: int = 5,
        reason: str = "No reason provided"
    ) -> None:
        # Validate duration
        minutes = max(1, min(40320, minutes))

        try:
            until = discord.utils.utcnow() + timedelta(minutes=minutes)
            try:
                embed = discord.Embed(
                    title=f"You have been timed out in {ctx.guild.name}",
                    description=f"**Duration:** {minutes} minutes\n**Reason:** {reason}",
                    color=discord.Color.orange()
                )
                await member.send(embed=embed)
            except:
                pass

            await member.timeout(until=until, reason=f"Timed out by {ctx.author} ({ctx.author.id}) - {reason}")
            await self._log_mod_action(
                ctx.guild.id,
                member.id,
                "timeout",
                f"{minutes} minutes - {reason}",
                ctx.author.id
            )
            await ctx.respond(f"✅ Timed out {member.mention} for {minutes} minutes | {reason}")
        except discord.Forbidden:
            await ctx.respond("❌ I don't have permission to timeout this member!")
        except Exception as e:
            await ctx.respond(f"❌ An error occurred: {str(e)}")    
            
    @slash_command(name="warn", description="Issue a warning to a member")
    @commands.has_permissions(moderate_members=True)
    @option("member", description="The member to warn", type=discord.Member)
    @option("reason", description="Reason for the warning", type=str)
    async def warn(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        reason: str
    ) -> None:
        try:
            try:
                embed = discord.Embed(
                    title=f"You have been warned in {ctx.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.yellow()
                )
                await member.send(embed=embed)
            except:
                pass

            await self._log_mod_action(
                ctx.guild.id,
                member.id,
                "warn",
                reason,
                ctx.author.id
            )
            await ctx.respond(f"✅ Warned {member.mention} | {reason}")
        except Exception as e:
            await ctx.respond(f"❌ An error occurred: {str(e)}")    
            
    @slash_command(name="clear", description="Clear a specified number of messages")
    @commands.has_permissions(manage_messages=True)
    @option("amount", description="Number of messages to delete", type=int, min_value=1, max_value=1000, default=10)
    @option("channel", description="Channel to clear (current if not specified)", type=discord.TextChannel, required=False)
    async def clear(
        self,
        ctx: discord.ApplicationContext,
        amount: int = 10,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        # Validate amount
        amount = max(1, min(1000, amount))
        channel = channel or ctx.channel

        if not channel:
            await ctx.respond("❌ Invalid channel specified!")
            return
            
        try:
            deleted = await channel.purge(
                limit=amount,
                reason=f"Cleared by {ctx.author} ({ctx.author.id})"
            )
            
            await self._log_mod_action(
                ctx.guild.id,
                ctx.author.id,
                "clear_messages",
                f"Cleared {len(deleted)} messages in {channel.name}",
                ctx.author.id
            )
            
            await ctx.respond(
                f"✅ Cleared {len(deleted)} messages in {channel.mention}",
                delete_after=5
            )
        except discord.Forbidden:
            await ctx.respond("❌ I don't have permission to delete messages!")
        except Exception as e:
            await ctx.respond(f"❌ An error occurred: {str(e)}")

def setup(bot):
    bot.add_cog(Moderation(bot))
