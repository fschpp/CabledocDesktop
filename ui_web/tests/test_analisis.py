#!/usr/bin/env python3
"""Test nativo de las funciones de análisis del bridge (Fase A.7): impacto, IRF,
diagnóstico de falla y linter de topología. Mismo layout temporal que test_bridge.py
(no toca data/database/ del repo).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_analisis.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_analisis_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"),
                ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
shutil.copy(os.path.join(RAIZ, "ui_web", "bridge.py"), os.path.join(app, "bridge.py"))
shutil.copy(os.path.join(RAIZ, "ui_web", "catalogos_web.py"), os.path.join(app, "catalogos_web.py"))   # bridge.py lo importa (B.2)
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402

# Topología de prueba:
#   CAM 1 --C-001--> DIST A --C-002--> MON 1
#                           --C-003--> MON 2
#   CAM 2 --C-004--> MON 3                       (cadena independiente)
#   MON 4 sin cables.   DIST A está en el rack 1.
SQL = """
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'DISTRIBUIDOR','DISTRIBUIDOR'),(3,'MONITOR',NULL);
INSERT INTO tipo_conector(id_tipo_conector,nombre,direccion) VALUES (1,'IN','IN'),(2,'OUT','OUT');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES
  (1,1,'CAM 1'),(2,2,'DIST A'),(3,3,'MON 1'),(4,3,'MON 2'),(5,1,'CAM 2'),(6,3,'MON 3'),(7,3,'MON 4');
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector) VALUES
  (1,'OUT 1',1,2),(2,'IN 1',2,1),(3,'OUT 1',2,2),(4,'OUT 2',2,2),(5,'IN',3,1),(6,'IN',4,1),
  (7,'OUT 1',5,2),(8,'IN',6,1);
INSERT INTO cable(id_cable,codigo,es_cable_conexion_interna) VALUES (1,'C-001',0),(2,'C-002',0),(3,'C-003',0),(4,'C-004',0);
INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna) VALUES
  (1,1,1,0),(2,1,2,0),(3,2,3,0),(4,2,5,0),(5,3,4,0),(6,3,6,0),(7,4,7,0),(8,4,8,0);
INSERT INTO rack(id_rack,numero,nombre,cantidad_maxima) VALUES (1,1,'Rack 1',42);
INSERT INTO posicion_en_rack(id_posicion_en_rack,id_rack,id_equipo,orificio_posicion_equipo_en_rack,unidades_de_rack_equipo)
  VALUES (1,1,2,3,1);
