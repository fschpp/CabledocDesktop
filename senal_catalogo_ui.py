#!/usr/bin/env python3
"""
senal_catalogo_ui.py — CableDoc GTK3

Dominio Señal (catálogos), extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 6). Fase 2 de plan_entidad_senal.md.

Contiene:
  - _DialogoSenal (editor de una entidad 'senal': identidad de contenido)
  - SenalesListado (listado de señales)
  - TiposFormatoSenalListado (catálogo de formatos técnicos de señal)
  - _mostrar_donde_esta_senal / abrir_buscador_senal (buscador "¿dónde está
    esta señal?", ubica una señal en el árbol de infraestructura)
  - _DialogoLinajeSenal / _ArbolLinajeSenal (linaje documental de una señal,
    ver plan_estado_senal_y_linaje.md — sólo documentación, nunca alimenta
    el motor de cálculo de cortes de graph_impact.py)
  - _mostrar_lista_simple (helper de listado genérico usado por el linaje y
    por la propagación)
  - _DialogoPropagacionSenal / abrir_propagacion_senal (propagación
    automática de señal en modo "sugerencia" sobre senal_propagation.py)
  - _DialogoReportesSenal / abrir_reportes_senal (reportes de señal)
  - abrir_limpiar_senales_propagadas (limpieza masiva de señales propagadas)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos 13 nombres sin cambios.

`senal_propagation.PropagadorSenal` se importa con import diferido dentro
de los métodos que lo usan (patrón ya existente en el bloque original, se
preserva sin cambios). `_DialogoConector` (conectores_ui.py) es sólo una
referencia en comentario/docstring, no en código — no requiere import.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from modelo import Modelo, DB_PATH

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
)


# ─── Señal (catálogos) ────────────────────────────────────────────────────────
# Fase 2 de plan_entidad_senal.md. Ver también la sección "Señal" agregada a
# _DialogoConector (asignación por conector) y abrir_buscador_senal (¿dónde
# está esta señal?), más abajo en este archivo.

class _DialogoSenal(Gtk.Dialog):
    """Editor de una entidad 'senal' (identidad de contenido, ej. 'TELEFE
    SAT'), separada a propósito del formato técnico (ver tipo_formato_senal)
    porque la misma señal puede viajar en más de un formato a lo largo de
    su recorrido."""

    TIPOS_CONTENIDO = ["VIDEO", "AUDIO", "DATOS", "EMBEBIDO"]

    def __init__(self, titulo, nombre="", tipo_contenido="", descripcion="",
                parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(400, 200)

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = Gtk.Entry(text=nombre, activates_default=True,
                                  hexpand=True)
        g.attach(self.e_nombre, 1, 0, 2, 1)

        _lbl_entry(g, _("Tipo de contenido:"), 1)
        self.c_tipo = Gtk.ComboBoxText.new_with_entry()
        for t in self.TIPOS_CONTENIDO:
            self.c_tipo.append_text(t)
        if tipo_contenido:
            self.c_tipo.get_child().set_text(tipo_contenido)
        self.c_tipo.set_hexpand(True)
        g.attach(self.c_tipo, 1, 1, 2, 1)

        _lbl_entry(g, _("Descripción:"), 2)
        self.e_desc = Gtk.Entry(text=descripcion, hexpand=True)
        g.attach(self.e_desc, 1, 2, 2, 1)

        self.get_content_area().add(g)
        self.show_all()

    @property
    def nombre(self):
        return self.e_nombre.get_text().strip()

    @property
    def tipo_contenido(self):
        return self.c_tipo.get_child().get_text().strip()

    @property
    def descripcion(self):
        return self.e_desc.get_text().strip()


class SenalesListado(VentanaListado):
    """Catálogo de señales (identidades de contenido). Doble función:
    ABM del catálogo, y punto de entrada al buscador '¿dónde está esta
    señal?' vía el botón extra agregado en el constructor."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Señales"),
            [_("ID"), _("Nombre"), _("Tipo contenido"), _("Descripción")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                (_("🔎 ¿Dónde está esta señal?"), self._on_buscar_donde),
                (_("🧬 Linaje…"), self._on_linaje),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_senales())

    def nuevo(self):
        dlg = _DialogoSenal(_("Nueva Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.nombre:
            Modelo.agregar_senal(dlg.nombre, dlg.tipo_contenido, dlg.descripcion)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_senal(id_)
        if not rows: return
        r = rows[0]
        dlg = _DialogoSenal(_("Editar Señal"), nombre=s(r[1]),
                            tipo_contenido=s(r[2]), descripcion=s(r[3]),
                            parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificar_senal(id_, dlg.nombre, dlg.tipo_contenido,
                                   dlg.descripcion)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_senal(id_)

    def _on_buscar_donde(self, btn):
        f = self._fila()
        if not f:
            mostrar_error(self, _("Elegí primero una señal de la lista."))
            return
        _mostrar_donde_esta_senal(id_senal=f[0], nombre_senal=f[1], parent=self)

    def _on_linaje(self, btn):
        f = self._fila()
        if not f:
            mostrar_error(self, _("Elegí primero una señal de la lista."))
            return
        _DialogoLinajeSenal(id_senal=f[0], nombre_senal=f[1], parent=self).run_and_destroy()


class TiposFormatoSenalListado(VentanaListado):
    """Catálogo de formatos técnicos de señal (ej. 'SDI 1080i', 'IP
    ST2110'). Separado del catálogo de 'senal' — ver _DialogoSenal."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Formatos de Señal"), [_("ID"), _("Nombre")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_formatos_senal())

    def nuevo(self):
        dlg = DialogoNombre(_("Nuevo Formato de Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.agregar_tipo_formato_senal(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        formatos = {s(r[0]): s(r[1]) for r in Modelo.devolver_formatos_senal()}
        if id_ not in formatos: return
        dlg = DialogoNombre(_("Editar Formato de Señal"),
                            valor=formatos[id_], parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificar_tipo_formato_senal(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_tipo_formato_senal(id_)


def _mostrar_donde_esta_senal(id_senal, nombre_senal, parent=None):
    """Ventana de solo lectura con todos los conectores (y su equipo) que
    hoy tienen cargada la señal id_senal. Ver Modelo.buscar_conectores_por_senal."""
    filas = Modelo.buscar_conectores_por_senal(id_senal)
    dlg = Gtk.Dialog(
        title=_("¿Dónde está \"{}\"?").format(nombre_senal),
        transient_for=parent, modal=True, destroy_with_parent=True,
    )
    dlg.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
    dlg.set_default_size(640, 420)

    area = dlg.get_content_area()
    area.set_spacing(6)

    hb_top = Gtk.Box(spacing=6, margin_start=10, margin_end=10, margin_top=6)
    btn_linaje = Gtk.Button(label="🧬 " + _("Ver / editar linaje…"))
    btn_linaje.connect(
        "clicked",
        lambda b: _DialogoLinajeSenal(
            id_senal=id_senal, nombre_senal=nombre_senal, parent=dlg
        ).run_and_destroy())
    hb_top.pack_start(btn_linaje, False, False, 0)
    area.pack_start(hb_top, False, False, 0)

    if not filas:
        lbl = Gtk.Label(
            label=_("Esta señal todavía no está cargada en ningún conector."))
        lbl.set_margin_start(16); lbl.set_margin_end(16)
        lbl.set_margin_top(16); lbl.set_margin_bottom(16)
        area.add(lbl)
    else:
        cols = [_("Equipo"), _("Conector"), _("Formato"), _("Origen")]
        store = Gtk.ListStore(str, str, str, str)
        for id_conector, nombre_conector, id_equipo, nombre_equipo, \
                nombre_formato, origen in filas:
            store.append([
                s(nombre_equipo) or f"(equipo #{s(id_equipo)})",
                s(nombre_conector),
                s(nombre_formato) or "—",
                s(origen),
            ])
        tv = Gtk.TreeView(model=store)
        for i, titulo_col in enumerate(cols):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

    dlg.show_all()
    dlg.run()
    dlg.destroy()


def abrir_buscador_senal(parent=None):
    """Punto de entrada del menú 'Diagramas → 🔎 Buscador de señal…': pide
    elegir una señal del catálogo y muestra dónde está cargada hoy."""
    sel = SenalesListado(parent=parent, modo_seleccion=True)
    if sel.run() == Gtk.ResponseType.OK:
        id_senal = sel.resultado_id
        nombre_senal = sel.resultado_nombre
        sel.destroy()
        _mostrar_donde_esta_senal(id_senal, nombre_senal, parent=parent)
    else:
        sel.destroy()


# ── Linaje de señal (plan_estado_senal_y_linaje.md, Función 2) ─────────────

class _DialogoLinajeSenal(Gtk.Dialog):
    """
    Editor de linaje de UNA señal: de qué otra(s) señal(es) deriva
    (padres). No edita hijos acá — para ver/editar el linaje completo
    hacia abajo hay que abrir el diálogo de linaje de la señal hija
    correspondiente (cada señal edita sus propios padres, nunca los
    padres de otra) — es más simple de razonar que un editor bidireccional
    y evita el caso raro de "edito A pero desde la ficha de B".

    Fila = (activo: bool, id_padre: str, nombre_padre: str, nota: str).
    Se precarga con la UNIÓN de:
      - los padres ya guardados (Modelo.devolver_padres_de_senal) — activos
      - los padres SUGERIDOS automáticamente (Modelo.sugerir_padres_de_senal)
        que todavía no estén guardados — también activos, para que el caso
        común (aceptar la sugerencia tal cual) sea "abrir → Aceptar" y nada
        más; el usuario destilda lo que no quiere.
    Al aceptar: guarda (agregar_linaje, que hace upsert) todo lo tildado
    y borra (quitar_linaje) lo que estaba guardado y quedó destildado.
    Antes de guardar un vínculo nuevo corre hay_ciclo_linaje(); si
    cerraría un ciclo, avisa y NO guarda esa fila puntual (no aborta el
    resto del guardado).
    """

    COL_ACTIVO, COL_ID_PADRE, COL_NOMBRE, COL_NOTA = range(4)

    def __init__(self, id_senal, nombre_senal, parent=None):
        super().__init__(title=f"🧬 {_('Linaje de')}: {nombre_senal}",
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(520, 460)
        self.id_senal = str(id_senal)
        self.nombre_senal = nombre_senal
        self._ids_guardados_al_abrir = set()   # para saber qué se destildó

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(10); area.set_margin_end(10)
        area.set_margin_top(8);   area.set_margin_bottom(8)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(_(
            "<b>¿De qué señal(es) deriva «{n}»?</b>\n"
            "<small>Tildadas: se guardan. Doble clic en la nota para "
            "editarla.</small>").format(n=GLib.markup_escape_text(nombre_senal)))
        lbl.set_line_wrap(True)
        area.pack_start(lbl, False, False, 0)

        self._store = Gtk.ListStore(bool, str, str, str)
        self._tv = Gtk.TreeView(model=self._store, headers_visible=True)

        rend_chk = Gtk.CellRendererToggle()
        rend_chk.connect("toggled", self._on_toggle)
        col_chk = Gtk.TreeViewColumn("", rend_chk, active=self.COL_ACTIVO)
        self._tv.append_column(col_chk)

        col_nom = Gtk.TreeViewColumn(
            _("Señal padre"), Gtk.CellRendererText(xpad=4),
            text=self.COL_NOMBRE)
        col_nom.set_expand(True); col_nom.set_resizable(True)
        self._tv.append_column(col_nom)

        rend_nota = Gtk.CellRendererText(xpad=4, editable=True)
        rend_nota.connect("edited", self._on_nota_editada)
        col_nota = Gtk.TreeViewColumn(
            _("Nota (opcional)"), rend_nota, text=self.COL_NOTA)
        col_nota.set_expand(True); col_nota.set_resizable(True)
        self._tv.append_column(col_nota)

        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        hb = Gtk.Box(spacing=6)
        btn_sugerir = Gtk.Button(label="🔄 " + _("Volver a sugerir"))
        btn_sugerir.set_tooltip_text(_(
            "Vuelve a mirar las entradas del equipo por si el cableado "
            "cambió desde que se abrió este diálogo. No borra lo que ya "
            "esté tildado a mano."))
        btn_sugerir.connect("clicked", lambda b: self._cargar(resugerir=True))
        hb.pack_start(btn_sugerir, False, False, 0)

        btn_agregar = Gtk.Button(label="➕ " + _("Agregar señal…"))
        btn_agregar.set_tooltip_text(_(
            "Buscar cualquier señal del catálogo y agregarla como padre "
            "manualmente, aunque no haya sido sugerida."))
        btn_agregar.connect("clicked", self._on_agregar_manual)
        hb.pack_start(btn_agregar, False, False, 0)

        btn_arbol = Gtk.Button(label="🌳 " + _("Ver árbol de linaje"))
        btn_arbol.connect("clicked", self._on_ver_arbol)
        hb.pack_start(btn_arbol, False, False, 0)
        area.pack_start(hb, False, False, 0)

        self._cargar(resugerir=False)
        self.show_all()

    # ── Carga ────────────────────────────────────────────────────────────
    def _cargar(self, resugerir: bool) -> None:
        """resugerir=False: carga inicial (guardados + sugeridos, ambos
        activos). resugerir=True: sólo AGREGA sugerencias nuevas que
        todavía no estén en la lista — no toca lo que el usuario ya
        tildó/destildó/editó a mano."""
        ids_en_store = {r[self.COL_ID_PADRE] for r in self._store}

        if not resugerir:
            self._store.clear()
            ids_en_store = set()
            guardados = Modelo.devolver_padres_de_senal(self.id_senal)
            self._ids_guardados_al_abrir = {str(r[1]) for r in guardados}
            for _id_lin, id_padre, nombre_padre, nota in guardados:
                self._store.append([True, str(id_padre), nombre_padre, nota or ""])
                ids_en_store.add(str(id_padre))

        try:
            sugeridos = Modelo.sugerir_padres_de_senal(self.id_senal)
        except Exception:
            sugeridos = []
        agregados = 0
        for id_padre, nombre_padre in sugeridos:
            id_padre = str(id_padre)
            if id_padre in ids_en_store or id_padre == self.id_senal:
                continue
            self._store.append([True, id_padre, nombre_padre, ""])
            ids_en_store.add(id_padre)
            agregados += 1

        if resugerir and agregados == 0:
            mostrar_info(self, _(
                "No se encontraron sugerencias nuevas (mirando las "
                "entradas del equipo donde esta señal está cargada a "
                "mano)."))

    def _on_toggle(self, cell, path):
        self._store[path][self.COL_ACTIVO] = not self._store[path][self.COL_ACTIVO]

    def _on_nota_editada(self, cell, path, texto_nuevo):
        self._store[path][self.COL_NOTA] = texto_nuevo

    def _on_agregar_manual(self, btn):
        dlg = SenalesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_sel = str(dlg.resultado_id)
            nombre_sel = dlg.resultado_nombre
            if id_sel == self.id_senal:
                mostrar_error(self, _("Una señal no puede ser padre de sí misma."))
            elif any(r[self.COL_ID_PADRE] == id_sel for r in self._store):
                mostrar_info(self, _("Esa señal ya está en la lista."))
            else:
                self._store.append([True, id_sel, nombre_sel, ""])
        dlg.destroy()

    def _on_ver_arbol(self, btn):
        dlg = _ArbolLinajeSenal(self.id_senal, self.nombre_senal, parent=self)
        dlg.run(); dlg.destroy()

    # ── Guardado ─────────────────────────────────────────────────────────
    def run_and_destroy(self) -> bool:
        """Devuelve True si se guardó algo (para que el llamador pueda
        refrescar su propia vista si hace falta)."""
        resp = self.run()
        guardo = False
        if resp == Gtk.ResponseType.OK:
            guardo = self._guardar()
        self.destroy()
        return guardo

    def _guardar(self) -> bool:
        tildados = {}
        for activo, id_padre, _nombre, nota in self._store:
            if activo:
                tildados[id_padre] = nota

        ciclos_bloqueados = []
        for id_padre, nota in tildados.items():
            es_nuevo = id_padre not in self._ids_guardados_al_abrir
            if es_nuevo and Modelo.hay_ciclo_linaje(self.id_senal, id_padre):
                ciclos_bloqueados.append(id_padre)
                continue
            Modelo.agregar_linaje(self.id_senal, id_padre, nota or None)

        # Lo que estaba guardado y quedó destildado (o se bloqueó por
        # ciclo, que no debería pasar nunca porque ya estaba guardado
        # antes sin ciclo — pero por las dudas no se toca acá) se borra.
        for id_padre in self._ids_guardados_al_abrir - set(tildados.keys()):
            padres_actuales = Modelo.devolver_padres_de_senal(self.id_senal)
            for id_lin, id_p, _n, _nota in padres_actuales:
                if str(id_p) == id_padre:
                    Modelo.quitar_linaje(id_lin)

        if ciclos_bloqueados:
            nombres = ", ".join(
                r[self.COL_NOMBRE] for r in self._store
                if r[self.COL_ID_PADRE] in ciclos_bloqueados)
            mostrar_error(self, _(
                "No se guardó el vínculo con: {n}\n"
                "Convertirla en padre cerraría un ciclo (esa señal ya es, "
                "directa o indirectamente, descendiente de «{h}»)."
            ).format(n=nombres, h=self.nombre_senal))

        return True


class _ArbolLinajeSenal(Gtk.Dialog):
    """
    Árbol de solo lectura, lazy-load (mismo patrón que
    pantallas_avanzadas.ArbolConexionesEquipo): raíz = la señal actual,
    con dos ramas expandibles — "⬆ Deriva de" (padres, recursivo hacia
    arriba) y "⬇ Usada en" (hijos, recursivo hacia abajo). Vista gráfica
    queda fuera de esta entrega (plan, sección 3.6) — esto es sólo texto.
    """

    COL_TEXTO, COL_KEY, COL_TIPO, COL_COLOR, COL_WEIGHT, COL_ITALIC = range(6)

    def __init__(self, id_senal, nombre_senal, parent=None):
        super().__init__(title="🧬 " + _("Árbol de linaje: {n}").format(n=nombre_senal),
                         transient_for=parent, destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(520, 560)

        area = self.get_content_area()
        self._store = Gtk.TreeStore(str, str, str, str, int, int)
        self._tv = Gtk.TreeView(model=self._store, headers_visible=False)
        self._tv.set_enable_tree_lines(True)
        rend = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(
            "", rend, text=self.COL_TEXTO, foreground=self.COL_COLOR,
            weight=self.COL_WEIGHT, style=self.COL_ITALIC)
        self._tv.append_column(col)
        self._tv.connect("row-expanded", self._on_expandido)

        sw = Gtk.ScrolledWindow(vexpand=True, margin_start=8, margin_end=8,
                                margin_top=8, margin_bottom=8)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        id_senal = str(id_senal)
        it_raiz = self._store.append(None, [
            f"📡  {nombre_senal}", id_senal, "raiz", "#0a3a6e", 700, 0])

        it_padres = self._store.append(it_raiz, [
            "⬆  " + _("Deriva de…"), "", "grupo_padres", "#8a6a1a", 600, 0])
        self._poblar_nivel(it_padres, Modelo.devolver_padres_de_senal(id_senal),
                           tipo_hijo="senal_padre")

        it_hijos = self._store.append(it_raiz, [
            "⬇  " + _("Usada en…"), "", "grupo_hijos", "#1a6a4a", 600, 0])
        self._poblar_nivel(it_hijos, Modelo.devolver_hijos_de_senal(id_senal),
                           tipo_hijo="senal_hijo")

        path_raiz = self._store.get_path(it_raiz)
        self._tv.expand_row(path_raiz, False)
        self.show_all()

    def _poblar_nivel(self, it_padre, filas, tipo_hijo) -> None:
        if not filas:
            self._store.append(it_padre, [
                "(" + _("ninguna") + ")", "", "vacio", "#888888", 300, 2])
            return
        for _id_lin, id_rel, nombre_rel, nota in filas:
            texto = f"📡  {nombre_rel}"
            if nota:
                texto += f"   —  {nota}"
            it = self._store.append(it_padre, [
                texto, str(id_rel), tipo_hijo, "#1a1a1a", 400, 0])
            # placeholder para poder seguir expandiendo, salvo que esta
            # misma señal ya sea la raíz (evita un loop de un solo paso
            # si alguien la agregó como su propio padre/hijo por error
            # antes de que existiera hay_ciclo_linaje)
            self._store.append(it, ["…", "", "dummy", "#bbbbbb", 300, 2])

    def _on_expandido(self, tv, it, path) -> None:
        tipo = self._store.get_value(it, self.COL_TIPO)
        key  = self._store.get_value(it, self.COL_KEY)
        if tipo not in ("senal_padre", "senal_hijo") or not key:
            return
        it_ch = self._store.iter_children(it)
        if it_ch and self._store.get_value(it_ch, self.COL_TIPO) != "dummy":
            return   # ya se expandió antes, no recargar
        while it_ch:
            self._store.remove(it_ch)
            it_ch = self._store.iter_children(it)
        if tipo == "senal_padre":
            filas = Modelo.devolver_padres_de_senal(key)
        else:
            filas = Modelo.devolver_hijos_de_senal(key)
        self._poblar_nivel(it, filas, tipo_hijo=tipo)


def _mostrar_lista_simple(titulo, encabezado, filas, parent=None):
    """Ventana de solo lectura genérica: una fila de texto por elemento.
    Usada para los sub-reportes de la revisión de propagación (conflictos,
    equipos ambiguos, enrutadores sin matriz) — no necesitan columnas,
    sólo una lista legible."""
    dlg = Gtk.Dialog(title=titulo, transient_for=parent, modal=True,
                     destroy_with_parent=True)
    dlg.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
    dlg.set_default_size(520, 380)
    area = dlg.get_content_area()
    area.set_spacing(6)

    lbl = Gtk.Label(label=encabezado, xalign=0, wrap=True)
    lbl.set_margin_start(10); lbl.set_margin_end(10); lbl.set_margin_top(10)
    area.add(lbl)

    store = Gtk.ListStore(str)
    for f in filas:
        store.append([f])
    tv = Gtk.TreeView(model=store, headers_visible=False)
    tv.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=6), text=0))
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_vexpand(True)
    sw.add(tv)
    area.pack_start(sw, True, True, 0)

    dlg.show_all()
    dlg.run()
    dlg.destroy()


class _DialogoPropagacionSenal(Gtk.Dialog):
    """Fase 3 de plan_entidad_senal.md — revisión del motor de propagación
    (senal_propagation.PropagadorSenal) en modo 'sugerencia': calcula todo
    en memoria, el usuario elige qué aceptar, y sólo entonces se escribe
    en senal_en_conector (Modelo.aplicar_propagacion_senal). Nunca pisa
    una carga MANUAL — ver comentarios en ambos módulos."""

    def __init__(self, parent=None):
        super().__init__(title=_("Propagación de señal — revisión"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aplicar seleccionadas"), Gtk.ResponseType.OK)
        self.set_default_size(720, 520)
        self.resultado = None
        self._filas_por_conector = {}

        area = self.get_content_area()
        area.set_spacing(6)

        self.lbl_resumen = Gtk.Label(xalign=0, wrap=True)
        self.lbl_resumen.set_margin_start(10); self.lbl_resumen.set_margin_top(10)
        area.add(self.lbl_resumen)

        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.set_margin_start(10); barra.set_margin_end(10)
        btn_todo = Gtk.Button(label=_("Marcar todo"))
        btn_todo.connect("clicked", lambda b: self._marcar_todo(True))
        btn_ninguno = Gtk.Button(label=_("Desmarcar todo"))
        btn_ninguno.connect("clicked", lambda b: self._marcar_todo(False))
        self.btn_conflictos = Gtk.Button(label=_("⚠ Ver conflictos"))
        self.btn_conflictos.connect("clicked", self._ver_conflictos)
        self.btn_ambiguos = Gtk.Button(label=_("⚠ Ver equipos ambiguos"))
        self.btn_ambiguos.connect("clicked", self._ver_ambiguos)
        for b in (btn_todo, btn_ninguno, self.btn_conflictos, self.btn_ambiguos):
            barra.pack_start(b, False, False, 0)
        area.pack_start(barra, False, False, 0)

        self.store = Gtk.ListStore(bool, str, str, str, str, str)
        # cols: aplicar?, equipo, conector, señal, formato, id_conector(oculta)
        tv = Gtk.TreeView(model=self.store)
        rend_toggle = Gtk.CellRendererToggle()
        rend_toggle.connect("toggled", self._on_toggle)
        tv.append_column(Gtk.TreeViewColumn(_("Aplicar"), rend_toggle, active=0))
        for i, titulo in enumerate(
                [_("Equipo"), _("Conector"), _("Señal propuesta"), _("Formato")], start=1):
            col = Gtk.TreeViewColumn(titulo, Gtk.CellRendererText(xpad=4), text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

        self.show_all()
        self._calcular()

    def _calcular(self):
        from senal_propagation import PropagadorSenal
        prop = PropagadorSenal(DB_PATH)
        self.resultado = prop.calcular()
        r = self.resultado

        partes = [
            _("{} conectores con señal propuesta para aplicar.")
              .format(len(r.propagadas)),
        ]
        if r.conflictos:
            partes.append(
                _("⚠ {} conectores con señales en conflicto (no se pueden "
                  "aplicar automáticamente, requieren revisión manual).")
                  .format(len(r.conflictos)))
        if r.equipos_distribuidor_ambiguo:
            partes.append(
                _("⚠ {} equipos no se pudieron propagar automáticamente: "
                  "jacks de patchera cuyos 4 conectores no siguen el "
                  "patrón de nombre esperado (A_BACK/B_BACK/A_FRONT/"
                  "B_FRONT — revisar tipeo), u otros equipos marcados "
                  "distribuidor con más de una entrada real.")
                  .format(len(r.equipos_distribuidor_ambiguo)))
        if r.equipos_enrutador_sin_matriz:
            partes.append(
                _("⚠ {} equipos enrutador no tienen matriz de ruteo "
                  "guardada, no se pudo propagar a través de ellos.")
                  .format(len(r.equipos_enrutador_sin_matriz)))
        if not r.convergio:
            partes.append(
                _("⚠ El cálculo no terminó de estabilizar (posible ciclo "
                  "de ruteo) — los resultados pueden ser parciales."))
        self.lbl_resumen.set_text("\n".join(partes))

        self.btn_conflictos.set_sensitive(bool(r.conflictos))
        self.btn_ambiguos.set_sensitive(
            bool(r.equipos_distribuidor_ambiguo or r.equipos_enrutador_sin_matriz))

        self.store.clear()
        self._filas_por_conector = {}
        for p in sorted(r.propagadas,
                        key=lambda p: (p.nombre_equipo or "", p.nombre_conector or "")):
            it = self.store.append([
                True, s(p.nombre_equipo), s(p.nombre_conector),
                s(p.nombre_senal), s(p.nombre_formato) or "—", p.id_conector,
            ])
            self._filas_por_conector[p.id_conector] = it

    def _on_toggle(self, cell, path):
        it = self.store.get_iter(path)
        self.store.set_value(it, 0, not self.store.get_value(it, 0))

    def _marcar_todo(self, valor):
        for row in self.store:
            row[0] = valor

    def _ver_conflictos(self, btn):
        filas = [
            "{} — {} (equipo: {})".format(
                s(p.nombre_conector), _("señales distintas llegan por rutas distintas"),
                s(p.nombre_equipo))
            for p in self.resultado.conflictos
        ]
        _mostrar_lista_simple(
            _("Conflictos detectados"),
            _("Estos conectores reciben más de una señal candidata por "
              "rutas distintas del grafo. No se tocan automáticamente — "
              "revisá el cableado o cargá la señal correcta a mano."),
            filas, parent=self)

    def _ver_ambiguos(self, btn):
        filas = []
        for eid in self.resultado.equipos_distribuidor_ambiguo:
            filas.append(_("Equipo #{} — patchera con nombres de conector "
                           "que no calzan con A_BACK/B_BACK/A_FRONT/"
                           "B_FRONT (revisar tipeo), u otro equipo "
                           "DISTRIBUIDOR con más de una entrada real.")
                         .format(eid))
        for eid in self.resultado.equipos_enrutador_sin_matriz:
            filas.append(_("Equipo #{} — rol ENRUTADOR sin matriz de "
                           "ruteo guardada.").format(eid))
        _mostrar_lista_simple(
            _("Equipos sin propagar"),
            _("Estos equipos no propagaron señal a través suyo por no "
              "poder determinar una correspondencia entrada→salida "
              "confiable. Si alguno es en realidad un amplificador de "
              "distribución simple, revisá que tenga una sola entrada; "
              "si es una patchera o un pasante, es esperable que quede "
              "acá."),
            filas, parent=self)

    def run_and_aplicar(self):
        """Corre el diálogo; si el usuario confirma, aplica las filas
        tildadas y devuelve la cantidad de conectores escritos (None si
        se canceló)."""
        resp = self.run()
        if resp != Gtk.ResponseType.OK:
            self.destroy()
            return None
        aceptadas = []
        by_id = {p.id_conector: p for p in self.resultado.propagadas}
        for row in self.store:
            if row[0]:
                id_conector = row[5]
                p = by_id.get(id_conector)
                if p:
                    aceptadas.append(p)
        escritas = Modelo.aplicar_propagacion_senal(aceptadas)
        self.destroy()
        return escritas


def abrir_propagacion_senal(parent=None):
    """Punto de entrada del menú 'Diagramas → 🔮 Calcular propagación de
    señal…'."""
    try:
        from senal_propagation import PropagadorSenal  # noqa: F401 (chequeo de import)
    except Exception as e:
        mostrar_error(parent, f"{_('Motor de propagación no disponible')}:\n{e}")
        return
    dlg = _DialogoPropagacionSenal(parent=parent)
    escritas = dlg.run_and_aplicar()
    if escritas is not None:
        info = Gtk.MessageDialog(
            transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("Se aplicaron {} señales propagadas.").format(escritas),
        )
        info.run()
        info.destroy()


class _DialogoReportesSenal(Gtk.Dialog):
    """Fase 6 de plan_entidad_senal.md — reportes de señal. Tres pestañas,
    cada una con su propia consulta en Modelo (reporte_formatos_en_uso,
    reporte_senales_sin_usar, reporte_senales_propagadas_sin_origen).
    Todo de solo lectura; no modifica nada."""

    def __init__(self, parent=None):
        super().__init__(title=_("📡 Reportes de señal"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(620, 460)

        nb = Gtk.Notebook()
        nb.append_page(self._tab_formatos(), Gtk.Label(label=_("Formatos en uso")))
        nb.append_page(self._tab_sin_usar(), Gtk.Label(label=_("Señales sin usar")))
        nb.append_page(self._tab_sin_origen(), Gtk.Label(label=_("Propagadas sin origen")))
        self.get_content_area().pack_start(nb, True, True, 0)
        self.show_all()

    def _tabla_simple(self, encabezados, filas):
        store = Gtk.ListStore(*([str] * len(encabezados)))
        for f in filas:
            store.append([s(v) for v in f])
        tv = Gtk.TreeView(model=store)
        for i, tit in enumerate(encabezados):
            col = Gtk.TreeViewColumn(tit, Gtk.CellRendererText(xpad=4), text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caja.set_margin_start(8); caja.set_margin_end(8)
        caja.set_margin_top(8); caja.set_margin_bottom(8)
        caja.pack_start(sw, True, True, 0)
        return caja

    def _con_encabezado(self, texto, widget):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl = Gtk.Label(label=texto, xalign=0, wrap=True)
        lbl.set_margin_start(8); lbl.set_margin_end(8); lbl.set_margin_top(8)
        caja.pack_start(lbl, False, False, 0)
        caja.pack_start(widget, True, True, 0)
        return caja

    def _tab_formatos(self):
        filas = Modelo.reporte_formatos_en_uso()
        tabla = self._tabla_simple(
            [_("Formato"), _("Conectores"), _("Señales distintas")], filas)
        return self._con_encabezado(
            _("Cuántos conectores y señales distintas usan cada formato "
              "técnico hoy — útil para ver, por ejemplo, cuánto SDI legacy "
              "queda frente a IP y planificar una migración."),
            tabla)

    def _tab_sin_usar(self):
        filas = Modelo.reporte_senales_sin_usar()
        tabla = self._tabla_simple(
            [_("Señal"), _("Tipo de contenido")],
            [(f[1], f[2]) for f in filas])
        return self._con_encabezado(
            _("Señales del catálogo que todavía no están cargadas en "
              "ningún conector (ni manual ni propagada) — dadas de alta "
              "pero nunca asignadas."),
            tabla)

    def _tab_sin_origen(self):
        filas = Modelo.reporte_senales_propagadas_sin_origen()
        tabla = self._tabla_simple([_("Señal")], [(f[1],) for f in filas])
        return self._con_encabezado(
            _("⚠ Señales con al menos un conector PROPAGADA pero sin "
              "ninguna carga MANUAL viva que las sostenga — normalmente "
              "pasa cuando se borró o cambió la fuente manual después de "
              "aplicar una propagación. Revisar: volver a cargar la "
              "fuente y recalcular, o quitar la señal de esos conectores."),
            tabla)


def abrir_reportes_senal(parent=None):
    """Punto de entrada del menú 'Catálogos → 📡 Reportes de señal…'."""
    dlg = _DialogoReportesSenal(parent=parent)
    dlg.run()
    dlg.destroy()


def abrir_limpiar_senales_propagadas(parent=None):
    """Punto de entrada del menú 'Diagramas → 📡🧹 Borrar señales
    propagadas…'. Borra en bloque todas las asignaciones de señal con
    origen='PROPAGADA' (deja esos conectores sin señal asignada), sin
    tocar ninguna carga MANUAL. Pide confirmación mostrando primero la
    cantidad de conectores afectados."""
    n = Modelo.contar_senales_propagadas()
    if n == 0:
        info = Gtk.MessageDialog(
            transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("No hay señales propagadas cargadas actualmente."),
        )
        info.run()
        info.destroy()
        return

    confirmar = Gtk.MessageDialog(
        transient_for=parent, modal=True, message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text=_("¿Borrar todas las señales propagadas?"),
    )
    confirmar.format_secondary_text(
        _("Se van a quitar {} asignaciones de señal con origen "
          "PROPAGADA (el conector queda sin señal asignada). Las cargas "
          "MANUAL no se tocan. Esta acción no se puede deshacer.").format(n)
    )
    resp = confirmar.run()
    confirmar.destroy()
    if resp != Gtk.ResponseType.YES:
        return

    borradas = Modelo.limpiar_senales_propagadas()
    info = Gtk.MessageDialog(
        transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=_("Se borraron {} señales propagadas.").format(borradas),
    )
    info.run()
    info.destroy()

