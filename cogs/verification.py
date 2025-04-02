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
                    "✅ You have been successfully verified!", 
                    ephemeral=True
                )
                logger.info(f"User {interaction.user} verified in {interaction.guild.name}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Failed to assign verification role.", 
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ Incorrect code. Please try again.", 
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
        self.session = aiohttp.ClientSession()
        logger.info("Verification cog initialized")
    
    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def generate_captcha(self, text: str) -> BytesIO:
        """Generate a captcha image"""
        width = 200
        height = 100
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        # Add noise (dots)
        for _ in range(500):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill='black')

        # Add text
        font_size = 36
        for i, char in enumerate(text):
            x = 30 + (i * 30) + random.randint(-10, 10)
            y = 30 + random.randint(-10, 10)
            draw.text((x, y), char, fill='black')

        # Add lines
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line((x1, y1, x2, y2), fill='gray', width=1)

        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    def generate_verification_code(self) -> str:
        """Generate a random verification code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    @app_commands.command(name="setupverification", description="Set up the verification system")
    @app_commands.describe(
        channel="Channel for verification",
        role="Role to give upon verification",
        type="Type of verification",
        message="Custom verification message"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Reaction", value="reaction"),
        app_commands.Choice(name="Captcha", value="captcha")
    ])
    @app_commands.default_permissions(administrator=True)
    async def setupverification(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
        type: app_commands.Choice[str],
        message: Optional[str] = None
    ):
        try:
            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message(
                    "❌ I cannot manage roles higher than my highest role!",
                    ephemeral=True
                )
                return

            default_message = "React with ✅ to verify" if type.value == "reaction" else "Click the button below to start verification"
            verify_message = message or default_message

            embed = discord.Embed(
                title="Verification Required",
                description=verify_message,
                color=discord.Color.blue()
            )

            # Create verification message
            verify_msg = await channel.send(embed=embed)
            if type.value == "reaction":
                await verify_msg.add_reaction("✅")

            # Save settings to database
            with self.db.cursor() as cur:
                cur.execute("""
                    INSERT OR REPLACE INTO verification_settings
                    (guild_id, enabled, channel_id, role_id, message, type)
                    VALUES (?, 1, ?, ?, ?, ?)
                """, (interaction.guild_id, channel.id, role.id, verify_message, type.value))

            await interaction.response.send_message("✅ Verification system set up successfully!", ephemeral=True)
            logger.info(f"Verification set up in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error setting up verification: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting up verification.",
                ephemeral=True
            )

    @app_commands.command(name="disableverification", description="Disable the verification system")
    @app_commands.default_permissions(administrator=True)
    async def disableverification(self, interaction: discord.Interaction):
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    UPDATE verification_settings
                    SET enabled = 0
                    WHERE guild_id = ?
                """, (interaction.guild_id,))

            await interaction.response.send_message("✅ Verification system disabled.", ephemeral=True)
            logger.info(f"Verification disabled in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error disabling verification: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while disabling verification.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Check if this is a verification message
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT role_id, type 
                    FROM verification_settings 
                    WHERE guild_id = ? AND channel_id = ? AND enabled = 1
                """, (payload.guild_id, payload.channel_id))
                result = cur.fetchone()

            if not result or str(payload.emoji) != "✅":
                return

            role_id, verify_type = result
            if verify_type != "reaction":
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            await member.add_roles(role)
            logger.info(f"Verified {member} in {guild.name}")

            # Log verification if enabled
            channel = guild.get_channel(payload.channel_id)
            if channel:
                embed = discord.Embed(
                    title="✅ User Verified",
                    description=f"{member.mention} has been verified",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed, delete_after=10)
        except Exception as e:
            logger.error(f"Error in verification reaction handler: {e}")

    @app_commands.command(name="verify", description="Start the verification process")
    async def verify(self, interaction: discord.Interaction):
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT role_id, type 
                    FROM verification_settings 
                    WHERE guild_id = ? AND enabled = 1
                """, (interaction.guild_id,))
                result = cur.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ Verification is not set up in this server.",
                    ephemeral=True
                )
                return

            role_id, verify_type = result
            if verify_type != "captcha":
                await interaction.response.send_message(
                    "❌ This server uses reaction verification. Please react to the verification message.",
                    ephemeral=True
                )
                return

            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "❌ Verification role not found.",
                    ephemeral=True
                )
                return

            # Generate captcha
            code = self.generate_verification_code()
            captcha = await self.generate_captcha(code)

            embed = discord.Embed(
                title="Verification Required",
                description="Click the button below and enter the code shown in the image",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://captcha.png")

            modal = VerifyModal(code, role)
            view = VerifyButton(modal)

            await interaction.response.send_message(
                embed=embed,
                file=discord.File(captcha, "captcha.png"),
                view=view,
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error starting verification: {e}")
            await interaction.response.send_message(
                "❌ An error occurred during verification.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Verification(bot))
