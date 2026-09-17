"""
pantallas_planos.py — Catálogo de Planos en Kivy.

Equivalente a PlanosListado / _DialogoPlano de ui_gtk/planos_ui.py.
Ítem 4a del roadmap de cierre de mobile ("Ubicación física en planos"):
sólo el catálogo simple (alta/edición/baja de nombre + imagen + orden de
cada plano) — el visor interactivo (VistaPlanoInteractivo, overlay de
salas/racks/muebles/equipos sueltos sobre la imagen del plano) queda
para un paso posterior del mismo bloque, no incluido acá.

Mismo criterio de "diálogo simple" que ImagenesListado/DialogoImagen
(pantallas_imagenes.py): Plano tiene 3 campos sin acciones propias ni
relaciones que ameriten pestañas (ver Fase 4 del plan de integración,
alcance acordado) — Popup + grid_formulario, sin BarraTabs.

La selección de imagen reutiliza FileChooserPopup + copia a IMG_DIR,
igual que DialogoImagen y que _explorar en el _DialogoPlano de GTK —
Modelo.alta_plano_retorna_id / modificacion_plano gestionan su propia
fila de `imagen` asociada 1 a 1 al plano (no se elige una fila ya
existente de la tabla `imagen` vía ImagenesListado, a diferencia de
Equipo/Conector/Frame/Slot).
"""

import os
import shutil

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, FileChooserPopup, grid_formulario, fila_etiqueta,
    fila_entry, etiqueta_ultima_edicion, titulo_con_nombre, mostrar_error,
    s, _, ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from core.modelo import Modelo, IMG_DIR


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


def abrir_planos(*_a):
    PlanosListado().open()
