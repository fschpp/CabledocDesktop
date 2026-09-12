"""
CableDoc Kivy - Pantallas avanzadas (fase 3, parte 1).

Equivalente a las primeras 3 clases de pantallas_avanzadas.py (GTK +
Cairo), las que ya tienen botones esperando desde Equipos/Conectores:

    1. CoordenadasImagenSeleccion   clic en imagen → X, Y [, ancho, alto]
    2. ImagenConectoresYCables      foto del equipo con marcadores de
                                    colores sobre cada conector + tabla
    3. ArbolConexionesEquipo        árbol jerárquico lazy-load de
                                    conexiones (equipo → cable → equipo…)

Lo que queda para la fase 4 (depende de Racks/Frames/Slots, que tampoco
están migrados todavía, y son los módulos más grandes del proyecto
original): VistaRack, PatcherasVista, VistaFrameSlots, DiagramaConexiones
(usa impacto_ui.py, marcado como prioridad baja), EditorConexiones,
EditorMasivoConectoresImagen, EditorMasivoSlotsFrame.

Nota sobre Drag&Drop: el árbol original (ArbolConexionesEquipo) tenía
soporte de arrastrar-y-soltar equipos entre nodos para "crear una
conexión", pero esa función ya estaba incompleta en el GTK original (solo
mostraba un mensaje de estado, no llegaba a crear la conexión en la base).
No se migra por ser una función no funcional en el original; usá el menú
Cableado → Conexiones para dar de alta conexiones.
"""

import math
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.metrics import dp, sp

from widgets_base import (
    VisorImagenZoom, dibujar_marcador_cuadrado, mostrar_info, mostrar_error,
    grid_formulario, fila_etiqueta, fila_entry, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, fila_cerrar_arriba,
    barra_superior_dialogo,
)
from modelo import Modelo, IMG_DIR

PALETA = [
    (0.85, 0.15, 0.15), (0.15, 0.72, 0.15), (0.18, 0.42, 0.90),
    (0.92, 0.55, 0.04), (0.65, 0.15, 0.82), (0.04, 0.78, 0.78),
    (0.78, 0.75, 0.04), (0.90, 0.30, 0.65), (0.30, 0.72, 0.38),
    (0.55, 0.30, 0.08), (0.10, 0.52, 0.30), (0.82, 0.10, 0.50),
    (0.28, 0.60, 0.90), (0.75, 0.55, 0.22), (0.50, 0.10, 0.10),
    (0.18, 0.28, 0.72), (0.10, 0.65, 0.55), (0.70, 0.38, 0.82),
    (0.30, 0.50, 0.18), (0.90, 0.18, 0.38),
]


def _ruta_imagen(path_archivo):
    if not path_archivo:
        return None
    ruta = os.path.join(IMG_DIR, s(path_archivo).strip())
    return ruta if os.path.exists(ruta) else None


def _ruta_desde_id_imagen(id_imagen):
    if not id_imagen:
        return None
    path = Modelo.path_imagen(id_imagen)
    return _ruta_imagen(path)


# ═══════════════════════════════════════════════════════════════════════════
# 1. CoordenadasImagenSeleccion
# ═══════════════════════════════════════════════════════════════════════════

