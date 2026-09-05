#!/usr/bin/env python3
"""
catalogo_equipos_ui.py — CableDoc GTK3

Dominio Catálogo de equipos (moldes), extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 5).

Contiene:
  - CatalogoEquiposListado (listado de moldes de equipo)
  - _DialogoConflictosImportacion (resolución de conflictos al importar)
  - _DialogoCatalogoEquipo (editor de molde: datos generales + conectores)
  - _ConectoresCatalogoListado (listado de conectores-molde de un molde)
  - _DialogoConectorCatalogo (ficha de conector-molde)
  - _DialogoInstanciarCatalogo (crear equipo real a partir de un molde)
  - _DialogoDuplicarMolde (duplicar un molde existente)
  - _DialogoRenombrarConectoresCatalogo (renombrado masivo de conectores
    de un molde; sumada en la Entrega 10 — ver nota más abajo)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos nombres sin cambios.

Separado de `catalogo_equipos_alta_rapida_ui.py` (_DialogoAltaRapidaCatalogo)
porque juntos superaban las ~900 líneas objetivo del plan (~1.200 líneas → 2
archivos), siguiendo el mismo criterio de tamaño usado en la Entrega 3 para
equipos_ui.py / equipos_alta_rapida_ui.py.

Referencias a clases de otros dominios que todavía viven en `cabledoc.py`
(MarcasListado, TiposEquipoListado, ImagenesListado) se resuelven con
import diferido dentro del método que las usa, siguiendo el mismo patrón
que ya usa el proyecto para evitar ciclos. `abrir_coords_imagen` se importa
a nivel de módulo desde `pantallas_avanzadas`, igual que hace
`conectores_ui.py`.

`_DialogoRenombrarConectoresCatalogo` (plan_refactor_cabledoc.md, Entrega
10 — cierre del refactor) quedó pendiente de destino desde la Entrega 8:
el plan (§4) no la contemplaba porque no forma parte del bloque "catálogos
básicos", y era el único bloque de dominio que seguía viviendo en
`cabledoc.py` fuera de la fachada. Se asigna acá, junto a
`_DialogoCatalogoEquipo` (su único consumidor, vía `_renombrar_conectores`,
ahora import directo en vez de `from cabledoc import ...`), en lugar de
`conectores_ui.py` (que es el dominio de conectores de equipos reales, no
de moldes de catálogo).
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

from pantallas_avanzadas import (
    abrir_coords_imagen,
    abrir_reglas_logicas_molde,
    abrir_editor_masivo_conectores_catalogo,
)

from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
    confirmar,
    VentanaListado,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
)


# ─── Catálogo de equipos (moldes) ──────────────────────────────────────────────

class CatalogoEquiposListado(VentanaListado):
    """Listado de moldes de equipo. Cada fila es un 'tipo de equipo' reutilizable
    con marca/modelo/manual/imagen/conectores ya definidos."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Catálogo de Equipos"),
            [_("ID"), _("Molde"), _("Marca"), _("Tipo"), _("Modelo"), _("Conectores")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                ("⚡ Alta Rápida…", self._alta_rapida),
                ("📦 Instanciar…", self._instanciar),
                ("⬆ Exportar…", self._exportar),
                ("⬇ Importar…", self._importar),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_todos_los_catalogos()
        # rows: id, nombre_molde, marca, tipo, modelo, n_conectores
        self._poblar(rows)

    def nuevo(self):
        dlg = _DialogoCatalogoEquipo(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoCatalogoEquipo(id_equipo_catalogo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_catalogo(id_)

    def _alta_rapida(self, *a):
        from catalogo_equipos_alta_rapida_ui import _DialogoAltaRapidaCatalogo
        dlg = _DialogoAltaRapidaCatalogo(parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _instanciar(self, *a):
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un molde del catálogo.")
            return
        dlg = _DialogoInstanciarCatalogo(id_equipo_catalogo=f[0],
                                         nombre_molde=f[1], parent=self)
        dlg.run_and_destroy()

    def _exportar(self, *a):
        """Exporta el molde seleccionado o todo el catálogo a un .zip
        portable que contiene un único JSON adentro (marca/tipo por nombre,
        imágenes/manual/picon embebidos en base64 dentro del JSON, y todo
        eso comprimido en el .zip)."""
        fila = self._fila()
        ids = [fila[0]] if fila else None
        if ids and not confirmar(
                self, f"¿Exportar solo el molde seleccionado «{fila[1]}»?\n\n"
                     "(Cancelá para exportar TODO el catálogo de equipos)"):
            ids = None
        dlg = Gtk.FileChooserDialog(
            title=_("Exportar catálogo de equipos"), parent=self,
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Guardar"), Gtk.ResponseType.OK)
        dlg.set_current_name("catalogo_equipos.zip")
        dlg.set_do_overwrite_confirmation(True)
        filt = Gtk.FileFilter(); filt.set_name("ZIP"); filt.add_pattern("*.zip")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if not ruta.lower().endswith(".zip"):
                ruta += ".zip"
            try:
                from cabledoc import _escribir_json_comprimido
                data = Modelo.exportar_catalogo_equipos(ids)
                _escribir_json_comprimido(ruta, "catalogo_equipos.json", data)
                mostrar_info(self,
                    f"Catálogo exportado: {len(data['moldes'])} molde(s) → {ruta}")
            except Exception as e:
                mostrar_error(self, f"Error al exportar:\n{e}")
        dlg.destroy()

    def _importar(self, *a):
        """Importa moldes desde un .zip (o un .json plano de una versión
        vieja) exportado por esta misma función, posiblemente de otra
        instalación de CableDoc."""
        dlg = Gtk.FileChooserDialog(
            title=_("Importar catálogo de equipos"), parent=self,
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
                if not isinstance(data, dict) or data.get("tipo") != "cabledoc_catalogo_equipos":
                    mostrar_error(self, "El archivo no es un catálogo de equipos válido.")
                else:
                    n_m, n_c, conflictos = Modelo.importar_catalogo_equipos(data)
                    mostrar_info(self, f"Importados {n_m} molde(s) con {n_c} conector(es).")
                    if conflictos:
                        _DialogoConflictosImportacion(conflictos, parent=self).run_and_destroy()
                    self.cargar_datos()
            except Exception as e:
                mostrar_error(self, f"Error al importar:\n{e}")
        dlg.destroy()


class _DialogoConflictosImportacion(Gtk.Dialog):
    """Fase 7 de plan_desarrollo_hardcodes_idioma.md: se muestra después de
    un import de catálogo cuando un tipo_equipo/tipo_conector ya existía en
    la base destino con un rol_senal/direccion/es_referencia_generada
    distinto al importado — el import NUNCA lo pisa solo, siempre queda el
    valor local hasta que el usuario elija explícitamente "usar el
    importado" acá y confirme."""

    _ETIQUETAS_CAMPO = {
        "rol_senal": _("Rol de señal"),
        "direccion": _("Dirección"),
        "es_referencia_generada": _("Es referencia generada"),
    }

    def __init__(self, conflictos, parent=None):
        super().__init__(
            title=_("Conflictos al importar (%d)") % len(conflictos),
            transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cerrar sin cambios"), Gtk.ResponseType.CANCEL,
                         _("Aplicar selección"), Gtk.ResponseType.OK)
        self.set_default_size(720, 380)
        self._conflictos = conflictos

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)

        lbl = Gtk.Label(wrap=True, xalign=0)
        lbl.set_markup(
            "<b>" + _("Estos tipos ya existían en la base destino con un "
                      "valor distinto al importado.") + "</b>\n" +
            _("Por defecto se mantiene el valor local en todos los casos — "
              "tildá \"Usar importado\" sólo en las filas donde corresponda "
              "y presioná \"Aplicar selección\"."))
        area.pack_start(lbl, False, False, 0)

        # store: usar_importado(bool), tipo, nombre, campo, local, importado, id, campo_raw
        self._store = Gtk.ListStore(bool, str, str, str, str, str, int, str)
        for c in conflictos:
            self._store.append([
                False, c["tipo"], c["nombre"],
                self._ETIQUETAS_CAMPO.get(c["campo"], c["campo"]),
                str(c["valor_local"]), str(c["valor_importado"]),
                int(c["id"]), c["campo"],
            ])
        tv = Gtk.TreeView(model=self._store)
        r_toggle = Gtk.CellRendererToggle()
        r_toggle.connect("toggled", self._on_toggle)
        tv.append_column(Gtk.TreeViewColumn(_("Usar importado"), r_toggle, active=0))
        for i, titulo in enumerate(
                [_("Tipo"), _("Nombre"), _("Campo"), _("Valor local"), _("Valor importado")], start=1):
            tv.append_column(Gtk.TreeViewColumn(titulo, Gtk.CellRendererText(), text=i))
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)
        self.show_all()

    def _on_toggle(self, _r, path):
        it = self._store.get_iter(path)
        self._store.set_value(it, 0, not self._store.get_value(it, 0))

    def run_and_destroy(self):
        resp = self.run()
        if resp == Gtk.ResponseType.OK:
            for row in self._store:
                usar_importado, tipo, _nom, _campo_lbl, _loc, importado, id_, campo_raw = row
                if not usar_importado:
                    continue
                if tipo == "tipo_equipo" and campo_raw == "rol_senal":
                    Modelo.establecer_rol_senal_tipo_equipo(id_, importado)
                elif tipo == "tipo_conector" and campo_raw == "direccion":
                    Modelo.establecer_direccion_tipo_conector(id_, importado)
                elif tipo == "tipo_conector" and campo_raw == "es_referencia_generada":
                    Modelo.establecer_es_referencia_generada_tipo_conector(
                        id_, importado == "True")
        self.destroy()


class _DialogoCatalogoEquipo(Gtk.Dialog):
    """Editor del molde: datos generales + lista de conectores-molde con
    posición sobre imagen (idéntico patrón a _DialogoEquipo, simplificado:
    sin inventario/serie/instancia, ya que eso es propio de cada instancia)."""

    def __init__(self, id_equipo_catalogo=None, parent=None):
        titulo = _("Editar Molde") if id_equipo_catalogo else _("Nuevo Molde de Equipo")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(560, 560)
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_marca = ""
        self.id_tipo = ""
        self.id_imagen = ""

        ca = self.get_content_area()
        g = _grid()
        _lbl_entry(g, _("Nombre molde:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Ej: Distribuidor DV700-STL")
        _lbl_entry(g, _("Tipo:"), 1)
        self.c_tipo = _searchable_combo(
            g, 1, Modelo.devolver_todos_los_tipos(), "…", self._sel_tipo_dropdown)
        _lbl_entry(g, _("Marca:"), 2)
        self.c_marca = _searchable_combo(
            g, 2, Modelo.devolver_todas_las_marcas(), "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Modelo:"), 3)
        self.e_modelo = _entry(g, 3)
        _lbl_entry(g, _("Imagen:"), 4)
        self.e_imagen = _entry_btn(g, 4, "…", self._sel_imagen)
        _lbl_entry(g, _("Manual (PDF):"), 5)
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 5, 1, 1)
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 5, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 6)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 6, 1, 1)
        btn_sel_picon = Gtk.Button(label="…")
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 6, 1, 1)
        btn_quitar_picon = Gtk.Button(label="✖")
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 6, 1, 1)
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(120, 120)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 7, 1, 1)
        ca.pack_start(g, False, False, 0)

        hbox_buttons = Gtk.Box(spacing=6)
        hbox_buttons.set_margin_start(12); hbox_buttons.set_margin_end(12)
        hbox_buttons.set_margin_bottom(6)
        if id_equipo_catalogo:
            btn_con = Gtk.Button(label="🔌 " + _("Conectores del molde"))
            btn_con.connect("clicked", self._ver_conectores)
            hbox_buttons.pack_start(btn_con, False, False, 0)

            btn_masivo = Gtk.Button(label="📍 " + _("Edición masiva conectores en imagen"))
            btn_masivo.connect("clicked", self._editar_conectores_masivo)
            hbox_buttons.pack_start(btn_masivo, False, False, 0)

            btn_rename = Gtk.Button(label="🏷 " + _("Renombrar conectores"))
            btn_rename.connect("clicked", self._renombrar_conectores)
            hbox_buttons.pack_start(btn_rename, False, False, 0)

            btn_reglas = Gtk.Button(label="🔀 " + _("Reglas lógicas"))
            btn_reglas.set_tooltip_text(
                _("Definir condiciones AND/OR sobre los conectores de este molde — "
                  "se copian automáticamente a cada equipo que se instancie desde acá"))
            btn_reglas.connect("clicked", self._ver_reglas_logicas_molde)
            hbox_buttons.pack_start(btn_reglas, False, False, 0)
        ca.pack_start(hbox_buttons, False, False, 0)

        if id_equipo_catalogo:
            rows = Modelo.devolver_catalogo(id_equipo_catalogo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_tipo = s(r[2]); _set_combo_id(self.c_tipo, self.id_tipo)
                self.id_marca = s(r[4]); _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[6]))
                self.id_imagen = s(r[7])
                self.e_imagen.set_text(s(r[8]))
                self.e_manual.set_text(s(r[9]))
                if len(r) > 11 and r[11]:
                    self.e_picon.set_text(s(r[11]))

        self._actualizar_picon_preview()
        self.show_all()

    def _sel_tipo_dropdown(self, btn):
        from cabledoc import TiposEquipoListado
        dlg = TiposEquipoListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_tipo, Modelo.devolver_todos_los_tipos())
            _set_combo_id(self.c_tipo, dlg.resultado_id)
        dlg.destroy()

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

    def _ver_conectores(self, btn):
        dlg = _ConectoresCatalogoListado(self.id_equipo_catalogo, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_reglas_logicas_molde(self, btn):
        """Abre el editor de reglas lógicas (AND/OR) de este molde."""
        nombre = self.e_nombre.get_text().strip() or f"Molde #{self.id_equipo_catalogo}"
        abrir_reglas_logicas_molde(self.id_equipo_catalogo, nombre, parent=self)

    def _editar_conectores_masivo(self, btn):
        from cabledoc import _sel_imagen_desde_abm
        if not self.id_imagen:
            mostrar_error(self, "Asigná una imagen al molde antes de "
                                "usar la edición masiva de conectores.")
            return
        abrir_editor_masivo_conectores_catalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def _renombrar_conectores(self, btn):
        dlg = _DialogoRenombrarConectoresCatalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self)
        dlg.run_and_destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_tipo = _get_combo_id(self.c_tipo)
            id_marca = _get_combo_id(self.c_marca)
            nombre = self.e_nombre.get_text().strip()
            modelo = self.e_modelo.get_text().strip()
            manual = self.e_manual.get_text().strip() or None
            picon = self.e_picon.get_text().strip() or None
            if self.id_equipo_catalogo:
                Modelo.modificacion_catalogo(
                    self.id_equipo_catalogo, nombre, id_tipo or None,
                    id_marca or None, modelo, self.id_imagen or None, manual,
                    picon=picon)
            else:
                nuevo_id = Modelo.alta_catalogo(
                    nombre, id_tipo or None, id_marca or None, modelo,
                    self.id_imagen or None, manual, picon=picon)
                self.id_equipo_catalogo = nuevo_id
        self.destroy()


