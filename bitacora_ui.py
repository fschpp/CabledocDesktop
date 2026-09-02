"""
bitacora_ui.py — UI de la Bitácora de Incidentes (Fase C)
============================================================================
Fase C de plan_desarrollo_bitacora_incidentes.md, sobre el esquema y CRUD
ya agregados a modelo.py (Fase A/B) y el motor de agregación de
riesgo_analogico.py (Fase B.2). La Fase D (overlay "🌡 Zona caliente" en
DiagramaConexiones + panel de pendientes del Home) se agrega en un paso
posterior, sobre este mismo archivo (BitacoraMixin).

Integración en cabledoc.py:
  - Importar `abrir_bitacora_incidentes` (directo desde acá, o re-exportado
    desde pantallas_avanzadas.py una vez se agregue la Fase D — mismo
    patrón que abrir_historial_diagnosticos en diagnostico_ui.py).
  - Agregar botón "📋 Ver incidentes" a EquiposListado y CablesListado,
    mismo patrón exacto que el botón "🩺 Historial de diagnósticos" ya
    existente en ambos.
  - Agregar sección "Armado" a _DialogoConector y _DialogoCable (ver
    Fase C.2 del plan; no vive en este archivo, se edita cabledoc.py
    directamente porque son diálogos ya existentes ahí).

Nota de diseño: para evitar el ciclo de imports cabledoc.py → 
pantallas_avanzadas.py → bitacora_ui.py → cabledoc.py, los selectores de
equipo/cable (EquiposListado/CablesListado) se importan de forma diferida
(dentro del método que los usa), mismo criterio ya establecido en
pantallas_avanzadas.py (ver _sel_equipo de ArbolConexionesEquipo).
"""

from __future__ import annotations

from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modelo import Modelo

try:
    from i18n import _
except ImportError:
    def _(t): return t


def s(v):
    return "" if v is None else str(v)


# ═══════════════════════════════════════════════════════════════════════════
# Selector reutilizable de N elementos (equipos / cables / zonas)
# ═══════════════════════════════════════════════════════════════════════════

class _SelectorMultiple(Gtk.Box):
    """Lista chica de pares (id, nombre) con botones ➕/➖.
    `fn_agregar()` debe devolver (id, nombre) o None si el usuario canceló
    el selector. No permite duplicados (mismo id dos veces)."""

    def __init__(self, titulo, fn_agregar):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl = Gtk.Label(label=titulo, xalign=0)
        self.pack_start(lbl, False, False, 0)

        self.store = Gtk.ListStore(str, str)   # id, nombre
        self._tv = Gtk.TreeView(model=self.store)
        self._tv.set_headers_visible(False)
        col = Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=4), text=1)
        col.set_expand(True)
        self._tv.append_column(col)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(64)
        sw.add(self._tv)
        self.pack_start(sw, True, True, 0)

        hb = Gtk.Box(spacing=4)
        btn_add = Gtk.Button(label="➕")
        btn_add.connect("clicked", self._on_agregar)
        btn_del = Gtk.Button(label="➖")
        btn_del.connect("clicked", self._on_quitar)
        hb.pack_start(btn_add, False, False, 0)
        hb.pack_start(btn_del, False, False, 0)
        self.pack_start(hb, False, False, 0)

        self._fn_agregar = fn_agregar

    def _on_agregar(self, _btn):
        par = self._fn_agregar()
        if not par or par[0] in (None, ""):
            return
        id_, nombre = par
        for row in self.store:
            if row[0] == str(id_):
                return   # ya estaba, no duplicar
        self.store.append([str(id_), s(nombre)])

    def _on_quitar(self, _btn):
        sel = self._tv.get_selection()
        _model, it = sel.get_selected()
        if it is not None:
            self.store.remove(it)

    def ids(self):
        return [row[0] for row in self.store]

    def set_pares(self, pares):
        self.store.clear()
        for id_, nombre in pares:
            self.store.append([str(id_), s(nombre)])


