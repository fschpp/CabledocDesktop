"""
CableDoc Kivy - Módulo de Equipos.

Equivalente a EquiposListado / _DialogoEquipo / _DialogoAltaRapidaEquipo /
_DialogoDireccionConector de cabledoc.py (GTK).

Botones que abren "pantallas avanzadas" (imagen con conectores, editor
masivo de coordenadas, árbol de conexiones, vista de patcheras, diagrama
de conexiones, selector visual de coordenadas) muestran un aviso de
"fase 3" — son las pantallas que en GTK usan Gtk.DrawingArea + Cairo y
se migran al Canvas de Kivy en la siguiente fase.
"""

import os
import subprocess

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.properties import (
    StringProperty, NumericProperty, ObjectProperty, ListProperty,
    BooleanProperty,
)
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, ComboBuscable, SpinnerCantidad, FileChooserPopup,
    grid_formulario, fila_etiqueta, fila_entry, seccion_tarjeta,
    fila_auditoria, titulo_con_nombre, fila_cerrar_arriba,
    barra_superior_dialogo, tarjeta_encabezado, FilaAccion, BarraTabs,
    fila_cancelar_aceptar, fila_botones_pill,
    mostrar_error, mostrar_info, confirmar, renderizar_markdown_simple, entry_selector,
    s, _, ALTO_BOTON, ALTO_ENTRY, ALTO_FILA, FUENTE_NORMAL, FUENTE_CHICA,
)
from tema import tema, Chip, Tarjeta, IconoImg, BotonIcono, ruta_icono
from modelo import Modelo, MANUALES_DIR, PICON_DIR
from logger_cabledoc import log_debug


# ─── Listado en tarjetas ────────────────────────────────────────────────────
#
# Rediseño 2.0: reemplaza la vieja tabla de columnas por tarjetas con foto
# (campo `picon`, ver modelo.py/PICON_DIR), chip de estado (Auditado / No
# auditado), badges de resumen (conectores/conexiones/patcheras) y un
# chevron que indica que la tarjeta entera es tocable para ir a Editar —
# mismo patrón que un listado de "ajustes" estilo Android moderno.

from kivy.uix.floatlayout import FloatLayout
from widgets_base import (
    agregar_mantener_presionado,
)
from pantallas_diagrama import _tipo_color


def _chip_chico(texto, clave_color):
    """Variante compacta de Chip (tema.py) para el badge de auditoría en
    la tarjeta de Equipos — la versión estándar queda grande al lado de
    un título más prominente."""
    chip = Chip(texto=texto, clave_color=clave_color, height=dp(17))
    chip._lbl.font_size = sp(9)
    chip.padding = (dp(6), 0)
    chip.width = max(dp(38), len(texto) * dp(5.4) + dp(12))
    return chip


class _PastillaFiltro(ButtonBehavior, FloatLayout):
    """Pastilla del carrusel de tipos: violeta cuando está activa, gris
    cuando no. Widget propio (no reutiliza el ToggleButton global de
    tema.py) para tener control total y directo del color según
    self.activo, en vez de depender del estado interno 'down'/'normal'
    de ToggleButtonBehavior — así el resaltado nunca puede quedar
    desincronizado de qué filtros están realmente aplicados.

    Basado en FloatLayout (no BoxLayout): un BoxLayout no centra de forma
    confiable un hijo de tamaño fijo en el eje transversal (el texto
    quedaba pegado abajo); FloatLayout + pos_hint sí, es el mismo patrón
    ya usado en las tarjetas para centrar íconos."""

    PAD_X = dp(16)

    def __init__(self, texto, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(34))
        kwargs.setdefault("width", dp(60))
        super().__init__(**kwargs)
        self.activo = False
        with self.canvas.before:
            self._c = Color(*tema.c("superficie_alt"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(17)])
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect)
        self._lbl = Label(text=texto, font_size=FUENTE_CHICA, bold=True,
                          color=tema.c("texto"), size_hint=(None, None),
                          pos_hint={"center_x": 0.5, "center_y": 0.5})
        self._lbl.bind(texture_size=self._on_texture)
        self.add_widget(self._lbl)
        tema.bind(modo=lambda *_a: self._retema())

    def _on_texture(self, lbl, texture_size):
        lbl.size = texture_size
        self.width = texture_size[0] + self.PAD_X * 2

    def _actualizar_rect(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_activo(self, activo):
        self.activo = activo
        self._retema()

    def _retema(self, *_a):
        if self.activo:
            self._c.rgba = tema.c("primario")
            self._lbl.color = tema.c("primario_txt")
        else:
            self._c.rgba = tema.c("superficie_alt")
            self._lbl.color = tema.c("texto")


class _TarjetaEquipoRV(RecycleDataViewBehavior, BoxLayout):
    """Fila reciclable del listado de Equipos: barra de color por
    categoría + título a todo el ancho (arriba) + foto (picon) + chip de
    auditoría + subtítulo + ubicación + badges grandes + chevron. Igual
    que _FilaRV (widgets_base.py), solo instancia las tarjetas que entran
    en el viewport, así que sigue rindiendo bien con cientos de equipos.

    La tarjeta en sí NO es tocable: solo el chevron (abre Editar) y la
    imagen (mantener presionada abre la foto en pantalla grande) tienen
    gesto propio — evita toques accidentales al scrollear la lista."""

    fila_id = StringProperty("")
    index = NumericProperty(0)
    popup_ref = ObjectProperty(None, allownone=True)

    ALTURA = dp(140)
    ANCHO_BARRA_CATEGORIA = dp(5)

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", size_hint=(1, None),
                         height=self.ALTURA, spacing=dp(4),
                         padding=(dp(14), dp(10), dp(10), dp(10)), **kwargs)
        with self.canvas.before:
            self._c_fondo = Color(*tema.c("superficie"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(16)])
            # Barra de color por categoría (mismo criterio que el
            # diagrama de conexiones, ver _tipo_color en
            # pantallas_diagrama.py): redondeada solo del lado izquierdo.
            self._c_categoria = Color(0.5, 0.5, 0.5, 1)
            self._rect_categoria = RoundedRectangle(
                pos=self.pos, size=(self.ANCHO_BARRA_CATEGORIA, self.height),
                radius=[dp(16), 0, 0, dp(16)])
            self._c_borde = Color(*tema.c("borde"))
            self._borde = Line(rounded_rectangle=(*self.pos, *self.size, dp(16)),
                               width=1)
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect)
        tema.bind(modo=lambda *_a: self._retema())

        self._picon_ruta_actual = ""
        self._nombre_actual = ""

        # ── Título a todo el ancho, arriba de la imagen (más visible) ──
        self._fila_titulo = BoxLayout(size_hint_y=None, height=dp(24),
                                      spacing=dp(6))
        self.add_widget(self._fila_titulo)

        # ── Cuerpo: imagen + textos + chevron ──
        fila_cuerpo = BoxLayout(orientation="horizontal", spacing=dp(12))
        self.add_widget(fila_cuerpo)

        # Imagen (picon), con caja redondeada de respaldo si no hay foto.
        self._caja_img = FloatLayout(size_hint=(None, None),
                                     size=(dp(72), dp(72)))
        with self._caja_img.canvas.before:
            self._c_img_fondo = Color(*tema.c("secundario_bg"))
            self._rect_img = RoundedRectangle(pos=self._caja_img.pos,
                                              size=self._caja_img.size,
                                              radius=[dp(14)])
        self._caja_img.bind(
            pos=lambda w, *_a: setattr(self._rect_img, "pos", w.pos),
            size=lambda w, *_a: setattr(self._rect_img, "size", w.size))
        self._img_fallback = IconoImg("equipos", clave_color="primario",
                                      size_hint=(None, None),
                                      size=(dp(28), dp(28)),
                                      pos_hint={"center_x": 0.5, "center_y": 0.5})
        self._caja_img.add_widget(self._img_fallback)
        self._img = None
        fila_cuerpo.add_widget(self._caja_img)
        # Mantener presionada la imagen -> abrirla en pantalla grande.
        agregar_mantener_presionado(self._caja_img, self._abrir_imagen_completa)

        # ── Columna de textos (subtítulo, ubicación, badges) ──
        self._col_textos = BoxLayout(orientation="vertical", spacing=dp(3))
        fila_cuerpo.add_widget(self._col_textos)

        # ── Chevron: ÚNICO punto de la tarjeta que abre Editar ──
        cont_chev = FloatLayout(size_hint=(None, 1), width=dp(40))
        self._btn_chevron = BotonIcono(
            icono="chevron_derecha", clave_icono="texto_sub", tamano=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.5})
        self._btn_chevron.bind(on_release=lambda *_a: self._on_chevron())
        cont_chev.add_widget(self._btn_chevron)
        fila_cuerpo.add_widget(cont_chev)

    def _actualizar_rect(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect_categoria.pos = self.pos
        self._rect_categoria.size = (self.ANCHO_BARRA_CATEGORIA, self.height)
        self._borde.rounded_rectangle = (*self.pos, *self.size, dp(16))

    def _retema(self, *_a):
        self._c_fondo.rgba = tema.c("superficie")
        self._c_borde.rgba = tema.c("borde")
        self._c_img_fondo.rgba = tema.c("secundario_bg")

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.fila_id = data.get("fila_id", "")
        self.popup_ref = data.get("popup_ref")
        self._reconstruir(data)
        return super().refresh_view_attrs(rv, index, data)

    def _reconstruir(self, data):
        # ── Barra de categoría ──
        r, g, b = _tipo_color(data.get("tipo", ""))
        self._c_categoria.rgba = (r, g, b, 1)

        # ── Imagen ──
        if self._img is not None and self._img.parent:
            self._caja_img.remove_widget(self._img)
            self._img = None
        if self._img_fallback.parent:
            self._caja_img.remove_widget(self._img_fallback)

        ruta = data.get("picon_ruta") or ""
        self._nombre_actual = data.get("nombre", "")
        mostrado = False
        if ruta and os.path.exists(ruta):
            try:
                self._img = Image(source=ruta, size_hint=(1, 1),
                                  pos_hint={"x": 0, "y": 0},
                                  fit_mode="cover", allow_stretch=True)
                self._caja_img.add_widget(self._img)
                mostrado = True
            except Exception:
                self._img = None
        if not mostrado:
            self._caja_img.add_widget(self._img_fallback)
        self._picon_ruta_actual = ruta if mostrado else ""

        # ── Título, a todo el ancho, arriba del cuerpo ──
        self._fila_titulo.clear_widgets()
        lbl_nombre = Label(text=data.get("nombre", ""), bold=True,
                          font_size=sp(18), color=tema.c("texto"),
                          halign="left", valign="middle", shorten=True,
                          shorten_from="right")
        lbl_nombre.bind(size=lambda w, *_a: setattr(
            w, "text_size", (w.width, w.height)))
        self._fila_titulo.add_widget(lbl_nombre)
        chip_texto = data.get("chip_texto")
        if chip_texto:
            self._fila_titulo.add_widget(_chip_chico(
                chip_texto, data.get("chip_color", "exito")))

        # ── Resto de los textos ──
        self._col_textos.clear_widgets()

        sub = data.get("subtitulo", "")
        if sub:
            lbl_sub = Label(text=sub, font_size=FUENTE_CHICA,
                           color=tema.c("texto_sub"), halign="left",
                           valign="middle", shorten=True, shorten_from="right",
                           size_hint_y=None, height=dp(18))
            lbl_sub.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width, w.height)))
            self._col_textos.add_widget(lbl_sub)

        ubic = data.get("ubicacion", "")
        if ubic:
            fila_ubic = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(4))
            fila_ubic.add_widget(IconoImg(
                "ubicacion", clave_color="texto_sub", size_hint=(None, None),
                size=(dp(13), dp(13))))
            lbl_ubic = Label(text=ubic, font_size=sp(10.5),
                            color=tema.c("texto_sub"), halign="left",
                            valign="middle", shorten=True, shorten_from="right")
            lbl_ubic.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width, w.height)))
            fila_ubic.add_widget(lbl_ubic)
            self._col_textos.add_widget(fila_ubic)

        self._col_textos.add_widget(BoxLayout())  # espaciador flexible

        fila_badges = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(20))
        for icono, valor, etiqueta in [
            ("conector", data.get("n_con", 0), _("Conectores")),
            ("conexiones", data.get("n_cx", 0), _("Conexiones")),
            ("patchera", data.get("n_patch", 0), _("Patcheras")),
        ]:
            fila_badges.add_widget(self._badge(icono, valor, etiqueta))
        self._col_textos.add_widget(fila_badges)

    def _badge(self, icono, valor, etiqueta):
        col = BoxLayout(orientation="vertical", size_hint=(None, None),
                        spacing=dp(1))
        col.bind(minimum_width=col.setter("width"))

        fila_top = BoxLayout(size_hint=(None, None), height=dp(22), spacing=dp(4))
        fila_top.bind(minimum_width=fila_top.setter("width"))
        fila_top.add_widget(IconoImg(icono, clave_color="primario",
                                     size_hint=(None, None),
                                     size=(dp(17), dp(17))))
        lbl_num = Label(text=str(valor or 0), bold=True, font_size=sp(19),
                       color=tema.c("texto"), size_hint=(None, None))
        lbl_num.bind(texture_size=lambda w, ts: setattr(w, "size", ts))
        fila_top.add_widget(lbl_num)
        col.add_widget(fila_top)

        lbl_etq = Label(text=etiqueta, font_size=sp(10),
                       color=tema.c("texto_sub"), size_hint=(None, None),
                       halign="left")
        lbl_etq.bind(texture_size=lambda w, ts: setattr(w, "size", ts))
        col.add_widget(lbl_etq)
        return col

    # ── Único punto de tap que navega a Editar / confirma selección ──
    def _on_chevron(self):
        if self.popup_ref:
            self.popup_ref._tap_tarjeta(self.fila_id)

    # ── Mantener presionada la imagen -> pantalla grande ──
    def _abrir_imagen_completa(self):
        if (self._picon_ruta_actual and os.path.exists(self._picon_ruta_actual)
                and self.popup_ref):
            self.popup_ref._ver_imagen_completa(
                self._picon_ruta_actual, self._nombre_actual)


