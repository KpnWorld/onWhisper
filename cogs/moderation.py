import discord
from discord.ext import commands
from typing import Optional
import asyncio
from datetime import datetime, timedelta

class DurationSelect(discord.ui.View):
    def __init__(self, user: discord.Member, mod: discord.Member, reason: Optional[str]):
        super().__init__(timeout=60)
        self.user = user
        self.mod = mod
        self.reason = reason
        self.duration = None

    @discord.ui.select(
        placeholder="Select timeout duration",
        options=[
            discord.SelectOption(label="60 seconds", value="60s", description="1 minute timeout"),
            discord.SelectOption(label="5 minutes", value="5m", description="5 minute timeout"),
            discord.SelectOption(label="10 minutes", value="10m", description="10 minute timeout"),
            discord.SelectOption(label="1 hour", value="1h", description="1 hour timeout"),
            discord.SelectOption(label="6 hours", value="6h", description="6 hour timeout"),
            discord.SelectOption(label="12 hours", value="12h", description="12 hour timeout"),
            discord.SelectOption(label="1 day", value="1d", description="1 day timeout"),
            discord.SelectOption(label="1 week", value="7d", description="1 week timeout"),
            discord.SelectOption(label="2 weeks", value="14d", description="2 week timeout"),
            discord.SelectOption(label="28 days", value="28d", description="Maximum timeout (28 days)")
        ]
    )
    async def duration_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.duration = select.values[0]
        self.stop()
        await interaction.response.defer()

