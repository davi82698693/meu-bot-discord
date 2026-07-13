import discord
import os
import json
import random
import time
import asyncio

from datetime import datetime, timezone, timedelta

from discord.ext import commands
from discord.ui import View, Button


# ==========================================================
# CONFIG / PERSISTÊNCIA
# ==========================================================

DATA_DIR = (
    os.getenv("JOGOS_DATA_DIR")
    or os.getenv("SORTEIO_DATA_DIR")
    or os.path.dirname(__file__)
)

os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "economia_data.json")

MOEDA = "🪙"
NOME_MOEDA = "moedas"

DIARIO_VALOR = (200, 500)
DIARIO_COOLDOWN = 86400

MINERAR_VALOR = (50, 200)
MINERAR_COOLDOWN = 1800

PESCAR_VALOR = (30, 300)
PESCAR_COOLDOWN = 1200

MISSAO_LIMITE_SALDO = 50
MISSAO_COOLDOWN = 1800
MISSAO_RECOMPENSA = (100, 300)

SALDO_INICIAL = 500


def carregar_dados():

    if not os.path.exists(DATA_FILE):
        return {"saldo": {}, "diario": {}, "minerar": {}, "pescar": {}, "missao": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("saldo", {})
            dados.setdefault("diario", {})
            dados.setdefault("minerar", {})
            dados.setdefault("pescar", {})
            dados.setdefault("missao", {})
            return dados
    except Exception as e:
        print(f"⚠️ Erro ao carregar economia_data.json: {e}")
        return {"saldo": {}, "diario": {}, "minerar": {}, "pescar": {}, "missao": {}}


def salvar_dados(dados):

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erro ao salvar economia_data.json: {e}")


def fmt(qtd):

    return f"{int(qtd):,}".replace(",", ".") + f" {MOEDA}"


def embed_padrao(titulo, descricao, cor=discord.Color.gold()):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(text="🎮 Central de Jogos")

    return embed


# ==========================================================
# COG
# ==========================================================

class Jogos(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.dados = carregar_dados()

        self.em_jogo = set()


    def salvar(self):

        salvar_dados(self.dados)


    def saldo(self, user_id):

        return self.dados["saldo"].get(str(user_id), SALDO_INICIAL)


    def definir_saldo(self, user_id, valor):

        self.dados["saldo"][str(user_id)] = max(0, int(valor))


    def adicionar(self, user_id, quantidade):

        self.definir_saldo(user_id, self.saldo(user_id) + quantidade)


    def remover(self, user_id, quantidade):

        self.definir_saldo(user_id, self.saldo(user_id) - quantidade)


    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(
                embed=embed_padrao("❌ Faltou argumento", f"Faltou informar: `{error.param.name}`", discord.Color.red())
            )

        if isinstance(error, commands.BadArgument):
            return await ctx.send(
                embed=embed_padrao("❌ Valor inválido", "Confira os argumentos do comando.", discord.Color.red())
            )

        print(f"Erro no comando {ctx.command}: {error}")

        await ctx.send(embed=embed_padrao("❌ Erro", f"```{type(error).__name__}: {error}```", discord.Color.red()))


    def _validar_aposta(self, ctx, aposta):

        if aposta <= 0:
            return "❌ A aposta precisa ser maior que zero."

        if aposta > self.saldo(ctx.author.id):
            return f"❌ Você não tem {fmt(aposta)}. Seu saldo é {fmt(self.saldo(ctx.author.id))}."

        return None


    # ======================================================
    # ECONOMIA BÁSICA
    # ======================================================

    @commands.hybrid_command(name="carteira", aliases=["saldo"])
    async def carteira(self, ctx, membro: discord.Member = None):

        membro = membro or ctx.author

        await ctx.send(
            embed=embed_padrao(
                f"👛 Carteira de {membro.display_name}",
                f"Saldo atual: **{fmt(self.saldo(membro.id))}**",
                discord.Color.gold()
            )
        )


    @commands.hybrid_command(name="diario")
    async def diario(self, ctx):

        ultimo = self.dados["diario"].get(str(ctx.author.id), 0)

        restante = DIARIO_COOLDOWN - (time.time() - ultimo)

        if restante > 0:

            horas = int(restante // 3600)
            minutos = int((restante % 3600) // 60)

            return await ctx.send(
                embed=embed_padrao(
                    "⏳ Já veio hoje",
                    f"Volte em **{horas}h {minutos}min** para resgatar de novo.",
                    discord.Color.orange()
                )
            )

        ganho = random.randint(*DIARIO_VALOR)

        self.adicionar(ctx.author.id, ganho)

        self.dados["diario"][str(ctx.author.id)] = time.time()

        self.salvar()

        await ctx.send(
            embed=embed_padrao(
                "🎁 Recompensa diária",
                f"Você recebeu **{fmt(ganho)}**!\nSaldo atual: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.green()
            )
        )


    @commands.hybrid_command(name="pagar")
    async def pagar(self, ctx, membro: discord.Member, valor: int):

        if membro.id == ctx.author.id:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Você não pode pagar você mesmo.", discord.Color.red()))

        if membro.bot:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Não dá pra pagar um bot.", discord.Color.red()))

        erro = self._validar_aposta(ctx, valor)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, valor)
        self.adicionar(membro.id, valor)
        self.salvar()

        await ctx.send(
            embed=embed_padrao(
                "💸 Transferência realizada",
                f"{ctx.author.mention} pagou **{fmt(valor)}** para {membro.mention}.",
                discord.Color.blurple()
            )
        )


    @commands.hybrid_command(name="ranking", aliases=["top"])
    async def ranking(self, ctx):

        lista = sorted(self.dados["saldo"].items(), key=lambda x: -x[1])[:10]

        if not lista:
            return await ctx.send(embed=embed_padrao("🏆 Ranking", "Ninguém tem saldo registrado ainda.", discord.Color.orange()))

        texto = ""

        for i, (uid, valor) in enumerate(lista, start=1):

            texto += f"**{i}.** <@{uid}> — {fmt(valor)}\n"

        await ctx.send(embed=embed_padrao("🏆 Ranking de Ricos", texto, discord.Color.gold()))


    # ======================================================
    # 1. CARA OU COROA
    # ======================================================

    @commands.hybrid_command(name="caracoroa")
    async def caracoroa(self, ctx, lado: str, aposta: int):

        lado = lado.lower()

        if lado not in ("cara", "coroa"):
            return await ctx.send(embed=embed_padrao("❌ Erro", "Escolha `cara` ou `coroa`.", discord.Color.red()))

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, aposta)

        resultado = random.choice(["cara", "coroa"])

        if resultado == lado:

            premio = aposta * 2

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao(
                "🪙 Cara ou Coroa — Você ganhou!",
                f"Deu **{resultado}**! Você apostou em **{lado}**.\n"
                f"💰 Ganhou {fmt(premio)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.green()
            )

        else:

            embed = embed_padrao(
                "🪙 Cara ou Coroa — Você perdeu",
                f"Deu **{resultado}**! Você apostou em **{lado}**.\n"
                f"💸 Perdeu {fmt(aposta)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.red()
            )

        self.salvar()

        await ctx.send(embed=embed)


    # ======================================================
    # 2. DADO DA SORTE
    # ======================================================

    @commands.hybrid_command(name="dado")
    async def dado(self, ctx, numero: int, aposta: int):

        if numero < 1 or numero > 6:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Escolha um número de 1 a 6.", discord.Color.red()))

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, aposta)

        resultado = random.randint(1, 6)

        dados_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

        if resultado == numero:

            premio = aposta * 6

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao(
                f"🎲 Dado da Sorte — {dados_emoji[resultado-1]} Você acertou!",
                f"Caiu o número **{resultado}**!\n💰 Ganhou {fmt(premio)} (x6)\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.green()
            )

        else:

            embed = embed_padrao(
                f"🎲 Dado da Sorte — {dados_emoji[resultado-1]} Não foi dessa vez",
                f"Caiu o número **{resultado}**, você apostou no **{numero}**.\n"
                f"💸 Perdeu {fmt(aposta)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.red()
            )

        self.salvar()

        await ctx.send(embed=embed)


    # ======================================================
    # 3. ROLETA
    # ======================================================

    @commands.hybrid_command(name="roleta")
    async def roleta(self, ctx, cor: str, aposta: int):

        cor = cor.lower()

        if cor not in ("vermelho", "preto", "verde"):
            return await ctx.send(embed=embed_padrao("❌ Erro", "Escolha `vermelho`, `preto` ou `verde`.", discord.Color.red()))

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, aposta)

        sorteio = random.choices(
            ["vermelho", "preto", "verde"],
            weights=[18, 18, 1],
            k=1
        )[0]

        emojis = {"vermelho": "🔴", "preto": "⚫", "verde": "🟢"}

        multiplicadores = {"vermelho": 2, "preto": 2, "verde": 14}

        if sorteio == cor:

            premio = aposta * multiplicadores[cor]

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao(
                f"🎡 Roleta — {emojis[sorteio]} Você ganhou!",
                f"Caiu **{sorteio}**!\n💰 Ganhou {fmt(premio)} (x{multiplicadores[cor]})\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.green()
            )

        else:

            embed = embed_padrao(
                f"🎡 Roleta — {emojis[sorteio]} Não foi dessa vez",
                f"Caiu **{sorteio}**, você apostou no **{cor}**.\n"
                f"💸 Perdeu {fmt(aposta)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.red()
            )

        self.salvar()

        await ctx.send(embed=embed)


    # ======================================================
    # 4. CAÇA-NÍQUEIS
    # ======================================================

    @commands.hybrid_command(name="slots", aliases=["caçaniqueis"])
    async def slots(self, ctx, aposta: int):

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, aposta)

        simbolos = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]

        resultado = [random.choice(simbolos) for _ in range(3)]

        linha = " | ".join(resultado)

        if resultado[0] == resultado[1] == resultado[2]:

            premio = aposta * 10

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao(
                "🎰 Caça-Níqueis — JACKPOT!",
                f"[ {linha} ]\n💰 Três iguais! Ganhou {fmt(premio)} (x10)\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.gold()
            )

        elif len(set(resultado)) == 2:

            premio = aposta * 2

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao(
                "🎰 Caça-Níqueis — Duas iguais!",
                f"[ {linha} ]\n💰 Ganhou {fmt(premio)} (x2)\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.green()
            )

        else:

            embed = embed_padrao(
                "🎰 Caça-Níqueis — Não foi dessa vez",
                f"[ {linha} ]\n💸 Perdeu {fmt(aposta)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.red()
            )

        self.salvar()

        await ctx.send(embed=embed)


    # ======================================================
    # 5. BLACKJACK (21)
    # ======================================================

    @commands.hybrid_command(name="blackjack", aliases=["21"])
    async def blackjack(self, ctx, aposta: int):

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        if ctx.author.id in self.em_jogo:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Você já tem um jogo rolando.", discord.Color.red()))

        self.em_jogo.add(ctx.author.id)
        self.remover(ctx.author.id, aposta)
        self.salvar()

        naipe = ["♠️", "♥️", "♦️", "♣️"]
        valores = list(range(2, 11)) + [10, 10, 10, 11]

        def nova_carta():
            return random.choice(valores)

        def total(mao):
            soma = sum(mao)
            ases = mao.count(11)
            while soma > 21 and ases:
                soma -= 10
                ases -= 1
            return soma

        jogador = [nova_carta(), nova_carta()]
        dealer = [nova_carta(), nova_carta()]

        async def finalizar(interaction_ou_ctx, editar=False):

            while total(dealer) < 17:
                dealer.append(nova_carta())

            tj, td = total(jogador), total(dealer)

            if tj > 21:
                resultado, cor, premio = f"Você estourou com {tj}! Perdeu.", discord.Color.red(), 0
            elif td > 21 or tj > td:
                premio = aposta * 2
                self.adicionar(ctx.author.id, premio)
                resultado, cor = f"Você ganhou! ({tj} x {td})", discord.Color.green()
            elif tj == td:
                self.adicionar(ctx.author.id, aposta)
                resultado, cor, premio = f"Empate ({tj} x {td}). Aposta devolvida.", discord.Color.orange(), aposta
            else:
                resultado, cor, premio = f"Você perdeu. ({tj} x {td})", discord.Color.red(), 0

            self.salvar()
            self.em_jogo.discard(ctx.author.id)

            embed = embed_padrao(
                "🃏 Blackjack — Resultado",
                f"**Sua mão:** {jogador} = {tj}\n**Mão do dealer:** {dealer} = {td}\n\n"
                f"{resultado}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                cor
            )

            if editar:
                await interaction_ou_ctx.response.edit_message(embed=embed, view=None)
            else:
                await interaction_ou_ctx.send(embed=embed)

        class BlackjackView(View):

            def __init__(self_view):
                super().__init__(timeout=60)

            async def interaction_check(self_view, interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Esse jogo não é seu.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label="🃏 Pedir carta", style=discord.ButtonStyle.primary)
            async def pedir(self_view, interaction, button):

                jogador.append(nova_carta())

                if total(jogador) >= 21:
                    return await finalizar(interaction, editar=True)

                embed = embed_padrao(
                    "🃏 Blackjack",
                    f"**Sua mão:** {jogador} = {total(jogador)}\n**Dealer mostra:** {dealer[0]}\n\nPedir mais uma carta ou parar?",
                    discord.Color.blurple()
                )

                await interaction.response.edit_message(embed=embed, view=self_view)

            @discord.ui.button(label="✋ Parar", style=discord.ButtonStyle.danger)
            async def parar(self_view, interaction, button):
                await finalizar(interaction, editar=True)

            async def on_timeout(self_view):
                self.em_jogo.discard(ctx.author.id)

        embed = embed_padrao(
            "🃏 Blackjack",
            f"**Sua mão:** {jogador} = {total(jogador)}\n**Dealer mostra:** {dealer[0]}\n\nPedir mais uma carta ou parar?",
            discord.Color.blurple()
        )

        if total(jogador) == 21:
            await ctx.send(embed=embed)
            await finalizar(ctx)
        else:
            await ctx.send(embed=embed, view=BlackjackView())


    # ======================================================
    # 6. FORCA
    # ======================================================

    @commands.hybrid_command(name="forca")
    async def forca(self, ctx):

        if ctx.author.id in self.em_jogo:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Você já tem um jogo rolando.", discord.Color.red()))

        palavras = ["discord", "python", "servidor", "moderacao", "loja", "sorteio", "estoque", "jogador", "credito", "programacao"]

        palavra = random.choice(palavras)

        letras_certas = set()
        letras_erradas = set()
        tentativas = 6

        self.em_jogo.add(ctx.author.id)

        def mostrar():
            return " ".join(l if l in letras_certas else "＿" for l in palavra)

        await ctx.send(
            embed=embed_padrao(
                "🔤 Jogo da Forca",
                f"Palavra: `{mostrar()}`\n❤️ Tentativas: {tentativas}\n\nDigite uma letra no chat!",
                discord.Color.blurple()
            )
        )

        def checar(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and len(m.content) == 1

        while tentativas > 0 and set(palavra) - letras_certas:

            try:
                msg = await self.bot.wait_for("message", check=checar, timeout=30)
            except asyncio.TimeoutError:
                self.em_jogo.discard(ctx.author.id)
                return await ctx.send(embed=embed_padrao("⏳ Tempo esgotado", f"A palavra era **{palavra}**.", discord.Color.orange()))

            letra = msg.content.lower()

            if letra in palavra:
                letras_certas.add(letra)
            else:
                letras_erradas.add(letra)
                tentativas -= 1

            if set(palavra) - letras_certas and tentativas > 0:
                await ctx.send(
                    embed=embed_padrao(
                        "🔤 Jogo da Forca",
                        f"Palavra: `{mostrar()}`\n❤️ Tentativas: {tentativas}\n❌ Erradas: {', '.join(letras_erradas) or 'nenhuma'}",
                        discord.Color.blurple()
                    )
                )

        self.em_jogo.discard(ctx.author.id)

        if not (set(palavra) - letras_certas):

            premio = len(palavra) * 30

            self.adicionar(ctx.author.id, premio)
            self.salvar()

            await ctx.send(
                embed=embed_padrao(
                    "🎉 Você venceu a Forca!",
                    f"A palavra era **{palavra}**!\n💰 Ganhou {fmt(premio)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                    discord.Color.green()
                )
            )

        else:

            await ctx.send(
                embed=embed_padrao("💀 Você perdeu", f"A palavra era **{palavra}**.", discord.Color.red())
            )


    # ======================================================
    # 7. ADIVINHAÇÃO
    # ======================================================

    @commands.hybrid_command(name="adivinhar")
    async def adivinhar(self, ctx):

        if ctx.author.id in self.em_jogo:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Você já tem um jogo rolando.", discord.Color.red()))

        self.em_jogo.add(ctx.author.id)

        numero = random.randint(1, 100)
        tentativas = 0
        max_tentativas = 7

        await ctx.send(
            embed=embed_padrao(
                "🔢 Adivinhe o Número",
                f"Pensei em um número de **1 a 100**. Você tem {max_tentativas} tentativas!\nDigite um número no chat.",
                discord.Color.blurple()
            )
        )

        def checar(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.isdigit()

        while tentativas < max_tentativas:

            try:
                msg = await self.bot.wait_for("message", check=checar, timeout=30)
            except asyncio.TimeoutError:
                self.em_jogo.discard(ctx.author.id)
                return await ctx.send(embed=embed_padrao("⏳ Tempo esgotado", f"O número era **{numero}**.", discord.Color.orange()))

            palpite = int(msg.content)
            tentativas += 1

            if palpite == numero:

                premio = max(50, (max_tentativas - tentativas + 1) * 100)

                self.adicionar(ctx.author.id, premio)
                self.salvar()
                self.em_jogo.discard(ctx.author.id)

                return await ctx.send(
                    embed=embed_padrao(
                        "🎉 Acertou!",
                        f"O número era **{numero}**! Você acertou em {tentativas} tentativa(s).\n"
                        f"💰 Ganhou {fmt(premio)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                        discord.Color.green()
                    )
                )

            dica = "maior 📈" if palpite < numero else "menor 📉"

            await ctx.send(
                embed=embed_padrao(
                    "🔢 Adivinhe o Número",
                    f"O número é **{dica}** que {palpite}. Tentativas restantes: {max_tentativas - tentativas}",
                    discord.Color.blurple()
                )
            )

        self.em_jogo.discard(ctx.author.id)

        await ctx.send(embed=embed_padrao("💀 Acabaram as tentativas", f"O número era **{numero}**.", discord.Color.red()))


    # ======================================================
    # 8. PEDRA, PAPEL OU TESOURA
    # ======================================================

    @commands.hybrid_command(name="ppt")
    async def ppt(self, ctx, escolha: str, aposta: int):

        escolha = escolha.lower()

        opcoes = {"pedra": "🪨", "papel": "📄", "tesoura": "✂️"}

        if escolha not in opcoes:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Escolha `pedra`, `papel` ou `tesoura`.", discord.Color.red()))

        erro = self._validar_aposta(ctx, aposta)

        if erro:
            return await ctx.send(embed=embed_padrao("❌ Erro", erro, discord.Color.red()))

        self.remover(ctx.author.id, aposta)

        bot_escolha = random.choice(list(opcoes.keys()))

        vence = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}

        linha = f"{opcoes[escolha]} Você  vs  Bot {opcoes[bot_escolha]}"

        if escolha == bot_escolha:

            self.adicionar(ctx.author.id, aposta)

            embed = embed_padrao("🤝 Empate!", f"{linha}\nAposta devolvida.\nSaldo: {fmt(self.saldo(ctx.author.id))}", discord.Color.orange())

        elif vence[escolha] == bot_escolha:

            premio = aposta * 2

            self.adicionar(ctx.author.id, premio)

            embed = embed_padrao("🎉 Você ganhou!", f"{linha}\n💰 Ganhou {fmt(premio)}\nSaldo: {fmt(self.saldo(ctx.author.id))}", discord.Color.green())

        else:

            embed = embed_padrao("💀 Você perdeu", f"{linha}\n💸 Perdeu {fmt(aposta)}\nSaldo: {fmt(self.saldo(ctx.author.id))}", discord.Color.red())

        self.salvar()

        await ctx.send(embed=embed)


    # ======================================================
    # 9. MINERAÇÃO
    # ======================================================

    @commands.hybrid_command(name="minerar")
    async def minerar(self, ctx):

        ultimo = self.dados["minerar"].get(str(ctx.author.id), 0)

        restante = MINERAR_COOLDOWN - (time.time() - ultimo)

        if restante > 0:

            minutos = int(restante // 60)

            return await ctx.send(embed=embed_padrao("⏳ Picareta quebrada", f"Espere mais **{minutos}min** para minerar de novo.", discord.Color.orange()))

        achados = ["🪨 Pedra", "🥉 Cobre", "🥈 Prata", "🥇 Ouro", "💎 Diamante"]
        pesos = [40, 30, 15, 10, 5]

        achado = random.choices(achados, weights=pesos, k=1)[0]

        multiplicador = {"🪨 Pedra": 0.5, "🥉 Cobre": 0.8, "🥈 Prata": 1.2, "🥇 Ouro": 2, "💎 Diamante": 4}[achado]

        ganho = int(random.randint(*MINERAR_VALOR) * multiplicador)

        self.adicionar(ctx.author.id, ganho)

        self.dados["minerar"][str(ctx.author.id)] = time.time()

        self.salvar()

        await ctx.send(
            embed=embed_padrao(
                "⛏️ Mineração",
                f"Você encontrou: **{achado}**!\n💰 Ganhou {fmt(ganho)}\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                discord.Color.dark_gold()
            )
        )


    # ======================================================
    # 10. PESCARIA
    # ======================================================

    @commands.hybrid_command(name="pescar")
    async def pescar(self, ctx):

        ultimo = self.dados["pescar"].get(str(ctx.author.id), 0)

        restante = PESCAR_COOLDOWN - (time.time() - ultimo)

        if restante > 0:

            minutos = int(restante // 60)

            return await ctx.send(embed=embed_padrao("⏳ Vara de pesca cansada", f"Espere mais **{minutos}min** para pescar de novo.", discord.Color.orange()))

        peixes = ["🥾 Bota velha", "🐟 Peixinho", "🐠 Peixe colorido", "🦈 Tubarão", "🐋 Baleia"]
        pesos = [15, 40, 25, 15, 5]

        peixe = random.choices(peixes, weights=pesos, k=1)[0]

        if peixe == "🥾 Bota velha":
            ganho = 0
        else:
            multiplicador = {"🐟 Peixinho": 0.6, "🐠 Peixe colorido": 1.2, "🦈 Tubarão": 2.5, "🐋 Baleia": 5}[peixe]
            ganho = int(random.randint(*PESCAR_VALOR) * multiplicador)

        self.adicionar(ctx.author.id, ganho)

        self.dados["pescar"][str(ctx.author.id)] = time.time()

        self.salvar()

        descricao = f"Você pescou: **{peixe}**!\n"
        descricao += "😅 Não valeu nada..." if ganho == 0 else f"💰 Ganhou {fmt(ganho)}"
        descricao += f"\nSaldo: {fmt(self.saldo(ctx.author.id))}"

        await ctx.send(
            embed=embed_padrao("🎣 Pescaria", descricao, discord.Color.blue())
        )


    # ======================================================
    # MISSÃO DE RESGATE (quando o saldo está baixo/zerado)
    # ======================================================

    @commands.hybrid_command(name="missao")
    async def missao(self, ctx):

        if self.saldo(ctx.author.id) > MISSAO_LIMITE_SALDO:
            return await ctx.send(
                embed=embed_padrao(
                    "❌ Você não precisa disso",
                    f"A missão de resgate só libera quando você tem {fmt(MISSAO_LIMITE_SALDO)} ou menos.",
                    discord.Color.orange()
                )
            )

        ultimo = self.dados["missao"].get(str(ctx.author.id), 0)
        restante = MISSAO_COOLDOWN - (time.time() - ultimo)

        if restante > 0:
            minutos = int(restante // 60)
            return await ctx.send(
                embed=embed_padrao("⏳ Aguarde", f"Você já fez uma missão recentemente. Espere mais **{minutos}min**.", discord.Color.orange())
            )

        if ctx.author.id in self.em_jogo:
            return await ctx.send(embed=embed_padrao("❌ Erro", "Você já tem um jogo rolando.", discord.Color.red()))

        self.em_jogo.add(ctx.author.id)

        tipo = random.choice(["matematica", "palavra"])

        if tipo == "matematica":

            a, b = random.randint(1, 20), random.randint(1, 20)
            operacao = random.choice(["+", "-", "*"])
            resposta = str(eval(f"{a}{operacao}{b}"))
            pergunta = f"Quanto é **{a} {operacao} {b}**?"

        else:

            resposta = random.choice(["coragem", "vitoria", "moeda", "sorte", "tesouro", "fortuna"])
            pergunta = f"Digite exatamente esta palavra: **{resposta}**"

        await ctx.send(
            embed=embed_padrao("🆘 Missão de Resgate", f"{pergunta}\n\nVocê tem 20 segundos!", discord.Color.blurple())
        )

        def checar(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        self.dados["missao"][str(ctx.author.id)] = time.time()
        self.salvar()

        try:
            msg = await self.bot.wait_for("message", check=checar, timeout=20)
        except asyncio.TimeoutError:
            self.em_jogo.discard(ctx.author.id)
            return await ctx.send(embed=embed_padrao("⏳ Tempo esgotado", "Tente de novo com `!missao` mais tarde.", discord.Color.red()))

        self.em_jogo.discard(ctx.author.id)

        correto = msg.content.strip().lower() == resposta.lower()

        if correto:

            premio = random.randint(*MISSAO_RECOMPENSA)

            self.adicionar(ctx.author.id, premio)
            self.salvar()

            await ctx.send(
                embed=embed_padrao(
                    "✅ Missão cumprida!",
                    f"Parabéns! Você ganhou **{fmt(premio)}**.\nSaldo: {fmt(self.saldo(ctx.author.id))}",
                    discord.Color.green()
                )
            )

        else:

            await ctx.send(
                embed=embed_padrao("❌ Resposta errada", f"A resposta certa era **{resposta}**. Tente de novo em 30 minutos.", discord.Color.red())
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Jogos(bot)
    )
