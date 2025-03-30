import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.db_manager import DatabaseManager

# Initialize logger
logger = logging.getLogger(__name__)

# Define role type choices
ROLE_TYPES = [
    app_commands.Choice(name="Member", value="member"),
    app_commands.Choice(name="Bot", value="bot"),
    app_commands.Choice(name="All", value="all")
]

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager('autorole')
        self._init_db()
        logger.info("AutoRole cog initialized")

    def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            # Initialize settings for all guilds
            for guild in self.bot.guilds:
                self.db.ensure_guild_exists(guild.id)
            logger.info("Autorole database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize autorole database: {e}")
            raise

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize settings when bot joins a new guild"""
        try:
            self.db.ensure_guild_exists(guild.id)
            logger.info(f"Initialized settings for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to initialize settings for guild {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Automatically assign role based on member type (bot or human)"""
        try:
            role_type = "bot" if member.bot else "member"
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT r.role_id 
                    FROM autorole r
                    JOIN guild_settings g ON r.guild_id = g.guild_id
                    WHERE r.guild_id = ? AND r.type = ?
                """, (member.guild.id, role_type))
                result = cur.fetchone()
            
            if result:
                role = member.guild.get_role(result[0])
                if role:
                    await member.add_roles(role)
                    logger.info(f"Assigned {role_type} autorole to {member} in {member.guild}")
        except Exception as e:
            logger.error(f"Error assigning autorole: {e}")

    @app_commands.command(name="setautorole", description="Set the automatic role for new members or bots")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        type="Choose whether this role is for members or bots",
        role="The role to automatically assign"
    )
    @app_commands.choices(type=ROLE_TYPES[:2])  # Exclude 'all' option for setting roles
    async def setautorole(self, interaction: discord.Interaction, type: app_commands.Choice[str], role: discord.Role):
        """Set the autorole for members or bots"""
        try:
            with self.db.cursor() as cur:
                cur.execute("INSERT OR REPLACE INTO autorole (guild_id, role_id, type) VALUES (?, ?, ?)",
                         (interaction.guild_id, role.id, type))

            embed = discord.Embed(
                title="⚙️ AutoRole Configuration",
                description="Automatic role assignment has been configured.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Settings",
                value=f"Type: `{type}`\nRole: {role.mention}",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="✅ Configuration saved successfully",
                inline=False
            )
            embed.set_footer(text="Administrative Command • AutoRole System")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Autorole set in {interaction.guild}: {role.name} for {type}s")
        except Exception as e:
            logger.error(f"Error setting autorole: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to set autorole configuration.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(name="removeautorole", description="Remove the automatic role assignment")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(type="Choose which autorole type to remove")
    @app_commands.choices(type=ROLE_TYPES)  # Include all options including 'all'
    async def removeautorole(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        """Remove autorole settings"""
        try:
            with self.db.cursor() as cur:
                if type == "all":
                    cur.execute("DELETE FROM autorole WHERE guild_id=?", (interaction.guild_id,))
                    status = "All autorole settings have been removed"
                else:
                    cur.execute("DELETE FROM autorole WHERE guild_id=? AND type=?", 
                              (interaction.guild_id, type))
                    status = f"Autorole for {type}s has been removed"

            embed = discord.Embed(
                title="⚙️ AutoRole Configuration",
                description="Automatic role assignment has been updated.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Action",
                value=f"Removed configuration for: `{type}`",
                inline=False
            )
            embed.add_field(
                name="Status",
                value=f"✅ {status}",
                inline=False
            )
            embed.set_footer(text="Administrative Command • AutoRole System")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Autorole removed in {interaction.guild} for {type}")
        except Exception as e:
            logger.error(f"Error removing autorole: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to remove autorole configuration.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(name="massrole", description="Assign a role to all server members")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="The role to assign to all members")
    async def massrole(self, interaction: discord.Interaction, role: discord.Role):
        """Assign a role to all members in the server"""
        try:
            if not interaction.guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ I don't have permission to manage roles!")
                return

            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ I can't assign roles higher than my highest role!")
                return

            await interaction.response.defer(thinking=True)
            progress_embed = discord.Embed(
                title="Role Assignment Progress",
                description="Starting role assignment...",
                color=discord.Color.blue()
            )
            progress_msg = await interaction.followup.send(embed=progress_embed)
            
            success_count = 0
            fail_count = 0
            error_users = []
            total_members = len(interaction.guild.members)
            
            for member in interaction.guild.members:
                if role in member.roles:
                    continue
                    
                try:
                    if member.top_role >= interaction.guild.me.top_role:
                        error_users.append(f"👑 {member.name} (Higher role)")
                        fail_count += 1
                        continue
                        
                    await member.add_roles(role)
                    success_count += 1
                    if success_count % 5 == 0:
                        progress_embed.description = f"Processing: {success_count + fail_count}/{total_members} members..."
                        await progress_msg.edit(embed=progress_embed)
                except Exception as e:
                    fail_count += 1
                    error_users.append(f"❌ {member.name} ({str(e)})")

            result_embed = discord.Embed(
                title="Role Assignment Complete",
                color=discord.Color.green() if success_count > 0 else discord.Color.red()
            )
            
            result_embed.add_field(
                name="📊 Statistics",
                value=f"✅ Success: {success_count} members\n❌ Failed: {fail_count} members",
                inline=False
            )
            
            if error_users and fail_count < 10:
                result_embed.add_field(
                    name="⚠️ Failed Members",
                    value="\n".join(error_users[:10]),
                    inline=False
                )

            result_embed.set_footer(text=f"Role: {role.name}")
            await progress_msg.edit(embed=result_embed)
            logger.info(f"Mass role assignment completed in {interaction.guild}: {role.name}")
        except Exception as e:
            logger.error(f"Error in mass role assignment: {e}")
            await interaction.followup.send("❌ An error occurred while assigning roles.")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
    
