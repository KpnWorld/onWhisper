# bot.py
"""
onWhisper main startup file.

Follows Persistent Developer Instructions for onWhisperBot:
- Loads environment variables from .env
- Creates a discord.py commands.Bot instance with required intents
- Instantiates DBManager (self.db) and initializes tables
- Auto-loads all cogs from ./cogs
- Structured logging with timestamps
- Graceful shutdown on SIGINT/SIGTERM
- Basic error handling for startup and cog loading
- Prints bot info on ready
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- Logging Setup ------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("onWhisper")

# --- DB Manager ---------------------------------------------------------------
from utils.db_manager import DBManager  # Must follow Persistent Developer Instructions


# --- Bot Class ----------------------------------------------------------------

class OnWhisperBot(commands.Bot):
    """Custom Bot that wires up database and auto-loads cogs."""

    def __init__(self, *, application_id: int) -> None:
        # Intents per developer instructions
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            application_id=application_id,
        )

        # DB Manager will be initialized in setup_hook
        self.db: Optional[DBManager] = None

        # Paths
        self.base_dir: Path = Path(__file__).parent.resolve()
        self.cogs_dir: Path = self.base_dir / "cogs"
        self.data_dir: Path = self.base_dir / "data"
        self.db_path: Path = self.data_dir / "onwhisper.db"

    async def setup_hook(self) -> None:
        """Initialize database and load cogs before bot connects."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.db = DBManager(str(self.db_path))
            await self.db.init()  # Changed from init_tables() to init()
            logger.info("Database initialized at %s", self.db_path)
        except Exception:
            logger.exception("Failed to initialize database")
            raise

        await self._load_all_cogs()

        # Sync application commands globally
        try:
            synced = await self.tree.sync()
            logger.info("Slash commands synced: %d", len(synced))
        except Exception:
            logger.exception("Failed to sync slash commands")

    async def _load_all_cogs(self) -> None:
        """Dynamically load all cogs in ./cogs."""
        if not self.cogs_dir.exists():
            logger.warning("Cogs directory not found at %s", self.cogs_dir)
            return

        loaded, failed = 0, 0
        for filename in os.listdir(self.cogs_dir):
            if filename.endswith(".py"):
                ext = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(ext)
                    loaded += 1
                    logger.info("Loaded cog: %s", ext)
                except Exception as e:
                    failed += 1
                    logger.exception("Failed to load cog %s: %s", ext, e)

        logger.info("Cog load summary: loaded=%d failed=%d", loaded, failed)

    async def close(self) -> None:
        """Close DB connection before shutting down."""
        try:
            if self.db:
                await self.db.close()
                logger.info("Database connection closed")
        except Exception:
            logger.exception("Error while closing database")
        finally:
            await super().close()

    async def on_ready(self) -> None:
        """Print bot info when ready."""
        try:
            if self.user:
                logger.info(
                    "Bot is ready! Name: %s | ID: %s | Guilds: %d",
                    self.user.name,
                    self.user.id,
                    len(self.guilds),
                )
                print(
                    f"[READY] {self.user.name} ({self.user.id}) connected to {len(self.guilds)} guild(s)."
                )
            else:
                logger.warning("Bot ready but self.user is None")
        except Exception:
            logger.exception("Error in on_ready event")


# --- Signal Handling ----------------------------------------------------------

def install_signal_handlers(loop: asyncio.AbstractEventLoop, bot: OnWhisperBot) -> None:
    """Install signal handlers for clean shutdown."""
    def _handle_signal(sig: signal.Signals) -> None:
        logger.warning("Received signal %s; shutting down...", sig.name)
        loop.create_task(bot.close())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))
        except NotImplementedError:
            logger.debug("Signal handler for %s not supported", sig.name)


# --- Entry Point --------------------------------------------------------------

def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    app_id_raw = os.getenv("APPLICATION_ID", "").strip()
    if not app_id_raw.isdigit():
        logger.error("Missing or invalid APPLICATION_ID in .env")
        sys.exit(1)
    application_id = int(app_id_raw)

    if not token:
        logger.error("Missing DISCORD_TOKEN in .env")
        sys.exit(1)

    bot = OnWhisperBot(application_id=application_id)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    install_signal_handlers(loop, bot)

    try:
        logger.info("Starting onWhisper bot...")
        bot.run(token, log_handler=None)
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt received; shutting down...")
    except Exception:
        logger.exception("Unhandled exception in bot.run()")
    finally:
        if not loop.is_closed():
            loop.close()
        logger.info("onWhisper bot shut down.")


if __name__ == "__main__":
    main()