class Moderation(commands.Cog):
    """Admin & mod tools"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.db_manager
        self.ui = self.bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())
        self.locked_channels = set()

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db_manager.ensure_connection():
                print("❌ Database not available for Moderation cog")
                return
            self._ready.set()
            print("✅ Moderation cog ready")
        except Exception as e:
            print(f"❌ Error setting up Moderation cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    async def log_mod_action(self, guild: discord.Guild, action: str, description: str):
        """Send mod action to logging channel"""
        try:
            config = await self.db_manager.get_data('logging_config', str(guild.id))
            if not config or not config.get('enabled', True):
                return

            channel_id = config.get('mod_channel')
            if not channel_id:
                return

            channel = guild.get_channel(channel_id)
            if channel:
                embed = self.ui.mod_embed(
                    action,
                    description
                )
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error logging mod action: {e}")

    @commands.hybrid_command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str):
        """Issue a warning"""
        try:
            if user.top_role >= ctx.author.top_role:
                await ctx.send("You cannot warn members with higher roles!", ephemeral=True)
                return

            # Add warning
            await self.db_manager.add_warning(
                ctx.guild.id,
                user.id,
                ctx.author.id,
                reason,
                datetime.utcnow()
            )

            # Get warning count
            warnings = await self.db_manager.get_warnings(ctx.guild.id, user.id)
            count = len(warnings)

            # Send warning message
            embed = self.ui.mod_embed(
                "Warning Issued",
                f"**User:** {user.mention}\n"
                f"**Reason:** {reason}\n"
                f"**Total Warnings:** {count}"
            )
            await ctx.send(embed=embed)

            # Log action
            await self.log_mod_action(
                ctx.guild,
                "Warning",
                f"{user.mention} was warned by {ctx.author.mention}\nReason: {reason}"
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="warnings")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx, user: discord.Member):
        """View a user's warnings"""
        try:
            warnings = await self.db_manager.get_warnings(ctx.guild.id, user.id)
            
            if not warnings:
                await ctx.send(f"{user.display_name} has no warnings.")
                return

            description = ""
            for i, warning in enumerate(warnings, 1):
                mod_id = warning.get('mod_id')
                reason = warning.get('reason')
                timestamp = datetime.fromisoformat(warning.get('timestamp'))
                mod = ctx.guild.get_member(mod_id)
                mod_name = mod.mention if mod else "Unknown Moderator"
                
                description += f"**Warning {i}**\n"
                description += f"By: {mod_name}\n"
                description += f"When: <t:{int(timestamp.timestamp())}:R>\n"
                description += f"Reason: {reason}\n\n"

            embed = self.ui.info_embed(
                f"Warnings for {user.display_name}",
                description
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason: Optional[str] = None):
        """Kick a member"""
        try:
            if user.top_role >= ctx.author.top_role:
                await ctx.send("You cannot kick members with higher roles!", ephemeral=True)
                return

            if user.top_role >= ctx.guild.me.top_role:
                await ctx.send("I cannot kick members with roles higher than mine!", ephemeral=True)
                return

            await user.kick(reason=f"Kicked by {ctx.author}: {reason}")

            embed = self.ui.mod_embed(
                "Member Kicked",
                f"**User:** {user.mention}\n"
                f"**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)

            await self.log_mod_action(
                ctx.guild,
                "Kick",
                f"{user.mention} was kicked by {ctx.author.mention}\nReason: {reason}"
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, *, reason: Optional[str] = None):
        """Ban a member"""
        try:
            if user.top_role >= ctx.author.top_role:
                await ctx.send("You cannot ban members with higher roles!", ephemeral=True)
                return

            if user.top_role >= ctx.guild.me.top_role:
                await ctx.send("I cannot ban members with roles higher than mine!", ephemeral=True)
                return

            await user.ban(reason=f"Banned by {ctx.author}: {reason}")

            embed = self.ui.mod_embed(
                "Member Banned",
                f"**User:** {user.mention}\n"
                f"**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)

            await self.log_mod_action(
                ctx.guild,
                "Ban",
                f"{user.mention} was banned by {ctx.author.mention}\nReason: {reason}"
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, user: discord.Member, *, reason: Optional[str] = None):
        """Temporarily mute a user
        
        Parameters
        ----------
        user : The user to timeout
        reason : The reason for the timeout (optional)
        """
        try:
            # Check if the target is the bot itself
            if user == ctx.guild.me:
                await ctx.send("I cannot timeout myself!", ephemeral=True)
                return

            # Check if user is trying to timeout themselves
            if user == ctx.author:
                await ctx.send("You cannot timeout yourself!", ephemeral=True)
                return

            # Check role hierarchy - command user vs target
            if not ctx.author.top_role > user.top_role and ctx.author != ctx.guild.owner:
                await ctx.send("You can only timeout members with roles lower than yours!", ephemeral=True)
                return

            # Check role hierarchy - bot vs target
            if not ctx.guild.me.top_role > user.top_role:
                await ctx.send("I can only timeout members with roles lower than mine!", ephemeral=True)
                return

            # Show duration selection
            view = DurationSelect(user, ctx.author, reason)
            sent = await ctx.send(f"Select timeout duration for {user.mention}:", view=view)
            view.message = sent
            await view.wait()

            if not view.duration:
                await ctx.send("Timeout cancelled - no duration selected.", ephemeral=True)
                return

            # Parse duration
            units = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400
            }
            amount = int(''.join(filter(str.isdigit, view.duration)))
            unit = view.duration[-1].lower()
            seconds = amount * units[unit]

            # Apply timeout
            until = discord.utils.utcnow() + timedelta(seconds=seconds)
            await user.timeout(until, reason=f"Timed out by {ctx.author}: {reason}")

            embed = self.ui.mod_embed(
                "Member Timed Out",
                f"**User:** {user.mention}\n"
                f"**Duration:** {view.duration}\n"
                f"**Reason:** {reason or 'No reason provided'}"
            )
            await ctx.send(embed=embed)

            await self.log_mod_action(
                ctx.guild,
                "Timeout",
                f"{user.mention} was timed out for {view.duration} by {ctx.author.mention}\nReason: {reason or 'No reason provided'}"
            )

        except discord.Forbidden:
            await ctx.send("I don't have permission to timeout this user! Make sure I have the 'Moderate Members' permission and my role is above the target user.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred while trying to timeout the user: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="purge")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Bulk delete messages"""
        try:
            if amount < 1 or amount > 100:
                await ctx.send("Amount must be between 1 and 100!", ephemeral=True)
                return

            # Defer the response since this might take a while
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.defer(ephemeral=True)
            
            # For text commands, we need to account for the command message
            if not isinstance(ctx.interaction, discord.Interaction):
                amount += 1  # Add 1 to include command message
            
            # Purge messages
            deleted = await ctx.channel.purge(limit=amount)
            actual_count = len(deleted)
            
            # Adjust count for text commands to not include command message
            if not isinstance(ctx.interaction, discord.Interaction):
                actual_count -= 1
            
            # Log the action
            await self.log_mod_action(
                ctx.guild,
                "Purge",
                f"{ctx.author.mention} purged {actual_count} messages in {ctx.channel.mention}"
            )

            # Send confirmation
            embed = self.ui.mod_embed(
                "Messages Purged",
                f"Successfully deleted {actual_count} messages"
            )
            
            # For slash commands, edit the deferred response
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.send(embed=embed, ephemeral=True)
            else:
                # For text commands, send and delete after delay
                confirmation = await ctx.send(embed=embed)
                await asyncio.sleep(5)
                try:
                    await confirmation.delete()
                except discord.NotFound:
                    pass

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="lockdown")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown(self, ctx, channel: Optional[discord.TextChannel] = None, duration: Optional[str] = None):
        """Lock a channel temporarily"""
        try:
            channel = channel or ctx.channel
            
            if channel.id in self.locked_channels:
                await ctx.send("This channel is already locked!", ephemeral=True)
                return

            # Set up overwrites
            overwrites = channel.overwrites
            for role in ctx.guild.roles:
                if not role.permissions.administrator:
                    perm = overwrites.get(role, discord.PermissionOverwrite())
                    perm.send_messages = False
                    overwrites[role] = perm

            await channel.edit(overwrites=overwrites)
            self.locked_channels.add(channel.id)

            # Handle duration
            if duration:
                units = {
                    's': 1,
                    'm': 60,
                    'h': 3600,
                    'd': 86400
                }
                amount = int(''.join(filter(str.isdigit, duration)))
                unit = duration[-1].lower()
                
                if unit in units:
                    seconds = amount * units[unit]
                    self.bot.loop.create_task(self.unlock_after(channel, seconds))
                    duration_text = f" for {duration}"
                else:
                    duration_text = ""
            else:
                duration_text = ""

            embed = self.ui.mod_embed(
                "Channel Locked",
                f"{channel.mention} has been locked{duration_text}"
            )
            await ctx.send(embed=embed)

            await self.log_mod_action(
                ctx.guild,
                "Lockdown",
                f"{ctx.author.mention} locked {channel.mention}{duration_text}"
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    async def unlock_after(self, channel: discord.TextChannel, seconds: int):
        """Helper to unlock channel after duration"""
        try:
            await asyncio.sleep(seconds)
            
            if channel.id in self.locked_channels:
                overwrites = channel.overwrites
                for role, perms in overwrites.items():
                    if not role.permissions.administrator:
                        perms.send_messages = None
                        if perms.is_empty():
                            del overwrites[role]
                        
                await channel.edit(overwrites=overwrites)
                self.locked_channels.remove(channel.id)
                
                await channel.send("🔓 Channel unlocked!")
        except Exception as e:
            print(f"Error unlocking channel: {e}")

    @commands.hybrid_command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int, channel: Optional[discord.TextChannel] = None):
        """Set slowmode in a channel"""
        try:
            channel = channel or ctx.channel
            
            if seconds < 0 or seconds > 21600:
                await ctx.send("Slowmode must be between 0 and 21600 seconds!", ephemeral=True)
                return

            await channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                description = f"Slowmode disabled in {channel.mention}"
            else:
                description = f"Slowmode set to {seconds} seconds in {channel.mention}"

            embed = self.ui.mod_embed(
                "Slowmode Updated",
                description
            )
            await ctx.send(embed=embed)

            await self.log_mod_action(
                ctx.guild,
                "Slowmode",
                f"{ctx.author.mention} set slowmode to {seconds}s in {channel.mention}"
            )

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @commands.hybrid_command(name="snipe")
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        """Retrieve last deleted message"""
        try:
            deleted = await self.db_manager.get_last_deleted(ctx.channel.id)
            
            if not deleted:
                await ctx.send("No recently deleted messages found!", ephemeral=True)
                return

            content = deleted.get('content', 'No content')
            author_id = deleted.get('author_id')
            timestamp = datetime.fromisoformat(deleted.get('timestamp'))
            
            author = ctx.guild.get_member(author_id)
            author_name = author.display_name if author else "Unknown User"

            embed = self.ui.info_embed(
                f"Last Deleted Message",
                f"**Author:** {author_name}\n"
                f"**When:** <t:{int(timestamp.timestamp())}:R>\n"
                f"**Content:**\n{content}"
            )
            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))