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
- `/config xp rate <amount>` - Set XP per message
- `/config xp cooldown <seconds>` - Set XP gain cooldown
- `/config xp toggle` - Toggle XP system
- `/config tickets category <category>` - Set ticket category
- `/config tickets support <role>` - Set support team role
- `/config logging channel <channel>` - Set log channel
- `/config moderation muterole <role>` - Set muted role
- `/config moderation modrole <role>` - Set mod role
- `/config moderation warnexpire <days>` - Set warning expiration
- `/config autorole set <role>` - Set auto-role
- `/config autorole toggle` - Toggle auto-role

### Moderation
- `/kick <member> [reason]` - Kick a member
- `/ban <member> [reason] [delete_days]` - Ban a member
- `/timeout <member> <duration> <unit> [reason]` - Timeout member
- `/warn <member> <reason>` - Warn a member
- `/clear <amount> [user]` - Clear messages
- `/lock [channel] [reason]` - Lock channel
- `/unlock [channel]` - Unlock channel
- `/slowmode <seconds> [channel]` - Set slowmode
- `/snipe [channel]` - Show deleted message

### Leveling
- `/level [user]` - Show level info
- `/leaderboard` - Show XP leaderboard

### Tickets
- `/ticket <reason>` - Create ticket
- Close button in ticket channels

### Roles
- `/setautorole <role>` - Set auto-role
- `/removeautorole` - Remove auto-role
- `/bindreactionrole <message_id> <emoji> <role>` - Create reaction role
- `/unbindreactionrole <message_id>` - Remove reaction role (shows selection menu)

### Information
- `/help [command]` - Show help
- `/botinfo` - Show bot stats
- `/serverinfo` - Show server info
- `/userinfo [user]` - Show user info
- `/uptime` - Show bot uptime

### Debug (Owner Only)
- `!dbcheck [key]` - Check database
- `!dblookup <collection> <key> <field>` - Look up data
- `!dbstats` - Show database stats
- `!guilddata [collection]` - Show guild data
- `!dblist [filter]` - List database entries

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

The bot uses Replit Database with the following collections:
- `logging_config` - Logging settings
- `auto_roles` - Autorole settings
- `reaction_roles` - Reaction role bindings
- `tickets` - Ticket data
- `levels` - XP/level data
- `moderation_config` - Moderation settings
- `logs` - Event & mod logs

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License.
