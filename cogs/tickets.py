import discord
import asyncio

from datetime import datetime
from discord.ext import commands
from discord.ui import View


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

CARGO_STAFF = "🛡️ Staff"
CARGO_SUPORTE = "🛠️ Suporte"

CATEGORIA_TICKETS = "📂 Atendimento"

CANAL_PAINEL = "🎫・suporte"
CANAL_LOGS = "📋・logs-tickets"


# ==========================================================
# EMBED PADRÃO
# ==========================================================

def criar_embed(
    titulo,
    descricao,
    cor=discord.Color.blurple()
):

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.utcnow()
    )

    embed.set_footer(
        text="🎫 Sistema Profissional de Tickets"
    )

    return embed



# ==========================================================
# VERIFICA EQUIPE
# ==========================================================

def eh_staff(member):

    if member.guild_permissions.administrator:
        return True


    cargos = [
        cargo.name
        for cargo in member.roles
    ]


    return (
        CARGO_STAFF in cargos
        or
        CARGO_SUPORTE in cargos
    )



# ==========================================================
# COG PRINCIPAL
# ==========================================================

class Tickets(commands.Cog):


    def __init__(self, bot):

        self.bot = bot



    # ======================================================
    # INICIAR SISTEMA
    # ======================================================

    @commands.Cog.listener()
    async def on_ready(self):

        print("🎫 Sistema de tickets carregado.")


        # mantém botões funcionando após reiniciar

        self.bot.add_view(
            PainelTickets()
        )


        for guild in self.bot.guilds:


            # -----------------------------
            # CRIAR CARGO STAFF
            # -----------------------------

            staff = discord.utils.get(
                guild.roles,
                name=CARGO_STAFF
            )


            if staff is None:

                await guild.create_role(
                    name=CARGO_STAFF,
                    reason="Sistema de tickets"
                )



            # -----------------------------
            # CRIAR CARGO SUPORTE
            # -----------------------------

            suporte = discord.utils.get(
                guild.roles,
                name=CARGO_SUPORTE
            )


            if suporte is None:

                await guild.create_role(
                    name=CARGO_SUPORTE,
                    reason="Sistema de tickets"
                )



            # -----------------------------
            # CRIAR CATEGORIA
            # -----------------------------

            categoria = discord.utils.get(
                guild.categories,
                name=CATEGORIA_TICKETS
            )


            if categoria is None:

                await guild.create_category(
                    CATEGORIA_TICKETS,
                    reason="Sistema de tickets"
                )



            # -----------------------------
            # CRIAR LOGS
            # -----------------------------

            logs = discord.utils.get(
                guild.text_channels,
                name=CANAL_LOGS
            )


            if logs is None:

                await guild.create_text_channel(
                    CANAL_LOGS,
                    reason="Sistema de tickets"
                )



            # -----------------------------
            # CRIAR PAINEL
            # -----------------------------

            painel = discord.utils.get(
                guild.text_channels,
                name=CANAL_PAINEL
            )


            if painel is None:

                painel = await guild.create_text_channel(
                    CANAL_PAINEL,
                    reason="Sistema de tickets"
                )


                embed = criar_embed(
                    "🎫 Central de Atendimento",
                    """
Bem-vindo ao suporte!

Escolha uma opção abaixo:

❓ **Dúvidas**
Perguntas gerais.

🛠️ **Suporte**
Ajuda com problemas.

🚨 **Denúncias**
Relatar usuários ou situações.

Nossa equipe responderá em breve.
""",
                    discord.Color.blue()
                )


                if guild.icon:

                    embed.set_thumbnail(
                        url=guild.icon.url
                    )


                await painel.send(
                    embed=embed,
                    view=PainelTickets()
                )



    # ======================================================
    # ENVIO DE LOG
    # ======================================================

    async def enviar_log(
        self,
        guild,
        embed
    ):

        canal = discord.utils.get(
            guild.text_channels,
            name=CANAL_LOGS
        )


        if canal:

            await canal.send(
                embed=embed
            )



