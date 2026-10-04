#!/usr/bin/env python3
"""Test nativo de ui_web/catalogos_web.py (Fase B.2): ABM de catálogos básicos vía bridge.call. Mismo layout temporal que
test_datos.py (no toca data/database/).

Uso (desde la raíz del repo):  python3 ui_web/tests/test_catalogos.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_catalogos_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"), ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
for f in ("bridge.py", "catalogos_web.py", "cables_web.py", "equipos_web.py"):
    shutil.copy(os.path.join(RAIZ, "ui_web", f), os.path.join(app, f))
sys.path.insert(0, app)

import core.modelo as m  # noqa: E402
import bridge as b  # noqa: E402
import catalogos_web as cw  # noqa: E402

M = m.Modelo
n = 0


def ok(cond, msg):
    global n
    n += 1
    assert cond, msg


def call(fn, **args):
    """Como JS: bridge.call → dict. Devuelve (respuesta, texto crudo)."""
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


con = sqlite3.connect(m.DB_PATH)
con.executescript("""
INSERT INTO marca(id_marca,nombre) VALUES (1,'Sony'),(2,'Grass Valley'),(3,'Sin uso');
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'FANTASMA','FANTASMA');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC'),(2,'XLR');
INSERT INTO tipo_cable(id_tipo_cable,nombre) VALUES (1,'RG59');
INSERT INTO tipo_ficha(id_tipo_ficha,nombre) VALUES (1,'TRS');
INSERT INTO imagen(id_imagen,path_archivo,descripcion) VALUES (1,'cam.png','Frente'),(2,'huerfana.png',NULL);
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre,id_marca,id_imagen) VALUES (1,1,'CAM 1',1,1),(2,1,'CAM 2',1,NULL);
INSERT INTO equipo_catalogo(id_equipo_catalogo,nombre_molde,id_tipo_equipo,id_marca,modelo) VALUES (1,'HDC-3500',1,1,'HDC-3500');
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector,id_imagen) VALUES (1,'OUT 1',1,1,1),(2,'IN 1',2,1,NULL);
INSERT INTO cable(id_cable,codigo,id_tipo_cable,id_tipo_ficha) VALUES (1,'C-001',1,1);
""")
con.commit(); con.close()
M.asegurar_tablas_senal()
M.asegurar_columnas_riesgo_senal()
M.asegurar_columnas_control_idioma()
con = sqlite3.connect(m.DB_PATH)
con.executescript("""
INSERT INTO senal(id_senal,nombre,tipo_contenido,descripcion) VALUES (1,'PGM','VIDEO','Programa'),(2,'AUX','CUSTOM',NULL);
INSERT INTO tipo_formato_senal(id_formato,nombre) VALUES (1,'1080i59.94'),(2,'sin uso');
INSERT INTO senal_en_conector(id_conector,id_senal,id_formato) VALUES (1,1,1);
INSERT INTO senal_linaje(id_senal_hijo,id_senal_padre) VALUES (2,1);
INSERT INTO regla_logica(id_tipo_equipo,nombre,operador) VALUES (1,'R1','AND');
INSERT INTO catalogo_simbolo_conector(id_tipo_ficha,svg_fragmento) VALUES (1,'<path/>');
""")
con.commit(); con.close()

# 0) las funciones están registradas y las de escritura se distinguen de las de lectura
ok({"catalogo_lista", "catalogo_alta", "catalogo_modificar", "catalogo_baja", "catalogo_restaurar"} <= set(b.FUNCIONES), "registradas en el bridge")
ok({"catalogo_alta", "catalogo_modificar", "catalogo_baja", "catalogo_restaurar"} <= b.ESCRITURAS and "catalogo_lista" not in b.ESCRITURAS, "ESCRITURAS incluye las 4 de escritura (y no la lectura)")
ok(set(data("firmas")["catalogo_baja"][i]["nombre"] for i in range(3)) == {"catalogo", "id", "solo_si_sin_uso"}, "firmas")

# 1) lista: filas, esquema y usos
r = data("catalogo_lista", catalogo="marca")
ok([f["nombre"] for f in r["filas"]] == ["Grass Valley", "Sin uso", "Sony"], f"orden alfabético sin distinguir mayúsculas: {r['filas']}")
sony = next(f for f in r["filas"] if f["id"] == 1)
ok(sony["n_usos"] == 3 and {(u["tabla"], u["n"], u["efecto"]) for u in sony["usos"]} == {("equipo", 2, "anula"), ("equipo_catalogo", 1, "anula")},
   f"usos de Sony: {sony['usos']}")
ok(next(f for f in r["filas"] if f["id"] == 3)["usos"] == [], "una marca sin uso no tiene usos")
ok(r["esquema"] == [{"nombre": "nombre", "tipo": "texto", "requerido": True, "largo": 120}], f"esquema de marca: {r['esquema']}")
esq = {e["nombre"]: e for e in data("catalogo_lista", catalogo="tipo_equipo")["esquema"]}
ok(esq["rol_senal"]["opciones"] == list(M.ROLES_SENAL) and "FANTASMA" in esq["rol_senal"]["opciones"], "los roles salen de Modelo.ROLES_SENAL (con FANTASMA)")
f, _ = falla("catalogo_lista", catalogo="inexistente")
ok("Catálogo desconocido" in f["error"] and "escribio" not in f and not f["error"].startswith("ErrorSinCambios"), f"catálogo desconocido: {f}")

# 2) alta de marca: valida, normaliza, rechaza repetidos y vacíos
nuevo, crudo = call("catalogo_alta", catalogo="marca", valores={"nombre": "  Panasonic  "})
ok(nuevo["ok"] and nuevo["data"]["fila"]["nombre"] == "Panasonic" and nuevo["data"]["id"] == nuevo["data"]["fila"]["id"], f"alta de marca: {nuevo}")
ok(crudo.startswith('{"escribio": true'), "la respuesta de una escritura abre con escribio (contrato con worker.js): " + crudo[:40])
ok(q("SELECT nombre FROM marca WHERE id_marca=?", (nuevo["data"]["id"],)) == [("Panasonic",)], "quedó en la base, sin espacios sobrantes")
ok(q("SELECT fecha_ultima_edicion FROM marca WHERE id_marca=?", (nuevo["data"]["id"],))[0][0] is not None, "los triggers de la base pusieron la fecha")
for malo, motivo in (("sony", "Ya existe uno con ese nombre"), ("  SONY ", "Ya existe uno con ese nombre"), ("Grass   Valley", "Ya existe uno con ese nombre"),
                     ("", "Obligatorio"), ("   ", "Obligatorio"), (None, "Obligatorio"), ("x" * 121, "Texto demasiado largo")):
    f, crudo = call("catalogo_alta", catalogo="marca", valores={"nombre": malo})
    ok(not f["ok"] and f["campos"] == {"nombre": motivo}, f"alta de {malo!r}: {f}")
    ok("escribio" not in f and not crudo.startswith('{"escribio"'), "un error de validación NO pide persistir")
    ok(f["error"] == "Hay datos que corregir", "el mensaje va sin el nombre de la clase (es para el usuario)")
ok(q("SELECT COUNT(*) FROM marca")[0][0] == 4, "ningún alta rechazada dejó filas")
f, _ = falla("catalogo_alta", catalogo="marca", valores={"nombre": "A", "otro": 1})
ok("Campos desconocidos" in f["error"], f"campo desconocido: {f}")
f, _ = falla("catalogo_alta", catalogo="marca", valores="Sony")
ok("objeto" in f["error"], "valores debe ser un objeto")

# 3) modificar: devuelve lo anterior; renombrar a uno existente falla; cambiar solo mayúsculas se permite
mod = data("catalogo_modificar", catalogo="marca", id=3, valores={"nombre": "Ya sin uso"})
ok(mod["anterior"] == {"nombre": "Sin uso"} and mod["fila"]["nombre"] == "Ya sin uso", f"modificar: {mod}")
f, _ = falla("catalogo_modificar", catalogo="marca", id=3, valores={"nombre": "sony"})
ok(f["campos"] == {"nombre": "Ya existe uno con ese nombre"}, "renombrar a un nombre existente")
ok(data("catalogo_modificar", catalogo="marca", id=3, valores={"nombre": "YA SIN USO"})["fila"]["nombre"] == "YA SIN USO", "cambiar solo mayúsculas del propio nombre")
f, _ = falla("catalogo_modificar", catalogo="marca", id=999, valores={"nombre": "X"})
ok("No existe" in f["error"] and "escribio" not in f, f"id inexistente: {f}")
f, _ = falla("catalogo_modificar", catalogo="marca", id="abc", valores={"nombre": "X"})
ok("Id inválido" in f["error"], "id inválido")
# una fila ya duplicada (el desktop lo permite) se puede seguir editando mientras no se le cambie el nombre
con = sqlite3.connect(m.DB_PATH); con.execute("INSERT INTO marca(id_marca,nombre) VALUES (10,'Repe'),(11,'Repe')"); con.commit(); con.close()
ok(data("catalogo_modificar", catalogo="marca", id=11, valores={"nombre": "Repe"})["fila"]["id"] == 11, "editar sin cambiar el nombre de una fila ya duplicada")

# 4) baja: SET NULL sobre lo que la usaba; solo_si_sin_uso; restaurar con el mismo id
f, _ = falla("catalogo_baja", catalogo="marca", id=1, solo_si_sin_uso=True)
ok("ya se usa" in f["error"] and "escribio" not in f and q("SELECT COUNT(*) FROM marca WHERE id_marca=1")[0][0] == 1, f"solo_si_sin_uso se niega: {f}")
baja = data("catalogo_baja", catalogo="marca", id=1)
ok(baja["anterior"] == {"nombre": "Sony"} and {(u["tabla"], u["n"]) for u in baja["usos"]} == {("equipo", 2), ("equipo_catalogo", 1)}, f"baja con uso: {baja}")
ok(q("SELECT id_marca FROM equipo WHERE id_equipo IN (1,2)") == [(None,), (None,)] and q("SELECT id_marca FROM equipo_catalogo")[0][0] is None, "las FK dejaron NULL lo que la usaba (SET NULL)")
ok(q("SELECT COUNT(*) FROM equipo")[0][0] == 2, "no se borraron los equipos")
sin = data("catalogo_baja", catalogo="marca", id=3, solo_si_sin_uso=True)
ok(sin["usos"] == [] and sin["anterior"] == {"nombre": "YA SIN USO"}, "baja de una marca sin uso")
rest = data("catalogo_restaurar", catalogo="marca", id=3, valores=sin["anterior"])
ok(rest["id"] == 3 and rest["fila"]["nombre"] == "YA SIN USO" and q("SELECT nombre FROM marca WHERE id_marca=3") == [("YA SIN USO",)], f"restaurar con el mismo id: {rest}")
f, _ = falla("catalogo_restaurar", catalogo="marca", id=3, valores={"nombre": "Otra"})
ok("Ya existe un registro con el id 3" in f["error"], "no se restaura sobre un id existente")
f, _ = falla("catalogo_baja", catalogo="marca", id=12345)
ok("No existe" in f["error"], "baja de un id inexistente")

# 5) tipos de equipo: rol, FANTASMA se conserva al editar, CASCADE sobre reglas lógicas
te = data("catalogo_alta", catalogo="tipo_equipo", valores={"nombre": "MATRIZ", "rol_senal": "ENRUTADOR"})
ok(M.devolver_rol_senal_tipo_equipo(te["id"]) == "ENRUTADOR", "el rol quedó como lo lee Modelo")
f, _ = falla("catalogo_alta", catalogo="tipo_equipo", valores={"nombre": "X", "rol_senal": "INVENTADO"})
ok(f["campos"] == {"rol_senal": "Elegí una opción válida"}, "rol inválido")
f, _ = falla("catalogo_alta", catalogo="tipo_equipo", valores={"nombre": "X", "rol_senal": None})
ok(f["campos"] == {"rol_senal": "Obligatorio"}, "el rol es obligatorio")
f, _ = falla("catalogo_alta", catalogo="tipo_equipo", valores={"nombre": "camara", "rol_senal": "FUENTE"})
ok(f["campos"] == {"nombre": "Ya existe uno con ese nombre"}, "nombre repetido de tipo de equipo")
fan = data("catalogo_modificar", catalogo="tipo_equipo", id=2, valores={"nombre": "FANTASMA 2", "rol_senal": "FANTASMA"})
ok(M.devolver_rol_senal_tipo_equipo(2) == "FANTASMA" and fan["anterior"] == {"nombre": "FANTASMA", "rol_senal": "FANTASMA"}, "editar el nombre de un tipo FANTASMA no le cambia el rol")
mr = data("catalogo_modificar", catalogo="tipo_equipo", id=1, valores={"nombre": "CAMARA", "rol_senal": "PROCESADOR"})
ok(M.devolver_rol_senal_tipo_equipo(1) == "PROCESADOR" and mr["anterior"]["rol_senal"] == "FUENTE", "cambio de rol")
lt = next(f for f in data("catalogo_lista", catalogo="tipo_equipo")["filas"] if f["id"] == 1)
ok({(u["tabla"], u["efecto"]) for u in lt["usos"]} == {("equipo", "anula"), ("equipo_catalogo", "anula"), ("regla_logica", "borra")}, f"usos de un tipo de equipo (con CASCADE): {lt['usos']}")
bt = data("catalogo_baja", catalogo="tipo_equipo", id=1)
ok(q("SELECT COUNT(*) FROM regla_logica")[0][0] == 0 and q("SELECT id_tipo_equipo FROM equipo")[0][0] is None, "CASCADE borró la regla lógica y SET NULL dejó los equipos sin tipo")

# 6) tipos de conector: es_referencia_generada
tc = data("catalogo_alta", catalogo="tipo_conector", valores={"nombre": "REFOUT", "es_referencia_generada": True})
ok(M.devolver_control_idioma_tipo_conector(tc["id"])[1] == 1 and tc["fila"]["es_referencia_generada"] is True, "alta con referencia generada")
data("catalogo_modificar", catalogo="tipo_conector", id=tc["id"], valores={"nombre": "REFOUT", "es_referencia_generada": False})
ok(M.devolver_control_idioma_tipo_conector(tc["id"])[1] == 0, "se destilda")
ok(next(f for f in data("catalogo_lista", catalogo="tipo_conector")["filas"] if f["id"] == 1)["es_referencia_generada"] is False, "la lista lo devuelve como booleano")
ok(data("catalogo_alta", catalogo="tipo_conector", valores={"nombre": "75"})["fila"]["nombre"] in (75, "75"), "un nombre solo de dígitos (columna INTEGER) se guarda")
f, _ = falla("catalogo_alta", catalogo="tipo_conector", valores={"nombre": "75"})
ok(f["campos"] == {"nombre": "Ya existe uno con ese nombre"}, "…y se detecta como repetido aunque SQLite lo devuelva como int")

# 7) tipos de cable: números, CHECK de naturaleza
cb = data("catalogo_alta", catalogo="tipo_cable", valores={"nombre": "Belden", "naturaleza_senal": "DIGITAL", "long_max_balanceado_m": "10,5",
                                                          "long_max_desbalanceado_m": 3, "ancho_banda_mhz": None})
ok(M.devolver_riesgo_tipo_cable(cb["id"]) == ["DIGITAL", 10.5, 3.0, None], f"riesgo como lo lee Modelo: {M.devolver_riesgo_tipo_cable(cb['id'])}")
f, _ = falla("catalogo_alta", catalogo="tipo_cable", valores={"nombre": "Z", "long_max_balanceado_m": -1, "naturaleza_senal": "MAGICA", "ancho_banda_mhz": "abc"})
ok(f["campos"] == {"long_max_balanceado_m": "No puede ser negativo", "naturaleza_senal": "Elegí una opción válida", "ancho_banda_mhz": "Debe ser un número"}, f"varios errores a la vez: {f['campos']}")
ok(q("SELECT COUNT(*) FROM tipo_cable")[0][0] == 2, "sin filas a medias tras los errores")
ok(data("catalogo_modificar", catalogo="tipo_cable", id=cb["id"], valores={"nombre": "Belden", "naturaleza_senal": None})["fila"]["naturaleza_senal"] is None, "vaciar la naturaleza")
ok(next(f for f in data("catalogo_lista", catalogo="tipo_cable")["filas"] if f["id"] == 1)["usos"] == [{"tabla": "cable", "n": 1, "efecto": "anula"}], "usos de un tipo de cable")

# 8) tipos de ficha
tf = data("catalogo_alta", catalogo="tipo_ficha", valores={"nombre": "XLR3", "n_conductores": "3", "modo_balance_default": "BALANCEADO", "modo_canal_default": "MONO", "ancho_banda_mhz": 0.02})
ok(M.devolver_riesgo_tipo_ficha(tf["id"]) == [3, "BALANCEADO", "MONO", 0.02], f"riesgo de ficha como lo lee Modelo: {M.devolver_riesgo_tipo_ficha(tf['id'])}")
for malo, motivo in ((0, "Debe ser mayor que cero"), (2.5, "Debe ser un número entero"), ("x", "Debe ser un número entero")):
    f, _ = falla("catalogo_alta", catalogo="tipo_ficha", valores={"nombre": "Q", "n_conductores": malo})
    ok(f["campos"] == {"n_conductores": motivo}, f"n_conductores={malo!r}: {f['campos']}")
f, _ = falla("catalogo_alta", catalogo="tipo_ficha", valores={"nombre": "Q", "modo_balance_default": "X", "modo_canal_default": "Y"})
ok(set(f["campos"]) == {"modo_balance_default", "modo_canal_default"}, "modos fuera del CHECK")
bf = data("catalogo_baja", catalogo="tipo_ficha", id=1)
ok({(u["tabla"], u["efecto"]) for u in bf["usos"]} == {("cable", "anula"), ("catalogo_simbolo_conector", "borra")}, f"usos de una ficha: {bf['usos']}")
ok(q("SELECT COUNT(*) FROM catalogo_simbolo_conector")[0][0] == 0 and q("SELECT id_tipo_ficha FROM cable")[0][0] is None, "CASCADE al símbolo, SET NULL al cable")

# 9) señales: texto libre en tipo_contenido, CASCADE sobre asignaciones y linaje
ok(next(e for e in data("catalogo_lista", catalogo="senal")["esquema"] if e["nombre"] == "tipo_contenido")["sugeridos"] == ["VIDEO", "AUDIO", "DATOS", "EMBEBIDO"], "tipos de contenido sugeridos")
sn = data("catalogo_alta", catalogo="senal", valores={"nombre": "TALLY", "tipo_contenido": "OTRO", "descripcion": "x" * 500})
ok(sn["fila"]["tipo_contenido"] == "OTRO", "un tipo de contenido que no es de los sugeridos se acepta (el campo es libre)")
f, _ = falla("catalogo_alta", catalogo="senal", valores={"nombre": "tally"})
ok(f["campos"] == {"nombre": "Ya existe uno con ese nombre"}, "señal repetida")
f, _ = falla("catalogo_alta", catalogo="senal", valores={"nombre": "Z", "descripcion": "x" * 501})
ok(f["campos"] == {"descripcion": "Texto demasiado largo"}, "descripción muy larga")
pgm = next(f for f in data("catalogo_lista", catalogo="senal")["filas"] if f["id"] == 1)
ok({(u["tabla"], u["n"], u["efecto"]) for u in pgm["usos"]} == {("senal_en_conector", 1, "borra"), ("senal_linaje", 1, "borra")}, f"usos de una señal: {pgm['usos']}")
data("catalogo_baja", catalogo="senal", id=1)
ok(q("SELECT COUNT(*) FROM senal_en_conector")[0][0] == 0 and q("SELECT COUNT(*) FROM senal_linaje")[0][0] == 0, "CASCADE: se fue la asignación al conector y el linaje")

# 10) formatos de señal: SET NULL
con = sqlite3.connect(m.DB_PATH); con.execute("INSERT INTO senal_en_conector(id_conector,id_senal,id_formato) VALUES (2,2,1)"); con.commit(); con.close()
ok(data("catalogo_baja", catalogo="formato_senal", id=1)["usos"] == [{"tabla": "senal_en_conector", "n": 1, "efecto": "anula"}], "usos de un formato")
ok(q("SELECT id_formato FROM senal_en_conector")[0][0] is None and q("SELECT COUNT(*) FROM senal_en_conector")[0][0] == 1, "SET NULL: la asignación sigue, sin formato")

# 11) imágenes: sin control de repetidos; el archivo es obligatorio; SET NULL / CASCADE
im = data("catalogo_alta", catalogo="imagen", valores={"path_archivo": "cam.png", "descripcion": "Otra vez"})
ok(im["fila"]["path_archivo"] == "cam.png" and im["id"] > 2, "dos registros pueden apuntar al mismo archivo")
f, _ = falla("catalogo_alta", catalogo="imagen", valores={"path_archivo": "  ", "descripcion": "x"})
ok(f["campos"] == {"path_archivo": "Obligatorio"}, "el archivo es obligatorio")
con = sqlite3.connect(m.DB_PATH); con.execute("INSERT INTO imagen_senal_conector(id_conector,id_imagen) VALUES (1,1)"); con.commit(); con.close()
bi = data("catalogo_baja", catalogo="imagen", id=1)
ok({(u["tabla"], u["efecto"]) for u in bi["usos"]} == {("conector", "anula"), ("equipo", "anula"), ("imagen_senal_conector", "borra")}, f"usos de una imagen: {bi['usos']}")
ok(q("SELECT id_imagen FROM conector WHERE id_conector=1")[0][0] is None and q("SELECT COUNT(*) FROM imagen_senal_conector")[0][0] == 0, "SET NULL en el conector, CASCADE en la imagen de señal")
ok(data("catalogo_modificar", catalogo="imagen", id=2, valores={"path_archivo": "otra.png", "descripcion": None})["anterior"] == {"path_archivo": "huerfana.png", "descripcion": None}, "modificar imagen")

# 12) contrato de bridge.call: lecturas sin escribio; fallo inesperado de una escritura SÍ pide persistir
r, crudo = call("catalogo_lista", catalogo="marca")
ok(r["ok"] and "escribio" not in r and crudo.startswith('{"ok": true'), "una lectura no pide persistir")
original = cw._alta


def _roto(*a, **k):
    raise sqlite3.IntegrityError("simulado")


cw._alta = _roto
f, crudo = falla("catalogo_alta", catalogo="marca", valores={"nombre": "Nueva"})
cw._alta = original
ok(crudo.startswith('{"escribio": true') and f["error"] == "IntegrityError: simulado" and "campos" not in f, f"un fallo inesperado pudo dejar la base a medias → persistir: {crudo[:90]}")
ok(call("catalogo_alta", catalogo="marca")[0]["error"].startswith("ValueError: catalogo_alta: falta"), "argumentos faltantes: mismo mensaje que el resto del bridge")

# 13) base vieja sin las tablas de señal: la lista de señales/formatos queda vacía en vez de romper
con = sqlite3.connect(m.DB_PATH)
con.executescript("PRAGMA foreign_keys=OFF; DROP TABLE senal_en_conector; DROP TABLE senal_linaje; DROP TABLE senal; DROP TABLE tipo_formato_senal;")
con.close()
ok(data("catalogo_lista", catalogo="senal")["filas"] == [] and data("catalogo_lista", catalogo="formato_senal")["filas"] == [], "sin tablas de señal: lista vacía")
ok(isinstance(data("catalogo_lista", catalogo="marca")["filas"], list), "las demás listas siguen andando")

# 14) la base quedó íntegra
c = sqlite3.connect(m.DB_PATH)
ok(c.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and c.execute("PRAGMA foreign_key_check").fetchall() == [], "integrity_check y foreign_key_check limpios")
c.close()

shutil.rmtree(tmp, ignore_errors=True)
print(f"✔ test_catalogos: {n} chequeos OK")
