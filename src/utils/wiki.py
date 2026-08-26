import aiohttp
import aiosqlite
import json
import re
import time
import logging
from typing import Dict, Any, Optional, List
from src.database.db import DB_PATH
from src.utils.heroes import HERO_DB, get_hero_data

logger = logging.getLogger("wiki_parser")

CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 días de caché
WIKI_API_URL = "https://marvelrivals.fandom.com/api.php"
HEADERS = {
    "User-Agent": "RivalsConnectBot/1.0 (Marvel Rivals Discord Bot; contact: Discord)"
}

WIKI_PAGE_MAP = {
    "captain america": "Captain_America",
    "doctor strange": "Doctor_Strange",
    "groot": "Groot",
    "hulk": "Hulk",
    "magneto": "Magneto",
    "peni parker": "Peni_Parker",
    "thor": "Thor",
    "venom": "Venom",
    "the thing": "The_Thing",
    "angela": "Angela",
    "black cat": "Black_Cat",
    "black panther": "Black_Panther",
    "black widow": "Black_Widow",
    "blade": "Blade",
    "cyclops": "Cyclops",
    "daredevil": "Daredevil",
    "deadpool": "Deadpool",
    "devil dinosaur": "Devil_Dinosaur",
    "elsa bloodstone": "Elsa_Bloodstone",
    "emma frost": "Emma_Frost",
    "gambit": "Gambit",
    "hawkeye": "Hawkeye",
    "hela": "Hela",
    "human torch": "Human_Torch",
    "invisible woman": "Invisible_Woman",
    "iron fist": "Iron_Fist",
    "iron man": "Iron_Man",
    "jubilee": "Jubilee",
    "magik": "Magik",
    "mister fantastic": "Mister_Fantastic",
    "moon knight": "Moon_Knight",
    "namor": "Namor",
    "phoenix": "Phoenix",
    "psylocke": "Psylocke",
    "punisher": "Punisher",
    "rogue": "Rogue",
    "scarlet witch": "Scarlet_Witch",
    "spider-man": "Spider-Man",
    "squirrel girl": "Squirrel_Girl",
    "star-lord": "Star-Lord",
    "storm": "Storm",
    "the hood": "The_Hood",
    "ultron": "Ultron",
    "white fox": "White_Fox",
    "winter soldier": "Winter_Soldier",
    "wolverine": "Wolverine",
    "adam warlock": "Adam_Warlock",
    "cloak & dagger": "Cloak_%26_Dagger",
    "jeff the land shark": "Jeff_the_Land_Shark",
    "loki": "Loki",
    "luna snow": "Luna_Snow",
    "mantis": "Mantis",
    "rocket raccoon": "Rocket_Raccoon"
}

