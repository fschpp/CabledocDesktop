"""CableDoc Web — capa JSON de lectura (plan_pyodide_v1.md, Fase A.1).

Un método por pantalla; la UI nunca ve `Modelo` crudo. Todas las funciones
devuelven estructuras JSON-serializables (dict/list de str, int, float, None)
y se invocan desde JS a través de `call(nombre, args_json)`, que siempre
devuelve un string JSON `{"ok": true, "data": ..., "ms": n}` o
`{"ok": false, "error": "..."}` — nunca levanta excepciones hacia JS.

Este archivo es de solo lectura: no hay INSERT/UPDATE/DELETE acá. La escritura (Fase B) vive en módulos
aparte que se registran al final (B.2: `catalogos_web.py`) y marcan sus respuestas con `"escribio": true`
para que el worker persista la base (syncfs) antes de contestar.

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


# ── Árbol de conexiones y cadena de extensiones (A.5) ────────────────────────

def conexiones_equipo(id_equipo):
    """Un nivel del árbol de conexiones (carga perezosa, como ArbolConexionesEquipo
    del desktop): los cables de un equipo y, bajo cada cable, el equipo del otro
    extremo. Sale de CONEXIONES_AMBOS_EXTREMOS (mismas filas que el desktop).

    Columnas de la vista (por posición, porque `id_equipo` y `id_conector` salen
    dos veces): 0 cable · 5 equipo consultado · 7 conector del consultado ·
    1 equipo del otro extremo · 3 su conector · 9 id consultado · 10 id otro
    extremo · 11 id_cable · 13 id_conector consultado · 14 id_conector otro
    extremo. Un mismo equipo destino aparece una sola vez por cable.
    `id_equipo_destino` es None si el otro extremo no tiene equipo (id 0/NULL):
    esa hoja no se puede expandir.
    """
    with _M()._conn_ctx() as conn:
        e = conn.execute("SELECT nombre FROM equipo WHERE id_equipo = ?", (id_equipo,)).fetchone()
        if e is None:
            raise ValueError(f"No existe el equipo {id_equipo}")
        filas = conn.execute(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo = ?", (id_equipo,)).fetchall()
    cables, por_id = [], {}
    for r in filas:
        id_cable = r[11]
        k = por_id.get(id_cable)
        if k is None:
            k = por_id[id_cable] = {"id_cable": id_cable, "codigo": (r[0] or "").strip() or "?",
                                    "conexiones": []}
            cables.append(k)
        dest = r[10] if r[10] not in (None, 0, "", "0") else None
        if any(c["id_equipo_destino"] == dest and c["equipo_destino"] == r[1] for c in k["conexiones"]):
            continue
        k["conexiones"].append({
            "id_conector_local": r[13], "conector_local": r[7],
            "id_conector_destino": r[14], "conector_destino": r[3],
            "id_equipo_destino": dest, "equipo_destino": r[1]})
    return {"id_equipo": id_equipo, "equipo": e["nombre"], "n_conexiones": len(filas), "cables": cables}


def cadena_extension(id_cable):
    """Recorrido completo equipo → cable → extensión → cable → … → equipo a partir
    de un cable cualquiera de la cadena (A.5). Misma lógica y mismos eslabones que
    `Modelo.resolver_cadena_extension` (el test_bridge los compara), pero sin
    `asegurar_tablas_extension_cable()`, que escribe: acá solo se lee, y si la
    base es vieja y no tiene `extension_cable` no hay extensiones y la cadena es
    solo el cable.

    Eslabones (ordenados de un extremo real al otro):
      {tipo: "equipo", equipo, conector, id_equipo, id_conector}
      {tipo: "cable", id_cable, codigo, foco}      (foco = el cable de partida)
      {tipo: "extension", id_extension, posicion, armado}   (armado: 1 / 0 / None)
      {tipo: "suelto"}  punta sin conector ni extensión (cadena incompleta)
      {tipo: "ciclo"}   protección ante referencia circular
    Devuelve [] si el cable no tiene conexiones.
    """
    def terminal(id_conexion):
        r = _one("SELECT equipo_nombre, conector_nombre, id_equipo, id_conector "
                 "FROM CONEXIONES WHERE id_conexion = ?", (id_conexion,))
        if r and r["equipo_nombre"]:
            return {"tipo": "equipo", "equipo": r["equipo_nombre"], "conector": r["conector_nombre"],
                    "id_equipo": r["id_equipo"], "id_conector": r["id_conector"]}
        return None

    def extension_de(id_conexion):
        r = _rows_opt("SELECT id_extension, id_conexion_a, id_conexion_b, posicion_libre, es_armado_correcto "
                      "FROM extension_cable WHERE id_conexion_a = ? OR id_conexion_b = ?",
                      (id_conexion, id_conexion))
        return r[0] if r else None

    def codigo(id_cab):
        r = _one("SELECT codigo FROM cable WHERE id_cable = ?", (id_cab,))
        return r["codigo"] if r else ""

    def seguir(cx_actual, visitados):
        lado = []
        while True:
            fila = _one("SELECT id_conector FROM conexion WHERE id_conexion = ?", (cx_actual,))
            if fila and fila["id_conector"]:
                lado.append(terminal(cx_actual) or {"tipo": "suelto"})
                break
            ext = extension_de(cx_actual)
            if not ext:
                lado.append({"tipo": "suelto"})
                break
            otro = ext["id_conexion_b"] if str(ext["id_conexion_a"]) == str(cx_actual) else ext["id_conexion_a"]
            lado.append({"tipo": "extension", "id_extension": ext["id_extension"],
                         "posicion": ext["posicion_libre"], "armado": ext["es_armado_correcto"]})
            sig = _one("SELECT id_cable FROM conexion WHERE id_conexion = ?", (otro,))
            id_sig = sig["id_cable"] if sig else None
            if not id_sig or id_sig in visitados:
                lado.append({"tipo": "ciclo"})
                break
            visitados.add(id_sig)
            lado.append({"tipo": "cable", "id_cable": id_sig, "codigo": codigo(id_sig), "foco": False})
            cand = [r["id_conexion"] for r in _rows(
                "SELECT id_conexion FROM conexion WHERE id_cable = ? ORDER BY id_conexion", (id_sig,))
                if str(r["id_conexion"]) != str(otro)]
            if not cand:
                lado.append({"tipo": "suelto"})
                break
            cx_actual = cand[0]
        return lado

    ext = [r["id_conexion"] for r in _rows(
        "SELECT id_conexion FROM conexion WHERE id_cable = ? ORDER BY id_conexion", (id_cable,))]
    if not ext:
        return []
    izq = seguir(ext[0], {id_cable})
    der = seguir(ext[1], {id_cable}) if len(ext) > 1 else []
    foco = {"tipo": "cable", "id_cable": id_cable, "codigo": codigo(id_cable), "foco": True}
    return list(reversed(izq)) + [foco] + der


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

# ── Ubicaciones: rack, frame/slots y patcheras (A.6) ─────────────────────────
# Son las mismas vistas que VistaRack, VistaFrameSlots y PatcherasVista (modo global) del desktop. Los datos se
# arman acá (la lógica de segmentos y de patchcords vive en la UI GTK, no en Modelo) y el JS solo dibuja en SVG.

def _int(v, defecto=0):
    """int tolerante: None, '' o basura → defecto (como los `int(x) if x else 0` de la UI GTK)."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return defecto


