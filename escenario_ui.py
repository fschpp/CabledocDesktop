"""
escenario_ui.py — Mixin de UI del "Modo Escenario" para DiagramaConexiones
===========================================================================
Agrega al diagrama de conexiones la posibilidad de armar un escenario
combinado — fallas de equipo + desconexiones de cable + reconexiones
virtuales de emergencia — y verlo evaluado en vivo con
GraphImpactAnalyzer.simular_escenario() (ver escenario_engine.py), sin
tocar la infraestructura real hasta confirmar "▶ Aplicar…".

Ver CableDoc_Plan_Escenarios_Diagrama.md para el diseño completo. Sigue el
mismo patrón de mixin por herencia múltiple que impacto_ui.ImpactoMixin /
riesgo_diagrama_ui.RiesgoDiagramaMixin, y reutiliza varios de sus helpers
(_imp_nodo_bajo_cursor, _imp_cable_bajo_cursor, _imp_draw_cruz, _imp_rrect)
en vez de reescribirlos.

Integración en pantallas_avanzadas.py (ya aplicada):
  1. class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin,
                               SenalDiagramaMixin, EscenarioMixin, Gtk.Dialog)
  2. self._esc_init(DB_PATH)                    — junto a los otros _*_init
  3. for w in self._esc_crear_items_menu(): menu_escenario.append(w)
     (los ítems se agregan al submenú "Escenario" de la barra de menús)
  4. En _on_press(): if self._esc_on_press(da, event): return True
     (ANTES que self._imp_on_press, ver _esc_activar_modo → exclusión mutua)
  5. En _on_motion(): if self._esc_on_motion(da, event): return
  6. En _on_release(): if self._esc_on_release(da, event): return
  7. En _on_draw(), después de self._imp_on_draw_overlay(cr, W, H):
       self._esc_on_draw_overlay(cr, W, H)

Modos mutuamente excluyentes con Analizar Impacto (sección 5 del plan):
activar el modo escenario apaga el modo/resultado de impacto si estaba
activo, y viceversa (ver el pequeño parche simétrico en
impacto_ui.ImpactoMixin._imp_on_activar).
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from modelo import Modelo
from escenario_engine import Escenario, CambioPendiente

try:
    from i18n import _
except ImportError:
    def _(t): return t


# ─────────────────────────────────────────────────────────────────────────────
# Paleta (deliberadamente distinta de la de impacto_ui, para no confundir
# "esto ya pasó" (impacto) con "esto es hipotético" (escenario))
# ─────────────────────────────────────────────────────────────────────────────
_C_FALLADO      = (0.80, 0.15, 0.55)   # magenta — equipo marcado como fallado
_C_IMPACTADO    = (0.85, 0.10, 0.10)   # rojo — consecuencia (queda sin señal)
_C_RECUPERADO   = (0.15, 0.75, 0.30)   # verde — salvado por una reconexión virtual
_C_CORTADO      = (0.55, 0.20, 0.20)   # rojo apagado — cable cortado del escenario
_C_VIRTUAL      = (0.95, 0.80, 0.15)   # amarillo — conexión virtual propuesta
_C_PAN_BG       = (0.11, 0.10, 0.16, 0.92)
_C_PAN_BRD      = (0.55, 0.35, 0.10, 0.95)
_C_TITULO       = (0.98, 0.75, 0.25, 1.00)
_C_TEXTO        = (0.91, 0.91, 0.91, 1.00)

# Familias de tipo_conector consideradas compatibles entre sí para una
# reconexión virtual (ver _esc_tipos_compatibles). El resto de las
# combinaciones no se bloquean —sólo se avisa—, porque puede haber casos
# legítimos que no anticipamos (adaptadores, etc.).
_FAM_ENTRADA = {"IN", "REFIN"}
_FAM_SALIDA  = {"OUT", "REFOUT"}


class EscenarioMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple."""

    # ── Init ─────────────────────────────────────────────────────────────────
    def _esc_init(self, db_path: str) -> None:
        """Llamar al final de __init__, junto a los otros _*_init(...)."""
        self._esc_db_path        = db_path
        self._esc_actual: "Escenario | None" = None
        self._esc_resultado                 = None   # ResultadoEscenario | None
        self._esc_modo                      = False  # True = modo edición activo
        self._esc_reconectar_activo         = False  # sub-modo: arrastrar puerto→puerto
        self._esc_wire_from                 = None   # (id_conector, lado, id_nodo) | None
        self._esc_wire_mx = self._esc_wire_my = 0.0
        # plan_estado_senal_y_linaje.md, Función 1: mismo cruce por
        # conector que impacto_ui/riesgo_diagrama_ui, recalculado cada vez
        # que se recalcula el escenario (_esc_recalcular). Se lee desde
        # senal_diagrama_ui.py para tachar el puerto.
        self._esc_senales_cache_dict = {}

    # ── Ítems de menú ───────────────────────────────────────────────────────
    def _esc_crear_items_menu(self) -> list:
        """Devuelve los ítems (con separadores) para el submenú "Escenario"
        de la barra de menús, agrupados por sub-función: gestión del
        escenario, modos de edición interactiva, y persistencia/aplicación."""
        btn_nuevo = Gtk.MenuItem(label=_("🆕 Escenario nuevo"))
        btn_nuevo.set_tooltip_text(
            "Crea un escenario nuevo: podés marcar equipos que fallan, "
            "cortar cables y proponer reconexiones de emergencia, y ver en "
            "vivo qué queda sin señal — sin tocar nada real hasta que lo "
            "confirmes."
        )
        btn_nuevo.connect("activate", self._esc_on_nuevo)

        btn_abrir = Gtk.MenuItem(label=_("📂 Abrir escenario…"))
        btn_abrir.set_tooltip_text("Abrir un escenario guardado anteriormente.")
        btn_abrir.connect("activate", self._esc_on_abrir)

        self._esc_btn_modo = Gtk.CheckMenuItem(label=_("🧪 Modo escenario"))
        self._esc_btn_modo.set_tooltip_text(
            "Con el modo activo: clic en un EQUIPO lo marca como fallado, "
            "clic en un CABLE lo marca como cortado. Clic de nuevo para "
            "des-marcar. Botón derecho o desactivar este botón para salir."
        )
        self._esc_btn_modo.connect("toggled", self._esc_on_toggle_modo)

        self._esc_btn_reconectar = Gtk.CheckMenuItem(label=_("🔗 Reconexión"))
        self._esc_btn_reconectar.set_tooltip_text(
            "Arrastrá de un puerto a otro para proponer una conexión "
            "virtual de emergencia (no toca nada real todavía)."
        )
        self._esc_btn_reconectar.connect("toggled", self._esc_on_toggle_reconectar)

        btn_guardar = Gtk.MenuItem(label=_("💾 Guardar"))
        btn_guardar.set_tooltip_text("Guarda el escenario actual con un nombre.")
        btn_guardar.connect("activate", self._esc_on_guardar)

        btn_aplicar = Gtk.MenuItem(label=_("▶ Aplicar…"))
        btn_aplicar.set_tooltip_text(
            "Aplica de verdad las desconexiones de cable y reconexiones "
            "virtuales del escenario a la infraestructura (pide "
            "confirmación antes). Las fallas de equipo son sólo para la "
            "simulación, no se aplican."
        )
        btn_aplicar.connect("activate", self._esc_on_aplicar)

        btn_descartar = Gtk.MenuItem(label=_("🗑 Descartar todo"))
        btn_descartar.set_tooltip_text(
            "Quita todos los cambios del escenario actual (no borra el "
            "escenario guardado, sólo lo vacía).")
        btn_descartar.connect("activate", self._esc_on_descartar)

        return [btn_nuevo, btn_abrir,
                Gtk.SeparatorMenuItem(),
                self._esc_btn_modo, self._esc_btn_reconectar,
                Gtk.SeparatorMenuItem(),
                btn_guardar, btn_aplicar, btn_descartar]

    # ── Activar / desactivar modo ────────────────────────────────────────────
    def _esc_on_toggle_modo(self, btn) -> None:
        if btn.get_active():
            self._esc_activar_modo()
        else:
            self._esc_desactivar_modo()

    def _esc_on_toggle_reconectar(self, btn) -> None:
        self._esc_reconectar_activo = btn.get_active()
        self._esc_wire_from = None
        if self._esc_reconectar_activo and not self._esc_modo:
            self._esc_activar_modo()
        self._da.queue_draw()

    def _esc_activar_modo(self) -> None:
        # Exclusión mutua con "Analizar Impacto" (sección 5 del plan) y con
        # "Diagnosticar falla" (diagnostico_ui.py): compiten por el mismo
        # gesto de clic-en-el-diagrama (selección de nodo, arrastre).
        #
        # Con "Vista previa de imagen" YA NO se excluye (mismo cambio y
        # mismo motivo que impacto_ui._imp_on_activar, ver ese comentario
        # para el detalle completo — a pedido explícito del usuario,
        # 2026-08-24). Caveat propio de Escenario que no aplica a Impacto:
        # el sub-modo "🔌 Reconectar virtualmente" (_esc_reconectar_activo)
        # arma una conexión virtual arrastrando de un puerto a otro — con
        # Vista Previa también activo, el PRIMER clic de ese arrastre cae
        # en el orden de _on_press() antes que acá (ver comentario en
        # impacto_ui.py), así que puede abrir el diálogo de Vista Previa
        # en vez de arrancar la conexión virtual. Si esto molesta en el uso
        # real, apagar Vista Previa mientras se arma una reconexión virtual
        # puntual es el workaround hasta que se revise el orden de
        # prioridad de clics entre estos modos.
        if getattr(self, "_imp_modo", False) or getattr(self, "_imp_resultado", None) is not None:
            self._imp_limpiar()
        if getattr(self, "_diag_modo", False):
            self._diag_desactivar()

        if self._esc_actual is None:
            self._esc_actual = Escenario(self._esc_db_path)  # en memoria, sin guardar
        if not self._esc_actual.asegurar_grafo():
            self._esc_msg("No se pudo construir el grafo de señal — "
                          "revisá que graphqlite esté disponible.")
            return
        self._esc_recalcular()
        self._esc_modo = True
        if hasattr(self, "_esc_btn_modo") and not self._esc_btn_modo.get_active():
            self._esc_btn_modo.set_active(True)
        win = self._da.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self._da.get_display(), "crosshair"))
        self._da.queue_draw()

    def _esc_desactivar_modo(self) -> None:
        self._esc_modo = False
        self._esc_reconectar_activo = False
        self._esc_wire_from = None
        if hasattr(self, "_esc_btn_modo") and self._esc_btn_modo.get_active():
            self._esc_btn_modo.set_active(False)
        if hasattr(self, "_esc_btn_reconectar") and self._esc_btn_reconectar.get_active():
            self._esc_btn_reconectar.set_active(False)
        win = self._da.get_window()
        if win:
            win.set_cursor(None)
        self._da.queue_draw()

    # ── Botones de acción (nuevo / abrir / guardar / aplicar / descartar) ───
    def _esc_on_nuevo(self, _btn=None) -> None:
        if (self._esc_actual and self._esc_actual.cambios
                and self._esc_actual.id_escenario is None):
            if not self._esc_confirmar(
                    "Hay cambios sin guardar en el escenario actual — "
                    "¿descartarlos y empezar uno nuevo?"):
                return
        resp = _dialogo_nombre_escenario(self.get_toplevel())
        if resp is None:
            return
        nombre, descripcion = resp
        self._esc_actual = Escenario.crear_nuevo(self._esc_db_path, nombre, descripcion)
        self._esc_resultado = None
        self._esc_senales_cache_dict = {}
        self._esc_activar_modo()

    def _esc_on_abrir(self, _btn=None) -> None:
        id_esc = _dialogo_listado_escenarios(self.get_toplevel())
        if id_esc is None:
            return
        self._esc_actual = Escenario(self._esc_db_path, id_escenario=id_esc)
        self._esc_activar_modo()

    def _esc_on_guardar(self, _btn=None) -> None:
        esc = self._esc_actual
        if esc is None or not esc.cambios:
            self._esc_msg("Activá el modo escenario y marcá al menos un "
                          "cambio antes de guardar.")
            return
        if esc.id_escenario is not None:
            self._esc_msg(f"Ya está guardado como «{esc.nombre}» — los "
                          "cambios se guardan solos a medida que los hacés.")
            return
        resp = _dialogo_nombre_escenario(self.get_toplevel())
        if resp is None:
            return
        nombre, descripcion = resp
        esc.guardar_como(nombre, descripcion)
        self._esc_msg(f"Escenario «{nombre}» guardado.")

    def _esc_on_descartar(self, _btn=None) -> None:
        esc = self._esc_actual
        if not esc or not esc.cambios:
            return
        if not self._esc_confirmar("¿Descartar todos los cambios de este escenario?"):
            return
        esc.vaciar()
        self._esc_resultado = None
        self._esc_senales_cache_dict = {}
        self._da.queue_draw()

    def _esc_on_aplicar(self, _btn=None) -> None:
        esc = self._esc_actual
        if not esc or not esc.cambios:
            self._esc_msg("No hay cambios en el escenario actual para aplicar.")
            return
        resumen = esc.resumen_aplicar()
        if not resumen["cables_a_desconectar"] and not resumen["reconexiones"]:
            self._esc_msg(
                "Este escenario sólo tiene fallas de equipo simuladas, que "
                "no tienen una operación real equivalente — no hay nada "
                "para aplicar a la infraestructura."
            )
            return
        if not self._esc_confirmar_aplicar(resumen):
            return
        try:
            resultado = esc.aplicar_a_infraestructura()
        except Exception as exc:
            self._esc_msg(f"Error al aplicar los cambios:\n{exc}")
            return

        # La infraestructura real cambió: invalidar todo lo que la cachea.
        if hasattr(self, "_imp_analyzer"):
            self._imp_analyzer.invalidar()
        self._esc_desactivar_modo()
        self._esc_resultado = None
        self._esc_senales_cache_dict = {}
        self._recargar()
        self._esc_msg(
            f"Aplicado: {len(resultado['cables_desconectados'])} cable(s) "
            f"desconectado(s), {len(resultado['cables_creados'])} cable(s) "
            "nuevo(s) creado(s)."
        )

    # ── Edición por clic (equipo / cable) ────────────────────────────────────
    def _esc_on_press(self, _da, event) -> bool:
        """Insertar AL INICIO de _on_press(), ANTES de _imp_on_press:
            if self._esc_on_press(da, event): return True
        """
        if not self._esc_modo:
            return False

        wx, wy = self._s2w(event.x, event.y)

        if self._esc_reconectar_activo:
            return self._esc_on_press_reconexion(wx, wy, event)

        if event.button == 1:
            nodo_id = self._imp_nodo_bajo_cursor(wx, wy)
            if nodo_id is not None:
                self._esc_toggle_falla_equipo(nodo_id)
                return True
            cable_id = self._imp_cable_bajo_cursor(wx, wy)
            if cable_id is not None:
                self._esc_toggle_desconexion_cable(cable_id)
                return True
            return True  # clic en vacío: mantener el modo activo

        if event.button == 3:
            self._esc_desactivar_modo()
            return True

        return False

    def _esc_on_press_reconexion(self, wx, wy, event) -> bool:
        if event.button != 1:
            return True
        hit = self._esc_puerto_bajo_cursor(wx, wy)
        if hit:
            cid, lado, nodo_id = hit
            self._esc_wire_from = (cid, lado, nodo_id)
            self._esc_wire_mx, self._esc_wire_my = wx, wy
            self._da.queue_draw()
        return True

    def _esc_on_motion(self, _da, event) -> bool:
        """Insertar AL INICIO de _on_motion():
            if self._esc_on_motion(da, event): return
        """
        if not self._esc_reconectar_activo or not self._esc_wire_from:
            return False
        self._esc_wire_mx, self._esc_wire_my = self._s2w(event.x, event.y)
        self._da.queue_draw()
        return True

    def _esc_on_release(self, _da, event) -> bool:
        """Insertar AL INICIO de _on_release():
            if self._esc_on_release(da, event): return
        """
        if not self._esc_reconectar_activo or not self._esc_wire_from:
            return False
        wx, wy = self._s2w(event.x, event.y)
        origen_cid, _origen_lado, _origen_nodo = self._esc_wire_from
        self._esc_wire_from = None
        hit = self._esc_puerto_bajo_cursor(wx, wy)
        if hit:
            destino_cid, _destino_lado, _destino_nodo = hit
            if str(destino_cid) != str(origen_cid):
                self._esc_agregar_conexion_virtual(origen_cid, destino_cid)
        self._da.queue_draw()
        return True

    def _esc_toggle_falla_equipo(self, id_equipo: str) -> None:
        esc = self._esc_actual
        existente = esc.cambio_en_equipo(id_equipo)
        if existente:
            esc.quitar_cambio(existente)
        else:
            esc.agregar_falla_equipo(id_equipo)
        self._esc_recalcular()

    def _esc_toggle_desconexion_cable(self, id_cable: str) -> None:
        esc = self._esc_actual
        existente = esc.cambio_en_cable(id_cable)
        if existente:
            esc.quitar_cambio(existente)
        else:
            esc.agregar_desconexion_cable(id_cable)
        self._esc_recalcular()

    def _esc_agregar_conexion_virtual(self, id_a: str, id_b: str) -> None:
        esc = self._esc_actual
        analyzer = esc.analyzer
        tipo_a = analyzer._conector_tipo.get(str(id_a), "") if analyzer.esta_construido() else ""
        tipo_b = analyzer._conector_tipo.get(str(id_b), "") if analyzer.esta_construido() else ""
        esc.agregar_conexion_virtual(id_a, id_b)
        self._esc_recalcular()
        if tipo_a and tipo_b and not _esc_tipos_compatibles(tipo_a, tipo_b):
            self._esc_msg(
                f"Aviso: conector tipo «{tipo_a}» → «{tipo_b}» no es la "
                "combinación esperada (entrada↔salida). Se agregó igual — "
                "revisá la compatibilidad física antes de aplicar."
            )

    def _esc_puerto_bajo_cursor(self, wx: float, wy: float, tol: float = 8.0):
        """(id_conector, 'in'|'out', id_nodo) bajo el punto (wx,wy) en
        coords mundo, o None. Mismo criterio geométrico que
        _senal_puerto_bajo_cursor / _port_pos, pero devuelve además el
        lado y el nodo (necesarios para armar la conexión virtual)."""
        if getattr(self, "_solo_nombre", False):
            return None  # en modo compacto no hay puertos dibujados
        r_mundo = self.PORT_R + tol
        for nodo in self._nodos.values():
            for cid, _cnm, _t in nodo.get("in", []):
                px, py = self._port_pos(nodo, cid, "in")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r_mundo ** 2:
                    return cid, "in", nodo["id"]
            for cid, _cnm, _t in nodo.get("out", []):
                px, py = self._port_pos(nodo, cid, "out")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r_mundo ** 2:
                    return cid, "out", nodo["id"]
        return None

    def _esc_puerto_pos_por_id(self, id_conector: str):
        id_conector = str(id_conector)
        for nodo in self._nodos.values():
            for cid, _cnm, _t in nodo.get("in", []):
                if cid == id_conector:
                    return self._port_pos(nodo, cid, "in")
            for cid, _cnm, _t in nodo.get("out", []):
                if cid == id_conector:
                    return self._port_pos(nodo, cid, "out")
        return None

    def _esc_recalcular(self) -> None:
        esc = self._esc_actual
        if esc is None:
            self._esc_resultado = None
            self._esc_senales_cache_dict = {}
        else:
            self._esc_resultado = esc.evaluar()
            self._esc_senales_cache_dict = self._esc_senales_caidas()
        self._da.queue_draw()

    def _esc_senales_caidas(self) -> dict:
        """plan_estado_senal_y_linaje.md, Función 1: nombres de señal (por
        conector) que quedan huérfanos con el escenario "después" ya
        aplicado (equipos_impactados incluye tanto los fallados
        directamente como los que se caen en cascada por regla lógica).
        Reusa el mismo helper que impacto_ui.py/riesgo_diagrama_ui.py.

        Bugfix 2026-08-24: equipos_impactados NO incluye a los equipos
        que fallaron DIRECTAMENTE (r.equipos_fallados) ni a los que
        tienen su propia regla lógica de salida rota — ambos se suman
        aparte: equipos_fallados como equipos_adicionales (correcto ahí:
        un equipo que falla POR COMPLETO pierde todos sus conectores), y
        r.conectores_regla_caida (conectores puntuales, ya calculado en
        graph_impact.py — la entrada culpable + la salida gobernada de
        cada regla rota) más los dos extremos de cada cable cortado, sin
        arrastrar el resto de esos equipos."""
        r = self._esc_resultado
        if not r or not (r.equipos_impactados or r.equipos_fallados or r.causas_regla):
            return {}
        try:
            from senal_estado import senales_caidas_por_equipos
            conectores_adicionales = set(r.conectores_regla_caida)
            if r.cables_cortados and hasattr(self, "_imp_analyzer"):
                for cable_id in r.cables_cortados:
                    src_con, dst_con = self._imp_analyzer.conectores_del_cable(cable_id)
                    conectores_adicionales |= {src_con, dst_con}
            return senales_caidas_por_equipos(
                self._esc_db_path, r.equipos_impactados,
                equipos_adicionales=r.equipos_fallados,
                conectores_adicionales=conectores_adicionales)
        except Exception:
            return {}

    # ── Dibujo Cairo ─────────────────────────────────────────────────────────
    def _esc_on_draw_overlay(self, cr, W: int, H: int) -> None:
        """Insertar AL FINAL de _on_draw(), después de
        self._imp_on_draw_overlay(cr, W, H):
            self._esc_on_draw_overlay(cr, W, H)
        """
        esc = self._esc_actual
        tiene_cambios = bool(esc and esc.cambios)
        wire_en_progreso = bool(self._esc_wire_from)

        if not self._esc_modo and not tiene_cambios:
            return

        # Overlay en coords de mundo
        cr.save()
        cr.translate(self._pan_x, self._pan_y)
        cr.scale(self._zoom, self._zoom)

        r = self._esc_resultado

        if esc:
            cortados  = {c.id_cable for c in esc.cambios if c.tipo == "desconexion_cable"}
            fallados  = {c.id_equipo for c in esc.cambios if c.tipo == "falla_equipo"}
            virtuales = [c for c in esc.cambios if c.tipo == "conexion_virtual"]

            # Cables cortados
            for conn in self._conns:
                if conn["id"] not in cortados:
                    continue
                src = self._nodos.get(conn["src_eq"])
                dst = self._nodos.get(conn["dst_eq"])
                if not src or not dst:
                    continue
                x0 = src["x"] + src["ancho"]; y0 = src["y"] + src["alto"] / 2
                x1 = dst["x"];                y1 = dst["y"] + dst["alto"] / 2
                cr.set_source_rgba(*_C_CORTADO, 0.85)
                cr.set_line_width(4.0)
                cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
                self._imp_draw_cruz(cr, (x0 + x1) / 2, (y0 + y1) / 2, 11)

            # Conexiones virtuales propuestas
            for c in virtuales:
                pa = self._esc_puerto_pos_por_id(c.id_conector_a)
                pb = self._esc_puerto_pos_por_id(c.id_conector_b)
                if not pa or not pb:
                    continue
                cr.save()
                cr.set_dash([6, 4])
                cr.set_source_rgba(*_C_VIRTUAL, 0.95)
                cr.set_line_width(2.5)
                cr.move_to(*pa); cr.line_to(*pb); cr.stroke()
                cr.restore()

            # Nodos fallados (marcados a mano)
            for eq_id in fallados:
                nodo = self._nodos.get(eq_id)
                if not nodo:
                    continue
                x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
                cr.set_source_rgba(*_C_FALLADO, 0.28)
                cr.rectangle(x, y, w, h); cr.fill()
                cr.set_source_rgba(*_C_FALLADO, 0.90)
                cr.set_line_width(3.5)
                cr.rectangle(x - 2, y - 2, w + 4, h + 4); cr.stroke()

            # Nodos impactados / recuperados (consecuencia calculada)
            if r:
                for eq_id in r.equipos_impactados:
                    if eq_id in fallados:
                        continue
                    nodo = self._nodos.get(eq_id)
                    if not nodo:
                        continue
                    x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
                    cr.set_source_rgba(*_C_IMPACTADO, 0.20)
                    cr.rectangle(x, y, w, h); cr.fill()
                    cr.set_source_rgba(*_C_IMPACTADO, 0.75)
                    cr.set_line_width(2.5)
                    cr.rectangle(x - 2, y - 2, w + 4, h + 4); cr.stroke()
                for eq_id in r.equipos_recuperados:
                    nodo = self._nodos.get(eq_id)
                    if not nodo:
                        continue
                    x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
                    cr.set_source_rgba(*_C_RECUPERADO, 0.85)
                    cr.set_line_width(3.0)
                    cr.rectangle(x - 3, y - 3, w + 6, h + 6); cr.stroke()

        # Cable virtual en construcción (arrastre puerto→puerto)
        if wire_en_progreso:
            cid, _lado, _nodo_id = self._esc_wire_from
            p0 = self._esc_puerto_pos_por_id(cid)
            if p0:
                cr.save()
                cr.set_dash([5, 3])
                cr.set_source_rgba(*_C_VIRTUAL, 0.9)
                cr.set_line_width(2.0)
                cr.move_to(*p0); cr.line_to(self._esc_wire_mx, self._esc_wire_my); cr.stroke()
                cr.restore()

        cr.restore()

        # Hint / panel en coords de pantalla
        if self._esc_modo and not tiene_cambios and not wire_en_progreso:
            self._esc_draw_hint(cr, W)
        elif tiene_cambios:
            self._esc_draw_panel(cr, W, H, esc, r)

    @staticmethod
    def _esc_draw_hint(cr, W: int) -> None:
        cr.set_source_rgba(0.20, 0.10, 0.30, 0.88)
        cr.rectangle(0, 0, W, 42); cr.fill()
        cr.set_source_rgba(0.98, 0.75, 0.25, 1.0)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(13)
        cr.move_to(14, 20)
        cr.show_text("🧪 MODO ESCENARIO  —  Clic en un EQUIPO = falla, clic en un CABLE = corte")
        cr.move_to(14, 37)
        cr.set_font_size(11)
        cr.set_source_rgba(0.85, 0.75, 0.55, 1.0)
        cr.show_text("🔗 Reconexión: arrastrá de un puerto a otro  ·  Botón derecho para salir")

    def _esc_draw_panel(self, cr, W: int, H: int, esc: "Escenario",
                         r) -> None:
        PW = 300; PH = min(H - 20, 640)
        px = W - PW - 10; py = 10

        cr.set_source_rgba(*_C_PAN_BG)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.fill()
        cr.set_source_rgba(*_C_PAN_BRD); cr.set_line_width(1.5)
        self._imp_rrect(cr, px, py, PW, PH, 10); cr.stroke()

        y = py + 26

        def txt(s, color=_C_TEXTO, bold=False, size=11):
            nonlocal y
            if y > py + PH - 20:
                return
            cr.set_source_rgba(*color)
            cr.select_font_face("Sans", 0, 1 if bold else 0)
            cr.set_font_size(size)
            cr.move_to(px + 14, y)
            cr.show_text(s[:44])
            y += size + 7

        nombre = esc.nombre if esc.id_escenario is not None else "(sin guardar)"
        txt(f"🧪 {nombre}", _C_TITULO, bold=True, size=13)
        y += 4

        fallados  = [c for c in esc.cambios if c.tipo == "falla_equipo"]
        cortados  = [c for c in esc.cambios if c.tipo == "desconexion_cable"]
        virtuales = [c for c in esc.cambios if c.tipo == "conexion_virtual"]

        if fallados:
            txt(f"🔺 {len(fallados)} equipo(s) fallado(s)", bold=True)
        if cortados:
            txt(f"✕ {len(cortados)} cable(s) cortado(s)", bold=True)
        if virtuales:
            txt(f"🔗 {len(virtuales)} reconexión(es) virtual(es)", bold=True)

        y += 4
        if r is None:
            txt("(calculando…)", (0.7, 0.7, 0.7, 1.0))
        elif not r.hay_impacto and not r.equipos_impactados_sin_reconexion:
            txt("✓ Sin impacto detectado.", (0.30, 0.80, 0.35, 1.0))
        else:
            antes = len(r.equipos_impactados_sin_reconexion)
            despues = len(r.equipos_impactados)
            if virtuales:
                txt(f"Consumidores afectados: {antes} → {despues}",
                    bold=True)
                if r.equipos_recuperados:
                    txt(f"  ✓ {len(r.equipos_recuperados)} recuperado(s) "
                        "por la reconexión", _C_RECUPERADO)
            else:
                txt(f"{despues} equipo(s) quedan sin señal", bold=True)

            if r.causas_regla:
                y += 2
                for texto_causa in list(r.causas_regla.values())[:4]:
                    txt(f"⚠ {texto_causa}", (0.85, 0.65, 0.15, 1.0), size=10)

            # plan_estado_senal_y_linaje.md, Función 1: nombres de señal
            # (no sólo equipos) que quedan huérfanos con este escenario.
            nombres_senal = sorted({
                info["nombre_senal"]
                for info in self._esc_senales_cache_dict.values()
                if info["nombre_senal"]
            })
            if nombres_senal:
                y += 4
                txt(f"📡 {len(nombres_senal)} señal(es) se pierden:", bold=True)
                for nombre in nombres_senal[:6]:
                    txt(f"  • {nombre}", (0.85, 0.75, 0.55, 1.0), size=10)
                if len(nombres_senal) > 6:
                    txt(f"  … y {len(nombres_senal) - 6} más",
                        (0.65, 0.60, 0.50, 1.0), size=10)

        if esc.id_escenario is None:
            y += 6
            txt("(guardalo con 💾 para no perderlo)", (0.65, 0.65, 0.70, 1.0), size=10)

    # ── Diálogos utilitarios ─────────────────────────────────────────────────
    def _esc_msg(self, texto: str) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
            text=texto)
        dlg.run()
        dlg.destroy()

    def _esc_confirmar(self, texto: str) -> bool:
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO,
            text=texto)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def _esc_confirmar_aplicar(self, resumen: dict) -> bool:
        partes = []
        if resumen["cables_a_desconectar"]:
            partes.append("Se DESCONECTAN estos cables (quedan de alta, sin extremos):")
            for _cid, nombre in resumen["cables_a_desconectar"]:
                partes.append(f"  • {nombre}")
        if resumen["reconexiones"]:
            if partes:
                partes.append("")
            partes.append("Se CREAN estas conexiones nuevas (cable nuevo automático):")
            for a, b in resumen["reconexiones"]:
                partes.append(f"  • conector {a} → conector {b}")

        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.YES_NO,
            text="¿Aplicar estos cambios a la infraestructura real?")
        dlg.format_secondary_text("\n".join(partes))
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de módulo
# ─────────────────────────────────────────────────────────────────────────────

