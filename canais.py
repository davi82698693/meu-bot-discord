import discord


async def criar_canais(bot):

    print("📂 Criando estrutura de canais...")


    for guild in bot.guilds:


        # ==========================
        # CATEGORIAS
        # ==========================

        categorias = [

            "📌 INFORMAÇÕES",

            "💬 COMUNIDADE",

            "🎫 ATENDIMENTO",

            "🔒 STAFF"

        ]


        criadas = {}


        for nome in categorias:


            categoria = discord.utils.get(
                guild.categories,
                name=nome
            )


            if categoria is None:

                categoria = await guild.create_category(
                    nome,
                    reason="Sistema automático de canais"
                )


            criadas[nome] = categoria



        # ==========================
        # CANAIS
        # ==========================


        canais = {


            "📌 INFORMAÇÕES": [

                "📢・anuncios",

                "📜・regras",

                "📝・atualizacoes"

            ],



            "💬 COMUNIDADE": [

                "💬・chat",

                "🤖・comandos",

                "🎨・midia"

            ],



            "🎫 ATENDIMENTO": [

                "🎫・suporte",

                "📋・tickets"

            ],



            "🔒 STAFF": [

                "🛡️・staff-chat",

                "📋・logs"

            ]

        }



        for categoria_nome, lista_canais in canais.items():


            categoria = criadas[categoria_nome]


            for nome_canal in lista_canais:


                existe = discord.utils.get(
                    guild.text_channels,
                    name=nome_canal
                )


                if existe is None:


                    await guild.create_text_channel(

                        nome_canal,

                        category=categoria,

                        reason="Sistema automático de canais"

                    )



        print(
            f"✅ Canais configurados em {guild.name}"
        )
