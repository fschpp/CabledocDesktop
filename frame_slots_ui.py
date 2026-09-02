#!/usr/bin/env python3
"""
frame_slots_ui.py — CableDoc GTK3

Entrega 1 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md). Move 1:1, sin cambio de lógica:

  VistaFrameSlots            vista gráfica de slots ocupados en un frame
  abrir_vista_frame_slots    función de conveniencia
"""

import math

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modelo import Modelo

from pantallas_comunes import _, s, confirmar, _pixbuf_from_name, _ImagenZoom, PALETA, _abrev


# ═══════════════════════════════════════════════════════════════════════════════
# VistaFrameSlots
# ═══════════════════════════════════════════════════════════════════════════════

class VistaFrameSlots(Gtk.Dialog):
    """
    Vista gráfica de un frame mostrando los equipos instalados en cada slot.
    Dibuja sobre la imagen del frame un rectángulo coloreado por slot,
    con el nombre del equipo instalado dentro.
    Funciona de forma análoga a ImagenConectoresYCables:
      • Clic en imagen  → resalta fila en la tabla
      • Clic en tabla   → resalta y centra el slot en la imagen
      • Doble clic fila → abre diálogo de edición del equipo del slot
    """

    def __init__(self, id_frame, parent=None):
        super().__init__(
            title="Slots del frame",
            transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1280, 720)
        self.id_frame = str(id_frame)

        self._marcadores = []   # lista de dicts por slot
        self._resaltado  = -1
        self._img_path   = None  # path de la imagen del frame o del slot

        area = self.get_content_area()

        # ── Layout HPaned ────────────────────────────────────────────────────
        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_position(780)
        area.pack_start(hpaned, True, True, 0)

        # Panel izquierdo — imagen
        self._viz = _ImagenZoom()
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("button-press-event", self._on_clic_imagen)
        # Conectar ajuste automático de imagen al mostrar el diálogo
        self._viz.da.connect("realize", self._on_viz_realize)
        hpaned.pack1(self._viz, resize=True, shrink=False)

        # Panel derecho — tabla
        vbox_r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                         margin_start=6, margin_end=6,
                         margin_top=6,   margin_bottom=4)

        self._lbl_frame = Gtk.Label(xalign=0)
        self._lbl_frame.set_markup("<i>Cargando…</i>")
        self._lbl_frame.set_line_wrap(True)
        vbox_r.pack_start(self._lbl_frame, False, False, 4)

        sw_t = Gtk.ScrolledWindow(vexpand=True)
        # ListStore: num, color_hex, slot_nom, eq_nom, id_equipo
        self._store = Gtk.ListStore(str, str, str, str, str)
        self._tv    = Gtk.TreeView(model=self._store, headers_visible=True)

        for i, (titulo, idx, expand) in enumerate([
            ("#",       0, False),
            ("Slot",    2, False),
            ("Equipo",  3, True),
        ]):
            rend = Gtk.CellRendererText(background_set=True, xpad=4,
                                        xalign=(0.5 if i == 0 else 0.0),
                                        weight=(700 if i == 0 else 400))
            col  = Gtk.TreeViewColumn(titulo, rend, text=idx, background=1)
            col.set_resizable(True); col.set_expand(expand)
            if i == 0: col.set_min_width(36)
            self._tv.append_column(col)

        self._tv.connect("row-activated", self._on_doble_click)
        self._tv.get_selection().connect("changed", self._on_sel_tabla)
        sw_t.add(self._tv)
        vbox_r.pack_start(sw_t, True, True, 0)

        nota = Gtk.Label(xalign=0)
        nota.set_markup(
            "<small>Clic en imagen → resaltar slot  │  "
            "Doble clic en fila → editar equipo del slot</small>")
        vbox_r.pack_start(nota, False, False, 2)
        hpaned.pack2(vbox_r, resize=True, shrink=False)

        self._cargar()
        self.show_all()

    # ── carga ────────────────────────────────────────────────────────────────
    def _cargar(self):
        rows = Modelo.devolver_slots_graficos_de_frame(self.id_frame)
        # cols: id_slot, slot_nom, id_equipo, eq_nom, x, y, ancho, alto,
        #       img_frame, img_slot
        if not rows:
            self._lbl_frame.set_markup("<b>Frame sin slots registrados</b>")
            return

        # Nombre del frame desde devolver_frame
        fr = Modelo.devolver_frame(self.id_frame)
        frame_nom = s(fr[0][1]) if fr else f"Frame {self.id_frame}"
        self.set_title(f"Slots: {frame_nom}")
        self._lbl_frame.set_markup(f"<b>{frame_nom}</b>")

        # Imagen: priorizar la del frame; si no, la del primer slot con imagen
        img_path = ""
        for r in rows:
            if s(r[8]).strip():
                img_path = s(r[8]).strip(); break
        if not img_path:
            for r in rows:
                if s(r[9]).strip():
                    img_path = s(r[9]).strip(); break

        if img_path:
            pb = _pixbuf_from_name(img_path)
            if pb:
                self._viz.set_pixbuf(pb)
                self._viz.set_zoom(1.0)

        idx_color = 0
        num       = 1
        for r in rows:
            slot_nom = s(r[1])
            id_eq    = s(r[2]) if r[2] else ""
            eq_nom   = s(r[3])
            x        = int(r[4]) if r[4] else 0
            y        = int(r[5]) if r[5] else 0
            ancho    = int(r[6]) if r[6] and int(r[6]) > 0 else 50
            alto     = int(r[7]) if r[7] and int(r[7]) > 0 else 30

            if id_eq:
                color = PALETA[idx_color % len(PALETA)]
                idx_color += 1
            else:
                color = (0.55, 0.55, 0.58)   # gris para slots vacíos

            hex_c = "#{:02X}{:02X}{:02X}".format(
                int(color[0]*255), int(color[1]*255), int(color[2]*255))

            self._marcadores.append({
                "num":      num,
                "slot_nom": slot_nom,
                "eq_nom":   eq_nom or "(vacío)",
                "id_eq":    id_eq,
                "x": x, "y": y, "ancho": ancho, "alto": alto,
                "r": color[0], "g": color[1], "b": color[2],
                "hex": hex_c,
            })
            self._store.append([
                str(num), hex_c, slot_nom, eq_nom or "(vacío)", id_eq,
            ])
            num += 1

    # ── overlay Cairo ─────────────────────────────────────────────────────────
    def _dibujar_overlay(self, cr):
        z = self._viz.zoom

        for i, m in enumerate(self._marcadores):
            wx, wy = self._viz.i2w(m["x"], m["y"])
            ww     = m["ancho"] * z
            wh     = m["alto"]  * z
            r, g, b = m["r"], m["g"], m["b"]
            resalt  = (i == self._resaltado)

            # Relleno semitransparente
            alpha = 0.45 if resalt else 0.22
            cr.set_source_rgba(r, g, b, alpha)
            cr.rectangle(wx, wy, ww, wh); cr.fill()

            # Borde (más grueso si resaltado)
            lw = max(3, (12 if resalt else 7) * z)
            cr.set_source_rgba(r, g, b, 0.95)
            cr.set_line_width(lw)
            cr.rectangle(wx, wy, ww, wh); cr.stroke()

            # Contorno negro fino
            cr.set_source_rgb(0, 0, 0)
            cr.set_line_width(max(1, 1.5 * z))
            cr.rectangle(wx, wy, ww, wh); cr.stroke()

            # ── Texto del equipo dentro del rectángulo ─────────────────────
            cx = wx + ww / 2
            cy = wy + wh / 2
            fs = max(7, min(12 * z, wh * 0.38, ww * 0.15))

            # Sombra
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(fs)
            texto = _abrev(cr, m["eq_nom"], ww - 8 * z)

            for dx, dy, col in [(-1,-1,(1,1,1)), (1,1,(0,0,0))]:
                cr.set_source_rgb(*col)
                cr.move_to(cx - cr.text_extents(texto).width/2
                           - cr.text_extents(texto).x_bearing + dx,
                           cy - cr.text_extents(texto).height/2
                           - cr.text_extents(texto).y_bearing + dy)
                cr.show_text(texto)

            # Texto en color del marcador
            cr.set_source_rgb(r * 0.30, g * 0.30, b * 0.30)
            ext = cr.text_extents(texto)
            cr.move_to(cx - ext.width/2 - ext.x_bearing,
                       cy - ext.height/2 - ext.y_bearing)
            cr.show_text(texto)

            # ── Número del slot (esquina superior izquierda) ───────────────
            ns  = str(m["num"])
            fs2 = max(6, min(10 * z, wh * 0.28))
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(fs2)
            # fondo pastilla
            e2 = cr.text_extents(ns)
            pad = 2 * z
            bx = wx + 3 * z; by = wy + 3 * z
            cr.set_source_rgba(r, g, b, 0.80)
            cr.rectangle(bx - pad, by - pad,
                         e2.width + 2*pad, e2.height + 2*pad)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(bx - e2.x_bearing, by - e2.y_bearing)
            cr.show_text(ns)

    # ── selección tabla → imagen ──────────────────────────────────────────────
    def _on_sel_tabla(self, sel):
        model, it = sel.get_selected()
        if it is None:
            self._resaltado = -1
        else:
            self._resaltado = model.get_path(it).get_indices()[0]
            if self._resaltado < len(self._marcadores):
                m = self._marcadores[self._resaltado]
                # Centrar en el slot
                self._viz.scroll_to_img(
                    m["x"] + m["ancho"] // 2,
                    m["y"] + m["alto"]  // 2)
        self._viz.da.queue_draw()

    # ── clic en imagen → seleccionar slot más cercano ─────────────────────────
    def _on_clic_imagen(self, da, event):
        ix, iy = self._viz.w2i(event.x, event.y)
        mejor_d = float("inf"); mejor_i = -1
        for i, m in enumerate(self._marcadores):
            # Clic dentro del rectángulo del slot
            if (m["x"] <= ix <= m["x"] + m["ancho"] and
                    m["y"] <= iy <= m["y"] + m["alto"]):
                cx = m["x"] + m["ancho"] / 2
                cy = m["y"] + m["alto"]  / 2
                d  = math.hypot(ix - cx, iy - cy)
                if d < mejor_d:
                    mejor_d = d; mejor_i = i
        if mejor_i >= 0:
            self._resaltado = mejor_i
            path = Gtk.TreePath.new_from_indices([mejor_i])
            self._tv.get_selection().select_path(path)
            self._tv.scroll_to_cell(path, None, True, 0.5, 0)
            self._viz.da.queue_draw()

    # ── doble clic → editar equipo del slot ───────────────────────────────────
    def _on_doble_click(self, tv, path, col):
        it    = tv.get_model().get_iter(path)
        id_eq = tv.get_model().get_value(it, 4)
        if id_eq and id_eq.strip():
            from cabledoc import _DialogoEquipo
            dlg = _DialogoEquipo(id_equipo=id_eq, parent=self)
            dlg.run_and_destroy()
            # Recargar por si cambió el nombre del equipo
            self._marcadores.clear()
            self._store.clear()
            self._resaltado = -1
            self._cargar()
            self._viz.da.queue_draw()

    def _on_viz_realize(self, widget):
        """Ajustar imagen automáticamente cuando el widget se realiza."""
        if self._viz.pixbuf:
            self._viz._zoom_fit()



# ── función de conveniencia ────────────────────────────────────────────────────

def abrir_vista_frame_slots(id_frame, parent=None):
    dlg = VistaFrameSlots(id_frame=id_frame, parent=parent)
    dlg.run(); dlg.destroy()
