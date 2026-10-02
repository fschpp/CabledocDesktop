#!/usr/bin/env python3
"""Test nativo de las funciones de escenarios del bridge (Fase A.8): escenarios_lista,
escenario_ficha y escenario_evaluar. Mismo layout temporal que test_analisis.py (no toca
data/database/ del repo) y la misma red de prueba.

Uso (desde la raíz del repo):  python3 ui_web/tests/test_escenarios.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_escenarios_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"),
                ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
shutil.copy(os.path.join(RAIZ, "ui_web", "bridge.py"), os.path.join(app, "bridge.py"))
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402

# Red de prueba (igual que test_analisis.py):
#   CAM 1 --C-001--> DIST A --C-002--> MON 1
#                           --C-003--> MON 2
#   CAM 2 --C-004--> MON 3                       (cadena independiente)
#   MON 4 sin cables.   Conectores: 1 OUT de CAM 1 · 2 IN y 3-4 OUT de DIST A · 5 IN de MON 1 · 6 IN de MON 2
#                                   7 OUT de CAM 2 · 8 IN de MON 3
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


def sql(texto, params=()):
    cx = sqlite3.connect(m.DB_PATH)
    cur = cx.execute(texto, params)
    cx.commit()
    ult = cur.lastrowid
    cx.close()
    return ult


def tablas():
    cx = sqlite3.connect(m.DB_PATH)
    r = {t[0] for t in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cx.close()
    return r


def volcado(*nombres):
    cx = sqlite3.connect(m.DB_PATH)
    r = {t: cx.execute(f'SELECT * FROM "{t}"').fetchall() for t in nombres}
    cx.close()
    return r


# ── Base sin las tablas de escenarios (bases viejas): lista vacía y NO se crean ──────────────────────
sql("DROP TABLE escenario_cambio")
sql("DROP TABLE escenario")
check(ll("escenarios_lista") == [], "sin tablas: la lista sale vacía")
check("No existe el escenario 1" in err("escenario_ficha", id_escenario=1), "sin tablas: ficha -> error claro")
check("No existe el escenario 1" in err("escenario_evaluar", id_escenario=1), "sin tablas: evaluar -> error claro")
check("escenario" not in tablas() and "escenario_cambio" not in tablas(), "sin tablas: el bridge no las crea (solo lectura)")

# ── Escenarios de prueba (se arman con Modelo, igual que el desktop) ─────────────────────────────────
m.Modelo.asegurar_tablas_escenario()
M = m.Modelo
e_falla = M.crear_escenario("Falla CAM 1", "Se cae la cámara 1")
M.agregar_cambio_escenario(e_falla, "falla_equipo", id_equipo="1")
e_recon = M.crear_escenario("Falla CAM 1 con reconexión", None)
M.agregar_cambio_escenario(e_recon, "falla_equipo", id_equipo="1")
M.agregar_cambio_escenario(e_recon, "conexion_virtual", id_conector_a="7", id_conector_b="2")
e_corte = M.crear_escenario("Corte C-002")
M.agregar_cambio_escenario(e_corte, "desconexion_cable", id_cable="2")
e_vacio = M.crear_escenario("Vacío")
e_inval = M.crear_escenario("Reconexión a un conector que ya no existe")
# FK sin forzar (como la conexión por defecto de sqlite3): simula un conector borrado a mano de la base
sql("INSERT INTO escenario_cambio(id_escenario,tipo,id_conector_a,id_conector_b,orden) VALUES (?,?,?,?,0)",
    (e_inval, "conexion_virtual", 7, 999))
sql("UPDATE escenario SET estado='aplicado' WHERE id_escenario=?", (e_corte,))

# ── Lista ────────────────────────────────────────────────────────────────────────────────────────────
lista = ll("escenarios_lista")
check(len(lista) == 5 and {x["id_escenario"] for x in lista} == {e_falla, e_recon, e_corte, e_vacio, e_inval},
      "lista: una fila por escenario")
check(all({"id_escenario", "nombre", "descripcion", "estado", "fecha", "n_cambios", "n_fallas", "n_cortes", "n_reconexiones"} <= set(x) for x in lista),
      "lista: claves de cada fila")
por_id = {x["id_escenario"]: x for x in lista}
check((por_id[e_recon]["n_cambios"], por_id[e_recon]["n_fallas"], por_id[e_recon]["n_cortes"], por_id[e_recon]["n_reconexiones"]) == (2, 1, 0, 1),
      "lista: cuenta los cambios por tipo")
check(por_id[e_vacio]["n_cambios"] == 0 and por_id[e_vacio]["n_fallas"] == 0, "lista: escenario sin cambios (LEFT JOIN, ceros)")
check(por_id[e_recon]["descripcion"] == "" and por_id[e_falla]["descripcion"] == "Se cae la cámara 1", "lista: descripción nula -> texto vacío")
check(por_id[e_corte]["estado"] == "aplicado" and por_id[e_falla]["estado"] == "borrador", "lista: estado")
# Modelo ordena sólo por fecha (segundos) y no desempata; el bridge desempata con el id más nuevo primero.
claves = [(x["fecha"], x["id_escenario"]) for x in lista]
check(claves == sorted(claves, reverse=True) and {x["id_escenario"] for x in lista} == {r[0] for r in M.devolver_todos_los_escenarios()},
      "lista: más reciente primero (fecha, y a igual fecha el id más nuevo), mismos escenarios que Modelo.devolver_todos_los_escenarios")
check(all(isinstance(x["id_escenario"], int) and isinstance(x["n_cambios"], int) for x in lista), "lista: números enteros")

# ── Ficha ────────────────────────────────────────────────────────────────────────────────────────────
f = ll("escenario_ficha", id_escenario=e_recon)
check(f["nombre"] == "Falla CAM 1 con reconexión" and f["estado"] == "borrador" and f["fecha_creacion"], "ficha: datos del escenario")
check([c["tipo"] for c in f["cambios"]] == ["falla_equipo", "conexion_virtual"], "ficha: cambios en el orden guardado")
c0, c1 = f["cambios"]
check(c0["id_equipo"] == 1 and c0["equipo"] == "CAM 1", "ficha: falla de equipo con nombre")
check((c1["id_conector_a"], c1["conector_a"], c1["id_equipo_a"], c1["equipo_a"]) == (7, "OUT 1", 5, "CAM 2")
      and (c1["id_conector_b"], c1["conector_b"], c1["id_equipo_b"], c1["equipo_b"]) == (2, "IN 1", 2, "DIST A"),
      "ficha: reconexión con conector y equipo de cada punta")
fc = ll("escenario_ficha", id_escenario=e_corte)["cambios"][0]
check(fc["tipo"] == "desconexion_cable" and fc["id_cable"] == 2 and fc["cable"] == "C-002", "ficha: corte de cable con código")
check(ll("escenario_ficha", id_escenario=e_vacio)["cambios"] == [], "ficha: escenario sin cambios")
check("No existe el escenario 999" in err("escenario_ficha", id_escenario=999), "ficha: id inexistente -> error claro")

# ── Evaluar ──────────────────────────────────────────────────────────────────────────────────────────
nombres = lambda r, estado=None: sorted(e["nombre"] for e in r["equipos"] if estado in (None, e["estado"]))  # noqa: E731

r = ll("escenario_evaluar", id_escenario=e_falla)
check(r["grafo_disponible"] and r["total_equipos"] == 7, "falla: grafo construido, 7 equipos")
check(nombres(r) == ["DIST A", "MON 1", "MON 2"] and all(e["estado"] == "impactado" for e in r["equipos"]),
      "falla: si cae CAM 1 quedan sin señal DIST A, MON 1 y MON 2 (CAM 1 no cuenta como impactado)")
check((r["n_antes"], r["n_despues"], r["n_recuperados"], r["hay_reconexion"]) == (3, 3, 0, False), "falla: sin reconexión antes = después")
check(r["n_fallados"] == 1 and r["n_cortados"] == 0, "falla: cantidad de fallas y cortes")
check(r["porcentaje_despues"] == round(100 * 3 / 7, 1) and r["porcentaje_antes"] == r["porcentaje_despues"], "falla: porcentaje del parque")
check(sorted(x["id_equipo"] for x in r["equipos"] if x["punto_final"]) == [3, 4] and r["n_puntos_finales"] == 2,
      "falla: puntos finales afectados (MON 1 y MON 2)")
check(sorted(c["codigo"] for c in r["cables_impactados"]) == ["C-001", "C-002", "C-003"],
      "falla: cables afectados = los que tocan un equipo sin señal (incluye C-001, cuyo otro extremo es CAM 1 caída)")
check(all(isinstance(e["id_equipo"], int) for e in r["equipos"]), "falla: ids int en la frontera")
check(r["cambios"] == ll("escenario_ficha", id_escenario=e_falla)["cambios"], "falla: la evaluación trae los mismos cambios que la ficha")

r = ll("escenario_evaluar", id_escenario=e_recon)
check((r["n_antes"], r["n_despues"], r["n_recuperados"], r["hay_reconexion"]) == (3, 0, 3, True),
      "reconexión: CAM 2 → DIST A recupera los 3 equipos (3 → 0)")
check(nombres(r, "recuperado") == ["DIST A", "MON 1", "MON 2"] and nombres(r, "impactado") == [], "reconexión: los 3 figuran como recuperados")
check(r["porcentaje_antes"] == round(100 * 3 / 7, 1) and r["porcentaje_despues"] == 0.0 and r["conectores_invalidos"] == [], "reconexión: porcentajes y sin conectores inválidos")
check(r["n_puntos_finales"] == 0 and r["cables_impactados"] == [], "reconexión: ya no quedan puntos finales ni cables afectados")

r = ll("escenario_evaluar", id_escenario=e_corte)
check(nombres(r) == ["MON 1"] and r["n_cortados"] == 1 and r["n_fallados"] == 0, "corte: cortar C-002 deja sin señal sólo a MON 1")
check(r["escenario"]["estado"] == "aplicado" and r["cables_impactados"] == [], "corte: el estado 'aplicado' viaja a la UI; el cable cortado no figura como impactado")

r = ll("escenario_evaluar", id_escenario=e_vacio)
check(r["grafo_disponible"] and r["equipos"] == [] and (r["n_antes"], r["n_despues"]) == (0, 0) and r["cambios"] == [],
      "vacío: sin cambios no hay impacto")

r = ll("escenario_evaluar", id_escenario=e_inval)
check(len(r["conectores_invalidos"]) == 1 and r["conectores_invalidos"][0]["id_conector_a"] == 7
      and r["conectores_invalidos"][0]["id_conector_b"] == 999 and r["conectores_invalidos"][0]["conector_b"] is None
      and r["conectores_invalidos"][0]["equipo_a"] == "CAM 2",
      "inválido: el conector inexistente se informa (con lo que sí se pudo resolver) y no rompe la simulación")
check(r["grafo_disponible"] and r["equipos"] == [], "inválido: el resto de la evaluación sigue funcionando")
check("No existe el escenario 999" in err("escenario_evaluar", id_escenario=999), "evaluar: id inexistente -> error claro")
check("falta ['id_escenario']" in err("escenario_evaluar"), "evaluar sin argumento -> error claro")
json.dumps(r)

# ── Coherencia con el motor: mismo resultado que llamar al Escenario directo ─────────────────────────
from core.escenario_engine import Escenario  # noqa: E402
esc = Escenario(m.DB_PATH, id_escenario=e_recon)
directo = esc.evaluar()
r = ll("escenario_evaluar", id_escenario=e_recon)
check({str(e["id_equipo"]) for e in r["equipos"] if e["estado"] == "recuperado"} == directo.equipos_recuperados
      and r["n_despues"] == len(directo.equipos_impactados), "el bridge coincide con Escenario.evaluar()")

# ── Solo lectura ─────────────────────────────────────────────────────────────────────────────────────
antes = volcado("equipo", "cable", "conexion", "escenario", "escenario_cambio")
for i in (e_falla, e_recon, e_corte, e_vacio, e_inval):
    ll("escenario_evaluar", id_escenario=i)
    ll("escenario_ficha", id_escenario=i)
ll("escenarios_lista")
check(volcado("equipo", "cable", "conexion", "escenario", "escenario_cambio") == antes,
      "solo lectura: evaluar no cambia equipo, cable, conexion ni escenarios (estado y fecha incluidos)")
check(volcado("cable")["cable"] == antes["cable"] and len(antes["cable"]) == 4, "solo lectura: la reconexión virtual NO crea cables")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(fallos)} fallas" if fallos else "\nTODO OK")
sys.exit(1 if fallos else 0)
