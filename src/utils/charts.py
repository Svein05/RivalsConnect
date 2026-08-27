import os
import io
from typing import List, Dict, Any, Optional
import matplotlib
matplotlib.use('Agg')  # Modo no interactivo para entornos de servidor
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "ranks")

TIER_THRESHOLDS = [
    {"en": "One Above All", "es": "El Que Está Por Encima", "score": 5400, "icon": "one_above_all"},
    {"en": "Eternity", "es": "Eternidad", "score": 5100, "icon": "eternity"},
    {"en": "Celestial 1", "es": "Celestial 1", "score": 5000, "icon": "celestial"},
    {"en": "Celestial 2", "es": "Celestial 2", "score": 4900, "icon": "celestial"},
    {"en": "Celestial 3", "es": "Celestial 3", "score": 4800, "icon": "celestial"},
    {"en": "Grandmaster 1", "es": "Gran Maestro 1", "score": 4700, "icon": "grandmaster"},
    {"en": "Grandmaster 2", "es": "Gran Maestro 2", "score": 4600, "icon": "grandmaster"},
    {"en": "Grandmaster 3", "es": "Gran Maestro 3", "score": 4500, "icon": "grandmaster"},
    {"en": "Diamond 1", "es": "Diamante 1", "score": 4400, "icon": "diamond"},
    {"en": "Diamond 2", "es": "Diamante 2", "score": 4300, "icon": "diamond"},
    {"en": "Diamond 3", "es": "Diamante 3", "score": 4200, "icon": "diamond"},
    {"en": "Platinum 1", "es": "Platino 1", "score": 4100, "icon": "platinum"},
    {"en": "Platinum 2", "es": "Platino 2", "score": 4000, "icon": "platinum"},
    {"en": "Platinum 3", "es": "Platino 3", "score": 3900, "icon": "platinum"},
    {"en": "Gold 1", "es": "Oro 1", "score": 3800, "icon": "gold"},
    {"en": "Gold 2", "es": "Oro 2", "score": 3700, "icon": "gold"},
    {"en": "Gold 3", "es": "Oro 3", "score": 3600, "icon": "gold"},
    {"en": "Silver 1", "es": "Plata 1", "score": 3500, "icon": "silver"},
    {"en": "Silver 2", "es": "Plata 2", "score": 3400, "icon": "silver"},
    {"en": "Silver 3", "es": "Plata 3", "score": 3300, "icon": "silver"},
    {"en": "Bronze 1", "es": "Bronce 1", "score": 3200, "icon": "bronze"},
    {"en": "Bronze 2", "es": "Bronce 2", "score": 3100, "icon": "bronze"},
    {"en": "Bronze 3", "es": "Bronce 3", "score": 3000, "icon": "bronze"},
]

