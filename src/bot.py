import discord
from discord.ext import commands
from src.server import start_web_server
from src.config import PORT

class SpiderBot(commands.Bot):
    def __init__(self):
        # Usamos solo los intents por defecto para evitar errores de permisos
        # en el portal de desarrolladores de Discord.
        intents = discord.Intents.default()
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Este método se ejecuta antes de que el bot se conecte a Discord."""
        print("⚙️ Iniciando setup_hook del bot...")
        
        # Sincronizar los comandos slash con Discord
        try:
            synced = await self.tree.sync()
            print(f"🔄 Comandos slash sincronizados: {len(synced)}")
        except Exception as e:
            print(f"❌ Error sincronizando comandos: {e}")

        # Iniciar el servidor HTTP como una tarea en segundo plano (background task)
        self.loop.create_task(start_web_server(self, PORT))

    async def on_ready(self):
        print(f"✅ Bot conectado y listo como {self.user} (ID: {self.user.id})")
        print("---------------------------------------------------")