class CoordenadasImagenSeleccion(Popup):
    """
    Muestra una imagen y permite elegir coordenadas tocando/clickeando:
      solo_xy=True  → punto (x, y)
      solo_xy=False → rectángulo (x, y, ancho, alto), arrastrando

    Uso:
        CoordenadasImagenSeleccion(
            id_imagen=5, solo_xy=True, x="100", y="200",
            on_aceptar=lambda r: print(r["x"], r["y"])
        ).open()
    """

    MARCADOR = 50

    def __init__(self, id_imagen=None, solo_xy=True, x="", y="",
                ancho="", alto="", on_aceptar=None, **kwargs):
        self.solo_xy = solo_xy
        self._on_aceptar = on_aceptar
        self._puntos = []
        self._rect_ini = None
        self._rect_fin = None
        self._arrastrando = False

        # En desktop era: imagen 70% + panel de campos 30% lado a lado.
        # En 360dp el panel quedaría en ~110dp, invivible para 4 campos +
        # botón + leyenda. Se apila: imagen arriba (grande, es lo que se
        # toca), panel compacto de campos abajo.
        outer = BoxLayout(orientation="vertical")

        self.visor = VisorImagenZoom(size_hint=(1, 0.7))
        self.visor.set_overlay_fn(self._dibujar_overlay)
        self.visor.canvas_widget.on_press_img = self._on_press
        self.visor.canvas_widget.on_motion_img = self._on_motion
        self.visor.canvas_widget.on_release_img = self._on_release
        outer.add_widget(self.visor)

        panel = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint=(1, 0.3), padding=dp(8))

        hb_xy = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        hb_xy.add_widget(Label(text=_("X:"), size_hint_x=None, width=dp(24),
                              font_size=FUENTE_CHICA))
        self.e_x = TextInput(text=s(x), multiline=False, font_size=FUENTE_NORMAL)
        hb_xy.add_widget(self.e_x)
        hb_xy.add_widget(Label(text=_("Y:"), size_hint_x=None, width=dp(24),
                              font_size=FUENTE_CHICA))
        self.e_y = TextInput(text=s(y), multiline=False, font_size=FUENTE_NORMAL)
        hb_xy.add_widget(self.e_y)
        panel.add_widget(hb_xy)

        if not solo_xy:
            hb_wh = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
            hb_wh.add_widget(Label(text=_("Ancho:"), size_hint_x=None,
                                  width=dp(50), font_size=FUENTE_CHICA))
            self.e_ancho = TextInput(text=s(ancho), multiline=False,
                                     font_size=FUENTE_NORMAL)
            hb_wh.add_widget(self.e_ancho)
            hb_wh.add_widget(Label(text=_("Alto:"), size_hint_x=None,
                                  width=dp(40), font_size=FUENTE_CHICA))
            self.e_alto = TextInput(text=s(alto), multiline=False,
                                    font_size=FUENTE_NORMAL)
            hb_wh.add_widget(self.e_alto)
            panel.add_widget(hb_wh)

        hb_ir = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_ir = Button(text=_("Ir a coordenadas"),
                       font_size=FUENTE_CHICA)
        btn_ir.bind(on_release=self._ir)
        hb_ir.add_widget(btn_ir)
        panel.add_widget(hb_ir)

        texto_leyenda = (_("Tocá para colocar el punto") if solo_xy
                         else _("Tocá y arrastrá para el área"))
        panel.add_widget(Label(
            text=texto_leyenda + " - " + _("pellizcá para zoom"),
            font_size=sp(10), size_hint_y=None, height=dp(18),
            color=(0.6, 0.6, 0.6, 1)))
        outer.add_widget(panel)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8),
                          padding=(dp(8), dp(4)))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._aceptar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        outer.add_widget(hb_btn)

        super().__init__(title=_("Seleccionar coordenadas en imagen"),
                         content=outer, size_hint=(1, 1), **kwargs)

        # precargar coords
        if solo_xy:
            try:
                self._puntos = [(int(float(x)), int(float(y)))]
            except (ValueError, TypeError):
                pass
        else:
            try:
                x1, y1 = int(float(x)), int(float(y))
                self._rect_ini = (x1, y1)
                self._rect_fin = (x1 + int(float(ancho)), y1 + int(float(alto)))
            except (ValueError, TypeError):
                pass

        ruta = _ruta_desde_id_imagen(id_imagen)
        self.visor.set_imagen(ruta)
        Clock.schedule_once(lambda *_a: self.visor._zoom_fit(), 0.3)

    # ── overlay ──
    def _dibujar_overlay(self, cw):
        z = self.visor.zoom
        M = self.MARCADOR * z
        if self.solo_xy:
            for ix, iy in self._puntos:
                wx, wy = self.visor.i2w(ix, iy)
                dibujar_marcador_cuadrado(cw, wx, wy, M, (0, 0.85, 0), 0.18)
        else:
            if self._rect_ini and self._rect_fin:
                x1, y1 = self._rect_ini
                x2, y2 = self._rect_fin
                wx1, wy1 = self.visor.i2w(min(x1, x2), max(y1, y2))
                w = abs(x2 - x1) * z
                h = abs(y2 - y1) * z
                from kivy.graphics import Color, Rectangle, Line
                with cw.canvas:
                    Color(0, 0.8, 0, 0.12)
                    Rectangle(pos=(wx1, wy1), size=(w, h))
                    Color(0, 0.85, 0, 0.92)
                    Line(rectangle=(wx1, wy1, w, h), width=max(2, 4 * z))

    # ── touch (coords ya en sistema local del canvas: bottom-up) ──
    def _on_press(self, lx, ly):
        ix, iy = self.visor.w2i(lx, ly)
        ix, iy = int(ix), int(iy)
        if self.solo_xy:
            self._puntos = [(ix, iy)]
            self.e_x.text = str(ix); self.e_y.text = str(iy)
        else:
            self._arrastrando = True
            self._rect_ini = self._rect_fin = (ix, iy)
        self.visor.queue_draw()

    def _on_motion(self, lx, ly):
        if self._arrastrando and not self.solo_xy:
            ix, iy = self.visor.w2i(lx, ly)
            self._rect_fin = (int(ix), int(iy))
            self.visor.queue_draw()

    def _on_release(self, lx, ly):
        if self._arrastrando and not self.solo_xy:
            self._arrastrando = False
            ix, iy = self.visor.w2i(lx, ly)
            ix, iy = int(ix), int(iy)
            x1 = min(self._rect_ini[0], ix); y1 = min(self._rect_ini[1], iy)
            x2 = max(self._rect_ini[0], ix); y2 = max(self._rect_ini[1], iy)
            self._rect_ini = (x1, y1); self._rect_fin = (x2, y2)
            self.e_x.text = str(x1); self.e_y.text = str(y1)
            self.e_ancho.text = str(x2 - x1); self.e_alto.text = str(y2 - y1)
            self.visor.queue_draw()

    def _ir(self, *_a):
        try:
            ix = int(self.e_x.text); iy = int(self.e_y.text)
            if self.solo_xy:
                self._puntos = [(ix, iy)]
            else:
                try:
                    aw = int(self.e_ancho.text); ah = int(self.e_alto.text)
                except ValueError:
                    aw, ah = 50, 50
                self._rect_ini = (ix, iy); self._rect_fin = (ix + aw, iy + ah)
            self.visor.queue_draw()
            self.visor.scroll_to_img(ix, iy)
        except ValueError:
            pass

    def _aceptar(self, *_a):
        resultado = {"x": self.e_x.text.strip(), "y": self.e_y.text.strip(),
                    "ancho": "", "alto": ""}
        if not self.solo_xy:
            resultado["ancho"] = self.e_ancho.text.strip()
            resultado["alto"] = self.e_alto.text.strip()
        self.dismiss()
        if self._on_aceptar:
            self._on_aceptar(resultado)


