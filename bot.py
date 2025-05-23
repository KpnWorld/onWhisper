import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from utils.db_manager import DBManager  # Your custom async DB manager

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in the environment variables.")
if not APPLICATION_ID:
    raise ValueError("APPLICATION_ID is not set in the environment variables.")

# Convert APPLICATION_ID to integer
APPLICATION_ID = int(APPLICATION_ID)

# Configure intents
intents = discord.Intents.all()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("WhisperBot")

# Global shutdown task variable
shutdown_task: Optional[asyncio.Task] = None

class WhisperBot(commands.Bot):
    """Base bot class with database integration."""
    
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, application_id=APPLICATION_ID)
        self.session = aiohttp.ClientSession()
        self.db: Optional[DBManager] = None

    async def setup_hook(self):
        """Called when the bot is starting up"""
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)

        # Initialize database
        self.db = DBManager("data/database.db", logger=log)
        await self.db.init()

        # Load all cogs
        await self.load_all_cogs()

        # Start the status task
        self.status_task.start()

    async def load_all_cogs(self):
        """Load all cogs from the cogs directory"""
        cogs_path = Path("./cogs")
        for cog_file in cogs_path.glob("*.py"):
            if cog_file.name.startswith("_"):
                continue
            cog_name = f"cogs.{cog_file.stem}"
            try:
                await self.load_extension(cog_name)
                log.info(f"Loaded cog {cog_name}")
            except Exception as e:
                log.error(f"Failed to load cog {cog_name}: {e}")

    async def on_ready(self):
        guild_count = len(self.guilds)
        cog_count = len(self.cogs)
        assert self.user is not None  # for static type checkers like Pylance
        log.info(f"Bot is ready. Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {guild_count} guild(s)")
        log.info(f"Loaded {cog_count} cog(s): {', '.join(self.cogs.keys())}")

        # Sync application commands
        try:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} global application command(s) with Discord")
        except Exception as e:
            log.error(f"Failed to sync application commands: {e}")

    @tasks.loop(minutes=10)
    async def status_task(self):
        await self.change_presence(activity=discord.Game(name="Keeping Whisper running!"))

    @status_task.before_loop
    async def before_status_task(self):
        await self.wait_until_ready()

    async def close(self):
        """Cleanup and close the bot."""
        log.info("Shutting down bot...")
        self.status_task.cancel()

        if self.db:
            await self.db.close()

        # Close aiohttp session if exists and open
        if hasattr(self, "session") and not self.session.closed:
            await self.session.close()

        # Wait for all pending tasks to complete (optional)
        pending = asyncio.all_tasks()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        await super().close()

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler for prefix commands."""
        if hasattr(ctx.command, 'on_error'):
            return  # Skip if the command has its own error handler

        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ Command not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing argument: `{error.param.name}`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Invalid argument provided.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("🚫 You do not have permission to use this command.")
        else:
            # Log unexpected errors
            import traceback
            traceback.print_exception(type(error), error, error.__traceback__)
            await ctx.send("⚠️ An unexpected error occurred.")

# Instantiate the bot
bot = WhisperBot()

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Global error handler for slash commands."""
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f} seconds.", ephemeral=True)
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 You do not have the required permissions to use this command.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandNotFound):
        await interaction.response.send_message("❌ Command not found.", ephemeral=True)
    else:
        # Log unexpected errors
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)
        await interaction.response.send_message("⚠️ An unexpected error occurred.", ephemeral=True)

def shutdown_handler(*_):
    global shutdown_task
    log.info("Received shutdown signal.")
    shutdown_task = asyncio.create_task(bot.close())

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: asyncio.create_task(bot.close()))

    try:
        loop.run_until_complete(bot.start(DISCORD_TOKEN)) # type: ignore
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received.")
    finally:
        log.info("Closing loop.")
        if not loop.is_closed():
            loop.run_until_complete(bot.close())
            tasks = asyncio.all_tasks(loop)
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()

if __name__ == "__main__":
    main()
