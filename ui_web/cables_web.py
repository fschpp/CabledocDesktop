"""CableDoc Web — ABM de cables y conexiones (plan_pyodide_v1.md, Fase B.3).

Se registra en `bridge.FUNCIONES` junto con catalogos_web.py (ver el final de bridge.py) y se llama igual que el resto:
`bridge.call("cable_alta", '{"valores": {"codigo": "C-001", "estado": "VERIFICADO"}}')`.

Lecturas:
  cable_formulario(id_cable)                     → {id_cable, esquema, valores}   (valores = None en un alta)
  cable_usos(id_cable)                           → {id_cable, codigo, usos}       (qué arrastra borrarlo)
  conexion_formulario(id_conexion, id_cable, id_conector) → {id_conexion, esquema, valores}
  conexion_usos(id_conexion)                     → {id_conexion, usos}

Escrituras:
  cable_alta(valores)                            → {id, codigo, valores}
  cable_temporal()                               → {id, codigo}                   (código SIN ETIQUETA NNNN, estado TEMPORAL)
  cable_modificar(id, valores)                   → {id, codigo, anterior, valores}  (`valores` reemplaza TODOS los campos)
  cable_baja(id, solo_si_sin_uso)                → {id, codigo, anterior, interno, id_cable_fusionado, usos}
  cable_restaurar(id, valores, interno, id_cable_fusionado) → {id, codigo}        (deshacer de una baja SIN uso)
  cable_fusionar(id_principal, id_secundario, codigo, estado) → {…, conexiones, anterior}
  cable_fusion_deshacer(id_principal, id_secundario, anterior, conexiones) → {…}
  conexion_alta(id_cable, id_conector)           → {id, valores, avisos}
  conexion_modificar(id, valores)                → {id, anterior, valores, avisos}
  conexion_baja(id, solo_si_sin_uso)             → {id, anterior, interno, usos}
  conexion_restaurar(id, valores, interno)       → {id, valores}

Reglas de diseño (mismas que catalogos_web.py, B.2):
  - Las escrituras pasan por los métodos de `Modelo` (los que usa el desktop). Excepciones, donde Modelo no alcanza:
    reinsertar con el MISMO id (restaurar, para "deshacer") y deshacer una fusión (una sola transacción).
  - Se valida TODO antes de escribir. Un error de validación es `ErrorCampos` (claves de i18n por campo): bridge.call lo
    devuelve como {"ok": false, "campos": {...}} y no pide persistir.
  - Diferencias con el desktop (todas a favor de no dejar la base inconsistente):
      · el código de cable no se puede repetir (la columna es UNIQUE: el desktop revienta con IntegrityError; acá se
        rechaza sin distinguir mayúsculas ni espacios de más, y una fila ya repetida se puede seguir editando mientras no
        se le cambie el código);
      · editar un cable FUSIONADO no le cambia el estado (el combo del desktop no lo ofrece y lo pisa con VERIFICADO);
      · editar una conexión conserva `es_conexion_interna` (el desktop la pisa con 0);
      · no se pueden repetir cable+conector (misma conexión dos veces) ni fusionar un cable ya fusionado, ni usar como
        código definitivo el de OTRO cable (el desktop falla a mitad de la fusión: ya movió las conexiones);
      · la ficha del cable, el armado y el override de ancho de banda solo se escriben si cambiaron (en una base vieja
        escribirlos migra el esquema; no se migra por guardar otro campo).
  - Un cable con conexiones se puede borrar: las FK arrastran sus conexiones (y las extensiones, escenarios e incidentes que
    lo usan). `cable_usos` lo informa antes de confirmar; el "deshacer" de una baja solo se ofrece si no arrastró nada.
  - Las conexiones no tienen baja lógica. Un alta/baja/edición recalcula la referencia virtual del frame del equipo (lo hace
    Modelo, igual que el desktop).
"""
import sqlite3

from catalogos_web import ErrorCampos, ErrorSinCambios, _c, _clave, _id, _valor


def _b():
    import bridge          # import diferido: bridge importa este módulo al final de su propio import
    return bridge


def _M():
    return _b()._M()


ESTADOS = ("VERIFICADO", "TEMPORAL", "EN_REVISION")       # los que ofrece el desktop (FUSIONADO lo pone la fusión)
ESTADOS_FUSION = ("VERIFICADO", "TEMPORAL")
_ARMADOS = ((1, "Correcto"), (0, "Mal armado"))
_OB, _NUM, _EL = "Obligatorio", "Debe ser un número", "Elegí una opción válida"


