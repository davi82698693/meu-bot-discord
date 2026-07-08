import discord
import asyncio
import random

from datetime import datetime

from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, ChannelSelect



# ==========================================================
# COG
# ==========================================================

class Sorteio(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.sorteios = {}



    def embed(
        self,
        titulo,
        descricao,
        cor=discord.Color.blurple()
    ):

        embed = discord.Embed(
            title=titulo,
            description=descricao,
            color=cor,
            timestamp=datetime.utcnow()
        )

        embed.set_footer(
            text="🎉 Sistema Profissional de Sorteios"
        )

        return embed



    @commands.command(name="sorteio")
    @commands.has_permissions(manage_guild=True)

    async def sorteio(self, ctx):

        painel = PainelSorteio(self)

        await ctx.send(
            embed=painel.gerar_embed(),
            view=painel
        )



# ==========================================================
# PAINEL
# ==========================================================

class PainelSorteio(View):

    def __init__(self, cog):

        super().__init__(timeout=600)

        self.cog = cog

        self.premio = ""

        self.canal = None

        self.tempo = ""

        self.vencedores = 1

        self.requisitos = "Nenhum"



    def gerar_embed(self):

        embed = discord.Embed(

            title="🎉 Configuração do Sorteio",

            description="""
Configure todas as opções abaixo.

Quando terminar clique em **Criar Sorteio**.
""",

            color=discord.Color.gold(),

            timestamp=datetime.utcnow()

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
    # BOTÃO CRIAR
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
                "❌ Defina um prêmio.",
                ephemeral=True
            )


        if self.canal is None:

            return await interaction.response.send_message(
                "❌ Escolha um canal.",
                ephemeral=True
            )


        if not self.tempo:

            return await interaction.response.send_message(
                "❌ Defina um tempo.",
                ephemeral=True
            )


        await interaction.response.defer(
            ephemeral=True
        )


        await iniciar_sorteio(
            self.cog,
            self,
            interaction
        )


        await interaction.followup.send(
            "✅ Sorteio criado com sucesso!",
            ephemeral=True
        )



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


        self.add_item(

            ChannelSelect(

                placeholder="Escolha o canal do sorteio",

                channel_types=[
                    discord.ChannelType.text
                ]

            )

        )


    @discord.ui.select(
        cls=ChannelSelect
    )
    async def selecionar(

        self,

        interaction: discord.Interaction,

        select: ChannelSelect

    ):


        canal = select.values[0]


        self.painel.canal = canal


        await interaction.response.edit_message(

            content="✅ Canal selecionado.",

            view=None

        )



# ==========================================================
# BOTÃO PARTICIPAR
# ==========================================================

class ParticiparSorteio(View):

    def __init__(self, sorteio_id):

        super().__init__(
            timeout=None
        )

        self.sorteio_id = sorteio_id



    @discord.ui.button(

        label="🎉 Participar",

        style=discord.ButtonStyle.success,

        custom_id="participar_sorteio"

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


        if dados is None:

            return await interaction.response.send_message(

                "❌ Esse sorteio não existe mais.",

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



        await interaction.response.send_message(

            "✅ Você entrou no sorteio!",

            ephemeral=True

        )



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



    cog.sorteios[sorteio_id] = {


        "premio": painel.premio,


        "tempo": painel.tempo,


        "vencedores": painel.vencedores,


        "requisitos": painel.requisitos,


        "participantes": []

    }



    embed = discord.Embed(

        title="🎉 NOVO SORTEIO",

        description=f"""

🎁 **Prêmio**

{painel.premio}



🏆 **Vencedores**

{painel.vencedores}



📋 **Requisitos**

{painel.requisitos}



⏰ **Duração**

{painel.tempo}



Clique no botão abaixo para participar!

""",

        color=discord.Color.gold(),

        timestamp=datetime.utcnow()

    )



    mensagem = await painel.canal.send(

        embed=embed,

        view=ParticiparSorteio(
            sorteio_id
        )

    )



       cog.sorteios[sorteio_id]["mensagem"] = mensagem.id

    cog.sorteios[sorteio_id]["canal"] = painel.canal.id

    asyncio.create_task(
        iniciar_contagem(
            cog,
            sorteio_id
        )
    )



# ==========================================================
# FINALIZAÇÃO DO SETUP DO CRIAR
# ==========================================================



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


        if canal:

            await canal.send(

                embed=discord.Embed(

                    title="🎉 Sorteio encerrado",

                    description="Ninguém participou do sorteio.",

                    color=discord.Color.red()

                )

            )


        del cog.sorteios[sorteio_id]

        return



    quantidade = min(

        dados["vencedores"],

        len(participantes)

    )



    vencedores = random.sample(

        participantes,

        quantidade

    )



    mencoes = []


    for usuario in vencedores:

        mencoes.append(

            f"<@{usuario}>"

        )



    resultado = "\n".join(
        mencoes
    )



    if canal:


        await canal.send(

            embed=discord.Embed(

                title="🏆 Sorteio Finalizado!",

                description=f"""

🎁 **Prêmio**

{dados["premio"]}



🎉 **Vencedor(es)**

{resultado}

""",

                color=discord.Color.green(),

                timestamp=datetime.utcnow()

            )

        )



    del cog.sorteios[sorteio_id]



# ==========================================================
# INICIAR CONTAGEM
# ==========================================================

async def iniciar_contagem(

    cog,

    sorteio_id

):


    dados = cog.sorteios.get(

        sorteio_id

    )


    if dados is None:

        return



    segundos = converter_tempo(

        dados["tempo"]

    )



    if segundos is None:

        return



    await asyncio.sleep(

        segundos

    )



    await finalizar_sorteio(

        cog,

        sorteio_id

    )
