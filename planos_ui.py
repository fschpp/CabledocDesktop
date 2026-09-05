#!/usr/bin/env python3
"""
planos_ui.py — CableDoc GTK3

Dominio Planos, Fase 2 de plan_desarrollo_ubicacion_fisica_planos.md
("Catálogo de Planos, sin overlay todavía").

Contiene, por ahora, solo el catálogo simple de planos:
  - PlanosListado, _DialogoPlano

El overlay interactivo (VistaPlanoInteractivo, polígonos de sala, puntos
de rack/equipo suelto, muebles) llega recién en las Fases 3 a 7 del
plan — este archivo crece en esas fases, mismo criterio de separación
por dominio que ya usan `racks_salas_ui.py` / `frames_slots_ui.py`, para
no mezclar desde el arranque el catálogo simple con el editor gráfico.

Sigue el mismo patrón que `_DialogoImagen` (catalogos_basicos_ui.py) para
la selección de imagen: un botón "Explorar" copia el archivo elegido a
IMG_DIR y completa el campo con el nombre de archivo. A diferencia de
`_DialogoImagen`, acá no se elige una fila ya existente de la tabla
`imagen` vía `ImagenesListado` — `Modelo.alta_plano_retorna_id`/
`modificacion_plano` gestionan su propia fila de `imagen` asociada
(1 a 1 con el plano) para no dejar imágenes húerfanas ni compartidas
entre planos.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import os
import shutil

from modelo import Modelo, IMG_DIR

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    VentanaListado,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
)


# ─── Planos ───────────────────────────────────────────────────────────────────

class PlanosListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Planos"),
                         [_("ID"), _("Nombre"), _("Imagen"), _("Orden")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_planos())

    def nuevo(self):
        dlg = _DialogoPlano(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoPlano(id_plano=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_plano(id_)


class _DialogoPlano(Gtk.Dialog):
    def __init__(self, id_plano=None, parent=None):
        titulo = _("Editar Plano") if id_plano else _("Nuevo Plano")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(480, 220)
        self.id_plano = id_plano

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Imagen:"), 1)
        self.e_imagen = _entry_btn(g, 1, "📂 " + _("Explorar"), self._explorar)
        _lbl_entry(g, _("Orden:"), 2)
        self.e_orden = _entry(g, 2)
        lbl_ayuda = Gtk.Label(xalign=0)
        lbl_ayuda.set_markup(
            "<small><i>" +
            _("Orden de aparición en el menú/selector de planos "
              "(0 = primero).") + "</i></small>")
        g.attach(lbl_ayuda, 1, 3, 2, 1)
        self.get_content_area().add(g)

        if id_plano:
            rows = Modelo.devolver_plano(id_plano)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.e_imagen.set_text(s(r[3]))
                self.e_orden.set_text(s(r[4]))
        else:
            self.e_orden.set_text("0")

        self.show_all()

    def _explorar(self, btn):
        dlg = Gtk.FileChooserDialog(
            title=_("Seleccionar imagen del plano"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Abrir"), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name(_("Imágenes"))
        filt.add_mime_type("image/*")
        filt.add_pattern("*.svg")
        filt.add_pattern("*.SVG")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if ruta:
                # Mismo criterio que _DialogoImagen (catalogos_basicos_ui.py,
                # Entrega 8): copiar a IMG_DIR pisando el destino, salvo que
                # origen y destino sean literalmente el mismo archivo.
                os.makedirs(IMG_DIR, exist_ok=True)
                nombre = os.path.basename(ruta)
                destino = os.path.join(IMG_DIR, nombre)
                if os.path.abspath(ruta) != os.path.abspath(destino):
                    try:
                        shutil.copy2(ruta, destino)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la imagen: {e}")
                self.e_imagen.set_text(nombre)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            path = self.e_imagen.get_text().strip() or None
            try:
                orden = int(self.e_orden.get_text().strip() or "0")
            except ValueError:
                orden = 0
            if not nombre:
                mostrar_error(self, _("El plano necesita un nombre."))
            else:
                if path and not os.path.isfile(os.path.join(IMG_DIR, path)):
                    mostrar_error(
                        self,
                        _("El archivo '{0}' no está en la carpeta de "
                          "imágenes ({1}). El plano se va a guardar igual, "
                          "pero la imagen va a aparecer en negro (\"Sin "
                          "imagen\") hasta que copies el archivo ahí — usá "
                          "el botón \"Explorar\" en vez de escribir la ruta "
                          "a mano.").format(path, IMG_DIR))
                if self.id_plano:
                    Modelo.modificacion_plano(self.id_plano, nombre, path,
                                              orden)
                else:
                    Modelo.alta_plano_retorna_id(nombre, path, orden)
        self.destroy()
