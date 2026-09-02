"""DiagramaConexiones — editor de nodos moderno del diagrama de conexiones,
más los diálogos auxiliares que sólo él consume (_BuscadorDiagrama,
_DialogoRuteoMatriz, _DialogoReglasLogicas, _DialogoReglasLogicasMolde,
_DialogoCableRapido).

Entrega 6 del refactor de pantallas_avanzadas.py (ver
PROGRESS_REFACTOR.md / plan_entrega6_refactor.md): último bloque de clases
propias que quedaba en pantallas_avanzadas.py sale de ahí, dejándolo como
fachada pura (sólo imports/re-exports). Move 1:1 de las clases; no se
modificó ninguna lógica.

DiagramaConexiones compone acá los 15 mixins ya existentes (7 de entregas
anteriores al refactor de pantallas_avanzadas.py + 8 de la Entrega 5 de
este mismo refactor). El "editor clásico" legacy (EditorConexiones) NO se
portó a este archivo — se eliminó del proyecto en esta misma entrega (ver
changelog): estaba deshabilitado en el menú de cabledoc.py desde que
"Alta rápida de conexiones" pasó a reutilizar DiagramaConexiones en modo
iniciar_vacio con panel de búsqueda/arrastre. _DialogoCableRapido SÍ se
conserva acá porque sigue en uso real (lo consume EdicionConexionesMixin
vía import diferido).
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from modelo import Modelo, DB_PATH
from impacto_ui import ImpactoMixin
from riesgo_diagrama_ui import RiesgoDiagramaMixin
from signal_risk_diagrama_ui import RiesgoSenalDiagramaMixin
from senal_diagrama_ui import SenalDiagramaMixin
from escenario_ui import EscenarioMixin
from senal_visual_ui import VistaPreviaMixin
from diagnostico_ui import DiagnosticoMixin

# 8 mixins de la Entrega 5 de este mismo refactor (ver
# PROGRESS_REFACTOR.md): núcleo propio de DiagramaConexiones que se
# extrajo a archivos aparte antes de esta entrega.
from grafo_diagrama_ui import GrafoMixin
from dibujo_diagrama_ui import DibujoMixin
from interaccion_diagrama_ui import InteraccionMixin
from edicion_conexiones_diagrama_ui import EdicionConexionesMixin
from layout_diagrama_ui import LayoutMixin
from busqueda_diagrama_ui import BusquedaMixin
from export_diagrama_ui import ExportMixin
from ruteo_interno_diagrama_ui import RuteoInternoMixin

from pantallas_comunes import _, s


class _BuscadorDiagrama(Gtk.Dialog):
    """
    Diálogo de búsqueda libre de equipos en el DiagramaConexiones.
    Busca en tiempo real sobre nombre, tipo de equipo, y código de cables.
    Al aceptar devuelve la lista de ids de nodos que coinciden.
    """

    def __init__(self, parent, nodos: dict, conns: list):
        super().__init__(
            title="Buscar en el diagrama",
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        self.set_default_size(480, 420)
        self.resultado_ids: list[str] = []
        self.texto_buscado: str = ""

        self._nodos = nodos    # {id_str: {nombre, tipo_equipo, ...}}
        self._conns = conns    # [{id, nombre, src_eq, dst_eq, ...}]

        # Construir índice de búsqueda: id_eq → set de términos
        self._indice: dict[str, dict] = {}
        for eq_id, nodo in nodos.items():
            self._indice[eq_id] = {
                "nombre":     (nodo.get("nombre") or "").lower(),
                "tipo":       (nodo.get("tipo") or "").lower(),
                "rack":       "",   # no disponible en este diagrama
                "cables_out": set(),
                "cables_in":  set(),
                "senales":    set(),   # nombres de señal cargados en sus conectores
            }
        for conn in conns:
            nom = (conn.get("nombre") or conn.get("codigo") or "").lower()
            src = conn.get("src_eq", "")
            dst = conn.get("dst_eq", "")
            if src in self._indice:
                self._indice[src]["cables_out"].add(nom)
            if dst in self._indice:
                self._indice[dst]["cables_in"].add(nom)

        # Fase 5 de plan_entidad_senal.md: permitir encontrar un equipo
        # por el nombre de la señal cargada en cualquiera de sus
        # conectores (ej. Ctrl+F "TELEFE SAT" salta directo a donde está).
        try:
            filas_senal = Modelo._query("""
                SELECT c.id_equipo, s.nombre
                FROM senal_en_conector sec
                JOIN conector c ON c.id_conector = sec.id_conector
                JOIN senal s ON s.id_senal = sec.id_senal
            """)
            for id_equipo, nombre_senal in filas_senal:
                eq_id = str(id_equipo)
                if eq_id in self._indice:
                    self._indice[eq_id]["senales"].add((nombre_senal or "").lower())
        except Exception:
            pass  # tablas de señal todavía no existen en esta BD (BD vieja sin migrar)

        self.add_buttons(
            "Limpiar resaltado", Gtk.ResponseType.REJECT,
            "Cancelar",          Gtk.ResponseType.CANCEL,
            "Resaltar",          Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(False)
        self._build_ui()
        self.show_all()

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(10); area.set_margin_end(10)
        area.set_margin_top(8);   area.set_margin_bottom(4)

        # ── Entrada de búsqueda ───────────────────────────────────────────────
        box_entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text("Nombre de equipo, tipo, rack, código de cable…")
        self._entry.grab_focus()
        box_entry.pack_start(self._entry, True, True, 0)

        # Filtros de campo
        self._chk_nombre = Gtk.CheckButton(label=_("Nombre"))
        self._chk_tipo   = Gtk.CheckButton(label=_("Tipo"))
        self._chk_cable  = Gtk.CheckButton(label=_("Cables"))
        self._chk_senal  = Gtk.CheckButton(label=_("📡 Señal"))
        for chk in (self._chk_nombre, self._chk_tipo, self._chk_cable, self._chk_senal):
            chk.set_active(True)
            chk.connect("toggled", lambda _: self._buscar())

        area.pack_start(Gtk.Label(label=_("Buscar en:  "), xalign=0), False, False, 0)

        hbox_chk = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        for chk in (self._chk_nombre, self._chk_tipo, self._chk_cable, self._chk_senal):
            hbox_chk.pack_start(chk, False, False, 0)
        area.pack_start(hbox_chk, False, False, 0)
        area.pack_start(box_entry, False, False, 0)

        # ── Resultado count ───────────────────────────────────────────────────
        self._lbl_count = Gtk.Label(xalign=0)
        self._lbl_count.set_markup("<small><i>Escribí para buscar</i></small>")
        area.pack_start(self._lbl_count, False, False, 0)

        # ── Lista de resultados ───────────────────────────────────────────────
        self._store = Gtk.ListStore(str, str, str)  # id, nombre, info
        self._tv    = Gtk.TreeView(model=self._store)
        self._tv.set_rubber_banding(True)
        self._tv.set_activate_on_single_click(False)

        for i, title in enumerate(["Equipo", "Tipo / Rack"]):
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", 3)   # END
            col  = Gtk.TreeViewColumn(title, cell, text=i + 1)
            col.set_resizable(True)
            col.set_sort_column_id(i + 1)
            col.set_expand(i == 0)
            self._tv.append_column(col)

        sel = self._tv.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        sel.connect("changed", self._on_sel_changed)
        self._tv.connect("row-activated", lambda *_: self.response(Gtk.ResponseType.OK))

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(240)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        # ── Tip ───────────────────────────────────────────────────────────────
        lbl_tip = Gtk.Label(xalign=0)
        lbl_tip.set_markup(
            "<small><i>Seleccioná uno o más equipos y presioná Resaltar.  "
            "Usá ◀ ▶ en el diagrama para navegar entre resultados.</i></small>"
        )
        lbl_tip.set_line_wrap(True)
        area.pack_start(lbl_tip, False, False, 0)

        self._entry.connect("changed", lambda _: self._buscar())
        self._entry.connect("activate", lambda _: self.response(Gtk.ResponseType.OK))

        # Búsqueda inicial vacía para poblar la lista completa
        self._buscar()

    def _buscar(self):
        txt = self._entry.get_text().lower().strip()
        self._store.clear()

        usar_nombre = self._chk_nombre.get_active()
        usar_tipo   = self._chk_tipo.get_active()
        usar_cable  = self._chk_cable.get_active()
        usar_senal  = self._chk_senal.get_active()

        resultados = []
        for eq_id, info in self._indice.items():
            if not txt:
                # Sin filtro: mostrar todos
                resultados.append(eq_id)
                continue

            coincide = False
            if usar_nombre and txt in info["nombre"]:
                coincide = True
            if usar_tipo and txt in info["tipo"]:
                coincide = True
            if usar_cable and (
                any(txt in c for c in info["cables_out"]) or
                any(txt in c for c in info["cables_in"])
            ):
                coincide = True
            if usar_senal and any(txt in sn for sn in info["senales"]):
                coincide = True
            if coincide:
                resultados.append(eq_id)

        # Ordenar por nombre
        resultados.sort(key=lambda eid: self._indice[eid]["nombre"])

        for eq_id in resultados:
            info  = self._indice[eq_id]
            nodo  = self._nodos[eq_id]
            nombre = nodo.get("nombre") or eq_id
            tipo  = nodo.get("tipo") or ""
            rack  = ""
            extra = "  ·  ".join(filter(None, [tipo, rack]))
            self._store.append([eq_id, nombre, extra])

        n = len(resultados)
        if not txt:
            self._lbl_count.set_markup(
                f"<small><i>{n} equipos en el diagrama</i></small>"
            )
        elif n == 0:
            self._lbl_count.set_markup(
                "<small><span foreground='#cc4444'>Sin resultados</span></small>"
            )
        else:
            self._lbl_count.set_markup(
                f"<small><b>{n}</b> equipo{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}</small>"
            )

        self.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(n > 0)

    def _on_sel_changed(self, sel):
        # Al cambiar la selección actualizamos resultado_ids en vivo
        model, paths = sel.get_selected_rows()
        if paths:
            self.resultado_ids = [model[p][0] for p in paths]
            self.texto_buscado = self._entry.get_text().strip()
        else:
            # Si nada seleccionado, usar todos los resultados de la lista
            self.resultado_ids = [row[0] for row in self._store]
            self.texto_buscado = self._entry.get_text().strip()

    def run(self):
        resp = super().run()
        # Asegurarse de que resultado_ids esté completo
        if resp == Gtk.ResponseType.OK:
            sel  = self._tv.get_selection()
            model, paths = sel.get_selected_rows()
            if paths:
                self.resultado_ids = [model[p][0] for p in paths]
            else:
                # Usar todos si no hay selección explícita
                self.resultado_ids = [row[0] for row in self._store]
            self.texto_buscado = self._entry.get_text().strip() or "(todos)"
        return resp


class _DialogoRuteoMatriz(Gtk.Dialog):
    """
    Asignación de ruteo entrada→salida para equipos tipo MATRIZ (N entradas
    x N salidas, ej. AJA KUMO 1616).

    Dos filas de radio buttons:
      • Fila superior: una opción por ENTRADA + «sin asignar» (grupo único).
      • Fila inferior: una opción por SALIDA (grupo único).

    Flujo: clic en una salida la selecciona (única activa en su fila, por
    ser radio buttons) y la fila de entrada muestra tildada la que tiene
    asignada (o «sin asignar»). Clic en una entrada la asigna a la salida
    seleccionada. Varias salidas pueden compartir la misma entrada; cada
    salida tiene 0 o 1 entrada.
    """

    def __init__(self, nodo, mapping_actual, parent=None):
        super().__init__(
            title=f"Ruteo interno — {nodo['nombre']}",
            transient_for=parent, modal=True, destroy_with_parent=True,
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "💾 " + _("Guardar"), Gtk.ResponseType.OK)
        self.set_default_size(720, 320)

        self._entradas = list(nodo["in"])     # [(cid, nombre, idx), ...]
        self._salidas  = list(nodo["out"])
        self._mapping  = dict(mapping_actual)  # {id_out: id_in|None}
        self._sel_salida = None
        self._updating    = False

        self._btns_in  = {}   # id_in  -> RadioButton
        self._btns_out = {}   # id_out -> RadioButton
        self._btn_in_none = None

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(10); area.set_margin_end(10)
        area.set_margin_top(8);    area.set_margin_bottom(6)

        self._lbl_estado = Gtk.Label(xalign=0)
        self._lbl_estado.set_markup(
            "<i>Hacé clic en una salida y luego en su entrada.</i>")
        area.pack_start(self._lbl_estado, False, False, 0)

        lbl_in = Gtk.Label(xalign=0)
        lbl_in.set_markup("<b>Entradas</b>")
        area.pack_start(lbl_in, False, False, 0)

        sw_in = Gtk.ScrolledWindow()
        sw_in.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        box_in = Gtk.Box(spacing=4)
        box_in.set_margin_bottom(4)
        self._btn_in_none = Gtk.RadioButton.new_with_label(None, "— (sin asignar) —")
        box_in.pack_start(self._btn_in_none, False, False, 0)
        for cid, cnm, _idx in self._entradas:
            rb = Gtk.RadioButton.new_with_label_from_widget(self._btn_in_none, s(cnm))
            box_in.pack_start(rb, False, False, 0)
            self._btns_in[cid] = rb
        self._btn_in_none.connect("toggled", self._on_toggle_entrada, None)
        for cid, rb in self._btns_in.items():
            rb.connect("toggled", self._on_toggle_entrada, cid)
        sw_in.add(box_in)
        area.pack_start(sw_in, False, False, 0)

        area.pack_start(Gtk.Separator(), False, False, 4)

        lbl_out = Gtk.Label(xalign=0)
        lbl_out.set_markup("<b>Salidas</b>")
        area.pack_start(lbl_out, False, False, 0)

        sw_out = Gtk.ScrolledWindow()
        sw_out.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        box_out = Gtk.Box(spacing=4)
        grupo_out = None
        for cid, cnm, _idx in self._salidas:
            if grupo_out is None:
                rb = Gtk.RadioButton.new_with_label(None, s(cnm))
                grupo_out = rb
            else:
                rb = Gtk.RadioButton.new_with_label_from_widget(grupo_out, s(cnm))
            rb.set_active(False)
            box_out.pack_start(rb, False, False, 0)
            self._btns_out[cid] = rb
        for cid, rb in self._btns_out.items():
            rb.connect("toggled", self._on_toggle_salida, cid)
        sw_out.add(box_out)
        area.pack_start(sw_out, False, False, 0)

        if self._sel_salida is None:
            self._lbl_estado.set_markup(
                "<i>Hacé clic en una salida y luego en su entrada.</i>")

        # Si el equipo tiene una sola salida, no tiene sentido obligar al
        # usuario a seleccionarla antes de poder asignarle una entrada.
        # Nota: un único RadioButton en su propio grupo ya nace activo y
        # GTK no permite desactivarlo (rb.set_active(False) más arriba es
        # un no-op), así que set_active(True) nunca dispara la señal
        # "toggled" acá. Por eso invocamos el handler directamente, con
        # el mismo botón/id que hubiera recibido el clic del usuario.
        if len(self._salidas) == 1:
            (unica_cid, *_resto) = self._salidas[0]
            self._on_toggle_salida(self._btns_out[unica_cid], unica_cid)

        self.show_all()

    # ── nombres por id, para mensajes ──────────────────────────────────────
    def _nombre_out(self, cid):
        return next((s(c) for i, c, _ in self._salidas if i == cid), cid)

    def _nombre_in(self, cid):
        return next((s(c) for i, c, _ in self._entradas if i == cid), cid)

    # ── eventos ───────────────────────────────────────────────────────────
    def _on_toggle_salida(self, chk, id_out):
        """El grupo de radios ya garantiza exclusividad; solo actuamos
        cuando ESTE botón pasa a activo."""
        if self._updating or not chk.get_active():
            return
        self._updating = True
        self._sel_salida = id_out
        id_in_actual = self._mapping.get(id_out)
        if id_in_actual and id_in_actual in self._btns_in:
            self._btns_in[id_in_actual].set_active(True)
        else:
            self._btn_in_none.set_active(True)
        nombre_in = self._nombre_in(id_in_actual) if id_in_actual else "(sin asignar)"
        self._lbl_estado.set_markup(
            f"Salida <b>{self._nombre_out(id_out)}</b> ← {nombre_in}")
        self._updating = False

    def _on_toggle_entrada(self, chk, id_in):
        """id_in es None para la opción «sin asignar»."""
        if self._updating or not chk.get_active():
            return
        if self._sel_salida is None:
            self._updating = True
            self._btn_in_none.set_active(True)
            self._updating = False
            self._lbl_estado.set_markup(
                "<span foreground='#cc4444'>Seleccioná primero una salida.</span>")
            return

        self._mapping[self._sel_salida] = id_in
        nombre_in = f"<b>{self._nombre_in(id_in)}</b>" if id_in else "(sin asignar)"
        self._lbl_estado.set_markup(
            f"Salida <b>{self._nombre_out(self._sel_salida)}</b> ← {nombre_in}")

    @property
    def resultado_mapping(self):
        """Todas las salidas quedan con una entrada explícita (o None), para
        que la configuración quede marcada como 'ya definida' aunque el
        usuario no haya asignado nada."""
        return {cid: self._mapping.get(cid) for cid, _cnm, _idx in self._salidas}


class _DialogoReglasLogicas(Gtk.Dialog):
    """
    Editor de reglas lógicas de equipo (AND / OR) — generaliza el caso
    "DSK necesita todas sus entradas salvo BKGD B" a cualquier equipo.

    Flujo:
      • Se listan las reglas EFECTIVAS del equipo (propias si tiene, si no
        las heredadas de su tipo_equipo — con aviso de que son de
        plantilla y un botón para "bajarlas" y poder editarlas).
      • Armado de una regla nueva: tildar conectores de ENTRADA (miembros),
        elegir operador AND/OR, elegir qué SALIDAS gobierna (Todas por
        defecto), "+ Agregar regla".
      • Al Guardar: se reemplazan por completo las reglas propias del
        equipo por las que quedaron en la lista (mismo patrón todo-o-nada
        que "Editar matriz").

    No soporta desde acá crear reglas encadenadas (miembro = resultado de
    otra regla) ni reglas de plantilla (tipo_equipo) — para lógica
    compuesta avanzada, cargar directamente vía Modelo.guardar_regla_logica.
    """

    def __init__(self, id_equipo, nombre_equipo, id_tipo_equipo, parent=None):
        super().__init__(
            title=f"Reglas lógicas — {nombre_equipo}",
            transient_for=parent, modal=True, destroy_with_parent=True,
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "💾 " + _("Guardar"), Gtk.ResponseType.OK)
        self.set_default_size(760, 560)

        self._id_equipo = id_equipo
        self._id_tipo_equipo = id_tipo_equipo

        con_rows = Modelo.devolver_conectores_de_equipo(id_equipo)
        # Tipos de conector que cuentan como "entrada" para armar una regla:
        # IN (señal normal) y REFIN (entrada de referencia — blackburst/
        # tri-level sync). REFOUT no entra acá: ya se trata aparte como
        # "fuente" en el resto del motor (GraphImpactAnalyzer._leer_bd).
        TIPOS_ENTRADA = {"IN", "REFIN"}
        self._entradas = [(str(cid), s(nom)) for cid, nom, tipo in con_rows
                           if str(tipo or "").upper() in TIPOS_ENTRADA]
        self._salidas  = [(str(cid), s(nom)) for cid, nom, tipo in con_rows
                           if str(tipo or "").upper() == "OUT"]
        self._nombre_conector = {cid: nom for cid, nom in self._entradas + self._salidas}

        # Grupos ya "confirmados" en esta sesión de edición (se persisten
        # todos juntos al Guardar). Cada uno: {"operador","miembros":[id_conector,...],
        # "salidas":[id_conector,...] (vacío = todas)}
        self._grupos: list[dict] = []
        self._chks_entrada: dict[str, Gtk.CheckButton] = {}
        self._chks_salida:  dict[str, Gtk.CheckButton] = {}

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(10);   area.set_margin_bottom(8)

        info = Modelo.listar_reglas_de_equipo(id_equipo, id_tipo_equipo)
        origen = info[0]["origen"] if info else "equipo"
        self._origen_actual = origen

        self._banner = Gtk.Label(xalign=0)
        self._banner.set_line_wrap(True)
        area.pack_start(self._banner, False, False, 0)
        self._btn_bajar_plantilla = Gtk.Button(
            label=_("⤵ Copiar del tipo de equipo para editar acá"))
        self._btn_bajar_plantilla.connect("clicked", self._bajar_plantilla)
        area.pack_start(self._btn_bajar_plantilla, False, False, 0)

        area.pack_start(Gtk.Separator(), False, False, 2)

        # ── Armado de una regla nueva ────────────────────────────────────
        lbl1 = Gtk.Label(xalign=0)
        lbl1.set_markup("<b>Entradas</b> — tildá las que forman parte de la nueva regla")
        area.pack_start(lbl1, False, False, 0)

        sw_in = Gtk.ScrolledWindow()
        sw_in.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw_in.set_min_content_height(64)
        box_in = Gtk.Box(spacing=4)
        for cid, nom in self._entradas:
            chk = Gtk.CheckButton(label=nom)
            box_in.pack_start(chk, False, False, 0)
            self._chks_entrada[cid] = chk
        sw_in.add(box_in)
        area.pack_start(sw_in, False, False, 0)

        hbox_op = Gtk.Box(spacing=10)
        hbox_op.pack_start(Gtk.Label(label=_("Operador:")), False, False, 0)
        self._rb_and = Gtk.RadioButton.new_with_label(None, "AND (requiere todas)")
        self._rb_or  = Gtk.RadioButton.new_with_label_from_widget(
            self._rb_and, "OR (alcanza con una)")
        hbox_op.pack_start(self._rb_and, False, False, 0)
        hbox_op.pack_start(self._rb_or, False, False, 0)
        area.pack_start(hbox_op, False, False, 4)

        lbl2 = Gtk.Label(xalign=0)
        lbl2.set_markup("<b>Salidas gobernadas</b>")
        area.pack_start(lbl2, False, False, 0)
        self._chk_todas_salidas = Gtk.CheckButton(label=_("Todas las salidas"))
        self._chk_todas_salidas.set_active(True)
        self._chk_todas_salidas.connect("toggled", self._toggle_todas_salidas)
        area.pack_start(self._chk_todas_salidas, False, False, 0)

        sw_out = Gtk.ScrolledWindow()
        sw_out.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw_out.set_min_content_height(56)
        box_out = Gtk.Box(spacing=4)
        for cid, nom in self._salidas:
            chk = Gtk.CheckButton(label=nom)
            chk.set_sensitive(False)
            box_out.pack_start(chk, False, False, 0)
            self._chks_salida[cid] = chk
        sw_out.add(box_out)
        area.pack_start(sw_out, False, False, 0)

        btn_agregar = Gtk.Button(label=_("+ Agregar regla"))
        btn_agregar.connect("clicked", self._agregar_grupo)
        area.pack_start(btn_agregar, False, False, 4)

        area.pack_start(Gtk.Separator(), False, False, 2)

        lbl3 = Gtk.Label(xalign=0)
        lbl3.set_markup("<b>Reglas de este equipo</b>")
        area.pack_start(lbl3, False, False, 0)

        sw_lista = Gtk.ScrolledWindow()
        sw_lista.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._lista_grupos = Gtk.ListBox()
        sw_lista.add(self._lista_grupos)
        area.pack_start(sw_lista, True, True, 0)

        # Precargar grupos existentes (si el origen ya es "equipo")
        if origen == "equipo":
            for regla in info:
                miembros = [m["ref"] for m in regla["miembros"] if m["tipo"] == "conector"]
                if not miembros:
                    continue  # regla encadenada o inválida: no editable desde este diálogo simple
                self._grupos.append({
                    "operador": regla["operador"],
                    "miembros": miembros,
                    "salidas": list(regla["salidas"]),
                })

        self._actualizar_banner(origen)
        self._refrescar_lista()
        self.show_all()

    # ── helpers ───────────────────────────────────────────────────────────
    def _actualizar_banner(self, origen):
        if origen == "tipo":
            self._banner.set_markup(
                "<i>Este equipo no tiene reglas propias — está usando las de su "
                "tipo de equipo (plantilla). Podés agregarlas/editarlas acá, pero "
                "primero hay que copiarlas para no afectar a otros equipos del "
                "mismo tipo.</i>")
            self._btn_bajar_plantilla.set_visible(True)
        else:
            self._banner.set_markup(
                "<i>Reglas propias de este equipo.</i>")
            self._btn_bajar_plantilla.set_visible(False)

    def _bajar_plantilla(self, _btn):
        Modelo.copiar_reglas_de_tipo_a_equipo(self._id_equipo, self._id_tipo_equipo)
        info = Modelo.listar_reglas_de_equipo(self._id_equipo, self._id_tipo_equipo)
        self._grupos = []
        for regla in info:
            miembros = [m["ref"] for m in regla["miembros"] if m["tipo"] == "conector"]
            if miembros:
                self._grupos.append({
                    "operador": regla["operador"], "miembros": miembros,
                    "salidas": list(regla["salidas"]),
                })
        self._origen_actual = "equipo"
        self._actualizar_banner("equipo")
        self._refrescar_lista()

    def _toggle_todas_salidas(self, chk):
        activo = not chk.get_active()
        for cb in self._chks_salida.values():
            cb.set_sensitive(activo)
            if not activo:
                cb.set_active(False)

    def _agregar_grupo(self, _btn):
        miembros = [cid for cid, chk in self._chks_entrada.items() if chk.get_active()]
        if len(miembros) < 1:
            return
        salidas = [] if self._chk_todas_salidas.get_active() else \
            [cid for cid, chk in self._chks_salida.items() if chk.get_active()]
        operador = "AND" if self._rb_and.get_active() else "OR"
        self._grupos.append({"operador": operador, "miembros": miembros, "salidas": salidas})
        for chk in self._chks_entrada.values():
            chk.set_active(False)
        for chk in self._chks_salida.values():
            chk.set_active(False)
        self._chk_todas_salidas.set_active(True)
        self._rb_and.set_active(True)
        self._refrescar_lista()

    def _refrescar_lista(self):
        for row in list(self._lista_grupos.get_children()):
            self._lista_grupos.remove(row)
        for idx, grupo in enumerate(self._grupos):
            fila = Gtk.Box(spacing=8, orientation=Gtk.Orientation.HORIZONTAL)
            fila.set_margin_top(4); fila.set_margin_bottom(4)
            fila.set_margin_start(6); fila.set_margin_end(6)

            nombres_miembros = " Y ".join(self._nombre_conector.get(c, c) for c in grupo["miembros"]) \
                if grupo["operador"] == "AND" else \
                " O ".join(self._nombre_conector.get(c, c) for c in grupo["miembros"])
            if grupo["salidas"]:
                txt_salidas = "salidas: " + ", ".join(
                    self._nombre_conector.get(c, c) for c in grupo["salidas"])
            else:
                txt_salidas = "todas las salidas"

            lbl = Gtk.Label(xalign=0)
            lbl.set_line_wrap(True)
            lbl.set_markup(
                f"<b>[{grupo['operador']}]</b> {GLib.markup_escape_text(nombres_miembros)}"
                f"\n<span size='small' foreground='#888'>→ {GLib.markup_escape_text(txt_salidas)}</span>")
            fila.pack_start(lbl, True, True, 0)

            btn_del = Gtk.Button(label="✕")
            btn_del.set_tooltip_text(_("Eliminar esta regla"))
            btn_del.connect("clicked", lambda _b, i=idx: self._eliminar_grupo(i))
            fila.pack_start(btn_del, False, False, 0)

            self._lista_grupos.add(fila)
        self._lista_grupos.show_all()

    def _eliminar_grupo(self, idx):
        del self._grupos[idx]
        self._refrescar_lista()

    def guardar(self):
        """Reemplaza por completo las reglas PROPIAS del equipo por las que
        quedaron armadas acá (todo-o-nada, mismo patrón que 'Editar
        matriz'). Se asume que el llamador sólo hace esto si la respuesta
        del diálogo fue Gtk.ResponseType.OK."""
        Modelo.asegurar_tablas_regla_logica()
        existentes = Modelo._query(
            "SELECT id_regla FROM regla_logica WHERE id_equipo=?", (self._id_equipo,))
        for (id_regla,) in existentes:
            Modelo.eliminar_regla_logica(id_regla)
        for orden, grupo in enumerate(self._grupos):
            Modelo.guardar_regla_logica(
                None, id_equipo=self._id_equipo,
                nombre=f"Regla {orden + 1}", operador=grupo["operador"],
                activa=True, orden=orden,
                miembros=[{"tipo": "conector", "ref": c} for c in grupo["miembros"]],
                salidas=grupo["salidas"])


def abrir_reglas_logicas(id_equipo, nombre_equipo, id_tipo_equipo, parent=None):
    """Abre el editor de reglas lógicas (AND/OR) del equipo. Guarda sólo si
    el usuario confirma con OK (mismo patrón que abrir_ruteo_matriz)."""
    dlg = _DialogoReglasLogicas(id_equipo, nombre_equipo, id_tipo_equipo, parent=parent)
    resp = dlg.run()
    if resp == Gtk.ResponseType.OK:
        dlg.guardar()
    dlg.destroy()
    return resp == Gtk.ResponseType.OK


class _DialogoReglasLogicasMolde(Gtk.Dialog):
    """
    Editor de reglas lógicas (AND / OR) de un MOLDE de catálogo
    (equipo_catalogo). Mismo flujo que _DialogoReglasLogicas, pero:
      • Lee/guarda en las tablas propias de catálogo (regla_logica_catalogo
        y afines — ver Modelo.asegurar_tablas_regla_logica_catalogo), no en
        las de equipos reales.
      • No hay banner de "heredado del tipo" — el molde es el propio dueño
        que se está editando, no hereda de nada.
      • Las reglas definidas acá se copian automáticamente a cada equipo
        que se instancie desde este molde (Modelo.instanciar_desde_catalogo
        → copiar_reglas_de_molde_a_equipo) — el usuario no tiene que
        volver a armarlas a mano por cada equipo nuevo.

    Igual que la versión de equipo: no soporta crear reglas encadenadas
    desde acá (para eso, cargar directamente vía
    Modelo.guardar_regla_logica_catalogo).
    """

    def __init__(self, id_equipo_catalogo, nombre_molde, parent=None):
        super().__init__(
            title=f"Reglas lógicas — {nombre_molde} (molde)",
            transient_for=parent, modal=True, destroy_with_parent=True,
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "💾 " + _("Guardar"), Gtk.ResponseType.OK)
        self.set_default_size(760, 560)

        self._id_equipo_catalogo = id_equipo_catalogo

        con_rows = Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo)
        # con_rows: (id_cc, nombre, tipo_nom, id_tipo_conector, id_imagen, img_path, x, y)
        TIPOS_ENTRADA = {"IN", "REFIN"}
        self._entradas = [(str(r[0]), s(r[1])) for r in con_rows
                           if str(r[2] or "").upper() in TIPOS_ENTRADA]
        self._salidas  = [(str(r[0]), s(r[1])) for r in con_rows
                           if str(r[2] or "").upper() == "OUT"]
        self._nombre_conector = {cid: nom for cid, nom in self._entradas + self._salidas}

        self._grupos: list[dict] = []
        self._chks_entrada: dict[str, Gtk.CheckButton] = {}
        self._chks_salida:  dict[str, Gtk.CheckButton] = {}

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(10);   area.set_margin_bottom(8)

        info = Gtk.Label(xalign=0)
        info.set_line_wrap(True)
        info.set_markup(
            "<i>Estas reglas se copian automáticamente a cada equipo que se "
            "instancie desde este molde — no hace falta volver a armarlas "
            "a mano por cada equipo nuevo.</i>")
        area.pack_start(info, False, False, 0)

        area.pack_start(Gtk.Separator(), False, False, 2)

        lbl1 = Gtk.Label(xalign=0)
        lbl1.set_markup("<b>Entradas</b> — tildá las que forman parte de la nueva regla")
        area.pack_start(lbl1, False, False, 0)

        sw_in = Gtk.ScrolledWindow()
        sw_in.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw_in.set_min_content_height(64)
        box_in = Gtk.Box(spacing=4)
        for cid, nom in self._entradas:
            chk = Gtk.CheckButton(label=nom)
            box_in.pack_start(chk, False, False, 0)
            self._chks_entrada[cid] = chk
        sw_in.add(box_in)
        area.pack_start(sw_in, False, False, 0)

        hbox_op = Gtk.Box(spacing=10)
        hbox_op.pack_start(Gtk.Label(label=_("Operador:")), False, False, 0)
        self._rb_and = Gtk.RadioButton.new_with_label(None, "AND (requiere todas)")
        self._rb_or  = Gtk.RadioButton.new_with_label_from_widget(
            self._rb_and, "OR (alcanza con una)")
        hbox_op.pack_start(self._rb_and, False, False, 0)
        hbox_op.pack_start(self._rb_or, False, False, 0)
        area.pack_start(hbox_op, False, False, 4)

        lbl2 = Gtk.Label(xalign=0)
        lbl2.set_markup("<b>Salidas gobernadas</b>")
        area.pack_start(lbl2, False, False, 0)
        self._chk_todas_salidas = Gtk.CheckButton(label=_("Todas las salidas"))
        self._chk_todas_salidas.set_active(True)
        self._chk_todas_salidas.connect("toggled", self._toggle_todas_salidas)
        area.pack_start(self._chk_todas_salidas, False, False, 0)

        sw_out = Gtk.ScrolledWindow()
        sw_out.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw_out.set_min_content_height(56)
        box_out = Gtk.Box(spacing=4)
        for cid, nom in self._salidas:
            chk = Gtk.CheckButton(label=nom)
            chk.set_sensitive(False)
            box_out.pack_start(chk, False, False, 0)
            self._chks_salida[cid] = chk
        sw_out.add(box_out)
        area.pack_start(sw_out, False, False, 0)

        btn_agregar = Gtk.Button(label=_("+ Agregar regla"))
        btn_agregar.connect("clicked", self._agregar_grupo)
        area.pack_start(btn_agregar, False, False, 4)

        area.pack_start(Gtk.Separator(), False, False, 2)

        lbl3 = Gtk.Label(xalign=0)
        lbl3.set_markup("<b>Reglas de este molde</b>")
        area.pack_start(lbl3, False, False, 0)

        sw_lista = Gtk.ScrolledWindow()
        sw_lista.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._lista_grupos = Gtk.ListBox()
        sw_lista.add(self._lista_grupos)
        area.pack_start(sw_lista, True, True, 0)

        # Precargar grupos existentes del molde
        for regla in Modelo.listar_reglas_de_molde(id_equipo_catalogo):
            miembros = [m["ref"] for m in regla["miembros"] if m["tipo"] == "conector_catalogo"]
            if not miembros:
                continue  # regla encadenada: no editable desde este diálogo simple
            self._grupos.append({
                "operador": regla["operador"],
                "miembros": miembros,
                "salidas": list(regla["salidas"]),
            })

        self._refrescar_lista()
        self.show_all()

    # ── helpers (idénticos a _DialogoReglasLogicas, salvo dónde persisten) ──
    def _toggle_todas_salidas(self, chk):
        activo = not chk.get_active()
        for cb in self._chks_salida.values():
            cb.set_sensitive(activo)
            if not activo:
                cb.set_active(False)

    def _agregar_grupo(self, _btn):
        miembros = [cid for cid, chk in self._chks_entrada.items() if chk.get_active()]
        if len(miembros) < 1:
            return
        salidas = [] if self._chk_todas_salidas.get_active() else \
            [cid for cid, chk in self._chks_salida.items() if chk.get_active()]
        operador = "AND" if self._rb_and.get_active() else "OR"
        self._grupos.append({"operador": operador, "miembros": miembros, "salidas": salidas})
        for chk in self._chks_entrada.values():
            chk.set_active(False)
        for chk in self._chks_salida.values():
            chk.set_active(False)
        self._chk_todas_salidas.set_active(True)
        self._rb_and.set_active(True)
        self._refrescar_lista()

    def _refrescar_lista(self):
        for row in list(self._lista_grupos.get_children()):
            self._lista_grupos.remove(row)
        for idx, grupo in enumerate(self._grupos):
            fila = Gtk.Box(spacing=8, orientation=Gtk.Orientation.HORIZONTAL)
            fila.set_margin_top(4); fila.set_margin_bottom(4)
            fila.set_margin_start(6); fila.set_margin_end(6)

            sep = " Y " if grupo["operador"] == "AND" else " O "
            nombres_miembros = sep.join(self._nombre_conector.get(c, c) for c in grupo["miembros"])
            if grupo["salidas"]:
                txt_salidas = "salidas: " + ", ".join(
                    self._nombre_conector.get(c, c) for c in grupo["salidas"])
            else:
                txt_salidas = "todas las salidas"

            lbl = Gtk.Label(xalign=0)
            lbl.set_line_wrap(True)
            lbl.set_markup(
                f"<b>[{grupo['operador']}]</b> {GLib.markup_escape_text(nombres_miembros)}"
                f"\n<span size='small' foreground='#888'>→ {GLib.markup_escape_text(txt_salidas)}</span>")
            fila.pack_start(lbl, True, True, 0)

            btn_del = Gtk.Button(label="✕")
            btn_del.set_tooltip_text(_("Eliminar esta regla"))
            btn_del.connect("clicked", lambda _b, i=idx: self._eliminar_grupo(i))
            fila.pack_start(btn_del, False, False, 0)

            self._lista_grupos.add(fila)
        self._lista_grupos.show_all()

    def _eliminar_grupo(self, idx):
        del self._grupos[idx]
        self._refrescar_lista()

    def guardar(self):
        """Reemplaza por completo las reglas del molde por las que
        quedaron armadas acá (todo-o-nada, mismo patrón que 'Editar
        matriz' / _DialogoReglasLogicas). Se asume que el llamador sólo
        hace esto si la respuesta del diálogo fue Gtk.ResponseType.OK."""
        Modelo.asegurar_tablas_regla_logica_catalogo()
        existentes = Modelo._query(
            "SELECT id_regla_logica_catalogo FROM regla_logica_catalogo "
            "WHERE id_equipo_catalogo=?", (self._id_equipo_catalogo,))
        for (id_regla,) in existentes:
            Modelo.eliminar_regla_logica_catalogo(id_regla)
        for orden, grupo in enumerate(self._grupos):
            Modelo.guardar_regla_logica_catalogo(
                None, id_equipo_catalogo=self._id_equipo_catalogo,
                nombre=f"Regla {orden + 1}", operador=grupo["operador"],
                activa=True, orden=orden,
                miembros=[{"tipo": "conector_catalogo", "ref": c} for c in grupo["miembros"]],
                salidas=grupo["salidas"])


def abrir_reglas_logicas_molde(id_equipo_catalogo, nombre_molde, parent=None):
    """Abre el editor de reglas lógicas (AND/OR) del MOLDE de catálogo.
    Guarda sólo si el usuario confirma con OK."""
    dlg = _DialogoReglasLogicasMolde(id_equipo_catalogo, nombre_molde, parent=parent)
    resp = dlg.run()
    if resp == Gtk.ResponseType.OK:
        dlg.guardar()
    dlg.destroy()
    return resp == Gtk.ResponseType.OK


class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin, RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin, VistaPreviaMixin, DiagnosticoMixin, GrafoMixin, DibujoMixin, InteraccionMixin, EdicionConexionesMixin, LayoutMixin, BusquedaMixin, ExportMixin, RuteoInternoMixin, Gtk.Dialog):
    """
    Node-based diagram: each equipment = node with IN/OUT ports;
    cables = Bézier curves connecting ports.

    Controls:
      • Drag node        — move (position saved to DB)
      • Scroll wheel     — zoom (centred on cursor)
      • Middle/right drag— pan
      • Click node       — select (highlights its connections)
      • Double-click     — open equipment detail dialog
      • Drag port→port   — create a new connection between two ports of
                            different nodes (search existing cable or
                            create one by code) — same gesture as the
                            classic EditorConexiones editor
      • ⊞ Encuadrar      — fit all nodes in view
      • ⊕ Expandir       — add neighbours of selected node(s); with
                            multiple nodes selected, expands each one's
                            neighbours in the same pass — Ctrl+E
    """

    # ── geometry (world units) ──────────────────────────────────────────────
    NODE_W   = 230
    HDR_H    = 30
    PORT_H   = 20
    PORT_PAD = 8
    PORT_R   = 5

    # ── minimapa (solo vista global, sin id_equipo) ──────────────────────────
    MINIMAP_W      = 220
    MINIMAP_H      = 150
    MINIMAP_MARGIN = 14
    ZOOM_INICIAL_GLOBAL = 1.5

    # ── colours ────────────────────────────────────────────────────────────
    C_BG        = (0.11, 0.12, 0.15)
    C_GRID      = (0.16, 0.17, 0.21)
    C_NODE      = (0.19, 0.21, 0.26)
    C_NODE_SEL  = (0.26, 0.29, 0.39)
    C_NODE_B    = (0.33, 0.36, 0.46)
    C_NODE_BSEL = (0.65, 0.70, 0.95)
    C_PORT_IN   = (0.32, 0.62, 0.95)
    C_PORT_OUT  = (0.95, 0.58, 0.22)
    C_CONN      = (0.48, 0.52, 0.62)
    C_CONN_SEL  = (0.95, 0.82, 0.28)
    C_TXT_H     = (0.94, 0.95, 0.97)
    C_TXT_SUB   = (0.58, 0.60, 0.68)
    C_TXT_PORT  = (0.72, 0.74, 0.80)
    C_TXT_CABLE = (0.72, 0.74, 0.44)

    def __init__(self, id_equipo=None, parent=None, iniciar_vacio=False):
        """
        iniciar_vacio: si True, el diagrama arranca sin nodos (en vez de
        cargar el equipo/vecinos indicados o la vista global de todo lo ya
        conectado) y muestra abierto el panel lateral de "Agregar equipo"
        (búsqueda + drag&drop). Usado por la "Alta rápida de conexiones"
        (ver cabledoc.py _abrir_editor_conexiones), que ahora reutiliza esta
        misma pantalla en vez del editor de nodos custom EditorConexiones
        (ver plan/registro en changelog.txt). No afecta el uso normal de
        "Diagrama de conexiones" (iniciar_vacio=False por defecto).
        """
        super().__init__(
            title=_("Alta rápida de conexiones") if iniciar_vacio else _("Diagrama de conexiones"),
            transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1280, 820)

        # state
        self._nodos      = {}    # {id_equipo_str: dict}
        self._conns      = []    # [dict]
        self._conns_extension = []  # [dict] — cadenas via extension_cable
                                     # (Fase 3 de plan_desarrollo_extension_
                                     # cable.md), ver grafo_diagrama_ui.py
                                     # _construir_conexiones_extension
        self._sel_id     = None    # id del nodo "primario" (compatibilidad)
        self._sel_ids    = set()   # set de ids seleccionados (multiselect)
        self._id_inicio  = str(id_equipo) if id_equipo else None
        self._iniciar_vacio = iniciar_vacio
        self._solo_nombre = False
        self._estilo_conn = "bezier"   # "bezier" | "recto" | "directo"
        self._line_jumps  = False
        # Cables que sólo tienen una punta documentada. No son conexiones
        # normales del diagrama (no hay segundo equipo/nodo): se dibujan de
        # forma auxiliar desde las entradas del equipo seleccionado.
        self._conexiones_incompletas_activo = False
        self._conexiones_incompletas = []
        self._icono_conexion_incompleta = None
        # Variante "todas": mismo concepto pero para TODOS los equipos
        # visibles en el diagrama a la vez, no sólo el equipo seleccionado.
        # Mutuamente excluyente con _conexiones_incompletas_activo (ver
        # _on_toggle_conexiones_incompletas / _on_toggle_todas_conexiones_incompletas).
        self._todas_conexiones_incompletas_activo = False
        self._todas_conexiones_incompletas = []

        # pan / zoom / drag
        self._zoom     = 1.0
        self._pan_x    = 0.0
        self._pan_y    = 0.0
        self._drag_id  = None
        self._drag_ox  = 0.0
        self._drag_oy  = 0.0
        # offset de cada nodo del grupo al iniciar el drag
        self._drag_offsets: dict = {}   # {id: (ox, oy)}
        self._panning  = False
        # Arrastre de un puerto a otro para crear una conexión nueva (mismo
        # gesto que tenía el editor clásico EditorConexiones/"modo
        # clásico"): (nodo, con_id, lado) del puerto donde arrancó el
        # arrastre, o None si no hay ninguno en curso. _wire_mx/_wire_my
        # son la posición actual del cursor en coordenadas mundo, para
        # dibujar el cable "elástico" mientras se arrastra.
        self._wire_from = None
        self._wire_mx = self._wire_my = 0.0
        # rubber-band selection
        self._rband_active = False
        self._rband_x0 = self._rband_y0 = 0.0   # coords mundo
        self._rband_x1 = self._rband_y1 = 0.0
        self._pan_mx   = 0.0
        self._pan_my   = 0.0
        self._pan_ox   = 0.0
        self._pan_oy   = 0.0
        # minimapa (solo vista global)
        self._minimap_rect = None
        self._minimap_dragging = False
        # "Conexión interna" — muestra el bypass A_BACK/B_BACK de un
        # módulo patchera seleccionado según los cables en A_FRONT/B_FRONT
        self._conex_interna_activo = False
        self._conex_interna_id     = None   # id_equipo mostrado
        self._conex_interna_estado = None   # dict de _calc_conexion_interna()

        area = self.get_content_area()

        # ── barra de menús desplegable, ordenada por función ───────────────────
        # (antes: dos filas de botones sueltos. Ahora cada grupo funcional
        # vive en su propio menú: Ver / Buscar / Exportar / Impacto / Riesgo /
        # Señal / Escenario / Herramientas — ver changelog.txt)
        menubar = Gtk.MenuBar()

        # ── "Ver": navegación básica, visualización, alineación ────────────────
        menu_ver = Gtk.Menu()
        for lbl, fn in [
            ("⊞ Encuadrar todo",   lambda _: self._fit_all()),
            ("↺ Recargar",         lambda _: self._recargar()),
        ]:
            it = Gtk.MenuItem(label=lbl)
            it.connect("activate", fn)
            menu_ver.append(it)

        btn_expandir_menu = Gtk.MenuItem(label=_("⊕ Expandir vecinos  (Ctrl+E)"))
        btn_expandir_menu.set_tooltip_text(
            "Agrega los vecinos (conectados por cable) del nodo "
            "seleccionado. Si hay varios nodos seleccionados a la vez "
            "(rubber-band o Shift/Ctrl+clic), expande los vecinos de "
            "TODOS ellos en la misma pasada, cada uno alrededor de su "
            "propio nodo.  Atajo: Ctrl+E.")
        btn_expandir_menu.connect("activate", lambda _: self._expandir())
        menu_ver.append(btn_expandir_menu)

        menu_ver.append(Gtk.SeparatorMenuItem())

        # "🧩 Panel de equipos" (buscar/arrastrar equipos al canvas): sólo
        # tiene sentido en Alta rápida de conexiones (iniciar_vacio=True),
        # que arranca vacía y necesita esa vía para poblar el canvas. En
        # el Diagrama de conexiones normal el canvas ya viene cargado con
        # los equipos/conexiones existentes — no se ofrece esta forma de
        # agregar equipos sueltos ahí (ver changelog.txt).
        if self._iniciar_vacio:
            self._chk_panel_agregar = Gtk.CheckMenuItem(
                label=_("🧩 Panel de equipos (buscar / arrastrar)"))
            self._chk_panel_agregar.set_tooltip_text(
                "Muestra/oculta el panel lateral para buscar equipos y "
                "arrastrarlos al canvas, agregándolos al diagrama.")
            self._chk_panel_agregar.set_active(False)
            self._chk_panel_agregar.connect("toggled", self._on_toggle_panel_agregar)
            menu_ver.append(self._chk_panel_agregar)

            menu_ver.append(Gtk.SeparatorMenuItem())

        self._chk_solo = Gtk.CheckMenuItem(label=_("Mostrar solo nombre nodo"))
        self._chk_solo.set_active(False)
        self._chk_solo.connect("toggled", self._on_toggle_solo_nombre)
        menu_ver.append(self._chk_solo)

        item_estilo = Gtk.MenuItem(label=_("Estilo de conexión"))
        submenu_estilo = Gtk.Menu()
        primer_radio = None
        for key, lbl in [("bezier", "Curva Bézier"),
                         ("recto",  "Ángulos rectos"),
                         ("directo","Línea directa")]:
            r = Gtk.RadioMenuItem.new_with_label_from_widget(primer_radio, lbl)
            if primer_radio is None:
                primer_radio = r
            if key == "bezier":
                r.set_active(True)
            r.connect("toggled", self._on_estilo_menu_toggled, key)
            submenu_estilo.append(r)
        item_estilo.set_submenu(submenu_estilo)
        menu_ver.append(item_estilo)

        self._chk_jumps = Gtk.CheckMenuItem(label=_("Line jumps"))
        self._chk_jumps.set_active(False)
        # Los line jumps no aplican (ni se calculan) en curvas Bézier
        self._chk_jumps.set_sensitive(self._estilo_conn != "bezier")
        self._chk_jumps.connect("toggled", lambda b: self._on_jumps_toggled(b))
        menu_ver.append(self._chk_jumps)

        self._chk_conexiones_incompletas = Gtk.CheckMenuItem(
            label=_("Mostrar conexiones incompletas"))
        self._chk_conexiones_incompletas.set_tooltip_text(
            "Para el equipo seleccionado, muestra los cables conectados a "
            "una entrada o salida que sólo tienen una punta documentada. "
            "El cono indica el extremo/equipo aún no relevado.")
        self._chk_conexiones_incompletas.connect(
            "toggled", self._on_toggle_conexiones_incompletas)
        menu_ver.append(self._chk_conexiones_incompletas)

        self._chk_todas_conexiones_incompletas = Gtk.CheckMenuItem(
            label=_("Mostrar todas las conexiones incompletas"))
        self._chk_todas_conexiones_incompletas.set_tooltip_text(
            "Muestra, para TODOS los equipos visibles en el diagrama a la "
            "vez, los cables conectados a una entrada o salida que sólo "
            "tienen una punta documentada. Se desactiva automáticamente "
            "«Mostrar conexiones incompletas» (por equipo seleccionado) "
            "para no duplicar los tramos.")
        self._chk_todas_conexiones_incompletas.connect(
            "toggled", self._on_toggle_todas_conexiones_incompletas)
        menu_ver.append(self._chk_todas_conexiones_incompletas)

        menu_ver.append(Gtk.SeparatorMenuItem())

        btn_h = Gtk.MenuItem(label=_("↔ Alinear horizontal"))
        btn_h.set_tooltip_text("Alinear nodos seleccionados horizontalmente (usando Y del nodo más a la derecha)")
        btn_h.connect("activate", lambda _: self._alinear_horizontal())
        menu_ver.append(btn_h)

        btn_v = Gtk.MenuItem(label=_("↕ Alinear vertical"))
        btn_v.set_tooltip_text("Alinear nodos seleccionados verticalmente (usando X del nodo más arriba)")
        btn_v.connect("activate", lambda _: self._alinear_vertical())
        menu_ver.append(btn_v)

        # "🧲 Auto-organizar (sin solape)": sólo en Alta rápida de
        # conexiones (iniciar_vacio=True). Ahí los equipos se van
        # agregando sueltos —arrastrados del panel lateral o con doble
        # clic centrado en la vista— y es fácil terminar con nodos
        # pisándose entre sí; este botón los reacomoda automáticamente
        # para que no se superpongan, sin necesidad de acomodarlos a
        # mano uno por uno. No se muestra en el Diagrama de conexiones
        # normal (ver changelog.txt).
        if self._iniciar_vacio:
            menu_ver.append(Gtk.SeparatorMenuItem())
            btn_auto_pos = Gtk.MenuItem(label=_("🧲 Auto-organizar nodos (sin solape)"))
            btn_auto_pos.set_tooltip_text(
                "Reubica automáticamente todos los nodos del canvas para "
                "que ninguno quede superpuesto con otro. Mantiene la "
                "disposición general (no reordena por tipo ni por "
                "conexiones), sólo los separa lo necesario. No guarda las "
                "posiciones en la base de datos: es sólo para esta "
                "sesión de edición, hasta que muevas un nodo a mano.")
            btn_auto_pos.connect("activate", lambda _: self._auto_posicionar_sin_solape())
            menu_ver.append(btn_auto_pos)

        item_ver = Gtk.MenuItem(label=_("Ver"))
        item_ver.set_submenu(menu_ver)
        menubar.append(item_ver)

        # ── "Buscar" ─────────────────────────────────────────────────────────
        menu_buscar = Gtk.Menu()
        btn_buscar = Gtk.MenuItem(label=_("🔍 Buscar equipo o cable…"))
        btn_buscar.set_tooltip_text("Buscar equipo o cable en el diagrama  (Ctrl+F)")
        btn_buscar.connect("activate", lambda _: self._buscar_abrir_dialogo())
        menu_buscar.append(btn_buscar)
        menu_buscar.append(Gtk.SeparatorMenuItem())
        btn_agregar_equipo = Gtk.MenuItem(label=_("➕ Agregar equipo al diagrama…"))
        btn_agregar_equipo.set_tooltip_text(
            "Buscar un equipo (aún no esté o ya esté en el diagrama) y "
            "agregarlo al canvas. Equivalente a arrastrarlo desde el "
            "panel lateral de equipos.")
        btn_agregar_equipo.connect("activate", lambda _: self._agregar_equipo_via_dialogo())
        menu_buscar.append(btn_agregar_equipo)
        item_buscar = Gtk.MenuItem(label=_("Buscar"))
        item_buscar.set_submenu(menu_buscar)
        menubar.append(item_buscar)

        # ── "Exportar" ───────────────────────────────────────────────────────
        menu_exportar = Gtk.Menu()
        btn_svg = Gtk.MenuItem(label=_("⧡ Exportar como SVG"))
        btn_svg.set_tooltip_text("Exportar diagrama como SVG vectorial")
        btn_svg.connect("activate", lambda _: self._exportar("svg"))
        menu_exportar.append(btn_svg)
        btn_pdf = Gtk.MenuItem(label=_("📄 Exportar como PDF"))
        btn_pdf.set_tooltip_text("Exportar diagrama como PDF")
        btn_pdf.connect("activate", lambda _: self._exportar("pdf"))
        menu_exportar.append(btn_pdf)
        item_exportar = Gtk.MenuItem(label=_("Exportar"))
        item_exportar.set_submenu(menu_exportar)
        menubar.append(item_exportar)

        # ── "Impacto": análisis de impacto de falla de cable ────────────────────
        menu_impacto = Gtk.Menu()
        for w in self._impacto_crear_items_menu():
            menu_impacto.append(w)
        item_impacto = Gtk.MenuItem(label=_("Impacto"))
        item_impacto.set_submenu(menu_impacto)
        menubar.append(item_impacto)

        # ── "Riesgo": coloreo por IRF, simulación de falla, marcado de críticos ─
        menu_riesgo = Gtk.Menu()
        for w in self._riesgo_crear_items_menu():
            menu_riesgo.append(w)

        menu_riesgo.append(Gtk.SeparatorMenuItem())

        btn_marcar_critico = Gtk.MenuItem(label=_("⭐ Marcar críticos"))
        btn_marcar_critico.set_tooltip_text(
            "Marca los equipos seleccionados (rectángulo de selección, o "
            "Shift/Ctrl+clic para ir agregando de a uno) como parte del "
            "conjunto de equipos críticos de la cadena. El cálculo de "
            "riesgo prioriza este conjunto por sobre contar todo el parque "
            "por igual — usá '🔺 Recalcular riesgo' después de marcar."
        )
        btn_marcar_critico.connect("activate", lambda _: self._marcar_criticos(True))
        menu_riesgo.append(btn_marcar_critico)

        btn_desmarcar_critico = Gtk.MenuItem(label=_("☆ Quitar de críticos"))
        btn_desmarcar_critico.set_tooltip_text(
            "Saca los equipos seleccionados del conjunto de equipos críticos."
        )
        btn_desmarcar_critico.connect("activate", lambda _: self._marcar_criticos(False))
        menu_riesgo.append(btn_desmarcar_critico)

        menu_riesgo.append(Gtk.SeparatorMenuItem())
        # Riesgo de CALIDAD de señal (plan_riesgo_senal_audio.md), distinto
        # del riesgo de IMPACTO/falla de arriba — coloreo va sobre el
        # cable, no sobre el equipo.
        for w in self._riesgo_senal_crear_items_menu():
            menu_riesgo.append(w)

        item_riesgo = Gtk.MenuItem(label=_("Riesgo"))
        item_riesgo.set_submenu(menu_riesgo)
        menubar.append(item_riesgo)

        # ── "Señal": coloreo por señal cargada y su leyenda, + vista previa
        # de imagen (ver plan_vista_previa_visual_senal.md) ─────────────────
        menu_senal = Gtk.Menu()
        for w in self._senal_crear_items_menu():
            menu_senal.append(w)
        menu_senal.append(Gtk.SeparatorMenuItem())
        for w in self._visp_crear_items_menu():
            menu_senal.append(w)
        item_senal = Gtk.MenuItem(label=_("Señal"))
        item_senal.set_submenu(menu_senal)
        menubar.append(item_senal)

        # ── "Escenario": modo escenario (fallas/cortes/reconexión simulados) ────
        menu_escenario = Gtk.Menu()
        for w in self._esc_crear_items_menu():
            menu_escenario.append(w)
        menu_escenario.append(Gtk.SeparatorMenuItem())
        for w in self._diag_crear_items_menu():
            menu_escenario.append(w)
        item_escenario = Gtk.MenuItem(label=_("Escenario"))
        item_escenario.set_submenu(menu_escenario)
        menubar.append(item_escenario)

        # ── "Herramientas": conexión interna, edición manual de matriz ──────────
        menu_herr = Gtk.Menu()
        self._btn_conex_interna = Gtk.MenuItem(label=_("🔀 Conexión interna"))
        self._btn_conex_interna.set_tooltip_text(
            "Seleccioná un equipo y hacé clic para ver, con líneas "
            "punteadas, su conexión interna:\n"
            "• Módulo patchera: bypass entrada\u2194salida trasera según cables en derivación/inserción frontal.\n"
            "• DDV: distribución de la señal IN hacia todos los OUT con cable.\n"
            "• MATRIZ: ruteo entrada→salida guardado (la 1ª vez pide asignarlo).")
        self._btn_conex_interna.connect("activate", lambda _: self._toggle_conexion_interna())
        menu_herr.append(self._btn_conex_interna)

        self._btn_editar_matriz = Gtk.MenuItem(label=_("✏️ Editar matriz"))
        self._btn_editar_matriz.set_tooltip_text(
            "Seleccioná una matriz (ej. KUMO 1616) y hacé clic para editar "
            "manualmente su ruteo entrada→salida guardado.")
        self._btn_editar_matriz.connect("activate", lambda _: self._editar_ruteo_matriz_click())
        menu_herr.append(self._btn_editar_matriz)

        item_herr = Gtk.MenuItem(label=_("Herramientas"))
        item_herr.set_submenu(menu_herr)
        menubar.append(item_herr)

        area.pack_start(menubar, False, False, 0)

        # ── fila de estado (informativa, no son botones): selección + zoom ─────
        status_row = Gtk.Box(spacing=6, margin_start=6, margin_end=6,
                              margin_top=3, margin_bottom=3)
        self._lbl_sel = Gtk.Label(label=_("Sin selección"), xalign=0, hexpand=True)
        self._lbl_sel.set_ellipsize(Pango.EllipsizeMode.END)
        self._lbl_sel.set_max_width_chars(60)
        status_row.pack_start(self._lbl_sel, True, True, 0)
        status_row.pack_start(Gtk.Label(label=_("Zoom:")), False, False, 0)
        self._lbl_zoom = Gtk.Label(label=_("100%"))
        status_row.pack_start(self._lbl_zoom, False, False, 0)
        area.pack_start(status_row, False, False, 0)

        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── canvas ──────────────────────────────────────────────────────────
        self._da = Gtk.DrawingArea()
        self._da.set_hexpand(True); self._da.set_vexpand(True)
        self._da.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK   |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.SCROLL_MASK
        )
        self._da.connect("draw",                 self._on_draw)
        self._da.connect("button-press-event",   self._on_press)
        self._da.connect("motion-notify-event",  self._on_motion)
        self._da.connect("button-release-event", self._on_release)
        self._da.connect("scroll-event",         self._on_scroll)
        self._da.set_has_tooltip(True)
        self._da.connect("query-tooltip",        self._senal_on_query_tooltip)

        # ── canvas + panel lateral "Agregar equipo" (búsqueda + drag&drop) ──
        # El panel es un desplegable (Gtk.Revealer) que se muestra/oculta con
        # el checkbox "🧩 Panel de equipos" del menú Ver, o automáticamente
        # al entrar en modo iniciar_vacio (Alta rápida de conexiones). Ese
        # checkbox sólo existe cuando iniciar_vacio=True (ver más abajo): en
        # el Diagrama de conexiones normal el revealer queda armado pero
        # nunca se revela (reveal_child por defecto en False y nada más lo
        # cambia), por lo que el panel queda inutilizable ahí.
        hbox_canvas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hbox_canvas.pack_start(self._da, True, True, 0)

        self._TARGET_EQUIPO = Gtk.TargetEntry.new(
            "cabledoc/id-equipo", Gtk.TargetFlags.SAME_APP, 0)

        self._revealer_agregar = Gtk.Revealer()
        self._revealer_agregar.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_LEFT)
        self._revealer_agregar.set_reveal_child(False)
        self._revealer_agregar.add(self._construir_panel_agregar_equipo())
        hbox_canvas.pack_start(self._revealer_agregar, False, False, 0)

        area.pack_start(hbox_canvas, True, True, 0)

        # El canvas es destino de drag&drop de equipos arrastrados desde el
        # panel lateral: al soltar, se agrega el equipo como nodo nuevo en
        # la posición del cursor.
        self._da.drag_dest_set(
            Gtk.DestDefaults.ALL, [self._TARGET_EQUIPO], Gdk.DragAction.COPY)
        self._da.connect("drag-data-received", self._on_canvas_drag_data_received)

        self._sb = Gtk.Statusbar()
        area.pack_start(self._sb, False, False, 0)

        self.show_all()
        self._impacto_init(DB_PATH)
        self._riesgo_init(DB_PATH)
        self._riesgo_senal_init(DB_PATH)
        self._senal_init(DB_PATH)
        self._esc_init(DB_PATH)
        self._visp_init(DB_PATH)
        self._diag_init(DB_PATH)
        # Estado del buscador
        self._buscar_ids: list[str] = []   # ids de nodos que coinciden
        self._buscar_idx: int = -1         # cual está "activo" (centrado)
        self._buscar_texto: str = ""       # término actual
        # Ctrl+F abre el buscador
        self.connect("key-press-event", self._on_key_global)
        self._cargar(self._id_inicio)

        if self._iniciar_vacio:
            # Alta rápida de conexiones: abrir directamente con el panel de
            # búsqueda/arrastre de equipos visible, ya que el canvas
            # arranca vacío y esa es la vía principal para poblarlo.
            self._chk_panel_agregar.set_active(True)

    # ── panel lateral "Agregar equipo" (búsqueda + drag&drop) ───────────────

    def _construir_panel_agregar_equipo(self):
        """Arma el panel lateral desplegable: entry de búsqueda + lista de
        equipos, con drag source habilitado para arrastrarlos al canvas.
        Reemplaza, para la Alta rápida de conexiones, al panel equivalente
        que tenía el editor de nodos custom EditorConexiones."""
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        panel.set_size_request(260, -1)
        panel.set_margin_start(4); panel.set_margin_end(8)
        panel.set_margin_top(4);   panel.set_margin_bottom(4)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<b>" + _("Agregar equipo") + "</b>")
        panel.pack_start(lbl, False, False, 0)

        fila_busq = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._e_busq_agregar = Gtk.Entry(placeholder_text=_("nombre, tipo, marca…"))
        self._e_busq_agregar.connect("changed", self._on_busq_agregar_changed)
        fila_busq.pack_start(self._e_busq_agregar, True, True, 0)

        # Checkbox "traer con equipos conectados" (tildado por defecto):
        # al agregar un equipo desde el buscador (fila / doble clic /
        # drag&drop), trae también los equipos ya conectados a sus
        # conectores IN y OUT — ver _agregar_vecinos_de/_vecinos_de_equipo.
        self._chk_traer_conectados = Gtk.CheckButton()
        lbl_chk = Gtk.Label(xalign=0)
        lbl_chk.set_markup("<small>" + _("traer con equipos\nconectados") + "</small>")
        lbl_chk.set_line_wrap(True)
        self._chk_traer_conectados.add(lbl_chk)
        self._chk_traer_conectados.set_active(True)
        self._chk_traer_conectados.set_tooltip_text(_(
            "Al agregar un equipo, traer también los equipos ya "
            "conectados a sus entradas y salidas."))
        fila_busq.pack_start(self._chk_traer_conectados, False, False, 0)

        panel.pack_start(fila_busq, False, False, 0)

        self._ls_agregar = Gtk.ListStore(str, str)   # nombre, id
        self._tv_agregar = Gtk.TreeView(model=self._ls_agregar)
        self._tv_agregar.set_headers_visible(False)
        col = Gtk.TreeViewColumn(_("Equipo"), Gtk.CellRendererText(), text=0)
        self._tv_agregar.append_column(col)
        self._tv_agregar.connect("row-activated", self._on_agregar_equipo_row_activated)

        # Drag source: arrastrar una fila hacia el canvas agrega el nodo.
        self._tv_agregar.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK, [self._TARGET_EQUIPO], Gdk.DragAction.COPY)
        self._tv_agregar.connect("drag-data-get", self._on_panel_drag_data_get)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(self._tv_agregar)
        panel.pack_start(sw, True, True, 0)

        lbl2 = Gtk.Label(xalign=0)
        lbl2.set_markup(
            "<small><i>" + _(
                "Arrastrar una fila al canvas para agregar ese equipo "
                "como nodo nuevo. Doble clic: agregarlo centrado en la "
                "vista actual.\n"
                "Una vez en el canvas: arrastrar de un conector a otro "
                "(entre equipos distintos) crea una conexión nueva, "
                "buscando un cable existente o creando uno por código.") + "</i></small>")
        lbl2.set_line_wrap(True)
        panel.pack_start(lbl2, False, False, 0)

        self._poblar_lista_agregar("")
        panel.show_all()
        return panel

    def _poblar_lista_agregar(self, texto):
        self._ls_agregar.clear()
        rows = Modelo._query(
            "SELECT ve.id, ve.nombre || COALESCE(' (' || te.nombre || ')','') "
            "FROM VISTA_EQUIPOS ve "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = ve.id_tipo "
            "WHERE ve.nombre LIKE ? OR te.nombre LIKE ? OR ve.marca LIKE ? "
            "ORDER BY ve.nombre LIMIT 80",
            (f"%{texto}%", f"%{texto}%", f"%{texto}%"),
        )
        for r in rows:
            etiqueta = s(r[1])
            if str(r[0]) in self._nodos:
                etiqueta += "  ✓"
            self._ls_agregar.append([etiqueta, str(r[0])])

    def _on_busq_agregar_changed(self, entry):
        self._poblar_lista_agregar(entry.get_text())

    def _on_agregar_equipo_row_activated(self, tv, path, col):
        it = self._ls_agregar.get_iter(path)
        id_eq = self._ls_agregar.get_value(it, 1)
        self._agregar_equipo_por_busqueda(id_eq)

    def _on_panel_drag_data_get(self, widget, drag_context, data, info, time):
        sel = widget.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return
        id_eq = model.get_value(it, 1)
        data.set(self._TARGET_EQUIPO, 8, id_eq.encode("utf-8"))

    def _on_canvas_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        try:
            id_eq = data.get_data().decode("utf-8")
        except Exception:
            drag_context.finish(False, False, time)
            return
        if not id_eq:
            drag_context.finish(False, False, time)
            return
        wx, wy = self._s2w(x, y)
        self._agregar_equipo_por_busqueda(id_eq, wx, wy)
        drag_context.finish(True, False, time)

    def _on_toggle_panel_agregar(self, chk):
        visible = chk.get_active()
        self._revealer_agregar.set_reveal_child(visible)
        if visible:
            self._poblar_lista_agregar(self._e_busq_agregar.get_text())

    # ── coordinate helpers ──────────────────────────────────────────────────
    def _marcar_criticos(self, activo: bool):
        """Agrega (activo=True) o saca (activo=False) del conjunto de
        equipos críticos a todos los nodos actualmente seleccionados
        (self._sel_ids, poblado por el rectángulo de selección o por
        Shift/Ctrl+clic). No recalcula el riesgo solo — hay que usar
        '🔺 Recalcular riesgo' después, igual que tras cargar/editar
        problemas."""
        valid_ids = [eid for eid in self._sel_ids if eid in self._nodos]
        if not valid_ids:
            self._status("Seleccioná uno o más equipos primero "
                         "(rectángulo de selección, o Shift/Ctrl+clic).")
            return
        if activo:
            Modelo.marcar_equipos_criticos(valid_ids)
            verbo = "marcado(s) como crítico(s)"
        else:
            Modelo.desmarcar_equipos_criticos(valid_ids)
            verbo = "sacado(s) del conjunto de críticos"
        self._equipos_criticos = Modelo.devolver_ids_equipos_criticos()
        for eid in valid_ids:
            if eid in self._nodos:
                self._nodos[eid]["critico"] = eid in self._equipos_criticos
        self._status(
            f"{len(valid_ids)} equipo(s) {verbo}. "
            f"Total críticos ahora: {len(self._equipos_criticos)}. "
            f"Usá '🔺 Recalcular riesgo' para que se refleje en el score.")
        self._da.queue_draw()

    def _on_estilo_menu_toggled(self, item, key):
        """Handler de los Gtk.RadioMenuItem del submenú Ver → Estilo de
        conexión. Un RadioMenuItem dispara "toggled" tanto al activarse
        como al desactivarse (por el compañero de grupo recién elegido),
        por eso solo actuamos cuando el que llegó es el que quedó activo."""
        if not item.get_active():
            return
        self._estilo_conn = key
        # Line jumps no tiene efecto (ni se calcula) en curvas Bézier
        self._chk_jumps.set_sensitive(self._estilo_conn != "bezier")
        self._da.queue_draw()

    def _on_jumps_toggled(self, btn):
        self._line_jumps = btn.get_active()
        self._da.queue_draw()

    # ── line-jump geometry helpers ───────────────────────────────────────────

    def _on_toggle_solo_nombre(self, btn):
        self._solo_nombre = btn.get_active()
        # Recalculate node heights when toggling
        for nodo in self._nodos.values():
            if self._solo_nombre:
                nodo["alto"] = self.HDR_H
            else:
                n_rows = max(len(nodo["in"]), len(nodo["out"]), 1)
                nodo["alto"] = self.HDR_H + self.PORT_PAD*2 + n_rows * self.PORT_H
        self._da.queue_draw()

    def _recargar(self):
        self._cargar(self._id_inicio)

    def _status(self, txt):
        self._sb.push(self._sb.get_context_id("i"), txt)


# ── convenience ───────────────────────────────────────────────────────────────

def abrir_diagrama_conexiones(id_equipo=None, parent=None, iniciar_vacio=False):
    dlg = DiagramaConexiones(id_equipo=id_equipo, parent=parent, iniciar_vacio=iniciar_vacio)
    dlg.run(); dlg.destroy()



# ── Diálogo de cable rápido ───────────────────────────────────────────────────

class _DialogoCableRapido(Gtk.Dialog):
    """
    Popup que aparece al conectar dos puertos.
    Permite buscar un cable existente o crear uno nuevo escribiendo su código.
    """

    def __init__(self, puerto_a, nodo_a, puerto_b, nodo_b,
                 existentes, parent=None):
        titulo = (f"{nodo_a['nombre']} · {puerto_a['nombre']}  →  "
                  f"{nodo_b['nombre']} · {puerto_b['nombre']}")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(420, 320)
        self.id_cable_resultado = None

        ca = self.get_content_area()
        ca.set_spacing(6)
        ca.set_margin_start(12); ca.set_margin_end(12)
        ca.set_margin_top(8);    ca.set_margin_bottom(8)

        if existentes:
            lbl_ex = Gtk.Label(xalign=0)
            lbl_ex.set_markup(
                "<b>Conexiones existentes entre estos puertos:</b>")
            ca.pack_start(lbl_ex, False, False, 0)
            for ex in existentes:
                lbl = Gtk.Label(
                    label=f"  Cable #{ex[0]}: {s(ex[1])}", xalign=0)
                ca.pack_start(lbl, False, False, 0)
            ca.pack_start(Gtk.Separator(), False, False, 4)

        lbl_busq = Gtk.Label(xalign=0)
        lbl_busq.set_markup("<b>Buscar o crear cable:</b>")
        ca.pack_start(lbl_busq, False, False, 0)

        self._entry = Gtk.Entry(
            placeholder_text="código del cable…", activates_default=True)
        self._entry.connect("changed", self._on_changed)
        ca.pack_start(self._entry, False, False, 0)

        # Lista de resultados
        self._store = Gtk.ListStore(str, str)   # codigo, id_cable
        self._tv = Gtk.TreeView(model=self._store)
        self._tv.set_headers_visible(False)
        col = Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0)
        self._tv.append_column(col)
        self._tv.connect("row-activated", self._on_seleccionar)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(-1, 140)
        sw.add(self._tv)
        ca.pack_start(sw, True, True, 0)

        self._lbl_nuevo = Gtk.Label(xalign=0)
        self._lbl_nuevo.set_markup(
            "<small><i>Presioná Enter o hacé clic en "
            "\"Crear cable\" para crear uno nuevo con ese código.</i></small>")
        ca.pack_start(self._lbl_nuevo, False, False, 0)

        self.add_button("Cancelar",    Gtk.ResponseType.CANCEL)
        self._btn_crear = self.add_button("✚ Crear cable", Gtk.ResponseType.OK)
        self._btn_usar  = self.add_button("✔ Usar seleccionado", Gtk.ResponseType.OK)
        self._btn_usar.set_sensitive(False)
        self.set_default_response(Gtk.ResponseType.OK)

        self._btn_crear.connect("clicked",  self._on_crear)
        self._btn_usar.connect("clicked",   self._on_usar)

        self._buscar("")
        self.show_all()

    def _buscar(self, texto):
        self._store.clear()
        rows = Modelo.buscar_cables(texto)
        for r in rows:
            self._store.append([f"{s(r[1])}  [{s(r[2])}]", str(r[0])])
        self._tv.get_selection().unselect_all()
        self._btn_usar.set_sensitive(False)

    def _on_changed(self, entry):
        self._buscar(entry.get_text())

    def _on_seleccionar(self, tv, path, col):
        # Doble clic → usar directo
        it = self._store.get_iter(path)
        self.id_cable_resultado = int(self._store.get_value(it, 1))
        self.response(Gtk.ResponseType.OK)

    def _on_crear(self, btn):
        codigo = self._entry.get_text().strip()
        if not codigo:
            return
        self.id_cable_resultado = Modelo.agregar_cable_retorna_id(codigo)
        # Evitar que el response handler pise esto
        # (ya conectado al botón; response se llama en _crear_conexion)

    def _on_usar(self, btn):
        _, it = self._tv.get_selection().get_selected()
        if it:
            self.id_cable_resultado = int(self._store.get_value(it, 1))

