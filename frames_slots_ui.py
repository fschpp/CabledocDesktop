#!/usr/bin/env python3
"""
frames_slots_ui.py — CableDoc GTK3

Dominio Frames / Slots (catálogo e instancia), extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 7, parte 2/2).

Contiene:
  - CatalogoFramesListado, _DialogoCatalogoFrame (catálogo de moldes de frame)
  - _SlotsCatalogoListado, _DialogoSlotCatalogo (slots del molde)
  - _DialogoInstanciarCatalogoFrame (instanciar frame real desde molde)
  - FramesListado, _DialogoFrame (frames reales)
  - SlotsListado, _DialogoSlot (slots del frame real)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos nueve nombres sin cambios.

Separado de `racks_salas_ui.py` (Racks, Posición en rack, Salas) porque
juntos superaban las ~900 líneas objetivo del plan (~1.275 líneas → 2
archivos), mismo criterio de tamaño usado en las Entregas 3 y 5. Este es
el bloque contiguo completo "Catálogo de frames" + "Frames" + "Slots" del
original (sin las sorpresas de layout no contiguo de la Entrega 3).

Referencias a clases/funciones de otros dominios que todavía viven en
`cabledoc.py` (MarcasListado, ImagenesListado, EquiposListado,
_escribir_json_comprimido, _leer_json_generico, _sel_imagen_desde_abm) se
resuelven con import diferido dentro del método que las usa, siguiendo el
mismo patrón ya usado en `catalogo_equipos_ui.py` (Entrega 5) para estos
mismos tres helpers de JSON/imagen.
"""

import os
import shutil

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf

from modelo import Modelo, PICON_DIR

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
    confirmar,
    VentanaListado,
    DialogoNombre,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
    _pack_ultima_edicion,
)
from pantallas_avanzadas import (
    abrir_coords_imagen,
    abrir_vista_rack,
    abrir_vista_frame_slots,
    abrir_editor_masivo_slots,
    abrir_editor_masivo_slots_catalogo,
)


# ─── Catálogo de frames (moldes) ───────────────────────────────────────────────

class CatalogoFramesListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Catálogo de Frames"),
            [_("ID"), _("Molde"), _("Marca"), _("Modelo"), _("Slots")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                ("📦 Instanciar…", self._instanciar),
                ("⬆ Exportar…", self._exportar),
                ("⬇ Importar…", self._importar),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_catalogos_frame())

    def nuevo(self):
        dlg = _DialogoCatalogoFrame(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoCatalogoFrame(id_frame_catalogo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_catalogo_frame(id_)

    def _instanciar(self, *a):
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un molde del catálogo.")
            return
        dlg = _DialogoInstanciarCatalogoFrame(id_frame_catalogo=f[0],
                                              nombre_molde=f[1], parent=self)
        dlg.run_and_destroy()

    def _exportar(self, *a):
        """Exporta el molde seleccionado o todo el catálogo de frames a un
        .zip portable que contiene un único JSON adentro (marca por nombre,
        imágenes/manual/picon embebidos en base64 dentro del JSON)."""
        fila = self._fila()
        ids = [fila[0]] if fila else None
        if ids and not confirmar(
                self, f"¿Exportar solo el molde seleccionado «{fila[1]}»?\n\n"
                     "(Cancelá para exportar TODO el catálogo de frames)"):
            ids = None
        dlg = Gtk.FileChooserDialog(
            title=_("Exportar catálogo de frames"), parent=self,
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Guardar"), Gtk.ResponseType.OK)
        dlg.set_current_name("catalogo_frames.zip")
        dlg.set_do_overwrite_confirmation(True)
        filt = Gtk.FileFilter(); filt.set_name("ZIP"); filt.add_pattern("*.zip")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if not ruta.lower().endswith(".zip"):
                ruta += ".zip"
            try:
                data = Modelo.exportar_catalogo_frames(ids)
                from cabledoc import _escribir_json_comprimido
                _escribir_json_comprimido(ruta, "catalogo_frames.json", data)
                mostrar_info(self,
                    f"Catálogo exportado: {len(data['moldes'])} molde(s) → {ruta}")
            except Exception as e:
                mostrar_error(self, f"Error al exportar:\n{e}")
        dlg.destroy()

    def _importar(self, *a):
        """Importa moldes de frame desde un .zip (o un .json plano de una
        versión vieja) exportado por esta misma función, posiblemente de
        otra instalación de CableDoc."""
        dlg = Gtk.FileChooserDialog(
            title=_("Importar catálogo de frames"), parent=self,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Abrir"), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name("ZIP / JSON")
        filt.add_pattern("*.zip"); filt.add_pattern("*.json")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            try:
                from cabledoc import _leer_json_generico
                data = _leer_json_generico(ruta)
                if not isinstance(data, dict) or data.get("tipo") != "cabledoc_catalogo_frames":
                    mostrar_error(self, "El archivo no es un catálogo de frames válido.")
                else:
                    n_m, n_s = Modelo.importar_catalogo_frames(data)
                    mostrar_info(self, f"Importados {n_m} molde(s) con {n_s} slot(s).")
                    self.cargar_datos()
            except Exception as e:
                mostrar_error(self, f"Error al importar:\n{e}")
        dlg.destroy()


class _DialogoCatalogoFrame(Gtk.Dialog):
    def __init__(self, id_frame_catalogo=None, parent=None):
        titulo = _("Editar Molde de Frame") if id_frame_catalogo else _("Nuevo Molde de Frame")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(540, 520)
        self.id_frame_catalogo = id_frame_catalogo
        self.id_marca = ""
        self.id_imagen = ""

        ca = self.get_content_area()
        g = _grid()
        _lbl_entry(g, _("Nombre molde:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Ej: PPV 16x16 Canare")
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(
            g, 1, Modelo.devolver_todas_las_marcas(), "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Modelo:"), 2)
        self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Imagen:"), 3)
        self.e_imagen = _entry_btn(g, 3, "…", self._sel_imagen)
        _lbl_entry(g, _("Manual (PDF):"), 4)
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 4, 1, 1)
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 4, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 5)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 5, 1, 1)
        btn_sel_picon = Gtk.Button(label=_("…"))
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 5, 1, 1)
        btn_quitar_picon = Gtk.Button(label=_("✖"))
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 5, 1, 1)
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(120, 120)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 6, 1, 1)
        ca.pack_start(g, False, False, 0)

        hbox_buttons = Gtk.Box(spacing=6)
        hbox_buttons.set_margin_start(12); hbox_buttons.set_margin_end(12)
        hbox_buttons.set_margin_bottom(6)
        if id_frame_catalogo:
            btn_slots = Gtk.Button(label=_("🗂️ Slots del molde"))
            btn_slots.connect("clicked", self._ver_slots)
            hbox_buttons.pack_start(btn_slots, False, False, 0)

            btn_masivo = Gtk.Button(label=_("📐 Edición masiva de slots"))
            btn_masivo.connect("clicked", self._editar_slots_masivo)
            hbox_buttons.pack_start(btn_masivo, False, False, 0)
        ca.pack_start(hbox_buttons, False, False, 0)

        if id_frame_catalogo:
            rows = Modelo.devolver_catalogo_frame(id_frame_catalogo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_marca = s(r[2]); _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[4]))
                self.id_imagen = s(r[5])
                self.e_imagen.set_text(s(r[6]))
                self.e_manual.set_text(s(r[7]))
                if len(r) > 9 and r[9]:
                    self.e_picon.set_text(s(r[9]))

        self._actualizar_picon_preview()
        self.show_all()

    def _sel_marca_dropdown(self, btn):
        from cabledoc import MarcasListado
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_marca, Modelo.devolver_todas_las_marcas())
            _set_combo_id(self.c_marca, dlg.resultado_id)
        dlg.destroy()

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_manual(self, btn):
        from modelo import MANUALES_DIR
        os.makedirs(MANUALES_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar Manual PDF"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(MANUALES_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Archivos PDF"))
        filtro.add_pattern("*.pdf"); filtro.add_pattern("*.PDF")
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(MANUALES_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar: {e}")
                self.e_manual.set_text(fname)
        dialog.destroy()

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
                self._actualizar_picon_preview()
        dialog.destroy()

    def _quitar_picon(self, btn):
        self.e_picon.set_text("")
        self._actualizar_picon_preview()

    def _actualizar_picon_preview(self):
        filename = self.e_picon.get_text().strip()
        if filename:
            ruta = os.path.join(PICON_DIR, filename)
            if os.path.isfile(ruta):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, 120, 120, True)
                    self.img_picon.set_from_pixbuf(pixbuf)
                    return
                except Exception:
                    pass
        self.img_picon.clear()

    def _ver_slots(self, btn):
        dlg = _SlotsCatalogoListado(self.id_frame_catalogo, parent=self)
        dlg.run(); dlg.destroy()

    def _editar_slots_masivo(self, btn):
        if not self.id_imagen:
            mostrar_error(self, "Asigná una imagen al molde antes de "
                                "usar la edición masiva de slots.")
            return
        from cabledoc import _sel_imagen_desde_abm
        abrir_editor_masivo_slots_catalogo(
            id_frame_catalogo=self.id_frame_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_marca = _get_combo_id(self.c_marca)
            nombre = self.e_nombre.get_text().strip()
            modelo = self.e_modelo.get_text().strip()
            manual = self.e_manual.get_text().strip() or None
            picon = self.e_picon.get_text().strip() or None
            if self.id_frame_catalogo:
                Modelo.modificacion_catalogo_frame(
                    self.id_frame_catalogo, nombre, id_marca or None,
                    modelo, self.id_imagen or None, manual, picon=picon)
            else:
                nuevo_id = Modelo.alta_catalogo_frame(
                    nombre, id_marca or None, modelo, self.id_imagen or None, manual,
                    picon=picon)
                self.id_frame_catalogo = nuevo_id
        self.destroy()


class _SlotsCatalogoListado(VentanaListado):
    def __init__(self, id_frame_catalogo, parent=None):
        super().__init__(_("Slots del molde"),
                         [_("ID"), _("Slot"), _("X"), _("Y"), _("Ancho"), _("Alto")],
                         parent=parent,
                         botones_extra=[
                             ("📐 Edición masiva de slots", self._editar_slots_masivo),
                         ])
        self.id_frame_catalogo = id_frame_catalogo
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_slots_de_catalogo_frame(self.id_frame_catalogo))

    def nuevo(self):
        dlg = _DialogoSlotCatalogo(id_frame_catalogo=self.id_frame_catalogo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoSlotCatalogo(id_slot_catalogo=id_,
                                   id_frame_catalogo=self.id_frame_catalogo, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_slot_catalogo(id_)

    def _editar_slots_masivo(self, btn):
        from cabledoc import _sel_imagen_desde_abm
        abrir_editor_masivo_slots_catalogo(
            id_frame_catalogo=self.id_frame_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)
        self.cargar_datos()


class _DialogoSlotCatalogo(Gtk.Dialog):
    def __init__(self, id_slot_catalogo=None, id_frame_catalogo=None, parent=None):
        titulo = _("Editar Slot Molde") if id_slot_catalogo else _("Nuevo Slot Molde")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(380, 280)
        self.id_slot_catalogo = id_slot_catalogo
        self.id_frame_catalogo = id_frame_catalogo

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Rect X:"), 1); self.e_x = _entry(g, 1)
        _lbl_entry(g, _("Rect Y:"), 2); self.e_y = _entry(g, 2)
        _lbl_entry(g, _("Ancho px:"), 3); self.e_ancho = _entry(g, 3)
        _lbl_entry(g, _("Alto px:"), 4); self.e_alto = _entry(g, 4)
        self.get_content_area().add(g)

        btn_coords = Gtk.Button(label=_("📍 Elegir rectángulo en imagen"))
        btn_coords.connect("clicked", self._sel_rect_imagen)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_slot_catalogo:
            rows = Modelo._query(
                "SELECT id_slot_catalogo, nombre, rectangulo_x_en_imagen, "
                "rectangulo_y_en_imagen, rectangulo_ancho_pixeles, "
                "rectangulo_alto_pixeles FROM slot_catalogo WHERE id_slot_catalogo=?",
                (id_slot_catalogo,))
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                x_px, y_px, ancho_px, alto_px = Modelo._px_rect_o_crudo(
                    Modelo._path_imagen(self._id_imagen_del_molde()),
                    r[2], r[3], r[4], r[5])
                self.e_x.set_text(s(x_px)); self.e_y.set_text(s(y_px))
                self.e_ancho.set_text(s(ancho_px)); self.e_alto.set_text(s(alto_px))

        self.show_all()

    def _id_imagen_del_molde(self):
        """Obtiene el id_imagen del frame_catalogo padre (la imagen sobre la
        que se dibujan los rectángulos de los slots del molde)."""
        rows = Modelo.devolver_catalogo_frame(self.id_frame_catalogo)
        if rows and rows[0][5]:
            return rows[0][5]
        return None

    def _sel_rect_imagen(self, btn):
        id_img = self._id_imagen_del_molde()
        if not id_img:
            mostrar_error(self, "El molde no tiene una imagen asignada.\n"
                                "Asigná una imagen al molde de frame antes de "
                                "elegir el rectángulo del slot.")
            return
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=False,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            ancho=self.e_ancho.get_text(), alto=self.e_alto.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])
            self.e_ancho.set_text(res["ancho"])
            self.e_alto.set_text(res["alto"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            x = self.e_x.get_text().strip(); y = self.e_y.get_text().strip()
            ancho = self.e_ancho.get_text().strip(); alto = self.e_alto.get_text().strip()
            if self.id_slot_catalogo:
                Modelo.modificacion_slot_catalogo(
                    self.id_slot_catalogo, nombre, x, y, ancho, alto)
            else:
                Modelo.agregar_slot_catalogo(
                    self.id_frame_catalogo, nombre, x, y, ancho, alto)
        self.destroy()


class _DialogoInstanciarCatalogoFrame(Gtk.Dialog):
    """Instancia un frame real desde un molde: solo pide nombre e inventario.
    Todo lo demás (marca/modelo/imagen/manual/slots) se copia del molde."""

    def __init__(self, id_frame_catalogo, nombre_molde="", parent=None):
        super().__init__(title=_("Instanciar frame desde catálogo"),
                         transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📦 " + _("Crear frame"), Gtk.ResponseType.OK)
        self.set_default_size(400, 220)
        self.id_frame_catalogo = id_frame_catalogo
        self.id_frame_creado = None

        ca = self.get_content_area()
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>Molde:</b> {nombre_molde}")
        lbl.set_margin_start(12); lbl.set_margin_top(10)
        ca.pack_start(lbl, False, False, 0)

        g = _grid()
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del frame real (requerido)")
        _lbl_entry(g, _("Inventario:"), 1)
        self.e_inventario = _entry(g, 1)
        ca.pack_start(g, False, False, 0)

        n_slots = len(Modelo.devolver_slots_de_catalogo_frame(id_frame_catalogo))
        lbl_n = Gtk.Label(xalign=0)
        lbl_n.set_markup(f"<small><i>Se copiarán {n_slots} slots vacíos (sin equipo).</i></small>")
        lbl_n.set_margin_start(12)
        ca.pack_start(lbl_n, False, False, 4)

        self.show_all()

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp != Gtk.ResponseType.OK:
                break
            nombre = self.e_nombre.get_text().strip()
            if not nombre:
                mostrar_error(self, "El nombre del frame es obligatorio.")
                continue
            self.id_frame_creado = Modelo.instanciar_frame_desde_catalogo(
                self.id_frame_catalogo, nombre,
                self.e_inventario.get_text().strip() or None,
            )
            mostrar_info(self, f"Frame «{nombre}» creado (ID {self.id_frame_creado}).")
            break
        self.destroy()


# ─── Frames ───────────────────────────────────────────────────────────────────

class FramesListado(VentanaListado):
    # filtro_pendiente: None | 'sin_slots' | 'sin_imagen' | 'sin_rect'
    def __init__(self, parent=None, modo_seleccion=False, filtro_pendiente=None):
        self._filtro_pendiente = filtro_pendiente
        self._ids_resaltar = set()
        titulo = _("Frames")
        if filtro_pendiente == "sin_slots":
            titulo = _("Frames — Sin slots")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Frames — Sin imagen")
        elif filtro_pendiente == "sin_rect":
            titulo = _("Frames — Sin slots en imagen")
        super().__init__(titulo,
                         [_("ID"), _("Nombre"), _("Marca"), _("Modelo"), _("Inventario")],
                         parent=parent, modo_seleccion=modo_seleccion,
                         botones_extra=[
                             ("🖼 Ver slots en imagen", self._ver_slots_imagen),
                             ("📐 Edición masiva de slots", self._editar_slots_masivo),
                             ("📦 Desde catálogo", self._desde_catalogo),
                         ])
        self.cargar_datos()

    def _desde_catalogo(self, *a):
        sel = CatalogoFramesListado(parent=self, modo_seleccion=True)
        if sel.run() == Gtk.ResponseType.OK:
            id_cat = sel.resultado_id
            nombre_molde = sel.resultado_nombre
            sel.destroy()
            dlg = _DialogoInstanciarCatalogoFrame(
                id_frame_catalogo=id_cat, nombre_molde=nombre_molde, parent=self)
            dlg.run_and_destroy()
            self.cargar_datos()
        else:
            sel.destroy()

    def _ver_slots_imagen(self, btn):
        fila = self._fila()
        if fila:
            abrir_vista_frame_slots(id_frame=fila[0], parent=self)

    def _editar_slots_masivo(self, btn):
        fila = self._fila()
        if fila:
            from cabledoc import _sel_imagen_desde_abm
            abrir_editor_masivo_slots(
                id_frame=fila[0], parent=self,
                fn_sel_imagen=_sel_imagen_desde_abm)
            self.cargar_datos()

    def cargar_datos(self):
        self._ids_resaltar = set()
        color = "#c8a800"
        if self._filtro_pendiente == "sin_slots":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE "
                "NOT EXISTS (SELECT 1 FROM slot WHERE id_frame=frame.id_frame)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_rect":
            rows = Modelo._query(
                "SELECT f.id_frame FROM frame f WHERE "
                "EXISTS (SELECT 1 FROM slot WHERE id_frame=f.id_frame) "
                "AND NOT EXISTS (SELECT 1 FROM slot s WHERE s.id_frame=f.id_frame "
                "AND s.rectangulo_x_en_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        todos = Modelo.devolver_todos_los_frames()
        data = [[r[0], r[1], r[2], r[3], r[7]] for r in todos]
        self._poblar(data, ids_resaltar=self._ids_resaltar, color_resaltar=color)

    def _filtrar(self, model, iter_, data):
        txt = self.entry_filtro.get_text().lower()
        n = len(self.columnas)
        if txt:
            if not any(txt in s(model.get_value(iter_, i)).lower() for i in range(n)):
                return False
        if self._filtro_pendiente and self._ids_resaltar:
            fid = s(model.get_value(iter_, 0))
            return fid in self._ids_resaltar
        return True

    def nuevo(self):
        dlg = _DialogoFrame(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoFrame(id_frame=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_frame(id_)


class _DialogoFrame(Gtk.Dialog):
    def __init__(self, id_frame=None, parent=None):
        titulo = _("Editar Frame") if id_frame else _("Nuevo Frame")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                                destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 300)
        self.id_frame = id_frame
        self.id_marca = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(g, 1, Modelo.devolver_todas_las_marcas())
        _lbl_entry(g, _("Modelo:"), 2); self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Inventario:"), 3); self.e_inv = _entry(g, 3)
        _lbl_entry(g, _("Imagen:"), 4)
        self.e_imagen = _entry_btn(g, 4, "…", self._sel_imagen)
        self.get_content_area().add(g)

        if id_frame:
            btn_slots = Gtk.Button(label=_("🗂️ Ver Slots"))
            btn_slots.connect("clicked", self._ver_slots)
            self.get_content_area().pack_start(btn_slots, False, False, 0)

            btn_vista = Gtk.Button(label=_("🖼 Ver slots en imagen"))
            btn_vista.connect("clicked", self._ver_slots_imagen)
            self.get_content_area().pack_start(btn_vista, False, False, 0)

            btn_rack = Gtk.Button(label=_("🗄 Rack del frame"))
            btn_rack.set_tooltip_text(
                _("Buscar en qué rack está montado este frame y abrir su vista gráfica"))
            btn_rack.connect("clicked", self._ver_rack)
            self.get_content_area().pack_start(btn_rack, False, False, 0)

            btn_template = Gtk.Button(label=_("🧬 Frame a template"))
            btn_template.set_tooltip_text(
                _("Crear un molde de catálogo reutilizable a partir de "
                  "este frame y sus slots (sin inventario)"))
            btn_template.connect("clicked", self._frame_a_template)
            self.get_content_area().pack_start(btn_template, False, False, 0)

        if id_frame:
            rows = Modelo.devolver_frame(id_frame)
            if rows:
                r = rows[0]
                # id, nombre, marca, modelo, id_marca, imagen_path, id_imagen, inventario
                self.e_nombre.set_text(s(r[1]))
                self.id_marca = s(r[4])
                _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[3]))
                self.e_imagen.set_text(s(r[5]))
                self.id_imagen = s(r[6])
                self.e_inv.set_text(s(r[7]))

        _pack_ultima_edicion(self, "frame", "id_frame", id_frame)
        self.show_all()

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _ver_slots(self, btn):
        dlg = SlotsListado(id_frame=self.id_frame, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_slots_imagen(self, btn):
        abrir_vista_frame_slots(id_frame=self.id_frame, parent=self)

    def _ver_rack(self, btn):
        """Busca el rack donde está montado este frame y abre su vista
        gráfica. Si no está rackeado, muestra un diálogo avisando."""
        filas = Modelo.devolver_rack_de_frame(self.id_frame)
        if not filas:
            mostrar_info(self, _("Equipo no rackeado"))
            return
        id_rack = filas[0][0]
        abrir_vista_rack(id_rack=id_rack, parent=self)

    def _frame_a_template(self, btn):
        """Crea un molde de catálogo (frame_catalogo) a partir de este
        frame: copia marca, modelo e imagen, más sus slots (nombre y
        rectángulo x/y/ancho/alto) vacíos en el molde. NO copia el
        inventario, que es propio de esta instancia física."""
        if not self.id_frame:
            return
        nombre_actual = self.e_nombre.get_text().strip() or "Frame"
        dlg = DialogoNombre(
            _("Frame a template"), etiqueta=_("Nombre del molde:"),
            valor=f"{nombre_actual} (molde)", parent=self)
        ok = dlg.run() == Gtk.ResponseType.OK
        valor = dlg.valor
        dlg.destroy()
        if not ok or not valor:
            return
        resultado = Modelo.crear_catalogo_desde_frame(self.id_frame, valor)
        if resultado:
            id_cat, n_slots = resultado
            mostrar_info(self,
                f"Molde «{valor}» creado (ID {id_cat}) con {n_slots} slot(s).\n\n"
                "Podés verlo/editarlo en Frames → 📦 Catálogo de Frames.")
        else:
            mostrar_error(self, "No se pudo crear el molde.")

    def _ver_editor_masivo_slots(self, btn):
        from cabledoc import _sel_imagen_desde_abm
        abrir_editor_masivo_slots(
            id_frame=self.id_frame, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            self.id_marca = _get_combo_id(self.c_marca)
            args = (
                self.e_nombre.get_text(),
                self.e_inv.get_text(),
                self.id_marca or None,
                self.id_imagen or None,
                self.e_modelo.get_text()
            )
            if self.id_frame:
                Modelo.modificar_frame(self.id_frame, *args)
            else:
                Modelo.agregar_frame(*args)
        self.destroy()


# ─── Slots ────────────────────────────────────────────────────────────────────

class SlotsListado(VentanaListado):
    def __init__(self, id_frame, parent=None):
        super().__init__(_("Slots"), [_("ID"), _("Slot"), _("Módulo/Equipo")],
                         parent=parent)
        self.id_frame = id_frame
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_slots_del_frame(self.id_frame))

    def nuevo(self):
        dlg = _DialogoSlot(id_frame=self.id_frame, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoSlot(id_slot=id_, id_frame=self.id_frame, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_slot(id_)


class _DialogoSlot(Gtk.Dialog):
    def __init__(self, id_slot=None, id_frame=None, parent=None):
        titulo = _("Editar Slot") if id_slot else _("Nuevo Slot")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 340)
        self.id_slot = id_slot
        self.id_frame = id_frame or ""
        self.id_equipo = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Equipo:"), 1)
        self.e_equipo = _entry_btn(g, 1, "…", self._sel_equipo)
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Rect X:"), 3); self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Rect Y:"), 4); self.e_y = _entry(g, 4)
        _lbl_entry(g, _("Ancho px:"), 5); self.e_ancho = _entry(g, 5)
        _lbl_entry(g, _("Alto px:"), 6); self.e_alto = _entry(g, 6)
        self.get_content_area().add(g)

        # Botón selector de rectángulo en imagen (slots usan ancho+alto)
        btn_coords = Gtk.Button(label=_("📍 Elegir rectángulo en imagen"))
        btn_coords.connect("clicked", self._sel_rect_imagen)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_slot:
            rows = Modelo.devolver_slot(id_slot)
            if rows:
                r = rows[0]
                # id_slot, slot_nombre, id_equipo, nombre_equipo,
                # path_imagen, id_imagen, x, y, alto, ancho, id_frame
                self.e_nombre.set_text(s(r[1]))
                self.id_equipo = s(r[2])
                self.e_equipo.set_text(s(r[3]))
                self.e_imagen.set_text(s(r[4]))
                self.id_imagen = s(r[5])
                self.e_x.set_text(s(r[6]))
                self.e_y.set_text(s(r[7]))
                self.e_alto.set_text(s(r[8]))
                self.e_ancho.set_text(s(r[9]))
                self.id_frame = s(r[10])

        _pack_ultima_edicion(self, "slot", "id_slot", id_slot)
        self.show_all()

    def _sel_equipo(self, btn):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.e_equipo.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_rect_imagen(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=False,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            ancho=self.e_ancho.get_text(), alto=self.e_alto.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])
            self.e_ancho.set_text(res["ancho"])
            self.e_alto.set_text(res["alto"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            args = (
                self.e_nombre.get_text(),
                self.id_equipo or None,
                self.id_frame or None,
                self.id_imagen or None,
                self.e_x.get_text(), self.e_y.get_text(),
                self.e_ancho.get_text(), self.e_alto.get_text()
            )
            if self.id_slot:
                Modelo.modificar_slot(self.id_slot, *args)
            else:
                Modelo.agregar_slot(*args)
        self.destroy()

