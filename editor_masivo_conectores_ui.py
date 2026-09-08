#!/usr/bin/env python3
"""
editor_masivo_conectores_ui.py — CableDoc GTK3
================================================
Editor de posicionado masivo de conectores sobre una imagen.

Contiene:
  - EditorMasivoConectoresBase  — lógica común (UI, overlay, interacción,
                                   guardado) extraída de las dos variantes
                                   que existían en pantallas_avanzadas.py.
  - EditorMasivoConectoresImagen    — para conector/equipo reales.
  - EditorMasivoConectoresCatalogo  — para conector_catalogo/equipo_catalogo
                                       (moldes).
  - abrir_editor_masivo_conectores(id_equipo, parent, fn_sel_imagen)
  - abrir_editor_masivo_conectores_catalogo(id_equipo_catalogo, parent, fn_sel_imagen)

Extraído 1:1 de pantallas_avanzadas.py (Entrega 4) y unificado en una
clase base para eliminar la duplicación entre ambas variantes.
"""

import math

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from modelo import Modelo
from pantallas_comunes import (
    _, s, PALETA, _pixbuf_from_name, _ImagenZoom, _ImagenSVG,
    _crear_handle_simbolo, _dibujar_simbolo_conector,
)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _clave_orden_natural(nombre):
    """Clave de orden para nombres de conector tipo '01', '24', 'IN 3',
    etc.: ordena por el último número que aparezca en el nombre (si hay),
    y si no por el texto plano. Usado por la colocación en lote (Fase 2
    de plan_paneles_vectoriales_v3.md) para poder ofrecer un orden
    ascendente/descendente sensato sin depender de que los nombres estén
    ceropadeados."""
    import re
    m = re.search(r"(\d+)(?!.*\d)", nombre or "")
    if m:
        return (0, int(m.group(1)), nombre)
    return (1, 0, (nombre or "").lower())


# ══════════════════════════════════════════════════════════════════════════════
#  _DialogoColocacionLote — Fase 2 de plan_paneles_vectoriales_v3.md
# ══════════════════════════════════════════════════════════════════════════════

