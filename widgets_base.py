"""
CableDoc Kivy - Widgets base reutilizables.

Equivalente a la parte superior de cabledoc.py (GTK):
    - mostrar_error / mostrar_info / confirmar
    - VentanaListado          -> ListadoPopup
    - DialogoNombre           -> DialogoNombre (Popup)
    - _grid/_lbl_entry/_entry/_entry_btn/_searchable_combo -> funciones equivalentes
    - _pack_ultima_edicion

DIFERENCIA CLAVE respecto a GTK
--------------------------------
En GTK, ``Gtk.Dialog.run()`` BLOQUEA hasta que el usuario responde, así que el
código podía escribirse de forma síncrona:

    if dlg.run() == Gtk.ResponseType.OK:
        guardar(dlg.valor)

En Kivy, ``Popup`` (igual que cualquier widget) es SIEMPRE no bloqueante:
``popup.open()`` retorna inmediatamente y el popup se cierra solo cuando el
usuario interactúa. Por lo tanto todo el código se reescribe con callbacks:

    DialogoNombre(titulo="Nueva Marca",
                  on_aceptar=lambda valor: guardar(valor)).open()

Esa es la transformación estructural más importante de toda la migración y
se aplica de forma consistente en todos los módulos.
"""

import os
import re
import math

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.dropdown import DropDown
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.graphics import (
    Color, Rectangle, RoundedRectangle, Line, PushMatrix, PopMatrix, Translate,
)
from kivy.properties import (
    ListProperty, StringProperty, BooleanProperty, NumericProperty,
    ObjectProperty,
)
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp

# ─── Constantes de layout táctil (celular 720×1600 ≈ 360×800 dp) ─────────────
#
# Todo tamaño que antes era un entero "a ojo" (pensado para mouse/escritorio)
# pasa a expresarse en dp/sp para que Kivy lo escale según la densidad real
# del dispositivo, y se agrandan los mínimos táctiles (Android recomienda
# ~48dp de alto para blancos tocables).

ALTO_FILA = dp(44)
ALTO_FILA_COMPACTA = dp(38)
ALTO_BOTON = dp(46)
ALTO_ENTRY = dp(42)
FUENTE_NORMAL = sp(14)
FUENTE_CHICA = sp(12)


def entry_selector(texto="", font_size=None, **kwargs):
    """TextInput de solo lectura para campos que muestran el resultado de
    una selección hecha en un listado ABM (Equipo, Cable, Rack, Marca,
    Imagen, Frame, Sala, etc.), siempre acompañados de un botón «…» que
    abre ese listado. Como el valor nunca se escribe a mano:
      - queda `readonly=True` (no se puede editar tocando el teclado), y
      - se desactiva el comportamiento nativo de selección de texto de
        Android/Kivy (burbuja Cortar/Copiar/Pegar/Seleccionar todo y los
        handles de arrastre), que en un campo de solo lectura no tiene
        sentido y solo tapa la pantalla al mantener presionado.
    """
    kwargs.setdefault("multiline", False)
    return TextInput(text=texto, readonly=True, use_bubble=False,
                     use_handles=False, font_size=font_size or FUENTE_NORMAL,
                     **kwargs)
FUENTE_TITULO = sp(16)
ANCHO_COL_TABLA = dp(130)   # ancho fijo de cada columna en listados (scroll-x)
ANCHO_BOTON_ICONO = dp(46)

from modelo import Modelo

try:
    from i18n import _, set_lang, get_lang, cargar_idioma_guardado, IDIOMAS_DISPONIBLES
    cargar_idioma_guardado()
except ImportError:
    def _(t): return t
    def set_lang(c): pass
    def get_lang(): return "es"
    def cargar_idioma_guardado(): pass
    IDIOMAS_DISPONIBLES = {"es": "Español"}


# ─── Utilidades ──────────────────────────────────────────────────────────────

def s(val):
    """Convierte None/cualquier cosa a cadena segura."""
    return "" if val is None else str(val)


def titulo_con_nombre(titulo, nombre):
    """Agrega el nombre/código del registro al título de una ventana de
    edición (p.ej. "Editar Equipo" -> "Editar Equipo: Switch Core 1"), solo
    si hay un nombre no vacío. Se usa en todos los diálogos "Editar X" para
    que el título muestre qué registro se está editando."""
    nombre = s(nombre).strip()
    return f"{titulo}: {nombre}" if nombre else titulo


from tema import tema

# Valores por defecto (tema claro al momento de importar el módulo). Se
# reasignan en cada apertura de ListadoPopup vía _refrescar_colores_tema()
# para reflejar el modo actual (claro/oscuro) incluso si el usuario lo
# alternó después de que arrancó la app.
COLOR_SELECCION = tema.c("primario")[:3] + (0.20,)
COLOR_FILA_PAR = tema.c("superficie")
COLOR_FILA_IMPAR = tema.c("superficie")
COLOR_HEADER = tema.c("superficie_alt")


def _refrescar_colores_tema():
    global COLOR_SELECCION, COLOR_FILA_PAR, COLOR_FILA_IMPAR, COLOR_HEADER
    COLOR_SELECCION = tema.c("primario")[:3] + (0.20,)
    COLOR_FILA_PAR = tema.c("superficie")
    COLOR_FILA_IMPAR = tema.c("superficie")
    COLOR_HEADER = tema.c("superficie_alt")


tema.bind(modo=lambda *_a: _refrescar_colores_tema())
DOBLE_CLICK_SEG = 0.4
# Tiempo de mantener presionado (hold) para editar una fila en los
# listados ABM. Antes se usaba doble-tap, pero en pantalla táctil es
# fácil de disparar sin querer (al hacer scroll o al retocar para
# corregir la selección); "mantener presionado" es el gesto estándar en
# apps móviles para una acción secundaria sobre una fila.
MANTENER_PRESIONADO_SEG = 0.45
# Tolerancia de movimiento del dedo (en dp) antes de cancelar el
# mantener-presionado, para no disparar "editar" cuando el gesto en
# realidad era el inicio de un scroll de la lista.
MANTENER_PRESIONADO_TOLERANCIA = dp(10)


def agregar_mantener_presionado(widget, callback, seg=MANTENER_PRESIONADO_SEG):
    """Agrega el gesto de 'mantener presionado' (ver MANTENER_PRESIONADO_SEG
    arriba) a CUALQUIER widget, encadenando su on_touch_down/move/up
    original en vez de reemplazarlo — así un TextInput readonly sigue
    recibiendo el touch normalmente (foco, cursor) y además dispara
    `callback()` si el dedo se mantiene quieto `seg` segundos."""
    estado = {"evento": None, "inicio": None}
    _down_orig = widget.on_touch_down
    _move_orig = widget.on_touch_move
    _up_orig = widget.on_touch_up

    def _disparar(_dt):
        estado["evento"] = None
        if hasattr(widget, "cancel_selection"):
            widget.cancel_selection()
        callback()

    def _on_touch_down(touch):
        resultado = _down_orig(touch)
        if widget.collide_point(*touch.pos):
            estado["inicio"] = (touch.x, touch.y)
            estado["evento"] = Clock.schedule_once(_disparar, seg)
        return resultado

    def _on_touch_move(touch):
        if estado["evento"] is not None and estado["inicio"] is not None:
            dx = abs(touch.x - estado["inicio"][0])
            dy = abs(touch.y - estado["inicio"][1])
            if dx > MANTENER_PRESIONADO_TOLERANCIA or dy > MANTENER_PRESIONADO_TOLERANCIA:
                Clock.unschedule(estado["evento"])
                estado["evento"] = None
        return _move_orig(touch)

    def _on_touch_up(touch):
        if estado["evento"] is not None:
            Clock.unschedule(estado["evento"])
            estado["evento"] = None
        return _up_orig(touch)

    widget.on_touch_down = _on_touch_down
    widget.on_touch_move = _on_touch_move
    widget.on_touch_up = _on_touch_up

    # Si es un TextInput (p.ej. campos readonly usados como "etiqueta
    # clickeable"), el propio widget interpreta mantener presionado como
    # "seleccionar texto" y muestra la burbuja nativa con "Select All" /
    # cortar-copiar-pegar, tapando la ventana que abre nuestro callback.
    # Como estos campos son de solo lectura y el mantener-presionado ya
    # tiene un uso propio (abrir el registro relacionado), se desactiva
    # la selección nativa por completo.
    if hasattr(widget, "use_bubble"):
        widget.use_bubble = False
    if hasattr(widget, "use_handles"):
        widget.use_handles = False


def mostrar_error(texto, on_dismiss=None):
    _popup_mensaje(_("Error"), texto, on_dismiss)


def mostrar_info(texto, on_dismiss=None):
    _popup_mensaje(_("Información"), texto, on_dismiss)


def _popup_mensaje(titulo, texto, on_dismiss=None):
    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    lbl = Label(text=texto, halign="center", valign="middle",
                font_size=FUENTE_NORMAL)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    box.add_widget(lbl)
    btn = Button(text=_("Aceptar"), size_hint_y=None, height=ALTO_BOTON,
                font_size=FUENTE_NORMAL)
    box.add_widget(btn)
    popup = Popup(title=titulo, content=box, size_hint=(1, 1),
                   auto_dismiss=False)
    btn.bind(on_release=lambda *_a: popup.dismiss())
    if on_dismiss:
        popup.bind(on_dismiss=lambda *_a: on_dismiss())
    popup.open()
    return popup


