"""CableDoc Web — capa JSON de lectura (plan_pyodide_v1.md, Fase A.1).

Un método por pantalla; la UI nunca ve `Modelo` crudo. Todas las funciones
devuelven estructuras JSON-serializables (dict/list de str, int, float, None)
y se invocan desde JS a través de `call(nombre, args_json)`, que siempre
devuelve un string JSON `{"ok": true, "data": ..., "ms": n}` o
`{"ok": false, "error": "..."}` — nunca levanta excepciones hacia JS.

Solo lectura: no hay INSERT/UPDATE/DELETE acá (la escritura es Fase B).

Notas de diseño:
  - `core.modelo` se importa de forma diferida (`_M()`): al importarse crea una
    base vacía si no existe `db.db` (asegurar_base_datos), así que el worker
    solo debe llamar a este módulo DESPUÉS de cargar la base real.
  - Se usa la conexión de Modelo (`_conn_ctx`: foreign_keys ON, cierre
    garantizado), pero las consultas son SQL directo sobre las tablas: los
    `listar_*`/`obtener_*` de Modelo devuelven listas posicionales pensadas
    para GTK, no estructuras con nombre.
  - Los ids van como int (tal cual salen de SQLite). Los motores de
    `core/` (GraphImpactAnalyzer, RiskEngine) usan str: convertir en la
    frontera cuando se agreguen (A.7).
  - Las tablas opcionales (señales, problemas, caché de riesgo) se leen con
    `_rows_opt`: si la base es vieja y no las tiene, devuelven lista vacía.
"""
import inspect
import json
import sqlite3
import time


def _M():
    from core.modelo import Modelo
    return Modelo


def _rows(sql, params=()):
    with _M()._conn_ctx() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def _rows_opt(sql, params=()):
    try:
        return _rows(sql, params)
    except sqlite3.OperationalError:  # tabla/columna inexistente en bases viejas
        return []


def _one(sql, params=()):
    r = _rows(sql, params)
    return r[0] if r else None


def _in(ids):
    return ",".join("?" * len(ids))


# Equipos "de sistema" que el desktop oculta en sus listas (VISTA_EQUIPOS_EDICION).
_SIN_SISTEMA = "e.nombre NOT LIKE 'EMPALME BNC 1' AND e.nombre NOT LIKE 'SIN EQUIPO'"


# ── Resumen y catálogos ──────────────────────────────────────────────────────

_TABLAS_RESUMEN = ("equipo", "conector", "cable", "conexion", "sala", "rack",
                   "frame", "slot", "imagen", "marca", "tipo_equipo",
                   "tipo_conector", "tipo_cable", "tipo_ficha")


def resumen():
    """Cantidad de filas por tabla principal (pantalla de inicio / chequeo)."""
    out = {}
    for t in _TABLAS_RESUMEN:  # nombres fijos, no vienen del usuario
        out[t] = _one(f"SELECT count(*) AS n FROM {t}")["n"]
    out["cables_externos"] = _one(
        "SELECT count(*) AS n FROM cable WHERE COALESCE(es_cable_conexion_interna,0)=0")["n"]
    return out


def catalogos():
    """Todos los catálogos chicos de una vez (marcas, tipos, señales, imágenes)."""
    return {
        "marcas": _rows("SELECT id_marca, nombre FROM marca ORDER BY lower(nombre)"),
        "tipos_equipo": _rows(
            "SELECT id_tipo_equipo, nombre, rol_senal, vida_util_anios "
            "FROM tipo_equipo ORDER BY lower(nombre)"),
        "tipos_conector": _rows(
            "SELECT id_tipo_conector, nombre FROM tipo_conector ORDER BY lower(nombre)"),
        "tipos_cable": _rows(
            "SELECT id_tipo_cable, nombre, naturaleza_senal, ancho_banda_mhz, "
            "longitud_maxima_recomendada_balanceado_m AS long_max_balanceado_m, "
            "longitud_maxima_recomendada_desbalanceado_m AS long_max_desbalanceado_m "
            "FROM tipo_cable ORDER BY lower(nombre)"),
        "tipos_ficha": _rows(
            "SELECT id_tipo_ficha, nombre, n_conductores, modo_balance_default, "
            "modo_canal_default, ancho_banda_mhz FROM tipo_ficha ORDER BY lower(nombre)"),
        "senales": _rows_opt(
            "SELECT id_senal, nombre, tipo_contenido, descripcion FROM senal "
            "ORDER BY lower(nombre)"),
        "formatos_senal": _rows_opt(
            "SELECT id_formato, nombre FROM tipo_formato_senal ORDER BY lower(nombre)"),
        "imagenes": _rows(
            "SELECT id_imagen, path_archivo, descripcion, mm_por_pixel "
            "FROM imagen ORDER BY id_imagen"),
    }


