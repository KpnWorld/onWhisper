🗂️ onWhisper File Structure
```
onWhisper/
│
├── bot.py                  # 🚀 Main bot startup file (onWhisperBot)
├── .env                    # 🔐 Token & environment configs
├── requirements.txt        # 📦 Python dependencies
│
├── cogs/                   # ⚙️ All bot modules (cogs)
│   ├── info.py             # /bot, /user, /guild, /role, /channel info
│   ├── leveling.py         # XP system, level roles, leaderboard
│   ├── moderation.py       # Warn, mute, kick, ban, lockdown, purge (hybrid)
│   ├── roles.py            # Auto roles, reaction roles, color roles
│   ├── logging.py          # Server event logging (joins, edits, deletes)
│   └── whisper.py          # 🤫 Whisper System (thread-based private support)
│
├── utils/                  # 🧠 Core logic managers
│   ├── db_manager.py       # Handles all DB operations via aiosqlite
│   └── config.py           # ConfigManager for dynamic guild settings
│
├── data/                   # 🗂 Local data storage
│   └── onwhisper.db        # SQLite database file
│
└── docs/                   # 📚 Documentation
    ├── File.md             # This file — file structure reference
    └── README.md           # Optional: project overview & usage guide
```
