import os
import sqlite3
import logging
import asyncio
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class AsyncCursorContextManager:
    def __init__(self, db):
        self.db = db
        self.cursor = None
        self.conn = None

    async def __aenter__(self):
        self.conn = await self.db.get_connection()
        self.cursor = await self.conn.cursor()
        return self.cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            await self.cursor.close()
            if exc_type is None:
                await self.conn.commit()

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
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def cursor(self):
        """Get a database cursor as an async context manager"""
        return AsyncCursorContextManager(self)

    async def setup_database(self) -> None:
        """Initialize database schema with proper constraints"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executescript("""
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

                -- Command metrics
                CREATE TABLE IF NOT EXISTS command_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    command_name TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    error TEXT,
                    execution_time REAL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Command logs
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    command_name TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    error TEXT,
                    execution_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Guild metrics
                CREATE TABLE IF NOT EXISTS guild_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    member_count INTEGER NOT NULL,
                    online_count INTEGER,
                    message_count INTEGER DEFAULT 0,
                    active_users INTEGER DEFAULT 0,
                    bot_latency REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_command_stats_guild ON command_stats(guild_id);
                CREATE INDEX IF NOT EXISTS idx_command_stats_user ON command_stats(user_id);
                CREATE INDEX IF NOT EXISTS idx_guild_metrics_guild ON guild_metrics(guild_id);
                CREATE INDEX IF NOT EXISTS idx_guild_metrics_time ON guild_metrics(timestamp);
            """)
            await conn.commit()

    async def ensure_guild_exists(self, guild_id: int, guild_name: str = None) -> None:
        """Ensure guild exists with all required settings"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("""
                INSERT OR IGNORE INTO guilds (id, name)
                VALUES (?, ?)
            """, (guild_id, guild_name or str(guild_id)))
            
            await conn.execute("""
                INSERT OR IGNORE INTO server_settings (guild_id)
                VALUES (?)
            """, (guild_id,))
            
            await conn.commit()

    async def batch_update_metrics(self, metrics: List[Dict[str, Any]]) -> None:
        """Batch insert guild metrics asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executemany("""
                INSERT INTO guild_metrics (
                    guild_id, member_count, online_count,
                    message_count, active_users, bot_latency
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [(m['guild_id'], m['member_count'], m.get('online_count', 0),
                  m.get('message_count', 0), m.get('active_users', 0),
                  m.get('bot_latency', 0)) for m in metrics])
            await conn.commit()

    async def log_command(self, guild_id: int, user_id: int, command_name: str,
                         success: bool, error: str = None, execution_time: float = None) -> None:
        """Log command usage asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("""
                INSERT INTO command_stats (
                    guild_id, user_id, command_name,
                    success, error, execution_time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error, execution_time))
            
            await conn.execute("""
                INSERT INTO command_logs (
                    guild_id, user_id, command_name,
                    success, error, execution_time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error, execution_time))
            
            await conn.commit()

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT * FROM guilds WHERE id = ?
            """, (guild_id,))
            result = await cur.fetchone()
            return dict(result) if result else {}

    async def update_guild_settings(self, guild_id: int, **settings) -> bool:
        """Update guild settings"""
        valid_columns = {'prefix', 'locale', 'timezone', 'name'}
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            try:
                set_clause = ', '.join(f"{key} = ?" for key in settings.keys())
                values = tuple(settings.values()) + (guild_id,)
                
                await conn.execute(f"""
                    UPDATE guilds 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update guild settings: {e}")
                return False

    async def backup_database(self) -> Optional[str]:
        """Create a backup of the database"""
        try:
            backup_dir = Path('db/backups')
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f"{self.db_name}_{timestamp}.db"
            
            # Create backup connection
            async with aiosqlite.connect(backup_path) as backup_conn:
                async with self._lock:
                    conn = await self.get_connection()
                    await conn.backup(backup_conn)
            
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
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

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch one row"""
        async with self._lock:
            conn = await self.get_connection()
            cursor = await conn.execute(query, params)
            result = await cursor.fetchone()
            await cursor.close()
            return dict(result) if result else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and fetch all rows"""
        async with self._lock:
            conn = await self.get_connection()
            cursor = await conn.execute(query, params)
            results = await cursor.fetchall()
            await cursor.close()
            return [dict(row) for row in results]

    async def execute(self, query: str, params: tuple = ()):
        """Execute a query without fetching results"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute(query, params)
            await conn.commit()

    async def executemany(self, query: str, params_list: List[tuple]):
        """Execute a query multiple times with different parameters"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executemany(query, params_list)
            await conn.commit()

    async def get_all_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get all settings for a guild"""
        return await self.fetchone("""
            SELECT g.*, s.*
            FROM guilds g
            LEFT JOIN server_settings s ON g.id = s.guild_id
            WHERE g.id = ?
        """, (guild_id,))