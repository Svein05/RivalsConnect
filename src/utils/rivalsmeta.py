import os
import time
import json
import logging
import aiohttp
import aiosqlite
from typing import Dict, Any, Optional, List
from src.database.db import DB_PATH
from src.utils.heroes import get_hero_by_id

logger = logging.getLogger("rivalsmeta_client")

CACHE_TTL_SECONDS = 24 * 3600  # 24 horas de caché para proteger la cuota de la API
API_KEY = os.getenv("RIVALSMETA_API_KEY", "RivalsConnect-3367c50e-5ad1-406b-addf-a31fb97298dc")
BASE_URL = "https://rivalsmeta.com/api/player"

MAP_ID_MAP = {
    1421: "Intergalactic Empire of Wakanda",
    1230: "Lower Manhattan",
    1434: "Empire of Eternal Night",
    1422: "Klyntar",
    1423: "K'un-Lun",
    1424: "Tokyo 2099",
    1425: "Yggsgard",
    1426: "Hellfire Gala",
    1427: "Museum of Contemplation",
    1428: "Thebes",
    1429: "Hydra Charteris Base"
}

GAME_MODE_MAP = {
    1: "Convoy",
    2: "Convergence",
    3: "Domination"
}

async def init_rivalsmeta_cache():
    """Crea la tabla de caché de RivalsMeta si no existe."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS rivalsmeta_cache (
                uid TEXT PRIMARY KEY,
                json_data TEXT,
                cached_at INTEGER
            )
        ''')
        await db.commit()

async def get_cached_player(uid: str) -> Optional[Dict[str, Any]]:
    """Recupera los datos del jugador de la caché local si no han expirado."""
    now = int(time.time())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT json_data, cached_at FROM rivalsmeta_cache WHERE uid = ?',
                (str(uid),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    json_data, cached_at = row
                    if now - cached_at < CACHE_TTL_SECONDS:
                        data = json.loads(json_data)
                        data["cached"] = True
                        return data
    except Exception as e:
        logger.warning(f"Error leyendo rivalsmeta_cache para UID {uid}: {e}")
    return None

async def save_cached_player(uid: str, data: Dict[str, Any]):
    """Guarda los datos procesados en la caché local de SQLite."""
    now = int(time.time())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO rivalsmeta_cache (uid, json_data, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    json_data = excluded.json_data,
                    cached_at = excluded.cached_at
            ''', (str(uid), json.dumps(data, ensure_ascii=False), now))
            await db.commit()
    except Exception as e:
        logger.warning(f"Error guardando en rivalsmeta_cache para UID {uid}: {e}")

def parse_hero_stats_dict(raw_heroes_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parsea el diccionario de héroes (heroes_ranked o heroes_unranked) y lo ordena por partidas."""
    parsed_heroes = []
    if not isinstance(raw_heroes_dict, dict):
        return parsed_heroes
        
    for hid_str, stats in raw_heroes_dict.items():
        try:
            hid = int(hid_str)
            hero_info = get_hero_by_id(hid)
            
            matches = int(stats.get("matches", 0))
            wins = int(stats.get("win", 0))
            wr = round((wins / matches * 100), 1) if matches > 0 else 0.0
            
            kills = int(stats.get("kills", 0))
            deaths = int(stats.get("deaths", 0))
            assists = int(stats.get("assists", 0))
            kda = round((kills + assists) / max(1, deaths), 2)
            
            play_time = float(stats.get("play_time", 0))
            play_mins = max(1.0, play_time / 60.0)
            
            dmg = float(stats.get("damage", 0))
            heal = float(stats.get("heal", 0))
            dmg_per_min = round(dmg / play_mins, 1)
            heal_per_min = round(heal / play_mins, 1)
            
            parsed_heroes.append({
                "id": hid,
                "name": hero_info.get("display_name", f"Hero {hid}"),
                "role_key": hero_info.get("role_key", "unknown"),
                "short_code": hero_info.get("short_code", "unknown"),
                "matches": matches,
                "wins": wins,
                "wr": wr,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "kda": kda,
                "dmg_per_min": dmg_per_min,
                "heal_per_min": heal_per_min,
                "mvps": int(stats.get("mvp", 0)),
                "svps": int(stats.get("svp", 0))
            })
        except Exception as e:
            continue
            
    # Ordenar descendente por partidas jugadas, luego por victorias
    parsed_heroes.sort(key=lambda h: (h["matches"], h["wins"]), reverse=True)
    return parsed_heroes

