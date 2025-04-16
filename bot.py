import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import random
import asyncio
import sys
import logging
import logging.handlers
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
import time
from datetime import datetime, timedelta
import sqlite3
from utils.db_manager import DatabaseManager
from utils.ui_manager import UIManager

# Initial extensions to load
INITIAL_EXTENSIONS = [
    'cogs.owner',
    'cogs.info',
    'cogs.autorole',
    'cogs.reactions',
    'cogs.verification',
    'cogs.leveling'
]

# Initialize colorama for Windows
colorama.init()

# Force flush stdout for Repl.it compatibility
if 'REPL_ID' in os.environ:
    sys.stdout.reconfigure(line_buffering=True)

def check_dependencies():
    """Check and warn about missing optional dependencies"""
    try:
        import nacl
        return True
    except ImportError:
        logger.warning("PyNaCl is not installed. Voice features will be disabled.")
        logger.info("To install PyNaCl, run: pip install PyNaCl")
        return False

# Custom formatter for console output
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'INFO': Fore.CYAN,
        'DEBUG': Fore.GREEN
    }

    def format(self, record):
        if record.msg is None:
            return ''
            
        msg_str = str(record.msg)
        
        # Special handling for discord.client and discord.gateway logs
        if record.name in ('discord.client', 'discord.gateway', 'discord.http'):
            # Convert these logs to our format
            clean_msg = msg_str
            for filter_msg in ('logging in using static token', 'has connected to Gateway'):
                if filter_msg in msg_str:
                    return ''  # Filter out these messages completely
            return f"{self.COLORS['INFO']}INFO{Style.RESET_ALL} | {clean_msg}"
                
        # Clean up bot status message
        if "Bot is in" in msg_str:
            guild_count = msg_str.split()[3]
            return f"{self.COLORS['INFO']}INFO{Style.RESET_ALL} | Active in {guild_count} guilds"
                
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            
        return f"{record.levelname} | {msg_str}"

# Create logs directory if it doesn't exist
def setup_logging_directory():
    """Ensure logging directory exists and is writable"""
    try:
        # For Replit compatibility - check if we're in Replit environment
        if 'REPL_ID' in os.environ:
            log_dir = os.path.join(os.getcwd(), 'logs')
        else:
            log_dir = 'logs'
            
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, 'bot.log')
    except Exception as e:
        print(f"Failed to setup logging directory: {e}")
        return 'bot.log'  # Fallback to current directory

# Create required directories
os.makedirs('logs', exist_ok=True)
os.makedirs('cogs', exist_ok=True)
os.makedirs('db', exist_ok=True)  # Add database directory

# Configure handlers
console_handler = logging.StreamHandler()  # Using default sys.stderr
console_handler.setFormatter(ColoredFormatter())
console_handler.setLevel(logging.INFO)  # Ensure console handler level is set

log_file = setup_logging_directory()
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.INFO)

# Clear any existing handlers
logging.getLogger().handlers.clear()

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Configure discord loggers
for logger_name in ('discord', 'discord.client', 'discord.gateway', 'discord.http'):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    # Allow propagation to root logger for console output
    logger.propagate = True
    logger.handlers.clear()  # Clear any existing handlers

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

def adapt_datetime(val: datetime) -> str:
    """Adapt datetime objects to ISO format strings for SQLite"""
    return val.isoformat()

def convert_datetime(val: bytes) -> datetime:
    """Convert ISO format strings from SQLite to datetime objects"""
    try:
        return datetime.fromisoformat(val.decode())
    except (ValueError, AttributeError):
        return None

