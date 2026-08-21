from src.bot import SpiderBot
from src.database import db
from src.config import TOKEN
import logging
import os
import asyncio

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler("logs/overwolf.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

logger = logging.getLogger(__name__)

async def main():
    """Punto de entrada principal de la aplicación."""
    setup_logging()
    
    bot = SpiderBot()

    @bot.event
    async def on_ready():
        logger.info(f"Bot conectado como {bot.user}")
        await db.init_db()
        logger.info("Base de datos inicializada")
        
        # Cargar emojis de la aplicación en el parser
        try:
            from src.utils.parser import APP_EMOJIS
            app_emojis = await bot.fetch_application_emojis()
            for emoji in app_emojis:
                APP_EMOJIS[emoji.name] = str(emoji)
            logger.info(f"Cargados {len(app_emojis)} emojis de la aplicación a la memoria.")
        except Exception as e:
            logger.error(f"Error cargando emojis de la app: {e}")
    
    # Cargar extensiones
    await bot.load_extension("src.cogs.auth")
    await bot.load_extension("src.cogs.leaderboard")
    await bot.load_extension("src.cogs.settings")
    await bot.load_extension("src.cogs.live_panel")
    await bot.load_extension("src.cogs.lords")
    await bot.load_extension("src.cogs.profile")
    
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("\nApagando el bot...")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
