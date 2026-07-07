import discord
from discord.ext import commands
from discord.ui import View
from datetime import datetime


class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot



    # ==================================
    # EMBED PADRÃO
    # ==================================

    def embed(
        self,
        title,
        description,
        color=discord.Color.blurple()
    ):

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )

        embed.set_footer(
            text="🎫 Sistema Profissional de Tickets"
        )

        return embed



    # ==================================
    # CONFIGURAÇÃO AUTOMÁTICA
    # ==================================

    @commands.Cog.listener()
    async def on_ready(self):

        for guild in self.bot.guilds:


            # ------------------------------
            # Cargo Suporte
            # ------------------------------

            suporte = discord.utils.get(
                guild.roles,
                name="🛠️ Suporte"
            )

            if suporte is None:

                await guild.create_role(
                    name="🛠️ Suporte",
                    reason="Sistema de tickets"
                )



            # ------------------------------
            # Cargo Staff
            # ------------------------------

            staff = discord.utils.get(
                guild.roles,
                name="🛡️ Staff"
            )

            if staff is None:

                await guild.create_role(
                    name="🛡️ Staff",
                    reason="Sistema de tickets"
                )



            # ------------------------------
            # Categoria Atendimento
            # ------------------------------

            categoria = discord.utils.get(
                guild.categories,
                name="📂 Atendimento"
            )

            if categoria is None:

                await guild.create_category(
                    "📂 Atendimento",
                    reason="Sistema de tickets"
                )



            # ------------------------------
            # Canal Painel
            # ------------------------------

            painel = discord.utils.get(
                guild.text_channels,
                name="🎫・suporte"
            )


            if painel is None:

                painel = await guild.create_text_channel(
                    "🎫・suporte",
                    reason="Painel de tickets"
                )


                embed = self.embed(
                    "🎫 Central de Atendimento",
                    """
Bem-vindo ao atendimento! 👋


Selecione uma opção abaixo para abrir um ticket.


❓ **Dúvidas**
Perguntas gerais.


🛠️ **Suporte**
Problemas técnicos e ajuda.


🚨 **Denúncias**
Relatar usuários ou situações.


Nossa equipe responderá assim que possível.
""",
                    discord.Color.blue()
                )


                await painel.send(
                    embed=embed,
                    view=TicketPanel()
                )



            # ------------------------------
            # Canal de Logs
            # ------------------------------

            logs = discord.utils.get(
                guild.text_channels,
                name="📋・logs-tickets"
            )


            if logs is None:

                await guild.create_text_channel(
                    "📋・logs-tickets",
                    reason="Logs de tickets"
                )



    # ==================================
    # LOGS
    # ==================================

    async def enviar_log(
        self,
        guild,
        embed
    ):

        canal = discord.utils.get(
            guild.text_channels,
            name="📋・logs-tickets"
        )

        if canal:

            await canal.send(
                embed=embed
            )



# ==================================
# PAINEL DE TICKETS
# ==================================