def abrir_coords_imagen(id_imagen=None, solo_xy=True, x="", y="",
                        ancho="", alto="", on_aceptar=None):
    """Atajo equivalente a abrir_coords_imagen() de GTK, pero asíncrono:
    el resultado llega por on_aceptar(dict) en vez de como retorno."""
    CoordenadasImagenSeleccion(
        id_imagen=id_imagen, solo_xy=solo_xy, x=x, y=y, ancho=ancho,
        alto=alto, on_aceptar=on_aceptar).open()


# ═══════════════════════════════════════════════════════════════════════════
# 2. ImagenConectoresYCables
# ═══════════════════════════════════════════════════════════════════════════

class _FilaTablaSimple(ButtonBehavior, BoxLayout):
    """Fila de tabla de solo lectura con tap simple (resalta) + mantener
    presionado (abre destino), usada en ImagenConectoresYCables y
    VistaFrameSlots (no necesita los botones CRUD de ListadoPopup).

    Antes usaba doble-tap para abrir el equipo destino; en pantalla
    táctil eso es poco confiable (fácil de disparar sin querer al tocar
    dos veces por error, o de no registrarse si el segundo toque tarda
    un poco más). Mantener presionado es el gesto estándar en apps
    móviles para una acción secundaria sobre una fila, igual que en
    ListadoPopup (widgets_base.py).

    col_width: si se especifica, cada columna tiene ese ancho fijo en dp
    y la fila entera pasa a size_hint_x=None (para usar dentro de un
    ScrollView horizontal, igual que las tablas de ListadoPopup). Si es
    None, se mantiene el comportamiento flexible original (columnas que
    se reparten el ancho disponible)."""

    MANTENER_PRESIONADO_SEG = 0.45
    MANTENER_PRESIONADO_TOLERANCIA = dp(10)

    def __init__(self, valores, color_fondo, on_click=None,
                on_mantener=None, col_width=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(36), **kwargs)
        self.valores = valores
        self._on_click = on_click
        self._on_mantener = on_mantener
        self._ev_mantener = None
        self._mantener_disparado = False
        self._touch_inicio = None
        if col_width:
            self.size_hint_x = None
            self.width = col_width * len(valores)
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            self._color_instr = Color(*color_fondo)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizar, size=self._actualizar)
        for v in valores:
            kw_lbl = dict(text=s(v), shorten=True, shorten_from="right",
                         halign="left", valign="middle", font_size=FUENTE_CHICA,
                         padding=(dp(4), 0))
            if col_width:
                kw_lbl["size_hint_x"] = None
                kw_lbl["width"] = col_width
                kw_lbl["text_size"] = (col_width - dp(8), dp(36))
            lbl = Label(**kw_lbl)
            lbl.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width - dp(8), w.height)))
            self.add_widget(lbl)

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_color(self, color):
        self._color_instr.rgba = color

    # ── Gesto "mantener presionado" (ver _FilaRV en widgets_base.py) ──
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._mantener_disparado = False
            self._touch_inicio = (touch.x, touch.y)
            self._ev_mantener = Clock.schedule_once(
                self._disparar_mantener, self.MANTENER_PRESIONADO_SEG)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._ev_mantener is not None and self._touch_inicio is not None:
            dx = abs(touch.x - self._touch_inicio[0])
            dy = abs(touch.y - self._touch_inicio[1])
            if dx > self.MANTENER_PRESIONADO_TOLERANCIA or dy > self.MANTENER_PRESIONADO_TOLERANCIA:
                Clock.unschedule(self._ev_mantener)
                self._ev_mantener = None
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._ev_mantener is not None:
            Clock.unschedule(self._ev_mantener)
            self._ev_mantener = None
        return super().on_touch_up(touch)

    def _disparar_mantener(self, *_a):
        self._ev_mantener = None
        self._mantener_disparado = True
        if self._on_click:
            self._on_click(self)
        if self._on_mantener:
            self._on_mantener(self)

    def on_release(self):
        if self._mantener_disparado:
            self._mantener_disparado = False
            return
        if self._on_click:
            self._on_click(self)


