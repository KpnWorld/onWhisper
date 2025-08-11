# onWhisperBot

A feature-rich Discord bot built with discord.py that includes leveling, whispers, moderation, autoroles, and logging functionalities.

## Features

### 🎮 Leveling System
- Message-based XP gain with configurable rates
- Customizable cooldown periods
- DM/Channel level-up notifications
- Interactive leaderboard with pagination
- Role rewards based on levels
- Progress tracking with visual bars
- Level/XP management commands
- Rank display and statistics

### Database Schema
```sql
-- XP/Leveling Tables
CREATE TABLE xp (
    guild_id INTEGER,
    user_id INTEGER,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    last_message_ts TIMESTAMP,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE level_config (
    guild_id INTEGER PRIMARY KEY,
    cooldown INTEGER DEFAULT 60,
    min_xp INTEGER DEFAULT 10,
    max_xp INTEGER DEFAULT 20
);

CREATE TABLE level_roles (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, level)
);
```

## Commands

### Leveling Commands
- `/level [user]` - View level stats and progress
  - Shows current level, XP, progress bar
  - Displays rank on server leaderboard
  - Shows progress to next level
  
- `/leaderboard [page]` - View server XP leaderboard
  - Paginated display of top users
  - Interactive navigation buttons
  - Shows XP and level for each user

- `/levelconfig` - Configure leveling system
  - `cooldown <seconds>` - Set XP gain cooldown
  - `xprange <min> <max>` - Set XP per message range
  - `togglenotifications` - Toggle level-up DMs
  - `addrole <level> <role>` - Add level role reward
  - `removerole <level>` - Remove level role reward
  - `roles` - List all level role rewards
  - `reset <user>` - Reset user's XP and level
  - `setlevel <user> <level>` - Set user's level

### Database Methods
```python
# XP Management
get_user_xp(guild_id, user_id) -> Optional[Dict]
update_user_xp(guild_id, user_id, xp, level)
add_xp(guild_id, user_id, xp_amount)
set_level(guild_id, user_id, level)
reset_user_xp(guild_id, user_id)

# Leaderboard
get_leaderboard(guild_id, limit) -> List[Dict]
get_leaderboard_page(guild_id, limit, offset) -> List[Dict]

# Level Configuration
get_level_config(guild_id) -> Optional[Dict]
set_level_config(guild_id, cooldown, min_xp, max_xp)

# Role Rewards
set_level_role(guild_id, level, role_id)
delete_level_role(guild_id, level)
get_level_roles(guild_id) -> List[Dict]
get_level_roles_for_level(guild_id, level) -> List[int]

# Cooldown & Notifications
get_user_cooldown(guild_id, user_id) -> Optional[float]
update_user_level(guild_id, user_id, level)
get_level_notification_setting(guild_id) -> bool
```

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
