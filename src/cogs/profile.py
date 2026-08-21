import discord
from discord.ext import commands
from discord import app_commands
from src.database import db
import logging

logger = logging.getLogger("profile_cog")

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Muestra el perfil y estadísticas de un usuario (o el tuyo)")
    async def profile(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        
        try:
            # Buscar en la DB
            user_data = await db.get_user(target.id)
            
            if not user_data:
                await interaction.response.send_message(
                    f"❌ **{target.display_name}** aún no ha vinculado su cuenta o no ha registrado ninguna partida en la base de datos.", 
                    ephemeral=True
                )
                return
                
            # Desempaquetar datos de la tupla (según schema de db.py)
            discord_id = user_data[0]
            discord_name = user_data[1]
            discord_avatar = user_data[2]
            link_code = user_data[3]
            is_playing = user_data[4]
            match_context = user_data[5]
            elo_score = user_data[6] or 0
            in_game_uid = user_data[7]
            
            # Crear Embed
            embed = discord.Embed(
                title=f"Perfil de Jugador: {target.display_name}",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
                
            estado = "🎮 En Partida" if is_playing else "💤 En Lobby / Desconectado"
            embed.add_field(name="Estado Actual", value=estado, inline=True)
            embed.add_field(name="Rank / ELO", value=f"⭐ **{elo_score}**", inline=True)
            
            if in_game_uid:
                embed.add_field(name="ID de Rivals", value=f"`{in_game_uid}`", inline=True)
                
            # Cargar los Lords del usuario
            user_lords = await db.get_user_lords(target.id)
            
            if user_lords:
                # user_lords es una lista de tuplas: (character_name, title_type)
                lords_text = []
                
                # Importar parser para usar la lógica de emojis global
                from src.utils.parser import APP_EMOJIS, format_char_name
                
                for char, title in user_lords:
                    short_name = format_char_name(char)
                    
                    if title == "Animated Lord" or title == "Champion":
                        t = "lordani"
                    else:
                        t = "lord"
                        
                    emoji_name = f"{short_name}_{t}"
                    
                    if emoji_name in APP_EMOJIS:
                        emoji = APP_EMOJIS[emoji_name]
                    else:
                        # Fallback
                        if title == "Animated Lord" or title == "Champion":
                            emoji = "🌟"
                        else:
                            emoji = "👑"
                            
                    # Formato ultracompacto: Solo Emoji
                    lords_text.append(f"{emoji}")
                    
                # Agruparlos solo con un espacio (sin texto ni puntos)
                formatted_lords = " ".join(lords_text)
                embed.add_field(name="Títulos de Personajes", value=formatted_lords, inline=False)
            else:
                embed.add_field(
                    name="Títulos de Personajes", 
                    value="*Este usuario no ha registrado ningún Lord/Champion con `/lord`.*", 
                    inline=False
                )
                
            # Cargar últimas 5 partidas
            recent_matches = await db.get_recent_matches(target.id, limit=5)
            if recent_matches:
                history_text = []
                for idx, match in enumerate(recent_matches, 1):
                    # match: elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, match_date
                    m_elo = match[0]
                    m_k = match[1]
                    m_d = match[2]
                    m_a = match[3]
                    m_dmg = match[4]
                    m_heal = match[5]
                    m_outcome = match[6] or "Desconocido"
                    m_char = match[7] or "???"
                    m_mode = match[8] or "Desconocido"
                    m_map = match[9] or "Desconocido"
                    m_date = match[10]
                    
                    if "victor" in m_outcome.lower() or "win" in m_outcome.lower():
                        prefix = "🔹 VICTORIA"
                    elif "defeat" in m_outcome.lower() or "loss" in m_outcome.lower() or "derrot" in m_outcome.lower():
                        prefix = "🔸 DERROTA"
                    else:
                        prefix = "⬜ TERMINADA"
                        
                    # Conseguir el emoji básico del personaje
                    from src.utils.parser import get_hero_emoji
                    emoji = get_hero_emoji(m_char, None, {}, True)
                    
                    line = f"{prefix} | {emoji} `{m_k}/{m_d}/{m_a}` | {m_mode} | {m_map}"
                        
                    history_text.append(line)
                    
                embed.add_field(name="Historial Reciente (Últimas 5)", value="\n".join(history_text), inline=False)
            else:
                embed.add_field(name="Historial Reciente", value="*No hay partidas jugadas recientemente.*", inline=False)
                
            embed.set_footer(text="RivalsConnect Database")
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error ejecutando /profile: {e}")
            await interaction.response.send_message("❌ Ocurrió un error al buscar el perfil. Inténtalo de nuevo más tarde.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Profile(bot))