def ubicaciones():
    """Listado para la pantalla Ubicaciones: salas con sus racks, racks sin sala y frames (con su rack)."""
    racks = _rows("""
        SELECT r.id_rack, r.numero, r.nombre, r.cantidad_maxima,
               (SELECT count(*) FROM posicion_en_rack p WHERE p.id_rack = r.id_rack) AS n_posiciones
        FROM rack r ORDER BY r.numero, r.id_rack""")
    por_id = {r["id_rack"]: r for r in racks}
    salas = _rows("SELECT id_sala, nombre FROM sala ORDER BY lower(nombre), id_sala")
    en_sala = set()
    por_sala = {s["id_sala"]: [] for s in salas}
    for rel in _rows("SELECT id_sala, id_rack FROM rack_por_sala ORDER BY id_rack_x_sala"):
        if rel["id_sala"] in por_sala and rel["id_rack"] in por_id:
            por_sala[rel["id_sala"]].append(por_id[rel["id_rack"]])
            en_sala.add(rel["id_rack"])
    for s in salas:
        s["racks"] = por_sala[s["id_sala"]]
    frames = frames_lista()
    donde = {}
    for p in _rows("""
        SELECT p.id_frame, p.id_rack, r.nombre AS rack FROM posicion_en_rack p
        LEFT JOIN rack r ON r.id_rack = p.id_rack WHERE p.id_frame IS NOT NULL
        ORDER BY p.id_posicion_en_rack"""):
        donde.setdefault(p["id_frame"], []).append({"id_rack": p["id_rack"], "rack": p["rack"]})
    for f in frames:
        f["racks"] = donde.get(f["id_frame"], [])
    return {"salas": salas, "racks_sin_sala": [r for r in racks if r["id_rack"] not in en_sala], "frames": frames}


def _segmentos_rack(devs, cap):
    """Segmentos de un rack, igual que VistaRack._cargar: una fila por orificio (1 U = 3 orificios); varios
    dispositivos en los mismos orificios se funden en una bandeja. `devs`: dicts con orificio, ur, inventario,
    dispositivo, id_equipo, id_frame (las columnas de la vista 'RACKS CON EQUIPOS')."""
    u_map = {u: [] for u in range(1, cap + 1)}
    for d in devs:
        u_ini = _int(d["orificio"], 0) if d["orificio"] else 0
        u_count = (_int(d["ur"], 1) if d["ur"] else 1) * 3
        if u_ini < 1 or u_count < 1:
            continue
        info = {"nombre": str(d["dispositivo"] or "").strip() or "?", "inv": str(d["inventario"] or "").strip(),
                "tipo": "frame" if d["id_frame"] else "equipo", "u_ini": u_ini, "u_count": u_count,
                "id_equipo": d["id_equipo"] or None, "id_frame": d["id_frame"] or None}
        for u in range(u_ini, min(u_ini + u_count, cap + 1)):
            u_map[u].append(info)

    def estado(u):
        n = len(u_map[u])
        return "libre" if n == 0 else "single" if n == 1 else "bandeja"

    segs, hechas, u = [], set(), 1
    while u <= cap:
        if u in hechas:
            u += 1
            continue
        est = estado(u)
        if est == "libre":
            segs.append({"u_ini": u, "u_count": 1, "tipo": "libre", "nombre": "", "inv": ""})
            hechas.add(u)
            u += 1
        elif est == "bandeja":
            infos = u_map[u]
            clave = frozenset(i["nombre"] for i in infos)
            u_fin = u
            while u_fin + 1 <= cap and len(u_map[u_fin + 1]) >= 2 and frozenset(i["nombre"] for i in u_map[u_fin + 1]) == clave:
                u_fin += 1
            items, vistos = [], set()
            for i in infos:
                if i["nombre"] in vistos:
                    continue
                vistos.add(i["nombre"])
                items.append({"nombre": i["nombre"], "tipo": i["tipo"], "id": i["id_frame"] if i["tipo"] == "frame" else i["id_equipo"]})
            segs.append({"u_ini": u, "u_count": u_fin - u + 1, "tipo": "bandeja", "nombre": [i["nombre"] for i in items], "inv": "", "items": items})
            hechas.update(range(u, u_fin + 1))
            u = u_fin + 1
        else:
            main = u_map[u][0]
            fin_dispositivo = min(main["u_ini"] + main["u_count"] - 1, cap)
            fin = u
            for uu in range(u + 1, fin_dispositivo + 1):
                if uu in hechas or estado(uu) != "single" or u_map[uu][0]["nombre"] != main["nombre"]:
                    break
                fin = uu
            segs.append({"u_ini": u, "u_count": fin - u + 1, "tipo": main["tipo"], "nombre": main["nombre"], "inv": main["inv"],
                         "id": main["id_frame"] if main["tipo"] == "frame" else main["id_equipo"]})
            hechas.update(range(u, fin + 1))
            u = fin + 1
    segs.sort(key=lambda x: x["u_ini"])
    return segs


