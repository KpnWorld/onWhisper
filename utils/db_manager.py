import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import asyncio
from replit import db  # Add database backend import
from typing import Optional, Dict, Any, List, Union

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

    async def close(self):
        """Close the database connection"""
        try:
            self.initialized = False
            self.db = None
        except Exception as e:
            print(f"Error closing database connection: {e}")

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
            expected_keys = ['whisper_config', 'whispers', 'xp_settings', 'xp_users', 'level_roles', 'mod_actions', 'reaction_roles', 'logs_config']
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
                # Create default guild structure
                default_data = {
                    'whisper_config': {
                        'enabled': True,
                        'staff_role': None,
                        'auto_close_minutes': 1440,
                        'anonymous_allowed': False
                    },
                    'whispers': [],
                    'xp_settings': {
                        'enabled': True,
                        'rate': 15,
                        'cooldown': 60
                    },
                    'xp_users': {},
                    'level_roles': {},
                    'mod_actions': [],
                    'reaction_roles': {},
                    'logs_config': {
                        'enabled': True,
                        'channels': {}  # channel_id -> [log_types]
                    }
                }
                self.db[key] = json.dumps(default_data)
                return default_data
            return json.loads(self.db[key])
        except Exception as e:
            print(f"Error getting guild data: {e}")
            raise

    async def update_guild_data(self, guild_id: int, section: str, data: dict):
        """Update a specific section of guild data"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            guild_data = await self.get_guild_data(guild_id)
            guild_data[section] = data
            self.db[f"{self.prefix}guild:{guild_id}"] = json.dumps(guild_data)
            
        except Exception as e:
            print(f"Error updating guild data: {e}")
            raise

    async def get_section(self, guild_id: int, section: str) -> Union[dict, list]:
        """Get a specific section of guild data"""
        try:
            data = await self.get_guild_data(guild_id)
            # Handle special sections that should be lists
            if section in ['whispers', 'mod_actions']:
                return data.get(section, [])
            return data.get(section, {})
        except Exception as e:
            print(f"Error getting section {section}: {e}")
            return {}

    async def get_guild_config(self, guild_id: int, section: str = None) -> dict:
        """Get guild configuration, optionally for a specific section"""
        try:
            data = await self.get_guild_data(guild_id)
            config = data.get('config', {})
            return config.get(section, {}) if section else config
        except Exception as e:
            print(f"Error getting guild config: {e}")
            return {}

    async def update_guild_config(self, guild_id: int, updates: dict, section: str = None) -> bool:
        """Update guild configuration, optionally for a specific section"""
        try:
            data = await self.get_guild_data(guild_id)
            
            if section:
                if 'config' not in data:
                    data['config'] = {}
                if section not in data['config']:
                    data['config'][section] = {}
                data['config'][section].update(updates)
            else:
                if 'config' not in data:
                    data['config'] = {}
                data['config'].update(updates)
            
            data['last_updated'] = datetime.utcnow().isoformat()
            self.db[f"{self.prefix}guild:{guild_id}"] = json.dumps(data)
            return True
        except Exception as e:
            print(f"Error updating guild config: {e}")
            return False

    async def update_user_level_data(self, guild_id: int, user_id: int, xp: int, level: int, timestamp: datetime):
        """Update user XP and level data"""
        try:
            data = await self.get_section(guild_id, 'xp_users')
            data[str(user_id)] = {
                'level': level,
                'xp': xp,
                'last_xp': timestamp.isoformat()
            }
            await self.update_guild_data(guild_id, 'xp_users', data)
        except Exception as e:
            print(f"Error updating user level data: {e}")
            raise

    async def get_user_level_data(self, guild_id: int, user_id: int) -> dict:
        """Get user XP and level data"""
        try:
            data = await self.get_section(guild_id, 'xp_users')
            return data.get(str(user_id), {})
        except Exception as e:
            print(f"Error getting user level data: {e}")
            return {}

    async def add_mod_action(self, guild_id: int, action: str, user_id: int, details: str, 
                            expires: datetime = None):
        """Add a moderation action"""
        try:
            mod_action = {
                'action': action,
                'user_id': str(user_id),
                'details': details,
                'timestamp': datetime.utcnow().isoformat(),
                'expires': expires.isoformat() if expires else None
            }
            
            actions = await self.get_section(guild_id, 'mod_actions')
            actions.append(mod_action)
            await self.update_guild_data(guild_id, 'mod_actions', actions)
        except Exception as e:
            print(f"Error adding mod action: {e}")
            raise

    async def add_level_role(self, guild_id: int, level: int, role_id: int):
        """Add a level-up role reward"""
        try:
            roles = await self.get_section(guild_id, 'level_roles')
            roles[str(level)] = role_id  # Store as int
            await self.update_guild_data(guild_id, 'level_roles', roles)
            return True
        except Exception as e:
            print(f"Error adding level role: {e}")
            return False

    async def remove_level_role(self, guild_id: int, level: int) -> bool:
        """Remove a level-up role"""
        try:
            roles = await self.get_section(guild_id, 'level_roles')
            if str(level) in roles:
                del roles[str(level)]
                await self.update_guild_data(guild_id, 'level_roles', roles)
                return True
            return False
        except Exception as e:
            print(f"Error removing level role: {e}")
            return False

    async def get_level_roles(self, guild_id: int) -> list:
        """Get all level-up roles"""
        try:
            roles = await self.get_section(guild_id, 'level_roles')
            return [(int(level), role_id) for level, role_id in roles.items()]
        except Exception as e:
            print(f"Error getting level roles: {e}")
            return []

    async def update_reaction_roles(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        """Update reaction role bindings"""
        try:
            reaction_roles = await self.get_section(guild_id, 'reaction_roles')
            if str(message_id) not in reaction_roles:
                reaction_roles[str(message_id)] = {}
            reaction_roles[str(message_id)][emoji] = str(role_id)
            await self.update_guild_data(guild_id, 'reaction_roles', reaction_roles)
            return True
        except Exception as e:
            print(f"Error updating reaction roles: {e}")
            return False

    async def get_reaction_roles(self, guild_id: int, message_id: int = None) -> dict:
        """Get reaction roles, optionally filtered by message"""
        try:
            reaction_roles = await self.get_section(guild_id, 'reaction_roles')
            if message_id:
                return reaction_roles.get(str(message_id), {})
            return reaction_roles
        except Exception as e:
            print(f"Error getting reaction roles: {e}")
            return {}

    async def get_ticket_logs(self, guild_id: int, user_id: int = None) -> list:
        """Get ticket logs, optionally filtered by user"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            logs = guild_data.get('data', {}).get('tickets', {}).get('logs', [])
            
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

    async def update_auto_role(self, guild_id: int, role_id: Optional[int] = None) -> bool:
        """Set or remove auto-role"""
        try:
            config = await self.get_section(guild_id, 'autorole')
            config['role_id'] = role_id
            config['enabled'] = bool(role_id)
            await self.update_guild_data(guild_id, 'autorole', config)
            return True
        except Exception as e:
            print(f"Error updating auto-role: {e}")
            return False

    async def get_auto_role(self, guild_id: int) -> tuple:
        """Get auto-role settings"""
        try:
            config = await self.get_section(guild_id, 'autorole')
            role_id = config.get('role_id')
            return (int(role_id) if role_id else None, config.get('enabled', False))
        except Exception as e:
            print(f"Error getting auto-role: {e}")
            return (None, False)

    async def get_all_levels(self, guild_id: int) -> dict:
        """Get all user levels in a guild"""
        try:
            data = await self.get_section(guild_id, 'xp_users')
            return data or {}
        except Exception as e:
            print(f"Error getting all levels: {e}")
            return {}

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

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        """Add a reaction role binding to a message"""
        try:
            data = await self.get_data('reaction_roles', str(message_id)) or {}
            data[emoji] = role_id
            await self.set_data('reaction_roles', str(message_id), data)
            
            # Also update in guild data for consistency
            reaction_roles = await self.get_section(guild_id, 'reaction_roles')
            if str(message_id) not in reaction_roles:
                reaction_roles[str(message_id)] = {}
            reaction_roles[str(message_id)][emoji] = str(role_id)
            await self.update_guild_data(guild_id, 'reaction_roles', reaction_roles)
        except Exception as e:
            print(f"Error adding reaction role: {e}")
            raise

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        """Remove a reaction role binding from a message"""
        try:
            # Remove from reaction_roles collection
            data = await self.get_data('reaction_roles', str(message_id))
            if data and emoji in data:
                del data[emoji]
                if data:
                    await self.set_data('reaction_roles', str(message_id), data)
                else:
                    await self.delete_data('reaction_roles', str(message_id))
            
            # Also remove from guild data
            reaction_roles = await self.get_section(guild_id, 'reaction_roles')
            if str(message_id) in reaction_roles and emoji in reaction_roles[str(message_id)]:
                del reaction_roles[str(message_id)][emoji]
                if not reaction_roles[str(message_id)]:
                    del reaction_roles[str(message_id)]
                await self.update_guild_data(guild_id, 'reaction_roles', reaction_roles)
                return True
            return False
        except Exception as e:
            print(f"Error removing reaction role: {e}")
            return False

    async def create_whisper_thread(self, guild_id: int, user_id: int, thread_id: int, message: str) -> bool:
        """Create a new whisper thread"""
        try:
            whisper = {
                'user_id': str(user_id),
                'thread_id': str(thread_id),
                'initial_message': message,
                'created_at': datetime.utcnow().isoformat(),
                'closed_at': None
            }
            whispers = await self.get_section(guild_id, 'whispers')
            whispers.append(whisper)
            await self.update_guild_data(guild_id, 'whispers', whispers)
            return True
        except Exception as e:
            print(f"Error creating whisper: {e}")
            return False

    async def close_whisper(self, guild_id: int, thread_id: str) -> bool:
        """Close a whisper thread"""
        try:
            whispers = await self.get_section(guild_id, 'whispers')
            for whisper in whispers:
                if whisper['thread_id'] == thread_id:
                    whisper['closed_at'] = datetime.utcnow().isoformat()
                    await self.update_guild_data(guild_id, 'whispers', whispers)
                    return True
            return False
        except Exception as e:
            print(f"Error closing whisper: {e}")
            return False

    async def get_whispers(self, guild_id: int, include_closed: bool = False) -> list:
        """Get all whispers for a guild"""
        try:
            whispers = await self.get_section(guild_id, 'whispers')
            if include_closed:
                return whispers
            return [w for w in whispers if not w.get('closed_at')]
        except Exception as e:
            print(f"Error getting whispers: {e}")
            return []

    async def get_active_whispers(self, guild_id: int) -> list:
        """Get only active whispers"""
        return await self.get_whispers(guild_id, include_closed=False)

    async def add_whisper(self, guild_id: int, thread_id: str, user_id: str, channel_id: str) -> bool:
        """Add a new whisper entry"""
        try:
            whisper = {
                'thread_id': thread_id,
                'user_id': user_id,
                'channel_id': channel_id,
                'created_at': datetime.utcnow().isoformat(),
                'closed_at': None
            }
            whispers = await self.get_section(guild_id, 'whispers')
            whispers.append(whisper)
            await self.update_guild_data(guild_id, 'whispers', whispers)
            return True
        except Exception as e:
            print(f"Error adding whisper: {e}")
            return False

    # Whisper System Methods
    async def update_whisper_config(self, guild_id: int, setting: str, value: Any) -> bool:
        """Update whisper system configuration"""
        try:
            config = await self.get_section(guild_id, 'whisper_config')
            config[setting] = value
            await self.update_guild_data(guild_id, 'whisper_config', config)
            return True
        except Exception as e:
            print(f"Error updating whisper config: {e}")
            return False

    # XP and Leveling Methods
    async def update_xp_config(self, guild_id: int, setting: str, value: Any) -> bool:
        """Update XP system configuration"""
        try:
            config = await self.get_section(guild_id, 'xp_settings')
            config[setting] = value
            await self.update_guild_data(guild_id, 'xp_settings', config)
            return True
        except Exception as e:
            print(f"Error updating XP config: {e}")
            return False

    # Moderation Methods
    async def add_warning(self, guild_id: int, user_id: int, mod_id: int, reason: str) -> bool:
        """Add a warning to a user"""
        try:
            warning = {
                'action': 'warn',
                'user_id': str(user_id),
                'mod_id': str(mod_id),
                'details': reason,
                'timestamp': datetime.utcnow().isoformat()
            }
            actions = await self.get_section(guild_id, 'mod_actions')
            actions.append(warning)
            await self.update_guild_data(guild_id, 'mod_actions', actions)
            return True
        except Exception as e:
            print(f"Error adding warning: {e}")
            return False

    async def get_user_warnings(self, guild_id: int, user_id: int) -> list:
        """Get all warnings for a user"""
        try:
            actions = await self.get_section(guild_id, 'mod_actions')
            return [
                a for a in actions 
                if a['action'] == 'warn' and a['user_id'] == str(user_id)
            ]
        except Exception as e:
            print(f"Error getting warnings: {e}")
            return []

    async def add_channel_lock(self, guild_id: int, channel_id: int, 
                             duration: int = None) -> bool:
        """Add a channel lockdown"""
        try:
            lock = {
                'channel_id': str(channel_id),
                'locked_at': datetime.utcnow().isoformat(),
                'duration': duration,
                'expires': (datetime.utcnow() + timedelta(minutes=duration)).isoformat() if duration else None
            }
            data = await self.get_section(guild_id, 'locks')
            data[str(channel_id)] = lock
            await self.update_guild_data(guild_id, 'locks', data)
            return True
        except Exception as e:
            print(f"Error adding channel lock: {e}")
            return False

    # Role Management Methods
    async def bulk_role_update(self, guild_id: int, role_id: int, 
                             user_ids: list, action: str) -> dict:
        """Bulk add/remove role from users"""
        try:
            key = f"{self.prefix}bulk_role:{guild_id}:{int(datetime.utcnow().timestamp())}"
            data = {
                'role_id': str(role_id),
                'users': [str(uid) for uid in user_ids],
                'action': action,
                'timestamp': datetime.utcnow().isoformat(),
                'status': {}
            }
            self.db[key] = json.dumps(data)
            return data
        except Exception as e:
            print(f"Error in bulk role update: {e}")
            return {}

    # Info and Stats Methods
    async def get_bot_stats(self, bot_id: int) -> dict:
        """Get bot statistics"""
        try:
            stats_key = f"{self.prefix}stats:{bot_id}"
            if stats_key not in self.db:
                return {'commands_used': 0, 'messages_seen': 0}
            return json.loads(self.db[stats_key])
        except Exception as e:
            print(f"Error getting bot stats: {e}")
            return {}

    async def increment_stat(self, bot_id: int, stat: str) -> bool:
        """Increment a bot statistic"""
        try:
            stats = await self.get_bot_stats(bot_id)
            stats[stat] = stats.get(stat, 0) + 1
            self.db[f"{self.prefix}stats:{bot_id}"] = json.dumps(stats)
            return True
        except Exception as e:
            print(f"Error incrementing stat: {e}")
            return False

    async def get_data(self, collection: str, key: str) -> Optional[Dict]:
        """Get data from a collection"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            db_key = f"{self.prefix}{collection}:{key}"
            data = self.db.get(db_key)
            return json.loads(data) if data else None
            
        except Exception as e:
            print(f"Error getting data from {collection}: {e}")
            return None

    async def set_data(self, collection: str, key: str, data: Dict) -> bool:
        """Set data in a collection"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            db_key = f"{self.prefix}{collection}:{key}"
            self.db[db_key] = json.dumps(data)
            return True
            
        except Exception as e:
            print(f"Error setting data in {collection}: {e}")
            return False

    async def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from a collection"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            db_key = f"{self.prefix}{collection}:{key}"
            if db_key in self.db:
                del self.db[db_key]
                return True
            return False
            
        except Exception as e:
            print(f"Error deleting data from {collection}: {e}")
            return False

    async def log_event(self, guild_id: int, user_id: int, event_type: str, details: str) -> bool:
        """Log an event to guild events collection"""
        try:
            event = {
                'user_id': str(user_id),
                'type': event_type,
                'details': details,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            events = await self.get_section(guild_id, 'events') or []
            events.append(event)
            await self.update_guild_data(guild_id, 'events', events)
            return True
            
        except Exception as e:
            print(f"Error logging event: {e}")
            return False

    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            cutoff = datetime.utcnow() - timedelta(days=days)
            counter = 0
            
            # Clean up old bulk role operations
            for key in list(self.db.keys()):
                if key.startswith(f"{self.prefix}bulk_role:"):
                    try:
                        data = json.loads(self.db[key])
                        if datetime.fromisoformat(data['timestamp']) < cutoff:
                            del self.db[key]
                            counter += 1
                    except:
                        continue

            # Clean up old snipe data
            for key in list(self.db.keys()):
                if key.startswith(f"{self.prefix}snipe:"):
                    try:
                        data = json.loads(self.db[key])
                        if datetime.fromisoformat(data['timestamp']) < cutoff:
                            del self.db[key]
                            counter += 1
                    except:
                        continue

            # Clean up old events
            for guild_key in list(self.db.keys()):
                if guild_key.startswith(f"{self.prefix}guild:"):
                    try:
                        guild_data = json.loads(self.db[guild_key])
                        events = guild_data.get('events', [])
                        new_events = [
                            e for e in events
                            if datetime.fromisoformat(e['timestamp']) >= cutoff
                        ]
                        if len(new_events) != len(events):
                            guild_data['events'] = new_events
                            self.db[guild_key] = json.dumps(guild_data)
                            counter += len(events) - len(new_events)
                    except:
                        continue
                        
            print(f"Cleaned up {counter} old records")
            return True
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False

    async def optimize(self) -> bool:
        """Optimize database"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            # Clean up any None or empty values
            for key in list(self.db.keys()):
                if key.startswith(self.prefix):
                    try:
                        value = self.db[key]
                        if value is None:
                            del self.db[key]
                            continue
                            
                        # Parse and re-serialize JSON to clean up formatting
                        if isinstance(value, str):
                            data = json.loads(value)
                            if not data:  # Remove empty objects/arrays
                                del self.db[key]
                            else:
                                self.db[key] = json.dumps(data)
                    except:
                        continue
                        
            return True
            
        except Exception as e:
            print(f"Error optimizing database: {e}")
            return False

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            total_keys = 0
            total_size = 0
            collections = {}
            
            # Calculate stats
            for key in self.db.keys():
                if key.startswith(self.prefix):
                    total_keys += 1
                    try:
                        size = len(str(self.db[key]).encode('utf-8'))
                        total_size += size
                        
                        # Group by collection
                        collection = key.split(':', 2)[1].split(':', 1)[0]
                        if collection not in collections:
                            collections[collection] = {'keys': 0, 'size': 0}
                        collections[collection]['keys'] += 1
                        collections[collection]['size'] += size
                    except:
                        continue
            
            return {
                'status': 'connected',
                'total_keys': total_keys,
                'total_size': total_size,
                'collections': collections,
                'prefix': self.prefix
            }
            
        except Exception as e:
            print(f"Error getting connection stats: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def get_database_size(self) -> int:
        """Get approximate database size in bytes"""
        try:
            if not await self.ensure_connection():
                raise Exception("Database not available")
                
            total_size = 0
            for key in self.db.keys():
                if key.startswith(self.prefix):
                    try:
                        total_size += len(key.encode('utf-8'))  # Key size
                        total_size += len(str(self.db[key]).encode('utf-8'))  # Value size
                    except:
                        continue
            return total_size
            
        except Exception as e:
            print(f"Error calculating database size: {e}")
            return 0

    async def cleanup_old_logs(self, guild_id: int, days: int = 30) -> bool:
        """Clean up old logs"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Clean up events
            events = await self.get_section(guild_id, 'events')
            if events:
                events = [
                    event for event in events 
                    if datetime.fromisoformat(event['timestamp']) > cutoff
                ]
                await self.update_guild_data(guild_id, 'events', events)
            
            # Clean up mod actions
            actions = await self.get_section(guild_id, 'mod_actions')
            if actions:
                actions = [
                    action for action in actions 
                    if datetime.fromisoformat(action['timestamp']) > cutoff
                ]
                await self.update_guild_data(guild_id, 'mod_actions', actions)
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up logs: {e}")
            return False

    async def get_logging_config(self, guild_id: int) -> dict:
        """Get logging configuration for a guild"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            return guild_data.get('logs_config', {
                'mod_channel': None,
                'join_channel': None,
                'enabled': False
            })
        except Exception as e:
            print(f"Error getting logging config: {e}")
            return {
                'mod_channel': None,
                'join_channel': None,
                'enabled': False
            }

    async def update_logging_config(self, guild_id: int, updates: dict):
        """Update logging configuration"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            
            # Get existing config or create default
            config = guild_data.get('logs_config', {
                'mod_channel': None,
                'join_channel': None,
                'enabled': False
            })
            
            # Update with new values
            config.update(updates)
            
            # Save back to guild data
            guild_data['logs_config'] = config
            await self.update_guild_data(guild_id, 'logs_config', config)
        except Exception as e:
            print(f"Error updating logging config: {e}")
            raise
