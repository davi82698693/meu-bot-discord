import discord
from discord.ext import commands
from datetime import datetime

from .logs import obter_canal_log


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.warnings = {}


    # ==================================
    # LOG DE INICIALIZAÇÃO
    # ==================================

    @commands.Cog.listener()
    async def on_ready(self):

        print("🛡️ Sistema de moderação carregado.")



    # ==================================
    # CONFIGURAR SISTEMA MANUALMENTE
    # ==================================

    @commands.command(name="setup-moderacao")
    @commands.has_permissions(manage_guild=True)
    async def setup_moderacao(self, ctx):

        guild = ctx.guild

        criado_algo = False


        # Criar cargo Muted

        muted = discord.utils.get(
            guild.roles,
            name="🔇 Muted"
        )

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


        # Criar cargo Staff

        staff = discord.utils.get(
            guild.roles,
            name="🛡️ Staff"
        )

        if staff is None:

            await guild.create_role(
                name="🛡️ Staff",
                reason="Sistema de moderação"
            )

            criado_algo = True


        # Criar canal de logs

        logs = discord.utils.get(
            guild.text_channels,
            name="📋・logs-moderação"
        )


        if logs is None:

            await guild.create_text_channel(
                "📋・logs-moderação",
                reason="Sistema de logs"
            )

            criado_algo = True


        await ctx.send(
            embed=self.embed(
                "✅ Setup de Moderação" if criado_algo else "ℹ️ Já configurado",
                "Estrutura de moderação criada/verificada com sucesso."
                if criado_algo
                else "Tudo que faltava já existia, nada novo foi criado.",
                discord.Color.green()
            )
        )



    # ==================================
    # EMBEDS PADRÃO
    # ==================================

    def embed(
        self,
        title,
        description,
        color=discord.Color.red()
    ):

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )


        embed.set_footer(
            text="🛡️ Sistema de Moderação"
        )


        return embed



    # ==================================
    # SISTEMA DE LOGS
    # ==================================

    async def enviar_log(
        self,
        guild,
        embed
    ):

        canal = obter_canal_log(self.bot, guild, "moderacao")

        if canal is None:

            canal = discord.utils.get(
                guild.text_channels,
                name="📋・logs-moderação"
            )


        if canal:

            await canal.send(
                embed=embed
            )



    # ==================================
    # BAN
    # ==================================

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason="Não informado"
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário para banir."
                )
            )


        if member == ctx.author:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você não pode se banir."
                )
            )


        if member.top_role >= ctx.author.top_role:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você não pode punir alguém com cargo igual ou superior."
                )
            )


        await member.ban(
            reason=reason
        )


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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # UNBAN
    # ==================================

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(
        self,
        ctx,
        user_id: int = None,
        *,
        reason="Não informado"
    ):

        if user_id is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa informar o ID do usuário para desbanir."
                )
            )


        try:

            user = await self.bot.fetch_user(
                user_id
            )

            await ctx.guild.unban(
                user,
                reason=reason
            )


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


            await ctx.send(
                embed=embed
            )


            await self.enviar_log(
                ctx.guild,
                embed
            )


        except discord.NotFound:

            await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Esse usuário não está banido ou o ID está incorreto."
                )
            )



    # ==================================
    # KICK
    # ==================================

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason="Não informado"
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário para expulsar."
                )
            )


        if member.top_role >= ctx.author.top_role:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você não pode expulsar esse usuário."
                )
            )


        await member.kick(
            reason=reason
        )


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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # MUTE
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason="Não informado"
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário para mutar."
                )
            )


        role = discord.utils.get(
            ctx.guild.roles,
            name="🔇 Muted"
        )


        if role is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "O cargo 🔇 Muted não existe. Use `!setup-moderacao` primeiro."
                )
            )


        await member.add_roles(
            role,
            reason=reason
        )


        embed = self.embed(
            "🔇 Usuário Mutado",
            f"""
👤 **Usuário:**
{member.mention}

🛡️ **Moderador:**
{ctx.author.mention}

📝 **Motivo:**
{reason}
""",
            discord.Color.gold()
        )


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # UNMUTE
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(
        self,
        ctx,
        member: discord.Member = None
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário."
                )
            )


        role = discord.utils.get(
            ctx.guild.roles,
            name="🔇 Muted"
        )


        if role in member.roles:

            await member.remove_roles(
                role
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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # WARN
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(
        self,
        ctx,
        member: discord.Member = None,
        *,
        reason="Não informado"
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário."
                )
            )


        if member.id not in self.warnings:

            self.warnings[member.id] = []


        self.warnings[member.id].append(
            {
                "motivo": reason,
                "moderador": ctx.author.name
            }
        )


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
{len(self.warnings[member.id])}
""",
            discord.Color.orange()
        )


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # VER WARNS
    # ==================================

    @commands.command(name="warns")
    async def warns(
        self,
        ctx,
        member: discord.Member = None
    ):


        member = member or ctx.author


        lista = self.warnings.get(
            member.id,
            []
        )


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

            texto += (
                f"**{numero}.** {warn['motivo']}\n"
            )


        embed = self.embed(
            "⚠️ Histórico de Warns",
            f"""
