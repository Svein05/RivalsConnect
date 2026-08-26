import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Any, Optional, List
from src.database import db
from src.database.db import format_relative_time
from src.utils.i18n import t, translate_rank
from src.utils.parser import APP_EMOJIS, get_hero_emoji
from src.utils.heroes import get_hero_data
from src.utils.rivalsmeta import fetch_player_from_rivalsmeta
from src.utils.charts import generate_rank_progression_chart
import logging

logger = logging.getLogger("profile_cog")

ROLE_FALLBACK = {
    "vanguard": "🛡️",
    "duelist": "⚔️",
    "strategist": "💚"
}

PAGE_NAMES = ["overview", "heroes", "ranked", "maps"]

class ModeSelect(discord.ui.Select):
    def __init__(self, parent_view: 'ProfileView'):
        self.parent_view = parent_view
        current_mode = parent_view.selected_mode
        options = [
            discord.SelectOption(
                label=t("profile_mode_competitive", parent_view.lang),
                value="ranked",
                emoji="🏆",
                default=(current_mode == "ranked")
            ),
            discord.SelectOption(
                label=t("profile_mode_quickplay", parent_view.lang),
                value="unranked",
                emoji="🎮",
                default=(current_mode == "unranked")
            )
        ]
        super().__init__(
            placeholder=t("profile_select_mode_placeholder", parent_view.lang),
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_mode = self.values[0]
        self.parent_view._update_components()
        embed, file = await self.parent_view.render_current_page()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self.parent_view)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self.parent_view)

