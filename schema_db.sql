BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "cable" (
  "id_cable"   INTEGER,
  "codigo"     TEXT UNIQUE,
  "longitud"   REAL,
  "id_tipo_cable"  INTEGER,
  "id_tipo_ficha"  INTEGER,
  "unidad_longitud" TEXT,
  "metraje_impreso_primer_extremo"  INTEGER,
  "metraje_impreso_segundo_extremo" INTEGER,
  "unidad_metraje_impreso" TEXT,
  "es_cable_conexion_interna" INTEGER,
  "fecha_ultima_edicion" TEXT,
  "estado"     TEXT DEFAULT 'VERIFICADO',
  "notas_relevamiento" TEXT,
  "id_cable_fusionado" INTEGER, ultima_auditoria_fecha TEXT,
  "ancho_banda_mhz_override" REAL,
  PRIMARY KEY("id_cable" AUTOINCREMENT),
  FOREIGN KEY("id_tipo_cable") REFERENCES "tipo_cable"("id_tipo_cable") ON DELETE SET NULL,
  FOREIGN KEY("id_tipo_ficha") REFERENCES "tipo_ficha"("id_tipo_ficha") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS categoria_problema (  id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,  nombre       TEXT,  fecha_ultima_edicion TEXT);
CREATE TABLE IF NOT EXISTS "conector" (
  "id_conector"  INTEGER,
  "nombre"       TEXT,
  "id_equipo"    INTEGER,
  "id_tipo_conector" INTEGER,
  "id_imagen"    INTEGER,
  "coordenada_x_en_imagen" INTEGER,
  "coordenada_y_en_imagen" INTEGER,
  "fecha_ultima_edicion" TEXT, ultima_auditoria_fecha TEXT,
  "id_tipo_ficha" INTEGER,
  "modo_balance" TEXT CHECK("modo_balance" IN ('BALANCEADO','DESBALANCEADO','NA')),
  "modo_canal"   TEXT CHECK("modo_canal"   IN ('MONO','ESTEREO','NA')),
  PRIMARY KEY("id_conector" AUTOINCREMENT),
  FOREIGN KEY("id_equipo")        REFERENCES "equipo"("id_equipo")               ON DELETE CASCADE,
  FOREIGN KEY("id_tipo_conector") REFERENCES "tipo_conector"("id_tipo_conector")  ON DELETE SET NULL,
  FOREIGN KEY("id_imagen")        REFERENCES "imagen"("id_imagen")                ON DELETE SET NULL,
  FOREIGN KEY("id_tipo_ficha")    REFERENCES "tipo_ficha"("id_tipo_ficha")        ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS conector_catalogo (  id_conector_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,  id_equipo_catalogo INTEGER NOT NULL,  nombre             TEXT,  id_tipo_conector   INTEGER,  id_imagen          INTEGER,  coordenada_x_en_imagen INTEGER,  coordenada_y_en_imagen INTEGER,  fecha_ultima_edicion TEXT,  FOREIGN KEY(id_equipo_catalogo) REFERENCES equipo_catalogo(id_equipo_catalogo) ON DELETE CASCADE,  FOREIGN KEY(id_tipo_conector)   REFERENCES tipo_conector(id_tipo_conector)     ON DELETE SET NULL,  FOREIGN KEY(id_imagen)          REFERENCES imagen(id_imagen)                   ON DELETE SET NULL);
-- id_conector es NULLABLE a propósito (ver plan_desarrollo_extension_
-- cable.md §3.1): una fila con id_conector IS NULL es un "extremo
-- suelto" — la punta de un cable que no llega a un equipo sino que se
-- empalma directamente con la ficha de otro cable (tabla extension_
-- cable, más abajo). No requirió ALTER: ya nace nullable en este schema.
CREATE TABLE IF NOT EXISTS "conexion" (
  "id_conexion" INTEGER,
  "id_cable"    INTEGER,
  "id_conector" INTEGER,
  "es_conexion_interna" INTEGER,
  "fecha_ultima_edicion" TEXT, ultima_auditoria_fecha TEXT,
  "id_tipo_ficha" INTEGER,
  "es_armado_correcto" INTEGER,
  "detalle_armado" TEXT,
  PRIMARY KEY("id_conexion" AUTOINCREMENT),
  FOREIGN KEY("id_cable")    REFERENCES "cable"("id_cable")       ON DELETE CASCADE,
  FOREIGN KEY("id_conector") REFERENCES "conector"("id_conector") ON DELETE CASCADE,
  FOREIGN KEY("id_tipo_ficha") REFERENCES "tipo_ficha"("id_tipo_ficha") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "diagrama_equipos_posicion_en_imagen" (
  "id_diagrama_posicion" INTEGER UNIQUE,
  "id_equipo"    INTEGER,
  "x"            INTEGER,
  "y"            INTEGER,
  "fecha_ultima_edicion" TEXT,
  "color_equipo"   TEXT,
  "id_conexion"    INTEGER,
  "color_conexion" TEXT,
  PRIMARY KEY("id_diagrama_posicion" AUTOINCREMENT),
  FOREIGN KEY("id_equipo") REFERENCES "equipo"("id_equipo") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "equipo" (
  "id_equipo"       INTEGER,
  "id_tipo_equipo"  INTEGER,
  "id_marca"        INTEGER,
  "num_inventario"  INTEGER,
  "num_serie"       TEXT,
  "modelo"          TEXT,
  "nombre"          TEXT,
  "id_imagen"       INTEGER,
  "fecha_ultima_edicion" TEXT,
  "coordenada_x_en_imagen" INTEGER,
  "coordenada_y_en_imagen" INTEGER, path_manual TEXT, configuraciones TEXT, ultima_auditoria_fecha TEXT, picon TEXT, fecha_fabricacion TEXT, es_equipo_usado INTEGER DEFAULT 0,
  "senal_requerida_mhz" REAL,
  PRIMARY KEY("id_equipo" AUTOINCREMENT),
  FOREIGN KEY("id_tipo_equipo") REFERENCES "tipo_equipo"("id_tipo_equipo") ON DELETE SET NULL,
  FOREIGN KEY("id_marca")       REFERENCES "marca"("id_marca")             ON DELETE SET NULL,
  FOREIGN KEY("id_imagen")      REFERENCES "imagen"("id_imagen")           ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS equipo_catalogo (  id_equipo_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,  nombre_molde    TEXT,  id_tipo_equipo  INTEGER,  id_marca        INTEGER,  modelo          TEXT,  id_imagen       INTEGER,  path_manual     TEXT,  configuraciones TEXT,  fecha_ultima_edicion TEXT, picon TEXT,  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE SET NULL,  FOREIGN KEY(id_marca)       REFERENCES marca(id_marca)             ON DELETE SET NULL,  FOREIGN KEY(id_imagen)      REFERENCES imagen(id_imagen)           ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS equiponoraqueable_por_sala (
  id_equiponoraqueable_por_sala INTEGER PRIMARY KEY AUTOINCREMENT,
  id_sala   INTEGER NOT NULL,
  id_equipo INTEGER NOT NULL,
  fecha_ultima_edicion TEXT,
  FOREIGN KEY(id_sala)   REFERENCES sala(id_sala)     ON DELETE CASCADE,
  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "frame" (
  "id_frame"       INTEGER,
  "nombre"         TEXT,
  "num_inventario" INTEGER,
  "id_marca"       INTEGER,
  "id_imagen"      INTEGER,
  "modelo"         TEXT,
  "fecha_ultima_edicion" TEXT, ultima_auditoria_fecha TEXT,
  PRIMARY KEY("id_frame" AUTOINCREMENT),
  FOREIGN KEY("id_marca")  REFERENCES "marca"("id_marca")   ON DELETE SET NULL,
  FOREIGN KEY("id_imagen") REFERENCES "imagen"("id_imagen") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS frame_catalogo (  id_frame_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,  nombre_molde TEXT,  id_marca     INTEGER,  modelo       TEXT,  id_imagen    INTEGER,  path_manual  TEXT,  configuraciones TEXT,  fecha_ultima_edicion TEXT, picon TEXT,  FOREIGN KEY(id_marca)  REFERENCES marca(id_marca)   ON DELETE SET NULL,  FOREIGN KEY(id_imagen) REFERENCES imagen(id_imagen) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS "imagen" (
	"id_imagen"	INTEGER,
	"path_archivo"	INTEGER NOT NULL,
	"descripcion"	TEXT,
	"fecha_ultima_Edicion"	TEXT,
	PRIMARY KEY("id_imagen" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "marca" (
	"id_marca"	INTEGER,
	"nombre"	TEXT,
	"fecha_ultima_edicion"	TEXT,
	PRIMARY KEY("id_marca" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS matriz_ruteo (  id_conector_salida  INTEGER PRIMARY KEY,  id_conector_entrada INTEGER,  fecha_ultima_edicion TEXT,  FOREIGN KEY(id_conector_salida)  REFERENCES conector(id_conector) ON DELETE CASCADE,  FOREIGN KEY(id_conector_entrada) REFERENCES conector(id_conector) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS parametro_riesgo (  clave TEXT PRIMARY KEY,  valor REAL);
CREATE TABLE IF NOT EXISTS "plantilla_conector" (
  "id"             INTEGER PRIMARY KEY AUTOINCREMENT,
  "id_tipo_equipo"   INTEGER NOT NULL,
  "id_tipo_conector" INTEGER NOT NULL,
  "direccion"      TEXT NOT NULL DEFAULT 'INOUT',
  "cantidad"       INTEGER NOT NULL DEFAULT 1,
  "fecha_ultima_edicion" TEXT,
  FOREIGN KEY("id_tipo_equipo")   REFERENCES "tipo_equipo"("id_tipo_equipo")     ON DELETE CASCADE,
  FOREIGN KEY("id_tipo_conector") REFERENCES "tipo_conector"("id_tipo_conector") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "posicion_en_rack" (
  "id_posicion_en_rack" INTEGER,
  "id_rack"   INTEGER,
  "id_equipo" INTEGER,
  "orificio_posicion_equipo_en_rack" INTEGER,
  "unidades_de_rack_equipo" INTEGER,
  "id_frame"  INTEGER,
  "fecha_ultima_edicion" TEXT,
  PRIMARY KEY("id_posicion_en_rack" AUTOINCREMENT),
  FOREIGN KEY("id_rack")   REFERENCES "rack"("id_rack")     ON DELETE CASCADE,
  FOREIGN KEY("id_equipo") REFERENCES "equipo"("id_equipo") ON DELETE SET NULL,
  FOREIGN KEY("id_frame")  REFERENCES "frame"("id_frame")   ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS problema_equipo (  id_problema  INTEGER PRIMARY KEY AUTOINCREMENT,  id_categoria INTEGER,  id_equipo    INTEGER NOT NULL,  gravedad     INTEGER NOT NULL,  descripcion  TEXT,  fecha_ultima_edicion TEXT, fecha TEXT, afecta_categoria_equipo INTEGER DEFAULT 0, resuelto INTEGER DEFAULT 0, fecha_resolucion TEXT,  FOREIGN KEY(id_categoria) REFERENCES categoria_problema(id_categoria) ON DELETE SET NULL,  FOREIGN KEY(id_equipo)    REFERENCES equipo(id_equipo)                ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS "rack" (
	"id_rack"	INTEGER,
	"numero"	INTEGER,
	"nombre"	TEXT,
	"cantidad_maxima"	INTEGER,
	"fecha_ultima_edicion"	TEXT, ultima_auditoria_fecha TEXT,
	PRIMARY KEY("id_rack" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "rack_por_sala" (
  "id_rack_x_sala" INTEGER,
  "id_rack"  INTEGER,
  "id_sala"  INTEGER,
  "fecha_ultima_edicion" TEXT,
  PRIMARY KEY("id_rack_x_sala" AUTOINCREMENT),
  FOREIGN KEY("id_rack") REFERENCES "rack"("id_rack") ON DELETE CASCADE,
  FOREIGN KEY("id_sala") REFERENCES "sala"("id_sala") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS regla_logica (  id_regla        INTEGER PRIMARY KEY AUTOINCREMENT,  id_equipo       INTEGER,  id_tipo_equipo  INTEGER,  nombre          TEXT,  operador        TEXT NOT NULL CHECK (operador IN ('AND','OR')),  activa          INTEGER NOT NULL DEFAULT 1,  orden           INTEGER NOT NULL DEFAULT 0,  fecha_ultima_edicion TEXT,  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,  CHECK ((id_equipo IS NULL) <> (id_tipo_equipo IS NULL)));
CREATE TABLE IF NOT EXISTS regla_logica_miembro (  id_miembro       INTEGER PRIMARY KEY AUTOINCREMENT,  id_regla         INTEGER NOT NULL,  id_conector      INTEGER,  id_regla_miembro INTEGER,  patron_conector  TEXT,  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE,  FOREIGN KEY(id_regla_miembro) REFERENCES regla_logica(id_regla) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS regla_logica_salida (  id_regla    INTEGER NOT NULL,  id_conector INTEGER NOT NULL,  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS riesgo_equipo_cache (  id_equipo     INTEGER PRIMARY KEY,  probabilidad  REAL,  impacto       REAL,  riesgo        REAL,  nivel         TEXT,  detalle_json  TEXT,  fecha_calculo TEXT,  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS "sala" (
	"id_sala"	INTEGER,
	"nombre"	INTEGER,
	"fecha_ultima_edicion"	TEXT,
	PRIMARY KEY("id_sala" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "slot" (
  "id_slot"  INTEGER,
  "nombre"   TEXT,
  "id_equipo" INTEGER,
  "id_frame" INTEGER,
  "id_imagen" INTEGER,
  "rectangulo_x_en_imagen"  INTEGER,
  "rectangulo_y_en_imagen"  INTEGER,
  "rectangulo_ancho_pixeles" INTEGER,
  "rectangulo_alto_pixeles"  INTEGER,
  "fecha_ultima_edicion" TEXT, ultima_auditoria_fecha TEXT,
  PRIMARY KEY("id_slot" AUTOINCREMENT),
  FOREIGN KEY("id_frame")  REFERENCES "frame"("id_frame")   ON DELETE CASCADE,
  FOREIGN KEY("id_equipo") REFERENCES "equipo"("id_equipo") ON DELETE SET NULL,
  FOREIGN KEY("id_imagen") REFERENCES "imagen"("id_imagen") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS slot_catalogo (  id_slot_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,  id_frame_catalogo INTEGER NOT NULL,  nombre TEXT,  rectangulo_x_en_imagen  INTEGER,  rectangulo_y_en_imagen  INTEGER,  rectangulo_ancho_pixeles INTEGER,  rectangulo_alto_pixeles  INTEGER,  fecha_ultima_edicion TEXT,  FOREIGN KEY(id_frame_catalogo) REFERENCES frame_catalogo(id_frame_catalogo) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS "tipo_cable" (
	"id_tipo_cable"	INTEGER,
	"nombre"	TEXT,
	"fecha_ultima_edicion"	TEXT,
	"naturaleza_senal" TEXT CHECK("naturaleza_senal" IN ('ANALOGICA','DIGITAL','HIBRIDA','DATOS')),
	"longitud_maxima_recomendada_balanceado_m" REAL,
	"longitud_maxima_recomendada_desbalanceado_m" REAL,
	"ancho_banda_mhz" REAL,
	PRIMARY KEY("id_tipo_cable" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "tipo_conector" (
	"id_tipo_conector"	INTEGER,
	"nombre"	INTEGER,
	"fecha_ultima_edicion"	TEXT,
	PRIMARY KEY("id_tipo_conector" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "tipo_equipo" (
	"id_tipo_equipo"	INTEGER,
	"nombre"	INTEGER,
	"fecha_ultima_edicion"	TEXT, vida_util_anios INTEGER, rol_senal TEXT DEFAULT 'DISTRIBUIDOR',
	PRIMARY KEY("id_tipo_equipo" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "senal" (  "id_senal" INTEGER,  "nombre" TEXT NOT NULL,  "tipo_contenido" TEXT,  "descripcion" TEXT,  "fecha_ultima_edicion" TEXT,  PRIMARY KEY("id_senal" AUTOINCREMENT));
CREATE TABLE IF NOT EXISTS "tipo_formato_senal" (  "id_formato" INTEGER,  "nombre" TEXT NOT NULL,  "fecha_ultima_edicion" TEXT,  PRIMARY KEY("id_formato" AUTOINCREMENT));
CREATE TABLE IF NOT EXISTS "senal_en_conector" (  "id_senal_en_conector" INTEGER,  "id_conector" INTEGER NOT NULL UNIQUE,  "id_senal" INTEGER NOT NULL,  "id_formato" INTEGER,  "origen" TEXT NOT NULL DEFAULT 'MANUAL' CHECK (origen IN ('MANUAL','PROPAGADA')),  "fecha_ultima_edicion" TEXT,  PRIMARY KEY("id_senal_en_conector" AUTOINCREMENT),  FOREIGN KEY("id_conector") REFERENCES "conector"("id_conector") ON DELETE CASCADE,  FOREIGN KEY("id_senal") REFERENCES "senal"("id_senal") ON DELETE CASCADE,  FOREIGN KEY("id_formato") REFERENCES "tipo_formato_senal"("id_formato") ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS "senal_linaje" (  "id_linaje" INTEGER,  "id_senal_hijo" INTEGER NOT NULL,  "id_senal_padre" INTEGER NOT NULL,  "nota" TEXT,  "fecha_ultima_edicion" TEXT,  PRIMARY KEY("id_linaje" AUTOINCREMENT),  FOREIGN KEY("id_senal_hijo") REFERENCES "senal"("id_senal") ON DELETE CASCADE,  FOREIGN KEY("id_senal_padre") REFERENCES "senal"("id_senal") ON DELETE CASCADE,  UNIQUE("id_senal_hijo","id_senal_padre"));
CREATE TABLE IF NOT EXISTS "tipo_ficha" (
	"id_tipo_ficha"	INTEGER,
	"nombre"	TEXT,
	"fecha_ultima_edicion"	TEXT,
	"n_conductores" INTEGER,
	"modo_balance_default" TEXT CHECK("modo_balance_default" IN ('BALANCEADO','DESBALANCEADO','NA')),
	"modo_canal_default"   TEXT CHECK("modo_canal_default"   IN ('MONO','ESTEREO','NA')),
	"ancho_banda_mhz" REAL,
	PRIMARY KEY("id_tipo_ficha" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "unidad_longitud_factor" (
	"unidad" TEXT PRIMARY KEY,
	"factor_a_metros" REAL NOT NULL
);
CREATE VIEW "CONEXIONES" AS select 
	distinct conexion.id_conexion,
	coalesce(equipo.nombre || " INV" || equipo.num_inventario,equipo.nombre || " NS" || equipo.num_serie,equipo.nombre) as equipo_nombre,
	conector.nombre as conector_nombre,
	cable.codigo as cable_codigo,
	tipo_conector.nombre as tipo_conector,
	tipo_equipo.nombre as tipo_equipo,
	conexion.id_cable,
	conexion.id_conector,
	equipo.id_equipo,
	frame.nombre as frame
from
	conexion
left join cable on conexion.id_cable = cable.id_cable
left join conector on conexion.id_conector = conector.id_conector 
left join equipo on conector.id_equipo = equipo.id_equipo
left join tipo_conector on conector.id_tipo_conector = tipo_conector.id_tipo_conector
left join tipo_equipo on tipo_equipo.id_tipo_equipo = equipo.id_tipo_equipo
left join slot on equipo.id_equipo = slot.id_equipo
left join frame on frame.id_frame = slot.id_frame;
CREATE VIEW "CONEXIONES DONDE APARECE UN CABLE MAS DE 2 VECES" AS SELECT conexiones.id_cable, conexiones.cable_codigo from CONEXIONES
group by conexiones.id_cable
having count(conexiones.cable_codigo) > 2;
CREATE VIEW "CONEXIONES_AMBOS_EXTREMOS" AS with origen as
	(select 
		coalesce(conexiones.frame || ':' || conexiones.equipo_nombre,conexiones.equipo_nombre) as "Extremo A: equipo",
		conexiones.tipo_equipo as "Extremo A: tipo equipo",
		conexiones.conector_nombre || '[' || conexiones.tipo_conector || ']' as "Extremo A: conector con tipo",
		conexiones.tipo_conector "Extremo A: tipo conector",
		conexiones.id_equipo,
		conexiones.id_cable,
		conexiones.id_conexion,
		conexiones.id_conector
	 from conexiones)
select 
	d.cable_codigo as "Cable",
	"Extremo A: equipo",
	"Extremo A: tipo equipo",
	"Extremo A: conector con tipo",
	"Extremo A: tipo conector",
	coalesce(d.frame || ':' || d.equipo_nombre,d.equipo_nombre) as "Extremo B: Equipo",
	d.tipo_equipo as "Extremo B: tipo equipo",
	d.conector_nombre || '[' || d.tipo_conector || ']' as "Extremo B: conector con tipo",
	d.tipo_conector "Extremo B: tipo conector",
	d.id_equipo,
	o.id_equipo,
	d.id_cable,
	d.id_conexion,
	d.id_conector,
	o.id_conector
from CONEXIONES d
join origen o
on d.id_equipo <> o.id_equipo and o.id_cable = d.id_Cable;
CREATE VIEW "CONEXIONES_AMBOS_EXTREMOS_CON_IMAGEN" AS select 
	CONEXIONES_AMBOS_EXTREMOS.*,
	conector.coordenada_x_en_imagen as x,
	conector.coordenada_y_en_imagen as y,
	imagen.path_archivo
from 
CONEXIONES_AMBOS_EXTREMOS
left join conector on conector.id_conector = CONEXIONES_AMBOS_EXTREMOS.id_conector
left join imagen on imagen.id_imagen = conector.id_imagen;
CREATE VIEW "RACKS CON EQUIPOS" AS SELECT 
	posicion_en_rack.id_posicion_en_rack as id,
	rack.nombre as rack,
	posicion_en_rack.orificio_posicion_equipo_en_rack as orificio,
	coalesce(equipo.num_inventario,frame.num_inventario, "SIN INVENTARIO") as inventario,
	coalesce(equipo.nombre,frame.nombre) as dispositivo,
	posicion_en_rack.unidades_de_rack_equipo as UR,
	rack.id_rack as id_rack,
	equipo.id_equipo as id_equipo,
	frame.id_frame as id_frame
from 
	posicion_en_rack 
	left join equipo on posicion_en_rack.id_equipo = equipo.id_equipo and posicion_en_rack.id_frame is NULL
	left join frame on posicion_en_rack.id_frame = frame.id_frame and posicion_en_rack.id_equipo is NULL
	left join rack on posicion_en_rack.id_rack = rack.id_rack
order by orificio;
CREATE VIEW "VISTA_CABLES" AS select id_cable, codigo, longitud FROM cable where es_cable_conexion_interna = 0 order by codigo;
CREATE VIEW "VISTA_CABLE_EDICION" AS select 
	cable.id_cable,
	cable.codigo as codigo,
	cable.id_tipo_cable as id_tipo_cable,
	tipo_cable.nombre as nombre_tipo_cable,
	cable.id_tipo_ficha as id_tipo_ficha,
	tipo_ficha.nombre as nombre_tipo_ficha,
	cable.longitud as longitud,
	cable.unidad_longitud,
	cable.metraje_impreso_primer_extremo,
	cable.metraje_impreso_segundo_extremo,
	cable.unidad_metraje_impreso
from
	cable
left join tipo_cable on tipo_cable.id_tipo_cable = cable.id_tipo_cable
left join tipo_ficha on tipo_ficha.id_tipo_ficha= cable.id_tipo_ficha
where cable.es_cable_conexion_interna = 0
order by codigo;
CREATE VIEW "VISTA_CONECTORES" AS select 
	conector.id_conector,
	conector.nombre as conector_nombre,
	tipo_conector.nombre as nombre_tipo_conector,
	conector.id_equipo as id_equipo
from
	conector
left join tipo_conector on tipo_conector.id_tipo_conector = conector.id_tipo_conector;
CREATE VIEW "VISTA_CONECTOR_EDICION" AS select 
	conector.id_conector,
	conector.nombre as conector_nombre,
	tipo_conector.nombre as nombre_tipo_conector,
	tipo_conector.id_tipo_conector As id_tipo_conector,
	conector.id_equipo as id_equipo,
	conector.coordenada_x_en_imagen as x,
	conector.coordenada_y_en_imagen as y,
	conector.id_imagen as conector_id_imagen,
	imagen.path_archivo as path_imagen
from
	conector
left join tipo_conector on tipo_conector.id_tipo_conector = conector.id_tipo_conector
left join imagen on conector.id_imagen = imagen.id_imagen;
CREATE VIEW "VISTA_CONEXIONES" AS select 
	cable.codigo as cable_codigo,
	equipo.nombre as equipo_nombre,
	conector.nombre as conector_nombre
from
	conexion
left join cable on conexion.id_cable = cable.id_cable
left join conector on conexion.id_conector = conector.id_conector 
left join equipo on conector.id_equipo = equipo.id_equipo
WHERE
	conexion.es_conexion_interna = 0
ORDER BY cable.codigo;
CREATE VIEW "VISTA_EQUIPOS" AS select 
	equipo.id_equipo as id,
	equipo.nombre as nombre,
	marca.nombre as marca,
	equipo.modelo as modelo,
	equipo.num_inventario AS inventario,
	equipo.num_serie as serie,
	marca.id_marca as id_marca,
	tipo_equipo.nombre as tipo_nombe,
	tipo_equipo.id_tipo_equipo as id_tipo,
	imagen.path_archivo as imagen_path,
	imagen.id_imagen as id_imagen
from
	equipo
left join marca on equipo.id_marca = marca.id_marca
left join tipo_equipo on equipo.id_tipo_equipo = tipo_equipo.id_tipo_equipo
left join imagen on equipo.id_imagen = imagen.id_imagen
ORDER by equipo.nombre;
CREATE VIEW "VISTA_EQUIPOS_EDICION" AS select 
	equipo.id_equipo as id,
	equipo.nombre as nombre,
	marca.nombre as marca,
	equipo.modelo as modelo,
	equipo.num_inventario AS inventario,
	equipo.num_serie as serie,
	marca.id_marca as id_marca,
	tipo_equipo.nombre as tipo_nombe,
	tipo_equipo.id_tipo_equipo as id_tipo,
	imagen.path_archivo as imagen_path,
	imagen.id_imagen as id_imagen
from
	equipo
left join marca on equipo.id_marca = marca.id_marca
left join tipo_equipo on equipo.id_tipo_equipo = tipo_equipo.id_tipo_equipo
left join imagen on equipo.id_imagen = imagen.id_imagen
where equipo.nombre NOT LIKE "EMPALME BNC 1" and equipo.nombre NOT LIKE "SIN EQUIPO"
ORDER by equipo.nombre;
CREATE VIEW "VISTA_EQUIPO_DETALLE" AS select 
	equipo.id_equipo as id,
	marca.id_marca as id_marca,
	imagen.id_imagen as id_imagen,
	tipo_equipo.id_tipo_equipo as id_tipo,
	equipo.nombre as nombre,
	marca.nombre as marca,
	equipo.modelo as modelo,
	equipo.num_inventario AS inventario,
	equipo.num_serie as serie,
	tipo_equipo.nombre as tipo_nombre,
	imagen.path_archivo as imagen_path,
	equipo.coordenada_x_en_imagen as coordenada_x_en_imagen,
	equipo.coordenada_y_en_imagen as coordenada_y_en_imagen
from
	equipo
left join marca on equipo.id_marca = marca.id_marca
left join tipo_equipo on equipo.id_tipo_equipo = tipo_equipo.id_tipo_equipo
left join imagen on equipo.id_imagen = imagen.id_imagen
where equipo.nombre NOT LIKE "EMPALME BNC 1" and equipo.nombre NOT LIKE "SIN EQUIPO"
ORDER by equipo.nombre;
CREATE VIEW "VISTA_FRAMES" AS select 
	frame.id_frame as id,
	frame.nombre as nombre,
	marca.nombre as marca,
	frame.modelo as modelo,
	marca.id_marca as id_marca,
	imagen.path_archivo as imagen_path,
	imagen.id_imagen as id_imagen,
	frame.num_inventario as inventario
from
	frame
left join marca on frame.id_marca = marca.id_marca
left join imagen on frame.id_imagen = imagen.id_imagen
ORDER by frame.nombre;
CREATE VIEW "VISTA_SLOTS" AS select
	slot.id_slot as id,
	slot.nombre as nombre,
	equipo.nombre as nombre_equipo,
	slot.id_frame as id_frame
from
	slot
left join equipo on slot.id_equipo = equipo.id_equipo
order by id;
CREATE VIEW "VISTA_SLOT_EDICION" as select 
	slot.id_slot,
	slot.nombre as slot_nombre,
	equipo.id_equipo as id_equipo,
	equipo.nombre as nombre_equipo,
	imagen.path_archivo as path_imagen,
	imagen.id_imagen as id_imagen,
	slot.rectangulo_x_en_imagen as x,
	slot.rectangulo_y_en_imagen as y,
	slot.rectangulo_alto_pixeles as alto,
	slot.rectangulo_ancho_pixeles as ancho,
	slot.id_frame as id_frame
from
	slot
left join equipo on slot.id_equipo = equipo.id_equipo
left join imagen on slot.id_imagen = imagen.id_imagen;
CREATE VIEW "vista_diagrama" AS select 
nombre,x,y
from diagrama_equipos_posicion_en_imagen
left join equipo on equipo.id_equipo = diagrama_equipos_posicion_en_imagen.id_equipo;
CREATE TRIGGER trg_cable_insert
    AFTER INSERT ON cable
    BEGIN
        UPDATE cable
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_cable = NEW.id_cable;
    END;
CREATE TRIGGER trg_cable_update
    AFTER UPDATE ON cable
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE cable
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_cable = NEW.id_cable;
    END;
CREATE TRIGGER trg_conector_insert
    AFTER INSERT ON conector
    BEGIN
        UPDATE conector
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_conector = NEW.id_conector;
    END;
CREATE TRIGGER trg_conector_update
    AFTER UPDATE ON conector
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE conector
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_conector = NEW.id_conector;
    END;
CREATE TRIGGER trg_conexion_insert
    AFTER INSERT ON conexion
    BEGIN
        UPDATE conexion
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_conexion = NEW.id_conexion;
    END;
CREATE TRIGGER trg_conexion_update
    AFTER UPDATE ON conexion
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE conexion
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_conexion = NEW.id_conexion;
    END;
CREATE TRIGGER trg_equipo_insert
    AFTER INSERT ON equipo
    BEGIN
        UPDATE equipo
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_equipo = NEW.id_equipo;
    END;
CREATE TRIGGER trg_equipo_update
    AFTER UPDATE ON equipo
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE equipo
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_equipo = NEW.id_equipo;
    END;
CREATE TRIGGER trg_equiponoraqueable_por_sala_insert
    AFTER INSERT ON equiponoraqueable_por_sala
    BEGIN
        UPDATE equiponoraqueable_por_sala
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_equiponoraqueable_por_sala = NEW.id_equiponoraqueable_por_sala;
    END;
CREATE TRIGGER trg_equiponoraqueable_por_sala_update
    AFTER UPDATE ON equiponoraqueable_por_sala
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE equiponoraqueable_por_sala
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_equiponoraqueable_por_sala = NEW.id_equiponoraqueable_por_sala;
    END;
CREATE TRIGGER trg_frame_insert
    AFTER INSERT ON frame
    BEGIN
        UPDATE frame
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_frame = NEW.id_frame;
    END;
CREATE TRIGGER trg_frame_update
    AFTER UPDATE ON frame
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE frame
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_frame = NEW.id_frame;
    END;
CREATE TRIGGER trg_imagen_insert
AFTER INSERT ON imagen
BEGIN
    UPDATE imagen
    SET fecha_ultima_Edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_imagen = NEW.id_imagen;
END;
CREATE TRIGGER trg_imagen_update
AFTER UPDATE ON imagen
WHEN NEW.fecha_ultima_Edicion = OLD.fecha_ultima_Edicion OR NEW.fecha_ultima_Edicion IS NULL
BEGIN
    UPDATE imagen
    SET fecha_ultima_Edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_imagen = NEW.id_imagen;
END;
CREATE TRIGGER trg_marca_insert
AFTER INSERT ON marca
BEGIN
    UPDATE marca
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_marca = NEW.id_marca;
END;
CREATE TRIGGER trg_marca_update
AFTER UPDATE ON marca
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE marca
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_marca = NEW.id_marca;
END;
CREATE TRIGGER trg_posicion_en_rack_insert
    AFTER INSERT ON posicion_en_rack
    BEGIN
        UPDATE posicion_en_rack
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_posicion_en_rack = NEW.id_posicion_en_rack;
    END;
CREATE TRIGGER trg_posicion_en_rack_update
    AFTER UPDATE ON posicion_en_rack
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE posicion_en_rack
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_posicion_en_rack = NEW.id_posicion_en_rack;
    END;
CREATE TRIGGER trg_rack_insert
AFTER INSERT ON rack
BEGIN
    UPDATE rack
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_rack = NEW.id_rack;
END;
CREATE TRIGGER trg_rack_por_sala_insert
    AFTER INSERT ON rack_por_sala
    BEGIN
        UPDATE rack_por_sala
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_rack_x_sala = NEW.id_rack_x_sala;
    END;
CREATE TRIGGER trg_rack_update
AFTER UPDATE ON rack
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE rack
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_rack = NEW.id_rack;
END;
CREATE TRIGGER trg_sala_insert
AFTER INSERT ON sala
BEGIN
    UPDATE sala
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_sala = NEW.id_sala;
END;
CREATE TRIGGER trg_sala_update
AFTER UPDATE ON sala
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE sala
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_sala = NEW.id_sala;
END;
CREATE TRIGGER trg_slot_insert
    AFTER INSERT ON slot
    BEGIN
        UPDATE slot
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_slot = NEW.id_slot;
    END;
CREATE TRIGGER trg_slot_update
    AFTER UPDATE ON slot
    WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
    BEGIN
        UPDATE slot
        SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
        WHERE id_slot = NEW.id_slot;
    END;
CREATE TRIGGER trg_tipo_cable_insert
AFTER INSERT ON tipo_cable
BEGIN
    UPDATE tipo_cable
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_cable = NEW.id_tipo_cable;
END;
CREATE TRIGGER trg_tipo_cable_update
AFTER UPDATE ON tipo_cable
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE tipo_cable
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_cable = NEW.id_tipo_cable;
END;
CREATE TRIGGER trg_tipo_conector_insert
AFTER INSERT ON tipo_conector
BEGIN
    UPDATE tipo_conector
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_conector = NEW.id_tipo_conector;
END;
CREATE TRIGGER trg_tipo_conector_update
AFTER UPDATE ON tipo_conector
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE tipo_conector
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_conector = NEW.id_tipo_conector;
END;
CREATE TRIGGER trg_tipo_equipo_insert
AFTER INSERT ON tipo_equipo
BEGIN
    UPDATE tipo_equipo
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_equipo = NEW.id_tipo_equipo;
END;
CREATE TRIGGER trg_tipo_equipo_update
AFTER UPDATE ON tipo_equipo
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE tipo_equipo
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_equipo = NEW.id_tipo_equipo;
END;
CREATE TRIGGER trg_tipo_ficha_insert
AFTER INSERT ON tipo_ficha
BEGIN
    UPDATE tipo_ficha
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_ficha = NEW.id_tipo_ficha;
END;
CREATE TRIGGER trg_tipo_ficha_update
AFTER UPDATE ON tipo_ficha
WHEN NEW.fecha_ultima_edicion = OLD.fecha_ultima_edicion OR NEW.fecha_ultima_edicion IS NULL
BEGIN
    UPDATE tipo_ficha
    SET fecha_ultima_edicion = STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')
    WHERE id_tipo_ficha = NEW.id_tipo_ficha;
END;

-- Diagramas personalizados (guardados): feature aparte, diagramas armados a
-- mano por el usuario (equipos + conexiones reales y/o "manuales" que no se
-- persisten en la tabla conexion). Ver Modelo.asegurar_tablas_diagramas_guardados
-- y diagrama_personalizado.py.
CREATE TABLE IF NOT EXISTS diagrama_guardado (
  id_diagrama INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  fecha_creacion TEXT,
  fecha_edicion TEXT
);
CREATE TABLE IF NOT EXISTS diagrama_guardado_nodo (
  id_diagrama_nodo INTEGER PRIMARY KEY AUTOINCREMENT,
  id_diagrama INTEGER NOT NULL,
  id_equipo INTEGER NOT NULL,
  x REAL, y REAL,
  FOREIGN KEY(id_diagrama) REFERENCES diagrama_guardado(id_diagrama) ON DELETE CASCADE,
  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS diagrama_guardado_conexion (
  id_diagrama_conexion INTEGER PRIMARY KEY AUTOINCREMENT,
  id_diagrama INTEGER NOT NULL,
  id_conector_a INTEGER NOT NULL,
  id_conector_b INTEGER NOT NULL,
  es_real INTEGER DEFAULT 0,
  id_cable_real INTEGER,
  etiqueta TEXT,
  FOREIGN KEY(id_diagrama) REFERENCES diagrama_guardado(id_diagrama) ON DELETE CASCADE,
  FOREIGN KEY(id_conector_a) REFERENCES conector(id_conector) ON DELETE CASCADE,
  FOREIGN KEY(id_conector_b) REFERENCES conector(id_conector) ON DELETE CASCADE
);

-- Modo Escenario (Plan: CableDoc_Plan_Escenarios_Diagrama.md): un
-- "escenario" agrupa varios cambios (falla de equipo, desconexión de
-- cable, conexión virtual de reconexión de emergencia) que se evalúan
-- juntos con GraphImpactAnalyzer.simular_escenario sin tocar la
-- infraestructura real hasta "Aplicar". Ver Modelo.asegurar_tablas_escenario,
-- escenario_engine.py y escenario_ui.py.
CREATE TABLE IF NOT EXISTS escenario (
  id_escenario INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  estado TEXT NOT NULL DEFAULT 'borrador',
  fecha_creacion TEXT,
  fecha_ultima_edicion TEXT
);
CREATE TABLE IF NOT EXISTS escenario_cambio (
  id_cambio INTEGER PRIMARY KEY AUTOINCREMENT,
  id_escenario INTEGER NOT NULL,
  tipo TEXT NOT NULL,
  id_equipo INTEGER,
  id_cable INTEGER,
  id_conector_a INTEGER,
  id_conector_b INTEGER,
  orden INTEGER NOT NULL DEFAULT 0,
  fecha_ultima_edicion TEXT,
  FOREIGN KEY(id_escenario) REFERENCES escenario(id_escenario) ON DELETE CASCADE,
  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,
  FOREIGN KEY(id_cable) REFERENCES cable(id_cable) ON DELETE CASCADE,
  FOREIGN KEY(id_conector_a) REFERENCES conector(id_conector) ON DELETE CASCADE,
  FOREIGN KEY(id_conector_b) REFERENCES conector(id_conector) ON DELETE CASCADE
);
-- Vista previa visual de la señal (ver plan_vista_previa_visual_senal.md).
-- Todo por CONECTOR de salida, nunca por equipo (ver sección 0 del plan:
-- un mismo equipo puede tener una salida con imagen manual y otra
-- compuesta, ej. MDK-111 A-M OUT 1 = barras / OUT 2 = key BKGD+FILL+MATTE).
CREATE TABLE IF NOT EXISTS imagen_senal_conector (
  id_conector INTEGER PRIMARY KEY,
  id_imagen   INTEGER NOT NULL,
  fecha_ultima_edicion TEXT,
  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE,
  FOREIGN KEY(id_imagen)   REFERENCES imagen(id_imagen)   ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS estrategia_visual (
  id_estrategia    INTEGER PRIMARY KEY AUTOINCREMENT,
  id_conector      INTEGER,
  id_tipo_equipo   INTEGER,
  patron_conector_salida TEXT,
  modo             TEXT NOT NULL CHECK (modo IN ('MOSAICO','OVERLAY','KEY','AUDIO_EMBEBIDO')),
  fecha_ultima_edicion TEXT,
  FOREIGN KEY(id_conector)    REFERENCES conector(id_conector)       ON DELETE CASCADE,
  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,
  CHECK ((id_conector IS NULL) <> (id_tipo_equipo IS NULL))
);
CREATE TABLE IF NOT EXISTS estrategia_visual_miembro (
  id_miembro      INTEGER PRIMARY KEY AUTOINCREMENT,
  id_estrategia   INTEGER NOT NULL,
  id_conector     INTEGER,
  patron_conector TEXT,
  posicion        TEXT NOT NULL,
  orden           INTEGER NOT NULL DEFAULT 0,
  origen          TEXT,
  FOREIGN KEY(id_estrategia) REFERENCES estrategia_visual(id_estrategia) ON DELETE CASCADE,
  FOREIGN KEY(id_conector)   REFERENCES conector(id_conector) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS diagnostico_sesion (
  id_sesion       INTEGER PRIMARY KEY AUTOINCREMENT,
  id_conector_sintoma INTEGER NOT NULL,
  descripcion     TEXT,
  resultado       TEXT,
  id_cable_resultado  INTEGER,
  id_equipo_resultado INTEGER,
  fecha_inicio    TEXT,
  fecha_fin       TEXT,
  FOREIGN KEY(id_conector_sintoma)  REFERENCES conector(id_conector) ON DELETE CASCADE,
  FOREIGN KEY(id_cable_resultado)   REFERENCES cable(id_cable)       ON DELETE SET NULL,
  FOREIGN KEY(id_equipo_resultado)  REFERENCES equipo(id_equipo)     ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS diagnostico_paso (
  id_paso         INTEGER PRIMARY KEY AUTOINCREMENT,
  id_sesion       INTEGER NOT NULL,
  id_conector_consultado INTEGER NOT NULL,
  respuesta       TEXT NOT NULL CHECK(respuesta IN ('SI','NO','NO_SE')),
  orden           INTEGER NOT NULL,
  FOREIGN KEY(id_sesion) REFERENCES diagnostico_sesion(id_sesion) ON DELETE CASCADE,
  FOREIGN KEY(id_conector_consultado) REFERENCES conector(id_conector) ON DELETE CASCADE
);
-- plan_desarrollo_extension_cable.md §3.1 — empalme ficha-contra-ficha de
-- dos extremos sueltos de cable (conexion.id_conector IS NULL), sin
-- equipo ni barril de por medio. Cardinalidad 1 a 1 (UNIQUE por extremo).
-- Ver Modelo.asegurar_tablas_extension_cable() para la migración
-- idempotente en instalaciones existentes; esta definición es la
-- referencia para instalaciones nuevas (no se ejecuta en producción).
CREATE TABLE IF NOT EXISTS extension_cable (
  id_extension INTEGER PRIMARY KEY AUTOINCREMENT,
  id_conexion_a INTEGER NOT NULL,
  id_conexion_b INTEGER NOT NULL,
  id_rack INTEGER,
  id_sala INTEGER,
  posicion_libre TEXT,
  es_armado_correcto INTEGER,
  detalle_armado TEXT,
  fecha_ultima_edicion TEXT,
  ultima_auditoria_fecha TEXT,
  FOREIGN KEY(id_conexion_a) REFERENCES conexion(id_conexion) ON DELETE CASCADE,
  FOREIGN KEY(id_conexion_b) REFERENCES conexion(id_conexion) ON DELETE CASCADE,
  FOREIGN KEY(id_rack) REFERENCES rack(id_rack) ON DELETE SET NULL,
  FOREIGN KEY(id_sala) REFERENCES sala(id_sala) ON DELETE SET NULL,
  UNIQUE(id_conexion_a),
  UNIQUE(id_conexion_b)
);
COMMIT;
