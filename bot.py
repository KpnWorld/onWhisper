import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.db_manager import DBManager  # Your custom async DB manager

load_dotenv()

raw_token = os.getenv("DISCORD_TOKEN")
raw_app_id = os.getenv("APPLICATION_ID")

if raw_token is None:
    raise ValueError("DISCORD_TOKEN is not set in the environment variables.")
if raw_app_id is None:
    raise ValueError("APPLICATION_ID is not set in the environment variables.")

# Now both are safe to cast
DISCORD_TOKEN: str = raw_token
APPLICATION_ID: int = int(raw_app_id)

# Set up intents for py-cord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True


log = logging.getLogger("onWhisper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class WhisperBot(discord.Bot):
    def __init__(self):
        super().__init__(
            intents=intents,
            application_id=APPLICATION_ID,
        )
        self.db: Optional[DBManager] = None    
          
    async def setup_hook(self):
        # Create data directory if it doesn't exist
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        
        self.db = DBManager("data/database.db", logger=log)
        await self.db.init()

        # Load cogs first
        await self.load_all_cogs()
        
        # Start status task after cogs are loaded
        self.status_task.start()
        
    async def load_all_cogs(self):
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

    @tasks.loop(minutes=10)
    async def status_task(self):
        await self.change_presence(activity=discord.Game(name="Keeping Whisper running!"))
    
    @status_task.before_loop
    async def before_status_task(self):
        """Wait until the bot is ready before starting the task"""
        await self.wait_until_ready()

    async def close(self):
        log.info("Shutting down bot...")
        self.status_task.cancel()
        if self.db:
            await self.db.close()
        await super().close()


bot = WhisperBot()


def shutdown_handler(*_):
    log.info("Received shutdown signal.")
    asyncio.create_task(bot.close())


def main():
    loop = asyncio.get_event_loop()
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
        loop.run_until_complete(bot.close())
        loop.close()


if __name__ == "__main__":
    main()

# This is a simple Discord bot that uses discord.py and asyncio.
# It loads cogs dynamically from the "cogs" directory, manages a database connection,
# and provides a framework for building interactive Discord applications.
# The bot's status is updated every 10 minutes, and it handles graceful shutdowns.
# The bot is designed to be run in an environment where the DISCORD_TOKEN and APPLICATION_ID
# environment variables are set.