class ImagenConectoresYCables(Popup):
    """
    Vista fotográfica del equipo con marcadores numerados/coloreados sobre
    cada conector y tabla de referencia al costado. Click en imagen ↔
    resalta fila. Mantener presionado en fila → equipo destino.
    """

    MARCADOR = 50

    def __init__(self, id_equipo, **kwargs):
        self.id_equipo = str(id_equipo)
        self._marcadores = []
        self._resaltado = -1
        self._filas_widgets = []
        self._col_w = dp(120)  # ancho fijo por columna de la tabla

        # En desktop era imagen 62% + tabla 38% lado a lado. Con 6
        # columnas de tabla, 38% de 360dp (~137dp) es inviable: se apila
        # (imagen arriba, tabla con scroll horizontal+vertical abajo,
        # mismo patrón que ListadoPopup).
        outer = BoxLayout(orientation="vertical")
        self._barra_top = barra_superior_dialogo(
            _("Imagen de conectores y cables"), on_atras=lambda: self.dismiss())
        outer.add_widget(self._barra_top)

        self.visor = VisorImagenZoom(size_hint=(1, 0.55))
        self.visor.set_overlay_fn(self._dibujar_overlay)
        self.visor.canvas_widget.on_press_img = self._on_clic_imagen
        outer.add_widget(self.visor)

        panel = BoxLayout(orientation="vertical", spacing=dp(4),
                          size_hint=(1, 0.45), padding=dp(4))
        self.lbl_equipo = Label(text=_("Cargando…"), italic=True,
                                size_hint_y=None, height=dp(26),
                                font_size=FUENTE_CHICA, halign="left")
        panel.add_widget(self.lbl_equipo)

        cols_header = ["#", _("Conector local"), _("Cable"),
                       _("Equipo destino"), _("Tipo"), _("Conector dest.")]
        tabla_scroll = ScrollView(do_scroll_x=True, do_scroll_y=True,
                                  bar_width=dp(4))
        tabla_root = BoxLayout(orientation="vertical", size_hint=(None, None),
                               spacing=dp(1))
        tabla_root.width = self._col_w * len(cols_header)
        tabla_root.bind(minimum_height=tabla_root.setter("height"))

        header = BoxLayout(size_hint=(None, None), height=dp(30),
                          width=self._col_w * len(cols_header))
        for titulo in cols_header:
            header.add_widget(Label(text=titulo, bold=True,
                                    font_size=FUENTE_CHICA,
                                    size_hint=(None, None),
                                    width=self._col_w, height=dp(30)))
        tabla_root.add_widget(header)

        self.box_filas = BoxLayout(orientation="vertical",
                                   size_hint=(None, None), spacing=dp(1),
                                   width=self._col_w * len(cols_header))
        self.box_filas.bind(minimum_height=self.box_filas.setter("height"))
        tabla_root.add_widget(self.box_filas)
        tabla_scroll.add_widget(tabla_root)
        panel.add_widget(tabla_scroll)

        panel.add_widget(Label(
            text=_("Deslizá la tabla") + "  |  " +
                _("Mantené presionado fila → equipo destino"),
            font_size=sp(10), color=(0.6, 0.6, 0.6, 1), size_hint_y=None,
            height=dp(18)))
        outer.add_widget(panel)

        super().__init__(title="", separator_height=0, content=outer,
                         size_hint=(1, 1), **kwargs)
        self._cargar()

    def _cargar(self):
        eq_rows = Modelo._query(
            "SELECT ve.nombre FROM VISTA_EQUIPOS ve WHERE ve.id=?",
            (self.id_equipo,))
        nombre_local = s(eq_rows[0][0]) if eq_rows else f"Equipo {self.id_equipo}"
        self.lbl_equipo.text = f"[b]{nombre_local}[/b]"
        self.lbl_equipo.markup = True
        self.lbl_equipo.italic = False
        self._barra_top.lbl_titulo.text = (
            f"{_('Imagen de conectores')}: {nombre_local}")

        cons = Modelo._query(
            "SELECT c.id_conector, c.nombre, "
            "       c.coordenada_x_en_imagen, c.coordenada_y_en_imagen, "
            "       i.path_archivo "
            "FROM conector c "
            "LEFT JOIN imagen i ON i.id_imagen = c.id_imagen "
            "WHERE c.id_equipo = ? ORDER BY c.nombre",
            (self.id_equipo,))

        if not cons:
            self.lbl_equipo.text = f"[b]{nombre_local}[/b] — [i]{_('sin conectores')}[/i]"
            return

        cx_rows = Modelo._query(
            "SELECT cn.id_conector, c.codigo, "
            "       eb.nombre, COALESCE(teb.nombre,''), cb2.nombre, eb.id_equipo "
            "FROM conexion cn "
            "JOIN cable c ON c.id_cable = cn.id_cable "
            "JOIN conexion cn2 ON cn2.id_cable = cn.id_cable "
            "              AND cn2.id_conector != cn.id_conector "
            "JOIN conector cb2 ON cb2.id_conector = cn2.id_conector "
            "JOIN equipo eb ON eb.id_equipo = cb2.id_equipo "
            "LEFT JOIN tipo_equipo teb ON teb.id_tipo_equipo = eb.id_tipo_equipo "
            "WHERE cn.id_conector IN ("
            "  SELECT id_conector FROM conector WHERE id_equipo=?"
            ")", (self.id_equipo,))
        cx_map = {}
        for row in cx_rows:
            cx_map.setdefault(str(row[0]), []).append(row[1:])

        path_img = None
        idx_color = 0
        num = 1

        for r in cons:
            id_con = str(r[0])
            con_local = s(r[1])
            x_str = s(r[2]).strip() if r[2] is not None else ""
            y_str = s(r[3]).strip() if r[3] is not None else ""
            path = s(r[4]).strip() if r[4] else ""
            if path and path_img is None:
                path_img = path

            color = PALETA[idx_color % len(PALETA)]
            cxs = cx_map.get(id_con, [])
            cable_str = s(cxs[0][0]) if cxs else ""
            eq_b = s(cxs[0][1]) if cxs else ""
            tipo_b = s(cxs[0][2]) if cxs else ""
            con_b = s(cxs[0][3]) if cxs else ""
            id_eq_b = str(cxs[0][4]) if cxs else ""

            if x_str and y_str:
                try:
                    ix, iy = int(float(x_str)), int(float(y_str))
                except ValueError:
                    ix = iy = None
                if ix is not None:
                    self._marcadores.append({
                        "x": ix, "y": iy, "rgb": color, "num": num,
                        "cable": cable_str, "con_local": con_local,
                        "eq_b": eq_b, "tipo_b": tipo_b, "con_b": con_b,
                        "id_eq_b": id_eq_b,
                    })
                    fila_color = (*color, 0.25)
                    self._agregar_fila([str(num), con_local, cable_str, eq_b,
                                       tipo_b, con_b], fila_color, id_eq_b,
                                      len(self._marcadores) - 1)
                    idx_color += 1; num += 1
            else:
                self._agregar_fila(["—", con_local, cable_str, eq_b, tipo_b,
                                   con_b], (0.2, 0.2, 0.2, 0.3), id_eq_b, None)
                num += 1

        if path_img:
            ruta = _ruta_imagen(path_img)
            self.visor.set_imagen(ruta)
            Clock.schedule_once(lambda *_a: self.visor._zoom_fit(), 0.3)

    def _agregar_fila(self, valores, color, id_eq_b, idx_marcador):
        fila = _FilaTablaSimple(
            valores, color, col_width=self._col_w,
            on_click=lambda f, i=idx_marcador: self._on_click_fila(i),
            on_mantener=lambda f, ie=id_eq_b: self._on_mantener_fila(ie))
        self.box_filas.add_widget(fila)
        self._filas_widgets.append((fila, idx_marcador))

    # ── overlay ──
    def _dibujar_overlay(self, cw):
        z = self.visor.zoom
        M = self.MARCADOR * z
        for i, m in enumerate(self._marcadores):
            wx, wy = self.visor.i2w(m["x"], m["y"])
            resaltado = (i == self._resaltado)
            dibujar_marcador_cuadrado(cw, wx, wy, M, m["rgb"],
                                     0.40 if resaltado else 0.15, resaltado)
            from kivy.graphics import Color, Rectangle
            ns = str(m["num"])
            lbl_n = Label(text=ns, font_size=max(10, 13 * z), bold=True,
                         size=(M, M), pos=(wx - M / 2, wy - M / 2),
                         color=(1, 1, 1, 1))
            lbl_n.texture_update()
            with cw.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=lbl_n.texture, pos=(wx - lbl_n.texture_size[0] / 2,
                                                      wy - lbl_n.texture_size[1] / 2),
                          size=lbl_n.texture_size)

    def _on_click_fila(self, idx_marcador):
        self._resaltado = idx_marcador if idx_marcador is not None else -1
        if idx_marcador is not None and idx_marcador < len(self._marcadores):
            m = self._marcadores[idx_marcador]
            self.visor.scroll_to_img(m["x"], m["y"])
        self.visor.queue_draw()

    def _on_mantener_fila(self, id_eq_b):
        if id_eq_b and id_eq_b.strip() not in ("", "0"):
            ImagenConectoresYCables(id_equipo=id_eq_b).open()

    def _on_clic_imagen(self, lx, ly):
        ix, iy = self.visor.w2i(lx, ly)
        hm = self.MARCADOR // 2
        mejor_d, mejor_i = float("inf"), -1
        for i, m in enumerate(self._marcadores):
            if abs(ix - m["x"]) <= hm and abs(iy - m["y"]) <= hm:
                d = math.hypot(ix - m["x"], iy - m["y"])
                if d < mejor_d:
                    mejor_d, mejor_i = d, i
        if mejor_i >= 0:
            self._resaltado = mejor_i
            self.visor.queue_draw()


