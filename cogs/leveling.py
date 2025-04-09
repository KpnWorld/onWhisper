import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import logging
from typing import Literal, Dict
from datetime import datetime, timedelta

# Initialize logger
logger = logging.getLogger(__name__)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use bot's database instance instead of creating new one
        self.xp_cooldowns: Dict[int, Dict[int, datetime]] = {}
        self.cooldown_settings = {}
        self.xp_ranges = {}
        self._cleanup_task = bot.loop.create_task(self._cleanup_cooldowns())
        bot.loop.create_task(self._init_db())
        logger.info("Leveling cog initialized")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._cleanup_task:
            self._cleanup_task.cancel()

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
        """Enhanced XP system with message tracking and race condition prevention"""
        user_id = message.author.id
        guild_id = message.guild.id
        timestamp = message.created_at.isoformat()

        async with self.db._lock:
            conn = await self.db.get_connection()
            await conn.execute("BEGIN EXCLUSIVE")
            try:
                # Get current XP and level atomically
                cursor = await conn.execute("""
                    SELECT xp, level 
                    FROM xp_data 
                    WHERE user_id=? AND guild_id=?
                    FOR UPDATE
                """, (user_id, guild_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    current_xp, current_level = result
                    new_xp = current_xp + xp_gained
                else:
                    current_level = 1
                    new_xp = xp_gained

                # Calculate level ups
                level_changed = False
                while True:
                    xp_needed = self.calculate_xp_for_level(current_level)
                    if new_xp >= xp_needed:
                        current_level += 1
                        new_xp -= xp_needed
                        level_changed = True
                    else:
                        break

                # Update with new values
                await conn.execute("""
                    INSERT INTO xp_data (user_id, guild_id, xp, level, messages, last_message)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET
                        xp = ?,
                        level = ?,
                        messages = messages + 1,
                        last_message = ?
                """, (user_id, guild_id, new_xp, current_level, timestamp,
                      new_xp, current_level, timestamp))

                await conn.commit()
                return (current_level, new_xp, self.calculate_xp_for_level(current_level)) if level_changed else None

            except Exception as e:
                await conn.rollback()
                logger.error(f"Error in add_xp: {e}")
                raise

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
            level_info = await self.add_xp(message, xp_gained)

            if level_info:
                new_level, current_xp, xp_needed = level_info
                # Handle level up
                role_id = await self._get_level_role(guild_id, new_level)
                if role_id:
                    role = message.guild.get_role(role_id)
                    if role:
                        await message.author.add_roles(role)

                # Send level up message
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} reached Level {new_level}!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Progress",
                    value=self.generate_progress_bar(current_xp, xp_needed),
                    inline=False
                )
                await message.channel.send(embed=embed)

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
                    f"{target.mention} hasn't earned any XP yet!",
                    ephemeral=True
                )
                return

            level, xp, messages, last_message = result
            xp_needed = self.calculate_xp_for_level(level)
            rank = await self._get_user_rank(interaction.guild_id, level, xp)

            embed = discord.Embed(
                title=f"📊 Level Stats: {target.display_name}",
                color=target.color if target.color != discord.Color.default() else discord.Color.blue()
            )
            
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)

            # Core Stats
            stats = (
                f"Level: `{level}`\n"
                f"Rank: `#{rank}`\n"
                f"Messages: `{messages:,}`\n"
                f"Total XP: `{xp:,}`"
            )
            embed.add_field(
                name="📈 Statistics", 
                value=stats,
                inline=False
            )

            # Progress Bar
            embed.add_field(
                name="📊 Progress",
                value=self.generate_progress_bar(xp, xp_needed),
                inline=False
            )

            # Activity Info
            if last_message:
                last_active = self.format_relative_time(
                    datetime.fromisoformat(last_message.replace('Z', '+00:00'))
                )
                embed.add_field(
                    name="⏰ Last Active",
                    value=f"`{last_active}`",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level info viewed for {target} in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing level info: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching level information.",
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
                    "No XP data found for this server!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🏆 XP Leaderboard",
                description=f"Top members in {interaction.guild.name}",
                color=discord.Color.gold()
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
                embed.add_field(
                    name=f"{medal} #{idx} {member.display_name}",
                    value=f"```{stats}```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Leaderboard viewed in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching the leaderboard.",
                ephemeral=True
            )

    @app_commands.command(name="setlevelrole", description="Set a role to be assigned at a specific level (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def setlevelrole(self, interaction: discord.Interaction, level: int, role: discord.Role):
        try:
            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message(
                    "❌ I cannot manage roles higher than my highest role!",
                    ephemeral=True
                )
                return

            async with self.db.cursor() as cur:
                await cur.execute("""
                    INSERT OR REPLACE INTO level_roles (guild_id, level, role_id)
                    VALUES (?, ?, ?)
                """, (interaction.guild_id, level, role.id))

            embed = discord.Embed(
                title="✅ Level Role Set",
                description=f"Members will receive {role.mention} at Level {level}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Administrative Command • Leveling System")

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level role set in {interaction.guild}: {role.name} at level {level}")
        except Exception as e:
            logger.error(f"Error setting level role: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the level role.",
                ephemeral=True
            )

    @app_commands.command(name="deletelevelrole", description="Remove a level role assignment (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def deletelevelrole(self, interaction: discord.Interaction, level: int):
        try:
            async with self.db.cursor() as cur:
                await cur.execute("""
                    DELETE FROM level_roles 
                    WHERE guild_id = ? AND level = ?
                """, (interaction.guild_id, level))

            embed = discord.Embed(
                title="✅ Level Role Removed",
                description=f"Role assignment for Level {level} has been removed",
                color=discord.Color.green()
            )
            embed.set_footer(text="Administrative Command • Leveling System")

            await interaction.response.send_message(embed=embed)
            logger.info(f"Level role removed in {interaction.guild} for level {level}")
        except Exception as e:
            logger.error(f"Error removing level role: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while removing the level role.",
                ephemeral=True
            )

    @app_commands.command(name="setcooldown", description="Set the XP gain cooldown time")
    @app_commands.default_permissions(administrator=True)
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

            embed = discord.Embed(
                title="⚙️ Cooldown Updated",
                description=f"XP cooldown set to {time}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Administrative Command • Leveling System")

            await interaction.response.send_message(embed=embed)
            logger.info(f"XP cooldown updated in {interaction.guild}: {time}")
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while updating the cooldown.",
                ephemeral=True
            )

    @app_commands.command(name="setxprange", description="Set the XP range for message rewards")
    @app_commands.default_permissions(administrator=True)
    async def setxprange(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        try:
            if not (1 <= min_xp <= max_xp <= 100):
                await interaction.response.send_message(
                    "❌ Invalid XP range! Min must be at least 1, max cannot exceed 100, and min must be less than max.",
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

            embed = discord.Embed(
                title="⚙️ XP Range Updated",
                description=f"Message XP range set to {min_xp}-{max_xp}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Administrative Command • Leveling System")

            await interaction.response.send_message(embed=embed)
            logger.info(f"XP range updated in {interaction.guild}: {min_xp}-{max_xp}")
        except Exception as e:
            logger.error(f"Error setting XP range: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while updating the XP range.",
                ephemeral=True
            )

    @app_commands.command(name="levelconfig", description="Show current leveling system configuration")
    @app_commands.default_permissions(administrator=True)
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
                    "❌ No leveling configuration found!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="⚙️ Leveling System Configuration",
                color=discord.Color.blue()
            )

            # XP Settings
            xp_settings = (
                f"XP Range: {settings['min_xp']}-{settings['max_xp']}\n"
                f"Cooldown: {settings['xp_cooldown']}s\n"
                f"Multiplier: {settings['xp_multiplier']}x"
            )
            embed.add_field(
                name="📊 XP Settings",
                value=f"```{xp_settings}```",
                inline=False
            )

            # Voice XP (if enabled)
            if settings['voice_xp_enabled']:
                voice_settings = (
                    f"Enabled: Yes\n"
                    f"XP per minute: {settings['voice_xp_per_minute']}"
                )
                embed.add_field(
                    name="🎤 Voice XP",
                    value=f"```{voice_settings}```",
                    inline=False
                )

            # Level Roles
            if roles:
                role_text = []
                for level, role_id in roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_text.append(f"Level {level}: {role.name}")
                if role_text:
                    embed.add_field(
                        name="🎭 Level Roles",
                        value=f"```{chr(10).join(role_text)}```",
                        inline=False
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
                embed.add_field(
                    name="🔧 Other Settings",
                    value=f"```{chr(10).join(other_settings)}```",
                    inline=False
                )

            embed.set_footer(text="Administrative Command • Leveling System")
            await interaction.response.send_message(embed=embed)
            logger.info(f"Level config viewed in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error showing level config: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching the configuration.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Leveling(bot))
