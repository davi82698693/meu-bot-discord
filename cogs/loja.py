import discord
import os
import json
import math
import random
import time
import asyncio

from datetime import datetime, timezone

from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput, RoleSelect

from .logs import obter_canal_log


# ==========================================================
# CONFIG / PERSISTÊNCIA
# ==========================================================

DATA_DIR = (
    os.getenv("LOJA_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "loja_data.json")
QRCODE_FILE = os.path.join(DATA_DIR, "loja_qrcode.png")

LOG_CHANNEL_NAME = "logs-loja"


def _parse_donos():

    bruto = os.getenv("LOJA_DONO_IDS", "")

    ids = set()

    for parte in bruto.split(","):

        parte = parte.strip()

        if parte.isdigit():
            ids.add(int(parte))

    return ids


DONO_IDS = _parse_donos()


async def _obter_membro(bot, user_id, guild_id):

    if guild_id is None:
        return None

    guild = bot.get_guild(guild_id)

    if guild is None:
        return None

    membro = guild.get_member(user_id)

    if membro is None:

        try:
            membro = await guild.fetch_member(user_id)
        except Exception:
            return None

    return membro


async def eh_dono(bot, user_id, guild_id=None):

    if user_id in DONO_IDS:
        return True

    membro = await _obter_membro(bot, user_id, guild_id)

    if membro is None:
        return False

    return membro.guild_permissions.administrator


CARGO_APROVADOR = os.getenv("LOJA_CARGO_APROVADOR", "✅Aprovador")


async def pode_aprovar(bot, user_id, guild_id=None):

    if user_id in DONO_IDS:
        return True

    membro = await _obter_membro(bot, user_id, guild_id)

    if membro is None:
        return False

    return any(
        cargo.name.lower() == CARGO_APROVADOR.lower()
        for cargo in membro.roles
    )


async def obter_donos_para_notificar(bot, guild_id):

    ids = set(DONO_IDS)

    if guild_id is None:
        return ids

    guild = bot.get_guild(guild_id)

    if guild is None:
        return ids

    cargo = discord.utils.get(guild.roles, name=CARGO_APROVADOR)

    if cargo:

        for membro in cargo.members:

            if not membro.bot:
                ids.add(membro.id)

    return ids



def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"produtos": {}, "pedidos": {}, "config": {}, "avaliacoes": []}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("produtos", {})
            dados.setdefault("pedidos", {})
            dados.setdefault("config", {})
            dados.setdefault("avaliacoes", [])
            return dados
    except Exception as e:
        print(f"⚠️ Erro ao carregar loja_data.json: {e}")
        return {"produtos": {}, "pedidos": {}, "config": {}, "avaliacoes": []}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar loja_data.json: {e}")


async def enviar_log(bot, guild, texto, cor=discord.Color.blurple()):

    if guild is None:
        return

    canal_log = obter_canal_log(bot, guild, "loja")

    if canal_log is None:

        canal_log = discord.utils.get(
            guild.text_channels,
            name=LOG_CHANNEL_NAME
        )

    if canal_log is None:
        return

    try:
        await canal_log.send(
            embed=discord.Embed(
                description=texto,
                color=cor,
                timestamp=datetime.now(timezone.utc)
            )
        )
    except Exception:
        pass


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🛒 Sistema de Loja")

    return embed


def container_view(texto, source_view, accent_color=discord.Color.gold()):
    """
    Pega os botões/selects já existentes de uma View comum e monta um
    LayoutView com Container (visual novo), sem duplicar a lógica dos botões.
    """

    layout = discord.ui.LayoutView(timeout=None)

    container = discord.ui.Container(accent_color=accent_color)

    container.add_item(discord.ui.TextDisplay(texto))
    container.add_item(discord.ui.Separator())

    por_row = {}

    for item in list(source_view.children):
        por_row.setdefault(item.row or 0, []).append(item)

    for numero in sorted(por_row):

        linha = discord.ui.ActionRow()

        for item in por_row[numero]:
            linha.add_item(item)

        container.add_item(linha)

    layout.add_item(container)

    return layout


def _validar_nick_roblox(nick: str):
    """
    Validação simples de nick do Roblox: 3 a 20 caracteres, só letras,
    números e underscore. Retorna None se válido, ou uma mensagem de erro.
    """

    nick = nick.strip()

    if not (3 <= len(nick) <= 20):
        return "O nick precisa ter entre 3 e 20 caracteres."

    if not all(c.isalnum() or c == "_" for c in nick):
        return "O nick só pode ter letras, números e underscore ( _ )."

    return None


def embed_robux_painel():
    """Embed público explicando o funcionamento da compra de Robux."""

    return embed_padrao(
        "🎮 Compre Robux",
        (
            "Clique no botão abaixo para comprar Robux.\n\n"
            "Você vai precisar informar:\n"
            "🧍 Seu **nick do Roblox** (o nick de **criação da conta**, não o nick de exibição)\n"
            "🔢 A **quantidade de Robux** desejada\n\n"
            "Depois é só escolher se a entrega vai ser:\n"
            "💸 **Com taxa** — via Gamepass (o Roblox desconta uma taxa, então a gamepass "
            "é criada com um valor um pouco maior que os Robux que você recebe)\n"
            "🎁 **Sem taxa** — via grupo/trade, sem desconto extra\n\n"
            "O valor a pagar em R$ é calculado automaticamente. 👇"
        ),
        discord.Color.gold()
    )


def formatar_valor_brl(valor):
    """Formata um float no padrão brasileiro (vírgula decimal), igual ao resto da loja."""

    return f"{valor:.2f}".replace(".", ",")


def calcular_valores_robux(cog, quantidade, com_taxa):
    """
    Retorna (valor_reais, valor_gamepass) para uma compra de Robux, ou
    (None, None) se o preço ainda não foi configurado pelo dono da loja.
    """

    preco_k = cog.dados["config"].get("robux_preco_k")

    if not preco_k:
        return None, None

    taxa_percentual = cog.dados["config"].get("robux_taxa_percentual", 30)

    valor_reais = (quantidade / 1000) * preco_k

    if com_taxa:
        fator = 1 - (taxa_percentual / 100)
        valor_gamepass = math.ceil(quantidade / fator)
    else:
        valor_gamepass = quantidade

    return valor_reais, valor_gamepass



# ==========================================================
# COG
# ==========================================================

class Loja(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        if not DONO_IDS:
            print(
                "ℹ️ LOJA_DONO_IDS não configurado — usando apenas quem tiver "
                "permissão de Administrador no servidor."
            )

        # registra a view do painel (rota fixa pro select funcionar após restart)
        self.bot.add_view(LojaPainelView(self))

        # registra os painéis de administração (nunca expiram)
        self.bot.add_view(PainelAdminView(self))

        # registra o painel de compra de Robux (nunca expira)
        self.bot.add_view(RobuxPainelView(self))
        self.bot.add_view(ModelosView(self))

        # reregistra views de pedidos em andamento
        for pedido_id, pedido in list(self.dados["pedidos"].items()):

            if pedido["status"] == "aguardando_pagamento":
                self.bot.add_view(PagamentoView(pedido_id))

            elif pedido["status"] == "aguardando_aprovacao":
                self.bot.add_view(AprovarView(pedido_id))

            elif pedido["status"] == "aprovado" and not pedido.get("avaliado"):
                self.bot.add_view(AvaliarView(pedido_id))


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Faltou argumento",
                    f"Faltou informar: `{error.param.name}`",
                    discord.Color.red()
                )
            )

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(
            embed=embed_padrao(
                "❌ Erro",
                f"```{type(error).__name__}: {error}```",
                discord.Color.red()
            )
        )


    async def _checar_dono(self, ctx):

        return await eh_dono(
            self.bot,
            ctx.author.id,
            ctx.guild.id if ctx.guild else None
        )


    # ======================================================
    # ADICIONAR PRODUTO
    # ======================================================

    @app_commands.describe(nome="Nome do produto", preco="Preço (ex: 25,00)", descricao="Descrição do produto")
    @commands.hybrid_command(name="loja-add-produto")
    async def loja_add_produto(self, ctx, nome: str, preco: str, *, descricao: str = "Sem descrição."):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        produto_id = str(random.randint(1000, 9999))

        while produto_id in self.dados["produtos"]:
            produto_id = str(random.randint(1000, 9999))

        self.dados["produtos"][produto_id] = {
            "nome": nome,
            "preco": preco,
            "descricao": descricao,
            "estoque": []
        }

        self.salvar()

        await ctx.send(
            embed=embed_padrao(
                "✅ Produto criado",
                f"**{nome}** — R$ {preco}\n📦 Estoque: 0\n🆔 ID: `{produto_id}`\n\n"
                f"Use `!loja-add-estoque {produto_id} usuario:senha` para adicionar contas.",
                discord.Color.green()
            )
        )


    # ======================================================
    # ADICIONAR ESTOQUE
    # ======================================================

    @commands.command(name="loja-add-estoque")
    async def loja_add_estoque(self, ctx, produto_id: str, *, credencial: str = None):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        produto = self.dados["produtos"].get(produto_id)

        if produto is None:
            return await ctx.send(
                embed=embed_padrao("❌ Produto não encontrado", f"Não existe produto com ID `{produto_id}`.", discord.Color.red())
            )

        adicionados = 0

        if ctx.message.attachments:

            for anexo in ctx.message.attachments:

                try:
                    conteudo = (await anexo.read()).decode("utf-8", errors="ignore")
                except Exception:
                    continue

                for linha in conteudo.splitlines():

                    linha = linha.strip()

                    if linha:
                        produto["estoque"].append(linha)
                        adicionados += 1

        elif credencial:

            produto["estoque"].append(credencial.strip())
            adicionados = 1

        if adicionados == 0:
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Nada foi adicionado",
                    "Passe a credencial depois do ID, ou anexe um arquivo `.txt` com uma credencial por linha.",
                    discord.Color.red()
                )
            )

        self.salvar()

        await atualizar_todos_paineis(self)

        await ctx.send(
            embed=embed_padrao(
                "✅ Estoque atualizado",
                f"**{produto['nome']}**\n➕ {adicionados} adicionada(s)\n"
                f"📦 Estoque atual: {len(produto['estoque'])}",
                discord.Color.green()
            )
        )


    # ======================================================
    # LISTAR PRODUTOS
    # ======================================================

    @commands.hybrid_command(name="loja-produtos")
    async def loja_produtos(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        if not self.dados["produtos"]:
            return await ctx.send(
                embed=embed_padrao("📦 Nenhum produto", "Nenhum produto cadastrado ainda.", discord.Color.orange())
            )

        embed = embed_padrao("📦 Produtos da Loja", "Lista de todos os produtos cadastrados.")

        for pid, produto in self.dados["produtos"].items():

            embed.add_field(
                name=f"{produto['nome']}  •  ID `{pid}`",
                value=f"💰 R$ {produto['preco']}\n📦 Estoque: {len(produto['estoque'])}",
                inline=False
            )

        await ctx.send(embed=embed)


    # ======================================================
    # VER NOTAS / AVALIAÇÕES
    # ======================================================

    @commands.hybrid_command(name="loja-stats")
    async def loja_stats(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        aprovados = [p for p in self.dados["pedidos"].values() if p.get("status") == "aprovado"]

        faturamento = 0.0
        contagem = {}

        for pedido in aprovados:

            try:
                valor = float(str(pedido["preco"]).replace(".", "").replace(",", "."))
            except Exception:
                valor = 0.0

            faturamento += valor

            nome = pedido["produto_nome"]
            contagem[nome] = contagem.get(nome, 0) + 1

        top = sorted(contagem.items(), key=lambda x: -x[1])[:5]

        embed = embed_padrao(
            "📊 Estatísticas da Loja",
            f"💰 **Faturamento total:** R$ {faturamento:.2f}\n"
            f"🛒 **Vendas aprovadas:** {len(aprovados)}\n"
            f"📦 **Produtos cadastrados:** {len(self.dados['produtos'])}",
            discord.Color.gold()
        )

        if top:

            texto = "\n".join(
                f"{i+1}. {nome} — {qtd} venda(s)"
                for i, (nome, qtd) in enumerate(top)
            )

            embed.add_field(name="🏆 Mais vendidos", value=texto, inline=False)

        await ctx.send(embed=embed)


    @app_commands.describe(produto_id="ID do produto (deixe vazio pra ver a nota geral da loja)")
    @commands.hybrid_command(name="loja-notas")
    async def loja_notas(self, ctx, produto_id: str = None):

        avaliacoes = self.dados.get("avaliacoes", [])

        if produto_id:

            avaliacoes = [a for a in avaliacoes if a["produto_id"] == produto_id]

            produto = self.dados["produtos"].get(produto_id)

            titulo = f"⭐ Avaliações — {produto['nome']}" if produto else f"⭐ Avaliações — ID {produto_id}"

        else:

            titulo = "⭐ Avaliações Gerais da Loja"

        if not avaliacoes:
            return await ctx.send(
                embed=embed_padrao(titulo, "Ainda não há avaliações.", discord.Color.orange())
            )

        media = sum(a["nota"] for a in avaliacoes) / len(avaliacoes)

        embed = embed_padrao(
            titulo,
            f"📊 Média: **{media:.1f}/5** ⭐  •  {len(avaliacoes)} avaliação(ões)",
            discord.Color.gold()
        )

        for avaliacao in avaliacoes[-10:]:

            estrelas = "⭐" * avaliacao["nota"]

            embed.add_field(
                name=f"{estrelas}  —  {avaliacao['produto_nome']}",
                value=avaliacao["comentario"] or "_Sem comentário._",
                inline=False
            )

        if len(avaliacoes) > 10:
            embed.set_footer(text=f"Mostrando as 10 mais recentes de {len(avaliacoes)}.")

        await ctx.send(embed=embed)


    # ======================================================
    # REMOVER PRODUTO
    # ======================================================

    @app_commands.describe(produto_id="ID do produto (veja com !loja-produtos)")
    @commands.hybrid_command(name="loja-remover-produto")
    async def loja_remover_produto(self, ctx, produto_id: str):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        produto = self.dados["produtos"].pop(produto_id, None)

        if produto is None:
            return await ctx.send(
                embed=embed_padrao("❌ Produto não encontrado", f"Não existe produto com ID `{produto_id}`.", discord.Color.red())
            )

        self.salvar()

        await atualizar_todos_paineis(self)

        await ctx.send(
            embed=embed_padrao("🗑️ Produto removido", f"**{produto['nome']}** foi removido da loja.", discord.Color.orange())
        )


    # ======================================================
    # VER / REMOVER ITEM ESPECÍFICO DO ESTOQUE
    # ======================================================

    @app_commands.describe(produto_id="ID do produto")
    @commands.hybrid_command(name="loja-ver-estoque")
    async def loja_ver_estoque(self, ctx, produto_id: str):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        produto = self.dados["produtos"].get(produto_id)

        if produto is None:
            return await ctx.send(
                embed=embed_padrao("❌ Produto não encontrado", f"Não existe produto com ID `{produto_id}`.", discord.Color.red())
            )

        if not produto["estoque"]:
            return await ctx.send(
                embed=embed_padrao(f"📦 {produto['nome']}", "Estoque vazio.", discord.Color.orange())
            )

        linhas = "\n".join(
            f"`{i+1}.` {item}"
            for i, item in enumerate(produto["estoque"])
        )

        await ctx.send(
            embed=embed_padrao(
                f"📦 Estoque — {produto['nome']}",
                f"{linhas}\n\nUse `!loja-remover-estoque {produto_id} <número>` para remover um item específico.",
                discord.Color.blurple()
            )
        )


    @app_commands.describe(produto_id="ID do produto", posicao="Posição do item no estoque (veja com !loja-ver-estoque)")
    @commands.hybrid_command(name="loja-remover-estoque")
    async def loja_remover_estoque(self, ctx, produto_id: str, posicao: int):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        produto = self.dados["produtos"].get(produto_id)

        if produto is None:
            return await ctx.send(
                embed=embed_padrao("❌ Produto não encontrado", f"Não existe produto com ID `{produto_id}`.", discord.Color.red())
            )

        indice = posicao - 1

        if indice < 0 or indice >= len(produto["estoque"]):
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Posição inválida",
                    f"Use `!loja-ver-estoque {produto_id}` para ver as posições válidas.",
                    discord.Color.red()
                )
            )

        removido = produto["estoque"].pop(indice)

        self.salvar()

        await atualizar_todos_paineis(self)

        await ctx.send(
            embed=embed_padrao(
                "🗑️ Item removido do estoque",
                f"**{produto['nome']}**\n➖ Removido: `{removido}`\n📦 Estoque atual: {len(produto['estoque'])}",
                discord.Color.orange()
            )
        )


    # ======================================================
    # CONFIGURAR PIX
    # ======================================================

    @app_commands.describe(chave="Chave PIX copia-e-cola (anexe a imagem do QR code junto, só funciona via !)")
    @commands.command(name="loja-pix")
    async def loja_pix(self, ctx, *, chave: str):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        self.dados["config"]["pix_chave"] = chave.strip()

        tem_qrcode = False

        if ctx.message.attachments:

            anexo = ctx.message.attachments[0]

            try:
                await anexo.save(QRCODE_FILE)
                self.dados["config"]["pix_qrcode"] = True
                tem_qrcode = True
            except Exception as e:
                print(f"⚠️ Erro ao salvar QR code: {e}")

        self.salvar()

        texto = f"Chave PIX definida: `{chave.strip()}`"

        if tem_qrcode:
            texto += "\n✅ QR code atualizado também."
        elif self.dados["config"].get("pix_qrcode"):
            texto += "\nℹ️ QR code anterior mantido (não foi enviado um novo)."
        else:
            texto += "\n⚠️ Nenhum QR code configurado ainda — anexe uma imagem junto do comando pra adicionar."

        await ctx.send(
            embed=embed_padrao("✅ PIX configurado", texto, discord.Color.green())
        )


    # ======================================================
    # CONFIGURAR PREÇO DO ROBUX
    # ======================================================

    @app_commands.describe(
        preco_k="Valor em R$ de 1.000 Robux (ex: 5.50)",
        taxa="Taxa % da gamepass (padrão do Roblox é 30, pode deixar em branco)"
    )
    @commands.hybrid_command(name="loja-robux-preco")
    async def loja_robux_preco(self, ctx, preco_k: str, taxa: str = None):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        try:
            preco = float(preco_k.strip().replace(",", "."))
            if preco <= 0:
                raise ValueError
        except ValueError:
            return await ctx.send(
                embed=embed_padrao("❌ Valor inválido", "Use um número válido, ex: `!loja-robux-preco 5.50`", discord.Color.red())
            )

        taxa_valor = self.dados["config"].get("robux_taxa_percentual", 30)

        if taxa is not None:

            try:
                taxa_valor = float(taxa.strip().replace(",", ".").replace("%", ""))

                if not (0 <= taxa_valor < 100):
                    raise ValueError

            except ValueError:
                return await ctx.send(
                    embed=embed_padrao("❌ Taxa inválida", "Use um número entre 0 e 99, ex: `30`", discord.Color.red())
                )

        self.dados["config"]["robux_preco_k"] = preco
        self.dados["config"]["robux_taxa_percentual"] = taxa_valor

        self.salvar()

        await ctx.send(
            embed=embed_padrao(
                "✅ Robux configurado",
                f"💰 Preço por 1.000 Robux: **R$ {formatar_valor_brl(preco)}**\n🎫 Taxa da Gamepass: **{taxa_valor:.0f}%**",
                discord.Color.green()
            )
        )


    # ======================================================
    # ENVIAR PAINEL
    # ======================================================

    @commands.hybrid_command(name="loja-painel")
    async def loja_painel(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        if not self.dados["produtos"]:
            return await ctx.send(
                embed=embed_padrao("❌ Sem produtos", "Cadastre pelo menos um produto antes de enviar o painel.", discord.Color.red())
            )

        await ctx.send(
            embed=embed_padrao(
                "🛠️ Novo painel neste canal",
                "Escolha abaixo quais produtos vão aparecer **neste painel**. "
                "Você pode montar painéis diferentes com produtos diferentes em cada canal.",
                discord.Color.blurple()
            ),
            view=SelecionarProdutosPainelView(self)
        )


    @commands.hybrid_command(name="loja-robux-painel")
    async def loja_robux_painel(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        if not self.dados["config"].get("robux_preco_k"):
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Robux não configurado",
                    "Defina o preço primeiro com `!loja-robux-preco <valor>` ou pelo botão **🎮 Configurar Robux** no `!loja-admin`.",
                    discord.Color.red()
                )
            )

        await ctx.send(embed=embed_robux_painel(), view=RobuxPainelView(self))


    @commands.hybrid_command(name="loja-modelos")
    async def loja_modelos(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        modelos = self.dados["config"].get("modelos", {})

        if modelos:
            lista = "\n".join(f"• **{m['nome']}** — {len(m['produtos'])} produto(s)" for m in modelos.values())
        else:
            lista = "_Nenhum modelo salvo ainda._"

        texto = (
            "## 📁 Modelos de Painel\n"
            "Modelos salvos que você pode reenviar ou editar a qualquer momento, sem montar do zero.\n\n"
            f"**Modelos salvos**\n{lista}"
        )

        await ctx.send(view=container_view(texto, ModelosView(self)))


    # ======================================================
    # EDITAR PAINEL (título/descrição)
    # ======================================================

    @app_commands.describe(texto="Formato: Título | Descrição")
    @commands.hybrid_command(name="editar-painel")
    async def editar_painel_cmd(self, ctx, *, texto: str = None):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        if not texto or "|" not in texto:
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Formato inválido",
                    "Use assim: `!editar-painel Título | Descrição`\n\n"
                    "Ou, mais fácil: use `!loja-admin` e clique em **✏️ Editar Painel**.",
                    discord.Color.red()
                )
            )

        titulo, descricao = texto.split("|", 1)

        self.dados["config"]["painel_titulo"] = titulo.strip()
        self.dados["config"]["painel_descricao"] = descricao.strip()

        self.salvar()

        await atualizar_todos_paineis(self)

        await ctx.send(
            embed=embed_padrao(
                "✅ Painel atualizado",
                "Título e descrição salvos, e todos os painéis já enviados foram atualizados.",
                discord.Color.green()
            )
        )


    # ======================================================
    # PAINEL DE ADMINISTRAÇÃO (mais fácil que comandos)
    # ======================================================

    @commands.hybrid_command(name="loja-admin")
    async def loja_admin(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        texto = (
            "## 🛠️ Painel de Administração da Loja\n"
            "Use os botões abaixo para gerenciar a loja sem precisar decorar comandos."
        )

        await ctx.send(view=container_view(texto, PainelAdminView(self)))


# ==========================================================
# CONSTRUIR EMBED + VIEW DO PAINEL DE COMPRAS
# ==========================================================

def _preco_float(preco_str):

    try:
        return float(str(preco_str).replace(".", "").replace(",", "."))
    except Exception:
        return 0.0


def _nota_media(cog, produto_id):

    avaliacoes = [a for a in cog.dados.get("avaliacoes", []) if a["produto_id"] == produto_id]

    if not avaliacoes:
        return None

    media = sum(a["nota"] for a in avaliacoes) / len(avaliacoes)

    return media, len(avaliacoes)


def _indicador_estoque(qtd):

    if qtd >= 10:
        return "🟢"

    if qtd >= 3:
        return "🟡"

    return "🔴"


def construir_painel_loja(cog, produtos_ids=None):

    titulo = cog.dados["config"].get("painel_titulo") or "🛒 Loja"

    descricao = cog.dados["config"].get("painel_descricao") or "Escolha abaixo o produto que deseja comprar."

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    banner = cog.dados["config"].get("painel_banner")

    if banner:
        embed.set_image(url=banner)

    produtos_disponiveis = {
        pid: produto
        for pid, produto in cog.dados["produtos"].items()
        if produto["estoque"]
        and (produtos_ids is None or pid in produtos_ids)
    }

    produtos_disponiveis = dict(
        sorted(produtos_disponiveis.items(), key=lambda item: _preco_float(item[1]["preco"]))
    )

    if not produtos_disponiveis:

        embed.add_field(
            name="😕 Sem produtos disponíveis no momento",
            value="Volte mais tarde!",
            inline=False
        )

    for pid, produto in produtos_disponiveis.items():

        qtd = len(produto["estoque"])

        indicador = _indicador_estoque(qtd)

        info_nota = _nota_media(cog, pid)

        linha_nota = f"\n⭐ {info_nota[0]:.1f} ({info_nota[1]} avaliação{'ões' if info_nota[1] != 1 else ''})" if info_nota else ""

        embed.add_field(
            name=f"{produto['nome']} — R$ {produto['preco']}",
            value=f"{produto['descricao']}\n{indicador} {qtd} em estoque{linha_nota}",
            inline=False
        )

    embed.set_footer(text=f"🛒 {len(produtos_disponiveis)} produto(s) disponível(is) • Selecione no menu abaixo")

    opcoes = []

    for pid, produto in produtos_disponiveis.items():

        qtd = len(produto["estoque"])

        info_nota = _nota_media(cog, pid)

        nota_txt = f" | ⭐{info_nota[0]:.1f}" if info_nota else ""

        opcoes.append(
            discord.SelectOption(
                label=f"{_indicador_estoque(qtd)} {produto['nome']}"[:100],
                value=pid,
                description=f"R$ {produto['preco']} | Estoque: {qtd}{nota_txt}"[:100]
            )
        )

    if not opcoes:

        opcoes = [
            discord.SelectOption(
                label="Nenhum produto disponível no momento",
                value="dummy"
            )
        ]

    view = LojaPainelView(cog, opcoes)

    return embed, view


async def atualizar_todos_paineis(cog):

    paineis = cog.dados["config"].get("paineis", [])

    ainda_validos = []

    for painel in paineis:

        canal = cog.bot.get_channel(painel["canal_id"])

        if canal is None:
            continue

        embed, view = construir_painel_loja(cog, painel.get("produtos"))

        try:
            mensagem = await canal.fetch_message(painel["mensagem_id"])
            await mensagem.edit(embed=embed, view=view)
            ainda_validos.append(painel)
        except Exception:
            continue

    cog.dados["config"]["paineis"] = ainda_validos

    cog.salvar()


# ==========================================================
# PAINEL (dropdown de produtos)
# ==========================================================

class LojaSelect(Select):

    def __init__(self, cog, opcoes=None):

        self.cog = cog

        if not opcoes:
            opcoes = [discord.SelectOption(label="Carregando...", value="dummy")]

        super().__init__(
            placeholder="Escolha o produto que deseja comprar",
            options=opcoes,
            min_values=1,
            max_values=1,
            custom_id="loja_painel_select"
        )


    async def callback(self, interaction: discord.Interaction):

        produto_id = self.values[0]

        if produto_id == "dummy":
            return await interaction.response.send_message(
                "❌ Não há produtos disponíveis no momento (ou esse painel está "
                "desatualizado — peça pra equipe reenviar).",
                ephemeral=True
            )

        produto = self.cog.dados["produtos"].get(produto_id)

        if produto is None or not produto["estoque"]:
            return await interaction.response.send_message(
                "❌ Esse produto está esgotado ou não existe mais. Atualize o painel e tente outro.",
                ephemeral=True
            )

        # Abre o carrinho: primeiro pede o nick do Roblox antes de gerar o pagamento.
        await interaction.response.send_modal(ModalCarrinho(self.cog, produto_id))


class LojaPainelView(View):

    def __init__(self, cog, opcoes=None):

        super().__init__(timeout=None)

        self.add_item(LojaSelect(cog, opcoes))


# ==========================================================
# CARRINHO (nick do Roblox + resumo do pedido antes de pagar)
# ==========================================================

class ModalCarrinho(Modal):
    """Primeiro passo do carrinho: pede o nick do Roblox pra vincular à conta comprada."""

    def __init__(self, cog, produto_id):

        super().__init__(title="🛒 Finalizar Pedido")

        self.cog = cog
        self.produto_id = produto_id

        self.nick_roblox = TextInput(
            label="Seu nick no Roblox",
            placeholder="Ex: JoaoBuilder123",
            min_length=3,
            max_length=20
        )

        self.add_item(self.nick_roblox)


    async def on_submit(self, interaction: discord.Interaction):

        produto = self.cog.dados["produtos"].get(self.produto_id)

        if produto is None or not produto["estoque"]:
            return await interaction.response.send_message(
                "❌ Esse produto ficou indisponível enquanto você preenchia o formulário. Tente outro.",
                ephemeral=True
            )

        nick = self.nick_roblox.value.strip()

        erro = _validar_nick_roblox(nick)

        if erro:
            return await interaction.response.send_message(f"❌ {erro}", ephemeral=True)

        embed = discord.Embed(
            title="🛒 Resumo do seu Carrinho",
            description="Confira os dados abaixo antes de seguir para o pagamento.",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="🎁 Produto", value=produto["nome"], inline=True)
        embed.add_field(name="💰 Valor", value=f"R$ {produto['preco']}", inline=True)
        embed.add_field(name="🧍 Nick no Roblox", value=f"`{nick}`", inline=False)
        embed.set_footer(text="Verifique se o nick está certo — é ele que vai ser vinculado à conta entregue.")

        if interaction.user.display_avatar:
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.send_message(
            embed=embed,
            view=ConfirmarCarrinhoView(self.cog, self.produto_id, nick),
            ephemeral=True
        )


class ConfirmarCarrinhoView(View):
    """Segundo passo do carrinho: confirmar ou cancelar antes de gerar o PIX."""

    def __init__(self, cog, produto_id, nick_roblox):

        super().__init__(timeout=120)

        self.cog = cog
        self.produto_id = produto_id
        self.nick_roblox = nick_roblox


    @discord.ui.button(label="✅ Confirmar e Pagar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: Button):

        await iniciar_compra(self.cog, interaction, self.produto_id, nick_roblox=self.nick_roblox)


    @discord.ui.button(label="✏️ Corrigir Nick", style=discord.ButtonStyle.secondary)
    async def corrigir(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(ModalCarrinho(self.cog, self.produto_id))


    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.edit_message(
            content="❌ Pedido cancelado. Você pode iniciar um novo quando quiser, no menu do painel.",
            embed=None,
            view=None
        )


# ==========================================================
# INICIAR COMPRA
# ==========================================================

async def iniciar_compra(cog, interaction: discord.Interaction, produto_id, nick_roblox=None):

    produto = cog.dados["produtos"].get(produto_id)

    if produto is None:
        return await interaction.response.send_message(
            "❌ Esse produto não existe mais.",
            ephemeral=True
        )

    if not produto["estoque"]:
        return await interaction.response.send_message(
            f"❌ **{produto['nome']}** está esgotado no momento.",
            ephemeral=True
        )

    pix_chave = cog.dados["config"].get("pix_chave")

    if not pix_chave:
        return await interaction.response.send_message(
            "❌ O pagamento ainda não foi configurado pela equipe. Tente novamente mais tarde.",
            ephemeral=True
        )

    pedido_id = str(random.randint(100000, 999999))

    while pedido_id in cog.dados["pedidos"]:
        pedido_id = str(random.randint(100000, 999999))

    cog.dados["pedidos"][pedido_id] = {
        "produto_id": produto_id,
        "produto_nome": produto["nome"],
        "preco": produto["preco"],
        "comprador_id": interaction.user.id,
        "nick_roblox": nick_roblox,
        "status": "aguardando_pagamento",
        "criado_em": time.time(),
        "guild_id": interaction.guild.id if interaction.guild else None,
        "avaliado": False
    }

    cog.salvar()

    descricao = (
        f"💰 **Valor:** R$ {produto['preco']}\n"
    )

    if nick_roblox:
        descricao += f"🧍 **Nick Roblox:** `{nick_roblox}`\n"

    descricao += (
        f"\n**Chave PIX (copia e cola):**\n```{pix_chave}```\n"
        "Depois de pagar, clique no botão **✅ Já paguei** abaixo.\n"
        "Sua conta será enviada aqui no privado assim que o pagamento for aprovado."
    )

    embed = discord.Embed(
        title=f"🛒 Pedido #{pedido_id} — {produto['nome']}",
        description=descricao,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="Pagamento seguro via PIX • Sistema de Loja")

    view = PagamentoView(pedido_id)

    arquivo = None

    if cog.dados["config"].get("pix_qrcode") and os.path.exists(QRCODE_FILE):

        arquivo = discord.File(QRCODE_FILE, filename="qrcode.png")

        embed.set_image(url="attachment://qrcode.png")

    if arquivo:
        await interaction.response.send_message(embed=embed, view=view, file=arquivo, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================================
# SISTEMA DE LOJA DE ROBUX
# ==========================================================

class ModalConfigRobux(Modal, title="🎮 Configurar Robux"):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog

        preco_atual = cog.dados["config"].get("robux_preco_k")
        taxa_atual = cog.dados["config"].get("robux_taxa_percentual", 30)

        self.preco_k = TextInput(
            label="Preço de 1.000 Robux (R$)",
            placeholder="Ex: 5.50",
            default=f"{preco_atual}" if preco_atual else None,
            max_length=10
        )

        self.taxa = TextInput(
            label="Taxa da Gamepass (%) — padrão: 30",
            placeholder="Ex: 30",
            default=f"{taxa_atual}",
            required=False,
            max_length=5
        )

        self.add_item(self.preco_k)
        self.add_item(self.taxa)


    async def on_submit(self, interaction: discord.Interaction):

        try:
            preco = float(self.preco_k.value.strip().replace(",", "."))

            if preco <= 0:
                raise ValueError

        except ValueError:
            return await interaction.response.send_message(
                "❌ Digite um preço válido para 1.000 Robux (ex: `5.50`).",
                ephemeral=True
            )

        taxa_valor = self.cog.dados["config"].get("robux_taxa_percentual", 30)
        taxa_bruta = (self.taxa.value or "").strip().replace(",", ".").replace("%", "")

        if taxa_bruta:

            try:
                taxa_valor = float(taxa_bruta)

                if not (0 <= taxa_valor < 100):
                    raise ValueError

            except ValueError:
                return await interaction.response.send_message(
                    "❌ Digite uma taxa válida entre 0 e 99 (ex: `30`).",
                    ephemeral=True
                )

        self.cog.dados["config"]["robux_preco_k"] = preco
        self.cog.dados["config"]["robux_taxa_percentual"] = taxa_valor

        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao(
                "✅ Robux configurado",
                (
                    f"💰 **Preço por 1.000 Robux:** R$ {formatar_valor_brl(preco)}\n"
                    f"🎫 **Taxa da Gamepass:** {taxa_valor:.0f}%\n\n"
                    "Use o botão **📤 Enviar Painel Robux Aqui** para publicar o painel de compra."
                ),
                discord.Color.green()
            ),
            ephemeral=True
        )


class RobuxPainelView(View):
    """View persistente com o botão público de compra de Robux."""

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog


    @discord.ui.button(label="🎮 Comprar Robux", style=discord.ButtonStyle.success, custom_id="loja_robux_comprar")
    async def comprar(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["config"].get("robux_preco_k"):
            return await interaction.response.send_message(
                "❌ A compra de Robux ainda não foi configurada pela equipe. Tente novamente mais tarde.",
                ephemeral=True
            )

        await interaction.response.send_modal(ModalRobuxPedido(self.cog))


class ModalRobuxPedido(Modal, title="🎮 Comprar Robux"):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog

        self.nick_roblox = TextInput(
            label="Nick do Roblox",
            placeholder="Nick de CRIAÇÃO da conta — não é o nick de exibição!",
            max_length=20
        )

        self.quantidade = TextInput(
            label="Quantidade de Robux",
            placeholder="Ex: 500",
            max_length=10
        )

        self.add_item(self.nick_roblox)
        self.add_item(self.quantidade)


    async def on_submit(self, interaction: discord.Interaction):

        nick = self.nick_roblox.value.strip()

        erro_nick = _validar_nick_roblox(nick)

        if erro_nick:
            return await interaction.response.send_message(f"❌ {erro_nick}", ephemeral=True)

        qtd_bruta = self.quantidade.value.strip().replace(".", "").replace(",", "")

        if not qtd_bruta.isdigit() or int(qtd_bruta) <= 0:
            return await interaction.response.send_message(
                "❌ Digite uma quantidade de Robux válida (só números, maior que zero).",
                ephemeral=True
            )

        quantidade = int(qtd_bruta)

        if quantidade > 1_000_000:
            return await interaction.response.send_message(
                "❌ Quantidade muito alta. Entre em contato com a equipe para pedidos grandes assim.",
                ephemeral=True
            )

        valor_reais, _ = calcular_valores_robux(self.cog, quantidade, com_taxa=False)

        if valor_reais is None:
            return await interaction.response.send_message(
                "❌ O preço do Robux ainda não foi configurado pela equipe. Tente novamente mais tarde.",
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=embed_padrao(
                "💳 Como vai ser a entrega?",
                (
                    f"🧍 **Nick:** `{nick}`\n"
                    f"🔢 **Quantidade:** `{quantidade}` Robux\n\n"
                    "**💸 Com taxa (Gamepass)** — você recebe via Gamepass. O Roblox desconta "
                    "uma taxa, então a gamepass é criada com um valor um pouco maior que a "
                    "quantidade de Robux que você recebe.\n\n"
                    "**🎁 Sem taxa (Grupo/Trade)** — a entrega é feita sem essa taxa extra, "
                    "e o valor combinado é o mesmo da quantidade de Robux pedida."
                ),
                discord.Color.blurple()
            ),
            view=EscolherTaxaView(self.cog, nick, quantidade),
            ephemeral=True
        )


class EscolherTaxaView(View):

    def __init__(self, cog, nick, quantidade):

        super().__init__(timeout=180)

        self.cog = cog
        self.nick = nick
        self.quantidade = quantidade


    @discord.ui.button(label="💸 Com taxa (Gamepass)", style=discord.ButtonStyle.primary)
    async def com_taxa(self, interaction: discord.Interaction, button: Button):

        await iniciar_compra_robux(self.cog, interaction, self.nick, self.quantidade, com_taxa=True)


    @discord.ui.button(label="🎁 Sem taxa (Grupo/Trade)", style=discord.ButtonStyle.secondary)
    async def sem_taxa(self, interaction: discord.Interaction, button: Button):

        await iniciar_compra_robux(self.cog, interaction, self.nick, self.quantidade, com_taxa=False)


async def iniciar_compra_robux(cog, interaction: discord.Interaction, nick, quantidade, com_taxa):

    pix_chave = cog.dados["config"].get("pix_chave")

    if not pix_chave:
        return await interaction.response.send_message(
            "❌ O pagamento ainda não foi configurado pela equipe. Tente novamente mais tarde.",
            ephemeral=True
        )

    valor_reais, valor_gamepass = calcular_valores_robux(cog, quantidade, com_taxa)

    if valor_reais is None:
        return await interaction.response.send_message(
            "❌ O preço do Robux ainda não foi configurado pela equipe. Tente novamente mais tarde.",
            ephemeral=True
        )

    pedido_id = str(random.randint(100000, 999999))

    while pedido_id in cog.dados["pedidos"]:
        pedido_id = str(random.randint(100000, 999999))

    cog.dados["pedidos"][pedido_id] = {
        "tipo": "robux",
        "produto_nome": f"{quantidade} Robux",
        "preco": formatar_valor_brl(valor_reais),
        "comprador_id": interaction.user.id,
        "nick_roblox": nick,
        "quantidade_robux": quantidade,
        "com_taxa": com_taxa,
        "valor_gamepass": valor_gamepass,
        "status": "aguardando_pagamento",
        "criado_em": time.time(),
        "guild_id": interaction.guild.id if interaction.guild else None,
        "avaliado": False
    }

    cog.salvar()

    tipo_label = "💸 Com taxa (Gamepass)" if com_taxa else "🎁 Sem taxa (Grupo/Trade)"

    descricao = (
        f"🧍 **Nick Roblox:** `{nick}`\n"
        f"🔢 **Quantidade:** `{quantidade}` Robux\n"
        f"📦 **Entrega:** {tipo_label}\n"
        f"🎫 **Valor da Gamepass a criar:** `{valor_gamepass}` Robux\n"
        f"💰 **Valor a pagar:** R$ {formatar_valor_brl(valor_reais)}\n\n"
    )

    if com_taxa:
        descricao += (
            f"⚠️ Crie uma **Gamepass** no valor de `{valor_gamepass}` Robux e tenha o link "
            "em mãos — a equipe pode pedir depois de aprovar o pagamento.\n\n"
        )

    descricao += (
        f"**Chave PIX (copia e cola):**\n```{pix_chave}```\n"
        "Depois de pagar, clique no botão **✅ Já paguei** abaixo.\n"
        "A confirmação será enviada aqui no privado assim que o pagamento for aprovado."
    )

    embed = discord.Embed(
        title=f"🎮 Pedido #{pedido_id} — {quantidade} Robux",
        description=descricao,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="Pagamento seguro via PIX • Sistema de Loja Robux")

    view = PagamentoView(pedido_id)

    arquivo = None

    if cog.dados["config"].get("pix_qrcode") and os.path.exists(QRCODE_FILE):

        arquivo = discord.File(QRCODE_FILE, filename="qrcode.png")

        embed.set_image(url="attachment://qrcode.png")

    if arquivo:
        await interaction.response.send_message(embed=embed, view=view, file=arquivo, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================================
# BOTÃO "JÁ PAGUEI"
# ==========================================================

class PagamentoView(View):

    def __init__(self, pedido_id):

        super().__init__(timeout=None)

        self.pedido_id = pedido_id

        self.ja_pagamento.custom_id = f"loja_pagou_{pedido_id}"


    @discord.ui.button(label="✅ Já paguei", style=discord.ButtonStyle.success)
    async def ja_pagamento(self, interaction: discord.Interaction, button: Button):

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        if pedido["comprador_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Esse pedido não é seu.", ephemeral=True)

        if pedido["status"] != "aguardando_pagamento":
            return await interaction.response.send_message("⚠️ Esse pedido já foi processado.", ephemeral=True)

        pedido["status"] = "aguardando_aprovacao"
        cog.salvar()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="⏳ Aguardando aprovação",
                description=(
                    f"Recebemos sua confirmação de pagamento de **{pedido['produto_nome']}**.\n"
                    "Assim que a equipe aprovar, você recebe os dados aqui no privado."
                ),
                color=discord.Color.orange()
            ),
            view=None,
            attachments=[]
        )

        donos_ids = await obter_donos_para_notificar(
            interaction.client,
            pedido.get("guild_id")
        )

        if not donos_ids:
            return

        descricao_aviso = (
            f"👤 **Comprador:** <@{interaction.user.id}> (`{interaction.user.id}`)\n"
            f"🎁 **Produto:** {pedido['produto_nome']}\n"
            f"💰 **Valor:** R$ {pedido['preco']}\n"
        )

        if pedido.get("nick_roblox"):
            descricao_aviso += f"🧍 **Nick Roblox:** `{pedido['nick_roblox']}`\n"

        descricao_aviso += f"🆔 **Pedido:** `{self.pedido_id}`"

        aviso = discord.Embed(
            title="🛒 Novo pedido aguardando aprovação",
            description=descricao_aviso,
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )

        for dono_id in donos_ids:

            try:
                dono = await interaction.client.fetch_user(dono_id)
                await dono.send(embed=aviso, view=AprovarView(self.pedido_id))
            except Exception as e:
                print(f"⚠️ Não consegui avisar o dono {dono_id}: {e}")


# ==========================================================
# BOTÕES DE APROVAÇÃO (DM do dono)
# ==========================================================

class AprovarView(View):

    def __init__(self, pedido_id):

        super().__init__(timeout=None)

        self.pedido_id = pedido_id

        self.aprovar.custom_id = f"loja_aprovar_{pedido_id}"
        self.recusar.custom_id = f"loja_recusar_{pedido_id}"


    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success)
    async def aprovar(self, interaction: discord.Interaction, button: Button):

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        autorizado = await pode_aprovar(
            interaction.client,
            interaction.user.id,
            pedido.get("guild_id")
        )

        if not autorizado:
            return await interaction.response.send_message(
                f"🚫 Você precisa ter o cargo **{CARGO_APROVADOR}** para aprovar isso.",
                ephemeral=True
            )

        if pedido["status"] != "aguardando_aprovacao":
            return await interaction.response.edit_message(
                content=f"⚠️ Esse pedido já foi processado (status atual: `{pedido['status']}`).",
                embed=None,
                view=None
            )

        if pedido.get("tipo") == "robux":
            return await self._aprovar_robux(interaction, cog, pedido)

        produto = cog.dados["produtos"].get(pedido["produto_id"])

        if produto is None or not produto["estoque"]:

            return await interaction.response.send_message(
                "❌ Esse produto está sem estoque! Adicione mais e clique em Aprovar de novo.",
                ephemeral=True
            )

        credencial = produto["estoque"][0]

        comprador_id = pedido["comprador_id"]

        entregue = False

        try:
            comprador = await interaction.client.fetch_user(comprador_id)

            descricao_entrega = f"🎁 **Produto:** {pedido['produto_nome']}\n"

            if pedido.get("nick_roblox"):
                descricao_entrega += f"🧍 **Vinculado ao nick:** `{pedido['nick_roblox']}`\n"

            descricao_entrega += (
                f"\n**Dados de acesso:**\n```{credencial}```\n"
                "Obrigado pela compra! 🎉"
            )

            await comprador.send(
                embed=discord.Embed(
                    title="✅ Pagamento aprovado!",
                    description=descricao_entrega,
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
            )

            entregue = True

        except Exception as e:
            print(f"⚠️ Não consegui entregar a conta pro comprador {comprador_id}: {e}")


        if not entregue:

            return await interaction.response.send_message(
                "⚠️ Não consegui mandar DM pro comprador (provavelmente ele tem DM de "
                "membros do servidor desativada). **O estoque não foi alterado.** "
                "Peça pra ele liberar as DMs e clique em Aprovar de novo, ou entregue "
                f"manualmente:\n```{credencial}```",
                ephemeral=True
            )


        # só remove do estoque depois de confirmar que a entrega deu certo
        produto["estoque"].pop(0)

        pedido["status"] = "aprovado"

        cog.salvar()

        await atualizar_todos_paineis(cog)

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Pedido aprovado",
                description=f"Produto **{pedido['produto_nome']}** entregue via DM com sucesso.",
                color=discord.Color.green()
            ),
            view=None
        )

        guild = interaction.client.get_guild(pedido.get("guild_id"))

        texto_log = f"✅ Pedido `{self.pedido_id}` aprovado — **{pedido['produto_nome']}** entregue para <@{comprador_id}>."

        if pedido.get("nick_roblox"):
            texto_log += f" (nick Roblox: `{pedido['nick_roblox']}`)"

        await enviar_log(
            interaction.client,
            guild,
            texto_log,
            discord.Color.green()
        )

        conquistas = interaction.client.get_cog("Conquistas")

        if conquistas and guild:

            try:
                membro_comprador = guild.get_member(comprador_id)

                if membro_comprador:
                    await conquistas.desbloquear(membro_comprador, "primeira_compra", canal_para_avisar=interaction.channel)
            except Exception:
                pass

        cargo_cliente_id = cog.dados["config"].get("cargo_cliente")

        if cargo_cliente_id and guild:

            cargo_cliente = guild.get_role(cargo_cliente_id)

            if cargo_cliente:

                try:
                    membro_comprador = guild.get_member(comprador_id) or await guild.fetch_member(comprador_id)
                    await membro_comprador.add_roles(cargo_cliente, reason="Compra aprovada na loja")
                except Exception as e:
                    print(f"⚠️ Não consegui dar o cargo de cliente pra {comprador_id}: {e}")

        try:

            await comprador.send(
                embed=discord.Embed(
                    title="⭐ Que tal avaliar sua compra?",
                    description=(
                        f"Deixe sua nota e comentário sobre **{pedido['produto_nome']}**. "
                        "Isso ajuda muito a equipe e outros clientes!"
                    ),
                    color=discord.Color.gold()
                ),
                view=AvaliarView(self.pedido_id)
            )

        except Exception:
            pass


    async def _aprovar_robux(self, interaction: discord.Interaction, cog, pedido):
        """Aprovação de pedidos de Robux (sem estoque/credencial, entrega manual pela equipe)."""

        comprador_id = pedido["comprador_id"]

        descricao_entrega = (
            f"🧍 **Nick:** `{pedido['nick_roblox']}`\n"
            f"🔢 **Quantidade:** `{pedido['quantidade_robux']}` Robux\n"
        )

        if pedido.get("com_taxa"):
            descricao_entrega += f"🎫 **Gamepass:** `{pedido['valor_gamepass']}` Robux\n"

        descricao_entrega += "\nSeu pagamento foi aprovado! Os Robux serão enviados em breve. 🎉"

        entregue = False

        try:
            comprador = await interaction.client.fetch_user(comprador_id)

            await comprador.send(
                embed=discord.Embed(
                    title="✅ Pagamento aprovado!",
                    description=descricao_entrega,
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
            )

            entregue = True

        except Exception as e:
            print(f"⚠️ Não consegui avisar o comprador {comprador_id}: {e}")

        if not entregue:
            return await interaction.response.send_message(
                "⚠️ Não consegui mandar DM pro comprador (provavelmente ele tem DM de "
                "membros do servidor desativada). Avise-o manualmente e depois faça a entrega.",
                ephemeral=True
            )

        pedido["status"] = "aprovado"
        cog.salvar()

        instrucao_entrega = (
            f"via Gamepass de `{pedido['valor_gamepass']}` Robux."
            if pedido.get("com_taxa")
            else "via grupo/trade, sem taxa adicional."
        )

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Pedido de Robux aprovado",
                description=(
                    "Comprador avisado com sucesso.\n\n"
                    f"🧍 **Nick:** `{pedido['nick_roblox']}`\n"
                    f"🔢 **Enviar:** `{pedido['quantidade_robux']}` Robux — {instrucao_entrega}"
                ),
                color=discord.Color.green()
            ),
            view=None
        )

        guild = interaction.client.get_guild(pedido.get("guild_id"))

        await enviar_log(
            interaction.client,
            guild,
            (
                f"✅ Pedido `{self.pedido_id}` (Robux) aprovado — `{pedido['quantidade_robux']}` "
                f"Robux para o nick `{pedido['nick_roblox']}` (<@{comprador_id}>)."
            ),
            discord.Color.green()
        )

        conquistas = interaction.client.get_cog("Conquistas")

        if conquistas and guild:

            try:
                membro_comprador = guild.get_member(comprador_id)

                if membro_comprador:
                    await conquistas.desbloquear(membro_comprador, "primeira_compra", canal_para_avisar=interaction.channel)
            except Exception:
                pass

        cargo_cliente_id = cog.dados["config"].get("cargo_cliente")

        if cargo_cliente_id and guild:

            cargo_cliente = guild.get_role(cargo_cliente_id)

            if cargo_cliente:

                try:
                    membro_comprador = guild.get_member(comprador_id) or await guild.fetch_member(comprador_id)
                    await membro_comprador.add_roles(cargo_cliente, reason="Compra de Robux aprovada na loja")
                except Exception as e:
                    print(f"⚠️ Não consegui dar o cargo de cliente pra {comprador_id}: {e}")

        try:

            await comprador.send(
                embed=discord.Embed(
                    title="⭐ Que tal avaliar sua compra?",
                    description=(
                        f"Deixe sua nota e comentário sobre sua compra de **{pedido['quantidade_robux']} Robux**. "
                        "Isso ajuda muito a equipe e outros clientes!"
                    ),
                    color=discord.Color.gold()
                ),
                view=AvaliarView(self.pedido_id)
            )

        except Exception:
            pass


    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: Button):

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        autorizado = await pode_aprovar(
            interaction.client,
            interaction.user.id,
            pedido.get("guild_id")
        )

        if not autorizado:
            return await interaction.response.send_message(
                f"🚫 Você precisa ter o cargo **{CARGO_APROVADOR}** para recusar isso.",
                ephemeral=True
            )

        if pedido["status"] != "aguardando_aprovacao":
            return await interaction.response.edit_message(
                content=f"⚠️ Esse pedido já foi processado (status atual: `{pedido['status']}`).",
                embed=None,
                view=None
            )

        pedido["status"] = "recusado"
        cog.salvar()

        comprador_id = pedido["comprador_id"]

        try:
            comprador = await interaction.client.fetch_user(comprador_id)

            await comprador.send(
                embed=discord.Embed(
                    title="❌ Pagamento não confirmado",
                    description=(
                        f"Não conseguimos confirmar o pagamento do pedido de "
                        f"**{pedido['produto_nome']}**. Entre em contato com a equipe."
                    ),
                    color=discord.Color.red()
                )
            )

        except Exception:
            pass

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ Pedido recusado",
                description=f"Pedido `{self.pedido_id}` marcado como recusado.",
                color=discord.Color.red()
            ),
            view=None
        )