# ── Equipos y conectores ─────────────────────────────────────────────────────

def equipos_lista(incluir_sistema=False):
    """Una fila por equipo, para el árbol/lista (A.3)."""
    filtro = "" if incluir_sistema else f"WHERE {_SIN_SISTEMA}"
    return _rows(f"""
        SELECT e.id_equipo, e.nombre, m.nombre AS marca, e.modelo,
               e.num_inventario AS inventario, e.num_serie AS serie,
               e.id_marca, e.id_tipo_equipo, t.nombre AS tipo, t.rol_senal,
               e.id_imagen,
               (SELECT count(*) FROM conector c WHERE c.id_equipo = e.id_equipo) AS n_conectores
        FROM equipo e
        LEFT JOIN marca m ON m.id_marca = e.id_marca
        LEFT JOIN tipo_equipo t ON t.id_tipo_equipo = e.id_tipo_equipo
        {filtro}
        ORDER BY lower(e.nombre), e.id_equipo""")


def arbol_equipos():
    """Árbol de infraestructura para A.3: Sala → Rack → Frame → Equipo → Conectores.

    Misma jerarquía y mismo texto de búsqueda que `PanelArbol` (ui_gtk/panel_arbol_ui.py),
    pero con consultas en lote (una por tabla, sin N+1) y sin la sección "Cables".
    Nodo: {t: tipo, i: id, l: etiqueta, b: badge, h: [hijos]} (h falta en las hojas: conectores y equipos sin conectores).
    Tipos: sala | rack | frame | equipo | conector | sueltos | sin_ubicacion. Los dos últimos son
    grupos sin etiqueta (l=None, n=cantidad): el texto lo pone la UI para traducirlo.
    La etiqueta del equipo es "<nombre> <marca> <tipo> <modelo> <inventario> <serie>" (vacíos
    omitidos): el filtro de la UI matchea contra ella.
    Raíz: salas por nombre y, si hay, el grupo "sin_ubicacion" al final.
    """
    def txt(v):
        return "" if v is None else str(v).strip()

    equipos = {}  # id → (etiqueta, tipo); en orden por nombre (también ordena a los sin ubicación)
    for r in _rows("""
            SELECT e.id_equipo, e.nombre, m.nombre AS marca, te.nombre AS tipo, e.modelo,
                   e.num_inventario AS inv, e.num_serie AS serie
            FROM equipo e
            LEFT JOIN marca m ON m.id_marca = e.id_marca
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE e.id_equipo != 0
            ORDER BY e.nombre, e.id_equipo"""):
        partes = (txt(r["nombre"]), txt(r["marca"]), txt(r["tipo"]), txt(r["modelo"]), txt(r["inv"]), txt(r["serie"]))
        equipos[r["id_equipo"]] = (" ".join(v for v in partes if v) or f"#{r['id_equipo']}", partes[2])

    conectores = {}  # id_equipo → [nodo conector]
    for r in _rows("""
            SELECT c.id_conector, c.id_equipo, c.nombre, tc.nombre AS tipo
            FROM conector c LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            ORDER BY c.nombre, c.id_conector"""):
        conectores.setdefault(r["id_equipo"], []).append(
            {"t": "conector", "i": r["id_conector"], "l": txt(r["nombre"]) or f"#{r['id_conector']}", "b": txt(r["tipo"])})

    def nodo_equipo(id_eq):
        etiqueta, tipo = equipos[id_eq]
        n = {"t": "equipo", "i": id_eq, "l": etiqueta, "b": tipo}
        if id_eq in conectores:
            n["h"] = conectores[id_eq]
        return n

    def agrupar(filas, clave, valor):
        out = {}
        for r in filas:
            out.setdefault(r[clave], []).append(valor(r))
        return out

    # Equipos en slots de cada frame (los que no existen en `equipo` se descartan, como el INNER JOIN del desktop).
    en_frame = agrupar(_rows("""
            SELECT sl.id_frame, sl.id_equipo FROM slot sl
            WHERE sl.id_equipo IS NOT NULL AND sl.id_equipo != 0
            ORDER BY sl.id_frame, sl.nombre, sl.id_slot"""),
        "id_frame", lambda r: r["id_equipo"])
    frames_de_rack = agrupar(_rows("""
            SELECT p.id_rack, f.id_frame, f.nombre, MIN(p.orificio_posicion_equipo_en_rack) AS pos
            FROM posicion_en_rack p JOIN frame f ON f.id_frame = p.id_frame
            WHERE p.id_frame IS NOT NULL
            GROUP BY p.id_rack, f.id_frame
            ORDER BY p.id_rack, pos, f.id_frame"""),
        "id_rack", lambda r: r)
    directos_de_rack = agrupar(_rows("""
            SELECT p.id_rack, p.id_equipo
            FROM posicion_en_rack p JOIN equipo e ON e.id_equipo = p.id_equipo
            WHERE p.id_frame IS NULL AND p.id_equipo IS NOT NULL AND p.id_equipo != 0
            ORDER BY p.id_rack, p.orificio_posicion_equipo_en_rack, e.nombre, p.id_posicion_en_rack"""),
        "id_rack", lambda r: r["id_equipo"])
    racks_de_sala = agrupar(_rows("""
            SELECT rps.id_sala, r.id_rack, r.nombre
            FROM rack r JOIN rack_por_sala rps ON rps.id_rack = r.id_rack
            ORDER BY rps.id_sala, r.numero, r.id_rack"""),
        "id_sala", lambda r: r)

    en_rack_o_slot = {r["id_equipo"] for r in _rows("""
        SELECT id_equipo FROM posicion_en_rack WHERE id_equipo IS NOT NULL AND id_equipo != 0
        UNION SELECT id_equipo FROM slot WHERE id_equipo IS NOT NULL AND id_equipo != 0""")}
    sueltos_de_sala = agrupar(_rows("""
            SELECT en.id_sala, e.id_equipo
            FROM equiponoraqueable_por_sala en JOIN equipo e ON e.id_equipo = en.id_equipo
            ORDER BY en.id_sala, e.nombre, e.id_equipo"""),
        "id_sala", lambda r: r["id_equipo"])
    con_sala = {r["id_equipo"] for r in _rows(
        "SELECT id_equipo FROM equiponoraqueable_por_sala WHERE id_equipo IS NOT NULL")}

    raiz = []
    for sala in _rows("SELECT id_sala, nombre FROM sala ORDER BY nombre, id_sala"):
        hijos_sala = []
        for rk in racks_de_sala.get(sala["id_sala"], []):
            hijos_rack = []
            for fr in frames_de_rack.get(rk["id_rack"], []):
                hijos_rack.append({
                    "t": "frame", "i": fr["id_frame"], "l": txt(fr["nombre"]) or f"#{fr['id_frame']}", "b": "",
                    "h": [nodo_equipo(e) for e in en_frame.get(fr["id_frame"], []) if e in equipos]})
            hijos_rack += [nodo_equipo(e) for e in directos_de_rack.get(rk["id_rack"], []) if e in equipos]
            hijos_sala.append({"t": "rack", "i": rk["id_rack"], "l": txt(rk["nombre"]) or f"#{rk['id_rack']}", "b": "", "h": hijos_rack})
        sueltos = [e for e in sueltos_de_sala.get(sala["id_sala"], []) if e in equipos and e not in en_rack_o_slot]
        if sueltos:
            hijos_sala.append({"t": "sueltos", "i": sala["id_sala"], "l": None, "b": "", "n": len(sueltos),
                              "h": [nodo_equipo(e) for e in sueltos]})
        raiz.append({"t": "sala", "i": sala["id_sala"], "l": txt(sala["nombre"]) or f"#{sala['id_sala']}", "b": "", "h": hijos_sala})

    sin_ubicacion = [e for e in equipos if e not in en_rack_o_slot and e not in con_sala]
    if sin_ubicacion:
        raiz.append({"t": "sin_ubicacion", "i": None, "l": None, "b": "", "n": len(sin_ubicacion),
                     "h": [nodo_equipo(e) for e in sin_ubicacion]})
    return {"nodos": raiz, "n_equipos": len(equipos)}


