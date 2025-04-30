# onWhisperBot

A feature-rich Discord bot built with py-cord that includes leveling, tickets, moderation, autoroles, and logging functionalities.

## Features

### 🎮 Leveling System
- Experience (XP) gain from chat activity 
- Customizable XP rates and cooldowns
- Level-up notifications with progress bar
- Server-wide leaderboards
- XP rewards based on message activity

### 🎫 Ticket System
- Thread-based support tickets
- Customizable ticket categories
- Staff role assignments 
- Automatic ticket closure
- Ticket logging and archival

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

### Configuration (`/config`)
- `/config xp rate <amount>` - Set XP per message (1-100)
- `/config xp cooldown <seconds>` - Set XP gain cooldown
- `/config xp toggle` - Toggle XP system

- `/config level add <level> <role>` - Set role reward for level
- `/config level remove <level>` - Remove level reward
- `/config level list` - List all level rewards

- `/config logs set <type> <channel>` - Set log channel (mod/member/message/server)
- `/config logs toggle` - Enable/disable logging

- `/config tickets category <channel>` - Set tickets category
- `/config tickets staff <role>` - Set support staff role

- `/config autorole set <role>` - Set auto-role for new members
- `/config autorole remove` - Disable auto-role

### Create Commands (`/create`)
- `/create ticket-panel <channel> <message>` - Generate a support ticket panel
- `/create reaction-role <channel> <emoji> <role> <message>` - Create a reaction role message
- `/create log-channel <type> <channel>` - Auto-setup a log channel
- `/create welcome-message <channel> <message>` - Preview/set welcome message
- `/create level-message <channel> <message>` - Preview/set level-up message

### Role Management (`/roles`)
- `/roles auto set <role>` - Enable auto-role
- `/roles auto remove` - Disable auto-role

- `/roles react bind <message_id> <emoji> <role>` - Bind emoji to role on message
- `/roles react unbind <message_id>` - Remove all reactions/roles from message
- `/roles react list` - Show all reaction role bindings

- `/roles bulk add <role> <users...>` - Assign role to multiple users
- `/roles bulk remove <role> <users...>` - Remove role from multiple users

### Moderation
- `/warn <user> <reason>` - Issue a warning
- `/warnings <user>` - View a user's warnings
- `/kick <user> [reason]` - Kick a member
- `/ban <user> [reason]` - Ban a member
- `/timeout <user> <duration> [reason]` - Temporarily mute a user
- `/purge <amount>` - Bulk delete messages (1-100)
- `/lockdown [channel] [duration]` - Lock a channel temporarily
- `/slowmode <seconds> [channel]` - Set slowmode in a channel
- `/snipe` - Retrieve last deleted message

### Information
- `/info help [command]` - Show help for a command
- `/info bot` - Show bot stats and ping
- `/info server` - Show server information
- `/info user [user]` - Show user information
- `/info role <role>` - Display role details
- `/info uptime` - Show bot uptime

### Debug (Owner Only)
- `/debug sync` - Sync application commands
- `/debug reload <cog>` - Reload a cog
- `/debug cleanup [limit]` - Clean up bot messages

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
    "tickets": {
        "open_tickets": [
            {
                "channel_id": number,
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
- `tickets_config`: Ticket category and support role settings
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
- Ticket activity

### Data Management
- Automatic cleanup of old logs and closed tickets (30 days)
- Optimization of database structure weekly
- Backup system for critical data (coming soon)

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License.
