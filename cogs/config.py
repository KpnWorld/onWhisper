import json
from typing import Optional
import discord
from discord.ext import commands
from discord.commands import slash_command, option

class Config(commands.Cog):
    """Configuration commands for the bot"""
    
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="config")
    async def config_base(self, ctx: discord.ApplicationContext):
        """Base config command - shows available configuration options"""
        embed = discord.Embed(
            title="Server Configuration",
            description="Available configuration commands:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="/config setlog",
            value="Set the logging channel",
            inline=False
        )
        embed.add_field(
            name="/config setwhisper",
            value="Set the whisper ticket channel",
            inline=False
        )
        embed.add_field(
            name="/config setstaff",
            value="Set staff role for whisper access",
            inline=False
        )
        embed.add_field(
            name="/config setxp",
            value="Configure XP settings",
            inline=False
        )
        embed.add_field(
            name="/config setlogoptions",
            value="Configure logging options",
            inline=False
        )
        await ctx.respond(embed=embed)    
        
    @slash_command(name="setlog")
    @commands.has_permissions(administrator=True)
    @option("channel", description="The channel to set for logging", type=discord.TextChannel)
    async def setlog(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel
    ):
        """Set the logging channel for the server"""
        await self.bot.db.set_logging_settings(
            ctx.guild.id,
            channel.id,
            "{}"  # Default empty options
        )
        await ctx.respond(f"✅ Logging channel set to {channel.mention}")    
        
    @slash_command(name="setwhisper")
    @commands.has_permissions(administrator=True)
    @option("channel", description="The channel to use for whisper tickets", type=discord.TextChannel)
    async def setwhisper(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel
    ):
        """Set the whisper ticket channel"""
        await self.bot.db.set_whisper_settings(
            ctx.guild.id,
            channel.id
        )
        await ctx.respond(f"✅ Whisper ticket channel set to {channel.mention}")    
    
    @slash_command(name="setstaff")
    @commands.has_permissions(administrator=True)
    @option("role", description="The role that can access whisper tickets", type=discord.Role)
    async def setstaff(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Role
    ):
        """Set the staff role for whisper ticket access"""
        await self.bot.db.set_staff_role(
            ctx.guild.id,
            role.id
        )
        await ctx.respond(f"✅ Staff role set to {role.mention}")    
        
    @slash_command(name="setxp")
    @commands.has_permissions(administrator=True)
    @option("cooldown", description="Cooldown between XP gains in seconds", type=int, min_value=0, max_value=3600)
    @option("min_xp", description="Minimum XP gained per message", type=int, min_value=1, max_value=100)
    @option("max_xp", description="Maximum XP gained per message", type=int, min_value=1, max_value=100)
    async def setxp(
        self,
        ctx: discord.ApplicationContext,
        cooldown: int,
        min_xp: int,
        max_xp: int
    ):
        """Configure XP settings"""
        if not (0 <= cooldown <= 3600):
            await ctx.respond("❌ Cooldown must be between 0 and 3600 seconds")
            return
        
        if not (1 <= min_xp <= 100) or not (1 <= max_xp <= 100):
            await ctx.respond("❌ XP values must be between 1 and 100")
            return
            
        if min_xp > max_xp:
            await ctx.respond("❌ Minimum XP cannot be greater than maximum XP")
            return

        await self.bot.db.set_xp_settings(
            ctx.guild.id,
            cooldown,
            min_xp,
            max_xp
        )
        await ctx.respond(f"✅ XP settings updated: Cooldown: {cooldown}s, Min XP: {min_xp}, Max XP: {max_xp}")    
        
    @slash_command(name="setlogoptions")
    @commands.has_permissions(administrator=True)
    @option("options", description="JSON string of logging options", type=str)
    async def setlogoptions(
        self,
        ctx: discord.ApplicationContext,
        options: str
    ):
        """Configure logging options"""
        try:
            options_dict = json.loads(options)
            await self.bot.db.set_logging_settings(
                ctx.guild.id,
                None,  # Don't change channel
                json.dumps(options_dict)  # Save formatted JSON
            )
            await ctx.respond("✅ Logging options updated")
        except json.JSONDecodeError:
            await ctx.respond("❌ Invalid JSON format for options")

def setup(bot):
    bot.add_cog(Config(bot))