def rack_vista(id_rack):
    """Rack listo para dibujar (equivale a VistaRack): segmentos por orificio y resumen. Lee las mismas filas que
    Modelo.devolver_dispositivos_de_un_rack ('RACKS CON EQUIPOS')."""
    r = _one("SELECT id_rack, numero, nombre, cantidad_maxima FROM rack WHERE id_rack = ?", (id_rack,))
    if r is None:
        raise ValueError(f"No existe el rack {id_rack}")
    cap_u = max(1, _int(r["cantidad_maxima"], 42)) if r["cantidad_maxima"] not in (None, "") else 42
    cap = cap_u * 3
    devs = _rows("""
        SELECT p.id_posicion_en_rack AS id, p.orificio_posicion_equipo_en_rack AS orificio,
               p.unidades_de_rack_equipo AS ur,
               COALESCE(e.num_inventario, f.num_inventario, 'SIN INVENTARIO') AS inventario,
               COALESCE(e.nombre, f.nombre) AS dispositivo, e.id_equipo AS id_equipo, f.id_frame AS id_frame
        FROM posicion_en_rack p
        LEFT JOIN equipo e ON p.id_equipo = e.id_equipo AND p.id_frame IS NULL
        LEFT JOIN frame f ON p.id_frame = f.id_frame AND p.id_equipo IS NULL
        WHERE p.id_rack = ?
        ORDER BY p.orificio_posicion_equipo_en_rack, p.id_posicion_en_rack""", (id_rack,))
    segs = _segmentos_rack(devs, cap)
    r["cap_u"], r["cap"] = cap_u, cap
    r["salas"] = _rows("""
        SELECT s.id_sala, s.nombre FROM rack_por_sala rs JOIN sala s ON s.id_sala = rs.id_sala
        WHERE rs.id_rack = ? ORDER BY s.id_sala""", (id_rack,))
    r["segmentos"] = segs
    # Dispositivos que empiezan más allá del último orificio del rack: la vista del desktop los omite sin avisar.
    r["fuera_de_rango"] = [str(d["dispositivo"] or "?") for d in devs if _int(d["orificio"], 0) > cap]
    r["resumen"] = {
        "asignaciones": len(devs),
        "equipos": sum(1 for s in segs if s["tipo"] == "equipo"),
        "frames": sum(1 for s in segs if s["tipo"] == "frame"),
        "bandejas": sum(1 for s in segs if s["tipo"] == "bandeja"),
        "libres": sum(s["u_count"] for s in segs if s["tipo"] == "libre"),
    }
    return r


def frame_vista(id_frame):
    """Frame listo para dibujar (equivale a VistaFrameSlots): imagen y rectángulos de slots en píxeles de la imagen,
    numerados en el orden del desktop (por nombre de slot). `color` es el índice de paleta de los slots con equipo
    (en orden de aparición); los vacíos van sin color. Rectángulo sin medida → 50×30, como en el desktop."""
    f = _one("""
        SELECT f.id_frame, f.nombre, f.num_inventario AS inventario, f.modelo, m.nombre AS marca,
               i.path_archivo AS imagen_path, f.ancho_mm, f.alto_mm, f.profundidad_mm
        FROM frame f LEFT JOIN marca m ON m.id_marca = f.id_marca LEFT JOIN imagen i ON i.id_imagen = f.id_imagen
        WHERE f.id_frame = ?""", (id_frame,))
    if f is None:
        raise ValueError(f"No existe el frame {id_frame}")
    filas = _rows("""
        SELECT s.id_slot, s.nombre, s.id_equipo, COALESCE(e.nombre, '') AS equipo,
               COALESCE(s.rectangulo_x_en_imagen, 0) AS x, COALESCE(s.rectangulo_y_en_imagen, 0) AS y,
               COALESCE(s.rectangulo_ancho_pixeles, 50) AS ancho, COALESCE(s.rectangulo_alto_pixeles, 30) AS alto,
               COALESCE(img_s.path_archivo, '') AS imagen_slot
        FROM slot s LEFT JOIN equipo e ON e.id_equipo = s.id_equipo LEFT JOIN imagen img_s ON img_s.id_imagen = s.id_imagen
        WHERE s.id_frame = ? ORDER BY s.nombre, s.id_slot""", (id_frame,))
    # Una sola imagen, como en el desktop: la del frame o, si no tiene, la primera de un slot.
    if not (f["imagen_path"] or "").strip():
        f["imagen_path"] = next((r["imagen_slot"].strip() for r in filas if r["imagen_slot"].strip()), None)
    slots, color = [], 0
    for n, r in enumerate(filas, 1):
        con_equipo = bool(r["id_equipo"])
        slots.append({"num": n, "id_slot": r["id_slot"], "nombre": r["nombre"], "id_equipo": r["id_equipo"] or None,
                      "equipo": r["equipo"], "x": _int(r["x"]), "y": _int(r["y"]),
                      "ancho": _int(r["ancho"], 50) if _int(r["ancho"], 50) > 0 else 50,
                      "alto": _int(r["alto"], 30) if _int(r["alto"], 30) > 0 else 30,
                      "color": color if con_equipo else None})
        color += 1 if con_equipo else 0
    f["slots"] = slots
    f["racks"] = _rows("""
        SELECT p.id_rack, r.nombre AS rack, r.numero AS rack_numero,
               p.orificio_posicion_equipo_en_rack AS orificio, p.unidades_de_rack_equipo AS unidades
        FROM posicion_en_rack p LEFT JOIN rack r ON r.id_rack = p.id_rack
        WHERE p.id_frame = ? ORDER BY p.id_posicion_en_rack""", (id_frame,))
    return f


