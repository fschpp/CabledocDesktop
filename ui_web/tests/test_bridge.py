#!/usr/bin/env python3
"""Test nativo de ui_web/bridge.py (Fase A.1) sobre una base de prueba chica.

Replica el layout de Pyodide: copia core/ y data/schema_db.sql a una carpeta
temporal (así Modelo crea su db.db ahí y NO toca data/database/ del repo),
inserta datos de ejemplo y llama a cada función del bridge.

Uso (desde la raíz del repo):  python3 ui_web/tests/test_bridge.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="cabledoc_bridge_")
app = os.path.join(tmp, "app")
shutil.copytree(os.path.join(RAIZ, "core"), os.path.join(app, "core"),
                ignore=shutil.ignore_patterns("__pycache__", "log.txt"))
os.makedirs(os.path.join(app, "data"))
shutil.copy(os.path.join(RAIZ, "data", "schema_db.sql"), os.path.join(app, "data", "schema_db.sql"))
shutil.copy(os.path.join(RAIZ, "ui_web", "bridge.py"), os.path.join(app, "bridge.py"))
sys.path.insert(0, app)

import core.modelo as m  # crea app/data/database/db.db desde el esquema
assert m.DB_PATH.startswith(app), m.DB_PATH

SQL = """
INSERT INTO marca(id_marca,nombre) VALUES (1,'Sony'),(2,'Blackmagic');
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE'),(2,'MATRIZ','DISTRIBUIDOR');
INSERT INTO tipo_conector(id_tipo_conector,nombre) VALUES (1,'BNC'),(2,'XLR');
INSERT INTO tipo_ficha(id_tipo_ficha,nombre,n_conductores) VALUES (1,'BNC 75',2);
INSERT INTO tipo_cable(id_tipo_cable,nombre,naturaleza_senal) VALUES (1,'RG59','DIGITAL');
INSERT INTO imagen(id_imagen,path_archivo,descripcion,mm_por_pixel) VALUES (1,'cam.png','Frente cámara',0.25);
INSERT INTO equipo(id_equipo,id_tipo_equipo,id_marca,num_inventario,num_serie,modelo,nombre,id_imagen)
  VALUES (1,1,1,100,'S1','HDC-3500','CAM 1',1),(2,2,2,101,'S2','Videohub','MATRIZ A',NULL),
         (3,1,1,102,'S3','HDC-3500','CAM 2',NULL),(4,2,NULL,NULL,NULL,NULL,'SIN EQUIPO',NULL);
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector,id_imagen,coordenada_x_en_imagen,coordenada_y_en_imagen,id_tipo_ficha)
  VALUES (1,'OUT 1',1,1,1,40,55,1),(2,'IN 1',2,1,NULL,NULL,NULL,1),(3,'OUT 1',2,1,NULL,NULL,NULL,1),(4,'OUT 1',3,1,NULL,NULL,NULL,NULL);
INSERT INTO cable(id_cable,codigo,longitud,id_tipo_cable,id_tipo_ficha,unidad_longitud,es_cable_conexion_interna)
  VALUES (1,'C-001',10,1,1,'m',0),(2,'C-002',5,1,1,'m',NULL),(3,'INT-1',0.5,1,1,'m',1);
INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna)
  VALUES (1,1,1,0),(2,1,2,0),(3,2,3,0),(4,3,2,1);
INSERT INTO sala(id_sala,nombre) VALUES (1,'Control Central');
INSERT INTO rack(id_rack,numero,nombre,cantidad_maxima) VALUES (1,1,'Rack 1',42);
INSERT INTO rack_por_sala(id_rack,id_sala) VALUES (1,1);
INSERT INTO frame(id_frame,nombre,num_inventario,id_marca,modelo) VALUES (1,'Frame 1',500,2,'Studio');
INSERT INTO slot(id_slot,nombre,id_equipo,id_frame,rectangulo_x_en_imagen,rectangulo_y_en_imagen,rectangulo_ancho_pixeles,rectangulo_alto_pixeles)
  VALUES (1,'Slot 1',3,1,0,0,100,20),(2,'Slot 2',NULL,1,0,20,100,20);
INSERT INTO posicion_en_rack(id_posicion_en_rack,id_rack,id_equipo,orificio_posicion_equipo_en_rack,unidades_de_rack_equipo,id_frame)
  VALUES (1,1,2,3,1,NULL),(2,1,NULL,10,4,1);
