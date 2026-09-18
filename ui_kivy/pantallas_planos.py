"""
pantallas_planos.py — Catálogo de Planos + Muebles + visor interactivo,
en Kivy.

Equivalente a PlanosListado/_DialogoPlano, MueblesListado/_DialogoMueble
y VistaPlanoInteractivo de ui_gtk/planos_ui.py — roadmap de cierre de
mobile, ítem 4 ("Ubicación física en planos"):

  - 4a: PlanosListado/DialogoPlano — catálogo simple de planos (nombre +
    imagen + orden).
  - 4b: MueblesListado/DialogoMueble — catálogo de muebles (nombre/sala/
    tipo) + asignación de equipos sobre cada uno.
  - 4c: VistaPlanoInteractivo — overlay de racks (cuadrados) y muebles
    (rectángulos, con sus equipos dentro) sobre la imagen del plano, más
    los selectores/botones para ubicar/redefinir cada uno. Cubre el
    equivalente de las Fases 5 y 6 de
    plan_desarrollo_ubicacion_fisica_planos.md (GTK). Deliberadamente NO
    incluye (quedan para una entrega posterior, mismo orden que tuvo el
    plan original):
      - Fase 4 (overlay de contorno de sala, polígono libre) — el modo
        polígono de CoordenadasImagenSeleccion no tiene equivalente en
        SelectorCoordenadasImagen (widgets_base.py) todavía.
      - Fase 7 (overlay de equipos sueltos — círculos — + hit-testing de
        racks: clic para listar equipos montados/módulos de frame).

Mismo criterio de "diálogo simple" que ImagenesListado/DialogoImagen
(pantallas_imagenes.py) para Plano: 3 campos sin acciones propias ni
relaciones que ameriten pestañas — Popup + grid_formulario, sin
BarraTabs. La selección de imagen reutiliza FileChooserPopup + copia a
IMG_DIR, igual que DialogoImagen y que _explorar en el _DialogoPlano de
GTK — Modelo.alta_plano_retorna_id/modificacion_plano gestionan su
propia fila de `imagen` asociada 1 a 1 al plano (no se elige una fila ya
existente de la tabla `imagen` vía ImagenesListado, a diferencia de
Equipo/Conector/Frame/Slot).

Mueble sí tiene dos secciones que sólo se habilitan una vez guardado
(self.id_mueble, mismo criterio que DialogoRackPorSala en
pantallas_salas.py): el rectángulo (depende de VistaPlanoInteractivo,
que a su vez necesita id_mueble para saber qué fila actualizar) y los
equipos asignados (equipo_sobre_mueble.id_mueble es FK). El botón
"Ubicar dentro del mueble" reutiliza SelectorCoordenadasImagen en modo
punto sobre la imagen COMPLETA del plano (no una vista recortada del
mueble), con rect_referencia para dibujar el rectángulo del mueble como
marco — mismo mecanismo que en GTK (rect_referencia de
abrir_coords_imagen).
"""

import os
import shutil

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, FileChooserPopup, grid_formulario, fila_etiqueta,
    fila_entry, entry_selector, etiqueta_ultima_edicion, titulo_con_nombre,
    mostrar_error, barra_superior_dialogo, seccion_tarjeta,
    dibujar_marcador_cuadrado, dibujar_marcador_rectangulo,
    SelectorCoordenadasImagen, VisorImagenZoom,
    s, _, ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from core.modelo import Modelo, IMG_DIR, DimensionesImagenError


