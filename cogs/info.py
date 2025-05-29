from typing import Literal, Optional, Union
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice, command

class InfoCog(commands.Cog):
    """Cog for various information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.version = "1.0.0"
        self.log = bot.get_logger("InfoCog")  # Use cog name for logger

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.log.info(f"{self.__class__.__name__} loaded successfully")

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.log.info(f"{self.__class__.__name__} unloaded successfully")

    @app_commands.command(name="info")
    @app_commands.describe(type="Type of info to retrieve")
    @app_commands.choices(type=[
        Choice(name="Server", value="server"),
        Choice(name="Bot", value="bot"),
        Choice(name="Role", value="role"),
        Choice(name="Channel", value="channel"),
        Choice(name="User", value="user")
    ])
    async def info(self, interaction: discord.Interaction, 
                  type: Literal["server", "bot", "role", "channel", "user"],
                  role: Optional[discord.Role] = None,
                  channel: Optional[discord.TextChannel] = None,
                  user: Optional[discord.User] = None):
        """Get detailed information."""
        
        await interaction.response.defer()
        
        if not interaction.guild:
            return await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
            
        try:
            embed = await self._create_info_embed(interaction, type, role, channel, user)
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden as e:
            self.log.warning(f"Permission error in info command: {str(e)}")
            await interaction.followup.send("❌ I don't have permission to view some information.", ephemeral=True)
        except ValueError as e:
            self.log.warning(f"Invalid input in info command: {str(e)}")
            await interaction.followup.send(f"❌ Invalid input: {str(e)}", ephemeral=True)
        except Exception as e:
            self.log.error(f"Error in info command: {str(e)}", exc_info=True)
            await interaction.followup.send("❌ An unexpected error occurred while fetching information.", ephemeral=True)

    async def _create_info_embed(self, interaction: discord.Interaction, 
                               type: str, role: Optional[discord.Role],
                               channel: Optional[discord.TextChannel],
                               user: Optional[discord.User]) -> discord.Embed:
        """Helper method to create info embeds"""
        if not interaction.guild:
            raise ValueError("This command can only be used in a server")

        embed = discord.Embed(color=discord.Color.blue())
        
        try:
            if type == "server":
                await self._add_server_info(embed, interaction.guild)
            elif type == "bot":
                await self._add_bot_info(embed)
            elif type == "role":
                if not role:
                    raise ValueError("Role parameter is required")
                await self._add_role_info(embed, role)
            elif type == "channel":
                if not channel:
                    raise ValueError("Channel parameter is required")
                await self._add_channel_info(embed, channel)
            elif type == "user":
                await self._add_user_info(embed, interaction.guild, user or interaction.user)
            else:
                raise ValueError(f"Unknown info type: {type}")
                
        except Exception as e:
            self.log.error(f"Error creating {type} info embed: {e}", exc_info=True)
            raise
            
        return embed

    async def _add_server_info(self, embed: discord.Embed, guild: discord.Guild) -> None:
        """Add server info to embed"""
        try:
            embed.title = f"📊 {guild.name} Info"
            
            # Basic Info
            embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, 'R'), inline=True)
            
            # Member Stats
            member_count = guild.member_count or 0
            bot_count = len([m for m in guild.members if m.bot])
            human_count = len([m for m in guild.members if not m.bot])
            embed.add_field(name="Members", value=f"Total: {member_count:,}\nHumans: {human_count:,}\nBots: {bot_count:,}", inline=True)
            
            # Channel Stats
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}", inline=True)
            
            # Role Stats
            embed.add_field(name="Roles", value=f"Total: {len(guild.roles)}", inline=True)
            
            # Server Features
            features = "\n".join(f"✓ {feature.replace('_', ' ').title()}" for feature in guild.features) or "None"
            embed.add_field(name="Features", value=features, inline=False)
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

        except Exception as e:
            self.log.error(f"Error adding server info: {e}", exc_info=True)
            raise

    async def _add_bot_info(self, embed: discord.Embed) -> None:
        """Add bot info to embed"""
        try:
            if not self.bot.user:
                raise ValueError("Bot is not fully initialized")
                
            total_members = sum(g.member_count or 0 for g in self.bot.guilds)
            embed.title = f"🤖 {self.bot.user.name} Statistics"
            
            # Basic Stats
            embed.add_field(name="Servers", value=f"{len(self.bot.guilds):,}", inline=True)
            embed.add_field(name="Members", value=f"{total_members:,}", inline=True)
            embed.add_field(name="Commands", value=f"{len(self.bot.tree.get_commands()):,}", inline=True)
            
            # Performance
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            embed.add_field(name="Version", value=self.version, inline=True)  # Update bot version fetching from a variable
            
            # Cog Stats
            cog_list = "\n".join(f"✓ {name}" for name in self.bot.cogs)
            embed.add_field(name=f"Loaded Cogs ({len(self.bot.cogs)})", value=cog_list or "None", inline=False)
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        except Exception as e:
            self.log.error(f"Error adding bot info: {e}", exc_info=True)
            raise

    async def _add_role_info(self, embed: discord.Embed, role: discord.Role) -> None:
        """Add role info to embed"""
        try:
            embed.title = f"👥 Role Info: {role.name}"
            embed.color = role.color
            embed.add_field(name="ID", value=str(role.id), inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, 'R'), inline=True)
            embed.add_field(name="Members", value=str(len(role.members)), inline=True)
            embed.add_field(name="Color", value=str(role.color), inline=True)
            embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
            embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
            
        except Exception as e:
            self.log.error(f"Error adding role info: {e}", exc_info=True)
            raise

    async def _add_channel_info(self, embed: discord.Embed, channel: discord.TextChannel) -> None:
        """Add channel info to embed"""
        try:
            embed.title = f"📝 Channel Info: {channel.name}"
            embed.add_field(name="ID", value=str(channel.id), inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(channel.created_at, 'R'), inline=True)
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
            embed.add_field(name="Topic", value=channel.topic or "No topic set", inline=True)
            embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off", inline=True)
            embed.add_field(name="NSFW", value=str(channel.is_nsfw()), inline=True)
            
        except Exception as e:
            self.log.error(f"Error adding channel info: {e}", exc_info=True)
            raise

    async def _add_user_info(self, embed: discord.Embed, guild: discord.Guild, user: Union[discord.User, discord.Member]) -> None:
        """Add user info to embed"""
        try:
            member = guild.get_member(user.id)
            
            embed.title = f"👤 User Information"
            embed.colour = member.color if member else discord.Color.blue()
            
            # Basic Info
            embed.add_field(name="Username", value=str(user), inline=True)
            embed.add_field(name="ID", value=user.id, inline=True)
            embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
            
            # Timestamps
            embed.add_field(name="Account Created", value=discord.utils.format_dt(user.created_at, 'R'), inline=True)
            if member and member.joined_at:
                embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, 'R'), inline=True)
            
            if member:
                # Role Info
                roles = [role.mention for role in reversed(member.roles[1:])]  # Skip @everyone
                embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) or "None", inline=False)
                
                # Permissions
                key_perms = []
                if member.guild_permissions.administrator:
                    key_perms.append("Administrator")
                if member.guild_permissions.manage_guild:
                    key_perms.append("Manage Server")
                if member.guild_permissions.manage_roles:
                    key_perms.append("Manage Roles")
                if member.guild_permissions.manage_channels:
                    key_perms.append("Manage Channels")
                if member.guild_permissions.manage_messages:
                    key_perms.append("Manage Messages")
                
                if key_perms:
                    embed.add_field(name="Key Permissions", value="\n".join(key_perms), inline=False)
                
                # Boost Status
                if member.premium_since:
                    embed.add_field(name="Boosting Since", value=discord.utils.format_dt(member.premium_since, 'R'), inline=True)
            
            embed.set_thumbnail(url=user.display_avatar.url)
        
        except Exception as e:
            self.log.error(f"Error adding user info: {e}", exc_info=True)
            raise

    @staticmethod
    def _format_list(items: list, max_items: int = 10) -> str:
        """Helper method to format lists with truncation"""
        if not items:
            return "None"
        formatted = "\n".join(str(item) for item in items[:max_items])
        if len(items) > max_items:
            formatted += f"\n...and {len(items) - max_items} more"
        return formatted

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