# ── Lectura de filas ─────────────────────────────────────────────────────────

_CABLE_BASE = ("id_cable, codigo, COALESCE(estado,'VERIFICADO') AS estado, id_tipo_cable, id_tipo_ficha, longitud, unidad_longitud, "
               "metraje_impreso_primer_extremo AS metraje_ext1, metraje_impreso_segundo_extremo AS metraje_ext2, "
               "unidad_metraje_impreso AS unidad_metraje, notas_relevamiento, COALESCE(es_cable_conexion_interna,0) AS interno, "
               "id_cable_fusionado")
_CABLE_EXTRA = "ancho_banda_mhz_override AS ancho_banda_override, es_armado_correcto, detalle_armado"
_CAMPOS_CABLE = ("codigo", "estado", "id_tipo_cable", "id_tipo_ficha", "longitud", "unidad_longitud", "metraje_ext1", "metraje_ext2",
                 "unidad_metraje", "ancho_banda_override", "es_armado_correcto", "detalle_armado", "notas_relevamiento")
_SOLO_EDICION = ("ancho_banda_override", "es_armado_correcto", "detalle_armado")


def _leer_cable(id_):
    """Fila del cable como dict, o None. Tolera una base vieja sin las columnas de override/armado (se leen como NULL)."""
    b = _b()
    try:
        r = b._one(f"SELECT {_CABLE_BASE}, {_CABLE_EXTRA} FROM cable WHERE id_cable=?", (id_,))
    except sqlite3.OperationalError:
        r = b._one(f"SELECT {_CABLE_BASE}, NULL AS ancho_banda_override, NULL AS es_armado_correcto, NULL AS detalle_armado "
                   "FROM cable WHERE id_cable=?", (id_,))
    return r


def _valores_cable(fila):
    return {k: fila[k] for k in _CAMPOS_CABLE}


def _cable_o_error(id_):
    f = _leer_cable(id_)
    if f is None:
        raise ErrorSinCambios(f"No existe el cable {id_}")
    return f


_CONEXION_BASE = "id_conexion, id_cable, id_conector, COALESCE(es_conexion_interna,0) AS interno"
_CAMPOS_CONEXION = ("id_cable", "id_conector", "id_tipo_ficha", "es_armado_correcto", "detalle_armado")


def _leer_conexion(id_):
    b = _b()
    try:
        return b._one(f"SELECT {_CONEXION_BASE}, id_tipo_ficha, es_armado_correcto, detalle_armado FROM conexion WHERE id_conexion=?", (id_,))
    except sqlite3.OperationalError:
        try:
            return b._one(f"SELECT {_CONEXION_BASE}, id_tipo_ficha, NULL AS es_armado_correcto, NULL AS detalle_armado "
                          "FROM conexion WHERE id_conexion=?", (id_,))
        except sqlite3.OperationalError:
            return b._one(f"SELECT {_CONEXION_BASE}, NULL AS id_tipo_ficha, NULL AS es_armado_correcto, NULL AS detalle_armado "
                          "FROM conexion WHERE id_conexion=?", (id_,))


def _conexion_o_error(id_):
    f = _leer_conexion(id_)
    if f is None:
        raise ErrorSinCambios(f"No existe la conexión {id_}")
    return f


def _valores_conexion(fila):
    return {k: fila[k] for k in _CAMPOS_CONEXION}


def _existe(tabla, pk, valor):
    return _b()._one(f"SELECT 1 AS x FROM {tabla} WHERE {pk}=?", (valor,)) is not None


def _contar(sql, params=()):
    """COUNT(*) tolerando tablas/columnas que una base vieja no tiene (nadie las usa → 0)."""
    try:
        r = _b()._one(sql, params)
    except sqlite3.OperationalError:
        return 0
    return int(r["n"]) if r else 0


# ── Validación ───────────────────────────────────────────────────────────────