class EquiposListado(Popup):
    """Listado de Equipos en tarjetas (foto + resumen + chevron).

    filtro_pendiente: None | 'sin_conectores' | 'sin_imagen' |
        'sin_img_conectores' | 'sin_auditar' | 'sin_manual' |
        'sin_configuraciones'
    modo_seleccion/on_seleccionar: igual que ListadoPopup — al tocar una
        tarjeta se confirma la selección y se cierra, en vez de abrir
        Editar.
    """

    def __init__(self, filtro_pendiente=None, modo_seleccion=False,
                on_seleccionar=None, **kwargs):
        self._filtro_pendiente = filtro_pendiente
        self._ocultar_patcheras = True
        self._ocultar_fantasmas = True
        self._filtro_tipos = set()  # vacío = "Todos"
        self.modo_seleccion = modo_seleccion
        self._on_seleccionar_cb = on_seleccionar
        self._filas_completas = []
        self._ids_resaltar = set()
        self._ubicaciones = {}
        self._botones_tipo = {}

        titulo = _("Equipos")
        if filtro_pendiente == "sin_conectores":
            titulo = _("Equipos — Sin conectores")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Equipos — Sin imagen")
        elif filtro_pendiente == "sin_img_conectores":
            titulo = _("Equipos — Sin imagen c/ conectores")
        elif filtro_pendiente == "sin_auditar":
            titulo = _("Equipos — Sin auditar")
        elif filtro_pendiente == "sin_manual":
            titulo = _("Equipos — Sin manual")
        elif filtro_pendiente == "sin_configuraciones":
            titulo = _("Equipos — Sin configuraciones")

        raiz = FloatLayout()
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8),
                        size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        raiz.add_widget(root)
        root.add_widget(barra_superior_dialogo(
            titulo, on_atras=lambda: self.dismiss()))

        # ── Barra de búsqueda tipo "pill" + botón de filtros ──
        hb_busqueda = BoxLayout(size_hint_y=None, height=ALTO_ENTRY,
                               spacing=dp(8))
        caja_busq = Tarjeta(clave_color="superficie_alt", radio=dp(22),
                           padding=(dp(12), 0), spacing=dp(8))
        caja_busq.add_widget(IconoImg("buscar", clave_color="texto_sub",
                                     size_hint=(None, 1), width=dp(18)))
        self.entry_filtro = TextInput(
            multiline=False, hint_text=_("Buscar equipo…"),
            background_color=(0, 0, 0, 0), font_size=FUENTE_NORMAL,
            foreground_color=tema.c("texto"),
            hint_text_color=tema.c("texto_sub"), cursor_color=tema.c("primario"),
            padding=(0, dp(10)))
        self.entry_filtro.bind(text=lambda *_a: self._refiltrar())
        caja_busq.add_widget(self.entry_filtro)
        hb_busqueda.add_widget(caja_busq)

        self.btn_filtro = BotonIcono(icono="filtro", clave_icono="texto_sub",
                                     clave_fondo="superficie_alt",
                                     tamano=ALTO_ENTRY)
        self.btn_filtro.bind(on_release=lambda *_a: self._toggle_panel_filtros())
        hb_busqueda.add_widget(self.btn_filtro)
        root.add_widget(hb_busqueda)

        # ── RecycleView de tarjetas ──
        self.rv = RecycleView(do_scroll_x=False, do_scroll_y=True,
                              bar_width=dp(6))
        self._rv_data = []
        _layout = RecycleBoxLayout(
            default_size=(None, _TarjetaEquipoRV.ALTURA),
            default_size_hint=(1, None), size_hint_y=None,
            orientation="vertical", spacing=dp(10),
            padding=(dp(2), dp(6)))
        _layout.bind(minimum_height=_layout.setter("height"))
        self.rv.add_widget(_layout)
        self.rv.viewclass = _TarjetaEquipoRV
        root.add_widget(self.rv)

        # Sin botonera propia: el alta de equipos (rápida, con plantilla
        # de conectores) se hace desde el '+' de la barra de navegación
        # inferior ("Alta rápida de equipo", ver main.py), visible en
        # toda la app — evita duplicar el mismo botón acá.

        # ── Panel de filtros (carrusel de tipos + checkboxes), colapsado
        # por defecto: se muestra/oculta con el botón de filtro de arriba.
        #
        # A propósito, este panel se agrega a `raiz` (FloatLayout) como
        # un OVERLAY flotante anclado justo debajo de la barra de
        # búsqueda — NO como un hijo más del `root` vertical. Si viviera
        # adentro del flujo vertical, abrirlo/cerrarlo obligaría a Kivy a
        # recalcular la posición de TODO lo que está debajo (la lista
        # completa de tarjetas) en cada toque, lo cual se sentía como una
        # demora/varios toques para que el panel "aparezca" en pantallas
        # con muchos equipos. Como overlay, se dibuja encima de la lista
        # sin mover ni remedir nada más: el cambio es inmediato.
        #
        # La altura es una CONSTANTE fija (la suma de sus dos filas, que
        # ya tienen alto fijo) para no depender del cálculo diferido de
        # minimum_height de Kivy. ──
        ALTO_FILA_TIPOS = dp(38)
        ALTO_FILA_CHECKS = dp(30)
        ESPACIADO_PANEL = dp(6)
        PADDING_PANEL = (dp(8), dp(6))
        self._alto_panel_filtros = (ALTO_FILA_TIPOS + ESPACIADO_PANEL
                                    + ALTO_FILA_CHECKS + PADDING_PANEL[1] * 2)

        self.panel_filtros = BoxLayout(orientation="vertical",
                                       size_hint=(None, None), height=0,
                                       spacing=ESPACIADO_PANEL,
                                       padding=PADDING_PANEL)
        self.panel_filtros.opacity = 0
        self.panel_filtros.disabled = True
        with self.panel_filtros.canvas.before:
            self._c_fondo_panel = Color(*tema.c("bg"))
            self._rect_fondo_panel = Rectangle(pos=self.panel_filtros.pos,
                                               size=self.panel_filtros.size)
        self.panel_filtros.bind(
            pos=lambda w, *_a: setattr(self._rect_fondo_panel, "pos", w.pos),
            size=lambda w, *_a: setattr(self._rect_fondo_panel, "size", w.size))

        self._scroll_tipos = ScrollView(size_hint_y=None,
                                        height=ALTO_FILA_TIPOS,
                                        do_scroll_y=False, bar_width=dp(3))
        self._box_tipos = BoxLayout(size_hint=(None, None),
                                    height=ALTO_FILA_TIPOS, spacing=dp(8))
        self._box_tipos.bind(minimum_width=self._box_tipos.setter("width"))
        self._scroll_tipos.add_widget(self._box_tipos)
        self.panel_filtros.add_widget(self._scroll_tipos)

        # Ambos checkboxes juntos, en la misma fila.
        hb_chk = BoxLayout(size_hint_y=None, height=ALTO_FILA_CHECKS,
                          spacing=dp(16))
        self.chk_patcheras = CheckBox(active=True, size_hint_x=None,
                                      width=dp(32))
        self.chk_patcheras.bind(active=self._on_toggle_patcheras)
        hb_chk.add_widget(self.chk_patcheras)
        hb_chk.add_widget(Label(text=_("Ocultar patcheras"), halign="left",
                               valign="middle", font_size=FUENTE_CHICA,
                               color=tema.c("texto"), size_hint_x=None,
                               width=dp(128)))
        self.chk_fantasmas = CheckBox(active=True, size_hint_x=None,
                                      width=dp(32))
        self.chk_fantasmas.bind(active=self._on_toggle_fantasmas)
        hb_chk.add_widget(self.chk_fantasmas)
        hb_chk.add_widget(Label(text=_("Ocultar fantasmas"), halign="left",
                               valign="middle", font_size=FUENTE_CHICA,
                               color=tema.c("texto")))
        self.panel_filtros.add_widget(hb_chk)

        raiz.add_widget(self.panel_filtros)

        def _reposicionar_panel_filtros(*_a):
            self.panel_filtros.width = hb_busqueda.width
            self.panel_filtros.x = hb_busqueda.x
            self.panel_filtros.top = hb_busqueda.y
        self._reposicionar_panel_filtros = _reposicionar_panel_filtros
        hb_busqueda.bind(pos=_reposicionar_panel_filtros,
                         size=_reposicionar_panel_filtros)
        _reposicionar_panel_filtros()

        super().__init__(title="", separator_height=0, content=raiz,
                         size_hint=(1, 1), **kwargs)
        self.cargar_datos()

    def _toggle_panel_filtros(self):
        if self.panel_filtros.height == 0:
            self.panel_filtros.height = self._alto_panel_filtros
            self.panel_filtros.opacity = 1
            self.panel_filtros.disabled = False
        else:
            self.panel_filtros.height = 0
            self.panel_filtros.opacity = 0
            self.panel_filtros.disabled = True
        # El panel crece hacia abajo desde el borde inferior de la barra
        # de búsqueda: al cambiar la altura hay que re-anclar el borde
        # superior (Kivy no lo hace solo, .top = .y + .height).
        self._reposicionar_panel_filtros()

    def _on_toggle_patcheras(self, _chk, valor):
        self._ocultar_patcheras = valor
        self._refiltrar()

    def _on_toggle_fantasmas(self, _chk, valor):
        self._ocultar_fantasmas = valor
        self._refiltrar()

    def _poblar_carrusel_tipos(self):
        """Pastillas 'Todos' + una por cada tipo de equipo presente en el
        listado actual. Cada pastilla se prende/apaga de forma
        independiente y pueden estar activas varias a la vez (relación
        OR — ej. 'Consola' + 'Monitor' muestra equipos de ambas
        categorías). 'Todos' es la excepción: tocarla limpia cualquier
        selección de tipo."""
        self._box_tipos.clear_widgets()
        self._botones_tipo = {}
        tipos = sorted({s(f[4]) for f in self._filas_completas if s(f[4])})

        def _chip(etiqueta, valor):
            b = _PastillaFiltro(etiqueta)
            b.bind(on_release=lambda *_a, v=valor: self._on_filtro_tipo(v))
            self._box_tipos.add_widget(b)
            self._botones_tipo[valor] = b

        _chip(_("Todos"), None)
        for tipo in tipos:
            _chip(tipo, tipo)
        self._sincronizar_chips_tipo()

    def _sincronizar_chips_tipo(self):
        """Fuerza el estado visual (color=activo / gris=inactivo) de
        todas las pastillas según self._filtro_tipos — se llama después
        de cada toque para que 'Todos' y el resto nunca queden
        inconsistentes entre sí."""
        todos_activo = not self._filtro_tipos
        for valor, boton in self._botones_tipo.items():
            activo = todos_activo if valor is None else valor in self._filtro_tipos
            boton.set_activo(activo)

    def _on_filtro_tipo(self, valor):
        if valor is None:
            self._filtro_tipos = set()
        elif valor in self._filtro_tipos:
            self._filtro_tipos.discard(valor)
        else:
            self._filtro_tipos.add(valor)
        self._sincronizar_chips_tipo()
        self._refiltrar()

    def cargar_datos(self):
        self._ids_resaltar = set()
        if self._filtro_pendiente == "sin_conectores":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector WHERE id_equipo=equipo.id_equipo)")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 AND id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_img_conectores":
            rows = Modelo._query(
                "SELECT e.id_equipo FROM equipo e WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector c "
                "WHERE c.id_equipo=e.id_equipo AND c.id_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_auditar":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND (ultima_auditoria_fecha IS NULL OR ultima_auditoria_fecha = '')")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_manual":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND (path_manual IS NULL OR TRIM(path_manual) = '')")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_configuraciones":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND (configuraciones IS NULL OR TRIM(configuraciones) = '')")
            self._ids_resaltar = {str(r[0]) for r in rows}
        self._filas_completas = Modelo.devolver_equipos_tarjetas()
        self._ubicaciones = Modelo.devolver_ubicaciones_equipos()
        self._poblar_carrusel_tipos()
        self._refiltrar()

    def _es_fantasma(self, marca, modelo, picon, n_con):
        """Heurística de 'equipo fantasma': un registro creado pero nunca
        completado (sin marca, sin modelo, sin ícono y sin conectores)."""
        return not marca and not modelo and not picon and int(n_con or 0) == 0

    def _refiltrar(self):
        txt = self.entry_filtro.text.lower().strip() if hasattr(
            self, "entry_filtro") else ""
        data = []
        for fila in self._filas_completas:
            (id_eq, nombre, marca, modelo, tipo, picon, n_con, n_cx,
             n_patch, auditado) = fila
            id_eq, nombre, marca, modelo, tipo, picon = (
                s(id_eq), s(nombre), s(marca), s(modelo), s(tipo), s(picon))
            if self._ocultar_patcheras and "PATCHERA" in tipo.upper():
                continue
            if self._ocultar_fantasmas and self._es_fantasma(
                    marca, modelo, picon, n_con):
                continue
            if self._filtro_tipos and tipo not in self._filtro_tipos:
                continue
            if txt and txt not in f"{nombre} {marca} {modelo} {tipo}".lower():
                continue
            if self._filtro_pendiente and self._ids_resaltar:
                if id_eq not in self._ids_resaltar:
                    continue
            sub = " · ".join(v for v in (marca, tipo, modelo) if v)
            ruta_picon = os.path.join(PICON_DIR, picon) if picon else ""
            data.append({
                "fila_id": id_eq,
                "nombre": nombre,
                "subtitulo": sub,
                "ubicacion": self._ubicaciones.get(id_eq, ""),
                "picon_ruta": ruta_picon,
                "tipo": tipo,
                "chip_texto": _("Auditado") if auditado else _("No auditado"),
                "chip_color": "exito" if auditado else "alerta",
                "n_con": n_con or 0,
                "n_cx": n_cx or 0,
                "n_patch": n_patch or 0,
                "popup_ref": self,
            })
        self._rv_data = data
        self.rv.data = self._rv_data

    def _fila_datos(self, fila_id):
        return next((f for f in self._filas_completas if s(f[0]) == fila_id),
                   None)

    def _tap_tarjeta(self, fila_id):
        if self.modo_seleccion:
            fila = self._fila_datos(fila_id)
            nombre = s(fila[1]) if fila else ""
            if self._on_seleccionar_cb:
                self._on_seleccionar_cb(fila_id, nombre, fila)
            self.dismiss()
        else:
            self.editar(fila_id)

    def _ver_imagen_completa(self, ruta, nombre=""):
        """Abre el picon de una tarjeta en pantalla completa con zoom
        (gesto: mantener presionada la imagen de la tarjeta)."""
        from widgets_base import VisorImagenZoom

        box = BoxLayout(orientation="vertical")
        popup = Popup(title="", separator_height=0, size_hint=(1, 1))
        box.add_widget(barra_superior_dialogo(
            nombre or _("Imagen"), on_atras=lambda: popup.dismiss()))
        visor = VisorImagenZoom()
        box.add_widget(visor)
        popup.content = box
        popup.open()
        visor.set_imagen(ruta)
        Clock.schedule_once(lambda *_a: visor._zoom_fit(), 0.2)

    def nuevo(self):
        DialogoEquipo(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoEquipo(id_equipo=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_equipo(id_)


# ─── Diálogo de Equipo ────────────────────────────────────────────────────────

class DialogoEquipo(Popup):
    def __init__(self, id_equipo=None, on_guardado=None, **kwargs):
        titulo_base = _("Editar Equipo") if id_equipo else _("Nuevo Equipo")
        self.id_equipo = id_equipo
        self.id_imagen = ""
        self.picon = ""
        self._on_guardado = on_guardado

        raiz = BoxLayout(orientation="vertical")

        # ── Barra superior: atrás + título + menú (solo si ya existe) ──
        raiz.add_widget(barra_superior_dialogo(
            titulo_base, on_atras=lambda: self.dismiss(),
            on_mas=self._abrir_menu_mas if id_equipo else None))

        # ── Tab "Acciones": lista de accesos con ícono + chevron ──
        scroll_acciones = ScrollView()
        box_acciones = BoxLayout(orientation="vertical", spacing=dp(8),
                                 padding=dp(10), size_hint_y=None)
        box_acciones.bind(minimum_height=box_acciones.setter("height"))

        if id_equipo:
            box_acciones.add_widget(Label(
                text=_("Acciones rápidas"), bold=True, font_size=FUENTE_NORMAL,
                color=tema.c("texto"), halign="left", valign="middle",
                size_hint_y=None, height=dp(24)))
            acciones = [
                ("conector", _("Ver conectores"),
                 _("Ver y gestionar conectores"), self._ver_conectores),
                ("editar", _("Edición masiva de conectores"),
                 _("Editar posición de varios conectores"),
                 lambda *_a: self._editor_masivo_conectores()),
                ("patchera", _("Ver patcheras"),
                 _("Patcheras donde está conectado"), self._ver_patcheras),
                ("diagrama", _("Diagrama de conexiones"),
                 _("Ver diagrama de conexiones"),
                 lambda *_a: self._ver_diagrama()),
                ("arbol", _("Árbol de conexiones"),
                 _("Explorar conexiones en árbol"),
                 self._ver_arbol_conexiones),
                ("imagen", _("Imagen con conectores"),
                 _("Ver imagen del equipo"), self._ver_imagen_conectores),
                ("conexiones", _("Conexiones del equipo"),
                 _("Listado de conexiones"), self._ver_conexiones_equipo),
                ("cables", _("Cables del equipo"),
                 _("Cables conectados"), self._ver_cables_equipo),
                ("ubicacion", _("Ver ubicación"),
                 _("Ubicación física del equipo"), self._sel_coordenadas),
            ]
            for icono, titulo_a, subtitulo_a, cb in acciones:
                fila = FilaAccion(icono, titulo_a, subtitulo_a)
                fila.bind(on_release=cb)
                box_acciones.add_widget(fila)

            # ── Resumen: contadores rápidos del equipo ──
            box_acciones.add_widget(Label(
                text=_("Resumen"), bold=True, font_size=FUENTE_NORMAL,
                color=tema.c("texto"), halign="left", valign="middle",
                size_hint_y=None, height=dp(24)))
            resumen = Tarjeta(orientation="vertical", size_hint_y=None,
                             padding=dp(4))
            resumen.bind(minimum_height=resumen.setter("height"))
            for etiqueta_r, valor_r in self._resumen_equipo(id_equipo):
                fila_r = BoxLayout(size_hint_y=None, height=dp(34),
                                  padding=(dp(10), 0))
                fila_r.add_widget(Label(
                    text=etiqueta_r, font_size=FUENTE_CHICA,
                    color=tema.c("texto_sub"), halign="left", valign="middle"))
                lbl_v = Label(text=str(valor_r), bold=True,
                             font_size=FUENTE_NORMAL, color=tema.c("texto"),
                             halign="right", valign="middle",
                             size_hint_x=None, width=dp(90))
                lbl_v.bind(size=lambda w, *_a: setattr(
                    w, "text_size", (w.width, w.height)))
                fila_r.add_widget(lbl_v)
                resumen.add_widget(fila_r)
            box_acciones.add_widget(resumen)
        else:
            fila_ubic = FilaAccion(
                "ubicacion", _("Ver ubicación"),
                _("Ubicación física del equipo"))
            fila_ubic.bind(on_release=self._sel_coordenadas)
            box_acciones.add_widget(fila_ubic)
            box_acciones.add_widget(Label(
                text=_("Guardá el equipo para ver más acciones."),
                font_size=FUENTE_CHICA, color=tema.c("texto_sub"),
                size_hint_y=None, height=dp(30)))

        scroll_acciones.add_widget(box_acciones)

        # ── Tab "Datos": formulario básico ──
        scroll_datos = ScrollView()
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")

        fila_etiqueta(g, _("Ícono (picon):"))
        ALTO_PICON_PREVIEW = dp(56)
        hb_picon = BoxLayout(size_hint_y=None, height=ALTO_PICON_PREVIEW,
                            spacing=dp(8))
        self._picon_preview_caja = FloatLayout(
            size_hint=(None, None),
            size=(ALTO_PICON_PREVIEW, ALTO_PICON_PREVIEW))
        with self._picon_preview_caja.canvas.before:
            Color(*tema.c("secundario_bg"))
            self._picon_preview_rect = RoundedRectangle(
                pos=self._picon_preview_caja.pos,
                size=self._picon_preview_caja.size, radius=[dp(12)])
        self._picon_preview_caja.bind(
            pos=lambda w, *_a: setattr(self._picon_preview_rect, "pos", w.pos),
            size=lambda w, *_a: setattr(self._picon_preview_rect, "size", w.size))
        self._picon_preview_fallback = IconoImg(
            "equipos", clave_color="primario", size_hint=(None, None),
            size=(dp(24), dp(24)), pos_hint={"center_x": 0.5, "center_y": 0.5})
        self._picon_preview_caja.add_widget(self._picon_preview_fallback)
        self._picon_preview_img = None
        hb_picon.add_widget(self._picon_preview_caja)
        self.e_picon = entry_selector()
        btn_picon = Button(text="…", size_hint_x=None, width=dp(44),
                          font_size=FUENTE_NORMAL)
        btn_picon.bind(on_release=self._sel_picon)
        hb_picon.add_widget(self.e_picon); hb_picon.add_widget(btn_picon)
        g.add_widget(hb_picon)

        fila_etiqueta(g, _("Marca:"))
        hb_marca = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_marca = entry_selector()
        btn_marca = Button(text="…", size_hint_x=None, width=dp(44),
                          font_size=FUENTE_NORMAL)
        btn_marca.bind(on_release=self._sel_marca)
        hb_marca.add_widget(self.e_marca); hb_marca.add_widget(btn_marca)
        g.add_widget(hb_marca)

        fila_etiqueta(g, _("Tipo:"))
        hb_tipo = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_tipo = entry_selector()
        btn_tipo = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_tipo.bind(on_release=self._sel_tipo)
        hb_tipo.add_widget(self.e_tipo); hb_tipo.add_widget(btn_tipo)
        g.add_widget(hb_tipo)

        fila_etiqueta(g, _("Modelo:"))
        self.e_modelo = fila_entry(g, "")
        fila_etiqueta(g, _("Inventario:"))
        self.e_inventario = fila_entry(g, "")
        fila_etiqueta(g, _("Serie:"))
        self.e_serie = fila_entry(g, "")

        fila_etiqueta(g, _("Imagen:"))
        hb_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_imagen = entry_selector()
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=self._sel_imagen)
        hb_img.add_widget(self.e_imagen); hb_img.add_widget(btn_img)
        g.add_widget(hb_img)

        # Coord X/Y en una misma fila (dos campos chicos entran bien juntos)
        fila_etiqueta(g, _("Coordenadas en imagen (X, Y):"))
        hb_coords = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_x = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_y = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        hb_coords.add_widget(self.e_x); hb_coords.add_widget(self.e_y)
        g.add_widget(hb_coords)

        fila_etiqueta(g, _("Manual (PDF):"))
        hb_man = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_manual = entry_selector()
        btn_sel_manual = Button(text="…", size_hint_x=None, width=dp(44),
                               font_size=FUENTE_NORMAL)
        btn_sel_manual.bind(on_release=self._sel_manual)
        btn_ver_manual = Button(text=_("Ver"), size_hint_x=None,
                               width=dp(70), font_size=FUENTE_CHICA)
        btn_ver_manual.bind(on_release=self._ver_manual)
        hb_man.add_widget(self.e_manual)
        hb_man.add_widget(btn_sel_manual)
        hb_man.add_widget(btn_ver_manual)
        g.add_widget(hb_man)

        box_datos = BoxLayout(orientation="vertical", size_hint_y=None,
                             padding=dp(10))
        box_datos.bind(minimum_height=box_datos.setter("height"))
        box_datos.add_widget(seccion_tarjeta(_("Datos básicos"), g,
                                             icono="equipos"))
        scroll_datos.add_widget(box_datos)

        # ── Tab "Configuración" ──
        # Ocupa todo el espacio disponible de la tab (sin ScrollView
        # propio: el contenido interno -vista previa o editor- ya se
        # desplaza solo); así la tarjeta llega hasta abajo en vez de
        # quedar con una altura fija que la corta antes de tiempo.
        box_conf = BoxLayout(orientation="vertical", spacing=dp(8),
                            padding=dp(10))
        box_conf.add_widget(Label(
            text=_("Configuración"), bold=True, font_size=FUENTE_CHICA,
            color=tema.c("texto_sub"), halign="left", valign="middle",
            size_hint_y=None, height=dp(22)))

        self.tv_configuraciones = TextInput(multiline=True,
                                            font_size=FUENTE_NORMAL)
        # size_hint=(None, None) + text_size=(None, None): el Label crece
        # a su ancho/alto natural sin recortar/ajustar línea (sin word
        # wrap), y el ScrollView permite desplazarlo en ambos ejes.
        self.lbl_preview = Label(markup=True, halign="left", valign="top",
                                 size_hint=(None, None), font_size=FUENTE_NORMAL)
        self.lbl_preview.text_size = (None, None)
        self.lbl_preview.bind(texture_size=lambda *_a: setattr(
            self.lbl_preview, "size", self.lbl_preview.texture_size))
        self.scroll_preview = ScrollView(do_scroll_x=True, do_scroll_y=True,
                                         bar_width=dp(8))
        self.scroll_preview.add_widget(self.lbl_preview)

        self._tarjeta_conf = Tarjeta(orientation="vertical", padding=dp(8))
        self._tarjeta_conf.add_widget(self.scroll_preview)
        box_conf.add_widget(self._tarjeta_conf)

        self.btn_edit_config = Button(text=_("Editar"),
                                      size_hint_y=None, height=ALTO_BOTON,
                                      font_size=FUENTE_NORMAL)
        self.btn_edit_config.bind(on_release=self._toggle_edit_configuraciones)
        box_conf.add_widget(self.btn_edit_config)
        self._modo_edicion_config = False

        # Cargar datos si es edición (los campos ya existen; se completan
        # ANTES de armar la tarjeta de encabezado, que los necesita).
        if id_equipo:
            rows = Modelo.devolver_equipo(id_equipo)
            if rows:
                r = rows[0]
                self.e_nombre.text = s(r[1])
                self.e_marca.text = s(r[2])
                self.id_marca = s(r[6])
                self.e_modelo.text = s(r[3])
                self.e_inventario.text = s(r[4])
                self.e_serie.text = s(r[5])
                self.e_tipo.text = s(r[7])
                self.id_tipo = s(r[8])
                self.e_imagen.text = s(r[9])
                self.id_imagen = s(r[10])
                self.e_x.text = s(r[11])
                self.e_y.text = s(r[12])
                self.e_manual.text = s(r[13])
                if r[14]:
                    self.tv_configuraciones.text = s(r[14])
                if len(r) > 15 and r[15]:
                    self.picon = s(r[15])
                    self.e_picon.text = self.picon
        if not hasattr(self, "id_marca"):
            self.id_marca = ""
        if not hasattr(self, "id_tipo"):
            self.id_tipo = ""

        self._actualizar_picon_preview()
        self._render_preview()

        # ── Tarjeta de encabezado (ícono + nombre + subtítulo + chip) ──
        fecha_aud = (Modelo.devolver_fecha_ultima_auditoria(
            "equipo", "id_equipo", id_equipo) if id_equipo else None)
        subtitulo = " · ".join(
            v for v in (self.e_marca.text, self.e_tipo.text, self.e_modelo.text)
            if v.strip())
        raiz.add_widget(tarjeta_encabezado(
            "equipos", self.e_nombre.text or titulo_base, subtitulo,
            chip_texto=(_("Auditado") if fecha_aud else _("Sin auditar"))
                      if id_equipo else None,
            chip_color="exito" if fecha_aud else "alerta",
            linea_extra=self._ubicacion_equipo(id_equipo) if id_equipo
                       else None))

        # ── Tabs subrayadas + contenedor que intercambia el contenido ──
        contenedores = [scroll_acciones, scroll_datos, box_conf]
        cont_visible = BoxLayout(orientation="vertical")
        cont_visible.add_widget(contenedores[0])

        tabs = BarraTabs([_("Acciones"), _("Datos"), _("Configuración")])

        def _cambiar_tab(idx):
            cont_visible.clear_widgets()
            cont_visible.add_widget(contenedores[idx])

        tabs.on_cambiar = _cambiar_tab

        raiz.add_widget(tabs)
        raiz.add_widget(cont_visible)

        lbl_aud, btn_aud = fila_auditoria(
            "equipo", "id_equipo", id_equipo,
            on_marcado=self._preguntar_auditar_conexiones)
        if lbl_aud:
            raiz.add_widget(lbl_aud)

        botones = []
        if btn_aud:
            botones.append({"texto": _("Auditado"), "icono": "lupa_check",
                           "estilo": "terciario",
                           "on_release": lambda: btn_aud.dispatch("on_release")})
        botones.append({"texto": _("Cancelar"), "icono": "cerrar",
                       "estilo": "secundario",
                       "on_release": lambda: self.dismiss()})
        botones.append({"texto": _("Aceptar"), "icono": "guardar",
                       "estilo": "primario", "on_release": self._guardar})
        raiz.add_widget(fila_botones_pill(botones))

        super().__init__(title="", separator_height=0, content=raiz,
                         size_hint=(1, 1), **kwargs)

    # ── Resumen (tab Acciones) ──
    def _ubicacion_equipo(self, id_equipo):
        """Texto 'Sala · Rack · Frame' para la tarjeta de encabezado.
        El equipo puede estar en un rack directamente, dentro de un
        frame montado en un rack, o suelto en una sala — se prueban
        las tres formas y se arma con lo que haya."""
        try:
            filas = Modelo._query(
                "SELECT s.nombre, r.nombre, f.nombre "
                "FROM posicion_en_rack pr "
                "LEFT JOIN rack r ON r.id_rack = pr.id_rack "
                "LEFT JOIN frame f ON f.id_frame = pr.id_frame "
                "LEFT JOIN rack_por_sala rps ON rps.id_rack = pr.id_rack "
                "LEFT JOIN sala s ON s.id_sala = rps.id_sala "
                "WHERE pr.id_equipo=? LIMIT 1", (id_equipo,))
            if not filas:
                filas = Modelo._query(
                    "SELECT s.nombre, r.nombre, f.nombre "
                    "FROM slot sl "
                    "JOIN posicion_en_rack pr ON pr.id_frame = sl.id_frame "
                    "LEFT JOIN rack r ON r.id_rack = pr.id_rack "
                    "LEFT JOIN frame f ON f.id_frame = sl.id_frame "
                    "LEFT JOIN rack_por_sala rps ON rps.id_rack = pr.id_rack "
                    "LEFT JOIN sala s ON s.id_sala = rps.id_sala "
                    "WHERE sl.id_equipo=? LIMIT 1", (id_equipo,))
            if filas:
                sala, rack, frame = (s(v) for v in filas[0])
                return " · ".join(v for v in (sala, rack, frame) if v)
            filas = Modelo._query(
                "SELECT s.nombre FROM equiponoraqueable_por_sala en "
                "JOIN sala s ON s.id_sala = en.id_sala "
                "WHERE en.id_equipo=? LIMIT 1", (id_equipo,))
            if filas:
                return s(filas[0][0])
        except Exception:
            pass
        return ""

    def _resumen_equipo(self, id_equipo):
        """(etiqueta, valor) para la tarjeta 'Resumen' del tab Acciones."""
        def _contar(sql, params=()):
            try:
                r = Modelo._query(sql, params)
                return r[0][0] if r else 0
            except Exception:
                return 0

        n_conectores = _contar(
            "SELECT COUNT(*) FROM conector WHERE id_equipo=?", (id_equipo,))
        n_conexiones = _contar(
            "SELECT COUNT(*) FROM conexion WHERE id_conector IN "
            "(SELECT id_conector FROM conector WHERE id_equipo=?)",
            (id_equipo,))
        n_cables = _contar(
            "SELECT COUNT(DISTINCT id_cable) FROM conexion WHERE "
            "id_conector IN (SELECT id_conector FROM conector "
            "WHERE id_equipo=?)", (id_equipo,))
        n_patcheras = _contar(
            "SELECT COUNT(DISTINCT e2.id_equipo) FROM conector c1 "
            "JOIN conexion cx1 ON cx1.id_conector = c1.id_conector "
            "JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
            "  AND cx2.id_conector != cx1.id_conector "
            "JOIN conector c2 ON c2.id_conector = cx2.id_conector "
            "JOIN equipo e2 ON e2.id_equipo = c2.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e2.id_tipo_equipo "
            "WHERE c1.id_equipo=? AND te.nombre='MODULO PATCHERA'",
            (id_equipo,))
        fecha_aud = Modelo.devolver_fecha_ultima_auditoria(
            "equipo", "id_equipo", id_equipo) or _("nunca")
        return [
            (_("Conectores"), n_conectores),
            (_("Conexiones activas"), n_conexiones),
            (_("Cables conectados"), n_cables),
            (_("Patcheras"), n_patcheras),
            (_("Última auditoría"), fecha_aud),
        ]

    # ── Menú "⋮" de la barra superior ──
    def _abrir_menu_mas(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(14))
        popup = Popup(title=_("Equipo"), content=box, size_hint=(0.85, 0.32))
        btn_eliminar = Button(text=_("Eliminar equipo"),
                             font_size=FUENTE_NORMAL, size_hint_y=None,
                             height=ALTO_BOTON)

        def _confirmar_eliminar(*_a):
            popup.dismiss()

            def _si():
                Modelo.eliminar_equipo(self.id_equipo)
                self.dismiss()
                if self._on_guardado:
                    self._on_guardado()

            confirmar(_("¿Eliminar este equipo? Esta acción no se puede "
                      "deshacer."), on_si=_si)

        btn_eliminar.bind(on_release=_confirmar_eliminar)
        box.add_widget(btn_eliminar)
        popup.open()

    # ── Configuraciones (markdown simple) ──
    def _render_preview(self):
        self.lbl_preview.text = renderizar_markdown_simple(
            self.tv_configuraciones.text)

    def _toggle_edit_configuraciones(self, *_a):
        self._modo_edicion_config = not self._modo_edicion_config
        self._tarjeta_conf.clear_widgets()
        if self._modo_edicion_config:
            self.btn_edit_config.text = _("Guardar y Ver")
            self._tarjeta_conf.add_widget(self.tv_configuraciones)
        else:
            self._render_preview()
            self.btn_edit_config.text = _("Editar")
            self._tarjeta_conf.add_widget(self.scroll_preview)

    # ── Selectores ──
    def _sel_picon(self, *_a):
        os.makedirs(PICON_DIR, exist_ok=True)

        def _elegido(ruta):
            nombre = os.path.basename(ruta)
            destino = os.path.join(PICON_DIR, nombre)
            if os.path.abspath(ruta) != os.path.abspath(destino):
                try:
                    import shutil
                    shutil.copy2(ruta, destino)
                except Exception as e:
                    mostrar_error(_("Error al copiar el ícono: {}").format(e))
                    return
            self.picon = nombre
            self.e_picon.text = nombre
            self._actualizar_picon_preview()

        FileChooserPopup(
            titulo=_("Seleccionar ícono (picon)"), ruta_inicial=PICON_DIR,
            filtros=["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp"],
            on_seleccionar=_elegido).open()

    def _actualizar_picon_preview(self):
        if self._picon_preview_img is not None and self._picon_preview_img.parent:
            self._picon_preview_caja.remove_widget(self._picon_preview_img)
            self._picon_preview_img = None
        if self._picon_preview_fallback.parent:
            self._picon_preview_caja.remove_widget(self._picon_preview_fallback)

        ruta = os.path.join(PICON_DIR, self.picon) if self.picon else ""
        if ruta and os.path.exists(ruta):
            try:
                self._picon_preview_img = Image(
                    source=ruta, size_hint=(1, 1),
                    pos_hint={"x": 0, "y": 0}, fit_mode="cover",
                    allow_stretch=True)
                self._picon_preview_caja.add_widget(self._picon_preview_img)
                return
            except Exception:
                self._picon_preview_img = None
        self._picon_preview_caja.add_widget(self._picon_preview_fallback)

    def _sel_marca(self, *_a):
        from pantallas_catalogos import MarcasListado

        def _con_marca(id_, nombre, _f):
            self.id_marca = id_
            self.e_marca.text = nombre
        MarcasListado(modo_seleccion=True, on_seleccionar=_con_marca).open()

    def _sel_tipo(self, *_a):
        from pantallas_catalogos import TiposEquipoListado

        def _con_tipo(id_, nombre, _f):
            self.id_tipo = id_
            self.e_tipo.text = nombre
        TiposEquipoListado(modo_seleccion=True, on_seleccionar=_con_tipo).open()

    def _sel_imagen(self, *_a):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_, nombre, _f):
            self.id_imagen = id_
            self.e_imagen.text = nombre
        ImagenesListado(modo_seleccion=True, on_seleccionar=_con_imagen).open()

    def _sel_manual(self, *_a):
        os.makedirs(MANUALES_DIR, exist_ok=True)


        def _elegido(ruta):
            filename = os.path.basename(ruta)
            dest = os.path.join(MANUALES_DIR, filename)
            if os.path.abspath(ruta) != os.path.abspath(dest):
                try:
                    import shutil
                    shutil.copy2(ruta, dest)
                except Exception as e:
                    mostrar_error(f"Error al copiar el archivo: {e}")
                    return
            self.e_manual.text = filename

        FileChooserPopup(titulo=_("Seleccionar Manual PDF"),
                         ruta_inicial=MANUALES_DIR, filtros=["*.pdf", "*.PDF"],
                         on_seleccionar=_elegido).open()

    def _ver_manual(self, *_a):
        nombre = self.e_manual.text.strip()
        if not nombre:
            mostrar_info(_("No hay manual PDF seleccionado"))
            return
        ruta = os.path.join(MANUALES_DIR, nombre)
        if not os.path.isfile(ruta):
            mostrar_error(_("Archivo no encontrado:\n{}").format(ruta))
            return
        try:
            if os.name == "posix":
                for cmd in ["xdg-open", "evince", "okular", "firefox",
                           "google-chrome"]:
                    try:
                        subprocess.Popen([cmd, ruta], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    raise FileNotFoundError(_("No se encontró un visor de PDF instalado."))
            elif os.name == "nt":
                os.startfile(ruta)
            else:
                subprocess.Popen(["open", ruta])
        except Exception as e:
            mostrar_error(_("Error al abrir el PDF: {}").format(e))

    def _ver_conectores(self, *_a):
        from pantallas_conectores import ConectoresListado
        ConectoresListado(id_equipo=self.id_equipo).open()

    def _ver_imagen_conectores(self, *_a):
        from pantallas_avanzadas import abrir_imagen_conectores
        abrir_imagen_conectores(self.id_equipo)

    def _ver_arbol_conexiones(self, *_a):
        from pantallas_avanzadas import abrir_arbol_conexiones
        abrir_arbol_conexiones(self.id_equipo)

    def _ver_patcheras(self, *_a):
        from pantallas_vistas import PatcherasVista
        PatcherasVista(id_equipo=self.id_equipo,
                      nombre_equipo=self.e_nombre.text.strip()).open()

    def _sel_coordenadas(self, *_a):
        from pantallas_avanzadas import CoordenadasImagenSeleccion

        if not self.id_imagen:
            mostrar_info(_("Primero elegí una imagen del equipo (botón «…» "
                          "junto a Imagen) para poder marcar su ubicación."))
            return

        def _con_coords(resultado):
            self.e_x.text = resultado["x"]
            self.e_y.text = resultado["y"]

        CoordenadasImagenSeleccion(
            id_imagen=self.id_imagen, solo_xy=True,
            x=self.e_x.text, y=self.e_y.text,
            on_aceptar=_con_coords).open()

    def _renombrar_conectores(self, *_a):
        from pantallas_conectores import DialogoRenombrarConectores
        DialogoRenombrarConectores(id_equipo=self.id_equipo).open()

    def _editor_masivo_conectores(self, *_a):
        from pantallas_editores_masivos import abrir_editor_masivo_conectores
        abrir_editor_masivo_conectores(self.id_equipo)

    def _ver_diagrama(self, *_a):
        from pantallas_diagrama import abrir_diagrama_conexiones
        abrir_diagrama_conexiones(id_equipo=self.id_equipo)

    def _ver_conexiones_equipo(self, *_a):
        from pantallas_conexiones import ConexionesListado
        ConexionesListado(id_equipo=self.id_equipo).open()

    def _ver_cables_equipo(self, *_a):
        from pantallas_cables import CablesListado
        CablesListado(id_equipo=self.id_equipo).open()

    def _preguntar_auditar_conexiones(self, fecha):
        """Al marcar el equipo como auditado, ofrece extender la misma
        fecha a todas sus conexiones (mismo criterio que 'auditar
        equipo')."""
        if not self.id_equipo:
            return

        def _si():
            _fecha, cantidad = Modelo.marcar_auditadas_conexiones_de_equipo(
                self.id_equipo, fecha)
            mostrar_info(
                _("Se marcaron {} conexión(es) como auditadas.").format(
                    cantidad))

        confirmar(
            _("¿Marcar también como auditadas todas las conexiones de "
              "este equipo?"),
            on_si=_si)

    def _guardar(self, *_a):
        nombre = self.e_nombre.text.strip()
        if not nombre:
            mostrar_error(_("El nombre del equipo es obligatorio."))
            return
        path_manual = self.e_manual.text.strip()
        configuraciones = self.tv_configuraciones.text.strip()
        args = (
            self.id_tipo or None, self.id_marca or None,
            self.e_inventario.text, self.e_serie.text, self.e_modelo.text,
            nombre, self.id_imagen or None, self.e_x.text, self.e_y.text,
            path_manual if path_manual else None,
            configuraciones if configuraciones else None,
            self.picon or None,
        )
        if self.id_equipo:
            Modelo.modificacion_equipo(self.id_equipo, *args)
        else:
            Modelo.alta_equipo(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ─── Alta Rápida de Equipo (estilo AVwire) ────────────────────────────────────

_COL_IN = (0.11, 0.62, 0.46, 1)
_COL_OUT = (0.33, 0.29, 0.72, 1)


class DialogoAltaRapidaEquipo(Popup):
    def __init__(self, on_guardado=None, **kwargs):
        self._on_guardado = on_guardado
        self.id_tipo = None
        self.id_marca = None
        self._conectores_activos = {}   # (id_tipo_con, dir) -> cantidad
        self._todos_tipos_con = Modelo.devolver_tipos_conectores()
        Modelo.asegurar_tabla_plantillas()

        # En desktop este diálogo era dos paneles lado a lado (form +
        # preview en vivo a la derecha, 40% del ancho). En 360dp eso deja
        # el preview inservible (~140dp) y el form comprimido. Se pasa a
        # una sola columna scrolleable: Tipo → Datos → Conectores →
        # Vista previa/Resumen, todo apilado, con botones fijos abajo.
        outer = BoxLayout(orientation="vertical")
        scroll_todo = ScrollView()
        col = BoxLayout(orientation="vertical", spacing=dp(8),
                       size_hint_y=None, padding=dp(8))
        col.bind(minimum_height=col.setter("height"))
        scroll_todo.add_widget(col)

        col.add_widget(Label(text="[b]1. " + _("Tipo de equipo") + "[/b]",
                             markup=True, size_hint_y=None, height=dp(26),
                             font_size=FUENTE_NORMAL, halign="left"))

        hb_tipo = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_tipo_search = TextInput(multiline=False, font_size=FUENTE_NORMAL,
                                       hint_text=_("Buscar tipo de equipo…"))
        self.e_tipo_search.bind(text=lambda *_a: self._poblar_tipos(
            self.e_tipo_search.text))
        btn_tipo_nuevo = Button(text="+ " + _("Nuevo"), size_hint_x=None,
                               width=dp(90), font_size=FUENTE_CHICA)
        btn_tipo_nuevo.bind(on_release=self._crear_tipo)
        hb_tipo.add_widget(self.e_tipo_search)
        hb_tipo.add_widget(btn_tipo_nuevo)
        col.add_widget(hb_tipo)

        self._box_tipos = BoxLayout(orientation="vertical", spacing=dp(1),
                                    size_hint_y=None, height=dp(140))
        scroll_tipos = ScrollView(size_hint_y=None, height=dp(140))
        scroll_tipos.add_widget(self._box_tipos)
        col.add_widget(scroll_tipos)

        self.lbl_tipo_sel = Label(text=_("Ningún tipo seleccionado"),
                                  italic=True, size_hint_y=None, height=dp(26),
                                  font_size=FUENTE_CHICA, halign="left")
        col.add_widget(self.lbl_tipo_sel)

        col.add_widget(Label(text="[b]2. " + _("Datos del equipo") + "[/b]",
                             markup=True, size_hint_y=None, height=dp(26),
                             font_size=FUENTE_NORMAL, halign="left"))
        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Nombre *:"))
        self.e_nombre = fila_entry(g, "")
        self.e_nombre.bind(text=lambda *_a: self._actualizar_preview())
        fila_etiqueta(g, _("Marca:"))
        hb_marca = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_marca = entry_selector()
        btn_marca = Button(text="…", size_hint_x=None, width=dp(44),
                          font_size=FUENTE_NORMAL)
        btn_marca.bind(on_release=self._sel_marca)
        hb_marca.add_widget(self.e_marca); hb_marca.add_widget(btn_marca)
        g.add_widget(hb_marca)
        fila_etiqueta(g, _("Modelo:"))
        self.e_modelo = fila_entry(g, "")
        fila_etiqueta(g, _("Inventario:"))
        self.e_inventario = fila_entry(g, "")
        fila_etiqueta(g, _("Serie:"))
        self.e_serie = fila_entry(g, "")
        col.add_widget(g)

        col.add_widget(Label(text="[b]3. " + _("Conectores") + "[/b]",
                             markup=True, size_hint_y=None, height=dp(26),
                             font_size=FUENTE_NORMAL, halign="left"))
        lbl_ayuda = Label(
            text=_("Ajustá las cantidades. Cantidad 0 = no se crea. La "
                  "plantilla se guarda por tipo de equipo."),
            italic=True, font_size=FUENTE_CHICA, size_hint_y=None, height=dp(46),
            halign="left", valign="top")
        lbl_ayuda.bind(width=lambda w, *_a: setattr(
            w, "text_size", (w.width, None)))
        col.add_widget(lbl_ayuda)

        self._con_box = BoxLayout(orientation="vertical", spacing=dp(2),
                                  size_hint_y=None)
        self._con_box.bind(minimum_height=self._con_box.setter("height"))
        col.add_widget(self._con_box)

        btn_add_con = Button(text=_("Agregar tipo conector"),
                            size_hint_y=None, height=ALTO_BOTON,
                            font_size=FUENTE_CHICA)
        btn_add_con.bind(on_release=self._agregar_conector_manual)
        col.add_widget(btn_add_con)

        # ── Vista previa / Resumen (antes a la derecha, ahora abajo) ──
        col.add_widget(Label(text="[b]" + _("Vista previa") + "[/b]",
                             markup=True, size_hint_y=None, height=dp(26),
                             font_size=FUENTE_NORMAL, halign="left"))
        self.lbl_prev_nombre = Label(text="—", markup=True, size_hint_y=None,
                                     height=dp(26), font_size=FUENTE_NORMAL,
                                     halign="left")
        col.add_widget(self.lbl_prev_nombre)
        self.lbl_prev_tipo = Label(text=_("tipo no seleccionado"), italic=True,
                                   size_hint_y=None, height=dp(24),
                                   font_size=FUENTE_CHICA, halign="left",
                                   color=(0.6, 0.6, 0.6, 1))
        col.add_widget(self.lbl_prev_tipo)

        self.box_prev_ports = BoxLayout(orientation="vertical", spacing=dp(2),
                                        size_hint_y=None)
        self.box_prev_ports.bind(
            minimum_height=self.box_prev_ports.setter("height"))
        col.add_widget(self.box_prev_ports)

        self.lbl_prev_resumen = Label(size_hint_y=None, height=dp(24),
                                      font_size=FUENTE_CHICA, halign="left",
                                      color=(0.6, 0.6, 0.6, 1))
        col.add_widget(self.lbl_prev_resumen)

        col.add_widget(Label(text="[b]" + _("Resumen") + "[/b]",
                             markup=True, size_hint_y=None, height=dp(26),
                             font_size=FUENTE_NORMAL, halign="left"))
        self.lbl_sum_detail = Label(markup=True, halign="left", valign="top",
                                    color=(0.6, 0.6, 0.6, 1), size_hint_y=None,
                                    height=dp(90), font_size=FUENTE_CHICA)
        self.lbl_sum_detail.bind(width=lambda w, *_a: setattr(
            w, "text_size", (w.width, None)))
        col.add_widget(self.lbl_sum_detail)

        outer.add_widget(scroll_todo)

        # ── Botonera fija abajo (2 filas: no entran 3 botones de texto
        # largo en 360dp de ancho) ──
        box_botones = BoxLayout(orientation="vertical", size_hint_y=None,
                                height=ALTO_BOTON * 2 + dp(4), spacing=dp(4),
                                padding=(dp(8), dp(4)))
        fila_b1 = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_guardar = Button(text=_("Guardar"), font_size=FUENTE_NORMAL)
        btn_dup = Button(text=_("Guardar y duplicar"), font_size=FUENTE_CHICA)
        btn_guardar.bind(on_release=self._on_guardar_click)
        btn_dup.bind(on_release=self._on_guardar_duplicar_click)
        fila_b1.add_widget(btn_guardar)
        fila_b1.add_widget(btn_dup)
        fila_b2 = BoxLayout(size_hint_y=None, height=ALTO_BOTON)
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        fila_b2.add_widget(btn_cancelar)
        box_botones.add_widget(fila_b1)
        box_botones.add_widget(fila_b2)
        outer.add_widget(box_botones)

        super().__init__(title=_("Alta Rápida de Equipo"), content=outer,
                         size_hint=(1, 1), **kwargs)

        self._poblar_tipos("")
        self._actualizar_preview()

    # ── Tipos de equipo ──
    def _poblar_tipos(self, filtro):
        self._box_tipos.clear_widgets()
        todos = Modelo.devolver_todos_los_tipos()
        fl = filtro.lower()
        for id_, nombre in todos:
            if fl and fl not in s(nombre).lower():
                continue
            b = Button(text=s(nombre), size_hint_y=None, height=dp(38),
                      font_size=FUENTE_CHICA, halign="left")
            b.bind(on_release=lambda inst, i=id_, n=nombre:
                  self._on_tipo_seleccionado(i, n))
            self._box_tipos.add_widget(b)

    def _on_tipo_seleccionado(self, id_tipo, nombre_tipo):
        self.id_tipo = id_tipo
        self.lbl_tipo_sel.text = f"{_('Tipo seleccionado')}: {nombre_tipo}"
        self.lbl_tipo_sel.italic = False
        self._cargar_plantilla(id_tipo)
        self._actualizar_preview()

    def _crear_tipo(self, *_a):
        from widgets_base import DialogoNombre

        def _creado(valor):
            Modelo.alta_tipo(valor)
            self._poblar_tipos(self.e_tipo_search.text)
            mostrar_info(_("Tipo creado: {}").format(valor))

        DialogoNombre(_("Nuevo Tipo de Equipo"), on_aceptar=_creado).open()

    # ── Plantilla de conectores ──
    def _cargar_plantilla(self, id_tipo):
        self._conectores_activos = {}
        plantilla = Modelo.devolver_plantillas_conectores(id_tipo)
        if not plantilla:
            filas = ([(s(r[0]), s(r[1]), "IN", 0) for r in self._todos_tipos_con] +
                    [(s(r[0]), s(r[1]), "OUT", 0) for r in self._todos_tipos_con])
        else:
            en_plantilla = {(s(r[0]), s(r[2])) for r in plantilla}
            filas = [(s(r[0]), s(r[1]), s(r[2]), int(r[3])) for r in plantilla]
            for r in self._todos_tipos_con:
                for dir_ in ("IN", "OUT"):
                    if (s(r[0]), dir_) not in en_plantilla:
                        filas.append((s(r[0]), s(r[1]), dir_, 0))

        for id_tc, _n, dir_, qty in filas:
            if qty > 0:
                self._conectores_activos[(id_tc, dir_)] = qty

        self._reconstruir_filas_conectores(filas)

    def _reconstruir_filas_conectores(self, filas):
        self._con_box.clear_widgets()
        filas_sorted = sorted(filas, key=lambda r: (r[3] == 0, r[1], r[2]))
        for id_tc, nombre_tc, dir_, qty in filas_sorted:
            self._con_box.add_widget(
                self._crear_fila_conector(id_tc, nombre_tc, dir_, qty))
        self._actualizar_preview()

    def _crear_fila_conector(self, id_tc, nombre_tc, dir_, qty):
        hb = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        color = _COL_IN if dir_ == "IN" else _COL_OUT
        lbl_dir = Label(text="IN" if dir_ == "IN" else "OUT", color=color,
                       bold=True, size_hint_x=None, width=dp(34),
                       font_size=sp(10))
        hb.add_widget(lbl_dir)
        lbl_n = Label(text=nombre_tc, halign="left", valign="middle",
                     font_size=FUENTE_CHICA, shorten=True, shorten_from="right",
                     color=(1, 1, 1, 1) if qty else (0.55, 0.55, 0.55, 1))
        lbl_n.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        hb.add_widget(lbl_n)
        lbl_d = Label(text=dir_, size_hint_x=None, width=dp(36),
                     font_size=FUENTE_CHICA)
        hb.add_widget(lbl_d)
        spin = SpinnerCantidad(valor=qty, minimo=0, maximo=99,
                              on_change=lambda v, tc=id_tc, d=dir_, l=lbl_n:
                              self._on_spin_changed(v, tc, d, l))
        hb.add_widget(spin)
        return hb

    def _on_spin_changed(self, qty, id_tc, dir_, lbl_n):
        if qty > 0:
            self._conectores_activos[(id_tc, dir_)] = qty
            lbl_n.color = (1, 1, 1, 1)
        else:
            self._conectores_activos.pop((id_tc, dir_), None)
            lbl_n.color = (0.55, 0.55, 0.55, 1)
        self._actualizar_preview()

    def _agregar_conector_manual(self, *_a):
        from pantallas_catalogos import TiposConectorListado

        def _con_tipo(id_tc, nombre, _f):
            def _con_direccion(direccion):
                if (id_tc, direccion) in self._conectores_activos:
                    return
                fila = self._crear_fila_conector(id_tc, nombre, direccion, 1)
                self._con_box.add_widget(fila)
                self._conectores_activos[(id_tc, direccion)] = 1
                self._actualizar_preview()
            DialogoDireccionConector(on_elegido=_con_direccion).open()

        TiposConectorListado(modo_seleccion=True, on_seleccionar=_con_tipo).open()

    # ── Preview ──
    def _actualizar_preview(self, *_a):
        nombre = self.e_nombre.text.strip() or "—"
        self.lbl_prev_nombre.text = f"[b]{nombre}[/b]"

        tipo_txt = self.lbl_tipo_sel.text.replace(
            f"{_('Tipo seleccionado')}: ", "").strip()
        if self.lbl_tipo_sel.italic:
            tipo_txt = _("tipo no seleccionado")
        marca = self.e_marca.text.strip()
        sub = tipo_txt + (f" · {marca}" if marca else "")
        self.lbl_prev_tipo.text = sub

        self.box_prev_ports.clear_widgets()
        n_in = n_out = 0
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next((s(r[1]) for r in self._todos_tipos_con
                             if s(r[0]) == id_tc), "?")
            color = _COL_IN if dir_ == "IN" else _COL_OUT
            signo = "←" if dir_ == "IN" else "→"
            texto = f"{signo} {nombre_tc}" + (f" ×{qty}" if qty > 1 else "")
            lbl = Label(text=texto, color=color, size_hint_y=None,
                       height=dp(24), font_size=FUENTE_CHICA, halign="left")
            self.box_prev_ports.add_widget(lbl)
            if dir_ == "IN":
                n_in += qty
            else:
                n_out += qty

        total_con = sum(self._conectores_activos.values())
        self.lbl_prev_resumen.text = (
            f"{total_con} conectores · {n_in} entradas · {n_out} salidas")
        self.lbl_sum_detail.text = (
            f"Se creará:\n  • 1 equipo: [b]{nombre}[/b]\n"
            f"  • {total_con} conectores ({n_in} IN, {n_out} OUT)\n"
            "  • Imagen y coordenadas: completar luego")

    # ── Selectores ──
    def _sel_marca(self, *_a):
        from pantallas_catalogos import MarcasListado

        def _con_marca(id_, nombre, _f):
            self.id_marca = id_
            self.e_marca.text = nombre
            self._actualizar_preview()
        MarcasListado(modo_seleccion=True, on_seleccionar=_con_marca).open()

    # ── Guardar ──
    def _guardar(self):
        nombre = self.e_nombre.text.strip()
        if not nombre:
            mostrar_error(_("El nombre del equipo es obligatorio."))
            return None

        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo=self.id_tipo or None, id_marca=self.id_marca or None,
            num_inventario=self.e_inventario.text.strip() or None,
            num_serie=self.e_serie.text.strip() or None,
            modelo=self.e_modelo.text.strip() or None, nombre=nombre,
            id_imagen=None, x=None, y=None)

        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next((s(r[1]) for r in self._todos_tipos_con
                             if s(r[0]) == id_tc), "?")
            for i in range(1, qty + 1):
                sufijo = f" {i:02d}" if qty > 1 else ""
                if nombre_tc.strip().upper() == dir_.strip().upper():
                    nombre_con = f"{dir_}{sufijo}"
                else:
                    nombre_con = f"{dir_} {nombre_tc}{sufijo}"
                Modelo.agregar_conector(nombre=nombre_con, id_equipo=id_equipo,
                                       id_tipo_conector=id_tc or None,
                                       id_imagen=None, x=None, y=None)

        if self.id_tipo and self._conectores_activos:
            for (id_tc, dir_), qty in self._conectores_activos.items():
                Modelo.guardar_plantilla_conector(self.id_tipo, id_tc, dir_, qty)

        return id_equipo

    def _limpiar_para_duplicar(self):
        self.e_nombre.text = ""
        self.e_inventario.text = ""
        self.e_serie.text = ""
        self.e_nombre.focus = True

    def _on_guardar_click(self, *_a):
        id_eq = self._guardar()
        if id_eq is None:
            return
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()

    def _on_guardar_duplicar_click(self, *_a):
        id_eq = self._guardar()
        if id_eq is None:
            return
        if self._on_guardado:
            self._on_guardado()
        mostrar_info(_("Equipo guardado (ID {}).\n"
                      "Completá el siguiente equipo del mismo tipo.").format(id_eq))
        self._limpiar_para_duplicar()


class DialogoDireccionConector(Popup):
    """Mini-diálogo para elegir IN / OUT al agregar conector manual."""

    def __init__(self, on_elegido=None, **kwargs):
        self._on_elegido = on_elegido
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        box.add_widget(barra_superior_dialogo(
            _("Dirección del conector"), on_atras=lambda: self.dismiss()))
        # Apilados en vez de lado a lado: "← Entrada (IN)" / "→ Salida
        # (OUT)" no entran legibles uno junto al otro en 360dp de ancho.
        btn_in = Button(text=_("Entrada (IN)"), size_hint_y=None,
                       height=ALTO_BOTON, font_size=FUENTE_NORMAL)
        btn_out = Button(text=_("Salida (OUT)"), size_hint_y=None,
                        height=ALTO_BOTON, font_size=FUENTE_NORMAL)
        btn_in.bind(on_release=lambda *_a: self._elegir("IN"))
        btn_out.bind(on_release=lambda *_a: self._elegir("OUT"))
        box.add_widget(btn_in)
        box.add_widget(btn_out)
        super().__init__(title="", separator_height=0, content=box,
                         size_hint=(1, 1), **kwargs)

    def _elegir(self, direccion):
        self.dismiss()
        if self._on_elegido:
            self._on_elegido(direccion)