def _conexiones_de_conectores(ids):
    """{id_conector: [conexión, ...]} con el/los extremo(s) opuesto(s) de cada cable."""
    ids = list(ids)
    if not ids:
        return {}
    propias = _rows(f"""
        SELECT cx.id_conexion, cx.id_cable, cx.id_conector, k.codigo AS cable,
               cx.es_conexion_interna, cx.es_armado_correcto, cx.detalle_armado
        FROM conexion cx LEFT JOIN cable k ON k.id_cable = cx.id_cable
        WHERE cx.id_conector IN ({_in(ids)})
        ORDER BY cx.id_conexion""", ids)
    cables = sorted({r["id_cable"] for r in propias if r["id_cable"] is not None})
    otros_por_cable = {}
    if cables:
        for r in _rows(f"""
            SELECT cx.id_cable, cx.id_conector, c.nombre AS conector,
                   c.id_equipo, e.nombre AS equipo
            FROM conexion cx
            JOIN conector c ON c.id_conector = cx.id_conector
            LEFT JOIN equipo e ON e.id_equipo = c.id_equipo
            WHERE cx.id_cable IN ({_in(cables)})""", cables):
            otros_por_cable.setdefault(r["id_cable"], []).append(r)
    out = {}
    for r in propias:
        r["otros"] = [{k: o[k] for k in ("id_conector", "conector", "id_equipo", "equipo")}
                      for o in otros_por_cable.get(r["id_cable"], [])
                      if o["id_conector"] != r["id_conector"]]
        out.setdefault(r["id_conector"], []).append(r)
    return out


