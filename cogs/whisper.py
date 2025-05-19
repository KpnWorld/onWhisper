import discord
from discord.ext import commands
from discord.commands import slash_command, option
from typing import Optional, Dict
from datetime import datetime

class Whisper(commands.Cog):
    """Thread-based ticket system"""
    
    def __init__(self, bot):
        self.bot = bot
        self._active_whispers: Dict[int, dict] = {}  # Cache of active whispers
        self.prefix = "🎫"  # Emoji prefix for whisper threads

    async def _get_settings(self, guild_id: int) -> Optional[dict]:
        """Get whisper settings for a guild"""
        settings = await self.bot.db.get_whisper_settings(guild_id)
        if not settings:
            return None
            
        channel = self.bot.get_channel(settings["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return None
            
        return {
            "channel": channel,
            "staff_role_id": settings["staff_role_id"]
        }

    async def _generate_whisper_id(self, guild_id: int) -> str:
        """Generate a unique whisper ID"""
        active = await self.bot.db.get_active_whispers(guild_id)
        base = len(active) + 1
        
        while any(str(base) == w["whisper_id"] for w in active):
            base += 1
            
        return str(base)

    async def _create_thread(
        self,
        channel: discord.TextChannel,
        user: discord.Member,
        whisper_id: str
    ) -> Optional[discord.Thread]:
        """Create a thread for a whisper"""
        try:
            thread = await channel.create_thread(
                name=f"{self.prefix} Whisper #{whisper_id} - {user.name}",
                type=discord.ChannelType.private_thread,
                reason=f"Whisper ticket created by {user}"
            )
            
            # Create initial message
            embed = discord.Embed(
                title=f"Whisper Ticket #{whisper_id}",
                description="A staff member will be with you shortly.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="Created By",
                value=user.mention,
                inline=True
            )
            
            await thread.send(
                content=f"{user.mention}",
                embed=embed
            )
            
            return thread
            
        except discord.Forbidden:
            return None
        except discord.HTTPException:
            return None    
        
    @slash_command(name="whisper", description="Create or manage whisper tickets")
    @option("action", description="The action to perform", type=str, choices=["create", "close", "delete"])
    @option("user", description="The user to manage tickets for (only needed for delete action)", type=discord.User, required=False)
    async def whisper(
        self,
        ctx: discord.ApplicationContext,
        action: str,
        user: Optional[discord.User] = None
    ):
        """Manage whisper tickets"""
        # Validate action choices
        if action not in ["create", "close", "delete"]:
            await ctx.respond(
                "❌ Invalid action! Use create, close, or delete.",
                ephemeral=True
            )
            return

        settings = await self._get_settings(ctx.guild.id)
        
        if not settings:
            await ctx.respond(
                "❌ Whisper system is not configured! Ask an admin to set it up.",
                ephemeral=True
            )
            return

        if action == "create":
            await self._handle_create(ctx, settings)
        elif action == "close":
            await self._handle_close(ctx, settings)
        elif action == "delete":
            await self._handle_delete(ctx, settings, user)

    async def _handle_create(self, ctx, settings):
        """Handle whisper creation"""
        # Check if user already has an active whisper
        active = await self.bot.db.get_active_whispers(ctx.guild.id)
        if any(w["user_id"] == ctx.author.id for w in active):
            await ctx.respond(
                "❌ You already have an active whisper ticket!",
                ephemeral=True
            )
            return

        # Generate whisper ID
        whisper_id = await self._generate_whisper_id(ctx.guild.id)
        
        # Create thread
        thread = await self._create_thread(settings["channel"], ctx.author, whisper_id)
        if not thread:
            await ctx.respond(
                "❌ Failed to create whisper ticket. Please try again later.",
                ephemeral=True
            )
            return
            
        # Store in database
        await self.bot.db.create_whisper(
            ctx.guild.id,
            whisper_id,
            ctx.author.id,
            thread.id
        )
        
        # Add staff role to thread if configured
        if settings["staff_role_id"]:
            try:
                staff_role = ctx.guild.get_role(settings["staff_role_id"])
                if staff_role:
                    await thread.add_user(staff_role)
            except discord.Forbidden:
                pass
        
        # Cache the whisper
        self._active_whispers[thread.id] = {
            "id": whisper_id,
            "user_id": ctx.author.id
        }
        
        await ctx.respond(
            f"✅ Created whisper ticket #{whisper_id}. Click here to view: {thread.mention}",
            ephemeral=True
        )

    async def _handle_close(self, ctx, settings):
        """Handle whisper closure"""
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond(
                "❌ This command can only be used in a whisper ticket thread!",
                ephemeral=True
            )
            return
            
        # Verify this is a whisper thread
        thread_data = self._active_whispers.get(ctx.channel.id)
        if not thread_data:
            await ctx.respond(
                "❌ This thread is not a whisper ticket!",
                ephemeral=True
            )
            return
            
        # Check permissions
        is_staff = (
            settings["staff_role_id"] in [r.id for r in ctx.author.roles] or
            ctx.author.guild_permissions.administrator
        )
        is_owner = ctx.author.id == thread_data["user_id"]
        
        if not (is_staff or is_owner):
            await ctx.respond(
                "❌ You don't have permission to close this ticket!",
                ephemeral=True
            )
            return
            
        # Close the thread
        await self.bot.db.close_whisper(ctx.guild.id, thread_data["id"])
        
        embed = discord.Embed(
            title="Whisper Ticket Closed",
            description=f"Closed by {ctx.author.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await ctx.channel.send(embed=embed)
        
        try:
            await ctx.channel.edit(archived=True, locked=True)
        except discord.Forbidden:
            pass
            
        # Remove from cache
        self._active_whispers.pop(ctx.channel.id, None)
        
        await ctx.respond("✅ Whisper ticket closed!", ephemeral=True)

    async def _handle_delete(self, ctx, settings, user):
        """Handle whisper deletion"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.respond(
                "❌ Only administrators can delete whisper tickets!",
                ephemeral=True
            )
            return
            
        if not user:
            await ctx.respond(
                "❌ Please specify a user whose ticket to delete!",
                ephemeral=True
            )
            return
            
        # Get user's whispers
        active = await self.bot.db.get_active_whispers(ctx.guild.id)
        user_whispers = [w for w in active if w["user_id"] == user.id]
        
        if not user_whispers:
            await ctx.respond(
                f"❌ No active whisper tickets found for {user.mention}!",
                ephemeral=True
            )
            return
            
        for whisper in user_whispers:
            # Delete from database
            await self.bot.db.delete_whisper(ctx.guild.id, whisper["whisper_id"])
            
            # Try to delete the thread
            thread = ctx.guild.get_thread(whisper["thread_id"])
            if thread:
                try:
                    await thread.delete()
                except discord.Forbidden:
                    pass
                    
            # Remove from cache
            self._active_whispers.pop(whisper["thread_id"], None)
            
        await ctx.respond(
            f"✅ Deleted all whisper tickets for {user.mention}!",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        """Handle thread deletion"""
        if thread.id in self._active_whispers:
            whisper_data = self._active_whispers.pop(thread.id)
            await self.bot.db.delete_whisper(
                thread.guild.id,
                whisper_data["id"]
            )

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        """Handle thread archival"""
        if (
            before.id in self._active_whispers and
            not before.archived and
            after.archived
        ):
            # Auto-close whisper when thread is archived
            whisper_data = self._active_whispers[before.id]
            await self.bot.db.close_whisper(
                before.guild.id,
                whisper_data["id"]
            )
            self._active_whispers.pop(before.id, None)

def setup(bot):
    bot.add_cog(Whisper(bot))
