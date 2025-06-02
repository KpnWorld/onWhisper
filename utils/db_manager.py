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
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER,
                setting TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, setting)
            )""",
            """CREATE TABLE IF NOT EXISTS xp (
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                last_message_ts TIMESTAMP,
                last_message TEXT,
                last_xp_gain INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS mod_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                moderator_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS whispers (
                guild_id INTEGER,
                whisper_id TEXT,
                user_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                is_closed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                PRIMARY KEY (guild_id, whisper_id)
            )""",
            """CREATE TABLE IF NOT EXISTS feature_settings (
                guild_id INTEGER,
                feature TEXT,
                enabled BOOLEAN DEFAULT FALSE,
                options_json TEXT,
                PRIMARY KEY (guild_id, feature)
            )""",
            """CREATE TABLE IF NOT EXISTS autoroles (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )""",
            """CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, message_id, emoji)
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
        -- Config Indexes
        CREATE INDEX IF NOT EXISTS idx_guild_settings ON guild_settings(guild_id);

        -- Role Management Indexes
        CREATE INDEX IF NOT EXISTS idx_autoroles_guild ON autoroles(guild_id);
        CREATE INDEX IF NOT EXISTS idx_color_roles_guild ON color_roles(guild_id);
        CREATE INDEX IF NOT EXISTS idx_reaction_roles_guild ON reaction_roles(guild_id, message_id);
        CREATE INDEX IF NOT EXISTS idx_level_roles_guild ON level_roles(guild_id);

        -- XP/Leveling Indexes
        CREATE INDEX IF NOT EXISTS idx_xp_leaderboard ON xp(guild_id, xp DESC);
        CREATE INDEX IF NOT EXISTS idx_xp_level ON xp(guild_id, level);

        -- Logging & Mod Actions Indexes
        CREATE INDEX IF NOT EXISTS idx_logs_guild ON logs(guild_id);
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_logs_type ON logs(guild_id, event_type);

        CREATE INDEX IF NOT EXISTS idx_mod_actions_guild ON mod_actions(guild_id);
        CREATE INDEX IF NOT EXISTS idx_mod_actions_user ON mod_actions(guild_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_mod_actions_timestamp ON mod_actions(timestamp DESC);

        -- Whispers Indexes
        CREATE INDEX IF NOT EXISTS idx_whispers_user ON whispers(guild_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_whispers_active ON whispers(guild_id) WHERE is_closed = FALSE;
        CREATE INDEX IF NOT EXISTS idx_whispers_thread ON whispers(thread_id);
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

    # -------------------- Leveling/XP Methods --------------------
    
    async def add_xp(self, guild_id: int, user_id: int, xp_amount: int):
        """Add XP to a user, creating the entry if it doesn't exist"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO xp (guild_id, user_id, xp)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?
            """, (guild_id, user_id, xp_amount, xp_amount))

    async def set_level(self, guild_id: int, user_id: int, level: int):
        """Set a user's level directly"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO xp (guild_id, user_id, level)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET level = ?
            """, (guild_id, user_id, level, level))

    async def update_user_xp(self, guild_id: int, user_id: int, xp: int, level: int) -> None:
        """Basic XP update without message tracking"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO xp (guild_id, user_id, xp, level)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE 
                SET xp = excluded.xp, level = excluded.level
            """, (guild_id, user_id, xp, level))

    async def update_user_xp_with_message(self, guild_id: int, user_id: int, xp: int, level: int, xp_gain: int, message: str) -> None:
        """Update user's XP with message tracking"""
        current_time = time.time()
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO xp (
                    guild_id, user_id, xp, level, 
                    last_message_ts, last_xp_gain, last_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE 
                SET xp = excluded.xp,
                    level = excluded.level,
                    last_message_ts = excluded.last_message_ts,
                    last_xp_gain = excluded.last_xp_gain,
                    last_message = excluded.last_message
            """, (guild_id, user_id, xp, level, current_time, xp_gain, message))

    async def get_user_xp(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's XP and level information"""
        async with self.connection.execute(
            "SELECT * FROM xp WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([column[0] for column in cursor.description], row))
            return None

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the XP leaderboard for a guild"""
        async with self.connection.execute(
            """SELECT user_id, xp, level FROM xp
            WHERE guild_id = ? ORDER BY xp DESC LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    async def get_leaderboard_page(self, guild_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get a paginated XP leaderboard for a guild
        
        Args:
            guild_id: The guild ID to get leaderboard for
            limit: Number of entries to return (default: 10)
            offset: Number of entries to skip (default: 0)
        """
        async with self.connection.execute(
            """SELECT user_id, xp, level FROM xp
            WHERE guild_id = ? ORDER BY xp DESC LIMIT ? OFFSET ?""",
            (guild_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    async def get_total_ranked_users(self, guild_id: int) -> int:
        """Get total number of users with XP in the guild"""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM xp WHERE guild_id = ? AND xp > 0",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_user_rank(self, guild_id: int, user_id: int) -> Optional[int]:
        """Get user's rank in the guild"""
        async with self.connection.execute(
            """WITH ranked AS (
                SELECT user_id, RANK() OVER (ORDER BY xp DESC) as rank
                FROM xp WHERE guild_id = ? AND xp > 0
            )
            SELECT rank FROM ranked WHERE user_id = ?""",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None    
            
    async def get_level_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get level configuration for a guild from feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        if not feature_settings or not feature_settings['enabled']:
            return None

        options = feature_settings['options']
        return {
            'cooldown': options.get('cooldown', 60),
            'min_xp': options.get('min_xp', 15),
            'max_xp': options.get('max_xp', 25)
        }    
        
    async def set_level_config(self, guild_id: int, cooldown: int, min_xp: int, max_xp: int):
        """Set level configuration for a guild using feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        options = feature_settings['options'] if feature_settings else {}
        
        options.update({
            'cooldown': cooldown,
            'min_xp': min_xp,
            'max_xp': max_xp
        })
        
        await self.set_feature_settings(
            guild_id,
            "leveling",
            True,
            options
        )

    # -------------------- Role Management Methods --------------------

    async def add_autorole(self, guild_id: int, role_id: int):
        """Add an autorole to a guild"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT OR IGNORE INTO autoroles (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role_id)
            )

    async def remove_autorole(self, guild_id: int, role_id: int):
        """Remove an autorole from a guild"""
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM autoroles WHERE guild_id = ? AND role_id = ?",
                (guild_id, role_id)
            )

    async def get_autoroles(self, guild_id: int) -> List[int]:
        """Get all autoroles for a guild"""
        async with self.connection.execute(
            "SELECT role_id FROM autoroles WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        """Set a role reward for a specific level using feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        options = feature_settings['options'] if feature_settings else {}
        
        # Initialize or get existing role rewards
        role_rewards = options.get('role_rewards', {})
        role_rewards[str(level)] = role_id  # Convert level to string for JSON compatibility
        options['role_rewards'] = role_rewards
        
        await self.set_feature_settings(
            guild_id,
            "leveling",
            True,
            options
        )

    async def delete_level_role(self, guild_id: int, level: int):
        """Remove a role reward for a specific level using feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        if not feature_settings or not feature_settings['enabled']:
            return
            
        options = feature_settings['options']
        role_rewards = options.get('role_rewards', {})
        if str(level) in role_rewards:
            del role_rewards[str(level)]
            options['role_rewards'] = role_rewards
            await self.set_feature_settings(guild_id, "leveling", True, options)

    async def get_level_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all level role rewards using feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        if not feature_settings or not feature_settings['enabled']:
            return []
            
        role_rewards = feature_settings['options'].get('role_rewards', {})
        return [{'level': int(level), 'role_id': int(role_id)} 
                for level, role_id in role_rewards.items()]

    # -------------------- Config Methods --------------------

    async def set_guild_setting(self, guild_id: int, setting: str, value: str):
        """Set a guild configuration setting"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO guild_settings (guild_id, setting, value)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, setting) DO UPDATE SET value = ?
            """, (guild_id, setting, value, value))

    async def get_guild_setting(self, guild_id: int, setting: str) -> Optional[str]:
        """Get a guild configuration setting"""
        async with self.connection.execute(
            "SELECT value FROM guild_settings WHERE guild_id = ? AND setting = ?",
            (guild_id, setting)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_guild_settings(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all settings for a guild"""
        async with self.connection.execute(
            "SELECT setting, value FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip(['setting', 'value'], row)) for row in rows]

    # -------------------- Logging & Mod Actions --------------------

    async def insert_log(self, guild_id: int, event_type: str, description: str):
        """Insert a new log entry"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT INTO logs (guild_id, event_type, description) VALUES (?, ?, ?)",
                (guild_id, event_type, description)
            )

    async def insert_mod_action(self, guild_id: int, user_id: int, action: str, reason: str, moderator_id: int):
        """Insert a new moderation action"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT INTO mod_actions (guild_id, user_id, action, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, action, reason, moderator_id)
            )    
    async def get_logs_filtered(self, guild_id: int, event_type: Optional[str] = None, since_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get filtered logs for a guild"""
        query = "SELECT * FROM logs WHERE guild_id = ?"
        params: List[Any] = [guild_id]
        
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if since_days is not None:
            query += " AND timestamp >= datetime('now', ?)"
            params.append(f'-{since_days} days')
            
        query += " ORDER BY timestamp DESC"
        
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    async def get_mod_actions_page(self, guild_id: int, limit: int, offset: int) -> List[Dict[str, Any]]:
        """Get a paginated list of moderation actions"""
        async with self.connection.execute(
            """SELECT * FROM mod_actions 
            WHERE guild_id = ? 
            ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            (guild_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    # -------------------- Whispers --------------------

    async def create_whisper(self, guild_id: int, whisper_id: str, user_id: int, thread_id: int):
        """Create a new whisper thread"""
        async with self.transaction() as tr:
            await tr.execute(
                "INSERT INTO whispers (guild_id, whisper_id, user_id, thread_id) VALUES (?, ?, ?, ?)",
                (guild_id, whisper_id, user_id, thread_id)
            )

    async def close_whisper(self, guild_id: int, whisper_id: str):
        """Close an existing whisper thread"""        
        async with self.transaction() as tr:
            await tr.execute(
                "UPDATE whispers SET is_closed = 1, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND whisper_id = ?",
                (guild_id, whisper_id)
            )

    async def delete_whisper(self, guild_id: int, whisper_id: str):
        """Delete a whisper thread from database"""
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM whispers WHERE guild_id = ? AND whisper_id = ?",
                (guild_id, whisper_id)
            )

    async def get_whispers_by_user(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all whispers for a specific user"""
        async with self.connection.execute(
            "SELECT * FROM whispers WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    async def get_all_whispers(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all whispers for a guild"""
        async with self.connection.execute(
            "SELECT * FROM whispers WHERE guild_id = ? ORDER BY created_at DESC",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]

    # -------------------- Deletion & Cleanup --------------------

    async def delete_guild_data(self, guild_id: int):
        """Delete all data associated with a guild"""
        async with self.transaction() as tr:
            queries = [
                "DELETE FROM guild_settings WHERE guild_id = ?",
                "DELETE FROM feature_settings WHERE guild_id = ?",
                "DELETE FROM autoroles WHERE guild_id = ?",
                "DELETE FROM color_roles WHERE guild_id = ?",
                "DELETE FROM reaction_roles WHERE guild_id = ?",
                "DELETE FROM xp WHERE guild_id = ?",
                "DELETE FROM logs WHERE guild_id = ?",
                "DELETE FROM mod_actions WHERE guild_id = ?",
                "DELETE FROM whispers WHERE guild_id = ?"
            ]
            for query in queries:
                await tr.execute(query, (guild_id,))

    async def delete_user_data(self, guild_id: int, user_id: int):
        """Delete all data associated with a user in a guild"""
        async with self.transaction() as tr:
            queries = [
                "DELETE FROM xp WHERE guild_id = ? AND user_id = ?",
                "DELETE FROM mod_actions WHERE guild_id = ? AND user_id = ?",
                "DELETE FROM whispers WHERE guild_id = ? AND user_id = ?"
            ]
            for query in queries:
                await tr.execute(query, (guild_id, user_id))

    async def purge_old_logs(self, days: int = 30):
        """Purge logs and mod actions older than specified days"""
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM logs WHERE timestamp < datetime('now', ?)",
                (f'-{days} days',)
            )
            await tr.execute(
                "DELETE FROM mod_actions WHERE timestamp < datetime('now', ?)",
                (f'-{days} days',)
            )

    # -------------------- Reaction Role Methods --------------------
    
    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        """Add a reaction role mapping"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, message_id, emoji) DO UPDATE SET role_id = ?
            """, (guild_id, message_id, emoji, role_id, role_id))

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        """Remove a reaction role mapping"""
        async with self.transaction() as tr:
            await tr.execute(
                "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild_id, message_id, emoji)
            )

    async def get_reaction_role(self, guild_id: int, message_id: int, emoji: str) -> Optional[int]:
        """Get the role ID for a specific reaction role mapping"""
        async with self.connection.execute(
            "SELECT role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (guild_id, message_id, emoji)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_message_reaction_roles(self, guild_id: int, message_id: int) -> List[Dict[str, Any]]:
        """Get all reaction roles for a specific message"""
        async with self.connection.execute(
            "SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
            (guild_id, message_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{'emoji': row[0], 'role_id': row[1]} for row in rows]

    async def get_user_cooldown(self, guild_id: int, user_id: int) -> Optional[float]:
        """Get user's last message timestamp for cooldown"""
        async with self.connection.execute(
            "SELECT last_message_ts FROM xp WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return float(row[0])
            return None

    async def update_user_level(self, guild_id: int, user_id: int, level: int):
        """Update user's level only"""
        async with self.transaction() as tr:
            await tr.execute("""
                UPDATE xp SET level = ? 
                WHERE guild_id = ? AND user_id = ?
            """, (level, guild_id, user_id))

    async def get_level_roles_for_level(self, guild_id: int, level: int) -> List[int]:
        """Get all role rewards for a specific level using feature settings"""
        feature_settings = await self.get_feature_settings(guild_id, "leveling")
        if not feature_settings or not feature_settings['enabled']:
            return []
            
        role_rewards = feature_settings['options'].get('role_rewards', {})
        role_id = role_rewards.get(str(level))
        return [int(role_id)] if role_id else []

    # -------------------- Feature Settings Methods --------------------

    async def get_feature_settings(self, guild_id: int, feature: str) -> Optional[Dict[str, Any]]:
        """Get feature settings for a specific feature in a guild"""
        async with self.connection.execute(
            "SELECT enabled, options_json FROM feature_settings WHERE guild_id = ? AND feature = ?",
            (guild_id, feature)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'enabled': bool(row[0]),
                    'options': json.loads(row[1]) if row[1] else {}
                }
            return None

    async def set_feature_settings(self, guild_id: int, feature: str, enabled: bool, options: Dict[str, Any]):
        """Set feature settings for a specific feature in a guild"""
        async with self.transaction() as tr:
            await tr.execute("""
                INSERT INTO feature_settings (guild_id, feature, enabled, options_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, feature) DO UPDATE 
                SET enabled = ?, options_json = ?
            """, (guild_id, feature, enabled, json.dumps(options), enabled, json.dumps(options)))