# ==========================================================
# PAINEL DE BOTÕES
# ==========================================================

class PainelTickets(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="❓ Dúvidas",
        style=discord.ButtonStyle.primary,
        custom_id="abrir_duvidas"
    )
    async def duvidas(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await criar_ticket(
            interaction,
            "❓ Dúvidas"
        )



    @discord.ui.button(
        label="🛠️ Suporte",
        style=discord.ButtonStyle.success,
        custom_id="abrir_suporte"
    )
    async def suporte(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await criar_ticket(
            interaction,
            "🛠️ Suporte"
        )



    @discord.ui.button(
        label="🚨 Denúncias",
        style=discord.ButtonStyle.danger,
        custom_id="abrir_denuncia"
    )
    async def denuncia(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await criar_ticket(
            interaction,
            "🚨 Denúncias"
        )



# ==========================================================
# CRIAÇÃO DO TICKET
# ==========================================================

async def criar_ticket(
    interaction: discord.Interaction,
    tipo
):

    guild = interaction.guild
    membro = interaction.user



    # ----------------------------------
    # VERIFICAR TICKET EXISTENTE
    # ----------------------------------

    for canal in guild.text_channels:

        if canal.name == f"ticket-{membro.id}":

            return await interaction.response.send_message(

                embed=criar_embed(
                    "❌ Ticket existente",
                    "Você já possui um ticket aberto.",
                    discord.Color.red()
                ),

                ephemeral=True
            )



    # ----------------------------------
    # PEGAR CARGOS
    # ----------------------------------

    suporte = discord.utils.get(
        guild.roles,
        name=CARGO_SUPORTE
    )


    staff = discord.utils.get(
        guild.roles,
        name=CARGO_STAFF
    )



    # ----------------------------------
    # PEGAR CATEGORIA
    # ----------------------------------

    categoria = discord.utils.get(
        guild.categories,
        name=CATEGORIA_TICKETS
    )


    if categoria is None:

        return await interaction.response.send_message(

            "❌ Categoria de tickets não encontrada.",

            ephemeral=True
        )



    # ----------------------------------
    # PERMISSÕES
    # ----------------------------------

    permissoes = {


        guild.default_role:

        discord.PermissionOverwrite(

            view_channel=False

        ),



        membro:

        discord.PermissionOverwrite(

            view_channel=True,

            send_messages=True,

            read_message_history=True

        )

    }



    if suporte:

        permissoes[suporte] = discord.PermissionOverwrite(

            view_channel=True,

            send_messages=True,

            read_message_history=True

        )



    if staff:

        permissoes[staff] = discord.PermissionOverwrite(

            view_channel=True,

            send_messages=True,

            manage_channels=True,

            read_message_history=True

        )



    # ----------------------------------
    # CRIAR CANAL
    # ----------------------------------

    canal = await guild.create_text_channel(

        name=f"ticket-{membro.id}",

        category=categoria,

        overwrites=permissoes,

        reason="Novo ticket criado"

    )



    # ----------------------------------
    # RESPONDER BOTÃO
    # ----------------------------------

    await interaction.response.send_message(

        embed=criar_embed(

            "🎫 Ticket criado",

            f"Seu ticket foi criado em {canal.mention}",

            discord.Color.green()

        ),

        ephemeral=True

    )



    # ----------------------------------
    # EMBED DO TICKET
    # ----------------------------------

    embed = criar_embed(

        "🎫 Atendimento iniciado",

        f"""
Olá {membro.mention}! 👋


Seu ticket foi aberto.


📌 **Categoria:**

{tipo}


Explique detalhadamente o motivo do contato.


A equipe responderá assim que possível.
""",

        discord.Color.blue()

    )


    await canal.send(

        embed=embed,

        view=BotoesTicket(
            membro
        )

    )



    # ----------------------------------
    # LOG DE ABERTURA
    # ----------------------------------

    log = criar_embed(

        "📩 Ticket Aberto",

        f"""
👤 Usuário:

{membro.mention}


📂 Categoria:

{tipo}


📌 Canal:

{canal.mention}
""",

        discord.Color.green()

    )


    for cog in interaction.client.cogs.values():

        if isinstance(cog, Tickets):

            await cog.enviar_log(

                guild,

                log

            )

            break



# ==========================================================
# BOTÕES DENTRO DO TICKET
# ==========================================================

class BotoesTicket(View):

    def __init__(self, dono):

        super().__init__(
            timeout=None
        )

        self.dono = dono



    # ======================================================
    # ASSUMIR TICKET
    # ======================================================

    @discord.ui.button(
        label="🟢 Assumir Ticket",
        style=discord.ButtonStyle.success,
        custom_id="assumir_ticket"
    )
    async def assumir(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):


        if not eh_staff(interaction.user):

            return await interaction.response.send_message(

                embed=criar_embed(
                    "🚫 Sem permissão",
                    "Apenas a equipe pode assumir tickets.",
                    discord.Color.red()
                ),

                ephemeral=True

            )



        embed = criar_embed(

            "🟢 Ticket assumido",

            f"""
Este ticket foi assumido por:

🛡️ {interaction.user.mention}
""",

            discord.Color.green()

        )


        await interaction.response.send_message(

            embed=embed

        )


        await interaction.channel.send(

            embed=embed

        )



    # ======================================================
    # CHAMAR STAFF
    # ======================================================

    @discord.ui.button(
        label="📢 Chamar Staff",
        style=discord.ButtonStyle.primary,
        custom_id="chamar_staff"
    )
    async def chamar_staff(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):


        staff = discord.utils.get(

            interaction.guild.roles,

            name=CARGO_STAFF

        )


        if staff:

            await interaction.channel.send(

                f"📢 {staff.mention} foi solicitado neste ticket."

            )



        await interaction.response.send_message(

            embed=criar_embed(

                "📢 Staff chamado",

                "A equipe foi notificada.",

                discord.Color.blue()

            ),

            ephemeral=True

        )



    # ======================================================
    # CHAMAR MEMBRO
    # ======================================================

    @discord.ui.button(
        label="👤 Chamar Membro",
        style=discord.ButtonStyle.secondary,
        custom_id="chamar_membro"
    )
    async def chamar_membro(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):


        if not eh_staff(interaction.user):

            return await interaction.response.send_message(

                embed=criar_embed(

                    "🚫 Sem permissão",

                    "Apenas a equipe pode chamar o membro.",

                    discord.Color.red()

                ),

                ephemeral=True

            )



        await interaction.channel.send(

            f"👤 {self.dono.mention}, a equipe solicitou sua presença."

        )



        await interaction.response.send_message(

            embed=criar_embed(

                "👤 Usuário chamado",

                "O membro foi notificado.",

                discord.Color.blurple()

            ),

            ephemeral=True

        )



    # ======================================================
    # FECHAR TICKET
    # ======================================================

    @discord.ui.button(
        label="🔒 Fechar Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="fechar_ticket"
    )
    async def fechar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):


        if not eh_staff(interaction.user):

            return await interaction.response.send_message(

                embed=criar_embed(

                    "🚫 Sem permissão",

                    "Somente Staff ou Suporte podem fechar tickets.",

                    discord.Color.red()

                ),

                ephemeral=True

            )



        log = criar_embed(

            "🔒 Ticket fechado",

            f"""
📌 Canal:

{interaction.channel.name}


🛡️ Fechado por:

{interaction.user.mention}
""",

            discord.Color.red()

        )



        for cog in interaction.client.cogs.values():

            if isinstance(cog, Tickets):

                await cog.enviar_log(

                    interaction.guild,

                    log

                )

                break



        await interaction.response.send_message(

            embed=criar_embed(

                "🔒 Ticket fechado",

                "Este ticket será apagado em 5 segundos.",

                discord.Color.orange()

            )

        )



        await asyncio.sleep(5)



        await interaction.channel.delete()



# ==========================================================
# SETUP DO COG
# ==========================================================

async def setup(bot):

    await bot.add_cog(

        Tickets(bot)

    )
