#!/usr/bin/env python3
"""
tema.py — Sistema de tema (rediseño 2.0, inspirado en apps Android
modernas: superficies claras, tarjetas redondeadas, acento índigo/violeta,
barra inferior, chips de estado).

Objetivo de este módulo: reskin GLOBAL con el mínimo de cambios en el
resto del código. En vez de tocar cada Button()/TextInput()/Popup() de
las ~20 pantallas, se redefinen las reglas kv de esas clases base
(<Button>, <ToggleButton>, <TextInput>, <Popup>, <Spinner>) una sola vez
acá. Cualquier Button/TextInput/Popup ya existente en el resto del
proyecto hereda el look nuevo automáticamente, sin tocar esos archivos.

Uso:
    from tema import tema
    tema.c("primario")       # color RGBA actual (según modo claro/oscuro)
    tema.alternar()          # cambia de modo y persiste la preferencia
    tema.modo                # "claro" | "oscuro"

Este módulo se importa una sola vez desde main.py (antes de crear
cualquier widget) para que el Builder.load_string se aplique al arrancar.
widgets_base.py también lo importa para usar tema.c(...) en los helpers
de mensajes/diálogos.
"""

import os

from kivy.event import EventDispatcher
from kivy.properties import StringProperty
from kivy.metrics import dp, sp
from kivy.lang import Builder
from kivy.core.window import Window

_CFG_PATH = os.path.expanduser("~/.config/cabledoc_tema")

# ─── Paletas ──────────────────────────────────────────────────────────────

PALETAS = {
    "claro": {
        "bg":             (0.965, 0.965, 0.975, 1),
        "superficie":     (1, 1, 1, 1),
        "superficie_alt": (0.95, 0.95, 0.97, 1),
        "texto":          (0.11, 0.11, 0.15, 1),
        "texto_sub":      (0.46, 0.46, 0.54, 1),
        "borde":          (0.87, 0.87, 0.92, 1),
        "primario":       (0.38, 0.35, 0.95, 1),
        "primario_osc":   (0.30, 0.27, 0.82, 1),
        "primario_txt":   (1, 1, 1, 1),
        "secundario_bg":  (0.92, 0.92, 0.98, 1),
        "secundario_txt": (0.32, 0.29, 0.85, 1),
        "exito":          (0.14, 0.62, 0.38, 1),
        "exito_bg":       (0.86, 0.96, 0.90, 1),
        "alerta":         (0.85, 0.55, 0.05, 1),
        "alerta_bg":      (1.00, 0.93, 0.80, 1),
        "error":          (0.82, 0.20, 0.20, 1),
        "error_bg":       (1.00, 0.88, 0.88, 1),
        "input_bg":       (0.96, 0.96, 0.98, 1),
        "barra_inf":      (1, 1, 1, 1),
        "icono_inactivo": (0.60, 0.60, 0.68, 1),
        "sombra":         (0, 0, 0, 0.10),
    },
    "oscuro": {
        "bg":             (0.07, 0.07, 0.10, 1),
        "superficie":     (0.12, 0.12, 0.16, 1),
        "superficie_alt": (0.17, 0.17, 0.22, 1),
        "texto":          (0.94, 0.94, 0.97, 1),
        "texto_sub":      (0.63, 0.63, 0.71, 1),
        "borde":          (0.24, 0.24, 0.30, 1),
        "primario":       (0.56, 0.53, 1.00, 1),
        "primario_osc":   (0.46, 0.43, 0.95, 1),
        "primario_txt":   (1, 1, 1, 1),
        "secundario_bg":  (0.20, 0.20, 0.27, 1),
        "secundario_txt": (0.75, 0.73, 1.00, 1),
        "exito":          (0.35, 0.80, 0.53, 1),
        "exito_bg":       (0.11, 0.22, 0.16, 1),
        "alerta":         (0.98, 0.70, 0.28, 1),
        "alerta_bg":      (0.28, 0.21, 0.08, 1),
        "error":          (0.95, 0.42, 0.42, 1),
        "error_bg":       (0.30, 0.12, 0.12, 1),
        "input_bg":       (0.17, 0.17, 0.22, 1),
        "barra_inf":      (0.12, 0.12, 0.16, 1),
        "icono_inactivo": (0.46, 0.46, 0.54, 1),
        "sombra":         (0, 0, 0, 0.40),
    },
}

