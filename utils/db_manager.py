from replit import db
from datetime import datetime, timedelta
import json

class DBManager:
    def __init__(self, name='bot'):
        self.name = name
        self.prefix = f"{name}:"  # Use prefix for namespacing
        try:
            self.db = db
        except Exception as e:
            print(f"Failed to initialize database connection: {e}")
            self.db = None

    async def initialize(self):
        """Initialize database tables"""
        try:
            # Verify db connection
            if not self.db:
                self.db = db

            # Initialize default collections
            collections = [
                'guilds',
                'logging_config', 
                'auto_roles',
                'reaction_roles',
                'tickets',
                'levels',
                'logs'
            ]
            
            for collection in collections:
                key = f"{self.prefix}{collection}"
                if key not in self.db:
                    self.db[key] = {}
            
            return True
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            self.db = None
            return False

    async def close(self):
        """No need to close connection with Replit db"""
        pass

    def _make_key(self, collection: str, id: str) -> str:
        """Create a composite key for the collection"""
        return f"{self.prefix}{collection}:{id}"

    async def set_data(self, collection: str, id: str, data: dict):
        """Set data in a collection"""
        try:
            key = self._make_key(collection, id)
            self.db[key] = json.dumps(data)
        except Exception as e:
            print(f"Data set error: {e}")
            raise

    async def get_data(self, collection: str, id: str) -> dict:
        """Get data from a collection"""
        try:
            key = self._make_key(collection, id)
            if key in self.db:
                return json.loads(self.db[key])
            return None
        except Exception as e:
            print(f"Data get error: {e}")
            raise

    async def delete_data(self, collection: str, id: str):
        """Delete data from a collection"""
        try:
            key = self._make_key(collection, id)
            if key in self.db:
                del self.db[key]
        except Exception as e:
            print(f"Data delete error: {e}")
            raise

    async def ensure_guild_exists(self, guild_id: int, name: str):
        """Ensure guild exists in database"""
        try:
            guild_data = await self.get_data('guilds', str(guild_id))
            if not guild_data:
                await self.set_data('guilds', str(guild_id), {
                    'name': name,
                    'joined_at': datetime.utcnow().isoformat()
                })
        except Exception as e:
            print(f"Guild creation error: {e}")
            raise

    async def set_auto_role(self, guild_id: int, role_id: int, enabled: bool):
        """Set or update auto role configuration"""
        try:
            await self.set_data('auto_roles', str(guild_id), {
                'role_id': role_id,
                'enabled': enabled
            })
        except Exception as e:
            print(f"Auto role set error: {e}")
            raise

    async def get_auto_role(self, guild_id: int):
        """Get auto role configuration"""
        try:
            data = await self.get_data('auto_roles', str(guild_id))
            if data:
                return (data['role_id'], data['enabled'])
            return None
        except Exception as e:
            print(f"Auto role get error: {e}")
            raise

    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        """Add a reaction role binding"""
        try:
            key = f"{message_id}:{emoji}"
            await self.set_data('reaction_roles', key, {
                'role_id': role_id
            })
        except Exception as e:
            print(f"Reaction role add error: {e}")
            raise

    async def get_reaction_roles(self, message_id: int):
        """Get reaction role bindings for a message"""
        try:
            prefix = f"{self.prefix}reaction_roles:{message_id}:"
            bindings = []
            for key in self.db.keys():
                if key.startswith(prefix):
                    emoji = key.split(':')[-1]
                    data = json.loads(self.db[key])
                    bindings.append((emoji, data['role_id']))
            return bindings
        except Exception as e:
            print(f"Reaction roles get error: {e}")
            raise

    async def remove_reaction_role(self, message_id: int, emoji: str) -> bool:
        """Remove a reaction role binding. Returns True if binding existed."""
        try:
            key = f"{self.prefix}reaction_roles:{message_id}:{emoji}"
            if key in self.db:
                del self.db[key]
                return True
            return False
        except Exception as e:
            print(f"Reaction role remove error: {e}")
            raise

    async def create_ticket(self, guild_id: int, channel_id: int, user_id: int):
        """Create a new ticket"""
        try:
            ticket_data = {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat(),
                'closed_at': None
            }
            await self.set_data('tickets', str(channel_id), ticket_data)
        except Exception as e:
            print(f"Ticket creation error: {e}")
            raise

    async def close_ticket(self, channel_id: int):
        """Close a ticket"""
        try:
            ticket = await self.get_data('tickets', str(channel_id))
            if ticket:
                ticket['closed_at'] = datetime.utcnow().isoformat()
                await self.set_data('tickets', str(channel_id), ticket)
        except Exception as e:
            print(f"Ticket close error: {e}")
            raise

    async def get_ticket_by_channel(self, channel_id: int):
        """Get ticket information by channel ID"""
        try:
            return await self.get_data('tickets', str(channel_id))
        except Exception as e:
            print(f"Ticket get error: {e}")
            raise

    async def get_open_ticket(self, user_id: int, guild_id: int):
        """Check if user has an open ticket"""
        try:
            prefix = f"{self.prefix}tickets:"
            for key in self.db.keys():
                if key.startswith(prefix):
                    ticket = json.loads(self.db[key])
                    if (ticket['user_id'] == user_id and 
                        ticket['guild_id'] == guild_id and 
                        ticket['closed_at'] is None):
                        return ticket
            return None
        except Exception as e:
            print(f"Open ticket check error: {e}")
            raise

    async def add_user_leveling(self, user_id: int, guild_id: int, level: int, xp: int):
        """Add or update user level information"""
        try:
            key = f"{guild_id}:{user_id}"
            await self.set_data('levels', key, {
                'level': level,
                'xp': xp,
                'last_xp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"Level update error: {e}")
            raise

    async def get_user_leveling(self, user_id: int, guild_id: int):
        """Get user level information"""
        try:
            key = f"{guild_id}:{user_id}"
            data = await self.get_data('levels', key)
            if data:
                return (data['level'], data['xp'])
            return (0, 0)
        except Exception as e:
            print(f"Level get error: {e}")
            raise

    async def get_leaderboard(self, guild_id: int, limit: int = 10):
        """Get guild leaderboard"""
        try:
            prefix = f"{self.prefix}levels:{guild_id}:"
            all_levels = []
            
            for key in self.db.keys():
                if key.startswith(prefix):
                    user_id = int(key.split(':')[-1])
                    data = json.loads(self.db[key])
                    all_levels.append((user_id, data['level'], data['xp']))
            
            # Sort by XP and take top entries
            return sorted(all_levels, key=lambda x: x[2], reverse=True)[:limit]
        except Exception as e:
            print(f"Leaderboard get error: {e}")
            raise

    async def log_event(self, guild_id: int, user_id: int, action: str, details: str = None, **kwargs):
        """Log an event with optional additional data"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_id = f"{guild_id}:{timestamp}"
            
            log_data = {
                'guild_id': guild_id,
                'user_id': user_id,
                'action': action,
                'details': details,
                'timestamp': timestamp,
                **kwargs  # Include any additional data like channel_id
            }
            
            await self.set_data('logs', log_id, log_data)
        except Exception as e:
            print(f"Event log error: {e}")
            raise

    async def cleanup_old_data(self, days: int = 30):
        """Clean up old logs and closed tickets"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Clean logs
            prefix = f"{self.prefix}logs:"
            for key in self.db.keys():
                if key.startswith(prefix):
                    log = json.loads(self.db[key])
                    if datetime.fromisoformat(log['timestamp']) < cutoff:
                        del self.db[key]
            
            # Clean tickets
            prefix = f"{self.prefix}tickets:"
            for key in self.db.keys():
                if key.startswith(prefix):
                    ticket = json.loads(self.db[key])
                    if (ticket['closed_at'] and 
                        datetime.fromisoformat(ticket['closed_at']) < cutoff):
                        del self.db[key]
                        
        except Exception as e:
            print(f"Cleanup error: {e}")
            raise

    async def optimize(self):
        """No optimization needed for Replit db"""
        pass

    async def get_connection_stats(self):
        """Get database statistics"""
        try:
            stats = {
                'total_keys': len(list(self.db.keys())),
                'collections': {}
            }
            
            # Count keys per collection
            for collection in ['guilds', 'logging_config', 'auto_roles', 
                             'reaction_roles', 'tickets', 'levels', 'logs']:
                prefix = f"{self.prefix}{collection}:"
                count = len([k for k in self.db.keys() if k.startswith(prefix)])
                stats['collections'][collection] = count
                
            return stats
        except Exception as e:
            print(f"Stats error: {e}")
            return None

    async def get_all_guild_data(self, guild_id: int) -> dict:
        """Get all data related to a specific guild"""
        try:
            guild_data = {}
            str_guild_id = str(guild_id)
            
            # Collections that store guild-specific data
            guild_collections = {
                'guilds': str_guild_id,
                'logging_config': str_guild_id,
                'auto_roles': str_guild_id,
                'tickets': lambda k: json.loads(self.db[k]).get('guild_id') == guild_id,
                'levels': lambda k: k.startswith(f"{self.prefix}levels:{guild_id}:"),
                'logs': lambda k: json.loads(self.db[k]).get('guild_id') == guild_id
            }
            
            for collection, filter_func in guild_collections.items():
                collection_data = []
                prefix = f"{self.prefix}{collection}:"
                
                for key in self.db.keys():
                    if not key.startswith(prefix):
                        continue
                        
                    if callable(filter_func):
                        if filter_func(key):
                            collection_data.append(json.loads(self.db[key]))
                    elif key == f"{prefix}{filter_func}":
                        collection_data.append(json.loads(self.db[key]))
                
                if collection_data:
                    guild_data[collection] = collection_data
                    
            return guild_data
            
        except Exception as e:
            print(f"Guild data retrieval error: {e}")
            raise

    async def update_config(self, collection: str, guild_id: str, updates: dict):
        """Update configuration while preserving existing values"""
        try:
            # Get existing config
            current_config = await self.get_data(collection, guild_id) or {}
            
            # Update with new values
            current_config.update(updates)
            
            # Save back to database
            await self.set_data(collection, guild_id, current_config)
            
        except Exception as e:
            print(f"Config update error: {e}")
            raise
