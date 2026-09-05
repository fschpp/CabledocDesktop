#!/usr/bin/env python3
"""
panel_arbol_ui.py — CableDoc GTK3

Dominio Panel de navegación en árbol, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 9).

Contiene:
  - PanelArbol

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta este nombre sin cambios para que ningún
`from cabledoc import X` externo se rompa (aunque, a diferencia de las
entregas anteriores, `PanelArbol` no tiene actualmente ningún consumidor
externo fuera de `cabledoc.py` mismo — confirmado por grep — se reexporta
igual por consistencia con el resto del patrón de la fachada).

Última entrega antes del cierre (Entrega 10) a propósito: `PanelArbol` es
el orquestador visual que dispara diálogos de *todos* los dominios ya
extraídos en las Entregas 1-8 (equipos, cables, conectores, racks, frames,
salas), así que se deja para el final: sus referencias cruzadas ya apuntan
a módulos finales y no hace falta retocarlas de nuevo en una entrega
posterior.

Referencias cruzadas a diálogos de otros dominios (`_DialogoEquipo`,
`_DialogoRack`, `_DialogoFrame`, `_DialogoConector`, `_DialogoCable`,
`_DialogoConexion`, `_DialogoPosicionRack`) se resuelven con import
diferido dentro del método que las usa (`_on_row_activated` y
`_on_drag_data_received`), rutuando vía `from cabledoc import X` — mismo
patrón ya establecido por `racks_salas_ui.py` con `FramesListado` y
`catalogos_basicos_ui.py` con `_DialogoCable` — en vez de importarlas
directo de cada módulo hermano. `_DialogoEquipoNoRackSala` ya usaba este
mismo patrón de import diferido *dentro* de `cabledoc.py` antes de esta
entrega (necesario para evitar ciclo cuando `PanelArbol` todavía vivía en
el mismo archivo); se preserva sin cambios, sólo combinado en la misma
línea con `_DialogoPosicionRack` porque ambos se usan en el mismo método.

`s()` y `DialogoNombre` (genéricos de `pantallas_comunes.py`, no un
dominio específico) sí se importan directo a nivel de módulo, igual que
en `racks_salas_ui.py`.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GObject

import time
from datetime import datetime

from modelo import Modelo

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import s, DialogoNombre


class PanelArbol(Gtk.Box):
    """
    Panel lateral con árbol jerárquico de infraestructura:
      Sala → Rack → Frame → Equipo → Conectores
              └──→ Equipo directo → Conectores
         └──→ Equipos sin rack → Conectores

    Al hacer clic en un nodo se abre el diálogo de edición correspondiente.
    """

    # Columnas del TreeStore
    COL_LABEL  = 0   # str — texto visible
    COL_TIPO   = 1   # str — "sala"|"rack"|"frame"|"equipo"|"conector"|"sin_rack"
    COL_ID     = 2   # str — id del objeto
    COL_ID2    = 3   # str — id auxiliar (id_rack para frame, id_equipo para conector)
    COL_COLOR  = 4   # str — color de la etiqueta de tipo
    COL_BADGE  = 5   # str — texto del badge
    COL_PESO   = 6   # int — Pango weight (700=bold, 400=normal)

    _BADGE_COLOR = {
        "sala":     "#534AB7",
        "rack":     "#185FA5",
        "frame":    "#BA7517",
        "equipo":   "#3B6D11",
        "conector": "#555550",
        "sin_rack": "#888880",
        "cable":    "#8B4513",
        "conexion": "#708090",
        "seccion":  "#444444",
    }

    def __init__(self, ventana_principal):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._vp = ventana_principal
        self.set_size_request(260, -1)

        # ── Cabecera ──
        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hdr.set_margin_start(8); hdr.set_margin_end(8)
        hdr.set_margin_top(6);   hdr.set_margin_bottom(4)

        lbl_titulo = Gtk.Label(xalign=0)
        lbl_titulo.set_markup("<b>Infraestructura</b>")
        hdr.pack_start(lbl_titulo, False, False, 0)

        # Buscador
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_lupa = Gtk.Label(label="🔍")
        self._entry_filtro = Gtk.Entry(placeholder_text="buscar equipo, rack, frame…")
        self._entry_filtro.set_hexpand(True)
        self._entry_filtro.connect("changed", self._on_filtro_changed)
        search_box.pack_start(lbl_lupa, False, False, 0)
        search_box.pack_start(self._entry_filtro, True, True, 0)
        hdr.pack_start(search_box, False, False, 0)

        self._lbl_status = Gtk.Label(xalign=0)
        self._lbl_status.set_no_show_all(False)
        hdr.pack_start(self._lbl_status, False, False, 0)

        self.pack_start(hdr, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        # ── TreeStore: label, tipo, id, id2, color, badge, peso ──
        self._store = Gtk.TreeStore(str, str, str, str, str, str, int)
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._row_visible)

        # PRUEBA: Usar el store directamente para drag and drop
        # self._tv = Gtk.TreeView(model=self._filter)
        self._tv = Gtk.TreeView(model=self._store)
        self._tv.set_headers_visible(False)
        self._tv.set_enable_search(False)
        self._tv.set_reorderable(False)  # Importante para drag and drop
        self._tv.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        col = Gtk.TreeViewColumn()
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_expand(True)
        self._tv.append_column(col)
        self._tv.set_hexpand(True)

        # Nombre del nodo — sin truncar
        rend_label = Gtk.CellRendererText()
        col.pack_start(rend_label, True)
        col.add_attribute(rend_label, "text",   self.COL_LABEL)
        col.add_attribute(rend_label, "weight", self.COL_PESO)

        # Badge de tipo (sala / rack / frame / equipo …)
        rend_badge = Gtk.CellRendererText(xpad=4, foreground_set=True)
        col.pack_start(rend_badge, False)
        col.add_attribute(rend_badge, "text",       self.COL_BADGE)
        col.add_attribute(rend_badge, "foreground", self.COL_COLOR)

        self._tv.connect("row-activated", self._on_row_activated)
        
        # ── Configurar Drag and Drop ─────────────────────────────────────
        # Permitir arrastrar equipos sin ubicación a salas
        import sys
        # Abrir archivo de log
        self._drag_drop_log = open("/tmp/cabledoc_drag_drop.log", "w", encoding="utf-8")
        def safe_log(msg):
            try:
                self._drag_drop_log.write(f"{msg}\n")
                self._drag_drop_log.flush()
            except Exception:
                pass
            try:
                print(f"{msg}", flush=True)
            except (BrokenPipeError, OSError):
                # Ignorar errores de pipe roto (cuando timeout termina el proceso)
                pass
            except Exception as e:
                pass
        self._log = safe_log
        
        self._log("\n" + "="*60)
        self._log("DRAG DROP LOG - Ver este archivo: /tmp/cabledoc_drag_drop.log")
        self._log("="*60)
        
        # Configurar drag source usando el STORE original (no el filtro)
        # Esto es necesario porque TreeModelFilter no soporta bien drag and drop
        # Ahora que usamos self._store directamente, configurar drag and drop normal
        self._log("Configurando drag source en TreeView")
        # Usar target STRING para simplificar
        target_entry = Gtk.TargetEntry.new("STRING", Gtk.TargetFlags.SAME_WIDGET, 0)
        self._tv.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            [target_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        )
        self._tv.connect("drag-data-get", self._on_drag_data_get)
        
        self._log("Configurando drag dest en TreeView")
        self._tv.enable_model_drag_dest(
            [target_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        )
        self._tv.connect("drag-data-received", self._on_drag_data_received)
        # Conectar drag-motion para indicar que el destino es válido
        self._tv.connect("drag-motion", self._on_drag_motion_valid)
        self._log("Drag and drop configurado ===")
        
        # Configurar drag and drop manual (para TreeModelFilter) - COMENTADO para usar DnD nativo
        # self._tv.connect("button-press-event", self._on_treeview_button_press)
        # self._tv.connect("button-release-event", self._on_treeview_button_release)
        # self._tv.connect("motion-notify-event", self._on_motion_notify)

        sw = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._tv)
        self.pack_start(sw, True, True, 0)

        # Botón recargar
        btn_reload = Gtk.Button(label=_("↺ Recargar árbol"))
        btn_reload.set_margin_start(6); btn_reload.set_margin_end(6)
        btn_reload.set_margin_top(4);   btn_reload.set_margin_bottom(6)
        btn_reload.connect("clicked", lambda b: self.recargar(forzar_bd=True))
        self.pack_start(btn_reload, False, False, 0)

        self._filtro_texto = ""
        self._arbol_datos = None       # cache en memoria: [nodo_infra, nodo_cables]
        self._filtro_debounce_id = None
        self.recargar(forzar_bd=True)

    # ── Manejadores de eventos para debug ────────────────────────────────────
    def _on_drag_motion_valid(self, tv, context, x, y, timestamp):
        """Manejador para validar movimiento durante drag y configurar destino."""
        # Obtener el nodo bajo el cursor
        result = tv.get_path_at_pos(x, y)
        if result:
            path = result[0]
            self._log(f"[DRAG MOTION] Path válido: {path} en ({x}, {y})")
            # Indicar que el destino es válido
            # Configurar el destino del drag para resaltar
            tv.set_drag_dest_row(path, Gtk.TreeViewDropPosition.INTO_OR_AFTER)
            # Aceptar el drop
            Gdk.drag_status(context, Gdk.DragAction.COPY, timestamp)
            return True
        else:
            self._log(f"[DRAG MOTION] No hay nodo en ({x}, {y})")
            # Rechazar el drop en esta posición
            Gdk.drag_status(context, 0, timestamp)
            return False

    def _on_treeview_button_press(self, tv, event):
        """Manejador para detectar click en TreeView y grabar el punto de inicio del drag."""
        result = tv.get_path_at_pos(event.x, event.y)
        # get_path_at_pos devuelve (path, column, x, y) o None
        if result:
            path = result[0]  # Extraer solo el path
            self._log(f"[BUTTON PRESS] path={path}, button={event.button}")
            # Guardar información para posible drag
            if event.button == 1:  # Botón izquierdo
                self._drag_start_path = path  # Guardar solo el path
                self._drag_start_x = event.x
                self._drag_start_y = event.y
        else:
            self._log(f"[BUTTON PRESS] No path at ({event.x}, {event.y}), button={event.button}")
            self._drag_start_path = None
        return False  # Permitir propagación del evento

    def _on_treeview_button_release(self, tv, event):
        """Manejador para detectar release en TreeView."""
        result = tv.get_path_at_pos(event.x, event.y)
        path = result[0] if result else None
        if path:
            self._log(f"[BUTTON RELEASE] path={path}, button={event.button}")
        else:
            self._log(f"[BUTTON RELEASE] No path at ({event.x}, {event.y}), button={event.button}")
        # Limpiar drag start
        self._drag_start_path = None
        return False  # Permitir propagación del evento

    def _on_motion_notify(self, tv, event):
        """Manejador para detectar movimiento y iniciar drag manualmente."""
        # Verificar si hay un drag en progreso
        if hasattr(self, '_drag_start_path') and self._drag_start_path is not None:
            # Calcular distancia desde el inicio
            dx = abs(event.x - self._drag_start_x)
            dy = abs(event.y - self._drag_start_y)
            # Iniciar drag si se movió suficiente distancia (threshold típico: 5-10 píxeles)
            if dx > 5 or dy > 5:
                self._log(f"[MOTION] Iniciando drag manual desde {self._drag_start_path}")
                # Obtener el iter del path guardado
                it = self._store.get_iter(self._drag_start_path)
                if it:
                    tipo = self._store.get_value(it, self.COL_TIPO)
                    oid = self._store.get_value(it, self.COL_ID)
                    self._log(f"[MOTION] tipo={tipo}, ID={oid}")
                    
                    if tipo == "equipo":
                        # Iniciar drag manualmente
                        self._start_manual_drag(tv, oid, self._drag_start_path)
                        # Limpiar para evitar múltiples drags
                        self._drag_start_path = None
                        return True  # Evento manejado
        return False  # Permitir propagación del evento

    def _start_manual_drag(self, tv, equipo_id, path):
        """Inicia un drag manualmente con el ID del equipo."""
        self._log(f"[MANUAL DRAG] Iniciando drag para equipo {equipo_id}")
        
        # Crear target list
        target_list = Gtk.TargetList.new([
            Gtk.TargetEntry.new("tree-row", Gtk.TargetFlags.SAME_WIDGET, 0)
        ])
        
        # Iniciar el drag
        context = tv.drag_begin(
            target_list,
            Gdk.DragAction.COPY,
            1,  # Botón izquierdo
            (0, 0)  # Hotspot
        )
        
        # Conectar señal drag-data-get al contexto
        context.connect("drag-data-get", self._on_manual_drag_data_get, equipo_id)
        
        self._log(f"[MANUAL DRAG] Drag iniciado para equipo {equipo_id}")

    def _on_manual_drag_data_get(self, context, selection, info, timestamp, equipo_id):
        """Manejador para proporcionar datos durante drag manual."""
        self._log(f"[MANUAL DRAG] drag-data-get llamado para equipo {equipo_id}")
        selection.set(Gtk.SELECTION_TYPE_STRING, 0, str(equipo_id).encode())

    # ── Drag and Drop ─────────────────────────────────────────────────────────
    
    def _on_drag_drop(self, tv, context, x, y, timestamp):
        """Sobrescribir manejador por defecto de drag_drop (requerido para TreeModelFilter)."""
        # Detener la emisión de la señal por defecto
        GObject.signal_stop_emission_by_name(tv, "drag_drop")
        # Devolver True para indicar que manejamos el evento
        return True

    def _on_drag_data_get(self, tv, context, selection, info, timestamp):
        """Manejador para obtener datos al arrastrar un nodo."""
        self._log("\n--- DRAG START ---")
        self._log(f"_on_drag_data_get called")
        # Usar la selección actual del TreeView
        sel = tv.get_selection()
        model, it = sel.get_selected()
        self._log(f"Selection - model: {model}, it: {it}")
        if not it:
            self._log("No selected iter")
            return
        
        # Obtener tipo e ID del iter
        tipo = model.get_value(it, self.COL_TIPO)
        oid = model.get_value(it, self.COL_ID)
        self._log(f"Node - Tipo: {tipo}, ID: {oid}")
        
        # Solo permitir arrastrar equipos (incluyendo los de "Sin ubicación")
        if tipo == "equipo":
            self._log(f"Setting selection data for equipo {oid}")
            # Almacenar el ID del equipo en la selección
            # Usar set_text que automáticamente usa el target STRING
            selection.set_text(str(oid), -1)
        else:
            self._log(f"Not an equipo, type is {tipo}")

    def _on_drag_data_received(self, tv, context, x, y, selection, info, timestamp):
        """Manejador para recibir datos al soltar en un nodo."""
        self._log("\n--- DROP RECEIVED ---")
        self._log(f"[DROP] x={x}, y={y}")
        
        # Obtener el equipo arrastrado
        id_equipo = selection.get_text()
        if not id_equipo:
            data = selection.get_data()
            id_equipo = data.decode() if data else None
        if not id_equipo:
            self._log("No data received")
            context.finish(False, False)
            return
        self._log(f"Equipo arrastrado ID: {id_equipo}")
        
        # Obtener el nodo destino (donde se soltó)
        # get_drag_dest_row() sin parámetros para obtener el destino actual del drag
        result = tv.get_drag_dest_row()
        self._log(f"[DROP] get_drag_dest_row() result: {result}")
        if result:
            path, pos = result
            self._log(f"[DROP] Drag dest row path: {path}, pos: {pos}")
            # Si get_drag_dest_row devolvió path=None, intentar con get_path_at_pos
            if not path:
                result = tv.get_path_at_pos(x, y)
                path = result[0] if result else None
                pos = None
                self._log(f"[DROP] Fallback 1: Path at pos: {path}")
        else:
            # Intentar con get_path_at_pos
            result = tv.get_path_at_pos(x, y)
            path = result[0] if result else None
            pos = None
            self._log(f"[DROP] Fallback 2: Path at pos: {path}")
        
        if not path:
            self._log("[DROP ERROR] No path found at all")
            context.finish(False, False)
            return
        
        # Usar el store directamente (el TreeView ahora usa self._store)
        it = self._store.get_iter(path)
        if not it:
            self._log("No iter found for path")
            context.finish(False, False)
            return
        
        # it ya es del store, no necesitamos convertir
        self._log(f"Iter obtenido para path {path}")
        
        tipo_destino = self._store.get_value(it, self.COL_TIPO)
        id_destino = self._store.get_value(it, self.COL_ID)
        nombre_destino = self._store.get_value(it, self.COL_LABEL)
        self._log(f"Destino - Tipo: {tipo_destino}, ID: {id_destino}, Nombre: {nombre_destino}")
        
        # Obtener nombre del equipo
        eq_row = Modelo.devolver_equipo(id_equipo)
        nombre_equipo = s(eq_row[0][1]) if eq_row and eq_row[0] else f"Equipo {id_equipo}"
        self._log(f"Equipo nombre: {nombre_equipo}")
        
        # Verificar si el equipo ya tiene ubicación
        import sqlite3
        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur = conn.cursor()
        
        # Verificar si está en rack/frame
        cur.execute("SELECT 1 FROM posicion_en_rack WHERE id_equipo = ?", (id_equipo,))
        en_rack = cur.fetchone() is not None
        self._log(f"en_rack: {en_rack}")
        
        # Verificar si está en slot
        cur.execute("SELECT 1 FROM slot WHERE id_equipo = ?", (id_equipo,))
        en_slot = cur.fetchone() is not None
        self._log(f"en_slot: {en_slot}")
        
        # Verificar si está en equiponoraqueable_por_sala
        cur.execute("SELECT 1 FROM equiponoraqueable_por_sala WHERE id_equipo = ?", (id_equipo,))
        en_sala = cur.fetchone() is not None
        self._log(f"en_sala: {en_sala}")
        
        conn.close()
        
        equipo_sin_ubicacion = not en_rack and not en_slot and not en_sala
        self._log(f"equipo_sin_ubicacion: {equipo_sin_ubicacion}")
        
        # Permitir soltar solo equipos sin ubicación
        if tipo_destino == "sala" and equipo_sin_ubicacion:
            self._log(f"Abriendo _DialogoEquipoNoRackSala para sala {id_destino}")
            # Abrir diálogo para agregar equipo suelto a sala
            from cabledoc import _DialogoEquipoNoRackSala, _DialogoPosicionRack
            dlg = _DialogoEquipoNoRackSala(parent=self._vp)
            dlg._id_sala = id_destino
            dlg._id_equipo = id_equipo
            # Prellenar nombres
            dlg.e_sala.set_text(nombre_destino)
            dlg.e_equipo.set_text(nombre_equipo)
            dlg.run_and_destroy()
            self._log(f"Dialogo _DialogoEquipoNoRackSala cerrado")
            self.recargar(forzar_bd=True)
            self._status(f"✅ Equipo {nombre_equipo} asignado a sala {nombre_destino}")
            
        elif tipo_destino == "rack" and equipo_sin_ubicacion:
            self._log(f"Abriendo _DialogoPosicionRack para rack {id_destino}")
            # Abrir diálogo para agregar posición en rack
            dlg = _DialogoPosicionRack(id_rack=id_destino, parent=self._vp)
            dlg.id_equipo = id_equipo
            # Pre-seleccionar el rack
            dlg.e_rack.set_text(nombre_destino)
            # Pre-cargar el equipo que se arrastró
            dlg.e_equipo.set_text(nombre_equipo)
            if dlg.run() == Gtk.ResponseType.OK:
                self._status(f"✅ Equipo {nombre_equipo} asignado a rack {nombre_destino}")
                self.recargar(forzar_bd=True)
            dlg.destroy()
        elif not equipo_sin_ubicacion:
            self._log(f"Equipo ya tiene ubicacion, mostrando mensaje")
            self._status(f"⚠️  El equipo {nombre_equipo} ya tiene una ubicación asignada")
        else:
            self._log(f"Tipo destino no manejado: {tipo_destino}")
        
        context.finish(True, False)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _tlog(self, etapa, extra=""):
        """Log de performance: timestamp + ms transcurridos desde el t0 de esta recarga."""
        ahora = time.perf_counter()
        t0 = getattr(self, "_t0_perf", ahora)
        elapsed_total = (ahora - t0) * 1000
        ultimo = getattr(self, "_t_ultimo_perf", t0)
        elapsed_paso = (ahora - ultimo) * 1000
        self._t_ultimo_perf = ahora
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        msg = f"[PERF {ts}] +{elapsed_paso:7.1f}ms (total {elapsed_total:7.1f}ms)  {etapa}"
        if extra:
            msg += f"  — {extra}"
        print(msg, flush=True)

    MAX_FILAS_CON_FILTRO = 400   # tope de filas insertadas cuando hay filtro activo

    def recargar(self, forzar_bd=False):
        self._t0_perf = time.perf_counter()
        self._t_ultimo_perf = self._t0_perf
        self._tlog("recargar() INICIO",
                   f"filtro='{self._filtro_texto}' forzar_bd={forzar_bd}")
        self._log("\n=== RECARGAR ===")
        # Guardar paths expandidos antes de limpiar
        expandidos = []
        self._tv.map_expanded_rows(lambda tv, path: expandidos.append(path.to_string()))
        self._log(f"Paths expandidos antes: {expandidos}")

        if forzar_bd or self._arbol_datos is None:
            self._arbol_datos = self._cargar_arbol_datos()
            self._tlog("_cargar_arbol_datos() FIN (consultó la BD)")
        else:
            self._tlog("usando caché en memoria (SIN consultar la BD)")

        # Desconectar el modelo del TreeView mientras se reconstruye (evita
        # revalidación/redibujo de GTK en cada append durante la carga completa).
        self._tv.set_model(None)
        try:
            self._store.clear()
            self._renderizar_store_desde_cache()
            self._tlog("_renderizar_store_desde_cache() FIN",
                       f"{self._filas_creadas} filas insertadas, "
                       f"{self._total_matches} matches, tope={self._tope_alcanzado}")
        finally:
            self._tv.set_model(self._store)

        if self._filtro_texto:
            if self._tope_alcanzado:
                self._lbl_status.set_markup(
                    f"<small>Mostrando {self._filas_creadas} de "
                    f"{self._total_matches} coincidencias — "
                    f"seguí escribiendo para acotar…</small>")
            else:
                n = self._total_matches
                self._lbl_status.set_markup(
                    f"<small>{n} coincidencia{'s' if n != 1 else ''}</small>")
            self._tv.expand_all()
            self._tlog("expand_all() FIN — recargar() TOTAL")
            return
        else:
            self._lbl_status.set_text("")

        # Restaurar expansión previa; si no había nada expandido, abrir primer nodo
        if expandidos:
            for path_str in expandidos:
                try:
                    self._tv.expand_row(Gtk.TreePath.new_from_string(path_str), False)
                except Exception:
                    pass
        else:
            # Expandir las dos raíces: Infraestructura (0) y Cables (1)
            self._tv.expand_row(Gtk.TreePath.new_from_string("0"), False)
        self._tlog("recargar() TOTAL")

    def _nodo(self, label, tipo, id_, id2, color, badge, peso, hijos=None):
        return {"vals": [label, tipo, id_, id2, color, badge, peso],
                "hijos": hijos if hijos is not None else []}

    def _renderizar_store_desde_cache(self):
        """Vuelca self._arbol_datos (estructura en memoria) al TreeStore,
        insertando SOLO los nodos visibles (que matchean el filtro o tienen
        algún descendiente que matchea) — nunca inserta un nodo para
        borrarlo después.

        Esa era la causa real de la demora: insertar los ~5000 nodos
        completos en el TreeStore y podar casi todos a continuación generaba
        un churn masivo de objetos GTK/PyGObject que degradaba progresivamente
        (10s → 18s → 22s en llamadas idénticas, aun con el modelo
        desconectado del TreeView). Acá primero se calcula la visibilidad en
        Python puro sobre la caché en memoria (barato, sin GTK), y recién
        después se inserta — una sola vez — lo que corresponde."""
        texto = self._filtro_texto

        visible_cache = {}
        self._total_matches = 0

        def calcular_visibilidad(nodo):
            label = nodo["vals"][0].lower()
            vis_propio = (not texto) or (texto in label)
            if vis_propio and texto:
                self._total_matches += 1
            vis_por_hijo = False
            for hijo in nodo["hijos"]:
                if calcular_visibilidad(hijo):
                    vis_por_hijo = True
            visible = vis_propio or vis_por_hijo
            visible_cache[id(nodo)] = visible
            return visible

        for raiz in self._arbol_datos:
            calcular_visibilidad(raiz)
        self._tlog("calcular_visibilidad() FIN (sin tocar GTK)",
                   f"{self._total_matches} matches directos")

        self._filas_creadas  = 0
        self._tope_alcanzado = False
        limite = self.MAX_FILAS_CON_FILTRO if texto else None

        def volcar(nodo, it_padre):
            if limite is not None and self._filas_creadas >= limite:
                self._tope_alcanzado = True
                return
            it = self._store.append(it_padre, nodo["vals"])
            self._filas_creadas += 1
            for hijo in nodo["hijos"]:
                if limite is not None and self._filas_creadas >= limite:
                    self._tope_alcanzado = True
                    return
                if visible_cache.get(id(hijo), True):
                    volcar(hijo, it)

        for raiz in self._arbol_datos:
            if limite is not None and self._filas_creadas >= limite:
                self._tope_alcanzado = True
                break
            if visible_cache.get(id(raiz), True):
                volcar(raiz, None)

    def _cargar_arbol_datos(self):
        """Lee toda la infraestructura de la BD UNA vez y arma una estructura
        de dicts en memoria (no toca self._store). Se llama solo al abrir
        la ventana, al presionar 'Recargar árbol', o tras un alta/baja/
        modificación — nunca en cada tecla del buscador."""
        import sqlite3

        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur  = conn.cursor()

        hijos_infra = []

        # ── Salas ──
        cur.execute("SELECT id_sala, nombre FROM sala ORDER BY nombre")
        salas = cur.fetchall()
        self._tlog("SQL salas", f"{len(salas)} salas")

        for id_sala, nombre_sala in salas:
            hijos_sala = []

            # Racks de esta sala
            cur.execute("""
                SELECT r.id_rack, r.nombre, r.numero
                FROM rack r
                JOIN rack_por_sala rps ON rps.id_rack = r.id_rack
                WHERE rps.id_sala = ?
                ORDER BY r.numero
            """, (id_sala,))
            racks = cur.fetchall()

            for id_rack, nombre_rack, _nr in racks:
                hijos_rack = []

                # Frames en este rack (via posicion_en_rack)
                cur.execute("""
                    SELECT f.id_frame, f.nombre
                    FROM posicion_en_rack p
                    JOIN frame f ON f.id_frame = p.id_frame
                    WHERE p.id_rack = ? AND p.id_frame IS NOT NULL
                    GROUP BY f.id_frame
                    ORDER BY p.orificio_posicion_equipo_en_rack
                """, (id_rack,))
                frames = cur.fetchall()

                for id_frame, nombre_frame in frames:
                    hijos_frame = []
                    # Equipos en slots de este frame
                    cur.execute("""
                        SELECT e.id_equipo, e.nombre, te.nombre
                        FROM slot sl
                        JOIN equipo e ON e.id_equipo = sl.id_equipo
                        LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                        WHERE sl.id_frame = ? AND sl.id_equipo IS NOT NULL AND sl.id_equipo != 0
                        ORDER BY sl.nombre
                    """, (id_frame,))
                    for id_eq, nom_eq, tipo_eq in cur.fetchall():
                        hijos_frame.append(self._nodo(
                            nom_eq, "equipo", str(id_eq), str(id_frame),
                            self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                            self._conectores_datos(cur, id_eq)))
                    hijos_rack.append(self._nodo(
                        nombre_frame, "frame", str(id_frame), str(id_rack),
                        self._BADGE_COLOR["frame"], "frame", 400, hijos_frame))

                # Equipos directos en rack (sin frame)
                cur.execute("""
                    SELECT e.id_equipo, e.nombre, te.nombre
                    FROM posicion_en_rack p
                    JOIN equipo e ON e.id_equipo = p.id_equipo
                    LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                    WHERE p.id_rack = ? AND p.id_frame IS NULL
                      AND p.id_equipo IS NOT NULL AND p.id_equipo != 0
                    ORDER BY p.orificio_posicion_equipo_en_rack, e.nombre
                """, (id_rack,))
                for id_eq, nom_eq, tipo_eq in cur.fetchall():
                    hijos_rack.append(self._nodo(
                        nom_eq, "equipo", str(id_eq), str(id_rack),
                        self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                        self._conectores_datos(cur, id_eq)))

                hijos_sala.append(self._nodo(
                    nombre_rack, "rack", str(id_rack), str(id_sala),
                    self._BADGE_COLOR["rack"], "rack", 400, hijos_rack))

            # Equipos sueltos de esta sala (equiponoraqueable_por_sala)
            # Excluir equipos que ya están en racks o frames
            cur.execute("""
                SELECT e.id_equipo, e.nombre, COALESCE(te.nombre,'')
                FROM equiponoraqueable_por_sala en
                JOIN equipo e ON e.id_equipo = en.id_equipo
                LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                WHERE en.id_sala = ?
                AND e.id_equipo NOT IN (
                    SELECT id_equipo FROM posicion_en_rack WHERE id_equipo IS NOT NULL AND id_equipo != 0
                )
                AND e.id_equipo NOT IN (
                    SELECT id_equipo FROM slot WHERE id_equipo IS NOT NULL AND id_equipo != 0
                )
                ORDER BY e.nombre
            """, (id_sala,))
            equipos_sueltos = cur.fetchall()
            if equipos_sueltos:
                hijos_sueltos = []
                for id_eq, nom_eq, tipo_eq in equipos_sueltos:
                    hijos_sueltos.append(self._nodo(
                        nom_eq, "equipo", str(id_eq), str(id_sala),
                        self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                        self._conectores_datos(cur, id_eq)))
                hijos_sala.append(self._nodo(
                    f"Equipos sueltos ({len(equipos_sueltos)})", "sin_rack",
                    str(id_sala), "", self._BADGE_COLOR["sin_rack"], "sueltos", 400,
                    hijos_sueltos))

            hijos_infra.append(self._nodo(
                nombre_sala, "sala", str(id_sala), "",
                self._BADGE_COLOR["sala"], "sala", 700, hijos_sala))

        self._tlog("loop salas/racks/frames/equipos/conectores FIN")

        # ── Equipos sin ubicación (no en rack, slot ni equiponoraqueable_por_sala) ──
        cur.execute("""
            SELECT e.id_equipo, e.nombre, te.nombre
            FROM equipo e
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE e.id_equipo != 0
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM posicion_en_rack
                  WHERE id_equipo IS NOT NULL AND id_equipo != 0
              )
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM slot
                  WHERE id_equipo IS NOT NULL AND id_equipo != 0
              )
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM equiponoraqueable_por_sala
                  WHERE id_equipo IS NOT NULL
              )
            ORDER BY e.nombre
        """)
        sin_rack = cur.fetchall()
        if sin_rack:
            hijos_sr = []
            for id_eq, nom_eq, tipo_eq in sin_rack:
                hijos_sr.append(self._nodo(
                    nom_eq, "equipo", str(id_eq), "",
                    self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                    self._conectores_datos(cur, id_eq)))
            hijos_infra.append(self._nodo(
                "" + _("Sin ubicación") + f" ({len(sin_rack)})", "sin_rack", "", "",
                self._BADGE_COLOR["sin_rack"], "", 700, hijos_sr))

        conn.close()
        self._tlog("_cargar_arbol_datos() sección Infraestructura FIN",
                   f"{len(sin_rack)} sin ubicación")

        nodo_infra = self._nodo(
            _("Infraestructura"), "seccion", "", "",
            self._BADGE_COLOR["seccion"], "", 700, hijos_infra)

        nodo_cables = self._cargar_seccion_cables_datos()
        self._tlog("_cargar_seccion_cables_datos() FIN")

        return [nodo_infra, nodo_cables]

    def _cargar_seccion_cables_datos(self):
        """Devuelve el nodo raíz 'Cables' con sus hijos (cable→conexiones)
        armado con 3 consultas SQL en total (antes: 1 + N conexiones SQLite
        nuevas, una por cada cable — cientos de conexiones por recarga)."""
        import sqlite3
        from collections import defaultdict
        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM cable")
        total = cur.fetchone()[0]
        self._tlog("_cargar_seccion_cables_datos() SQL count", f"{total} cables")

        cur.execute(
            "SELECT id_cable, codigo, COALESCE(estado,'') FROM cable ORDER BY codigo"
        )
        filas_cable = cur.fetchall()
        self._tlog("_cargar_seccion_cables_datos() SQL lista cables", f"{len(filas_cable)} filas")

        # Todas las conexiones de TODOS los cables en una sola consulta,
        # agrupadas por id_cable en Python (reemplaza al N+1 anterior).
        cur.execute(
            "SELECT id_cable, equipo_nombre, conector_nombre, tipo_conector, id_conexion "
            "FROM CONEXIONES ORDER BY id_cable"
        )
        por_cable = defaultdict(list)
        for id_cable, eq_nom, con_nom, tipo_con, id_conexion in cur.fetchall():
            por_cable[str(id_cable)].append((id_conexion, eq_nom, con_nom, tipo_con))
        self._tlog("_cargar_seccion_cables_datos() SQL conexiones (batch)",
                   f"{sum(len(v) for v in por_cable.values())} conexiones")

        hijos_cables = []
        for id_cable, codigo, estado in filas_cable:
            hijos_conex = []
            for id_conexion, eq_nom, con_nom, tipo_con in por_cable.get(str(id_cable), []):
                conn_label = f"{s(eq_nom) or '?'} - {s(con_nom) or '?'} ({s(tipo_con) or '?'})"
                hijos_conex.append(self._nodo(
                    conn_label, "conexion", str(id_conexion), "",
                    self._BADGE_COLOR["conexion"], "", 300))
            hijos_cables.append(self._nodo(
                s(codigo) or f"#{id_cable}", "cable", str(id_cable), "",
                self._BADGE_COLOR["cable"], estado or "", 400, hijos_conex))

        conn.close()
        self._tlog("_cargar_seccion_cables_datos() loop FIN", f"{len(filas_cable)} cables")

        return self._nodo(
            _("Cables") + f" ({total})", "seccion", "cables", "",
            self._BADGE_COLOR["seccion"], "", 700, hijos_cables)

    def _conectores_datos(self, cur, id_eq):
        cur.execute("""
            SELECT c.id_conector, c.nombre, tc.nombre
            FROM conector c
            LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE c.id_equipo = ?
            ORDER BY c.nombre
        """, (id_eq,))
        hijos = []
        for id_con, nom_con, tipo_con in cur.fetchall():
            hijos.append(self._nodo(
                nom_con or f"#{id_con}", "conector", str(id_con), str(id_eq),
                self._BADGE_COLOR["conector"], tipo_con or "", 400))
        return hijos

    # ── Filtro ───────────────────────────────────────────────────────────────

    _FILTRO_DEBOUNCE_MS = 300   # pausa de tipeo antes de filtrar
    _FILTRO_MIN_CHARS   = 2     # no filtrar con 1 solo carácter

    def _on_filtro_changed(self, entry):
        # Debounce: cancelar timer pendiente y reprogramar. Así "engin7"
        # tipeado rápido dispara UN solo filtrado, no uno por tecla.
        if self._filtro_debounce_id is not None:
            GLib.source_remove(self._filtro_debounce_id)
            self._filtro_debounce_id = None
        texto = entry.get_text().lower().strip()
        self._filtro_debounce_id = GLib.timeout_add(
            self._FILTRO_DEBOUNCE_MS, self._aplicar_filtro_debounced, texto)

    def _aplicar_filtro_debounced(self, texto):
        self._filtro_debounce_id = None
        # Con 1 solo carácter no filtramos (matchea casi todo, no aporta)
        if texto and len(texto) < self._FILTRO_MIN_CHARS:
            return False
        print(f"\n[PERF ========] filtro aplicado (debounced) → '{texto}'", flush=True)
        self._filtro_texto = texto
        self.recargar()   # sin forzar_bd: usa la caché en memoria, no toca la BD
        return False   # no repetir el GLib.timeout

    def _row_visible(self, model, it, data):
        txt = self._filtro_texto
        if not txt:
            return True
        # La fila es visible si su label o algún descendiente hace match
        label = (model.get_value(it, self.COL_LABEL) or "").lower()
        if txt in label:
            return True
        # Revisar hijos
        child = model.iter_children(it)
        while child:
            if self._row_visible(model, child, data):
                return True
            child = model.iter_next(child)
        return False

    # ── Acción al hacer clic ─────────────────────────────────────────────────

    def _on_row_activated(self, tv, path, col):
        # Import diferido: estos diálogos viven en módulos de dominio ya
        # extraídos (cables_conexiones_ui.py, conectores_ui.py,
        # equipos_ui.py, frames_slots_ui.py, racks_salas_ui.py); se rutea
        # vía `from cabledoc import X` en vez de importarlos directo de
        # cada módulo hermano, siguiendo la convención ya establecida por
        # `racks_salas_ui.py` con `FramesListado` y `catalogos_basicos_ui.py`
        # con `_DialogoCable`.
        from cabledoc import (
            _DialogoEquipo,
            _DialogoRack,
            _DialogoFrame,
            _DialogoConector,
            _DialogoCable,
            _DialogoConexion,
        )
        it = self._store.get_iter(path)
        if it is None:
            return
        tipo = self._store.get_value(it, self.COL_TIPO)
        oid  = self._store.get_value(it, self.COL_ID)
        if not oid:
            return

        vp = self._vp
        if tipo == "equipo":
            dlg = _DialogoEquipo(id_equipo=oid, parent=vp)
            dlg.run_and_destroy()
        elif tipo == "sala":
            rows = Modelo.devolver_sala(oid)
            if rows:
                nombre_actual = s(rows[0][1])
                dlg = DialogoNombre(_("Editar Sala"), valor=nombre_actual, parent=vp)
                if dlg.run() == Gtk.ResponseType.OK:
                    Modelo.modificacion_sala(oid, dlg.valor)
                dlg.destroy()
                self.recargar(forzar_bd=True)
        elif tipo == "rack":
            dlg = _DialogoRack(id_rack=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "frame":
            dlg = _DialogoFrame(id_frame=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "conector":
            id_eq = self._store.get_value(it, self.COL_ID2)
            dlg = _DialogoConector(id_conector=oid, id_equipo=id_eq, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "cable":
            dlg = _DialogoCable(id_cable=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "conexion":
            dlg = _DialogoConexion(id_conexion=oid, parent=vp)
            dlg.run_and_destroy()

