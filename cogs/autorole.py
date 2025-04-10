from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import logging
from cogs.info import format_relative_time
from utils.db_manager import DatabaseManager
from utils.ui_manager import UIManager
import asyncio

# Initialize logger
logger = logging.getLogger(__name__)

# Define role type choices
ROLE_TYPES = [
    app_commands.Choice(name="Member", value="member"),
    app_commands.Choice(name="Bot", value="bot"),
    app_commands.Choice(name="All", value="all")
]

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.ui = UIManager()
        self._role_queue = asyncio.Queue()
        self._role_task = bot.loop.create_task(self._process_role_queue())
        bot.loop.create_task(self._init_db())
        logger.info("AutoRole cog initialized")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._role_task:
            self._role_task.cancel()

    async def _init_db(self):
        """Initialize database tables and indexes"""
        try:
            async with self.db.transaction():
                await self.db.execute_script("""
                    CREATE TABLE IF NOT EXISTS autorole_settings (
                        guild_id INTEGER PRIMARY KEY,
                        role_ids TEXT,
                        enabled BOOLEAN DEFAULT 1,
                        delay INTEGER DEFAULT 0,
                        require_verification BOOLEAN DEFAULT 0,
                        exclude_bots BOOLEAN DEFAULT 1,
                        temporary_duration INTEGER,
                        log_channel_id INTEGER,
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS autorole_logs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        role_id INTEGER,
                        success BOOLEAN,
                        error TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_autorole_logs_guild 
                    ON autorole_logs(guild_id);
                    
                    CREATE INDEX IF NOT EXISTS idx_autorole_logs_time 
                    ON autorole_logs(timestamp);
                """)

            # Initialize settings for all guilds
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
                await self.db.execute("""
                    INSERT OR IGNORE INTO autorole_settings (guild_id)
                    VALUES (?)
                """, (guild.id,))

            logger.info("AutoRole database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize autorole database: {e}")

    async def _process_role_queue(self):
        """Process queued role assignments with retries and error handling"""
        while True:
            try:
                if self._role_queue.empty():
                    await asyncio.sleep(1)
                    continue

                guild_id, user_id, role_id, delay = await self._role_queue.get()
                
                if delay > 0:
                    await asyncio.sleep(delay)

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                member = guild.get_member(user_id)
                if not member:
                    continue

                role = guild.get_role(role_id)
                if not role:
                    continue

                try:
                    await member.add_roles(role, reason="AutoRole Assignment")
                    
                    # Log successful role assignment
                    async with self.db.transaction():
                        await self.db.execute("""
                            INSERT INTO autorole_logs 
                            (guild_id, user_id, role_id, success)
                            VALUES (?, ?, ?, 1)
                        """, (guild_id, user_id, role_id))
                        
                        # Get log channel
                        result = await self.db.fetchone("""
                            SELECT log_channel_id 
                            FROM autorole_settings 
                            WHERE guild_id = ?
                        """, (guild_id,))
                        
                        if result and result['log_channel_id']:
                            log_channel = guild.get_channel(result['log_channel_id'])
                            if log_channel:
                                embed = self.ui.success_embed(
                                    "AutoRole Assigned",
                                    f"Role {role.mention} assigned to {member.mention}",
                                    "AutoRole"
                                )
                                await log_channel.send(embed=embed)

                except discord.Forbidden:
                    logger.error(f"Missing permissions to assign role in {guild.name}")
                    await self._log_error(guild_id, user_id, role_id, "Missing permissions")
                except Exception as e:
                    logger.error(f"Error assigning role: {e}")
                    await self._log_error(guild_id, user_id, role_id, str(e))
                finally:
                    self._role_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in role queue processor: {e}")
                await asyncio.sleep(5)

    async def _log_error(self, guild_id: int, user_id: int, role_id: int, error: str):
        """Log role assignment errors to database"""
        try:
            async with self.db.transaction():
                await self.db.execute("""
                    INSERT INTO autorole_logs 
                    (guild_id, user_id, role_id, success, error)
                    VALUES (?, ?, ?, 0, ?)
                """, (guild_id, user_id, role_id, error))
        except Exception as e:
            logger.error(f"Error logging autorole failure: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle role assignment when a member joins"""
        if member.bot:
            return

        try:
            settings = await self.db.fetchone("""
                SELECT * FROM autorole_settings 
                WHERE guild_id = ? AND enabled = 1
            """, (member.guild.id,))

            if not settings or not settings['role_ids']:
                return

            role_ids = [int(id) for id in settings['role_ids'].split(',')]
            delay = settings.get('delay', 0)
            exclude_bots = settings.get('exclude_bots', True)
            require_verification = settings.get('require_verification', False)

            if exclude_bots and member.bot:
                return

            if require_verification:
                # Check verification status if required
                verified = await self.db.fetchone("""
                    SELECT verified FROM verification_data 
                    WHERE guild_id = ? AND user_id = ?
                """, (member.guild.id, member.id))
                
                if not verified or not verified['verified']:
                    return

            for role_id in role_ids:
                await self._role_queue.put((
                    member.guild.id,
                    member.id,
                    role_id,
                    delay
                ))

        except Exception as e:
            logger.error(f"Error in autorole member join handler: {e}")

    @app_commands.command(name="setautorole")
    @app_commands.default_permissions(administrator=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        """Set up automatic role assignment"""
        try:
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Permission Error",
                        "I cannot assign roles that are higher than my highest role!",
                        "AutoRole"
                    ),
                    ephemeral=True
                )
                return

            async with self.db.transaction():
                # Get existing roles
                result = await self.db.fetchone("""
                    SELECT role_ids FROM autorole_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

                existing_roles = []
                if result and result['role_ids']:
                    existing_roles = result['role_ids'].split(',')

                # Add new role if not already present
                if str(role.id) not in existing_roles:
                    existing_roles.append(str(role.id))

                # Update settings
                await self.db.execute("""
                    INSERT OR REPLACE INTO autorole_settings 
                    (guild_id, role_ids, enabled) 
                    VALUES (?, ?, 1)
                """, (interaction.guild_id, ','.join(existing_roles)))

            embed = self.ui.success_embed(
                "AutoRole Updated",
                f"{role.mention} will now be automatically assigned to new members",
                "AutoRole"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"AutoRole set in {interaction.guild.name}: {role.name}")
        except Exception as e:
            logger.error(f"Error setting autorole: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Setup Error",
                    "An error occurred while setting up autorole.",
                    "AutoRole"
                ),
                ephemeral=True
            )

    @app_commands.command(name="removeautorole")
    @app_commands.default_permissions(administrator=True)
    async def removeautorole(self, interaction: discord.Interaction, role: discord.Role):
        """Remove a role from automatic assignment"""
        try:
            async with self.db.transaction():
                # Get existing roles
                result = await self.db.fetchone("""
                    SELECT role_ids FROM autorole_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

                if not result or not result['role_ids']:
                    await interaction.response.send_message(
                        embed=self.ui.error_embed(
                            "Not Found",
                            "No autoroles are currently set up.",
                            "AutoRole"
                        ),
                        ephemeral=True
                    )
                    return

                existing_roles = result['role_ids'].split(',')
                if str(role.id) not in existing_roles:
                    await interaction.response.send_message(
                        embed=self.ui.error_embed(
                            "Not Found",
                            f"{role.mention} is not set as an autorole.",
                            "AutoRole"
                        ),
                        ephemeral=True
                    )
                    return

                # Remove role
                existing_roles.remove(str(role.id))
                
                # Update settings
                if existing_roles:
                    await self.db.execute("""
                        UPDATE autorole_settings 
                        SET role_ids = ? 
                        WHERE guild_id = ?
                    """, (','.join(existing_roles), interaction.guild_id))
                else:
                    await self.db.execute("""
                        UPDATE autorole_settings 
                        SET role_ids = NULL, enabled = 0 
                        WHERE guild_id = ?
                    """, (interaction.guild_id,))

            embed = self.ui.success_embed(
                "AutoRole Removed",
                f"{role.mention} will no longer be automatically assigned",
                "AutoRole"
            )

            await interaction.response.send_message(embed=embed)
            logger.info(f"AutoRole removed in {interaction.guild.name}: {role.name}")
        except Exception as e:
            logger.error(f"Error removing autorole: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Removal Error",
                    "An error occurred while removing the autorole.",
                    "AutoRole"
                ),
                ephemeral=True
            )

    @app_commands.command(name="listautoroles")
    async def listautoroles(self, interaction: discord.Interaction):
        """List all automatic role assignments"""
        try:
            async with self.db.transaction():
                result = await self.db.fetchone("""
                    SELECT role_ids, enabled, delay, exclude_bots, require_verification 
                    FROM autorole_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

            if not result or not result['role_ids']:
                await interaction.response.send_message(
                    embed=self.ui.info_embed(
                        "No AutoRoles",
                        "No automatic role assignments are set up.",
                        "AutoRole"
                    ),
                    ephemeral=True
                )
                return

            role_ids = result['role_ids'].split(',')
            roles = []
            for role_id in role_ids:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    roles.append(role)

            if not roles:
                await interaction.response.send_message(
                    embed=self.ui.info_embed(
                        "No Valid Roles",
                        "No valid automatic role assignments found.",
                        "AutoRole"
                    ),
                    ephemeral=True
                )
                return

            embed = self.ui.info_embed(
                "AutoRole Configuration",
                "Current automatic role assignments",
                "AutoRole"
            )

            # Role list
            roles_text = "\n".join(f"• {role.mention}" for role in roles)
            embed.add_field(
                name="🎭 Roles",
                value=roles_text,
                inline=False
            )

            # Settings
            settings = []
            settings.append(f"Status: {'Enabled' if result['enabled'] else 'Disabled'}")
            if result['delay']:
                settings.append(f"Delay: {result['delay']} seconds")
            if result['exclude_bots']:
                settings.append("Bots: Excluded")
            if result['require_verification']:
                settings.append("Requires Verification: Yes")

            embed.add_field(
                name="⚙️ Settings",
                value="```" + "\n".join(settings) + "```",
                inline=False
            )

            # Recent logs
            async with self.db.transaction():
                logs = await self.db.fetchall("""
                    SELECT user_id, role_id, success, error, timestamp
                    FROM autorole_logs
                    WHERE guild_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 5
                """, (interaction.guild_id,))

            if logs:
                log_text = []
                for log in logs:
                    member = interaction.guild.get_member(log['user_id'])
                    role = interaction.guild.get_role(log['role_id'])
                    if member and role:
                        status = "✅" if log['success'] else "❌"
                        error = f" ({log['error']})" if not log['success'] and log['error'] else ""
                        timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                        log_text.append(
                            f"{status} {member.display_name} → {role.name}{error} "
                            f"({format_relative_time(timestamp)})"
                        )

                if log_text:
                    embed.add_field(
                        name="📋 Recent Activity",
                        value="\n".join(log_text),
                        inline=False
                    )

            await interaction.response.send_message(embed=embed)
            logger.info(f"AutoRole list viewed in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error listing autoroles: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching autorole settings.",
                    "AutoRole"
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AutoRole(bot))

