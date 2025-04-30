import discord
from discord.ext import commands
import asyncio
from typing import Optional

class Create(commands.Cog):
    """Panel and message generation commands"""
    
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
                print("❌ Database not available for Create cog")
                return
            self._ready.set()
            print("✅ Create cog ready")
        except Exception as e:
            print(f"❌ Error setting up Create cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    @commands.hybrid_group(name="create")
    @commands.has_permissions(administrator=True)
    async def create(self, ctx):
        """Generate panels, templates, and setup messages"""
        if ctx.invoked_subcommand is None:
            embed = self.ui.admin_embed(
                "Create Commands",
                "Available commands:\n"
                "• /create ticket-panel - Generate a support ticket panel\n"
                "• /create reaction-role - Create a reaction role message\n"
                "• /create log-channel - Auto-setup a log channel\n"
                "• /create welcome-message - Preview/set a welcome message\n"
                "• /create level-message - Preview/set a level-up message"
            )
            await ctx.send(embed=embed)

    @create.command(name="ticket-panel")
    async def create_ticket_panel(self, ctx, channel: discord.TextChannel, *, message: str):
        """Generate a support ticket panel"""
        try:
            embed = self.ui.info_embed(
                "Support Tickets",
                message or "Click the button below to create a support ticket"
            )
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(
                label="Create Ticket",
                custom_id="create_ticket",
                style=discord.ButtonStyle.primary,
                emoji="🎫"
            ))
            await channel.send(embed=embed, view=view)
            await ctx.send("✅ Ticket panel created!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @create.command(name="reaction-role")
    async def create_reaction_role(self, ctx, channel: discord.TextChannel, emoji: str, role: discord.Role, *, message: str):
        """Create a reaction role message"""
        try:
            embed = self.ui.info_embed(
                "Role Selection",
                f"{message}\n\nReact with {emoji} to get the {role.mention} role"
            )
            msg = await channel.send(embed=embed)
            await msg.add_reaction(emoji)
            
            # Store reaction role binding
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {emoji: role.id},
                ['reaction_roles', str(msg.id)]
            )
            await ctx.send("✅ Reaction role message created!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @create.command(name="log-channel")
    async def create_log_channel(self, ctx, log_type: str, channel: discord.TextChannel):
        """Auto-setup a log channel"""
        valid_types = ['mod', 'member', 'message', 'server']
        try:
            if log_type.lower() not in valid_types:
                await ctx.send(f"Invalid log type. Must be one of: {', '.join(valid_types)}", ephemeral=True)
                return

            # Update logging config
            config = await self.db_manager.get_data('logging_config', str(ctx.guild.id)) or {}
            config[f'{log_type.lower()}_channel'] = channel.id
            config[f'{log_type.lower()}_logs'] = True
            await self.db_manager.set_data('logging_config', str(ctx.guild.id), config)

            embed = self.ui.admin_embed(
                "Log Channel Setup",
                f"Successfully set up {log_type} logs in {channel.mention}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @create.command(name="welcome-message")
    async def create_welcome_message(self, ctx, channel: discord.TextChannel, *, message: str):
        """Preview/set a welcome message"""
        try:
            # Save welcome message config
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {
                    'channel_id': channel.id,
                    'message': message,
                    'enabled': True
                },
                ['welcome']
            )
            
            # Show preview
            preview = message.replace("{user}", ctx.author.mention)
            preview = preview.replace("{server}", ctx.guild.name)
            
            embed = self.ui.info_embed(
                "Welcome Message Preview",
                preview
            )
            await ctx.send(f"Welcome message will be sent to {channel.mention}:", embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @create.command(name="level-message")
    @commands.has_permissions(administrator=True)
    async def create_level_message(self, ctx, channel: discord.TextChannel, duration: Optional[int] = 0, *, message: str):
        """Preview/set a level-up message
        
        Parameters
        ----------
        channel : The channel to show this preview in (level-up messages will show in the channel where user levels up)
        duration : How long the message should stay (in seconds, 0 for permanent)
        message : The message to show. Use {user} for the user mention and {level} for the level number
        """
        try:
            # Validate duration
            if duration < 0:
                await ctx.send("Duration must be 0 or greater (0 means permanent)", ephemeral=True)
                return

            # Save level-up message config
            await self.db_manager.update_guild_data(
                ctx.guild.id,
                {
                    'message': message,
                    'duration': duration,
                    'enabled': True
                },
                ['level_up']
            )
            
            # Show preview
            preview = message.replace("{user}", ctx.author.mention)
            preview = preview.replace("{level}", "5")
            
            embed = self.ui.info_embed(
                "Level-Up Message Preview",
                f"{preview}\n\n" + (
                    f"Message will be deleted after {duration} seconds"
                    if duration > 0 else
                    "Message will stay permanently"
                )
            )
            preview_msg = await ctx.send(embed=embed)
            
            # Delete preview after duration if set
            if duration > 0:
                await preview_msg.delete(delay=duration)
                
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Create(bot))
