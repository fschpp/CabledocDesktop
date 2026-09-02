"""
senal_propagation.py — Motor de propagación de señal para CableDoc
====================================================================
Fase 3 de plan_entidad_senal.md.

Decisión de arquitectura respecto del plan original: el plan hablaba de
"extender graph_impact.py". En la práctica se optó por un módulo aparte
porque el problema es distinto al que resuelve GraphImpactAnalyzer:
  - graph_impact.py responde "¿qué se cae si corto este cable/equipo?"
    (alcanzabilidad + compuertas AND/OR sobre GraphQLite, pensado para
    miles de simulaciones puntuales muy rápidas).
  - Este módulo responde "¿qué señal hay en cada conector, dado lo que
    se cargó a mano en las fuentes?" (propagación de una etiqueta de
    contenido, una sola pasada sobre todo el grafo). No necesita
    GraphQLite: la escala (miles de conectores) resuelve cómodo en
    Python puro con una relajación iterativa tipo Bellman-Ford.
Mezclarlos hubiera acoplado dos motores con ciclos de vida distintos
(uno se reconstruye por sesión de diagrama, este se corre bajo demanda
desde el menú) a costa de legibilidad, sin ganancia real de código
compartido: lo único reutilizado a propósito es la MISMA vista
CONEXIONES_AMBOS_EXTREMOS y la MISMA lógica de "OUT en el string del
tipo de conector define el sentido del cable" que ya usa
GraphImpactAnalyzer._leer_bd(), para que ambos motores nunca discrepen
sobre la dirección de un cable.

Reglas de propagación (ver plan_entidad_senal.md, sección 2):
  - Semillas: conectores con senal_en_conector.origen='MANUAL'.
  - A través de un cable: la señal viaja sin cambios del conector OUT
    de un equipo al conector IN del equipo del otro extremo (el cable
    en sí no transforma nada).
  - Dentro de un equipo, según tipo_equipo.rol_senal:
      FUENTE       → no hereda de ningún IN (si su OUT no está
                     etiquetado a mano, ese OUT queda sin señal).
      DISTRIBUIDOR → sólo se propaga cuando el equipo tiene EXACTAMENTE
                     un conector IN (semántica real de un DA: una
                     entrada, N salidas idénticas). Si tiene más de un
                     IN — típicamente un jack de patchera con pares
                     A/B, IN+OUT en ambos sentidos, NO un
                     amplificador de distribución real — no se asume
                     ninguna correspondencia IN→OUT y el equipo queda
                     marcado como "ambiguo" en vez de propagar (ver
                     ResultadoPropagacion.equipos_distribuidor_ambiguo).
                     EXCEPCIÓN: si tipo_equipo.rol_senal es 'PATCHERA',
                     no se aplica esta regla general — se usa la lógica
                     de bypass full-normal descripta abajo, que
                     reutiliza el mismo criterio ya probado en
                     pantallas_avanzadas.DiagramaConexiones.
                     _calc_conexion_interna() (botón "🔌 Conexión
                     interna" del diagrama).
      ENRUTADOR    → cada conector OUT hereda únicamente del IN que
                     matriz_ruteo tiene asignado para esa salida; si el
                     equipo no tiene ruteo guardado, no se propaga nada
                     a través de él (no hay forma de saber qué va a
                     cada salida).
      PROCESADOR   → no propaga IN→OUT (la salida es señal nueva, se
                     exige carga manual — DSK, encoder, decoder, etc).
      CONSUMIDOR   → no tiene salidas de señal, nada que propagar.

  Caso especial — equipos rol_senal='PATCHERA' (bypass full-normal):
      Un jack de patchera típico expone 4 conectores, cada uno con una
      FUNCIÓN abstracta (conector.id_funcion_patchera → tabla
      funcion_patchera — ver plan_desarrollo_funcion_patchera.md):
      BACK_ENTRADA(IN), BACK_SALIDA(OUT), FRONT_DERIVACION(OUT),
      FRONT_INSERCION(IN). YA NO se identifican por prefijo de nombre
      de conector (A_BACK/B_BACK/A_FRONT/B_FRONT era la convención de
      UNA sola marca de patchera de video; un patch module de audio con
      "01_BACK"/"25_BACK" quedaba mal detectado, o directamente afuera,
      con el criterio anterior) — se identifican EXCLUSIVAMENTE por esa
      columna, cargada a mano en la ficha del equipo o del molde de
      catálogo, exactamente igual que _calc_conexion_interna en
      pantallas_avanzadas.py — mismo criterio en los dos lugares, para
      que el diagrama y el motor de propagación nunca digan cosas
      distintas sobre el mismo jack.
      Comportamiento eléctrico real de un jack full-normal:
        - Si NINGÚN frente tiene un cable parcheado: BACK_ENTRADA y
          BACK_SALIDA quedan unidas por bypass interno (la señal entra
          por atrás de un lado y sale por atrás del otro, de largo —
          los frentes quedan sin nada porque no hay ningún cable ahí).
          Es el caso más común en una instalación real: la mayoría de
          los jacks no tienen nada parcheado al frente en operación
          normal.
        - Si FRONT_DERIVACION tiene un cable: se rompe el bypass de ese
          lado, BACK_ENTRADA pasa a salir por FRONT_DERIVACION en vez
          de por BACK_SALIDA.
        - Si FRONT_INSERCION tiene un cable: análogo, FRONT_INSERCION
          pasa a alimentar BACK_SALIDA en vez de recibir del bypass.
        - Si ambos frentes tienen cable ("loop externo" en la UI): cada
          lado sale por su propio frente, ninguno usa el bypass.
      Si el equipo no tiene las 4 funciones asignadas todavía (ver
      Modelo.listar_patcheras_sin_funcion_completa para ubicarlos), se
      degrada exactamente igual que antes: no propaga por él y queda
      marcado ambiguo — nunca se adivina por nombre como alternativa.
  - Conflicto: un conector recibe, por rutas distintas, más de una
    señal candidata distinta. Se marca el conector con conflicto=True
    y NO se pisa lo que ya tenía (si era MANUAL, se respeta tal cual;
    si no tenía nada, queda sin resolver) — el usuario decide.

Este motor NO escribe en la base de datos por sí solo. calcular()
devuelve un ResultadoPropagacion en memoria; Modelo.aplicar_propagacion_
senal() es quien persiste, y sólo los conectores que el usuario elija
aceptar (ver _DialogoPropagacionSenal en cabledoc.py) — así se respeta
el modo "sugerencia, el usuario confirma" del plan.
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PropuestaConector:
    id_conector:   str
    nombre_conector: str
    id_equipo:     str
    nombre_equipo: str
    id_senal:      Optional[str] = None
    nombre_senal:  Optional[str] = None
    id_formato:    Optional[str] = None
    nombre_formato: Optional[str] = None
    origen:        str = ""          # "" (sin resolver) | MANUAL | PROPAGADA
    conflicto:     bool = False
    # Sólo tiene sentido mostrar/aplicar una propuesta si es PROPAGADA
    # nueva (no existía nada antes) o si difiere de lo que ya había
    # cargado a mano — eso lo decide la UI comparando contra lo vigente.


@dataclass
class ResultadoPropagacion:
    propuestas: dict = field(default_factory=dict)   # id_conector -> PropuestaConector
    convergio:  bool = True    # False si se alcanzó el tope de iteraciones
                                 # sin estabilizar (posible ciclo de ruteo)
    equipos_enrutador_sin_matriz: set = field(default_factory=set)
    # Equipos rol_senal=DISTRIBUIDOR con más de un conector IN — no se
    # asume ninguna correspondencia IN→OUT (ver comentario de cabecera).
    # Candidatos típicos para revisar el rol asignado (probablemente
    # deberían ser PROCESADOR, o directamente no son equipos de
    # distribución real sino patcheras/pasantes).
    equipos_distribuidor_ambiguo: set = field(default_factory=set)

    @property
    def conflictos(self):
        return [p for p in self.propuestas.values() if p.conflicto]

    @property
    def propagadas(self):
        return [p for p in self.propuestas.values()
                if p.origen == "PROPAGADA" and not p.conflicto]


class PropagadorSenal:
    """
    Uso:
        prop = PropagadorSenal(db_path)
        resultado = prop.calcular()
        # revisar resultado.propagadas / resultado.conflictos con el usuario…
        Modelo.aplicar_propagacion_senal(ids_conector_aceptados, resultado)
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    # ──────────────────────────────────────────────────────────────────
    def calcular(self, max_iteraciones: int = None) -> ResultadoPropagacion:
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        # Tablas de señal — aseguradas acá también por si este módulo se
        # usa antes de que Modelo.asegurar_tablas_senal() haya corrido en
        # el resto de la app (mismo criterio que graph_impact._leer_bd
        # con matriz_ruteo/regla_logica).
        cur.execute(
            "CREATE TABLE IF NOT EXISTS senal ("
            "  id_senal       INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre         TEXT NOT NULL,"
            "  tipo_contenido TEXT,"
            "  descripcion    TEXT,"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS tipo_formato_senal ("
            "  id_formato     INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre         TEXT NOT NULL,"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS senal_en_conector ("
            "  id_senal_en_conector INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_conector    INTEGER NOT NULL UNIQUE,"
            "  id_senal       INTEGER NOT NULL,"
            "  id_formato     INTEGER,"
            "  origen         TEXT NOT NULL DEFAULT 'MANUAL' "
            "                 CHECK (origen IN ('MANUAL','PROPAGADA')),"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        cols_tipo = [c[1] for c in cur.execute(
            "PRAGMA table_info(tipo_equipo)").fetchall()]
        if "rol_senal" not in cols_tipo:
            cur.execute(
                "ALTER TABLE tipo_equipo ADD COLUMN rol_senal TEXT "
                "DEFAULT 'DISTRIBUIDOR'")
            db.commit()
        # Población defensiva de rol_senal='PATCHERA' (idempotente, mismo
        # criterio que Modelo.asegurar_columnas_control_idioma) — antes de
        # este cambio el caso especial de patchera se detectaba por
        # tipo_equipo.nombre directamente, así que no dependía de que esta
        # UPDATE ya hubiera corrido en algún otro lado. Al pasar a mirar
        # rol_senal=='PATCHERA' (Fase C de plan_desarrollo_funcion_
        # patchera.md, ver más abajo), hay que garantizar acá mismo que el
        # dato esté poblado, para que este módulo siga funcionando solo
        # (sin GTK, sin depender de que cabledoc.py haya arrancado antes)
        # exactamente como ya lo documenta la cabecera del archivo.
        cur.execute(
            "UPDATE tipo_equipo SET rol_senal='PATCHERA' "
            "WHERE UPPER(nombre)='MODULO PATCHERA' "
            "AND (rol_senal IS NULL OR rol_senal='DISTRIBUIDOR')")
        db.commit()

        # ── Conectores IN/OUT (los únicos que participan de la señal de
        # contenido; REF*, ETHERNET, SERIAL, GPI/O, USB quedan afuera) ──
        cur.execute("""
            SELECT c.id_conector AS id, c.id_equipo, c.nombre,
                   UPPER(tc.nombre) AS tipo
            FROM conector c
            JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE UPPER(tc.nombre) IN ('IN','OUT')
        """)
        conectores = {}
        ins_por_equipo: dict[str, set] = {}
        outs_por_equipo: dict[str, set] = {}
        nombre_conector = {}
        equipo_de_conector = {}
        for r in cur.fetchall():
            cid = str(r["id"])
            eid = str(r["id_equipo"])
            conectores[cid] = r["tipo"]
            nombre_conector[cid] = r["nombre"]
            equipo_de_conector[cid] = eid
            if r["tipo"] == "IN":
                ins_por_equipo.setdefault(eid, set()).add(cid)
            else:
                outs_por_equipo.setdefault(eid, set()).add(cid)

        # ── Equipos + rol_senal (default DISTRIBUIDOR, igual que
        # Modelo.devolver_rol_senal_tipo_equipo) ──
        cur.execute("""
            SELECT e.id_equipo AS id, e.nombre,
                   COALESCE(te.rol_senal, 'DISTRIBUIDOR') AS rol_senal
            FROM equipo e
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
        """)
        nombre_equipo = {}
        rol_por_equipo = {}
        for r in cur.fetchall():
            eid = str(r["id"])
            nombre_equipo[eid] = r["nombre"]
            rol_por_equipo[eid] = (r["rol_senal"] or "DISTRIBUIDOR").upper()

        # ── Cables dirigidos (misma vista y misma lógica de sentido que
        # GraphImpactAnalyzer._leer_bd, para no discrepar entre motores) ──
        cur.execute("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
        cable_edges = []
        seen = set()
        for r in cur.fetchall():
            id_cable = str(r["id_cable"])
            if id_cable in seen:
                continue
            id_con_a = str(r["id_conector:1"])
            id_con_b = str(r["id_conector"])
            if id_con_a not in conectores or id_con_b not in conectores:
                continue  # extremo no es IN/OUT (ej. REFIN/REFOUT) — no participa
            if conectores.get(id_con_a) == "OUT":
                src, dst = id_con_a, id_con_b
            else:
                src, dst = id_con_b, id_con_a
            seen.add(id_cable)
            cable_edges.append((src, dst))

        # ── matriz_ruteo (para equipos ENRUTADOR) ──
        cur.execute(
            "CREATE TABLE IF NOT EXISTS matriz_ruteo ("
            "  id_conector_salida  INTEGER PRIMARY KEY,"
            "  id_conector_entrada INTEGER,"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        cur.execute("SELECT id_conector_salida, id_conector_entrada "
                     "FROM matriz_ruteo")
        ruteo_por_salida = {str(r["id_conector_salida"]): (
            str(r["id_conector_entrada"])
            if r["id_conector_entrada"] is not None else None)
            for r in cur.fetchall()}

        cur.execute("SELECT DISTINCT id_conector FROM conexion")
        conectores_con_cable = {str(r[0]) for r in cur.fetchall()}

        # ── funcion_patchera (Fase C de plan_desarrollo_funcion_patchera.md):
        # los 4 puertos de un módulo PATCHERA se identifican EXCLUSIVAMENTE
        # por conector.id_funcion_patchera — ya no se adivina por prefijo de
        # nombre de conector (A_BACK/B_BACK/A_FRONT/B_FRONT era la
        # convención de UNA marca de patchera; un patch module de audio con
        # "01_BACK"/"25_BACK" quedaba mal detectado o directamente afuera).
        cur.execute(
            "CREATE TABLE IF NOT EXISTS funcion_patchera ("
            "  id_funcion_patchera INTEGER PRIMARY KEY,"
            "  clave TEXT UNIQUE NOT NULL, nombre_es TEXT NOT NULL,"
            "  direccion TEXT NOT NULL, descripcion TEXT)")
        cols_con = [c[1] for c in cur.execute(
            "PRAGMA table_info(conector)").fetchall()]
        puertos_patchera_por_equipo: dict[str, dict[str, str]] = {}
        if "id_funcion_patchera" in cols_con:
            cur.execute("""
                SELECT c.id_conector AS id, c.id_equipo, fp.clave
                FROM conector c
                LEFT JOIN funcion_patchera fp
                  ON fp.id_funcion_patchera = c.id_funcion_patchera
                WHERE c.id_funcion_patchera IS NOT NULL
            """)
            for r in cur.fetchall():
                puertos_patchera_por_equipo.setdefault(
                    str(r["id_equipo"]), {})[r["clave"]] = str(r["id"])

        db.close()

        # ── Aristas internas de cada equipo, según su rol ──
        internal_edges = []
        equipos_enrutador_sin_matriz = set()
        equipos_distribuidor_ambiguo = set()
        FUNCIONES_PATCHERA = ("BACK_ENTRADA", "BACK_SALIDA",
                              "FRONT_DERIVACION", "FRONT_INSERCION")
        for eid, rol in rol_por_equipo.items():
            ins = ins_por_equipo.get(eid, set())
            outs = outs_por_equipo.get(eid, set())
            if not outs:
                continue

            if rol == "PATCHERA":
                # Caso especial: bypass full-normal (ver docstring de
                # cabecera). Prevalece sobre cualquier otra interpretación
                # de rol_senal — un jack de patchera no es conceptualmente
                # un DISTRIBUIDOR aunque la columna diga eso por default.
                puertos = puertos_patchera_por_equipo.get(eid, {})
                if not all(f in puertos for f in FUNCIONES_PATCHERA):
                    equipos_distribuidor_ambiguo.add(eid)
                    continue
                derivacion_usada = puertos["FRONT_DERIVACION"] in conectores_con_cable
                insercion_usada = puertos["FRONT_INSERCION"] in conectores_con_cable
                if not derivacion_usada and not insercion_usada:
                    internal_edges.append(
                        (puertos["BACK_ENTRADA"], puertos["BACK_SALIDA"]))
                if derivacion_usada:
                    internal_edges.append(
                        (puertos["BACK_ENTRADA"], puertos["FRONT_DERIVACION"]))
                if insercion_usada:
                    internal_edges.append(
                        (puertos["FRONT_INSERCION"], puertos["BACK_SALIDA"]))
                continue

            if rol == "DISTRIBUIDOR":
                if len(ins) == 1:
                    cin = next(iter(ins))
                    for cout in outs:
                        internal_edges.append((cin, cout))
                elif len(ins) > 1:
                    equipos_distribuidor_ambiguo.add(eid)
                # len(ins) == 0: nada que propagar, no es ambiguo, sólo vacío.
            elif rol == "ENRUTADOR":
                tiene_ruteo = any(cout in ruteo_por_salida for cout in outs)
                if not tiene_ruteo:
                    equipos_enrutador_sin_matriz.add(eid)
                    continue
                for cout in outs:
                    cin = ruteo_por_salida.get(cout)
                    if cin:
                        internal_edges.append((cin, cout))
            # FUENTE / PROCESADOR / CONSUMIDOR: sin aristas internas.

        # ── Semillas: señal cargada a mano ──
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        cur.execute("""
            SELECT sec.id_conector, sec.id_senal, s.nombre AS nombre_senal,
                   sec.id_formato, f.nombre AS nombre_formato, sec.origen
            FROM senal_en_conector sec
            JOIN senal s ON s.id_senal = sec.id_senal
            LEFT JOIN tipo_formato_senal f ON f.id_formato = sec.id_formato
        """)
        valores = {}   # id_conector -> dict(id_senal,nombre_senal,id_formato,nombre_formato,origen)
        for r in cur.fetchall():
            cid = str(r["id_conector"])
            valores[cid] = {
                "id_senal": str(r["id_senal"]),
                "nombre_senal": r["nombre_senal"],
                "id_formato": str(r["id_formato"]) if r["id_formato"] is not None else None,
                "nombre_formato": r["nombre_formato"],
                "origen": r["origen"],
            }
        db.close()

        conflicto = set()
        edges = cable_edges + internal_edges

        if max_iteraciones is None:
            max_iteraciones = max(len(conectores), 10) + 5

        convergio = True
        for _ in range(max_iteraciones):
            cambio = False
            for u, v in edges:
                val_u = valores.get(u)
                if not val_u or u in conflicto:
                    continue
                if v not in valores:
                    valores[v] = {
                        "id_senal": val_u["id_senal"],
                        "nombre_senal": val_u["nombre_senal"],
                        "id_formato": val_u["id_formato"],
                        "nombre_formato": val_u["nombre_formato"],
                        "origen": "PROPAGADA",
                    }
                    cambio = True
                elif valores[v]["id_senal"] != val_u["id_senal"]:
                    if v not in conflicto:
                        conflicto.add(v)
                        cambio = True
            if not cambio:
                break
        else:
            convergio = False

        # ── Armar resultado ──
        propuestas = {}
        for cid, tipo in conectores.items():
            eid = equipo_de_conector[cid]
            val = valores.get(cid)
            p = PropuestaConector(
                id_conector=cid,
                nombre_conector=nombre_conector.get(cid, ""),
                id_equipo=eid,
                nombre_equipo=nombre_equipo.get(eid, ""),
                conflicto=(cid in conflicto),
            )
            if val:
                p.id_senal = val["id_senal"]
                p.nombre_senal = val["nombre_senal"]
                p.id_formato = val["id_formato"]
                p.nombre_formato = val["nombre_formato"]
                p.origen = val["origen"]
            propuestas[cid] = p

        return ResultadoPropagacion(
            propuestas=propuestas,
            convergio=convergio,
            equipos_enrutador_sin_matriz=equipos_enrutador_sin_matriz,
            equipos_distribuidor_ambiguo=equipos_distribuidor_ambiguo,
        )
