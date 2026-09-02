"""
diagrama_personalizado.py — Diagramas de conexiones personalizados/guardables
================================================================================
Funcionalidad APARTE del diagrama global (DiagramaConexiones en
pantallas_avanzadas.py): permite armar un diagrama desde cero eligiendo qué
equipos incluir, agregar conexiones "manuales" (no reales, no se guardan en
la tabla `conexion`) y también traer un equipo con sus conexiones reales
existentes. Al terminar, se guarda con nombre + descripción en tablas propias
(diagrama_guardado / diagrama_guardado_nodo / diagrama_guardado_conexion —
ver Modelo.asegurar_tablas_diagramas_guardados en modelo.py).

Reutiliza la ventana DiagramaConexiones (pan/zoom, drag de nodos, export
SVG/PDF, buscador, etc.) por herencia; sólo agrega la carga/guardado propios
y la edición manual de conexiones.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from modelo import Modelo, DB_PATH
from pantallas_avanzadas import DiagramaConexiones

try:
    from i18n import _
except ImportError:
    def _(t): return t


def s(v):
    return "" if v is None else str(v)


# ─────────────────────────────────────────────────────────────────────────────
# Diálogo: nombre + descripción al guardar
# ─────────────────────────────────────────────────────────────────────────────

class _DialogoGuardarDiagrama(Gtk.Dialog):
    def __init__(self, nombre="", descripcion="", parent=None):
        super().__init__(
            title="Guardar diagrama personalizado",
            transient_for=parent, modal=True, destroy_with_parent=True,
        )
        self.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                         "💾 Guardar", Gtk.ResponseType.OK)
        self.set_default_size(420, 240)
        self.set_default_response(Gtk.ResponseType.OK)

        g = Gtk.Grid(column_spacing=8, row_spacing=6,
                     margin_start=12, margin_end=12,
                     margin_top=12, margin_bottom=12)
        g.attach(Gtk.Label(label=_("Nombre:"), xalign=1), 0, 0, 1, 1)
        self.e_nombre = Gtk.Entry(text=nombre, hexpand=True,
                                  activates_default=True)
        g.attach(self.e_nombre, 1, 0, 1, 1)

        g.attach(Gtk.Label(label=_("Descripción:"), xalign=1), 0, 1, 1, 1)
        self.tv_desc = Gtk.TextView()
        self.tv_desc.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_desc.get_buffer().set_text(descripcion)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(100)
        sw.add(self.tv_desc)
        g.attach(sw, 1, 1, 1, 1)

        self.get_content_area().add(g)
        self.show_all()

    @property
    def descripcion(self):
        buf = self.tv_desc.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Ventana principal del editor (subclase de DiagramaConexiones)
# ─────────────────────────────────────────────────────────────────────────────

class DiagramaPersonalizado(DiagramaConexiones):
    """
    Editor de diagramas personalizados guardables.
    id_diagrama_guardado=None → diagrama nuevo, vacío, sin guardar todavía.
    id_diagrama_guardado=<id> → carga el diagrama guardado con ese id.
    """

    def __init__(self, id_diagrama_guardado=None, parent=None):
        self.id_diagrama_guardado = id_diagrama_guardado
        self.nombre_diagrama = ""
        self.descripcion_diagrama = ""
        self._modo_conectar = False
        self._conectar_origen = None   # (id_eq, id_conector, nombre, lado)

        super().__init__(id_equipo=None, parent=parent)

        titulo = (f"Diagrama personalizado: {self.nombre_diagrama}"
                  if self.nombre_diagrama else
                  "Diagrama personalizado (nuevo, sin guardar)")
        self.set_title(titulo)

        # ── Fila extra de toolbar propia de este editor ─────────────────────
        # DiagramaConexiones ahora arma su barra de menús desplegable (ver
        # pantallas_avanzadas.py) como primer hijo del content area, seguida
        # de la fila de estado (selección/zoom). Esta fila propia del editor
        # personalizado se inserta justo debajo de la barra de menús.
        area = self.get_content_area()
        fila3 = Gtk.Box(spacing=6)
        area.pack_start(fila3, False, False, 0)
        # Nota: reorder_child() cuenta la posición sumando 1 por la
        # presencia del action-area interno del Gtk.Dialog (ver
        # self.add_buttons(...) en DiagramaConexiones.__init__), por eso
        # el índice 2 (no 1) deja a fila3 justo debajo de la barra de menús.
        area.reorder_child(fila3, 2)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<b>Personalizado:</b>")
        fila3.pack_start(lbl, False, False, 0)

        btn_add = Gtk.Button(label=_("➕ Agregar equipo…"))
        btn_add.set_tooltip_text("Agrega un equipo al lienzo, sin traer sus conexiones reales.")
        btn_add.connect("clicked", lambda _: self._agregar_equipo())
        fila3.pack_start(btn_add, False, False, 0)

        btn_real = Gtk.Button(label=_("🔗 Traer equipo + conectados (real)…"))
        btn_real.set_tooltip_text("Agrega un equipo junto con los equipos que tiene "
                                   "conectados según los cables reales de la base.")
        btn_real.connect("clicked", lambda _: self._traer_con_conexiones_reales())
        fila3.pack_start(btn_real, False, False, 0)

        self._btn_conectar = Gtk.ToggleButton(label=_("✎ Conectar puertos"))
        self._btn_conectar.set_tooltip_text(
            "Modo conexión manual: clic en un puerto de origen y luego en el "
            "de destino crea una conexión NO real (no se guarda en la tabla "
            "de conexiones/cables de la base).")
        self._btn_conectar.connect("toggled", self._on_toggle_conectar)
        fila3.pack_start(self._btn_conectar, False, False, 0)

        btn_gestionar = Gtk.Button(label=_("🗂 Conexiones manuales…"))
        btn_gestionar.connect("clicked", lambda _: self._gestionar_conexiones_manuales())
        fila3.pack_start(btn_gestionar, False, False, 0)

        btn_quitar = Gtk.Button(label=_("🗑 Quitar equipo(s)"))
        btn_quitar.set_tooltip_text("Quita del lienzo el/los equipo(s) seleccionado(s).")
        btn_quitar.connect("clicked", lambda _: self._quitar_equipos_seleccionados())
        fila3.pack_start(btn_quitar, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        fila3.pack_start(sep, False, False, 4)

        btn_guardar = Gtk.Button(label=_("💾 Guardar diagrama…"))
        btn_guardar.get_style_context().add_class("suggested-action")
        btn_guardar.connect("clicked", lambda _: self._guardar_diagrama())
        fila3.pack_start(btn_guardar, False, False, 0)

        fila3.show_all()

    # ── carga: reemplaza la del diagrama global ─────────────────────────────
    def _cargar(self, id_inicio=None):
        self._nodos.clear()
        self._conns.clear()
        self._equipos_con_regla = Modelo.equipos_con_regla_logica_activa()
        self._equipos_criticos  = Modelo.devolver_ids_equipos_criticos()

        if self.id_diagrama_guardado:
            self._cargar_desde_guardado(self.id_diagrama_guardado)

        self._fit_all()
        self._da.queue_draw()
        n_virt = sum(1 for c in self._conns if c.get("virtual"))
        nombre = self.nombre_diagrama or "(sin guardar)"
        self._status(
            f"{nombre} — {len(self._nodos)} equipo(s), {len(self._conns)} "
            f"conexión(es) ({n_virt} manual(es))"
        )

    def _cargar_desde_guardado(self, id_diagrama):
        meta = Modelo.devolver_diagrama_guardado(id_diagrama)
        if meta:
            self.nombre_diagrama = s(meta[0][1])
            self.descripcion_diagrama = s(meta[0][2])

        for id_eq, x, y in Modelo.devolver_nodos_de_diagrama_guardado(id_diagrama):
            id_eq = str(id_eq)
            nodo = self._construir_nodo(id_eq, con_posicion=False)
            if not nodo:
                continue
            nodo["x"] = float(x) if x is not None else 0.0
            nodo["y"] = float(y) if y is not None else 0.0
            nodo["has_pos"] = True
            self._nodos[id_eq] = nodo

        for idx, (ca, cb, real, cable_real, etq) in enumerate(
                Modelo.devolver_conexiones_de_diagrama_guardado(id_diagrama)):
            ca, cb = str(ca), str(cb)
            eq_a = Modelo.equipo_de_conector(ca)
            eq_b = Modelo.equipo_de_conector(cb)
            if not eq_a or not eq_b:
                continue
            if eq_a not in self._nodos or eq_b not in self._nodos:
                continue
            self._conns.append({
                "id": str(cable_real) if (real and cable_real) else f"virt_{idx}",
                "nombre": etq or "",
                "src_eq": eq_a, "src_con": ca,
                "dst_eq": eq_b, "dst_con": cb,
                "virtual": not bool(real),
            })

    # ── preservar conexiones manuales al recalcular desde la BD real ───────
    def _reconstruir_conexiones(self):
        virtuales = [c for c in self._conns if c.get("virtual")]
        super()._reconstruir_conexiones()
        for c in virtuales:
            if c["src_eq"] in self._nodos and c["dst_eq"] in self._nodos:
                self._conns.append(c)

    # ── no persistir posiciones en la tabla global del diagrama común ──────
    def _on_release(self, da, event):
        if self._minimap_dragging:
            self._minimap_dragging = False
            return
        if self._drag_id:
            self._drag_id = None
            self._drag_offsets = {}
        if self._rband_active:
            self._rband_active = False
            if (abs(self._rband_x1 - self._rband_x0) < 4 and
                    abs(self._rband_y1 - self._rband_y0) < 4):
                self._sel_ids = set()
                self._lbl_sel.set_text("Sin selección")
            self._da.queue_draw()
        self._panning = False

    def _alinear_horizontal(self):
        valid_ids = [eid for eid in self._sel_ids if eid in self._nodos]
        if len(valid_ids) < 2:
            self._status("Seleccione al menos 2 nodos para alinear.")
            return
        nodo_derecha = max(valid_ids, key=lambda eid: self._nodos[eid]["x"])
        y_alinear = self._nodos[nodo_derecha]["y"]
        for eid in valid_ids:
            self._nodos[eid]["y"] = y_alinear
        self._status(f"Alineados {len(valid_ids)} nodos horizontalmente.")
        self._da.queue_draw()

    def _alinear_vertical(self):
        valid_ids = [eid for eid in self._sel_ids if eid in self._nodos]
        if len(valid_ids) < 2:
            self._status("Seleccione al menos 2 nodos para alinear.")
            return
        nodo_arriba = min(valid_ids, key=lambda eid: self._nodos[eid]["y"])
        x_alinear = self._nodos[nodo_arriba]["x"]
        for eid in valid_ids:
            self._nodos[eid]["x"] = x_alinear
        self._status(f"Alineados {len(valid_ids)} nodos verticalmente.")
        self._da.queue_draw()

    # ── posicionamiento simple para nodos nuevos ────────────────────────────
    def _proxima_posicion(self):
        n = len(self._nodos)
        col, fila = n % 5, n // 5
        return 80 + col * 280, 80 + fila * 220

    # ── acciones propias ────────────────────────────────────────────────────
    def _agregar_equipo(self):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_eq = str(dlg.resultado_id)
            dlg.destroy()
            if id_eq in self._nodos:
                self._status("Ese equipo ya está en el diagrama.")
                return
            nodo = self._construir_nodo(id_eq, con_posicion=False)
            if not nodo:
                self._status("No se pudo cargar el equipo.")
                return
            nodo["x"], nodo["y"] = self._proxima_posicion()
            nodo["has_pos"] = True
            self._nodos[id_eq] = nodo
            self._fit_all()
            self._da.queue_draw()
            self._status(f"Equipo «{nodo['nombre']}» agregado.")
        else:
            dlg.destroy()

    def _traer_con_conexiones_reales(self):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() != Gtk.ResponseType.OK:
            dlg.destroy()
            return
        id_eq = str(dlg.resultado_id)
        dlg.destroy()

        nuevos = []
        if id_eq not in self._nodos:
            nodo = self._construir_nodo(id_eq, con_posicion=False)
            if not nodo:
                self._status("No se pudo cargar el equipo.")
                return
            nodo["x"], nodo["y"] = self._proxima_posicion()
            nodo["has_pos"] = True
            self._nodos[id_eq] = nodo
            nuevos.append(id_eq)

        rows = Modelo._query(
            "SELECT DISTINCT \"id_equipo:1\" "
            "FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo=?",
            (id_eq,),
        )
        for r in rows:
            nid = str(r[0])
            if nid in self._nodos:
                continue
            n = self._construir_nodo(nid, con_posicion=False)
            if n:
                n["x"], n["y"] = self._proxima_posicion()
                n["has_pos"] = True
                self._nodos[nid] = n
                nuevos.append(nid)

        self._reconstruir_conexiones()
        self._fit_all()
        self._da.queue_draw()
        self._status(f"Traído(s) {len(nuevos)} equipo(s) con sus conexiones reales.")

    def _quitar_equipos_seleccionados(self):
        if not self._sel_ids:
            self._status("Seleccioná uno o más equipos para quitar.")
            return
        n = len(self._sel_ids)
        for eid in list(self._sel_ids):
            self._nodos.pop(eid, None)
        self._conns = [
            c for c in self._conns
            if c["src_eq"] in self._nodos and c["dst_eq"] in self._nodos
        ]
        self._sel_ids = set()
        self._sel_id = None
        self._lbl_sel.set_text("Sin selección")
        self._da.queue_draw()
        self._status(f"{n} equipo(s) quitado(s) del diagrama.")

    # ── modo conexión manual (dos clics: origen → destino) ──────────────────
    def _on_toggle_conectar(self, btn):
        self._modo_conectar = btn.get_active()
        self._conectar_origen = None
        if self._modo_conectar:
            self._status("Modo conectar: clic en el puerto de origen.")
        else:
            self._status("Modo conectar desactivado.")

    def _hit_port(self, wx, wy, tol=9):
        for nodo in self._nodos.values():
            for lado, lst in (("in", nodo["in"]), ("out", nodo["out"])):
                for cid, cnm, _ in lst:
                    px, py = self._port_pos(nodo, cid, lado)
                    if (wx - px) ** 2 + (wy - py) ** 2 <= tol * tol:
                        return nodo, cid, cnm, lado
        return None

    def _on_press(self, da, event):
        if self._modo_conectar and event.button == 1:
            wx, wy = self._s2w(event.x, event.y)
            hit = self._hit_port(wx, wy)
            if hit:
                nodo, cid, cnm, lado = hit
                if self._conectar_origen is None:
                    self._conectar_origen = (nodo["id"], cid, cnm, lado)
                    self._status(
                        f"Origen: {nodo['nombre']} · {cnm} — clic en el puerto destino.")
                else:
                    oeq, ocid, ocnm, olado = self._conectar_origen
                    deq, dcid, dcnm, dlado = nodo["id"], cid, cnm, lado
                    if oeq == deq and ocid == dcid:
                        self._status("Elegí un puerto distinto al de origen.")
                    else:
                        src_eq, src_con, src_nom = oeq, ocid, ocnm
                        dst_eq, dst_con, dst_nom = deq, dcid, dcnm
                        if olado == "in" and dlado == "out":
                            src_eq, src_con, src_nom, dst_eq, dst_con, dst_nom = (
                                deq, dcid, dcnm, oeq, ocid, ocnm)
                        self._conns.append({
                            "id": f"virt_{len(self._conns)}_{src_eq}_{dst_eq}",
                            "nombre": "(manual)",
                            "src_eq": src_eq, "src_con": src_con,
                            "dst_eq": dst_eq, "dst_con": dst_con,
                            "virtual": True,
                        })
                        self._status(
                            f"Conexión manual creada: {src_nom} → {dst_nom} "
                            "(no se guarda en la base de cables).")
                    self._conectar_origen = None
                self._da.queue_draw()
                return True
            # clic fuera de cualquier puerto: cancela el origen elegido
            self._conectar_origen = None
            self._da.queue_draw()
            return True
        return super()._on_press(da, event)

    def _gestionar_conexiones_manuales(self):
        virtuales = [c for c in self._conns if c.get("virtual")]
        if not virtuales:
            self._status("No hay conexiones manuales en este diagrama.")
            return

        dlg = Gtk.Dialog(
            title="Conexiones manuales (no reales)",
            transient_for=self, modal=True, destroy_with_parent=True,
        )
        dlg.add_buttons("Cerrar", Gtk.ResponseType.CLOSE)
        dlg.set_default_size(480, 320)

        store = Gtk.ListStore(str, str)
        for c in virtuales:
            na = self._nodos.get(c["src_eq"], {}).get("nombre", c["src_eq"])
            nb = self._nodos.get(c["dst_eq"], {}).get("nombre", c["dst_eq"])
            store.append([c["id"], f"{na}  →  {nb}"])

        tv = Gtk.TreeView(model=store)
        tv.append_column(
            Gtk.TreeViewColumn("Conexión manual", Gtk.CellRendererText(), text=1))
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(220)
        sw.add(tv)
        area = dlg.get_content_area()
        area.set_margin_start(10); area.set_margin_end(10)
        area.set_margin_top(8); area.set_margin_bottom(6)
        area.pack_start(sw, True, True, 4)

        def _quitar(_b):
            sel = tv.get_selection()
            model, it = sel.get_selected()
            if it:
                cid = model.get_value(it, 0)
                self._conns = [c for c in self._conns if c["id"] != cid]
                model.remove(it)
                self._da.queue_draw()

        btn_quitar = Gtk.Button(label=_("🗑 Quitar seleccionada"))
        btn_quitar.connect("clicked", _quitar)
        area.pack_start(btn_quitar, False, False, 4)

        dlg.show_all()
        dlg.run()
        dlg.destroy()

    # ── guardado ─────────────────────────────────────────────────────────────
    def _guardar_diagrama(self):
        if not self._nodos:
            self._status("Agregá al menos un equipo antes de guardar.")
            return

        dlg = _DialogoGuardarDiagrama(
            self.nombre_diagrama, self.descripcion_diagrama, parent=self)
        if dlg.run() != Gtk.ResponseType.OK:
            dlg.destroy()
            return
        nombre = dlg.e_nombre.get_text().strip()
        desc = dlg.descripcion
        dlg.destroy()
        if not nombre:
            self._status("El nombre es obligatorio.")
            return

        nodos = [(int(n["id"]), n["x"], n["y"]) for n in self._nodos.values()]
        conexiones = []
        for c in self._conns:
            es_real = 0 if c.get("virtual") else 1
            cable_real = (int(c["id"]) if es_real and s(c["id"]).isdigit() else None)
            conexiones.append((
                int(c["src_con"]), int(c["dst_con"]),
                es_real, cable_real, c.get("nombre") or "",
            ))

        if self.id_diagrama_guardado:
            Modelo.modificar_diagrama_guardado(self.id_diagrama_guardado, nombre, desc)
        else:
            self.id_diagrama_guardado = Modelo.alta_diagrama_guardado(nombre, desc)
        Modelo.guardar_contenido_diagrama_guardado(
            self.id_diagrama_guardado, nodos, conexiones)

        self.nombre_diagrama = nombre
        self.descripcion_diagrama = desc
        self.set_title(f"Diagrama personalizado: {nombre}")
        self._status(
            f"Diagrama «{nombre}» guardado: {len(nodos)} equipo(s), "
            f"{len(conexiones)} conexión(es).")


def abrir_diagrama_personalizado(id_diagrama_guardado=None, parent=None):
    dlg = DiagramaPersonalizado(id_diagrama_guardado=id_diagrama_guardado, parent=parent)
    dlg.run()
    dlg.destroy()
