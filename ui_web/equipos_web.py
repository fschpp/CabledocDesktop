"""CableDoc Web — ABM de equipos y conectores (plan_pyodide_v1.md, Fase B.4).

Se registra en `bridge.FUNCIONES` junto con catalogos_web.py y cables_web.py (ver el final de bridge.py) y se llama igual:
`bridge.call("equipo_alta", '{"valores": {"nombre": "CAM 1", "id_tipo_equipo": 3}}')`.

Lecturas:
  equipo_formulario(id_equipo)                 → {id_equipo, esquema, valores}   (valores = None en un alta)
  equipo_usos(id_equipo)                       → {id_equipo, nombre, usos}       (qué arrastra borrarlo)
  equipo_plantilla(id_tipo_equipo)             → {id_tipo_equipo, tiene_plantilla, filas}   (para la alta rápida)
  conector_formulario(id_conector, id_equipo)  → {id_conector, id_equipo, equipo, esquema, valores}
  conector_usos(id_conector)                   → {id_conector, nombre, usos}

Extremo desconectado (equipo FANTASMA, el «⚡» del desktop para documentar la punta de un cable confirmada sin conectar):
  cable_extremo_formulario(id_cable)           → {id_cable, codigo, n_extremos, lado, nombre_tipo, puede, motivo}   (lectura)
  cable_extremo_desconectado(id_cable, lado)   → {id_equipo, id_conector, id_conexion, nombre, lado}              (escritura)
  cable_extremo_deshacer(id_equipo, id_conexion) → {id_equipo}                                                    (escritura)

Escrituras:
  equipo_alta(valores)                         → {id, nombre, valores}
  equipo_alta_rapida(valores, conectores)      → {id, nombre, n_conectores, ids_conectores, plantilla_guardada}
  equipo_modificar(id, valores)                → {id, nombre, anterior, valores}   (`valores` reemplaza TODOS los campos)
  equipo_baja(id, solo_si_sin_uso, conectores_propios) → {id, nombre, fila, usos}
  equipo_restaurar(id, fila)                   → {id, nombre}                    (deshacer de una baja SIN uso)
  conector_alta(id_equipo, valores)            → {id, nombre, valores}
  conector_modificar(id, valores)              → {id, nombre, anterior, valores}
  conector_baja(id, solo_si_sin_uso)           → {id, nombre, fila, usos}
  conector_restaurar(id, fila)                 → {id, nombre}

Reglas de diseño (mismas que catalogos_web.py y cables_web.py):
  - Las altas y bajas pasan por los métodos de `Modelo` (los del desktop). Excepciones, donde Modelo no alcanza:
      · EDITAR un equipo o un conector: Modelo.modificacion_equipo / modificacion_conector reescriben la imagen y las coordenadas
        y, si no pueden medir la imagen, las dejan en NULL. En la web las imágenes viven en OPFS (Modelo no las ve), así que
        usarlos borraría las coordenadas cargadas desde el desktop. Acá se hace un UPDATE solo de los campos del formulario:
        la imagen, el picon y las coordenadas no se tocan (se editan en B.8);
      · reinsertar con el MISMO id (restaurar, para «deshacer»).
  - Se valida TODO antes de escribir. Un error de validación es `ErrorCampos`: bridge.call lo devuelve como
    {"ok": false, "campos": {...}} y no pide persistir.
  - Qué arrastra una baja se calcula SIN lista propia de tablas: se recorren las claves foráneas de la base (PRAGMA
    foreign_key_list) siguiendo las cascadas (equipo → conectores → conexiones → extensiones…). El «deshacer» de una baja solo
    se ofrece si no arrastró nada (lo que se llevó no se puede reconstruir).
  - «Equipo crítico de la cadena» (tabla equipo_critico) se edita con el resto del equipo, vía Modelo.establecer_equipo_critico y solo
    si cambió (el desktop lo habilita únicamente al editar; acá también se puede marcar en el alta).
  - Diferencias con el desktop: el nombre del equipo es obligatorio (como en su alta rápida); el equipo de un conector no se
    cambia al editarlo (el desktop tampoco lo ofrece); no se tocan imagen ni coordenadas al editar (ver arriba); la alta rápida
    valida la plantilla entera antes de crear nada y, si falla a mitad, borra el equipo recién creado.
  - Alta rápida: mismas reglas de nombres que el desktop (`IN`, `IN 01`, `OUT BNC`, `OUT BNC 02`…) y, como él, guarda la
    plantilla del tipo con las cantidades elegidas (crea la tabla plantilla_conector en una base vieja que no la tenga).
"""
import sqlite3

from catalogos_web import ErrorCampos, ErrorSinCambios, _c, _id, _valor
from cables_web import _campo, _op, _ref, _OB, _EL

_BALANCES = ("BALANCEADO", "DESBALANCEADO", "NA")          # CHECK de conector.modo_balance
_CANALES = ("MONO", "ESTEREO", "NA")                       # CHECK de conector.modo_canal
_DIRECCIONES = ("IN", "OUT", "INOUT")                      # las de plantilla_conector.direccion
MAX_POR_FILA, MAX_TOTAL = 99, 500                          # alta rápida: conectores por fila de plantilla / en total
_PROPIAS = ("equipo_critico", "riesgo_equipo_cache")       # datos del equipo mismo (marca de crítico, caché de riesgo): no cuentan como «uso» para el deshacer de un alta


