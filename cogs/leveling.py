import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import logging
from typing import Literal, Dict
from datetime import datetime, timedelta
from utils.ui_manager import UIManager

# Initialize logger
logger = logging.getLogger(__name__)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use bot's database instance instead of creating new one
        self.ui = UIManager()
        self.xp_cooldowns: Dict[int, Dict[int, datetime]] = {}
        self.cooldown_settings = {}
        self.xp_ranges = {}
        self._cleanup_task = bot.loop.create_task(self._cleanup_cooldowns())
        self._xp_buffer = []
        self._buffer_lock = asyncio.Lock()
        self._last_flush = datetime.now()
        bot.loop.create_task(self._init_db())
        bot.loop.create_task(self._flush_xp_buffer())
        logger.info("Leveling cog initialized")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.bot.loop.create_task(self._final_flush())

    async def _final_flush(self):
        """Final flush of XP buffer on unload"""
        try:
            if self._xp_buffer:
                await self._flush_xp_buffer_to_db()
        except Exception as e:
            logger.error(f"Error in final XP flush: {e}")

    async def _cleanup_cooldowns(self):
        """Periodically clean up expired cooldowns"""
        try:
            while True:
                current_time = datetime.now()
                for guild_id in list(self.xp_cooldowns.keys()):
                    users = self.xp_cooldowns[guild_id]
                    # Remove expired cooldowns
                    expired = [user_id for user_id, end_time in users.items() 
                             if current_time >= end_time]
                    for user_id in expired:
                        del users[user_id]
                    # Remove empty guild entries
                    if not users:
                        del self.xp_cooldowns[guild_id]
                await asyncio.sleep(60)  # Cleanup every minute
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in cooldown cleanup: {e}")

    async def _flush_xp_buffer(self):
        """Periodically flush XP buffer to database"""
        while not self.bot.is_closed():
            try:
                current_time = datetime.now()
                if (current_time - self._last_flush).total_seconds() >= 60 or len(self._xp_buffer) >= 100:
                    await self._flush_xp_buffer_to_db()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in XP buffer flush: {e}")
                await asyncio.sleep(30)

    async def _flush_xp_buffer_to_db(self):
        """Flush XP buffer to database with batch processing"""
        async with self._buffer_lock:
            if not self._xp_buffer:
                return

            buffer_copy = self._xp_buffer.copy()
            self._xp_buffer.clear()
            self._last_flush = datetime.now()

        try:
            async with self.db.transaction():
                # Group updates by user and guild
                updates = {}
                for entry in buffer_copy:
                    key = (entry['user_id'], entry['guild_id'])
                    if key not in updates:
                        updates[key] = {
                            'xp_gained': 0,
                            'messages': 0,
                            'timestamp': entry['timestamp']
                        }
                    updates[key]['xp_gained'] += entry['xp_gained']
                    updates[key]['messages'] += 1

                # Process updates in batches
                batch_size = 50
                update_batch = []
                
                for (user_id, guild_id), data in updates.items():
                    # Get current XP and level
                    current = await self.db.fetchone("""
                        SELECT xp, level, messages 
                        FROM xp_data 
                        WHERE user_id = ? AND guild_id = ?
                    """, (user_id, guild_id))

                    if current:
                        current_xp = current['xp']
                        current_level = current['level']
                        total_messages = current['messages'] + data['messages']
                    else:
                        current_xp = 0
                        current_level = 1
                        total_messages = data['messages']

                    new_xp = current_xp + data['xp_gained']
                    level_changed = False

                    # Calculate level ups
                    while True:
                        xp_needed = self.calculate_xp_for_level(current_level)
                        if new_xp >= xp_needed:
                            current_level += 1
                            new_xp -= xp_needed
                            level_changed = True
                        else:
                            break

                    update_batch.append((
                        new_xp, current_level, total_messages,
                        data['timestamp'], user_id, guild_id
                    ))

                    if len(update_batch) >= batch_size:
                        await self.db.batch_update(
                            'xp_data',
                            ['xp', 'level', 'messages', 'last_message'],
                            'user_id, guild_id',
                            update_batch
                        )
                        update_batch = []

                # Process remaining updates
                if update_batch:
                    await self.db.batch_update(
                        'xp_data',
                        ['xp', 'level', 'messages', 'last_message'],
                        'user_id, guild_id',
                        update_batch
                    )

        except Exception as e:
            logger.error(f"Error flushing XP buffer: {e}")
            # Re-add failed updates to buffer
            async with self._buffer_lock:
                self._xp_buffer.extend(buffer_copy)

    def is_on_cooldown(self, guild_id: int, user_id: int) -> bool:
        """Check if a user is on XP gain cooldown"""
        if guild_id not in self.xp_cooldowns:
            return False
        if user_id not in self.xp_cooldowns[guild_id]:
            return False
        return datetime.now() < self.xp_cooldowns[guild_id][user_id]

    def add_cooldown(self, guild_id: int, user_id: int, seconds: int):
        """Add a cooldown for a user"""
        if guild_id not in self.xp_cooldowns:
            self.xp_cooldowns[guild_id] = {}
        self.xp_cooldowns[guild_id][user_id] = datetime.now() + timedelta(seconds=seconds)

    async def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            async with self.db.cursor() as cur:
                # Create leveling tables if they don't exist
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS leveling_settings (
                        guild_id INTEGER PRIMARY KEY,
                        xp_cooldown INTEGER DEFAULT 60,
                        min_xp INTEGER DEFAULT 15,
                        max_xp INTEGER DEFAULT 25,
                        voice_xp_enabled BOOLEAN DEFAULT 0,
                        voice_xp_per_minute INTEGER DEFAULT 10,
                        level_up_message TEXT DEFAULT 'Congratulations {user}, you reached level {level}!',
                        level_up_channel_id INTEGER,
                        stack_roles BOOLEAN DEFAULT 1,
                        ignore_channels TEXT,
                        xp_multiplier REAL DEFAULT 1.0,
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    )
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS xp_data (
                        user_id INTEGER,
                        guild_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        messages INTEGER DEFAULT 0,
                        last_message TIMESTAMP,
                        PRIMARY KEY (user_id, guild_id),
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    )
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS level_roles (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        remove_lower BOOLEAN DEFAULT 0,
                        temporary BOOLEAN DEFAULT 0,
                        duration INTEGER,
                        PRIMARY KEY (guild_id, level),
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    )
                """)

                # Create indexes
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_xp_data_guild ON xp_data(guild_id)")
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_xp_data_level ON xp_data(level DESC)")
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_level_roles_guild ON level_roles(guild_id)")

            # Initialize settings for all guilds
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
                async with self.db.cursor() as cur:
                    await cur.execute("""
                        INSERT OR IGNORE INTO leveling_settings (guild_id)
                        VALUES (?)
                    """, (guild.id,))

            # Load settings into memory
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT guild_id, xp_cooldown, min_xp, max_xp
                    FROM leveling_settings
                """)
                rows = await cur.fetchall()
                for guild_id, cooldown, min_xp, max_xp in rows:
                    self.cooldown_settings[guild_id] = cooldown
                    self.xp_ranges[guild_id] = (min_xp, max_xp)

            logger.info("Leveling database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize leveling database: {e}")

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed with balanced curve"""
        base_xp = 100
        scaling_factor = 1.2
        acceleration = 1.1
        return int(base_xp * (scaling_factor ** (level - 1)) * (1 + (level * acceleration)))

    def generate_progress_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """Generate a visual progress bar"""
        filled = '█'
        empty = '░'
        progress = current / maximum
        filled_length = int(length * progress)
        bar = filled * filled_length + empty * (length - filled_length)
        return f"`{bar}` ({(progress * 100):.1f}%)"

    def format_timestamp(self, timestamp_str: str) -> str:
        """Convert ISO timestamp to readable format"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            return timestamp_str

    def format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time"""
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        
        days = delta.days
        if days > 365:
            years = days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
        if days > 30:
            months = days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''} ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        minutes = (delta.seconds % 3600) // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    def get_cooldown(self, guild_id: int) -> int:
        """Get guild-specific cooldown or default"""
        return self.cooldown_settings.get(guild_id, 60)

    def get_xp_range(self, guild_id: int) -> tuple[int, int]:
        """Get guild-specific XP range or default"""
        return self.xp_ranges.get(guild_id, (15, 25))

    async def add_xp(self, message, xp_gained: int):
        """Add XP with buffering for better performance"""
        async with self._buffer_lock:
            self._xp_buffer.append({
                'user_id': message.author.id,
                'guild_id': message.guild.id,
                'xp_gained': xp_gained,
                'timestamp': message.created_at.isoformat()
            })

        # Force flush if buffer is getting too large
        if len(self._xp_buffer) >= 100:
            await self._flush_xp_buffer_to_db()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Enhanced message handler with better XP gains"""
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        if self.is_on_cooldown(guild_id, user_id):
            return

        try:
            min_xp, max_xp = self.get_xp_range(guild_id)
            xp_gained = random.randint(min_xp, max_xp)
            await self.add_xp(message, xp_gained)
            self.add_cooldown(guild_id, user_id, self.get_cooldown(guild_id))
        except Exception as e:
            logger.error(f"Error in XP processing: {e}")

    async def _get_user_rank(self, guild_id: int, level: int, xp: int) -> int:
        async with self.db._lock:
            conn = await self.db.get_connection()
            cursor = await conn.execute("""
                SELECT COUNT(*) + 1 FROM xp_data 
                WHERE guild_id = ? AND (
                    level > ? OR (level = ? AND xp > ?)
                )
            """, (guild_id, level, level, xp))
            result = await cursor.fetchone()
            await cursor.close()
            return result[0] if result else 1

    async def _get_level_role(self, guild_id: int, level: int) -> int:
        async with self.db._lock:
            conn = await self.db.get_connection()
            cursor = await conn.execute("""
                SELECT role_id FROM level_roles 
                WHERE guild_id = ? AND level = ?
            """, (guild_id, level))
            result = await cursor.fetchone()
            await cursor.close()
            return result[0] if result else None

    @app_commands.command(name="level", description="Check your current level and XP")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        """Display level and XP information for a user"""
        try:
            target = member or interaction.user
            
            result = await self.db.fetchrow("""
                SELECT level, xp, messages, last_message 
                FROM xp_data 
                WHERE user_id = ? AND guild_id = ?
            """, (target.id, interaction.guild_id))

            if not result:
                await interaction.response.send_message(
                    embed=self.ui.info_embed(
                        "No XP",
                        f"{target.mention} hasn't earned any XP yet!",
                        "Leveling"
                    ),
                    ephemeral=True
                )
                return

            level, xp, messages, last_message = result
            xp_needed = self.calculate_xp_for_level(level)
            rank = await self._get_user_rank(interaction.guild_id, level, xp)

            embed = self.ui.info_embed(
                f"Level Stats: {target.display_name}",
                "",
                "Leveling"
            )
            
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)

            stats = (
                f"Level: `{level}`\n"
                f"Rank: `#{rank}`\n"
                f"Messages: `{messages:,}`\n"
                f"Total XP: `{xp:,}`"
            )
            self.ui.add_field_if_exists(
                embed,
                "📈 Statistics", 
                stats,
                False
            )

            self.ui.add_field_if_exists(
                embed,
                "📊 Progress",
                self.generate_progress_bar(xp, xp_needed),
                False
            )

            if last_message:
                last_active = self.format_relative_time(
                    datetime.fromisoformat(last_message.replace('Z', '+00:00'))
                )
                self.ui.add_field_if_exists(
                    embed,
                    "⏰ Last Active",
                    f"`{last_active}`",
                    False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level info viewed for {target} in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing level info: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching level information.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="leaderboard", description="View the XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Display the server's XP leaderboard"""
        try:
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        user_id,
                        level,
                        xp,
                        messages
                    FROM xp_data 
                    WHERE guild_id = ?
                    ORDER BY level DESC, xp DESC
                    LIMIT 10
                """, (interaction.guild_id,))
                leaders = await cur.fetchall()

            if not leaders:
                await interaction.response.send_message(
                    embed=self.ui.info_embed(
                        "No Data",
                        "No XP data found for this server!",
                        "Leveling"
                    ),
                    ephemeral=True
                )
                return

            embed = self.ui.info_embed(
                "XP Leaderboard",
                f"Top members in {interaction.guild.name}",
                "Leveling"
            )

            for idx, (user_id, level, xp, messages) in enumerate(leaders, 1):
                member = interaction.guild.get_member(user_id)
                if not member:
                    continue

                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, "🏅")
                stats = (
                    f"Level: {level} • "
                    f"XP: {xp:,} • "
                    f"Messages: {messages:,}"
                )
                self.ui.add_field_if_exists(
                    embed,
                    f"{medal} #{idx} {member.display_name}",
                    f"```{stats}```",
                    False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Leaderboard viewed in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching the leaderboard.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="setlevelrole")
    @app_commands.default_permissions(administrator=True)
    async def setlevelrole(self, interaction: discord.Interaction, level: int, role: discord.Role):
        try:
            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Permission Error",
                        "I cannot manage roles higher than my highest role!",
                        "Leveling"
                    ),
                    ephemeral=True
                )
                return

            async with self.db.transaction():
                await self.db.execute("""
                    INSERT OR REPLACE INTO level_roles (guild_id, level, role_id)
                    VALUES (?, ?, ?)
                """, (interaction.guild_id, level, role.id))

            embed = self.ui.success_embed(
                "Level Role Set",
                f"Members will receive {role.mention} at Level {level}",
                "Leveling"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level role set in {interaction.guild}: {role.name} at level {level}")
        except Exception as e:
            logger.error(f"Error setting level role: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Setup Error",
                    "An error occurred while setting the level role.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="deletelevelrole")
    async def deletelevelrole(self, interaction: discord.Interaction, level: int):
        try:
            async with self.db.cursor() as cur:
                await cur.execute("""
                    DELETE FROM level_roles 
                    WHERE guild_id = ? AND level = ?
                """, (interaction.guild_id, level))

            embed = self.ui.success_embed(
                "Level Role Removed",
                f"Role assignment for Level {level} has been removed",
                "Leveling"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level role removed in {interaction.guild} for level {level}")
        except Exception as e:
            logger.error(f"Error removing level role: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Removal Error",
                    "An error occurred while removing the level role.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="setcooldown")
    async def setcooldown(self, interaction: discord.Interaction, time: Literal["15s", "30s", "1m", "2m", "5m"]):
        try:
            time_map = {"15s": 15, "30s": 30, "1m": 60, "2m": 120, "5m": 300}
            cooldown = time_map[time]

            async with self.db.cursor() as cur:
                await cur.execute("""
                    UPDATE leveling_settings 
                    SET xp_cooldown = ? 
                    WHERE guild_id = ?
                """, (cooldown, interaction.guild_id))

            self.cooldown_settings[interaction.guild_id] = cooldown

            embed = self.ui.success_embed(
                "Cooldown Updated",
                f"XP cooldown set to {time}",
                "Leveling"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"XP cooldown updated in {interaction.guild}: {time}")
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Update Error",
                    "An error occurred while updating the cooldown.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="setxprange")
    async def setxprange(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        try:
            if not (1 <= min_xp <= max_xp <= 100):
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Invalid Range",
                        "Invalid XP range! Min must be at least 1, max cannot exceed 100, and min must be less than max.",
                        "Leveling"
                    ),
                    ephemeral=True
                )
                return

            async with self.db.cursor() as cur:
                await cur.execute("""
                    UPDATE leveling_settings 
                    SET min_xp = ?, max_xp = ? 
                    WHERE guild_id = ?
                """, (min_xp, max_xp, interaction.guild_id))

            self.xp_ranges[interaction.guild_id] = (min_xp, max_xp)

            embed = self.ui.success_embed(
                "XP Range Updated",
                f"Message XP range set to {min_xp}-{max_xp}",
                "Leveling"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"XP range updated in {interaction.guild}: {min_xp}-{max_xp}")
        except Exception as e:
            logger.error(f"Error setting XP range: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Update Error",
                    "An error occurred while updating the XP range.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="levelconfig")
    async def levelconfig(self, interaction: discord.Interaction):
        try:
            async with self.db.cursor() as cur:
                # Get leveling settings
                await cur.execute("""
                    SELECT * FROM leveling_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))
                settings = await cur.fetchone()

                # Get level roles
                await cur.execute("""
                    SELECT level, role_id 
                    FROM level_roles 
                    WHERE guild_id = ?
                    ORDER BY level ASC
                """, (interaction.guild_id,))
                roles = await cur.fetchall()

            if not settings:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Not Found",
                        "No leveling configuration found!",
                        "Leveling"
                    ),
                    ephemeral=True
                )
                return

            embed = self.ui.info_embed(
                "Leveling System Configuration",
                "Current leveling system settings",
                "Leveling"
            )

            # XP Settings
            xp_settings = (
                f"XP Range: {settings['min_xp']}-{settings['max_xp']}\n"
                f"Cooldown: {settings['xp_cooldown']}s\n"
                f"Multiplier: {settings['xp_multiplier']}x"
            )
            self.ui.add_field_if_exists(
                embed,
                "📊 XP Settings",
                f"```{xp_settings}```",
                False
            )

            # Voice XP (if enabled)
            if settings['voice_xp_enabled']:
                voice_settings = (
                    f"Enabled: Yes\n"
                    f"XP per minute: {settings['voice_xp_per_minute']}"
                )
                self.ui.add_field_if_exists(
                    embed,
                    "🎤 Voice XP",
                    f"```{voice_settings}```",
                    False
                )

            # Level Roles
            if roles:
                role_text = []
                for level, role_id in roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_text.append(f"Level {level}: {role.name}")
                if role_text:
                    self.ui.add_field_if_exists(
                        embed,
                        "🎭 Level Roles",
                        f"```{chr(10).join(role_text)}```",
                        False
                    )

            # Additional Settings
            other_settings = []
            if settings['level_up_channel_id']:
                channel = interaction.guild.get_channel(settings['level_up_channel_id'])
                if channel:
                    other_settings.append(f"Level Up Channel: #{channel.name}")
            if settings['stack_roles']:
                other_settings.append("Role Stacking: Enabled")
            if settings['ignore_channels']:
                other_settings.append(f"Ignored Channels: {len(settings['ignore_channels'].split(','))}")

            if other_settings:
                self.ui.add_field_if_exists(
                    embed,
                    "🔧 Other Settings",
                    f"```{chr(10).join(other_settings)}```",
                    False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level config viewed in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing level config: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching the configuration.",
                    "Leveling"
                ),
                ephemeral=True
            )

    @app_commands.command(name="resetlevels")
    @app_commands.default_permissions(administrator=True)
    async def resetlevels(self, interaction: discord.Interaction):
        """Reset all levels in the server"""
        try:
            await interaction.response.defer()

            async with self.db.transaction():
                # Delete all XP data for the guild
                await self.db.execute("""
                    DELETE FROM xp_data 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

            embed = self.ui.success_embed(
                "Levels Reset",
                "All levels and XP have been reset for this server.",
                "Leveling"
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"Levels reset in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error resetting levels: {e}")
            await interaction.followup.send(
                embed=self.ui.error_embed(
                    "Reset Error",
                    "An error occurred while resetting levels.",
                    "Leveling"
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Leveling(bot))
