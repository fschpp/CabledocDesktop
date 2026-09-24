"""
auditoria_diagrama_ui.py — Mixin de UI para DiagramaConexiones
==================================================================
Agrega "🕓 Colorear por auditoría" al diagrama de conexiones: cuando está
prendido, la cabecera de cada nodo se pinta con Modelo.color_escala_auditoria
(core/modelo.py) según su ultima_auditoria_fecha — más claro = auditado hace
poco, más oscuro = auditado hace más tiempo. Es una escala de un solo
tono, no relativa a los demás equipos del diagrama: agregar o quitar nodos
no cambia el color de los que ya estaban. Los equipos con la auditoría
vencida según el SLA (Modelo.devolver_vencidos_sla_auditoria: más viejos que
dias_sla_auditoria días, o nunca auditados) se pintan de un tercer tono,
naranja (Modelo.AUDITORIA_COLOR_VENCIDO) — Modelo.devolver_colores_
auditoria_equipos() resuelve ambos casos (Grupo E, E5).

Mismo patrón que senal_diagrama_ui.SenalDiagramaMixin (mismo autor de
diseño): init/cache + un CheckMenuItem + un método de una sola línea para
usar en _draw_node. Sin leyenda en el canvas (a diferencia de señal): la
explicación de la escala va en el tooltip del propio ítem de menú, para no
competir por las esquinas del canvas con impacto/riesgo/señal/escenario/
minimapa/vista previa, que ya las ocupan todas.

Integración en diagrama_conexiones_ui.py (ya aplicada):
  1. class DiagramaConexiones(..., AuditoriaDiagramaMixin, ..., Gtk.Dialog)
  2. menu_ver.append(self._auditoria_crear_item_menu())
  3. self._auditoria_init() junto a self._senal_init(DB_PATH)
  4. En _draw_node() (dibujo_diagrama_ui.py), antes de calcular el color de
     cabecera: rc, gc, bc = self._auditoria_color_nodo(nodo["id"], rc, gc, bc)
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.modelo import Modelo

try:
    from core.i18n import _
except ImportError:
    def _(t): return t


def _hex_a_rgb01(hexcolor: str) -> tuple:
    hexcolor = hexcolor.lstrip("#")
    return tuple(int(hexcolor[i:i+2], 16) / 255.0 for i in (0, 2, 4))


class AuditoriaDiagramaMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple."""

    # ── Init ─────────────────────────────────────────────────────────────
    def _auditoria_init(self) -> None:
        """Llamar en __init__, junto a self._senal_init(...) y compañía."""
        self._auditoria_color_activo = False   # toggle "🕓 Colorear por auditoría"
        self._auditoria_cache = {}   # str(id_equipo) -> "#rrggbb"
        self._auditoria_cargar_cache()

    def _auditoria_cargar_cache(self) -> None:
        """Recalcula el color de cada equipo a partir de su
        ultima_auditoria_fecha y del SLA de auditoría (Modelo.
        devolver_colores_auditoria_equipos). Barato: dos consultas en
        total, sin tocar el motor de grafo."""
        try:
            self._auditoria_cache = (
                Modelo.devolver_colores_auditoria_equipos())
        except Exception:
            self._auditoria_cache = {}

    # ── Ítem de menú ─────────────────────────────────────────────────────
    def _auditoria_crear_item_menu(self) -> Gtk.CheckMenuItem:
        """Devuelve el CheckMenuItem para agregar al menú "Ver"."""
        self._auditoria_btn_toggle = Gtk.CheckMenuItem(
            label=_("🕓 Colorear por auditoría"))
        self._auditoria_btn_toggle.set_tooltip_text(
            "Pinta la cabecera de cada equipo según hace cuánto se auditó "
            "en el campo (Modelo.marcar_auditado): más CLARO = auditado "
            "hace poco, más OSCURO = auditado hace más tiempo (el tono más "
            f"oscuro llega a los {Modelo.AUDITORIA_ESCALA_DIAS_MAX} días); "
            "NARANJA = auditoría vencida según el SLA (más vieja que el SLA "
            "de auditoría, o nunca auditado)."
        )
        self._auditoria_btn_toggle.connect("toggled", self._auditoria_on_toggle)
        return self._auditoria_btn_toggle

    # ── Handler ──────────────────────────────────────────────────────────
    def _auditoria_on_toggle(self, btn) -> None:
        self._auditoria_color_activo = btn.get_active()
        if self._auditoria_color_activo:
            self._auditoria_cargar_cache()   # traer el último dato al activar
        self._da.queue_draw()

    # ── Integración con _draw_node ──────────────────────────────────────
    def _auditoria_color_nodo(self, id_equipo, rc, gc, bc) -> tuple:
        """Dado el color (r,g,b) 0..1 que _draw_node iba a usar para la
        cabecera de ese nodo, devuelve la versión por auditoría si el
        toggle está activo. Si no, devuelve el color tal cual (no-op,
        seguro de llamar siempre)."""
        if not self._auditoria_color_activo:
            return rc, gc, bc
        hexcolor = self._auditoria_cache.get(str(id_equipo))
        if not hexcolor:
            return rc, gc, bc
        return _hex_a_rgb01(hexcolor)
