# 📝 onWhisper Slash Command Reference

This document outlines all slash commands available in the onWhisper bot. Each command includes its purpose and whether it uses the database.

---

## 🧠 General Info (`info.py`)

### `/bot`
- Shows bot statistics and meta info (uptime, ping, etc).

### `/user [member]`
- Displays profile details about a user.
- 🧠 **Uses DBManager**: `get_xp`, `get_level`

### `/guild`
- Overview of guild/server info.

### `/role [role]`
- Details about a selected role.

### `/channel [channel]`
- Information about a channel.

---

## 📈 Leveling (`leveling.py`)

### `/level [member]`
- View your or another member's level and XP.
- 🧠 **Uses DBManager**: `get_xp`, `get_level`

### `/leaderboard`
- Show XP leaderboard.
- 🧠 **Uses DBManager**: `get_top_users`

### `/levelrole set <level> <role>`
- Assign a role for reaching a specific level.
- 🧠 **Uses DBManager**: `set_level_role`

### `/levelrole remove <level>`
- Remove a level reward role.
- 🧠 **Uses DBManager**: custom deletion logic (likely uses SQL DELETE)

### `/levelrole list`
- List all level reward roles.
- 🧠 **Uses DBManager**: `get_level_roles`

---

## 🔨 Moderation (`moderation.py` - hybrid)

> Can be used as both slash and prefix (`-`) commands.  
> These commands do **not** use the database.

### `/warn <member> [reason]`
- Warns a member (may be logged externally in the future).

### `/mute <member> [duration] [reason]`
- Temporarily restricts a user from messaging.

### `/kick <member> [reason]`
- Removes a user from the server.

### `/ban <member> [reason]`
- Bans a user.

### `/unban <user_id>`
- Reverses a ban.

### `/purge <amount>`
- Deletes a number of recent messages in a channel.

### `/lock [channel]`
- Locks the selected or current channel.

### `/unlock [channel]`
- Unlocks the selected or current channel.

---

## 👥 Roles (`roles.py`)

### `/autorole set <role>`
- Automatically assign a role on join.
- 🧠 **Uses DBManager**: `set_autorole`

### `/autorole disable`
- Disables autorole assignment.
- 🧠 **Uses DBManager**: `update_guild_setting`

### `/reactionrole add <message_id> <emoji> <role>`
- Add a reaction-role binding.
- 🧠 **Uses DBManager**: `add_reaction_role`

### `/reactionrole remove <message_id> <emoji>`
- Remove a reaction-role binding.
- 🧠 **Uses DBManager**: `remove_reaction_role`

### `/color <role>`
- Set or clear your color role.
- 🧠 **Uses DBManager**: `set_color_role`, `clear_color_role`

---

## 🤫 Whisper System (`whisper.py`)

### `/whisper open`
- Opens a private Whisper thread.
- 🧠 **Uses DBManager**: `create_whisper`

### `/whisper close`
- Closes your active Whisper thread.
- 🧠 **Uses DBManager**: `close_whisper`

### `/whisper list`
- Lists all open Whisper threads (admin-only).
- 🧠 **Uses DBManager**: `get_active_whispers`

---

## ⚙️ Configuration (`config.py`)

### `/config view`
- Shows all current config values for the server.
- 🧠 **Uses DBManager**: `get_guild_settings`

### `/config set <key> <value>`
- Updates a specific config key in the database.
- 🧠 **Uses DBManager**: `update_guild_setting`

---

### 🔑 Config Keys

| Key               | Description                                      |
|------------------|--------------------------------------------------|
| `log_channel_id`  | Channel ID for logging (if implemented)         |
| `auto_role_id`    | Role ID given to new members on join            |
| `mute_role_id`    | Role used to mute users                         |
| `whisper_enabled` | Enables or disables the Whisper system          |
| `xp_rate`         | XP earned per message                           |
| `xp_cooldown`     | Cooldown in seconds before earning more XP      |
| `created_at`      | Timestamp when config was created               |
| `updated_at`      | Timestamp of last config update                 |

> These keys are stored in the `guild_settings` table and managed through `DBManager`.

---

## ❓ Help System (`help.py`) 

### `/help`
- Shows an interactive help menu with categories.

### `/help <category>`
- Lists all commands under a category (info, leveling, moderation, roles, whisper, config, debug). 

### `/help <command>`
- Shows detailed usage and options for a specific command.

> *(Do not use DBManager - pulls directly from bot command registry.)*
---

## 🧪 Debug & Maintenance (`debug.py`)

### `/debug key`
- Shows all DB keys currently tracked.
- 🧠 **Uses DBManager**: Custom method or wrapper.

### `/debug resetdb`
- Fully wipes DB data for current guild.
- 🧠 **Uses DBManager**: `reset_leaderboard`, `update_guild_setting`, and/or custom logic

### `/debug version`
- Shows bot + DB versioning info (not DB-bound).

---

## 📌 Notes

- All commands use `@bot.slash_command`
- Commands that access or write to persistent storage are marked `🧠 Uses DBManager`
- Commands are permission-guarded and use styled embeds with command-type footers
- Debug tools are admin-only