# ==========================================================
# SISTEMA DE AVALIAÇÕES
# ==========================================================

CANAL_AVALIACOES_NOMES = ["avaliações", "avaliacoes", "⭐・avaliações", "⭐・avaliacoes"]


async def postar_avaliacao(bot, guild_id, avaliacao):

    if guild_id is None:
        return

    guild = bot.get_guild(guild_id)

    if guild is None:
        return

    canal = None

    for nome in CANAL_AVALIACOES_NOMES:

        canal = discord.utils.get(guild.text_channels, name=nome)

        if canal:
            break

    if canal is None:
        return

    estrelas = "⭐" * avaliacao["nota"] + "☆" * (5 - avaliacao["nota"])

    embed = discord.Embed(
        title=f"{estrelas}",
        description=(
            f"🎁 **Produto:** {avaliacao['produto_nome']}\n"
            f"👤 **Cliente:** <@{avaliacao['comprador_id']}>\n\n"
            f"💬 {avaliacao['comentario'] or '_Sem comentário._'}"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    try:
        await canal.send(embed=embed)
    except Exception:
        pass


class ModalAvaliacao(Modal):

    def __init__(self, pedido_id):

        super().__init__(title="⭐ Avaliar Compra")

        self.pedido_id = pedido_id

        self.nota = TextInput(
            label="Nota (1 a 5)",
            placeholder="Ex: 5",
            max_length=1
        )

        self.comentario = TextInput(
            label="Comentário (opcional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )

        self.add_item(self.nota)
        self.add_item(self.comentario)


    async def on_submit(self, interaction: discord.Interaction):

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        if pedido.get("avaliado"):
            return await interaction.response.send_message("⚠️ Você já avaliou essa compra.", ephemeral=True)

        try:
            nota = int(self.nota.value.strip())
            if nota < 1 or nota > 5:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ A nota precisa ser um número de 1 a 5.",
                ephemeral=True
            )

        avaliacao = {
            "pedido_id": self.pedido_id,
            "produto_id": pedido.get("produto_id"),
            "produto_nome": pedido["produto_nome"],
            "comprador_id": pedido["comprador_id"],
            "nota": nota,
            "comentario": self.comentario.value.strip(),
            "criado_em": time.time()
        }

        cog.dados["avaliacoes"].append(avaliacao)
        pedido["avaliado"] = True
        cog.salvar()

        await postar_avaliacao(interaction.client, pedido.get("guild_id"), avaliacao)

        await interaction.response.send_message(
            "✅ Obrigado pela avaliação!",
            ephemeral=True
        )

        conquistas = interaction.client.get_cog("Conquistas")

        if conquistas is not None:

            try:
                await conquistas.desbloquear(interaction.user, "avaliador", canal_para_avisar=None)
            except Exception:
                pass


class AvaliarView(View):

    def __init__(self, pedido_id):

        super().__init__(timeout=None)

        self.pedido_id = pedido_id

        self.avaliar.custom_id = f"loja_avaliar_{pedido_id}"


    @discord.ui.button(label="⭐ Avaliar compra", style=discord.ButtonStyle.primary)
    async def avaliar(self, interaction: discord.Interaction, button: Button):

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        if pedido["comprador_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Esse pedido não é seu.", ephemeral=True)

        if pedido.get("avaliado"):
            return await interaction.response.send_message("⚠️ Você já avaliou essa compra.", ephemeral=True)

        await interaction.response.send_modal(ModalAvaliacao(self.pedido_id))



# ==========================================================
# PAINEL DE ADMINISTRAÇÃO (botões + formulários)
# ==========================================================

class ModalNovoProduto(Modal):

    def __init__(self, cog):

        super().__init__(title="➕ Novo Produto")

        self.cog = cog

        self.nome = TextInput(
            label="Nome do produto",
            placeholder="Ex: Blox Fruits com Dragon",
            max_length=100
        )

        self.preco = TextInput(
            label="Preço (R$)",
            placeholder="Ex: 25,00",
            max_length=20
        )

        self.estoque_inicial = TextInput(
            label="Estoque inicial (opcional, 1 por linha)",
            style=discord.TextStyle.paragraph,
            placeholder="usuario1:senha1\nusuario2:senha2",
            required=False,
            max_length=1000
        )

        self.descricao = TextInput(
            label="Descrição (opcional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300
        )

        self.add_item(self.nome)
        self.add_item(self.preco)
        self.add_item(self.estoque_inicial)
        self.add_item(self.descricao)


    async def on_submit(self, interaction: discord.Interaction):

        produto_id = str(random.randint(1000, 9999))

        while produto_id in self.cog.dados["produtos"]:
            produto_id = str(random.randint(1000, 9999))

        linhas = [
            linha.strip()
            for linha in self.estoque_inicial.value.splitlines()
            if linha.strip()
        ] if self.estoque_inicial.value else []

        self.cog.dados["produtos"][produto_id] = {
            "nome": self.nome.value,
            "preco": self.preco.value,
            "descricao": self.descricao.value or "Sem descrição.",
            "estoque": linhas
        }

        self.cog.salvar()

        await atualizar_todos_paineis(self.cog)

        await interaction.response.send_message(
            embed=embed_padrao(
                "✅ Produto criado",
                f"**{self.nome.value}** — R$ {self.preco.value}\n"
                f"🆔 ID: `{produto_id}`\n"
                f"📦 Estoque: {len(linhas)}"
                + ("" if linhas else "\n\nUse **📦 Adicionar Estoque** pra colocar contas nele."),
                discord.Color.green()
            ),
            ephemeral=True
        )


class SelecionarProdutoEstoqueSelect(Select):

    def __init__(self, cog):

        self.cog = cog

        opcoes = [
            discord.SelectOption(
                label=produto["nome"][:100],
                value=pid,
                description=f"Estoque atual: {len(produto['estoque'])}"
            )
            for pid, produto in cog.dados["produtos"].items()
        ][:25]

        super().__init__(
            placeholder="Escolha o produto",
            options=opcoes
        )


    async def callback(self, interaction: discord.Interaction):

        await interaction.response.send_modal(
            ModalAddEstoque(self.cog, self.values[0])
        )


class SelecionarProdutoEstoqueView(View):

    def __init__(self, cog):

        super().__init__(timeout=120)

        self.add_item(SelecionarProdutoEstoqueSelect(cog))


class ModalAddEstoque(Modal):

    def __init__(self, cog, produto_id):

        super().__init__(title="📦 Adicionar Estoque")

        self.cog = cog

        self.produto_id = produto_id

        self.credenciais = TextInput(
            label="Credenciais (uma por linha)",
            style=discord.TextStyle.paragraph,
            placeholder="usuario1:senha1\nusuario2:senha2\nusuario3:senha3",
            max_length=4000
        )

        self.add_item(self.credenciais)


    async def on_submit(self, interaction: discord.Interaction):

        produto = self.cog.dados["produtos"].get(self.produto_id)

        if produto is None:
            return await interaction.response.send_message(
                "❌ Esse produto não existe mais.",
                ephemeral=True
            )

        linhas = [
            linha.strip()
            for linha in self.credenciais.value.splitlines()
            if linha.strip()
        ]

        produto["estoque"].extend(linhas)

        self.cog.salvar()

        await atualizar_todos_paineis(self.cog)

        await interaction.response.send_message(
            embed=embed_padrao(
                "✅ Estoque atualizado",
                f"**{produto['nome']}**\n"
                f"➕ {len(linhas)} adicionada(s)\n"
                f"📦 Estoque atual: {len(produto['estoque'])}",
                discord.Color.green()
            ),
            ephemeral=True
        )


class ModalPix(Modal):

    def __init__(self, cog):

        super().__init__(title="💰 Configurar PIX")

        self.cog = cog

        chave_atual = cog.dados["config"].get("pix_chave", "")

        self.chave = TextInput(
            label="Chave PIX (copia e cola)",
            style=discord.TextStyle.paragraph,
            default=chave_atual or None,
            max_length=500
        )

        self.add_item(self.chave)


    async def on_submit(self, interaction: discord.Interaction):

        self.cog.dados["config"]["pix_chave"] = self.chave.value.strip()

        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao(
                "✅ Chave PIX salva",
                "Se quiser atualizar o QR code também, **envie a imagem aqui no "
                "chat nos próximos 60 segundos**. Se não mandar nada, o QR code "
                "atual (se já tiver um) continua valendo.",
                discord.Color.green()
            ),
            ephemeral=True
        )

        def checar(m):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
                and len(m.attachments) > 0
            )

        try:

            mensagem = await interaction.client.wait_for(
                "message",
                check=checar,
                timeout=60
            )

            await mensagem.attachments[0].save(QRCODE_FILE)

            self.cog.dados["config"]["pix_qrcode"] = True

            self.cog.salvar()

            await interaction.followup.send(
                "✅ QR code atualizado também!",
                ephemeral=True
            )

        except asyncio.TimeoutError:

            pass