RADIO = dp(14)
RADIO_CHICO = dp(10)


class _Tema(EventDispatcher):
    modo = StringProperty("claro")

    def __init__(self, **kw):
        super().__init__(**kw)
        self._cargar()
        self.bind(modo=lambda *_a: self._aplicar_fondo_ventana())
        self._aplicar_fondo_ventana()

    def c(self, clave):
        """Color RGBA actual para `clave` según el modo activo."""
        return PALETAS[self.modo][clave]

    def alternar(self):
        self.modo = "oscuro" if self.modo == "claro" else "claro"
        self._guardar()

    def set_modo(self, modo):
        if modo in PALETAS and modo != self.modo:
            self.modo = modo
            self._guardar()

    def _aplicar_fondo_ventana(self):
        try:
            Window.clearcolor = self.c("bg")
        except Exception:
            pass

    def _guardar(self):
        try:
            os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
            with open(_CFG_PATH, "w") as f:
                f.write(self.modo)
        except Exception:
            pass

    def _cargar(self):
        try:
            if os.path.exists(_CFG_PATH):
                with open(_CFG_PATH) as f:
                    m = f.read().strip()
                if m in PALETAS:
                    self.modo = m
        except Exception:
            pass


tema = _Tema()


# ─── Reskin global vía reglas kv ───────────────────────────────────────────
#
# Kivy permite redefinir las reglas <Button>/<TextInput>/<Popup>/... una
# sola vez; cualquier instancia creada en cualquier archivo del proyecto
# (Button(text="Guardar"), TextInput(...), Popup(...)) hereda el nuevo
# look sin que haya que tocar esos ~20 archivos uno por uno.
#
# `tema.c('primario')` dentro de una expresión kv queda "observado": como
# tema es un EventDispatcher con la propiedad `modo`, Kivy vuelve a
# evaluar la expresión cada vez que `tema.modo` cambia (toggle de tema),
# así que todos los widgets ya creados se repintan solos al alternar
# claro/oscuro.
#
# Nota: si un Button/TextInput puntual pasa background_color=(...) por
# código (unos pocos casos en pantallas_conexiones.py/equipos.py para
# botones de acento verde), ese valor pisa el default de acá al crearse.
# Solo se pierde si el usuario alterna el tema DESPUÉS de abrir esa
# pantalla (vuelve al color por defecto); es un caso raro y no rompe
# funcionalidad.

_RUTA_INPUT_PILL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "iconos",
    "_input_pill.png").replace("\\", "/")

_KV = f"""
#:import tema tema.tema
#:import dp kivy.metrics.dp

<Button>:
    background_normal: ''
    background_down: ''
    background_color: tema.c('primario')
    color: tema.c('primario_txt')
    canvas.before:
        Color:
            rgba: tema.c('primario_osc') if self.state == 'down' else self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<ToggleButton>:
    background_normal: ''
    background_down: ''
    canvas.before:
        Color:
            rgba: (tema.c('primario') if self.state == 'down' else tema.c('superficie_alt'))
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: tema.c('borde')
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(10)]
            width: 1
    color: (tema.c('primario_txt') if self.state == 'down' else tema.c('texto'))

<TextInput>:
    background_normal: '{_RUTA_INPUT_PILL}'
    background_active: '{_RUTA_INPUT_PILL}'
    background_disabled_normal: '{_RUTA_INPUT_PILL}'
    border: (16, 16, 16, 16)
    background_color: tema.c('input_bg')
    foreground_color: tema.c('texto')
    hint_text_color: tema.c('texto_sub')
    cursor_color: tema.c('primario')
    selection_color: tema.c('primario')[0], tema.c('primario')[1], tema.c('primario')[2], 0.35
    padding: [dp(10), dp(10), dp(10), dp(10)]

<Popup>:
    separator_color: tema.c('borde')
    title_color: tema.c('texto')
    title_size: sp(16)
    title_align: 'left'
    background: ''
    background_color: tema.c('bg')
    overlay_color: 0, 0, 0, 0.55

<Spinner>:
    background_normal: ''
    background_down: ''
    background_color: tema.c('superficie_alt')
    color: tema.c('texto')
    canvas.before:
        Color:
            rgba: tema.c('superficie_alt')
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: tema.c('borde')
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(10)]
            width: 1

<CheckBox>:
    color: tema.c('primario')

<Label>:
    color: tema.c('texto')

<ScrollView>:
    bar_color: tema.c('primario')
    bar_inactive_color: tema.c('borde')
    bar_width: dp(4)
"""

