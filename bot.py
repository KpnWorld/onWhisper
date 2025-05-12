import discord
from discord.ext import tasks, commands
import os
import random
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import signal
from typing import Optional, Dict, Any, List
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

# Configure logging
logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.WARNING)  # Raise to WARNING to hide detailed HTTP logs
logging.getLogger('discord.gateway').setLevel(logging.WARNING)  # Raise to WARNING to hide detailed gateway logs

# Clear any existing handlers
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

# Custom logging format
class CustomFormatter(logging.Formatter):
    FORMATS = {
        logging.INFO: '[INFO] %(message)s',
        logging.WARNING: '[WARNING] %(message)s',
        logging.ERROR: '[ERROR] %(message)s',
        logging.CRITICAL: '[CRITICAL] %(message)s',
        logging.DEBUG: '[DEBUG] %(message)s'
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Set up handler with custom formatter
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
root.addHandler(handler)
root.setLevel(logging.INFO)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
APPID = os.getenv('APPLICATION_ID')

ACTIVITIES = [
    discord.Game("with commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="commands"),
    discord.Game("with Python"),
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
            help_command=None,
            application_id=APPID
        )        
        self.db_manager: Optional[DBManager] = None
        self.ui_manager: UIManager = UIManager()
        self.bg_tasks: List[asyncio.Task] = []
        self.start_time: Optional[datetime] = None
        self._shutdown_timeout: int = 10
        self._closing: asyncio.Event = asyncio.Event()
        self._ready: asyncio.Event = asyncio.Event()

        try:
            with open("version.txt", "r") as f:
                self.version = f.read().strip()
        except (FileNotFoundError, IOError) as e:
            logging.warning(f"Version file not found or unreadable: {e}")
            self.version = "0.0.1"
            try:
                with open("version.txt", "w") as f:
                    f.write(self.version)
            except IOError as e:
                logging.error(f"Failed to write version file: {e}")

    async def setup_hook(self):
        logging.info(f"Starting Bot v{self.version}")
        self.setup_signal_handlers()

        self.db_manager = DBManager(self)
        
        if not await self.db_manager.initialize():
            logging.error("Failed to initialize database.")
            return await self.close()

        if not await self._validate_startup():
            logging.error("Startup validation failed.")
            return await self.close()

        # Load cogs using Path for better cross-platform compatibility
        cogs_path = Path(__file__).parent / "cogs"
        logging.info(f"Looking for cogs in: {cogs_path}")

        if not cogs_path.exists():
            logging.error(f"❌ Cogs directory not found at {cogs_path}")
            return await self.close()

        loaded_cogs = 0
        failed_cogs = 0
        
        # Sync commands before loading cogs
        try:
            logging.info("Initial command sync...")
            await self.tree.sync()
        except Exception as e:
            logging.warning(f"Initial sync warning (can be ignored): {e}")
        
        for file in cogs_path.glob("*.py"):
            if file.name.startswith("_"):
                continue

            logging.debug(f"Attempting to load cog: {file.name}")
            try:
                module_path = f"cogs.{file.stem}"
                logging.debug(f"Loading extension: {module_path}")
                await self.load_extension(module_path)
                
                if hasattr(self, 'cogs') and file.stem in self.cogs:
                    cog = self.get_cog(file.stem)
                    if cog:
                        app_commands = [cmd.name for cmd in cog.walk_app_commands()]
                        text_commands = [cmd.name for cmd in cog.get_commands()]
                        logging.info(f"Commands in {file.name}:")
                        logging.info(f"- Slash commands: {app_commands}")
                        logging.info(f"- Text commands: {text_commands}")
                
                loaded_cogs += 1
                logging.info(f"✅ Loaded cog {file.name}")
            except Exception as e:
                logging.error(f"❌ Failed to load cog {file.name}: {str(e)}", exc_info=True)
                failed_cogs += 1

        logging.info(f"📦 Loaded {loaded_cogs} cogs, {failed_cogs} failed")

        # Final command sync after all cogs are loaded
        try:
            logging.info("Final command sync...")
            
            # Debug: List all commands before sync
            all_commands = self.tree.get_commands()
            logging.info(f"Commands before sync: {[cmd.name for cmd in all_commands]}")
            
            # Sync commands
            synced = await self.tree.sync()
            
            # Log results
            logging.info(f"✅ Synced {len(synced)} commands globally")
            logging.info(f"Synced commands: {[cmd.name for cmd in synced]}")
            
        except discord.Forbidden as e:
            logging.error(f"❌ Missing 'applications.commands' scope: {e}")
            return await self.close()
        except Exception as e:
            logging.error(f"❌ Command sync failed: {e}", exc_info=True)
            return await self.close()

        # Start background tasks
        try:
            self.bg_tasks.extend([
                self.periodic_cleanup.start(),
                self.periodic_maintenance.start(),
                self.change_activity.start()
            ])
            logging.info("✅ Started background tasks")
        except Exception as e:
            logging.error(f"❌ Failed to start background tasks: {e}")
            return await self.close()

        self._ready.set()
        logging.info("✅ Bot setup complete")

    @property
    def uptime(self):
        if not self.start_time:
            return "Bot not started"
        delta = datetime.now(timezone.utc) - self.start_time
        return f"{delta.days}d {delta.seconds//3600}h {(delta.seconds//60)%60}m {delta.seconds%60}s"

    async def on_ready(self):
        logging.info(f"Bot {self.user.name} is ready!")
        # Replace datetime.utcnow() with timezone-aware alternative
        self.start_time = datetime.now(timezone.utc)

    async def _validate_startup(self):
        try:            
            if not await self.db_manager.check_connection():
                return False
            return True
        except Exception as e:
            logging.error(f"Startup validation failed: {e}")
            return False

    @tasks.loop(hours=24)
    async def periodic_cleanup(self):
        try:
            # Add your cleanup logic here
            pass
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
        except Exception as e:
            logging.error(f"Cleanup error: {e}", exc_info=True)
            await asyncio.sleep(300)  
            # Back off on error

    @tasks.loop(hours=1)
    async def periodic_maintenance(self):
        try:
            await self.db_manager.sync_guilds(self)
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
        except Exception as e:
            logging.error(f"Maintenance error: {e}", exc_info=True)
            await asyncio.sleep(300)  
            # Back off on error 
               
    @tasks.loop(minutes=10)
    async def change_activity(self):
        if not self.is_ready():
            return
            
        try:
            await self.change_presence(activity=random.choice(ACTIVITIES))
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
        except discord.HTTPException as e:
            logging.error(f"Activity update failed: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Activity error: {e}", exc_info=True)

    @periodic_cleanup.before_loop
    @periodic_maintenance.before_loop
    @change_activity.before_loop
    async def before_tasks(self):
        await self.wait_until_ready()

    def setup_signal_handlers(self):
        """Set up graceful shutdown handlers for SIGINT and SIGTERM"""
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))
            logging.info("✅ Set up signal handlers")
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            logging.warning("Signal handlers not supported on this platform")
            
    async def _handle_signal(self, sig: signal.Signals):
        """Handle incoming signals gracefully"""
        signame = sig.name
        logging.info(f"Received signal {signame}, initiating shutdown...")
        await self.close()

    async def close(self):
        if self._closing.is_set():
            return
        self._closing.set()
        logging.info("Shutting down...")

        # Cancel all background tasks
        if self.bg_tasks:
            for task in self.bg_tasks:
                if not task.done():
                    task.cancel()
                
            try:
                # Wait for tasks to complete with timeout
                await asyncio.wait(self.bg_tasks, timeout=self._shutdown_timeout)
            except asyncio.TimeoutError:
                logging.warning("Some tasks did not complete within shutdown timeout")
            except ValueError:
                # Tasks list became empty
                pass

        # Cancel all background tasks
        self.periodic_cleanup.cancel()
        self.periodic_maintenance.cancel()
        self.change_activity.cancel()

        # Close database connection
        if self.db_manager:
            try:
                await asyncio.wait_for(self.db_manager.close(), timeout=5)
            except asyncio.TimeoutError:
                logging.error("Database connection close timed out")
            except Exception as e:
                logging.error(f"DB close error: {e}")

        # Close any remaining HTTP sessions
        try:
            if hasattr(self, 'http') and hasattr(self.http, '_session'):
                await asyncio.wait_for(self.http._session.close(), timeout=5)                           
        except asyncio.TimeoutError:
            logging.error("HTTP session close timed out")
        except Exception as e:
            logging.error(f"HTTP session close error: {e}")

        # Close discord connection
        try:
            await asyncio.wait_for(super().close(), timeout=5)
        except asyncio.TimeoutError:
            logging.error("Timeout while closing Discord connection")
        except Exception as e:
            logging.error(f"Error during Discord shutdown: {e}")

        logging.info("Bot shutdown complete.")

    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=self.ui_manager.error_embed(
                    "Missing Permissions",
                    "You don't have the required permissions to use this command."
                )
            )
            return
            
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                embed=self.ui_manager.error_embed(
                    "Bot Missing Permissions",
                    "I don't have the required permissions to execute this command."
                )
            )
            return

        if isinstance(error, commands.NotOwner):
            await ctx.send(
                embed=self.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                )
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                embed=self.ui_manager.error_embed(
                    "Invalid Input",
                    str(error)
                )
            )
            return        
        # Log unexpected errors
        logging.error(f"Command error in {ctx.command}: {str(error)}")
        await ctx.send(
            embed=self.ui_manager.error_embed(
                "Error",
                "An unexpected error occurred. This has been logged."            
                )
        )

    async def on_application_command_error(self, interaction: discord.Interaction, error: commands.errors.CommandError):
        if isinstance(error, commands.errors.CommandOnCooldown):
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Cooldown",
                        f"Please wait {error.retry_after:.1f}s before using this command again."
                    ),
                    ephemeral=True
                )
                return 
               
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "Missing Permissions",
                    "You don't have the required permissions to use this command."
                ),
                ephemeral=True
            )
            return

        if isinstance(error, commands.BotMissingPermissions):
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "Bot Missing Permissions",
                    "I don't have the required permissions to execute this command."
                ),
                ephemeral=True
            )
            return
        
        if isinstance(error, commands.NotOwner):
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "Unauthorized",
                    "This command is only available to the bot owner."
                ),
                ephemeral=True
            )
            return
            
        # Log unexpected errors
        logging.error(f"Slash command error in {interaction.command}: {str(error)}")
        
        try:
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "Error",
                    "An unexpected error occurred. This has been logged."
                ),
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Failed to send error message: {e}")

def run_bot():
    bot = Bot()
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Bot runtime error: {e}", exc_info=True)
        return 1
    return 0

if __name__ == "__main__":
    exit_code = run_bot()
    exit(exit_code)
