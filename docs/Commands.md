# 📝 onWhisper Command Reference

This document outlines all **27 synced slash commands** available in onWhisper. Each command includes its purpose, parameters, and database usage.

---

## ⚙️ Configuration (`config.py`) - 2 Commands

### `/config view-all`
- Shows all current configuration values for the server
- 🧠 **Uses DBManager**: `get_guild_settings`

### `/config view <key>`
- View a specific configuration value
- 🧠 **Uses DBManager**: Config system with type conversion

### `/config set <key> <value>`
- Update a specific configuration setting
- 🧠 **Uses DBManager**: `set_guild_setting`

### `/log-setup view-config`
- Display current logging event configuration
- 🧠 **Uses DBManager**: LoggingManager channel resolution

### `/log-setup configure <channel> <event>`
- Configure logging events for a channel (channel-first workflow)
- **Parameters**:
  - `channel`: Target text channel for logs
  - `event`: Event type (member, message, moderation, voice, channel, role, bot, whisper, or "all")
- 🧠 **Uses DBManager**: Multiple configuration updates via LoggingManager

---

## 📈 Leveling (`leveling.py`) - 6 Commands

### `/level [user]`
- View your or another user's level and XP progress
- 🧠 **Uses DBManager**: `get_user_xp`, level calculation

### `/leaderboard`
- Display server XP leaderboard with top 10 users
- 🧠 **Uses DBManager**: `get_leaderboard`

### `/setlevel <member> <level>`
- Manually set a member's level (Admin only)
- 🧠 **Uses DBManager**: `set_user_level`

### `/add-level-role <level> <role>`
- Assign a role reward for reaching a specific level (Admin only)
- 🧠 **Uses DBManager**: `add_level_reward`

### `/remove-level-role <level>`
- Remove role reward for a specific level (Admin only)
- 🧠 **Uses DBManager**: `remove_level_reward`

### `/list-level-roles`
- Display all configured level role rewards
- 🧠 **Uses DBManager**: `get_level_rewards`

---

## 🔨 Moderation (`moderation.py`) - 5 Commands

> All moderation commands support both slash and prefix usage (hybrid commands)
> All actions are logged through the unified logging system

### `/kick <member> [reason]`
- Remove a member from the server
- **Logging**: Moderation events category
- 🧠 **Uses DBManager**: `log_moderation_action`

### `/ban <member> [reason]`
- Ban a member from the server
- **Logging**: Moderation events category  
- 🧠 **Uses DBManager**: `log_moderation_action`

### `/mute <member> [duration] [reason]`
- Temporarily restrict a member from messaging
- **Logging**: Moderation events category
- 🧠 **Uses DBManager**: `log_moderation_action`

### `/warn <member> [reason]`
- Issue a warning to a member
- **Logging**: Moderation events category
- 🧠 **Uses DBManager**: `log_moderation_action`

### `/purge <amount>`
- Delete a specified number of recent messages
- **Parameters**: 
  - `amount`: Number of messages to delete (1-100)
- **Logging**: Moderation events category
- 🧠 **Uses DBManager**: `log_moderation_action`

---

## 🤫 Whisper System (`whisper.py`) - 1 Command

### `/whisper`
- Create anonymous whisper thread using modal form interface
- **Features**:
  - Modal form for reason input
  - Automatic thread creation in configured channel
  - Admin notifications with configurable role pings
  - Sequential whisper numbering
  - Staff management interface
- **Logging**: Whisper events category
- 🧠 **Uses DBManager**: `create_whisper`, whisper tracking

---

## 🎭 Role Management (`roles.py`) - Multiple Commands

### `/autorole set <role>`
- Set automatic role assignment for new members
- 🧠 **Uses DBManager**: `set_autorole`

### `/autorole disable`
- Disable automatic role assignment
- 🧠 **Uses DBManager**: Configuration updates

### `/reactionrole add <message_id> <emoji> <role>`
- Add emoji → role mapping to a message
- 🧠 **Uses DBManager**: `add_reaction_role`

### `/reactionrole remove <message_id> <emoji>`
- Remove reaction role mapping
- 🧠 **Uses DBManager**: `remove_reaction_role`

### `/reactionrole list [message_id]`
- List reaction role mappings
- 🧠 **Uses DBManager**: `get_reaction_roles`

### `/colorrole <role>`
- Set or update your color role
- 🧠 **Uses DBManager**: `set_color_role`

### `/colorrole clear`
- Remove your color role
- 🧠 **Uses DBManager**: Color role management

---

## ℹ️ Information (`info.py`) - Multiple Commands

### `/info`
- Display bot information and statistics
- Shows uptime, command count, server count

### `/ping`
- Check bot latency and response time

### `/serverinfo`
- Display detailed server information
- Member counts, creation date, roles, channels

### `/userinfo [member]`
- Show detailed information about a user
- **Includes**: Join date, roles, level/XP integration
- 🧠 **Uses DBManager**: User level and XP data

---

## 📖 Help System (`help.py`) - 2 Commands

### `/help`
- Display interactive help menu with command categories

### `/help <command>`
- Show detailed usage information for a specific command

---

## 🔧 Debug & Development (`debug.py`) - Multiple Commands

> Admin-only commands for bot maintenance and troubleshooting

### `/debug info`
- Display system information and bot statistics

### `/debug reload <cog>`
- Reload a specific cog without restarting the bot

### `/debug database`
- Show database statistics and health information
- 🧠 **Uses DBManager**: Database metrics

### `/debug config`
- Display configuration debug information
- 🧠 **Uses DBManager**: Configuration analysis

---

## 📊 Configuration Options (71 Total)

### **Core Settings (1)**
- `prefix` → Command prefix (default: "!")

### **Leveling System (6)**
- `leveling_enabled` → Enable/disable leveling
- `xp_rate` → XP per message (default: 10)
- `xp_cooldown` → XP gain cooldown in seconds (default: 60)
- `level_up_message` → Level up announcement template
- `level_channel` → Channel for level announcements

### **Moderation (2)**
- `moderation_enabled` → Enable/disable moderation features
- `mod_log_channel` → Channel for moderation logs

### **Unified Logging System (17)**
- `unified_logging_enabled` → Master logging toggle
- **Per-category toggles** (8): `log_[category]_events`
- **Per-category channels** (8): `log_[category]_channel`

### **Role Management (2)**
- `roles_enabled` → Enable/disable role features
- `autorole_enabled` → Enable/disable autorole

### **Whisper System (5)**
- `whisper_enabled` → Enable/disable whisper system
- `whisper_channel` → Channel for whisper threads
- `whisper_notification_enabled` → Enable admin notifications
- `whisper_notification_channel` → Channel for admin notifications
- `whisper_notification_role` → Role to ping for notifications

---

## 📌 Command Features

### **Universal Features**
- **Permission-based access control** for admin commands
- **Error handling** with user-friendly messages
- **Consistent embed styling** across all commands
- **Database integration** with automatic error recovery

### **Logging Integration**
- **Automatic event logging** for all major actions
- **8 event categories** with configurable channels
- **Smart fallback channels** when specific channels unavailable
- **Admin notification system** for whisper events

### **Hybrid Command Support**
- **Moderation commands** work as both slash and prefix commands
- **Flexible usage patterns** for different user preferences
- **Consistent behavior** across both command types

---

## 🎯 Quick Command Summary

**Total Commands: 27**
- Configuration: 2
- Leveling: 6  
- Moderation: 5
- Whisper: 1
- Roles: 6+
- Info: 4+
- Help: 2
- Debug: 3+

All commands are automatically synced and use the modern Discord slash command interface with comprehensive database integration and unified logging.