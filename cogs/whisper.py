import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice
from typing import Optional
from datetime import datetime
import uuid

class WhisperCog(commands.Cog):
    """Cog for managing whisper/ticket threads"""
    
    def __init__(self, bot):
        self.bot = bot

    async def _check_manage_threads(self, interaction: discord.Interaction) -> bool:
        """Check if user has manage threads permissions"""
        if not interaction.guild:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.guild_permissions.manage_threads
    
    async def _check_whisper_enabled(self, guild_id: int) -> bool:
        """Check if whisper feature is enabled"""
        feature_settings = await self.bot.db.get_feature_settings(guild_id, "whispers")
        return bool(feature_settings and feature_settings['enabled'])

    @app_commands.command(name="whisper")
    @commands.guild_only()
    @app_commands.guild_only()
    async def whisper(self, interaction: discord.Interaction, action: str, user: Optional[discord.User] = None):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)

        # Check if whispers are enabled and get settings in one step
        feature_settings = await self.bot.db.get_feature_settings(interaction.guild.id, "whispers")
        if not feature_settings or not feature_settings['enabled']:
            return await interaction.response.send_message(
                "❌ Whisper system is currently disabled. An admin can enable it with `/config`.",
                ephemeral=True
            )

        # Get whisper options from feature settings
        options = feature_settings['options']
        if not options:
            return await interaction.response.send_message(
                "❌ Whisper system is not properly configured. Use `/config` to set it up.",
                ephemeral=True
            )

        channel_id = options.get('channel_id')
        staff_role_id = options.get('staff_role_id')

        if not channel_id or not staff_role_id:
            return await interaction.response.send_message(
                "❌ Whisper system is not properly configured. Use `/config` to set it up.",
                ephemeral=True
            )

        # Use configured channel instead of current channel
        channel_to_use = interaction.guild.get_channel(channel_id)
        if not isinstance(channel_to_use, discord.TextChannel):
            return await interaction.response.send_message("❌ The configured channel must be a text channel!", ephemeral=True)

        if action == "create":
            if not user:
                return await interaction.response.send_message("Please specify a user to create a whisper for!", ephemeral=True)
                
            try:
                # Generate unique whisper ID
                whisper_id = str(uuid.uuid4())[:8]
                
                # Create the thread in configured channel
                thread = await channel_to_use.create_thread(
                    name=f"whisper-{user.name}-{whisper_id}",
                    type=discord.ChannelType.private_thread,
                    invitable=False
                )
                
                # Add the user to the thread
                await thread.add_user(user)
                
                # Store whisper in database
                await self.bot.db.create_whisper(
                    interaction.guild.id,
                    whisper_id,
                    user.id,
                    thread.id
                )
                
                # Log the whisper creation
                await self.bot.db.insert_log(
                    interaction.guild.id,
                    "whisper_create",
                    f"Whisper thread created by {interaction.user.mention} for {user.mention} (ID: {whisper_id})"
                )
                
                # Send initial message
                embed = discord.Embed(
                    title=f"🤫 Whisper Thread Created",
                    description=f"Whisper ID: `{whisper_id}`\nCreated for: {user.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text=f"Created by {interaction.user}")
                
                await thread.send(embed=embed)
                await interaction.response.send_message(f"✅ Created whisper thread for {user.mention}", ephemeral=True)
                
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to create or manage threads!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
                
        elif action == "close":
            if not isinstance(interaction.channel, discord.Thread):
                return await interaction.response.send_message("This command can only be used in a whisper thread!", ephemeral=True)
                
            try:
                # Extract whisper ID from thread name
                thread_name_parts = interaction.channel.name.split("-")
                if len(thread_name_parts) < 3 or not thread_name_parts[0] == "whisper":
                    return await interaction.response.send_message("This doesn't appear to be a whisper thread!", ephemeral=True)
                    
                whisper_id = thread_name_parts[-1]
                
                # Archive the thread
                await interaction.channel.edit(archived=True, locked=True)
                
                # Update database
                await self.bot.db.close_whisper(interaction.guild.id, whisper_id)
                
                # Log the whisper closure
                await self.bot.db.insert_log(
                    interaction.guild.id,
                    "whisper_close",
                    f"Whisper thread closed by {interaction.user.mention} (ID: {whisper_id})"
                )
                
                await interaction.response.send_message("✅ Whisper thread closed.")
                
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
                
        elif action == "delete":
            if not await self._check_manage_threads(interaction):
                return await interaction.response.send_message("You need the Manage Threads permission to delete whispers!", ephemeral=True)
                
            if not isinstance(interaction.channel, discord.Thread):
                return await interaction.response.send_message("This command can only be used in a whisper thread!", ephemeral=True)
                
            try:
                # Get whisper ID before deletion
                thread_name_parts = interaction.channel.name.split("-")
                whisper_id = thread_name_parts[-1] if len(thread_name_parts) >= 3 else "unknown"
                
                await interaction.channel.delete()
                
                # Log the whisper deletion
                await self.bot.db.insert_log(
                    interaction.guild.id,
                    "whisper_delete",
                    f"Whisper thread deleted by {interaction.user.mention} (ID: {whisper_id})"
                )
                
                await interaction.response.send_message("✅ Whisper thread deleted.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="whispers", description="View recent or active whispers.")
    @commands.guild_only()
    @app_commands.guild_only()
    async def whispers(self, interaction: discord.Interaction, user: discord.User, include_closed: bool = False):
        """View whisper threads."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        if not await self._check_manage_threads(interaction):
            return await interaction.response.send_message("You need the Manage Threads permission to view all whispers!", ephemeral=True)
            
        try:
            # Get whispers from database - now user is required
            whispers = await self.bot.db.get_whispers_by_user(interaction.guild.id, user.id)
                
            if not include_closed:
                whispers = [w for w in whispers if not w['is_closed']]
                
            if not whispers:
                return await interaction.response.send_message("No whispers found!", ephemeral=True)
                
            # Create embed
            embed = discord.Embed(
                title="🤫 Whisper Threads",
                description=f"Showing whispers for {user.mention}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            for whisper in whispers[:10]:  # Limit to 10 most recent
                thread = interaction.guild.get_thread(whisper['thread_id'])
                status = "🔒 Closed" if whisper['is_closed'] else "🔓 Open"
                
                if thread:
                    embed.add_field(
                        name=f"{status} • ID: {whisper['whisper_id']}",
                        value=f"Thread: {thread.mention}\nCreated: {discord.utils.format_dt(whisper['created_at'], 'R')}",
                        inline=False
                    )
                
            if len(whispers) > 10:
                embed.set_footer(text=f"Showing 10 most recent of {len(whispers)} whispers")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    async def _get_whisper_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """Get the configured whisper channel"""
        settings = await self.bot.db.get_whisper_settings(guild_id)
        if not settings:
            return None
        
        channel = self.bot.get_channel(settings['channel_id'])
        return channel if isinstance(channel, discord.TextChannel) else None

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))
