# onWhisperBot  
*A feature-rich Discord bot built with `discord.py` and SQLite.*

## 📌 Overview  
onWhisper is a multi-purpose Discord bot that brings together **leveling**, **moderation**, **role management**, and a **private whisper system** — all backed by a powerful SQLite database for reliability and speed.

## ✨ Features  
- **Leveling System** — Earn XP, level up, and unlock role rewards.  
- **Moderation Tools** — Kick, ban, mute, and log server events.  
- **Role Management** — Autoroles, reaction roles, and color roles.  
- **Whisper System** — Send private anonymous messages via commands.  
- **Customizable Server Settings** — Prefix, XP rates, log channels, and more.  
- **Slash Commands** — Fully integrated with Discord’s modern command system.
---

## ⚙️ Setup Instructions  
### 1. Clone the Repository:  
```bash
git clone https://github.com/yourusername/onWhisper.git
cd onWhisper
```

### 2. Install Dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables:
```env
DISCORD_TOKEN=your_token_here
BOT_OWNER=your_id_here
```

### 4. Run the bot:
```bash
python bot.py
```

## 💬 Commands Overview

| Category | Commands & Description |
|---|---|
| **Info** | `/bot` — Bot stats and meta info |
| | `/user [member]` — View user profile and XP/level |
| | `/guild` — Server information |
| | `/role [role], /channel [channel]` — Details |
| **Leveling** | `/level [user]` — Show XP and levels |
| | `/leaderboard [page]` — Server XP leaderboard |
| | `/levelrole` — Manage level-based role rewards |
| **Moderation** | `/warn, /mute, /kick, /ban, /unban, /purge` |
| | `/lock, /unlock` — Channel moderation |
| **Roles** | `/autorole` — Set or disable auto role assignment |
| | `/reactionrole` — Add/remove reaction roles |
| | `/color` — Set or clear color role |
| **Whisper System** | `/whisper open/close/list` — Manage private whisper threads |
| **Configuration** | `/config view/set` — Manage guild settings |
| **Debug** | `/debug key/resetdb/version` — Admin debugging tools |
---

## 🗄 Database Structure (SQLite)

The bot uses `aiosqlite` with the following key tables:

| Table           | Purpose                                     |
| :-------------- | :------------------------------------------ |
| `guild_settings`  | Stores configuration per guild              |
| `leveling_users`  | Tracks XP, levels, and message counts per user |
| `leveling_roles`  | Level-based role rewards                    |
| `autoroles`       | Roles auto-assigned to new members          |
| `reaction_roles`  | Emoji-to-role mappings for reaction roles   |
| `color_roles`     | Custom user color roles                     |
| `whispers`        | Active and closed whisper threads           |
---
## 📚 Developer Notes

*   All database access is done asynchronously through the `DBManager` class (`utils/db_manager.py`).
*   Commands are modularized in cogs within the `cogs/` directory.
*   The bot is designed for multi-guild scalability and performance.

## 📝 License

This project is licensed under the MIT License — free to use, modify, and distribute.
