import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List

class HelpCog(commands.Cog):
    """Help command for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.command_categories = {
            "Leveling": {
                "description": "XP and leveling system commands",
                "commands": {
                    "level": "View your current level, XP, and progress",
                    "leaderboard": "View server XP leaderboard with rankings",
                    "levelconfig": "Configure leveling system settings and rewards"
                },
                "emoji": "🎮"
            },
            "Moderation": {
                "description": "Server moderation commands",
                "commands": {
                    "ban": "Ban a member from the server with reason",
                    "kick": "Kick a member from the server",
                    "timeout": "Temporarily mute a member",
                    "warn": "Issue a warning to a member",
                    "purge": "Bulk delete messages",
                    "lockdown": "Lock/unlock channel",
                    "slowmode": "Set channel slowmode delay"
                },
                "emoji": "👮"
            },
            "Roles": {
                "description": "Role management commands",
                "commands": {
                    "roles": "View and manage server roles",
                    "autorole": "Configure automatic role assignment",
                    "reactionrole": "Set up reaction-based role assignment"
                },
                "emoji": "🎭"
            },
            "Whispers": {
                "description": "Private thread management",
                "commands": {
                    "whisper": "Create private threads for communication",
                    "whispers": "View and manage existing whisper threads"
                },
                "emoji": "💬"
            },
            "Logging": {
                "description": "Server logging configuration",
                "commands": {
                    "logging": "Configure logging channels and events",
                    "viewlogs": "View server event logs with filters"
                },
                "emoji": "📝"
            },
            "Configuration": {
                "description": "Bot and server settings",
                "commands": {
                    "config": "Configure bot settings for the server",
                    "viewsettings": "View current server configuration"
                },
                "emoji": "⚙️"
            }
        }

    @app_commands.command(name="help", description="Get help with bot commands")
    @app_commands.describe(
        category="Specific category to get help for",
        command="Specific command to get help for"
    )
    async def help(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None,
        command: Optional[str] = None
    ):
        """Show help for bot commands"""
        if command:
            # Show detailed help for specific command
            cmd = self.bot.tree.get_command(command)
            if not cmd:
                return await interaction.response.send_message(
                    f"❌ Command `{command}` not found!", ephemeral=True
                )
            
            embed = discord.Embed(
                title=f"Command: /{command}",
                description=cmd.description or "No description available.",
                color=discord.Color.blue()
            )
            
            # Add usage examples and more detailed help
            for cat in self.command_categories.values():
                if command in cat['commands']:
                    embed.add_field(
                        name="Usage",
                        value=cat['commands'][command],
                        inline=False
                    )
            
            if hasattr(cmd, 'parameters'):
                params = []
                for param in cmd.parameters:
                    desc = param.description or "No description"
                    required = "Required" if param.required else "Optional"
                    params.append(f"`{param.name}`: {desc} ({required})")
                if params:
                    embed.add_field(
                        name="Parameters",
                        value="\n".join(params),
                        inline=False
                    )
            
            # Add examples if available
            if hasattr(cmd, 'examples'):
                embed.add_field(
                    name="Examples",
                    value="\n".join(cmd.examples),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if category:
            # Show commands for specific category
            category_title = next(
                (k for k in self.command_categories.keys() 
                 if k.lower() == category.lower()),
                None
            )
            if not category_title:
                return await interaction.response.send_message(
                    f"❌ Category `{category}` not found!", ephemeral=True
                )
            
            cat_data = self.command_categories[category_title]
            embed = discord.Embed(
                title=f"{cat_data['emoji']} {category_title} Commands",
                description=cat_data['description'],
                color=discord.Color.blue()
            )
            
            for cmd_name, cmd_desc in cat_data['commands'].items():
                embed.add_field(
                    name=f"/{cmd_name}",
                    value=cmd_desc,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Show main help overview
        embed = discord.Embed(
            title="📚 Command Categories",
            description=(
                "Welcome to the help menu! Here are all available command categories.\n"
                "Use `/help <category>` to see commands in each category.\n"
                "Use `/help <command>` to see detailed command usage."
            ),
            color=discord.Color.blue()
        )
        
        for cat_name, cat_data in self.command_categories.items():
            embed.add_field(
                name=f"{cat_data['emoji']} {cat_name}",
                value=(
                    f"{cat_data['description']}\n"
                    f"Commands: {len(cat_data['commands'])}\n"
                    f"Example: /{next(iter(cat_data['commands']))}"
                ),
                inline=False
            )
            
        if self.bot.user:
            embed.set_footer(
                text=f"Type /help <category> for more info",
                icon_url=self.bot.user.display_avatar.url
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
