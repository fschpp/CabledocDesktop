"""CableDoc Web — ABM de catálogos básicos (plan_pyodide_v1.md, Fase B.2).

Son las PRIMERAS funciones de escritura del bridge. Se registran en `bridge.FUNCIONES`
(ver el final de bridge.py), así que se llaman igual que las de lectura:
`bridge.call("catalogo_alta", '{"catalogo": "marca", "valores": {"nombre": "Sony"}}')`.

Catálogos (clave → tabla): marca, tipo_equipo, tipo_conector, tipo_cable, tipo_ficha,
senal, formato_senal (tipo_formato_senal) e imagen. Cada uno se describe una sola vez en
`_CATALOGOS` (campos, validación, qué tablas lo usan y qué pasa con ellas al borrarlo).

Funciones:
  catalogo_lista(catalogo)                        → {catalogo, esquema, filas}   (solo lectura)
  catalogo_alta(catalogo, valores)                → {id, fila}
  catalogo_modificar(catalogo, id, valores)       → {id, anterior, fila}   (`valores` reemplaza TODOS los campos)
  catalogo_baja(catalogo, id, solo_si_sin_uso)    → {id, anterior, usos}
  catalogo_restaurar(catalogo, id, valores)       → {id, fila}   (reinserta con el MISMO id: sirve para deshacer una baja)

Reglas de diseño:
  - Las escrituras pasan por los métodos de `Modelo` (los mismos que usa el desktop), no por SQL
    propio: así los efectos laterales (p. ej. recalcular la referencia virtual de los frames al
    cambiar un rol de señal) son idénticos. La única excepción es `catalogo_restaurar`, que necesita
    fijar el id.
  - Se valida TODO antes de escribir. Un error de validación es `ErrorCampos` (mensajes por campo,
    claves de i18n en español): bridge.call lo devuelve como {"ok": false, "campos": {...}} y NO
    marca la respuesta como `escribio` (no hay nada que persistir).
  - No hay "baja lógica": borrar es borrar. Las FK de la base anulan (SET NULL) o arrastran
    (CASCADE) los registros que usaban el valor; `catalogo_lista` informa cuántos son, por tabla,
    para que la UI lo muestre antes de confirmar.
  - Nombres repetidos: se rechaza un alta (o un cambio de nombre) cuyo nombre ya existe en ese
    catálogo, sin distinguir mayúsculas ni espacios de más. El desktop sí lo permite; una fila que
    ya está duplicada se puede seguir editando mientras no se le cambie el nombre. Las imágenes no
    se controlan (dos registros pueden apuntar al mismo archivo).
  - Las columnas `nombre` de tipo_equipo y tipo_conector están declaradas INTEGER en el esquema:
    SQLite devuelve int para un nombre que sea solo dígitos. Por eso se compara siempre con str().
"""
import math
import sqlite3


class ErrorSinCambios(ValueError):
    """Falló antes de tocar la base (id inexistente, catálogo desconocido…). bridge.call lo trata
    como mensaje para el usuario y no pide persistir."""
    sin_cambios = True


class ErrorCampos(ErrorSinCambios):
    """Validación por campo: `campos` = {nombre_del_campo: clave de i18n con el motivo}."""

    def __init__(self, mensaje, campos=None):
        super().__init__(mensaje)
        self.campos = dict(campos or {})


def _b():
    import bridge          # import diferido: bridge importa este módulo al final de su propio import
    return bridge


def _M():
    return _b()._M()


# ── Descripción de los catálogos ─────────────────────────────────────────────

ANULA, BORRA = "anula", "borra"     # efecto de borrar el valor sobre la tabla que lo usa (SET NULL / CASCADE)

_NATURALEZAS = ("ANALOGICA", "DIGITAL", "HIBRIDA", "DATOS")           # CHECK de tipo_cable.naturaleza_senal
_BALANCES = ("BALANCEADO", "DESBALANCEADO", "NA")                      # CHECK de tipo_ficha.modo_balance_default
_CANALES = ("MONO", "ESTEREO", "NA")                                   # CHECK de tipo_ficha.modo_canal_default
_CONTENIDOS = ("VIDEO", "AUDIO", "DATOS", "EMBEBIDO")                  # los que ofrece el desktop (el campo es libre)


