import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def oi(ctx):
    await ctx.send("Olá! Eu sou um bot Python 😎")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