def _b():
    import bridge          # import diferido: bridge importa este módulo al final de su propio import
    return bridge


def _M():
    return _b()._M()


def _cols(tabla):
    return {r["name"] for r in _b()._rows(f'PRAGMA table_info("{tabla}")')}


def _existe(tabla, pk, valor):
    return _b()._one(f'SELECT 1 AS x FROM "{tabla}" WHERE "{pk}"=?', (valor,)) is not None


def _hay_tabla(nombre):
    return _b()._one("SELECT 1 AS x FROM sqlite_master WHERE type='table' AND name=?", (nombre,)) is not None


# ── Qué arrastra una baja (claves foráneas) ──────────────────────────────────

def _hijos():
    """{tabla_padre: [(tabla_hija, columna, columna_referenciada, on_delete)]}, leído de la base."""
    b, out = _b(), {}
    for t in b._rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        for fk in b._rows(f'PRAGMA foreign_key_list("{t["name"]}")'):
            out.setdefault(fk["table"], []).append((t["name"], fk["from"], fk["to"], (fk["on_delete"] or "").upper()))
    return out


def _pk(tabla):
    pks = [r["name"] for r in _b()._rows(f'PRAGMA table_info("{tabla}")') if r["pk"]]
    return pks[0] if len(pks) == 1 else "rowid"


def _en(valores):
    return ",".join("?" * len(valores))


def _arrastre(tabla, ids, hijos=None, acum=None, nivel=0):
    """Filas que se borran (CASCADE) o se anulan (SET NULL) al borrar `ids` (valores de la clave de `tabla`).
    Devuelve {(tabla_hija, 'borra'|'anula'): {claves}}; cada fila se cuenta una sola vez."""
    hijos = _hijos() if hijos is None else hijos
    acum = {} if acum is None else acum
    if not ids or nivel > 5:
        return acum
    b = _b()
    for hija, col, ref, accion in hijos.get(tabla, []):
        if accion not in ("CASCADE", "SET NULL") or (ref is not None and ref != _pk(tabla)):
            continue
        pk, filas = _pk(hija), []
        for i in range(0, len(ids), 400):
            lote = ids[i:i + 400]
            filas += [r["k"] for r in b._rows(f'SELECT "{pk}" AS k FROM "{hija}" WHERE "{col}" IN ({_en(lote)})', lote)]
        efecto = "borra" if accion == "CASCADE" else "anula"
        previos = acum.setdefault((hija, efecto), set())
        nuevas = [k for k in filas if k not in previos]
        previos.update(nuevas)
        if accion == "CASCADE" and nuevas and hija != tabla:
            _arrastre(hija, nuevas, hijos, acum, nivel + 1)
    return acum


def _usos(tabla, ids):
    """[{tabla, n, efecto}] (solo n > 0), primero lo que se borra y dentro de cada grupo lo más numeroso."""
    acum = _arrastre(tabla, list(ids))
    usos = [{"tabla": t, "n": len(k), "efecto": e} for (t, e), k in acum.items() if k]
    return sorted(usos, key=lambda u: (u["efecto"] != "borra", -u["n"], u["tabla"]))


# ── Lectura de filas ─────────────────────────────────────────────────────────

_EQ_BASE = ("id_equipo, nombre, id_tipo_equipo, id_marca, modelo, num_inventario, num_serie, fecha_fabricacion, "
            "COALESCE(es_equipo_usado,0) AS es_equipo_usado, path_manual, configuraciones")
_EQ_OPC = ("es_modulo_de_frame", "ancho_mm", "alto_mm", "profundidad_mm")      # columnas que una base vieja puede no tener
_CAMPOS_EQUIPO = ("nombre", "id_tipo_equipo", "id_marca", "modelo", "num_inventario", "num_serie", "fecha_fabricacion",
                  "es_equipo_usado", "es_modulo_de_frame", "critico", "ancho_mm", "alto_mm", "profundidad_mm", "path_manual", "configuraciones")
_RAPIDA = ("nombre", "id_tipo_equipo", "id_marca", "modelo", "num_inventario", "num_serie")


def _leer_equipo(id_):
    """Fila del equipo como dict, o None. Las columnas opcionales de una base vieja se leen como NULL (es_modulo_de_frame, 0)."""
    cols = _cols("equipo")
    extra = ", ".join(f"COALESCE({c},0) AS {c}" if c == "es_modulo_de_frame" else c for c in _EQ_OPC if c in cols)
    faltan = ", ".join(("0" if c == "es_modulo_de_frame" else "NULL") + f" AS {c}" for c in _EQ_OPC if c not in cols)
    f = _b()._one(f"SELECT {_EQ_BASE}, {', '.join(x for x in (extra, faltan) if x)} FROM equipo WHERE id_equipo=?", (id_,))
    if f is not None:       # «Equipo crítico de la cadena»: vive en la tabla equipo_critico (una base vieja no la tiene → no crítico)
        f["critico"] = _b()._one("SELECT 1 AS x FROM equipo_critico WHERE id_equipo=?", (id_,)) is not None if _hay_tabla("equipo_critico") else False
    return f


