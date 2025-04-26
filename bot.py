import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
import sys
import time

from utils.db_manager import DBManager

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Register datetime adapter and converter for sqlite3
def adapt_datetime(val: datetime) -> str:
    return val.isoformat()

def convert_datetime(val: bytes) -> datetime:
    try:
        return datetime.fromisoformat(val.decode())
    except (ValueError, AttributeError):
        return None

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

# List of activities for the bot to cycle through
ACTIVITIES = [
    discord.Game(name="with commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="to commands"),
    discord.Game(name="with Python"),
    discord.Activity(type=discord.ActivityType.competing, name="in tasks")
]

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.all(),
            help_command=None
        )
        self.db_manager = DBManager('bot')
        self._rate_limit_retries = 0
        self._session_valid = True
        self.start_time = datetime.utcnow()

    def create_embed(self, title: str, description: str, command_type: str = "User") -> discord.Embed:
        """Create a standardized embed with consistent formatting"""
        color = discord.Color.blurple() if command_type == "User" else discord.Color.red()

        embed = discord.Embed(
            title=title,
            description=f"```\n{description}\n```",
            color=color,
            timestamp=datetime.utcnow()
        )

        # Add command type footer
        embed.set_footer(text=f"Command Type • {command_type}")

        return embed

    async def setup_hook(self) -> None:
        await self.db_manager.initialize()
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"{filename[:-3]} cog initialized")
                except Exception as e:
                    print(f"Failed to load extension {filename}: {e}")

    async def close(self):
        await self.db_manager.close()
        await super().close()

    async def on_ready(self):
        try:
            # Check if we need to sync commands (only once per boot)
            if not hasattr(self, 'commands_synced'):  
                try:
                    await self.sync_commands()  # Sync commands
                    self.commands_synced = True  # Set flag after syncing
                    synced_count = len(self.application_commands)
                except Exception as e:
                    print(f"⚠ Failed to sync commands: {e}")
                    synced_count = "?"
            else:
                synced_count = len(self.application_commands)

            # Pretty format synced count with commas
            formatted_count = f"{synced_count:,}"

            print("\n───────────────")
            print(f"🔌 Connected as {self.user.name}#{self.user.discriminator}")
            print(f"🌎 Serving {len(self.guilds)} servers")
            print(f"🎯 Slash commands auto-synced by Pycord ({formatted_count} commands)")
            print("───────────────\n")

            change_activity.start()

        except Exception as e:
            print(f"✖ Error during on_ready setup: {str(e)}")

    async def on_guild_join(self, guild: discord.Guild):
        try:
            await self.db_manager.ensure_guild_exists(guild.id, guild.name)
            print(f"Initialized settings for new guild: {guild.name}")
        except Exception as e:
            print(f"Failed to initialize settings for guild {guild.name}: {e}")

    async def on_app_command_completion(self, interaction: discord.Interaction, command: commands.Command):
        """Command completion handler without logging"""
        pass

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Error handler that just prints to console"""
        print(f"Command error: {str(error)}")

    async def on_command_completion(self, ctx):
        """Legacy command completion handler without logging"""
        pass

    async def on_command_error(self, ctx, error):
        """Legacy error handler that just prints to console"""
        if not isinstance(error, commands.CommandNotFound):
            print(f"Command error: {str(error)}")

    async def on_error(self, event_method: str, *args, **kwargs):
        try:
            error = sys.exc_info()[1]
            if isinstance(error, discord.errors.HTTPException) and error.status == 429:
                retry_after = error.response.headers.get('Retry-After', 5)
                self._rate_limit_retries += 1
                wait_time = float(retry_after) * (2 ** self._rate_limit_retries)
                print(f"Rate limited. Waiting {wait_time:.2f} seconds. Retry #{self._rate_limit_retries}")
                await asyncio.sleep(wait_time)
                if event_method == "start":
                    await self.start(TOKEN)
            else:
                self._rate_limit_retries = 0
                print(f"Error in {event_method}: {str(error)}")
        except Exception as e:
            print(f"Error in error handler: {str(e)}")

    async def on_shard_ready(self, shard_id): print(f"Shard {shard_id} ready")
    async def on_shard_connect(self, shard_id): print(f"Shard {shard_id} connected")
    async def on_shard_disconnect(self, shard_id): print(f"Shard {shard_id} disconnected")
    async def on_shard_resumed(self, shard_id): print(f"Shard {shard_id} resumed"); self._session_valid = True
    async def on_disconnect(self): print("Bot disconnected")
    async def on_resumed(self): print("Session resumed"); self._session_valid = True
    async def on_connect(self): print("Connected to Discord"); self._session_valid = True

    async def _periodic_db_cleanup(self):
        try:
            while not self.is_closed():
                await asyncio.sleep(86400)
                print("Starting database cleanup")
                try:
                    await self.db_manager.cleanup_old_data(days=30)
                except Exception as e:
                    print(f"Error during cleanup: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Cleanup loop error: {e}")

    async def _periodic_db_optimize(self):
        try:
            while not self.is_closed():
                await asyncio.sleep(604800)
                print("Starting database optimization")
                try:
                    await self.db_manager.optimize()
                    stats = await self.db_manager.get_connection_stats()
                    size = await self.db_manager.get_database_size()
                    print(f"Optimized DB. Size: {size/1024/1024:.2f}MB | Stats: {stats}")
                except Exception as e:
                    print(f"Optimization error: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Optimization loop error: {e}")

@tasks.loop(minutes=10)
async def change_activity():
    await bot.wait_until_ready()
    await bot.change_presence(activity=random.choice(ACTIVITIES))

def run_bot():
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
                print(f"Startup rate limit. Attempt {retries}/{max_retries}. Waiting {delay}s...")
                time.sleep(delay)
            else:
                raise
        except discord.errors.GatewayNotFound:
            print("Discord gateway not found.")
            break
        except discord.errors.ConnectionClosed:
            retries += 1
            delay = min(1800, base_delay * (2 ** retries))
            print(f"Connection closed. Attempt {retries}/{max_retries}. Waiting {delay}s...")
            time.sleep(delay)

if __name__ == "__main__":
    bot = Bot()
    run_bot()
