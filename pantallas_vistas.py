"""
CableDoc Kivy - Vistas gráficas (fases 5 y 6).

Equivalente a VistaRack, VistaFrameSlots y PatcherasVista de
pantallas_avanzadas.py (GTK).

A diferencia de las pantallas de la fase 3 (que dibujan un overlay sobre
una FOTO), VistaRack y PatcherasVista dibujan una grilla completa a mano:
no hay textura de fondo, cada celda se calcula matemáticamente. Para esto
se usan _GrillaRackWidget y _PatcheraStripWidget en este módulo, en vez
de ImagenCanvas.

VistaFrameSlots sí dibuja sobre una foto (la imagen del frame), así que
reutiliza VisorImagenZoom igual que ImagenConectoresYCables.

Lo que queda para una fase posterior: DiagramaConexiones (depende de
impacto_ui.py, prioridad baja), EditorConexiones,
EditorMasivoConectoresImagen, EditorMasivoSlotsFrame.
"""

import math
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp

from widgets_base import (
    VisorImagenZoom, mostrar_info, mostrar_error, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, fila_cerrar_arriba,
    barra_superior_dialogo,
)
from pantallas_avanzadas import PALETA, _ruta_imagen, _FilaTablaSimple
from modelo import Modelo


# ═══════════════════════════════════════════════════════════════════════════
# VistaRack
# ═══════════════════════════════════════════════════════════════════════════

COL_EQUIPO = (0.78, 0.90, 0.98, 1)
COL_FRAME = (1.00, 0.88, 0.68, 1)
COL_LIBRE = (0.93, 0.93, 0.93, 1)
COL_BANDEJA = (0.68, 0.92, 0.68, 1)
COL_NUM_BG = (0.82, 0.82, 0.82, 1)
COL_HEADER = (0.15, 0.20, 0.35, 1)

BORDE_EQUIPO = (0.30, 0.55, 0.75, 1)
BORDE_FRAME = (0.65, 0.48, 0.10, 1)
BORDE_BANDEJA = (0.15, 0.60, 0.15, 1)
BORDE_LIBRE = (0.55, 0.55, 0.55, 1)


def _construir_segmentos_rack(id_rack):
    """Calcula los segmentos visuales de un rack (libre/equipo/frame/
    bandeja), igual que VistaRack._cargar() del original. No depende de
    GTK, así que se porta casi literal."""
    rows_rack = Modelo.devolver_rack(id_rack)
    if not rows_rack:
        return None
    r = rows_rack[0]
    nombre_rack = s(r[2])
    try:
        cap_u = max(1, int(r[3]))
    except (TypeError, ValueError):
        cap_u = 42
    cap = cap_u * 3  # 1 U = 3 orificios

    devs = Modelo.devolver_dispositivos_de_un_rack(id_rack)
    u_map = {u: [] for u in range(1, cap + 1)}
    for d in devs:
        try:
            u_ini = int(d[2]) if d[2] else 0
            ur = int(d[5]) if d[5] else 1
            u_count = ur * 3
        except (TypeError, ValueError):
            continue
        if u_ini < 1 or u_count < 1:
            continue
        info = {
            "nombre": s(d[4]).strip() or "?",
            "inv": s(d[3]).strip(),
            "tipo": "frame" if (d[8] and str(d[8]).strip() not in
                               ("", "0", "None")) else "equipo",
            "u_ini": u_ini, "u_count": u_count,
        }
        for u in range(u_ini, min(u_ini + u_count, cap + 1)):
            u_map[u].append(info)

    def estado(u):
        n = len(u_map[u])
        return "libre" if n == 0 else ("single" if n == 1 else "bandeja")

    segmentos = []
    procesadas = set()
    u = 1
    while u <= cap:
        if u in procesadas:
            u += 1
            continue
        est = estado(u)
        if est == "libre":
            segmentos.append({"u_ini": u, "u_count": 1, "tipo": "libre",
                             "nombre": "", "inv": ""})
            procesadas.add(u)
            u += 1
        elif est == "bandeja":
            infos = u_map[u]
            key = frozenset(i["nombre"] for i in infos)
            u_end = u
            while u_end + 1 <= cap:
                nxt = u_map[u_end + 1]
                if len(nxt) >= 2 and frozenset(i["nombre"] for i in nxt) == key:
                    u_end += 1
                else:
                    break
            nombres = list(dict.fromkeys(i["nombre"] for i in infos))
            segmentos.append({"u_ini": u, "u_count": u_end - u + 1,
                             "tipo": "bandeja", "nombre": nombres, "inv": ""})
            for uu in range(u, u_end + 1):
                procesadas.add(uu)
            u = u_end + 1
        else:
            main = u_map[u][0]
            u_ini_d = main["u_ini"]
            u_end_d = min(u_ini_d + main["u_count"] - 1, cap)
            actual_end = u
            for uu in range(u + 1, u_end_d + 1):
                if uu in procesadas:
                    break
                if estado(uu) == "single" and u_map[uu][0]["nombre"] == main["nombre"]:
                    actual_end = uu
                else:
                    break
            segmentos.append({"u_ini": u, "u_count": actual_end - u + 1,
                             "tipo": main["tipo"], "nombre": main["nombre"],
                             "inv": main["inv"]})
            for uu in range(u, actual_end + 1):
                procesadas.add(uu)
            u = actual_end + 1

    segmentos.sort(key=lambda x: x["u_ini"])
    return nombre_rack, cap, cap_u, segmentos, len(devs)


def _abreviar(texto, max_chars):
    if not texto:
        return ""
    return texto if len(texto) <= max_chars else texto[:max_chars - 1] + "…"


