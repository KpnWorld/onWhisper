from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Any, TypeVar
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

