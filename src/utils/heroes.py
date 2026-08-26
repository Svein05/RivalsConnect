# Diccionario oficial de héroes de Marvel Rivals
# Usado para normalizar nombres que vienen de Overwolf, extraer Emojis correctos, resolver IDs numéricas y ordenar por Rol

import json
import os
from typing import Dict, Any, Optional

HERO_DB: Dict[str, Dict[str, Any]] = {}
HERO_ID_MAP: Dict[int, Dict[str, Any]] = {}

json_path = os.path.join(os.path.dirname(__file__), 'heroes.json')

try:
    with open(json_path, 'r', encoding='utf-8') as f:
        HERO_DB = json.load(f)
        for name_key, data in HERO_DB.items():
            hid = data.get("id")
            if hid is not None:
                HERO_ID_MAP[int(hid)] = data
except Exception as e:
    print(f"Error loading heroes.json: {e}")

def get_hero_by_id(hero_id: Any) -> Dict[str, Any]:
    """Busca y retorna los datos del héroe por su ID numérica oficial del juego."""
    try:
        numeric_id = int(hero_id)
        if numeric_id in HERO_ID_MAP:
            return HERO_ID_MAP[numeric_id]
    except (ValueError, TypeError):
        pass
    return {"id": 0, "role": "Desconocido", "role_key": "unknown", "display_name": f"Hero {hero_id}", "short_code": "unknown"}

def get_hero_data(raw_name: str) -> Dict[str, Any]:
    """
    Toma el nombre que manda Overwolf o Discord y lo normaliza para buscar en la base de datos.
    Si no lo encuentra, devuelve un diccionario genérico de fallback.
    """
    if not raw_name:
        return {"id": 0, "role": "Desconocido", "role_key": "unknown", "display_name": "???", "short_code": "unknown"}
        
    clean_name = str(raw_name).lower().strip()
    
    # Comprobar si se envió una ID numérica como string
    if clean_name.isdigit():
        return get_hero_by_id(int(clean_name))
        
    if clean_name in HERO_DB:
        return HERO_DB[clean_name]
        
    # Variación sin "the "
    no_the = clean_name[4:] if clean_name.startswith("the ") else clean_name
    if no_the in HERO_DB:
        return HERO_DB[no_the]
        
    # Búsqueda por subcadena
    for db_name, data in HERO_DB.items():
        if db_name in clean_name or clean_name in db_name:
            return data
            
    clean_slug = clean_name.replace("&", "").replace("-", "")
    words = clean_slug.split()
    if len(words) == 1: 
        short = words[0]
    else:
        short = words[0] + words[1][0]
        
    return {"id": 0, "role": "Desconocido", "role_key": "unknown", "display_name": raw_name, "short_code": short}