def equipo_ficha(id_equipo):
    """Ficha completa de un equipo (A.4): datos, conectores con sus conexiones,
    ubicación (rack/frame/slot), problemas y último riesgo calculado."""
    eq = _one("""
        SELECT e.*, m.nombre AS marca, t.nombre AS tipo, t.rol_senal,
               i.path_archivo AS imagen_path, i.mm_por_pixel AS imagen_mm_por_pixel
        FROM equipo e
        LEFT JOIN marca m ON m.id_marca = e.id_marca
        LEFT JOIN tipo_equipo t ON t.id_tipo_equipo = e.id_tipo_equipo
        LEFT JOIN imagen i ON i.id_imagen = e.id_imagen
        WHERE e.id_equipo = ?""", (id_equipo,))
    if eq is None:
        raise ValueError(f"No existe el equipo {id_equipo}")
    conectores = _rows("""
        SELECT c.id_conector, c.nombre, c.id_tipo_conector, tc.nombre AS tipo_conector,
               c.id_tipo_ficha, tf.nombre AS ficha, c.modo_balance, c.modo_canal,
               c.id_imagen, i.path_archivo AS imagen_path,
               c.coordenada_x_en_imagen AS x, c.coordenada_y_en_imagen AS y
        FROM conector c
        LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = c.id_tipo_ficha
        LEFT JOIN imagen i ON i.id_imagen = c.id_imagen
        WHERE c.id_equipo = ?
        ORDER BY c.id_conector""", (id_equipo,))
    ids = [c["id_conector"] for c in conectores]
    cx = _conexiones_de_conectores(ids)
    senales = {}
    if ids:
        for r in _rows_opt(f"""
            SELECT se.id_conector, s.nombre AS senal, f.nombre AS formato, se.origen
            FROM senal_en_conector se
            JOIN senal s ON s.id_senal = se.id_senal
            LEFT JOIN tipo_formato_senal f ON f.id_formato = se.id_formato
            WHERE se.id_conector IN ({_in(ids)})""", ids):
            senales[r["id_conector"]] = r
    for c in conectores:
        c["conexiones"] = cx.get(c["id_conector"], [])
        s = senales.get(c["id_conector"])
        c["senal"] = {"senal": s["senal"], "formato": s["formato"], "origen": s["origen"]} if s else None
    eq["conectores"] = conectores
    eq["racks"] = _rows("""
        SELECT p.id_posicion_en_rack, p.id_rack, r.nombre AS rack, r.numero AS rack_numero,
               p.orificio_posicion_equipo_en_rack AS orificio,
               p.unidades_de_rack_equipo AS unidades, p.id_frame,
               (SELECT group_concat(s.nombre, ', ') FROM rack_por_sala rs
                  JOIN sala s ON s.id_sala = rs.id_sala WHERE rs.id_rack = p.id_rack) AS sala
        FROM posicion_en_rack p LEFT JOIN rack r ON r.id_rack = p.id_rack
        WHERE p.id_equipo = ? ORDER BY p.id_posicion_en_rack""", (id_equipo,))
    eq["slots"] = _rows("""
        SELECT s.id_slot, s.nombre AS slot, s.id_frame, f.nombre AS frame
        FROM slot s LEFT JOIN frame f ON f.id_frame = s.id_frame
        WHERE s.id_equipo = ? ORDER BY s.id_slot""", (id_equipo,))
    eq["problemas"] = _rows_opt("""
        SELECT p.id_problema, p.gravedad, p.descripcion, p.fecha, p.resuelto,
               p.fecha_resolucion, c.nombre AS categoria
        FROM problema_equipo p LEFT JOIN categoria_problema c ON c.id_categoria = p.id_categoria
        WHERE p.id_equipo = ? ORDER BY p.resuelto, p.gravedad DESC, p.id_problema""", (id_equipo,))
    eq["riesgo"] = next(iter(_rows_opt(
        "SELECT probabilidad, impacto, riesgo, nivel, fecha_calculo "
        "FROM riesgo_equipo_cache WHERE id_equipo = ?", (id_equipo,))), None)
    return eq


