"""
impacto_ui.py — Mixin de UI para DiagramaConexiones
====================================================
Agrega "⚡ Analizar Impacto" a pantallas_avanzadas.py.

Selección de cable (tres modos, el usuario elige el que le resulte cómodo):
  1. Clic en un NODO  → diálogo con lista de cables salientes de ese equipo
  2. Botón "Buscar cable…" → diálogo con búsqueda por nombre/código
  3. Clic directo sobre una línea (modo legacy, tolerancia 10 px en coords mundo)

Integración en pantallas_avanzadas.py — 5 cambios (ya aplicados):
  Ver INSTRUCCIONES al pie de este módulo.
"""

import math
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from graph_impact import GraphImpactAnalyzer, ResultadoImpacto

try:
    from i18n import _
except ImportError:
    def _(t): return t


# ─────────────────────────────────────────────────────────────────────────────
# Paleta
# ─────────────────────────────────────────────────────────────────────────────
_C_NODO_SIN  = (0.85, 0.10, 0.10)
_C_NODO_OK   = (0.10, 0.68, 0.22)
_C_CAB_SIN   = (0.90, 0.22, 0.22)
_C_CAB_CORT  = (0.72, 0.10, 0.85)
_C_PAN_BG    = (0.10, 0.11, 0.16, 0.92)
_C_PAN_BRD   = (0.55, 0.12, 0.12, 0.95)
_C_TITULO    = (1.00, 0.33, 0.33, 1.00)
_C_TEXTO     = (0.91, 0.91, 0.91, 1.00)
_C_BTN_SALIR = (0.22, 0.48, 0.82, 1.00)


# ─────────────────────────────────────────────────────────────────────────────
# Diálogos de selección de cable
# ─────────────────────────────────────────────────────────────────────────────

def _dialogo_cables_nodo(parent, cables: list[dict]) -> "str | None":
    """
    Muestra los cables salientes de un nodo y devuelve el id_cable elegido,
    o None si el usuario cancela.
    """
    dlg = Gtk.Dialog(
        title="Seleccionar cable a desconectar",
        transient_for=parent,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
    )
    dlg.add_buttons(
        "Cancelar", Gtk.ResponseType.CANCEL,
        "Analizar", Gtk.ResponseType.OK,
    )
    dlg.set_default_size(480, 320)
    dlg.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(False)

    area = dlg.get_content_area()
    area.set_margin_top(10); area.set_margin_bottom(10)
    area.set_margin_start(12); area.set_margin_end(12)
    area.set_spacing(8)

    lbl = Gtk.Label(label=_("Cables salientes del equipo seleccionado:"))
    lbl.set_xalign(0)
    area.pack_start(lbl, False, False, 0)

    store = Gtk.ListStore(str, str, str)   # id_cable, nombre, destino
    for c in cables:
        store.append([c["id_cable"], c["nombre"], c["dst_nombre"]])

    tv = Gtk.TreeView(model=store)
    for i, title in enumerate(["Código", "Destino"]):
        col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i + 1)
        col.set_resizable(True)
        tv.append_column(col)

    sel = tv.get_selection()
    sel.set_mode(Gtk.SelectionMode.SINGLE)

    def on_sel_changed(_sel):
        dlg.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(
            sel.get_selected()[1] is not None
        )
    sel.connect("changed", on_sel_changed)
    tv.connect("row-activated", lambda *_: dlg.response(Gtk.ResponseType.OK))

    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_min_content_height(200)
    sw.add(tv)
    area.pack_start(sw, True, True, 0)

    dlg.show_all()
    resp = dlg.run()
    cable_id = None
    if resp == Gtk.ResponseType.OK:
        model, it = sel.get_selected()
        if it:
            cable_id = model[it][0]
    dlg.destroy()
    return cable_id


