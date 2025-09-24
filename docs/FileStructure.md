# 📂 onWhisper File Structure

This page documents the complete file and folder layout for onWhisper.  
Understanding this structure ensures consistent organization and faster onboarding for new developers.

---

## 🗂 Root Directory

```
📂 onWhisper/  
│  
├── bot.py               # 🚀 Main bot startup file with LoggingManager integration
├── .env                 # 🔐 Token & environment configs  
├── requirements.txt     # 📦 Python dependencies
├── runtime.txt          # 🐍 Python version specification
├── version.txt          # 📋 Bot version tracking
├── instructions.txt     # 📝 Setup instructions
├── replit.md           # 📊 Technical documentation and preferences
│  
├── cogs/                # ⚙️ All bot modules (8 active cogs)  
│ ├── config.py          # ⚙️ Configuration management & simplified /log-setup
│ ├── debug.py           # 🔧 Development and debugging utilities
│ ├── help.py            # 📖 Dynamic help system with categorized commands
│ ├── info.py            # ℹ️ Bot information, server stats, utility commands
│ ├── leveling.py        # 📈 XP tracking, leveling system, role rewards
│ ├── moderation.py      # 🔨 Kick, ban, mute, warn, purge with logging integration
│ ├── roles.py           # 🎭 Autoroles, reaction roles, color roles
│ └── whisper.py         # 🤫 Anonymous whisper system with modal forms
│  
├── utils/               # 🧠 Core utility modules  
│ ├── db_manager.py      # 🗄️ Database operations (40+ methods, 7 tables)
│ ├── config.py          # ⚙️ ConfigManager with type-safe operations (71 options)
│ └── logging_manager.py # 📊 Unified logging system (8 event categories)
│  
├── data/                # 🗂 Persistent local data  
│ └── onwhisper.db       # 🗃 SQLite database file  
│  
├── docs/                # 📚 Complete documentation structure
│ ├── README.md          # 📝 Manual overview & table of contents  
│ ├── FileStructure.md   # 🗂 This file - directory structure reference  
│ ├── Database.md        # 💿 Database schema & all DBManager methods
│ ├── Commands.md        # 🧑‍💻 Complete slash command reference (27 commands)
│ ├── CodeStyle.md       # 🎨 Code style & structure guidelines
│ ├── Development.md     # 🛠️ Setup, contribution, and hosting instructions
│ └── Updates.md         # 📋 Update history and changelog
│  
└── attached_assets/     # 📎 Temporary files and logs
```

---

## 📁 Cogs (Command Modules)

> Located in: `cogs/`  
> 8 specialized modules, each handling distinct functionality with integrated logging.

| File          | Purpose                                                     | Commands |
|---------------|-------------------------------------------------------------|----------|
| config.py     | Configuration management with channel-first log setup      | 2        |
| debug.py      | Development utilities and debugging tools                   | Multiple |
| help.py       | Dynamic help system with categorized documentation         | 2        |
| info.py       | Bot information, server stats, and utility commands        | Multiple |
| leveling.py   | XP tracking, leveling system, role rewards, leaderboards   | 6        |
| moderation.py | Comprehensive moderation tools with unified logging        | 5        |
| roles.py      | Autoroles, reaction roles, and color role management       | Multiple |
| whisper.py    | Anonymous whisper system with modal forms & notifications  | 1        |

**Total: 27 synced application commands**

---

## 🛠 Utils (Core Utilities)

> Located in: `utils/`  
> Essential utility modules used across all cogs.

| File | Purpose | Key Features |
|------|---------|--------------|
| `db_manager.py` | **Database Manager** with full CRUD operations | 40+ async methods, 7 tables, type-safe operations |
| `config.py` | **Configuration Manager** with guild-specific settings | 71 configurable options, type conversion, caching |
| `logging_manager.py` | **Unified Logging System** for all bot events | 8 event categories, smart channel resolution, fallbacks |

---

## 💾 Data (Persistent Storage)

> Located in: `data/`  

| File | Purpose | Details |
|------|---------|---------|
| `onwhisper.db` | SQLite database file | 7 tables, multi-guild support, automated migrations |

---

## 📚 Documentation Structure

> Located in: `docs/`  
> Complete technical documentation for developers and administrators.

| File | Purpose | Content |
|------|---------|---------|
| `README.md` | Project overview and navigation | Feature summary, development goals |
| `FileStructure.md` | Directory structure reference | This file - complete layout |
| `Database.md` | Database documentation | Schema, methods, usage examples |
| `Commands.md` | Command reference guide | All 27 commands with parameters |
| `CodeStyle.md` | Development standards | Code formatting, patterns, conventions |
| `Development.md` | Setup and hosting guide | Installation, deployment, contribution |
| `Updates.md` | Version history | Update log and changelog |

---

## 📌 Architecture Philosophy

### **Modular Design Principles**
- **Separation of Concerns**: Each cog handles one functional area
- **Utility Reusability**: Core utilities shared across all modules  
- **Database Abstraction**: Single DBManager for all data operations
- **Configuration Centralization**: Unified config system with type safety

### **Logging Integration**
- **Event-Driven Architecture**: LoggingManager integrated throughout
- **Channel-First Workflow**: Intuitive admin configuration process
- **Comprehensive Coverage**: 8 event categories covering all bot functions
- **Smart Fallbacks**: Robust error handling and alternative channels

### **Scalability Features**
- **Multi-Guild Support**: All operations guild-scoped
- **Type-Safe Operations**: Automatic value conversion and validation
- **Async Performance**: Full async/await pattern throughout
- **Modular Expansion**: Easy to add new cogs and features

---

## 🔄 Development Workflow

1. **New Features**: Create new cog in `cogs/` directory
2. **Database Changes**: Add methods to `utils/db_manager.py`
3. **Configuration**: Add options to `utils/config.py`
4. **Logging**: Integrate with `utils/logging_manager.py`
5. **Documentation**: Update relevant files in `docs/`

This structure ensures maintainable, scalable development with comprehensive documentation coverage.