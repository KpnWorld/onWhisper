from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Any, TypeVar, Tuple
from datetime import datetime
import json
import time
import logging
import aiosqlite
from aiosqlite import Connection, Cursor

T = TypeVar('T')

class DBManager:    
    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None) -> None:
        self.db_path = db_path
        self._conn: Optional[Connection] = None
        self.log = logger or logging.getLogger("DBManager")

    @property
    def connection(self) -> Connection:
        """Get the database connection.
        
        Returns:
            The active database connection
            
        Raises:
            RuntimeError: If the connection hasn't been initialized
        """
        if not self._conn:
            raise RuntimeError("Database connection not initialized. Call init() first.")
        return self._conn    
        
    async def init(self) -> None:
        """Initialize database connection and create tables"""
        try:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._create_tables()
            await self._create_indexes()
            self.log.info("Database initialization complete")
        except Exception as e:
            self.log.error(f"Error initializing database: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """Close the database connection and perform cleanup.
        
        This method should be called when the database is no longer needed
        to ensure proper resource cleanup.
        """
        if self._conn:
            try:
                await self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Cleanup WAL files
                await self._conn.close()
                self._conn = None
                self.log.info("Database connection closed successfully.")
            except aiosqlite.Error as e:
                self.log.error(f"Error while closing database connection: {e}")
                raise

    async def _create_tables(self):
        """Create all required database tables"""
        tables = [
            """CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '!',
                locale TEXT DEFAULT 'en',
                premium_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                guild_id INTEGER,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                messages_count INTEGER DEFAULT 0,
                commands_used INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS feature_settings (
                guild_id INTEGER,
                feature TEXT,
                enabled BOOLEAN DEFAULT FALSE,
                options_json TEXT,
                PRIMARY KEY (guild_id, feature),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS leveling_users (
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS leveling_roles (
                guild_id INTEGER,
                level INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, level)
            )""",
            """CREATE TABLE IF NOT EXISTS autoroles (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, message_id, emoji)
            )""",
            """CREATE TABLE IF NOT EXISTS color_roles (
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS whispers (
                guild_id INTEGER,
                user_id INTEGER,
                thread_id INTEGER,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (guild_id, thread_id)
            )""",
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER,
                setting TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, setting)
            )"""
        ]

        async with self.transaction() as tr:
            for table in tables:
                await tr.execute(table)
        
        await self.connection.commit()
        self.log.info("Database tables created.")

    async def _create_indexes(self):
        """Create performance indexes"""
        await self.connection.executescript("""
        -- Guild Indexes
        CREATE INDEX IF NOT EXISTS idx_guilds_premium ON guilds(premium_until) WHERE premium_until IS NOT NULL;

        -- User Indexes
        CREATE INDEX IF NOT EXISTS idx_users_activity ON users(guild_id, last_seen DESC);
        CREATE INDEX IF NOT EXISTS idx_users_messages ON users(guild_id, messages_count DESC);

        -- Feature Settings Indexes
        CREATE INDEX IF NOT EXISTS idx_feature_settings_lookup ON feature_settings(guild_id, feature);
        CREATE INDEX IF NOT EXISTS idx_feature_settings_enabled ON feature_settings(guild_id) WHERE enabled = TRUE;

        -- Logs Indexes
        CREATE INDEX IF NOT EXISTS idx_logs_guild ON logs(guild_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_logs_type ON logs(guild_id, event_type);

        -- Leveling Indexes
        CREATE INDEX IF NOT EXISTS idx_leveling_users_xp ON leveling_users(guild_id, xp DESC);
        CREATE INDEX IF NOT EXISTS idx_leveling_roles_lookup ON leveling_roles(guild_id, level);

        -- Reaction Roles Index
        CREATE INDEX IF NOT EXISTS idx_reaction_roles_lookup ON reaction_roles(guild_id, message_id);

        -- Whispers Indexes
        CREATE INDEX IF NOT EXISTS idx_whispers_active ON whispers(guild_id, status) WHERE status = 'active';
        CREATE INDEX IF NOT EXISTS idx_whispers_user ON whispers(guild_id, user_id);
        """)
        
        await self.connection.commit()
        self.log.info("Database indexes created.")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Cursor]:
        """A context manager for database transactions.
        
        This ensures that a series of database operations either all complete successfully
        or are all rolled back in case of an error.
        
        Yields:
            Cursor: A database cursor for executing SQL commands
            
        Raises:
            aiosqlite.Error: If any database operation fails
            RuntimeError: If the database connection is not initialized
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
            
        tr = await self.connection.cursor()
        await tr.execute("BEGIN IMMEDIATE")  # Get write lock immediately
        
        try:
            yield tr
            await self.connection.commit()
        except Exception as e:
            await self.connection.rollback()
            self.log.error(f"Transaction failed, rolled back: {e}")
            raise
        finally:
            await tr.close()

    # -------------------- Guild Methods --------------------

    async def add_guild(self, guild_id: int) -> None:
        """Add a new guild to the database"""
        async with self.transaction() as tr:
            await tr.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))

    async def remove_guild(self, guild_id: int) -> None:
        """Remove a guild and all its associated data"""
        async with self.transaction() as tr:
            await tr.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))

    async def get_guild_prefix(self, guild_id: int) -> str:
        """Get guild prefix"""
        async with self.connection.execute(
            "SELECT prefix FROM guilds WHERE guild_id = ?", 
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "!"

    async def set_guild_prefix(self, guild_id: int, prefix: str) -> None:
        """Set guild prefix"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT INTO guilds (guild_id, prefix) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET prefix = ?",
                (guild_id, prefix, prefix)
            )

    # -------------------- User Methods --------------------

    async def update_user_activity(self, guild_id: int, user_id: int) -> None:
        """Update user's last seen timestamp"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO users (guild_id, user_id, last_seen, messages_count) 
                VALUES (?, ?, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(guild_id, user_id) DO UPDATE 
                SET last_seen = CURRENT_TIMESTAMP,
                    messages_count = messages_count + 1
            """, (guild_id, user_id))

    async def increment_user_commands(self, guild_id: int, user_id: int) -> None:
        """Increment user's commands used counter"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO users (guild_id, user_id, commands_used) 
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, user_id) DO UPDATE 
                SET commands_used = commands_used + 1
            """, (guild_id, user_id))

    # -------------------- Feature Settings Methods --------------------

    async def get_feature_settings(self, guild_id: int, feature: str) -> Optional[Dict[str, Any]]:
        """Get raw feature settings from database"""
        if not self._conn:
            raise RuntimeError("Database not initialized")
            
        async with self.connection.execute(
            "SELECT enabled, options_json FROM feature_settings WHERE guild_id = ? AND feature = ?",
            (guild_id, feature)
        ) as cursor:
            row = await cursor.fetchone()
            return {
                'enabled': bool(row[0]),
                'options': json.loads(row[1]) if row[1] else {}
            } if row else None

    async def set_feature_settings(self, guild_id: int, feature: str, enabled: bool, options: Dict[str, Any]) -> None:
        """Set raw feature settings in database. For feature management, use FeatureManager."""
        async with self.transaction() as tr:
            # Ensure guild exists first
            await tr.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
            
            # Then set feature settings
            await tr.execute("""
                INSERT INTO feature_settings (guild_id, feature, enabled, options_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, feature) DO UPDATE 
                SET enabled = ?, options_json = ?
            """, (guild_id, feature, enabled, json.dumps(options), enabled, json.dumps(options)))

    # -------------------- Logging Methods --------------------

    async def add_log(self, guild_id: int, event_type: str, description: str) -> None:
        """Add a log entry"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT INTO logs (guild_id, event_type, description) VALUES (?, ?, ?)",
                (guild_id, event_type, description)
            )

    async def get_logs(self, guild_id: int, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logs with optional filtering"""
        query = "SELECT * FROM logs WHERE guild_id = ?"
        params: List[Any] = [guild_id]
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    async def clear_old_logs(self, guild_id: int, days: int) -> None:
        """Clear logs older than specified days"""
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM logs WHERE guild_id = ? AND timestamp < datetime('now', ?)",
                (guild_id, f'-{days} days')
            )

    # -------------------- Guild Settings Methods --------------------

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        async with self.connection.execute(
            "SELECT setting, value FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def update_guild_setting(self, guild_id: int, key: str, value: Any) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO guild_settings (guild_id, setting, value)
                VALUES (?, ?, ?) ON CONFLICT(guild_id, setting) 
                DO UPDATE SET value=excluded.value""",
                (guild_id, key, str(value))
            )

    # -------------------- Leveling Methods --------------------

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO leveling_users (guild_id, user_id, xp, level, message_count)
                VALUES (?, ?, ?, 0, 1)
                ON CONFLICT(guild_id, user_id) DO UPDATE
                SET xp = xp + excluded.xp,
                    message_count = message_count + 1""",
                (guild_id, user_id, amount)
            )

    async def set_level(self, guild_id: int, user_id: int, level: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """UPDATE leveling_users SET level = ?, xp = (SELECT xp FROM leveling_users WHERE guild_id = ? AND user_id = ?) 
                WHERE guild_id = ? AND user_id = ?""",
                (level, guild_id, user_id, guild_id, user_id)
            )

    async def get_user_level(self, guild_id: int, user_id: int) -> Tuple[int, int]:
        async with self.connection.execute(
            "SELECT level, xp FROM leveling_users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else (0, 0)

    async def get_guild_leaderboard(self, guild_id: int, limit: int = 10) -> List[Tuple[int, int, int]]:
        async with self.connection.execute(
            "SELECT user_id, level, xp FROM leveling_users WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row["user_id"], row["level"], row["xp"]) for row in rows]

    async def set_role_for_level(self, guild_id: int, level: int, role_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO leveling_roles (guild_id, level, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id""",
                (guild_id, level, role_id)
            )

    async def get_role_for_level(self, guild_id: int, level: int) -> Optional[int]:
        async with self.connection.execute(
            "SELECT role_id FROM leveling_roles WHERE guild_id = ? AND level = ?",
            (guild_id, level)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    # -------------------- Autoroles Methods --------------------

    async def set_autorole(self, guild_id: int, role_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO autoroles (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id""",
                (guild_id, role_id)
            )

    async def get_autorole(self, guild_id: int) -> Optional[int]:
        async with self.connection.execute(
            "SELECT role_id FROM autoroles WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    # -------------------- Reaction Roles Methods --------------------

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, message_id, emoji) DO UPDATE SET role_id = excluded.role_id""",
                (guild_id, message_id, emoji, role_id)
            )

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild_id, message_id, emoji)
            )

    async def get_reaction_roles(self, guild_id: int, message_id: int) -> List[Dict[str, Any]]:
        async with self.connection.execute(
            "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
            (guild_id, message_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"emoji": row[0], "role_id": row[1]} for row in rows]

    # -------------------- Color Roles Methods --------------------

    async def set_color_role(self, guild_id: int, user_id: int, role_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO color_roles (guild_id, user_id, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET role_id = excluded.role_id""",
                (guild_id, user_id, role_id)
            )

    async def get_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        async with self.connection.execute(
            "SELECT role_id FROM color_roles WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    # -------------------- Whispers Methods --------------------

    async def create_whisper_thread(self, guild_id: int, user_id: int) -> int:
        async with self.transaction() as tr:
            await tr.execute(
                """INSERT INTO whispers (guild_id, user_id, status, created_at, updated_at)
                VALUES (?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (guild_id, user_id)
            )
            rowid = tr.lastrowid
            if rowid is None:
                raise RuntimeError("Failed to create whisper thread: lastrowid is None")
            return rowid

    async def get_active_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        async with self.connection.execute(
            "SELECT user_id, thread_id FROM whispers WHERE guild_id = ? AND status = 'active'",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"user_id": row[0], "thread_id": row[1]} for row in rows]

    async def close_whisper_thread(self, guild_id: int, thread_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                "UPDATE whispers SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND thread_id = ?",
                (guild_id, thread_id)
            )

    async def reopen_whisper_thread(self, guild_id: int, thread_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                "UPDATE whispers SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND thread_id = ?",
                (guild_id, thread_id)
            )

    async def delete_whisper_thread(self, guild_id: int, thread_id: int) -> None:
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM whispers WHERE guild_id = ? AND thread_id = ?",
                (guild_id, thread_id)
            )

