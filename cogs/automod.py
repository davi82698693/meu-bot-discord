import discord
import os
import json

from datetime import datetime, timezone

from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput, ChannelSelect


DATA_DIR = (
    os.getenv("AUTOMOD_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "automod_data.json")


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
        print(f"⚠️ Erro ao salvar automod_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🚨 AutoMod")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"ativo": True, "palavras": [], "canal_log": None})


def container_view(texto, source_view, accent_color=discord.Color.red()):
    """
    Pega os botões/selects já existentes de uma View comum e monta um
    LayoutView com Container (visual novo), sem duplicar a lógica dos botões.
    """

    layout = discord.ui.LayoutView(timeout=None)

    container = discord.ui.Container(accent_color=accent_color)

    container.add_item(discord.ui.TextDisplay(texto))
    container.add_item(discord.ui.Separator())

    por_row = {}

    for item in list(source_view.children):
        por_row.setdefault(item.row or 0, []).append(item)

    for numero in sorted(por_row):

        linha = discord.ui.ActionRow()

        for item in por_row[numero]:
            linha.add_item(item)

        container.add_item(linha)

    layout.add_item(container)

    return layout


def texto_painel(guild, conf):

    status = "🟢 Ativado" if conf.get("ativo", True) else "🔴 Desativado"

    canal_id = conf.get("canal_log")
    canal_txt = f"<#{canal_id}>" if canal_id else "`Não definido`"

    if conf["palavras"]:
        palavras_txt = ", ".join(f"`{p}`" for p in conf["palavras"])
    else:
        palavras_txt = "_Nenhuma palavra proibida ainda._"

    return (
        "## 🚨 Painel do AutoMod\n"
        "Mensagens com essas palavras são apagadas automaticamente, e um aviso "
        "com o autor, horário e conteúdo vai pro canal de log.\n\n"
        f"**Status:** {status}\n"
        f"**Canal de log:** {canal_txt}\n\n"
        f"**Palavras proibidas ({len(conf['palavras'])})**\n{palavras_txt}"
    )


# ==========================================================
# COG
# ==========================================================

class Automod(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        self.bot.add_view(PainelAutomodView(self))


    def salvar(self):

        salvar_dados(self.dados)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot or message.guild is None:
            return

        if message.author.guild_permissions.administrator:
            return

        conf = config(self.dados, message.guild.id)

        if not conf.get("ativo", True) or not conf["palavras"]:
            return

        conteudo = message.content.lower()

        palavra_encontrada = None

        for palavra in conf["palavras"]:

            if palavra.lower() in conteudo:
                palavra_encontrada = palavra
                break

        if palavra_encontrada is None:
            return

        try:
            await message.delete()
        except Exception:
            pass

        canal_id = conf.get("canal_log")

        if canal_id is None:
            return

        canal_log = message.guild.get_channel(canal_id)

        if canal_log is None:
            return

        embed = discord.Embed(
            title="🚫 Mensagem bloqueada pelo AutoMod",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="👤 Usuário", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="📌 Canal", value=message.channel.mention, inline=True)
        embed.add_field(name="🔒 Palavra detectada", value=f"`{palavra_encontrada}`", inline=True)
        embed.add_field(name="💬 Mensagem original", value=message.content[:1000] or "_(vazia)_", inline=False)

        if message.author.display_avatar:
            embed.set_thumbnail(url=message.author.display_avatar.url)

        try:
            await canal_log.send(embed=embed)
        except Exception:
            pass


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="automod-ativar")
    @commands.has_permissions(administrator=True)
    async def automod_ativar(self, ctx):

        conf = config(self.dados, ctx.guild.id)
        conf["ativo"] = True
        self.salvar()

        await ctx.send(embed=embed_padrao("✅ AutoMod ativado", "As palavras proibidas voltaram a ser bloqueadas.", discord.Color.green()))


    @commands.hybrid_command(name="automod-desativar")
    @commands.has_permissions(administrator=True)
    async def automod_desativar(self, ctx):

        conf = config(self.dados, ctx.guild.id)
        conf["ativo"] = False
        self.salvar()

        await ctx.send(embed=embed_padrao("🚫 AutoMod desativado", "Nenhuma mensagem será bloqueada até reativar.", discord.Color.orange()))


    @commands.hybrid_command(name="automod-painel")
    @commands.has_permissions(administrator=True)
    async def automod_painel(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        await ctx.send(
            view=container_view(texto_painel(ctx.guild, conf), PainelAutomodView(self))
        )


async def setup(bot):

    await bot.add_cog(
        Automod(bot)
    )


# ==========================================================
# ADICIONAR PALAVRA
# ==========================================================

class ModalAdicionarPalavra(Modal):

    def __init__(self, cog):

        super().__init__(title="🚨 Adicionar Palavra Proibida")

        self.cog = cog

        self.palavras = TextInput(
            label="Palavra(s) — uma por linha",
            style=discord.TextStyle.paragraph,
            placeholder="link na bio\npromoção grátis\n...",
            max_length=500
        )

        self.add_item(self.palavras)


    async def on_submit(self, interaction: discord.Interaction):

        conf = config(self.cog.dados, interaction.guild.id)

        novas = [
            linha.strip().lower()
            for linha in self.palavras.value.splitlines()
            if linha.strip()
        ]

        adicionadas = 0

        for palavra in novas:

            if palavra not in conf["palavras"]:
                conf["palavras"].append(palavra)
                adicionadas += 1

        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), PainelAutomodView(self.cog))
        )