def patcheras_global():
    """Todas las patcheras del sistema (equivale a PatcherasVista en modo global): racks → frames → columnas.
    Cada columna es un módulo (equipo con rol_senal PATCHERA) instalado en un slot cuyo nombre trae el número de
    columna. Fila A = BACK_ENTRADA / FRONT_DERIVACION, fila B = BACK_SALIDA / FRONT_INSERCION (por función de
    patchera, nunca por nombre). `color` es un índice de paleta por equipo conectado (None = fantasma o vacío);
    `jumpers` son los patchcords del frente (tipo 'curva' si unen dos módulos del mismo rack, si no 'cabo')."""
    import re

    slots = _rows_opt("""
        SELECT DISTINCT r.id_rack, r.nombre AS rack, f.id_frame, f.nombre AS frame,
               s.id_slot, s.nombre AS slot, s.id_equipo, e.nombre AS modulo
        FROM rack r
        JOIN posicion_en_rack pr ON pr.id_rack = r.id_rack
        JOIN frame f ON f.id_frame = pr.id_frame
        JOIN slot s ON s.id_frame = f.id_frame
        JOIN equipo e ON e.id_equipo = s.id_equipo
        JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
        WHERE te.rol_senal = 'PATCHERA'
        ORDER BY r.nombre, r.id_rack, f.nombre, f.id_frame, s.nombre, s.id_slot""")
    racks, ubic = {}, {}                      # id_rack → {…, frames: {id_frame → {…, cols: {col → celda}}}} ; id_equipo → (rack, frame, col)

    def vacio():
        return {"estado": "vacio", "id_equipo": None, "nombre": None, "conector": None, "color": None}

    for s in slots:
        m = re.findall(r"\d+", str(s["slot"] or ""))
        col = int(m[0]) if m else 0
        if col == 0:
            continue
        ubic[s["id_equipo"]] = (s["id_rack"], s["id_frame"], col)
        rk = racks.setdefault(s["id_rack"], {"id_rack": s["id_rack"], "rack": s["rack"], "frames": {}})
        fr = rk["frames"].setdefault(s["id_frame"], {"id_frame": s["id_frame"], "frame": s["frame"], "cols": {}})
        fr["cols"].setdefault(col, {"col": col, "id_equipo": s["id_equipo"], "modulo": s["modulo"], "A": vacio(), "B": vacio(),
                                    "front": {"A": {**vacio(), "es_jumper": False, "destino": None},
                                              "B": {**vacio(), "es_jumper": False, "destino": None}}})

    conex = _rows_opt("""
        SELECT c1.id_conector AS id_con1, c1.id_equipo AS id_modulo, e2.id_equipo AS id_eq2, e2.nombre AS eq2,
               c2.nombre AS con2, te2.rol_senal AS rol2, fp1.clave AS clave1, fp2.clave AS clave2
        FROM conector c1
        JOIN equipo e1 ON e1.id_equipo = c1.id_equipo
        JOIN tipo_equipo te1 ON te1.id_tipo_equipo = e1.id_tipo_equipo
        JOIN conexion cx1 ON cx1.id_conector = c1.id_conector
        JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable AND cx2.id_conector != cx1.id_conector
        JOIN conector c2 ON c2.id_conector = cx2.id_conector
        JOIN equipo e2 ON e2.id_equipo = c2.id_equipo
        JOIN tipo_equipo te2 ON te2.id_tipo_equipo = e2.id_tipo_equipo
        LEFT JOIN funcion_patchera fp1 ON fp1.id_funcion_patchera = c1.id_funcion_patchera
        LEFT JOIN funcion_patchera fp2 ON fp2.id_funcion_patchera = c2.id_funcion_patchera
        WHERE te1.rol_senal = 'PATCHERA' AND c1.id_funcion_patchera IS NOT NULL
        ORDER BY c1.id_equipo, c1.id_conector, cx2.id_conector""")
    colores = {}                              # id_equipo conectado → índice de paleta, por orden de aparición

    def color_de(id_eq):
        return colores.setdefault(id_eq, len(colores))

    for c in conex:
        if c["id_modulo"] not in ubic or c["clave1"] is None:
            continue                           # módulo fuera de un slot con número / conector sin función asignada
        id_rack, id_frame, col = ubic[c["id_modulo"]]
        celda = racks[id_rack]["frames"][id_frame]["cols"][col]
        fila = "A" if c["clave1"] in ("BACK_ENTRADA", "FRONT_DERIVACION") else "B"
        fantasma = str(c["rol2"] or "").upper() == "FANTASMA"
        estado, color = ("fantasma", None) if fantasma else ("conectado", color_de(c["id_eq2"]))
        dato = {"estado": estado, "id_equipo": c["id_eq2"], "nombre": c["eq2"], "conector": c["con2"], "color": color}
        if c["clave1"] in ("BACK_ENTRADA", "BACK_SALIDA"):
            celda[fila] = dato
        elif c["clave1"] in ("FRONT_DERIVACION", "FRONT_INSERCION"):
            es_jumper = (str(c["rol2"] or "").upper() == "PATCHERA" and c["clave2"] in ("FRONT_DERIVACION", "FRONT_INSERCION")
                         and c["id_eq2"] in ubic)
            destino = None
            if es_jumper:
                d_rack, d_frame, d_col = ubic[c["id_eq2"]]
                destino = {"id_rack": d_rack, "id_frame": d_frame, "col": d_col,
                           "row": "A" if c["clave2"] in ("BACK_ENTRADA", "FRONT_DERIVACION") else "B"}
            celda["front"][fila] = {**dato, "es_jumper": es_jumper, "destino": destino}

    jumpers, vistos = [], set()
    for rk in racks.values():
        for fr in rk["frames"].values():
            for col, celda in fr["cols"].items():
                for fila in ("A", "B"):
                    fr_ = celda["front"][fila]
                    if fr_["estado"] == "vacio":
                        continue
                    origen = (rk["id_rack"], fr["id_frame"], col, fila)
                    p1 = {"id_rack": rk["id_rack"], "id_frame": fr["id_frame"], "col": col, "row": fila}
                    if fr_["es_jumper"] and fr_["destino"]:
                        d = fr_["destino"]
                        par = frozenset({origen, (d["id_rack"], d["id_frame"], d["col"], d["row"])})
                        if par in vistos:
                            continue          # el otro extremo ya lo dibujó
                        vistos.add(par)
                        mismo = d["id_rack"] == rk["id_rack"]
                        jumpers.append({"tipo": "curva" if mismo else "cabo", "cruza_rack": not mismo, "p1": p1, "p2": d, "color": fr_["color"],
                                        "texto": f"{fr_['nombre']} ({fr_['conector']})"})
                    else:
                        jumpers.append({"tipo": "cabo", "cruza_rack": False, "p1": p1, "p2": None, "color": fr_["color"],
                                        "fantasma": fr_["estado"] == "fantasma", "texto": f"{fr_['nombre']} ({fr_['conector']})"})

    salida = []
    for rk in sorted(racks.values(), key=lambda r: (str(r["rack"] or "").lower(), r["id_rack"])):
        frames = [{"id_frame": f["id_frame"], "frame": f["frame"], "columnas": [f["cols"][c] for c in sorted(f["cols"])]}
                  for f in sorted(rk["frames"].values(), key=lambda f: (str(f["frame"] or "").lower(), f["id_frame"]))]
        salida.append({"id_rack": rk["id_rack"], "rack": rk["rack"], "frames": frames})
    celdas = [c for rk in salida for f in rk["frames"] for c in f["columnas"]]
    return {
        "racks": salida, "jumpers": jumpers,
        "max_col": max((c["col"] for c in celdas), default=24),
        "resumen": {"racks": len(salida), "patcheras": sum(len(r["frames"]) for r in salida), "equipos": len(colores),
                    "fantasma": sum(1 for c in celdas for f in ("A", "B") if c[f]["estado"] == "fantasma")},
    }