def _esc_tipos_compatibles(tipo_a: str, tipo_b: str) -> bool:
    a, b = tipo_a.upper(), tipo_b.upper()
    return ((a in _FAM_ENTRADA and b in _FAM_SALIDA)
            or (a in _FAM_SALIDA and b in _FAM_ENTRADA))


def _dialogo_nombre_escenario(parent):
    """(nombre, descripcion) o None si se canceló."""
    dlg = Gtk.Dialog(title="Nombre del escenario", transient_for=parent,
                      modal=True, destroy_with_parent=True)
    dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                     "Aceptar", Gtk.ResponseType.OK)
    dlg.set_default_size(380, 180)
    box = dlg.get_content_area()
    box.set_margin_start(12); box.set_margin_end(12)
    box.set_margin_top(10); box.set_margin_bottom(10)
    box.set_spacing(6)

    box.pack_start(Gtk.Label(label=_("Nombre:"), xalign=0), False, False, 0)
    entry_nombre = Gtk.Entry()
    entry_nombre.set_activates_default(True)
    box.pack_start(entry_nombre, False, False, 0)

    box.pack_start(Gtk.Label(label=_("Descripción (opcional):"), xalign=0), False, False, 4)
    entry_desc = Gtk.Entry()
    box.pack_start(entry_desc, False, False, 0)

    dlg.set_default_response(Gtk.ResponseType.OK)
    dlg.show_all()
    resp = dlg.run()
    nombre = entry_nombre.get_text().strip()
    descripcion = entry_desc.get_text().strip()
    dlg.destroy()
    if resp != Gtk.ResponseType.OK or not nombre:
        return None
    return nombre, descripcion