class _GrillaRackWidget(Widget):
    """Dibuja la grilla completa de un rack (sin foto de fondo)."""

    U_H = 28
    NUM_W = 40
    RACK_W = 310

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), **kwargs)
        self.zoom = 1.0
        self.cap = 0
        self.segmentos = []
        self.nombre_rack = ""
        self.resaltado = None
        self.bind(pos=self._redraw, size=self._redraw)

    def cargar(self, nombre_rack, cap, segmentos):
        self.nombre_rack = nombre_rack
        self.cap = cap
        self.segmentos = segmentos
        self._actualizar_size()

    def set_zoom(self, z):
        self.zoom = max(0.25, min(4.0, z))
        self._actualizar_size()

    def _actualizar_size(self):
        z = self.zoom
        w = int((self.NUM_W + self.RACK_W) * z) or 350
        h = int((1 + max(1, self.cap)) * self.U_H * z) or 300
        self.size = (w, h)
        self._redraw()

    def segmento_en(self, u):
        for sg in self.segmentos:
            if sg["u_ini"] <= u < sg["u_ini"] + sg["u_count"]:
                return sg
        return None

    def u_en_punto(self, lx, ly):
        """lx, ly en coordenadas locales (bottom-up). Retorna número de U
        u None."""
        z = self.zoom
        UH = self.U_H * z
        y_top = self.height - ly
        if y_top < UH:
            return None
        u = int((y_top - UH) / UH) + 1
        if u < 1 or u > self.cap:
            return None
        return u

    def _redraw(self, *_a):
        self.canvas.clear()
        z = self.zoom
        UH = self.U_H * z
        NW = self.NUM_W * z
        RW = self.RACK_W * z
        total_w = NW + RW
        total_h = UH + self.cap * UH if self.cap else self.height

        with self.canvas:
            from kivy.graphics import PushMatrix, PopMatrix, Translate
            PushMatrix()
            Translate(self.x, self.y + self.height - total_h)
            Color(1, 1, 1, 1)
            Rectangle(pos=(0, 0), size=(total_w, total_h))

            if not self.segmentos:
                PopMatrix()
                return

            y_header = total_h - UH
            Color(*COL_HEADER)
            Rectangle(pos=(0, y_header), size=(total_w, UH))

            for sg in self.segmentos:
                u_ini, u_count, tipo = sg["u_ini"], sg["u_count"], sg["tipo"]
                nombre, inv = sg["nombre"], sg.get("inv", "")
                y0_top = UH + (u_ini - 1) * UH
                h = u_count * UH
                y0_local = total_h - y0_top - h

                if tipo == "libre":
                    bg, border = COL_LIBRE, BORDE_LIBRE
                elif tipo == "frame":
                    bg, border = COL_FRAME, BORDE_FRAME
                elif tipo == "bandeja":
                    bg, border = COL_BANDEJA, BORDE_BANDEJA
                else:
                    bg, border = COL_EQUIPO, BORDE_EQUIPO

                for i in range(u_count):
                    u_num = u_ini + i
                    y_u_top = UH + (u_num - 1) * UH
                    y_u_local = total_h - y_u_top - UH
                    Color(*COL_NUM_BG)
                    Rectangle(pos=(0, y_u_local), size=(NW, UH))

                resaltado = (self.resaltado == u_ini)
                Color(*bg)
                Rectangle(pos=(NW, y0_local), size=(RW, h))
                Color(*border)
                Line(rectangle=(NW, y0_local, RW, h),
                    width=(3 if resaltado else 1.5) * z)

                if tipo == "bandeja":
                    texto = _("Bandeja: ") + ", ".join(nombre)
                elif tipo == "libre":
                    texto = _("LIBRE")
                else:
                    texto = nombre
                texto = _abreviar(texto, max(4, int(RW / (7 * z))))
                self._texto_centrado(texto, NW + RW / 2, y0_local + h / 2,
                                    max(8, min(12 * z, h * 0.5)))

                for i in range(u_count):
                    u_num = u_ini + i
                    y_u_top = UH + (u_num - 1) * UH
                    y_u_local = total_h - y_u_top - UH
                    self._texto_centrado(str(u_num), NW * 0.5,
                                        y_u_local + UH / 2,
                                        max(7, 9 * z), color=(0.2, 0.2, 0.2, 1))

            self._texto_centrado(self.nombre_rack, total_w / 2,
                                y_header + UH / 2, max(9, 13 * z),
                                color=(1, 1, 1, 1), bold=True)

            Color(0.15, 0.18, 0.22, 1)
            Line(rectangle=(0, 0, total_w, total_h), width=max(2, 3 * z))
            PopMatrix()

    def _texto_centrado(self, texto, cx, cy, font_size, color=(0, 0, 0, 1),
                        bold=False):
        if not texto:
            return
        lbl = Label(text=texto, font_size=font_size, color=color, bold=bold)
        lbl.texture_update()
        if not lbl.texture:
            return
        tw, th = lbl.texture_size
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=lbl.texture, pos=(cx - tw / 2, cy - th / 2),
                      size=(tw, th))