def _dialogo_buscar_cable(parent, cables: dict[str, str]) -> "str | None":
    """
    Diálogo de búsqueda libre por código/nombre de cable.
    `cables` = {id_cable: nombre}
    Devuelve id_cable o None.
    """
    dlg = Gtk.Dialog(
        title="Buscar cable por nombre",
        transient_for=parent,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
    )
    dlg.add_buttons(
        "Cancelar", Gtk.ResponseType.CANCEL,
        "Analizar", Gtk.ResponseType.OK,
    )
    dlg.set_default_size(420, 360)
    dlg.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(False)

    area = dlg.get_content_area()
    area.set_margin_top(10); area.set_margin_bottom(10)
    area.set_margin_start(12); area.set_margin_end(12)
    area.set_spacing(8)

    entry = Gtk.SearchEntry()
    entry.set_placeholder_text("Escribir código de cable (ej: VL0007, DL0012…)")
    area.pack_start(entry, False, False, 0)

    # ListStore: id_cable, nombre
    store_full = [(cid, nom) for cid, nom in sorted(cables.items(), key=lambda x: x[1])]
    store = Gtk.ListStore(str, str)
    for cid, nom in store_full:
        store.append([cid, nom])

    tv = Gtk.TreeView(model=store)
    col = Gtk.TreeViewColumn("Código de cable", Gtk.CellRendererText(), text=1)
    tv.append_column(col)

    sel = tv.get_selection()
    sel.set_mode(Gtk.SelectionMode.SINGLE)

    def on_sel_changed(_):
        dlg.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(
            sel.get_selected()[1] is not None
        )
    sel.connect("changed", on_sel_changed)
    tv.connect("row-activated", lambda *_: dlg.response(Gtk.ResponseType.OK))

    def on_search(e):
        txt = e.get_text().lower().strip()
        store.clear()
        for cid, nom in store_full:
            if txt in nom.lower() or txt in cid.lower():
                store.append([cid, nom])
        dlg.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(False)
    entry.connect("changed", on_search)

    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_min_content_height(220)
    sw.add(tv)
    area.pack_start(sw, True, True, 0)

    lbl = Gtk.Label()
    lbl.set_markup("<small><i>También puede hacer clic sobre un nodo del diagrama\n"
                   "para ver sus cables salientes.</i></small>")
    lbl.set_xalign(0)
    area.pack_start(lbl, False, False, 0)

    dlg.show_all()
    entry.grab_focus()
    resp = dlg.run()
    cable_id = None
    if resp == Gtk.ResponseType.OK:
        model, it = sel.get_selected()
        if it:
            cable_id = model[it][0]
    dlg.destroy()
    return cable_id


# ─────────────────────────────────────────────────────────────────────────────
# Mixin principal
# ─────────────────────────────────────────────────────────────────────────────