def abrir_imagen_conectores(id_equipo):
    ImagenConectoresYCables(id_equipo=id_equipo).open()


# ═══════════════════════════════════════════════════════════════════════════
# 3. ArbolConexionesEquipo
# ═══════════════════════════════════════════════════════════════════════════

class _NodoArbol:
    """Nodo del árbol de conexiones (reemplaza al Gtk.TreeStore original)."""

    def __init__(self, texto, key, tipo, color="#e8e8e8", bold=False,
                italic=False):
        self.texto = texto
        self.key = key
        self.tipo = tipo  # "equipo" | "cable" | "dummy"
        self.color = color
        self.bold = bold
        self.italic = italic
        self.hijos = []
        self.expandido = False
        self.cargado = False  # solo aplica a tipo == "equipo"


class _FilaArbol(ButtonBehavior, BoxLayout):
    def __init__(self, nodo, profundidad, tiene_hijos, on_toggle, on_doble_click,
                on_click, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(38), **kwargs)
        self.nodo = nodo
        self._ultimo_click = 0
        self._on_doble_click = on_doble_click
        self._on_click = on_click
        # Sangría más chica que en desktop (dp(14) en vez de dp(20) por
        # nivel): en 360dp de ancho, árboles de 4-5 niveles no pueden
        # darse el lujo de comerse tanto espacio horizontal por sangría.
        self.add_widget(BoxLayout(size_hint_x=None, width=profundidad * dp(14)))
        if tiene_hijos or nodo.tipo == "equipo":
            simbolo = "-" if nodo.expandido else "+"
            btn_toggle = Button(text=simbolo, size_hint_x=None, width=dp(36),
                               font_size=FUENTE_CHICA, bold=True)
            btn_toggle.bind(on_release=lambda *_a: on_toggle(nodo))
            self.add_widget(btn_toggle)
        else:
            self.add_widget(BoxLayout(size_hint_x=None, width=dp(36)))
        color_rgba = self._hex_a_rgba(nodo.color)
        # size_hint_x=None + ancho ligado a texture_size: el texto se
        # muestra completo (sin truncar) y queda alineado a la izquierda
        # de forma natural, permitiendo que el ScrollView horizontal del
        # árbol llegue hasta el final de las ramas más largas.
        lbl = Label(text=nodo.texto, color=color_rgba,
                   bold=nodo.bold, italic=nodo.italic,
                   halign="left", valign="middle", font_size=FUENTE_CHICA,
                   size_hint_x=None)
        lbl.bind(texture_size=lambda w, val: setattr(w, "width", val[0] + dp(6)))
        self.add_widget(lbl)
        # La fila entera se ajusta a su contenido real (indentación +
        # botón + texto), no al ancho del popup.
        self.size_hint_x = None
        self.bind(minimum_width=self.setter("width"))

    @staticmethod
    def _hex_a_rgba(hex_color):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return (r, g, b, 1)

    def on_release(self):
        ahora = Clock.get_time()
        es_doble = (ahora - self._ultimo_click) < 0.4
        self._ultimo_click = ahora
        if self._on_click:
            self._on_click(self.nodo)
        if es_doble and self._on_doble_click:
            self._on_doble_click(self.nodo)


