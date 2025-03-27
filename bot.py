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

    # Messages to filter out completely
    FILTERED_MESSAGES = [
        'logging in using static token',
        'has connected to Gateway'
    ]

    def format(self, record):
        if record.msg is None:
            return ''
            
        msg_str = str(record.msg)
        
        # Filter out specific messages
        if any(filter_msg in msg_str for filter_msg in self.FILTERED_MESSAGES):
            return ''
                
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

# Configure handlers
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(levelname)s | %(message)s'))

log_file = setup_logging_directory()
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Configure our bot logger
logger = logging.getLogger('onWhisper')
logger.setLevel(logging.INFO)
# Don't add handlers to avoid duplicates
logger.propagate = True

# Disable propagation for discord loggers to prevent duplicate messages
discord_logger = logging.getLogger('discord')
discord_logger.propagate = False
discord_logger.addHandler(console_handler)
discord_logger.addHandler(file_handler)
discord_logger.setLevel(logging.INFO)  # Update discord logger level to show more informative messages

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

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

async def load_cogs():
    """Load all cogs from the cogs directory."""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Loaded cog: {filename[:-3]}')
            except Exception as e:
                logger.error(f'Failed to load cog {filename[:-3]}: {str(e)}')

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    try:
        await load_cogs()
        change_activity.start()  # Start the activity cycling task
        logger.info(f'{bot.user} has connected to Discord!')
        logger.info(f'Bot is in {len(bot.guilds)} guilds')
    except Exception as e:
        logger.error(f'Error in on_ready: {str(e)}')

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for bot commands."""
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error(f'Error occurred: {str(error)}')
    await ctx.send(f'An error occurred: {str(error)}')

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
    run_bot()