class ImpactoMixin:
    """
    Pegar en DiagramaConexiones via herencia múltiple:
        class DiagramaConexiones(ImpactoMixin, Gtk.Dialog):
    """

    # ── Init ─────────────────────────────────────────────────────────────────

    def _impacto_init(self, db_path: str) -> None:
        """Llamar al final de __init__, antes de show_all()."""
        self._imp_analyzer  = GraphImpactAnalyzer(db_path)
        self._imp_resultado: Optional[ResultadoImpacto] = None
        self._imp_senales_cache: list = []   # ver _imp_calcular_senales_perdidas
        # plan_estado_senal_y_linaje.md, Función 1: mismo cruce que
        # _imp_senales_cache pero por conector (id_conector -> info),
        # para que senal_diagrama_ui.py pueda tachar el puerto puntual
        # en vez de sólo listar nombres en el panel.
        self._imp_senales_cache_dict: dict = {}
        self._imp_modo      = False     # True = modo análisis activo
        self._imp_btn_rect  = None      # (x,y,w,h) botón "Salir" en pantalla

    # ── Botones de toolbar ───────────────────────────────────────────────────

    def _impacto_crear_items_menu(self) -> list[Gtk.Widget]:
        """
        Devuelve [btn_analizar, btn_buscar] como Gtk.MenuItem para agregar
        al submenú "Impacto" de la barra de menús.

        Ejemplo en __init__:
            for w in self._impacto_crear_items_menu():
                menu_impacto.append(w)
        """
        btn_analizar = Gtk.MenuItem(label=_("⚡ Analizar Impacto"))
        btn_analizar.set_tooltip_text(
            "Activa el modo análisis.\n"
            "Luego haga clic sobre un NODO para elegir uno de sus cables,\n"
            "o use '🔍 Buscar cable' para escribir el código directamente."
        )
        btn_analizar.connect("activate", self._imp_on_activar)

        btn_buscar = Gtk.MenuItem(label=_("🔍 Buscar cable…"))
        btn_buscar.set_tooltip_text(
            "Buscar un cable por nombre/código para analizar su impacto."
        )
        btn_buscar.connect("activate", self._imp_on_buscar_cable)

        return [btn_analizar, btn_buscar]

    # ── Handlers públicos ────────────────────────────────────────────────────

    def _imp_on_activar(self, _=None) -> None:
        """Activa el modo análisis (clic en botón ⚡)."""
        # Exclusión mutua con el Modo Escenario (ver escenario_ui.py) y con
        # "Diagnosticar falla" (ver diagnostico_ui.py): son modos de
        # clic-en-el-diagrama que compiten por el mismo gesto (seleccionar
        # un nodo para elegir cable, arrastre de selección, etc.).
        #
        # Con "Vista previa de imagen" YA NO se excluye (cambio a pedido
        # explícito del usuario, 2026-08-24 — antes de esto, activar
        # Impacto apagaba Vista Previa y viceversa, lo cual impedía ver el
        # placeholder de "señal caída" de Vista Previa mientras había un
        # Análisis de Impacto corriendo, que es exactamente el caso de uso
        # que motivó la Función 1 de plan_estado_senal_y_linaje.md). Mismo
        # criterio ya probado con Diagnóstico↔Vista Previa (2026-08-18):
        # Vista Previa nunca bloquea el resto del diagrama, así que pueden
        # convivir. Ambos SÍ consumen clic izquierdo sobre un puerto —
        # cuando los dos están activos a la vez, gana el que se chequea
        # primero en _on_press() (pantallas_avanzadas.py): hoy Vista Previa
        # se chequea antes que Impacto, así que un clic en un puerto abre
        # el diálogo de Vista Previa; para elegir el cable a analizar con
        # Impacto mientras tanto, usar "🔍 Buscar cable…" o clic directo
        # sobre la línea del cable (no sobre el puerto) — ambos siguen
        # andando igual, no dependen del clic en nodo/puerto.
        #
        # getattr() por las dudas: esta clase también se usa en otras
        # pantallas que no mezclan con esos otros mixins.
        if getattr(self, "_esc_modo", False):
            self._esc_desactivar_modo()
        if getattr(self, "_diag_modo", False):
            self._diag_desactivar()

        self._imp_asegurar_grafo()
        if not self._imp_analyzer.esta_construido():
            return

        self._imp_modo      = True
        self._imp_resultado = None
        self._da.queue_draw()

        win = self._da.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self._da.get_display(), "crosshair"))

    def _imp_on_buscar_cable(self, _=None) -> None:
        """Abre el diálogo de búsqueda libre por nombre de cable."""
        self._imp_asegurar_grafo()
        if not self._imp_analyzer.esta_construido():
            return
        cable_id = _dialogo_buscar_cable(
            self.get_toplevel(),
            self._imp_analyzer._cables,
        )
        if cable_id:
            self._imp_ejecutar(cable_id)

    def _imp_on_press(self, _da, event) -> bool:
        """
        Insertar AL INICIO de _on_press():
            if self._imp_on_press(da, event): return True
        """
        # Clic en botón "Salir" del panel lateral
        if self._imp_btn_rect and event.button == 1:
            bx, by, bw, bh = self._imp_btn_rect
            if bx <= event.x <= bx + bw and by <= event.y <= by + bh:
                self._imp_limpiar()
                return True

        if not self._imp_modo:
            return False

        if event.button == 1:
            wx, wy = self._s2w(event.x, event.y)

            # ── Prioridad 1: clic en un NODO → diálogo de cables salientes
            nodo_id = self._imp_nodo_bajo_cursor(wx, wy)
            if nodo_id is not None:
                cables_sal = self._imp_analyzer.cables_salientes_de(nodo_id)
                if not cables_sal:
                    self._imp_msg(
                        f"El equipo «{self._imp_analyzer.nombre_equipo(nodo_id)}»\n"
                        "no tiene cables salientes en el grafo."
                    )
                    return True
                cable_id = _dialogo_cables_nodo(self.get_toplevel(), cables_sal)
                if cable_id:
                    self._imp_ejecutar(cable_id)
                return True

            # ── Prioridad 2: clic sobre una línea de cable (fallback)
            cable_id = self._imp_cable_bajo_cursor(wx, wy)
            if cable_id is not None:
                self._imp_ejecutar(cable_id)
                return True

            # Clic en vacío — mantener modo activo con hint
            return True

        if event.button == 3:
            # Botón derecho cancela el modo
            self._imp_limpiar()
            return True

        return False

    def _imp_on_draw_overlay(self, cr, W: int, H: int) -> None:
        """
        Insertar AL FINAL de _on_draw(), después del cr.restore():
            self._imp_on_draw_overlay(cr, W, H)
        """
        if not self._imp_modo and self._imp_resultado is None:
            return

        if self._imp_modo and self._imp_resultado is None:
            self._imp_draw_hint(cr, W)
            return

        r = self._imp_resultado

        # Overlay en coords de mundo
        cr.save()
        cr.translate(self._pan_x, self._pan_y)
        cr.scale(self._zoom, self._zoom)

        # Cables
        for conn in self._conns:
            cid = conn["id"]
            src = self._nodos.get(conn["src_eq"])
            dst = self._nodos.get(conn["dst_eq"])
            if not src or not dst:
                continue
            if cid == r.cable_desconectado:
                rgb, lw = _C_CAB_CORT, 5.0
            elif cid in r.cables_impactados:
                rgb, lw = _C_CAB_SIN, 3.5
            else:
                continue
            x0 = src["x"] + src["ancho"]
            y0 = src["y"] + src["alto"] / 2
            x1 = dst["x"]
            y1 = dst["y"] + dst["alto"] / 2
            cr.set_source_rgba(*rgb, 0.88)
            cr.set_line_width(lw)
            cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
            if cid == r.cable_desconectado:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                self._imp_draw_cruz(cr, cx, cy, 12)

        # Nodos
        for eq_id, nodo in self._nodos.items():
            if eq_id in r.equipos_impactados:
                rgb, fill_a, stroke_a = _C_NODO_SIN, 0.22, 0.78
            elif eq_id in r.equipos_con_senal:
                rgb, fill_a, stroke_a = _C_NODO_OK, 0.15, 0.45
            else:
                continue
            x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
            cr.set_source_rgba(*rgb, fill_a)
            cr.rectangle(x, y, w, h); cr.fill()
            cr.set_source_rgba(*rgb, stroke_a)
            cr.set_line_width(3.5)
            cr.rectangle(x - 2, y - 2, w + 4, h + 4); cr.stroke()

        cr.restore()

        # Panel lateral (coords de pantalla)
        self._imp_draw_panel(cr, W, H, r)

    # ── Lógica interna ───────────────────────────────────────────────────────

    def _imp_asegurar_grafo(self) -> None:
        if self._imp_analyzer.esta_construido():
            return
        try:
            self._imp_analyzer.construir_grafo()
        except Exception as exc:
            self._imp_dlg_error(f"Error construyendo el grafo de señal:\n{exc}")

    def _imp_ejecutar(self, cable_id: str) -> None:
        try:
            r = self._imp_analyzer.simular_desconexion(cable_id)
        except Exception as exc:
            self._imp_dlg_error(f"Error en análisis:\n{exc}")
            return
        self._imp_resultado = r
        # Fase 6 de plan_entidad_senal.md: qué señales (por nombre) se
        # pierden con esta desconexión, no sólo IDs de equipo/cable.
        # Se calcula UNA vez acá (no en _imp_draw_panel, que corre en
        # cada repintado) y se cachea en el propio resultado.
        self._imp_senales_cache = self._imp_calcular_senales_perdidas(r)
        self._imp_modo      = False
        win = self._da.get_window()
        if win:
            win.set_cursor(None)
        self._da.queue_draw()

    def _imp_calcular_senales_perdidas(self, r: ResultadoImpacto) -> list:
        """Nombres de señal (distintos, ordenados) que hoy están cargadas
        — manual o propagada — en algún conector de los equipos afectados
        por esta desconexión. No vuelve a correr el motor de propagación,
        sólo lee lo que ya está guardado en senal_en_conector: es un
        cruce informativo, no un recálculo.

        A partir de plan_estado_senal_y_linaje.md (Función 1) delega en
        senal_estado.py — mismo cálculo de siempre, factorizado para que
        riesgo_diagrama_ui.py y escenario_ui.py lo reutilicen en vez de
        reimplementar la misma consulta cada uno. También deja poblado
        self._imp_senales_cache_dict (por conector) para el tachado del
        diagrama — ver senal_diagrama_ui.py.

        Bugfix 2026-08-24 (reporte visual sobre un caso real: el conector
        exacto que causó el corte, IN 3 BKGD A BNC de un DSK real, no
        aparecía tachado pese a que el panel de texto sí mencionaba la
        regla lógica rota): equipos_impactados NO incluye al equipo cuya
        PROPIA regla de salida se rompió (sigue "vivo", sólo deja de
        propagar hacia adelante), así que se suma
        r.conectores_regla_caida (la entrada culpable + la salida
        gobernada, calculado en graph_impact.py) y los dos extremos del
        cable recién cortado — ambos a nivel de CONECTOR puntual, no de
        equipo entero, para no arrastrar de paso otras entradas/salidas
        del mismo equipo que siguen con señal real."""
        try:
            from senal_estado import senales_caidas_por_equipos
            src_con, dst_con = self._imp_analyzer.conectores_del_cable(
                r.cable_desconectado)
            conectores_adicionales = set(r.conectores_regla_caida) | {src_con, dst_con}
            self._imp_senales_cache_dict = senales_caidas_por_equipos(
                self._imp_analyzer._db_path, r.equipos_impactados,
                conectores_adicionales=conectores_adicionales)
            return sorted({
                info["nombre_senal"] for info in self._imp_senales_cache_dict.values()
                if info["nombre_senal"]
            })
        except Exception:
            self._imp_senales_cache_dict = {}
            return []   # tablas de señal no existen todavía en esta BD

    def _imp_limpiar(self) -> None:
        self._imp_resultado = None
        self._imp_senales_cache = []
        self._imp_senales_cache_dict = {}
        self._imp_modo      = False
        self._imp_btn_rect  = None
        win = self._da.get_window()
        if win:
            win.set_cursor(None)
        self._da.queue_draw()

    def _imp_nodo_bajo_cursor(self, wx: float, wy: float) -> "str | None":
        """Devuelve el id del nodo que contiene el punto (wx, wy) en coords mundo."""
        for eq_id, nodo in self._nodos.items():
            x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
            if x <= wx <= x + w and y <= wy <= y + h:
                return eq_id
        return None

    def _imp_cable_bajo_cursor(self, wx: float, wy: float,
                                tol: float = 10.0) -> "str | None":
        mejor_id, mejor_d = None, tol
        for conn in self._conns:
            src = self._nodos.get(conn["src_eq"])
            dst = self._nodos.get(conn["dst_eq"])
            if not src or not dst:
                continue
            x0 = src["x"] + src["ancho"]; y0 = src["y"] + src["alto"] / 2
            x1 = dst["x"];                y1 = dst["y"] + dst["alto"] / 2
            d = self._imp_dist_seg(wx, wy, x0, y0, x1, y1)
            if d < mejor_d:
                mejor_d, mejor_id = d, conn["id"]
        return mejor_id

    @staticmethod
    def _imp_dist_seg(px, py, x1, y1, x2, y2) -> float:
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0,
            ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    # ── Dibujo Cairo ─────────────────────────────────────────────────────────

    @staticmethod
    def _imp_draw_hint(cr, W: int) -> None:
        cr.set_source_rgba(0.12, 0.12, 0.35, 0.88)
        cr.rectangle(0, 0, W, 42); cr.fill()
        cr.set_source_rgba(1.0, 1.0, 0.25, 1.0)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(13)
        cr.move_to(14, 20)
        cr.show_text("⚡ MODO ANÁLISIS  —  Clic en un NODO para elegir sus cables salientes")
        cr.move_to(14, 37)
        cr.set_font_size(11)
        cr.set_source_rgba(0.85, 0.85, 0.55, 1.0)
        cr.show_text("También puede hacer clic directo sobre un cable  ·  Botón derecho para cancelar")

    @staticmethod
    def _imp_draw_cruz(cr, cx, cy, s) -> None:
        cr.set_line_width(3.5)
        cr.move_to(cx - s, cy - s); cr.line_to(cx + s, cy + s); cr.stroke()
        cr.move_to(cx + s, cy - s); cr.line_to(cx - s, cy + s); cr.stroke()

    def _imp_draw_panel(self, cr, W: int, H: int, r: ResultadoImpacto) -> None:
        PW = 295; PH = min(H - 20, 620)
        px = W - PW - 10; py = 10

        cr.set_source_rgba(*_C_PAN_BG)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.fill()
        cr.set_source_rgba(*_C_PAN_BRD); cr.set_line_width(1.5)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.stroke()

        y = py + 28

        def txt(s, color=_C_TEXTO, bold=False, size=11):
            nonlocal y
            if y > py + PH - 100: return
            cr.set_source_rgba(*color)
            cr.select_font_face("Sans", 0, 1 if bold else 0)
            cr.set_font_size(size)
            cr.move_to(px + 14, y); cr.show_text(s)
            y += size + 5

        txt("⚡ ANÁLISIS DE IMPACTO", _C_TITULO, bold=True, size=13)
        cr.set_source_rgba(*_C_PAN_BRD); cr.set_line_width(1)
        cr.move_to(px + 8, y - 2); cr.line_to(px + PW - 8, y - 2); cr.stroke()
        y += 8

        txt("Cable desconectado:", bold=True)
        txt(f"  🔌 {r.nombre_cable}  (id {r.cable_desconectado})", (1.0, 0.55, 0.55, 1.0))
        y += 6

        n_eq  = len(r.equipos_impactados)
        n_cab = len(r.cables_impactados)

        if not r.hay_impacto:
            txt("✅  Sin impacto en la cadena", (0.25, 0.95, 0.40, 1.0), bold=True)
        else:
            # Orden deliberado (bugfix 2026-08-24, mismo reporte visual que
            # motivó el guard PH-100 de arriba): "Motivo" y "Señales
            # perdidas" van ANTES de las listas largas de equipos/cables.
            # Esas dos listas ya truncan a 14/8 con su propio "…y N más",
            # así que no pierden información aunque no entren enteras — en
            # cambio "Motivo"/"Señales" no tenían truncado propio y, con
            # un impacto grande (40+ equipos), el guard de espacio las
            # cortaba en seco sin avisar, silenciosamente. Poniéndolas
            # primero se garantiza que siempre se alcancen a dibujar.
            if r.causas_regla:
                txt("Motivo (regla lógica):", _C_TITULO, bold=True)
                for texto in list(r.causas_regla.values())[:4]:
                    txt(f"  ⚠ {texto}", (0.95, 0.75, 0.35, 1.0), size=10)
                if len(r.causas_regla) > 4:
                    txt(f"  … y {len(r.causas_regla) - 4} más", (0.65, 0.55, 0.30, 1.0), size=10)
                y += 6

            # Fase 6 de plan_entidad_senal.md: señales por NOMBRE que se
            # pierden, no sólo IDs de equipo — cacheado en _imp_ejecutar,
            # no se recalcula acá (esto corre en cada repintado).
            if self._imp_senales_cache:
                txt(f"📡 Señales perdidas:  {len(self._imp_senales_cache)}",
                    _C_TITULO, bold=True)
                for nombre in self._imp_senales_cache[:8]:
                    txt(f"  • {nombre}", (1.0, 0.75, 0.35, 1.0))
                if len(self._imp_senales_cache) > 8:
                    txt(f"  … y {len(self._imp_senales_cache) - 8} más",
                        (0.65, 0.55, 0.25, 1.0))
                y += 6

            txt(f"Equipos sin señal:  {n_eq}", _C_TITULO, bold=True)
            for eid in sorted(r.equipos_impactados,
                               key=lambda x: self._imp_analyzer.nombre_equipo(x))[:14]:
                txt(f"  • {self._imp_analyzer.nombre_equipo(eid)}", (0.95, 0.65, 0.65, 1.0))
            if n_eq > 14:
                txt(f"  … y {n_eq - 14} más", (0.65, 0.45, 0.45, 1.0))
            y += 6
            txt(f"Cables sin señal:  {n_cab}", _C_TITULO, bold=True)
            for cid in sorted(r.cables_impactados,
                               key=lambda x: self._imp_analyzer.nombre_cable(x))[:8]:
                txt(f"  • {self._imp_analyzer.nombre_cable(cid)}", (0.95, 0.65, 0.65, 1.0))
            if n_cab > 8:
                txt(f"  … y {n_cab - 8} más", (0.65, 0.45, 0.45, 1.0))

        # Leyenda — se ubica DESPUÉS de donde terminó el contenido dinámico
        # (equipos/cables/causas/señales, todo eso hecho con txt()), no en
        # una posición fija desde abajo: con causas_regla + señales
        # perdidas (agregadas después del diseño original de este panel)
        # el contenido puede llegar a superponerse con una posición fija
        # (bugfix 2026-08-24: reportado con captura real mostrando el
        # texto "regla AND…" superpuesto a la leyenda). Si el contenido
        # terminó temprano, se usa igual la posición de siempre
        # (py+PH-92) para que la leyenda no quede pegada al contenido
        # corto con un hueco raro antes del botón Salir.
        y = max(y + 14, py + PH - 92)
        for rgb, label in [
            (_C_CAB_CORT, "Cable desconectado"),
            (_C_NODO_SIN, "Equipo / cable sin señal"),
            (_C_NODO_OK,  "Equipo con señal"),
        ]:
            cr.set_source_rgb(*rgb)
            cr.rectangle(px + 14, y - 10, 14, 12); cr.fill()
            cr.set_source_rgba(*_C_TEXTO)
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(10)
            cr.move_to(px + 32, y); cr.show_text(label)
            y += 16

        # Botón Salir
        BW, BH = PW - 28, 28
        bx = px + 14; by2 = py + PH - BH - 8
        self._imp_btn_rect = (bx, by2, BW, BH)
        cr.set_source_rgba(*_C_BTN_SALIR)
        self._imp_rrect(cr, bx, by2, BW, BH, 6); cr.fill()
        cr.set_source_rgba(1, 1, 1, 1)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(12)
        cr.move_to(bx + BW / 2 - 60, by2 + 19)
        cr.show_text("✕  Salir del análisis")

    @staticmethod
    def _imp_rrect(cr, x, y, w, h, r) -> None:
        cr.new_sub_path()
        cr.arc(x + r,     y + r,     r, math.pi,         3 * math.pi / 2)
        cr.arc(x + w - r, y + r,     r, 3 * math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0,               math.pi / 2)
        cr.arc(x + r,     y + h - r, r, math.pi / 2,     math.pi)
        cr.close_path()

    # ── Helpers de diálogo GTK ───────────────────────────────────────────────

    def _imp_dlg_error(self, msg: str) -> None:
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), flags=0,
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK, text=msg)
        dlg.run(); dlg.destroy()

    def _imp_msg(self, msg: str) -> None:
        dlg = Gtk.MessageDialog(transient_for=self.get_toplevel(), flags=0,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text=msg)
        dlg.run(); dlg.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# ImpactoResultadoDialog — plan_simular_remocion_cadena.md