# ── Análisis (A.7): impacto, IRF, diagnóstico de falla y linter de topología ─
#
# Todo es de solo lectura (no se persiste nada, ni siquiera el caché de riesgo).
# Los motores de core/ trabajan con ids `str`; acá se convierten a int en la
# frontera (el resto del bridge usa int tal cual SQLite).

def _id(v):
    """'12' -> 12 (ids de los motores de core/ vuelven como str)."""
    return int(v) if isinstance(v, str) and v.isdigit() else v


def _db_path():
    from core import modelo
    return modelo.DB_PATH


def _grafo():
    from core.graph_impact import GraphImpactAnalyzer
    g = GraphImpactAnalyzer(_db_path())
    g.construir_grafo()
    return g


def _resultado_impacto(g, tipo, id_origen, nombre, r):
    """Normaliza ResultadoImpacto / ResultadoImpactoEquipo a un dict JSON."""
    finales = set(getattr(r, "puntos_finales_impactados", ()) or ())
    equipos = sorted(({"id_equipo": _id(e), "nombre": g.nombre_equipo(e), "punto_final": e in finales}
                      for e in r.equipos_impactados), key=lambda x: (x["nombre"].lower(), x["id_equipo"]))
    cables = sorted(({"id_cable": _id(c), "codigo": g.nombre_cable(c)} for c in r.cables_impactados),
                    key=lambda x: (str(x["codigo"]).lower(), x["id_cable"]))
    causas = sorted(({"id_equipo": _id(e), "nombre": g.nombre_equipo(e), "texto": txt}
                     for e, txt in (r.causas_regla or {}).items()), key=lambda x: x["nombre"].lower())
    total, total_finales = g.totales()
    return {"origen": {"tipo": tipo, "id": id_origen, "nombre": nombre},
            "total_equipos": total, "total_puntos_finales": total_finales,
            "n_impactados": len(equipos), "n_puntos_finales": len(finales),
            "porcentaje": round(100.0 * len(equipos) / total, 1) if total else 0.0,
            "equipos_impactados": equipos, "cables_impactados": cables, "causas_regla": causas}


def impacto_cable(id_cable):
    """Qué equipos quedan sin señal si se corta este cable (GraphImpactAnalyzer.simular_desconexion)."""
    if _one("SELECT 1 AS x FROM cable WHERE id_cable = ?", (id_cable,)) is None:
        raise ValueError(f"No existe el cable {id_cable}")
    g = _grafo()
    r = g.simular_desconexion(str(id_cable))
    return _resultado_impacto(g, "cable", id_cable, g.nombre_cable(str(id_cable)), r)


def impacto_equipo(id_equipo):
    """Qué otros equipos quedan sin señal si este equipo falla por completo."""
    if _one("SELECT 1 AS x FROM equipo WHERE id_equipo = ?", (id_equipo,)) is None:
        raise ValueError(f"No existe el equipo {id_equipo}")
    g = _grafo()
    r = g.simular_falla_equipo(str(id_equipo))
    return _resultado_impacto(g, "equipo", id_equipo, g.nombre_equipo(str(id_equipo)), r)


def impacto_rack(id_rack):
    """Qué equipos quedan sin señal si se pierde el rack completo (energía, incendio, etc.)."""
    rack = _one("SELECT nombre FROM rack WHERE id_rack = ?", (id_rack,))
    if rack is None:
        raise ValueError(f"No existe el rack {id_rack}")
    g = _grafo()
    r = g.simular_perdida_rack(str(id_rack))
    return _resultado_impacto(g, "rack", id_rack, rack["nombre"] or f"Rack #{id_rack}", r)


def riesgo_irf():
    """IRF de todos los equipos, calculado en el momento y SIN persistir (persistir=False).
    Tarda ~3 s en wasm con la base real: correr siempre desde el worker."""
    from core import risk_engine as re_
    t0 = time.perf_counter()
    res = re_.RiskEngine(_db_path()).calcular_todos(persistir=False)
    nombres = {str(r["id_equipo"]): r for r in _rows(
        "SELECT e.id_equipo, e.nombre, t.nombre AS tipo FROM equipo e "
        "LEFT JOIN tipo_equipo t ON t.id_tipo_equipo = e.id_tipo_equipo")}
    filas = []
    for k, v in res.items():
        n = nombres.get(str(k), {})
        p, i = v["probabilidad"], v["impacto"]
        filas.append({"id_equipo": _id(k), "nombre": n.get("nombre") or f"Equipo #{k}", "tipo": n.get("tipo"),
                      "probabilidad": p, "impacto": i, "riesgo": v["riesgo"], "nivel": v["nivel"],
                      "cuadrante": ("alto" if p >= re_.UMBRAL_CUADRANTE else "bajo") + "/"
                                   + ("alto" if i >= re_.UMBRAL_CUADRANTE else "bajo"),
                      "detalle": v["detalle"]})
    filas.sort(key=lambda f: (-f["riesgo"], -f["impacto"], f["nombre"].lower()))
    det = filas[0]["detalle"] if filas else {}
    return {"filas": filas, "umbral_cuadrante": re_.UMBRAL_CUADRANTE,
            "niveles": [{"desde": d, "nivel": n} for d, n, _c in re_.NIVELES],
            "modo_impacto": det.get("modo_impacto", "todos"), "grafo_disponible": det.get("grafo_disponible", True),
            "calculo_ms": round((time.perf_counter() - t0) * 1000, 1)}


def conectores_de_equipo(id_equipo):
    """Nombre del equipo y sus conectores (liviano, para elegir el síntoma del diagnóstico)."""
    eq = _one("SELECT id_equipo, nombre FROM equipo WHERE id_equipo = ?", (id_equipo,))
    if eq is None:
        raise ValueError(f"No existe el equipo {id_equipo}")
    eq["conectores"] = _rows("""
        SELECT c.id_conector, c.nombre, tc.nombre AS tipo_conector,
               (SELECT count(*) FROM conexion cx WHERE cx.id_conector = c.id_conector) AS n_conexiones
        FROM conector c LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
        WHERE c.id_equipo = ? ORDER BY c.id_conector""", (id_equipo,))
    return eq


def _paso(p):
    return {"id_conector": _id(p.id_conector), "nombre": p.nombre, "id_equipo": _id(p.id_equipo),
            "equipo": p.nombre_equipo, "es_punto_test": bool(p.es_punto_test)}