def _dialogo_listado_escenarios(parent):
    """id_escenario elegido, o None."""
    Modelo.asegurar_tablas_escenario()
    dlg = Gtk.Dialog(title="Escenarios guardados", transient_for=parent,
                      modal=True, destroy_with_parent=True)
    dlg.add_buttons("Cerrar", Gtk.ResponseType.CLOSE,
                     "Eliminar", Gtk.ResponseType.REJECT,
                     "Abrir", Gtk.ResponseType.OK)
    dlg.set_default_size(560, 360)
    box = dlg.get_content_area()
    box.set_margin_start(10); box.set_margin_end(10)
    box.set_margin_top(8); box.set_margin_bottom(8)

    # id, nombre, descripcion, estado, fecha, n_cambios
    store = Gtk.ListStore(int, str, str, str, str, int)

    def recargar():
        store.clear()
        for fila in Modelo.devolver_todos_los_escenarios():
            store.append(fila)

    recargar()
    tv = Gtk.TreeView(model=store)
    for idx, titulo in ((1, "Nombre"), (3, "Estado"), (5, "Cambios"), (4, "Última edición")):
        tv.append_column(Gtk.TreeViewColumn(titulo, Gtk.CellRendererText(), text=idx))
    sel = tv.get_selection()
    sw = Gtk.ScrolledWindow()
    sw.set_vexpand(True)
    sw.add(tv)
    box.pack_start(sw, True, True, 4)
    dlg.show_all()

    while True:
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            model, it = sel.get_selected()
            if it is None:
                continue
            id_esc = model[it][0]
            dlg.destroy()
            return id_esc
        elif resp == Gtk.ResponseType.REJECT:
            model, it = sel.get_selected()
            if it is None:
                continue
            id_esc, nombre = model[it][0], model[it][1]
            confirmar = Gtk.MessageDialog(
                transient_for=dlg, modal=True,
                message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.YES_NO,
                text=f"¿Eliminar el escenario «{nombre}»? Esta acción no se puede deshacer.")
            r2 = confirmar.run()
            confirmar.destroy()
            if r2 == Gtk.ResponseType.YES:
                Modelo.eliminar_escenario(id_esc)
                recargar()
            continue
        else:
            dlg.destroy()
            return None
