# onWhisperBot

A feature-rich Discord bot built with discord.py that includes leveling, tickets, moderation, autoroles, and logging functionalities.

## Features

### 🎮 Leveling System
- Experience (XP) gain from chat activity
- Customizable XP rates and cooldowns
- Level-up notifications
- Server leaderboards

### 🎫 Ticket System
- Thread-based support tickets
- Easy ticket creation and management
- Staff-only commands for ticket handling
- Ticket archiving

### 👮 Moderation
- Basic moderation commands (kick, ban, timeout)
- Message purging
- Warning system
- Role management

### 🎭 Role Management
- Automatic role assignment for new members
- Reaction roles
- Role hierarchy respect
- Custom role commands

### 📝 Logging
- Comprehensive server logging
- Customizable log channels
- Tracks member events, messages, and moderation actions
- Detailed audit logs

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Configure the .env file:
```env
DISCORD_TOKEN=your_token_here
BOT-OWNER=your_id_here
```
4. Run the bot:
```bash
python bot.py
```

## Project Structure

```
onWhisperBot/
│
├── bot.py                        # Entry point for the bot
├── .env                         # Contains the DISCORD_TOKEN
├── cogs/                        # All cog modules
│   ├── info.py                  # Bot info, server info, user info
│   ├── leveling.py             # Leveling system & role assignments
│   ├── tickets.py              # Ticket system using threads
│   ├── moderation.py           # Moderation commands
│   ├── autorole.py             # Autorole and reaction roles
│   └── logging.py              # Logs events to logging channel
│
├── utils/                       # Utility modules
│   └── db_manager.py           # Database handling (async-based)
│
└── data/                        # Data storage
    └── database.sqlite3         # SQLite database
```

## Commands

### Leveling
- `/level [user]` - Check your or another user's level
- `/set-xp-rate <amount>` - Set XP rate (Admin only)
- `/set-xp-cooldown <seconds>` - Set XP cooldown (Admin only)

### Tickets
- `/ticket <reason>` - Create a support ticket
- `/close-ticket` - Close current ticket
- `/add-to-ticket <user>` - Add user to ticket (Staff only)
- `/remove-from-ticket <user>` - Remove user from ticket (Staff only)

### Moderation
- `/kick <user> [reason]` - Kick a user
- `/ban <user> [reason] [delete_days]` - Ban a user
- `/timeout <user> <duration> <unit> [reason]` - Timeout a user
- `/clear <amount> [user]` - Clear messages
- `/warn <user> <reason>` - Warn a user

### Role Management
- `/setautorole <role>` - Set automatic role for new members
- `/removeautorole` - Disable automatic role
- `/bind_reaction_role <message_id> <emoji> <role>` - Create reaction role

### Logging
- `/setlogchannel <channel>` - Set logging channel

## Database Schema

The bot uses SQLite with the following main tables:
- `leveling` - User XP and levels
- `tickets` - Support ticket tracking
- `auto_role` - Autorole configuration
- `reaction_roles` - Reaction role bindings
- `logs` - Server event logs
- `logging_config` - Logging channel settings

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License.
