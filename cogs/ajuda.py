import discord

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select


# ==========================================================
# DADOS DAS CATEGORIAS
# ==========================================================

CATEGORIAS = {

    "basicos": {
        "nome": "⚙️ Geral",
        "descricao": "Comandos básicos do bot.",
        "comandos": [
            ("!help", "Mostra esta central de ajuda."),
            ("!invite", "Gera o link para convidar o bot para outro servidor."),
        ]
    },

    "antispam": {
        "nome": "🚫 Anti-spam",
        "descricao": "Proteção automática contra flood de mensagens (Administrador).",
        "comandos": [
            ("!ativarantispam", "Liga a proteção automática contra spam neste servidor."),
            ("!desativarantispam", "Desliga a proteção automática contra spam neste servidor."),
        ]
    },

    "sugestoes": {
        "nome": "💡 Sugestões",
        "descricao": "Membros sugerem ideias, votam com reação, e staff aprova/recusa.",
        "comandos": [
            ("!sugestoes-painel", "Envia o painel com o botão de sugerir neste canal."),
            ("!sugestoes-lista", "Lista as sugestões ainda pendentes de avaliação."),
        ]
    },

    "cargos": {
        "nome": "🎭 Cargos Automáticos",
        "descricao": "Membros escolhem sozinhos os próprios cargos, sem precisar de staff.",
        "comandos": [
            ("!cargos-admin", "Painel de administração: adicionar/remover cargos e enviar o painel público."),
        ]
    },

    "boasvindas": {
        "nome": "👋 Boas-vindas",
        "descricao": "Mensagens de entrada/saída com visual pronto. Configuração 100% por painel.",
        "comandos": [
            ("!boasvindas-painel", "Abre o painel: escolha os canais, ative/desative e teste o visual."),
        ]
    },

    "niveis": {
        "nome": "📈 Níveis",
        "descricao": "Ganhe XP conversando e suba de nível. Level up dá bônus de moedas se a Loja/Jogos estiver ativa.",
        "comandos": [
            ("!rank [@user]", "Mostra seu nível, XP e barra de progresso."),
            ("!levels", "Ranking dos 10 com maior nível do servidor."),
        ]
    },

    "jogos": {
        "nome": "🎮 Jogos & Economia",
        "descricao": "Sistema de moedas e 10 jogos pra passar o tempo. Todo mundo começa com 500 🪙.",
        "comandos": [
            ("!carteira", "Mostra seu saldo de moedas."),
            ("!diario", "Recompensa diária (200-500 🪙, uma vez a cada 24h)."),
            ("!pagar @user valor", "Transfere moedas pra outra pessoa."),
            ("!ranking", "Top 10 mais ricos do servidor."),
            ("!missao", "Missão de resgate — só libera quando você tem 50 🪙 ou menos."),
            ("!caracoroa cara/coroa valor", "Cara ou coroa."),
            ("!dado 1-6 valor", "Acerte o número do dado (paga x6)."),
            ("!roleta vermelho/preto/verde valor", "Roleta (verde paga x14)."),
            ("!slots valor", "Caça-níqueis."),
            ("!blackjack valor", "21 contra o bot, com botões."),
            ("!forca", "Jogo da forca — digite letras no chat."),
            ("!adivinhar", "Adivinhe um número de 1 a 100."),
            ("!ppt pedra/papel/tesoura valor", "Pedra, papel ou tesoura contra o bot."),
            ("!minerar", "Minere itens aleatórios (cooldown 30min)."),
            ("!pescar", "Pesque peixes aleatórios (cooldown 20min)."),
        ]
    },

    "loja": {
        "nome": "🛒 Loja",
        "descricao": "Sistema de vendas com estoque e aprovação manual. Gerenciar produtos exige Administrador; aprovar pedidos exige o cargo **✅Aprovador**.",
        "comandos": [
            ("!loja-admin", "Abre o painel de administração (botões e formulários — mais fácil que decorar comando)."),
            ("!loja-painel", "Envia o painel de compras (dropdown) no canal atual. Some sozinho o que estiver esgotado."),
            ("!editar-painel Título | Descrição", "Muda o texto do painel de compras (atualiza os já enviados)."),
            ("!loja-add-produto \"Nome\" \"Preço\" [descrição]", "(Alternativa por texto) Cadastra um novo produto."),
            ("!loja-add-estoque <ID> credencial", "(Alternativa por texto) Adiciona uma conta ao estoque."),
            ("!loja-produtos", "Lista todos os produtos e o estoque de cada um."),
            ("!loja-notas [ID do produto]", "Mostra a média de avaliações (geral ou de um produto específico)."),
            ("!loja-remover-produto <ID>", "Remove um produto da loja."),
            ("!loja-ver-estoque <ID>", "Lista os itens do estoque de um produto (numerados)."),
            ("!loja-remover-estoque <ID> <número>", "Remove um item específico do estoque."),
            ("!loja-stats", "Mostra faturamento total e produtos mais vendidos."),
            ("!loja-pix <chave>", "(Alternativa por texto) Configura a chave PIX."),
        ]
    },

    "moderacao": {
        "nome": "🛡️ Moderação",
        "descricao": "Comandos para manter o servidor organizado e seguro.",
        "comandos": [
            ("!setup-moderacao", "Cria/verifica os cargos e o canal de logs de moderação."),
            ("!ban @usuário [motivo]", "Bane um membro do servidor."),
            ("!unban <ID> [motivo]", "Desbane um usuário pelo ID."),
            ("!kick @usuário [motivo]", "Expulsa um membro do servidor."),
            ("!mute @usuário [motivo]", "Silencia um membro (cargo 🔇 Muted)."),
            ("!unmute @usuário", "Remove o silenciamento de um membro."),
            ("!warn @usuário [motivo]", "Aplica uma advertência a um membro."),
            ("!warns [@usuário]", "Mostra as advertências de um membro."),
            ("!clear <quantidade>", "Apaga mensagens do canal (padrão: 5)."),
            ("!lock", "Bloqueia o canal atual para mensagens."),
            ("!unlock", "Desbloqueia o canal atual."),
            ("!slowmode <segundos>", "Define o modo lento do canal (0 a 21600s)."),
            ("!nick @usuário [novo nome]", "Altera o apelido de um membro."),
        ]
    },

    "sorteios": {
        "nome": "🎉 Sorteios",
        "descricao": "Sistema completo de sorteios com painel interativo.",
        "comandos": [
            ("!sorteio", "Abre o painel para configurar e criar um novo sorteio."),
            ("!sorteios", "Lista todos os sorteios ativos no momento."),
            ("!sorteio-cancelar <ID>", "Cancela um sorteio que está rolando."),
            ("!sorteio-reroll <ID>", "Sorteia novo(s) vencedor(es) de um sorteio já finalizado."),
            ("!sorteio-editar <ID>", "Abre o painel para editar um sorteio ativo."),
        ]
    },

    "tickets": {
        "nome": "🎫 Tickets",
        "descricao": "Sistema de atendimento por botões (sem comandos de texto).",
        "comandos": [
            ("!setup-tickets", "Cria/verifica cargos, categoria, canal de logs e o painel de tickets."),
            ("🎫・suporte", "Painel fixo no canal — clique em Dúvidas, Suporte ou Denúncias para abrir um ticket."),
            ("!painel-ticket [#canal]", "Reenvia/recria o painel de tickets (no canal atual ou no indicado)."),
            ("🟢 Assumir Ticket", "Botão dentro do ticket — apenas Staff/Suporte."),
            ("📢 Chamar Staff", "Botão dentro do ticket — notifica a equipe."),
            ("👤 Chamar Membro", "Botão dentro do ticket — apenas Staff/Suporte."),
            ("🔒 Fechar Ticket", "Botão dentro do ticket — apenas Staff/Suporte."),
        ]
    },

    "verificacao": {
        "nome": "🔰 Verificação",
        "descricao": "Sistema de verificação de novos membros por botão (sem comandos de texto).",
        "comandos": [
            ("!setup-verificacao", "Cria/verifica o cargo e o canal de verificação."),
            ("🔓 Verificar", "Botão fixo no canal 🔰・verificacao — libera o acesso ao servidor."),
        ]
    },

}


