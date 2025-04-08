import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import logging
from typing import Literal, Dict
from datetime import datetime, timedelta

# Initialize logger
logger = logging.getLogger(__name__)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use bot's database instance instead of creating new one
        self.xp_cooldowns: Dict[int, Dict[int, datetime]] = {}
        self.cooldown_settings = {}
        self.xp_ranges = {}
        self._cleanup_task = bot.loop.create_task(self._cleanup_cooldowns())
        bot.loop.create_task(self._init_db())
        logger.info("Leveling cog initialized")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _cleanup_cooldowns(self):
        """Periodically clean up expired cooldowns"""
        try:
            while True:
                current_time = datetime.now()
                for guild_id in list(self.xp_cooldowns.keys()):
                    users = self.xp_cooldowns[guild_id]
                    # Remove expired cooldowns
                    expired = [user_id for user_id, end_time in users.items() 
                             if current_time >= end_time]
                    for user_id in expired:
                        del users[user_id]
                    # Remove empty guild entries
                    if not users:
                        del self.xp_cooldowns[guild_id]
                await asyncio.sleep(60)  # Cleanup every minute
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in cooldown cleanup: {e}")

    def is_on_cooldown(self, guild_id: int, user_id: int) -> bool:
        """Check if a user is on XP gain cooldown"""
        if guild_id not in self.xp_cooldowns:
            return False
        if user_id not in self.xp_cooldowns[guild_id]:
            return False
        return datetime.now() < self.xp_cooldowns[guild_id][user_id]

    def add_cooldown(self, guild_id: int, user_id: int, seconds: int):
        """Add a cooldown for a user"""
        if guild_id not in self.xp_cooldowns:
            self.xp_cooldowns[guild_id] = {}
        self.xp_cooldowns[guild_id][user_id] = datetime.now() + timedelta(seconds=seconds)

    async def _init_db(self):
        """Initialize database and load settings asynchronously"""
        try:
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT guild_id, xp_cooldown, min_xp, max_xp
                    FROM leveling_settings
                """)
                rows = await cur.fetchall()
                for guild_id, cooldown, min_xp, max_xp in rows:
                    self.cooldown_settings[guild_id] = cooldown
                    self.xp_ranges[guild_id] = (min_xp, max_xp)

            # Initialize settings for new guilds
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
                async with self.db.cursor() as cur:
                    await cur.execute("""
                        INSERT OR IGNORE INTO leveling_settings 
                        (guild_id, xp_cooldown, min_xp, max_xp)
                        VALUES (?, ?, ?, ?)
                    """, (guild.id, 60, 15, 25))

            logger.info("Leveling system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize leveling system: {e}")
            raise

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed with balanced curve"""
        base_xp = 100
        scaling_factor = 1.2
        acceleration = 1.1
        return int(base_xp * (scaling_factor ** (level - 1)) * (1 + (level * acceleration)))

    def generate_progress_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """Generate a visual progress bar"""
        filled = '█'
        empty = '░'
        progress = current / maximum
        filled_length = int(length * progress)
        bar = filled * filled_length + empty * (length - filled_length)
        return f"`{bar}` ({(progress * 100):.1f}%)"

    def format_timestamp(self, timestamp_str: str) -> str:
        """Convert ISO timestamp to readable format"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            return timestamp_str

    def format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time"""
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        
        days = delta.days
        if days > 365:
            years = days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
        if days > 30:
            months = days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''} ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        minutes = (delta.seconds % 3600) // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    def get_cooldown(self, guild_id: int) -> int:
        """Get guild-specific cooldown or default"""
        return self.cooldown_settings.get(guild_id, 60)

    def get_xp_range(self, guild_id: int) -> tuple[int, int]:
        """Get guild-specific XP range or default"""
        return self.xp_ranges.get(guild_id, (15, 25))

    async def add_xp(self, message, xp_gained: int):
        """Enhanced XP system with message tracking and race condition prevention"""
        user_id = message.author.id
        guild_id = message.guild.id
        timestamp = message.created_at.isoformat()

        async with self.db.cursor() as cur:
            # Use transaction to prevent race conditions
            await cur.execute("BEGIN EXCLUSIVE")
            try:
                # Ensure user settings exist
                await cur.execute("""
                    INSERT OR IGNORE INTO user_settings (user_id, guild_id)
                    VALUES (?, ?)
                """, (user_id, guild_id))

                # Get current XP and level atomically
                await cur.execute("""
                    SELECT xp, level 
                    FROM xp_data 
                    WHERE user_id=? AND guild_id=?
                    FOR UPDATE
                """, (user_id, guild_id))
                result = await cur.fetchone()

                if result:
                    current_xp, current_level = result
                    new_xp = current_xp + xp_gained
                else:
                    current_level = 1
                    new_xp = xp_gained

                # Calculate level ups
                level_changed = False
                while True:
                    xp_needed = self.calculate_xp_for_level(current_level)
                    if new_xp >= xp_needed:
                        current_level += 1
                        new_xp -= xp_needed
                        level_changed = True
                    else:
                        break

                # Update with new values
                await cur.execute("""
                    INSERT INTO xp_data (user_id, guild_id, xp, level, messages, last_message)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET
                        xp = ?,
                        level = ?,
                        messages = messages + 1,
                        last_message = ?
                """, (user_id, guild_id, new_xp, current_level, timestamp,
                      new_xp, current_level, timestamp))

                await cur.execute("COMMIT")
                return (current_level, new_xp, self.calculate_xp_for_level(current_level)) if level_changed else (None, new_xp, xp_needed)

            except Exception:
                await cur.execute("ROLLBACK")
                raise

    @commands.Cog.listener()
    async def on_message(self, message):
        """Enhanced message handler with better XP gains"""
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        if self.is_on_cooldown(guild_id, user_id):
            return

        try:
            min_xp, max_xp = self.get_xp_range(guild_id)
            xp_gained = random.randint(min_xp, max_xp)
            new_level, current_xp, xp_needed = await self.add_xp(message, xp_gained)

            self.add_cooldown(guild_id, user_id, self.get_cooldown(guild_id))

            if new_level:
                embed = discord.Embed(
                    title="🌟 Level Up!",
                    description=f"Congratulations {message.author.mention}!",
                    color=discord.Color.gold()
                )
                
                progress_bar = self.generate_progress_bar(current_xp, xp_needed)
                embed.add_field(
                    name=f"Level {new_level} Achieved!",
                    value=f"XP: {current_xp:,}/{xp_needed:,}\n{progress_bar}",
                    inline=False
                )

                # Get rank and roles in parallel
                rank_task = asyncio.create_task(self._get_user_rank(message.guild.id, new_level, current_xp))
                role_task = asyncio.create_task(self._get_level_role(message.guild.id, new_level))
                
                rank = await rank_task
                role_data = await role_task

                embed.add_field(name="Server Rank", value=f"#{rank}", inline=True)

                if role_data:
                    new_role = message.guild.get_role(role_data)
                    if new_role:
                        try:
                            await message.author.add_roles(new_role)
                            embed.add_field(
                                name="🎭 Role Reward",
                                value=f"You've earned the {new_role.mention} role!",
                                inline=False
                            )
                        except discord.Forbidden:
                            logger.warning(f"Missing permissions to assign role in {message.guild.id}")
                        except Exception as e:
                            logger.error(f"Error assigning level role: {e}")

                await message.channel.send(embed=embed)
                logger.info(f"User {message.author} leveled up to {new_level}")
        except Exception as e:
            logger.error(f"Error in XP processing: {e}")

    async def _get_user_rank(self, guild_id: int, level: int, xp: int) -> int:
        """Get user's rank in an async way"""
        async with self.db.cursor() as cur:
            await cur.execute("""
                SELECT COUNT(*) + 1 FROM xp_data 
                WHERE guild_id = ? AND (
                    level > ? OR (level = ? AND xp > ?)
                )
            """, (guild_id, level, level, xp))
            return (await cur.fetchone())[0]

    async def _get_level_role(self, guild_id: int, level: int) -> int:
        """Get role ID for level in an async way"""
        async with self.db.cursor() as cur:
            await cur.execute("""
                SELECT role_id FROM level_roles 
                WHERE guild_id = ? AND level = ?
            """, (guild_id, level))
            result = await cur.fetchone()
            return result[0] if result else None

    @app_commands.command(name="level", description="Check your current level and XP")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        """Display level and XP information for a user"""
        try:
            await interaction.response.defer()
            member = member or interaction.user

            async with self.db.cursor() as cur:
                # First get user data
                await cur.execute("""
                    SELECT xp, level, messages, last_message 
                    FROM xp_data 
                    WHERE user_id=? AND guild_id=?
                """, (member.id, interaction.guild.id))
                user_data = await cur.fetchone()

                if user_data:
                    xp, level, messages, last_message = user_data
                    # Get user rank
                    await cur.execute("""
                        SELECT COUNT(*) + 1 FROM xp_data 
                        WHERE guild_id = ? AND (
                            level > ? OR (level = ? AND xp > ?)
                        )
                    """, (interaction.guild.id, level, level, xp))
                    rank = (await cur.fetchone())[0]

                    next_level_xp = self.calculate_xp_for_level(level)
                    next_level = level + 1
                    remaining_xp = next_level_xp - xp

                    embed = discord.Embed(
                        title=f"📊 Level Stats: {member.display_name}",
                        color=member.color if member.color != discord.Color.default() else discord.Color.blue()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)

                    # Core Stats
                    core_stats = (
                        f"Level: {level}\n"
                        f"Rank: #{rank:,}\n"
                        f"Messages: {messages:,}"
                    )
                    embed.add_field(
                        name="📈 Statistics",
                        value=f"```\n{core_stats}\n```",
                        inline=False
                    )

                    # XP Progress
                    progress = self.generate_progress_bar(xp, next_level_xp)
                    xp_stats = (
                        f"Current XP: {xp:,}\n"
                        f"XP to next level: {remaining_xp:,}\n"
                        f"Progress: {progress}"
                    )
                    embed.add_field(
                        name="🔋 XP Progress",
                        value=f"```\n{xp_stats}\n```",
                        inline=False
                    )

                    # Last Active
                    if last_message:
                        try:
                            last_msg_dt = datetime.fromisoformat(last_message.replace('Z', '+00:00'))
                            relative_time = self.format_relative_time(last_msg_dt)
                            embed.set_footer(text=f"Last active: {relative_time}")
                        except (ValueError, AttributeError):
                            pass

                else:
                    embed = discord.Embed(
                        title=f"{member.display_name}'s Level Stats",
                        description="No XP gained yet! Start chatting to earn experience.",
                        color=discord.Color.blue()
                    )

            await interaction.followup.send(embed=embed)
            logger.info(f"Level command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in level command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching level information.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="View the XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Display the server's XP leaderboard"""
        try:
            await interaction.response.defer()
            
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT user_id, xp, level, messages 
                    FROM xp_data 
                    WHERE guild_id = ? 
                    ORDER BY level DESC, xp DESC 
                    LIMIT 10
                """, (interaction.guild.id,))
                top_users = await cur.fetchall()

                # Get total ranked users
                await cur.execute("""
                    SELECT COUNT(*) FROM xp_data WHERE guild_id = ?
                """, (interaction.guild.id,))
                total_ranked = (await cur.fetchone())[0]

                # Get user's rank and stats
                await cur.execute("""
                    SELECT COUNT(*) + 1
                    FROM xp_data 
                    WHERE guild_id = ? AND (
                        level > (SELECT level FROM xp_data WHERE user_id = ? AND guild_id = ?)
                        OR (level = (SELECT level FROM xp_data WHERE user_id = ? AND guild_id = ?) 
                            AND xp > (SELECT xp FROM xp_data WHERE user_id = ? AND guild_id = ?))
                    )
                """, (interaction.guild.id, interaction.user.id, interaction.guild.id,
                      interaction.user.id, interaction.guild.id, interaction.user.id,
                      interaction.guild.id))
                user_rank = (await cur.fetchone())[0]

            if not top_users:
                await interaction.followup.send("No leaderboard data yet! Start chatting to earn XP.")
                return

            embed = discord.Embed(
                title=f"📊 Server Leaderboard",
                description=f"Top 10 out of {total_ranked:,} ranked users",
                color=discord.Color.blue()
            )

            # Generate leaderboard text
            leaderboard_text = []
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            
            for idx, (user_id, xp, level, messages) in enumerate(top_users, 1):
                user = interaction.guild.get_member(user_id)
                if user:
                    medal = medals.get(idx, "•")
                    leaderboard_text.append(
                        f"{medal} {user.name}\n"
                        f"Level {level} | {xp:,} XP"
                    )

            if leaderboard_text:
                embed.add_field(
                    name="📈 Rankings",
                    value=f"```\n{'\n\n'.join(leaderboard_text)}\n```",
                    inline=False
                )

            # User's Rank
            if user_rank > 10:
                embed.set_footer(text=f"Your Rank: #{user_rank}")

            await interaction.followup.send(embed=embed)
            logger.info(f"Leaderboard command used by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching the leaderboard.", ephemeral=True)

    @app_commands.command(name="setlevelrole", description="Set a role to be assigned at a specific level (Admin only).")
    @commands.has_permissions(administrator=True)
    async def setlevelrole(self, interaction: discord.Interaction, level: int, role: discord.Role):
        try:
            # Add level validation
            if level < 1:
                await interaction.response.send_message(
                    "❌ Level must be greater than 0!", 
                    ephemeral=True
                )
                return

            # Check role hierarchy
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "❌ I cannot assign roles higher than my highest role!",
                    ephemeral=True
                )
                return

            # Check if role is managed by integration
            if role.managed:
                await interaction.response.send_message(
                    "❌ Cannot use roles managed by integrations!",
                    ephemeral=True
                )
                return

            async with self.db.cursor() as cur:
                # Get existing roles to check hierarchy
                await cur.execute("""
                    SELECT role_id FROM level_roles 
                    WHERE guild_id = ? AND level <= ?
                    ORDER BY level DESC
                """, (interaction.guild.id, level))
                existing_roles = await cur.fetchall()

                # Insert new role
                await cur.execute(
                    "INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)", 
                    (interaction.guild.id, level, role.id)
                )

            # Create the details text separately to avoid f-string/backtick issues            
            details = (
                f"Level: {level}\n"
                f"Role: {role.mention}\n"
                f"Members Eligible: {len([m for m in interaction.guild.members if m.guild_permissions.administrator])}"
            )

            # Create and send embed
            embed = discord.Embed(
                title="⚙️ Level Role Configuration",
                description="Role reward settings have been updated.",
                color=discord.Color.blue()
            )
            
            # Add field with proper formatting
            embed.add_field(
                name="Details",
                value=f"```\n{details}\n```",
                inline=False
            )
            embed.set_footer(text="Administrative Command • Level Rewards System")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Level role set: Level {level} -> Role {role.name} ({role.id})")
        except Exception as e:
            logger.error(f"Error setting level role: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to set level role configuration.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(name="deletelevelrole", description="Remove a level role assignment (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def deletelevelrole(self, interaction: discord.Interaction, level: int):
        """Remove a role assignment for a specific level"""
        try:
            async with self.db.cursor() as cur:
                # Check if a role exists for this level
                await cur.execute("""
                    SELECT role_id FROM level_roles
                    WHERE guild_id = ? AND level = ?
                """, (interaction.guild.id, level))
                result = await cur.fetchone()

                if not result:
                    await interaction.response.send_message(f"❌ No role is assigned to level {level}.", ephemeral=True)
                    return

                # Delete the level role assignment
                await cur.execute("""
                    DELETE FROM level_roles
                    WHERE guild_id = ? AND level = ?
                """, (interaction.guild.id, level))

                await interaction.response.send_message(f"✅ Successfully removed the role assignment for level {level}.", ephemeral=True)
                logger.info(f"Level role removed for level {level} in guild {interaction.guild.id}")
        except Exception as e:
            logger.error(f"Error removing level role: {e}")
            await interaction.response.send_message("❌ An error occurred while removing the level role.", ephemeral=True)

    @app_commands.command(name="setcooldown", description="Set the XP gain cooldown time")
    @app_commands.default_permissions(administrator=True)
    async def setcooldown(self, interaction: discord.Interaction, time: Literal["15s", "30s", "1m", "2m", "5m"]):
        try:
            cooldown_map = {
                "15s": 15,
                "30s": 30,
                "1m": 60,
                "2m": 120,
                "5m": 300
            }
            
            guild_id = interaction.guild.id
            old_cooldown = self.get_cooldown(guild_id)
            seconds = cooldown_map[time]
            
            async with self.db.cursor() as cur:
                await cur.execute("""
                    INSERT OR REPLACE INTO leveling_settings (guild_id, xp_cooldown)
                    VALUES (?, ?)
                """, (guild_id, seconds))
            
            self.cooldown_settings[guild_id] = seconds
            
            embed = discord.Embed(
                title="⚙️ XP System Configuration",
                description="Cooldown settings have been updated.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Previous Setting",
                value=f"```\nCooldown: {old_cooldown} seconds```",
                inline=True
            )
            embed.add_field(
                name="New Setting",
                value=f"```\nCooldown: {seconds} seconds```",
                inline=True
            )
            embed.add_field(
                name="Effect",
                value="This change affects how frequently users can gain XP from messages.",
                inline=False
            )
            embed.set_footer(text="Administrative Command • XP System Settings")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"XP cooldown changed to {seconds}s by {interaction.user} in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to update XP cooldown settings.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(name="setxprange", description="Set the XP range for message rewards")
    @app_commands.describe(
        min_xp="Minimum XP per message (1-100)",
        max_xp="Maximum XP per message (1-100)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setxprange(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        try:
            if not 1 <= min_xp <= 100 or not 1 <= max_xp <= 100:
                await interaction.response.send_message(
                    "❌ XP values must be between 1 and 100!",
                    ephemeral=True
                )
                return

            if min_xp > max_xp:
                await interaction.response.send_message(
                    "❌ Minimum XP cannot be greater than maximum XP!",
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            old_min, old_max = self.get_xp_range(guild_id)

            # Update database with new XP range
            async with self.db.cursor() as cur:
                await cur.execute("""
                    UPDATE leveling_settings 
                    SET min_xp = ?, max_xp = ?
                    WHERE guild_id = ?
                """, (min_xp, max_xp, guild_id))

            # Update cache
            self.xp_ranges[guild_id] = (min_xp, max_xp)

            embed = discord.Embed(
                title="⚙️ XP Range Configuration",
                description="Message reward settings have been updated.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Previous Setting",
                value=f"```\nMin XP: {old_min}\nMax XP: {old_max}\n```",
                inline=True
            )
            embed.add_field(
                name="New Setting",
                value=f"```\nMin XP: {min_xp}\nMax XP: {max_xp}\n```",
                inline=True
            )
            embed.add_field(
                name="Effect",
                value="This change affects how much XP users gain from each message.",
                inline=False
            )
            embed.set_footer(text="Administrative Command • XP System Settings")

            await interaction.response.send_message(embed=embed)
            logger.info(f"XP range updated in {interaction.guild.name}: {min_xp}-{max_xp}")
        except Exception as e:
            logger.error(f"Error setting XP range: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while updating XP range settings.",
                ephemeral=True
            )

    @app_commands.command(name="levelconfig", description="Show current leveling system configuration")
    @app_commands.default_permissions(administrator=True)
    async def levelconfig(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            embed = discord.Embed(
                title="⚙️ Leveling System Configuration",
                description="Current settings for this server",
                color=discord.Color.blue()
            )

            # Get current cooldown and XP range from cache
            cooldown = self.get_cooldown(interaction.guild.id)
            min_xp, max_xp = self.get_xp_range(interaction.guild.id)

            # XP Settings
            embed.add_field(
                name="⏱️ XP Gain Settings",
                value=f"```\nCooldown: {cooldown} seconds\nXP per message: {min_xp}-{max_xp}\n```",
                inline=False
            )

            # Get level-up message and channel
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT level_up_message, level_up_channel_id
                    FROM leveling_settings
                    WHERE guild_id = ?
                """, (interaction.guild.id,))
                level_up_settings = await cur.fetchone()
                
            if level_up_settings:
                message, channel_id = level_up_settings
                channel = f"<#{channel_id}>" if channel_id else "Same channel"
                embed.add_field(
                    name="📢 Level Up Settings",
                    value=f"```\nMessage: {message}\nChannel: {channel}\n```",
                    inline=False
                )

            # Get level roles
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT level, role_id
                    FROM level_roles
                    WHERE guild_id = ?
                    ORDER BY level ASC
                """, (interaction.guild.id,))
                level_roles = await cur.fetchall()

            if level_roles:
                roles_text = []
                for level, role_id in level_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        roles_text.append(f"Level {level}: {role.mention}")
                
                embed.add_field(
                    name="🎭 Level Role Rewards",
                    value="\n".join(roles_text),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎭 Level Role Rewards",
                    value="No role rewards configured",
                    inline=False
                )

            # Add XP curve information
            example_levels = [1, 5, 10, 20, 50]
            xp_info = []
            for level in example_levels:
                xp_needed = self.calculate_xp_for_level(level)
                xp_info.append(f"Level {level}: {xp_needed:,} XP")

            embed.add_field(
                name="📈 XP Requirements",
                value="```\n" + "\n".join(xp_info) + "\n```",
                inline=False
            )

            # Server Statistics
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(*), AVG(CAST(level AS FLOAT)), MAX(level)
                    FROM xp_data
                    WHERE guild_id = ?
                """, (interaction.guild.id,))
                user_count, avg_level, max_level = await cur.fetchone()

            if user_count:
                # Format average level properly outside of f-string
                avg_level_str = f"{avg_level:.1f}" if avg_level else "0.0"
                stats = (
                    f"Users tracked: {int(user_count) if user_count else 0}\n"
                    f"Average level: {avg_level_str}\n"
                    f"Highest level: {int(max_level) if max_level else 0}"
                )
                embed.add_field(
                    name="📊 Server Statistics",
                    value=f"```\n{stats}\n```",
                    inline=False
                )

            embed.set_footer(text="Administrative Command • Leveling System")
            await interaction.followup.send(embed=embed)
            logger.info(f"Level config displayed for {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error showing level config: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching the configuration.",
                ephemeral=True
            )

    @app_commands.command(name="togglexp", description="Toggle XP notifications")
    async def togglexp(self, interaction: discord.Interaction):
        """Toggle XP gain notifications for the user"""
        try:
            async with self.db.cursor() as cur:
                # Get current setting
                await cur.execute("""
                    SELECT notifications_enabled 
                    FROM user_settings 
                    WHERE user_id = ? AND guild_id = ?
                """, (interaction.user.id, interaction.guild.id))
                result = await cur.fetchone()
                
                enabled = not (result and result[0]) if result else False
                
                # Update setting
                await cur.execute("""
                    INSERT INTO user_settings (user_id, guild_id, notifications_enabled)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET notifications_enabled = ?
                """, (interaction.user.id, interaction.guild.id, enabled, enabled))

            status = "enabled" if enabled else "disabled"
            await interaction.response.send_message(
                f"✅ XP notifications {status}!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user} {status} XP notifications")
        except Exception as e:
            logger.error(f"Error toggling XP notifications: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while updating your preferences.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Leveling(bot))