# Register the adapter and converter at module level
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.all(),
            help_command=None
        )
        self.db = DatabaseManager('bot')
        self._rate_limit_retries = 0
        self._session_valid = True
        
    async def setup_hook(self) -> None:
        # Ensure database is initialized first
        await self.db.initialize()
        
        # Now load all cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"{filename[:-3]} cog initialized")
                except Exception as e:
                    logger.error(f"Failed to load extension {filename}: {e}")

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        try:
            # Initialize settings for all guilds
            for guild in self.guilds:
                try:
                    await self.db.ensure_guild_exists(guild.id, guild.name)
                except Exception as e:
                    logger.error(f"Error initializing guild {guild.id}: {e}")

            # Count and sync slash commands
            command_count = len([cmd for cmd in self.tree.walk_commands()])
            await self.tree.sync()
            logger.info(f"✓ Successfully registered {command_count} slash commands")
            
            change_activity.start()
            logger.info(f'{self.user} is ready!')
            logger.info(f'Bot is in {len(self.guilds)} guilds')
        except Exception as e:
            logger.error(f'Error in on_ready: {str(e)}')

    async def on_guild_join(self, guild: discord.Guild):
        """Initialize settings when bot joins a new guild"""
        try:
            await self.db.ensure_guild_exists(guild.id, guild.name)
            logger.info(f"Initialized settings for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to initialize settings for guild {guild.name}: {e}")

    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        """Log successful slash command usage"""
        try:
            if interaction.guild:
                execution_time = (datetime.now() - interaction.created_at).total_seconds()
                await self.db.log_command(
                    guild_id=interaction.guild_id,
                    user_id=interaction.user.id,
                    command_name=command.name,
                    success=True,
                    execution_time=execution_time
                )
                
                if hasattr(command, 'logging_enabled') and command.logging_enabled:
                    logger.info(f"{command.name} command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in command logging: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Log failed slash command usage"""
        try:
            if interaction.guild:
                execution_time = (datetime.now() - interaction.created_at).total_seconds()
                await self.db.log_command(
                    guild_id=interaction.guild_id,
                    user_id=interaction.user.id,
                    command_name=interaction.command.name if interaction.command else "unknown",
                    success=False,
                    error=str(error),
                    execution_time=execution_time
                )
            logger.error(f"Command error: {str(error)}")
        except Exception as e:
            logger.error(f"Error in command error logging: {e}")

    async def on_command_completion(self, ctx):
        """Log successful prefix command usage"""
        try:
            if ctx.guild:
                execution_time = (datetime.now() - ctx.message.created_at).total_seconds()
                await self.db.log_command(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    command_name=ctx.command.name,
                    success=True,
                    execution_time=execution_time
                )
        except Exception as e:
            logger.error(f"Error in command completion logging: {e}")

    async def on_command_error(self, ctx, error):
        """Log failed prefix command usage"""
        try:
            if not isinstance(error, commands.CommandNotFound) and ctx.guild:
                execution_time = (datetime.now() - ctx.message.created_at).total_seconds()
                await self.db.log_command(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    command_name=ctx.command.name if ctx.command else "unknown",
                    success=False,
                    error=str(error),
                    execution_time=execution_time
                )
            if not isinstance(error, commands.CommandNotFound):
                logger.error(f"Command error: {str(error)}")
        except Exception as e:
            logger.error(f"Error in command error logging: {e}")

    async def on_error(self, event_method: str, *args, **kwargs):
        """Global error handler for bot events"""
        try:
            error = sys.exc_info()[1]
            if isinstance(error, discord.errors.HTTPException) and error.status == 429:
                retry_after = error.response.headers.get('Retry-After', 5)
                self._rate_limit_retries += 1
                wait_time = float(retry_after) * (2 ** self._rate_limit_retries)  # Exponential backoff
                logger.warning(f"Rate limited. Waiting {wait_time:.2f} seconds before retry. Retry count: {self._rate_limit_retries}")
                await asyncio.sleep(wait_time)
                if event_method == "start":
                    await self.start(TOKEN)
            else:
                self._rate_limit_retries = 0  # Reset retry counter on non-rate-limit errors
                logger.error(f"Error in {event_method}: {str(error)}")
        except Exception as e:
            logger.error(f"Error in error handler: {str(e)}")

    async def on_shard_ready(self, shard_id):
        """Called when a shard is ready"""
        logger.info(f"Shard {shard_id} ready")
        self._session_valid = True

    async def on_shard_connect(self, shard_id):
        """Called when a shard connects to Discord"""
        logger.info(f"Shard {shard_id} connected")

    async def on_shard_disconnect(self, shard_id):
        """Called when a shard disconnects from Discord"""
        logger.warning(f"Shard {shard_id} disconnected")

    async def on_shard_resumed(self, shard_id):
        """Called when a shard resumes its session"""
        logger.info(f"Shard {shard_id} resumed")
        self._session_valid = True

    async def on_disconnect(self):
        """Called when the bot disconnects from Discord"""
        logger.warning("Bot disconnected from Discord")

    async def on_resumed(self):
        """Called when the bot resumes its session"""
        logger.info("Session resumed")
        self._session_valid = True

    async def on_connect(self):
        """Called when the bot connects to Discord"""
        logger.info("Connected to Discord")
        self._session_valid = True

    async def _periodic_db_cleanup(self):
        """Periodically clean up old database entries"""
        try:
            while not self.is_closed():
                await asyncio.sleep(86400)  # Run daily
                logger.info("Starting database cleanup")
                try:
                    await self.db.cleanup_old_data(days=30)
                except Exception as e:
                    logger.error(f"Error during database cleanup: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in database cleanup task: {e}")

    async def _periodic_db_optimize(self):
        """Periodically optimize database performance"""
        try:
            while not self.is_closed():
                await asyncio.sleep(604800)  # Run weekly
                logger.info("Starting database optimization")
                try:
                    await self.db.optimize()
                    stats = await self.db.get_connection_stats()
                    size = await self.db.get_database_size()
                    logger.info(f"Database optimized. Size: {size/1024/1024:.2f}MB, Stats: {stats}")
                except Exception as e:
                    logger.error(f"Error during database optimization: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in database optimization task: {e}")

# List of activities for the bot to cycle through
ACTIVITIES = [
    discord.Game(name="with commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="to commands"),
    discord.Game(name="with Python"),
    discord.Activity(type=discord.ActivityType.competing, name="in tasks")
]

@tasks.loop(minutes=10)
async def change_activity():
    """Change the bot's activity randomly every 10 minutes."""
    await bot.wait_until_ready()
    await bot.change_presence(activity=random.choice(ACTIVITIES))

def run_bot():
    """Start the bot with improved error handling"""
    retries = 0
    max_retries = 5
    base_delay = 5

    while retries < max_retries:
        try:
            bot._session_valid = True
            bot._reconnect_attempts = 0
            asyncio.run(bot.start(TOKEN))
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                retries += 1
                delay = min(1800, base_delay * (2 ** retries))
                logger.warning(f"Rate limited on startup. Attempt {retries}/{max_retries}. Waiting {delay} seconds...")
                time.sleep(delay)
            else:
                raise
        except discord.errors.GatewayNotFound:
            logger.error("Unable to connect to Discord. Gateway not available.")
            break
        except discord.errors.ConnectionClosed as e:
            retries += 1
            delay = min(1800, base_delay * (2 ** retries))
            logger.warning(f"Connection closed. Attempt {retries}/{max_retries}. Waiting {delay} seconds...")
            time.sleep(delay)
        except KeyboardInterrupt:
            logger.info('Bot shutdown initiated')
            break
        except Exception as e:
            logger.error(f'Failed to start bot: {str(e)}')
            break

if __name__ == '__main__':
    check_dependencies()
    bot = Bot()
    run_bot()

