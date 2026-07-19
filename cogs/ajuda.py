import discord

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button


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
            ("!stats", "Mostra um dashboard com estatísticas do servidor e do bot."),
            ("!backup", "Gera um arquivo .zip com todos os dados configurados (Administrador)."),
            ("!restore", "Restaura dados a partir de um backup .zip anexado (Administrador, só via !)."),
        ]
    },

    "automod": {
        "nome": "🚨 AutoMod",
        "descricao": "Bloqueia mensagens com palavras proibidas e avisa num canal de log.",
        "comandos": [
            ("!automod-painel", "Painel: adicionar/remover palavras e escolher o canal de log."),
            ("!automod-ativar", "Liga o bloqueio automático."),
            ("!automod-desativar", "Desliga o bloqueio automático."),
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

    "logs": {
        "nome": "📋 Logs",
        "descricao": "Configure pra onde cada tipo de log vai (moderação, tickets, loja, etc).",
        "comandos": [
            ("!logs-painel", "Abre o painel: escolha a categoria e depois o canal de destino."),
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

    "autorole": {
        "nome": "🏷️ Cargo Automático",
        "descricao": "Todo novo membro recebe cargo(s) automaticamente ao entrar.",
        "comandos": [
            ("!autorole-painel", "Escolhe quais cargos são dados automaticamente e ativa/desativa."),
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
            ("!loja-modelos", "Modelos de painel salvos: enviar, editar produtos, renomear ou excluir."),
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
            ("!delwarn @usuário <número>", "Remove uma advertência específica (veja o número com !warns)."),
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
            ("!tickets-categoria", "Escolhe em qual categoria os tickets são criados."),
            ("!tickets-cargo-atendente", "Escolhe qual cargo pode ver/assumir/fechar tickets."),
            ("🟢 Assumir Ticket", "Botão dentro do ticket — apenas Staff/Suporte."),
            ("📢 Chamar Staff", "Botão dentro do ticket — notifica a equipe."),
            ("👤 Chamar Membro", "Botão dentro do ticket — apenas Staff/Suporte."),
            ("🔒 Fechar Ticket", "Botão dentro do ticket — apenas Staff/Suporte."),
        ]
    },

    "conquistas": {
        "nome": "🏆 Conquistas",
        "descricao": "Badges desbloqueadas automaticamente ao atingir marcos no servidor.",
        "comandos": [
            ("!conquistas [@user]", "Mostra as conquistas de alguém."),
            ("!conquistas-ranking", "Top 10 com mais conquistas."),
        ]
    },

    "salasvoz": {
        "nome": "🔊 Salas de Voz Temporárias",
        "descricao": "Entrar no canal gatilho cria uma sala só sua, que some quando esvazia.",
        "comandos": [
            ("!salasvoz-painel", "Escolhe o canal de voz gatilho (Administrador)."),
        ]
    },

    "cosmeticos": {
        "nome": "✨ Loja de Cosméticos",
        "descricao": "Compre cargos especiais usando as moedas do sistema de jogos.",
        "comandos": [
            ("!loja-cosmeticos", "Mostra a loja e permite comprar itens."),
            ("!cosmeticos-admin", "Cadastra/remove itens à venda (Administrador)."),
        ]
    },

    "drops": {
        "nome": "💰 Drops",
        "descricao": "Baús de moedas caem aleatoriamente no chat, quem clica primeiro leva.",
        "comandos": [
            ("!drops-painel", "Configura canal, intervalo e valor dos baús (Administrador)."),
        ]
    },

    "parcerias": {
        "nome": "🤝 Parcerias",
        "descricao": "Outros servidores pedem parceria, você aprova/recusa, publica automaticamente.",
        "comandos": [
            ("!parcerias-painel", "Envia o botão de pedir parceria neste canal."),
            ("!parcerias-canal-pedidos #canal", "Define onde os pedidos aparecem pra staff avaliar."),
            ("!parcerias-canal-publicar #canal", "Define onde parcerias aprovadas são publicadas."),
        ]
    },

    "convites": {
        "nome": "📨 Convites",
        "descricao": "Veja quem convidou quem pro servidor.",
        "comandos": [
            ("!convites [@user]", "Quantos membros essa pessoa trouxe."),
            ("!convites-ranking", "Top 10 quem mais convidou."),
        ]
    },

    "aniversarios": {
        "nome": "🎂 Aniversários",
        "descricao": "Cadastre seu aniversário e receba parabéns automático no dia.",
        "comandos": [
            ("!aniversario DD/MM", "Define seu aniversário."),
            ("!aniversario", "Mostra o que você já definiu."),
            ("!aniversarios-canal #canal", "Define onde os parabéns aparecem (Administrador)."),
            ("!aniversarios-lista", "Lista todo mundo cadastrado."),
        ]
    },

    "backup": {
        "nome": "💾 Backup",
        "descricao": "Exporte ou restaure todos os dados configurados do bot.",
        "comandos": [
            ("!backup", "Gera um .zip com todos os dados (Administrador)."),
            ("!restore", "Restaura a partir de um .zip anexado, só via ! (Administrador)."),
            ("!stats", "Dashboard com estatísticas do servidor e do bot."),
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

def saudacao():

    hora_br = (datetime.now(timezone.utc).hour - 3) % 24

    if 5 <= hora_br < 12:
        return "Bom dia"

    if 12 <= hora_br < 18:
        return "Boa tarde"

    return "Boa noite"


def texto_categoria(chave):

    dados = CATEGORIAS[chave]

    linhas = [f"## {dados['nome']}", dados["descricao"], ""]

    for comando, explicacao in dados["comandos"]:

        linhas.append(f"**{comando}**\n{explicacao}")

    return "\n\n".join(linhas)


# ==========================================================
# LAYOUT — CENTRAL DE CONTROLE (Components V2)
# ==========================================================

class BotaoCategoria(discord.ui.Button):

    def __init__(self, chave, nome):

        super().__init__(
            label=nome,
            style=discord.ButtonStyle.secondary,
            custom_id=f"ajuda_categoria_{chave}"
        )

        self.chave = chave


    async def callback(self, interaction: discord.Interaction):

        await interaction.response.edit_message(
            view=CategoriaLayout(self.chave)
        )


class BotaoVoltar(discord.ui.Button):

    def __init__(self):

        super().__init__(
            label="🔙 Voltar",
            style=discord.ButtonStyle.primary,
            custom_id="ajuda_voltar"
        )


    async def callback(self, interaction: discord.Interaction):

        await interaction.response.edit_message(
            view=CentralControleLayout(interaction.client, interaction.user, interaction.guild)
        )


class CategoriaLayout(discord.ui.LayoutView):

    def __init__(self, chave="basicos"):

        super().__init__(timeout=None)

        container = discord.ui.Container(accent_color=discord.Color.blurple())

        container.add_item(discord.ui.TextDisplay(texto_categoria(chave)))

        container.add_item(discord.ui.Separator())

        linha = discord.ui.ActionRow()
        linha.add_item(BotaoVoltar())

        container.add_item(linha)

        self.add_item(container)


class CentralControleLayout(discord.ui.LayoutView):

    def __init__(self, bot, user, guild):

        super().__init__(timeout=None)

        container = discord.ui.Container(accent_color=discord.Color.blurple())

        nome_usuario = user.display_name if user else "administrador"

        cabecalho = (
            f"## 🎛️ Central de Controle\n"
            f"Olá, **{nome_usuario}**! {saudacao()} 👋\n\n"
            "Escolha uma categoria abaixo pra ver os comandos.\n\n"
            "Prefixo: **`!`** ou **`/`**"
        )

        if bot.user and bot.user.display_avatar:

            secao = discord.ui.Section(
                cabecalho,
                accessory=discord.ui.Thumbnail(bot.user.display_avatar.url)
            )

            container.add_item(secao)

        else:

            container.add_item(discord.ui.TextDisplay(cabecalho))

        container.add_item(discord.ui.Separator())

        chaves = list(CATEGORIAS.items())

        for i in range(0, len(chaves), 5):

            linha = discord.ui.ActionRow()

            for chave, dados in chaves[i:i + 5]:
                linha.add_item(BotaoCategoria(chave, dados["nome"]))

            container.add_item(linha)

        if guild:
            container.add_item(discord.ui.TextDisplay(f"-# {guild.name} • {len(CATEGORIAS)} categorias disponíveis"))

        self.add_item(container)


# ==========================================================
# COG
# ==========================================================

class Ajuda(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    async def cog_load(self):

        self.bot.add_view(CentralControleLayout(self.bot, self.bot.user, None))
        self.bot.add_view(CategoriaLayout())


    @commands.hybrid_command(name="help", aliases=["ajuda", "comandos"])
    async def help_cmd(self, ctx):

        await ctx.send(
            view=CentralControleLayout(self.bot, ctx.author, ctx.guild)
        )


    @commands.hybrid_command(name="invite", aliases=["convite", "convidar"])
    async def invite_cmd(self, ctx):

        permissoes = discord.Permissions(administrator=True)

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
