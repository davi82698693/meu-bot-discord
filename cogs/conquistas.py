import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands


DATA_DIR = (
    os.getenv("CONQUISTAS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "conquistas_data.json")


CONQUISTAS = {
    "primeira_compra": {"nome": "🛍️ Primeira Compra", "descricao": "Fez a primeira compra na loja."},
    "nivel_10": {"nome": "⭐ Nível 10", "descricao": "Alcançou o nível 10."},
    "nivel_25": {"nome": "🌟 Nível 25", "descricao": "Alcançou o nível 25."},
    "nivel_50": {"nome": "💫 Nível 50", "descricao": "Alcançou o nível 50."},
    "rico": {"nome": "💰 Milionário", "descricao": "Acumulou 1.000.000 de moedas."},
    "sortudo": {"nome": "🍀 Sortudo", "descricao": "Ganhou o jackpot no caça-níqueis."},
    "avaliador": {"nome": "⭐ Crítico", "descricao": "Fez a primeira avaliação de uma compra."},
    "veterano": {"nome": "🏆 Veterano", "descricao": "Está no servidor há mais de 30 dias."},
    "convidador": {"nome": "📨 Divulgador", "descricao": "Convidou 5 pessoas pro servidor."},
    "colecionador": {"nome": "🎖️ Colecionador", "descricao": "Desbloqueou 5 conquistas diferentes."},
}


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"usuarios": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("usuarios", {})
            return dados
    except Exception:
        return {"usuarios": {}}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar conquistas_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.gold()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🏆 Conquistas")

    return embed


class Conquistas(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    def salvar(self):

        salvar_dados(self.dados)


    async def desbloquear(self, user, chave, canal_para_avisar=None):
        """
        Chamado por OUTROS cogs pra dar uma conquista.
        Uso: conquistas_cog = bot.get_cog("Conquistas")
             if conquistas_cog: await conquistas_cog.desbloquear(member, "primeira_compra")
        """

        if chave not in CONQUISTAS:
            return False

        usuario = self.dados["usuarios"].setdefault(str(user.id), [])

        if chave in usuario:
            return False

        usuario.append(chave)
        self.salvar()

        info = CONQUISTAS[chave]

        if canal_para_avisar:

            try:
                await canal_para_avisar.send(
                    embed=embed_padrao(
                        "🎉 Nova Conquista Desbloqueada!",
                        f"{user.mention} desbloqueou **{info['nome']}**!\n_{info['descricao']}_",
                        discord.Color.gold()
                    )
                )
            except Exception:
                pass

        if len(usuario) >= 5 and "colecionador" not in usuario:
            await self.desbloquear(user, "colecionador", canal_para_avisar)

        return True


    @commands.hybrid_command(name="conquistas")
    async def conquistas_cmd(self, ctx, membro: discord.Member = None):

        membro = membro or ctx.author

        desbloqueadas = self.dados["usuarios"].get(str(membro.id), [])

        embed = embed_padrao(
            f"🏆 Conquistas de {membro.display_name}",
            f"{len(desbloqueadas)} de {len(CONQUISTAS)} desbloqueadas.",
            discord.Color.gold()
        )

        for chave, info in CONQUISTAS.items():

            marcado = "✅" if chave in desbloqueadas else "🔒"

            embed.add_field(
                name=f"{marcado} {info['nome']}",
                value=info["descricao"],
                inline=True
            )

        if membro.display_avatar:
            embed.set_thumbnail(url=membro.display_avatar.url)

        await ctx.send(embed=embed)


    @commands.hybrid_command(name="conquistas-ranking")
    async def conquistas_ranking(self, ctx):

        lista = sorted(
            self.dados["usuarios"].items(),
            key=lambda x: -len(x[1])
        )[:10]

        if not lista:
            return await ctx.send(embed=embed_padrao("🏆 Ranking de Conquistas", "Ninguém desbloqueou nada ainda.", discord.Color.orange()))

        texto = "\n".join(f"**{i}.** <@{uid}> — {len(c)} conquista(s)" for i, (uid, c) in enumerate(lista, start=1))

        await ctx.send(embed=embed_padrao("🏆 Ranking de Conquistas", texto, discord.Color.gold()))


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        pass


async def setup(bot):

    await bot.add_cog(
        Conquistas(bot)
    )
