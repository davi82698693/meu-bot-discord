import discord

from discord.ext import commands
from discord.ui import View, Modal, TextInput

from datetime import datetime



# ==========================================
# CONFIGURAÇÃO
# ==========================================


class ConfigSorteio:

    def __init__(self):

        self.premio = "❌ Não definido"

        self.canal = "❌ Não definido"

        self.tempo = "❌ Não definido"

        self.requisitos = "❌ Nenhum"



# ==========================================
# EMBED
# ==========================================


def criar_embed(
    titulo,
    descricao,
    cor=discord.Color.gold()
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




def painel_texto(config):

    return f"""

Configure seu sorteio usando os botões abaixo.


🎁 **Prêmio**

`{config.premio}`


📢 **Canal**

`{config.canal}`


⏰ **Tempo**

`{config.tempo}`


👥 **Requisitos**

`{config.requisitos}`


Quando terminar:

🚀 Clique em **Criar Sorteio**
"""





# ==========================================
# MODAL PRÊMIO
# ==========================================


class PremioModal(Modal):


    def __init__(self, config, view):

        super().__init__(

            title="🎁 Definir Prêmio"

        )

        self.config = config

        self.view_original = view



        self.nome = TextInput(

            label="Qual será o prêmio?",

            placeholder="Ex: Nitro Discord 1 mês",

            max_length=100

        )


        self.add_item(
            self.nome
        )




    async def on_submit(
        self,
        interaction: discord.Interaction
    ):


        self.config.premio = self.nome.value



        await interaction.response.edit_message(

            embed=criar_embed(

                "🎉 Criador de Sorteio",

                painel_texto(

                    self.config

                )

            ),

            view=self.view_original

        )





# ==========================================
# MODAL TEMPO
# ==========================================


class TempoModal(Modal):


    def __init__(self, config, view):

        super().__init__(

            title="⏰ Definir Tempo"

        )


        self.config = config

        self.view_original = view



        self.tempo = TextInput(

            label="Tempo em minutos",

            placeholder="Ex: 60",

            max_length=5

        )


        self.add_item(
            self.tempo
        )




    async def on_submit(
        self,
        interaction: discord.Interaction
    ):


        self.config.tempo = (

            self.tempo.value

            + " minutos"

        )



        await interaction.response.edit_message(

            embed=criar_embed(

                "🎉 Criador de Sorteio",

                painel_texto(

                    self.config

                )

            ),

            view=self.view_original

        )





# ==========================================
# COG
# ==========================================


class Sorteio(commands.Cog):


    def __init__(self, bot):

        self.bot = bot



    @commands.command(
        name="sorteio"
    )

    @commands.has_permissions(
        manage_guild=True
    )

    async def sorteio(
        self,
        ctx
    ):


        config = ConfigSorteio()



        await ctx.send(

            embed=criar_embed(

                "🎉 Criador de Sorteio",

                painel_texto(

                    config

                )

            ),

            view=PainelSorteio(

                config

            )

        )





# ==========================================
# PAINEL
# ==========================================


class PainelSorteio(View):


    def __init__(self, config):

        super().__init__(

            timeout=None

        )

        self.config = config



    @discord.ui.button(

        label="🎁 Definir Prêmio",

        style=discord.ButtonStyle.primary,

        custom_id="premio"

    )

    async def premio(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            PremioModal(

                self.config,

                self

            )

        )




    @discord.ui.button(

        label="⏰ Definir Tempo",

        style=discord.ButtonStyle.success,

        custom_id="tempo"

    )

    async def tempo(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            TempoModal(

                self.config,

                self

            )

        )




    @discord.ui.button(

        label="📢 Escolher Canal",

        style=discord.ButtonStyle.secondary,

        custom_id="canal"

    )

    async def canal(

        self,

        interaction,

        button

    ):


        await interaction.response.send_message(

            "📢 Escolha de canal entra na Parte 3.",

            ephemeral=True

        )





    @discord.ui.button(

        label="👥 Requisitos",

        style=discord.ButtonStyle.secondary,

        custom_id="requisitos"

    )

    async def requisitos(

        self,

        interaction,

        button

    ):


        await interaction.response.send_message(

            "👥 Requisitos entram na Parte 3.",

            ephemeral=True

        )





    @discord.ui.button(

        label="🚀 Criar Sorteio",

        style=discord.ButtonStyle.danger,

        custom_id="criar"

    )

    async def criar(

        self,

        interaction,

        button

    ):


        await interaction.response.send_message(

            embed=criar_embed(

                "⚠️ Ainda falta configurar",

                "Configure canal e requisitos antes de criar.",

                discord.Color.red()

            ),

            ephemeral=True

        )





# ==========================================
# SETUP
# ==========================================


async def setup(bot):

    await bot.add_cog(

        Sorteio(bot)

    )



# ==========================================================
# MODAIS DE CONFIGURAÇÃO
# ==========================================================


class PremioModal(discord.ui.Modal):

    def __init__(self, view):

        super().__init__(
            title="🎁 Configurar Prêmio"
        )

        self.view = view


        self.premio = discord.ui.TextInput(
            label="Prêmio do sorteio",
            placeholder="Ex: Nitro, Cargo VIP, R$50...",
            max_length=100
        )

        self.add_item(
            self.premio
        )



    async def on_submit(self, interaction):

        self.view.premio = self.premio.value


        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎁 Prêmio definido",
                description=f"Novo prêmio:\n\n**{self.premio.value}**",
                color=discord.Color.green()
            ),
            ephemeral=True
        )




