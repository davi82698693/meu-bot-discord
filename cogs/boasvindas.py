import discord
import os
import json

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Select, Button, ChannelSelect


DATA_DIR = (
    os.getenv("BOASVINDAS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "boasvindas_data.json")


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
        print(f"⚠️ Erro ao salvar boasvindas_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="👋 Boas-vindas")

    return embed


# ==========================================================
# TEMPLATE FIXO DE ENTRADA
# ==========================================================

def montar_embed_entrada(member: discord.Member):

    guild = member.guild

    embed = discord.Embed(
        color=discord.Color.from_rgb(87, 242, 135),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_author(
        name=f"✨ Novo membro em {guild.name}!",
        icon_url=guild.icon.url if guild.icon else None
    )

    embed.title = f"👋 Seja bem-vindo(a), {member.display_name}!"

    embed.description = (
        f"{member.mention} acabou de entrar no servidor!\n\n"
        f"Dá uma olhada nas regras e se sinta em casa. 🎉"
    )

    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="👥 Membro número",
        value=f"`#{guild.member_count}`",
        inline=True
    )

    embed.add_field(
        name="📅 Conta criada em",
        value=f"<t:{int(member.created_at.timestamp())}:D>",
        inline=True
    )

    if guild.banner:
        embed.set_image(url=guild.banner.url)

    embed.set_footer(
        text=f"{guild.name} • Bem-vindo(a)!",
        icon_url=guild.icon.url if guild.icon else None
    )

    return embed


# ==========================================================
# TEMPLATE FIXO DE SAÍDA
# ==========================================================

def montar_embed_saida(member: discord.Member):

    guild = member.guild

    embed = discord.Embed(
        color=discord.Color.from_rgb(237, 66, 69),
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_author(
        name=f"💨 Alguém saiu de {guild.name}",
        icon_url=guild.icon.url if guild.icon else None
    )

    embed.title = f"👋 Até mais, {member.display_name}."

    embed.description = "Esperamos te ver de novo algum dia. 💙"

    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="👥 Membros restantes",
        value=f"`{guild.member_count}`",
        inline=True
    )

    if member.joined_at:

        embed.add_field(
            name="📌 Estava no servidor desde",
            value=f"<t:{int(member.joined_at.timestamp())}:D>",
            inline=True
        )

    embed.set_footer(
        text=f"{guild.name}",
        icon_url=guild.icon.url if guild.icon else None
    )

    return embed


# ==========================================================
# COG
# ==========================================================

class BoasVindas(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    def salvar(self):

        salvar_dados(self.dados)


    def config(self, guild_id):

        return self.dados.setdefault(str(guild_id), {"ativo": True})


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        conf = self.config(member.guild.id)

        if not conf.get("ativo", True):
            return

        canal_id = conf.get("canal_entrada")

        if canal_id is None:
            return

        canal = member.guild.get_channel(canal_id)

        if canal is None:
            return

        try:
            await canal.send(embed=montar_embed_entrada(member))
        except Exception:
            pass


    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):

        conf = self.config(member.guild.id)

        if not conf.get("ativo", True):
            return

        canal_id = conf.get("canal_saida")

        if canal_id is None:
            return

        canal = member.guild.get_channel(canal_id)

        if canal is None:
            return

        try:
            await canal.send(embed=montar_embed_saida(member))
        except Exception:
            pass


    async def _checar_admin(self, ctx):

        return ctx.author.guild_permissions.administrator


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="boasvindas-painel")
    async def boasvindas_painel(self, ctx):

        if not await self._checar_admin(ctx):
            return await ctx.send(
                embed=embed_padrao("🚫 Sem permissão", "Você precisa ser Administrador para usar isso.", discord.Color.red())
            )

        conf = self.config(ctx.guild.id)

        await ctx.send(
            embed=gerar_embed_painel(ctx.guild, conf),
            view=PainelBoasVindasView(self)
        )


async def setup(bot):

    await bot.add_cog(
        BoasVindas(bot)
    )


# ==========================================================
# EMBED DO PAINEL DE CONFIGURAÇÃO
# ==========================================================

def gerar_embed_painel(guild, conf):

    canal_entrada = guild.get_channel(conf.get("canal_entrada")) if conf.get("canal_entrada") else None
    canal_saida = guild.get_channel(conf.get("canal_saida")) if conf.get("canal_saida") else None

    status = "🟢 Ativado" if conf.get("ativo", True) else "🔴 Desativado"

    embed = embed_padrao(
        "🛠️ Painel de Boas-vindas",
        "Configure abaixo os canais de entrada e saída. O visual das mensagens já vem pronto.",
        discord.Color.blurple()
    )

    embed.add_field(name="Status", value=status, inline=False)
    embed.add_field(name="👋 Canal de Boas-vindas", value=canal_entrada.mention if canal_entrada else "`Não definido`", inline=False)
    embed.add_field(name="🚪 Canal de Despedida", value=canal_saida.mention if canal_saida else "`Não definido`", inline=False)

    return embed


# ==========================================================
# PAINEL (dropdowns + botões)
# ==========================================================

class SelecionarCanalEntrada(ChannelSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(
            placeholder="Escolha o canal de BOAS-VINDAS",
            channel_types=[discord.ChannelType.text],
            row=0
        )


    async def callback(self, interaction: discord.Interaction):

        canal_selecionado = self.values[0]

        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)

        conf = self.cog.config(interaction.guild.id)
        conf["canal_entrada"] = canal.id
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=self.view
        )


class SelecionarCanalSaida(ChannelSelect):

    def __init__(self, cog):

        self.cog = cog

        super().__init__(
            placeholder="Escolha o canal de DESPEDIDA",
            channel_types=[discord.ChannelType.text],
            row=1
        )


    async def callback(self, interaction: discord.Interaction):

        canal_selecionado = self.values[0]

        canal = interaction.guild.get_channel(canal_selecionado.id)

        if canal is None:
            canal = canal_selecionado.resolve()

        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)

        conf = self.cog.config(interaction.guild.id)
        conf["canal_saida"] = canal.id
        self.cog.salvar()

        await interaction.response.edit_message(
            embed=gerar_embed_painel(interaction.guild, conf),
            view=self.view
        )


class PainelBoasVindasView(View):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog

        self.add_item(SelecionarCanalEntrada(cog))
        self.add_item(SelecionarCanalSaida(cog))


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelBoasVindasView ==========")
        traceback.print_exception(type(error), error, error.__traceback__)
        print("======================================================")
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

        conf = self.cog.config(interaction.guild.id)
        conf["ativo"] = True
        self.cog.salvar()

        await interaction.response.edit_message(embed=gerar_embed_painel(interaction.guild, conf), view=self)


    @discord.ui.button(label="🔴 Desativar", style=discord.ButtonStyle.danger, row=2)
    async def desativar(self, interaction: discord.Interaction, button: Button):

        conf = self.cog.config(interaction.guild.id)
        conf["ativo"] = False
        self.cog.salvar()

        await interaction.response.edit_message(embed=gerar_embed_painel(interaction.guild, conf), view=self)


    @discord.ui.button(label="🧪 Testar Boas-vindas", style=discord.ButtonStyle.primary, row=3)
    async def testar_entrada(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(embed=montar_embed_entrada(interaction.user), ephemeral=True)


    @discord.ui.button(label="🧪 Testar Despedida", style=discord.ButtonStyle.secondary, row=3)
    async def testar_saida(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_message(embed=montar_embed_saida(interaction.user), ephemeral=True)