def conector_ficha(id_conector):
    """Ficha de un conector (A.4): datos, equipo, conexiones con extremos opuestos,
    señal y ruteo de matriz (si es salida de una matriz)."""
    c = _one("""
        SELECT c.*, e.nombre AS equipo, tc.nombre AS tipo_conector, tf.nombre AS ficha,
               i.path_archivo AS imagen_path, i.mm_por_pixel AS imagen_mm_por_pixel
        FROM conector c
        LEFT JOIN equipo e ON e.id_equipo = c.id_equipo
        LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = c.id_tipo_ficha
        LEFT JOIN imagen i ON i.id_imagen = c.id_imagen
        WHERE c.id_conector = ?""", (id_conector,))
    if c is None:
        raise ValueError(f"No existe el conector {id_conector}")
    c["conexiones"] = _conexiones_de_conectores([id_conector]).get(id_conector, [])
    c["senal"] = next(iter(_rows_opt("""
        SELECT s.nombre AS senal, f.nombre AS formato, se.origen
        FROM senal_en_conector se JOIN senal s ON s.id_senal = se.id_senal
        LEFT JOIN tipo_formato_senal f ON f.id_formato = se.id_formato
        WHERE se.id_conector = ?""", (id_conector,))), None)
    c["ruteo_entrada"] = next(iter(_rows_opt("""
        SELECT m.id_conector_entrada AS id_conector, ci.nombre AS conector,
               ci.id_equipo, ei.nombre AS equipo
        FROM matriz_ruteo m
        LEFT JOIN conector ci ON ci.id_conector = m.id_conector_entrada
        LEFT JOIN equipo ei ON ei.id_equipo = ci.id_equipo
        WHERE m.id_conector_salida = ?""", (id_conector,))), None)
    return c


