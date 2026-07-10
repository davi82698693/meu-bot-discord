import discord
import os
import json
import random
import time
import asyncio

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput


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

    @commands.command(name="loja-admin")
    async def loja_admin(self, ctx):

        if not await self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        embed = embed_padrao(
            "🛠️ Painel de Administração da Loja",
            "Use os botões abaixo para gerenciar a loja sem precisar decorar comandos.",
            discord.Color.blurple()
        )

        await ctx.send(embed=embed, view=PainelAdminView(self))


# ==========================================================
# CONSTRUIR EMBED + VIEW DO PAINEL DE COMPRAS
# ==========================================================

def construir_painel_loja(cog, produtos_ids=None):

    titulo = cog.dados["config"].get("painel_titulo") or "🛒 Loja"

    descricao = cog.dados["config"].get("painel_descricao") or "Escolha abaixo o produto que deseja comprar."

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    produtos_disponiveis = {
        pid: produto
        for pid, produto in cog.dados["produtos"].items()
        if produto["estoque"]
        and (produtos_ids is None or pid in produtos_ids)
    }

    if not produtos_disponiveis:

        embed.add_field(
            name="😕 Sem produtos disponíveis no momento",
            value="Volte mais tarde!",
            inline=False
        )

    for pid, produto in produtos_disponiveis.items():

        embed.add_field(
            name=f"{produto['nome']} — R$ {produto['preco']}",
            value=f"{produto['descricao']}\n📦 {len(produto['estoque'])} em estoque",
            inline=False
        )

    embed.set_footer(text="Selecione um produto no menu abaixo")

    opcoes = []

    for pid, produto in produtos_disponiveis.items():

        opcoes.append(
            discord.SelectOption(
                label=produto["nome"][:100],
                value=pid,
                description=f"Preço: R$ {produto['preco']} | Estoque: {len(produto['estoque'])}"[:100]
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

        await iniciar_compra(self.cog, interaction, produto_id)


class LojaPainelView(View):

    def __init__(self, cog, opcoes=None):

        super().__init__(timeout=None)

        self.add_item(LojaSelect(cog, opcoes))


# ==========================================================
# INICIAR COMPRA
# ==========================================================

async def iniciar_compra(cog, interaction: discord.Interaction, produto_id):

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
        "status": "aguardando_pagamento",
        "criado_em": time.time(),
        "guild_id": interaction.guild.id if interaction.guild else None,
        "avaliado": False
    }

    cog.salvar()

    embed = discord.Embed(
        title=f"🛒 {produto['nome']}",
        description=(
            f"💰 **Valor:** R$ {produto['preco']}\n\n"
            f"**Chave PIX (copia e cola):**\n```{pix_chave}```\n"
            "Depois de pagar, clique no botão **✅ Já paguei** abaixo.\n"
            "Sua conta será enviada aqui no privado assim que o pagamento for aprovado."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

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

        aviso = discord.Embed(
            title="🛒 Novo pedido aguardando aprovação",
            description=(
                f"👤 **Comprador:** <@{interaction.user.id}> (`{interaction.user.id}`)\n"
                f"🎁 **Produto:** {pedido['produto_nome']}\n"
                f"💰 **Valor:** R$ {pedido['preco']}\n"
                f"🆔 **Pedido:** `{self.pedido_id}`"
            ),
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

            await comprador.send(
                embed=discord.Embed(
                    title="✅ Pagamento aprovado!",
                    description=(
                        f"🎁 **Produto:** {pedido['produto_nome']}\n\n"
                        f"**Dados de acesso:**\n```{credencial}```\n"
                        "Obrigado pela compra! 🎉"
                    ),
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

        await enviar_log(
            interaction.client,
            guild,
            f"✅ Pedido `{self.pedido_id}` aprovado — **{pedido['produto_nome']}** entregue para <@{comprador_id}>.",
            discord.Color.green()
        )

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
            "produto_id": pedido["produto_id"],
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


class PainelAdminView(View):

    def __init__(self, cog):

        super().__init__(timeout=300)

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


    @discord.ui.button(label="➕ Novo Produto", style=discord.ButtonStyle.success, row=0)
    async def novo_produto(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalNovoProduto(self.cog)
        )


    @discord.ui.button(label="📦 Adicionar Estoque", style=discord.ButtonStyle.primary, row=0)
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


    @discord.ui.button(label="💰 Configurar PIX", style=discord.ButtonStyle.primary, row=0)
    async def config_pix(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalPix(self.cog)
        )


    @discord.ui.button(label="📋 Ver Produtos", style=discord.ButtonStyle.secondary, row=1)
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


    @discord.ui.button(label="📤 Enviar Painel Aqui", style=discord.ButtonStyle.success, row=1)
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


    @discord.ui.button(label="✏️ Editar Painel", style=discord.ButtonStyle.secondary, row=1)
    async def editar_painel(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(
            ModalEditarPainel(self.cog)
        )



# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Loja(bot)
    )
