import discord
from discord.ext import commands
from discord.commands import slash_command, option
import datetime
from platform import python_version
from typing import Optional

class Info(commands.Cog):
    """Information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.now()    
        
    @slash_command(name="info", description="Get information about users, server, roles, channels, or the bot")
    @option("target", description="What to get info about", type=str, choices=["user", "server", "role", "channel", "bot"])
    @option("item", description="Optional ID or mention of the item to get info about", type=str, required=False)
    async def info_command(
        self,
        ctx: discord.ApplicationContext,
        target: str,
        item: Optional[str] = None
    ) -> None:
        if target == "user":
            await self._user_info(ctx, item)
        elif target == "server":
            await self._server_info(ctx)
        elif target == "role":
            await self._role_info(ctx, item)
        elif target == "channel":
            await self._channel_info(ctx, item)
        elif target == "bot":
            await self._bot_info(ctx)

    async def _user_info(
        self,
        ctx: discord.ApplicationContext,
        user_arg: Optional[str] = None
    ) -> None:
        """Get information about a user"""
        try:
            if user_arg:
                # Try to get user from mention or ID
                user_id = int(''.join(filter(str.isdigit, user_arg)))
                member = await ctx.guild.fetch_member(user_id)
            else:
                member = ctx.author if isinstance(ctx.author, discord.Member) else None
                
            if not member:
                await ctx.respond("Could not find that user in this server.", ephemeral=True)
                return
                
            roles = [role.mention for role in member.roles[1:]]  # All roles except @everyone
            joined_at = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
            created_at = member.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            embed = discord.Embed(
                color=member.color if hasattr(member, 'color') else discord.Color.default(),
                timestamp=datetime.datetime.now()
            )
            embed.set_author(name=f"User Info - {str(member)}")
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="ID", value=str(member.id))
            embed.add_field(name="Display Name", value=member.display_name)
            embed.add_field(name="Created at", value=created_at)
            embed.add_field(name="Joined at", value=joined_at)
            embed.add_field(name="Roles", value=" ".join(roles) if roles else "No roles")
            
            await ctx.respond(embed=embed)
        except ValueError:
            await ctx.respond("Invalid user ID or mention format.", ephemeral=True)
        except discord.NotFound:
            await ctx.respond("User not found.", ephemeral=True)

    async def _server_info(
        self,
        ctx: discord.ApplicationContext
    ) -> None:
        """Get information about the server"""
        guild = ctx.guild
        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return
            
        total_members = guild.member_count
        total_text_channels = len(guild.text_channels)
        total_voice_channels = len(guild.voice_channels)
        total_categories = len(guild.categories)
        
        embed = discord.Embed(title=f"{guild.name} Server Information", color=discord.Color.blue())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        owner = guild.owner
        embed.add_field(name="Owner", value=owner.mention if owner else "Unknown")
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d"))
        embed.add_field(name="Member Count", value=str(total_members))
        embed.add_field(name="Channels", value=f"📝 Text: {total_text_channels}\n🔊 Voice: {total_voice_channels}\n📂 Categories: {total_categories}")
        embed.add_field(name="Verification Level", value=str(guild.verification_level))
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier}")
        
        await ctx.respond(embed=embed)

    async def _role_info(
        self,
        ctx: discord.ApplicationContext,
        role_arg: Optional[str] = None
    ) -> None:
        """Get information about a role"""
        try:
            if not role_arg:
                await ctx.respond("Please specify a role to get information about.", ephemeral=True)
                return
                
            # Try to get role from mention or ID
            role_id = int(''.join(filter(str.isdigit, role_arg)))
            role = ctx.guild.get_role(role_id)
            
            if not role:
                await ctx.respond("Role not found.", ephemeral=True)
                return
                
            embed = discord.Embed(color=role.color)
            embed.set_author(name=f"Role Info - {role.name}")
            embed.add_field(name="ID", value=str(role.id))
            embed.add_field(name="Created at", value=role.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            embed.add_field(name="Color", value=str(role.color))
            embed.add_field(name="Members", value=str(len(role.members)))
            embed.add_field(name="Mentionable", value=str(role.mentionable))
            embed.add_field(name="Displayed separately", value=str(role.hoist))
            
            await ctx.respond(embed=embed)
        except ValueError:
            await ctx.respond("Invalid role ID or mention format.", ephemeral=True)

    async def _channel_info(
        self,
        ctx: discord.ApplicationContext,
        channel_arg: Optional[str] = None
    ) -> None:
        """Get information about a channel"""
        try:
            if not channel_arg:
                channel = ctx.channel
            else:
                # Try to get channel from mention or ID
                channel_id = int(''.join(filter(str.isdigit, channel_arg)))
                channel = ctx.guild.get_channel(channel_id)
            
            if not channel:
                await ctx.respond("Channel not found.", ephemeral=True)
                return
                
            embed = discord.Embed(color=discord.Color.blue())
            embed.set_author(name=f"Channel Info - {channel.name}")
            embed.add_field(name="ID", value=str(channel.id))
            embed.add_field(name="Type", value=str(channel.type))
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None")
            embed.add_field(name="Created at", value=channel.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            
            if isinstance(channel, discord.TextChannel):
                embed.add_field(name="Topic", value=channel.topic or "No topic set")
                embed.add_field(name="NSFW", value=str(channel.is_nsfw()))
                embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off")
            
            await ctx.respond(embed=embed)
        except ValueError:
            await ctx.respond("Invalid channel ID or mention format.", ephemeral=True)

    async def _bot_info(
        self,
        ctx: discord.ApplicationContext
    ) -> None:
        """Get information about the bot"""
        bot_user = ctx.bot.user
        if not bot_user:
            await ctx.respond("Bot user information not available.", ephemeral=True)
            return
            
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name=f"Bot Info - {bot_user.name}")
        embed.set_thumbnail(url=bot_user.display_avatar.url)
        
        # Calculate uptime
        uptime = datetime.datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        embed.add_field(name="ID", value=str(bot_user.id))
        embed.add_field(name="Created at", value=bot_user.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="Uptime", value=uptime_str)
        embed.add_field(name="Servers", value=str(len(ctx.bot.guilds)))
        embed.add_field(name="Commands", value=str(len(ctx.bot.application_commands)))
        embed.add_field(name="Python Version", value=python_version())
        embed.add_field(name="discord.py Version", value=discord.__version__)
        
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Info(bot))
