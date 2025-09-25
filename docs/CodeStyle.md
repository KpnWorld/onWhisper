# 🎨 onWhisper Code Style & Structure Guide

This document outlines the coding standards, patterns, and conventions used throughout the onWhisper Discord bot codebase. Following these guidelines ensures consistency, maintainability, and readability across all modules.

---

## 📁 File Organization

### **Directory Structure**
```
onWhisper/
├── bot.py                   # Main bot entry point
├── cogs/                    # Feature modules (8 cogs)
├── utils/                   # Core utility modules  
├── data/                    # Persistent storage
└── docs/                    # Documentation
```

### **File Naming Conventions**
- **Snake_case** for all Python files: `leveling.py`, `db_manager.py`
- **Descriptive names** reflecting functionality: `moderation.py`, `config.py`
- **Utility prefix** for shared modules: `utils/db_manager.py`

---

## 📥 Import Organization

### **Import Order (PEP 8 Compliant)**
```python
# 1. Standard library imports
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union

# 2. Third-party imports
import discord
from discord.ext import commands, tasks
from discord import app_commands

# 3. Local application imports  
from utils.db_manager import DBManager
from utils.config import ConfigManager
from utils.logging_manager import LoggingManager
```

### **Import Style Guidelines**
- **Explicit imports** over wildcard: `from typing import Optional` not `from typing import *`
- **Grouped by source**: Standard → Third-party → Local
- **One line per import** for multiple items from same module
- **Type imports** from typing module for all type hints

---

## 🏗️ Class Structure

### **Cog Class Pattern**
```python
class ExampleCog(commands.Cog):
    """📝 Brief description of cog functionality"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DBManager = bot.db_manager
        self.config: ConfigManager = bot.config_manager
        # Add logging manager if needed
        # self.logging: LoggingManager = bot.logging_manager
    
    # Event listeners first
    @commands.Cog.listener()
    async def on_event_name(self, ...):
        """Handle specific bot events"""
        pass
    
    # Public commands second  
    @app_commands.command(name="example", description="Command description")
    async def example_command(self, interaction: discord.Interaction):
        """Public slash command implementation"""
        pass
    
    # Private helper methods last (prefixed with _)
    async def _helper_method(self, param: type) -> type:
        """Private helper method for internal use"""
        pass
```

### **Utility Class Pattern**
```python
class UtilityManager:
    """Utility manager for specific functionality"""
    
    def __init__(self, dependency1: Type1, dependency2: Type2):
        self.dependency1 = dependency1
        self.dependency2 = dependency2
        self._lock = asyncio.Lock()  # For thread safety
    
    async def public_method(self, param: type) -> type:
        """Public async method with type hints"""
        async with self._lock:
            # Thread-safe operations
            pass
    
    def _private_method(self, param: type) -> type:
        """Private helper method"""
        pass
```

---

## 📝 Function & Method Standards

### **Method Signatures**
```python
# Complete type annotations for all parameters and return values
async def example_method(self, 
                        guild_id: int, 
                        user: discord.Member,
                        optional_param: Optional[str] = None) -> bool:
    """
    Brief description of method functionality.
    
    Args:
        guild_id: The Discord guild ID
        user: Discord member object
        optional_param: Optional parameter description
    
    Returns:
        bool: Success/failure status
    
    Raises:
        ValueError: When invalid parameters provided
    """
    pass
```

### **Command Method Pattern**
```python
@app_commands.command(name="command-name", description="User-friendly description")
@app_commands.describe(
    param1="Description of first parameter",
    param2="Description of second parameter"
)
async def command_method(self, 
                        interaction: discord.Interaction,
                        param1: str,
                        param2: Optional[int] = None):
    """Command implementation with validation"""
    # 1. Guild/permission validation
    if not interaction.guild:
        await interaction.response.send_message("This command requires a server.", ephemeral=True)
        return
    
    # 2. Permission checks
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
        return
    
    # 3. Input validation
    if param2 and param2 < 1:
        await interaction.response.send_message("Parameter must be positive.", ephemeral=True)
        return
    
    # 4. Main logic with error handling
    try:
        # Implementation here
        result = await self.db.some_operation(interaction.guild.id, param1)
        
        embed = discord.Embed(
            title="Success",
            description=f"Operation completed: {result}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Command error: {e}", exc_info=True)
        await interaction.response.send_message("An error occurred.", ephemeral=True)
```

