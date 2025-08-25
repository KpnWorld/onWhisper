import aiosqlite
import asyncio
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("onWhisper.DBManager")


class DBManager:
    def __init__(self, db_path: str = "data/onwhisper.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        logger.debug(f"DBManager initialized with db_path={db_path}")

    async def init_db(self):
        logger.info("Initializing database schema...")
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
        logger.info("Database initialized successfully.")

    # Guild Settings

    async def get_guild_settings(self, guild_id: int) -> Dict[str, str]:
        logger.debug(f"Fetching guild settings for guild_id={guild_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT setting, value FROM guild_settings WHERE guild_id = ?", (guild_id,)
            )
            rows = await cur.fetchall()
            settings = {row[0]: row[1] for row in rows}
            logger.debug(f"Settings retrieved: {settings}")
            return settings

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        logger.info(f"Setting guild setting: guild_id={guild_id}, {setting}={value}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO guild_settings (guild_id, setting, value) VALUES (?, ?, ?)",
                (guild_id, setting, value),
            )
            await db.commit()

    async def remove_guild_setting(self, guild_id: int, setting: str):
        logger.info(f"Removing guild setting: guild_id={guild_id}, setting={setting}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM guild_settings WHERE guild_id = ? AND setting = ?",
                (guild_id, setting),
            )
            await db.commit()

    # Leveling System

    async def get_user_xp(self, guild_id: int, user_id: int) -> int:
        logger.debug(f"Fetching XP: guild_id={guild_id}, user_id={user_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT xp FROM leveling_users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cur.fetchone()
            xp = row[0] if row else 0
            logger.debug(f"XP result: {xp}")
            return xp

    async def set_user_xp(self, guild_id: int, user_id: int, xp: int):
        logger.info(f"Setting XP: guild_id={guild_id}, user_id={user_id}, xp={xp}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?)",
                (guild_id, user_id, xp),
            )
            await db.commit()

    async def reset_user_xp(self, guild_id: int, user_id: int):
        logger.warning(f"Resetting XP: guild_id={guild_id}, user_id={user_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM leveling_users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await db.commit()

    async def add_xp(self, guild_id: int, user_id: int, amount: int):
        logger.info(f"Adding XP: guild_id={guild_id}, user_id={user_id}, amount={amount}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO leveling_users (guild_id, user_id, xp) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?",
                (guild_id, user_id, amount, amount),
            )
            await db.commit()

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        logger.info(f"Assigning level role: guild_id={guild_id}, level={level}, role_id={role_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO leveling_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                (guild_id, level, role_id),
            )
            await db.commit()

    async def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        logger.debug(f"Fetching level roles for guild_id={guild_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT level, role_id FROM leveling_roles WHERE guild_id = ?", (guild_id,)
            )
            rows = await cur.fetchall()
            result = {row[0]: row[1] for row in rows}
            logger.debug(f"Level roles: {result}")
            return result

    # Roles System

    async def set_autorole(self, guild_id: int, role_id: int):
        logger.info(f"Setting autorole: guild_id={guild_id}, role_id={role_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO autoroles (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role_id),
            )
            await db.commit()

    async def get_autorole(self, guild_id: int) -> Optional[int]:
        logger.debug(f"Fetching autorole for guild_id={guild_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT role_id FROM autoroles WHERE guild_id = ?", (guild_id,)
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        logger.info(f"Adding reaction role: guild_id={guild_id}, message_id={message_id}, emoji={emoji}, role_id={role_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
                (guild_id, message_id, emoji, role_id),
            )
            await db.commit()

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        logger.info(f"Removing reaction role: guild_id={guild_id}, message_id={message_id}, emoji={emoji}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild_id, message_id, emoji),
            )
            await db.commit()

    async def get_reaction_roles(self, guild_id: int, message_id: int) -> Dict[str, int]:
        logger.debug(f"Fetching reaction roles: guild_id={guild_id}, message_id={message_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
                (guild_id, message_id),
            )
            rows = await cur.fetchall()
            result = {row[0]: row[1] for row in rows}
            logger.debug(f"Reaction roles: {result}")
            return result

    async def set_color_role(self, guild_id: int, user_id: int, role_id: int):
        logger.info(f"Setting color role: guild_id={guild_id}, user_id={user_id}, role_id={role_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO color_roles (guild_id, user_id, role_id) VALUES (?, ?, ?)",
                (guild_id, user_id, role_id),
            )
            await db.commit()

    async def get_color_role(self, guild_id: int, user_id: int) -> Optional[int]:
        logger.debug(f"Fetching color role: guild_id={guild_id}, user_id={user_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT role_id FROM color_roles WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    # Whisper System

    async def create_whisper(self, guild_id: int, user_id: int, thread_id: int):
        logger.info(f"Creating whisper: guild_id={guild_id}, user_id={user_id}, thread_id={thread_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO whispers (guild_id, user_id, thread_id, is_open) VALUES (?, ?, ?, 1)",
                (guild_id, user_id, thread_id),
            )
            await db.commit()

    async def close_whisper(self, guild_id: int, user_id: int, thread_id: int):
        logger.info(f"Closing whisper: guild_id={guild_id}, user_id={user_id}, thread_id={thread_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE whispers SET is_open = 0, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND user_id = ? AND thread_id = ?",
                (guild_id, user_id, thread_id),
            )
            await db.commit()

    async def get_open_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching open whispers for guild_id={guild_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, thread_id, created_at FROM whispers WHERE guild_id = ? AND is_open = 1",
                (guild_id,),
            )
            rows = await cur.fetchall()
            result = [{"user_id": r[0], "thread_id": r[1], "created_at": r[2]} for r in rows]
            logger.debug(f"Open whispers: {result}")
            return result

    # Moderation Logs

    async def log_moderation_action(
        self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int
    ):
        logger.info(f"Logging moderation action: guild_id={guild_id}, user_id={user_id}, action={action}, moderator={moderator_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO moderation_logs (guild_id, user_id, action, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, action, reason, moderator_id),
            )
            await db.commit()

    async def get_moderation_logs(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching moderation logs: guild_id={guild_id}, user_id={user_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT case_id, action, reason, moderator_id, timestamp FROM moderation_logs WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            rows = await cur.fetchall()
            result = [
                {"case_id": r[0], "action": r[1], "reason": r[2], "moderator_id": r[3], "timestamp": r[4]}
                for r in rows
            ]
            logger.debug(f"Moderation logs: {result}")
            return result

    # Maintenance

    async def reset_guild_data(self, guild_id: int):
        logger.warning(f"Resetting all data for guild_id={guild_id}")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            for table in [
                "guild_settings",
                "leveling_users",
                "leveling_roles",
                "autoroles",
                "reaction_roles",
                "color_roles",
                "whispers",
                "moderation_logs",
            ]:
                await db.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def vacuum(self):
        logger.info("Running VACUUM on database")
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute("VACUUM")
            await db.commit()
