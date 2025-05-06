import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta, timezone
import asyncio
from replit import db
from typing import Optional, Dict, Any, List, Union, Callable
import random
import aiofiles

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

    async def initialize(self) -> bool:
        """Initialize database connection and create required directories/files"""
        try:
            if self._initialized:
                return True

            # Create data directory if it doesn't exist
            import os
            os.makedirs('data', exist_ok=True)

            # Initialize guilds file if it doesn't exist
            guilds_data = await self._read_data('guilds')
            if guilds_data is None:
                await self._write_data('guilds', [])

            # Verify we can read and write to the database
            test_key = "db_test"
            test_data = {"test": True, "timestamp": datetime.utcnow().isoformat()}
            
            # Test write
            if not await self._write_data(test_key, test_data):
                print("Failed to write test data")
                return False

            # Test read
            read_data = await self._read_data(test_key)
            if not read_data or read_data.get('test') is not True:
                print("Failed to verify test data")
                return False

            # Clean up test data
            try:
                import os
                os.remove(f'data/{test_key}.json')
            except:
                pass

            self._initialized = True
            return True

        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        try:
            if not self._initialized:
                return False

            # Try to read guilds file as connection test
            guilds = await self._read_data('guilds')
            return guilds is not None

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

    async def _write_data(self, key: str, data: Any) -> bool:
        """Write data to storage with proper locking"""
        try:
            async with self._write_lock:
                async with aiofiles.open(f'data/{key}.json', 'w') as f:
                    await f.write(json.dumps(data, indent=2))
                self._cache[key] = data
                return True
        except Exception as e:
            print(f"Error writing data: {e}")
            return False

    async def _read_data(self, key: str) -> Optional[Any]:
        """Read data from storage with caching"""
        if key in self._cache:
            return self._cache[key]

        try:
            async with aiofiles.open(f'data/{key}.json', 'r') as f:
                data = json.loads(await f.read())
                self._cache[key] = data
                return data
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error reading data: {e}")
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

# Alias for backward compatibility
DBManager = DatabaseManager
