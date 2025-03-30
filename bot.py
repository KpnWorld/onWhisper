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

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name

    def update_guild_metrics(self, guild_id, member_count, active_users):
        pass

    def ensure_guild_exists(self, guild_id):
        pass

    def log_command(self, guild_id, user_id, command_name, success, error=None):
        pass

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = time.time()
        self.db = DatabaseManager('bot')
        self._metrics_task = None

    async def setup_hook(self):
        """Set up the bot's database and metrics collection"""
        await self.load_cogs()
        self._metrics_task = self.loop.create_task(self._collect_metrics())
        logger.info("Bot setup completed")

    async def _collect_metrics(self):
        """Collect guild metrics every 5 minutes"""
        try:
            while not self.is_closed():
                for guild in self.guilds:
                    # Count active users (members who sent message in last hour)
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    active_users = len([
                        m for m in guild.members 
                        if isinstance(m.status, discord.Status.online) and not m.bot
                    ])

                    self.db.update_guild_metrics(
                        guild_id=guild.id,
                        member_count=guild.member_count,
                        active_users=active_users
                    )
                
                await asyncio.sleep(300)  # 5 minutes
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

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

