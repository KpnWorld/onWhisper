from utils.features import FeatureType

// ...existing imports...

class WhisperCog(commands.Cog):
    // ...existing init code...

    async def _get_whisper_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get whisper settings"""
        settings = await self.bot.features.get_feature_settings(
            guild_id,
            FeatureType.WHISPERS
        )
        return settings if settings and settings['enabled'] else None

    @app_commands.command(name="whisper")
    // ...existing decorators...
    async def whisper(self, interaction: discord.Interaction, action: str, user: Optional[discord.User] = None):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server!", 
                ephemeral=True
            )

        settings = await self._get_whisper_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message(
                "❌ Whisper system is currently disabled.",
                ephemeral=True
            )

        if action == "create":
            // ...existing permission checks...
            
            try:
                # Create thread
                thread = await self._create_whisper_thread(
                    interaction.guild,
                    user,
                    settings['options']
                )
                
                # Update settings with new thread
                await self.bot.features.update_whisper_thread(
                    interaction.guild.id,
                    thread.id,
                    {
                        'user_id': user.id,
                        'created_at': time.time(),
                        'is_closed': False
                    }
                )
                
                await interaction.response.send_message(
                    f"✅ Created whisper thread for {user.mention}",
                    ephemeral=True
                )
                
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Error: {str(e)}",
                    ephemeral=True
                )

    // ...rest of existing code...
