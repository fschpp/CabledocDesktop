"""
graph_impact.py — Análisis de impacto en la cadena de transmisión para CableDoc
=================================================================================
Usa GraphQLite (graphqlite.graph.Graph) para modelar el grafo dirigido de señal:
    Equipo-OUT --[CABLE]--> Equipo-IN

Requiere:
    pip install graphqlite

API pública:
    analyzer = GraphImpactAnalyzer(db_path)
    analyzer.construir_grafo()          # carga BD → Graph en :memory:  (~75 ms)
    r = analyzer.simular_desconexion("42")   # BFS parcial              (~5-25 ms)
    r.equipos_impactados  → set[str]    ids de equipos sin señal
    r.cables_impactados   → set[str]    ids de cables sin señal
    r.hay_impacto         → bool

Fuentes de señal:
    Unión de (1) equipos con conector de tipo REFOUT (generan referencia,
    ej. generadores de sync/wordclock)  +  (2) nodos sin aristas entrantes
    en el grafo.  Se pre-calculan en construir_grafo() para que cada
    simulación solo haga BFS sobre las fuentes afectadas por el cable cortado.
"""

import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from typing import Optional

# ── Redirigir archivos temporales de SQLite a una carpeta local ────────────
# Por defecto, SQLite (y por lo tanto GraphQLite) escribe las tablas
# temporales que no entran en memoria (por ejemplo al correr caminos de
# largo variable como [:CABLE*1..8], que pueden generar resultados
# intermedios enormes) en la carpeta temporal del sistema operativo, que en
# Linux suele ser /tmp — a veces un tmpfs con tamaño limitado por RAM y NO
# por el disco real. Si esa carpeta se llena, SQLite falla con
# "database or disk is full" aunque el disco donde vive la app tenga
# espacio de sobra. Acá la redirigimos a una carpeta local, en el mismo
# disco que db.db, antes de que se abra ninguna conexión SQLite (incluida
# la de GraphQLite).
_LOCAL_TMP_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tmp_sqlite")

try:
    os.makedirs(_LOCAL_TMP_DIR, exist_ok=True)

    # Limpieza de arranque: si una sesión anterior se cortó a mitad de una
    # consulta pesada, puede haber dejado archivos temporales enormes sin
    # borrar. Los eliminamos al iniciar (son siempre datos de trabajo
    # descartables, nunca información persistente de la app).
    for _f in os.listdir(_LOCAL_TMP_DIR):
        try:
            os.remove(os.path.join(_LOCAL_TMP_DIR, _f))
        except OSError:
            pass

    os.environ["SQLITE_TMPDIR"] = _LOCAL_TMP_DIR   # el que lee SQLite en Unix
    os.environ["TMPDIR"]        = _LOCAL_TMP_DIR   # fallback genérico Unix
    os.environ["TEMP"]          = _LOCAL_TMP_DIR   # Windows
    os.environ["TMP"]           = _LOCAL_TMP_DIR   # Windows
    tempfile.tempdir            = _LOCAL_TMP_DIR   # tempfile.* de Python
except Exception:
    # Si no se puede crear/usar la carpeta local (permisos, disco de solo
    # lectura, etc.), seguimos con el comportamiento por defecto del
    # sistema en vez de romper el arranque de la app.
    pass

from graphqlite.graph import Graph


# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoImpacto:
    cable_desconectado: str          # id_cable (str)
    nombre_cable:       str = ""
    equipos_con_senal:  set = field(default_factory=set)   # str ids
    equipos_impactados: set = field(default_factory=set)   # str ids
    cables_impactados:  set = field(default_factory=set)   # str ids
    # {id_equipo: texto} — sólo para equipos cuya propia regla lógica (AND/OR,
    # ver Modelo.asegurar_tablas_regla_logica) dejó de cumplirse a raíz de
    # ESTA desconexión (no simplemente "está aguas abajo de algo cortado").
    causas_regla:       dict = field(default_factory=dict)
    # plan_estado_senal_y_linaje.md, Función 1 — bugfix 2026-08-24:
    # conectores puntuales (entrada culpable + salida gobernada) de
    # cada regla lógica que se rompió por este cálculo — más preciso
    # que barrer TODO el equipo de causas_regla.keys() (que incluiría
    # entradas/salidas ajenas a la regla, con señal real intacta).
    conectores_regla_caida: set = field(default_factory=set)   # str ids

    @property
    def hay_impacto(self) -> bool:
        return bool(self.equipos_impactados or self.cables_impactados)


@dataclass
class ResultadoEscenario:
    """Resultado de simular_escenario(): combinación arbitraria de cables
    cortados + equipos fallados + conexiones virtuales (reconexión de
    emergencia), evaluada en un solo cálculo — ver GraphImpactAnalyzer.
    simular_escenario() y escenario_engine.py.

    Guarda tanto el estado "después" (con la reconexión virtual aplicada,
    si la hay) como el "antes" (sólo las fallas, sin reconexión), para que
    la UI pueda mostrar el comparativo de la sección 7 del documento de
    inspiración ("Consumidores afectados: 18 → 2. Recuperados: 16")."""
    cables_cortados:      set = field(default_factory=set)   # str ids
    equipos_fallados:      set = field(default_factory=set)   # str ids
    # [(id_conector_a, id_conector_b), ...] tal como se pidieron
    conexiones_virtuales:  list = field(default_factory=list)

    # Estado "después" (fallas + reconexión virtual aplicada)
    equipos_con_senal:     set = field(default_factory=set)
    equipos_impactados:    set = field(default_factory=set)
    cables_impactados:     set = field(default_factory=set)
    causas_regla:          dict = field(default_factory=dict)
    # plan_estado_senal_y_linaje.md, Función 1 — bugfix 2026-08-24:
    # conectores puntuales (entrada culpable + salida gobernada) de
    # cada regla lógica que se rompió por este cálculo — más preciso
    # que barrer TODO el equipo de causas_regla.keys() (que incluiría
    # entradas/salidas ajenas a la regla, con señal real intacta).
    conectores_regla_caida: set = field(default_factory=set)   # str ids

    # Estado "antes" (sólo las fallas, SIN la reconexión virtual) — para
    # el comparativo antes/después.
    equipos_impactados_sin_reconexion: set = field(default_factory=set)
    # Equipos que estaban impactados sin reconexión y dejaron de estarlo
    # gracias a alguna conexión virtual del escenario.
    equipos_recuperados:   set = field(default_factory=set)

    # [(id_conector_a, id_conector_b), ...] de conexiones virtuales pedidas
    # cuyo conector no se pudo resolver a un nodo del grafo actual (por
    # ejemplo, un id_conector que ya no existe) — para que la UI pueda
    # avisar sin que la simulación entera falle.
    conectores_invalidos:  list = field(default_factory=list)

    @property
    def hay_impacto(self) -> bool:
        return bool(self.equipos_impactados or self.cables_impactados)


@dataclass
class ResultadoImpactoEquipo:
    """Resultado de simular_falla_equipo(): qué pasa si el EQUIPO completo
    (no un cable puntual) deja de funcionar — usado para el factor de
    Impacto (I) del Índice de Riesgo de Falla."""
    equipo_id:                str
    nombre_equipo:             str = ""
    equipos_impactados:        set = field(default_factory=set)   # str ids, sin contar al propio equipo
    puntos_finales_impactados: set = field(default_factory=set)   # subset de equipos_impactados que son hojas
    causas_regla:              dict = field(default_factory=dict)  # ver ResultadoImpacto.causas_regla
    # Agregado para plan_simular_remocion_cadena.md: cables cuyos extremos
    # quedan en equipos_impactados (mismo criterio que ResultadoImpacto.
    # cables_impactados). No incluye los propios cables del equipo que
    # falló. Antes de este agregado el dataclass no traía cables — los
    # llamados existentes (risk_engine.py) siguen funcionando igual porque
    # el campo tiene default vacío.
    cables_impactados:        set = field(default_factory=set)   # str ids
    # plan_estado_senal_y_linaje.md, Función 1 — bugfix 2026-08-24:
    # conectores puntuales (entrada culpable + salida gobernada) de
    # cada regla lógica que se rompió por este cálculo — más preciso
    # que barrer TODO el equipo de causas_regla.keys() (que incluiría
    # entradas/salidas ajenas a la regla, con señal real intacta).
    conectores_regla_caida: set = field(default_factory=set)   # str ids

    @property
    def hay_impacto(self) -> bool:
        return bool(self.equipos_impactados)


# ─────────────────────────────────────────────────────────────────────────────

