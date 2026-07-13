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

    @commands.hybrid_command(name="sorteio")
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

    @commands.hybrid_command(name="sorteios")
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

    @commands.hybrid_command(name="sorteio-cancelar")
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

    @commands.hybrid_command(name="sorteio-reroll")
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

    @commands.hybrid_command(name="sorteio-editar")
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

            label="Número de vencedores",

            placeholder="Ex: 1",

            default=str(painel.vencedores),

            max_length=3

        )


        self.add_item(
            self.quantidade
        )



    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            numero = int(
                self.quantidade.value
            )


            if numero <= 0:

                raise ValueError



            self.painel.vencedores = numero


        except:


            return await interaction.response.send_message(

                "❌ Digite um número válido.",

                ephemeral=True

            )



        await interaction.response.edit_message(

            embed=self.painel.gerar_embed(),

            view=self.painel

        )



# ==========================================================
# MODAL REQUISITOS
# ==========================================================

class ModalRequisitos(Modal):

    def __init__(self, painel):

        super().__init__(
            title="📋 Requisitos"
        )

        self.painel = painel


        self.requisito = TextInput(

            label="Requisitos para participar",

            placeholder="Ex: Ter cargo membro, estar no servidor há 7 dias...",

            style=discord.TextStyle.paragraph,

            default=painel.requisitos or None,

            max_length=500

        )


        self.add_item(
            self.requisito
        )



    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        self.painel.requisitos = self.requisito.value


        await interaction.response.edit_message(

            embed=self.painel.gerar_embed(),

            view=self.painel

        )



# ==========================================================
# SELECIONAR CANAL
# ==========================================================