class VistaRack(Popup):
    def __init__(self, id_rack=None, **kwargs):
        self._cap = 0
        self._segmentos = []

        box_main = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))

        hb_top = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        btn_sel = Button(text=_("Elegir rack…"), size_hint_x=None,
                        width=dp(140), font_size=FUENTE_CHICA)
        btn_sel.bind(on_release=self._sel_rack)
        self.lbl_rack = Label(text=_("Seleccione un rack…"), italic=True,
                             font_size=FUENTE_CHICA, halign="left",
                             shorten=True, shorten_from="right")
        self.lbl_rack.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        hb_top.add_widget(btn_sel)
        hb_top.add_widget(self.lbl_rack)
        box_main.add_widget(hb_top)

        # Fila de zoom (propia): Zoom: valor, +, −, 1:1, Ajustar.
        hbz = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.lbl_zoom = Label(text="100%", size_hint_x=None, width=dp(50),
                              font_size=FUENTE_CHICA)
        hbz.add_widget(Label(text=_("Zoom:"), size_hint_x=None, width=dp(44),
                            font_size=FUENTE_CHICA))
        hbz.add_widget(self.lbl_zoom)
        for etiqueta, factor in [("+", 1.2), ("-", 1 / 1.2)]:
            b = Button(text=etiqueta, size_hint_x=None, width=dp(40),
                      font_size=FUENTE_NORMAL)
            b.bind(on_release=lambda _b, f=factor: self._set_zoom(
                self.grilla.zoom * f))
            hbz.add_widget(b)
        b11 = Button(text="1:1", size_hint_x=None, width=dp(46),
                    font_size=FUENTE_CHICA)
        b11.bind(on_release=lambda *_a: self._set_zoom(1.0))
        bfit = Button(text=_("Ajustar"), size_hint_x=None, width=dp(76),
                     font_size=FUENTE_CHICA)
        bfit.bind(on_release=lambda *_a: self._zoom_fit())
        hbz.add_widget(b11); hbz.add_widget(bfit)
        box_main.add_widget(hbz)

        # Fila de leyenda (propia, scroll horizontal): en desktop
        # compartía fila con el zoom, pero "Zoom + botones + 3 leyendas"
        # no entra ni comprimido en 360dp de ancho.
        scroll_ley = ScrollView(size_hint_y=None, height=dp(26),
                                do_scroll_y=False, bar_width=dp(3))
        hb_ley = BoxLayout(size_hint_x=None, height=dp(26), spacing=dp(4))
        hb_ley.bind(minimum_width=hb_ley.setter("width"))
        for texto, color in [(_("Equipo"), COL_EQUIPO), (_("Frame"), COL_FRAME),
                            (_("Bandeja"), COL_BANDEJA)]:
            hb_ley.add_widget(self._leyenda(color))
            hb_ley.add_widget(Label(text=texto, size_hint_x=None,
                                    width=dp(20) + len(texto) * dp(7),
                                    font_size=sp(11)))
        scroll_ley.add_widget(hb_ley)
        box_main.add_widget(scroll_ley)

        self.scroll = ScrollView()
        self.grilla = _GrillaRackWidget()
        cont = BoxLayout(size_hint=(None, None))
        cont.add_widget(self.grilla)
        cont.bind(minimum_size=cont.setter("size"))
        self.scroll.add_widget(cont)
        box_main.add_widget(self.scroll)

        self.lbl_status = Label(text="", size_hint_y=None, height=dp(22),
                                font_size=sp(10), color=(0.6, 0.6, 0.6, 1),
                                halign="left")
        box_main.add_widget(self.lbl_status)

        outer = BoxLayout(orientation="vertical")
        self._barra_top = barra_superior_dialogo(
            _("Vista de Rack"), on_atras=lambda: self.dismiss())
        outer.add_widget(self._barra_top)
        outer.add_widget(box_main)

        super().__init__(title="", separator_height=0, content=outer,
                         size_hint=(1, 1), **kwargs)
        self.grilla.on_touch_down = self._dummy

        if id_rack:
            self._cargar(id_rack)

    def _dummy(self, *_a):
        return False

    def _leyenda(self, color):
        w = Widget(size_hint=(None, None), size=(dp(14), dp(14)))

        def _draw(*_a):
            w.canvas.clear()
            with w.canvas:
                Color(*color)
                Rectangle(pos=w.pos, size=w.size)
                Color(0.4, 0.4, 0.4, 1)
                Line(rectangle=(*w.pos, *w.size), width=1)
        w.bind(pos=_draw, size=_draw)
        Clock.schedule_once(_draw, 0)
        return w

    def _sel_rack(self, *_a):
        from pantallas_racks import RacksListado

        def _con_rack(id_, _nombre, _f):
            self._cargar(id_)
        RacksListado(modo_seleccion=True, on_seleccionar=_con_rack).open()

    def _cargar(self, id_rack):
        resultado = _construir_segmentos_rack(id_rack)
        if not resultado:
            return
        nombre_rack, cap, cap_u, segmentos, n_devs = resultado
        self._cap = cap
        self._segmentos = segmentos
        self._barra_top.lbl_titulo.text = f"{_('Vista de Rack')}: {nombre_rack}"

        n_eq = sum(1 for sg in segmentos if sg["tipo"] == "equipo")
        n_fr = sum(1 for sg in segmentos if sg["tipo"] == "frame")
        n_ban = sum(1 for sg in segmentos if sg["tipo"] == "bandeja")
        n_lib = sum(sg["u_count"] for sg in segmentos if sg["tipo"] == "libre")
        self.lbl_rack.text = f"[b]{nombre_rack}[/b]  ({cap_u} U / {cap} orificios)"
        self.lbl_rack.markup = True
        self.lbl_rack.italic = False
        self.lbl_status.text = (
            f"{n_devs} asignaciones — {n_eq} equipos, {n_fr} frames, "
            f"{n_ban} bandejas, {n_lib} orificios libres (1 U = 3 orificios)")

        self.grilla.cargar(nombre_rack, cap, segmentos)
        self.grilla.on_touch_down = self._on_click_grilla
        Clock.schedule_once(lambda *_a: self._zoom_fit(), 0.3)

    def _on_click_grilla(self, touch):
        if not self.grilla.collide_point(*touch.pos):
            return False
        lx, ly = self.grilla.to_widget(touch.x, touch.y, relative=True)
        u = self.grilla.u_en_punto(lx, ly)
        if u is not None:
            sg = self.grilla.segmento_en(u)
            if sg:
                self.grilla.resaltado = sg["u_ini"]
                self.grilla._redraw()
                if sg["tipo"] == "libre":
                    self.lbl_status.text = f"U{u} — {_('LIBRE')}"
                elif sg["tipo"] == "bandeja":
                    self.lbl_status.text = (
                        f"U{sg['u_ini']}–{sg['u_ini']+sg['u_count']-1}  "
                        f"[{_('Bandeja compartida')}] " + ", ".join(sg["nombre"]))
                else:
                    rng = (f"U{sg['u_ini']}" if sg["u_count"] == 1 else
                          f"U{sg['u_ini']}–{sg['u_ini']+sg['u_count']-1}")
                    txt = f"{rng}  {sg['nombre']}"
                    if sg.get("inv"):
                        txt += f"  (Inv: {sg['inv']})"
                    self.lbl_status.text = txt
        return True

    def _set_zoom(self, z):
        self.grilla.set_zoom(z)
        self.lbl_zoom.text = f"{int(self.grilla.zoom * 100)}%"

    def _zoom_fit(self):
        if not self._cap or not self.scroll.height:
            return
        zh = self.scroll.height / ((1 + self._cap) * self.grilla.U_H)
        zw = self.scroll.width / (self.grilla.NUM_W + self.grilla.RACK_W)
        self._set_zoom(min(zh, zw))


