# utils/db_manager.py

import aiosqlite
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("onWhisper.DBManager")


class DBManager:
    def __init__(self, db_path: str = "data/onwhisper.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self.conn: Optional[aiosqlite.Connection] = None
        logger.debug(f"DBManager initialized with db_path={db_path}")

    async def init_db(self):
        logger.info("Initializing database schema...")
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        async with self._lock:
            await self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER,
                    setting TEXT,
                    value TEXT,
                    PRIMARY KEY (guild_id, setting)
                );

                CREATE TABLE IF NOT EXISTS leveling_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS leveling_roles (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, level)
                );

                CREATE TABLE IF NOT EXISTS autoroles (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER
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
                    user_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS whispers (
                    guild_id INTEGER,
                    user_id INTEGER,
                    thread_id INTEGER,
                    is_open INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id, thread_id)
                );

                CREATE TABLE IF NOT EXISTS moderation_logs (
                    guild_id INTEGER,
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    reason TEXT,
                    moderator_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await self.conn.commit()
        logger.info("Database initialized successfully.")

    # -------------------- Generic Query Methods -------------------- #
    async def execute(self, query: str, params: Tuple = ()) -> aiosqlite.Cursor:
        async with self._lock:
            logger.debug(f"Executing query: {query} | params={params}")
            cur = await self.conn.execute(query, params)
            await self.conn.commit()
            return cur

    async def fetchall(self, query: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        async with self._lock:
            logger.debug(f"Fetching all: {query} | params={params}")
            cur = await self.conn.execute(query, params)
            rows = await cur.fetchall()
            logger.debug(f"Fetched {len(rows)} rows")
            return rows

    async def fetchrow(self, query: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        async with self._lock:
            logger.debug(f"Fetching one row: {query} | params={params}")
            cur = await self.conn.execute(query, params)
            row = await cur.fetchone()
            logger.debug(f"Row fetched: {row}")
            return row

    async def fetchone(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow(query, params)
        result = dict(row) if row else None
        logger.debug(f"fetchone result: {result}")
        return result

    # -------------------- Guild Settings -------------------- #
    async def get_guild_settings(self, guild_id: int) -> Dict[str, str]:
        logger.debug(f"Getting guild settings for guild_id={guild_id}")
        rows = await self.fetchall(
            "SELECT setting, value FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        settings = {row["setting"]: row["value"] for row in rows}
        logger.debug(f"Guild settings: {settings}")
        return settings

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        logger.info(f"Setting guild setting: guild_id={guild_id}, {setting}={value}")
        await self.execute(
            "INSERT OR REPLACE INTO guild_settings (guild_id, setting, value) VALUES (?, ?, ?)",
            (guild_id, setting, value),
        )

    async def remove_guild_setting(self, guild_id: int, setting: str):
        logger.info(f"Removing guild setting: guild_id={guild_id}, setting={setting}")
        await self.execute(
            "DELETE FROM guild_settings WHERE guild_id = ? AND setting = ?", (guild_id, setting)
        )

    # -------------------- Leveling System -------------------- #
    async def get_user_xp(self, guild_id: int, user_id: int) -> int:
        logger.debug(f"Getting user XP: guild_id={guild_id}, user_id={user_id}")
        row = await self.fetchone(
            "SELECT xp FROM leveling_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        xp = row["xp"] if row else 0
        logger.debug(f"User XP: {xp}")
        return xp

    async def set_user_xp(self, guild_id: int, user_id: int, xp: int):
        logger.info(f"Setting user XP: guild_id={guild_id}, user_id={user_id}, xp={xp}")
        await self.execute(
            "INSERT OR REPLACE INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?)",
            (guild_id, user_id, xp),
        )

    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        logger.info(f"Adding XP: guild_id={guild_id}, user_id={user_id}, amount={amount}")
        await self.execute(
            "INSERT INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
            (guild_id, user_id, amount, amount),
        )

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        logger.info(f"Setting level role: guild_id={guild_id}, level={level}, role_id={role_id}")
        await self.execute(
            "INSERT OR REPLACE INTO leveling_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
            (guild_id, level, role_id),
        )

    async def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        logger.debug(f"Fetching level roles for guild_id={guild_id}")
        rows = await self.fetchall(
            "SELECT level, role_id FROM leveling_roles WHERE guild_id = ?", (guild_id,)
        )
        result = {row["level"]: row["role_id"] for row in rows}
        logger.debug(f"Level roles: {result}")
        return result

    # -------------------- Roles System -------------------- #
    async def set_autorole(self, guild_id: int, role_id: int):
        logger.info(f"Setting autorole: guild_id={guild_id}, role_id={role_id}")
        await self.execute(
            "INSERT OR REPLACE INTO autoroles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id)
        )

    async def get_autorole(self, guild_id: int) -> Optional[int]:
        logger.debug(f"Getting autorole for guild_id={guild_id}")
        row = await self.fetchone("SELECT role_id FROM autoroles WHERE guild_id = ?", (guild_id,))
        result = row["role_id"] if row else None
        logger.debug(f"Autorole: {result}")
        return result

    # -------------------- Reaction & Color Roles -------------------- #
    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        logger.info(f"Adding reaction role: guild_id={guild_id}, message_id={message_id}, emoji={emoji}, role_id={role_id}")
        await self.execute(
            "INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
            (guild_id, message_id, emoji, role_id),
        )

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        logger.info(f"Removing reaction role: guild_id={guild_id}, message_id={message_id}, emoji={emoji}")
        await self.execute(
            "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (guild_id, message_id, emoji),
        )

    async def get_reaction_roles(self, guild_id: int, message_id: int) -> Dict[str, int]:
        logger.debug(f"Fetching reaction roles: guild_id={guild_id}, message_id={message_id}")
        rows = await self.fetchall(
            "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
            (guild_id, message_id),
        )
        result = {row["emoji"]: row["role_id"] for row in rows}
        logger.debug(f"Reaction roles: {result}")
        return result

    async def set_color_role(self, guild_id: int, user_id: int, role_id: int):
        logger.info(f"Setting color role: guild_id={guild_id}, user_id={user_id}, role_id={role_id}")
        await self.execute(
            "INSERT OR REPLACE INTO color_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)",
            (guild_id, user_id, role_id),
        )

    async def get_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        logger.debug(f"Getting color role: guild_id={guild_id}, user_id={user_id}")
        row = await self.fetchone(
            "SELECT role_id FROM color_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        result = row["role_id"] if row else None
        logger.debug(f"Color role: {result}")
        return result

    # -------------------- Whispers -------------------- #
    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int):
        logger.info(f"Creating whisper: guild_id={guild_id}, user_id={user_id}, thread_id={thread_id}")
        await self.execute(
            "INSERT INTO whispers (guild_id, user_id, thread_id, is_open) VALUES (?, ?, ?, 1)",
            (guild_id, user_id, thread_id),
        )

    async def close_whisper(self, guild_id: int, user_id: int, thread_id: int):
        logger.info(f"Closing whisper: guild_id={guild_id}, user_id={user_id}, thread_id={thread_id}")
        await self.execute(
            "UPDATE whispers SET is_open = 0, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND user_id = ? AND thread_id = ?",
            (guild_id, user_id, thread_id),
        )

    async def get_open_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching open whispers for guild_id={guild_id}")
        rows = await self.fetchall(
            "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? AND is_open = 1",
            (guild_id,),
        )
        result = [{"user_id": r["user_id"], "thread_id": r["thread_id"], "created_at": r["created_at"]} for r in rows]
        logger.debug(f"Open whispers: {result}")
        return result

    # -------------------- Moderation Logs -------------------- #
    async def log_moderation_action(
        self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int
    ):
        logger.info(f"Logging moderation action: guild_id={guild_id}, user_id={user_id}, action={action}, moderator_id={moderator_id}")
        await self.execute(
            "INSERT INTO moderation_logs (guild_id, user_id, action, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, action, reason, moderator_id),
        )

    async def get_moderation_logs(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching moderation logs: guild_id={guild_id}, user_id={user_id}")
        rows = await self.fetchall(
            "SELECT case_id, action, reason, moderator_id, timestamp FROM moderation_logs WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = [
            {"case_id": r["case_id"], "action": r["action"], "reason": r["reason"], "moderator_id": r["moderator_id"], "timestamp": r["timestamp"]}
            for r in rows
        ]
        logger.debug(f"Moderation logs: {result}")
        return result

    # -------------------- Maintenance -------------------- #
    async def reset_guild_data(self, guild_id: int):
        logger.warning(f"Resetting all data for guild_id={guild_id}")
        tables = [
            "guild_settings", "leveling_users", "leveling_roles",
            "autoroles", "reaction_roles", "color_roles",
            "whispers", "moderation_logs",
        ]
        for table in tables:
            await self.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
            logger.debug(f"Cleared {table} for guild {guild_id}")

    async def vacuum(self):
        logger.info("Running VACUUM on database")
        await self.execute("VACUUM")
