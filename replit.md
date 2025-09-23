# onWhisper Discord Bot

## Overview

onWhisper is a comprehensive Discord bot built with discord.py and SQLite, providing a modular feature set for server management and community engagement. The bot implements a leveling system with XP tracking, role management (autoroles, reaction roles, color roles), comprehensive moderation tools with logging, a unified 8-category logging system, and a unique "whisper" system for anonymous communication through private threads with admin notifications. The architecture follows a cog-based pattern for modularity and includes robust configuration management with type-safe database operations.

## Recent Changes

**Update 149c - Unified Server-Side Logging System** - September 21, 2025
- Implemented comprehensive unified logging system with 8 distinct event categories
- Added LoggingManager class for centralized event tracking across all bot functions
- Created user-friendly /log-setup command for easy configuration of logging categories and channels
- Integrated logging throughout moderation, whisper, and bot events with visual feedback
- Fixed critical type-handling bug in configuration system for proper channel ID resolution
- Added 17 new configuration options for granular logging control per guild

**Whisper Update 149b - General Cogs Update 3 (Whisper via Modal Form)** - September 21, 2025
- Upgraded whisper system to use Discord modal forms for improved user experience
- Replaced basic command input with professional modal form interface
- Maintained all existing functionality including cooldowns, naming conventions, and permission checks
- Enhanced UI consistency with required reason field and automatic user ID capture
- Preserved complete whisper workflow: User create → Admin Review → Close or Delete → Remove thread from DB and Discord

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Framework
- **Discord.py**: Primary framework for Discord API interactions with slash commands and traditional commands
- **Cog-based Architecture**: Modular command organization separating features into distinct modules (leveling, moderation, roles, etc.)
- **Async/Await Pattern**: Full asynchronous operation using asyncio for concurrent database operations and Discord API calls

### Database Layer
- **SQLite with aiosqlite**: Lightweight, file-based database for persistence
- **Connection Pooling**: Single connection with row factory for dictionary-like access
- **Schema Design**: Normalized tables for guild settings, user leveling data, role configurations, and whisper threads
- **Atomic Operations**: Database operations protected by asyncio locks to prevent race conditions

### Configuration System
- **ConfigManager**: Centralized configuration management with guild-specific settings
- **Default Configuration**: Fallback values for all configurable options
- **Caching Layer**: In-memory cache for frequently accessed guild settings to reduce database queries
- **Dynamic Loading**: Guild configurations loaded on-demand and cached for performance

### Command Architecture
- **Hybrid Commands**: Support for both slash commands (app_commands) and traditional prefix commands
- **Permission Checking**: Role-based and permission-based command access control
- **Parameter Validation**: Type hints and Discord.py choices for command parameters
- **Error Handling**: Structured error responses with user-friendly messages

### Feature Modules
- **Leveling System**: XP gain on messages with cooldowns, level calculation, and reward roles with leaderboards
- **Role Management**: Automatic role assignment, reaction-based roles, and color roles per user
- **Moderation Tools**: Warning system, timeouts, kicks, bans, purge operations, and comprehensive channel management
- **Whisper System**: Private thread creation for anonymous communication with staff oversight, enhanced with Discord modal forms and admin notifications
- **Unified Logging System**: 8-category event tracking with channel-first configuration (member, message, moderation, voice, channel, role, bot, whisper events)
- **Configuration System**: Per-guild settings with type-safe conversions and caching
- **Help System**: Dynamic command documentation with categorized help commands

## External Dependencies

### Core Libraries
- **discord.py (>=2.0.0)**: Discord API wrapper and bot framework
- **python-dotenv (>=1.0.0)**: Environment variable management for tokens and configuration
- **aiosqlite (>=0.19.0)**: Asynchronous SQLite database adapter
- **psutil (>=5.9.5)**: System and process utilities for bot statistics
- **aiohttp (>=3.8.0)**: HTTP client for external API calls
- **aiofiles (>=0.8.0)**: Asynchronous file operations

### Runtime Environment
- **Python 3.13.0**: Runtime specified for consistent behavior
- **Replit Hosting**: Cloud hosting platform with persistent storage
- **SQLite Database**: File-based database stored in `/data/onwhisper.db`

### Discord Integration
- **Application Commands**: Slash command registration with Discord's API
- **Guild Intents**: Member and message content intents for full functionality
- **Permission System**: Integration with Discord's role and permission hierarchy
- **Webhook Support**: Potential for webhook-based logging and notifications

