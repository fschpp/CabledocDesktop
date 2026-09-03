#!/usr/bin/env python3
"""
equipos_ui.py — CableDoc GTK3

Dominio Equipos — Listado y Ficha completa, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 3).

Contiene:
  - EquiposListado (listado principal de equipos)
  - _DialogoDireccionConector (mini-diálogo IN/OUT)
  - _DialogoEquipo (ficha completa de equipo)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos tres nombres sin cambios.

Separado de `equipos_alta_rapida_ui.py` (_DialogoAltaRapidaEquipo) porque
juntos superaban las ~900 líneas objetivo del plan (~1.700 líneas → 2
archivos).

Referencias a clases de otros dominios que todavía viven en `cabledoc.py`
(CatalogoEquiposListado, _DialogoInstanciarCatalogo, ImagenesListado,
MarcasListado, TiposEquipoListado, ConectoresListado,
_DialogoRenombrarConectores, ProblemasEquipoListado) se resuelven con
import diferido dentro del método que las usa, siguiendo el mismo patrón
que ya usa el proyecto para evitar ciclos.
"""

import os
import re
import json
import shutil
import subprocess

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf, Pango

from modelo import Modelo, DB_PATH, PICON_DIR, MANUALES_DIR

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
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
    abrir_historial_diagnosticos,
    abrir_arbol_conexiones,
    abrir_coords_imagen,
    abrir_diagrama_conexiones,
    abrir_editor_masivo_conectores,
    abrir_imagen_conectores,
    abrir_patcheras,
    abrir_reglas_logicas,
    abrir_vista_rack,
)


# ─── Equipos ──────────────────────────────────────────────────────────────────

