import discord
import os
import json
import io
import zipfile

from datetime import datetime, timezone

from discord.ext import commands
from discord.ui import View, Button


DATA_DIR = (
    os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

ARQUIVOS_CONHECIDOS = [
    "sorteios_data.json",
    "loja_data.json",
    "economia_data.json",
    "niveis_data.json",
    "boasvindas_data.json",
    "cargos_data.json",
    "autorole_data.json",
    "sugestoes_data.json",
    "logs_config.json",
    "antispam_config.json",
    "tickets_abertos.json",
    "convites_data.json",
    "aniversarios_data.json",
]


def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="💾 Backup")

    return embed


class Backup(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    async def cog_command_error(self, ctx, error):

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    @commands.hybrid_command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup_cmd(self, ctx):

        encontrados = []

        buffer_zip = io.BytesIO()

        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:

            for nome_arquivo in ARQUIVOS_CONHECIDOS:

                caminho = os.path.join(DATA_DIR, nome_arquivo)

                if os.path.exists(caminho):
                    zf.write(caminho, arcname=nome_arquivo)
                    encontrados.append(nome_arquivo)

        if not encontrados:
            return await ctx.send(
                embed=embed_padrao("❌ Nada pra fazer backup", "Nenhum arquivo de dados encontrado ainda.", discord.Color.orange())
            )

        buffer_zip.seek(0)

        data_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")

        arquivo = discord.File(buffer_zip, filename=f"backup_{data_str}.zip")

        texto = "\n".join(f"✅ {n}" for n in encontrados)

        await ctx.send(
            embed=embed_padrao(
                "💾 Backup gerado",
                f"Guarda esse arquivo em local seguro! Contém:\n\n{texto}",
                discord.Color.green()
            ),
            file=arquivo
        )


    @commands.hybrid_command(name="restore")
    @commands.has_permissions(administrator=True)
    async def restore_cmd(self, ctx):

        anexo = None

        if ctx.message and ctx.message.attachments:
            anexo = ctx.message.attachments[0]

        if anexo is None or not anexo.filename.endswith(".zip"):
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Anexo necessário",
                    "Use esse comando anexando o arquivo `.zip` gerado pelo `!backup`.",
                    discord.Color.red()
                )
            )

        await ctx.send(
            embed=embed_padrao(
                "⚠️ Tem certeza?",
                f"Isso vai **substituir os dados atuais** pelos do arquivo `{anexo.filename}`. "
                "Essa ação não pode ser desfeita. Confirma?",
                discord.Color.orange()
            ),
            view=ConfirmarRestoreView(anexo)
        )


async def setup(bot):

    await bot.add_cog(
        Backup(bot)
    )


class ConfirmarRestoreView(View):

    def __init__(self, anexo):

        super().__init__(timeout=60)

        self.anexo = anexo


    async def interaction_check(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Você precisa ser Administrador para usar isso.", ephemeral=True)
            return False

        return True


    @discord.ui.button(label="✅ Confirmar Restauração", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.defer()

        try:

            conteudo = await self.anexo.read()

            buffer = io.BytesIO(conteudo)

            restaurados = []

            with zipfile.ZipFile(buffer, "r") as zf:

                for nome in zf.namelist():

                    if nome not in ARQUIVOS_CONHECIDOS:
                        continue

                    destino = os.path.join(DATA_DIR, nome)

                    with zf.open(nome) as origem, open(destino, "wb") as saida:
                        saida.write(origem.read())

                    restaurados.append(nome)

            if not restaurados:

                return await interaction.followup.send(
                    embed=embed_padrao("❌ Nada restaurado", "O zip não continha arquivos reconhecidos.", discord.Color.red())
                )

            texto = "\n".join(f"✅ {n}" for n in restaurados)

            await interaction.followup.send(
                embed=embed_padrao(
                    "✅ Restauração concluída",
                    f"Arquivos restaurados:\n\n{texto}\n\n"
                    "⚠️ **Reinicie o bot (redeploy)** pra ele recarregar os dados restaurados.",
                    discord.Color.green()
                )
            )

        except Exception as e:

            await interaction.followup.send(
                embed=embed_padrao("❌ Erro ao restaurar", f"```{type(e).__name__}: {e}```", discord.Color.red())
            )


    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: Button):

        await interaction.response.edit_message(
            embed=embed_padrao("❌ Cancelado", "Nada foi alterado.", discord.Color.orange()),
            view=None
        )