class ModalEditarPainel(Modal):

    def __init__(self, cog):

        super().__init__(title="✏️ Editar Painel da Loja")

        self.cog = cog

        titulo_atual = cog.dados["config"].get("painel_titulo", "🛒 Loja")
        descricao_atual = cog.dados["config"].get("painel_descricao", "Escolha abaixo o produto que deseja comprar.")

        self.titulo = TextInput(
            label="Título do painel",
            default=titulo_atual,
            max_length=256
        )

        self.descricao = TextInput(
            label="Descrição do painel",
            style=discord.TextStyle.paragraph,
            default=descricao_atual,
            max_length=1000
        )

        self.add_item(self.titulo)
        self.add_item(self.descricao)


    async def on_submit(self, interaction: discord.Interaction):

        self.cog.dados["config"]["painel_titulo"] = self.titulo.value
        self.cog.dados["config"]["painel_descricao"] = self.descricao.value

        self.cog.salvar()

        await atualizar_todos_paineis(self.cog)

        await interaction.response.send_message(
            embed=embed_padrao(
                "✅ Painel atualizado",
                "O título e a descrição foram salvos, e todos os painéis já "
                "enviados foram atualizados automaticamente.",
                discord.Color.green()
            ),
            ephemeral=True
        )


class SelecionarProdutosPainelSelect(Select):

    def __init__(self, cog):

        self.cog = cog

        opcoes = [
            discord.SelectOption(
                label=produto["nome"][:100],
                value=pid,
                description=f"R$ {produto['preco']} | Estoque: {len(produto['estoque'])}"[:100]
            )
            for pid, produto in list(cog.dados["produtos"].items())[:25]
        ]

        super().__init__(
            placeholder="Escolha os produtos deste painel",
            options=opcoes,
            min_values=1,
            max_values=len(opcoes)
        )


    async def callback(self, interaction: discord.Interaction):

        produtos_ids = self.values

        embed, view = construir_painel_loja(self.cog, produtos_ids)

        mensagem = await interaction.channel.send(embed=embed, view=view)

        self.cog.dados["config"].setdefault("paineis", []).append(
            {"canal_id": mensagem.channel.id, "mensagem_id": mensagem.id, "produtos": produtos_ids}
        )

        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"✅ Painel criado com {len(produtos_ids)} produto(s)! Ele se atualiza sozinho.",
            embed=None,
            view=None
        )


