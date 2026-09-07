#!/usr/bin/env python3
"""
planos_ui.py — CableDoc GTK3

Dominio Planos, plan_desarrollo_ubicacion_fisica_planos.md.

Contiene:
  - PlanosListado, _DialogoPlano (Fase 2: catálogo simple de planos)
  - MueblesListado, _DialogoMueble (Fase 6: catálogo de muebles +
    asignación de equipos sobre cada uno)
  - VistaPlanoInteractivo (Fase 4: overlay de salas en el plano;
    Fase 5: + overlay de racks — cuadrados; Fase 6: + overlay de
    muebles — rectángulos, con los equipos que contienen; Fase 7: +
    overlay de equipos sueltos — círculos — y clic sobre un rack para
    listar/resaltar sus equipos, directos y módulos de frame)

El editor gráfico de _DialogoEquipoNoRackSala (tipo de montaje, filtro
de módulos de frame, botón "Ubicar en el plano") vive en
racks_salas_ui.py, mismo criterio de separación por dominio que
_DialogoRackPorSala (Fase 5) — este archivo (planos_ui.py) sólo aloja el
visor interactivo y los catálogos propios de Plano/Mueble.

Fase 5 ("Overlay de racks (puntos)"): a diferencia del contorno de sala
(polígono libre, dibujado a mano vértice por vértice con
CoordenadasImagenSeleccion(modo_poligono=True)), el rack se ubica con un
único punto (x_pct/y_pct) — dibujado en el overlay como un cuadrado, no
como un círculo, para diferenciarlo a simple vista de futuros elementos
redondos (equipos sueltos, Fase 7) — se reutiliza el modo solo_xy=True ya existente de
CoordenadasImagenSeleccion (mismo mecanismo histórico usado para ubicar
conectores/slots sobre la imagen de un equipo) vía abrir_coords_imagen.
El punto de un rack sólo puede editarse si ese rack YA figura en
rack_por_sala para una sala que a su vez ya tiene un plano asignado — el
botón "📍 Ubicar en el plano" en _DialogoRackPorSala (racks_salas_ui.py)
está deshabilitado hasta que se cumplen ambas condiciones (ver el
docstring de esa clase).

Sigue el mismo patrón que `_DialogoImagen` (catalogos_basicos_ui.py) para
la selección de imagen: un botón "Explorar" copia el archivo elegido a
IMG_DIR y completa el campo con el nombre de archivo. A diferencia de
`_DialogoImagen`, acá no se elige una fila ya existente de la tabla
`imagen` vía `ImagenesListado` — `Modelo.alta_plano_retorna_id`/
`modificacion_plano` gestionan su propia fila de `imagen` asociada
(1 a 1 con el plano) para no dejar imágenes húerfanas ni compartidas
entre planos.

VistaPlanoInteractivo (Fase 4, "Overlay de salas en el plano") dibuja,
sobre la imagen del plano, el contorno (sala.poligono) de todas las
salas que ya tienen uno cargado para ese plano — modo navegar, sólo
lectura vía overlay Cairo — y ofrece un selector de sala + botón para
dibujar/rehacer su contorno, reutilizando en modo_poligono el mismo
CoordenadasImagenSeleccion de la Fase 3 (imagen_conectores_ui.py).

Fase 5 ("Overlay de racks") suma, sobre el mismo overlay, un cuadrado por
cada rack de rack_por_sala que ya tiene x_pct/y_pct cargado (dibujado
aunque la sala dueña todavía no tenga contorno propio — ver el ajuste
correspondiente en Modelo.devolver_contenido_plano) + un selector de
rack + botón para ubicarlo/moverlo, reutilizando en solo_xy=True el
mismo CoordenadasImagenSeleccion.

Fase 6 ("Muebles") suma un rectángulo por cada mueble con geometría
cargada (x_pct/y_pct/ancho_pct/alto_pct), con los equipos que tiene
asignados dibujados dentro (posición relativa al rectángulo, resuelta a
absoluta acá igual que hace Modelo.devolver_ubicacion_fisica_de_equipo)
+ un selector de mueble + botón para ubicar/redimensionar su rectángulo,
reutilizando esta vez el modo rectángulo ya existente de
CoordenadasImagenSeleccion (solo_xy=False, el mismo mecanismo histórico
de selección de área sobre la imagen de un equipo — sin cambios en
imagen_conectores_ui.py, el plan ya lo anticipaba así en la sección 3.2).
MueblesListado/_DialogoMueble (nuevas en esta fase) manejan el
alta/edición del mueble en sí (nombre, sala, tipo) y la asignación de
equipos que contiene — con el mismo botón "▭ Definir rectángulo en el
plano" que abre este visor enfocado en el mueble, patrón idéntico al
"📍 Ubicar en el plano" de _DialogoRackPorSala en la Fase 5. Todavía no
dibuja equipos sueltos directos (eso llega en la Fase 7):
Modelo.devolver_contenido_plano ya devuelve esa información lista para
cuando corresponda, pero se ignora a propósito acá para no salirse del
criterio de cierre de esta fase.

Fase 7 ("Equipos sueltos, módulos de frame y herencia de ubicación")
suma, sobre el mismo overlay, un círculo por cada equipo suelto directo
(equiponoraqueable_por_sala) con punto ya cargado — sólido para
tipo_montaje=PISO, punteado para PARED, con ícono acorde (🖴/🧱) — más un
selector de equipo suelto + botón "📍 Ubicar/mover" (mismo mecanismo de
punto simple del rack en la Fase 5, pero conservando el tipo_montaje ya
elegido en _DialogoEquipoNoRackSala de racks_salas_ui.py, que esta
Fase 7 también extiende con ese selector y con el filtro
`excluir_modulos_de_frame=True` en el buscador de equipo). Suma además
hit-testing simple (clic + distancia en la imagen) sobre los cuadrados
de rack: al hacer clic se resalta el rack con un halo amarillo y se
lista, debajo del visor, tanto los equipos montados directo en él como
los módulos instalados en los frames que contiene
(Modelo.devolver_equipos_de_rack_con_modulos) — la resolución completa
de la cadena (rack directo → módulo de frame rackeado → mueble → suelto)
ya la hacía Modelo.devolver_ubicacion_fisica_de_equipo desde la Fase 1,
sin consumidor hasta ahora salvo el propio overlay de sólo lectura.
equipos_ui.py suma el checkbox "Es módulo de frame" en _DialogoEquipo.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import os
import json
import math
import shutil

from modelo import Modelo, IMG_DIR, DimensionesImagenError

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
    _ImagenZoom,
    _pixbuf_from_name_con_motivo,
)
from imagen_conectores_ui import abrir_coords_imagen


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


# ─── Muebles (Fase 6) ───────────────────────────────────────────────────────

class MueblesListado(VentanaListado):
    """Catálogo simple de muebles (mesas/escritorios) — el rectángulo
    sobre el plano y la asignación de equipos se editan desde
    _DialogoMueble, no desde acá (mismo criterio que _DialogoRackPorSala
    con su botón "📍 Ubicar en el plano")."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Muebles"),
            [_("ID"), _("Sala"), _("Nombre"), _("Tipo"), _("Ubicación")],
            parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        filas = []
        for id_mueble, id_sala, nombre_sala, nombre, tipo, x_pct in \
                Modelo.devolver_todos_los_muebles():
            ubicacion = _("Sin ubicar") if x_pct is None else _("Ubicado")
            filas.append((id_mueble, nombre_sala, nombre, tipo, ubicacion))
        self._poblar(filas)

    def nuevo(self):
        dlg = _DialogoMueble(parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def editar(self, id_):
        dlg = _DialogoMueble(id_mueble=id_, parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def eliminar(self, id_):
        Modelo.eliminar_mueble(id_)


class _DialogoMueble(Gtk.Dialog):
    """Alta/edición de un mueble: nombre, sala, tipo — más dos secciones
    que sólo se habilitan una vez guardado (self.id_mueble, igual
    criterio que _DialogoRackPorSala en la Fase 5, porque tanto el
    rectángulo como los equipos que contiene son filas que dependen de
    que el mueble ya exista):

      - "▭ Definir rectángulo en el plano": abre VistaPlanoInteractivo
        enfocado en este mueble (id_mueble_foco), reutilizando el modo
        rectángulo ya existente de CoordenadasImagenSeleccion
        (solo_xy=False) — mismo patrón que el punto de un rack en la
        Fase 5, sólo que acá el resultado son 4 valores (x, y, ancho,
        alto) en vez de 2. Habilitado sólo si la sala ya tiene un plano
        asignado.

      - Lista de equipos asignados + "➕ Agregar equipo" (selector
        EquiposListado filtrado con excluir_modulos_de_frame=True,
        posición relativa inicial 50/50 — centrado, después ajustable)
        + "➖ Quitar equipo" + "📍 Ubicar dentro del mueble" (reutiliza
        abrir_coords_imagen en modo punto sobre la imagen COMPLETA del
        plano, no una vista recortada del mueble — se precarga con la
        posición absoluta actual del equipo, resuelta desde su offset
        relativo, y al aceptar se vuelve a expresar como % relativo al
        rectángulo del mueble, recortado a 0-100 si el clic cae afuera).
        Habilitada sólo si además el mueble ya tiene su propio
        rectángulo definido (si no, no hay `mueble.ancho_pct`/`alto_pct`
        con qué calcular el relativo)."""

    def __init__(self, id_mueble=None, parent=None):
        titulo = _("Editar Mueble") if id_mueble else _("Nuevo Mueble")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(460, 460)
        self.id_mueble = id_mueble
        self._id_plano_de_sala = None

        ca = self.get_content_area()
        g = _grid()
        ca.pack_start(g, False, False, 0)

        _lbl_entry(g, _("Sala:"), 0)
        self.e_sala = _entry_btn(g, 0, "…", self._sel_sala)
        self._id_sala = None

        _lbl_entry(g, _("Nombre:"), 1)
        self.e_nombre = _entry(g, 1)

        _lbl_entry(g, _("Tipo:"), 2)
        self.e_tipo = _entry(g, 2)

        self.lbl_rectangulo = Gtk.Label(xalign=0)
        self.lbl_rectangulo.set_margin_start(8)
        self.lbl_rectangulo.set_margin_top(4)
        ca.pack_start(self.lbl_rectangulo, False, False, 0)

        self.btn_rectangulo = Gtk.Button(
            label="▭ " + _("Definir rectángulo en el plano"))
        self.btn_rectangulo.set_margin_start(8)
        self.btn_rectangulo.set_margin_bottom(4)
        self.btn_rectangulo.connect("clicked", self._definir_rectangulo)
        ca.pack_start(self.btn_rectangulo, False, False, 0)

        ca.pack_start(Gtk.Separator(), False, False, 4)

        lbl_equipos = Gtk.Label(xalign=0)
        lbl_equipos.set_markup("<b>" + _("Equipos en este mueble") + "</b>")
        lbl_equipos.set_margin_start(8)
        ca.pack_start(lbl_equipos, False, False, 0)

        self._store_equipos = Gtk.ListStore(str, str, str, str)  # id, nombre, x%, y%
        tv = Gtk.TreeView(model=self._store_equipos)
        for i, titulo_col in enumerate(
                [_("ID"), _("Equipo"), _("X %"), _("Y %")]):
            tv.append_column(Gtk.TreeViewColumn(
                titulo_col, Gtk.CellRendererText(), text=i))
        self._tv_equipos = tv
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(140)
        scroll.set_margin_start(8); scroll.set_margin_end(8)
        scroll.add(tv)
        ca.pack_start(scroll, True, True, 0)

        hb_eq = Gtk.Box(spacing=6)
        hb_eq.set_margin_start(8); hb_eq.set_margin_end(8)
        hb_eq.set_margin_bottom(6)
        btn_agregar = Gtk.Button(label="➕ " + _("Agregar equipo"))
        btn_agregar.connect("clicked", self._agregar_equipo)
        hb_eq.pack_start(btn_agregar, False, False, 0)
        btn_quitar = Gtk.Button(label="➖ " + _("Quitar equipo"))
        btn_quitar.connect("clicked", self._quitar_equipo)
        hb_eq.pack_start(btn_quitar, False, False, 0)
        self.btn_ubicar_equipo = Gtk.Button(
            label="📍 " + _("Ubicar dentro del mueble"))
        self.btn_ubicar_equipo.connect("clicked", self._ubicar_equipo)
        hb_eq.pack_start(self.btn_ubicar_equipo, False, False, 0)
        ca.pack_start(hb_eq, False, False, 0)

        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(_("Guardar"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        self._geometria = (None, None, None, None)  # x_pct,y_pct,ancho_pct,alto_pct
        if id_mueble:
            rows = Modelo.devolver_mueble(id_mueble)
            if rows:
                r = rows[0]
                self._id_sala = str(r[1])
                self.e_nombre.set_text(s(r[2]))
                self.e_tipo.set_text(s(r[3]) or "MESA")
                self._geometria = (r[4], r[5], r[6], r[7])
                self._id_plano_de_sala = r[8]
                rows_sala = Modelo.devolver_sala(self._id_sala)
                if rows_sala:
                    self.e_sala.set_text(s(rows_sala[0][1]))
            self._cargar_equipos()
        else:
            self.e_tipo.set_text("MESA")

        self._actualizar_estado_rectangulo()
        self.show_all()

    def _sel_sala(self, btn):
        from racks_salas_ui import SalasListado
        dlg = SalasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_sala = str(fila[0])
                self.e_sala.set_text(s(fila[1]))
                rows_sala = Modelo.devolver_sala(self._id_sala)
                self._id_plano_de_sala = rows_sala[0][2] if rows_sala else None
        dlg.destroy()
        self._actualizar_estado_rectangulo()

    def _actualizar_estado_rectangulo(self):
        x_pct, y_pct, ancho_pct, alto_pct = self._geometria
        tiene_rect = None not in (x_pct, y_pct, ancho_pct, alto_pct)
        habilitar = bool(self.id_mueble and self._id_plano_de_sala)
        self.btn_rectangulo.set_sensitive(habilitar)
        self.btn_ubicar_equipo.set_sensitive(habilitar and tiene_rect)
        if not self.id_mueble:
            texto = _("Guardá el mueble primero; el rectángulo se define "
                      "al volver a editarlo.")
        elif not self._id_plano_de_sala:
            texto = _("La sala de este mueble todavía no tiene un plano "
                      "asignado — asignaselo desde la ficha de Sala.")
        elif not tiene_rect:
            texto = _("Sin rectángulo todavía — definilo con el botón "
                      "de abajo antes de ubicar equipos dentro.")
        else:
            texto = _("Rectángulo definido ({0:.0f}% × {1:.0f}%). Podés "
                      "redefinirlo con el botón de abajo.").format(
                          ancho_pct, alto_pct)
        self.lbl_rectangulo.set_markup("<small><i>" + texto + "</i></small>")

    def _definir_rectangulo(self, btn):
        from planos_ui import VistaPlanoInteractivo
        VistaPlanoInteractivo(
            self._id_plano_de_sala, parent=self,
            id_mueble_foco=self.id_mueble).run_and_destroy()
        rows = Modelo.devolver_mueble(self.id_mueble)
        if rows:
            r = rows[0]
            self._geometria = (r[4], r[5], r[6], r[7])
        self._actualizar_estado_rectangulo()

    def _cargar_equipos(self):
        self._store_equipos.clear()
        if not self.id_mueble:
            return
        for id_equipo, nombre_eq, x_rel, y_rel in \
                Modelo.devolver_equipos_de_mueble(self.id_mueble):
            self._store_equipos.append([
                str(id_equipo), s(nombre_eq),
                "{0:.0f}".format(x_rel) if x_rel is not None else "—",
                "{0:.0f}".format(y_rel) if y_rel is not None else "—",
            ])

    def _agregar_equipo(self, btn):
        if not self.id_mueble:
            mostrar_error(
                self, _("Guardá el mueble primero — un equipo no puede "
                        "asignarse a un mueble que todavía no existe."))
            return
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True,
                             excluir_modulos_de_frame=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                try:
                    Modelo.asignar_equipo_a_mueble(
                        fila[0], self.id_mueble, 50, 50)
                except ValueError as e:
                    mostrar_error(self, str(e))
                else:
                    self._cargar_equipos()
        dlg.destroy()

    def _quitar_equipo(self, btn):
        sel = self._tv_equipos.get_selection()
        modelo, it = sel.get_selected()
        if not it:
            mostrar_error(self, _("Seleccioná un equipo de la lista primero."))
            return
        id_equipo = modelo.get_value(it, 0)
        Modelo.quitar_equipo_de_mueble(id_equipo)
        self._cargar_equipos()

    def _ubicar_equipo(self, btn):
        sel = self._tv_equipos.get_selection()
        modelo, it = sel.get_selected()
        if not it:
            mostrar_error(self, _("Seleccioná un equipo de la lista primero."))
            return
        id_equipo = modelo.get_value(it, 0)
        x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m = self._geometria
        if None in (x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m):
            mostrar_error(
                self, _("Este mueble todavía no tiene rectángulo — "
                        "definilo primero."))
            return

        filas_plano = Modelo.devolver_plano(self._id_plano_de_sala)
        if not filas_plano:
            mostrar_error(self, _("No se encontró el plano de la sala."))
            return
        id_imagen_plano = filas_plano[0][2]
        path_imagen_plano = filas_plano[0][3]

        x_rel_actual = y_rel_actual = 50
        for id_e, _nombre_e, xr, yr in Modelo.devolver_equipos_de_mueble(self.id_mueble):
            if str(id_e) == str(id_equipo):
                x_rel_actual = xr if xr is not None else 50
                y_rel_actual = yr if yr is not None else 50
                break
        x_pct_abs_actual = x_pct_m + (x_rel_actual / 100.0) * ancho_pct_m
        y_pct_abs_actual = y_pct_m + (y_rel_actual / 100.0) * alto_pct_m
        x_px_actual, y_px_actual = Modelo._px_punto_o_crudo(
            path_imagen_plano, x_pct_abs_actual, y_pct_abs_actual)

        resultado = abrir_coords_imagen(
            id_imagen_plano, solo_xy=True,
            x=s(x_px_actual) if x_px_actual is not None else "",
            y=s(y_px_actual) if y_px_actual is not None else "",
            parent=self)
        if not resultado:
            return
        try:
            x_px_nuevo = int(float(resultado["x"]))
            y_px_nuevo = int(float(resultado["y"]))
        except (ValueError, TypeError):
            mostrar_error(
                self, _("No se marcó ningún punto sobre la imagen — no "
                        "se guardó la ubicación del equipo."))
            return
        try:
            x_pct_abs, y_pct_abs = Modelo._punto_px_a_pct(
                path_imagen_plano, x_px_nuevo, y_px_nuevo)
        except DimensionesImagenError:
            mostrar_error(
                self, _("No se pudo determinar el tamaño de la imagen "
                        "del plano — no se guardó la ubicación."))
            return

        # de absoluto (% del plano) a relativo (% del rectángulo del
        # mueble), recortado a 0-100 si el clic cayó afuera del mueble
        x_rel = (x_pct_abs - x_pct_m) / ancho_pct_m * 100.0 if ancho_pct_m else 50
        y_rel = (y_pct_abs - y_pct_m) / alto_pct_m * 100.0 if alto_pct_m else 50
        x_rel = max(0.0, min(100.0, x_rel))
        y_rel = max(0.0, min(100.0, y_rel))

        Modelo.asignar_equipo_a_mueble(id_equipo, self.id_mueble, x_rel, y_rel)
        self._cargar_equipos()

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return
        nombre = self.e_nombre.get_text().strip()
        tipo = self.e_tipo.get_text().strip() or "MESA"
        if not self._id_sala or not nombre:
            mostrar_error(self, _("Elegí una sala y escribí un nombre "
                                  "antes de guardar."))
            return
        x_pct, y_pct, ancho_pct, alto_pct = self._geometria
        if self.id_mueble:
            Modelo.modificacion_mueble(
                self.id_mueble, nombre, x_pct, y_pct, ancho_pct, alto_pct,
                tipo)
        else:
            self.id_mueble = Modelo.alta_mueble_retorna_id(
                self._id_sala, nombre, x_pct, y_pct, ancho_pct, alto_pct,
                tipo)

    def run_and_destroy(self):
        self.run()
        self.destroy()


# ─── Vista interactiva del plano (Fase 4) ──────────────────────────────────────

class VistaPlanoInteractivo(Gtk.Dialog):
    """Overlay de salas sobre la imagen de un plano.

    Modo navegar (siempre activo): dibuja el contorno de cada sala que
    pertenece a este plano y ya tiene sala.poligono cargado, con su
    nombre centrado. Sólo lectura — el overlay se redibuja con Cairo
    sobre `_ImagenZoom`, no hay hit-testing todavía sobre los polígonos
    (eso es una mejora de la Fase 9 "Pulido": tooltips/clic al pasar el
    mouse; por ahora la selección de sala es siempre vía el combo).

    Modo editar (botón "✏ Editar contorno de esta sala"): abre
    CoordenadasImagenSeleccion en modo_poligono=True (Fase 3) precargado
    con el contorno actual de la sala elegida en el combo (convertido de
    % a píxeles de imagen), y al aceptar con el polígono cerrado guarda
    el resultado (convertido de vuelta a %) vía
    Modelo.actualizar_ubicacion_sala. El combo incluye TODAS las salas
    del plano (Modelo.devolver_salas_de_plano), tengan o no contorno
    todavía — a diferencia del overlay de sólo lectura, que sólo dibuja
    las que ya lo tienen (Modelo.devolver_contenido_plano).

    Modo editar rack (Fase 5, botón "📍 Ubicar/mover este rack en el
    plano"): a diferencia del contorno de sala, el punto de un rack es
    simple — se reutiliza CoordenadasImagenSeleccion en su modo
    solo_xy=True (histórico, el mismo que ya usan conectores/slots) vía
    abrir_coords_imagen, precargado con la posición actual si ya tiene
    una. El combo "Rack:" incluye TODOS los rack_por_sala cuya sala
    pertenece a este plano (Modelo.devolver_racks_por_sala_de_plano),
    tengan o no punto todavía — igual criterio que el combo de salas.

    Modo editar mueble (Fase 6, botón "▭ Ubicar/redimensionar este
    mueble en el plano"): a diferencia del rack (un punto), el mueble es
    un rectángulo — se reutiliza CoordenadasImagenSeleccion en su modo
    solo_xy=False (histórico, el mismo que ya usa la selección de área
    sobre la imagen de un equipo), que devuelve (x, y, ancho, alto) en
    píxeles en vez de sólo (x, y). El combo "Mueble:" incluye TODOS los
    muebles cuyas salas pertenecen a este plano
    (Modelo.devolver_muebles_de_plano), tengan o no rectángulo todavía.

    Uso:
        VistaPlanoInteractivo(id_plano, parent=p,
                              id_sala_foco=id_sala).run_and_destroy()
    id_sala_foco (opcional): preselecciona esa sala en el combo al abrir
    — usado por _DialogoSala."Editar contorno en el plano"
    (racks_salas_ui.py) para no obligar a volver a buscarla.
    id_rack_x_sala_foco (opcional, Fase 5): preselecciona ese
    rack_por_sala en el combo "Rack:" al abrir — usado por
    _DialogoRackPorSala."📍 Ubicar en el plano" (racks_salas_ui.py).
    id_mueble_foco (opcional, Fase 6): preselecciona ese mueble en el
    combo "Mueble:" al abrir — usado por _DialogoMueble."▭ Definir
    rectángulo en el plano" (este mismo archivo).

    Modo editar equipo suelto (Fase 7, botón "📍 Ubicar/mover este
    equipo suelto en el plano"): mismo mecanismo de punto simple que el
    rack (Fase 5, CoordenadasImagenSeleccion en solo_xy=True), pero
    conserva el tipo_montaje ya cargado (Piso/Pared, elegido en
    _DialogoEquipoNoRackSala de racks_salas_ui.py) — este botón sólo
    mueve el punto, no cambia el tipo de montaje. El combo "Equipo
    suelto:" incluye TODOS los equiponoraqueable_por_sala de salas de
    este plano (Modelo.devolver_equiponoraqueable_de_plano), tengan o
    no punto todavía — igual criterio que rack/mueble.
    id_equiponoraqueable_foco (opcional, Fase 7): preselecciona ese
    equipo suelto en el combo al abrir — usado por
    _DialogoEquipoNoRackSala."📍 Ubicar en el plano" (racks_salas_ui.py).

    Fase 7 también agrega, sobre el mismo overlay de sólo lectura, el
    punto de cada equipo suelto directo (círculo, con ícono/borde según
    tipo_montaje: sólido para Piso, punteado para Pared — a diferencia
    del cuadrado de rack y el rectángulo de mueble) y un clic sobre el
    cuadrado de un rack (hit-testing simple por distancia en la imagen,
    tolerancia de ~20px en pantalla ajustada por zoom) que lista y
    resalta tanto los equipos montados directo en ese rack como los
    módulos instalados en los frames que contiene
    (Modelo.devolver_equipos_de_rack_con_modulos) — el resaltado
    (self._rack_resaltado) se dibuja con un halo amarillo alrededor del
    cuadrado hasta el próximo clic en otro rack o el cierre del visor.
    """

    COLOR_SALA = (0.10, 0.45, 0.90)   # azul — contorno sólido + relleno tenue
    COLOR_RACK = (0.85, 0.45, 0.05)   # naranja — cuadrado de rack
    COLOR_MUEBLE = (0.15, 0.60, 0.35)  # verde — rectángulo de mueble
    COLOR_SUELTO = (0.55, 0.15, 0.65)  # violeta — círculo de equipo suelto
    COLOR_RESALTADO = (1.0, 0.85, 0.0)  # amarillo — halo del rack clickeado

    def __init__(self, id_plano, parent=None, id_sala_foco=None,
                 id_rack_x_sala_foco=None, id_mueble_foco=None,
                 id_equiponoraqueable_foco=None):
        self._rack_resaltado = None
        self.id_plano = id_plano
        filas_plano = Modelo.devolver_plano(id_plano)
        nombre_plano = s(filas_plano[0][1]) if filas_plano else "?"
        self.id_imagen = filas_plano[0][2] if filas_plano else None
        self.path_imagen = filas_plano[0][3] if filas_plano else ""

        super().__init__(
            title="🗺 " + _("Plano: {0}").format(nombre_plano),
            transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1050, 750)
        self.connect("response", lambda d, r: d.destroy())

        ca = self.get_content_area()

        self._viz = _ImagenZoom()
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("realize", self._on_viz_realize)
        self._viz.da.connect("button-press-event", self._on_click_overlay)
        ca.pack_start(self._viz, True, True, 0)

        if self.id_imagen:
            pb, motivo = _pixbuf_from_name_con_motivo(self.path_imagen)
            if pb:
                self._viz.set_pixbuf(pb)
            else:
                self._viz.set_motivo_sin_imagen(motivo)
        else:
            self._viz.set_motivo_sin_imagen(
                _("Este plano todavía no tiene una imagen cargada."))

        # ── barra inferior: selector de sala + editar contorno ──
        hb = Gtk.Box(spacing=6)
        hb.set_margin_start(8); hb.set_margin_end(8)
        hb.set_margin_top(4);  hb.set_margin_bottom(8)
        hb.pack_start(Gtk.Label(label=_("Sala:")), False, False, 0)

        self._combo_salas = Gtk.ComboBoxText()
        hb.pack_start(self._combo_salas, True, True, 0)
        self._cargar_combo_salas(id_sala_foco)

        btn_editar = Gtk.Button(
            label="✏ " + _("Editar contorno de esta sala"))
        btn_editar.connect("clicked", self._editar_contorno_sala)
        hb.pack_start(btn_editar, False, False, 0)
        ca.pack_start(hb, False, False, 0)

        # ── barra inferior 2: selector de rack + ubicar en el plano (Fase 5) ──
        hb2 = Gtk.Box(spacing=6)
        hb2.set_margin_start(8); hb2.set_margin_end(8)
        hb2.set_margin_top(0);  hb2.set_margin_bottom(8)
        hb2.pack_start(Gtk.Label(label=_("Rack:")), False, False, 0)

        self._combo_racks = Gtk.ComboBoxText()
        hb2.pack_start(self._combo_racks, True, True, 0)
        self._rack_pcts = {}
        self._cargar_combo_racks(id_rack_x_sala_foco)

        btn_ubicar_rack = Gtk.Button(
            label="📍 " + _("Ubicar/mover este rack en el plano"))
        btn_ubicar_rack.connect("clicked", self._ubicar_rack)
        hb2.pack_start(btn_ubicar_rack, False, False, 0)
        ca.pack_start(hb2, False, False, 0)

        # ── barra inferior 3: selector de mueble + ubicar/redimensionar (Fase 6) ──
        hb3 = Gtk.Box(spacing=6)
        hb3.set_margin_start(8); hb3.set_margin_end(8)
        hb3.set_margin_top(0);  hb3.set_margin_bottom(8)
        hb3.pack_start(Gtk.Label(label=_("Mueble:")), False, False, 0)

        self._combo_muebles = Gtk.ComboBoxText()
        hb3.pack_start(self._combo_muebles, True, True, 0)
        self._mueble_geoms = {}
        self._cargar_combo_muebles(id_mueble_foco)

        btn_ubicar_mueble = Gtk.Button(
            label="▭ " + _("Ubicar/redimensionar este mueble en el plano"))
        btn_ubicar_mueble.connect("clicked", self._ubicar_mueble)
        hb3.pack_start(btn_ubicar_mueble, False, False, 0)
        ca.pack_start(hb3, False, False, 0)

        # ── barra inferior 4: selector de equipo suelto + ubicar (Fase 7) ──
        hb4 = Gtk.Box(spacing=6)
        hb4.set_margin_start(8); hb4.set_margin_end(8)
        hb4.set_margin_top(0);  hb4.set_margin_bottom(8)
        hb4.pack_start(Gtk.Label(label=_("Equipo suelto:")), False, False, 0)

        self._combo_equipos_sueltos = Gtk.ComboBoxText()
        hb4.pack_start(self._combo_equipos_sueltos, True, True, 0)
        self._equipo_suelto_datos = {}
        self._cargar_combo_equipos_sueltos(id_equiponoraqueable_foco)

        btn_ubicar_suelto = Gtk.Button(
            label="📍 " + _("Ubicar/mover este equipo suelto en el plano"))
        btn_ubicar_suelto.connect("clicked", self._ubicar_equipo_suelto)
        hb4.pack_start(btn_ubicar_suelto, False, False, 0)
        ca.pack_start(hb4, False, False, 0)

        # ── barra inferior 5: lo que muestra el clic sobre un rack (Fase 7) ──
        self.lbl_rack_resaltado = Gtk.Label(xalign=0)
        self.lbl_rack_resaltado.set_margin_start(8)
        self.lbl_rack_resaltado.set_margin_bottom(8)
        self.lbl_rack_resaltado.set_line_wrap(True)
        self.lbl_rack_resaltado.set_markup(
            "<small><i>" +
            _("Hacé clic sobre el cuadrado de un rack para listar los "
              "equipos que tiene montados (directos y módulos de sus "
              "frames).") + "</i></small>")
        ca.pack_start(self.lbl_rack_resaltado, False, False, 0)

        self.show_all()

    def _on_viz_realize(self, widget):
        if self._viz.pixbuf:
            self._viz._zoom_fit()

    def _cargar_combo_salas(self, id_sala_foco=None):
        self._combo_salas.remove_all()
        salas = Modelo.devolver_salas_de_plano(self.id_plano)
        indice_foco = 0
        for i, (id_sala, nombre_sala, poligono) in enumerate(salas):
            etiqueta = nombre_sala if poligono else (
                nombre_sala + " " + _("(sin contorno)"))
            self._combo_salas.append(str(id_sala), etiqueta)
            if id_sala_foco and str(id_sala) == str(id_sala_foco):
                indice_foco = i
        if salas:
            self._combo_salas.set_active(indice_foco)

    def _cargar_combo_racks(self, id_rack_x_sala_foco=None):
        """Fase 5: pobla el combo "Rack:" con TODOS los rack_por_sala de
        salas de este plano (tengan o no punto todavía) — mismo criterio
        que _cargar_combo_salas. self._rack_pcts guarda (x_pct, y_pct)
        actuales por id_rack_x_sala para precargar el selector de
        coordenadas en _ubicar_rack sin tener que volver a consultar."""
        self._combo_racks.remove_all()
        self._rack_pcts = {}
        racks = Modelo.devolver_racks_por_sala_de_plano(self.id_plano)
        indice_foco = 0
        for i, (id_rxs, nombre_sala, nombre_rack, x_pct, y_pct) in enumerate(racks):
            self._rack_pcts[id_rxs] = (x_pct, y_pct)
            etiqueta = "{0} — {1}".format(s(nombre_sala), s(nombre_rack))
            if x_pct is None or y_pct is None:
                etiqueta += " " + _("(sin ubicar)")
            self._combo_racks.append(str(id_rxs), etiqueta)
            if id_rack_x_sala_foco and str(id_rxs) == str(id_rack_x_sala_foco):
                indice_foco = i
        if racks:
            self._combo_racks.set_active(indice_foco)

    def _cargar_combo_muebles(self, id_mueble_foco=None):
        """Fase 6: pobla el combo "Mueble:" con TODOS los muebles de
        salas de este plano (tengan o no rectángulo todavía) — mismo
        criterio que _cargar_combo_racks. self._mueble_geoms guarda
        (x_pct, y_pct, ancho_pct, alto_pct) actuales por id_mueble para
        precargar el selector de rectángulo en _ubicar_mueble."""
        self._combo_muebles.remove_all()
        self._mueble_geoms = {}
        muebles = Modelo.devolver_muebles_de_plano(self.id_plano)
        indice_foco = 0
        for i, (id_mueble, nombre_sala, nombre_mueble, x_pct, y_pct,
                ancho_pct, alto_pct) in enumerate(muebles):
            self._mueble_geoms[id_mueble] = (x_pct, y_pct, ancho_pct, alto_pct)
            etiqueta = "{0} — {1}".format(s(nombre_sala), s(nombre_mueble))
            if x_pct is None:
                etiqueta += " " + _("(sin ubicar)")
            self._combo_muebles.append(str(id_mueble), etiqueta)
            if id_mueble_foco and str(id_mueble) == str(id_mueble_foco):
                indice_foco = i
        if muebles:
            self._combo_muebles.set_active(indice_foco)

    def _cargar_combo_equipos_sueltos(self, id_en_foco=None):
        """Fase 7: pobla el combo "Equipo suelto:" con TODOS los
        equiponoraqueable_por_sala de salas de este plano (tengan o no
        punto todavía) — mismo criterio que _cargar_combo_racks/
        _cargar_combo_muebles. self._equipo_suelto_datos guarda
        (x_pct, y_pct, tipo_montaje) actuales por
        id_equiponoraqueable_por_sala, para precargar el selector de
        coordenadas en _ubicar_equipo_suelto sin volver a consultar y
        para conservar el tipo_montaje ya elegido (ese botón sólo mueve
        el punto, no lo cambia)."""
        self._combo_equipos_sueltos.remove_all()
        self._equipo_suelto_datos = {}
        equipos = Modelo.devolver_equiponoraqueable_de_plano(self.id_plano)
        indice_foco = 0
        for i, (id_en, nombre_sala, nombre_eq, x_pct, y_pct,
                tipo_montaje) in enumerate(equipos):
            self._equipo_suelto_datos[id_en] = (x_pct, y_pct, tipo_montaje)
            etiqueta = "{0} — {1}".format(s(nombre_sala), s(nombre_eq))
            if x_pct is None or y_pct is None:
                etiqueta += " " + _("(sin ubicar)")
            self._combo_equipos_sueltos.append(str(id_en), etiqueta)
            if id_en_foco and str(id_en) == str(id_en_foco):
                indice_foco = i
        if equipos:
            self._combo_equipos_sueltos.set_active(indice_foco)

    # ── overlay Cairo (modo navegar) ─────────────────────────────────────
    def _dibujar_overlay(self, cr):
        if not self._viz.pixbuf:
            return
        ancho_img = self._viz.pixbuf.get_width()
        alto_img = self._viz.pixbuf.get_height()
        if not ancho_img or not alto_img:
            return

        contenido = Modelo.devolver_contenido_plano(self.id_plano)
        r, g, b = self.COLOR_SALA
        for sala in contenido:
            # ── contorno de la sala (Fase 4) — sólo si ya está dibujado.
            # Una sala sin contorno todavía puede tener racks ya ubicados
            # (Fase 5), así que la ausencia de polígono ya NO corta el
            # resto del dibujo de esta sala (ver Modelo.devolver_contenido_plano).
            poligono = sala.get("poligono")
            vertices_pct = None
            if poligono:
                try:
                    vertices_pct = json.loads(poligono)
                except (ValueError, TypeError):
                    vertices_pct = None
            if vertices_pct and len(vertices_pct) >= 3:
                puntos_w = []
                for v in vertices_pct:
                    try:
                        x_img = (float(v.get("x_pct", 0)) / 100.0) * ancho_img
                        y_img = (float(v.get("y_pct", 0)) / 100.0) * alto_img
                    except (TypeError, ValueError):
                        continue
                    puntos_w.append(self._viz.i2w(x_img, y_img))
                if len(puntos_w) >= 3:
                    cr.set_source_rgba(r, g, b, 0.18)
                    cr.move_to(*puntos_w[0])
                    for wx, wy in puntos_w[1:]:
                        cr.line_to(wx, wy)
                    cr.close_path()
                    cr.fill_preserve()
                    cr.set_source_rgba(r, g, b, 0.95)
                    cr.set_line_width(max(2, 3 * self._viz.zoom))
                    cr.stroke()

                    cx = sum(p[0] for p in puntos_w) / len(puntos_w)
                    cy = sum(p[1] for p in puntos_w) / len(puntos_w)
                    cr.set_source_rgb(0.05, 0.05, 0.05)
                    cr.select_font_face("Sans", 0, 1)  # 1 = Cairo.FONT_WEIGHT_BOLD
                    cr.set_font_size(14)
                    texto = s(sala.get("nombre", ""))
                    ext = cr.text_extents(texto)
                    cr.move_to(cx - ext.width / 2, cy)
                    cr.show_text(texto)

            # ── Fase 5: puntos de rack de esta sala — representados como
            # cuadrados (no círculos) para distinguirlos a simple vista
            # de otros elementos del overlay que sí sean redondos
            # (equipos sueltos, Fase 7) ──
            r2, g2, b2 = self.COLOR_RACK
            for id_rxs, id_rack, nombre_rack, x_pct_r, y_pct_r in sala.get("racks", []):
                try:
                    x_img_r = (float(x_pct_r) / 100.0) * ancho_img
                    y_img_r = (float(y_pct_r) / 100.0) * alto_img
                except (TypeError, ValueError):
                    continue
                wx_r, wy_r = self._viz.i2w(x_img_r, y_img_r)
                lado = max(12, 18 * self._viz.zoom)  # lado del cuadrado
                mitad = lado / 2.0
                # Fase 7: halo amarillo si este es el rack resaltado por
                # el último clic (ver _on_click_overlay).
                if self._rack_resaltado is not None and id_rack == self._rack_resaltado:
                    rh, gh, bh = self.COLOR_RESALTADO
                    cr.set_source_rgba(rh, gh, bh, 0.55)
                    cr.rectangle(wx_r - mitad - 5, wy_r - mitad - 5,
                                 lado + 10, lado + 10)
                    cr.fill()
                cr.set_source_rgba(r2, g2, b2, 0.92)
                cr.rectangle(wx_r - mitad, wy_r - mitad, lado, lado)
                cr.fill_preserve()
                cr.set_source_rgb(0, 0, 0)
                cr.set_line_width(1.5)
                cr.stroke()
                cr.set_source_rgb(0.05, 0.05, 0.05)
                cr.select_font_face("Sans", 0, 0)
                cr.set_font_size(12)
                texto_r = "🗄 " + s(nombre_rack)
                cr.move_to(wx_r + mitad + 3, wy_r + 4)
                cr.show_text(texto_r)

            # ── Fase 6: rectángulo de cada mueble de esta sala, con los
            # equipos que contiene dibujados adentro (posición relativa
            # al rectángulo del mueble, resuelta acá a absoluta — mismo
            # criterio que Modelo.devolver_ubicacion_fisica_de_equipo) ──
            r3, g3, b3 = self.COLOR_MUEBLE
            for (id_mueble, nombre_mueble, x_pct_m, y_pct_m, ancho_pct_m,
                 alto_pct_m, equipos_m) in sala.get("muebles", []):
                try:
                    x_img_m = (float(x_pct_m) / 100.0) * ancho_img
                    y_img_m = (float(y_pct_m) / 100.0) * alto_img
                    ancho_img_m = (float(ancho_pct_m) / 100.0) * ancho_img
                    alto_img_m = (float(alto_pct_m) / 100.0) * alto_img
                except (TypeError, ValueError):
                    continue
                wx_m, wy_m = self._viz.i2w(x_img_m, y_img_m)
                wx_m2, wy_m2 = self._viz.i2w(
                    x_img_m + ancho_img_m, y_img_m + alto_img_m)
                cr.set_source_rgba(r3, g3, b3, 0.15)
                cr.rectangle(wx_m, wy_m, wx_m2 - wx_m, wy_m2 - wy_m)
                cr.fill_preserve()
                cr.set_source_rgba(r3, g3, b3, 0.95)
                cr.set_line_width(max(2, 2.5 * self._viz.zoom))
                cr.stroke()
                cr.set_source_rgb(0.05, 0.05, 0.05)
                cr.select_font_face("Sans", 0, 1)  # bold
                cr.set_font_size(12)
                cr.move_to(wx_m + 4, wy_m + 14)
                cr.show_text("🪑 " + s(nombre_mueble))

                for id_eq, nombre_eq, x_rel, y_rel in equipos_m:
                    try:
                        x_rel_f = max(0.0, min(100.0, float(x_rel)))
                        y_rel_f = max(0.0, min(100.0, float(y_rel)))
                    except (TypeError, ValueError):
                        continue
                    x_img_e = x_img_m + (x_rel_f / 100.0) * ancho_img_m
                    y_img_e = y_img_m + (y_rel_f / 100.0) * alto_img_m
                    wx_e, wy_e = self._viz.i2w(x_img_e, y_img_e)
                    radio_e = max(4, 6 * self._viz.zoom)
                    cr.set_source_rgba(r3, g3, b3, 0.95)
                    cr.arc(wx_e, wy_e, radio_e, 0, 2 * math.pi)
                    cr.fill()
                    cr.set_source_rgb(0.05, 0.05, 0.05)
                    cr.select_font_face("Sans", 0, 0)
                    cr.set_font_size(10)
                    cr.move_to(wx_e + radio_e + 2, wy_e + 3)
                    cr.show_text(s(nombre_eq))

            # ── Fase 7: puntos de equipo suelto directo de esta sala —
            # círculos (a diferencia del cuadrado de rack y el
            # rectángulo de mueble), con borde punteado si el tipo de
            # montaje es PARED (sólido para PISO) para distinguirlos a
            # simple vista sin depender sólo del ícono ──
            r4, g4, b4 = self.COLOR_SUELTO
            for (id_en, id_eq, nombre_eq, x_pct_s, y_pct_s,
                 tipo_montaje_s) in sala.get("equipos_sueltos", []):
                try:
                    x_img_s = (float(x_pct_s) / 100.0) * ancho_img
                    y_img_s = (float(y_pct_s) / 100.0) * alto_img
                except (TypeError, ValueError):
                    continue
                wx_s, wy_s = self._viz.i2w(x_img_s, y_img_s)
                radio_s = max(6, 8 * self._viz.zoom)
                es_pared = (tipo_montaje_s or "PISO") == "PARED"
                cr.set_source_rgba(r4, g4, b4, 0.92)
                cr.arc(wx_s, wy_s, radio_s, 0, 2 * math.pi)
                cr.fill_preserve()
                cr.set_source_rgb(0, 0, 0)
                cr.set_line_width(1.5)
                if es_pared:
                    cr.set_dash([3, 2])
                cr.stroke()
                cr.set_dash([])
                cr.set_source_rgb(0.05, 0.05, 0.05)
                cr.select_font_face("Sans", 0, 0)
                cr.set_font_size(11)
                icono = "🧱" if es_pared else "🖴"
                cr.move_to(wx_s + radio_s + 3, wy_s + 4)
                cr.show_text(icono + " " + s(nombre_eq))

    # ── modo navegar: clic sobre un rack -> listar/resaltar equipos ──────
    def _on_click_overlay(self, widget, event):
        if not self._viz.pixbuf:
            return
        ancho_img = self._viz.pixbuf.get_width()
        alto_img = self._viz.pixbuf.get_height()
        if not ancho_img or not alto_img:
            return
        ix, iy = self._viz.w2i(event.x, event.y)
        tolerancia_img = 20.0 / max(self._viz.zoom, 0.01)

        contenido = Modelo.devolver_contenido_plano(self.id_plano)
        mejor_id_rack = None
        mejor_nombre_rack = None
        mejor_dist = None
        for sala in contenido:
            for id_rxs, id_rack, nombre_rack, x_pct_r, y_pct_r in sala.get("racks", []):
                try:
                    x_img_r = (float(x_pct_r) / 100.0) * ancho_img
                    y_img_r = (float(y_pct_r) / 100.0) * alto_img
                except (TypeError, ValueError):
                    continue
                dist = math.hypot(ix - x_img_r, iy - y_img_r)
                if dist <= tolerancia_img and (mejor_dist is None or dist < mejor_dist):
                    mejor_dist = dist
                    mejor_id_rack = id_rack
                    mejor_nombre_rack = nombre_rack
        if mejor_id_rack is None:
            return

        self._rack_resaltado = mejor_id_rack
        self._viz.da.queue_draw()

        equipos = Modelo.devolver_equipos_de_rack_con_modulos(mejor_id_rack)
        if not equipos:
            texto = _("«{0}» no tiene equipos montados todavía.").format(
                s(mejor_nombre_rack))
        else:
            lineas = []
            for id_eq, nombre_eq, origen in equipos:
                if origen == "directo":
                    lineas.append("• " + s(nombre_eq) + " — " + _("directo en el rack"))
                else:
                    lineas.append(
                        "• " + s(nombre_eq) + " — " +
                        _("módulo del frame «{0}»").format(s(origen)))
            texto = _("Equipos en «{0}»:").format(s(mejor_nombre_rack)) + "\n" + "\n".join(lineas)
        self.lbl_rack_resaltado.set_markup(
            "<small>" + texto.replace("&", "&amp;").replace("<", "&lt;") + "</small>")

    # ── modo editar: dibujar/rehacer el contorno de una sala ─────────────
    def _editar_contorno_sala(self, btn):
        id_str = self._combo_salas.get_active_id()
        if not id_str:
            mostrar_error(
                self, _("Este plano todavía no tiene ninguna sala "
                        "asignada — asignaselo desde la ficha de Sala."))
            return
        if not self.id_imagen:
            mostrar_error(
                self, _("Este plano todavía no tiene una imagen cargada."))
            return
        id_sala = int(id_str)

        rows = Modelo.devolver_sala(id_sala)
        poligono_actual = rows[0][3] if rows else None
        vertices_px = None
        if poligono_actual:
            try:
                vertices_pct = json.loads(poligono_actual)
                vertices_px = [
                    Modelo._punto_pct_a_px(
                        self.path_imagen, v.get("x_pct"), v.get("y_pct"))
                    for v in vertices_pct
                ]
            except (ValueError, TypeError, DimensionesImagenError):
                vertices_px = None

        resultado = abrir_coords_imagen(
            self.id_imagen, modo_poligono=True, vertices=vertices_px,
            parent=self)
        if not resultado:
            return
        if not resultado["cerrado"] or len(resultado["vertices"]) < 3:
            mostrar_error(
                self, _("El contorno quedó sin cerrar (hacé clic sobre "
                        "el primer vértice con 3 o más ya cargados) — no "
                        "se guardó."))
            return

        vertices_pct_nuevos = []
        for x_px, y_px in resultado["vertices"]:
            try:
                x_pct, y_pct = Modelo._punto_px_a_pct(
                    self.path_imagen, x_px, y_px)
            except DimensionesImagenError:
                mostrar_error(
                    self, _("No se pudo determinar el tamaño de la "
                            "imagen del plano — no se guardó el "
                            "contorno."))
                return
            vertices_pct_nuevos.append({"x_pct": x_pct, "y_pct": y_pct})

        Modelo.actualizar_ubicacion_sala(
            id_sala, self.id_plano, json.dumps(vertices_pct_nuevos))
        self._cargar_combo_salas(id_sala_foco=id_sala)
        self._viz.da.queue_draw()

    # ── modo editar: ubicar/mover el punto de un rack (Fase 5) ───────────
    def _ubicar_rack(self, btn):
        id_str = self._combo_racks.get_active_id()
        if not id_str:
            mostrar_error(
                self, _("Este plano todavía no tiene ningún rack "
                        "asignado — asignalo primero desde \"Rack por "
                        "Sala\"."))
            return
        if not self.id_imagen:
            mostrar_error(
                self, _("Este plano todavía no tiene una imagen cargada."))
            return
        id_rxs = int(id_str)

        x_pct_actual, y_pct_actual = self._rack_pcts.get(id_rxs, (None, None))
        # _px_punto_o_crudo nunca levanta: si no se puede determinar el
        # tamaño de la imagen en este momento, precarga sin más (mismo
        # criterio que el resto de la app al mostrar un punto existente).
        x_px_actual, y_px_actual = Modelo._px_punto_o_crudo(
            self.path_imagen, x_pct_actual, y_pct_actual)

        resultado = abrir_coords_imagen(
            self.id_imagen, solo_xy=True,
            x=s(x_px_actual) if x_px_actual is not None else "",
            y=s(y_px_actual) if y_px_actual is not None else "",
            parent=self)
        if not resultado:
            return
        try:
            x_px_nuevo = int(float(resultado["x"]))
            y_px_nuevo = int(float(resultado["y"]))
        except (ValueError, TypeError):
            mostrar_error(
                self, _("No se marcó ningún punto sobre la imagen — no "
                        "se guardó la ubicación del rack."))
            return
        try:
            x_pct, y_pct = Modelo._punto_px_a_pct(
                self.path_imagen, x_px_nuevo, y_px_nuevo)
        except DimensionesImagenError:
            mostrar_error(
                self, _("No se pudo determinar el tamaño de la imagen "
                        "del plano — no se guardó la ubicación del "
                        "rack."))
            return

        Modelo.actualizar_posicion_rack_por_sala(id_rxs, x_pct, y_pct)
        self._cargar_combo_racks(id_rack_x_sala_foco=id_rxs)
        self._viz.da.queue_draw()

    # ── modo editar: ubicar/redimensionar el rectángulo de un mueble
    #    (Fase 6) — mismo flujo que _ubicar_rack pero con 4 valores en
    #    vez de 2 (x, y, ancho, alto) y el modo rectángulo
    #    (solo_xy=False) de CoordenadasImagenSeleccion. ─────────────────
    def _ubicar_mueble(self, btn):
        id_str = self._combo_muebles.get_active_id()
        if not id_str:
            mostrar_error(
                self, _("Este plano todavía no tiene ningún mueble "
                        "asignado — creá uno primero desde \"Muebles\"."))
            return
        if not self.id_imagen:
            mostrar_error(
                self, _("Este plano todavía no tiene una imagen cargada."))
            return
        id_mueble = int(id_str)

        x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m = self._mueble_geoms.get(
            id_mueble, (None, None, None, None))
        # _px_rect_o_crudo nunca levanta — mismo criterio que
        # _px_punto_o_crudo en _ubicar_rack.
        x_px_m, y_px_m, ancho_px_m, alto_px_m = Modelo._px_rect_o_crudo(
            self.path_imagen, x_pct_m, y_pct_m, ancho_pct_m, alto_pct_m)

        resultado = abrir_coords_imagen(
            self.id_imagen, solo_xy=False,
            x=s(x_px_m) if x_px_m is not None else "",
            y=s(y_px_m) if y_px_m is not None else "",
            ancho=s(ancho_px_m) if ancho_px_m is not None else "",
            alto=s(alto_px_m) if alto_px_m is not None else "",
            parent=self)
        if not resultado:
            return
        try:
            x_px_n = int(float(resultado["x"]))
            y_px_n = int(float(resultado["y"]))
            ancho_px_n = int(float(resultado["ancho"]))
            alto_px_n = int(float(resultado["alto"]))
        except (ValueError, TypeError, KeyError):
            mostrar_error(
                self, _("No se marcó ningún rectángulo sobre la imagen "
                        "— no se guardó la ubicación del mueble."))
            return
        try:
            x_pct, y_pct, ancho_pct, alto_pct = Modelo._rect_px_a_pct(
                self.path_imagen, x_px_n, y_px_n, ancho_px_n, alto_px_n)
        except DimensionesImagenError:
            mostrar_error(
                self, _("No se pudo determinar el tamaño de la imagen "
                        "del plano — no se guardó la ubicación del "
                        "mueble."))
            return

        filas = Modelo.devolver_mueble(id_mueble)
        if not filas:
            mostrar_error(self, _("No se encontró el mueble."))
            return
        r = filas[0]
        nombre_m, tipo_m = r[2], r[3]
        Modelo.modificacion_mueble(
            id_mueble, nombre_m, x_pct, y_pct, ancho_pct, alto_pct, tipo_m)
        self._cargar_combo_muebles(id_mueble_foco=id_mueble)
        self._viz.da.queue_draw()

    # ── modo editar: ubicar/mover el punto de un equipo suelto (Fase 7)
    #    — mismo flujo que _ubicar_rack, pero conserva el tipo_montaje ya
    #    cargado (self._equipo_suelto_datos), que este botón no toca. ──
    def _ubicar_equipo_suelto(self, btn):
        id_str = self._combo_equipos_sueltos.get_active_id()
        if not id_str:
            mostrar_error(
                self, _("Este plano todavía no tiene ningún equipo "
                        "suelto asignado — asignalo primero desde "
                        "\"Equipos sueltos por Sala\"."))
            return
        if not self.id_imagen:
            mostrar_error(
                self, _("Este plano todavía no tiene una imagen cargada."))
            return
        id_en = int(id_str)

        x_pct_actual, y_pct_actual, tipo_montaje_actual = \
            self._equipo_suelto_datos.get(id_en, (None, None, "PISO"))
        x_px_actual, y_px_actual = Modelo._px_punto_o_crudo(
            self.path_imagen, x_pct_actual, y_pct_actual)

        resultado = abrir_coords_imagen(
            self.id_imagen, solo_xy=True,
            x=s(x_px_actual) if x_px_actual is not None else "",
            y=s(y_px_actual) if y_px_actual is not None else "",
            parent=self)
        if not resultado:
            return
        try:
            x_px_nuevo = int(float(resultado["x"]))
            y_px_nuevo = int(float(resultado["y"]))
        except (ValueError, TypeError):
            mostrar_error(
                self, _("No se marcó ningún punto sobre la imagen — no "
                        "se guardó la ubicación del equipo."))
            return
        try:
            x_pct, y_pct = Modelo._punto_px_a_pct(
                self.path_imagen, x_px_nuevo, y_px_nuevo)
        except DimensionesImagenError:
            mostrar_error(
                self, _("No se pudo determinar el tamaño de la imagen "
                        "del plano — no se guardó la ubicación del "
                        "equipo."))
            return

        Modelo.actualizar_posicion_equipo_no_rack_sala(
            id_en, x_pct, y_pct, tipo_montaje_actual or "PISO")
        self._cargar_combo_equipos_sueltos(id_en_foco=id_en)
        self._viz.da.queue_draw()

    def run_and_destroy(self):
        self.run()