# ── Cables y conexiones ──────────────────────────────────────────────────────

def cables_lista(incluir_internos=False):
    """Una fila por cable. Por defecto solo los externos (es_cable_conexion_interna
    nulo o 0), como VISTA_CABLES del desktop pero tolerando NULL."""
    filtro = "" if incluir_internos else "WHERE COALESCE(k.es_cable_conexion_interna,0) = 0"
    return _rows(f"""
        SELECT k.id_cable, k.codigo, k.longitud, k.unidad_longitud, k.estado,
               k.id_tipo_cable, tc.nombre AS tipo_cable,
               k.id_tipo_ficha, tf.nombre AS ficha,
               COALESCE(k.es_cable_conexion_interna,0) AS es_interno,
               (SELECT count(*) FROM conexion cx WHERE cx.id_cable = k.id_cable) AS n_conexiones
        FROM cable k
        LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = k.id_tipo_cable
        LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = k.id_tipo_ficha
        {filtro}
        ORDER BY lower(k.codigo), k.id_cable""")


def cable_ficha(id_cable):
    """Ficha de un cable (A.4): datos y sus extremos (conexión → conector → equipo)."""
    k = _one("""
        SELECT k.*, tc.nombre AS tipo_cable, tf.nombre AS ficha
        FROM cable k
        LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = k.id_tipo_cable
        LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = k.id_tipo_ficha
        WHERE k.id_cable = ?""", (id_cable,))
    if k is None:
        raise ValueError(f"No existe el cable {id_cable}")
    k["extremos"] = _rows("""
        SELECT cx.id_conexion, cx.es_conexion_interna, cx.es_armado_correcto, cx.detalle_armado,
               cx.id_conector, c.nombre AS conector, tc.nombre AS tipo_conector,
               tf.nombre AS ficha_conexion, c.id_equipo, e.nombre AS equipo
        FROM conexion cx
        LEFT JOIN conector c ON c.id_conector = cx.id_conector
        LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = cx.id_tipo_ficha
        LEFT JOIN equipo e ON e.id_equipo = c.id_equipo
        WHERE cx.id_cable = ? ORDER BY cx.id_conexion""", (id_cable,))
    return k


def conexiones_lista(solo_externas=True, id_equipo=None, id_cable=None):
    """Una fila por conexión (un extremo de un cable). Filtros opcionales por
    equipo o cable. `solo_externas` replica VISTA_CONEXIONES (excluye internas)."""
    where, params = [], []
    if solo_externas:
        where.append("COALESCE(cx.es_conexion_interna,0) = 0")
    if id_equipo is not None:
        where.append("c.id_equipo = ?"); params.append(id_equipo)
    if id_cable is not None:
        where.append("cx.id_cable = ?"); params.append(id_cable)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    return _rows(f"""
        SELECT cx.id_conexion, cx.id_cable, k.codigo AS cable,
               cx.id_conector, c.nombre AS conector, tc.nombre AS tipo_conector,
               c.id_equipo, e.nombre AS equipo,
               COALESCE(cx.es_conexion_interna,0) AS es_interna
        FROM conexion cx
        LEFT JOIN cable k ON k.id_cable = cx.id_cable
        LEFT JOIN conector c ON c.id_conector = cx.id_conector
        LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        LEFT JOIN equipo e ON e.id_equipo = c.id_equipo
        {w}
        ORDER BY lower(k.codigo), cx.id_conexion""", params)


# ── Salas, racks, frames y slots ─────────────────────────────────────────────

def salas_lista():
    return _rows("""
        SELECT s.id_sala, s.nombre,
               (SELECT count(*) FROM rack_por_sala rs WHERE rs.id_sala = s.id_sala) AS n_racks
        FROM sala s ORDER BY lower(s.nombre), s.id_sala""")


