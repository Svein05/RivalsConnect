import aiosqlite
import os
from typing import Optional, List, Dict, Any, Tuple

DB_PATH = "rivalsconnect.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                discord_name TEXT,
                discord_avatar TEXT,
                link_code TEXT UNIQUE,
                is_playing BOOLEAN DEFAULT 0,
                match_context TEXT,
                elo_score INTEGER DEFAULT 0,
                in_game_uid TEXT,
                language TEXT DEFAULT 'es'
            )
        ''')
        
        # Migración automática si la columna no existe
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'es'")
        except:
            pass
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_lords (
                discord_id INTEGER,
                character_name TEXT,
                title_type TEXT,
                PRIMARY KEY(discord_id, character_name)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER,
                elo_change INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                damage INTEGER,
                heal INTEGER,
                outcome TEXT,
                character_name TEXT,
                mode TEXT,
                map_name TEXT,
                match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                match_uid TEXT UNIQUE
            )
        ''')
        
        try:
            await db.execute("ALTER TABLE matches ADD COLUMN match_uid TEXT")
        except:
            pass
        try:
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_uid ON matches(match_uid) WHERE match_uid IS NOT NULL")
        except:
            pass
        try:
            await db.execute("ALTER TABLE matches ADD COLUMN season INTEGER DEFAULT 19")
        except:
            pass
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                logs_channel_id INTEGER,
                live_panel_channel_id INTEGER,
                live_panel_msg_id INTEGER,
                leaderboard_channel_id INTEGER,
                leaderboard_msg_id INTEGER,
                language TEXT DEFAULT 'es'
            )
        ''')
        
        # Migración automática: añadir columna language a guild_config si no existe
        try:
            await db.execute("ALTER TABLE guild_config ADD COLUMN language TEXT DEFAULT 'es'")
        except:
            pass
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS elo_thresholds (
                rank_id INTEGER PRIMARY KEY,
                rank_name TEXT UNIQUE,
                min_elo INTEGER
            )
        ''')
        
        # Populate default ranks if empty (using neutral keys — Opción A)
        async with db.execute('SELECT COUNT(*) FROM elo_thresholds') as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                ranks = [
                    (0, "bronze_3"), (1, "bronze_2"), (2, "bronze_1"),
                    (3, "silver_3"), (4, "silver_2"), (5, "silver_1"),
                    (6, "gold_3"), (7, "gold_2"), (8, "gold_1"),
                    (9, "platinum_3"), (10, "platinum_2"), (11, "platinum_1"),
                    (12, "diamond_3"), (13, "diamond_2"), (14, "diamond_1"),
                    (15, "grand_master_3"), (16, "grand_master_2"), (17, "grand_master_1"),
                    (18, "celestial_3"), (19, "celestial_2"), (20, "celestial_1"),
                    (21, "eternity"), (22, "one_above_all")
                ]
                for r_id, r_name in ranks:
                    await db.execute('INSERT INTO elo_thresholds (rank_id, rank_name, min_elo) VALUES (?, ?, 99999)', (r_id, r_name))
        
        # Migración: actualizar nombres de rangos en español a claves neutras si la DB fue creada antes
        ES_TO_KEY = {
            "Bronce III": "bronze_3", "Bronce II": "bronze_2", "Bronce I": "bronze_1",
            "Plata III": "silver_3", "Plata II": "silver_2", "Plata I": "silver_1",
            "Oro III": "gold_3", "Oro II": "gold_2", "Oro I": "gold_1",
            "Platino III": "platinum_3", "Platino II": "platinum_2", "Platino I": "platinum_1",
            "Diamante III": "diamond_3", "Diamante II": "diamond_2", "Diamante I": "diamond_1",
            "Gran Maestro III": "grand_master_3", "Gran Maestro II": "grand_master_2", "Gran Maestro I": "grand_master_1",
            "Celestial III": "celestial_3", "Celestial II": "celestial_2", "Celestial I": "celestial_1",
            "Eternidad": "eternity", "One Above All": "one_above_all"
        }
        async with db.execute('SELECT rank_name FROM elo_thresholds') as cursor:
            existing = await cursor.fetchall()
        for (name,) in existing:
            if name in ES_TO_KEY:
                await db.execute('UPDATE elo_thresholds SET rank_name = ? WHERE rank_name = ?', (ES_TO_KEY[name], name))
        
        # Check if roster_json column exists in matches
        async with db.execute('PRAGMA table_info(matches)') as cursor:
            cols = [c[1] for c in await cursor.fetchall()]
            if 'roster_json' not in cols:
                await db.execute('ALTER TABLE matches ADD COLUMN roster_json TEXT')

        await db.commit()

async def get_user_by_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT discord_id, discord_name, discord_avatar FROM users WHERE link_code = ?', (code,)) as cursor:
            return await cursor.fetchone()

