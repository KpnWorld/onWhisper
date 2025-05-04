# onWhisperBot

A feature-rich Discord bot built with py-cord that includes leveling, whispers, moderation, autoroles, and logging functionalities.

## Features

### 🎮 Leveling System
- Experience (XP) gain from chat activity 
- Customizable XP rates and cooldowns
- Level-up notifications with progress bar
- Server-wide leaderboards
- XP rewards based on message activity

### 💬 Whisper System
- Thread-based private communication
- Staff role management
- Auto-close for inactive threads
- Configurable retention periods
- Anonymous reporting option
- Comprehensive logging

### 👮 Moderation
- Core moderation commands (kick, ban, timeout)
- Warning system with auto-expire
- Message bulk deletion
- Channel lockdown capabilities
- Slowmode management
- Message snipe command
- Detailed mod logs

### 🎭 Role Management
- Automatic role assignment for new members
- Reaction roles with selection menu management
- Role hierarchy respect
- Interactive role unbinding interface
- Bulk role assignments
- Error handling for permissions
- Role logging and tracking

### 📝 Logging
- Comprehensive event logging
- Member join/leave tracking
- Message edit/delete logging
- Role & channel update logs
- Mod action logging
- Clean embed formatting
- Customizable log channels

## Commands

### Moderation
- `/warn <user> <reason>` - Issue a warning
- `/warnings <user>` - View a user's warnings
- `/kick <user> [reason]` - Kick a member
- `/ban <user> [reason] [delete_days]` - Ban a member
- `/timeout <user> <duration> [reason]` - Temporarily mute a user
- `/lockdown [channel] [duration] [reason]` - Lock a channel temporarily
- `/unlock [channel]` - Remove a channel lockdown
- `/slowmode <seconds> [channel]` - Set slowmode in a channel
- `/clear <amount> [user]` - Bulk delete messages (1-100)
- `/snipe <type>` - Show recently deleted/edited messages

### Role Management
- `/roles auto_set <role>` - Enable auto-role for new members
- `/roles auto_disable` - Disable automatic role
- `/roles color set <role>` - Set your color role
- `/roles color clear` - Remove your color role
- `/roles bulk_add <role> <users>` - Add role to multiple users
- `/roles bulk_remove <role> <users>` - Remove role from multiple users
- `/roles react_bind <message_id> <emoji> <role>` - Create reaction role
- `/roles react_unbind <message_id>` - Remove reaction roles
- `/roles react_list` - List reaction roles
- `/config color add <role>` - Add a role to allowed color roles
- `/config color remove <role>` - Remove a role from allowed color roles
- `/config color list` - Show all configured color roles

### Leveling System
- `/config_xp rate <amount>` - Set XP per message (1-100)
- `/config_xp cooldown <seconds>` - Set XP gain cooldown
- `/config_xp toggle` - Toggle XP system
- `/config_level add <level> <role>` - Set role reward for level
- `/config_level remove <level>` - Remove level reward
- `/config_level list` - List all level rewards

### Whisper System
- `/whisper <message>` - Start a private thread with staff
- `/whisper_close` - Close your whisper thread
- `/config_whisper channel [channel]` - Set whisper channel
- `/config_whisper staff <role>` - Set staff role
- `/config_whisper timeout <minutes>` - Set auto-close timeout
- `/config_whisper retention <days>` - Set thread retention period
- `/config_whisper toggle` - Toggle whisper system

### Logging
- `/config_logs enable <type> <channel>` - Enable logging for specified type
- `/config_logs disable <type>` - Disable logging for specified type

### Information
- `/info help [command]` - Show command help
- `/info bot` - Show bot stats and info
- `/info server` - Show server information
- `/info user [user]` - Show user information
- `/info role <role>` - Show role information
- `/info uptime` - Show bot uptime

### Debug (Owner Only)
- `/debug_db` - Get database diagnostics
- `/debug_system` - Get system diagnostics 
- `/maintenance` - Toggle maintenance mode
- `!sync [guild|global]` - Sync slash commands
- `!load <cog>` - Load a cog
- `!unload <cog>` - Unload a cog
- `!reload <cog>` - Reload a cog

## Setup & Configuration

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Configure `.env`:
```env
DISCORD_TOKEN=your_token_here
BOT_OWNER=your_id_here
```

3. Run the bot:
```bash
python bot.py
```

## Database Structure

The bot uses Replit Database with nested JSON structures. Each guild has its own data namespace.

### Guild Data Structure (`{botname}:guild:{guild_id}`)
```json
{
    "xp_settings": {
        "rate": 15,
        "cooldown": 60,
        "enabled": true
    },
    "xp_users": {
        "user_id": {
            "level": number,
            "xp": number,
            "last_xp": "ISO datetime"
        }
    },
    "level_roles": {
        "level": "role_id"
    },
    "whispers": {
        "active_threads": [
            {
                "thread_id": number,
                "user_id": number,
                "created_at": "ISO datetime",
                "closed_at": "ISO datetime or null"
            }
        ],
        "logs": []
    },
    "mod_actions": [
        {
            "action": "string",
            "user_id": number,
            "details": "string",
            "timestamp": "ISO datetime",
            "expires": "ISO datetime or null"  // New field for temporary actions
        }
    ],
    // Keep only the last 100 actions per guild
    // Auto-cleanup of expired actions
    "reaction_roles": {
        "message_id": {
            "emoji": "role_id"
        }
    },
    "logs_config": {
        "mod_channel": null,
        "join_channel": null,
        "enabled": true
    }
}
```

### Configuration Collections
- `logging_config`: Logging channel settings and filters
- `whisper_config`: Whisper system settings and staff roles
- `moderation_config`: Moderation roles and warning settings
- `xp_config`: XP gain rate and cooldown settings
- `level_roles`: Level-based role reward mappings

### Event Logs
Event logs are stored with automatic cleanup after 30 days:
- Message edits/deletions
- Member joins/leaves
- Role changes
- Channel updates
- Moderation actions
- Whisper activity

### Data Management
- Automatic cleanup of old logs and closed whispers (30 days)
- Optimization of database structure weekly
- Backup system for critical data (coming soon)

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License.
