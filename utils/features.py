from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time

class FeatureType(Enum):
    """Types of features available in the bot"""
    LEVELING = "leveling"
    LOGGING = "logging"
    WHISPERS = "whispers"
    REACTION_ROLES = "reaction_roles"
    AUTOROLES = "autoroles"
    COLOR_ROLES = "color_roles"

@dataclass
class FeatureDefaults:
    """Default settings for features"""
    leveling = {
        "enabled": False,
        "options": {
            "cooldown": 60,
            "min_xp": 15,
            "max_xp": 25,
            "dm_notifications": True,
            "role_rewards": {}
        }
    }
    
    logging = {
        "enabled": False,
        "options": {
            "channel_id": None,
            "events": [
                "message_delete",
                "message_edit",
                "member_join",
                "member_leave"
            ]
        }
    }
    
    whispers = {
        "enabled": False,
        "options": {
            "channel_id": None,
            "staff_role_id": None,
            "auto_close_hours": 24,
            "log_channel_id": None,
            "threads": [],  # List to store whisper threads
            "settings": {
                "allow_attachments": True,
                "notify_staff": True,
                "user_close": False
            }
        }
    }
    
    reaction_roles = {
        "enabled": False,
        "options": {
            "max_per_message": 20,
            "restricted_roles": []
        }
    }
    
    autoroles = {
        "enabled": False,
        "options": {
            "roles": [],
            "delay_seconds": 0
        }
    }
    
    color_roles = {
        "enabled": False,
        "options": {
            "allowed_colors": [],
            "position": None
        }
    }

class FeatureManager:
    """Manages feature settings and provides a standard interface"""
    
    def __init__(self, db):
        if not db:
            raise ValueError("Database manager cannot be None")
        self.db = db
        self.defaults = FeatureDefaults()
        
    async def enable_feature(self, guild_id: int, feature: FeatureType) -> None:
        """Enable a feature with default settings"""
        default_config = getattr(self.defaults, feature.value)
        await self.db.set_feature_settings(
            guild_id,
            feature.value,
            True,
            default_config["options"]
        )
        
    async def disable_feature(self, guild_id: int, feature: FeatureType) -> None:
        """Disable a feature while preserving its settings"""
        await self.db.set_feature_settings(
            guild_id,
            feature.value,
            False,
            (await self.get_feature_settings(guild_id, feature))["options"]
        )
        
    async def get_feature_settings(self, guild_id: int, feature: FeatureType) -> Dict[str, Any]:
        """Get feature settings with defaults if not set"""
        settings = await self.db.get_feature_settings(guild_id, feature.value)
        if not settings:
            return getattr(self.defaults, feature.value)
        return settings
        
    async def update_feature_settings(
        self, 
        guild_id: int, 
        feature: FeatureType, 
        options: Dict[str, Any]
    ) -> None:
        """Update specific feature settings while preserving others"""
        current = await self.get_feature_settings(guild_id, feature)
        current["options"].update(options)
        await self.db.set_feature_settings(
            guild_id,
            feature.value,
            current["enabled"],
            current["options"]
        )
        
    async def reset_feature(self, guild_id: int, feature: FeatureType) -> None:
        """Reset a feature to default settings"""
        default_config = getattr(self.defaults, feature.value)
        await self.db.set_feature_settings(
            guild_id,
            feature.value,
            default_config["enabled"],
            default_config["options"]
        )

    def get_required_permissions(self, feature: FeatureType) -> Dict[str, bool]:
        """Get required bot permissions for a feature"""
        perms = {
            FeatureType.LEVELING: {
                "manage_roles": True
            },
            FeatureType.LOGGING: {
                "view_audit_log": True,
                "read_messages": True,
                "send_messages": True
            },
            FeatureType.WHISPERS: {
                "manage_threads": True,
                "send_messages": True
            },
            FeatureType.REACTION_ROLES: {
                "manage_roles": True,
                "add_reactions": True
            },
            FeatureType.AUTOROLES: {
                "manage_roles": True
            },
            FeatureType.COLOR_ROLES: {
                "manage_roles": True
            }
        }
        return perms[feature]

    async def get_whisper_thread(self, guild_id: int, whisper_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific whisper thread"""
        settings = await self.get_feature_settings(guild_id, FeatureType.WHISPERS)
        if not settings or not settings['enabled']:
            return None
            
        threads = settings['options'].get('threads', [])
        return next((t for t in threads if t['whisper_id'] == whisper_id), None)

    async def update_whisper_thread(self, guild_id: int, whisper_id: str, updates: Dict[str, Any]) -> bool:
        """Update a whisper thread's data"""
        settings = await self.get_feature_settings(guild_id, FeatureType.WHISPERS)
        if not settings or not settings['enabled']:
            return False
            
        threads = settings['options'].get('threads', [])
        for thread in threads:
            if thread['whisper_id'] == whisper_id:
                thread.update(updates)
                await self.update_feature_settings(
                    guild_id,
                    FeatureType.WHISPERS,
                    {'threads': threads}
                )
                return True
        return False

    async def remove_whisper_thread(self, guild_id: int, whisper_id: str) -> bool:
        """Remove a whisper thread from storage"""
        settings = await self.get_feature_settings(guild_id, FeatureType.WHISPERS)
        if not settings or not settings['enabled']:
            return False
            
        threads = settings['options'].get('threads', [])
        new_threads = [t for t in threads if t['whisper_id'] != whisper_id]
        
        if len(new_threads) != len(threads):
            await self.update_feature_settings(
                guild_id,
                FeatureType.WHISPERS,
                {'threads': new_threads}
            )
            return True
        return False

    async def cleanup_old_whispers(self, guild_id: int, hours: int = 168) -> int:
        """Clean up whisper threads older than specified hours (default 7 days)
        Returns number of threads cleaned up"""
        settings = await self.get_feature_settings(guild_id, FeatureType.WHISPERS)
        if not settings or not settings['enabled']:
            return 0
            
        current_time = time.time()
        max_age = hours * 3600  # Convert hours to seconds
        
        threads = settings['options'].get('threads', [])
        active_threads = [
            t for t in threads 
            if not t['is_closed'] or (current_time - t['closed_at']) < max_age
        ]
        
        if len(active_threads) != len(threads):
            await self.update_feature_settings(
                guild_id,
                FeatureType.WHISPERS,
                {'threads': active_threads}
            )
            return len(threads) - len(active_threads)
        return 0

    async def init_guild_features(self, guild_id: int) -> None:
        """Initialize default features for a new guild"""
        for feature in FeatureType:
            settings = await self.get_feature_settings(guild_id, feature)
            if not settings:
                default_config = getattr(self.defaults, feature.value)
                await self.db.set_feature_settings(
                    guild_id,
                    feature.value,
                    default_config["enabled"],
                    default_config["options"]
                )

    async def get_guild_features(self, guild_id: int) -> Dict[str, Dict[str, Any]]:
        """Get all feature settings for a guild"""
        features = {}
        for feature in FeatureType:
            features[feature.value] = await self.get_feature_settings(guild_id, feature)
        return features

    async def bulk_update_features(self, guild_id: int, updates: Dict[str, Dict[str, Any]]) -> None:
        """Update multiple features at once"""
        for feature_name, settings in updates.items():
            if feature_name in [f.value for f in FeatureType]:
                await self.update_feature_settings(
                    guild_id,
                    FeatureType(feature_name),
                    settings.get('options', {})
                )

    # Add property for type checking
    @property
    def ready(self) -> bool:
        """Check if feature manager is ready"""
        return self.db is not None
