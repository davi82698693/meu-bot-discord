import discord
import time

from datetime import datetime, timezone

from discord.ext import commands


INICIO_BOT = time.time()


def formatar_tempo(segundos):

    dias, resto = divmod(int(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)

    partes = []

    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")

    partes.append(f"{minutos}m")

    return " ".join(partes)


class Stats(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.hybrid_command(name="stats", aliases=["estatisticas"])
    async def stats_cmd(self, ctx):

        guild = ctx.guild

        membros_totais = guild.member_count if guild else 0
        membros_online = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild else 0
        bots = sum(1 for m in guild.members if m.bot) if guild else 0

        canais_texto = len(guild.text_channels) if guild else 0
        canais_voz = len(guild.voice_channels) if guild else 0
        cargos = len(guild.roles) if guild else 0

        uptime = formatar_tempo(time.time() - INICIO_BOT)

        linhas = [
            "## 📊 Estatísticas do Servidor",
            f"**{guild.name if guild else 'Servidor'}**",
            ""
        ]

        linhas.append(
            f"👥 **Membros:** {membros_totais} totais • {membros_online} online • {bots} bot(s)"
        )
        linhas.append(
            f"📺 **Canais:** {canais_texto} de texto • {canais_voz} de voz"
        )
        linhas.append(
            f"🎭 **Cargos:** {cargos}"
        )
        linhas.append(
            f"⏱️ **Bot online há:** {uptime}"
        )

        loja = self.bot.get_cog("Loja")

        if loja is not None:

            produtos = loja.dados.get("produtos", {})
            aprovados = [p for p in loja.dados.get("pedidos", {}).values() if p.get("status") == "aprovado"]

            faturamento = 0.0

            for p in aprovados:
                try:
                    faturamento += float(str(p["preco"]).replace(".", "").replace(",", "."))
                except Exception:
                    pass

            linhas.append("")
            linhas.append(
                f"🛒 **Loja:** {len(produtos)} produto(s) • {len(aprovados)} venda(s) • R$ {faturamento:.2f} faturados"
            )

        sorteio = self.bot.get_cog("Sorteio")

        if sorteio is not None:

            ativos = [s for s in sorteio.sorteios.values() if s.get("status") == "ativo"]

            linhas.append(f"🎉 **Sorteios ativos:** {len(ativos)}")

        jogos = self.bot.get_cog("Jogos")

        if jogos is not None:

            saldos = jogos.dados.get("saldo", {})
            total_moedas = sum(saldos.values())

            linhas.append(f"🪙 **Economia:** {len(saldos)} carteira(s) • {total_moedas:,} moedas em circulação".replace(",", "."))

        niveis = self.bot.get_cog("Niveis")

        if niveis is not None:

            usuarios_xp = niveis.dados.get("usuarios", {})

            linhas.append(f"📈 **Níveis:** {len(usuarios_xp)} membro(s) com XP registrado")

        texto = "\n".join(linhas)

        container = discord.ui.Container(accent_color=discord.Color.gold())

        if guild and guild.icon:

            secao = discord.ui.Section(
                texto,
                accessory=discord.ui.Thumbnail(guild.icon.url)
            )

            container.add_item(secao)

        else:

            container.add_item(discord.ui.TextDisplay(texto))

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# Gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}"))

        layout = discord.ui.LayoutView(timeout=None)
        layout.add_item(container)

        await ctx.send(view=layout)


async def setup(bot):

    await bot.add_cog(
        Stats(bot)
    )
