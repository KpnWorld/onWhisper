import os
import sqlite3
import logging
import asyncio
import time
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class AsyncCursorContextManager:
    def __init__(self, db):
        self.db = db
        self.cursor = None
        self.conn = None
        self._transaction = False

    async def __aenter__(self):
        """Enter the cursor context with proper error handling"""
        try:
            self.conn = await self.db.get_connection()
            self.cursor = await self.conn.cursor()
            return self.cursor
        except Exception as e:
            logger.error(f"Error creating cursor: {e}")
            if self.cursor:
                await self.cursor.close()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the cursor context with proper cleanup"""
        try:
            if exc_type is None:
                # Only commit if no exception occurred
                await self.conn.commit()
            else:
                # Rollback on exception
                await self.conn.rollback()
                logger.error(f"Transaction rolled back due to {exc_type.__name__}: {exc_val}")
        except Exception as e:
            logger.error(f"Error in cursor cleanup: {e}")
            # Attempt rollback on cleanup error
            try:
                await self.conn.rollback()
            except:
                pass
            raise
        finally:
            if self.cursor:
                await self.cursor.close()

    async def begin(self):
        """Start a transaction"""
        self._transaction = True
        await self.cursor.execute("BEGIN TRANSACTION")

    async def commit(self):
        """Commit the current transaction"""
        if self._transaction:
            await self.conn.commit()
            self._transaction = False

    async def rollback(self):
        """Rollback the current transaction"""
        if self._transaction:
            await self.conn.rollback()
            self._transaction = False

class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.db_path = f"db/{db_name}.db"
        self._connection = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self._transaction_lock = asyncio.Lock()
        self._closing = False
        self._pool = []
        self._max_connections = 5
        self._last_connection_check = time.time()
        # Remove immediate initialization

    async def ensure_initialized(self):
        """Ensure the database is initialized before use"""
        if not self._initialized:
            await self.initialize()
        return self._initialized

    async def initialize(self):
        """Initialize the database connection"""
        if not self._initialized:
            try:
                if not os.path.exists('db'):
                    os.makedirs('db')
                await self._initialize()
                self._initialized = True
                logger.info("Database manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise

    async def _initialize(self):
        """Initialize the database connection with optimized settings"""
        self._connection = await self._create_connection()
        
        # Enable WAL mode for better concurrency
        await self._connection.execute("PRAGMA journal_mode=WAL")
        
        # Optimize cache settings
        await self._connection.execute("PRAGMA cache_size=-2000") # 2MB cache
        await self._connection.execute("PRAGMA page_size=4096")
        
        # Other performance optimizations
        await self._connection.execute("PRAGMA temp_store=MEMORY")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA mmap_size=2147483648") # 2GB
        
        # Ensure foreign key support
        await self._connection.execute("PRAGMA foreign_keys=ON")
        
        await self.setup_database()

    async def _ensure_initialized(self):
        """Ensure database is initialized before operations"""
        if not self._initialized:
            await self.ensure_initialized()
        return self._initialized

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection"""
        conn = await aiosqlite.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better concurrency
        return conn

    async def get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection with proper error handling"""
        await self.ensure_initialized()
        if self._closing:
            raise RuntimeError("Database manager is closing")
            
        if self._connection is None or self._connection.closed:
            try:
                self._connection = await self._create_connection()
            except Exception as e:
                logger.error(f"Failed to create database connection: {e}")
                raise

        return self._connection

    async def close(self):
        """Close database connection properly"""
        self._closing = True
        if self._connection and not self._connection.closed:
            try:
                await self._connection.commit()
                await self._connection.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self._connection = None
        self._closing = False

    async def __aenter__(self):
        """Async context manager support"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on context manager exit"""
        await self.close()

    async def cursor(self):
        """Get a database cursor as an async context manager"""
        await self.ensure_initialized()
        return AsyncCursorContextManager(self)

    async def commit(self):
        """Commit changes with proper error handling"""
        if self._connection and not self._connection.closed:
            try:
                await self._connection.commit()
            except Exception as e:
                logger.error(f"Failed to commit database changes: {e}")
                raise

    async def rollback(self):
        """Rollback changes with proper error handling"""
        if self._connection and not self._connection.closed:
            try:
                await self._connection.rollback()
            except Exception as e:
                logger.error(f"Failed to rollback database changes: {e}")
                raise

    async def setup_database(self) -> None:
        """Initialize database schema with proper constraints"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executescript("""
                -- Core guild settings
                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prefix TEXT DEFAULT '!',
                    locale TEXT DEFAULT 'en-US',
                    timezone TEXT DEFAULT 'UTC',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Server settings table
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT,
                    goodbye_channel_id INTEGER,
                    goodbye_message TEXT,
                    mod_log_channel_id INTEGER,
                    audit_log_channel_id INTEGER,
                    mute_role_id INTEGER,
                    auto_role_id INTEGER,
                    authorized_roles TEXT,
                    disabled_commands TEXT,
                    auto_mod_enabled BOOLEAN DEFAULT 0,
                    max_mentions INTEGER DEFAULT 5,
                    max_links INTEGER DEFAULT 3,
                    max_attachments INTEGER DEFAULT 5,
                    filters_enabled BOOLEAN DEFAULT 0,
                    filtered_words TEXT,
                    caps_threshold INTEGER DEFAULT 70,
                    spam_threshold INTEGER DEFAULT 5,
                    raid_mode_enabled BOOLEAN DEFAULT 0,
                    verification_level INTEGER DEFAULT 0,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Command metrics
                CREATE TABLE IF NOT EXISTS command_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    command_name TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    error TEXT,
                    execution_time REAL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Command logs
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    command_name TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    error TEXT,
                    execution_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Guild metrics
                CREATE TABLE IF NOT EXISTS guild_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    member_count INTEGER NOT NULL,
                    online_count INTEGER,
                    message_count INTEGER DEFAULT 0,
                    active_users INTEGER DEFAULT 0,
                    bot_latency REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_command_stats_guild ON command_stats(guild_id);
                CREATE INDEX IF NOT EXISTS idx_command_stats_user ON command_stats(user_id);
                CREATE INDEX IF NOT EXISTS idx_guild_metrics_guild ON guild_metrics(guild_id);
                CREATE INDEX IF NOT EXISTS idx_guild_metrics_time ON guild_metrics(timestamp);
            """)
            await conn.commit()

    async def ensure_guild_exists(self, guild_id: int, guild_name: str = None) -> None:
        """Ensure guild exists with all required settings"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("""
                INSERT OR IGNORE INTO guilds (id, name)
                VALUES (?, ?)
            """, (guild_id, guild_name or str(guild_id)))
            
            await conn.execute("""
                INSERT OR IGNORE INTO server_settings (guild_id)
                VALUES (?)
            """, (guild_id,))
            
            await conn.commit()

    async def batch_update_metrics(self, metrics: List[Dict[str, Any]]) -> None:
        """Batch insert guild metrics asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executemany("""
                INSERT INTO guild_metrics (
                    guild_id, member_count, online_count,
                    message_count, active_users, bot_latency
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [(m['guild_id'], m['member_count'], m.get('online_count', 0),
                  m.get('message_count', 0), m.get('active_users', 0),
                  m.get('bot_latency', 0)) for m in metrics])
            await conn.commit()

    async def log_command(self, guild_id: int, user_id: int, command_name: str,
                         success: bool, error: str = None, execution_time: float = None) -> None:
        """Log command usage asynchronously"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute("""
                INSERT INTO command_stats (
                    guild_id, user_id, command_name,
                    success, error, execution_time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error, execution_time))
            
            await conn.execute("""
                INSERT INTO command_logs (
                    guild_id, user_id, command_name,
                    success, error, execution_time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error, execution_time))
            
            await conn.commit()

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT * FROM guilds WHERE id = ?
            """, (guild_id,))
            result = await cur.fetchone()
            return dict(result) if result else {}

    async def update_guild_settings(self, guild_id: int, **settings) -> bool:
        """Update guild settings"""
        valid_columns = {'prefix', 'locale', 'timezone', 'name'}
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            try:
                set_clause = ', '.join(f"{key} = ?" for key in settings.keys())
                values = tuple(settings.values()) + (guild_id,)
                
                await conn.execute(f"""
                    UPDATE guilds 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update guild settings: {e}")
                return False

    async def backup_database(self) -> Optional[str]:
        """Create a backup of the database"""
        try:
            backup_dir = Path('db/backups')
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f"{self.db_name}_{timestamp}.db"
            
            # Create backup connection
            async with aiosqlite.connect(backup_path) as backup_conn:
                async with self._lock:
                    conn = await self.get_connection()
                    await conn.backup(backup_conn)
            
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None

    async def get_server_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get server settings for a guild"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT * FROM server_settings WHERE guild_id = ?
            """, (guild_id,))
            result = await cur.fetchone()
            return dict(result) if result else None

    async def update_server_settings(self, guild_id: int, **settings) -> bool:
        """Update server settings"""
        valid_columns = {
            'welcome_channel_id', 'welcome_message', 'goodbye_channel_id',
            'goodbye_message', 'mod_log_channel_id', 'audit_log_channel_id',
            'mute_role_id', 'auto_role_id', 'authorized_roles',
            'disabled_commands', 'auto_mod_enabled', 'max_mentions',
            'max_links', 'max_attachments', 'filters_enabled',
            'filtered_words', 'caps_threshold', 'spam_threshold',
            'raid_mode_enabled', 'verification_level'
        }
        
        settings = {k: v for k, v in settings.items() if k in valid_columns}
        if not settings:
            return False

        async with self._lock:
            conn = await self.get_connection()
            try:
                # Ensure server settings entry exists
                await conn.execute("""
                    INSERT OR IGNORE INTO server_settings (guild_id)
                    VALUES (?)
                """, (guild_id,))

                # Update settings
                set_clause = ', '.join(f"{key} = ?" for key in settings.keys())
                values = tuple(settings.values()) + (guild_id,)
                
                await conn.execute(f"""
                    UPDATE server_settings 
                    SET {set_clause}
                    WHERE guild_id = ?
                """, values)
                
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update server settings: {e}")
                return False

    async def ensure_server_settings(self, guild_id: int) -> None:
        """Ensure server settings exist with default values"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.execute("""
                    INSERT OR IGNORE INTO server_settings (guild_id)
                    VALUES (?)
                """, (guild_id,))
                await conn.commit()
            except Exception as e:
                logger.error(f"Failed to initialize server settings: {e}")
                raise

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch one row"""
        async with self._lock:
            conn = await self.get_connection()
            cursor = await conn.execute(query, params)
            result = await cursor.fetchone()
            await cursor.close()
            return dict(result) if result else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and fetch all rows"""
        async with self._lock:
            conn = await self.get_connection()
            cursor = await conn.execute(query, params)
            results = await cursor.fetchall()
            await cursor.close()
            return [dict(row) for row in results]

    async def execute(self, query: str, params: tuple = ()):
        """Execute a query without fetching results"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute(query, params)
            await conn.commit()

    async def executemany(self, query: str, params_list: List[tuple]):
        """Execute a query multiple times with different parameters"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.executemany(query, params_list)
            await conn.commit()

    async def get_all_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get all settings for a guild"""
        return await self.fetchone("""
            SELECT g.*, s.*
            FROM guilds g
            LEFT JOIN server_settings s ON g.id = s.guild_id
            WHERE g.id = ?
        """, (guild_id,))

    async def vacuum_database(self) -> None:
        """Optimize database by removing empty space and defragmenting"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.execute("VACUUM")
                await conn.commit()
                logger.info("Database vacuum completed successfully")
            except Exception as e:
                logger.error(f"Error during database vacuum: {e}")
                raise

    async def analyze_database(self) -> None:
        """Update database statistics for query optimization"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.execute("ANALYZE")
                await conn.commit()
                logger.info("Database analysis completed successfully")
            except Exception as e:
                logger.error(f"Error during database analysis: {e}")
                raise

    async def optimize_database(self) -> None:
        """Run complete database optimization with advanced techniques"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                # Run optimizations in a transaction
                async with self.transaction():
                    # Update statistics
                    await conn.execute("ANALYZE")
                    
                    # Rebuild indexes
                    await conn.execute("REINDEX")
                    
                    # Clear unused space
                    await conn.execute("PRAGMA incremental_vacuum")
                    
                    # Optimize database
                    await conn.execute("PRAGMA optimize")
                    
                    # Update database statistics
                    tables = await (await conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )).fetchall()
                    
                    for table in tables:
                        await conn.execute(f"ANALYZE {table[0]}")

                # Run full vacuum after other optimizations
                await conn.execute("VACUUM")
                
            logger.info("Advanced database optimization completed successfully")
        except Exception as e:
            logger.error(f"Error during advanced database optimization: {e}")
            raise

    async def initialize_indexes(self) -> None:
        """Ensure all required indexes exist"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.executescript("""
                    -- Command related indexes
                    CREATE INDEX IF NOT EXISTS idx_command_stats_timestamp ON command_stats(used_at);
                    CREATE INDEX IF NOT EXISTS idx_command_logs_timestamp ON command_logs(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_command_stats_name ON command_stats(command_name);
                    
                    -- Guild related indexes
                    CREATE INDEX IF NOT EXISTS idx_guild_settings ON server_settings(guild_id);
                    CREATE INDEX IF NOT EXISTS idx_guild_joined ON guilds(joined_at);
                    CREATE INDEX IF NOT EXISTS idx_guild_updated ON guilds(updated_at);
                    
                    -- Metrics related indexes
                    CREATE INDEX IF NOT EXISTS idx_metrics_composite ON guild_metrics(guild_id, timestamp);
                """)
                await conn.commit()
                logger.info("Database indexes initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing indexes: {e}")
                raise

    async def initialize_advanced_indexes(self) -> None:
        """Initialize optimized indexes for improved query performance"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.executescript("""
                    -- Composite indexes for common queries
                    CREATE INDEX IF NOT EXISTS idx_guild_metrics_composite 
                    ON guild_metrics(guild_id, timestamp DESC);
                    
                    CREATE INDEX IF NOT EXISTS idx_command_stats_performance 
                    ON command_stats(guild_id, user_id, used_at DESC);
                    
                    CREATE INDEX IF NOT EXISTS idx_command_logs_analysis 
                    ON command_logs(guild_id, command_name, success, timestamp DESC);
                    
                    -- Filtered indexes for common conditions
                    CREATE INDEX IF NOT EXISTS idx_active_guilds 
                    ON guilds(id) WHERE active = 1;
                    
                    CREATE INDEX IF NOT EXISTS idx_enabled_features 
                    ON server_settings(guild_id) 
                    WHERE auto_mod_enabled = 1 OR raid_mode_enabled = 1;
                    
                    -- Partial indexes for specific queries
                    CREATE INDEX IF NOT EXISTS idx_recent_commands 
                    ON command_stats(guild_id, command_name) 
                    WHERE used_at >= datetime('now', '-7 days');
                """)
                await conn.commit()
                logger.info("Advanced database indexes initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing advanced indexes: {e}")
                raise

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                stats = {}
                
                # Get database settings
                cursor = await conn.execute("PRAGMA journal_mode")
                stats['journal_mode'] = (await cursor.fetchone())[0]
                
                cursor = await conn.execute("PRAGMA foreign_keys")
                stats['foreign_keys'] = bool((await cursor.fetchone())[0])
                
                cursor = await conn.execute("PRAGMA cache_size")
                stats['cache_size'] = (await cursor.fetchone())[0]
                
                # Get connection status
                stats['connection_open'] = not conn.closed
                stats['in_transaction'] = conn.in_transaction
                
                await cursor.close()
                return stats
            except Exception as e:
                logger.error(f"Error getting connection stats: {e}")
                return {}

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions with proper locking"""
        await self._ensure_initialized()
        async with self._transaction_lock:
            if not self._connection:
                await self._ensure_initialized()
            try:
                await self._connection.execute("BEGIN TRANSACTION")
                yield
                await self._connection.commit()
            except Exception as e:
                await self._connection.rollback()
                logger.error(f"Transaction failed, rolling back: {e}")
                raise
            finally:
                if self._connection and self._connection.in_transaction:
                    await self._connection.rollback()

    async def batch_insert(self, table: str, columns: List[str], values: List[tuple]) -> None:
        """Efficiently insert multiple rows into a table"""
        if not values:
            return

        placeholders = ','.join(['?' for _ in columns])
        columns_str = ','.join(columns)
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.executemany(query, values)
                await conn.commit()
            except Exception as e:
                logger.error(f"Error in batch insert: {e}")
                await conn.rollback()
                raise

    async def batch_update(self, table: str, set_columns: List[str], where_column: str, 
                          values: List[tuple]) -> None:
        """Efficiently update multiple rows in a table"""
        if not values:
            return

        set_clause = ','.join([f"{col} = ?" for col in set_columns])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_column} = ?"

        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.executemany(query, values)
                await conn.commit()
            except Exception as e:
                logger.error(f"Error in batch update: {e}")
                await conn.rollback()
                raise

    async def batch_delete(self, table: str, where_column: str, values: List[Any]) -> None:
        """Efficiently delete multiple rows from a table"""
        if not values:
            return

        placeholders = ','.join(['?' for _ in values])
        query = f"DELETE FROM {table} WHERE {where_column} IN ({placeholders})"

        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.execute(query, values)
                await conn.commit()
            except Exception as e:
                logger.error(f"Error in batch delete: {e}")
                await conn.rollback()
                raise

    async def execute_script(self, script: str) -> None:
        """Execute a SQL script with proper error handling"""
        async with self._lock:
            conn = await self.get_connection()
            try:
                await conn.executescript(script)
                await conn.commit()
            except Exception as e:
                logger.error(f"Error executing script: {e}")
                await conn.rollback()
                raise

    async def get_row_count(self, table: str, condition: str = None, 
                           params: tuple = ()) -> int:
        """Get the number of rows in a table with optional condition"""
        query = f"SELECT COUNT(*) FROM {table}"
        if condition:
            query += f" WHERE {condition}"

        async with self.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchone()
            return result[0] if result else 0

    async def table_exists(self, table: str) -> bool:
        """Check if a table exists in the database"""
        async with self.cursor() as cur:
            await cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            return bool(await cur.fetchone())

    async def get_column_info(self, table: str) -> List[Dict[str, Any]]:
        """Get information about table columns"""
        async with self.cursor() as cur:
            await cur.execute(f"PRAGMA table_info({table})")
            columns = await cur.fetchall()
            return [dict(col) for col in columns]

    async def create_backup_point(self, name: str) -> None:
        """Create a savepoint for transaction rollback"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute(f"SAVEPOINT {name}")

    async def rollback_to_point(self, name: str) -> None:
        """Rollback to a specific savepoint"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute(f"ROLLBACK TO SAVEPOINT {name}")

    async def release_backup_point(self, name: str) -> None:
        """Release a savepoint"""
        async with self._lock:
            conn = await self.get_connection()
            await conn.execute(f"RELEASE SAVEPOINT {name}")

    async def get_table_schema(self, table: str) -> str:
        """Get the CREATE TABLE statement for a table"""
        async with self.cursor() as cur:
            await cur.execute(f"""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            result = await cur.fetchone()
            return result[0] if result else None

    async def get_database_size(self) -> int:
        """Get the current size of the database in bytes"""
        try:
            row = await self.fetchone("SELECT page_count * page_size as size FROM pragma_page_count, pragma_page_size")
            return row['size'] if row else 0
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return 0

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        try:
            stats = {}
            async with self.transaction():
                for pragma in ['journal_mode', 'cache_size', 'page_size', 'max_page_count']:
                    result = await self.fetchone(f"PRAGMA {pragma}")
                    if result:
                        stats[pragma] = result[0]
            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    async def optimize(self) -> None:
        """Run database optimization tasks"""
        try:
            async with self.transaction():
                await self.execute_script("""
                    PRAGMA optimize;
                    VACUUM;
                    ANALYZE;
                """)
            logger.info("Database optimization completed")
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            raise

    async def close(self) -> None:
        """Close the database connection"""
        if self._connection:
            try:
                await self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
                raise

    async def get_performance_metrics(self) -> dict:
        """Get database performance metrics"""
        async with self._lock:
            conn = await self.get_connection()
            metrics = {}
            try:
                # Get database size
                size_result = await conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                metrics['database_size'] = (await size_result.fetchone())[0]

                # Get cache stats
                cache_result = await conn.execute("PRAGMA cache_stats")
                metrics['cache_stats'] = dict(await cache_result.fetchone())

                # Get index statistics
                idx_stats = await conn.execute("SELECT * FROM sqlite_stat1")
                metrics['index_stats'] = [dict(row) for row in await idx_stats.fetchall()]

                return metrics
            except Exception as e:
                logger.error(f"Error collecting performance metrics: {e}")
                raise

    async def monitor_slow_queries(self, threshold_ms: int = 100) -> None:
        """Enable monitoring of slow queries"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS slow_queries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT,
                        duration_ms INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        stack_trace TEXT
                    )
                """)
                # Enable query timing
                await conn.execute("PRAGMA query_trace=ON")
                # Set threshold
                await conn.execute(f"PRAGMA slow_query_threshold={threshold_ms}")
                logger.info(f"Slow query monitoring enabled with {threshold_ms}ms threshold")
        except Exception as e:
            logger.error(f"Error setting up slow query monitoring: {e}")
            raise

    async def recover_from_corruption(self) -> bool:
        """Attempt to recover from database corruption"""
        try:
            backup_path = f"{self.db_path}.backup"
            async with self._lock:
                conn = await self.get_connection()
                # Check database integrity
                integrity = await conn.execute("PRAGMA integrity_check")
                if (await integrity.fetchone())[0] == "ok":
                    return True

                logger.warning("Database corruption detected, attempting recovery")
                # Create backup
                await conn.execute(f"VACUUM INTO '{backup_path}'")
                # Attempt repair
                await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await conn.execute("VACUUM")
                
                # Verify repair
                integrity = await conn.execute("PRAGMA integrity_check")
                if (await integrity.fetchone())[0] == "ok":
                    logger.info("Database recovery successful")
                    return True
                else:
                    logger.error("Database recovery failed")
                    return False
        except Exception as e:
            logger.error(f"Error during database recovery: {e}")
            raise

    async def check_connection_health(self) -> bool:
        """Check if database connection is healthy"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def optimize_connection_pool(self, max_connections: int = 10) -> None:
        """Optimize the connection pool settings"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                # Set optimal pool size
                await conn.execute(f"PRAGMA max_page_count = {max_connections * 1000}")
                # Enable connection pooling
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA busy_timeout = 5000")
                # Set cache size (in pages)
                await conn.execute("PRAGMA cache_size = -2000")
                logger.info(f"Connection pool optimized with max {max_connections} connections")
        except Exception as e:
            logger.error(f"Error optimizing connection pool: {e}")
            raise

    async def create_maintenance_triggers(self) -> None:
        """Create maintenance triggers for automated cleanup"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                # Create cleanup trigger for old slow query logs
                await conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS cleanup_old_slow_queries
                    AFTER INSERT ON slow_queries
                    BEGIN
                        DELETE FROM slow_queries 
                        WHERE timestamp < datetime('now', '-7 days');
                    END;
                """)
                logger.info("Maintenance triggers created successfully")
        except Exception as e:
            logger.error(f"Error creating maintenance triggers: {e}")
            raise

    async def analyze_query_performance(self) -> dict:
        """Analyze and return database query performance metrics"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                stats = {}
                
                # Get index statistics
                rows = await conn.execute("PRAGMA index_list('users')")
                stats['indexes'] = len(await rows.fetchall())
                
                # Get database size
                rows = await conn.execute("PRAGMA page_count")
                page_count = (await rows.fetchone())[0]
                rows = await conn.execute("PRAGMA page_size")
                page_size = (await rows.fetchone())[0]
                stats['size_mb'] = (page_count * page_size) / (1024 * 1024)
                
                return stats
        except Exception as e:
            logger.error(f"Error analyzing query performance: {e}")
            raise

    async def perform_maintenance(self) -> None:
        """Perform routine database maintenance"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                # Rebuild indexes
                await conn.execute("PRAGMA optimize")
                # Update statistics
                await conn.execute("ANALYZE")
                # Compact database
                await conn.execute("VACUUM")
                logger.info("Database maintenance completed successfully")
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
            raise

    async def backup_database(self, backup_path: str) -> None:
        """Create a backup of the database"""
        try:
            async with self._lock:
                conn = await self.get_connection()
                await conn.execute(f"VACUUM INTO '{backup_path}'")
                logger.info(f"Database backup created at {backup_path}")
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise

    async def _create_connection(self):
        """Create a new database connection with optimized settings"""
        conn = await aiosqlite.connect(self.db_path)
        # Enable WAL mode for better concurrency
        await conn.execute("PRAGMA journal_mode=WAL")
        # Optimize cache settings
        await conn.execute("PRAGMA cache_size=-2000")  # 2MB cache
        await conn.execute("PRAGMA temp_store=MEMORY")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def get_connection(self):
        """Get a connection from the pool or create a new one"""
        await self._ensure_initialized()
        # Check connections health periodically
        current_time = time.time()
        if current_time - self._last_connection_check > 60:  # Check every minute
            await self._health_check()
            self._last_connection_check = current_time

        # Try to get a connection from the pool
        while self._pool:
            conn = self._pool.pop()
            try:
                # Test if connection is still valid
                await conn.execute("SELECT 1")
                return conn
            except Exception:
                await conn.close()
                continue

        # Create new connection if pool is empty
        return await self._create_connection()

    async def _health_check(self):
        """Check and clean up dead connections"""
        valid_connections = []
        for conn in self._pool:
            try:
                await conn.execute("SELECT 1")
                valid_connections.append(conn)
            except Exception:
                await conn.close()
        self._pool = valid_connections

    async def release_connection(self, conn):
        """Release a connection back to the pool"""
        if len(self._pool) < self._max_connections:
            self._pool.append(conn)
        else:
            await conn.close()

    async def optimize_database(self):
        """Perform database optimization and maintenance"""
        conn = await self.get_connection()
        try:
            # Analyze tables for query optimization
            await conn.execute("ANALYZE")
            # Clean up unused space
            await conn.execute("VACUUM")
            # Update statistics
            await conn.execute("PRAGMA optimize")
            await conn.commit()
        finally:
            await self.release_connection(conn)

    async def execute_optimized(self, query: str, parameters: tuple = None):
        """Execute a query with optimized settings and automatic retry"""
        retries = 3
        while retries > 0:
            try:
                conn = await self.get_connection()
                try:
                    if parameters:
                        result = await conn.execute(query, parameters)
                    else:
                        result = await conn.execute(query)
                    await conn.commit()
                    return result
                finally:
                    await self.release_connection(conn)
            except aiosqlite.OperationalError as e:
                retries -= 1
                if retries == 0:
                    raise
                await asyncio.sleep(0.5)

    async def create_indexes(self):
        """Create optimized indexes for common queries"""
        conn = await self.get_connection()
        try:
            # Add indexes for frequently accessed columns
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_levels_user_id ON levels(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_autoroles_guild_id ON autoroles(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_verification_guild_id ON verification(guild_id)")
            await conn.commit()
        finally:
            await self.release_connection(conn)

    async def optimize_database(self):
        """Perform database optimization tasks"""
        async with self._lock:
            try:
                # Analyze tables for query optimization
                await self.execute("ANALYZE")
                
                # Clean up unused space
                await self.execute("VACUUM")
                
                # Rebuild indexes
                await self.execute("REINDEX")
                
                # Update statistics
                await self.execute("PRAGMA optimize")
                
                logger.info("Database optimization completed successfully")
            except Exception as e:
                logger.error(f"Database optimization failed: {e}")
                raise

    async def get_indexes(self) -> List[Dict[str, str]]:
        """Get information about database indexes"""
        indexes = []
        async with self._lock:
            tables = await self.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
            for table in tables:
                table_name = table['name']
                index_info = await self.fetchall(f"PRAGMA index_list('{table_name}')")
                for index in index_info:
                    indexes.append({
                        'table': table_name,
                        'index_name': index['name'],
                        'unique': bool(index['unique'])
                    })
        return indexes