import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils.db_manager import DBManager
from utils.ui_manager import UIManager

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DBManager()
        self.ui_manager = UIManager(bot)
        self.xp_rate = 10  # Default XP per message
        self.xp_cooldown = 10  # Cooldown in seconds
        self.level_roles = {}  # level: role_name

    def calculate_level(self, xp: int) -> int:
        return int(xp ** 0.5)

    async def check_role_assignment(self, user: discord.Member, level: int):
        if level in self.level_roles:
            role = discord.utils.get(user.guild.roles, name=self.level_roles[level])
            if role and role not in user.roles:
                await user.add_roles(role)
                await self.remove_lower_level_roles(user, level)

    async def remove_lower_level_roles(self, user: discord.Member, new_level: int):
        for level, role_name in self.level_roles.items():
            if level < new_level:
                role = discord.utils.get(user.guild.roles, name=role_name)
                if role in user.roles:
                    await user.remove_roles(role)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = str(message.author.id)
        now = datetime.utcnow()

        async with self.db_manager.db.execute(
            "SELECT xp, level, last_xp_gain FROM leveling WHERE user_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()

        if result is None:
            await self.db_manager.db.execute(
                "INSERT INTO leveling (user_id, xp, level, last_xp_gain) VALUES (?, ?, ?, ?)",
                (user_id, 0, 1, now.strftime("%Y-%m-%d %H:%M:%S")),
            )
            await self.db_manager.db.commit()
            return

        xp, level, last_gain = result
        last_gain = datetime.strptime(last_gain, "%Y-%m-%d %H:%M:%S")

        if now - last_gain < timedelta(seconds=self.xp_cooldown):
            return  # Still on cooldown

        xp += self.xp_rate
        new_level = self.calculate_level(xp)

        await self.db_manager.db.execute(
            "UPDATE leveling SET xp = ?, level = ?, last_xp_gain = ? WHERE user_id = ?",
            (xp, new_level, now.strftime("%Y-%m-%d %H:%M:%S"), user_id),
        )
        await self.db_manager.db.commit()

        await self.check_role_assignment(message.author, new_level)
        await self.ui_manager.send_xp_update(message.author, xp, new_level, message.channel)

    # =========================
    # 🔧 Admin Commands
    # =========================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_xp_rate(self, ctx, rate: int):
        """Admin: Set how much XP a message gives"""
        self.xp_rate = rate
        await self.ui_manager.send_embed(
            ctx,
            title="XP Rate Updated",
            description=f"XP per message is now set to **{rate}**.",
            command_type="Administrator"
        )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_xp_cooldown(self, ctx, seconds: int):
        """Admin: Set cooldown in seconds between XP gains"""
        self.xp_cooldown = seconds
        await self.ui_manager.send_embed(
            ctx,
            title="XP Cooldown Updated",
            description=f"Users can now gain XP every **{seconds} seconds**.",
            command_type="Administrator"
        )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_level_role(self, ctx, level: int, role: discord.Role):
        """Admin: Set a role to be given at a certain level"""
        self.level_roles[level] = role.name
        await self.ui_manager.send_embed(
            ctx,
            title="Level Role Set",
            description=f"Role **{role.name}** will be given at **Level {level}**.",
            command_type="Administrator"
        )

    # =========================
    # 👤 User Command - Level Check
    # =========================

    @commands.command()
    async def level(self, ctx, user: discord.User = None):
        """Check your or another user's level + XP"""
        user = user or ctx.author
        user_id = str(user.id)

        async with self.db_manager.db.execute(
            "SELECT xp, level FROM leveling WHERE user_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            xp, level = result
            await self.ui_manager.send_embed(
                ctx,
                title=f"{user.name}'s Level Info",
                description=f"**Level:** {level}\n**XP:** {xp}",
                command_type="User"
            )
        else:
            await self.ui_manager.send_embed(
                ctx,
                title="No XP Yet",
                description=f"{user.name} hasn't earned any XP yet. Get chatting!",
                command_type="User"
            )

async def setup(bot):
    await bot.add_cog(Leveling(bot))
