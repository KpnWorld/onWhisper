from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice, command

class InfoCog(commands.Cog):
    """Cog for various information commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="info", description="Get various types of information.")
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
        """Get various types of information."""
        
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        embed = discord.Embed(color=discord.Color.blue())
        
        if type == "server":            
            embed.title = f"📊 {interaction.guild.name} Info"
            embed.description = interaction.guild.description or "No description set"
            # Handle case where owner might be None
            owner_value = interaction.guild.owner.mention if interaction.guild.owner else "Unknown"
            embed.add_field(name="Owner", value=owner_value, inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(interaction.guild.created_at, 'R'), inline=True)
            embed.add_field(name="Members", value=str(interaction.guild.member_count), inline=True)
            
        # Set thumbnail if icon exists
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        elif type == "bot":
            if not self.bot.user:
                return await interaction.response.send_message("Bot is not fully initialized yet.", ephemeral=True)

            embed.title = f"🤖 {self.bot.user.name} Info"
            embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
            embed.add_field(name="Commands", value=str(len(self.bot.tree.get_commands())), inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
        elif type == "role":
            if not role:
                return await interaction.response.send_message("Please specify a role!", ephemeral=True)
            embed.title = f"👥 Role Info: {role.name}"
            embed.color = role.color
            embed.add_field(name="ID", value=str(role.id), inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, 'R'), inline=True)
            embed.add_field(name="Members", value=str(len(role.members)), inline=True)
            embed.add_field(name="Color", value=str(role.color), inline=True)
            embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
            embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
            
        elif type == "channel":
            if not channel:
                return await interaction.response.send_message("Please specify a channel!", ephemeral=True)
            embed.title = f"📝 Channel Info: {channel.name}"
            embed.add_field(name="ID", value=str(channel.id), inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(channel.created_at, 'R'), inline=True)
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
            embed.add_field(name="Topic", value=channel.topic or "No topic set", inline=True)
            embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off", inline=True)
            embed.add_field(name="NSFW", value=str(channel.is_nsfw()), inline=True)
            
        elif type == "user":            
            target = user or interaction.user
            member = interaction.guild.get_member(target.id)
            embed.title = f"👤 User Info: {target}"
            
            # Set thumbnail if avatar exists
            if target.avatar:
                embed.set_thumbnail(url=target.display_avatar.url)
                
            embed.add_field(name="ID", value=str(target.id), inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(target.created_at, 'R'), inline=True)
            
            if member:
                if member.joined_at:
                    embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, 'R'), inline=True)
                
                # Add top role only if the member has roles beyond @everyone
                if len(member.roles) > 1:
                    embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
                
                # Set color if member has a color role
                if member.color != discord.Color.default():
                    embed.color = member.color
                
                if member.premium_since:
                    embed.add_field(name="Boosting Since", value=discord.utils.format_dt(member.premium_since, 'R'), inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
