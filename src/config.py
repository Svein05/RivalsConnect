import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 3000))

if not TOKEN:
    raise ValueError("El BOT_TOKEN no está definido en el archivo .env")
