import discord
import os
import json
import random
import time

from datetime import datetime, timezone

from discord.ext import commands


DATA_DIR = (
    os.getenv("NIVEIS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "niveis_data.json")

XP_MIN, XP_MAX = 15, 25
COOLDOWN_XP = 60

BONUS_MOEDAS_LEVEL_UP = 100


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"usuarios": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("usuarios", {})
            return dados
    except Exception as e:
        print(f"⚠️ Erro ao carregar niveis_data.json: {e}")
        return {"usuarios": {}}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar niveis_data.json: {e}")


def xp_para_nivel(nivel):

    return 5 * (nivel ** 2) + 50 * nivel + 100


def barra_progresso(atual, total, tamanho=15):

    if total <= 0:
        preenchido = 0
    else:
        preenchido = int((atual / total) * tamanho)

    preenchido = max(0, min(tamanho, preenchido))

    return "🟩" * preenchido + "⬛" * (tamanho - preenchido)


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="📈 Sistema de Níveis")

    return embed


class Niveis(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()

        self.cooldowns = {}


    def salvar(self):

        salvar_dados(self.dados)


    def obter_usuario(self, user_id):

        uid = str(user_id)

        if uid not in self.dados["usuarios"]:

            self.dados["usuarios"][uid] = {"xp": 0, "nivel": 0}

        return self.dados["usuarios"][uid]


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot or message.guild is None:
            return

        if not message.content.strip():
            return

        agora = time.time()

        ultimo = self.cooldowns.get(message.author.id, 0)

        if agora - ultimo < COOLDOWN_XP:
            return

        self.cooldowns[message.author.id] = agora

        usuario = self.obter_usuario(message.author.id)

        usuario["xp"] += random.randint(XP_MIN, XP_MAX)

        subiu = False

        while usuario["xp"] >= xp_para_nivel(usuario["nivel"]):

            usuario["xp"] -= xp_para_nivel(usuario["nivel"])
            usuario["nivel"] += 1
            subiu = True

        self.salvar()

        if subiu:

            embed = embed_padrao(
                "🎉 Level Up!",
                f"{message.author.mention} subiu para o **nível {usuario['nivel']}**!",
                discord.Color.gold()
            )

            jogos = self.bot.get_cog("Jogos")

            if jogos is not None:

                try:
                    jogos.adicionar(message.author.id, BONUS_MOEDAS_LEVEL_UP)
                    jogos.salvar()
                    embed.description += f"\n💰 Bônus: **{BONUS_MOEDAS_LEVEL_UP} 🪙**"
                except Exception:
                    pass

            try:
                await message.channel.send(embed=embed)
            except Exception:
                pass


    @commands.command(name="rank", aliases=["nivel", "level"])
    async def rank(self, ctx, membro: discord.Member = None):

        membro = membro or ctx.author

        usuario = self.obter_usuario(membro.id)

        necessario = xp_para_nivel(usuario["nivel"])

        barra = barra_progresso(usuario["xp"], necessario)

        embed = embed_padrao(
            f"📈 Nível de {membro.display_name}",
            f"🏆 **Nível:** {usuario['nivel']}\n"
            f"✨ **XP:** {usuario['xp']} / {necessario}\n"
            f"{barra}",
            discord.Color.blurple()
        )

        if membro.display_avatar:
            embed.set_thumbnail(url=membro.display_avatar.url)

        await ctx.send(embed=embed)


    @commands.command(name="levels", aliases=["ranking-niveis", "topniveis"])
    async def levels(self, ctx):

        lista = sorted(
            self.dados["usuarios"].items(),
            key=lambda x: (x[1]["nivel"], x[1]["xp"]),
            reverse=True
        )[:10]

        if not lista:
            return await ctx.send(embed=embed_padrao("📈 Ranking de Níveis", "Ninguém tem XP registrado ainda.", discord.Color.orange()))

        texto = ""

        for i, (uid, dados) in enumerate(lista, start=1):

            texto += f"**{i}.** <@{uid}> — Nível {dados['nivel']} ({dados['xp']} XP)\n"

        await ctx.send(embed=embed_padrao("📈 Ranking de Níveis", texto, discord.Color.gold()))


async def setup(bot):

    await bot.add_cog(
        Niveis(bot)
    )
