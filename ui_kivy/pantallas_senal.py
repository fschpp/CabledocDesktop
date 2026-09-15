"""
pantallas_senal.py — "Colorear por señal" en Kivy (Fase 5.4 del roadmap)
=========================================================================
Ver ROADMAP_FASE5_paridad_pantallas.md, ítem 4. Equivalente a
ui_gtk/senal_diagrama_ui.py (SenalDiagramaMixin) — NO a
ui_gtk/signal_risk_diagrama_ui.py, que es un mixin distinto (Riesgo,
ítem 5 del roadmap, colorea CABLES vía _calc_conn_colors/
_riesgo_senal_conn_colors, todavía sin portar). El roadmap mencionaba
"_calc_conn_colors() en la línea 717" como punto de integración de este
ítem, pero esa función en GTK sólo la usa signal_risk_diagrama_ui.py —
senal_diagrama_ui.py (este archivo) únicamente toca _draw_node(). Esta
entrega se limita a lo que el archivo fuente realmente hace: colorear
PUERTOS por señal + panel de leyenda. Ver el aparte al final de esta
entrega en changelog.txt para el detalle de la confusión de nombres.

Reutiliza SIN NINGÚN CAMBIO la misma tabla que ya usa GTK
(senal_en_conector, vía Modelo._query — no hay un core/ dedicado a esta
consulta puntual tampoco en GTK, así que no hace falta inventar uno acá)
y core/senal_estado.senales_caidas_por_equipos, ya integrado en mobile
desde Fase 5.3 (ver DiagramaConexiones._esc_senales_cache_dict en
pantallas_diagrama.py).

Adaptaciones táctiles respecto a GTK (ver docstring de cada función):
  - El panel de leyenda es un widget real (PanelLeyendaSenal, mismo
    mecanismo de tarjeta flotante que PanelEscenario/PanelDiagnostico),
    no texto Cairo dibujado a mano — mismo criterio que el resto de
    mobile. Ancla arriba-IZQUIERDA (GTK: misma esquina), el único rincón
    todavía libre — Escenario ya usa arriba-derecha, Diagnóstico
    abajo-centro.
  - El botón "✕" del panel es un Button real en vez del rectángulo
    dibujado a mano + hit-test manual de GTK (_senal_panel_btn_rect) —
    Kivy ya resuelve esto solo.
  - El tachado de una señal caída en la leyenda usa markup de Kivy
    ([s]...[/s], Label(markup=True)) en vez de trazar una línea a mano
    sobre el texto (_senal_dibujar_tachado de GTK) — Cairo no tiene
    texto tachado nativo, Kivy sí vía BBCode.
  - El tooltip al pasar el mouse sobre un puerto (_senal_tooltip_puerto,
    GTK) no tiene equivalente táctil — un dispositivo táctil no tiene
    "hover". En vez de perder la información, se agrega el nombre de la
    señal al lado del nombre del puerto en el propio diagrama (ver
    _CanvasDiagrama._draw_node en pantallas_diagrama.py), visible todo
    el tiempo en vez de sólo al pasar el mouse — un dato más, no menos,
    que la versión GTK.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Line, RoundedRectangle, Rectangle
from kivy.metrics import dp

from widgets_base import _, FUENTE_CHICA
from core.modelo import Modelo


# Misma paleta que EditorMasivoConectoresImagen.PALETA (GTK,
# pantallas_avanzadas.py) y que ui_gtk/senal_diagrama_ui.py._PALETA_SENAL
# — reutilizada tal cual para que el color de una señal se vea IGUAL en
# desktop y mobile, no una paleta inventada aparte.
_PALETA_SENAL = [
    "#E53935", "#8E24AA", "#1E88E5", "#00897B", "#F4511E",
    "#6D4C41", "#3949AB", "#039BE5", "#43A047", "#E91E63",
    "#FF6F00", "#00ACC1", "#7CB342", "#546E7A", "#AB47BC",
    "#26A69A", "#EF5350", "#5C6BC0", "#29B6F6", "#66BB6A",
]

# Paleta del panel — mismo esquema que PanelEscenario pero con acento
# celeste en vez de amarillo/naranja, para diferenciar a simple vista
# "leyenda de señal" de "escenario" aunque ambos paneles compartan la
# misma forma de tarjeta.
_SC_PAN_BG  = (0.10, 0.11, 0.16, 0.92)
_SC_PAN_BRD = (0.12, 0.42, 0.62, 0.95)
_SC_TITULO  = (0.35, 0.75, 1.00, 1.00)


def _hex_a_rgb01(hexcolor: str) -> tuple:
    hexcolor = hexcolor.lstrip("#")
    return tuple(int(hexcolor[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def cargar_cache_senal():
    """Equivalente a SenalDiagramaMixin._senal_cargar_cache (GTK): lee
    senal_en_conector completa (barato, una sola consulta con JOIN, sin
    tocar ningún motor de grafo) y asigna un color estable a cada
    id_senal distinta — orden alfabético por NOMBRE (no por id), para
    que el color de una señal no salte cada vez que se recalcula la
    propagación, sólo si se agregan/quitan señales al catálogo completo.

    Devuelve (cache, color_por_id):
      cache: {id_conector(str): (id_senal, nombre_senal, nombre_formato,
              origen)}
      color_por_id: {id_senal(str): (r,g,b)}

    Se degrada a "sin datos" sin romper el diagrama si la tabla todavía
    no existe (BD vieja) — mismo criterio defensivo que el resto de
    mobile (ver Escenario/Diagnóstico)."""
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
    cache = {str(r[0]): (str(r[1]), r[2], r[3], r[4]) for r in filas}
    ids_ordenados = sorted(
        {(v[0], v[1]) for v in cache.values()},
        key=lambda t: (t[1] or "").lower(),
    )
    color_por_id = {
        id_senal: _hex_a_rgb01(_PALETA_SENAL[i % len(_PALETA_SENAL)])
        for i, (id_senal, _nombre) in enumerate(ids_ordenados)
    }
    return cache, color_por_id


def _label_wrap(texto, color=(0.91, 0.91, 0.91, 1), font_size=FUENTE_CHICA,
                markup=False):
    lbl = Label(text=texto, color=color, font_size=font_size, markup=markup,
                halign="left", valign="middle", size_hint_y=None,
                height=dp(20))
    lbl.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
    return lbl


def _swatch_widget(color, alpha=1.0):
    """Cuadradito de color — equivalente al rectángulo relleno que
    dibuja GTK a mano para cada entrada de la leyenda."""
    w = Widget(size_hint=(None, None), size=(dp(16), dp(14)))
    with w.canvas:
        Color(*color, alpha)
        rect = Rectangle(pos=w.pos, size=w.size)
        Color(0, 0, 0, 0.6)
        borde = Line(rectangle=(*w.pos, *w.size), width=1)

    def _upd(*_a):
        rect.pos = w.pos
        rect.size = w.size
        borde.rectangle = (*w.pos, *w.size)
    w.bind(pos=_upd, size=_upd)
    return w


def _swatch_tachado_widget():
    """Cuadradito gris con una línea diagonal — equivalente a la entrada
    fija "caída (análisis activo)" de GTK (_senal_dibujar_tachado
    aplicado al swatch, no al texto, en ese caso puntual)."""
    w = Widget(size_hint=(None, None), size=(dp(16), dp(14)))
    with w.canvas:
        Color(0.35, 0.35, 0.38, 1.0)
        rect = Rectangle(pos=w.pos, size=w.size)
        Color(0.85, 0.20, 0.20, 0.85)
        diag = Line(points=[w.x, w.y, w.right, w.top], width=1.3)

    def _upd(*_a):
        rect.pos = w.pos
        rect.size = w.size
        diag.points = [w.x, w.y, w.right, w.top]
    w.bind(pos=_upd, size=_upd)
    return w


# ─────────────────────────────────────────────────────────────────────────
# Panel flotante de leyenda — equivalente a SenalDiagramaMixin.
# _senal_on_draw_overlay (GTK), con widgets reales (ver docstring del
# módulo). Mismo mecanismo de tarjeta que PanelEscenario/
# PanelDiagnostico, anclada arriba-izquierda.
# ─────────────────────────────────────────────────────────────────────────
class PanelLeyendaSenal(BoxLayout):

    ANCHO = dp(240)
    ALTO_FRAC_MAX = 0.55
    ALTO_MIN = dp(56)
    MARGEN = dp(10)
    _ALTO_CABECERA = dp(26)

    def __init__(self, contenedor, on_cerrar=None, **kwargs):
        self._contenedor = contenedor
        self._on_cerrar = on_cerrar
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("width", self.ANCHO)
        kwargs.setdefault("spacing", dp(4))
        kwargs.setdefault("padding", dp(10))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*_SC_PAN_BG)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(10)])
            Color(*_SC_PAN_BRD)
            self._borde = Line(
                rounded_rectangle=(*self.pos, *self.size, dp(10)), width=1.3)
        self.bind(pos=self._actualizar_fondo, size=self._actualizar_fondo)

        hdr = BoxLayout(size_hint_y=None, height=self._ALTO_CABECERA,
                        spacing=dp(4))
        lbl_titulo = Label(text=_("📡 Leyenda de señal"), bold=True,
                           font_size=FUENTE_CHICA, color=_SC_TITULO,
                           halign="left", valign="middle", shorten=True,
                           shorten_from="right")
        lbl_titulo.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        hdr.add_widget(lbl_titulo)
        btn_cerrar = Button(text="✕", size_hint=(None, None),
                            size=(dp(22), dp(22)), font_size=FUENTE_CHICA)
        btn_cerrar.bind(on_release=lambda *_a: self._cerrar())
        hdr.add_widget(btn_cerrar)
        self.add_widget(hdr)

        scroll = ScrollView(do_scroll_x=False)
        self._area = BoxLayout(orientation="vertical", spacing=dp(3),
                               padding=(0, dp(2)), size_hint_y=None)
        self._area.bind(minimum_height=lambda *_a: self._actualizar_alto())
        scroll.add_widget(self._area)
        self.add_widget(scroll)

        if self._contenedor is not None:
            self._contenedor.add_widget(self)
            self._contenedor.bind(size=lambda *_a: self._reposicionar())
        self._actualizar_alto()

    def _cerrar(self, *_a):
        if self._on_cerrar:
            self._on_cerrar()

    # ── Geometría (idéntico patrón que PanelEscenario, ancla arriba-
    # izquierda en vez de arriba-derecha) ──
    def _actualizar_fondo(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._borde.rounded_rectangle = (*self.pos, *self.size, dp(10))

    def _actualizar_alto(self, *_a):
        disp_h = (self._contenedor.height if self._contenedor else 0) or dp(500)
        alto_max = disp_h * self.ALTO_FRAC_MAX
        deseado = (self._ALTO_CABECERA + self.spacing
                  + self._area.minimum_height + dp(20))
        self.height = max(self.ALTO_MIN, min(deseado, alto_max))
        self._reposicionar()

    def _reposicionar(self, *_a):
        if self._contenedor is None:
            return
        self.width = min(self.ANCHO,
                         max(dp(160), self._contenedor.width - self.MARGEN * 2))
        self.x = self._contenedor.x + self.MARGEN
        self.y = self._contenedor.y + self._contenedor.height - self.height - self.MARGEN

    def quitar(self) -> None:
        if self.parent is not None:
            self.parent.remove_widget(self)

    # ── Blindaje de toques — mismo criterio que PanelEscenario/
    # PanelDiagnostico ──
    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        return self.collide_point(*touch.pos)

    def on_touch_move(self, touch):
        if super().on_touch_move(touch):
            return True
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if super().on_touch_up(touch):
            return True
        return self.collide_point(*touch.pos)

    # ── Contenido ────────────────────────────────────────────────────────
    def actualizar(self, cache: dict, color_por_id: dict, caidos: dict) -> None:
        """Equivalente a _senal_on_draw_overlay (GTK). `caidos` es el
        dict {id_conector: {"id_senal":..., ...}} devuelto por
        DiagramaConexiones._senal_conectores_caidos()."""
        self._area.clear_widgets()

        nombres_por_id = {}
        for id_senal, nombre_senal, _fmt, _origen in cache.values():
            nombres_por_id[id_senal] = nombre_senal
        items = sorted(nombres_por_id.items(), key=lambda t: (t[1] or "").lower())

        if not items:
            self._area.add_widget(_label_wrap(
                _("Todavía no hay señal cargada.")))
        else:
            ids_senal_caidas = {
                info["id_senal"] for info in caidos.values()
                if info.get("id_senal")
            }
            for id_senal, nombre_senal in items:
                caida = id_senal in ids_senal_caidas
                color = color_por_id.get(id_senal, (0.6, 0.6, 0.6))
                fila = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))
                fila.add_widget(_swatch_widget(color, alpha=0.45 if caida else 1.0))
                texto = f"[s]{nombre_senal}[/s]" if caida else nombre_senal
                fila.add_widget(_label_wrap(texto, markup=True))
                self._area.add_widget(fila)

        if caidos:
            fila = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))
            fila.add_widget(_swatch_tachado_widget())
            fila.add_widget(_label_wrap(
                _("caída (análisis activo)"), color=(0.85, 0.20, 0.20, 0.85)))
            self._area.add_widget(fila)

        self._actualizar_alto()