class SelecionarProdutosPainelView(View):

    def __init__(self, cog):

        super().__init__(timeout=180)

        self.add_item(SelecionarProdutosPainelSelect(cog))


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO SelecionarProdutosPainelView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=============================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


class SelecionarCargoCliente(RoleSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(placeholder="Escolha o cargo de cliente")


    async def callback(self, interaction: discord.Interaction):

        cargo = self.values[0]

        if cargo.managed:
            return await interaction.response.send_message(
                "❌ Esse cargo é gerenciado automaticamente (bot/integração/boost) e não pode ser usado.",
                ephemeral=True
            )

        self.cog.dados["config"]["cargo_cliente"] = cargo.id
        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"✅ Cargo de cliente definido: {cargo.mention}. Quem comprar a partir de agora recebe ele.",
            view=None
        )


class SelecionarCargoClienteView(View):

    def __init__(self, cog):

        super().__init__(timeout=120)

        self.add_item(SelecionarCargoCliente(cog))


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO SelecionarCargoClienteView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("============================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


# ==========================================================
# MODELOS DE PAINEL (salvos, reutilizáveis)
# ==========================================================

class ModalNomeModelo(Modal):

    def __init__(self, cog, modelo_id=None):

        titulo = "✏️ Renomear Modelo" if modelo_id else "📁 Novo Modelo de Painel"

        super().__init__(title=titulo)

        self.cog = cog
        self.modelo_id = modelo_id

        nome_atual = None

        if modelo_id:
            modelo = cog.dados["config"].get("modelos", {}).get(modelo_id)
            nome_atual = modelo["nome"] if modelo else None

        self.nome = TextInput(
            label="Nome do modelo",
            placeholder="Ex: Painel Robux, Painel Contas Blox...",
            default=nome_atual,
            max_length=100
        )

        self.add_item(self.nome)


    async def on_submit(self, interaction: discord.Interaction):

        modelos = self.cog.dados["config"].setdefault("modelos", {})

        if self.modelo_id:

            if self.modelo_id in modelos:
                modelos[self.modelo_id]["nome"] = self.nome.value
                self.cog.salvar()

            await interaction.response.send_message(
                embed=embed_padrao("✅ Renomeado", f"Modelo agora se chama **{self.nome.value}**.", discord.Color.green()),
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                f"Nome definido: **{self.nome.value}**. Agora escolha os produtos desse modelo:",
                view=SelecionarProdutosModeloView(self.cog, self.nome.value),
                ephemeral=True
            )


class SelecionarProdutosModeloSelect(Select):

    def __init__(self, cog, nome_modelo, modelo_id=None, produtos_atuais=None):

        self.cog = cog
        self.nome_modelo = nome_modelo
        self.modelo_id = modelo_id

        produtos_atuais = produtos_atuais or []

        opcoes = [
            discord.SelectOption(
                label=produto["nome"][:100],
                value=pid,
                description=f"R$ {produto['preco']}"[:100],
                default=(pid in produtos_atuais)
            )
            for pid, produto in list(cog.dados["produtos"].items())[:25]
        ]

        super().__init__(
            placeholder="Escolha os produtos deste modelo",
            options=opcoes,
            min_values=1,
            max_values=len(opcoes)
        )


    async def callback(self, interaction: discord.Interaction):

        modelos = self.cog.dados["config"].setdefault("modelos", {})

        if self.modelo_id:

            if self.modelo_id in modelos:
                modelos[self.modelo_id]["produtos"] = list(self.values)
                self.cog.salvar()

            await interaction.response.edit_message(
                content=f"✅ Modelo **{self.nome_modelo}** atualizado com {len(self.values)} produto(s).",
                view=None
            )

        else:

            modelo_id = str(random.randint(100, 999))

            while modelo_id in modelos:
                modelo_id = str(random.randint(100, 999))

            modelos[modelo_id] = {"nome": self.nome_modelo, "produtos": list(self.values)}

            self.cog.salvar()

            await interaction.response.edit_message(
                content=f"✅ Modelo **{self.nome_modelo}** criado com {len(self.values)} produto(s)!",
                view=None
            )


class SelecionarProdutosModeloView(View):

    def __init__(self, cog, nome_modelo, modelo_id=None, produtos_atuais=None):

        super().__init__(timeout=180)

        self.add_item(SelecionarProdutosModeloSelect(cog, nome_modelo, modelo_id, produtos_atuais))


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO SelecionarProdutosModeloView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("===============================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


class AcoesModeloView(View):

    def __init__(self, cog, modelo_id):

        super().__init__(timeout=180)

        self.cog = cog
        self.modelo_id = modelo_id


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO AcoesModeloView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="📤 Enviar Aqui", style=discord.ButtonStyle.success, row=0)
    async def enviar(self, interaction: discord.Interaction, button: Button):

        modelo = self.cog.dados["config"].get("modelos", {}).get(self.modelo_id)

        if modelo is None:
            return await interaction.response.send_message("❌ Modelo não encontrado (pode ter sido excluído).", ephemeral=True)

        embed, view = construir_painel_loja(self.cog, modelo["produtos"])

        mensagem = await interaction.channel.send(embed=embed, view=view)

        self.cog.dados["config"].setdefault("paineis", []).append(
            {"canal_id": mensagem.channel.id, "mensagem_id": mensagem.id, "produtos": modelo["produtos"]}
        )

        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"✅ Modelo **{modelo['nome']}** enviado neste canal! Ele se atualiza sozinho.",
            embed=None,
            view=None
        )


    @discord.ui.button(label="✏️ Editar Produtos", style=discord.ButtonStyle.primary, row=0)
    async def editar_produtos(self, interaction: discord.Interaction, button: Button):

        modelo = self.cog.dados["config"].get("modelos", {}).get(self.modelo_id)

        if modelo is None:
            return await interaction.response.send_message("❌ Modelo não encontrado (pode ter sido excluído).", ephemeral=True)

        await interaction.response.edit_message(
            content=f"Editando produtos de **{modelo['nome']}** (os já marcados já fazem parte do modelo):",
            view=SelecionarProdutosModeloView(self.cog, modelo["nome"], self.modelo_id, modelo["produtos"])
        )


    @discord.ui.button(label="✏️ Renomear", style=discord.ButtonStyle.secondary, row=1)
    async def renomear(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalNomeModelo(self.cog, self.modelo_id)
        )


    @discord.ui.button(label="🗑️ Excluir Modelo", style=discord.ButtonStyle.danger, row=1)
    async def excluir(self, interaction: discord.Interaction, button: Button):

        modelos = self.cog.dados["config"].get("modelos", {})

        modelo = modelos.pop(self.modelo_id, None)

        self.cog.salvar()

        if modelo:
            await interaction.response.edit_message(content=f"🗑️ Modelo **{modelo['nome']}** excluído.", embed=None, view=None)
        else:
            await interaction.response.edit_message(content="❌ Esse modelo já tinha sido excluído.", embed=None, view=None)


