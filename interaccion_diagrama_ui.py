"""InteraccionMixin — eventos de mouse/teclado sobre el canvas del diagrama de conexiones (selección, arrastre, zoom, tooltips).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
from gi.repository import Gdk

from modelo import Modelo


class InteraccionMixin:
    def _on_press(self, da, event):
        if self._esc_on_press(da, event):
            return True
        if self._diag_on_press(da, event):
            return True
        if self._visp_on_press(da, event):
            return True
        if self._imp_on_press(da, event):
            return True
        if self._senal_on_press(da, event):
            return True
        # Clics en los botones HUD del buscador (coords de pantalla)
        if self._buscar_ids and event.button == 1:
            ex, ey = event.x, event.y
            for rect, accion in [
                (getattr(self, "_buscar_btn_prev", None), lambda: self._buscar_navegar(-1)),
                (getattr(self, "_buscar_btn_next", None), lambda: self._buscar_navegar(+1)),
                (getattr(self, "_buscar_btn_x",    None), lambda: self._buscar_limpiar()),
            ]:
                if rect and rect[0] <= ex <= rect[0]+rect[2] and rect[1] <= ey <= rect[1]+rect[3]:
                    accion()
                    return True

        # Clic en el minimapa → centrar la vista en ese punto (y permitir arrastre)
        mm = self._minimap_rect
        if mm and event.button == 1:
            mx, my, mw, mh, mn_x, mn_y, escala, off_x, off_y = mm
            if mx <= event.x <= mx + mw and my <= event.y <= my + mh:
                self._minimap_dragging = True
                self._minimap_mover_a(event.x, event.y)
                return True

        wx, wy = self._s2w(event.x, event.y)

        ctrl  = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)

        if event.button == 1:
            # Clic sobre un puerto (no en doble clic): arrancar el
            # arrastre "elástico" para crear una conexión nueva hacia otro
            # puerto — mismo gesto que el editor clásico EditorConexiones.
            # Se chequea ANTES que _hit_node porque los puertos viven sobre
            # el borde del nodo (deben ganar el clic ahí).
            if event.type != Gdk.EventType.DOUBLE_BUTTON_PRESS:
                hit_p = self._hit_puerto(wx, wy)
                if hit_p:
                    self._wire_from = hit_p
                    self._wire_mx, self._wire_my = wx, wy
                    self._da.queue_draw()
                    return
            hit = self._hit_node(wx, wy)
            if hit:
                hid = hit["id"]
                if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
                    # Doble clic siempre abre el diálogo sin importar modificadores
                    from cabledoc import _DialogoEquipo
                    dlg = _DialogoEquipo(id_equipo=hid, parent=self)
                    dlg.run_and_destroy()
                elif ctrl or shift:
                    # Ctrl/Shift+clic: toggle en la selección múltiple
                    if hid in self._sel_ids:
                        self._sel_ids.discard(hid)
                        if hid == self._sel_id:
                            self._sel_id = next(iter(self._sel_ids), None)
                    else:
                        self._sel_ids.add(hid)
                        self._sel_id = hid
                else:
                    # Clic simple: seleccionar sólo este nodo
                    if hid not in self._sel_ids:
                        # Si no estaba en la selección, reemplazar
                        self._sel_ids = {hid}
                    # Si ya estaba seleccionado, mantener selección múltiple para drag
                    self._sel_id = hid

                # Preparar drag del grupo completo
                self._drag_id = hid
                self._drag_offsets = {
                    eid: (wx - self._nodos[eid]["x"], wy - self._nodos[eid]["y"])
                    for eid in self._sel_ids
                    if eid in self._nodos
                }
                self._drag_ox = wx - hit["x"]
                self._drag_oy = wy - hit["y"]

                n = len(self._sel_ids)
                if n == 1:
                    self._lbl_sel.set_text(
                        f"{hit['nombre']}   [{hit['tipo']}]   id={hit['id']}")
                else:
                    self._lbl_sel.set_text(f"{n} equipos seleccionados")
            else:
                # Clic en vacío sin modificador: iniciar rubber-band
                if not (ctrl or shift):
                    self._sel_id  = None
                    self._sel_ids = set()
                    self._lbl_sel.set_text("Sin selección")
                self._drag_id      = None
                self._drag_offsets = {}
                self._rband_active = True
                self._rband_x0 = self._rband_x1 = wx
                self._rband_y0 = self._rband_y1 = wy
        elif event.button in (2, 3):
            self._panning = True
            self._pan_mx  = event.x; self._pan_my = event.y
            self._pan_ox  = self._pan_x; self._pan_oy = self._pan_y
        if self._conexiones_incompletas_activo:
            self._actualizar_conexiones_incompletas()
        # El modo "todas" no depende de self._sel_id, pero un cambio de
        # selección puede coincidir con una edición previa (ej. se acaba de
        # crear la segunda punta de un cable desde otro diálogo) — se
        # refresca igual por consistencia con el comportamiento de la
        # variante por equipo seleccionado.
        if self._todas_conexiones_incompletas_activo:
            self._actualizar_todas_conexiones_incompletas()
        self._da.queue_draw()

    def _on_motion(self, da, event):
        if self._esc_on_motion(da, event):
            return
        self._visp_on_motion(da, event)
        btn1 = bool(event.state & Gdk.ModifierType.BUTTON1_MASK)
        if self._minimap_dragging and btn1:
            self._minimap_mover_a(event.x, event.y)
            return
        wx, wy = self._s2w(event.x, event.y)
        if self._wire_from and btn1:
            # Arrastrando un cable "elástico" desde un puerto: sólo hace
            # falta actualizar el extremo libre y redibujar.
            self._wire_mx, self._wire_my = wx, wy
            self._da.queue_draw()
            return
        if self._drag_id and btn1:
            # Mover todos los nodos del grupo seleccionado
            for eid, (ox, oy) in self._drag_offsets.items():
                nd = self._nodos.get(eid)
                if nd:
                    nd["x"] = wx - ox
                    nd["y"] = wy - oy
            self._da.queue_draw()
        elif self._rband_active and btn1:
            # Actualizar esquina opuesta del rubber-band
            self._rband_x1 = wx
            self._rband_y1 = wy
            # Seleccionar nodos dentro del rectángulo en tiempo real
            rx0 = min(self._rband_x0, wx); rx1 = max(self._rband_x0, wx)
            ry0 = min(self._rband_y0, wy); ry1 = max(self._rband_y0, wy)
            self._sel_ids = {
                eid for eid, nd in self._nodos.items()
                if rx0 <= nd["x"] + nd["ancho"]/2 <= rx1
                and ry0 <= nd["y"] + nd["alto"]/2  <= ry1
            }
            n = len(self._sel_ids)
            self._lbl_sel.set_text(
                f"{n} equipo{'s' if n != 1 else ''} seleccionado{'s' if n != 1 else ''}"
                if n else "Sin selección"
            )
            self._da.queue_draw()
        elif self._panning:
            self._pan_x = self._pan_ox + (event.x - self._pan_mx)
            self._pan_y = self._pan_oy + (event.y - self._pan_my)
            self._da.queue_draw()

    def _on_release(self, da, event):
        if self._esc_on_release(da, event):
            return
        if self._minimap_dragging:
            self._minimap_dragging = False
            return
        if self._wire_from:
            src = self._wire_from
            self._wire_from = None
            wx, wy = self._s2w(event.x, event.y)
            dst = self._hit_puerto(wx, wy)
            self._da.queue_draw()
            if dst and dst[0]["id"] != src[0]["id"]:
                self._crear_conexion_wire(src, dst)
            return
        if self._drag_id:
            # Guardar posición de todos los nodos movidos
            if self._id_inicio is None:
                for eid in self._drag_offsets:
                    nd = self._nodos.get(eid)
                    if nd:
                        Modelo.guardar_posicion_en_diagrama(nd["id"], nd["x"], nd["y"])
            self._drag_id      = None
            self._drag_offsets = {}
        if self._rband_active:
            self._rband_active = False
            # Si el rubber-band fue mínimo (clic rápido), limpiar selección
            if (abs(self._rband_x1 - self._rband_x0) < 4 and
                    abs(self._rband_y1 - self._rband_y0) < 4):
                self._sel_ids = set()
                self._lbl_sel.set_text("Sin selección")
            self._da.queue_draw()
        self._panning = False

    def _on_scroll(self, da, event):
        factor = 1.15 if event.direction == Gdk.ScrollDirection.UP else 1/1.15
        old_z  = self._zoom
        new_z  = max(0.04, min(4.0, self._zoom * factor))
        self._pan_x = event.x - (event.x - self._pan_x) * (new_z / old_z)
        self._pan_y = event.y - (event.y - self._pan_y) * (new_z / old_z)
        self._zoom  = new_z
        self._lbl_zoom.set_text(f"{int(new_z*100)}%")
        self._da.queue_draw()

    # ── toolbar actions ──────────────────────────────────────────────────────
    def _on_key_global(self, widget, event):
        """Ctrl+F abre el buscador; Ctrl+E expande vecinos (del nodo
        primario o de todos los nodos seleccionados, igual que el menú
        "⊕ Expandir vecinos"); Escape lo limpia; n/N navegan resultados."""
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and event.keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self._buscar_abrir_dialogo()
            return True
        if ctrl and event.keyval in (Gdk.KEY_e, Gdk.KEY_E):
            self._expandir()
            return True
        if event.keyval == Gdk.KEY_Escape and self._buscar_ids:
            self._buscar_limpiar()
            return True
        return False


    # ── EXPORTACION SVG / PDF ──────────────────────────────────────────────────

    def _hit_node(self, wx, wy):
        for nodo in reversed(list(self._nodos.values())):
            x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
            if x <= wx <= x+w and y <= wy <= y+h:
                return nodo
        return None

    # ── data loading ────────────────────────────────────────────────────────
    def _hit_puerto(self, wx, wy):
        """Coords MUNDO → (nodo, con_id, lado) si caen sobre el círculo de
        un puerto visible, o None. Sólo aplica en modo completo ("Mostrar
        solo nombre nodo" no dibuja puertos, así que tampoco se pueden
        arrastrar). Usado para permitir crear conexiones arrastrando de un
        puerto a otro — mismo gesto que tenía el editor clásico
        EditorConexiones ("modo clásico" de Alta rápida de conexiones)."""
        if self._solo_nombre:
            return None
        r2 = (self.PORT_R + 4) ** 2
        for nodo in self._nodos.values():
            for cid, _cnm, _ in nodo.get("in", []):
                px, py = self._port_pos(nodo, cid, "in")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r2:
                    return nodo, cid, "in"
            for cid, _cnm, _ in nodo.get("out", []):
                px, py = self._port_pos(nodo, cid, "out")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r2:
                    return nodo, cid, "out"
        return None

    def _s2w(self, sx, sy):
        """Screen → world."""
        return (sx - self._pan_x) / self._zoom, \
               (sy - self._pan_y) / self._zoom

    def _port_pos(self, nodo, con_id, side):
        """World position of port circle for a connector.
        Must match body_y in _draw_node exactly."""
        lst = nodo["in"] if side == "in" else nodo["out"]
        body_y = nodo["y"] + self.HDR_H + self.PORT_PAD + 10  # +10 for tipo label
        for idx, (cid, _, _) in enumerate(lst):
            if cid == con_id:
                py = body_y + idx * self.PORT_H + self.PORT_H / 2
                px = nodo["x"] if side == "in" else nodo["x"] + nodo["ancho"]
                return px, py
        # fallback: mid-edge
        py = nodo["y"] + nodo["alto"] / 2
        px = nodo["x"] if side == "in" else nodo["x"] + nodo["ancho"]
        return px, py

    def _nombre_puerto(self, nodo, con_id, lado):
        """Nombre del conector con_id en el lado ("in"/"out") indicado del
        nodo, o el propio id como fallback si no se encuentra."""
        for cid, cnm, _ in nodo.get(lado, []):
            if cid == con_id:
                return cnm
        return con_id

    def _senal_puerto_bajo_cursor(self, ex, ey):
        """Coords de pantalla → busca si caen sobre un puerto IN/OUT de
        algún nodo visible. Devuelve id_conector o None. Usado por el
        tooltip de señal (Fase 5 de plan_entidad_senal.md). Ver también
        `_hit_puerto` (coords mundo), usado para el arrastre puerto→puerto
        que crea conexiones nuevas."""
        if self._solo_nombre:
            return None  # en modo compacto no se dibujan puertos
        wx, wy = self._s2w(ex, ey)
        r_mundo = self.PORT_R + 3
        for nodo in self._nodos.values():
            for cid, _cnm, _t in nodo.get("in", []):
                px, py = self._port_pos(nodo, cid, "in")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r_mundo ** 2:
                    return cid
            for cid, _cnm, _t in nodo.get("out", []):
                px, py = self._port_pos(nodo, cid, "out")
                if (wx - px) ** 2 + (wy - py) ** 2 <= r_mundo ** 2:
                    return cid
        return None

    def _senal_on_query_tooltip(self, da, x, y, kb, tooltip):
        cid = self._senal_puerto_bajo_cursor(x, y)
        if cid is None:
            return False
        texto = self._senal_tooltip_puerto(cid)
        if not texto:
            return False
        tooltip.set_text(texto)
        return True

    def _minimap_mover_a(self, ex, ey):
        """Centra la vista en el punto del mundo correspondiente a (ex,ey)
        de pantalla, usando la proyección del minimapa. Sin clamping para
        permitir arrastre fluido incluso si el cursor sale del rect."""
        mm = self._minimap_rect
        if not mm:
            return
        mx, my, mw, mh, mn_x, mn_y, escala, off_x, off_y = mm
        wx_click = mn_x + (ex - off_x) / escala
        wy_click = mn_y + (ey - off_y) / escala
        alloc = self._da.get_allocation()
        self._pan_x = alloc.width  / 2 - wx_click * self._zoom
        self._pan_y = alloc.height / 2 - wy_click * self._zoom
        self._da.queue_draw()

    # ── interaction ─────────────────────────────────────────────────────────