def clean_wikitext(text: str) -> str:
    """Limpia etiquetas y formato de wikitext a texto plano legible."""
    if not text:
        return ""
    # Quitar referencias <ref>...</ref>
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'<ref[^>]*/>', '', text)
    # Quitar plantillas {{...}} anidadas simples
    text = re.sub(r'\{\{ATC\|[^\|]*\|([^}]+)\}\}', r'\1', text)
    text = re.sub(r'\{\{Affiliation\|([^}]+)\}\}', r'\1', text)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # Reemplazar enlaces [[Destino|Texto]] o [[Texto]]
    text = re.sub(r'\[\[(?:File|Image):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\[[^\]\|]+\|([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # Quitar HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Quitar negritas y cursivas
    text = text.replace("'''", "").replace("''", "")
    return text.strip()

async def init_wiki_cache():
    """Inicializa la tabla de caché de la wiki si no existe."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS wiki_cache (
                hero_key TEXT PRIMARY KEY,
                json_data TEXT,
                cached_at INTEGER
            )
        ''')
        await db.commit()

async def get_cached_hero(hero_key: str) -> Optional[Dict[str, Any]]:
    """Recupera los datos del héroe de la base de datos si la caché no ha expirado."""
    now = int(time.time())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT json_data, cached_at FROM wiki_cache WHERE hero_key = ?',
                (hero_key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    json_data, cached_at = row
                    if now - cached_at < CACHE_TTL_SECONDS:
                        return json.loads(json_data)
    except Exception as e:
        logger.warning(f"Error leyendo wiki_cache para {hero_key}: {e}")
    return None

async def save_cached_hero(hero_key: str, data: Dict[str, Any]):
    """Guarda los datos parseados del héroe en SQLite."""
    now = int(time.time())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO wiki_cache (hero_key, json_data, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(hero_key) DO UPDATE SET
                    json_data = excluded.json_data,
                    cached_at = excluded.cached_at
            ''', (hero_key, json.dumps(data, ensure_ascii=False), now))
            await db.commit()
    except Exception as e:
        logger.warning(f"Error guardando en wiki_cache para {hero_key}: {e}")

async def fetch_image_urls(session: aiohttp.ClientSession, filenames: List[str]) -> Dict[str, str]:
    """Obtiene las URLs directas del CDN para una lista de nombres de archivos."""
    if not filenames:
        return {}
    
    # Formatear títulos como File:Nombre.png
    titles = "|".join([f"File:{fn.strip()}" if not fn.startswith("File:") else fn.strip() for fn in filenames if fn.strip()])
    params = {
        "action": "query",
        "titles": titles,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json"
    }
    
    url_map = {}
    try:
        async with session.get(WIKI_API_URL, params=params, headers=HEADERS, timeout=10) as resp:
            if resp.status == 200:
                result = await resp.json()
                pages = result.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    title = page_data.get("title", "")
                    clean_title = title.replace("File:", "").strip()
                    imageinfo = page_data.get("imageinfo", [])
                    if imageinfo and "url" in imageinfo[0]:
                        url_map[clean_title] = imageinfo[0]["url"]
                        url_map[title] = imageinfo[0]["url"]
    except Exception as e:
        logger.error(f"Error obteniendo URLs de imágenes: {e}")
    return url_map

async def fetch_character_from_wiki(hero_key: str) -> Dict[str, Any]:
    """Consulta la API de la wiki y parsea la información completa del personaje."""
    clean_key = hero_key.lower().strip()
    page_title = WIKI_PAGE_MAP.get(clean_key)
    
    if not page_title:
        # Fallback genérico capitalizado
        page_title = clean_key.replace(" ", "_").title()
        
    hero_base = get_hero_data(clean_key)
    
    result_data = {
        "key": clean_key,
        "display_name": hero_base.get("display_name", page_title.replace("_", " ")),
        "role": hero_base.get("role", "Desconocido"),
        "role_key": hero_base.get("role_key", "unknown"),
        "short_code": hero_base.get("short_code", "unknown"),
        "real_name": "???",
        "health": 250,
        "difficulty": 3,
        "voice_actor": "Desconocido",
        "affiliation": "Marvel Rivals",
        "lore_quote": "",
        "portrait_url": "",
        "strengths": [],
        "weaknesses": [],
        "abilities": [],
        "teamups": []
    }
    
    images_to_resolve = []
    
    async with aiohttp.ClientSession() as session:
        # 1. Obtener la página principal del personaje
        params_main = {
            "action": "parse",
            "page": page_title,
            "prop": "wikitext",
            "format": "json"
        }
        
        main_wikitext = ""
        try:
            async with session.get(WIKI_API_URL, params=params_main, headers=HEADERS, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    main_wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        except Exception as e:
            logger.error(f"Error consultando página wiki de {page_title}: {e}")
            
        if not main_wikitext:
            return result_data
            
        # Parsear Infobox
        m_realname = re.search(r'\|\s*realname\s*=\s*([^\n\|]+)', main_wikitext)
        if m_realname: result_data["real_name"] = clean_wikitext(m_realname.group(1))
        
        m_health = re.search(r'\|\s*health\s*=\s*(\d+)', main_wikitext)
        if m_health: result_data["health"] = int(m_health.group(1))
        
        m_diff = re.search(r'\|\s*difficulty\s*=\s*(\d+)', main_wikitext)
        if m_diff: result_data["difficulty"] = int(m_diff.group(1))
        
        m_voice = re.search(r'\|\s*voiceactor\s*=\s*([^\n\|]+)', main_wikitext)
        if m_voice: result_data["voice_actor"] = clean_wikitext(m_voice.group(1))
        
        m_aff = re.search(r'\|\s*affiliation\s*=\s*([^\n\|]+)', main_wikitext)
        if m_aff: result_data["affiliation"] = clean_wikitext(m_aff.group(1))
        
        m_quote = re.search(r'\{\{Quote\|(.*?)\|Official description\}\}', main_wikitext, re.DOTALL)
        if m_quote: result_data["lore_quote"] = clean_wikitext(m_quote.group(1))
        
        m_img = re.search(r'\|\s*image\s*=\s*([^\n\|]+)', main_wikitext)
        if m_img:
            portrait_fn = m_img.group(1).strip()
            images_to_resolve.append(portrait_fn)
            result_data["portrait_filename"] = portrait_fn

        # Parsear Strengths
        strengths_match = re.search(r'===Strengths===(.*?)(?:===Weaknesses===|==)', main_wikitext, re.DOTALL)
        if strengths_match:
            lines = strengths_match.group(1).strip().split('\n')
            for line in lines:
                if line.startswith('*') and not line.startswith('**'):
                    cleaned = clean_wikitext(line.lstrip('* '))
                    if cleaned: result_data["strengths"].append(cleaned)
                    
        # Parsear Weaknesses
        weak_match = re.search(r'===Weaknesses===(.*?)(?:==Costumes==|==Abilities==|==)', main_wikitext, re.DOTALL)
        if weak_match:
            lines = weak_match.group(1).strip().split('\n')
            for line in lines:
                if line.startswith('*') and not line.startswith('**'):
                    cleaned = clean_wikitext(line.lstrip('* '))
                    if cleaned: result_data["weaknesses"].append(cleaned)

        # 2. Obtener Habilidades desde Template:Abilities/{Hero}
        abilities_template_title = f"Template:Abilities/{page_title}"
        params_abil = {
            "action": "parse",
            "page": abilities_template_title,
            "prop": "wikitext",
            "format": "json"
        }
        
        abil_wikitext = ""
        try:
            async with session.get(WIKI_API_URL, params=params_abil, headers=HEADERS, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    abil_wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        except Exception as e:
            logger.warning(f"No se pudo cargar {abilities_template_title}: {e}")

        # Parsear bloques de {{Skill ...}}
        if abil_wikitext:
            skill_blocks = re.findall(r'\{\{Skill[^\n]*\n(.*?)\n\}\}', abil_wikitext, re.DOTALL)
            for block in skill_blocks:
                name_m = re.search(r'\|\s*name\s*=\s*(.+)', block)
                key_m = re.search(r'\|\s*key\s*=\s*(.+)', block)
                icon_m = re.search(r'\|\s*(?:icon|team up icon)\s*=\s*([^\n\|]+)', block)
                desc_m = re.search(r'\|\s*description\s*=\s*(.+?)(?:<table|$)', block, re.DOTALL)
                hero_partner_m = re.search(r'\|\s*hero\s*=\s*(.+)', block)
                
                if name_m:
                    skill_name = clean_wikitext(name_m.group(1))
                    skill_key = clean_wikitext(key_m.group(1)) if key_m else ""
                    # Simplificar key switch de PC
                    if "PC =" in skill_key:
                        m_pc = re.search(r'PC\s*=\s*([^\|\}]+)', skill_key)
                        if m_pc: skill_key = m_pc.group(1).strip().upper()
                        
                    skill_desc = clean_wikitext(desc_m.group(1)) if desc_m else ""
                    skill_icon_fn = icon_m.group(1).strip() if icon_m else ""
                    if skill_icon_fn:
                        images_to_resolve.append(skill_icon_fn)
                        
                    is_teamup = bool(hero_partner_m or "team up icon" in block)
                    
                    item = {
                        "name": skill_name,
                        "key": skill_key,
                        "description": skill_desc,
                        "icon_filename": skill_icon_fn,
                        "icon_url": "",
                        "partner": clean_wikitext(hero_partner_m.group(1)) if hero_partner_m else ""
                    }
                    
                    if is_teamup:
                        result_data["teamups"].append(item)
                    else:
                        result_data["abilities"].append(item)
                        
        # 3. Resolver URLs de imágenes en batch
        if images_to_resolve:
            url_map = await fetch_image_urls(session, images_to_resolve)
            
            # Retrato principal
            portrait_fn = result_data.get("portrait_filename")
            if portrait_fn and portrait_fn in url_map:
                result_data["portrait_url"] = url_map[portrait_fn]
                
            # Iconos de habilidades
            for ab in result_data["abilities"]:
                fn = ab.get("icon_filename")
                if fn and fn in url_map:
                    ab["icon_url"] = url_map[fn]
                    
            # Iconos de teamups
            for tu in result_data["teamups"]:
                fn = tu.get("icon_filename")
                if fn and fn in url_map:
                    tu["icon_url"] = url_map[fn]
                    
    # Guardar en caché SQLite
    await save_cached_hero(clean_key, result_data)
    return result_data

async def get_hero_wiki_data(hero_key: str) -> Dict[str, Any]:
    """Punto de entrada principal con lectura de caché transparente."""
    await init_wiki_cache()
    cached = await get_cached_hero(hero_key.lower().strip())
    if cached:
        return cached
    return await fetch_character_from_wiki(hero_key.lower().strip())
