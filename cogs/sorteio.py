import discord
import asyncio
import json
import os
import random
import time

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, ChannelSelect, RoleSelect

from .logs import obter_canal_log


# ==========================================================
# CONFIG / PERSISTÊNCIA
# ==========================================================

DATA_DIR = os.getenv("SORTEIO_DATA_DIR", os.path.dirname(__file__))

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "sorteios_data.json")

LOG_CHANNEL_NAME = "logs-moderação"


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Erro ao carregar sorteios_data.json: {e}")
        return {}


def salvar_dados(sorteios):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(sorteios, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar sorteios_data.json: {e}")


async def enviar_log(bot, guild, texto, cor=discord.Color.blurple()):

    if guild is None:
        return

    canal_log = obter_canal_log(bot, guild, "sorteio")

    if canal_log is None:

        canal_log = discord.utils.get(
            guild.text_channels,
            name=LOG_CHANNEL_NAME
        )

    if canal_log is None:
        return

    try:
        await canal_log.send(
            embed=discord.Embed(
                description=texto,
                color=cor,
                timestamp=datetime.now(timezone.utc)
            )
        )
    except Exception:
        pass


def construir_embed_sorteio(dados):

    cargo_texto = (
        f"<@&{dados['cargo_id']}>"
        if dados.get("cargo_id")
        else "Nenhum"
    )

    embed = discord.Embed(

        title="🎉 NOVO SORTEIO",

        description=f"""

🎁 **Prêmio**

{dados['premio']}



🏆 **Vencedores**

{dados['vencedores']}



📋 **Requisitos**

{dados['requisitos']}



🔒 **Cargo Obrigatório**

{cargo_texto}



👥 **Participantes**

{len(dados['participantes'])}



⏰ **Termina**

<t:{int(dados['termina_em'])}:R>



Clique no botão abaixo para participar!

""",

        color=discord.Color.gold(),

        timestamp=datetime.now(timezone.utc)

    )

    return embed


async def atualizar_mensagem_sorteio(cog, sorteio_id):

    dados = cog.sorteios.get(sorteio_id)

    if dados is None:
        return

    canal = cog.bot.get_channel(dados.get("canal"))

    if canal is None:
        return

    try:
        msg = await canal.fetch_message(dados["mensagem"])
        await msg.edit(embed=construir_embed_sorteio(dados))
    except Exception:
        pass



# ==========================================================
# COG
# ==========================================================

class Sorteio(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.sorteios = carregar_dados()

        self.tasks = {}


    async def cog_load(self):

        for sorteio_id, dados in list(self.sorteios.items()):

            if dados.get("status") == "ativo":

                self.bot.add_view(
                    ParticiparSorteio(sorteio_id)
                )

                task = asyncio.create_task(
                    iniciar_contagem(self, sorteio_id)
                )

                self.tasks[sorteio_id] = task


    def salvar(self):

        salvar_dados(self.sorteios)


    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("❌ Você não tem permissão para usar esse comando.")

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"❌ Faltou um argumento: `{error.param.name}`.")

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(f"❌ Ocorreu um erro: `{error}`")


    # ======================================================
    # CRIAR SORTEIO (painel)
    # ======================================================

    @commands.command(name="sorteio")
    @commands.has_permissions(manage_guild=True)
    async def sorteio(self, ctx):

        painel = PainelSorteio(self)

        await ctx.send(
            embed=painel.gerar_embed(),
            view=painel
        )


    # ======================================================
    # LISTAR SORTEIOS ATIVOS
    # ======================================================

    @commands.command(name="sorteios")
    @commands.has_permissions(manage_guild=True)
    async def sorteios_ativos(self, ctx):

        ativos = {
            sid: d for sid, d in self.sorteios.items()
            if d.get("status") == "ativo"
        }

        if not ativos:
            return await ctx.send(
                embed=discord.Embed(
                    description="Nenhum sorteio ativo no momento.",
                    color=discord.Color.red()
                )
            )

        embed = discord.Embed(
            title="🎉 Sorteios Ativos",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )

        for sid, d in ativos.items():

            embed.add_field(
                name=f"🎁 {d['premio']}  •  ID `{sid}`",
                value=(
                    f"📢 <#{d['canal']}>\n"
                    f"👥 {len(d['participantes'])} participante(s)\n"
                    f"⏰ termina <t:{int(d['termina_em'])}:R>"
                ),
                inline=False
            )

        await ctx.send(embed=embed)


    # ======================================================
    # CANCELAR SORTEIO
    # ======================================================

    @commands.command(name="sorteio-cancelar")
    @commands.has_permissions(manage_guild=True)
    async def sorteio_cancelar(self, ctx, sorteio_id: str):

        dados = self.sorteios.get(sorteio_id)

        if dados is None or dados.get("status") != "ativo":
            return await ctx.send("❌ Sorteio não encontrado ou não está ativo.")

        dados["status"] = "cancelado"
        self.salvar()

        task = self.tasks.pop(sorteio_id, None)

        if task:
            task.cancel()

        canal = self.bot.get_channel(dados["canal"])

        if canal:
            try:
                msg = await canal.fetch_message(dados["mensagem"])
                await msg.edit(
                    embed=discord.Embed(
                        title="🚫 Sorteio Cancelado",
                        description=f"O sorteio de **{dados['premio']}** foi cancelado.",
                        color=discord.Color.red()
                    ),
                    view=None
                )
            except Exception:
                pass

        await ctx.send(f"✅ Sorteio `{sorteio_id}` cancelado.")

        await enviar_log(
            self.bot,
            ctx.guild,
            f"🚫 Sorteio **{dados['premio']}** (ID `{sorteio_id}`) foi cancelado por {ctx.author.mention}.",
            discord.Color.red()
        )


    # ======================================================
    # REROLL (novo sorteio de vencedores)
    # ======================================================

    @commands.command(name="sorteio-reroll")
    @commands.has_permissions(manage_guild=True)
    async def sorteio_reroll(self, ctx, sorteio_id: str):

        dados = self.sorteios.get(sorteio_id)

        if dados is None or dados.get("status") != "finalizado":
            return await ctx.send("❌ Sorteio não encontrado ou ainda não foi finalizado.")

        participantes = dados.get("participantes", [])

        if not participantes:
            return await ctx.send("❌ Não há participantes para sortear novamente.")

        quantidade = min(dados["vencedores"], len(participantes))

        novos = random.sample(participantes, quantidade)

        dados["vencedores_sorteados"] = novos
        self.salvar()

        mencoes = "\n".join(f"<@{u}>" for u in novos)

        canal = self.bot.get_channel(dados["canal"])

        embed = discord.Embed(
            title="🔁 Reroll — Novo(s) Vencedor(es)!",
            description=f"🎁 **Prêmio**\n{dados['premio']}\n\n🎉 **Vencedor(es)**\n{mencoes}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        if canal:
            await canal.send(embed=embed)

        await ctx.send(f"✅ Reroll feito para o sorteio `{sorteio_id}`.")

        await enviar_log(
            self.bot,
            ctx.guild,
            f"🔁 Reroll no sorteio **{dados['premio']}** (ID `{sorteio_id}`) por {ctx.author.mention}.",
            discord.Color.blue()
        )


    # ======================================================
    # EDITAR SORTEIO
    # ======================================================

    @commands.command(name="sorteio-editar")
    @commands.has_permissions(manage_guild=True)
    async def sorteio_editar(self, ctx, sorteio_id: str):

        dados = self.sorteios.get(sorteio_id)

        if dados is None or dados.get("status") != "ativo":
            return await ctx.send("❌ Sorteio não encontrado ou não está ativo.")

        painel = PainelSorteio(self, sorteio_id=sorteio_id)

        painel.premio = dados["premio"]
        painel.tempo = dados["tempo"]
        painel.vencedores = dados["vencedores"]
        painel.requisitos = dados["requisitos"]
        painel.cargo_id = dados.get("cargo_id")
        painel.canal = self.bot.get_channel(dados["canal"])

        await ctx.send(
            embed=painel.gerar_embed(),
            view=painel
        )



# ==========================================================
# PAINEL (criação e edição)
# ==========================================================

class PainelSorteio(View):

    def __init__(self, cog, sorteio_id=None):

        super().__init__(timeout=600)

        self.cog = cog

        self.sorteio_id = sorteio_id

        self.premio = ""

        self.canal = None

        self.tempo = ""

        self.vencedores = 1

        self.requisitos = "Nenhum"

        self.cargo_id = None

        if sorteio_id:

            self.criar_sorteio.label = "💾 Salvar Alterações"

            self.criar_sorteio.style = discord.ButtonStyle.primary

            self.remove_item(self.botao_canal)



    def gerar_embed(self):

        titulo = (
            "✏️ Editando Sorteio"
            if self.sorteio_id
            else "🎉 Configuração do Sorteio"
        )

        embed = discord.Embed(

            title=titulo,

            description="""
Configure todas as opções abaixo.

Quando terminar clique no botão de confirmar.
""",

            color=discord.Color.gold(),

            timestamp=datetime.now(timezone.utc)

        )

        embed.add_field(
            name="🎁 Prêmio",
            value=self.premio or "`Não definido`",
            inline=False
        )

        embed.add_field(
            name="📢 Canal",
            value=self.canal.mention if self.canal else "`Não definido`",
            inline=False
        )

        embed.add_field(
            name="⏰ Tempo",
            value=self.tempo or "`Não definido`",
            inline=True
        )

        embed.add_field(
            name="🏆 Vencedores",
            value=str(self.vencedores),
            inline=True
        )

        embed.add_field(
            name="📋 Requisitos",
            value=self.requisitos,
            inline=False
        )

        embed.add_field(
            name="🔒 Cargo Obrigatório",
            value=f"<@&{self.cargo_id}>" if self.cargo_id else "`Nenhum`",
            inline=False
        )

        embed.set_footer(
            text="Sistema Profissional de Sorteios"
        )

        return embed



    # ======================================================
    # BOTÃO PRÊMIO
    # ======================================================

    @discord.ui.button(
        label="🎁 Prêmio",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def botao_premio(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            ModalPremio(self)
        )


    # ======================================================
    # BOTÃO CANAL
    # ======================================================

    @discord.ui.button(
        label="📢 Canal",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def botao_canal(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_message(

            "Selecione o canal abaixo.",

            view=SelecionarCanal(self),

            ephemeral=True

        )


    # ======================================================
    # BOTÃO TEMPO
    # ======================================================

    @discord.ui.button(
        label="⏰ Tempo",
        style=discord.ButtonStyle.primary,
        row=1
    )
    async def botao_tempo(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            ModalTempo(self)
        )


    # ======================================================
    # BOTÃO VENCEDORES
    # ======================================================

    @discord.ui.button(
        label="🏆 Vencedores",
        style=discord.ButtonStyle.success,
        row=1
    )
    async def botao_vencedores(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            ModalVencedores(self)
        )


    # ======================================================
    # BOTÃO REQUISITOS
    # ======================================================

    @discord.ui.button(
        label="📋 Requisitos",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def botao_requisitos(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_modal(
            ModalRequisitos(self)
        )


    # ======================================================
    # BOTÃO CARGO OBRIGATÓRIO
    # ======================================================

    @discord.ui.button(
        label="🔒 Cargo",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def botao_cargo(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        await interaction.response.send_message(

            "Selecione o cargo obrigatório, ou clique em "
            "\"Sem restrição\" para não exigir nenhum.",

            view=SelecionarCargo(self),

            ephemeral=True

        )


    # ======================================================
    # BOTÃO CRIAR / SALVAR
    # ======================================================

    @discord.ui.button(
        label="🚀 Criar Sorteio",
        style=discord.ButtonStyle.success,
        row=3
    )
    async def criar_sorteio(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        if not self.premio:

            return await interaction.response.send_message(
                "❌ Você precisa definir o prêmio.",
                ephemeral=True
            )


        if self.canal is None:

            return await interaction.response.send_message(
                "❌ Você precisa escolher o canal do sorteio.",
                ephemeral=True
            )


        if not self.tempo:

            return await interaction.response.send_message(
                "❌ Você precisa definir o tempo do sorteio.",
                ephemeral=True
            )


        if converter_tempo(self.tempo) is None:

            return await interaction.response.send_message(
                "❌ Tempo inválido. Use algo como `30m`, `1h` ou `2d`.",
                ephemeral=True
            )


        await interaction.response.defer(
            ephemeral=True
        )


        if self.sorteio_id:

            await salvar_edicao_sorteio(
                self.cog,
                self,
                interaction
            )

            await interaction.followup.send(
                "✅ Sorteio atualizado com sucesso!",
                ephemeral=True
            )

        else:

            await iniciar_sorteio(
                self.cog,
                self,
                interaction
            )

            await interaction.followup.send(
                "✅ Sorteio criado com sucesso!",
                ephemeral=True
            )


    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item
    ):
        import traceback

        print("========== ERRO NO PainelSorteio ==========")
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        print("===============================================")

        mensagem_erro = (
            f"❌ Deu erro nesse botão:\n"
            f"```{type(error).__name__}: {error}```"
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    mensagem_erro,
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    mensagem_erro,
                    ephemeral=True
                )
        except Exception:
            pass



# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Sorteio(bot)
    )



# ==========================================================
# MODAL PRÊMIO
# ==========================================================

class ModalPremio(Modal):

    def __init__(self, painel):

        super().__init__(
            title="🎁 Configurar Prêmio"
        )

        self.painel = painel


        self.nome = TextInput(

            label="Qual será o prêmio?",

            placeholder="Ex: Nitro, R$50, Cargo VIP...",

            default=painel.premio or None,

            max_length=100

        )


        self.add_item(
            self.nome
        )



    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        self.painel.premio = self.nome.value


        await interaction.response.edit_message(

            embed=self.painel.gerar_embed(),

            view=self.painel

        )



# ==========================================================
# MODAL TEMPO
# ==========================================================

class ModalTempo(Modal):

    def __init__(self, painel):

        super().__init__(
            title="⏰ Configurar Tempo"
        )

        self.painel = painel


        self.tempo = TextInput(

            label="Tempo do sorteio",

            placeholder="Ex: 1h, 30m, 2d",

            default=painel.tempo or None,

            max_length=20

        )


        self.add_item(
            self.tempo
        )



    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        self.painel.tempo = self.tempo.value


        await interaction.response.edit_message(

            embed=self.painel.gerar_embed(),

            view=self.painel

        )



# ==========================================================
# MODAL VENCEDORES
# ==========================================================

class ModalVencedores(Modal):

    def __init__(self, painel):

        super().__init__(
            title="🏆 Quantidade de vencedores"
        )

        self.painel = painel


        self.quantidade = TextInput(

            label="Número 