class TempoModal(discord.ui.Modal):

    def __init__(self, view):

        super().__init__(
            title="⏰ Configurar Tempo"
        )

        self.view = view


        self.tempo = discord.ui.TextInput(
            label="Tempo do sorteio",
            placeholder="Ex: 10m, 1h, 2d",
            max_length=20
        )


        self.add_item(
            self.tempo
        )



    async def on_submit(self, interaction):

        self.view.tempo = self.tempo.value


        await interaction.response.send_message(
            embed=discord.Embed(
                title="⏰ Tempo definido",
                description=f"O sorteio irá durar:\n\n**{self.tempo.value}**",
                color=discord.Color.green()
            ),
            ephemeral=True
        )





class VencedoresModal(discord.ui.Modal):

    def __init__(self, view):

        super().__init__(
            title="🏆 Quantidade de vencedores"
        )

        self.view = view


        self.quantidade = discord.ui.TextInput(
            label="Número de vencedores",
            placeholder="Ex: 1",
            max_length=3
        )


        self.add_item(
            self.quantidade
        )



    async def on_submit(self, interaction):

        try:

            self.view.vencedores = int(
                self.quantidade.value
            )


        except:

            return await interaction.response.send_message(
                "❌ Digite apenas números.",
                ephemeral=True
            )



        await interaction.response.send_message(
            embed=discord.Embed(
                title="🏆 Vencedores definidos",
                description=f"Quantidade:\n\n**{self.view.vencedores}**",
                color=discord.Color.green()
            ),
            ephemeral=True
        )






class RequisitosModal(discord.ui.Modal):

    def __init__(self, view):

        super().__init__(
            title="📋 Requisitos"
        )


        self.view = view


        self.requisitos = discord.ui.TextInput(

            label="Requisitos para participar",

            placeholder="Ex: Ter cargo Membro, estar no servidor, etc",

            style=discord.TextStyle.paragraph,

            max_length=500

        )


        self.add_item(
            self.requisitos
        )



    async def on_submit(self, interaction):

        self.view.requisitos = self.requisitos.value



        await interaction.response.send_message(

            embed=discord.Embed(

                title="📋 Requisitos definidos",

                description=self.requisitos.value,

                color=discord.Color.green()

            ),

            ephemeral=True

        )





# ==========================================================
# VIEW PRINCIPAL DO PAINEL
# ==========================================================


