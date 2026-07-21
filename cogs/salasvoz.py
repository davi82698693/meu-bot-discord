import discord
import os
import json
from datetime import datetime, timezone
from discord.ext import commands
from discord.ui import View, Button, ChannelSelect

DATA_DIR = (
    os.getenv("SALASVOZ_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "salasvoz_data.json")

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
        print(f"⚠️ Erro ao salvar salasvoz_data.json: {e}")

def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):
    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="🔊 Salas de Voz")
    return embed

def config(dados, guild_id):
    return dados.setdefault(str(guild_id), {
        "canal_gatilho": None,
        "salas_criadas": {}
    })

def container_view(texto, source_view, accent_color=discord.Color.blurple()):
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

class SalasVoz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dados = carregar_dados()
    
    async def cog_load(self):
        self.bot.add_view(PainelSalasVozView(self))
    
    def salvar(self):
        salvar_dados(self.dados)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        conf = config(self.dados, member.guild.id)
        gatilho_id = conf.get("canal_gatilho")
        
        # Entrou no canal gatilho
        if gatilho_id and after.channel and after.channel.id == gatilho_id:
            categoria = after.channel.category
            try:
                nova_sala = await member.guild.create_voice_channel(
                    name=f"🔊 Sala de {member.display_name}",
                    category=categoria,
                    reason="Sala de voz temporária"
                )
                await nova_sala.set_permissions(
                    member,
                    manage_channels=True,
                    move_members=True,
                    reason="Dono da sala temporária"
                )
                await member.move_to(nova_sala, reason="Sala de voz temporária")
                conf["salas_criadas"][str(nova_sala.id)] = member.id
                self.salvar()
            except Exception as e:
                print(f"⚠️ Erro ao criar sala de voz temporária: {e}")
        
        # Saiu de um canal
        if before.channel and str(before.channel.id) in conf["salas_criadas"]:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Sala de voz temporária vazia")
                except Exception:
                    pass
                conf["salas_criadas"].pop(str(before.channel.id), None)
                self.salvar()
    
    @commands.hybrid_command(name="salasvoz-painel")
    @commands.has_permissions(administrator=True)
    async def salasvoz_painel(self, ctx):
        conf = config(self.dados, ctx.guild.id)
        canal_id = conf.get("canal_gatilho")
        canal = ctx.guild.get_channel(canal_id) if canal_id else None
        
        texto = (
            "## 🔊 Painel de Salas de Voz\n"
            "Escolha um canal de voz **gatilho**. Sempre que alguém entrar nele, "
            "uma sala nova é criada na hora só pra essa pessoa (que vira dona da sala), "
            "e some sozinha quando fica vazia.\n\n"
            f"**Canal gatilho atual:** {canal.mention if canal else '`Não definido`'}"
        )
        
        await ctx.send(view=container_view(texto, PainelSalasVozView(self)))
    
    async def cog_command_error(self, ctx, error):
        print(f"Erro no comando {ctx.command}: {error}")
        await ctx.send(
            embed=embed_padrao(
                "❌ Erro",
                f"```{type(error).__name__}: {error}```",
                discord.Color.red()
            )
        )

class SelecionarCanalGatilho(ChannelSelect):
    def __init__(self, cog):
        self.cog = cog
        super().__init__(
            placeholder="Escolha o canal de voz gatilho",
            channel_types=[discord.ChannelType.voice],
            row=0,
            custom_id="salasvoz_gatilho_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 Você precisa ser Administrador para usar isso.",
                ephemeral=True
            )
        
        canal_selecionado = self.values[0]
        canal = interaction.guild.get_channel(canal_selecionado.id)
        
        if canal is None:
            canal = canal_selecionado.resolve()
        if canal is None:
            canal = await interaction.guild.fetch_channel(canal_selecionado.id)
        
        conf = config(self.cog.dados, interaction.guild.id)
        conf["canal_gatilho"] = canal.id
        self.cog.salvar()
        
        texto = (
            "## 🔊 Painel de Salas de Voz\n"
            "Escolha um canal de voz **gatilho**. Sempre que alguém entrar nele, "
            "uma sala nova é criada na hora só pra essa pessoa (que vira dona da sala), "
            "e some sozinha quando fica vazia.\n\n"
            f"**Canal gatilho atual:** {canal.mention}"
        )
        
        await interaction.response.edit_message(
            view=container_view(texto, PainelSalasVozView(self.cog))
        )

class PainelSalasVozView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(SelecionarCanalGatilho(cog))
    
    async def interaction_check(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "🚫 Você precisa ser Administrador para usar isso.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_error(self, interaction, error, item):
        import traceback
        print("========== ERRO NO PainelSalasVozView ==========")
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

async def setup(bot):
    await bot.add_cog(SalasVoz(bot))
