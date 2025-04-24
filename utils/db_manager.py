import aiosqlite
from datetime import datetime
import threading
import asyncio

class DBManager:
    def __init__(self, db_path='bot.db'):
        self.db_path = db_path
        self._connections = {}
        self._lock = asyncio.Lock()

    async def connect(self):
        """Get a connection for the current thread or create a new one."""
        thread_id = threading.get_ident()
        if thread_id not in self._connections or self._connections[thread_id] is None:
            async with self._lock:
                if thread_id not in self._connections or self._connections[thread_id] is None:
                    self._connections[thread_id] = await aiosqlite.connect(self.db_path)
        return self._connections[thread_id]

    async def initialize(self):
        """Initialize the database, creating tables if they don't exist."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            # Leveling Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS leveling (
                    user_id INTEGER,
                    guild_id INTEGER,
                    level INTEGER,
                    xp INTEGER,
                    PRIMARY KEY (user_id, guild_id)
                );
            ''')

            # Scheduled Messages Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message TEXT,
                    interval INTEGER,
                    last_sent TIMESTAMP
                );
            ''')

            # Verification Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS verification (
                    guild_id INTEGER,
                    user_id INTEGER,
                    is_verified INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );
            ''')

            # Auto Role Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS auto_role (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER,
                    enabled INTEGER DEFAULT 1
                );
            ''')

            # Reaction Roles Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    PRIMARY KEY (message_id, emoji)
                );
            ''')

            # Logs Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    action TEXT,
                    timestamp TEXT,
                    details TEXT
                );
            ''')

            # Guild Stats Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS guild_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    joins INTEGER DEFAULT 0,
                    leaves INTEGER DEFAULT 0,
                    messages_sent INTEGER DEFAULT 0
                );
            ''')

            # Bot Stats Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS bot_stats (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_type TEXT,
                    stat_value INTEGER,
                    timestamp TEXT
                );
            ''')

            # Verification Settings Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS verification_settings (
                    guild_id INTEGER PRIMARY KEY,
                    verification_message TEXT,
                    verification_channel_id INTEGER,
                    enabled INTEGER DEFAULT 1
                );
            ''')

            # Logging Config Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS logging_config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                );
            ''')

            # Tickets Table
            await cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER UNIQUE,
                    user_id INTEGER,
                    status TEXT DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            await conn.commit()

    async def close(self):
        """Close all connections."""
        async with self._lock:
            for conn in self._connections.values():
                if conn:
                    await conn.close()
            self._connections.clear()

    # ---- Leveling ----
    async def add_user_leveling(self, user_id, guild_id, level, xp):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                INSERT OR REPLACE INTO leveling (user_id, guild_id, level, xp)
                VALUES (?, ?, ?, ?);
            ''', (user_id, guild_id, level, xp))
            await conn.commit()

    async def get_user_leveling(self, user_id, guild_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT level, xp FROM leveling WHERE user_id = ? AND guild_id = ?;
            ''', (user_id, guild_id))
            result = await cursor.fetchone()
            return result if result else (0, 0)

    # ---- Scheduled Messages ----
    async def add_scheduled_message(self, guild_id, channel_id, message,
                                    interval):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            timestamp = datetime.utcnow().isoformat()
            await cursor.execute(
                ''' 
                INSERT INTO scheduled_messages (guild_id, channel_id, message, interval, last_sent)
                VALUES (?, ?, ?, ?, ?);
            ''', (guild_id, channel_id, message, interval, timestamp))
            await conn.commit()

    async def get_scheduled_messages(self, guild_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT message_id, channel_id, message, interval, last_sent FROM scheduled_messages
                WHERE guild_id = ?;
            ''', (guild_id, ))
            return await cursor.fetchall()

    async def update_last_sent_message(self, message_id, timestamp):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                UPDATE scheduled_messages SET last_sent = ? WHERE message_id = ?;
            ''', (timestamp, message_id))
            await conn.commit()

    # ---- Verification ----
    async def set_verified(self, guild_id, user_id, verified):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                INSERT OR REPLACE INTO verification (guild_id, user_id, is_verified)
                VALUES (?, ?, ?);
            ''', (guild_id, user_id, verified))
            await conn.commit()

    async def get_verified(self, guild_id, user_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT is_verified FROM verification WHERE guild_id = ? AND user_id = ?;
            ''', (guild_id, user_id))
            result = await cursor.fetchone()
            return result[0] if result else 0

    # ---- Auto Role ----
    async def set_auto_role(self, guild_id, role_id, enabled):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                INSERT OR REPLACE INTO auto_role (guild_id, role_id, enabled)
                VALUES (?, ?, ?);
            ''', (guild_id, role_id, enabled))
            await conn.commit()

    async def get_auto_role(self, guild_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT role_id, enabled FROM auto_role WHERE guild_id = ?;
            ''', (guild_id, ))
            return await cursor.fetchone()

    # ---- Reaction Roles ----
    async def add_reaction_role(self, message_id, emoji, role_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                INSERT INTO reaction_roles (message_id, emoji, role_id)
                VALUES (?, ?, ?);
            ''', (message_id, emoji, role_id))
            await conn.commit()

    async def get_reaction_roles(self, message_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT emoji, role_id FROM reaction_roles WHERE message_id = ?;
            ''', (message_id, ))
            return await cursor.fetchall()

    # ---- Logging ----
    async def log_event(self, guild_id, user_id, action, details):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            timestamp = datetime.utcnow().isoformat()
            await cursor.execute(
                ''' 
                INSERT INTO logs (guild_id, user_id, action, timestamp, details)
                VALUES (?, ?, ?, ?, ?);
            ''', (guild_id, user_id, action, timestamp, details))
            await conn.commit()

    # ---- Guild Stats ----
    async def log_guild_stat(self,
                             guild_id,
                             joins=0,
                             leaves=0,
                             messages_sent=0):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            timestamp = datetime.utcnow().isoformat()
            await cursor.execute(
                ''' 
                INSERT INTO guild_stats (guild_id, timestamp, joins, leaves, messages_sent)
                VALUES (?, ?, ?, ?, ?);
            ''', (guild_id, timestamp, joins, leaves, messages_sent))
            await conn.commit()

    async def get_guild_stats(self, guild_id):
        conn = await self.connect()  # Use the single connection
        async with conn.cursor() as cursor:
            await cursor.execute(
                ''' 
                SELECT * FROM guild_stats WHERE guild_id = ? ORDER BY timestamp DESC LIMIT 1;
            ''', (guild_id, ))
            return await cursor.fetchone()

    async def execute(self, query: str, params: tuple = None):
        """Execute a raw SQL query with optional parameters."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            if params:
                await cursor.execute(query, params)
            else:
                await cursor.execute(query)
            await conn.commit()
            return cursor

    async def ensure_guild_exists(self, guild_id: int, guild_name: str):
        """Ensure guild exists in all necessary tables with default settings."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            # Add guild to verification settings if not exists
            await cursor.execute('''
                INSERT OR IGNORE INTO verification_settings 
                (guild_id, verification_message, enabled)
                VALUES (?, 'Please verify to access the server.', 1)
            ''', (guild_id,))

            # Add guild to auto role if not exists
            await cursor.execute('''
                INSERT OR IGNORE INTO auto_role 
                (guild_id, enabled)
                VALUES (?, 1)
            ''', (guild_id,))

            # Initialize guild stats
            await cursor.execute('''
                INSERT OR IGNORE INTO guild_stats 
                (guild_id, timestamp)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (guild_id,))

            await conn.commit()

    async def create_ticket(self, guild_id: int, channel_id: int, user_id: int):
        """Create a new ticket record."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO tickets (guild_id, channel_id, user_id, status)
                VALUES (?, ?, ?, 'open')
                """,
                (guild_id, channel_id, user_id)
            )
            await conn.commit()

    async def get_open_ticket(self, user_id: int, guild_id: int):
        """Get user's open ticket if exists."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT channel_id FROM tickets
                WHERE user_id = ? AND guild_id = ? AND status = 'open'
                """,
                (user_id, guild_id)
            )
            result = await cursor.fetchone()
            return result[0] if result else None

    async def get_ticket_by_channel(self, channel_id: int):
        """Get ticket by channel ID."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT * FROM tickets 
                WHERE channel_id = ? AND status = 'open'
                """,
                (channel_id,)
            )
            return await cursor.fetchone()

    async def close_ticket(self, channel_id: int):
        """Close a ticket."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                UPDATE tickets 
                SET status = 'closed' 
                WHERE channel_id = ?
                """,
                (channel_id,)
            )
            await conn.commit()

    # Add new database methods
    async def fetch_all(self, query: str, params: tuple = None):
        """Execute a query and fetch all results."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            if params:
                await cursor.execute(query, params)
            else:
                await cursor.execute(query)
            rows = await cursor.fetchall()
            return rows

    async def fetch_one(self, query: str, params: tuple = None):
        """Execute a query and fetch one result."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            if params:
                await cursor.execute(query, params)
            else:
                await cursor.execute(query)
            row = await cursor.fetchone()
            return row

    async def get_leaderboard(self, guild_id: int, limit: int = 10):
        """Get the XP leaderboard for a guild."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT user_id, level, xp
                FROM leveling
                WHERE guild_id = ?
                ORDER BY xp DESC
                LIMIT ?
                """,
                (guild_id, limit)
            )
            return await cursor.fetchall()

    async def set_verification_settings(self, guild_id: int, role_id: int, channel_id: int, 
                                     expiry_days: int, method: str, message: str):
        """Set verification settings for a guild."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT OR REPLACE INTO verification_settings 
                (guild_id, role_id, channel_id, expiry_days, verification_method, verification_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (guild_id, role_id, channel_id, expiry_days, method, message)
            )
            await conn.commit()

    async def remove_auto_role(self, guild_id: int, role_id: int):
        """Remove an auto role from a guild."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM auto_role 
                WHERE guild_id = ? AND role_id = ?
                """,
                (guild_id, role_id)
            )
            await conn.commit()

    async def increment_stat(self, guild_id: int, stat_type: str):
        """Increment a guild statistic."""
        conn = await self.connect()
        async with conn.cursor() as cursor:
            await cursor.execute(
                f"""
                UPDATE guild_stats 
                SET {stat_type} = {stat_type} + 1
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
            await conn.commit()
