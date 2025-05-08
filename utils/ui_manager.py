import discord

class UIManager:
    @staticmethod
    def error_embed(title: str, description: str) -> discord.Embed:
        """Create an error embed"""
        return discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red()
        )

    @staticmethod
    def success_embed(title: str, description: str) -> discord.Embed:
        """Create a success embed"""
        return discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green()
        )

    @staticmethod
    def info_embed(title: str, description: str) -> discord.Embed:
        """Create an info embed"""
        return discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=discord.Color.blue()
        )

    @staticmethod
    def warning_embed(title: str, description: str) -> discord.Embed:
        """Create a warning embed"""
        return discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=discord.Color.yellow()
        )