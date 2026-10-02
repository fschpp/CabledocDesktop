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

# ── arbol_equipos (A.3) ──
c = sqlite3.connect(m.DB_PATH)
c.executescript("INSERT INTO equipo(id_equipo,id_tipo_equipo,id_marca,nombre) VALUES (5,1,2,'MONITOR');"
                "INSERT INTO equiponoraqueable_por_sala(id_sala,id_equipo) VALUES (1,5),(1,3);")  # el 3 ya está en un slot: no debe repetirse
c.commit(); c.close()
ar = ll("arbol_equipos")
check(ar["n_equipos"] == 5, "arbol_equipos: n_equipos excluye el id 0")
sala, sinub = ar["nodos"]
check(sala["t"] == "sala" and sala["l"] == "Control Central" and sinub["t"] == "sin_ubicacion" and sinub["n"] == 2, "arbol: sala + grupo sin ubicación al final")
rack, sueltos = sala["h"]
check(rack["t"] == "rack" and rack["l"] == "Rack 1" and sueltos["t"] == "sueltos" and sueltos["n"] == 1
      and [x["l"] for x in sueltos["h"]] == ["MONITOR Blackmagic CAMARA"], "arbol: rack y equipos sueltos (sin los ya ubicados)")
frame, matriz = rack["h"]
check(frame["t"] == "frame" and frame["l"] == "Frame 1" and [x["l"] for x in frame["h"]] == ["CAM 2 Sony CAMARA HDC-3500 102 S3"],
      "arbol: frame con el equipo de su slot y etiqueta nombre+marca+tipo+modelo+inventario+serie")
check(matriz["t"] == "equipo" and matriz["b"] == "MATRIZ" and [x["l"] for x in matriz["h"]] == ["IN 1", "OUT 1"]
      and matriz["h"][0]["b"] == "BNC" and matriz["h"][0]["t"] == "conector", "arbol: equipo directo en rack con sus conectores y su tipo")
check([x["l"].split()[0] for x in sinub["h"]] == ["CAM", "SIN"] and "h" not in sinub["h"][1], "arbol: sin ubicación ordenado por nombre; sin conectores no hay 'h'")
ids = []
def _rec(n):
    if n["t"] == "equipo": ids.append(n["i"])
    for x in n.get("h", []): _rec(x)
for n in ar["nodos"]: _rec(n)
check(sorted(ids) == [1, 2, 3, 4, 5], "arbol: cada equipo aparece exactamente una vez")

# ── conexiones_equipo y cadena_extension (A.5) ──
m.Modelo.asegurar_tablas_extension_cable()
c = sqlite3.connect(m.DB_PATH)
c.executescript("""
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector) VALUES (5,'IN 2',2,1);
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES (0,2,'EMPALME BNC 1');
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector) VALUES (6,'X',0,1);
INSERT INTO cable(id_cable,codigo) VALUES (4,'EXT-A'),(5,'EXT-B'),(6,'SUELTO'),(7,'CICLO'),(8,'C-008'),(9,'VACIO');
INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna) VALUES
  (5,4,4,0),(6,4,NULL,0),(7,5,NULL,0),(8,5,5,0),
  (9,6,1,0),(10,6,NULL,0),(11,7,NULL,0),(12,7,NULL,0),(13,8,1,0),(14,8,6,0);
INSERT INTO extension_cable(id_extension,id_conexion_a,id_conexion_b,posicion_libre,es_armado_correcto)
  VALUES (1,6,7,'Rack 1 U3',0),(2,11,12,NULL,NULL);
""")
c.commit(); c.close()

ce = ll("conexiones_equipo", id_equipo=1)
check(ce["equipo"] == "CAM 1" and [k["codigo"] for k in ce["cables"]] == ["C-001", "C-008"], "conexiones_equipo: cables del equipo (sin extremos sueltos)")
d1 = ce["cables"][0]["conexiones"]
check(len(d1) == 1 and d1[0]["id_equipo_destino"] == 2 and d1[0]["equipo_destino"] == "MATRIZ A INV101"
      and d1[0]["id_conector_destino"] == 2 and d1[0]["id_conector_local"] == 1, "conexiones_equipo: destino con ids")
