import discord
from discord.ext import commands
from discord import app_commands
from src.database import db
from src.utils.i18n import t

class RoleSelect(discord.ui.Select):
    def __init__(self, placeholder, options, lang="es"):
        if not options:
            options = [discord.SelectOption(label=t("no_options", lang), value="NONE")]
            super().__init__(placeholder=placeholder, min_values=0, max_values=1, options=options, disabled=True)
        else:
            super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.interacted_selects.add(self.custom_id)
        await interaction.response.defer()

class LordsEditView(discord.ui.View):
    def __init__(self, discord_id, title_type, owned_titles, opposite_titles, lang="es"):
        super().__init__(timeout=300)
        self.discord_id = discord_id
        self.title_type = title_type
        self.lang = lang
        self.interacted_selects = set()
        
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
        self.select_1 = RoleSelect(t("group_1", self.lang), make_options(list_1), self.lang)
        self.add_item(self.select_1)
        
        list_2 = [
            "Invisible Woman", "Iron Fist", "Iron Man", "Jeff the Land Shark", 
            "Jubilee", "Loki", "Luna Snow", "Magik", "Magneto", "Mantis", 
            "Mister Fantastic", "Moon Knight", "Namor", "Peni Parker", 
            "Phoenix", "Psylocke", "Punisher"
        ]
        self.select_2 = RoleSelect(t("group_2", self.lang), make_options(list_2), self.lang)
        self.add_item(self.select_2)
        
        list_3 = [
            "Rocket Raccoon", "Rogue", "Scarlet Witch", "Spider-Man", 
            "Squirrel Girl", "Star-Lord", "Storm", "The Hood", "The Thing", 
            "Thor", "Ultron", "Venom", "White Fox", "Winter Soldier", "Wolverine"
        ]
        self.select_3 = RoleSelect(t("group_3", self.lang), make_options(list_3), self.lang)
        self.add_item(self.select_3)
        self.save_button.label = t("btn_save", self.lang)


    @discord.ui.button(label="💾 Guardar Cambios", style=discord.ButtonStyle.green, row=4)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        heroes = []
        for select in [self.select_1, self.select_2, self.select_3]:
            if select.custom_id in self.interacted_selects:
                if select.values and select.values[0] != "NONE":
                    heroes.extend(select.values)
            else:
                # El usuario no tocó este menú, rescatamos lo que tenía seleccionado por defecto
                defaults = [opt.value for opt in select.options if opt.default]
                heroes.extend(defaults)
        
        try:
            await db.update_user_lords(self.discord_id, heroes, self.title_type)
            
            # Recreate main menu view
            view = SettingsMenu(self.discord_id, self.lang)
            lords, champions = await view.get_user_data()
            lords_text = ", ".join(lords) if lords else t("none", self.lang)
            champions_text = ", ".join(champions) if champions else t("none", self.lang)
            
            embed = discord.Embed(
                title=t("settings_title", self.lang),
                description=t("settings_desc", self.lang),
                color=discord.Color.blue()
            )
            embed.add_field(name=t("settings_lords_current", self.lang), value=lords_text, inline=False)
            embed.add_field(name=t("settings_champs_current", self.lang), value=champions_text, inline=False)
            
            await interaction.response.edit_message(content=t("save_success", self.lang, title_type=self.title_type), embed=embed, view=view)
        except Exception as e:
            await interaction.response.send_message(t("save_error", self.lang), ephemeral=True)

class SettingsMenu(discord.ui.View):
    def __init__(self, discord_id, lang="es"):
        super().__init__(timeout=300)
        self.discord_id = discord_id
        self.lang = lang
        self.edit_lords.label = t("btn_edit_lords", self.lang)
        self.edit_champions.label = t("btn_edit_champs", self.lang)


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
        view = LordsEditView(self.discord_id, "Lord", lords, champions, self.lang)
        await interaction.response.edit_message(content=t("editing_lords", self.lang), embed=None, view=view)

    @discord.ui.button(label="🌟 Editar Champions", style=discord.ButtonStyle.primary)
    async def edit_champions(self, interaction: discord.Interaction, button: discord.ui.Button):
        lords, champions = await self.get_user_data()
        view = LordsEditView(self.discord_id, "Champion", champions, lords, self.lang)
        await interaction.response.edit_message(content=t("editing_champs", self.lang), embed=None, view=view)

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="configprofile", description="Configura los títulos (Lords/Champions) y opciones de tu perfil.")
    async def configprofile_command(self, interaction: discord.Interaction):
        lang = await db.get_user_language(interaction.user.id)
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
            title=t("settings_title", lang),
            description=t("settings_desc", lang),
            color=discord.Color.blue()
        )
        
        lords_text = ", ".join(lords) if lords else t("none", lang)
        champions_text = ", ".join(champions) if champions else t("none", lang)
        
        embed.add_field(name=t("settings_lords_current", lang), value=lords_text, inline=False)
        embed.add_field(name=t("settings_champs_current", lang), value=champions_text, inline=False)
        
        view = SettingsMenu(discord_id, lang)
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
        
        lang = await db.get_user_language(interaction.user.id)
        embed_panel = discord.Embed(
            title=t("setup_panel_title", lang),
            description=t("setup_panel_desc", lang),
            color=discord.Color.blue()
        )
        msg_panel = await canal_panel_vivo.send(embed=embed_panel)
        
        embed_leaderboard = discord.Embed(
            title=t("setup_lb_title", lang),
            description=t("setup_lb_desc", lang),
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
            
        await interaction.followup.send(t("setup_success", lang))

    @app_commands.command(name="configserver", description="Configure server language and settings / Configura el idioma del servidor.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(idioma=[
        app_commands.Choice(name="🇪🇸 Español", value="es"),
        app_commands.Choice(name="🇺🇸 English", value="en")
    ])
    async def configserver(self, interaction: discord.Interaction, idioma: app_commands.Choice[str]):
        from src.database import db as database_module
        await database_module.set_guild_language(interaction.guild_id, idioma.value)
        lang_name = "Español" if idioma.value == "es" else "English"
        await interaction.response.send_message(
            t("configserver_success", idioma.value, lang_name=lang_name), ephemeral=True
        )

    @app_commands.command(name="language", description="Cambia el idioma del bot para ti / Change the bot's language for you.")
    @app_commands.choices(idioma=[
        app_commands.Choice(name="🇪🇸 Español", value="es"),
        app_commands.Choice(name="🇺🇸 English", value="en")
    ])
    async def language_command(self, interaction: discord.Interaction, idioma: app_commands.Choice[str]):
        await db.set_user_language(interaction.user.id, idioma.value)
        if idioma.value == "es":
            await interaction.response.send_message(f"✅ Idioma actualizado a **Español**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Language updated to **English**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Settings(bot))
