import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button, RoleSelect


DATA_DIR = (
    os.getenv("CARGOS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "cargos_data.json")


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar cargos_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🎭 Cargos Automáticos")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"cargos": []})


# ==========================================================
# COG
# ==========================================================

class Cargos(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        self.bot.add_view(CargosPainelView(self))


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="cargos-admin")
    @commands.has_permissions(administrator=True)
    async def cargos_admin(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        await ctx.send(
            embed=gerar_embed_admin(ctx.guild, conf),
            view=PainelAdminCargosView(self)
        )


async def setup(bot):

    await bot.add_cog(
        Cargos(bot)
    )


# ==========================================================
# EMBEDS
# ==========================================================

def gerar_embed_admin(guild, conf):

    embed = embed_padrao(
        "🛠️ Painel de Cargos Automáticos",
        "Adicione cargos que os membros vão poder escolher sozinhos, depois clique em "
        "**📤 Enviar Painel Aqui** no canal desejado.",
        discord.Color.blurple()
    )

    if not conf["cargos"]:

        embed.add_field(name="Cargos configurados", value="_Nenhum ainda._", inline=False)

    else:

        texto = "\n".join(
            f"{c['emoji']} <@&{c['id']}>"
            for c in conf["cargos"]
        )

        embed.add_field(name=f"Cargos configurados ({len(conf['cargos'])}/25)", value=texto, inline=False)

    return embed


def gerar_embed_publico(guild, conf):

    embed = embed_padrao(
        "🎭 Escolha seus cargos",
        "Selecione abaixo os cargos que você quer ter. Pode escolher mais de um, "
        "e desmarcar pra remover.",
        discord.Color.gold()
    )

    if conf["cargos"]:

        texto = "\n".join(
            f"{c['emoji']} <@&{c['id']}>"
            for c in conf["cargos"]
        )

        embed.add_field(name="Disponíveis", value=texto, inline=False)

    return embed


# ==========================================================
# PAINEL PÚBLICO (membros escolhem os cargos)
# ==========================================================

class CargosSelect(Select):

    def __init__(self, cog, opcoes=None):

        self.cog = cog

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhum cargo configurado ainda", value="dummy")]

        super().__init__(
            placeholder="Escolha seus cargos",
            options=opcoes,
            min_values=0,
            max_values=len(opcoes),
            custom_id="cargos_painel_select"
        )


    async def callback(self, interaction: discord.Interaction):

        if not self.values or "dummy" in self.values:
            return await interaction.response.send_message(
                "❌ Nenhum cargo configurado ainda, ou esse painel está desatualizado.",
                ephemeral=True
            )

        conf = config(self.cog.dados, interaction.guild.id)

        ids_configurados = {c["id"] for c in conf["cargos"]}

        selecionados = {int(v) for v in self.values}

        adicionados = []
        removidos = []

        for cargo_id in ids_configurados:

            cargo = interaction.guild.get_role(cargo_id)

            if cargo is None:
                continue

            tem = cargo in interaction.user.roles

            deveria_ter = cargo_id in selecionados

            try:

                if deveria_ter and not tem:
                    await interaction.user.add_roles(cargo, reason="Auto-cargo (painel)")
                    adicionados.append(cargo.mention)

                elif not deveria_ter and tem:
                    await interaction.user.remove_roles(cargo, reason="Auto-cargo (painel)")
                    removidos.append(cargo.mention)

            except discord.Forbidden:
                pass

        partes = []

        if adicionados:
            partes.append("✅ Adicionado: " + ", ".join(adicionados))

        if removidos:
            partes.append("➖ Removido: " + ", ".join(removidos))

        texto = "\n".join(partes) if partes else "Nenhuma mudança."

        await interaction.response.send_message(texto, ephemeral=True)


class CargosPainelView(View):

    def __init__(self, cog, opcoes=None):

        super().__init__(timeout=None)

        self.add_item(CargosSelect(cog, opcoes))


# ==========================================================
# PAINEL DE ADMINISTRAÇÃO
# ==========================================================

class ModalEmoji(discord.ui.Modal):

    def __init__(self, cog, cargo: discord.Role):

        super().__init__(title="🎭 Emoji do cargo")

        self.cog = cog
        self.cargo = cargo

        self.emoji = discord.ui.TextInput(
            label="Emoji (opcional)",
            placeholder="Ex: 🎮",
            required=False,
            max_length=10
        )

        self.add_item(self.emoji)


    async def on_submit(self, interaction: discord.Interaction):

        conf = config(self.cog.dados, interaction.guild.id)

        if len(conf["cargos"]) >= 25:
            return await interaction.response.send_message("❌ Máximo de 25 cargos no painel.", ephemeral=True)

        if any(c["id"] == self.cargo.id for c in conf["cargos"]):
            return await interaction.response.send_message("⚠️ Esse cargo já está configurado.", ephemeral=True)

        conf["cargos"].append({
            "id": self.cargo.id,
            "emoji": self.emoji.value.strip() or "🎭"
        })

        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao("✅ Cargo adicionado", f"{self.emoji.value or '🎭'} {self.cargo.mention} agora está disponível no painel.", discord.Color.green()),
            ephemeral=True
        )


class SelecionarCargoAdicionar(RoleSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(placeholder="Escolha o cargo pra adicionar ao painel")


    async def callback(self, interaction: discord.Interaction):

        cargo = self.values[0]

        await interaction.response.send_modal(ModalEmoji(self.cog, cargo))


class SelecionarCargoAdicionarView(View):

    def __init__(self, cog):

        super().__init__(timeout=120)

        self.add_item(SelecionarCargoAdicionar(cog))


class SelecionarCargoRemover(Select):

    def __init__(self, cog, conf):

        self.cog = cog

        opcoes = [
            discord.SelectOption(label=f"ID {c['id']}", value=str(c["id"]), emoji=None, description=c["emoji"])
            for c in conf["cargos"]
        ][:25]

        super().__init__(placeholder="Escolha o cargo pra remover do painel", options=opcoes or [discord.SelectOption(label="Nenhum cargo configurado", value="dummy")])


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhum cargo configurado.", ephemeral=True)

        conf = config(self.cog.dados, interaction.guild.id)

        cargo_id = int(self.values[0])

        conf["cargos"] = [c for c in conf["cargos"] if c["id"] != cargo_id]

        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao("🗑️ Cargo removido", f"<@&{cargo_id}> não aparece mais no painel.", discord.Color.orange()),
            ephemeral=True
        )


class SelecionarCargoRemoverView(View):

    def __init__(self, cog, conf):

        super().__init__(timeout=120)

        self.add_item(SelecionarCargoRemover(cog, conf))


class PainelAdminCargosView(View):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelAdminCargosView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("=======================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="➕ Adicionar Cargo", style=discord.ButtonStyle.success, row=0)
    async def adicionar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(
            "Escolha o cargo:",
            view=SelecionarCargoAdicionarView(self.cog),
            ephemeral=True
        )


    @discord.ui.button(label="🗑️ Remover Cargo", style=discord.ButtonStyle.danger, row=0)
    async def remover(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)

        await interaction.response.send_message(
            "Escolha o cargo pra remover do painel:",
            view=SelecionarCargoRemoverView(self.cog, conf),
            ephemeral=True
        )


    @discord.ui.button(label="📤 Enviar Painel Aqui", style=discord.ButtonStyle.primary, row=1)
    async def enviar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)

        if not conf["cargos"]:
            return await interaction.response.send_message("❌ Configure pelo menos um cargo primeiro.", ephemeral=True)

        opcoes = [
            discord.SelectOption(label=(interaction.guild.get_role(c["id"]).name if interaction.guild.get_role(c["id"]) else f"ID {c['id']}")[:100], value=str(c["id"]), emoji=c["emoji"] if c["emoji"] and len(c["emoji"]) <= 2 else None)
            for c in conf["cargos"]
        ]

        await interaction.channel.send(
            embed=gerar_embed_publico(interaction.guild, conf),
            view=CargosPainelView(self.cog, opcoes)
        )

        await interaction.response.send_message("✅ Painel enviado neste canal!", ephemeral=True)
