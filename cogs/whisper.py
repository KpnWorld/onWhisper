import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta
import asyncio

class Whisper(commands.Cog):
    """Private messaging system for support"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager
        self._ready = asyncio.Event()
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        """Ensure cog is properly initialized"""
        await self.bot.wait_until_ready()
        try:
            if not await self.db.ensure_connection():
                print("❌ Database not available for Whisper cog")
                return
            self._ready.set()
            print("✅ Whisper cog ready")
        except Exception as e:
            print(f"❌ Error setting up Whisper cog: {e}")

    async def check_thread_timeout(self, guild_id: int, thread_id: str, user_id: int):
        """Check and auto-close inactive threads"""
        try:
            while True:
                # Get latest config and whisper data
                config = await self.db.get_section(guild_id, 'whisper_config')
                timeout = config.get('auto_close_minutes', 1440)  # Default 24h
                
                # Sleep until potential timeout
                await asyncio.sleep(timeout * 60)
                
                # Get thread and check if it should be closed
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    return
                    
                thread = guild.get_thread(int(thread_id))
                if not thread or thread.archived:
                    return
                    
                last_message = await thread.history(limit=1).next()
                if not last_message:
                    return
                    
                # Check if inactive for timeout duration
                now = datetime.utcnow()
                inactive_time = (now - last_message.created_at).total_seconds() / 60
                
                if inactive_time >= timeout:
                    await self.db.close_whisper(guild_id, thread_id)
                    await thread.edit(archived=True, locked=True)
                    await thread.send(
                        embed=self.ui.warning_embed(
                            "Thread Auto-Closed",
                            f"This thread has been automatically closed due to {timeout} minutes of inactivity."
                        )
                    )
                    return
                    
        except Exception as e:
            print(f"Error in thread timeout check: {e}")

    @commands.hybrid_group(name="whisper")
    async def whisper(self, ctx):
        """Whisper system commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @whisper.command(name="send")
    async def whisper_send(self, ctx, *, message: str):
        """Start a private whisper thread to staff"""
        try:
            config = await self.db.get_section(ctx.guild.id, 'whisper_config')
            
            if not config.get('enabled', True):
                await ctx.send("The whisper system is currently disabled.", ephemeral=True)
                return

            staff_role_id = config.get('staff_role')
            if not staff_role_id:
                await ctx.send("No staff role has been configured for whispers.", ephemeral=True)
                return

            # Create thread in staff channel
            thread = await ctx.channel.create_thread(
                name=f"Whisper from {ctx.author.name}",
                type=discord.ChannelType.private_thread
            )

            # Create whisper in database using new method
            success = await self.db.create_whisper_thread(
                ctx.guild.id,
                ctx.author.id,
                thread.id,
                message
            )

            if not success:
                await thread.delete()
                await ctx.send("Error creating whisper thread.", ephemeral=True)
                return

            # Add author and staff role
            await thread.add_user(ctx.author)
            staff_role = ctx.guild.get_role(staff_role_id)
            if staff_role:
                for member in staff_role.members:
                    try:
                        await thread.add_user(member)
                    except:
                        pass

            # Send initial message
            embed = self.ui.info_embed(
                "New Whisper",
                f"**From:** {ctx.author.mention}\n\n{message}"
            )
            await thread.send(embed=embed)
            
            # Start timeout checking task
            self.bot.loop.create_task(
                self.check_thread_timeout(
                    ctx.guild.id,
                    str(thread.id),
                    ctx.author.id
                )
            )
            
            await ctx.send("Whisper thread created!", ephemeral=True)

        except Exception as e:
            await ctx.send(f"Error creating whisper: {e}", ephemeral=True)

    @whisper.command(name="close")
    async def whisper_close(self, ctx):
        """Close your whisper thread"""
        try:
            if not isinstance(ctx.channel, discord.Thread):
                await ctx.send("This command can only be used in whisper threads.", ephemeral=True)
                return

            whispers = await self.db.get_whispers(ctx.guild.id)
            whisper = next((w for w in whispers if w['thread_id'] == str(ctx.channel.id)), None)

            if not whisper:
                await ctx.send("This is not a whisper thread.", ephemeral=True)
                return

            if str(ctx.author.id) != whisper['user_id']:
                config = await self.db.get_section(ctx.guild.id, 'whisper_config')
                staff_role_id = config.get('staff_role')
                if not staff_role_id or staff_role_id not in [r.id for r in ctx.author.roles]:
                    await ctx.send("You don't have permission to close this whisper.", ephemeral=True)
                    return

            await self.db.close_whisper(ctx.guild.id, str(ctx.channel.id))
            await ctx.channel.edit(archived=True, locked=True)
            await ctx.send("Whisper thread closed!")

        except Exception as e:
            await ctx.send(f"Error closing whisper: {e}", ephemeral=True)

    @commands.hybrid_group(name="config")
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """Server configuration commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @config.group(name="whisper")
    async def config_whisper(self, ctx):
        """Whisper system configuration"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @config_whisper.command(name="toggle")
    async def whisper_toggle(self, ctx):
        """Toggle the whisper system on/off"""
        try:
            config = await self.db.get_section(ctx.guild.id, 'whisper_config')
            enabled = not config.get('enabled', True)
            
            await self.db.update_guild_data(
                ctx.guild.id,
                'whisper_config',
                {**config, 'enabled': enabled}
            )

            await ctx.send(
                f"Whisper system {'enabled' if enabled else 'disabled'}!",
                ephemeral=True
            )

        except Exception as e:
            await ctx.send(f"Error updating configuration: {e}", ephemeral=True)

    @config_whisper.command(name="staff")
    async def whisper_staff(self, ctx, role: discord.Role):
        """Set the staff role for whispers"""
        try:
            config = await self.db.get_section(ctx.guild.id, 'whisper_config')
            await self.db.update_guild_data(
                ctx.guild.id,
                'whisper_config',
                {**config, 'staff_role': role.id}
            )
            
            await ctx.send(
                f"Staff role for whispers set to {role.mention}!",
                ephemeral=True
            )

        except Exception as e:
            await ctx.send(f"Error updating configuration: {e}", ephemeral=True)

    @config_whisper.command(name="timeout")
    async def whisper_timeout(self, ctx, minutes: int):
        """Set the auto-close timeout for whispers"""
        try:
            if minutes < 1:
                await ctx.send("Timeout must be at least 1 minute.", ephemeral=True)
                return

            config = await self.db.get_section(ctx.guild.id, 'whisper_config')
            await self.db.update_guild_data(
                ctx.guild.id,
                'whisper_config',
                {**config, 'auto_close_minutes': minutes}
            )
            
            await ctx.send(
                f"Whisper threads will auto-close after {minutes} minutes of inactivity!",
                ephemeral=True
            )

        except Exception as e:
            await ctx.send(f"Error updating configuration: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Whisper(bot))
