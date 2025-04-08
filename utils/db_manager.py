import aiosqlite
import sqlite3
import logging
from datetime import datetime
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

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
        """Get a database cursor in an async context manager"""
        conn = await self.get_connection()
        return await conn.cursor()

    async def setup_database(self) -> None:
        """Initialize database schema with proper constraints"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executescript("""
                -- Core guild settings with improved constraints
                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prefix TEXT DEFAULT '!',
                    locale TEXT DEFAULT 'en-US',
                    timezone TEXT DEFAULT 'UTC',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    CHECK (prefix != '')
                );

                -- Extended guild settings with better organization
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT,
                    goodbye_channel_id INTEGER,
                    goodbye_message TEXT,
                    log_channel_id INTEGER,
                    mod_log_channel_id INTEGER,
                    mute_role_id INTEGER,
                    autorole_enabled BOOLEAN DEFAULT 0,
                    autorole_id INTEGER,
                    level_channel_id INTEGER,
                    embed_color TEXT DEFAULT '0000FF',
                    premium_status INTEGER DEFAULT 0,
                    premium_until TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Enhanced user statistics
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    messages INTEGER DEFAULT 0,
                    last_xp TIMESTAMP,
                    voice_time INTEGER DEFAULT 0,
                    invites INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    total_voice_messages INTEGER DEFAULT 0,
                    total_reactions_added INTEGER DEFAULT 0,
                    total_reactions_received INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id),
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                    CHECK (xp >= 0),
                    CHECK (level >= 0)
                );

                -- Detailed command logging
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
                    execution_time REAL,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Comprehensive guild metrics
                CREATE TABLE IF NOT EXISTS guild_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    member_count INTEGER,
                    active_users INTEGER,
                    message_count INTEGER DEFAULT 0,
                    voice_users INTEGER DEFAULT 0,
                    bot_count INTEGER DEFAULT 0,
                    channel_count INTEGER DEFAULT 0,
                    role_count INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                    CHECK (member_count >= 0),
                    CHECK (active_users >= 0)
                );

                -- Enhanced leveling system
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
                    ignore_channels TEXT, -- JSON array of channel IDs
                    xp_multiplier REAL DEFAULT 1.0,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                    CHECK (xp_cooldown > 0),
                    CHECK (min_xp > 0),
                    CHECK (max_xp >= min_xp)
                );

                -- Improved level roles with role removal tracking
                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    remove_lower BOOLEAN DEFAULT 0,
                    temporary BOOLEAN DEFAULT 0,
                    duration INTEGER, -- Duration in minutes if temporary
                    PRIMARY KEY (guild_id, level),
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Enhanced user settings
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

                -- Improved reaction roles with groups
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    description TEXT,
                    exclusive_group INTEGER DEFAULT 0,
                    temporary BOOLEAN DEFAULT 0,
                    duration INTEGER, -- Duration in minutes if temporary
                    max_users INTEGER DEFAULT 0, -- 0 means unlimited
                    required_role_id INTEGER,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Enhanced verification system
                CREATE TABLE IF NOT EXISTS verification_settings (
                    guild_id INTEGER PRIMARY KEY,
                    enabled BOOLEAN DEFAULT 0,
                    channel_id INTEGER,
                    role_id INTEGER,
                    message TEXT DEFAULT 'React with ✅ to verify',
                    type TEXT DEFAULT 'reaction',
                    timeout INTEGER DEFAULT 300,
                    captcha_enabled BOOLEAN DEFAULT 0,
                    verification_logs BOOLEAN DEFAULT 1,
                    min_account_age INTEGER DEFAULT 0, -- Minimum account age in hours
                    required_inviter_role_id INTEGER,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Create optimized indexes
                CREATE INDEX IF NOT EXISTS idx_user_stats_guild ON user_stats(guild_id, level DESC);
                CREATE INDEX IF NOT EXISTS idx_command_logs_guild_time ON command_logs(guild_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_metrics_guild_time ON guild_metrics(guild_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_reaction_roles_message ON reaction_roles(message_id);
                CREATE INDEX IF NOT EXISTS idx_level_roles_guild ON level_roles(guild_id, level);
                CREATE INDEX IF NOT EXISTS idx_user_settings_guild ON user_settings(guild_id);
            """)
            await conn.commit()

    async def ensure_guild_exists(self, guild_id: int, guild_name: str = None) -> None:
        """Ensure guild exists with all required settings"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("BEGIN")
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO guilds (id, name) VALUES (?, ?)",
                    (guild_id, guild_name or str(guild_id))
                )
                
                # Initialize all required settings atomically
                await conn.execute(
                    "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
                    (guild_id,)
                )
                
                await conn.execute("""
                    INSERT OR IGNORE INTO leveling_settings 
                    (guild_id, xp_cooldown, min_xp, max_xp)
                    VALUES (?, 60, 15, 25)
                """, (guild_id,))
                
                await conn.commit()
            except Exception:
                await conn.rollback()
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
            except Exception:
                await conn.rollback()
                raise

    async def log_command(self, guild_id: int, user_id: int, command_name: str,
                         success: bool, error: str = None, execution_time: float = None) -> None:
        """Log command usage asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("""
                INSERT INTO command_logs 
                (guild_id, user_id, command_name, success, error, execution_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error, execution_time))
            await conn.commit()

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            async with conn.execute("""
                SELECT g.*, gs.*
                FROM guilds g
                LEFT JOIN guild_settings gs ON g.id = gs.guild_id
                WHERE g.id = ?
            """, (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_guild_settings(self, guild_id: int, **settings) -> bool:
        """Update guild settings asynchronously"""
        valid_columns = {
            'prefix', 'locale', 'timezone', 'welcome_channel_id',
            'goodbye_channel_id', 'log_channel_id', 'mute_role_id',
            'autorole_enabled', 'autorole_id', 'level_channel_id'
        }
        
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("BEGIN")
            try:
                for key, value in settings.items():
                    table = 'guilds' if key in {'prefix', 'locale', 'timezone'} else 'guild_settings'
                    await conn.execute(
                        f"UPDATE {table} SET {key} = ? WHERE {'id' if table == 'guilds' else 'guild_id'} = ?",
                        (value, guild_id)
                    )
                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                return False

    async def backup_database(self) -> Optional[str]:
        """Create a backup of the database asynchronously"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join('db', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f'{self.db_name}_{timestamp}.db')
            
            # Create backup connection
            await self._lock.acquire()
            try:
                conn = await self.get_connection()
                backup_conn = await aiosqlite.connect(backup_path)
                await conn.backup(backup_conn)
                await backup_conn.close()
            finally:
                self._lock.release()
            
            # Keep only last 5 backups
            backups = sorted(Path(backup_dir).glob(f'{self.db_name}_*.db'))
            while len(backups) > 5:
                backups.pop(0).unlink()
            
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None