def _roles():
    return list(_M().ROLES_SENAL)       # sin lista propia: la fuente de verdad es Modelo (incluye FANTASMA)


def _c(nombre, tipo="texto", requerido=False, opciones=None, minimo=None, largo=None, columna=None,
       opcional=False, sugeridos=None):
    """Un campo. `columna` = nombre real en la tabla si difiere; `opcional` = la columna puede no existir en
    una base vieja (se lee como NULL); `sugeridos` = valores que la UI ofrece en un campo de texto libre."""
    return {"nombre": nombre, "tipo": tipo, "requerido": requerido, "opciones": opciones, "minimo": minimo,
            "largo": largo, "columna": columna or nombre, "opcional": opcional, "sugeridos": sugeridos}


_CATALOGOS = {
    "marca": {
        "tabla": "marca", "pk": "id_marca", "orden": "lower(nombre)", "unico": "nombre",
        "campos": [_c("nombre", requerido=True, largo=120)],
        "usos": [("equipo", "id_marca", ANULA), ("equipo_catalogo", "id_marca", ANULA),
                 ("frame", "id_marca", ANULA), ("frame_catalogo", "id_marca", ANULA)],
    },
    "tipo_equipo": {
        "tabla": "tipo_equipo", "pk": "id_tipo_equipo", "orden": "lower(nombre)", "unico": "nombre",
        "campos": [_c("nombre", requerido=True, largo=120),
                   _c("rol_senal", "select", requerido=True, opciones=_roles)],
        "usos": [("equipo", "id_tipo_equipo", ANULA), ("equipo_catalogo", "id_tipo_equipo", ANULA),
                 ("plantilla_conector", "id_tipo_equipo", BORRA), ("regla_logica", "id_tipo_equipo", BORRA),
                 ("estrategia_visual", "id_tipo_equipo", BORRA)],
    },
    "tipo_conector": {
        "tabla": "tipo_conector", "pk": "id_tipo_conector", "orden": "lower(nombre)", "unico": "nombre",
        "campos": [_c("nombre", requerido=True, largo=120),
                   _c("es_referencia_generada", "bool", opcional=True)],
        "asegurar": "asegurar_columnas_control_idioma",
        "usos": [("conector", "id_tipo_conector", ANULA), ("conector_catalogo", "id_tipo_conector", ANULA),
                 ("plantilla_conector", "id_tipo_conector", BORRA)],
    },
    "tipo_cable": {
        "tabla": "tipo_cable", "pk": "id_tipo_cable", "orden": "lower(nombre)", "unico": "nombre",
        "campos": [_c("nombre", requerido=True, largo=120),
                   _c("naturaleza_senal", "select", opciones=_NATURALEZAS),
                   _c("long_max_balanceado_m", "numero", minimo=0, columna="longitud_maxima_recomendada_balanceado_m"),
                   _c("long_max_desbalanceado_m", "numero", minimo=0,
                      columna="longitud_maxima_recomendada_desbalanceado_m"),
                   _c("ancho_banda_mhz", "numero", minimo=0)],
        "asegurar": "asegurar_columnas_riesgo_senal",
        "usos": [("cable", "id_tipo_cable", ANULA)],
    },
    "tipo_ficha": {
        "tabla": "tipo_ficha", "pk": "id_tipo_ficha", "orden": "lower(nombre)", "unico": "nombre",
        "campos": [_c("nombre", requerido=True, largo=120),
                   _c("n_conductores", "entero", minimo=1),
                   _c("modo_balance_default", "select", opciones=_BALANCES),
                   _c("modo_canal_default", "select", opciones=_CANALES),
                   _c("ancho_banda_mhz", "numero", minimo=0)],
        "asegurar": "asegurar_columnas_riesgo_senal",
        "usos": [("cable", "id_tipo_ficha", ANULA), ("conector", "id_tipo_ficha", ANULA),
                 ("conexion", "id_tipo_ficha", ANULA), ("catalogo_simbolo_conector", "id_tipo_ficha", BORRA)],
    },
    "senal": {
        "tabla": "senal", "pk": "id_senal", "orden": "lower(nombre)", "unico": "nombre", "tabla_opcional": True,
        "campos": [_c("nombre", requerido=True, largo=120),
                   _c("tipo_contenido", largo=40, sugeridos=_CONTENIDOS),
                   _c("descripcion", "texto_largo", largo=500)],
        "asegurar": "asegurar_tablas_senal",
        "usos": [("senal_en_conector", "id_senal", BORRA), ("senal_linaje", "id_senal_hijo", BORRA),
                 ("senal_linaje", "id_senal_padre", BORRA)],
    },
    "formato_senal": {
        "tabla": "tipo_formato_senal", "pk": "id_formato", "orden": "lower(nombre)", "unico": "nombre",
        "tabla_opcional": True,
        "campos": [_c("nombre", requerido=True, largo=120)],
        "asegurar": "asegurar_tablas_senal",
        "usos": [("senal_en_conector", "id_formato", ANULA)],
    },
    "imagen": {
        "tabla": "imagen", "pk": "id_imagen", "orden": "lower(path_archivo), id_imagen", "unico": None,
        "campos": [_c("path_archivo", requerido=True, largo=260),
                   _c("descripcion", largo=500)],
        "usos": [("conector", "id_imagen", ANULA), ("equipo", "id_imagen", ANULA), ("frame", "id_imagen", ANULA),
                 ("slot", "id_imagen", ANULA), ("equipo_catalogo", "id_imagen", ANULA),
                 ("frame_catalogo", "id_imagen", ANULA), ("conector_catalogo", "id_imagen", ANULA),
                 ("imagen_senal_conector", "id_imagen", BORRA)],
    },
}


