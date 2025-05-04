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
        # Store last deleted/edited messages per channel
        self.deleted_messages = {}
        self.edited_messages = {}

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
            
        self.deleted_messages[message.channel.id] = {
            'content': message.content,
            'author': message.author,
            'timestamp': message.created_at,
            'attachments': [a.url for a in message.attachments]
        }

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Store last edited message per channel"""
        if not before.guild or before.author.bot or before.content == after.content:
            return

        self.edited_messages[before.channel.id] = {
            'before': before.content,
            'after': after.content,
            'author': before.author,
            'timestamp': after.edited_at or discord.utils.utcnow()
        }

    @app_commands.command(
        name="warn",
        description="Warn a user"
    )
    @app_commands.describe(
        user="The user to warn",
        reason="The reason for warning the user"
    )
    @app_commands.default_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = None
    ):
        """Warn a user"""
        try:
            # Defer the response immediately to prevent timeout
            await interaction.response.defer()

            if not interaction.user.guild_permissions.moderate_members:
                raise commands.MissingPermissions(["moderate_members"])

            # Check bot's role hierarchy
            if user.top_role >= interaction.guild.me.top_role:
                raise commands.CommandError("I cannot warn this user as their role is higher than or equal to my highest role")

            # Check command user's role hierarchy
            if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                raise commands.CommandError("You cannot warn someone with a higher or equal role")

            if reason is None:
                reason = "No reason provided"

            # Try to DM the user first with a timeout
            try:
                await asyncio.wait_for(
                    user.send(
                        embed=self.bot.ui_manager.warning_embed(
                            "Warning",
                            f"You were warned in {interaction.guild.name}\n**Reason:** {reason}"
                        )
                    ),
                    timeout=5.0
                )
            except (discord.Forbidden, asyncio.TimeoutError):
                pass

            # Add warning to database with timeout
            try:
                async with asyncio.timeout(10.0):
                    await self.bot.db_manager.add_warning(
                        guild_id=interaction.guild.id,
                        user_id=user.id,
                        mod_id=interaction.user.id,  # Changed from moderator_id to mod_id
                        reason=reason
                    )
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "The warning operation timed out while updating the database. Please try again."
                    ),
                    ephemeral=True
                )
                return

            embed = self.bot.ui_manager.mod_embed(
                "User Warned",
                f"**User:** {user}\n**Reason:** {reason}"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    str(e)
                ),
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
        reason: str = None
    ):
        """Kick a user from the server"""
        try:
            # Defer the response immediately to prevent timeout
            await interaction.response.defer()

            if not interaction.user.guild_permissions.kick_members:
                raise commands.MissingPermissions(["kick_members"])

            if user.top_role >= interaction.user.top_role:
                raise commands.CommandError("You cannot kick someone with a higher or equal role.")

            if reason is None:
                reason = "No reason provided"

            # Try to DM the user first with a timeout
            try:
                await asyncio.wait_for(
                    user.send(
                        embed=self.bot.ui_manager.warning_embed(
                            "Kicked",
                            f"You were kicked from {interaction.guild.name}\n**Reason:** {reason}"
                        )
                    ),
                    timeout=5.0
                )
            except (discord.Forbidden, asyncio.TimeoutError):
                pass  # Continue even if DM fails

            # Perform the kick with timeout
            try:
                async with asyncio.timeout(10.0):
                    await user.kick(reason=reason)
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "The kick operation timed out. Please try again."
                    ),
                    ephemeral=True
                )
                return
            except discord.Forbidden:
                await interaction.followup.send(
                    embed=self.bot.ui_manager.error_embed(
                        "Error",
                        "I don't have permission to kick this user."
                    ),
                    ephemeral=True
                )
                return

            embed = self.bot.ui_manager.mod_embed(
                "User Kicked",
                f"**User:** {user}\n**Reason:** {reason}"
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Error",
                    f"An error occurred while kicking the user: {str(e)}"
                ),
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
            # Defer the response immediately to prevent timeout
            await interaction.response.defer()

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
            # Defer the response immediately to prevent timeout
            await interaction.response.defer()

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

            await interaction.followup.send(embed=embed)

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
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Manage Channels permission to use this command."
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
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
        description="Show the last deleted or edited message in the channel"
    )
    @app_commands.describe(
        type="Type of message to snipe (deleted or edited)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Deleted message", value="deleted"),
        app_commands.Choice(name="Edited message", value="edited")
    ])
    @app_commands.default_permissions(manage_messages=True)
    async def snipe(
        self,
        interaction: discord.Interaction,
        type: str
    ):
        """Show recently deleted or edited messages"""
        try:
            if not interaction.user.guild_permissions.manage_messages:
                raise commands.MissingPermissions(["manage_messages"])

            # Get message from memory
            messages = self.deleted_messages if type == "deleted" else self.edited_messages
            message_data = messages.get(interaction.channel.id)
            
            if not message_data:
                await interaction.response.send_message(
                    embed=self.bot.ui_manager.error_embed(
                        "No Messages Found",
                        "No recently deleted or edited messages found in this channel"
                    ),
                    ephemeral=True
                )
                return

            # Create snipe embed
            embed = self.bot.ui_manager.mod_embed(
                f"Sniped Message ({type.title()})",
                message_data['content'] if type == "deleted" else message_data['after']
            )

            # Add author info
            embed.add_field(
                name="Author",
                value=message_data['author'].mention,
                inline=True
            )

            # Add timestamp
            embed.add_field(
                name="When",
                value=discord.utils.format_dt(message_data['timestamp'], style='R'),
                inline=True
            )

            # For edited messages, show both versions
            if type == "edited":
                embed.add_field(
                    name="Original Content",
                    value=message_data['before'],
                    inline=False
                )

            # Add attachments if any (for deleted messages)
            if type == "deleted" and message_data.get('attachments'):
                embed.add_field(
                    name="Attachments",
                    value="\n".join(message_data['attachments']),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except commands.MissingPermissions:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need Manage Messages permission to use this command"
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
            # Defer the response immediately to prevent timeout
            await interaction.response.defer()

            if not interaction.user.guild_permissions.moderate_members:
                raise commands.MissingPermissions(["moderate_members"])

            if duration < 1:
                raise ValueError("Duration must be at least 1 minute")

            if user.top_role >= interaction.user.top_role:
                raise commands.CommandError("You cannot timeout someone with a higher or equal role")

            # Apply timeout using aware datetime
            until = datetime.now(discord.utils.utc) + timedelta(minutes=duration)
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

            await interaction.followup.send(embed=embed)

        except commands.MissingPermissions as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed(
                    "Missing Permissions",
                    "You need the Moderate Members permission to use this command."
                ),
                ephemeral=True
            )
        except ValueError as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Invalid Value", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))