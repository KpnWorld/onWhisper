from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice, command
import logging

class ConfigCog(commands.Cog):
    """Cog for managing bot and server settings"""
    
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("cogs.config")  # Use standard logging

    @app_commands.command(name="config", description="Configure server settings.")
    @app_commands.guild_only()
    @app_commands.choices(setting=[
        Choice(name="Set Prefix", value="prefix"),
        Choice(name="Set Language", value="language"),
        Choice(name="Set Whisper Staff Role", value="staff_role"),  # Changed from mod_role
        Choice(name="Set Whisper Channel", value="whisper_channel")
    ])
    @app_commands.describe(
        setting="The setting to configure",
        value="For channels/roles: Mention them (#channel or @role)"
    )
    async def config(self, interaction: discord.Interaction, 
                    setting: Literal["prefix", "language", "staff_role", "whisper_channel"],
                    value: str):
        """Configure server settings."""
        
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        # Type cast to Member since we know this is in a guild
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            return await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer(ephemeral=True)
        
        try:            
            if setting == "prefix":
                # Validate prefix
                if not value or len(value) > 5:
                    return await interaction.followup.send("Prefix must be between 1 and 5 characters!", ephemeral=True)
                if ' ' in value:
                    return await interaction.followup.send("Prefix cannot contain spaces!", ephemeral=True)
                
                await self.bot.db.set_guild_setting(interaction.guild.id, "prefix", value)
                await interaction.followup.send(f"✅ Server prefix has been set to: `{value}`", ephemeral=True)
                
            elif setting == "language":
                valid_languages = ["en", "es", "fr", "de"]  # Add more as needed
                if value.lower() not in valid_languages:
                    return await interaction.followup.send(f"Invalid language! Valid options: {', '.join(valid_languages)}", ephemeral=True)
                await self.bot.db.set_guild_setting(interaction.guild.id, "language", value.lower())
                await interaction.followup.send(f"✅ Server language has been set to: `{value.lower()}`", ephemeral=True)
                
            elif setting == "staff_role":
                # Try to find the role by mention, ID, or name
                role = None
                try:
                    value = value.strip()
                    if value.startswith('<@&') and value.endswith('>'):
                        role_id = int(value[3:-1])
                    else:
                        role_id = int(value)
                    role = interaction.guild.get_role(role_id)
                except (ValueError, AttributeError):
                    role = discord.utils.get(interaction.guild.roles, name=value)
                
                if not role:
                    return await interaction.followup.send("Could not find that role! Please provide a valid role mention, ID, or name.", ephemeral=True)
                
                if role >= interaction.guild.me.top_role:
                    return await interaction.followup.send("I cannot manage this role as it is higher than my highest role!", ephemeral=True)
                
                if role.managed:
                    return await interaction.followup.send("This role is managed by an integration and cannot be used!", ephemeral=True)
                
                # Save both whisper staff role and mod role settings
                await self.bot.db.set_whisper_channel(interaction.guild.id, 
                    (await self.bot.db.get_whisper_settings(interaction.guild.id) or {}).get('channel_id', 0), 
                    role.id)
                await self.bot.db.set_guild_setting(interaction.guild.id, "mod_role", str(role.id))
                
                await interaction.followup.send(
                    f"✅ Whisper Staff role has been set to: {role.mention}\n"
                    "This role will be used for managing whisper threads.", 
                    ephemeral=True
                )

            elif setting == "whisper_channel":
                # Parse channel mention
                if not value.startswith('<#') or not value.endswith('>'):
                    return await interaction.followup.send("Please mention a valid channel (#channel)", ephemeral=True)
                
                try:
                    channel_id = int(value[2:-1])
                    channel = interaction.guild.get_channel(channel_id)
                    
                    if not isinstance(channel, discord.TextChannel):
                        return await interaction.followup.send("The channel must be a text channel!", ephemeral=True)

                    # Check bot permissions in the channel
                    bot_perms = channel.permissions_for(interaction.guild.me)
                    if not (bot_perms.send_messages and bot_perms.create_private_threads):
                        return await interaction.followup.send("I need permissions to send messages and create private threads in that channel!", ephemeral=True)
                    
                    # Get or create staff role
                    staff_role = discord.utils.get(interaction.guild.roles, name="Whisper Staff")
                    if not staff_role:
                        staff_role = await interaction.guild.create_role(
                            name="Whisper Staff",
                            reason="Automatically created for whisper functionality"
                        )
                    
                    # Save settings
                    await self._save_whisper_settings(
                        interaction.guild.id,
                        channel.id,
                        staff_role.id
                    )
                    
                    # Also save the mod role for consistency
                    await self.bot.db.set_guild_setting(interaction.guild.id, "mod_role", str(staff_role.id))
                    
                    await interaction.followup.send(
                        f"✅ Whisper configuration updated:\n"
                        f"Channel: {channel.mention}\n"
                        f"Staff Role: {staff_role.mention}\n\n"
                        f"Note: I've created/set the 'Whisper Staff' role for managing whispers.",
                        ephemeral=True
                    )
                    
                except ValueError:
                    await interaction.followup.send("Invalid channel format! Please use a channel mention (#channel)", ephemeral=True)
                except Exception as e:
                    self.log.error(f"Error setting whisper config: {str(e)}", exc_info=True)
                    await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

        except discord.Forbidden as e:
            self.log.error(f"Permission error in config command: {str(e)}")
            await interaction.followup.send("❌ I don't have the required permissions to perform this action!", ephemeral=True)
        except Exception as e:
            self.log.error(f"Unexpected error in config command: {str(e)}", exc_info=True)
            await interaction.followup.send("❌ An unexpected error occurred. Please try again later.", ephemeral=True)

    @app_commands.command(name="viewsettings", description="View current bot/server config.")
    @app_commands.guild_only()
    async def viewsettings(self, interaction: discord.Interaction):
        """View current server settings."""
        
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer(ephemeral=True)
        
        try:
            settings = await self._fetch_all_settings(interaction.guild.id)
            embed = self._create_settings_embed(interaction.guild, settings)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.log.error(f"Error in viewsettings: {str(e)}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while fetching settings. Please try again later.",
                ephemeral=True
            )

    async def _save_whisper_settings(self, guild_id: int, channel_id: int, role_id: int) -> None:
        """Helper method to save whisper settings consistently"""
        await self.bot.db.set_whisper_channel(guild_id, channel_id, role_id)

    async def _fetch_all_settings(self, guild_id: int) -> dict:
        """Helper method to fetch all settings"""
        settings = {}
        try:
            settings['prefix'] = await self.bot.db.get_guild_setting(guild_id, "prefix") or "!"
            settings['language'] = await self.bot.db.get_guild_setting(guild_id, "language") or "en"
            settings['mod_role_id'] = await self.bot.db.get_guild_setting(guild_id, "mod_role")
        except Exception as e:
            self.log.error(f"Error fetching settings: {str(e)}", exc_info=True)
            raise
        return settings

    def _create_settings_embed(self, guild: discord.Guild, settings: dict) -> discord.Embed:
        """Helper method to create settings embed"""
        embed = discord.Embed(
            title=f"⚙️ Settings for {guild.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Prefix",
            value=f"`{settings['prefix']}`",
            inline=True
        )
        
        embed.add_field(
            name="Language",
            value=settings['language'].upper(),
            inline=True
        )
        
        # Handle mod role
        if settings.get('mod_role_id'):
            mod_role = guild.get_role(int(settings['mod_role_id']))
            if mod_role and not mod_role.managed and mod_role < guild.me.top_role:
                embed.add_field(name="Mod Role", value=mod_role.mention, inline=True)
            else:
                embed.add_field(name="Mod Role", value="Not set", inline=True)
        else:
            embed.add_field(name="Mod Role", value="Not set", inline=True)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        return embed

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