class PlanosListado(ListadoPopup):
    def __init__(self, **kwargs):
        super().__init__(_("Planos"),
                         [_("ID"), _("Nombre"), _("Imagen"), _("Orden")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_planos())

    def nuevo(self):
        DialogoPlano(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoPlano(id_plano=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_plano(id_)


class DialogoPlano(Popup):
    def __init__(self, id_plano=None, on_guardado=None, **kwargs):
        self.id_plano = id_plano
        self._on_guardado = on_guardado
        titulo = _("Editar Plano") if id_plano else _("Nuevo Plano")

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")

        fila_etiqueta(g, _("Imagen:"))
        hb_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_imagen = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        btn_explorar = Button(text=_("Explorar"), size_hint_x=None,
                             width=dp(110), font_size=FUENTE_CHICA)
        btn_explorar.bind(on_release=self._explorar)
        hb_img.add_widget(self.e_imagen)
        hb_img.add_widget(btn_explorar)
        g.add_widget(hb_img)

        fila_etiqueta(g, _("Orden:"))
        self.e_orden = fila_entry(g, "0")

        box.add_widget(g)

        box.add_widget(Label(
            text=_("Orden de aparición en el menú/selector de planos "
                  "(0 = primero)."),
            italic=True, font_size=sp(11), color=(0.6, 0.6, 0.6, 1),
            size_hint_y=None, height=dp(36), halign="left", valign="top"))

        if id_plano:
            rows = Modelo.devolver_plano(id_plano)
            if rows:
                r = rows[0]
                self.e_nombre.text = s(r[1])
                self.e_imagen.text = s(r[3])
                self.e_orden.text = s(r[4]) or "0"

        etq = etiqueta_ultima_edicion("plano", "id_plano", id_plano)
        if etq:
            box.add_widget(etq)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        if id_plano:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _explorar(self, *_a):
        def _elegida(ruta):
            os.makedirs(IMG_DIR, exist_ok=True)
            nombre = os.path.basename(ruta)
            destino = os.path.join(IMG_DIR, nombre)
            if os.path.abspath(ruta) != os.path.abspath(destino):
                try:
                    shutil.copy2(ruta, destino)
                except Exception as e:
                    mostrar_error(_("Error al copiar la imagen: {}").format(e))
                    return
            self.e_imagen.text = nombre

        FileChooserPopup(
            titulo=_("Seleccionar imagen del plano"),
            filtros=["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.svg",
                    "*.SVG"],
            on_seleccionar=_elegida).open()

    def _guardar(self, *_a):
        nombre = self.e_nombre.text.strip()
        if not nombre:
            mostrar_error(_("El plano necesita un nombre."))
            return
        path = self.e_imagen.text.strip() or None
        try:
            orden = int(self.e_orden.text.strip() or "0")
        except ValueError:
            orden = 0
        # `imagen.path_archivo` es NOT NULL en el schema (ver
        # data/schema_db.sql): a diferencia de lo que decía el aviso de
        # GTK ("se va a guardar igual, pero va a aparecer en negro"),
        # guardar sin imagen en realidad revienta con IntegrityError —
        # detectado con el smoke test de este mismo cambio. Bug también
        # presente en ui_gtk/planos_ui.py._DialogoPlano.run_and_destroy
        # (no se toca acá, fuera de alcance; ver PROGRESS). Del lado
        # mobile se bloquea antes de llegar a Modelo, con un mensaje
        # que explica el motivo real en vez del que decía GTK.
        if not path:
            mostrar_error(_("El plano necesita una imagen — usá el botón "
                          "\"Explorar\" antes de Aceptar."))
            return
        if not os.path.isfile(os.path.join(IMG_DIR, path)):
            mostrar_error(
                _("El archivo '{0}' no está en la carpeta de imágenes "
                  "({1}). Usá el botón \"Explorar\" en vez de escribir la "
                  "ruta a mano.").format(path, IMG_DIR))
            return
        if self.id_plano:
            Modelo.modificacion_plano(self.id_plano, nombre, path, orden)
        else:
            Modelo.alta_plano_retorna_id(nombre, path, orden)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ─── Vista interactiva del plano (ítem 4c) ─────────────────────────────────

class VistaPlanoInteractivo(Popup):
    """Visor interactivo del plano — roadmap de cierre mobile ítem 4c.
    Ver docstring del módulo para el alcance exacto (Fases 5 y 6 de
    plan_desarrollo_ubicacion_fisica_planos.md; Fases 4 y 7 quedan
    afuera).

    id_mueble_foco (opcional): si se pasa, el selector de Mueble arranca
    en ese mueble, se lo resalta en el overlay y el visor centra el
    encuadre inicial sobre su rectángulo (si ya tiene uno) — mismo uso
    que en GTK desde DialogoMueble._definir_rectangulo.
    on_cerrar (opcional): callback sin argumentos, invocado al cerrar el
    visor — para que el diálogo que lo abrió refresque su propio estado
    (ver DialogoMueble._definir_rectangulo)."""

    _LADO_RACK_DP = 18
    _RADIO_EQUIPO_DP = 4

    def __init__(self, id_plano, id_mueble_foco=None, on_cerrar=None,
                **kwargs):
        self.id_plano = id_plano
        self._on_cerrar = on_cerrar
        self._id_mueble_foco = str(id_mueble_foco) if id_mueble_foco else None

        filas_plano = Modelo.devolver_plano(id_plano)
        nombre_plano = filas_plano[0][1] if filas_plano else ""
        self._path_imagen = (
            os.path.join(IMG_DIR, filas_plano[0][3])
            if filas_plano and filas_plano[0][3] else None)

        self._racks = Modelo.devolver_racks_por_sala_de_plano(id_plano)
        self._muebles = Modelo.devolver_muebles_de_plano(id_plano)

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(4))
        root.add_widget(barra_superior_dialogo(
            titulo_con_nombre(_("Plano"), nombre_plano),
            on_atras=lambda: self.dismiss()))

        self._visor = VisorImagenZoom(size_hint=(1, 0.62))
        self._visor.set_overlay_fn(self._dibujar_overlay)
        root.add_widget(self._visor)

        hb_rack = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        hb_rack.add_widget(Label(text=_("Rack:"), size_hint_x=None,
                                 width=dp(58), font_size=FUENTE_CHICA))
        valores_rack = ["{0} / {1}".format(r[1], r[2]) for r in self._racks]
        self._combo_rack = Spinner(
            text=(valores_rack[0] if valores_rack
                 else _("(sin racks en este plano)")),
            values=valores_rack, font_size=FUENTE_CHICA)
        hb_rack.add_widget(self._combo_rack)
        btn_rack = Button(text="📍", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_rack.bind(on_release=self._ubicar_rack)
        hb_rack.add_widget(btn_rack)
        root.add_widget(hb_rack)

        hb_mueble = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        hb_mueble.add_widget(Label(text=_("Mueble:"), size_hint_x=None,
                                   width=dp(58), font_size=FUENTE_CHICA))
        valores_mueble = ["{0} / {1}".format(m[1], m[2]) for m in self._muebles]
        idx_foco = 0
        for i, m in enumerate(self._muebles):
            if self._id_mueble_foco and str(m[0]) == self._id_mueble_foco:
                idx_foco = i
                break
        self._combo_mueble = Spinner(
            text=(valores_mueble[idx_foco] if valores_mueble
                 else _("(sin muebles en este plano)")),
            values=valores_mueble, font_size=FUENTE_CHICA)
        hb_mueble.add_widget(self._combo_mueble)
        btn_mueble = Button(text="▭", size_hint_x=None, width=dp(44),
                           font_size=FUENTE_NORMAL)
        btn_mueble.bind(on_release=self._definir_rectangulo_mueble)
        hb_mueble.add_widget(btn_mueble)
        root.add_widget(hb_mueble)

        root.add_widget(Label(
            text=_("🟦 Rack   🟧 Mueble (con sus equipos ⚪)"),
            size_hint_y=None, height=dp(18), font_size=sp(10),
            color=(0.6, 0.6, 0.6, 1)))

        super().__init__(title="", separator_height=0, content=root,
                         size_hint=(1, 1), **kwargs)
        self._visor.set_imagen(self._path_imagen)
        Clock.schedule_once(lambda *_a: self._encuadre_inicial(), 0.15)

    def on_dismiss(self):
        if self._on_cerrar:
            self._on_cerrar()

    def _rack_seleccionado(self):
        if not self._racks:
            return None
        try:
            idx = self._combo_rack.values.index(self._combo_rack.text)
        except ValueError:
            idx = 0
        return self._racks[idx]

    def _mueble_seleccionado(self):
        if not self._muebles:
            return None
        try:
            idx = self._combo_mueble.values.index(self._combo_mueble.text)
        except ValueError:
            idx = 0
        return self._muebles[idx]

    def _dibujar_overlay(self, canvas_widget):
        if not self._path_imagen:
            return
        zoom = self._visor.zoom
        lado_rack = dp(self._LADO_RACK_DP)
        for _id_rxs, _nombre_sala, _nombre_rack, x_pct, y_pct in self._racks:
            if x_pct is None or y_pct is None:
                continue
            x_px, y_px = Modelo._px_punto_o_crudo(
                self._path_imagen, x_pct, y_pct)
            cx, cy = canvas_widget.i2w(x_px, y_px, zoom)
            dibujar_marcador_cuadrado(canvas_widget, cx, cy, lado_rack,
                                      (0.3, 0.55, 0.95))
        for id_m, _nombre_sala, _nombre_m, x_pct, y_pct, ancho_pct, alto_pct \
                in self._muebles:
            if None in (x_pct, y_pct, ancho_pct, alto_pct):
                continue
            x_px, y_px, ancho_px, alto_px = Modelo._px_rect_o_crudo(
                self._path_imagen, x_pct, y_pct, ancho_pct, alto_pct)
            wx, wy = canvas_widget.i2w(x_px, y_px + alto_px, zoom)
            resaltado = bool(self._id_mueble_foco and
                            str(id_m) == self._id_mueble_foco)
            dibujar_marcador_rectangulo(
                canvas_widget, wx, wy, ancho_px * zoom, alto_px * zoom,
                (0.95, 0.6, 0.15), resaltado=resaltado)
            radio_eq = dp(self._RADIO_EQUIPO_DP)
            for _id_eq, _nombre_eq, x_rel, y_rel in \
                    Modelo.devolver_equipos_de_mueble(id_m):
                if x_rel is None or y_rel is None:
                    continue
                ex_px = x_px + (x_rel / 100.0) * ancho_px
                ey_px = y_px + (y_rel / 100.0) * alto_px
                ecx, ecy = canvas_widget.i2w(ex_px, ey_px, zoom)
                with canvas_widget.canvas:
                    Color(0.92, 0.92, 0.97, 0.95)
                    Ellipse(pos=(ecx - radio_eq, ecy - radio_eq),
                           size=(radio_eq * 2, radio_eq * 2))

    def _ubicar_rack(self, *_a):
        rack = self._rack_seleccionado()
        if not rack or not self._path_imagen:
            mostrar_error(
                _("No hay racks para ubicar en este plano — asigná un "
                  "rack a una sala de este plano primero (ver \"Rack por "
                  "Sala\")."))
            return
        id_rxs, _ns, _nr, x_pct, y_pct = rack
        x_px = y_px = None
        if x_pct is not None:
            x_px, y_px = Modelo._px_punto_o_crudo(
                self._path_imagen, x_pct, y_pct)

        def _con_resultado(resultado):
            if not resultado:
                return
            try:
                x_pct_n, y_pct_n = Modelo._punto_px_a_pct(
                    self._path_imagen, resultado["x"], resultado["y"])
            except DimensionesImagenError:
                mostrar_error(
                    _("No se pudo determinar el tamaño de la imagen del "
                      "plano — no se guardó la ubicación."))
                return
            Modelo.actualizar_posicion_rack_por_sala(id_rxs, x_pct_n, y_pct_n)
            self._racks = Modelo.devolver_racks_por_sala_de_plano(self.id_plano)
            self._visor.queue_draw()

        SelectorCoordenadasImagen(
            self._path_imagen, solo_xy=True, x=x_px, y=y_px,
            on_aceptar=_con_resultado).open()

    def _definir_rectangulo_mueble(self, *_a):
        mueble = self._mueble_seleccionado()
        if not mueble or not self._path_imagen:
            mostrar_error(
                _("No hay muebles para ubicar en este plano — creá uno "
                  "primero desde \"Muebles\"."))
            return
        id_m, _ns, nombre_m, x_pct, y_pct, ancho_pct, alto_pct = mueble
        x_px = y_px = ancho_px = alto_px = None
        if None not in (x_pct, y_pct, ancho_pct, alto_pct):
            x_px, y_px, ancho_px, alto_px = Modelo._px_rect_o_crudo(
                self._path_imagen, x_pct, y_pct, ancho_pct, alto_pct)

        def _con_resultado(resultado):
            if not resultado:
                return
            try:
                x_pct_n, y_pct_n, ancho_pct_n, alto_pct_n = \
                    Modelo._rect_px_a_pct(
                        self._path_imagen, resultado["x"], resultado["y"],
                        resultado["ancho"], resultado["alto"])
            except DimensionesImagenError:
                mostrar_error(
                    _("No se pudo determinar el tamaño de la imagen del "
                      "plano — no se guardó el rectángulo."))
                return
            rows = Modelo.devolver_mueble(id_m)
            if rows:
                Modelo.modificacion_mueble(
                    id_m, rows[0][2], x_pct_n, y_pct_n, ancho_pct_n,
                    alto_pct_n, rows[0][3])
            self._id_mueble_foco = str(id_m)
            self._muebles = Modelo.devolver_muebles_de_plano(self.id_plano)
            self._visor.queue_draw()

        SelectorCoordenadasImagen(
            self._path_imagen, solo_xy=False, x=x_px, y=y_px,
            ancho=ancho_px, alto=alto_px,
            etiqueta_referencia=s(nombre_m),
            on_aceptar=_con_resultado).open()

    def _encuadre_inicial(self):
        self._visor._zoom_fit()
        if not self._id_mueble_foco or not self._path_imagen:
            return
        mueble = self._mueble_seleccionado()
        if not mueble or None in mueble[3:7]:
            return
        _id_m, _ns, _nm, x_pct, y_pct, ancho_pct, alto_pct = mueble
        x_px, y_px, ancho_px, alto_px = Modelo._px_rect_o_crudo(
            self._path_imagen, x_pct, y_pct, ancho_pct, alto_pct)
        self._visor.scroll_to_img(x_px + ancho_px / 2, y_px + alto_px / 2)


# ─── Muebles (ítem 4b) ──────────────────────────────────────────────────────

class MueblesListado(ListadoPopup):
    """Catálogo simple de muebles (mesas/escritorios) — roadmap de cierre
    mobile ítem 4b. El rectángulo sobre el plano y la asignación de
    equipos se editan desde DialogoMueble, no desde acá (mismo criterio
    que DialogoRackPorSala con su botón "Ubicar en el plano")."""

    def __init__(self, **kwargs):
        super().__init__(_("Muebles"),
                         [_("ID"), _("Sala"), _("Nombre"), _("Tipo"),
                          _("Ubicación")], **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        filas = []
        for id_m, _id_sala, nombre_sala, nombre, tipo, x_pct in \
                Modelo.devolver_todos_los_muebles():
            ubicacion = _("Sin ubicar") if x_pct is None else _("Ubicado")
            filas.append((id_m, nombre_sala, nombre, tipo, ubicacion))
        self._poblar(filas)

    def nuevo(self):
        DialogoMueble(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoMueble(id_mueble=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_mueble(id_)


class DialogoMueble(Popup):
    """Alta/edición de un mueble — roadmap de cierre mobile ítem 4b.
    Equivalente a _DialogoMueble (GTK, planos_ui.py): nombre/sala/tipo +
    definición del rectángulo (vía VistaPlanoInteractivo) + equipos
    asignados (agregar/quitar/ubicar dentro del mueble, vía
    SelectorCoordenadasImagen sobre la imagen completa del plano)."""

    def __init__(self, id_mueble=None, on_guardado=None, **kwargs):
        self.id_mueble = id_mueble
        self._on_guardado = on_guardado
        self._id_sala = None
        self._id_plano_de_sala = None
        self._geometria = (None, None, None, None)
        self._equipos = []
        self._sel_id_equipo = None
        titulo = _("Editar Mueble") if id_mueble else _("Nuevo Mueble")

        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        root.add_widget(barra_superior_dialogo(
            titulo, on_atras=lambda: self.dismiss()))

        scroll = ScrollView(size_hint=(1, 1))
        box = BoxLayout(orientation="vertical", spacing=dp(6),
                        size_hint_y=None, padding=(dp(4), 0))
        box.bind(minimum_height=box.setter("height"))

        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Sala:"))
        hb_sala = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_sala = entry_selector()
        btn_sala = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_sala.bind(on_release=self._sel_sala)
        hb_sala.add_widget(self.e_sala); hb_sala.add_widget(btn_sala)
        g.add_widget(hb_sala)

        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")

        fila_etiqueta(g, _("Tipo:"))
        self.e_tipo = fila_entry(g, "MESA")
        box.add_widget(seccion_tarjeta(_("Datos del mueble"), g,
                                       icono="ubicacion"))

        self._lbl_rectangulo = Label(
            text="", size_hint_y=None, height=dp(40), font_size=sp(11),
            italic=True, color=(0.65, 0.65, 0.65, 1), halign="left",
            valign="top")
        self._lbl_rectangulo.bind(
            size=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
        box.add_widget(self._lbl_rectangulo)
        self._btn_rectangulo = Button(
            text="▭ " + _("Definir rectángulo en el plano"),
            size_hint_y=None, height=ALTO_BOTON, font_size=FUENTE_CHICA)
        self._btn_rectangulo.bind(on_release=self._definir_rectangulo)
        box.add_widget(self._btn_rectangulo)

        lbl_eq = Label(text=_("Equipos en este mueble"), bold=True,
                      size_hint_y=None, height=dp(26), font_size=FUENTE_CHICA,
                      halign="left", valign="middle")
        lbl_eq.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        box.add_widget(lbl_eq)

        hdr = BoxLayout(size_hint_y=None, height=dp(22))
        for t in [_("Equipo"), _("X %"), _("Y %")]:
            hdr.add_widget(Label(text=t, bold=True, font_size=FUENTE_CHICA))
        box.add_widget(hdr)

        self._box_filas = BoxLayout(orientation="vertical",
                                    size_hint_y=None, spacing=dp(1))
        self._box_filas.bind(minimum_height=self._box_filas.setter("height"))
        box.add_widget(self._box_filas)

        hb_eq = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_agregar = Button(text=_("➕ Agregar"), font_size=FUENTE_CHICA)
        btn_agregar.bind(on_release=self._agregar_equipo)
        btn_quitar = Button(text=_("➖ Quitar"), font_size=FUENTE_CHICA)
        btn_quitar.bind(on_release=self._quitar_equipo)
        self._btn_ubicar_equipo = Button(text=_("📍 Ubicar"),
                                         font_size=FUENTE_CHICA)
        self._btn_ubicar_equipo.bind(on_release=self._ubicar_equipo)
        hb_eq.add_widget(btn_agregar)
        hb_eq.add_widget(btn_quitar)
        hb_eq.add_widget(self._btn_ubicar_equipo)
        box.add_widget(hb_eq)

        etq = etiqueta_ultima_edicion("mueble", "id_mueble", id_mueble)
        if etq:
            box.add_widget(etq)

        scroll.add_widget(box)
        root.add_widget(scroll)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_guardar = Button(text=_("Guardar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_guardar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_guardar)
        root.add_widget(hb_btn)

        if id_mueble:
            rows = Modelo.devolver_mueble(id_mueble)
            if rows:
                r = rows[0]
                self._id_sala = str(r[1])
                self.e_nombre.text = s(r[2])
                self.e_tipo.text = s(r[3]) or "MESA"
                self._geometria = (r[4], r[5], r[6], r[7])
                self._id_plano_de_sala = r[8]
                rows_sala = Modelo.devolver_sala(self._id_sala)
                if rows_sala:
                    self.e_sala.text = s(rows_sala[0][1])
            self._cargar_equipos()
        else:
            self.e_tipo.text = "MESA"

        if id_mueble:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=root, size_hint=(1, 1),
                         **kwargs)
        self._actualizar_estado_rectangulo()

    def _sel_sala(self, *_a):
        from pantallas_salas import SalasListado

        def _con_sala(id_, nombre, _f):
            self._id_sala = id_
            self.e_sala.text = nombre
            rows_sala = Modelo.devolver_sala(id_)
            self._id_plano_de_sala = rows_sala[0][2] if rows_sala else None
            self._actualizar_estado_rectangulo()
        SalasListado(modo_seleccion=True, on_seleccionar=_con_sala).open()

    def _actualizar_estado_rectangulo(self):
        x_pct, y_pct, ancho_pct, alto_pct = self._geometria
        tiene_rect = None not in (x_pct, y_pct, ancho_pct, alto_pct)
        habilitar = bool(self.id_mueble and self._id_plano_de_sala)
        self._btn_rectangulo.disabled = not habilitar
        self._btn_ubicar_equipo.disabled = not (habilitar and tiene_rect)
        if not self.id_mueble:
            texto = _("Guardá el mueble primero; el rectángulo se define "
                      "al volver a editarlo.")
        elif not self._id_plano_de_sala:
            texto = _("La sala de este mueble todavía no tiene un plano "
                      "asignado — asignáselo desde \"Planos\".")
        elif not tiene_rect:
            texto = _("Sin rectángulo todavía — definilo con el botón de "
                      "abajo antes de ubicar equipos dentro.")
        else:
            texto = _("Rectángulo definido ({0:.0f}% × {1:.0f}%). Podés "
                      "redefinirlo con el botón de abajo.").format(
                          ancho_pct, alto_pct)
        self._lbl_rectangulo.text = texto

    def _definir_rectangulo(self, *_a):
        def _al_cerrar():
            rows = Modelo.devolver_mueble(self.id_mueble)
            if rows:
                r = rows[0]
                self._geometria = (r[4], r[5], r[6], r[7])
            self._actualizar_estado_rectangulo()
        VistaPlanoInteractivo(self._id_plano_de_sala,
                             id_mueble_foco=self.id_mueble,
                             on_cerrar=_al_cerrar).open()

    def _cargar_equipos(self):
        from pantallas_editores_masivos import _FilaConector
        self._box_filas.clear_widgets()
        self._equipos = []
        self._sel_id_equipo = None
        if not self.id_mueble:
            return
        self._equipos = list(Modelo.devolver_equipos_de_mueble(self.id_mueble))
        for id_eq, nombre_eq, x_rel, y_rel in self._equipos:
            cols = [
                s(nombre_eq),
                "{0:.0f}".format(x_rel) if x_rel is not None else "—",
                "{0:.0f}".format(y_rel) if y_rel is not None else "—",
            ]
            fila = _FilaConector(str(id_eq), cols, (0, 0, 0, 0),
                                 on_click=self._sel_equipo)
            self._box_filas.add_widget(fila)

    def _sel_equipo(self, fila):
        self._sel_id_equipo = fila.id_item
        for f in self._box_filas.children:
            f.set_color((0.25, 0.45, 0.85, 0.35)
                       if f.id_item == self._sel_id_equipo else (0, 0, 0, 0))

    def _agregar_equipo(self, *_a):
        if not self.id_mueble:
            mostrar_error(
                _("Guardá el mueble primero — un equipo no puede "
                  "asignarse a un mueble que todavía no existe."))
            return
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_eq, _nombre, _f):
            try:
                Modelo.asignar_equipo_a_mueble(id_eq, self.id_mueble, 50, 50)
            except ValueError as e:
                mostrar_error(str(e))
            else:
                self._cargar_equipos()
        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo,
                      excluir_modulos_de_frame=True).open()

    def _quitar_equipo(self, *_a):
        if not self._sel_id_equipo:
            mostrar_error(_("Seleccioná un equipo de la lista primero."))
            return
        Modelo.quitar_equipo_de_mueble(self._sel_id_equipo)
        self._cargar_equipos()

    def _ubicar_equipo(self, *_a):
        if not self._sel_id_equipo:
            mostrar_error(_("Seleccioná un equipo de la lista primero."))
            return
        x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m = self._geometria
        if None in (x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m):
            mostrar_error(_("Este mueble todavía no tiene rectángulo — "
                            "definilo primero."))
            return
        filas_plano = Modelo.devolver_plano(self._id_plano_de_sala)
        if not filas_plano or not filas_plano[0][3]:
            mostrar_error(_("No se encontró la imagen del plano de la "
                            "sala."))
            return
        path_imagen_plano = os.path.join(IMG_DIR, filas_plano[0][3])

        x_rel_actual = y_rel_actual = 50
        for id_e, _ne, xr, yr in self._equipos:
            if str(id_e) == str(self._sel_id_equipo):
                x_rel_actual = xr if xr is not None else 50
                y_rel_actual = yr if yr is not None else 50
                break
        x_pct_abs = x_pct_m + (x_rel_actual / 100.0) * ancho_pct_m
        y_pct_abs = y_pct_m + (y_rel_actual / 100.0) * alto_pct_m
        x_px_actual, y_px_actual = Modelo._px_punto_o_crudo(
            path_imagen_plano, x_pct_abs, y_pct_abs)

        rect_referencia = None
        try:
            x1_px, y1_px, ancho_px, alto_px = Modelo._rect_pct_a_px(
                path_imagen_plano, x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m)
            if None not in (x1_px, y1_px, ancho_px, alto_px):
                rect_referencia = (x1_px, y1_px, x1_px + ancho_px,
                                  y1_px + alto_px)
        except DimensionesImagenError:
            rect_referencia = None

        id_equipo_actual = self._sel_id_equipo

        def _con_resultado(resultado):
            if not resultado:
                return
            try:
                x_pct_abs_n, y_pct_abs_n = Modelo._punto_px_a_pct(
                    path_imagen_plano, resultado["x"], resultado["y"])
            except DimensionesImagenError:
                mostrar_error(
                    _("No se pudo determinar el tamaño de la imagen del "
                      "plano — no se guardó la ubicación."))
                return
            x_rel = ((x_pct_abs_n - x_pct_m) / ancho_pct_m * 100.0
                    if ancho_pct_m else 50)
            y_rel = ((y_pct_abs_n - y_pct_m) / alto_pct_m * 100.0
                    if alto_pct_m else 50)
            x_rel = max(0.0, min(100.0, x_rel))
            y_rel = max(0.0, min(100.0, y_rel))
            Modelo.asignar_equipo_a_mueble(id_equipo_actual, self.id_mueble,
                                          x_rel, y_rel)
            self._cargar_equipos()

        SelectorCoordenadasImagen(
            path_imagen_plano, solo_xy=True,
            x=x_px_actual, y=y_px_actual, rect_referencia=rect_referencia,
            etiqueta_referencia=self.e_nombre.text.strip() or None,
            on_aceptar=_con_resultado).open()

    def _guardar(self, *_a):
        nombre = self.e_nombre.text.strip()
        tipo = self.e_tipo.text.strip() or "MESA"
        if not self._id_sala or not nombre:
            mostrar_error(_("Elegí una sala y escribí un nombre antes de "
                            "guardar."))
            return
        x_pct, y_pct, ancho_pct, alto_pct = self._geometria
        if self.id_mueble:
            Modelo.modificacion_mueble(self.id_mueble, nombre, x_pct, y_pct,
                                      ancho_pct, alto_pct, tipo)
        else:
            self.id_mueble = Modelo.alta_mueble_retorna_id(
                self._id_sala, nombre, x_pct, y_pct, ancho_pct, alto_pct,
                tipo)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


def abrir_planos(*_a):
    PlanosListado().open()


def abrir_muebles(*_a):
    MueblesListado().open()
