import discord
from discord.ext import commands
from discord import app_commands
from src.database import db

class RoleSelect(discord.ui.Select):
    def __init__(self, placeholder, options):
        if not options:
            options = [discord.SelectOption(label="No hay opciones disponibles", value="NONE")]
            super().__init__(placeholder=placeholder, min_values=0, max_values=1, options=options, disabled=True)
        else:
            super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class LordsEditView(discord.ui.View):
    def __init__(self, discord_id, title_type, owned_titles, opposite_titles):
        super().__init__(timeout=300)
        self.discord_id = discord_id
        self.title_type = title_type
        
        def make_options(names):
            opts = []
            for name in names:
                if name.upper() in opposite_titles:
                    continue
                is_owned = name.upper() in owned_titles
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

    @discord.ui.button(label="💾 Guardar Cambios", style=discord.ButtonStyle.green, row=4)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        heroes = []
        if self.select_1.values and self.select_1.values[0] != "NONE": heroes.extend(self.select_1.values)
        if self.select_2.values and self.select_2.values[0] != "NONE": heroes.extend(self.select_2.values)
        if self.select_3.values and self.select_3.values[0] != "NONE": heroes.extend(self.select_3.values)
        
        try:
            await db.update_user_lords(self.discord_id, heroes, self.title_type)
            await interaction.response.send_message(f"✅ Tus {self.title_type}s han sido guardados correctamente.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Hubo un error al guardar.", ephemeral=True)

class SettingsMenu(discord.ui.View):
    def __init__(self, discord_id):
        super().__init__(timeout=300)
        self.discord_id = discord_id

    async def get_user_data(self):
        lords = []
        champions = []
        try:
            user_titles = await db.get_user_lords(self.discord_id)
            for char_name, title_type in user_titles:
                if title_type == "Lord":
                    lords.append(char_name)
                elif title_type == "Champion" or title_type == "Animated Lord":
                    champions.append(char_name)
        except Exception as e:
            pass
        return [l.upper() for l in lords], [c.upper() for c in champions]

    @discord.ui.button(label="👑 Editar Lords", style=discord.ButtonStyle.primary)
    async def edit_lords(self, interaction: discord.Interaction, button: discord.ui.Button):
        lords, champions = await self.get_user_data()
        view = LordsEditView(self.discord_id, "Lord", lords, champions)
        await interaction.response.edit_message(content="**👑 Editando tus Lords**\nSelecciona tus personajes de los menús (tus Champions actuales han sido ocultados para evitar conflictos).", embed=None, view=view)

    @discord.ui.button(label="🌟 Editar Champions", style=discord.ButtonStyle.primary)
    async def edit_champions(self, interaction: discord.Interaction, button: discord.ui.Button):
        lords, champions = await self.get_user_data()
        view = LordsEditView(self.discord_id, "Champion", champions, lords)
        await interaction.response.edit_message(content="**🌟 Editando tus Champions**\nSelecciona tus personajes de los menús (tus Lords actuales han sido ocultados para evitar conflictos).", embed=None, view=view)

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="configprofile", description="Configura los títulos (Lords/Champions) y opciones de tu perfil.")
    async def configprofile_command(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        
        lords = []
        champions = []
        try:
            user_titles = await db.get_user_lords(discord_id)
            for char_name, title_type in user_titles:
                if title_type == "Lord":
                    lords.append(char_name)
                elif title_type == "Champion" or title_type == "Animated Lord":
                    champions.append(char_name)
        except Exception as e:
            pass
            
        embed = discord.Embed(
            title="⚙️ Configuración de Perfil", 
            description="Aquí puedes administrar los títulos (Lords y Champions) que se muestran en tu perfil de RivalsConnect.\n\nRecuerda que **Lord** y **Champion** son mutuamente excluyentes (un personaje no puede tener ambos títulos a la vez).",
            color=discord.Color.blue()
        )
        
        lords_text = ", ".join(lords) if lords else "Ninguno"
        champions_text = ", ".join(champions) if champions else "Ninguno"
        
        embed.add_field(name="👑 Tus Lords Actuales", value=lords_text, inline=False)
        embed.add_field(name="🌟 Tus Champions Actuales", value=champions_text, inline=False)
        
        view = SettingsMenu(discord_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="setup_servidor", description="Configura los 3 canales de RivalsConnect.")
    @app_commands.default_permissions(administrator=True)
    async def setup_servidor(
        self, 
        interaction: discord.Interaction, 
        canal_partidas: discord.TextChannel,
        canal_panel_vivo: discord.TextChannel,
        canal_leaderboard: discord.TextChannel
    ):
        await interaction.response.defer(ephemeral=True)
        
        # Enviar mensajes placeholder
        embed_panel = discord.Embed(
            title="📡 Panel de Información en Vivo",
            description="Esperando a que los jugadores se conecten...",
            color=discord.Color.blue()
        )
        msg_panel = await canal_panel_vivo.send(embed=embed_panel)
        
        embed_leaderboard = discord.Embed(
            title="🏆 Clasificación del Servidor",
            description="Nadie ha jugado partidas aún.",
            color=discord.Color.gold()
        )
        msg_leaderboard = await canal_leaderboard.send(embed=embed_leaderboard)
        
        import aiosqlite
        async with aiosqlite.connect("rivalsconnect.db") as database:
            await database.execute('''
                INSERT INTO guild_config (
                    guild_id, logs_channel_id, live_panel_channel_id, live_panel_msg_id, leaderboard_channel_id, leaderboard_msg_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    logs_channel_id = excluded.logs_channel_id,
                    live_panel_channel_id = excluded.live_panel_channel_id,
                    live_panel_msg_id = excluded.live_panel_msg_id,
                    leaderboard_channel_id = excluded.leaderboard_channel_id,
                    leaderboard_msg_id = excluded.leaderboard_msg_id
            ''', (
                interaction.guild_id,
                canal_partidas.id,
                canal_panel_vivo.id,
                msg_panel.id,
                canal_leaderboard.id,
                msg_leaderboard.id
            ))
            await database.commit()
            
        await interaction.followup.send("✅ Canales configurados con éxito. Los paneles se actualizarán automáticamente.")

async def setup(bot):
    await bot.add_cog(Settings(bot))
