# 🧠 onWhisper Database System

The onWhisper bot uses `aiosqlite` for persistent storage. The `DBManager` class in `utils/db_manager.py` handles all interactions. This document includes all table schemas and callable methods.

---

## 🗃️ Tables Overview

| Table Name           | Purpose                                      |
|----------------------|----------------------------------------------|
| guild_settings       | Stores config values per guild               |
| leveling_users       | Stores XP, levels, and message counts        |
| leveling_roles       | XP-based reward roles                        |
| autoroles            | Auto-assigned roles on join                  |
| reaction_roles       | Stores reaction role bindings                |
| color_roles          | Stores user color role assignments           |
| whispers             | Tracks active whisper threads (ticket system)|

---

## 🏗️ Table Schema Reference

### leveling_users
```sql
  guild_id INTEGER,
  user_id INTEGER,
  xp INTEGER,
  level INTEGER,
  message_count INTEGER,
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
  status TEXT,
  created_at TEXT,
  updated_at TEXT,
  PRIMARY KEY (guild_id, thread_id)
```
---

## 📘 DBManager Method Reference

## 🔧 Guild Settings

### `get_guild_settings(guild_id: int)`
Returns all stored settings for the specified guild.

### `update_guild_setting(guild_id: int, key: str, value: Any)`
Updates a single setting value for a guild.

### `set_autorole(guild_id: int, role_id: int)`
Sets the auto role for new members in a guild.

### `get_autorole(guild_id: int)`
Fetches the auto role ID for a guild.

---

## 📊 Leveling

### `add_xp(guild_id: int, user_id: int, amount: int)`
Adds XP to a user and handles level-up logic if needed.

### `get_xp(guild_id: int, user_id: int)`
Gets the total XP a user has in a guild.

### `get_level(guild_id: int, user_id: int)`
Returns the level of a user based on stored XP.

### `get_top_users(guild_id: int, limit: int = 10)`
Returns a leaderboard of users with the highest XP.

### `set_level_role(guild_id: int, level: int, role_id: int)`
Assigns a role reward to a level in the guild.

### `get_level_roles(guild_id: int)`
Returns all configured level reward roles for a guild.

### `clear_user_xp(guild_id: int, user_id: int)`
Removes all XP data for a specific user in a guild.

### `reset_leaderboard(guild_id: int)`
Resets all XP and leveling data for a guild.

---

## 🎭 Roles

### `add_reaction_role(guild_id: int, message_id: int, emoji: str, role_id: int)`
Stores a new reaction-role binding in the database.

### `remove_reaction_role(guild_id: int, message_id: int, emoji: str)`
Removes a reaction-role binding.

### `get_reaction_roles(guild_id: int)`
Returns all reaction role bindings in a guild.

### `set_color_role(guild_id: int, user_id: int, role_id: int)`
Saves the selected color role for a user.

### `get_color_role(guild_id: int, user_id: int)`
Returns the active color role for a user.

### `clear_color_role(guild_id: int, user_id: int)`
Removes a user's color role record.

---

## 🤫 Whisper System

### `create_whisper(guild_id: int, user_id: int, thread_id: int)`
Creates a new whisper thread record.

### `get_active_whispers(guild_id: int)`
Returns all currently active whisper threads in a guild.

### `close_whisper(guild_id: int, thread_id: int)`
Marks a whisper thread as closed.

### `get_whisper_by_user(guild_id: int, user_id: int)`
Returns the active whisper thread ID for a user, if any.

---

## 🧹 Maintenance

### `init_tables()`
Creates all required tables if they don’t exist.

### `cleanup()`
Optional: perform data pruning or optimization tasks.

---

## 📌 Usage Notes

- All methods are `async` — use `await`.
- Access through `self.db` in your cogs.
- If a method does not return anything, it’s a direct update.
- Designed to be scalable across multi-guild bots.