def _valores_equipo(f):
    v = {k: f[k] for k in _CAMPOS_EQUIPO}
    for k in ("es_equipo_usado", "es_modulo_de_frame", "critico"):
        v[k] = bool(v[k])
    if v["num_inventario"] is not None:
        v["num_inventario"] = str(v["num_inventario"])
    return v


def _equipo_o_error(id_):
    f = _leer_equipo(id_)
    if f is None:
        raise ErrorSinCambios(f"No existe el equipo {id_}")
    return f


def _fila_cruda(tabla, pk, id_):
    """Todas las columnas de la fila (para reinsertarla tal cual al deshacer una baja)."""
    return _b()._one(f'SELECT * FROM "{tabla}" WHERE "{pk}"=?', (id_,))


def _reinsertar(tabla, pk, id_, fila):
    """Inserta `fila` con su id original. Las columnas se validan contra el esquema (no se arma SQL con nombres del cliente)."""
    if not isinstance(fila, dict) or not fila:
        raise ErrorSinCambios("Datos de deshacer inválidos.")
    if _existe(tabla, pk, id_):
        raise ErrorSinCambios(f"Ya existe un registro con el id {id_}: no se restaura.")
    validas = _cols(tabla)
    sobran = sorted(set(fila) - validas)
    if sobran:
        raise ErrorSinCambios(f"Datos de deshacer inválidos: columnas desconocidas {sobran}")
    fila = dict(fila, **{pk: id_})
    cols = list(fila)
    with _M()._conn_ctx() as conn:
        conn.execute(f'INSERT INTO "{tabla}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({_en(cols)})', [fila[c] for c in cols])


# ── Validación de equipo ─────────────────────────────────────────────────────

_CAMPO_TXT = {
    "nombre": _c("nombre", requerido=True, largo=200),
    "modelo": _c("modelo", largo=200),
    "num_inventario": _c("num_inventario", largo=60),
    "num_serie": _c("num_serie", largo=120),
    "fecha_fabricacion": _c("fecha_fabricacion", largo=40),
    "path_manual": _c("path_manual", largo=500),
    "configuraciones": _c("configuraciones", "texto_largo", largo=50000),
    "ancho_mm": _c("ancho_mm", "numero", minimo=0),
    "alto_mm": _c("alto_mm", "numero", minimo=0),
    "profundidad_mm": _c("profundidad_mm", "numero", minimo=0),
}


def _bool(v):
    if v is None or v == "":
        return False
    if v in (True, False, 0, 1, "0", "1"):
        return bool(int(v))
    raise ValueError(_EL)


def _normalizar_equipo(valores, permitidos=_CAMPOS_EQUIPO):
    """Valores del formulario → dict normalizado con TODOS los campos (vacío = None, casillas = bool). Levanta ErrorCampos
    con todos los errores juntos."""
    if not isinstance(valores, dict):
        raise ErrorSinCambios("`valores` debe ser un objeto {campo: valor}")
    sobran = sorted(set(valores) - set(permitidos))
    if sobran:
        raise ErrorSinCambios(f"Campos desconocidos: {sobran}")
    out, errores = {}, {}
    for nombre in _CAMPOS_EQUIPO:
        v = valores.get(nombre)
        try:
            if nombre in _CAMPO_TXT:
                out[nombre] = _valor(_CAMPO_TXT[nombre], v)
            elif nombre == "id_tipo_equipo":
                out[nombre] = _ref(v, "tipo_equipo", "id_tipo_equipo")
            elif nombre == "id_marca":
                out[nombre] = _ref(v, "marca", "id_marca")
            else:
                out[nombre] = _bool(v)
        except ValueError as ex:
            errores[nombre] = str(ex)
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    return out


def _asegurar_columna_modulo():
    """equipo.es_modulo_de_frame: la agrega Modelo al arrancar el desktop (asegurar_tablas_plano); acá solo la columna."""
    if "es_modulo_de_frame" not in _cols("equipo"):
        with _M()._conn_ctx() as conn:
            conn.execute("ALTER TABLE equipo ADD COLUMN es_modulo_de_frame INTEGER DEFAULT 0")


def _dimensiones(v):
    return tuple(v[k] for k in ("ancho_mm", "alto_mm", "profundidad_mm"))


# ── Formulario de equipo ─────────────────────────────────────────────────────

def _esquema_equipo(solo=None):
    b = _b()
    esq = [
        _campo("nombre", "texto", True, largo=200),
        _campo("id_tipo_equipo", "select", opciones=_op(b._rows("SELECT id_tipo_equipo, nombre FROM tipo_equipo ORDER BY lower(nombre)"), "id_tipo_equipo")),
        _campo("id_marca", "select", opciones=_op(b._rows("SELECT id_marca, nombre FROM marca ORDER BY lower(nombre)"), "id_marca")),
        _campo("modelo", "texto", largo=200),
        _campo("num_inventario", "texto", largo=60), _campo("num_serie", "texto", largo=120),
        _campo("fecha_fabricacion", "texto", largo=40),
        _campo("es_equipo_usado", "bool"), _campo("es_modulo_de_frame", "bool"), _campo("critico", "bool"),
        _campo("ancho_mm", "numero", minimo=0), _campo("alto_mm", "numero", minimo=0), _campo("profundidad_mm", "numero", minimo=0),
        _campo("path_manual", "texto", largo=500),
        _campo("configuraciones", "texto_largo", largo=50000),
    ]
    return [e for e in esq if solo is None or e["nombre"] in solo]


