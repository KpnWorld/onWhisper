# onWhisper Discord Bot

A feature-rich Discord bot with leveling system, auto-role management, and server information commands.

## Features

- **Leveling System**: Track user activity and assign roles based on levels
- **Auto-Role**: Automatically assign roles to new members and bots
- **Server Information**: Comprehensive server and user information commands

## Requirements

- Python 3.13.0 or higher
- Discord.py with voice support
- SQLite3 for database management

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create environment variables:
   - For local development: Create a `.env` file with:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```
   - For Repl.it: Add `DISCORD_TOKEN` to the Secrets tab in your repl

3. Required Bot Permissions:
- Manage Roles
- Send Messages
- Embed Links
- Read Message History

## Deployment on Repl.it

1. Create a new Python repl
2. Upload all files or connect your GitHub repository
3. Add your bot token:
   - Go to "Tools" -> "Secrets"
   - Add a new secret with key `DISCORD_TOKEN` and your bot token as value
4. The bot will automatically start when you run the repl
5. Enable "Always On" in your repl to keep the bot running 24/7

## Database Management

The bot uses SQLite with automatic backups. The database will be stored in your repl's persistent storage:
- Database files are stored in the `db/` directory
- Backups are created automatically
- Data persists between restarts
