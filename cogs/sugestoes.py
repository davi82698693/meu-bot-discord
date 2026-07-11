import discord
import os
import json
import random

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput


DATA_DIR = (
    os.getenv("SUGESTOES_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "sugestoes_data.json")

NOMES_CANAL_SUGESTOES = ["sugestões", "sugestoes", "suggestions"]


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"sugestoes": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("sugestoes", {})
            return dados
    except Exception:
        return {"sugestoes": {}}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar sugestoes_data.json: {e}")


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="💡 Sugestões")

    return embed


def encontrar_canal_sugestoes(guild):

    for canal in guild.text_channels:

        nome = canal.name.lower()

        for alvo in NOMES_CANAL_SUGESTOES:

            if alvo in nome:
                return canal

    return None


def montar_embed_sugestao(sugestao, status="🕐 Em análise", cor=discord.Color.gold()):

    embed = discord.Embed(
        title=f"💡 {sugestao['titulo']}",
        description=sugestao["descricao"],
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(name="👤 Sugerido por", value=f"<@{sugestao['autor_id']}>", inline=True)
    embed.add_field(name="📌 Status", value=status, inline=True)

    embed.set_footer(text=f"ID: {sugestao['id']}")

    return embed


# ==========================================================
# COG
# ==========================================================

class Sugestoes(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()


    async def cog_load(self):

        self.bot.add_view(PainelSugerirView(self))

        for sid, sugestao in list(self.dados["sugestoes"].items()):

            if sugestao.get("status") == "pendente":
                self.bot.add_view(VotoStaffView(self, sid))


    def salvar(self):

        salvar_dados(self.dados)


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.command(name="sugestoes-painel")
    @commands.has_permissions(administrator=True)
    async def sugestoes_painel(self, ctx):

        await ctx.send(
            embed=embed_padrao(
                "💡 Central de Sugestões",
                "Tem uma ideia pra melhorar o servidor? Clique no botão abaixo!",
                discord.Color.gold()
            ),
            view=PainelSugerirView(self)
        )


    @commands.command(name="sugestoes-lista")
    @commands.has_permissions(administrator=True)
    async def sugestoes_lista(self, ctx):

        pendentes = {sid: s for sid, s in self.dados["sugestoes"].items() if s.get("status") == "pendente"}

        if not pendentes:
            return await ctx.send(embed=embed_padrao("💡 Sugestões pendentes", "Nenhuma sugestão pendente.", discord.Color.orange()))

        texto = "\n".join(f"`{sid}` — {s['titulo']} (por <@{s['autor_id']}>)" for sid, s in pendentes.items())

        await ctx.send(embed=embed_padrao("💡 Sugestões pendentes", texto, discord.Color.gold()))


async def setup(bot):

    await bot.add_cog(
        Sugestoes(bot)
    )


# ==========================================================
# BOTÃO "SUGERIR"
# ==========================================================

class ModalSugestao(Modal):

    def __init__(self, cog):

        super().__init__(title="💡 Nova Sugestão")

        self.cog = cog

        self.titulo_campo = TextInput(
            label="Título da sugestão",
            max_length=100
        )

        self.descricao_campo = TextInput(
            label="Explique sua ideia",
            style=discord.TextStyle.paragraph,
            max_length=1000
        )

        self.add_item(self.titulo_campo)
        self.add_item(self.descricao_campo)


    async def on_submit(self, interaction: discord.Interaction):

        sid = str(random.randint(1000, 9999))

        while sid in self.cog.dados["sugestoes"]:
            sid = str(random.randint(1000, 9999))

        sugestao = {
            "id": sid,
            "titulo": self.titulo_campo.value,
            "descricao": self.descricao_campo.value,
            "autor_id": interaction.user.id,
            "status": "pendente",
            "guild_id": interaction.guild.id
        }

        canal = encontrar_canal_sugestoes(interaction.guild) or interaction.channel

        mensagem = await canal.send(embed=montar_embed_sugestao(sugestao))

        sugestao["canal_id"] = canal.id
        sugestao["mensagem_id"] = mensagem.id

        self.cog.dados["sugestoes"][sid] = sugestao
        self.cog.salvar()

        await interaction.response.send_message(
            embed=embed_padrao("✅ Sugestão enviada!", f"Sua sugestão foi postada em {canal.mention}.", discord.Color.green()),
            ephemeral=True
        )

        try:

            topico = await canal.create_thread(
                name=f"💡 Sugestão #{sid}",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
                reason="Análise de sugestão (apenas Administradores)"
            )

            sugestao["thread_id"] = topico.id
            self.cog.salvar()

            await topico.send(
                embed=montar_embed_sugestao(sugestao).add_field(
                    name="🔗 Mensagem pública", value=f"[Clique aqui]({mensagem.jump_url})", inline=False
                ),
                view=VotoStaffView(self.cog, sid)
            )

        except discord.Forbidden:

            print(f"⚠️ SEM PERMISSÃO para criar tópico privado (sugestão {sid}). Faltam as permissões 'Criar Tópicos Privados' / 'Enviar Mensagens em Tópicos' pro bot nesse canal.")

            await avisar_falha_topico(interaction, sugestao)

        except Exception as e:
            print(f"⚠️ Não consegui criar o tópico privado da sugestão {sid}: {e}")
            await avisar_falha_topico(interaction, sugestao)


async def avisar_falha_topico(interaction, sugestao):
    """
    Plano B: se não der pra criar o tópico privado (geralmente falta de
    permissão), manda o card de aprovação num canal alternativo e avisa
    quem configurou, pra corrigir a permissão do bot.
    """

    canal_alternativo = None

    for c in interaction.guild.text_channels:
        nome = c.name.lower()
        if "staff" in nome or "-staf" in nome or "logs" in nome:
            canal_alternativo = c
            break

    if canal_alternativo is None:
        canal_alternativo = interaction.channel

    try:

        await canal_alternativo.send(
            embed=embed_padrao(
                "⚠️ Tópico privado não pôde ser criado",
                "O bot não tem permissão de **Criar Tópicos Privados** / **Enviar Mensagens em Tópicos** "
                "nesse canal. Dando essa permissão pro cargo do bot nas configurações do servidor, "
                "isso passa a funcionar direitinho. Por enquanto, aprove por aqui:",
                discord.Color.orange()
            )
        )

        await canal_alternativo.send(
            embed=montar_embed_sugestao(sugestao),
            view=VotoStaffView(interaction.client.get_cog("Sugestoes"), sugestao["id"])
        )

    except Exception as e:
        print(f"⚠️ Plano B também falhou: {e}")


class PainelSugerirView(View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog

        self.sugerir.custom_id = "painel_sugerir_botao"


    @discord.ui.button(label="💡 Sugerir algo", style=discord.ButtonStyle.primary)
    async def sugerir(self, interaction: discord.Interaction, button: Button):

        await interaction.response.send_modal(ModalSugestao(self.cog))


# ==========================================================
# BOTÕES DE APROVAÇÃO DA STAFF
# ==========================================================

class VotoStaffView(View):

    def __init__(self, cog, sid):

        super().__init__(timeout=None)

        self.cog = cog
        self.sid = sid

        self.aprovar.custom_id = f"sugestao_aprovar_{sid}"
        self.recusar.custom_id = f"sugestao_recusar_{sid}"


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Só Administradores podem avaliar sugestões.", ephemeral=True)
            return False

        return True


    async def _finalizar(self, interaction, novo_status, status_texto, cor):

        sugestao = self.cog.dados["sugestoes"].get(self.sid)

        if sugestao is None:
            return await interaction.response.send_message("❌ Sugestão não encontrada.", ephemeral=True)

        if sugestao["status"] != "pendente":
            return await interaction.response.edit_message(
                embed=embed_padrao("⚠️ Já processada", f"Essa sugestão já foi marcada como `{sugestao['status']}`.", discord.Color.orange()),
                view=None
            )

        sugestao["status"] = novo_status
        self.cog.salvar()

        canal = interaction.guild.get_channel(sugestao["canal_id"])

        if canal:

            try:
                msg_original = await canal.fetch_message(sugestao["mensagem_id"])
                await msg_original.edit(embed=montar_embed_sugestao(sugestao, status_texto, cor))
            except Exception:
                pass

        await interaction.response.edit_message(
            embed=embed_padrao(f"{status_texto}", f"Sugestão `{self.sid}` avaliada por {interaction.user.mention}.", cor),
            view=None
        )

        try:
            autor = await interaction.client.fetch_user(sugestao["autor_id"])
            await autor.send(embed=embed_padrao(f"{status_texto}", f"Sua sugestão **{sugestao['titulo']}** foi avaliada!", cor))
        except Exception:
            pass

        try:
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.edit(archived=True, locked=True)
        except Exception:
            pass


    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success)
    async def aprovar(self, interaction: discord.Interaction, button: Button):

        await self._finalizar(interaction, "aprovada", "✅ Aprovada", discord.Color.green())


    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: Button):

        await self._finalizar(interaction, "recusada", "❌ Recusada", discord.Color.red())
    
