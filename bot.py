import asyncio
import logging
import os
import signal
import aiohttp
from pathlib import Path
from typing import Optional, Union

import discord as dc
from discord.ext import tasks
from dotenv import load_dotenv

from utils.db_manager import DBManager  # Your custom async DB manager

# Load environment variables
load_dotenv()

# Retrieve token and application ID from environment variables
discord_token_env: Union[str, None] = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")

if discord_token_env is None:
    raise ValueError("DISCORD_TOKEN is not set in the environment variables.")
DISCORD_TOKEN: str = discord_token_env  # Type assertion after None check
if APPLICATION_ID is None:
    raise ValueError("APPLICATION_ID is not set in the environment variables.")

# Convert APPLICATION_ID to integer
APPLICATION_ID = int(APPLICATION_ID)

# Configure intents
intents = dc.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("WhisperBot")

# Global shutdown task variable
shutdown_task: Optional[asyncio.Task] = None


class WhisperBot(dc.Bot):
    def __init__(self):
        super().__init__(intents=intents, application_id=APPLICATION_ID)
        self.db: Optional[DBManager] = None
        self.session = aiohttp.ClientSession()

    async def setup_hook(self):
        """Called when the bot is starting up"""
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)

        # Initialize database
        self.db = DBManager("data/database.db", logger=log)
        await self.db.init()

        # Load all cogs and sync commands
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
                self.load_extension(cog_name)
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

        # Correct method to sync application commands
        try:
            synced = await self.sync()  # type: ignore
            log.info(f"Synced {len(synced)} global application command(s) with Discord")
        except Exception as e:
            log.error(f"Failed to sync application commands: {e}")

    @tasks.loop(minutes=10)
    async def status_task(self):
        await self.change_presence(activity=dc.Game(name="Keeping Whisper running!"))

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


# Instantiate the bot
bot = WhisperBot()


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
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
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