def sala_ficha(id_sala):
    s = _one("SELECT id_sala, nombre FROM sala WHERE id_sala = ?", (id_sala,))
    if s is None:
        raise ValueError(f"No existe la sala {id_sala}")
    s["racks"] = _rows("""
        SELECT r.id_rack, r.numero, r.nombre, r.cantidad_maxima,
               (SELECT count(*) FROM posicion_en_rack p WHERE p.id_rack = r.id_rack) AS n_posiciones
        FROM rack_por_sala rs JOIN rack r ON r.id_rack = rs.id_rack
        WHERE rs.id_sala = ? ORDER BY r.numero, r.id_rack""", (id_sala,))
    return s


def racks_lista():
    return _rows("""
        SELECT r.id_rack, r.numero, r.nombre, r.cantidad_maxima,
               (SELECT group_concat(s.nombre, ', ') FROM rack_por_sala rs
                  JOIN sala s ON s.id_sala = rs.id_sala WHERE rs.id_rack = r.id_rack) AS sala,
               (SELECT count(*) FROM posicion_en_rack p WHERE p.id_rack = r.id_rack) AS n_posiciones
        FROM rack r ORDER BY r.numero, r.id_rack""")


def rack_ficha(id_rack):
    """Rack con sus posiciones ordenadas por orificio (equivale a 'RACKS CON EQUIPOS').
    `tipo` es 'FRAME' si la posición aloja un frame, si no 'EQUIPO'."""
    r = _one("SELECT id_rack, numero, nombre, cantidad_maxima FROM rack WHERE id_rack = ?", (id_rack,))
    if r is None:
        raise ValueError(f"No existe el rack {id_rack}")
    r["salas"] = _rows("""
        SELECT s.id_sala, s.nombre FROM rack_por_sala rs JOIN sala s ON s.id_sala = rs.id_sala
        WHERE rs.id_rack = ? ORDER BY s.id_sala""", (id_rack,))
    r["posiciones"] = _rows("""
        SELECT p.id_posicion_en_rack, p.orificio_posicion_equipo_en_rack AS orificio,
               p.unidades_de_rack_equipo AS unidades,
               CASE WHEN p.id_frame IS NOT NULL THEN 'FRAME' ELSE 'EQUIPO' END AS tipo,
               p.id_equipo, p.id_frame,
               CASE WHEN p.id_frame IS NOT NULL THEN f.nombre ELSE e.nombre END AS dispositivo,
               CASE WHEN p.id_frame IS NOT NULL THEN f.num_inventario ELSE e.num_inventario END AS inventario
        FROM posicion_en_rack p
        LEFT JOIN equipo e ON e.id_equipo = p.id_equipo
        LEFT JOIN frame f ON f.id_frame = p.id_frame
        WHERE p.id_rack = ?
        ORDER BY p.orificio_posicion_equipo_en_rack, p.id_posicion_en_rack""", (id_rack,))
    return r


def frames_lista():
    return _rows("""
        SELECT f.id_frame, f.nombre, m.nombre AS marca, f.modelo,
               f.num_inventario AS inventario, f.id_marca, f.id_imagen,
               (SELECT count(*) FROM slot s WHERE s.id_frame = f.id_frame) AS n_slots
        FROM frame f LEFT JOIN marca m ON m.id_marca = f.id_marca
        ORDER BY lower(f.nombre), f.id_frame""")


def slots_lista(id_frame=None):
    """Slots (todos, o los de un frame) con el equipo que alojan."""
    w, p = ("WHERE s.id_frame = ?", (id_frame,)) if id_frame is not None else ("", ())
    return _rows(f"""
        SELECT s.id_slot, s.nombre, s.id_frame, f.nombre AS frame,
               s.id_equipo, e.nombre AS equipo, s.id_imagen, i.path_archivo AS imagen_path,
               s.rectangulo_x_en_imagen AS x, s.rectangulo_y_en_imagen AS y,
               s.rectangulo_ancho_pixeles AS ancho, s.rectangulo_alto_pixeles AS alto
        FROM slot s
        LEFT JOIN frame f ON f.id_frame = s.id_frame
        LEFT JOIN equipo e ON e.id_equipo = s.id_equipo
        LEFT JOIN imagen i ON i.id_imagen = s.id_imagen
        {w} ORDER BY s.id_frame, s.id_slot""", p)


