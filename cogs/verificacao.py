import discord

from discord.ext import commands
from discord.ui import View

from datetime import datetime



CARGO_VERIFICADO = "✅ Verificado"

CANAL_VERIFICACAO = "🔰・verificacao"



# ==================================
# EMBED
# ==================================

def embed(
    titulo,
    descricao,
    cor=discord.Color.green()
):

    e = discord.Embed(

        title=titulo,

        description=descricao,

        color=cor,

        timestamp=datetime.utcnow()

    )


    e.set_footer(
        text="🔰 Sistema de Verificação"
    )


    return e




# ==================================
# COG
# ==================================

class Verificacao(commands.Cog):


    def __init__(self, bot):

        self.bot = bot




    @commands.Cog.listener()
    async def on_ready(self):

        print(
            "🔰 Sistema de verificação carregado."
        )


        self.bot.add_view(
            BotaoVerificacao()
        )



        for guild in self.bot.guilds:



            # ==========================
            # CARGO
            # ==========================


            cargo = discord.utils.get(

                guild.roles,

                name=CARGO_VERIFICADO

            )


            if cargo is None:


                await guild.create_role(

                    name=CARGO_VERIFICADO,

                    reason="Sistema de verificação"

                )




            # ==========================
            # CANAL
            # ==========================


            canal = discord.utils.get(

                guild.text_channels,

                name=CANAL_VERIFICACAO

            )


            if canal is None:


                canal = await guild.create_text_channel(

                    CANAL_VERIFICACAO,

                    reason="Sistema de verificação"

                )



                mensagem = embed(

                    "🔰 Verificação",

                    """
Bem-vindo ao servidor! 👋


Para liberar seu acesso, clique no botão abaixo.


🔒 Isso evita contas falsas e mantém o servidor seguro.


Clique em **🔓 Verificar** para continuar.
""",

                    discord.Color.blue()

                )



                await canal.send(

                    embed=mensagem,

                    view=BotaoVerificacao()

                )





# ==================================
# BOTÃO
# ==================================

class BotaoVerificacao(View):


    def __init__(self):

        super().__init__(

            timeout=None

        )



    @discord.ui.button(

        label="🔓 Verificar",

        style=discord.ButtonStyle.success,

        custom_id="botao_verificacao"

    )

    async def verificar(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):


        cargo = discord.utils.get(

            interaction.guild.roles,

            name=CARGO_VERIFICADO

        )



        if cargo is None:


            return await interaction.response.send_message(

                "❌ Cargo de verificação não encontrado.",

                ephemeral=True

            )




        if cargo in interaction.user.roles:


            return await interaction.response.send_message(

                "✅ Você já está verificado.",

                ephemeral=True

            )




        await interaction.user.add_roles(

            cargo,

            reason="Usuário verificado"

        )



        await interaction.response.send_message(

            embed=embed(

                "✅ Verificado!",

                "Você recebeu acesso ao servidor.",

                discord.Color.green()

            ),

            ephemeral=True

        )





# ==================================
# SETUP
# ==================================

async def setup(bot):

    await bot.add_cog(

        Verificacao(bot)

    )
