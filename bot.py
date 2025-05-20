import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional, Union

import discord
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
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("WhisperBot")

class WhisperBot(discord.Bot):
    def __init__(self):
        super().__init__(intents=intents, application_id=APPLICATION_ID)
        self.db: Optional[DBManager] = None
        self.status_task.start()  # Start the status task within the constructor

    async def setup_hook(self):
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)

        self.db = DBManager("data/database.db", logger=log)
        await self.db.init()

        await self.load_all_cogs()

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
        await self.wait_until_ready()

    async def close(self):
        log.info("Shutting down bot...")
        self.status_task.cancel()
        if self.db:
            await self.db.close()
        await super().close()


# Instantiate the bot
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
