import aiohttp
import aiosqlite
import json
import re
import time
import os
import logging
from typing import Dict, Any, Optional, List
from src.database.db import DB_PATH
from src.utils.heroes import HERO_DB, get_hero_data
from src.utils.i18n import t

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
    # Reemplazar BalanceText
    text = re.sub(r'\{\{BalanceText\|[^\|]+\|([^}]+)\}\}', r'\1', text)
    # Quitar plantillas {{...}} anidadas simples
    text = re.sub(r'\{\{ATC\|[^\|]*\|([^}]+)\}\}', r'\1', text)
    text = re.sub(r'\{\{Affiliation\|([^}]+)\}\}', r'\1', text)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # Reemplazar iconos de Buff y Nerf antes de limpiar archivos
    text = re.sub(r'\[\[File:Buff\.svg[^\]]*\]\]', '🟢 [BUFF] ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\[File:Nerf\.svg[^\]]*\]\]', '🔴 [NERF] ', text, flags=re.IGNORECASE)
    # Reemplazar enlaces [[Destino|Texto]] o [[Texto]]
    text = re.sub(r'\[\[(?:File|Image):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\[[^\]\|]+\|([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # Quitar HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Quitar negritas y cursivas
    text = text.replace("'''", "").replace("''", "")
    return text.strip()

def slugify(text: str) -> str:
    """Convierte un texto a un identificador seguro para claves de traducción."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text).strip('_')
    return text[:40] if text else "item"

def sync_hero_translations_to_locales(hero_key: str, data: Dict[str, Any]):
    """
    Sincroniza las cadenas en inglés extraídas de la wiki en locales/en.json
    y crea las claves correspondientes en locales/es.json para Crowdin.
    """
    en_path = os.path.join("locales", "en.json")
    es_path = os.path.join("locales", "es.json")
    
    try:
        en_dict = {}
        es_dict = {}
        
        if os.path.exists(en_path):
            with open(en_path, "r", encoding="utf-8") as f:
                en_dict = json.load(f)
        if os.path.exists(es_path):
            with open(es_path, "r", encoding="utf-8") as f:
                es_dict = json.load(f)
                
        hkey_slug = slugify(hero_key)
        updated = False
        
        # 1. Fortalezas
        for idx, st in enumerate(data.get("strengths", []), 1):
            key = f"char_{hkey_slug}_strength_{idx}"
            if key not in en_dict:
                en_dict[key] = st
                updated = True
            if key not in es_dict:
                es_dict[key] = st
                updated = True
                
        # 2. Debilidades
        for idx, wk in enumerate(data.get("weaknesses", []), 1):
            key = f"char_{hkey_slug}_weakness_{idx}"
            if key not in en_dict:
                en_dict[key] = wk
                updated = True
            if key not in es_dict:
                es_dict[key] = wk
                updated = True
                
        # 3. Habilidades
        for ab in data.get("abilities", []):
            name_slug = slugify(ab.get("name", ""))
            key_desc = f"char_{hkey_slug}_skill_{name_slug}_desc"
            desc = ab.get("description", "")
            if desc:
                if key_desc not in en_dict:
                    en_dict[key_desc] = desc
                    updated = True
                if key_desc not in es_dict:
                    es_dict[key_desc] = desc
                    updated = True
                    
        # 4. Team-Ups
        for tu in data.get("teamups", []):
            name_slug = slugify(tu.get("name", ""))
            key_desc = f"char_{hkey_slug}_teamup_{name_slug}_desc"
            desc = tu.get("description", "")
            if desc:
                if key_desc not in en_dict:
                    en_dict[key_desc] = desc
                    updated = True
                if key_desc not in es_dict:
                    es_dict[key_desc] = desc
                    updated = True

        if updated:
            with open(en_path, "w", encoding="utf-8") as f:
                json.dump(en_dict, f, indent=4, ensure_ascii=False)
            with open(es_path, "w", encoding="utf-8") as f:
                json.dump(es_dict, f, indent=4, ensure_ascii=False)
            logger.info(f"Sincronizadas claves i18n para {hero_key} en locales/en.json y locales/es.json")
    except Exception as e:
        logger.error(f"Error sincronizando traducciones para {hero_key}: {e}")

def get_localized_hero_data(data: Dict[str, Any], lang: str = "es") -> Dict[str, Any]:
    """Retorna una copia de los datos del héroe con los textos traducidos según el idioma."""
    hkey_slug = slugify(data.get("key", ""))
    loc_data = json.loads(json.dumps(data))  # deep copy
    
    # Traducir fortalezas
    for idx, st in enumerate(loc_data.get("strengths", []), 1):
        key = f"char_{hkey_slug}_strength_{idx}"
        translated = t(key, lang)
        if not translated.startswith(f"[{key}"):
            loc_data["strengths"][idx - 1] = translated
            
    # Traducir debilidades
    for idx, wk in enumerate(loc_data.get("weaknesses", []), 1):
        key = f"char_{hkey_slug}_weakness_{idx}"
        translated = t(key, lang)
        if not translated.startswith(f"[{key}"):
            loc_data["weaknesses"][idx - 1] = translated
            
    # Traducir habilidades
    for ab in loc_data.get("abilities", []):
        name_slug = slugify(ab.get("name", ""))
        key_desc = f"char_{hkey_slug}_skill_{name_slug}_desc"
        translated = t(key_desc, lang)
        if not translated.startswith(f"[{key_desc}"):
            ab["description"] = translated
            
    # Traducir teamups
    for tu in loc_data.get("teamups", []):
        name_slug = slugify(tu.get("name", ""))
        key_desc = f"char_{hkey_slug}_teamup_{name_slug}_desc"
        translated = t(key_desc, lang)
        if not translated.startswith(f"[{key_desc}"):
            tu["description"] = translated

    return loc_data

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
    """Guarda los datos parseados del héroe en SQLite y sincroniza con locales."""
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
            
        # Sincronizar con los archivos i18n
        sync_hero_translations_to_locales(hero_key, data)
    except Exception as e:
        logger.warning(f"Error guardando en wiki_cache para {hero_key}: {e}")

async def fetch_image_urls(session: aiohttp.ClientSession, filenames: List[str]) -> Dict[str, str]:
    """Obtiene las URLs directas del CDN para una lista de nombres de archivos."""
    if not filenames:
        return {}
    
    unique_filenames = list(set([fn.strip() for fn in filenames if fn and fn.strip()]))
    titles = "|".join([f"File:{fn}" if not fn.startswith("File:") else fn for fn in unique_filenames])
    
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
    """Consulta la API de la wiki y parsea la información completa del personaje, incluyendo balance."""
    clean_key = hero_key.lower().strip()
    page_title = WIKI_PAGE_MAP.get(clean_key)
    
    if not page_title:
        page_title = clean_key.replace(" ", "_").title()
        
    hero_base = get_hero_data(clean_key)
    
    result_data = {
        "key": clean_key,
        "display_name": hero_base.get("display_name", page_title.replace("_", " ")),
        "role": hero_base.get("role", "Desconocido"),
        "role_key": hero_base.get("role_key", "unknown"),
        "short_code": hero_base.get("short_code", "unknown"),
        "health": 250,
        "difficulty": 3,
        "portrait_url": "",
        "strengths": [],
        "weaknesses": [],
        "abilities": [],
        "teamups": [],
        "balance_changes": []
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
            
        if main_wikitext:
            # Parsear Infobox
            m_health = re.search(r'\|\s*health\s*=\s*(\d+)', main_wikitext)
            if m_health: result_data["health"] = int(m_health.group(1))
            
            m_diff = re.search(r'\|\s*difficulty\s*=\s*(\d+)', main_wikitext)
            if m_diff: result_data["difficulty"] = int(m_diff.group(1))
            
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

        # 3. Obtener Cambios de Balance desde {Hero}/Balance_Changes
        balance_page_title = f"{page_title}/Balance_Changes"
        params_bal = {
            "action": "parse",
            "page": balance_page_title,
            "prop": "wikitext",
            "format": "json"
        }
        
        bal_wikitext = ""
        try:
            async with session.get(WIKI_API_URL, params=params_bal, headers=HEADERS, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bal_wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        except Exception as e:
            logger.info(f"No se encontró página de balance para {balance_page_title}: {e}")

        # Parsear tabla de balance
        if bal_wikitext:
            rows = re.findall(r'\|\-\s*\n\|<center><big>\'\'\'(.*?)\'\'\'</big>(?:<br><small>\'\'\'(.*?)\'\'\'</small>)?</center>\s*\n\|(.*?)(?=\|\-|\n\|\})', bal_wikitext, re.DOTALL)
            for version, date, changes_text in rows:
                patch_version = version.strip()
                patch_date = date.strip() if date else ""
                
                # Procesar líneas de cambio
                change_lines = []
                for raw_line in changes_text.strip().split('\n'):
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    if raw_line.startswith('*'):
                        cleaned_line = clean_wikitext(raw_line.lstrip('* '))
                        if cleaned_line:
                            change_lines.append(f"• {cleaned_line}")
                    elif raw_line.startswith("'''") or raw_line.startswith("[["):
                        section_name = clean_wikitext(raw_line)
                        if section_name:
                            change_lines.append(f"\n⚡ **{section_name}**")
                            
                if change_lines:
                    result_data["balance_changes"].append({
                        "version": patch_version,
                        "date": patch_date,
                        "changes": change_lines
                    })

        # 4. Resolver URLs de imágenes en batch
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
                    
    # Guardar en caché SQLite y sincronizar con locales
    await save_cached_hero(clean_key, result_data)
    return result_data

async def get_hero_wiki_data(hero_key: str) -> Dict[str, Any]:
    """Punto de entrada principal con lectura de caché transparente."""
    await init_wiki_cache()
    cached = await get_cached_hero(hero_key.lower().strip())
    if cached:
        return cached
    return await fetch_character_from_wiki(hero_key.lower().strip())
