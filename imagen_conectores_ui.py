#!/usr/bin/env python3
"""
imagen_conectores_ui.py — CableDoc GTK3

Entrega 2 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md). Move 1:1, sin cambio de lógica:

  CoordenadasImagenSeleccion   selector de coordenadas/rectángulo sobre imagen
  abrir_coords_imagen          función de conveniencia
  ImagenConectoresYCables      vista de imagen de equipo + tabla de cables/conectores
  abrir_imagen_conectores      función de conveniencia

Columnas de CONEXIONES_AMBOS_EXTREMOS (WHERE id_equipo = X):
  0  Cable                   1  EA: equipo (= el CONECTADO)
  3  EA: conector            5  EB: Equipo (= el CONSULTADO)
  9  id_equipo (= X)        10  id_equipo:1 (= id del CONECTADO)
  +15 x  +16 y  +17 path_archivo   (en _CON_IMAGEN, cols 11-14 son id_cable/id_conexion/id_conector/id_conector:1)
"""

import os
import math

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from modelo import Modelo

from pantallas_comunes import (
    _, s, _pixbuf_from_name, _pixbuf_from_name_con_motivo,
    _ImagenZoom, PALETA,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  CoordenadasImagenSeleccion
# ═══════════════════════════════════════════════════════════════════════════════

class CoordenadasImagenSeleccion(Gtk.Dialog):
    """
    Muestra una imagen y permite seleccionar coordenadas con el ratón:
      solo_xy=True  → clic simple         → punto (x, y)
      solo_xy=False → clic + arrastre     → rectángulo (x, y, ancho, alto)

    Uso:
        dlg = CoordenadasImagenSeleccion(
                  id_imagen="5", solo_xy=True, x="100", y="200", parent=p)
        if dlg.run() == Gtk.ResponseType.OK:
            x, y = dlg.x, dlg.y
        dlg.destroy()
    """

    MARCADOR = 50

    def __init__(self, id_imagen=None, solo_xy=True,
                 x="", y="", ancho="", alto="", parent=None):
        super().__init__(
            title=_("Seleccionar coordenadas en imagen"),
            transient_for=parent,
            modal=True, destroy_with_parent=True,
        )
        self.add_buttons("Cancelar",  Gtk.ResponseType.CANCEL,
                         "✔ Aceptar", Gtk.ResponseType.OK)
        self.set_default_size(1050, 700)

        # resultado público
        self.x     = x;  self.y    = y
        self.ancho = ancho; self.alto = alto
        self.solo_xy = solo_xy

        # estado interno
        self._puntos   = []
        self._rect_ini = None
        self._rect_fin = None
        self._drag     = False

        # ── layout ──────────────────────────────────────────────────────
        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_position(760)
        self.get_content_area().pack_start(hpaned, True, True, 0)

        # visor de imagen
        self._viz = _ImagenZoom()
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("button-press-event",    self._on_press)
        self._viz.da.connect("motion-notify-event",   self._on_motion)
        self._viz.da.connect("button-release-event",  self._on_release)
        # Conectar ajuste automático de imagen al mostrar el diálogo
        self._viz.da.connect("realize", self._on_viz_realize)
        hpaned.pack1(self._viz, resize=True, shrink=False)

        # panel de campos
        vbox_r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         margin_start=10, margin_end=10, margin_top=10)
        grid   = Gtk.Grid(column_spacing=8, row_spacing=6)

        def campo(lbl, fila):
            grid.attach(Gtk.Label(label=lbl, xalign=1), 0, fila, 1, 1)
            e = Gtk.Entry(width_chars=10, hexpand=True)
            grid.attach(e, 1, fila, 1, 1)
            return e

        self._ex = campo("X (píxeles):", 0)
        self._ey = campo("Y (píxeles):", 1)
        fila_btn = 2
        if not solo_xy:
            self._eancho = campo(_("Ancho (px):"), 2)
            self._ealto  = campo(_("Alto  (px):"), 3)
            fila_btn = 4

        btn_ir = Gtk.Button(label=_("⊙ Ir a coordenadas"))
        btn_ir.connect("clicked", self._ir)
        grid.attach(btn_ir, 0, fila_btn, 2, 1)
        vbox_r.pack_start(grid, False, False, 0)
        vbox_r.pack_start(Gtk.Separator(), False, False, 0)

        leyenda = Gtk.Label(xalign=0)
        if solo_xy:
            leyenda.set_markup(
                "<small><b>Modo punto</b>\n"
                "• Clic para colocar marcador\n"
                "• Rueda del ratón: zoom</small>")
        else:
            leyenda.set_markup(
                "<small><b>Modo rectángulo</b>\n"
                "• Clic y arrastrar para seleccionar área\n"
                "• Rueda del ratón: zoom</small>")
        vbox_r.pack_start(leyenda, False, False, 0)
        hpaned.pack2(vbox_r, resize=False, shrink=False)

        # precargar coords
        self._ex.set_text(s(x)); self._ey.set_text(s(y))
        if solo_xy:
            try:
                self._puntos = [(int(float(x)), int(float(y)))]
            except (ValueError, TypeError):
                pass
        else:
            self._eancho.set_text(s(ancho)); self._ealto.set_text(s(alto))
            try:
                x1, y1 = int(float(x)), int(float(y))
                self._rect_ini = (x1, y1)
                self._rect_fin = (x1 + int(float(ancho)), y1 + int(float(alto)))
            except (ValueError, TypeError):
                pass

        # cargar imagen
        if id_imagen:
            path = Modelo.path_imagen(id_imagen)
            if path:
                pb, motivo = _pixbuf_from_name_con_motivo(path)
                if pb:
                    self._viz.set_pixbuf(pb)
                else:
                    self._viz.set_motivo_sin_imagen(motivo)

        self.show_all()

    def _on_viz_realize(self, widget):
        """Ajustar imagen automáticamente cuando el widget se realiza."""
        if self._viz.pixbuf:
            self._viz._zoom_fit()

    # ── overlay Cairo ─────────────────────────────────────────────────────
    def _dibujar_overlay(self, cr):
        z  = self._viz.zoom
        M  = self.MARCADOR * z
        HM = M / 2

        if self.solo_xy:
            for ix, iy in self._puntos:
                wx, wy = self._viz.i2w(ix, iy)
                # relleno verde semitransparente
                cr.set_source_rgba(0, 0.85, 0, 0.18)
                cr.rectangle(wx - HM, wy - HM, M, M); cr.fill()
                # borde grueso verde
                cr.set_source_rgba(0, 0.85, 0, 0.92)
                cr.set_line_width(max(3, 8 * z))
                cr.rectangle(wx - HM, wy - HM, M, M); cr.stroke()
                # contorno negro
                cr.set_source_rgb(0, 0, 0); cr.set_line_width(1)
                cr.rectangle(wx - HM, wy - HM, M, M); cr.stroke()
                # mira
                cr.set_source_rgb(0, 0.85, 0)
                cr.set_line_width(max(1, 2 * z))
                s6 = 6 * z
                cr.move_to(wx - s6, wy); cr.line_to(wx + s6, wy)
                cr.move_to(wx, wy - s6); cr.line_to(wx, wy + s6)
                cr.stroke()
        else:
            if self._rect_ini and self._rect_fin:
                x1, y1 = self._rect_ini; x2, y2 = self._rect_fin
                wx1, wy1 = self._viz.i2w(x1, y1)
                wx2, wy2 = self._viz.i2w(x2, y2)
                rw, rh   = wx2 - wx1, wy2 - wy1
                # relleno
                cr.set_source_rgba(0, 0.80, 0, 0.12)
                cr.rectangle(wx1, wy1, rw, rh); cr.fill()
                # borde grueso verde
                cr.set_source_rgba(0, 0.85, 0, 0.92)
                cr.set_line_width(max(3, 8 * z))
                cr.rectangle(wx1, wy1, rw, rh); cr.stroke()
                # contorno negro
                cr.set_source_rgb(0, 0, 0); cr.set_line_width(1)
                cr.rectangle(wx1, wy1, rw, rh); cr.stroke()
                # cruces en esquinas
                cr.set_source_rgb(0, 0.85, 0)
                cr.set_line_width(max(1, 2 * z))
                s4 = 4 * z
                for px, py in [(wx1, wy1), (wx2, wy2)]:
                    cr.move_to(px - s4, py); cr.line_to(px + s4, py)
                    cr.move_to(px, py - s4); cr.line_to(px, py + s4)
                cr.stroke()

    # ── eventos de ratón ─────────────────────────────────────────────────
    def _on_press(self, da, event):
        ix, iy = self._viz.w2i(event.x, event.y)
        if self.solo_xy:
            self._puntos = [(ix, iy)]
            self._ex.set_text(str(ix)); self._ey.set_text(str(iy))
        else:
            self._drag     = True
            self._rect_ini = self._rect_fin = (ix, iy)
            da.get_window().set_cursor(
                Gdk.Cursor.new_from_name(da.get_display(), "crosshair"))
        da.queue_draw()

    def _on_motion(self, da, event):
        if self._drag and not self.solo_xy:
            ix, iy = self._viz.w2i(event.x, event.y)
            self._rect_fin = (ix, iy)
            da.queue_draw()

    def _on_release(self, da, event):
        if self._drag and not self.solo_xy:
            self._drag = False
            ix, iy     = self._viz.w2i(event.x, event.y)
            x1 = min(self._rect_ini[0], ix); y1 = min(self._rect_ini[1], iy)
            x2 = max(self._rect_ini[0], ix); y2 = max(self._rect_ini[1], iy)
            self._rect_ini = (x1, y1); self._rect_fin = (x2, y2)
            self._ex.set_text(str(x1));       self._ey.set_text(str(y1))
            self._eancho.set_text(str(x2-x1)); self._ealto.set_text(str(y2-y1))
            da.get_window().set_cursor(None)
            da.queue_draw()

    def _ir(self, btn):
        try:
            ix = int(self._ex.get_text()); iy = int(self._ey.get_text())
            if self.solo_xy:
                self._puntos = [(ix, iy)]
            else:
                try:
                    aw = int(self._eancho.get_text())
                    ah = int(self._ealto.get_text())
                except ValueError:
                    aw, ah = 50, 50
                self._rect_ini = (ix, iy); self._rect_fin = (ix+aw, iy+ah)
            self._viz.da.queue_draw()
            self._viz.scroll_to_img(ix, iy)
        except ValueError:
            pass

    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.OK:
            self.x = self._ex.get_text().strip()
            self.y = self._ey.get_text().strip()
            if not self.solo_xy:
                self.ancho = self._eancho.get_text().strip()
                self.alto  = self._ealto.get_text().strip()


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  ImagenConectoresYCables
# ═══════════════════════════════════════════════════════════════════════════════