def diagnostico(id_conector, ramas=None, respuestas=None):
    """Asistente de diagnóstico sin estado: se rearma la cadena y se repiten las respuestas.
    ramas: {id_equipo: id_conector_entrada} para resolver bifurcaciones ya elegidas.
    respuestas: [[indice, 'SI'|'NO'|'NO_SE'], ...] en orden (deshacer = sacar la última)."""
    from core.diagnostico_falla import MotorDiagnostico, SesionDiagnostico
    if _one("SELECT 1 AS x FROM conector WHERE id_conector = ?", (id_conector,)) is None:
        raise ValueError(f"No existe el conector {id_conector}")
    ramas = {str(k): str(v) for k, v in (ramas or {}).items()}
    cad = MotorDiagnostico(_db_path()).construir_cadena(str(id_conector), ramas)
    pasos = [_paso(p) for p in cad.pasos]
    bif = None
    if cad.bifurcacion is not None:
        b = cad.bifurcacion
        bif = {"id_equipo": _id(b.id_equipo), "equipo": b.nombre_equipo,
               "opciones": [{"id_conector": _id(c), "nombre": n} for c, n in b.opciones]}
    out = {"pasos": pasos, "motivo_corte": cad.motivo_corte, "categoria_corte": cad.categoria_corte,
           "bifurcacion": bif, "sesion": None}
    if len(cad.pasos) < 2:
        return out
    ses = SesionDiagnostico(cad.pasos)
    for item in (respuestas or []):
        indice, resp = item
        ses.responder(int(indice), resp)
    sig = ses.siguiente_punto()
    res = None
    if ses.convergido():
        sin, con = ses.resultado()
        res = {"sin_senal": _paso(sin), "con_senal": _paso(con),
               "sospechoso": "equipo" if sin.id_equipo == con.id_equipo else "cable"}
    out["sesion"] = {"lo": ses.lo, "hi": ses.hi, "convergido": ses.convergido(),
                     "siguiente": sig[0] if sig else None,
                     "historial": [[i, r] for i, r in ses.historial], "resultado": res}
    return out


def linter_topologia():
    """Las 4 reglas del linter de topología, cada una ya priorizada por riesgo (core/linter_topologia.py).
    El orden usa el riesgo CACHEADO en la base (riesgo_equipo_cache): sin él, `con_riesgo` es False."""
    from core import linter_topologia as lt
    db = _db_path()

    def planos(filas):
        out = []
        for f in filas:
            d = {k: v for k, v in f.items() if not k.startswith("_")}
            for k in ("id_equipo", "id_conector", "id_conector_origen"):
                if k in d:
                    d[k] = _id(d[k])
            if isinstance(d.get("destinos"), list):
                d["destinos"] = [{**x, "id_equipo": _id(x.get("id_equipo"))} for x in d["destinos"]]
            out.append(d)
        return out

    reglas = [("fuera_de_patchera", lt.equipos_fuera_de_patchera_priorizados),
              ("fuera_de_distribuidor", lt.equipos_fuera_de_distribuidor_priorizados),
              ("loop_en_uso", lt.loops_en_uso_priorizados),
              ("referencia_en_cascada", lt.referencia_en_cascada_priorizada)]
    out = [{"id": rid, "hallazgos": planos(fn(db))} for rid, fn in reglas]
    con_riesgo = any(h.get("riesgo") is not None for r in out for h in r["hallazgos"])
    return {"reglas": out, "con_riesgo": con_riesgo}


# ── Escenarios (A.8): abrir y evaluar ────────────────────────────────────────
# Solo lectura: no se crea, edita, aplica ni cambia de estado nada (eso es B.11). Las tablas `escenario` y
# `escenario_cambio` se leen con _rows_opt: en una base que nunca las creó la lista sale vacía y NO se
# crean (Modelo.asegurar_tablas_escenario escribiría en la base). La evaluación corre el motor real
# (core/escenario_engine.Escenario.evaluar) sobre un escenario que ya existe, así que ese asegurar es un no-op.

_ESCENARIO_COLS = ("id_escenario", "nombre", "descripcion", "estado", "fecha_creacion", "fecha_ultima_edicion")


def _escenario_fila(id_escenario):
    f = _rows_opt("SELECT id_escenario, nombre, COALESCE(descripcion,'') AS descripcion, estado, "
                  "fecha_creacion, fecha_ultima_edicion FROM escenario WHERE id_escenario = ?", (id_escenario,))
    if not f:
        raise ValueError(f"No existe el escenario {id_escenario}")
    return f[0]


def _cambios_escenario(id_escenario):
    """Cambios del escenario con los nombres ya resueltos (mismo orden que Modelo.devolver_cambios_de_escenario)."""
    return _rows_opt("""
        SELECT c.id_cambio, c.tipo,
               c.id_equipo, e.nombre AS equipo,
               c.id_cable, k.codigo AS cable,
               c.id_conector_a, ca.nombre AS conector_a, ea.id_equipo AS id_equipo_a, ea.nombre AS equipo_a,
               c.id_conector_b, cb.nombre AS conector_b, eb.id_equipo AS id_equipo_b, eb.nombre AS equipo_b
        FROM escenario_cambio c
        LEFT JOIN equipo e   ON e.id_equipo = c.id_equipo
        LEFT JOIN cable k    ON k.id_cable = c.id_cable
        LEFT JOIN conector ca ON ca.id_conector = c.id_conector_a
        LEFT JOIN equipo ea  ON ea.id_equipo = ca.id_equipo
        LEFT JOIN conector cb ON cb.id_conector = c.id_conector_b
        LEFT JOIN equipo eb  ON eb.id_equipo = cb.id_equipo
        WHERE c.id_escenario = ? ORDER BY c.orden, c.id_cambio""", (id_escenario,))


def escenarios_lista():
    """Escenarios guardados, el más reciente primero (como Modelo.devolver_todos_los_escenarios; la fecha llega al
    segundo, así que a igual fecha va primero el id más nuevo), con la cantidad de cambios de cada tipo."""
    return _rows_opt("""
        SELECT e.id_escenario, e.nombre, COALESCE(e.descripcion,'') AS descripcion, e.estado,
               COALESCE(e.fecha_ultima_edicion, e.fecha_creacion, '') AS fecha,
               COUNT(c.id_cambio) AS n_cambios,
               COALESCE(SUM(c.tipo = 'falla_equipo'), 0) AS n_fallas,
               COALESCE(SUM(c.tipo = 'desconexion_cable'), 0) AS n_cortes,
               COALESCE(SUM(c.tipo = 'conexion_virtual'), 0) AS n_reconexiones
        FROM escenario e LEFT JOIN escenario_cambio c ON c.id_escenario = e.id_escenario
        GROUP BY e.id_escenario
        ORDER BY COALESCE(e.fecha_ultima_edicion, e.fecha_creacion) DESC, e.id_escenario DESC""")


