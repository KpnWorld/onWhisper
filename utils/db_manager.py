import aiosqlite
from datetime import datetime


class DBManager:

    def __init__(self, db_path='bot.db'):
        self.db_path = db_path
        self._db_connection = None  # Store the connection here

    async def connect(self):
        """Establish a new connection if one doesn't already exist."""
        if self._db_connection is None:
            self._db_connection = await aiosqlite.connect(self.db_path)
        return self._db_connection

    async def initialize(self):
        """Initialize the database, creating tables if they don't exist."""
        conn = await self.connect()  # Use the single connection
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

            await conn.commit()

    async def close(self):
        """Close the connection when the bot shuts down."""
        if self._db_connection:
            await self._db_connection.close()

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
        async with (await self.connect()).cursor() as cursor:
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

            await cursor.connection.commit()
