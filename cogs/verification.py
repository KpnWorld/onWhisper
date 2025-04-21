import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils.DBManager import DBManager
from utils.UIManager import UIManager
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

    @commands.slash_command(name="set-verification", description="Admin: Set verification role, channel, expiry, and method")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_verification(self, interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel, expiry_days: int = 7, verification_method: str = 'button', message_text: str = "Click the button to verify"):
        """Admin: Set verification role, channel, expiry, and method."""
        # Update verification settings in the database
        await self.db_manager.set_verification_settings(interaction.guild.id, role.id, channel.id, expiry_days, verification_method, message_text)

        # Send confirmation message
        embed = self.ui_manager.create_embed(
            title="Verification Settings Updated",
            description=f"Verification role set to {role.mention}.\nVerification channel set to {channel.mention}.\nVerification method set to {verification_method}.",
            footer="Administrative Command • Success"
        )
        await interaction.response.send_message(embed=embed)

        # Send the verification message with the button or instructions
        await self.send_verification_message(channel, message_text)

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

    @commands.slash_command(name="verify", description="User: Verify yourself")
    async def verify(self, interaction: discord.Interaction):
        """User: Verify themselves."""
        settings = await self.db_manager.get_verification_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message("Verification settings not configured yet.", ephemeral=True)

        # Check if the verification period has expired
        join_time = interaction.user.joined_at
        expiration_date = join_time + timedelta(days=settings['expiry_days'])
        if datetime.now() > expiration_date:
            return await interaction.response.send_message("You missed the verification window. Please contact an admin for a new verification message.", ephemeral=True)

        # Check if the user already has the verification role
        role = interaction.guild.get_role(settings['role_id'])
        if role in interaction.user.roles:
            return await interaction.response.send_message("You're already verified!", ephemeral=True)

        # Send CAPTCHA if the method is 'captcha'
        if settings['verification_method'] == 'captcha':
            await self.send_captcha(interaction.channel)

        await interaction.response.send_message("Verification button or CAPTCHA sent!", ephemeral=True)

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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button click to verify the user."""
        if interaction.data['custom_id'] != "verify_button":
            return

        settings = await self.db_manager.get_verification_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message("Verification settings not configured.", ephemeral=True)

        # Check if user already has the verified role
        role = interaction.guild.get_role(settings['role_id'])
        if role in interaction.user.roles:
            return await interaction.response.send_message("You're already verified!", ephemeral=True)

        # Grant the role
        await interaction.user.add_roles(role)

        # Send a confirmation message
        embed = self.ui_manager.create_embed(
            title="Verification Successful",
            description=f"Congratulations {interaction.user.mention}, you've been verified!",
            footer="User Command • Success"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(Verification(bot))

