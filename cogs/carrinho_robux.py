# carrinho_robux.py
# Sistema completo de carrinho de Robux com aprovação em 2 passos
# Cole isso em: cogs/carrinho_robux.py

import discord
import json
import os
import random
import math
from datetime import datetime, timezone
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput

# =========== FUNÇÕES AUXILIARES ===========

def gerar_id_carrinho():
    return f"cart_{random.randint(100000, 999999)}"

def formatar_valor_brl(valor):
    return f"{valor:.2f}".replace(".", ",")

def embed_padrao(titulo, descricao, cor=discord.Color.blurple()):
    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="🛒 Sistema de Loja")
    return embed

def calcular_valores_robux(quantidade, com_taxa, preco_k, taxa_percentual=30):
    """Calcula valores de Robux"""
    valor_reais = (quantidade / 1000) * preco_k
    if com_taxa:
        fator = 1 - (taxa_percentual / 100)
        valor_gamepass = math.ceil(quantidade / fator)
    else:
        valor_gamepass = quantidade
    return valor_reais, valor_gamepass

# =========== MODALS ===========

class ModalCategoria(Modal):
    """Modal pra escolher categoria do carrinho"""
    categoria = TextInput(
        label="Categoria",
        placeholder="ex: Robux, Passes, Itens",
        min_length=1,
        max_length=50
    )
    
    def __init__(self, cog, carrinho_id):
        super().__init__(title="Selecione a Categoria")
        self.cog = cog
        self.carrinho_id = carrinho_id
    
    async def on_submit(self, interaction: discord.Interaction):
        categoria = self.categoria.value.strip()
        
        if self.carrinho_id not in self.cog.dados.get("carrinhos", {}):
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Erro", "Carrinho não encontrado.", discord.Color.red()),
                ephemeral=True
            )
        
        carrinho = self.cog.dados["carrinhos"][self.carrinho_id]
        carrinho["categoria"] = categoria
        self.cog.salvar()
        
        # Mostra resumo
        valor_reais_fmt = formatar_valor_brl(carrinho["valor_reais"])
        metodo_txt = "Gamepass (com taxa)" if carrinho["metodo"] == "com_taxa" else "Trade/Grupo (sem taxa)"
        
        embed = embed_padrao(
            "📋 Resumo do Carrinho",
            f"👤 **Nick Roblox:** {carrinho['nick_roblox']}\n"
            f"🎮 **Robux:** {carrinho['quantidade_robux']:,}\n"
            f"📂 **Categoria:** {categoria}\n"
            f"💳 **Método:** {metodo_txt}\n"
            f"💰 **Valor:** R$ {valor_reais_fmt}\n\n"
            f"Clique abaixo para confirmar ou cancelar.",
            discord.Color.gold()
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=ViewConfirmarCarrinho(self.cog, self.carrinho_id),
            ephemeral=True
        )

