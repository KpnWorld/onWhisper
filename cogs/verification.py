from collections import defaultdict
from datetime import datetime, timezone
import time
import discord
from discord.ext import commands
from discord import app_commands
import logging
import random
import string
import asyncio
from typing import Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from utils.ui_manager import UIManager

logger = logging.getLogger(__name__)

class VerifyModal(discord.ui.Modal, title="Verification"):
    code = discord.ui.TextInput(
        label="Enter Verification Code",
        placeholder="Enter the code from the image above",
        min_length=6,
        max_length=6,
        required=True
    )

    def __init__(self, expected_code: str, role: discord.Role):
        super().__init__()
        self.expected_code = expected_code
        self.role = role

    async def on_submit(self, interaction: discord.Interaction):
        if self.code.value.upper() == self.expected_code:
            try:
                await interaction.user.add_roles(self.role)
                await interaction.response.send_message(
                    embed=interaction.client.get_cog("Verification").ui.success_embed(
                        "Verification Complete",
                        "You have been successfully verified!",
                        "Verification"
                    ),
                    ephemeral=True
                )
                logger.info(f"User {interaction.user} verified in {interaction.guild.name}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    embed=interaction.client.get_cog("Verification").ui.error_embed(
                        "Permission Error",
                        "Failed to assign verification role.",
                        "Verification"
                    ),
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                embed=interaction.client.get_cog("Verification").ui.error_embed(
                    "Verification Failed",
                    "Incorrect code. Please try again.",
                    "Verification"
                ),
                ephemeral=True
            )