# ─────────────────────────────────────────────────────────────────────────────
#
# Diálogo liviano (sin canvas Cairo) para mostrar un ResultadoImpacto /
# ResultadoImpactoEquipo desde los diálogos de detalle de Cable, Equipo,
# Rack y Conexión en cabledoc.py — ninguno de esos tiene el DiagramaConexiones
# de fondo, así que no puede usarse el overlay de ImpactoMixin (necesita
# self._nodos/self._conns/self._da del canvas). Reutiliza la misma lógica de
# texto que _imp_draw_panel, sin Cairo — y el mismo cruce de señales caídas
# de senal_estado.py (Función 1) que ya usa el resto del panel de impacto.

class ImpactoResultadoDialog(Gtk.Dialog):
    """
    Uso:
        dlg = ImpactoResultadoDialog(resultado, analyzer, titulo="Cable VL0007",
                                     parent=self)
        dlg.run(); dlg.destroy()

    `resultado` es cualquiera de ResultadoImpacto / ResultadoImpactoEquipo
    (ambos tienen equipos_impactados, causas_regla y hay_impacto; sólo
    ResultadoImpacto trae cables_impactados directamente en el objeto —
    para ResultadoImpactoEquipo ese campo se agregó en graph_impact.py
    junto con este plan, así que también está disponible).
    `analyzer` es el GraphImpactAnalyzer ya construido, para resolver
    nombres de equipo/cable (nombre_equipo()/nombre_cable()).
    """

    def __init__(self, resultado, analyzer, titulo: str, parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons("Cerrar", Gtk.ResponseType.CLOSE)
        self.set_default_size(460, 460)

        area = self.get_content_area()
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(10);   area.set_margin_bottom(10)
        area.set_spacing(6)

        if not resultado.hay_impacto:
            lbl = Gtk.Label(
                label=_("✅ Sin impacto en la cadena: nada queda sin señal."))
            lbl.set_line_wrap(True); lbl.set_xalign(0)
            area.pack_start(lbl, False, False, 0)
            self.show_all()
            return

        equipos_impactados = resultado.equipos_impactados
        cables_impactados = getattr(resultado, "cables_impactados", set())

        lbl_eq = Gtk.Label(
            label=f"{len(equipos_impactados)} equipo(s) quedan sin señal:")
        lbl_eq.set_xalign(0); lbl_eq.set_line_wrap(True)
        area.pack_start(lbl_eq, False, False, 0)

        causas_regla = getattr(resultado, "causas_regla", {})
        if causas_regla:
            lbl_causa = Gtk.Label()
            lbl_causa.set_markup(
                "<span foreground='#d4a017' size='small'>⚠ "
                + "\n⚠ ".join(GLib.markup_escape_text(t)
                              for t in causas_regla.values())
                + "</span>")
            lbl_causa.set_xalign(0); lbl_causa.set_line_wrap(True)
            area.pack_start(lbl_causa, False, False, 4)

        store_eq = Gtk.ListStore(str)
        for eq_id in sorted(equipos_impactados,
                             key=lambda x: analyzer.nombre_equipo(x)):
            store_eq.append([analyzer.nombre_equipo(eq_id)])
        tv_eq = Gtk.TreeView(model=store_eq, headers_visible=False)
        tv_eq.append_column(Gtk.TreeViewColumn(
            "", Gtk.CellRendererText(xpad=4), text=0))
        sw_eq = Gtk.ScrolledWindow()
        sw_eq.set_vexpand(True)
        sw_eq.add(tv_eq)
        area.pack_start(sw_eq, True, True, 4)

        if cables_impactados:
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            area.pack_start(sep, False, False, 2)
            lbl_cab = Gtk.Label(
                label=f"🔌 {len(cables_impactados)} cable(s) quedan sin señal:")
            lbl_cab.set_xalign(0)
            area.pack_start(lbl_cab, False, False, 0)
            store_cab = Gtk.ListStore(str)
            for cid in sorted(cables_impactados,
                               key=lambda x: analyzer.nombre_cable(x)):
                store_cab.append([analyzer.nombre_cable(cid)])
            tv_cab = Gtk.TreeView(model=store_cab, headers_visible=False)
            tv_cab.append_column(Gtk.TreeViewColumn(
                "", Gtk.CellRendererText(xpad=4), text=0))
            sw_cab = Gtk.ScrolledWindow()
            sw_cab.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw_cab.set_min_content_height(min(24 * len(cables_impactados) + 4, 110))
            sw_cab.add(tv_cab)
            area.pack_start(sw_cab, False, False, 0)

        # plan_estado_senal_y_linaje.md, Función 1: qué NOMBRES de señal
        # (no sólo equipos/cables) se pierden — mismo cruce que usa el
        # resto de la app.
        #
        # Bugfix 2026-08-24 (mismo criterio ya validado en el overlay del
        # diagrama): equipos_impactados no incluye ni al equipo que falló
        # directamente (equipo_id, sólo existe en ResultadoImpactoEquipo)
        # ni a los equipos con su propia regla lógica rota — se suman
        # aparte, el primero como equipo completo (equipos_adicionales,
        # correcto: un equipo caído del todo pierde todos sus
        # conectores) y el resto como conectores puntuales
        # (conectores_regla_caida + extremos del cable cortado), para no
        # tachar de más otras entradas/salidas del mismo equipo que
        # siguen con señal real.
        try:
            from senal_estado import nombres_senal_caidos
            equipos_adicionales = set()
            id_equipo_fallado = getattr(resultado, "equipo_id", None)
            if id_equipo_fallado:
                equipos_adicionales.add(str(id_equipo_fallado))
            conectores_adicionales = set(getattr(resultado, "conectores_regla_caida", ()))
            cable_desconectado = getattr(resultado, "cable_desconectado", None)
            if cable_desconectado:
                src_con, dst_con = analyzer.conectores_del_cable(cable_desconectado)
                conectores_adicionales |= {src_con, dst_con}
            senales = nombres_senal_caidos(
                analyzer._db_path, equipos_impactados,
                equipos_adicionales=equipos_adicionales,
                conectores_adicionales=conectores_adicionales)
        except Exception:
            senales = []
        if senales:
            sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            area.pack_start(sep2, False, False, 2)
            lbl_sen = Gtk.Label(label=f"📡 {len(senales)} señal(es) se pierden:")
            lbl_sen.set_xalign(0)
            area.pack_start(lbl_sen, False, False, 0)
            store_sen = Gtk.ListStore(str)
            for nombre in senales:
                store_sen.append([nombre])
            tv_sen = Gtk.TreeView(model=store_sen, headers_visible=False)
            tv_sen.append_column(Gtk.TreeViewColumn(
                "", Gtk.CellRendererText(xpad=4), text=0))
            sw_sen = Gtk.ScrolledWindow()
            sw_sen.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw_sen.set_min_content_height(min(24 * len(senales) + 4, 110))
            sw_sen.add(tv_sen)
            area.pack_start(sw_sen, False, False, 0)

        self.show_all()


def simular_remocion_y_mostrar(parent, db_path: str, titulo: str,
                                metodo: str, *args) -> None:
    """
    Punto de entrada único para los botones "⚡ Simular remoción" de
    cabledoc.py (Cable/Equipo/Rack/Conexión) — construye el analyzer,
    llama al método pedido de GraphImpactAnalyzer con *args, y muestra el
    resultado en ImpactoResultadoDialog. Encapsula acá el manejo de
    errores para no repetirlo 4 veces en cabledoc.py.

    metodo: "simular_desconexion" | "simular_falla_equipo" |
            "simular_perdida_rack" | "simular_perdida_conexion"
    """
    try:
        analyzer = GraphImpactAnalyzer(db_path)
        analyzer.construir_grafo()
        resultado = getattr(analyzer, metodo)(*args)
    except Exception as exc:
        dlg = Gtk.MessageDialog(
            transient_for=parent, flags=0,
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
            text=f"No se pudo simular la remoción:\n{exc}")
        dlg.run(); dlg.destroy()
        return

    dlg = ImpactoResultadoDialog(resultado, analyzer, titulo=titulo, parent=parent)
    dlg.run()
    dlg.destroy()


# Importación tardía para que funcione el type hint
from typing import Optional