class _ConectoresCatalogoListado(VentanaListado):
    def __init__(self, id_equipo_catalogo, parent=None):
        super().__init__(_("Conectores del molde"),
                         [_("ID"), _("Nombre"), _("Tipo")], parent=parent,
                         botones_extra=[
                             ("📍 Edición masiva en imagen", self._editar_masivo),
                         ])
        self.id_equipo_catalogo = id_equipo_catalogo
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_conectores_de_catalogo(self.id_equipo_catalogo)
        # rows: id, nombre, tipo_nom, id_tipo_conector, id_imagen, img_path, x, y
        data = [[r[0], r[1], r[2]] for r in rows]
        self._poblar(data)

    def nuevo(self):
        dlg = _DialogoConectorCatalogo(id_equipo_catalogo=self.id_equipo_catalogo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConectorCatalogo(id_conector_catalogo=id_,
                                       id_equipo_catalogo=self.id_equipo_catalogo,
                                       parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conector_catalogo(id_)

    def _editar_masivo(self, btn):
        from cabledoc import _sel_imagen_desde_abm
        abrir_editor_masivo_conectores_catalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)
        self.cargar_datos()


class _DialogoConectorCatalogo(Gtk.Dialog):
    def __init__(self, id_conector_catalogo=None, id_equipo_catalogo=None, parent=None):
        titulo = _("Editar Conector Molde") if id_conector_catalogo else _("Nuevo Conector Molde")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(420, 260)
        self.id_conector_catalogo = id_conector_catalogo
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Tipo conector:"), 1)
        self.c_tipo = _searchable_combo(g, 1, Modelo.devolver_tipos_conectores())
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)

        # Fase B de plan_desarrollo_funcion_patchera.md: el combo lee
        # Modelo.funciones_patchera() (tabla, no una lista fija en
        # Python) y muestra el NOMBRE VISIBLE de cada función — el valor
        # que persiste es id_funcion_patchera, independiente de cualquier
        # convención de nombre de conector (a diferencia del extinto
        # "Fila de patchera" A_BACK/B_BACK/A_FRONT/B_FRONT, que forzaba
        # la convención de una sola marca).
        self._es_molde_patchera = False
        if id_equipo_catalogo:
            rows_cat = Modelo.devolver_catalogo(id_equipo_catalogo)
            if rows_cat and rows_cat[0][2]:
                self._es_molde_patchera = (
                    Modelo.devolver_rol_senal_tipo_equipo(rows_cat[0][2]) == "PATCHERA")
        self.c_funcion_patchera = Gtk.ComboBoxText()
        self.c_funcion_patchera.append("", _("(ninguna)"))
        for f in Modelo.funciones_patchera():
            self.c_funcion_patchera.append(f["id"], f["nombre_es"])
        self.c_funcion_patchera.set_active_id("")
        if self._es_molde_patchera:
            _lbl_entry(g, _("Función de patchera:"), 5)
            g.attach(self.c_funcion_patchera, 1, 5, 2, 1)
        self.get_content_area().add(g)

        btn_coords = Gtk.Button(label="📍 " + _("Elegir coords en imagen"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_conector_catalogo:
            rows = Modelo._query(
                "SELECT id_conector_catalogo, nombre, id_tipo_conector, "
                "id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen, "
                "id_funcion_patchera "
                "FROM conector_catalogo WHERE id_conector_catalogo=?",
                (id_conector_catalogo,))
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                _set_combo_id(self.c_tipo, s(r[2]))
                self.id_imagen = s(r[3])
                x_px, y_px = Modelo._px_punto_o_crudo(
                    Modelo._path_imagen(r[3]), r[4], r[5])
                self.e_x.set_text(s(x_px)); self.e_y.set_text(s(y_px))
                if len(r) > 6 and r[6]:
                    self.c_funcion_patchera.set_active_id(s(r[6]))
                if self.id_imagen:
                    rows_img = Modelo.devolver_imagen(self.id_imagen)
                    if rows_img:
                        self.e_imagen.set_text(s(rows_img[0][1]))

        self.show_all()

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(), parent=self)
        if res:
            self.e_x.set_text(res["x"]); self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            id_tipo_conector = _get_combo_id(self.c_tipo)
            x = self.e_x.get_text().strip(); y = self.e_y.get_text().strip()
            id_funcion_patchera = self.c_funcion_patchera.get_active_id() or None
            if self.id_conector_catalogo:
                Modelo.modificacion_conector_catalogo(
                    self.id_conector_catalogo, nombre,
                    id_tipo_conector or None, self.id_imagen or None, x, y,
                    id_funcion_patchera=id_funcion_patchera,
                    _tocar_funcion_patchera=self._es_molde_patchera)
            else:
                Modelo.agregar_conector_catalogo(
                    self.id_equipo_catalogo, nombre,
                    id_tipo_conector or None, self.id_imagen or None, x, y,
                    id_funcion_patchera=id_funcion_patchera)
        self.destroy()


class _DialogoInstanciarCatalogo(Gtk.Dialog):
    """Instancia un equipo real desde un molde: solo pide nombre, serie,
    inventario y posición x/y en planta. Todo lo demás se copia del molde."""

    def __init__(self, id_equipo_catalogo, nombre_molde="", parent=None):
        super().__init__(title=_("Instanciar equipo desde catálogo"),
                         transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📦 " + _("Crear equipo"), Gtk.ResponseType.OK)
        self.set_default_size(420, 260)
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_equipo_creado = None

        ca = self.get_content_area()
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>Molde:</b> {nombre_molde}")
        lbl.set_margin_start(12); lbl.set_margin_top(10)
        ca.pack_start(lbl, False, False, 0)

        g = _grid()
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del equipo real (requerido)")
        _lbl_entry(g, _("Inventario:"), 1)
        self.e_inventario = _entry(g, 1)
        _lbl_entry(g, _("Serie:"), 2)
        self.e_serie = _entry(g, 2)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)
        ca.pack_start(g, False, False, 0)

        n_con = len(Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo))
        lbl_n = Gtk.Label(xalign=0)
        lbl_n.set_markup(f"<small><i>Se copiarán {n_con} conectores con su posición.</i></small>")
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
                mostrar_error(self, "El nombre del equipo es obligatorio.")
                continue
            self.id_equipo_creado = Modelo.instanciar_desde_catalogo(
                self.id_equipo_catalogo, nombre,
                self.e_inventario.get_text().strip() or None,
                self.e_serie.get_text().strip() or None,
                self.e_x.get_text().strip() or None,
                self.e_y.get_text().strip() or None,
            )
            mostrar_info(self, f"Equipo «{nombre}» creado (ID {self.id_equipo_creado}).")
            break
        self.destroy()


