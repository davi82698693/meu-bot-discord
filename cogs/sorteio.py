import discord

from discord.ext import commands
from discord.ui import View

from datetime import datetime



# ==========================================
# CONFIGURAÇÃO
# ==========================================


class ConfigSorteio:

    def __init__(self):

        self.premio = None

        self.canal = None

        self.tempo = None

        self.requisitos = []



# ==========================================
# EMBED PADRÃO
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



# ==========================================
# COG
# ==========================================


class Sorteio(commands.Cog):


    def __init__(self, bot):

        self.bot = bot



    # guarda configurações abertas

    def criar_config(self):

        return ConfigSorteio()



    # ======================================
    # COMANDO !SORTEIO
    # ======================================


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


        config = self.criar_config()



        embed = criar_embed(

            "🎉 Criador de Sorteio",

            f"""
Configure seu sorteio usando os botões abaixo.


🎁 **Prêmio**

`❌ Não definido`


📢 **Canal**

`❌ Não definido`


⏰ **Tempo**

`❌ Não definido`


👥 **Requisitos**

`❌ Nenhum`


Quando terminar, clique em:

🚀 **Criar Sorteio**
""",

            discord.Color.gold()

        )



        await ctx.send(

            embed=embed,

            view=PainelSorteio(
                config
            )

        )





# ==========================================
# PAINEL DE CONFIGURAÇÃO
# ==========================================


class PainelSorteio(View):


    def __init__(
        self,
        config
    ):

        super().__init__(

            timeout=None

        )

        self.config = config



    # ======================================
    # DEFINIR PRÊMIO
    # ======================================


    @discord.ui.button(

        label="🎁 Definir Prêmio",

        style=discord.ButtonStyle.primary,

        custom_id="definir_premio"

    )

    async def premio(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await interaction.response.send_message(

            "🎁 Sistema de prêmio será configurado na próxima parte.",

            ephemeral=True

        )




    # ======================================
    # ESCOLHER CANAL
    # ======================================


    @discord.ui.button(

        label="📢 Escolher Canal",

        style=discord.ButtonStyle.secondary,

        custom_id="escolher_canal"

    )

    async def canal(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await interaction.response.send_message(

            "📢 Sistema de canal será configurado na próxima parte.",

            ephemeral=True

        )




    # ======================================
    # DEFINIR TEMPO
    # ======================================


    @discord.ui.button(

        label="⏰ Definir Tempo",

        style=discord.ButtonStyle.success,

        custom_id="definir_tempo"

    )

    async def tempo(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await interaction.response.send_message(

            "⏰ Sistema de tempo será configurado na próxima parte.",

            ephemeral=True

        )





    # ======================================
    # REQUISITOS
    # ======================================


    @discord.ui.button(

        label="👥 Requisitos",

        style=discord.ButtonStyle.secondary,

        custom_id="requisitos"

    )

    async def requisitos(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await interaction.response.send_message(

            "👥 Sistema de requisitos será configurado na próxima parte.",

            ephemeral=True

        )





    # ======================================
    # CRIAR SORTEIO
    # ======================================


    @discord.ui.button(

        label="🚀 Criar Sorteio",

        style=discord.ButtonStyle.danger,

        custom_id="criar_sorteio"

    )

    async def criar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        await interaction.response.send_message(

            embed=criar_embed(

                "⚠️ Configuração incompleta",

                "Configure todas as opções antes de iniciar o sorteio.",

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
