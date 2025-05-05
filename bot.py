import discord
from discord import app_commands
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
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            help_command=None
        )
        self.db_manager = DBManager('bot')
        self.ui_manager = UIManager(self)
        self._rate_limit_retries = 0
        self._session_valid = True
        self.start_time = datetime.utcnow()
        self.bg_tasks = []  # Track background tasks

    async def setup_hook(self):
        """This is called when the bot starts, sets up the database and loads cogs"""
        # Initialize database
        print("Initializing database...")
        try:
            if not await self.db_manager.initialize():
                print("❌ Failed to initialize database")
                await self.close()
                return
            print("✅ Database initialized")
            
            # Verify database connection
            if not await self.db_manager.check_connection():
                print("❌ Database connection check failed") 
                await self.close()
                return
            print("✅ Database connection verified")

            # Load cogs
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f"✅ Loaded {filename[:-3]}")
                    except Exception as e:
                        print(f"❌ Failed to load {filename}: {e}")

            # Sync commands directly from cogs
            print("Registering commands in bot's profile...")
            try:
                # First sync to guild for testing
                try:
                    guild_commands = await self.tree.sync(guild=discord.Object(id=int(os.getenv('TEST_GUILD_ID'))))
                    print(f"✅ Synced {len(guild_commands)} commands to test guild")
                except Exception as e:
                    print(f"⚠️ Guild sync failed: {e}")
                
                # Then sync globally
                print("Syncing commands globally...")
                commands = await self.tree.sync()
                print(f"✅ Synced {len(commands)} commands globally")

                # Start background tasks
                self.bg_tasks.append(self.loop.create_task(self._periodic_db_cleanup()))
                self.bg_tasks.append(self.loop.create_task(self._periodic_db_optimize()))
                self.bg_tasks.append(self.loop.create_task(self._periodic_db_health_check()))

            except Exception as e:
                print(f"❌ Failed to sync commands: {e}")
                raise

        except Exception as e:
            print(f"❌ Critical setup error: {e}")
            raise

    async def _periodic_db_health_check(self):
        """Periodically check database health"""
        try:
            while not self.is_closed():
                await asyncio.sleep(300)  # Check every 5 minutes
                if not await self.db_manager.check_connection():
                    print("⚠️ Database health check failed")
                    if await self.db_manager.initialize():
                        print("✅ Database connection restored")
                    else:
                        print("❌ Database recovery failed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Health check error: {e}")

    async def close(self):
        # Cancel all background tasks
        for task in self.bg_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.bg_tasks, return_exceptions=True)
        
        await self.db_manager.close()
        await super().close()

    async def on_ready(self):
        try:
            # Count both application commands and text commands
            total_commands = len(set([cmd.qualified_name for cmd in self.walk_commands()]))
            formatted_count = f"{total_commands:,}"

            print("\n───────────────")
            print(f"🔌 Connected as {self.user}")
            print(f"🌎 Serving {len(self.guilds)} servers")
            print(f"🎯 Commands loaded ({formatted_count} commands)")
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

    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command):
        await self.db_manager.increment_stat(self.user.id, 'commands_used')

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Enhanced error handler for slash commands"""
        try:
            # Rate limit/cooldown errors
            if isinstance(error, discord.app_commands.CommandOnCooldown):
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Slow Down!",
                        f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
                    ),
                    ephemeral=True
                )
                return

            # Permission errors
            if isinstance(error, discord.app_commands.MissingPermissions):
                perms = ", ".join(error.missing_permissions)
                await interaction.response.send_message(
                    embed=self.ui_manager.error_embed(
                        "Missing Permissions",
                        f"You need these permissions: {perms}"
                    ),
                    ephemeral=True
                )
                return

            if isinstance(error, discord.app_commands.BotMissingPermissions):
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
            if isinstance(error, discord.app_commands.CheckFailure):
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

    async def _periodic_db_cleanup(self):
        """Periodically clean up old database entries"""
        try:
            while not self.is_closed():
                await asyncio.sleep(86400)  # Run daily
                print("Starting database cleanup")
                try:
                    await self.db_manager.cleanup_old_data(days=30)
                    print("✅ Database cleanup completed")
                except Exception as e:
                    print(f"❌ Error during cleanup: {e}")
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
async def change_activity(bot):
    await bot.change_presence(activity=random.choice(ACTIVITIES))

def run_bot():
    while True:  # Keep trying to reconnect
        try:
            bot = Bot()
            asyncio.run(bot.start(TOKEN))
        except Exception as e:
            print(f"Error: {e}")
            try:
                if not bot.is_closed():
                    asyncio.run(bot.close())
            except:
                pass
            print("Restarting bot in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    run_bot()
