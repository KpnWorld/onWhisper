import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_deleted = {}  # Channel ID -> Last deleted message

    # Helper method to log moderation events
    async def log_mod_action(self, guild_id: int, action: str, user: discord.Member, mod: discord.Member, reason: str = None):
        """Log a moderation action to the moderation log channel"""
        embed = discord.Embed(
            title=f"Moderation Action: {action.title()}",
            description=f"{user.mention} was {action} by {mod.mention}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
            
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"User ID: {user.id}")
        
        try:
            # Get the logging cog
            logging_cog = self.bot.get_cog('LoggingCog')
            if logging_cog:
                await logging_cog.log_event(guild_id, "moderation", embed)
        except Exception as e:
            print(f"Error sending moderation log: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Store last deleted message per channel"""
        if not message.guild or message.author.bot:
            return
            
        self.last_deleted[message.channel.id] = {
            'content': message.content,
            'author': message.author.id,
            'timestamp': message.created_at.isoformat(),
            'attachments': [a.url for a in message.attachments]
        }

    @app_commands.command(
        name="warn",
        description="Warn a user"
    )
    @app_commands.describe(
        user="The user to warn",
        reason="The reason for the warning"
    )
    @app_commands.default_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        """Warn a user and log the action"""
        try:
            if not interaction.user.guild_permissions.moderate_members:
                raise commands.MissingPermissions(["moderate_members"])

            # Add warning
            success = await self.bot.db_manager.add_warning(
                interaction.guild_id,
                user.id,
                interaction.user.id,
                reason
            )

            if not success:
                raise Exception("Failed to save warning")

            # Get user's warnings
            warnings = await self.bot.db_manager.get_user_warnings(interaction.guild_id, user.id)

            # Create warn embed
            embed = self.bot.ui_manager.mod_embed(
                "User Warned",
                f"**User:** {user.mention}\n**Reason:** {reason}\n**Total Warnings:** {len(warnings)}"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            # Log the action to both DB and logging channel
            await self.bot.db_manager.add_mod_action(
                interaction.guild_id,
                "warn",
                user.id,
                f"Warning by {interaction.user}: {reason}"
            )
            await self.log_mod_action(interaction.guild_id, "warned", user, interaction.user, reason)

            # Notify the user
            try:
                await user.send(
                    embed=self.bot.ui_manager.warning_embed(
                        "Warning Received",
                        f"You were warned in {interaction.guild.name}\n**Reason:** {reason}"
                    )
                )
            except discord.Forbidden:
                embed.add_field(
                    name="Note",
                    value="Could not DM user about the warning",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Moderate Members permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="warnings",
        description="View warnings for a user"
    )
    @app_commands.describe(
        user="The user to check warnings for"
    )
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """View a user's warning history"""
        try:
            if not interaction.user.guild_permissions.moderate_members:
                raise commands.MissingPermissions(["moderate_members"])

            warnings = await self.bot.db_manager.get_user_warnings(interaction.guild_id, user.id)

            if not warnings:
                embed = self.bot.ui_manager.info_embed(
                    "No Warnings",
                    f"{user.display_name} has no warnings."
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                await interaction.response.send_message(embed=embed)
                return

            # Create pages for each warning
            pages = []
            for i, warning in enumerate(warnings, 1):
                embed = self.bot.ui_manager.mod_embed(
                    f"Warning #{i}",
                    f"**User:** {user.mention}\n**Reason:** {warning['details']}"
                )
                embed.add_field(
                    name="Warned By",
                    value=f"<@{warning['mod_id']}>",
                    inline=True
                )
                embed.add_field(
                    name="Date",
                    value=discord.utils.format_dt(
                        datetime.fromisoformat(warning['timestamp']),
                        style='R'
                    ),
                    inline=True
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                pages.append(embed)

            await self.bot.ui_manager.paginate(
                interaction,
                pages,
                ephemeral=True
            )

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Moderate Members permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="kick",
        description="Kick a user from the server"
    )
    @app_commands.describe(
        user="The user to kick",
        reason="The reason for kicking the user"
    )
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str
    ):
        """Kick a user from the server"""
        try:
            if not interaction.user.guild_permissions.kick_members:
                raise commands.MissingPermissions(["kick_members"])

            if user.top_role >= interaction.user.top_role:
                raise commands.CommandError("You cannot kick someone with a higher or equal role.")

            # Ask for confirmation
            confirmed = await self.bot.ui_manager.confirm_action(
                interaction,
                "Confirm Kick",
                f"Are you sure you want to kick {user.mention}?",
                confirm_label="Kick",
                cancel_label="Cancel"
            )

            if not confirmed:
                return

            # Try to DM the user
            try:
                await user.send(
                    embed=self.bot.ui_manager.warning_embed(
                        "Kicked",
                        f"You were kicked from {interaction.guild.name}\n**Reason:** {reason}"
                    )
                )
            except:
                pass

            # Kick the user
            await user.kick(reason=f"Kicked by {interaction.user}: {reason}")

            # Log the action
            await self.bot.db_manager.add_mod_action(
                interaction.guild_id,
                "kick",
                user.id,
                f"Kicked by {interaction.user}: {reason}"
            )

            embed = self.bot.ui_manager.mod_embed(
                "User Kicked",
                f"**User:** {user.mention}\n**Reason:** {reason}"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            await interaction.followup.send(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Kick Members permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="ban",
        description="Ban a user from the server"
    )
    @app_commands.describe(
        user="The user to ban",
        reason="The reason for banning the user",
        delete_days="Number of days of messages to delete (0-7)"
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        delete_days: Optional[int] = 1
    ):
        """Ban a user from the server"""
        try:
            if not interaction.user.guild_permissions.ban_members:
                raise commands.MissingPermissions(["ban_members"])

            if user.top_role >= interaction.user.top_role:
                raise commands.CommandError("You cannot ban someone with a higher or equal role.")

            if delete_days < 0 or delete_days > 7:
                raise ValueError("Delete days must be between 0 and 7")

            # Ask for confirmation
            confirmed = await self.bot.ui_manager.confirm_action(
                interaction,
                "Confirm Ban",
                f"Are you sure you want to ban {user.mention}?",
                confirm_label="Ban",
                cancel_label="Cancel"
            )

            if not confirmed:
                return

            # Try to DM the user
            try:
                await user.send(
                    embed=self.bot.ui_manager.warning_embed(
                        "Banned",
                        f"You were banned from {interaction.guild.name}\n**Reason:** {reason}"
                    )
                )
            except:
                pass

            # Ban the user
            await user.ban(
                reason=f"Banned by {interaction.user}: {reason}",
                delete_message_days=delete_days
            )

            # Log the action to both DB and logging channel
            await self.bot.db_manager.add_mod_action(
                interaction.guild_id,
                "ban",
                user.id,
                f"Banned by {interaction.user}: {reason}"
            )
            await self.log_mod_action(interaction.guild_id, "banned", user, interaction.user, reason)

            embed = self.bot.ui_manager.mod_embed(
                "User Banned",
                f"**User:** {user.mention}\n**Reason:** {reason}\n**Message Deletion:** {delete_days} days"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            await interaction.followup.send(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Ban Members permission to use this command."
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="lockdown",
        description="Lock a channel to prevent messages"
    )
    @app_commands.describe(
        channel="The channel to lock (current channel if not specified)",
        duration="Duration in minutes (leave empty for indefinite)",
        reason="Reason for the lockdown"
    )
    @app_commands.default_permissions(manage_channels=True)
    async def lockdown(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        duration: Optional[int] = None,
        reason: Optional[str] = "No reason provided"
    ):
        """Lock down a channel"""
        try:
            if not interaction.user.guild_permissions.manage_channels:
                raise commands.MissingPermissions(["manage_channels"])

            target_channel = channel or interaction.channel

            # Store the lockdown
            await self.bot.db_manager.add_channel_lock(
                interaction.guild_id,
                target_channel.id,
                duration
            )

            # Lock the channel
            await target_channel.set_permissions(
                interaction.guild.default_role,
                send_messages=False,
                reason=f"Lockdown by {interaction.user}: {reason}"
            )

            duration_text = f"for {duration} minutes" if duration else "indefinitely"
            embed = self.bot.ui_manager.mod_embed(
                "Channel Locked",
                f"🔒 {target_channel.mention} has been locked {duration_text}\n**Reason:** {reason}"
            )

            await interaction.response.send_message(embed=embed)

            # If duration set, schedule unlock
            if duration:
                await asyncio.sleep(duration * 60)
                try:
                    await target_channel.set_permissions(
                        interaction.guild.default_role,
                        send_messages=None,
                        reason=f"Lockdown expired"
                    )
                    await target_channel.send(
                        embed=self.bot.ui_manager.success_embed(
                            "Channel Unlocked",
                            "🔓 This channel has been automatically unlocked."
                        )
                    )
                except:
                    pass

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Channels permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="unlock",
        description="Unlock a locked channel"
    )
    @app_commands.describe(
        channel="The channel to unlock (current channel if not specified)"
    )
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Unlock a locked channel"""
        try:
            if not interaction.user.guild_permissions.manage_channels:
                raise commands.MissingPermissions(["manage_channels"])

            target_channel = channel or interaction.channel

            # Reset permissions
            await target_channel.set_permissions(
                interaction.guild.default_role,
                send_messages=None,
                reason=f"Unlocked by {interaction.user}"
            )

            embed = self.bot.ui_manager.mod_embed(
                "Channel Unlocked",
                f"🔓 {target_channel.mention} has been unlocked"
            )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Channels permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="slowmode",
        description="Set slowmode in a channel"
    )
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0 to disable)",
        channel="The channel to set slowmode in (current channel if not specified)"
    )
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: Optional[discord.TextChannel] = None
    ):
        """Set channel slowmode"""
        try:
            if not interaction.user.guild_permissions.manage_channels:
                raise commands.MissingPermissions(["manage_channels"])

            if seconds < 0 or seconds > 21600:  # Discord's max is 6 hours
                raise ValueError("Slowmode must be between 0 and 21600 seconds (6 hours)")

            target_channel = channel or interaction.channel
            await target_channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode set by {interaction.user}"
            )

            if seconds == 0:
                description = f"Slowmode has been disabled in {target_channel.mention}"
            else:
                description = f"Slowmode set to {seconds} seconds in {target_channel.mention}"

            embed = self.bot.ui_manager.mod_embed(
                "Slowmode Updated",
                description
            )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Channels permission to use this command."
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="clear",
        description="Clear messages in a channel"
    )
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: Optional[discord.Member] = None
    ):
        """Clear messages from a channel"""
        try:
            if not interaction.user.guild_permissions.manage_messages:
                raise commands.MissingPermissions(["manage_messages"])

            if amount < 1 or amount > 100:
                raise ValueError("Amount must be between 1 and 100")

            await interaction.response.defer(ephemeral=True)

            def check_message(message):
                return True if not user else message.author.id == user.id

            # Purge messages
            deleted = await interaction.channel.purge(
                limit=amount,
                check=check_message,
                reason=f"Clear command used by {interaction.user}"
            )

            target_text = f" from {user.mention}" if user else ""
            embed = self.bot.ui_manager.success_embed(
                "Messages Cleared",
                f"Deleted {len(deleted)} messages{target_text}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Messages permission to use this command."
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="snipe",
        description="View the last deleted message in this channel"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def snipe(self, interaction: discord.Interaction):
        """Show the last deleted message"""
        try:
            if not interaction.user.guild_permissions.manage_messages:
                raise commands.MissingPermissions(["manage_messages"])

            # Get last deleted message
            deleted = self.last_deleted.get(interaction.channel.id)
            if not deleted:
                raise commands.CommandError("No recently deleted messages found in this channel")

            # Create embed
            author = interaction.guild.get_member(deleted['author'])
            embed = self.bot.ui_manager.info_embed(
                "Last Deleted Message",
                deleted['content'] if deleted['content'] else "*No content*"
            )

            if author:
                embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)

            # Add timestamp
            embed.add_field(
                name="Sent",
                value=discord.utils.format_dt(datetime.fromisoformat(deleted['timestamp']), style='R'),
                inline=False
            )

            # Add attachments if any
            if deleted['attachments']:
                embed.add_field(
                    name="Attachments",
                    value="\n".join(deleted['attachments']),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Messages permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    @app_commands.command(
        name="timeout",
        description="Timeout a user for a specified duration"
    )
    @app_commands.describe(
        user="The user to timeout",
        duration="Duration in minutes",
        reason="Reason for the timeout"
    )
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int,
        reason: str = "No reason provided"
    ):
        """Timeout a user"""
        try:
            if not interaction.user.guild_permissions.moderate_members:
                raise commands.MissingPermissions(["moderate_members"])

            if duration < 1:
                raise ValueError("Duration must be at least 1 minute")

            if user.top_role >= interaction.user.top_role:
                raise commands.CommandError("You cannot timeout someone with a higher or equal role")

            # Apply timeout
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await user.timeout(until, reason=f"Timeout by {interaction.user}: {reason}")

            # Log the action to both DB and logging channel
            await self.bot.db_manager.add_mod_action(
                interaction.guild_id,
                "timeout",
                user.id,
                f"Timed out by {interaction.user} for {duration} minutes: {reason}",
                until
            )
            await self.log_mod_action(interaction.guild_id, "timed out", user, interaction.user, f"{duration} minutes - {reason}")

            embed = self.bot.ui_manager.mod_embed(
                "User Timed Out",
                f"**User:** {user.mention}\n**Duration:** {duration} minutes\n**Reason:** {reason}"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            # Try to DM user
            try:
                await user.send(
                    embed=self.bot.ui_manager.warning_embed(
                        "You Have Been Timed Out",
                        f"You have been timed out in {interaction.guild.name}\n"
                        f"**Duration:** {duration} minutes\n"
                        f"**Reason:** {reason}"
                    )
                )
            except:
                embed.add_field(
                    name="Note",
                    value="Could not DM user about the timeout",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Moderate Members permission to use this command."
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))