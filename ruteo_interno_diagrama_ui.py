"""RuteoInternoMixin — conexión interna de un equipo seleccionado en el diagrama (bypass de patchera, distribución DDV, ruteo de matriz).

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
from pantallas_comunes import s, PALETA


class RuteoInternoMixin:
    def _toggle_conexion_interna(self):
        """Botón toolbar: activa/desactiva la vista de conexión interna del
        equipo actualmente seleccionado (self._sel_id). Soporta:
          • PATCHERA → bypass BACK_ENTRADA↔BACK_SALIDA / FRONT_DERIVACION / FRONT_INSERCION
          • DDV             → distribución IN → todos los OUT con cable
        """
        if self._conex_interna_activo:
            self._conex_interna_activo = False
            self._conex_interna_id     = None
            self._conex_interna_estado = None
            self._da.queue_draw()
            return

        if not self._sel_id or self._sel_id not in self._nodos:
            self._status("Seleccioná un equipo (módulo patchera o DDV) para ver su conexión interna.")
            return

        nodo = self._nodos[self._sel_id]
        tipo = s(nodo.get("tipo")).strip().upper()

        # Fase 6 de plan_desarrollo_hardcodes_idioma.md: se detecta el caso
        # patchera por rol_senal='PATCHERA' (columna dedicada) en vez de
        # comparar tipo_equipo.nombre == "MODULO PATCHERA" — con fallback
        # al nombre si el equipo es de un tipo creado antes de la migración
        # y todavía no tiene rol_senal asignado.
        es_patchera = (nodo.get("rol_senal") == "PATCHERA") or (
            nodo.get("rol_senal") is None and tipo == "MODULO PATCHERA")

        if es_patchera:
            estado = self._calc_conexion_interna(nodo)
            if estado is None:
                self._status(
                    f"«{nodo['nombre']}»: no tiene las 4 funciones de "
                    "patchera asignadas (Entrada/Salida traseras y "
                    "Derivación/Inserción frontales) — asignalas desde la "
                    "ficha del equipo.")
                return
            estado["modo"] = "patchera"
            if not estado["derivacion_usada"] and not estado["insercion_usada"]:
                resumen = "bypass directo entrada↔salida (sin cables al frente)"
            elif estado["derivacion_usada"] and estado["insercion_usada"]:
                resumen = "loop externo: derivación afuera e inserción entrando"
            elif estado["derivacion_usada"]:
                resumen = "interrumpido: sale por derivación, la salida trasera queda sin señal"
            else:
                resumen = "interrumpido: entra por inserción, la entrada trasera queda sin destino"

        elif (nodo.get("rol_senal") == "DISTRIBUIDOR") or (
                nodo.get("rol_senal") is None and tipo == "DDV"):
            estado = self._calc_conexion_interna_ddv(nodo)
            if estado is None:
                self._status(f"«{nodo['nombre']}»: no se encontró el puerto IN.")
                return
            estado["modo"] = "ddv"
            n = len(estado["out_ports"])
            resumen = (f"distribución 1→{n}: IN replicado en {n} salida(s) con cable"
                       if n else "IN sin salidas con cable conectado")

        elif (nodo.get("rol_senal") == "ENRUTADOR") or (
                nodo.get("rol_senal") is None and tipo == "MATRIZ"):
            if not Modelo.existe_configuracion_matriz(nodo["id"]):
                if not self._editar_ruteo_matriz(nodo):
                    self._status(f"«{nodo['nombre']}»: configuración de ruteo cancelada.")
                    return
            estado = self._calc_conexion_interna_matriz(nodo)
            if not estado["grupos"]:
                self._status(f"«{nodo['nombre']}»: sin salidas con entrada asignada.")
                return
            estado["modo"] = "matriz"
            n_rutas = sum(len(g["out_ports"]) for g in estado["grupos"])
            resumen = (f"ruteo interno: {n_rutas} salida(s) activa(s) "
                       f"en {len(estado['grupos'])} entrada(s)")

        else:
            self._status(f"«{nodo['nombre']}» no soporta conexión interna "
                          "(solo MODULO PATCHERA, DDV o MATRIZ).")
            return

        self._conex_interna_id     = self._sel_id
        self._conex_interna_estado = estado
        self._conex_interna_activo = True
        self._status(f"«{nodo['nombre']}» — {resumen}")
        self._da.queue_draw()

    def _editar_ruteo_matriz_click(self):
        """Botón toolbar '✏️ Editar matriz': permite reconfigurar el ruteo
        aunque ya exista una configuración guardada."""
        if not self._sel_id or self._sel_id not in self._nodos:
            self._status("Seleccioná una matriz para editar su ruteo.")
            return
        nodo = self._nodos[self._sel_id]
        # Fase 6 de plan_desarrollo_hardcodes_idioma.md: se admite cualquier
        # equipo con rol_senal='ENRUTADOR' (columna dedicada), no sólo el
        # que se llame literalmente "MATRIZ" — con fallback al nombre para
        # tipos creados antes de la migración y todavía sin rol_senal.
        es_enrutador = (nodo.get("rol_senal") == "ENRUTADOR") or (
            nodo.get("rol_senal") is None and s(nodo.get("tipo")).strip().upper() == "MATRIZ")
        if not es_enrutador:
            self._status(f"«{nodo['nombre']}» no es una matriz.")
            return
        if self._editar_ruteo_matriz(nodo):
            if self._conex_interna_activo and self._conex_interna_id == self._sel_id:
                estado = self._calc_conexion_interna_matriz(nodo)
                estado["modo"] = "matriz"
                self._conex_interna_estado = estado
            self._status(f"«{nodo['nombre']}»: ruteo guardado.")
            self._da.queue_draw()

    def _editar_ruteo_matriz(self, nodo):
        """Abre el diálogo de asignación entrada→salida de una matriz y, si
        el usuario confirma, guarda el ruteo en la base. Devuelve True si
        se guardó, False si se canceló."""
        mapping_actual = Modelo.devolver_ruteo_matriz(nodo["id"])
        from pantallas_avanzadas import _DialogoRuteoMatriz  # import diferido: evita ciclo con pantallas_avanzadas.py
        dlg = _DialogoRuteoMatriz(nodo, mapping_actual, parent=self)
        ok = (dlg.run() == Gtk.ResponseType.OK)
        if ok:
            Modelo.guardar_ruteo_matriz(nodo["id"], dlg.resultado_mapping)
        dlg.destroy()
        return ok

    def _calc_conexion_interna_matriz(self, nodo):
        """Para una matriz (N entradas x N salidas, ej. KUMO 1616): carga el
        ruteo guardado y agrupa las salidas por entrada compartida (mismo
        color de línea para las salidas de una misma entrada).
        Devuelve {"grupos": [{"in_port":, "out_ports":[...], "color":}, ...]}
        """
        mapping = Modelo.devolver_ruteo_matriz(nodo["id"])   # {id_out: id_in|None}

        pos_in  = {cid: (cid, "in")  for cid, _, _ in nodo["in"]}
        pos_out = {cid: (cid, "out") for cid, _, _ in nodo["out"]}

        por_entrada = {}   # id_in -> [id_out, ...]
        for id_out, id_in in mapping.items():
            if not id_in or id_in not in pos_in or id_out not in pos_out:
                continue
            por_entrada.setdefault(id_in, []).append(id_out)

        grupos = []
        for i, (id_in, salidas) in enumerate(por_entrada.items()):
            grupos.append({
                "in_port":   pos_in[id_in],
                "out_ports": [pos_out[o] for o in salidas],
                "color":     PALETA[i % len(PALETA)],
            })
        return {"grupos": grupos}

    def _calc_conexion_interna(self, nodo):
        """Ubica los 4 puertos de función (BACK_ENTRADA/BACK_SALIDA/
        FRONT_DERIVACION/FRONT_INSERCION) del nodo (patchera full-normal) y
        determina, según qué cables hay realmente en la tabla `conexion`
        para FRONT_DERIVACION/FRONT_INSERCION, qué tramos del bypass
        interno siguen activos.
        Devuelve dict con los puertos ubicados y la lista de tramos
        activos, o None si el equipo no tiene las 4 funciones asignadas.
        Fase C de plan_desarrollo_funcion_patchera.md: identifica los 4
        puertos EXCLUSIVAMENTE por conector.id_funcion_patchera — se quitó
        el fallback a prefijo de nombre que tenía antes. Un equipo sin las
        4 funciones cargadas (ej. un patch module recién dado de alta,
        antes de pasar por la Fase B) devuelve None — aparece en
        Modelo.listar_patcheras_sin_funcion_completa para completarlo a
        mano, nunca se adivina desde el nombre del conector.
        """
        ids_todos = [cid for _side, lst in (("in", nodo["in"]), ("out", nodo["out"]))
                     for cid, _cnm, _ in lst]
        clave_por_id = {}
        if ids_todos:
            placeholders = ",".join("?" * len(ids_todos))
            clave_por_id = {str(r[0]): r[1] for r in Modelo._query(
                f"SELECT c.id_conector, fp.clave FROM conector c "
                f"LEFT JOIN funcion_patchera fp "
                f"  ON fp.id_funcion_patchera = c.id_funcion_patchera "
                f"WHERE c.id_conector IN ({placeholders})", ids_todos)}

        FUNCIONES = ("BACK_ENTRADA", "BACK_SALIDA",
                    "FRONT_DERIVACION", "FRONT_INSERCION")
        puertos = {}
        for side, lst in (("in", nodo["in"]), ("out", nodo["out"])):
            for cid, cnm, _ in lst:
                clave = clave_por_id.get(str(cid))
                if clave in FUNCIONES and clave not in puertos:
                    puertos[clave] = (cid, side)

        if any(f not in puertos for f in FUNCIONES):
            return None

        def _tiene_cable(id_conector):
            r = Modelo._query(
                "SELECT COUNT(*) FROM conexion WHERE id_conector=?",
                (id_conector,))
            return bool(r and r[0][0])

        derivacion_usada = _tiene_cable(puertos["FRONT_DERIVACION"][0])
        insercion_usada = _tiene_cable(puertos["FRONT_INSERCION"][0])

        tramos = []
        if not derivacion_usada and not insercion_usada:
            tramos.append(("BACK_ENTRADA", "BACK_SALIDA"))
        if derivacion_usada:
            tramos.append(("BACK_ENTRADA", "FRONT_DERIVACION"))
        if insercion_usada:
            tramos.append(("FRONT_INSERCION", "BACK_SALIDA"))

        muerto = None
        if derivacion_usada and not insercion_usada:
            muerto = "BACK_SALIDA"
        elif insercion_usada and not derivacion_usada:
            muerto = "BACK_ENTRADA"

        return {
            "puertos": puertos,
            "derivacion_usada": derivacion_usada,
            "insercion_usada": insercion_usada,
            "tramos": tramos,
            "muerto": muerto,
        }

    def _calc_conexion_interna_ddv(self, nodo):
        """Para un distribuidor de video (tipo DDV): ubica el único puerto
        IN y todos los puertos OUT que tengan un cable conectado. La señal
        que entra por IN se replica en cada una de esas salidas.
        Devuelve dict con el puerto IN y la lista de puertos OUT activos,
        o None si el equipo no tiene puerto IN.
        """
        if not nodo["in"]:
            return None
        cid_in, _, _ = nodo["in"][0]
        in_port = (cid_in, "in")

        def _tiene_cable(id_conector):
            r = Modelo._query(
                "SELECT COUNT(*) FROM conexion WHERE id_conector=?",
                (id_conector,))
            return bool(r and r[0][0])

        out_ports = [
            (cid, "out") for cid, _, _ in nodo["out"] if _tiene_cable(cid)
        ]

        return {
            "in_port":   in_port,
            "out_ports": out_ports,
        }


