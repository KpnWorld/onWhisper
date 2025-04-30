import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import asyncio

class DBManager:
    _shared_state = {
        'initialized': False,
        'db': None,
        'initializing': False
    }

    def __init__(self, name='bot'):
        self.__dict__ = self._shared_state
        self.name = name
        self.prefix = f"{name}:"

    async def initialize(self) -> bool:
        """Initialize database connection and verify structure"""
        if self.initialized:
            return True
            
        if self.initializing:
            while self.initializing:
                await asyncio.sleep(0.1)
            return self.initialized

        try:
            self.initializing = True
            self.db = db
            
            # Test write operation
            test_key = f"{self.prefix}test"
            self.db[test_key] = "test"
            read_value = self.db[test_key]
            del self.db[test_key]
            
            if read_value != "test":
                raise Exception("Database read/write verification failed")
                
            self.initialized = True
            return True
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            self.db = None
            return False
        finally:
            self.initializing = False

    async def ensure_connection(self) -> bool:
        """Ensure database is connected and initialized"""
        if not self.initialized:
            return await self.initialize()
        if not await self.check_connection():
            self.initialized = False
            return await self.initialize()
        return True

    async def check_connection(self) -> bool:
        """Verify database connection is working"""
        try:
            if not self.db:
                return False
                
            test_key = f"{self.prefix}healthcheck"
            test_value = datetime.utcnow().isoformat()
            
            try:
                self.db[test_key] = test_value
                read_value = self.db[test_key]
                del self.db[test_key]
                return read_value == test_value
            except:
                return False
                
        except Exception:
            return False

    async def ensure_guild_exists(self, guild_id: int, guild_name: str = None) -> bool:
        """Ensure guild data exists with proper structure"""
        try:
            if not await self.ensure_connection():
                return False
                
            data = await self.get_guild_data(guild_id)
            if not data:
                return False
                
            # Verify structure is complete
            expected_keys = ['xp', 'tickets', 'logging', 'moderation', 'autorole']
            missing = [k for k in expected_keys if k not in data]
            
            if missing:
                # Repair missing sections
                await self.get_guild_data(guild_id)
                
            return True
            
        except Exception as e:
            print(f"Error ensuring guild exists: {e}")
            return False

    async def get_guild_data(self, guild_id: int) -> dict:
        """Get all data for a guild, with proper initialization"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")

            key = f"{self.prefix}guild:{guild_id}"
            if key not in self.db:
                # Create default guild structure matching cogs
                default_data = {
                    'xp': {
                        'settings': {
                            'rate': 15,
                            'cooldown': 60,
                            'enabled': True
                        },
                        'users': {},
                        'roles': {}
                    },
                    'tickets': {
                        'settings': {
                            'category_id': None,
                            'support_role_id': None,
                            'enabled': True
                        },
                        'active': [],
                        'archived': []
                    },
                    'logging': {
                        'settings': {
                            'channel_id': None,
                            'enabled': True,
                            'events': {
                                'messages': True,
                                'members': True,
                                'moderation': True,
                                'server': True
                            }
                        }
                    },
                    'moderation': {
                        'settings': {
                            'muted_role_id': None,
                            'mod_role_id': None,
                            'warn_expire_days': 30,
                            'max_warnings': 3
                        },
                        'cases': []
                    },
                    'autorole': {
                        'settings': {
                            'role_id': None,
                            'enabled': False
                        },
                        'reaction_roles': {}
                    }
                }
                self.db[key] = json.dumps(default_data)
                return default_data
            return json.loads(self.db[key])
        except Exception as e:
            print(f"Error getting guild data: {e}")
            raise

    async def update_guild_data(self, guild_id: int, updates: dict, path: list = None):
        """Update guild data at specific path"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            data = await self.get_guild_data(guild_id)
            
            if path:
                # Navigate to nested location
                current = data
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = updates
            else:
                data.update(updates)

            # Save with metadata
            data['last_updated'] = datetime.utcnow().isoformat()
            self.db[f"{self.prefix}guild:{guild_id}"] = json.dumps(data)
            
        except Exception as e:
            print(f"Error updating guild data: {e}")
            raise

    async def get_data(self, collection: str, key: str) -> dict:
        """Get data from a collection with connection management"""
        if not await self.ensure_connection():
            return None
            
        db_key = f"{self.prefix}{collection}:{key}"
        if db_key not in self.db:
            return None
            
        return json.loads(self.db[db_key])

    async def set_data(self, collection: str, key: str, data: dict):
        """Set data in a collection"""
        try:
            if not self.db:
                await self.initialize()
                if not self.db:
                    raise Exception("Database not available")
                    
            db_key = f"{self.prefix}{collection}:{key}"
            self.db[db_key] = json.dumps(data)
        except Exception as e:
            print(f"Error setting data: {e}")
            raise

    async def log_event(self, guild_id: int, user_id: int, event_type: str, details: str, **kwargs):
        """Log an event with additional metadata"""
        try:
            if not self.db:
                await self.initialize()
                if not self.db:
                    return
                    
            event_data = {
                'guild_id': guild_id,
                'user_id': user_id,
                'action': event_type,
                'details': details,
                'timestamp': datetime.utcnow().isoformat(),
                **kwargs
            }
            
            key = f"{self.prefix}logs:{guild_id}:{int(datetime.utcnow().timestamp())}"
            self.db[key] = json.dumps(event_data)
            
        except Exception as e:
            print(f"Error logging event: {e}")

    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        try:
            if not await self.ensure_connection():
                return
                
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            for guild_id in [k.split(':')[2] for k in self.db.keys() if k.startswith(f"{self.prefix}guild:")]:
                data = await self.get_guild_data(int(guild_id))
                
                # Clean old tickets
                if 'tickets' in data:
                    data['tickets']['archived'] = [
                        t for t in data['tickets'].get('archived', [])
                        if datetime.fromisoformat(t['closed_at']) > cutoff
                    ]
                
                # Clean old mod cases
                if 'moderation' in data:
                    data['moderation']['cases'] = [
                        c for c in data['moderation'].get('cases', [])
                        if not c.get('expires') or 
                        datetime.fromisoformat(c['expires']) > cutoff
                    ]
                
                # Update cleaned data
                await self.update_guild_data(int(guild_id), data)
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
            raise

    async def optimize(self):
        """Optimize database structure"""
        try:
            if not await self.ensure_connection():
                return
                
            # Verify all guild data matches current structure
            for key in self.db.keys():
                if key.startswith(f"{self.prefix}guild:"):
                    guild_id = int(key.split(':')[2])
                    await self.get_guild_data(guild_id)  # This will fix structure
                    
        except Exception as e:
            print(f"Error during optimization: {e}")
            raise

    async def add_warning(self, guild_id: int, user_id: int, mod_id: int, reason: str, timestamp: datetime):
        """Add a warning to a user"""
        try:
            warning = {
                'mod_id': mod_id,
                'reason': reason,
                'timestamp': timestamp.isoformat()
            }
            
            await self.update_guild_data(
                guild_id,
                {'warnings': [warning]},
                ['moderation', 'users', str(user_id)]
            )
        except Exception as e:
            print(f"Error adding warning: {e}")
            raise

    async def get_warnings(self, guild_id: int, user_id: int) -> list:
        """Get all warnings for a user"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            return guild_data.get('moderation', {}).get('users', {}).get(str(user_id), {}).get('warnings', [])
        except Exception as e:
            print(f"Error getting warnings: {e}")
            return []

    async def update_user_level_data(self, guild_id: int, user_id: int, xp: int, level: int, timestamp: datetime):
        """Update user XP and level data"""
        try:
            await self.update_guild_data(
                guild_id,
                {
                    'xp': xp,
                    'level': level,
                    'last_xp': timestamp.isoformat()
                },
                ['xp', 'users', str(user_id)]
            )
        except Exception as e:
            print(f"Error updating user level data: {e}")
            raise

    async def get_user_level_data(self, guild_id: int, user_id: int) -> dict:
        """Get user XP and level data"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            return guild_data.get('xp', {}).get('users', {}).get(str(user_id), {})
        except Exception as e:
            print(f"Error getting user level data: {e}")
            return {}

    async def get_ticket_logs(self, guild_id: int, user_id: int = None) -> list:
        """Get ticket logs, optionally filtered by user"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            logs = guild_data.get('tickets', {}).get('logs', [])
            
            if user_id:
                logs = [log for log in logs if log.get('user_id') == user_id]
                
            return sorted(logs, key=lambda x: datetime.fromisoformat(x.get('timestamp')), reverse=True)
        except Exception as e:
            print(f"Error getting ticket logs: {e}")
            return []

    async def get_last_deleted(self, channel_id: int) -> dict:
        """Get last deleted message in a channel"""
        try:
            key = f"{self.prefix}snipe:{channel_id}"
            data = self.db.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Error getting last deleted message: {e}")
            return None

    async def log_deleted_message(self, channel_id: int, message_data: dict):
        """Store a deleted message for snipe command"""
        try:
            key = f"{self.prefix}snipe:{channel_id}"
            self.db[key] = json.dumps(message_data)
        except Exception as e:
            print(f"Error logging deleted message: {e}")
            raise

    async def set_auto_role(self, guild_id: int, role_id: int, enabled: bool = True):
        """Set auto-role for new members"""
        try:
            await self.update_guild_data(
                guild_id,
                {
                    'role_id': role_id,
                    'enabled': enabled
                },
                ['autorole', 'settings']
            )
        except Exception as e:
            print(f"Error setting auto-role: {e}")
            raise

    async def get_auto_role(self, guild_id: int) -> tuple:
        """Get auto-role settings"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            settings = guild_data.get('autorole', {}).get('settings', {})
            return (settings.get('role_id'), settings.get('enabled', False))
        except Exception as e:
            print(f"Error getting auto-role: {e}")
            return (None, False)

    async def get_all_levels(self, guild_id: int) -> dict:
        """Get all user levels in a guild"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            return guild_data.get('xp', {}).get('users', {})
        except Exception as e:
            print(f"Error getting all levels: {e}")
            return []

    async def add_level_reward(self, guild_id: int, level: int, role_id: int):
        """Add a role reward for reaching a level"""
        try:
            key = f"{self.prefix}level_roles:{guild_id}:{level}"
            self.db[key] = json.dumps({
                'level': level,
                'role_id': role_id,
                'last_updated': datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"Error adding level reward: {e}")
            raise

    async def remove_level_reward(self, guild_id: int, level: int) -> bool:
        """Remove a level reward"""
        try:
            key = f"{self.prefix}level_roles:{guild_id}:{level}"
            if key in self.db:
                del self.db[key]
                return True
            return False
        except Exception as e:
            print(f"Error removing level reward: {e}")
            return False

    async def get_level_rewards(self, guild_id: int) -> list:
        """Get all level rewards for a guild"""
        try:
            rewards = []
            prefix = f"{self.prefix}level_roles:{guild_id}:"
            
            for key in self.db.keys():
                if key.startswith(prefix):
                    data = json.loads(self.db[key])
                    rewards.append((data['level'], data['role_id']))
            
            return sorted(rewards, key=lambda x: x[0])
        except Exception as e:
            print(f"Error getting level rewards: {e}")
            return []
