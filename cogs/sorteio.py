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
