from replit import db
from datetime import datetime, timedelta
import json

class DBManager:
    def __init__(self, name='bot'):
        self.name = name
        self.prefix = f"{name}:"
        self.db = None
        
    async def initialize(self) -> bool:
        """Initialize database connection and verify structure"""
        try:
            self.db = db
            
            # Test write operation
            test_key = f"{self.prefix}test"
            self.db[test_key] = "test"
            read_value = self.db[test_key]
            del self.db[test_key]
            
            if read_value != "test":
                raise Exception("Database read/write verification failed")
                
            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            self.db = None
            return False

    async def check_connection(self) -> bool:
        """Verify database connection is working"""
        try:
            if not self.db:
                return False
                
            # Test read/write
            test_key = f"{self.prefix}healthcheck"
            test_value = datetime.utcnow().isoformat()
            self.db[test_key] = test_value
            read_value = self.db[test_key]
            del self.db[test_key]
            
            return read_value == test_value
        except Exception as e:
            print(f"Database health check error: {e}")
            return False

    async def reconnect(self) -> bool:
        """Attempt to reconnect to database"""
        try:
            self.db = db
            return await self.check_connection()
        except Exception as e:
            print(f"Database reconnection error: {e}")
            return False

    async def close(self):
        """Close database connection"""
        try:
            self.db = None
        except Exception as e:
            print(f"Error closing database: {e}")

    async def get_guild_data(self, guild_id: int) -> dict:
        """Get all data for a guild, creating default structure if needed"""
        try:
            key = f"{self.prefix}guild:{guild_id}"
            if key not in self.db:
                default_data = {
                    "xp_settings": {
                        "rate": 15,
                        "cooldown": 60,
                        "enabled": True
                    },
                    "xp_users": {},
                    "level_roles": {},
                    "tickets": {
                        "open_tickets": [],
                        "logs": []
                    },
                    "mod_actions": [],
                    "reaction_roles": {},
                    "logs_config": {
                        "mod_channel": None,
                        "join_channel": None,
                        "enabled": True
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
            data = await self.get_guild_data(guild_id)
            
            if path:
                # Navigate to the correct nested location
                current = data
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = updates
            else:
                # Update root level
                data.update(updates)

            # Save back to database
            self.db[f"{self.prefix}guild:{guild_id}"] = json.dumps(data)
            
        except Exception as e:
            print(f"Error updating guild data: {e}")
            raise

    async def add_user_leveling(self, user_id: int, guild_id: int, level: int, xp: int):
        """Add or update user level information"""
        try:
            await self.update_guild_data(
                guild_id,
                {
                    str(user_id): {
                        "level": level,
                        "xp": xp,
                        "last_xp": datetime.utcnow().isoformat()
                    }
                },
                ["xp_users"]
            )
        except Exception as e:
            print(f"Level update error: {e}")
            raise

    async def get_user_leveling(self, user_id: int, guild_id: int):
        """Get user level information"""
        try:
            data = await self.get_guild_data(guild_id)
            user_data = data.get("xp_users", {}).get(str(user_id))
            if user_data:
                return (user_data["level"], user_data["xp"])
            return (0, 0)
        except Exception as e:
            print(f"Level get error: {e}")
            raise

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        """Set a level role reward"""
        try:
            await self.update_guild_data(
                guild_id,
                {str(level): role_id},
                ["level_roles"]
            )
        except Exception as e:
            print(f"Level role set error: {e}")
            raise

    async def get_level_role(self, guild_id: int, level: int):
        """Get role ID for a specific level"""
        try:
            data = await self.get_guild_data(guild_id)
            return data.get("level_roles", {}).get(str(level))
        except Exception as e:
            print(f"Get level role error: {e}")
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
            await self.update_guild_data(
                guild_id,
                ticket_data,
                ["tickets", "open_tickets"]
            )
        except Exception as e:
            print(f"Ticket creation error: {e}")
            raise

    async def close_ticket(self, guild_id: int, channel_id: int):
        """Close a ticket"""
        try:
            ticket = await self.get_ticket_by_channel(guild_id, channel_id)
            if ticket:
                ticket['closed_at'] = datetime.utcnow().isoformat()
                await self.update_guild_data(
                    guild_id,
                    ticket,
                    ["tickets", "open_tickets"]
                )
        except Exception as e:
            print(f"Ticket close error: {e}")
            raise

    async def get_ticket_by_channel(self, guild_id: int, channel_id: int):
        """Get ticket information by channel ID"""
        try:
            data = await self.get_guild_data(guild_id)
            open_tickets = data.get("tickets", {}).get("open_tickets", [])
            for ticket in open_tickets:
                if ticket.get("channel_id") == channel_id:
                    return ticket
            return None
        except Exception as e:
            print(f"Ticket get error: {e}")
            raise

    async def check_open_ticket(self, guild_id: int, user_id: int):
        """Check if user has an open ticket"""
        try:
            data = await self.get_guild_data(guild_id)
            open_tickets = data.get("tickets", {}).get("open_tickets", [])
            for ticket in open_tickets:
                if ticket.get("user_id") == user_id:
                    return ticket
            return None
        except Exception as e:
            print(f"Open ticket check error: {e}")
            raise

    async def add_mod_action(self, guild_id: int, action: str, user_id: int, details: str = None, expires: datetime = None):
        """Log a moderation action, keeping only recent history"""
        try:
            # Get current mod actions
            data = await self.get_guild_data(guild_id)
            mod_actions = data.get('mod_actions', [])

            # Add new action
            action_data = {
                "action": action,
                "user_id": user_id,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
                "expires": expires.isoformat() if expires else None
            }

            # Remove expired actions
            current_time = datetime.utcnow()
            mod_actions = [
                action for action in mod_actions 
                if not action.get('expires') or 
                datetime.fromisoformat(action['expires']) > current_time
            ]

            # Add new action and keep only last 100
            mod_actions.append(action_data)
            if len(mod_actions) > 100:
                mod_actions = mod_actions[-100:]

            # Update database
            await self.update_guild_data(
                guild_id,
                {'mod_actions': mod_actions}
            )

        except Exception as e:
            print(f"Add mod action error: {e}")
            raise

    async def get_mod_actions(self, guild_id: int, user_id: int = None):
        """Get moderation actions log, optionally filtered by user"""
        try:
            data = await self.get_guild_data(guild_id)
            mod_actions = data.get('mod_actions', [])

            # Clean expired actions
            current_time = datetime.utcnow()
            mod_actions = [
                action for action in mod_actions 
                if not action.get('expires') or 
                datetime.fromisoformat(action['expires']) > current_time
            ]

            # Filter by user if specified
            if user_id:
                mod_actions = [
                    action for action in mod_actions 
                    if action['user_id'] == user_id
                ]

            return mod_actions
        except Exception as e:
            print(f"Get mod actions error: {e}")
            raise

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        """Add a reaction role binding"""
        try:
            await self.update_guild_data(
                guild_id,
                role_id,
                ["reaction_roles", str(message_id), emoji]
            )
        except Exception as e:
            print(f"Reaction role add error: {e}")
            raise

    async def get_reaction_roles(self, guild_id: int, message_id: int):
        """Get reaction role bindings for a message"""
        try:
            data = await self.get_guild_data(guild_id)
            return data.get("reaction_roles", {}).get(str(message_id), {})
        except Exception as e:
            print(f"Reaction roles get error: {e}")
            raise

    async def remove_reaction_role(self, guild_id: int, message_id: int, emoji: str) -> bool:
        """Remove a reaction role binding. Returns True if binding existed."""
        try:
            data = await self.get_guild_data(guild_id)
            reaction_roles = data.get("reaction_roles", {})
            message_roles = reaction_roles.get(str(message_id), {})
            if emoji in message_roles:
                del message_roles[emoji]
                # If no more roles for this message, remove the message entry
                if not message_roles:
                    del reaction_roles[str(message_id)]
                else:
                    reaction_roles[str(message_id)] = message_roles
                await self.update_guild_data(guild_id, reaction_roles, ["reaction_roles"])
                return True
            return False
        except Exception as e:
            print(f"Reaction role remove error: {e}")
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
        """Get all data collections for a guild"""
        try:
            collections = {}
            prefix = f"{self.prefix}guild:{guild_id}:"
            
            # Get main guild data
            guild_data = await self.get_guild_data(guild_id)
            if guild_data:
                collections['guild'] = guild_data
            
            # Get other collections
            for key in self.db.keys():
                if key.startswith(prefix):
                    collection = key.split(':')[2]  # Get collection name from key
                    try:
                        data = json.loads(self.db[key])
                        if collection not in collections:
                            collections[collection] = {}
                        collections[collection][key] = data
                    except:
                        continue
                        
            return collections
        except Exception as e:
            print(f"Error getting all guild data: {e}")
            raise

    async def get_leaderboard(self, guild_id: int, limit: int = 100) -> list:
        """Get the XP leaderboard for a guild"""
        try:
            guild_data = await self.get_guild_data(guild_id)
            xp_users = guild_data.get('xp_users', {})
            
            # Convert to list of tuples (user_id, level, xp)
            leaderboard = [
                (int(user_id), data['level'], data['xp'])
                for user_id, data in xp_users.items()
            ]
            
            # Sort by XP, then by level
            leaderboard.sort(key=lambda x: (x[2], x[1]), reverse=True)
            
            return leaderboard[:limit]
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            raise

    async def get_data(self, collection: str, key: str) -> dict:
        """Get data from a collection"""
        try:
            if not self.db:
                await self.initialize()
                if not self.db:
                    return None
                    
            db_key = f"{self.prefix}{collection}:{key}"
            if db_key not in self.db:
                return None
                
            return json.loads(self.db[db_key])
        except Exception as e:
            print(f"Error getting data: {e}")
            return None

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
