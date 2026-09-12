#!/usr/bin/env python3
"""
pantallas_editores_masivos.py — Fase 7: editores masivos de coordenadas.

Equivalente a EditorMasivoConectoresImagen y EditorMasivoSlotsFrame de
pantallas_avanzadas.py (GTK+Cairo).

Diferencias respecto al original GTK:
  - El overlay de marcadores/rectángulos usa kivy.graphics en lugar de Cairo.
  - El selector de imagen abre ImagenesListado en modo selección (patrón
    ya establecido en pantallas_racks.py).
  - El "avance automático al siguiente sin posición" se mantiene.
  - Export: no hay PDF/SVG; se puede exportar el canvas a PNG.
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
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.core.text import Label as CoreLabel
from kivy.clock import Clock
from kivy.metrics import dp, sp

from widgets_base import (
    VisorImagenZoom, mostrar_info, mostrar_error,
    confirmar, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, fila_cerrar_arriba,
    barra_superior_dialogo,
)
from pantallas_avanzadas import PALETA, _ruta_imagen, _ruta_desde_id_imagen
from modelo import Modelo, IMG_DIR

# ─── helpers ─────────────────────────────────────────────────────────────────

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _color_hex(idx):
    c = PALETA[idx % len(PALETA)]
    return "#{:02X}{:02X}{:02X}".format(
        int(c[0]*255), int(c[1]*255), int(c[2]*255))


def _draw_text_centered_on_canvas(canvas, texto, cx, cy, size=9,
                                   color=(1, 1, 1, 1)):
    """Renderiza texto centrado en el canvas usando CoreLabel."""
    lbl = CoreLabel(text=texto, font_size=size, color=color)
    lbl.refresh()
    tex = lbl.texture
    if not tex:
        return
    tw, th = tex.size
    with canvas:
        Color(1, 1, 1, 1)
        Rectangle(texture=tex,
                  pos=(cx - tw / 2, cy - th / 2),
                  size=(tw, th))


class _FilaConector(ButtonBehavior, BoxLayout):
    """Fila cliqueable para la tabla de conectores/slots.

    col_widths: lista opcional de anchos fijos (uno por columna, en dp).
    Si se especifica, la fila pasa a size_hint_x=None (para usarla dentro
    de un ScrollView horizontal — necesario para la tabla de slots, que
    tiene 7 columnas y no entra nunca en 360dp de ancho)."""

    def __init__(self, id_item, columnas_texto, color_fondo,
                 on_click=None, col_widths=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(34), **kwargs)
        self.id_item = id_item
        self._on_click = on_click
        if col_widths:
            self.size_hint_x = None
            self.width = sum(col_widths)
        with self.canvas.before:
            self._c_instr = Color(*color_fondo)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        for i, txt in enumerate(columnas_texto):
            kw = dict(text=s(txt), font_size=FUENTE_CHICA, halign="left",
                     valign="middle", shorten=True, shorten_from="right")
            if col_widths:
                kw["size_hint_x"] = None
                kw["width"] = col_widths[i]
                kw["text_size"] = (col_widths[i] - dp(6), dp(34))
            lbl = Label(**kw)
            if col_widths:
                lbl.bind(size=lambda w, *_a: setattr(
                    w, "text_size", (w.width - dp(6), w.height)))
            self.add_widget(lbl)

    def _upd(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def set_color(self, color):
        self._c_instr.rgba = color

    def on_release(self):
        if self._on_click:
            self._on_click(self)


# ═══════════════════════════════════════════════════════════════════════════
# EditorMasivoConectoresImagen
# ═══════════════════════════════════════════════════════════════════════════

class EditorMasivoConectoresImagen(Popup):
    """
    Equivalente a EditorMasivoConectoresImagen (GTK).

    Permite posicionar todos los conectores de un equipo sobre su imagen
    en una sola sesión:
      1. Seleccionar un conector en la tabla (derecha).
      2. Tocar la imagen (izquierda) → coloca el marcador.
      3. «Guardar» persiste coordenada_x/y e id_imagen en la BD.

    Toque derecho (long-press no disponible en Kivy básico → botón
    "Quitar") quita el marcador del conector seleccionado.
    """

    R = 10  # radio del círculo marcador (en px de imagen, antes del zoom)

    def __init__(self, id_equipo, **kwargs):
        self._id_equipo   = str(id_equipo)
        self._pendientes  = {}   # id_conector → {x, y, id_imagen, modificado}
        self._conectores  = []   # lista ordenada de dicts {id, nombre, tipo, color, hex}
        self._sel_id      = None
        self._img_id_actual = ""

        # ── Layout ──────────────────────────────────────────────────────────
        # En desktop: imagen 62% + tabla 38% lado a lado. En 360dp de
        # ancho eso deja la tabla en ~137dp (4 columnas ilegibles), así
        # que se apila: imagen arriba (grande, para poder tocar con
        # precisión), tabla de conectores + botones abajo.
        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(4))
        root.add_widget(barra_superior_dialogo(
            _("Edición masiva: conectores en imagen"), on_atras=lambda: self.dismiss()))

        top_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        top_img.add_widget(Label(text=_("Imagen:"), size_hint_x=None,
                                  width=dp(60), font_size=FUENTE_CHICA))
        self._e_img = TextInput(text="", multiline=False,
                                font_size=FUENTE_CHICA, readonly=True)
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=lambda *_: self._sel_imagen())
        top_img.add_widget(self._e_img)
        top_img.add_widget(btn_img)
        root.add_widget(top_img)

        self._visor = VisorImagenZoom(size_hint=(1, 0.52))
        self._visor.canvas_widget.on_press_img = self._on_press_img
        root.add_widget(self._visor)

        hint = Label(
            text=_("1. Elegí un conector en la tabla  2. Tocá la imagen"),
            size_hint_y=None, height=dp(18), font_size=sp(10),
            color=(0.65, 0.65, 0.65, 1))
        root.add_widget(hint)

        # Panel de tabla de conectores (ahora ocupa todo el ancho)
        self._lbl_eq = Label(text="", size_hint_y=None, height=dp(24),
                              font_size=FUENTE_CHICA, halign="left",
                              valign="middle", bold=True)
        root.add_widget(self._lbl_eq)

        # Encabezado tabla
        hdr = BoxLayout(size_hint_y=None, height=dp(24))
        for t in [_("Conector"), _("X"), _("Y"), ""]:
            hdr.add_widget(Label(text=t, bold=True, font_size=FUENTE_CHICA))
        root.add_widget(hdr)

        # Scroll tabla
        self._scroll_tabla = ScrollView(do_scroll_x=False, size_hint=(1, 0.30))
        self._box_filas = BoxLayout(orientation="vertical",
                                    size_hint_y=None, spacing=dp(1))
        self._box_filas.bind(minimum_height=self._box_filas.setter("height"))
        self._scroll_tabla.add_widget(self._box_filas)
        root.add_widget(self._scroll_tabla)

        # Botones
        btn_row = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_quitar = Button(text=_("Quitar"), font_size=FUENTE_CHICA)
        btn_quitar.bind(on_release=lambda *_: self._quitar_sel())
        btn_todos  = Button(text=_("Quitar todos"), font_size=FUENTE_CHICA)
        btn_todos.bind(on_release=lambda *_: self._quitar_todos())
        btn_row.add_widget(btn_quitar)
        btn_row.add_widget(btn_todos)
        root.add_widget(btn_row)

        btn_guardar = Button(text=_("Guardar cambios"),
                             size_hint_y=None, height=ALTO_BOTON,
                             font_size=FUENTE_NORMAL)
        btn_guardar.bind(on_release=lambda *_: self._guardar())
        root.add_widget(btn_guardar)

        super().__init__(
            title="", separator_height=0,
            content=root, size_hint=(1, 1), **kwargs)

        self.bind(on_open=lambda *_: Clock.schedule_once(self._cargar, 0.05))

    # ── Carga ─────────────────────────────────────────────────────────────────

    def _cargar(self, *_a):
        rows = Modelo._query(
            "SELECT ve.nombre FROM VISTA_EQUIPOS ve WHERE ve.id=?",
            (self._id_equipo,))
        nombre_eq = s(rows[0][0]) if rows else f"Equipo {self._id_equipo}"
        self._lbl_eq.text = nombre_eq

        cons = Modelo._query(
            "SELECT c.id_conector, c.nombre, COALESCE(tc.nombre,''), "
            "c.id_imagen, COALESCE(i.path_archivo,''), "
            "c.coordenada_x_en_imagen, c.coordenada_y_en_imagen "
            "FROM conector c "
            "LEFT JOIN tipo_conector tc "
            "  ON tc.id_tipo_conector=c.id_tipo_conector "
            "LEFT JOIN imagen i ON i.id_imagen=c.id_imagen "
            "WHERE c.id_equipo=? ORDER BY c.nombre",
            (self._id_equipo,))

        self._conectores = []
        self._pendientes = {}

        # Imagen predominante
        img_paths = {}
        for r in cons:
            p = s(r[4]).strip()
            if p:
                img_paths[p] = img_paths.get(p, 0) + 1
        img_pred = max(img_paths, key=img_paths.get) if img_paths else ""

        for i, r in enumerate(cons):
            id_con = str(r[0])
            nombre = s(r[1]);  tipo = s(r[2])
            id_img = str(r[3]) if r[3] else ""
            path   = s(r[4]).strip()
            x      = str(r[5]) if r[5] is not None else ""
            y      = str(r[6]) if r[6] is not None else ""
            hex_c  = _color_hex(i)
            self._conectores.append({
                "id": id_con, "nombre": nombre, "tipo": tipo,
                "hex": hex_c, "idx": i,
            })
            self._pendientes[id_con] = {
                "x": x, "y": y, "id_imagen": id_img,
                "path": path, "modificado": False,
            }

        self._reconstruir_tabla()

        if img_pred:
            self._e_img.text = img_pred
            ruta = _ruta_imagen(img_pred)
            if ruta:
                self._visor.set_imagen(ruta)
                Clock.schedule_once(lambda *_: self._visor._zoom_fit(), 0.1)
            self._actualizar_overlay()

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _reconstruir_tabla(self):
        self._box_filas.clear_widgets()
        self._filas_widgets = {}
        for c in self._conectores:
            id_con = c["id"]
            p = self._pendientes[id_con]
            self._agregar_fila_widget(c, p)

    def _agregar_fila_widget(self, c, p):
        id_con = c["id"]
        tiene  = bool(p["x"] and p["y"])
        hex_c  = c["hex"]
        rgb    = _hex_to_rgb(hex_c)
        bg     = (*rgb, 0.45) if tiene else (0.15, 0.15, 0.15, 1)
        marca  = "" if tiene else ""
        fila = _FilaConector(
            id_item=id_con,
            columnas_texto=[c["nombre"], p["x"] or "–", p["y"] or "–", marca],
            color_fondo=bg,
            on_click=self._click_fila,
        )
        self._box_filas.add_widget(fila)
        self._filas_widgets[id_con] = fila

    def _click_fila(self, widget):
        # Deselect anterior
        if self._sel_id and self._sel_id in self._filas_widgets:
            c = next((c for c in self._conectores if c["id"] == self._sel_id), None)
            if c:
                p = self._pendientes[self._sel_id]
                tiene = bool(p["x"] and p["y"])
                rgb = _hex_to_rgb(c["hex"])
                bg = (*rgb, 0.45) if tiene else (0.15, 0.15, 0.15, 1)
                self._filas_widgets[self._sel_id].set_color(bg)
        self._sel_id = widget.id_item
        widget.set_color((0.25, 0.45, 0.85, 0.6))
        self._actualizar_overlay()

    def _actualizar_fila_widget(self, id_con):
        fila = self._filas_widgets.get(id_con)
        if not fila:
            return
        c = next((c for c in self._conectores if c["id"] == id_con), None)
        if not c:
            return
        p = self._pendientes[id_con]
        tiene = bool(p["x"] and p["y"])
        fila.clear_widgets()
        marca = "" if tiene else ""
        for txt in [c["nombre"], p["x"] or "–", p["y"] or "–", marca]:
            lbl = Label(text=s(txt), font_size=FUENTE_CHICA,
                       halign="left", valign="middle",
                       shorten=True, shorten_from="right")
            lbl.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
            fila.add_widget(lbl)
        rgb   = _hex_to_rgb(c["hex"])
        bg    = (*rgb, 0.45) if tiene else (0.15, 0.15, 0.15, 1)
        sel_c = (0.25, 0.45, 0.85, 0.6)
        fila.set_color(sel_c if id_con == self._sel_id else bg)

    # ── Interacción imagen ────────────────────────────────────────────────────

    def _on_press_img(self, lx, ly):
        if not self._sel_id:
            return
        ix, iy = self._visor.w2i(lx, ly)
        if self._visor.textura:
            W = self._visor.textura.width
            H = self._visor.textura.height
            ix = max(0, min(W, int(ix)))
            iy = max(0, min(H, int(iy)))

        # id_imagen de la imagen activa
        img_nombre = self._e_img.text.strip()
        rows = Modelo._query(
            "SELECT id_imagen FROM imagen WHERE path_archivo=?",
            (img_nombre,))
        id_img = str(rows[0][0]) if rows else self._img_id_actual

        p = self._pendientes[self._sel_id]
        p["x"]         = str(ix)
        p["y"]         = str(iy)
        p["id_imagen"] = id_img
        p["modificado"] = True
        self._actualizar_fila_widget(self._sel_id)
        self._actualizar_overlay()
        self._avanzar_seleccion()

    def _avanzar_seleccion(self):
        if not self._sel_id:
            return
        idx_actual = next((i for i, c in enumerate(self._conectores)
                           if c["id"] == self._sel_id), -1)
        n = len(self._conectores)
        for offset in range(1, n + 1):
            siguiente = self._conectores[(idx_actual + offset) % n]
            if not self._pendientes[siguiente["id"]]["x"]:
                self._sel_id = siguiente["id"]
                fila = self._filas_widgets.get(self._sel_id)
                if fila:
                    fila.set_color((0.25, 0.45, 0.85, 0.6))
                return

    def _quitar_sel(self):
        if not self._sel_id:
            return
        p = self._pendientes[self._sel_id]
        p["x"] = "";  p["y"] = ""
        p["modificado"] = True
        self._actualizar_fila_widget(self._sel_id)
        self._actualizar_overlay()

    def _quitar_todos(self):
        for id_con, p in self._pendientes.items():
            p["x"] = "";  p["y"] = ""
            p["modificado"] = True
            self._actualizar_fila_widget(id_con)
        self._actualizar_overlay()

    # ── Selector de imagen ────────────────────────────────────────────────────

    def _sel_imagen(self):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_, nombre, fila):
            self._img_id_actual = str(id_)
            nombre_path = s(nombre)
            self._e_img.text = nombre_path
            ruta = _ruta_imagen(nombre_path)
            if ruta:
                self._visor.set_imagen(ruta)
                Clock.schedule_once(lambda *_: self._visor._zoom_fit(), 0.1)
            self._actualizar_overlay()

        ImagenesListado(modo_seleccion=True,
                        on_seleccionar=_con_imagen).open()

    # ── Overlay ───────────────────────────────────────────────────────────────

    def _actualizar_overlay(self):
        def _fn(canvas_widget):
            self._dibujar_overlay(canvas_widget)
        self._visor.set_overlay_fn(_fn)
        self._visor.queue_draw()

    def _dibujar_overlay(self, canvas_widget):
        z   = self._visor.zoom
        R   = self.R * z
        # NO limpiar el canvas ni redibujar el fondo acá: ImagenCanvas._redraw()
        # ya hace canvas.clear() + PushMatrix/Translate + fondo antes de
        # invocar este overlay, y hace PopMatrix() al volver. Si acá adentro
        # se vuelve a limpiar el canvas, se borra ese PushMatrix y el
        # PopMatrix final revienta con "IndexError: list index out of range"
        # (pop_states vacío), lo que tumba el render loop y cierra la app.
        for c in self._conectores:
            id_con = c["id"]
            p = self._pendientes[id_con]
            if not p["x"] or not p["y"]:
                continue
            try:
                ix, iy = int(p["x"]), int(p["y"])
            except ValueError:
                continue
            wx, wy = canvas_widget.i2w(ix, iy, z)
            rgb = _hex_to_rgb(c["hex"])
            es_sel = (id_con == self._sel_id)

            with canvas_widget.canvas:
                # Sombra
                Color(0, 0, 0, 0.35)
                Ellipse(pos=(wx - R + 2, wy - R - 2), size=(R*2, R*2))
                # Círculo relleno
                Color(*rgb, 1)
                Ellipse(pos=(wx - R, wy - R), size=(R*2, R*2))
                # Borde blanco (más grueso si seleccionado)
                Color(1, 1, 1, 1)
                Line(circle=(wx, wy, R),
                     width=2.5 if es_sel else 1.2)
                # Borde naranja si seleccionado
                if es_sel:
                    Color(1.0, 0.65, 0.0, 1)
                    Line(circle=(wx, wy, R + 3), width=1.5)

            _draw_text_centered_on_canvas(
                canvas_widget.canvas,
                c["nombre"][:8],
                wx, wy - R - 8,
                size=max(7, int(9 * z)),
                color=(1, 1, 1, 0.9))

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _guardar(self):
        modificados = 0
        for id_con, p in self._pendientes.items():
            if not p["modificado"]:
                continue
            rows = Modelo.devolver_conector(id_con)
            if not rows:
                continue
            r = rows[0]
            id_imagen = p["id_imagen"] if p["id_imagen"] else s(r[7])
            x = p["x"] if p["x"] else None
            y = p["y"] if p["y"] else None
            Modelo.modificacion_conector(
                id_con, s(r[1]), s(r[4]), s(r[3]), id_imagen, x, y)
            modificados += 1
        mostrar_info(_(f"Se guardaron {modificados} conector(es)."))
        self.dismiss()


# ═══════════════════════════════════════════════════════════════════════════
# EditorMasivoSlotsFrame
# ═══════════════════════════════════════════════════════════════════════════

class EditorMasivoSlotsFrame(Popup):
    """
    Equivalente a EditorMasivoSlotsFrame (GTK).

    Editor visual para definir los rectángulos de los slots de un frame:
      1. Seleccionar un slot en la tabla.
      2. Tocar (coloca rect con tamaño recordado) o arrastrar (tamaño libre).
      3. «Guardar» persiste x/y/ancho/alto en la BD.
    """

    def __init__(self, id_frame, **kwargs):
        self._id_frame   = str(id_frame)
        self._id_imagen  = ""
        self._slots      = {}    # id_slot → dict
        self._slot_ids   = []    # orden
        self._sel_id     = None
        self._last_w     = 80
        self._last_h     = 40
        # estado de arrastre
        self._drag_ini   = None  # (ix, iy) inicio
        self._drag_cur   = None  # (ix, iy) actual
        self._new_count  = 0

        # ── Layout ──────────────────────────────────────────────────────────
        # Igual criterio que EditorMasivoConectoresImagen: imagen arriba
        # (grande), tabla abajo. Acá además la tabla tiene 7 columnas
        # (Slot/Equipo/X/Y/W/H/), así que va con ancho fijo por columna
        # + scroll horizontal (patrón de ListadoPopup).
        self._col_widths = [dp(85), dp(85), dp(46), dp(46), dp(46), dp(46), dp(28)]
        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(4))

        root.add_widget(barra_superior_dialogo(
            _("Edición masiva de slots"), on_atras=lambda: self.dismiss()))
        top_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        top_img.add_widget(Label(text=_("Imagen:"), size_hint_x=None,
                                  width=dp(60), font_size=FUENTE_CHICA))
        self._e_img = TextInput(text="", multiline=False,
                                font_size=FUENTE_CHICA, readonly=True)
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=lambda *_: self._sel_imagen())
        top_img.add_widget(self._e_img)
        top_img.add_widget(btn_img)
        root.add_widget(top_img)

        self._visor = VisorImagenZoom(size_hint=(1, 0.48))
        cw = self._visor.canvas_widget
        cw.on_press_img   = self._on_press_img
        cw.on_motion_img  = self._on_motion_img
        cw.on_release_img = self._on_release_img
        root.add_widget(self._visor)

        self._lbl_size = Label(
            text=self._texto_size(), size_hint_y=None, height=dp(18),
            font_size=sp(10), color=(0.6, 0.6, 0.6, 1), halign="left")
        root.add_widget(self._lbl_size)

        self._lbl_frame = Label(text="", size_hint_y=None, height=dp(24),
                                font_size=FUENTE_CHICA, bold=True, halign="left")
        root.add_widget(self._lbl_frame)

        hint = Label(
            text=_("Toque = tamaño recordado  ·  Arrastre = tamaño libre  ·  scroll lateral"),
            size_hint_y=None, height=dp(18), font_size=sp(10),
            color=(0.55, 0.55, 0.55, 1))
        root.add_widget(hint)

        ancho_total = sum(self._col_widths)
        tabla_scroll = ScrollView(do_scroll_x=True, size_hint=(1, 0.24),
                                  bar_width=dp(4))
        tabla_root = BoxLayout(orientation="vertical", size_hint=(None, None),
                               width=ancho_total, spacing=dp(1))
        tabla_root.bind(minimum_height=tabla_root.setter("height"))

        hdr = BoxLayout(size_hint=(None, None), width=ancho_total, height=dp(24))
        for t, w in zip([_("Slot"), _("Equipo"), "X", "Y", "W", "H", ""],
                        self._col_widths):
            hdr.add_widget(Label(text=t, bold=True, font_size=sp(10),
                                 size_hint=(None, None), width=w, height=dp(24)))
        tabla_root.add_widget(hdr)

        self._box_filas = BoxLayout(orientation="vertical",
                                    size_hint=(None, None), spacing=dp(1),
                                    width=ancho_total)
        self._box_filas.bind(minimum_height=self._box_filas.setter("height"))
        tabla_root.add_widget(self._box_filas)
        tabla_scroll.add_widget(tabla_root)
        root.add_widget(tabla_scroll)

        btn_row = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_nuevo  = Button(text=_("＋ Nuevo slot"), font_size=FUENTE_CHICA)
        btn_nuevo.bind(on_release=lambda *_: self._nuevo_slot())
        btn_quitar = Button(text=_("Quitar rect."), font_size=FUENTE_CHICA)
        btn_quitar.bind(on_release=lambda *_: self._quitar_rect())
        btn_row.add_widget(btn_nuevo)
        btn_row.add_widget(btn_quitar)
        root.add_widget(btn_row)

        btn_guardar = Button(text=_("Guardar cambios"),
                             size_hint_y=None, height=ALTO_BOTON,
                             font_size=FUENTE_NORMAL)
        btn_guardar.bind(on_release=lambda *_: self._guardar())
        root.add_widget(btn_guardar)

        super().__init__(
            title="", separator_height=0,
            content=root, size_hint=(1, 1), **kwargs)

        self.bind(on_open=lambda *_: Clock.schedule_once(self._cargar, 0.05))

    def _texto_size(self):
        return _(f"Tamaño recordado: [b]{self._last_w} × {self._last_h} px[/b]")

    # ── Carga ─────────────────────────────────────────────────────────────────

    def _cargar(self, *_a):
        rows = Modelo._query(
            "SELECT f.nombre, f.id_imagen, COALESCE(i.path_archivo,'') "
            "FROM frame f LEFT JOIN imagen i ON i.id_imagen=f.id_imagen "
            "WHERE f.id_frame=?", (self._id_frame,))
        if not rows:
            return
        nombre_frame   = s(rows[0][0])
        self._id_imagen = str(rows[0][1]) if rows[0][1] else ""
        img_path        = s(rows[0][2])

        self._lbl_frame.text = nombre_frame

        if img_path:
            self._e_img.text = img_path
            ruta = _ruta_imagen(img_path)
            if ruta:
                self._visor.set_imagen(ruta)
                Clock.schedule_once(lambda *_: self._visor._zoom_fit(), 0.1)

        # Slots existentes
        slots_db = Modelo._query(
            "SELECT s.id_slot, s.nombre, COALESCE(e.nombre,''), "
            "s.rectangulo_x_en_imagen, s.rectangulo_y_en_imagen, "
            "s.rectangulo_ancho_pixeles, s.rectangulo_alto_pixeles, s.id_equipo "
            "FROM slot s "
            "LEFT JOIN equipo e ON e.id_equipo=s.id_equipo "
            "WHERE s.id_frame=? ORDER BY s.nombre", (self._id_frame,))

        for i, r in enumerate(slots_db):
            id_slot = str(r[0])
            x = r[3];  y = r[4];  w = r[5];  h = r[6]
            self._agregar_slot_interno(
                id_slot=id_slot, nombre=s(r[1]), equipo=s(r[2]),
                id_equipo=str(r[7]) if r[7] else "",
                x=x, y=y, w=w, h=h, es_nuevo=False, idx=i)

        self._actualizar_overlay()

    def _agregar_slot_interno(self, id_slot, nombre, equipo="",
                               id_equipo="", x=None, y=None,
                               w=None, h=None, es_nuevo=False, idx=None):
        if idx is None:
            idx = len(self._slot_ids)
        hex_c  = _color_hex(idx)
        self._slots[id_slot] = {
            "nombre": nombre, "equipo": equipo, "id_equipo": id_equipo,
            "x": x, "y": y, "w": w, "h": h,
            "hex": hex_c, "es_nuevo": es_nuevo, "modificado": False,
        }
        self._slot_ids.append(id_slot)
        if w and h:
            self._last_w = int(w);  self._last_h = int(h)
        self._agregar_fila_widget(id_slot)

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _agregar_fila_widget(self, id_slot):
        p    = self._slots[id_slot]
        tiene = p["x"] is not None
        rgb  = _hex_to_rgb(p["hex"])
        bg   = (*rgb, 0.45) if tiene else (0.15, 0.15, 0.15, 1)
        marca = "" if tiene else ""
        cols = [p["nombre"], p["equipo"],
                str(p["x"]) if p["x"] is not None else "–",
                str(p["y"]) if p["y"] is not None else "–",
                str(p["w"]) if p["w"] is not None else "–",
                str(p["h"]) if p["h"] is not None else "–",
                marca]
        fila = _FilaConector(
            id_item=id_slot, columnas_texto=cols, col_widths=self._col_widths,
            color_fondo=bg, on_click=self._click_fila)
        self._box_filas.add_widget(fila)
        if not hasattr(self, "_filas_widgets"):
            self._filas_widgets = {}
        self._filas_widgets[id_slot] = fila

    def _click_fila(self, widget):
        if self._sel_id and self._sel_id in self._filas_widgets:
            p   = self._slots[self._sel_id]
            rgb = _hex_to_rgb(p["hex"])
            bg  = (*rgb, 0.45) if p["x"] is not None else (0.15, 0.15, 0.15, 1)
            self._filas_widgets[self._sel_id].set_color(bg)
        self._sel_id = widget.id_item
        widget.set_color((0.25, 0.45, 0.85, 0.6))
        self._actualizar_overlay()

    def _actualizar_fila_widget(self, id_slot):
        fila = self._filas_widgets.get(id_slot)
        if not fila:
            return
        p    = self._slots[id_slot]
        tiene = p["x"] is not None
        rgb  = _hex_to_rgb(p["hex"])
        bg   = (*rgb, 0.45) if tiene else (0.15, 0.15, 0.15, 1)
        marca = "" if tiene else ""
        fila.clear_widgets()
        cols = [p["nombre"], p["equipo"],
                str(p["x"]) if p["x"] is not None else "–",
                str(p["y"]) if p["y"] is not None else "–",
                str(p["w"]) if p["w"] is not None else "–",
                str(p["h"]) if p["h"] is not None else "–",
                marca]
        for txt, w in zip(cols, self._col_widths):
            lbl = Label(text=s(txt), font_size=FUENTE_CHICA,
                       halign="left", valign="middle", shorten=True,
                       shorten_from="right", size_hint_x=None, width=w,
                       text_size=(w - dp(6), dp(34)))
            lbl.bind(size=lambda lw, *_a: setattr(
                lw, "text_size", (lw.width - dp(6), lw.height)))
            fila.add_widget(lbl)
        sel_c = (0.25, 0.45, 0.85, 0.6)
        fila.set_color(sel_c if id_slot == self._sel_id else bg)

    # ── Nuevo slot ────────────────────────────────────────────────────────────

    def _nuevo_slot(self):
        from widgets_base import DialogoNombre

        def _crear(nombre):
            self._new_count += 1
            fake_id = f"NEW_{self._new_count}"
            self._agregar_slot_interno(
                id_slot=fake_id, nombre=nombre,
                es_nuevo=True, idx=len(self._slot_ids))
            # Seleccionar nueva fila
            self._sel_id = fake_id
            fila = self._filas_widgets.get(fake_id)
            if fila:
                fila.set_color((0.25, 0.45, 0.85, 0.6))

        DialogoNombre(titulo=_("Nuevo slot"), etiqueta=_("Nombre:"),
                      on_aceptar=_crear).open()

    def _quitar_rect(self):
        if not self._sel_id or self._sel_id not in self._slots:
            return
        p = self._slots[self._sel_id]
        p["x"] = p["y"] = p["w"] = p["h"] = None
        p["modificado"] = True
        self._actualizar_fila_widget(self._sel_id)
        self._actualizar_overlay()

    # ── Selector de imagen ────────────────────────────────────────────────────

    def _sel_imagen(self):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_, nombre, fila):
            self._id_imagen = str(id_)
            nombre_path = s(nombre)
            self._e_img.text = nombre_path
            ruta = _ruta_imagen(nombre_path)
            if ruta:
                self._visor.set_imagen(ruta)
                Clock.schedule_once(lambda *_: self._visor._zoom_fit(), 0.1)
            # Guardar id_imagen en el frame también
            if self._id_imagen:
                Modelo._exec(
                    "UPDATE frame SET id_imagen=? WHERE id_frame=?",
                    (self._id_imagen, self._id_frame))
            self._actualizar_overlay()

        ImagenesListado(modo_seleccion=True,
                        on_seleccionar=_con_imagen).open()

    # ── Touch sobre imagen ────────────────────────────────────────────────────

    def _on_press_img(self, lx, ly):
        if not self._sel_id:
            return
        ix, iy = self._visor.w2i(lx, ly)
        self._drag_ini = (int(ix), int(iy))
        self._drag_cur = (int(ix), int(iy))

    def _on_motion_img(self, lx, ly):
        if self._drag_ini is None or not self._sel_id:
            return
        ix, iy = self._visor.w2i(lx, ly)
        self._drag_cur = (int(ix), int(iy))
        self._actualizar_overlay()

    def _on_release_img(self, lx, ly):
        if self._drag_ini is None or not self._sel_id:
            return
        ix, iy = self._visor.w2i(lx, ly)
        x0, y0 = self._drag_ini
        dx = abs(int(ix) - x0);  dy = abs(int(iy) - y0)

        if dx < 5 and dy < 5:
            # Toque simple → tamaño recordado centrado
            rx = int(x0 - self._last_w / 2)
            ry = int(y0 - self._last_h / 2)
            rw, rh = self._last_w, self._last_h
        else:
            rx = min(x0, int(ix));  ry = min(y0, int(iy))
            rw = dx;  rh = dy
            self._last_w = rw;  self._last_h = rh
            self._lbl_size.text = self._texto_size()

        p = self._slots[self._sel_id]
        p["x"] = rx;  p["y"] = ry
        p["w"] = rw;  p["h"] = rh
        p["modificado"] = True
        self._drag_ini = None;  self._drag_cur = None
        self._actualizar_fila_widget(self._sel_id)
        self._actualizar_overlay()
        self._avanzar_seleccion()

    def _avanzar_seleccion(self):
        if not self._sel_id:
            return
        try:
            idx_actual = self._slot_ids.index(self._sel_id)
        except ValueError:
            return
        n = len(self._slot_ids)
        for offset in range(1, n + 1):
            nid = self._slot_ids[(idx_actual + offset) % n]
            if self._slots[nid]["x"] is None:
                self._sel_id = nid
                for sid, fw in self._filas_widgets.items():
                    p   = self._slots[sid]
                    rgb = _hex_to_rgb(p["hex"])
                    bg  = (*rgb, 0.45) if p["x"] is not None else (0.15, 0.15, 0.15, 1)
                    fw.set_color((0.25, 0.45, 0.85, 0.6) if sid == nid else bg)
                return

    # ── Overlay ───────────────────────────────────────────────────────────────

    def _actualizar_overlay(self):
        def _fn(canvas_widget):
            self._dibujar_overlay(canvas_widget)
        self._visor.set_overlay_fn(_fn)
        self._visor.queue_draw()

    def _dibujar_overlay(self, canvas_widget):
        z = self._visor.zoom
        # NO limpiar el canvas acá (ver comentario equivalente en
        # EditorMasivoConectoresImagen._dibujar_overlay más arriba).
        for sid in self._slot_ids:
            p = self._slots[sid]
            if p["x"] is None:
                continue
            rgb    = _hex_to_rgb(p["hex"])
            es_sel = (sid == self._sel_id)
            wx1, wy1 = canvas_widget.i2w(p["x"],          p["y"],          z)
            wx2, wy2 = canvas_widget.i2w(p["x"] + p["w"], p["y"] + p["h"], z)
            rw = wx2 - wx1;  rh = wy2 - wy1
            # Invertir si es necesario (coordenadas locales Kivy: y arriba)
            if rh < 0:
                wy1, wy2 = wy2, wy1;  rh = -rh
            if rw < 0:
                wx1, wx2 = wx2, wx1;  rw = -rw

            with canvas_widget.canvas:
                alpha_fill = 0.40 if es_sel else 0.18
                Color(*rgb, alpha_fill)
                Rectangle(pos=(wx1, wy1), size=(rw, rh))
                Color(*rgb, 0.9)
                Line(rectangle=(wx1, wy1, rw, rh),
                     width=2.5 if es_sel else 1.4)
                Color(0, 0, 0, 0.5)
                Line(rectangle=(wx1, wy1, rw, rh), width=0.8)

            _draw_text_centered_on_canvas(
                canvas_widget.canvas,
                p["nombre"][:14],
                wx1 + rw / 2, wy1 + rh / 2,
                size=max(7, int(10 * z)),
                color=(1, 1, 1, 1))

        # Rectángulo en construcción durante arrastre
        if self._drag_ini and self._drag_cur and self._sel_id:
            x0, y0 = self._drag_ini;  x1, y1 = self._drag_cur
            wx0, wy0 = canvas_widget.i2w(min(x0, x1), min(y0, y1), z)
            wx1b, wy1b = canvas_widget.i2w(max(x0, x1), max(y0, y1), z)
            dw = wx1b - wx0;  dh = wy1b - wy0
            if dh < 0: wy0, wy1b = wy1b, wy0; dh = -dh
            if dw < 0: wx0, wx1b = wx1b, wx0; dw = -dw
            with canvas_widget.canvas:
                Color(1, 1, 0, 0.35)
                Rectangle(pos=(wx0, wy0), size=(dw, dh))
                Color(1, 0.8, 0, 0.9)
                Line(rectangle=(wx0, wy0, dw, dh), width=1.8)

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _guardar(self):
        id_img = self._id_imagen or None
        guardados = 0
        for sid in self._slot_ids:
            p = self._slots[sid]
            if not p["modificado"] and not p["es_nuevo"]:
                continue
            nombre    = p["nombre"]
            id_equipo = p["id_equipo"] or None
            x = p["x"];  y = p["y"];  w = p["w"];  h = p["h"]

            if sid.startswith("NEW_"):
                Modelo.agregar_slot_retorna_id(
                    nombre, id_equipo, self._id_frame, id_img, x, y, w, h)
            else:
                Modelo.modificar_slot(
                    sid, nombre, id_equipo, self._id_frame, id_img, x, y, w, h)
            guardados += 1

        mostrar_info(_(f"Se guardaron {guardados} slot(s)."))
        self.dismiss()


# ─── Funciones de conveniencia ────────────────────────────────────────────────

def abrir_editor_masivo_conectores(id_equipo):
    EditorMasivoConectoresImagen(id_equipo=id_equipo).open()


def abrir_editor_masivo_slots(id_frame):
    EditorMasivoSlotsFrame(id_frame=id_frame).open()
