#!/usr/bin/env python3
"""Test nativo de ui_web/equipos_web.py (Fase B.4): ABM de equipos y conectores y alta rápida con plantilla, vía bridge.call.
Mismo layout temporal que test_cables.py (no toca data/database/).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_equipos_b4.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_equipos_b4_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"), ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
for f in ("bridge.py", "catalogos_web.py", "cables_web.py", "equipos_web.py"):
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


def foto():
    """Contenido de las tablas que las lecturas no deben tocar."""
    return [q(f"SELECT * FROM {t} ORDER BY 1") for t in ("equipo", "conector", "conexion", "cable", "plantilla_conector")]


con = sqlite3.connect(m.DB_PATH)
con.executescript("""
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'SWITCHER','ENRUTADOR');
INSERT INTO marca(id_marca,nombre) VALUES (1,'Sony');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC'),(2,'XLR'),(3,'IN'),(4,'OUT');
INSERT INTO tipo_ficha(id_tipo_ficha,nombre) VALUES (1,'TRS');
INSERT INTO imagen(id_imagen,path_archivo) VALUES (1,'imagen/cam.png');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre,id_imagen,coordenada_x_en_imagen,coordenada_y_en_imagen,picon)
  VALUES (1,1,'CAM 1',1,10,20,'cam1.jpg'),(2,1,'CAM 2',NULL,NULL,NULL,NULL);
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector,id_imagen,coordenada_x_en_imagen,coordenada_y_en_imagen)
  VALUES (1,'OUT 1',1,1,1,30,40),(2,'IN 1',2,1,NULL,NULL,NULL);