class ProfileView(discord.ui.View):
    def __init__(
        self,
        target: discord.Member,
        user_data: tuple,
        meta_data: Optional[Dict[str, Any]],
        lang: str = "es",
        author_id: int = 0
    ):
        super().__init__(timeout=240)
        self.target = target
        self.user_data = user_data
        self.meta_data = meta_data
        self.lang = lang
        self.author_id = author_id
        self.current_page_idx = 0  # 0: Overview, 1: Heroes, 2: Ranked/Graph, 3: Maps
        self.selected_mode = "ranked"  # "ranked" o "unranked"
        self._update_components()

    def _update_components(self):
        self.clear_items()
        
        # 1. Menú selector de modo en páginas de Héroes (1) y Mapas (3)
        if self.current_page_idx in (1, 3):
            self.add_item(ModeSelect(self))
            
        in_game_uid = self.user_data[7]
        # 2. Botón URL directo a RivalsMeta
        if in_game_uid:
            btn_rivals = discord.ui.Button(
                label=t("btn_view_rivalsmeta", self.lang),
                url=f"https://rivalsmeta.com/player/{in_game_uid}",
                style=discord.ButtonStyle.link,
                emoji="🌐",
                row=1
            )
            self.add_item(btn_rivals)
            
        # 3. Botones de Navegación Circular (◀ y ▶)
        btn_prev = discord.ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id="btn_profile_prev"
        )
        btn_prev.callback = self.prev_page_cb
        self.add_item(btn_prev)
        
        btn_next = discord.ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id="btn_profile_next"
        )
        btn_next.callback = self.next_page_cb
        self.add_item(btn_next)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(t("char_not_your_menu", self.lang), ephemeral=True)
            return False
        return True

    async def prev_page_cb(self, interaction: discord.Interaction):
        self.current_page_idx = (self.current_page_idx - 1) % len(PAGE_NAMES)
        self._update_components()
        embed, file = await self.render_current_page()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def next_page_cb(self, interaction: discord.Interaction):
        self.current_page_idx = (self.current_page_idx + 1) % len(PAGE_NAMES)
        self._update_components()
        embed, file = await self.render_current_page()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def render_current_page(self):
        page_name = PAGE_NAMES[self.current_page_idx]
        if page_name == "overview":
            return await self.render_overview_page(), None
        elif page_name == "heroes":
            return await self.render_heroes_page(), None
        elif page_name == "ranked":
            return await self.render_ranked_page()
        elif page_name == "maps":
            return await self.render_maps_page(), None
        return await self.render_overview_page(), None

    async def render_overview_page(self) -> discord.Embed:
        elo_score = self.user_data[6] or 0
        in_game_uid = self.user_data[7]
        
        rank_key = await db.get_user_rank(elo_score)
        rank_name = translate_rank(rank_key, self.lang)
        
        embed = discord.Embed(
            title=t("profile_title", self.lang, name=self.target.display_name),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        if self.target.avatar:
            embed.set_thumbnail(url=self.target.avatar.url)
            
        embed.add_field(name=t("profile_comp_rank", self.lang), value=f"**{rank_name}** ({elo_score} ELO)", inline=False)
        if in_game_uid:
            embed.add_field(name=t("profile_rivals_id", self.lang), value=f"`{in_game_uid}`", inline=False)
            
        # Cargar los Lords del usuario
        user_lords = await db.get_user_lords(self.target.id)
        fake_lords_dict = {}
        if user_lords:
            fake_lords_dict[str(self.target.id)] = {char.upper(): title for char, title in user_lords}
            lords_text = []
            for char, title in user_lords:
                short_name = get_hero_data(char)["short_code"]
                title_suffix = "lordani" if (title == "Animated Lord" or title == "Champion") else "lord"
                emoji_name = f"{short_name}_{title_suffix}"
                emoji = APP_EMOJIS.get(emoji_name, "🌟" if title_suffix == "lordani" else "👑")
                lords_text.append(f"{emoji}")
            embed.add_field(name=t("profile_titles_section", self.lang), value=" ".join(lords_text), inline=False)
            
        # --- Top Personajes Lado a Lado (Competitivo y Casual) ---
        comp_heroes_lines = []
        casual_heroes_lines = []
        
        if self.meta_data and self.meta_data.get("heroes_ranked"):
            for h in self.meta_data["heroes_ranked"][:5]:
                emoji = get_hero_emoji(h["name"], str(self.target.id), fake_lords_dict, True)
                comp_heroes_lines.append(f"{emoji} **{h['name']}** | {h['wr']}% WR\n└ `{h['kda']} KDA` ({h['matches']}P)")
        else:
            local_comp = await db.get_top_characters(self.target.id, mode_type="ranked", limit=5)
            for cname, tgames, wins, ak, ad, aa in local_comp:
                emoji = get_hero_emoji(cname, str(self.target.id), fake_lords_dict, True)
                wr = int((wins / tgames) * 100) if tgames > 0 else 0
                kda = round((ak + aa) / max(1, ad), 2)
                comp_heroes_lines.append(f"{emoji} **{cname}** | {wr}% WR\n└ `{kda} KDA` ({tgames}P)")
                
        if self.meta_data and self.meta_data.get("heroes_unranked"):
            for h in self.meta_data["heroes_unranked"][:5]:
                emoji = get_hero_emoji(h["name"], str(self.target.id), fake_lords_dict, True)
                casual_heroes_lines.append(f"{emoji} **{h['name']}** | {h['wr']}% WR\n└ `{h['kda']} KDA` ({h['matches']}P)")
        else:
            local_casual = await db.get_top_characters(self.target.id, mode_type="unranked", limit=5)
            for cname, tgames, wins, ak, ad, aa in local_casual:
                emoji = get_hero_emoji(cname, str(self.target.id), fake_lords_dict, True)
                wr = int((wins / tgames) * 100) if tgames > 0 else 0
                kda = round((ak + aa) / max(1, ad), 2)
                casual_heroes_lines.append(f"{emoji} **{cname}** | {wr}% WR\n└ `{kda} KDA` ({tgames}P)")
                
        val_comp = "\n".join(comp_heroes_lines) if comp_heroes_lines else t("profile_no_heroes", self.lang)
        val_cas = "\n".join(casual_heroes_lines) if casual_heroes_lines else t("profile_no_heroes", self.lang)
        
        embed.add_field(name=t("profile_top_comp", self.lang), value=val_comp, inline=True)
        embed.add_field(name=t("profile_top_casual", self.lang), value=val_cas, inline=True)
        
        # --- Historial Reciente (10 Partidas con Formato Exacto) ---
        recent_matches = await db.get_recent_matches(self.target.id, limit=10)
        if recent_matches:
            history_text = []
            for match in recent_matches:
                elo_change = match[0] or 0
                m_k = match[1]
                m_d = match[2]
                m_a = match[3]
                m_outcome = match[6] or ""
                m_char = match[7] or "???"
                m_mode_raw = match[8] or "unknown"
                m_date = match[10]
                
                # Indicador de Resultado
                if "victor" in m_outcome.lower() or "win" in m_outcome.lower():
                    prefix = "🔹VICTORIA"
                elif "defeat" in m_outcome.lower() or "loss" in m_outcome.lower() or "derrot" in m_outcome.lower():
                    prefix = "🔸DERROTA"
                else:
                    prefix = "⬜TERMINADA"
                    
                # Indicador de Modo / Ranked
                is_ranked = "comp" in m_mode_raw.lower() or "rank" in m_mode_raw.lower() or elo_change != 0
                if is_ranked:
                    if elo_change > 0:
                        mode_tag = f"RANKED🔺+ {elo_change}"
                    elif elo_change < 0:
                        mode_tag = f"RANKED🔻- {abs(elo_change)}"
                    else:
                        mode_tag = "RANKED"
                else:
                    mode_tag = "QUICKPLAY"
                    
                emoji = get_hero_emoji(m_char, str(self.target.id), fake_lords_dict, True)
                mode_name = t(f"mode_{m_mode_raw.lower()}", self.lang)
                if mode_name.startswith("[mode_"): 
                    mode_name = m_mode_raw.capitalize()
                    
                rel_time = format_relative_time(m_date, self.lang)
                line = f"{prefix} | {mode_tag} | {emoji} `{m_k}/{m_d}/{m_a}` | {mode_name} | {rel_time}"
                history_text.append(line)
                
            embed.add_field(name=t("profile_recent_section", self.lang, num=len(recent_matches)), value="\n".join(history_text), inline=False)
        else:
            embed.add_field(name=t("profile_recent_title", self.lang), value=t("profile_recent_empty", self.lang), inline=False)
            
        embed.set_footer(text=f"{t('profile_footer', self.lang)} • Pag 1/4")
        return embed

    async def render_heroes_page(self) -> discord.Embed:
        mode = self.selected_mode
        is_comp = (mode == "ranked")
        mode_label = t("profile_mode_competitive" if is_comp else "profile_mode_quickplay", self.lang)
        
        embed = discord.Embed(
            title=f"🦸 {t('profile_page_heroes', self.lang)} ({mode_label}) — {self.target.display_name}",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        if self.target.avatar:
            embed.set_thumbnail(url=self.target.avatar.url)
            
        heroes_list = []
        role_wr = {}
        if self.meta_data:
            heroes_list = self.meta_data.get("heroes_ranked" if is_comp else "heroes_unranked", [])
            role_wr = self.meta_data.get("role_wr_ranked" if is_comp else "role_wr_unranked", {})
            
        # Barra de resumen por Roles
        vg = role_wr.get("vanguard", {"wr": 0.0, "matches": 0, "wins": 0, "losses": 0})
        du = role_wr.get("duelist", {"wr": 0.0, "matches": 0, "wins": 0, "losses": 0})
        st = role_wr.get("strategist", {"wr": 0.0, "matches": 0, "wins": 0, "losses": 0})
        
        roles_text = (
            f"🛡️ **Vanguard:** `{vg['wr']}%` ({vg['wins']}W {vg.get('losses',0)}L)\n"
            f"⚔️ **Duelist:** `{du['wr']}%` ({du['wins']}W {du.get('losses',0)}L)\n"
            f"💚 **Strategist:** `{st['wr']}%` ({st['wins']}W {st.get('losses',0)}L)"
        )
        embed.add_field(name=t("profile_roles_overview", self.lang), value=roles_text, inline=False)
        
        # Tabla detallada de Héroes
        user_lords = await db.get_user_lords(self.target.id)
        fake_lords_dict = {str(self.target.id): {char.upper(): title for char, title in user_lords}} if user_lords else {}
        
        if heroes_list:
            table_lines = []
            for h in heroes_list[:12]:
                emoji = get_hero_emoji(h["name"], str(self.target.id), fake_lords_dict, True)
                name = h["name"]
                m = h["matches"]
                wr = h["wr"]
                kda = h["kda"]
                dmg = h.get("dmg_per_min", 0)
                heal = h.get("heal_per_min", 0)
                
                extra = f" | ⚔️{dmg}/m" if dmg > 0 else ""
                if heal > 0:
                    extra += f" 💚{heal}/m"
                    
                table_lines.append(f"{emoji} **{name}**: `{m}P` | **{wr}%** WR | `{kda} KDA`{extra}")
                
            embed.add_field(name=f"Top Héroes ({len(heroes_list)} registrados)", value="\n".join(table_lines), inline=False)
        else:
            embed.add_field(name="Héroes", value=t("profile_no_heroes", self.lang), inline=False)
            
        embed.set_footer(text=f"{t('profile_footer', self.lang)} • Pag 2/4")
        return embed

    async def render_ranked_page(self):
        elo_score = self.user_data[6] or 0
        rank_key = await db.get_user_rank(elo_score)
        rank_name = translate_rank(rank_key, self.lang)
        
        embed = discord.Embed(
            title=t("profile_rank_progression_title", self.lang, name=self.target.display_name),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        if self.target.avatar:
            embed.set_thumbnail(url=self.target.avatar.url)
            
        peak_rs = elo_score
        total_games = 0
        win_rate = 0.0
        active_season = 9.5
        history_points = []
        
        if self.meta_data:
            peak_rs = max(elo_score, self.meta_data.get("peak_rs", elo_score))
            total_games = self.meta_data.get("ranked_matches", 0)
            win_rate = self.meta_data.get("ranked_wr", 0.0)
            active_season = self.meta_data.get("active_season") or 9.5
            history_points = self.meta_data.get("rank_history_points", [])
            
        embed.add_field(name=t("profile_comp_rank", self.lang), value=f"**{rank_name}** ({elo_score} RS)", inline=True)
        embed.add_field(name=t("profile_rank_peak", self.lang), value=f"**{peak_rs} RS**", inline=True)
        embed.add_field(name=t("profile_rank_total_games", self.lang), value=f"`{total_games}` ({win_rate}% WR)", inline=True)
        
        # Generar gráfico de progresión en memoria
        chart_buf = generate_rank_progression_chart(
            history_points=history_points,
            season_name=f"S{active_season}",
            current_rs=elo_score,
            peak_rs=peak_rs
        )
        file = discord.File(fp=chart_buf, filename="rank_progression.png")
        embed.set_image(url="attachment://rank_progression.png")
        
        embed.set_footer(text=f"{t('profile_footer', self.lang)} • Pag 3/4")
        return embed, file

    async def render_maps_page(self) -> discord.Embed:
        mode = self.selected_mode
        is_comp = (mode == "ranked")
        mode_label = t("profile_mode_competitive" if is_comp else "profile_mode_quickplay", self.lang)
        
        embed = discord.Embed(
            title=f"🗺️ {t('profile_maps_title', self.lang, name=self.target.display_name)} ({mode_label})",
            color=discord.Color.teal(),
            timestamp=discord.utils.utcnow()
        )
        if self.target.avatar:
            embed.set_thumbnail(url=self.target.avatar.url)
            
        maps_list = self.meta_data.get("maps_data", []) if self.meta_data else []
        
        if maps_list:
            # Agrupar mapas por los 3 modos principales
            conv_maps = []
            convoy_maps = []
            dom_maps = []
            
            for m in maps_list:
                name = m["name"]
                cnt = m["matches"]
                wr = m["wr"]
                kda = m["kda"]
                t_str = m.get("time_str", "")
                line = f"• **{name}**: `{cnt}P` | **{wr}%** WR | `{kda} KDA` ({t_str})"
                
                # Clasificar mapa heurísticamente por nombre
                name_l = name.lower()
                if "wakanda" in name_l or "manhattan" in name_l or "klyntar" in name_l:
                    conv_maps.append(line)
                elif "eternal" in name_l or "yggsgard" in name_l or "gala" in name_l or "thebes" in name_l:
                    convoy_maps.append(line)
                else:
                    dom_maps.append(line)
                    
            if conv_maps:
                embed.add_field(name="🎯 Convergencia (Convergence)", value="\n".join(conv_maps[:5]), inline=False)
            if convoy_maps:
                embed.add_field(name="🛡️ Convoy", value="\n".join(convoy_maps[:5]), inline=False)
            if dom_maps:
                embed.add_field(name="⚔️ Dominación (Domination)", value="\n".join(dom_maps[:5]), inline=False)
        else:
            embed.add_field(name=t("profile_maps_title", self.lang, name=""), value=t("profile_no_maps", self.lang), inline=False)
            
        embed.set_footer(text=f"{t('profile_footer', self.lang)} • Pag 4/4")
        return embed

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Muestra el perfil completo, historial y estadísticas de un jugador.")
    async def profile(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        lang = await db.get_user_language(interaction.user.id)
        
        await interaction.response.defer()
        
        try:
            user_data = await db.get_user(target.id)
            if not user_data:
                await interaction.followup.send(
                    t("profile_no_account", lang, name=target.display_name),
                    ephemeral=True
                )
                return
                
            in_game_uid = user_data[7]
            elo_score = user_data[6] or 0
            
            # Sincronización controlada de 24h con RivalsMeta si tiene UID
            meta_data = None
            if in_game_uid:
                meta_data = await fetch_player_from_rivalsmeta(in_game_uid)
                if meta_data:
                    rivals_elo = int(meta_data.get("elo", 0))
                    if rivals_elo > 0 and rivals_elo != elo_score:
                        await db.update_user_elo(target.id, rivals_elo, in_game_uid)
                        user_list = list(user_data)
                        user_list[6] = rivals_elo
                        user_data = tuple(user_list)
                        
            view = ProfileView(
                target=target,
                user_data=user_data,
                meta_data=meta_data,
                lang=lang,
                author_id=interaction.user.id
            )
            embed, file = await view.render_current_page()
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)
                
        except Exception as e:
            logger.error(f"Error ejecutando /profile: {e}", exc_info=True)
            await interaction.followup.send(t("profile_error", lang), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Profile(bot))
