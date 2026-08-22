# Diccionario oficial de héroes de Marvel Rivals
# Usado para normalizar nombres que vienen de Overwolf, extraer Emojis correctos y ordernar por Rol

import json
import os

HERO_DB = {}
json_path = os.path.join(os.path.dirname(__file__), 'heroes.json')

try:
    with open(json_path, 'r', encoding='utf-8') as f:
        HERO_DB = json.load(f)
except Exception as e:
    print(f"Error loading heroes.json: {e}")

def get_hero_data(raw_name):
    """
    Toma el nombre que manda Overwolf y lo limpia para buscar en la base de datos.
    Si no lo encuentra, devuelve un diccionario genérico.
    """
    if not raw_name:
        return {"role": "Desconocido", "display_name": "???", "short_code": "unknown"}
        
    clean_name = raw_name.lower().strip()
    
    if clean_name.startswith("the "): 
        clean_name = clean_name[4:]
        
    if clean_name in HERO_DB:
        return HERO_DB[clean_name]
        
    for db_name, data in HERO_DB.items():
        if db_name in clean_name:
            return data
            
    clean_name = clean_name.replace("&", "").replace("-", "")
    words = clean_name.split()
    if len(words) == 1: 
        short = words[0]
    else:
        short = words[0] + words[1][0]
        
    return {"role": "Desconocido", "display_name": raw_name, "short_code": short}