INSERT INTO cable(id_cable,codigo,estado) VALUES (1,'C-001','VERIFICADO');
INSERT INTO conexion(id_cable,id_conector,es_conexion_interna) VALUES (1,1,0),(1,2,0);
""")
con.commit()
con.close()

# 0) registro: solo las escrituras llevan "escribio"
r, _ = call("equipo_formulario")
ok("escribio" not in r and r["ok"], "una lectura no lleva escribio")
for fn in ("equipo_alta", "equipo_alta_rapida", "equipo_modificar", "equipo_baja", "equipo_restaurar",
           "conector_alta", "conector_modificar", "conector_baja", "conector_restaurar", "cable_extremo_desconectado", "cable_extremo_deshacer"):
    ok(fn in b.ESCRITURAS, f"{fn} es escritura")
for fn in ("equipo_formulario", "equipo_usos", "equipo_plantilla", "conector_formulario", "conector_usos", "cable_extremo_formulario"):
    ok(fn in b.FUNCIONES and fn not in b.ESCRITURAS, f"{fn} es lectura")

# 1) formulario de equipo
r = data("equipo_formulario")
ok([e["nombre"] for e in r["esquema"]] == ["nombre", "id_tipo_equipo", "id_marca", "modelo", "num_inventario", "num_serie",
   "fecha_fabricacion", "es_equipo_usado", "es_modulo_de_frame", "critico", "ancho_mm", "alto_mm", "profundidad_mm", "path_manual",
   "configuraciones"], "campos del formulario")
ok(r["valores"] is None and esq(r)["nombre"]["requerido"] and esq(r)["critico"]["tipo"] == "bool", "alta: sin valores, nombre obligatorio, casillas bool")
ok(esq(r)["id_tipo_equipo"]["opciones"] == [{"valor": 1, "etiqueta": "CAMARA"}, {"valor": 2, "etiqueta": "SWITCHER"}], "tipos como opciones")
r = data("equipo_formulario", id_equipo=1)
ok(r["valores"]["nombre"] == "CAM 1" and r["valores"]["critico"] is False and r["valores"]["es_modulo_de_frame"] is False, "valores del equipo 1")
falla("equipo_formulario", id_equipo=999)

# 2) alta: normaliza y valida
a = data("equipo_alta", valores={"nombre": "  VTR 1 ", "id_tipo_equipo": 1, "id_marca": 1, "modelo": " XDCAM ", "num_inventario": "1234",
                                 "num_serie": "SN-9", "fecha_fabricacion": "2019", "es_equipo_usado": True, "es_modulo_de_frame": True,
                                 "critico": True, "ancho_mm": "480,5", "alto_mm": 44, "configuraciones": "A\nB"})
ok(a["nombre"] == "VTR 1" and a["valores"]["modelo"] == "XDCAM" and a["valores"]["num_inventario"] == "1234", "normalizó textos")
ok(a["valores"]["es_equipo_usado"] is True and a["valores"]["es_modulo_de_frame"] is True and a["valores"]["critico"] is True, "casillas guardadas")
fila = q("SELECT nombre, id_tipo_equipo, id_marca, ancho_mm, alto_mm, profundidad_mm, id_imagen, picon FROM equipo WHERE id_equipo=?", (a["id"],))[0]
ok(fila == ("VTR 1", 1, 1, 480.5, 44.0, None, None, None), f"fila guardada: {fila}")
ok(q("SELECT COUNT(*) FROM equipo_critico WHERE id_equipo=?", (a["id"],))[0][0] == 1, "marcado como crítico")
r, _ = call("equipo_alta", valores={"nombre": "", "id_tipo_equipo": 99, "id_marca": "x", "ancho_mm": "-1", "alto_mm": "abc", "modelo": "x" * 201})
ok(not r["ok"] and "escribio" not in r, "un error de validación no pide persistir")
ok(set(r["campos"]) == {"nombre", "id_tipo_equipo", "id_marca", "ancho_mm", "alto_mm", "modelo"}, f"errores por campo: {r['campos']}")
n_eq = q("SELECT COUNT(*) FROM equipo")[0][0]
f, _ = falla("equipo_alta", valores={"nombre": "Z", "picon": "x.jpg"})
ok("Campos desconocidos" in f["error"] and q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq, "campos que no son del formulario: rechazados sin escribir")
falla("equipo_alta", valores="no soy un dict")

# 3) modificar: solo toca los campos del formulario (imagen, picon y coordenadas quedan)
v1 = data("equipo_formulario", id_equipo=1)["valores"]
mo = data("equipo_modificar", id=1, valores={**v1, "nombre": "CAM 1 HD", "id_marca": 1, "num_inventario": "A-7", "es_equipo_usado": True,
                                              "critico": True, "ancho_mm": 200})
ok(mo["anterior"] == v1 and mo["valores"]["nombre"] == "CAM 1 HD" and mo["valores"]["critico"] is True, "devuelve lo anterior y lo nuevo")
ok(q("SELECT id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen, picon FROM equipo WHERE id_equipo=1")[0] == (1, 10, 20, "cam1.jpg"),
   "imagen, coordenadas y picon intactos tras editar")
ok(q("SELECT num_inventario, es_equipo_usado, ancho_mm FROM equipo WHERE id_equipo=1")[0] == ("A-7", 1, 200.0), "campos del formulario guardados")
data("equipo_modificar", id=1, valores=mo["anterior"])                                     # deshacer
ok(q("SELECT nombre, id_marca, num_inventario, es_equipo_usado, ancho_mm FROM equipo WHERE id_equipo=1")[0] == ("CAM 1", None, None, 0, None)
   and q("SELECT COUNT(*) FROM equipo_critico WHERE id_equipo=1")[0][0] == 0, "el deshacer devuelve los valores anteriores")
r, _ = call("equipo_modificar", id=2, valores={**data("equipo_formulario", id_equipo=2)["valores"], "nombre": ""})
ok(not r["ok"] and r["campos"] == {"nombre": "Obligatorio"}, "editar sin nombre: error por campo")
falla("equipo_modificar", id=999, valores={"nombre": "x"})

# 4) usos y baja (cascadas leídas de las FK)
antes = foto()
u = data("equipo_usos", id_equipo=2)
d = {x["tabla"]: (x["n"], x["efecto"]) for x in u["usos"]}
ok(d.get("conector") == (1, "borra") and d.get("conexion") == (1, "borra"), f"equipo 2: borra 1 conector y 1 conexión ({d})")
ok(foto() == antes, "equipo_usos no modifica la base")
f, _ = falla("equipo_baja", id=2, solo_si_sin_uso=True)
ok(q("SELECT COUNT(*) FROM equipo WHERE id_equipo=2")[0][0] == 1, "solo_si_sin_uso: no borró nada")
libre = data("equipo_alta", valores={"nombre": "LIBRE", "id_tipo_equipo": 1, "ancho_mm": 10})["id"]
bj = data("equipo_baja", id=libre)
ok(bj["usos"] == [] and bj["fila"]["nombre"] == "LIBRE", "baja sin uso: nada arrastrado y devuelve la fila completa")
data("equipo_restaurar", id=libre, fila=bj["fila"])
ok(q("SELECT nombre, id_tipo_equipo, ancho_mm FROM equipo WHERE id_equipo=?", (libre,))[0] == ("LIBRE", 1, 10.0), "restaurar: mismo id y mismos datos")
falla("equipo_restaurar", id=libre, fila=bj["fila"])
falla("equipo_restaurar", id=12345, fila={"id_equipo": 12345, "columna_que_no_existe": 1})
bj2 = data("equipo_baja", id=2)
ok({x["tabla"] for x in bj2["usos"]} >= {"conector", "conexion"}, "la baja informa lo que arrastró")
ok(q("SELECT COUNT(*) FROM conector WHERE id_equipo=2")[0][0] == 0 and q("SELECT COUNT(*) FROM conexion WHERE id_conector=2")[0][0] == 0, "cascada: sin conectores ni conexiones")
ok(q("PRAGMA integrity_check")[0][0] == "ok" and q("PRAGMA foreign_key_check") == [], "la base queda sana tras la baja")

# 5) plantilla y alta rápida
pl = data("equipo_plantilla", id_tipo_equipo=2)
ok(pl["tiene_plantilla"] is False and len(pl["filas"]) == 8 and all(f["cantidad"] == 0 for f in pl["filas"]), "sin plantilla: cada tipo con IN y OUT en 0")
ok(foto()[4] == [], "equipo_plantilla no escribe")
ar = data("equipo_alta_rapida", valores={"nombre": "SW 1", "id_tipo_equipo": 2, "id_marca": 1, "modelo": "X", "num_inventario": "5", "num_serie": "S"},
          conectores=[{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 3}, {"id_tipo_conector": 1, "direccion": "OUT", "cantidad": 1},
                      {"id_tipo_conector": 3, "direccion": "IN", "cantidad": 2}, {"id_tipo_conector": 2, "direccion": "OUT", "cantidad": 0}])
ok(ar["n_conectores"] == 6 and ar["plantilla_guardada"] is True and len(ar["ids_conectores"]) == 6, "creó 6 conectores y guardó la plantilla")
nombres = [r[0] for r in q("SELECT nombre FROM conector WHERE id_equipo=? ORDER BY id_conector", (ar["id"],))]
ok(nombres == ["IN BNC 01", "IN BNC 02", "IN BNC 03", "OUT BNC", "IN 01", "IN 02"], f"nombres como el desktop: {nombres}")
ok(q("SELECT COUNT(*) FROM conector WHERE id_equipo=? AND id_tipo_conector IS NULL", (ar["id"],))[0][0] == 0, "con su tipo de conector")
pl = data("equipo_plantilla", id_tipo_equipo=2)
ok(pl["tiene_plantilla"] and [(f["tipo_conector"], f["direccion"], f["cantidad"]) for f in pl["filas"][:3]] == [("BNC", "IN", 3), ("BNC", "OUT", 1), ("IN", "IN", 2)],
   f"la plantilla del tipo quedó guardada y va primero: {pl['filas'][:3]}")
sin_tipo = data("equipo_alta_rapida", valores={"nombre": "SIN TIPO"}, conectores=[{"id_tipo_conector": 1, "direccion": "OUT", "cantidad": 1}])
ok(sin_tipo["plantilla_guardada"] is False and q("SELECT COUNT(*) FROM plantilla_conector")[0][0] == 3, "sin tipo de equipo no hay plantilla que guardar")
solo = data("equipo_alta_rapida", valores={"nombre": "SIN CONECTORES", "id_tipo_equipo": 1}, conectores=[])
ok(solo["n_conectores"] == 0 and solo["plantilla_guardada"] is False, "sin conectores: solo el equipo")
n_eq = q("SELECT COUNT(*) FROM equipo")[0][0]
for malos, clave in (([{"id_tipo_conector": 99, "direccion": "IN", "cantidad": 1}], "q_99_IN"),
                     ([{"id_tipo_conector": 1, "direccion": "X", "cantidad": 1}], "q_1_X"),
                     ([{"id_tipo_conector": 1, "direccion": "IN", "cantidad": -1}], "q_1_IN"),
                     ([{"id_tipo_conector": 1, "direccion": "IN", "cantidad": "1,5"}], "q_1_IN"),
                     ([{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 100}], "q_1_IN"),
                     ([{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 1}, {"id_tipo_conector": 1, "direccion": "IN", "cantidad": 2}], "q_1_IN")):
    r, _ = call("equipo_alta_rapida", valores={"nombre": "MALO", "id_tipo_equipo": 1}, conectores=malos)
    ok(not r["ok"] and clave in r["campos"] and "escribio" not in r, f"plantilla inválida {malos}: {r}")
ok(q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq, "una plantilla inválida no crea el equipo")
r, _ = call("equipo_alta_rapida", valores={"nombre": ""}, conectores=[{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 1}])
ok(not r["ok"] and r["campos"] == {"nombre": "Obligatorio"} and q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq, "sin nombre: no crea nada")
falla("equipo_alta_rapida", valores={"nombre": "X"}, conectores="no es lista")
falla("equipo_alta_rapida", valores={"nombre": "X", "critico": True}, conectores=[])           # la alta rápida tiene menos campos
falla("equipo_alta_rapida", valores={"nombre": "X"}, conectores=[{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 99}] * 6)   # 594 > 500
ok(q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq, "tope de conectores: no crea nada")
orig = M.agregar_conector_retorna_id
cont = {"n": 0}


def roto(*a, **k):
    cont["n"] += 1
    if cont["n"] == 3:
        raise RuntimeError("falló el tercero")
    return orig(*a, **k)


M.agregar_conector_retorna_id = staticmethod(roto)
try:
    r, _ = call("equipo_alta_rapida", valores={"nombre": "A MEDIAS", "id_tipo_equipo": 1}, conectores=[{"id_tipo_conector": 1, "direccion": "IN", "cantidad": 4}])
finally:
    M.agregar_conector_retorna_id = orig
ok(not r["ok"] and r.get("escribio") is True, "si falla a mitad se avisa y se pide persistir")
ok(q("SELECT COUNT(*) FROM equipo WHERE nombre='A MEDIAS'")[0][0] == 0 and q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq, "…y no queda un equipo a medio armar")
# deshacer una alta rápida: se lleva solo sus conectores propios
f, _ = falla("equipo_baja", id=ar["id"], solo_si_sin_uso=True)
data("equipo_baja", id=ar["id"], solo_si_sin_uso=True, conectores_propios=ar["n_conectores"])
ok(q("SELECT COUNT(*) FROM equipo WHERE id_equipo=?", (ar["id"],))[0][0] == 0 and q("SELECT COUNT(*) FROM conector WHERE id_equipo=?", (ar["id"],))[0][0] == 0,
   "deshacer la alta rápida borra el equipo y sus conectores")
ar3 = data("equipo_alta_rapida", valores={"nombre": "CONECTADO", "id_tipo_equipo": 1}, conectores=[{"id_tipo_conector": 1, "direccion": "OUT", "cantidad": 1}])
data("conexion_alta", id_cable=1, id_conector=ar3["ids_conectores"][0])
f, _ = falla("equipo_baja", id=ar3["id"], solo_si_sin_uso=True, conectores_propios=1)
ok("conexiones" in f["error"], "si lo conectaron mientras tanto, el deshacer se niega")

# deshacer un alta que dejó el equipo marcado como crítico: la marca es del equipo, no bloquea
crit = data("equipo_alta", valores={"nombre": "CRITICO", "critico": True})["id"]
data("equipo_baja", id=crit, solo_si_sin_uso=True)
ok(q("SELECT COUNT(*) FROM equipo WHERE id_equipo=?", (crit,))[0][0] == 0 and q("SELECT COUNT(*) FROM equipo_critico WHERE id_equipo=?", (crit,))[0][0] == 0,
   "deshacer un alta con equipo crítico: se borra (la marca no cuenta como uso)")

# 6) conectores
r = data("conector_formulario", id_equipo=1)
ok(r["valores"] is None and r["id_equipo"] == 1 and r["equipo"] == "CAM 1" and esq(r)["nombre"]["requerido"] is True, "formulario de alta de conector")
r = data("conector_formulario", id_conector=1)
ok(r["valores"]["nombre"] == "OUT 1" and r["id_equipo"] == 1 and not esq(r)["nombre"]["requerido"], "edición: valores y equipo fijo")
falla("conector_formulario", id_conector=999)
falla("conector_formulario")
ca = data("conector_alta", id_equipo=1, valores={"nombre": " OUT 2 ", "id_tipo_conector": 4, "id_tipo_ficha": 1, "modo_balance": "BALANCEADO"})
ok(ca["nombre"] == "OUT 2" and ca["valores"]["id_tipo_ficha"] == 1 and ca["valores"]["modo_balance"] == "BALANCEADO", "alta de conector con formato eléctrico")
r, _ = call("conector_alta", id_equipo=1, valores={"nombre": "", "id_tipo_conector": 99, "modo_canal": "X"})
ok(not r["ok"] and set(r["campos"]) == {"nombre", "id_tipo_conector", "modo_canal"}, f"errores por campo: {r.get('campos')}")
falla("conector_alta", id_equipo=999, valores={"nombre": "x"})
falla("conector_alta", id_equipo=1, valores={"nombre": "x", "id_imagen": 1})
mc = data("conector_modificar", id=1, valores={**data("conector_formulario", id_conector=1)["valores"], "nombre": "OUT PGM", "id_tipo_conector": 4,
                                               "id_tipo_ficha": 1, "modo_canal": "ESTEREO"})
ok(mc["anterior"]["nombre"] == "OUT 1" and mc["valores"]["modo_canal"] == "ESTEREO", "editar conector")
ok(q("SELECT id_equipo, id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen FROM conector WHERE id_conector=1")[0] == (1, 1, 30, 40),
   "equipo, imagen y coordenadas del conector intactos tras editar")
data("conector_modificar", id=1, valores=mc["anterior"])
ok(q("SELECT nombre, id_tipo_conector, id_tipo_ficha, modo_canal FROM conector WHERE id_conector=1")[0] == ("OUT 1", 1, None, None), "deshacer: valores anteriores")
# señal y formato
q_ = sqlite3.connect(m.DB_PATH)
q_.executescript("INSERT INTO senal(id_senal,nombre) VALUES (1,'PGM'),(2,'ISO'); INSERT INTO tipo_formato_senal(id_formato,nombre) VALUES (1,'SDI');")
q_.commit()
q_.close()
r = data("conector_formulario", id_conector=1)
ok("id_senal" in esq(r) and "id_formato" in esq(r), "con tablas de señal el formulario ofrece señal y formato")
r, _ = call("conector_modificar", id=1, valores={**r["valores"], "id_formato": 1})
ok(not r["ok"] and "id_senal" in r["campos"], "formato sin señal: error en la señal")
base = data("conector_formulario", id_conector=1)["valores"]
data("conector_modificar", id=1, valores={**base, "id_senal": 1, "id_formato": 1})
ok(q("SELECT id_senal, id_formato, origen FROM senal_en_conector WHERE id_conector=1")[0] == (1, 1, "MANUAL"), "señal asignada (origen MANUAL)")
q_ = sqlite3.connect(m.DB_PATH)
q_.execute("UPDATE senal_en_conector SET origen='PROPAGADA' WHERE id_conector=1")
q_.commit()
q_.close()
data("conector_modificar", id=1, valores={**data("conector_formulario", id_conector=1)["valores"], "nombre": "OUT 1 b"})
ok(q("SELECT origen FROM senal_en_conector WHERE id_conector=1")[0][0] == "PROPAGADA", "editar otro campo no pisa el origen de la señal")
data("conector_modificar", id=1, valores={**data("conector_formulario", id_conector=1)["valores"], "id_senal": None, "id_formato": None, "nombre": "OUT 1"})
ok(q("SELECT COUNT(*) FROM senal_en_conector WHERE id_conector=1")[0][0] == 0, "quitar la señal")
# usos y baja
antes = foto()
uc = data("conector_usos", id_conector=1)
ok({x["tabla"]: x["n"] for x in uc["usos"]}.get("conexion") == 1 and foto() == antes, "conector_usos informa las conexiones y no escribe")
falla("conector_baja", id=1, solo_si_sin_uso=True)
bc = data("conector_baja", id=ca["id"])
ok(bc["usos"] == [] and bc["fila"]["nombre"] == "OUT 2", "baja de un conector sin uso")
data("conector_restaurar", id=ca["id"], fila=bc["fila"])
ok(q("SELECT nombre, id_tipo_ficha, modo_balance FROM conector WHERE id_conector=?", (ca["id"],))[0] == ("OUT 2", 1, "BALANCEADO"), "restaurar: mismos datos")
falla("conector_restaurar", id=ca["id"], fila=bc["fila"])
bc1 = data("conector_baja", id=1)
ok({x["tabla"] for x in bc1["usos"]} == {"conexion"} and q("SELECT COUNT(*) FROM conexion WHERE id_conector=1")[0][0] == 0, "la baja con conexiones las arrastra y lo informa")
ok(q("PRAGMA integrity_check")[0][0] == "ok" and q("PRAGMA foreign_key_check") == [], "la base quedó sana y sin claves foráneas rotas")

# 6b) extremo desconectado (equipo FANTASMA)
n_eq0 = q("SELECT COUNT(*) FROM equipo")[0][0]
cab = data("cable_alta", valores={"codigo": "C-100", "estado": "VERIFICADO"})["id"]
r = data("cable_extremo_formulario", id_cable=cab)
ok(r["n_extremos"] == 0 and r["lado"] is None and r["puede"] is False and "FANTASMA" in r["motivo"], f"sin tipo FANTASMA en el catálogo: no se puede ({r})")
f, _ = falla("cable_extremo_desconectado", id_cable=cab, lado="A")
ok("FANTASMA" in f["error"] and "escribio" not in f and q("SELECT COUNT(*) FROM equipo")[0][0] == n_eq0, "sin tipo FANTASMA: avisa y no escribe")
q_ = sqlite3.connect(m.DB_PATH)
q_.execute("INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (9,'EXTREMO','FANTASMA')")
q_.commit()
q_.close()
r = data("cable_extremo_formulario", id_cable=cab)
ok(r["puede"] is True and r["lado"] is None and r["motivo"] is None, "con tipo FANTASMA y sin extremos: se puede, el lado se elige")
r, _ = call("cable_extremo_desconectado", id_cable=cab)
ok(not r["ok"] and r["campos"] == {"lado": "Obligatorio"} and "escribio" not in r, "sin extremos el lado es obligatorio")
r, _ = call("cable_extremo_desconectado", id_cable=cab, lado="Z")
ok(not r["ok"] and r["campos"] == {"lado": "Elegí una opción válida"}, "lado inválido")
ea = data("cable_extremo_desconectado", id_cable=cab, lado="A")
ok(ea["nombre"] == "EXTREMO A DESCONECTADO C-100" and ea["lado"] == "A", "equipo A con el nombre del desktop")
ok(q("SELECT e.id_tipo_equipo, c.nombre, c.id_tipo_conector FROM equipo e JOIN conector c ON c.id_equipo=e.id_equipo WHERE e.id_equipo=?", (ea["id_equipo"],))[0] == (9, "OUT", 4),
   "tipo FANTASMA y un conector OUT (el de nombre exacto OUT)")
ok(q("SELECT id_cable, id_conector FROM conexion WHERE id_conexion=?", (ea["id_conexion"],))[0] == (cab, ea["id_conector"]), "conectado al cable")
r = data("cable_extremo_formulario", id_cable=cab)
ok(r["n_extremos"] == 1 and r["lado"] == "B" and r["nombre_tipo"] == "OUT" and r["puede"], "con un extremo OUT el lado que falta se infiere: B")
eb = data("cable_extremo_desconectado", id_cable=cab, lado="A")            # el lado pedido se ignora: manda el inferido
ok(eb["lado"] == "B" and q("SELECT c.nombre FROM conector c WHERE c.id_conector=?", (eb["id_conector"],))[0][0] == "IN", "se infiere el lado B (conector IN)")
r = data("cable_extremo_formulario", id_cable=cab)
ok(r["puede"] is False and "dos extremos" in r["motivo"], "con dos extremos ya no se puede")
f, _ = falla("cable_extremo_desconectado", id_cable=cab, lado="B")
ok("dos extremos" in f["error"] and q("SELECT COUNT(*) FROM conexion WHERE id_cable=?", (cab,))[0][0] == 2, "tercer extremo: rechazado")
falla("cable_extremo_formulario", id_cable=9999)
falla("cable_extremo_desconectado", id_cable=9999, lado="A")
# deshacer: se lleva el equipo, su conector y su conexión; se niega si ya tiene algo más
data("cable_extremo_deshacer", id_equipo=eb["id_equipo"], id_conexion=eb["id_conexion"])
ok(q("SELECT COUNT(*) FROM equipo WHERE id_equipo=?", (eb["id_equipo"],))[0][0] == 0 and q("SELECT COUNT(*) FROM conexion WHERE id_conexion=?", (eb["id_conexion"],))[0][0] == 0,
   "deshacer: sin equipo ni conexión")
data("conector_alta", id_equipo=ea["id_equipo"], valores={"nombre": "EXTRA", "id_tipo_conector": 1})
f, _ = falla("cable_extremo_deshacer", id_equipo=ea["id_equipo"], id_conexion=ea["id_conexion"])
ok(q("SELECT COUNT(*) FROM equipo WHERE id_equipo=?", (ea["id_equipo"],))[0][0] == 1, "si el equipo ya tiene otro conector, el deshacer se niega")
falla("cable_extremo_deshacer", id_equipo=1, id_conexion=ea["id_conexion"])
# cable con un extremo suelto (sin conector): no se puede inferir el lado
cab2 = data("cable_alta", valores={"codigo": "C-101", "estado": "VERIFICADO"})["id"]
q_ = sqlite3.connect(m.DB_PATH)
q_.execute("INSERT INTO conexion(id_cable,id_conector,es_conexion_interna) VALUES (?,NULL,0)", (cab2,))
q_.commit()
q_.close()
r = data("cable_extremo_formulario", id_cable=cab2)
ok(r["n_extremos"] == 1 and r["lado"] is None and r["puede"], "extremo suelto: no se infiere el lado")
ok(q("PRAGMA integrity_check")[0][0] == "ok" and q("PRAGMA foreign_key_check") == [], "la base sigue sana")

# 7) base vieja: sin las columnas/tablas opcionales las lecturas no se rompen y escribir otro campo no migra nada
con = sqlite3.connect(m.DB_PATH)
con.executescript("DROP TABLE IF EXISTS equipo_critico;")
con.commit()
con.close()
r = data("equipo_formulario", id_equipo=1)
ok(r["valores"]["critico"] is False, "sin tabla equipo_critico: no crítico")
data("equipo_modificar", id=1, valores={**r["valores"], "modelo": "otro"})
ok(q("SELECT COUNT(*) FROM sqlite_master WHERE name='equipo_critico'")[0][0] == 0, "guardar otro campo no crea la tabla equipo_critico")
data("equipo_modificar", id=1, valores={**r["valores"], "modelo": "otro", "critico": True})
ok(q("SELECT COUNT(*) FROM equipo_critico WHERE id_equipo=1")[0][0] == 1, "marcar crítico sí la crea")

print(f"OK — {n} chequeos")
