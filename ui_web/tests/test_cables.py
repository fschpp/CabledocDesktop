#!/usr/bin/env python3
"""Test nativo de ui_web/cables_web.py (Fase B.3): ABM de cables, fusión y conexiones vía bridge.call. Mismo layout temporal
que test_catalogos.py (no toca data/database/).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_cables.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_cables_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"), ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
for f in ("bridge.py", "catalogos_web.py", "cables_web.py"):
    shutil.copy(os.path.join(RAIZ, "ui_web", f), os.path.join(app, f))
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402
import bridge as b  # noqa: E402

M = m.Modelo
n = 0


def ok(cond, msg):
    global n
    n += 1
    assert cond, msg


def call(fn, **args):
    crudo = b.call(fn, json.dumps(args))
    return json.loads(crudo), crudo


def data(fn, **args):
    r, _ = call(fn, **args)
    assert r["ok"], f"{fn}{args}: {r}"
    return r["data"]


def falla(fn, **args):
    r, crudo = call(fn, **args)
    assert not r["ok"], f"{fn}{args} debía fallar: {r}"
    return r, crudo


def q(sql, params=()):
    c = sqlite3.connect(m.DB_PATH)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


def esq(r):
    return {e["nombre"]: e for e in r["esquema"]}


con = sqlite3.connect(m.DB_PATH)
con.executescript("""
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'FANTASMA','FANTASMA');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC');
INSERT INTO tipo_cable(id_tipo_cable,nombre) VALUES (1,'RG59'),(2,'Belden');
INSERT INTO tipo_ficha(id_tipo_ficha,nombre) VALUES (1,'TRS'),(2,'BNC');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES (1,1,'CAM 1'),(2,1,'CAM 2'),(3,1,'SIN EQUIPO');
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector) VALUES (1,'OUT 1',1,1),(2,'IN 1',2,1),(3,'IN 2',2,1);
INSERT INTO cable(id_cable,codigo,id_tipo_cable,id_tipo_ficha,estado) VALUES (1,'C-001',1,1,'VERIFICADO'),(2,'C-002',NULL,NULL,'TEMPORAL'),
  (3,'SIN ETIQUETA 0007',NULL,NULL,'TEMPORAL'),(4,'C-004',NULL,NULL,'VERIFICADO');
