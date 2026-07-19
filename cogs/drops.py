import discord
import os
import json
import random
import time

from datetime import datetime, timezone

from discord.ext import commands, tasks
from discord.ui import View, Button, ChannelSelect, Modal, TextInput


DATA_DIR = (
    os.getenv("DROPS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "drops_data.json")

MOEDA = "🪙"


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
        print(f"⚠️ Erro ao salvar drops_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.gold()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="💰 Drops")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {
        "ativo": False,
        "canal_id": None,
        "intervalo_min": 15,
        "intervalo_max": 60,
        "valor_min": 50,
        "valor_max": 300,
        "proximo_drop": None
    })


def container_view(texto, source_view, accent_color=discord.Color.gold()):
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

    status = "🟢 Ativado" if conf.get("ativo") else "🔴 Desativado"

    canal_id = conf.get("canal_id")
    canal_txt = f"<#{canal_id}>" if canal_id else "`Não definido`"

    return (
        "## 💰 Painel de Drops\n"
        "De tempos em tempos, um baú de moedas cai no canal escolhido. "
        "Quem clicar primeiro leva o prêmio!\n\n"
        f"**Status:** {status}\n"
        f"**Canal:** {canal_txt}\n"
        f"**Intervalo:** {conf['intervalo_min']} a {conf['intervalo_max']} minutos\n"
        f"**Valor do baú:** {conf['valor_min']} a {conf['valor_max']} {MOEDA}"
    )


# ==========================================================
# COG
# ==========================================================

class Drops(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()

        self.verificar_drops.start()


    def cog_unload(self):

        self.verificar_drops.cancel()


    async def cog_load(self):

        self.bot.add_view(PainelDropsView(self))


    def salvar(self):

        salvar_dados(self.dados)


    @tasks.loop(minutes=1)
    async def verificar_drops(self):

        agora = time.time()

        for guild in self.bot.guilds:

            conf = config(self.dados, guild.id)

            if not conf.get("ativo") or conf.get("canal_id") is None:
                continue

            proximo = conf.get("proximo_drop")

            if proximo is None:

                self._agendar_proximo(conf)
                self.salvar()
                continue

            if agora >= proximo:

                canal = guild.get_channel(conf["canal_id"])

                if canal:
                    await self._soltar_drop(canal, conf)

                self._agendar_proximo(conf)
                self.salvar()


    @verificar_drops.before_loop
    async def antes(self):

        await self.bot.wait_until_ready()


    def _agendar_proximo(self, conf):

        minutos = random.randint(conf["intervalo_min"], conf["intervalo_max"])

        conf["proximo_drop"] = time.time() + (minutos * 60)


    async def _soltar_drop(self, canal, conf):

        valor = random.randint(conf["valor_min"], conf["valor_max"])

        try:
            await canal.send(
                embed=embed_padrao(
                    "🎁 Um baú apareceu!",
                    f"Clique rápido no botão abaixo pra pegar **{valor} {MOEDA}**!\nSó o primeiro leva.",
                    discord.Color.gold()
                ),
                view=BaustView(self, valor)
            )
        except Exception as e:
            print(f"⚠️ Erro ao soltar drop: {e}")


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="drops-painel")
    @commands.has_permissions(administrator=True)
    async def drops_painel(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        await ctx.send(
            view=container_view(texto_painel(ctx.guild, conf), PainelDropsView(self))
        )


async def setup(bot):

    await bot.add_cog(
        Drops(bot)
    )


# ==========================================================
# BOTÃO DO BAÚ (cada drop é único, custom_id dinâmico)
# ==========================================================

class BaustView(View):

    def __init__(self, cog, valor):

        super().__init__(timeout=600)

        self.cog = cog
        self.valor = valor
        self.pego = False


    @discord.ui.button(label="💰 Pegar", style=discord.ButtonStyle.success)
    async def pegar(self, interaction: discord.Interaction, button: Button):

        if self.pego:
            return await interaction.response.send_message("😢 Alguém já pegou esse baú.", ephemeral=True)

        self.pego = True

        jogos = interaction.client.get_cog("Jogos")

        if jogos is not None:

            try:
                jogos.adicionar(interaction.user.id, self.valor)
                jogos.salvar()
            except Exception:
                pass

        button.disabled = True
        button.label = f"✅ Pego por {interaction.user.display_name}"

        await interaction.response.edit_message(
            embed=embed_padrao(
                "🎉 Baú coletado!",
                f"{interaction.user.mention} pegou **{self.valor} {MOEDA}**!",
                discord.Color.green()
            ),
            view=self
        )


    async def on_timeout(self):

        self.pego = True


# ==========================================================
# PAINEL DE ADMINISTRAÇÃO
# ==========================================================

class ModalConfigDrops(Modal):

    def __init__(self, cog):

        super().__init__(title="💰 Configurar Drops")

        self.cog = cog

        self.intervalo = TextInput(
            label="Intervalo em minutos (min-max)",
            placeholder="Ex: 15-60",
            max_length=20
        )

        self.valor = TextInput(
            label="Valor do baú (min-max)",
            placeholder="Ex: 50-300",
            max_length=20
        )

        self.add_item(self.intervalo)
        self.add_item(self.valor)


    async def on_submit(self, interaction: discord.Interaction):

        conf = config(self.cog.dados, interaction.guild.id)

        try:

            i_min, i_max = [int(x.strip()) for x in self.intervalo.value.split("-")]
            v_min, v_max = [int(x.strip()) for x in self.valor.value.split("-")]

            if i_min <= 0 or i_max < i_min or v_min <= 0 or v_max < v_min:
                raise ValueError

        except ValueError:

            return await interaction.response.send_message(
                "❌ Formato inválido. Use `min-max`, exemplo: `15-60`.",
                ephemeral=True
            )

        conf["intervalo_min"] = i_min
        conf["intervalo_max"] = i_max
        conf["valor_min"] = v_min
        conf["valor_max"] = v_max
        conf["proximo_drop"] = None

        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), PainelDropsView(self.cog))
        )


class SelecionarCanalDrops(ChannelSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(
            placeholder="Escolha o canal dos drops",
            channel_types=[discord.ChannelType.text],
            row=0,
            custom_id="drops_canal_select"
        )


    async def callback(self, interaction: discord.Interaction):

        canal_selecionado = self.values[0]

        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)

        conf = config(self.cog.dados, interaction.guild.id)
        conf["canal_id"] = canal.id
        conf["proximo_drop"] = None
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self.view)
        )


class PainelDropsView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        self.add_item(SelecionarCanalDrops(cog))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelDropsView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="⚙️ Configurar Valores", style=discord.ButtonStyle.primary, row=1, custom_id="drops_config")
    async def configurar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(ModalConfigDrops(self.cog))


    @discord.ui.button(label="🟢 Ativar", style=discord.ButtonStyle.success, row=2, custom_id="drops_ativar")
    async def ativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)

        if conf.get("canal_id") is None:
            return await interaction.response.send_message("❌ Escolha um canal primeiro.", ephemeral=True)

        conf["ativo"] = True
        conf["proximo_drop"] = None
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self)
        )


    @discord.ui.button(label="🔴 Desativar", style=discord.ButtonStyle.danger, row=2, custom_id="drops_desativar")
    async def desativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)
        conf["ativo"] = False
        self.cog.salvar()

        await interaction.response.edit_message(
            view=container_view(texto_painel(interaction.guild, conf), self)
        )
