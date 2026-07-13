import discord
import os
import json
import re

from datetime import datetime, timezone

from discord.ext import commands, tasks


DATA_DIR = (
    os.getenv("ANIVERSARIOS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "aniversarios_data.json")


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
        print(f"⚠️ Erro ao salvar aniversarios_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🎂 Aniversários")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"datas": {}, "canal": None, "ultimo_check": None})


class Aniversarios(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()

        self.checar_aniversarios.start()


    def cog_unload(self):

        self.checar_aniversarios.cancel()


    def salvar(self):

        salvar_dados(self.dados)


    @tasks.loop(hours=1)
    async def checar_aniversarios(self):

        hoje = datetime.now(timezone.utc)
        hoje_str = hoje.strftime("%d/%m")
        marcador = hoje.strftime("%Y-%m-%d")

        for guild in self.bot.guilds:

            conf = config(self.dados, guild.id)

            if conf.get("ultimo_check") == marcador:
                continue

            canal_id = conf.get("canal")

            if canal_id is None:
                continue

            canal = guild.get_channel(canal_id)

            if canal is None:
                continue

            aniversariantes = [
                uid for uid, data in conf["datas"].items()
                if data == hoje_str
            ]

            if aniversariantes:

                mencoes = " ".join(f"<@{uid}>" for uid in aniversariantes)

                try:
                    await canal.send(
                        content=mencoes,
                        embed=embed_padrao(
                            "🎉 Feliz Aniversário!",
                            f"Hoje é dia de comemorar! Parabéns {mencoes}! 🎂🎈",
                            discord.Color.gold()
                        )
                    )
                except Exception:
                    pass

            conf["ultimo_check"] = marcador
            self.salvar()


    @checar_aniversarios.before_loop
    async def antes_de_checar(self):

        await self.bot.wait_until_ready()


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.command(name="aniversario")
    async def aniversario(self, ctx, data: str = None):

        if data is None:

            conf = config(self.dados, ctx.guild.id)

            data_salva = conf["datas"].get(str(ctx.author.id))

            if data_salva:
                return await ctx.send(embed=embed_padrao("🎂 Seu aniversário", f"Está definido como **{data_salva}**.", discord.Color.blurple()))
            else:
                return await ctx.send(embed=embed_padrao("🎂 Aniversário", "Você ainda não definiu. Use `!aniversario DD/MM`.", discord.Color.orange()))

        if not re.match(r"^\d{2}/\d{2}$", data):
            return await ctx.send(embed=embed_padrao("❌ Formato inválido", "Use o formato `DD/MM`, exemplo: `!aniversario 25/12`.", discord.Color.red()))

        dia, mes = data.split("/")

        if not (1 <= int(dia) <= 31 and 1 <= int(mes) <= 12):
            return await ctx.send(embed=embed_padrao("❌ Data inválida", "Confira o dia e o mês.", discord.Color.red()))

        conf = config(self.dados, ctx.guild.id)

        conf["datas"][str(ctx.author.id)] = data

        self.salvar()

        await ctx.send(embed=embed_padrao("✅ Aniversário salvo!", f"Vamos te parabenizar em **{data}**. 🎉", discord.Color.green()))


    @commands.command(name="aniversarios-canal")
    @commands.has_permissions(administrator=True)
    async def aniversarios_canal(self, ctx, canal: discord.TextChannel):

        conf = config(self.dados, ctx.guild.id)

        conf["canal"] = canal.id

        self.salvar()

        await ctx.send(embed=embed_padrao("✅ Canal definido", f"Aniversários serão anunciados em {canal.mention}.", discord.Color.green()))


    @commands.command(name="aniversarios-lista")
    async def aniversarios_lista(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        if not conf["datas"]:
            return await ctx.send(embed=embed_padrao("🎂 Aniversários", "Ninguém cadastrou aniversário ainda.", discord.Color.orange()))

        ordenados = sorted(conf["datas"].items(), key=lambda x: (int(x[1].split("/")[1]), int(x[1].split("/")[0])))

        texto = "\n".join(f"🎂 **{data}** — <@{uid}>" for uid, data in ordenados)

        await ctx.send(embed=embed_padrao("🎂 Lista de Aniversários", texto, discord.Color.blurple()))


async def setup(bot):

    await bot.add_cog(
        Aniversarios(bot)
    )