class _DialogoDuplicarMolde(Gtk.Dialog):
    """
    Mini-diálogo para 'Guardar y duplicar' en el catálogo: pide cuántos
    moldes duplicados crear y un patrón de nombre con 'XX' como marcador
    de posición del número (ej: 'EQUIPO_XX' → EQUIPO_01, EQUIPO_02...).
    """

    def __init__(self, nombre_base="", parent=None):
        super().__init__(title=_("Duplicar molde"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📋 " + _("Crear duplicados"), Gtk.ResponseType.OK)
        self.set_default_size(420, 200)
        self.cantidad = 0
        self.patron = ""

        g = _grid()
        _lbl_entry(g, _("Patrón de nombre:"), 0)
        self.e_patron = _entry(g, 0)
        sugerido = (nombre_base + "_XX") if nombre_base else "EQUIPO_XX"
        self.e_patron.set_text(sugerido)
        self.e_patron.set_placeholder_text("Ej: EQUIPO_XX")

        _lbl_entry(g, _("Cantidad:"), 1)
        adj = Gtk.Adjustment(value=2, lower=1, upper=99, step_increment=1)
        self.spin_cant = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        g.attach(self.spin_cant, 1, 1, 2, 1)

        self.get_content_area().add(g)

        lbl_hint = Gtk.Label(xalign=0)
        lbl_hint.set_markup(
            "<small><i>'XX' en el patrón se reemplaza por el número de "
            "secuencia (01, 02, …). Si el patrón no contiene 'XX', se "
            "agrega automáticamente al final.</i></small>")
        lbl_hint.set_line_wrap(True)
        lbl_hint.set_margin_start(12); lbl_hint.set_margin_end(12)
        lbl_hint.set_margin_bottom(8)
        self.get_content_area().pack_start(lbl_hint, False, False, 0)

        self._lbl_preview = Gtk.Label(xalign=0)
        self._lbl_preview.set_margin_start(12); self._lbl_preview.set_margin_bottom(8)
        self.get_content_area().pack_start(self._lbl_preview, False, False, 0)

        self.e_patron.connect("changed", self._actualizar_preview)
        self.spin_cant.connect("value-changed", self._actualizar_preview)

        self.show_all()
        self._actualizar_preview()

    def _actualizar_preview(self, *a):
        nombres = self._generar_nombres()
        if not nombres:
            self._lbl_preview.set_markup("<small><i>" + _("Patrón inválido") + "</i></small>")
            return
        muestra = ", ".join(nombres[:3])
        if len(nombres) > 3:
            muestra += f", … ({len(nombres)} en total)"
        self._lbl_preview.set_markup(f"<small>Se crearán: <b>{muestra}</b></small>")

    def _generar_nombres(self):
        patron = self.e_patron.get_text().strip()
        cantidad = int(self.spin_cant.get_value())
        if not patron or cantidad < 1:
            return []
        if "XX" not in patron:
            patron = patron + "_XX"
        ancho = max(2, len(str(cantidad)))
        return [patron.replace("XX", str(i).zfill(ancho))
                for i in range(1, cantidad + 1)]

    def run_and_destroy(self):
        resultado = None
        if self.run() == Gtk.ResponseType.OK:
            nombres = self._generar_nombres()
            if nombres:
                resultado = nombres
            else:
                mostrar_error(self, "Patrón de nombre o cantidad inválidos.")
        self.destroy()
        return resultado


# ─── Conectores de catálogo — Renombrado masivo ────────────────────────────────
#
# Movida desde cabledoc.py (plan_refactor_cabledoc.md, Entrega 10, cierre):
# único bloque de dominio que seguía sin mover desde la Entrega 8. Su único
# consumidor es _DialogoCatalogoEquipo._renombrar_conectores, en este mismo
# archivo — se asigna acá en vez de conectores_ui.py (dominio de conectores
# de equipos reales, no de moldes).

class _DialogoRenombrarConectoresCatalogo(Gtk.Dialog):
    """Igual que _DialogoRenombrarConectores pero para los conectores de un
    MOLDE de catálogo (conector_catalogo), no de un equipo real."""

    def __init__(self, id_equipo_catalogo, parent=None):
        super().__init__(
            title=_("Renombrar Conectores del Molde"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(600, 500)
        self.id_equipo_catalogo = id_equipo_catalogo

        # Contenedor principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.get_content_area().add(vbox)

        # Obtener conectores del molde
        # cols: id_conector_catalogo, nombre, tipo_nombre, id_tipo_conector,
        #       id_imagen, img_path, x, y
        conectores = Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo)

        # Crear grid para los conectores
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(4)
        grid.set_vexpand(True)
        grid.set_hexpand(True)

        # Crear lista para guardar los entries
        self.entries = []

        for i, c in enumerate(conectores):
            id_cc, nombre = c[0], c[1]
            # Label con el nombre actual
            lbl = Gtk.Label(label=nombre)
            lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1)

            # Entry para el nuevo nombre
            entry = Gtk.Entry()
            entry.set_text(nombre)
            entry.set_hexpand(True)
            grid.attach(entry, 1, i, 1, 1)

            # Guardar referencia al entry junto con el id y nombre original
            self.entries.append({
                'id': id_cc,
                'original': nombre,
                'entry': entry
            })

        if not conectores:
            lbl_vacio = Gtk.Label(label=_("Este molde todavía no tiene conectores."))
            lbl_vacio.set_xalign(0)
            grid.attach(lbl_vacio, 0, 0, 2, 1)

        # ScrolledWindow para el grid
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        sw.add(grid)
        vbox.pack_start(sw, True, True, 0)

        self.show_all()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            # Guardar los cambios
            for item in self.entries:
                nuevo_nombre = item['entry'].get_text().strip()
                # Si está en blanco, mantener el nombre original
                if not nuevo_nombre:
                    nuevo_nombre = item['original']
                # Solo actualizar si el nombre cambió
                if nuevo_nombre != item['original']:
                    # Obtener los otros datos del conector-molde para no perderlos
                    conectores = Modelo.devolver_conectores_de_catalogo(
                        self.id_equipo_catalogo)
                    fila = next((c for c in conectores if str(c[0]) == str(item['id'])), None)
                    if fila:
                        Modelo.modificacion_conector_catalogo(
                            item['id'],
                            nuevo_nombre,
                            fila[3],  # id_tipo_conector
                            fila[4],  # id_imagen
                            fila[6],  # x
                            fila[7],  # y
                            fila[8] if len(fila) > 8 else None,  # fila_patchera
                        )
        self.destroy()