def confirmar(texto, on_si=None, on_no=None):
    """Equivalente a confirmar() de GTK pero asíncrono: el resultado llega
    por callback (on_si / on_no) en vez de como valor de retorno."""
    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    lbl = Label(text=texto, halign="center", valign="middle",
                font_size=FUENTE_NORMAL)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    box.add_widget(lbl)
    hb = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
    btn_si = Button(text=_("Sí"), font_size=FUENTE_NORMAL)
    btn_no = Button(text=_("No"), font_size=FUENTE_NORMAL)
    hb.add_widget(btn_no)
    hb.add_widget(btn_si)
    box.add_widget(hb)
    popup = Popup(title=_("Confirmar"), content=box, size_hint=(1, 1),
                   auto_dismiss=False)

    def _si(*_a):
        popup.dismiss()
        if on_si:
            on_si()

    def _no(*_a):
        popup.dismiss()
        if on_no:
            on_no()

    btn_si.bind(on_release=_si)
    btn_no.bind(on_release=_no)
    popup.open()
    return popup


# ─── Fila reciclable para ListadoPopup (RecycleView) ─────────────────────────
#
# Antes cada fila visible del listado era un _FilaTabla creado de una sola
# vez (con su canvas, sus binds y sus Labels de ancho fijo), y todas se
# metían en un BoxLayout dentro de un ScrollView. Con listados grandes
# (Conexiones, Equipos) eso hacía que abrir el popup tardara varios
# segundos: se construían widgets para filas que ni entraban en pantalla.
#
# _FilaRV + RecycleView solo crean los widgets de fila que entran en el
# viewport (+ margen) y los reciclan al hacer scroll, sea el listado de
# 10 o de 10.000 filas. Mantiene el mismo ancho fijo por columna
# (self.ancho_columna) que usaba _FilaTabla para el scroll horizontal.

