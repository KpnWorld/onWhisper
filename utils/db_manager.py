import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta, timezone
import asyncio
from typing import Optional, Dict, Any, List, Union, Callable
import random
from replit import db
import os

class DatabaseTransaction:
    def __init__(self, db_manager, guild_id: int, namespace: str):
        self.db_manager = db_manager
        self.guild_id = guild_id
        self.namespace = namespace
        self._lock = asyncio.Lock()
        self.changes = {}
        self._committed = False
        self._snapshot = {}

    async def __aenter__(self):
        await self._lock.acquire()
        # Take snapshot of current data for rollback
        try:
            data = await self.db_manager.get_section(self.guild_id, self.namespace)
            self._snapshot = data.copy() if data else {}
        except Exception as e:
            print(f"Error taking transaction snapshot: {e}")
            self._snapshot = {}
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None and not self._committed:
                # Commit changes
                await self.commit()
            elif exc_type is not None:
                # Roll back on error
                await self.rollback()
        finally:
            self._lock.release()

    async def commit(self) -> bool:
        """Commit transaction changes"""
        if self._committed:
            return False

        try:
            # Apply changes atomically
            data = await self.db_manager.get_section(self.guild_id, self.namespace) or {}
            data.update(self.changes)
            success = await self.db_manager.update_section(self.guild_id, self.namespace, data)
            if success:
                self._committed = True
                return True
            return False
        except Exception as e:
            print(f"Error committing transaction: {e}")
            await self.rollback()
            return False

    async def rollback(self) -> bool:
        """Roll back transaction changes"""
        try:
            if self._committed:
                return False
            # Restore snapshot
            success = await self.db_manager.update_section(self.guild_id, self.namespace, self._snapshot)
            return success
        except Exception as e:
            print(f"Error rolling back transaction: {e}")
            return False

    def update(self, key: str, value: Any) -> None:
        """Stage an update in the transaction"""
        if self._committed:
            raise ValueError("Cannot update committed transaction")
        self.changes[key] = value

    def delete(self, key: str) -> None:
        """Stage a deletion in the transaction"""
        if self._committed:
            raise ValueError("Cannot update committed transaction")
        self.changes[key] = None  # Mark for deletion

