import discord
from discord.ext import commands
import asyncio
import sys
import traceback
from typing import Optional
import json
import os

def is_owner():
    """Check if user is bot owner"""
    async def predicate(ctx):
        return await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)

class Debug(commands.Cog):
    """Owner-only debug commands"""
    
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
                print("❌ Database not available for Debug cog")
                return
            self._ready.set()
            print("✅ Debug cog ready")
        except Exception as e:
            print(f"❌ Error setting up Debug cog: {e}")

    async def cog_before_invoke(self, ctx):
        """Wait for cog to be ready before processing commands"""
        await self._ready.wait()

    async def cog_check(self, ctx):
        """Only allow bot owner to use these commands"""
        return await self.bot.is_owner(ctx.author)

    @commands.hybrid_group(name="debug")
    @is_owner()
    async def debug(self, ctx):
        """Debug and maintenance commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @debug.command(name="sync")
    async def debug_sync(self, ctx):
        """Sync application commands"""
        try:
            await self.bot.tree.sync()
            await ctx.send("✅ Application commands synced!")
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @debug.command(name="reload")
    async def debug_reload(self, ctx, cog: str):
        """Reload a cog"""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Reloaded `{cog}`!")
        except Exception as e:
            await ctx.send(f"Error reloading `{cog}`: {e}", ephemeral=True)

    @debug.command(name="load")
    async def debug_load(self, ctx, cog: str):
        """Load a cog"""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Loaded `{cog}`!")
        except Exception as e:
            await ctx.send(f"Error loading `{cog}`: {e}", ephemeral=True)

    @debug.command(name="unload")
    async def debug_unload(self, ctx, cog: str):
        """Unload a cog"""
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Unloaded `{cog}`!")
        except Exception as e:
            await ctx.send(f"Error unloading `{cog}`: {e}", ephemeral=True)

    @debug.command(name="eval")
    async def debug_eval(self, ctx, *, code: str):
        """Evaluate Python code"""
        try:
            # Remove code blocks if present
            if code.startswith("```") and code.endswith("```"):
                code = code.strip("```")
                if code.startswith("py"):
                    code = code[2:]

            # Add return for expressions
            if not any(code.startswith(x) for x in ('def', 'class', 'async', 'await', 'import', 'from')):
                code = f"return {code}"

            # Create function
            env = {
                'bot': self.bot,
                'ctx': ctx,
                'channel': ctx.channel,
                'author': ctx.author,
                'guild': ctx.guild,
                'message': ctx.message,
                'discord': discord
            }

            func = f"async def _eval():\n" + "\n".join(f"    {line}" for line in code.split("\n"))
            
            # Execute
            exec(func, env)
            result = await env['_eval']()

            await ctx.send(f"```py\n{result}\n```")
        except Exception as e:
            await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

    @debug.command(name="cleanup")
    async def debug_cleanup(self, ctx, limit: Optional[int] = 100):
        """Clean up bot messages"""
        try:
            def is_bot(m):
                return m.author == ctx.me or m.content.startswith(ctx.prefix)

            deleted = await ctx.channel.purge(
                limit=limit,
                check=is_bot
            )
            
            msg = await ctx.send(f"Deleted {len(deleted)} messages")
            await asyncio.sleep(5)
            await msg.delete()

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @debug.command(name="sql")
    async def debug_sql(self, ctx, *, query: str):
        """Execute SQL query"""
        try:
            if not query.lower().startswith('select'):
                await ctx.send("Only SELECT queries are allowed!", ephemeral=True)
                return

            result = await self.db_manager.execute_query(query)
            
            if not result:
                await ctx.send("No results.")
                return

            # Format results
            if len(str(result)) > 1990:  # Discord message limit
                # Save to file if too long
                file = discord.File(
                    fp=json.dumps(result, indent=2).encode('utf-8'),
                    filename='query_result.json'
                )
                await ctx.send("Query result:", file=file)
            else:
                await ctx.send(f"```json\n{json.dumps(result, indent=2)}\n```")

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @debug.command(name="status")
    async def debug_status(self, ctx):
        """Show debug info"""
        try:
            embed = self.ui.info_embed(
                "Debug Status",
                "Current bot status and stats"
            )

            # System info
            pid = os.getpid()
            python_version = sys.version.split()[0]
            embed.add_field(
                name="System",
                value=f"PID: {pid}\n"
                      f"Python: {python_version}\n"
                      f"Discord.py: {discord.__version__}",
                inline=False
            )

            # Bot info
            embed.add_field(
                name="Bot",
                value=f"Servers: {len(self.bot.guilds)}\n"
                      f"Users: {sum(g.member_count for g in self.bot.guilds)}\n"
                      f"Latency: {round(self.bot.latency * 1000)}ms",
                inline=False
            )

            # Memory usage
            if hasattr(sys, 'getrefcount'):
                refs = sys.getrefcount(self.bot)
            else:
                refs = "N/A"
            
            embed.add_field(
                name="Memory",
                value=f"Bot refs: {refs}\n"
                      f"Guilds: {sys.getsizeof(self.bot.guilds)} bytes\n"
                      f"Users: {sys.getsizeof(self.bot.users)} bytes",
                inline=False
            )

            # Cog status
            cogs = [f"{name}: {'✅' if cog._ready.is_set() else '❌'}"
                   for name, cog in self.bot.cogs.items()]
            embed.add_field(
                name="Cogs",
                value="\n".join(cogs) or "No cogs loaded",
                inline=False
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

    @debug.command(name="leave")
    async def debug_leave(self, ctx, guild_id: int):
        """Leave a server by ID"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                await ctx.send("Guild not found!", ephemeral=True)
                return

            await guild.leave()
            await ctx.send(f"✅ Left guild: {guild.name}")
        except Exception as e:
            await ctx.send(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Debug(bot))
