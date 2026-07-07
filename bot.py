import os
import discord
from discord.ext import commands

# Configura intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Evento de inicialização
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Bot Profissional 🚀"))

# -------------------------------
# Comandos básicos
# -------------------------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latência: {bot.latency*1000:.2f}ms")

@bot.command()
async def oi(ctx):
    await ctx.send(f"Olá {ctx.author.mention}, tudo certo? 😎")

@bot.command()
async def soma(ctx, a: int, b: int):
    await ctx.send(f"A soma de {a} + {b} é {a+b}")

# -------------------------------
# Comandos de moderação
# -------------------------------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Sem motivo"):
    await member.kick(reason=reason)
    await ctx.send(embed=discord.Embed(
        title="👢 Usuário Expulso",
        description=f"{member.mention} foi expulso.\nMotivo: {reason}",
        color=discord.Color.red()
    ))

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Sem motivo"):
    await member.ban(reason=reason)
    await ctx.send(embed=discord.Embed(
        title="🔨 Usuário Banido",
        description=f"{member.mention} foi banido.\nMotivo: {reason}",
        color=discord.Color.dark_red()
    ))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(embed=discord.Embed(
        title="🧹 Chat Limpo",
        description=f"Foram apagadas {amount} mensagens.",
        color=discord.Color.orange()
    ), delete_after=5)

# -------------------------------
# Comandos de utilidade
# -------------------------------
@bot.command()
async def avatar(ctx, member: discord.Member=None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar de {member}", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title="📊 Informações do Servidor", color=discord.Color.green())
    embed.add_field(name="Nome", value=guild.name, inline=True)
    embed.add_field(name="Membros", value=guild.member_count, inline=True)
    embed.add_field(name="Canais", value=len(guild.channels), inline=True)
    embed.add_field(name="Dono", value=guild.owner.mention, inline=True)
    await ctx.send(embed=embed)

# -------------------------------
# Comandos de diversão
# -------------------------------
@bot.command()
async def dado(ctx, lados: int=6):
    import random
    resultado = random.randint(1, lados)
    await ctx.send(f"🎲 Você rolou um dado de {lados} lados e saiu: **{resultado}**")

@bot.command()
async def moeda(ctx):
    import random
    resultado = random.choice(["Cara", "Coroa"])
    await ctx.send(f"🪙 Deu **{resultado}**")

# -------------------------------
# Sistema de ajuda customizado
# -------------------------------
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="📖 Menu de Comandos", description="Lista de comandos disponíveis:", color=discord.Color.purple())
    embed.add_field(name="Básicos", value="!ping, !oi, !soma", inline=False)
    embed.add_field(name="Moderação", value="!kick, !ban, !clear", inline=False)
    embed.add_field(name="Utilidades", value="!avatar, !serverinfo", inline=False)
    embed.add_field(name="Diversão", value="!dado, !moeda", inline=False)
    await ctx.send(embed=embed)

# -------------------------------
# Rodar o bot
# -------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