def equipo_formulario(id_equipo=None):
    """Esquema del formulario (con las opciones ya resueltas) y, al editar, los valores actuales del equipo."""
    if id_equipo is None:
        return {"id_equipo": None, "esquema": _esquema_equipo(), "valores": None}
    id_ = _id(id_equipo)
    return {"id_equipo": id_, "esquema": _esquema_equipo(), "valores": _valores_equipo(_equipo_o_error(id_))}


def equipo_usos(id_equipo):
    """Qué arrastra borrar el equipo: [{tabla, n, efecto: anula|borra}] (solo n > 0), con las cascadas incluidas."""
    id_ = _id(id_equipo)
    f = _equipo_o_error(id_)
    return {"id_equipo": id_, "nombre": f["nombre"], "usos": _usos("equipo", [id_])}


# ── Escrituras de equipo ─────────────────────────────────────────────────────

def _crear_equipo(v):
    M = _M()
    id_ = M.alta_equipo_retorna_id(v["id_tipo_equipo"], v["id_marca"], v["num_inventario"], v["num_serie"], v["modelo"], v["nombre"],
                                   None, None, None, v["path_manual"], v["configuraciones"], None, v["fecha_fabricacion"],
                                   1 if v["es_equipo_usado"] else 0)
    if v["es_modulo_de_frame"]:
        _asegurar_columna_modulo()
        M.actualizar_es_modulo_de_frame(id_, True)
    if any(d is not None for d in _dimensiones(v)):
        M.actualizar_dimensiones("equipo", id_, *_dimensiones(v))
    if v["critico"]:
        M.establecer_equipo_critico(id_, True)
    return id_


def equipo_alta(valores):
    v = _normalizar_equipo(valores)
    id_ = _crear_equipo(v)
    return {"id": id_, "nombre": v["nombre"], "valores": _valores_equipo(_equipo_o_error(id_))}


def equipo_modificar(id, valores):
    id_ = _id(id)
    previa = _equipo_o_error(id_)
    v = _normalizar_equipo(valores)
    anterior = _valores_equipo(previa)
    with _M()._conn_ctx() as conn:       # solo los campos del formulario: imagen, picon y coordenadas quedan como están
        conn.execute("UPDATE equipo SET id_tipo_equipo=?, id_marca=?, num_inventario=?, num_serie=?, modelo=?, nombre=?, "
                     "path_manual=?, configuraciones=?, fecha_fabricacion=?, es_equipo_usado=? WHERE id_equipo=?",
                     (v["id_tipo_equipo"], v["id_marca"], v["num_inventario"], v["num_serie"], v["modelo"], v["nombre"],
                      v["path_manual"], v["configuraciones"], v["fecha_fabricacion"], 1 if v["es_equipo_usado"] else 0, id_))
    M = _M()
    if v["es_modulo_de_frame"] != anterior["es_modulo_de_frame"]:      # en una base vieja escribirlo agrega la columna; no se agrega por guardar otro campo
        _asegurar_columna_modulo()
        M.actualizar_es_modulo_de_frame(id_, v["es_modulo_de_frame"])
    if _dimensiones(v) != _dimensiones(anterior):
        M.actualizar_dimensiones("equipo", id_, *_dimensiones(v))
    if v["critico"] != anterior["critico"]:          # en una base vieja marcarlo crea la tabla equipo_critico (Modelo); no se crea por guardar otro campo
        M.establecer_equipo_critico(id_, v["critico"])
    return {"id": id_, "nombre": v["nombre"], "anterior": anterior, "valores": _valores_equipo(_equipo_o_error(id_))}


def equipo_baja(id, solo_si_sin_uso=False, conectores_propios=0):
    """Borra el equipo (las FK arrastran sus conectores, conexiones, etc.). Con `solo_si_sin_uso` se niega si arrastra algo
    (lo pide el «deshacer» de un alta, para no borrar lo que se haya conectado mientras tanto); `conectores_propios` = cuántos
    conectores recién creados por la alta rápida se pueden llevar (n exacto, sin conexiones ni nada más). La marca de equipo
    crítico y la caché de riesgo son del equipo mismo y no bloquean ese deshacer."""
    id_ = _id(id)
    previa = _equipo_o_error(id_)
    propios = _id(conectores_propios)
    usos = _usos("equipo", [id_])
    if solo_si_sin_uso:
        resto = [u for u in usos if u["tabla"] not in _PROPIAS
                 and not (propios and u["tabla"] == "conector" and u["n"] == propios and u["efecto"] == "borra")]
        if resto:
            raise ErrorSinCambios("El equipo ya tiene conexiones u otros datos asociados: no se elimina.")
    fila = _fila_cruda("equipo", "id_equipo", id_)
    _M().eliminar_equipo(id_)
    return {"id": id_, "nombre": previa["nombre"], "fila": fila, "usos": usos}


