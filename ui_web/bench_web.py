"""Benchmark de core/ dentro de Pyodide (Fase 0.6/0.7). Misma lógica que
tests/bench_core.py, pero con reporte de progreso. No escribe en la base."""
import sys, time, json, hashlib, sqlite3
sys.path.insert(0, "/app")

ESPERADO = {  # hashes de CPython nativo sobre el db.db del 2026-09-28
    "simular_10_fallas": "21002f5a158c", "irf_calcular_todos": "7d4526bfe00d",
    "criticidad_todos": "882705e630fd", "linter_patchera": "e093e1105325",
    "linter_distribuidor": "a1901c9f0f98", "modelo_equipos": "f55cb6c6ace5",
}

def _h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()[:12]

def run(report=print):
    t_imp = time.perf_counter()
    import core.modelo as m
    from core.graph_impact import GraphImpactAnalyzer
    from core.risk_engine import RiskEngine, calcular_criticidad_todos
    from core.linter_topologia import (equipos_fuera_de_patchera_priorizados,
                                       equipos_fuera_de_distribuidor_priorizados)
    R = {"import_core": {"s": round(time.perf_counter() - t_imp, 3)}}

    def T(name, fn):
        report(f"… {name}")
        t = time.perf_counter(); v = fn()
        R[name] = {"s": round(time.perf_counter() - t, 3), "hash": _h(v)}
        if name in ESPERADO:
            R[name]["ok"] = (R[name]["hash"] == ESPERADO[name])
        return v

    g = GraphImpactAnalyzer(m.DB_PATH)
    T("construir_grafo", lambda: (g.construir_grafo(), 1)[1])
    ids = [r[0] for r in sqlite3.connect(m.DB_PATH).execute(
        "select id_equipo from equipo order by id_equipo limit 10")]
    def sims():
        out = []
        for i in ids:
            r = g.simular_escenario(equipos_fallados={str(i)})
            out.append([sorted(map(str, r.equipos_impactados)),
                        sorted(map(str, r.equipos_con_senal)),
                        sorted(map(str, r.cables_impactados))])
        return out
    T("simular_10_fallas", sims)
    def irf():
        d = RiskEngine(m.DB_PATH).calcular_todos(persistir=False)
        return {str(k): (round(v, 6) if isinstance(v, float) else str(v)) for k, v in d.items()}
    T("irf_calcular_todos", irf)
    T("criticidad_todos", lambda: [str(x) for x in calcular_criticidad_todos(m.DB_PATH)])
    T("linter_patchera", lambda: [str(x) for x in equipos_fuera_de_patchera_priorizados(m.DB_PATH)])
    T("linter_distribuidor", lambda: [str(x) for x in equipos_fuera_de_distribuidor_priorizados(m.DB_PATH)])
    T("modelo_equipos", lambda: [tuple(map(str, x)) for x in
        m.Modelo._query("select * from conexiones_ambos_extremos limit 500")])
    return R
