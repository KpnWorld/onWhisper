import aiosqlite
import asyncio
from datetime import datetime, timedelta
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps
import traceback

class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass

class DBCache:
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            item = self.cache[key]
            if datetime.now().timestamp() - item['timestamp'] < self.ttl:
                return item['value']
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        if len(self.cache) >= self.max_size:
            # Remove oldest items
            oldest = sorted(self.cache.items(), key=lambda x: x[1]['timestamp'])[0][0]
            del self.cache[oldest]
        
        self.cache[key] = {
            'value': value,
            'timestamp': datetime.now().timestamp()
        }

    def invalidate(self, key: str):
        if key in self.cache:
            del self.cache[key]

def db_transaction():
    """Decorator to handle database transactions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                async with self.db.execute('BEGIN') as cursor:
                    result = await func(self, *args, **kwargs)
                    await self.db.commit()
                    return result
            except Exception as e:
                await self.db.rollback()
                logging.error(f"Database transaction failed in {func.__name__}: {str(e)}\n{traceback.format_exc()}")
                raise DatabaseError(f"Database operation failed: {str(e)}")
        return wrapper
    return decorator

class DBManager:
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "bot.db"
        self.db = None
        self._ready = asyncio.Event()
        self.cache = DBCache()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('db.log'),
                logging.StreamHandler()
            ]
        )

    async def initialize(self):
        """Initialize the database connection and create tables"""
        try:
            self.db = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            await self._create_indexes()
            self._ready.set()
            return True
        except Exception as e:
            logging.error(f"Database initialization failed: {str(e)}\n{traceback.format_exc()}")
            return False

    async def close(self):
        """Close the database connection"""
        if self.db:
            await self.db.close()
            self.db = None
            self._ready.clear()

    async def check_connection(self):
        """Check if database connection is alive"""
        if not self.db:
            return False
        try:
            await self.db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def _create_tables(self):
        """Create all necessary database tables"""
        queries = [
            # Guild configuration
            """
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                xp_rate INTEGER DEFAULT 15,
                xp_cooldown INTEGER DEFAULT 60,
                whisper_enabled BOOLEAN DEFAULT 1,
                logging_enabled BOOLEAN DEFAULT 1,
                mod_role_id INTEGER,
                admin_role_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # XP and leveling system
            """
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                last_xp_gain TIMESTAMP,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """,
            # Level roles
            """
            CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER,
                level INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, level),
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """,
            # Whisper system
            """
            CREATE TABLE IF NOT EXISTS whispers (
                thread_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """,
            # Logging channels
            """
            CREATE TABLE IF NOT EXISTS logging_channels (
                guild_id INTEGER,
                channel_type TEXT,
                channel_id INTEGER,
                enabled BOOLEAN DEFAULT 1,
                PRIMARY KEY (guild_id, channel_type),
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """,
            # Moderation actions
            """
            CREATE TABLE IF NOT EXISTS mod_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                action_type TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """,
            # Reaction roles
            """
            CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                PRIMARY KEY (message_id, emoji),
                FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
            )
            """
        ]
        
        async with self.db.cursor() as cursor:
            for query in queries:
                await cursor.execute(query)
            await self.db.commit()

    async def _create_indexes(self):
        """Create indexes for frequently queried columns"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_user_levels_user ON user_levels(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_levels_guild ON user_levels(guild_id);",
            "CREATE INDEX IF NOT EXISTS idx_whispers_user ON whispers(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_whispers_guild ON whispers(guild_id);",
            "CREATE INDEX IF NOT EXISTS idx_mod_actions_user ON mod_actions(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_mod_actions_guild ON mod_actions(guild_id);",
            "CREATE INDEX IF NOT EXISTS idx_logging_channels_guild ON logging_channels(guild_id);",
            "CREATE INDEX IF NOT EXISTS idx_reaction_roles_message ON reaction_roles(message_id);"
        ]
        
        async with self.db.cursor() as cursor:
            for index in indexes:
                await cursor.execute(index)
            await self.db.commit()

    @db_transaction()
    async def sync_guilds(self, bot) -> Dict[str, int]:
        """Sync bot guilds with database"""
        success = 0
        failed = 0
        
        async with self.db.cursor() as cursor:
            for guild in bot.guilds:
                try:
                    await cursor.execute(
                        "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)",
                        (guild.id,)
                    )
                    success += 1
                except Exception as e:
                    logging.error(f"Failed to sync guild {guild.id}: {str(e)}")
                    failed += 1
        
        return {"success": success, "failed": failed}

    @db_transaction()
    async def add_xp(self, guild_id: int, user_id: int, xp_amount: int) -> Optional[Dict[str, Any]]:
        """Add XP to a user and handle level ups"""
        cache_key = f"xp_{guild_id}_{user_id}"
        
        try:
            # Check cooldown from cache
            last_xp = self.cache.get(cache_key)
            if last_xp and (datetime.now() - last_xp['timestamp']).total_seconds() < 60:
                return None

            async with self.db.cursor() as cursor:
                # Get current XP and level
                await cursor.execute("""
                    INSERT OR IGNORE INTO user_levels (guild_id, user_id, xp, level, last_xp_gain)
                    VALUES (?, ?, 0, 0, ?)
                """, (guild_id, user_id, datetime.utcnow() - timedelta(minutes=5)))
                
                await cursor.execute("""
                    UPDATE user_levels 
                    SET xp = xp + ?,
                        level = CAST(((xp + ?) / 100) as INT),
                        last_xp_gain = ?
                    WHERE guild_id = ? AND user_id = ?
                    RETURNING level, xp, (level = CAST(((xp - ?) / 100) as INT)) as leveled_up
                """, (xp_amount, xp_amount, datetime.utcnow(), guild_id, user_id, xp_amount))
                
                result = await cursor.fetchone()
                
                if result:
                    current_level, total_xp, leveled_up = result
                    # Update cache
                    self.cache.set(cache_key, {
                        'level': current_level,
                        'xp': total_xp,
                        'timestamp': datetime.now()
                    })
                    return {
                        "level": current_level,
                        "xp": total_xp,
                        "leveled_up": bool(leveled_up)
                    }
                return None
                
        except Exception as e:
            logging.error(f"Error adding XP for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to add XP: {str(e)}")

    @db_transaction()
    async def get_level_info(self, guild_id: int, user_id: int) -> Optional[Tuple[int, int]]:
        """Get user's level information"""
        cache_key = f"xp_{guild_id}_{user_id}"
        
        try:
            # Check cache first
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data['level'], cached_data['xp']

            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT level, xp FROM user_levels
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                result = await cursor.fetchone()
                
                if result:
                    # Update cache
                    self.cache.set(cache_key, {
                        'level': result[0],
                        'xp': result[1],
                        'timestamp': datetime.now()
                    })
                return result
                
        except Exception as e:
            logging.error(f"Error getting level info for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get level info: {str(e)}")

    @db_transaction()
    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int):
        """Create a new whisper thread"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO whispers (guild_id, user_id, thread_id)
                    VALUES (?, ?, ?)
                """, (guild_id, user_id, thread_id))
                
        except Exception as e:
            logging.error(f"Error creating whisper for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to create whisper: {str(e)}")

    async def cleanup_old_data(self):
        """Clean up expired or old data"""
        try:
            async with self.db.cursor() as cursor:
                # Clean up expired mod actions
                await cursor.execute("""
                    UPDATE mod_actions 
                    SET active = 0
                    WHERE expires_at IS NOT NULL 
                    AND expires_at < ? 
                    AND active = 1
                """, (datetime.utcnow(),))
                
                # Clean up old whispers (30 days)
                await cursor.execute("""
                    DELETE FROM whispers
                    WHERE closed_at IS NOT NULL
                    AND closed_at < ?
                """, (datetime.utcnow() - timedelta(days=30),))
                
                # Clean up cache
                current_time = datetime.now().timestamp()
                expired_keys = [
                    k for k, v in self.cache.cache.items()
                    if current_time - v['timestamp'] > self.cache.ttl
                ]
                for key in expired_keys:
                    self.cache.invalidate(key)
                
                await self.db.commit()
                
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")
            await self.db.rollback()
            raise DatabaseError(f"Failed to clean up old data: {str(e)}")