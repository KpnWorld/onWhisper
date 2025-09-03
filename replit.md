# onWhisper Discord Bot

## Overview

onWhisper is a comprehensive Discord bot built with discord.py and SQLite, providing a modular feature set for server management and community engagement. The bot implements a leveling system with XP tracking, role management (autoroles, reaction roles), moderation tools, logging capabilities, and a unique "whisper" system for anonymous communication through private threads. The architecture follows a cog-based pattern for modularity and includes robust configuration management per guild.

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
- **Leveling System**: XP gain on messages with cooldowns, level calculation, and reward roles
- **Role Management**: Automatic role assignment, reaction-based roles, and color roles
- **Moderation Tools**: Warning system, timeouts, kicks, bans, and channel management
- **Whisper System**: Private thread creation for anonymous communication with staff oversight
- **Logging System**: Event tracking for joins, leaves, message edits, and moderation actions

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
- **Guild-specific Settings**: Per-server configuration stored in database
- **Default Configuration**: Fallback values defined in configuration manager
- **Runtime Configuration**: Dynamic setting updates without bot restart