def equipo_restaurar(id, fila):
    """Reinserta un equipo con su id original (deshacer de una baja SIN uso: lo que lo usaba ya no se puede reconstruir)."""
    id_ = _id(id)
    _reinsertar("equipo", "id_equipo", id_, fila)
    return {"id": id_, "nombre": _equipo_o_error(id_)["nombre"]}


# ── Alta rápida con plantilla de conectores ──────────────────────────────────

def _tipos_conector():
    return _b()._rows("SELECT id_tipo_conector AS id, nombre FROM tipo_conector ORDER BY lower(nombre), id_tipo_conector")


def equipo_plantilla(id_tipo_equipo=None):
    """Filas de la alta rápida: primero las de la plantilla del tipo (con su cantidad) y después cada otro tipo de conector
    con IN y OUT en 0, como el desktop. [{id_tipo_conector, tipo_conector, direccion, cantidad}]."""
    id_tipo = None if id_tipo_equipo is None else _id(id_tipo_equipo)
    tipos = _tipos_conector()
    nombres = {t["id"]: t["nombre"] for t in tipos}
    filas, vistas = [], set()
    if id_tipo is not None:
        for r in _M().devolver_plantillas_conectores(id_tipo):
            if r[0] in nombres:
                dir_ = str(r[2] or "INOUT").upper()
                filas.append({"id_tipo_conector": r[0], "tipo_conector": nombres[r[0]], "direccion": dir_, "cantidad": int(r[3] or 0)})
                vistas.add((r[0], dir_))
    tiene = bool(filas)
    for t in tipos:
        for dir_ in ("IN", "OUT"):
            if (t["id"], dir_) not in vistas:
                filas.append({"id_tipo_conector": t["id"], "tipo_conector": t["nombre"], "direccion": dir_, "cantidad": 0})
    filas.sort(key=lambda f: (f["cantidad"] == 0, str(f["tipo_conector"]).lower(), f["direccion"]))
    return {"id_tipo_equipo": id_tipo, "tiene_plantilla": tiene, "filas": filas}


def _normalizar_plantilla(conectores):
    """[{id_tipo_conector, direccion, cantidad}] → solo las de cantidad > 0, validadas. Se mira entera antes de crear nada."""
    if not isinstance(conectores, list):
        raise ErrorSinCambios("`conectores` debe ser una lista [{id_tipo_conector, direccion, cantidad}]")
    nombres = {t["id"]: t["nombre"] for t in _tipos_conector()}
    out, errores, vistos, total = [], {}, set(), 0
    for i, c in enumerate(conectores):
        if not isinstance(c, dict):
            raise ErrorSinCambios("`conectores` debe ser una lista de objetos")
        clave = f"q_{c.get('id_tipo_conector')}_{c.get('direccion')}"
        try:
            id_tc = c.get("id_tipo_conector")
            if isinstance(id_tc, bool) or not isinstance(id_tc, (int, str)) or int(id_tc) not in nombres:
                raise ValueError(_EL)
            id_tc, dir_ = int(id_tc), c.get("direccion")
            if dir_ not in _DIRECCIONES:
                raise ValueError(_EL)
            if (id_tc, dir_) in vistos:
                raise ValueError("Fila repetida")
            vistos.add((id_tc, dir_))
            q = c.get("cantidad")
            q = 0 if q is None or q == "" else q
            if isinstance(q, bool) or not isinstance(q, (int, float, str)):
                raise ValueError("Debe ser un número entero")
            try:
                x = float(str(q).replace(",", "."))
            except ValueError:
                raise ValueError("Debe ser un número entero") from None
            if x != int(x):
                raise ValueError("Debe ser un número entero")
            q = int(x)
            if q < 0:
                raise ValueError("No puede ser negativo")
            if q > MAX_POR_FILA:       # el texto del error es una clave de i18n fija (ver i18n_web.py)
                raise ValueError("Máximo 99 por fila")
            if q:
                out.append({"id_tipo_conector": id_tc, "tipo_conector": nombres[id_tc], "direccion": dir_, "cantidad": q})
                total += q
        except (ValueError, TypeError) as ex:
            errores[clave] = str(ex)
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    if total > MAX_TOTAL:
        raise ErrorSinCambios(f"Son demasiados conectores ({total}): el máximo por alta es {MAX_TOTAL}.")
    return out


def _nombre_conector(dir_, tipo, i, q):
    """Misma regla que el desktop: `IN` / `IN 01` si el tipo se llama como la dirección; si no `IN BNC` / `IN BNC 01`."""
    sufijo = f" {i:02d}" if q > 1 else ""
    if str(tipo).strip().upper() == dir_.strip().upper():
        return f"{dir_}{sufijo}"
    return f"{dir_} {tipo}{sufijo}"


