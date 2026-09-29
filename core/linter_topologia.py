"""
linter_topologia.py — Linter de reglas de diseño de topología para CableDoc
=============================================================================
Fase 3 de plan_inteligencia_implicita_v1.md: convierte reglas de diseño que
hoy sólo viven en la cabeza de Fede (equipos fuera de patchera, referencia
en cascada, loop en uso) en chequeos automáticos sobre
datos que ya están cargados — mismo espíritu que risk_engine.py /
graph_impact.py / escenario_engine.py: no rediseña nada, cruza lo que ya
existe.

La entrega de la Fase 3 implementó sólo la primera regla: "equipos fuera de
patchera" (equipamiento cableado directo, sin pasar por un panel de
parcheo — Modelo.devolver_equipos_fuera_de_patchera(), Fase 3.1). La Fase
4.2 agrega la regla "loop en uso" (loops_en_uso_priorizados) y la Fase 2.2
la regla "referencia en cascada" (referencia_en_cascada_priorizada), ambas
al final del módulo.

Decisión de diseño (Fase 3.2 — priorización): el plan original preveía una
función nueva de Fase 1 ("calcular_criticidad_todos", blast radius vía
escenario_engine.py) para ordenar los hallazgos del linter por gravedad
real. Esa función todavía no existe, y no hace falta escribirla para esta
entrega: el "riesgo" (probabilidad × impacto, 0-100) que ya calcula
risk_engine.RiskEngine —donde el factor Impacto sale de
GraphImpactAnalyzer.simular_falla_equipo(), exactamente el mismo cálculo
de blast radius que pedía la Fase 1.1— queda cacheado en
riesgo_equipo_cache y se expone en lote vía
Modelo.devolver_riesgo_todos_los_equipos(). Se reutiliza tal cual (ver
ways-of-working: "extender sistemas existentes en vez de crear
paralelos") en lugar de duplicar el cálculo.
"""

from __future__ import annotations

from core.modelo import Modelo


def equipos_fuera_de_patchera_priorizados(db_path=None) -> list:
    """Fase 3.1 (detección) + 3.2 (priorización): cruza
    Modelo.devolver_equipos_fuera_de_patchera() con el último cálculo de
    riesgo cacheado (ver docstring del módulo) para que un equipo CRÍTICO
    y fuera de patchera aparezca primero — es el caso que realmente
    importa revisar, no sólo "existe un cable directo".

    `db_path` se acepta por simetría con el resto de los engines
    (risk_engine.RiskEngine, GraphImpactAnalyzer) aunque hoy no se use —
    Modelo ya apunta a la única base activa del proceso.

    Devuelve una lista de dicts, ordenada por riesgo descendente (los
    equipos sin riesgo calculado todavía — nunca se corrió "🔺 Recalcular
    riesgo" — van al final, no se excluyen):
        {"id_equipo": str, "nombre": str,
         "riesgo": float | None, "nivel": str | None}
    """
    equipos = Modelo.devolver_equipos_fuera_de_patchera()
    if not equipos:
        return []

    riesgo_por_equipo = Modelo.devolver_riesgo_todos_los_equipos()  # {id: (riesgo, nivel)}

    resultado = []
    for id_eq, nombre in equipos:
        riesgo, nivel = riesgo_por_equipo.get(str(id_eq), (None, None))
        resultado.append({
            "id_equipo": str(id_eq), "nombre": nombre,
            "riesgo": riesgo, "nivel": nivel,
        })

    resultado.sort(key=lambda r: (r["riesgo"] is None, -(r["riesgo"] or 0)))
    return resultado


def ids_equipos_fuera_de_patchera_priorizados(db_path=None) -> list:
    """Atajo para la UI (ver ui_gtk/equipos_ui.py,
    filtro_pendiente='fuera_de_patchera'): sólo los ids, ya en el orden de
    prioridad de equipos_fuera_de_patchera_priorizados()."""
    return [r["id_equipo"]
            for r in equipos_fuera_de_patchera_priorizados(db_path)]


def equipos_fuera_de_distribuidor_priorizados(db_path=None) -> list:
    """Regla "Fuera de distribuidor": cruza
    Modelo.devolver_equipos_fuera_de_distribuidor() con el riesgo cacheado
    (misma fuente y mismo criterio que equipos_fuera_de_patchera_priorizados)
    para que un equipo crítico cuya salida no entra directo a un
    distribuidor aparezca primero. Los equipos sin riesgo calculado todavía
    van al final, no se excluyen. `db_path` se acepta por simetría.

    Devuelve [{"id_equipo": str, "nombre": str, "riesgo": float | None,
    "nivel": str | None}, ...].
    """
    equipos = Modelo.devolver_equipos_fuera_de_distribuidor()
    if not equipos:
        return []
    riesgo_por_equipo = Modelo.devolver_riesgo_todos_los_equipos()  # {id: (riesgo, nivel)}
    resultado = []
    for id_eq, nombre in equipos:
        riesgo, nivel = riesgo_por_equipo.get(str(id_eq), (None, None))
        resultado.append({
            "id_equipo": str(id_eq), "nombre": nombre,
            "riesgo": riesgo, "nivel": nivel,
        })
    resultado.sort(key=lambda r: (r["riesgo"] is None, -(r["riesgo"] or 0)))
    return resultado


def ids_equipos_fuera_de_distribuidor_priorizados(db_path=None) -> list:
    """Atajo para la UI (ver ui_gtk/equipos_ui.py,
    filtro_pendiente='fuera_de_distribuidor'): sólo los ids, en el orden de
    prioridad de equipos_fuera_de_distribuidor_priorizados()."""
    return [r["id_equipo"]
            for r in equipos_fuera_de_distribuidor_priorizados(db_path)]


