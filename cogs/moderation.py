import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional
from datetime import datetime, timedelta
import asyncio

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _log_mod_action(
        self,
        guild: discord.Guild,
        target: discord.Member,
        moderator: discord.Member,
        action: str,
        reason: str,
        duration: Optional[timedelta] = None
    ):
        """Log a moderation action to the database and logging channel"""
        if not self.bot.db_manager:
            return

        try:
            # Store in database
            await self.bot.db_manager.add_mod_action(
                guild.id,
                target.id,
                moderator.id,
                action,
                reason,
                datetime.utcnow() + duration if duration else None
            )

            # Create log embed
            embed = discord.Embed(
                title=f"Moderation Action: {action.title()}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="User", value=f"{target.mention} ({target.id})")
            embed.add_field(name="Moderator", value=moderator.mention)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            if duration:
                embed.add_field(
                    name="Duration",
                    value=f"Until <t:{int((datetime.utcnow() + duration).timestamp())}:F>"
                )

            # Send to logging channel
            channel_id = await self.bot.db_manager.get_logging_channel(guild.id, "mod")
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

        except Exception as e:
            print(f"Error logging moderation action: {e}")

    @commands.hybrid_command()
    @commands.has_permissions(kick_members=True)
    @app_commands.describe(
        user="The user to kick",
        reason="The reason for the kick",
        delete_days="Number of days of messages to delete (0-7)"
    )
    async def kick(
        self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str,
        delete_days: Optional[int] = 0
    ):
        """Kick a member from the server"""
        if user.top_role >= ctx.author.top_role:
            return await ctx.send(
                "❌ You cannot kick someone with a role higher than or equal to yours.",
                ephemeral=True
            )

        try:
            # Send DM to user
            try:
                embed = discord.Embed(
                    title=f"Kicked from {ctx.guild.name}",
                    description=f"You were kicked by {ctx.author.mention}",
                    color=discord.Color.red()
                )
                embed.add_field(name="Reason", value=reason)
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

            await user.kick(reason=f"{ctx.author}: {reason}")
            
            # Log action
            await self._log_mod_action(
                ctx.guild,
                user,
                ctx.author,
                "kick",
                reason
            )

            # Delete messages if specified
            if delete_days > 0:
                delete_days = min(7, max(0, delete_days))
                for channel in ctx.guild.text_channels:
                    try:
                        async for message in channel.history(
                            limit=None,
                            after=datetime.utcnow() - timedelta(days=delete_days)
                        ):
                            if message.author.id == user.id:
                                await message.delete()
                    except discord.Forbidden:
                        continue

            await ctx.send(
                f"✅ Kicked {user.mention} | Reason: {reason}",
                ephemeral=True
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to kick that user.",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to ban",
        reason="The reason for the ban",
        delete_days="Number of days of messages to delete (0-7)",
        duration="Ban duration in days (leave empty for permanent)"
    )
    async def ban(
        self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str,
        delete_days: Optional[int] = 0,
        duration: Optional[int] = None
    ):
        """Ban a member from the server"""
        if user.top_role >= ctx.author.top_role:
            return await ctx.send(
                "❌ You cannot ban someone with a role higher than or equal to yours.",
                ephemeral=True
            )

        try:
            # Send DM to user
            try:
                embed = discord.Embed(
                    title=f"Banned from {ctx.guild.name}",
                    description=f"You were banned by {ctx.author.mention}",
                    color=discord.Color.red()
                )
                embed.add_field(name="Reason", value=reason)
                if duration:
                    embed.add_field(
                        name="Duration",
                        value=f"{duration} days"
                    )
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

            delete_days = min(7, max(0, delete_days))
            await user.ban(
                reason=f"{ctx.author}: {reason}",
                delete_message_days=delete_days
            )
            
            # Log action
            await self._log_mod_action(
                ctx.guild,
                user,
                ctx.author,
                "ban",
                reason,
                timedelta(days=duration) if duration else None
            )

            # Schedule unban if duration specified
            if duration:
                async def unban_task():
                    await asyncio.sleep(duration * 86400)  # days to seconds
                    try:
                        await ctx.guild.unban(user, reason="Temporary ban expired")
                        await self._log_mod_action(
                            ctx.guild,
                            user,
                            self.bot.user,
                            "unban",
                            "Temporary ban expired"
                        )
                    except:
                        pass

                asyncio.create_task(unban_task())

            await ctx.send(
                f"✅ Banned {user.mention} | Reason: {reason}"
                + (f" | Duration: {duration} days" if duration else ""),
                ephemeral=True
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to ban that user.",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(
        user="The user ID to unban",
        reason="The reason for the unban"
    )
    async def unban(
        self,
        ctx: commands.Context,
        user: str,
        reason: str
    ):
        """Unban a user by ID"""
        try:
            try:
                user_id = int(user)
                ban_entry = await ctx.guild.fetch_ban(discord.Object(id=user_id))
                user_obj = ban_entry.user
            except ValueError:
                return await ctx.send(
                    "❌ Please provide a valid user ID.",
                    ephemeral=True
                )
            except discord.NotFound:
                return await ctx.send(
                    "❌ This user is not banned.",
                    ephemeral=True
                )

            await ctx.guild.unban(user_obj, reason=f"{ctx.author}: {reason}")
            
            # Log action
            await self._log_mod_action(
                ctx.guild,
                user_obj,
                ctx.author,
                "unban",
                reason
            )

            await ctx.send(
                f"✅ Unbanned {user_obj.mention} | Reason: {reason}",
                ephemeral=True
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to unban users.",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_command()
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(
        user="The user to timeout",
        duration="Timeout duration in minutes",
        reason="The reason for the timeout"
    )
    async def timeout(
        self,
        ctx: commands.Context,
        user: discord.Member,
        duration: int,
        reason: str
    ):
        """Timeout a member"""
        if user.top_role >= ctx.author.top_role:
            return await ctx.send(
                "❌ You cannot timeout someone with a role higher than or equal to yours.",
                ephemeral=True
            )

        try:
            duration = min(40320, max(1, duration))  # 28 days maximum
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            
            # Send DM to user
            try:
                embed = discord.Embed(
                    title=f"Timeout in {ctx.guild.name}",
                    description=f"You were timed out by {ctx.author.mention}",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Reason", value=reason)
                embed.add_field(
                    name="Duration",
                    value=f"Until <t:{int(until.timestamp())}:F>"
                )
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

            await user.timeout(until, reason=f"{ctx.author}: {reason}")
            
            # Log action
            await self._log_mod_action(
                ctx.guild,
                user,
                ctx.author,
                "timeout",
                reason,
                timedelta(minutes=duration)
            )

            await ctx.send(
                f"✅ Timed out {user.mention} for {duration} minutes | Reason: {reason}",
                ephemeral=True
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to timeout that user.",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_command()
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(
        user="The user to warn",
        reason="The reason for the warning"
    )
    async def warn(
        self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str
    ):
        """Warn a member"""
        if user.top_role >= ctx.author.top_role:
            return await ctx.send(
                "❌ You cannot warn someone with a role higher than or equal to yours.",
                ephemeral=True
            )

        try:
            # Send DM to user
            try:
                embed = discord.Embed(
                    title=f"Warning in {ctx.guild.name}",
                    description=f"You were warned by {ctx.author.mention}",
                    color=discord.Color.yellow()
                )
                embed.add_field(name="Reason", value=reason)
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

            # Log action
            await self._log_mod_action(
                ctx.guild,
                user,
                ctx.author,
                "warn",
                reason
            )

            # Get warning count
            warnings = await self.bot.db_manager.get_user_warnings(
                ctx.guild.id,
                user.id
            )

            await ctx.send(
                f"✅ Warned {user.mention} | Reason: {reason} | Total Warnings: {len(warnings)}",
                ephemeral=True
            )

        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_command()
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user"
    )
    async def purge(
        self,
        ctx: commands.Context,
        amount: int,
        user: Optional[discord.Member] = None
    ):
        """Purge messages from a channel"""
        try:
            amount = min(100, max(1, amount))
            
            def check(msg):
                return not user or msg.author == user

            deleted = await ctx.channel.purge(
                limit=amount + 1,  # +1 for command message
                check=check
            )

            # Log action
            await self._log_mod_action(
                ctx.guild,
                user or ctx.guild.me,  # if no user specified, use bot as target
                ctx.author,
                "purge",
                f"Purged {len(deleted) - 1} messages in {ctx.channel.mention}"
                + (f" from {user.mention}" if user else "")
            )

            # Send confirmation
            confirm_msg = await ctx.send(
                f"✅ Purged {len(deleted) - 1} messages"
                + (f" from {user.mention}" if user else ""),
                ephemeral=True
            )
            await asyncio.sleep(5)
            try:
                await confirm_msg.delete()
            except:
                pass

        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to delete messages.",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.hybrid_group(fallback="view")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx: commands.Context, user: discord.Member):
        """View warnings for a user"""
        try:
            warnings = await self.bot.db_manager.get_user_warnings(
                ctx.guild.id,
                user.id
            )

            if not warnings:
                return await ctx.send(
                    f"{user.mention} has no warnings.",
                    ephemeral=True
                )

            embed = discord.Embed(
                title=f"Warnings for {user.display_name}",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            for i, warning in enumerate(warnings, 1):
                mod = ctx.guild.get_member(warning["moderator_id"])
                embed.add_field(
                    name=f"Warning #{i}",
                    value=f"""
                    **Reason:** {warning['reason']}
                    **Moderator:** {mod.mention if mod else 'Unknown'}
                    **Date:** <t:{int(warning['created_at'].timestamp())}:F>
                    """.strip(),
                    inline=False
                )

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    @warnings.command(name="clear")
    @commands.has_permissions(moderate_members=True)
    async def clear_warnings(self, ctx: commands.Context, user: discord.Member):
        """Clear all warnings for a user"""
        try:
            await self.bot.db_manager.clear_user_warnings(
                ctx.guild.id,
                user.id
            )

            # Log action
            await self._log_mod_action(
                ctx.guild,
                user,
                ctx.author,
                "clear_warnings",
                "Cleared all warnings"
            )

            await ctx.send(
                f"✅ Cleared all warnings for {user.mention}",
                ephemeral=True
            )

        except Exception as e:
            await ctx.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))