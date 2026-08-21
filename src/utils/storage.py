import json
import os

CONFIG_FILE = "config.json"

def save_channel(channel_id: int):
    """Guarda el ID del canal en el archivo de configuración."""
    data = {"channel_id": channel_id}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                data["channel_id"] = channel_id
            except json.JSONDecodeError:
                pass
                
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_channel() -> int | None:
    """Obtiene el ID del canal vinculado."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                return data.get("channel_id")
            except json.JSONDecodeError:
                return None
    return None
