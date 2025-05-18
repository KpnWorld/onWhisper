import aiosqlite
import logging
import random
from typing import Optional

class DBManager:
    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self.log = logger or logging.getLogger("DBManager")

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection has not been initialized.")
        return self._conn

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self._create_tables()
        self.log.info("Database initialized.")

    async def _create_tables(self):
        await self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            whisper_channel_id INTEGER,
            whisper_staff_role_id INTEGER,
            leveling_enabled BOOLEAN DEFAULT 1,
            leveling_cooldown INTEGER DEFAULT 60,
            xp_min INTEGER DEFAULT 10,
            xp_max INTEGER DEFAULT 20
        );

        CREATE TABLE IF NOT EXISTS level_roles (
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, level),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS whispers (
            guild_id INTEGER,
            whisper_id TEXT,
            user_id INTEGER,
            thread_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, whisper_id)
        );

        CREATE TABLE IF NOT EXISTS logs (
            guild_id INTEGER,
            event_type TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_message TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS autoroles (
            guild_id INTEGER,
            role_id INTEGER,
            event TEXT CHECK(event IN ('join', 'level')),
            level_required INTEGER,
            PRIMARY KEY (guild_id, role_id, event)
        );

        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id INTEGER,
            message_id INTEGER,
            emoji TEXT,
            role_id INTEGER,
            PRIMARY KEY (guild_id, message_id, emoji)
        );

        CREATE TABLE IF NOT EXISTS color_roles (
            guild_id INTEGER,
            role_id INTEGER,
            name TEXT,
            PRIMARY KEY (guild_id, role_id)
        );
        """)
        await self.connection.commit()
        self.log.info("Database tables created or verified.")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self.log.info("Database connection closed.")
