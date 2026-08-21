import discord
from discord.ext import commands
from discord import app_commands
from src.database import db

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_servidor", description="Configura los 3 canales de RivalsConnect.")
    @app_commands.default_permissions(administrator=True)
    async def setup_servidor(
        self, 
        interaction: discord.Interaction, 
        canal_partidas: discord.TextChannel,
        canal_panel_vivo: discord.TextChannel,
        canal_leaderboard: discord.TextChannel
    ):
        await interaction.response.defer(ephemeral=True)
        
        # Enviar mensajes placeholder
        embed_panel = discord.Embed(
            title="📡 Panel de Información en Vivo",
            description="Esperando a que los jugadores se conecten...",
            color=discord.Color.blue()
        )
        msg_panel = await canal_panel_vivo.send(embed=embed_panel)
        
        embed_leaderboard = discord.Embed(
            title="🏆 Clasificación del Servidor",
            description="Nadie ha jugado partidas aún.",
            color=discord.Color.gold()
        )
        msg_leaderboard = await canal_leaderboard.send(embed=embed_leaderboard)
        
        # Guardar en base de datos
        import aiosqlite
        async with aiosqlite.connect("rivalsconnect.db") as database:
            await database.execute('''
                INSERT INTO guild_config (
                    guild_id, logs_channel_id, live_panel_channel_id, live_panel_msg_id, leaderboard_channel_id, leaderboard_msg_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    logs_channel_id = excluded.logs_channel_id,
                    live_panel_channel_id = excluded.live_panel_channel_id,
                    live_panel_msg_id = excluded.live_panel_msg_id,
                    leaderboard_channel_id = excluded.leaderboard_channel_id,
                    leaderboard_msg_id = excluded.leaderboard_msg_id
            ''', (
                interaction.guild_id,
                canal_partidas.id,
                canal_panel_vivo.id,
                msg_panel.id,
                canal_leaderboard.id,
                msg_leaderboard.id
            ))
            await database.commit()
            
        await interaction.followup.send("✅ Canales configurados con éxito. Los paneles se actualizarán automáticamente.")

async def setup(bot):
    await bot.add_cog(Settings(bot))