### Configuration Management
- **Environment Variables**: Sensitive data (tokens, IDs) stored in `.env` file
- **Guild-specific Settings**: Per-server configuration stored in database with 71 configurable options
- **Default Configuration**: Fallback values defined in configuration manager with type checking
- **Runtime Configuration**: Dynamic setting updates without bot restart

## Current Cog Structure

### Core Cogs (8 Active Modules)
- **`cogs/config.py`**: Configuration management with `/config` and simplified `/log-setup` commands
- **`cogs/debug.py`**: Development and debugging utilities for bot maintenance
- **`cogs/help.py`**: Dynamic help system with categorized command documentation
- **`cogs/info.py`**: Bot information, server stats, and utility commands
- **`cogs/leveling.py`**: XP tracking, leveling system, and role rewards management
- **`cogs/moderation.py`**: Comprehensive moderation tools (kick, ban, mute, warn, purge) with logging integration
- **`cogs/roles.py`**: Role management including autoroles, reaction roles, and color roles
- **`cogs/whisper.py`**: Anonymous whisper system with modal forms and admin notifications

### Utility Modules
- **`utils/db_manager.py`**: Database operations and schema management
- **`utils/config.py`**: Configuration manager with type-safe operations and caching
- **`utils/logging_manager.py`**: Unified logging system for 8 event categories

## Database Schema & Methods

### Database Tables (7 Tables)

#### `guild_settings`
**Purpose**: Store per-guild configuration settings
**Schema**: `(guild_id INTEGER, setting TEXT, value TEXT)` - PRIMARY KEY: (guild_id, setting)

#### `leveling_users`  
**Purpose**: Track user XP and levels per guild
**Schema**: `(guild_id INTEGER, user_id INTEGER, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0)` - PRIMARY KEY: (guild_id, user_id)

#### `leveling_roles`
**Purpose**: Define role rewards for specific levels
**Schema**: `(guild_id INTEGER, level INTEGER, role_id INTEGER)` - PRIMARY KEY: (guild_id, level)

#### `autoroles`
**Purpose**: Store automatic role assignments for new members
**Schema**: `(guild_id INTEGER PRIMARY KEY, role_id INTEGER)`

#### `reaction_roles`
**Purpose**: Map emoji reactions to role assignments
**Schema**: `(guild_id INTEGER, message_id INTEGER, emoji TEXT, role_id INTEGER)` - PRIMARY KEY: (guild_id, message_id, emoji)

#### `color_roles`
**Purpose**: Track custom color roles assigned to users
**Schema**: `(guild_id INTEGER, user_id INTEGER, role_id INTEGER)` - PRIMARY KEY: (guild_id, user_id)

#### `whispers`
**Purpose**: Track anonymous whisper threads and their status
**Schema**: `(guild_id INTEGER, user_id INTEGER, thread_id INTEGER, is_open INTEGER DEFAULT 1, created_at TIMESTAMP, closed_at TIMESTAMP, closed_by_staff INTEGER DEFAULT 0)` - PRIMARY KEY: (guild_id, user_id, thread_id)

#### `moderation_logs`
**Purpose**: Log all moderation actions with case tracking
**Schema**: `(guild_id INTEGER, case_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, reason TEXT, moderator_id INTEGER, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`

### Database Methods (by Category)

#### Generic Query Methods
- `execute(query, params)` → Execute query with parameters
- `fetchall(query, params)` → Fetch all rows as list
- `fetchrow(query, params)` → Fetch single row as aiosqlite.Row
- `fetchone(query, params)` → Fetch single row as dict

#### Guild Settings Management  
- `get_guild_settings(guild_id)` → Get all settings as dict
- `set_guild_setting(guild_id, setting, value)` → Set single setting
- `remove_guild_setting(guild_id, setting)` → Delete setting

#### Whisper System Methods
- `create_whisper(guild_id, user_id, thread_id)` → Create whisper, returns sequential number
- `get_whisper_by_number(guild_id, whisper_number)` → Get whisper by sequential number
- `get_active_whispers(guild_id)` → Get all open whispers
- `close_whisper(guild_id, thread_id, closed_by_staff=False)` → Close whisper thread
- `delete_whisper(guild_id, thread_id)` → Delete whisper from database
- `get_open_whispers(guild_id)` → Get open whispers with timestamps

