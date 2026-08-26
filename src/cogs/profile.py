import discord
from discord.ext import commands
from discord import app_commands
from src.database import db
from src.utils.i18n import t, translate_rank
from src.utils.rivalsmeta import fetch_player_from_rivalsmeta
import logging

logger = logging.getLogger("profile_cog")

ROLE_FALLBACK = {
    "vanguard": "🛡️",
    "duelist": "⚔️",
    "strategist": "💚"
}

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Muestra el perfil y estadísticas de un usuario (o el tuyo)")
    async def profile(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        lang = await db.get_user_language(interaction.user.id)
        
        await interaction.response.defer()
        
        try:
            # Buscar en la DB
            user_data = await db.get_user(target.id)
            
            if not user_data:
                await interaction.followup.send(
                    t("profile_no_account", lang, name=target.display_name),
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
            
            # Sincronización controlada con RivalsMeta si el usuario tiene UID
            meta_data = None
            if in_game_uid:
                meta_data = await fetch_player_from_rivalsmeta(in_game_uid)
                if meta_data:
                    rivals_elo = int(meta_data.get("elo", 0))
                    # Si RivalsMeta tiene un ELO válido y es distinto, calibramos
                    if rivals_elo > 0 and rivals_elo != elo_score:
                        await db.update_user_elo(target.id, rivals_elo, in_game_uid)
                        elo_score = rivals_elo
            
            # Crear Embed
            rank_key = await db.get_user_rank(elo_score)
            rank_name = translate_rank(rank_key, lang)
            embed = discord.Embed(
                title=t("profile_title", lang, name=target.display_name),
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
                
            embed.add_field(name=t("profile_comp_rank", lang), value=f"**{rank_name}** ({elo_score} ELO)", inline=False)
            if in_game_uid:
                embed.add_field(name=t("profile_rivals_id", lang), value=f"`{in_game_uid}`", inline=False)
                
            # Estadísticas Globales de RivalsMeta (si están disponibles)
            if meta_data and meta_data.get("ranked_matches", 0) > 0:
                season_num = meta_data.get("active_season", 0)
                matches = meta_data.get("ranked_matches", 0)
                wr = meta_data.get("ranked_wr", 0.0)
                kda = meta_data.get("kda", 0.0)
                k = meta_data.get("kills", 0)
                d = meta_data.get("deaths", 0)
                a = meta_data.get("assists", 0)
                
                global_lines = [
                    f"• **{t('profile_global_matches', lang)}:** `{matches}` ({wr}% WR)",
                    f"• **{t('profile_global_kda', lang)}:** `{kda}` ({k}K / {d}D / {a}A)",
                    f"*{t('profile_synced_rivalsmeta', lang)}*"
                ]
                embed.add_field(
                    name=t("profile_global_section", lang, season=season_num),
                    value="\n".join(global_lines),
                    inline=False
                )
                
            # Cargar los Lords del usuario
            user_lords = await db.get_user_lords(target.id)
            
            from src.utils.parser import APP_EMOJIS, get_hero_emoji
            from src.utils.heroes import get_hero_data
            
            if user_lords:
                lords_text = []
                for char, title in user_lords:
                    short_name = get_hero_data(char)["short_code"]
                    
                    if title == "Animated Lord" or title == "Champion":
                        title_suffix = "lordani"
                    else:
                        title_suffix = "lord"
                        
                    emoji_name = f"{short_name}_{title_suffix}"
                    if emoji_name in APP_EMOJIS:
                        emoji = APP_EMOJIS[emoji_name]
                    else:
                        emoji = "🌟" if (title == "Animated Lord" or title == "Champion") else "👑"
                            
                    lords_text.append(f"{emoji}")
                    
                formatted_lords = " ".join(lords_text)
                embed.add_field(name=t("profile_titles_section", lang), value=formatted_lords, inline=False)
            
            # Crear diccionario falso para que get_hero_emoji procese los Lords correctamente
            fake_lords_dict = {}
            if user_lords:
                fake_lords_dict[str(target.id)] = {char.upper(): title for char, title in user_lords}
                
            # Cargar Top Personajes
            top_chars = await db.get_top_characters(target.id, limit=5)
            if top_chars:
                top_text = []
                for char_name, total_games, wins in top_chars:
                    emoji = get_hero_emoji(char_name, str(target.id), fake_lords_dict, True)
                    winrate = int((wins / total_games) * 100) if total_games > 0 else 0
                    top_text.append(t("profile_top_format", lang, emoji=emoji, char=char_name, wr=winrate, games=total_games))
                
                embed.add_field(name=t("profile_top_section", lang), value="\n".join(top_text), inline=False)

            # --- Stats por Rol ---
            role_stats = await db.get_top_roles(target.id)
            role_order = sorted(["vanguard", "duelist", "strategist"], key=lambda r: role_stats.get(r, {}).get("total", 0), reverse=True)
            role_lines = []
            for role_key_r in role_order:
                data = role_stats.get(role_key_r)
                if data and data["total"] > 0:
                    wr = int((data["wins"] / data["total"]) * 100)
                    emoji_name = f"{role_key_r}_icon"
                    emoji = APP_EMOJIS.get(emoji_name, ROLE_FALLBACK.get(role_key_r, "❓"))
                    label = t(f"role_{role_key_r}", lang)
                    role_lines.append(t("profile_role_format", lang, emoji=emoji, role=label, wr=wr, games=data["total"]))
            if role_lines:
                embed.add_field(name=t("profile_role_stats", lang), value="\n".join(role_lines), inline=False)
                
            # Cargar últimas 5 partidas
            recent_matches = await db.get_recent_matches(target.id, limit=5)
            if recent_matches:
                history_text = []
                for idx, match in enumerate(recent_matches, 1):
                    m_k = match[1]
                    m_d = match[2]
                    m_a = match[3]
                    m_outcome = match[6] or ""
                    m_char = match[7] or "???"
                    
                    m_mode_raw = match[8] or "unknown"
                    m_mode = t(f"mode_{m_mode_raw.lower()}", lang)
                    if m_mode.startswith("[mode_"): 
                        m_mode = m_mode_raw.capitalize()
                        
                    m_map = match[9] or t("unknown", lang)
                    
                    if "victor" in m_outcome.lower() or "win" in m_outcome.lower():
                        prefix = t("victory_short", lang)
                    elif "defeat" in m_outcome.lower() or "loss" in m_outcome.lower() or "derrot" in m_outcome.lower():
                        prefix = t("defeat_short", lang)
                    else:
                        prefix = t("finished_short", lang)
                        
                    emoji = get_hero_emoji(m_char, str(target.id), fake_lords_dict, True)
                    
                    line = f"{prefix} | {emoji} `{m_k}/{m_d}/{m_a}` | {m_mode} | {m_map}"
                    history_text.append(line)
                    
                embed.add_field(name=t("profile_recent_section", lang, num=len(recent_matches)), value="\n".join(history_text), inline=False)
            else:
                embed.add_field(name=t("profile_recent_title", lang), value=t("profile_recent_empty", lang), inline=False)
                
            embed.set_footer(text=t("profile_footer", lang))
            
            # Botón URL a RivalsMeta si el usuario tiene UID registrado
            view = None
            if in_game_uid:
                view = discord.ui.View(timeout=180)
                btn_rivals = discord.ui.Button(
                    label=t("btn_view_rivalsmeta", lang),
                    url=f"https://rivalsmeta.com/player/{in_game_uid}",
                    style=discord.ButtonStyle.link,
                    emoji="🌐"
                )
                view.add_item(btn_rivals)
                
            if view:
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error ejecutando /profile: {e}")
            await interaction.followup.send(t("profile_error", lang), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Profile(bot))