"""
m.Modelo.asegurar_columnas_control_idioma()  # agrega tipo_conector.direccion (la base real ya la tiene)
c = sqlite3.connect(m.DB_PATH)
c.executescript(SQL)
c.commit()
c.close()

import bridge  # noqa: E402


def ll(fn, **kw):
    r = json.loads(bridge.call(fn, json.dumps(kw)))
    assert r["ok"], f"{fn}{kw}: {r.get('error')}"
    return r["data"]


def err(fn, **kw):
    r = json.loads(bridge.call(fn, json.dumps(kw)))
    assert not r["ok"], f"{fn}{kw} debía fallar"
    return r["error"]


fallos = []


def check(cond, msg):
    print(("  ok  " if cond else "  FALLA ") + msg)
    if not cond:
        fallos.append(msg)


def volcado():
    cx = sqlite3.connect(m.DB_PATH)
    tablas = [r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    filas = {t: cx.execute(f'SELECT * FROM "{t}"').fetchall() for t in tablas}
    cx.close()
    return filas


antes = volcado()

# ── Impacto ──────────────────────────────────────────────────────────────────
ic = ll("impacto_cable", id_cable=2)
check(ic["origen"] == {"tipo": "cable", "id": 2, "nombre": "C-002"}, "impacto_cable: origen")
check([e["id_equipo"] for e in ic["equipos_impactados"]] == [3] and ic["equipos_impactados"][0]["nombre"] == "MON 1",
      "impacto_cable: cortar C-002 deja sin señal sólo a MON 1 (ids int)")
check(ic["total_equipos"] == 7 and ic["n_impactados"] == 1 and ic["porcentaje"] == round(100 / 7, 1), "impacto_cable: totales y porcentaje")

ie = ll("impacto_equipo", id_equipo=1)
check(sorted(e["id_equipo"] for e in ie["equipos_impactados"]) == [2, 3, 4], "impacto_equipo: si cae CAM 1 → DIST A, MON 1 y MON 2")
check(all(isinstance(e["id_equipo"], int) for e in ie["equipos_impactados"]), "impacto_equipo: ids int en la frontera")
check({e["nombre"] for e in ie["equipos_impactados"] if e["punto_final"]} == {"MON 1", "MON 2"}, "impacto_equipo: marca puntos finales")
check(sorted(c["id_cable"] for c in ie["cables_impactados"]) == [2, 3], "impacto_equipo: cables aguas abajo")
check(ll("impacto_equipo", id_equipo=6)["n_impactados"] == 0, "impacto_equipo: una hoja no arrastra a nadie")

ir = ll("impacto_rack", id_rack=1)
check(sorted(e["id_equipo"] for e in ir["equipos_impactados"]) == [3, 4] and ir["origen"]["nombre"] == "Rack 1",
      "impacto_rack: perder el rack con DIST A deja sin señal a MON 1 y MON 2")
check(all(f"No existe el {n} 999" in err(fn, **{k: 999}) for fn, n, k in
          (("impacto_rack", "rack", "id_rack"), ("impacto_cable", "cable", "id_cable"), ("impacto_equipo", "equipo", "id_equipo"))),
      "impacto_*: id inexistente -> error claro")

# ── IRF ──────────────────────────────────────────────────────────────────────
rk = ll("riesgo_irf")
check(len(rk["filas"]) == 7, "riesgo_irf: una fila por equipo")
check(all({"id_equipo", "nombre", "probabilidad", "impacto", "riesgo", "nivel", "cuadrante", "detalle"} <= set(f) for f in rk["filas"]),
      "riesgo_irf: claves de cada fila")
check([f["riesgo"] for f in rk["filas"]] == sorted((f["riesgo"] for f in rk["filas"]), reverse=True), "riesgo_irf: orden por riesgo descendente")
check(rk["filas"][0]["nombre"] in ("CAM 1", "DIST A"), "riesgo_irf: el mayor impacto (CAM 1 / DIST A) va primero")
check(rk["umbral_cuadrante"] == 50.0 and [n["nivel"] for n in rk["niveles"]] == ["Crítico", "Alto", "Medio", "Bajo"], "riesgo_irf: niveles y umbral")
check(ll("riesgo_irf")["filas"] == rk["filas"], "riesgo_irf: determinista")

# ── Diagnóstico ──────────────────────────────────────────────────────────────
d = ll("diagnostico", id_conector=5)   # síntoma: MON 1 sin señal
check([p["id_conector"] for p in d["pasos"]] == [5, 3, 2, 1] or [p["id_conector"] for p in d["pasos"]][0] == 5,
      "diagnostico: la cadena arranca en el síntoma")
print("      cadena:", [(p["equipo"], p["nombre"], p["es_punto_test"]) for p in d["pasos"]], d["categoria_corte"])
check(d["categoria_corte"] in ("FUENTE", "SIN_ORIGEN", "BIFURCACION", "MATRIZ_SIN_RUTEO", "PATCHERA_INCOMPLETA", "BUCLE") and d["motivo_corte"], "diagnostico: motivo de corte")
check(d["sesion"] is not None and d["sesion"]["lo"] == 0 and d["sesion"]["hi"] == len(d["pasos"]) - 1, "diagnostico: sesión inicial")
check(all(isinstance(p["id_conector"], int) and isinstance(p["id_equipo"], int) for p in d["pasos"]), "diagnostico: ids int")

# Sin puntos de test marcados: el asistente no sugiere nada y la UI deja elegir a mano dentro del segmento (lo, hi)
check(d["sesion"]["siguiente"] is None and not d["sesion"]["convergido"], "diagnostico: sin puntos de test -> sin sugerencia (elección manual)")
man = ll("diagnostico", id_conector=5, respuestas=[[1, "NO"]])["sesion"]
check(man["lo"] == 1 and man["hi"] == 3 and not man["convergido"], "diagnostico: NO en el paso 1 acota el segmento (1, 3)")
man = ll("diagnostico", id_conector=5, respuestas=[[1, "NO"], [2, "SI"]])["sesion"]
r = man["resultado"]
check(man["convergido"] and r["sin_senal"]["nombre"] == "OUT 1" and r["con_senal"]["nombre"] == "IN 1",
      "diagnostico: converge entre DIST A OUT 1 (sin señal) y DIST A IN 1 (con señal)")
check(r["sospechoso"] == "equipo", "diagnostico: extremos del mismo equipo -> sospechoso 'equipo'")
nsv = ll("diagnostico", id_conector=5, respuestas=[[1, "NO_SE"]])["sesion"]
check(nsv["lo"] == 0 and nsv["hi"] == 3 and nsv["historial"] == [[1, "NO_SE"]], "diagnostico: NO_SE no mueve el segmento")

# Con puntos de test marcados: la sugerencia automática converge sola
cx = sqlite3.connect(m.DB_PATH); cx.execute("UPDATE conector SET es_punto_test = 1 WHERE id_conector IN (2, 3)"); cx.commit(); cx.close()
ses = ll("diagnostico", id_conector=5)["sesion"]
check(ses["siguiente"] in (1, 2), "diagnostico: con puntos de test sugiere uno")
resp = []
for _ in range(10):
    if ses["convergido"] or ses["siguiente"] is None:
        break
    resp.append([ses["siguiente"], "SI"])
    ses = ll("diagnostico", id_conector=5, respuestas=resp)["sesion"]
check(ses["convergido"] and ses["resultado"] is not None and ses["resultado"]["sospechoso"] in ("equipo", "cable"),
      "diagnostico: seguir las sugerencias converge y da un sospechoso")
check("inválida" in err("diagnostico", id_conector=5, respuestas=[[1, "TAL VEZ"]]), "diagnostico: respuesta inválida -> error")
check(ll("diagnostico", id_conector=5, respuestas=resp[:-1])["sesion"]["historial"] == resp[:-1], "diagnostico: 'deshacer' = reenviar sin la última respuesta")
d1 = ll("diagnostico", id_conector=1)   # CAM 1 OUT: sin origen → cadena de 1 solo punto
check(d1["sesion"] is None and len(d1["pasos"]) == 1, "diagnostico: cadena de un solo punto -> sin sesión")
ce = ll("conectores_de_equipo", id_equipo=2)
check(ce["nombre"] == "DIST A" and [c["nombre"] for c in ce["conectores"]] == ["IN 1", "OUT 1", "OUT 2"]
      and [c["n_conexiones"] for c in ce["conectores"]] == [1, 1, 1], "conectores_de_equipo: nombre del equipo, conectores y cantidad de conexiones")
check("No existe el equipo 999" in err("conectores_de_equipo", id_equipo=999), "conectores_de_equipo: id inexistente -> error claro")

# ── Linter ───────────────────────────────────────────────────────────────────
lt = ll("linter_topologia")
check([r["id"] for r in lt["reglas"]] == ["fuera_de_patchera", "fuera_de_distribuidor", "loop_en_uso", "referencia_en_cascada"], "linter: 4 reglas en orden")
fp = next(r for r in lt["reglas"] if r["id"] == "fuera_de_patchera")["hallazgos"]
check(fp and all(isinstance(h["id_equipo"], int) for h in fp), "linter: fuera de patchera con ids int")
check(lt["con_riesgo"] is False, "linter: sin caché de riesgo -> con_riesgo False")
json.dumps(lt)

# ── Datos intactos ───────────────────────────────────────────────────────────
# Los motores de core/ pueden migrar el esquema de una base vieja (columnas nuevas, tablas auxiliares vacías,
# semillas de parametro_riesgo). Con la base real, ya al día desde el desktop, eso es un no-op. Los DATOS no cambian.
despues = volcado()
DATOS = ("equipo", "cable", "conexion", "rack", "posicion_en_rack", "tipo_conector", "marca")
check(all(antes[t] == despues[t] for t in DATOS), "datos intactos: equipo, cable, conexion, rack, posicion_en_rack, tipo_conector")
nuevas = sorted(set(despues) - set(antes))
print(f"      (informativo) tablas creadas por los motores: {nuevas}")
check(all(len(despues[t]) == 0 for t in nuevas), "las tablas que crean los motores quedan vacías")
cambiadas = sorted(t for t in antes if antes[t] != despues[t])
print(f"      (informativo) tablas migradas/sembradas por los motores: {cambiadas}")
check(set(cambiadas) <= {"conector", "tipo_equipo", "parametro_riesgo", "_migracion_hardcode_idioma"},
      "solo se tocan tablas de migración/semilla conocidas")

# Errores: JSON, nunca excepción
check("No existe el conector 999" in err("diagnostico", id_conector=999), "diagnostico: conector inexistente -> error claro")
check("falta ['id_cable']" in err("impacto_cable"), "impacto_cable sin argumento -> error claro")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(fallos)} fallas" if fallos else "\nTODO OK")
sys.exit(1 if fallos else 0)
