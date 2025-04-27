import os
import aiosqlite

class DBManager:
    def __init__(self, name='bot'):
        self.name = name
        self.db_path = f'data/{name}.db'
        self._connection = None
        self._cursor = None
        
    async def initialize(self):
        """Initialize database connection and tables"""
        try:
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            
            # Create connection in async context
            self._connection = await aiosqlite.connect(self.db_path)
            self._cursor = await self._connection.cursor()
            
            # Enable foreign keys
            await self._cursor.execute('PRAGMA foreign_keys = ON')
            
            # Create tables with proper constraints
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS logging_config (
                    guild_id INTEGER PRIMARY KEY REFERENCES guilds(guild_id) ON DELETE CASCADE,
                    channel_id INTEGER NOT NULL
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_roles (
                    guild_id INTEGER PRIMARY KEY REFERENCES guilds(guild_id) ON DELETE CASCADE,
                    role_id INTEGER,
                    enabled BOOLEAN DEFAULT TRUE
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    PRIMARY KEY (message_id, emoji)
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    UNIQUE(channel_id)
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS levels (
                    user_id INTEGER,
                    guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE,
                    level INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    last_xp TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            await self._cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE,
                    channel_id INTEGER,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            ''')
            
            await self._connection.commit()
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            raise

    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._cursor = None

    async def execute(self, query: str, params: tuple = ()):
        """Execute a query and commit changes"""
        try:
            await self._cursor.execute(query, params)
            await self._connection.commit()
        except Exception as e:
            print(f"Query execution error: {e}")
            raise

    async def fetch_one(self, query: str, params: tuple = ()):
        """Fetch a single row"""
        try:
            await self._cursor.execute(query, params)
            return await self._cursor.fetchone()
        except Exception as e:
            print(f"Query fetch error: {e}")
            raise

    async def fetch_all(self, query: str, params: tuple = ()):
        """Fetch all rows"""
        try:
            await self._cursor.execute(query, params)
            return await self._cursor.fetchall()
        except Exception as e:
            print(f"Query fetch error: {e}")
            raise

    # Guild Management
    async def ensure_guild_exists(self, guild_id: int, name: str):
        """Ensure guild exists in database"""
        await self.execute(
            'INSERT OR IGNORE INTO guilds (guild_id, name) VALUES (?, ?)',
            (guild_id, name)
        )

    # Auto Role Management
    async def set_auto_role(self, guild_id: int, role_id: int, enabled: bool):
        """Set or update auto role configuration"""
        await self.execute(
            'INSERT OR REPLACE INTO auto_roles (guild_id, role_id, enabled) VALUES (?, ?, ?)',
            (guild_id, role_id, enabled)
        )

    async def get_auto_role(self, guild_id: int):
        """Get auto role configuration"""
        return await self.fetch_one(
            'SELECT role_id, enabled FROM auto_roles WHERE guild_id = ?',
            (guild_id,)
        )

    # Reaction Roles Management
    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        """Add a reaction role binding"""
        await self.execute(
            'INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)',
            (message_id, emoji, role_id)
        )

    async def get_reaction_roles(self, message_id: int):
        """Get reaction role bindings for a message"""
        return await self.fetch_all(
            'SELECT emoji, role_id FROM reaction_roles WHERE message_id = ?',
            (message_id,)
        )

    # Ticket Management
    async def create_ticket(self, guild_id: int, channel_id: int, user_id: int):
        """Create a new ticket"""
        await self.execute(
            'INSERT INTO tickets (guild_id, channel_id, user_id) VALUES (?, ?, ?)',
            (guild_id, channel_id, user_id)
        )

    async def close_ticket(self, channel_id: int):
        """Close a ticket"""
        await self.execute(
            'UPDATE tickets SET closed_at = CURRENT_TIMESTAMP WHERE channel_id = ?',
            (channel_id,)
        )

    async def get_ticket_by_channel(self, channel_id: int):
        """Get ticket information by channel ID"""
        return await self.fetch_one(
            'SELECT * FROM tickets WHERE channel_id = ?',
            (channel_id,)
        )

    async def get_open_ticket(self, user_id: int, guild_id: int):
        """Check if user has an open ticket"""
        return await self.fetch_one(
            'SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND closed_at IS NULL',
            (user_id, guild_id)
        )

    # Level System Management
    async def add_user_leveling(self, user_id: int, guild_id: int, level: int, xp: int):
        """Add or update user level information"""
        await self.execute(
            '''
            INSERT OR REPLACE INTO levels (user_id, guild_id, level, xp, last_xp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (user_id, guild_id, level, xp)
        )

    async def get_user_leveling(self, user_id: int, guild_id: int):
        """Get user level information"""
        result = await self.fetch_one(
            'SELECT level, xp FROM levels WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        )
        return result if result else (0, 0)

    async def get_leaderboard(self, guild_id: int, limit: int = 10):
        """Get guild leaderboard"""
        return await self.fetch_all(
            'SELECT user_id, level, xp FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?',
            (guild_id, limit)
        )

    # Event Logging
    async def log_event(self, guild_id: int, user_id: int, action: str, details: str = None):
        """Log an event"""
        await self.execute(
            'INSERT INTO logs (guild_id, user_id, action, details) VALUES (?, ?, ?, ?)',
            (guild_id, user_id, action, details)
        )

    # Database Maintenance
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old logs and closed tickets"""
        try:
            await self.execute(
                'DELETE FROM logs WHERE timestamp < datetime("now", ?)',
                (f'-{days} days',)
            )
            await self.execute(
                'DELETE FROM tickets WHERE closed_at < datetime("now", ?)',
                (f'-{days} days',)
            )
        except Exception as e:
            print(f"Cleanup error: {e}")
            raise

    async def optimize(self):
        """Optimize database"""
        try:
            await self.execute('VACUUM')
            await self.execute('ANALYZE')
        except Exception as e:
            print(f"Optimization error: {e}")
            raise

    async def get_connection_stats(self):
        """Get database connection statistics"""
        stats = {}
        try:
            await self._cursor.execute('PRAGMA page_count')
            stats['page_count'] = (await self._cursor.fetchone())[0]
            await self._cursor.execute('PRAGMA page_size')
            stats['page_size'] = (await self._cursor.fetchone())[0]
            await self._cursor.execute('PRAGMA cache_size')
            stats['cache_size'] = (await self._cursor.fetchone())[0]
            return stats
        except Exception as e:
            print(f"Stats error: {e}")
            return None

    async def get_database_size(self):
        """Get database file size in bytes"""
        try:
            return os.path.getsize(self.db_path)
        except Exception as e:
            print(f"Size check error: {e}")
            return 0
