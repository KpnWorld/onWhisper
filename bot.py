import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import sys
import time

from utils.db_manager import DBManager
from utils.ui_manager import UIManager

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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
                print("❌ Required intents are not enabled")
                return False

            # Check database connection
            if not await self.db_manager.check_connection():
                print("❌ Database connection failed")
                return False

            return True

        except Exception as e:
            print(f"❌ Startup validation failed: {e}")
            return False

    async def start(self, token: str) -> None:
        """Override start to add error handling"""
        try:
            self.start_time = datetime.utcnow()
            await super().start(token)
        except discord.LoginFailure:
            print("❌ Failed to login. Please check your token.")
            return
        except discord.PrivilegedIntentsRequired:
            print("❌ Privileged intents are required. Enable them in the Discord Developer Portal.")
            return
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            return

    async def setup_hook(self):
        """This is called when the bot starts, sets up the database and loads cogs"""
        print(f"\nStarting Bot v{self.version}")
        print("Running startup validation...")
        
        # Initialize database manager
        try:
            self.db_manager = DBManager(self)
            if not await self.db_manager.initialize():
                print("❌ Failed to initialize database")
                await self.close()
                return
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            await self.close()
            return

        if not await self._validate_startup():
            print("❌ Startup validation failed")
            await self.close()
            return

        print("✅ Startup validation passed\n")

        print("Initializing database...")
        try:
            # Load cogs
            print("\nLoading cogs...")
            cog_load_errors = []
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f"✅ Loaded {filename[:-3]}")
                    except Exception as e:
                        cog_load_errors.append((filename, str(e)))
                        print(f"❌ Failed to load {filename}: {e}")

            if cog_load_errors:
                print("\n⚠️ Some cogs failed to load:")
                for cog, error in cog_load_errors:
                    print(f"  - {cog}: {error}")

            # Sync guild data
            print("\nSyncing guild data...")
            try:
                sync_results = await self.db_manager.sync_guilds(self)
                print(f"✅ Synced {sync_results['success']} guilds")
                if sync_results['failed'] > 0:
                    print(f"⚠️ Failed to sync {sync_results['failed']} guilds")
            except Exception as e:
                print(f"❌ Failed to sync guilds: {e}")
                raise

            # Sync commands globally
            print("\nSyncing commands globally...")
            try:
                commands = await self.tree.sync()
                print(f"✅ Synced {len(commands)} commands globally")
            except discord.Forbidden:
                print("❌ Failed to sync commands: Missing applications.commands scope")
                raise
            except Exception as e:
                print(f"❌ Failed to sync commands: {e}")
                raise

            # Start background tasks
            print("\nStarting background tasks...")
            self.bg_tasks.extend([
                self.loop.create_task(self._periodic_cleanup()),
                self.loop.create_task(self._periodic_maintenance())
            ])
            print("✅ Background tasks started")

            # Set ready flag
            self._ready.set()

        except Exception as e:
            print(f"❌ Critical setup error: {e}")
            await self.close()
            raise

    @property
    def uptime(self):
        """Calculate the bot's uptime"""
        now = datetime.utcnow()
        delta = now - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    async def _periodic_cleanup(self):
        """Run periodic data cleanup"""
        while not self.is_closed():
            try:
                await asyncio.sleep(86400)  # Run daily
                await self.db_manager.cleanup_old_data()
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _periodic_maintenance(self):
        """Run periodic maintenance tasks"""
        while not self.is_closed():
            try:
                await asyncio.sleep(3600)  # Run hourly
                # Re-sync any guilds that might have gotten out of sync
                await self.db_manager.sync_guilds(self)
            except Exception as e:
                print(f"Error in periodic maintenance: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def close(self):
        """Close bot and cleanup"""
        # Cancel all background tasks
        for task in self.bg_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.bg_tasks, return_exceptions=True)
        
        await self.db_manager.close()
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready to start"""
        try:
            # Count both regular commands and application commands
            text_commands = set(cmd.qualified_name for cmd in self.walk_commands())
            app_commands = set(cmd.qualified_name for cmd in self.tree.walk_commands())
            total_commands = len(text_commands.union(app_commands))
            formatted_count = f"{total_commands:,}"

            print("\n───────────────")
            print(f"🔌 Connected as {self.user}")
            print(f"🌎 Serving {len(self.guilds)} servers")
            print(f"🎯 Commands loaded ({formatted_count} total commands)")
            print("───────────────\n")

            change_activity.start(self)

        except Exception as e:
            print(f"✖ Error during on_ready setup: {str(e)}")

    async def on_guild_join(self, guild: discord.Guild):
        try:
            await self.db_manager.ensure_guild_exists(guild.id, guild.name)
            print(f"Initialized settings for new guild: {guild.name}")
        except Exception as e:
            print(f"Failed to initialize settings for guild {guild.name}: {e}")

    async def on_message(self, message: discord.Message):
        if not message.author.bot:
            await self.db_manager.increment_stat(self.user.id, 'messages_seen')
        await super().on_message(message)

    async def on_app_command_completion(self, interaction: discord.Interaction, command: commands.Command):
        """Command completion handler"""
        await self.db_manager.increment_stat(self.user.id, 'commands_used')

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Enhanced error handler for slash commands"""
        try:
            # Rate limit/cooldown errors
            if isinstance(error, commands.CommandOnCooldown):
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Slow Down!",
                        f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
                    ),
                    ephemeral=True
                )
                return

            # Permission errors
            if isinstance(error, commands.MissingPermissions):
                perms = ", ".join(error.missing_permissions)
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Missing Permissions",
                        f"You need these permissions: {perms}"
                    ),
                    ephemeral=True
                )
                return

            if isinstance(error, commands.BotMissingPermissions):
                perms = ", ".join(error.missing_permissions)
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Bot Missing Permissions", 
                        f"I need these permissions: {perms}"
                    ),
                    ephemeral=True
                )
                return

            # Check errors
            if isinstance(error, commands.CheckFailure):
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Check Failed",
                        "You don't have permission to use this command."
                    ),
                    ephemeral=True
                )
                return

            # Log context of unexpected errors
            print(f"Command error in {interaction.command.name}:")
            print(f"- User: {interaction.user} ({interaction.user.id})")
            print(f"- Guild: {interaction.guild.name} ({interaction.guild.id})")
            print(f"- Channel: #{interaction.channel.name}")
            print(f"- Error: {str(error)}")
            
            error_embed = self.ui_manager.error_embed(
                "Command Error",
                "An unexpected error occurred. This has been logged for investigation."
            )
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except:
                # If we can't send the error message, just log it
                print("Failed to send error message to user")

        except Exception as e:
            print(f"Error in error handler: {str(e)}")

    async def on_command_completion(self, ctx: commands.Context):
        """Legacy command completion handler without logging"""
        await self.db_manager.increment_stat(self.user.id, 'commands_used')

    async def on_command_error(self, ctx, error):
        """Enhanced error handler for prefix commands"""
        try:
            if isinstance(error, commands.CommandNotFound):
                return  # Silently ignore command not found

            # Rate limit/cooldown errors 
            if isinstance(error, commands.CommandOnCooldown):
                await ctx.send(
                    embed=self.ui_manager.error_embed(
                        "Slow Down!",
                        f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
                    ),
                    ephemeral=True
                )
                return

            # Permission errors
            if isinstance(error, commands.MissingPermissions):
                perms = ", ".join(error.missing_permissions)
                await ctx.send(
                    embed=self.ui_manager.error_embed(
                        "Missing Permissions",
                        f"You need these permissions: {perms}"
                    ),
                    ephemeral=True
                )
                return

            if isinstance(error, commands.BotMissingPermissions):
                perms = ", ".join(error.missing_permissions)
                await ctx.send(
                    embed=self.ui_manager.error_embed(
                        "Bot Missing Permissions",
                        f"I need the following permissions: {perms}"
                    ),
                    ephemeral=True
                )
                return

            if isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(
                    embed=self.ui_manager.error_embed(
                        "Missing Argument",
                        f"Missing required argument: {error.param.name}"
                    ),
                    ephemeral=True
                )
                return

            # Log unexpected errors
            print(f"Command error in {ctx.command}: {str(error)}")
            await ctx.send(
                embed=self.ui_manager.error_embed(
                    "Command Error",
                    "An unexpected error occurred. The error has been logged."
                ),
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in error handler: {str(e)}")

    async def on_error(self, event_method: str, *args, **kwargs):
        """Enhanced global error handler"""
        try:
            error = sys.exc_info()[1]
            
            # Database errors
            if isinstance(error, Exception) and "Database" in str(error):
                print(f"Database error in {event_method}: {str(error)}")
                if not await self.db_manager.check_connection():
                    print("Attempting database recovery...")
                    if await self.db_manager.initialize():
                        print("Database connection restored")
                    else:
                        print("Database recovery failed")
                return

            # Discord API errors
            if isinstance(error, discord.errors.HTTPException):
                if error.status == 429:  # Rate limit
                    retry_after = error.response.headers.get('Retry-After', 5)
                    self._rate_limit_retries += 1
                    wait_time = float(retry_after) * (2 ** self._rate_limit_retries)
                    print(f"Rate limited. Waiting {wait_time:.2f}s (Retry #{self._rate_limit_retries})")
                    await asyncio.sleep(wait_time)
                    if event_method == "start":
                        await self.start(TOKEN)
                elif error.status == 403:  # Forbidden
                    print(f"Permission error in {event_method}: {error.text}")
                    # Check if it's thread-related
                    if "thread" in error.text.lower():
                        print("Thread permission error - check MANAGE_THREADS permission")
                elif error.status == 404:  # Not Found
                    print(f"Resource not found in {event_method}: {error.text}")
                else:
                    print(f"HTTP error in {event_method}: {error.status} - {error.text}")

            # Thread-specific errors
            elif isinstance(error, discord.errors.Forbidden) and "thread" in str(error).lower():
                print(f"Thread permission error in {event_method}")
                print("Make sure the bot has MANAGE_THREADS permission")

            # Generic Discord errors
            elif isinstance(error, discord.DiscordException):
                print(f"Discord error in {event_method}: {str(error)}")

            # Unexpected errors
            else:
                print(f"Unexpected error in {event_method}: {str(error)}")
                print(f"Args: {args}")
                print(f"Kwargs: {kwargs}")

        except asyncio.CancelledError:
            pass  # Task cancellation, handled gracefully
        except Exception as e:
            print(f"Error in error handler: {str(e)}")

    # Add custom exceptions for feature-specific errors
    class WhisperError(Exception):
        """Base exception for whisper-related errors"""
        pass

    class WhisperNotConfigured(WhisperError):
        """Raised when whisper system is not configured"""
        pass

    class WhisperNotEnabled(WhisperError):
        """Raised when whisper system is disabled"""
        pass

    class WhisperThreadError(WhisperError):
        """Raised when there's an error with whisper threads"""
        pass

    class LevelingError(Exception):
        """Base exception for leveling-related errors"""
        pass

    class XPNotEnabled(LevelingError):
        """Raised when XP system is disabled"""
        pass

    class ReactionRoleError(Exception):
        """Base exception for reaction role errors"""
        pass

@tasks.loop(minutes=10)
async def change_activity(bot):
    await bot.change_presence(activity=random.choice(ACTIVITIES))

def run_bot():
    """Run the bot with proper error handling and reconnection"""
    bot = None
    max_retries = 5
    retry_count = 0
    retry_delay = 30  # Initial delay in seconds

    while True:
        try:
            if retry_count >= max_retries:
                print(f"❌ Failed to start after {max_retries} attempts. Please check logs and configuration.")
                return

            if bot is None:
                bot = Bot()

            print("\n=== Starting Bot ===")
            if retry_count > 0:
                print(f"Retry attempt {retry_count}/{max_retries}")

            # Run the bot
            asyncio.run(bot.start(TOKEN))

        except discord.LoginFailure:
            print("❌ Login failed - Invalid token. Please check your .env file.")
            return  # Don't retry on authentication failures
        except discord.PrivilegedIntentsRequired:
            print("❌ Required privileged intents are not enabled. Please enable them in the Discord Developer Portal.")
            return  # Don't retry on intent issues
        except KeyboardInterrupt:
            print("\n⚠️ Shutdown requested...")
            if bot and not bot.is_closed():
                asyncio.run(bot.close())
            return
        except Exception as e:
            retry_count += 1
            print(f"\n❌ Error: {str(e)}")
            
            # Cleanup
            try:
                if bot and not bot.is_closed():
                    print("Cleaning up...")
                    asyncio.run(bot.close())
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
            
            # Reset bot instance
            bot = None
            
            if retry_count < max_retries:
                wait_time = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Maximum retry attempts reached. Shutting down.")
                return

if __name__ == "__main__":
    run_bot()
