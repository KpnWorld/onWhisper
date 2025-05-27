from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice, command

class ConfigCog(commands.Cog):
    """Cog for managing bot and server settings"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="config", description="Configure server settings.")
    @app_commands.guild_only()
    @app_commands.choices(setting=[
        Choice(name="Set Prefix", value="prefix"),
        Choice(name="Set Language", value="language"),
        Choice(name="Set Mod Role", value="mod_role"),
        Choice(name="Set Whisper Channel", value="whisper_channel")
    ])
    @app_commands.describe(value="The new value for the setting")
    async def config(self, interaction: discord.Interaction, 
                    setting: Literal["prefix", "language", "mod_role", "whisper_channel"],
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
                
            elif setting == "mod_role":
                # Try to find the role by mention, ID, or name
                role = None
                try:
                    # First try to convert from mention or ID
                    value = value.strip()
                    if value.startswith('<@&') and value.endswith('>'):
                        role_id = int(value[3:-1])
                    else:
                        role_id = int(value)
                    role = interaction.guild.get_role(role_id)
                except (ValueError, AttributeError):
                    # If that fails, try to find by name
                    role = discord.utils.get(interaction.guild.roles, name=value)
                
                if not role:
                    return await interaction.followup.send("Could not find that role! Please provide a valid role mention, ID, or name.", ephemeral=True)
                
                # Check if the role is manageable
                if role >= interaction.guild.me.top_role:
                    return await interaction.followup.send("I cannot manage this role as it is higher than or equal to my highest role!", ephemeral=True)
                
                if role.managed:
                    return await interaction.followup.send("This role is managed by an integration and cannot be used as a mod role!", ephemeral=True)
                
                await self.bot.db.set_guild_setting(interaction.guild.id, "mod_role", str(role.id))
                await interaction.followup.send(f"✅ Moderator role has been set to: {role.mention}", ephemeral=True)
                
            elif setting == "whisper_channel":
                # Try to get channel and role from the value (expects format: #channel @role)
                try:
                    parts = value.split()
                    if len(parts) != 2:
                        return await interaction.followup.send("Please provide both channel and role in format: #channel @role", ephemeral=True)
                    
                    # Parse channel
                    channel_str = parts[0]
                    if channel_str.startswith('<#') and channel_str.endswith('>'):
                        channel_id = int(channel_str[2:-1])
                        channel = interaction.guild.get_channel(channel_id)
                    else:
                        return await interaction.followup.send("Please mention a valid channel (#channel)", ephemeral=True)
                    
                    # Parse role
                    role_str = parts[1]
                    if role_str.startswith('<@&') and role_str.endswith('>'):
                        role_id = int(role_str[3:-1])
                        role = interaction.guild.get_role(role_id)
                    else:
                        return await interaction.followup.send("Please mention a valid role (@role)", ephemeral=True)
                    
                    if not isinstance(channel, discord.TextChannel):
                        return await interaction.followup.send("The channel must be a text channel!", ephemeral=True)
                    
                    if not role:
                        return await interaction.followup.send("Could not find the specified role!", ephemeral=True)

                    # Check bot permissions in the channel
                    bot_perms = channel.permissions_for(interaction.guild.me)
                    if not (bot_perms.send_messages and bot_perms.create_private_threads):
                        return await interaction.followup.send("I need permissions to send messages and create private threads in that channel!", ephemeral=True)
                    
                    # Save both settings
                    await self.bot.db.set_whisper_settings(
                        interaction.guild.id,
                        {
                            'channel_id': channel.id,
                            'staff_role_id': role.id,
                        }
                    )

                    # Also save the mod role for consistency
                    await self.bot.db.set_guild_setting(interaction.guild.id, "mod_role", str(role.id))
                    
                    # Send success message with mention of both channel and role
                    await interaction.followup.send(
                        f"✅ Whisper configuration updated:\n"
                        f"Channel: {channel.mention}\n"
                        f"Staff Role: {role.mention}\n"
                        f"This role will be able to see and manage whisper threads.",
                        ephemeral=True
                    )
                    
                except ValueError:
                    await interaction.followup.send("Invalid format! Use: #channel @role", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have the required permissions to perform this action!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed to communicate with Discord: {str(e)}", ephemeral=True)
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid value: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An unexpected error occurred: {str(e)}", ephemeral=True)
            # Log the error
            self.bot.logger.error(f"Error in config command: {str(e)}", exc_info=True)

    @app_commands.command(name="viewsettings", description="View current bot/server config.")
    @app_commands.guild_only()
    async def viewsettings(self, interaction: discord.Interaction):
        """View current server settings."""
        
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Fetch all relevant settings with default values
            try:
                prefix = await self.bot.db.get_guild_setting(interaction.guild.id, "prefix")
            except:
                prefix = "!"
                
            try:
                language = await self.bot.db.get_guild_setting(interaction.guild.id, "language")
            except:
                language = "en"
                
            try:
                mod_role_id = await self.bot.db.get_guild_setting(interaction.guild.id, "mod_role")
                mod_role = interaction.guild.get_role(int(mod_role_id)) if mod_role_id else None
            except:
                mod_role = None
            
            embed = discord.Embed(
                title=f"⚙️ Settings for {interaction.guild.name}",
                color=discord.Color.blue()
            )
            
            # Add fields with proper formatting and error handling
            embed.add_field(
                name="Prefix",
                value=f"`{prefix}`" if prefix else "`!` (default)",
                inline=True
            )
            
            embed.add_field(
                name="Language",
                value=(language or "en").upper(),
                inline=True
            )
            
            if mod_role and not mod_role.managed and mod_role < interaction.guild.me.top_role:
                embed.add_field(name="Mod Role", value=mod_role.mention, inline=True)
            else:
                embed.add_field(name="Mod Role", value="Not set", inline=True)
            
            if interaction.guild.icon:
                try:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                except:
                    pass  # Ignore if setting thumbnail fails
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while fetching settings. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
