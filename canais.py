import discord

from discord.ext import commands
from datetime import datetime


# ==========================================
# CONFIGURAÇÕES
# ==========================================

CATEGORIAS = [

    "📌 INFORMAÇÕES",
    "💬 COMUNIDADE",
    "🎫 ATENDIMENTO",
    "🔒 STAFF"

]


CANAIS = {

    "📌 INFORMAÇÕES": [

        "📢・anuncios",
        "📜・regras",
        "👋・boas-vindas"

    ],


    "💬 COMUNIDADE": [

        "💬・chat",
        "🎮・jogos",
        "📷・midia"

    ],


    "🎫 ATENDIMENTO": [

        "🎫・suporte"

    ],


    "🔒 STAFF": [

        "🔒・chat-staff",
        "📋・logs"

    ]

}



# ==========================================
# SISTEMA DE CANAIS
# ==========================================

class Canais(commands.Cog):


    def __init__(self, bot):

        self.bot = bot



    @commands.Cog.listener()
    async def on_ready(self):

        print("📁 Sistema de canais carregado.")


        for guild in self.bot.guilds:


            for nome_categoria in CATEGORIAS:


                categoria = discord.utils.get(

                    guild.categories,

                    name=nome_categoria

                )


                if categoria is None:


                    categoria = await guild.create_category(

                        nome_categoria,

                        reason="Sistema automático de canais"

                    )



                for nome_canal in CANAIS[nome_categoria]:


                    canal = discord.utils.get(

                        guild.text_channels,

                        name=nome_canal

                    )


                    if canal is None:


                        await guild.create_text_channel(

                            nome_canal,

                            category=categoria,

                            reason="Sistema automático de canais"

                        )



# ==========================================
# CARREGAR COG
# ==========================================

async def setup(bot):

    await bot.add_cog(

        Canais(bot)

    )