---

## 🔧 Configuration Integration

### **ConfigManager Usage Pattern**
```python
# Getting configuration values with defaults
setting_value = await self.config.get(guild_id, "setting_key", default_value)

# Setting configuration values  
await self.config.set(guild_id, "setting_key", new_value)

# Type-safe configuration access
enabled: bool = await self.config.get(guild_id, "feature_enabled", True)
channel_id: Optional[int] = await self.config.get(guild_id, "target_channel")
```

### **Configuration Constants**
```python
# Use descriptive configuration keys
DEFAULT_CONFIG: Dict[str, Any] = {
    # Group by feature with emojis for clarity
    # 🎮 Leveling
    "leveling_enabled": True,
    "xp_rate": 10,
    "level_up_destination": "same",  # Options documented in comments
    
    # 🛡️ Moderation  
    "moderation_enabled": True,
    "mod_log_channel": None,
}
```

---

## 🗄️ Database Integration

### **Database Access Pattern**
```python
# Use typed database methods with error handling
try:
    result = await self.db.get_user_data(guild_id, user_id)
    if result:
        # Process result
        pass
    else:
        # Handle no data case
        pass
except Exception as e:
    logger.error(f"Database error: {e}", exc_info=True)
    # Graceful fallback
```

### **Database Method Structure**
```python
async def database_method(self, 
                         guild_id: int, 
                         param: str) -> Optional[Dict[str, Any]]:
    """Database operation with proper locking"""
    async with self._lock:
        try:
            result = await self.fetchone(
                "SELECT * FROM table WHERE guild_id = ? AND param = ?",
                (guild_id, param)
            )
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Database operation failed: {e}", exc_info=True)
            return None
```

---

## 📊 Logging Standards

### **Logger Setup**
```python
# Module-level logger with hierarchical naming
logger = logging.getLogger("onWhisper.ModuleName")
```

### **Logging Patterns**
```python
# Use structured logging with context
logger.info(f"User {user.name} performed action in guild {guild.id}")
logger.warning(f"Configuration missing for guild {guild.id}, using default")
logger.error(f"Failed operation for user {user_id}: {error}", exc_info=True)

# Include relevant IDs for debugging
logger.debug(f"Processing command: guild={guild.id}, user={user.id}, command={command}")
```

### **LoggingManager Integration**
```python
# Use unified logging for bot events
await self.bot.logging_manager.log_event(
    guild=interaction.guild,
    category="moderation",
    title="User Kicked", 
    description=f"{member.mention} was kicked",
    fields={"Reason": reason, "Moderator": interaction.user.mention}
)
```

---

## ⚠️ Error Handling

### **Standard Error Handling Pattern**
```python
async def operation_with_error_handling(self, param: str) -> bool:
    """Operation with comprehensive error handling"""
    try:
        # Main operation
        result = await self.some_operation(param)
        return True
        
    except discord.Forbidden:
        logger.warning(f"Insufficient permissions for operation with {param}")
        return False
        
    except discord.NotFound:
        logger.warning(f"Resource not found for operation with {param}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error in operation: {e}", exc_info=True)
        return False
```

### **User-Facing Error Messages**
```python
# Provide helpful, non-technical error messages
try:
    # Operation
    pass
except discord.Forbidden:
    await interaction.response.send_message(
        "I don't have permission to perform this action.", 
        ephemeral=True
    )
except ValueError as e:
    await interaction.response.send_message(
        f"Invalid input: {str(e)}", 
        ephemeral=True
    )
```

---

## 🎭 Discord Integration Patterns

### **Embed Standards**
```python
def create_standard_embed(self, title: str, description: str, 
                         color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    """Create standardized embed with consistent formatting"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"onWhisper Bot", icon_url=self.bot.user.avatar.url if self.bot.user else None)
    return embed
```

### **Permission Checking**
```python
async def _check_permissions(self, interaction: discord.Interaction, 
                           required_perm: str) -> bool:
    """Centralized permission checking"""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    
    # Check specific permission
    if hasattr(interaction.user.guild_permissions, required_perm):
        return getattr(interaction.user.guild_permissions, required_perm)
    
    # Fallback to administrator check
    return interaction.user.guild_permissions.administrator
```

