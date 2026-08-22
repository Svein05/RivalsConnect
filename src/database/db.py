import aiosqlite
import os

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
                match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                logs_channel_id INTEGER,
                live_panel_channel_id INTEGER,
                live_panel_msg_id INTEGER,
                leaderboard_channel_id INTEGER,
                leaderboard_msg_id INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS elo_thresholds (
                rank_id INTEGER PRIMARY KEY,
                rank_name TEXT UNIQUE,
                min_elo INTEGER
            )
        ''')
        
        # Populate default ranks if empty
        async with db.execute('SELECT COUNT(*) FROM elo_thresholds') as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                ranks = [
                    (0, "Bronce III"), (1, "Bronce II"), (2, "Bronce I"),
                    (3, "Plata III"), (4, "Plata II"), (5, "Plata I"),
                    (6, "Oro III"), (7, "Oro II"), (8, "Oro I"),
                    (9, "Platino III"), (10, "Platino II"), (11, "Platino I"),
                    (12, "Diamante III"), (13, "Diamante II"), (14, "Diamante I"),
                    (15, "Gran Maestro III"), (16, "Gran Maestro II"), (17, "Gran Maestro I"),
                    (18, "Celestial III"), (19, "Celestial II"), (20, "Celestial I"),
                    (21, "Eternidad"), (22, "One Above All")
                ]
                for r_id, r_name in ranks:
                    await db.execute('INSERT INTO elo_thresholds (rank_id, rank_name, min_elo) VALUES (?, ?, 99999)', (r_id, r_name))
        
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

async def add_match(discord_id: int, elo_change: int, kills: int, deaths: int, assists: int, damage: int, heal: int, outcome: str, character_name: str, mode: str, map_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO matches (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (discord_id, elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name))
        await db.commit()

async def get_recent_matches(discord_id: int, limit: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT elo_change, kills, deaths, assists, damage, heal, outcome, character_name, mode, map_name, match_date
            FROM matches
            WHERE discord_id = ?
            ORDER BY match_date DESC
            LIMIT ?
        ''', (discord_id, limit)) as cursor:
            return await cursor.fetchall()

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

async def get_top_characters(discord_id: int, limit: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT character_name, 
                   COUNT(*) as total_games, 
                   SUM(CASE WHEN LOWER(outcome) LIKE '%victor%' OR LOWER(outcome) LIKE '%win%' THEN 1 ELSE 0 END) as wins 
            FROM matches 
            WHERE discord_id = ? AND character_name IS NOT NULL AND character_name != '???' 
            GROUP BY character_name 
            ORDER BY total_games DESC, wins DESC
            LIMIT ?
        ''', (discord_id, limit)) as cursor:
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

async def get_user_rank(elo: int):
    if elo <= 0: return "Desclasificado"
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT rank_name, min_elo FROM elo_thresholds WHERE min_elo != 99999 ORDER BY rank_id DESC') as cursor:
            rows = await cursor.fetchall()
            
            if not rows:
                return "Desclasificado"
                
            for r_name, r_min in rows:
                if elo >= r_min:
                    return r_name
                    
            # Si el ELO es menor que todos los rangos configurados,
            # lo mantenemos en el rango más bajo configurado en lugar de desclasificarlo.
            return rows[-1][0]