def abrir_vista_rack(id_rack=None):
    VistaRack(id_rack=id_rack).open()


# ═══════════════════════════════════════════════════════════════════════════
# VistaFrameSlots
# ═══════════════════════════════════════════════════════════════════════════

class VistaFrameSlots(Popup):
    """Foto del frame con un rectángulo por slot (equivalente a
    ImagenConectoresYCables, pero con rectángulos en vez de cuadrados de
    tamaño fijo, ya que cada slot tiene su propio ancho/alto)."""

    def __init__(self, id_frame, **kwargs):
        self.id_frame = str(id_frame)
        self._marcadores = []
        self._resaltado = -1
        self._col_w = dp(110)

        # Apilado en vez de lado a lado (imagen 62% + tabla 38%): a
        # 360dp de ancho la tabla quedaba en ~137dp, insuficiente incluso
        # para 3 columnas cortas.
        outer = BoxLayout(orientation="vertical")
        self._barra_top = barra_superior_dialogo(
            _("Slots del frame"), on_atras=lambda: self.dismiss())
        outer.add_widget(self._barra_top)

        self.visor = VisorImagenZoom(size_hint=(1, 0.55))
        self.visor.set_overlay_fn(self._dibujar_overlay)
        self.visor.canvas_widget.on_press_img = self._on_clic_imagen
        outer.add_widget(self.visor)

        panel = BoxLayout(orientation="vertical", spacing=dp(4),
                          size_hint=(1, 0.45), padding=dp(4))
        self.lbl_frame = Label(text=_("Cargando…"), italic=True,
                               size_hint_y=None, height=dp(26),
                               font_size=FUENTE_CHICA, halign="left")
        panel.add_widget(self.lbl_frame)

        cols_header = ["#", _("Slot"), _("Equipo")]
        tabla_scroll = ScrollView(do_scroll_x=True, do_scroll_y=True,
                                  bar_width=dp(4))
        tabla_root = BoxLayout(orientation="vertical", size_hint=(None, None),
                               spacing=dp(1))
        tabla_root.width = self._col_w * len(cols_header)
        tabla_root.bind(minimum_height=tabla_root.setter("height"))

        header = BoxLayout(size_hint=(None, None), height=dp(28),
                          width=self._col_w * len(cols_header))
        for titulo in cols_header:
            header.add_widget(Label(text=titulo, bold=True,
                                    font_size=FUENTE_CHICA,
                                    size_hint=(None, None),
                                    width=self._col_w, height=dp(28)))
        tabla_root.add_widget(header)

        self.box_filas = BoxLayout(orientation="vertical",
                                   size_hint=(None, None), spacing=dp(1),
                                   width=self._col_w * len(cols_header))
        self.box_filas.bind(minimum_height=self.box_filas.setter("height"))
        tabla_root.add_widget(self.box_filas)
        tabla_scroll.add_widget(tabla_root)
        panel.add_widget(tabla_scroll)

        panel.add_widget(Label(
            text=_("Mantené presionado fila - editar equipo") + "  |  " +
                _("Tap en imagen → resaltar slot"),
            font_size=sp(10), color=(0.6, 0.6, 0.6, 1), size_hint_y=None,
            height=dp(18)))
        outer.add_widget(panel)

        super().__init__(title="", separator_height=0, content=outer,
                         size_hint=(1, 1), **kwargs)
        self._cargar()

    def _cargar(self):
        rows = Modelo.devolver_slots_graficos_de_frame(self.id_frame)
        if not rows:
            self.lbl_frame.text = "[b]" + _("Frame sin slots registrados") + "[/b]"
            self.lbl_frame.markup = True
            self.lbl_frame.italic = False
            return

        fr = Modelo.devolver_frame(self.id_frame)
        frame_nom = s(fr[0][1]) if fr else f"Frame {self.id_frame}"
        self._barra_top.lbl_titulo.text = f"{_('Slots')}: {frame_nom}"
        self.lbl_frame.text = f"[b]{frame_nom}[/b]"
        self.lbl_frame.markup = True
        self.lbl_frame.italic = False

        img_path = ""
        for r in rows:
            if s(r[8]).strip():
                img_path = s(r[8]).strip(); break
        if not img_path:
            for r in rows:
                if s(r[9]).strip():
                    img_path = s(r[9]).strip(); break

        idx_color = 0
        num = 1
        for r in rows:
            slot_nom = s(r[1])
            id_eq = s(r[2]) if r[2] else ""
            eq_nom = s(r[3])
            x = int(r[4]) if r[4] else 0
            y = int(r[5]) if r[5] else 0
            ancho = int(r[6]) if r[6] and int(r[6]) > 0 else 50
            alto = int(r[7]) if r[7] and int(r[7]) > 0 else 30

            if id_eq:
                color = PALETA[idx_color % len(PALETA)]
                idx_color += 1
            else:
                color = (0.55, 0.55, 0.58)

            self._marcadores.append({
                "num": num, "slot_nom": slot_nom,
                "eq_nom": eq_nom or _("(vacío)"), "id_eq": id_eq,
                "x": x, "y": y, "ancho": ancho, "alto": alto, "rgb": color,
            })
            fila_color = (*color, 0.25)
            self._agregar_fila([str(num), slot_nom, eq_nom or _("(vacío)")],
                              fila_color, id_eq, len(self._marcadores) - 1)
            num += 1

        if img_path:
            ruta = _ruta_imagen(img_path)
            self.visor.set_imagen(ruta)
            Clock.schedule_once(lambda *_a: self.visor._zoom_fit(), 0.3)

    def _agregar_fila(self, valores, color, id_eq, idx_marcador):
        fila = _FilaTablaSimple(
            valores, color, col_width=self._col_w,
            on_click=lambda f, i=idx_marcador: self._on_click_fila(i),
            on_mantener=lambda f, ie=id_eq: self._on_mantener_fila(ie))
        self.box_filas.add_widget(fila)

    def _dibujar_overlay(self, cw):
        z = self.visor.zoom
        for i, m in enumerate(self._marcadores):
            wx, wy = self.visor.i2w(m["x"], m["y"] + m["alto"])
            ww = m["ancho"] * z
            wh = m["alto"] * z
            r, g, b = m["rgb"]
            resaltado = (i == self._resaltado)
            alpha = 0.45 if resaltado else 0.22
            with cw.canvas:
                Color(r, g, b, alpha)
                Rectangle(pos=(wx, wy), size=(ww, wh))
                Color(r, g, b, 0.95)
                Line(rectangle=(wx, wy, ww, wh),
                    width=max(2, (8 if resaltado else 4) * z))
                Color(0, 0, 0, 1)
                Line(rectangle=(wx, wy, ww, wh), width=max(1, 1.2 * z))

            ns = str(m["num"])
            lbl_n = Label(text=ns, font_size=max(9, 11 * z), bold=True,
                         color=(1, 1, 1, 1))
            lbl_n.texture_update()
            if lbl_n.texture:
                with cw.canvas:
                    Color(r, g, b, 0.85)
                    Rectangle(pos=(wx + 2, wy + wh - lbl_n.texture_size[1] - 2),
                              size=(lbl_n.texture_size[0] + 4,
                                   lbl_n.texture_size[1] + 4))
                    Color(1, 1, 1, 1)
                    Rectangle(texture=lbl_n.texture,
                              pos=(wx + 4, wy + wh - lbl_n.texture_size[1] - 1),
                              size=lbl_n.texture_size)

    def _on_click_fila(self, idx_marcador):
        self._resaltado = idx_marcador
        if idx_marcador is not None and idx_marcador < len(self._marcadores):
            m = self._marcadores[idx_marcador]
            self.visor.scroll_to_img(m["x"] + m["ancho"] // 2,
                                    m["y"] + m["alto"] // 2)
        self.visor.queue_draw()

    def _on_mantener_fila(self, id_eq):
        if id_eq and id_eq.strip():
            from pantallas_equipos import DialogoEquipo

            def _refrescar():
                self._marcadores.clear()
                self.box_filas.clear_widgets()
                self._resaltado = -1
                self._cargar()
                self.visor.queue_draw()
            DialogoEquipo(id_equipo=id_eq, on_guardado=_refrescar).open()

    def _on_clic_imagen(self, lx, ly):
        ix, iy = self.visor.w2i(lx, ly)
        mejor_d, mejor_i = float("inf"), -1
        for i, m in enumerate(self._marcadores):
            if (m["x"] <= ix <= m["x"] + m["ancho"] and
                    m["y"] <= iy <= m["y"] + m["alto"]):
                cx = m["x"] + m["ancho"] / 2
                cy = m["y"] + m["alto"] / 2
                d = math.hypot(ix - cx, iy - cy)
                if d < mejor_d:
                    mejor_d, mejor_i = d, i
        if mejor_i >= 0:
            self._resaltado = mejor_i
            self.visor.queue_draw()


def abrir_vista_frame_slots(id_frame):
    VistaFrameSlots(id_frame=id_frame).open()


# ═══════════════════════════════════════════════════════════════════════════
# PatcherasVista
# ═══════════════════════════════════════════════════════════════════════════

C_BG = (0.06, 0.06, 0.06, 1)
C_STRP = (0.10, 0.10, 0.12, 1)
C_RHDR = (0.15, 0.20, 0.30, 1)
C_GREEN = (0.10, 0.85, 0.20, 1)
C_RED = (0.90, 0.20, 0.15, 1)
C_DARK = (0.18, 0.18, 0.20, 1)
C_TXT = (0.82, 0.82, 0.85, 1)
C_NUM = (0.38, 0.38, 0.45, 1)
C_ROW = (0.55, 0.55, 0.62, 1)
C_EDGE = (0.18, 0.20, 0.26, 1)


def _cargar_datos_patcheras(id_equipo):
    """Calcula rack_data igual que PatcherasVista._cargar() del original
    (puro SQL/Python, sin GTK)."""
    import re as _re

    con_rows = Modelo._query(
        "SELECT DISTINCT c2.id_conector, c2.nombre "
        "FROM conexion cx1 "
        "JOIN conector c1 ON cx1.id_conector = c1.id_conector "
        "JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
        "   AND cx2.id_conector != cx1.id_conector "
        "JOIN conector c2 ON cx2.id_conector = c2.id_conector "
        "JOIN equipo e2 ON e2.id_equipo = c2.id_equipo "
        "JOIN tipo_equipo te ON te.id_tipo_equipo = e2.id_tipo_equipo "
        "WHERE c1.id_equipo = ? "
        "AND te.nombre = 'MODULO PATCHERA' "
        "AND (c2.nombre LIKE 'A_BACK%' OR c2.nombre LIKE 'B_BACK%')",
        (id_equipo,))
    con_conectados = {
        str(r[0]): ("A" if str(r[1]).upper().startswith("A") else "B")
        for r in con_rows
    }

    rack_rows = Modelo._query(
        "SELECT DISTINCT r.id_rack, r.nombre "
        "FROM rack r "
        "JOIN posicion_en_rack pr ON pr.id_rack = r.id_rack "
        "JOIN frame f ON f.id_frame = pr.id_frame "
        "JOIN slot s ON s.id_frame = f.id_frame "
        "JOIN equipo e ON e.id_equipo = s.id_equipo "
        "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
        "WHERE te.nombre = 'MODULO PATCHERA' "
        "ORDER BY r.nombre")

    rack_data = {}
    for id_rack, rack_nom in [(r[0], s(r[1])) for r in rack_rows]:
        frame_rows = Modelo._query(
            "SELECT DISTINCT f.id_frame, f.nombre "
            "FROM frame f "
            "JOIN posicion_en_rack pr ON pr.id_frame = f.id_frame "
            "JOIN slot s ON s.id_frame = f.id_frame "
            "JOIN equipo e ON e.id_equipo = s.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE pr.id_rack = ? AND te.nombre = 'MODULO PATCHERA' "
            "ORDER BY f.nombre", (id_rack,))

        frames_dict = {}
        for id_frame, frame_nom in [(fr[0], s(fr[1])) for fr in frame_rows]:
            slot_rows = Modelo._query(
                "SELECT s.nombre, c.id_conector, c.nombre "
                "FROM slot s "
                "JOIN equipo e ON e.id_equipo = s.id_equipo "
                "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
                "JOIN conector c ON c.id_equipo = e.id_equipo "
                "WHERE s.id_frame = ? AND te.nombre = 'MODULO PATCHERA' "
                "AND (c.nombre LIKE 'A_BACK%' OR c.nombre LIKE 'B_BACK%') "
                "ORDER BY s.nombre, c.nombre", (id_frame,))

            frame_cols = {}
            for sr in slot_rows:
                slot_nom = s(sr[0])
                id_con = str(sr[1])
                con_nom = s(sr[2]).upper()
                nums = _re.findall(r"\d+", slot_nom)
                col = int(nums[0]) if nums else 0
                if col == 0:
                    continue
                row = "A" if con_nom.startswith("A") else "B"
                if id_con in con_conectados:
                    color = "green" if row == "A" else "red"
                else:
                    color = "dark"
                frame_cols.setdefault(col, {"A": "dark", "B": "dark"})
                frame_cols[col][row] = color

            if frame_cols:
                frames_dict[frame_nom] = frame_cols

        if frames_dict:
            rack_data[rack_nom] = frames_dict

    return rack_data


class _PatcheraStripWidget(Widget):
    """Dibuja todas las patcheras (frames PPV/PPA) de UN rack."""

    DOT_R = 6
    DOT_STEP = 19
    ROW_H = 24
    HDR_H = 16
    LBL_W = 56
    STRIP_GAP = 3
    RHDR_H = 22
    MARGIN = 6

    def __init__(self, rack_nom, frames, **kwargs):
        super().__init__(size_hint=(None, None), **kwargs)
        self.rack_nom = rack_nom
        self.frames = frames
        self.zoom = 1.0
        self.STRIP_H = self.HDR_H + 2 * self.ROW_H
        self.bind(pos=self._redraw, size=self._redraw)
        self._actualizar_size()

    def _max_col(self):
        return max(
            (max(cols.keys(), default=0) for cols in self.frames.values()),
            default=24) or 24

    def strip_w(self):
        return (self.LBL_W + self._max_col() * self.DOT_STEP +
               self.MARGIN * 2) * self.zoom

    def rack_h(self):
        n_frames = len(self.frames)
        return (self.RHDR_H + self.MARGIN +
               n_frames * (self.STRIP_H + self.STRIP_GAP)) * self.zoom

    def set_zoom(self, z):
        self.zoom = max(0.3, min(3.0, z))
        self._actualizar_size()

    def _actualizar_size(self):
        self.size = (max(1, int(self.strip_w())), max(1, int(self.rack_h())))
        self._redraw()

    def celda_en(self, lx, ly):
        """lx, ly en coords locales bottom-up. Retorna (frame_nom, col, row)
        o None."""
        z = self.zoom
        y_top = self.height - ly
        rhdr, m = self.RHDR_H * z, self.MARGIN * z
        sh, sg = self.STRIP_H * z, self.STRIP_GAP * z
        lw, hh, rh, step = self.LBL_W * z, self.HDR_H * z, self.ROW_H * z, self.DOT_STEP * z

        y_rel = y_top - rhdr - m
        if y_rel < 0:
            return None
        strip_idx = int(y_rel / (sh + sg))
        nombres = sorted(self.frames.keys())
        if strip_idx >= len(nombres):
            return None
        frame_nom = nombres[strip_idx]
        y_in_strip = y_rel - strip_idx * (sh + sg)
        if y_in_strip < hh:
            return None
        row_idx = int((y_in_strip - hh) / rh)
        if row_idx > 1:
            return None
        row = "A" if row_idx == 0 else "B"
        col_idx = int((lx - lw) / step)
        if col_idx < 0:
            return None
        col = col_idx + 1
        if col > max(self.frames[frame_nom].keys(), default=24):
            return None
        return frame_nom, col, row

    def _redraw(self, *_a):
        self.canvas.clear()
        z = self.zoom
        m, lw, step = self.MARGIN * z, self.LBL_W * z, self.DOT_STEP * z
        dr, rh, hh = self.DOT_R * z, self.ROW_H * z, self.HDR_H * z
        sh, sg, rhdr = self.STRIP_H * z, self.STRIP_GAP * z, self.RHDR_H * z
        max_col = self._max_col()
        total_w, total_h = self.strip_w(), self.rack_h()

        with self.canvas:
            from kivy.graphics import PushMatrix, PopMatrix, Translate
            PushMatrix()
            # top-down local: y=0 arriba. Traducimos para que coincida con
            # bottom-up real del widget.
            Translate(self.x, self.y + self.height - total_h)
            y_td = lambda y_top_down: total_h - y_top_down  # helper

            Color(*C_BG)
            Rectangle(pos=(0, 0), size=(total_w, total_h))

            Color(*C_RHDR)
            Rectangle(pos=(0, y_td(rhdr)), size=(total_w, rhdr))
            self._texto(f"RACK {self.rack_nom.upper()}", m, y_td(rhdr * 0.3),
                       max(9, 11 * z), color=C_TXT, bold=True, ancla="izq")

            for s_idx, frame_nom in enumerate(sorted(self.frames.keys())):
                y0_top = rhdr + m + s_idx * (sh + sg)
                cols = self.frames[frame_nom]
                y0_local = y_td(y0_top + sh)

                Color(*C_STRP)
                Rectangle(pos=(0, y0_local), size=(total_w, sh))

                self._texto(frame_nom, lw * 0.45, y_td(y0_top + sh / 2),
                           max(7, 9 * z), color=C_TXT, ancla="centro")

                for c_idx in range(max_col):
                    cx = lw + c_idx * step + step / 2
                    self._texto(f"{c_idx+1:02d}", cx,
                               y_td(y0_top + hh * 0.72),
                               max(6, 7 * z), color=C_NUM, ancla="centro")

                for row_idx, row_lbl in enumerate(("A", "B")):
                    ry_top = y0_top + hh + row_idx * rh + rh / 2
                    ry_local = y_td(ry_top)
                    self._texto(row_lbl, lw * 0.80, ry_local,
                               max(7, 9 * z), color=C_ROW, ancla="centro")

                    if row_idx == 0:
                        Color(*C_EDGE)
                        Line(points=[lw, y_td(y0_top + hh + rh),
                                    total_w - m, y_td(y0_top + hh + rh)],
                            width=max(0.5, 0.8 * z))

                    for c_idx in range(max_col):
                        cx = lw + c_idx * step + step / 2
                        col = c_idx + 1
                        color = cols.get(col, {"A": "dark", "B": "dark"}).get(
                            row_lbl, "dark")
                        if color == "green":
                            fill_c, glow_c = C_GREEN, C_GREEN
                        elif color == "red":
                            fill_c, glow_c = C_RED, C_RED
                        else:
                            fill_c, glow_c = C_DARK, None

                        if glow_c:
                            Color(glow_c[0], glow_c[1], glow_c[2], 0.22)
                            rg = dr * 1.7
                            Ellipse(pos=(cx - rg, ry_local - rg), size=(rg * 2, rg * 2))

                        Color(*fill_c)
                        Ellipse(pos=(cx - dr, ry_local - dr), size=(dr * 2, dr * 2))
                        Color(1, 1, 1, 0.20 if color != "dark" else 0.05)
                        rs = dr * 0.38
                        Ellipse(pos=(cx - dr * 0.2 - rs, ry_local + dr * 0.3 - rs),
                               size=(rs * 2, rs * 2))

                Color(*C_EDGE)
                Line(rectangle=(0, y0_local, total_w, sh), width=max(1, 1.0 * z))

            Color(0.22, 0.25, 0.35, 1)
            Line(rectangle=(0, 0, total_w, total_h), width=max(1, 1.5 * z))
            PopMatrix()

    def _texto(self, texto, cx, cy, font_size, color=(1, 1, 1, 1), bold=False,
              ancla="centro"):
        if not texto:
            return
        lbl = Label(text=texto, font_size=font_size, color=color, bold=bold)
        lbl.texture_update()
        if not lbl.texture:
            return
        tw, th = lbl.texture_size
        px = cx - tw / 2 if ancla == "centro" else cx
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=lbl.texture, pos=(px, cy - th / 2), size=(tw, th))


