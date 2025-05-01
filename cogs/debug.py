import discord
from discord.ext import commands
from typing import Optional

class Debug(commands.Cog):
    """Developer debug commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.ui = bot.ui_manager

    async def cog_check(self, ctx):
        """Only allow bot owner to use debug commands"""
        return await self.bot.is_owner(ctx.author)

    @commands.hybrid_group(name="debug")
    async def debug(self, ctx):
        """Debug commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @debug.command(name="sync")
    async def debug_sync(self, ctx):
        """Sync slash commands"""
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} command(s)!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error syncing commands: {e}", ephemeral=True)

    @debug.command(name="reload")
    async def debug_reload(self, ctx, cog: str):
        """Reload a cog"""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Reloaded cog: {cog}", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error reloading cog: {e}", ephemeral=True)

    @debug.command(name="cleanup")
    async def debug_cleanup(self, ctx, limit: Optional[int] = 100):
        """Clean bot messages"""
        try:
            def is_bot_msg(m):
                return m.author == self.bot.user
                
            deleted = await ctx.channel.purge(
                limit=limit,
                check=is_bot_msg
            )
            await ctx.send(
                f"Deleted {len(deleted)} bot messages.",
                ephemeral=True,
                delete_after=5
            )
        except Exception as e:
            await ctx.send(f"Error cleaning messages: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Debug(bot))
