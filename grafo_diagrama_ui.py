"""GrafoMixin — carga y construcción del grafo de nodos/aristas del diagrama de conexiones.

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
from gi.repository import Gtk

from modelo import Modelo
from pantallas_comunes import _, s, _tipo_color


class GrafoMixin:
    def _cargar(self, id_inicio=None):
        self._nodos.clear(); self._conns.clear()
        # Una sola consulta en lote (no una por nodo) — ver
        # Modelo.equipos_con_regla_logica_activa.
        self._equipos_con_regla = Modelo.equipos_con_regla_logica_activa()
        self._equipos_criticos = Modelo.devolver_ids_equipos_criticos()

        # ── collect equipment IDs ──
        if id_inicio:
            eq_ids = {str(id_inicio)}
            rows = Modelo._query(
                "SELECT DISTINCT id_equipo, \"id_equipo:1\" "
                "FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo=?",
                (id_inicio,))
            for r in rows:
                eq_ids.add(str(r[1]))   # col 1 = id_equipo:1 (neighbour)
        elif getattr(self, "_iniciar_vacio", False):
            # Alta rápida de conexiones: arrancar sin nodos; se van
            # agregando a mano desde el panel "Agregar equipo".
            eq_ids = set()
        else:
            rows = Modelo._query(
                "SELECT DISTINCT id_equipo FROM CONEXIONES_AMBOS_EXTREMOS")
            eq_ids = {str(r[0]) for r in rows}

        # ── build nodes ──
        for id_eq in eq_ids:
            nodo = self._construir_nodo(id_eq, con_posicion=(id_inicio is None))
            if nodo:
                self._nodos[id_eq] = nodo

        # ── load cables between visible nodes (antes del layout: el layout
        #    contextual necesita saber qué puerto conecta a cada vecino) ──
        self._reconstruir_conexiones()

        self._auto_layout()

        if id_inicio is None:
            self._centrar_zoom_inicial_global()
        else:
            self._fit_all()
        # Refrescar los pendientes de relevar si algún modo estaba activo:
        # tras un _recargar() el set de nodos visibles pudo haber cambiado.
        if self._conexiones_incompletas_activo:
            self._actualizar_conexiones_incompletas()
        if self._todas_conexiones_incompletas_activo:
            self._actualizar_todas_conexiones_incompletas()
        self._da.queue_draw()
        self._status(f"{len(self._nodos)} nodos  ·  {len(self._conns)} cables")

    def _construir_nodo(self, id_eq, con_posicion=False):
        """Construye el dict-nodo para un equipo (sin agregarlo a self._nodos).
        con_posicion=True intenta leer la posición guardada en
        diagrama_equipos_posicion_en_imagen (solo aplica a la vista global).
        """
        rows_eq = Modelo.devolver_equipo(id_eq)
        if not rows_eq:
            return None
        r      = rows_eq[0]
        nombre = s(r[1]);  tipo = s(r[7])
        rol_senal = Modelo.devolver_rol_senal_tipo_equipo(r[8]) if r[8] else None

        con_rows = Modelo.devolver_conectores_de_equipo(id_eq)
        # Dirección de cada conector leída de tipo_conector.direccion (Fase
        # 1/2 de plan_desarrollo_hardcodes_idioma.md) en vez de buscar "IN"/
        # "OUT" en el nombre del tipo de conector — mismo criterio que
        # graph_impact.py._leer_bd().
        # Dirección por conector: leer tc.direccion, con fallback al nombre
        # del tipo de conector y nombre del conector si no está definida (Fase 2+ de
        # plan_desarrollo_hardcodes_idioma.md).
        rows_dir = Modelo._query(
            "SELECT c.id_conector, c.nombre AS conector_nombre, tc.direccion, tc.nombre AS tc_nombre "
            "FROM conector c LEFT JOIN tipo_conector tc "
            "ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE c.id_equipo=?", (id_eq,))
        dir_por_conector = {}
        for row in rows_dir:
            cid = str(row[0])
            conector_nombre = s(row[1]).upper() if row[1] else ""
            direccion = s(row[2]).upper() if row[2] else ""
            tc_nombre = s(row[3]).upper() if row[3] else ""
            if direccion == "IN":
                dir_por_conector[cid] = "IN"
            elif direccion == "OUT":
                dir_por_conector[cid] = "OUT"
            else:
                # Fallback: usar palabras clave en tc_nombre o conector_nombre
                es_entrada = any(kw in tc_nombre or kw in conector_nombre
                                for kw in ["IN", "INPUT", "ENTRADA", "ENTRY", "INGRESS"])
                es_salida = any(kw in tc_nombre or kw in conector_nombre
                               for kw in ["OUT", "OUTPUT", "SALIDA", "EXIT", "EGRESS"])
                dir_por_conector[cid] = "IN" if (es_entrada and not es_salida) else "OUT"
        p_in, p_out = [], []
        for cr in con_rows:
            cid = str(cr[0]); cnm = s(cr[1])
            if dir_por_conector.get(cid, "OUT") == "IN":
                p_in.append((cid, cnm, len(p_in)))
            else:
                p_out.append((cid, cnm, len(p_out)))

        nx, ny, has_pos = 0.0, 0.0, False
        if con_posicion:
            pos = Modelo.devolver_posicion_en_diagrama(id_eq)
            if pos and pos[0][2] is not None:
                nx, ny, has_pos = float(pos[0][2]), float(pos[0][3]), True

        n_rows = max(len(p_in), len(p_out), 1)
        alto   = self.HDR_H + self.PORT_PAD*2 + n_rows * self.PORT_H

        return {
            "id": id_eq, "nombre": nombre, "tipo": tipo, "rol_senal": rol_senal,
            "x": nx, "y": ny, "ancho": self.NODE_W, "alto": alto,
            "in": p_in, "out": p_out,
            "color": _tipo_color(tipo), "has_pos": has_pos,
            "tiene_regla": id_eq in getattr(self, "_equipos_con_regla", ()),
            "critico": id_eq in getattr(self, "_equipos_criticos", ()),
        }

    def _reconstruir_conexiones(self):
        """Recalcula self._conns a partir de todos los cables cuyos dos
        extremos son equipos actualmente presentes en self._nodos."""
        self._conns.clear()
        seen = set()
        all_cx = Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS"
        )
        # Dirección por conector, leída de tipo_conector.direccion (Fase 1/2
        # de plan_desarrollo_hardcodes_idioma.md) en vez de parsear "OUT" en
        # el texto compuesto "Extremo A: conector con tipo" de la vista.
        # Con fallback al nombre del tipo de conector y nombre del conector si direccion es NULL.
        rows_dir_all = Modelo._query(
            "SELECT c.id_conector, c.nombre AS conector_nombre, tc.direccion, tc.nombre AS tc_nombre "
            "FROM conector c LEFT JOIN tipo_conector tc "
            "ON tc.id_tipo_conector = c.id_tipo_conector")
        dir_por_conector = {}
        for row in rows_dir_all:
            cid = str(row[0])
            conector_nombre = s(row[1]).upper() if row[1] else ""
            direccion = s(row[2]).upper() if row[2] else ""
            tc_nombre = s(row[3]).upper() if row[3] else ""
            if direccion == "IN":
                dir_por_conector[cid] = "IN"
            elif direccion == "OUT":
                dir_por_conector[cid] = "OUT"
            else:
                # Fallback: usar palabras clave en tc_nombre o conector_nombre
                es_entrada = any(kw in tc_nombre or kw in conector_nombre
                                for kw in ["IN", "INPUT", "ENTRADA", "ENTRY", "INGRESS"])
                es_salida = any(kw in tc_nombre or kw in conector_nombre
                               for kw in ["OUT", "OUTPUT", "SALIDA", "EXIT", "EGRESS"])
                dir_por_conector[cid] = "IN" if (es_entrada and not es_salida) else "OUT"
        for r in all_cx:
            id_cb  = str(r[11])
            if id_cb in seen: continue
            id_ea  = str(r[10])   # connected equipment (Extremo A)
            id_eb  = str(r[9])    # queried equipment (Extremo B)
            if id_ea not in self._nodos or id_eb not in self._nodos:
                continue
            seen.add(id_cb)
            con_a_id  = str(r[14])   # id_conector Extremo A
            con_b_id  = str(r[13])   # id_conector Extremo B
            # Direction: if EA's connector is OUT → EA is source
            if dir_por_conector.get(con_a_id, "OUT") == "OUT":
                src_eq, src_con = id_ea, con_a_id
                dst_eq, dst_con = id_eb, con_b_id
            else:
                src_eq, src_con = id_eb, con_b_id
                dst_eq, dst_con = id_ea, con_a_id
            self._conns.append({
                "id": id_cb, "nombre": s(r[0]),
                "src_eq": src_eq, "src_con": src_con,
                "dst_eq": dst_eq, "dst_con": dst_con,
            })

        self._construir_conexiones_extension()

    def _extremo_real_de_cable(self, id_cable):
        """(id_equipo, id_conector, 'in'|'out') del extremo con conector
        real de id_cable, o None si sus dos puntas están sueltas (cable
        que sólo empalma con extensiones a ambos lados). Ancla el
        principio/fin de una cadena de extension_cable a un puerto real
        dibujable — mismo criterio de dirección (con el mismo fallback de
        palabras clave) que usa _reconstruir_conexiones para cables
        comunes."""
        rows = Modelo._query(
            "SELECT cx.id_conector, c.id_equipo, c.nombre, tc.direccion, tc.nombre "
            "FROM conexion cx "
            "JOIN conector c ON c.id_conector = cx.id_conector "
            "LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE cx.id_cable=? AND cx.id_conector IS NOT NULL",
            (id_cable,))
        if not rows:
            return None
        id_con, id_eq, con_nombre, direccion, tc_nombre = rows[0]
        con_nombre_s = s(con_nombre).upper() if con_nombre else ""
        direccion_s  = s(direccion).upper() if direccion else ""
        tc_nombre_s  = s(tc_nombre).upper() if tc_nombre else ""
        if direccion_s in ("IN", "OUT"):
            d = direccion_s
        else:
            es_entrada = any(kw in tc_nombre_s or kw in con_nombre_s
                              for kw in ["IN", "INPUT", "ENTRADA", "ENTRY", "INGRESS"])
            es_salida = any(kw in tc_nombre_s or kw in con_nombre_s
                             for kw in ["OUT", "OUTPUT", "SALIDA", "EXIT", "EGRESS"])
            d = "IN" if (es_entrada and not es_salida) else "OUT"
        return str(id_eq), str(id_con), ("in" if d == "IN" else "out")

    def _construir_conexiones_extension(self):
        """Arma self._conns_extension: cadenas de cable que atraviesan
        extension_cable (empalmes ficha-contra-ficha sin equipo de por
        medio — Fase 3 de plan_desarrollo_extension_cable.md), sólo para
        cadenas cuyos DOS extremos reales están visibles en self._nodos
        (mismo criterio que arriba para cables comunes: si el equipo no
        está cargado en el canvas, no se dibuja su cable).

        Capa de dibujo aparte de self._conns a propósito: impacto,
        riesgo, escenario, señal, búsqueda y exportación asumen que toda
        entrada de self._conns conecta dos nodos de self._nodos por
        conector real — meterla ahí obligaría a tocar los ~10 lugares que
        la consumen. Esta capa sólo la dibuja dibujo_diagrama_ui.py
        (_draw_conexiones_extension); todavía no participa de esos
        análisis (limitación conocida, documentada en cabledoc cambios).

        Reutiliza Modelo.resolver_cadena_extension (ya probado por
        extension_cable_ui.py, "Ver cadena completa") para el recorrido
        de la cadena, con cycle/incompleta ya resueltos ahí; acá sólo se
        agrega la resolución de ids reales (esa función sólo da nombres,
        pensada para mostrar texto) y el filtro de visibilidad."""
        self._conns_extension = []
        candidatos = Modelo._query(
            "SELECT DISTINCT id_cable FROM conexion WHERE id_conector IS NULL")
        if not candidatos:
            return

        vistos = set()
        for (id_cable,) in candidatos:
            id_cable = str(id_cable)
            if id_cable in vistos:
                continue
            cadena = Modelo.resolver_cadena_extension(id_cable)
            if not cadena or any(
                    e.get("tipo") not in ("equipo", "cable", "extension")
                    for e in cadena):
                continue  # incompleta o con ciclo: no se dibuja todavía
            if cadena[0]["tipo"] != "equipo" or cadena[-1]["tipo"] != "equipo":
                continue

            cables_ids = [str(e["id_cable"]) for e in cadena if e["tipo"] == "cable"]
            vistos.update(cables_ids)
            if not cables_ids:
                continue

            extremo_izq = self._extremo_real_de_cable(cables_ids[0])
            extremo_der = self._extremo_real_de_cable(cables_ids[-1])
            if not extremo_izq or not extremo_der:
                continue
            id_eq_a, con_a, lado_a = extremo_izq
            id_eq_b, con_b, lado_b = extremo_der
            if id_eq_a not in self._nodos or id_eq_b not in self._nodos:
                continue

            extensiones = [str(e["id_extension"]) for e in cadena
                           if e["tipo"] == "extension"]
            self._conns_extension.append({
                "id_eq_a": id_eq_a, "con_a": con_a, "lado_a": lado_a,
                "id_eq_b": id_eq_b, "con_b": con_b, "lado_b": lado_b,
                "cables": cables_ids, "extensiones": extensiones,
            })

    # ── crear conexión arrastrando de un puerto a otro (drag&drop) ──────────
    # Mismo gesto que tenía el editor clásico EditorConexiones ("modo
    # clásico" de Alta rápida de conexiones, hoy deshabilitado en el menú
    # pero conservado en el código): arrastrar de un conector libre u
    # ocupado de un equipo a un conector de OTRO equipo abre el popup
    # _DialogoCableRapido para buscar un cable existente o crear uno nuevo
    # por código. Si el destino ya tenía otra conexión, se avisa antes de
    # reemplazarla (misma UX que el editor clásico).

    def _conexion_existente_en_puerto(self, con_id):
        """Devuelve el dict de self._conns que ya usa con_id como extremo
        (src_con o dst_con), o None si el conector está libre."""
        for cn in self._conns:
            if cn["src_con"] == con_id or cn["dst_con"] == con_id:
                return cn
        return None

    def _vecinos_de_equipo(self, id_eq):
        """Devuelve (izq_ids, der_ids): sets con los id_equipo (str) ya
        conectados (por cualquier cable documentado en ambas puntas) a los
        conectores de entrada (izq) y de salida (der) del equipo id_eq, sin
        importar si ya están en el canvas o no. Mismo criterio de dirección
        (tc.direccion con fallback a palabras clave) que _construir_nodo /
        _reconstruir_conexiones. Usado por el checkbox "traer con equipos
        conectados" del panel Agregar equipo."""
        rows = Modelo._query(
            "SELECT tc1.direccion, tc1.nombre AS tc_nombre, c1.nombre AS conector_nombre, c2.id_equipo "
            "FROM conexion cn1 "
            "JOIN conector c1 ON c1.id_conector = cn1.id_conector "
            "LEFT JOIN tipo_conector tc1 ON tc1.id_tipo_conector = c1.id_tipo_conector "
            "JOIN conexion cn2 ON cn2.id_cable = cn1.id_cable "
            "  AND cn2.id_conector != cn1.id_conector "
            "JOIN conector c2 ON c2.id_conector = cn2.id_conector "
            "WHERE c1.id_equipo = ? AND c2.id_equipo != ?",
            (id_eq, id_eq),
        )
        izq_ids, der_ids = set(), set()
        for direccion, tc_nombre, conector_nombre, id_vecino in rows:
            direccion_upper = s(direccion).upper() if direccion else ""
            tc_nombre_upper = s(tc_nombre).upper() if tc_nombre else ""
            conector_nombre_upper = s(conector_nombre).upper() if conector_nombre else ""
            if direccion_upper == "IN":
                destino = izq_ids
            elif direccion_upper == "OUT":
                destino = der_ids
            else:
                es_entrada = any(kw in tc_nombre_upper or kw in conector_nombre_upper
                                for kw in ["IN", "INPUT", "ENTRADA", "ENTRY", "INGRESS"])
                es_salida = any(kw in tc_nombre_upper or kw in conector_nombre_upper
                               for kw in ["OUT", "OUTPUT", "SALIDA", "EXIT", "EGRESS"])
                destino = izq_ids if (es_entrada and not es_salida) else der_ids
            destino.add(str(id_vecino))
        return izq_ids, der_ids

    def _agregar_vecinos_de(self, id_eq):
        """Agrega al canvas (si no estaban ya) los equipos conectados a
        id_eq: los de sus conectores IN apilados a la izquierda, los de OUT
        a la derecha — mismo patrón visual que EditorConexiones._expandir_vecinos_de.
        Usado por el checkbox "traer con equipos conectados". Devuelve la
        cantidad de nodos nuevos agregados."""
        id_eq = str(id_eq)
        central = self._nodos.get(id_eq)
        if not central:
            return 0
        izq_ids, der_ids = self._vecinos_de_equipo(id_eq)
        agregados = 0

        y_izq = central["y"]
        for vid in sorted(izq_ids):
            if vid in self._nodos:
                continue
            nv = self._construir_nodo(vid, con_posicion=False)
            if not nv:
                continue
            nv["x"] = central["x"] - nv["ancho"] - 100
            nv["y"] = y_izq
            nv["has_pos"] = True
            self._nodos[vid] = nv
            if self._id_inicio is None:
                Modelo.guardar_posicion_en_diagrama(vid, nv["x"], nv["y"])
            y_izq += nv["alto"] + 30
            agregados += 1

        y_der = central["y"]
        for vid in sorted(der_ids):
            if vid in self._nodos:
                continue
            nv = self._construir_nodo(vid, con_posicion=False)
            if not nv:
                continue
            nv["x"] = central["x"] + central["ancho"] + 100
            nv["y"] = y_der
            nv["has_pos"] = True
            self._nodos[vid] = nv
            if self._id_inicio is None:
                Modelo.guardar_posicion_en_diagrama(vid, nv["x"], nv["y"])
            y_der += nv["alto"] + 30
            agregados += 1

        return agregados

    def _agregar_equipo_por_busqueda(self, id_eq, wx=None, wy=None):
        """Agrega el equipo id_eq al canvas como nodo nuevo (o simplemente
        lo centra en la vista si ya estaba). Usado tanto por el drag&drop
        desde el panel lateral como por el diálogo "➕ Agregar equipo al
        diagrama…" del menú Buscar.

        Si el checkbox "traer con equipos conectados" está tildado (por
        defecto lo está), además del equipo elegido se agregan al canvas
        los equipos ya conectados a sus conectores IN y OUT (ver
        _agregar_vecinos_de). Sólo aplica cuando el equipo se agrega por
        primera vez, no cuando ya estaba en el canvas."""
        id_eq = str(id_eq)
        ya_estaba = id_eq in self._nodos
        if ya_estaba:
            nodo = self._nodos[id_eq]
        else:
            nodo = self._construir_nodo(id_eq, con_posicion=False)
            if not nodo:
                self._status(_("Equipo no encontrado."))
                return
            if wx is None or wy is None:
                alloc = self._da.get_allocation()
                wx, wy = self._s2w(alloc.width / 2, alloc.height / 2)
            nodo["x"] = wx - nodo["ancho"] / 2
            nodo["y"] = wy - nodo["alto"] / 2
            nodo["has_pos"] = True
            self._nodos[id_eq] = nodo
            if self._id_inicio is None:
                Modelo.guardar_posicion_en_diagrama(id_eq, nodo["x"], nodo["y"])
            agregados_extra = 0
            if getattr(self, "_chk_traer_conectados", None) is not None \
                    and self._chk_traer_conectados.get_active():
                agregados_extra = self._agregar_vecinos_de(id_eq)
            self._reconstruir_conexiones()
            if agregados_extra:
                self._status(
                    _("Equipo agregado: ") + nodo["nombre"]
                    + f" (+{agregados_extra} " + _("conectado(s)") + ")")
            else:
                self._status(_("Equipo agregado: ") + nodo["nombre"])
        self._sel_id  = id_eq
        self._sel_ids = {id_eq}
        self._lbl_sel.set_text(f"{nodo['nombre']}   [{nodo['tipo']}]   id={id_eq}")
        self._poblar_lista_agregar(self._e_busq_agregar.get_text())
        self._da.queue_draw()

    def _agregar_equipo_via_dialogo(self):
        """Entrada del menú Buscar: abre un selector modal de equipos y
        agrega el elegido al canvas (mismo destino que arrastrarlo desde
        el panel lateral)."""
        from cabledoc import EquiposListado
        selector = EquiposListado(parent=self, modo_seleccion=True)
        if selector.run() == Gtk.ResponseType.OK:
            id_eq = selector.resultado_id
            selector.destroy()
            self._agregar_equipo_por_busqueda(id_eq)
        else:
            selector.destroy()