class SelecionarModeloSelect(Select):

    def __init__(self, cog):

        self.cog = cog

        modelos = cog.dados["config"].get("modelos", {})

        opcoes = [
            discord.SelectOption(
                label=modelo["nome"][:100],
                value=mid,
                description=f"{len(modelo['produtos'])} produto(s)"
            )
            for mid, modelo in modelos.items()
        ][:25]

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhum modelo salvo ainda", value="dummy")]

        super().__init__(placeholder="📂 Escolha um modelo salvo", options=opcoes, row=0, custom_id="loja_modelos_select")


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhum modelo salvo ainda. Crie um primeiro.", ephemeral=True)

        modelo_id = self.values[0]

        modelo = self.cog.dados["config"].get("modelos", {}).get(modelo_id)

        if modelo is None:
            return await interaction.response.send_message("❌ Modelo não encontrado (pode ter sido excluído).", ephemeral=True)

        await interaction.response.send_message(
            embed=embed_padrao(
                f"📁 {modelo['nome']}",
                f"📦 {len(modelo['produtos'])} produto(s) configurado(s).\nO que deseja fazer?",
                discord.Color.blurple()
            ),
            view=AcoesModeloView(self.cog, modelo_id),
            ephemeral=True
        )


class ModelosView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        self.add_item(SelecionarModeloSelect(cog))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO ModelosView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=============================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="➕ Criar Modelo", style=discord.ButtonStyle.success, row=1, custom_id="loja_modelos_criar")
    async def criar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalNomeModelo(self.cog)
        )