Builder.load_string(_KV)


# ─── Componentes reutilizables de más alto nivel ──────────────────────────
#
# Se definen acá (en vez de widgets_base.py) para mantener el sistema de
# tema autocontenido en un solo archivo nuevo. widgets_base.py y main.py
# los importan.

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse

ALTURA_BARRA_INFERIOR = dp(60)
ALTURA_BARRA_SUPERIOR = dp(56)

ICONOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "iconos")


def ruta_icono(nombre):
    """Ruta al PNG de assets/iconos/<nombre>.png (blanco sobre
    transparente; se tiñe en runtime con Image.color). Generados por
    generar_iconos.py — reemplazan a los glifos Unicode, que no se ven
    en Pydroid 3."""
    return os.path.join(ICONOS_DIR, f"{nombre}.png")


class IconoImg(Image):
    """Image que se tiñe automáticamente con un color del tema (o uno
    fijo) y se repinta sola si el tema cambia."""

    def __init__(self, icono, clave_color="texto", color_fijo=None,
                **kwargs):
        kwargs.setdefault("fit_mode", "contain")
        super().__init__(source=ruta_icono(icono), **kwargs)
        self._clave_color = clave_color
        self._color_fijo = color_fijo
        self.color = color_fijo or tema.c(clave_color)
        if not color_fijo:
            tema.bind(modo=lambda *_a: setattr(
                self, "color", tema.c(self._clave_color)))

    def set_icono(self, icono):
        self.source = ruta_icono(icono)


class Tarjeta(BoxLayout):
    """Contenedor con fondo de 'superficie' redondeado — la unidad visual
    básica del rediseño (equivalente a un Card de Material Design)."""

    def __init__(self, radio=None, clave_color="superficie", borde=True,
                **kwargs):
        super().__init__(**kwargs)
        self._radio = radio or RADIO
        self._clave_color = clave_color
        self._borde = borde
        with self.canvas.before:
            self._c_fondo = Color(*tema.c(clave_color))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self._radio])
            if borde:
                self._c_borde = Color(*tema.c("borde"))
                self._line = Line(rounded_rectangle=(*self.pos, *self.size,
                                                      self._radio), width=1)
        self.bind(pos=self._actualizar, size=self._actualizar)
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._borde:
            self._line.rounded_rectangle = (*self.pos, *self.size, self._radio)

    def _actualizar_color(self, *_a):
        self._c_fondo.rgba = tema.c(self._clave_color)
        if self._borde:
            self._c_borde.rgba = tema.c("borde")


class Chip(BoxLayout):
    """Etiqueta redondeada pequeña para estados (Activo, Mantenimiento,
    Conectado, etc.) — equivalente a los "badges" del mockup."""

    def __init__(self, texto="", clave_color="exito", **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(24))
        super().__init__(**kwargs)
        self._clave_color = clave_color
        self.padding = (dp(10), 0)
        with self.canvas.before:
            self._c = Color(*tema.c(clave_color + "_bg"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(12)])
        self.bind(pos=self._actualizar, size=self._actualizar)
        self._lbl = Label(text=texto, font_size=sp(11), bold=True,
                          color=tema.c(clave_color))
        self.add_widget(self._lbl)
        self.width = max(dp(50), len(texto) * dp(7) + dp(20))
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _actualizar_color(self, *_a):
        self._c.rgba = tema.c(self._clave_color + "_bg")
        self._lbl.color = tema.c(self._clave_color)

    def set_texto(self, texto, clave_color=None):
        self._lbl.text = texto
        if clave_color:
            self._clave_color = clave_color
            self._actualizar_color()
        self.width = max(dp(50), len(texto) * dp(7) + dp(20))


