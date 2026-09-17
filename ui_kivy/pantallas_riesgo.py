"""
pantallas_riesgo.py — "Colorear por riesgo" en Kivy (roadmap de cierre
mobile, ítem 3).
=============================================================================
Equivalente a ui_gtk/riesgo_diagrama_ui.py (RiesgoDiagramaMixin, riesgo de
IMPACTO/falla de equipo — pinta la CABECERA del nodo) +
ui_gtk/signal_risk_diagrama_ui.py (RiesgoSenalDiagramaMixin, riesgo de
CALIDAD DE SEÑAL — pinta el CABLE). Se unifican en un solo módulo mobile
porque comparten toolbar ("Riesgo") y porque, a diferencia de desktop
(2 mixins separados con menús propios), acá conviene un solo lugar para
las dos cachés — mismo criterio de "un archivo por pantalla nueva" que ya
usa pantallas_senal.py/pantallas_diagnostico.py/pantallas_escenario.py.

Sigue el mismo patrón que pantallas_senal.py:
  - Funciones puras de carga de caché (cargar_cache_riesgo_equipo,
    cargar_cache_riesgo_senal), sin estado propio — el estado (toggle
    activo, caché cargada) vive en DiagramaConexiones (pantallas_
    diagrama.py), igual que _senal_color_activo/_senal_cache.
  - Colores ya en escala 0-1 (Kivy), no hex — a diferencia de
    _PALETA_SENAL (que sí necesita _hex_a_rgb01 porque son colores
    "inventados" para distinguir señales entre sí), acá los colores
    son los mismos tuples RGB 0-1 que ya usaba GTK/Cairo (_NIVEL_COLOR,
    _COLOR_ATENUACION/_ANCHO_BANDA/_FORMATO) — se copian tal cual, sin
    conversión.
  - "Simular falla del seleccionado" (antes un Gtk.Dialog modal con
    Gtk.TreeView) pasa a un Popup real con ScrollView + Label, mismo
    patrón que PopupDetalleSesion (pantallas_diagnostico.py).
  - Adaptación táctil: GTK exponía la simulación como ítem de menú
    ("🔺 Simular falla del seleccionado") que actuaba sobre
    self._sel_id del propio Cairo DrawingArea; acá es un botón de la
    toolbar del diagrama que lee self._canvas._sel_id (mismo lugar
    donde vive la selección en mobile, ver _CanvasDiagrama._sel_id).

Integración esperada en pantallas_diagrama.py (a aplicar en ese archivo):
  1. import: from pantallas_riesgo import (
         cargar_cache_riesgo_equipo, cargar_cache_riesgo_senal,
         color_y_borde_por_riesgo, conn_colors_por_riesgo_senal,
         simular_falla_equipo, PopupResultadoSimulacion)
  2. __init__: self._riesgo_color_activo = False; self._riesgo_cache = {}
     self._riesgo_senal_color_activo = False; self._riesgo_senal_cache = {}
     self._riesgo_senales_cache_dict = {}  (ya contemplado por
     _senal_conectores_caidos vía getattr, no requiere tocar ese método)
  3. Toolbar: dos ToggleButton ("🎨 Riesgo equipo" / "🎨 Riesgo señal") +
     un Button ("🔺 Simular falla"), junto a los de Señal.
  4. _draw_node: envolver el color/ancho de cabecera con
     color_y_borde_por_riesgo(nodo["id"], self._popup._riesgo_cache,
     rc, gc, bc, ancho_borde) si self._popup._riesgo_color_activo.
  5. _calc_conn_colors: fusionar con
     conn_colors_por_riesgo_senal(self._popup._riesgo_senal_cache) si
     self._popup._riesgo_senal_color_activo — con prioridad sobre el
     color de selección (mismo criterio que GTK, ver docstring de
     signal_risk_diagrama_ui.py).
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.metrics import dp

from widgets_base import _, FUENTE_CHICA, barra_superior_dialogo
from core.modelo import Modelo, DB_PATH

# ── Riesgo de impacto/falla de equipo (RiesgoDiagramaMixin, GTK) ───────────
# Mismos colores 0-1 que _NIVEL_COLOR (Cairo ya usaba esa escala, no hex).
_NIVEL_COLOR = {
    "Crítico": (0.85, 0.15, 0.15),
    "Alto":    (0.90, 0.55, 0.10),
    "Medio":   (0.90, 0.80, 0.10),
    "Bajo":    (0.15, 0.65, 0.20),
}

# ── Riesgo de calidad de señal (RiesgoSenalDiagramaMixin, GTK) ─────────────
_COLOR_ATENUACION  = (0.90, 0.55, 0.10)   # naranja
_COLOR_ANCHO_BANDA = (0.90, 0.75, 0.10)   # ámbar
_COLOR_FORMATO     = (0.85, 0.15, 0.15)   # rojo (ELECTRICO/BALANCE/CANAL)
_EJES_FORMATO = ("ELECTRICO", "BALANCE", "CANAL")


def cargar_cache_riesgo_equipo() -> dict:
    """Relee riesgo_equipo_cache — barato, una sola consulta, sin tocar
    el motor de grafo. Se degrada a {} si la tabla no existe todavía
    (BD vieja, sin `Equipos → 🔺 Recalcular riesgo` corrido nunca) —
    mismo criterio defensivo que cargar_cache_senal."""
    try:
        filas = Modelo._query(
            "SELECT id_equipo, riesgo, impacto, nivel FROM riesgo_equipo_cache")
    except Exception:
        return {}
    return {str(r[0]): (r[1], r[2], r[3]) for r in filas}


def cargar_cache_riesgo_senal(db_path=DB_PATH) -> dict:
    """{id_cable(str): [(eje, detalle), ...]} vía SignalRiskAnalyzer —
    idéntico a _riesgo_senal_cargar_cache (GTK)."""
    try:
        from core.signal_risk import SignalRiskAnalyzer
        analyzer = SignalRiskAnalyzer(db_path)
        return analyzer.resumen_por_cable()
    except Exception:
        return {}


def color_y_borde_por_riesgo(id_equipo, cache: dict, rc, gc, bc,
                             ancho_base) -> tuple:
    """Dado el color de cabecera (rc,gc,bc) y ancho de borde ya
    calculados por _draw_node, devuelve la versión ajustada por riesgo
    si hay dato para ese equipo — idéntico a _riesgo_color_y_borde
    (GTK). No-op (devuelve tal cual) si no hay caché para ese id, así
    que es seguro llamar siempre con el toggle apagado tratado aparte
    por el llamador."""
    info = cache.get(str(id_equipo))
    if not info:
        return rc, gc, bc, ancho_base
    _riesgo, impacto, nivel = info
    color = _NIVEL_COLOR.get(nivel, (rc, gc, bc))
    # Engrosar el borde según impacto (0-100 -> +0 a +3px): distingue
    # "punto único de falla" de "riesgoso" a simple vista.
    extra = min(3.0, (impacto or 0) / 33.0)
    return color[0], color[1], color[2], ancho_base + extra


def conn_colors_por_riesgo_senal(cache: dict) -> dict:
    """{id_cable: (r,g,b)} para cables con riesgo de señal activo —
    idéntico a _riesgo_senal_conn_colors (GTK)."""
    colores = {}
    for id_cable, activos in cache.items():
        ejes = {e for e, _d in activos}
        if ejes & set(_EJES_FORMATO):
            colores[id_cable] = _COLOR_FORMATO
        elif "ATENUACION" in ejes:
            colores[id_cable] = _COLOR_ATENUACION
        elif "ANCHO_BANDA" in ejes:
            colores[id_cable] = _COLOR_ANCHO_BANDA
    return colores


def tooltip_riesgo_senal(cache: dict, id_cable) -> str:
    """Detalle concatenado de los riesgos activos de un cable — mismo
    criterio que _riesgo_senal_tooltip (GTK): no fusiona ejes, los
    lista todos. Sin hover táctil, se usa como texto fijo (ver
    integración sugerida en pantallas_diagrama.py, mismo criterio que
    _senal_texto_puerto_extra)."""
    activos = cache.get(str(id_cable))
    if not activos:
        return ""
    return " | ".join(f"{eje}: {detalle}" for eje, detalle in activos)


# ═══════════════════════════════════════════════════════════════════════
# Simular falla del seleccionado
# ═══════════════════════════════════════════════════════════════════════

def simular_falla_equipo(db_path, id_equipo):
    """Corre GraphImpactAnalyzer.simular_falla_equipo — idéntico a
    _riesgo_on_simular_falla (GTK), pero devuelve los datos en vez de
    armar directamente el diálogo (separación función pura / UI, mismo
    criterio que el resto de mobile).

    Retorna (resultado, analyzer, nombres_afectados, senales_perdidas,
    senales_cache_dict) o (None, None, None, None, None) si el motor de
    impacto no está disponible o falla la simulación — el llamador
    decide cómo avisarlo (mostrar_error/mostrar_info)."""
    try:
        from core.graph_impact import GraphImpactAnalyzer
    except Exception:
        return None, None, None, None, None
    try:
        analyzer = GraphImpactAnalyzer(db_path)
        analyzer.construir_grafo()
        resultado = analyzer.simular_falla_equipo(id_equipo)
    except Exception:
        return None, None, None, None, None

    nombres_afectados = sorted(
        (analyzer.nombre_equipo(eq_id) for eq_id in resultado.equipos_impactados),
        key=lambda n: (n or "").lower())

    senales_perdidas = []
    senales_cache_dict = {}
    if resultado.hay_impacto:
        try:
            from core.senal_estado import senales_caidas_por_equipos
            senales_cache_dict = senales_caidas_por_equipos(
                db_path, resultado.equipos_impactados,
                equipos_adicionales={str(resultado.equipo_id)},
                conectores_adicionales=resultado.conectores_regla_caida)
            senales_perdidas = sorted({
                info["nombre_senal"] for info in senales_cache_dict.values()
                if info.get("nombre_senal")
            })
        except Exception:
            senales_cache_dict = {}
            senales_perdidas = []

    return resultado, analyzer, nombres_afectados, senales_perdidas, senales_cache_dict


def _label_wrap(texto, color=(0.91, 0.91, 0.91, 1), font_size=FUENTE_CHICA,
                bold=False):
    lbl = Label(text=texto, color=color, font_size=font_size, bold=bold,
                halign="left", valign="middle", size_hint_y=None,
                height=dp(22))
    lbl.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
    return lbl


class PopupResultadoSimulacion(Popup):
    """Muestra el resultado de "🔺 Simular falla del seleccionado" —
    equivalente al Gtk.Dialog modal de _riesgo_on_simular_falla (GTK),
    con ScrollView + Label en vez de Gtk.TreeView (mismo patrón que
    PopupDetalleSesion, pantallas_diagnostico.py)."""

    def __init__(self, nombre_equipo, resultado, nombres_afectados,
                senales_perdidas, **kwargs):
        raiz = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        raiz.add_widget(barra_superior_dialogo(
            _("Equipos afectados si falla: {}").format(nombre_equipo),
            on_atras=lambda: self.dismiss()))

        cuerpo = BoxLayout(orientation="vertical", spacing=dp(4),
                          padding=dp(4), size_hint_y=None)
        cuerpo.bind(minimum_height=cuerpo.setter("height"))

        if not resultado.hay_impacto:
            cuerpo.add_widget(_label_wrap(
                _("Ningún equipo depende exclusivamente de este: hay "
                  "redundancia o no alimenta a nadie más.")))
        else:
            cuerpo.add_widget(_label_wrap(
                _("{} equipo(s) quedan sin señal:").format(
                    len(nombres_afectados)),
                bold=True))

            for texto in (resultado.causas_regla or {}).values():
                cuerpo.add_widget(_label_wrap(
                    f"⚠ {texto}", color=(0.83, 0.63, 0.09, 1)))

            for nombre in nombres_afectados:
                cuerpo.add_widget(_label_wrap(f"• {nombre}"))

            if senales_perdidas:
                cuerpo.add_widget(_label_wrap(
                    _("{} señal(es) se pierden:").format(
                        len(senales_perdidas)),
                    bold=True))
                for nombre in senales_perdidas:
                    cuerpo.add_widget(_label_wrap(f"📡 {nombre}"))

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(cuerpo)
        raiz.add_widget(scroll)

        super().__init__(title="", separator_height=0, content=raiz,
                         size_hint=(1, 1), **kwargs)
