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
import re

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
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
    barra_superior_dialogo, crear_textura_simbolo, dibujar_simbolo_conector_kivy,
    grid_formulario, fila_etiqueta, SpinnerCantidad,
)
from pantallas_avanzadas import PALETA, _ruta_imagen, _ruta_desde_id_imagen
from core.modelo import Modelo, IMG_DIR

# ─── helpers ─────────────────────────────────────────────────────────────────

def _parse_int(texto, default=0):
    """Parseo tolerante de un TextInput a entero: nunca levanta
    excepción (vacío, no numérico, o con decimales de sobra tipo
    "30.0" caen todos al default o se truncan). Mismo criterio que
    widgets_base._parse_mm mencionado en pantallas_equipos.py."""
    texto = (texto or "").strip()
    if not texto:
        return default
    try:
        return int(float(texto))
    except ValueError:
        return default


def _clave_orden_natural(nombre):
    """Clave de orden para nombres de conector tipo '01', '24', 'IN 3',
    etc.: ordena por el último número que aparezca en el nombre (si hay),
    y si no por el texto plano. Port de
    ui_gtk/editor_masivo_conectores_ui.py._clave_orden_natural (Fase 2
    de plan_paneles_vectoriales_v3.md) — usado por la colocación en
    lote para ofrecer un orden ascendente/descendente sensato sin
    depender de que los nombres estén ceropadeados."""
    m = re.search(r"(\d+)(?!.*\d)", nombre or "")
    if m:
        return (0, int(m.group(1)), nombre)
    return (1, 0, (nombre or "").lower())


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


# ═══════════════════════════════════════════════════════════════════════════
#  _DialogoMedicion — herramienta "Medir en la imagen" (Fase 1 de
#  ubicación física en planos, port de ui_gtk/editor_masivo_conectores_ui.py
#  §3.4 de plan_paneles_vectoriales_v3.md)
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoMedicion(Popup):
    """Se abre después de que el usuario tocó dos puntos de referencia
    sobre la imagen (dos toques en modo "Medir en la imagen"). Pide
    cuánto mide esa distancia en la realidad, en mm, y con eso el
    llamador calcula `imagen.mm_por_pixel = mm_reales / distancia_px`
    (fuente 1 de la cascada de calibración — gana siempre sobre
    ancho_mm del equipo y sobre el fallback genérico).

    Equivalente a _DialogoMedicion de editor_masivo_conectores_ui.py
    (GTK). on_aceptar(mm_reales) se llama solo si el usuario confirma
    con un valor > 0.
    """

    def __init__(self, distancia_px, on_aceptar=None, **kwargs):
        self._on_aceptar = on_aceptar

        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        lbl_info = Label(
            text=_("Distancia marcada: {px:.1f} px (píxeles nativos de "
                   "la imagen, no de pantalla).\n"
                   "¿Cuánto mide esa distancia en la realidad, en mm?")
                .format(px=distancia_px),
            size_hint_y=None, height=dp(70), font_size=FUENTE_CHICA,
            halign="left", valign="top")
        lbl_info.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        box.add_widget(lbl_info)

        hbox = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        hbox.add_widget(Label(text=_("Milímetros:"), size_hint_x=None,
                              width=dp(90), font_size=FUENTE_NORMAL))
        self.e_mm = TextInput(text="", multiline=False, input_filter="float",
                              font_size=FUENTE_NORMAL)
        hbox.add_widget(self.e_mm)
        box.add_widget(hbox)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        super().__init__(title=_("Medir en la imagen"), content=box,
                         size_hint=(0.9, None), height=dp(230), **kwargs)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._aceptar)
        self.e_mm.bind(on_text_validate=self._aceptar)

    def _aceptar(self, *_a):
        try:
            v = float(self.e_mm.text.strip() or "0")
        except ValueError:
            v = 0
        self.dismiss()
        if v > 0 and self._on_aceptar:
            self._on_aceptar(v)


