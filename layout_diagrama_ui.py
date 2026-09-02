"""LayoutMixin — organización automática de nodos del diagrama de conexiones (fit, expandir, alinear, auto-posicionar).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
import random

from modelo import Modelo


class LayoutMixin:
    def _auto_layout(self):
        no_pos = [n for n in self._nodos.values() if not n["has_pos"]]
        if not no_pos: return

        # Vista contextual (abierta desde un equipo): layout en columnas
        # IN-izquierda / centro / OUT-derecha, alineado a puertos
        if self._id_inicio and self._id_inicio in self._nodos:
            self._layout_lados_puertos(no_pos)
            return

        # Vista global: layout por columnas agrupado por tipo
        grupos = {}
        for n in no_pos:
            grupos.setdefault(n["tipo"], []).append(n)
        GAP_X = 290; GAP_Y = 60; MAX_R = 6
        col = 0
        for _, nlist in sorted(grupos.items()):
            row = 0
            for nd in nlist:
                nd["x"] = 80 + col * GAP_X
                nd["y"] = 80 + row * (nd["alto"] + GAP_Y)
                row += 1
                if row >= MAX_R: row = 0; col += 1
            col += 1

    def _layout_lados_puertos(self, nodos, id_central=None, recentrar=True):
        """Layout en columnas IN-izquierda / centro / OUT-derecha.

        `nodos` es la lista de nodos a posicionar (sin incluir el central,
        aunque si aparece se ignora). Solo se mueven equipos cuyo id esté
        en `nodos`; el resto de self._nodos queda intacto — por eso sirve
        tanto para el layout inicial (recentrar=True, todos los nodos sin
        posición) como para _expandir() (recentrar=False, solo los nodos
        recién agregados, alrededor del nodo seleccionado id_central).

        Cada vecino queda alineado en Y con el puerto del central al que se
        conecta; ambas columnas quedan en una sola línea vertical (mismo X)
        evitando superposición entre nodos.
        Se apoya en self._conns, ya reconstruido por _reconstruir_conexiones().
        """
        id_central = id_central or self._id_inicio
        centro = self._nodos.get(id_central)
        if not centro:
            return

        if recentrar:
            CX, CY = 600.0, 400.0
            centro["x"] = CX - self.NODE_W / 2
            centro["y"] = CY - centro["alto"] / 2
        CX = centro["x"] + centro["ancho"] / 2

        vecinos_ids = {n["id"] for n in nodos if n["id"] != id_central}
        if not vecinos_ids:
            return

        # Vecino asignado a cada puerto del central (uno por puerto, en orden)
        vecino_por_puerto_in  = {}   # con_id -> id_equipo vecino
        vecino_por_puerto_out = {}
        usados = set()
        for conn in self._conns:
            if (conn["dst_eq"] == id_central and conn["dst_con"]
                    and conn["src_eq"] in vecinos_ids
                    and conn["dst_con"] not in vecino_por_puerto_in):
                vecino_por_puerto_in[conn["dst_con"]] = conn["src_eq"]
                usados.add(conn["src_eq"])
            elif (conn["src_eq"] == id_central and conn["src_con"]
                    and conn["dst_eq"] in vecinos_ids
                    and conn["src_con"] not in vecino_por_puerto_out):
                vecino_por_puerto_out[conn["src_con"]] = conn["dst_eq"]
                usados.add(conn["dst_eq"])

        GAP_X     = 340   # separación horizontal columna ↔ nodo central
        GAP_Y_MIN = 24    # separación vertical mínima entre nodos apilados

        def colocar(lista_puertos, mapa_vecino, lado):
            prev_bottom = None
            x_col = CX - GAP_X if lado == "in" else CX + GAP_X
            for cid, _cnm, _ in lista_puertos:
                vid = mapa_vecino.get(cid)
                if not vid:
                    continue
                nd = self._nodos.get(vid)
                if not nd:
                    continue
                _, py = self._port_pos(centro, cid, lado)
                y = py - nd["alto"] / 2
                if prev_bottom is not None and y < prev_bottom + GAP_Y_MIN:
                    y = prev_bottom + GAP_Y_MIN
                nd["x"] = (x_col - nd["ancho"]) if lado == "in" else x_col
                nd["y"] = y
                prev_bottom = y + nd["alto"]

        colocar(centro["in"],  vecino_por_puerto_in,  "in")
        colocar(centro["out"], vecino_por_puerto_out, "out")

        # Vecinos sin puerto identificado (p.ej. cable sin conector propio)
        # se apilan igual en la columna derecha, debajo de los ya ubicados.
        faltantes = sorted(vecinos_ids - usados)
        if faltantes:
            x_col = CX + GAP_X
            ys_der = [self._nodos[v]["y"] + self._nodos[v]["alto"]
                      for v in usados
                      if v in vecino_por_puerto_out.values() and v in self._nodos]
            y = max(ys_der) + GAP_Y_MIN if ys_der else centro["y"]
            for vid in faltantes:
                nd = self._nodos.get(vid)
                if not nd:
                    continue
                nd["x"] = x_col
                nd["y"] = y
                y += nd["alto"] + GAP_Y_MIN

    # ── canvas drawing ──────────────────────────────────────────────────────
    def _fit_all(self):
        if not self._nodos: return
        alloc = self._da.get_allocation()
        if alloc.width < 10: return

        xs = [n["x"] for n in self._nodos.values()]
        ys = [n["y"] for n in self._nodos.values()]
        x2 = [n["x"]+n["ancho"] for n in self._nodos.values()]
        y2 = [n["y"]+n["alto"]  for n in self._nodos.values()]

        mn_x, mn_y = min(xs)-40,  min(ys)-40
        mx_x, mx_y = max(x2)+40, max(y2)+40
        cw = mx_x - mn_x; ch = mx_y - mn_y
        z  = max(0.04, min(2.0, min(alloc.width/cw, alloc.height/ch)))
        self._zoom  = z
        self._pan_x = (alloc.width  - cw*z)/2 - mn_x*z
        self._pan_y = (alloc.height - ch*z)/2 - mn_y*z
        self._lbl_zoom.set_text(f"{int(z*100)}%")
        self._da.queue_draw()

    def _expandir(self):
        """Expande vecinos de todos los nodos actualmente seleccionados
        (self._sel_ids, poblado por clic simple, rubber-band o
        Shift/Ctrl+clic). Si no hay selección múltiple activa, cae al
        nodo "primario" self._sel_id (compatibilidad con el flujo previo
        de un solo nodo). Para cada nodo central consulta sus vecinos en
        la base y agrega los que todavía no estén en el canvas, cada uno
        ubicado en columnas IN/OUT alrededor de SU nodo central (mismo
        criterio que antes, ahora aplicado por cada seleccionado). Un
        vecino compartido por dos o más centrales seleccionados sólo se
        agrega una vez, junto al primer central que lo reclama.
        Disponible desde el menú "⊕ Expandir vecinos" y con el atajo
        Ctrl+E (ver _on_key_global).
        """
        centrales = [eid for eid in self._sel_ids if eid in self._nodos]
        if not centrales and self._sel_id and self._sel_id in self._nodos:
            centrales = [self._sel_id]
        if not centrales:
            self._status("Seleccione al menos un nodo para expandir vecinos.")
            return

        nodos_nuevos_por_central = {}
        total_nuevos = 0
        for id_central in centrales:
            rows = Modelo._query(
                "SELECT DISTINCT \"id_equipo:1\" "
                "FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo=?",
                (id_central,))
            new_ids = {str(r[0]) for r in rows} - set(self._nodos.keys())
            if not new_ids:
                continue

            # Agregar los nodos nuevos de este central (sin tocar los
            # existentes ni los ya reclamados por un central anterior en
            # esta misma pasada, gracias a que new_ids se recalcula
            # contra self._nodos.keys() actualizado en cada iteración).
            nodos_nuevos = []
            for id_eq in new_ids:
                nodo = self._construir_nodo(id_eq, con_posicion=False)
                if nodo:
                    self._nodos[id_eq] = nodo
                    nodos_nuevos.append(nodo)
            if nodos_nuevos:
                nodos_nuevos_por_central[id_central] = nodos_nuevos
                total_nuevos += len(nodos_nuevos)

        if not nodos_nuevos_por_central:
            self._status("No hay vecinos nuevos para expandir.")
            return

        # Recalcular cables una sola vez al final (incluye los que
        # conectan a los nodos nuevos de todos los centrales procesados)
        self._reconstruir_conexiones()

        # Ubicar los nodos nuevos de cada central en columnas IN/OUT
        # alrededor de su nodo respectivo, sin mover ningún nodo existente
        for id_central, nodos_nuevos in nodos_nuevos_por_central.items():
            self._layout_lados_puertos(nodos_nuevos, id_central=id_central,
                                        recentrar=False)

        self._da.queue_draw()
        if len(centrales) > 1:
            self._status(
                f"{total_nuevos} nodo(s) nuevo(s) agregado(s) "
                f"({len(nodos_nuevos_por_central)} de {len(centrales)} "
                f"nodos seleccionados con vecinos nuevos).")
        else:
            self._status(f"{total_nuevos} nodo(s) nuevo(s) agregado(s).")

    def _alinear_horizontal(self):
        """Alinea nodos seleccionados horizontalmente usando la Y del nodo más a la derecha."""
        if len(self._sel_ids) < 2:
            self._status("Seleccione al menos 2 nodos para alinear.")
            return
        # Filtrar nodos que existen en _nodos
        valid_ids = [eid for eid in self._sel_ids if eid in self._nodos]
        if len(valid_ids) < 2:
            self._status("Seleccione al menos 2 nodos válidos para alinear.")
            return
        # Encontrar el nodo más a la derecha (mayor x)
        nodo_derecha = max(valid_ids, key=lambda eid: self._nodos[eid]["x"])
        y_alinear = self._nodos[nodo_derecha]["y"]
        # Aplicar la misma Y a todos los nodos seleccionados
        for eid in valid_ids:
            self._nodos[eid]["y"] = y_alinear
            Modelo.guardar_posicion_en_diagrama(eid, self._nodos[eid]["x"], y_alinear)
        self._status(f"Alineados {len(valid_ids)} nodos horizontalmente.")
        self._da.queue_draw()

    def _alinear_vertical(self):
        """Alinea nodos seleccionados verticalmente usando la X del nodo más arriba."""
        if len(self._sel_ids) < 2:
            self._status("Seleccione al menos 2 nodos para alinear.")
            return
        # Filtrar nodos que existen en _nodos
        valid_ids = [eid for eid in self._sel_ids if eid in self._nodos]
        if len(valid_ids) < 2:
            self._status("Seleccione al menos 2 nodos válidos para alinear.")
            return
        # Encontrar el nodo más arriba (menor y)
        nodo_arriba = min(valid_ids, key=lambda eid: self._nodos[eid]["y"])
        x_alinear = self._nodos[nodo_arriba]["x"]
        # Aplicar la misma X a todos los nodos seleccionados
        for eid in valid_ids:
            self._nodos[eid]["x"] = x_alinear
            Modelo.guardar_posicion_en_diagrama(eid, x_alinear, self._nodos[eid]["y"])
        self._status(f"Alineados {len(valid_ids)} nodos verticalmente.")
        self._da.queue_draw()

    def _auto_posicionar_sin_solape(self):
        """Reubica todos los nodos actuales del canvas para que ninguno se
        solape con otro (separación mínima ``MARGEN`` entre bordes).

        Pensado para "Alta rápida de conexiones": ahí los equipos se
        agregan sueltos —arrastrados del panel lateral a cualquier punto,
        o con doble clic, que los centra en la vista actual y puede
        apilar varios exactamente en el mismo punto— sin ningún criterio
        de layout automático como el que sí tiene "Expandir vecinos"
        (columnas IN/OUT alrededor de un nodo central).

        Algoritmo: separación de rectángulos por pares (AABB), iterativo.
        En cada pasada, para cada par de nodos que se solapan (incluyendo
        el margen), se empuja a ambos en direcciones opuestas a lo largo
        del eje de menor solape, hasta que no quede ningún par superpuesto
        o se llega al máximo de iteraciones. A diferencia de un layout
        completo (grilla/árbol), conserva la disposición general que ya
        armó el usuario — sólo los separa lo mínimo indispensable.

        A propósito, este botón sólo separa los nodos en memoria
        (self._nodos) para esta sesión de edición — NO llama a
        Modelo.guardar_posicion_en_diagrama(). En Alta rápida de
        conexiones la posición todavía no está "definitiva" mientras se
        arma el cableado; queda igual que cualquier otro reacomodo manual
        sin soltar el nodo: se persiste recién cuando el usuario arrastra
        ese nodo puntualmente (el drag normal sí guarda al soltar).
        """
        ids = list(self._nodos.keys())
        if len(ids) < 2:
            self._status("No hay suficientes nodos para reorganizar.")
            return

        MARGEN    = 40.0   # separación mínima entre bordes de nodos
        MAX_ITER  = 500

        # Si dos o más nodos quedaron exactamente en el mismo punto (p.ej.
        # varios "doble clic" seguidos, que los agrega centrados en la
        # vista), la repulsión no tiene una dirección clara en la que
        # empujar: se les da un empujoncito aleatorio inicial para
        # desambiguar, con semilla fija para que el resultado sea
        # reproducible si se aprieta el botón de nuevo sin mover nada.
        rnd = random.Random(1234)
        vistos = {}
        for eid in ids:
            n = self._nodos[eid]
            key = (round(n["x"]), round(n["y"]))
            if key in vistos:
                n["x"] += rnd.uniform(-25, 25)
                n["y"] += rnd.uniform(-25, 25)
            else:
                vistos[key] = eid

        for _ in range(MAX_ITER):
            hubo_solape = False
            for i in range(len(ids)):
                a = self._nodos[ids[i]]
                ax1, ay1 = a["x"] - MARGEN / 2, a["y"] - MARGEN / 2
                ax2, ay2 = a["x"] + a["ancho"] + MARGEN / 2, a["y"] + a["alto"] + MARGEN / 2
                for j in range(i + 1, len(ids)):
                    b = self._nodos[ids[j]]
                    bx1, by1 = b["x"] - MARGEN / 2, b["y"] - MARGEN / 2
                    bx2, by2 = b["x"] + b["ancho"] + MARGEN / 2, b["y"] + b["alto"] + MARGEN / 2

                    ox = min(ax2, bx2) - max(ax1, bx1)
                    oy = min(ay2, by2) - max(ay1, by1)
                    if ox <= 0 or oy <= 0:
                        continue   # no se solapan (con margen incluido)

                    hubo_solape = True
                    acx = a["x"] + a["ancho"] / 2; acy = a["y"] + a["alto"] / 2
                    bcx = b["x"] + b["ancho"] / 2; bcy = b["y"] + b["alto"] / 2

                    # Empujar a lo largo del eje de menor solape (el que
                    # resuelve la superposición moviendo menos distancia).
                    if ox < oy:
                        push = ox / 2 + 1
                        if acx <= bcx:
                            a["x"] -= push; b["x"] += push
                        else:
                            a["x"] += push; b["x"] -= push
                    else:
                        push = oy / 2 + 1
                        if acy <= bcy:
                            a["y"] -= push; b["y"] += push
                        else:
                            a["y"] += push; b["y"] -= push

                    # Recalcular bounds de "a" tras moverlo, para que las
                    # comparaciones siguientes en esta misma pasada usen
                    # su posición actualizada.
                    ax1, ay1 = a["x"] - MARGEN / 2, a["y"] - MARGEN / 2
                    ax2, ay2 = a["x"] + a["ancho"] + MARGEN / 2, a["y"] + a["alto"] + MARGEN / 2
            if not hubo_solape:
                break

        # A propósito, NO se llama a Modelo.guardar_posicion_en_diagrama()
        # acá: sólo reacomoda self._nodos en memoria para esta sesión de
        # Alta rápida de conexiones (ver docstring).
        self._da.queue_draw()
        self._fit_all()
        self._status(f"Reorganizados {len(ids)} nodos para evitar solapamientos (sin guardar posiciones).")

    def _centrar_zoom_inicial_global(self):
        """Vista global: zoom fijo al 150%, centrado en el bounding box
        de todos los nodos (mismo centro que representa el minimapa)."""
        if not self._nodos:
            return
        alloc = self._da.get_allocation()
        if alloc.width < 10:
            return
        xs  = [n["x"] for n in self._nodos.values()]
        ys  = [n["y"] for n in self._nodos.values()]
        x2s = [n["x"] + n["ancho"] for n in self._nodos.values()]
        y2s = [n["y"] + n["alto"]  for n in self._nodos.values()]
        cx = (min(xs) + max(x2s)) / 2
        cy = (min(ys) + max(y2s)) / 2
        self._zoom  = self.ZOOM_INICIAL_GLOBAL
        self._pan_x = alloc.width  / 2 - cx * self._zoom
        self._pan_y = alloc.height / 2 - cy * self._zoom
        self._lbl_zoom.set_text(f"{int(self._zoom*100)}%")

    def _centrar_en_nodo(self, nodo: dict):
        """Pan + zoom suave para que el nodo quede centrado en la vista."""
        alloc = self._da.get_allocation()
        W, H  = alloc.width, alloc.height
        cx = nodo["x"] + nodo["ancho"] / 2
        cy = nodo["y"] + nodo["alto"]  / 2
        self._pan_x = W / 2 - cx * self._zoom
        self._pan_y = H / 2 - cy * self._zoom