# ═══════════════════════════════════════════════════════════════════════════
# Zonas sospechosas
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoZonaSospechosa(Gtk.Dialog):
    """Alta/edición de una zona sospechosa (conjunto reutilizable de
    equipos — ver plan_bitacora_incidentes_riesgo_analogico.md §3.2)."""

    def __init__(self, id_zona=None, parent=None):
        titulo = "Editar zona" if id_zona else "Nueva zona sospechosa"
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                         "Aceptar", Gtk.ResponseType.OK)
        self.set_default_size(360, 380)
        self.id_zona = id_zona

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)

        hb_nombre = Gtk.Box(spacing=6)
        hb_nombre.pack_start(Gtk.Label(label=_("Nombre:")), False, False, 0)
        self.e_nombre = Gtk.Entry(hexpand=True)
        hb_nombre.pack_start(self.e_nombre, True, True, 0)
        area.pack_start(hb_nombre, False, False, 0)

        self.sel_equipos = _SelectorMultiple(
            "Equipos que componen la zona:", self._agregar_equipo)
        area.pack_start(self.sel_equipos, True, True, 0)

        if id_zona:
            fila = Modelo.devolver_zona(id_zona)
            if fila:
                self.e_nombre.set_text(s(fila[1]))
            self.sel_equipos.set_pares(Modelo.devolver_equipos_de_zona(id_zona))

        self.show_all()

    def _agregar_equipo(self):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        resultado = None
        if dlg.run() == Gtk.ResponseType.OK:
            resultado = (dlg.resultado_id, dlg.resultado_nombre)
        dlg.destroy()
        return resultado

    def run_and_destroy(self):
        """Corre el diálogo, persiste el resultado, y devuelve el id_zona
        final (nuevo o editado), o None si se canceló / faltó el nombre."""
        id_zona_resultado = None
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            if nombre:
                ids_eq = set(self.sel_equipos.ids())
                if self.id_zona:
                    Modelo.renombrar_zona_sospechosa(self.id_zona, nombre)
                    actuales = {str(r[0]) for r in
                               Modelo.devolver_equipos_de_zona(self.id_zona)}
                    for id_eq in actuales - ids_eq:
                        Modelo.quitar_equipo_de_zona(self.id_zona, id_eq)
                    for id_eq in ids_eq - actuales:
                        Modelo.asignar_equipo_a_zona(self.id_zona, id_eq)
                    id_zona_resultado = self.id_zona
                else:
                    id_zona_resultado = Modelo.crear_zona_sospechosa(
                        nombre, ids_equipo=list(ids_eq))
        self.destroy()
        return id_zona_resultado


class _DialogoElegirZona(Gtk.Dialog):
    """Diálogo chico: elegir una zona existente de la lista, o crear una
    nueva sin salir de acá. self.resultado = (id_zona, nombre) al aceptar,
    o None si se canceló."""

    def __init__(self, parent=None):
        super().__init__(title="Elegir zona sospechosa", transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(360, 320)
        self.resultado = None

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        self.store = Gtk.ListStore(str, str)   # id, nombre
        tv = Gtk.TreeView(model=self.store)
        tv.set_headers_visible(False)
        tv.append_column(
            Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=4), text=1))
        tv.connect("row-activated", lambda *_a: self._usar())
        self._tv = tv
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

        hb = Gtk.Box(spacing=6)
        btn_nueva = Gtk.Button(label=_("➕ Nueva zona…"))
        btn_nueva.connect("clicked", self._nueva)
        btn_usar = Gtk.Button(label=_("✔ Usar"))
        btn_usar.connect("clicked", lambda _b: self._usar())
        hb.pack_start(btn_nueva, False, False, 0)
        hb.pack_start(btn_usar, False, False, 0)
        area.pack_start(hb, False, False, 0)

        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        for id_zona, nombre, _n_eq in Modelo.devolver_zonas():
            self.store.append([str(id_zona), nombre])

    def _usar(self):
        sel = self._tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return
        self.resultado = (model.get_value(it, 0), model.get_value(it, 1))
        self.response(Gtk.ResponseType.OK)

    def _nueva(self, _btn):
        dlg = _DialogoZonaSospechosa(parent=self)
        id_zona = dlg.run_and_destroy()
        if not id_zona:
            return
        self._cargar()
        for row in self.store:
            if row[0] == str(id_zona):
                self._tv.get_selection().select_iter(row.iter)
                break
        self._usar()


