#!/usr/bin/env python3
"""Test nativo de bridge.busqueda_indice (Fase A.9, búsqueda global). Mismo layout temporal que
test_escenarios.py (no toca data/database/ del repo).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_busqueda.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_busqueda_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"),
                ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
shutil.copy(os.path.join(RAIZ, "ui_web", "bridge.py"), os.path.join(app, "bridge.py"))
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402

SQL = """
INSERT INTO marca(id_marca,nombre) VALUES (1,'Sony'),(2,'Blackmagic');
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'MATRIZ','DISTRIBUIDOR');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC'),(2,'XLR');
INSERT INTO tipo_cable(id_tipo_cable,nombre) VALUES (1,'RG59');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES (0,2,'SIN EQUIPO');
INSERT INTO equipo(id_equipo,id_tipo_equipo,id_marca,num_inventario,num_serie,modelo,nombre)
  VALUES (1,1,1,100,'WT-77','HDC-3500','CÁMARA 1'),(2,2,2,101,'S2','Videohub','MATRIZ A'),
         (3,1,1,102,NULL,'HDC-3500','CAM 2'),(4,2,NULL,NULL,NULL,NULL,NULL);
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector) VALUES
  (1,'OUT 1',1,1),(2,'IN 1',2,1),(3,'OUT 1',2,2),(4,'OUT 1',3,1),(5,'HUERFANO',0,1),(6,NULL,3,NULL);
INSERT INTO cable(id_cable,codigo,id_tipo_cable,estado,es_cable_conexion_interna) VALUES
  (1,'C-001',1,'VERIFICADO',0),(2,'C-002',NULL,NULL,NULL),(3,'INT-1',1,NULL,1),(4,NULL,NULL,NULL,0);
INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna) VALUES
  (1,1,1,0),(2,1,2,0),(3,2,3,0),(4,2,5,0),(5,3,2,1);
INSERT INTO sala(id_sala,nombre) VALUES (1,'Control Central'),(2,'Estudio');
INSERT INTO rack(id_rack,numero,nombre,cantidad_maxima) VALUES (1,1,'Rack 1',42),(2,2,'Rack suelto',42);
INSERT INTO rack_por_sala(id_rack,id_sala) VALUES (1,1),(1,2);
INSERT INTO frame(id_frame,nombre,num_inventario,id_marca,modelo) VALUES (1,'Frame 1',500,2,'Studio'),(2,'Frame sin rack',NULL,NULL,NULL);
INSERT INTO posicion_en_rack(id_posicion_en_rack,id_rack,id_equipo,orificio_posicion_equipo_en_rack,unidades_de_rack_equipo,id_frame)
  VALUES (1,1,2,3,1,NULL),(2,1,NULL,10,4,1);
