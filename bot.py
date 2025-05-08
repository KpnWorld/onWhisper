import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import sys
import time
import signal
import logging

from utils.db_manager import DBManager
from utils.ui_manager import UIManager

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bot')

# List of activities for the bot to cycle through
ACTIVITIES = [
    discord.Game(name="with commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="commands"),
    discord.Game(name="with Python"),
    discord.Activity(type=discord.ActivityType.competing, name="tasks")
]

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Game(name="with commands")
        )
        
        # Core attributes
        self.db_manager = None  # Will be initialized in setup_hook
        self.ui_manager = UIManager()
        self.bg_tasks = []
        self._rate_limit_retries = 0
        self.start_time = None
        self._maintenance_mode = False
        self._ready = asyncio.Event()
        self._closing = asyncio.Event()  # New flag to track shutdown state
        self.activity_task = None  # Track the activity task

        # Version info
        try:
            with open('version.txt', 'r') as f:
                self.version = f.read().strip()
        except:
            self.version = "0.0.1"
            with open('version.txt', 'w') as f:
                f.write(self.version)

    async def _validate_startup(self) -> bool:
        """Validate critical components and permissions"""
        try:
            # Check intents
            if not all([self.intents.message_content, self.intents.members]):
                logger.error("Required intents are not enabled")
                return False

            # Check database connection
            if not await self.db_manager.check_connection():
                logger.error("Database connection failed")
                return False

            return True

        except Exception as e:
            logger.error(f"Startup validation failed: {e}")
            return False

    async def start(self, token: str) -> None:
        """Override start to add error handling"""
        try:
            self.start_time = datetime.utcnow()
            await super().start(token)
        except discord.LoginFailure:
            logger.error("Failed to login. Please check your token.")
            return
        except discord.PrivilegedIntentsRequired:
            logger.error("Privileged intents are required. Enable them in the Discord Developer Portal.")
            return
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return

    async def setup_hook(self):
        """This is called when the bot starts, sets up the database and loads cogs"""
        logger.info(f"\nStarting Bot v{self.version}")
        logger.info("Running startup validation...")
        
        # Initialize database manager
        try:
            self.db_manager = DBManager(self)
            if not await self.db_manager.initialize():
                logger.error("Failed to initialize database")
                await self.close()
                return
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            await self.close()
            return

        if not await self._validate_startup():
            logger.error("Startup validation failed")
            await self.close()
            return

        logger.info("✅ Startup validation passed\n")

        try:
            # Load cogs
            logger.info("\nLoading cogs...")
            cog_load_errors = []
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        logger.info(f"✅ Loaded {filename[:-3]}")
                    except Exception as e:
                        cog_load_errors.append((filename, str(e)))
                        logger.error(f"❌ Failed to load {filename}: {e}")

            if cog_load_errors:
                logger.warning("\n⚠️ Some cogs failed to load:")
                for cog, error in cog_load_errors:
                    logger.warning(f"  - {cog}: {error}")

            # Sync guild data
            logger.info("\nSyncing guild data...")
            try:
                sync_results = await self.db_manager.sync_guilds(self)
                logger.info(f"✅ Synced {sync_results['success']} guilds")
                if sync_results['failed'] > 0:
                    logger.warning(f"⚠️ Failed to sync {sync_results['failed']} guilds")
            except Exception as e:
                logger.error(f"❌ Failed to sync guilds: {e}")
                raise

            # Sync commands globally
            logger.info("\nSyncing commands globally...")
            try:
                commands = await self.tree.sync()
                logger.info(f"✅ Synced {len(commands)} commands globally")
            except discord.Forbidden:
                logger.error("❌ Failed to sync commands: Missing applications.commands scope")
                raise
            except Exception as e:
                logger.error(f"❌ Failed to sync commands: {e}")
                raise

            # Start background tasks
            logger.info("\nStarting background tasks...")
            self.bg_tasks.extend([
                self.loop.create_task(self._periodic_cleanup()),
                self.loop.create_task(self._periodic_maintenance())
            ])
            # Start activity loop
            self.activity_task = self.loop.create_task(self._change_activity())
            logger.info("✅ Background tasks started")

            # Set ready flag
            self._ready.set()

        except Exception as e:
            logger.error(f"❌ Critical setup error: {e}")
            await self.close()
            raise

    async def _periodic_cleanup(self):
        """Run periodic data cleanup"""
        while not self.is_closed():
            try:
                await asyncio.sleep(86400)  # Run daily
                if self._closing.is_set():
                    break
                await self.db_manager.cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _periodic_maintenance(self):
        """Run periodic maintenance tasks"""
        while not self.is_closed():
            try:
                await asyncio.sleep(3600)  # Run hourly
                if self._closing.is_set():
                    break
                # Re-sync any guilds that might have gotten out of sync
                await self.db_manager.sync_guilds(self)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic maintenance: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _change_activity(self):
        """Change bot activity periodically"""
        while not self.is_closed():
            try:
                await asyncio.sleep(600)  # Change every 10 minutes
                if self._closing.is_set():
                    break
                await self.change_presence(activity=random.choice(ACTIVITIES))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error changing activity: {e}")
                await asyncio.sleep(60)  # Wait a minute on error

    async def close(self):
        """Close bot and cleanup"""
        if self._closing.is_set():
            return  # Already closing
        
        self._closing.set()
        logger.info("Shutting down bot...")
        
        try:
            # Cancel activity task
            if self.activity_task and not self.activity_task.done():
                self.activity_task.cancel()
                try:
                    await self.activity_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel all background tasks
            logger.info("Cancelling background tasks...")
            for task in self.bg_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            try:
                await asyncio.wait(self.bg_tasks, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Some tasks didn't complete in time")
            
            # Close database connection
            logger.info("Closing database connection...")
            if self.db_manager:
                await self.db_manager.close()
            
            # Close Discord connection
            logger.info("Closing Discord connection...")
            await super().close()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            logger.info("Shutdown complete")

def run_bot():
    """Run the bot with proper error handling and reconnection"""
    bot = None
    max_retries = 5
    retry_count = 0
    retry_delay = 30  # Initial delay in seconds

    def signal_handler(signum, frame):
        logger.info(f"\nReceived signal {signum}")
        if bot and not bot.is_closed():
            logger.info("Initiating graceful shutdown...")
            asyncio.run(bot.close())
            sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        try:
            if retry_count >= max_retries:
                logger.error(f"Failed to start after {max_retries} attempts. Please check logs and configuration.")
                return

            if bot is None:
                bot = Bot()

            logger.info("\n=== Starting Bot ===")
            if retry_count > 0:
                logger.info(f"Retry attempt {retry_count}/{max_retries}")

            # Run the bot
            asyncio.run(bot.start(TOKEN))

        except discord.LoginFailure:
            logger.error("Login failed - Invalid token. Please check your .env file.")
            return  # Don't retry on authentication failures
        except discord.PrivilegedIntentsRequired:
            logger.error("Required privileged intents are not enabled. Please enable them in the Discord Developer Portal.")
            return  # Don't retry on intent issues
        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
            if bot and not bot.is_closed():
                asyncio.run(bot.close())
            return
        except Exception as e:
            retry_count += 1
            logger.error(f"\nError: {str(e)}")
            
            # Cleanup
            try:
                if bot and not bot.is_closed():
                    logger.info("Cleaning up...")
                    asyncio.run(bot.close())
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
            
            # Reset bot instance
            bot = None
            
            if retry_count < max_retries:
                wait_time = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.info("Maximum retry attempts reached. Shutting down.")
                return

if __name__ == "__main__":
    run_bot()