#### Leveling System Methods
- `get_user_xp(guild_id, user_id)` → Get user's current XP
- `set_user_xp(guild_id, user_id, xp)` → Set user's XP directly
- `add_xp(guild_id, user_id, amount)` → Add XP to user
- `set_user_level(guild_id, user_id, level)` → Set user's level directly
- `get_leaderboard(guild_id, limit=10)` → Get top users by level/XP
- `add_level_reward(guild_id, level, role_id)` → Add role reward for level
- `remove_level_reward(guild_id, level)` → Remove level role reward
- `get_level_rewards(guild_id)` → Get all level→role mappings
- `set_level_role(guild_id, level, role_id)` → Set role for specific level
- `get_level_roles(guild_id)` → Get level roles as dict

#### Role Management Methods
- `set_autorole(guild_id, role_id)` → Set automatic role for new members
- `get_autorole(guild_id)` → Get current autorole ID
- `add_reaction_role(guild_id, message_id, emoji, role_id)` → Add reaction role mapping
- `remove_reaction_role(guild_id, message_id, emoji)` → Remove reaction role
- `get_reaction_roles(guild_id, message_id)` → Get emoji→role mappings for message
- `set_color_role(guild_id, user_id, role_id)` → Set user's color role
- `get_color_role(guild_id, user_id)` → Get user's current color role

#### Moderation Methods
- `log_moderation_action(guild_id, user_id, action, reason, moderator_id)` → Log moderation action
- `get_moderation_logs(guild_id, user_id)` → Get all moderation logs for user

#### Maintenance Methods
- `reset_guild_data(guild_id)` → Delete all data for a guild
- `vacuum()` → Optimize database storage

## Configuration Options (71 Total Settings)

### Core Settings
- `prefix` → Command prefix (default: "!")

### Leveling System (6 options)
- `leveling_enabled` → Enable/disable leveling system
- `xp_rate` → XP gained per message (default: 10)
- `xp_cooldown` → Cooldown between XP gains in seconds (default: 60)
- `level_up_message` → Level up announcement template
- `level_channel` → Channel for level up announcements

### Moderation (2 options)
- `moderation_enabled` → Enable/disable moderation features
- `mod_log_channel` → Channel for moderation logs

### Unified Logging System (17 options)
- `unified_logging_enabled` → Master logging toggle
- **Member Events**: `log_member_events` (enabled), `log_member_channel` (channel)
- **Message Events**: `log_message_events` (enabled), `log_message_channel` (channel)  
- **Moderation Events**: `log_moderation_events` (enabled), `log_moderation_channel` (channel)
- **Voice Events**: `log_voice_events` (enabled), `log_voice_channel` (channel)
- **Channel Events**: `log_channel_events` (enabled), `log_channel_channel` (channel)
- **Role Events**: `log_role_events` (enabled), `log_role_channel` (channel)
- **Bot Events**: `log_bot_events` (enabled), `log_bot_channel` (channel)
- **Whisper Events**: `log_whisper_events` (enabled), `log_whisper_channel` (channel)

### Role Management (2 options)
- `roles_enabled` → Enable/disable role features
- `autorole_enabled` → Enable/disable automatic role assignment

### Whisper System (5 options)
- `whisper_enabled` → Enable/disable whisper system
- `whisper_channel` → Channel where whisper threads are created
- `whisper_notification_enabled` → Enable admin notifications
- `whisper_notification_channel` → Channel for admin notifications  
- `whisper_notification_role` → Role to ping for whisper notifications

## Command Structure

### Configuration Commands (2 commands)
- `/config view-all|view|set` → Manage bot configuration
- `/log-setup view-config|configure` → Simple logging setup (channel-first workflow)

### Moderation Commands (5 commands)  
- `/kick`, `/ban`, `/mute`, `/warn`, `/purge` → Core moderation tools

### Leveling Commands (4 commands)
- `/level`, `/leaderboard`, `/setlevel`, `/add-level-role`, `/remove-level-role`, `/list-level-roles`

### Whisper Commands (1 command)
- `/whisper` → Create anonymous whisper thread (modal form interface)

### Role Commands (Multiple)
- Autorole, reaction role, and color role management commands

### Info & Help Commands
- `/help`, `/info`, `/ping` → Bot information and help system

Total: **27 synced application commands** across all categories