check(ce["cables"][1]["conexiones"][0]["id_equipo_destino"] is None, "conexiones_equipo: destino con id 0 -> None (hoja)")
cv = ll("conexiones_equipo", id_equipo=5)
check(cv["cables"] == [] and cv["n_conexiones"] == 0, "conexiones_equipo: equipo sin conexiones")
e = json.loads(bridge.call("conexiones_equipo", json.dumps({"id_equipo": 999})))
check(e["ok"] is False and "999" in e["error"], "conexiones_equipo: id inexistente -> error JSON")
# mismas filas que el desktop (Modelo.devolver_equipos_conectados_a_equipo)
nativo = m.Modelo.devolver_equipos_conectados_a_equipo(1)
check(ce["n_conexiones"] == len(nativo) == 2, "conexiones_equipo: misma cantidad de filas que Modelo")

def _sin_ids(l):
    return [{k: v for k, v in x.items() if k not in ("id_equipo", "id_conector")} for x in l]

for cable in (4, 5, 6, 7, 1, 9):
    web, nat = ll("cadena_extension", id_cable=cable), m.Modelo.resolver_cadena_extension(cable)
    check(_sin_ids(web) == nat, f"cadena_extension({cable}) idéntica a Modelo.resolver_cadena_extension")
ch = ll("cadena_extension", id_cable=4)
check([x["tipo"] for x in ch] == ["equipo", "cable", "extension", "cable", "equipo"], "cadena: equipo-cable-extensión-cable-equipo")
check(ch[1]["foco"] is True and ch[3]["foco"] is False and ch[2]["armado"] == 0 and ch[2]["posicion"] == "Rack 1 U3", "cadena: foco, armado y posición")
check(ch[0]["id_equipo"] == 3 and ch[4]["id_conector"] == 5, "cadena: ids de los extremos reales (para enlazar)")
ch5 = ll("cadena_extension", id_cable=5)
check([x["tipo"] for x in ch5] == ["equipo", "cable", "extension", "cable", "equipo"] and ch5[3]["foco"] and not ch5[1]["foco"] and ch5[0]["id_equipo"] == 3 and ch5[4]["id_equipo"] == 2,
      "cadena: desde el otro cable (mismo recorrido, foco en el cable de partida)")
check([x["tipo"] for x in ll("cadena_extension", id_cable=6)] == ["equipo", "cable", "suelto"], "cadena: punta suelta")
check("ciclo" in [x["tipo"] for x in ll("cadena_extension", id_cable=7)], "cadena: referencia circular detectada")
check(ll("cadena_extension", id_cable=9) == [], "cadena: cable sin conexiones -> []")
cc = sqlite3.connect(m.DB_PATH); cc.executescript("DROP TABLE extension_cable;"); cc.commit(); cc.close()
check([x["tipo"] for x in ll("cadena_extension", id_cable=4)] == ["equipo", "cable", "suelto"], "cadena: sin tabla extension_cable -> solo el cable, sin error")