class ArbolConexionesEquipo(Popup):
    """
    Árbol jerárquico lazy-load:
      Equipo raíz
        Cable "cod" → conector
            Equipo destino (expandible recursivamente)
    """

    def __init__(self, id_equipo=None, **kwargs):
        self._raiz = None
        self._desarrollados = set()
        # Claves (tipo, id) de los nodos equipo/cable actualmente abiertos
        # en CUALQUIER rama del árbol. Antes de expandir un nodo se
        # consulta este set para no abrir dos veces el mismo equipo/cable.
        self._claves_abiertas = set()

        box_main = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))

        # Fila 1: qué equipo es la raíz actual (info, sin botones — en
        # 360dp de ancho, "Raíz:" + info + 4 botones no entraban ni
        # comprimidos).
        hb_info = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
        hb_info.add_widget(Label(text=_("Raíz:"), size_hint_x=None,
                                 width=dp(44), font_size=FUENTE_CHICA))
        self.lbl_sel = Label(text=_("Ningún equipo seleccionado"), italic=True,
                             font_size=FUENTE_CHICA, halign="left",
                             shorten=True, shorten_from="right")
        self.lbl_sel.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        hb_info.add_widget(self.lbl_sel)
        box_main.add_widget(hb_info)

        # Fila 2: botones de acción, en scroll horizontal.
        scroll_btn = ScrollView(size_hint_y=None, height=ALTO_BOTON,
                                do_scroll_y=False, bar_width=dp(4))
        hb = BoxLayout(size_hint_x=None, height=ALTO_BOTON, spacing=dp(6))
        hb.bind(minimum_width=hb.setter("width"))
        btn_elegir = Button(text=_("Elegir equipo…"), size_hint_x=None,
                           width=dp(160), font_size=FUENTE_CHICA)
        btn_elegir.bind(on_release=self._sel_equipo)
        btn_limpiar = Button(text=_("Limpiar"), size_hint_x=None,
                            width=dp(100), font_size=FUENTE_CHICA)
        btn_limpiar.bind(on_release=self._limpiar)
        btn_exp = Button(text=_("Expandir todo"), size_hint_x=None,
                        width=dp(150), font_size=FUENTE_CHICA)
        btn_exp.bind(on_release=lambda *_a: self._expandir_colapsar_todo(True))
        btn_col = Button(text=_("Colapsar todo"), size_hint_x=None,
                        width=dp(150), font_size=FUENTE_CHICA)
        btn_col.bind(on_release=lambda *_a: self._expandir_colapsar_todo(False))
        hb.add_widget(btn_elegir)
        hb.add_widget(btn_limpiar)
        hb.add_widget(btn_exp)
        hb.add_widget(btn_col)
        scroll_btn.add_widget(hb)
        box_main.add_widget(scroll_btn)

        # do_scroll_x=True (default) + box_arbol con size_hint=(None, None)
        # ligado a su minimum_width/height: las filas ya no se truncan
        # (ver _FilaArbol) y el ScrollView permite desplazarse
        # horizontalmente hasta el final de las ramas más largas.
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True, bar_width=dp(4))
        self.box_arbol = BoxLayout(orientation="vertical", size_hint=(None, None),
                                   spacing=1)
        self.box_arbol.bind(minimum_height=self.box_arbol.setter("height"),
                            minimum_width=self.box_arbol.setter("width"))
        scroll.add_widget(self.box_arbol)
        box_main.add_widget(scroll)

        self.lbl_info = Label(text="", size_hint_y=None, height=0,
                              color=(0.7, 0.85, 1, 1), halign="left",
                              valign="middle", font_size=FUENTE_CHICA)
        self.lbl_info.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        box_main.add_widget(self.lbl_info)

        self.lbl_status = Label(text="", size_hint_y=None, height=dp(22),
                                font_size=FUENTE_CHICA, color=(0.6, 0.6, 0.6, 1),
                                halign="left", valign="middle")
        self.lbl_status.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        box_main.add_widget(self.lbl_status)

        outer = BoxLayout(orientation="vertical")
        outer.add_widget(barra_superior_dialogo(
            _("Árbol de conexiones de equipo"), on_atras=lambda: self.dismiss()))
        outer.add_widget(box_main)
        super().__init__(title="", separator_height=0,
                         content=outer, size_hint=(1, 1), **kwargs)

        if id_equipo:
            self._cargar_raiz(str(id_equipo))

    # ── helpers ──
    def _nombre_equipo(self, id_eq):
        rows = Modelo.devolver_equipo(id_eq)
        return s(rows[0][1]) if rows and rows[0][1] else f"Equipo {id_eq}"

    def _buscar_cable_hijo(self, nodo_padre, clave):
        for h in nodo_padre.hijos:
            if h.tipo == "cable" and h.key == clave:
                return h
        return None

    def _hijo_equipo_existe(self, nodo_cable, id_dest):
        return any(h.key == id_dest for h in nodo_cable.hijos)

    def _poblar(self, nodo_padre_equipo, id_eq_local, datos):
        for r in datos:
            cable = s(r[0]).strip() or "?"
            con_loc = s(r[3])
            eq_dest = s(r[1])
            id_dest = s(r[10]).strip()

            clave_cable = f"{id_eq_local}::{cable}"
            nodo_cable = self._buscar_cable_hijo(nodo_padre_equipo, clave_cable)
            if nodo_cable is None:
                nodo_cable = _NodoArbol(f" {cable}  ›  {con_loc}",
                                       clave_cable, "cable", color="#5ab0e0")
                nodo_padre_equipo.hijos.append(nodo_cable)

            if self._hijo_equipo_existe(nodo_cable, id_dest):
                continue

            if id_dest in ("0", ""):
                color_d, expandible = "#aaaaaa", False
            else:
                color_d, expandible = "#5adc7e", True

            nodo_dest = _NodoArbol(f" {eq_dest}", id_dest, "equipo",
                                  color=color_d, italic=not expandible)
            nodo_cable.hijos.append(nodo_dest)

    def _cargar_raiz(self, id_eq):
        if not id_eq or id_eq == "0":
            return
        nombre = self._nombre_equipo(id_eq)
        self.lbl_sel.text = f"[b]{nombre}[/b]"
        self.lbl_sel.markup = True
        self.lbl_sel.italic = False

        datos = Modelo.devolver_equipos_conectados_a_equipo(id_eq)
        if not datos:
            self.lbl_status.text = _("El equipo no tiene conexiones registradas.")
            return

        self._raiz = _NodoArbol(f" {nombre}", id_eq, "equipo",
                                color="#3a8ee0", bold=True)
        self._poblar(self._raiz, id_eq, datos)
        self._raiz.cargado = True
        self._raiz.expandido = True
        self._desarrollados.add(id_eq)
        self._claves_abiertas.add(("equipo", id_eq))
        self.lbl_status.text = _("Cargadas {} conexiones para «{}»").format(
            len(datos), nombre)
        self._rebuild()

    def _toggle_nodo(self, nodo):
        clave = (nodo.tipo, nodo.key)
        abriendo = not nodo.expandido

        # Si se va a ABRIR un nodo equipo/cable cuya clave ya está abierta
        # en otra rama del árbol, no lo abrimos (evita duplicados).
        if (abriendo and nodo.key not in ("", "0")
                and nodo.tipo in ("equipo", "cable")
                and clave in self._claves_abiertas):
            self.lbl_status.text = _(
                "Ese equipo/cable ya está abierto en otra rama del árbol.")
            return

        if nodo.tipo == "equipo" and not nodo.cargado:
            if nodo.key in ("", "0"):
                return
            datos = Modelo.devolver_equipos_conectados_a_equipo(nodo.key)
            nombre = self._nombre_equipo(nodo.key)
            if datos:
                self._poblar(nodo, nodo.key, datos)
                nodo.expandido = True
                self.lbl_status.text = f"«{nombre}» — {len(datos)} conexiones"
            else:
                nodo.color = "#aaaaaa"; nodo.italic = True
                self.lbl_status.text = _("«{}» no tiene más conexiones").format(nombre)
            nodo.cargado = True
            self._desarrollados.add(nodo.key)
        else:
            nodo.expandido = not nodo.expandido

        if nodo.key not in ("", "0") and nodo.tipo in ("equipo", "cable"):
            if nodo.expandido:
                self._claves_abiertas.add(clave)
            else:
                self._claves_abiertas.discard(clave)
        self._rebuild()

    def _expandir_colapsar_todo(self, expandir):
        def _rec(nodo):
            if nodo.hijos:
                clave = (nodo.tipo, nodo.key)
                puede = nodo.key in ("", "0") or nodo.tipo not in ("equipo", "cable")
                if expandir:
                    if puede or clave not in self._claves_abiertas:
                        nodo.expandido = True
                        if not puede:
                            self._claves_abiertas.add(clave)
                else:
                    nodo.expandido = False
                    if not puede:
                        self._claves_abiertas.discard(clave)
            for h in nodo.hijos:
                _rec(h)
        if self._raiz:
            _rec(self._raiz)
        self._rebuild()

    # ── render ──
    def _rebuild(self):
        self.box_arbol.clear_widgets()
        if self._raiz:
            self._render_nodo(self._raiz, 0)

    def _render_nodo(self, nodo, profundidad):
        tiene_hijos = bool(nodo.hijos)
        fila = _FilaArbol(nodo, profundidad, tiene_hijos, self._toggle_nodo,
                          self._on_doble_clic, self._on_click)
        self.box_arbol.add_widget(fila)
        if nodo.expandido:
            for h in nodo.hijos:
                self._render_nodo(h, profundidad + 1)
            if nodo.tipo == "equipo" and not nodo.cargado:
                placeholder = _NodoArbol("   " + _("(tocar > para cargar...)"),
                                        "", "dummy", color="#888888", italic=True)
                self._render_nodo(placeholder, profundidad + 1)

    def _on_click(self, nodo):
        if nodo.tipo == "equipo" and nodo.key not in ("", "0"):
            self.lbl_info.height = 40
            self.lbl_info.text = (
                f"[b]Equipo ID {nodo.key}[/b]  —  {nodo.texto.strip()}\n"
                "[size=11]Tocá > para cargar conexiones | doble clic para ver "
                "imagen de conectores[/size]")
            self.lbl_info.markup = True
        elif nodo.tipo == "cable":
            cod = nodo.key.split("::", 1)[1] if "::" in nodo.key else nodo.key
            self.lbl_info.height = 22
            self.lbl_info.text = f"[b]{_('Cable')}:[/b]  {cod}"
            self.lbl_info.markup = True
        else:
            self.lbl_info.height = 0
            self.lbl_info.text = ""

    def _on_doble_clic(self, nodo):
        if nodo.tipo == "equipo" and nodo.key not in ("", "0"):
            ImagenConectoresYCables(id_equipo=nodo.key).open()

    def _sel_equipo(self, *_a):
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_, nombre, _f):
            self._limpiar()
            self._cargar_raiz(str(id_))

        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()

    def _limpiar(self, *_a):
        self._raiz = None
        self._desarrollados.clear()
        self._claves_abiertas.clear()
        self.lbl_sel.text = _("Ningún equipo seleccionado")
        self.lbl_sel.italic = True
        self.lbl_sel.markup = False
        self.lbl_info.text = ""
        self.lbl_info.height = 0
        self.lbl_status.text = ""
        self.box_arbol.clear_widgets()


def abrir_arbol_conexiones(id_equipo=None):
    ArbolConexionesEquipo(id_equipo=id_equipo).open()
