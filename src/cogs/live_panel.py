import discord
from discord.ext import commands
import aiosqlite
import logging

logger = logging.getLogger("live_panel")

async def update_live_panel(bot, guild_id):
    """Actualiza el panel en vivo estático con el estado actual de los usuarios."""
    try:
        async with aiosqlite.connect("rivalsconnect.db") as db:
            # Recuperar configuración del guild
            async with db.execute('SELECT live_panel_channel_id, live_panel_msg_id FROM guild_config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return
                channel_id, msg_id = row
                
            async with db.execute('SELECT discord_id, discord_name, is_playing, match_context, status FROM users') as cursor:
                users = await cursor.fetchall()
                
        channel = bot.get_channel(channel_id)
        if not channel:
            return
            
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            # Si el mensaje fue borrado manualmente, no hacemos nada para evitar spam
            return
            
        embed = discord.Embed(
            title="📡 Panel de Información (Live)",
            description="Estado actual de los agentes de la comunidad.",
            color=discord.Color.dark_blue(),
            timestamp=discord.utils.utcnow()
        )
        
        in_game = []
        in_lobby = []
        offline = []
        
        for user in users:
            d_id, name, is_playing, context, status = user
            if status == "En Partida" or is_playing:
                in_game.append(f"🟢 **{name}** : En Partida | {context if context else 'Sin detalles'}")
            elif status == "Lobby":
                in_lobby.append(f"🟡 **{name}** : En Lobby (Buscando partida)")
            else:
                offline.append(f"🔴 **{name}** : Desconectado")
                
        if in_game:
            embed.add_field(name="🎮 En Partida", value="\n".join(in_game), inline=False)
        else:
            embed.add_field(name="🎮 En Partida", value="*Nadie está jugando en este momento.*", inline=False)
            
        if in_lobby:
            embed.add_field(name="☕ En Lobby", value="\n".join(in_lobby), inline=False)
            
        if offline:
            embed.add_field(name="💤 Desconectados", value="\n".join(offline), inline=False)
            
        embed.set_footer(text="RivalsConnect | Actualización automática")
        await msg.edit(embed=embed)
        
    except Exception as e:
        logger.error(f"Error actualizando panel en vivo: {e}")

async def setup(bot):
    # En este cog no hay comandos, solo lógica utilitaria,
    # pero el setup es necesario para que load_extension no falle.
    pass