# ── Ubicaciones: rack_vista, frame_vista, patcheras_global (A.6) ──
m.Modelo.asegurar_columnas_control_idioma()          # funcion_patchera (1 BACK_ENTRADA, 2 BACK_SALIDA, 3 FRONT_DERIVACION, 4 FRONT_INSERCION) + conector.id_funcion_patchera
c = sqlite3.connect(m.DB_PATH)
c.executescript("""
INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (10,'MODULO PATCHERA','PATCHERA'),(11,'FANTASMA','FANTASMA');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre,num_inventario) VALUES
  (100,1,'RX A',1000),(101,1,'RX B',NULL),(102,1,'RX C',NULL),(103,1,'RX LEJOS',NULL),(104,1,'MON',NULL),
  (110,10,'PATCH 1',NULL),(111,10,'PATCH 2',NULL),(112,10,'PATCH 3',NULL),(113,10,'PATCH SIN NUMERO',NULL),(120,11,'FANT',NULL);
INSERT INTO rack(id_rack,numero,nombre,cantidad_maxima) VALUES (2,2,'Rack 2',4),(3,3,'Rack 3',NULL);
INSERT INTO rack_por_sala(id_rack,id_sala) VALUES (2,1);
INSERT INTO frame(id_frame,nombre) VALUES (2,'PPV 1'),(3,'PPV 2');
INSERT INTO posicion_en_rack(id_posicion_en_rack,id_rack,id_equipo,orificio_posicion_equipo_en_rack,unidades_de_rack_equipo,id_frame) VALUES
  (10,2,100,1,1,NULL),(11,2,101,1,1,NULL),(12,2,102,4,1,NULL),(13,2,103,20,1,NULL),(14,2,NULL,7,1,2),(15,3,NULL,1,1,3);
INSERT INTO slot(id_slot,nombre,id_equipo,id_frame) VALUES
  (10,'Slot 1',110,2),(11,'Slot 2',111,2),(12,'Slot 1',112,3),(13,'Sin numero',113,3);
INSERT INTO conector(id_conector,nombre,id_equipo,id_tipo_conector,id_funcion_patchera) VALUES
  (200,'A_BACK',110,1,1),(201,'B_BACK',110,1,2),(202,'A_FRONT',110,1,3),(203,'B_FRONT',110,1,4),
  (210,'A_BACK',111,1,1),(211,'B_BACK',111,1,2),(212,'A_FRONT',111,1,3),(213,'B_FRONT',111,1,4),
  (220,'A_BACK',112,1,1),(221,'B_BACK',112,1,2),(222,'A_FRONT',112,1,3),(223,'B_FRONT',112,1,4),
  (230,'SIN',120,1,NULL),(240,'IN',104,1,NULL);
INSERT INTO cable(id_cable,codigo,es_cable_conexion_interna) VALUES (100,'P-100',0),(101,'P-101',0),(102,'P-102',0),(103,'P-103',0),(104,'P-104',0),(105,'P-105',0);
INSERT INTO conexion(id_conexion,id_cable,id_conector,es_conexion_interna) VALUES
  (100,100,1,0),(101,100,200,0),          -- CAM 1 -> PATCH 1 A_BACK
  (102,101,4,0),(103,101,201,0),          -- CAM 2 -> PATCH 1 B_BACK
  (104,102,230,0),(105,102,210,0),        -- FANT -> PATCH 2 A_BACK
  (106,103,202,0),(107,103,213,0),        -- jumper PATCH 1 A_FRONT <-> PATCH 2 B_FRONT (mismo rack)
  (108,104,212,0),(109,104,222,0),        -- jumper PATCH 2 A_FRONT <-> PATCH 3 A_FRONT (otro rack)
  (110,105,203,0),(111,105,240,0);        -- PATCH 1 B_FRONT -> MON (equipo final)
""")
c.commit(); c.close()

ub = ll("ubicaciones")
check([s["nombre"] for s in ub["salas"]] == ["Control Central"] and [r["nombre"] for r in ub["salas"][0]["racks"]] == ["Rack 1", "Rack 2"], "ubicaciones: sala con sus racks")
check([r["nombre"] for r in ub["racks_sin_sala"]] == ["Rack 3"], "ubicaciones: racks sin sala")
check({f["nombre"]: [x["rack"] for x in f["racks"]] for f in ub["frames"]} == {"Frame 1": ["Rack 1"], "PPV 1": ["Rack 2"], "PPV 2": ["Rack 3"]}, "ubicaciones: frames con su rack")

rv = ll("rack_vista", id_rack=1)
check(rv["cap_u"] == 42 and rv["cap"] == 126 and sum(s["u_count"] for s in rv["segmentos"]) == 126, "rack_vista: 42 U = 126 orificios, sin huecos ni solapes")
sg = [(s["u_ini"], s["u_count"], s["tipo"]) for s in rv["segmentos"] if s["tipo"] != "libre"]
check(sg == [(3, 3, "equipo"), (10, 12, "frame")], "rack_vista: equipo de 1 U = 3 orificios y frame de 4 U = 12")
eq = next(s for s in rv["segmentos"] if s["tipo"] == "equipo")
check(eq["nombre"] == "MATRIZ A" and eq["id"] == 2 and eq["inv"] == "101", "rack_vista: nombre, id e inventario del equipo")
check(next(s for s in rv["segmentos"] if s["tipo"] == "frame")["inv"] == "500", "rack_vista: inventario del frame")
check(rv["resumen"] == {"asignaciones": 2, "equipos": 1, "frames": 1, "bandejas": 0, "libres": 126 - 15} and rv["salas"][0]["nombre"] == "Control Central", "rack_vista: resumen y sala")

rv2 = ll("rack_vista", id_rack=2)
ban = [s for s in rv2["segmentos"] if s["tipo"] == "bandeja"]
check(len(ban) == 1 and (ban[0]["u_ini"], ban[0]["u_count"]) == (1, 3) and ban[0]["nombre"] == ["RX A", "RX B"]
      and [i["id"] for i in ban[0]["items"]] == [100, 101], "rack_vista: dos equipos en los mismos orificios = una bandeja con sus items")
check(rv2["cap_u"] == 4 and rv2["cap"] == 12 and [(s["u_ini"], s["tipo"]) for s in rv2["segmentos"] if s["tipo"] != "libre"] == [(1, "bandeja"), (4, "equipo"), (7, "frame")],
      "rack_vista: rack de 4 U; bandeja, equipo y frame en orden")