class ImagenConectoresYCables(Gtk.Dialog):
    """
    Vista fotográfica del equipo con rectángulos numerados/coloreados sobre
    cada conector y tabla de referencia al costado.
    Clic en imagen ↔ resalta fila. Doble-clic en fila → equipo destino.
    """

    MARCADOR = 50

    def __init__(self, id_equipo, parent=None):
        super().__init__(
            title=_("Imagen de conectores y cables"),
            transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1280, 720)
        self.id_equipo   = str(id_equipo)
        self._marcadores = []
        self._resaltado  = -1

        # ── layout ──────────────────────────────────────────────────────
        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_position(760)
        self.get_content_area().pack_start(hpaned, True, True, 0)

        # visor
        self._viz = _ImagenZoom()
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("button-press-event", self._on_clic_imagen)
        hpaned.pack1(self._viz, resize=True, shrink=False)

        # tabla
        vbox_r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                         margin_start=6, margin_end=6,
                         margin_top=6,   margin_bottom=4)

        self._lbl_equipo = Gtk.Label(xalign=0)
        self._lbl_equipo.set_markup("<i>Cargando…</i>")
        self._lbl_equipo.set_line_wrap(True)
        vbox_r.pack_start(self._lbl_equipo, False, False, 4)

        sw_t = Gtk.ScrolledWindow(vexpand=True)
        # ListStore: num, color_hex, con_local, cable, id_eq_b, eq_b, tipo_b, con_b
        self._store = Gtk.ListStore(str, str, str, str, str, str, str, str)
        self._tv    = Gtk.TreeView(model=self._store, headers_visible=True)

        for i, (titulo, idx, expand) in enumerate([
            ("#",              0, False),
            (_("Conector local"), 2, True),
            (_("Cable"),          3, False),
            (_("Equipo destino"), 5, True),
            (_("Tipo"),           6, False),
            (_("Conector dest."), 7, True),
        ]):
            rend = Gtk.CellRendererText(background_set=True, xpad=4,
                                        xalign=(0.5 if i == 0 else 0.0),
                                        weight=(700 if i == 0 else 400))
            col  = Gtk.TreeViewColumn(titulo, rend, text=idx, background=1)
            col.set_resizable(True); col.set_expand(expand)
            if i == 0:
                col.set_min_width(36)
            self._tv.append_column(col)

        self._tv.connect("row-activated", self._on_doble_click)
        self._tv.get_selection().connect("changed", self._on_sel_tabla)
        sw_t.add(self._tv)
        vbox_r.pack_start(sw_t, True, True, 0)

        nota = Gtk.Label(xalign=0)
        nota.set_markup(
            "<small>Doble clic en fila → equipo destino  │  "
            "" + _("Clic en imagen → resaltar fila") + "</small>")
        vbox_r.pack_start(nota, False, False, 2)
        hpaned.pack2(vbox_r, resize=True, shrink=False)

        self._cargar()
        self.show_all()

    # ── carga ─────────────────────────────────────────────────────────────
    def _cargar(self):
        # Nombre del equipo
        eq_rows = Modelo._query(
            "SELECT ve.nombre FROM VISTA_EQUIPOS ve WHERE ve.id=?",
            (self.id_equipo,))
        nombre_local = s(eq_rows[0][0]) if eq_rows else f"Equipo {self.id_equipo}"
        self._lbl_equipo.set_markup(f"<b>{nombre_local}</b>")
        self.set_title(f"Imagen de conectores: {nombre_local}")

        # Leer todos los conectores del equipo directamente
        cons = Modelo._query(
            "SELECT c.id_conector, c.nombre, "
            "       c.coordenada_x_en_imagen, c.coordenada_y_en_imagen, "
            "       i.path_archivo "
            "FROM conector c "
            "LEFT JOIN imagen i ON i.id_imagen = c.id_imagen "
            "WHERE c.id_equipo = ? ORDER BY c.nombre",
            (self.id_equipo,))
        cons = [
            (r[0], r[1], *Modelo._px_punto_o_crudo(r[4] or None, r[2], r[3]), r[4])
            for r in cons
        ]

        if not cons:
            self._lbl_equipo.set_markup(
                f"<b>{nombre_local}</b> — <i>sin conectores</i>")
            return

        # Pre-cargar conexiones existentes agrupadas por id_conector
        # { id_conector: [(cable, eq_b, tipo_b, con_b, id_eq_b), ...] }
        cx_rows = Modelo._query(
            "SELECT cn.id_conector, c.codigo, "
            "       eb.nombre, COALESCE(teb.nombre,''), cb2.nombre, eb.id_equipo "
            "FROM conexion cn "
            "JOIN cable c ON c.id_cable = cn.id_cable "
            "JOIN conexion cn2 ON cn2.id_cable = cn.id_cable "
            "              AND cn2.id_conector != cn.id_conector "
            "JOIN conector cb2 ON cb2.id_conector = cn2.id_conector "
            "JOIN equipo eb ON eb.id_equipo = cb2.id_equipo "
            "LEFT JOIN tipo_equipo teb ON teb.id_tipo_equipo = eb.id_tipo_equipo "
            "WHERE cn.id_conector IN ("
            "  SELECT id_conector FROM conector WHERE id_equipo=?"
            ")",
            (self.id_equipo,))
        cx_map = {}
        for row in cx_rows:
            cx_map.setdefault(str(row[0]), []).append(row[1:])

        path_img  = None
        idx_color = 0
        num       = 1

        for r in cons:
            id_con    = str(r[0])
            con_local = s(r[1])
            x_str     = s(r[2]).strip() if r[2] is not None else ""
            y_str     = s(r[3]).strip() if r[3] is not None else ""
            path      = s(r[4]).strip() if r[4] else ""

            if path and path_img is None:
                path_img = path

            color = PALETA[idx_color % len(PALETA)]
            hex_c = "#{:02X}{:02X}{:02X}".format(
                int(color[0]*255), int(color[1]*255), int(color[2]*255))

            # Si tiene coordenadas → añadir marcador
            if x_str and y_str:
                try:
                    ix = int(float(x_str)); iy = int(float(y_str))
                except ValueError:
                    ix = iy = None
                if ix is not None:
                    cxs = cx_map.get(id_con, [])
                    cable_str = s(cxs[0][0]) if cxs else ""
                    eq_b      = s(cxs[0][1]) if cxs else ""
                    tipo_b    = s(cxs[0][2]) if cxs else ""
                    con_b     = s(cxs[0][3]) if cxs else ""
                    id_eq_b   = str(cxs[0][4]) if cxs else ""
                    self._marcadores.append({
                        "x": ix, "y": iy,
                        "r": color[0], "g": color[1], "b": color[2],
                        "hex": hex_c, "num": num,
                        "cable": cable_str, "con_local": con_local,
                        "eq_b": eq_b, "tipo_b": tipo_b,
                        "con_b": con_b, "id_eq_b": id_eq_b,
                    })
                    self._store.append([
                        str(num), hex_c, con_local, cable_str,
                        id_eq_b, eq_b, tipo_b, con_b,
                    ])
                    idx_color += 1; num += 1
            else:
                # Sin posición: mostrar igual en la tabla sin marcador
                cxs = cx_map.get(id_con, [])
                cable_str = s(cxs[0][0]) if cxs else ""
                eq_b      = s(cxs[0][1]) if cxs else ""
                tipo_b    = s(cxs[0][2]) if cxs else ""
                con_b     = s(cxs[0][3]) if cxs else ""
                id_eq_b   = str(cxs[0][4]) if cxs else ""
                self._store.append([
                    "—", "#e8e8e8", con_local, cable_str,
                    id_eq_b, eq_b, tipo_b, con_b,
                ])
                num += 1

        if path_img:
            pb, motivo = _pixbuf_from_name_con_motivo(path_img)
            if pb:
                self._viz.set_pixbuf(pb)
                GLib.idle_add(self._viz._zoom_fit)
            else:
                self._viz.set_motivo_sin_imagen(motivo)

    # ── overlay ───────────────────────────────────────────────────────────
    def _dibujar_overlay(self, cr):
        z  = self._viz.zoom
        M  = self.MARCADOR * z
        HM = M / 2
        FS = max(10, 15 * z)

        for i, m in enumerate(self._marcadores):
            wx, wy  = self._viz.i2w(m["x"], m["y"])
            r, g, b = m["r"], m["g"], m["b"]
            resalt  = (i == self._resaltado)
            lw      = max(5, (14 if resalt else 9) * z)

            # relleno semitransparente
            cr.set_source_rgba(r, g, b, 0.40 if resalt else 0.15)
            cr.rectangle(wx-HM, wy-HM, M, M); cr.fill()
            # borde de color
            cr.set_source_rgba(r, g, b, 0.95)
            cr.set_line_width(lw)
            cr.rectangle(wx-HM, wy-HM, M, M); cr.stroke()
            # borde blanco
            cr.set_source_rgba(1, 1, 1, 0.90)
            cr.set_line_width(max(1.5, 2 * z))
            cr.rectangle(wx-HM, wy-HM, M, M); cr.stroke()
            # borde negro
            cr.set_source_rgb(0, 0, 0); cr.set_line_width(1)
            cr.rectangle(wx-HM, wy-HM, M, M); cr.stroke()

            # número (triple capa)
            ns = str(m["num"])
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(FS)
            ext = cr.text_extents(ns)
            tx = wx - ext.width/2 - ext.x_bearing
            ty = wy - ext.height/2 - ext.y_bearing
            for dx, dy, col in [(-1,-1,(1,1,1)), (1,1,(0,0,0)), (0,0,(r,g,b))]:
                cr.set_source_rgb(*col)
                cr.move_to(tx+dx, ty+dy); cr.show_text(ns)

    # ── selección tabla → imagen ──────────────────────────────────────────
    def _on_sel_tabla(self, sel):
        model, it = sel.get_selected()
        if it is None:
            self._resaltado = -1
        else:
            self._resaltado = model.get_path(it).get_indices()[0]
            if self._resaltado < len(self._marcadores):
                m = self._marcadores[self._resaltado]
                self._viz.scroll_to_img(m["x"], m["y"])
        self._viz.da.queue_draw()

    # ── clic en imagen → seleccionar fila ────────────────────────────────
    def _on_clic_imagen(self, da, event):
        ix, iy  = self._viz.w2i(event.x, event.y)
        HM      = self.MARCADOR // 2
        mejor_d = float("inf"); mejor_i = -1
        for i, m in enumerate(self._marcadores):
            if abs(ix-m["x"]) <= HM and abs(iy-m["y"]) <= HM:
                d = math.hypot(ix-m["x"], iy-m["y"])
                if d < mejor_d:
                    mejor_d = d; mejor_i = i
        if mejor_i >= 0:
            self._resaltado = mejor_i
            path = Gtk.TreePath.new_from_indices([mejor_i])
            self._tv.get_selection().select_path(path)
            self._tv.scroll_to_cell(path, None, True, 0.5, 0)
            self._viz.da.queue_draw()

    # ── doble-clic en tabla → equipo destino ─────────────────────────────
    def _on_doble_click(self, tv, path, col):
        it      = tv.get_model().get_iter(path)
        id_eq_b = tv.get_model().get_value(it, 4)
        if id_eq_b and id_eq_b.strip() not in ("", "0"):
            dlg = ImagenConectoresYCables(id_equipo=id_eq_b, parent=self)
            dlg.run(); dlg.destroy()


# ── funciones de conveniencia de las secciones 1 y 2 ────────────────────────────
# (quedaron físicamente ubicadas acá en el archivo original, después de
# ArbolConexionesEquipo, pero pertenecen a CoordenadasImagenSeleccion e
# ImagenConectoresYCables — ambas siguen definidas en este archivo)

def abrir_coords_imagen(id_imagen, solo_xy=True, x="", y="",
                        ancho="", alto="", parent=None):
    """Abre el selector y devuelve dict con x/y[/ancho/alto], o None si canceló."""
    dlg = CoordenadasImagenSeleccion(
        id_imagen=id_imagen, solo_xy=solo_xy,
        x=x, y=y, ancho=ancho, alto=alto, parent=parent)
    resp = dlg.run()
    resultado = None
    if resp == Gtk.ResponseType.OK:
        resultado = {"x": dlg.x, "y": dlg.y,
                     "ancho": dlg.ancho, "alto": dlg.alto}
    dlg.destroy()
    return resultado


def abrir_imagen_conectores(id_equipo, parent=None):
    dlg = ImagenConectoresYCables(id_equipo=id_equipo, parent=parent)
    dlg.run(); dlg.destroy()
