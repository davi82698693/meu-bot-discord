import discord


# ==========================================
# ESTRUTURA DO SERVIDOR
# ==========================================

ESTRUTURA = {

    "📌 INFORMAÇÕES": [

        "📜・regras",
        "📢・anuncios",
        "👋・boas-vindas"

    ],


    "💬 COMUNIDADE": [

        "💬・chat",
        "🤖・comandos",
        "🎮・midia"

    ],


    "🎫 SUPORTE": [

        "🎫・suporte",
        "📋・logs-tickets"

    ],


    "🛡️ STAFF": [

        "🔒・chat-staff",
        "📋・logs-moderação",
        "📋・logs-servidor"

    ]

}



# ==========================================
# CRIAR CATEGORIAS E CANAIS
# ==========================================

async def criar_canais(guild):


    for nome_categoria, canais in ESTRUTURA.items():


        # Procura categoria existente

        categoria = discord.utils.get(
            guild.categories,
            name=nome_categoria
        )


        # Se não existir, cria

        if categoria is None:

            categoria = await guild.create_category(
                name=nome_categoria,
                reason="Configuração automática do servidor"
            )



        # Criar canais dentro dela

        for nome_canal in canais:


            canal = discord.utils.get(
                guild.text_channels,
                name=nome_canal
            )


            if canal is None:

                await guild.create_text_channel(

                    name=nome_canal,

                    category=categoria,

                    reason="Configuração automática do servidor"

                )
