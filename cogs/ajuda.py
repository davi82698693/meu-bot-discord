import discord
from datetime import datetime, timezone
from typing import Optional
from discord.ext import commands
from discord.ui import View, Select, Button

# (Reutilize a sua definição de CATEGORIAS original aqui; estou mantendo a mesma estrutura.)
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
        ],
    },
    # ... (mantenha as outras categorias exatamente como no seu arquivo)
    "loja-robux": {
        "nome": "🎮 Loja Robux",
        "descricao": "Sistema completo de compra de Robux com carrinho, aprovação em 2 passos e cálculo automático. Usuários compram, admins aprovam.",
        "comandos": [
            ("!/loja-carrinho-novo", "Abre o formulário: informe nick do Roblox, quantidade de Robux e método (com/sem taxa)."),
            ("!loja-carrinho-aprovar <ID>", "Admin aprova um carrinho aguardando (com botões: Aprovar ou Rejeitar)."),
            ("!loja-carrinhos-pendentes", "Lista todos os carrinhos aguardando aprovação de admin."),
            ("!/loja-robux-preco <valor> [taxa]", "Define o preço de 1.000 Robux em R$ e a taxa da gamepass (padrão 30%)."),
            ("!loja-robux-painel", "Envia o painel público com o botão de comprar Robux no canal atual."),
        ],
    },
    # ... copie as demais categorias do seu arquivo original
}

# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
def saudacao() -> str:
    # Horário BR (UTC-3)
    hora_br = (datetime.now(timezone.utc).hour - 3) % 24
    if 5 <= hora_br < 12:
        return "Bom dia"
    if 12 <= hora_br < 18:
        return "Boa tarde"
    return "Boa noite"

def build_category_embed(chave: str, guild: Optional[discord.Guild] = None) -> discord.Embed:
    dados = CATEGORIAS.get(chave)
    if not dados:
        return discord.Embed(title="Categoria não encontrada", description="Chave inválida.", color=discord.Color.red())

    title = dados.get("nome", chave)
    desc = dados.get("descricao", "")
    embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))

    # Adiciona comandos como campos — mantém embed legível e evita ultrapassar limites
    comandos = dados.get("comandos", [])
    if chave == "loja-robux":
        # Tratamento especial para Loja Robux — instruções passo a passo
        embed.add_field(
            name="Como comprar Robux",
            value=(
                "1) Execute `/loja-carrinho-novo` ou use o formulário via painel.\n"
                "2) Informe seu nick do Roblox, a quantidade de Robux e se quer com/sem taxa.\n"
                "3) O carrinho ficará pendente até que um admin aprove.\n"
                "4) Admins usam `!loja-carrinho-aprovar <ID>` para Aprovar ou Rejeitar.\n"
                "5) Após aprovação, o usuário recebe o Robux/conta ou instruções de pagamento.\n\n"
                "Observações: configure o preço com `!/loja-robux-preco` e verifique o estoque com `!loja-ver-estoque`."
            ),
            inline=False,
        )
        # Lista comandos principais
        for nome, texto in comandos:
            embed.add_field(name=nome, value=texto, inline=False)
    else:
        # comandos gerais — agrupa em blocos para evitar embeds enormes
        text = ""
        for cmd, info in comandos:
            text += f"**{cmd}** — {info}\n"
        # corta caso seja muito grande
        if len(text) > 1024:
            # coloca só os primeiros e informa que há continuação
            embed.add_field(name="Comandos (parte)", value=text[:1000] + "\n...", inline=False)
        else:
            embed.add_field(name="Comandos", value=text or "Nenhum comando listado.", inline=False)

    if guild:
        embed.set_footer(text=f"{guild.name} • {saudacao()}")

    return embed

# ==========================================================
# VIEW e COMPONENTS
# ==========================================================
class CategorySelect(Select):
    def __init__(self):
        options = []
        for chave, dados in CATEGORIAS.items():
            description = dados.get("descricao", "")
            # garantir descrição curta (Select limita tamanho)
            desc_short = (description[:95] + "...") if len(description) > 95 else description
            options.append(discord.SelectOption(label=dados.get("nome", chave), value=chave, description=desc_short))
        super().__init__(placeholder="Escolha uma categoria...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chave = self.values[0]
        embed = build_category_embed(chave, guild=interaction.guild)
        # substitui view por uma que contenha botão Voltar
        await interaction.response.edit_message(embed=embed, view=CategoryView(original_author=interaction.user))

class BackButton(Button):
    def __init__(self):
        super().__init__(label="🔙 Voltar", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view = HelpView(self.view.bot, original_author=interaction.user, guild=interaction.guild)
        embed = discord.Embed(
            title="🎛️ Central de Controle",
            description=f"Olá, **{interaction.user.display_name}**! {saudacao()} 👋\n\nEscolha uma categoria abaixo pra ver os comandos.\n\nPrefixo: **`!`** ou **`/`**",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.response.edit_message(embed=embed, view=view)

class CategoryView(View):
    def __init__(self, original_author: discord.User):
        super().__init__(timeout=None)
        self.original_author = original_author
        # adiciona botão voltar
        self.add_item(BackButton())

class HelpView(View):
    def __init__(self, bot: commands.Bot, original_author: discord.User, guild: Optional[discord.Guild]):
        super().__init__(timeout=None)
        self.bot = bot
        self.original_author = original_author
        # select de categorias
        self.add_item(CategorySelect())
        # botão de referência rápido para loja-robux (opcional)
        if "loja-robux" in CATEGORIAS:
            self.add_item(Button(label="Loja Robux (info rápida)", style=discord.ButtonStyle.primary, custom_id="loja_robux_info"))
        # adiciona botão de fechar (apenas para autor)
        self.add_item(Button(label="Fechar", style=discord.ButtonStyle.danger, custom_id="ajuda_fechar"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # permite que qualquer pessoa use, mas você pode limitar ao autor:
        # return interaction.user.id == self.original_author.id
        return True

    async def on_timeout(self) -> None:
        # remove componentes ao expirar
        pass

    @discord.ui.button(label="Fechar", style=discord.ButtonStyle.danger, row=2)
    async def fechar_button(self, button: Button, interaction: discord.Interaction):
        # apenas fecha a mensagem para o usuário
        try:
            await interaction.message.delete()
        except Exception:
            await interaction.response.send_message("Não foi possível apagar a mensagem.", ephemeral=True)

# ==========================================================
# COG
# ==========================================================
class Ajuda(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # registra views persistentes (opcional)
        self.bot.add_view(HelpView(self.bot, original_author=None, guild=None))
        self.bot.add_view(CategoryView(original_author=None))

    @commands.hybrid_command(name="help", aliases=["ajuda", "comandos"])
    async def help_cmd(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎛️ Central de Controle",
            description=(
                f"Olá, **{ctx.author.display_name}**! {saudacao()} 👋\n\n"
                "Escolha uma categoria abaixo pra ver os comandos.\n\n"
                "Prefixo: **`!`** ou **`/`**"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        # thumbnail do bot (se disponível)
        if self.bot.user and getattr(self.bot.user, "display_avatar", None):
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        view = HelpView(self.bot, original_author=ctx.author, guild=ctx.guild)
        await ctx.send(embed=embed, view=view)

# ==========================================================
# SETUP
# ==========================================================
async def setup(bot: commands.Bot):
    await bot.add_cog(Ajuda(bot))