async def get_user(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT discord_id, discord_name, discord_avatar, link_code, 
                   is_playing, match_context, elo_score, in_game_uid 
            FROM users WHERE discord_id = ?
        ''', (discord_id,)) as cursor:
            return await cursor.fetchone()

async def set_user_code(discord_id: int, discord_name: str, discord_avatar: str, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (discord_id, link_code, discord_name, discord_avatar)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET 
                link_code = excluded.link_code,
                discord_name = excluded.discord_name,
                discord_avatar = excluded.discord_avatar
        ''', (discord_id, code, discord_name, discord_avatar))
        await db.commit()

async def update_user_elo(discord_id: int, new_elo: int, uid: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Recuperar el ELO actual para comparar
        async with db.execute('SELECT elo_score FROM users WHERE discord_id = ?', (discord_id,)) as cursor:
            row = await cursor.fetchone()
            
            old_elo = row[0] if row else 0
            
            # Actualizamos ELO y el UID interno si viene
            if uid:
                await db.execute('''
                    UPDATE users SET elo_score = ?, in_game_uid = ? WHERE discord_id = ?
                ''', (new_elo, uid, discord_id))
            else:
                await db.execute('''
                    UPDATE users SET elo_score = ? WHERE discord_id = ?
                ''', (new_elo, discord_id))
                
            await db.commit()
            return old_elo

async def get_user_lords(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT character_name, title_type FROM user_lords WHERE discord_id = ?', (discord_id,)) as cursor:
            return await cursor.fetchall()

async def set_user_lord(discord_id: int, character_name: str, title_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO user_lords (discord_id, character_name, title_type)
            VALUES (?, ?, ?)
            ON CONFLICT(discord_id, character_name) DO UPDATE SET title_type = excluded.title_type
        ''', (discord_id, character_name, title_type))
        await db.commit()
        
async def get_all_lords_by_uid():
    """Retorna un dict mapping uid -> {character_name: title_type}"""
    lords = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT u.in_game_uid, l.character_name, l.title_type 
            FROM users u
            JOIN user_lords l ON u.discord_id = l.discord_id
            WHERE u.in_game_uid IS NOT NULL
        ''') as cursor:
            rows = await cursor.fetchall()
            for uid, char, title in rows:
                if uid not in lords:
                    lords[uid] = {}
                lords[uid][char.upper()] = title
    return lords

async def get_current_season() -> int:
    """Devuelve la temporada activa detectada dinámicamente desde los datos del juego."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT MAX(season) FROM matches WHERE season IS NOT NULL') as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return int(row[0])
    except Exception:
        pass
    return 19

async def add_match(discord_id: int, elo_change: int, kills: int, deaths: int, assists: int, damage: int, heal: int, outcome: str, character_name: str, mode: str, map_name: str, roster_json: str = None, season: Optional[int] = None):
    if season is None:
        season = await get_current_season()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO matches (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, roster_json, season)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, roster_json, season))
        await db.commit()

async def sync_rivalsmeta_matches(discord_id: int, match_history: list, season: Optional[int] = None):
    """Inserta las partidas del historial de RivalsMeta en la tabla matches si no existen previamente y reconcilia duplicados."""
    if not match_history:
        return
        
    if season is None:
        season = await get_current_season()
        
    from datetime import datetime, timezone
    from src.utils.heroes import get_hero_by_id
    from src.utils.rivalsmeta import MAP_ID_MAP, GAME_MODE_MAP
    
    async with aiosqlite.connect(DB_PATH) as db:
        for m in match_history:
            m_uid = str(m.get("match_uid", "")).strip()
            if not m_uid:
                continue
                
            mp = m.get("match_player", {})
            df = mp.get("dynamic_fields", {})
            p_hero = mp.get("player_hero", {})
            hero_id = p_hero.get("hero_id") if isinstance(p_hero, dict) else p_hero
            hero_info = get_hero_by_id(hero_id)
            hero_name = hero_info.get("display_name", f"Hero {hero_id}")
            
            is_win = bool(mp.get("is_win", 0))
            outcome = "VICTORIA" if is_win else "DERROTA"
            
            add_score = 0
            if isinstance(df, dict) and df.get("add_score") is not None:
                add_score = int(round(float(df.get("add_score", 0))))
                
            k = int(mp.get("k", 0))
            d = int(mp.get("d", 0))
            a = int(mp.get("a", 0))
            
            mode_id = m.get("game_mode_id", 2)
            mode_name = GAME_MODE_MAP.get(mode_id, "Competitive")
            
            map_id = m.get("match_map_id", 0)
            map_name = MAP_ID_MAP.get(map_id, "Marvel Rivals Map")
            
            ts = m.get("match_time_stamp", 0)
            dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None
            
            # 1. Comprobar si ya existe con este match_uid exacto
            async with db.execute("SELECT id FROM matches WHERE match_uid = ?", (m_uid,)) as cursor:
                if await cursor.fetchone():
                    continue
                    
            # 2. Si hay una partida local sin match_uid con las mismas stats (kills, deaths, assists), actualizarla con la data oficial
            async with db.execute('''
                SELECT id FROM matches 
                WHERE discord_id = ? AND match_uid IS NULL AND kills = ? AND deaths = ? AND assists = ?
                LIMIT 1
            ''', (discord_id, k, d, a)) as cursor:
                local_match = await cursor.fetchone()
                if local_match:
                    local_id = local_match[0]
                    await db.execute('''
                        UPDATE matches SET
                            match_uid = ?,
                            elo_change = ?,
                            kills = ?,
                            deaths = ?,
                            assists = ?,
                            outcome = ?,
                            character_name = ?,
                            mode = ?,
                            map_name = ?,
                            match_date = ?
                        WHERE id = ?
                    ''', (m_uid, add_score, k, d, a, outcome, hero_name, mode_name, map_name, dt_str, local_id))
                    continue
                    
            # 3. Si no existe, insertar nueva fila oficial
            await db.execute('''
                INSERT INTO matches (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, match_date, match_uid, season)
                VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
            ''', (discord_id, add_score, k, d, a, outcome, hero_name, mode_name, map_name, dt_str, m_uid, season))
            
        # 4. Eliminar cualquier duplicado residual sin match_uid que tenga los mismos K/D/A de una partida con match_uid
        await db.execute('''
            DELETE FROM matches 
            WHERE discord_id = ? AND match_uid IS NULL 
            AND EXISTS (
                SELECT 1 FROM matches m2 
                WHERE m2.discord_id = matches.discord_id 
                  AND m2.match_uid IS NOT NULL 
                  AND m2.kills = matches.kills 
                  AND m2.deaths = matches.deaths 
                  AND m2.assists = matches.assists
            )
        ''', (discord_id,))
        await db.commit()

async def sync_rivalsmeta_rank_history(discord_id: int, rank_matches: list, season: Optional[int] = None):
    """Guarda todas las partidas del historial de la temporada (/rank-history) en SQLite si no existen."""
    if not rank_matches:
        return
        
    if season is None:
        season = await get_current_season()
        
    from datetime import datetime, timezone
    from src.utils.heroes import get_hero_by_id
    
    async with aiosqlite.connect(DB_PATH) as db:
        for m in rank_matches:
            m_uid = str(m.get("match_uid", "")).strip()
            if not m_uid:
                continue
                
            async with db.execute("SELECT id FROM matches WHERE match_uid = ?", (m_uid,)) as cursor:
                if await cursor.fetchone():
                    continue
                    
            hero_id = m.get("hero_id")
            hero_info = get_hero_by_id(hero_id)
            hero_name = hero_info.get("display_name", f"Hero {hero_id}")
            
            is_win = bool(m.get("is_win", False))
            outcome = "VICTORIA" if is_win else "DERROTA"
            score_change = int(round(float(m.get("score_change", 0))))
            ts = m.get("timestamp", 0)
            dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None
            
            await db.execute('''
                INSERT INTO matches (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, match_date, match_uid, season)
                VALUES (?, ?, 0, 0, 0, 0, 0, ?, ?, 'Competitive', 'Marvel Rivals Map', ?, ?, ?)
            ''', (discord_id, score_change, outcome, hero_name, dt_str, m_uid, season))
            
        await db.commit()

async def get_recent_matches(discord_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, match_date, roster_json
            FROM matches
            WHERE discord_id = ?
            ORDER BY match_date DESC
            LIMIT ?
        ''', (discord_id, limit)) as cursor:
            return await cursor.fetchall()

def format_relative_time(date_val, lang: str = "es") -> str:
    """Calcula y formatea el tiempo transcurrido en formato ultra-compacto (| 3h, | 3d, | 3m)."""
    from datetime import datetime, timezone
    if not date_val:
        return "1min"
        
    now = datetime.now(timezone.utc)
    match_dt = None
    
    if isinstance(date_val, (int, float)):
        match_dt = datetime.fromtimestamp(date_val, tz=timezone.utc)
    elif isinstance(date_val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                match_dt = datetime.strptime(date_val, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                pass
                
    if not match_dt:
        return "1min"
        
    diff = (now - match_dt).total_seconds()
    if diff < 0:
        diff = 0
        
    if diff < 3600:
        mins = max(1, int(diff / 60))
        return f"{mins}min"
    elif diff < 86400:
        hours = max(1, int(diff / 3600))
        return f"{hours}h"
    elif diff < 2592000:
        days = max(1, int(diff / 86400))
        return f"{days}d"
    else:
        months = max(1, int(diff / 2592000))
        return f"{months}m"

async def update_user_lords(discord_id: int, heroes: list, title_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Primero borramos todos los títulos de este tipo para este usuario
        await db.execute('DELETE FROM user_lords WHERE discord_id = ? AND title_type = ?', (discord_id, title_type))
        # También borramos "Animated Lord" por retrocompatibilidad si están actualizando Champions
        if title_type == "Champion":
            await db.execute('DELETE FROM user_lords WHERE discord_id = ? AND title_type = ?', (discord_id, "Animated Lord"))
            
        # Insertamos los nuevos
        for hero in heroes:
            # Upsert en caso de que accidentalmente el personaje tenga otro título (garantizando exclusividad a nivel DB)
            await db.execute('''
                INSERT INTO user_lords (discord_id, character_name, title_type)
                VALUES (?, ?, ?)
                ON CONFLICT(discord_id, character_name) DO UPDATE SET title_type = excluded.title_type
            ''', (discord_id, hero, title_type))
        await db.commit()

async def get_top_characters(discord_id: int, mode_type: str = None, limit: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        query = '''
            SELECT character_name, 
                   COUNT(*) as total_games, 
                   SUM(CASE WHEN LOWER(outcome) LIKE '%victor%' OR LOWER(outcome) LIKE '%win%' THEN 1 ELSE 0 END) as wins,
                   ROUND(AVG(kills), 1) as avg_k,
                   ROUND(AVG(deaths), 1) as avg_d,
                   ROUND(AVG(assists), 1) as avg_a
            FROM matches 
            WHERE discord_id = ? AND character_name IS NOT NULL AND character_name != '???'
        '''
        params = [discord_id]
        if mode_type == "ranked":
            query += " AND (LOWER(mode) LIKE '%comp%' OR LOWER(mode) LIKE '%rank%')"
        elif mode_type == "unranked":
            query += " AND (LOWER(mode) NOT LIKE '%comp%' AND LOWER(mode) NOT LIKE '%rank%')"
            
        query += " GROUP BY character_name ORDER BY total_games DESC, wins DESC LIMIT ?"
        params.append(limit)
        
        async with db.execute(query, tuple(params)) as cursor:
            return await cursor.fetchall()

async def get_user_language(discord_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT language FROM users WHERE discord_id = ?', (discord_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 'es'

async def set_user_language(discord_id: int, language: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET language = ? WHERE discord_id = ?', (language, discord_id))
        await db.commit()



async def update_rank_threshold(rank_name: str, elo: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT min_elo FROM elo_thresholds WHERE rank_name = ?', (rank_name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                current_min = row[0]
                new_min = min(current_min, elo) if current_min != 99999 else elo
                await db.execute('UPDATE elo_thresholds SET min_elo = ? WHERE rank_name = ?', (new_min, rank_name))
                await db.commit()
                return new_min
        return None

async def get_user_rank(elo: int) -> str:
    """Returns the neutral rank key (e.g. 'grand_master_1') for the given ELO. Use translate_rank() to display it."""
    if elo <= 0: return "unranked"
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT rank_name, min_elo FROM elo_thresholds WHERE min_elo != 99999 ORDER BY rank_id DESC') as cursor:
            rows = await cursor.fetchall()
            
            if not rows:
                return "unranked"
                
            for r_name, r_min in rows:
                if elo >= r_min:
                    return r_name
                    
            # If ELO is below all configured thresholds, keep at the lowest configured rank.
            return rows[-1][0]

async def get_guild_language(guild_id: int) -> str:
    """Returns the configured language for a guild (default 'es')."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT language FROM guild_config WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 'es'

async def set_guild_language(guild_id: int, language: str):
    """Saves the language preference for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE guild_config SET language = ? WHERE guild_id = ?', (language, guild_id))
        await db.commit()

async def get_all_matches(discord_id: int):
    """Returns all matches for a user as a list of dicts."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT outcome, character_name FROM matches WHERE discord_id = ?',
            (discord_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [{"outcome": r[0] or "", "character_name": r[1] or ""} for r in rows]

async def get_top_roles(discord_id: int) -> dict:
    """Aggregates win/total stats per role_key (vanguard/duelist/strategist) from match history."""
    from src.utils.heroes import get_hero_data
    matches = await get_all_matches(discord_id)
    role_stats: dict = {}
    for match in matches:
        char_name = match["character_name"]
        if not char_name or char_name == "???":
            continue
        outcome = match["outcome"].lower()
        role_key = get_hero_data(char_name).get("role_key", "unknown")
        if role_key == "unknown":
            continue
        if role_key not in role_stats:
            role_stats[role_key] = {"wins": 0, "total": 0}
        role_stats[role_key]["total"] += 1
        if "victor" in outcome or "win" in outcome:
            role_stats[role_key]["wins"] += 1
    return role_stats