class TicketPanel(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )



    @discord.ui.button(
        label="❓ Dúvidas",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_duvidas"
    )
    async def duvidas(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await criar_ticket(
            interaction,
            "❓ Dúvida"
        )



    @discord.ui.button(
        label="🛠️ Suporte",
        style=discord.ButtonStyle.success,
        custom_id="ticket_suporte"
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
        label="🚨 Denúncia",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_denuncia"
    )
    async def denuncia(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await criar_ticket(
            interaction,
            "🚨 Denúncia"
        )



# ==================================
# CRIAR TICKET
# ==================================

async def criar_ticket(
    interaction,
    tipo
):

    guild = interaction.guild
    membro = interaction.user



    # Verifica ticket existente

    for canal in guild.text_channels:

        if canal.name == f"ticket-{membro.name.lower()}":

            return await interaction.response.send_message(

                embed=discord.Embed(
                    title="❌ Ticket existente",
                    description="Você já possui um ticket aberto.",
                    color=discord.Color.red()
                ),

                ephemeral=True
            )



    suporte = discord.utils.get(
        guild.roles,
        name="🛠️ Suporte"
    )


    staff = discord.utils.get(
        guild.roles,
        name="🛡️ Staff"
    )


    categoria = discord.utils.get(
        guild.categories,
        name="📂 Atendimento"
    )



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



    canal = await guild.create_text_channel(

        name=f"ticket-{membro.name}",

        category=categoria,

        overwrites=permissoes,

        reason="Ticket criado"

    )



    await interaction.response.send_message(

        embed=discord.Embed(
            title="🎫 Ticket Criado",
            description=f"Seu atendimento foi criado em {canal.mention}",
            color=discord.Color.green()
        ),

        ephemeral=True
    )



    embed = discord.Embed(

        title="🎫 Novo Atendimento",

        description=f"""
Olá {membro.mention}! 👋


Seu ticket foi aberto.


📌 **Categoria:**
{tipo}


Explique sua situação com detalhes.


A equipe responderá em breve.
""",

        color=discord.Color.blue(),

        timestamp=datetime.utcnow()

    )


    embed.set_footer(
        text="Sistema Profissional de Atendimento"
    )



    await canal.send(

        embed=embed,

        view=TicketActions(
            membro
        )

    )



    log = discord.Embed(

        title="📩 Ticket Criado",

        description=f"""
👤 Usuário:
{membro.mention}


📂 Categoria:
{tipo}


📌 Canal:
{canal.mention}
""",

        color=discord.Color.green(),

        timestamp=datetime.utcnow()

    )


    # envia log se possível
    for cog in guild._state._get_client().cogs.values():

        if isinstance(cog, Tickets):

            await cog.enviar_log(
                guild,
                log
            )

            break



# ==================================
# AÇÕES DENTRO DO TICKET
# ==================================

class TicketActions(View):

    def __init__(self, dono):

        super().__init__(
            timeout=None
        )

        self.dono = dono



    # ==================================
    # ASSUMIR TICKET
    # ==================================

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

        if not await verificar_staff(interaction):

            return await interaction.response.send_message(

                embed=discord.Embed(
                    title="🚫 Sem permissão",
                    description="Apenas a equipe pode assumir tickets.",
                    color=discord.Color.red()
                ),

                ephemeral=True
            )



        embed = discord.Embed(

            title="🟢 Ticket Assumido",

            description=f"""
Este ticket foi assumido por:

🛡️ {interaction.user.mention}
""",

            color=discord.Color.green(),

            timestamp=datetime.utcnow()

        )


        await interaction.response.send_message(
            embed=embed
        )


        await interaction.channel.send(
            embed=embed
        )



    # ==================================
    # CHAMAR STAFF
    # ==================================

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
            name="🛡️ Staff"
        )


        if staff:

            await interaction.channel.send(
                f"📢 {staff.mention} solicitado no ticket."
            )


        await interaction.response.send_message(

            embed=discord.Embed(
                title="📢 Staff chamado",
                description="A equipe foi notificada.",
                color=discord.Color.blue()
            ),

            ephemeral=True
        )



    # ==================================
    # CHAMAR MEMBRO
    # ==================================

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

        if not await verificar_staff(interaction):

            return await interaction.response.send_message(

                embed=discord.Embed(
                    title="🚫 Sem permissão",
                    description="Apenas a equipe pode chamar membros.",
                    color=discord.Color.red()
                ),

                ephemeral=True
            )


        await interaction.channel.send(
            f"👤 {self.dono.mention}, você foi chamado pela equipe."
        )


        await interaction.response.send_message(

            embed=discord.Embed(
                title="👤 Membro chamado",
                description="O usuário foi notificado.",
                color=discord.Color.blurple()
            ),

            ephemeral=True
        )



    # ==================================
    # FECHAR TICKET
    # ==================================

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


        if not await verificar_staff(interaction):

            return await interaction.response.send_message(

                embed=discord.Embed(
                    title="🚫 Sem permissão",
                    description="Apenas Suporte ou Staff podem fechar tickets.",
                    color=discord.Color.red()
                ),

                ephemeral=True
            )



        embed = discord.Embed(

            title="🔒 Ticket Fechado",

            description=f"""
Este ticket foi fechado por:

🛡️ {interaction.user.mention}

O canal será apagado em 5 segundos.
""",

            color=discord.Color.orange(),

            timestamp=datetime.utcnow()

        )


        await interaction.response.send_message(
            embed=embed
        )


        # LOG

        log = discord.Embed(

            title="🔒 Ticket Fechado",

            description=f"""
📌 Canal:
{interaction.channel.name}


🛡️ Responsável:
{interaction.user.mention}
""",

            color=discord.Color.red(),

            timestamp=datetime.utcnow()

        )


        for cog in interaction.client.cogs.values():

            if isinstance(cog, Tickets):

                await cog.enviar_log(
                    interaction.guild,
                    log
                )

                break



        await interaction.channel.delete(
            delay=5
        )



# ==================================
# VERIFICAR STAFF
# ==================================

async def verificar_staff(
    interaction
):

    suporte = discord.utils.get(
        interaction.guild.roles,
        name="🛠️ Suporte"
    )


    staff = discord.utils.get(
        interaction.guild.roles,
        name="🛡️ Staff"
    )


    return (
        suporte in interaction.user.roles
        or
        staff in interaction.user.roles
        or
        interaction.user.guild_permissions.administrator
    )



# ==================================
# CARREGAR COG
# ==================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )
