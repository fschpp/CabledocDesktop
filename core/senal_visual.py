"""
senal_visual.py — Motor de vista previa visual de la señal para CableDoc
=========================================================================
Implementa plan_vista_previa_visual_senal.md (versión ya corregida a nivel
de CONECTOR, no de equipo — ver sección 0 de ese plan).

Mismo criterio de separación que ya justifica senal_propagation.py frente a
graph_impact.py: es un problema distinto (acá no es "¿qué se cae?" ni "¿qué
nombre de señal hay?", es "¿qué IMAGEN corresponde a este conector de
salida, ahora mismo?"), así que va en un módulo propio, sin GTK, para poder
probarlo aparte de la interfaz.

Resolución — un único mecanismo, sin ramas por rol_senal
----------------------------------------------------------
Se arma, igual que en senal_propagation.py, un grafo dirigido "quién
alimenta a quién" (cables + aristas internas de DISTRIBUIDOR/ENRUTADOR/
MODULO PATCHERA, exactamente con el mismo criterio ya probado en ese
módulo), pero invertido: REV[conector] = "el conector que lo alimenta".
Con eso, resolver la imagen de CUALQUIER conector es una única función
recursiva:

    1. ¿Tiene estrategia_visual efectiva (propia, o heredada de su
       tipo_equipo)? → componer sus miembros (ver _componer) y listo.
    2. Si no: ¿tiene imagen_senal_conector manual? → usarla tal cual.
    3. Si no: ¿algo lo alimenta (REV)? → recursión sobre ese conector.
    4. Si no: sin imagen, con el motivo.

No hace falta mirar rol_senal explícitamente en esta función: el paso 3 ya
sólo tiene aristas para los roles que son passthrough automático (el mismo
REV que ya usa senal_propagation), así que un FUENTE o un PROCESADOR sin
estrategia simplemente no tienen entrada en REV y caen directo al paso 4
salvo que tengan imagen manual (paso 2) — es exactamente la semántica del
plan, expresada con menos código gracias al mismo truco de grafo invertido
que ya usa el resto del proyecto.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResultadoImagen:
    id_conector: str
    path: Optional[str] = None          # archivo final a mostrar (PNG)
    origen: str = "SIN_IMAGEN"          # 'MANUAL' | 'COMPUESTA' | 'SIN_IMAGEN'
    detalle: str = ""                    # motivo, para mostrar al usuario
    fuentes: list = field(default_factory=list)  # id_conector usados (composición)

    @property
    def tiene_imagen(self) -> bool:
        return self.path is not None


class VisualizadorSenal:
    """
    Uso:
        vis = VisualizadorSenal(db_path)
        resultado = vis.resolver(id_conector_salida)
        if resultado.tiene_imagen:
            ... mostrar resultado.path ...
    """

    def __init__(self, db_path: str, cache_dir: Optional[str] = None):
        self._db_path = db_path
        # Carpeta donde se guardan las imágenes COMPUESTAS generadas (mosaico/
        # overlay/key) — junto con las imágenes originales en imagen/
        # para mantener todo en un solo lugar consistente.
        self._cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.abspath(db_path or ".")), "imagen")
        self._cargado = False

    # ── Carga de grafo (una sola vez por instancia) ─────────────────────
    def _cargar(self):
        if self._cargado:
            return
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        # Tablas propias, aseguradas acá también por si este módulo se usa
        # antes de que Modelo.asegurar_tablas_imagen_visual() haya corrido
        # (mismo criterio que graph_impact._leer_bd / senal_propagation).
        cur.execute(
            "CREATE TABLE IF NOT EXISTS imagen_senal_conector ("
            "  id_conector INTEGER PRIMARY KEY,"
            "  id_imagen   INTEGER NOT NULL,"
            "  fecha_ultima_edicion TEXT)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS estrategia_visual ("
            "  id_estrategia    INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_conector      INTEGER,"
            "  id_tipo_equipo   INTEGER,"
            "  patron_conector_salida TEXT,"
            "  modo             TEXT NOT NULL,"
            "  fecha_ultima_edicion TEXT)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS estrategia_visual_miembro ("
            "  id_miembro      INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_estrategia   INTEGER NOT NULL,"
            "  id_conector     INTEGER,"
            "  patron_conector TEXT,"
            "  posicion        TEXT NOT NULL,"
            "  orden           INTEGER NOT NULL DEFAULT 0,"
            "  origen          TEXT)"
        )
        # Migración defensiva: si la tabla ya existía de una versión previa
        # (sin la columna 'origen', agregada para el rol BASE dinámico
        # "<ASIGNADO POR MATRIZ>" — ver _componer/_entrada_por_matriz), se
        # agrega acá. CREATE TABLE IF NOT EXISTS no retrofittea columnas en
        # una tabla preexistente.
        _cols_evm = [c[1] for c in cur.execute(
            "PRAGMA table_info(estrategia_visual_miembro)").fetchall()]
        if "origen" not in _cols_evm:
            cur.execute("ALTER TABLE estrategia_visual_miembro ADD COLUMN origen TEXT")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS matriz_ruteo ("
            "  id_conector_salida  INTEGER PRIMARY KEY,"
            "  id_conector_entrada INTEGER,"
            "  fecha_ultima_edicion TEXT)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS funcion_patchera ("
            "  id_funcion_patchera INTEGER PRIMARY KEY,"
            "  clave TEXT UNIQUE NOT NULL, nombre_es TEXT NOT NULL,"
            "  direccion TEXT NOT NULL, descripcion TEXT)"
        )
        cols_conector = [c[1] for c in cur.execute(
            "PRAGMA table_info(conector)").fetchall()]
        # Población defensiva rol_senal='PATCHERA' (idempotente) — mismo
        # motivo que en graph_impact.py/senal_propagation.py: este módulo
        # tiene que poder correr solo, sin depender de que
        # Modelo.asegurar_columnas_control_idioma() ya haya corrido antes
        # en otro lado (ver plan_desarrollo_funcion_patchera.md, Fase C).
        cur.execute(
            "UPDATE tipo_equipo SET rol_senal='PATCHERA' "
            "WHERE UPPER(nombre)='MODULO PATCHERA' "
            "AND (rol_senal IS NULL OR rol_senal='DISTRIBUIDOR')")
        db.commit()

        # ── Conectores IN/OUT (mismo filtro que senal_propagation) ──
        cur.execute("""
            SELECT c.id_conector AS id, c.id_equipo, c.nombre,
                   UPPER(tc.nombre) AS tipo
            FROM conector c
            JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE UPPER(tc.nombre) IN ('IN','OUT')
        """)
        self._tipo_conector = {}       # id_conector -> 'IN'|'OUT'
        self._nombre_conector = {}     # id_conector -> nombre
        self._equipo_de_conector = {}  # id_conector -> id_equipo
        ins_por_equipo, outs_por_equipo = {}, {}
        for r in cur.fetchall():
            cid, eid = str(r["id"]), str(r["id_equipo"])
            self._tipo_conector[cid] = r["tipo"]
            self._nombre_conector[cid] = r["nombre"]
            self._equipo_de_conector[cid] = eid
            (ins_por_equipo if r["tipo"] == "IN" else outs_por_equipo) \
                .setdefault(eid, set()).add(cid)

        # ── Equipos: rol_senal + id_tipo_equipo (para estrategia_visual
        # heredada) ──
        cur.execute("""
            SELECT e.id_equipo AS id, e.id_tipo_equipo,
                   COALESCE(te.rol_senal, 'DISTRIBUIDOR') AS rol_senal
            FROM equipo e
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
        """)
        rol_por_equipo = {}
        self._tipo_equipo_de_equipo = {}
        for r in cur.fetchall():
            eid = str(r["id"])
            rol_por_equipo[eid] = (r["rol_senal"] or "DISTRIBUIDOR").upper()
            self._tipo_equipo_de_equipo[eid] = (
                str(r["id_tipo_equipo"]) if r["id_tipo_equipo"] is not None else None)
        # Expuesto como atributo (antes sólo variable local de este método) —
        # lo necesita diagnostico_falla.py para distinguir, cuando un
        # conector no tiene origen automático en self._rev, SI es porque el
        # equipo dueño tiene más de una entrada real ambigua (candidato a
        # "bifurcación" del asistente de diagnóstico) o porque es, por
        # ejemplo, una matriz/patchera sin documentar del todo (otro
        # tratamiento — ver plan_asistente_diagnostico_fallas.md, 3.2).
        self._rol_por_equipo = rol_por_equipo

        # ── Cables dirigidos OUT->IN (misma vista/lógica que graph_impact
        # y senal_propagation, para no discrepar sobre el sentido) ──
        cur.execute("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
        seen = set()
        cable_out_a_in = []
        for r in cur.fetchall():
            id_cable = str(r["id_cable"])
            if id_cable in seen:
                continue
            id_con_a, id_con_b = str(r["id_conector:1"]), str(r["id_conector"])
            if id_con_a not in self._tipo_conector or id_con_b not in self._tipo_conector:
                continue
            if self._tipo_conector.get(id_con_a) == "OUT":
                src, dst = id_con_a, id_con_b
            else:
                src, dst = id_con_b, id_con_a
            seen.add(id_cable)
            cable_out_a_in.append((src, dst))

        # ── matriz_ruteo ──
        cur.execute("SELECT id_conector_salida, id_conector_entrada FROM matriz_ruteo")
        ruteo_por_salida = {str(r["id_conector_salida"]): (
            str(r["id_conector_entrada"]) if r["id_conector_entrada"] is not None else None)
            for r in cur.fetchall()}

        cur.execute("SELECT DISTINCT id_conector FROM conexion")
        conectores_con_cable = {str(r[0]) for r in cur.fetchall()}

        # ── funcion_patchera (Fase C de plan_desarrollo_funcion_patchera.md):
        # los 4 puertos de un equipo PATCHERA se identifican EXCLUSIVAMENTE
        # por conector.id_funcion_patchera, nunca por prefijo de nombre —
        # mismo criterio ya aplicado en graph_impact.py y senal_propagation.py
        # (los tres motores tienen que coincidir sobre el mismo jack).
        puertos_patchera_por_equipo = {}
        if "id_funcion_patchera" in cols_conector:
            cur.execute("""
                SELECT c.id_conector AS id, c.id_equipo, fp.clave
                FROM conector c
                LEFT JOIN funcion_patchera fp
                  ON fp.id_funcion_patchera = c.id_funcion_patchera
                WHERE c.id_funcion_patchera IS NOT NULL
            """)
            for r in cur.fetchall():
                puertos_patchera_por_equipo.setdefault(
                    str(r["id_equipo"]), {})[r["clave"]] = str(r["id"])

        # ── Nombre de conector normalizado por equipo (para resolver
        # patron_conector de estrategias/miembros de plantilla) ──
        self._conectores_por_equipo_nombre = {}
        for cid, nombre in self._nombre_conector.items():
            eid = self._equipo_de_conector[cid]
            self._conectores_por_equipo_nombre.setdefault(eid, {})[
                (nombre or "").strip().upper()] = cid

        # ── Aristas internas por equipo (mismo criterio que
        # senal_propagation: DISTRIBUIDOR con 1 IN, ENRUTADOR según
        # matriz_ruteo, PATCHERA con bypass full-normal) ──
        internal_edges = []
        self.equipos_enrutador_sin_matriz = set()
        self.equipos_distribuidor_ambiguo = set()
        FUNCIONES_PATCHERA = ("BACK_ENTRADA", "BACK_SALIDA",
                              "FRONT_DERIVACION", "FRONT_INSERCION")
        for eid, rol in rol_por_equipo.items():
            ins = ins_por_equipo.get(eid, set())
            outs = outs_por_equipo.get(eid, set())
            if not outs:
                continue
            if rol == "PATCHERA":
                puertos = puertos_patchera_por_equipo.get(eid, {})
                if not all(f in puertos for f in FUNCIONES_PATCHERA):
                    self.equipos_distribuidor_ambiguo.add(eid)
                    continue
                derivacion_usada = puertos["FRONT_DERIVACION"] in conectores_con_cable
                insercion_usada = puertos["FRONT_INSERCION"] in conectores_con_cable
                if not derivacion_usada and not insercion_usada:
                    internal_edges.append(
                        (puertos["BACK_ENTRADA"], puertos["BACK_SALIDA"]))
                if derivacion_usada:
                    internal_edges.append(
                        (puertos["BACK_ENTRADA"], puertos["FRONT_DERIVACION"]))
                if insercion_usada:
                    internal_edges.append(
                        (puertos["FRONT_INSERCION"], puertos["BACK_SALIDA"]))
                continue
            if rol == "DISTRIBUIDOR":
                if len(ins) == 1:
                    cin = next(iter(ins))
                    for cout in outs:
                        internal_edges.append((cin, cout))
                elif len(ins) > 1:
                    self.equipos_distribuidor_ambiguo.add(eid)
            elif rol == "ENRUTADOR":
                tiene_ruteo = any(cout in ruteo_por_salida for cout in outs)
                if not tiene_ruteo:
                    self.equipos_enrutador_sin_matriz.add(eid)
                    continue
                for cout in outs:
                    cin = ruteo_por_salida.get(cout)
                    if cin:
                        internal_edges.append((cin, cout))
            # FUENTE / PROCESADOR / CONSUMIDOR: sin aristas internas
            # automáticas — dependen de imagen manual o estrategia_visual.

        # ── Grafo invertido: REV[conector] = quién lo alimenta ──
        self._rev = {}
        for src, dst in cable_out_a_in + internal_edges:
            self._rev[dst] = src

        db.close()
        self._cargado = True

    # ── Resolución ───────────────────────────────────────────────────────
    def resolver(self, id_conector, _visitados=None) -> ResultadoImagen:
        """Punto de entrada público. Envuelve toda la resolución (lectura
        de BD, recursión, composición) en una red de seguridad: CUALQUIER
        excepción no prevista en el camino vuelve como un ResultadoImagen
        normal con el detalle del error, en vez de propagarse sin
        capturar — si eso pasara dentro de un callback de dibujo de GTK
        (el diálogo de vista previa, la mini-ventana de hover), quedaría
        silenciado en la consola sin que el usuario se entere. Nunca se
        oculta el motivo, sólo se evita que rompa la interfaz."""
        try:
            return self._resolver_paso(id_conector, _visitados)
        except Exception as ex:
            return ResultadoImagen(
                str(id_conector), origen="SIN_IMAGEN",
                detalle=f"error inesperado al resolver: {ex}")

    def _resolver_paso(self, id_conector, _visitados=None) -> ResultadoImagen:
        self._cargar()
        id_conector = str(id_conector)
        visitados = set(_visitados or ())
        if id_conector in visitados:
            return ResultadoImagen(id_conector, origen="SIN_IMAGEN",
                                    detalle="bucle de ruteo detectado")
        visitados = visitados | {id_conector}

        estrategia = self._estrategia_efectiva(id_conector)
        if estrategia:
            return self._componer(id_conector, estrategia, visitados)

        manual = self._imagen_manual(id_conector)
        if manual:
            return ResultadoImagen(id_conector, path=manual, origen="MANUAL",
                                    detalle="imagen manual asignada a este conector")

        origen_conector = self._rev.get(id_conector)
        if origen_conector:
            return self._resolver_paso(origen_conector, visitados)

        return ResultadoImagen(
            id_conector, origen="SIN_IMAGEN",
            detalle=self._motivo_sin_imagen(id_conector))

    def _motivo_sin_imagen(self, id_conector):
        eid = self._equipo_de_conector.get(id_conector)
        if eid in self.equipos_enrutador_sin_matriz:
            return "sin ruteo asignado en la matriz"
        if eid in self.equipos_distribuidor_ambiguo:
            return "equipo con más de una entrada real: no se puede saber qué pasa"
        return "sin estrategia, sin imagen manual y sin passthrough hacia esta salida"

    # ── Helpers de datos (leen de la BD directamente, sin depender de
    # Modelo, para que este módulo se pueda usar/testear sin GTK) ──
    def _imagen_manual(self, id_conector):
        db = sqlite3.connect(self._db_path)
        try:
            r = db.execute(
                "SELECT i.path_archivo FROM imagen_senal_conector isc "
                "JOIN imagen i ON i.id_imagen = isc.id_imagen "
                "WHERE isc.id_conector=?", (id_conector,)).fetchall()
            return r[0][0] if r else None
        finally:
            db.close()

    def _estrategia_efectiva(self, id_conector):
        db = sqlite3.connect(self._db_path)
        try:
            propia = db.execute(
                "SELECT id_estrategia, modo FROM estrategia_visual WHERE id_conector=?",
                (id_conector,)).fetchall()
            if propia:
                id_estrategia, modo = propia[0]
            else:
                id_tipo_equipo = self._tipo_equipo_de_equipo.get(
                    self._equipo_de_conector.get(id_conector))
                if id_tipo_equipo is None:
                    return None
                nombre_norm = (self._nombre_conector.get(id_conector) or "").strip().upper()
                candidatas = db.execute(
                    "SELECT id_estrategia, modo, patron_conector_salida "
                    "FROM estrategia_visual "
                    "WHERE id_tipo_equipo=? AND patron_conector_salida IS NOT NULL",
                    (id_tipo_equipo,)).fetchall()
                id_estrategia = modo = None
                for cand_id, cand_modo, patron in candidatas:
                    if (patron or "").strip().upper() == nombre_norm:
                        id_estrategia, modo = cand_id, cand_modo
                        break
                if id_estrategia is None:
                    return None
            miembros_raw = db.execute(
                "SELECT id_conector, patron_conector, posicion, orden, origen "
                "FROM estrategia_visual_miembro WHERE id_estrategia=? ORDER BY orden",
                (id_estrategia,)).fetchall()
        finally:
            db.close()

        eid = self._equipo_de_conector.get(id_conector)
        miembros = []
        for id_conector_m, patron_m, posicion, orden, origen in miembros_raw:
            if origen == "MATRIZ":
                # Rol dinámico: no hay id_conector fijo — se resuelve en
                # _componer() contra matriz_ruteo del propio conector de
                # SALIDA que se está componiendo (no de este miembro).
                miembros.append({"id_conector": None, "posicion": posicion,
                                  "orden": orden, "origen": "MATRIZ"})
                continue
            cid = str(id_conector_m) if id_conector_m is not None else None
            if cid is None and patron_m is not None:
                cid = self._conectores_por_equipo_nombre.get(eid, {}).get(
                    (patron_m or "").strip().upper())
            if cid is not None:
                miembros.append({"id_conector": cid, "posicion": posicion, "orden": orden})
        if not miembros:
            return None
        return {"id_estrategia": str(id_estrategia), "modo": modo, "miembros": miembros}

    def _entrada_por_matriz(self, id_conector_salida):
        """Entrada actualmente asignada, vía 'Editar matriz', a esta salida
        puntual — o None si no hay fila guardada o está explícitamente sin
        asignar. Consulta matriz_ruteo directamente (mismo criterio del
        resto de este módulo: sin depender de Modelo)."""
        db = sqlite3.connect(self._db_path)
        try:
            r = db.execute(
                "SELECT id_conector_entrada FROM matriz_ruteo "
                "WHERE id_conector_salida=?", (id_conector_salida,)).fetchall()
            return str(r[0][0]) if r and r[0][0] is not None else None
        finally:
            db.close()

    # ── Composición (Cairo, sin dependencias nuevas) ────────────────────
    def _componer(self, id_conector_salida, estrategia, visitados) -> ResultadoImagen:
        import cairo  # import diferido: no hace falta si nunca se compone

        modo = estrategia["modo"]
        miembros = estrategia["miembros"]

        resueltos = {}   # posicion -> ResultadoImagen
        fuentes = []
        for m in miembros:
            if m.get("origen") == "MATRIZ":
                # Rol dinámico "<ASIGNADO POR MATRIZ>": la entrada no es
                # fija, se relee CADA VEZ desde matriz_ruteo del propio
                # conector de salida que se está componiendo — así el rol
                # sigue el ruteo vivo (ej. si después se reasigna la
                # matriz vía 'Editar matriz', esta composición lo refleja
                # sin tocar nada acá). Ver plan de "BASE dinámico por
                # matriz" en la solicitud original.
                id_in = self._entrada_por_matriz(id_conector_salida)
                if id_in is None:
                    resueltos[m["posicion"]] = ResultadoImagen(
                        id_conector_salida, origen="SIN_IMAGEN",
                        detalle="sin ruteo asignado en la matriz para este conector")
                    continue
            else:
                id_in = m["id_conector"]
            # IMPORTANTE: se resuelve el conector miembro con el MISMO
            # mecanismo de 4 pasos que cualquier otro conector (no un
            # atajo que sólo mire si tiene cable) — un IN puede tener su
            # propia imagen manual sin estar cableado a nada (fue el caso
            # que el test de validación de este motor encontró: una
            # entrada de composición con imagen de prueba puesta
            # directamente, sin cable, se descartaba igual si acá se
            # chequeaba _rev antes de llamar a resolver()).
            r = self.resolver(id_in, visitados)
            resueltos[m["posicion"]] = r
            fuentes.append(id_in)

        os.makedirs(self._cache_dir, exist_ok=True)
        out_path = os.path.join(self._cache_dir, f"compuesta_{id_conector_salida}.png")

        try:
            if modo == "MOSAICO":
                _componer_mosaico(cairo, resueltos, out_path)
            elif modo == "OVERLAY":
                _componer_overlay(cairo, resueltos, out_path)
            elif modo == "KEY":
                _componer_key(cairo, resueltos, out_path)
            elif modo == "AUDIO_EMBEBIDO":
                _componer_audio_embebido(cairo, resueltos, out_path)
            else:
                return ResultadoImagen(id_conector_salida, origen="SIN_IMAGEN",
                                        detalle=f"modo de composición desconocido: {modo}")
        except _SinInsumos as ex:
            return ResultadoImagen(id_conector_salida, origen="SIN_IMAGEN",
                                    detalle=str(ex))
        except Exception as ex:
            # CUALQUIER otro error de composición (una imagen de entrada en
            # un formato que el motor no sabe leer directamente, archivo
            # corrupto o movido, etc.) tiene que volver como resultado
            # normal, NO como excepción sin capturar — antes de este
            # cambio, un error acá (ej. "BASE en JPG, el motor sólo lee
            # PNG") sólo se veía como traceback en la consola, porque
            # nadie lo atajaba entre este método y el callback de dibujo
            # de GTK que terminaba tragándoselo. Ahora se ve tal cual en
            # el diálogo y en la mini-ventana de hover, con el detalle
            # completo del error — nunca se oculta en silencio.
            return ResultadoImagen(
                id_conector_salida, origen="SIN_IMAGEN",
                detalle=f"error al componer ({modo.lower()}): {ex}")

        return ResultadoImagen(
            id_conector_salida, path=out_path, origen="COMPUESTA",
            detalle=f"{modo.lower()} de {len(fuentes)} entrada(s)", fuentes=fuentes)


class _SinInsumos(Exception):
    """Falta al menos una imagen de entrada indispensable para componer."""


# ── Funciones de composición Cairo, libres de estado (fáciles de testear
# aparte, ver test_senal_visual.py) ────────────────────────────────────────
_ANCHO_REF, _ALTO_REF = 640, 360  # 16:9 fijo en el MVP (ver plan, sección 6.4)


def _superficie_desde_path(cairo, path):
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return cairo.ImageSurface.create_from_png(path)
    # JPG u otro formato sin soporte nativo en cairo: se resuelve en la
    # capa de UI (GdkPixbuf sabe leer cualquier formato y sí puede volcarlo
    # a una ImageSurface) — este motor puro-Cairo asume PNG, que es el
    # formato interno recomendado en toda la cadena (ver plan, sección 2.4).
    raise ValueError(
        f"formato no soportado directamente por el motor de composición: {ext} "
        f"(convertir a PNG antes de asignarlo como imagen manual)")


def _pintar_ajustado(cr, cairo, surface, x, y, w, h):
    """Pinta `surface` escalada para ocupar el rectángulo (x,y,w,h)
    completo (deforma si la relación de aspecto no coincide — MVP; ver
    plan sección 6.4 sobre relación de aspecto configurable a futuro)."""
    sw, sh = surface.get_width(), surface.get_height()
    if sw == 0 or sh == 0:
        return
    cr.save()
    cr.translate(x, y)
    cr.scale(w / sw, h / sh)
    cr.set_source_surface(surface, 0, 0)
    cr.paint()
    cr.restore()


def _componer_mosaico(cairo, resueltos, out_path):
    posiciones = sorted(resueltos.keys())  # orden estable
    n = len(posiciones)
    if n == 0:
        raise _SinInsumos("mosaico sin entradas configuradas")
    import math
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, _ANCHO_REF, _ALTO_REF)
    cr = cairo.Context(surface)
    cr.set_source_rgb(0, 0, 0)
    cr.paint()
    cell_w, cell_h = _ANCHO_REF / cols, _ALTO_REF / rows
    for i, pos in enumerate(posiciones):
        r = resueltos[pos]
        row, col = divmod(i, cols)
        celda = _superficie_desde_path(cairo, r.path)
        if celda is None:
            continue  # celda queda negra ("sin imagen"), no aborta el mosaico entero
        _pintar_ajustado(cr, cairo, celda, col * cell_w, row * cell_h, cell_w, cell_h)
    surface.write_to_png(out_path)


def _componer_overlay(cairo, resueltos, out_path):
    base = resueltos.get("BASE")
    if base is None or not base.tiene_imagen:
        raise _SinInsumos("overlay sin imagen BASE resuelta")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, _ANCHO_REF, _ALTO_REF)
    cr = cairo.Context(surface)
    base_surf = _superficie_desde_path(cairo, base.path)
    _pintar_ajustado(cr, cairo, base_surf, 0, 0, _ANCHO_REF, _ALTO_REF)
    capas = sorted(
        (p for p in resueltos if p.startswith("OVERLAY_")),
        key=lambda p: int(p.split("_")[1]) if p.split("_")[1].isdigit() else 0)
    for pos in capas:
        r = resueltos[pos]
        if not r.tiene_imagen:
            continue
        capa_surf = _superficie_desde_path(cairo, r.path)
        cr.save()
        cr.scale(_ANCHO_REF / capa_surf.get_width(), _ALTO_REF / capa_surf.get_height())
        cr.set_source_surface(capa_surf, 0, 0)
        cr.paint()  # el canal alfa del PNG ya define qué se pisa
        cr.restore()
    surface.write_to_png(out_path)


def _componer_key(cairo, resueltos, out_path):
    """BASE + FILL enmascarado por MATTE (escala de grises → alfa),
    caso MDK-111 OUT 2 (BKGD + KEY VIDEO + KEY ALPHA). Distinto de
    OVERLAY: acá la transparencia no viene en el archivo de FILL, viene
    de una tercera imagen (ver plan, sección 2.4)."""
    base, fill, matte = resueltos.get("BASE"), resueltos.get("FILL"), resueltos.get("MATTE")
    if base is None or not base.tiene_imagen:
        raise _SinInsumos("key sin imagen BASE resuelta")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, _ANCHO_REF, _ALTO_REF)
    cr = cairo.Context(surface)
    base_surf = _superficie_desde_path(cairo, base.path)
    _pintar_ajustado(cr, cairo, base_surf, 0, 0, _ANCHO_REF, _ALTO_REF)

    if fill is not None and fill.tiene_imagen and matte is not None and matte.tiene_imagen:
        fill_surf = _superficie_desde_path(cairo, fill.path)
        matte_surf = _superficie_desde_path(cairo, matte.path)
        # mask_surface() interpreta el (x,y) y el tamaño de la máscara en
        # el sistema de coordenadas YA transformado por el CTM vigente —
        # si se la usa dentro de un cr.scale() (como el resto de este
        # motor hace para ajustar tamaños), la máscara queda corrida y
        # deformada en vez de coincidir píxel a píxel con el FILL. Por
        # eso acá, a diferencia de _pintar_ajustado, primero se reescala
        # FILL a un buffer del tamaño final (mismo truco ya usado para
        # el matte en _luminosidad_a_mascara_a8) y recién ahí se pinta y
        # se enmascara SIN ningún cr.scale() activo — los dos quedan en
        # la misma resolución 1:1, que es lo que mask_surface espera.
        fill_full = cairo.ImageSurface(cairo.FORMAT_ARGB32, _ANCHO_REF, _ALTO_REF)
        cr_fill = cairo.Context(fill_full)
        cr_fill.scale(_ANCHO_REF / fill_surf.get_width(), _ALTO_REF / fill_surf.get_height())
        cr_fill.set_source_surface(fill_surf, 0, 0)
        cr_fill.paint()

        mask_a8 = _luminosidad_a_mascara_a8(cairo, matte_surf, _ANCHO_REF, _ALTO_REF)
        cr.set_source_surface(fill_full, 0, 0)
        # mask_surface usa el canal alfa de mask_a8 (ya cargado con la
        # luminosidad del matte) como opacidad del FILL — blanco=opaco,
        # negro=transparente, tal como un matte de key real.
        cr.mask_surface(mask_a8, 0, 0)
    # Si falta FILL o MATTE: se deja sólo BASE (barras/fondo visible),
    # mejor degradar a "se ve el fondo" que fallar la composición entera.

    surface.write_to_png(out_path)


def _componer_audio_embebido(cairo, resueltos, out_path):
    """BASE + panel de audio embebido en el margen izquierdo: un rectángulo
    negro de la MISMA altura que la imagen original, con una barra estilo
    vúmetro (valores inventados, no medidos — este motor no decodifica
    audio real) y el número de canal debajo de cada barra, uno por cada
    entrada tildada como fuente de audio (posición 'AUDIO_N'). Mismo
    espíritu que OVERLAY/KEY: BASE es obligatoria, el resto degrada sin
    abortar la composición entera (panel vacío si no hay canales)."""
    base = resueltos.get("BASE")
    if base is None or not base.tiene_imagen:
        raise _SinInsumos("audio embebido sin imagen BASE resuelta")

    canales = sorted(
        (p for p in resueltos if p.startswith("AUDIO_")),
        key=lambda p: int(p.split("_")[1]) if p.split("_")[1].isdigit() else 0)
    n = len(canales)

    # Ancho del panel: crece con la cantidad de canales tildados, con un
    # mínimo que deja lugar a "sin canales" (panel negro vacío) sin
    # quedar ridículamente angosto.
    margen, ancho_barra_min = 8, 26
    ancho_panel = max(60, margen + n * (ancho_barra_min + margen))
    ancho_total = ancho_panel + _ANCHO_REF

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho_total, _ALTO_REF)
    cr = cairo.Context(surface)
    cr.set_source_rgb(0, 0, 0)
    cr.paint()  # fondo total negro: cubre también el panel desde el vamos

    base_surf = _superficie_desde_path(cairo, base.path)
    _pintar_ajustado(cr, cairo, base_surf, ancho_panel, 0, _ANCHO_REF, _ALTO_REF)
    # El rectángulo del panel ya quedó negro por el paint() inicial (misma
    # altura _ALTO_REF que la imagen original, tal como pide el plan) —
    # no hace falta volver a pintarlo, sólo dibujar encima.

    if n > 0:
        alto_texto = 16
        alto_barras = _ALTO_REF - alto_texto - margen * 2
        ancho_barra = (ancho_panel - margen * (n + 1)) / n
        cr.select_font_face(
            "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        for i, pos in enumerate(canales):
            num_canal = i + 1
            x = margen + i * (ancho_barra + margen)
            y = margen
            # Valor "inventado" pero estable (no aleatorio en cada
            # composición): una función determinística del número de
            # canal, para que la barra no titile de una regeneración a
            # otra sin motivo — este motor no mide audio real (ver
            # docstring del módulo, esto es un indicador de presencia de
            # canal, no un medidor calibrado).
            nivel = 0.2 + ((num_canal * 47) % 71) / 100.0
            _dibujar_barra_vuumetro(cr, x, y, ancho_barra, alto_barras, nivel)

            texto = str(num_canal)
            tam_fuente = max(8, min(13, ancho_barra * 0.6))
            cr.set_font_size(tam_fuente)
            cr.set_source_rgb(1, 1, 1)
            ext = cr.text_extents(texto)
            tx = x + (ancho_barra - ext.width) / 2 - ext.x_bearing
            ty = y + alto_barras + margen + ext.height
            cr.move_to(tx, ty)
            cr.show_text(texto)

    surface.write_to_png(out_path)


def _dibujar_barra_vuumetro(cr, x, y, w, h, nivel):
    """Dibuja una barra vertical estilo vúmetro de segmentos (como los
    medidores L/R de un monitor de audio broadcast): celdas apagadas de
    fondo + celdas "encendidas" desde abajo hasta `nivel` (0..1), con las
    tres bandas de color habituales según la altura de cada celda (verde
    en el grueso inferior, amarillo cerca del techo, rojo en el pico)."""
    nivel = max(0.0, min(1.0, nivel))
    n_celdas = 14
    celda_h = h / n_celdas
    hueco = celda_h * 0.18
    celdas_encendidas = round(nivel * n_celdas)
    for c in range(n_celdas):
        frac_altura = c / n_celdas  # 0 = celda de más abajo
        if frac_altura < 0.6:
            color = (0.20, 0.80, 0.25)   # verde
        elif frac_altura < 0.85:
            color = (0.90, 0.80, 0.15)   # amarillo
        else:
            color = (0.90, 0.20, 0.20)   # rojo
        if c < celdas_encendidas:
            cr.set_source_rgb(*color)
        else:
            # celda apagada: mismo color muy oscurecido, para que se note
            # la banda (verde/amarillo/rojo) del vúmetro aun sin señal.
            cr.set_source_rgb(color[0] * 0.22, color[1] * 0.22, color[2] * 0.22)
        cy = y + h - (c + 1) * celda_h + hueco / 2
        cr.rectangle(x, cy, w, celda_h - hueco)
        cr.fill()


def _luminosidad_a_mascara_a8(cairo, surface_color, ancho, alto):
    """Convierte una superficie a escala de grises (RGBA) en una máscara
    cairo.FORMAT_A8 (un byte de opacidad por píxel = luminosidad del
    original), escalada a (ancho, alto). Única pieza del motor que toca
    píxeles a mano en vez de sólo componer superficies — ver plan,
    sección 2.4, marcada ahí como el costo extra de KEY frente a OVERLAY."""
    # Reescalar primero a (ancho, alto) pintando en una superficie color
    # temporal, para no tener que hacer el resampleo a mano.
    tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr_tmp = cairo.Context(tmp)
    cr_tmp.scale(ancho / surface_color.get_width(), alto / surface_color.get_height())
    cr_tmp.set_source_surface(surface_color, 0, 0)
    cr_tmp.paint()

    mask = cairo.ImageSurface(cairo.FORMAT_A8, ancho, alto)
    tmp.flush()
    src = tmp.get_data()
    src_stride = tmp.get_stride()
    dst = mask.get_data()
    dst_stride = mask.get_stride()
    for y in range(alto):
        for x in range(ancho):
            off = y * src_stride + x * 4
            b, g, r = src[off], src[off + 1], src[off + 2]
            # Luminosidad perceptual estándar (Rec. 601).
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            dst[y * dst_stride + x] = lum
    mask.mark_dirty()
    return mask