"""
c = sqlite3.connect(m.DB_PATH)
c.executescript(SQL)
c.commit()
c.close()

import bridge  # noqa: E402


def ll(fn, **kw):
    r = json.loads(bridge.call(fn, json.dumps(kw)))
    assert r["ok"], f"{fn}{kw}: {r.get('error')}"
    return r["data"]


fallos = []


def check(cond, msg):
    print(("  ok  " if cond else "  FALLA ") + msg)
    if not cond:
        fallos.append(msg)


r = ll("resumen")
check(r["equipo"] == 4 and r["conector"] == 4 and r["cable"] == 3 and r["conexion"] == 4, "resumen cuenta filas")
check(r["cables_externos"] == 2, "resumen: cable con es_cable_conexion_interna NULL cuenta como externo")

cat = ll("catalogos")
check(len(cat["marcas"]) == 2 and cat["imagenes"][0]["mm_por_pixel"] == 0.25, "catalogos")

eqs = ll("equipos_lista")
check([e["nombre"] for e in eqs] == ["CAM 1", "CAM 2", "MATRIZ A"], "equipos_lista oculta 'SIN EQUIPO' y ordena")
check(len(ll("equipos_lista", incluir_sistema=True)) == 4, "equipos_lista(incluir_sistema=True)")
check(eqs[0]["n_conectores"] == 1 and eqs[0]["marca"] == "Sony", "equipos_lista: marca y n_conectores")

f = ll("equipo_ficha", id_equipo=2)
check(f["nombre"] == "MATRIZ A" and f["tipo"] == "MATRIZ" and f["marca"] == "Blackmagic", "equipo_ficha: datos")
check(len(f["conectores"]) == 2, "equipo_ficha: conectores")
in1 = next(x for x in f["conectores"] if x["nombre"] == "IN 1")
check(len(in1["conexiones"]) == 2, "equipo_ficha: IN 1 tiene la conexión externa y la interna")
ext = next(x for x in in1["conexiones"] if x["cable"] == "C-001")
check(ext["otros"] and ext["otros"][0]["equipo"] == "CAM 1", "equipo_ficha: extremo opuesto del cable = CAM 1")
check(f["racks"] and f["racks"][0]["orificio"] == 3 and f["racks"][0]["sala"] == "Control Central", "equipo_ficha: rack y sala")
check(f["problemas"] == [] and f["riesgo"] is None and in1["senal"] is None, "equipo_ficha: opcionales vacíos")
f3 = ll("equipo_ficha", id_equipo=3)
check(f3["slots"] and f3["slots"][0]["frame"] == "Frame 1", "equipo_ficha: slot/frame")
f1 = ll("equipo_ficha", id_equipo=1)
check(f1["imagen_path"] == "cam.png" and f1["conectores"][0]["x"] == 40, "equipo_ficha: imagen y coordenadas de conector")

cf = ll("conector_ficha", id_conector=1)
check(cf["equipo"] == "CAM 1" and cf["conexiones"][0]["otros"][0]["conector"] == "IN 1", "conector_ficha")
check(cf["ruteo_entrada"] is None and cf["senal"] is None, "conector_ficha: sin ruteo ni señal")

cab = ll("cables_lista")
check([k["codigo"] for k in cab] == ["C-001", "C-002"], "cables_lista excluye internos")
check(len(ll("cables_lista", incluir_internos=True)) == 3, "cables_lista(incluir_internos=True)")
kf = ll("cable_ficha", id_cable=1)
check(len(kf["extremos"]) == 2 and {e["equipo"] for e in kf["extremos"]} == {"CAM 1", "MATRIZ A"}, "cable_ficha: extremos")

cx = ll("conexiones_lista")
check(len(cx) == 3, "conexiones_lista excluye internas")
check(len(ll("conexiones_lista", solo_externas=False)) == 4, "conexiones_lista(solo_externas=False)")
check(len(ll("conexiones_lista", id_equipo=2)) == 2 and len(ll("conexiones_lista", id_cable=1)) == 2, "conexiones_lista: filtros")

check(ll("salas_lista")[0]["n_racks"] == 1, "salas_lista")
check(ll("sala_ficha", id_sala=1)["racks"][0]["n_posiciones"] == 2, "sala_ficha")
check(ll("racks_lista")[0]["sala"] == "Control Central", "racks_lista")
rk = ll("rack_ficha", id_rack=1)
check([(p["orificio"], p["tipo"], p["dispositivo"]) for p in rk["posiciones"]] ==
      [(3, "EQUIPO", "MATRIZ A"), (10, "FRAME", "Frame 1")], "rack_ficha: posiciones ordenadas, equipo y frame")
check(ll("frames_lista")[0]["n_slots"] == 2, "frames_lista")
check(len(ll("slots_lista")) == 2 and len(ll("slots_lista", id_frame=1)) == 2, "slots_lista")
fr = ll("frame_ficha", id_frame=1)
check(fr["slots"][0]["equipo"] == "CAM 2" and fr["racks"][0]["orificio"] == 10, "frame_ficha")

# Errores: siempre JSON, nunca excepción hacia JS
e = json.loads(bridge.call("equipo_ficha", json.dumps({"id_equipo": 999})))
check(e["ok"] is False and "999" in e["error"], "id inexistente -> error JSON")
e = json.loads(bridge.call("no_existe", "{}"))
check(e["ok"] is False and "desconocida" in e["error"], "función desconocida -> error JSON")
e = json.loads(bridge.call("resumen", "{no es json"))
check(e["ok"] is False, "args inválidos -> error JSON")

# Base vieja sin tablas opcionales: debe degradar a vacío
c = sqlite3.connect(m.DB_PATH)
c.executescript("DROP TABLE riesgo_equipo_cache; DROP TABLE problema_equipo; DROP TABLE senal_en_conector;")
c.commit(); c.close()
f = ll("equipo_ficha", id_equipo=2)
check(f["problemas"] == [] and f["riesgo"] is None, "tablas opcionales ausentes -> vacío, sin error")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(fallos)} fallas" if fallos else "\nTODO OK")
sys.exit(1 if fallos else 0)
