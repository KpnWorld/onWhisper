# cogs/help.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Any


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.command_categories: Dict[str, Dict[str, Any]] = {
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
                "description": "Server moderation commands (all support both / and prefix)",
                "commands": {
                    "kick": "kick <member> [reason] - Remove a member from the server",
                    "ban": "ban <member> [reason] - Ban a member permanently from the server", 
                    "unban": "unban <user> - Unban a user from the server",
                    "mute": "mute <member> <duration> [reason] - Timeout a member (duration in minutes)",
                    "unmute": "unmute <member> - Remove timeout from a member",
                    "warn": "warn <member> [reason] - Issue a warning to a member",
                    "warnings": "warnings <member> - Display all warnings for a member",
                    "modlogs": "modlogs <member> - Display all moderation actions for a member",
                    "purge": "purge <limit> - Bulk delete messages (limit: 1-100)",
                    "lock": "lock [channel] - Lock a channel to prevent @everyone from sending messages",
                    "unlock": "unlock [channel] - Unlock a channel to restore @everyone sending messages"
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
                "description": "Bot and server settings (slash commands only)",
                "commands": {
                    "config": "/config <action> [key] [value] - Configure bot settings (slash only)"
                },
                "emoji": "⚙️"
            },
            "Debug": {
                "description": "Owner-only debug and database analysis commands",
                "commands": {
                    "analyzedb": "Analyze database stats globally or per server",
                    "deletedata": "Delete user, server, or global data from the DB"
                },
                "emoji": "🛠️"
            }
        }

    @app_commands.command(name="help", description="Get help with bot commands")
    @app_commands.describe(
        category="Specific category to get help for",
        command="Specific command to get help for"
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name=cat_name, value=cat_name.lower())
            for cat_name in [
                "Leveling", "Moderation", "Roles",
                "Whispers", "Logging", "Configuration", "Debug"
            ]
        ]
    )
    async def help(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None,
        command: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            if command:
                cmd = self.bot.tree.get_command(command)
                if not cmd:
                    await interaction.followup.send(
                        f"❌ Command `{command}` not found!", ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"📘 Command Help - /{command}",
                    color=discord.Color.blue()
                )

                embed.add_field(name="Description", value=f"```{cmd.description or 'No description'}```", inline=False)

                for cat in self.command_categories.values():
                    if command in cat["commands"]:
                        embed.add_field(
                            name="Usage",
                            value=f"```{cat['commands'][command]}```",
                            inline=False
                        )

                if hasattr(cmd, "parameters"):
                    params = []
                    for param in cmd.parameters:
                        desc = param.description or "No description"
                        required = "Required" if param.required else "Optional"
                        params.append(f"{param.name}: {desc} ({required})")
                    if params:
                        embed.add_field(
                            name="Parameters",
                            value=f"```{chr(10).join(params)}```",
                            inline=False
                        )

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if category:
                category_title = next(
                    (k for k in self.command_categories.keys()
                     if k.lower() == category.lower()),
                    None
                )
                if not category_title:
                    await interaction.followup.send(
                        f"❌ Category `{category}` not found!", ephemeral=True
                    )
                    return

                cat_data = self.command_categories[category_title]
                
                # Get current prefix for moderation commands
                prefix = "!"
                if category_title == "Moderation" and interaction.guild:
                    try:
                        if hasattr(self.bot, 'config_manager'):
                            # Use a timeout to prevent hanging
                            import asyncio
                            prefix = await asyncio.wait_for(
                                self.bot.config_manager.get(interaction.guild.id, "prefix", "!"),
                                timeout=3.0
                            )
                    except Exception as e:
                        # Log the error for debugging with more detail
                        import traceback
                        print(f"Error getting prefix: {e}")
                        print(f"Traceback: {traceback.format_exc()}")
                        prefix = "!"
                
                description = cat_data['description']
                
                embed = discord.Embed(
                    title=f"{cat_data['emoji']} {category_title} Commands",
                    description=f"```{description}```",
                    color=discord.Color.blue()
                )
                
                # Add prefix info for moderation as a separate field
                if category_title == "Moderation":
                    embed.add_field(
                        name="Current Server Prefix",
                        value=f"`{prefix}`",
                        inline=False
                    )

                for cmd_name, cmd_desc in cat_data["commands"].items():
                    field_name = f"/{cmd_name}"
                    if category_title == "Moderation":
                        field_name += f" or {prefix}{cmd_name}"
                    
                    embed.add_field(
                        name=field_name,
                        value=f"```{cmd_desc}```",
                        inline=False
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="📚 Command Categories",
                description=(
                    "Here’s a list of all categories. Use:\n"
                    "```/help category:<category>``` → to see commands\n"
                    "```/help command:<command>``` → for detailed command usage"
                ),
                color=discord.Color.blue()
            )

            for cat_name, cat_data in self.command_categories.items():
                embed.add_field(
                    name=f"{cat_data['emoji']} {cat_name}",
                    value=(
                        f"```{cat_data['description']}```\n"
                        f"Commands: ```{len(cat_data['commands'])}```\n"
                        f"Example: ```/{next(iter(cat_data['commands']))}```"
                    ),
                    inline=False
                )

            if interaction.guild is not None and self.bot.user:
                embed.set_footer(
                    text="Use /help category:<category> for more info",
                    icon_url=self.bot.user.display_avatar.url
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while showing help. Please try again.",
                ephemeral=True
            )
            if hasattr(self.bot, "log"):
                self.bot.log.error(f"Error in help command: {str(e)}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
