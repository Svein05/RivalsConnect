import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'locales')

translations = {}

def load_locales():
    global translations
    if not os.path.exists(LOCALES_DIR):
        return
        
    for filename in os.listdir(LOCALES_DIR):
        if filename.endswith('.json'):
            lang = filename.replace('.json', '')
            with open(os.path.join(LOCALES_DIR, filename), 'r', encoding='utf-8') as f:
                try:
                    translations[lang] = json.load(f)
                except Exception as e:
                    print(f'Error loading {filename}: {e}')

load_locales()

def t(key: str, lang: str = 'es', **kwargs) -> str:
    if not lang:
        lang = 'es'
    if lang not in translations:
        lang = 'es'
        
    text = translations.get(lang, {}).get(key)
    
    if not text:
        text = translations.get('es', {}).get(key, f'[{key}]')
        
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text

def translate_rank(rank_key: str, lang: str = 'es') -> str:
    """Translates a neutral rank key (e.g. 'grand_master_1') to the localized string."""
    return t(f"rank_{rank_key}", lang)