def _spec(catalogo):
    sp = _CATALOGOS.get(catalogo)
    if sp is None:
        raise ErrorSinCambios(f"Catálogo desconocido: {catalogo!r}. Válidos: {', '.join(_CATALOGOS)}")
    return sp


def _opciones(c):
    o = c["opciones"]
    return None if o is None else list(o() if callable(o) else o)


def _esquema(sp):
    """Lo que la UI necesita para armar el formulario: nombre, tipo, requerido, opciones, mínimo, largo, sugeridos."""
    out = []
    for c in sp["campos"]:
        d = {"nombre": c["nombre"], "tipo": c["tipo"], "requerido": c["requerido"]}
        if c["opciones"] is not None:
            d["opciones"] = _opciones(c)
        if c["minimo"] is not None:
            d["minimo"] = c["minimo"]
        if c["largo"] is not None:
            d["largo"] = c["largo"]
        if c["sugeridos"]:
            d["sugeridos"] = list(c["sugeridos"])
        out.append(d)
    return out


def _id(v):
    try:
        if isinstance(v, bool):
            raise ValueError
        return int(v)
    except (TypeError, ValueError):
        raise ErrorSinCambios(f"Id inválido: {v!r}") from None


# ── Lectura ──────────────────────────────────────────────────────────────────

def _select(sp, sin_opcionales=False):
    cols = [f"{sp['pk']} AS id"]
    for c in sp["campos"]:
        origen = "NULL" if (sin_opcionales and c["opcional"]) else c["columna"]
        cols.append(f"{origen} AS {c['nombre']}")
    return f"SELECT {', '.join(cols)} FROM {sp['tabla']}"


def _leer(sp, donde="", params=(), orden=True):
    """Filas como dict {id, <campos>}. Tolera una base vieja: sin la columna opcional se lee como NULL y, si el
    catálogo es opcional (señales), sin la tabla es una lista vacía."""
    sql = _select(sp) + (f" WHERE {donde}" if donde else "") + (f" ORDER BY {sp['orden']}" if orden else "")
    b = _b()
    try:
        filas = b._rows(sql, params)
    except sqlite3.OperationalError:
        try:
            filas = b._rows(_select(sp, sin_opcionales=True) + (f" WHERE {donde}" if donde else "")
                            + (f" ORDER BY {sp['orden']}" if orden else ""), params)
        except sqlite3.OperationalError:
            if sp.get("tabla_opcional"):
                return []
            raise
    for f in filas:
        for c in sp["campos"]:
            if c["tipo"] == "bool":
                f[c["nombre"]] = bool(f[c["nombre"]])
    return filas


