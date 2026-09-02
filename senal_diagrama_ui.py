"""
senal_diagrama_ui.py — Mixin de UI para DiagramaConexiones
==============================================================
Fase 5 de plan_entidad_senal.md ("Integración visual"). Agrega
"📡 Colorear por señal" al diagrama de conexiones: cada conector IN/OUT
que tiene una señal cargada (manual o propagada) se pinta con un color
estable asignado a esa señal, en vez del celeste/naranja fijo de
IN/OUT. Conectores sin señal cargada mantienen el color normal.

La leyenda ("qué señal corresponde a cada color") se dibuja como un
panel fijo directamente sobre el canvas (esquina superior izquierda),
con el mismo estilo visual que el panel "⚡ ANÁLISIS DE IMPACTO" de
impacto_ui.py (ImpactoMixin._imp_draw_panel / _imp_rrect) — antes era
un Gtk.Popover transitorio que se cerraba solo. Se ancla a la
izquierda a propósito para no superponerse con el panel de impacto o
de escenario (que usan la esquina superior derecha) ni con el
minimapa (esquina inferior derecha).

Sigue el mismo patrón que riesgo_diagrama_ui.RiesgoDiagramaMixin (mismo
autor de diseño, incluso el mismo comentario de integración) para que
ambos mixins convivan sin sorpresas en DiagramaConexiones.

Integración en pantallas_avanzadas.py (ya aplicada):
  1. class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin,
                               SenalDiagramaMixin, Gtk.Dialog):
     (ImpactoMixin va ANTES para que self._imp_rrect esté disponible,
     reutilizado acá para dibujar el panel con el mismo estilo)
  2. self._senal_init(DB_PATH)                — junto a _impacto_init/_riesgo_init
  3. for w in self._senal_crear_items_menu(): menu_senal.append(w)
     (los ítems se agregan al submenú "Señal" de la barra de menús)
  4. En _draw_node(), al dibujar cada puerto IN/OUT: usar
     self._senal_color_puerto(cid, color_defecto) en vez del color fijo.
  5. query-tooltip de la DrawingArea: self._senal_tooltip_puerto(cid)
     para el texto adicional de señal (si hay).
  6. En _on_draw(), después de pintar el mundo (cr.restore()) y junto a
     los demás overlays: self._senal_on_draw_overlay(cr, W, H).
  7. En _on_press(), junto a los demás handlers de overlay (ANTES de
     interpretar el clic como selección de nodo):
     if self._senal_on_press(da, event): return True
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modelo import Modelo

try:
    from i18n import _
except ImportError:
    def _(t): return t


# Misma paleta que EditorMasivoConectoresImagen.PALETA (pantallas_avanzadas.py)
# — reutilizada tal cual para que el mismo criterio de "colores
# distinguibles a simple vista" se vea igual en todas las pantallas de
# la app, en vez de inventar una paleta nueva.
_PALETA_SENAL = [
    "#E53935", "#8E24AA", "#1E88E5", "#00897B", "#F4511E",
    "#6D4C41", "#3949AB", "#039BE5", "#43A047", "#E91E63",
    "#FF6F00", "#00ACC1", "#7CB342", "#546E7A", "#AB47BC",
    "#26A69A", "#EF5350", "#5C6BC0", "#29B6F6", "#66BB6A",
]

# Paleta del panel — mismo esquema que impacto_ui.py (_C_PAN_BG/_C_PAN_BRD/
# _C_TITULO/_C_TEXTO/_C_BTN_SALIR) pero con acento celeste en vez de rojo,
# para diferenciar a simple vista "leyenda de señal" de "análisis de
# impacto" aunque ambos paneles compartan la misma forma.
_SC_PAN_BG  = (0.10, 0.11, 0.16, 0.92)
_SC_PAN_BRD = (0.12, 0.42, 0.62, 0.95)
_SC_TITULO  = (0.35, 0.75, 1.00, 1.00)
_SC_TEXTO   = (0.91, 0.91, 0.91, 1.00)
_SC_BTN     = (0.22, 0.48, 0.82, 1.00)


def _hex_a_rgb01(hexcolor: str) -> tuple:
    hexcolor = hexcolor.lstrip("#")
    return tuple(int(hexcolor[i:i+2], 16) / 255.0 for i in (0, 2, 4))


class SenalDiagramaMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple. Asume que la
    clase combinada también hereda de ImpactoMixin (se reutiliza
    ImpactoMixin._imp_rrect para dibujar el panel con el mismo estilo)."""

    # ── Init ─────────────────────────────────────────────────────────────
    def _senal_init(self, db_path: str) -> None:
        """Llamar al final de __init__, junto a self._impacto_init(...) y
        self._riesgo_init(...)."""
        self._senal_db_path = db_path
        self._senal_color_activo = False   # toggle "📡 Colorear por señal"
        self._senal_leyenda_activa = False  # toggle "🎨 Leyenda" (panel en canvas)
        self._senal_panel_btn_rect = None   # (x,y,w,h) botón "✕" del panel, en pantalla
        # id_conector(str) -> (id_senal, nombre_senal, nombre_formato, origen)
        self._senal_cache = {}
        # id_senal(str) -> (r,g,b) — asignación estable, ver _senal_cargar_cache
        self._senal_color_por_id = {}
        self._senal_cargar_cache()

    def _senal_cargar_cache(self) -> None:
        """Relee senal_en_conector desde la BD. Barato: una sola consulta
        con JOIN, sin tocar ningún motor de grafo. Si las tablas de señal
        todavía no existen (BD vieja sin pasar por Modelo.asegurar_tablas_
        senal al menos una vez), se degrada a "sin datos" sin romper el
        diagrama — mismo criterio defensivo que RiesgoDiagramaMixin."""
        try:
            filas = Modelo._query("""
                SELECT sec.id_conector, sec.id_senal, s.nombre,
                       f.nombre, sec.origen
                FROM senal_en_conector sec
                JOIN senal s ON s.id_senal = sec.id_senal
                LEFT JOIN tipo_formato_senal f ON f.id_formato = sec.id_formato
            """)
        except Exception:
            filas = []
        self._senal_cache = {
            str(r[0]): (str(r[1]), r[2], r[3], r[4]) for r in filas
        }
        # Asignación de color estable por señal: orden alfabético por
        # nombre (no por id) para que el color de una señal no salte
        # cada vez que se recalcula la propagación — sólo cambia si se
        # agregan/quitan señales al catálogo completo.
        ids_ordenados = sorted(
            {(v[0], v[1]) for v in self._senal_cache.values()},
            key=lambda t: (t[1] or "").lower(),
        )
        self._senal_color_por_id = {
            id_senal: _hex_a_rgb01(_PALETA_SENAL[i % len(_PALETA_SENAL)])
            for i, (id_senal, _nombre) in enumerate(ids_ordenados)
        }

    # ── Ítems de menú ───────────────────────────────────────────────────
    def _senal_crear_items_menu(self) -> list:
        """Devuelve [toggle_color, toggle_leyenda] como Gtk.MenuItem para
        agregar al submenú "Señal" de la barra de menús."""
        self._senal_btn_toggle = Gtk.CheckMenuItem(label=_("📡 Colorear por señal"))
        self._senal_btn_toggle.set_tooltip_text(
            "Pinta cada conector según la señal que tiene cargada (manual "
            "o propagada) — cada señal distinta tiene un color propio.\n"
            "Pasá el mouse sobre un conector para ver el nombre.\n"
            "Usá el buscador (Ctrl+F, filtro 📡 Señal) para saltar directo "
            "a dónde está una señal en particular."
        )
        self._senal_btn_toggle.connect("toggled", self._senal_on_toggle_color)

        self._senal_btn_leyenda = Gtk.CheckMenuItem(label=_("🎨 Leyenda"))
        self._senal_btn_leyenda.set_tooltip_text(
            "Muestra/oculta, sobre el diagrama, qué señal corresponde a "
            "cada color (igual que el panel de ⚡ Análisis de impacto)."
        )
        self._senal_btn_leyenda.connect("toggled", self._senal_on_toggle_leyenda)

        return [self._senal_btn_toggle, self._senal_btn_leyenda]

    # ── Handlers ─────────────────────────────────────────────────────────
    def _senal_on_toggle_color(self, btn) -> None:
        self._senal_color_activo = btn.get_active()
        if self._senal_color_activo:
            self._senal_cargar_cache()   # traer el último dato al activar
        self._da.queue_draw()

    def _senal_on_toggle_leyenda(self, btn) -> None:
        """Muestra/oculta el panel de leyenda sobre el canvas. Sirve tanto
        si "📡 Colorear por señal" está prendido como apagado (para saber
        de antemano qué colores va a usar antes de activarlo)."""
        self._senal_leyenda_activa = btn.get_active()
        if self._senal_leyenda_activa:
            self._senal_cargar_cache()   # no mostrar una leyenda vieja
        else:
            self._senal_panel_btn_rect = None
        self._da.queue_draw()

    # ── Clic en el panel (botón "✕") ─────────────────────────────────────
    def _senal_on_press(self, _da, event) -> bool:
        """
        Insertar en _on_press(), junto a los demás handlers de overlay:
            if self._senal_on_press(da, event): return True
        """
        if self._senal_panel_btn_rect and event.button == 1:
            bx, by, bw, bh = self._senal_panel_btn_rect
            if bx <= event.x <= bx + bw and by <= event.y <= by + bh:
                self._senal_leyenda_activa = False
                self._senal_panel_btn_rect = None
                self._senal_btn_leyenda.set_active(False)   # sincroniza el check del menú
                self._da.queue_draw()
                return True
        return False

    # ── Dibujo Cairo (panel de leyenda sobre el canvas) ──────────────────
    def _senal_on_draw_overlay(self, cr, W: int, H: int) -> None:
        """
        Insertar en _on_draw(), junto a los demás overlays (después de
        pintar el mundo, en coords de pantalla):
            self._senal_on_draw_overlay(cr, W, H)

        Dibuja la leyenda de señal (color → nombre) como panel fijo en la
        esquina superior izquierda, mismo estilo que el panel de
        "⚡ ANÁLISIS DE IMPACTO" (impacto_ui.ImpactoMixin._imp_draw_panel):
        fondo redondeado semitransparente, borde de color, título y lista.
        Se reconstruye la lista de señales en cada repintado leyendo
        self._senal_cache (no vuelve a consultar la BD) para no mostrar
        una leyenda vieja si se cargó/quitó señal desde que se activó.
        """
        if not self._senal_leyenda_activa:
            self._senal_panel_btn_rect = None
            return

        nombres_por_id = {}
        for id_senal, nombre_senal, _fmt, _origen in self._senal_cache.values():
            nombres_por_id[id_senal] = nombre_senal
        items = sorted(nombres_por_id.items(), key=lambda t: (t[1] or "").lower())
        hay_caidos = bool(self._senal_conectores_caidos())

        PW = 250
        PH = min(H - 20, 64 + max(1, len(items)) * 20 + (22 if hay_caidos else 0))
        px, py = 10, 10

        cr.set_source_rgba(*_SC_PAN_BG)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.fill()
        cr.set_source_rgba(*_SC_PAN_BRD); cr.set_line_width(1.5)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.stroke()

        y = py + 28
        cr.set_source_rgba(*_SC_TITULO)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(13)
        cr.move_to(px + 14, y); cr.show_text("📡 LEYENDA DE SEÑAL")
        cr.set_source_rgba(*_SC_PAN_BRD); cr.set_line_width(1)
        cr.move_to(px + 8, y + 6); cr.line_to(px + PW - 8, y + 6); cr.stroke()
        y += 22

        cr.select_font_face("Sans", 0, 0); cr.set_font_size(11)
        if not items:
            cr.set_source_rgba(*_SC_TEXTO)
            cr.move_to(px + 14, y)
            cr.show_text("Todavía no hay señal cargada.")
            y += 18
        else:
            # plan_estado_senal_y_linaje.md, Función 1 — bugfix 2026-08-24
            # (reporte visual del usuario): antes sólo había una entrada
            # GENÉRICA al final ("❌ caída") — la fila de la señal puntual
            # que realmente cayó, acá en la lista de colores, seguía
            # mostrándose intacta como si nada. Se calcula una sola vez
            # qué ids de señal tienen HOY algún conector caído (no
            # importa cuál conector puntual, alcanza con que la señal
            # esté afectada en algún lado para tacharla acá).
            ids_senal_caidas = {
                info["id_senal"] for info in self._senal_conectores_caidos().values()
            }
            for i, (id_senal, nombre_senal) in enumerate(items):
                if y > py + PH - 16:
                    cr.set_source_rgba(*_SC_TEXTO)
                    cr.move_to(px + 14, y)
                    cr.show_text(f"… y {len(items) - i} más")
                    y += 18
                    break
                caida = id_senal in ids_senal_caidas
                r, g, b = self._senal_color_por_id.get(id_senal, (0.6, 0.6, 0.6))
                alpha_swatch = 0.45 if caida else 1.0
                cr.set_source_rgba(r, g, b, alpha_swatch)
                cr.rectangle(px + 14, y - 10, 14, 12); cr.fill()
                cr.set_source_rgba(0, 0, 0, 0.6); cr.set_line_width(1)
                cr.rectangle(px + 14.5, y - 9.5, 13, 11); cr.stroke()
                cr.set_source_rgba(*_SC_TEXTO)
                cr.move_to(px + 34, y); cr.show_text(nombre_senal)
                if caida:
                    ext_nombre = cr.text_extents(nombre_senal)
                    self._senal_dibujar_tachado(
                        cr, px + 34, y - ext_nombre.height / 2 + 1,
                        px + 34 + ext_nombre.width, y - ext_nombre.height / 2 + 1)
                y += 20

        # plan_estado_senal_y_linaje.md, Función 1: entrada fija de leyenda
        # cuando hay una simulación activa (Impacto/Riesgo/Escenario) con al
        # menos un conector caído — mismo estilo que las entradas de arriba,
        # pero con el cuadrito tachado en vez de relleno sólido.
        if hay_caidos:
            cr.set_source_rgba(*_SC_PAN_BRD); cr.set_line_width(1)
            cr.move_to(px + 8, y - 4); cr.line_to(px + PW - 8, y - 4); cr.stroke()
            y += 6
            cr.set_source_rgba(0.35, 0.35, 0.38, 1.0)
            cr.rectangle(px + 14, y - 10, 14, 12); cr.fill()
            self._senal_dibujar_tachado(cr, px + 15, y - 9, px + 27, y + 1)
            cr.set_source_rgba(0.85, 0.20, 0.20, 0.85)
            cr.move_to(px + 34, y); cr.show_text("caída (análisis activo)")
            y += 20

        # Botón cerrar (✕), esquina superior derecha del panel
        bw = bh = 18
        bx, by = px + PW - bw - 8, py + 8
        self._senal_panel_btn_rect = (bx, by, bw, bh)
        cr.set_source_rgba(*_SC_BTN)
        self._imp_rrect(cr, bx, by, bw, bh, 4); cr.fill()
        cr.set_source_rgba(1, 1, 1, 1)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(12)
        cr.move_to(bx + 4.5, by + 14); cr.show_text("✕")

    # ── Integración con _draw_node ──────────────────────────────────────
    def _senal_color_puerto(self, id_conector, color_defecto) -> tuple:
        """Dado el color (r,g,b) que _draw_node iba a usar para ese
        puerto, devuelve la versión ajustada por señal si el toggle está
        activo y ese conector tiene señal cargada. Si no, devuelve el
        color tal cual (no-op — seguro de llamar siempre).

        plan_estado_senal_y_linaje.md, Función 1: si el conector quedó
        "caído" por una simulación activa (Impacto/Riesgo/Escenario), se
        ignora el color de señal y se devuelve el color neutro — el
        color distintivo de la señal no tiene sentido mostrarlo si esa
        señal, en este análisis, dejó de estar presente ahí."""
        if not self._senal_color_activo:
            return color_defecto
        if self._senal_puerto_caido(id_conector):
            return color_defecto
        info = self._senal_cache.get(str(id_conector))
        if not info:
            return color_defecto
        id_senal = info[0]
        return self._senal_color_por_id.get(id_senal, color_defecto)

    def _senal_tooltip_puerto(self, id_conector) -> str:
        """Texto adicional de tooltip para un puerto, o '' si no hay
        señal cargada. Pensado para concatenar al tooltip existente del
        conector (nombre), no para reemplazarlo."""
        info = self._senal_cache.get(str(id_conector))
        if not info:
            return ""
        _id_senal, nombre_senal, nombre_formato, origen = info
        origen_lbl = "manual" if origen == "MANUAL" else "propagada"
        prefijo = "❌ CAÍDA — " if self._senal_puerto_caido(id_conector) else ""
        if nombre_formato:
            return f"{prefijo}📡 {nombre_senal} ({nombre_formato}) — {origen_lbl}"
        return f"{prefijo}📡 {nombre_senal} — {origen_lbl}"

    # ── Función 1: estado vivo/caído (plan_estado_senal_y_linaje.md) ─────
    def _senal_conectores_caidos(self) -> dict:
        """Unión de conectores marcados 'caídos' por CUALQUIER simulación
        activa en este momento sobre el mismo DiagramaConexiones — Impacto
        (impacto_ui.ImpactoMixin._imp_senales_cache_dict), Riesgo
        (riesgo_diagrama_ui.RiesgoDiagramaMixin._riesgo_senales_cache_dict)
        o Escenario (escenario_ui.EscenarioMixin._esc_senales_cache_dict).

        Contrato deliberadamente flojo (getattr con default {}): este
        mixin no necesita saber los detalles de cada uno, sólo que exponen
        un dict {id_conector: {...}} con esa forma — así se puede seguir
        agregando un cuarto motor en el futuro sin tocar este método."""
        caidos = {}
        for attr in ("_imp_senales_cache_dict",
                     "_riesgo_senales_cache_dict",
                     "_esc_senales_cache_dict"):
            caidos.update(getattr(self, attr, None) or {})
        return caidos

    def _senal_puerto_caido(self, id_conector) -> bool:
        return str(id_conector) in self._senal_conectores_caidos()

    def _senal_dibujar_tachado(self, cr, x0, y0, x1, y1) -> None:
        """Línea horizontal sobre un label para simular strikethrough —
        Cairo no tiene texto tachado nativo (a diferencia de Pango
        markup), así que se traza a mano. Mismo criterio ya usado en el
        proyecto para overlays custom sobre texto/formas (ver
        DiagramaConexiones._draw_conn, "jumps" de cables)."""
        cr.set_source_rgba(0.85, 0.20, 0.20, 0.85)
        cr.set_line_width(1.3)
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()
