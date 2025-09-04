# bot.py

import os
import signal
import asyncio
import logging
import random
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from discord import app_commands

# -------------------- Utils Imports -------------------- #
from utils.db_manager import DBManager
from utils.config import ConfigManager

# -------------------- Environment -------------------- #
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")

if not DISCORD_TOKEN or not APPLICATION_ID:
    raise ValueError("DISCORD_TOKEN or APPLICATION_ID not found in .env")

# -------------------- Logging Setup -------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("onWhisperBot")

# -------------------- Bot Setup -------------------- #
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=int(APPLICATION_ID)
)

# -------------------- Managers -------------------- #
db_manager = DBManager()
config_manager = ConfigManager(db_manager)

bot.db_manager = db_manager
bot.config_manager = config_manager

# -------------------- Rotating Status -------------------- #
@tasks.loop(minutes=10)
async def rotate_status():
    statuses = [
        discord.Game(name="onWhisper v1.0.0"),
        discord.Activity(type=discord.ActivityType.listening, name="/help"),
        discord.Status.idle
    ]
    choice = random.choice(statuses)
    if isinstance(choice, discord.Status):
        await bot.change_presence(status=discord.Status.idle)
    else:
        await bot.change_presence(activity=choice, status=discord.Status.online)

# -------------------- Events -------------------- #
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("Bot is ready!")

    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} app commands")
    except Exception:
        logger.exception("Failed to sync app commands")

    if not rotate_status.is_running():
        rotate_status.start()

# -------------------- Global Error Handlers -------------------- #
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"App command error: {error}", exc_info=True)
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Something went wrong while executing that command.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ An unexpected error occurred after the command started.",
                ephemeral=True
            )
    except Exception as followup_error:
        logger.error(f"Failed to send error response: {followup_error}", exc_info=True)

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`. Please check the command usage.", ephemeral=True)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided: {error}", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    else:
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
        await ctx.send("❌ An unexpected error occurred while executing that command.", ephemeral=True)

# -------------------- Cog Loading -------------------- #
COGS = [
    "cogs.debug",
    "cogs.info",
    "cogs.leveling",
    "cogs.moderation",
    # "cogs.roles",
    # "cogs.logging",
    # "cogs.whisper",
    "cogs.config",
    "cogs.help"
]

async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.exception(f"Failed to load cog {cog}: {e}")

# -------------------- Async Main -------------------- #
async def main():
    async with bot:
        await db_manager.init_db()
        await load_cogs()
        await bot.start(DISCORD_TOKEN)

# -------------------- Graceful Shutdown -------------------- #
def shutdown(*_):
    logger.info("Shutting down bot...")
    asyncio.create_task(bot.close())

loop = asyncio.get_event_loop()
for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, lambda s=sig: shutdown())

# -------------------- Entry -------------------- #
if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped via keyboard interrupt.")
    finally:
        loop.close()
