# utils/config.py

import asyncio
import logging
from typing import Any, Dict, Optional

from utils.db_manager import DBManager

logger = logging.getLogger("ConfigManager")

DEFAULT_CONFIG: Dict[str, Any] = {
    "xp_rate": 10,
    "xp_cooldown": 60,
    "level_up_message": "🎉 {user} reached level {level}!",
    "level_channel": None,
    "mod_log_channel": None,
    "join_log_channel": None,
    "leave_log_channel": None,
    "prefix": "!",
    "autorole_enabled": False,
    "whisper_enabled": True,
    "whisper_channel": None,
}


class ConfigManager:
    def __init__(self, db: DBManager):
        self.db = db
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def load_guild(self, guild_id: int) -> None:
        async with self._lock:
            settings = await self.db.get_guild_settings(guild_id)
            merged = {**DEFAULT_CONFIG, **settings}
            self._cache[guild_id] = merged
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in settings:
                    await self.db.set_guild_setting(guild_id, key, str(default_value))
            logger.info(f"Loaded config for guild {guild_id} with {len(self._cache[guild_id])} keys")

    async def get(self, guild_id: int, key: str, default: Optional[Any] = None) -> Any:
        async with self._lock:
            if guild_id not in self._cache:
                await self.load_guild(guild_id)
            value = self._cache[guild_id].get(key, DEFAULT_CONFIG.get(key, default))
            logger.debug(f"Get config: guild={guild_id}, key={key}, value={value}")
            return value

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