def loops_en_uso_priorizados(db_path=None) -> list:
    """Fase 4.2 (detección) del linter: cruza Modelo.devolver_loops_en_uso()
    con el riesgo cacheado del EQUIPO dueño de la salida loop (mismo
    criterio y misma fuente que equipos_fuera_de_patchera_priorizados — ver
    docstring del módulo) para que un loop en uso en un equipo crítico
    aparezca primero. A igual riesgo, primero el que tiene más cables.

    Regla (revisada 2026-09-28): toda salida loop con un cable real
    conectado está mal vista, vaya a un equipo, a una patchera, a un
    enrutador o a un FANTASMA. Ver el docstring de
    Modelo.devolver_loops_en_uso().

    `db_path` se acepta por simetría con el resto de los engines, aunque
    hoy no se use.

    Devuelve los mismos dicts que Modelo.devolver_loops_en_uso() más las
    claves "riesgo" (float | None) y "nivel" (str | None) del equipo dueño;
    los equipos sin riesgo calculado todavía van al final, no se excluyen.
    """
    loops = Modelo.devolver_loops_en_uso()
    if not loops:
        return []

    riesgo_por_equipo = Modelo.devolver_riesgo_todos_los_equipos()  # {id: (riesgo, nivel)}
    for r in loops:
        r["riesgo"], r["nivel"] = riesgo_por_equipo.get(
            str(r["id_equipo"]), (None, None))

    # sort estable: el orden por equipo/nombre de Modelo desempata.
    loops.sort(key=lambda r: (r["riesgo"] is None, -(r["riesgo"] or 0),
                              -r["n_cables"]))
    return loops


def ids_equipos_loop_en_uso_priorizados(db_path=None) -> list:
    """Atajo para la UI (ver ui_gtk/equipos_ui.py,
    filtro_pendiente='loop_en_uso', Fase 4.3): ids (str) de los EQUIPOS
    dueños de al menos una salida loop en uso, sin repetir, en el orden de
    prioridad de loops_en_uso_priorizados() (primero el de más riesgo)."""
    vistos = []
    for r in loops_en_uso_priorizados(db_path):
        id_eq = str(r["id_equipo"])
        if id_eq not in vistos:
            vistos.append(id_eq)
    return vistos


def referencia_en_cascada_priorizada(db_path=None) -> list:
    """Fase 2.1 (detección) + 2.2 (priorización) del linter: cruza
    Modelo.devolver_referencia_en_cascada() con el blast radius del EQUIPO
    dueño de la salida de referencia, para ordenar por gravedad real y no
    sólo por existencia de la cascada: si el equipo que re-emite la
    referencia falla, arrastra todo lo que cuelga de él, así que importa
    cuánto pierde el parque cuando ese equipo cae.

    El blast radius sale de risk_engine.calcular_criticidad_todos() (Fase
    1.1), reusada tal cual — no se reimplementa ni se vuelve a simular
    nada (ver docstring del módulo). Desempate: riesgo IRF cacheado del
    mismo equipo (probabilidad × impacto, la misma fuente que las otras
    reglas del linter) y luego cantidad de cables; el orden natural por
    equipo/conector de Modelo desempata al final (sort estable).

    `db_path` se acepta por simetría con el resto de los engines, aunque
    hoy no se use.

    Devuelve los mismos dicts que Modelo.devolver_referencia_en_cascada()
    más las claves "impacto" (float | None: blast radius 0-100 del equipo
    dueño), "riesgo" (float | None) y "nivel" (str | None). Los equipos sin
    cálculo de riesgo corrido todavía (nunca se ejecutó "🔺 Recalcular
    riesgo") van al final con esas claves en None, no se excluyen.
    """
    hallazgos = Modelo.devolver_referencia_en_cascada()
    if not hallazgos:
        return []

    # Import diferido: risk_engine importa Modelo, y mantiene este módulo
    # liviano para quien sólo usa las reglas que no necesitan el IRF.
    from core.risk_engine import calcular_criticidad_todos
    impacto_por_equipo = dict(calcular_criticidad_todos(db_path))  # {id(str): blast_radius}
    riesgo_por_equipo = Modelo.devolver_riesgo_todos_los_equipos()  # {id(str): (riesgo, nivel)}
    for r in hallazgos:
        id_eq = str(r["id_equipo"])
        r["impacto"] = impacto_por_equipo.get(id_eq)
        r["riesgo"], r["nivel"] = riesgo_por_equipo.get(id_eq, (None, None))

    hallazgos.sort(key=lambda r: (r["impacto"] is None, -(r["impacto"] or 0),
                                  r["riesgo"] is None, -(r["riesgo"] or 0),
                                  -r["n_cables"]))
    return hallazgos


def ids_equipos_referencia_en_cascada_priorizados(db_path=None) -> list:
    """Atajo para la UI (ver ui_gtk/equipos_ui.py,
    filtro_pendiente='referencia_en_cascada', Fase 2.3): ids (str) de los
    EQUIPOS dueños de al menos una salida de referencia en cascada, sin
    repetir, en el orden de prioridad de referencia_en_cascada_priorizada()
    (primero el de mayor blast radius)."""
    vistos = []
    for r in referencia_en_cascada_priorizada(db_path):
        id_eq = str(r["id_equipo"])
        if id_eq not in vistos:
            vistos.append(id_eq)
    return vistos