class BotonIcono(ButtonBehavior, BoxLayout):
    """Botón circular con un ícono PNG — usado en la barra superior
    (búsqueda, alternar tema, menú) y en accesos rápidos."""

    def __init__(self, icono="mas", tamano=None, clave_fondo=None,
                clave_icono=None, **kwargs):
        tam = tamano or dp(40)
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (tam, tam))
        kwargs.setdefault("padding", dp(8))
        super().__init__(**kwargs)
        self._clave_fondo = clave_fondo
        with self.canvas.before:
            self._c = Color(*(tema.c(clave_fondo) if clave_fondo
                             else (0, 0, 0, 0)))
            self._el = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizar, size=self._actualizar)
        self._img = IconoImg(icono, clave_color=clave_icono or "texto")
        self.add_widget(self._img)
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _actualizar(self, *_a):
        self._el.pos = self.pos
        self._el.size = self.size

    def _actualizar_color(self, *_a):
        if self._clave_fondo:
            self._c.rgba = tema.c(self._clave_fondo)

    def set_icono(self, icono):
        self._img.set_icono(icono)


class BotonPill(ButtonBehavior, BoxLayout):
    """Botón redondeado tipo 'pill' (radio = mitad de la altura), más
    chico y compacto que el Button rectangular por defecto. Se ajusta a
    su contenido (ícono + texto) usando el `minimum_width` nativo de
    BoxLayout — el mismo mecanismo que ya usan las listas del resto del
    proyecto para autoajustar alto — en vez de calcular el ancho a mano
    de forma asíncrona (eso dejaba el 'pill' más ancho que el contenido,
    con el ícono/texto pegados a la izquierda en vez de centrados).
    Tres estilos para dar jerarquía visual cuando hay varias acciones en
    la misma fila:

        estilo='primario'   → relleno sólido color primario, texto
                              blanco (la acción recomendada/por defecto,
                              p.ej. Aceptar)
        estilo='secundario' → fondo tenue + borde color primario, texto
                              primario (alternativa directa, p.ej.
                              Cancelar)
        estilo='terciario'  → fondo tenue + borde gris (no primario),
                              texto gris — jerarquía más baja, para una
                              acción opcional que no compite visualmente
                              con la principal (p.ej. Auditado)

    icono: nombre de ícono opcional (de assets/iconos) a la izquierda
    del texto.
    """

    def __init__(self, texto, icono=None, estilo="primario", **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(42))
        kwargs.setdefault("spacing", dp(5))
        kwargs.setdefault("padding", (dp(16), 0))
        super().__init__(**kwargs)
        self._estilo = estilo

        with self.canvas.before:
            self._c = Color(*self._color_fondo())
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self.height / 2])
            self._c_borde = Color(*self._color_borde())
            self._borde = Line(rounded_rectangle=(*self.pos, *self.size,
                                                   self.height / 2),
                               width=1.3)
        self.bind(pos=self._actualizar, size=self._actualizar)
        # El ancho del botón sigue automáticamente al ancho natural de
        # sus hijos (ícono + texto + padding/spacing) — se recalcula
        # solo cada vez que el texto cambia de tamaño, sin timing manual.
        self.bind(minimum_width=self.setter("width"))

        # BoxLayout horizontal ancla los hijos ABAJO por defecto (solo
        # respeta padding_bottom, no centra en y) — por eso el ícono y
        # el texto quedaban pegados al piso del 'pill' en vez de
        # centrados. pos_hint centra cada hijo en su propia celda
        # verticalmente, sin afectar el ancho/posición horizontal
        # (que sigue definido por el layout normal de la fila).
        if icono:
            self._img = IconoImg(icono, color_fijo=self._color_texto(),
                                size_hint=(None, None),
                                size=(dp(16), dp(16)),
                                pos_hint={"center_y": 0.5})
            self.add_widget(self._img)
        else:
            self._img = None
        self._lbl = Label(text=texto, bold=True, font_size=sp(14),
                          color=self._color_texto(), size_hint=(None, None),
                          pos_hint={"center_y": 0.5})
        self._lbl.bind(texture_size=lambda w, ts: setattr(w, "size", ts))
        self.add_widget(self._lbl)

        tema.bind(modo=lambda *_a: self._retema())

    def _color_fondo(self):
        if self._estilo == "primario":
            return tema.c("primario")
        return tema.c("secundario_bg")

    def _color_borde(self):
        if self._estilo == "secundario":
            return tema.c("primario")
        if self._estilo == "terciario":
            return tema.c("borde")
        return (0, 0, 0, 0)

    def _color_texto(self):
        if self._estilo == "primario":
            return tema.c("primario_txt")
        if self._estilo == "terciario":
            return tema.c("texto_sub")
        return tema.c("primario")

    def _actualizar(self, *_a):
        r = self.height / 2
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [r]
        self._borde.rounded_rectangle = (*self.pos, *self.size, r)

    def _retema(self):
        self._c.rgba = self._color_fondo()
        self._c_borde.rgba = self._color_borde()
        self._lbl.color = self._color_texto()
        if self._img:
            self._img.color = self._color_texto()


