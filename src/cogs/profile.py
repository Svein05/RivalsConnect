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
                
            if in_game_uid:
                embed.add_field(name="ID de Rivals", value=f"`{in_game_uid}`", inline=False)
                
            # Cargar los Lords del usuario
            user_lords = await db.get_user_lords(target.id)
            
            from src.utils.parser import APP_EMOJIS, get_hero_emoji
            from src.utils.heroes import get_hero_data
            
            if user_lords:
                lords_text = []
                for char, title in user_lords:
                    short_name = get_hero_data(char)["short_code"]
                    
                    if title == "Animated Lord" or title == "Champion":
                        t = "lordani"
                    else:
                        t = "lord"
                        
                    emoji_name = f"{short_name}_{t}"
                    if emoji_name in APP_EMOJIS:
                        emoji = APP_EMOJIS[emoji_name]
                    else:
                        emoji = "🌟" if (title == "Animated Lord" or title == "Champion") else "👑"
                            
                    lords_text.append(f"{emoji}")
                    
                formatted_lords = " ".join(lords_text)
                embed.add_field(name="Títulos de Personajes", value=formatted_lords, inline=False)
            
            # Cargar Top Personajes
            top_chars = await db.get_top_characters(target.id, limit=3)
            if top_chars:
                top_text = []
                for char_name, total_games, wins in top_chars:
                    emoji = get_hero_emoji(char_name, None, {}, True)
                    winrate = int((wins / total_games) * 100) if total_games > 0 else 0
                    top_text.append(f"{emoji} **{char_name}** | {winrate}% WR ({total_games} Partidas)")
                
                embed.add_field(name="Top Personajes", value="\n".join(top_text), inline=False)
                
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
                    m_outcome = match[6] or "Desconocido"
                    m_char = match[7] or "???"
                    m_mode = match[8] or "Desconocido"
                    m_map = match[9] or "Desconocido"
                    
                    if "victor" in m_outcome.lower() or "win" in m_outcome.lower():
                        prefix = "🔹 VICTORIA"
                    elif "defeat" in m_outcome.lower() or "loss" in m_outcome.lower() or "derrot" in m_outcome.lower():
                        prefix = "🔸 DERROTA"
                    else:
                        prefix = "⬜ TERMINADA"
                        
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
