#!/usr/bin/env python3
"""
equipos_alta_rapida_ui.py — CableDoc GTK3

Dominio Equipos — Alta rápida individual, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 3).

Contiene:
  - _DialogoAltaRapidaEquipo (alta de equipo en un solo formulario, estilo
    AVwire)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta este nombre sin cambios.

Separado de `equipos_ui.py` (listado + ficha completa) porque juntos
superaban las ~900 líneas objetivo del plan (~1.700 líneas → 2 archivos).

`_DialogoDireccionConector` sigue viviendo en `equipos_ui.py`; se resuelve
con import diferido dentro del método que lo usa, siguiendo el mismo patrón
que ya usa el proyecto para evitar ciclos.
"""

import os
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modelo import Modelo, PICON_DIR

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
    DialogoNombre,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
)


# ─── Alta Rápida de Equipo (estilo AVwire) ───────────────────────────────────

class _DialogoAltaRapidaEquipo(Gtk.Dialog):
    """
    Alta de equipo en un solo formulario:
      • Selector de tipo de equipo (con buscador)
      • Datos básicos (nombre, marca, modelo, inventario, serie)
      • Panel de conectores por plantilla con spinners IN / OUT
      • Vista previa en tiempo real
      • Botón "Guardar y duplicar"
    """

    # Colores por dirección de conector
    _COL_IN    = "#1D9E75"   # verde
    _COL_OUT   = "#534AB7"   # violeta
    _COL_INOUT = "#BA7517"   # naranja

    def __init__(self, parent=None):
        super().__init__(title=_("Alta Rápida de Equipo"),
                         transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(920, 580)
        self.add_buttons("Cancelar",          Gtk.ResponseType.CANCEL,
                         "💾 Guardar",        Gtk.ResponseType.OK,
                         "📋 Guardar y duplicar", Gtk.ResponseType.APPLY)

        # Estado interno
        self.id_tipo   = None
        self.id_marca  = None
        self._conectores_activos = {}   # (id_tipo_con, dir) -> cantidad
        self._todos_tipos_con = []      # [(id, nombre), ...]
        self._duplicar = False

        ca = self.get_content_area()
        ca.set_spacing(0)

        # ── Layout principal: izquierda datos + conectores / derecha preview ──
        hpan = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpan.set_position(600)
        ca.pack_start(hpan, True, True, 0)

        # ════════════════════════════════════
        # PANEL IZQUIERDO
        # ════════════════════════════════════
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_box.set_margin_start(12); left_box.set_margin_end(8)
        left_box.set_margin_top(10);  left_box.set_margin_bottom(8)
        left_scroll.add(left_box)
        hpan.add1(left_scroll)

        # ── Sección 1: Tipo de equipo ──
        lbl_s1 = Gtk.Label()
        lbl_s1.set_markup("<b>" + _("1. Tipo de equipo") + "</b>")
        lbl_s1.set_xalign(0); lbl_s1.set_margin_bottom(4)
        left_box.pack_start(lbl_s1, False, False, 0)

        hb_tipo = Gtk.Box(spacing=6)
        self.e_tipo_search = Gtk.SearchEntry()
        self.e_tipo_search.set_placeholder_text("Buscar tipo de equipo…")
        self.e_tipo_search.set_hexpand(True)
        self.e_tipo_search.connect("search-changed", self._on_tipo_search)
        hb_tipo.pack_start(self.e_tipo_search, True, True, 0)
        btn_tipo_nuevo = Gtk.Button(label="+ " + _("Nuevo tipo"))
        btn_tipo_nuevo.connect("clicked", self._crear_tipo)
        hb_tipo.pack_start(btn_tipo_nuevo, False, False, 0)
        left_box.pack_start(hb_tipo, False, False, 0)

        # Lista de tipos
        sw_tipos = Gtk.ScrolledWindow()
        sw_tipos.set_min_content_height(120)
        sw_tipos.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._store_tipos = Gtk.ListStore(str, str)  # id, nombre
        self._tv_tipos = Gtk.TreeView(model=self._store_tipos)
        self._tv_tipos.set_headers_visible(False)
        self._tv_tipos.set_activate_on_single_click(True)
        col_t = Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=6), text=1)
        self._tv_tipos.append_column(col_t)
        self._tv_tipos.connect("row-activated", self._on_tipo_seleccionado)
        sw_tipos.add(self._tv_tipos)
        left_box.pack_start(sw_tipos, False, False, 0)

        self._lbl_tipo_sel = Gtk.Label()
        self._lbl_tipo_sel.set_markup("<i>" + _("Ningún tipo seleccionado") + "</i>")
        self._lbl_tipo_sel.set_xalign(0)
        self._lbl_tipo_sel.set_margin_top(4); self._lbl_tipo_sel.set_margin_bottom(8)
        left_box.pack_start(self._lbl_tipo_sel, False, False, 0)

        sep1 = Gtk.Separator(); left_box.pack_start(sep1, False, False, 6)

        # ── Sección 2: Datos del equipo ──
        lbl_s2 = Gtk.Label()
        lbl_s2.set_markup("<b>" + _("2. Datos del equipo") + "</b>")
        lbl_s2.set_xalign(0); lbl_s2.set_margin_bottom(4)
        left_box.pack_start(lbl_s2, False, False, 0)

        g = _grid(); g.set_margin_bottom(4)
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del equipo (requerido)")
        self.e_nombre.connect("changed", self._actualizar_preview)
        _lbl_entry(g, _("Marca:"), 1)
        self.e_marca = _entry_btn(g, 1, "…", self._sel_marca)
        _lbl_entry(g, _("Modelo:"), 2)
        self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Inventario:"), 3)
        self.e_inventario = _entry(g, 3)
        _lbl_entry(g, _("Serie:"), 4)
        self.e_serie = _entry(g, 4)
        _lbl_entry(g, _("Foto (Picon):"), 5)
        self.e_picon = _entry_btn(g, 5, "…", self._sel_picon)
        left_box.pack_start(g, False, False, 0)

        sep2 = Gtk.Separator(); left_box.pack_start(sep2, False, False, 6)

        # ── Sección 3: Conectores ──
        lbl_s3 = Gtk.Label()
        lbl_s3.set_markup("<b>" + _("3. Conectores") + "</b>")
        lbl_s3.set_xalign(0); lbl_s3.set_margin_bottom(4)
        left_box.pack_start(lbl_s3, False, False, 0)

        lbl_hint = Gtk.Label()
        lbl_hint.set_markup(
            "<small><i>Ajustá las cantidades de cada conector. "
            "Cantidad 0 = no se crea. La plantilla se guarda por tipo de equipo.</i></small>"
        )
        lbl_hint.set_xalign(0); lbl_hint.set_line_wrap(True)
        lbl_hint.set_margin_bottom(6)
        left_box.pack_start(lbl_hint, False, False, 0)

        # Cabecera de conectores
        hdr_con = Gtk.Box(spacing=0)
        for txt, w, align in [
            (_("Tipo conector"),  1,   0.0),
            (_("Entradas (IN)"),  0,   0.5),
            (_("Salidas (OUT)"),  0,   0.5),
        ]:
            lbl = Gtk.Label(label=txt)
            lbl.set_markup(f"<small><b>{txt}</b></small>")
            lbl.set_xalign(align)
            lbl.set_margin_start(4)
            if w:
                hdr_con.pack_start(lbl, True, True, 0)
            else:
                lbl.set_width_chars(12)
                hdr_con.pack_start(lbl, False, False, 0)
        left_box.pack_start(hdr_con, False, False, 0)

        sep_hdr = Gtk.Separator()
        sep_hdr.set_margin_bottom(2)
        left_box.pack_start(sep_hdr, False, False, 0)

        # Contenedor de filas de conectores (se regenera al cambiar tipo)
        self._con_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left_box.pack_start(self._con_box, False, False, 0)

        # Botón agregar tipo conector manual
        btn_add_con = Gtk.Button(label="➕ " + _("Agregar tipo conector"))
        btn_add_con.connect("clicked", self._agregar_conector_manual)
        btn_add_con.set_margin_top(6)
        left_box.pack_start(btn_add_con, False, False, 0)

        # ════════════════════════════════════
        # PANEL DERECHO — Preview
        # ════════════════════════════════════
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8); right_box.set_margin_end(12)
        right_box.set_margin_top(10);  right_box.set_margin_bottom(8)
        hpan.add2(right_box)

        lbl_prev = Gtk.Label()
        lbl_prev.set_markup("<b>" + _("Vista previa") + "</b>")
        lbl_prev.set_xalign(0)
        right_box.pack_start(lbl_prev, False, False, 0)

        # Tarjeta de preview
        frame_prev = Gtk.Frame()
        frame_prev.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        prev_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prev_inner.set_margin_start(12); prev_inner.set_margin_end(12)
        prev_inner.set_margin_top(10);   prev_inner.set_margin_bottom(10)
        frame_prev.add(prev_inner)
        right_box.pack_start(frame_prev, False, False, 0)

        self._lbl_prev_nombre = Gtk.Label()
        self._lbl_prev_nombre.set_markup("<b>—</b>")
        self._lbl_prev_nombre.set_line_wrap(True)
        prev_inner.pack_start(self._lbl_prev_nombre, False, False, 0)

        self._lbl_prev_tipo = Gtk.Label()
        self._lbl_prev_tipo.set_markup("<i>" + _("tipo no seleccionado") + "</i>")
        self._lbl_prev_tipo.get_style_context().add_class("dim-label")
        prev_inner.pack_start(self._lbl_prev_tipo, False, False, 0)

        self._flow_prev_ports = Gtk.FlowBox()
        self._flow_prev_ports.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow_prev_ports.set_max_children_per_line(3)
        self._flow_prev_ports.set_row_spacing(4)
        self._flow_prev_ports.set_column_spacing(4)
        prev_inner.pack_start(self._flow_prev_ports, False, False, 0)

        self._lbl_prev_resumen = Gtk.Label()
        self._lbl_prev_resumen.get_style_context().add_class("dim-label")
        self._lbl_prev_resumen.set_margin_top(4)
        prev_inner.pack_start(self._lbl_prev_resumen, False, False, 0)

        # Resumen de lo que se creará
        sep_sum = Gtk.Separator(); right_box.pack_start(sep_sum, False, False, 0)

        lbl_sum = Gtk.Label()
        lbl_sum.set_markup("<b>" + _("Resumen") + "</b>")
        lbl_sum.set_xalign(0)
        right_box.pack_start(lbl_sum, False, False, 0)

        self._lbl_sum_detail = Gtk.Label()
        self._lbl_sum_detail.set_xalign(0)
        self._lbl_sum_detail.set_line_wrap(True)
        self._lbl_sum_detail.get_style_context().add_class("dim-label")
        right_box.pack_start(self._lbl_sum_detail, False, False, 0)

        self.show_all()

        # Cargar datos iniciales
        Modelo.asegurar_tabla_plantillas()
        self._todos_tipos_con = Modelo.devolver_tipos_conectores()
        self._poblar_tipos("")

    # ── Tipos de equipo ──────────────────────────────────────────────────────

    def _poblar_tipos(self, filtro):
        self._store_tipos.clear()
        todos = Modelo.devolver_todos_los_tipos()
        fl = filtro.lower()
        for r in todos:
            if not fl or fl in s(r[1]).lower():
                self._store_tipos.append([s(r[0]), s(r[1])])

    def _on_tipo_search(self, entry):
        self._poblar_tipos(entry.get_text())

    def _on_tipo_seleccionado(self, tv, path, col):
        it = self._store_tipos.get_iter(path)
        self.id_tipo = self._store_tipos.get_value(it, 0)
        nombre_tipo  = self._store_tipos.get_value(it, 1)
        self._lbl_tipo_sel.set_markup(
            f"Tipo seleccionado: <b>{nombre_tipo}</b>"
        )
        self._cargar_plantilla(self.id_tipo)
        self._actualizar_preview()

    def _crear_tipo(self, btn):
        dlg = DialogoNombre(_("Nuevo Tipo de Equipo"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_tipo(dlg.valor)
            self._poblar_tipos(self.e_tipo_search.get_text())
            mostrar_info(self, f"Tipo creado: {dlg.valor}")
        dlg.destroy()

    # ── Plantilla de conectores ───────────────────────────────────────────────

    def _cargar_plantilla(self, id_tipo):
        """Carga la plantilla del tipo y construye las filas de spinners."""
        self._conectores_activos = {}
        plantilla = Modelo.devolver_plantillas_conectores(id_tipo)

        # Si no hay plantilla, mostrar todos los tipos con cantidad 0
        if not plantilla:
            filas = [(s(r[0]), s(r[1]), "IN",    0) for r in self._todos_tipos_con] +                     [(s(r[0]), s(r[1]), "OUT",   0) for r in self._todos_tipos_con]
        else:
            # Incluir plantilla + tipos restantes con cantidad 0
            en_plantilla = {(s(r[0]), s(r[2])) for r in plantilla}
            filas = [(s(r[0]), s(r[1]), s(r[2]), int(r[3])) for r in plantilla]
            for r in self._todos_tipos_con:
                for dir_ in ("IN", "OUT"):
                    if (s(r[0]), dir_) not in en_plantilla:
                        filas.append((s(r[0]), s(r[1]), dir_, 0))

        # Inicializar estado activo desde plantilla
        for id_tc, nombre_tc, dir_, qty in filas:
            if qty > 0:
                self._conectores_activos[(id_tc, dir_)] = qty

        self._reconstruir_filas_conectores(filas)

    def _reconstruir_filas_conectores(self, filas):
        """Limpia y reconstruye el panel de conectores."""
        for ch in self._con_box.get_children():
            self._con_box.remove(ch)

        # Ordenar: primero los que tienen cantidad > 0, luego los demás
        filas_sorted = sorted(filas, key=lambda r: (r[3] == 0, r[1], r[2]))

        for id_tc, nombre_tc, dir_, qty in filas_sorted:
            row = self._crear_fila_conector(id_tc, nombre_tc, dir_, qty)
            self._con_box.pack_start(row, False, False, 0)

        self._con_box.show_all()
        self._actualizar_preview()

    def _crear_fila_conector(self, id_tc, nombre_tc, dir_, qty):
        """Crea una fila con nombre del conector, dirección y spinner."""
        hb = Gtk.Box(spacing=6)
        hb.set_margin_start(2); hb.set_margin_end(2)

        # Indicador de dirección (color)
        color = self._COL_IN if dir_ == "IN" else self._COL_OUT
        lbl_dir = Gtk.Label()
        lbl_dir.set_markup(
            f"<span foreground='{color}'><b>{'←' if dir_=='IN' else '→'}</b></span>"
        )
        lbl_dir.set_width_chars(2)
        hb.pack_start(lbl_dir, False, False, 0)

        # Nombre del tipo de conector
        lbl_n = Gtk.Label(label=f"{nombre_tc}")
        lbl_n.set_xalign(0)
        lbl_n.set_hexpand(True)
        if qty == 0:
            lbl_n.get_style_context().add_class("dim-label")
        hb.pack_start(lbl_n, True, True, 0)

        # Dirección texto
        lbl_d = Gtk.Label(label=dir_)
        lbl_d.set_width_chars(4)
        lbl_d.set_xalign(0.5)
        hb.pack_start(lbl_d, False, False, 0)

        # Spinner de cantidad
        adj = Gtk.Adjustment(value=qty, lower=0, upper=99, step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        spin.set_width_chars(4)
        spin.connect("value-changed",
                     self._on_spin_changed, id_tc, dir_, lbl_n)
        hb.pack_start(spin, False, False, 0)

        return hb

    def _on_spin_changed(self, spin, id_tc, dir_, lbl_n):
        qty = int(spin.get_value())
        if qty > 0:
            self._conectores_activos[(id_tc, dir_)] = qty
            lbl_n.get_style_context().remove_class("dim-label")
        else:
            self._conectores_activos.pop((id_tc, dir_), None)
            lbl_n.get_style_context().add_class("dim-label")
        self._actualizar_preview()

    def _agregar_conector_manual(self, btn):
        """Permite agregar un tipo de conector no listado en la plantilla."""
        from cabledoc import TiposConectorListado
        from equipos_ui import _DialogoDireccionConector
        dlg = TiposConectorListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_tc    = dlg.resultado_id
            nombre   = dlg.resultado_nombre
            # Preguntar dirección
            dlg2 = _DialogoDireccionConector(parent=self)
            if dlg2.run() == Gtk.ResponseType.OK:
                dir_ = dlg2.direccion
                # Verificar que no existe ya
                if (id_tc, dir_) not in {(id_, d)
                        for id_, d in self._conectores_activos}:
                    fila = self._crear_fila_conector(id_tc, nombre, dir_, 1)
                    self._con_box.pack_start(fila, False, False, 0)
                    self._con_box.show_all()
                    self._conectores_activos[(id_tc, dir_)] = 1
                    self._actualizar_preview()
            dlg2.destroy()
        dlg.destroy()

    # ── Preview ───────────────────────────────────────────────────────────────

    def _actualizar_preview(self, *a):
        nombre = self.e_nombre.get_text().strip() or "—"
        self._lbl_prev_nombre.set_markup(f"<b>{nombre}</b>")

        tipo_txt = self._lbl_tipo_sel.get_text().replace(
            "Tipo seleccionado: ", "").strip() or "tipo no seleccionado"
        marca = self.e_marca.get_text().strip()
        sub = tipo_txt + (f" · {marca}" if marca else "")
        self._lbl_prev_tipo.set_markup(f"<i>{sub}</i>")

        # Chips de puertos
        for ch in self._flow_prev_ports.get_children():
            self._flow_prev_ports.remove(ch)

        n_in = 0; n_out = 0
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc),
                "?"
            )
            color = self._COL_IN if dir_ == "IN" else self._COL_OUT
            signo = "←" if dir_ == "IN" else "→"
            lbl = Gtk.Label()
            lbl.set_markup(
                f"<span foreground='{color}'>{signo}</span> "
                f"{nombre_tc}"
                + (f" ×{qty}" if qty > 1 else "")
            )
            lbl.set_margin_start(6); lbl.set_margin_end(6)
            lbl.set_margin_top(3);   lbl.set_margin_bottom(3)
            frame_chip = Gtk.Frame()
            frame_chip.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            frame_chip.add(lbl)
            self._flow_prev_ports.add(frame_chip)
            if dir_ == "IN":
                n_in += qty
            else:
                n_out += qty

        self._flow_prev_ports.show_all()

        total_con = sum(self._conectores_activos.values())
        self._lbl_prev_resumen.set_markup(
            f"<small>{total_con} conectores · {n_in} entradas · {n_out} salidas</small>"
        )
        self._lbl_sum_detail.set_markup(
            f"Se crear\u00e1:\n  \u2022 1 equipo: <b>{nombre}</b>\n"
            f"  \u2022 {total_con} conectores ({n_in} IN, {n_out} OUT)\n"
            "  \u2022 Imagen y coordenadas: completar luego"
        )

    # ── Selectores ────────────────────────────────────────────────────────────

    def _sel_marca(self, btn):
        from cabledoc import MarcasListado
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_marca = dlg.resultado_id
            self.e_marca.set_text(dlg.resultado_nombre)
        dlg.destroy()

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _sel_picon(self, btn):
        os.makedirs(PICON_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(PICON_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filtro.add_pattern(pat)
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(PICON_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la foto: {e}")
                self.e_picon.set_text(fname)
        dialog.destroy()

    def guardar(self):
        """
        Crea el equipo y todos sus conectores.
        Retorna el id_equipo creado, o None si falla validación.
        """
        nombre = self.e_nombre.get_text().strip()
        if not nombre:
            mostrar_error(self, "El nombre del equipo es obligatorio.")
            return None

        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo = self.id_tipo or None,
            id_marca       = self.id_marca or None,
            num_inventario = self.e_inventario.get_text().strip() or None,
            num_serie      = self.e_serie.get_text().strip() or None,
            modelo         = self.e_modelo.get_text().strip() or None,
            nombre         = nombre,
            id_imagen      = None,
            x              = None,
            y              = None,
            picon          = self.e_picon.get_text().strip() or None,
        )

        # Crear conectores
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc), "?"
            )
            for i in range(1, qty + 1):
                sufijo = f" {i:02d}" if qty > 1 else ""
                if nombre_tc.strip().upper() == dir_.strip().upper():
                    nombre_con = f"{dir_}{sufijo}"
                else:
                    nombre_con = f"{dir_} {nombre_tc}{sufijo}"
                Modelo.agregar_conector(
                    nombre           = nombre_con,
                    id_equipo        = id_equipo,
                    id_tipo_conector = id_tc or None,
                    id_imagen        = None,
                    x                = None,
                    y                = None,
                )

        # Guardar plantilla para este tipo
        if self.id_tipo and self._conectores_activos:
            for (id_tc, dir_), qty in self._conectores_activos.items():
                Modelo.guardar_plantilla_conector(
                    self.id_tipo, id_tc, dir_, qty
                )

        return id_equipo

    def _limpiar_para_duplicar(self):
        """Limpia solo los campos que cambian entre unidades del mismo equipo."""
        self.e_nombre.set_text("")
        self.e_inventario.set_text("")
        self.e_serie.set_text("")
        self.e_nombre.grab_focus()

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp == Gtk.ResponseType.APPLY:
                # Guardar y duplicar
                id_eq = self.guardar()
                if id_eq is not None:
                    mostrar_info(self,
                        f"Equipo guardado (ID {id_eq}).\n"
                        "Completá el siguiente equipo del mismo tipo.")
                    self._limpiar_para_duplicar()
                    continue   # volver al loop
            elif resp == Gtk.ResponseType.OK:
                id_eq = self.guardar()
                if id_eq is None:
                    continue   # validación falló, volver al loop
                break
            else:
                break
        self.destroy()


