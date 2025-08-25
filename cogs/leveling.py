import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
import logging
from datetime import datetime, timedelta
import random
import asyncio

class LevelingCog(commands.Cog):
    """XP and leveling system with role rewards"""

    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.leveling")
        # XP cooldown cache: guild_id -> user_id -> last_xp_gain
        self._xp_cooldowns: Dict[int, Dict[int, datetime]] = {}
        # Default settings
        self.default_settings = {
            'min_xp': 15,
            'max_xp': 25,
            'cooldown': 60,  # seconds
            'level_multiplier': 100,  # XP needed = level * multiplier
            'message_length': 5,  # minimum message length for XP
            'announcement_channel': None,
            'level_up_dm': False,
            'ignore_channels': [],
            'enabled': True
        }

    def _calculate_level(self, xp: int, multiplier: int = 100) -> int:
        """Calculate level based on XP"""
        level = 0
        while xp >= level * multiplier:
            xp -= level * multiplier
            level += 1
        return level - 1 if level > 0 else 0

    def _calculate_needed_xp(self, level: int, multiplier: int = 100) -> int:
        """Calculate XP needed for next level"""
        return level * multiplier

    async def _handle_level_up(
        self,
        member: discord.Member,
        channel: discord.TextChannel,
        old_level: int,
        new_level: int
    ) -> None:
        """Handle level up events and rewards"""
        try:
            settings = await self.bot.db.get_feature_settings(member.guild.id, "leveling") or self.default_settings

            # Get level roles
            level_roles = await self.bot.db.get_level_roles(member.guild.id)
            roles_to_add = []
            roles_to_remove = []

            for level, role_id in level_roles.items():
                role = member.guild.get_role(role_id)
                if not role:
                    continue

                if int(level) <= new_level:
                    if role not in member.roles:
                        roles_to_add.append(role)
                else:
                    if role in member.roles:
                        roles_to_remove.append(role)

            # Apply role changes
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Level up reward")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Level requirement not met")

            # Send level up message
            level_up_message = (
                f"🎉 Congratulations {member.mention}!\n"
                f"You've reached level **{new_level}**"
            )

            if roles_to_add:
                level_up_message += f"\nNew role{'s' if len(roles_to_add) > 1 else ''} earned: " + \
                                  ", ".join(role.mention for role in roles_to_add)

            # Determine where to send the message
            if settings.get('announcement_channel'):
                try:
                    announce_channel = member.guild.get_channel(settings['announcement_channel'])
                    if announce_channel:
                        await announce_channel.send(level_up_message)
                        return
                except Exception as e:
                    self.log.error(f"Error sending to announcement channel: {e}")

            if settings.get('level_up_dm'):
                try:
                    await member.send(level_up_message)
                except discord.Forbidden:
                    await channel.send(level_up_message)
            else:
                await channel.send(level_up_message)

        except Exception as e:
            self.log.error(f"Error handling level up: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        if not message.guild or message.author.bot:
            return

        # Initialize cooldown cache for guild if needed
        if message.guild.id not in self._xp_cooldowns:
            self._xp_cooldowns[message.guild.id] = {}

        try:
            # Get leveling settings
            settings = await self.bot.db.get_feature_settings(message.guild.id, "leveling") or self.default_settings
            if not settings.get('enabled'):
                return

            # Check cooldown
            user_cooldown = self._xp_cooldowns[message.guild.id].get(message.author.id)
            if user_cooldown and datetime.utcnow() - user_cooldown < timedelta(seconds=settings['cooldown']):
                return

            # Check message length and ignored channels
            if len(message.content) < settings['message_length'] or \
               message.channel.id in settings.get('ignore_channels', []):
                return

            # Calculate XP gain
            xp_gain = random.randint(settings['min_xp'], settings['max_xp'])

            # Get current XP and level
            current_data = await self.bot.db.get_xp(message.guild.id, message.author.id)
            current_xp = current_data.get('xp', 0)
            current_level = current_data.get('level', 0)

            # Add XP
            new_xp = current_xp + xp_gain
            new_level = self._calculate_level(new_xp, settings['level_multiplier'])

            # Update database
            await self.bot.db.add_xp(
                message.guild.id,
                message.author.id,
                xp_gain
            )

            # Update cooldown
            self._xp_cooldowns[message.guild.id][message.author.id] = datetime.utcnow()

            # Handle level up
            if new_level > current_level:
                await self._handle_level_up(
                    message.author,
                    message.channel,
                    current_level,
                    new_level
                )

        except Exception as e:
            self.log.error(f"Error processing XP gain: {e}", exc_info=True)

    @app_commands.command(name="rank")
    @app_commands.describe(user="User to check rank for")
    async def check_rank(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Check your or another user's rank and XP"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        target = user or interaction.user

        try:
            # Get user's XP data
            data = await self.bot.db.get_xp(interaction.guild.id, target.id)
            if not data:
                return await interaction.response.send_message(
                    f"{target.mention} hasn't earned any XP yet!",
                    ephemeral=True
                )

            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "leveling") or self.default_settings

            # Calculate progress to next level
            current_level = data['level']
            total_xp = data['xp']
            next_level_xp = self._calculate_needed_xp(current_level + 1, settings['level_multiplier'])
            current_level_xp = self._calculate_needed_xp(current_level, settings['level_multiplier'])
            level_progress = total_xp - current_level_xp
            level_needed = next_level_xp - current_level_xp

            # Create progress bar
            progress = level_progress / level_needed if level_needed > 0 else 1
            bar_length = 20
            filled = int(bar_length * progress)
            progress_bar = '█' * filled + '░' * (bar_length - filled)

            # Create embed
            embed = discord.Embed(
                title=f"Rank for {target.display_name}",
                color=target.color or discord.Color.blue()
            )

            embed.add_field(
                name="Level",
                value=str(current_level),
                inline=True
            )
            embed.add_field(
                name="Total XP",
                value=f"{total_xp:,}",
                inline=True
            )
            embed.add_field(
                name="Messages",
                value=f"{data.get('message_count', 0):,}",
                inline=True
            )
            embed.add_field(
                name=f"Progress to Level {current_level + 1}",
                value=f"`{progress_bar}` {level_progress:,}/{level_needed:,} XP ({progress:.1%})",
                inline=False
            )

            embed.set_thumbnail(url=target.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            self.log.error(f"Error checking rank: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while checking rank.",
                ephemeral=True
            )

    @app_commands.command(name="leaderboard")
    @app_commands.describe(page="Page number to view")
    async def show_leaderboard(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = 1
    ):
        """View the server's XP leaderboard"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Validate page number
            if page < 1:
                page = 1

            # Get leaderboard data
            per_page = 10
            offset = (page - 1) * per_page
            leaderboard = await self.bot.db.get_top_users(
                interaction.guild.id,
                limit=per_page,
                offset=offset
            )

            if not leaderboard:
                return await interaction.response.send_message(
                    "No XP data found!",
                    ephemeral=True
                )

            # Create embed
            embed = discord.Embed(
                title=f"🏆 XP Leaderboard - {interaction.guild.name}",
                color=discord.Color.gold()
            )

            # Add leaderboard entries
            for idx, entry in enumerate(leaderboard, start=offset + 1):
                member = interaction.guild.get_member(entry['user_id'])
                if not member:
                    continue

                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, "")
                embed.add_field(
                    name=f"{medal} #{idx} - {member.display_name}",
                    value=f"Level: {entry['level']} | XP: {entry['xp']:,}",
                    inline=False
                )

            embed.set_footer(text=f"Page {page}")
            embed.timestamp = datetime.utcnow()

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            self.log.error(f"Error showing leaderboard: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while fetching the leaderboard.",
                ephemeral=True
            )

    @app_commands.command(name="levelrole")
    @app_commands.describe(
        level="Level required for the role",
        role="Role to award at the specified level"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def set_level_role(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role
    ):
        """Set a role reward for reaching a specific level"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Validate level
            if level < 0:
                return await interaction.response.send_message(
                    "Level must be positive!",
                    ephemeral=True
                )

            # Verify bot permissions
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.send_message(
                    "I don't have permission to manage roles!",
                    ephemeral=True
                )

            # Verify role hierarchy
            if role.position >= interaction.guild.me.top_role.position:
                return await interaction.response.send_message(
                    "I can't assign roles that are higher than my highest role!",
                    ephemeral=True
                )

            # Save level role
            await self.bot.db.set_level_role(
                interaction.guild.id,
                level,
                role.id
            )

            await interaction.response.send_message(
                f"✅ {role.mention} will now be awarded at level {level}",
                ephemeral=True
            )

        except Exception as e:
            self.log.error(f"Error setting level role: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while setting the level role.",
                ephemeral=True
            )

    @app_commands.command(name="levelconfig")
    @app_commands.describe(
        min_xp="Minimum XP per message",
        max_xp="Maximum XP per message",
        cooldown="Cooldown between XP gains (seconds)",
        multiplier="XP multiplier for level calculation",
        announcement_channel="Channel for level up announcements",
        dm_announcements="Send level up messages in DMs",
        enabled="Enable or disable the leveling system"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def configure_leveling(
        self,
        interaction: discord.Interaction,
        min_xp: Optional[int] = None,
        max_xp: Optional[int] = None,
        cooldown: Optional[int] = None,
        multiplier: Optional[int] = None,
        announcement_channel: Optional[discord.TextChannel] = None,
        dm_announcements: Optional[bool] = None,
        enabled: Optional[bool] = None
    ):
        """Configure the leveling system"""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )

        try:
            # Get current settings
            settings = await self.bot.db.get_feature_settings(interaction.guild.id, "leveling") or self.default_settings.copy()

            # Update settings
            if min_xp is not None:
                if min_xp < 0:
                    return await interaction.response.send_message(
                        "Minimum XP must be positive!",
                        ephemeral=True
                    )
                settings['min_xp'] = min_xp

            if max_xp is not None:
                if max_xp < settings['min_xp']:
                    return await interaction.response.send_message(
                        "Maximum XP must be greater than minimum XP!",
                        ephemeral=True
                    )
                settings['max_xp'] = max_xp

            if cooldown is not None:
                if cooldown < 0:
                    return await interaction.response.send_message(
                        "Cooldown must be positive!",
                        ephemeral=True
                    )
                settings['cooldown'] = cooldown

            if multiplier is not None:
                if multiplier < 1:
                    return await interaction.response.send_message(
                        "Multiplier must be at least 1!",
                        ephemeral=True
                    )
                settings['level_multiplier'] = multiplier

            if announcement_channel is not None:
                settings['announcement_channel'] = announcement_channel.id

            if dm_announcements is not None:
                settings['level_up_dm'] = dm_announcements

            if enabled is not None:
                settings['enabled'] = enabled

            # Save settings
            await self.bot.db.update_feature_settings(
                interaction.guild.id,
                "leveling",
                settings
            )

            # Create response embed
            embed = discord.Embed(
                title="⚙️ Leveling System Configuration",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Status",
                value="✅ Enabled" if settings['enabled'] else "❌ Disabled",
                inline=True
            )
            embed.add_field(
                name="XP Range",
                value=f"{settings['min_xp']} - {settings['max_xp']} XP",
                inline=True
            )
            embed.add_field(
                name="Cooldown",
                value=f"{settings['cooldown']} seconds",
                inline=True
            )
            embed.add_field(
                name="Level Multiplier",
                value=str(settings['level_multiplier']),
                inline=True
            )
            embed.add_field(
                name="Announcements",
                value=f"Channel: {f'<#{settings['announcement_channel']}>' if settings.get('announcement_channel') else 'Same Channel'}\nDM: {'Yes' if settings['level_up_dm'] else 'No'}",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            self.log.error(f"Error configuring leveling: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while updating leveling settings.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))