def _valores_de(sp, fila):
    return {c["nombre"]: fila[c["nombre"]] for c in sp["campos"]}


def _conteos(sp):
    """{tabla: {id: n}} y el efecto de cada una, con UNA consulta agrupada por tabla/columna que referencia al catálogo."""
    b, out = _b(), {}
    for tabla, col, efecto in sp["usos"]:
        try:
            filas = b._rows(f"SELECT {col} AS id, COUNT(*) AS n FROM {tabla} WHERE {col} IS NOT NULL GROUP BY {col}")
        except sqlite3.OperationalError:       # tabla o columna inexistente en una base vieja: nadie lo usa
            continue
        d = out.setdefault(tabla, {"efecto": efecto, "por_id": {}})
        for f in filas:
            d["por_id"][f["id"]] = d["por_id"].get(f["id"], 0) + f["n"]
    return out


def _usos_de(conteos, id_):
    usos = [{"tabla": t, "n": d["por_id"][id_], "efecto": d["efecto"]} for t, d in conteos.items() if d["por_id"].get(id_)]
    return usos


def catalogo_lista(catalogo):
    """Filas del catálogo con el detalle de uso de cada una. `usos` = [{tabla, n, efecto: anula|borra}] (solo n > 0)."""
    sp = _spec(catalogo)
    filas, conteos = _leer(sp), _conteos(sp)
    for f in filas:
        f["usos"] = _usos_de(conteos, f["id"])
        f["n_usos"] = sum(u["n"] for u in f["usos"])
    return {"catalogo": catalogo, "esquema": _esquema(sp), "filas": filas}


# ── Validación ───────────────────────────────────────────────────────────────

def _num(v):
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, (int, float)):
        x = float(v)
    elif isinstance(v, str):
        x = float(v.strip().replace(",", "."))
    else:
        raise ValueError
    if not math.isfinite(x):
        raise ValueError
    return x


def _valor(c, v):
    """Normaliza UN valor según su campo. Levanta ValueError con la clave de i18n del motivo."""
    t = c["tipo"]
    if t == "bool":
        return bool(v)
    if t in ("texto", "texto_largo"):
        s = None if v is None else str(v).strip()
        if not s:
            if c["requerido"]:
                raise ValueError("Obligatorio")
            return None
        if c["largo"] and len(s) > c["largo"]:
            raise ValueError("Texto demasiado largo")
        return s
    if t == "select":
        if v is None or v == "":
            if c["requerido"]:
                raise ValueError("Obligatorio")
            return None
        if v not in _opciones(c):
            raise ValueError("Elegí una opción válida")
        return v
    if t in ("numero", "entero"):
        if v is None or (isinstance(v, str) and not v.strip()):
            if c["requerido"]:
                raise ValueError("Obligatorio")
            return None
        try:
            x = _num(v)
        except ValueError:
            raise ValueError("Debe ser un número entero" if t == "entero" else "Debe ser un número") from None
        if t == "entero":
            if x != int(x):
                raise ValueError("Debe ser un número entero")
            x = int(x)
        if c["minimo"] is not None and x < c["minimo"]:
            raise ValueError("No puede ser negativo" if c["minimo"] == 0 else "Debe ser mayor que cero")
        return x
    raise ErrorSinCambios(f"Tipo de campo no soportado: {t}")


def _normalizar(sp, valores):
    if not isinstance(valores, dict):
        raise ErrorSinCambios("`valores` debe ser un objeto {campo: valor}")
    sobran = sorted(set(valores) - {c["nombre"] for c in sp["campos"]})
    if sobran:
        raise ErrorSinCambios(f"Campos desconocidos: {sobran}")
    out, errores = {}, {}
    for c in sp["campos"]:
        try:
            out[c["nombre"]] = _valor(c, valores.get(c["nombre"]))
        except ValueError as ex:
            errores[c["nombre"]] = str(ex)
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    return out