def generate_rank_progression_chart(
    history_points: Optional[List[Dict[str, Any]]] = None,
    season_name: str = "S9.5",
    current_rs: float = 0,
    peak_rs: float = 0,
    lang: str = "es",
    rank_history_matches: Optional[List[Dict[str, Any]]] = None,
    rank_history_summary: Optional[Dict[str, Any]] = None,
    rank_transitions: Optional[List[Dict[str, Any]]] = None
) -> io.BytesIO:
    """
    Genera un gráfico PNG idéntico al de RivalsMeta con toda la progresión de la temporada.
    Utiliza GridSpec para maximizar el ancho de la curva (86%) y mantener la barra lateral fija (14%).
    """
    scores = []
    matches = rank_history_matches or []
    summary = rank_history_summary or {}
    transitions = rank_transitions or []
    
    if matches:
        scores.append(matches[0].get("score_before", matches[0].get("score_after", 4500)))
        for m in matches:
            scores.append(m.get("score_after", scores[-1]))
    elif history_points:
        scores = [p["rs"] for p in history_points if "rs" in p]
        
    if not scores:
        base = current_rs if current_rs > 0 else 4500
        scores = [base - 20, base]
        
    total_games = summary.get("total_games", len(matches) if matches else len(scores))
    net_score = summary.get("net_score", round(scores[-1] - scores[0], 1))
    net_str = f"+{int(net_score)} RS" if net_score >= 0 else f"{int(net_score)} RS"
    
    # Paleta de colores Dark Theme idéntica a RivalsMeta
    bg_color = "#10141d"
    line_orange = "#f97316"
    grid_dashed = "#222a38"
    green_promo = "#22c55e"
    red_demo = "#f43f5e"
    text_gray = "#64748b"

    fig = plt.figure(figsize=(10.5, 4.5), dpi=140)
    fig.patch.set_facecolor(bg_color)
    
    # 2 columnas proporcionales: Barra lateral compacta (1.4), Curva panorámica completa (8.6)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 8.6], wspace=0.0)
    
    ax_sidebar = fig.add_subplot(gs[0])
    ax_curve = fig.add_subplot(gs[1], sharey=ax_sidebar)
    
    ax_sidebar.set_facecolor(bg_color)
    ax_curve.set_facecolor(bg_color)

    x_vals = list(range(len(scores)))
    y_vals = scores
    ax_curve.plot(x_vals, y_vals, color=line_orange, linewidth=2.2, zorder=4)

    min_s = min(scores)
    max_s = max(scores)
    pad = max(30, (max_s - min_s) * 0.12)
    ax_curve.set_ylim(min_s - pad, max_s + pad)
    ax_curve.set_xlim(0, max(1, len(scores) - 0.5))

    # Líneas guía de rangos con icono oficial y texto
    for tier in TIER_THRESHOLDS:
        score_val = tier["score"]
        if min_s - 50 <= score_val <= max_s + 50:
            name = tier.get(lang, tier["en"])
            
            # Línea discontinua en ambos subplots para continuidad perfecta
            ax_curve.axhline(y=score_val, color=grid_dashed, linestyle="--", linewidth=1.0, zorder=2)
            ax_sidebar.axhline(y=score_val, color=grid_dashed, linestyle="--", linewidth=1.0, zorder=2)
            
            icon_file = os.path.join(ASSETS_DIR, f"{tier['icon']}.png")
            if os.path.exists(icon_file):
                try:
                    img = Image.open(icon_file).convert("RGBA")
                    img.thumbnail((22, 22), Image.Resampling.LANCZOS)
                    imagebox = OffsetImage(img, zoom=0.65)
                    ab = AnnotationBbox(imagebox, (0.16, score_val), frameon=False, zorder=5)
                    ax_sidebar.add_artist(ab)
                except Exception:
                    pass
                
            ax_sidebar.text(
                0.32, score_val, f" {name}", 
                color=text_gray, fontsize=8.2, va="center", ha="left",
                fontweight="normal"
            )

    # Marcar transiciones de ascenso y descenso con círculos huecos
    uid_to_idx = {m.get("match_uid"): idx for idx, m in enumerate(matches, 1)}
    for t in transitions:
        m_uid = t.get("match_uid")
        if m_uid in uid_to_idx:
            idx = uid_to_idx[m_uid]
            if idx < len(scores):
                score_at = scores[idx]
                color = green_promo if t.get("type") == "promotion" else red_demo
                ax_curve.scatter([idx], [score_at], s=45, facecolors=bg_color, edgecolors=color, linewidth=2.2, zorder=6)

    # Configurar bordes de la barra lateral (la espina derecha es la divisoria vertical)
    for spine_name, spine in ax_sidebar.spines.items():
        if spine_name == "right":
            spine.set_visible(True)
            spine.set_color("#1e293b")
            spine.set_linewidth(1.2)
        else:
            spine.set_visible(False)
            
    ax_sidebar.set_xticks([])
    ax_sidebar.set_yticks([])
    ax_sidebar.set_xlim(0, 1)

    # Remover spines del gráfico de la curva
    for spine in ax_curve.spines.values():
        spine.set_visible(False)
    ax_curve.set_xticks([])
    ax_curve.set_yticks([])

    # Textos de cabecera bilingües
    title_text = "Progresión de Rango" if lang == "es" else "Rank Progression"
    games_text = f"{total_games} partidas" if lang == "es" else f"{total_games} games"

    fig.text(0.04, 0.92, str(season_name), color=text_gray, fontsize=9, fontweight="bold")
    fig.text(0.04, 0.86, title_text, color="#f8fafc", fontsize=13, fontweight="bold")

    fig.text(0.85, 0.88, games_text, color="#cbd5e1", fontsize=11, fontweight="bold", ha="right")
    fig.text(0.96, 0.88, f" {net_str} ", color="#22c55e" if net_score >= 0 else "#ef4444", 
             fontsize=10.5, fontweight="bold", ha="right",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="#064e3b" if net_score >= 0 else "#4c0519", edgecolor="none"))

    plt.subplots_adjust(left=0.04, right=0.97, top=0.82, bottom=0.06)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=bg_color, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf
