#!/usr/bin/env python3
"""
planos_ui.py — CableDoc GTK3

Dominio Planos, plan_desarrollo_ubicacion_fisica_planos.md.

Contiene:
  - PlanosListado, _DialogoPlano (Fase 2: catálogo simple de planos)
  - VistaPlanoInteractivo (Fase 4: overlay de salas en el plano;
    Fase 5: + overlay de racks — puntos)

El overlay interactivo (puntos de equipo suelto, muebles) sigue creciendo
en las Fases 6 y 7 del plan — este archivo crece en esas fases, mismo
criterio de separación por dominio que ya usan `racks_salas_ui.py` /
`frames_slots_ui.py`, para no mezclar desde el arranque el catálogo
simple con el editor gráfico.

Fase 5 ("Overlay de racks (puntos)"): a diferencia del contorno de sala
(polígono libre, dibujado a mano vértice por vértice con
CoordenadasImagenSeleccion(modo_poligono=True)), el rack es un punto
simple — se reutiliza el modo solo_xy=True ya existente de
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

Fase 5 ("Overlay de racks") suma, sobre el mismo overlay, un punto por
cada rack de rack_por_sala que ya tiene x_pct/y_pct cargado (dibujado
aunque la sala dueña todavía no tenga contorno propio — ver el ajuste
correspondiente en Modelo.devolver_contenido_plano) + un selector de
rack + botón para ubicarlo/moverlo, reutilizando en solo_xy=True el
mismo CoordenadasImagenSeleccion. Todavía no dibuja muebles ni equipos
sueltos (eso llega en las Fases 6-7): Modelo.devolver_contenido_plano ya
devuelve esa información lista para cuando corresponda, pero se ignora
a propósito acá para no salirse del criterio de cierre de esta fase.
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

    Uso:
        VistaPlanoInteractivo(id_plano, parent=p,
                              id_sala_foco=id_sala).run_and_destroy()
    id_sala_foco (opcional): preselecciona esa sala en el combo al abrir
    — usado por _DialogoSala."Editar contorno en el plano"
    (racks_salas_ui.py) para no obligar a volver a buscarla.
    id_rack_x_sala_foco (opcional, Fase 5): preselecciona ese
    rack_por_sala en el combo "Rack:" al abrir — usado por
    _DialogoRackPorSala."📍 Ubicar en el plano" (racks_salas_ui.py).
    """

    COLOR_SALA = (0.10, 0.45, 0.90)  # azul — contorno sólido + relleno tenue
    COLOR_RACK = (0.85, 0.45, 0.05)  # naranja — punto de rack

    def __init__(self, id_plano, parent=None, id_sala_foco=None,
                 id_rack_x_sala_foco=None):
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

            # ── Fase 5: puntos de rack de esta sala ──
            r2, g2, b2 = self.COLOR_RACK
            for id_rxs, id_rack, nombre_rack, x_pct_r, y_pct_r in sala.get("racks", []):
                try:
                    x_img_r = (float(x_pct_r) / 100.0) * ancho_img
                    y_img_r = (float(y_pct_r) / 100.0) * alto_img
                except (TypeError, ValueError):
                    continue
                wx_r, wy_r = self._viz.i2w(x_img_r, y_img_r)
                radio = max(6, 9 * self._viz.zoom)
                cr.set_source_rgba(r2, g2, b2, 0.92)
                cr.arc(wx_r, wy_r, radio, 0, 2 * math.pi)
                cr.fill_preserve()
                cr.set_source_rgb(0, 0, 0)
                cr.set_line_width(1.5)
                cr.stroke()
                cr.set_source_rgb(0.05, 0.05, 0.05)
                cr.select_font_face("Sans", 0, 0)
                cr.set_font_size(12)
                texto_r = "🗄 " + s(nombre_rack)
                cr.move_to(wx_r + radio + 3, wy_r + 4)
                cr.show_text(texto_r)

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

    def run_and_destroy(self):
        self.run()
