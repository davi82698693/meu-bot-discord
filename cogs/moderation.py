import discord
from discord.ext import commands


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # -------------------------
    # BAN
    # -------------------------
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member = None, *, reason="Sem motivo informado"):

        if member is None:
            embed = discord.Embed(
                title="❌ Erro",
                description="Você precisa marcar um usuário para banir.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if member == ctx.author:
            return await ctx.send(
                embed=discord.Embed(
                    title="❌ Erro",
                    description="Você não pode se banir.",
                    color=discord.Color.red()
                )
            )

        await member.ban(reason=reason)

        embed = discord.Embed(
            title="🔨 Usuário Banido",
            description=(
                f"**Usuário:** {member.mention}\n"
                f"**Moderador:** {ctx.author.mention}\n"
                f"**Motivo:** {reason}"
            ),
            color=discord.Color.dark_red()
        )

        embed.set_footer(text="Sistema de Moderação")

        await ctx.send(embed=embed)


    # -------------------------
    # KICK
    # -------------------------
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason="Sem motivo informado"):

        if member is None:
            return await ctx.send(
                embed=discord.Embed(
                    title="❌ Erro",
                    description="Você precisa marcar um usuário para expulsar.",
                    color=discord.Color.red()
                )
            )

        await member.kick(reason=reason)

        embed = discord.Embed(
            title="👢 Usuário Expulso",
            description=(
                f"**Usuário:** {member.mention}\n"
                f"**Moderador:** {ctx.author.mention}\n"
                f"**Motivo:** {reason}"
            ),
            color=discord.Color.orange()
        )

        await ctx.send(embed=embed)


    # -------------------------
    # CLEAR
    # -------------------------
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, quantidade: int = 5):

        await ctx.channel.purge(limit=quantidade + 1)

        embed = discord.Embed(
            title="🧹 Mensagens Apagadas",
            description=f"Foram apagadas **{quantidade} mensagens**.",
            color=discord.Color.blue()
        )

        msg = await ctx.send(embed=embed)

        await msg.delete(delay=5)


    # -------------------------
    # MUTE
    # -------------------------
    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member = None):

        if member is None:
            return await ctx.send(
                embed=discord.Embed(
                    title="❌ Erro",
                    description="Você precisa marcar um usuário para mutar.",
                    color=discord.Color.red()
                )
            )

        role = discord.utils.get(
            ctx.guild.roles,
            name="Muted"
        )

        if role is None:

            role = await ctx.guild.create_role(
                name="Muted",
                reason="Sistema automático de mute"
            )

            for channel in ctx.guild.channels:
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    speak=False
                )

        await member.add_roles(role)

        embed = discord.Embed(
            title="🔇 Usuário Mutado",
            description=f"{member.mention} foi mutado.",
            color=discord.Color.yellow()
        )

        await ctx.send(embed=embed)


    # -------------------------
    # UNMUTE
    # -------------------------
    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member = None):

        if member is None:
            return await ctx.send(
                embed=discord.Embed(
                    title="❌ Erro",
                    description="Você precisa marcar um usuário.",
                    color=discord.Color.red()
                )
            )

        role = discord.utils.get(
            ctx.guild.roles,
            name="Muted"
        )

        if role in member.roles:
            await member.remove_roles(role)

        embed = discord.Embed(
            title="🔊 Usuário Desmutado",
            description=f"{member.mention} foi desmutado.",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))