INSERT INTO conexion(id_cable,id_conector,es_conexion_interna) VALUES (1,1,0),(1,2,0),(3,3,0);
""")
con.commit(); con.close()
M.asegurar_columnas_riesgo_senal()
M.asegurar_tablas_bitacora()

# 0) registro: lecturas y escrituras se distinguen
LEC = {"cable_formulario", "cable_usos", "conexion_formulario", "conexion_usos"}
ESC = {"cable_alta", "cable_temporal", "cable_modificar", "cable_baja", "cable_restaurar", "cable_fusionar", "cable_fusion_deshacer",
       "conexion_alta", "conexion_modificar", "conexion_baja", "conexion_restaurar"}
ok((LEC | ESC) <= set(b.FUNCIONES), "registradas en el bridge")
ok(ESC <= b.ESCRITURAS and not (LEC & b.ESCRITURAS), "escrituras marcadas; lecturas no")
ok(call("cable_formulario")[0].get("escribio") is None and call("cable_alta", valores={"estado": "VERIFICADO"})[0]["escribio"] is True,
   "solo las escrituras llevan escribio")

# 1) formulario de alta y de edición
r = data("cable_formulario")
ok(r["valores"] is None and [e["nombre"] for e in r["esquema"]] == ["codigo", "estado", "id_tipo_cable", "id_tipo_ficha", "longitud", "unidad_longitud",
   "metraje_ext1", "metraje_ext2", "unidad_metraje", "notas_relevamiento"], f"campos del alta: {[e['nombre'] for e in r['esquema']]}")
ok([o["valor"] for o in esq(r)["estado"]["opciones"]] == ["VERIFICADO", "TEMPORAL", "EN_REVISION"], "estados del desktop")
ok(esq(r)["id_tipo_cable"]["opciones"] == [{"valor": 2, "etiqueta": "Belden"}, {"valor": 1, "etiqueta": "RG59"}], "tipos de cable ordenados, con etiqueta")
r = data("cable_formulario", id_cable=1)
ok(r["valores"]["codigo"] == "C-001" and r["valores"]["id_tipo_cable"] == 1 and r["valores"]["estado"] == "VERIFICADO", f"valores: {r['valores']}")
ok({"ancho_banda_override", "es_armado_correcto", "detalle_armado"} <= set(esq(r)), "la edición suma override y armado")
f, _ = falla("cable_formulario", id_cable=999)
ok("No existe el cable 999" in f["error"] and "escribio" not in f, f"cable inexistente: {f}")

# 2) alta: normaliza, valida, no repite códigos
a = data("cable_alta", valores={"codigo": "  C-010 ", "estado": "TEMPORAL", "id_tipo_cable": 1, "longitud": "10,5", "unidad_longitud": "m",
                                "metraje_ext1": "3", "notas_relevamiento": " nota "})
ok(a["codigo"] == "C-010" and a["valores"]["longitud"] == 10.5 and a["valores"]["notas_relevamiento"] == "nota" and a["valores"]["id_tipo_ficha"] is None,
   f"alta normalizada: {a}")
ok(q("SELECT codigo, estado, longitud, id_tipo_cable, metraje_impreso_primer_extremo, es_cable_conexion_interna FROM cable WHERE id_cable=?", (a["id"],))[0]
   == ("C-010", "TEMPORAL", 10.5, 1, 3, 0), "fila en la base")
r, crudo = call("cable_alta", valores={"codigo": "c-001 ", "estado": "VERIFICADO"})
ok(not r["ok"] and r["campos"] == {"codigo": "Ya existe un cable con ese código"} and "escribio" not in r, f"código repetido (sin distinguir mayúsculas): {r}")
r, _ = call("cable_alta", valores={"codigo": "x" * 121, "estado": "NOPE", "id_tipo_cable": 99, "longitud": "-1", "metraje_ext2": "abc"})
ok(r["campos"] == {"codigo": "Texto demasiado largo", "estado": "Elegí una opción válida", "id_tipo_cable": "Elegí una opción válida",
                   "longitud": "No puede ser negativo", "metraje_ext2": "Debe ser un número"}, f"todos los errores a la vez: {r['campos']}")
r, _ = call("cable_alta", valores={"estado": ""})
ok(r["campos"] == {"estado": "Obligatorio"}, "estado obligatorio")
f, _ = falla("cable_alta", valores={"codigo": "Z", "estado": "VERIFICADO", "es_armado_correcto": 1})
ok("Campos desconocidos" in f["error"] and "escribio" not in f, "armado no es un campo del alta")
antes = q("SELECT COUNT(*) FROM cable")[0][0]
sin_codigo = data("cable_alta", valores={"estado": "VERIFICADO"})
ok(sin_codigo["codigo"] is None and q("SELECT COUNT(*) FROM cable")[0][0] == antes + 1, "el código es opcional (como en el desktop)")
data("cable_alta", valores={"estado": "VERIFICADO"})
ok(q("SELECT COUNT(*) FROM cable")[0][0] == antes + 2, "dos cables sin código conviven (UNIQUE admite varios NULL)")

# 3) temporal: el siguiente SIN ETIQUETA libre
t = data("cable_temporal")
ok(t["codigo"] == "SIN ETIQUETA 0008" and q("SELECT estado, codigo FROM cable WHERE id_cable=?", (t["id"],))[0] == ("TEMPORAL", "SIN ETIQUETA 0008"), f"temporal: {t}")

# 4) modificar: reemplaza todos los campos, devuelve lo anterior, valida unicidad
mo = data("cable_modificar", id=1, valores={**data("cable_formulario", id_cable=1)["valores"], "longitud": 5, "unidad_longitud": "m", "id_tipo_cable": 2,
                                           "ancho_banda_override": "120", "es_armado_correcto": 0, "detalle_armado": "pin 2 y 3 cruzados"})
ok(mo["anterior"]["longitud"] is None and mo["anterior"]["id_tipo_cable"] == 1 and mo["valores"]["id_tipo_cable"] == 2, f"anterior/nuevo: {mo}")
ok(q("SELECT longitud, unidad_longitud, id_tipo_cable, ancho_banda_mhz_override, es_armado_correcto, detalle_armado FROM cable WHERE id_cable=1")[0]
   == (5.0, "m", 2, 120.0, 0, "pin 2 y 3 cruzados"), "campos, override y armado guardados")
r, _ = call("cable_modificar", id=1, valores={**mo["valores"], "codigo": "C-002"})
ok(r["campos"] == {"codigo": "Ya existe un cable con ese código"} and q("SELECT codigo FROM cable WHERE id_cable=1")[0][0] == "C-001", "no pisa el código de otro cable")
data("cable_modificar", id=1, valores={**mo["valores"], "codigo": "c-001"})       # mismo código en otra capitalización: es el mismo cable
ok(q("SELECT codigo FROM cable WHERE id_cable=1")[0][0] == "c-001", "puede cambiar la capitalización de su propio código")
data("cable_modificar", id=1, valores=mo["anterior"])                          # deshacer
ok(q("SELECT codigo, longitud, id_tipo_cable, ancho_banda_mhz_override, es_armado_correcto, detalle_armado FROM cable WHERE id_cable=1")[0]
   == ("C-001", None, 1, None, None, None), "deshacer: vuelve todo (también override y armado)")
f, _ = falla("cable_modificar", id=999, valores={"estado": "VERIFICADO"})
ok("No existe el cable" in f["error"] and "escribio" not in f, "modificar un id inexistente")

# 5) un cable FUSIONADO conserva su estado al editarlo (el combo del desktop lo pisaría)
con = sqlite3.connect(m.DB_PATH); con.execute("UPDATE cable SET estado='FUSIONADO', id_cable_fusionado=1 WHERE id_cable=4"); con.commit(); con.close()
fo = data("cable_formulario", id_cable=4)
ok(esq(fo)["estado"]["opciones"][-1] == {"valor": "FUSIONADO", "etiqueta": "FUSIONADO"} and fo["valores"]["estado"] == "FUSIONADO", "FUSIONADO se ofrece al editar")
data("cable_modificar", id=4, valores={**fo["valores"], "notas_relevamiento": "historial"})
ok(q("SELECT estado, notas_relevamiento FROM cable WHERE id_cable=4")[0] == ("FUSIONADO", "historial"), "el estado no se pisa")
r, _ = call("cable_alta", valores={"estado": "FUSIONADO"})
ok(r["campos"] == {"estado": "Elegí una opción válida"}, "pero no se puede dar de alta un cable FUSIONADO")

# 6) usos y baja
u = data("cable_usos", id_cable=1)
ok(u["codigo"] == "C-001" and u["usos"] == [{"tabla": "conexion", "n": 2, "efecto": "borra"}], f"usos de C-001: {u}")
ok(data("cable_usos", id_cable=2)["usos"] == [], "un cable sin conexiones no tiene usos")
f, _ = falla("cable_baja", id=1, solo_si_sin_uso=True)
ok("ya tiene conexiones" in f["error"] and q("SELECT COUNT(*) FROM cable WHERE id_cable=1")[0][0] == 1 and "escribio" not in f, "solo_si_sin_uso se niega y no escribe")
nuevo = data("cable_alta", valores={"codigo": "C-099", "estado": "VERIFICADO", "id_tipo_ficha": 2, "longitud": 3, "notas_relevamiento": "n"})
bj = data("cable_baja", id=nuevo["id"], solo_si_sin_uso=True)
ok(bj["usos"] == [] and bj["anterior"]["codigo"] == "C-099" and q("SELECT COUNT(*) FROM cable WHERE id_cable=?", (nuevo["id"],))[0][0] == 0, "baja sin uso")
rs = data("cable_restaurar", id=bj["id"], valores=bj["anterior"], interno=bj["interno"], id_cable_fusionado=bj["id_cable_fusionado"])
ok(q("SELECT codigo, longitud, id_tipo_ficha, notas_relevamiento, es_cable_conexion_interna FROM cable WHERE id_cable=?", (bj["id"],))[0]
   == ("C-099", 3.0, 2, "n", 0), f"restaurar: mismo id y mismos datos: {rs}")
f, _ = falla("cable_restaurar", id=bj["id"], valores=bj["anterior"])
ok("Ya existe un cable con el id" in f["error"], "no restaura sobre un id existente")
# baja de un cable CON conexiones: las FK las arrastran y se informa
bj = data("cable_baja", id=1)
ok(bj["usos"] == [{"tabla": "conexion", "n": 2, "efecto": "borra"}] and q("SELECT COUNT(*) FROM conexion WHERE id_cable=1")[0][0] == 0
   and q("SELECT COUNT(*) FROM cable WHERE id_cable=1")[0][0] == 0, "baja con conexiones: se llevan sus conexiones")
data("cable_restaurar", id=1, valores=bj["anterior"])
con = sqlite3.connect(m.DB_PATH)
con.executescript("INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna) VALUES (1,1,1,0),(2,1,2,0);")
con.commit(); con.close()

# 7) fusión: validaciones
f, _ = falla("cable_fusionar", id_principal=1, id_secundario=1, codigo="X", estado="VERIFICADO")
ok("dos cables distintos" in f["error"] and "escribio" not in f, "mismo cable")
f, _ = falla("cable_fusionar", id_principal=1, id_secundario=4, codigo="X", estado="VERIFICADO")
ok("ya está fusionado" in f["error"], f"un cable ya fusionado no se fusiona: {f['error']}")
r, _ = call("cable_fusionar", id_principal=1, id_secundario=3, codigo="", estado="OTRO")
ok(r["campos"] == {"codigo": "Obligatorio", "estado": "Elegí una opción válida"}, f"campos de la fusión: {r}")
r, _ = call("cable_fusionar", id_principal=1, id_secundario=3, codigo="sin etiqueta 0007", estado="VERIFICADO")
ok(r["campos"] == {"codigo": "Ya lo usa otro cable (incluido el secundario)"}
   and q("SELECT id_cable FROM conexion WHERE id_conexion=3")[0][0] == 3, "el código del secundario no sirve como definitivo y NO se movió nada")
# fusión OK: principal 1 (C-001) absorbe a 3 (SIN ETIQUETA 0007, una conexión)
fu = data("cable_fusionar", id_principal=1, id_secundario=3, codigo="C-001", estado="VERIFICADO")
ok(fu["conexiones"] == [3] and q("SELECT id_cable FROM conexion WHERE id_conexion=3")[0][0] == 1, f"las conexiones del secundario pasan al principal: {fu}")
ok(q("SELECT estado, id_cable_fusionado FROM cable WHERE id_cable=3")[0] == ("FUSIONADO", 1) and q("SELECT estado, id_cable_fusionado FROM cable WHERE id_cable=1")[0] == ("VERIFICADO", None),
   "secundario FUSIONADO apuntando al principal; no se borra")
ok(q("SELECT COUNT(*) FROM conexion WHERE id_cable=1")[0][0] == 3, "el principal tiene las 3 conexiones")
fusionados = [o["valor"] for o in esq(data("conexion_formulario", id_conexion=1))["id_cable"]["opciones"]]
ok(3 not in fusionados and 1 in fusionados, "los cables fusionados no se ofrecen para conectar")
# deshacer la fusión
data("cable_fusion_deshacer", id_principal=1, id_secundario=3, anterior=fu["anterior"], conexiones=fu["conexiones"])
ok(q("SELECT id_cable FROM conexion WHERE id_conexion=3")[0][0] == 3 and q("SELECT codigo, estado, id_cable_fusionado FROM cable WHERE id_cable=1")[0] == ("C-001", "VERIFICADO", None)
   and q("SELECT codigo, estado, id_cable_fusionado FROM cable WHERE id_cable=3")[0] == ("SIN ETIQUETA 0007", "TEMPORAL", None), "deshacer fusión: todo como estaba")
f, _ = falla("cable_fusion_deshacer", id_principal=1, id_secundario=3, anterior=fu["anterior"], conexiones=fu["conexiones"])
ok("ya no se puede deshacer" in f["error"], "deshacer dos veces no hace nada")
# fusión con código nuevo y estado TEMPORAL, y deshacer cuando el principal cambió de código
fu = data("cable_fusionar", id_principal=3, id_secundario=2, codigo="C-777", estado="TEMPORAL")
ok(q("SELECT codigo, estado FROM cable WHERE id_cable=3")[0] == ("C-777", "TEMPORAL"), "el principal toma código y estado definitivos")
data("cable_fusion_deshacer", id_principal=3, id_secundario=2, anterior=fu["anterior"], conexiones=fu["conexiones"])
ok(q("SELECT codigo FROM cable WHERE id_cable=3")[0][0] == "SIN ETIQUETA 0007" and q("SELECT estado FROM cable WHERE id_cable=2")[0][0] == "TEMPORAL", "deshecha")

# 8) formulario de conexión
r = data("conexion_formulario", id_cable=2)
ok(r["valores"] == {"id_cable": 2, "id_equipo": None, "id_conector": None} and [e["nombre"] for e in r["esquema"]] == ["id_cable", "id_equipo", "id_conector"], f"alta prefijada: {r}")
ok(esq(r)["id_conector"]["depende_de"] == "id_equipo" and esq(r)["id_conector"]["opciones"] == [], "el conector depende del equipo y arranca vacío")
ok("SIN EQUIPO" not in [o["etiqueta"] for o in esq(r)["id_equipo"]["opciones"]], "los equipos de sistema no se ofrecen")
r = data("conexion_formulario", id_conector=3)
ok(r["valores"]["id_equipo"] == 2 and [o["etiqueta"] for o in esq(r)["id_conector"]["opciones"]] == ["IN 1 · BNC (1)", "IN 2 · BNC (1)"] and r["valores"]["id_cable"] is None,
   f"alta desde un conector: equipo y conectores del equipo: {esq(r)['id_conector']['opciones']}")
r = data("conexion_formulario", id_conexion=2)
ok(r["valores"]["id_cable"] == 1 and r["valores"]["id_equipo"] == 2 and r["valores"]["id_conector"] == 2 and {"id_tipo_ficha", "es_armado_correcto", "detalle_armado"} <= set(esq(r)),
   "edición: valores actuales y campos extra")
f, _ = falla("conexion_formulario", id_conexion=999)
ok("No existe la conexión" in f["error"], "conexión inexistente")
f, _ = falla("conexion_formulario", id_conector=999)
ok("No existe el conector" in f["error"], "conector inexistente")

# 9) alta de conexión
c = data("conexion_alta", id_cable=2, id_conector=1)
ok(c["valores"] == {"id_cable": 2, "id_conector": 1, "id_tipo_ficha": None, "es_armado_correcto": None, "detalle_armado": None}, f"alta: {c}")
ok(c["avisos"] == [{"clave": "El conector ya tiene {n} conexión(es) más", "vars": {"n": 1}}], f"aviso: el conector 1 ya tenía el cable C-001: {c['avisos']}")
ok(q("SELECT es_conexion_interna FROM conexion WHERE id_conexion=?", (c["id"],))[0][0] == 0, "no es interna")
r, _ = call("conexion_alta", id_cable=2, id_conector=1)
ok(r["campos"] == {"id_conector": "Ese cable ya está conectado a ese conector"} and "escribio" not in r, f"misma conexión dos veces: {r}")
r, _ = call("conexion_alta", id_cable=None, id_conector=None)
ok(r["campos"] == {"id_cable": "Obligatorio", "id_conector": "Obligatorio"}, "obligatorios")
r, _ = call("conexion_alta", id_cable=999, id_conector=999)
ok(r["campos"] == {"id_cable": "Elegí una opción válida", "id_conector": "Elegí una opción válida"}, "ids inexistentes")
c2 = data("conexion_alta", id_cable=2, id_conector=3)
c3 = data("conexion_alta", id_cable=2, id_conector=2)
ok(c3["avisos"][0] == {"clave": "El cable tiene {n} extremos (lo habitual es 2)", "vars": {"n": 3}}, f"aviso de más de dos extremos: {c3['avisos']}")
data("conexion_baja", id=c3["id"]); data("conexion_baja", id=c2["id"])

# 10) modificar conexión: conector, ficha y armado; conserva es_conexion_interna; repetidas
con = sqlite3.connect(m.DB_PATH); con.execute("UPDATE conexion SET es_conexion_interna=1 WHERE id_conexion=?", (c["id"],)); con.commit(); con.close()
cm = data("conexion_modificar", id=c["id"], valores={"id_cable": 2, "id_conector": 3, "id_tipo_ficha": 2, "es_armado_correcto": 0, "detalle_armado": " cruce "})
ok(cm["anterior"]["id_conector"] == 1 and cm["valores"] == {"id_cable": 2, "id_conector": 3, "id_tipo_ficha": 2, "es_armado_correcto": 0, "detalle_armado": "cruce"}, f"modificar: {cm}")
ok(q("SELECT es_conexion_interna FROM conexion WHERE id_conexion=?", (c["id"],))[0][0] == 1, "es_conexion_interna se conserva (el desktop la pisa con 0)")
r, _ = call("conexion_modificar", id=c["id"], valores={**cm["valores"], "id_cable": 1, "id_conector": 1})
ok(r["campos"] == {"id_conector": "Ese cable ya está conectado a ese conector"}, "no duplica una conexión existente al editar")
r, _ = call("conexion_modificar", id=c["id"], valores={**cm["valores"], "id_conector": None})
ok(r["campos"] == {"id_conector": "Obligatorio"}, "no se deja una conexión con conector sin extremo suelto")
f, _ = falla("conexion_modificar", id=c["id"], valores={**cm["valores"], "id_equipo": 2})
ok("Campos desconocidos" in f["error"], "id_equipo es solo de la UI: no se manda")
data("conexion_modificar", id=c["id"], valores=cm["anterior"])               # deshacer
ok(q("SELECT id_conector, id_tipo_ficha, es_armado_correcto, detalle_armado, es_conexion_interna FROM conexion WHERE id_conexion=?", (c["id"],))[0] == (1, None, None, None, 1),
   "deshacer: vuelve todo")
# extremo suelto: se edita sin conector (ficha, armado) y no se le obliga uno
con = sqlite3.connect(m.DB_PATH); con.execute("INSERT INTO conexion(id_conexion,id_cable,id_conector) VALUES (50,4,NULL)"); con.commit(); con.close()
fs = data("conexion_formulario", id_conexion=50)
ok(esq(fs)["id_conector"]["requerido"] is False and fs["valores"]["id_conector"] is None, "extremo suelto: conector no obligatorio")
data("conexion_modificar", id=50, valores={**{k: v for k, v in fs["valores"].items() if k != "id_equipo"}, "id_tipo_ficha": 1})
ok(q("SELECT id_conector, id_tipo_ficha FROM conexion WHERE id_conexion=50")[0] == (None, 1), "el extremo suelto sigue suelto")
data("conexion_baja", id=50)

# 11) baja de conexión, usos y restaurar
con = sqlite3.connect(m.DB_PATH)
con.execute("INSERT INTO conexion(id_conexion,id_cable,id_conector) VALUES (60,2,3),(61,4,1)")
M.asegurar_tablas_extension_cable()
con.execute("INSERT INTO extension_cable(id_conexion_a,id_conexion_b) VALUES (60,61)")
con.commit(); con.close()
ok(data("conexion_usos", id_conexion=60)["usos"] == [{"tabla": "extension_cable", "n": 1, "efecto": "borra"}], "usos: una extensión")
ok(data("cable_usos", id_cable=2)["usos"][0] == {"tabla": "conexion", "n": 2, "efecto": "borra"} and {"tabla": "extension_cable", "n": 1, "efecto": "borra"} in data("cable_usos", id_cable=2)["usos"],
   "el cable cuenta también las extensiones que se llevaría")
f, _ = falla("conexion_baja", id=60, solo_si_sin_uso=True)
ok("forma parte de una extensión" in f["error"] and "escribio" not in f, "solo_si_sin_uso con extensión: se niega")
bj = data("conexion_baja", id=60)
ok(bj["usos"][0]["n"] == 1 and q("SELECT COUNT(*) FROM extension_cable")[0][0] == 0 and q("SELECT COUNT(*) FROM conexion WHERE id_conexion=60")[0][0] == 0, "la baja arrastra la extensión")
bj = data("conexion_baja", id=61, solo_si_sin_uso=True)
rs = data("conexion_restaurar", id=bj["id"], valores=bj["anterior"], interno=bj["interno"])
ok(q("SELECT id_cable, id_conector, es_conexion_interna FROM conexion WHERE id_conexion=61")[0] == (4, 1, 0) and rs["valores"]["id_cable"] == 4, "restaurar: mismo id y datos")
f, _ = falla("conexion_restaurar", id=61, valores=bj["anterior"])
ok("Ya existe una conexión con el id" in f["error"], "no restaura sobre un id existente")

# 12) las FK siguen sanas y nada quedó a medias
ok(q("PRAGMA integrity_check")[0][0] == "ok", "integrity_check")
ok(q("PRAGMA foreign_key_check") == [], f"foreign_key_check: {q('PRAGMA foreign_key_check')}")
# 13) base vieja: sin las columnas de armado/override (las crea asegurar_*) las lecturas siguen andando y no se migra por leer
con = sqlite3.connect(m.DB_PATH)
for col in ("es_armado_correcto", "detalle_armado"):
    con.execute(f"ALTER TABLE cable DROP COLUMN {col}")
    con.execute(f"ALTER TABLE conexion DROP COLUMN {col}")
con.execute("ALTER TABLE cable DROP COLUMN ancho_banda_mhz_override")
con.commit(); con.close()
v = data("cable_formulario", id_cable=2)["valores"]
ok(v["es_armado_correcto"] is None and v["ancho_banda_override"] is None and v["detalle_armado"] is None, "cable: sin columnas se leen como NULL")
ok(data("conexion_formulario", id_conexion=1)["valores"]["es_armado_correcto"] is None, "conexión: ídem")
data("cable_modificar", id=2, valores={**v, "notas_relevamiento": "sin migrar"})
cols = [r[1] for r in sqlite3.connect(m.DB_PATH).execute("PRAGMA table_info(cable)")]
ok("es_armado_correcto" not in cols and "ancho_banda_mhz_override" not in cols, "guardar otro campo NO migra el esquema")
data("cable_modificar", id=2, valores={**v, "es_armado_correcto": 1})
ok("es_armado_correcto" in [r[1] for r in sqlite3.connect(m.DB_PATH).execute("PRAGMA table_info(cable)")], "cambiar el armado sí lo migra (Modelo.asegurar_tablas_bitacora)")

print(f"\nOK — {n} chequeos")
shutil.rmtree(tmp, ignore_errors=True)
