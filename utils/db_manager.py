import sqlite3
import os
import shutil
from datetime import datetime
from contextlib import contextmanager
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import asyncio

logger = logging.getLogger(__name__)

def adapt_datetime(val: datetime) -> str:
    """Adapt datetime objects to ISO format strings for SQLite"""
    return val.isoformat()

def convert_datetime(val: bytes) -> datetime:
    """Convert ISO format strings from SQLite to datetime objects"""
    try:
        return datetime.fromisoformat(val.decode())
    except (ValueError, AttributeError):
        return None

# Register the adapter and converter
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.db_dir = os.path.join(self.base_dir, "db")
        self.backup_dir = os.path.join(self.db_dir, "backups")
        self.db_path = os.path.join(self.db_dir, f"{db_name}.db")
        self._connection_pool = []
        self._pool_lock = asyncio.Lock()
        self._max_connections = 5
        
        # Create necessary directories
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        self._initialize_db()
        self._create_backup()

    def _initialize_db(self):
        """Initialize database with proper settings and schemas"""
        with self.connection() as conn:
            # Performance tuning
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -2000000")  # Use 2GB memory for cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 30000000000")
            conn.execute("PRAGMA busy_timeout = 60000")  # 60 second timeout

            # Core Tables
            guild_settings_schema = '''CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                prefix TEXT DEFAULT "!",
                locale TEXT DEFAULT "en",
                timezone TEXT DEFAULT "UTC",
                disabled_commands TEXT DEFAULT "",
                disabled_channels TEXT DEFAULT ""
            )'''

            user_settings_schema = '''CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level_up_dm BOOLEAN DEFAULT FALSE,
                notifications_enabled BOOLEAN DEFAULT TRUE,
                custom_color INTEGER DEFAULT NULL,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            # Leveling System Tables
            leveling_settings_schema = '''CREATE TABLE IF NOT EXISTS leveling_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE,
                xp_cooldown INTEGER DEFAULT 60,
                min_xp INTEGER DEFAULT 15,
                max_xp INTEGER DEFAULT 25,
                level_up_message TEXT DEFAULT 'Congratulations {user}! You reached level {level}!',
                level_up_channel_id INTEGER DEFAULT NULL,
                stack_roles BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            xp_data_schema = '''CREATE TABLE IF NOT EXISTS xp_data (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                last_message TIMESTAMP,
                total_xp INTEGER DEFAULT 0,
                weekly_xp INTEGER DEFAULT 0,
                weekly_reset TIMESTAMP,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id, guild_id) REFERENCES user_settings(user_id, guild_id) ON DELETE CASCADE
            )'''

            level_roles_schema = '''CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, level),
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            # AutoRole System Tables
            autorole_schema = '''CREATE TABLE IF NOT EXISTS autorole (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, type),
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            # Stats and Analytics Tables
            command_stats_schema = '''CREATE TABLE IF NOT EXISTS command_stats (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                command_name TEXT NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT DEFAULT NULL,
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            metrics_schema = '''CREATE TABLE IF NOT EXISTS guild_metrics (
                metric_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                member_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                command_count INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
            )'''

            # Create triggers for updating timestamps
            guild_timestamp_trigger = '''CREATE TRIGGER IF NOT EXISTS update_guild_timestamp 
                AFTER UPDATE ON guild_settings
                BEGIN
                    UPDATE guild_settings 
                    SET updated_at = CURRENT_TIMESTAMP 
                    WHERE guild_id = NEW.guild_id;
                END;'''

            user_timestamp_trigger = '''CREATE TRIGGER IF NOT EXISTS update_user_timestamp 
                AFTER UPDATE ON user_settings
                BEGIN
                    UPDATE user_settings 
                    SET updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = NEW.user_id AND guild_id = NEW.guild_id;
                END;'''

            weekly_xp_reset_trigger = '''CREATE TRIGGER IF NOT EXISTS reset_weekly_xp 
                AFTER UPDATE ON xp_data
                WHEN (julianday('now') - julianday(OLD.weekly_reset)) >= 7
                BEGIN
                    UPDATE xp_data 
                    SET weekly_xp = 0,
                        weekly_reset = CURRENT_TIMESTAMP 
                    WHERE user_id = NEW.user_id AND guild_id = NEW.guild_id;
                END;'''

            autorole_timestamp_trigger = '''CREATE TRIGGER IF NOT EXISTS update_autorole_timestamp 
                AFTER UPDATE ON autorole
                BEGIN
                    UPDATE autorole 
                    SET updated_at = CURRENT_TIMESTAMP 
                    WHERE guild_id = NEW.guild_id AND type = NEW.type;
                END;'''

            try:
                # Drop existing autorole table if it exists (for schema update)
                conn.execute("DROP TABLE IF EXISTS autorole")
                
                # Drop and recreate metrics table to update schema
                conn.execute("DROP TABLE IF EXISTS guild_metrics")
                conn.execute(metrics_schema)

                # Create tables
                conn.execute(guild_settings_schema)
                conn.execute(user_settings_schema)
                conn.execute(leveling_settings_schema)
                conn.execute(xp_data_schema)
                conn.execute(level_roles_schema)
                conn.execute(autorole_schema)
                conn.execute(command_stats_schema)

                # Create triggers
                conn.execute(guild_timestamp_trigger)
                conn.execute(user_timestamp_trigger)
                conn.execute(weekly_xp_reset_trigger)
                conn.execute(autorole_timestamp_trigger)

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_xp_guild ON xp_data(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_xp_level ON xp_data(level)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_xp_combined ON xp_data(guild_id, level DESC, xp DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_autorole_guild ON autorole(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_level_roles_guild ON level_roles(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_settings_guild ON user_settings(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_command_stats_guild ON command_stats(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_command_stats_user ON command_stats(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_command_stats_analysis ON command_stats(guild_id, used_at, success)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_guild ON guild_metrics(guild_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON guild_metrics(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_guild_time ON guild_metrics(guild_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_recent ON guild_metrics(timestamp DESC)")
                
                logger.info("Database optimization complete")
            except Exception as e:
                logger.error(f"Error optimizing database: {e}")
                raise

    def _create_backup(self):
        """Create timestamped backup of database"""
        if os.path.exists(self.db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"{self.db_name}_{timestamp}.db")
            try:
                shutil.copy2(self.db_path, backup_path)
                # Keep only last 5 backups
                backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith(self.db_name)])
                for old_backup in backups[:-5]:
                    os.remove(os.path.join(self.backup_dir, old_backup))
                logger.info(f"Database backup created: {backup_path}")
            except Exception as e:
                logger.error(f"Backup creation failed: {e}")

    def _get_connection(self):
        """Get a connection from the pool or create a new one"""
        if self._connection_pool:
            return self._connection_pool.pop()
            
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -2000000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _return_connection(self, conn):
        """Return a connection to the pool"""
        if len(self._connection_pool) < self._max_connections:
            self._connection_pool.append(conn)
        else:
            conn.close()

    @contextmanager
    def connection(self):
        conn = None
        try:
            conn = self._get_connection()
            yield conn
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self._return_connection(conn)

    @contextmanager
    def cursor(self):
        conn = None
        cur = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database cursor error: {e}")
            raise
        finally:
            if cur:
                cur.close()
            if conn:
                self._return_connection(conn)

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        with self.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed: {e}")
                raise

    def _check_integrity(self):
        """Check database integrity"""
        with self.connection() as conn:
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    logger.error(f"Database integrity check failed: {result}")
                    self._restore_latest_backup()
                return result == "ok"
            except Exception as e:
                logger.error(f"Integrity check failed: {e}")
                return False

    def _restore_latest_backup(self):
        """Restore from most recent backup"""
        try:
            backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith(self.db_name)])
            if backups:
                latest_backup = os.path.join(self.backup_dir, backups[-1])
                shutil.copy2(latest_backup, self.db_path)
                logger.info(f"Database restored from backup: {latest_backup}")
                return True
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
        return False

    def migrate_table(self, table_name, schema):
        """Safely migrate table schema with backup"""
        try:
            # Create backup before migration
            self._create_backup()
            
            with self.transaction() as conn:
                cur = conn.cursor()
                # Get existing table info
                cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                old_schema = cur.fetchone()

                if old_schema:
                    # Store existing data
                    cur.execute(f"PRAGMA table_info({table_name})")
                    old_columns = [row[1] for row in cur.fetchall()]
                    cur.execute(f"SELECT * FROM {table_name}")
                    old_data = cur.fetchall()
                    
                    # Create new table with temp name
                    temp_table = f"{table_name}_new"
                    new_schema = schema.replace(table_name, temp_table)
                    cur.execute(new_schema)
                    
                    # Migrate data
                    self._migrate_data(cur, table_name, temp_table, old_columns, old_data)
                    
                    # Swap tables
                    cur.execute(f"DROP TABLE {table_name}")
                    cur.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")
                else:
                    # Create new table if it doesn't exist
                    cur.execute(schema)
                
                logger.info(f"Successfully migrated table: {table_name}")
                
            # Verify integrity after migration
            if not self._check_integrity():
                raise Exception("Migration resulted in database integrity issues")
                
        except Exception as e:
            logger.error(f"Migration error for {table_name}: {e}")
            if self._restore_latest_backup():
                logger.info("Restored from backup after failed migration")
            raise

    def _migrate_data(self, cur, old_table, new_table, old_columns, old_data):
        """Migrate data from old table to new table"""
        cur.execute(f"PRAGMA table_info({new_table})")
        new_columns = [row[1] for row in cur.fetchall()]
        common_columns = [col for col in old_columns if col in new_columns]
        
        if old_data:
            columns_str = ", ".join(common_columns)
            placeholders = ", ".join(["?" for _ in common_columns])
            insert_sql = f"INSERT INTO {new_table} ({columns_str}) VALUES ({placeholders})"
            
            for row in old_data:
                row_dict = dict(zip(old_columns, row))
                values = [row_dict[col] for col in common_columns]
                cur.execute(insert_sql, values)

    def ensure_guild_exists(self, guild_id: int):
        """Ensure guild settings exist for the given guild"""
        with self.cursor() as cur:
            cur.execute("""
                INSERT OR IGNORE INTO guild_settings (guild_id)
                VALUES (?)
            """, (guild_id,))

    def get_guild_setting(self, guild_id: int, table: str, column: str):
        """Get a specific setting for a guild"""
        with self.cursor() as cur:
            cur.execute(f"""
                SELECT {column} FROM {table}
                WHERE guild_id = ?
            """, (guild_id,))
            result = cur.fetchone()
            return result[0] if result else None

    def set_guild_setting(self, guild_id: int, table: str, column: str, value):
        """Set a specific setting for a guild"""
        self.ensure_guild_exists(guild_id)
        with self.cursor() as cur:
            cur.execute(f"""
                INSERT OR REPLACE INTO {table} (guild_id, {column})
                VALUES (?, ?)
            """, (guild_id, value))

    def get_user_setting(self, user_id: int, guild_id: int, column: str):
        """Get a specific setting for a user in a guild"""
        with self.cursor() as cur:
            cur.execute(f"""
                SELECT {column} FROM user_settings
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            result = cur.fetchone()
            return result[0] if result else None

    def set_user_setting(self, user_id: int, guild_id: int, column: str, value):
        """Set a specific setting for a user in a guild"""
        self.ensure_guild_exists(guild_id)
        with self.cursor() as cur:
            cur.execute("""
                INSERT OR IGNORE INTO user_settings (user_id, guild_id)
                VALUES (?, ?)
            """, (user_id, guild_id))
            cur.execute(f"""
                UPDATE user_settings
                SET {column} = ?
                WHERE user_id = ? AND guild_id = ?
            """, (value, user_id, guild_id))

    def get_all_guild_settings(self, guild_id: int):
        """Get all settings for a guild"""
        with self.cursor() as cur:
            cur.execute("""
                SELECT 
                    gs.*,
                    ls.xp_cooldown,
                    ls.min_xp,
                    ls.max_xp,
                    ls.level_up_message,
                    ls.level_up_channel_id
                FROM guild_settings gs
                LEFT JOIN leveling_settings ls ON gs.guild_id = ls.guild_id
                WHERE gs.guild_id = ?
            """, (guild_id,))
            return cur.fetchone()

    def log_command(self, guild_id: int, user_id: int, command_name: str, success: bool = True, error: str = None):
        """Log command usage for analytics"""
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO command_stats (guild_id, user_id, command_name, success, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (guild_id, user_id, command_name, success, error))
    
    def update_guild_metrics(self, guild_id: int, member_count: int, message_count: int = 0, 
                           command_count: int = 0, active_users: int = 0):
        """Update guild metrics"""
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO guild_metrics 
                (guild_id, member_count, message_count, command_count, active_users)
                VALUES (?, ?, ?, ?, ?)
            """, (guild_id, member_count, message_count, command_count, active_users))

    def batch_update_metrics(self, metrics_data):
        """Optimized batch update for metrics"""
        if not metrics_data:
            return
            
        try:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.executemany("""
                    INSERT INTO guild_metrics 
                    (guild_id, member_count, active_users, timestamp)
                    VALUES (?, ?, ?, ?)
                """, [(m['guild_id'], m['member_count'], m['active_users'], m['timestamp']) for m in metrics_data])
        except Exception as e:
            logger.error(f"Failed to batch update metrics: {e}")

    def get_guild_stats(self, guild_id: int, days: int = 7) -> Dict[str, Any]:
        """Get guild statistics for the specified time period"""
        try:
            with self.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COALESCE(AVG(member_count), 0) as avg_members,
                        COALESCE(SUM(message_count), 0) as total_messages,
                        COALESCE(SUM(command_count), 0) as total_commands,
                        COALESCE(AVG(active_users), 0) as avg_active_users
                    FROM guild_metrics
                    WHERE guild_id = ? 
                    AND timestamp >= datetime('now', ?)
                """, (guild_id, f'-{days} days'))
                result = cur.fetchone()
                if result:
                    return {
                        'avg_members': result[0] or 0,
                        'total_messages': result[1] or 0,
                        'total_commands': result[2] or 0,
                        'avg_active_users': result[3] or 0
                    }
                return {
                    'avg_members': 0,
                    'total_messages': 0,
                    'total_commands': 0,
                    'avg_active_users': 0
                }
        except Exception as e:
            logger.error(f"Error getting guild stats: {e}")
            return {
                'avg_members': 0,
                'total_messages': 0,
                'total_commands': 0,
                'avg_active_users': 0
            }

    def get_user_stats(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        with self.cursor() as cur:
            cur.execute("""
                SELECT 
                    xd.level, xd.xp, xd.total_xp, xd.messages,
                    xd.weekly_xp, xd.weekly_reset,
                    us.level_up_dm, us.notifications_enabled,
                    us.custom_color
                FROM xp_data xd
                JOIN user_settings us ON xd.user_id = us.user_id 
                    AND xd.guild_id = us.guild_id
                WHERE xd.user_id = ? AND xd.guild_id = ?
            """, (user_id, guild_id))
            result = cur.fetchone()
            if result:
                return {
                    'level': result[0],
                    'xp': result[1],
                    'total_xp': result[2],
                    'messages': result[3],
                    'weekly_xp': result[4],
                    'weekly_reset': result[5],
                    'level_up_dm': result[6],
                    'notifications': result[7],
                    'custom_color': result[8]
                }
            return None

    def get_leaderboard(self, guild_id: int, limit: int = 10, 
                       type: str = 'level') -> List[Tuple[int, int, int]]:
        """Get guild leaderboard by specified type"""
        sort_column = {
            'level': 'level',
            'xp': 'total_xp',
            'weekly': 'weekly_xp',
            'messages': 'messages'
        }.get(type, 'level')

        with self.cursor() as cur:
            cur.execute(f"""
                SELECT user_id, {sort_column}, messages
                FROM xp_data
                WHERE guild_id = ?
                ORDER BY {sort_column} DESC
                LIMIT ?
            """, (guild_id, limit))
            return cur.fetchall()