def equipo_alta_rapida(valores, conectores):
    """Crea el equipo y sus conectores según la plantilla elegida, y guarda esa plantilla para el tipo (como el desktop)."""
    v = _normalizar_equipo(valores, permitidos=_RAPIDA)
    plantilla = _normalizar_plantilla(conectores)
    M = _M()
    id_ = _crear_equipo(v)
    ids = []
    try:
        for p in plantilla:
            for i in range(1, p["cantidad"] + 1):
                ids.append(M.agregar_conector_retorna_id(_nombre_conector(p["direccion"], p["tipo_conector"], i, p["cantidad"]),
                                                         id_, p["id_tipo_conector"], None, None, None))
        if v["id_tipo_equipo"] is not None:
            for p in plantilla:
                M.guardar_plantilla_conector(v["id_tipo_equipo"], p["id_tipo_conector"], p["direccion"], p["cantidad"])
    except Exception:
        try:
            M.eliminar_equipo(id_)       # sus conectores se van por cascada: no queda un equipo a medio armar
        except Exception:                # noqa: BLE001
            pass
        raise
    return {"id": id_, "nombre": v["nombre"], "n_conectores": len(ids), "ids_conectores": ids,
            "plantilla_guardada": bool(plantilla) and v["id_tipo_equipo"] is not None}


# ── Conectores ───────────────────────────────────────────────────────────────

_CAMPOS_CONECTOR = ("nombre", "id_tipo_conector", "id_tipo_ficha", "modo_balance", "modo_canal", "id_senal", "id_formato")
_NOMBRE_CONECTOR = {"alta": _c("nombre", requerido=True, largo=120), "edicion": _c("nombre", largo=120)}


def _leer_conector(id_):
    """Fila del conector como dict (con su señal vigente), o None. Tolera una base vieja sin las columnas de formato eléctrico
    ni las tablas de señal (se leen como NULL)."""
    b = _b()
    try:
        f = b._one("SELECT id_conector, nombre, id_equipo, id_tipo_conector, id_tipo_ficha, modo_balance, modo_canal FROM conector WHERE id_conector=?", (id_,))
    except sqlite3.OperationalError:
        f = b._one("SELECT id_conector, nombre, id_equipo, id_tipo_conector, NULL AS id_tipo_ficha, NULL AS modo_balance, NULL AS modo_canal "
                   "FROM conector WHERE id_conector=?", (id_,))
    if f is None:
        return None
    s = next(iter(b._rows_opt("SELECT id_senal, id_formato, origen FROM senal_en_conector WHERE id_conector=?", (id_,))), None)
    f["id_senal"], f["id_formato"] = (s["id_senal"], s["id_formato"]) if s else (None, None)
    f["origen_senal"] = s["origen"] if s else None
    return f


def _conector_o_error(id_):
    f = _leer_conector(id_)
    if f is None:
        raise ErrorSinCambios(f"No existe el conector {id_}")
    return f


def _valores_conector(f):
    return {k: f[k] for k in _CAMPOS_CONECTOR}


def _esquema_conector(editando):
    b = _b()
    esq = [
        _campo("nombre", "texto", not editando, largo=120),
        _campo("id_tipo_conector", "select", opciones=_op(b._rows("SELECT id_tipo_conector, nombre FROM tipo_conector ORDER BY lower(nombre)"), "id_tipo_conector")),
        _campo("id_tipo_ficha", "select", opciones=_op(b._rows_opt("SELECT id_tipo_ficha, nombre FROM tipo_ficha ORDER BY lower(nombre)"), "id_tipo_ficha")),
        _campo("modo_balance", "select", opciones=[{"valor": x, "etiqueta": x} for x in _BALANCES]),
        _campo("modo_canal", "select", opciones=[{"valor": x, "etiqueta": x} for x in _CANALES]),
    ]
    if _hay_tabla("senal"):
        esq += [_campo("id_senal", "select", opciones=_op(b._rows("SELECT id_senal, nombre FROM senal ORDER BY lower(nombre)"), "id_senal")),
                _campo("id_formato", "select", opciones=_op(b._rows_opt("SELECT id_formato, nombre FROM tipo_formato_senal ORDER BY lower(nombre)"), "id_formato"))]
    return esq


def conector_formulario(id_conector=None, id_equipo=None):
    """Formulario de un conector. En un alta se pasa `id_equipo` (se agrega desde la ficha del equipo); al editar el equipo no cambia."""
    b = _b()
    if id_conector is None:
        if id_equipo is None:
            raise ErrorSinCambios("Falta el equipo al que se agrega el conector.")
        eq = b._one("SELECT id_equipo, nombre FROM equipo WHERE id_equipo=?", (_id(id_equipo),))
        if eq is None:
            raise ErrorSinCambios(f"No existe el equipo {id_equipo}")
        return {"id_conector": None, "id_equipo": eq["id_equipo"], "equipo": eq["nombre"], "esquema": _esquema_conector(False), "valores": None}
    f = _conector_o_error(_id(id_conector))
    eq = b._one("SELECT nombre FROM equipo WHERE id_equipo=?", (f["id_equipo"],))
    return {"id_conector": f["id_conector"], "id_equipo": f["id_equipo"], "equipo": eq["nombre"] if eq else None,
            "esquema": _esquema_conector(True), "valores": _valores_conector(f)}


def conector_usos(id_conector):
    id_ = _id(id_conector)
    f = _conector_o_error(id_)
    return {"id_conector": id_, "nombre": f["nombre"], "usos": _usos("conector", [id_])}