def _ref(v, tabla, pk):
    """Referencia opcional a un registro de un catálogo: None/'' → None; si no es un id que exista → ValueError."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, bool):
            raise ValueError
        i = int(v)
    except (TypeError, ValueError):
        raise ValueError(_EL) from None
    if not _existe(tabla, pk, i):
        raise ValueError(_EL)
    return i


def _armado(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool) or v not in (0, 1, "0", "1"):
        raise ValueError(_EL)
    return int(v)


_CAMPO_TXT = {
    "codigo": _c("codigo", largo=120),
    "unidad_longitud": _c("unidad_longitud", largo=20),
    "unidad_metraje": _c("unidad_metraje", largo=20),
    "detalle_armado": _c("detalle_armado", "texto_largo", largo=500),
    "notas_relevamiento": _c("notas_relevamiento", "texto_largo", largo=2000),
    "longitud": _c("longitud", "numero", minimo=0),
    "metraje_ext1": _c("metraje_ext1", "numero", minimo=0),
    "metraje_ext2": _c("metraje_ext2", "numero", minimo=0),
    "ancho_banda_override": _c("ancho_banda_override", "numero", minimo=0),
}


def _normalizar_cable(valores, editando, estado_actual=None):
    """Valores del formulario de cable → dict normalizado (vacío = None). Levanta ErrorCampos con TODOS los errores."""
    if not isinstance(valores, dict):
        raise ErrorSinCambios("`valores` debe ser un objeto {campo: valor}")
    permitidos = set(_CAMPOS_CABLE) if editando else set(_CAMPOS_CABLE) - set(_SOLO_EDICION)
    sobran = sorted(set(valores) - permitidos)
    if sobran:
        raise ErrorSinCambios(f"Campos desconocidos: {sobran}")
    out, errores = {}, {}
    for nombre in _CAMPOS_CABLE:
        if nombre not in permitidos:
            continue
        v = valores.get(nombre)
        try:
            if nombre in _CAMPO_TXT:
                out[nombre] = _valor(_CAMPO_TXT[nombre], v)
            elif nombre == "estado":
                if v is None or v == "":
                    raise ValueError(_OB)
                if v not in ESTADOS and v != estado_actual:
                    raise ValueError(_EL)
                out[nombre] = v
            elif nombre == "id_tipo_cable":
                out[nombre] = _ref(v, "tipo_cable", "id_tipo_cable")
            elif nombre == "id_tipo_ficha":
                out[nombre] = _ref(v, "tipo_ficha", "id_tipo_ficha")
            elif nombre == "es_armado_correcto":
                out[nombre] = _armado(v)
        except ValueError as ex:
            errores[nombre] = str(ex)
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    return out


def _verificar_codigo(codigo, id_=None, anterior=None):
    """El código de cable es UNIQUE en la base: se rechaza uno repetido (sin distinguir mayúsculas ni espacios de más)."""
    if codigo is None:
        return
    nuevo = _clave(codigo)
    if anterior is not None and _clave(anterior) == nuevo:
        return
    for f in _b()._rows("SELECT id_cable, codigo FROM cable WHERE codigo IS NOT NULL"):
        if f["id_cable"] != id_ and _clave(f["codigo"]) == nuevo:
            raise ErrorCampos("Hay datos que corregir", {"codigo": "Ya existe un cable con ese código"})


# ── Formularios ──────────────────────────────────────────────────────────────

def _op(filas, pk, etiqueta="nombre"):
    return [{"valor": f[pk], "etiqueta": f[etiqueta] if f[etiqueta] is not None else f"#{f[pk]}"} for f in filas]


def _campo(nombre, tipo, requerido=False, opciones=None, minimo=None, largo=None, **extra):
    d = {"nombre": nombre, "tipo": tipo, "requerido": requerido}
    if opciones is not None:
        d["opciones"] = opciones
    if minimo is not None:
        d["minimo"] = minimo
    if largo is not None:
        d["largo"] = largo
    d.update(extra)
    return d


def _esquema_cable(editando, estado_actual=None):
    b = _b()
    estados = list(ESTADOS) + ([estado_actual] if estado_actual and estado_actual not in ESTADOS else [])
    esq = [
        _campo("codigo", "texto", largo=120),
        _campo("estado", "select", True, [{"valor": e, "etiqueta": e} for e in estados]),
        _campo("id_tipo_cable", "select", opciones=_op(b._rows("SELECT id_tipo_cable, nombre FROM tipo_cable ORDER BY lower(nombre)"), "id_tipo_cable")),
        _campo("id_tipo_ficha", "select", opciones=_op(b._rows("SELECT id_tipo_ficha, nombre FROM tipo_ficha ORDER BY lower(nombre)"), "id_tipo_ficha")),
        _campo("longitud", "numero", minimo=0), _campo("unidad_longitud", "texto", largo=20),
        _campo("metraje_ext1", "numero", minimo=0), _campo("metraje_ext2", "numero", minimo=0),
        _campo("unidad_metraje", "texto", largo=20),
    ]
    if editando:
        esq += [_campo("ancho_banda_override", "numero", minimo=0),
                _campo("es_armado_correcto", "select", opciones=[{"valor": v, "etiqueta": e} for v, e in _ARMADOS]),
                _campo("detalle_armado", "texto_largo", largo=500)]
    esq.append(_campo("notas_relevamiento", "texto_largo", largo=2000))
    return esq


def cable_formulario(id_cable=None):
    """Esquema del formulario (con las opciones ya resueltas) y, al editar, los valores actuales del cable."""
    if id_cable is None:
        return {"id_cable": None, "esquema": _esquema_cable(False), "valores": None}
    id_ = _id(id_cable)
    f = _cable_o_error(id_)
    return {"id_cable": id_, "esquema": _esquema_cable(True, f["estado"]), "valores": _valores_cable(f)}


def cable_usos(id_cable):
    """Qué arrastra borrar el cable: [{tabla, n, efecto: anula|borra}] (solo n > 0)."""
    id_ = _id(id_cable)
    f = _cable_o_error(id_)
    usos = []

    def sumar(tabla, n, efecto):
        if n:
            usos.append({"tabla": tabla, "n": n, "efecto": efecto})

    sumar("conexion", _contar("SELECT COUNT(*) AS n FROM conexion WHERE id_cable=?", (id_,)), "borra")
    sumar("extension_cable", _contar(
        "SELECT COUNT(*) AS n FROM extension_cable WHERE id_conexion_a IN (SELECT id_conexion FROM conexion WHERE id_cable=?) "
        "OR id_conexion_b IN (SELECT id_conexion FROM conexion WHERE id_cable=?)", (id_, id_)), "borra")
    sumar("escenario_cambio", _contar("SELECT COUNT(*) AS n FROM escenario_cambio WHERE id_cable=?", (id_,)), "borra")
    sumar("incidente_cable", _contar("SELECT COUNT(*) AS n FROM incidente_cable WHERE id_cable=?", (id_,)), "borra")
    sumar("diagnostico_sesion", _contar("SELECT COUNT(*) AS n FROM diagnostico_sesion WHERE id_cable_resultado=?", (id_,)), "anula")
    return {"id_cable": id_, "codigo": f["codigo"], "usos": usos}


# ── Escrituras de cable ──────────────────────────────────────────────────────

def _ultimo_id_cable():
    return _b()._one("SELECT MAX(id_cable) AS m FROM cable")["m"]


def cable_alta(valores):
    v = _normalizar_cable(valores, editando=False)
    _verificar_codigo(v["codigo"])
    _M().agregar_cable(v["codigo"], v["longitud"], v["id_tipo_cable"], v["id_tipo_ficha"], v["unidad_longitud"],
                       v["metraje_ext1"], v["metraje_ext2"], v["unidad_metraje"], v["estado"], v["notas_relevamiento"])
    id_ = _ultimo_id_cable()
    f = _cable_o_error(id_)
    return {"id": id_, "codigo": f["codigo"], "valores": _valores_cable(f)}


def cable_temporal():
    """Alta rápida: cable con código SIN ETIQUETA NNNN y estado TEMPORAL (el botón «⚡ Temporal» del desktop)."""
    M = _M()
    codigo = M.siguiente_codigo_temporal()
    M.agregar_cable(codigo, None, None, None, None, None, None, None, "TEMPORAL", None)
    return {"id": _ultimo_id_cable(), "codigo": codigo}


def cable_modificar(id, valores):
    id_ = _id(id)
    previa = _cable_o_error(id_)
    v = _normalizar_cable(valores, editando=True, estado_actual=previa["estado"])
    anterior = _valores_cable(previa)
    _verificar_codigo(v["codigo"], id_, anterior["codigo"])
    M = _M()
    M.modificar_cable(id_, v["codigo"], v["longitud"], v["id_tipo_cable"], v["id_tipo_ficha"], v["unidad_longitud"],
                      v["metraje_ext1"], v["metraje_ext2"], v["unidad_metraje"], v["estado"], v["notas_relevamiento"])
    if v["ancho_banda_override"] != anterior["ancho_banda_override"]:
        M.establecer_ancho_banda_override_cable(id_, v["ancho_banda_override"])
    if (v["es_armado_correcto"], v["detalle_armado"]) != (anterior["es_armado_correcto"], anterior["detalle_armado"]):
        es = v["es_armado_correcto"]
        M.establecer_armado_cable(id_, None if es is None else bool(es), v["detalle_armado"])
    f = _cable_o_error(id_)
    return {"id": id_, "codigo": f["codigo"], "anterior": anterior, "valores": _valores_cable(f)}


def cable_baja(id, solo_si_sin_uso=False):
    """Borra el cable (las FK arrastran sus conexiones). Con `solo_si_sin_uso` se niega si arrastra algo (lo pide el
    "deshacer" de un alta, para no borrar lo que se haya conectado mientras tanto)."""
    id_ = _id(id)
    previa = _cable_o_error(id_)
    usos = cable_usos(id_)["usos"]
    if solo_si_sin_uso and usos:
        raise ErrorSinCambios("El cable ya tiene conexiones u otros datos asociados: no se elimina.")
    _M().eliminar_cable(id_)
    return {"id": id_, "codigo": previa["codigo"], "anterior": _valores_cable(previa), "interno": bool(previa["interno"]),
            "id_cable_fusionado": previa["id_cable_fusionado"], "usos": usos}


def cable_restaurar(id, valores, interno=False, id_cable_fusionado=None):
    """Reinserta un cable con su id original (deshacer de una baja SIN uso: lo que lo usaba ya no se puede reconstruir)."""
    id_ = _id(id)
    if _existe("cable", "id_cable", id_):
        raise ErrorSinCambios(f"Ya existe un cable con el id {id_}: no se restaura.")
    estado = valores.get("estado") if isinstance(valores, dict) else None      # el de la baja puede ser FUSIONADO
    v = _normalizar_cable(valores, editando=True, estado_actual=estado)
    _verificar_codigo(v["codigo"])
    fus = None if id_cable_fusionado is None else _id(id_cable_fusionado)
    with _M()._conn_ctx() as conn:
        conn.execute(
            "INSERT INTO cable (id_cable, codigo, longitud, id_tipo_cable, id_tipo_ficha, unidad_longitud, "
            "metraje_impreso_primer_extremo, metraje_impreso_segundo_extremo, unidad_metraje_impreso, "
            "es_cable_conexion_interna, estado, notas_relevamiento, id_cable_fusionado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (id_, v["codigo"], v["longitud"], v["id_tipo_cable"], v["id_tipo_ficha"], v["unidad_longitud"], v["metraje_ext1"],
             v["metraje_ext2"], v["unidad_metraje"], 1 if interno else 0, v["estado"], v["notas_relevamiento"], fus))
    M = _M()
    if v["ancho_banda_override"] is not None:
        M.establecer_ancho_banda_override_cable(id_, v["ancho_banda_override"])
    if v["es_armado_correcto"] is not None or v["detalle_armado"] is not None:
        es = v["es_armado_correcto"]
        M.establecer_armado_cable(id_, None if es is None else bool(es), v["detalle_armado"])
    return {"id": id_, "codigo": v["codigo"]}


# ── Fusión ───────────────────────────────────────────────────────────────────

def cable_fusionar(id_principal, id_secundario, codigo, estado):
    """Las conexiones del secundario pasan al principal; el principal toma el código y el estado definitivos y el secundario
    queda FUSIONADO (no se borra: historial). Devuelve lo necesario para deshacerla (`cable_fusion_deshacer`)."""
    p, s = _id(id_principal), _id(id_secundario)
    errores = {}
    if p == s:
        raise ErrorSinCambios("Elegí dos cables distintos para fusionar.")
    cp, cs = _cable_o_error(p), _cable_o_error(s)
    for f, rol in ((cp, "principal"), (cs, "secundario")):
        if f["estado"] == "FUSIONADO":
            raise ErrorSinCambios(f"El cable {rol} ({f['codigo'] or '#' + str(f['id_cable'])}) ya está fusionado.")
    try:
        codigo = _valor(_CAMPO_TXT["codigo"], codigo)
        if codigo is None:
            raise ValueError(_OB)
    except ValueError as ex:
        errores["codigo"] = str(ex)
    if estado not in ESTADOS_FUSION:
        errores["estado"] = _EL
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    nuevo = _clave(codigo)       # no puede ser el código de OTRO cable (el principal puede conservar el suyo)
    for f in _b()._rows("SELECT id_cable, codigo FROM cable WHERE codigo IS NOT NULL"):
        if f["id_cable"] != p and _clave(f["codigo"]) == nuevo:
            raise ErrorCampos("Hay datos que corregir", {"codigo": "Ya lo usa otro cable (incluido el secundario)"})
    conexiones = [r["id_conexion"] for r in _b()._rows("SELECT id_conexion FROM conexion WHERE id_cable=? ORDER BY id_conexion", (s,))]
    anterior = {"principal": {"codigo": cp["codigo"], "estado": cp["estado"], "id_cable_fusionado": cp["id_cable_fusionado"]},
                "secundario": {"estado": cs["estado"], "id_cable_fusionado": cs["id_cable_fusionado"]}}
    _M().fusionar_cables(p, s, codigo, estado)
    return {"principal": p, "secundario": s, "codigo": codigo, "conexiones": conexiones, "anterior": anterior}


def cable_fusion_deshacer(id_principal, id_secundario, anterior, conexiones):
    """Revierte una fusión: devuelve al secundario SUS conexiones (las mismas, por id) y restaura código/estado de ambos.
    Una sola transacción. Se niega si el secundario ya no está fusionado en el principal."""
    p, s = _id(id_principal), _id(id_secundario)
    cp, cs = _cable_o_error(p), _cable_o_error(s)
    if cs["estado"] != "FUSIONADO" or cs["id_cable_fusionado"] != p:
        raise ErrorSinCambios("La fusión ya no se puede deshacer: el cable secundario cambió.")
    try:
        ids = [_id(i) for i in (conexiones or [])]
        ap, as_ = anterior["principal"], anterior["secundario"]
        cod, est, fus = ap["codigo"], ap["estado"], ap["id_cable_fusionado"]
        est_s, fus_s = as_["estado"], as_["id_cable_fusionado"]
    except (KeyError, TypeError):
        raise ErrorSinCambios("Datos de deshacer inválidos.") from None
    if cod is not None:
        nuevo = _clave(cod)
        for f in _b()._rows("SELECT id_cable, codigo FROM cable WHERE codigo IS NOT NULL"):
            if f["id_cable"] != p and _clave(f["codigo"]) == nuevo:
                raise ErrorSinCambios("No se puede deshacer: otro cable ya usa el código anterior.")
    with _M()._conn_ctx() as conn:
        for i in ids:
            conn.execute("UPDATE conexion SET id_cable=? WHERE id_conexion=? AND id_cable=?", (s, i, p))
        conn.execute("UPDATE cable SET codigo=?, estado=?, id_cable_fusionado=? WHERE id_cable=?", (cod, est, fus, p))
        conn.execute("UPDATE cable SET estado=?, id_cable_fusionado=? WHERE id_cable=?", (est_s, fus_s, s))
    return {"principal": p, "secundario": s, "conexiones": ids}


# ── Conexiones ───────────────────────────────────────────────────────────────

def _opciones_conectores(id_equipo):
    filas = _b()._rows(
        "SELECT c.id_conector, c.nombre, tc.nombre AS tipo, (SELECT count(*) FROM conexion cx WHERE cx.id_conector=c.id_conector) AS n "
        "FROM conector c LEFT JOIN tipo_conector tc ON tc.id_tipo_conector=c.id_tipo_conector WHERE c.id_equipo=? ORDER BY c.id_conector",
        (id_equipo,))
    return [{"valor": f["id_conector"], "etiqueta": " · ".join(str(x) for x in (f["nombre"] or f"#{f['id_conector']}", f["tipo"]) if x)
             + (f" ({f['n']})" if f["n"] else "")} for f in filas]


def conexion_formulario(id_conexion=None, id_cable=None, id_conector=None):
    """Formulario de una conexión. `id_cable` / `id_conector` prefijan el alta (se conecta desde la ficha de un cable o de un
    conector). Los campos `id_equipo` (solo para elegir el conector; no se guarda) e `id_conector` van encadenados: la UI
    vuelve a pedir los conectores con `conectores_de_equipo` al cambiar el equipo."""
    b = _b()
    editando = id_conexion is not None
    previa = _conexion_o_error(_id(id_conexion)) if editando else None
    cable_sel = previa["id_cable"] if editando else (None if id_cable is None else _id(id_cable))
    conector_sel = previa["id_conector"] if editando else (None if id_conector is None else _id(id_conector))
    if cable_sel is not None:
        _cable_o_error(cable_sel)
    id_equipo = None
    if conector_sel is not None:
        fila = b._one("SELECT id_equipo FROM conector WHERE id_conector=?", (conector_sel,))
        if fila is None:
            raise ErrorSinCambios(f"No existe el conector {conector_sel}")
        id_equipo = fila["id_equipo"]
    cables = b._rows("SELECT id_cable, codigo FROM cable WHERE (COALESCE(es_cable_conexion_interna,0)=0 AND COALESCE(estado,'')<>'FUSIONADO') "
                     "OR id_cable=? ORDER BY lower(codigo), id_cable", (cable_sel,))
    equipos = b._rows("SELECT e.id_equipo, e.nombre FROM equipo e WHERE (e.nombre NOT LIKE 'EMPALME BNC 1' AND e.nombre NOT LIKE 'SIN EQUIPO') "
                      "OR e.id_equipo=? ORDER BY lower(e.nombre), e.id_equipo", (id_equipo,))
    suelto = editando and previa["id_conector"] is None          # extremo suelto de una extensión: se edita sin conector
    esq = [
        _campo("id_cable", "select", True, _op(cables, "id_cable", "codigo")),
        _campo("id_equipo", "select", False, _op(equipos, "id_equipo")),
        _campo("id_conector", "select", not suelto, _opciones_conectores(id_equipo) if id_equipo is not None else [], depende_de="id_equipo"),
    ]
    if editando:
        esq += [_campo("id_tipo_ficha", "select", opciones=_op(b._rows("SELECT id_tipo_ficha, nombre FROM tipo_ficha ORDER BY lower(nombre)"), "id_tipo_ficha")),
                _campo("es_armado_correcto", "select", opciones=[{"valor": v, "etiqueta": e} for v, e in _ARMADOS]),
                _campo("detalle_armado", "texto_largo", largo=500)]
    valores = {"id_cable": cable_sel, "id_equipo": id_equipo, "id_conector": conector_sel}
    if editando:
        valores.update({k: previa[k] for k in ("id_tipo_ficha", "es_armado_correcto", "detalle_armado")})
    return {"id_conexion": previa["id_conexion"] if editando else None, "esquema": esq, "valores": valores}


def conexion_usos(id_conexion):
    id_ = _id(id_conexion)
    _conexion_o_error(id_)
    n = _contar("SELECT COUNT(*) AS n FROM extension_cable WHERE id_conexion_a=? OR id_conexion_b=?", (id_, id_))
    return {"id_conexion": id_, "usos": [{"tabla": "extension_cable", "n": n, "efecto": "borra"}] if n else []}


def _normalizar_conexion(valores, editando, suelto=False):
    if not isinstance(valores, dict):
        raise ErrorSinCambios("`valores` debe ser un objeto {campo: valor}")
    permitidos = set(_CAMPOS_CONEXION) if editando else {"id_cable", "id_conector"}
    sobran = sorted(set(valores) - permitidos)
    if sobran:
        raise ErrorSinCambios(f"Campos desconocidos: {sobran}")
    out, errores = {}, {}
    for nombre in sorted(permitidos):
        v = valores.get(nombre)
        try:
            if nombre == "id_cable":
                out[nombre] = _ref(v, "cable", "id_cable")
                if out[nombre] is None:
                    raise ValueError(_OB)
            elif nombre == "id_conector":
                out[nombre] = _ref(v, "conector", "id_conector")
                if out[nombre] is None and not suelto:
                    raise ValueError(_OB)
            elif nombre == "id_tipo_ficha":
                out[nombre] = _ref(v, "tipo_ficha", "id_tipo_ficha")
            elif nombre == "es_armado_correcto":
                out[nombre] = _armado(v)
            elif nombre == "detalle_armado":
                out[nombre] = _valor(_CAMPO_TXT["detalle_armado"], v)
        except ValueError as ex:
            errores[nombre] = str(ex)
    if errores:
        raise ErrorCampos("Hay datos que corregir", errores)
    return out


def _verificar_repetida(id_cable, id_conector, id_=None):
    if id_conector is None:
        return
    r = _b()._one("SELECT id_conexion FROM conexion WHERE id_cable=? AND id_conector=? AND id_conexion<>?", (id_cable, id_conector, id_ if id_ is not None else -1))
    if r:
        raise ErrorCampos("Hay datos que corregir", {"id_conector": "Ese cable ya está conectado a ese conector"})


def _avisos(id_conexion, id_cable, id_conector):
    """Avisos (no bloquean): un cable con más de dos extremos o un conector que ya tenía otra conexión."""
    av = []
    n_cable = _contar("SELECT COUNT(*) AS n FROM conexion WHERE id_cable=?", (id_cable,))
    if n_cable > 2:
        av.append({"clave": "El cable tiene {n} extremos (lo habitual es 2)", "vars": {"n": n_cable}})
    if id_conector is not None:
        otras = _contar("SELECT COUNT(*) AS n FROM conexion WHERE id_conector=? AND id_conexion<>?", (id_conector, id_conexion))
        if otras:
            av.append({"clave": "El conector ya tiene {n} conexión(es) más", "vars": {"n": otras}})
    return av


def _ultimo_id_conexion():
    return _b()._one("SELECT MAX(id_conexion) AS m FROM conexion")["m"]


def conexion_alta(id_cable, id_conector):
    v = _normalizar_conexion({"id_cable": id_cable, "id_conector": id_conector}, editando=False)
    _verificar_repetida(v["id_cable"], v["id_conector"])
    _M().alta_conexion(v["id_cable"], v["id_conector"], 0)
    id_ = _ultimo_id_conexion()
    f = _conexion_o_error(id_)
    return {"id": id_, "valores": _valores_conexion(f), "avisos": _avisos(id_, f["id_cable"], f["id_conector"])}


def conexion_modificar(id, valores):
    id_ = _id(id)
    previa = _conexion_o_error(id_)
    v = _normalizar_conexion(valores, editando=True, suelto=previa["id_conector"] is None)
    anterior = _valores_conexion(previa)
    _verificar_repetida(v["id_cable"], v["id_conector"], id_)
    M = _M()
    M.modificacion_conexion(id_, v["id_cable"], v["id_conector"], previa["interno"])     # conserva es_conexion_interna
    if v["id_tipo_ficha"] != anterior["id_tipo_ficha"]:
        M.establecer_ficha_conexion(id_, v["id_tipo_ficha"])
    if (v["es_armado_correcto"], v["detalle_armado"]) != (anterior["es_armado_correcto"], anterior["detalle_armado"]):
        es = v["es_armado_correcto"]
        M.establecer_armado_conexion(id_, None if es is None else bool(es), v["detalle_armado"])
    f = _conexion_o_error(id_)
    return {"id": id_, "anterior": anterior, "valores": _valores_conexion(f), "avisos": _avisos(id_, f["id_cable"], f["id_conector"])}


def conexion_baja(id, solo_si_sin_uso=False):
    id_ = _id(id)
    previa = _conexion_o_error(id_)
    usos = conexion_usos(id_)["usos"]
    if solo_si_sin_uso and usos:
        raise ErrorSinCambios("La conexión ya forma parte de una extensión: no se elimina.")
    _M().eliminar_conexion(id_)
    return {"id": id_, "anterior": _valores_conexion(previa), "interno": bool(previa["interno"]), "usos": usos}


def conexion_restaurar(id, valores, interno=False):
    """Reinserta una conexión con su id original (deshacer de una baja SIN uso)."""
    id_ = _id(id)
    if _existe("conexion", "id_conexion", id_):
        raise ErrorSinCambios(f"Ya existe una conexión con el id {id_}: no se restaura.")
    v = _normalizar_conexion(valores, editando=True, suelto=True)
    if v["id_cable"] is None:
        raise ErrorCampos("Hay datos que corregir", {"id_cable": _OB})
    with _M()._conn_ctx() as conn:
        conn.execute("INSERT INTO conexion (id_conexion, id_cable, id_conector, es_conexion_interna) VALUES (?,?,?,?)",
                     (id_, v["id_cable"], v["id_conector"], 1 if interno else 0))
    M = _M()
    if v["id_tipo_ficha"] is not None:
        M.establecer_ficha_conexion(id_, v["id_tipo_ficha"])
    if v["es_armado_correcto"] is not None or v["detalle_armado"] is not None:
        es = v["es_armado_correcto"]
        M.establecer_armado_conexion(id_, None if es is None else bool(es), v["detalle_armado"])
    if not interno:
        M._resync_referencia_virtual_si_aplica(v["id_conector"])
    return {"id": id_, "valores": _valores_conexion(_conexion_o_error(id_))}


LECTURAS = (cable_formulario, cable_usos, conexion_formulario, conexion_usos)
ESCRITURAS = (cable_alta, cable_temporal, cable_modificar, cable_baja, cable_restaurar, cable_fusionar, cable_fusion_deshacer,
              conexion_alta, conexion_modificar, conexion_baja, conexion_restaurar)
