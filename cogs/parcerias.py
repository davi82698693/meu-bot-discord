import discord
import os
import json
import random

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput


DATA_DIR = (
    os.getenv("PARCERIAS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "parcerias_data.json")


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
        print(f"⚠️ Erro ao salvar parcerias_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🤝 Parcerias")

    return embed


def config(dados, guild_id):

    return dados.setdefault(str(guild_id), {"canal_pedidos": None, "canal_publicar": None, "pedidos": {}})


class Parcerias(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        self.bot.add_view(PainelPedirParceriaView(self))

        for guild_id_str, conf in self.dados.items():

            for pedido_id, pedido in conf.get("pedidos", {}).items():

                if pedido.get("status") == "pendente":
                    self.bot.add_view(VotoParceriaView(self, guild_id_str, pedido_id))


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="parcerias-canal-pedidos")
    @commands.has_permissions(administrator=True)
    async def parcerias_canal_pedidos(self, ctx, canal: discord.TextChannel):

        conf = config(self.dados, ctx.guild.id)
        conf["canal_pedidos"] = canal.id
        self.salvar()

        await ctx.send(embed=embed_padrao("✅ Canal definido", f"Painel de pedir parceria deve ser enviado em {canal.mention} com `!parcerias-painel`.", discord.Color.green()))


    @commands.hybrid_command(name="parcerias-canal-publicar")
    @commands.has_permissions(administrator=True)
    async def parcerias_canal_publicar(self, ctx, canal: discord.TextChannel):

        conf = config(self.dados, ctx.guild.id)
        conf["canal_publicar"] = canal.id
        self.salvar()

        await ctx.send(embed=embed_padrao("✅ Canal definido", f"Parcerias aprovadas serão publicadas em {canal.mention}.", discord.Color.green()))


    @commands.hybrid_command(name="parcerias-painel")
    @commands.has_permissions(administrator=True)
    async def parcerias_painel(self, ctx):

        await ctx.send(
            embed=embed_padrao(
                "🤝 Central de Parcerias",
                "Quer fazer parceria com a gente? Clique no botão abaixo e preencha as informações do seu servidor!",
                discord.Color.blurple()
            ),
            view=PainelPedirParceriaView(self)
        )


async def setup(bot):

    await bot.add_cog(
        Parcerias(bot)
    )


# ==========================================================
# PEDIR PARCERIA
# ==========================================================

class ModalPedirParceria(Modal):

    def __init__(self, cog):

        super().__init__(title="🤝 Pedido de Parceria")

        self.cog = cog

        self.nome_servidor = TextInput(label="Nome do seu servidor", max_length=100)
        self.convite = TextInput(label="Link de convite (discord.gg/...)", max_length=100)
        self.descricao = TextInput(label="Descrição do servidor", style=discord.TextStyle.paragraph, max_length=500)
        self.membros = TextInput(label="Quantos membros vocês têm?", max_length=20)

        self.add_item(self.nome_servidor)
        self.add_item(self.convite)
        self.add_item(self.descricao)
        self.add_item(self.membros)


    async def on_submit(self, interaction: discord.Interaction):

        conf = config(self.cog.dados, interaction.guild.id)

        canal_pedidos = interaction.guild.get_channel(conf.get("canal_pedidos")) if conf.get("canal_pedidos") else interaction.channel

        pedido_id = str(random.randint(1000, 9999))

        while pedido_id in conf["pedidos"]:
            pedido_id = str(random.randint(1000, 9999))

        pedido = {
            "id": pedido_id,
            "nome_servidor": self.nome_servidor.value,
            "convite": self.convite.value,
            "descricao": self.descricao.value,
            "membros": self.membros.value,
            "autor_id": interaction.user.id,
            "status": "pendente"
        }

        conf["pedidos"][pedido_id] = pedido

        self.cog.salvar()

        embed = discord.Embed(
            title=f"🤝 Pedido de Parceria — {pedido['nome_servidor']}",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="👤 Enviado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="👥 Membros", value=pedido["membros"], inline=True)
        embed.add_field(name="🔗 Convite", value=pedido["convite"], inline=False)
        embed.add_field(name="📋 Descrição", value=pedido["descricao"], inline=False)

        try:
            await canal_pedidos.send(embed=embed, view=VotoParceriaView(self.cog, str(interaction.guild.id), pedido_id))
        except Exception:
            pass

        await interaction.response.send_message(
            embed=embed_padrao("✅ Pedido enviado!", "A equipe vai avaliar seu pedido de parceria em breve.", discord.Color.green()),
            ephemeral=True
        )


class PainelPedirParceriaView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        self.pedir.custom_id = "parcerias_pedir_botao"


    @discord.ui.button(label="🤝 Pedir Parceria", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(ModalPedirParceria(self.cog))


# ==========================================================
# APROVAR / RECUSAR
# ==========================================================

class VotoParceriaView(View):

    def __init__(self, cog, guild_id_str, pedido_id):

        super().__init__(timeout=None)

        self.cog = cog
        self.guild_id_str = guild_id_str
        self.pedido_id = pedido_id

        self.aprovar.custom_id = f"parceria_aprovar_{guild_id_str}_{pedido_id}"
        self.recusar.custom_id = f"parceria_recusar_{guild_id_str}_{pedido_id}"


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO VotoParceriaView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("==================================================")
        msg = f"❌ Erro:\n```{type(error).__name__}: {error}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


    def _pedido(self):

        conf = self.cog.dados.get(self.guild_id_str, {})

        return conf.get("pedidos", {}).get(self.pedido_id)


    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success)
    async def aprovar(self, interaction: discord.Interaction, button: Button):

        pedido = self._pedido()

        if pedido is None or pedido["status"] != "pendente":
            return await interaction.response.edit_message(content="⚠️ Esse pedido já foi processado.", embed=None, view=None)

        pedido["status"] = "aprovado"
        self.cog.salvar()

        conf = config(self.cog.dados, interaction.guild.id)

        canal_publicar = interaction.guild.get_channel(conf.get("canal_publicar")) if conf.get("canal_publicar") else interaction.channel

        embed = discord.Embed(
            title=f"🤝 Nova Parceria — {pedido['nome_servidor']}",
            description=pedido["descricao"],
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="👥 Membros", value=pedido["membros"], inline=True)
        embed.add_field(name="🔗 Convite", value=pedido["convite"], inline=False)

        try:
            await canal_publicar.send(embed=embed)
        except Exception:
            pass

        await interaction.response.edit_message(
            embed=embed_padrao("✅ Parceria aprovada", f"**{pedido['nome_servidor']}** foi publicada.", discord.Color.green()),
            view=None
        )

        try:
            autor = await interaction.client.fetch_user(pedido["autor_id"])
            await autor.send(embed=embed_padrao("✅ Parceria aprovada!", f"Sua parceria com **{interaction.guild.name}** foi aprovada.", discord.Color.green()))
        except Exception:
            pass


    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: Button):

        pedido = self._pedido()

        if pedido is None or pedido["status"] != "pendente":
            return await interaction.response.edit_message(content="⚠️ Esse pedido já foi processado.", embed=None, view=None)

        pedido["status"] = "recusado"
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=embed_padrao("❌ Parceria recusada", f"Pedido de **{pedido['nome_servidor']}** recusado.", discord.Color.red()),
            view=None
        )

        try:
            autor = await interaction.client.fetch_user(pedido["autor_id"])
            await autor.send(embed=embed_padrao("❌ Parceria recusada", f"Seu pedido de parceria com **{interaction.guild.name}** não foi aprovado.", discord.Color.red()))
        except Exception:
            pass
