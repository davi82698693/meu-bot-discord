import discord
import re
import os
import json
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from discord.ui import View
from .logs import obter_canal_log

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

def carregar_warns():
 if not os.path.exists(WARNS_FILE):
 return {}
 try:
 with open(WARNS_FILE, "r", encoding="utf-8") as f:
 return json.load(f)
 except Exception:
 return {}

def salvar_warns(dados):
 try:
 with open(WARNS_FILE, "w", encoding="utf-8") as f:
 json.dump(dados, f, ensure_ascii=False, indent=2)
 except Exception as e:
 print(f"⚠️ Erro ao salvar warnings.json: {e}")

# ============================================
# PARSER DE TEMPO FLEXÍVEL
# ============================================
def parsear_tempo(texto: str) -> int:
 """
 Converte strings de tempo flexíveis pra minutos.
 Aceita: 1d, 1 dia, 10min, 10 minutos, 2hrs, 2 horas, 1hr, 1 hora, etc.
 Retorna minutos ou None se inválido.
 """
 texto = texto.strip().lower()
 
 # Remover espaços extras
 texto = re.sub(r'\s+', ' ', texto)
 
 # Expressões regulares
 dias = re.search(r'(\d+)\s*(?:d|dia|dias)', texto)
 horas = re.search(r'(\d+)\s*(?:h|hr|hrs|hora|horas)', texto)
 minutos = re.search(r'(\d+)\s*(?:min|minutos?)', texto)
 
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
 def __init__(self, bot):
 self.bot = bot
 self.warnings = carregar_warns()
 
 @commands.Cog.listener()
 async def on_ready(self):
 print("🛡️ Sistema de moderação carregado.")
 
 # ======================================
 # SETUP
 # ======================================
 
 @commands.hybrid_command(name="setup-moderacao")
 @commands.has_permissions(manage_guild=True)
 async def setup_moderacao(self, ctx):
 guild = ctx.guild
 criado_algo = False
 
 # Muted
 muted = discord.utils.get(guild.roles, name="🔇 Muted")
 if muted is None:
 muted = await guild.create_role(
 name="🔇 Muted",
 reason="Sistema de moderação"
 )
 for channel in guild.channels:
 try:
 await channel.set_permissions(
 muted,
 send_messages=False,
 speak=False,
 add_reactions=False
 )
 except:
 pass
 criado_algo = True
 
 # Staff
 staff = discord.utils.get(guild.roles, name="🛡️ Staff")
 if staff is None:
 await guild.create_role(
 name="🛡️ Staff",
 reason="Sistema de moderação"
 )
 criado_algo = True
 
 # Logs
 logs = discord.utils.get(guild.text_channels, name="📋・logs-moderação")
 if logs is None:
 await guild.create_text_channel(
 "📋・logs-moderação",
 reason="Sistema de logs"
 )
 criado_algo = True
 
 await ctx.send(
 embed=self.embed(
 "✅ Setup de Moderação" if criado_algo else "i️ Já configurado",
 "Estrutura de moderação criada/verificada com sucesso."
 if criado_algo
 else "Tudo que faltava já existia, nada novo foi criado.",
 discord.Color.green()
 )
 )
 
 # ======================================
 # EMBEDS
 # ======================================
 
 def embed(self, title, description, color=discord.Color.red()):
 embed = discord.Embed(
 title=title,
 description=description,
 color=color,
 timestamp=datetime.utcnow()
 )
 embed.set_footer(text="🛡️ Sistema de Moderação")
 return embed
 
 # ======================================
 # LOGS
 # ======================================
 
 async def enviar_log(self, guild, embed):
 canal = obter_canal_log(self.bot, guild, "moderacao")
 if canal is None:
 canal = discord.utils.get(
 guild.text_channels,
 name="📋・logs-moderação"
 )
 if canal:
 await canal.send(embed=embed)
 
 # ======================================
 # BAN
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(ban_members=True)
 async def ban(self, ctx, member: discord.Member = None, *, reason="Não informado"):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário para banir.")
 )
 
 if member == ctx.author:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você não pode se banir.")
 )
 
 if member.top_role >= ctx.author.top_role:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você não pode punir alguém com cargo igual ou superior.")
 )
 
 await member.ban(reason=reason)
 embed = self.embed(
 "🔨 Usuário Banido",
 f"""
👤 **Usuário:**
{member.mention}
🛡️ **Moderador:**
{ctx.author.mention}
📝 **Motivo:**
{reason}
🆔 **ID:**
{member.id}
""",
 discord.Color.dark_red()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # UNBAN
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(ban_members=True)
 async def unban(self, ctx, user_id: int = None, *, reason="Não informado"):
 if user_id is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa informar o ID do usuário para desbanir.")
 )
 
 try:
 user = await self.bot.fetch_user(user_id)
 await ctx.guild.unban(user, reason=reason)
 embed = self.embed(
 "🔓 Usuário Desbanido",
 f"""
👤 **Usuário:**
{user.mention}
🛡️ **Moderador:**
{ctx.author.mention}
📝 **Motivo:**
{reason}
🆔 **ID:**
{user.id}
""",
 discord.Color.green()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 except discord.NotFound:
 await ctx.send(
 embed=self.embed("❌ Erro", "Esse usuário não está banido ou o ID está incorreto.")
 )
 
 # ======================================
 # KICK
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(kick_members=True)
 async def kick(self, ctx, member: discord.Member = None, *, reason="Não informado"):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário para expulsar.")
 )
 
 if member.top_role >= ctx.author.top_role:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você não pode expulsar esse usuário.")
 )
 
 await member.kick(reason=reason)
 embed = self.embed(
 "👢 Usuário Expulso",
 f"""
👤 **Usuário:**
{member.mention}
🛡️ **Moderador:**
{ctx.author.mention}
📝 **Motivo:**
{reason}
""",
 discord.Color.orange()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # MUTE (com tempo flexível)
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(moderate_members=True)
 async def mute(self, ctx, member: discord.Member = None, tempo: str = "10min", *, reason="Não informado"):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário para mutar.")
 )
 
 if member == ctx.author:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você não pode se mutar.")
 )
 
 if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você não pode mutar alguém com cargo igual ou superior.")
 )
 
 # Parsear tempo
 duracao_minutos = parsear_tempo(tempo)
 if duracao_minutos is None:
 return await ctx.send(
 embed=self.embed(
 "❌ Tempo inválido",
 "Use formatos como: `10min`, `1hr`, `2 horas`, `1d`, `1 dia`, etc."
 )
 )
 
 if duracao_minutos <= 0 or duracao_minutos > 40320:
 return await ctx.send(
 embed=self.embed(
 "❌ Duração inválida",
 "A duração precisa ser entre 1 minuto e 40320 minutos (28 dias)."
 )
 )
 
 try:
 await member.timeout(
 discord.utils.utcnow() + timedelta(minutes=duracao_minutos),
 reason=reason
 )
 except discord.Forbidden:
 return await ctx.send(
 embed=self.embed(
 "❌ Sem permissão",
 "Não consegui silenciar esse usuário — confira se meu cargo está **acima** do cargo dele."
 )
 )
 
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
 f"""
👤 **Usuário:**
{member.mention}
⏱️ **Duração:**
{display_tempo}
🛡️ **Moderador:**
{ctx.author.mention}
📝 **Motivo:**
{reason}
""",
 discord.Color.gold()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # UNMUTE
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(moderate_members=True)
 async def unmute(self, ctx, member: discord.Member = None):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário.")
 )
 
 if member.timed_out_until is None:
 return await ctx.send(
 embed=self.embed(
 "⚠️ Aviso",
 f"{member.mention} não está silenciado no momento.",
 discord.Color.orange()
 )
 )
 
 try:
 await member.timeout(None, reason=f"Desmutado por {ctx.author}")
 except discord.Forbidden:
 return await ctx.send(
 embed=self.embed(
 "❌ Sem permissão",
 "Não consegui desmutar esse usuário — confira minhas permissões."
 )
 )
 
 embed = self.embed(
 "🔊 Usuário Desmutado",
 f"""
👤 **Usuário:**
{member.mention}
🛡️ **Moderador:**
{ctx.author.mention}
""",
 discord.Color.green()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # WARN (com persistência CORRIGIDO)
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_messages=True)
 async def warn(self, ctx, member: discord.Member = None, *, reason="Não informado"):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário.")
 )
 
 user_id = str(member.id)
 if user_id not in self.warnings:
 self.warnings[user_id] = []
 
 self.warnings[user_id].append({
 "motivo": reason,
 "moderador": ctx.author.name,
 "moderador_id": ctx.author.id,
 "timestamp": datetime.utcnow().isoformat()
 })
 
 salvar_warns(self.warnings)
 
 total_warns = len(self.warnings[user_id])
 
 embed = self.embed(
 "⚠️ Advertência Aplicada",
 f"""
👤 **Usuário:**
{member.mention}
🛡️ **Moderador:**
{ctx.author.mention}
📝 **Motivo:**
{reason}
📌 **Total de warns:**
{total_warns}
""",
 discord.Color.orange()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # VER WARNS
 # ======================================
 
 @commands.hybrid_command(name="warns")
 async def warns(self, ctx, member: discord.Member = None):
 member = member or ctx.author
 user_id = str(member.id)
 lista = self.warnings.get(user_id, [])
 
 if not lista:
 return await ctx.send(
 embed=self.embed(
 "✅ Sem Warns",
 f"{member.mention} não possui advertências.",
 discord.Color.green()
 )
 )
 
 texto = ""
 for numero, warn in enumerate(lista, start=1):
 texto += f"**{numero}.** {warn['motivo']}\n"
 
 embed = self.embed(
 "⚠️ Histórico de Warns",
 f"""
👤 **Usuário:**
{member.mention}
{texto}
""",
 discord.Color.orange()
 )
 await ctx.send(embed=embed)
 
 # ======================================
 # REMOVER WARN
 # ======================================
 
 @commands.hybrid_command(name="delwarn", aliases=["removerwarn"])
 @commands.has_permissions(manage_messages=True)
 async def delwarn(self, ctx, member: discord.Member = None, numero: int = None):
 if member is None or numero is None:
 return await ctx.send(
 embed=self.embed(
 "❌ Erro",
 "Use assim: `!delwarn @usuário <número>`\nVeja os números com `!warns @usuário`."
 )
 )
 
 user_id = str(member.id)
 lista = self.warnings.get(user_id, [])
 
 if not lista or numero < 1 or numero > len(lista):
 return await ctx.send(
 embed=self.embed(
 "❌ Erro",
 f"Não existe o warn número {numero} para {member.mention}."
 )
 )
 
 removido = lista.pop(numero - 1)
 salvar_warns(self.warnings)
 
 embed = self.embed(
 "🗑️ Warn Removido",
 f"""
👤 **Usuário:**
{member.mention}
📝 **Motivo removido:**
{removido['motivo']}
🛡️ **Responsável:**
{ctx.author.mention}
📌 **Warns restantes:**
{len(lista)}
""",
 discord.Color.green()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # CLEAR
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_messages=True)
 async def clear(self, ctx, quantidade: int = 5):
 await ctx.channel.purge(limit=quantidade + 1)
 embed = self.embed(
 "🧹 Chat Limpo",
 f"Foram apagadas **{quantidade} mensagens**.",
 discord.Color.blue()
 )
 mensagem = await ctx.send(embed=embed)
 await mensagem.delete(delay=5)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # LOCK
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_channels=True)
 async def lock(self, ctx):
 await ctx.channel.set_permissions(
 ctx.guild.default_role,
 send_messages=False,
 send_messages_in_threads=False,
 create_public_threads=False,
 create_private_threads=False
 )
 embed = self.embed(
 "🔒 Canal Bloqueado",
 f"""
📌 **Canal:**
{ctx.channel.mention}
🛡️ **Responsável:**
{ctx.author.mention}
O canal foi bloqueado (mensagens e tópicos).
""",
 discord.Color.red()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # UNLOCK
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_channels=True)
 async def unlock(self, ctx):
 await ctx.channel.set_permissions(
 ctx.guild.default_role,
 send_messages=True,
 send_messages_in_threads=True,
 create_public_threads=True,
 create_private_threads=True
 )
 embed = self.embed(
 "🔓 Canal Liberado",
 f"""
📌 **Canal:**
{ctx.channel.mention}
🛡️ **Responsável:**
{ctx.author.mention}
O canal foi desbloqueado (mensagens e tópicos).
""",
 discord.Color.green()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # SLOWMODE
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_channels=True)
 async def slowmode(self, ctx, segundos: int = 5):
 if segundos < 0 or segundos > 21600:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Use um valor entre 0 e 21600 segundos.")
 )
 
 await ctx.channel.edit(slowmode_delay=segundos)
 embed = self.embed(
 "🐢 Slowmode Alterado",
 f"""
📌 **Canal:**
{ctx.channel.mention}
⏱️ **Tempo:**
{segundos} segundos
🛡️ **Responsável:**
{ctx.author.mention}
""",
 discord.Color.blue()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # NICK
 # ======================================
 
 @commands.hybrid_command()
 @commands.has_permissions(manage_nicknames=True)
 async def nick(self, ctx, member: discord.Member = None, *, nome=None):
 if member is None:
 return await ctx.send(
 embed=self.embed("❌ Erro", "Você precisa marcar um usuário.")
 )
 
 await member.edit(nick=nome)
 embed = self.embed(
 "✏️ Apelido Alterado",
 f"""
👤 **Usuário:**
{member.mention}
🆕 **Novo apelido:**
{nome if nome else "Removido"}
🛡️ **Responsável:**
{ctx.author.mention}
""",
 discord.Color.purple()
 )
 await ctx.send(embed=embed)
 await self.enviar_log(ctx.guild, embed)
 
 # ======================================
 # TRATAMENTO DE ERROS
 # ======================================
 
 async def cog_command_error(self, ctx, error):
 if isinstance(error, commands.MissingPermissions):
 return await ctx.send(
 embed=self.embed(
 "🚫 Sem Permissão",
 "Você não tem permissão para usar esse comando."
 )
 )
 
 if isinstance(error, commands.MissingRequiredArgument):
 return await ctx.send(
 embed=self.embed(
 "❌ Argumento Faltando",
 f"Falta informar: `{error.param.name}`"
 )
 )
 
 if isinstance(error, commands.MemberNotFound):
 return await ctx.send(
 embed=self.embed(
 "❌ Usuário não encontrado",
 "Não encontrei esse membro no servidor."
 )
 )
 
 raise error

async def setup(bot):
 await bot.add_cog(Moderation(bot))
    
