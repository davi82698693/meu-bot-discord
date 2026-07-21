import discord
import re
import os
import json
import tempfile
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from discord.ext import commands
from discord.ui import View
from .logs import obter_canal_log

logger = logging.getLogger(__name__)

# ============================================
# PERSISTÊNCIA DO WARN
# ============================================
DATA_DIR = (
    os.getenv("MODERATION_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)
os.makedirs(DATA_DIR, exist_ok=True)
WARNS_FILE = os.path.join(DATA_DIR, "warnings.json")


def carregar_warns() -> Dict[str, Any]:
    if not os.path.exists(WARNS_FILE):
        return {}
    try:
        with open(WARNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.exception("Arquivo warnings.json inválido, retornando dict vazio.")
        return {}
    except Exception:
        logger.exception("Erro ao carregar warnings.json, retornando dict vazio.")
        return {}


def salvar_warns(dados: Dict[str, Any]) -> None:
    try:
        # escrita atômica: grava em arquivo temporário e substitui
        dirpath = os.path.dirname(WARNS_FILE)
        fd, tmp_path = tempfile.mkstemp(prefix="warnings-", dir=dirpath, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, WARNS_FILE)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
    except Exception:
        logger.exception("⚠️ Erro ao salvar warnings.json")


# ============================================
# PARSER DE TEMPO FLEXÍVEL
# ============================================
def parsear_tempo(texto: str) -> Optional[int]:
    """
    Converte strings de tempo flexíveis pra minutos.
    Aceita: 1d, 1 dia, 10min, 10 minutos, 2hrs, 2 horas, 1hr, 1 hora, etc.
    Retorna minutos ou None se inválido.
    """
    if not texto:
        return None
    texto = texto.strip().lower()
    texto = re.sub(r"\s+", " ", texto)

    # Captura padrões mais comuns
    dias = re.search(r"(\d+)\s*(?:d|dia|dias)", texto)
    horas = re.search(r"(\d+)\s*(?:h|hr|hrs|hora|horas)", texto)
    minutos = re.search(r"(\d+)\s*(?:m|min|minuto|minutos|mins)", texto)

    total_minutos = 0
    if dias:
        total_minutos += int(dias.group(1)) * 24 * 60
    if horas:
        total_minutos += int(horas.group(1)) * 60
    if minutos:
        total_minutos += int(minutos.group(1))

    return total_minutos if total_minutos > 0 else None


# ============================================
# COG
# ============================================
class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = carregar_warns()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("🛡️ Sistema de moderação carregado.")

    # ======================================
    # SETUP
    # ======================================
    @commands.hybrid_command(name="setup-moderacao")
    @commands.has_permissions(manage_guild=True)
    async def setup_moderacao(self, ctx: commands.Context):
        guild = ctx.guild
        criado_algo = False

        # Muted
        muted = discord.utils.get(guild.roles, name="🔇 Muted")
        if muted is None:
            muted = await guild.create_role(name="🔇 Muted", reason="Sistema de moderação")
            criado_algo = True

        # aplica permissões do mute nos canais (tentativa segura)
        for channel in guild.channels:
            try:
                await channel.set_permissions(
                    muted,
                    send_messages=False,
                    speak=False,
                    add_reactions=False,
                )
            except Exception:
                # não travar se algum canal não aceitar
                logger.debug("Não foi possível ajustar permissões em canal %s", channel.name)

        # Staff
        staff = discord.utils.get(guild.roles, name="🛡️ Staff")
        if staff is None:
            await guild.create_role(name="🛡️ Staff", reason="Sistema de moderação")
            criado_algo = True

        # Logs
        logs = discord.utils.get(guild.text_channels, name="📋・logs-moderação")
        if logs is None:
            await guild.create_text_channel("📋・logs-moderação", reason="Sistema de logs")
            criado_algo = True

        await ctx.send(
            embed=self.embed(
                "✅ Setup de Moderação" if criado_algo else "ℹ️ Já configurado",
                "Estrutura de moderação criada/verificada com sucesso."
                if criado_algo
                else "Tudo que faltava já existia, nada novo foi criado.",
                discord.Color.green(),
            )
        )

    # ======================================
    # EMBEDS
    # ======================================
    def embed(self, title: str, description: str, color: discord.Color = discord.Color.red()) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="🛡️ Sistema de Moderação")
        return embed

    # ======================================
    # LOGS
    # ======================================
    async def enviar_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        try:
            canal = obter_canal_log(self.bot, guild, "moderacao")
        except Exception:
            canal = None
            logger.exception("Erro ao obter canal de logs via obter_canal_log")

        if canal is None:
            canal = discord.utils.get(guild.text_channels, name="📋・logs-moderação")

        if canal:
            try:
                await canal.send(embed=embed)
            except Exception:
                logger.exception("Erro ao enviar embed para canal de logs")

    # ======================================
    # AUX: checar se o bot pode agir sobre o membro
    # ======================================
    def bot_pode_atuar(self, guild: discord.Guild, member: discord.Member) -> bool:
        me = guild.me
        if me is None:
            return False
        return me.top_role > member.top_role

    # ======================================
    # BAN
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "Não informado"):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário para banir."))

        if member == ctx.author:
            return await ctx.send(embed=self.embed("❌ Erro", "Você não pode se banir."))

        if not self.bot_pode_atuar(ctx.guild, member):
            return await ctx.send(embed=self.embed("❌ Erro", "Não consigo banir esse usuário (meu cargo está abaixo)."))

        if not ctx.guild.me.guild_permissions.ban_members:
            return await ctx.send(embed=self.embed("❌ Erro", "Não tenho permissão para banir membros."))

        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Erro", "Falha ao banir: permissão negada."))
        except Exception:
            logger.exception("Erro ao banir usuário %s", member.id)
            return await ctx.send(embed=self.embed("❌ Erro", "Ocorreu um erro ao tentar banir o usuário."))

        embed = self.embed(
            "🔨 Usuário Banido",
            f"👤 **Usuário:** {member.mention}\n🛡️ **Moderador:** {ctx.author.mention}\n📝 **Motivo:** {reason}\n🆔 **ID:** {member.id}",
            discord.Color.dark_red(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # UNBAN
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int = None, *, reason: str = "Não informado"):
        if user_id is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa informar o ID do usuário para desbanir."))

        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            return await ctx.send(embed=self.embed("❌ Erro", "Esse usuário não está banido ou o ID está incorreto."))
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Erro", "Falha ao desbanir: permissão negada."))
        except Exception:
            logger.exception("Erro ao desbanir usuário %s", user_id)
            return await ctx.send(embed=self.embed("❌ Erro", "Ocorreu um erro ao tentar desbanir o usuário."))

        embed = self.embed(
            "🔓 Usuário Desbanido",
            f"👤 **Usuário:** {user.mention}\n🛡️ **Moderador:** {ctx.author.mention}\n📝 **Motivo:** {reason}\n🆔 **ID:** {user.id}",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # KICK
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "Não informado"):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário para expulsar."))

        if not self.bot_pode_atuar(ctx.guild, member):
            return await ctx.send(embed=self.embed("❌ Erro", "Não consigo expulsar esse usuário (meu cargo está abaixo)."))

        if not ctx.guild.me.guild_permissions.kick_members:
            return await ctx.send(embed=self.embed("❌ Erro", "Não tenho permissão para expulsar membros."))

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Erro", "Falha ao expulsar: permissão negada."))
        except Exception:
            logger.exception("Erro ao expulsar usuário %s", getattr(member, "id", None))
            return await ctx.send(embed=self.embed("❌ Erro", "Ocorreu um erro ao tentar expulsar o usuário."))

        embed = self.embed(
            "👢 Usuário Expulso",
            f"👤 **Usuário:** {member.mention}\n🛡️ **Moderador:** {ctx.author.mention}\n📝 **Motivo:** {reason}",
            discord.Color.orange(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # MUTE (com tempo flexível)
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member = None, tempo: str = "10min", *, reason: str = "Não informado"):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário para mutar."))

        if member == ctx.author:
            return await ctx.send(embed=self.embed("❌ Erro", "Você não pode se mutar."))

        if not self.bot_pode_atuar(ctx.guild, member) and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=self.embed("❌ Erro", "Você não pode mutar alguém com cargo igual ou superior."))

        duracao_minutos = parsear_tempo(tempo)
        if duracao_minutos is None:
            return await ctx.send(embed=self.embed("❌ Tempo inválido", "Use formatos como: `10min`, `1hr`, `2 horas`, `1d`, `1 dia`, etc."))

        if duracao_minutos <= 0 or duracao_minutos > 40320:
            return await ctx.send(embed=self.embed("❌ Duração inválida", "A duração precisa ser entre 1 minuto e 40320 minutos (28 dias)."))

        if not ctx.guild.me.guild_permissions.moderate_members:
            return await ctx.send(embed=self.embed("❌ Erro", "Não tenho permissão para silenciar membros."))

        try:
            until = discord.utils.utcnow() + timedelta(minutes=duracao_minutos)
            await member.edit(timed_out_until=until, reason=reason)
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Sem permissão", "Não consegui silenciar esse usuário — confira se meu cargo está acima do cargo dele."))
        except Exception:
            logger.exception("Erro ao mutar usuário %s", member.id)
            return await ctx.send(embed=self.embed("❌ Erro", "Ocorreu um erro ao tentar silenciar o usuário."))

        # Formatar tempo pra exibição
        display_tempo = tempo
        if duracao_minutos % (24 * 60) == 0:
            display_tempo = f"{duracao_minutos // (24 * 60)} dia(s)"
        elif duracao_minutos % 60 == 0:
            display_tempo = f"{duracao_minutos // 60} hora(s)"
        else:
            display_tempo = f"{duracao_minutos} minuto(s)"

        embed = self.embed(
            "🔇 Usuário Mutado",
            f"👤 **Usuário:** {member.mention}\n⏱️ **Duração:** {display_tempo}\n🛡️ **Moderador:** {ctx.author.mention}\n📝 **Motivo:** {reason}",
            discord.Color.gold(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # UNMUTE
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member = None):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário."))

        if getattr(member, "timed_out_until", None) is None:
            return await ctx.send(embed=self.embed("⚠️ Aviso", f"{member.mention} não está silenciado no momento.", discord.Color.orange()))

        try:
            await member.edit(timed_out_until=None, reason=f"Desmutado por {ctx.author}")
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Sem permissão", "Não consegui desmutar esse usuário — confira minhas permissões."))
        except Exception:
            logger.exception("Erro ao desmutar usuário %s", member.id)
            return await ctx.send(embed=self.embed("❌ Erro", "Ocorreu um erro ao tentar desmutar o usuário."))

        embed = self.embed(
            "🔊 Usuário Desmutado",
            f"👤 **Usuário:** {member.mention}\n🛡️ **Moderador:** {ctx.author.mention}",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # WARN (com persistência)
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "Não informado"):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário."))

        user_id = str(member.id)
        if user_id not in self.warnings:
            self.warnings[user_id] = []

        self.warnings[user_id].append({
            "motivo": reason,
            "moderador": ctx.author.name,
            "moderador_id": ctx.author.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        salvar_warns(self.warnings)
        total_warns = len(self.warnings[user_id])

        embed = self.embed(
            "⚠️ Advertência Aplicada",
            f"👤 **Usuário:** {member.mention}\n🛡️ **Moderador:** {ctx.author.mention}\n📝 **Motivo:** {reason}\n📌 **Total de warns:** {total_warns}",
            discord.Color.orange(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # VER WARNS
    # ======================================
    @commands.hybrid_command(name="warns")
    async def warns(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        user_id = str(member.id)
        lista = self.warnings.get(user_id, [])

        if not lista:
            return await ctx.send(embed=self.embed("✅ Sem Warns", f"{member.mention} não possui advertências.", discord.Color.green()))

        texto = ""
        for numero, warn in enumerate(lista, start=1):
            texto += f"**{numero}.** {warn.get('motivo', 'Sem motivo')}\n"

        embed = self.embed("⚠️ Histórico de Warns", f"👤 **Usuário:** {member.mention}\n{texto}", discord.Color.orange())
        await ctx.send(embed=embed)

    # ======================================
    # REMOVER WARN
    # ======================================
    @commands.hybrid_command(name="delwarn", aliases=["removerwarn"])
    @commands.has_permissions(manage_messages=True)
    async def delwarn(self, ctx: commands.Context, member: discord.Member = None, numero: int = None):
        if member is None or numero is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Use assim: `!delwarn @usuário <número>`\nVeja os números com `!warns @usuário`."))

        user_id = str(member.id)
        lista = self.warnings.get(user_id, [])

        if not lista or numero < 1 or numero > len(lista):
            return await ctx.send(embed=self.embed("❌ Erro", f"Não existe o warn número {numero} para {member.mention}."))

        removido = lista.pop(numero - 1)
        salvar_warns(self.warnings)

        embed = self.embed(
            "🗑️ Warn Removido",
            f"👤 **Usuário:** {member.mention}\n📝 **Motivo removido:** {removido.get('motivo')}\n🛡️ **Responsável:** {ctx.author.mention}\n📌 **Warns restantes:** {len(lista)}",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # CLEAR
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, quantidade: int = 5):
        try:
            await ctx.channel.purge(limit=quantidade + 1)
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Erro", "Não tenho permissão para apagar mensagens aqui."))
        except Exception:
            logger.exception("Erro ao limpar mensagens")
            return await ctx.send(embed=self.embed("❌ Erro", "Não foi possível apagar mensagens."))

        embed = self.embed("🧹 Chat Limpo", f"Foram apagadas **{quantidade} mensagens**.", discord.Color.blue())
        mensagem = await ctx.send(embed=embed)
        await mensagem.delete(delay=5)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # LOCK
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        try:
            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        except Exception:
            logger.exception("Erro ao bloquear canal")
            return await ctx.send(embed=self.embed("❌ Erro", "Não foi possível bloquear o canal."))

        embed = self.embed(
            "🔒 Canal Bloqueado",
            f"📌 **Canal:** {ctx.channel.mention}\n🛡️ **Responsável:** {ctx.author.mention}\nO canal foi bloqueado (mensagens e tópicos).",
            discord.Color.red(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # UNLOCK
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        try:
            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                send_messages=True,
                send_messages_in_threads=True,
                create_public_threads=True,
                create_private_threads=True,
            )
        except Exception:
            logger.exception("Erro ao desbloquear canal")
            return await ctx.send(embed=self.embed("❌ Erro", "Não foi possível desbloquear o canal."))

        embed = self.embed(
            "🔓 Canal Liberado",
            f"📌 **Canal:** {ctx.channel.mention}\n🛡️ **Responsável:** {ctx.author.mention}\nO canal foi desbloqueado (mensagens e tópicos).",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # SLOWMODE
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, segundos: int = 5):
        if segundos < 0 or segundos > 21600:
            return await ctx.send(embed=self.embed("❌ Erro", "Use um valor entre 0 e 21600 segundos."))

        try:
            await ctx.channel.edit(slowmode_delay=segundos)
        except Exception:
            logger.exception("Erro ao alterar slowmode")
            return await ctx.send(embed=self.embed("❌ Erro", "Não foi possível alterar o slowmode."))

        embed = self.embed(
            "🐢 Slowmode Alterado",
            f"📌 **Canal:** {ctx.channel.mention}\n⏱️ **Tempo:** {segundos} segundos\n🛡️ **Responsável:** {ctx.author.mention}",
            discord.Color.blue(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # NICK
    # ======================================
    @commands.hybrid_command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member = None, *, nome: Optional[str] = None):
        if member is None:
            return await ctx.send(embed=self.embed("❌ Erro", "Você precisa marcar um usuário."))

        try:
            await member.edit(nick=nome)
        except discord.Forbidden:
            return await ctx.send(embed=self.embed("❌ Erro", "Não tenho permissão para alterar apelido deste usuário."))
        except Exception:
            logger.exception("Erro ao alterar apelido")
            return await ctx.send(embed=self.embed("❌ Erro", "Não foi possível alterar o apelido."))

        embed = self.embed(
            "✏️ Apelido Alterado",
            f"👤 **Usuário:** {member.mention}\n🆕 **Novo apelido:** {nome if nome else 'Removido'}\n🛡️ **Responsável:** {ctx.author.mention}",
            discord.Color.purple(),
        )
        await ctx.send(embed=embed)
        await self.enviar_log(ctx.guild, embed)

    # ======================================
    # TRATAMENTO DE ERROS
    # ======================================
    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(embed=self.embed("🚫 Sem Permissão", "Você não tem permissão para usar esse comando."))

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(embed=self.embed("❌ Argumento Faltando", f"Falta informar: `{error.param.name}`"))

        if isinstance(error, commands.MemberNotFound):
            return await ctx.send(embed=self.embed("❌ Usuário não encontrado", "Não encontrei esse membro no servidor."))

        # registra outros erros para debug e re-levanta
        logger.exception("Erro não tratado em comando")
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
