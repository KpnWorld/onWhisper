# cogs/info.py

import logging
from typing import Literal

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
        target: discord.Role | discord.TextChannel | discord.Member | None = None,
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            embed = None

            if type == "server":
                embed = await self._server_info(interaction.guild)
            elif type == "bot":
                embed = await self._bot_info()
            elif type == "role":
                if not isinstance(target, discord.Role):
                    raise ValueError("You must select a role.")
                embed = await self._role_info(target)
            elif type == "channel":
                if not isinstance(target, discord.TextChannel):
                    raise ValueError("You must select a text channel.")
                embed = await self._channel_info(target)
            elif type == "user":
                member = target or interaction.user
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
        embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.blue())
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        log.info("Generated server info for %s", guild.id)
        return embed

    async def _bot_info(self) -> discord.Embed:
        embed = discord.Embed(title="Bot Info", color=discord.Color.blurple())
        embed.add_field(name="Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="Version", value=self.version, inline=True)
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        log.info("Generated bot info")
        return embed

    async def _role_info(self, role: discord.Role) -> discord.Embed:
        embed = discord.Embed(title=f"Role Info - {role.name}", color=role.color)
        embed.add_field(name="Role ID", value=role.id, inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Created", value=role.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        perms = ", ".join([p for p, v in role.permissions if v])
        embed.add_field(name="Permissions", value=perms or "None", inline=False)
        log.info("Generated role info for %s", role.id)
        return embed

    async def _channel_info(self, channel: discord.TextChannel) -> discord.Embed:
        embed = discord.Embed(title=f"Channel Info - #{channel.name}", color=discord.Color.green())
        embed.add_field(name="Channel ID", value=channel.id, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="Created", value=channel.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="NSFW", value=str(channel.is_nsfw()), inline=True)
        log.info("Generated channel info for %s", channel.id)
        return embed

    async def _user_info(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=f"User Info - {member}", color=member.color if member.color.value else discord.Color.blue())
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Created Account", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Top Role", value=member.top_role.name, inline=True)
        embed.add_field(name="Bot", value=str(member.bot), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        log.info("Generated user info for %s", member.id)
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))