def _clave(s):
    return " ".join(str(s).split()).casefold()


def _verificar_unico(sp, v, id_=None, anterior=None):
    """Rechaza un nombre que ya existe en el catálogo. Si se está modificando y el nombre no cambió, no se controla."""
    campo = sp.get("unico")
    if not campo or v.get(campo) is None:
        return
    nuevo = _clave(v[campo])
    if anterior is not None and anterior.get(campo) is not None and _clave(anterior[campo]) == nuevo:
        return
    for f in _leer(sp, orden=False):
        if f["id"] != id_ and f[campo] is not None and _clave(f[campo]) == nuevo:
            raise ErrorCampos("Hay datos que corregir", {campo: "Ya existe uno con ese nombre"})


def _asegurar(sp):
    nombre = sp.get("asegurar")
    if nombre:
        getattr(_M(), nombre)()


def _ultimo_id(sp):
    """Id recién insertado para los alta de Modelo que no lo devuelven (marca, imagen). AUTOINCREMENT → el máximo."""
    return _b()._one(f"SELECT MAX({sp['pk']}) AS m FROM {sp['tabla']}")["m"]


def _fila_o_error(sp, id_):
    f = _leer(sp, f"{sp['pk']}=?", (id_,), orden=False)
    if not f:
        raise ErrorSinCambios(f"No existe el registro {id_} en {sp['tabla']}")
    return f[0]


# ── Escrituras por catálogo (siempre vía Modelo) ─────────────────────────────

def _alta(catalogo, sp, v):
    M = _M()
    if catalogo == "marca":
        M.alta_marca(v["nombre"])
        return _ultimo_id(sp)
    if catalogo == "tipo_equipo":
        return M.alta_tipo(v["nombre"], rol_senal=v["rol_senal"])
    if catalogo == "tipo_conector":
        id_ = M.agregar_tipo_conector(v["nombre"])
        M.establecer_es_referencia_generada_tipo_conector(id_, v["es_referencia_generada"])
        return id_
    if catalogo == "tipo_cable":
        id_ = M.alta_tipo_cable_retorna_id(v["nombre"])
        M.establecer_riesgo_tipo_cable(id_, v["naturaleza_senal"], v["long_max_balanceado_m"],
                                       v["long_max_desbalanceado_m"], v["ancho_banda_mhz"])
        return id_
    if catalogo == "tipo_ficha":
        id_ = M.alta_tipo_ficha_retorna_id(v["nombre"])
        M.establecer_riesgo_tipo_ficha(id_, v["n_conductores"], v["modo_balance_default"],
                                       v["modo_canal_default"], v["ancho_banda_mhz"])
        return id_
    if catalogo == "senal":
        return M.agregar_senal(v["nombre"], v["tipo_contenido"], v["descripcion"])
    if catalogo == "formato_senal":
        return M.agregar_tipo_formato_senal(v["nombre"])
    if catalogo == "imagen":
        M.alta_imagen(v["path_archivo"], v["descripcion"])
        return _ultimo_id(sp)
    raise ErrorSinCambios(f"Alta no soportada: {catalogo}")