class PainelSorteio(View):


    def __init__(self):

        super().__init__(
            timeout=None
        )


        self.canal = None

        self.premio = "Não configurado"

        self.tempo = "Não configurado"

        self.vencedores = 1

        self.requisitos = "Nenhum"



    def atualizar_embed(self):

        embed = discord.Embed(

            title="🎉 Configuração de Sorteio",

            description=f"""

🎁 **Prêmio**
{self.premio}


⏰ **Tempo**
{self.tempo}


🏆 **Vencedores**
{self.vencedores}


📋 **Requisitos**
{self.requisitos}


📢 **Canal**
{self.canal if self.canal else "Não selecionado"}

""",

            color=discord.Color.gold()

        )


        embed.set_footer(
            text="Sistema profissional de sorteios"
        )


        return embed






    @discord.ui.button(

        label="🎁 Prêmio",

        style=discord.ButtonStyle.primary

    )

    async def premio(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            PremioModal(
                self
            )

        )




    @discord.ui.button(

        label="⏰ Tempo",

        style=discord.ButtonStyle.primary

    )

    async def tempo(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            TempoModal(
                self
            )

        )




    @discord.ui.button(

        label="🏆 Vencedores",

        style=discord.ButtonStyle.success

    )

    async def vencedores(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            VencedoresModal(
                self
            )

        )




    @discord.ui.button(

        label="📋 Requisitos",

        style=discord.ButtonStyle.secondary

    )

    async def requisitos(

        self,

        interaction,

        button

    ):


        await interaction.response.send_modal(

            RequisitosModal(
                self
            )

        )




    @discord.ui.button(

        label="🚀 Criar Sorteio",

        style=discord.ButtonStyle.danger

    )

    async def criar(

        self,

        interaction,

        button

    ):


        if self.canal is None:

            return await interaction.response.send_message(

                "❌ Você precisa selecionar um canal.",

                ephemeral=True

            )


        if self.premio == "Não configurado":

            return await interaction.response.send_message(

                "❌ Configure o prêmio primeiro.",

                ephemeral=True

            )


        await interaction.response.send_message(

            embed=discord.Embed(

                title="✅ Sorteio criado",

                description="O sorteio foi enviado com sucesso.",

                color=discord.Color.green()

            ),

            ephemeral=True

        )



# ==========================================================
# SISTEMA DE CRIAÇÃO DO SORTEIO
# ==========================================================


sorteios_ativos = {}




# ==========================================================
# SELECT DE CANAL
# ==========================================================


class SelecionarCanal(discord.ui.ChannelSelect):

    def __init__(self, painel):

        self.painel = painel

        super().__init__(
            placeholder="📢 Selecione o canal do sorteio",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )



    async def callback(
        self,
        interaction: discord.Interaction
    ):


        canal = self.values[0]


        self.painel.canal = canal



        await interaction.response.send_message(

            embed=discord.Embed(

                title="📢 Canal definido",

                description=f"""
O sorteio será enviado em:

{canal.mention}
""",

                color=discord.Color.green()

            ),

            ephemeral=True

        )






class EscolherCanalView(discord.ui.View):

    def __init__(self, painel):

        super().__init__(
            timeout=60
        )


        self.add_item(

            SelecionarCanal(
                painel
            )

        )





# ==========================================================
# BOTÃO DE ESCOLHER CANAL
# ==========================================================


async def abrir_selecao_canal(
    interaction,
    painel
):

    await interaction.response.send_message(

        embed=discord.Embed(

            title="📢 Escolha o canal",

            description="Selecione abaixo onde o sorteio será enviado.",

            color=discord.Color.blurple()

        ),

        view=EscolherCanalView(
            painel
        ),

        ephemeral=True

    )



# ==========================================================
# BOTÃO DE PARTICIPAR DO SORTEIO
# ==========================================================


class BotaoParticipar(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )



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


        sorteio = sorteios_ativos.get(
            interaction.message.id
        )


        if sorteio is None:


            return await interaction.response.send_message(

                embed=discord.Embed(

                    title="❌ Sorteio encerrado",

                    description="Este sorteio não está mais ativo.",

                    color=discord.Color.red()

                ),

                ephemeral=True

            )



        if interaction.user.id in sorteio["participantes"]:


            return await interaction.response.send_message(

                embed=discord.Embed(

                    title="⚠️ Você já participa",

                    description="Você já entrou neste sorteio.",

                    color=discord.Color.orange()

                ),

                ephemeral=True

            )



        sorteio["participantes"].append(

            interaction.user.id

        )



        embed = interaction.message.embeds[0]


        participantes = len(

            sorteio["participantes"]

        )


        texto_antigo = (

            f"👥 **Participantes:** "

            f"{participantes - 1}"

        )


        texto_novo = (

            f"👥 **Participantes:** "

            f"{participantes}"

        )



        embed.description = embed.description.replace(

            texto_antigo,

            texto_novo

        )



        await interaction.message.edit(

            embed=embed

        )



        await interaction.response.send_message(

            embed=discord.Embed(

                title="🎉 Participação confirmada",

                description="Você entrou no sorteio!",

                color=discord.Color.green()

            ),

            ephemeral=True

        )