# ═══════════════════════════════════════════════════════════════════════════
# Incidente
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoIncidente(Gtk.Dialog):
    def __init__(self, id_incidente=None, parent=None,
                id_equipo_predef=None, id_cable_predef=None,
                id_zona_predef=None):
        titulo = "Editar incidente" if id_incidente else "Nuevo incidente"
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                         "Aceptar", Gtk.ResponseType.OK)
        self.set_default_size(600, 640)
        self.id_incidente = id_incidente

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)

        g = Gtk.Grid(column_spacing=8, row_spacing=6)
        g.attach(Gtk.Label(label=_("Fecha y hora:"), xalign=1), 0, 0, 1, 1)
        hb_f = Gtk.Box(spacing=4)
        self.e_fecha = Gtk.Entry(hexpand=True)
        self.e_fecha.set_placeholder_text("AAAA-MM-DD HH:MM:SS")
        btn_hoy = Gtk.Button(label=_("Hoy"))
        btn_hoy.connect("clicked", self._hoy)
        hb_f.pack_start(self.e_fecha, True, True, 0)
        hb_f.pack_start(btn_hoy, False, False, 0)
        g.attach(hb_f, 1, 0, 1, 1)

        g.attach(Gtk.Label(label=_("Resumen:"), xalign=1), 0, 1, 1, 1)
        self.e_resumen = Gtk.Entry(hexpand=True)
        g.attach(self.e_resumen, 1, 1, 1, 1)

        g.attach(Gtk.Label(label=_("Estado:"), xalign=1), 0, 2, 1, 1)
        self.c_estado = Gtk.ComboBoxText()
        self.c_estado.append("MITIGADO", "Mitigado (puede volver)")
        self.c_estado.append("RESUELTO", "Resuelto")
        self.c_estado.set_active_id("MITIGADO")
        g.attach(self.c_estado, 1, 2, 1, 1)
        area.pack_start(g, False, False, 0)

        lbl_relato = Gtk.Label(label=_("Relato (pegar el texto tal cual):"), xalign=0)
        lbl_relato.set_margin_top(4)
        area.pack_start(lbl_relato, False, False, 0)
        sw_relato = Gtk.ScrolledWindow()
        sw_relato.set_min_content_height(180)
        self.tv_relato = Gtk.TextView()
        self.tv_relato.set_wrap_mode(Gtk.WrapMode.WORD)
        sw_relato.add(self.tv_relato)
        area.pack_start(sw_relato, True, True, 0)

        hb_sel = Gtk.Box(spacing=10, homogeneous=True)
        hb_sel.set_margin_top(4)
        self.sel_equipos = _SelectorMultiple("Equipos:", self._agregar_equipo)
        self.sel_cables = _SelectorMultiple("Cables:", self._agregar_cable)
        self.sel_zonas = _SelectorMultiple("Zonas:", self._agregar_zona)
        hb_sel.pack_start(self.sel_equipos, True, True, 0)
        hb_sel.pack_start(self.sel_cables, True, True, 0)
        hb_sel.pack_start(self.sel_zonas, True, True, 0)
        area.pack_start(hb_sel, False, False, 0)

        if id_incidente:
            fila = Modelo.devolver_incidente(id_incidente)
            if fila:
                self.e_fecha.set_text(s(fila[1]))
                self.e_resumen.set_text(s(fila[2]))
                self.tv_relato.get_buffer().set_text(s(fila[3]) or "")
                self.c_estado.set_active_id(s(fila[4]) or "MITIGADO")
            self.sel_equipos.set_pares(
                Modelo.devolver_equipos_de_incidente(id_incidente))
            self.sel_cables.set_pares(
                Modelo.devolver_cables_de_incidente(id_incidente))
            self.sel_zonas.set_pares(
                Modelo.devolver_zonas_de_incidente(id_incidente))
        else:
            self._hoy(None)
            if id_equipo_predef:
                rows = Modelo._query(
                    "SELECT nombre FROM equipo WHERE id_equipo=?",
                    (id_equipo_predef,))
                nombre = s(rows[0][0]) if rows else str(id_equipo_predef)
                self.sel_equipos.set_pares([(id_equipo_predef, nombre)])
            if id_cable_predef:
                rows = Modelo._query(
                    "SELECT codigo FROM cable WHERE id_cable=?",
                    (id_cable_predef,))
                codigo = s(rows[0][0]) if rows else str(id_cable_predef)
                self.sel_cables.set_pares([(id_cable_predef, codigo)])
            if id_zona_predef:
                fila_z = Modelo.devolver_zona(id_zona_predef)
                if fila_z:
                    self.sel_zonas.set_pares([(fila_z[0], fila_z[1])])

        self.show_all()

    def _hoy(self, _btn):
        self.e_fecha.set_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _agregar_equipo(self):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        resultado = None
        if dlg.run() == Gtk.ResponseType.OK:
            resultado = (dlg.resultado_id, dlg.resultado_nombre)
        dlg.destroy()
        return resultado

    def _agregar_cable(self):
        from cabledoc import CablesListado
        dlg = CablesListado(parent=self, modo_seleccion=True)
        resultado = None
        if dlg.run() == Gtk.ResponseType.OK:
            resultado = (dlg.resultado_id, dlg.resultado_nombre)
        dlg.destroy()
        return resultado

    def _agregar_zona(self):
        dlg = _DialogoElegirZona(parent=self)
        resultado = None
        if dlg.run() == Gtk.ResponseType.OK and dlg.resultado:
            resultado = dlg.resultado
        dlg.destroy()
        return resultado

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            fecha = self.e_fecha.get_text().strip()
            resumen = self.e_resumen.get_text().strip()
            buf = self.tv_relato.get_buffer()
            relato = buf.get_text(
                buf.get_start_iter(), buf.get_end_iter(), True).strip() or None
            estado = self.c_estado.get_active_id() or "MITIGADO"
            ids_eq = self.sel_equipos.ids()
            ids_cb = self.sel_cables.ids()
            ids_zn = self.sel_zonas.ids()
            if fecha and resumen:
                if self.id_incidente:
                    Modelo.modificar_incidente(
                        self.id_incidente, fecha, resumen, relato, estado,
                        ids_equipo=ids_eq, ids_cable=ids_cb, ids_zona=ids_zn)
                else:
                    Modelo.crear_incidente(
                        fecha, resumen, relato, estado,
                        ids_equipo=ids_eq, ids_cable=ids_cb, ids_zona=ids_zn)
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Listado principal
# ═══════════════════════════════════════════════════════════════════════════