# ═══════════════════════════════════════════════════════════════════════════
#  _DialogoColocacionLote — Fase 2 de plan_paneles_vectoriales_v3.md
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoColocacionLote(Popup):
    """Coloca en una sola operación una fila o grilla de conectores del
    mismo tipo, espaciados uniformemente a partir de un punto inicial.
    Pensado para el caso típico de un patchbay de 24 conectores en
    línea: sin esto, hay que tocar cada uno por separado.

    El orden ascendente/descendente cubre la numeración espejada típica
    de patchbays (la fila física va 24→1 en la cara trasera aunque los
    nombres sigan siendo '1'..'24'): se ordena por _clave_orden_natural
    y, si es descendente, se invierte antes de recorrer la grilla.

    No crea conectores nuevos — sólo asigna posición a conectores que ya
    existen en `conectores` (misma lista que usa
    EditorMasivoConectoresImagen), filtrados por tipo y, opcionalmente,
    sólo entre los que todavía no tienen posición. Equivalente a
    _DialogoColocacionLote de ui_gtk/editor_masivo_conectores_ui.py.
    on_colocar(ids_ordenados, columnas, sep_x, sep_y, ix0, iy0) se llama
    solo si el usuario confirma con al menos un conector seleccionado.
    """

    def __init__(self, conectores, pendientes, punto_inicial=None,
                 on_colocar=None, **kwargs):
        # Evaluados acá (no como atributos de clase) porque el idioma
        # puede cambiarse en caliente desde main.py sin reiniciar la
        # app — un atributo de clase quedaría congelado con el _()
        # vigente en el momento en que se importó este módulo, no el
        # vigente cuando se abre el diálogo.
        self._TODOS = _("(todos)")
        self._ASCENDENTE = _("Ascendente (1, 2, 3…)")
        self._DESCENDENTE = _("Descendente (…3, 2, 1)")

        self._conectores = conectores
        self._pendientes = pendientes
        self._on_colocar = on_colocar
        self._seleccionados = []

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(4))
        root.add_widget(barra_superior_dialogo(
            _("Colocar fila / grilla"), on_atras=lambda: self.dismiss()))

        scroll = ScrollView()
        g = grid_formulario(cols=1)

        tipos = sorted({c["tipo"] for c in conectores if c["tipo"]})
        fila_etiqueta(g, _("Tipo de conector:"))
        self.c_tipo = Spinner(text=self._TODOS, values=[self._TODOS] + tipos,
                              size_hint_y=None, height=ALTO_ENTRY,
                              font_size=FUENTE_NORMAL)
        self.c_tipo.bind(text=self._recalcular)
        g.add_widget(self.c_tipo)

        hb_libres = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        self.chk_solo_libres = CheckBox(active=True, size_hint_x=None, width=dp(40))
        self.chk_solo_libres.bind(active=self._recalcular)
        hb_libres.add_widget(self.chk_solo_libres)
        hb_libres.add_widget(Label(text=_("Sólo sin posición"),
                                   font_size=FUENTE_NORMAL, halign="left",
                                   valign="middle"))
        g.add_widget(hb_libres)

        fila_etiqueta(g, _("Orden de numeración:"))
        self.c_orden = Spinner(text=self._ASCENDENTE,
                               values=[self._ASCENDENTE, self._DESCENDENTE],
                               size_hint_y=None, height=ALTO_ENTRY,
                               font_size=FUENTE_CHICA)
        self.c_orden.bind(text=self._recalcular)
        g.add_widget(self.c_orden)

        fila_etiqueta(g, _("Cantidad a colocar:"))
        self.sp_cantidad = SpinnerCantidad(valor=1, minimo=1, maximo=500,
                                           on_change=self._recalcular)
        g.add_widget(self.sp_cantidad)

        fila_etiqueta(g, _("Filas:"))
        self.sp_filas = SpinnerCantidad(valor=1, minimo=1, maximo=100,
                                        on_change=self._recalcular)
        g.add_widget(self.sp_filas)

        fila_etiqueta(g, _("Columnas:"))
        self.sp_columnas = SpinnerCantidad(valor=1, minimo=1, maximo=100,
                                           on_change=self._recalcular)
        g.add_widget(self.sp_columnas)

        ix0, iy0 = punto_inicial or (50, 50)
        fila_etiqueta(g, _("Punto inicial X:"))
        self.e_x0 = TextInput(text=str(ix0), multiline=False,
                              input_filter="int", font_size=FUENTE_NORMAL,
                              size_hint_y=None, height=ALTO_ENTRY)
        g.add_widget(self.e_x0)
        fila_etiqueta(g, _("Punto inicial Y:"))
        self.e_y0 = TextInput(text=str(iy0), multiline=False,
                              input_filter="int", font_size=FUENTE_NORMAL,
                              size_hint_y=None, height=ALTO_ENTRY)
        g.add_widget(self.e_y0)

        fila_etiqueta(g, _("Separación X (px):"))
        self.e_sep_x = TextInput(text="40", multiline=False,
                                 input_filter="int", font_size=FUENTE_NORMAL,
                                 size_hint_y=None, height=ALTO_ENTRY)
        g.add_widget(self.e_sep_x)
        fila_etiqueta(g, _("Separación Y (px):"))
        self.e_sep_y = TextInput(text="40", multiline=False,
                                 input_filter="int", font_size=FUENTE_NORMAL,
                                 size_hint_y=None, height=ALTO_ENTRY)
        g.add_widget(self.e_sep_y)

        self._lbl_preview = Label(
            text="", font_size=sp(10), color=(0.65, 0.65, 0.65, 1),
            halign="left", valign="top", size_hint_y=None, height=dp(50))
        self._lbl_preview.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        g.add_widget(self._lbl_preview)

        scroll.add_widget(g)
        root.add_widget(scroll)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_colocar = Button(text=_("Colocar"), font_size=FUENTE_NORMAL)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_colocar)
        root.add_widget(hb_btn)

        super().__init__(title="", separator_height=0, content=root,
                         size_hint=(1, 1), **kwargs)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_colocar.bind(on_release=self._colocar)
        self._recalcular()

    def _candidatos(self):
        """Conectores que matchean el tipo elegido y (si aplica) que
        todavía no tienen posición, ordenados naturalmente por
        nombre."""
        tipo_sel = self.c_tipo.text
        solo_libres = self.chk_solo_libres.active
        out = []
        for c in self._conectores:
            if tipo_sel and tipo_sel != self._TODOS and c["tipo"] != tipo_sel:
                continue
            if solo_libres and self._pendientes.get(c["id"], {}).get("x"):
                continue
            out.append(c)
        out.sort(key=lambda c: _clave_orden_natural(c["nombre"]))
        return out

    def _recalcular(self, *_a):
        candidatos = self._candidatos()
        max_cant = max(1, len(candidatos))
        self.sp_cantidad.maximo = max_cant
        # Igual que GTK: si la cantidad sigue en "1" (sentinel de "el
        # usuario todavía no la tocó a mano") o quedó por encima del
        # máximo disponible tras cambiar el filtro, saltar directo al
        # máximo — el caso de uso típico es "quiero TODOS los que
        # coincidan con el filtro", no ir subiendo de a uno.
        if self.sp_cantidad.get_value() > max_cant or self.sp_cantidad.get_value() == 1:
            self.sp_cantidad.set_value(max_cant)

        cantidad = self.sp_cantidad.get_value()
        filas = self.sp_filas.get_value()
        cols = self.sp_columnas.get_value()
        # Si la grilla no alcanza para "cantidad", ajustar filas para
        # que sí (mismo criterio que GTK).
        if filas * cols < cantidad:
            filas = -(-cantidad // cols)   # ceil
            self.sp_filas.set_value(filas)

        seleccionados = candidatos[:cantidad]
        if self.c_orden.text == self._DESCENDENTE:
            seleccionados = list(reversed(seleccionados))

        if not candidatos:
            self._lbl_preview.text = _("No hay conectores que coincidan con el filtro.")
        else:
            nombres = ", ".join(c["nombre"] for c in seleccionados[:6])
            if len(seleccionados) > 6:
                nombres += f"… (+{len(seleccionados) - 6})"
            self._lbl_preview.text = _(
                "Se van a posicionar {n} conector(es): {nombres}").format(
                n=len(seleccionados), nombres=nombres)
        self._seleccionados = seleccionados

    def _colocar(self, *_a):
        if not self._seleccionados:
            self.dismiss()
            return
        ids_ordenados = [c["id"] for c in self._seleccionados]
        columnas = self.sp_columnas.get_value()
        sep_x = _parse_int(self.e_sep_x.text, 40)
        sep_y = _parse_int(self.e_sep_y.text, 40)
        ix0 = _parse_int(self.e_x0.text, 0)
        iy0 = _parse_int(self.e_y0.text, 0)
        self.dismiss()
        if self._on_colocar:
            self._on_colocar(ids_ordenados, columnas, sep_x, sep_y, ix0, iy0)


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

        # Fase 3.4b (integración mobile): mismo estado y mismo criterio de
        # activación que ImagenConectoresYCables en pantallas_avanzadas.py
        # (réplica de EditorMasivoConectoresBase._preparar_simbolos_conector
        # de ui_gtk/editor_masivo_conectores_ui.py). "equipo" es la misma
        # _TABLA_DIMENSIONES que usa EditorMasivoConectoresImagen en GTK
        # (EditorMasivoConectoresCatalogo, para moldes de equipo_catalogo,
        # no tiene equivalente en mobile todavía).
        self._TABLA_DIMENSIONES = "equipo"
        self._simbolos_activos = False
        self._texturas_por_tipo = {}
        self._mm_por_pixel = None
        # Herramienta "Medir en la imagen" (Fase 1 — ubicación física en
        # planos), port de _toggle_medir/_on_clic_medir de
        # ui_gtk/editor_masivo_conectores_ui.py. Sin clic derecho en
        # mobile: cancelar la medición en curso es un botón aparte en
        # vez de un segundo tipo de toque.
        self._modo_medir = False
        self._medir_p1 = None
        # "Último click" (Fase 2 — colocación en lote): recuerda el
        # último punto tocado en la imagen, aunque no haya seleccionado
        # ningún conector, para prellenar el "punto inicial" del diálogo
        # de colocación en lote. No se actualiza durante el modo medir.
        self._ultimo_click = None

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

        # "Colocar fila / grilla" — Fase 2 de plan_paneles_vectoriales_v3.md,
        # el mayor ahorro de tiempo real: coloca de una sola vez varios
        # conectores del mismo tipo en vez de tocar uno por uno.
        btn_lote = Button(text=_("▦ Colocar fila / grilla…"),
                          size_hint_y=None, height=ALTO_BOTON,
                          font_size=FUENTE_CHICA)
        btn_lote.bind(on_release=lambda *_a: self._abrir_colocacion_lote())
        root.add_widget(btn_lote)

        # Herramienta "Medir en la imagen" — calibra mm_por_pixel de esta
        # imagen para que los símbolos de conector salgan a su tamaño
        # físico real en vez del tamaño genérico.
        self._btn_medir = Button(text=_("📏 Medir en la imagen…"),
                                 size_hint_y=None, height=ALTO_BOTON,
                                 font_size=FUENTE_CHICA)
        self._btn_medir.bind(on_release=lambda *_a: self._toggle_medir())
        root.add_widget(self._btn_medir)

        self._lbl_medir_estado = Label(
            text="", size_hint_y=None, height=0, font_size=sp(10),
            color=(0.65, 0.65, 0.65, 1))
        root.add_widget(self._lbl_medir_estado)

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
            "c.coordenada_x_en_imagen, c.coordenada_y_en_imagen, "
            "c.id_tipo_ficha "
            "FROM conector c "
            "LEFT JOIN tipo_conector tc "
            "  ON tc.id_tipo_conector=c.id_tipo_conector "
            "LEFT JOIN imagen i ON i.id_imagen=c.id_imagen "
            "WHERE c.id_equipo=? ORDER BY c.nombre",
            (self._id_equipo,))
        # coordenada_x/y_en_imagen se guardan en % (0-100) desde Fase 3.1 —
        # convertir a píxeles acá, una sola vez, antes de precargar los
        # marcadores existentes. Mismo patrón que
        # editor_masivo_conectores_ui.py en desktop.
        cons = [
            (*r[:5], *Modelo._px_punto_o_crudo(r[4] or None, r[5], r[6]), r[7])
            for r in cons
        ]

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
            id_tipo_ficha = r[7] if len(r) > 7 else None
            hex_c  = _color_hex(i)
            self._conectores.append({
                "id": id_con, "nombre": nombre, "tipo": tipo,
                "hex": hex_c, "idx": i, "id_tipo_ficha": id_tipo_ficha,
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
            id_imagen_pred = next(
                (r[3] for r in cons if s(r[4]).strip() == img_pred and r[3]),
                None)
            self._preparar_simbolos_conector(id_imagen_pred)
            self._actualizar_overlay()

    def _preparar_simbolos_conector(self, id_imagen):
        """Precalcula (una sola vez por carga o por cambio de imagen) los
        símbolos con forma real y la calibración de escala — Fase 3.4b de
        la integración mobile, réplica de
        EditorMasivoConectoresBase._preparar_simbolos_conector de
        ui_gtk/editor_masivo_conectores_ui.py. Regla de activación
        idéntica a desktop (§4 del plan): sólo si el fondo es SVG. Si
        algo falla acá, se deja todo desactivado y _dibujar_overlay cae
        al círculo genérico de siempre, sin excepciones visibles."""
        self._simbolos_activos = False
        self._texturas_por_tipo = {}
        self._mm_por_pixel = None
        if not self._visor.es_svg or self._visor.textura is None:
            return
        ancho_px = self._visor.textura.width
        if not ancho_px:
            return
        try:
            self._mm_por_pixel = Modelo.resolver_mm_por_pixel(
                self._TABLA_DIMENSIONES, self._id_equipo, id_imagen, ancho_px)
        except Exception:
            self._mm_por_pixel = None
        tipos = {c["id_tipo_ficha"] for c in self._conectores
                 if c.get("id_tipo_ficha")}
        if not tipos:
            return
        try:
            simbolos = Modelo.obtener_simbolos_conector(list(tipos))
        except Exception:
            simbolos = {}
        for id_tipo, (frag, viewbox, tamano_rel, color) in simbolos.items():
            textura = crear_textura_simbolo(frag, viewbox, color)
            if textura is not None:
                self._texturas_por_tipo[id_tipo] = (textura, tamano_rel or 1.0)
        self._simbolos_activos = bool(self._texturas_por_tipo)

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
        ix, iy = self._visor.w2i(lx, ly)
        # Siempre coordenadas enteras de imagen (independiente de si ya
        # hay textura cargada): _ultimo_click y las coordenadas de
        # conector se guardan como texto entero en toda la pantalla, y
        # un float acá rompería el parseo int() en _DialogoColocacionLote.
        ix, iy = int(round(ix)), int(round(iy))
        if self._visor.textura:
            W = self._visor.textura.width
            H = self._visor.textura.height
            ix = max(0, min(W, ix))
            iy = max(0, min(H, iy))

        if self._modo_medir:
            self._on_clic_medir(ix, iy)
            return

        # Fase 2 de plan_paneles_vectoriales_v3.md: recordar el último
        # punto tocado (aunque no haya conector seleccionado) para
        # prellenar el "punto inicial" de la colocación en lote.
        self._ultimo_click = (ix, iy)

        if not self._sel_id:
            return

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

    # ── Colocación en lote ("Colocar fila / grilla") ────────────────────────────

    def _abrir_colocacion_lote(self):
        """Fase 2 de plan_paneles_vectoriales_v3.md: colocar de una sola
        vez una fila o grilla de conectores del mismo tipo, en vez de
        tocar uno por uno. No requiere que haya imagen elegida para
        abrir el diálogo, pero sí para poder guardar posiciones con
        sentido (la imagen determina el sistema de coordenadas en el
        que se ubican X/Y)."""
        if self._visor.textura is None:
            mostrar_error(_("Elegí una imagen primero."))
            return
        _DialogoColocacionLote(
            self._conectores, self._pendientes,
            punto_inicial=self._ultimo_click,
            on_colocar=self._aplicar_colocacion_lote).open()

    def _aplicar_colocacion_lote(self, ids_ordenados, columnas, sep_x, sep_y,
                                  ix0, iy0):
        img_nombre = self._e_img.text.strip()
        rows = Modelo._query(
            "SELECT id_imagen FROM imagen WHERE path_archivo=?",
            (img_nombre,))
        id_img = str(rows[0][0]) if rows else self._img_id_actual

        for i, id_con in enumerate(ids_ordenados):
            fila_grilla = i // columnas
            col_grilla = i % columnas
            x = ix0 + col_grilla * sep_x
            y = iy0 + fila_grilla * sep_y
            p = self._pendientes[id_con]
            p["x"] = str(int(x))
            p["y"] = str(int(y))
            p["id_imagen"] = id_img
            p["modificado"] = True
            self._actualizar_fila_widget(id_con)

        self._actualizar_overlay()

    # ── Herramienta "Medir en la imagen" ────────────────────────────────────────

    def _toggle_medir(self):
        """Activa/desactiva el modo "Medir en la imagen". Mientras está
        activo, los toques en la imagen no colocan conectores — se usan
        para marcar los dos extremos del segmento a medir."""
        self._modo_medir = not self._modo_medir
        self._medir_p1 = None
        if self._modo_medir:
            self._btn_medir.text = _("✕ Cancelar medición")
            self._lbl_medir_estado.text = _("Tocá el primer punto de referencia…")
            self._lbl_medir_estado.height = dp(18)
        else:
            self._btn_medir.text = _("📏 Medir en la imagen…")
            self._lbl_medir_estado.text = ""
            self._lbl_medir_estado.height = 0
        self._actualizar_overlay()

    def _on_clic_medir(self, ix, iy):
        if self._medir_p1 is None:
            self._medir_p1 = (ix, iy)
            self._lbl_medir_estado.text = _("Tocá el segundo punto de referencia…")
            self._actualizar_overlay()
            return

        x1, y1 = self._medir_p1
        self._medir_p1 = None
        distancia_px = math.hypot(ix - x1, iy - y1)
        self._actualizar_overlay()
        if distancia_px < 1:
            self._lbl_medir_estado.text = _("Tocá el primer punto de referencia…")
            return

        # Igual que en GTK: apagar el modo medición apenas se dispara el
        # diálogo, sin esperar la respuesta (cancelar el diálogo también
        # sale del modo, no reintenta con el mismo primer punto).
        self._modo_medir = False
        self._btn_medir.text = _("📏 Medir en la imagen…")
        self._lbl_medir_estado.text = ""
        self._lbl_medir_estado.height = 0

        def _con_mm(mm_reales):
            img_nombre = self._e_img.text.strip()
            rows = Modelo._query(
                "SELECT id_imagen FROM imagen WHERE path_archivo=?",
                (img_nombre,))
            id_img = str(rows[0][0]) if rows else self._img_id_actual
            if not id_img:
                mostrar_error(_(
                    "No se pudo determinar la imagen actual — elegí una "
                    "imagen guardada antes de calibrar."))
                return

            Modelo.actualizar_mm_por_pixel_imagen(id_img, mm_reales / distancia_px)
            self._preparar_simbolos_conector(id_img)
            self._actualizar_overlay()

        _DialogoMedicion(distancia_px, on_aceptar=_con_mm).open()

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
            self._preparar_simbolos_conector(id_)
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

            # Fase 3.4b (integración mobile): símbolo con forma real si el
            # fondo es SVG y hay un símbolo cargado para este tipo de
            # ficha — mismo criterio que EditorMasivoConectoresBase en
            # GTK. Si no se pudo dibujar, se cae al círculo genérico de
            # siempre (comportamiento sin cambios).
            dibujado = False
            if self._simbolos_activos:
                info = self._texturas_por_tipo.get(c.get("id_tipo_ficha"))
                if info is not None:
                    textura, tamano_rel = info
                    radio_img_px = Modelo.calcular_radio_simbolo_px(
                        tamano_rel, self._mm_por_pixel, radio_default_px=self.R)
                    radio_px = radio_img_px * z
                    dibujado = dibujar_simbolo_conector_kivy(
                        canvas_widget, textura, wx, wy, radio_px)
                    if dibujado and es_sel:
                        with canvas_widget.canvas:
                            Color(1.0, 0.65, 0.0, 1)
                            Line(circle=(wx, wy, radio_px + 3), width=1.5)

            if not dibujado:
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

        # Primer punto marcado de la herramienta "Medir en la imagen",
        # a la espera del segundo toque.
        if self._modo_medir and self._medir_p1:
            wx, wy = canvas_widget.i2w(*self._medir_p1, z)
            with canvas_widget.canvas:
                Color(1, 0.15, 0.15, 0.9)
                Ellipse(pos=(wx - 5, wy - 5), size=(10, 10))
                Color(1, 1, 1, 1)
                Line(circle=(wx, wy, 5), width=1.5)

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
            # rectangulo_*_en_imagen/pixeles se guardan en % (0-100) desde
            # Fase 3.1 — convertir a píxeles acá antes de precargar el
            # rectángulo existente. Mismo patrón que
            # editor_masivo_slots_ui.py en desktop (Modelo._px_rect_o_crudo
            # con el path de imagen del frame, ya resuelto arriba en
            # img_path).
            x, y, w, h = Modelo._px_rect_o_crudo(
                img_path or None, r[3], r[4], r[5], r[6])
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
