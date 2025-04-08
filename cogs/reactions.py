import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        bot.loop.create_task(self._init_db())
        logger.info("Reaction Roles cog initialized")

    async def _init_db(self):
        """Initialize database and ensure guild settings exist"""
        try:
            for guild in self.bot.guilds:
                await self.db.ensure_guild_exists(guild.id)
            logger.info("Reaction Roles database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize reaction roles database: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Initialize settings when bot joins a new guild"""
        try:
            await self.db.ensure_guild_exists(guild.id)
            logger.info(f"Initialized reaction roles for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to initialize reaction roles for guild {guild.name}: {e}")

    @app_commands.command(name="reactrole", description="Create a reaction role message")
    @app_commands.describe(
        role="The role to assign",
        emoji="The emoji to react with",
        description="Description of the role",
        channel="Channel to send the message in"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def reactrole(
        self, 
        interaction: discord.Interaction, 
        role: discord.Role,
        emoji: str,
        description: str,
        channel: Optional[discord.TextChannel] = None
    ):
        try:
            target_channel = channel or interaction.channel
            
            # Verify bot permissions
            if not interaction.guild.me.guild_permissions.manage_roles:
                error_embed = discord.Embed(
                    title="❌ Permission Error",
                    description="I need Manage Roles permission to set up reaction roles.",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text="Administrative Command • Error")
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            if role.position >= interaction.guild.me.top_role.position:
                error_embed = discord.Embed(
                    title="❌ Role Hierarchy Error",
                    description="I cannot assign roles higher than my highest role.",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text="Administrative Command • Error")
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # Create the reaction role message with consistent style
            embed = discord.Embed(
                title="🎭 Role Assignment",
                description=f"React with {emoji} to get the {role.mention} role",
                color=role.color if role.color != discord.Color.default() else discord.Color.blue()
            )
            
            # Add description field if provided
            if description:
                embed.add_field(name="ℹ️ About this role", value=description, inline=False)
            
            embed.set_footer(text=f"Role ID: {role.id} • Reaction Roles")

            progress_msg = await interaction.response.send_message(
                "⚙️ Creating reaction role...", 
                ephemeral=True
            )
            message = await target_channel.send(embed=embed)
            await message.add_reaction(emoji)

            # Save to database
            async with self.db.cursor() as cur:
                await cur.execute("""
                    INSERT INTO reaction_roles 
                    (guild_id, channel_id, message_id, emoji, role_id, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    interaction.guild_id,
                    target_channel.id,
                    message.id,
                    emoji,
                    role.id,
                    description
                ))

            # Success message with consistent style
            success_embed = discord.Embed(
                title="✅ Reaction Role Created",
                description="Role assignment has been configured successfully.",
                color=discord.Color.green()
            )
            success_embed.add_field(
                name="Details",
                value=f"```\nRole: {role.name}\nEmoji: {emoji}\nChannel: {target_channel.name}\n```",
                inline=False
            )
            success_embed.set_footer(text="Administrative Command • Reaction Roles")
            
            await interaction.edit_original_response(embed=success_embed)
            logger.info(f"Reaction role created: {role.name} in {interaction.guild.name}")

        except Exception as e:
            logger.error(f"Error creating reaction role: {e}")
            error_embed = discord.Embed(
                title="❌ Configuration Error",
                description="Failed to set up reaction role.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @app_commands.command(name="removereactrole", description="Remove a reaction role message")
    @app_commands.describe(message_id="The ID of the reaction role message to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def removereactrole(self, interaction: discord.Interaction, message_id: str):
        try:
            # Find reaction role in database
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT channel_id 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (interaction.guild_id, int(message_id)))
                result = await cur.fetchone()

            if not result:
                error_embed = discord.Embed(
                    title="❌ Not Found",
                    description="No reaction role found with that message ID.",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text="Administrative Command • Error")
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # Delete the message
            channel = interaction.guild.get_channel(result[0])
            if channel:
                try:
                    message = await channel.fetch_message(int(message_id))
                    await message.delete()
                except discord.NotFound:
                    pass  # Message already deleted

            # Remove from database
            async with self.db.cursor() as cur:
                await cur.execute("""
                    DELETE FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (interaction.guild_id, int(message_id)))

            success_embed = discord.Embed(
                title="✅ Reaction Role Removed",
                description="The reaction role has been removed successfully.",
                color=discord.Color.green()
            )
            success_embed.set_footer(text="Administrative Command • Reaction Roles")
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            logger.info(f"Reaction role removed in {interaction.guild.name}")
        except ValueError:
            error_embed = discord.Embed(
                title="❌ Invalid Input",
                description="Invalid message ID provided.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing reaction role: {e}")
            error_embed = discord.Embed(
                title="❌ Removal Error",
                description="An error occurred while removing the reaction role.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Check if this is a reaction role message
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT role_id, emoji 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (payload.guild_id, payload.message_id))
                result = await cur.fetchone()

            if not result:
                return

            role_id, expected_emoji = result
            if str(payload.emoji) != expected_emoji:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            await member.add_roles(role)
            logger.info(f"Added role {role.name} to {member} in {guild.name}")
        except Exception as e:
            logger.error(f"Error in reaction add handler: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Check if this is a reaction role message
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT role_id, emoji 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (payload.guild_id, payload.message_id))
                result = await cur.fetchone()

            if not result:
                return

            role_id, expected_emoji = result
            if str(payload.emoji) != expected_emoji:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            await member.remove_roles(role)
            logger.info(f"Removed role {role.name} from {member} in {guild.name}")
        except Exception as e:
            logger.error(f"Error in reaction remove handler: {e}")

    @app_commands.command(name="listreactroles", description="List all reaction roles in the server")
    @app_commands.default_permissions(manage_roles=True)
    async def listreactroles(self, interaction: discord.Interaction):
        try:
            async with self.db.cursor() as cur:
                await cur.execute("""
                    SELECT message_id, channel_id, emoji, role_id, description 
                    FROM reaction_roles 
                    WHERE guild_id = ?
                    ORDER BY message_id DESC
                """, (interaction.guild_id,))
                roles = await cur.fetchall()

            if not roles:
                embed = discord.Embed(
                    title="📜 Reaction Roles",
                    description="No reaction roles set up in this server.",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Administrative Command • Reaction Roles")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="🎭 Reaction Roles",
                description="List of all reaction roles in this server",
                color=discord.Color.blue()
            )

            for message_id, channel_id, emoji, role_id, description in roles:
                channel = interaction.guild.get_channel(channel_id)
                role = interaction.guild.get_role(role_id)
                if channel and role:
                    embed.add_field(
                        name=f"{emoji} {role.name}",
                        value=f"Channel: {channel.mention}\nMessage ID: {message_id}\nDescription: {description}",
                        inline=False
                    )

            embed.set_footer(text="Administrative Command • Reaction Roles")
            await interaction.response.send_message(embed=embed)
            logger.info(f"Listed reaction roles for {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error listing reaction roles: {e}")
            error_embed = discord.Embed(
                title="❌ Listing Error",
                description="An error occurred while fetching reaction roles.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Administrative Command • Error")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
