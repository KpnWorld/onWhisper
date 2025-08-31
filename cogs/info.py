# cogs/info.py

import logging
from typing import Literal, Optional
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

class InfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.version = bot.__dict__.get("version", "1.0.0")

    @app_commands.command(name="info", description="Display various information")
    @app_commands.describe(type="Choose the type of information to display")
    async def info(
        self,
        interaction: discord.Interaction,
        type: Literal["server", "bot", "role", "channel", "user"],
        role: Optional[discord.Role] = None,
        channel: Optional[discord.TextChannel] = None,
        user: Optional[discord.Member] = None,
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            embed = None

            if type == "server":
                embed = await self._server_info(interaction.guild)
            elif type == "bot":
                embed = await self._bot_info()
            elif type == "role":
                if not role:
                    raise ValueError("You must select a role for type 'role'.")
                embed = await self._role_info(role)
            elif type == "channel":
                if not channel:
                    raise ValueError("You must select a text channel for type 'channel'.")
                embed = await self._channel_info(channel)
            elif type == "user":
                member = user or interaction.user
                if not isinstance(member, discord.Member):
                    raise ValueError("Invalid user provided.")
                embed = await self._user_info(member)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            log.warning("Missing permissions to send info response.")
            await interaction.followup.send(
                "I don’t have permission to send embeds here.", ephemeral=True
            )
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception:
            log.exception("Error in /info command")
            await interaction.followup.send(
                "An unexpected error occurred.", ephemeral=True
            )

    async def _server_info(self, guild: discord.Guild) -> discord.Embed:
        created = guild.created_at.strftime("%Y-%m-%d %H:%M")
        embed = discord.Embed(
            title=f"📊 Server Information - {guild.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Server ID", value=f"```{guild.id}```", inline=True)
        embed.add_field(name="Owner", value=f"```{guild.owner}```", inline=True)
        embed.add_field(name="Members", value=f"```{guild.member_count}```", inline=True)
        embed.add_field(name="Created", value=f"```{created}```", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        log.info("Generated server info for %s", guild.id)
        return embed

    async def _bot_info(self) -> discord.Embed:
        embed = discord.Embed(title="🤖 Bot Information", color=discord.Color.blurple())
        embed.add_field(name="Name", value=f"```{self.bot.user.name}```", inline=True)
        embed.add_field(name="ID", value=f"```{self.bot.user.id}```", inline=True)
        embed.add_field(name="Version", value=f"```{self.version}```", inline=True)
        embed.add_field(name="Servers", value=f"```{len(self.bot.guilds)}```", inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        log.info("Generated bot info")
        return embed

    async def _role_info(self, role: discord.Role) -> discord.Embed:
        created = role.created_at.strftime("%Y-%m-%d %H:%M")
        perms = ", ".join([name for name, value in role.permissions if value])
        embed = discord.Embed(
            title=f"🎭 Role Information - {role.name}",
            color=role.color
        )
        embed.add_field(name="Role ID", value=f"```{role.id}```", inline=True)
        embed.add_field(name="Members", value=f"```{len(role.members)}```", inline=True)
        embed.add_field(name="Created", value=f"```{created}```", inline=True)
        embed.add_field(name="Color", value=f"```{role.color}```", inline=True)
        embed.add_field(name="Permissions", value=f"```{perms or 'None'}```", inline=False)
        log.info("Generated role info for %s", role.id)
        return embed

    async def _channel_info(self, channel: discord.TextChannel) -> discord.Embed:
        created = channel.created_at.strftime("%Y-%m-%d %H:%M")
        embed = discord.Embed(
            title=f"📺 Channel Information - #{channel.name}",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel ID", value=f"```{channel.id}```", inline=True)
        embed.add_field(
            name="Category",
            value=f"```{channel.category.name if channel.category else 'None'}```",
            inline=True
        )
        embed.add_field(name="Created", value=f"```{created}```", inline=True)
        embed.add_field(
            name="Type",
            value=f"```{channel.type.name.capitalize()}```",
            inline=True
        )
        log.info("Generated channel info for %s", channel.id)
        return embed

    async def _user_info(self, member: discord.Member) -> discord.Embed:
        joined = member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown"
        created = member.created_at.strftime("%Y-%m-%d %H:%M")
        color = member.color if member.color != discord.Color.default() else discord.Color.blue()

        embed = discord.Embed(
            title=f"👤 User Information - {member}",
            color=color
        )
        embed.add_field(name="User ID", value=f"```{member.id}```", inline=True)
        embed.add_field(name="Joined Server", value=f"```{joined}```", inline=True)
        embed.add_field(name="Created Account", value=f"```{created}```", inline=True)
        embed.add_field(name="Top Role", value=f"```{member.top_role.name}```", inline=True)
        embed.add_field(name="Bot", value=f"```{member.bot}```", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        log.info("Generated user info for %s", member.id)
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))