def frame_ficha(id_frame):
    """Frame con su imagen, ubicación en rack y slots (rectángulos en píxeles de la imagen)."""
    f = _one("""
        SELECT f.*, m.nombre AS marca, i.path_archivo AS imagen_path,
               i.mm_por_pixel AS imagen_mm_por_pixel
        FROM frame f
        LEFT JOIN marca m ON m.id_marca = f.id_marca
        LEFT JOIN imagen i ON i.id_imagen = f.id_imagen
        WHERE f.id_frame = ?""", (id_frame,))
    if f is None:
        raise ValueError(f"No existe el frame {id_frame}")
    f["racks"] = _rows("""
        SELECT p.id_rack, r.nombre AS rack, r.numero AS rack_numero,
               p.orificio_posicion_equipo_en_rack AS orificio, p.unidades_de_rack_equipo AS unidades
        FROM posicion_en_rack p LEFT JOIN rack r ON r.id_rack = p.id_rack
        WHERE p.id_frame = ?""", (id_frame,))
    f["slots"] = slots_lista(id_frame)
    return f


def firmas():
    """Argumentos de cada función: {nombre: [{nombre, requerido, defecto}]}.
    La página lo usa para prellenar los argumentos al elegir una función."""
    out = {}
    for n, f in FUNCIONES.items():
        out[n] = [{"nombre": p.name, "requerido": p.default is inspect.Parameter.empty,
                   "defecto": None if p.default is inspect.Parameter.empty else p.default}
                  for p in inspect.signature(f).parameters.values()]
    return out


# ── Despachador ──────────────────────────────────────────────────────────────

FUNCIONES = {f.__name__: f for f in (
    resumen, catalogos,
    equipos_lista, arbol_equipos, equipo_ficha, conector_ficha,
    cables_lista, cable_ficha, conexiones_lista,
    salas_lista, sala_ficha, racks_lista, rack_ficha,
    frames_lista, slots_lista, frame_ficha,
)}



FUNCIONES["firmas"] = firmas


def call(fn, args_json="{}"):
    """Punto de entrada único desde JS. Nunca levanta: devuelve siempre un JSON."""
    t = time.perf_counter()
    try:
        if fn not in FUNCIONES:
            raise KeyError(f"Función desconocida: {fn}")
        args = json.loads(args_json) if args_json else {}
        if not isinstance(args, dict):
            raise ValueError("Los argumentos deben ser un objeto JSON, ej. {\"id_equipo\": 1}")
        params = inspect.signature(FUNCIONES[fn]).parameters
        sobran = sorted(set(args) - set(params))
        faltan = sorted(n for n, p in params.items()
                        if p.default is inspect.Parameter.empty and n not in args)
        if sobran or faltan:
            validos = ", ".join(n + ("" if p.default is inspect.Parameter.empty else " (opcional)")
                                for n, p in params.items()) or "ninguno"
            raise ValueError(f"{fn}: " + (f"no acepta {sobran}; " if sobran else "")
                             + (f"falta {faltan}; " if faltan else "")
                             + f"argumentos válidos: {validos}")
        data = FUNCIONES[fn](**args)
        return json.dumps({"ok": True, "data": data,
                           "ms": round((time.perf_counter() - t) * 1000, 1)},
                          ensure_ascii=False, default=str)
    except Exception as ex:  # noqa: BLE001 — se informa a la UI, no se oculta
        return json.dumps({"ok": False, "error": f"{type(ex).__name__}: {ex}",
                           "ms": round((time.perf_counter() - t) * 1000, 1)},
                          ensure_ascii=False)
