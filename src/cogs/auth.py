import discord
from discord.ext import commands
from discord import app_commands
import random
import string
from src.database import db

# Diccionario global para guardar las interacciones pendientes y poder editarlas luego
pending_links = {}

class Auth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_code(self):
        chars = string.ascii_uppercase + string.digits
        return 'MR-' + ''.join(random.choices(chars, k=4))

    @app_commands.command(name="link", description="Genera un código para vincular tu app de Overwolf con Discord.")
    async def link(self, interaction: discord.Interaction):
        # Generar código
        code = self.generate_code()
        
        avatar_url = interaction.user.avatar.url if interaction.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        # Guardar en BD
        await db.set_user_code(
            discord_id=interaction.user.id,
            discord_name=interaction.user.name,
            discord_avatar=avatar_url,
            code=code
        )
        
        embed = discord.Embed(
            title="🔗 Vinculación de Cuenta",
            description=f"Hola **{interaction.user.name}**. Aquí tienes tu código secreto para conectar la app de Overwolf.",
            color=discord.Color.purple()
        )
        embed.add_field(name="Tu Código Secreto", value=f"```fix\n{code}\n```", inline=False)
        embed.add_field(name="Instrucciones", value="1. Abre la app de RivalsConnect en Overwolf.\n2. Pega este código en la ventana.\n3. ¡Listo! Todas tus partidas se registrarán aquí.")
        embed.set_footer(text="No compartas este código con nadie.")
        
        # Responder de forma efímera
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Guardar la interacción para editarla cuando la app de Overwolf confirme
        pending_links[code] = interaction

async def setup(bot):
    await bot.add_cog(Auth(bot))
