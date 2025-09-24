# 🧠 onWhisper Database System

The onWhisper bot uses `aiosqlite` for persistent storage. The `DBManager` class in `utils/db_manager.py` handles all interactions with automatic connection management and type-safe operations.

---

## 🗃️ Tables Overview

| Table Name           | Purpose                                      |
|----------------------|----------------------------------------------|
| guild_settings       | Per-guild configuration settings (71 options) |
| leveling_users       | User XP and level tracking per guild        |
| leveling_roles       | Level-based role rewards                     |
| autoroles            | Auto-assigned roles on member join          |
| reaction_roles       | Emoji → role mappings for messages          |
| color_roles          | User-specific color role assignments        |
| whispers             | Anonymous whisper thread tracking           |
| moderation_logs      | Complete moderation action history          |

---

## 🏗️ Table Schema Reference

### guild_settings
```sql
guild_id INTEGER,
setting TEXT,
value TEXT,
PRIMARY KEY (guild_id, setting)
```

### leveling_users  
```sql
guild_id INTEGER,
user_id INTEGER,
xp INTEGER DEFAULT 0,
level INTEGER DEFAULT 0,
PRIMARY KEY (guild_id, user_id)
```

### leveling_roles
```sql
guild_id INTEGER,
level INTEGER,
role_id INTEGER,
PRIMARY KEY (guild_id, level)
```

### autoroles
```sql
guild_id INTEGER PRIMARY KEY,
role_id INTEGER
```

### reaction_roles
```sql
guild_id INTEGER,
message_id INTEGER,
emoji TEXT,
role_id INTEGER,
PRIMARY KEY (guild_id, message_id, emoji)
```

### color_roles
```sql
guild_id INTEGER,
user_id INTEGER,
role_id INTEGER,
PRIMARY KEY (guild_id, user_id)
```

### whispers
```sql
guild_id INTEGER,
user_id INTEGER,
thread_id INTEGER,
is_open INTEGER DEFAULT 1,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
closed_at TIMESTAMP,
closed_by_staff INTEGER DEFAULT 0,
PRIMARY KEY (guild_id, user_id, thread_id)
```

### moderation_logs
```sql
guild_id INTEGER,
case_id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
action TEXT,
reason TEXT,
moderator_id INTEGER,
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 📘 DBManager Method Reference

## 🔧 Generic Query Methods

### `execute(query: str, params: Tuple = ())`
Execute a query with parameters and return cursor.

### `fetchall(query: str, params: Tuple = ())`
Fetch all rows from a query as a list.

### `fetchrow(query: str, params: Tuple = ())`
Fetch single row as aiosqlite.Row object.

### `fetchone(query: str, params: Tuple = ())`
Fetch single row as dictionary.

---

## ⚙️ Guild Settings Management

### `get_guild_settings(guild_id: int)`
Returns all stored configuration settings for the specified guild.

### `set_guild_setting(guild_id: int, setting: str, value: str)`
Updates a single configuration setting for a guild.

### `remove_guild_setting(guild_id: int, setting: str)`
Deletes a specific configuration setting for a guild.

---

## 📊 Leveling System

### `get_user_xp(guild_id: int, user_id: int)`
Get user's current XP in the specified guild.

### `set_user_xp(guild_id: int, user_id: int, xp: int)`
Set user's XP to a specific value.

### `add_xp(guild_id: int, user_id: int, amount: int)`
Add XP to a user (handles conflicts automatically).

### `set_user_level(guild_id: int, user_id: int, level: int)`
Set user's level directly.

### `get_leaderboard(guild_id: int, limit: int = 10)`
Get top users by level/XP with configurable limit.

### `add_level_reward(guild_id: int, level: int, role_id: int)`
Add a role reward for reaching a specific level.

### `remove_level_reward(guild_id: int, level: int)`
Remove the role reward for a specific level.

### `get_level_rewards(guild_id: int)`
Get all level → role mappings for a guild.

### `set_level_role(guild_id: int, level: int, role_id: int)`
Set role for a specific level (alias for add_level_reward).

### `get_level_roles(guild_id: int)`
Get level roles as dictionary mapping.

---

## 🎭 Role Management

### `set_autorole(guild_id: int, role_id: int)`
Set automatic role assigned to new members.

### `get_autorole(guild_id: int)`
Get the current autorole ID for a guild.

### `add_reaction_role(guild_id: int, message_id: int, emoji: str, role_id: int)`
Add an emoji → role mapping for a message.

### `remove_reaction_role(guild_id: int, message_id: int, emoji: str)`
Remove a reaction role mapping.

### `get_reaction_roles(guild_id: int, message_id: int)`
Get all emoji → role mappings for a specific message.

### `set_color_role(guild_id: int, user_id: int, role_id: int)`
Set a user's color role.

### `get_color_role(guild_id: int, user_id: int)`
Get a user's current color role.

---

## 🤫 Whisper System

### `create_whisper(guild_id: int, user_id: int, thread_id: int)`
Create a new whisper thread record, returns sequential whisper number.

### `get_whisper_by_number(guild_id: int, whisper_number: int)`
Get whisper details by sequential number (1-indexed).

### `get_active_whispers(guild_id: int)`
Get all currently open whisper threads.

### `close_whisper(guild_id: int, thread_id: int, closed_by_staff: bool = False)`
Close a whisper thread with staff tracking.

### `delete_whisper(guild_id: int, thread_id: int)`
Permanently delete a whisper record from database.

### `get_open_whispers(guild_id: int)`
Get open whispers with creation timestamps.

---

## 🛡️ Moderation

### `log_moderation_action(guild_id: int, user_id: int, action: str, reason: str, moderator_id: int)`
Log a moderation action with automatic case numbering.

### `get_moderation_logs(guild_id: int, user_id: int)`
Get all moderation logs for a specific user.

---

## 🧹 Maintenance

### `reset_guild_data(guild_id: int)`
Delete all data for a guild across all tables.

### `vacuum()`
Optimize database storage and performance.

---

## 📌 Usage Notes

- **All methods are async** — use `await` in your cogs
- **Type-safe operations** with automatic value conversion
- **Connection management** handled automatically with locks
- **Error handling** built into all database operations
- **Multi-guild support** — all operations are guild-scoped
- **Atomic transactions** prevent race conditions