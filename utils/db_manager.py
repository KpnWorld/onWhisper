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

    # -------------------- Database Initialization -------------------- #
    async def init_db(self):
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
        if self.conn is None:
            raise RuntimeError("Database not initialized")
        async with self._lock:
            cur = await self.conn.execute(query, params)
            await self.conn.commit()
            return cur

    async def fetchall(self, query: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        if self.conn is None:
            raise RuntimeError("Database not initialized")
        async with self._lock:
            cur = await self.conn.execute(query, params)
            rows = await cur.fetchall()
            return list(rows)

    async def fetchrow(self, query: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        if self.conn is None:
            raise RuntimeError("Database not initialized")
        async with self._lock:
            cur = await self.conn.execute(query, params)
            row = await cur.fetchone()
            return row

    async def fetchone(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow(query, params)
        return dict(row) if row else None

    # -------------------- Guild Settings -------------------- #
    async def get_guild_settings(self, guild_id: int) -> Dict[str, str]:
        rows = await self.fetchall(
            "SELECT setting, value FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        return {row["setting"]: row["value"] for row in rows}

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        await self.execute(
            "INSERT OR REPLACE INTO guild_settings (guild_id, setting, value) VALUES (?, ?, ?)",
            (guild_id, setting, value),
        )

    async def remove_guild_setting(self, guild_id: int, setting: str):
        await self.execute(
            "DELETE FROM guild_settings WHERE guild_id = ? AND setting = ?", (guild_id, setting)
        )

    # -------------------- Whisper System -------------------- #
    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int) -> int:
        """Create a new whisper and return its sequential number"""
        async with self._lock:
            # Get the next whisper number for this guild
            count_row = await self.conn.execute(
                "SELECT COUNT(*) as count FROM whispers WHERE guild_id = ?", (guild_id,)
            )
            count_result = await count_row.fetchone()
            whisper_number = (count_result[0] if count_result else 0) + 1
            
            # Insert the whisper
            await self.conn.execute(
                "INSERT INTO whispers (guild_id, user_id, thread_id, created_at, is_open) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, thread_id, datetime.utcnow(), 1)
            )
            await self.conn.commit()
            return whisper_number

    async def get_whisper_by_number(self, guild_id: int, whisper_number: int) -> Optional[Dict[str, Any]]:
        """Get whisper by its sequential number (1-indexed)"""
        rows = await self.fetchall(
            "SELECT user_id, thread_id, created_at, is_open FROM whispers WHERE guild_id = ? ORDER BY created_at",
            (guild_id,)
        )
        if rows and 1 <= whisper_number <= len(rows):
            row = rows[whisper_number - 1]
            return dict(row)
        return None

    async def get_active_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all active whispers for a guild"""
        rows = await self.fetchall(
            "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? AND is_open = ? ORDER BY created_at",
            (guild_id, 1)
        )
        return [dict(row) for row in rows]

    async def close_whisper(self, guild_id: int, thread_id: int) -> bool:
        """Close a whisper thread"""
        result = await self.execute(
            "UPDATE whispers SET is_open = ?, closed_at = ? WHERE guild_id = ? AND thread_id = ?",
            (0, datetime.utcnow(), guild_id, thread_id)
        )
        return result.rowcount > 0

    async def delete_whisper(self, guild_id: int, thread_id: int) -> bool:
        """Delete a whisper from database"""
        result = await self.execute(
            "DELETE FROM whispers WHERE guild_id = ? AND thread_id = ?",
            (guild_id, thread_id)
        )
        return result.rowcount > 0

    # -------------------- Leveling -------------------- #
    async def get_user_xp(self, guild_id: int, user_id: int) -> int:
        row = await self.fetchone(
            "SELECT xp FROM leveling_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return row["xp"] if row else 0

    async def set_user_xp(self, guild_id: int, user_id: int, xp: int):
        await self.execute(
            "INSERT OR REPLACE INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?)",
            (guild_id, user_id, xp),
        )

    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        await self.execute(
            "INSERT INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
            (guild_id, user_id, amount, amount),
        )

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO leveling_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
            (guild_id, level, role_id),
        )

    async def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        rows = await self.fetchall(
            "SELECT level, role_id FROM leveling_roles WHERE guild_id = ?", (guild_id,)
        )
        return {row["level"]: row["role_id"] for row in rows}

    async def add_level_reward(self, guild_id: int, level: int, role_id: int):
        await self.set_level_role(guild_id, level, role_id)

    async def remove_level_reward(self, guild_id: int, level: int):
        await self.execute(
            "DELETE FROM leveling_roles WHERE guild_id = ? AND level = ?", (guild_id, level)
        )

    async def get_level_rewards(self, guild_id: int) -> Dict[int, int]:
        return await self.get_level_roles(guild_id)

    async def set_user_level(self, guild_id: int, user_id: int, level: int):
        await self.execute(
            "INSERT OR REPLACE INTO leveling_users (guild_id, user_id, level) VALUES (?, ?, ?)",
            (guild_id, user_id, level),
        )

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT user_id, xp, level FROM leveling_users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT ?",
            (guild_id, limit),
        )
        return [{"user_id": r["user_id"], "xp": r["xp"], "level": r["level"]} for r in rows]

    # -------------------- Roles -------------------- #
    async def set_autorole(self, guild_id: int, role_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO autoroles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id)
        )

    async def get_autorole(self, guild_id: int) -> Optional[int]:
        row = await self.fetchone("SELECT role_id FROM autoroles WHERE guild_id = ?", (guild_id,))
        return row["role_id"] if row else None

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
            (guild_id, message_id, emoji, role_id),
        )

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        await self.execute(
            "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (guild_id, message_id, emoji),
        )

    async def get_reaction_roles(self, guild_id: int, message_id: int) -> Dict[str, int]:
        rows = await self.fetchall(
            "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
            (guild_id, message_id),
        )
        return {row["emoji"]: row["role_id"] for row in rows}

    async def set_color_role(self, guild_id: int, user_id: int, role_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO color_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)",
            (guild_id, user_id, role_id),
        )

    async def get_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        row = await self.fetchone(
            "SELECT role_id FROM color_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return row["role_id"] if row else None

    # -------------------- Whispers -------------------- #
    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int):
        await self.execute(
            "INSERT INTO whispers (guild_id, user_id, thread_id, is_open) VALUES (?, ?, ?, 1)",
            (guild_id, user_id, thread_id),
        )

    async def close_whisper(self, guild_id: int, user_id: int, thread_id: int):
        await self.execute(
            "UPDATE whispers SET is_open = 0, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND user_id = ? AND thread_id = ?",
            (guild_id, user_id, thread_id),
        )

    async def get_open_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? AND is_open = 1",
            (guild_id,),
        )
        return [{"user_id": r["user_id"], "thread_id": r["thread_id"], "created_at": r["created_at"]} for r in rows]
        
    # -------------------- Moderation -------------------- #
    async def log_moderation_action(self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int):
        await self.execute(
            "INSERT INTO moderation_logs (guild_id, user_id, action, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, action, reason, moderator_id),
        )

    async def get_moderation_logs(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT case_id, action, reason, moderator_id, timestamp FROM moderation_logs WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return [{"case_id": r["case_id"], "action": r["action"], "reason": r["reason"], "moderator_id": r["moderator_id"], "timestamp": r["timestamp"]} for r in rows]

    # -------------------- Maintenance -------------------- #
    async def reset_guild_data(self, guild_id: int):
        tables = [
            "guild_settings", "leveling_users", "leveling_roles",
            "autoroles", "reaction_roles", "color_roles",
            "whispers", "moderation_logs",
        ]
        for table in tables:
            await self.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))

    async def vacuum(self):
        await self.execute("VACUUM")
