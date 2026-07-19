import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands


DATA_DIR = (
    os.getenv("CONVITES_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "convites_data.json")


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar convites_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="📨 Sistema de Convites")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"convidou_por": {}, "contagem": {}})


class Convites(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()

        self.cache_convites = {}


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_load(self):

        for guild in self.bot.guilds:
            await self._atualizar_cache(guild)


    async def _atualizar_cache(self, guild):

        try:
            convites = await guild.invites()
            self.cache_convites[guild.id] = {c.code: c.uses for c in convites}
        except discord.Forbidden:
            print(f"⚠️ Sem permissão 'Gerenciar Servidor' pra ver convites em {guild.name}.")
        except Exception as e:
            print(f"⚠️ Erro ao cachear convites de {guild.name}: {e}")


    @commands.Cog.listener()
    async def on_ready(self):

        for guild in self.bot.guilds:
            await self._atualizar_cache(guild)


    @commands.Cog.listener()
    async def on_invite_create(self, invite):

        cache = self.cache_convites.setdefault(invite.guild.id, {})
        cache[invite.code] = invite.uses


    @commands.Cog.listener()
    async def on_invite_delete(self, invite):

        cache = self.cache_convites.get(invite.guild.id, {})
        cache.pop(invite.code, None)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        if member.bot:
            return

        guild = member.guild

        cache_antigo = self.cache_convites.get(guild.id, {})

        try:
            convites_atuais = await guild.invites()
        except Exception:
            return

        convite_usado = None

        for convite in convites_atuais:

            usos_antigos = cache_antigo.get(convite.code, 0)

            if convite.uses > usos_antigos:
                convite_usado = convite
                break

        self.cache_convites[guild.id] = {c.code: c.uses for c in convites_atuais}

        if convite_usado is None or convite_usado.inviter is None:
            return

        conf = config(self.dados, guild.id)

        inviter_id = str(convite_usado.inviter.id)

        conf["convidou_por"][str(member.id)] = inviter_id

        conf["contagem"][inviter_id] = conf["contagem"].get(inviter_id, 0) + 1

        self.salvar()

        if conf["contagem"][inviter_id] >= 5:

            conquistas = self.bot.get_cog("Conquistas")

            if conquistas is not None:

                try:
                    await conquistas.desbloquear(convite_usado.inviter, "convidador", canal_para_avisar=None)
                except Exception:
                    pass


    @commands.hybrid_command(name="convites")
    async def convites_cmd(self, ctx, membro: discord.Member = None):

        membro = membro or ctx.author

        conf = config(self.dados, ctx.guild.id)

        total = conf["contagem"].get(str(membro.id), 0)

        await ctx.send(
            embed=embed_padrao(
                f"📨 Convites de {membro.display_name}",
                f"Trouxe **{total}** membro(s) pro servidor.",
                discord.Color.blurple()
            )
        )


    @commands.hybrid_command(name="convites-ranking")
    async def convites_ranking(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        lista = sorted(conf["contagem"].items(), key=lambda x: -x[1])[:10]

        if not lista:
            return await ctx.send(embed=embed_padrao("📨 Ranking de Convites", "Ninguém convidou ninguém ainda.", discord.Color.orange()))

        texto = "\n".join(f"**{i}.** <@{uid}> — {qtd} convite(s)" for i, (uid, qtd) in enumerate(lista, start=1))

        await ctx.send(embed=embed_padrao("📨 Ranking de Convites", texto, discord.Color.gold()))


async def setup(bot):

    await bot.add_cog(
        Convites(bot)
    )
