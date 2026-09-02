"""
riesgo_diagrama_ui.py — Mixin de UI para DiagramaConexiones
=============================================================
Agrega "🎨 Colorear por riesgo" y "🔺 Simular falla del seleccionado" al
diagrama de conexiones, reutilizando el Índice de Riesgo de Falla (IRF)
calculado por risk_engine.py y el motor de grafo de graph_impact.py.

Sigue el mismo patrón que impacto_ui.ImpactoMixin: se mezcla por herencia
múltiple en DiagramaConexiones y expone puntos de integración puntuales
para no tener que reescribir el dibujo Cairo existente.

Integración en pantallas_avanzadas.py (3 cambios, ya aplicados):
  1. class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin, Gtk.Dialog):
  2. self._riesgo_init(db_path)               — junto a self._impacto_init(...)
  3. for w in self._riesgo_crear_items_menu(): menu_riesgo.append(w)
     (los ítems se agregan al submenú "Riesgo" de la barra de menús)
  4. En _draw_node(): usar self._riesgo_color_y_borde(...) para obtener
     color de cabecera y ancho de borde en vez de los valores crudos.
"""

import json
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from modelo import Modelo, DB_PATH

try:
    from i18n import _
except ImportError:
    def _(t): return t


class RiesgoDiagramaMixin:
    """Pegar en DiagramaConexiones via herencia múltiple."""

    # ── Init ─────────────────────────────────────────────────────────────
    def _riesgo_init(self, db_path: str) -> None:
        """Llamar al final de __init__, junto a self._impacto_init(...)."""
        self._riesgo_db_path = db_path
        self._riesgo_color_activo = False   # toggle "🎨 Colorear por riesgo"
        self._riesgo_cache = {}             # {id_equipo(str): (riesgo, impacto, nivel)}
        # plan_estado_senal_y_linaje.md, Función 1: cruce por conector de
        # la última simulación de falla corrida desde este mixin, para que
        # senal_diagrama_ui.py pueda tacharlo si "Colorear por señal" está
        # activo al mismo tiempo. Se completa en _riesgo_on_simular_falla;
        # no persiste entre simulaciones (se pisa cada vez que se corre de
        # nuevo, y no hay "modo persistente" acá — ver docstring del
        # método para el porqué).
        self._riesgo_senales_cache_dict = {}
        self._riesgo_cargar_cache()

    def _riesgo_cargar_cache(self) -> None:
        """Relee la caché de riesgo (riesgo_equipo_cache) desde la BD.
        Barato: una sola consulta, sin tocar el motor de grafo."""
        try:
            filas = Modelo._query(
                "SELECT id_equipo, riesgo, impacto, nivel FROM riesgo_equipo_cache")
            self._riesgo_cache = {
                str(r[0]): (r[1], r[2], r[3]) for r in filas
            }
        except Exception:
            self._riesgo_cache = {}

    # ── Ítems de menú ───────────────────────────────────────────────────
    def _riesgo_crear_items_menu(self) -> list:
        """Devuelve [toggle_color, btn_simular] como Gtk.MenuItem para
        agregar al submenú "Riesgo" de la barra de menús."""
        self._riesgo_btn_toggle = Gtk.CheckMenuItem(label=_("🎨 Colorear por riesgo"))
        self._riesgo_btn_toggle.set_tooltip_text(
            "Pinta la cabecera de cada equipo según su Índice de Riesgo de "
            "Falla (verde/amarillo/naranja/rojo) y engrosa el borde de los "
            "que son punto único de falla.\n"
            "Usa el último cálculo guardado (ventana Equipos → 🔺 Recalcular riesgo)."
        )
        self._riesgo_btn_toggle.connect("toggled", self._riesgo_on_toggle_color)

        btn_simular = Gtk.MenuItem(label=_("🔺 Simular falla del seleccionado"))
        btn_simular.set_tooltip_text(
            "Selecciona un equipo en el diagrama y hacé clic acá para ver "
            "qué otros equipos quedan sin señal si ese equipo falla por completo."
        )
        btn_simular.connect("activate", self._riesgo_on_simular_falla)

        return [self._riesgo_btn_toggle, btn_simular]

    # ── Handlers ─────────────────────────────────────────────────────────
    def _riesgo_on_toggle_color(self, btn) -> None:
        self._riesgo_color_activo = btn.get_active()
        if self._riesgo_color_activo:
            self._riesgo_cargar_cache()   # traer el último cálculo al activar
        self._da.queue_draw()

    def _riesgo_on_simular_falla(self, _btn=None) -> None:
        sel_id = getattr(self, "_sel_id", None)
        if not sel_id:
            self._riesgo_msg("Seleccioná un equipo en el diagrama primero "
                             "(clic simple sobre su cabecera).")
            return
        try:
            from graph_impact import GraphImpactAnalyzer
        except Exception as e:
            self._riesgo_msg(f"Análisis de impacto no disponible:\n{e}")
            return
        try:
            analyzer = GraphImpactAnalyzer(self._riesgo_db_path)
            analyzer.construir_grafo()
            resultado = analyzer.simular_falla_equipo(sel_id)
        except Exception as e:
            self._riesgo_msg(f"No se pudo simular la falla:\n{e}")
            return

        dlg = Gtk.Dialog(
            title=f"Equipos afectados si falla: {resultado.nombre_equipo}",
            transient_for=self.get_toplevel(), modal=True)
        dlg.add_buttons("Cerrar", Gtk.ResponseType.CLOSE)
        dlg.set_default_size(420, 380)
        box = dlg.get_content_area()
        box.set_margin_start(12); box.set_margin_end(12)
        box.set_margin_top(10); box.set_margin_bottom(10)

        if not resultado.hay_impacto:
            lbl = Gtk.Label(label=_(
                "Ningún equipo depende exclusivamente de este: hay redundancia o no alimenta a nadie más."))
            lbl.set_line_wrap(True)
            box.pack_start(lbl, False, False, 0)
        else:
            lbl = Gtk.Label(label=(
                f"{len(resultado.equipos_impactados)} equipo(s) quedan sin señal:"))
            lbl.set_xalign(0); lbl.set_line_wrap(True)
            box.pack_start(lbl, False, False, 0)

            if resultado.causas_regla:
                lbl_causa = Gtk.Label()
                lbl_causa.set_markup(
                    "<span foreground='#d4a017' size='small'>⚠ "
                    + "\n⚠ ".join(GLib.markup_escape_text(t)
                                  for t in resultado.causas_regla.values())
                    + "</span>")
                lbl_causa.set_xalign(0); lbl_causa.set_line_wrap(True)
                box.pack_start(lbl_causa, False, False, 4)

            store = Gtk.ListStore(str, str)
            for eq_id in sorted(resultado.equipos_impactados,
                                key=lambda x: analyzer.nombre_equipo(x)):
                store.append([analyzer.nombre_equipo(eq_id), eq_id])
            tv = Gtk.TreeView(model=store)
            tv.append_column(Gtk.TreeViewColumn(
                "Equipo sin señal", Gtk.CellRendererText(), text=0))
            sw = Gtk.ScrolledWindow()
            sw.set_vexpand(True)
            sw.add(tv)
            box.pack_start(sw, True, True, 6)

            # Fase 6 de plan_entidad_senal.md: además de LOS EQUIPOS,
            # mostrar qué señales (por nombre) se pierden — mismo cruce
            # que _imp_calcular_senales_perdidas en impacto_ui.py, pero
            # acá se arma en el momento porque este diálogo no se
            # repinta en un loop de 'draw' (no hay costo de cachear).
            senales = self._riesgo_senales_perdidas(resultado)
            if senales:
                sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                box.pack_start(sep, False, False, 4)
                lbl_sen = Gtk.Label(
                    label=f"📡 {len(senales)} señal(es) se pierden:")
                lbl_sen.set_xalign(0)
                box.pack_start(lbl_sen, False, False, 0)
                store_sen = Gtk.ListStore(str)
                for nombre in senales:
                    store_sen.append([nombre])
                tv_sen = Gtk.TreeView(model=store_sen, headers_visible=False)
                tv_sen.append_column(Gtk.TreeViewColumn(
                    "", Gtk.CellRendererText(xpad=4), text=0))
                sw_sen = Gtk.ScrolledWindow()
                sw_sen.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                sw_sen.set_min_content_height(min(28 * len(senales) + 4, 120))
                sw_sen.add(tv_sen)
                box.pack_start(sw_sen, False, False, 0)

        dlg.show_all()
        dlg.run()
        dlg.destroy()
        # Este "Simular falla del seleccionado" es modal y de un solo
        # disparo (no hay un "modo persistente" como el de ⚡ Analizar
        # Impacto / 🧪 Modo Escenario que se mantenga después de cerrar).
        # Limpiar el cache acá evita dejar un tachado "fantasma" en el
        # diagrama si algo lo repinta después de cerrar este diálogo.
        self._riesgo_senales_cache_dict = {}
        self._da.queue_draw()

    def _riesgo_senales_perdidas(self, resultado) -> list:
        """Fase 6 de plan_entidad_senal.md: nombres de señal (distintos,
        ordenados) cargados hoy en algún conector de los equipos
        afectados. Mismo cruce informativo que
        impacto_ui.ImpactoMixin._imp_calcular_senales_perdidas — no
        recalcula propagación, sólo lee lo ya guardado.

        A partir de plan_estado_senal_y_linaje.md (Función 1) delega en
        senal_estado.py (mismo cálculo, factorizado) y de paso deja
        poblado self._riesgo_senales_cache_dict por conector.

        Recibe el `resultado` completo (ResultadoImpactoEquipo), no sólo
        equipos_impactados — bugfix 2026-08-24: ese equipo (el que falló
        directamente) NO está incluido en equipos_impactados a propósito
        (sigue "vivo" para el resto del grafo, sólo deja de propagar), así
        que hay que sumarlo aparte (equipos_adicionales, correcto acá
        porque un equipo que falla POR COMPLETO sí pierde todos sus
        conectores). Además se suma resultado.conectores_regla_caida
        (conectores puntuales, no equipo entero) para los casos donde la
        falla en cascada rompe la regla lógica de OTRO equipo aguas
        abajo — mismo criterio ya validado en impacto_ui.py."""
        try:
            from senal_estado import senales_caidas_por_equipos
            self._riesgo_senales_cache_dict = senales_caidas_por_equipos(
                self._riesgo_db_path, resultado.equipos_impactados,
                equipos_adicionales={str(resultado.equipo_id)},
                conectores_adicionales=resultado.conectores_regla_caida)
            return sorted({
                info["nombre_senal"]
                for info in self._riesgo_senales_cache_dict.values()
                if info["nombre_senal"]
            })
        except Exception:
            self._riesgo_senales_cache_dict = {}
            return []

    def _riesgo_msg(self, texto: str) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
            text=texto)
        dlg.run()
        dlg.destroy()

    # ── Integración con _draw_node ──────────────────────────────────────
    _NIVEL_COLOR = {
        "Crítico": (0.85, 0.15, 0.15),
        "Alto":    (0.90, 0.55, 0.10),
        "Medio":   (0.90, 0.80, 0.10),
        "Bajo":    (0.15, 0.65, 0.20),
    }

    def _riesgo_color_y_borde(self, id_equipo, rc, gc, bc, ancho_base) -> tuple:
        """Dado el color de cabecera (rc,gc,bc) y ancho de borde base ya
        calculados por _draw_node, devuelve la versión ajustada por riesgo
        si el toggle está activo. Si no, devuelve los valores tal cual
        (no-op — seguro de llamar siempre)."""
        if not self._riesgo_color_activo:
            return rc, gc, bc, ancho_base
        info = self._riesgo_cache.get(str(id_equipo))
        if not info:
            return rc, gc, bc, ancho_base
        riesgo, impacto, nivel = info
        color = self._NIVEL_COLOR.get(nivel, (rc, gc, bc))
        # Engrosar el borde según impacto (0-100 -> +0 a +3px), para
        # distinguir visualmente "punto único de falla" de "riesgoso"
        extra = min(3.0, (impacto or 0) / 33.0)
        return color[0], color[1], color[2], ancho_base + extra