class DatabaseManager:
    def __init__(self, bot):
        self.bot = bot
        self._cache = {}
        self._locks = {}
        self._operation_locks = {}
        self._write_lock = asyncio.Lock()
        self._initialized = False

    async def _read_data(self, key: str) -> Optional[Any]:
        """Read data from Replit database with caching"""
        if key in self._cache:
            return self._cache[key]

        try:
            value = db.get(key)
            if value is not None:
                try:
                    # Try to parse JSON data
                    if isinstance(value, str):
                        data = json.loads(value)
                    else:
                        # Non-string data is likely already parsed
                        data = value
                    
                    # Cache the parsed data
                    self._cache[key] = data
                    return data
                except json.JSONDecodeError:
                    # If JSON parsing fails, return raw value but don't cache
                    print(f"Warning: Failed to parse JSON for key {key}")
                    return value
            return None
        except Exception as e:
            print(f"Error reading data for key {key}: {e}")
            # Invalidate cache on error
            self._cache.pop(key, None)
            return None

    async def _write_data(self, key: str, value: Any) -> bool:
        """Write data to Replit database"""
        try:
            async with self._write_lock:
                # Ensure data is JSON serializable
                if not isinstance(value, str):
                    try:
                        # Test JSON serialization
                        json_str = json.dumps(value)
                        # Only update if serialization succeeds
                        db[key] = json_str
                        self._cache[key] = value  # Cache the original value
                    except (TypeError, ValueError) as e:
                        print(f"Error serializing data for key {key}: {e}")
                        return False
                else:
                    # Value is already a string, verify it's valid JSON if it looks like it
                    if value.startswith('{') or value.startswith('['):
                        try:
                            # Validate JSON format
                            json.loads(value)
                        except json.JSONDecodeError:
                            print(f"Warning: Invalid JSON string for key {key}")
                            return False
                    
                    db[key] = value
                    self._cache[key] = value

                return True
        except Exception as e:
            print(f"Error writing data for key {key}: {e}")
            # Invalidate cache on error
            self._cache.pop(key, None)
            return False

    async def _delete_data(self, key: str) -> bool:
        """Delete data from Replit database"""
        try:
            async with self._write_lock:
                if key in db:
                    del db[key]
                    self._cache.pop(key, None)
                    return True
                return False
        except Exception as e:
            print(f"Error deleting data for key {key}: {e}")
            # Invalidate cache on error
            self._cache.pop(key, None)
            return False

    async def _list_keys(self, prefix: str = "") -> List[str]:
        """List all keys with given prefix"""
        try:
            if prefix:
                return list(db.prefix(prefix))
            return list(db.keys())
        except Exception as e:
            print(f"Error listing keys with prefix {prefix}: {e}")
            return []

    async def initialize(self) -> bool:
        """Initialize database connection"""
        try:
            # Test database connection by writing and reading a test key
            test_key = "_test_connection"
            test_value = str(datetime.utcnow())
            
            db[test_key] = test_value
            read_value = db[test_key]
            del db[test_key]
            
            if read_value == test_value:
                self._initialized = True
                return True
                
            return False
        except Exception as e:
            print(f"Database initialization failed: {e}")
            return False

    async def close(self) -> None:
        """Close database connection"""
        # No need to close anything with the official client
        self._initialized = False

    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            test_key = "_test_connection"
            test_value = str(datetime.utcnow())
            
            db[test_key] = test_value
            read_value = db[test_key]
            del db[test_key]
            
            return read_value == test_value
        except Exception as e:
            print(f"Database connection check failed: {e}")
            return False

    async def transaction(self, guild_id: int, namespace: str) -> DatabaseTransaction:
        """Create a new transaction for atomic operations"""
        return DatabaseTransaction(self, guild_id, namespace)

    async def safe_operation(self, operation_name: str, func: Callable, *args, **kwargs) -> Any:
        """Execute a database operation with proper locking and error handling"""
        if operation_name not in self._operation_locks:
            self._operation_locks[operation_name] = asyncio.Lock()

        async with self._operation_locks[operation_name]:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                print(f"Error in database operation {operation_name}: {e}")
                return None

    async def get_guild_data(self, guild_id: int) -> Optional[dict]:
        """Get all guild data"""
        data = await self._read_data(f"guild:{guild_id}")
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return data if data else {}

    async def get_section(self, guild_id: int, section: str) -> Optional[dict]:
        """Get a specific section of guild data"""
        guild_data = await self.get_guild_data(guild_id)
        if not guild_data:
            return None
        return guild_data.get(section, {})

    async def update_section(self, guild_id: int, section: str, data: Any) -> bool:
        """Update a specific section of guild data"""
        guild_data = await self.get_guild_data(guild_id)
        if not guild_data:
            guild_data = {}
        guild_data[section] = data
        return await self._write_data(f"guild:{guild_id}", guild_data)

    async def get_user_xp(self, guild_id: int, user_id: str) -> Optional[dict]:
        """Get user XP data"""
        data = await self.get_section(guild_id, 'xp_users')
        return data.get(user_id)

    async def update_user_xp(self, guild_id: int, user_id: str, xp_data: dict) -> bool:
        """Update user XP data"""
        data = await self.get_section(guild_id, 'xp_users') or {}
        data[user_id] = xp_data
        return await self.update_section(guild_id, 'xp_users', data)

    async def get_all_xp(self, guild_id: int) -> dict:
        """Get all users' XP data for a guild"""
        return await self.get_section(guild_id, 'xp_users') or {}

    async def add_log(self, guild_id: int, log_data: dict) -> bool:
        """Add a log entry with automatic cleanup"""
        data = await self.get_section(guild_id, 'logs') or []
        
        # Add new log
        data.append({
            **log_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 1000 logs
        if len(data) > 1000:
            data = data[-1000:]
            
        return await self.update_section(guild_id, 'logs', data)

    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old logs and expired data"""
        try:
            async with self._write_lock:
                cutoff = datetime.utcnow() - timedelta(days=days)
                guilds = await self._read_data('guilds') or []
                success_count = 0
                
                for guild_id in guilds:
                    try:
                        # Create backup before cleanup
                        await self.backup_guild_data(guild_id, f"Auto-backup before {days}-day cleanup")
                        
                        # Get guild data with validation
                        data = await self.get_guild_data(guild_id)
                        if not data or not isinstance(data, dict):
                            continue

                        changes = False
                        
                        # Clean up logs with validation
                        if 'logs' in data and isinstance(data['logs'], list):
                            old_len = len(data['logs'])
                            data['logs'] = [
                                log for log in data['logs']
                                if isinstance(log, dict) and 
                                'timestamp' in log and
                                datetime.fromisoformat(log['timestamp']) > cutoff
                            ]
                            if len(data['logs']) != old_len:
                                changes = True
                        
                        # Clean up expired warnings
                        if 'mod_actions' in data and isinstance(data['mod_actions'], list):
                            old_len = len(data['mod_actions'])
                            data['mod_actions'] = [
                                action for action in data['mod_actions']
                                if isinstance(action, dict) and (
                                    not action.get('expires') or
                                    datetime.fromisoformat(action['expires']) > datetime.utcnow()
                                )
                            ]
                            if len(data['mod_actions']) != old_len:
                                changes = True
                        
                        # Clean up closed whispers
                        if 'whispers' in data and isinstance(data['whispers'], dict):
                            if 'active_threads' in data['whispers']:
                                old_len = len(data['whispers']['active_threads'])
                                data['whispers']['active_threads'] = [
                                    w for w in data['whispers']['active_threads']
                                    if isinstance(w, dict) and (
                                        not w.get('closed_at') or
                                        datetime.fromisoformat(w['closed_at']) > cutoff
                                    )
                                ]
                                if len(data['whispers']['active_threads']) != old_len:
                                    changes = True
                        
                        if changes:
                            # Validate data before saving
                            if await self.validate_schema(data.get('whisper_config', {}), 'whisper') and \
                               await self.validate_schema(data.get('logs', {}), 'logs') and \
                               await self.validate_schema(data.get('xp_settings', {}), 'xp'):
                                if await self._write_data(f"guild:{guild_id}", data):
                                    success_count += 1
                        else:
                            success_count += 1

                    except Exception as e:
                        print(f"Error cleaning up guild {guild_id}: {e}")
                        continue
                
                return success_count > 0

        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False

    async def optimize(self) -> bool:
        """Optimize database storage"""
        try:
            async with self._write_lock:
                # Clear cache to force reloading
                self._cache.clear()
                success_count = 0
                
                # Create backup before optimization
                guilds = await self._read_data('guilds') or []
                for guild_id in guilds:
                    try:
                        await self.backup_guild_data(guild_id, "Auto-backup before optimization")
                        
                        # Get and validate data
                        data = await self.get_guild_data(guild_id)
                        if not data or not isinstance(data, dict):
                            continue
                            
                        # Remove empty sections
                        data = {k: v for k, v in data.items() if v is not None and v != {} and v != []}
                        
                        # Validate critical sections
                        if await self.validate_schema(data.get('whisper_config', {}), 'whisper') and \
                           await self.validate_schema(data.get('logs', {}), 'logs') and \
                           await self.validate_schema(data.get('xp_settings', {}), 'xp'):
                            
                            # Rewrite data to clean up storage
                            if await self._write_data(f"guild:{guild_id}", data):
                                success_count += 1
                    
                    except Exception as e:
                        print(f"Error optimizing guild {guild_id}: {e}")
                        continue
                
                return success_count > 0
                
        except Exception as e:
            print(f"Error during optimization: {e}")
            return False

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection and usage statistics"""
        try:
            guilds = await self._read_data('guilds') or []
            total_size = 0
            total_keys = 0
            collections = {}
            
            for guild_id in guilds:
                data = await self.get_guild_data(guild_id)
                if not data:
                    continue
                    
                guild_size = len(json.dumps(data))
                total_size += guild_size
                total_keys += 1
                
                for section, section_data in data.items():
                    if section not in collections:
                        collections[section] = {'size': 0, 'keys': 0}
                    
                    collections[section]['size'] += len(json.dumps(section_data))
                    collections[section]['keys'] += (
                        len(section_data) if isinstance(section_data, (dict, list)) else 1
                    )
            
            return {
                'status': 'connected',
                'total_size': total_size,
                'total_keys': total_keys,
                'collections': collections,
                'prefix': 'guild:'
            }
        except Exception as e:
            print(f"Error getting connection stats: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def sync_guilds(self, bot) -> dict:
        """Synchronize guild data with current bot guilds"""
        try:
            success = 0
            failed = 0
            guilds = []

            # Get current guilds list
            for guild in bot.guilds:
                try:
                    # Ensure guild data exists
                    guild_data = await self.get_guild_data(guild.id)
                    if not guild_data:
                        # Initialize new guild
                        guild_data = {
                            'id': str(guild.id),
                            'name': guild.name,
                            'joined_at': datetime.utcnow().isoformat(),
                            'whisper_config': {'enabled': False},
                            'logs': {'enabled': False},
                            'xp_settings': {'enabled': True, 'rate': 15, 'cooldown': 60},
                            'roles': {'color_roles': [], 'level_roles': {}}
                        }
                        await self._write_data(f"guild:{guild.id}", guild_data)
                    
                    guilds.append(str(guild.id))
                    success += 1
                except Exception as e:
                    print(f"Failed to sync guild {guild.name}: {e}")
                    failed += 1

            # Save updated guilds list
            await self._write_data('guilds', guilds)
            
            return {
                'success': success,
                'failed': failed
            }

        except Exception as e:
            print(f"Error syncing guilds: {e}")
            return {
                'success': 0,
                'failed': len(bot.guilds)
            }

    async def get_defaults(self, section: str) -> Optional[dict]:
        """Get default configuration for a section"""
        defaults = {
            'whisper_config': {
                'enabled': False,
                'channel_id': None,
                'staff_role': None,
                'anonymous_allowed': True
            },
            'logs': {
                'enabled': False,
                'log_channel': None,
                'log_types': {
                    'member': ['join', 'leave'],
                    'server': ['message_delete', 'message_edit'],
                    'mod': ['warn', 'kick', 'ban', 'timeout']
                }
            },
            'xp_settings': {
                'enabled': True,
                'rate': 15,
                'cooldown': 60,
                'level_roles': {}
            },
            'roles': {
                'color_roles': [],
                'level_roles': {},
                'staff_role': None,
                'muted_role': None
            }
        }
        return defaults.get(section)

    async def ensure_guild_exists(self, guild_id: int, guild_name: str) -> bool:
        """Ensure guild data exists, initialize if not"""
        try:
            guilds = await self._read_data('guilds') or []
            guild_data = await self.get_guild_data(guild_id)

            if not guild_data:
                # Initialize new guild
                guild_data = {
                    'id': str(guild_id),
                    'name': guild_name,
                    'joined_at': datetime.utcnow().isoformat(),
                    'whisper_config': {'enabled': False},
                    'logs': {'enabled': False},
                    'xp_settings': {'enabled': True, 'rate': 15, 'cooldown': 60},
                    'roles': {'color_roles': [], 'level_roles': {}}
                }
                await self._write_data(f"guild:{guild_id}", guild_data)

            if str(guild_id) not in guilds:
                guilds.append(str(guild_id))
                await self._write_data('guilds', guilds)

            return True

        except Exception as e:
            print(f"Error ensuring guild exists: {e}")
            return False

    async def increment_stat(self, bot_id: int, stat_name: str) -> bool:
        """Increment a bot statistic"""
        try:
            stats = await self.get_bot_stats(bot_id) or {}
            stats[stat_name] = stats.get(stat_name, 0) + 1
            return await self._write_data(f"bot_stats:{bot_id}", stats)
        except Exception as e:
            print(f"Error incrementing stat: {e}")
            return False

    async def get_bot_stats(self, bot_id: int) -> Optional[dict]:
        """Get bot statistics"""
        try:
            data = await self._read_data(f"bot_stats:{bot_id}")
            if isinstance(data, str):
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {}
            return data if data else {}
        except Exception as e:
            print(f"Error getting bot stats: {e}")
            return None

    async def validate_schema(self, data: Any, schema_type: str) -> bool:
        """Validate data against a known schema type"""
        try:
            schemas = {
                'whisper': {
                    'required': ['enabled', 'channel_id', 'staff_role'],
                    'types': {
                        'enabled': bool,
                        'channel_id': (str, type(None)),
                        'staff_role': (str, type(None)),
                        'anonymous_allowed': bool,
                        'auto_close_minutes': (int, type(None))
                    }
                },
                'logs': {
                    'required': ['enabled', 'log_channel', 'log_types'],
                    'types': {
                        'enabled': bool,
                        'log_channel': (str, type(None)),
                        'log_types': dict
                    }
                },
                'xp': {
                    'required': ['enabled', 'rate', 'cooldown'],
                    'types': {
                        'enabled': bool,
                        'rate': int,
                        'cooldown': int,
                        'level_roles': dict
                    }
                }
            }

            if schema_type not in schemas:
                return True  # Skip validation for unknown schemas

            schema = schemas[schema_type]

            # Check required fields
            for field in schema['required']:
                if field not in data:
                    print(f"Missing required field {field} for schema {schema_type}")
                    return False

            # Check field types
            for field, value in data.items():
                if field in schema['types']:
                    expected_type = schema['types'][field]
                    if not isinstance(value, expected_type):
                        if isinstance(expected_type, tuple):
                            if not any(isinstance(value, t) for t in expected_type):
                                print(f"Invalid type for field {field} in schema {schema_type}")
                                return False
                        else:
                            print(f"Invalid type for field {field} in schema {schema_type}")
                            return False

            return True
        except Exception as e:
            print(f"Error validating schema: {e}")
            return False

    async def repair_data(self, guild_id: int) -> bool:
        """Attempt to repair corrupted guild data"""
        try:
            data = await self.get_guild_data(guild_id)
            if not data:
                # Initialize with defaults if no data exists
                return await self.ensure_guild_exists(guild_id, "Unknown Guild")

            changes = False

            # Check and repair known sections
            sections = {
                'whisper_config': 'whisper',
                'logs': 'logs',
                'xp_settings': 'xp'
            }

            for section, schema in sections.items():
                if section in data:
                    if not await self.validate_schema(data[section], schema):
                        # Get default config for invalid section
                        default = await self.get_defaults(section)
                        if default:
                            # Preserve valid fields from existing data
                            merged = default.copy()
                            if isinstance(data[section], dict):
                                for key, value in data[section].items():
                                    if key in default:
                                        try:
                                            if isinstance(value, type(default[key])):
                                                merged[key] = value
                                        except Exception:
                                            pass
                            data[section] = merged
                            changes = True
                else:
                    # Add missing section with defaults
                    default = await self.get_defaults(section)
                    if default:
                        data[section] = default
                        changes = True

            if changes:
                # Save repaired data
                return await self._write_data(f"guild:{guild_id}", data)
            return True

        except Exception as e:
            print(f"Error repairing guild data: {e}")
            return False

    async def backup_guild_data(self, guild_id: int, backup_reason: str = "") -> bool:
        """Create a backup of guild data"""
        try:
            data = await self.get_guild_data(guild_id)
            if not data:
                return False

            # Add backup metadata
            backup = {
                'data': data,
                'timestamp': datetime.utcnow().isoformat(),
                'reason': backup_reason
            }

            # Store backup with timestamp
            backup_key = f"backup:{guild_id}:{int(datetime.utcnow().timestamp())}"
            success = await self._write_data(backup_key, backup)

            if success:
                # Keep only last 5 backups
                backups = await self._list_keys(f"backup:{guild_id}:")
                if len(backups) > 5:
                    backups.sort()  # Sort by timestamp
                    for old_backup in backups[:-5]:
                        await self._delete_data(old_backup)

            return success

        except Exception as e:
            print(f"Error creating backup: {e}")
            return False

# Alias for backward compatibility
DBManager = DatabaseManager