class _FilaRV(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    fila_id = StringProperty("")
    textos = ListProperty([])
    bg_color = ListProperty([0, 0, 0, 0])
    index = NumericProperty(0)
    popup_ref = ObjectProperty(None, allownone=True)
    ancho_columna = NumericProperty(ANCHO_COL_TABLA)

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.size_hint = (None, None)
        self.height = ALTO_FILA
        with self.canvas.before:
            self._color_instr = Color(*self.bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(10)])
            self._c_borde = Color(*tema.c("borde"))
            self._borde = Line(rounded_rectangle=(*self.pos, *self.size,
                                                   dp(10)), width=1)
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect,
                  bg_color=self._actualizar_color)
        tema.bind(modo=lambda *_a: setattr(self._c_borde, "rgba",
                                           tema.c("borde")))
        self._ultimo_click = 0
        # Estado del gesto "mantener presionado" (reemplaza al doble-tap
        # para abrir editar). Ver comentario en MANTENER_PRESIONADO_SEG.
        self._ev_mantener = None
        self._mantener_disparado = False
        self._touch_inicio = None

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.fila_id = data.get("fila_id", "")
        self.bg_color = data.get("bg_color", (0, 0, 0, 0))
        self.popup_ref = data.get("popup_ref")
        self.ancho_columna = data.get("ancho_columna", ANCHO_COL_TABLA)
        self.textos = data.get("textos", [])
        self._reconstruir_labels()
        return super().refresh_view_attrs(rv, index, data)

    def _reconstruir_labels(self):
        self.clear_widgets()
        for i, t in enumerate(self.textos):
            es_titulo = (i == 0)
            lbl = Label(text=s(t), shorten=True, shorten_from="right",
                       halign="left", valign="middle",
                       font_size=FUENTE_NORMAL if es_titulo else FUENTE_CHICA,
                       bold=es_titulo,
                       color=tema.c("texto") if es_titulo
                             else tema.c("texto_sub"),
                       size_hint=(None, None),
                       width=self.ancho_columna, height=ALTO_FILA,
                       text_size=(self.ancho_columna - dp(10), ALTO_FILA),
                       padding=(dp(6), 0))
            # Nota: el text_size también se fija al crear el Label (no solo
            # en el bind) porque el ancho ya llega fijo por kwargs; un bind
            # agregado después de __init__ no se dispara para el valor que
            # ya trajo el widget al nacer, y sin text_size el halign="left"
            # y el shorten (recorte con "…") quedan sin efecto y el texto
            # largo se dibuja centrado y sin cortar, tapando la columna
            # siguiente.
            lbl.bind(size=lambda lw, *_a: setattr(
                lw, "text_size", (lw.width - dp(10), lw.height)))
            self.add_widget(lbl)

    def _actualizar_rect(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._borde.rounded_rectangle = (*self.pos, *self.size, dp(10))

    def _actualizar_color(self, *_a):
        self._color_instr.rgba = self.bg_color

    # ── Gesto "mantener presionado" → editar ──
    # Un tap simple solo selecciona la fila (igual que antes). Mantener
    # el dedo apoyado MANTENER_PRESIONADO_SEG segundos abre directamente
    # Editar (o confirma la selección en modo_seleccion), reemplazando al
    # doble-tap que antes cumplía esa función.
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._mantener_disparado = False
            self._touch_inicio = (touch.x, touch.y)
            self._ev_mantener = Clock.schedule_once(
                self._disparar_mantener, MANTENER_PRESIONADO_SEG)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._ev_mantener is not None and self._touch_inicio is not None:
            dx = abs(touch.x - self._touch_inicio[0])
            dy = abs(touch.y - self._touch_inicio[1])
            if dx > MANTENER_PRESIONADO_TOLERANCIA or dy > MANTENER_PRESIONADO_TOLERANCIA:
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
        if self.popup_ref:
            self.popup_ref._click_fila_id(self.fila_id)
            self.popup_ref._mantener_fila_id(self.fila_id)

    def on_release(self):
        if not self.popup_ref:
            return
        if self._mantener_disparado:
            # La acción ya se disparó al mantener presionado; el "release"
            # que sigue no debe volver a interpretarse como un tap.
            self._mantener_disparado = False
            return
        self.popup_ref._click_fila_id(self.fila_id)


class _BoxFilasCompat:
    """Shim con la interfaz mínima (solo clear_widgets()) que necesitan las
    subclases de ListadoPopup que reimplementan _refiltrar() a mano
    (EquiposListado, FramesListado). Vacía los datos del RecycleView en
    vez de un BoxLayout real."""

    def __init__(self, popup):
        self._popup = popup

    def clear_widgets(self):
        self._popup._rv_data = []
        self._popup.rv.data = []


class _OverlayCarga(BoxLayout):
    """Overlay semitransparente con 'Cargando…' sobre un ListadoPopup
    mientras se ejecuta cargar_datos()."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", size_hint=(1, 1),
                         pos_hint={"x": 0, "y": 0}, **kwargs)
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizar, size=self._actualizar)
        self.add_widget(BoxLayout())
        self.add_widget(Label(text=_("Cargando…"), font_size=sp(16),
                              color=(1, 1, 1, 1), size_hint_y=None,
                              height=dp(30)))
        self.add_widget(BoxLayout())
        self.opacity = 0
        self.disabled = True

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def mostrar(self):
        self.opacity = 1
        self.disabled = True

    def ocultar(self):
        self.opacity = 0
        self.disabled = False


# ─── Listado genérico (equivalente a VentanaListado) ─────────────────────────

class ListadoPopup(Popup):
    """
    Popup de listado genérico con filtro, tabla de filas y botones CRUD.
    Equivalente a VentanaListado (GTK).

    Subclases deben implementar:
        cargar_datos(self)   -> llama a self._poblar(filas)
        nuevo(self)          -> abre diálogo y al aceptar llama self.cargar_datos()
        editar(self, id_)    -> idem
        eliminar(self, id_)  -> operación sobre Modelo (síncrona)
    """

    def __init__(self, titulo, columnas, modo_seleccion=False,
                 botones_extra=None, on_seleccionar=None,
                 ancho_columna=None, **kwargs):
        self.columnas = columnas
        self.modo_seleccion = modo_seleccion
        self.resultado_id = None
        self.resultado_nombre = None
        self._on_seleccionar_cb = on_seleccionar
        self._filas_completas = []      # todas las filas (de cargar_datos)
        self._colores_extra = {}        # id (str) -> color de fondo
        self._fila_widget_sel = None
        self._fila_sel_datos = None
        # Ancho fijo por columna: en una pantalla angosta (360dp) una tabla
        # de 5-7 columnas no entra comprimida y legible a la vez, así que
        # cada columna tiene un ancho mínimo fijo y la tabla completa se
        # desplaza horizontalmente (scroll-x) en vez de aplastar el texto.
        self.ancho_columna = ancho_columna or ANCHO_COL_TABLA
        self._n_cols_visibles = max(1, len(self.columnas) - 1)
        self._ancho_tabla = self.ancho_columna * self._n_cols_visibles

        contenido = BoxLayout(orientation="vertical", spacing=dp(4),
                             padding=dp(6))
        contenido.add_widget(barra_superior_dialogo(
            titulo, on_atras=lambda: self.dismiss()))

        # Barra de filtro (alto táctil, ocupa todo el ancho disponible)
        hb_filtro = BoxLayout(size_hint_y=None, height=ALTO_ENTRY,
                             spacing=dp(6))
        hb_filtro.add_widget(Label(text=_("Filtro:"), size_hint_x=None,
                                   width=dp(56), font_size=FUENTE_CHICA))
        self.entry_filtro = TextInput(multiline=False, size_hint_y=None,
                                      height=ALTO_ENTRY, font_size=FUENTE_NORMAL)
        self.entry_filtro.bind(text=lambda *_a: self._refiltrar())
        hb_filtro.add_widget(self.entry_filtro)
        contenido.add_widget(hb_filtro)

        # Contenedor para filtros extra (ej. radios de estado en Cables).
        # En celular estos filtros suelen no entrar en una sola fila, así
        # que este contenedor se deja como BoxLayout vertical: cada
        # pantalla que agrega filtros extra puede apilarlos en varias
        # filas internas si hace falta (ver pantallas_cables.py/equipos.py).
        self.box_filtros_extra = BoxLayout(orientation="vertical",
                                           size_hint_y=None, height=0,
                                           spacing=dp(2))
        contenido.add_widget(self.box_filtros_extra)

        # Aviso de scroll horizontal (ayuda de UX en pantalla táctil chica)
        if self._n_cols_visibles > 2:
            contenido.add_widget(Label(
                text=_("Deslizá para ver más columnas"),
                size_hint_y=None, height=dp(18), font_size=sp(10),
                color=(0.55, 0.55, 0.55, 1)))

        # Leyenda de gestos: tap simple selecciona, mantener presionado
        # abre Editar (o confirma selección en modo_seleccion). Reemplaza
        # al doble-tap, poco confiable en pantalla táctil.
        texto_leyenda = (_("Toque: seleccionar") + "   ·   " +
                         (_("Mantener presionado: elegir")
                          if self.modo_seleccion
                          else _("Mantener presionado: editar")))
        contenido.add_widget(Label(
            text=texto_leyenda, size_hint_y=None, height=dp(18),
            font_size=sp(10), color=(0.55, 0.55, 0.55, 1)))

        # Tabla: header con scroll horizontal sincronizado (queda fijo
        # verticalmente) + RecycleView virtualizado para las filas. Antes
        # todas las filas visibles se creaban como widgets reales de una
        # sola vez (incluso las que no entraban en pantalla); con listados
        # grandes (Conexiones, Equipos) eso hacía que abrir el popup
        # tardara varios segundos. RecycleView solo instancia los widgets
        # de fila que entran en el viewport + un margen, y los recicla al
        # hacer scroll, sin importar si hay 100 o 10.000 filas.
        self.header_scroll = ScrollView(do_scroll_x=True, do_scroll_y=False,
                                        size_hint_y=None, height=ALTO_FILA,
                                        bar_width=0)
        self.box_header = BoxLayout(size_hint=(None, None),
                                    width=self._ancho_tabla, height=ALTO_FILA)
        self.header_scroll.add_widget(self.box_header)
        self._construir_header()
        contenido.add_widget(self.header_scroll)

        self.rv = RecycleView(do_scroll_x=True, do_scroll_y=True,
                              bar_width=dp(6), scroll_type=["bars", "content"])
        self._rv_data = []
        _layout = RecycleBoxLayout(
            default_size=(self._ancho_tabla, ALTO_FILA),
            default_size_hint=(None, None), size_hint=(None, None),
            orientation="vertical", spacing=dp(6), padding=(0, dp(4)))
        _layout.width = self._ancho_tabla
        _layout.bind(minimum_height=_layout.setter("height"))
        self.rv.add_widget(_layout)
        # IMPORTANTE: viewclass se asigna al layout_manager (RecycleView.
        # viewclass es un AliasProperty que proxea a self.layout_manager.
        # viewclass), así que hay que setearlo DESPUÉS de add_widget(); si
        # se hace antes, self.layout_manager todavía es None y la
        # asignación se pierde en silencio (no tira error, pero no
        # aparece ninguna fila en pantalla).
        self.rv.viewclass = _FilaRV
        self.rv.bind(scroll_x=lambda _inst, val:
                     setattr(self.header_scroll, "scroll_x", val))
        contenido.add_widget(self.rv)
        # Compat: subclases que reimplementan _refiltrar() a mano
        # (EquiposListado, FramesListado) llaman box_filas.clear_widgets().
        self.box_filas = _BoxFilasCompat(self)

        # Botones: se apilan en 2 filas si hay muchos, para no achicarse
        # de más en 360dp de ancho.
        box_botones = BoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(4))
        fila1 = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(4))
        self.btn_agregar = Button(text=_("Agregar"), font_size=FUENTE_CHICA)
        self.btn_editar = Button(text=_("Editar"), font_size=FUENTE_CHICA)
        self.btn_eliminar = Button(text=_("Eliminar"), font_size=FUENTE_CHICA)
        self.btn_agregar.bind(on_release=lambda *_a: self.nuevo())
        self.btn_editar.bind(on_release=self._on_editar)
        self.btn_eliminar.bind(on_release=self._on_eliminar)
        fila1.add_widget(self.btn_agregar)
        fila1.add_widget(self.btn_editar)
        fila1.add_widget(self.btn_eliminar)
        box_botones.add_widget(fila1)
        n_filas_botones = 1

        extra_widgets = []
        if botones_extra:
            for lbl, cb in botones_extra:
                b = Button(text=lbl, font_size=FUENTE_CHICA)
                b.bind(on_release=lambda inst, c=cb: c())
                extra_widgets.append(b)
        if self.modo_seleccion:
            self.btn_seleccionar = Button(text=_("Seleccionar"),
                                          font_size=FUENTE_CHICA)
            self.btn_seleccionar.bind(on_release=self._on_seleccionar)
            extra_widgets.append(self.btn_seleccionar)

        # Máximo 2 botones extra por fila para que no se compriman.
        for i in range(0, len(extra_widgets), 2):
            fila = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(4))
            for b in extra_widgets[i:i + 2]:
                fila.add_widget(b)
            box_botones.add_widget(fila)
            n_filas_botones += 1

        box_botones.height = ALTO_BOTON * n_filas_botones + dp(4) * (n_filas_botones - 1)
        contenido.add_widget(box_botones)

        raiz = FloatLayout()
        contenido.size_hint = (1, 1)
        contenido.pos_hint = {"x": 0, "y": 0}
        raiz.add_widget(contenido)
        self._overlay_carga = _OverlayCarga()
        raiz.add_widget(self._overlay_carga)

        super().__init__(title="", separator_height=0, content=raiz,
                         size_hint=(1, 1), **kwargs)
        self.bind(on_open=self._bind_teclado)
        self.bind(on_dismiss=self._desbind_teclado)

        self._cargar_datos_real = self.cargar_datos
        self.cargar_datos = self._cargar_datos_con_espera

    def _cargar_datos_con_espera(self, *args, **kwargs):
        self._overlay_carga.mostrar()

        def _hacer(_dt):
            try:
                self._cargar_datos_real(*args, **kwargs)
            finally:
                self._overlay_carga.ocultar()

        Clock.schedule_once(_hacer, 0.05)

    # ── Teclado: Alt+A/E/R y Escape (equivalente a _on_tecla de GTK) ──
    def _bind_teclado(self, *_a):
        Window.bind(on_key_down=self._on_tecla)

    def _desbind_teclado(self, *_a):
        Window.unbind(on_key_down=self._on_tecla)

    def _on_tecla(self, window, key, scancode, codepoint, modifiers):
        if key == 27:  # Escape
            self.dismiss()
            return True
        if "alt" in modifiers:
            if codepoint == "a":
                self.nuevo(); return True
            elif codepoint == "e":
                self._on_editar(); return True
            elif codepoint == "r":
                self._on_eliminar(); return True
        return False

    # ── Encabezado ──
    def _construir_header(self):
        self.box_header.clear_widgets()
        for i, titulo_col in enumerate(self.columnas):
            if i == 0:
                continue  # columna ID oculta, igual que en GTK
            lbl = Label(text=titulo_col, bold=True, halign="left",
                       valign="middle", font_size=FUENTE_NORMAL,
                       size_hint=(None, None),
                       width=self.ancho_columna, height=ALTO_FILA,
                       text_size=(self.ancho_columna - dp(10), ALTO_FILA),
                       shorten=True, shorten_from="right",
                       padding=(dp(6), 0))
            lbl.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width - dp(10), w.height)))
            with lbl.canvas.before:
                Color(*COLOR_HEADER)
                rect = Rectangle(pos=lbl.pos, size=lbl.size)
            lbl.bind(pos=lambda w, *_a, r=rect: setattr(r, "pos", w.pos),
                     size=lambda w, *_a, r=rect: setattr(r, "size", w.size))
            self.box_header.add_widget(lbl)

    # ── Población de filas ──
    def _poblar(self, filas, ids_resaltar=None, color_resaltar=(0.78, 0.65, 0, 0.5)):
        """Guarda las filas y reconstruye la tabla visible (con filtro aplicado)."""
        ids_set = set(str(i) for i in ids_resaltar) if ids_resaltar else set()
        self._colores_extra = {}
        n = len(self.columnas)
        filas_norm = []
        for f in filas:
            fila = [s(v) for v in list(f)[:n]]
            while len(fila) < n:
                fila.append("")
            filas_norm.append(fila)
            if ids_set and fila[0] in ids_set:
                self._colores_extra[fila[0]] = color_resaltar
        self._filas_completas = filas_norm
        self._refiltrar()

    def _refiltrar(self):
        txt = self.entry_filtro.text.lower()
        self.box_filas.clear_widgets()
        self._fila_widget_sel = None
        self._fila_sel_datos = None
        visibles = 0
        for fila in self._filas_completas:
            if txt and not any(txt in v.lower() for v in fila):
                continue
            self._agregar_widget_fila(fila, visibles)
            visibles += 1
        self._rv_refrescar()

    def _agregar_widget_fila(self, fila, indice):
        """Agrega una fila a los datos del RecycleView (no crea el widget
        acá: Kivy solo instancia los widgets de las filas visibles)."""
        columnas_visibles = fila[1:] if len(fila) > 1 else fila
        color = self._colores_extra.get(fila[0])
        if color is None:
            color = COLOR_FILA_IMPAR if indice % 2 else COLOR_FILA_PAR
        self._rv_data.append({
            "fila_id": fila[0],
            "textos": list(columnas_visibles),
            "bg_color": (COLOR_SELECCION if fila[0] == self._id_seleccionado()
                        else color),
            "_color_base": color,
            "ancho_columna": self.ancho_columna,
            "popup_ref": self,
        })

    def _rv_refrescar(self):
        # OJO: RecycleView.data es una Property de Kivy; si se le reasigna
        # el MISMO objeto lista (aunque sus dicts internos se hayan
        # mutado in-place), Kivy considera que "no cambió" y NO vuelve a
        # llamar refresh_view_attrs en los widgets ya instanciados — la
        # fila seleccionada podía quedar sin pintar hasta que el scroll
        # forzaba un reciclado. Por eso siempre se reasigna una lista
        # nueva (ver _click_fila_id).
        self.rv.data = self._rv_data

    def _id_seleccionado(self):
        return self._fila_sel_datos[0] if self._fila_sel_datos else None

    def _click_fila_id(self, fila_id):
        # Recalcula colores (des-selecciona la anterior, pinta la nueva)
        # armando una lista NUEVA con dicts NUEVOS para las filas que
        # cambian de color, en vez de mutar self._rv_data in-place: así
        # Kivy detecta la diferencia de valor y repinta de verdad.
        nueva_data = []
        for d in self._rv_data:
            if d["fila_id"] == fila_id:
                color_nuevo = COLOR_SELECCION
                self._fila_sel_datos = [d["fila_id"]] + list(d["textos"])
            elif d["bg_color"] == COLOR_SELECCION:
                color_nuevo = d["_color_base"]
            else:
                color_nuevo = d["bg_color"]
            if color_nuevo != d["bg_color"]:
                d = dict(d)
                d["bg_color"] = color_nuevo
            nueva_data.append(d)
        self._fila_widget_sel = fila_id
        self._rv_data = nueva_data
        self._rv_refrescar()

    def _color_de(self, fila_id):
        return self._colores_extra.get(fila_id, COLOR_FILA_PAR)

    def _mantener_fila_id(self, fila_id):
        """Se dispara al mantener presionada una fila (reemplaza al
        doble-tap): confirma selección en modo_seleccion, o abre Editar."""
        if self.modo_seleccion:
            self._on_seleccionar()
        else:
            self._on_editar()

    def _fila(self):
        return self._fila_sel_datos

    # ── Acciones ──
    def _on_editar(self, *_a):
        f = self._fila()
        if f:
            self.editar(f[0])

    def _on_eliminar(self, *_a):
        f = self._fila()
        if not f:
            return

        def _hacer():
            try:
                self.eliminar(f[0])
                self.cargar_datos()
            except Exception as e:
                mostrar_error(f"Error al eliminar:\n{e}")

        confirmar(_("¿Borrar el registro ID={}?").format(f[0]), on_si=_hacer)

    def _on_seleccionar(self, *_a):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[1] if len(f) > 1 else ""
            if self._on_seleccionar_cb:
                self._on_seleccionar_cb(self.resultado_id, self.resultado_nombre, f)
            self.dismiss()

    # ── A implementar en subclases ──
    def cargar_datos(self):
        raise NotImplementedError

    def nuevo(self):
        raise NotImplementedError

    def editar(self, id_):
        raise NotImplementedError

    def eliminar(self, id_):
        raise NotImplementedError


# ─── Diálogo simple de nombre (Marcas, Tipos, etc.) ──────────────────────────

class DialogoNombre(Popup):
    """Diálogo genérico para entidades con un solo campo 'nombre'.
    on_aceptar(valor) se llama solo si el usuario confirma con un valor no vacío.
    """

    def __init__(self, titulo, etiqueta=None, valor="", on_aceptar=None, **kwargs):
        etiqueta = etiqueta or _("Nombre:")
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        # En pantalla angosta, etiqueta arriba y campo abajo (apilado) en
        # vez de lado a lado, para que el TextInput tenga ancho completo.
        box.add_widget(Label(text=etiqueta, size_hint_y=None, height=dp(24),
                             font_size=FUENTE_NORMAL, halign="left"))
        self.entry = TextInput(text=valor, multiline=False,
                              size_hint_y=None, height=ALTO_ENTRY,
                              font_size=FUENTE_NORMAL)
        box.add_widget(self.entry)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)
        self._on_aceptar = on_aceptar
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._aceptar)
        self.entry.bind(on_text_validate=self._aceptar)

    def _aceptar(self, *_a):
        valor = self.entry.text.strip()
        if valor and self._on_aceptar:
            self._on_aceptar(valor)
        self.dismiss()


# ─── Helpers para construcción de formularios ─────────────────────────────────

def grid_formulario(cols=1, **kwargs):
    """Grilla de formulario. En celular (360dp de ancho) el default pasa
    a ser 1 columna (etiqueta arriba, campo abajo) — 2 o 3 columnas
    comprimen demasiado los TextInput para tocar con el dedo. Las
    pantallas que todavía piden cols=2/3 explícitamente siguen
    funcionando, pero se recomienda migrarlas a 1.
    """
    g = GridLayout(cols=cols, spacing=dp(6), padding=dp(8), size_hint_y=None)
    g.bind(minimum_height=g.setter("height"))
    return g


def seccion_tarjeta(titulo, contenido, icono=None):
    """Envuelve `contenido` (cualquier widget, típicamente el resultado
    de grid_formulario) en una Tarjeta con encabezado — el patrón de
    'card con título' de las pantallas de detalle del rediseño 2.0
    (Datos, Especificaciones, Notas, etc.). No reemplaza el widget de
    contenido, solo lo empaqueta: las pantallas existentes siguen
    llenando/leyendo sus TextInput/ComboBuscable igual que antes.
    """
    from tema import tema, Tarjeta, IconoImg
    box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
    box.bind(minimum_height=box.setter("height"))
    hdr = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6),
                    padding=(dp(4), 0))
    if icono:
        hdr.add_widget(IconoImg(icono, clave_color="primario",
                                size_hint=(None, None), size=(dp(16), dp(16))))
    hdr.add_widget(Label(text=titulo, bold=True, font_size=FUENTE_CHICA,
                         color=tema.c("texto_sub"), halign="left",
                         valign="middle"))
    box.add_widget(hdr)
    tarjeta = Tarjeta(orientation="vertical", size_hint_y=None,
                      padding=dp(2))
    tarjeta.bind(minimum_height=tarjeta.setter("height"))
    contenido.size_hint_y = None
    tarjeta.add_widget(contenido)
    tarjeta.height = contenido.height
    contenido.bind(height=lambda w, v: setattr(tarjeta, "height", v))
    box.add_widget(tarjeta)
    return box


def fila_etiqueta(grid, texto):
    grid.add_widget(Label(text=texto, halign="left", valign="middle",
                          font_size=FUENTE_NORMAL, size_hint_y=None,
                          height=dp(24)))


def fila_entry(grid, valor="", multiline=False, height=None):
    e = TextInput(text=s(valor), multiline=multiline, size_hint_y=None,
                 height=height or ALTO_ENTRY, font_size=FUENTE_NORMAL)
    grid.add_widget(e)
    return e


class ComboBuscable(BoxLayout):
    """
    Equivalente al ComboBox con entrada de texto y autocompletado de GTK
    (_searchable_combo). Es un TextInput + botón que despliega un DropDown
    con las opciones filtradas a medida que se escribe.

    datos: lista de tuplas (id, nombre)
    """

    def __init__(self, datos=None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", ALTO_ENTRY)
        super().__init__(orientation="horizontal", spacing=dp(4), **kwargs)
        self.datos = list(datos or [])
        # Copia de respaldo del último set de datos "completo" cargado
        # (p.ej. los conectores de un equipo recién elegido). La usan
        # pantallas como EditorConexionesRapidas para poder limpiar la
        # selección de conector sin perder la lista de opciones vigente.
        self._datos_originales = list(datos or [])
        self.id_seleccionado = ""
        self.entry = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.btn = Button(text="v", size_hint_x=None, width=ANCHO_BOTON_ICONO,
                         font_size=FUENTE_NORMAL)
        self.add_widget(self.entry)
        self.add_widget(self.btn)
        self._dropdown = DropDown(auto_width=False)
        self.btn.bind(on_release=self._abrir_dropdown)
        self.entry.bind(text=self._on_texto_cambia)
        self._actualizando = False

    def set_datos(self, datos):
        self.datos = list(datos or [])
        self._datos_originales = list(datos or [])

    def repoblar(self, datos):
        """Reemplaza la lista de opciones (p.ej. al elegir un equipo nuevo,
        los conectores de ese equipo) y limpia la selección/texto actual.
        Equivalente a llamar set_datos() + limpiar entry.text/id_seleccionado
        a mano, que es lo que hacían otras pantallas del proyecto."""
        self.set_datos(datos)
        self._actualizando = True
        self.entry.text = ""
        self._actualizando = False
        self.id_seleccionado = ""

    def _opciones_filtradas(self):
        txt = self.entry.text.strip().lower()
        if not txt:
            return self.datos
        return [d for d in self.datos if txt in s(d[1]).lower()]

    def _abrir_dropdown(self, *_a):
        # Al abrir con el botón «▾» se muestran SIEMPRE todas las opciones
        # (sin filtrar por el texto ya cargado en el campo, p.ej. el
        # conector actual), y el desplegable se ancla al widget completo
        # (TextInput + botón) para que salga con su mismo ancho, debajo
        # del campo, en vez de angosto y debajo del botón.
        self._poblar_dropdown(self.datos)
        self._dropdown.width = self.width
        self._dropdown.open(self)

    def _on_texto_cambia(self, *_a):
        if self._actualizando:
            return
        opciones = self._opciones_filtradas()
        # Si el texto coincide exactamente con una opción, fijamos el id
        match = next((d for d in self.datos
                     if s(d[1]).lower() == self.entry.text.strip().lower()), None)
        self.id_seleccionado = str(match[0]) if match else ""
        if opciones and self.entry.focus:
            self._poblar_dropdown(opciones)
            if not self._dropdown.attach_to:
                self._dropdown.width = self.width
                self._dropdown.open(self)

    def _poblar_dropdown(self, opciones):
        self._dropdown.clear_widgets()
        for fila in opciones[:50]:
            id_, nombre = fila[0], fila[1]
            btn = Button(text=s(nombre), size_hint_y=None, height=ALTO_FILA,
                        font_size=FUENTE_NORMAL)
            btn.bind(on_release=lambda inst, i=id_, n=nombre: self._elegir(i, n))
            self._dropdown.add_widget(btn)

    def _elegir(self, id_, nombre):
        self._actualizando = True
        self.entry.text = s(nombre)
        self._actualizando = False
        self.id_seleccionado = str(id_)
        self._dropdown.dismiss()

    def get_id(self):
        if self.id_seleccionado:
            return self.id_seleccionado
        txt = self.entry.text.strip().lower()
        if not txt:
            return ""
        for fila in self.datos:
            if s(fila[1]).strip().lower() == txt:
                return str(fila[0])
        return ""

    def set_id(self, id_val):
        if id_val is None:
            return
        for fila in self.datos:
            if str(fila[0]) == str(id_val):
                self._actualizando = True
                self.entry.text = s(fila[1])
                self._actualizando = False
                self.id_seleccionado = str(fila[0])
                return


class SpinnerCantidad(BoxLayout):
    """Equivalente a Gtk.SpinButton: cantidad numérica con botones -/+."""

    def __init__(self, valor=0, minimo=0, maximo=99, on_change=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(40), spacing=dp(2), **kwargs)
        self.minimo = minimo
        self.maximo = maximo
        self._on_change = on_change
        self.btn_menos = Button(text="-", size_hint_x=None, width=dp(40),
                               font_size=FUENTE_NORMAL)
        self.entry = TextInput(text=str(valor), multiline=False,
                               input_filter="int", halign="center",
                               size_hint_x=None, width=dp(50),
                               font_size=FUENTE_NORMAL)
        self.btn_mas = Button(text="+", size_hint_x=None, width=dp(40),
                             font_size=FUENTE_NORMAL)
        self.add_widget(self.btn_menos)
        self.add_widget(self.entry)
        self.add_widget(self.btn_mas)
        self.btn_menos.bind(on_release=lambda *_a: self._sumar(-1))
        self.btn_mas.bind(on_release=lambda *_a: self._sumar(1))
        self.entry.bind(text=self._on_texto)

    def _sumar(self, delta):
        self.set_value(self.get_value() + delta)

    def _on_texto(self, *_a):
        if self._on_change:
            self._on_change(self.get_value())

    def get_value(self):
        try:
            return int(self.entry.text)
        except ValueError:
            return 0

    def set_value(self, v):
        v = max(self.minimo, min(self.maximo, v))
        self.entry.text = str(v)


class FileChooserPopup(Popup):
    """
    Equivalente a Gtk.FileChooserDialog. Kivy no tiene un selector de
    archivos nativo del sistema operativo, así que se construye con
    FileChooserListView sobre el filesystem.
    """

    def __init__(self, titulo=None, ruta_inicial=None, filtros=None,
                on_seleccionar=None, **kwargs):
        from kivy.uix.filechooser import FileChooserListView
        import os as _os
        self._on_seleccionar = on_seleccionar

        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        self.chooser = FileChooserListView(
            path=ruta_inicial or _os.path.expanduser("~"),
            filters=filtros or [],
        )
        box.add_widget(self.chooser)

        hb = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_abrir = Button(text=_("Abrir"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_abrir.bind(on_release=self._abrir)
        hb.add_widget(btn_cancelar)
        hb.add_widget(btn_abrir)
        box.add_widget(hb)

        super().__init__(title=titulo or _("Seleccionar archivo"),
                         content=box, size_hint=(1, 1), **kwargs)

    def _abrir(self, *_a):
        seleccion = self.chooser.selection
        if not seleccion:
            mostrar_error(_("Elegí un archivo."))
            return
        ruta = seleccion[0]
        self.dismiss()
        if self._on_seleccionar:
            self._on_seleccionar(ruta)


_MD_BULLETS = "○●◦◉▪▫‣∙·•►▶➤»─└├┌│⁃∎◆◇■□★☆✓✗➔→"
_MD_INDENT_ANCHO = 2  # nbsp por nivel de sangría/bullet detectado

# Caracteres permitidos en el resultado final (además de ASCII imprimible y
# el nbsp de sangría): letras acentuadas / ñ / signos de puntuación en
# español. Todo lo demás (emoji, dingbats, cuadros, etc.) se descarta:
# Pydroid 3 no tiene esas glifas y se ven como "tofu" (cuadraditos □).
_MD_PERMITIDOS = re.compile(
    r"[^\x20-\x7E\u00a0áéíóúÁÉÍÓÚñÑüÜ¿¡–—…“”\n]")


def renderizar_markdown_simple(texto):
    """Convierte un subconjunto simple de Markdown a markup de Kivy:
    encabezados #, ##, ###, **bold**, *italic*, `mono`. Es un equivalente
    reducido al render manual con Gtk.TextTag del original (alcanza para
    notas de configuración de equipos, no es un parser Markdown completo).

    Además:
      - Reemplaza bullets/símbolos Unicode (○ ● ▫ etc.) por "-", ya que
        Pydroid 3 no tiene esas fuentes y se ven como cuadraditos (□).
      - Preserva la sangría de listas anidadas usando espacios NO
        separables (\\u00a0), porque Kivy recorta los espacios normales
        al inicio de línea.
    """
    lineas_out = []
    for linea in texto.split("\n"):
        # nivel de sangría = espacios/tabs iniciales + bullets Unicode
        # anidados tipo "▫▫-" que en realidad marcan profundidad
        m = re.match(r"^([ \t]*)((?:[" + re.escape(_MD_BULLETS) + r"]\s*)*)(.*)$", linea)
        espacios, bullets, resto = m.groups()
        nivel = len(espacios.replace("\t", "    ")) // 2 + len(bullets.strip())
        resto = resto.lstrip()

        prefijo = ""
        if bullets.strip():
            prefijo = "- "

        stripped = resto
        if stripped.startswith("### "):
            cuerpo = f"[b]{stripped[4:]}[/b]"
        elif stripped.startswith("## "):
            cuerpo = f"[size=22][b]{stripped[3:]}[/b][/size]"
        elif stripped.startswith("# "):
            cuerpo = f"[size=28][b]{stripped[2:]}[/b][/size]"
        elif stripped.startswith("- ") or stripped.startswith("* "):
            prefijo = "- "
            cuerpo = stripped[2:]
        else:
            cuerpo = stripped

        sangria = "\u00a0" * (nivel * _MD_INDENT_ANCHO)
        lineas_out.append(sangria + prefijo + cuerpo)

    texto = "\n".join(lineas_out)
    texto = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", texto)
    texto = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"[i]\1[/i]", texto)
    texto = re.sub(r"`([^`]+)`", r"[b]\1[/b]", texto)

    # Última pasada: sacar cualquier símbolo no-ASCII que haya quedado
    # (emoji, dingbats, cuadros de dibujo) fuera de las tags [..] de markup.
    texto = _MD_PERMITIDOS.sub("", texto)
    return texto


def fila_botones_pill(botones, justificar="centro"):
    """Fila con uno o más BotonPill. Los botones se agrupan con un
    espacio fijo y chico entre sí (no se estiran ni se separan de más)
    y ese grupo compacto se centra en el ancho disponible — evita tanto
    el extremo de "amontonados sin separación" como el de "perdidos con
    huecos enormes a los costados". `botones`: lista de dict con claves
    texto/icono/estilo/on_release."""
    from tema import BotonPill
    contenedor = AnchorLayout(size_hint_y=None, height=dp(46),
                             anchor_x="center", anchor_y="center")
    grupo = BoxLayout(size_hint=(None, None), height=dp(42), spacing=dp(10))
    grupo.bind(minimum_width=grupo.setter("width"))
    for b in botones:
        btn = BotonPill(b["texto"], icono=b.get("icono"),
                       estilo=b.get("estilo", "primario"))
        btn.bind(on_release=lambda *_a, cb=b["on_release"]: cb())
        grupo.add_widget(btn)
    contenedor.add_widget(grupo)
    return contenedor


def fila_cancelar_aceptar(on_cancelar, on_aceptar, texto_cancelar=None,
                          texto_aceptar=None):
    """Fila Cancelar/Aceptar del pie de los diálogos de edición, con
    jerarquía visual clara: Cancelar es un botón 'pill' secundario
    (tonal, sin relleno fuerte) y Aceptar es un botón 'pill' primario
    (relleno, la acción recomendada/por defecto) — más chicos, más
    separados entre sí y con margen a los costados en vez de ocupar
    todo el ancho, y cada uno con su ícono."""
    return fila_botones_pill([
        {"texto": texto_cancelar or _("Cancelar"), "icono": "cerrar",
         "estilo": "secundario", "on_release": on_cancelar},
        {"texto": texto_aceptar or _("Aceptar"), "icono": "guardar",
         "estilo": "primario", "on_release": on_aceptar},
    ])


def fila_cerrar_arriba(on_cerrar):
    """Fila delgada con un botón ícono 'X' alineado a la derecha, pensada
    para ir como PRIMER widget del `content` de un Popup. Reemplaza a los
    viejos botones de texto 'Cerrar' al pie de cada pantalla, que quedan
    tapados por la barra de navegación inferior (fija, global). Uso:

        outer = BoxLayout(orientation="vertical")
        outer.add_widget(fila_cerrar_arriba(self.dismiss))
        outer.add_widget(...)   # resto del contenido
        super().__init__(content=outer, ...)
    """
    from tema import BotonIcono
    fila = BoxLayout(size_hint_y=None, height=dp(38),
                     padding=(0, 0, dp(6), 0))
    fila.add_widget(BoxLayout())  # empuja el botón a la derecha
    btn = BotonIcono(icono="cerrar", clave_icono="texto", tamano=dp(30))
    btn.bind(on_release=lambda *_a: on_cerrar())
    fila.add_widget(btn)
    return fila


def barra_superior_dialogo(titulo, on_atras, on_mas=None):
    """Barra superior de una pantalla de detalle: flecha atrás + título +
    (opcional) botón de menú de tres puntos verticales — reemplaza al
    título plano por defecto de Popup en las pantallas rediseñadas
    (Editar Equipo, etc.), siguiendo el patrón del mockup 2.0."""
    from tema import tema, BotonIcono
    barra = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4),
                      padding=(dp(4), 0))
    btn_atras = BotonIcono(icono="atras", clave_icono="texto")
    btn_atras.bind(on_release=lambda *_a: on_atras())
    barra.add_widget(btn_atras)
    lbl = Label(text=titulo, bold=True, font_size=FUENTE_TITULO,
               color=tema.c("texto"), halign="left", valign="middle",
               shorten=True, shorten_from="right")
    lbl.bind(size=lambda w, *_a: setattr(w, "text_size", (w.width, w.height)))
    barra.add_widget(lbl)
    barra.lbl_titulo = lbl
    if on_mas:
        btn_mas = BotonIcono(icono="mas_vertical", clave_icono="texto")
        btn_mas.bind(on_release=lambda *_a: on_mas())
        barra.add_widget(btn_mas)
    return barra


def tarjeta_encabezado(icono, nombre, subtitulo, chip_texto=None,
                       chip_color="exito", linea_extra=None):
    """Tarjeta de encabezado tipo mockup 2.0: caja de ícono + nombre +
    subtítulo (p.ej. 'Marca · Tipo · Modelo') + chip de estado a la
    derecha del nombre + una línea extra opcional, con letra más chica
    (p.ej. 'Sala · Rack · Frame'). Usada arriba de las pantallas de
    detalle."""
    from tema import tema, Tarjeta, Chip, IconoImg
    alto = dp(74) if not linea_extra else dp(90)
    tarjeta = Tarjeta(size_hint_y=None, height=alto, padding=dp(10),
                     spacing=dp(10))
    caja = FloatLayout(size_hint=(None, None), size=(dp(50), dp(50)))
    rect_c = Color(*tema.c("secundario_bg"))
    rect = RoundedRectangle(pos=caja.pos, size=caja.size, radius=[dp(12)])
    caja.canvas.before.add(rect_c)
    caja.canvas.before.add(rect)
    caja.bind(pos=lambda w, *_a: setattr(rect, "pos", w.pos),
             size=lambda w, *_a: setattr(rect, "size", w.size))
    img = IconoImg(icono, clave_color="primario", size_hint=(None, None),
                  size=(dp(26), dp(26)),
                  pos_hint={"center_x": 0.5, "center_y": 0.5})
    caja.add_widget(img)
    tarjeta.add_widget(caja)

    textos = BoxLayout(orientation="vertical", spacing=dp(2))
    fila_nombre = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(6))
    lbl_nombre = Label(text=nombre or "-", bold=True, font_size=sp(15),
                       color=tema.c("texto"), halign="left", valign="middle",
                       shorten=True, shorten_from="right")
    lbl_nombre.bind(size=lambda w, *_a: setattr(
        w, "text_size", (w.width, w.height)))
    fila_nombre.add_widget(lbl_nombre)
    if chip_texto:
        fila_nombre.add_widget(Chip(texto=chip_texto, clave_color=chip_color))
    textos.add_widget(fila_nombre)
    lbl_sub = Label(text=subtitulo or "", font_size=FUENTE_CHICA,
                    color=tema.c("texto_sub"), halign="left", valign="middle",
                    shorten=True, shorten_from="right")
    lbl_sub.bind(size=lambda w, *_a: setattr(w, "text_size", (w.width, w.height)))
    textos.add_widget(lbl_sub)
    if linea_extra:
        lbl_extra = Label(text=linea_extra, font_size=sp(10),
                          color=tema.c("texto_sub"), halign="left",
                          valign="middle", shorten=True, shorten_from="right")
        lbl_extra.bind(size=lambda w, *_a: setattr(
            w, "text_size", (w.width, w.height)))
        textos.add_widget(lbl_extra)
    tarjeta.add_widget(textos)
    return tarjeta


class FilaAccion(ButtonBehavior, BoxLayout):
    """Fila de 'acción rápida' con ícono en caja redondeada + título +
    subtítulo + chevron a la derecha — la lista de accesos de las
    pantallas de detalle rediseñadas (Ver conectores, Diagrama, etc.)."""

    def __init__(self, icono, titulo, subtitulo="", **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(58))
        kwargs.setdefault("padding", (dp(10), dp(6)))
        kwargs.setdefault("spacing", dp(10))
        super().__init__(**kwargs)
        from tema import tema, IconoImg

        with self.canvas.before:
            self._c_fondo = Color(*tema.c("superficie"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(10)])
        self.bind(pos=self._actualizar, size=self._actualizar)

        caja = FloatLayout(size_hint=(None, None), size=(dp(38), dp(38)))
        with caja.canvas.before:
            Color(*tema.c("secundario_bg"))
            self._rect_icono = RoundedRectangle(pos=caja.pos, size=caja.size,
                                               radius=[dp(9)])
        caja.bind(pos=lambda w, *_a: setattr(self._rect_icono, "pos", w.pos))
        img = IconoImg(icono, clave_color="primario", size_hint=(None, None),
                      size=(dp(19), dp(19)),
                      pos_hint={"center_x": 0.5, "center_y": 0.5})
        caja.add_widget(img)
        self.add_widget(caja)

        textos = BoxLayout(orientation="vertical", spacing=dp(1))
        lbl_t = Label(text=titulo, bold=True, font_size=FUENTE_NORMAL,
                     color=tema.c("texto"), halign="left", valign="middle")
        lbl_t.bind(size=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
        textos.add_widget(lbl_t)
        if subtitulo:
            lbl_s = Label(text=subtitulo, font_size=sp(11),
                         color=tema.c("texto_sub"), halign="left",
                         valign="middle")
            lbl_s.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width, None)))
            textos.add_widget(lbl_s)
        self.add_widget(textos)

        chevron = IconoImg("chevron_derecha", clave_color="texto_sub",
                          size_hint=(None, None), size=(dp(14), dp(14)))
        self.add_widget(chevron)

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size


class _ItemTabHeader(ButtonBehavior, BoxLayout):
    def __init__(self, texto, activo, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)
        from tema import tema
        self._activo = activo
        self._lbl = Label(text=texto.upper(), bold=True, font_size=sp(12),
                          color=tema.c("primario") if activo
                                else tema.c("texto_sub"))
        self.add_widget(self._lbl)
        with self.canvas.after:
            self._c = Color(*(tema.c("primario") if activo else (0, 0, 0, 0)))
            self._linea = Line(points=[0, 0, 0, 0], width=dp(2.5))
        self.bind(pos=self._actualizar, size=self._actualizar)

    def _actualizar(self, *_a):
        self._linea.points = [self.x + dp(6), self.y + dp(1),
                              self.right - dp(6), self.y + dp(1)]

    def set_activo(self, activo):
        from tema import tema
        self._activo = activo
        self._lbl.color = tema.c("primario") if activo else tema.c("texto_sub")
        self._c.rgba = tema.c("primario") if activo else (0, 0, 0, 0)


class BarraTabs(BoxLayout):
    """Barra de pestañas subrayadas (estilo mockup 2.0): reemplaza a
    TabbedPanel para las pantallas de detalle. Uso:

        tabs = BarraTabs(["Acciones", "Datos", "Configuración"])
        tabs.on_cambiar = lambda i: mostrar_contenido(i)

    El contenido de cada pestaña se maneja aparte (BarraTabs solo pinta
    los encabezados y notifica el índice elegido); así cada pantalla
    controla cómo arma/cachea su propio contenido."""

    def __init__(self, etiquetas, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(42))
        super().__init__(**kwargs)
        from tema import tema
        self.on_cambiar = None
        self._botones = []
        with self.canvas.before:
            self._c_borde = Color(*tema.c("borde"))
            self._linea = Line(points=[self.x, self.y, self.right, self.y],
                              width=1)
        self.bind(pos=self._actualizar, size=self._actualizar)
        for i, etq in enumerate(etiquetas):
            b = _ItemTabHeader(etq, i == 0)
            b.bind(on_release=lambda w, idx=i: self.elegir(idx))
            self.add_widget(b)
            self._botones.append(b)

    def _actualizar(self, *_a):
        self._linea.points = [self.x, self.y, self.right, self.y]

    def elegir(self, idx):
        for j, b in enumerate(self._botones):
            b.set_activo(j == idx)
        if self.on_cambiar:
            self.on_cambiar(idx)


def etiqueta_ultima_edicion(tabla, pk_col, pk_val):
    """Equivalente a _pack_ultima_edicion: retorna un Label o None."""
    if not pk_val:
        return None
    fecha = Modelo.devolver_fecha_ultima_edicion(tabla, pk_col, pk_val)
    if not fecha:
        return None
    return Label(text=f"[i]ÚLTIMA EDICIÓN: {fecha}[/i]", markup=True,
                size_hint_y=None, height=22, halign="right",
                font_size=12, color=(0.6, 0.6, 0.6, 1))


def fila_auditoria(tabla, pk_col, pk_val, on_actualizado=None, on_marcado=None):
    """
    Devuelve (info, boton):
      info   → Label con la fecha de última edición/auditoría (o None si
               pk_val no existe todavía — alta sin guardar).
      boton  → BotonPill "Auditado" (estilo terciario: jerarquía más baja
               que Cancelar/Aceptar) que marca el registro como auditado
               al tocarlo, o None si pk_val no existe.

    El llamador decide cómo ubicarlos: `info` normalmente va solo en su
    propia fila, y `boton` se agrega junto a Cancelar/Aceptar en la
    fila de botones del pie (ver fila_botones_pill) para que las tres
    acciones queden juntas en una sola línea.

    on_actualizado: se llama después de marcar, para refrescar la UI.
    on_marcado(fecha): se llama después de marcar, con la fecha/hora
        grabada — útil para encadenar acciones (p.ej. preguntar si
        también se auditan registros relacionados).
    """
    if not pk_val:
        return None, None

    lbl = Label(halign="left", valign="top", font_size=FUENTE_CHICA,
               markup=True, size_hint_y=None)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    lbl.bind(texture_size=lambda w, *_a: setattr(w, "height", w.texture_size[1]))

    def _refrescar():
        fecha_ed = Modelo.devolver_fecha_ultima_edicion(tabla, pk_col, pk_val)
        fecha_aud = Modelo.devolver_fecha_ultima_auditoria(tabla, pk_col, pk_val)
        partes = []
        if fecha_ed:
            partes.append(f"[color=999999]{_('Edición')}: {fecha_ed}[/color]")
        if fecha_aud:
            partes.append(f"[color=8ccf8c]{_('Auditado')}: {fecha_aud}[/color]")
        else:
            partes.append(f"[color=e0a84a]{_('Sin auditar')}[/color]")
        lbl.text = "   ·   ".join(partes)

    _refrescar()

    from tema import BotonPill
    btn = BotonPill(_("Auditado"), icono="guardar", estilo="terciario")

    def _marcar(*_a):
        fecha = Modelo.marcar_auditado(tabla, pk_col, pk_val)
        _refrescar()
        if on_actualizado:
            on_actualizado()
        if on_marcado:
            on_marcado(fecha)

    btn.bind(on_release=_marcar)
    return lbl, btn


# ─── Visor de imagen con zoom + overlay (fase 3) ──────────────────────────────
#
# Equivalente a _ImagenZoom de pantallas_avanzadas.py (GTK + Cairo).
#
# Cómo se traduce Cairo -> Kivy graphics aquí:
#   - GTK dibujaba todo con un cr (Cairo context) recibido en la señal "draw".
#   - Kivy no tiene una señal de "redibujar"; en cambio, cada widget tiene un
#     `canvas` (lista de instrucciones gráficas) que vos reconstruís cuando
#     algo cambia. ImagenCanvas hace eso en `_redraw()`.
#   - Para que las coordenadas de imagen (x,y en píxeles, origen arriba-
#     izquierda, igual que las que ya están guardadas en la base de datos)
#     coincidan con las coordenadas locales del widget (origen abajo-
#     izquierda en Kivy), se envuelve el dibujo en
#     `PushMatrix() / Translate(*self.pos) / PopMatrix()` y se exponen los
#     métodos `i2w` / `w2i` que hacen la conversión (incluyendo el flip de
#     eje Y).
#   - `overlay_fn(canvas_widget)` es el equivalente directo de
#     `viz.overlay_fn = lambda cr: ...` en GTK: el dueño del visor dibuja
#     encima de la imagen usando `with canvas_widget.canvas: Color(...);
#     Line(...)`.

class ImagenCanvas(Widget):
    """Widget de tamaño fijo (no size_hint) que dibuja una textura de imagen
    y permite overlay + clicks en coordenadas de imagen.

    Soporta pinch-to-zoom con 2 dedos (fundamental en celular: los botones
    +/− de la barra de zoom siguen andando, pero para explorar una imagen
    grande con el dedo hace falta poder pellizcar). Al detectar un segundo
    dedo, se cancela cualquier colocación de marcador en curso con el
    primero, para que no queden marcadores puestos "sin querer" al pellizcar.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.textura = None
        self.overlay_fn = None       # callable(self) -> dibuja sobre la imagen
        self.on_press_img = None     # callable(ix, iy)
        self.on_motion_img = None    # callable(ix, iy)
        self.on_release_img = None   # callable(ix, iy)
        self.on_pinch_zoom = None    # callable(factor, cx, cy) -- 2 dedos
        self._tocando = False
        self._pinch_touches = {}     # uid -> (x, y) en coords de ventana
        self._pinch_dist0 = None
        self.bind(pos=self._redraw, size=self._redraw)

    def set_textura(self, textura):
        self.textura = textura
        self._redraw()

    def _redraw(self, *_a):
        self.canvas.clear()
        with self.canvas:
            PushMatrix()
            Translate(*self.pos)
            if self.textura is not None:
                Color(1, 1, 1, 1)
                Rectangle(texture=self.textura, pos=(0, 0), size=self.size)
            else:
                Color(0.5, 0.5, 0.5, 1)
                Rectangle(pos=(0, 0), size=self.size)
        if callable(self.overlay_fn):
            self.overlay_fn(self)
        with self.canvas:
            PopMatrix()

    # ── conversión imagen(px, origen arriba-izq.) <-> local widget (origen
    #    abajo-izq., como cualquier coordenada Kivy) ──
    def i2w(self, ix, iy, zoom=1.0):
        return ix * zoom, self.height - iy * zoom

    def w2i(self, lx, ly, zoom=1.0):
        return lx / zoom, (self.height - ly) / zoom

    # ── touch ──
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self._pinch_touches[touch.uid] = (touch.x, touch.y)

        if len(self._pinch_touches) == 2:
            # Al aparecer el segundo dedo, cancelamos cualquier colocación
            # de marcador en curso con el primero.
            self._tocando = False
            pts = list(self._pinch_touches.values())
            self._pinch_dist0 = math.hypot(pts[1][0] - pts[0][0],
                                           pts[1][1] - pts[0][1])
            return True

        if len(self._pinch_touches) == 1:
            self._tocando = True
            if self.on_press_img:
                lx, ly = self.to_widget(touch.x, touch.y, relative=True)
                self.on_press_img(lx, ly)
        return True

    def on_touch_move(self, touch):
        if touch.uid in self._pinch_touches:
            self._pinch_touches[touch.uid] = (touch.x, touch.y)

            if len(self._pinch_touches) == 2 and self._pinch_dist0:
                pts = list(self._pinch_touches.values())
                dist = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
                if self._pinch_dist0 > 1 and self.on_pinch_zoom:
                    factor = dist / self._pinch_dist0
                    cx = (pts[0][0] + pts[1][0]) / 2
                    cy = (pts[0][1] + pts[1][1]) / 2
                    self.on_pinch_zoom(factor, cx, cy)
                self._pinch_dist0 = dist  # incremental: base para el próximo delta
                return True

            if touch.grab_current is self and self._tocando and self.on_motion_img:
                lx, ly = self.to_widget(touch.x, touch.y, relative=True)
                self.on_motion_img(lx, ly)
                return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.uid in self._pinch_touches:
            touch.ungrab(self)
            self._pinch_touches.pop(touch.uid, None)
            if len(self._pinch_touches) < 2:
                self._pinch_dist0 = None
            tocando_previo = self._tocando
            self._tocando = False
            if tocando_previo and self.on_release_img:
                lx, ly = self.to_widget(touch.x, touch.y, relative=True)
                self.on_release_img(lx, ly)
            return True
        return super().on_touch_up(touch)


class VisorImagenZoom(BoxLayout):
    """Equivalente a _ImagenZoom: barra de zoom + ScrollView + ImagenCanvas."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=0, **kwargs)
        self.zoom = 1.0
        self.textura = None
        self.overlay_fn = None

        hbz = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(4),
                       padding=dp(4))
        self._lbl_zoom = Label(text="100%", size_hint_x=None, width=dp(52),
                              font_size=FUENTE_CHICA)
        hbz.add_widget(Label(text=_("Zoom:"), size_hint_x=None, width=dp(48),
                            font_size=FUENTE_CHICA))
        hbz.add_widget(self._lbl_zoom)
        for etiqueta, factor in [("+", 1.25), ("-", 1 / 1.25)]:
            b = Button(text=etiqueta, size_hint_x=None, width=dp(42),
                      font_size=FUENTE_NORMAL)
            b.bind(on_release=lambda _b, f=factor: self.set_zoom(self.zoom * f))
            hbz.add_widget(b)
        b11 = Button(text="1:1", size_hint_x=None, width=dp(46),
                    font_size=FUENTE_CHICA)
        b11.bind(on_release=lambda *_a: self.set_zoom(1.0))
        hbz.add_widget(b11)
        bfit = Button(text=_("Ajustar"), size_hint_x=None, width=dp(76),
                     font_size=FUENTE_CHICA)
        bfit.bind(on_release=lambda *_a: self._zoom_fit())
        hbz.add_widget(bfit)
        # Sin espaciador: en 360dp de ancho estos botones ya ocupan casi
        # todo el ancho disponible (52+48+52+42+42+46+76 ≈ 358dp).
        self.add_widget(hbz)

        self._scroll = ScrollView()
        self.canvas_widget = ImagenCanvas(size=(600, 400))
        self.canvas_widget.on_pinch_zoom = self._on_pinch_zoom
        self._lbl_sin_imagen = Label(
            text=_("Sin imagen asignada al equipo/conector"),
            color=(0.85, 0.85, 0.85, 1))
        self._contenedor = FloatLayout(size=(600, 400), size_hint=(None, None))
        self._contenedor.add_widget(self.canvas_widget)
        self._contenedor.add_widget(self._lbl_sin_imagen)
        self._scroll.add_widget(self._contenedor)
        self.add_widget(self._scroll)
        self._scroll.bind(size=lambda *_a: self._update_size())

    def _on_pinch_zoom(self, factor, cx, cy):
        """Pellizco de 2 dedos sobre la imagen (cx, cy en coords de
        ventana). Recentra el punto pellizcado tras cambiar el zoom, para
        que la zona bajo los dedos sea la que quede visible."""
        if self.textura is None:
            return
        lx, ly = self.canvas_widget.to_widget(cx, cy, relative=True)
        ix, iy = self.canvas_widget.w2i(lx, ly, self.zoom)
        self.set_zoom(self.zoom * factor)
        self.scroll_to_img(ix, iy)

    # ── público ──
    def set_imagen(self, ruta_archivo):
        """ruta_archivo: path absoluto al archivo de imagen, o None."""
        self.textura = None
        if ruta_archivo and os.path.exists(ruta_archivo):
            try:
                from kivy.core.image import Image as CoreImage
                self.textura = CoreImage(ruta_archivo).texture
            except Exception:
                self.textura = None
        self.canvas_widget.set_textura(self.textura)
        self._lbl_sin_imagen.opacity = 0 if self.textura else 1
        self._update_size()

    def set_zoom(self, z):
        self.zoom = max(0.1, min(8.0, z))
        self._lbl_zoom.text = f"{int(self.zoom * 100)}%"
        self._update_size()

    def scroll_to_img(self, ix, iy):
        wx, wy = self.i2w(ix, iy)
        if self._scroll.width and self._contenedor.width > self._scroll.width:
            self._scroll.scroll_x = max(0, min(1, (wx - self._scroll.width / 2) /
                                              (self._contenedor.width - self._scroll.width)))
        if self._scroll.height and self._contenedor.height > self._scroll.height:
            self._scroll.scroll_y = max(0, min(1, 1 - (wy + self._scroll.height / 2) /
                                              self._contenedor.height))

    # ── conversión (delega en canvas_widget, ya considera self.zoom) ──
    def i2w(self, ix, iy):
        return self.canvas_widget.i2w(ix, iy, self.zoom)

    def w2i(self, lx, ly):
        return self.canvas_widget.w2i(lx, ly, self.zoom)

    def set_overlay_fn(self, fn):
        self.overlay_fn = fn
        self.canvas_widget.overlay_fn = fn

    def queue_draw(self):
        self.canvas_widget._redraw()

    # ── privado ──
    def _update_size(self):
        if self.textura is not None:
            w = int(self.textura.width * self.zoom)
            h = int(self.textura.height * self.zoom)
        else:
            w, h = 600, 400
        self.canvas_widget.size = (w, h)
        self._contenedor.size = (max(w, self._scroll.width or 0),
                                 max(h, self._scroll.height or 0))
        # Anclar la imagen a la esquina SUPERIOR-izquierda del contenedor
        # (FloatLayout no reposiciona hijos solo; sin esto la imagen queda
        # pegada abajo cuando el contenedor es más alto que la imagen).
        self.canvas_widget.pos = (0, self._contenedor.height - h)
        self._lbl_sin_imagen.center = (self._contenedor.width / 2,
                                       self._contenedor.height / 2)
        # Mantener scroll arriba del todo tras (re)cargar/hacer zoom.
        self._scroll.scroll_y = 1
        self.canvas_widget._redraw()

    def _zoom_fit(self):
        if self.textura is None or not self._scroll.width:
            return
        zw = self._scroll.width / self.textura.width
        zh = self._scroll.height / self.textura.height
        self.set_zoom(min(zw, zh))


def dibujar_marcador_cuadrado(canvas_widget, cx, cy, lado, color_rgb,
                              alpha_relleno=0.18, resaltado=False, grosor=None):
    """Dibuja un marcador cuadrado con relleno + borde, centrado en (cx, cy)
    (coordenadas locales del widget, ya convertidas con i2w). Equivalente a
    los rectángulos que dibujaba _dibujar_overlay con Cairo."""
    hl = lado / 2
    grosor = grosor or max(2, lado * 0.12)
    with canvas_widget.canvas:
        Color(*color_rgb, alpha_relleno)
        Rectangle(pos=(cx - hl, cy - hl), size=(lado, lado))
        Color(*color_rgb, 0.95 if not resaltado else 1.0)
        Line(rectangle=(cx - hl, cy - hl, lado, lado),
            width=grosor * (1.4 if resaltado else 1.0))
        Color(1, 1, 1, 0.9)
        Line(rectangle=(cx - hl, cy - hl, lado, lado), width=1.2)
