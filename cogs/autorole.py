import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button, RoleSelect, Select


DATA_DIR = (
    os.getenv("AUTOROLE_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "autorole_data.json")


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
        print(f"⚠️ Erro ao salvar autorole_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🏷️ Cargo Automático")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"cargos": [], "ativo": True})


# ==========================================================
# COG
# ==========================================================

class Autorole(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    def salvar(self):

        salvar_dados(self.dados)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        if member.bot:
            return

        conf = config(self.dados, member.guild.id)

        if not conf.get("ativo", True):
            return

        for cargo_id in conf.get("cargos", []):

            cargo = member.guild.get_role(cargo_id)

            if cargo is None:
                continue

            try:
                await member.add_roles(cargo, reason="Cargo automático de entrada")
            except Exception as e:
                print(f"⚠️ Não consegui dar o cargo automático pra {member}: {e}")


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="autorole-painel")
    @commands.has_permissions(administrator=True)
    async def autorole_painel(self, ctx):

        conf = config(self.dados, ctx.guild.id)

        await ctx.send(
            embed=gerar_embed_painel(ctx.guild, conf),
            view=PainelAutoroleView(self, conf)
        )


async def setup(bot):

    await bot.add_cog(
        Autorole(bot)
    )


# ==========================================================
# EMBED DO PAINEL
# ==========================================================

def gerar_embed_painel(guild, conf):

    status = "🟢 Ativado" if conf.get("ativo", True) else "🔴 Desativado"

    if conf["cargos"]:
        texto = "\n".join(f"<@&{cid}>" for cid in conf["cargos"])
    else:
        texto = "_Nenhum cargo configurado._"

    embed = embed_padrao(
        "🛠️ Painel de Cargo Automático",
        "Escolha os cargos que todo novo membro recebe automaticamente ao entrar no servidor.",
        discord.Color.blurple()
    )

    embed.add_field(name="Status", value=status, inline=False)
    embed.add_field(name="Cargos configurados", value=texto, inline=False)

    return embed


# ==========================================================
# ADICIONAR CARGO
# ==========================================================

class SelecionarCargoAutorole(RoleSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(placeholder="➕ Escolha um cargo pra adicionar", row=0)


    async def callback(self, interaction: discord.Interaction):

        cargo = self.values[0]

        conf = config(self.cog.dados, interaction.guild.id)

        if cargo.managed:
            return await interaction.response.send_message(
                "❌ Esse cargo é gerenciado automaticamente (bot/integração/boost) e não pode ser usado.",
                ephemeral=True
            )

        if cargo.id in conf["cargos"]:
            return await interaction.response.send_message("⚠️ Esse cargo já está configurado.", ephemeral=True)

        conf["cargos"].append(cargo.id)
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=PainelAutoroleView(self.cog, conf)
        )


# ==========================================================
# REMOVER CARGO
# ==========================================================

class RemoverCargoAutorole(Select):

    def __init__(self, cog, conf):

        self.cog = cog

        opcoes = [
            discord.SelectOption(label=f"ID {cid}", value=str(cid))
            for cid in conf["cargos"]
        ][:25]

        if not opcoes:
            opcoes = [discord.SelectOption(label="Nenhum cargo configurado", value="dummy")]

        super().__init__(placeholder="➖ Escolha um cargo pra remover", options=opcoes, row=1)


    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "dummy":
            return await interaction.response.send_message("❌ Nenhum cargo configurado ainda.", ephemeral=True)

        conf = config(self.cog.dados, interaction.guild.id)

        cargo_id = int(self.values[0])

        if cargo_id not in conf["cargos"]:
            return await interaction.response.send_message(
                "⚠️ Esse menu está desatualizado, reabra com `!autorole-painel`.",
                ephemeral=True
            )

        conf["cargos"] = [c for c in conf["cargos"] if c != cargo_id]
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=PainelAutoroleView(self.cog, conf)
        )


# ==========================================================
# VIEW PRINCIPAL DO PAINEL
# ==========================================================

class PainelAutoroleView(View):

    def __init__(self, cog, conf):

        super().__init__(timeout=300)

        self.cog = cog

        self.add_item(SelecionarCargoAutorole(cog))
        self.add_item(RemoverCargoAutorole(cog, conf))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelAutoroleView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("====================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    @discord.ui.button(label="🟢 Ativar", style=discord.ButtonStyle.success, row=2)
    async def ativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)
        conf["ativo"] = True
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=PainelAutoroleView(self.cog, conf)
        )


    @discord.ui.button(label="🔴 Desativar", style=discord.ButtonStyle.danger, row=2)
    async def desativar(self, interaction: discord.Interaction, button: Button):

        conf = config(self.cog.dados, interaction.guild.id)
        conf["ativo"] = False
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=PainelAutoroleView(self.cog, conf)
        )
