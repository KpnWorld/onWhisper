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

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                # Commit changes
                for key, value in self.changes.items():
                    await self.db_manager._write_data(key, value)
        finally:
            self._lock.release()

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
            if key in db:
                data = db[key]
                # Convert string data to JSON if needed
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass
                self._cache[key] = data
                return data
            return None
        except Exception as e:
            print(f"Error reading data: {e}")
            return None

    async def _write_data(self, key: str, data: Any) -> bool:
        """Write data to Replit database with proper locking"""
        try:
            async with self._write_lock:
                # Convert data to JSON string if it's not already a string
                if not isinstance(data, str):
                    data = json.dumps(data)
                
                db[key] = data
                self._cache[key] = data
                return True
        except Exception as e:
            print(f"Error writing data: {e}")
            return False

    async def _delete_data(self, key: str) -> bool:
        """Delete data from Replit database"""
        try:
            if key in db:
                del db[key]
                self._cache.pop(key, None)
                return True
            return False
        except Exception as e:
            print(f"Error deleting data: {e}")
            return False

    async def _list_keys(self, prefix: str = "") -> List[str]:
        """List all keys with given prefix"""
        try:
            if prefix:
                return list(db.prefix(prefix))
            return list(db.keys())
        except Exception as e:
            print(f"Error listing keys: {e}")
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

    async def get_guild_data(self, guild_id: int) -> dict:
        """Get all data for a guild"""
        key = f"guild:{guild_id}"
        return await self._read_data(key) or {}

    async def get_section(self, guild_id: int, section: str) -> Optional[dict]:
        """Get a specific section of guild data"""
        data = await self.get_guild_data(guild_id)
        return data.get(section, {})

    async def update_section(self, guild_id: int, section: str, data: dict) -> bool:
        """Update a specific section of guild data"""
        key = f"guild:{guild_id}"
        guild_data = await self.get_guild_data(guild_id)
        guild_data[section] = data
        return await self._write_data(key, guild_data)

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
            cutoff = datetime.utcnow() - timedelta(days=days)
            guilds = await self._read_data('guilds') or []
            
            for guild_id in guilds:
                data = await self.get_guild_data(guild_id)
                
                # Clean up logs
                if 'logs' in data:
                    data['logs'] = [
                        log for log in data['logs']
                        if datetime.fromisoformat(log['timestamp']) > cutoff
                    ]
                
                # Clean up expired warnings
                if 'mod_actions' in data:
                    data['mod_actions'] = [
                        action for action in data['mod_actions']
                        if not action.get('expires') or
                        datetime.fromisoformat(action['expires']) > datetime.utcnow()
                    ]
                
                # Clean up closed whispers
                if 'whispers' in data:
                    data['whispers'] = [
                        w for w in data['whispers']
                        if not w.get('closed_at') or
                        datetime.fromisoformat(w['closed_at']) > cutoff
                    ]
                
                await self._write_data(f"guild:{guild_id}", data)
                
            return True
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False

    async def optimize(self) -> bool:
        """Optimize database storage"""
        try:
            # Clear cache to force reloading
            self._cache.clear()
            
            # Rewrite all data to clean up storage
            guilds = await self._read_data('guilds') or []
            for guild_id in guilds:
                data = await self.get_guild_data(guild_id)
                if data:
                    await self._write_data(f"guild:{guild_id}", data)
            
            return True
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
            stats_data = await self._read_data(f"bot_stats:{bot_id}")
            stats = {}
            if stats_data:
                try:
                    stats = json.loads(stats_data) if isinstance(stats_data, str) else stats_data
                except json.JSONDecodeError:
                    stats = {}
            
            stats[stat_name] = stats.get(stat_name, 0) + 1
            return await self._write_data(f"bot_stats:{bot_id}", stats)
        except Exception as e:
            print(f"Error incrementing stat: {e}")
            return False

    async def get_bot_stats(self, bot_id: int) -> Optional[dict]:
        """Get bot statistics"""
        try:
            return await self._read_data(f"bot_stats:{bot_id}")
        except Exception as e:
            print(f"Error getting bot stats: {e}")
            return None

# Alias for backward compatibility
DBManager = DatabaseManager
