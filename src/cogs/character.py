import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Any
from src.utils.wiki import get_hero_wiki_data
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

class CharacterView(discord.ui.View):
    def __init__(self, hero_data: Dict[str, Any], lang: str = "es", author_id: int = 0):
        super().__init__(timeout=180)
        self.hero_data = hero_data
        self.lang = lang
        self.author_id = author_id
        self.current_tab = "overview"
        self._update_buttons()

    def _update_buttons(self):
        self.btn_overview.style = discord.ButtonStyle.primary if self.current_tab == "overview" else discord.ButtonStyle.secondary
        self.btn_abilities.style = discord.ButtonStyle.primary if self.current_tab == "abilities" else discord.ButtonStyle.secondary
        self.btn_teamups.style = discord.ButtonStyle.primary if self.current_tab == "teamups" else discord.ButtonStyle.secondary
        
        self.btn_overview.label = t("char_btn_overview", self.lang)
        self.btn_abilities.label = t("char_btn_abilities", self.lang)
        self.btn_teamups.label = t("char_btn_teamups", self.lang)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(t("char_not_your_menu", self.lang), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="btn_overview")
    async def btn_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_tab = "overview"
        self._update_buttons()
        embed = render_overview_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Abilities", style=discord.ButtonStyle.secondary, emoji="⚡", custom_id="btn_abilities")
    async def btn_abilities(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_tab = "abilities"
        self._update_buttons()
        embed = render_abilities_embed(self.hero_data, self.lang)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Team-Ups", style=discord.ButtonStyle.secondary, emoji="🤝", custom_id="btn_teamups")
    async def btn_teamups(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_tab = "teamups"
        self._update_buttons()
        embed = render_teamups_embed(self.hero_data, self.lang)
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
    
    lore = data.get("lore_quote")
    if lore:
        embed.description = f"*\"{lore}\"*\n\u200b"
        
    # Ficha Técnica
    health = data.get("health", 250)
    diff = data.get("difficulty", 3)
    stars = get_difficulty_stars(diff)
    real_name = data.get("real_name", "???")
    voice = data.get("voice_actor", t("unknown", lang))
    aff = data.get("affiliation", "Marvel Rivals")
    
    stats_text = (
        f"• **{t('char_hp', lang)}:** `{health} HP`\n"
        f"• **{t('char_difficulty', lang)}:** {stars}\n"
        f"• **{t('char_real_name', lang)}:** {real_name}\n"
        f"• **{t('char_voice', lang)}:** {voice}\n"
        f"• **{t('char_affiliation', lang)}:** {aff}"
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
            value_line = desc if len(desc) <= 300 else desc[:297] + "..."
            embed.add_field(name=title_line, value=value_line if value_line else "-", inline=False)
            
    portrait_url = data.get("portrait_url")
    if portrait_url:
        embed.set_thumbnail(url=portrait_url)
        
    embed.set_footer(text=t("char_wiki_footer", lang))
    return embed

def render_teamups_embed(data: Dict[str, Any], lang: str = "es") -> discord.Embed:
    role_key = data.get("role_key", "unknown")
    short_code = data.get("short_code", "unknown")
    emoji = get_hero_emoji_str(short_code, role_key)
    display_name = data.get("display_name", "Hero")
    
    embed = discord.Embed(
        title=f"{emoji} {t('char_teamups_title', lang, name=display_name)}",
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
            value_line = desc if len(desc) <= 300 else desc[:297] + "..."
            embed.add_field(name=title_line, value=value_line if value_line else "-", inline=False)
            
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
        
        # Encontrar clave canon
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
            embed = render_overview_embed(wiki_data, lang=lang)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error en comando /character para {personaje}: {e}")
            await interaction.followup.send(t("char_error", lang), ephemeral=True)

async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
