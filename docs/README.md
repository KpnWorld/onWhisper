# onWhisper Bot Manual

**Version:** Development Build 2026  
**Platform:** discord.py | SQLAlchemy | Multi-Hosting Compatible  

> **This "Manual Overview" serves as a foundational guide for expanding upon the current version of onWhisper.**  
> It details the bot's core components, including its file structure, database organization, command system, coding standards, and web app interface.  
> The aim is to provide a clear blueprint for future development efforts, ensuring consistency and maintainability across all contributions.  
> By understanding these established patterns, new developers can easily integrate their work while adhering to the project's design principles.

---

## 📚 Table of Contents

1. [File Structure](./FileStructure.md)  
2. [Database Structure](./Database.md)  
3. [Command System](./Commands.md)  
4. [Code Style & Structure Guide](./CodeStyle.md)  
5. [Development & Hosting](./Development.md)  
6. [Web App Control Center](./WebApp.md)  

---

### 📌 About onWhisper

onWhisper is a feature-rich Discord bot built with **discord.py** and **SQLAlchemy**, offering:

- Leveling system with XP gain, cooldowns, and configurable rates  
- Role rewards for reaching levels  
- Whispers (private, staff-viewable anonymous messages)  
- Autoroles, reaction roles, and color roles  
- Logging and moderation tools  
- Fully slash command-based interface  
- **Web App Control Center** for monitoring and managing the bot remotely  

---

### 🔹 Development Goals (2026 Update)

- Maintain a clean, modular codebase  
- Keep database structure consistent, scalable, and ORM-managed via SQLAlchemy  
- Ensure commands follow a standard format  
- **Cross-hosting compatibility**: able to run on Replit, PythonAnywhere, local machines, or any standard Python environment  
- **Web App Control Center**: monitor stats, manage guild settings, and track XP and whispers  
- Document everything for future contributors  

---

### ⚙️ Notes on Hosting

- SQLAlchemy abstracts database access, allowing flexibility in backend choice (SQLite, PostgreSQL, MySQL, etc.)  
- Hosting decisions are deferred; the bot is designed to be portable and environment-agnostic  
- Web app can be deployed alongside the bot or independently for remote control  