class _DialogoColocacionLote(Gtk.Dialog):
    """Coloca en una sola operación una fila o grilla de conectores del
    mismo tipo, espaciados uniformemente a partir de un punto inicial.
    Pensado para el caso típico de un patchbay de 24 conectores en línea:
    sin esto, había que hacer 24 clics uno por uno.

    El orden ascendente/descendente cubre la numeración espejada típica
    de patchbays (la fila física va 24→1 en la cara trasera aunque los
    nombres sigan siendo '1'..'24'): se ordena por _clave_orden_natural y,
    si es descendente, se invierte antes de recorrer la grilla.

    No crea conectores nuevos — sólo asigna posición a conectores que ya
    existen en `conectores` (misma lista que usa EditorMasivoConectoresBase),
    filtrados por tipo y, opcionalmente, sólo entre los que todavía no
    tienen posición."""

    def __init__(self, parent, conectores, pendientes, punto_inicial=None):
        super().__init__(title=_("Colocar fila / grilla"),
                          transient_for=parent, modal=True)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          _("Colocar"), Gtk.ResponseType.OK)
        self.set_default_size(420, 0)
        self._conectores = conectores
        self._pendientes = pendientes
        self.resultado = None   # (lista_ids_en_orden, cols, sx, sy, ix0, iy0)

        tipos = sorted({c["tipo"] for c in conectores if c["tipo"]})

        g = Gtk.Grid(row_spacing=6, column_spacing=8,
                     margin_start=10, margin_end=10, margin_top=10, margin_bottom=6)
        fila_g = 0

        def _agregar(label_txt, widget):
            nonlocal fila_g
            g.attach(Gtk.Label(label=label_txt, xalign=0), 0, fila_g, 1, 1)
            g.attach(widget, 1, fila_g, 1, 1)
            fila_g += 1

        self.c_tipo = Gtk.ComboBoxText()
        self.c_tipo.append_text(_("(todos)"))
        for t in tipos:
            self.c_tipo.append_text(t)
        self.c_tipo.set_active(0)
        self.c_tipo.connect("changed", self._recalcular)
        _agregar(_("Tipo de conector:"), self.c_tipo)

        self.chk_solo_libres = Gtk.CheckButton(label=_("Sólo sin posición"))
        self.chk_solo_libres.set_active(True)
        self.chk_solo_libres.connect("toggled", self._recalcular)
        _agregar("", self.chk_solo_libres)

        self.c_orden = Gtk.ComboBoxText()
        self.c_orden.append_text(_("Ascendente (1, 2, 3…)"))
        self.c_orden.append_text(_("Descendente (…3, 2, 1)"))
        self.c_orden.set_active(0)
        self.c_orden.connect("changed", self._recalcular)
        _agregar(_("Orden de numeración:"), self.c_orden)

        self.sp_cantidad = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.sp_cantidad.connect("value-changed", self._recalcular)
        _agregar(_("Cantidad a colocar:"), self.sp_cantidad)

        self.sp_filas = Gtk.SpinButton.new_with_range(1, 100, 1)
        self.sp_filas.set_value(1)
        self.sp_filas.connect("value-changed", self._recalcular)
        _agregar(_("Filas:"), self.sp_filas)

        self.sp_columnas = Gtk.SpinButton.new_with_range(1, 100, 1)
        self.sp_columnas.set_value(1)
        self.sp_columnas.connect("value-changed", self._recalcular)
        _agregar(_("Columnas:"), self.sp_columnas)

        ix0, iy0 = punto_inicial or (50, 50)
        self.sp_x0 = Gtk.SpinButton.new_with_range(0, 20000, 1)
        self.sp_x0.set_value(ix0)
        _agregar(_("Punto inicial X:"), self.sp_x0)
        self.sp_y0 = Gtk.SpinButton.new_with_range(0, 20000, 1)
        self.sp_y0.set_value(iy0)
        _agregar(_("Punto inicial Y:"), self.sp_y0)

        self.sp_sep_x = Gtk.SpinButton.new_with_range(1, 5000, 1)
        self.sp_sep_x.set_value(40)
        _agregar(_("Separación X (px):"), self.sp_sep_x)
        self.sp_sep_y = Gtk.SpinButton.new_with_range(1, 5000, 1)
        self.sp_sep_y.set_value(40)
        _agregar(_("Separación Y (px):"), self.sp_sep_y)

        self._lbl_preview = Gtk.Label(xalign=0, wrap=True)
        self._lbl_preview.set_markup("<small></small>")
        g.attach(self._lbl_preview, 0, fila_g, 2, 1)

        self.get_content_area().pack_start(g, True, True, 0)
        self.connect("response", self._on_response)
        self._recalcular()
        self.show_all()

    def _candidatos(self):
        """Conectores que matchean el tipo elegido y (si aplica) que
        todavía no tienen posición, ordenados naturalmente por nombre."""
        tipo_sel = self.c_tipo.get_active_text()
        solo_libres = self.chk_solo_libres.get_active()
        out = []
        for c in self._conectores:
            if tipo_sel and tipo_sel != _("(todos)") and c["tipo"] != tipo_sel:
                continue
            if solo_libres and self._pendientes.get(c["id"], {}).get("x"):
                continue
            out.append(c)
        out.sort(key=lambda c: _clave_orden_natural(c["nombre"]))
        return out

    def _recalcular(self, *_a):
        candidatos = self._candidatos()
        max_cant = max(1, len(candidatos))
        self.sp_cantidad.set_range(1, max_cant)
        if self.sp_cantidad.get_value() > max_cant or self.sp_cantidad.get_value() == 1:
            self.sp_cantidad.set_value(max_cant)

        cantidad = int(self.sp_cantidad.get_value())
        filas, cols = int(self.sp_filas.get_value()), int(self.sp_columnas.get_value())
        # Si la grilla no alcanza para "cantidad", ajustar filas para que sí.
        if filas * cols < cantidad:
            filas = -(-cantidad // cols)   # ceil
            self.sp_filas.set_value(filas)

        seleccionados = candidatos[:cantidad]
        if self.c_orden.get_active() == 1:   # Descendente
            seleccionados = list(reversed(seleccionados))

        if not candidatos:
            texto = _("<small><i>No hay conectores que coincidan con el filtro.</i></small>")
        else:
            nombres = ", ".join(c["nombre"] for c in seleccionados[:6])
            if len(seleccionados) > 6:
                nombres += f"… (+{len(seleccionados) - 6})"
            texto = (f"<small>Se van a posicionar <b>{len(seleccionados)}</b> "
                     f"conector(es): {GLib.markup_escape_text(nombres)}</small>")
        self._lbl_preview.set_markup(texto)
        self._seleccionados = seleccionados

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return
        if not self._seleccionados:
            self.resultado = None
            return
        self.resultado = (
            [c["id"] for c in self._seleccionados],
            int(self.sp_columnas.get_value()),
            int(self.sp_sep_x.get_value()), int(self.sp_sep_y.get_value()),
            int(self.sp_x0.get_value()), int(self.sp_y0.get_value()),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoConectoresBase — lógica común
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoConectoresBase(Gtk.Dialog):
    """
    Ventana para posicionar todos los conectores de un equipo (o de un molde
    de catálogo) sobre su imagen en una sola sesión.

    Panel izquierdo: imagen con zoom (se dibuja un círculo coloreado por
    cada conector ya posicionado).
    Panel derecho: lista de conectores. Seleccionar uno y luego hacer clic
    en la imagen coloca/mueve su marcador. La fila se colorea igual que el
    marcador. El botón "Colocar fila / grilla…" (Fase 2 de
    plan_paneles_vectoriales_v3.md) posiciona de una sola vez varios
    conectores del mismo tipo, espaciados uniformemente desde un punto
    inicial — pensado para filas de patchbay de 8/16/24 conectores, con
    orden ascendente o descendente para cubrir la numeración espejada
    típica de la cara trasera.

    Al presionar "Guardar" se actualizan coordenada_x_en_imagen,
    coordenada_y_en_imagen e id_imagen en todos los conectores modificados.

    Subclases deben implementar:
      _cargar_datos()      → (nombre_padre, lista de conectores normalizados,
                               path_imagen_fallback)
                              cada conector: (id_con, nombre, tipo, id_img,
                              path, x, y[, id_tipo_ficha])
                              El 8vo elemento (id_tipo_ficha — la ficha,
                              qué es el conector eléctricamente; NO
                              id_tipo_conector, que es sólo el rol IN/OUT
                              del jack, ver corrección de modelo.py) es
                              opcional — si falta, el símbolo con forma
                              real de la Fase 1 de
                              plan_paneles_vectoriales_v3.md queda
                              desactivado para ese conector y se dibuja
                              el círculo genérico de siempre.
      _guardar_uno(id_con, p) → bool (True si se persistió el cambio)
    Y pueden opcionalmente sobrescribir:
      _post_sel_imagen(id_img) → hook tras elegir imagen nueva (no-op default)
      _msg_guardado(n)         → texto del mensaje de confirmación
      _TABLA_DIMENSIONES       → "equipo" o "equipo_catalogo" (whitelist de
                                  Modelo._TABLAS_DIMENSIONES) — de dónde sale
                                  el ancho_mm para la calibración de escala
                                  cuando no hay medición manual en la imagen
    """

    PALETA = PALETA
    R = 10   # radio del marcador genérico
    _TABLA_DIMENSIONES = None   # subclases lo sobrescriben

    def __init__(self, id_padre, parent=None, fn_sel_imagen=None,
                 titulo_inicial="Edición masiva: conectores en imagen"):
        super().__init__(
            title=titulo_inicial,
            transient_for=parent,
            modal=True, destroy_with_parent=True,
        )
        self.set_default_size(1280, 750)
        self._id_padre = str(id_padre)
        self._fn_sel_imagen = fn_sel_imagen
        self._pendientes = {}   # id_conector → {x, y, id_imagen, modificado}
        self._sel_id = None     # id_conector seleccionado
        self._ultimo_click = None   # último punto clickeado en la imagen
                                     # (Fase 2 — prefill de "punto inicial")
        # Fase 1 de plan_paneles_vectoriales_v3.md — ver
        # _preparar_simbolos_conector.
        self._simbolos_activos = False
        self._handles_por_tipo = {}
        self._mm_por_pixel     = None

        self._build_ui()
        self._cargar()

    # ── Hooks a implementar/sobrescribir en subclases ──────────────────────

    def _cargar_datos(self):
        raise NotImplementedError

    def _guardar_uno(self, id_con, p):
        raise NotImplementedError

    def _post_sel_imagen(self, id_img):
        pass

    def _msg_guardado(self, n):
        return f"Se guardaron {n} conector(es)."

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ca = self.get_content_area()

        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_position(820)
        ca.pack_start(hpaned, True, True, 0)

        # ── Panel izquierdo: imagen ──
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # selector de imagen
        top_bar = Gtk.Box(spacing=6, margin_start=6, margin_end=6,
                          margin_top=4, margin_bottom=4)
        top_bar.pack_start(Gtk.Label(label=_("Imagen:")), False, False, 0)
        self._e_imagen = Gtk.Entry(editable=False, hexpand=True)
        btn_img = Gtk.Button(label="…")
        btn_img.connect("clicked", self._sel_imagen)
        top_bar.pack_start(self._e_imagen, True, True, 0)
        top_bar.pack_start(btn_img, False, False, 0)
        left.pack_start(top_bar, False, False, 0)

        self._viz = _ImagenZoom(
            eventos_extra=Gdk.EventMask.BUTTON_PRESS_MASK
        )
        self._viz.overlay_fn = self._dibujar_overlay
        self._viz.da.connect("button-press-event", self._on_clic_imagen)
        left.pack_start(self._viz, True, True, 0)

        hpaned.pack1(left, resize=True, shrink=False)

        # ── Panel derecho: conectores ──
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                        margin_start=6, margin_end=8,
                        margin_top=6, margin_bottom=4)

        self._lbl_eq = Gtk.Label(xalign=0)
        self._lbl_eq.set_markup("<i>Cargando…</i>")
        right.pack_start(self._lbl_eq, False, False, 0)

        lbl_ins = Gtk.Label(xalign=0)
        lbl_ins.set_markup(
            "<small>1. Seleccioná un conector\n"
            "2. Hacé clic en la imagen para posicionarlo\n"
            "Clic derecho en imagen → quitar posición\n"
            "'Colocar fila / grilla' → posicionar varios de una</small>"
        )
        right.pack_start(lbl_ins, False, False, 4)

        right.pack_start(Gtk.Separator(), False, False, 0)

        # TreeView de conectores
        # cols: id_conector, nombre, tipo, color_bg, x, y, ✓
        self._store = Gtk.ListStore(str, str, str, str, str, str, str)
        self._tv = Gtk.TreeView(model=self._store, headers_visible=True)
        self._tv.set_activate_on_single_click(True)

        specs = [
            ("Conector", 1, True),
            ("Tipo",     2, True),
            ("X",        4, True),
            ("Y",        5, True),
            ("",         6, True),   # ✓ posicionado
        ]
        for titulo, col_idx, expand in specs:
            rend = Gtk.CellRendererText(xpad=4)
            rend.set_property("ellipsize", 3)
            col  = Gtk.TreeViewColumn(titulo, rend, text=col_idx,
                                      background=3)
            col.set_expand(expand)
            col.set_resizable(True)
            self._tv.append_column(col)

        self._tv.get_selection().connect("changed", self._on_sel_conector)
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._tv)
        right.pack_start(sw, True, True, 0)

        # botones
        btn_box = Gtk.Box(spacing=6, margin_top=4)
        btn_limpiar = Gtk.Button(label=_("✕ Quitar seleccionado"))
        btn_limpiar.connect("clicked", self._quitar_sel)
        btn_limpiar_todos = Gtk.Button(label=_("✕✕ Quitar todos"))
        btn_limpiar_todos.connect("clicked", self._quitar_todos)
        btn_box.pack_start(btn_limpiar, True, True, 0)
        btn_box.pack_start(btn_limpiar_todos, True, True, 0)
        right.pack_start(btn_box, False, False, 0)

        btn_lote = Gtk.Button(label=_("▦ Colocar fila / grilla…"))
        btn_lote.connect("clicked", self._abrir_colocacion_lote)
        right.pack_start(btn_lote, False, False, 4)

        hpaned.pack2(right, resize=False, shrink=False)

        # Botones del diálogo
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button("💾 Guardar cambios", Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.connect("response", self._on_response)

        self.show_all()

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _cargar(self):
        nombre_titulo, cons, img_pred_fallback = self._cargar_datos()
        self._lbl_eq.set_markup(f"<b>{nombre_titulo}</b>")
        self.set_title(f"Edición masiva conectores: {nombre_titulo}")

        self._conectores = []   # lista ordenada de dicts
        self._pendientes = {}
        self._store.clear()

        # Determinar imagen predominante
        img_paths = {}
        for r in cons:
            p = s(r[4]).strip()
            if p:
                img_paths[p] = img_paths.get(p, 0) + 1
        img_pred = max(img_paths, key=img_paths.get) if img_paths else ""
        if not img_pred and img_pred_fallback:
            img_pred = img_pred_fallback

        for i, r in enumerate(cons):
            id_con = str(r[0])
            nombre = s(r[1])
            tipo   = s(r[2])
            id_img = str(r[3]) if r[3] else ""
            path   = s(r[4]).strip()
            x      = str(r[5]) if r[5] is not None else ""
            y      = str(r[6]) if r[6] is not None else ""
            id_tipo_ficha = r[7] if len(r) > 7 else None
            color  = self.PALETA[i % len(self.PALETA)]
            hex_c  = "#{:02X}{:02X}{:02X}".format(
                int(color[0]*255), int(color[1]*255), int(color[2]*255))
            tiene  = "✓" if (x and y) else ""

            self._conectores.append({
                "id": id_con, "nombre": nombre, "tipo": tipo,
                "color": hex_c, "idx": i,
                "id_tipo_ficha": id_tipo_ficha,
            })
            self._pendientes[id_con] = {
                "x": x, "y": y, "id_imagen": id_img,
                "path": path, "modificado": False,
            }
            bg = hex_c if (x and y) else "#ffffff"
            self._store.append([id_con, nombre, tipo, bg, x, y, tiene])

        # Cargar imagen predominante
        if img_pred:
            self._e_imagen.set_text(img_pred)
            pb = _pixbuf_from_name(img_pred)
            if pb:
                self._viz.set_pixbuf(pb)
                GLib.idle_add(self._viz._zoom_fit)
                id_imagen_pred = next(
                    (r[3] for r in cons if s(r[4]).strip() == img_pred and r[3]),
                    None)
                self._preparar_simbolos_conector(pb, id_imagen_pred)

    def _preparar_simbolos_conector(self, pb, id_imagen):
        """Precalcula (una sola vez por carga) los símbolos con forma real
        y la calibración de escala — Fase 1 de plan_paneles_vectoriales_v3.md.
        Regla de activación (§4): sólo si el fondo es SVG. Compartido entre
        EditorMasivoConectoresImagen y EditorMasivoConectoresCatalogo vía
        `_TABLA_DIMENSIONES`, que cada subclase declara. Si algo falla acá,
        queda todo desactivado y _dibujar_overlay cae al círculo genérico
        de siempre, sin excepciones visibles."""
        self._simbolos_activos = False
        self._handles_por_tipo = {}
        self._mm_por_pixel     = None
        if not isinstance(pb, _ImagenSVG):
            return
        try:
            ancho_px = pb.get_width()
        except Exception:
            ancho_px = 0
        if not ancho_px:
            return
        try:
            self._mm_por_pixel = Modelo.resolver_mm_por_pixel(
                self._TABLA_DIMENSIONES, self._id_padre, id_imagen, ancho_px)
        except Exception:
            self._mm_por_pixel = None
        tipos = {c["id_tipo_ficha"] for c in self._conectores
                 if c.get("id_tipo_ficha")}
        if not tipos:
            return
        try:
            simbolos = Modelo.obtener_simbolos_conector(list(tipos))
        except Exception:
            simbolos = {}
        for id_tipo, (frag, viewbox, tamano_rel, color) in simbolos.items():
            handle = _crear_handle_simbolo(frag, viewbox, color)
            if handle is not None:
                self._handles_por_tipo[id_tipo] = (handle, tamano_rel or 1.0)
        self._simbolos_activos = bool(self._handles_por_tipo)

    def _color_de(self, id_con):
        for c in self._conectores:
            if c["id"] == id_con:
                return c["color"]
        return "#888888"

    def _idx_de(self, id_con):
        for i, c in enumerate(self._conectores):
            if c["id"] == id_con:
                return i
        return -1

    # ── Selector de imagen ────────────────────────────────────────────────────

    def _sel_imagen(self, btn):
        # Usar fn_sel_imagen (ABM interno) obligatoriamente
        if self._fn_sel_imagen:
            result = self._fn_sel_imagen(self)
            if result:
                nombre, id_img = result
                self._e_imagen.set_text(s(nombre))
                self._img_id_actual = str(id_img) if id_img else ""
                pb = _pixbuf_from_name(nombre)
                if pb:
                    self._viz.set_pixbuf(pb)
                    GLib.idle_add(self._viz._zoom_fit)
                self._post_sel_imagen(self._img_id_actual)
        else:
            # Si no hay callback, no hacemos nada o avisamos
            pass

    # ── Interacción imagen ────────────────────────────────────────────────────

    def _on_clic_imagen(self, da, ev):
        if self._viz.pixbuf is None:
            return
        ix, iy = self._viz.w2i(ev.x, ev.y)
        if not (0 <= ix < self._viz.pixbuf.get_width() and
                0 <= iy < self._viz.pixbuf.get_height()):
            return

        # Fase 2 de plan_paneles_vectoriales_v3.md: recordar el último
        # punto clickeado (aunque no haya seleccionado nada) para
        # prellenar el "punto inicial" de la colocación en lote.
        self._ultimo_click = (int(round(ix)), int(round(iy)))

        if ev.button == 3:   # clic derecho → quitar posición del seleccionado
            self._quitar_sel(None)
            return

        if not self._sel_id:
            return

        # Obtener id_imagen de la imagen actual
        img_nombre = self._e_imagen.get_text().strip()
        rows = Modelo._query(
            "SELECT id_imagen FROM imagen WHERE path_archivo=?", (img_nombre,))
        id_img = str(rows[0][0]) if rows else \
                 getattr(self, "_img_id_actual", "")

        p = self._pendientes[self._sel_id]
        p["x"] = str(int(round(ix)))
        p["y"] = str(int(round(iy)))
        p["id_imagen"] = id_img
        p["modificado"] = True

        self._actualizar_fila(self._sel_id)
        self._viz.da.queue_draw()

        # Avanzar selección al siguiente sin posición
        self._avanzar_seleccion()

    def _avanzar_seleccion(self):
        """Selecciona automáticamente el próximo conector sin posición."""
        idx_actual = self._idx_de(self._sel_id)
        n = len(self._conectores)
        for offset in range(1, n + 1):
            siguiente = self._conectores[(idx_actual + offset) % n]
            p = self._pendientes[siguiente["id"]]
            if not p["x"]:
                self._sel_conector_por_id(siguiente["id"])
                return

    def _sel_conector_por_id(self, id_con):
        idx = self._idx_de(id_con)
        if idx >= 0:
            self._tv.get_selection().select_path(
                Gtk.TreePath.new_from_indices([idx]))
            self._tv.scroll_to_cell(
                Gtk.TreePath.new_from_indices([idx]), None, True, 0.5, 0)

    def _on_sel_conector(self, sel):
        model, it = sel.get_selected()
        if it:
            self._sel_id = model.get_value(it, 0)
        else:
            self._sel_id = None
        self._viz.da.queue_draw()

    def _actualizar_fila(self, id_con):
        idx = self._idx_de(id_con)
        if idx < 0:
            return
        p = self._pendientes[id_con]
        color = self._color_de(id_con)
        tiene = "✓" if p["x"] else ""
        bg    = color if p["x"] else "#ffffff"
        it = self._store.get_iter(Gtk.TreePath.new_from_indices([idx]))
        self._store.set(it, 3, bg, 4, p["x"], 5, p["y"], 6, tiene)

    def _quitar_sel(self, btn):
        if not self._sel_id:
            return
        p = self._pendientes[self._sel_id]
        p["x"] = ""; p["y"] = ""
        p["modificado"] = True
        self._actualizar_fila(self._sel_id)
        self._viz.da.queue_draw()

    def _quitar_todos(self, btn):
        for id_con, p in self._pendientes.items():
            p["x"] = ""; p["y"] = ""
            p["modificado"] = True
            self._actualizar_fila(id_con)
        self._viz.da.queue_draw()

    def _abrir_colocacion_lote(self, btn):
        """Fase 2 de plan_paneles_vectoriales_v3.md: colocar de una sola
        vez una fila o grilla de conectores del mismo tipo, en vez de
        clic por clic. No requiere que haya imagen elegida para abrir el
        diálogo, pero sí para poder guardar posiciones con sentido (la
        imagen determina el sistema de coordenadas en el que se ubican
        X/Y)."""
        if self._viz.pixbuf is None:
            msg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("Elegí una imagen primero."))
            msg.run(); msg.destroy()
            return
        dlg = _DialogoColocacionLote(
            self, self._conectores, self._pendientes,
            punto_inicial=self._ultimo_click)
        dlg.run()
        resultado = dlg.resultado
        dlg.destroy()
        if resultado:
            self._aplicar_colocacion_lote(*resultado)

    def _aplicar_colocacion_lote(self, ids_ordenados, columnas, sep_x, sep_y, ix0, iy0):
        img_nombre = self._e_imagen.get_text().strip()
        rows = Modelo._query(
            "SELECT id_imagen FROM imagen WHERE path_archivo=?", (img_nombre,))
        id_img = str(rows[0][0]) if rows else \
                 getattr(self, "_img_id_actual", "")

        for i, id_con in enumerate(ids_ordenados):
            fila_grilla = i // columnas
            col_grilla  = i % columnas
            x = ix0 + col_grilla * sep_x
            y = iy0 + fila_grilla * sep_y
            p = self._pendientes[id_con]
            p["x"] = str(int(x))
            p["y"] = str(int(y))
            p["id_imagen"] = id_img
            p["modificado"] = True
            self._actualizar_fila(id_con)

        self._viz.da.queue_draw()

    # ── Overlay ───────────────────────────────────────────────────────────────

    def _dibujar_overlay(self, cr):
        for c in self._conectores:
            id_con = c["id"]
            p = self._pendientes[id_con]
            if not p["x"] or not p["y"]:
                continue
            try:
                ix, iy = int(p["x"]), int(p["y"])
            except ValueError:
                continue

            wx, wy = self._viz.i2w(ix, iy)
            r, g, b = _hex_to_rgb(c["color"])
            es_sel  = (id_con == self._sel_id)

            # Fase 1 de plan_paneles_vectoriales_v3.md: símbolo con forma
            # real si hay uno cargado para el tipo de este conector y el
            # fondo es SVG (ver _preparar_simbolos_conector). Fallback
            # automático al círculo genérico si falta símbolo o falla el
            # render (§4 del plan — nunca rompe el editor).
            if self._simbolos_activos:
                info = self._handles_por_tipo.get(c.get("id_tipo_ficha"))
                if info is not None:
                    handle, tamano_rel = info
                    radio_px = Modelo.calcular_radio_simbolo_px(
                        tamano_rel, self._mm_por_pixel,
                        radio_default_px=self.R)
                    if _dibujar_simbolo_conector(cr, handle, wx, wy, radio_px):
                        if es_sel:
                            cr.set_source_rgba(1, 0.9, 0, 0.85)
                            cr.set_line_width(2.5)
                            cr.arc(wx, wy, radio_px + 3, 0, 2 * math.pi)
                            cr.stroke()
                        cr.select_font_face("Sans", 0, 1)
                        cr.set_font_size(9)
                        lbl = c["nombre"][:8]
                        xb, _, tw, th = cr.text_extents(lbl)[:4]
                        cr.set_source_rgba(0, 0, 0, 0.7)
                        cr.rectangle(wx - tw/2 - 2, wy + radio_px + 1, tw + 4, th + 2)
                        cr.fill()
                        cr.set_source_rgb(1, 1, 1)
                        cr.move_to(wx - tw/2 - xb, wy + radio_px + th + 2)
                        cr.show_text(lbl)
                        continue  # símbolo dibujado OK, no caer al genérico

            # Sombra
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.arc(wx + 2, wy + 2, self.R, 0, 2 * math.pi)
            cr.fill()

            # Círculo
            cr.set_source_rgb(r, g, b)
            cr.arc(wx, wy, self.R, 0, 2 * math.pi)
            cr.fill()

            # Borde (más grueso si seleccionado)
            cr.set_source_rgb(1, 1, 1)
            cr.set_line_width(3 if es_sel else 1.5)
            cr.arc(wx, wy, self.R, 0, 2 * math.pi)
            cr.stroke()

            # Etiqueta
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(9)
            lbl = c["nombre"][:8]
            xb, _, tw, th = cr.text_extents(lbl)[:4]
            cr.set_source_rgba(0, 0, 0, 0.7)
            cr.rectangle(wx - tw/2 - 2, wy + self.R + 1, tw + 4, th + 2)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(wx - tw/2 - xb, wy + self.R + th + 2)
            cr.show_text(lbl)

        # Cruz sobre el punto seleccionado (sin posición aún)
        if self._sel_id:
            p = self._pendientes.get(self._sel_id, {})
            if not p.get("x"):
                # Mostrar cursor guía en centro del viewport
                alloc = self._viz.da.get_allocation()
                cx, cy = alloc.width / 2, alloc.height / 2
                cr.set_source_rgba(1, 0.9, 0, 0.6)
                cr.set_line_width(1.5)
                cr.move_to(cx - 12, cy); cr.line_to(cx + 12, cy)
                cr.move_to(cx, cy - 12); cr.line_to(cx, cy + 12)
                cr.stroke()

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return
        modificados = 0
        for id_con, p in self._pendientes.items():
            if not p["modificado"]:
                continue
            if self._guardar_uno(id_con, p):
                modificados += 1

        if modificados:
            msg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=self._msg_guardado(modificados),
            )
            msg.run(); msg.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoConectoresImagen — equipo/conector reales
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoConectoresImagen(EditorMasivoConectoresBase):

    _TABLA_DIMENSIONES = "equipo"

    def __init__(self, id_equipo, parent=None, fn_sel_imagen=None):
        super().__init__(
            id_padre=id_equipo, parent=parent, fn_sel_imagen=fn_sel_imagen,
            titulo_inicial="Edición masiva: conectores en imagen",
        )

    def _cargar_datos(self):
        id_equipo = self._id_padre
        rows = Modelo._query(
            "SELECT ve.nombre FROM VISTA_EQUIPOS ve WHERE ve.id=?",
            (id_equipo,)
        )
        nombre_eq = s(rows[0][0]) if rows else f"Equipo {id_equipo}"

        cons = Modelo._query(
            "SELECT c.id_conector, c.nombre, COALESCE(tc.nombre,''), "
            "       c.id_imagen, COALESCE(i.path_archivo,''), "
            "       c.coordenada_x_en_imagen, c.coordenada_y_en_imagen, "
            "       c.id_tipo_ficha "
            "FROM conector c "
            "LEFT JOIN tipo_conector tc ON tc.id_tipo_conector=c.id_tipo_conector "
            "LEFT JOIN imagen i ON i.id_imagen=c.id_imagen "
            "WHERE c.id_equipo=? ORDER BY c.nombre",
            (id_equipo,)
        )
        cons = [
            (*r[:5], *Modelo._px_punto_o_crudo(r[4] or None, r[5], r[6]), r[7])
            for r in cons
        ]
        return nombre_eq, cons, None

    def _guardar_uno(self, id_con, p):
        # Leer datos actuales para no pisar nombre/tipo
        rows = Modelo.devolver_conector(id_con)
        if not rows:
            return False
        r = rows[0]
        nombre     = s(r[1])
        id_equipo  = s(r[4])
        id_tipo    = s(r[3])
        id_imagen  = p["id_imagen"] if p["id_imagen"] else s(r[7])
        x          = p["x"] if p["x"] else None
        y          = p["y"] if p["y"] else None
        Modelo.modificacion_conector(
            id_con, nombre, id_equipo, id_tipo, id_imagen, x, y)
        return True