class ModalCarrinho(Modal):
    """Modal inicial do carrinho"""
    nick_roblox = TextInput(
        label="Nick do Roblox (nick de criação)",
        placeholder="seu_nick_aqui",
        min_length=3,
        max_length=20
    )
    quantidade = TextInput(
        label="Quantidade de Robux",
        placeholder="5000",
        min_length=1,
        max_length=10
    )
    metodo = TextInput(
        label="Método (com_taxa ou sem_taxa)",
        placeholder="com_taxa",
        min_length=7,
        max_length=10
    )
    
    def __init__(self, cog):
        super().__init__(title="Comprar Robux")
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        nick = self.nick_roblox.value.strip()
        
        # Validar nick
        if not (3 <= len(nick) <= 20):
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Nick inválido", "Nick precisa ter 3-20 caracteres.", discord.Color.red()),
                ephemeral=True
            )
        
        if not all(c.isalnum() or c == "_" for c in nick):
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Nick inválido", "Só letras, números e underscore.", discord.Color.red()),
                ephemeral=True
            )
        
        # Validar quantidade
        try:
            quantidade = int(self.quantidade.value.strip())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Quantidade inválida", "Use um número válido.", discord.Color.red()),
                ephemeral=True
            )
        
        # Validar método
        metodo = self.metodo.value.strip().lower()
        if metodo not in ["com_taxa", "sem_taxa"]:
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Método inválido", "Use 'com_taxa' ou 'sem_taxa'.", discord.Color.red()),
                ephemeral=True
            )
        
        # Verificar preço configurado
        preco_k = self.cog.dados.get("config", {}).get("robux_preco_k")
        if not preco_k:
            return await interaction.response.send_message(
                embed=embed_padrao("❌ Preço não configurado", "Admin não setou o preço do Robux ainda.", discord.Color.red()),
                ephemeral=True
            )
        
        # Calcular valores
        com_taxa = metodo == "com_taxa"
        taxa_percentual = self.cog.dados.get("config", {}).get("robux_taxa_percentual", 30)
        valor_reais, valor_gamepass = calcular_valores_robux(quantidade, com_taxa, preco_k, taxa_percentual)
        
        # Criar carrinho
        carrinho_id = gerar_id_carrinho()
        self.cog.dados.setdefault("carrinhos", {})[carrinho_id] = {
            "usuario_id": interaction.user.id,
            "usuario_nome": interaction.user.name,
            "nick_roblox": nick,
            "quantidade_robux": quantidade,
            "metodo": metodo,
            "valor_reais": valor_reais,
            "valor_gamepass": valor_gamepass,
            "categoria": None,
            "status": "awaiting_category",  # Aguardando escolha de categoria
            "approved_by_user": False,
            "approved_by_admin": False,
            "admin_que_aprovou": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.cog.salvar()
        
        # Pedir categoria
        await interaction.response.send_modal(ModalCategoria(self.cog, carrinho_id))

# =========== VIEWS ===========

class ViewConfirmarCarrinho(View):
    """View pra confirmar/cancelar carrinho após categoria"""
    def __init__(self, cog, carrinho_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.carrinho_id = carrinho_id
    
    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.green)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        carrinho = self.cog.dados["carrinhos"].get(self.carrinho_id)
        if not carrinho:
            return await interaction.response.send_message("Carrinho não encontrado.", ephemeral=True)
        
        carrinho["approved_by_user"] = True
        carrinho["status"] = "awaiting_admin_approval"
        self.cog.salvar()
        
        # Notificar admins
        guild = interaction.guild
        if guild:
            admins_ids = set()
            
            # Pegar donos + aprovadores
            if "LOJA_DONO_IDS" in os.environ:
                for pid in os.environ["LOJA_DONO_IDS"].split(","):
                    if pid.strip().isdigit():
                        admins_ids.add(int(pid.strip()))
            
            for membro in guild.members:
                if membro.guild_permissions.administrator:
                    admins_ids.add(membro.id)
            
            # Enviar DM pra cada admin
            for admin_id in admins_ids:
                try:
                    admin = await interaction.client.fetch_user(admin_id)
                    embed = embed_padrao(
                        "🔔 Novo Carrinho Aguardando Aprovação",
                        f"👤 **Usuário:** {carrinho['usuario_nome']}\n"
                        f"🎮 **Nick Roblox:** {carrinho['nick_roblox']}\n"
                        f"💰 **Robux:** {carrinho['quantidade_robux']:,}\n"
                        f"📂 **Categoria:** {carrinho['categoria']}\n"
                        f"💵 **Valor:** R$ {formatar_valor_brl(carrinho['valor_reais'])}\n"
                        f"🆔 **ID:** `{self.carrinho_id}`\n\n"
                        f"Use `/loja-carrinho-aprovar {self.carrinho_id}` pra aprovar.",
                        discord.Color.gold()
                    )
                    await admin.send(embed=embed)
                except:
                    pass
        
        await interaction.response.send_message(
            embed=embed_padrao("✅ Carrinho Enviado", "Aguardando aprovação de um admin...", discord.Color.green()),
            ephemeral=True
        )
    
    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.dados["carrinhos"].pop(self.carrinho_id, None)
        self.cog.salvar()
        
        await interaction.response.send_message(
            embed=embed_padrao("❌ Cancelado", "Seu carrinho foi cancelado.", discord.Color.red()),
            ephemeral=True
        )

class ViewAprovarCarrinho(View):
    """View pra admin aprovar/rejeitar"""
    def __init__(self, cog, carrinho_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.carrinho_id = carrinho_id
    
    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.green)
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verificar se é admin
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        
        carrinho = self.cog.dados["carrinhos"].get(self.carrinho_id)
        if not carrinho:
            return await interaction.response.send_message("Carrinho não encontrado.", ephemeral=True)
        
        carrinho["approved_by_admin"] = True
        carrinho["admin_que_aprovou"] = interaction.user.id
        carrinho["status"] = "approved"
        self.cog.salvar()
        
        # Avisar o usuário via DM
        try:
            user = await interaction.client.fetch_user(carrinho["usuario_id"])
            embed = embed_padrao(
                "✅ Carrinho Aprovado!",
                f"Seu carrinho de {carrinho['quantidade_robux']:,} Robux foi aprovado!\n\n"
                f"Agora é só fazer o pagamento via PIX.\n"
                f"Chave PIX será enviada em breve.",
                discord.Color.green()
            )
            await user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(
            embed=embed_padrao("✅ Aprovado", f"Carrinho `{self.carrinho_id}` aprovado!", discord.Color.green()),
            ephemeral=True
        )
    
    @discord.ui.button(label="❌ Rejeitar", style=discord.ButtonStyle.red)
    async def rejeitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        
        carrinho = self.cog.dados["carrinhos"].get(self.carrinho_id)
        if not carrinho:
            return await interaction.response.send_message("Carrinho não encontrado.", ephemeral=True)
        
        carrinho["status"] = "rejected"
        self.cog.salvar()
        
        try:
            user = await interaction.client.fetch_user(carrinho["usuario_id"])
            await user.send(embed=embed_padrao(
                "❌ Carrinho Rejeitado",
                "Seu carrinho foi rejeitado. Você pode criar um novo.",
                discord.Color.red()
            ))
        except:
            pass
        
        await interaction.response.send_message(
            embed=embed_padrao("❌ Rejeitado", f"Carrinho `{self.carrinho_id}` rejeitado.", discord.Color.red()),
            ephemeral=True
        )

# =========== COG ===========

class CarrinhoRobux(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Carregar dados do arquivo principal
        self.dados = {}
        self._load_data()
    
    def _load_data(self):
        """Carrega dados compartilhados com loja.py"""
        data_dir = os.getenv("LOJA_DATA_DIR") or os.path.dirname(__file__)
        data_file = os.path.join(data_dir, "loja_data.json")
        
        if os.path.exists(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    self.dados = json.load(f)
            except:
                self.dados = {"config": {}, "carrinhos": {}}
        else:
            self.dados = {"config": {}, "carrinhos": {}}
        
        self.dados.setdefault("carrinhos", {})
        self.dados.setdefault("config", {})
    
    def salvar(self):
        """Salva dados"""
        data_dir = os.getenv("LOJA_DATA_DIR") or os.path.dirname(__file__)
        data_file = os.path.join(data_dir, "loja_data.json")
        
        try:
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar: {e}")
    
    async def cog_load(self):
        """Registra views"""
        for carrinho_id, carrinho in self.dados.get("carrinhos", {}).items():
            if carrinho.get("status") == "awaiting_admin_approval":
                self.bot.add_view(ViewAprovarCarrinho(self, carrinho_id))
    
    @commands.hybrid_command(name="loja-carrinho-novo")
    async def loja_carrinho_novo(self, ctx):
        """Inicia novo carrinho de Robux"""
        await ctx.interaction.response.send_modal(ModalCarrinho(self))
    
    @commands.hybrid_command(name="loja-carrinho-aprovar")
    @app_commands.describe(carrinho_id="ID do carrinho (ex: cart_123456)")
    async def loja_carrinho_aprovar(self, ctx, carrinho_id: str):
        """Admin aprova carrinho"""
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=embed_padrao("❌ Sem permissão", "Só admins.", discord.Color.red()), ephemeral=True)
        
        carrinho = self.dados.get("carrinhos", {}).get(carrinho_id)
        if not carrinho:
            return await ctx.send(embed=embed_padrao("❌ Carrinho não encontrado", f"ID: `{carrinho_id}`", discord.Color.red()), ephemeral=True)
        
        await ctx.send(
            embed=embed_padrao(
                "🔔 Aprovar Carrinho",
                f"👤 {carrinho['usuario_nome']}\n"
                f"🎮 {carrinho['quantidade_robux']:,} Robux\n"
                f"💰 R$ {formatar_valor_brl(carrinho['valor_reais'])}",
                discord.Color.gold()
            ),
            view=ViewAprovarCarrinho(self, carrinho_id)
        )
    
    @commands.hybrid_command(name="loja-carrinhos-pendentes")
    async def loja_carrinhos_pendentes(self, ctx):
        """Lista carrinhos aguardando aprovação"""
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=embed_padrao("❌ Sem permissão", "Só admins.", discord.Color.red()), ephemeral=True)
        
        pendentes = {
            cid: c for cid, c in self.dados.get("carrinhos", {}).items()
            if c.get("status") == "awaiting_admin_approval"
        }
        
        if not pendentes:
            return await ctx.send(embed=embed_padrao("✅ Nada pendente", "Nenhum carrinho aguardando.", discord.Color.green()))
        
        embed = embed_padrao("⏳ Carrinhos Pendentes", f"Total: {len(pendentes)}")
        
        for cid, carrinho in pendentes.items():
            embed.add_field(
                name=f"{carrinho['usuario_nome']} • `{cid}`",
                value=f"🎮 {carrinho['quantidade_robux']:,} Robux\n💰 R$ {formatar_valor_brl(carrinho['valor_reais'])}\n📂 {carrinho['categoria']}",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CarrinhoRobux(bot))
