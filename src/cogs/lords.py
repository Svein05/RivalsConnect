import discord
from discord.ext import commands
from discord import app_commands
from src.database import db
import logging

logger = logging.getLogger("lords_cog")

class RoleSelect(discord.ui.Select):
    def __init__(self, placeholder, options):
        super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class LordsView(discord.ui.View):
    def __init__(self, user_lords):
        super().__init__(timeout=180)
        
        owned_heroes = [char.upper() for char, _ in user_lords]
        
        self.title_select = discord.ui.Select(
            placeholder="1️⃣ Selecciona el Rango a asignar",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Lord", emoji="👑", value="Lord", description="Lord normal (Marco Dorado)"),
                discord.SelectOption(label="Champion", emoji="🌟", value="Champion", description="Champion (Lord Animado)")
            ]
        )
        
        async def title_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
        self.title_select.callback = title_callback
        self.add_item(self.title_select)
        
        def make_options(names):
            opts = []
            for name in names:
                is_owned = name.upper() in owned_heroes
                opts.append(discord.SelectOption(label=name, value=name, default=is_owned))
            return opts

        list_1 = [
            "Adam Warlock", "Angela", "Black Cat", "Black Panther", "Black Widow", 
            "Blade", "Captain America", "Cloak & Dagger", "Cyclops", "Daredevil", 
            "Deadpool", "Devil Dinosaur", "Doctor Strange", "Elsa Bloodstone", 
            "Emma Frost", "Gambit", "Groot", "Hawkeye", "Hela", "Hulk", "Human Torch"
        ]
        self.select_1 = RoleSelect("2️⃣ Personajes (A - H)", make_options(list_1))
        self.add_item(self.select_1)
        
        list_2 = [
            "Invisible Woman", "Iron Fist", "Iron Man", "Jeff the Land Shark", 
            "Jubilee", "Loki", "Luna Snow", "Magik", "Magneto", "Mantis", 
            "Mister Fantastic", "Moon Knight", "Namor", "Peni Parker", 
            "Phoenix", "Psylocke", "Punisher"
        ]
        self.select_2 = RoleSelect("3️⃣ Personajes (I - P)", make_options(list_2))
        self.add_item(self.select_2)
        
        list_3 = [
            "Rocket Raccoon", "Rogue", "Scarlet Witch", "Spider-Man", 
            "Squirrel Girl", "Star-Lord", "Storm", "The Hood", "The Thing", 
            "Thor", "Ultron", "Venom", "White Fox", "Winter Soldier", "Wolverine"
        ]
        self.select_3 = RoleSelect("4️⃣ Personajes (R - Z)", make_options(list_3))
        self.add_item(self.select_3)
        
    @discord.ui.button(label="Guardar Configuración", style=discord.ButtonStyle.green, row=4)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.title_select.values:
            await interaction.response.send_message("❌ Debes seleccionar un Título en el primer menú.", ephemeral=True)
            return
            
        t_type = self.title_select.values[0]
        
        heroes = []
        if self.select_1.values: heroes.extend(self.select_1.values)
        if self.select_2.values: heroes.extend(self.select_2.values)
        if self.select_3.values: heroes.extend(self.select_3.values)
        
        if not heroes:
            await interaction.response.send_message("❌ Debes seleccionar al menos un personaje en las listas.", ephemeral=True)
            return
            
        for h in heroes:
            await db.set_user_lord(interaction.user.id, h.upper(), t_type)
            
        for item in self.children:
            item.disabled = True
            
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✅ ¡Guardado exitosamente!\nSe asignó el rango **{t_type}** a:\n`{', '.join(heroes)}`", ephemeral=True)

class Lords(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lord", description="Abre un menú interactivo para seleccionar tus Lords/Champions de una lista.")
    async def lord(self, interaction: discord.Interaction):
        user_lords = await db.get_user_lords(interaction.user.id)
        if not user_lords:
            user_lords = []
            
        embed = discord.Embed(
            title="Gestor de Rangos (Lords & Champions)",
            description="1. Selecciona el rango que quieres asignar.\n2. Abre las listas de personajes y selecciona **todos los que quieras** (puedes marcar múltiples a la vez).\n3. Presiona **Guardar Configuración**.\n\n*Nota: Tus personajes actuales ya aparecen marcados por defecto.*",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed, view=LordsView(user_lords), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Lords(bot))
