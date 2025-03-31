import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import random
import asyncio
import logging
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
import time
from datetime import datetime, timedelta
import sqlite3

# Initialize colorama for Windows
colorama.init()

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

    # Messages to completely filter out
    FILTERED_MESSAGES = [
        'logging in using static token',
        'has connected to Gateway',
        'Shard ID',
        'Session ID'
    ]

    def format(self, record):
        if record.msg is None:
            return ''
            
        msg_str = str(record.msg)
        
        # Filter out noise
        if any(filter_msg in msg_str for filter_msg in self.FILTERED_MESSAGES):
            return ''
        
        # Clean up bot status message
        if "Bot is in" in msg_str:
            guild_count = msg_str.split()[3]
            return f"{self.COLORS['INFO']}INFO{Style.RESET_ALL} | Active in {guild_count} guilds"
                
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            
        return super().format(record)

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
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(levelname)s | %(message)s'))

log_file = setup_logging_directory()
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Clear any existing handlers from all loggers
logging.getLogger().handlers.clear()
logging.getLogger('discord').handlers.clear()
logging.getLogger('discord.http').handlers.clear()
logging.getLogger('discord.gateway').handlers.clear()

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Configure our bot logger
logger = logging.getLogger('onWhisper')
logger.setLevel(logging.INFO)
logger.propagate = False  # Changed to False
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Configure discord logger
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
discord_logger.propagate = False
discord_logger.addHandler(console_handler)
discord_logger.addHandler(file_handler)

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

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.db_path = os.path.join('db', f'{db_name}.db')
        os.makedirs('db', exist_ok=True)

    def update_guild_metrics(self, guild_id: int, member_count: int, active_users: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO guild_metrics 
                    (guild_id, member_count, active_users)
                    VALUES (?, ?, ?)
                """, (guild_id, member_count, active_users))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")

    def batch_update_metrics(self, metrics_data):
        try:
            with sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            ) as conn:
                cur = conn.cursor()
                cur.executemany("""
                    INSERT INTO guild_metrics 
                    (guild_id, member_count, active_users, timestamp)
                    VALUES (?, ?, ?, ?)
                """, [(m['guild_id'], m['member_count'], m['active_users'], m['timestamp']) for m in metrics_data])
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to batch update metrics: {e}")

    def ensure_guild_exists(self, guild_id: int):
        try:
            with sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            ) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR IGNORE INTO guild_settings (guild_id)
                    VALUES (?)
                """, (guild_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to ensure guild exists: {e}")

    def log_command(self, guild_id: int, user_id: int, command_name: str, success: bool = True, error: str = None):
        try:
            with sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            ) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO command_stats 
                    (guild_id, user_id, command_name, success, error_message)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild_id, user_id, command_name, success, error))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = time.time()
        self.db = DatabaseManager('bot')
        self._metrics_task = None
        self._last_metrics = {}  # Will store datetime objects
        self._metric_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._last_flush = datetime.now()

    async def setup_hook(self):
        """Set up the bot's database and metrics collection"""
        await self.load_cogs()
        self._metrics_task = self.loop.create_task(self._collect_metrics())
        self._flush_task = self.loop.create_task(self._flush_metrics())
        logger.info("Bot setup completed")

    async def _collect_metrics(self):
        """Collect guild metrics every 5 minutes"""
        try:
            while not self.is_closed():
                current_time = datetime.now()
                
                for guild in self.guilds:
                    last_collection = self._last_metrics.get(guild.id, datetime.min)  # Use datetime.min as default
                    if (current_time - last_collection).total_seconds() >= 300:  # 5 minutes
                        active_users = len([
                            m for m in guild.members 
                            if str(m.status) == "online" and not m.bot
                        ])
                        
                        async with self._buffer_lock:
                            self._metric_buffer.append({
                                'guild_id': guild.id,
                                'member_count': guild.member_count,
                                'active_users': active_users,
                                'timestamp': current_time
                            })
                        self._last_metrics[guild.id] = current_time
                
                await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            if self._metric_buffer:
                await self._flush_metrics_buffer()
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def _flush_metrics(self):
        """Periodically flush collected metrics to database"""
        try:
            while not self.is_closed():
                current_time = datetime.now()
                if (current_time - self._last_flush).total_seconds() >= 300 or len(self._metric_buffer) >= 100:
                    await self._flush_metrics_buffer()
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            if self._metric_buffer:
                await self._flush_metrics_buffer()
        except Exception as e:
            logger.error(f"Error in metrics flush: {e}")

    async def _flush_metrics_buffer(self):
        """Flush metrics buffer to database"""
        async with self._buffer_lock:
            if not self._metric_buffer:
                return
            
            try:
                # Process in chunks of 50 to avoid overwhelming the database
                chunk_size = 50
                for i in range(0, len(self._metric_buffer), chunk_size):
                    chunk = self._metric_buffer[i:i + chunk_size]
                    await asyncio.to_thread(self.db.batch_update_metrics, chunk)
                
                self._metric_buffer.clear()
                self._last_flush = datetime.now()
            except Exception as e:
                logger.error(f"Error flushing metrics: {e}")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._metrics_task:
            self._metrics_task.cancel()
        if self._flush_task:
            self._flush_task.cancel()

    async def load_cogs(self):
        """Load all cogs from the cogs directory."""
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'Loaded cog: {filename[:-3]}')
                except Exception as e:
                    logger.error(f'Failed to load cog {filename[:-3]}: {str(e)}')

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        try:
            # Initialize settings for all guilds
            for guild in self.guilds:
                self.db.ensure_guild_exists(guild.id)

            # Count and sync slash commands
            command_count = 0
            for cmd in self.tree.walk_commands():
                command_count += 1
            
            await self.tree.sync()
            logger.info(f"✓ Successfully registered {command_count} slash commands")
            
            change_activity.start()
            logger.info(f'{self.user} is ready!')
            logger.info(f'Bot is in {len(self.guilds)} guilds')
        except Exception as e:
            logger.error(f'Error in on_ready: {str(e)}')

    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild"""
        try:
            self.db.ensure_guild_exists(guild.id)
            logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        except Exception as e:
            logger.error(f"Error setting up new guild {guild.name}: {e}")

    async def on_command_error(self, ctx, error):
        """Global error handler with logging"""
        if isinstance(error, commands.CommandNotFound):
            return

        self.db.log_command(
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.author.id,
            command_name=ctx.command.name if ctx.command else "unknown",
            success=False,
            error=str(error)
        )
        
        logger.error(f'Error occurred: {str(error)}')
        await ctx.send(f'An error occurred: {str(error)}')

    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        """Log successful slash command usage"""
        if interaction.guild:
            self.db.log_command(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                command_name=command.name,
                success=True
            )

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
    """Start the bot with the token from environment variables."""
    try:
        asyncio.run(bot.run(TOKEN))
    except KeyboardInterrupt:
        logger.info('Bot shutdown initiated')
    except Exception as e:
        logger.error(f'Failed to start bot: {str(e)}')

if __name__ == '__main__':
    check_dependencies()
    bot = Bot()
    run_bot()

