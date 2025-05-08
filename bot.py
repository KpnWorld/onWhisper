import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import signal
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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
            help_command=None
        )

        self.db_manager = None
        self.ui_manager = UIManager()
        self.bg_tasks = []
        self.start_time = None
        self.activity_task = None
        self._shutdown_timeout = 10
        self._closing = asyncio.Event()
        self._ready = asyncio.Event()

        try:
            with open("version.txt", "r") as f:
                self.version = f.read().strip()
        except:
            self.version = "0.0.1"
            with open("version.txt", "w") as f:
                f.write(self.version)

    @property
    def uptime(self):
        if not self.start_time:
            return "Bot not started"
        delta = datetime.utcnow() - self.start_time
        return f"{delta.days}d {delta.seconds//3600}h {(delta.seconds//60)%60}m {delta.seconds%60}s"

    async def setup_hook(self):
        print(f"[INFO] Starting Bot v{self.version}")
        self.db_manager = DBManager(self)

        if not await self.db_manager.initialize():
            print("[ERROR] Failed to initialize database.")
            return await self.close()

        if not await self._validate_startup():
            print("[ERROR] Startup validation failed.")
            return await self.close()

        for file in os.listdir("./cogs"):
            if file.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{file[:-3]}")
                    print(f"[INFO] ✅ Loaded cog {file}")
                except Exception as e:
                    print(f"[ERROR] ❌ Failed to load cog {file}: {e}")

        try:
            sync_result = await self.db_manager.sync_guilds(self)
            print(f"[INFO] ✅ Synced {sync_result['success']} guilds")
        except Exception as e:
            print(f"[ERROR] ❌ Guild sync failed: {e}")

        try:
            await self.tree.sync()
            print(f"[INFO] ✅ Synced commands globally")
        except discord.Forbidden:
            print("[ERROR] ❌ Missing 'applications.commands' scope.")
        except Exception as e:
            print(f"[ERROR] ❌ Command sync failed: {e}")

        self.bg_tasks.extend([
            asyncio.create_task(self._periodic_cleanup()),
            asyncio.create_task(self._periodic_maintenance())
        ])
        self._ready.set()

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord"""
        print(f"[INFO] Bot {self.user.name} is ready!")
        self.start_time = datetime.utcnow()
        self.activity_task = asyncio.create_task(self._change_activity())

    async def _validate_startup(self):
        try:
            if not await self.db_manager.check_connection():
                return False
            return True
        except Exception as e:
            print(f"[ERROR] Startup validation failed: {e}")
            return False

    async def _periodic_cleanup(self):
        while not self.is_closed():
            try:
                await asyncio.sleep(86400)
                await self.db_manager.cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Cleanup error: {e}")
                await asyncio.sleep(300)

    async def _periodic_maintenance(self):
        while not self.is_closed():
            try:
                await asyncio.sleep(3600)
                await self.db_manager.sync_guilds(self)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Maintenance error: {e}")
                await asyncio.sleep(300)

    async def _change_activity(self):
        """Change bot's activity periodically"""
        while not self.is_closed():
            try:
                await self.change_presence(activity=random.choice(ACTIVITIES))
                await asyncio.sleep(600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Activity error: {e}")
                await asyncio.sleep(60)

    async def close(self):
        if self._closing.is_set():
            return
        self._closing.set()
        print("[INFO] Shutting down...")

        if self.activity_task:
            self.activity_task.cancel()
            try:
                await asyncio.wait_for(self.activity_task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                print("[WARNING] Activity task shutdown timed out")

        for task in self.bg_tasks:
            task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(*self.bg_tasks, return_exceptions=True), timeout=self._shutdown_timeout)
        except asyncio.TimeoutError:
            print("[WARNING] Some tasks did not shut down in time")

        if self.db_manager:
            try:
                await asyncio.wait_for(self.db_manager.close(), timeout=5)
            except Exception as e:
                print(f"[ERROR] DB close error: {e}")

        await super().close()
        print("[INFO] Bot shutdown complete.")

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
        print(f"[ERROR] Command error in {ctx.command}: {str(error)}")
        await ctx.send(
            embed=self.ui_manager.error_embed(
                "Error",
                "An unexpected error occurred. This has been logged."
            )
        )

    async def on_application_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Global error handler for slash commands"""
        if isinstance(error, commands.CommandOnCooldown):
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

        # Log unexpected errors
        print(f"[ERROR] Slash command error in {interaction.command}: {str(error)}")
        
        try:
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    "Error",
                    "An unexpected error occurred. This has been logged."
                ),
                ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] Failed to send error message: {e}")

def run_bot():
    bot = Bot()

    def handle_signal(signum, frame):
        signal_name = signal.Signals(signum).name
        print(f"[INFO] Received signal: {signal_name}")
        asyncio.create_task(bot.close())

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot()
