import os
import time
import json
import logging
import aiohttp
import aiosqlite
from typing import Dict, Any, Optional
from src.database.db import DB_PATH

logger = logging.getLogger("rivalsmeta_client")

CACHE_TTL_SECONDS = 4 * 3600  # 4 horas de caché para proteger la cuota de la API
API_KEY = os.getenv("RIVALSMETA_API_KEY", "RivalsConnect-3367c50e-5ad1-406b-addf-a31fb97298dc")
BASE_URL = "https://rivalsmeta.com/api/player"

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

def parse_rivalsmeta_payload(raw_json: Dict[str, Any], uid: str) -> Dict[str, Any]:
    """Parsea y estructura el JSON de RivalsMeta a un formato estándar para RivalsConnect."""
    player = raw_json.get("player", {})
    info = player.get("info", {})
    stats = raw_json.get("stats", {})
    ranked_stats = stats.get("ranked", {})
    
    player_name = info.get("name", "Unknown")
    player_level = info.get("level", "0")
    
    # Extraer rango y ELO de la temporada activa más reciente
    rank_game_season = info.get("rank_game_season", {})
    latest_season_num = 0
    latest_rank_score = 0.0
    latest_level = 0
    
    for season_key, season_val_str in rank_game_season.items():
        try:
            # Claves tienen formato tipo 1001019 -> temporada 19
            s_num = int(season_key) % 1000 if str(season_key).isdigit() else 0
            s_data = json.loads(season_val_str) if isinstance(season_val_str, str) else season_val_str
            r_score = float(s_data.get("rank_score", 0.0))
            lvl = int(s_data.get("level", 0))
            
            if s_num >= latest_season_num:
                latest_season_num = s_num
                latest_rank_score = r_score
                latest_level = lvl
        except Exception as e:
            continue
            
    # Estadísticas globales de ranked
    total_ranked_matches = stats.get("ranked_matches", 0)
    total_ranked_wins = stats.get("ranked_matches_wins", 0)
    wr = round((total_ranked_wins / total_ranked_matches * 100), 1) if total_ranked_matches > 0 else 0.0
    
    kills = int(ranked_stats.get("total_kills", 0))
    deaths = int(ranked_stats.get("total_deaths", 0))
    assists = int(ranked_stats.get("total_assists", 0))
    kda = round((kills + assists) / max(1, deaths), 2)
    
    return {
        "uid": str(uid),
        "player_name": player_name,
        "player_level": player_level,
        "active_season": latest_season_num,
        "elo": round(latest_rank_score, 1),
        "rank_level": latest_level,
        "ranked_matches": total_ranked_matches,
        "ranked_wins": total_ranked_wins,
        "ranked_wr": wr,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": kda,
        "web_url": f"https://rivalsmeta.com/player/{uid}",
        "cached": False
    }

async def fetch_player_from_rivalsmeta(uid: str) -> Optional[Dict[str, Any]]:
    """Consulta la API pública de RivalsMeta con la clave autorizada y soporte de caché."""
    clean_uid = str(uid).strip()
    if not clean_uid:
        return None
        
    await init_rivalsmeta_cache()
    
    # 1. Comprobar caché local
    cached = await get_cached_player(clean_uid)
    if cached:
        return cached
        
    # 2. Consultar la API externa
    url = f"{BASE_URL}/{clean_uid}"
    headers = {
        "X-API-Key": API_KEY,
        "User-Agent": "RivalsConnectBot/1.0 (Marvel Rivals Discord Bot; contact: Discord)"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    structured = parse_rivalsmeta_payload(raw_data, clean_uid)
                    # Guardar en caché local
                    await save_cached_player(clean_uid, structured)
                    return structured
                else:
                    logger.warning(f"RivalsMeta API retornó status {resp.status} para UID {clean_uid}")
    except Exception as e:
        logger.error(f"Error consultando RivalsMeta API para UID {clean_uid}: {e}")
        
    return None
