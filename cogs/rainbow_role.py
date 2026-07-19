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

import discord
from discord.ext import commands, tasks


class RainbowRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Guarda as tasks ativas por role_id
        self.active_tasks: dict[int, tasks.Loop] = {}
        self.hues: dict[int, float] = {}

    def cog_unload(self):
        for task in self.active_tasks.values():
            task.cancel()

    def _make_task(self, role: discord.Role, interval: float):
        self.hues[role.id] = 0.0

        @tasks.loop(seconds=interval)
        async def rainbow_loop():
            hue = self.hues.get(role.id, 0.0)
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            color = discord.Color.from_rgb(int(r * 255), int(g * 255), int(b * 255))
            try:
                await role.edit(color=color, reason="Rainbow role effect")
            except discord.Forbidden:
                rainbow_loop.cancel()
                self.active_tasks.pop(role.id, None)
            except discord.HTTPException:
                pass  # ignora falhas temporárias (ex: rate limit) e tenta de novo no próximo ciclo

            # avança a "cor" no círculo de matizes (0.0 a 1.0)
            self.hues[role.id] = (hue + 0.05) % 1.0

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
        await ctx.send(f"Efeito rainbow parado no cargo **{role.name}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(RainbowRole(bot))