# ==========================================================
# EMBEDS
# ==========================================================

def embed_geral(bot):

    embed = discord.Embed(
        title="📖 Central de Ajuda",
        description=(
            "Selecione uma categoria no menu abaixo para ver os comandos "
            "detalhados, ou confira o resumo geral aqui embaixo.\n\n"
            "Prefixo dos comandos: **`!`**"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )

    for chave, dados in CATEGORIAS.items():

        embed.add_field(
            name=dados["nome"],
            value=dados["descricao"],
            inline=False
        )

    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.set_footer(text="Use o menu abaixo para navegar")

    return embed


def embed_categoria(chave):

    dados = CATEGORIAS[chave]

    embed = discord.Embed(
        title=dados["nome"],
        description=dados["descricao"],
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )

    for comando, explicacao in dados["comandos"]:

        embed.add_field(
            name=comando,
            value=explicacao,
            inline=False
        )

    embed.set_footer(text="Use o menu abaixo para voltar ou trocar de categoria")

    return embed


# ==========================================================
# VIEW COM MENU DE CATEGORIAS
# ==========================================================

class AjudaView(View):

    def __init__(self, bot):

        super().__init__(timeout=120)

        self.bot = bot

        self.add_item(SelecionarCategoria(bot))


class SelecionarCategoria(Select):

    def __init__(self, bot):

        self.bot = bot

        opcoes = [
            discord.SelectOption(
                label="📖 Visão geral",
                value="geral",
                description="Resumo de todas as categorias"
            )
        ]

        for chave, dados in CATEGORIAS.items():

            opcoes.append(
                discord.SelectOption(
                    label=dados["nome"],
                    value=chave,
                    description=dados["descricao"][:100]
                )
            )

        super().__init__(
            placeholder="Escolha uma categoria...",
            options=opcoes,
            min_values=1,
            max_values=1
        )


    async def callback(self, interaction: discord.Interaction):

        escolha = self.values[0]

        if escolha == "geral":
            embed = embed_geral(self.bot)
        else:
            embed = embed_categoria(escolha)

        await interaction.response.edit_message(embed=embed, view=self.view)


# ==========================================================
# COG
# ==========================================================

class Ajuda(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="help", aliases=["ajuda", "comandos"])
    async def help_cmd(self, ctx):

        view = AjudaView(self.bot)

        await ctx.send(
            embed=embed_geral(self.bot),
            view=view
        )


    @commands.command(name="invite", aliases=["convite", "convidar"])
    async def invite_cmd(self, ctx):

        permissoes = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            manage_messages=True,
            manage_channels=True,
            manage_roles=True,
            manage_nicknames=True,
            kick_members=True,
            ban_members=True,
        )

        link = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissoes,
            scopes=("bot", "applications.commands")
        )

        embed = discord.Embed(
            title="🔗 Convide o bot para o seu servidor!",
            description=(
                f"[**Clique aqui para adicionar o bot**]({link})\n\n"
                "O link já vem com as permissões necessárias para "
                "todos os sistemas (moderação, tickets, verificação e sorteios)."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        if self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Ajuda(bot)
    )
