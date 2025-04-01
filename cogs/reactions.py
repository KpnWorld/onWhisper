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
        logger.info("Reaction Roles cog initialized")

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
                await interaction.response.send_message(
                    "❌ I need Manage Roles permission to set up reaction roles.",
                    ephemeral=True
                )
                return

            if role.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message(
                    "❌ I cannot assign roles higher than my highest role.",
                    ephemeral=True
                )
                return

            # Create the reaction role message
            embed = discord.Embed(
                title="Role Assignment",
                description=f"React with {emoji} to get the {role.mention} role\n\n{description}",
                color=role.color
            )
            embed.set_footer(text=f"Role ID: {role.id}")

            await interaction.response.send_message("Creating reaction role message...", ephemeral=True)
            message = await target_channel.send(embed=embed)
            await message.add_reaction(emoji)

            # Save to database
            with self.db.cursor() as cur:
                cur.execute("""
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

            await interaction.edit_original_response(content="✅ Reaction role created successfully!")
            logger.info(f"Reaction role created for role {role.name} in {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error creating reaction role: {e}")
            await interaction.followup.send(
                "❌ An error occurred while setting up the reaction role.",
                ephemeral=True
            )

    @app_commands.command(name="removereactrole", description="Remove a reaction role message")
    @app_commands.describe(message_id="The ID of the reaction role message to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def removereactrole(self, interaction: discord.Interaction, message_id: str):
        try:
            # Find reaction role in database
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT channel_id 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (interaction.guild_id, int(message_id)))
                result = cur.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ No reaction role found with that message ID.",
                    ephemeral=True
                )
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
            with self.db.cursor() as cur:
                cur.execute("""
                    DELETE FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (interaction.guild_id, int(message_id)))

            await interaction.response.send_message("✅ Reaction role removed successfully!", ephemeral=True)
            logger.info(f"Reaction role removed in {interaction.guild.name}")
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error removing reaction role: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while removing the reaction role.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        try:
            # Check if this is a reaction role message
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT role_id, emoji 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (payload.guild_id, payload.message_id))
                result = cur.fetchone()

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
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT role_id, emoji 
                    FROM reaction_roles 
                    WHERE guild_id = ? AND message_id = ?
                """, (payload.guild_id, payload.message_id))
                result = cur.fetchone()

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
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT message_id, channel_id, emoji, role_id, description 
                    FROM reaction_roles 
                    WHERE guild_id = ?
                    ORDER BY message_id DESC
                """, (interaction.guild_id,))
                roles = cur.fetchall()

            if not roles:
                await interaction.response.send_message(
                    "No reaction roles set up in this server.",
                    ephemeral=True
                )
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

            await interaction.response.send_message(embed=embed)
            logger.info(f"Listed reaction roles for {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error listing reaction roles: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching reaction roles.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
