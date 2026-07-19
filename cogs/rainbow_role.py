"""
Rainbow Role - Cog para discord.py

Faz um cargo (role) mudar de cor continuamente, criando um efeito "arco-íris".

Como usar:
1. Coloque este arquivo na pasta de cogs do seu bot (ex: ./cogs/rainbow_role.py)
2. No seu bot principal, carregue o cog com:
       await bot.load_extension("cogs.rainbow_role")
   (ajuste o caminho conforme onde você salvar o arquivo)
3. No Discord, use os comandos:
       !rainbow start @Cargo       -> inicia o efeito rainbow no cargo
       !rainbow start @Cargo 5     -> troca de cor a cada 5 segundos (padrão: 10)
       !rainbow stop @Cargo        -> para o efeito

Requisitos:
    pip install discord.py

IMPORTANTE:
- O cargo do bot precisa estar ACIMA do cargo que vai ficar rainbow, na
  hierarquia de cargos do servidor (Configurações do Servidor > Cargos).
- O bot precisa da permissão "Gerenciar Cargos" (Manage Roles).
- Discord tem limite de taxa (rate limit) para editar cargos. Não recomendado
  usar intervalos muito curtos (menos de 2-3 segundos) com muitos cargos rainbow
  ao mesmo tempo, para não ser limitado pela API.
"""

import colorsys
import logging
import time

import discord
from discord.ext import commands, tasks

log = logging.getLogger(__name__)

# --- Configuração do throttling adaptativo -------------------------------
# Se uma chamada demorar mais que INTERVALO_ATUAL * este fator, entendemos
# que o Discord nos limitou (a lib fica esperando por dentro do await).
FATOR_DETECCAO_LIMITE = 2.0
# Depois de desacelerar, espera esse tempo sem novos limites antes de
# tentar acelerar de novo (evita ficar batendo no limite repetidamente).
COOLDOWN_SEGUNDOS = 20.0
# A cada passo de "aceleração", reduz o intervalo atual multiplicando por isto
# (se aproxima do valor original gradualmente, em vez de pular direto pra ele).
FATOR_ACELERACAO = 0.7
# Intervalo máximo permitido, mesmo se o Discord limitar muito forte.
INTERVALO_MAXIMO = 15.0
# --------------------------------------------------------------------------


class RainbowRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Guarda as tasks ativas por role_id
        self.active_tasks: dict[int, tasks.Loop] = {}
        self.hues: dict[int, float] = {}
        self.intervalo_original: dict[int, float] = {}
        self.intervalo_atual: dict[int, float] = {}
        self.cooldown_ate: dict[int, float] = {}

    def cog_unload(self):
        for task in self.active_tasks.values():
            task.cancel()

    def _desacelerar(self, loop_obj: tasks.Loop, role_id: int, minimo: float):
        atual = self.intervalo_atual[role_id]
        novo = min(max(minimo, atual * 1.5), INTERVALO_MAXIMO)
        if novo != atual:
            loop_obj.change_interval(seconds=novo)
            self.intervalo_atual[role_id] = novo
            log.warning("Rainbow role %s: rate limit detectado, intervalo subiu para %.2fs.", role_id, novo)
        self.cooldown_ate[role_id] = time.monotonic() + COOLDOWN_SEGUNDOS

    def _tentar_acelerar(self, loop_obj: tasks.Loop, role_id: int):
        original = self.intervalo_original[role_id]
        atual = self.intervalo_atual[role_id]
        if atual <= original:
            return
        agora = time.monotonic()
        if agora < self.cooldown_ate.get(role_id, 0.0):
            return
        novo = max(original, atual * FATOR_ACELERACAO)
        loop_obj.change_interval(seconds=novo)
        self.intervalo_atual[role_id] = novo
        if novo > original:
            log.info("Rainbow role %s: reduzindo intervalo de volta para %.2fs.", role_id, novo)
        # dá uma nova janela de cooldown antes do próximo passo de aceleração
        self.cooldown_ate[role_id] = agora + COOLDOWN_SEGUNDOS

    def _make_task(self, role: discord.Role, interval: float):
        self.hues[role.id] = 0.0
        self.intervalo_original[role.id] = interval
        self.intervalo_atual[role.id] = interval
        self.cooldown_ate[role.id] = 0.0

        @tasks.loop(seconds=interval)
        async def rainbow_loop():
            # Tudo dentro de um try/except genérico: qualquer erro (rate limit,
            # falha de rede, role deletada, etc.) é ignorado e o loop tenta
            # de novo no próximo ciclo, em vez de travar pra sempre.
            try:
                hue = self.hues.get(role.id, 0.0)
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                color = discord.Color.from_rgb(int(r * 255), int(g * 255), int(b * 255))

                inicio = time.monotonic()
                try:
                    await role.edit(color=color, reason="Rainbow role effect")
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        retry_after = float(getattr(e, "retry_after", 0) or self.intervalo_atual[role.id] * 2)
                        self._desacelerar(rainbow_loop, role.id, retry_after)
                        return
                    raise

                self.hues[role.id] = (hue + 0.05) % 1.0
                duracao = time.monotonic() - inicio

                if duracao > self.intervalo_atual[role.id] * FATOR_DETECCAO_LIMITE:
                    # A chamada demorou muito mais que o esperado: provavelmente
                    # a lib ficou esperando um rate limit por dentro do await.
                    self._desacelerar(rainbow_loop, role.id, duracao)
                else:
                    self._tentar_acelerar(rainbow_loop, role.id)

            except discord.NotFound:
                # O cargo foi deletado do servidor: aí sim não há mais o que fazer.
                log.warning("Rainbow role %s não existe mais, parando o loop.", role.id)
                rainbow_loop.cancel()
                self.active_tasks.pop(role.id, None)
                self.hues.pop(role.id, None)
            except discord.Forbidden:
                log.warning(
                    "Sem permissão para editar o cargo %s (verifique hierarquia/permissão).",
                    role.id,
                )
                # Não cancela: se a permissão for corrigida depois, o loop volta a funcionar sozinho.
            except Exception:
                # Timeout, erro de conexão, etc. Só loga e segue.
                log.exception("Erro ao atualizar cor do rainbow role %s, tentando de novo.", role.id)

        # Se o loop travar por algum erro não tratado dentro dele mesmo (não deveria
        # acontecer, já que tudo está no try/except acima), reinicia automaticamente.
        @rainbow_loop.error
        async def rainbow_loop_error(error):
            log.exception("Loop do rainbow role %s caiu, reiniciando.", role.id)
            if role.id in self.active_tasks and not rainbow_loop.is_running():
                rainbow_loop.restart()

        return rainbow_loop

    @commands.group(invoke_without_command=True)
    async def rainbow(self, ctx: commands.Context):
        await ctx.send("Use `!rainbow start @Cargo [segundos]` ou `!rainbow stop @Cargo`.")

    @rainbow.command(name="start")
    @commands.has_permissions(manage_roles=True)
    async def rainbow_start(self, ctx: commands.Context, role: discord.Role, interval: float = 10.0):
        if role.id in self.active_tasks:
            await ctx.send(f"O cargo **{role.name}** já está com o efeito rainbow ativo.")
            return

        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "Não consigo editar esse cargo: o cargo do bot precisa estar "
                "ACIMA dele na hierarquia de cargos do servidor."
            )
            return

        task = self._make_task(role, interval)
        self.active_tasks[role.id] = task
        task.start()
        await ctx.send(f"Efeito rainbow iniciado no cargo **{role.name}** (troca a cada {interval}s).")

    @rainbow.command(name="stop")
    @commands.has_permissions(manage_roles=True)
    async def rainbow_stop(self, ctx: commands.Context, role: discord.Role):
        task = self.active_tasks.pop(role.id, None)
        if task is None:
            await ctx.send(f"O cargo **{role.name}** não está com o efeito rainbow ativo.")
            return
        task.cancel()
        self.hues.pop(role.id, None)
        self.intervalo_original.pop(role.id, None)
        self.intervalo_atual.pop(role.id, None)
        self.cooldown_ate.pop(role.id, None)
        await ctx.send(f"Efeito rainbow parado no cargo **{role.name}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(RainbowRole(bot))
