import io
import matplotlib
matplotlib.use('Agg')  # Modo no interactivo para entornos de servidor
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from typing import List, Dict, Any, Optional

def generate_rank_progression_chart(
    history_points: List[Dict[str, Any]], 
    season_name: str = "S9.5",
    current_rs: float = 0,
    peak_rs: float = 0
) -> io.BytesIO:
    """
    Genera un gráfico PNG elegante en tema oscuro imitando la interfaz de RivalsMeta
    con la curva de progresión de ELO/RS a lo largo de las partidas.
    """
    # Extraer puntuaciones de la lista
    # Cada punto esperado: {"rs": float, "is_win": bool, "change": float, "label": str}
    if not history_points:
        # Fallback con puntos base si no hay historial detallado
        history_points = [
            {"rs": current_rs * 0.98 if current_rs else 4500, "is_win": True},
            {"rs": current_rs if current_rs else 4500, "is_win": True}
        ]
        
    y_values = [p["rs"] for p in history_points]
    x_values = list(range(1, len(y_values) + 1))
    
    # Configurar dimensiones y DPI
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=130)
    
    # Colores Dark Theme
    bg_color = "#0f172a"      # Slate 900
    card_bg = "#1e293b"       # Slate 800
    line_color = "#f59e0b"    # Amber 500
    glow_color = "#fbbf24"    # Amber 400
    grid_color = "#334155"    # Slate 700
    text_color = "#94a3b8"    # Slate 400
    
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_bg)
    
    # Trazar línea de progresión
    ax.plot(x_values, y_values, color=line_color, linewidth=2.5, zorder=3, alpha=0.95)
    
    # Área sombreada bajo la curva
    min_y = min(y_values)
    padding = max(30, (max(y_values) - min_y) * 0.2)
    bottom_val = max(0, min_y - padding)
    ax.fill_between(x_values, y_values, bottom_val, color=line_color, alpha=0.12, zorder=2)
    
    # Dibujar puntos clave (primer punto, último punto, ascensos y descensos)
    for idx, (x, y) in enumerate(zip(x_values, y_values)):
        p = history_points[idx]
        change = p.get("change", 0)
        
        # Último punto siempre destacado
        if idx == len(x_values) - 1:
            ax.scatter([x], [y], color="#38bdf8", s=50, edgecolors="#ffffff", linewidth=1.5, zorder=5)
        elif change > 25: # Gran subida / Posible ascenso
            ax.scatter([x], [y], color="#10b981", s=30, edgecolors="#ffffff", linewidth=1, zorder=4)
        elif change < -25: # Gran bajada / Posible descenso
            ax.scatter([x], [y], color="#ef4444", s=30, edgecolors="#ffffff", linewidth=1, zorder=4)
            
    # Configuración de ejes y cuadrícula
    ax.grid(True, linestyle="--", alpha=0.3, color=grid_color, zorder=1)
    ax.tick_params(colors=text_color, labelsize=9)
    
    # Quitar bordes (spines) exteriores
    for spine in ax.spines.values():
        spine.set_visible(False)
        
    # Título y etiquetas
    delta = round(y_values[-1] - y_values[0], 1) if len(y_values) > 1 else 0
    delta_str = f"+{delta} RS" if delta >= 0 else f"{delta} RS"
    delta_color = "#10b981" if delta >= 0 else "#ef4444"
    
    ax.set_title(
        f"{season_name} Rank Progression  —  {len(history_points)} Games ({delta_str})",
        color="#f8fafc",
        fontsize=11,
        fontweight="bold",
        pad=12,
        loc="left"
    )
    
    ax.set_xlabel("Partidas Jugadas", color=text_color, fontsize=9, labelpad=8)
    ax.set_ylabel("Puntos de Rango (RS)", color=text_color, fontsize=9, labelpad=8)
    
    # Ajuste de límites del eje Y
    ax.set_ylim(bottom=bottom_val, top=max(y_values) + padding)
    
    plt.tight_layout()
    
    # Guardar en memoria BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
