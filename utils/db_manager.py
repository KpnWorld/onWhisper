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
            CREATE TABLE IF NOT EXISTS guild_config (                guild_id INTEGER PRIMARY KEY,
                xp_rate INTEGER DEFAULT 15,
                xp_cooldown INTEGER DEFAULT 60,
                whisper_enabled BOOLEAN DEFAULT 1,
                logging_enabled BOOLEAN DEFAULT 1,
                mod_role_id INTEGER,
                admin_role_id INTEGER,
                staff_role_id INTEGER,
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
            """,
            # Color roles
            """
            CREATE TABLE IF NOT EXISTS color_roles (
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id),
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

    @db_transaction()
    async def close_whisper(self, thread_id: int) -> bool:
        """Close a whisper thread"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    UPDATE whispers
                    SET closed_at = CURRENT_TIMESTAMP
                    WHERE thread_id = ? AND closed_at IS NULL
                    RETURNING 1
                """, (thread_id,))
                
                result = await cursor.fetchone()
                return bool(result)
                
        except Exception as e:
            logging.error(f"Error closing whisper thread {thread_id}: {str(e)}")
            raise DatabaseError(f"Failed to close whisper: {str(e)}")
            
    @db_transaction()
    async def delete_whisper(self, thread_id: int) -> bool:
        """Delete a whisper thread"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM whispers
                    WHERE thread_id = ?
                    RETURNING 1
                """, (thread_id,))
                
                result = await cursor.fetchone()
                return bool(result)
                
        except Exception as e:
            logging.error(f"Error deleting whisper thread {thread_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete whisper: {str(e)}")
            
    @db_transaction()
    async def get_active_whispers(self, guild_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get active whisper threads for a guild or specific user"""
        try:
            async with self.db.cursor() as cursor:
                query = """
                    SELECT * FROM whispers
                    WHERE guild_id = ? AND closed_at IS NULL
                """
                params = [guild_id]
                
                if user_id is not None:
                    query += " AND user_id = ?"
                    params.append(user_id)
                    
                query += " ORDER BY created_at DESC"
                
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                
                return [{
                    'thread_id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'created_at': row[3],
                    'closed_at': row[4]
                } for row in rows]
                
        except Exception as e:
            logging.error(f"Error getting active whispers in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get active whispers: {str(e)}")

    @db_transaction()
    async def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get guild configuration"""
        cache_key = f"guild_config_{guild_id}"
        
        try:
            # Check cache first
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data

            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM guild_config 
                    WHERE guild_id = ?
                """, (guild_id,))
                
                result = await cursor.fetchone()
                if result:
                    # Convert to dict
                    columns = [description[0] for description in cursor.description]
                    config = dict(zip(columns, result))
                    
                    # Cache the result
                    self.cache.set(cache_key, config)
                    return config
                    
                # If no config exists, create default config
                await cursor.execute("""
                    INSERT OR IGNORE INTO guild_config (guild_id)
                    VALUES (?)
                """, (guild_id,))
                
                # Get the default config
                await cursor.execute("""
                    SELECT * FROM guild_config 
                    WHERE guild_id = ?
                """, (guild_id,))
                
                result = await cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    config = dict(zip(columns, result))
                    self.cache.set(cache_key, config)
                    return config
                
                return None

        except Exception as e:
            logging.error(f"Error getting guild config for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get guild config: {str(e)}")

    @db_transaction()
    async def update_guild_config(self, guild_id: int, config_updates: Dict[str, Any]) -> bool:
        """Update guild configuration"""
        cache_key = f"guild_config_{guild_id}"
        
        try:
            # Prepare the update query
            update_fields = []
            params = []
            for key, value in config_updates.items():
                update_fields.append(f"{key} = ?")
                params.append(value)
            params.append(guild_id)

            async with self.db.cursor() as cursor:
                await cursor.execute(f"""
                    UPDATE guild_config 
                    SET {', '.join(update_fields)},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                """, params)
                
                # Invalidate cache
                self.cache.invalidate(cache_key)
                return True

        except Exception as e:
            logging.error(f"Error updating guild config for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to update guild config: {str(e)}")

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

    @db_transaction()
    async def get_reaction_role(self, guild_id: int, message_id: int, emoji: str) -> Optional[int]:
        """Get role ID for a reaction role binding"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT role_id FROM reaction_roles
                    WHERE message_id = ? AND emoji = ?
                """, (message_id, emoji))
                
                result = await cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logging.error(f"Error getting reaction role for message {message_id} emoji {emoji}: {str(e)}")
            raise DatabaseError(f"Failed to get reaction role: {str(e)}")

    @db_transaction()
    async def set_level_role(self, guild_id: int, level: int, role_id: Optional[int]) -> bool:
        """Set or remove a level-based role reward"""
        try:
            async with self.db.cursor() as cursor:
                if role_id is None:
                    # Remove the level role
                    await cursor.execute("""
                        DELETE FROM level_roles
                        WHERE guild_id = ? AND level = ?
                    """, (guild_id, level))
                else:
                    # Set the level role
                    await cursor.execute("""
                        INSERT OR REPLACE INTO level_roles (guild_id, level, role_id)
                        VALUES (?, ?, ?)
                    """, (guild_id, level, role_id))
                return True
        except Exception as e:
            logging.error(f"Error setting level role for level {level} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to set level role: {str(e)}")
            
    @db_transaction()
    async def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        """Get all level-based role rewards for a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT level, role_id FROM level_roles
                    WHERE guild_id = ?
                    ORDER BY level ASC
                """, (guild_id,))
                
                return {row[0]: row[1] for row in await cursor.fetchall()}
        except Exception as e:
            logging.error(f"Error getting level roles for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get level roles: {str(e)}")

    @db_transaction()
    async def get_mod_actions(self, guild_id: int, user_id: Optional[int] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get moderation actions for a guild or specific user"""
        try:
            async with self.db.cursor() as cursor:
                query = """
                    SELECT * FROM mod_actions
                    WHERE guild_id = ?
                """
                params = [guild_id]
                
                if user_id is not None:
                    query += " AND user_id = ?"
                    params.append(user_id)
                    
                if active_only:
                    query += " AND active = 1"
                    
                query += " ORDER BY created_at DESC"
                
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                
                return [{
                    'action_id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'moderator_id': row[3],
                    'action_type': row[4],
                    'reason': row[5],
                    'created_at': row[6],
                    'expires_at': row[7],
                    'active': bool(row[8])
                } for row in rows]
                
        except Exception as e:
            logging.error(f"Error getting mod actions for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get mod actions: {str(e)}")
            
    @db_transaction()
    async def clear_mod_actions(self, guild_id: int, user_id: int) -> int:
        """Clear all moderation actions for a user in a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    UPDATE mod_actions
                    SET active = 0
                    WHERE guild_id = ? AND user_id = ? AND active = 1
                    RETURNING changes()
                """, (guild_id, user_id))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logging.error(f"Error clearing mod actions for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to clear mod actions: {str(e)}")
            
    @db_transaction()
    async def get_warnings(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all warnings for a user in a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM mod_actions
                    WHERE guild_id = ? AND user_id = ? AND action_type = 'warn'
                    ORDER BY created_at DESC
                """, (guild_id, user_id))
                
                rows = await cursor.fetchall()
                return [{
                    'action_id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'moderator_id': row[3],
                    'reason': row[5],
                    'created_at': row[6],
                    'active': bool(row[8])
                } for row in rows]
                
        except Exception as e:
            logging.error(f"Error getting warnings for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get warnings: {str(e)}")
            
    @db_transaction()
    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        """Clear all warnings for a user in a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    UPDATE mod_actions
                    SET active = 0
                    WHERE guild_id = ? AND user_id = ? AND action_type = 'warn' AND active = 1
                    RETURNING changes()
                """, (guild_id, user_id))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logging.error(f"Error clearing warnings for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to clear warnings: {str(e)}")

    @db_transaction()
    async def get_user_xp(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user XP data for a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM user_levels
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                
                result = await cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'guild_id': result[1],
                        'xp': result[2],
                        'level': result[3],
                        'last_xp_gain': result[4]
                    }
                return None
                
        except Exception as e:
            logging.error(f"Error getting user XP for {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get user XP: {str(e)}")
            
    @db_transaction()
    async def get_leaderboard(self, guild_id: int, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """Get XP leaderboard for a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM user_levels
                    WHERE guild_id = ?
                    ORDER BY xp DESC
                    LIMIT ? OFFSET ?
                """, (guild_id, limit, offset))
                
                rows = await cursor.fetchall()
                return [{
                    'user_id': row[0],
                    'guild_id': row[1],
                    'xp': row[2],
                    'level': row[3],
                    'last_xp_gain': row[4]
                } for row in rows]
                
        except Exception as e:
            logging.error(f"Error getting leaderboard for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get leaderboard: {str(e)}")

    @db_transaction()
    async def add_mod_action(self, guild_id: int, user_id: int, moderator_id: int, action_type: str, reason: str, expires_at: Optional[datetime] = None) -> bool:
        """Add a moderation action to the database"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO mod_actions (guild_id, user_id, moderator_id, action_type, reason, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (guild_id, user_id, moderator_id, action_type, reason, expires_at))
                return True
                
        except Exception as e:
            logging.error(f"Error adding mod action for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to add mod action: {str(e)}")
            
    @db_transaction()
    async def get_logging_channel(self, guild_id: int, log_type: str) -> Optional[int]:
        """Get logging channel ID for a specific log type"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT channel_id FROM logging_channels
                    WHERE guild_id = ? AND channel_type = ? AND enabled = 1
                """, (guild_id, log_type))
                
                result = await cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            logging.error(f"Error getting logging channel for {log_type} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get logging channel: {str(e)}")
            
    @db_transaction()
    async def set_logging_channel(self, guild_id: int, log_type: str, channel_id: Optional[int]) -> bool:
        """Set or disable a logging channel"""
        try:
            async with self.db.cursor() as cursor:
                if channel_id is None:
                    await cursor.execute("""
                        UPDATE logging_channels
                        SET enabled = 0
                        WHERE guild_id = ? AND channel_type = ?
                    """, (guild_id, log_type))
                else:
                    await cursor.execute("""
                        INSERT OR REPLACE INTO logging_channels (guild_id, channel_type, channel_id, enabled)
                        VALUES (?, ?, ?, 1)
                    """, (guild_id, log_type, channel_id))
                return True
                
        except Exception as e:
            logging.error(f"Error setting logging channel for {log_type} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to set logging channel: {str(e)}")

    @db_transaction()
    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> bool:
        """Add a reaction role binding"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO reaction_roles
                    (guild_id, message_id, emoji, role_id)
                    VALUES (?, ?, ?, ?)
                """, (guild_id, message_id, emoji, role_id))
                return True
                
        except Exception as e:
            logging.error(f"Error adding reaction role for message {message_id}: {str(e)}")
            raise DatabaseError(f"Failed to add reaction role: {str(e)}")
            
    @db_transaction()
    async def remove_reaction_roles(self, guild_id: int, message_id: int) -> bool:
        """Remove all reaction roles from a message"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM reaction_roles
                    WHERE guild_id = ? AND message_id = ?
                """, (guild_id, message_id))
                return True
                
        except Exception as e:
            logging.error(f"Error removing reaction roles for message {message_id}: {str(e)}")
            raise DatabaseError(f"Failed to remove reaction roles: {str(e)}")
            
    @db_transaction()
    async def get_reaction_roles(self, guild_id: int) -> Dict[int, Dict[str, int]]:
        """Get all reaction role bindings for a guild"""
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT message_id, emoji, role_id
                    FROM reaction_roles
                    WHERE guild_id = ?
                """, (guild_id,))
                
                result = {}
                for row in await cursor.fetchall():
                    message_id = row[0]
                    if message_id not in result:
                        result[message_id] = {}
                    result[message_id][row[1]] = row[2]
                return result
                
        except Exception as e:
            logging.error(f"Error getting reaction roles for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get reaction roles: {str(e)}")
              
    @db_transaction()
    async def get_user_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        """Get user's color role for a guild"""
        cache_key = f"color_role_{guild_id}_{user_id}"
        
        try:
            # Check cache first
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data['role_id']

            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT role_id FROM color_roles
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                
                result = await cursor.fetchone()
                if result:
                    # Update cache
                    self.cache.set(cache_key, {'role_id': result[0]})
                return result[0] if result else None
                
        except Exception as e:
            logging.error(f"Error getting color role for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get color role: {str(e)}")

    @db_transaction()
    async def set_user_color_role(self, guild_id: int, user_id: int, role_id: Optional[int]) -> bool:
        """Set or remove a user's color role"""
        cache_key = f"color_role_{guild_id}_{user_id}"
        
        try:
            async with self.db.cursor() as cursor:
                # First, remove any existing color role
                await cursor.execute("""
                    DELETE FROM color_roles
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                
                if role_id is not None:
                    # Verify this is a valid color role
                    await cursor.execute("""
                        SELECT 1 FROM color_roles 
                        WHERE guild_id = ? AND user_id = 0 AND role_id = ?
                    """, (guild_id, role_id))
                    
                    if await cursor.fetchone():
                        # Set the new color role
                        await cursor.execute("""
                            INSERT INTO color_roles (guild_id, user_id, role_id)
                            VALUES (?, ?, ?)
                        """, (guild_id, user_id, role_id))
                    else:
                        raise DatabaseError(f"Invalid color role ID: {role_id}")
                
                # Invalidate cache
                self.cache.invalidate(cache_key)
                return True
                
        except Exception as e:
            logging.error(f"Error setting color role for user {user_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to set color role: {str(e)}")

    @db_transaction()
    async def get_color_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all available color roles for a guild with usage counts"""
        cache_key = f"color_roles_{guild_id}"
        
        try:
            # Check cache first
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data['roles']

            async with self.db.cursor() as cursor:
                # Get all color roles and their usage counts
                await cursor.execute("""
                    SELECT cr.role_id,
                           (SELECT COUNT(*) 
                            FROM color_roles u 
                            WHERE u.guild_id = cr.guild_id 
                            AND u.role_id = cr.role_id 
                            AND u.user_id != 0) as user_count
                    FROM color_roles cr
                    WHERE cr.guild_id = ? AND cr.user_id = 0
                    ORDER BY user_count DESC, role_id ASC
                """, (guild_id,))
                
                roles = [{
                    'role_id': row[0],
                    'user_count': row[1]
                } for row in await cursor.fetchall()]
                
                # Cache the result
                self.cache.set(cache_key, {'roles': roles})
                return roles
                
        except Exception as e:
            logging.error(f"Error getting color roles for guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to get color roles: {str(e)}")

    @db_transaction()
    async def add_color_role(self, guild_id: int, role_id: int) -> bool:
        """Add a role as an available color role"""
        cache_key = f"color_roles_{guild_id}"
        
        try:
            async with self.db.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR IGNORE INTO color_roles (guild_id, user_id, role_id)
                    VALUES (?, 0, ?)
                """, (guild_id, role_id))
                
                # Invalidate cache
                self.cache.invalidate(cache_key)
                return True
                
        except Exception as e:
            logging.error(f"Error adding color role {role_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to add color role: {str(e)}")

    @db_transaction()
    async def remove_color_role(self, guild_id: int, role_id: int) -> bool:
        """Remove a role from available color roles and unassign it from users"""
        cache_key = f"color_roles_{guild_id}"
        
        try:
            async with self.db.cursor() as cursor:
                # Remove role from available color roles and user assignments
                await cursor.execute("""
                    DELETE FROM color_roles
                    WHERE guild_id = ? AND role_id = ?
                """, (guild_id, role_id))
                
                # Invalidate cache for the guild's color roles
                self.cache.invalidate(cache_key)
                
                # Invalidate cache for all users who had this role
                await cursor.execute("""
                    SELECT user_id FROM color_roles
                    WHERE guild_id = ? AND role_id = ?
                """, (guild_id, role_id))
                
                for row in await cursor.fetchall():
                    self.cache.invalidate(f"color_role_{guild_id}_{row[0]}")
                
                return True
                
        except Exception as e:
            logging.error(f"Error removing color role {role_id} in guild {guild_id}: {str(e)}")
            raise DatabaseError(f"Failed to remove color role: {str(e)}")