class PainelAdminView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog


    async def interaction_check(self, interaction: discord.Interaction):

        autorizado = await eh_dono(
            interaction.client,
            interaction.user.id,
            interaction.guild.id if interaction.guild else None
        )

        if not autorizado:

            await interaction.response.send_message(
                "🚫 Você precisa ser Administrador no servidor para usar isso.",
                ephemeral=True
            )

            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelAdminView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="➕ Novo Produto", style=discord.ButtonStyle.success, row=0, custom_id="loja_admin_novo_produto")
    async def novo_produto(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalNovoProduto(self.cog)
        )


    @discord.ui.button(label="📦 Adicionar Estoque", style=discord.ButtonStyle.primary, row=0, custom_id="loja_admin_add_estoque")
    async def add_estoque(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["produtos"]:

            return await interaction.response.send_message(
                "❌ Cadastre um produto primeiro (botão ➕ Novo Produto).",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Escolha o produto que vai receber estoque:",
            view=SelecionarProdutoEstoqueView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="💰 Configurar PIX", style=discord.ButtonStyle.primary, row=0, custom_id="loja_admin_pix")
    async def config_pix(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalPix(self.cog)
        )


    @discord.ui.button(label="📋 Ver Produtos", style=discord.ButtonStyle.secondary, row=1, custom_id="loja_admin_ver_produtos")
    async def ver_produtos(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["produtos"]:

            return await interaction.response.send_message(
                "📦 Nenhum produto cadastrado ainda.",
                ephemeral=True
            )

        embed = embed_padrao("📦 Produtos da Loja", "Lista de todos os produtos cadastrados.")

        for pid, produto in self.cog.dados["produtos"].items():

            embed.add_field(
                name=f"{produto['nome']}  •  ID `{pid}`",
                value=f"💰 R$ {produto['preco']}\n📦 Estoque: {len(produto['estoque'])}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @discord.ui.button(label="📤 Enviar Painel Aqui", style=discord.ButtonStyle.success, row=1, custom_id="loja_admin_enviar_painel")
    async def enviar_painel(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["produtos"]:

            return await interaction.response.send_message(
                "❌ Cadastre um produto primeiro.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Escolha os produtos deste painel:",
            view=SelecionarProdutosPainelView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="✏️ Editar Painel", style=discord.ButtonStyle.secondary, row=1, custom_id="loja_admin_editar_painel")
    async def editar_painel(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalEditarPainel(self.cog)
        )


    @discord.ui.button(label="🖼️ Definir Banner", style=discord.ButtonStyle.secondary, row=2, custom_id="loja_admin_banner")
    async def definir_banner(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(
            embed=embed_padrao(
                "🖼️ Banner do painel",
                "Envie uma **imagem** aqui no chat nos próximos 60 segundos (ou o **link** direto de uma imagem).",
                discord.Color.blurple()
            ),
            ephemeral=True
        )

        def checar(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and (m.attachments or m.content.startswith("http"))

        try:

            msg = await interaction.client.wait_for("message", check=checar, timeout=60)

            url = msg.attachments[0].url if msg.attachments else msg.content.strip()

            self.cog.dados["config"]["painel_banner"] = url
            self.cog.salvar()

            await atualizar_todos_paineis(self.cog)

            await interaction.followup.send(
                embed=embed_padrao("✅ Banner definido", "Todos os painéis já enviados foram atualizados.", discord.Color.green()),
                ephemeral=True
            )

        except asyncio.TimeoutError:

            await interaction.followup.send(
                embed=embed_padrao("⏳ Tempo esgotado", "Nenhuma imagem recebida.", discord.Color.orange()),
                ephemeral=True
            )


    @discord.ui.button(label="🏷️ Cargo de Cliente", style=discord.ButtonStyle.secondary, row=2, custom_id="loja_admin_cargo_cliente")
    async def definir_cargo_cliente(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(
            "Escolha o cargo que quem comprar vai receber automaticamente:",
            view=SelecionarCargoClienteView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="📁 Modelos de Painel", style=discord.ButtonStyle.primary, row=3, custom_id="loja_admin_modelos")
    async def modelos(self, interaction: discord.Interaction, button: Button):

        modelos = self.cog.dados["config"].get("modelos", {})

        if modelos:
            lista = "\n".join(f"• **{m['nome']}** — {len(m['produtos'])} produto(s)" for m in modelos.values())
        else:
            lista = "_Nenhum modelo salvo ainda._"

        texto = (
            "## 📁 Modelos de Painel\n"
            "Modelos salvos que você pode reenviar ou editar a qualquer momento, sem montar do zero.\n\n"
            f"**Modelos salvos**\n{lista}"
        )

        await interaction.response.send_message(view=container_view(texto, ModelosView(self.cog)), ephemeral=True)


    @discord.ui.button(label="🎮 Configurar Robux", style=discord.ButtonStyle.primary, row=4, custom_id="loja_admin_config_robux")
    async def config_robux(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalConfigRobux(self.cog)
        )


    @discord.ui.button(label="📤 Enviar Painel Robux Aqui", style=discord.ButtonStyle.success, row=4, custom_id="loja_admin_enviar_robux")
    async def enviar_painel_robux(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["config"].get("robux_preco_k"):

            return await interaction.response.send_message(
                "❌ Configure o preço do Robux primeiro (botão 🎮 Configurar Robux).",
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=embed_robux_painel(),
            view=RobuxPainelView(self.cog)
        )



# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Loja(bot)
    )