class EquiposListado(VentanaListado):
    # filtro_pendiente: None | 'sin_conectores' | 'sin_imagen' | 'sin_img_conectores'
    def __init__(self, parent=None, modo_seleccion=False, filtro_pendiente=None):
        self._ocultar_patcheras = True   # debe existir antes de super().__init__
        self._filtro_pendiente = filtro_pendiente
        self._ids_resaltar = set()
        titulo = _("Equipos")
        if filtro_pendiente == "sin_conectores":
            titulo = _("Equipos — Sin conectores")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Equipos — Sin imagen")
        elif filtro_pendiente == "sin_img_conectores":
            titulo = _("Equipos — Sin imagen c/ conectores")
        super().__init__(
            titulo,
            [_("ID"), _("Nombre"), _("Marca"), _("Modelo"), _("Inventario"), _("Serie"), _("Tipo"),
             _("Riesgo")],
            parent=parent, modo_seleccion=modo_seleccion
        )
        # Obtener la barra de botones (hbtn) de VentanaListado
        hbtn = None
        for ch in self.get_content_area().get_children():
            if isinstance(ch, Gtk.Box):
                hbtn = ch
                break
        
        # Añadir botón Alta Rápida a la barra de botones
        btn_ar = Gtk.Button(label="⚡ " + _("Alta Rápida"))
        btn_ar.set_tooltip_text(
            _("Crear equipo con conectores en un solo formulario (estilo AVwire)"))
        btn_ar.connect("clicked", self._alta_rapida)
        if hbtn:
            hbtn.pack_start(btn_ar, False, False, 0)
            hbtn.reorder_child(btn_ar, 3)

        btn_cat = Gtk.Button(label="📦 " + _("Desde catálogo"))
        btn_cat.set_tooltip_text(
            _("Crear equipo instanciando un molde del catálogo (nombre/serie/inventario/posición)"))
        btn_cat.connect("clicked", self._desde_catalogo)
        if hbtn:
            hbtn.pack_start(btn_cat, False, False, 0)
            hbtn.reorder_child(btn_cat, 4)

        btn_hist = Gtk.Button(label="🩺 " + _("Historial de diagnósticos"))
        btn_hist.set_tooltip_text(
            _("'Prontuario' del equipo seleccionado — sesiones de "
              "diagnóstico de falla donde resultó sospechoso"))
        btn_hist.connect("clicked", self._ver_historial_diagnosticos)
        if hbtn:
            hbtn.pack_start(btn_hist, False, False, 0)
            hbtn.reorder_child(btn_hist, 5)

        btn_bitacora = Gtk.Button(label="📋 " + _("Ver incidentes"))
        btn_bitacora.set_tooltip_text(
            _("Bitácora de incidentes del equipo seleccionado — fallas "
              "reales registradas, directamente o vía una zona sospechosa "
              "a la que pertenezca"))
        btn_bitacora.connect("clicked", self._ver_bitacora_incidentes)
        if hbtn:
            hbtn.pack_start(btn_bitacora, False, False, 0)
            hbtn.reorder_child(btn_bitacora, 6)
        
        # Añadir checkbox "Ocultar patcheras" a la barra de botones
        self._chk_patchera = Gtk.CheckButton(label=_("Ocultar patcheras"))
        self._chk_patchera.set_active(True)
        self._chk_patchera.connect("toggled", self._on_toggle_patcheras)
        if hbtn:
            hbtn.pack_start(self._chk_patchera, False, False, 0)

        # Botón para recalcular el Índice de Riesgo de Falla (IRF) de
        # todo el parque de equipos (columna "Riesgo")
        btn_riesgo = Gtk.Button(label="🔺 " + _("Recalcular riesgo"))
        btn_riesgo.set_tooltip_text(
            _("Recalcula el Índice de Riesgo de Falla de todos los equipos "
              "(antigüedad, condición de uso, historial de problemas y "
              "criticidad en la cadena de transmisión)."))
        btn_riesgo.connect("clicked", self._recalcular_riesgo)
        if hbtn:
            hbtn.pack_start(btn_riesgo, False, False, 0)

        self.show_all()
        self.btn_seleccionar.set_visible(self.modo_seleccion)
        self.cargar_datos()

    def _on_toggle_patcheras(self, chk):
        self._ocultar_patcheras = chk.get_active()
        self.filtro_model.refilter()

    def cargar_datos(self):
        self._ids_resaltar = set()
        # Fase 4 de plan_desarrollo_hardcodes_idioma.md: el filtro "Ocultar
        # patcheras" ya no busca la palabra "PATCHERA" en la columna Tipo
        # (texto libre) -- usa rol_senal='PATCHERA', igual que
        # devolver_equipos_patchera().
        self._ids_patchera = {str(r[0]) for r in Modelo.devolver_equipos_patchera()}
        color = "#c8a800"
        if self._filtro_pendiente == "sin_conectores":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector WHERE id_equipo=equipo.id_equipo)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 AND id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_img_conectores":
            rows = Modelo._query(
                "SELECT e.id_equipo FROM equipo e WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector c "
                "WHERE c.id_equipo=e.id_equipo AND c.id_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        todos = Modelo.devolver_todos_los_equipos()
        todos, color_por_id = self._agregar_columna_riesgo(todos)
        # Fase 4 de plan_desarrollo_hardcodes_idioma.md: ya no se filtra
        # comparando texto ("PATCHERA" in tipo) sino por rol_senal real.
        self._ids_patchera = {str(r[0]) for r in Modelo.devolver_equipos_patchera()}
        self._poblar(todos, ids_resaltar=self._ids_resaltar, color_resaltar=color,
                     color_por_id=color_por_id)
        # Aplicar prefiltro de texto si hay filtro activo
        if self._filtro_pendiente:
            self.entry_filtro.set_text("")
            self.filtro_model.refilter()

    @staticmethod
    def _agregar_columna_riesgo(filas):
        """Agrega el texto de riesgo (ej. '35 · Medio') como última columna
        de cada fila, y arma el mapeo id->color hex para semáforo visual.
        Usa la caché guardada en riesgo_equipo_cache (no recalcula en cada
        apertura del listado; para eso está el botón "🔺 Recalcular riesgo")."""
        from risk_engine import color_de
        cache = Modelo.devolver_riesgo_todos_los_equipos()  # {id_str: (riesgo, nivel)}
        filas_ext = []
        color_por_id = {}
        for f in filas:
            id_str = s(f[0])
            if id_str in cache:
                riesgo, nivel = cache[id_str]
                texto = f"{riesgo:.0f} · {nivel}"
                r, g, b = color_de(riesgo)
                color_por_id[id_str] = "#%02x%02x%02x" % (
                    int(r * 255), int(g * 255), int(b * 255))
            else:
                texto = _("Sin calcular")
            filas_ext.append(list(f) + [texto])
        return filas_ext, color_por_id

    def _recalcular_riesgo(self, *a):
        from risk_engine import RiskEngine
        self.set_sensitive(False)
        try:
            RiskEngine(DB_PATH).calcular_todos()
        except Exception as e:
            mostrar_error(self, f"{_('No se pudo calcular el riesgo')}:\n{e}")
        finally:
            self.set_sensitive(True)
        self.cargar_datos()

    def _filtrar(self, model, iter_, data):
        """Extiende el filtro: texto + patcheras + solo-pendientes."""
        txt = self.entry_filtro.get_text().lower()
        n = len(self.columnas)
        if txt:
            if not any(txt in s(model.get_value(iter_, i)).lower() for i in range(n)):
                return False
        if self._ocultar_patcheras:
            fid = s(model.get_value(iter_, 0))
            if fid in getattr(self, "_ids_patchera", ()):
                return False
        # Si hay filtro pendiente, mostrar SOLO los resaltados
        if self._filtro_pendiente and self._ids_resaltar:
            fid = s(model.get_value(iter_, 0))
            return fid in self._ids_resaltar
        return True

    def nuevo(self):
        dlg = _DialogoEquipo(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoEquipo(id_equipo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_equipo(id_)

    def _alta_rapida(self, *a):
        from equipos_alta_rapida_ui import _DialogoAltaRapidaEquipo
        dlg = _DialogoAltaRapidaEquipo(parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _desde_catalogo(self, *a):
        from cabledoc import CatalogoEquiposListado, _DialogoInstanciarCatalogo
        sel = CatalogoEquiposListado(parent=self, modo_seleccion=True)
        if sel.run() == Gtk.ResponseType.OK:
            id_cat = sel.resultado_id
            nombre_molde = sel.resultado_nombre
            sel.destroy()
            dlg = _DialogoInstanciarCatalogo(
                id_equipo_catalogo=id_cat, nombre_molde=nombre_molde, parent=self)
            dlg.run_and_destroy()
            self.cargar_datos()
        else:
            sel.destroy()

    def _ver_historial_diagnosticos(self, *a):
        """'Prontuario' del equipo seleccionado (ver plan_asistente_
        diagnostico_fallas.md) — sesiones donde este equipo resultó
        sospechoso, para detectar fallas recurrentes."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un equipo primero.")
            return
        abrir_historial_diagnosticos(DB_PATH, parent=self, id_equipo=f[0])

    def _ver_bitacora_incidentes(self, *a):
        """Bitácora de incidentes (ver plan_bitacora_incidentes_riesgo_
        analogico.md) del equipo seleccionado — incluye los cargados vía
        una zona sospechosa a la que pertenezca, no sólo los directos."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un equipo primero.")
            return
        from bitacora_ui import abrir_bitacora_incidentes
        abrir_bitacora_incidentes(parent=self, id_equipo=f[0])



class _DialogoDireccionConector(Gtk.Dialog):
    """Mini-diálogo para elegir IN / OUT al agregar conector manual."""
    def __init__(self, parent=None):
        super().__init__(title=_("Dirección del conector"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "OK", Gtk.ResponseType.OK)
        self.direccion = "IN"
        hb = Gtk.Box(spacing=12)
        hb.set_margin_start(16); hb.set_margin_end(16)
        hb.set_margin_top(12);   hb.set_margin_bottom(12)
        rb_in = Gtk.RadioButton.new_with_label(None, "← Entrada (IN)")
        rb_out = Gtk.RadioButton.new_with_label_from_widget(rb_in, "→ Salida (OUT)")
        rb_in.connect("toggled", lambda b: setattr(self, "direccion", "IN"))
        rb_out.connect("toggled", lambda b: setattr(self, "direccion", "OUT"))
        hb.pack_start(rb_in, False, False, 0)
        hb.pack_start(rb_out, False, False, 0)
        self.get_content_area().pack_start(hb, False, False, 0)
        self.show_all()

class _DialogoEquipo(Gtk.Dialog):
    def __init__(self, id_equipo=None, parent=None):
        titulo = _("Editar Equipo") if id_equipo else _("Nuevo Equipo")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(700, 620)
        self.id_equipo = id_equipo
        self.id_marca = ""
        self.id_tipo = ""
        self.id_imagen = ""

        # Crear contenedor principal vertical
        vbox_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox_main.set_margin_top(6)
        self.get_content_area().add(vbox_main)

        # ── Pestaña Datos (Notebook primero) ──
        nb = Gtk.Notebook()

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(
            g, 1, Modelo.devolver_todas_las_marcas(),
            "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Tipo:"), 2)
        self.c_tipo = _searchable_combo(
            g, 2, Modelo.devolver_todos_los_tipos(),
            "…", self._sel_tipo_dropdown)
        _lbl_entry(g, _("Modelo:"), 3)
        self.e_modelo = _entry(g, 3)
        _lbl_entry(g, _("Inventario:"), 4)
        self.e_inventario = _entry(g, 4)
        _lbl_entry(g, _("Serie:"), 5)
        self.e_serie = _entry(g, 5)
        _lbl_entry(g, _("Imagen:"), 6)
        self.e_imagen = _entry_btn(g, 6, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 7)
        self.e_x = _entry(g, 7)
        _lbl_entry(g, _("Coord Y:"), 8)
        self.e_y = _entry(g, 8)
        _lbl_entry(g, _("Manual (PDF):"), 9)
        # Entry para el manual PDF
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 9, 1, 1)
        # Botón para seleccionar manual
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 9, 1, 1)
        # Botón para ver el PDF
        btn_view_manual = Gtk.Button(label="👁 " + _("Ver"))
        btn_view_manual.connect("clicked", self._ver_manual)
        g.attach(btn_view_manual, 3, 9, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 10)
        # Entry para el nombre de archivo de la foto del equipo (picon)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 10, 1, 1)
        # Botón para seleccionar la foto
        btn_sel_picon = Gtk.Button(label="…")
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 10, 1, 1)
        # Botón para quitar la foto
        btn_quitar_picon = Gtk.Button(label="✖")
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 10, 1, 1)
        # Miniatura de vista previa de la foto
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(140, 140)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 11, 1, 1)
        _lbl_entry(g, _("Fecha de fabricación:"), 12)
        self.e_fecha_fabricacion = _entry(g, 12)
        self.e_fecha_fabricacion.set_placeholder_text("AAAA-MM-DD")
        self.chk_equipo_usado = Gtk.CheckButton(label=_("Equipo usado (no nuevo)"))
        g.attach(self.chk_equipo_usado, 1, 13, 2, 1)

        # ── Sección: Riesgo de falla (IRF) ──
        sep_riesgo = Gtk.Separator()
        g.attach(sep_riesgo, 0, 14, 4, 1)
        lbl_riesgo_titulo = Gtk.Label()
        lbl_riesgo_titulo.set_markup("<b>🔺 " + _("Riesgo de falla") + "</b>")
        lbl_riesgo_titulo.set_xalign(0)
        g.attach(lbl_riesgo_titulo, 0, 15, 4, 1)

        self.lbl_riesgo_score = Gtk.Label(label="—")
        self.lbl_riesgo_score.set_xalign(0)
        g.attach(self.lbl_riesgo_score, 0, 16, 4, 1)

        self.chk_equipo_critico = Gtk.CheckButton(
            label="⭐ " + _("Equipo crítico de la cadena"))
        self.chk_equipo_critico.set_tooltip_text(
            _("Marca este equipo como parte del conjunto curado de equipos "
              "realmente vitales (ej. la cadena de aire). Con al menos un "
              "equipo marcado en toda la base, el factor Impacto del riesgo "
              "prioriza este conjunto en vez de contar todo el parque por "
              "igual. También se puede marcar de a varios desde el "
              "diagrama de conexiones (seleccioná con rectángulo o "
              "Shift/Ctrl+clic y usá '⭐ Marcar críticos')."))
        self.chk_equipo_critico.connect("toggled", self._on_toggle_critico)
        g.attach(self.chk_equipo_critico, 0, 17, 4, 1)

        self.lbl_riesgo_detalle = Gtk.Label(label="")
        self.lbl_riesgo_detalle.set_xalign(0)
        self.lbl_riesgo_detalle.set_line_wrap(True)
        self.lbl_riesgo_detalle.get_style_context().add_class("dim-label")
        g.attach(self.lbl_riesgo_detalle, 0, 18, 4, 2)

        hbox_riesgo = Gtk.Box(spacing=6)
        btn_recalc_riesgo = Gtk.Button(label="🔄 " + _("Recalcular"))
        btn_recalc_riesgo.set_tooltip_text(
            _("Recalcula el riesgo de este equipo (y de todo el parque, ya "
              "que el factor de impacto depende del grafo completo)."))
        btn_recalc_riesgo.connect("clicked", self._recalcular_riesgo)
        hbox_riesgo.pack_start(btn_recalc_riesgo, False, False, 0)
        btn_ver_afectados = Gtk.Button(label="⚡ " + _("Simular remoción"))
        btn_ver_afectados.set_tooltip_text(_(
            "Qué otros equipos y cables quedan sin señal si este equipo "
            "falla (no destructivo, no toca la base)."))
        btn_ver_afectados.connect("clicked", self._ver_equipos_afectados)
        hbox_riesgo.pack_start(btn_ver_afectados, False, False, 0)
        g.attach(hbox_riesgo, 0, 20, 4, 1)

        nb.append_page(g, Gtk.Label(label=_("Datos")))

        # ── Pestaña Configuraciones ──
        box_conf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box_conf.set_margin_start(12)
        box_conf.set_margin_end(12)
        box_conf.set_margin_top(6)
        box_conf.set_margin_bottom(6)
        
        # TextView para edición (arriba)
        self.tv_configuraciones_edit = Gtk.TextView()
        self.tv_configuraciones_edit.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_configuraciones_edit.set_editable(True)
        self.tv_configuraciones_edit.set_hexpand(True)
        
        scrolled_edit = Gtk.ScrolledWindow()
        scrolled_edit.set_hexpand(True)
        scrolled_edit.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_edit.add(self.tv_configuraciones_edit)
        box_conf.pack_start(scrolled_edit, True, True, 0)
        
        # Separador
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box_conf.pack_start(sep, False, False, 0)
        
        # Label para vista previa
        lbl_preview = Gtk.Label(label=_("Vista previa (Markdown renderizado):"))
        lbl_preview.set_xalign(0)
        box_conf.pack_start(lbl_preview, False, False, 0)
        
        # TextView para visualización (abajo)
        self.tv_configuraciones_view = Gtk.TextView()
        self.tv_configuraciones_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_configuraciones_view.set_editable(False)
        self.tv_configuraciones_view.set_cursor_visible(False)
        self.tv_configuraciones_view.set_hexpand(True)
        self.tv_configuraciones_view.set_vexpand(True)
        
        # Crear tags para formato Markdown (una sola vez)
        buffer_view = self.tv_configuraciones_view.get_buffer()
        self.tag_bold = buffer_view.create_tag("bold", weight=700)
        self.tag_italic = buffer_view.create_tag("italic", style=Pango.Style.ITALIC)
        self.tag_mono = buffer_view.create_tag("monospace", family="Monospace")
        self.tag_large = buffer_view.create_tag("large", scale=1.5, weight=700)
        self.tag_xlarge = buffer_view.create_tag("x-large", scale=2.0, weight=700)
        
        scrolled_view = Gtk.ScrolledWindow()
        scrolled_view.set_hexpand(True)
        scrolled_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_view.add(self.tv_configuraciones_view)
        box_conf.pack_start(scrolled_view, True, True, 0)
        
        # Botón para alternar entre edición y visualización
        self.btn_edit_config = Gtk.Button(label="✏️ " + _("Editar"))
        self.btn_edit_config.connect("clicked", self._toggle_edit_configuraciones)
        box_conf.pack_start(self.btn_edit_config, False, False, 0)
        
        # Guardar referencia al TextView de edición para compatibilidad
        self.tv_configuraciones = self.tv_configuraciones_edit
        
        # Guardar referencias a widgets para mostrar/ocultar
        self.scrolled_edit = scrolled_edit
        self.sep_config = sep
        self.lbl_preview = lbl_preview
        self.scrolled_view = scrolled_view
        
        nb.append_page(box_conf, Gtk.Label(label=_("Configuraciones")))

        # Añadir Notebook al contenedor principal (expande para ocupar espacio)
        vbox_main.pack_start(nb, True, True, 0)

        # ── Botones extra abajo del Notebook (2 filas de 5) ──
        vbox_botones = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox_botones.set_margin_start(12)
        vbox_botones.set_margin_end(12)
        vbox_botones.set_margin_bottom(6)

        hbox_fila1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_fila2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_fila3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox_botones.pack_start(hbox_fila1, False, False, 0)
        vbox_botones.pack_start(hbox_fila2, False, False, 0)
        vbox_botones.pack_start(hbox_fila3, False, False, 0)

        if id_equipo:
            btn_con = Gtk.Button(label="🔌 " + _("Ver Conectores"))
            btn_con.connect("clicked", self._ver_conectores)
            hbox_fila1.pack_start(btn_con, False, False, 0)

            btn_img_con = Gtk.Button(label="🖼 " + _("Imagen c/ conectores"))
            btn_img_con.connect("clicked", self._ver_imagen_conectores)
            hbox_fila1.pack_start(btn_img_con, False, False, 0)

            btn_ed_masivo = Gtk.Button(label="📍 " + _("Edición masiva conectores en imagen"))
            btn_ed_masivo.connect("clicked", self._ver_editor_masivo_conectores)
            hbox_fila1.pack_start(btn_ed_masivo, False, False, 0)

            btn_arbol = Gtk.Button(label="🌳 " + _("Árbol de conexiones"))
            btn_arbol.connect("clicked", self._ver_arbol)
            hbox_fila1.pack_start(btn_arbol, False, False, 0)

            btn_patch = Gtk.Button(label="🔌 " + _("Patcheras"))
            btn_patch.connect("clicked", self._ver_patcheras)
            hbox_fila2.pack_start(btn_patch, False, False, 0)

            btn_diag = Gtk.Button(label="🔗 " + _("Diagrama de conexiones"))
            btn_diag.connect("clicked", self._ver_diagrama)
            hbox_fila2.pack_start(btn_diag, False, False, 0)

            btn_rename = Gtk.Button(label="🏷 " + _("Renombrar conectores"))
            btn_rename.connect("clicked", self._renombrar_conectores)
            hbox_fila2.pack_start(btn_rename, False, False, 0)

            btn_rack = Gtk.Button(label="🗄 " + _("Rack del equipo"))
            btn_rack.set_tooltip_text(
                _("Buscar en qué rack está montado este equipo (directo o dentro de un frame) y abrir su vista gráfica"))
            btn_rack.connect("clicked", self._ver_rack)
            hbox_fila2.pack_start(btn_rack, False, False, 0)

            btn_reglas = Gtk.Button(label="🔀 " + _("Reglas lógicas"))
            btn_reglas.set_tooltip_text(
                _("Definir condiciones AND/OR sobre los conectores de entrada "
                  "(ej. \"requiere todas estas entradas para que funcionen las "
                  "salidas\", o \"alcanza con una de estas dos\")"))
            btn_reglas.connect("clicked", self._ver_reglas_logicas)
            hbox_fila2.pack_start(btn_reglas, False, False, 0)

            btn_template = Gtk.Button(label="🧬 " + _("Equipo a template"))
            btn_template.set_tooltip_text(
                _("Crear un molde de catálogo reutilizable a partir de "
                  "este equipo y sus conectores (sin inventario/serie)"))
            btn_template.connect("clicked", self._equipo_a_template)
            hbox_fila3.pack_start(btn_template, False, False, 0)

        btn_coords = Gtk.Button(label="📍 " + _("Ver ubicación"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        hbox_fila3.pack_start(btn_coords, False, False, 0)

        if id_equipo:
            n_problemas = Modelo.devolver_cantidad_problemas_de_equipo(id_equipo)
            etiqueta_problemas = "⚠ Problemas del equipo"
            if n_problemas:
                etiqueta_problemas += f" ({n_problemas})"
            btn_problemas = Gtk.Button(label=etiqueta_problemas)
            btn_problemas.set_tooltip_text(
                _("Ver y cargar los problemas reportados para este equipo "
                  "(categoría, gravedad y descripción)"))
            btn_problemas.connect("clicked", self._ver_problemas)
            hbox_fila3.pack_start(btn_problemas, False, False, 0)

        vbox_main.pack_start(vbox_botones, False, False, 0)

        # Cargar datos si es edición
        if id_equipo:
            rows = Modelo.devolver_equipo(id_equipo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.e_modelo.set_text(s(r[3]))
                self.e_inventario.set_text(s(r[4]))
                self.e_serie.set_text(s(r[5]))
                _set_combo_id(self.c_marca, s(r[6]))
                _set_combo_id(self.c_tipo, s(r[8]))
                self.e_imagen.set_text(s(r[9]))
                self.id_imagen = s(r[10])
                self.e_x.set_text(s(r[11]))
                self.e_y.set_text(s(r[12]))
                self.e_manual.set_text(s(r[13]))
                if r[14]:
                    markdown_text = s(r[14])
                    # Guardar texto sin formato en el editor
                    self.tv_configuraciones_edit.get_buffer().set_text(markdown_text, -1)
                    # Formatear y mostrar en el visor
                    self._render_markdown(markdown_text)
                if len(r) > 15 and r[15]:
                    self.e_picon.set_text(s(r[15]))
                if len(r) > 16 and r[16]:
                    self.e_fecha_fabricacion.set_text(s(r[16]))
                if len(r) > 17 and r[17]:
                    self.chk_equipo_usado.set_active(bool(r[17]))

        self._actualizar_seccion_riesgo()
        self._actualizar_picon_preview()
        _pack_ultima_edicion(self, "equipo", "id_equipo", id_equipo)
        self.show_all()
        
        # Por defecto: mostrar solo el visor (renderizado), ocultar el editor
        self.scrolled_edit.hide()
        self.sep_config.hide()
        self.lbl_preview.hide()

    def _render_markdown(self, markdown_text):
        """Renderiza texto Markdown en self.tv_configuraciones_view."""
        buffer = self.tv_configuraciones_view.get_buffer()
        buffer.set_text(markdown_text)
        
        if not markdown_text.strip():
            return
        
        # Usar tags pre-creados
        tag_bold = self.tag_bold
        tag_italic = self.tag_italic
        tag_mono = self.tag_mono
        tag_large = self.tag_large
        tag_xlarge = self.tag_xlarge
        
        start_iter = buffer.get_start_iter()
        
        # Procesar línea por línea para encabezados
        line_iter = start_iter.copy()
        while line_iter.forward_line():
            line_start = line_iter.copy()
            if not line_iter.forward_to_line_end():
                break
            line_end = line_iter.copy()
            line_text = buffer.get_text(line_start, line_end, False)
            
            stripped = line_text.strip()
            if stripped.startswith('# '):
                tag_start = line_start.copy()
                tag_start.forward_chars(2)
                buffer.apply_tag(tag_xlarge, tag_start, line_end)
            elif stripped.startswith('## '):
                tag_start = line_start.copy()
                tag_start.forward_chars(3)
                buffer.apply_tag(tag_large, tag_start, line_end)
            elif stripped.startswith('### '):
                tag_start = line_start.copy()
                tag_start.forward_chars(4)
                buffer.apply_tag(tag_bold, tag_start, line_end)
        
        # Aplicar formato inline
        self._apply_markdown_tags_global(buffer, tag_bold, r'\*\*(.+?)\*\*', r'__(.+?)__')
        self._apply_markdown_tags_global(buffer, tag_italic, r'\*(.+?)\*', r'(?<!\w)_(.+?)_(?!\w)')
        self._apply_markdown_tags_global(buffer, tag_mono, r'`([^`]+)`')

    def _toggle_edit_configuraciones(self, btn):
        """Alterna entre modo edición y visualización de configuraciones."""
        if self.btn_edit_config.get_label() == "✏️ Editar":
            # Cambiar a modo edición: mostrar editor, ocultar visor
            self.scrolled_edit.show()
            self.sep_config.show()
            self.lbl_preview.show()
            self.scrolled_view.hide()
            self.btn_edit_config.set_label("👁️ Guardar y Ver")
        else:
            # Cambiar a modo visualización: renderizar markdown y mostrar visor
            buf_edit = self.tv_configuraciones_edit.get_buffer()
            start, end = buf_edit.get_bounds()
            markdown_text = buf_edit.get_text(start, end, False)
            
            # Renderizar y mostrar en el visor
            self._render_markdown(markdown_text)
            
            self.scrolled_edit.hide()
            self.sep_config.hide()
            self.lbl_preview.hide()
            self.scrolled_view.show()
            self.btn_edit_config.set_label("✏️ Editar")

    
    def _apply_markdown_tags_global(self, buffer, tag, *patterns):
        """Aplica tags de formato al buffer completo según patrones Markdown."""
        import re
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False)
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                start_offset = start.get_offset() + match.start()
                end_offset = start.get_offset() + match.end()
                start_iter = buffer.get_iter_at_offset(start_offset)
                end_iter = buffer.get_iter_at_offset(end_offset)
                buffer.apply_tag(tag, start_iter, end_iter)

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_manual(self, btn):
        """Seleccionar archivo PDF y copiarlo a manuales/"""
        from modelo import MANUALES_DIR
        import os
        import shutil
        
        # Asegurar que el directorio exista
        os.makedirs(MANUALES_DIR, exist_ok=True)
        
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar Manual PDF"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_default_size(600, 400)
        
        # Filtrar solo archivos PDF
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name(_("Archivos PDF"))
        filter_pdf.add_mime_type("application/pdf")
        filter_pdf.add_pattern("*.pdf")
        filter_pdf.add_pattern("*.PDF")
        dialog.add_filter(filter_pdf)
        
        # Filtrar todos los archivos
        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos los archivos"))
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        # Establecer el directorio manuales como ubicación inicial
        dialog.set_current_folder(MANUALES_DIR)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            source_path = dialog.get_filename()
            if source_path:
                # Extraer nombre de archivo
                filename = os.path.basename(source_path)
                # Crear path destino
                dest_path = os.path.join(MANUALES_DIR, filename)
                
                # Verificar si el archivo ya está en manuales/
                if os.path.abspath(source_path) == os.path.abspath(dest_path):
                    # El archivo ya está en manuales/, solo guardar el nombre
                    self.e_manual.set_text(filename)
                else:
                    # Copiar archivo a manuales/
                    try:
                        shutil.copy2(source_path, dest_path)
                        # Guardar solo el nombre del archivo
                        self.e_manual.set_text(filename)
                    except Exception as e:
                        dlg = Gtk.MessageDialog(
                            transient_for=self,
                            modal=True,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.OK,
                            text=f"Error al copiar el archivo: {e}"
                        )
                        dlg.run()
                        dlg.destroy()
        
        dialog.destroy()

    def _ver_manual(self, btn):
        """Abre el manual PDF con el visor del sistema."""
        import subprocess
        import os
        from modelo import MANUALES_DIR
        
        manual_filename = self.e_manual.get_text().strip()
        if not manual_filename:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="No hay manual PDF seleccionado"
            )
            dlg.run()
            dlg.destroy()
            return
        
        # Construir el path completo al archivo PDF
        manual_path = os.path.join(MANUALES_DIR, manual_filename)
        
        # Verificar que el archivo exista
        if not os.path.isfile(manual_path):
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Archivo no encontrado:\n{manual_path}"
            )
            dlg.run()
            dlg.destroy()
            return
        
        # Abrir con el visor del sistema
        try:
            if os.name == "posix":  # Linux/Mac
                # Probar diferentes comandos para abrir PDF
                for cmd in ["xdg-open", "evince", "okular", "firefox", "google-chrome"]:
                    try:
                        subprocess.Popen([cmd, manual_path],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    raise FileNotFoundError("No se encontró ningún visor de PDF instalado (xdg-open, evince, okular, firefox)")
            elif os.name == "nt":  # Windows
                os.startfile(manual_path)
            else:
                subprocess.Popen(["open", manual_path],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        except Exception as e:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Error al abrir el PDF: {e}"
            )
            dlg.run()
            dlg.destroy()

    def _sel_picon(self, btn):
        """Seleccionar una foto del equipo y copiarla a picon/"""
        os.makedirs(PICON_DIR, exist_ok=True)

        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_default_size(600, 400)

        filter_img = Gtk.FileFilter()
        filter_img.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filter_img.add_pattern(pat)
        dialog.add_filter(filter_img)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos los archivos"))
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        dialog.set_current_folder(PICON_DIR)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            source_path = dialog.get_filename()
            if source_path:
                filename = os.path.basename(source_path)
                dest_path = os.path.join(PICON_DIR, filename)
                try:
                    if os.path.abspath(source_path) != os.path.abspath(dest_path):
                        shutil.copy2(source_path, dest_path)
                    self.e_picon.set_text(filename)
                    self._actualizar_picon_preview()
                except Exception as e:
                    dlg = Gtk.MessageDialog(
                        transient_for=self,
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=f"Error al copiar la foto: {e}"
                    )
                    dlg.run()
                    dlg.destroy()

        dialog.destroy()

    def _quitar_picon(self, btn):
        """Quita la referencia a la foto (no borra el archivo físico)."""
        self.e_picon.set_text("")
        self._actualizar_picon_preview()

    def _actualizar_picon_preview(self):
        """Actualiza la miniatura de vista previa de la foto del equipo."""
        filename = self.e_picon.get_text().strip()
        if filename:
            ruta = os.path.join(PICON_DIR, filename)
            if os.path.isfile(ruta):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, 140, 140, True)
                    self.img_picon.set_from_pixbuf(pixbuf)
                    return
                except Exception:
                    pass
        self.img_picon.clear()

    def _sel_marca_dropdown(self, btn):
        """Abre el ABM de Marcas para buscar/crear y seleccionar una marca."""
        from cabledoc import MarcasListado
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_ = dlg.resultado_id
            # Recargar el combo (por si se creó una marca nueva en el ABM)
            _repopulate_combo(self.c_marca, Modelo.devolver_todas_las_marcas())
            _set_combo_id(self.c_marca, id_)
        dlg.destroy()

    def _sel_tipo_dropdown(self, btn):
        """Abre el ABM de Tipos de Equipo para buscar/crear y seleccionar un tipo."""
        from cabledoc import TiposEquipoListado
        dlg = TiposEquipoListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_ = dlg.resultado_id
            # Recargar el combo (por si se creó un tipo nuevo en el ABM)
            _repopulate_combo(self.c_tipo, Modelo.devolver_todos_los_tipos())
            _set_combo_id(self.c_tipo, id_)
        dlg.destroy()

    def _ver_conectores(self, btn):
        from cabledoc import ConectoresListado
        dlg = ConectoresListado(id_equipo=self.id_equipo, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_imagen_conectores(self, btn):
        abrir_imagen_conectores(self.id_equipo, parent=self)

    def _ver_editor_masivo_conectores(self, btn):
        from cabledoc import ImagenesListado
        def _fn_img(p):
            d = ImagenesListado(parent=p, modo_seleccion=True)
            r = None
            if d.run() == Gtk.ResponseType.OK:
                r = (d.resultado_nombre, d.resultado_id)
            d.destroy()
            return r
        abrir_editor_masivo_conectores(self.id_equipo, parent=self, fn_sel_imagen=_fn_img)

    def _ver_arbol(self, btn):
        abrir_arbol_conexiones(self.id_equipo, parent=self)

    def _ver_patcheras(self, btn):
        nombre = self.e_nombre.get_text().strip()
        abrir_patcheras(self.id_equipo, nombre_equipo=nombre, parent=self)

    def _ver_diagrama(self, btn):
        abrir_diagrama_conexiones(id_equipo=self.id_equipo, parent=self)

    def _renombrar_conectores(self, btn):
        from cabledoc import _DialogoRenombrarConectores
        dlg = _DialogoRenombrarConectores(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def _ver_rack(self, btn):
        """Busca el rack donde está montado este equipo (directo o dentro
        de un frame) y abre su vista gráfica. Si no está rackeado,
        muestra un diálogo avisando."""
        filas = Modelo.devolver_rack_de_equipo(self.id_equipo)
        if not filas:
            mostrar_info(self, _("Equipo no rackeado"))
            return
        id_rack = filas[0][0]
        abrir_vista_rack(id_rack=id_rack, parent=self)

    def _ver_reglas_logicas(self, btn):
        """Abre el editor de reglas lógicas (AND/OR) de este equipo."""
        nombre = self.e_nombre.get_text().strip() or f"Equipo #{self.id_equipo}"
        abrir_reglas_logicas(self.id_equipo, nombre, self.id_tipo or None, parent=self)

    def _ver_problemas(self, btn):
        """Abre el listado de problemas cargados para este equipo
        (tabla problema_equipo: categoría, gravedad y descripción)."""
        from cabledoc import ProblemasEquipoListado
        dlg = ProblemasEquipoListado(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def _actualizar_seccion_riesgo(self):
        """Pinta la sección '🔺 Riesgo de falla' con el último valor
        calculado (cacheado en riesgo_equipo_cache). No recalcula solo:
        para eso está el botón 'Recalcular'."""
        if not self.id_equipo:
            self.lbl_riesgo_score.set_text(
                _("Se calcula una vez guardado el equipo."))
            self.lbl_riesgo_detalle.set_text("")
            self.chk_equipo_critico.set_sensitive(False)
            return
        self.chk_equipo_critico.set_sensitive(True)
        self._cargando_critico = True
        self.chk_equipo_critico.set_active(Modelo.es_equipo_critico(self.id_equipo))
        self._cargando_critico = False
        fila = Modelo.devolver_riesgo_equipo(self.id_equipo)
        if not fila:
            self.lbl_riesgo_score.set_markup(
                "<i>" + _("Todavía no calculado. Usá 'Recalcular'.") + "</i>")
            self.lbl_riesgo_detalle.set_text("")
            return
        probabilidad, impacto, riesgo, nivel, detalle_json, fecha_calculo = fila
        colores_hex = {"Crítico": "#d92626", "Alto": "#e68c1a",
                       "Medio": "#e6c11a", "Bajo": "#26a642"}
        color = colores_hex.get(nivel, "#666666")
        self.lbl_riesgo_score.set_markup(
            f"<span foreground='{color}'><b>{riesgo:.0f}/100 · {nivel}</b></span>"
            f"   (Probabilidad {probabilidad:.0f} × Impacto {impacto:.0f})")
        try:
            det = json.loads(detalle_json) if detalle_json else {}
        except Exception:
            det = {}
        partes = []
        if det.get("edad_anios") is not None:
            partes.append(_("Antigüedad: {a:.1f} años (vida útil {v:.0f})").format(
                a=det["edad_anios"], v=det.get("vida_util_anios") or 0))
        else:
            partes.append(_("Antigüedad: sin fecha de fabricación cargada"))
        partes.append(_("Historial: {n} problema(s) registrados").format(
            n=det.get("cantidad_problemas", 0)))
        if det.get("equipos_impactados") is not None:
            partes.append(_("Si falla, quedan sin señal {e} equipo(s)").format(
                e=det["equipos_impactados"]))
        elif not det.get("grafo_disponible", True):
            partes.append(_("(criticidad de red no disponible en este cálculo)"))
        if det.get("modo_impacto") == "criticos":
            partes.append(_("Impacto medido sobre el conjunto crítico: "
                            "{c} de {t} crítico(s) afectado(s)").format(
                c=det.get("criticos_impactados", 0),
                t=det.get("criticos_totales", 0)))
        partes.append(_("Calculado: {f}").format(f=fecha_calculo or "—"))
        self.lbl_riesgo_detalle.set_text("  ·  ".join(partes))

    def _on_toggle_critico(self, chk):
        if getattr(self, "_cargando_critico", False) or not self.id_equipo:
            return
        Modelo.establecer_equipo_critico(self.id_equipo, chk.get_active())
        self._status_riesgo_critico(chk.get_active())

    def _status_riesgo_critico(self, activo):
        texto = (_("Marcado como equipo crítico de la cadena.") if activo
                 else _("Sacado del conjunto de equipos críticos."))
        self.lbl_riesgo_detalle.set_text(
            texto + " " + _("Usá 'Recalcular' para reflejarlo en el score."))

    def _recalcular_riesgo(self, btn):
        from risk_engine import RiskEngine
        self.set_sensitive(False)
        try:
            RiskEngine(DB_PATH).calcular_todos()
        except Exception as e:
            mostrar_error(self, f"{_('No se pudo calcular el riesgo')}:\n{e}")
        finally:
            self.set_sensitive(True)
        self._actualizar_seccion_riesgo()

    def _ver_equipos_afectados(self, btn):
        """plan_simular_remocion_cadena.md — simula la falla de este
        equipo completo y muestra qué otros equipos/cables quedan sin
        señal, y qué señales con nombre se pierden. Reemplaza la versión
        anterior (que solo listaba equipos) delegando en el mismo helper
        único de impacto_ui.py que usan Cable/Rack/Conexión — antes cada
        uno tenía su propio diálogo ad-hoc con menos información
        (faltaban cables_impactados y señales caídas)."""
        if not self.id_equipo:
            mostrar_error(self, _("Guardá el equipo primero."))
            return
        from impacto_ui import simular_remocion_y_mostrar
        nombre = self.e_nombre.get_text().strip() or f"Equipo {self.id_equipo}"
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {nombre}",
            "simular_falla_equipo", self.id_equipo)

    def _equipo_a_template(self, btn):
        """Crea un molde de catálogo (equipo_catalogo) a partir de este
        equipo: copia tipo, marca, modelo, imagen, manual y configuraciones,
        más sus conectores (nombre, tipo, imagen y coordenadas). NO copia
        inventario ni número de serie, que son propios de esta instancia."""
        if not self.id_equipo:
            return
        nombre_actual = self.e_nombre.get_text().strip() or "Equipo"
        dlg = DialogoNombre(
            _("Equipo a template"), etiqueta=_("Nombre del molde:"),
            valor=f"{nombre_actual} (molde)", parent=self)
        ok = dlg.run() == Gtk.ResponseType.OK
        valor = dlg.valor
        dlg.destroy()
        if not ok or not valor:
            return
        resultado = Modelo.crear_catalogo_desde_equipo(self.id_equipo, valor)
        if resultado:
            id_cat, n_con = resultado
            mostrar_info(self,
                f"Molde «{valor}» creado (ID {id_cat}) con {n_con} conector(es).\n\n"
                "Podés verlo/editarlo en Equipos → 📦 Catálogo de Equipos.")
        else:
            mostrar_error(self, "No se pudo crear el molde.")

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_marca = _get_combo_id(self.c_marca)
            id_tipo  = _get_combo_id(self.c_tipo)
            path_manual = self.e_manual.get_text().strip()
            picon = self.e_picon.get_text().strip()
            fecha_fabricacion = self.e_fecha_fabricacion.get_text().strip()
            es_equipo_usado = self.chk_equipo_usado.get_active()
            # Obtener texto de configuraciones desde el editor
            buf = self.tv_configuraciones_edit.get_buffer()
            start, end = buf.get_bounds()
            configuraciones = buf.get_text(start, end, False).strip()
            
            if self.id_equipo:
                Modelo.modificacion_equipo(
                    self.id_equipo,
                    id_tipo or None, id_marca or None,
                    self.e_inventario.get_text(),
                    self.e_serie.get_text(),
                    self.e_modelo.get_text(),
                    self.e_nombre.get_text(),
                    self.id_imagen or None,
                    self.e_x.get_text(), self.e_y.get_text(),
                    path_manual if path_manual else None,
                    configuraciones if configuraciones else None,
                    picon if picon else None,
                    fecha_fabricacion if fecha_fabricacion else None,
                    es_equipo_usado
                )
            else:
                Modelo.alta_equipo(
                    id_tipo or None, id_marca or None,
                    self.e_inventario.get_text(),
                    self.e_serie.get_text(),
                    self.e_modelo.get_text(),
                    self.e_nombre.get_text(),
                    self.id_imagen or None,
                    self.e_x.get_text(), self.e_y.get_text(),
                    path_manual if path_manual else None,
                    configuraciones if configuraciones else None,
                    picon if picon else None,
                    fecha_fabricacion if fecha_fabricacion else None,
                    es_equipo_usado
                )
        
        # Limpiar buffers de TextView para liberar memoria antes de destruir
        try:
            self.tv_configuraciones_edit.get_buffer().set_text("")
            self.tv_configuraciones_view.get_buffer().set_text("")
        except Exception:
            pass  # Ignorar errores si los widgets ya no existen
        
        self.destroy()