def escenario_ficha(id_escenario):
    """Datos del escenario y su lista de cambios (sin evaluar)."""
    f = _escenario_fila(id_escenario)
    f["cambios"] = _cambios_escenario(id_escenario)
    return f


def escenario_evaluar(id_escenario):
    """Evalúa TODOS los cambios juntos en un solo cálculo (Escenario.evaluar → GraphImpactAnalyzer.simular_escenario).
    Devuelve el comparativo antes/después de la reconexión virtual: `antes` = solo las fallas y cortes,
    `despues` = con las conexiones virtuales aplicadas. Los equipos que fallan no cuentan como impactados.
    No guarda el resultado ni cambia el estado del escenario."""
    from core.escenario_engine import Escenario
    t0 = time.perf_counter()
    ficha = escenario_ficha(id_escenario)
    esc = Escenario(_db_path(), id_escenario=id_escenario)
    res = esc.evaluar()
    out = {"escenario": {k: ficha[k] for k in _ESCENARIO_COLS}, "cambios": ficha["cambios"],
           "grafo_disponible": res is not None}
    if res is None:                      # sin tablas de conexión, etc.: la UI avisa en vez de romper
        out["calculo_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out
    g = esc.analyzer
    total, total_finales = g.totales()
    finales = g.puntos_finales()
    n_antes, n_despues = len(res.equipos_impactados_sin_reconexion), len(res.equipos_impactados)
    equipos = [{"id_equipo": _id(e), "nombre": g.nombre_equipo(e), "punto_final": e in finales,
                "estado": "recuperado" if e in res.equipos_recuperados else "impactado"}
               for e in (res.equipos_impactados_sin_reconexion | res.equipos_impactados)]
    equipos.sort(key=lambda x: (x["estado"] != "impactado", x["nombre"].lower(), x["id_equipo"]))
    por_par = {(str(c["id_conector_a"]), str(c["id_conector_b"])): c
               for c in ficha["cambios"] if c["tipo"] == "conexion_virtual"}

    def invalido(par):
        c = por_par.get((str(par[0]), str(par[1])), {})
        return {"id_conector_a": _id(par[0]), "id_conector_b": _id(par[1]),
                "equipo_a": c.get("equipo_a"), "conector_a": c.get("conector_a"),
                "equipo_b": c.get("equipo_b"), "conector_b": c.get("conector_b")}

    out.update({
        "total_equipos": total, "total_puntos_finales": total_finales,
        "hay_reconexion": bool(res.conexiones_virtuales),
        "n_fallados": len(res.equipos_fallados), "n_cortados": len(res.cables_cortados),
        "n_antes": n_antes, "n_despues": n_despues, "n_recuperados": len(res.equipos_recuperados),
        "n_puntos_finales": sum(1 for e in res.equipos_impactados if e in finales),
        "porcentaje_antes": round(100.0 * n_antes / total, 1) if total else 0.0,
        "porcentaje_despues": round(100.0 * n_despues / total, 1) if total else 0.0,
        "equipos": equipos,
        "cables_impactados": sorted(({"id_cable": _id(c), "codigo": g.nombre_cable(c)} for c in res.cables_impactados),
                                    key=lambda x: (str(x["codigo"]).lower(), x["id_cable"])),
        "causas_regla": sorted(({"id_equipo": _id(e), "nombre": g.nombre_equipo(e), "texto": txt}
                                for e, txt in (res.causas_regla or {}).items()), key=lambda x: x["nombre"].lower()),
        "conectores_invalidos": [invalido(p) for p in res.conectores_invalidos],
        "calculo_ms": round((time.perf_counter() - t0) * 1000, 1),
    })
    return out


# ── Búsqueda global (A.9) ────────────────────────────────────────────────────

def busqueda_indice():
    """Índice plano de todo lo que se puede buscar, para la pantalla Búsqueda (A.9).

    Se pide UNA vez por carga de base y el filtro corre en el navegador sobre esa copia (mismo patrón que el
    árbol de A.3: nada de una consulta por tecla). Una fila por entidad:
        {t: tipo, i: id, l: etiqueta, d: [datos para mostrar], x: texto que solo se busca, int?: true}
    Tipos: sala | rack | frame | equipo | conector | cable. El JS busca sobre `l` + `d` + `x`.
      - equipo: l = nombre; d = tipo, marca + modelo, inventario, serie (los mismos campos que la etiqueta del árbol,
        así que "sony 3500" o un número de serie encuentran el equipo igual que en el panel de GTK/Kivy).
      - conector: l = nombre; d = tipo de conector, equipo ("cam 1 out" funciona). Los del equipo 0 (sin equipo) no entran.
      - cable: l = código; d = estado, tipo de cable, equipos de sus extremos (máx. 4); x = "equipo conector" de
        cada extremo (como el desktop, donde el cable aparece si matchea alguna de sus conexiones).
        Entran también los internos (el árbol de GTK/Kivy los lista), marcados con `int`.
      - sala: solo el nombre. rack: l = nombre; d = sus salas. frame: l = nombre; d = marca + modelo, inventario, su rack.
    Solo lectura. Orden: por nombre dentro de cada tipo (los conectores, por equipo y luego nombre).
    """
    def txt(v):
        return "" if v is None else str(v).strip()

    def junta(*partes):
        return " ".join(p for p in partes if p)

    def nombre(fila, clave, id_):
        return txt(fila[clave]) or f"#{fila[id_]}"

    items = []
    for r in _rows("""
            SELECT s.id_sala, s.nombre FROM sala s ORDER BY lower(s.nombre), s.id_sala"""):
        items.append({"t": "sala", "i": r["id_sala"], "l": nombre(r, "nombre", "id_sala"), "d": []})

    salas_de_rack = {}
    for r in _rows("""
            SELECT rs.id_rack, s.nombre FROM rack_por_sala rs JOIN sala s ON s.id_sala = rs.id_sala
            ORDER BY rs.id_rack, s.id_sala"""):
        salas_de_rack.setdefault(r["id_rack"], []).append(txt(r["nombre"]))
    for r in _rows("SELECT id_rack, nombre FROM rack ORDER BY lower(nombre), numero, id_rack"):
        items.append({"t": "rack", "i": r["id_rack"], "l": nombre(r, "nombre", "id_rack"),
                      "d": [s for s in salas_de_rack.get(r["id_rack"], []) if s]})

    rack_de_frame = {}
    for r in _rows("""
            SELECT p.id_frame, r.nombre FROM posicion_en_rack p JOIN rack r ON r.id_rack = p.id_rack
            WHERE p.id_frame IS NOT NULL ORDER BY p.id_posicion_en_rack"""):
        rack_de_frame.setdefault(r["id_frame"], txt(r["nombre"]))     # el primero, como en la lista de Ubicaciones
    for r in _rows("""
            SELECT f.id_frame, f.nombre, m.nombre AS marca, f.modelo, f.num_inventario AS inv
            FROM frame f LEFT JOIN marca m ON m.id_marca = f.id_marca
            ORDER BY lower(f.nombre), f.id_frame"""):
        d = [junta(txt(r["marca"]), txt(r["modelo"])), txt(r["inv"]), rack_de_frame.get(r["id_frame"], "")]
        items.append({"t": "frame", "i": r["id_frame"], "l": nombre(r, "nombre", "id_frame"), "d": [x for x in d if x]})

    for r in _rows("""
            SELECT e.id_equipo, e.nombre, m.nombre AS marca, te.nombre AS tipo, e.modelo,
                   e.num_inventario AS inv, e.num_serie AS serie
            FROM equipo e
            LEFT JOIN marca m ON m.id_marca = e.id_marca
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE e.id_equipo != 0
            ORDER BY lower(e.nombre), e.id_equipo"""):
        d = [txt(r["tipo"]), junta(txt(r["marca"]), txt(r["modelo"])), txt(r["inv"]), txt(r["serie"])]
        items.append({"t": "equipo", "i": r["id_equipo"], "l": nombre(r, "nombre", "id_equipo"), "d": [x for x in d if x]})

    for r in _rows("""
            SELECT c.id_conector, c.nombre, tc.nombre AS tipo, e.nombre AS equipo
            FROM conector c
            JOIN equipo e ON e.id_equipo = c.id_equipo
            LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE c.id_equipo != 0
            ORDER BY lower(e.nombre), lower(c.nombre), c.id_conector"""):
        d = [txt(r["tipo"]), txt(r["equipo"])]
        items.append({"t": "conector", "i": r["id_conector"], "l": nombre(r, "nombre", "id_conector"), "d": [x for x in d if x]})

    extremos = {}      # id_cable → [(equipo, conector)] de las conexiones que apuntan a un equipo real
    for r in _rows("""
            SELECT cx.id_cable, e.nombre AS equipo, c.nombre AS conector
            FROM conexion cx
            JOIN conector c ON c.id_conector = cx.id_conector
            JOIN equipo e ON e.id_equipo = c.id_equipo
            WHERE c.id_equipo != 0
            ORDER BY cx.id_cable, cx.id_conexion"""):
        extremos.setdefault(r["id_cable"], []).append((txt(r["equipo"]), txt(r["conector"])))
    for r in _rows("""
            SELECT k.id_cable, k.codigo, k.estado, tc.nombre AS tipo_cable,
                   COALESCE(k.es_cable_conexion_interna, 0) AS interno
            FROM cable k LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = k.id_tipo_cable
            ORDER BY lower(k.codigo), k.id_cable"""):
        ext = extremos.get(r["id_cable"], [])
        equipos = list(dict.fromkeys(e for e, _c in ext if e))[:4]
        it = {"t": "cable", "i": r["id_cable"], "l": nombre(r, "codigo", "id_cable"),
              "d": [x for x in (txt(r["estado"]), txt(r["tipo_cable"]), " ⇄ ".join(equipos)) if x],
              "x": " ".join(junta(e, c) for e, c in ext)}
        if r["interno"]:
            it["int"] = True
        items.append(it)
    return {"items": items}


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
    cables_lista, cable_ficha, conexiones_lista, conexiones_equipo, cadena_extension,
    salas_lista, sala_ficha, racks_lista, rack_ficha,
    frames_lista, slots_lista, frame_ficha,
    ubicaciones, rack_vista, frame_vista, patcheras_global,
    impacto_cable, impacto_equipo, impacto_rack, riesgo_irf, conectores_de_equipo, diagnostico, linter_topologia,
    escenarios_lista, escenario_ficha, escenario_evaluar,
    busqueda_indice,
)}