"""
c = sqlite3.connect(m.DB_PATH)
c.executescript(SQL)
c.commit()
c.close()

import bridge  # noqa: E402

fallos = []


def check(cond, msg):
    print(("  ok  " if cond else "  FALLA ") + msg)
    if not cond:
        fallos.append(msg)


def ll(fn, **kw):
    r = json.loads(bridge.call(fn, json.dumps(kw)))
    assert r["ok"], f"{fn}{kw}: {r.get('error')}"
    return r["data"]


def volcado():
    cx = sqlite3.connect(m.DB_PATH)
    r = {t[0]: cx.execute(f'SELECT * FROM "{t[0]}"').fetchall()
         for t in cx.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    cx.close()
    return r


antes = volcado()
idx = ll("busqueda_indice")
check(volcado() == antes, "solo lectura: pedir el índice no cambia ninguna tabla")
items = idx["items"]
por = {}
for it in items:
    por.setdefault(it["t"], []).append(it)
fila = lambda t, i: next(x for x in por[t] if x["i"] == i)   # noqa: E731
texto = lambda it: " ".join([it["l"], *it["d"], it.get("x", "")]).lower()   # noqa: E731

# ── Estructura ───────────────────────────────────────────────────────────────
check(set(idx) == {"items"}, "devuelve {items}")
check(set(por) == {"sala", "rack", "frame", "equipo", "conector", "cable"}, f"seis tipos: {sorted(por)}")
check(all(isinstance(x["i"], int) and isinstance(x["l"], str) and x["l"] and isinstance(x["d"], list) for x in items),
      "todo item trae id int, etiqueta no vacía y d lista")
check(json.loads(json.dumps(items)) == items, "es JSON puro")

# ── Cantidades y exclusiones ─────────────────────────────────────────────────
check(len(por["sala"]) == 2 and len(por["rack"]) == 2 and len(por["frame"]) == 2, "salas, racks y frames completos")
# Orden de SQLite: NULL primero y lower() solo baja ASCII (igual que el resto del bridge): sin nombre, CAM 2, CÁMARA 1, MATRIZ A.
check([x["i"] for x in por["equipo"]] == [4, 3, 1, 2], f"equipos sin el id 0, por nombre: {[x['i'] for x in por['equipo']]}")
check([x["i"] for x in por["conector"]] == [6, 4, 1, 2, 3], f"conectores del equipo 0 fuera; por equipo y luego nombre: {[x['i'] for x in por['conector']]}")
check(len(por["cable"]) == 4, "los 4 cables entran (internos y sin código incluidos)")

# ── Equipos: mismos campos que la etiqueta del árbol (A.3) ───────────────────
e1 = fila("equipo", 1)
check(e1["l"] == "CÁMARA 1" and e1["d"] == ["CAMARA", "Sony HDC-3500", "100", "WT-77"], f"equipo 1: {e1}")
check(fila("equipo", 3)["d"] == ["CAMARA", "Sony HDC-3500", "102"], "equipo 3: sin serie no deja huecos")
check(fila("equipo", 4)["l"] == "#4" and fila("equipo", 4)["d"] == ["MATRIZ"], "equipo sin nombre → #id")
arbol = ll("arbol_equipos")
etiquetas = {}


def recorrer(ns):
    for n in ns:
        if n["t"] == "equipo":
            etiquetas[n["i"]] = n["l"]
        recorrer(n.get("h", []))


recorrer(arbol["nodos"])
check(set(etiquetas) == {x["i"] for x in por["equipo"]}, "los mismos equipos que el árbol de A.3")
check(all(all(tok in texto(fila("equipo", i)) for tok in lab.lower().split()) for i, lab in etiquetas.items()),
      "cada palabra de la etiqueta del árbol está en el texto buscable del equipo")

# ── Conectores ───────────────────────────────────────────────────────────────
c1 = fila("conector", 1)
check(c1["l"] == "OUT 1" and c1["d"] == ["BNC", "CÁMARA 1"], f"conector 1: {c1}")
check(fila("conector", 6)["l"] == "#6" and fila("conector", 6)["d"] == ["CAM 2"], "conector sin nombre ni tipo → #id")
check(fila("conector", 3)["d"] == ["XLR", "MATRIZ A"], "conector con otro tipo")

# ── Cables ───────────────────────────────────────────────────────────────────
k1 = fila("cable", 1)
check(k1["l"] == "C-001" and k1["d"] == ["VERIFICADO", "RG59", "CÁMARA 1 ⇄ MATRIZ A"], f"cable 1: {k1}")
check(k1["x"] == "CÁMARA 1 OUT 1 MATRIZ A IN 1" and "int" not in k1, "cable 1: extremos 'equipo conector' y no es interno")
k2 = fila("cable", 2)
check(k2["d"] == ["MATRIZ A"] and k2["x"] == "MATRIZ A OUT 1", f"cable 2: el extremo en el equipo 0 no entra: {k2}")
check(fila("cable", 3).get("int") is True and fila("cable", 3)["d"] == ["RG59", "MATRIZ A"], "cable interno marcado")
k4 = fila("cable", 4)
check(k4["l"] == "#4" and k4["d"] == [] and k4["x"] == "", "cable sin código ni conexiones → #id, sin datos")

# ── Salas, racks y frames ────────────────────────────────────────────────────
check([x["l"] for x in por["sala"]] == ["Control Central", "Estudio"] and all(x["d"] == [] for x in por["sala"]), "salas por nombre")
check(fila("rack", 1)["d"] == ["Control Central", "Estudio"] and fila("rack", 2)["d"] == [], "rack: sus salas (varias o ninguna)")
check(fila("frame", 1)["d"] == ["Blackmagic Studio", "500", "Rack 1"], f"frame 1: {fila('frame', 1)}")
check(fila("frame", 2)["d"] == [], "frame sin marca, inventario ni rack")

# ── Base sin ninguna fila de un tipo ─────────────────────────────────────────
cx = sqlite3.connect(m.DB_PATH)
cx.executescript("DELETE FROM conexion; DELETE FROM cable; DELETE FROM conector;")
cx.commit()
cx.close()
vacio = ll("busqueda_indice")["items"]
check({x["t"] for x in vacio} == {"sala", "rack", "frame", "equipo"}, "sin conectores ni cables: solo quedan los otros cuatro tipos")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(fallos)} fallas" if fallos else "\nTODO OK")
sys.exit(1 if fallos else 0)