# ==========================================================
# FUNÇÃO PARA ENVIAR O SORTEIO
# ==========================================================


async def enviar_sorteio(

    interaction,

    painel

):


    if painel.canal is None:


        return await interaction.response.send_message(

            embed=discord.Embed(

                title="❌ Canal não definido",

                description="Selecione o canal antes de criar o sorteio.",

                color=discord.Color.red()

            ),

            ephemeral=True

        )



    if painel.premio == "Não configurado":


        return await interaction.response.send_message(

            embed=discord.Embed(

                title="❌ Prêmio não configurado",

                description="Defina o prêmio do sorteio.",

                color=discord.Color.red()

            ),

            ephemeral=True

        )



    embed = discord.Embed(

        title="🎉 SORTEIO 🎉",

        description=f"""

🎁 **Prêmio**

{painel.premio}



⏰ **Duração**

{painel.tempo}



🏆 **Vencedores**

{painel.vencedores}



📋 **Requisitos**

{painel.requisitos}



👥 **Participantes:** 0



Clique no botão abaixo para participar!

""",

        color=discord.Color.gold(),

        timestamp=datetime.utcnow()

    )


    embed.set_footer(

        text="Boa sorte a todos 🍀"

    )



    mensagem = await painel.canal.send(

        embed=embed,

        view=BotaoParticipar()

    )



    sorteios_ativos[mensagem.id] = {


        "premio":

        painel.premio,


        "tempo":

        painel.tempo,


        "vencedores":

        painel.vencedores,


        "requisitos":

        painel.requisitos,


        "participantes":

        [],


        "mensagem":

        mensagem


    }



    await interaction.response.send_message(

        embed=discord.Embed(

            title="✅ Sorteio criado",

            description=f"O sorteio foi enviado em {painel.canal.mention}",

            color=discord.Color.green()

        ),

        ephemeral=True

    )



# ==========================================================
# EXTENSÃO DO PAINEL DE CONFIGURAÇÃO
# ==========================================================


class PainelSorteioFinal(PainelSorteio):


    def __init__(self):

        super().__init__()



    # ------------------------------------------------------
    # ESCOLHER CANAL
    # ------------------------------------------------------


    @discord.ui.button(

        label="📢 Canal",

        style=discord.ButtonStyle.secondary,

        row=2

    )

    async def canal_sorteio(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await abrir_selecao_canal(

            interaction,

            self

        )




    # ------------------------------------------------------
    # CRIAR SORTEIO
    # ------------------------------------------------------


    @discord.ui.button(

        label="🚀 Iniciar Sorteio",

        style=discord.ButtonStyle.success,

        row=3

    )

    async def iniciar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await enviar_sorteio(

            interaction,

            self

        )





# ==========================================================
# COMANDO !SORTEIO
# ==========================================================


@bot.command(
    name="sorteio"
)

async def sorteio(

    ctx

):


    embed = discord.Embed(

        title="🎉 Painel de Configuração de Sorteio",

        description="""

Configure seu sorteio usando os botões abaixo.


🎁 Prêmio

Defina o que será sorteado.


⏰ Tempo

Escolha a duração.


🏆 Vencedores

Defina quantas pessoas ganham.


📋 Requisitos

Defina regras para participar.


📢 Canal

Escolha onde o sorteio será enviado.


Quando terminar clique em:

🚀 Iniciar Sorteio

""",

        color=discord.Color.gold(),

        timestamp=datetime.utcnow()

    )


    embed.set_footer(

        text="Sistema Profissional de Sorteios"

    )



    await ctx.send(

        embed=embed,

        view=PainelSorteioFinal()

    )