FUNCIONES["firmas"] = firmas


# ── Escritura (Fase B): módulos aparte que se registran acá ──────────────────
# Se importan al final porque usan helpers de este módulo (de forma diferida, vía `import bridge`).
import catalogos_web  # noqa: E402

ESCRITURAS = {f.__name__ for f in catalogos_web.ESCRITURAS}      # nombres de las funciones que modifican la base
FUNCIONES.update({f.__name__: f for f in catalogos_web.LECTURAS + catalogos_web.ESCRITURAS})


def call(fn, args_json="{}"):
    """Punto de entrada único desde JS. Nunca levanta: devuelve siempre un JSON.

    Respuestas: {"ok": true, "data": ..., "ms": n} o {"ok": false, "error": "...", "ms": n}. Las funciones de
    ESCRITURA agregan `"escribio": true` como PRIMERA clave (el worker lo detecta con un `startsWith`, sin parsear
    respuestas grandes) para persistir la base antes de contestar; también lo agregan al fallar, porque una
    escritura de varios pasos pudo quedar a medias. No lo agregan cuando el error ocurrió ANTES de tocar la base
    (excepciones con `sin_cambios`, p. ej. un campo inválido). Un error con `campos` ({campo: motivo}) los devuelve
    en `"campos"` y su mensaje va sin el nombre de la clase (es texto para el usuario)."""
    t = time.perf_counter()
    ms = lambda: round((time.perf_counter() - t) * 1000, 1)  # noqa: E731
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
        out = {"escribio": True} if fn in ESCRITURAS else {}
        out.update({"ok": True, "data": data, "ms": ms()})
        return json.dumps(out, ensure_ascii=False, default=str)
    except Exception as ex:  # noqa: BLE001 — se informa a la UI, no se oculta
        sin_cambios = getattr(ex, "sin_cambios", False)
        out = {"escribio": True} if (fn in ESCRITURAS and not sin_cambios) else {}
        out.update({"ok": False, "error": str(ex) if sin_cambios else f"{type(ex).__name__}: {ex}", "ms": ms()})
        if getattr(ex, "campos", None):
            out["campos"] = ex.campos
        return json.dumps(out, ensure_ascii=False, default=str)