def _normalizar_conector(valores, editando):
    if not isinstance(valores, dict):
        raise ErrorSinCambios("`valores` debe ser un objeto {campo: valor}")
    permitidos = set(_CAMPOS_CONECTOR)
    sobran = sorted(set(valores) - permitidos)
    if sobran:
        raise ErrorSinCambios(f"Campos desconocidos: {sobran}")
    out, errores = {}, {}
    for nombre in _CAMPOS_CONECTOR:
        v = valores.get(nombre)
        try:
            if nombre == "nombre":
                out[nombre] = _valor(_NOMBRE_CONECTOR["edicion" if editando else "alta"], v)
            elif nombre == "id_tipo_conector":
                out[nombre] = _ref(v, "tipo_conector", "id_tipo_conector")
            elif nombre == "id_tipo_ficha":
                out[nombre] = _ref(v, "tipo_ficha", "id_tipo_ficha") if _hay_tabla("tipo_ficha") else None
            elif nombre == "modo_balance":
                if v not in (None, "") and v not in _BALANCES:
                    raise ValueError(_EL)
                out[nombre] = v or None
            elif nombre == "modo_canal":
                if v not in (None, "") and v not in _CANALES:
                    raise ValueError(_EL)
                out[nombre] = v or None
            elif nombre == "id_senal":
                out[nombre] = _ref(v, "senal", "id_senal") if _hay_tabla("senal") else None
            elif nombre == "id_formato":
                out[nombre] = _ref(v, "tipo_formato_senal", "id_formato") if _hay_tabla("tipo_formato_senal") else None
        except ValueError as ex:
            errores[nombre] = str(ex)
    if out.get("id_formato") is not None and out.get("id_senal") is None and "id_senal" not in errores:
        errores["id_senal"] = "Elegí una señal para usar un formato"
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    return out


def _formato(v):
    return (v["id_tipo_ficha"], v["modo_balance"], v["modo_canal"])


def conector_alta(id_equipo, valores):
    id_eq = _id(id_equipo)
    if not _existe("equipo", "id_equipo", id_eq):
        raise ErrorSinCambios(f"No existe el equipo {id_eq}")
    v = _normalizar_conector(valores, editando=False)
    M = _M()
    id_ = M.agregar_conector_retorna_id(v["nombre"], id_eq, v["id_tipo_conector"], None, None, None)
    if any(x is not None for x in _formato(v)):
        M.establecer_formato_conector(id_, *_formato(v))
    if v["id_senal"] is not None:
        M.establecer_senal_en_conector(id_, v["id_senal"], v["id_formato"])
    return {"id": id_, "nombre": v["nombre"], "valores": _valores_conector(_conector_o_error(id_))}


def conector_modificar(id, valores):
    id_ = _id(id)
    previa = _conector_o_error(id_)
    v = _normalizar_conector(valores, editando=True)
    anterior = _valores_conector(previa)
    with _M()._conn_ctx() as conn:       # nombre y tipo: la imagen y las coordenadas del conector quedan como están
        conn.execute("UPDATE conector SET nombre=?, id_tipo_conector=? WHERE id_conector=?", (v["nombre"], v["id_tipo_conector"], id_))
    M = _M()
    if _formato(v) != _formato(anterior):        # en una base vieja escribirlo migra el esquema; no se migra por guardar otro campo
        M.establecer_formato_conector(id_, *_formato(v))
    if (v["id_senal"], v["id_formato"]) != (anterior["id_senal"], anterior["id_formato"]):
        if v["id_senal"] is None:
            M.quitar_senal_en_conector(id_)
        else:
            M.establecer_senal_en_conector(id_, v["id_senal"], v["id_formato"])
    return {"id": id_, "nombre": v["nombre"], "anterior": anterior, "valores": _valores_conector(_conector_o_error(id_))}


def conector_baja(id, solo_si_sin_uso=False):
    """Borra el conector (las FK arrastran sus conexiones, su señal, etc.). Con `solo_si_sin_uso` se niega si arrastra algo."""
    id_ = _id(id)
    previa = _conector_o_error(id_)
    usos = _usos("conector", [id_])
    if solo_si_sin_uso and usos:
        raise ErrorSinCambios("El conector ya tiene conexiones u otros datos asociados: no se elimina.")
    fila = _fila_cruda("conector", "id_conector", id_)
    _M().eliminar_conector(id_)
    return {"id": id_, "nombre": previa["nombre"], "fila": fila, "usos": usos}


def conector_restaurar(id, fila):
    """Reinserta un conector con su id original (deshacer de una baja SIN uso)."""
    id_ = _id(id)
    if isinstance(fila, dict) and fila.get("id_equipo") is not None and not _existe("equipo", "id_equipo", fila["id_equipo"]):
        raise ErrorSinCambios("El equipo del conector ya no existe: no se restaura.")
    _reinsertar("conector", "id_conector", id_, fila)
    return {"id": id_, "nombre": _conector_o_error(id_)["nombre"]}


# ── Extremo desconectado (equipo FANTASMA) ───────────────────────────────────

