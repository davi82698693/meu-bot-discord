import os
import discord
from discord.ext import commands

# Configura intents (necessário para ler mensagens)
intents = discord.Intents.default()
intents.message_content = True

# Cria o bot com prefixo !
bot = commands.Bot(command_prefix="!", intents=intents)

# Exemplo de comando
@bot.command()
async def oi(ctx):
    await ctx.send("Olá! Eu sou um bot Python 😎")

# Pega o token da variável de ambiente
TOKEN = os.getenv("DISCORD_TOKEN")

# Inicia o bot
bot.run(TOKEN)

