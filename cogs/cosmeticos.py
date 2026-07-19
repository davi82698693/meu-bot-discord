import discord
import os
import json
import random

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput, RoleSelect


DATA_DIR = (
    os.getenv("COSMETICOS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "cosmeticos_data.json")

MOEDA = "🪙"


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"itens": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("itens", {})
            return dados
    except Exception:
        return {"itens": {}}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar cosmeticos_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.purple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="✨ Loja de Cosméticos")

    return embed


def container_view(texto, source_view, accent_color=discord.Color.purple()):

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


class Cosmeticos(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        self.bot.add_view(PainelLojaCosmeticosView(self))
        self.bot.add_view(PainelAdminCosmeticosView(self))


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="loja-cosmeticos")
    async def loja_cosmeticos_cmd(self, ctx):

        texto = texto_loja(self.dados)

        await ctx.send(view=container_view(texto, PainelLojaCosmeticosView(self)))


    @commands.hybrid_command(name="cosmeticos-admin")
    @commands.has_permissions(administrator=True)
    async def cosmeticos_admin(self, ctx):

        texto = texto_admin(self.dados)

        await ctx.send(view=container_view(texto, PainelAdminCosmeticosView(self)))


async def setup(bot):

    await bot.add_cog(
        Cosmeticos(bot)
    )


def texto_loja(dados):

    linhas = [
        "## ✨ Loja de Cosméticos",
        "Use suas moedas pra comprar cargos especiais! Escolha abaixo.",
        ""
    ]

    if not dados["itens"]:
        linhas.append("_Nenhum item disponível ainda._")
    else:
        for item_id, item in dados["itens"].items():
            linhas.append(f"🏷️ **{item['nome']}** — {item['preco']} {MOEDA} — <@&{item['cargo_id']}>")

    return "\n".join(linhas)


def texto_admin(dados):

    linhas = [
        "## 🛠️ Administração — Loja de Cosméticos",
        "Cadastre cargos que os membros podem comprar com moedas.",
        ""
    ]

    if not dados["itens"]:
        linhas.append("_Nenhum item cadastrado ainda._")
    else:
        for item_id, item in dados["itens"].items():
            linhas.append(f"`{item_id}` — **{item['nome']}** — {item['preco']} {MOEDA}")

    return "\n".join(linhas)


# ==========================================================
# COMPRA
# ==========================================================

class SelecionarItemComprar(Select):

    def __init__(self, cog):

        self.cog = cog

        opcoes = [
            discord.SelectOption(
                label=f"{item['nome']} — {item['preco']} {MOEDA}"[:100],
                value=item_id
            )
            for item_id, item in cog.dados["itens"].items()
        ][:25]

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhum item disponível", value="dummy")]

        super().__init__(placeholder="🛍️ Escolha um item pra comprar", options=opcoes, row=0)


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhum item disponível ainda.", ephemeral=True)

        item = self.cog.dados["itens"].get(self.values[0])

        if item is None:
            return await interaction.response.send_message("❌ Esse item não existe mais.", ephemeral=True)

        jogos = interaction.client.get_cog("Jogos")

        if jogos is None:
            return await interaction.response.send_message("❌ Sistema de economia indisponível no momento.", ephemeral=True)

        saldo = jogos.saldo(interaction.user.id)

        if saldo < item["preco"]:
            return await interaction.response.send_message(
                f"❌ Você não tem moedas suficientes. Precisa de {item['preco']} {MOEDA}, você tem {saldo} {MOEDA}.",
                ephemeral=True
            )

        cargo = interaction.guild.get_role(item["cargo_id"])

        if cargo is None:
            return await interaction.response.send_message("❌ O cargo desse item não existe mais.", ephemeral=True)

        if cargo in interaction.user.roles:
            return await interaction.response.send_message("⚠️ Você já tem esse item.", ephemeral=True)

        jogos.remover(interaction.user.id, item["preco"])
        jogos.salvar()

        try:
            await interaction.user.add_roles(cargo, reason="Compra na loja de cosméticos")
        except Exception:

            jogos.adicionar(interaction.user.id, item["preco"])
            jogos.salvar()

            return await interaction.response.send_message(
                "❌ Não consegui dar o cargo (permissão do bot). Suas moedas foram devolvidas.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ Você comprou **{item['nome']}**! Cargo {cargo.mention} adicionado.",
            ephemeral=True
        )


class PainelLojaCosmeticosView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.add_item(SelecionarItemComprar(cog))


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelLojaCosmeticosView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("==========================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


# ==========================================================
# ADMINISTRAÇÃO
# ==========================================================

class ModalPrecoItem(Modal):

    def __init__(self, cog, cargo):

        super().__init__(title="✨ Preço do Item")

        self.cog = cog
        self.cargo = cargo

        self.preco = TextInput(
            label="Preço em moedas",
            placeholder="Ex: 5000",
            max_length=10
        )

        self.add_item(self.preco)


    async def on_submit(self, interaction: discord.Interaction):

        try:
            preco = int(self.preco.value.strip())
            if preco <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Digite um número válido.", ephemeral=True)

        item_id = str(random.randint(1000, 9999))

        while item_id in self.cog.dados["itens"]:
            item_id = str(random.randint(1000, 9999))

        self.cog.dados["itens"][item_id] = {
            "nome": self.cargo.name,
            "preco": preco,
            "cargo_id": self.cargo.id
        }

        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao("✅ Item criado", f"**{self.cargo.name}** por {preco} {MOEDA} (ID `{item_id}`).", discord.Color.green()),
            ephemeral=True
        )


class SelecionarCargoItem(RoleSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(placeholder="Escolha o cargo do novo item", row=0)


    async def callback(self, interaction: discord.Interaction):

        cargo = self.values[0]

        if cargo.managed:
            return await interaction.response.send_message("❌ Esse cargo é gerenciado automaticamente e não pode ser usado.", ephemeral=True)

        await interaction.response.send_modal(ModalPrecoItem(self.cog, cargo))


class SelecionarCargoItemView(View):

    def __init__(self, cog):

        super().__init__(timeout=120)

        self.add_item(SelecionarCargoItem(cog))


class SelecionarItemRemover(Select):

    def __init__(self, cog):

        self.cog = cog

        opcoes = [
            discord.SelectOption(label=f"{item['nome']} ({item_id})"[:100], value=item_id)
            for item_id, item in cog.dados["itens"].items()
        ][:25]

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhum item cadastrado", value="dummy")]

        super().__init__(placeholder="🗑️ Escolha o item pra remover", options=opcoes)


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhum item cadastrado.", ephemeral=True)

        item = self.cog.dados["itens"].pop(self.values[0], None)

        self.cog.salvar()

        await interaction.response.edit_message(
            content=f"🗑️ Item **{item['nome']}** removido." if item else "❌ Item não encontrado.",
            view=None
        )


class SelecionarItemRemoverView(View):

    def __init__(self, cog):

        super().__init__(timeout=120)

        self.add_item(SelecionarItemRemover(cog))


class PainelAdminCosmeticosView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelAdminCosmeticosView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("===========================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="➕ Criar Item", style=discord.ButtonStyle.success, row=0, custom_id="cosmeticos_add")
    async def criar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(
            "Escolha o cargo desse item:",
            view=SelecionarCargoItemView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="🗑️ Remover Item", style=discord.ButtonStyle.danger, row=0, custom_id="cosmeticos_remove")
    async def remover(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(
            "Escolha o item pra remover:",
            view=SelecionarItemRemoverView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="📤 Enviar Loja Aqui", style=discord.ButtonStyle.primary, row=1, custom_id="cosmeticos_enviar")
    async def enviar(self, interaction: discord.Interaction, button: Button):

        if not self.cog.dados["itens"]:
            return await interaction.response.send_message("❌ Crie pelo menos um item primeiro.", ephemeral=True)

        texto = texto_loja(self.cog.dados)

        await interaction.channel.send(view=container_view(texto, PainelLojaCosmeticosView(self.cog)))

        await interaction.response.send_message("✅ Loja enviada neste canal!", ephemeral=True)
