import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Any, Optional
from src.utils.wiki import get_hero_wiki_data, get_localized_hero_data
from src.utils.heroes import HERO_DB, get_hero_data
from src.utils.parser import APP_EMOJIS
from src.utils.i18n import t
from src.database import db
import logging

logger = logging.getLogger("character_cog")

ROLE_ICONS = {
    "vanguard": "🛡️",
    "duelist": "⚔️",
    "strategist": "💚",
}

def get_difficulty_stars(difficulty: int) -> str:
    """Retorna una representación visual de estrellas de 1 a 5."""
    difficulty = max(1, min(5, difficulty))
    return "⭐" * difficulty + "☆" * (5 - difficulty)

def get_hero_emoji_str(short_code: str, role_key: str) -> str:
    """Obtiene el emoji del héroe o fallback por rol."""
    emoji_key = f"{short_code}_lord"
    if emoji_key in APP_EMOJIS:
        return APP_EMOJIS[emoji_key]
    role_emoji_key = f"{role_key}_icon"
    if role_emoji_key in APP_EMOJIS:
        return APP_EMOJIS[role_emoji_key]
    return ROLE_ICONS.get(role_key, "🦸")

class AbilitySelect(discord.ui.Select):
    def __init__(self, parent_view: 'CharacterView'):
        self.parent_view = parent_view
        abilities = parent_view.hero_data.get("abilities", [])
        options = []
        
        # Opción para ver todas las habilidades juntas
        options.append(discord.SelectOption(
            label=t("char_select_all_abilities", parent_view.lang),
            value="ALL",
            emoji="📜",
            default=(parent_view.selected_ability_index is None)
        ))
        
        for idx, ab in enumerate(abilities[:24]):
            name = ab.get("name", f"Habilidad {idx+1}")
            key = ab.get("key", "")
            desc = f"Tecla: [{key}]" if key else "Habilidad"
            is_def = (parent_view.selected_ability_index == idx)
            options.append(discord.SelectOption(
                label=name[:100],
                value=str(idx),
                description=desc[:100],
                emoji="⚡",
                default=is_def
            ))
            
        super().__init__(
            placeholder=t("char_select_ability_placeholder", parent_view.lang),
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "ALL":
            self.parent_view.selected_ability_index = None
            embed = render_abilities_embed(self.parent_view.hero_data, self.parent_view.lang)
        else:
            idx = int(selected)
            self.parent_view.selected_ability_index = idx
            embed = render_single_ability_embed(self.parent_view.hero_data, idx, self.parent_view.lang)
            
        self.parent_view._update_components()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class TeamupSelect(discord.ui.Select):
    def __init__(self, parent_view: 'CharacterView'):
        self.parent_view = parent_view
        teamups = parent_view.hero_data.get("teamups", [])
        options = []
        
        options.append(discord.SelectOption(
            label=t("char_select_all_teamups", parent_view.lang),
            value="ALL",
            emoji="📜",
            default=(parent_view.selected_teamup_index is None)
        ))
        
        for idx, tu in enumerate(teamups[:24]):
            name = tu.get("name", f"Team-Up {idx+1}")
            partner = tu.get("partner", "")
            desc = f"Con: {partner}" if partner else "Sinergia"
            is_def = (parent_view.selected_teamup_index == idx)
            options.append(discord.SelectOption(
                label=name[:100],
                value=str(idx),
                description=desc[:100],
                emoji="🤝",
                default=is_def
            ))
            
        super().__init__(
            placeholder=t("char_select_teamup_placeholder", parent_view.lang),
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "ALL":
            self.parent_view.selected_teamup_index = None
            embed = render_teamups_embed(self.parent_view.hero_data, self.parent_view.lang)
        else:
            idx = int(selected)
            self.parent_view.selected_teamup_index = idx
            embed = render_single_teamup_embed(self.parent_view.hero_data, idx, self.parent_view.lang)
            
        self.parent_view._update_components()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class CharacterView(discord.ui.View):
    def __init__(self, raw_hero_data: Dict[str, Any], lang: str = "es", author_id: int = 0):
        super().__init__(timeout=240)
        self.raw_hero_data = raw_hero_data
        self.lang = lang
        self.hero_data = get_localized_hero_data(raw_hero_data, lang)
        self.author_id = author_id
        self.current_tab = "overview"
        self.selected_ability_index: Optional[int] = None
        self.selected_teamup_index: Optional[int] = None
        self._update_components()

    def _update_components(self):
        self.clear_items()
        
        # 1. Agregar dropdown si estamos en pestaña de habilidades o teamups
        if self.current_tab == "abilities" and self.hero_data.get("abilities"):
            self.add_item(AbilitySelect(self))
        elif self.current_tab == "teamups" and self.hero_data.get("teamups"):
            self.add_item(TeamupSelect(self))
            
        # 2. Botones de navegación (Fila 1)
        btn_ov = discord.ui.Button(
            label=t("char_btn_overview", self.lang),
            style=discord.ButtonStyle.primary if self.current_tab == "overview" else discord.ButtonStyle.secondary,
            emoji="🛡️",
            row=1
        )
        btn_ov.callback = self.btn_overview_cb
        self.add_item(btn_ov)
        
        btn_ab = discord.ui.Button(
            label=t("char_btn_abilities", self.lang),
            style=discord.ButtonStyle.primary if self.current_tab == "abilities" else discord.ButtonStyle.secondary,
            emoji="⚡",
            row=1
        )
        btn_ab.callback = self.btn_abilities_cb
        self.add_item(btn_ab)
        
        btn_tu = discord.ui.Button(
            label=t("char_btn_teamups", self.lang),
            style=discord.ButtonStyle.primary if self.current_tab == "teamups" else discord.ButtonStyle.secondary,
            emoji="🤝",
            row=1
        )
        btn_tu.callback = self.btn_teamups_cb
        self.add_item(btn_tu)
        
        btn_bal = discord.ui.Button(
            label=t("char_btn_balance", self.lang),
            style=discord.ButtonStyle.primary if self.current_tab == "balance" else discord.ButtonStyle.secondary,
            emoji="⚖️",
            row=1
        )
        btn_bal.callback = self.btn_balance_cb
        self.add_item(btn_bal)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(t("char_not_your_menu", self.lang), ephemeral=True)
            return False
        return True

    async def btn_overview_cb(self, interaction: discord.Interaction):
        self.current_tab = "overview"
        self._update_components()
        embed = render_overview_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

    async def btn_abilities_cb(self, interaction: discord.Interaction):
        self.current_tab = "abilities"
        self.selected_ability_index = None
        self._update_components()
        embed = render_abilities_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

    async def btn_teamups_cb(self, interaction: discord.Interaction):
        self.current_tab = "teamups"
        self.selected_teamup_index = None
        self._update_components()
        embed = render_teamups_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

    async def btn_balance_cb(self, interaction: discord.Interaction):
        self.current_tab = "balance"
        self._update_components()
        embed = render_balance_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

def render_overview_embed(data: Dict[str, Any], lang: str = "es") -> discord.Embed:
    role_key = data.get("role_key", "unknown")
    short_code = data.get("short_code", "unknown")
    emoji = get_hero_emoji_str(short_code, role_key)
    role_label = t(f"role_{role_key}", lang)
    display_name = data.get("display_name", "Hero")
    
    color = discord.Color.blue()
    if role_key == "vanguard":
        color = discord.Color.blue()
    elif role_key == "duelist":
        color = discord.Color.red()
    elif role_key == "strategist":
        color = discord.Color.green()
        
    embed = discord.Embed(
        title=f"{emoji} {display_name} — {role_label}",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Ficha Técnica Limpia
    health = data.get("health", 250)
    diff = data.get("difficulty", 3)
    stars = get_difficulty_stars(diff)
    
    stats_text = (
        f"• **{t('char_hp', lang)}:** `{health} HP`\n"
        f"• **{t('char_difficulty', lang)}:** {stars}\n"
        f"• **Rol:** **{role_label}**"
    )
    embed.add_field(name=t("char_info_section", lang), value=stats_text, inline=False)
    
    # Fortalezas
    strengths = data.get("strengths", [])
    if strengths:
        st_lines = [f"• {s}" for s in strengths[:4]]
        embed.add_field(name=t("char_strengths", lang), value="\n".join(st_lines), inline=False)
        
    # Debilidades
    weaknesses = data.get("weaknesses", [])
    if weaknesses:
        wk_lines = [f"• {w}" for w in weaknesses[:4]]
        embed.add_field(name=t("char_weaknesses", lang), value="\n".join(wk_lines), inline=False)
        
    portrait_url = data.get("portrait_url")
    if portrait_url:
        embed.set_thumbnail(url=portrait_url)
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_abilities_embed(data: Dict[str, Any], lang: str = "es") -> discord.Embed:
    role_key = data.get("role_key", "unknown")
    short_code = data.get("short_code", "unknown")
    emoji = get_hero_emoji_str(short_code, role_key)
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"{emoji} {t('char_abilities_title', lang, name=display_name)}",
        description=t("char_abilities_summary_desc", lang),
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow()
    )
    
    abilities = data.get("abilities", [])
    if not abilities:
        embed.description = t("char_no_abilities", lang)
    else:
        for ab in abilities:
            name = ab.get("name", "Skill")
            key = ab.get("key", "")
            desc = ab.get("description", "")
            
            key_str = f"`[{key}]` " if key else ""
            title_line = f"{key_str}**{name}**"
            value_line = desc if len(desc) <= 220 else desc[:217] + "..."
            embed.add_field(name=title_line, value=value_line if value_line else "-", inline=False)
            
    portrait_url = data.get("portrait_url")
    if portrait_url:
        embed.set_thumbnail(url=portrait_url)
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_single_ability_embed(data: Dict[str, Any], index: int, lang: str = "es") -> discord.Embed:
    abilities = data.get("abilities", [])
    if index < 0 or index >= len(abilities):
        return render_abilities_embed(data, lang)
        
    ab = abilities[index]
    name = ab.get("name", "Habilidad")
    key = ab.get("key", "")
    desc = ab.get("description", t("char_no_desc", lang))
    icon_url = ab.get("icon_url")
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"⚡ {name} — {display_name}",
        description=desc,
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow()
    )
    if key:
        embed.add_field(name=t("char_ability_key_label", lang), value=f"`[{key}]`", inline=True)
        
    if icon_url:
        embed.set_thumbnail(url=icon_url)
    elif data.get("portrait_url"):
        embed.set_thumbnail(url=data.get("portrait_url"))
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_teamups_embed(data: Dict[str, Any], lang: str = "es") -> discord.Embed:
    role_key = data.get("role_key", "unknown")
    short_code = data.get("short_code", "unknown")
    emoji = get_hero_emoji_str(short_code, role_key)
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"{emoji} {t('char_teamups_title', lang, name=display_name)}",
        description=t("char_teamups_summary_desc", lang),
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    teamups = data.get("teamups", [])
    if not teamups:
        embed.description = t("char_no_teamups", lang)
    else:
        for tu in teamups:
            name = tu.get("name", "Team-Up")
            partner = tu.get("partner", "")
            desc = tu.get("description", "")
            
            partner_str = f" *(con {partner})*" if partner else ""
            title_line = f"🤝 **{name}**{partner_str}"
            value_line = desc if len(desc) <= 250 else desc[:247] + "..."
            embed.add_field(name=title_line, value=value_line if value_line else "-", inline=False)
            
    portrait_url = data.get("portrait_url")
    if portrait_url:
        embed.set_thumbnail(url=portrait_url)
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_single_teamup_embed(data: Dict[str, Any], index: int, lang: str = "es") -> discord.Embed:
    teamups = data.get("teamups", [])
    if index < 0 or index >= len(teamups):
        return render_teamups_embed(data, lang)
        
    tu = teamups[index]
    name = tu.get("name", "Team-Up")
    partner = tu.get("partner", "")
    desc = tu.get("description", t("char_no_desc", lang))
    icon_url = tu.get("icon_url")
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"🤝 {name} — {display_name}",
        description=desc,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    if partner:
        embed.add_field(name=t("char_teamup_partner_label", lang), value=f"**{partner}**", inline=True)
        
    if icon_url:
        embed.set_thumbnail(url=icon_url)
    elif data.get("portrait_url"):
        embed.set_thumbnail(url=data.get("portrait_url"))
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_balance_embed(data: Dict[str, Any], lang: str = "es") -> discord.Embed:
    role_key = data.get("role_key", "unknown")
    short_code = data.get("short_code", "unknown")
    emoji = get_hero_emoji_str(short_code, role_key)
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"⚖️ {t('char_balance_title', lang, name=display_name)}",
        description=t("char_balance_desc", lang),
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )
    
    balances = data.get("balance_changes", [])
    if not balances:
        embed.description = t("char_no_balance", lang)
    else:
        # Mostrar los últimos 4 parches
        for patch in balances[:4]:
            version = patch.get("version", "Patch")
            date = patch.get("date", "")
            changes = patch.get("changes", [])
            
            date_str = f" `({date})`" if date else ""
            title_line = f"📅 **{version}**{date_str}"
            
            changes_text = "\n".join(changes[:8])
            if len(changes_text) > 1000:
                changes_text = changes_text[:997] + "..."
                
            embed.add_field(name=title_line, value=changes_text if changes_text else "-", inline=False)
            
    portrait_url = data.get("portrait_url")
    if portrait_url:
        embed.set_thumbnail(url=portrait_url)
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

class CharacterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def hero_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        choices = []
        clean_current = current.lower().strip()
        for hero_key, hdata in HERO_DB.items():
            disp_name = hdata.get("display_name", hero_key.title())
            if not clean_current or clean_current in hero_key or clean_current in disp_name.lower():
                choices.append(app_commands.Choice(name=disp_name, value=hero_key))
                if len(choices) >= 25:
                    break
        return choices

    @app_commands.command(name="character", description="Muestra información, habilidades y sinergias de un héroe de Marvel Rivals.")
    @app_commands.describe(personaje="El nombre del personaje a consultar.")
    @app_commands.autocomplete(personaje=hero_autocomplete)
    async def character(self, interaction: discord.Interaction, personaje: str):
        await interaction.response.defer()
        lang = await db.get_user_language(interaction.user.id)
        
        clean_name = personaje.lower().strip()
        hdata = get_hero_data(clean_name)
        
        hero_key = None
        for k, v in HERO_DB.items():
            if k == clean_name or v.get("display_name", "").lower() == clean_name:
                hero_key = k
                break
        if not hero_key:
            hero_key = clean_name
            
        try:
            wiki_data = await get_hero_wiki_data(hero_key)
            view = CharacterView(wiki_data, lang=lang, author_id=interaction.user.id)
            embed = render_overview_embed(view.hero_data, lang=lang)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error en comando /character para {personaje}: {e}")
            await interaction.followup.send(t("char_error", lang), ephemeral=True)

async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
