import discord
from discord.ext import commands
from discord import app_commands
import src.database.db as db

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="syncelo", description="(Admin) Sincroniza tu ELO actual con un Rango Oficial para entrenar al bot.")
    @app_commands.choices(rango=[
        app_commands.Choice(name="Bronce III", value="Bronce III"),
        app_commands.Choice(name="Bronce II", value="Bronce II"),
        app_commands.Choice(name="Bronce I", value="Bronce I"),
        app_commands.Choice(name="Plata III", value="Plata III"),
        app_commands.Choice(name="Plata II", value="Plata II"),
        app_commands.Choice(name="Plata I", value="Plata I"),
        app_commands.Choice(name="Oro III", value="Oro III"),
        app_commands.Choice(name="Oro II", value="Oro II"),
        app_commands.Choice(name="Oro I", value="Oro I"),
        app_commands.Choice(name="Platino III", value="Platino III"),
        app_commands.Choice(name="Platino II", value="Platino II"),
        app_commands.Choice(name="Platino I", value="Platino I"),
        app_commands.Choice(name="Diamante III", value="Diamante III"),
        app_commands.Choice(name="Diamante II", value="Diamante II"),
        app_commands.Choice(name="Diamante I", value="Diamante I"),
        app_commands.Choice(name="Gran Maestro III", value="Gran Maestro III"),
        app_commands.Choice(name="Gran Maestro II", value="Gran Maestro II"),
        app_commands.Choice(name="Gran Maestro I", value="Gran Maestro I"),
        app_commands.Choice(name="Celestial III", value="Celestial III"),
        app_commands.Choice(name="Celestial II", value="Celestial II"),
        app_commands.Choice(name="Celestial I", value="Celestial I"),
        app_commands.Choice(name="Eternidad", value="Eternidad"),
        app_commands.Choice(name="One Above All", value="One Above All")
    ])
    async def syncelo(self, interaction: discord.Interaction, rango: str):
        is_owner = await self.bot.is_owner(interaction.user)
        if not is_owner and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ No tienes permisos para calibrar los rangos del bot.", ephemeral=True)
            return

        import aiosqlite
        async with aiosqlite.connect(db.DB_PATH) as database:
            async with database.execute('SELECT elo_score FROM users WHERE discord_id = ?', (interaction.user.id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] <= 0:
                    await interaction.response.send_message("❌ No tienes un ELO registrado. ¡Juega una partida con Overwolf activo primero!", ephemeral=True)
                    return
                current_elo = row[0]
                
        new_min = await db.update_rank_threshold(rango, current_elo)
        
        if new_min is not None:
            await interaction.response.send_message(f"✅ **Rango Calibrado:** El bot ha aprendido que **{rango}** comienza desde >= {new_min} ELO basándose en tus {current_elo} puntos.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error al calibrar el rango {rango}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
