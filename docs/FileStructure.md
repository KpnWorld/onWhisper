# 📂 onWhisper File Structure

This page documents the full file and folder layout for onWhisper.  
Understanding this structure ensures consistent organization and faster onboarding for new developers.

---

## 🗂 Root Directory

```
onWhisper/
│
├── bot.py               # 🚀 Main bot startup file (onWhisperBot)
├── .env                 # 🔐 Token & environment configs
│
├── cogs/                # ⚙️ All bot modules (cogs)
│ ├── info.py            # ℹ️ /bot, /user, /guild, /role, /channel info
│ ├── leveling.py        # 📈 XP, roles, leaderboard
│ ├── moderation.py      # 🔨 Warn, mute, kick, ban, lockdown, purge (hybrid)
│ ├── roles.py           # 🎭 Auto, reaction, color roles
│ ├── logging.py         # 📝 Event logs (joins, edits, deletions)
│ └── whisper.py         # 🤫 Whisper System (thread-based tickets)
│
├── utils/               # 🧠 Core logic managers
│ ├── db_manager.py      # 🗄️ Database layer using SQLAlchemy ORM (async-ready)
│ ├── models.py          # 🧩 ORM models for all tables (used by db_manager)
│ └── config.py          # ⚙️ ConfigManager for guild settings
│
├── data/                # 🗂 Persistent local data
│ └── onwhisper.db       # 🗃 SQLAlchemy database file
│
├── webapp/              # 🌐 Web Control Center for monitoring & managing bot
│ ├── static/            # 📁 Main backend files for html templates (`CSS`&`JS`)
│ │    ├── css/
│ │    │   └── style.css
│ │    └── js/
│ │        └── script.js
│ ├── templates/         # 📁 HTML templates for dashboard
│ │         
│ ├── app.py             # 🗝️ MAIN Flask app config
│ └── routes.py          # 📟 API endpoints for bot stats, XP, whispers, guild settings
├── docs/
│ ├── README.md          # 📝 Full slash command reference with DB usage
│ ├── FileStructure.md   # 🗂 File Structure reference
│ ├── Database.md        # 💿 Full database schema & DBManager methods documentation
│ ├── Commands.md        # 🧑‍💻 Full slash command reference with DB usage
│ ├── CodeStyle.md       # 🎨 Universal code style & structure guide
│ └── Development.md     # 🛠️ Instructions for Setup, contribution, and hosting
```


---

## 📁 Cogs (Command Modules)

> Located in: `cogs/`  
> Each cog is a separate feature module, loaded dynamically at runtime.

| File | Purpose |
|------|---------|
| `info.py` | General info commands (server, bot, user, roles, channels) |
| `leveling.py` | XP gain, level tracking, leaderboard, level config |
| `moderation.py` | Kick, ban, mute, and moderation utilities |
| `roles.py` | Autoroles, reaction roles, and color roles |
| `logging.py` | Server logging for joins, leaves, message deletes, edits |
| `whisper.py` | Anonymous whispers, staff view, and whisper settings |
| `config.py` | Guild-specific configuration commands |

---

## 🛠 Utils (Core Utilities)

> Located in: `utils/`  
> Contains helper modules used across cogs.

| File             | Purpose |
|------------------|---------|
| db_manager.py    | SQLAlchemy DB manager with async ORM CRUD methods |
| config.py        | Global constants, embed colors, and helper functions |
---

## 💾 Data (Persistent Storage)

> Located in: `data/`  

| File | Purpose |
|------|---------|
| onwhisper.db   | Default SQLite database file (can be replaced by PostgreSQL, MySQL, etc.) |

---

## 🌐 Web App (Control Center)

Located in: `webapp/`  
Provides a web-based interface to monitor and manage the bot.

| File/Folder     | Purpose |
|-----------------|---------|
| app.py          | Main webapp config |
| routes.py       | API endpoints for bot stats, XP, whispers, and guild settings (Fetched from `Utils/`|
| static/         | Main backend files for html templates (`CSS`&`JS`)|
| templates/      | HTML templates for dashboard |

---

## 📚 Documentation

> Located in: `docs/`  

| File | Purpose |
|------|---------|
| `README.md` | Manual overview & table of contents |
| `FileStructure.md` | (This file) Full directory structure reference |
| `Database.md` | Database schema & DBManager methods |
| `Commands.md` | Slash command reference |
| `CodeStyle.md` | Universal code style & structure guide |
| `Development.md` | Setup, contribution, and hosting instructions |

---

## 📌 File Structure Philosophy

- **Separation of Concerns:** Each cog handles a single category of functionality.  
- **Modular Design:** Utilities are reusable across multiple cogs.  
- **Scalable Layout:** New features get their own cog, webapp module, and database methods.  
- **Cross-Hosting Ready:** The project is structured to support any Python environment.  
- **Clear Documentation:** All major files and folders are listed in `docs/` for contributor reference.
- **Config Migrations:** Database migrations are handled via SQLAlchemy’s Alembic integration for schema evolution.
---

