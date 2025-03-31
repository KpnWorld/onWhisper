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
                    SELECT role_id 
                    FROM autorole
                    WHERE guild_id = ? AND type = ? AND enabled = 1
                """, (member.guild.id, role_type))
                result = cur.fetchone()
            
            if result:
                role_id = result[0]
                role = member.guild.get_role(role_id)
                if role and role.position < member.guild.me.top_role.position:
                    await member.add_roles(role)
                    logger.info(f"Assigned {role_type} autorole ({role.name}) to {member} in {member.guild}")
                else:
                    logger.warning(f"Cannot assign autorole in {member.guild.id}: Role not found or higher than bot's role")
        except Exception as e:
            logger.error(f"Error assigning autorole: {e}")

    @app_commands.command(name="setautorole", description="Set the automatic role for new members or bots")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        type="Choose whether this role is for members or bots",
        role="The role to automatically assign"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Member", value="member"),
        app_commands.Choice(name="Bot", value="bot")
    ])
    async def setautorole(self, interaction: discord.Interaction, type: app_commands.Choice[str], role: discord.Role):
        """Set the autorole for members or bots"""
        try:
            # Check role hierarchy
            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message(
                    "❌ I cannot assign roles that are higher than my highest role!",
                    ephemeral=True
                )
                return

            with self.db.cursor() as cur:
                # First ensure guild settings exist
                cur.execute("""
                    INSERT OR IGNORE INTO guild_settings (guild_id)
                    VALUES (?)
                """, (interaction.guild_id,))
                
                # Then set the autorole
                cur.execute("""
                    INSERT OR REPLACE INTO autorole (guild_id, role_id, type, enabled)
                    VALUES (?, ?, ?, 1)
                """, (interaction.guild_id, role.id, type.value))

            embed = discord.Embed(
                title="⚙️ AutoRole Configuration",
                description="Automatic role assignment has been configured.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Settings",
                value=f"Type: `{type.value}`\nRole: {role.mention}",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="✅ Configuration saved successfully",
                inline=False
            )
            embed.set_footer(text="Administrative Command • AutoRole System")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Autorole set in {interaction.guild}: {role.name} for {type.value}s")
        except Exception as e:
            logger.error(f"Error setting autorole: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to set autorole configuration.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(name="removeautorole", description="Remove the automatic role assignment")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(type="Choose which autorole type to remove")
    @app_commands.choices(type=ROLE_TYPES)  # Include all options including 'all'
    async def removeautorole(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        """Remove autorole settings"""
        try:
            with self.db.cursor() as cur:
                if type.value == "all":
                    cur.execute("""
                        DELETE FROM autorole 
                        WHERE guild_id = ?
                    """, (interaction.guild_id,))
                else:
                    cur.execute("""
                        DELETE FROM autorole 
                        WHERE guild_id = ? AND type = ?
                    """, (interaction.guild_id, type.value))

            embed = discord.Embed(
                title="⚙️ AutoRole Configuration",
                description="Automatic role assignment has been updated.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Action",
                value=f"Removed configuration for: `{type.value}`",
                inline=False
            )
            embed.set_footer(text="Administrative Command • AutoRole System")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Autorole removed in {interaction.guild}: {type.value}")
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
            
            embed = discord.Embed(
                title="⚙️ Mass Role Assignment",
                description="Starting role assignment process...",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Role",
                value=f"{role.mention}",
                inline=False
            )
            progress_msg = await interaction.followup.send(embed=embed)
            
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
                        embed.description = f"Processing: {success_count + fail_count}/{total_members} members..."
                        await progress_msg.edit(embed=embed)
                except Exception as e:
                    fail_count += 1
                    error_users.append(f"❌ {member.name} ({str(e)})")

            final_embed = discord.Embed(
                title="⚙️ Mass Role Assignment",
                description="Role assignment process completed.",
                color=discord.Color.blue()
            )
            
            final_embed.add_field(
                name="📊 Results",
                value=f"```\nSuccess: {success_count} members\nFailed: {fail_count} members\nTotal: {total_members} members\n```",
                inline=False
            )
            
            if error_users and fail_count < 10:
                final_embed.add_field(
                    name="⚠️ Failed Assignments",
                    value="\n".join(error_users[:10]),
                    inline=False
                )

            final_embed.add_field(
                name="Role",
                value=f"{role.mention}",
                inline=False
            )
            
            final_embed.set_footer(text="Administrative Command • Role Management")

            await progress_msg.edit(embed=final_embed)
            logger.info(f"Mass role assignment completed in {interaction.guild}: {role.name}")
        except Exception as e:
            logger.error(f"Error in mass role assignment: {e}")
            error_embed = discord.Embed(
                title="⚙️ Configuration Error",
                description="❌ Failed to complete mass role assignment.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoRole(bot))

