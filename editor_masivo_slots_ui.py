#!/usr/bin/env python3
"""
editor_masivo_slots_ui.py — CableDoc GTK3
============================================
Editor de posicionado masivo de rectángulos de slots sobre la imagen de
un frame (o de un molde de frame_catalogo).

Contiene:
  - EditorMasivoSlotsBase   — lógica común (UI, overlay, arrastre, guardado)
                               extraída de las dos variantes que existían
                               en pantallas_avanzadas.py.
  - EditorMasivoSlotsFrame     — para frame/slot reales.
  - EditorMasivoSlotsCatalogo  — para frame_catalogo/slot_catalogo (moldes).
  - abrir_editor_masivo_slots(id_frame, parent, fn_sel_imagen)
  - abrir_editor_masivo_slots_catalogo(id_frame_catalogo, parent, fn_sel_imagen)

Extraído 1:1 de pantallas_avanzadas.py (Entrega 4) y unificado en una
clase base para eliminar la duplicación entre ambas variantes.

Nota de unificación: la variante de catálogo nunca tuvo columna "Equipo"
(los slots de un molde nunca tienen equipo asignado). La base preserva
ese comportamiento vía el flag de clase `_MOSTRAR_EQUIPO`.
"""

import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib

from modelo import Modelo, IMG_DIR
from pantallas_comunes import _, s, PALETA, _pixbuf_from_name, _ImagenZoom


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoSlotsBase — lógica común
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoSlotsBase(Gtk.Dialog):
    """
    Editor para definir visualmente los rectángulos de los slots de un frame
    (o de un molde de frame_catalogo) sobre su imagen en una sola sesión.

    Panel izquierdo : imagen con zoom + overlay de rectángulos.
    Panel derecho   : lista de slots. Seleccionar uno y arrastrar en la imagen
                      dibuja/mueve su rectángulo.

    El tamaño del último rectángulo dibujado se recuerda para los siguientes
    (basta hacer clic, sin arrastrar, para reutilizarlo).

    Slots nuevos se pueden crear directamente desde el panel derecho.

    Subclases deben implementar:
      _cargar_padre()  → (nombre_padre, id_imagen, img_path)
      _cargar_slots()  → lista de (id_slot, nombre, nombre_equipo, id_equipo,
                                    x, y, w, h)
      _actualizar_imagen_padre(id_img) → persiste el id_imagen elegido
      _guardar_nuevo(nombre, id_equipo, x, y, w, h)
      _guardar_existente(sid, nombre, id_equipo, x, y, w, h)
    Y pueden sobrescribir:
      _msg_guardado(n)
      _ETIQUETA_PADRE = "Frame" | "Molde"
      _TITULO_VENTANA_FMT = "Slots de frame: {}" | "Slots del molde: {}"
      _MOSTRAR_EQUIPO = True | False
    """

    _ETIQUETA_PADRE = "Frame"
    _TITULO_VENTANA_FMT = "Slots de frame: {}"
    _MOSTRAR_EQUIPO = True

    def __init__(self, id_padre, parent=None, fn_sel_imagen=None,
                 titulo_inicial="Edición masiva de slots"):
        self._fn_sel_imagen = fn_sel_imagen
        super().__init__(
            title=titulo_inicial,
            transient_for=parent,
            modal=True, destroy_with_parent=True,
        )
        self.set_default_size(1300, 780)
        self._id_padre  = str(id_padre)
        self._id_imagen = ""          # id_imagen del frame/slot
        self._img_path  = ""

        # Estado de slots: id_slot (str, "NEW_n" si es nuevo) → dict
        self._slots    = {}
        self._slot_ids = []           # lista ordenada de ids
        self._sel_id   = None

        # Tamaño recordado del último rect dibujado
        self._last_w   = 80
        self._last_h   = 40

        # Arrastre en curso
        self._drag_start = None       # (ix, iy) en coords imagen
        self._drag_cur   = None
        self._new_count  = 0          # contador de slots nuevos

        # Índices de columnas del store, según haya o no columna "Equipo"
        if self._MOSTRAR_EQUIPO:
            # id, nombre, equipo, color, x, y, w, h, ✓
            self._COL_COLOR, self._COL_X, self._COL_Y = 3, 4, 5
            self._COL_W, self._COL_H, self._COL_TIENE = 6, 7, 8
        else:
            # id, nombre, color, x, y, w, h, ✓
            self._COL_COLOR, self._COL_X, self._COL_Y = 2, 3, 4
            self._COL_W, self._COL_H, self._COL_TIENE = 5, 6, 7

        self._build_ui()
        self._cargar()

    # ── Hooks a implementar/sobrescribir en subclases ──────────────────────

    def _cargar_padre(self):
        raise NotImplementedError

    def _cargar_slots(self):
        raise NotImplementedError

    def _actualizar_imagen_padre(self, id_img):
        raise NotImplementedError

    def _guardar_nuevo(self, nombre, id_equipo, x, y, w, h):
        raise NotImplementedError

    def _guardar_existente(self, sid, nombre, id_equipo, x, y, w, h):
        raise NotImplementedError

    def _msg_guardado(self, n):
        return f"Se guardaron {n} slot(s)."

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ca = self.get_content_area()

        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_position(840)
        ca.pack_start(hpaned, True, True, 0)

        # ── Izquierda: imagen ──
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        top = Gtk.Box(spacing=6, margin_start=6, margin_end=6,
                      margin_top=4, margin_bottom=2)
        top.pack_start(Gtk.Label(label=_("Imagen:")), False, False, 0)
        self._e_img = Gtk.Entry(editable=False, hexpand=True)
        btn_img = Gtk.Button(label="…")
        btn_img.connect("clicked", self._sel_imagen)
        top.pack_start(self._e_img, True, True, 0)
        top.pack_start(btn_img, False, False, 0)

        lbl_hint = Gtk.Label(xalign=0, margin_start=6, margin_bottom=2)
        lbl_hint.set_markup(
            "<small>Clic: colocar slot con tamaño recordado  |  "
            "Arrastrar: dibujar tamaño libre  |  "
            "Clic derecho: quitar rectángulo</small>")

        left.pack_start(top, False, False, 0)
        left.pack_start(lbl_hint, False, False, 0)

        self._viz = _ImagenZoom(
            eventos_extra=(Gdk.EventMask.BUTTON_PRESS_MASK |
                           Gdk.EventMask.BUTTON_RELEASE_MASK |
                           Gdk.EventMask.POINTER_MOTION_MASK))
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("button-press-event",   self._on_press)
        self._viz.da.connect("button-release-event", self._on_release)
        self._viz.da.connect("motion-notify-event",  self._on_motion)
        left.pack_start(self._viz, True, True, 0)

        # Tamaño recordado
        self._lbl_size = Gtk.Label(xalign=0, margin_start=6, margin_bottom=4)
        self._actualizar_lbl_size()
        left.pack_start(self._lbl_size, False, False, 0)

        hpaned.pack1(left, resize=True, shrink=False)

        # ── Derecha: slots ──
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                        margin_start=6, margin_end=8,
                        margin_top=6, margin_bottom=4)

        self._lbl_frame = Gtk.Label(xalign=0)
        right.pack_start(self._lbl_frame, False, False, 0)

        right.pack_start(Gtk.Separator(), False, False, 2)

        # TreeView slots
        if self._MOSTRAR_EQUIPO:
            # cols: id_slot, nombre, equipo, color_bg, x, y, w, h, ✓
            self._store = Gtk.ListStore(str, str, str, str, str, str, str, str, str)
            col_specs = [
                (_("Slot"),   1, True),
                (_("Equipo"), 2, True),
                (_("X"), self._COL_X, True),
                (_("Y"), self._COL_Y, True),
                (_("W"), self._COL_W, True),
                (_("H"), self._COL_H, True),
                ("",     self._COL_TIENE, True),
            ]
        else:
            # cols: id_slot_catalogo, nombre, color_bg, x, y, w, h, ✓
            self._store = Gtk.ListStore(str, str, str, str, str, str, str, str)
            col_specs = [
                (_("Slot"), 1, True),
                (_("X"), self._COL_X, True),
                (_("Y"), self._COL_Y, True),
                (_("W"), self._COL_W, True),
                (_("H"), self._COL_H, True),
                ("",     self._COL_TIENE, True),
            ]

        self._tv = Gtk.TreeView(model=self._store, headers_visible=True)
        self._tv.set_activate_on_single_click(True)

        for titulo, idx, exp in col_specs:
            rend = Gtk.CellRendererText(xpad=3)
            rend.set_property("ellipsize", 3)
            col  = Gtk.TreeViewColumn(titulo, rend, text=idx,
                                      background=self._COL_COLOR)
            col.set_expand(exp)
            col.set_resizable(True)
            self._tv.append_column(col)

        self._tv.get_selection().connect("changed", self._on_sel)
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._tv)
        right.pack_start(sw, True, True, 0)

        # Botones panel derecho
        bb = Gtk.Box(spacing=4, margin_top=4)
        btn_nuevo  = Gtk.Button(label="＋ Nuevo slot")
        btn_quitar = Gtk.Button(label="✕ Quitar rect.")
        btn_nuevo.connect ("clicked", self._nuevo_slot)
        btn_quitar.connect("clicked", lambda b: self._quitar_rect())
        bb.pack_start(btn_nuevo,  True, True, 0)
        bb.pack_start(btn_quitar, True, True, 0)
        right.pack_start(bb, False, False, 0)

        hpaned.pack2(right, resize=False, shrink=False)

        # Botones diálogo
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button("💾 Guardar cambios", Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.connect("response", self._on_response)

        self.show_all()

    def _actualizar_lbl_size(self):
        self._lbl_size.set_markup(
            f"<small>Tamaño recordado: <b>{self._last_w} × {self._last_h} px</b></small>")

    # ── Carga ────────────────────────────────────────────────────────────────

    def _cargar(self):
        nombre_padre, id_imagen, img_path = self._cargar_padre()
        self._id_imagen = id_imagen or ""
        self._img_path  = img_path or ""

        self._lbl_frame.set_markup(f"<b>{self._ETIQUETA_PADRE}: {nombre_padre}</b>")
        self.set_title(self._TITULO_VENTANA_FMT.format(nombre_padre))

        if self._img_path:
            self._e_img.set_text(self._img_path)
            pb = _pixbuf_from_name(self._img_path)
            if pb:
                self._viz.set_pixbuf(pb)
                GLib.idle_add(self._viz._zoom_fit)

        for i, sl in enumerate(self._cargar_slots()):
            id_slot, nombre, nombre_equipo, id_equipo, x, y, w, h = sl
            self._agregar_slot_interno(
                id_slot=str(id_slot), nombre=s(nombre), equipo=s(nombre_equipo),
                x=x, y=y, w=w, h=h,
                id_equipo=str(id_equipo) if id_equipo else "",
                es_nuevo=False, idx=i,
            )

    def _agregar_slot_interno(self, id_slot, nombre, equipo="",
                              x=None, y=None, w=None, h=None,
                              id_equipo="", es_nuevo=False, idx=None):
        if idx is None:
            idx = len(self._slot_ids)
        color = PALETA[idx % len(PALETA)]
        hex_c = "#{:02X}{:02X}{:02X}".format(
            int(color[0]*255), int(color[1]*255), int(color[2]*255))

        tiene = "✓" if (x is not None and y is not None
                        and w is not None and h is not None) else ""
        bg    = hex_c if tiene else "#ffffff"

        self._slots[id_slot] = {
            "nombre": nombre, "equipo": equipo, "id_equipo": id_equipo,
            "x": x, "y": y, "w": w, "h": h,
            "color": color, "hex": hex_c,
            "es_nuevo": es_nuevo, "modificado": False,
        }
        self._slot_ids.append(id_slot)

        if self._MOSTRAR_EQUIPO:
            self._store.append([
                id_slot, nombre, equipo, bg,
                s(x) if x is not None else "",
                s(y) if y is not None else "",
                s(w) if w is not None else "",
                s(h) if h is not None else "",
                tiene,
            ])
        else:
            self._store.append([
                id_slot, nombre, bg,
                s(x) if x is not None else "",
                s(y) if y is not None else "",
                s(w) if w is not None else "",
                s(h) if h is not None else "",
                tiene,
            ])

        if tiene and w and h:
            self._last_w = int(w)
            self._last_h = int(h)
            self._actualizar_lbl_size()

    # ── Nuevo slot ────────────────────────────────────────────────────────────

    def _nuevo_slot(self, btn):
        dlg = Gtk.Dialog(title="Nuevo slot", transient_for=self,
                         modal=True, destroy_with_parent=True)
        dlg.set_default_size(320, -1)
        ca = dlg.get_content_area()
        ca.set_margin_start(12); ca.set_margin_end(12)
        ca.set_margin_top(8);    ca.set_margin_bottom(8)
        ca.pack_start(Gtk.Label(label="Nombre del slot:", xalign=0),
                      False, False, 2)
        entry = Gtk.Entry(activates_default=True)
        ca.pack_start(entry, False, False, 4)
        dlg.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        dlg.add_button("Agregar",  Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.show_all()

        if dlg.run() == Gtk.ResponseType.OK:
            nombre = entry.get_text().strip()
            if nombre:
                self._new_count += 1
                fake_id = f"NEW_{self._new_count}"
                idx = len(self._slot_ids)
                self._agregar_slot_interno(
                    id_slot=fake_id, nombre=nombre, es_nuevo=True, idx=idx)
                # Seleccionar la nueva fila
                self._sel_fila(idx)
        dlg.destroy()

    def _sel_fila(self, idx):
        path = Gtk.TreePath.new_from_indices([idx])
        self._tv.get_selection().select_path(path)
        self._tv.scroll_to_cell(path, None, True, 0.5, 0)

    # ── Selección ────────────────────────────────────────────────────────────

    def _on_sel(self, sel):
        model, it = sel.get_selected()
        self._sel_id = model.get_value(it, 0) if it else None
        self._viz.da.queue_draw()

    def _quitar_rect(self):
        if not self._sel_id or self._sel_id not in self._slots:
            return
        p = self._slots[self._sel_id]
        p["x"] = p["y"] = p["w"] = p["h"] = None
        p["modificado"] = True
        self._actualizar_fila(self._sel_id)
        self._viz.da.queue_draw()

    def _actualizar_fila(self, id_slot):
        idx = self._slot_ids.index(id_slot)
        p   = self._slots[id_slot]
        tiene = "✓" if p["x"] is not None else ""
        bg    = p["hex"] if tiene else "#ffffff"
        it = self._store.get_iter(Gtk.TreePath.new_from_indices([idx]))
        self._store.set(
            it,
            self._COL_COLOR, bg,
            self._COL_X, s(p["x"]) if p["x"] is not None else "",
            self._COL_Y, s(p["y"]) if p["y"] is not None else "",
            self._COL_W, s(p["w"]) if p["w"] is not None else "",
            self._COL_H, s(p["h"]) if p["h"] is not None else "",
            self._COL_TIENE, tiene,
        )

    # ── Imagen: selector ─────────────────────────────────────────────────────

    def _sel_imagen(self, btn):
        # Si hay un selector externo (ImagenesListado), usarlo
        if self._fn_sel_imagen:
            result = self._fn_sel_imagen(self)
            if result:
                id_img, nombre = result
                self._id_imagen = str(id_img)
                self._img_path  = nombre
                self._e_img.set_text(nombre)
                pb = _pixbuf_from_name(nombre)
                if pb:
                    self._viz.set_pixbuf(pb)
                    GLib.idle_add(self._viz._zoom_fit)
                if self._id_imagen:
                    self._actualizar_imagen_padre(self._id_imagen)
            return

        # Fallback: file chooser local
        dlg = Gtk.FileChooserDialog(
            title="Seleccionar imagen", transient_for=self,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OPEN,   Gtk.ResponseType.OK)
        ff = Gtk.FileFilter(); ff.set_name("Imágenes")
        for p in ["*.jpg","*.jpeg","*.png","*.bmp","*.gif"]:
            ff.add_pattern(p)
        dlg.add_filter(ff)

        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            os.makedirs(IMG_DIR, exist_ok=True)
            nombre = os.path.basename(ruta)
            destino = os.path.join(IMG_DIR, nombre)
            if not os.path.exists(destino):
                import shutil; shutil.copy2(ruta, destino)

            rows = Modelo._query(
                "SELECT id_imagen FROM imagen WHERE path_archivo=?", (nombre,))
            if rows:
                self._id_imagen = str(rows[0][0])
            else:
                Modelo._exec(
                    "INSERT INTO imagen (path_archivo, descripcion) VALUES (?,?)",
                    (nombre, nombre))
                rows2 = Modelo._query(
                    "SELECT id_imagen FROM imagen WHERE path_archivo=?", (nombre,))
                self._id_imagen = str(rows2[0][0]) if rows2 else ""

            self._img_path = nombre
            self._e_img.set_text(nombre)
            pb = _pixbuf_from_name(nombre)
            if pb:
                self._viz.set_pixbuf(pb)
                GLib.idle_add(self._viz._zoom_fit)

            # Actualizar id_imagen del padre (frame o frame_catalogo)
            if self._id_imagen:
                self._actualizar_imagen_padre(self._id_imagen)
        dlg.destroy()

    # ── Eventos de dibujo ────────────────────────────────────────────────────

    def _on_press(self, da, ev):
        if self._viz.pixbuf is None or not self._sel_id:
            return
        if ev.button == 3:
            self._quitar_rect(); return
        if ev.button == 1:
            ix, iy = self._viz.w2i(ev.x, ev.y)
            self._drag_start = (ix, iy)
            self._drag_cur   = (ix, iy)

    def _on_motion(self, da, ev):
        if self._drag_start and self._sel_id:
            ix, iy = self._viz.w2i(ev.x, ev.y)
            self._drag_cur = (ix, iy)
            da.queue_draw()

    def _on_release(self, da, ev):
        if ev.button != 1 or not self._drag_start or not self._sel_id:
            self._drag_start = self._drag_cur = None
            return

        ix, iy = self._viz.w2i(ev.x, ev.y)
        x0, y0 = self._drag_start
        dx = abs(ix - x0); dy = abs(iy - y0)

        if dx < 4 and dy < 4:
            # Clic simple → usar tamaño recordado centrado en el punto
            rx = int(x0 - self._last_w / 2)
            ry = int(y0 - self._last_h / 2)
            rw, rh = self._last_w, self._last_h
        else:
            # Arrastre libre
            rx = int(min(x0, ix)); ry = int(min(y0, iy))
            rw = int(abs(ix - x0)); rh = int(abs(iy - y0))
            self._last_w = rw; self._last_h = rh
            self._actualizar_lbl_size()

        p = self._slots[self._sel_id]
        p["x"] = rx; p["y"] = ry
        p["w"] = rw; p["h"] = rh
        p["modificado"] = True
        self._actualizar_fila(self._sel_id)

        self._drag_start = self._drag_cur = None
        da.queue_draw()

        # Avanzar al siguiente sin rect
        self._avanzar_seleccion()

    def _avanzar_seleccion(self):
        if not self._sel_id:
            return
        idx_actual = self._slot_ids.index(self._sel_id)
        n = len(self._slot_ids)
        for offset in range(1, n + 1):
            nid = self._slot_ids[(idx_actual + offset) % n]
            if self._slots[nid]["x"] is None:
                self._sel_fila(self._slot_ids.index(nid))
                return

    # ── Overlay ──────────────────────────────────────────────────────────────

    def _dibujar_overlay(self, cr):
        for sid in self._slot_ids:
            p = self._slots[sid]
            if p["x"] is None:
                continue
            wx1, wy1 = self._viz.i2w(p["x"], p["y"])
            wx2, wy2 = self._viz.i2w(p["x"] + p["w"], p["y"] + p["h"])
            r, g, b  = p["color"]
            es_sel   = (sid == self._sel_id)
            alpha    = 0.35 if es_sel else 0.18

            # Relleno semitransparente
            cr.set_source_rgba(r, g, b, alpha)
            cr.rectangle(wx1, wy1, wx2 - wx1, wy2 - wy1)
            cr.fill()

            # Borde
            cr.set_source_rgba(r, g, b, 0.9)
            cr.set_line_width(2.5 if es_sel else 1.5)
            cr.rectangle(wx1, wy1, wx2 - wx1, wy2 - wy1)
            cr.stroke()

            # Etiqueta centrada
            cx = (wx1 + wx2) / 2; cy = (wy1 + wy2) / 2
            lbl = p["nombre"][:14]
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(10)
            xb, _, tw, th = cr.text_extents(lbl)[:4]
            cr.set_source_rgba(0, 0, 0, 0.65)
            cr.rectangle(cx - tw/2 - 3, cy - th - 1, tw + 6, th + 4)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(cx - tw/2 - xb, cy + 1)
            cr.show_text(lbl)

        # Rectángulo en construcción (mientras se arrastra)
        if self._drag_start and self._drag_cur and self._sel_id:
            x0, y0 = self._drag_start
            x1, y1 = self._drag_cur
            wx0, wy0 = self._viz.i2w(min(x0, x1), min(y0, y1))
            wx1, wy1 = self._viz.i2w(max(x0, x1), max(y0, y1))
            cr.set_source_rgba(1, 1, 0, 0.4)
            cr.rectangle(wx0, wy0, wx1 - wx0, wy1 - wy0)
            cr.fill()
            cr.set_source_rgba(1, 0.8, 0, 0.9)
            cr.set_line_width(2)
            cr.rectangle(wx0, wy0, wx1 - wx0, wy1 - wy0)
            cr.stroke()
            # Mostrar dimensiones
            dw = int(abs(x1 - x0)); dh = int(abs(y1 - y0))
            cr.set_font_size(10)
            lbl2 = f"{dw}×{dh}"
            xb2, _, tw2, th2 = cr.text_extents(lbl2)[:4]
            cr.set_source_rgba(0, 0, 0, 0.7)
            cr.rectangle(wx0, wy0 - th2 - 6, tw2 + 6, th2 + 4)
            cr.fill()
            cr.set_source_rgb(1, 1, 0)
            cr.move_to(wx0 + 3 - xb2, wy0 - 4)
            cr.show_text(lbl2)

    # ── Guardar ──────────────────────────────────────────────────────────────

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return

        guardados = 0
        for sid in self._slot_ids:
            p = self._slots[sid]
            if not p["modificado"] and not p["es_nuevo"]:
                continue

            nombre    = p["nombre"]
            id_equipo = p["id_equipo"] or None
            x = p["x"]; y = p["y"]; w = p["w"]; h = p["h"]

            if sid.startswith("NEW_"):
                self._guardar_nuevo(nombre, id_equipo, x, y, w, h)
            else:
                self._guardar_existente(sid, nombre, id_equipo, x, y, w, h)
            guardados += 1

        if guardados:
            msg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=self._msg_guardado(guardados),
            )
            msg.run(); msg.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoSlotsFrame — frame/slot reales
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoSlotsFrame(EditorMasivoSlotsBase):

    _ETIQUETA_PADRE = "Frame"
    _TITULO_VENTANA_FMT = "Slots de frame: {}"
    _MOSTRAR_EQUIPO = True

    def __init__(self, id_frame, parent=None, fn_sel_imagen=None):
        super().__init__(
            id_padre=id_frame, parent=parent, fn_sel_imagen=fn_sel_imagen,
            titulo_inicial="Edición masiva de slots",
        )

    def _cargar_padre(self):
        rows = Modelo._query(
            "SELECT f.nombre, f.id_imagen, COALESCE(i.path_archivo,'') "
            "FROM frame f LEFT JOIN imagen i ON i.id_imagen=f.id_imagen "
            "WHERE f.id_frame=?", (self._id_padre,))
        if not rows:
            return f"Frame {self._id_padre}", "", ""
        r = rows[0]
        id_img = str(r[1]) if r[1] else ""
        return s(r[0]), id_img, s(r[2])

    def _cargar_slots(self):
        slots_db = Modelo._query(
            "SELECT s.id_slot, s.nombre, COALESCE(e.nombre,''), "
            "       s.rectangulo_x_en_imagen, s.rectangulo_y_en_imagen, "
            "       s.rectangulo_ancho_pixeles, s.rectangulo_alto_pixeles, "
            "       s.id_equipo "
            "FROM slot s "
            "LEFT JOIN equipo e ON e.id_equipo=s.id_equipo "
            "WHERE s.id_frame=? ORDER BY s.nombre",
            (self._id_padre,))
        path_archivo = Modelo._path_imagen(self._id_imagen or None)
        # normalizado: id_slot, nombre, nombre_equipo, id_equipo, x, y, w, h
        resultado = []
        for r in slots_db:
            x, y, w, h = Modelo._px_rect_o_crudo(
                path_archivo, r[3], r[4], r[5], r[6])
            resultado.append((r[0], r[1], r[2], r[7], x, y, w, h))
        return resultado

    def _actualizar_imagen_padre(self, id_img):
        Modelo._exec(
            "UPDATE frame SET id_imagen=? WHERE id_frame=?",
            (id_img, self._id_padre))

    def _guardar_nuevo(self, nombre, id_equipo, x, y, w, h):
        id_img = self._id_imagen or None
        Modelo.agregar_slot_retorna_id(
            nombre, id_equipo, self._id_padre, id_img, x, y, w, h)

    def _guardar_existente(self, sid, nombre, id_equipo, x, y, w, h):
        id_img = self._id_imagen or None
        Modelo.modificar_slot(
            sid, nombre, id_equipo, self._id_padre, id_img, x, y, w, h)


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoSlotsCatalogo — frame_catalogo/slot_catalogo (moldes)
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoSlotsCatalogo(EditorMasivoSlotsBase):
    """
    Variante de EditorMasivoSlotsFrame para el catálogo (moldes): define
    visualmente los rectángulos de los slot_catalogo de un frame_catalogo
    sobre su imagen, en una sola sesión.

    Diferencias respecto al editor de frame real:
      - Lee/escribe frame_catalogo / slot_catalogo (no frame / slot).
      - Los slots de molde nunca tienen equipo asignado (sin columna Equipo).
      - Al guardar usa Modelo.agregar_slot_catalogo / modificacion_slot_catalogo.
    """

    _ETIQUETA_PADRE = "Molde"
    _TITULO_VENTANA_FMT = "Slots del molde: {}"
    _MOSTRAR_EQUIPO = False

    def __init__(self, id_frame_catalogo, parent=None, fn_sel_imagen=None):
        super().__init__(
            id_padre=id_frame_catalogo, parent=parent,
            fn_sel_imagen=fn_sel_imagen,
            titulo_inicial="Edición masiva de slots (molde)",
        )

    def _cargar_padre(self):
        rows = Modelo.devolver_catalogo_frame(self._id_padre)
        if not rows:
            return f"Molde {self._id_padre}", "", ""
        r = rows[0]
        # r: id, nombre_molde, id_marca, marca_nom, modelo, id_imagen,
        #    img_path, path_manual, configuraciones
        id_img = str(r[5]) if r[5] else ""
        return s(r[1]), id_img, s(r[6])

    def _cargar_slots(self):
        slots_db = Modelo.devolver_slots_de_catalogo_frame(self._id_padre)
        # slots_db: id_slot_catalogo, nombre, x, y, ancho, alto
        # normalizado: id_slot, nombre, nombre_equipo(""), id_equipo(None), x, y, w, h
        return [(sl[0], sl[1], "", None, sl[2], sl[3], sl[4], sl[5])
                for sl in slots_db]

    def _actualizar_imagen_padre(self, id_img):
        Modelo._exec(
            "UPDATE frame_catalogo SET id_imagen=? WHERE id_frame_catalogo=?",
            (id_img, self._id_padre))

    def _guardar_nuevo(self, nombre, id_equipo, x, y, w, h):
        Modelo.agregar_slot_catalogo(self._id_padre, nombre, x, y, w, h)

    def _guardar_existente(self, sid, nombre, id_equipo, x, y, w, h):
        Modelo.modificacion_slot_catalogo(sid, nombre, x, y, w, h)

    def _msg_guardado(self, n):
        return f"Se guardaron {n} slot(s) del molde."


# ── funciones de conveniencia ─────────────────────────────────────────────────

def abrir_editor_masivo_slots(id_frame, parent=None, fn_sel_imagen=None):
    dlg = EditorMasivoSlotsFrame(id_frame=id_frame, parent=parent, fn_sel_imagen=fn_sel_imagen)
    dlg.run()
    dlg.destroy()


def abrir_editor_masivo_slots_catalogo(id_frame_catalogo, parent=None, fn_sel_imagen=None):
    dlg = EditorMasivoSlotsCatalogo(
        id_frame_catalogo=id_frame_catalogo, parent=parent, fn_sel_imagen=fn_sel_imagen)
    dlg.run()
    dlg.destroy()
