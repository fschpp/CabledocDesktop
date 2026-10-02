#!/usr/bin/env python3
"""Test nativo de ui_web/datos_web.py (Fase A.10). Mismo layout temporal que test_busqueda.py (no toca data/database/).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_datos.py
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_datos_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"), ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
shutil.copy(os.path.join(RAIZ, "ui_web", "datos_web.py"), os.path.join(app, "datos_web.py"))
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402
import datos_web as d  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    n += 1
    assert cond, msg


def sha(p):
    """Huella de los DATOS (INSERT), no del archivo: Modelo.asegurar_tablas_catalogo puede migrar el esquema de una base vieja
    (agrega una columna legada), igual que los motores de A.7; con el db.db al día del desktop es un no-op."""
    c = sqlite3.connect(p)
    try:
        return hashlib.sha256("\n".join(l for l in c.iterdump() if l.startswith("INSERT")).encode()).hexdigest()
    finally:
        c.close()


db = m.DB_PATH
con = sqlite3.connect(db)
con.executescript("""
INSERT INTO marca(id_marca,nombre) VALUES (1,'Sony');
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES (1,1,'CAM 1');
INSERT INTO equipo_catalogo(id_equipo_catalogo,nombre_molde,id_tipo_equipo,id_marca,modelo) VALUES (1,'HDC-3500',1,1,'HDC-3500');
INSERT INTO conector_catalogo(id_equipo_catalogo,nombre,id_tipo_conector) VALUES (1,'OUT 1',1),(1,'OUT 2',1);
INSERT INTO frame_catalogo(id_frame_catalogo,nombre_molde,id_marca,modelo) VALUES (1,'FR-10',1,'FR-10');
INSERT INTO slot_catalogo(id_frame_catalogo,nombre,rectangulo_x_en_imagen,rectangulo_y_en_imagen,rectangulo_ancho_pixeles,rectangulo_alto_pixeles) VALUES (1,'SLOT 1',0,0,50,30);
""")
con.commit(); con.close()

# 1) validar_db
v = d.validar_db(db)
ok(v["ok"] and v["equipos"] == 1 and v["conectores"] == 0 and v["cables"] == 0, f"validar_db de una base buena: {v}")
txt = os.path.join(tmp, "x.db"); open(txt, "wb").write(b"esto no es sqlite, es texto largo largo")
ok(not d.validar_db(txt)["ok"] and "SQLite" in d.validar_db(txt)["error"], "un texto no es una base")
vacia = os.path.join(tmp, "vacia.db"); sqlite3.connect(vacia).execute("CREATE TABLE otra(x)").connection.commit()
r = d.validar_db(vacia); ok(not r["ok"] and r["tabla"] == "equipo", f"base sin tablas de CableDoc: {r}")

# 2) exportar: formato del desktop y base intacta
out = os.path.join(tmp, "eq.zip")
for t in ("equipos", "frames"):          # 1.ª pasada: deja la base de prueba (armada con schema_db.sql) al día con las migraciones de Modelo
    d.catalogo_exportar(t, os.path.join(tmp, "calentar.zip"))
antes = sha(db)
r = json.loads(d.catalogo_exportar("equipos", out))
ok(r["ok"] and r["moldes"] == 1 and r["nombre"] == "catalogo_equipos.zip", f"export equipos: {r}")
with zipfile.ZipFile(out) as z:
    ok(z.namelist() == ["catalogo_equipos.json"], "un único .json adentro")
    data = json.loads(z.read("catalogo_equipos.json"))
ok(data["tipo"] == "cabledoc_catalogo_equipos" and data["version"] == 5 and len(data["moldes"]) == 1, "cabecera del catálogo de equipos")
outf = os.path.join(tmp, "fr.zip")
r = json.loads(d.catalogo_exportar("frames", outf))
ok(r["ok"] and r["moldes"] == 1, f"export frames: {r}")
ok(sha(db) == antes, "exportar no modifica los datos de la base")

# 3) base sin tablas de catálogo: exporta vacío y NO las crea
con = sqlite3.connect(db); con.executescript("DROP TABLE slot_catalogo; DROP TABLE frame_catalogo;"); con.commit(); con.close()
antes = sha(db)
r = json.loads(d.catalogo_exportar("frames", outf)); ok(r["ok"] and r["moldes"] == 0, "frames sin tabla → 0 moldes")
ok(sha(db) == antes, "los datos siguen iguales")
con = sqlite3.connect(db)
ok(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN ('frame_catalogo','slot_catalogo')").fetchone()[0] == 0, "no se crearon las tablas de catálogo de frames (solo lectura)")
con.close()

# 4) importar: vuelve a crear los moldes borrados (zip) y también acepta .json plano
con = sqlite3.connect(db); con.executescript("DELETE FROM conector_catalogo; DELETE FROM equipo_catalogo;"); con.commit(); con.close()
r = json.loads(d.catalogo_importar(out))
ok(r["ok"] and r["tipo"] == "equipos" and r["moldes"] == 1 and r["hijos"] == 2 and r["conflictos"] == 0, f"import zip: {r}")
con = sqlite3.connect(db)
ok(con.execute("SELECT COUNT(*) FROM equipo_catalogo").fetchone()[0] == 1 and con.execute("SELECT COUNT(*) FROM conector_catalogo").fetchone()[0] == 2, "moldes y conectores restaurados")
con.close()
plano = os.path.join(tmp, "plano.json"); open(plano, "w", encoding="utf-8").write(json.dumps(data))
r = json.loads(d.catalogo_importar(plano)); ok(r["ok"] and r["moldes"] == 1, f"import .json plano: {r}")

# 5) importar frames (la tabla se recrea sola) y archivos inválidos
with zipfile.ZipFile(outf, "w") as z:
    z.writestr("catalogo_frames.json", json.dumps({"tipo": "cabledoc_catalogo_frames", "version": 1, "imagenes": {}, "moldes": [{"nombre_molde": "FR-X", "marca": "Sony", "modelo": "X", "slots": [{"nombre": "S1", "x": 0, "y": 0, "ancho": 10, "alto": 10}]}]}))
r = json.loads(d.catalogo_importar(outf)); ok(r["ok"] and r["tipo"] == "frames" and r["moldes"] == 1, f"import frames: {r}")
otro = os.path.join(tmp, "otro.json"); open(otro, "w").write(json.dumps({"tipo": "otra_cosa"}))
r = json.loads(d.catalogo_importar(otro)); ok(not r["ok"] and "catálogo" in r["error"], "un .json de otro tipo se rechaza")
vacio_zip = os.path.join(tmp, "v.zip"); zipfile.ZipFile(vacio_zip, "w").writestr("x.txt", "hola")
try:
    d.catalogo_importar(vacio_zip); ok(False, "debió fallar un zip sin .json")
except ValueError:
    ok(True, "")

shutil.rmtree(tmp, ignore_errors=True)
print(f"OK — {n} chequeos")