def _modificar(catalogo, id_, v, anterior):
    M = _M()
    if catalogo == "marca":
        M.modificacion_marca(id_, v["nombre"])
    elif catalogo == "tipo_equipo":
        M.modificacion_tipo(id_, v["nombre"])
        if v["rol_senal"] != anterior["rol_senal"]:      # el desktop lo llama siempre; acá solo si cambió (evita recalcular frames de balde)
            M.establecer_rol_senal_tipo_equipo(id_, v["rol_senal"])
    elif catalogo == "tipo_conector":
        M.modificar_tipo_conector(id_, v["nombre"])
        M.establecer_es_referencia_generada_tipo_conector(id_, v["es_referencia_generada"])
    elif catalogo == "tipo_cable":
        M.modificacion_tipo_cable(id_, v["nombre"])
        M.establecer_riesgo_tipo_cable(id_, v["naturaleza_senal"], v["long_max_balanceado_m"],
                                       v["long_max_desbalanceado_m"], v["ancho_banda_mhz"])
    elif catalogo == "tipo_ficha":
        M.modificacion_tipo_ficha(id_, v["nombre"])
        M.establecer_riesgo_tipo_ficha(id_, v["n_conductores"], v["modo_balance_default"],
                                       v["modo_canal_default"], v["ancho_banda_mhz"])
    elif catalogo == "senal":
        M.modificar_senal(id_, v["nombre"], v["tipo_contenido"], v["descripcion"])
    elif catalogo == "formato_senal":
        M.modificar_tipo_formato_senal(id_, v["nombre"])
    elif catalogo == "imagen":
        M.modificacion_imagen(id_, v["path_archivo"], v["descripcion"])
    else:
        raise ErrorSinCambios(f"Modificación no soportada: {catalogo}")


_BAJAS = {"marca": "eliminar_marca", "tipo_equipo": "eliminar_tipo", "tipo_conector": "eliminar_tipo_conector",
          "tipo_cable": "eliminar_tipo_cable", "tipo_ficha": "eliminar_tipo_ficha", "senal": "eliminar_senal",
          "formato_senal": "eliminar_tipo_formato_senal", "imagen": "eliminar_imagen"}


# ── API ──────────────────────────────────────────────────────────────────────

def catalogo_alta(catalogo, valores):
    sp = _spec(catalogo)
    v = _normalizar(sp, valores)
    _verificar_unico(sp, v)
    nuevo = _alta(catalogo, sp, v)
    return {"id": nuevo, "fila": _fila_o_error(sp, nuevo)}


def catalogo_modificar(catalogo, id, valores):
    sp, id_ = _spec(catalogo), _id(id)
    previa = _fila_o_error(sp, id_)
    v = _normalizar(sp, valores)
    anterior = _valores_de(sp, previa)
    _verificar_unico(sp, v, id_, anterior)
    _modificar(catalogo, id_, v, anterior)
    return {"id": id_, "anterior": anterior, "fila": _fila_o_error(sp, id_)}


def catalogo_baja(catalogo, id, solo_si_sin_uso=False):
    """Borra el registro. Con `solo_si_sin_uso` se niega si algo lo usa (lo pide el "deshacer" de un alta, para no
    arrastrar nada que se haya asignado mientras tanto)."""
    sp, id_ = _spec(catalogo), _id(id)
    previa = _fila_o_error(sp, id_)
    usos = _usos_de(_conteos(sp), id_)
    if solo_si_sin_uso and usos:
        raise ErrorSinCambios("El registro ya se usa en otros datos: no se elimina.")
    getattr(_M(), _BAJAS[catalogo])(id_)
    return {"id": id_, "anterior": _valores_de(sp, previa), "usos": usos}


def catalogo_restaurar(catalogo, id, valores):
    """Reinserta un registro con su id original (deshacer de una baja SIN uso: lo que lo usaba ya no se puede reconstruir)."""
    sp, id_ = _spec(catalogo), _id(id)
    if _leer(sp, f"{sp['pk']}=?", (id_,), orden=False):
        raise ErrorSinCambios(f"Ya existe un registro con el id {id_}: no se restaura.")
    v = _normalizar(sp, valores)
    _verificar_unico(sp, v)
    _asegurar(sp)
    cols = [sp["pk"]] + [c["columna"] for c in sp["campos"]]
    vals = [id_] + [(int(v[c["nombre"]]) if c["tipo"] == "bool" else v[c["nombre"]]) for c in sp["campos"]]
    with _M()._conn_ctx() as conn:
        conn.execute(f"INSERT INTO {sp['tabla']} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
    return {"id": id_, "fila": _fila_o_error(sp, id_)}


LECTURAS = (catalogo_lista,)
ESCRITURAS = (catalogo_alta, catalogo_modificar, catalogo_baja, catalogo_restaurar)