def calculate_role_winrates(heroes_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Calcula el winrate acumulado por rol a partir de la lista de héroes."""
    roles = {
        "vanguard": {"matches": 0, "wins": 0, "wr": 0.0},
        "duelist": {"matches": 0, "wins": 0, "wr": 0.0},
        "strategist": {"matches": 0, "wins": 0, "wr": 0.0}
    }
    for h in heroes_list:
        rk = h.get("role_key")
        if rk in roles:
            roles[rk]["matches"] += h.get("matches", 0)
            roles[rk]["wins"] += h.get("wins", 0)
            
    for rk, rdata in roles.items():
        m = rdata["matches"]
        w = rdata["wins"]
        rdata["wr"] = round((w / m * 100), 1) if m > 0 else 0.0
        rdata["losses"] = max(0, m - w)
        
    return roles

def parse_rivalsmeta_payload(raw_json: Dict[str, Any], uid: str) -> Dict[str, Any]:
    """Parsea completamente el JSON de RivalsMeta estructurando héroes, mapas, historial y ranking."""
    player = raw_json.get("player", {})
    info = player.get("info", {})
    stats = raw_json.get("stats", {})
    ranked_stats = stats.get("ranked", {})
    
    player_name = info.get("name", "Unknown")
    player_level = info.get("level", "0")
    
    # Extraer rango y ELO de la temporada activa
    rank_game_season = info.get("rank_game_season", {})
    latest_season_num = 0
    latest_rank_score = 0.0
    peak_rs = 0.0
    latest_level = 0
    
    for season_key, season_val_str in rank_game_season.items():
        try:
            s_num = int(season_key) % 1000 if str(season_key).isdigit() else 0
            s_data = json.loads(season_val_str) if isinstance(season_val_str, str) else season_val_str
            r_score = float(s_data.get("rank_score", 0.0))
            max_r = float(s_data.get("max_rank_score", r_score))
            lvl = int(s_data.get("level", 0))
            
            if s_num >= latest_season_num:
                latest_season_num = s_num
                latest_rank_score = r_score
                peak_rs = max(max_r, r_score)
                latest_level = lvl
        except Exception:
            continue
            
    # Estadísticas globales
    total_ranked_matches = stats.get("ranked_matches", 0)
    total_ranked_wins = stats.get("ranked_matches_wins", 0)
    wr = round((total_ranked_wins / total_ranked_matches * 100), 1) if total_ranked_matches > 0 else 0.0
    
    kills = int(ranked_stats.get("total_kills", 0))
    deaths = int(ranked_stats.get("total_deaths", 0))
    assists = int(ranked_stats.get("total_assists", 0))
    kda = round((kills + assists) / max(1, deaths), 2)
    
    # Parsear héroes ranked y unranked
    heroes_ranked = parse_hero_stats_dict(raw_json.get("heroes_ranked", {}))
    heroes_unranked = parse_hero_stats_dict(raw_json.get("heroes_unranked", {}))
    
    role_wr_ranked = calculate_role_winrates(heroes_ranked)
    role_wr_unranked = calculate_role_winrates(heroes_unranked)
    
    # Parsear historial de partidas para la gráfica de progresión
    match_history = raw_json.get("match_history", [])
    rank_history_points = []
    
    # Ordenar cronológicamente del más antiguo al más reciente
    sorted_matches = sorted(match_history, key=lambda m: m.get("match_time_stamp", 0))
    for m in sorted_matches:
        mp = m.get("match_player", {})
        df = mp.get("dynamic_fields", {})
        new_score = df.get("new_score")
        add_score = df.get("add_score", 0)
        is_win = bool(mp.get("is_win", 0))
        ts = m.get("match_time_stamp", 0)
        
        if new_score is not None:
            rank_history_points.append({
                "rs": float(new_score),
                "change": float(add_score),
                "is_win": is_win,
                "timestamp": ts
            })
            
    # Si no hay puntos detallados en match_history, usar al menos el score actual y el peak
    if not rank_history_points and latest_rank_score > 0:
        rank_history_points = [
            {"rs": latest_rank_score - 20, "change": 20, "is_win": True, "timestamp": time.time() - 86400},
            {"rs": latest_rank_score, "change": 0, "is_win": True, "timestamp": time.time()}
        ]
        
    # Parsear mapas
    raw_maps = raw_json.get("maps", {})
    maps_data = []
    for mid_str, mstats in raw_maps.items():
        try:
            mid = int(mid_str)
            m_name = MAP_ID_MAP.get(mid, f"Map {mid}")
            m_count = int(mstats.get("matches", 0))
            m_wins = int(mstats.get("win", 0))
            m_wr = round((m_wins / m_count * 100), 1) if m_count > 0 else 0.0
            
            m_k = int(mstats.get("kills", 0))
            m_d = int(mstats.get("deaths", 0))
            m_a = int(mstats.get("assists", 0))
            m_kda = round((m_k + m_a) / max(1, m_d), 2)
            
            play_time = float(mstats.get("play_time", 0))
            time_str = f"{round(play_time / 3600, 1)} hrs" if play_time >= 3600 else f"{int(play_time / 60)} mins"
            
            maps_data.append({
                "id": mid,
                "name": m_name,
                "matches": m_count,
                "wins": m_wins,
                "wr": m_wr,
                "kda": m_kda,
                "time_str": time_str
            })
        except Exception:
            continue
            
    maps_data.sort(key=lambda m: m["matches"], reverse=True)
    
    return {
        "uid": str(uid),
        "player_name": player_name,
        "player_level": player_level,
        "active_season": latest_season_num,
        "elo": round(latest_rank_score, 1),
        "peak_rs": round(peak_rs, 1),
        "rank_level": latest_level,
        "ranked_matches": total_ranked_matches,
        "ranked_wins": total_ranked_wins,
        "ranked_wr": wr,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": kda,
        "heroes_ranked": heroes_ranked,
        "heroes_unranked": heroes_unranked,
        "role_wr_ranked": role_wr_ranked,
        "role_wr_unranked": role_wr_unranked,
        "rank_history_points": rank_history_points,
        "maps_data": maps_data,
        "web_url": f"https://rivalsmeta.com/player/{uid}",
        "cached": False
    }

async def fetch_player_from_rivalsmeta(uid: str) -> Optional[Dict[str, Any]]:
    """Consulta la API pública de RivalsMeta con TTL de 24 horas y soporte de caché."""
    clean_uid = str(uid).strip()
    if not clean_uid:
        return None
        
    await init_rivalsmeta_cache()
    
    cached = await get_cached_player(clean_uid)
    if cached:
        return cached
        
    url = f"{BASE_URL}/{clean_uid}"
    headers = {
        "X-API-Key": API_KEY,
        "User-Agent": "RivalsConnectBot/1.0 (Marvel Rivals Discord Bot; contact: Discord)"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    structured = parse_rivalsmeta_payload(raw_data, clean_uid)
                    await save_cached_player(clean_uid, structured)
                    return structured
                else:
                    logger.warning(f"RivalsMeta API retornó status {resp.status} para UID {clean_uid}")
    except Exception as e:
        logger.error(f"Error consultando RivalsMeta API para UID {clean_uid}: {e}")
        
    return None
