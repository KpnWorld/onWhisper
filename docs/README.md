# onWhisper Bot Manual

**Version:** Development Build 2025  
**Platform:** discord.py | SQLite | Replit Hosting  

> **This "Manual Overview" serves as a foundational guide for expanding upon the current version of onWhisper.**  
> It details the bot's core components, including its file structure, database organization, command system, and coding standards.  
> The aim is to provide a clear blueprint for future development efforts, ensuring consistency and maintainability across all contributions.  
> By understanding these established patterns, new developers can easily integrate their work while adhering to the project's design principles.

---

## 📚 Table of Contents

1. [File Structure](./FileStructure.md)  
2. [Database Structure](./Database.md)  
3. [Command System](./Commands.md)  
4. [Code Style & Structure Guide](./CodeStyle.md)  
5. [Development & Hosting](./Development.md)  

---

### 📌 About onWhisper

onWhisper is a comprehensive Discord bot built with **discord.py** and **SQLite**, offering:

- **Leveling system** with XP tracking, role rewards, and leaderboards
- **Role management** including autoroles, reaction roles, and color roles
- **Comprehensive moderation tools** with kick, ban, mute, warn, and purge operations
- **Whisper system** for anonymous communication via private threads with modal forms
- **Unified logging system** with 8 event categories and channel-first configuration
- **Admin notifications** for whisper creation and management
- **32 synced slash commands** with hybrid command support
- **Flexible level-up messaging** with same channel, DM, or dedicated channel options
- **Type-safe configuration** with 72 configurable options per guild  

---

### 🔹 Development Goals
- **Modular cog-based architecture** with 8 specialized modules
- **Unified logging system** covering all major bot events
- **Type-safe configuration management** with automatic value conversion
- **Channel-first logging workflow** for intuitive admin setup
- **Comprehensive database coverage** with 40+ methods across 7 tables
- **Complete documentation** for maintainable development