def _estado_extremo(id_cable):
    """Lo que hace falta para decidir si se puede marcar un extremo desconectado y de qué lado. `lado` = «A» (la punta que falta es
    la del conector OUT) o «B» (la del IN); None si no se puede inferir (el cable no tiene extremos o el único es un extremo suelto)."""
    M = _M()
    extremos = M.devolver_extremos_de_cable(id_cable)
    lado, nombre_tipo = None, None
    if len(extremos) == 1:
        nombre_tipo = extremos[0][3]
        lado = "B" if nombre_tipo == "OUT" else "A" if nombre_tipo == "IN" else None
    motivo = None
    if len(extremos) >= 2:
        motivo = "Este cable ya tiene sus dos extremos documentados."
    elif not M.devolver_id_tipo_equipo_fantasma():
        motivo = "No hay ningún tipo de equipo con rol FANTASMA en el catálogo. Marcá uno (Catálogos → Tipos de equipo) antes de usar esta acción."
    return {"n_extremos": len(extremos), "lado": lado, "nombre_tipo": nombre_tipo, "puede": motivo is None, "motivo": motivo}


def cable_extremo_formulario(id_cable):
    """Si se puede marcar un extremo desconectado en este cable y, cuando ya hay un extremo con conector IN/OUT, de qué lado va."""
    id_ = _id(id_cable)
    cod = _b()._one("SELECT codigo FROM cable WHERE id_cable=?", (id_,))
    if cod is None:
        raise ErrorSinCambios(f"No existe el cable {id_}")
    return {"id_cable": id_, "codigo": cod["codigo"], **_estado_extremo(id_)}


def cable_extremo_desconectado(id_cable, lado=None):
    """Crea un equipo FANTASMA «EXTREMO A|B DESCONECTADO <código>» con un conector OUT (lado A) o IN (lado B) ya conectado al cable.
    Si el cable tiene un extremo con conector IN/OUT el lado se infiere (opuesto); si no, `lado` es obligatorio. Se valida todo antes
    de escribir y, si algo falla a mitad, se borra el equipo recién creado."""
    id_ = _id(id_cable)
    cod = _b()._one("SELECT codigo FROM cable WHERE id_cable=?", (id_,))
    if cod is None:
        raise ErrorSinCambios(f"No existe el cable {id_}")
    est = _estado_extremo(id_)
    if not est["puede"]:
        raise ErrorSinCambios(est["motivo"])
    lado = est["lado"] or lado
    if lado not in ("A", "B"):
        raise ErrorCampos("Hay datos que corregir", {"lado": _OB if lado in (None, "") else _EL})
    M = _M()
    tipo_conector = "OUT" if lado == "A" else "IN"
    id_tipo_equipo = M.devolver_id_tipo_equipo_fantasma()
    id_tipo_conector = M.devolver_id_tipo_conector_por_nombre(tipo_conector)
    if not id_tipo_conector:
        raise ErrorSinCambios(f"No hay ningún tipo de conector llamado '{tipo_conector}' en el catálogo.")
    nombre = f"EXTREMO {lado} DESCONECTADO {cod['codigo'] or '#' + str(id_)}"
    id_equipo = M.alta_equipo_retorna_id(id_tipo_equipo, None, None, None, None, nombre, None, None, None)
    try:
        id_conector = M.agregar_conector_retorna_id(tipo_conector, id_equipo, id_tipo_conector, None, None, None)
        M.alta_conexion(id_, id_conector)
        id_conexion = _b()._one("SELECT MAX(id_conexion) AS m FROM conexion WHERE id_cable=? AND id_conector=?", (id_, id_conector))["m"]
    except Exception:
        try:
            M.eliminar_equipo(id_equipo)
        except Exception:                # noqa: BLE001
            pass
        raise
    return {"id_equipo": id_equipo, "id_conector": id_conector, "id_conexion": id_conexion, "nombre": nombre, "lado": lado}


def cable_extremo_deshacer(id_equipo, id_conexion):
    """Deshace «extremo desconectado»: borra el equipo FANTASMA recién creado, su conector y su conexión. Se niega si ya tiene
    algo más (otro conector, otra conexión, datos asociados) o si la conexión no es la que se creó."""
    id_eq, id_cx = _id(id_equipo), _id(id_conexion)
    _equipo_o_error(id_eq)
    fila = _b()._one("SELECT cx.id_conexion FROM conexion cx JOIN conector c ON c.id_conector = cx.id_conector "
                     "WHERE cx.id_conexion=? AND c.id_equipo=?", (id_cx, id_eq))
    n_con = _b()._one("SELECT COUNT(*) AS n FROM conector WHERE id_equipo=?", (id_eq,))["n"]
    usos = {u["tabla"]: u["n"] for u in _usos("equipo", [id_eq]) if u["tabla"] not in _PROPIAS}
    if fila is None or n_con != 1 or usos != {"conector": 1, "conexion": 1}:
        raise ErrorSinCambios("El equipo ya tiene otros datos asociados: no se elimina.")
    _M().eliminar_equipo(id_eq)
    return {"id_equipo": id_eq}


LECTURAS = (equipo_formulario, equipo_usos, equipo_plantilla, conector_formulario, conector_usos, cable_extremo_formulario)
ESCRITURAS = (equipo_alta, equipo_alta_rapida, equipo_modificar, equipo_baja, equipo_restaurar,
              conector_alta, conector_modificar, conector_baja, conector_restaurar,
              cable_extremo_desconectado, cable_extremo_deshacer)