class GraphImpactAnalyzer:
    """
    Motor de análisis de impacto sobre el grafo de señal de CableDoc.

    Ciclo de vida:
        1.  construir_grafo()  — llamar al abrir DiagramaConexiones (~75 ms)
        2.  simular_desconexion(cable_id)  — por cada análisis (~5-25 ms)
        3.  invalidar()  — si la BD cambia, fuerza reconstrucción en el paso 1

    Internamente usa graphqlite.graph.Graph (in-memory SQLite + extensión C).
    La simulación es no destructiva: se elimina el edge, se corre BFS parcial
    sobre las fuentes afectadas, y se restaura el edge antes de retornar.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._g: Optional[Graph] = None

        # Mapas str-id → nombre (para la UI)
        self._equipos: dict[str, str] = {}
        self._cables:  dict[str, str] = {}

        # cable_str → (src_str, dst_str)
        self._cable_endpoints: dict[str, tuple[str, str]] = {}

        # Fuentes de señal (REFOUT + nodos raíz)
        self._fuentes: set[str] = set()

        # Semillas (nodos) de todas las fuentes activas juntas — se usa un
        # único cálculo global de alcanzabilidad (no uno por fuente), ver
        # el comentario en construir_grafo().
        self._semillas_globales: set = set()

        # Alcanzabilidad global (unión de todos)
        self._alcanzables_ok: set[str] = set()

        # Equipos de tipo FANTASMA (placeholders, no cuentan como equipo
        # real a proteger — ver _leer_bd)
        self._fantasma: set[str] = set()

        # Nodos de paso "EXT:<id_extension>" (empalmes ficha-contra-ficha
        # sin equipo — Fase 3 de plan_desarrollo_extension_cable.md, ver
        # _leer_bd). No son equipos: se excluyen de equipos_impactados
        # igual que self._fantasma, pero SÍ participan de la detección de
        # cables_impactados (ver simular_desconexion/simular_falla_equipo/
        # simular_escenario) porque, a diferencia de un FANTASMA, perder
        # señal en un empalme sí es información real para el cable físico
        # de cada lado.
        self._ext_nodos: set[str] = set()
        self._nombres_extension: dict[str, str] = {}

        # ── Ruteo interno de equipos tipo MATRIZ ────────────────────────────
        # Un equipo MATRIZ con configuración guardada (ver Modelo.
        # guardar_ruteo_matriz / botón "Editar matriz") no se modela como un
        # único nodo "pasa todo" en el grafo: cada conector de entrada y
        # cada conector de salida involucrados en el ruteo se modelan como
        # nodos propios ("MI:<id_conector>" / "MO:<id_conector>"), unidos
        # por una arista interna MI→MO sólo cuando esa salida tiene esa
        # entrada asignada. Así, cortar el cable que llega a una entrada
        # sólo afecta a las salidas realmente ruteadas desde esa entrada.
        # Equipos MATRIZ sin configuración guardada (existe_configuracion_
        # matriz=False) NO aparecen en este diccionario y siguen usando el
        # nodo único de equipo (comportamiento anterior, sin filtrar).
        self._matriz_ruteo: dict[str, dict[str, Optional[str]]] = {}

        # {(id_equipo, id_conector): "MI:x"|"MO:x"} — a qué nodo del grafo
        # se redirige un cable que toca ese conector de un equipo MATRIZ
        # configurado. Los conectores que no participan del ruteo (REF,
        # RS422, ETHERNET, USB, etc.) no están acá y siguen resolviendo al
        # nodo de equipo de siempre.
        self._conector_a_nodo: dict[tuple[str, str], str] = {}

        # Cable id → (nodo_src, nodo_dst) tal como existen en el grafo
        # interno (puede diferir de self._cable_endpoints, que siempre es a
        # nivel equipo y se mantiene para la API pública / CSV / etc.)
        self._cable_graph_endpoints: dict[str, tuple[str, str]] = {}

        # Nodo de grafo "MI:x"/"MO:x" → id_equipo dueño (para traducir
        # conjuntos de nodos alcanzables de vuelta a equipos).
        self._node_equipo: dict[str, str] = {}

        # id_equipo → conjunto de nodos de grafo que lo representan
        # ({id_equipo} para equipos normales; {"MI:..","MO:.."} para una
        # MATRIZ configurada). Usado como semillas de BFS / puntos de corte.
        self._equipo_nodos: dict[str, set] = {}

        # ── Reglas lógicas de equipo (AND / OR) ─────────────────────────────
        # Generaliza lo que originalmente era un caso hardcodeado ("DSK
        # necesita todas sus entradas salvo BKGD B") a cualquier tipo de
        # equipo. No hay ningún tratamiento especial para "DSK" en este
        # archivo ni en ningún otro — es sólo el ejemplo que motivó el
        # diseño. Las reglas se cargan por equipo o por tipo_equipo desde
        # la UI ("🔀 Reglas lógicas" en la ficha de equipo); si no se
        # configuró ninguna, el equipo se comporta como nodo único (sin
        # condición AND/OR), igual que cualquier otro equipo sin reglas.
        # Una regla AND requiere que TODOS sus miembros tengan señal; una
        # OR, que ALGUNO la tenga. Esto no es expresable como simple
        # alcanzabilidad de grafo (que es "OR global": con que llegue una
        # señal por cualquier lado, el nodo queda "vivo").
        #
        # Se modela con "compuertas": cada conector miembro de una regla es
        # su propio nodo de puerto ("RI:<id_conector>", ver construir_grafo),
        # y las salidas que gobierna se redirigen a un nodo-compuerta único
        # ("RG:<id_regla>"). self._compuertas mapea nodo-compuerta →
        # (operador, lista de nodos miembro) — ver _alcanzables_desde() para
        # cómo se evalúa AND/OR y se resuelven cadenas de reglas.
        self._compuertas: dict[str, tuple[str, list[str]]] = {}
        self._compuerta_salidas: dict[str, set] = {}

        # Espejo en Python puro de los edges del grafo (cables + rutas
        # internas de MATRIZ), usado por _alcanzables_desde() para poder
        # aplicar las reglas lógicas durante el recorrido — GraphQLite no soporta
        # condiciones AND, sólo alcanzabilidad simple.
        self._adj: dict[str, list[str]] = {}

        # id_conector → nombre (para armar explicaciones legibles de causa
        # cuando una regla lógica es la que corta un equipo, ver
        # _explicar_compuertas_caidas()).
        self._nombre_conector: dict[str, str] = {}

        # ── Usados por simular_escenario() (conexiones virtuales) ──────────
        # id_conector → id_equipo dueño / id_conector → nombre de tipo de
        # conector (p.ej. "OUT", "IN"), para poder resolver un id_conector
        # arbitrario (elegido por arrastre en la UI de escenario) al nodo
        # de grafo correspondiente y para inferir la dirección de la
        # conexión virtual. No se usa en ningún otro cálculo existente.
        self._conector_equipo: dict[str, str] = {}
        self._conector_tipo:   dict[str, str] = {}
        # id_conector -> 'IN'/'OUT', leído de tipo_conector.direccion (Fase 1/2
        # de plan_desarrollo_hardcodes_idioma.md). Se usa en simular_escenario()
        # en vez de parsear "OUT" en el nombre del tipo de conector.
        self._conector_direccion: dict[str, str] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Construcción del grafo
    # ──────────────────────────────────────────────────────────────────────────

    def construir_grafo(self) -> None:
        """
        Lee la BD de CableDoc, construye el grafo en GraphQLite (:memory:)
        y pre-calcula el BFS de estado normal desde cada fuente de señal.

        Tiempo típico: ~75 ms (10 ms inserción + 65 ms BFS inicial).
        """
        (equipos_raw, cables_raw, fuentes_refout,
         equipos_fantasma, matriz_ruteo, reglas_por_equipo,
         salidas_por_equipo, nombre_por_conector,
         conector_equipo, conector_tipo,
         conector_direccion, patchera_puertos) = self._leer_bd()
        self._nombre_conector = nombre_por_conector
        self._conector_equipo = conector_equipo
        self._conector_tipo   = conector_tipo
        self._conector_direccion = conector_direccion

        # ── Mapas auxiliares ─────────────────────────────────────────────────
        self._equipos = {str(r["id"]): r["nombre"] for r in equipos_raw}
        self._fantasma = equipos_fantasma
        # self._nombres_extension ya lo dejó armado _leer_bd() (nodos de
        # paso "EXT:<id_extension>" — Fase 3 de plan_desarrollo_extension_
        # cable.md). No son equipos: no van a self._equipos (eso los haría
        # candidatos a "fuente raíz" al no tener entrante propio).
        self._ext_nodos = set(self._nombres_extension.keys())
        self._cables  = {r["id_cable"]: r["nombre"] for r in cables_raw}
        self._cable_endpoints = {r["id_cable"]: (r["src"], r["dst"])
                                  for r in cables_raw}
        # plan_estado_senal_y_linaje.md, Función 1 — bugfix del
        # 2026-08-24 (reporte visual sobre un caso real): equipos_impactados
        # NO incluye al equipo cuya propia regla lógica de salida se rompió
        # (sigue siendo "alcanzable" por sus otras entradas — sólo deja de
        # PROPAGAR hacia adelante), así que el conector de entrada exacto
        # que causó el corte, y el propio conector de salida gobernado por
        # la regla, quedaban afuera de cualquier cruce por
        # equipos_impactados. Este mapa permite ubicar los DOS conectores
        # puntuales de un cable cortado (independiente de si sus equipos
        # terminan en equipos_impactados o no) — ver conectores_del_cable().
        self._cable_endpoints_conector = {
            r["id_cable"]: (r["src_conector"], r["dst_conector"])
            for r in cables_raw
        }

        # Un equipo con regla lógica propia (reglas_por_equipo, AND/OR —
        # ver el bloque más abajo) queda modelado por esa regla, no por
        # ruteo de matriz: si el mismo equipo tuviera ADEMÁS filas en
        # matriz_ruteo (normalmente datos viejos/residuales de un ruteo
        # cargado antes de definir la regla, o de un cambio de rol_senal
        # posterior), ambos bloques compiten por el MISMO conector — el de
        # matriz gana en el conector de entrada ("MI:x") pero el de reglas
        # gana en el de salida (que se sobreescribe sin condición más
        # abajo), dejando el nodo-compuerta ("RG:x") con un miembro
        # ("RI:x") que ningún cable alimenta realmente. El síntoma es
        # silencioso: el equipo queda "sin señal" siempre, aunque su
        # entrada real sí la tenga, y el análisis de impacto no encuentra
        # ningún corte que cambie nada aguas abajo (todo ya figuraba sin
        # señal de antes). Se resuelve dando prioridad a la regla propia:
        # se ignora el matriz_ruteo de cualquier equipo que ya tenga
        # reglas_por_equipo, igual que un equipo con regla propia ya
        # ignora las reglas de su tipo_equipo (ver comentario en _leer_bd).
        matriz_ruteo = {eq_mtz: ruteo for eq_mtz, ruteo in matriz_ruteo.items()
                         if eq_mtz not in reglas_por_equipo}
        self._matriz_ruteo = matriz_ruteo

        # ── Nodos de puerto para equipos MATRIZ configurados ────────────────
        # Por cada MATRIZ con ruteo guardado: un nodo "MO:<conector>" por
        # cada salida involucrada y un nodo "MI:<conector>" por cada entrada
        # realmente asignada a alguna salida. self._conector_a_nodo permite
        # redirigir los cables que tocan esos conectores puntuales; el resto
        # de los conectores del equipo (REF, RS422, ETHERNET, USB, etc.)
        # sigue resolviendo al nodo de equipo de siempre.
        self._conector_a_nodo = {}
        self._node_equipo = {}
        self._equipo_nodos = {}
        puertos_matriz: list[tuple[str, dict, str]] = []
        aristas_ruteo:  list[tuple[str, str, dict, str]] = []

        for eq_mtz, ruteo in matriz_ruteo.items():
            nombre_mtz = self._equipos.get(eq_mtz, eq_mtz)
            nodos_de_este_equipo = set()

            for id_salida, id_entrada in ruteo.items():
                nodo_out = f"MO:{id_salida}"
                self._conector_a_nodo[(eq_mtz, id_salida)] = nodo_out
                self._node_equipo[nodo_out] = eq_mtz
                nodos_de_este_equipo.add(nodo_out)
                puertos_matriz.append(
                    (nodo_out, {"nombre": f"{nombre_mtz} OUT {id_salida}"}, "PuertoMatriz"))

                if id_entrada is not None:
                    nodo_in = f"MI:{id_entrada}"
                    if (eq_mtz, id_entrada) not in self._conector_a_nodo:
                        self._conector_a_nodo[(eq_mtz, id_entrada)] = nodo_in
                        self._node_equipo[nodo_in] = eq_mtz
                        nodos_de_este_equipo.add(nodo_in)
                        puertos_matriz.append(
                            (nodo_in, {"nombre": f"{nombre_mtz} IN {id_entrada}"}, "PuertoMatriz"))
                    aristas_ruteo.append(
                        (nodo_in, nodo_out, {"equipo": eq_mtz}, "MATRIZ_ROUTE"))

            if nodos_de_este_equipo:
                self._equipo_nodos[eq_mtz] = nodos_de_este_equipo

        for eq_id in self._equipos:
            self._equipo_nodos.setdefault(eq_id, {eq_id})

        # ── Nodos de puerto + compuerta AND/OR para reglas lógicas de equipo ──
        # Generaliza lo que antes era sólo para DSK. Cada conector MIEMBRO
        # de una regla se modela como su propio nodo "RI:<conector>" (Rule
        # Input) — así, cortar el cable puntual de ESE conector no se
        # "disimula" porque el equipo que lo alimenta sigue vivo por otro
        # lado. Conectores que NO son miembro de ninguna regla (excepciones
        # implícitas, ej. el BKGD B del caso DSK) simplemente no se
        # redirigen — quedan cayendo en el nodo de equipo de siempre, que
        # es inofensivo mientras todas sus salidas estén cubiertas por
        # alguna regla (ver más abajo). El resultado de cada regla es un
        # único nodo-compuerta ("RG:<id_regla>", o "RG:<id_regla>:<equipo>"
        # para una instancia de regla de tipo_equipo), que sólo se activa
        # (self._compuertas / _alcanzables_desde) cuando se cumple su
        # condición AND/OR. Las salidas gobernadas del equipo se redirigen
        # ahí; si la regla no especificó salidas puntuales, gobierna TODAS
        # las salidas del equipo (default).
        self._compuertas = {}
        # plan_estado_senal_y_linaje.md, Función 1 — bugfix 2026-08-24:
        # conectores de SALIDA puntuales que gobierna cada compuerta, para
        # poder marcar como "caído" sólo esa/s salida/s (y la entrada
        # culpable) cuando la regla se rompe — NO el equipo entero, que
        # normalmente tiene otras entradas/salidas ajenas a esta regla con
        # señal real intacta (ver _explicar_compuertas_caidas, que es
        # quien realmente arma el set final de conectores afectados).
        self._compuerta_salidas: dict[str, set] = {}
        puertos_regla: list[tuple[str, dict, str]] = []

        for eq_id, lista_reglas in reglas_por_equipo.items():
            nombre_eq = self._equipos.get(eq_id, eq_id)
            nodos_de_este_equipo = set(self._equipo_nodos.get(eq_id, set()))
            todas_las_salidas = salidas_por_equipo.get(eq_id, set())

            for regla in sorted(lista_reglas, key=lambda r: r["orden"]):
                nodo_gate = regla["nodo_id"]
                nodos_miembro = []
                for m in regla["miembros"]:
                    if m["tipo"] == "conector":
                        nodo_ri = f"RI:{m['ref']}"
                        if (eq_id, m["ref"]) not in self._conector_a_nodo:
                            self._conector_a_nodo[(eq_id, m["ref"])] = nodo_ri
                            self._node_equipo[nodo_ri] = eq_id
                            nodos_de_este_equipo.add(nodo_ri)
                            puertos_regla.append(
                                (nodo_ri, {"nombre": f"{nombre_eq} IN {m['ref']}"}, "PuertoRegla"))
                        nodos_miembro.append(nodo_ri)
                    else:  # regla encadenada (sólo entre reglas del mismo equipo, ver _leer_bd)
                        nodos_miembro.append(f"RG:{m['ref']}")

                salidas_gobernadas = regla["salidas"] or todas_las_salidas
                for id_conector_salida in salidas_gobernadas:
                    self._conector_a_nodo[(eq_id, id_conector_salida)] = nodo_gate
                self._node_equipo[nodo_gate] = eq_id
                nodos_de_este_equipo.add(nodo_gate)
                puertos_regla.append(
                    (nodo_gate, {"nombre": f"{nombre_eq} — regla {regla['operador']}"}, "PuertoRegla"))

                self._compuertas[nodo_gate] = (regla["operador"], nodos_miembro)
                self._compuerta_salidas[nodo_gate] = set(salidas_gobernadas)

            self._equipo_nodos[eq_id] = nodos_de_este_equipo

        # ── Nodos de puerto + bypass interno para equipos PATCHERA ──────────
        # Cada módulo de patchera con sus 4 puertos identificados
        # (patchera_puertos, ver _leer_bd) se modela con un nodo de puerto
        # por conector ("PP:<id_conector>") en vez de un único nodo de
        # equipo "pasa todo" — así cortar el cable de un lado (ej.
        # BACK_ENTRADA) no "sostiene" señal en el otro lado (ej.
        # FRONT_INSERCION) sólo porque comparten equipo. El estado del
        # bypass se decide igual que en
        # pantallas_avanzadas._calc_conexion_interna(), según si
        # FRONT_DERIVACION/FRONT_INSERCION tienen algún cable conectado.
        # Fase D de plan_desarrollo_funcion_patchera.md: las 4 claves ya
        # NO son "A_BACK"/"B_BACK"/"A_FRONT"/"B_FRONT" (convención de una
        # sola marca de patchera) sino las funciones abstractas de
        # funcion_patchera — el mismo cálculo sirve igual para un patch
        # module de audio (01_BACK/25_BACK/a_front/b_front) sin ninguna
        # rama de código distinta:
        #   ninguno usado → BACK_ENTRADA -> BACK_SALIDA   (bypass directo)
        #   sólo derivación → BACK_ENTRADA -> FRONT_DERIVACION
        #                                              (tap externo;
        #                                               BACK_SALIDA queda
        #                                               sin origen)
        #   sólo inserción  → FRONT_INSERCION -> BACK_SALIDA
        #                                              (inserción externa;
        #                                               BACK_ENTRADA queda
        #                                               sin destino)
        #   ambos usados    → BACK_ENTRADA -> FRONT_DERIVACION  y
        #                      FRONT_INSERCION -> BACK_SALIDA
        #                                              (loop externo, ej.
        #                                               un procesador
        #                                               insertado)
        puertos_patchera: list[tuple[str, dict, str]] = []
        aristas_patchera: list[tuple[str, str, dict, str]] = []

        conectores_con_cable = set()
        for r in cables_raw:
            conectores_con_cable.add(r["src_conector"])
            conectores_con_cable.add(r["dst_conector"])

        for eq_pat, puertos in patchera_puertos.items():
            nombre_pat = self._equipos.get(eq_pat, eq_pat)
            nodos_de_este_equipo = set(self._equipo_nodos.get(eq_pat, set()))
            nodo_por_funcion = {}

            for funcion, id_con in puertos.items():
                nodo = f"PP:{id_con}"
                self._conector_a_nodo[(eq_pat, id_con)] = nodo
                self._node_equipo[nodo] = eq_pat
                nodos_de_este_equipo.add(nodo)
                nodo_por_funcion[funcion] = nodo
                puertos_patchera.append(
                    (nodo, {"nombre": f"{nombre_pat} {funcion}"}, "PuertoPatchera"))

            derivacion_usada = puertos["FRONT_DERIVACION"] in conectores_con_cable
            insercion_usada = puertos["FRONT_INSERCION"] in conectores_con_cable

            if not derivacion_usada and not insercion_usada:
                aristas_patchera.append(
                    (nodo_por_funcion["BACK_ENTRADA"], nodo_por_funcion["BACK_SALIDA"],
                     {"equipo": eq_pat}, "PATCHERA_BYPASS"))
            if derivacion_usada:
                aristas_patchera.append(
                    (nodo_por_funcion["BACK_ENTRADA"], nodo_por_funcion["FRONT_DERIVACION"],
                     {"equipo": eq_pat}, "PATCHERA_BYPASS"))
            if insercion_usada:
                aristas_patchera.append(
                    (nodo_por_funcion["FRONT_INSERCION"], nodo_por_funcion["BACK_SALIDA"],
                     {"equipo": eq_pat}, "PATCHERA_BYPASS"))

            self._equipo_nodos[eq_pat] = nodos_de_este_equipo

        # ── GraphQLite bulk insert ───────────────────────────────────────────
        self._g = Graph(":memory:")

        nodes = [(eid, {"nombre": nom}, "Equipo")
                 for eid, nom in self._equipos.items()]
        nodes += [(nid, {"nombre": nom}, "Extension")
                  for nid, nom in self._nombres_extension.items()]
        nodes += puertos_matriz
        nodes += puertos_regla
        nodes += puertos_patchera

        # Cables: si el conector de un extremo pertenece a una MATRIZ
        # configurada, la arista se ancla en su nodo de puerto (MI:/MO:) en
        # vez del nodo de equipo, para que el BFS respete el ruteo interno.
        self._cable_graph_endpoints = {}
        # plan_riesgo_senal_audio.md, sección 5.2: propiedades de riesgo de
        # señal consultables desde la Consola Cypher, agregadas como
        # propiedades ADICIONALES de la arista CABLE ya existente — no
        # toca nada de la lógica de impacto/BFS de este módulo. Envuelto
        # en try/except: si la migración de riesgo de señal todavía no
        # corrió en esta base (o directamente no existen las columnas),
        # el grafo de impacto sigue funcionando exactamente igual que
        # siempre, sin estas propiedades.
        riesgo_por_cable = {}
        try:
            db_rs = sqlite3.connect(self._db_path)
            db_rs.row_factory = sqlite3.Row
            for r in db_rs.execute("""
                SELECT c.id_cable,
                       tc.naturaleza_senal,
                       COALESCE(c.ancho_banda_mhz_override, tc.ancho_banda_mhz) AS ancho_banda_mhz
                FROM cable c
                LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = c.id_tipo_cable
            """).fetchall():
                riesgo_por_cable[str(r["id_cable"])] = {
                    "naturaleza_senal": r["naturaleza_senal"],
                    "ancho_banda_mhz": r["ancho_banda_mhz"],
                }
            db_rs.close()
        except Exception:
            riesgo_por_cable = {}

        edges = []
        for r in cables_raw:
            nodo_src = self._conector_a_nodo.get((r["src"], r["src_conector"]), r["src"])
            nodo_dst = self._conector_a_nodo.get((r["dst"], r["dst_conector"]), r["dst"])
            self._cable_graph_endpoints[r["id_cable"]] = (nodo_src, nodo_dst)
            props = {"cable_id": r["id_cable"], "nombre": r["nombre"]}
            props.update(riesgo_por_cable.get(str(r["id_cable"]), {}))
            edges.append((nodo_src, nodo_dst, props, "CABLE"))

        edges += aristas_ruteo
        edges += aristas_patchera

        self._g.insert_graph_bulk(nodes, edges)

        # ── Espejo en Python puro del grafo (para _alcanzables_desde) ───────
        self._adj = {}
        for nodo_src, nodo_dst, _attrs, _tipo in edges:
            self._adj.setdefault(nodo_src, []).append(nodo_dst)

        # ── Fuentes de señal ─────────────────────────────────────────────────
        tiene_entrante = {dst for _, dst in self._cable_endpoints.values()}
        fuentes_raiz   = {eid for eid in self._equipos
                          if eid not in tiene_entrante}
        self._fuentes  = fuentes_refout | fuentes_raiz

        # ── Semillas de todas las fuentes juntas ─────────────────────────────
        # Importante: se calcula la alcanzabilidad con TODAS las fuentes
        # activas a la vez (un solo cálculo global), no una por una. Esto es
        # necesario para que la regla AND de los equipos DSK funcione bien:
        # las 3-4 entradas requeridas de un DSK suelen venir de fuentes
        # RAÍZ *distintas e independientes* entre sí (ej. 4 salidas
        # distintas de una MATRIZ, cada una "fuente" para su propio árbol);
        # si se calculara la alcanzabilidad fuente por fuente por separado,
        # cada cálculo vería sólo su propia semilla y la condición AND
        # nunca se cumpliría aunque, en conjunto, todas las entradas
        # tuvieran señal.
        self._semillas_globales: set = set()
        for fid in self._fuentes:
            self._semillas_globales |= self._equipo_nodos.get(fid, {fid})

        self._alcanzables_ok = self._alcanzables_desde(self._semillas_globales)

    def _alcanzables_desde(self, semillas: set, aristas_excluidas: frozenset = frozenset(),
                            aristas_extra: "Optional[dict[str, list[str]]]" = None) -> set:
        """
        Alcanzabilidad en self._adj (espejo Python del grafo: cables +
        rutas internas de MATRIZ) partiendo de `semillas`, excluyendo
        puntualmente las aristas (nodo_src, nodo_dst) en `aristas_excluidas`
        (así se simula un corte sin tocar self._g).

        `aristas_extra` (opcional): {nodo_src: [nodo_dst, ...]} de aristas
        que se suman SÓLO para este cálculo, sin tocar self._adj — usado
        por simular_escenario() para representar conexiones virtuales
        (reconexión de emergencia) sin escribir nada en la base ni en el
        grafo real.

        Además de la propagación normal por aristas (que es "OR": con que
        llegue señal por cualquier lado, el nodo queda alcanzado), aplica
        las compuertas de reglas lógicas de equipo (self._compuertas): un
        nodo-compuerta "RG:<id_regla>" sólo se agrega al conjunto cuando se
        cumple la condición de sus miembros — TODOS alcanzados si el
        operador es AND, o ALGUNO si es OR. Se resuelve por relajación a
        punto fijo (se reintenta mientras el conjunto siga creciendo), lo
        que además maneja correctamente cadenas de varias reglas en serie.
        """
        extra = aristas_extra or {}
        alc: set = set(semillas)
        cambio = True
        while cambio:
            cambio = False
            # Propagación normal por aristas del grafo, respetando los
            # cortes de aristas_excluidas.
            for u in list(alc):
                for v in self._adj.get(u, ()):
                    if (u, v) in aristas_excluidas:
                        continue
                    if v not in alc:
                        alc.add(v)
                        cambio = True
                # Aristas virtuales (aristas_extra): se agregan SIEMPRE, sin
                # pasar por aristas_excluidas. Son conexiones nuevas
                # propuestas por el escenario, no relacionadas con lo que
                # se está cortando — aunque casualmente conecten el mismo
                # par de nodos que una arista real cortada (ambas resuelven
                # al mismo nodo de equipo, ya que el grafo es a nivel
                # equipo salvo MATRIZ/reglas configuradas), representan un
                # cable físicamente distinto y deben quedar activas.
                for v in extra.get(u, ()):
                    if v not in alc:
                        alc.add(v)
                        cambio = True
            # Compuertas de reglas lógicas: activar la salida sólo si se
            # cumple la condición AND/OR de sus miembros.
            for nodo_compuerta, (operador, miembros) in self._compuertas.items():
                if nodo_compuerta in alc:
                    continue
                cumplida = all(n in alc for n in miembros) if operador == "AND" \
                    else any(n in alc for n in miembros)
                if cumplida:
                    alc.add(nodo_compuerta)
                    cambio = True
        return alc

    def _nodos_a_equipos(self, nodos: set) -> set:
        """Traduce un conjunto de nodos de grafo (que puede incluir nodos de
        puerto "MI:x"/"MO:x" de una MATRIZ configurada) al conjunto de
        id_equipo que representan. Un equipo MATRIZ queda "con señal" si al
        menos uno de sus puertos sigue siendo alcanzable."""
        return {self._node_equipo.get(n, n) for n in nodos}

    def _leer_bd(self) -> tuple[list[dict], list[dict], set[str], set[str],
                                 dict[str, dict[str, Optional[str]]],
                                 dict[str, list[dict]], dict[str, set[str]],
                                 dict[str, str], dict[str, str], dict[str, str],
                                 dict[str, str], dict[str, dict[str, str]]]:
        """
        Lee equipos, cables (con dirección + conectores de cada extremo),
        fuentes REFOUT, equipos FANTASMA, ruteo de equipos MATRIZ, reglas
        lógicas de equipo (AND/OR, ver Modelo.asegurar_tablas_regla_logica)
        y puertos de función abstracta (BACK_ENTRADA/BACK_SALIDA/
        FRONT_DERIVACION/FRONT_INSERCION) de equipos PATCHERA (para
        modelar su bypass interno real, ver construir_grafo) desde la BD.
        La dirección de cada conector y el rol de cada equipo (FANTASMA,
        PATCHERA, fuente de referencia REFOUT) se leen de las columnas
        dedicadas agregadas en la Fase 1 de plan_desarrollo_hardcodes_
        idioma.md (tipo_conector.direccion, tipo_equipo.rol_senal,
        tipo_conector.es_referencia_generada); la función de cada puerto
        de patchera se lee de conector.id_funcion_patchera (Fase A/C de
        plan_desarrollo_funcion_patchera.md, que reemplaza a la
        conector.fila_patchera de la fase anterior — ver funcion_patchera).
        Nada de esto lee texto libre.
        """
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        # Columnas de control de la Fase 1 de plan_desarrollo_hardcodes_
        # idioma.md, aseguradas acá también por si este módulo corre antes
        # que Modelo.asegurar_columnas_control_idioma() en el resto de la
        # app (mismo criterio defensivo que ya usa senal_propagation.py y
        # que este mismo método ya usaba para matriz_ruteo/regla_logica).
        cols_tc = [c[1] for c in cur.execute(
            "PRAGMA table_info(tipo_conector)").fetchall()]
        if "direccion" not in cols_tc:
            cur.execute("ALTER TABLE tipo_conector ADD COLUMN direccion TEXT")
            cur.execute(
                "UPDATE tipo_conector SET direccion = "
                "CASE WHEN UPPER(nombre) LIKE '%OUT%' THEN 'OUT' ELSE 'IN' END")
        if "es_referencia_generada" not in cols_tc:
            cur.execute(
                "ALTER TABLE tipo_conector ADD COLUMN "
                "es_referencia_generada INTEGER NOT NULL DEFAULT 0")
            cur.execute(
                "UPDATE tipo_conector SET es_referencia_generada = 1 "
                "WHERE nombre = 'REFOUT'")
        cols_te = [c[1] for c in cur.execute(
            "PRAGMA table_info(tipo_equipo)").fetchall()]
        if "rol_senal" not in cols_te:
            cur.execute(
                "ALTER TABLE tipo_equipo ADD COLUMN rol_senal TEXT "
                "DEFAULT 'DISTRIBUIDOR'")
        # Población defensiva PATCHERA/FANTASMA (idempotente) — este bloque
        # sólo agregaba la columna, nunca la poblaba, así que el filtro
        # "WHERE te.rol_senal = 'PATCHERA'" de más abajo dependía en
        # silencio de que Modelo.asegurar_columnas_control_idioma() ya
        # hubiera corrido en otro lado antes. Se completa acá para que este
        # módulo (igual que senal_propagation.py) siga funcionando solo.
        cur.execute(
            "UPDATE tipo_equipo SET rol_senal='PATCHERA' "
            "WHERE UPPER(nombre)='MODULO PATCHERA' "
            "AND (rol_senal IS NULL OR rol_senal='DISTRIBUIDOR')")
        # funcion_patchera / conector.id_funcion_patchera: mismo criterio
        # defensivo, ver plan_desarrollo_funcion_patchera.md Fase A. No se
        # migra fila_patchera→id_funcion_patchera acá (eso es trabajo de
        # Modelo.asegurar_columnas_control_idioma, que corre en cada
        # arranque real de la app) — esto sólo garantiza que la tabla y la
        # columna EXISTAN para que el SELECT de más abajo no falle si este
        # módulo corre primero contra una base recién creada.
        cur.execute(
            "CREATE TABLE IF NOT EXISTS funcion_patchera ("
            "  id_funcion_patchera INTEGER PRIMARY KEY,"
            "  clave TEXT UNIQUE NOT NULL, nombre_es TEXT NOT NULL,"
            "  direccion TEXT NOT NULL, descripcion TEXT)")
        cols_c = [c[1] for c in cur.execute(
            "PRAGMA table_info(conector)").fetchall()]
        if "id_funcion_patchera" not in cols_c:
            cur.execute(
                "ALTER TABLE conector ADD COLUMN id_funcion_patchera "
                "INTEGER REFERENCES funcion_patchera(id_funcion_patchera)")
        db.commit()

        # Equipos
        cur.execute("SELECT id_equipo AS id, nombre FROM equipo")
        equipos = [dict(r) for r in cur.fetchall()]

        # Equipos de tipo FANTASMA (placeholders para equipo real fuera del
        # alcance de la documentación, ej. \"lo que sigue después\" de un
        # feed externo) — no cuentan como equipo real a proteger, así que
        # se excluyen del factor Impacto (y de equipos_totales, para no
        # diluir el porcentaje con activos que no son propios).
        cur.execute("""
            SELECT e.id_equipo
            FROM equipo e
            JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE te.rol_senal = 'FANTASMA'
        """)
        equipos_fantasma = {str(r["id_equipo"]) for r in cur.fetchall()}

        # ── Puertos de patchera (funciones abstractas) de equipos PATCHERA ───
        # Un módulo de patchera NO es un nodo "pasa todo": físicamente es un
        # bypass condicional (mismo modelo que ya usa pantallas_avanzadas.
        # _calc_conexion_interna() para dibujarlo) — sin nada patcheado al
        # frente, la entrada trasera queda internamente unida a la salida
        # trasera; si se patchea la derivación y/o la inserción frontal,
        # ese bypass se interrumpe y la señal sigue por el frente en su
        # lugar. Tratar todo el equipo como un único nodo (como se hacía
        # antes de este cambio) hacía que CUALQUIER cable tocando
        # cualquiera de sus 4 conectores "sostuviera" señal en TODO el
        # equipo, ocultando el impacto real de desconectar, por ejemplo,
        # el cable que llega a la entrada trasera cuando el que sigue
        # viaja por la salida trasera.
        # Fase C/D de plan_desarrollo_funcion_patchera.md: los 4 puertos
        # se identifican EXCLUSIVAMENTE por conector.id_funcion_patchera
        # (vía JOIN a funcion_patchera para obtener la clave abstracta) —
        # ya no hay fallback a fila_patchera ni a prefijo de nombre. Un
        # equipo sin las 4 funciones cargadas no se modela con bypass (se
        # deja como nodo único, comportamiento anterior) y aparece en
        # Modelo.listar_patcheras_sin_funcion_completa() para completarlo
        # a mano — nunca se adivina desde el nombre del conector.
        cur.execute("""
            SELECT e.id_equipo FROM equipo e
            JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE te.rol_senal = 'PATCHERA'
        """)
        equipos_patchera_ids = [str(r["id_equipo"]) for r in cur.fetchall()]

        FUNCIONES_PATCHERA = ("BACK_ENTRADA", "BACK_SALIDA",
                              "FRONT_DERIVACION", "FRONT_INSERCION")
        patchera_puertos: dict[str, dict[str, str]] = {}
        if equipos_patchera_ids:
            qmarks = ",".join("?" * len(equipos_patchera_ids))
            cur.execute(
                f"SELECT c.id_conector, c.id_equipo, fp.clave "
                f"FROM conector c "
                f"LEFT JOIN funcion_patchera fp "
                f"  ON fp.id_funcion_patchera = c.id_funcion_patchera "
                f"WHERE c.id_equipo IN ({qmarks})",
                equipos_patchera_ids)
            conectores_por_eq_patchera: dict[str, list[sqlite3.Row]] = {}
            for r in cur.fetchall():
                conectores_por_eq_patchera.setdefault(
                    str(r["id_equipo"]), []).append(r)

            for eq_id, cons in conectores_por_eq_patchera.items():
                puertos = {}
                for r in cons:
                    clave = r["clave"]
                    if clave in FUNCIONES_PATCHERA and clave not in puertos:
                        puertos[clave] = str(r["id_conector"])
                if len(puertos) == 4:
                    patchera_puertos[eq_id] = puertos
                # Si no se encuentran las 4 funciones, el equipo se deja tal
                # cual (nodo único de equipo, comportamiento anterior) — no
                # se puede modelar el bypass sin saber qué conector es cuál.

        # Dirección IN/OUT de cada conector: se lee de tipo_conector.
        # direccion (columna agregada en la Fase 1 de
        # plan_desarrollo_hardcodes_idioma.md) en vez de buscar el texto
        # "OUT" dentro del nombre del tipo de conector.
        cur.execute("""
            SELECT c.id_conector AS id_conector, c.id_equipo AS id_equipo,
                   COALESCE(tc.direccion, 'OUT') AS direccion
            FROM conector c
            LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        """)
        direccion_por_conector = {}
        equipo_por_conector = {}
        for r in cur.fetchall():
            cid = str(r["id_conector"])
            direccion_por_conector[cid] = r["direccion"] or "OUT"
            equipo_por_conector[cid] = str(r["id_equipo"])

        # Cables dirigidos desde CONEXIONES_AMBOS_EXTREMOS
        #   col 'id_equipo:1' = id Extremo A  /  'id_equipo' = id Extremo B
        #   col 'id_conector:1' = conector Extremo A / 'id_conector' = conector Extremo B
        cur.execute("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
        rows = cur.fetchall()

        seen: set[str] = set()
        cables: list[dict] = []
        for r in rows:
            id_cable_str = str(r["id_cable"])
            if id_cable_str in seen:
                continue
            id_ea   = str(r["id_equipo:1"])
            id_eb   = str(r["id_equipo"])
            id_con_a = str(r["id_conector:1"])
            id_con_b = str(r["id_conector"])
            dir_a = direccion_por_conector.get(id_con_a, "OUT")
            if dir_a == "OUT":
                src, dst = id_ea, id_eb
                src_conector, dst_conector = id_con_a, id_con_b
            else:
                src, dst = id_eb, id_ea
                src_conector, dst_conector = id_con_b, id_con_a
            seen.add(id_cable_str)
            cables.append({
                "id_cable":     id_cable_str,
                "nombre":       str(r["Cable"]),
                "src":          src,
                "dst":          dst,
                "src_conector": src_conector,
                "dst_conector": dst_conector,
            })

        # ── Cables que atraviesan extension_cable (empalmes ficha-contra-
        # ficha sin equipo de por medio — Fase 3 de plan_desarrollo_
        # extension_cable.md). CONEXIONES_AMBOS_EXTREMOS exige equipo real
        # en los dos extremos, así que estos cables no aparecen en absoluto
        # en el bloque de arriba — se resuelven acá caminando la cadena de
        # extension_cable con el mismo criterio de dirección
        # (tipo_conector.direccion) que el resto de este método, anclando
        # cada lado empalmado a un nodo de paso "EXT:<id_extension>" en vez
        # de a un id_equipo. Ese nodo de paso se agrega más abajo a `nodes`
        # (tipo "Extension") y participa del grafo de GraphQLite igual que
        # cualquier otro nodo — el bucle de armado de aristas de más abajo
        # no necesita ningún caso especial, porque _conector_a_nodo.get()
        # ya cae al valor por defecto (el propio "EXT:<id>") cuando no
        # encuentra la clave. Mismo mecanismo de resolución que
        # senal_propagation.py, para que los dos motores nunca discrepen
        # sobre la misma cadena. Un extremo suelto sin extension_cable
        # todavía (cadena incompleta) deja ese cable sin arista, igual que
        # hoy un dato incompleto no propaga.
        self._nombres_extension: dict[str, str] = {}
        cur.execute("SELECT id_conexion, id_cable, id_conector FROM conexion")
        id_cable_de_cx, id_conector_de_cx, cxs_por_cable = {}, {}, {}
        for r in cur.fetchall():
            cx, cbl = str(r[0]), str(r[1])
            id_cable_de_cx[cx] = cbl
            id_conector_de_cx[cx] = str(r[2]) if r[2] is not None else None
            cxs_por_cable.setdefault(cbl, []).append(cx)

        cur.execute(
            "SELECT id_extension, id_conexion_a, id_conexion_b FROM extension_cable")
        partner_ext = {}
        for id_ext, cxa, cxb in cur.fetchall():
            id_ext, cxa, cxb = str(id_ext), str(cxa), str(cxb)
            partner_ext[cxa] = (cxb, id_ext)
            partner_ext[cxb] = (cxa, id_ext)

        if partner_ext:
            def _lado_ext(cx):
                id_con = id_conector_de_cx.get(cx)
                if id_con is not None:
                    return ("REAL", id_con)
                par = partner_ext.get(cx)
                return ("EXT", par[1]) if par else None

            info_cable_ext = {}
            for id_cable_e, cxs in cxs_por_cable.items():
                if len(cxs) != 2:
                    continue
                la, lb = _lado_ext(cxs[0]), _lado_ext(cxs[1])
                if la is None or lb is None:
                    continue
                if la[0] == "REAL" and lb[0] == "REAL":
                    continue  # cable normal, ya viene del bloque de arriba
                info_cable_ext[id_cable_e] = (la, lb)

            resueltas_ext = {}
            for id_cable_e, (la, lb) in info_cable_ext.items():
                if la[0] == "REAL":
                    resueltas_ext[id_cable_e] = (
                        (la, lb) if direccion_por_conector.get(la[1], "OUT") == "OUT"
                        else (lb, la))
                elif lb[0] == "REAL":
                    resueltas_ext[id_cable_e] = (
                        (lb, la) if direccion_por_conector.get(lb[1], "OUT") == "OUT"
                        else (la, lb))

            cables_por_ext_node = {}
            for id_cable_e, (la, lb) in info_cable_ext.items():
                for lado in (la, lb):
                    if lado[0] == "EXT":
                        cables_por_ext_node.setdefault(lado[1], []).append(id_cable_e)

            cambio_ext, intentos_ext = True, 0
            while cambio_ext and intentos_ext < len(info_cable_ext) + 5:
                cambio_ext, intentos_ext = False, intentos_ext + 1
                for id_cable_e, (src_e, dst_e) in list(resueltas_ext.items()):
                    for lado, rol in ((src_e, "src"), (dst_e, "dst")):
                        if lado[0] != "EXT":
                            continue
                        for otro in cables_por_ext_node.get(lado[1], []):
                            if otro == id_cable_e or otro in resueltas_ext:
                                continue
                            la2, lb2 = info_cable_ext[otro]
                            if la2[0] == "EXT" and la2[1] == lado[1]:
                                local2, opuesto2 = la2, lb2
                            elif lb2[0] == "EXT" and lb2[1] == lado[1]:
                                local2, opuesto2 = lb2, la2
                            else:
                                continue
                            resueltas_ext[otro] = (
                                (local2, opuesto2) if rol == "dst" else (opuesto2, local2))
                            cambio_ext = True

            if resueltas_ext:
                ids_cable_ext = list(resueltas_ext.keys())
                qmarks = ",".join("?" * len(ids_cable_ext))
                cur.execute(
                    f"SELECT id_cable, codigo FROM cable WHERE id_cable IN ({qmarks})",
                    ids_cable_ext)
                codigo_de_cable_ext = {str(r[0]): r[1] for r in cur.fetchall()}

                ids_extension = {lado[1] for src_e, dst_e in resueltas_ext.values()
                                  for lado in (src_e, dst_e) if lado[0] == "EXT"}
                if ids_extension:
                    qmarks2 = ",".join("?" * len(ids_extension))
                    cur.execute(
                        f"SELECT id_extension, posicion_libre FROM extension_cable "
                        f"WHERE id_extension IN ({qmarks2})", list(ids_extension))
                    for id_ext, pos in cur.fetchall():
                        id_ext = str(id_ext)
                        etiqueta = f"Extensión #{id_ext}"
                        if pos:
                            etiqueta += f" ({pos})"
                        self._nombres_extension[f"EXT:{id_ext}"] = etiqueta

                for id_cable_e, (src_e, dst_e) in resueltas_ext.items():
                    src_node = (equipo_por_conector.get(src_e[1]) if src_e[0] == "REAL"
                                else f"EXT:{src_e[1]}")
                    dst_node = (equipo_por_conector.get(dst_e[1]) if dst_e[0] == "REAL"
                                else f"EXT:{dst_e[1]}")
                    cables.append({
                        "id_cable":     id_cable_e,
                        "nombre":       codigo_de_cable_ext.get(id_cable_e, f"Cable #{id_cable_e}"),
                        "src":          src_node,
                        "dst":          dst_node,
                        "src_conector": src_e[1] if src_e[0] == "REAL" else None,
                        "dst_conector": dst_e[1] if dst_e[0] == "REAL" else None,
                    })

        # Ruteo interno de equipos tipo MATRIZ (salida → entrada asignada),
        # sólo para equipos que ya tienen configuración guardada (al menos
        # una fila en matriz_ruteo, la misma tabla que usa el botón
        # "Editar matriz"). Se crea la tabla si todavía no existe (por si
        # esta conexión de lectura corre antes que Modelo.
        # asegurar_tabla_matriz_ruteo() en el resto de la app).
        cur.execute(
            "CREATE TABLE IF NOT EXISTS matriz_ruteo ("
            "  id_conector_salida  INTEGER PRIMARY KEY,"
            "  id_conector_entrada INTEGER,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_conector_salida)  REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_entrada) REFERENCES conector(id_conector) ON DELETE SET NULL"
            ")"
        )
        cur.execute("""
            SELECT c.id_equipo AS id_equipo,
                   mr.id_conector_salida,
                   mr.id_conector_entrada
            FROM matriz_ruteo mr
            JOIN conector c ON c.id_conector = mr.id_conector_salida
        """)
        matriz_ruteo: dict[str, dict[str, Optional[str]]] = {}
        for r in cur.fetchall():
            eq_mtz = str(r["id_equipo"])
            id_salida = str(r["id_conector_salida"])
            id_entrada = (str(r["id_conector_entrada"])
                          if r["id_conector_entrada"] is not None else None)
            matriz_ruteo.setdefault(eq_mtz, {})[id_salida] = id_entrada

        # ── Reglas lógicas de equipo (AND / OR) ──────────────────────────────
        # Generaliza lo que antes era un caso hardcodeado sólo para
        # tipo_equipo='DSK'. Ver Modelo.asegurar_tablas_regla_logica /
        # PLAN_reglas_logicas_equipo.md para el diseño completo. Se crean
        # las tablas acá también (idempotente) por si esta conexión de
        # lectura corre antes que Modelo en el resto de la app.
        cur.execute(
            "CREATE TABLE IF NOT EXISTS regla_logica ("
            "  id_regla        INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_equipo       INTEGER,"
            "  id_tipo_equipo  INTEGER,"
            "  nombre          TEXT,"
            "  operador        TEXT NOT NULL CHECK (operador IN ('AND','OR')),"
            "  activa          INTEGER NOT NULL DEFAULT 1,"
            "  orden           INTEGER NOT NULL DEFAULT 0,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,"
            "  CHECK ((id_equipo IS NULL) <> (id_tipo_equipo IS NULL))"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS regla_logica_miembro ("
            "  id_miembro       INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_regla         INTEGER NOT NULL,"
            "  id_conector      INTEGER,"
            "  id_regla_miembro INTEGER,"
            "  patron_conector  TEXT,"
            "  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_regla_miembro) REFERENCES regla_logica(id_regla) ON DELETE CASCADE"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS regla_logica_salida ("
            "  id_regla    INTEGER NOT NULL,"
            "  id_conector INTEGER NOT NULL,"
            "  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE"
            ")"
        )

        cur.execute("SELECT id_regla, id_equipo, id_tipo_equipo, operador, orden "
                     "FROM regla_logica WHERE activa=1")
        reglas_raw = [dict(r) for r in cur.fetchall()]
        ids_regla = [r["id_regla"] for r in reglas_raw]

        miembros_por_regla: dict[int, list[dict]] = {}
        salidas_por_regla: dict[int, list[int]] = {}
        if ids_regla:
            qmarks = ",".join("?" * len(ids_regla))
            cur.execute(
                f"SELECT id_regla, id_conector, id_regla_miembro, patron_conector "
                f"FROM regla_logica_miembro WHERE id_regla IN ({qmarks})", ids_regla)
            for r in cur.fetchall():
                miembros_por_regla.setdefault(r["id_regla"], []).append(dict(r))
            cur.execute(
                f"SELECT id_regla, id_conector FROM regla_logica_salida "
                f"WHERE id_regla IN ({qmarks})", ids_regla)
            for r in cur.fetchall():
                salidas_por_regla.setdefault(r["id_regla"], []).append(r["id_conector"])

        # Un equipo con regla propia (id_equipo seteado) IGNORA por completo
        # las reglas de su tipo_equipo (no se combinan, ver plan).
        equipos_con_regla_propia = {str(r["id_equipo"]) for r in reglas_raw
                                     if r["id_equipo"] is not None}

        cur.execute("SELECT id_equipo, id_tipo_equipo FROM equipo")
        equipos_por_tipo: dict[str, list[str]] = {}
        for r in cur.fetchall():
            if r["id_tipo_equipo"] is not None:
                equipos_por_tipo.setdefault(str(r["id_tipo_equipo"]), []).append(str(r["id_equipo"]))

        # Nombre de conector (normalizado) → id_conector, por equipo — para
        # resolver los patron_conector de las reglas de tipo_equipo contra
        # los conectores REALES de cada equipo de ese tipo (cada instancia
        # tiene sus propios id_conector, por eso las reglas de plantilla no
        # pueden guardar un id_conector literal).
        cur.execute("SELECT id_equipo, id_conector, nombre FROM conector")
        conectores_por_equipo_nombre: dict[str, dict[str, str]] = {}
        nombre_por_conector: dict[str, str] = {}
        for r in cur.fetchall():
            conectores_por_equipo_nombre.setdefault(str(r["id_equipo"]), {})[
                str(r["nombre"]).strip().upper()] = str(r["id_conector"])
            nombre_por_conector[str(r["id_conector"])] = str(r["nombre"])

        # Conectores de salida ("OUT") de TODO equipo — para resolver
        # salidas=[] como "todas las salidas del equipo" (default).
        cur.execute("""
            SELECT c.id_equipo AS id_equipo, c.id_conector
            FROM conector c
            JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE UPPER(tc.nombre) = 'OUT'
        """)
        salidas_por_equipo: dict[str, set[str]] = {}
        for r in cur.fetchall():
            salidas_por_equipo.setdefault(str(r["id_equipo"]), set()).add(str(r["id_conector"]))

        def _miembros_resueltos(miembros_raw, eq_id_contexto):
            out = []
            for m in miembros_raw:
                if m["id_conector"] is not None:
                    out.append({"tipo": "conector", "ref": str(m["id_conector"])})
                elif m["id_regla_miembro"] is not None:
                    # Encadenado: sólo soportado entre reglas del MISMO
                    # equipo (una regla de tipo_equipo no puede encadenar a
                    # otra porque cada instancia necesitaría su propio nodo
                    # — fuera de alcance por ahora, ver plan).
                    out.append({"tipo": "regla", "ref": str(m["id_regla_miembro"])})
                elif m["patron_conector"] is not None:
                    cid = conectores_por_equipo_nombre.get(eq_id_contexto, {}).get(
                        str(m["patron_conector"]).strip().upper())
                    if cid:
                        out.append({"tipo": "conector", "ref": cid})
                    # si no matchea ningún conector de este equipo, se omite
            return out

        # eq_id → [{"nodo_id", "operador", "miembros", "salidas", "orden"}, ...]
        reglas_por_equipo: dict[str, list[dict]] = {}
        for r in reglas_raw:
            id_regla = r["id_regla"]
            miembros_raw = miembros_por_regla.get(id_regla, [])
            salidas_raw = salidas_por_regla.get(id_regla, [])
            if r["id_equipo"] is not None:
                eq_id = str(r["id_equipo"])
                miembros = _miembros_resueltos(miembros_raw, eq_id)
                if not miembros:
                    continue
                reglas_por_equipo.setdefault(eq_id, []).append({
                    "nodo_id": f"RG:{id_regla}", "operador": r["operador"],
                    "miembros": miembros, "salidas": [str(c) for c in salidas_raw],
                    "orden": r["orden"],
                })
            else:
                id_tipo = str(r["id_tipo_equipo"])
                for eq_id in equipos_por_tipo.get(id_tipo, []):
                    if eq_id in equipos_con_regla_propia:
                        continue  # reemplazadas por las reglas propias del equipo
                    miembros = _miembros_resueltos(miembros_raw, eq_id)
                    if not miembros:
                        continue
                    reglas_por_equipo.setdefault(eq_id, []).append({
                        "nodo_id": f"RG:{id_regla}:{eq_id}", "operador": r["operador"],
                        "miembros": miembros, "salidas": [],  # tipo_equipo sólo soporta "todas"
                        "orden": r["orden"],
                    })

        # Fuentes REFOUT: equipos que GENERAN una referencia (ej. generadores
        # de sync/wordclock tipo SPG) — estos sí son fuentes de señal
        # incondicionales, sin importar si tienen otras entradas cableadas.
        #
        # OJO: no usar REFIN acá. REFIN es la entrada de referencia que un
        # equipo RECIBE de otro (genlock/wordclock externo) — la tiene casi
        # cualquier equipo profesional de audio/video, incluso equipos que
        # dependen 100% de su entrada de señal real (SDI/AES IN) para tener
        # algo que procesar. Si se marca como fuente a todo equipo con
        # REFIN, ese equipo queda "con señal" en la simulación aunque se
        # desconecte su único cable de entrada real, porque el BFS arranca
        # directamente desde él sin pasar por esa entrada.
        cur.execute("""
            SELECT DISTINCT e.id_equipo
            FROM equipo e
            JOIN conector c   ON c.id_equipo       = e.id_equipo
            JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE tc.es_referencia_generada = 1
        """)
        fuentes_refout = {str(r["id_equipo"]) for r in cur.fetchall()}

        # id_conector → id_equipo / tipo de conector — sólo para
        # simular_escenario() (resolver conexiones virtuales, ver
        # _nodo_de_conector). No confundir con conectores_por_equipo_nombre
        # (que está indexado por nombre normalizado, no por id).
        cur.execute("""
            SELECT c.id_conector, c.id_equipo, tc.nombre AS tipo
            FROM conector c
            LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        """)
        conector_equipo: dict[str, str] = {}
        conector_tipo: dict[str, str] = {}
        for r in cur.fetchall():
            cid = str(r["id_conector"])
            conector_equipo[cid] = str(r["id_equipo"])
            conector_tipo[cid] = str(r["tipo"]) if r["tipo"] is not None else ""

        db.close()
        return (equipos, cables, fuentes_refout, equipos_fantasma,
                matriz_ruteo, reglas_por_equipo, salidas_por_equipo,
                nombre_por_conector, conector_equipo, conector_tipo,
                direccion_por_conector, patchera_puertos)

    # ──────────────────────────────────────────────────────────────────────────
    # Simulación de desconexión
    # ──────────────────────────────────────────────────────────────────────────

    def _explicar_compuertas_caidas(self, alc_sim_nodos: set):
        """Para cada regla lógica cuya compuerta CUMPLÍA en el estado normal
        (self._alcanzables_ok) y dejó de cumplirse en esta simulación
        puntual, arma un texto explicando qué conector faltó. Devuelve una
        tupla (explicaciones, conectores_afectados):
          - explicaciones: {id_equipo: texto} — sólo incluye equipos donde
            la causa es atribuible a SU PROPIA regla (no simplemente "está
            aguas abajo de algo cortado"), para que el panel de análisis
            pueda mostrar el motivo real en vez de sólo "sin señal".
          - conectores_afectados: set de ids de conector — la(s) entrada(s)
            puntual(es) que faltó/faltaron MÁS la(s) salida(s) que esa
            regla gobierna. Deliberadamente NO es "todos los conectores
            del equipo": un equipo con una regla rota puede tener otras
            entradas/salidas ajenas a esa regla con señal real intacta
            (bugfix 2026-08-24, plan_estado_senal_y_linaje.md Función 1 —
            antes de esto, senal_estado.py usaba equipo_id entero como
            proxy y terminaba marcando "caídos" conectores que en
            realidad seguían con señal)."""
        explicaciones: dict = {}
        conectores_afectados: set = set()
        for nodo_gate, (operador, miembros) in self._compuertas.items():
            if nodo_gate in alc_sim_nodos or nodo_gate not in self._alcanzables_ok:
                continue  # sigue cumpliéndose, o ya estaba caída de por sí (no es por esta simulación)
            eq_id = self._node_equipo.get(nodo_gate, nodo_gate)
            conectores_faltantes = [
                n.split(":", 1)[1]
                for n in miembros if n.startswith("RI:") and n not in alc_sim_nodos
            ]
            if not conectores_faltantes:
                continue
            nombres_faltantes = [
                self._nombre_conector.get(cid, cid) for cid in conectores_faltantes]
            explicaciones[eq_id] = (
                f"{self._equipos.get(eq_id, eq_id)}: falta señal en "
                f"{', '.join(nombres_faltantes)} — regla {operador}")
            conectores_afectados.update(conectores_faltantes)
            conectores_afectados.update(self._compuerta_salidas.get(nodo_gate, ()))
        return explicaciones, conectores_afectados

    def simular_desconexion(self, cable_id: str) -> ResultadoImpacto:
        """
        Simula que `cable_id` se desconecta y calcula el impacto.

        Estrategia (no destructiva, no toca self._g):
          1. Identificar fuentes que alcanzaban el origen del cable → las únicas
             cuyo cálculo puede cambiar.
          2. Re-calcular alcanzabilidad de esas fuentes excluyendo puntualmente
             la arista del cable cortado (ver _alcanzables_desde).
          3. Diferencia de alcanzabilidad = equipos impactados.

        Retorna ResultadoImpacto con todos los equipos y cables sin señal.

        Si alguno de los dos extremos del cable es un conector de entrada o
        salida de un equipo MATRIZ con ruteo configurado, la desconexión se
        aplica sobre el nodo de puerto correspondiente (MI:/MO:) en vez del
        nodo de equipo — así sólo se ven afectadas las salidas realmente
        ruteadas desde esa entrada, no todo el equipo. Si el cable corta la
        única entrada requerida de un equipo DSK (o una de varias), la regla
        AND de _alcanzables_desde() corta también, en cascada, todo lo que
        dependa exclusivamente de las salidas de ese DSK.

        Se recalcula la alcanzabilidad global (todas las fuentes juntas) en
        vez de sólo las "fuentes afectadas": la regla AND del DSK necesita
        ver, en un mismo cálculo, si TODAS sus entradas requeridas siguen
        con señal — y esas entradas suelen venir de fuentes independientes
        entre sí, que un cálculo aislado por fuente no puede comparar entre
        ellas. El grafo es chico (cientos de nodos), así que el costo de
        recalcular todo es despreciable.
        """
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")

        src_c, dst_c   = self._cable_endpoints[cable_id]           # nivel equipo (API pública)
        nodo_src, nodo_dst = self._cable_graph_endpoints[cable_id]  # nivel grafo (interno)
        nombre        = self._cables.get(cable_id, f"Cable #{cable_id}")

        arista_cortada = frozenset({(nodo_src, nodo_dst)})
        alc_sim_nodos = self._alcanzables_desde(self._semillas_globales, arista_cortada)

        # Traducir nodos de puerto (MI:/MO:) a id_equipo antes de reportar
        equipos_con_senal_sim = self._nodos_a_equipos(alc_sim_nodos)
        equipos_ok             = self._nodos_a_equipos(self._alcanzables_ok)

        # Equipos que pierden señal. Los equipos FANTASMA son placeholders
        # (representan "lo que sigue después" de un feed externo fuera del
        # alcance de la documentación, ej. "EXTREMO A DESCONECTADO") — no
        # son un equipo real a proteger, así que se excluyen del resultado
        # aunque el BFS los marque como no alcanzados (mismo criterio que
        # ya aplicaba simular_falla_equipo()).
        # Nodos EXT:<id_extension> (empalmes de extension_cable, Fase 3 de
        # plan_desarrollo_extension_cable.md) se excluyen del resultado
        # público igual que FANTASMA (no son un "equipo"), pero SÍ deben
        # seguir contando para detectar qué cables físicos quedan
        # impactados más abajo — por eso se resta en dos pasos.
        equipos_impactados_full = (equipos_ok - equipos_con_senal_sim) - self._fantasma
        equipos_impactados = equipos_impactados_full - self._ext_nodos

        # Cables cuyos extremos pierden señal
        cables_impactados: set[str] = set()
        for cid, (s, d) in self._cable_endpoints.items():
            if cid == cable_id:
                continue
            if s in equipos_impactados_full or d in equipos_impactados_full:
                cables_impactados.add(cid)

        causas_regla, conectores_regla_caida = self._explicar_compuertas_caidas(alc_sim_nodos)
        return ResultadoImpacto(
            cable_desconectado=cable_id,
            nombre_cable=nombre,
            equipos_con_senal=equipos_con_senal_sim,
            equipos_impactados=equipos_impactados,
            cables_impactados=cables_impactados,
            causas_regla=causas_regla,
            conectores_regla_caida=conectores_regla_caida,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Simulación de falla de EQUIPO (para el Índice de Riesgo de Falla)
    # ──────────────────────────────────────────────────────────────────────────

    def simular_falla_equipo(self, equipo_id: str) -> ResultadoImpactoEquipo:
        """
        Simula que `equipo_id` falla por completo (todos sus cables de
        entrada y salida dejan de transmitir a la vez), y calcula qué otros
        equipos quedan sin señal.

        Misma estrategia no-destructiva que simular_desconexion() (no toca
        self._g): se recalcula la alcanzabilidad global excluyendo
        puntualmente todas las aristas incidentes al equipo. No reconstruye
        el grafo completo. Si el equipo que falla alimenta una entrada
        requerida de un equipo DSK, la regla AND corta también, en
        cascada, las salidas de ese DSK (ver _alcanzables_desde).
        """
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")

        eq_id = str(equipo_id)
        nombre = self._equipos.get(eq_id, f"Equipo #{eq_id}")

        # cables_del_equipo guarda, por cable, tanto el par a nivel equipo
        # (para identificar "toca a este equipo") como el par a nivel grafo
        # (nodo real cuya arista hay que excluir — puede ser un puerto
        # MI:/MO: si el otro extremo es una MATRIZ configurada, o si el
        # propio eq_id lo es).
        cables_del_equipo = [
            (cid, geq_src, geq_dst, gnodo_src, gnodo_dst)
            for cid, (geq_src, geq_dst) in self._cable_endpoints.items()
            for (gnodo_src, gnodo_dst) in [self._cable_graph_endpoints[cid]]
            if geq_src == eq_id or geq_dst == eq_id
        ]
        if not cables_del_equipo:
            return ResultadoImpactoEquipo(equipo_id=eq_id, nombre_equipo=nombre)

        aristas_cortadas = frozenset(
            (gnodo_src, gnodo_dst)
            for _cid, _geq_s, _geq_d, gnodo_src, gnodo_dst in cables_del_equipo
        )
        alc_sim_nodos = self._alcanzables_desde(self._semillas_globales, aristas_cortadas)

        # Traducir nodos de puerto (MI:/MO:) a id_equipo antes de reportar.
        # Los equipos FANTASMA son placeholders (no hay un equipo real que
        # proteger del otro lado), así que no cuentan como "equipo que se
        # queda sin señal" aunque el BFS los marque como no alcanzados.
        equipos_con_senal_sim = self._nodos_a_equipos(alc_sim_nodos)
        equipos_ok             = self._nodos_a_equipos(self._alcanzables_ok)
        equipos_impactados_full = (equipos_ok - equipos_con_senal_sim) - {eq_id} - self._fantasma
        equipos_impactados = equipos_impactados_full - self._ext_nodos
        finales = self.puntos_finales()
        puntos_finales_impactados = equipos_impactados & finales

        # Cables cuyos extremos pierden señal (mismo criterio que
        # simular_desconexion), excluyendo los propios del equipo que falló
        # — esos ya se sabe que quedan sin transmitir, no son "impacto".
        cables_del_eq_ids = {cid for cid, _g, _g2, _n1, _n2 in cables_del_equipo}
        cables_impactados: set[str] = set()
        for cid, (s, d) in self._cable_endpoints.items():
            if cid in cables_del_eq_ids:
                continue
            if s in equipos_impactados_full or d in equipos_impactados_full:
                cables_impactados.add(cid)

        causas_regla, conectores_regla_caida = self._explicar_compuertas_caidas(alc_sim_nodos)
        return ResultadoImpactoEquipo(
            equipo_id=eq_id,
            nombre_equipo=nombre,
            equipos_impactados=equipos_impactados,
            puntos_finales_impactados=puntos_finales_impactados,
            causas_regla=causas_regla,
            cables_impactados=cables_impactados,
            conectores_regla_caida=conectores_regla_caida,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Simulación de pérdida de RACK / CONEXIÓN puntual
    # (plan_simular_remocion_cadena.md — botón "⚡ Simular remoción" en los
    # diálogos de detalle de Cable/Equipo/Rack/Conexión; el caso Cable usa
    # simular_desconexion() y el caso Equipo simular_falla_equipo(), ambos
    # ya existentes desde antes de este plan)
    # ──────────────────────────────────────────────────────────────────────────

    def _equipos_de_rack(self, id_rack: str) -> set:
        """Todos los id_equipo alojados en el rack: los posicionados
        directo (posicion_en_rack.id_equipo) MÁS los que están en un slot
        de un frame que a su vez está posicionado en ese rack. Consulta
        directa a la BD (no hay nada de esto precalculado en el grafo en
        memoria) — se abre y cierra una conexión propia, mismo criterio
        que _leer_bd()."""
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        try:
            cur.execute(
                "SELECT id_equipo FROM posicion_en_rack "
                "WHERE id_rack=? AND id_equipo IS NOT NULL AND id_equipo != 0",
                (str(id_rack),),
            )
            equipos = {str(r["id_equipo"]) for r in cur.fetchall()}

            cur.execute(
                "SELECT s.id_equipo FROM slot s "
                "JOIN posicion_en_rack pr ON pr.id_frame = s.id_frame "
                "WHERE pr.id_rack=? AND s.id_equipo IS NOT NULL AND s.id_equipo != 0",
                (str(id_rack),),
            )
            equipos |= {str(r["id_equipo"]) for r in cur.fetchall()}
            return equipos
        finally:
            db.close()

    def simular_perdida_rack(self, id_rack: str) -> ResultadoImpacto:
        """
        Simula que TODOS los equipos alojados en el rack (directos +
        dentro de sus frames) dejan de alimentar al resto del sistema al
        mismo tiempo — equivalente a un corte de energía del rack
        completo.

        Reutiliza simular_escenario() con equipos_fallados = todos los
        equipos del rack, evaluados en un ÚNICO cálculo (mismo motivo que
        ya documenta simular_escenario: una regla AND que dependa de
        equipos repartidos en el mismo rack tiene que verse en conjunto,
        no equipo por equipo). El resultado se re-empaqueta como
        ResultadoImpacto (mismo shape que usa ImpactoResultadoDialog),
        sin exponer el detalle "antes/después" propio de Escenario porque
        acá no hay reconexión virtual involucrada.
        """
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")

        nombre_rack = self._nombre_rack(id_rack)
        equipos = self._equipos_de_rack(id_rack)
        if not equipos:
            return ResultadoImpacto(
                cable_desconectado="", nombre_cable=f"Rack: {nombre_rack}")

        r = self.simular_escenario(equipos_fallados=equipos)
        return ResultadoImpacto(
            cable_desconectado="",
            nombre_cable=f"Rack: {nombre_rack}  ({len(equipos)} equipo(s) alojados)",
            equipos_con_senal=r.equipos_con_senal,
            equipos_impactados=r.equipos_impactados,
            cables_impactados=r.cables_impactados,
            causas_regla=r.causas_regla,
        )

    def _nombre_rack(self, id_rack: str) -> str:
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        try:
            cur = db.execute(
                "SELECT nombre FROM rack WHERE id_rack=?", (str(id_rack),))
            row = cur.fetchone()
            return row["nombre"] if row and row["nombre"] else f"Rack #{id_rack}"
        finally:
            db.close()

    def simular_perdida_conexion(self, id_conexion: str) -> ResultadoImpacto:
        """
        Resuelve id_conexion → id_cable y delega en simular_desconexion(),
        ya existente. Una 'conexión' en CableDoc es una punta de cable en
        un conector puntual (tabla `conexion`); desconectarla equivale a
        desconectar el cable entero para el grafo de señal (el grafo no
        modela extremos sueltos), así que el resultado es idéntico a
        cortar el cable — se agrega este método solo para no obligar al
        llamador (el diálogo de Conexión) a conocer el id_cable de
        antemano.
        """
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")

        db = sqlite3.connect(self._db_path)
        try:
            cur = db.execute(
                "SELECT id_cable FROM conexion WHERE id_conexion=?",
                (str(id_conexion),))
            row = cur.fetchone()
        finally:
            db.close()

        if not row or row[0] is None:
            return ResultadoImpacto(
                cable_desconectado="",
                nombre_cable=f"Conexión #{id_conexion} (sin cable asociado)")

        id_cable = str(row[0])
        if id_cable not in self._cable_endpoints:
            return ResultadoImpacto(
                cable_desconectado=id_cable,
                nombre_cable=self._cables.get(id_cable, f"Cable #{id_cable}"))

        return self.simular_desconexion(id_cable)

    # ──────────────────────────────────────────────────────────────────────────
    # Simulación de ESCENARIO (combinación de cortes + reconexión virtual)
    # ──────────────────────────────────────────────────────────────────────────

    def _nodo_de_conector(self, id_conector: str) -> Optional[str]:
        """Resuelve un id_conector arbitrario al nodo de grafo que le
        corresponde hoy: su nodo de puerto (MI:/MO:/RI:/RG:) si participa
        de un ruteo de MATRIZ configurada o de una regla lógica, o si no,
        el nodo de equipo de siempre. Devuelve None si el conector no
        existe en la BD actual (por ejemplo, se borró después de armar el
        escenario)."""
        eq_id = self._conector_equipo.get(str(id_conector))
        if eq_id is None:
            return None
        return self._conector_a_nodo.get((eq_id, str(id_conector)), eq_id)

    def simular_escenario(self, cables_cortados=(), equipos_fallados=(),
                           conexiones_virtuales=()) -> ResultadoEscenario:
        """
        Generaliza simular_desconexion()/simular_falla_equipo() a una
        combinación arbitraria de cambios evaluada en un SOLO cálculo:

          cables_cortados:       iterable de id_cable a desconectar
          equipos_fallados:      iterable de id_equipo que fallan por completo
          conexiones_virtuales:  iterable de (id_conector_a, id_conector_b) —
                                  reconexión de emergencia propuesta, sin
                                  tocar la base (ver escenario_engine.py
                                  para la aplicación real, cuando se confirma)

        Estrategia no-destructiva (no toca self._g ni self._adj), igual
        criterio que las otras dos simulaciones:
          1. Junta en un solo frozenset TODAS las aristas a excluir: las de
             los cables cortados + las incidentes a cada equipo fallado
             (misma lógica exacta que simular_desconexion/simular_falla_equipo,
             sólo que unificada en un único cálculo — así una regla AND que
             dependa de entradas repartidas entre varios de los cambios se
             evalúa correctamente en conjunto, no cambio por cambio).
          2. Resuelve cada conexión virtual a una arista de nodo agregada
             (self._conector_a_nodo, respetando MATRIZ/reglas si el
             conector participa de alguna) y arma un frozenset aparte.
          3. Corre _alcanzables_desde() DOS veces: una sólo con los cortes
             ("antes"), y otra con cortes + conexiones virtuales
             ("después") — el diff entre ambas es el comparativo antes/
             después de la sección 7 del documento de inspiración.
        """
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")

        cables_cortados  = {str(c) for c in cables_cortados}
        equipos_fallados  = {str(e) for e in equipos_fallados}
        conexiones_virtuales = [(str(a), str(b)) for a, b in conexiones_virtuales]

        # ── 1. Aristas a excluir (cables cortados + equipos fallados) ──────
        aristas_cortes: set = set()
        for cid in cables_cortados:
            ge = self._cable_graph_endpoints.get(cid)
            if ge is not None:
                aristas_cortes.add(ge)
        for eq_id in equipos_fallados:
            for cid, (geq_src, geq_dst) in self._cable_endpoints.items():
                if geq_src == eq_id or geq_dst == eq_id:
                    aristas_cortes.add(self._cable_graph_endpoints[cid])
        aristas_excluidas = frozenset(aristas_cortes)

        # ── 2. Aristas a agregar (conexiones virtuales) ─────────────────────
        aristas_agregadas: dict[str, list[str]] = {}
        conectores_invalidos: list = []
        for id_a, id_b in conexiones_virtuales:
            nodo_a = self._nodo_de_conector(id_a)
            nodo_b = self._nodo_de_conector(id_b)
            if nodo_a is None or nodo_b is None:
                conectores_invalidos.append((id_a, id_b))
                continue
            dir_a = self._conector_direccion.get(id_a, "OUT")
            dir_b = self._conector_direccion.get(id_b, "OUT")
            # Igual criterio de dirección que _leer_bd para cables reales:
            # el extremo OUT es el origen. Si ninguno de los dos está
            # marcado OUT (tipos atípicos), se deja el orden tal como se
            # pidió — la UI avisa (no bloquea) de la incompatibilidad.
            if dir_b == "OUT" and dir_a != "OUT":
                nodo_src, nodo_dst = nodo_b, nodo_a
            else:
                nodo_src, nodo_dst = nodo_a, nodo_b
            aristas_agregadas.setdefault(nodo_src, []).append(nodo_dst)

        equipos_ok = self._nodos_a_equipos(self._alcanzables_ok)

        # ── 3a. "Antes": sólo las fallas, sin reconexión virtual ────────────
        alc_antes = self._alcanzables_desde(self._semillas_globales, aristas_excluidas)
        equipos_con_senal_antes = self._nodos_a_equipos(alc_antes)
        equipos_impactados_antes = (
            (equipos_ok - equipos_con_senal_antes) - self._fantasma
            - self._ext_nodos - equipos_fallados)

        # ── 3b. "Después": fallas + conexiones virtuales aplicadas ──────────
        alc_despues = self._alcanzables_desde(
            self._semillas_globales, aristas_excluidas, aristas_agregadas)
        equipos_con_senal_despues = self._nodos_a_equipos(alc_despues)
        equipos_impactados_despues_full = (
            (equipos_ok - equipos_con_senal_despues) - self._fantasma - equipos_fallados)
        equipos_impactados_despues = equipos_impactados_despues_full - self._ext_nodos

        equipos_recuperados = equipos_impactados_antes - equipos_impactados_despues

        cables_impactados: set = set()
        for cid, (s, d) in self._cable_endpoints.items():
            if cid in cables_cortados:
                continue
            if s in equipos_impactados_despues_full or d in equipos_impactados_despues_full:
                cables_impactados.add(cid)

        causas_regla, conectores_regla_caida = self._explicar_compuertas_caidas(alc_despues)
        return ResultadoEscenario(
            cables_cortados=cables_cortados,
            equipos_fallados=equipos_fallados,
            conexiones_virtuales=conexiones_virtuales,
            equipos_con_senal=equipos_con_senal_despues,
            equipos_impactados=equipos_impactados_despues,
            cables_impactados=cables_impactados,
            causas_regla=causas_regla,
            conectores_regla_caida=conectores_regla_caida,
            equipos_impactados_sin_reconexion=equipos_impactados_antes,
            equipos_recuperados=equipos_recuperados,
            conectores_invalidos=conectores_invalidos,
        )

    def puntos_finales(self) -> set:
        """Equipos sin cables salientes: destinos finales de la señal
        (ej. monitores, transmisores) — cuentan doble en el factor Impacto
        porque ahí es donde el corte realmente se nota."""
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")
        con_saliente = {src for src, _ in self._cable_endpoints.values()}
        return set(self._equipos) - con_saliente

    def totales(self) -> tuple:
        """(cantidad_equipos, cantidad_puntos_finales) del grafo actual,
        para normalizar el factor Impacto a escala 0-100."""
        if self._g is None:
            raise RuntimeError("Llamar a construir_grafo() primero.")
        return len(self._equipos), len(self.puntos_finales())

    # ──────────────────────────────────────────────────────────────────────────
    # API pública para la UI
    # ──────────────────────────────────────────────────────────────────────────

    def cables_salientes_de(self, equipo_id: str) -> list[dict]:
        """
        Devuelve los cables que salen del equipo (tipo OUT).
        Útil para el diálogo de selección por clic en puerto.
        Retorna lista de {"id_cable": str, "nombre": str, "dst": str, "dst_nombre": str}
        """
        resultado = []
        for cid, (src, dst) in self._cable_endpoints.items():
            if src == equipo_id:
                resultado.append({
                    "id_cable":   cid,
                    "nombre":     self._cables.get(cid, cid),
                    "dst":        dst,
                    "dst_nombre": self._equipos.get(dst, dst),
                })
        return sorted(resultado, key=lambda x: x["nombre"])

    def nombre_equipo(self, eq_id: str) -> str:
        return self._equipos.get(str(eq_id), f"Equipo #{eq_id}")

    def conectores_del_cable(self, cable_id: str):
        """(src_conector, dst_conector) del cable dado, o (None, None) si
        no se encuentra (cable_id vacío o no cargado). Usado por
        senal_estado.py para poder marcar como "caído" el conector
        puntual de un cable recién desconectado, más allá de si su
        equipo terminó en equipos_impactados (ver comentario en
        construir_grafo, _cable_endpoints_conector)."""
        return self._cable_endpoints_conector.get(str(cable_id), (None, None))

    def nombre_cable(self, cable_id: str) -> str:
        return self._cables.get(str(cable_id), f"Cable #{cable_id}")

    def esta_construido(self) -> bool:
        return self._g is not None

    def invalidar(self) -> None:
        """Forzar reconstrucción en la próxima llamada (tras cambios en BD)."""
        self._g = None
        self._semillas_globales.clear()
        self._alcanzables_ok.clear()
        self._fantasma.clear()
        self._ext_nodos.clear()
        self._nombres_extension.clear()
        self._matriz_ruteo.clear()
        self._conector_a_nodo.clear()
        self._cable_graph_endpoints.clear()
        self._node_equipo.clear()
        self._equipo_nodos.clear()
        self._compuertas.clear()
        self._compuerta_salidas.clear()
        self._adj.clear()
        self._nombre_conector.clear()
        self._conector_equipo.clear()
        self._conector_tipo.clear()
        self._conector_direccion.clear()