class SelecionarCanal(View):

    def __init__(self, painel):

        super().__init__(
            timeout=60
        )

        self.painel = painel


    @discord.ui.select(
        cls=ChannelSelect,
        placeholder="Escolha o canal do sorteio",
        channel_types=[discord.ChannelType.text]
    )
    async def selecionar(

        self,

        interaction: discord.Interaction,

        select: ChannelSelect

    ):


        canal_selecionado = select.values[0]


        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)


        self.painel.canal = canal


        await interaction.response.edit_message(

            content="✅ Canal selecionado.",

            view=None

        )


    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item
    ):
        import traceback

        print("========== ERRO NO SelecionarCanal ==========")
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        print("===============================================")

        mensagem_erro = (
            f"❌ Deu erro ao selecionar o canal:\n"
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
# SELECIONAR CARGO OBRIGATÓRIO
# ==========================================================

class SelecionarCargo(View):

    def __init__(self, painel):

        super().__init__(
            timeout=60
        )

        self.painel = painel


    @discord.ui.select(
        cls=RoleSelect,
        placeholder="Escolha o cargo obrigatório",
        min_values=1,
        max_values=1,
        row=0
    )
    async def selecionar(

        self,

        interaction: discord.Interaction,

        select: RoleSelect

    ):

        cargo = select.values[0]

        self.painel.cargo_id = cargo.id

        await interaction.response.edit_message(

            content=f"✅ Cargo obrigatório definido: {cargo.mention}",

            view=None

        )


    @discord.ui.button(
        label="🔓 Sem restrição de cargo",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def sem_cargo(
        self,
        interaction: discord.Interaction,
        button: Button
    ):

        self.painel.cargo_id = None

        await interaction.response.edit_message(

            content="✅ Sorteio sem restrição de cargo.",

            view=None

        )


    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item
    ):
        import traceback

        print("========== ERRO NO SelecionarCargo ==========")
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        print("===============================================")

        mensagem_erro = (
            f"❌ Deu erro ao selecionar o cargo:\n"
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
# BOTÃO PARTICIPAR / SAIR
# ==========================================================

class ParticiparSorteio(View):

    def __init__(self, sorteio_id):

        super().__init__(
            timeout=None
        )

        self.sorteio_id = sorteio_id

        self.participar.custom_id = f"participar_sorteio_{sorteio_id}"

        self.sair.custom_id = f"sair_sorteio_{sorteio_id}"



    @discord.ui.button(

        label="🎉 Participar",

        style=discord.ButtonStyle.success

    )

    async def participar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        cog = interaction.client.get_cog(
            "Sorteio"
        )


        if cog is None:

            return await interaction.response.send_message(

                "❌ Sistema indisponível.",

                ephemeral=True

            )



        dados = cog.sorteios.get(
            self.sorteio_id
        )


        if dados is None or dados.get("status") != "ativo":

            return await interaction.response.send_message(

                "❌ Esse sorteio não está mais ativo.",

                ephemeral=True

            )


        cargo_id = dados.get("cargo_id")

        if cargo_id:

            cargo = interaction.guild.get_role(cargo_id)

            if cargo and cargo not in interaction.user.roles:

                return await interaction.response.send_message(

                    f"❌ Você precisa ter o cargo {cargo.mention} para participar.",

                    ephemeral=True

                )



        usuario = interaction.user.id



        if usuario in dados["participantes"]:

            return await interaction.response.send_message(

                "⚠️ Você já está participando.",

                ephemeral=True

            )



        dados["participantes"].append(
            usuario
        )

        cog.salvar()

        await atualizar_mensagem_sorteio(cog, self.sorteio_id)



        await interaction.response.send_message(

            "✅ Você entrou no sorteio!",

            ephemeral=True

        )



    @discord.ui.button(

        label="🚪 Sair",

        style=discord.ButtonStyle.danger

    )

    async def sair(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):

        cog = interaction.client.get_cog(
            "Sorteio"
        )

        if cog is None:

            return await interaction.response.send_message(
                "❌ Sistema indisponível.",
                ephemeral=True
            )

        dados = cog.sorteios.get(
            self.sorteio_id
        )

        if dados is None or dados.get("status") != "ativo":

            return await interaction.response.send_message(
                "❌ Esse sorteio não está mais ativo.",
                ephemeral=True
            )

        usuario = interaction.user.id

        if usuario not in dados["participantes"]:

            return await interaction.response.send_message(
                "⚠️ Você não está participando desse sorteio.",
                ephemeral=True
            )

        dados["participantes"].remove(usuario)

        cog.salvar()

        await atualizar_mensagem_sorteio(cog, self.sorteio_id)

        await interaction.response.send_message(
            "👋 Você saiu do sorteio.",
            ephemeral=True
        )


    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item
    ):
        import traceback

        print("========== ERRO NO ParticiparSorteio ==========")
        traceback.print_exception(
            type(error), error, error.__traceback__
        )
        print("===============================================")

        mensagem_erro = (
            f"❌ Deu erro:\n"
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
# CRIAR SORTEIO
# ==========================================================

async def iniciar_sorteio(

    cog,

    painel,

    interaction

):


    sorteio_id = str(
        random.randint(
            100000,
            999999
        )
    )


    segundos = converter_tempo(painel.tempo)

    termina_em = time.time() + segundos


    cog.sorteios[sorteio_id] = {

        "premio": painel.premio,

        "tempo": painel.tempo,

        "vencedores": painel.vencedores,

        "requisitos": painel.requisitos,

        "cargo_id": painel.cargo_id,

        "participantes": [],

        "termina_em": termina_em,

        "status": "ativo",

        "canal": painel.canal.id,

        "criado_por": interaction.user.id

    }


    view = ParticiparSorteio(sorteio_id)


    mensagem = await painel.canal.send(

        embed=construir_embed_sorteio(cog.sorteios[sorteio_id]),

        view=view

    )


    cog.sorteios[sorteio_id]["mensagem"] = mensagem.id

    cog.salvar()


    task = asyncio.create_task(
        iniciar_contagem(
            cog,
            sorteio_id
        )
    )

    cog.tasks[sorteio_id] = task


    await enviar_log(
        cog.bot,
        painel.canal.guild,
        f"🎉 Sorteio de **{painel.premio}** criado por {interaction.user.mention} "
        f"em {painel.canal.mention}. (ID `{sorteio_id}`)"
    )



# ==========================================================
# SALVAR EDIÇÃO DE SORTEIO
# ==========================================================

async def salvar_edicao_sorteio(

    cog,

    painel,

    interaction

):

    sorteio_id = painel.sorteio_id

    dados = cog.sorteios.get(sorteio_id)

    if dados is None:
        return

    dados["premio"] = painel.premio

    dados["vencedores"] = painel.vencedores

    dados["requisitos"] = painel.requisitos

    dados["cargo_id"] = painel.cargo_id


    if painel.tempo and painel.tempo != dados.get("tempo"):

        segundos = converter_tempo(painel.tempo)

        if segundos:

            dados["tempo"] = painel.tempo

            dados["termina_em"] = time.time() + segundos

            old_task = cog.tasks.pop(sorteio_id, None)

            if old_task:
                old_task.cancel()

            task = asyncio.create_task(
                iniciar_contagem(cog, sorteio_id)
            )

            cog.tasks[sorteio_id] = task


    cog.salvar()

    await atualizar_mensagem_sorteio(cog, sorteio_id)

    await enviar_log(
        cog.bot,
        interaction.guild,
        f"✏️ Sorteio **{dados['premio']}** (ID `{sorteio_id}`) foi editado por "
        f"{interaction.user.mention}.",
        discord.Color.blue()
    )



# ==========================================================
# CONVERTER TEMPO
# ==========================================================

def converter_tempo(tempo):

    try:

        numero = int(
            tempo[:-1]
        )

        unidade = tempo[-1].lower()


        if unidade == "m":

            return numero * 60


        if unidade == "h":

            return numero * 3600


        if unidade == "d":

            return numero * 86400


    except:

        return None



# ==========================================================
# FINALIZAR SORTEIO
# ==========================================================

async def finalizar_sorteio(

    cog,

    sorteio_id

):


    dados = cog.sorteios.get(
        sorteio_id
    )


    if dados is None:

        return



    participantes = dados["participantes"]



    canal = cog.bot.get_channel(

        dados.get("canal")

    )



    if not participantes:

        dados["status"] = "finalizado"

        dados["vencedores_sorteados"] = []

        cog.salvar()

        if canal:

            try:

                msg = await canal.fetch_message(dados["mensagem"])

                await msg.edit(

                    embed=discord.Embed(

                        title="🎉 Sorteio encerrado",

                        description=f"Ninguém participou do sorteio de **{dados['premio']}**.",

                        color=discord.Color.red()

                    ),

                    view=None

                )

            except Exception:

                pass

        await enviar_log(
            cog.bot,
            canal.guild if canal else None,
            f"🎉 Sorteio **{dados['premio']}** (ID `{sorteio_id}`) encerrado sem participantes.",
            discord.Color.orange()
        )

        return



    quantidade = min(

        dados["vencedores"],

        len(participantes)

    )



    vencedores = random.sample(

        participantes,

        quantidade

    )


    dados["vencedores_sorteados"] = vencedores

    dados["status"] = "finalizado"

    cog.salvar()


    mencoes = []


    for usuario in vencedores:

        mencoes.append(

            f"<@{usuario}>"

        )



    resultado = "\n".join(
        mencoes
    )



    if canal:

        try:

            msg = await canal.fetch_message(dados["mensagem"])

            await msg.edit(

                embed=discord.Embed(

                    title="🏆 Sorteio Finalizado!",

                    description=f"""

🎁 **Prêmio**

{dados["premio"]}



🎉 **Vencedor(es)**

{resultado}

""",

                    color=discord.Color.green(),

                    timestamp=datetime.now(timezone.utc)

                ),

                view=None

            )

        except Exception:

            pass


        await canal.send(

            f"🎉 Parabéns {resultado}! Vocês ganharam **{dados['premio']}**!"

        )


    await enviar_log(
        cog.bot,
        canal.guild if canal else None,
        f"🏆 Sorteio **{dados['premio']}** (ID `{sorteio_id}`) finalizado. "
        f"Vencedor(es): {resultado}",
        discord.Color.green()
    )



# ==========================================================
# INICIAR CONTAGEM
# ==========================================================

async def iniciar_contagem(

    cog,

    sorteio_id

):

    await cog.bot.wait_until_ready()


    dados = cog.sorteios.get(

        sorteio_id

    )


    if dados is None or dados.get("status") != "ativo":

        return


    restante = dados["termina_em"] - time.time()


    if restante > 0:

        try:

            await asyncio.sleep(restante)

        except asyncio.CancelledError:

            return


    dados = cog.sorteios.get(sorteio_id)

    if dados is None or dados.get("status") != "ativo":

        return


    await finalizar_sorteio(

        cog,

        sorteio_id

    )

    cog.tasks.pop(sorteio_id, None)