class BotonFAB(ButtonBehavior, BoxLayout):
    """Floating Action Button circular color primario, con sombra sutil."""

    def __init__(self, icono="plus", tamano=None, **kwargs):
        tam = tamano or dp(56)
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (tam, tam))
        kwargs.setdefault("padding", dp(14))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*tema.c("sombra"))
            self._sombra = Ellipse(pos=(self.x, self.y - dp(2)),
                                   size=self.size)
            self._c = Color(*tema.c("primario"))
            self._el = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizar, size=self._actualizar)
        self._img = IconoImg(icono, color_fijo=tema.c("primario_txt"))
        self.add_widget(self._img)
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _actualizar(self, *_a):
        self._el.pos = self.pos
        self._el.size = self.size
        self._sombra.pos = (self.x, self.y - dp(2))
        self._sombra.size = self.size

    def _actualizar_color(self, *_a):
        self._c.rgba = tema.c("primario")


class BarraSuperior(BoxLayout):
    """Barra superior estilo app Android moderna: título + acciones
    (íconos redondos) a la derecha. Reemplaza visualmente a la vieja
    barra_top de main.py, pero es reutilizable desde cualquier pantalla."""

    def __init__(self, titulo="", acciones=None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("padding", (dp(14), dp(6)))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        with self.canvas.before:
            self._c = Color(*tema.c("bg"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[0])
        self.bind(pos=self._actualizar, size=self._actualizar)
        self._lbl = Label(text=titulo, font_size=sp(19), bold=True,
                          color=tema.c("texto"), halign="left",
                          valign="middle")
        self._lbl.bind(size=lambda w, *_a: setattr(
            w, "text_size", (w.width, w.height)))
        self.add_widget(self._lbl)
        for icono, cb in (acciones or []):
            b = BotonIcono(icono=icono, clave_icono="texto")
            b.bind(on_release=lambda *_a, c=cb: c())
            self.add_widget(b)
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _actualizar_color(self, *_a):
        self._c.rgba = tema.c("bg")
        self._lbl.color = tema.c("texto")


class BarraInferior(BoxLayout):
    """Barra de navegación inferior estilo Android (íconos + etiqueta,
    ítem activo resaltado en color primario). Un ítem con etiqueta=None
    se renderiza como botón circular (FAB) centrado en su columna —
    así el '+' queda integrado en la barra, entre los demás ítems, en
    vez de flotar aparte.

    Pensada para vivir como widget de nivel Window (por eso NO usa
    size_hint por defecto: se le asigna pos/size explícitos desde
    afuera para que quede fija en toda la app, incluso con pantallas
    abiertas encima como Popup)."""

    def __init__(self, items, activo=0, **kwargs):
        """items: lista de (icono, etiqueta, callback). etiqueta=None
        marca el ítem central como FAB."""
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", ALTURA_BARRA_INFERIOR)
        super().__init__(**kwargs)
        self._items = items
        self._botones = []
        with self.canvas.before:
            self._c = Color(*tema.c("barra_inf"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[0])
            self._c_borde = Color(*tema.c("borde"))
            self._linea_top = Line(points=[self.x, self.top, self.right,
                                           self.top], width=1)
        self.bind(pos=self._actualizar, size=self._actualizar)
        for i, (icono, etiqueta, cb) in enumerate(items):
            item = self._crear_item(icono, etiqueta, i == activo)
            item.bind(on_release=lambda *_a, c=cb: c())
            self._botones.append(item)
            self.add_widget(item)
        tema.bind(modo=lambda *_a: self._actualizar_color())

    def _crear_item(self, icono, etiqueta, activo):
        if etiqueta is None:
            return _ItemFAB(icono)
        return _ItemNav(icono, etiqueta, activo)

    def _actualizar(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._linea_top.points = [self.x, self.top, self.right, self.top]

    def _actualizar_color(self, *_a):
        self._c.rgba = tema.c("barra_inf")
        self._c_borde.rgba = tema.c("borde")
        for b in self._botones:
            b.refrescar()

    def fijar_en_window(self, window):
        """Ancla esta barra al ancho completo de `window`, al pie,
        y la mantiene ahí ante cualquier resize (rotación, etc.)."""
        def _reajustar(*_a):
            self.size = (window.width, ALTURA_BARRA_INFERIOR)
            self.pos = (0, 0)
        window.bind(size=_reajustar)
        _reajustar()


class _ItemNav(ButtonBehavior, BoxLayout):
    def __init__(self, icono, etiqueta, activo, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", (0, dp(6)))
        super().__init__(**kwargs)
        self._activo = activo
        clave = "primario" if activo else "icono_inactivo"
        self._img = IconoImg(icono, clave_color=clave,
                            size_hint_y=None, height=dp(22))
        self._lbl_t = Label(text=etiqueta, font_size=sp(10),
                            color=tema.c(clave), size_hint_y=None,
                            height=dp(14))
        self.add_widget(self._img)
        self.add_widget(self._lbl_t)

    def refrescar(self):
        clave = "primario" if self._activo else "icono_inactivo"
        self._img.color = tema.c(clave)
        self._lbl_t.color = tema.c(clave)


class _ItemFAB(ButtonBehavior, BoxLayout):
    """Ítem central de la barra inferior: círculo color primario con
    ícono blanco — el '+' de alta rápida, integrado entre Equipos y
    Conexiones en vez de flotar aparte."""

    DIAMETRO = dp(44)

    def __init__(self, icono="plus", **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*tema.c("sombra"))
            self._sombra = Ellipse()
            self._c = Color(*tema.c("primario"))
            self._el = Ellipse()
        self.bind(pos=self._actualizar, size=self._actualizar)
        fl = FloatLayout()
        self._img = IconoImg(icono, color_fijo=tema.c("primario_txt"),
                            size_hint=(None, None),
                            size=(dp(20), dp(20)),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})
        fl.add_widget(self._img)
        self.add_widget(fl)

    def _actualizar(self, *_a):
        d = self.DIAMETRO
        cx, cy = self.center_x, self.center_y
        self._el.pos = (cx - d / 2, cy - d / 2)
        self._el.size = (d, d)
        self._sombra.pos = (cx - d / 2, cy - d / 2 - dp(2))
        self._sombra.size = (d, d)

    def refrescar(self):
        self._c.rgba = tema.c("primario")
        self._img.color = tema.c("primario_txt")


# ─── Colchón global anti-solapamiento con la barra inferior ───────────────
#
# La barra inferior (ver BarraInferior/CableDocApp.on_start en main.py) es
# global: vive pegada a la Window, no dentro de cada Popup, así que queda
# SIEMPRE por encima de cualquier pantalla — incluido el contenido que esa
# pantalla dibuje pegado a su propio borde inferior (y=0). Como casi todos
# los Popup de la app son a pantalla completa (size_hint=(1,1)), cualquier
# fila de botones al final (Aceptar/Cancelar, Cerrar, etc.) terminaba
# literalmente detrás de la barra.
#
# En vez de tocar manualmente cada una de las ~30 pantallas, se parchea
# Popup.open() una sola vez acá: a los popups fullscreen se les agrega un
# espaciador invisible del alto de la barra al final de su `content` (si
# es un BoxLayout vertical, que es el patrón que usa todo el proyecto) o
# se envuelve el contenido en uno nuevo si no lo es. Así el contenido real
# nunca queda detrás de la barra, sin tener que ajustar cada pantalla.

from kivy.uix.popup import Popup as _PopupClass

_popup_open_original = _PopupClass.open


def _popup_open_con_colchon(self, *args, **kwargs):
    try:
        sh = self.size_hint
        es_fullscreen = sh and sh[0] == 1 and sh[1] == 1
        if es_fullscreen and not getattr(self, "_colchon_barra_ok", False):
            contenido = self.content
            if contenido is not None:
                # Kivy reserva SIEMPRE overhead fijo en su Popup nativo,
                # sin forma de desactivarlo por properties (confirmado
                # inspeccionando el kv fuente de Kivy: el GridLayout
                # interno tiene `padding: '12dp'` escrito literal, y la
                # fila de título mide `texture_size[1] + dp(16)` incluso
                # con title="" vacío — y no se puede sobrescribir la
                # plantilla completa por Builder.load_string porque Kivy
                # F-U-S-I-O-N-A reglas <Popup> de distintas cargas en
                # vez de reemplazarlas, así que agregar widgets propios
                # ahí duplica la estructura en vez de sustituirla).
                # Confirmado también midiendo en vivo: content.pos
                # terminaba en (12,12) en vez de (0,0).
                #   arriba: padding(12) + título vacío(16) + separador(4) = 32dp
                #   abajo:  padding(12) = 12dp
                _overhead_arriba_nativo = dp(12) + dp(16) + dp(4)
                _overhead_abajo_nativo = dp(12)
                espacio_abajo = BoxLayout(
                    size_hint_y=None,
                    height=max(0, ALTURA_BARRA_INFERIOR
                              - _overhead_abajo_nativo))
                espacio_arriba = BoxLayout(
                    size_hint_y=None,
                    height=max(0, ALTURA_BARRA_SUPERIOR
                              - _overhead_arriba_nativo))
                if (isinstance(contenido, BoxLayout)
                        and contenido.orientation == "vertical"):
                    contenido.add_widget(espacio_abajo)
                    # index=len(children) inserta arriba de todo lo demás
                    # (ver nota en fila_botones_pill/tarjeta_encabezado):
                    # las llamadas add_widget() sucesivas de un
                    # BoxLayout vertical apilan de arriba hacia abajo en
                    # el orden en que se llaman, así que agregar acá
                    # DESPUÉS de que todo el contenido ya se armó
                    # requiere ese índice explícito para terminar arriba
                    # de todo (debajo de la barra global) en vez de al
                    # final (abajo de todo).
                    contenido.add_widget(espacio_arriba,
                                        index=len(contenido.children))
                else:
                    padre = contenido.parent
                    if padre is not None:
                        padre.remove_widget(contenido)
                    nuevo = BoxLayout(orientation="vertical")
                    nuevo.add_widget(espacio_arriba)
                    nuevo.add_widget(contenido)
                    nuevo.add_widget(espacio_abajo)
                    self.content = nuevo
            self._colchon_barra_ok = True
    except Exception:
        pass
    return _popup_open_original(self, *args, **kwargs)


_PopupClass.open = _popup_open_con_colchon