👤 **Usuário:**
{member.mention}


{texto}
""",
            discord.Color.orange()
        )


        await ctx.send(
            embed=embed
        )



    # ==================================
    # RETIRAR WARN
    # ==================================

    @commands.command(name="delwarn", aliases=["removerwarn"])
    @commands.has_permissions(manage_messages=True)
    async def delwarn(
        self,
        ctx,
        member: discord.Member = None,
        numero: int = None
    ):

        if member is None or numero is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Use assim: `!delwarn @usuário <número>`\nVeja os números com `!warns @usuário`."
                )
            )


        lista = self.warnings.get(member.id, [])


        if not lista or numero < 1 or numero > len(lista):

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    f"Não existe o warn número {numero} para {member.mention}."
                )
            )


        removido = lista.pop(numero - 1)


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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # LIMPAR CHAT
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(
        self,
        ctx,
        quantidade:int = 5
    ):


        await ctx.channel.purge(
            limit=quantidade + 1
        )


        embed = self.embed(
            "🧹 Chat Limpo",
            f"Foram apagadas **{quantidade} mensagens**.",
            discord.Color.blue()
        )


        mensagem = await ctx.send(
            embed=embed
        )


        await mensagem.delete(
            delay=5
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # LOCK - BLOQUEAR CANAL
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(
        self,
        ctx
    ):


        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False
        )


        embed = self.embed(
            "🔒 Canal Bloqueado",
            f"""
📌 **Canal:**
{ctx.channel.mention}

🛡️ **Responsável:**
{ctx.author.mention}

O canal foi bloqueado.
""",
            discord.Color.red()
        )


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # UNLOCK - DESBLOQUEAR CANAL
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(
        self,
        ctx
    ):


        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=True
        )


        embed = self.embed(
            "🔓 Canal Liberado",
            f"""
📌 **Canal:**
{ctx.channel.mention}

🛡️ **Responsável:**
{ctx.author.mention}

O canal foi desbloqueado.
""",
            discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # SLOWMODE
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(
        self,
        ctx,
        segundos:int = 5
    ):


        if segundos < 0 or segundos > 21600:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Use um valor entre 0 e 21600 segundos."
                )
            )


        await ctx.channel.edit(
            slowmode_delay=segundos
        )


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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # ALTERAR APELIDO
    # ==================================

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(
        self,
        ctx,
        member:discord.Member = None,
        *,
        nome=None
    ):


        if member is None:

            return await ctx.send(
                embed=self.embed(
                    "❌ Erro",
                    "Você precisa marcar um usuário."
                )
            )


        await member.edit(
            nick=nome
        )


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


        await ctx.send(
            embed=embed
        )


        await self.enviar_log(
            ctx.guild,
            embed
        )



    # ==================================
    # TRATAMENTO DE ERROS DO COG
    # ==================================

    async def cog_command_error(
        self,
        ctx,
        error
    ):


        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                embed=self.embed(
                    "🚫 Sem Permissão",
                    "Você não tem permissão para usar esse comando."
                )
            )


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                embed=self.embed(
                    "❌ Argumento Faltando",
                    f"Falta informar: `{error.param.name}`"
                )
            )


        if isinstance(
            error,
            commands.MemberNotFound
        ):

            return await ctx.send(
                embed=self.embed(
                    "❌ Usuário não encontrado",
                    "Não encontrei esse membro no servidor."
                )
            )


        raise error



# ==================================
# CARREGAR COG
# ==================================

async def setup(bot):

    await bot.add_cog(
        Moderation(bot)
            )
        