class PatcherasVista(Popup):
    def __init__(self, id_equipo, nombre_equipo="", **kwargs):
        self.id_equipo = id_equipo
        self._rack_data = {}
        self._strips = {}

        box_main = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))

        # Fila 1: info (racks/patcheras/salidas/entradas) — su propia
        # fila, ancho completo, con shorten para no desbordar.
        self.lbl_info = Label(text=_("Cargando…"), italic=True, halign="left",
                             markup=True, size_hint_y=None, height=dp(30),
                             font_size=FUENTE_CHICA, shorten=True,
                             shorten_from="right")
        self.lbl_info.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        box_main.add_widget(self.lbl_info)

        # Fila 2: controles de zoom.
        hbz = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.lbl_zoom = Label(text="100%", size_hint_x=None, width=dp(50),
                              font_size=FUENTE_CHICA)
        hbz.add_widget(Label(text=_("Zoom:"), size_hint_x=None, width=dp(44),
                            font_size=FUENTE_CHICA))
        hbz.add_widget(self.lbl_zoom)
        for etiqueta, factor in [("+", 1.2), ("-", 1 / 1.2)]:
            b = Button(text=etiqueta, size_hint_x=None, width=dp(40),
                      font_size=FUENTE_NORMAL)
            b.bind(on_release=lambda _b, f=factor: self._set_zoom(self._zoom * f))
            hbz.add_widget(b)
        b11 = Button(text="1:1", size_hint_x=None, width=dp(46),
                    font_size=FUENTE_CHICA)
        b11.bind(on_release=lambda *_a: self._set_zoom(1.0))
        hbz.add_widget(b11)
        btn_png = Button(text=_("PNG"), size_hint_x=None,
                        width=dp(70), font_size=FUENTE_CHICA)
        btn_png.bind(on_release=self._exportar_png)
        hbz.add_widget(btn_png)
        box_main.add_widget(hbz)

        # Fila 3: leyenda de colores, en scroll horizontal.
        scroll_ley = ScrollView(size_hint_y=None, height=dp(26),
                                do_scroll_y=False, bar_width=dp(3))
        hb_ley = BoxLayout(size_hint_x=None, height=dp(26), spacing=dp(4))
        hb_ley.bind(minimum_width=hb_ley.setter("width"))
        for texto, color in [(_("Salida (A)"), C_GREEN), (_("Entrada (B)"), C_RED)]:
            dot = Widget(size_hint=(None, None), size=(dp(14), dp(14)))

            def _draw_dot(w, *_a, c=color):
                w.canvas.clear()
                with w.canvas:
                    Color(*c)
                    Ellipse(pos=w.pos, size=w.size)
            dot.bind(pos=_draw_dot, size=_draw_dot)
            Clock.schedule_once(lambda *_a, d=dot, c=color: _draw_dot(d, c=c), 0)
            hb_ley.add_widget(dot)
            hb_ley.add_widget(Label(text=texto, size_hint_x=None,
                                    width=dp(20) + len(texto) * dp(7),
                                    font_size=sp(11)))
        scroll_ley.add_widget(hb_ley)
        box_main.add_widget(scroll_ley)

        self.scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        self.hbox = BoxLayout(orientation="vertical", size_hint=(None, None),
                              spacing=dp(8))
        self.hbox.bind(minimum_size=self.hbox.setter("size"))
        self.scroll.add_widget(self.hbox)
        box_main.add_widget(self.scroll)

        self.lbl_status = Label(text="", size_hint_y=None, height=dp(22),
                                font_size=sp(10), color=(0.6, 0.6, 0.6, 1),
                                halign="left")
        box_main.add_widget(self.lbl_status)

        titulo = f"{_('Patcheras')} — {nombre_equipo}" if nombre_equipo else _("Patcheras")
        outer = BoxLayout(orientation="vertical")
        outer.add_widget(barra_superior_dialogo(
            titulo, on_atras=lambda: self.dismiss()))
        outer.add_widget(box_main)

        self._zoom = 1.0
        super().__init__(title="", separator_height=0, content=outer,
                         size_hint=(1, 1), **kwargs)
        self._cargar()

    def _cargar(self):
        self._rack_data = _cargar_datos_patcheras(self.id_equipo)

        n_racks = len(self._rack_data)
        n_frames = sum(len(v) for v in self._rack_data.values())
        verdes = sum(1 for rd in self._rack_data.values() for fd in rd.values()
                    for cd in fd.values() if cd.get("A") == "green")
        rojos = sum(1 for rd in self._rack_data.values() for fd in rd.values()
                   for cd in fd.values() if cd.get("B") == "red")
        self.lbl_info.text = (
            f"[b]{n_racks} racks  ·  {n_frames} patcheras[/b]  —  "
            f"[color=22ee44]{verdes} salidas[/color]  "
            f"[color=ff4444]{rojos} entradas[/color]")
        self.lbl_status.text = _("Cargado: {} racks, {} frames PPV/PPA").format(
            n_racks, n_frames)

        self.hbox.clear_widgets()
        self._strips = {}
        for rack_nom in sorted(self._rack_data.keys()):
            cont = BoxLayout(orientation="vertical", size_hint=(None, None),
                            spacing=dp(2))
            strip = _PatcheraStripWidget(rack_nom, self._rack_data[rack_nom])
            strip.on_touch_down = self._gen_click(strip)
            cont.add_widget(strip)
            cont.size = strip.size
            strip.bind(size=lambda inst, val, c=cont: setattr(c, "size", val))
            # una sola columna: cada rack ocupa el ancho completo disponible
            cont.width = self.hbox.width or strip.width
            self.hbox.bind(width=lambda inst, val, c=cont: setattr(c, "width", val))
            self.hbox.add_widget(cont)
            self._strips[rack_nom] = strip

        if not self._rack_data:
            self.lbl_info.text = (
                "[i][color=999999]" +
                _("No se encontraron racks con patcheras conectadas al "
                  "equipo.") + "[/color][/i]")

    def _gen_click(self, strip):
        def _click(touch):
            if not strip.collide_point(*touch.pos):
                return False
            lx, ly = strip.to_widget(touch.x, touch.y, relative=True)
            info = strip.celda_en(lx, ly)
            if info:
                frame_nom, col, row = info
                color = strip.frames[frame_nom].get(
                    col, {"A": "dark", "B": "dark"}).get(row, "dark")
                estado = {"green": _("Salida (A_BACK conectado)"),
                         "red": _("Entrada (B_BACK conectado)"),
                         "dark": _("Sin conexión al equipo")}.get(color, "?")
                self.lbl_status.text = f"{frame_nom}  Col {col:02d}  Fila {row}  —  {estado}"
            return True
        return _click

    def _set_zoom(self, z):
        self._zoom = max(0.3, min(3.0, z))
        self.lbl_zoom.text = f"{int(self._zoom * 100)}%"
        for strip in self._strips.values():
            strip.set_zoom(self._zoom)

    def _exportar_png(self, *_a):
        if not self._rack_data:
            mostrar_error(_("No hay datos de patcheras para exportar"))
            return
        import tempfile
        carpeta = os.path.join(tempfile.gettempdir(), "cabledoc_patcheras")
        os.makedirs(carpeta, exist_ok=True)
        archivos = []
        for rack_nom, strip in self._strips.items():
            nombre_archivo = f"patchera_{rack_nom}.png".replace(" ", "_")
            ruta = os.path.join(carpeta, nombre_archivo)
            strip.export_to_png(ruta)
            archivos.append(ruta)
        mostrar_info(_("Exportado {} imagen(es) PNG a:\n{}").format(
            len(archivos), carpeta))


def abrir_patcheras(id_equipo, nombre_equipo=""):
    PatcherasVista(id_equipo=id_equipo, nombre_equipo=nombre_equipo).open()
