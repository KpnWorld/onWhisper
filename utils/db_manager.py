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
        -- Config cog tables
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER,
            setting TEXT,
            value TEXT,
            PRIMARY KEY (guild_id, setting)
        );

        CREATE TABLE IF NOT EXISTS whisper_settings (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            staff_role_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS logging_settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            options_json TEXT
        );

        -- Roles cog tables
        CREATE TABLE IF NOT EXISTS autoroles (
            guild_id INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS color_roles (
            guild_id INTEGER,
            role_id INTEGER,
            color_name TEXT,
            PRIMARY KEY (guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id INTEGER,
            message_id INTEGER,
            emoji TEXT,
            role_id INTEGER,
            PRIMARY KEY (guild_id, message_id, emoji)
        );

        CREATE TABLE IF NOT EXISTS level_roles (
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, level)
        );

        -- Leveling cog tables
        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_message_ts TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS level_config (
            guild_id INTEGER PRIMARY KEY,
            cooldown INTEGER DEFAULT 60,  -- seconds
            min_xp INTEGER DEFAULT 10,
            max_xp INTEGER DEFAULT 20
        );

        -- Logging cog tables
        CREATE TABLE IF NOT EXISTS logs (
            guild_id INTEGER,
            event_type TEXT,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Moderation cog tables
        CREATE TABLE IF NOT EXISTS mod_actions (
            guild_id INTEGER,
            user_id INTEGER,
            action TEXT,
            reason TEXT,
            moderator_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Whisper cog tables
        CREATE TABLE IF NOT EXISTS whispers (
            guild_id INTEGER,
            whisper_id TEXT,
            user_id INTEGER,
            thread_id INTEGER,
            is_closed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            PRIMARY KEY (guild_id, whisper_id)
        );
        """)
        await self.connection.commit()
        self.log.info("Database tables created or verified.")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self.log.info("Database connection closed.")

    # Config cog methods
    async def get_guild_setting(self, guild_id: int, setting: str) -> Optional[str]:
        async with self.connection.execute(
            "SELECT value FROM guild_settings WHERE guild_id = ? AND setting = ?",
            (guild_id, setting)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        await self.connection.execute(
            """INSERT OR REPLACE INTO guild_settings (guild_id, setting, value)
            VALUES (?, ?, ?)""",
            (guild_id, setting, value)
        )
        await self.connection.commit()

    async def get_whisper_settings(self, guild_id: int) -> Optional[dict]:
        async with self.connection.execute(
            "SELECT channel_id, staff_role_id FROM whisper_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "channel_id": result[0],
                    "staff_role_id": result[1]
                }
            return None

    async def set_whisper_settings(self, guild_id: int, channel_id: int, staff_role_id: int):
        await self.connection.execute(
            """INSERT OR REPLACE INTO whisper_settings (guild_id, channel_id, staff_role_id)
            VALUES (?, ?, ?)""",
            (guild_id, channel_id, staff_role_id)
        )
        await self.connection.commit()

    async def get_logging_settings(self, guild_id: int) -> Optional[dict]:
        async with self.connection.execute(
            "SELECT log_channel_id, options_json FROM logging_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "log_channel_id": result[0],
                    "options_json": result[1]
                }
            return None

    async def set_logging_settings(self, guild_id: int, log_channel_id: int, options_json: str):
        await self.connection.execute(
            """INSERT OR REPLACE INTO logging_settings (guild_id, log_channel_id, options_json)
            VALUES (?, ?, ?)""",
            (guild_id, log_channel_id, options_json)
        )
        await self.connection.commit()

    # Roles cog methods
    async def add_autorole(self, guild_id: int, role_id: int):
        await self.connection.execute(
            "INSERT OR IGNORE INTO autoroles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id)
        )
        await self.connection.commit()

    async def remove_autorole(self, guild_id: int, role_id: int):
        await self.connection.execute(
            "DELETE FROM autoroles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id)
        )
        await self.connection.commit()

    async def get_autoroles(self, guild_id: int) -> list[int]:
        async with self.connection.execute(
            "SELECT role_id FROM autoroles WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            return [row[0] for row in await cursor.fetchall()]

    async def add_color_role(self, guild_id: int, role_id: int, color_name: str):
        await self.connection.execute(
            """INSERT OR REPLACE INTO color_roles (guild_id, role_id, color_name)
            VALUES (?, ?, ?)""",
            (guild_id, role_id, color_name)
        )
        await self.connection.commit()

    async def remove_color_role(self, guild_id: int, role_id: int):
        await self.connection.execute(
            "DELETE FROM color_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id)
        )
        await self.connection.commit()

    async def get_color_roles(self, guild_id: int) -> list[dict]:
        async with self.connection.execute(
            "SELECT role_id, color_name FROM color_roles WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            return [{"role_id": row[0], "color_name": row[1]} for row in await cursor.fetchall()]

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        await self.connection.execute(
            """INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)""",
            (guild_id, message_id, emoji, role_id)
        )
        await self.connection.commit()

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        await self.connection.execute(
            "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (guild_id, message_id, emoji)
        )
        await self.connection.commit()

    async def get_reaction_roles(self, guild_id: int) -> list[dict]:
        async with self.connection.execute(
            "SELECT message_id, emoji, role_id FROM reaction_roles WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            return [{
                "message_id": row[0],
                "emoji": row[1],
                "role_id": row[2]
            } for row in await cursor.fetchall()]

    async def add_level_role(self, guild_id: int, level: int, role_id: int):
        await self.connection.execute(
            """INSERT OR REPLACE INTO level_roles (guild_id, level, role_id)
            VALUES (?, ?, ?)""",
            (guild_id, level, role_id)
        )
        await self.connection.commit()

    async def remove_level_role(self, guild_id: int, level: int):
        await self.connection.execute(
            "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
            (guild_id, level)
        )
        await self.connection.commit()

    async def get_level_roles(self, guild_id: int) -> list[dict]:
        async with self.connection.execute(
            "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level",
            (guild_id,)
        ) as cursor:
            return [{"level": row[0], "role_id": row[1]} for row in await cursor.fetchall()]

    # Leveling cog methods
    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        await self.connection.execute(
            """INSERT INTO xp (guild_id, user_id, xp, level, last_message_ts)
            VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
            xp = xp + ?,
            last_message_ts = CURRENT_TIMESTAMP""",
            (guild_id, user_id, amount, amount)
        )
        await self.connection.commit()

    async def get_user_xp(self, guild_id: int, user_id: int) -> dict:
        async with self.connection.execute(
            """SELECT xp, level, last_message_ts FROM xp
            WHERE guild_id = ? AND user_id = ?""",
            (guild_id, user_id)
        ) as cursor:
            result = await cursor.fetchone()
            return {
                "xp": result[0],
                "level": result[1],
                "last_message_ts": result[2]
            } if result else {"xp": 0, "level": 0, "last_message_ts": None}

    async def set_xp(self, guild_id: int, user_id: int, xp: int, level: int):
        await self.connection.execute(
            """INSERT OR REPLACE INTO xp (guild_id, user_id, xp, level, last_message_ts)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (guild_id, user_id, xp, level)
        )
        await self.connection.commit()

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> list[dict]:
        async with self.connection.execute(
            """SELECT user_id, xp, level FROM xp
            WHERE guild_id = ?
            ORDER BY xp DESC LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            return [{
                "user_id": row[0],
                "xp": row[1],
                "level": row[2]
            } for row in await cursor.fetchall()]

    async def get_level_config(self, guild_id: int) -> dict:
        async with self.connection.execute(
            """SELECT cooldown, min_xp, max_xp FROM level_config
            WHERE guild_id = ?""",
            (guild_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return {
                "cooldown": result[0],
                "min_xp": result[1],
                "max_xp": result[2]
            } if result else {"cooldown": 60, "min_xp": 10, "max_xp": 20}

    async def set_level_config(self, guild_id: int, cooldown: int, min_xp: int, max_xp: int):
        await self.connection.execute(
            """INSERT OR REPLACE INTO level_config (guild_id, cooldown, min_xp, max_xp)
            VALUES (?, ?, ?, ?)""",
            (guild_id, cooldown, min_xp, max_xp)
        )
        await self.connection.commit()

    # Logging cog methods
    async def log_event(self, guild_id: int, event_type: str, description: str, timestamp: Optional[float] = None):
        await self.connection.execute(
            """INSERT INTO logs (guild_id, event_type, description, timestamp)
            VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
            (guild_id, event_type, description, timestamp)
        )
        await self.connection.commit()

    async def get_logs(self, guild_id: int, limit: int = 100) -> list[dict]:
        async with self.connection.execute(
            """SELECT event_type, description, timestamp FROM logs
            WHERE guild_id = ?
            ORDER BY timestamp DESC LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            return [{
                "event_type": row[0],
                "description": row[1],
                "timestamp": row[2]
            } for row in await cursor.fetchall()]

    # Moderation cog methods
    async def add_mod_action(self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int):
        await self.connection.execute(
            """INSERT INTO mod_actions (guild_id, user_id, action, reason, moderator_id)
            VALUES (?, ?, ?, ?, ?)""",
            (guild_id, user_id, action, reason, moderator_id)
        )
        await self.connection.commit()

    async def get_user_mod_actions(self, guild_id: int, user_id: int) -> list[dict]:
        async with self.connection.execute(
            """SELECT action, reason, moderator_id, timestamp FROM mod_actions
            WHERE guild_id = ? AND user_id = ?
            ORDER BY timestamp DESC""",
            (guild_id, user_id)
        ) as cursor:
            return [{
                "action": row[0],
                "reason": row[1],
                "moderator_id": row[2],
                "timestamp": row[3]
            } for row in await cursor.fetchall()]

    # Whisper cog methods
    async def create_whisper(self, guild_id: int, whisper_id: int, user_id: int, thread_id: int):
        await self.connection.execute(
            """INSERT INTO whispers (guild_id, whisper_id, user_id, thread_id)
            VALUES (?, ?, ?, ?)""",
            (guild_id, whisper_id, user_id, thread_id)
        )
        await self.connection.commit()

    async def close_whisper(self, guild_id: int, whisper_id: int):
        await self.connection.execute(
            """UPDATE whispers SET is_closed = TRUE, closed_at = CURRENT_TIMESTAMP
            WHERE guild_id = ? AND whisper_id = ?""",
            (guild_id, whisper_id)
        )
        await self.connection.commit()

    async def delete_whisper(self, guild_id: int, whisper_id: int):
        await self.connection.execute(
            "DELETE FROM whispers WHERE guild_id = ? AND whisper_id = ?",
            (guild_id, whisper_id)
        )
        await self.connection.commit()

    async def get_whisper(self, guild_id: int, whisper_id: int) -> Optional[dict]:
        async with self.connection.execute(
            """SELECT user_id, thread_id, is_closed, created_at, closed_at
            FROM whispers WHERE guild_id = ? AND whisper_id = ?""",
            (guild_id, whisper_id)
        ) as cursor:
            result = await cursor.fetchone()
            if result is None:
                return None
            return {
                "user_id": result[0],
                "thread_id": result[1],
                "is_closed": bool(result[2]),
                "created_at": result[3],
                "closed_at": result[4]
            }

    async def get_active_whispers(self, guild_id: int) -> list[dict]:
        async with self.connection.execute(
            """SELECT whisper_id, user_id, thread_id, created_at
            FROM whispers WHERE guild_id = ? AND is_closed = FALSE""",
            (guild_id,)
        ) as cursor:
            return [{
                "whisper_id": row[0],
                "user_id": row[1],
                "thread_id": row[2],
                "created_at": row[3]
            } for row in await cursor.fetchall()]
