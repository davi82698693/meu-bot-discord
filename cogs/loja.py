import discord
import os
import json
import random
import time

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button


# ==========================================================
# CONFIG / PERSISTÊNCIA
# ==========================================================

DATA_DIR = os.getenv("LOJA_DATA_DIR", os.path.dirname(__file__))

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


def eh_dono(user_id):

    return user_id in DONO_IDS



def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"produtos": {}, "pedidos": {}, "config": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("produtos", {})
            dados.setdefault("pedidos", {})
            dados.setdefault("config", {})
            return dados
    except Exception as e:
        print(f"⚠️ Erro ao carregar loja_data.json: {e}")
        return {"produtos": {}, "pedidos": {}, "config": {}}


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
                "⚠️ ATENÇÃO: nenhum LOJA_DONO_IDS configurado. "
                "Ninguém vai conseguir aprovar pagamentos até configurar essa variável."
            )

        # registra a view do painel (rota fixa pro select funcionar após restart)
        self.bot.add_view(LojaPainelView(self))

        # reregistra views de pedidos em andamento
        for pedido_id, pedido in list(self.dados["pedidos"].items()):

            if pedido["status"] == "aguardando_pagamento":
                self.bot.add_view(PagamentoView(pedido_id))

            elif pedido["status"] == "aguardando_aprovacao":
                self.bot.add_view(AprovarView(pedido_id))


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


    def _checar_dono(self, ctx):

        return eh_dono(ctx.author.id)


    # ======================================================
    # ADICIONAR PRODUTO
    # ======================================================

    @commands.command(name="loja-add-produto")
    async def loja_add_produto(self, ctx, nome: str, preco: str, *, descricao: str = "Sem descrição."):

        if not self._checar_dono(ctx):
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

        if not self._checar_dono(ctx):
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

        if not self._checar_dono(ctx):
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
    # REMOVER PRODUTO
    # ======================================================

    @commands.command(name="loja-remover-produto")
    async def loja_remover_produto(self, ctx, produto_id: str):

        if not self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        produto = self.dados["produtos"].pop(produto_id, None)

        if produto is None:
            return await ctx.send(
                embed=embed_padrao("❌ Produto não encontrado", f"Não existe produto com ID `{produto_id}`.", discord.Color.red())
            )

        self.salvar()

        await ctx.send(
            embed=embed_padrao("🗑️ Produto removido", f"**{produto['nome']}** foi removido da loja.", discord.Color.orange())
        )


    # ======================================================
    # CONFIGURAR PIX
    # ======================================================

    @commands.command(name="loja-pix")
    async def loja_pix(self, ctx, *, chave: str):

        if not self._checar_dono(ctx):
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

        if not self._checar_dono(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Apenas os donos da loja podem usar isso.", discord.Color.red())
            )

        if not self.dados["produtos"]:
            return await ctx.send(
                embed=embed_padrao("❌ Sem produtos", "Cadastre pelo menos um produto antes de enviar o painel.", discord.Color.red())
            )

        embed = discord.Embed(
            title="🛒 Loja",
            description="Escolha abaixo o produto que deseja comprar.",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )

        for pid, produto in self.dados["produtos"].items():

            status = f"📦 {len(produto['estoque'])} em estoque" if produto["estoque"] else "❌ Esgotado"

            embed.add_field(
                name=f"{produto['nome']} — R$ {produto['preco']}",
                value=f"{produto['descricao']}\n{status}",
                inline=False
            )

        embed.set_footer(text="Selecione um produto no menu abaixo")

        opcoes = []

        for pid, produto in self.dados["produtos"].items():

            disponivel = len(produto["estoque"]) > 0

            label = produto["nome"]

            if not disponivel:
                label = f"🚫 {label} (Esgotado)"

            opcoes.append(
                discord.SelectOption(
                    label=label[:100],
                    value=pid,
                    description=f"R$ {produto['preco']}"[:100]
                )
            )

        view = LojaPainelView(self, opcoes)

        await ctx.send(embed=embed, view=view)


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
                "❌ Esse painel está desatualizado. Peça para a equipe reenviar com `!loja-painel`.",
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
        "guild_id": interaction.guild.id if interaction.guild else None
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

        if not DONO_IDS:
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

        for dono_id in DONO_IDS:

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

        if not eh_dono(interaction.user.id):
            return await interaction.response.send_message("🚫 Você não é um dono da loja.", ephemeral=True)

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

        if pedido["status"] != "aguardando_aprovacao":
            return await interaction.response.edit_message(
                content=f"⚠️ Esse pedido já foi processado (status atual: `{pedido['status']}`).",
                embed=None,
                view=None
            )

        produto = cog.dados["produtos"].get(pedido["produto_id"])

        if produto is None or not produto["estoque"]:

            return await interaction.response.send_message(
                "❌ Esse produto está sem estoque! Adicione mais com `!loja-add-estoque` e clique em Aprovar de novo.",
                ephemeral=True
            )

        credencial = produto["estoque"].pop(0)

        pedido["status"] = "aprovado"

        cog.salvar()

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

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Pedido aprovado",
                description=(
                    f"Produto **{pedido['produto_nome']}** entregue via DM"
                    f"{' com sucesso.' if entregue else ', mas a DM falhou — envie manualmente:'}\n"
                    + (f"```{credencial}```" if not entregue else "")
                ),
                color=discord.Color.green()
            ),
            view=None
        )

        if interaction.guild is None and pedido.get("guild_id"):

            guild = interaction.client.get_guild(pedido["guild_id"])

            await enviar_log(
                interaction.client,
                guild,
                f"✅ Pedido `{self.pedido_id}` aprovado — **{pedido['produto_nome']}** entregue para <@{comprador_id}>.",
                discord.Color.green()
            )


    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: Button):

        if not eh_dono(interaction.user.id):
            return await interaction.response.send_message("🚫 Você não é um dono da loja.", ephemeral=True)

        cog = interaction.client.get_cog("Loja")

        if cog is None:
            return await interaction.response.send_message("❌ Sistema indisponível.", ephemeral=True)

        pedido = cog.dados["pedidos"].get(self.pedido_id)

        if pedido is None:
            return await interaction.response.send_message("❌ Pedido não encontrado.", ephemeral=True)

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
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Loja(bot)
    )
