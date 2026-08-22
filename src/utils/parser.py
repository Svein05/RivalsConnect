import discord
import logging
from src.utils.heroes import get_hero_data
from src.utils.i18n import t

logger = logging.getLogger("overwolf_parser")

APP_EMOJIS = {}

def get_hero_emoji(character_name, uid, lords_dict, is_ally=True):
    """Retorna el emoji correspondiente (de la app o placeholder)"""
    if not character_name:
        return "🔹" if is_ally else "🔸"
        
    char_upper = character_name.upper()
    title = lords_dict.get(uid, {}).get(char_upper)
    
    hero_data = get_hero_data(character_name)
    short_name = hero_data["short_code"]
    
    if title == "Animated Lord" or title == "Champion":
        title_suffix = "lordani"
    elif title == "Lord":
        title_suffix = "lord"
    else:
        title_suffix = "basic"
        
    emoji_name = f"{short_name}_{title_suffix}"
    
    if emoji_name in APP_EMOJIS:
        return APP_EMOJIS[emoji_name]
        
    # Fallbacks si no están subidos a Discord
    if title in ["Animated Lord", "Champion"]:
        return "🌟"
    elif title == "Lord":
        return "👑"
        
    return "🔹" if is_ally else "🔸"

def create_embed_from_data(payload, discord_name="Usuario", discord_avatar=None, elo_change=0, lords_dict=None, lang="es"):
    """
    Parsea el payload optimizado del cliente de Overwolf y retorna un Embed de Discord.
    """
    if lords_dict is None:
        lords_dict = {}
        
    try:
        event_name = payload.get("event")
        mapa = payload.get("map", "Desconocido")
        modo = payload.get("mode", "Desconocido")
        
        if not event_name:
            return None
            
        roster = payload.get("roster", {})
        
        # --- PARSE BANS (Para saber si es competitivo desde el inicio) ---
        bans = payload.get("bans")
        game_type = payload.get("game_type", "")
        is_competitive = (game_type.lower() == "competitive")
        parsed_bans = None
        
        if isinstance(bans, str) and bans.strip().startswith("["):
            import json
            try:
                parsed_bans = json.loads(bans)
                is_competitive = True
            except:
                pass
        elif isinstance(bans, list):
            parsed_bans = bans
            is_competitive = True
            
        modo_display = game_type if game_type else ("Competitivo" if is_competitive else "Casual")
        
        # Bloque de renderizado de bans compartido
        ban_text = ""
        if parsed_bans:
            ally_bans = []
            enemy_bans = []
            for b in parsed_bans:
                char_name = b.get("character_name", "")
                is_team = b.get("is_teammate", False)
                uid = b.get("uid", "")
                hero_data = get_hero_data(char_name)
                hero_name = hero_data["display_name"]
                emoji = get_hero_emoji(char_name, uid, lords_dict, is_team)
                
                if is_team:
                    ally_bans.append(f"{emoji} {hero_name}")
                else:
                    enemy_bans.append(f"{emoji} {hero_name}")
            
            if ally_bans: ban_text += f"**{t('ally_team', lang)}:** " + ", ".join(ally_bans) + "\n"
            if enemy_bans: ban_text += f"**{t('enemy_team', lang)}:** " + ", ".join(enemy_bans)

        if event_name == "match_start":
            embed = discord.Embed(
                title=f"{modo_display} - {modo} | {mapa}",
                description="Partida encontrada y cargando...",
                color=discord.Color.brand_green(),
                timestamp=discord.utils.utcnow()
            )
            if discord_avatar:
                embed.set_author(name=f"{discord_name} está en partida", icon_url=discord_avatar)
                
            if ban_text:
                embed.add_field(name="🚫 " + t("bans", lang), value=ban_text, inline=False)
                
            return embed
            
        elif event_name in ["match_playing", "match_end"]:
            # Configurar el embed base dependiendo del estado
            if event_name == "match_playing":
                embed = discord.Embed(
                    title=f"{modo_display} - {modo} | {mapa}",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                if discord_avatar:
                    embed.set_author(name=f"{discord_name} - En Progreso", icon_url=discord_avatar)
            else:
                outcome = payload.get("outcome", "Desconocido").lower()
                if "victor" in outcome or "win" in outcome:
                    final_color = discord.Color.brand_green()
                    title_prefix = "🏆 ¡VICTORIA!"
                elif "defeat" in outcome or "loss" in outcome or "derrot" in outcome:
                    final_color = discord.Color.brand_red()
                    title_prefix = "☠️ DERROTA"
                else:
                    final_color = discord.Color.light_grey()
                    title_prefix = "🛑 Partida Finalizada"
                    
                embed = discord.Embed(
                    title=f"{title_prefix} | {modo_display} - {modo} | {mapa}",
                    color=final_color,
                    timestamp=discord.utils.utcnow()
                )
                if discord_avatar:
                    embed.set_author(name=f"{discord_name} - Resumen Final", icon_url=discord_avatar)

            # --- ZOE BOT 3 COLUMNS FORMAT ---
            aliados_list = []
            enemigos_list = []
            for key, p in roster.items():
                if p.get("is_teammate"): aliados_list.append(p)
                else: enemigos_list.append(p)
                
            def get_role_priority(role_name):
                if role_name == "Vanguardia": return 1
                if role_name == "Duelista": return 2
                if role_name == "Estratega": return 3
                return 4

            # Sort by Role then Name
            aliados_list.sort(key=lambda p: (
                get_role_priority(get_hero_data(p.get("character_name", ""))["role"]),
                get_hero_data(p.get("character_name", ""))["display_name"]
            ))
            
            enemigos_list.sort(key=lambda p: (
                get_role_priority(get_hero_data(p.get("character_name", ""))["role"]),
                get_hero_data(p.get("character_name", ""))["display_name"]
            ))
                
            max_len = max(len(aliados_list), len(enemigos_list))
            while len(aliados_list) < max_len: aliados_list.append(None)
            while len(enemigos_list) < max_len: enemigos_list.append(None)
            
            col_aliados = []
            col_score = []
            col_enemigos = []
            
            for al, en in zip(aliados_list, enemigos_list):
                if al:
                    uid = al.get("uid", "")
                    name = al.get("name", "Anónimo").replace("*****", "Anónimo")
                    hero = get_hero_data(al.get("character_name", ""))["display_name"]
                    emoji = get_hero_emoji(al.get("character_name", ""), uid, lords_dict, True)
                    short_name = name[:10] + ".." if len(name) > 12 else name
                    
                    if al.get("is_local"):
                        col_aliados.append(f"{emoji} **{short_name}**")
                    else:
                        col_aliados.append(f"{emoji} {short_name}")
                        
                    k = al.get("kills", 0)
                    d = al.get("deaths", 0)
                    a = al.get("assists", 0)
                    al_kda = "\u200b" + f"{k}/{d}/{a}".rjust(8, '\u2007')
                else:
                    col_aliados.append("👤 ABANDONO")
                    al_kda = "\u200b" + "-/-/-".rjust(8, '\u2007')
                    
                if en:
                    uid = en.get("uid", "")
                    name = en.get("name", "Anónimo").replace("*****", "Anónimo")
                    hero = get_hero_data(en.get("character_name", ""))["display_name"]
                    emoji = get_hero_emoji(en.get("character_name", ""), uid, lords_dict, False)
                    short_name = name[:10] + ".." if len(name) > 12 else name
                    
                    # Enemies are never is_local for the viewing user, so no bold
                    col_enemigos.append(f"{emoji} {short_name}")
                    
                    k = en.get("kills", 0)
                    d = en.get("deaths", 0)
                    a = en.get("assists", 0)
                    en_kda = f"{k}/{d}/{a}".ljust(8, '\u2007')
                else:
                    col_enemigos.append("👤 ABANDONO")
                    en_kda = "-/-/-".ljust(8, '\u2007')
                    
                col_score.append(f"{al_kda} | {en_kda}")
                
            # Extraer progreso del objetivo para inyectarlo al final de la partida también
            objective = payload.get("objective")
            obj_text_ally = ""
            obj_text_enemy = ""
            obj_footer = ""
            
            if objective:
                obj_mode = objective.get("game_mode", "")
                team_role = objective.get("team", "")
                role_es = t("defending", lang) if team_role == "Defense" else t("attacking", lang) if team_role == "Attacker" else team_role
                
                if obj_mode == "Domination":
                    left = int(objective.get("left_capture", 0))
                    right = int(objective.get("right_capture", 0))
                    obj_text_ally = t("capture_ally", lang, percent=left)
                    obj_text_enemy = t("capture_enemy", lang, percent=right)
                elif obj_mode == "Convoy":
                    chk = int(objective.get("checkpoint", 0))
                    progress_bar = ("🟩" * chk) + ("⬛" * max(0, 3 - chk))
                    obj_footer = t("escort", lang, bar=progress_bar, chk=chk, role=role_es)
                elif obj_mode == "Convergence":
                    chk = int(objective.get("checkpoint", 0))
                    obj_footer = t("convergence", lang, chk=chk, role=role_es)
                    
            aliados_text = "\n".join(col_aliados) if col_aliados else t("searching", lang)
            if obj_text_ally:
                aliados_text += f"\n\n{obj_text_ally}"
                
            enemigos_text = "\n".join(col_enemigos) if col_enemigos else t("searching", lang)
            if obj_text_enemy:
                enemigos_text += f"\n\n{obj_text_enemy}"
                
            # Añadir las 3 columnas
            if col_aliados:
                embed.add_field(name=t("ally_team", lang), value=aliados_text, inline=True)
                
                # Formatear el score calculando los espacios matemáticamente para centrar la barra en texto plano
                score_block = "\n".join(col_score)
                embed.add_field(name="\u200b \u200b \u200b \u200b \u200b \u200b " + t("kda", lang), value=score_block, inline=True)
                
                embed.add_field(name=t("enemy_team", lang), value=enemigos_text, inline=True)
            else:
                embed.add_field(name=t("error", lang), value=t("no_player_data", lang), inline=False)
                
            if obj_footer:
                embed.add_field(name="\u200b", value=obj_footer, inline=False)
            
            # Personajes Baneados (si los hay)
            if ban_text:
                embed.add_field(name="🚫 " + t("bans", lang), value=ban_text, inline=False)
                
            # Formatear estadísticas del jugador
            stats = payload.get("stats", {})
            if stats:
                damage = stats.get("damage_dealt", 0)
                heal = stats.get("total_heal", 0)
                block = stats.get("damage_block", 0)
                accuracy = stats.get("accuracy", 0)
                
                # Solo mostrar estadísticas si al menos una es mayor a 0
                if damage > 0 or heal > 0 or block > 0:
                    stat_items = [
                        (damage, t("stat_dmg", lang, val=f"{damage:,}")),
                        (heal, t("stat_heal", lang, val=f"{heal:,}")),
                        (block, t("stat_block", lang, val=f"{block:,}"))
                    ]
                    # Ordenar de mayor a menor valor
                    stat_items.sort(key=lambda x: x[0], reverse=True)
                    
                    # Unir y agregar precisión al final
                    stats_str = " | ".join(item[1] for item in stat_items)
                    stats_str += f" | {t('stat_acc', lang, val=accuracy)}"
                    
                    embed.add_field(name=t("stats_title", lang), value=stats_str, inline=False)
                
            embed.set_footer(text=t("footer_official", lang))
            return embed
            
        return None
        
    except Exception as e:
        logger.error(f"Error creando embed: {e}")
        return None
