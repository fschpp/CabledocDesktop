"""
signal_risk_diagrama_ui.py — Mixin de UI para DiagramaConexiones
====================================================================
Agrega "🎨 Colorear por riesgo de señal" al diagrama de conexiones,
coloreando en ámbar/naranja/rojo los cables con riesgo activo según
signal_risk.py (plan_riesgo_senal_audio.md, sección 5.2). Distinto del
riesgo de IMPACTO/falla de equipo que ya cubre riesgo_diagrama_ui.py —
acá el riesgo es de CALIDAD DE SEÑAL y se pinta sobre el CABLE (arista),
no sobre el equipo (nodo).

Sigue el mismo patrón que RiesgoDiagramaMixin/ImpactoMixin: se mezcla
por herencia múltiple en DiagramaConexiones.

Integración en pantallas_avanzadas.py (aplicada):
  1. class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin,
                               RiesgoSenalDiagramaMixin, Gtk.Dialog):
  2. self._riesgo_senal_init(db_path)     — junto a self._riesgo_init(...)
  3. for w in self._riesgo_senal_crear_items_menu(): menu_riesgo.append(w)
  4. _calc_conn_colors() consulta self._riesgo_senal_conn_colors() y lo
     fusiona con los colores de selección (el de riesgo tiene prioridad,
     para que se vea aunque haya un nodo seleccionado).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

try:
    from i18n import _
except ImportError:
    def _(t): return t


class RiesgoSenalDiagramaMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple."""

    # Colores por eje (mismo criterio de "no fusionar en un score único"
    # que signal_risk.py: si un cable tiene más de un eje activo, se pinta
    # con el de mayor severidad, pero el tooltip lista todos).
    _COLOR_ATENUACION  = (0.90, 0.55, 0.10)   # naranja
    _COLOR_ANCHO_BANDA = (0.90, 0.75, 0.10)   # ámbar
    _COLOR_FORMATO     = (0.85, 0.15, 0.15)   # rojo (incluye ELECTRICO/BALANCE/CANAL)
    _EJES_FORMATO = ("ELECTRICO", "BALANCE", "CANAL")

    # ── Init ─────────────────────────────────────────────────────────────
    def _riesgo_senal_init(self, db_path: str) -> None:
        """Llamar al final de __init__, junto a self._riesgo_init(...)."""
        self._riesgo_senal_db_path = db_path
        self._riesgo_senal_color_activo = False
        self._riesgo_senal_cache = {}   # {id_cable(str): [(eje, detalle), ...]}
        # No se calcula en __init__ (recorre todos los cables): sólo al
        # activar el toggle, igual que RiesgoDiagramaMixin con su caché.

    def _riesgo_senal_cargar_cache(self) -> None:
        try:
            from signal_risk import SignalRiskAnalyzer
            analyzer = SignalRiskAnalyzer(self._riesgo_senal_db_path)
            self._riesgo_senal_cache = analyzer.resumen_por_cable()
        except Exception:
            self._riesgo_senal_cache = {}

    # ── Ítems de menú ───────────────────────────────────────────────────
    def _riesgo_senal_crear_items_menu(self) -> list:
        self._riesgo_senal_btn_toggle = Gtk.CheckMenuItem(
            label=_("🎨 Colorear por riesgo de señal"))
        self._riesgo_senal_btn_toggle.set_tooltip_text(
            "Pinta los cables con riesgo de calidad de señal activo: "
            "naranja = atenuación (tramo analógico largo), ámbar = "
            "cuello de botella de ancho de banda, rojo = mismatch de "
            "formato (balance/canal/eléctrico).\n"
            "Requiere haber cargado los datos de catálogo (tipo de "
            "cable, tipo de ficha) — ver Catálogos → Tipos de Cable / "
            "Tipos de Ficha.")
        self._riesgo_senal_btn_toggle.connect(
            "toggled", self._riesgo_senal_on_toggle_color)
        return [self._riesgo_senal_btn_toggle]

    # ── Handlers ─────────────────────────────────────────────────────────
    def _riesgo_senal_on_toggle_color(self, btn) -> None:
        self._riesgo_senal_color_activo = btn.get_active()
        if self._riesgo_senal_color_activo:
            self._riesgo_senal_cargar_cache()
        self._da.queue_draw()

    # ── Integración con _calc_conn_colors / _draw_conn ──────────────────
    def _riesgo_senal_conn_colors(self) -> dict:
        """Devuelve {id_cable: (r,g,b)} para cables con riesgo activo, o
        {} si el toggle está apagado (no-op, seguro de llamar siempre)."""
        if not self._riesgo_senal_color_activo:
            return {}
        colores = {}
        for id_cable, activos in self._riesgo_senal_cache.items():
            ejes = {e for e, _d in activos}
            if ejes & set(self._EJES_FORMATO):
                colores[id_cable] = self._COLOR_FORMATO
            elif "ATENUACION" in ejes:
                colores[id_cable] = self._COLOR_ATENUACION
            elif "ANCHO_BANDA" in ejes:
                colores[id_cable] = self._COLOR_ANCHO_BANDA
        return colores

    def _riesgo_senal_tooltip(self, id_cable) -> str:
        """Detalle concatenado de los riesgos activos de un cable, para
        usar como tooltip/estado al pasar el mouse (mismo criterio de
        signal_risk.py: no fusiona ejes, los lista todos)."""
        activos = self._riesgo_senal_cache.get(str(id_cable))
        if not activos:
            return ""
        return " | ".join(f"{eje}: {detalle}" for eje, detalle in activos)
