import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, ChannelSelect


DATA_DIR = (
    os.getenv("LOGS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "logs_config.json")

CATEGORIAS = {
    "geral": "📋 Geral (usado quando uma categoria não tem canal próprio)",
    "moderacao": "🛡️ Moderação",
    "tickets": "🎫 Tickets",
    "loja": "🛒 Loja",
    "sorteio": "🎉 Sorteios",
    "cargos": "🎭 Cargos Automáticos",
    "sugestoes": "💡 Sugestões",
    "boasvindas": "👋 Boas-vindas",
    "antispam": "🚫 Anti-spam",
}


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
        print(f"⚠️ Erro ao salvar logs_config.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="📋 Sistema de Logs")

    return embed


# ==========================================================
# FUNÇÕES PÚBLICAS (usadas pelos outros cogs)
# ==========================================================

def obter_canal_log(bot, guild, categoria):
    """
    Retorna o canal configurado pra essa categoria (ou o canal 'geral'
    como fallback). Devolve None se nada estiver configurado.
    """

    if guild is None:
        return None

    dados = carregar_dados()

    conf = dados.get(str(guild.id), {})

    canal_id = conf.get(categoria) or conf.get("geral")

    if canal_id is None:
        return None

    return guild.get_channel(canal_id)


async def enviar_log(bot, guild, categoria, titulo, descricao, cor=discord.Color.blurple()):
    """
    Função pronta pra outros cogs chamarem direto:
    from .logs import enviar_log
    await enviar_log(bot, guild, "moderacao", "🔨 Ban", "texto...", discord.Color.red())
    """

    canal = obter_canal_log(bot, guild, categoria)

    if canal is None:
        return

    try:
        await canal.send(embed=embed_padrao(titulo, descricao, cor))
    except Exception:
        pass


# ==========================================================
# COG
# ==========================================================

class Logs(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    def salvar(self):

        salvar_dados(self.dados)


    def config(self, guild_id):

        return self.dados.setdefault(str(guild_id), {})


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.command(name="logs-painel")
    @commands.has_permissions(administrator=True)
    async def logs_painel(self, ctx):

        conf = self.config(ctx.guild.id)

        await ctx.send(
            embed=gerar_embed_painel(ctx.guild, conf),
            view=PainelLogsView(self)
        )


async def setup(bot):

    await bot.add_cog(
        Logs(bot)
    )


# ==========================================================
# PAINEL
# ==========================================================

def gerar_embed_painel(guild, conf):

    embed = embed_padrao(
        "🛠️ Painel de Logs",
        "Escolha uma categoria no menu abaixo e depois o canal onde os logs dela devem cair.\n"
        "Categorias sem canal próprio usam o canal **Geral**, se ele estiver configurado.",
        discord.Color.blurple()
    )

    texto = ""

    for chave, nome in CATEGORIAS.items():

        canal_id = conf.get(chave)

        canal_txt = f"<#{canal_id}>" if canal_id else "`Não definido`"

        texto += f"{nome}: {canal_txt}\n"

    embed.add_field(name="Configuração atual", value=texto, inline=False)

    return embed


class SelecionarCategoriaLog(Select):

    def __init__(self, cog):

        self.cog = cog

        opcoes = [
            discord.SelectOption(label=nome[:100], value=chave)
            for chave, nome in CATEGORIAS.items()
        ]

        super().__init__(placeholder="Escolha a categoria pra configurar", options=opcoes, row=0)


    async def callback(self, interaction: discord.Interaction):

        categoria = self.values[0]

        await interaction.response.send_message(
            f"Escolha o canal para **{CATEGORIAS[categoria]}**:",
            view=SelecionarCanalLogView(self.cog, categoria),
            ephemeral=True
        )


class SelecionarCanalLog(ChannelSelect):

    def __init__(self, cog, categoria):

        self.cog = cog
        self.categoria = categoria

        super().__init__(
            placeholder="Escolha o canal",
            channel_types=[discord.ChannelType.text]
        )


    async def callback(self, interaction: discord.Interaction):

        canal_selecionado = self.values[0]

        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)

        conf = self.cog.config(interaction.guild.id)
        conf[self.categoria] = canal.id
        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"✅ **{CATEGORIAS[self.categoria]}** agora manda logs em {canal.mention}.",
            view=None
        )


class SelecionarCanalLogView(View):

    def __init__(self, cog, categoria):

        super().__init__(timeout=120)

        self.add_item(SelecionarCanalLog(cog, categoria))


class PainelLogsView(View):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog

        self.add_item(SelecionarCategoriaLog(cog))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelLogsView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