### **Channel Validation**
```python
async def _get_text_channel(self, guild: discord.Guild, 
                          channel_id: Optional[int]) -> Optional[discord.TextChannel]:
    """Safely get and validate text channel"""
    if not channel_id:
        return None
    
    try:
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
    except (ValueError, TypeError):
        pass
    
    return None
```

---

## 🧪 Testing & Validation

### **Input Validation Pattern**
```python
def validate_input(self, value: Any, min_val: int = None, max_val: int = None) -> bool:
    """Validate user input with clear constraints"""
    try:
        int_value = int(value)
        if min_val is not None and int_value < min_val:
            return False
        if max_val is not None and int_value > max_val:
            return False
        return True
    except (ValueError, TypeError):
        return False
```

### **Defensive Programming**
```python
# Always validate external data
if not guild or not user:
    logger.warning("Missing required guild or user data")
    return

# Use type checking for critical operations
if not isinstance(channel, discord.TextChannel):
    logger.error(f"Expected TextChannel, got {type(channel)}")
    return

# Provide fallbacks for optional features
try:
    optional_feature()
except Exception:
    logger.debug("Optional feature unavailable, continuing without it")
```

---

## 📋 Documentation Standards

### **Module Docstrings**
```python
"""
Leveling system cog for XP tracking and role rewards.

This module handles:
- XP gain from messages with configurable rates and cooldowns
- Level calculation using square root progression
- Flexible level-up messaging (same channel, DM, or dedicated channel)
- Role rewards for reaching specific levels
- Leaderboard functionality with pagination

Configuration options:
- leveling_enabled: Master toggle for leveling system
- xp_rate: XP gained per message (default: 10)
- level_up_destination: Where to send level-up messages (same/dm/channel)
"""
```

### **Inline Comments**
```python
# Calculate new level using square root progression
new_level = int(xp ** 0.5 // 1)

# Send level-up message based on configured destination
destination = await self.config.get(guild.id, "level_up_destination", "same")

# Fallback to same channel if DM or configured channel fails
try:
    if destination == "dm":
        await user.send(message)
    elif destination == "channel":
        await level_channel.send(message)
    else:  # destination == "same"
        await current_channel.send(message)
except discord.Forbidden:
    # Permission denied, use fallback
    await current_channel.send(message)
```

---

## 🚀 Performance Considerations

### **Async/Await Best Practices**
```python
# Use async context managers for resources
async with self._lock:
    # Thread-safe operations
    pass

# Batch database operations when possible
async def batch_update(self, operations: List[Tuple]):
    """Batch multiple database operations for efficiency"""
    async with self._lock:
        for operation in operations:
            await self.execute(*operation)
```

### **Caching Patterns**
```python
# Cache frequently accessed data
self._cache: Dict[int, Dict[str, Any]] = {}

async def get_cached_data(self, guild_id: int) -> Dict[str, Any]:
    """Get data with caching for performance"""
    if guild_id not in self._cache:
        data = await self.db.get_guild_data(guild_id)
        self._cache[guild_id] = data
    return self._cache[guild_id]
```

---

## 📌 Code Review Checklist

Before submitting code, ensure:

- ✅ **Type hints** on all function parameters and returns
- ✅ **Error handling** with appropriate try/catch blocks
- ✅ **Logging** for important operations and errors
- ✅ **Permission checks** for administrative commands
- ✅ **Input validation** for user-provided data
- ✅ **Docstrings** for public methods and classes
- ✅ **Consistent naming** following snake_case conventions
- ✅ **Import organization** following PEP 8 standards
- ✅ **Configuration integration** for customizable features
- ✅ **Database operations** using proper locking and error handling

---

## 🎯 Common Patterns Summary

### **Command Structure**
1. **Validation** (guild, permissions, input)
2. **Configuration** retrieval with defaults
3. **Database** operations with error handling
4. **Discord** API interactions with fallbacks
5. **Logging** for operations and errors
6. **User feedback** with informative embeds

### **Cog Organization**
1. **Event listeners** (`@commands.Cog.listener()`)
2. **Public commands** (`@app_commands.command()`)
3. **Helper methods** (`async def _helper_method()`)
4. **Setup method** (`async def setup(bot)`)

This code style guide ensures the onWhisper bot maintains high code quality, consistency, and maintainability across all modules and future development.