import aiosqlite
import sqlite3
import logging
from datetime import datetime
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class AsyncCursorContextManager:
    def __init__(self, db):
        self.db = db
        self.cursor = None

    async def __aenter__(self):
        conn = await self.db.get_connection()
        self.cursor = await conn.cursor()
        return self.cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            await self.cursor.close()

class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.db_path = os.path.join('db', f'{db_name}.db')
        os.makedirs('db', exist_ok=True)
        self._connection = None
        self._lock = asyncio.Lock()
        
    async def get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            await self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    async def cursor(self):
        """Get a database cursor as an async context manager"""
        return AsyncCursorContextManager(self)

    async def setup_database(self) -> None:
        """Initialize database schema with proper constraints"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executescript("""
                -- Command logging tables
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    command_name TEXT NOT NULL,
                    success BOOLEAN,
                    error TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    args TEXT,
                    context TEXT,
                    execution_time REAL
                );

                CREATE TABLE IF NOT EXISTS command_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    command_name TEXT NOT NULL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT 1,
                    execution_time REAL
                );

                -- Core guild settings
                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prefix TEXT DEFAULT '!',
                    locale TEXT DEFAULT 'en-US',
                    timezone TEXT DEFAULT 'UTC',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Server settings table
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT,
                    goodbye_channel_id INTEGER,
                    goodbye_message TEXT,
                    mod_log_channel_id INTEGER,
                    audit_log_channel_id INTEGER,
                    mute_role_id INTEGER,
                    auto_role_id INTEGER,
                    authorized_roles TEXT,
                    disabled_commands TEXT,
                    auto_mod_enabled BOOLEAN DEFAULT 0,
                    max_mentions INTEGER DEFAULT 5,
                    max_links INTEGER DEFAULT 3,
                    max_attachments INTEGER DEFAULT 5,
                    filters_enabled BOOLEAN DEFAULT 0,
                    filtered_words TEXT,
                    caps_threshold INTEGER DEFAULT 70,
                    spam_threshold INTEGER DEFAULT 5,
                    raid_mode_enabled BOOLEAN DEFAULT 0,
                    verification_level INTEGER DEFAULT 0,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Create index for server settings
                CREATE INDEX IF NOT EXISTS idx_server_settings_guild ON server_settings(guild_id);

                -- Guild metrics tracking
                CREATE TABLE IF NOT EXISTS guild_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    member_count INTEGER,
                    active_users INTEGER,
                    message_count INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Leveling System Tables
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
                );

                CREATE TABLE IF NOT EXISTS xp_data (
                    user_id INTEGER,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    messages INTEGER DEFAULT 0,
                    last_message TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id),
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    remove_lower BOOLEAN DEFAULT 0,
                    temporary BOOLEAN DEFAULT 0,
                    duration INTEGER,
                    PRIMARY KEY (guild_id, level),
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER,
                    guild_id INTEGER,
                    notifications_enabled BOOLEAN DEFAULT 1,
                    private_levels BOOLEAN DEFAULT 0,
                    level_dms BOOLEAN DEFAULT 0,
                    custom_color TEXT,
                    custom_background TEXT,
                    PRIMARY KEY (user_id, guild_id),
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_command_logs_guild ON command_logs(guild_id);
                CREATE INDEX IF NOT EXISTS idx_command_stats_guild ON command_stats(guild_id);
                CREATE INDEX IF NOT EXISTS idx_metrics_guild_time ON guild_metrics(guild_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_xp_data_guild ON xp_data(guild_id);
                CREATE INDEX IF NOT EXISTS idx_xp_data_level ON xp_data(level DESC);
                CREATE INDEX IF NOT EXISTS idx_level_roles_guild ON level_roles(guild_id);
                CREATE INDEX IF NOT EXISTS idx_user_settings_guild ON user_settings(guild_id);
            """)
            await conn.commit()

    async def ensure_guild_exists(self, guild_id: int, guild_name: str = None) -> None:
        """Ensure guild exists with all required settings"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("BEGIN")
            try:
                await conn.execute("""
                    INSERT OR IGNORE INTO guilds (id, name)
                    VALUES (?, ?)
                """, (guild_id, guild_name or str(guild_id)))
                
                await conn.commit()
                logger.info(f"Initialized guild {guild_id} in database")
            except Exception as e:
                await conn.rollback()
                logger.error(f"Failed to initialize guild {guild_id}: {e}")
                raise

    async def batch_update_metrics(self, metrics: List[Dict[str, Any]]) -> None:
        """Batch insert guild metrics asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("BEGIN")
            try:
                await conn.executemany("""
                    INSERT INTO guild_metrics 
                    (guild_id, member_count, active_users, message_count, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, [
                    (m['guild_id'], m['member_count'], m['active_users'],
                     m.get('message_count', 0), m.get('timestamp', datetime.now()))
                    for m in metrics
                ])
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                logger.error(f"Failed to update metrics: {e}")
                raise

    async def log_command(self, guild_id: int, user_id: int, command_name: str,
                         success: bool, error: str = None, execution_time: float = None) -> None:
        """Log command usage asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                # Log to command_stats for metrics
                await conn.execute("""
                    INSERT INTO command_stats 
                    (guild_id, user_id, command_name, success, execution_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild_id, user_id, command_name, success, execution_time))

                # Log to command_logs for detailed tracking
                await conn.execute("""
                    INSERT INTO command_logs 
                    (guild_id, user_id, command_name, success, error, execution_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (guild_id, user_id, command_name, success, error, execution_time))
                
                await conn.commit()
            except Exception as e:
                logger.error(f"Failed to log command: {e}")

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get all settings for a guild"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT * FROM guilds WHERE id = ?
            """, (guild_id,))
            result = await cur.fetchone()
            return dict(result) if result else None

    async def update_guild_settings(self, guild_id: int, **settings) -> bool:
        """Update guild settings"""
        valid_columns = {'prefix', 'locale', 'timezone', 'name'}
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            try:
                for key, value in settings.items():
                    await conn.execute(f"""
                        UPDATE guilds 
                        SET {key} = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (value, guild_id))
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update guild settings: {e}")
                return False

    async def backup_database(self) -> Optional[str]:
        """Create a backup of the database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join('db', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f'{self.db_name}_{timestamp}.db')
            
            async with self._lock:
                conn = await self.get_connection()
                backup_conn = await aiosqlite.connect(backup_path)
                await conn.backup(backup_conn)
                await backup_conn.close()
            
            # Keep only last 5 backups
            backups = sorted(Path(backup_dir).glob(f'{self.db_name}_*.db'))
            while len(backups) > 5:
                backups[0].unlink()
                backups.pop(0)
            
            logger.info(f"Database backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    async def get_server_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get server settings for a guild"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT * FROM server_settings WHERE guild_id = ?
            """, (guild_id,))
            result = await cur.fetchone()
            return dict(result) if result else None

    async def update_server_settings(self, guild_id: int, **settings) -> bool:
        """Update server settings"""
        valid_columns = {
            'welcome_channel_id', 'welcome_message', 'goodbye_channel_id',
            'goodbye_message', 'mod_log_channel_id', 'audit_log_channel_id',
            'mute_role_id', 'auto_role_id', 'authorized_roles',
            'disabled_commands', 'auto_mod_enabled', 'max_mentions',
            'max_links', 'max_attachments', 'filters_enabled',
            'filtered_words', 'caps_threshold', 'spam_threshold',
            'raid_mode_enabled', 'verification_level'
        }
        
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            try:
                # Ensure server settings entry exists
                await conn.execute("""
                    INSERT OR IGNORE INTO server_settings (guild_id)
                    VALUES (?)
                """, (guild_id,))

                # Update settings
                set_clause = ', '.join(f"{key} = ?" for key in settings.keys())
                values = tuple(settings.values()) + (guild_id,)
                
                await conn.execute(f"""
                    UPDATE server_settings 
                    SET {set_clause}
                    WHERE guild_id = ?
                """, values)
                
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update server settings: {e}")
                return False

    async def ensure_server_settings(self, guild_id: int) -> None:
        """Ensure server settings exist with default values"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.execute("""
                    INSERT OR IGNORE INTO server_settings (guild_id)
                    VALUES (?)
                """, (guild_id,))
                await conn.commit()
            except Exception as e:
                logger.error(f"Failed to initialize server settings: {e}")
                raise