class BitacoraIncidentesListado(Gtk.Dialog):
    _COLUMNAS = ["ID", "Fecha", "Resumen", "Estado"]

    def __init__(self, parent=None, id_equipo=None, id_cable=None, id_zona=None):
        titulo = "📋 Bitácora de incidentes"
        if id_equipo:
            titulo += f" — equipo {id_equipo}"
        elif id_cable:
            titulo += f" — cable {id_cable}"
        elif id_zona:
            titulo += f" — zona {id_zona}"
        super().__init__(title=titulo, transient_for=parent, destroy_with_parent=True)
        self.set_default_size(760, 460)
        self._id_equipo = id_equipo
        self._id_cable = id_cable
        self._id_zona = id_zona

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        hb_f = Gtk.Box(spacing=6)
        hb_f.pack_start(Gtk.Label(label=_("Filtro:")), False, False, 0)
        self.e_filtro = Gtk.SearchEntry(hexpand=True)
        self.e_filtro.connect("search-changed", lambda _e: self._cargar())
        hb_f.pack_start(self.e_filtro, True, True, 0)
        area.pack_start(hb_f, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        self.store = Gtk.ListStore(*([str] * len(self._COLUMNAS)))
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.connect("row-activated", self._on_doble_click)
        for i, titulo_col in enumerate(self._COLUMNAS):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(i == 2)
            if i == 0:
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        fila_botones = Gtk.Box(spacing=6)
        btn_nuevo = Gtk.Button(label=_("➕ Nuevo incidente"))
        btn_nuevo.connect("clicked", lambda _b: self._nuevo())
        btn_editar = Gtk.Button(label=_("✏️ Editar"))
        btn_editar.connect("clicked", lambda _b: self._editar())
        btn_eliminar = Gtk.Button(label=_("🗑 Eliminar"))
        btn_eliminar.connect("clicked", lambda _b: self._eliminar())
        fila_botones.pack_start(btn_nuevo, False, False, 0)
        fila_botones.pack_start(btn_editar, False, False, 0)
        fila_botones.pack_start(btn_eliminar, False, False, 0)
        area.pack_start(fila_botones, False, False, 0)

        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        filas = Modelo.devolver_todos_los_incidentes(
            filtro_texto=self.e_filtro.get_text().strip() or None,
            id_equipo=self._id_equipo, id_cable=self._id_cable,
            id_zona=self._id_zona)
        for f in filas:
            self.store.append([s(f[0]), s(f[1]), s(f[2]), s(f[3])])
        if not filas:
            self.store.append(
                ["", "", "(sin incidentes registrados todavía)", ""])

    def _fila_seleccionada(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None
        return model.get_value(it, 0) or None

    def _on_doble_click(self, *_a):
        self._editar()

    def _nuevo(self):
        dlg = _DialogoIncidente(
            parent=self, id_equipo_predef=self._id_equipo,
            id_cable_predef=self._id_cable, id_zona_predef=self._id_zona)
        dlg.run_and_destroy()
        self._cargar()

    def _editar(self):
        id_incidente = self._fila_seleccionada()
        if not id_incidente:
            return
        dlg = _DialogoIncidente(id_incidente=id_incidente, parent=self)
        dlg.run_and_destroy()
        self._cargar()

    def _eliminar(self):
        id_incidente = self._fila_seleccionada()
        if not id_incidente:
            return
        confirmar = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"¿Eliminar el incidente #{id_incidente}?")
        resp = confirmar.run()
        confirmar.destroy()
        if resp == Gtk.ResponseType.YES:
            Modelo.eliminar_incidente(id_incidente)
            self._cargar()


def abrir_bitacora_incidentes(parent=None, id_equipo=None, id_cable=None,
                              id_zona=None):
    dlg = BitacoraIncidentesListado(
        parent=parent, id_equipo=id_equipo, id_cable=id_cable, id_zona=id_zona)
    dlg.run()
    dlg.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Listado de zonas sospechosas (punto de entrada independiente de un
# equipo/cable puntual — Catálogos → "📋 Zonas sospechosas")
# ═══════════════════════════════════════════════════════════════════════════

class ZonasSospechosasListado(Gtk.Dialog):
    """Punto de entrada general a las zonas sospechosas: hasta ahora una
    zona solo se podía crear/editar "de paso" desde el selector de zonas
    de un incidente (_DialogoElegirZona), sin ningún lugar donde
    consultarlas o entrar a ver sus incidentes directamente. Mismo patrón
    de listado que BitacoraIncidentesListado."""

    _COLUMNAS = ["ID", "Nombre", "Equipos"]

    def __init__(self, parent=None):
        super().__init__(title="📋 " + _("Zonas sospechosas"),
                         transient_for=parent, destroy_with_parent=True)
        self.set_default_size(480, 420)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        self.store = Gtk.ListStore(str, str, str)
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.connect("row-activated", self._on_doble_click)
        for i, titulo_col in enumerate(self._COLUMNAS):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(i == 1)
            if i == 0:
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        fila_botones = Gtk.Box(spacing=6)
        btn_nueva = Gtk.Button(label=_("➕ Nueva zona…"))
        btn_nueva.connect("clicked", lambda _b: self._nueva())
        btn_editar = Gtk.Button(label=_("✏️ Editar"))
        btn_editar.connect("clicked", lambda _b: self._editar())
        btn_eliminar = Gtk.Button(label=_("🗑 Eliminar"))
        btn_eliminar.connect("clicked", lambda _b: self._eliminar())
        btn_incidentes = Gtk.Button(label=_("📋 Ver incidentes"))
        btn_incidentes.connect("clicked", lambda _b: self._ver_incidentes())
        fila_botones.pack_start(btn_nueva, False, False, 0)
        fila_botones.pack_start(btn_editar, False, False, 0)
        fila_botones.pack_start(btn_eliminar, False, False, 0)
        fila_botones.pack_start(btn_incidentes, False, False, 0)
        area.pack_start(fila_botones, False, False, 0)

        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        filas = Modelo.devolver_zonas()
        for id_zona, nombre, n_equipos in filas:
            self.store.append([s(id_zona), s(nombre), s(n_equipos)])
        if not filas:
            self.store.append(["", "(sin zonas sospechosas todavía)", ""])

    def _fila_seleccionada(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None
        return model.get_value(it, 0) or None

    def _on_doble_click(self, *_a):
        self._ver_incidentes()

    def _nueva(self):
        dlg = _DialogoZonaSospechosa(parent=self)
        dlg.run_and_destroy()
        self._cargar()

    def _editar(self):
        id_zona = self._fila_seleccionada()
        if not id_zona:
            return
        dlg = _DialogoZonaSospechosa(id_zona=id_zona, parent=self)
        dlg.run_and_destroy()
        self._cargar()

    def _eliminar(self):
        id_zona = self._fila_seleccionada()
        if not id_zona:
            return
        confirmar = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("¿Eliminar la zona sospechosa seleccionada?"),
            secondary_text=_(
                "También se quitará de los incidentes que la tengan "
                "asociada (el incidente en sí no se borra)."))
        resp = confirmar.run()
        confirmar.destroy()
        if resp == Gtk.ResponseType.YES:
            Modelo.eliminar_zona(id_zona)
            self._cargar()

    def _ver_incidentes(self):
        id_zona = self._fila_seleccionada()
        if not id_zona:
            return
        abrir_bitacora_incidentes(parent=self, id_zona=id_zona)
        self._cargar()


def abrir_zonas_sospechosas(parent=None):
    dlg = ZonasSospechosasListado(parent=parent)
    dlg.run()
    dlg.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Configuración del score de riesgo analógico
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoConfigRiesgoAnalogico(Gtk.Dialog):
    _CAMPOS = [
        ("ventana_meses_incidentes", "Ventana de incidentes (meses):"),
        ("peso_incidente",           "Peso por incidente:"),
        ("peso_armado_incorrecto",   "Peso por armado incorrecto:"),
        ("corte_medio",              "Corte BAJO → MEDIO:"),
        ("corte_alto",               "Corte MEDIO → ALTO:"),
    ]

    def __init__(self, parent=None):
        super().__init__(title="Configuración de riesgo analógico",
                         transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                         "Aceptar", Gtk.ResponseType.OK)
        self.set_default_size(380, -1)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)
        g = Gtk.Grid(column_spacing=8, row_spacing=6)
        area.pack_start(g, False, False, 0)

        config = Modelo.devolver_config_riesgo_analogico()
        self._entries = {}
        for i, (clave, etiqueta) in enumerate(self._CAMPOS):
            g.attach(Gtk.Label(label=etiqueta, xalign=1), 0, i, 1, 1)
            e = Gtk.Entry(hexpand=True)
            e.set_text(str(config.get(clave, "")))
            g.attach(e, 1, i, 1, 1)
            self._entries[clave] = e

        self.show_all()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            for clave, entry in self._entries.items():
                txt = entry.get_text().strip()
                try:
                    valor = float(txt)
                except ValueError:
                    continue
                Modelo.establecer_config_riesgo_analogico(clave, valor)
        self.destroy()


def abrir_config_riesgo_analogico(parent=None):
    dlg = _DialogoConfigRiesgoAnalogico(parent=parent)
    dlg.run_and_destroy()
