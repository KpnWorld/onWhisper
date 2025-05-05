import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional

class InfoCog(commands.Cog):
    """Information commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="info")
    @app_commands.describe(
        action="The type of information to show",
        user="The user to get information about (only for 'user' action)",
        role="The role to get information about (only for 'role' action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Bot Information", value="bot"),
        app_commands.Choice(name="Server Information", value="server"),
        app_commands.Choice(name="User Information", value="user"),
        app_commands.Choice(name="Role Information", value="role"),
        app_commands.Choice(name="Bot Uptime", value="uptime")
    ])
    async def info(
        self,
        interaction: discord.Interaction,
        action: str,
        user: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None
    ):
        """Get information about various aspects of the server and bot"""
        try:
            if action == "bot":
                await self._show_bot_info(interaction)
            elif action == "server":
                await self._show_server_info(interaction)
            elif action == "user":
                await self._show_user_info(interaction, user)
            elif action == "role":
                if not role:
                    raise ValueError("You must specify a role to get information about")
                await self._show_role_info(interaction, role)
            elif action == "uptime":
                await self._show_uptime_info(interaction)

        except ValueError as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=self.bot.ui_manager.error_embed("Error", str(e)),
                ephemeral=True
            )

    async def _show_bot_info(self, interaction: discord.Interaction):
        """Show bot information"""
        stats = await self.bot.db_manager.get_bot_stats(self.bot.user.id)
        
        embed = self.bot.ui_manager.info_embed(
            "Bot Information",
            f"Information about {self.bot.user.name}"
        )
        
        embed.add_field(
            name="Statistics",
            value=f"Servers: {len(self.bot.guilds)}\nCommands: {len(self.bot.tree.get_commands())}\nUptime: {self.bot.uptime}",
            inline=False
        )
        
        if stats:
            embed.add_field(
                name="Usage",
                value="\n".join(f"{k}: {v}" for k, v in stats.items()),
                inline=False
            )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def _show_server_info(self, interaction: discord.Interaction):
        """Show server information"""
        guild = interaction.guild
        
        # Get role counts
        role_count = len(guild.roles) - 1  # Exclude @everyone
        emoji_count = len(guild.emojis)
        
        # Get channel counts
        text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        
        embed = self.bot.ui_manager.info_embed(
            f"{guild.name}",
            guild.description or "No description set"
        )
        
        # General info
        embed.add_field(
            name="General",
            value=f"Owner: {guild.owner.mention}\nCreated: {discord.utils.format_dt(guild.created_at, style='R')}\nMembers: {guild.member_count}",
            inline=False
        )
        
        # Channel info
        embed.add_field(
            name="Channels",
            value=f"Text: {text_channels}\nVoice: {voice_channels}",
            inline=True
        )
        
        # Role & emoji info
        embed.add_field(
            name="Other",
            value=f"Roles: {role_count}\nEmojis: {emoji_count}",
            inline=True
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        await interaction.response.send_message(embed=embed)

    async def _show_user_info(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Show user information"""
        member = user or interaction.user
        
        embed = self.bot.ui_manager.info_embed(
            str(member),
            f"Information about {member.mention}"
        )
        
        # Join dates
        embed.add_field(
            name="Joined",
            value=f"Server: {discord.utils.format_dt(member.joined_at, style='R')}\nDiscord: {discord.utils.format_dt(member.created_at, style='R')}",
            inline=False
        )
        
        # Roles
        roles = [role.mention for role in reversed(member.roles[1:])]  # Exclude @everyone
        embed.add_field(
            name=f"Roles [{len(roles)}]",
            value=" ".join(roles) if roles else "No roles",
            inline=False
        )
        
        # XP info if enabled
        xp_data = await self.bot.db_manager.get_user_level_data(interaction.guild_id, member.id)
        if xp_data:
            embed.add_field(
                name="XP",
                value=f"Level: {xp_data.get('level', 0)}\nXP: {xp_data.get('xp', 0)}",
                inline=True
            )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def _show_role_info(self, interaction: discord.Interaction, role: discord.Role):
        """Show role information"""
        embed = self.bot.ui_manager.info_embed(
            role.name,
            "Role information"
        )
        
        embed.add_field(
            name="General",
            value=f"ID: {role.id}\nColor: {role.color}\nPosition: {role.position}\nMentionable: {role.mentionable}\nHoisted: {role.hoist}",
            inline=False
        )
        
        # Get member count
        member_count = len(role.members)
        embed.add_field(
            name="Members",
            value=str(member_count),
            inline=True
        )
        
        # Show if it's a special role
        special_roles = []
        color_roles = await self.bot.db_manager.get_color_roles(interaction.guild_id)
        level_roles = await self.bot.db_manager.get_section(interaction.guild_id, 'level_roles')
        
        if str(role.id) in color_roles:
            special_roles.append("Color Role")
            
        if level_roles and str(role.id) in level_roles.values():
            level = next(k for k, v in level_roles.items() if v == str(role.id))
            special_roles.append(f"Level {level} Reward")
            
        if special_roles:
            embed.add_field(
                name="Special",
                value="\n".join(special_roles),
                inline=True
            )
        
        embed.colour = role.color
        await interaction.response.send_message(embed=embed)

    async def _show_uptime_info(self, interaction: discord.Interaction):
        """Show bot uptime"""
        embed = self.bot.ui_manager.info_embed(
            "Bot Uptime",
            f"Online since {discord.utils.format_dt(self.bot.start_time, style='R')}"
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))