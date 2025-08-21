import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any


class DBManager:
    def __init__(self, db_path: str = "data/onwhisper.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
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
            await db.commit()

    async def get_guild_settings(self, guild_id: int) -> Dict[str, str]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT setting, value FROM guild_settings WHERE guild_id = ?", (guild_id,))
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO guild_settings (guild_id, setting, value) VALUES (?, ?, ?)",
                (guild_id, setting, value),
            )
            await db.commit()

    async def remove_guild_setting(self, guild_id: int, setting: str):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM guild_settings WHERE guild_id = ? AND setting = ?", (guild_id, setting))
            await db.commit()

    async def get_user_xp(self, guild_id: int, user_id: int) -> int:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT xp FROM leveling_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            )
            row = await cur.fetchone()
            return row[0] if row else 0

    async def set_user_xp(self, guild_id: int, user_id: int, xp: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?)",
                (guild_id, user_id, xp),
            )
            await db.commit()

    async def reset_user_xp(self, guild_id: int, user_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM leveling_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
                (guild_id, user_id, amount, amount),
            )
            await db.commit()

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, xp FROM leveling_users WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
                (guild_id, limit),
            )
            rows = await cur.fetchall()
            return [{"user_id": row[0], "xp": row[1]} for row in rows]

    async def get_level_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT level, role_id FROM leveling_roles WHERE guild_id = ?", (guild_id,))
            rows = await cur.fetchall()
            return [{"level": row[0], "role_id": row[1]} for row in rows]

    async def add_level_role(self, guild_id: int, level: int, role_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO leveling_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                (guild_id, level, role_id),
            )
            await db.commit()

    async def remove_level_role(self, guild_id: int, level: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM leveling_roles WHERE guild_id = ? AND level = ?", (guild_id, level))
            await db.commit()

    async def set_autorole(self, guild_id: int, role_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO autoroles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
            await db.commit()

    async def get_autorole(self, guild_id: int) -> Optional[int]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT role_id FROM autoroles WHERE guild_id = ?", (guild_id,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def clear_autorole(self, guild_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM autoroles WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
                (guild_id, message_id, emoji, role_id),
            )
            await db.commit()

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild_id, message_id, emoji),
            )
            await db.commit()

    async def get_reaction_roles(self, guild_id: int, message_id: int) -> List[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
                (guild_id, message_id),
            )
            rows = await cur.fetchall()
            return [{"emoji": row[0], "role_id": row[1]} for row in rows]

    async def assign_color_role(self, guild_id: int, user_id: int, role_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO color_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)",
                (guild_id, user_id, role_id),
            )
            await db.commit()

    async def clear_color_role(self, guild_id: int, user_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM color_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await db.commit()

    async def get_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT role_id FROM color_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO whispers (guild_id, user_id, thread_id, is_open) VALUES (?, ?, ?, 1)",
                (guild_id, user_id, thread_id),
            )
            await db.commit()

    async def close_whisper(self, guild_id: int, user_id: int, thread_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE whispers SET is_open = 0, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND user_id = ? AND thread_id = ?",
                (guild_id, user_id, thread_id),
            )
            await db.commit()

    async def get_whisper(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT thread_id, is_open, created_at, closed_at FROM whispers WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
                (guild_id, user_id),
            )
            row = await cur.fetchone()
            if row:
                return {
                    "thread_id": row[0],
                    "is_open": row[1],
                    "created_at": row[2],
                    "closed_at": row[3],
                }
            return None

    async def get_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, thread_id, is_open, created_at, closed_at FROM whispers WHERE guild_id = ?",
                (guild_id,),
            )
            rows = await cur.fetchall()
            return [
                {"user_id": row[0], "thread_id": row[1], "is_open": row[2], "created_at": row[3], "closed_at": row[4]}
                for row in rows
            ]

    async def log_moderation_action(self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO moderation_logs (guild_id, user_id, action, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, action, reason, moderator_id),
            )
            await db.commit()

    async def get_moderation_logs(self, guild_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            if user_id:
                cur = await db.execute(
                    "SELECT case_id, action, reason, moderator_id, timestamp FROM moderation_logs WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                )
            else:
                cur = await db.execute(
                    "SELECT case_id, user_id, action, reason, moderator_id, timestamp FROM moderation_logs WHERE guild_id = ?",
                    (guild_id,),
                )
            rows = await cur.fetchall()
            return [
                {
                    "case_id": row[0],
                    "user_id": row[1] if not user_id else user_id,
                    "action": row[2] if not user_id else row[1],
                    "reason": row[3] if not user_id else row[2],
                    "moderator_id": row[4] if not user_id else row[3],
                    "timestamp": row[5] if not user_id else row[4],
                }
                for row in rows
            ]

    async def reset_tables(self, guild_id: int):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM leveling_users WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM leveling_roles WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM autoroles WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM reaction_roles WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM color_roles WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM whispers WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM moderation_logs WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def vacuum(self):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("VACUUM")
            await db.commit()

    async def migrate_schema(self):
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                -- Example placeholder for schema migrations
                """
            )
            await db.commit()
