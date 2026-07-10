import discord
import os
import time

from datetime import datetime, timedelta, timezone
from discord.ext import commands


LIMITE_MENSAGENS = int(os.getenv("ANTISPAM_LIMITE", "5"))
JANELA_SEGUNDOS = int(os.getenv("ANTISPAM_JANELA", "5"))
TIMEOUT_SEGUNDOS = int(os.getenv("ANTISPAM_TIMEOUT", "60"))

LOG_CHANNEL_NAME = "logs-moderação"


class Antispam(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.historico = {}


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if message.guild is None:
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
