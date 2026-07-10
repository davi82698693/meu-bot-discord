import discord
import os
import json
import time

from datetime import datetime, timedelta, timezone
from discord.ext import commands


LIMITE_MENSAGENS = int(os.getenv("ANTISPAM_LIMITE", "5"))
JANELA_SEGUNDOS = int(os.getenv("ANTISPAM_JANELA", "5"))
TIMEOUT_SEGUNDOS = int(os.getenv("ANTISPAM_TIMEOUT", "60"))

LOG_CHANNEL_NAME = "logs-moderação"

DATA_DIR = (
    os.getenv("ANTISPAM_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "antispam_config.json")


def carregar_config():

    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_config(config):

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar antispam_config.json: {e}")


class Antispam(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.historico = {}

        self.config = carregar_config()


    def esta_ativo(self, guild_id):

        return self.config.get(str(guild_id), True)


    @commands.command(name="ativarantispam")
    @commands.has_permissions(administrator=True)
    async def ativar_antispam(self, ctx):

        self.config[str(ctx.guild.id)] = True

        salvar_config(self.config)

        await ctx.send(
            embed=discord.Embed(
                title="✅ Anti-spam ativado",
                description="A proteção automática contra spam está ligada neste servidor.",
                color=discord.Color.green()
            )
        )


    @commands.command(name="desativarantispam")
    @commands.has_permissions(administrator=True)
    async def desativar_antispam(self, ctx):

        self.config[str(ctx.guild.id)] = False

        salvar_config(self.config)

        await ctx.send(
            embed=discord.Embed(
                title="🚫 Anti-spam desativado",
                description="A proteção automática contra spam está desligada neste servidor.",
                color=discord.Color.orange()
            )
        )


    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                embed=discord.Embed(
                    title="🚫 Sem permissão",
                    description="Você precisa ser Administrador para usar isso.",
                    color=discord.Color.red()
                )
            )

        raise error


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if message.guild is None:
            return

        if not self.esta_ativo(message.guild.id):
            return

        if message.author.guild_permissions.administrator:
            return

        agora = time.time()

        registros = self.historico.setdefault(message.author.id, [])

        registros.append(agora)

        registros[:] = [t for t in registros if agora - t <= JANELA_SEGUNDOS]

        if len(registros) <= LIMITE_MENSAGENS:
            return

        registros.clear()

        try:
            await message.delete()
        except Exception:
            pass

        membro = message.author

        try:

            await membro.timeout(
                discord.utils.utcnow() + timedelta(seconds=TIMEOUT_SEGUNDOS),
                reason="Anti-spam automático"
            )

        except Exception as e:
            print(f"⚠️ Não consegui silenciar {membro}: {e}")

        try:

            aviso = await message.channel.send(
                embed=discord.Embed(
                    title="🚫 Spam detectado",
                    description=(
                        f"{membro.mention} foi silenciado por **{TIMEOUT_SEGUNDOS}s** "
                        "por enviar mensagens rápido demais."
                    ),
                    color=discord.Color.red()
                )
            )

            await aviso.delete(delay=6)

        except Exception:
            pass

        canal_log = discord.utils.get(message.guild.text_channels, name=LOG_CHANNEL_NAME)

        if canal_log:

            try:
                await canal_log.send(
                    embed=discord.Embed(
                        title="🚫 Anti-spam acionado",
                        description=(
                            f"👤 **Usuário:** {membro.mention} (`{membro.id}`)\n"
                            f"📌 **Canal:** {message.channel.mention}\n"
                            f"⏱️ **Silenciado por:** {TIMEOUT_SEGUNDOS}s"
                        ),
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                )
            except Exception:
                pass


async def setup(bot):

    await bot.add_cog(
        Antispam(bot)
    )