class VerifyButton(discord.ui.View):
    def __init__(self, modal: VerifyModal):
        super().__init__(timeout=None)
        self.modal = modal

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.primary, emoji="✅")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.ui = UIManager()
        self.verification_cache = {}
        self._cleanup_task = bot.loop.create_task(self._cleanup_verification_cache())
        bot.loop.create_task(self._init_db())
        logger.info("Verification cog initialized")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _init_db(self):
        """Initialize database tables and indexes"""
        try:
            async with self.db.transaction():
                await self.db.execute_script("""
                    CREATE TABLE IF NOT EXISTS verification_settings (
                        guild_id INTEGER PRIMARY KEY,
                        enabled BOOLEAN DEFAULT 0,
                        role_id INTEGER,
                        channel_id INTEGER,
                        message TEXT DEFAULT 'Please complete verification to access the server.',
                        timeout INTEGER DEFAULT 300,
                        log_channel_id INTEGER,
                        custom_questions TEXT,
                        min_account_age INTEGER DEFAULT 0,
                        captcha_required BOOLEAN DEFAULT 1,
                        dm_welcome BOOLEAN DEFAULT 0,
                        welcome_message TEXT,
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS verification_data (
                        user_id INTEGER,
                        guild_id INTEGER,
                        verified BOOLEAN DEFAULT 0,
                        verified_at TIMESTAMP,
                        verification_method TEXT,
                        failed_attempts INTEGER DEFAULT 0,
                        last_attempt TIMESTAMP,
                        PRIMARY KEY (user_id, guild_id),
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS verification_logs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        action TEXT,
                        success BOOLEAN,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_verification_logs_guild 
                    ON verification_logs(guild_id);
                    
                    CREATE INDEX IF NOT EXISTS idx_verification_logs_time 
                    ON verification_logs(timestamp);
                """)

            # Initialize settings for all guilds
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
                await self.db.execute("""
                    INSERT OR IGNORE INTO verification_settings (guild_id)
                    VALUES (?)
                """, (guild.id,))

            logger.info("Verification database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize verification database: {e}")

    async def _cleanup_verification_cache(self):
        """Periodically clean up expired verification attempts"""
        while True:
            try:
                current_time = time.time()
                expired = []
                for key, data in self.verification_cache.items():
                    if current_time - data['timestamp'] > data['timeout']:
                        expired.append(key)
                
                for key in expired:
                    del self.verification_cache[key]

                await asyncio.sleep(60)  # Clean up every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in verification cache cleanup: {e}")

    async def log_verification_action(self, guild_id: int, user_id: int, 
                                    action: str, success: bool, details: str = None):
        """Log verification actions with proper error handling"""
        try:
            async with self.db.transaction():
                # Insert log entry
                await self.db.execute("""
                    INSERT INTO verification_logs 
                    (guild_id, user_id, action, success, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild_id, user_id, action, success, details))

                # Get log channel
                result = await self.db.fetchone("""
                    SELECT log_channel_id 
                    FROM verification_settings 
                    WHERE guild_id = ?
                """, (guild_id,))

                if result and result['log_channel_id']:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        log_channel = guild.get_channel(result['log_channel_id'])
                        if log_channel:
                            user = guild.get_member(user_id)
                            embed = (
                                self.ui.success_embed if success 
                                else self.ui.error_embed
                            )(
                                f"Verification {action}",
                                f"User: {user.mention if user else user_id}\n"
                                f"Details: {details or 'No additional details'}",
                                "Verification"
                            )
                            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging verification action: {e}")

    async def check_verification_requirements(self, member: discord.Member) -> tuple[bool, str]:
        """Check if a member meets verification requirements"""
        try:
            settings = await self.db.fetchone("""
                SELECT min_account_age FROM verification_settings 
                WHERE guild_id = ?
            """, (member.guild.id,))

            if not settings:
                return True, None

            if settings['min_account_age']:
                account_age = (datetime.now(timezone.utc) - member.created_at).days
                if account_age < settings['min_account_age']:
                    return False, f"Account too new (requires {settings['min_account_age']} days)"

            return True, None
        except Exception as e:
            logger.error(f"Error checking verification requirements: {e}")
            return False, "Internal error checking requirements"

    @app_commands.command(name="setupverification")
    @app_commands.default_permissions(administrator=True)
    async def setupverification(self, interaction: discord.Interaction, 
                              role: discord.Role, channel: discord.TextChannel):
        """Set up the verification system"""
        try:
            # Check bot permissions
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Permission Error",
                        "I cannot manage roles that are higher than my highest role!",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Permission Error",
                        "I don't have permission to send messages in that channel!",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            async with self.db.transaction():
                # Update verification settings
                await self.db.execute("""
                    INSERT OR REPLACE INTO verification_settings 
                    (guild_id, enabled, role_id, channel_id)
                    VALUES (?, 1, ?, ?)
                """, (interaction.guild_id, role.id, channel.id))

                # Send verification message
                embed = self.ui.info_embed(
                    "Server Verification",
                    "Click the button below to start the verification process.",
                    "Verification"
                )
                verify_button = discord.ui.Button(
                    label="Verify",
                    style=discord.ButtonStyle.primary,
                    custom_id="verify_start"
                )
                view = discord.ui.View()
                view.add_item(verify_button)
                await channel.send(embed=embed, view=view)

            success_embed = self.ui.success_embed(
                "Verification Setup Complete",
                f"Verification channel: {channel.mention}\n"
                f"Verified role: {role.mention}",
                "Verification"
            )
            await interaction.response.send_message(embed=success_embed)
            
            # Log setup
            await self.log_verification_action(
                interaction.guild_id,
                interaction.user.id,
                "Setup",
                True,
                f"Channel: {channel.id}, Role: {role.id}"
            )
            logger.info(f"Verification setup in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error setting up verification: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Setup Error",
                    "An error occurred while setting up verification.",
                    "Verification"
                ),
                ephemeral=True
            )

    @app_commands.command(name="disableverification")
    @app_commands.default_permissions(administrator=True)
    async def disableverification(self, interaction: discord.Interaction):
        """Disable the verification system"""
        try:
            async with self.db.transaction():
                # Check if verification is enabled
                result = await self.db.fetchone("""
                    SELECT enabled FROM verification_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

                if not result or not result['enabled']:
                    await interaction.response.send_message(
                        embed=self.ui.error_embed(
                            "Not Enabled",
                            "Verification is not enabled in this server.",
                            "Verification"
                        ),
                        ephemeral=True
                    )
                    return

                # Disable verification
                await self.db.execute("""
                    UPDATE verification_settings 
                    SET enabled = 0 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

            embed = self.ui.success_embed(
                "Verification Disabled",
                "The verification system has been disabled.",
                "Verification"
            )
            await interaction.response.send_message(embed=embed)
            
            # Log disable
            await self.log_verification_action(
                interaction.guild_id,
                interaction.user.id,
                "Disable",
                True
            )
            logger.info(f"Verification disabled in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error disabling verification: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while disabling verification.",
                    "Verification"
                ),
                ephemeral=True
            )

    @app_commands.command(name="verificationstats")
    @app_commands.default_permissions(administrator=True)
    async def verificationstats(self, interaction: discord.Interaction):
        """View verification system statistics"""
        try:
            async with self.db.transaction():
                # Get settings
                settings = await self.db.fetchone("""
                    SELECT * FROM verification_settings 
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

                if not settings:
                    await interaction.response.send_message(
                        embed=self.ui.error_embed(
                            "Not Setup",
                            "Verification has not been set up in this server.",
                            "Verification"
                        ),
                        ephemeral=True
                    )
                    return

                # Get verification stats
                stats = await self.db.fetchone("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified,
                        AVG(failed_attempts) as avg_attempts
                    FROM verification_data
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

                # Get recent logs
                logs = await self.db.fetchall("""
                    SELECT action, success, timestamp
                    FROM verification_logs
                    WHERE guild_id = ?
                    AND timestamp >= datetime('now', '-7 days')
                    ORDER BY timestamp DESC
                """, (interaction.guild_id,))

            embed = self.ui.info_embed(
                "Verification Statistics",
                f"Statistics for {interaction.guild.name}",
                "Verification"
            )

            # System Status
            status_text = (
                f"Status: {'Enabled' if settings['enabled'] else 'Disabled'}\n"
                f"Role: <@&{settings['role_id']}>\n"
                f"Channel: <#{settings['channel_id']}>"
            )
            embed.add_field(
                name="⚙️ System Status",
                value=status_text,
                inline=False
            )

            # Verification Stats
            stats_text = (
                f"Total Attempts: {stats['total']:,}\n"
                f"Verified Users: {stats['verified']:,}\n"
                f"Success Rate: {(stats['verified'] / stats['total'] * 100):.1f}%\n"
                f"Avg Attempts: {stats['avg_attempts']:.1f}"
            )
            embed.add_field(
                name="📊 Statistics",
                value=f"```{stats_text}```",
                inline=False
            )

            # Recent Activity
            if logs:
                recent = defaultdict(int)
                for log in logs:
                    key = f"{log['action']}_{log['success']}"
                    recent[key] += 1

                activity_text = []
                for action in ['Verify', 'Setup', 'Disable']:
                    successes = recent.get(f"{action}_1", 0)
                    failures = recent.get(f"{action}_0", 0)
                    if successes or failures:
                        activity_text.append(
                            f"{action}: {successes} ✅ {failures} ❌"
                        )

                if activity_text:
                    embed.add_field(
                        name="📈 Recent Activity (7 days)",
                        value="```" + "\n".join(activity_text) + "```",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed)
            logger.info(f"Verification stats viewed in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error showing verification stats: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while fetching verification statistics.",
                    "Verification"
                ),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle verification button interactions"""
        if not interaction.type == discord.InteractionType.component:
            return

        if interaction.custom_id != "verify_start":
            return

        try:
            # Check if verification is enabled
            settings = await self.db.fetchone("""
                SELECT * FROM verification_settings 
                WHERE guild_id = ? AND enabled = 1
            """, (interaction.guild_id,))

            if not settings:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Not Available",
                        "Verification is not currently enabled.",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            # Get verification role
            role = interaction.guild.get_role(settings['role_id'])
            if not role:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Configuration Error",
                        "Verification role not found. Please contact an administrator.",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            # Check if already verified
            verified = await self.db.fetchone("""
                SELECT verified FROM verification_data 
                WHERE guild_id = ? AND user_id = ?
            """, (interaction.guild_id, interaction.user.id))

            if verified and verified['verified']:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Already Verified",
                        "You are already verified in this server.",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            # Check verification requirements
            meets_requirements, error = await self.check_verification_requirements(interaction.user)
            if not meets_requirements:
                await interaction.response.send_message(
                    embed=self.ui.error_embed(
                        "Requirements Not Met",
                        f"You cannot verify yet: {error}",
                        "Verification"
                    ),
                    ephemeral=True
                )
                return

            # Generate verification challenge
            challenge = self._generate_challenge()
            self.verification_cache[f"{interaction.guild_id}_{interaction.user.id}"] = {
                'challenge': challenge,
                'attempts': 0,
                'timestamp': time.time(),
                'timeout': settings['timeout']
            }

            embed = self.ui.info_embed(
                "Verification Challenge",
                "Please enter the code shown in the image below:",
                "Verification"
            )
            embed.set_image(url=challenge['image_url'])

            modal = VerifyModal(challenge['code'], role)
            await interaction.response.send_modal(modal)

            # Log verification start
            await self.log_verification_action(
                interaction.guild_id,
                interaction.user.id,
                "Start",
                True
            )

        except Exception as e:
            logger.error(f"Error starting verification: {e}")
            await interaction.response.send_message(
                embed=self.ui.error_embed(
                    "Error",
                    "An error occurred while starting verification.",
                    "Verification"
                ),
                ephemeral=True
            )

    def _generate_challenge(self) -> dict:
        """Generate a verification challenge"""
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        image = self._create_captcha_image(code)
        return {
            'code': code,
            'image_url': image
        }

    def _create_captcha_image(self, text: str) -> str:
        """Create a CAPTCHA image and return its URL"""
        # Implementation would generate and store/upload image
        # For now, return a placeholder
        return "https://via.placeholder.com/300x100?text=CAPTCHA"

async def setup(bot):
    await bot.add_cog(Verification(bot))
