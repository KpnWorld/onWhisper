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
                    title=f"Command: /{command}",
                    description=cmd.description or "No description available.",
                    color=discord.Color.blue()
                )

                for cat in self.command_categories.values():
                    if command in cat["commands"]:
                        embed.add_field(
                            name="Usage",
                            value=cat["commands"][command],
                            inline=False
                        )

                if hasattr(cmd, "parameters"):
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
                embed = discord.Embed(
                    title=f"{cat_data['emoji']} {category_title} Commands",
                    description=cat_data["description"],
                    color=discord.Color.blue()
                )

                for cmd_name, cmd_desc in cat_data["commands"].items():
                    embed.add_field(
                        name=f"/{cmd_name}",
                        value=cmd_desc,
                        inline=False
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="📚 Command Categories",
                description=(
                    "Welcome to the help menu! Here are all available command categories.\n"
                    "Use `/help category:<category>` to see commands in each category.\n"
                    "Use `/help command:<command>` to see detailed command usage."
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

            if interaction.guild is not None and self.bot.user:
                embed.set_footer(
                    text="Type /help <category> for more info",
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