check(rv2["fuera_de_rango"] == ["RX LEJOS"] and rv2["resumen"]["bandejas"] == 1, "rack_vista: el equipo más allá del último orificio se informa")
rv3 = ll("rack_vista", id_rack=3)
check(rv3["cap_u"] == 42 and rv3["segmentos"][0]["tipo"] == "frame" and rv3["resumen"]["frames"] == 1, "rack_vista: cantidad_maxima NULL -> 42 U (como el desktop)")
for rk in (1, 2, 3):                                  # mismas filas que el desktop ('RACKS CON EQUIPOS' vía Modelo)
    devs = [{"id": d[0], "orificio": d[2], "inventario": d[3], "dispositivo": d[4], "ur": d[5], "id_equipo": d[7], "id_frame": d[8]}
            for d in m.Modelo.devolver_dispositivos_de_un_rack(rk)]
    cap = ll("rack_vista", id_rack=rk)["cap"]
    check(bridge._segmentos_rack(devs, cap) == ll("rack_vista", id_rack=rk)["segmentos"], f"rack_vista({rk}): segmentos idénticos a los de las filas de Modelo")
e = json.loads(bridge.call("rack_vista", json.dumps({"id_rack": 999})))
check(e["ok"] is False and "999" in e["error"], "rack_vista: id inexistente -> error JSON")

fv = ll("frame_vista", id_frame=1)
check(fv["nombre"] == "Frame 1" and fv["marca"] == "Blackmagic" and fv["racks"][0]["rack"] == "Rack 1" and fv["imagen_path"] is None, "frame_vista: datos, rack y sin imagen")
check([(s["num"], s["nombre"], s["equipo"], s["x"], s["y"], s["ancho"], s["alto"], s["color"]) for s in fv["slots"]]
      == [(1, "Slot 1", "CAM 2", 0, 0, 100, 20, 0), (2, "Slot 2", "", 0, 20, 100, 20, None)], "frame_vista: slots numerados; el vacío sin color")
c = sqlite3.connect(m.DB_PATH)
c.executescript("""INSERT INTO imagen(id_imagen,path_archivo) VALUES (50,'slot.png'),(51,'frame.png');
  INSERT INTO slot(id_slot,nombre,id_equipo,id_frame,id_imagen) VALUES (90,'Slot 3',NULL,3,50),(91,'Slot 4',102,3,NULL);""")
c.commit(); c.close()
fv3 = ll("frame_vista", id_frame=3)
check(fv3["imagen_path"] == "slot.png" and [(s["ancho"], s["alto"]) for s in fv3["slots"] if s["nombre"] == "Slot 4"] == [(50, 30)], "frame_vista: sin imagen de frame usa la del primer slot; rectángulo sin medida = 50×30")
c = sqlite3.connect(m.DB_PATH); c.execute("UPDATE frame SET id_imagen=51 WHERE id_frame=3"); c.commit(); c.close()
check(ll("frame_vista", id_frame=3)["imagen_path"] == "frame.png", "frame_vista: la imagen del frame tiene prioridad")
check([(x["nombre"], x["color"]) for x in ll("frame_vista", id_frame=3)["slots"]] == [("Sin numero", 0), ("Slot 1", 1), ("Slot 3", None), ("Slot 4", 2)],
      "frame_vista: orden por nombre de slot; colores por orden de aparición solo a los slots con equipo")
nat = m.Modelo.devolver_slots_graficos_de_frame(1)
check([(r[1], r[2], r[4], r[5], r[6], r[7]) for r in nat] == [(s["nombre"], s["id_equipo"], s["x"], s["y"], s["ancho"], s["alto"]) for s in fv["slots"]], "frame_vista: mismos slots que Modelo.devolver_slots_graficos_de_frame")
e = json.loads(bridge.call("frame_vista", json.dumps({"id_frame": 999})))
check(e["ok"] is False and "999" in e["error"], "frame_vista: id inexistente -> error JSON")

