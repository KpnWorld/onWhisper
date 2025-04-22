import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from utils.db_manager import DBManager
from utils.ui_manager import UIManager
import random
import string
from PIL import Image, ImageDraw, ImageFont
import io
import asyncio

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)

    def generate_captcha_text(self):
        """Generate random text for CAPTCHA."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    def generate_captcha_image(self, captcha_text):
        """Generate an image with the CAPTCHA text."""
        font = ImageFont.load_default()  # You can replace this with any font you want
        image = Image.new('RGB', (200, 80), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)

        # Add noise: random dots or squiggly lines
        for _ in range(random.randint(5, 10)):
            x1, y1 = random.randint(0, 200), random.randint(0, 80)
            x2, y2 = random.randint(0, 200), random.randint(0, 80)
            draw.line([x1, y1, x2, y2], fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), width=2)

        # Add random dots
        for _ in range(random.randint(10, 20)):
            x, y = random.randint(0, 200), random.randint(0, 80)
            draw.ellipse((x, y, x+3, y+3), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        # Draw the CAPTCHA text
        draw.text((50, 20), captcha_text, font=font, fill=(0, 0, 0))

        return image

    # =========================
    # 🔧 Admin Commands
    # =========================

    @app_commands.command(name="set-verification", description="Set verification settings for the server")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        role="The role to give when verified",
        channel="The channel for verification messages",
        expiry_days="Days before verification expires (1-30)",
        verification_method="Method of verification (button/captcha)",
        message_text="Custom verification message"
    )
    async def set_verification(
        self, 
        interaction: discord.Interaction, 
        role: discord.Role,
        channel: discord.TextChannel,
        expiry_days: app_commands.Range[int, 1, 30] = 7,
        verification_method: str = 'button',
        message_text: str = "Click the button to verify"
    ):
        try:
            if verification_method not in ['button', 'captcha']:
                raise ValueError("Verification method must be 'button' or 'captcha'")

            await self.db_manager.set_verification_settings(
                interaction.guild.id, 
                role.id, 
                channel.id, 
                expiry_days, 
                verification_method, 
                message_text
            )

            embed = self.ui_manager.success_embed(
                title="Verification Settings Updated",
                description=f"✅ Role: {role.mention}\n📝 Channel: {channel.mention}\n⚙️ Method: {verification_method}",
                command_type="Administrator"
            )
            await interaction.response.send_message(embed=embed)
            
            # Send verification message to channel
            await self.send_verification_message(channel, message_text)

        except Exception as e:
            await self.ui_manager.error_embed(
                interaction,
                title="Error Setting Verification",
                description=f"Failed to set verification: {str(e)}",
                command_type="Administrator"
            )

    async def send_verification_message(self, channel, message_text):
        """Send the verification message based on the method."""
        settings = await self.db_manager.get_verification_settings(channel.guild.id)
        method = settings['verification_method']

        if method == 'button':
            verify_button = discord.ui.Button(label="Click to Verify", custom_id="verify_button")
            view = discord.ui.View()
            view.add_item(verify_button)
            await channel.send(embed=self.ui_manager.create_embed(
                title="Verification",
                description=message_text,
                footer="User Command • Verification"
            ), view=view)
        elif method == 'captcha':
            await self.send_captcha(channel)
        else:
            await channel.send("Invalid verification method set.")

    async def send_captcha(self, channel):
        """Generate and send CAPTCHA."""
        captcha_text = self.generate_captcha_text()
        captcha_image = self.generate_captcha_image(captcha_text)

        # Save the CAPTCHA image in memory
        image_bytes = io.BytesIO()
        captcha_image.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        # Send CAPTCHA image to the channel
        await channel.send(
            embed=self.ui_manager.create_embed(
                title="CAPTCHA Verification",
                description="Please solve the CAPTCHA below to verify yourself.",
                footer="User Command • Verification"
            ),
            file=discord.File(image_bytes, filename="captcha.png")
        )

        # Store the CAPTCHA text in the database to validate user responses
        await self.db_manager.set_captcha_text(channel.guild.id, captcha_text)

        # Start a timeout mechanism (e.g., 5 minutes)
        await asyncio.sleep(300)  # 5 minutes timeout

        # Check if the CAPTCHA text is still active (not verified)
        is_verified = await self.db_manager.get_captcha_verified(channel.guild.id)
        if not is_verified:
            await channel.send(f"The CAPTCHA verification has expired. Please try again, {channel.guild.name} members.")

    # =========================
    # 👤 User Commands
    # =========================

    @app_commands.command(name="verify", description="Verify yourself to access the server")
    @app_commands.describe(method="Optional: Specify verification method (button/captcha)")
    async def verify(self, interaction: discord.Interaction, method: str = None):
        try:
            settings = await self.db_manager.get_verification_settings(interaction.guild.id)
            if not settings:
                raise ValueError("Verification not configured for this server")

            # Check if already verified
            role = interaction.guild.get_role(settings['role_id'])
            if role in interaction.user.roles:
                await interaction.response.send_message("You're already verified!", ephemeral=True)
                return

            # Check verification window
            join_time = interaction.user.joined_at
            expiration_date = join_time + timedelta(days=settings['expiry_days'])
            if datetime.now() > expiration_date:
                await interaction.response.send_message(
                    "Verification period expired. Contact an admin.", 
                    ephemeral=True
                )
                return

            # Use specified method or default
            verify_method = method or settings['verification_method']
            if verify_method == 'captcha':
                await self.send_captcha(interaction.channel)
                await interaction.response.send_message(
                    "CAPTCHA verification sent!", 
                    ephemeral=True
                )
            else:
                await self.send_button_verify(interaction)

        except Exception as e:
            await self.ui_manager.error_embed(
                interaction,
                title="Verification Error",
                description=str(e),
                command_type="User"
            )

    # =========================
    # 🎮 Verification UI
    # =========================

    async def send_button_verify(self, interaction: discord.Interaction):
        """Send button verification UI"""
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            style=discord.ButtonStyle.green,
            label="Verify",
            custom_id="verify_button"
        )
        view.add_item(button)
        
        await interaction.response.send_message(
            embed=self.ui_manager.info_embed(
                title="Verification",
                description="Click the button below to verify yourself",
                command_type="User"
            ),
            view=view,
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle CAPTCHA response."""
        if message.author.bot:
            return

        # Check if the message is the CAPTCHA response
        settings = await self.db_manager.get_verification_settings(message.guild.id)
        if not settings or settings['verification_method'] != 'captcha':
            return

        # Get the correct CAPTCHA text from DB
        correct_captcha = await self.db_manager.get_captcha_text(message.guild.id)

        # Validate the CAPTCHA response (case-insensitive)
        if message.content.strip().upper() == correct_captcha:
            role = message.guild.get_role(settings['role_id'])
            await message.author.add_roles(role)
            await message.channel.send(f"Congratulations {message.author.mention}, you've been verified!", delete_after=5)

            # Mark the user as verified
            await self.db_manager.set_captcha_verified(message.guild.id, message.author.id)
            # Clear the CAPTCHA text after successful verification
            await self.db_manager.clear_captcha_text(message.guild.id)
        else:
            await message.channel.send(f"Incorrect CAPTCHA, {message.author.mention}. Please try again!", delete_after=5)

    # =========================
    # 📝 Event Listeners
    # =========================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
            
        if interaction.data.get("custom_id") == "verify_button":
            await self.handle_verify_button(interaction)

    async def handle_verify_button(self, interaction: discord.Interaction):
        """Handle verification button clicks"""
        try:
            settings = await self.db_manager.get_verification_settings(interaction.guild.id)
            if not settings:
                raise ValueError("Verification not configured")

            role = interaction.guild.get_role(settings['role_id'])
            if role in interaction.user.roles:
                await interaction.response.send_message(
                    "You're already verified!", 
                    ephemeral=True
                )
                return

            await interaction.user.add_roles(role)
            await self.db_manager.set_verified(
                interaction.guild.id,
                interaction.user.id,
                True
            )

            await interaction.response.send_message(
                embed=self.ui_manager.success_embed(
                    title="Verification Successful",
                    description=f"Welcome {interaction.user.mention}! You now have access to the server.",
                    command_type="User"
                ),
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                embed=self.ui_manager.error_embed(
                    title="Verification Failed",
                    description=str(e),
                    command_type="User"
                ),
                ephemeral=True
            )

    async def ensure_verification_table(self):
        """Ensure verification table exists with proper schema"""
        await self.db_manager.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_settings (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER,
                channel_id INTEGER,
                expiry_days INTEGER DEFAULT 7,
                verification_method TEXT DEFAULT 'button',
                verification_message TEXT,
                enabled INTEGER DEFAULT 1
            )
            """
        )

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_verification_table()

async def setup(bot):
    await bot.add_cog(Verification(bot))

