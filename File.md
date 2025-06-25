onWhisper/
│
├── bot.py                  # 🚀 Main bot startup file (onWhisperBot)
├── .env                    # 🔐 Token & environment configs
├── requirements.txt        # 📦 Python dependencies
│
├── cogs/                   # ⚙️ All bot modules (cogs)
│   ├── info.py             # /bot, /user, /guild, /role, /channel info
│   ├── leveling.py         # XP, roles, leaderboard
│   ├── moderation.py       # Warn, mute, kick, ban, lockdown, purge (hybrid)
│   ├── roles.py            # Auto, reaction, color roles
│   ├── logging.py          # Event logs (joins, edits, deletions)
│   └── whisper.py          # 🤫 Whisper System (thread-based tickets)
│
├── utils/                  # 🧠 Core logic managers
│   ├── db_manager.py       # DB layer (aiosqlite)
│   └── config.py           # ConfigManager for guild settings
│    
│
├── data/                   # 🗂 Persistent local data
│   └── onwhisper.db        # SQLite database file
│
└── docs/
    ├── File.md             # 📄File Structure
    └── README.md           # 📄 (Optional) Bot documentation