pg = ll("patcheras_global")
check([r["rack"] for r in pg["racks"]] == ["Rack 2", "Rack 3"] and [f["frame"] for f in pg["racks"][0]["frames"]] == ["PPV 1"], "patcheras: racks y frames con módulos de patchera")
cols = pg["racks"][0]["frames"][0]["columnas"]
check([(c_["col"], c_["modulo"]) for c_ in cols] == [(1, "PATCH 1"), (2, "PATCH 2")] and pg["max_col"] == 2, "patcheras: columnas por el número del slot (el slot sin número se ignora)")
c1, c2 = cols
check(c1["A"]["estado"] == "conectado" and c1["A"]["nombre"] == "CAM 1" and c1["A"]["conector"] == "OUT 1" and c1["B"]["nombre"] == "CAM 2"
      and c1["A"]["color"] != c1["B"]["color"], "patcheras: BACK_ENTRADA = fila A y BACK_SALIDA = fila B, un color por equipo")
check(c2["A"]["estado"] == "fantasma" and c2["A"]["color"] is None and c2["B"]["estado"] == "vacio", "patcheras: extremo FANTASMA y fila vacía")
check(c1["front"]["B"]["estado"] == "conectado" and c1["front"]["B"]["nombre"] == "MON" and not c1["front"]["B"]["es_jumper"], "patcheras: frente a un equipo final (no es jumper)")
check(c1["front"]["A"]["es_jumper"] and c1["front"]["A"]["destino"] == {"id_rack": 2, "id_frame": 2, "col": 2, "row": "B"}, "patcheras: frente a otra patchera = jumper con su destino")
curvas = [j for j in pg["jumpers"] if j["tipo"] == "curva"]
cruzan = [j for j in pg["jumpers"] if j["cruza_rack"]]
check(len(curvas) == 1 and len(cruzan) == 1 and cruzan[0]["tipo"] == "cabo" and cruzan[0]["p2"]["id_rack"] == 3, "patcheras: un patchcord por par (curva en el mismo rack, cabo si cruza de rack)")
check(len(pg["jumpers"]) == 3 and sum(1 for j in pg["jumpers"] if j["p2"] is None) == 1, "patcheras: 3 patchcords (curva, cruce y el cabo a MON)")
check(pg["resumen"] == {"racks": 2, "patcheras": 2, "equipos": 6, "fantasma": 1}, "patcheras: resumen (equipos con color: los de atrás, los del frente y los módulos de los jumpers, como el desktop) " + str(pg["resumen"]))
c = sqlite3.connect(m.DB_PATH); c.executescript("DROP TABLE funcion_patchera;"); c.commit(); c.close()
check(ll("patcheras_global")["racks"] and all(x["A"]["estado"] == "vacio" for r in ll("patcheras_global")["racks"] for f in r["frames"] for x in f["columnas"]),
      "patcheras: sin tabla funcion_patchera -> módulos sin conexiones, sin error")

# Errores: siempre JSON, nunca excepción hacia JS
e = json.loads(bridge.call("equipo_ficha", json.dumps({"id_equipo": 999})))
check(e["ok"] is False and "999" in e["error"], "id inexistente -> error JSON")
e = json.loads(bridge.call("no_existe", "{}"))
check(e["ok"] is False and "desconocida" in e["error"], "función desconocida -> error JSON")
e = json.loads(bridge.call("resumen", "{no es json"))
check(e["ok"] is False, "args inválidos -> error JSON")

e = json.loads(bridge.call("equipos_lista", json.dumps({"id_equipo": 180})))
check(e["ok"] is False and "no acepta ['id_equipo']" in e["error"] and "incluir_sistema (opcional)" in e["error"],
      "argumento que sobra -> error que lista los válidos")
e = json.loads(bridge.call("equipo_ficha", "{}"))
check(e["ok"] is False and "falta ['id_equipo']" in e["error"], "argumento obligatorio ausente -> error claro")
e = json.loads(bridge.call("resumen", "[1]"))
check(e["ok"] is False and "objeto JSON" in e["error"], "args que no son objeto -> error claro")
fm = ll("firmas")
check(fm["equipo_ficha"] == [{"nombre": "id_equipo", "requerido": True, "defecto": None}]
      and fm["equipos_lista"][0]["defecto"] is False and fm["resumen"] == [], "firmas")

# Base vieja sin tablas opcionales: debe degradar a vacío
c = sqlite3.connect(m.DB_PATH)
c.executescript("DROP TABLE riesgo_equipo_cache; DROP TABLE problema_equipo; DROP TABLE senal_en_conector;")
c.commit(); c.close()
f = ll("equipo_ficha", id_equipo=2)
check(f["problemas"] == [] and f["riesgo"] is None, "tablas opcionales ausentes -> vacío, sin error")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(fallos)} fallas" if fallos else "\nTODO OK")
sys.exit(1 if fallos else 0)
