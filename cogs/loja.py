import discord
import os
import json
import random
import time
import asyncio

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput

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

    @commands.command(name="loja-add-produto")
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

    @commands.command(name="loja-produtos")
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

    @commands.command(name="loja-stats")
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


    @commands.command(name="loja-notas")
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

    @commands.command(name="loja-remover-produto")
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

    @commands.command(name="loja-ver-estoque")
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


    @commands.command(name="loja-remover-estoque")
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
    # ENVIAR PAINEL
    # ======================================================

    @commands.command(name="loja-painel")
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


    # ======================================================
    # EDITAR PAINEL (título/descrição)
    # ======================================================

    @commands.command(name="editar-painel")
    async def editar_painel_cmd(self, ctx, *, texto: str = None):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padra
