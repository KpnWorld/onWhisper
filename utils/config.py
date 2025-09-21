# utils/config.py

import asyncio
import logging
from typing import Any, Dict, Optional

from utils.db_manager import DBManager

logger = logging.getLogger("ConfigManager")

DEFAULT_CONFIG: Dict[str, Any] = {
    # 🔧 Core
    "prefix": "!",

    # 🎮 Leveling
    "leveling_enabled": True,
    "xp_rate": 10,
    "xp_cooldown": 60,
    "level_up_message": "🎉 {user} reached level {level}!",
    "level_channel": None,

    # 🛡 Moderation
    "moderation_enabled": True,
    "mod_log_channel": None,

    # 📊 Unified Logging System
    "unified_logging_enabled": True,
    
    # 🚪 Member Events
    "log_member_events": True,
    "log_member_channel": None,
    
    # 💬 Message Events  
    "log_message_events": True,
    "log_message_channel": None,
    
    # 🛡️ Moderation Events
    "log_moderation_events": True,
    "log_moderation_channel": None,
    
    # 🔊 Voice Events
    "log_voice_events": True,
    "log_voice_channel": None,
    
    # 📂 Channel Events
    "log_channel_events": True,
    "log_channel_channel": None,
    
    # 🎭 Role Events
    "log_role_events": True,
    "log_role_channel": None,
    
    # 🤖 Bot Events
    "log_bot_events": True,
    "log_bot_channel": None,
    
    # 🤫 Whisper Events
    "log_whisper_events": True,
    "log_whisper_channel": None,

    # 🎭 Roles
    "roles_enabled": True,
    "autorole_enabled": False,

    # 💌 Whisper system
    "whisper_enabled": True,
    "whisper_channel": None,
    "whisper_notification_enabled": True,
    "whisper_notification_channel": None,
    "whisper_notification_role": None,
}


class ConfigManager:
    def __init__(self, db: DBManager):
        self.db = db
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def load_guild(self, guild_id: int) -> None:
        # This method should only be called when already holding the lock
        settings = await self.db.get_guild_settings(guild_id)
        merged = {**DEFAULT_CONFIG, **settings}
        self._cache[guild_id] = merged
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in settings:
                await self.db.set_guild_setting(guild_id, key, str(default_value))
        logger.info(f"Loaded config for guild {guild_id} with {len(self._cache[guild_id])} keys")

    async def get(self, guild_id: int, key: str, default: Optional[Any] = None) -> Any:
        try:
            # Check cache first without lock
            if guild_id in self._cache:
                value = self._cache[guild_id].get(key, DEFAULT_CONFIG.get(key, default))
                logger.debug(f"Get config (cached): guild={guild_id}, key={key}, value={value}")
                return value
            
            # Only acquire lock if we need to load
            async with self._lock:
                # Double-check after acquiring lock
                if guild_id not in self._cache:
                    await self.load_guild(guild_id)
                value = self._cache[guild_id].get(key, DEFAULT_CONFIG.get(key, default))
                logger.debug(f"Get config (loaded): guild={guild_id}, key={key}, value={value}")
                return value
        except Exception as e:
            logger.error(f"Error in config.get: guild={guild_id}, key={key}, error={e}")
            return DEFAULT_CONFIG.get(key, default)

    async def set(self, guild_id: int, key: str, value: Any) -> None:
        async with self._lock:
            await self.db.set_guild_setting(guild_id, key, str(value))
            if guild_id not in self._cache:
                await self.load_guild(guild_id)
            self._cache[guild_id][key] = value
            logger.info(f"Set config: guild={guild_id}, key={key}, value={value}")

    async def clear_cache(self, guild_id: Optional[int] = None) -> None:
        async with self._lock:
            if guild_id:
                self._cache.pop(guild_id, None)
                logger.info(f"Cleared cache for guild {guild_id}")
            else:
                self._cache.clear()
                logger.info("Cleared all config cache")

    async def bootstrap_guilds(self, guild_ids: list[int]) -> None:
        tasks = [self.load_guild(gid) for gid in guild_ids]
        await asyncio.gather(*tasks)
        logger.info(f"Bootstrapped configs for {len(guild_ids)} guilds")
