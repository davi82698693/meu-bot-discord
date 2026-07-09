import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)
# ==========================
# ONLINE
# ==========================
@bot.event
async def on_ready():
    print("==============================")
    print(f"Bot online: {bot.user}")
    print("==============================")
    await bot.change_presence(
        activity=discord.Game(
            name="Servidor Profissional 🚀"
        )
    )
# ==========================
# COGS
# ==========================
async def load_cogs():
    for arquivo in os.listdir("./cogs"):
        if arquivo.endswith(".py"):
            await bot.load_extension(
                f"cogs.{arquivo[:-3]}"
            )
            print(
                f"Cog carregado: {arquivo}"
            )
# ==========================
# START
# ==========================
async def main():
    async with bot:
        await load_cogs()
        token = os.getenv(
            "DISCORD_TOKEN"
        )
        await bot.start(token)
asyncio.run(main())