# ══════════════════════════════════════════════════════════════════════════════
#  EditorMasivoConectoresCatalogo — equipo_catalogo/conector_catalogo (moldes)
# ══════════════════════════════════════════════════════════════════════════════

class EditorMasivoConectoresCatalogo(EditorMasivoConectoresBase):
    """
    Variante de EditorMasivoConectoresImagen para el catálogo (moldes):
    posiciona todos los conectores de un equipo_catalogo sobre su imagen
    en una sola sesión.

    Diferencias respecto al editor de equipo real:
      - Lee/escribe equipo_catalogo / conector_catalogo (no equipo / conector).
      - Al guardar usa Modelo.modificacion_conector_catalogo.
      - Al elegir una imagen nueva, además actualiza equipo_catalogo.id_imagen.
    """

    _TABLA_DIMENSIONES = "equipo_catalogo"

    def __init__(self, id_equipo_catalogo, parent=None, fn_sel_imagen=None):
        super().__init__(
            id_padre=id_equipo_catalogo, parent=parent,
            fn_sel_imagen=fn_sel_imagen,
            titulo_inicial="Edición masiva: conectores en imagen (molde)",
        )

    def _cargar_datos(self):
        id_equipo_catalogo = self._id_padre
        rows = Modelo.devolver_catalogo(id_equipo_catalogo)
        nombre_molde = s(rows[0][1]) if rows else f"Molde {id_equipo_catalogo}"

        cons_raw = Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo)
        # cons_raw: id_cc, nombre, tipo_nom, id_tipo_conector, id_imagen,
        #           img_path, x, y
        # NOTA: conector_catalogo todavía no tiene columna id_tipo_ficha
        # (sólo id_tipo_conector, que no sirve para elegir símbolo — ver
        # corrección en modelo.py). Se pasa None a propósito: el símbolo
        # con forma real queda desactivado para moldes hasta que se
        # agregue conector_catalogo.id_tipo_ficha en una entrega futura
        # (fuera de alcance de esta corrección puntual); cae al círculo
        # genérico de siempre, sin romper nada.
        cons = [(r[0], r[1], r[2], r[4], r[5], r[6], r[7], None) for r in cons_raw]

        # Fallback: si ningún conector tiene imagen, usar la imagen del molde
        img_pred_fallback = None
        if rows and rows[0][7]:
            img_pred_fallback = s(rows[0][8]).strip()   # ..., id_imagen(7), img_path(8), ...

        return nombre_molde, cons, img_pred_fallback

    def _post_sel_imagen(self, id_img):
        if id_img:
            Modelo._exec(
                "UPDATE equipo_catalogo SET id_imagen=? WHERE id_equipo_catalogo=?",
                (id_img, self._id_padre))

    def _guardar_uno(self, id_con, p):
        rows = Modelo._query(
            "SELECT nombre, id_tipo_conector FROM conector_catalogo "
            "WHERE id_conector_catalogo=?", (id_con,))
        if not rows:
            return False
        nombre, id_tipo = rows[0]
        id_imagen = p["id_imagen"] or None
        x = p["x"] if p["x"] else None
        y = p["y"] if p["y"] else None
        Modelo.modificacion_conector_catalogo(
            id_con, nombre, id_tipo, id_imagen, x, y)
        return True

    def _msg_guardado(self, n):
        return f"Se guardaron {n} conector(es) del molde."


# ── funciones de conveniencia ─────────────────────────────────────────────────

def abrir_editor_masivo_conectores(id_equipo, parent=None, fn_sel_imagen=None):
    dlg = EditorMasivoConectoresImagen(
        id_equipo=id_equipo, parent=parent, fn_sel_imagen=fn_sel_imagen)
    dlg.run()
    dlg.destroy()


def abrir_editor_masivo_conectores_catalogo(id_equipo_catalogo, parent=None, fn_sel_imagen=None):
    dlg = EditorMasivoConectoresCatalogo(
        id_equipo_catalogo=id_equipo_catalogo, parent=parent, fn_sel_imagen=fn_sel_imagen)
    dlg.run()
    dlg.destroy()