# ==========================================================
# REMOVER PALAVRA
# ==========================================================

class SelecionarPalavraRemover(Select):

    def __init__(self, cog, conf):

        self.cog = cog

        opcoes = [
            discord.SelectOption(label=p[:100], value=p[:100])
            for p in conf["palavras"]
        ][:25]

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhuma palavra configurada", value="dummy")]

        super().__init__(placeholder="🗑️ Escolha a palavra pra remover", options=opcoes)


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhuma palavra configurada.", ephemeral=True)

        conf = config(self.cog.dados, interaction.guild.id)

        conf["palavras"] = [p for p in conf["palavras"] if p[:100] != self.values[0]]

        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"✅ Palavra removida.",
            view=None
        )


class SelecionarPalavraRemoverView(View):

    def __init__(self, cog, conf):

        super().__init__(timeout=120)

        self.add_item(SelecionarPalavraRemover(cog, conf))


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO SelecionarPalavraRemoverView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("===============================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


# ==========================================================
# ESCOLHER CANAL DE LOG
# ==========================================================

class SelecionarCanalAutomod(ChannelSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(
            placeholder="Escolha o canal de log",
            channel_types=[discord.ChannelType.text],
            row=0,
            custom_id="automod_canal_log"
        )


    async def callback(self, interaction: discord.Interaction):

        canal_selecionado = self.values[0]

        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)

        conf = config(self.cog.dados, interaction.guild.id)
        conf["canal_log"] = canal.id
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self.view)
        )


# ==========================================================
# VIEW PRINCIPAL DO PAINEL
# ==========================================================

class PainelAutomodView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        self.add_item(SelecionarCanalAutomod(cog))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelAutomodView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("===================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="➕ Adicionar Palavra", style=discord.ButtonStyle.success, row=1, custom_id="automod_add_palavra")
    async def adicionar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(ModalAdicionarPalavra(self.cog))


    @discord.ui.button(label="🗑️ Remover Palavra", style=discord.ButtonStyle.danger, row=1, custom_id="automod_remove_palavra")
    async def remover(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)

        await interaction.response.send_message(
            "Escolha a palavra pra remover:",
            view=SelecionarPalavraRemoverView(self.cog, conf),
            ephemeral=True
        )


    @discord.ui.button(label="🟢 Ativar", style=discord.ButtonStyle.success, row=2, custom_id="automod_ativar_btn")
    async def ativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)
        conf["ativo"] = True
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self)
        )


    @discord.ui.button(label="🔴 Desativar", style=discord.ButtonStyle.danger, row=2, custom_id="automod_desativar_btn")
    async def desativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)
        conf["ativo"] = False
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self)
        )
