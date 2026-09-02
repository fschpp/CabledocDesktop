"""
CableDoc - Capa de acceso a datos (modelo.py)
Equivalente Python de Modelo.vb (VB.NET/SQLite)
Usa parámetros en las consultas para evitar inyección SQL.
"""

import sqlite3
import os
import base64
import contextlib

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database/db.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagen")
MANUALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manuales")
PICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picon")
SCHEMA_SQL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_db.sql")


class ImagenInvalidaError(Exception):
    """Se levanta cuando un archivo de imagen no se puede usar como imagen
    de señal (ni tal cual, ni convirtiéndolo a PNG) — ver
    Modelo._normalizar_imagen_a_png. A propósito NO hereda de ValueError
    genérico: así el código que llama (la interfaz) la puede distinguir
    de otros errores de validación y mostrarla tal cual al usuario, sin
    que se pierda en un except Exception más amplio en el medio."""


def asegurar_directorios():
    """Crea las carpetas base de la app si no existen todavía: la carpeta
    que contiene database/db.db, y las carpetas imagen/, manuales/, picon/.
    Pensado para una instalación nueva (recién clonada del repo, donde solo
    están los .py) que todavía no tiene ninguna de estas carpetas creadas."""
    for d in (os.path.dirname(DB_PATH), IMG_DIR, MANUALES_DIR, PICON_DIR):
        os.makedirs(d, exist_ok=True)


def asegurar_base_datos():
    """Si database/db.db no existe todavía, lo crea ejecutando el esquema
    completo (tablas, vistas, triggers, sin datos) de schema_db.sql, que
    vive junto a este archivo. No hace nada si el archivo ya existe, para
    no pisar nunca una base con datos reales. Si tampoco existe
    schema_db.sql, no crea nada — se deja que el resto de la app falle más
    adelante con un mensaje explícito en vez de crear un .db vacío sin
    tablas."""
    if os.path.isfile(DB_PATH):
        return
    if not os.path.isfile(SCHEMA_SQL_PATH):
        return
    with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# Asegurar que carpetas y base de datos existan apenas se importa este
# módulo (arranque de la app, o cualquier script que use Modelo).
asegurar_directorios()
asegurar_base_datos()


def _n(val):
    """Convierte cadena vacía a None (NULL en SQLite)."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s == "" else s


class DimensionesImagenError(Exception):
    """Se levanta cuando no se pueden determinar el ancho/alto (px) de una
    imagen — necesarios para convertir entre coordenadas en píxeles y en
    porcentaje (ver Modelo._dimensiones_imagen). A propósito NO hereda de
    ValueError genérico, por el mismo motivo que ImagenInvalidaError: así
    la interfaz la puede distinguir y mostrarla tal cual al usuario."""


class Modelo:
    # ── Coordenadas en imagen: píxeles ↔ porcentaje (SIN columnas nuevas) ───
    #
    # Las columnas existentes coordenada_x_en_imagen/coordenada_y_en_imagen
    # (conector, conector_catalogo, equipo) y rectangulo_x_en_imagen/
    # rectangulo_y_en_imagen/rectangulo_ancho_pixeles/rectangulo_alto_pixeles
    # (slot, slot_catalogo) ahora guardan un ENTERO de 0 a 100 (porcentaje
    # del ancho/alto de la imagen), no un píxel libre. No se agregó ninguna
    # columna ni se tocó el esquema — mismos nombres, mismo tipo INTEGER,
    # sólo cambia el significado del valor guardado.
    #
    # El resto de la aplicación (pantallas, Cairo, _ImagenZoom) sigue
    # trabajando en PÍXELES como siempre — la conversión es invisible
    # fuera de este archivo: se convierte a porcentaje al escribir
    # (INSERT/UPDATE) y de vuelta a píxeles al leer (los métodos
    # devolver_*), usando exactamente estas fórmulas:
    #     x_pct = round(x_px / ancho_imagen * 100)
    #     y_pct = round(y_px / alto_imagen  * 100)
    #     w_pct = round(ancho_px / ancho_imagen * 100)
    #     h_pct = round(alto_px  / alto_imagen  * 100)
    # y a la inversa (x_px = round(x_pct / 100 * ancho_imagen), etc.) para
    # reconstruir píxeles al leer. El ancho/alto de la imagen NO se guarda
    # en la base — se lee del archivo real al vuelo (GdkPixbuf para
    # rasters, Rsvg para SVG) cada vez que hace falta, con una caché en
    # memoria por (ruta, mtime). Ver Modelo._dimensiones_imagen.
    #
    # Nota sobre datos reales existentes: algunos conectores/slots quedaron
    # posicionados fuera del borde de su imagen (probablemente la imagen
    # fue reemplazada por una versión de otro tamaño después de ubicar el
    # punto). El porcentaje resultante para esos casos puede ser negativo
    # o mayor a 100 — a propósito NO se recorta (clampear perdería la
    # posición real y movería el punto visualmente); Modelo.
    # migrar_coordenadas_a_porcentaje() los reporta para que se puedan
    # revisar a mano.

    _CACHE_DIMENSIONES_IMAGEN = {}

    @staticmethod
    def _dimensiones_imagen(path_archivo):
        """Devuelve (ancho_px, alto_px) de la imagen ubicada en IMG_DIR
        bajo el nombre `path_archivo`. Soporta cualquier raster que
        entienda GdkPixbuf (PNG/JPG/GIF/BMP/...) y SVG (vía Rsvg, leyendo
        el tamaño intrínseco del documento sin rasterizarlo).

        Cachea por (path_archivo, mtime) para no releer el archivo del
        disco en cada conversión — se invalida sola si el archivo cambia.

        Levanta DimensionesImagenError si el archivo no existe, no se
        puede leer, o no están disponibles los bindings de introspección
        necesarios (gi/GdkPixbuf/Rsvg) en este entorno."""
        if not path_archivo:
            raise DimensionesImagenError(
                "No hay imagen asociada: no se puede determinar su "
                "ancho/alto para convertir la coordenada.")

        full_path = os.path.join(IMG_DIR, path_archivo)
        if not os.path.isfile(full_path):
            raise DimensionesImagenError(
                f"No se encontró el archivo de imagen {path_archivo!r} "
                f"en {IMG_DIR!r}.")

        try:
            mtime = os.path.getmtime(full_path)
        except OSError:
            mtime = None
        clave = (full_path, mtime)
        cacheado = Modelo._CACHE_DIMENSIONES_IMAGEN.get(clave)
        if cacheado is not None:
            return cacheado

        es_svg = full_path.lower().endswith(".svg")
        try:
            import gi
            if es_svg:
                gi.require_version("Rsvg", "2.0")
                from gi.repository import Rsvg
                handle = Rsvg.Handle.new_from_file(full_path)
                dim = handle.get_dimensions()
                ancho, alto = dim.width, dim.height
            else:
                gi.require_version("GdkPixbuf", "2.0")
                from gi.repository import GdkPixbuf
                fmt, ancho, alto = GdkPixbuf.Pixbuf.get_file_info(full_path)
                if fmt is None:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(full_path)
                    ancho, alto = pixbuf.get_width(), pixbuf.get_height()
        except DimensionesImagenError:
            raise
        except Exception as ex:
            raise DimensionesImagenError(
                f"No se pudo determinar el tamaño de {path_archivo!r}: "
                f"{ex}"
            ) from ex

        if not ancho or not alto:
            raise DimensionesImagenError(
                f"{path_archivo!r} no reportó un ancho/alto válido "
                f"({ancho}x{alto}).")

        resultado = (ancho, alto)
        Modelo._CACHE_DIMENSIONES_IMAGEN[clave] = resultado
        return resultado

    @staticmethod
    def _px_a_pct(valor_px, dimension_px):
        """px -> porcentaje entero (redondeado, puede ser <0 o >100 si el
        punto cae fuera de la imagen — ver nota más arriba). None si
        valor_px es None."""
        if valor_px is None:
            return None
        if not dimension_px:
            raise DimensionesImagenError(
                "Dimensión de imagen inválida (0) al convertir a "
                "porcentaje.")
        return int(round((float(valor_px) / float(dimension_px)) * 100.0))

    @staticmethod
    def _pct_a_px(valor_pct, dimension_px):
        """porcentaje entero -> px (int, redondeado). None si valor_pct
        es None."""
        if valor_pct is None:
            return None
        return int(round((float(valor_pct) / 100.0) * float(dimension_px)))

    @staticmethod
    def _punto_px_a_pct(path_archivo, x_px, y_px):
        if x_px is None and y_px is None:
            return None, None
        ancho, alto = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._px_a_pct(x_px, ancho),
                Modelo._px_a_pct(y_px, alto))

    @staticmethod
    def _punto_pct_a_px(path_archivo, x_pct, y_pct):
        if x_pct is None and y_pct is None:
            return None, None
        ancho, alto = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._pct_a_px(x_pct, ancho),
                Modelo._pct_a_px(y_pct, alto))

    @staticmethod
    def _rect_px_a_pct(path_archivo, x_px, y_px, ancho_px, alto_px):
        if x_px is None and y_px is None and ancho_px is None and alto_px is None:
            return None, None, None, None
        ancho_img, alto_img = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._px_a_pct(x_px, ancho_img),
                Modelo._px_a_pct(y_px, alto_img),
                Modelo._px_a_pct(ancho_px, ancho_img),
                Modelo._px_a_pct(alto_px, alto_img))

    @staticmethod
    def _rect_pct_a_px(path_archivo, x_pct, y_pct, ancho_pct, alto_pct):
        if x_pct is None and y_pct is None and ancho_pct is None and alto_pct is None:
            return None, None, None, None
        ancho_img, alto_img = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._pct_a_px(x_pct, ancho_img),
                Modelo._pct_a_px(y_pct, alto_img),
                Modelo._pct_a_px(ancho_pct, ancho_img),
                Modelo._pct_a_px(alto_pct, alto_img))

    @staticmethod
    def _path_imagen(id_imagen):
        """path_archivo de la fila `imagen` con ese id, o None."""
        if not id_imagen:
            return None
        r = Modelo._query(
            "SELECT path_archivo FROM imagen WHERE id_imagen=?", (id_imagen,))
        return r[0][0] if r else None

    @staticmethod
    def _path_imagen_de_frame_catalogo(id_frame_catalogo):
        """path_archivo de la imagen del frame_catalogo dueño — es la que
        usan sus slots (slot_catalogo no tiene id_imagen propio)."""
        if not id_frame_catalogo:
            return None
        r = Modelo._query(
            "SELECT i.path_archivo FROM frame_catalogo fc "
            "LEFT JOIN imagen i ON i.id_imagen = fc.id_imagen "
            "WHERE fc.id_frame_catalogo=?", (id_frame_catalogo,))
        return r[0][0] if r else None

    @staticmethod
    def _path_imagen_de_slot_catalogo(id_slot_catalogo):
        """Ídem _path_imagen_de_frame_catalogo pero partiendo del
        id_slot_catalogo (para modificacion_slot_catalogo, que no recibe
        id_frame_catalogo)."""
        if not id_slot_catalogo:
            return None
        r = Modelo._query(
            "SELECT i.path_archivo FROM slot_catalogo sc "
            "LEFT JOIN frame_catalogo fc ON fc.id_frame_catalogo = sc.id_frame_catalogo "
            "LEFT JOIN imagen i ON i.id_imagen = fc.id_imagen "
            "WHERE sc.id_slot_catalogo=?", (id_slot_catalogo,))
        return r[0][0] if r else None

    @staticmethod
    def _pct_punto_o_none(path_archivo, x_px, y_px):
        """Wrapper de _punto_px_a_pct que nunca levanta: si no se pueden
        determinar las dimensiones de la imagen (falta el archivo, sin
        id_imagen, entorno sin bindings gráficos, etc.) devuelve
        (None, None) en vez de interrumpir el alta/edición — se guarda
        NULL y se puede completar después con
        Modelo.migrar_coordenadas_a_porcentaje() en cuanto la imagen esté
        disponible."""
        try:
            return Modelo._punto_px_a_pct(path_archivo, x_px, y_px)
        except DimensionesImagenError:
            return None, None

    @staticmethod
    def _pct_rect_o_none(path_archivo, x_px, y_px, ancho_px, alto_px):
        try:
            return Modelo._rect_px_a_pct(path_archivo, x_px, y_px, ancho_px, alto_px)
        except DimensionesImagenError:
            return None, None, None, None

    @staticmethod
    def _px_punto_o_crudo(path_archivo, x_pct, y_pct):
        """Wrapper de _punto_pct_a_px que nunca levanta: si no puede
        convertir (imagen no disponible en este momento/entorno) devuelve
        el valor CRUDO tal cual está guardado, en vez de None — así una
        pantalla que sólo lee (sin la carpeta de imágenes a mano, por
        ejemplo) sigue mostrando *algo* razonable en vez de perder el
        punto."""
        try:
            return Modelo._punto_pct_a_px(path_archivo, x_pct, y_pct)
        except DimensionesImagenError:
            return x_pct, y_pct

    @staticmethod
    def _px_rect_o_crudo(path_archivo, x_pct, y_pct, ancho_pct, alto_pct):
        try:
            return Modelo._rect_pct_a_px(path_archivo, x_pct, y_pct, ancho_pct, alto_pct)
        except DimensionesImagenError:
            return x_pct, y_pct, ancho_pct, alto_pct

    @staticmethod
    def migrar_coordenadas_a_porcentaje(reportar_progreso=None, _dry_run=False,
                                        forzar=False):
        """Migración ÚNICA de datos existentes: reinterpreta en el lugar
        (mismas columnas, sin agregar ninguna) las coordenadas en píxeles
        de conector/conector_catalogo/equipo/slot/slot_catalogo como
        porcentaje entero 0-100, usando el ancho/alto real de la imagen
        asociada a cada fila.

        Corré esto UNA sola vez, con la carpeta de imágenes real
        disponible en IMG_DIR — no se llama automáticamente al arrancar
        la app. HACÉ UN BACKUP DEL .db ANTES: es una conversión
        destructiva del valor guardado (no hay columna vieja para volver
        atrás).

        Idempotente por marca en `_migracion_porcentaje_imagen`: si ya se
        corrió antes en esta base, la segunda llamada no hace nada (para
        no volver a convertir un valor que ya es porcentaje) salvo que se
        pase forzar=True a propósito.

        `_dry_run=True`: calcula todo pero no escribe nada — sólo sirve
        para ver el resumen antes de aplicar de verdad; no marca la
        migración como hecha.

        `reportar_progreso(tabla, id_fila, ok, detalle)` opcional, se
        llama por cada fila procesada.

        Devuelve {"migradas": N, "sin_cambios": N,
                  "errores": [(tabla, id_fila, mensaje), ...]}."""
        with Modelo._conn_ctx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _migracion_porcentaje_imagen ("
                "  clave TEXT PRIMARY KEY, fecha TEXT)")
            ya_migrada = conn.execute(
                "SELECT 1 FROM _migracion_porcentaje_imagen "
                "WHERE clave='coordenadas_a_porcentaje'").fetchone()
        if ya_migrada and not forzar and not _dry_run:
            resumen = {"migradas": 0, "sin_cambios": 0, "errores": [],
                       "ya_migrada": True}
            return resumen

        resumen = {"migradas": 0, "sin_cambios": 0, "errores": []}

        def _procesar(tabla, id_col, x_col, y_col, extra_cols, set_cols,
                       convertir, id_imagen_expr="id_imagen"):
            cols_sel = ", ".join([id_col, x_col, y_col] + list(extra_cols) +
                                  [f"({id_imagen_expr}) AS id_imagen"])
            filas = Modelo._query(
                f"SELECT {cols_sel} FROM {tabla} WHERE {x_col} IS NOT NULL")
            for fila in filas:
                id_fila = fila[0]
                x_px, y_px = fila[1], fila[2]
                extra_vals = fila[3:3 + len(extra_cols)]
                id_imagen = fila[-1]
                if not id_imagen:
                    resumen["errores"].append(
                        (tabla, id_fila, "sin imagen asociada (id_imagen NULL)"))
                    if reportar_progreso:
                        reportar_progreso(tabla, id_fila, False,
                                           "sin imagen asociada")
                    continue
                path_archivo = Modelo._path_imagen(id_imagen)
                try:
                    valores_pct = convertir(path_archivo, x_px, y_px, *extra_vals)
                except DimensionesImagenError as ex:
                    resumen["errores"].append((tabla, id_fila, str(ex)))
                    if reportar_progreso:
                        reportar_progreso(tabla, id_fila, False, str(ex))
                    continue
                if not _dry_run:
                    set_clause = ", ".join(f"{c}=?" for c in set_cols)
                    Modelo._exec(
                        f"UPDATE {tabla} SET {set_clause} WHERE {id_col}=?",
                        (*valores_pct, id_fila))
                resumen["migradas"] += 1
                if reportar_progreso:
                    reportar_progreso(tabla, id_fila, True, None)

        _procesar(
            "conector", "id_conector",
            "coordenada_x_en_imagen", "coordenada_y_en_imagen", (),
            ("coordenada_x_en_imagen", "coordenada_y_en_imagen"),
            lambda path, x, y: Modelo._punto_px_a_pct(path, x, y))

        _procesar(
            "conector_catalogo", "id_conector_catalogo",
            "coordenada_x_en_imagen", "coordenada_y_en_imagen", (),
            ("coordenada_x_en_imagen", "coordenada_y_en_imagen"),
            lambda path, x, y: Modelo._punto_px_a_pct(path, x, y))

        _procesar(
            "equipo", "id_equipo",
            "coordenada_x_en_imagen", "coordenada_y_en_imagen", (),
            ("coordenada_x_en_imagen", "coordenada_y_en_imagen"),
            lambda path, x, y: Modelo._punto_px_a_pct(path, x, y))

        _procesar(
            "slot", "id_slot",
            "rectangulo_x_en_imagen", "rectangulo_y_en_imagen",
            ("rectangulo_ancho_pixeles", "rectangulo_alto_pixeles"),
            ("rectangulo_x_en_imagen", "rectangulo_y_en_imagen",
             "rectangulo_ancho_pixeles", "rectangulo_alto_pixeles"),
            lambda path, x, y, w, h: Modelo._rect_px_a_pct(path, x, y, w, h))

        _procesar(
            "slot_catalogo", "id_slot_catalogo",
            "rectangulo_x_en_imagen", "rectangulo_y_en_imagen",
            ("rectangulo_ancho_pixeles", "rectangulo_alto_pixeles"),
            ("rectangulo_x_en_imagen", "rectangulo_y_en_imagen",
             "rectangulo_ancho_pixeles", "rectangulo_alto_pixeles"),
            lambda path, x, y, w, h: Modelo._rect_px_a_pct(path, x, y, w, h),
            id_imagen_expr=(
                "SELECT fc.id_imagen FROM frame_catalogo fc "
                "WHERE fc.id_frame_catalogo = slot_catalogo.id_frame_catalogo"))

        if not _dry_run:
            with Modelo._conn_ctx() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO _migracion_porcentaje_imagen "
                    "(clave, fecha) VALUES ('coordenadas_a_porcentaje', "
                    "datetime('now'))")

        return resumen

    @staticmethod
    def _conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    @contextlib.contextmanager
    def _conn_ctx():
        """Como _conn() pero como context manager que SIEMPRE cierra la
        conexión al salir (commit en éxito, rollback en excepción).
        `with Modelo._conn() as conn:` en Python NO cierra la conexión
        (solo hace commit/rollback) -> causaba fuga de conexiones SQLite
        que se acumulaban en cada operación, degradando el rendimiento."""
        conn = Modelo._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _query(sql, params=()):
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(sql, params)
            return [list(row) for row in cur.fetchall()]

    @staticmethod
    def _exec(sql, params=()):
        with Modelo._conn_ctx() as conn:
            conn.execute(sql, params)
            conn.commit()

    # ── Equipos ──────────────────────────────────────────────────────────────
    @staticmethod
    def asegurar_columnas_equipo():
        """Asegura que las columnas path_manual y configuraciones existan en la tabla equipo."""
        with Modelo._conn_ctx() as conn:
            # Verificar si path_manual existe
            cursor = conn.execute("PRAGMA table_info(equipo)")
            columnas = [col[1] for col in cursor.fetchall()]
            
            if "path_manual" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN path_manual TEXT")
            
            if "configuraciones" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN configuraciones TEXT")
            
            if "picon" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN picon TEXT")

            if "fecha_fabricacion" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN fecha_fabricacion TEXT")

            if "es_equipo_usado" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN es_equipo_usado INTEGER DEFAULT 0")
            
            conn.commit()

    # ── Riesgo de falla (IRF) ────────────────────────────────────────────────
    @staticmethod
    def asegurar_tablas_riesgo():
        """Crea/migra las tablas y columnas necesarias para el cálculo del
        Índice de Riesgo de Falla (IRF):
          - tipo_equipo.vida_util_anios   : vida útil esperada por categoría
          - problema_equipo.afecta_categoria_equipo : defecto de modelo/lote
          - problema_equipo.resuelto / fecha_resolucion
          - parametro_riesgo  : pesos y constantes configurables
          - riesgo_equipo_cache : último cálculo por equipo (evita recalcular
            el grafo completo en cada apertura de ventana)
          - equipo_critico : conjunto curado a mano de equipos que son
            realmente vitales para la cadena (ver sección 'Impacto' del
            cálculo). Si está vacía, el riesgo se calcula como siempre
            (contando todo el parque); si tiene equipos cargados, el factor
            Impacto pasa a medirse contra ese conjunto específico.
        Idempotente: seguro de llamar en cada arranque de la app.
        """
        Modelo.asegurar_tablas_problemas()  # problema_equipo debe existir antes
        with Modelo._conn_ctx() as conn:
            # tipo_equipo.vida_util_anios
            cols_tipo = [c[1] for c in conn.execute(
                "PRAGMA table_info(tipo_equipo)").fetchall()]
            if "vida_util_anios" not in cols_tipo:
                conn.execute(
                    "ALTER TABLE tipo_equipo ADD COLUMN vida_util_anios INTEGER")

            # problema_equipo.afecta_categoria_equipo / resuelto / fecha_resolucion
            cols_prob = [c[1] for c in conn.execute(
                "PRAGMA table_info(problema_equipo)").fetchall()]
            if "afecta_categoria_equipo" not in cols_prob:
                conn.execute(
                    "ALTER TABLE problema_equipo "
                    "ADD COLUMN afecta_categoria_equipo INTEGER DEFAULT 0")
            if "resuelto" not in cols_prob:
                conn.execute(
                    "ALTER TABLE problema_equipo ADD COLUMN resuelto INTEGER DEFAULT 0")
            if "fecha_resolucion" not in cols_prob:
                conn.execute(
                    "ALTER TABLE problema_equipo ADD COLUMN fecha_resolucion TEXT")

            # parametro_riesgo (pesos/constantes configurables)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS parametro_riesgo ("
                "  clave TEXT PRIMARY KEY,"
                "  valor REAL"
                ")"
            )

            # riesgo_equipo_cache (último resultado calculado, para no
            # reconstruir el grafo en cada refresco de listado)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS riesgo_equipo_cache ("
                "  id_equipo     INTEGER PRIMARY KEY,"
                "  probabilidad  REAL,"
                "  impacto       REAL,"
                "  riesgo        REAL,"
                "  nivel         TEXT,"
                "  detalle_json  TEXT,"
                "  fecha_calculo TEXT,"
                "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE"
                ")"
            )

            # equipo_critico (conjunto curado a mano — ver docstring arriba)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS equipo_critico ("
                "  id_equipo  INTEGER PRIMARY KEY,"
                "  fecha_alta TEXT,"
                "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE"
                ")"
            )
            conn.commit()

        # Valores por defecto de los parámetros (solo si no existen aún, así
        # no se pisan ajustes ya hechos por el usuario en versiones futuras)
        defaults = {
            "w_edad":                  0.25,
            "w_uso":                   0.15,
            "w_historial":             0.60,
            "p_min":                   10.0,   # piso de probabilidad (nada es 0% seguro)
            "k_saturacion":            15.0,   # saturación del historial de problemas
            "decaimiento_meses":       24.0,   # vida media del peso de un problema viejo
            "vida_util_default_anios": 10.0,   # si el tipo_equipo no tiene vida_util_anios
            "s_edad_sin_dato":         50.0,   # valor neutro si falta fecha_fabricacion
            # Nota: el factor Impacto ya no pondera "puntos finales" por
            # separado (concepto ambiguo en la práctica) — usa directamente
            # la fracción de equipos que quedan sin señal, sin peso propio.
        }
        existentes = {r[0] for r in Modelo._query(
            "SELECT clave FROM parametro_riesgo")}
        for clave, valor in defaults.items():
            if clave not in existentes:
                Modelo._exec(
                    "INSERT INTO parametro_riesgo (clave, valor) VALUES (?,?)",
                    (clave, valor),
                )

    @staticmethod
    def devolver_parametros_riesgo():
        """dict {clave: valor} con todos los parámetros configurables del IRF."""
        Modelo.asegurar_tablas_riesgo()
        return {r[0]: r[1] for r in Modelo._query(
            "SELECT clave, valor FROM parametro_riesgo")}

    @staticmethod
    def actualizar_parametro_riesgo(clave, valor):
        Modelo.asegurar_tablas_riesgo()
        Modelo._exec(
            "UPDATE parametro_riesgo SET valor=? WHERE clave=?", (valor, clave)
        )

    @staticmethod
    def guardar_riesgo_equipo(id_equipo, probabilidad, impacto, riesgo, nivel, detalle_json):
        Modelo.asegurar_tablas_riesgo()
        Modelo._exec(
            "INSERT INTO riesgo_equipo_cache "
            "(id_equipo, probabilidad, impacto, riesgo, nivel, detalle_json, fecha_calculo) "
            "VALUES (?,?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')) "
            "ON CONFLICT(id_equipo) DO UPDATE SET "
            "  probabilidad=excluded.probabilidad, impacto=excluded.impacto, "
            "  riesgo=excluded.riesgo, nivel=excluded.nivel, "
            "  detalle_json=excluded.detalle_json, fecha_calculo=excluded.fecha_calculo",
            (id_equipo, probabilidad, impacto, riesgo, nivel, detalle_json),
        )

    @staticmethod
    def devolver_riesgo_equipo(id_equipo):
        """Fila cacheada de riesgo para un equipo, o None si nunca se calculó."""
        Modelo.asegurar_tablas_riesgo()
        r = Modelo._query(
            "SELECT probabilidad, impacto, riesgo, nivel, detalle_json, fecha_calculo "
            "FROM riesgo_equipo_cache WHERE id_equipo=?",
            (id_equipo,),
        )
        return r[0] if r else None

    @staticmethod
    def devolver_riesgo_todos_los_equipos():
        """dict {id_equipo(str): (riesgo, nivel)} — para poblar la columna
        Riesgo del listado de equipos sin una consulta por fila."""
        Modelo.asegurar_tablas_riesgo()
        return {str(r[0]): (r[1], r[2]) for r in Modelo._query(
            "SELECT id_equipo, riesgo, nivel FROM riesgo_equipo_cache")}

    # ── Conjunto de equipos críticos (mejora el factor Impacto del IRF) ────
    @staticmethod
    def devolver_ids_equipos_criticos():
        """set[str] con los ids marcados como críticos. Si está vacío,
        risk_engine.py calcula el factor Impacto como siempre (contando
        todo el parque); si tiene elementos, lo mide sólo contra este
        conjunto curado a mano."""
        Modelo.asegurar_tablas_riesgo()
        return {str(r[0]) for r in Modelo._query(
            "SELECT id_equipo FROM equipo_critico")}

    @staticmethod
    def es_equipo_critico(id_equipo):
        Modelo.asegurar_tablas_riesgo()
        r = Modelo._query(
            "SELECT 1 FROM equipo_critico WHERE id_equipo=?", (id_equipo,))
        return bool(r)

    @staticmethod
    def marcar_equipos_criticos(ids_equipo):
        """Agrega (INSERT OR IGNORE) los ids dados al conjunto de críticos.
        Acepta cualquier iterable de ids (str o int)."""
        Modelo.asegurar_tablas_riesgo()
        ids = [int(i) for i in ids_equipo]
        if not ids:
            return
        with Modelo._conn_ctx() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO equipo_critico (id_equipo, fecha_alta) "
                "VALUES (?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                [(i,) for i in ids],
            )
            conn.commit()

    @staticmethod
    def desmarcar_equipos_criticos(ids_equipo):
        """Saca los ids dados del conjunto de críticos."""
        Modelo.asegurar_tablas_riesgo()
        ids = [int(i) for i in ids_equipo]
        if not ids:
            return
        with Modelo._conn_ctx() as conn:
            conn.executemany(
                "DELETE FROM equipo_critico WHERE id_equipo=?",
                [(i,) for i in ids],
            )
            conn.commit()

    @staticmethod
    def establecer_equipo_critico(id_equipo, critico: bool):
        """Toggle de un único equipo (usado por el checkbox en la ficha)."""
        if critico:
            Modelo.marcar_equipos_criticos([id_equipo])
        else:
            Modelo.desmarcar_equipos_criticos([id_equipo])

    @staticmethod
    def devolver_vida_util_tipo_equipo(id_tipo_equipo):
        Modelo.asegurar_tablas_riesgo()
        if id_tipo_equipo is None:
            return None
        r = Modelo._query(
            "SELECT vida_util_anios FROM tipo_equipo WHERE id_tipo_equipo=?",
            (id_tipo_equipo,),
        )
        return r[0][0] if r and r[0][0] is not None else None

    @staticmethod
    def actualizar_vida_util_tipo_equipo(id_tipo_equipo, vida_util_anios):
        Modelo.asegurar_tablas_riesgo()
        Modelo._exec(
            "UPDATE tipo_equipo SET vida_util_anios=? WHERE id_tipo_equipo=?",
            (vida_util_anios, id_tipo_equipo),
        )

    @staticmethod
    def devolver_todos_los_equipos():
        # 7 columnas: id, nombre, marca, modelo, inventario, serie, tipo_equipo
        return Modelo._query(
            "SELECT ve.id, ve.nombre, ve.marca, ve.modelo, "
            "ve.inventario, ve.serie, "
            "COALESCE(te.nombre, '') AS tipo_equipo "
            "FROM VISTA_EQUIPOS ve "
            "LEFT JOIN equipo eq ON eq.id_equipo = ve.id "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo "
            "ORDER BY ve.nombre"
        )

    @staticmethod
    def devolver_id_todos_los_equipos():
        return Modelo._query("SELECT id_equipo FROM equipo")

    @staticmethod
    def devolver_equipos_para_riesgo():
        """Todos los equipos con lo que necesita el motor de riesgo
        (risk_engine.py): id, id_tipo_equipo, fecha_fabricacion,
        es_equipo_usado, vida_util_anios (de su tipo_equipo, si está
        cargada). Una sola consulta para todo el parque."""
        Modelo.asegurar_columnas_equipo()
        Modelo.asegurar_tablas_riesgo()
        return Modelo._query(
            "SELECT eq.id_equipo, eq.id_tipo_equipo, eq.fecha_fabricacion, "
            "COALESCE(eq.es_equipo_usado,0), te.vida_util_anios "
            "FROM equipo eq "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo"
        )

    @staticmethod
    def devolver_id_equipos_con_conexiones():
        return Modelo._query(
            "SELECT id_equipo FROM conexiones GROUP BY id_equipo"
        )

    @staticmethod
    def devolver_equipo(id_equipo):
        filas = Modelo._query(
            "SELECT eq.id_equipo AS id, eq.nombre, "
            "COALESCE(m.nombre, '') AS marca, eq.modelo, "
            "eq.num_inventario AS inventario, eq.num_serie AS serie, "
            "eq.id_marca, COALESCE(te.nombre, '') AS tipo_nombre, "
            "eq.id_tipo_equipo AS id_tipo, "
            "COALESCE(im.path_archivo, '') AS imagen_path, eq.id_imagen, "
            "eq.coordenada_x_en_imagen, eq.coordenada_y_en_imagen, "
            "eq.path_manual, eq.configuraciones, eq.picon, "
            "eq.fecha_fabricacion, eq.es_equipo_usado "
            "FROM equipo eq "
            "LEFT JOIN marca m ON m.id_marca = eq.id_marca "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo "
            "LEFT JOIN imagen im ON im.id_imagen = eq.id_imagen "
            "WHERE eq.id_equipo = ?",
            (id_equipo,),
        )
        if not filas:
            return filas
        f = list(filas[0])
        # índices: 9=imagen_path, 11=coordenada_x, 12=coordenada_y
        x_px, y_px = Modelo._px_punto_o_crudo(f[9] or None, f[11], f[12])
        f[11], f[12] = x_px, y_px
        return [tuple(f)]

    @staticmethod
    def alta_equipo(id_tipo_equipo, id_marca, num_inventario, num_serie,
                    modelo, nombre, id_imagen, x, y, path_manual=None, configuraciones=None,
                    picon=None, fecha_fabricacion=None, es_equipo_usado=0):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "INSERT INTO equipo (id_tipo_equipo, id_marca, num_inventario, "
            "num_serie, modelo, nombre, id_imagen, "
            "coordenada_x_en_imagen, coordenada_y_en_imagen, path_manual, configuraciones, picon, "
            "fecha_fabricacion, es_equipo_usado) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
             _n(num_serie), _n(modelo), _n(nombre),
             _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones), _n(picon),
             _n(fecha_fabricacion), 1 if es_equipo_usado else 0),
        )

    @staticmethod
    def modificacion_equipo(id_equipo, id_tipo_equipo, id_marca,
                            num_inventario, num_serie, modelo, nombre,
                            id_imagen, x, y, path_manual=None, configuraciones=None,
                            picon=None, fecha_fabricacion=None, es_equipo_usado=0):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "UPDATE equipo SET id_tipo_equipo=?, id_marca=?, "
            "num_inventario=?, num_serie=?, modelo=?, nombre=?, "
            "id_imagen=?, coordenada_x_en_imagen=?, "
            "coordenada_y_en_imagen=?, path_manual=?, configuraciones=?, picon=?, "
            "fecha_fabricacion=?, es_equipo_usado=? WHERE id_equipo=?",
            (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
             _n(num_serie), _n(modelo), _n(nombre),
             _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones), _n(picon),
             _n(fecha_fabricacion), 1 if es_equipo_usado else 0, id_equipo),
        )

    @staticmethod
    def eliminar_equipo(id_equipo):
        Modelo._exec("DELETE FROM equipo WHERE id_equipo=?", (id_equipo,))

    @staticmethod
    def alta_equipo_retorna_id(id_tipo_equipo, id_marca, num_inventario,
                               num_serie, modelo, nombre, id_imagen, x, y, path_manual=None, configuraciones=None,
                               picon=None, fecha_fabricacion=None, es_equipo_usado=0):
        """Igual que alta_equipo pero retornael id del registro creado."""
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO equipo (id_tipo_equipo, id_marca, num_inventario, "
                "num_serie, modelo, nombre, id_imagen, "
                "coordenada_x_en_imagen, coordenada_y_en_imagen, path_manual, configuraciones, picon, "
                "fecha_fabricacion, es_equipo_usado) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
                 _n(num_serie), _n(modelo), _n(nombre),
                 _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones), _n(picon),
                 _n(fecha_fabricacion), 1 if es_equipo_usado else 0),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def devolver_plantillas_conectores(id_tipo_equipo):
        """
        Devuelve los conectores típicos para un tipo de equipo.
        Tabla: plantilla_conector(id, id_tipo_equipo, id_tipo_conector,
                                   direccion TEXT, cantidad INT)
        Si la tabla no existe aún, retorna lista vacía.
        """
        try:
            return Modelo._query(
                "SELECT pc.id_tipo_conector, tc.nombre, pc.direccion, "
                "pc.cantidad "
                "FROM plantilla_conector pc "
                "JOIN tipo_conector tc ON tc.id_tipo_conector = pc.id_tipo_conector "
                "WHERE pc.id_tipo_equipo = ? "
                "ORDER BY pc.direccion, tc.nombre",
                (id_tipo_equipo,),
            )
        except Exception:
            return []

    @staticmethod
    def asegurar_tabla_plantillas():
        """Crea la tabla plantilla_conector si no existe."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS plantilla_conector ("
            "  id              INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_tipo_equipo  INTEGER NOT NULL,"
            "  id_tipo_conector INTEGER NOT NULL,"
            "  direccion       TEXT NOT NULL DEFAULT 'INOUT',"
            "  cantidad        INTEGER NOT NULL DEFAULT 1,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY (id_tipo_equipo)   REFERENCES tipo_equipo(id_tipo_equipo),"
            "  FOREIGN KEY (id_tipo_conector) REFERENCES tipo_conector(id_tipo_conector)"
            ")"
        )

    @staticmethod
    def guardar_plantilla_conector(id_tipo_equipo, id_tipo_conector,
                                   direccion, cantidad):
        """Inserta o actualiza una entrada de plantilla."""
        Modelo.asegurar_tabla_plantillas()
        existing = Modelo._query(
            "SELECT id FROM plantilla_conector "
            "WHERE id_tipo_equipo=? AND id_tipo_conector=? AND direccion=?",
            (id_tipo_equipo, id_tipo_conector, direccion),
        )
        if existing:
            Modelo._exec(
                "UPDATE plantilla_conector SET cantidad=? WHERE id=?",
                (cantidad, existing[0][0]),
            )
        else:
            Modelo._exec(
                "INSERT INTO plantilla_conector "
                "(id_tipo_equipo, id_tipo_conector, direccion, cantidad) "
                "VALUES (?,?,?,?)",
                (id_tipo_equipo, id_tipo_conector, direccion, cantidad),
            )

    @staticmethod
    def eliminar_plantilla_conector(id_tipo_equipo, id_tipo_conector, direccion):
        Modelo.asegurar_tabla_plantillas()
        Modelo._exec(
            "DELETE FROM plantilla_conector "
            "WHERE id_tipo_equipo=? AND id_tipo_conector=? AND direccion=?",
            (id_tipo_equipo, id_tipo_conector, direccion),
        )

    # ── Reglas lógicas de equipo (AND / OR) ──────────────────────────────────
    # Generaliza el caso "DSK necesita todas sus entradas salvo BKGD B" a
    # cualquier tipo de equipo, configurable desde la UI. Ver
    # PLAN_reglas_logicas_equipo.md para el diseño completo.
    #
    # Una regla_logica pertenece a UN equipo puntual (id_equipo) O a UN
    # tipo_equipo entero (id_tipo_equipo, "de fábrica" / plantilla) — nunca
    # ambos. Si un equipo tiene alguna regla propia, esas reemplazan por
    # completo a las de su tipo_equipo (no se combinan).
    #
    # Los miembros de una regla son, cada uno, UNA de estas tres cosas:
    #   - id_conector       : un conector de ENTRADA concreto (reglas de equipo)
    #   - patron_conector   : un nombre de conector a matchear por igualdad
    #                         (case-insensitive) contra cada equipo del tipo
    #                         (reglas de tipo_equipo — no hay un id_conector
    #                         único porque cada equipo tiene el suyo)
    #   - id_regla_miembro  : el resultado de OTRA regla (encadenado, para
    #                         lógica compuesta tipo "(A y B) o C")
    #
    # Las salidas gobernadas (regla_logica_salida) sólo se soportan como
    # conectores puntuales para reglas de EQUIPO. Si no hay filas, la regla
    # gobierna TODAS las salidas del equipo — es el único modo soportado
    # para reglas de tipo_equipo (alcanza para el caso real: DSK).
    @staticmethod
    def asegurar_tablas_regla_logica():
        """Idempotente. Una regla_logica pertenece a UN equipo puntual
        (id_equipo) o a UN tipo_equipo entero (id_tipo_equipo, plantilla
        "de fábrica" por categoría) — nunca ambos. Las reglas ligadas a un
        MOLDE de catálogo viven en tablas propias, separadas (ver
        asegurar_tablas_regla_logica_catalogo), siguiendo el mismo patrón
        que ya usa el resto del catálogo (equipo→equipo_catalogo,
        conector→conector_catalogo, frame→frame_catalogo, slot→slot_catalogo):
        no dependen de estas tablas "reales" ni comparten columnas con ellas.

        Si la tabla regla_logica ya existe con una columna id_equipo_catalogo
        (de una versión intermedia de esta función, nunca llegó a usarse en
        producción), se migra de vuelta a 2 vías con el patrón estándar de
        SQLite para cambiar un CHECK: renombrar → crear la nueva → copiar
        sólo las filas de equipo/tipo_equipo → borrar la vieja."""
        cols = Modelo._query("PRAGMA table_info(regla_logica)")
        existe = bool(cols)
        tiene_catalogo = any(c[1] == "id_equipo_catalogo" for c in cols)

        if existe and tiene_catalogo:
            with Modelo._conn_ctx() as conn:
                conn.execute("ALTER TABLE regla_logica RENAME TO regla_logica_v2_old")
                conn.execute(
                    "CREATE TABLE regla_logica ("
                    "  id_regla        INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  id_equipo       INTEGER,"
                    "  id_tipo_equipo  INTEGER,"
                    "  nombre          TEXT,"
                    "  operador        TEXT NOT NULL CHECK (operador IN ('AND','OR')),"
                    "  activa          INTEGER NOT NULL DEFAULT 1,"
                    "  orden           INTEGER NOT NULL DEFAULT 0,"
                    "  fecha_ultima_edicion TEXT,"
                    "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,"
                    "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,"
                    "  CHECK ((id_equipo IS NULL) <> (id_tipo_equipo IS NULL))"
                    ")"
                )
                conn.execute(
                    "INSERT INTO regla_logica "
                    "(id_regla, id_equipo, id_tipo_equipo, nombre, operador, "
                    " activa, orden, fecha_ultima_edicion) "
                    "SELECT id_regla, id_equipo, id_tipo_equipo, nombre, operador, "
                    "       activa, orden, fecha_ultima_edicion "
                    "FROM regla_logica_v2_old "
                    "WHERE id_equipo IS NOT NULL OR id_tipo_equipo IS NOT NULL"
                )
                conn.execute("DROP TABLE regla_logica_v2_old")
        elif not existe:
            Modelo._exec(
                "CREATE TABLE regla_logica ("
                "  id_regla        INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_equipo       INTEGER,"
                "  id_tipo_equipo  INTEGER,"
                "  nombre          TEXT,"
                "  operador        TEXT NOT NULL CHECK (operador IN ('AND','OR')),"
                "  activa          INTEGER NOT NULL DEFAULT 1,"
                "  orden           INTEGER NOT NULL DEFAULT 0,"
                "  fecha_ultima_edicion TEXT,"
                "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,"
                "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,"
                "  CHECK ((id_equipo IS NULL) <> (id_tipo_equipo IS NULL))"
                ")"
            )
        # (si ya existe en su forma de 2 vías: nada que hacer)

        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS regla_logica_miembro ("
            "  id_miembro       INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_regla         INTEGER NOT NULL,"
            "  id_conector      INTEGER,"
            "  id_regla_miembro INTEGER,"
            "  patron_conector  TEXT,"
            "  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_regla_miembro) REFERENCES regla_logica(id_regla) ON DELETE CASCADE"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS regla_logica_salida ("
            "  id_regla    INTEGER NOT NULL,"
            "  id_conector INTEGER NOT NULL,"
            "  FOREIGN KEY(id_regla) REFERENCES regla_logica(id_regla) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE"
            ")"
        )

    @staticmethod
    def asegurar_tablas_regla_logica_catalogo():
        """Idempotente. Tablas PROPIAS para reglas lógicas ligadas a un
        MOLDE de catálogo (equipo_catalogo) — mismo patrón que el resto del
        catálogo: no comparten columnas con regla_logica/regla_logica_miembro
        (las de equipos reales). Los miembros referencian id_conector_catalogo
        directamente (no hace falta matchear por nombre: el molde tiene sus
        propios conectores-molde con ids estables, a diferencia de las
        reglas de tipo_equipo que sí necesitan patron_conector porque un
        mismo tipo_equipo puede abarcar equipos con distinta cantidad/orden
        de conectores)."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS regla_logica_catalogo ("
            "  id_regla_logica_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_equipo_catalogo INTEGER NOT NULL,"
            "  nombre    TEXT,"
            "  operador  TEXT NOT NULL CHECK (operador IN ('AND','OR')),"
            "  activa    INTEGER NOT NULL DEFAULT 1,"
            "  orden     INTEGER NOT NULL DEFAULT 0,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_equipo_catalogo) REFERENCES equipo_catalogo(id_equipo_catalogo) ON DELETE CASCADE"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS regla_logica_catalogo_miembro ("
            "  id_miembro                       INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_regla_logica_catalogo         INTEGER NOT NULL,"
            "  id_conector_catalogo             INTEGER,"
            "  id_regla_logica_catalogo_miembro INTEGER,"
            "  FOREIGN KEY(id_regla_logica_catalogo) REFERENCES regla_logica_catalogo(id_regla_logica_catalogo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_catalogo) REFERENCES conector_catalogo(id_conector_catalogo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_regla_logica_catalogo_miembro) REFERENCES regla_logica_catalogo(id_regla_logica_catalogo) ON DELETE CASCADE"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS regla_logica_catalogo_salida ("
            "  id_regla_logica_catalogo INTEGER NOT NULL,"
            "  id_conector_catalogo     INTEGER NOT NULL,"
            "  FOREIGN KEY(id_regla_logica_catalogo) REFERENCES regla_logica_catalogo(id_regla_logica_catalogo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_catalogo) REFERENCES conector_catalogo(id_conector_catalogo) ON DELETE CASCADE"
            ")"
        )

    @staticmethod
    def equipos_con_regla_logica_activa():
        """Versión en LOTE de tiene_regla_logica_efectiva: set de todos los
        id_equipo (str) que tienen alguna regla lógica efectiva (propia
        activa, o heredada de su tipo_equipo si no tiene ninguna propia).
        Pensada para cargarse UNA sola vez al abrir un diagrama completo
        (ej. DiagramaConexiones._cargar), en vez de una consulta por nodo —
        evita N+1 queries (~5ms/equipo × 400+ equipos sería notorio)."""
        Modelo.asegurar_tablas_regla_logica()
        con_propia_activa = {str(eq) for (eq,) in Modelo._query(
            "SELECT DISTINCT id_equipo FROM regla_logica "
            "WHERE id_equipo IS NOT NULL AND activa=1")}
        con_propia_cualquiera = {str(eq) for (eq,) in Modelo._query(
            "SELECT DISTINCT id_equipo FROM regla_logica WHERE id_equipo IS NOT NULL")}
        tipos_con_regla_activa = {str(t) for (t,) in Modelo._query(
            "SELECT DISTINCT id_tipo_equipo FROM regla_logica "
            "WHERE id_tipo_equipo IS NOT NULL AND activa=1")}

        resultado = set(con_propia_activa)
        if tipos_con_regla_activa:
            for id_eq, id_tipo in Modelo._query("SELECT id_equipo, id_tipo_equipo FROM equipo"):
                id_eq = str(id_eq)
                if id_eq in con_propia_cualquiera:
                    continue  # tiene reglas propias (activas o no): no hereda del tipo
                if id_tipo is not None and str(id_tipo) in tipos_con_regla_activa:
                    resultado.add(id_eq)
        return resultado

    @staticmethod
    def tiene_regla_logica_efectiva(id_equipo, id_tipo_equipo=None):
        """Chequeo puntual (un solo equipo) equivalente a comprobar
        pertenencia en equipos_con_regla_logica_activa(). Para cargar un
        diagrama COMPLETO usar esa versión en lote en su lugar — llamar
        esto una vez por nodo genera N+1 queries notorias a esa escala."""
        Modelo.asegurar_tablas_regla_logica()
        propia = Modelo._query(
            "SELECT COUNT(*) FROM regla_logica WHERE id_equipo=? AND activa=1", (id_equipo,))
        if propia and propia[0][0]:
            return True
        if id_tipo_equipo is None:
            return False
        propia_total = Modelo._query(
            "SELECT COUNT(*) FROM regla_logica WHERE id_equipo=?", (id_equipo,))
        if propia_total and propia_total[0][0]:
            return False  # tiene reglas propias, aunque inactivas: no hereda del tipo
        de_tipo = Modelo._query(
            "SELECT COUNT(*) FROM regla_logica WHERE id_tipo_equipo=? AND activa=1",
            (id_tipo_equipo,))
        return bool(de_tipo and de_tipo[0][0])

    @staticmethod
    def listar_reglas_de_equipo(id_equipo, id_tipo_equipo=None):
        """Reglas efectivas para este equipo: las propias si tiene alguna
        (activa o no, para poder editarlas), si no las de su tipo_equipo.
        Devuelve [{id_regla, nombre, operador, activa, origen: 'equipo'|'tipo',
        miembros:[{tipo:'conector'|'patron'|'regla', ref}], salidas:[id_conector,...]}]
        ordenadas por `orden`.
        """
        Modelo.asegurar_tablas_regla_logica()
        propias = Modelo._query(
            "SELECT id_regla, nombre, operador, activa FROM regla_logica "
            "WHERE id_equipo=? ORDER BY orden, id_regla", (id_equipo,))
        if propias:
            filas, origen = propias, 'equipo'
        elif id_tipo_equipo is not None:
            filas = Modelo._query(
                "SELECT id_regla, nombre, operador, activa FROM regla_logica "
                "WHERE id_tipo_equipo=? ORDER BY orden, id_regla", (id_tipo_equipo,))
            origen = 'tipo'
        else:
            filas, origen = [], 'equipo'

        reglas = []
        for id_regla, nombre, operador, activa in filas:
            miembros = Modelo._query(
                "SELECT id_conector, id_regla_miembro, patron_conector "
                "FROM regla_logica_miembro WHERE id_regla=?", (id_regla,))
            miembros_out = []
            for id_conector, id_regla_miembro, patron in miembros:
                if id_conector is not None:
                    miembros_out.append({"tipo": "conector", "ref": str(id_conector)})
                elif id_regla_miembro is not None:
                    miembros_out.append({"tipo": "regla", "ref": str(id_regla_miembro)})
                else:
                    miembros_out.append({"tipo": "patron", "ref": patron})
            salidas = Modelo._query(
                "SELECT id_conector FROM regla_logica_salida WHERE id_regla=?", (id_regla,))
            reglas.append({
                "id_regla": str(id_regla), "nombre": nombre, "operador": operador,
                "activa": bool(activa), "origen": origen,
                "miembros": miembros_out,
                "salidas": [str(r[0]) for r in salidas],  # [] = todas
            })
        return reglas

    @staticmethod
    def listar_reglas_de_molde(id_equipo_catalogo):
        """Reglas del molde de catálogo, desde sus tablas propias
        (regla_logica_catalogo / _miembro / _salida — ver
        asegurar_tablas_regla_logica_catalogo). Los miembros son
        id_conector_catalogo directos (o el resultado de otra regla del
        mismo molde, encadenado). Devuelve la misma forma que
        listar_reglas_de_equipo (con origen='molde' y tipo de miembro
        'conector_catalogo') para poder reusar la UI del editor."""
        Modelo.asegurar_tablas_regla_logica_catalogo()
        filas = Modelo._query(
            "SELECT id_regla_logica_catalogo, nombre, operador, activa "
            "FROM regla_logica_catalogo WHERE id_equipo_catalogo=? "
            "ORDER BY orden, id_regla_logica_catalogo", (id_equipo_catalogo,))
        reglas = []
        for id_regla, nombre, operador, activa in filas:
            miembros = Modelo._query(
                "SELECT id_conector_catalogo, id_regla_logica_catalogo_miembro "
                "FROM regla_logica_catalogo_miembro WHERE id_regla_logica_catalogo=?",
                (id_regla,))
            miembros_out = []
            for id_cc, id_regla_miembro in miembros:
                if id_cc is not None:
                    miembros_out.append({"tipo": "conector_catalogo", "ref": str(id_cc)})
                elif id_regla_miembro is not None:
                    miembros_out.append({"tipo": "regla_catalogo", "ref": str(id_regla_miembro)})
            salidas = Modelo._query(
                "SELECT id_conector_catalogo FROM regla_logica_catalogo_salida "
                "WHERE id_regla_logica_catalogo=?", (id_regla,))
            reglas.append({
                "id_regla": str(id_regla), "nombre": nombre, "operador": operador,
                "activa": bool(activa), "origen": "molde",
                "miembros": miembros_out,
                "salidas": [str(r[0]) for r in salidas],  # [] = todas
            })
        return reglas

    @staticmethod
    def guardar_regla_logica_catalogo(id_regla, *, id_equipo_catalogo,
                                      nombre, operador, activa, orden, miembros, salidas):
        """Crea o actualiza (si id_regla no es None) una regla de MOLDE
        completa, en las tablas propias del catálogo. `miembros`: lista de
        dicts {"tipo": "conector_catalogo"|"regla_catalogo", "ref": ...}.
        `salidas`: lista de id_conector_catalogo, o [] para "todas".
        Devuelve el id_regla_logica_catalogo."""
        Modelo.asegurar_tablas_regla_logica_catalogo()
        with Modelo._conn_ctx() as conn:
            if id_regla is None:
                cur = conn.execute(
                    "INSERT INTO regla_logica_catalogo "
                    "(id_equipo_catalogo, nombre, operador, activa, orden, "
                    " fecha_ultima_edicion) "
                    "VALUES (?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                    (id_equipo_catalogo, nombre, operador, int(activa), orden))
                id_regla = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE regla_logica_catalogo SET nombre=?, operador=?, activa=?, "
                    "orden=?, fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                    "WHERE id_regla_logica_catalogo=?",
                    (nombre, operador, int(activa), orden, id_regla))
                conn.execute(
                    "DELETE FROM regla_logica_catalogo_miembro WHERE id_regla_logica_catalogo=?",
                    (id_regla,))
                conn.execute(
                    "DELETE FROM regla_logica_catalogo_salida WHERE id_regla_logica_catalogo=?",
                    (id_regla,))
            for m in miembros:
                if m["tipo"] == "conector_catalogo":
                    conn.execute(
                        "INSERT INTO regla_logica_catalogo_miembro "
                        "(id_regla_logica_catalogo, id_conector_catalogo) VALUES (?,?)",
                        (id_regla, m["ref"]))
                else:  # regla_catalogo (encadenado)
                    conn.execute(
                        "INSERT INTO regla_logica_catalogo_miembro "
                        "(id_regla_logica_catalogo, id_regla_logica_catalogo_miembro) VALUES (?,?)",
                        (id_regla, m["ref"]))
            for id_cc in salidas:
                conn.execute(
                    "INSERT INTO regla_logica_catalogo_salida "
                    "(id_regla_logica_catalogo, id_conector_catalogo) VALUES (?,?)",
                    (id_regla, id_cc))
        return str(id_regla)

    @staticmethod
    def eliminar_regla_logica_catalogo(id_regla):
        Modelo.asegurar_tablas_regla_logica_catalogo()
        Modelo._exec(
            "DELETE FROM regla_logica_catalogo WHERE id_regla_logica_catalogo=?", (id_regla,))

    @staticmethod
    def guardar_regla_logica(id_regla, *, id_equipo=None, id_tipo_equipo=None,
                             nombre, operador, activa, orden, miembros, salidas):
        """Crea o actualiza (si id_regla no es None) una regla completa,
        reemplazando sus miembros y salidas. `miembros`: lista de dicts
        {"tipo": "conector"|"patron"|"regla", "ref": ...}. `salidas`: lista
        de id_conector, o [] para "todas" (siempre [] para reglas de
        id_tipo_equipo, que sólo soporta "todas"). Exactamente uno de
        id_equipo / id_tipo_equipo debe estar seteado. Para reglas ligadas
        a un MOLDE de catálogo usar guardar_regla_logica_catalogo (tablas
        separadas). Devuelve el id_regla."""
        Modelo.asegurar_tablas_regla_logica()
        if (id_equipo is None) == (id_tipo_equipo is None):
            raise ValueError("guardar_regla_logica: exactamente uno de "
                              "id_equipo / id_tipo_equipo debe estar seteado")
        with Modelo._conn_ctx() as conn:
            if id_regla is None:
                cur = conn.execute(
                    "INSERT INTO regla_logica "
                    "(id_equipo, id_tipo_equipo, nombre, operador, activa, orden, "
                    " fecha_ultima_edicion) "
                    "VALUES (?,?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                    (id_equipo, id_tipo_equipo, nombre, operador, int(activa), orden))
                id_regla = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE regla_logica SET nombre=?, operador=?, activa=?, orden=?, "
                    "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                    "WHERE id_regla=?",
                    (nombre, operador, int(activa), orden, id_regla))
                conn.execute("DELETE FROM regla_logica_miembro WHERE id_regla=?", (id_regla,))
                conn.execute("DELETE FROM regla_logica_salida WHERE id_regla=?", (id_regla,))
            for m in miembros:
                if m["tipo"] == "conector":
                    conn.execute(
                        "INSERT INTO regla_logica_miembro (id_regla, id_conector) VALUES (?,?)",
                        (id_regla, m["ref"]))
                elif m["tipo"] == "regla":
                    conn.execute(
                        "INSERT INTO regla_logica_miembro (id_regla, id_regla_miembro) VALUES (?,?)",
                        (id_regla, m["ref"]))
                else:  # patron
                    conn.execute(
                        "INSERT INTO regla_logica_miembro (id_regla, patron_conector) VALUES (?,?)",
                        (id_regla, m["ref"]))
            for id_conector in salidas:
                conn.execute(
                    "INSERT INTO regla_logica_salida (id_regla, id_conector) VALUES (?,?)",
                    (id_regla, id_conector))
        return str(id_regla)

    @staticmethod
    def eliminar_regla_logica(id_regla):
        Modelo.asegurar_tablas_regla_logica()
        Modelo._exec("DELETE FROM regla_logica WHERE id_regla=?", (id_regla,))

    @staticmethod
    def copiar_reglas_de_tipo_a_equipo(id_equipo, id_tipo_equipo):
        """'Baja' las reglas de plantilla del tipo_equipo a este equipo
        puntual, resolviendo cada patron_conector al id_conector real de
        ESTE equipo (si existe una coincidencia; si no, ese miembro se
        omite), para que el usuario pueda ajustarlas/agregar excepciones
        sin afectar al resto de los equipos del mismo tipo. No hace nada
        si el equipo ya tiene reglas propias."""
        Modelo.asegurar_tablas_regla_logica()
        ya_tiene = Modelo._query(
            "SELECT COUNT(*) FROM regla_logica WHERE id_equipo=?", (id_equipo,))
        if ya_tiene and ya_tiene[0][0]:
            return
        conectores_equipo = Modelo._query(
            "SELECT id_conector, nombre FROM conector WHERE id_equipo=?", (id_equipo,))
        nombre_a_id = {str(nom).strip().upper(): str(cid) for cid, nom in conectores_equipo}

        reglas_tipo = Modelo._query(
            "SELECT id_regla, nombre, operador, activa, orden FROM regla_logica "
            "WHERE id_tipo_equipo=? ORDER BY orden, id_regla", (id_tipo_equipo,))
        for id_regla_tipo, nombre, operador, activa, orden in reglas_tipo:
            miembros_tipo = Modelo._query(
                "SELECT patron_conector FROM regla_logica_miembro "
                "WHERE id_regla=? AND patron_conector IS NOT NULL", (id_regla_tipo,))
            miembros_resueltos = []
            for (patron,) in miembros_tipo:
                cid = nombre_a_id.get(str(patron).strip().upper())
                if cid:
                    miembros_resueltos.append({"tipo": "conector", "ref": cid})
            if not miembros_resueltos:
                continue  # ningún conector de este equipo matchea la plantilla
            Modelo.guardar_regla_logica(
                None, id_equipo=id_equipo, nombre=nombre, operador=operador,
                activa=activa, orden=orden, miembros=miembros_resueltos, salidas=[])

    @staticmethod
    def copiar_reglas_de_molde_a_equipo(id_equipo, id_equipo_catalogo):
        """Copia las reglas del MOLDE de catálogo (tablas propias, ver
        asegurar_tablas_regla_logica_catalogo) a un equipo recién
        instanciado, como reglas de equipo normales (regla_logica con
        id_equipo). Se llama automáticamente desde
        Modelo.instanciar_desde_catalogo() — el usuario no necesita hacer
        nada para que las reglas del molde "vengan puestas" en el equipo
        nuevo. Si el molde no tiene reglas, no hace nada.

        Resolución: cada id_conector_catalogo miembro/salida se traduce a
        nombre (vía conector_catalogo) y ese nombre se busca entre los
        conectores YA COPIADOS de este equipo (deben coincidir 1:1, mismo
        nombre, porque se acaban de copiar del mismo molde). Las reglas
        encadenadas (miembro = resultado de otra regla del molde) se
        resuelven en una segunda pasada, una vez que todas las reglas ya
        tienen su id_regla nuevo en el equipo."""
        reglas_molde = Modelo.listar_reglas_de_molde(id_equipo_catalogo)
        if not reglas_molde:
            return

        nombre_por_cc = {str(cid): nom for cid, nom, *_ in
                          Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo)}
        conectores_equipo = Modelo._query(
            "SELECT id_conector, nombre FROM conector WHERE id_equipo=?", (id_equipo,))
        nombre_a_id = {str(nom).strip().upper(): str(cid) for cid, nom in conectores_equipo}

        def _resolver_cc(id_cc):
            nom = nombre_por_cc.get(id_cc)
            return nombre_a_id.get(str(nom).strip().upper()) if nom else None

        id_molde_a_id_nuevo = {}
        reglas_con_encadenado = []  # (id_regla_nuevo, regla_molde) a repasar en 2da pasada

        for regla in reglas_molde:
            miembros_directos = []
            tiene_encadenado = False
            for m in regla["miembros"]:
                if m["tipo"] == "conector_catalogo":
                    cid = _resolver_cc(m["ref"])
                    if cid:
                        miembros_directos.append({"tipo": "conector", "ref": cid})
                else:
                    tiene_encadenado = True  # se resuelve en la 2da pasada
            salidas_resueltas = [c for c in (_resolver_cc(s) for s in regla["salidas"]) if c]

            if not miembros_directos and not tiene_encadenado:
                continue  # ningún conector matchea (no debería pasar)

            id_nuevo = Modelo.guardar_regla_logica(
                None, id_equipo=id_equipo, nombre=regla["nombre"], operador=regla["operador"],
                activa=regla["activa"], orden=0,
                miembros=miembros_directos, salidas=salidas_resueltas)
            id_molde_a_id_nuevo[regla["id_regla"]] = id_nuevo
            if tiene_encadenado:
                reglas_con_encadenado.append((id_nuevo, regla))

        # 2da pasada: ahora que todas las reglas del molde ya tienen su
        # equivalente en el equipo, resolver los miembros encadenados
        # (referencian OTRA regla del mismo molde → su id_regla nuevo).
        for id_nuevo, regla in reglas_con_encadenado:
            miembros_completos = []
            for m in regla["miembros"]:
                if m["tipo"] == "conector_catalogo":
                    cid = _resolver_cc(m["ref"])
                    if cid:
                        miembros_completos.append({"tipo": "conector", "ref": cid})
                else:
                    id_ref_nuevo = id_molde_a_id_nuevo.get(m["ref"])
                    if id_ref_nuevo:
                        miembros_completos.append({"tipo": "regla", "ref": id_ref_nuevo})
            salidas_resueltas = [c for c in (_resolver_cc(s) for s in regla["salidas"]) if c]
            Modelo.guardar_regla_logica(
                id_nuevo, id_equipo=id_equipo, nombre=regla["nombre"], operador=regla["operador"],
                activa=regla["activa"], orden=0,
                miembros=miembros_completos, salidas=salidas_resueltas)

    # ── Ruteo de matrices N x N (ej. KUMO 1616) ──────────────────────────────
    @staticmethod
    def asegurar_tabla_matriz_ruteo():
        """Crea la tabla matriz_ruteo si no existe. Guarda, por conector de
        salida de un equipo tipo MATRIZ, qué conector de entrada tiene
        asignado (o NULL si está explícitamente sin asignar)."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS matriz_ruteo ("
            "  id_conector_salida  INTEGER PRIMARY KEY,"
            "  id_conector_entrada INTEGER,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_conector_salida)  REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_entrada) REFERENCES conector(id_conector) ON DELETE SET NULL"
            ")"
        )

    @staticmethod
    def existe_configuracion_matriz(id_equipo):
        """True si ya se guardó al menos una fila de ruteo para las salidas
        de este equipo (aunque sea 'sin asignar')."""
        Modelo.asegurar_tabla_matriz_ruteo()
        r = Modelo._query(
            "SELECT COUNT(*) FROM matriz_ruteo mr "
            "JOIN conector c ON c.id_conector = mr.id_conector_salida "
            "WHERE c.id_equipo = ?",
            (id_equipo,))
        return bool(r and r[0][0])

    @staticmethod
    def devolver_ruteo_matriz(id_equipo):
        """Devuelve {id_conector_salida: id_conector_entrada|None} para
        todas las salidas del equipo que ya tengan fila guardada."""
        Modelo.asegurar_tabla_matriz_ruteo()
        rows = Modelo._query(
            "SELECT mr.id_conector_salida, mr.id_conector_entrada "
            "FROM matriz_ruteo mr "
            "JOIN conector c ON c.id_conector = mr.id_conector_salida "
            "WHERE c.id_equipo = ?",
            (id_equipo,))
        return {str(r[0]): (str(r[1]) if r[1] is not None else None) for r in rows}

    @staticmethod
    def guardar_ruteo_matriz(id_equipo, mapping):
        """Guarda (INSERT OR REPLACE) el ruteo salida→entrada.
        `mapping`: {id_conector_salida: id_conector_entrada|None}."""
        Modelo.asegurar_tabla_matriz_ruteo()
        with Modelo._conn() as conn:
            for id_out, id_in in mapping.items():
                conn.execute(
                    "INSERT OR REPLACE INTO matriz_ruteo "
                    "(id_conector_salida, id_conector_entrada, fecha_ultima_edicion) "
                    "VALUES (?, ?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                    (id_out, id_in),
                )
            conn.commit()

    # ── Funciones de patchera (Fase A/B de plan_desarrollo_funcion_patchera.md) ──
    @staticmethod
    def funciones_patchera():
        """Las 4 funciones abstractas de un módulo de patchera full-normal
        (no dependen de ninguna convención de nombre — ver
        funcion_patchera en asegurar_columnas_control_idioma). Devuelve
        [{"id":, "clave":, "nombre_es":, "direccion":, "descripcion":}, ...]
        en el orden fijo BACK_ENTRADA/BACK_SALIDA/FRONT_DERIVACION/
        FRONT_INSERCION."""
        Modelo.asegurar_columnas_control_idioma()
        filas = Modelo._query(
            "SELECT id_funcion_patchera, clave, nombre_es, direccion, descripcion "
            "FROM funcion_patchera ORDER BY id_funcion_patchera")
        return [{"id": str(r[0]), "clave": r[1], "nombre_es": r[2],
                "direccion": r[3], "descripcion": r[4]} for r in filas]

    @staticmethod
    def establecer_funcion_patchera_conector(id_conector, id_funcion_patchera):
        """id_funcion_patchera puede ser None (desasignar)."""
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE conector SET id_funcion_patchera=? WHERE id_conector=?",
            (_n(id_funcion_patchera), id_conector))

    @staticmethod
    def establecer_funcion_patchera_conector_catalogo(id_conector_catalogo, id_funcion_patchera):
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE conector_catalogo SET id_funcion_patchera=? "
            "WHERE id_conector_catalogo=?",
            (_n(id_funcion_patchera), id_conector_catalogo))

    @staticmethod
    def listar_patcheras_sin_funcion_completa():
        """Reporte 'Patcheras sin función asignada' (Fase B): equipos con
        rol_senal='PATCHERA' que NO tienen las 4 funciones cubiertas por
        alguno de sus conectores — para ubicarlos de un vistazo sin
        depender de que el nombre siga ninguna convención. Devuelve
        [{"id_equipo":, "nombre":, "funciones_asignadas": int}, ...]
        ordenado por menos funciones asignadas primero (los más
        incompletos arriba)."""
        Modelo.asegurar_columnas_control_idioma()
        filas = Modelo._query(
            "SELECT e.id_equipo, e.nombre, "
            "       COUNT(DISTINCT c.id_funcion_patchera) AS asignadas "
            "FROM equipo e "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "LEFT JOIN conector c ON c.id_equipo = e.id_equipo "
            "  AND c.id_funcion_patchera IS NOT NULL "
            "WHERE te.rol_senal = 'PATCHERA' "
            "GROUP BY e.id_equipo, e.nombre "
            "HAVING asignadas < 4 "
            "ORDER BY asignadas ASC, e.nombre ASC")
        return [{"id_equipo": str(r[0]), "nombre": r[1], "funciones_asignadas": r[2]}
                for r in filas]

    # ── Asistente de diagnóstico de fallas (plan_asistente_diagnostico_fallas.md) ──
    @staticmethod
    def establecer_punto_test(id_conector, es_punto_test):
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE conector SET es_punto_test=? WHERE id_conector=?",
            (1 if es_punto_test else 0, id_conector))

    @staticmethod
    def es_punto_test(id_conector):
        Modelo.asegurar_columnas_control_idioma()
        r = Modelo._query(
            "SELECT es_punto_test FROM conector WHERE id_conector=?", (id_conector,))
        return bool(r and r[0][0])

    @staticmethod
    def crear_sesion_diagnostico(id_conector_sintoma, descripcion=None):
        """Alta de una sesión nueva (al arrancar el asistente). Devuelve el
        id_sesion — los pasos se van agregando con agregar_paso_diagnostico
        a medida que el usuario contesta, y se cierra con
        cerrar_sesion_diagnostico al llegar a un resultado (o abandonarla)."""
        Modelo.asegurar_columnas_control_idioma()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO diagnostico_sesion "
                "(id_conector_sintoma, descripcion, fecha_inicio) "
                "VALUES (?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (id_conector_sintoma, _n(descripcion)))
            return str(cur.lastrowid)

    @staticmethod
    def agregar_paso_diagnostico(id_sesion, id_conector_consultado, respuesta, orden):
        """respuesta: 'SI'|'NO'|'NO_SE' (ver sección 6.2 del plan — 'no
        pude verificar' no gasta la pregunta pero queda igual registrado
        para el historial, con esa marca)."""
        Modelo.asegurar_columnas_control_idioma()
        if respuesta not in ("SI", "NO", "NO_SE"):
            raise ValueError(f"respuesta de diagnóstico inválida: {respuesta!r}")
        Modelo._exec(
            "INSERT INTO diagnostico_paso "
            "(id_sesion, id_conector_consultado, respuesta, orden) "
            "VALUES (?,?,?,?)",
            (id_sesion, id_conector_consultado, respuesta, orden))

    @staticmethod
    def quitar_ultimo_paso_diagnostico(id_sesion):
        """Para el botón '⬅ Atrás' del asistente — barato tal como
        anticipaba el plan: borra sólo el último paso registrado."""
        Modelo.asegurar_columnas_control_idioma()
        r = Modelo._query(
            "SELECT id_paso FROM diagnostico_paso WHERE id_sesion=? "
            "ORDER BY orden DESC LIMIT 1", (id_sesion,))
        if r:
            Modelo._exec("DELETE FROM diagnostico_paso WHERE id_paso=?", (r[0][0],))
        return bool(r)

    @staticmethod
    def cerrar_sesion_diagnostico(id_sesion, resultado, id_cable_resultado=None,
                                  id_equipo_resultado=None):
        """resultado: 'CABLE_SOSPECHOSO'|'EQUIPO_SOSPECHOSO'|'ABANDONADO'."""
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE diagnostico_sesion SET resultado=?, id_cable_resultado=?, "
            "id_equipo_resultado=?, "
            "fecha_fin=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_sesion=?",
            (resultado, _n(id_cable_resultado), _n(id_equipo_resultado), id_sesion))

    @staticmethod
    def historial_diagnosticos(id_cable=None, id_equipo=None, limite=50):
        """Prontuario: sesiones ya cerradas, más recientes primero,
        filtrables por cable o equipo sospechoso (para detectar fallas
        recurrentes en un mismo punto — el pedido original del cliente)."""
        Modelo.asegurar_columnas_control_idioma()
        condiciones = ["ds.resultado IS NOT NULL"]
        params = []
        if id_cable is not None:
            condiciones.append("ds.id_cable_resultado=?")
            params.append(id_cable)
        if id_equipo is not None:
            condiciones.append("ds.id_equipo_resultado=?")
            params.append(id_equipo)
        params.append(limite)
        filas = Modelo._query(
            "SELECT ds.id_sesion, c.nombre, e.nombre, ds.descripcion, "
            "ds.resultado, cab.codigo, eqr.nombre, ds.fecha_inicio, ds.fecha_fin "
            "FROM diagnostico_sesion ds "
            "JOIN conector c ON c.id_conector = ds.id_conector_sintoma "
            "JOIN equipo e ON e.id_equipo = c.id_equipo "
            "LEFT JOIN cable cab ON cab.id_cable = ds.id_cable_resultado "
            "LEFT JOIN equipo eqr ON eqr.id_equipo = ds.id_equipo_resultado "
            "WHERE " + " AND ".join(condiciones) + " "
            "ORDER BY ds.fecha_inicio DESC LIMIT ?", tuple(params))
        return [{
            "id_sesion": str(r[0]), "conector_sintoma": r[1], "equipo_sintoma": r[2],
            "descripcion": r[3], "resultado": r[4],
            "cable_resultado": r[5], "equipo_resultado": r[6],
            "fecha_inicio": r[7], "fecha_fin": r[8],
        } for r in filas]

    @staticmethod
    def eliminar_sesion_diagnostico(id_sesion):
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec("DELETE FROM diagnostico_sesion WHERE id_sesion=?", (id_sesion,))

    @staticmethod
    def detalle_sesion_diagnostico(id_sesion):
        """Cabecera + pasos de una sesión ya cerrada, para la pantalla de
        detalle del historial. Devuelve (cabecera_dict, [paso_dict, ...])."""
        Modelo.asegurar_columnas_control_idioma()
        r = Modelo._query(
            "SELECT ds.id_sesion, c.nombre, e.nombre, ds.descripcion, "
            "ds.resultado, cab.codigo, eqr.nombre, ds.fecha_inicio, ds.fecha_fin "
            "FROM diagnostico_sesion ds "
            "JOIN conector c ON c.id_conector = ds.id_conector_sintoma "
            "JOIN equipo e ON e.id_equipo = c.id_equipo "
            "LEFT JOIN cable cab ON cab.id_cable = ds.id_cable_resultado "
            "LEFT JOIN equipo eqr ON eqr.id_equipo = ds.id_equipo_resultado "
            "WHERE ds.id_sesion=?", (id_sesion,))
        if not r:
            return None, []
        row = r[0]
        cabecera = {
            "id_sesion": str(row[0]), "conector_sintoma": row[1], "equipo_sintoma": row[2],
            "descripcion": row[3], "resultado": row[4],
            "cable_resultado": row[5], "equipo_resultado": row[6],
            "fecha_inicio": row[7], "fecha_fin": row[8],
        }
        pasos = Modelo._query(
            "SELECT dp.orden, e.nombre, c.nombre, dp.respuesta "
            "FROM diagnostico_paso dp "
            "JOIN conector c ON c.id_conector = dp.id_conector_consultado "
            "JOIN equipo e ON e.id_equipo = c.id_equipo "
            "WHERE dp.id_sesion=? ORDER BY dp.orden", (id_sesion,))
        pasos_fmt = [{"orden": p[0], "equipo": p[1], "conector": p[2], "respuesta": p[3]}
                    for p in pasos]
        return cabecera, pasos_fmt

    # ── Catálogo de equipos (moldes) ────────────────────────────────────────
    @staticmethod
    def asegurar_tablas_catalogo():
        """Crea equipo_catalogo y conector_catalogo si no existen."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS equipo_catalogo ("
            "  id_equipo_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre_molde    TEXT,"
            "  id_tipo_equipo  INTEGER,"
            "  id_marca        INTEGER,"
            "  modelo          TEXT,"
            "  id_imagen       INTEGER,"
            "  path_manual     TEXT,"
            "  configuraciones TEXT,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE SET NULL,"
            "  FOREIGN KEY(id_marca)       REFERENCES marca(id_marca)             ON DELETE SET NULL,"
            "  FOREIGN KEY(id_imagen)      REFERENCES imagen(id_imagen)           ON DELETE SET NULL"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS conector_catalogo ("
            "  id_conector_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_equipo_catalogo INTEGER NOT NULL,"
            "  nombre             TEXT,"
            "  id_tipo_conector   INTEGER,"
            "  id_imagen          INTEGER,"
            "  coordenada_x_en_imagen INTEGER,"
            "  coordenada_y_en_imagen INTEGER,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_equipo_catalogo) REFERENCES equipo_catalogo(id_equipo_catalogo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_tipo_conector)   REFERENCES tipo_conector(id_tipo_conector)     ON DELETE SET NULL,"
            "  FOREIGN KEY(id_imagen)          REFERENCES imagen(id_imagen)                   ON DELETE SET NULL"
            ")"
        )
        # Migración: asegurar que exista la columna picon en equipo_catalogo
        with Modelo._conn_ctx() as conn:
            cursor = conn.execute("PRAGMA table_info(equipo_catalogo)")
            columnas = [col[1] for col in cursor.fetchall()]
            if "picon" not in columnas:
                conn.execute("ALTER TABLE equipo_catalogo ADD COLUMN picon TEXT")
            conn.commit()
            # Fase 7 de plan_desarrollo_hardcodes_idioma.md: fila_patchera
            # también en el conector del MOLDE, para poder cargarla a mano
            # en el catálogo y que viaje en el export/import, en vez de
            # depender de que el nombre del conector siga la convención.
            cursor = conn.execute("PRAGMA table_info(conector_catalogo)")
            columnas_cc = [col[1] for col in cursor.fetchall()]
            if "fila_patchera" not in columnas_cc:
                conn.execute(
                    "ALTER TABLE conector_catalogo ADD COLUMN fila_patchera TEXT "
                    "CHECK(fila_patchera IN "
                    "('A_BACK','B_BACK','A_FRONT','B_FRONT') OR fila_patchera IS NULL)")
            conn.commit()

    @staticmethod
    def devolver_todos_los_catalogos():
        Modelo.asegurar_tablas_catalogo()
        return Modelo._query(
            "SELECT ec.id_equipo_catalogo, ec.nombre_molde, "
            "COALESCE(m.nombre,''), COALESCE(te.nombre,''), ec.modelo, "
            "(SELECT COUNT(*) FROM conector_catalogo cc "
            " WHERE cc.id_equipo_catalogo=ec.id_equipo_catalogo) AS n_conectores "
            "FROM equipo_catalogo ec "
            "LEFT JOIN marca m ON m.id_marca = ec.id_marca "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = ec.id_tipo_equipo "
            "ORDER BY ec.nombre_molde"
        )

    @staticmethod
    def devolver_catalogo(id_equipo_catalogo):
        Modelo.asegurar_tablas_catalogo()
        return Modelo._query(
            "SELECT ec.id_equipo_catalogo, ec.nombre_molde, "
            "ec.id_tipo_equipo, COALESCE(te.nombre,''), "
            "ec.id_marca, COALESCE(m.nombre,''), ec.modelo, "
            "ec.id_imagen, COALESCE(i.path_archivo,''), "
            "ec.path_manual, ec.configuraciones, ec.picon "
            "FROM equipo_catalogo ec "
            "LEFT JOIN marca m ON m.id_marca = ec.id_marca "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = ec.id_tipo_equipo "
            "LEFT JOIN imagen i ON i.id_imagen = ec.id_imagen "
            "WHERE ec.id_equipo_catalogo=?",
            (id_equipo_catalogo,),
        )

    @staticmethod
    def alta_catalogo(nombre_molde, id_tipo_equipo, id_marca, modelo,
                      id_imagen, path_manual=None, configuraciones=None,
                      picon=None):
        Modelo.asegurar_tablas_catalogo()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO equipo_catalogo "
                "(nombre_molde, id_tipo_equipo, id_marca, modelo, id_imagen, "
                "path_manual, configuraciones, picon) VALUES (?,?,?,?,?,?,?,?)",
                (_n(nombre_molde), _n(id_tipo_equipo), _n(id_marca), _n(modelo),
                 _n(id_imagen), _n(path_manual), _n(configuraciones), _n(picon)),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def modificacion_catalogo(id_equipo_catalogo, nombre_molde, id_tipo_equipo,
                              id_marca, modelo, id_imagen,
                              path_manual=None, configuraciones=None,
                              picon=None):
        Modelo.asegurar_tablas_catalogo()
        Modelo._exec(
            "UPDATE equipo_catalogo SET nombre_molde=?, id_tipo_equipo=?, "
            "id_marca=?, modelo=?, id_imagen=?, path_manual=?, configuraciones=?, picon=? "
            "WHERE id_equipo_catalogo=?",
            (_n(nombre_molde), _n(id_tipo_equipo), _n(id_marca), _n(modelo),
             _n(id_imagen), _n(path_manual), _n(configuraciones), _n(picon), id_equipo_catalogo),
        )

    @staticmethod
    def eliminar_catalogo(id_equipo_catalogo):
        Modelo.asegurar_tablas_catalogo()
        Modelo._exec(
            "DELETE FROM equipo_catalogo WHERE id_equipo_catalogo=?",
            (id_equipo_catalogo,),
        )

    @staticmethod
    def devolver_conectores_de_catalogo(id_equipo_catalogo):
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_columnas_control_idioma()
        filas = Modelo._query(
            "SELECT cc.id_conector_catalogo, cc.nombre, "
            "COALESCE(tc.nombre,''), cc.id_tipo_conector, "
            "cc.id_imagen, COALESCE(i.path_archivo,''), "
            "cc.coordenada_x_en_imagen, cc.coordenada_y_en_imagen, "
            "cc.fila_patchera, fp.clave "
            "FROM conector_catalogo cc "
            "LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = cc.id_tipo_conector "
            "LEFT JOIN imagen i ON i.id_imagen = cc.id_imagen "
            "LEFT JOIN funcion_patchera fp "
            "  ON fp.id_funcion_patchera = cc.id_funcion_patchera "
            "WHERE cc.id_equipo_catalogo=? ORDER BY cc.nombre",
            (id_equipo_catalogo,),
        )
        resultado = []
        for fila in filas:
            f = list(fila)
            # índices: 5=path_imagen, 6=coordenada_x, 7=coordenada_y
            x_px, y_px = Modelo._px_punto_o_crudo(f[5] or None, f[6], f[7])
            f[6], f[7] = x_px, y_px
            resultado.append(tuple(f))
        return resultado

    @staticmethod
    def agregar_conector_catalogo(id_equipo_catalogo, nombre, id_tipo_conector,
                                  id_imagen, x, y, fila_patchera=None,
                                  id_funcion_patchera=None):
        """fila_patchera: parámetro LEGADO (Fase A-C de
        plan_desarrollo_funcion_patchera.md) — se mantiene sólo para no
        romper llamadas existentes; la UI nueva ya no lo escribe, escribe
        id_funcion_patchera en su lugar (columna independiente de
        cualquier convención de nombre, ver Modelo.funciones_patchera)."""
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_columnas_control_idioma()
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "INSERT INTO conector_catalogo "
            "(id_equipo_catalogo, nombre, id_tipo_conector, id_imagen, "
            "coordenada_x_en_imagen, coordenada_y_en_imagen, fila_patchera, "
            "id_funcion_patchera) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (id_equipo_catalogo, _n(nombre), _n(id_tipo_conector),
             _n(id_imagen), x_pct, y_pct, _n(fila_patchera),
             _n(id_funcion_patchera)),
        )

    @staticmethod
    def modificacion_conector_catalogo(id_conector_catalogo, nombre,
                                       id_tipo_conector, id_imagen, x, y,
                                       fila_patchera=None,
                                       id_funcion_patchera=None,
                                       _tocar_funcion_patchera=False):
        """Ídem agregar_conector_catalogo respecto de fila_patchera/
        id_funcion_patchera. `_tocar_funcion_patchera`: por defecto False
        para no pisar en silencio una función ya asignada cuando el
        llamador ni siquiera pasó el parámetro (varios call sites viejos
        no lo conocen todavía) — pasar True explícitamente cuando sí se
        quiere escribir id_funcion_patchera (aunque sea a NULL)."""
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_columnas_control_idioma()
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        if _tocar_funcion_patchera:
            Modelo._exec(
                "UPDATE conector_catalogo SET nombre=?, id_tipo_conector=?, "
                "id_imagen=?, coordenada_x_en_imagen=?, coordenada_y_en_imagen=?, "
                "fila_patchera=?, id_funcion_patchera=? "
                "WHERE id_conector_catalogo=?",
                (_n(nombre), _n(id_tipo_conector), _n(id_imagen),
                 x_pct, y_pct, _n(fila_patchera), _n(id_funcion_patchera),
                 id_conector_catalogo),
            )
        else:
            Modelo._exec(
                "UPDATE conector_catalogo SET nombre=?, id_tipo_conector=?, "
                "id_imagen=?, coordenada_x_en_imagen=?, coordenada_y_en_imagen=?, "
                "fila_patchera=? "
                "WHERE id_conector_catalogo=?",
                (_n(nombre), _n(id_tipo_conector), _n(id_imagen),
                 x_pct, y_pct, _n(fila_patchera), id_conector_catalogo),
            )

    @staticmethod
    def eliminar_conector_catalogo(id_conector_catalogo):
        Modelo.asegurar_tablas_catalogo()
        Modelo._exec(
            "DELETE FROM conector_catalogo WHERE id_conector_catalogo=?",
            (id_conector_catalogo,),
        )

    @staticmethod
    def instanciar_desde_catalogo(id_equipo_catalogo, nombre, num_inventario,
                                  num_serie, x, y):
        """
        Crea un equipo real copiando marca/tipo/modelo/imagen/manual/config
        del molde, y copia cada conector_catalogo a un conector real
        (mismo nombre, tipo e imagen/coords), además de las reglas lógicas
        (AND/OR) que tenga definidas el molde. Retorna id_equipo creado.
        """
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_columnas_equipo()
        rows = Modelo.devolver_catalogo(id_equipo_catalogo)
        if not rows:
            return None
        r = rows[0]
        # r: id, nombre_molde, id_tipo, tipo_nom, id_marca, marca_nom, modelo,
        #    id_imagen, img_path, path_manual, configuraciones, picon
        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo=r[2], id_marca=r[4],
            num_inventario=num_inventario, num_serie=num_serie,
            modelo=r[6], nombre=nombre,
            id_imagen=r[7], x=x, y=y,
            path_manual=r[9], configuraciones=r[10],
            picon=r[11] if len(r) > 11 else None,
        )
        for c in Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo):
            # c: id_cc, nombre, tipo_nom, id_tipo_conector, id_imagen,
            #    img_path, cx, cy, fila_patchera, clave_funcion_patchera
            id_funcion = None
            if len(c) > 9 and c[9]:
                # La función de patchera del molde viaja al equipo real
                # instanciado — antes de este cambio se perdía en silencio
                # acá (Modelo.agregar_conector ni siquiera tenía el
                # parámetro), obligando a re-cargarla a mano en cada
                # instancia nueva de un mismo molde de patch module.
                r_fn = Modelo._query(
                    "SELECT id_funcion_patchera FROM funcion_patchera WHERE clave=?",
                    (c[9],))
                id_funcion = r_fn[0][0] if r_fn else None
            Modelo.agregar_conector(
                nombre=c[1], id_equipo=id_equipo,
                id_tipo_conector=c[3], id_imagen=c[4],
                x=c[6], y=c[7], id_funcion_patchera=id_funcion,
            )
        # Las reglas lógicas del molde "vienen puestas" en el equipo nuevo
        # (se copian por nombre de conector — ver copiar_reglas_de_molde_a_equipo).
        Modelo.copiar_reglas_de_molde_a_equipo(id_equipo, id_equipo_catalogo)
        return id_equipo

    @staticmethod
    def crear_catalogo_desde_equipo(id_equipo, nombre_molde=None):
        """Crea un molde de catálogo (equipo_catalogo) a partir de un
        equipo real existente: copia los datos reutilizables (tipo, marca,
        modelo, imagen, manual, configuraciones) y sus conectores (nombre,
        tipo, imagen, coordenadas). NO copia inventario ni número de serie,
        que son propios de cada instancia física. Retorna
        (id_equipo_catalogo, n_conectores_copiados) o None si el equipo no existe."""
        Modelo.asegurar_tablas_catalogo()
        rows = Modelo.devolver_equipo(id_equipo)
        if not rows:
            return None
        r = rows[0]
        # r: id, nombre, marca, modelo, inventario, serie, id_marca,
        #    tipo_nombre, id_tipo, imagen_path, id_imagen, x, y,
        #    path_manual, configuraciones, picon
        nombre_molde = _n(nombre_molde) or (
            f"{r[1]} (molde)" if r[1] else "Molde sin nombre")
        id_cat = Modelo.alta_catalogo(
            nombre_molde=nombre_molde,
            id_tipo_equipo=r[8], id_marca=r[6], modelo=r[3],
            id_imagen=r[10], path_manual=r[13], configuraciones=r[14],
            picon=r[15] if len(r) > 15 else None,
        )
        conectores = Modelo._query(
            "SELECT nombre, id_tipo_conector, id_imagen, "
            "coordenada_x_en_imagen, coordenada_y_en_imagen "
            "FROM conector WHERE id_equipo=? ORDER BY nombre", (id_equipo,))
        for nombre, id_tc, id_img, x_pct, y_pct in conectores:
            x_px, y_px = Modelo._px_punto_o_crudo(
                Modelo._path_imagen(id_img), x_pct, y_pct)
            Modelo.agregar_conector_catalogo(
                id_equipo_catalogo=id_cat, nombre=nombre,
                id_tipo_conector=id_tc, id_imagen=id_img, x=x_px, y=y_px)
        return id_cat, len(conectores)

    # ── Catálogo de frames (moldes) ──────────────────────────────────────────
    @staticmethod
    def asegurar_tablas_catalogo_frame():
        """Crea frame_catalogo y slot_catalogo si no existen."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS frame_catalogo ("
            "  id_frame_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre_molde TEXT,"
            "  id_marca     INTEGER,"
            "  modelo       TEXT,"
            "  id_imagen    INTEGER,"
            "  path_manual  TEXT,"
            "  configuraciones TEXT,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_marca)  REFERENCES marca(id_marca)   ON DELETE SET NULL,"
            "  FOREIGN KEY(id_imagen) REFERENCES imagen(id_imagen) ON DELETE SET NULL"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS slot_catalogo ("
            "  id_slot_catalogo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_frame_catalogo INTEGER NOT NULL,"
            "  nombre TEXT,"
            "  rectangulo_x_en_imagen  INTEGER,"
            "  rectangulo_y_en_imagen  INTEGER,"
            "  rectangulo_ancho_pixeles INTEGER,"
            "  rectangulo_alto_pixeles  INTEGER,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_frame_catalogo) REFERENCES frame_catalogo(id_frame_catalogo) ON DELETE CASCADE"
            ")"
        )
        # Migración: asegurar que exista la columna picon en frame_catalogo
        with Modelo._conn_ctx() as conn:
            cursor = conn.execute("PRAGMA table_info(frame_catalogo)")
            columnas = [col[1] for col in cursor.fetchall()]
            if "picon" not in columnas:
                conn.execute("ALTER TABLE frame_catalogo ADD COLUMN picon TEXT")
            conn.commit()

    @staticmethod
    def devolver_todos_los_catalogos_frame():
        Modelo.asegurar_tablas_catalogo_frame()
        return Modelo._query(
            "SELECT fc.id_frame_catalogo, fc.nombre_molde, "
            "COALESCE(m.nombre,''), fc.modelo, "
            "(SELECT COUNT(*) FROM slot_catalogo sc "
            " WHERE sc.id_frame_catalogo=fc.id_frame_catalogo) AS n_slots "
            "FROM frame_catalogo fc "
            "LEFT JOIN marca m ON m.id_marca = fc.id_marca "
            "ORDER BY fc.nombre_molde"
        )

    @staticmethod
    def devolver_catalogo_frame(id_frame_catalogo):
        Modelo.asegurar_tablas_catalogo_frame()
        return Modelo._query(
            "SELECT fc.id_frame_catalogo, fc.nombre_molde, "
            "fc.id_marca, COALESCE(m.nombre,''), fc.modelo, "
            "fc.id_imagen, COALESCE(i.path_archivo,''), "
            "fc.path_manual, fc.configuraciones, fc.picon "
            "FROM frame_catalogo fc "
            "LEFT JOIN marca m ON m.id_marca = fc.id_marca "
            "LEFT JOIN imagen i ON i.id_imagen = fc.id_imagen "
            "WHERE fc.id_frame_catalogo=?",
            (id_frame_catalogo,),
        )

    @staticmethod
    def alta_catalogo_frame(nombre_molde, id_marca, modelo, id_imagen,
                            path_manual=None, configuraciones=None,
                            picon=None):
        Modelo.asegurar_tablas_catalogo_frame()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO frame_catalogo "
                "(nombre_molde, id_marca, modelo, id_imagen, path_manual, configuraciones, picon) "
                "VALUES (?,?,?,?,?,?,?)",
                (_n(nombre_molde), _n(id_marca), _n(modelo), _n(id_imagen),
                 _n(path_manual), _n(configuraciones), _n(picon)),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def modificacion_catalogo_frame(id_frame_catalogo, nombre_molde, id_marca,
                                    modelo, id_imagen, path_manual=None,
                                    configuraciones=None, picon=None):
        Modelo.asegurar_tablas_catalogo_frame()
        Modelo._exec(
            "UPDATE frame_catalogo SET nombre_molde=?, id_marca=?, modelo=?, "
            "id_imagen=?, path_manual=?, configuraciones=?, picon=? WHERE id_frame_catalogo=?",
            (_n(nombre_molde), _n(id_marca), _n(modelo), _n(id_imagen),
             _n(path_manual), _n(configuraciones), _n(picon), id_frame_catalogo),
        )

    @staticmethod
    def eliminar_catalogo_frame(id_frame_catalogo):
        Modelo.asegurar_tablas_catalogo_frame()
        Modelo._exec(
            "DELETE FROM frame_catalogo WHERE id_frame_catalogo=?",
            (id_frame_catalogo,),
        )

    @staticmethod
    def devolver_slots_de_catalogo_frame(id_frame_catalogo):
        Modelo.asegurar_tablas_catalogo_frame()
        filas = Modelo._query(
            "SELECT id_slot_catalogo, nombre, rectangulo_x_en_imagen, "
            "rectangulo_y_en_imagen, rectangulo_ancho_pixeles, "
            "rectangulo_alto_pixeles "
            "FROM slot_catalogo WHERE id_frame_catalogo=? ORDER BY nombre",
            (id_frame_catalogo,),
        )
        path_archivo = Modelo._path_imagen_de_frame_catalogo(id_frame_catalogo)
        resultado = []
        for id_sc, nombre, x_pct, y_pct, w_pct, h_pct in filas:
            x, y, w, h = Modelo._px_rect_o_crudo(
                path_archivo, x_pct, y_pct, w_pct, h_pct)
            resultado.append((id_sc, nombre, x, y, w, h))
        return resultado

    @staticmethod
    def agregar_slot_catalogo(id_frame_catalogo, nombre, x, y, ancho, alto):
        Modelo.asegurar_tablas_catalogo_frame()
        x_pct, y_pct, w_pct, h_pct = Modelo._pct_rect_o_none(
            Modelo._path_imagen_de_frame_catalogo(id_frame_catalogo),
            _n(x), _n(y), _n(ancho), _n(alto))
        Modelo._exec(
            "INSERT INTO slot_catalogo "
            "(id_frame_catalogo, nombre, rectangulo_x_en_imagen, "
            "rectangulo_y_en_imagen, rectangulo_ancho_pixeles, rectangulo_alto_pixeles) "
            "VALUES (?,?,?,?,?,?)",
            (id_frame_catalogo, _n(nombre), x_pct, y_pct, w_pct, h_pct),
        )

    @staticmethod
    def modificacion_slot_catalogo(id_slot_catalogo, nombre, x, y, ancho, alto):
        Modelo.asegurar_tablas_catalogo_frame()
        x_pct, y_pct, w_pct, h_pct = Modelo._pct_rect_o_none(
            Modelo._path_imagen_de_slot_catalogo(id_slot_catalogo),
            _n(x), _n(y), _n(ancho), _n(alto))
        Modelo._exec(
            "UPDATE slot_catalogo SET nombre=?, rectangulo_x_en_imagen=?, "
            "rectangulo_y_en_imagen=?, rectangulo_ancho_pixeles=?, "
            "rectangulo_alto_pixeles=? WHERE id_slot_catalogo=?",
            (_n(nombre), x_pct, y_pct, w_pct, h_pct, id_slot_catalogo),
        )

    @staticmethod
    def eliminar_slot_catalogo(id_slot_catalogo):
        Modelo.asegurar_tablas_catalogo_frame()
        Modelo._exec(
            "DELETE FROM slot_catalogo WHERE id_slot_catalogo=?",
            (id_slot_catalogo,),
        )

    @staticmethod
    def instanciar_frame_desde_catalogo(id_frame_catalogo, nombre, num_inventario):
        """
        Crea un frame real copiando marca/modelo/imagen/manual/config del
        molde, y copia cada slot_catalogo a un slot real vacío (mismo
        nombre y rectángulo; sin equipo asignado). Retorna id_frame creado.
        """
        Modelo.asegurar_tablas_catalogo_frame()
        rows = Modelo.devolver_catalogo_frame(id_frame_catalogo)
        if not rows:
            return None
        r = rows[0]
        # r: id, nombre_molde, id_marca, marca_nom, modelo, id_imagen,
        #    img_path, path_manual, configuraciones
        id_frame = None
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO frame (nombre, num_inventario, id_marca, id_imagen, modelo) "
                "VALUES (?,?,?,?,?)",
                (_n(nombre), _n(num_inventario), _n(r[2]), _n(r[5]), _n(r[4])),
            )
            conn.commit()
            id_frame = cur.lastrowid

        for sc in Modelo.devolver_slots_de_catalogo_frame(id_frame_catalogo):
            # sc: id_sc, nombre, x, y, ancho, alto
            Modelo.agregar_slot(
                nombre=sc[1], id_equipo=None, id_frame=id_frame,
                id_imagen=r[5], x=sc[2], y=sc[3], ancho=sc[4], alto=sc[5],
            )
        return id_frame

    @staticmethod
    def crear_catalogo_desde_frame(id_frame, nombre_molde=None):
        """Crea un molde de catálogo (frame_catalogo) a partir de un
        frame real existente: copia los datos reutilizables (marca,
        modelo, imagen) y sus slots (nombre y rectángulo x/y/ancho/alto),
        vacíos (sin equipo asignado) en el molde. NO copia el inventario,
        que es propio de cada instancia física. Retorna
        (id_frame_catalogo, n_slots_copiados) o None si el frame no existe."""
        Modelo.asegurar_tablas_catalogo_frame()
        rows = Modelo.devolver_frame(id_frame)
        if not rows:
            return None
        r = rows[0]
        # r: id, nombre, marca, modelo, id_marca, imagen_path, id_imagen, inventario
        nombre_molde = _n(nombre_molde) or (
            f"{r[1]} (molde)" if r[1] else "Molde sin nombre")
        id_cat = Modelo.alta_catalogo_frame(
            nombre_molde=nombre_molde,
            id_marca=r[4], modelo=r[3], id_imagen=r[6],
        )
        slots = Modelo._query(
            "SELECT id_imagen, nombre, rectangulo_x_en_imagen, rectangulo_y_en_imagen, "
            "rectangulo_ancho_pixeles, rectangulo_alto_pixeles "
            "FROM slot WHERE id_frame=? ORDER BY nombre", (id_frame,))
        for id_img_slot, nombre, x_pct, y_pct, ancho_pct, alto_pct in slots:
            x, y, ancho, alto = Modelo._px_rect_o_crudo(
                Modelo._path_imagen(id_img_slot), x_pct, y_pct, ancho_pct, alto_pct)
            Modelo.agregar_slot_catalogo(id_cat, nombre, x, y, ancho, alto)
        return id_cat, len(slots)

    # ── Export/Import de catálogos (equipos y frames) ───────────────────────
    # Formato JSON portable entre instalaciones: marca/tipo_equipo/
    # tipo_conector se resuelven por NOMBRE (se crean si no existen) y las
    # imágenes se embeben en base64 para no depender de la carpeta /imagen
    # de origen.

    @staticmethod
    def _resolver_marca(nombre):
        nombre = _n(nombre)
        if not nombre:
            return None
        rows = Modelo._query("SELECT id_marca FROM marca WHERE nombre=?", (nombre,))
        if rows:
            return rows[0][0]
        with Modelo._conn_ctx() as conn:
            cur = conn.execute("INSERT INTO marca (nombre) VALUES (?)", (nombre,))
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def _resolver_tipo_equipo(nombre, rol_senal=None):
        """Resuelve tipo_equipo por nombre, creándolo si no existe (Fase 7
        de plan_desarrollo_hardcodes_idioma.md).
        Si el tipo NO existe: se crea con `rol_senal` (validado contra
        Modelo.ROLES_SENAL; si viene vacío/inválido, default 'DISTRIBUIDOR'
        silencioso, igual que el comportamiento previo a esta fase).
        Si el tipo YA existe con un rol_senal distinto al recibido: NO se
        pisa — se devuelve el conflicto para que lo resuelva la UI (mismo
        criterio que ya usa _importar_archivo_binario para no pisar un
        archivo local distinto).
        Retorna (id_tipo_equipo, conflicto) donde conflicto es None o
        {"tipo": "tipo_equipo", "nombre": nombre, "campo": "rol_senal",
         "valor_local": ..., "valor_importado": rol_senal}.
        """
        nombre = _n(nombre)
        if not nombre:
            return None, None
        Modelo.asegurar_tablas_senal()
        rows = Modelo._query(
            "SELECT id_tipo_equipo, rol_senal FROM tipo_equipo WHERE nombre=?",
            (nombre,))
        if rows:
            id_tipo, rol_local = rows[0]
            conflicto = None
            if rol_senal and rol_senal in Modelo.ROLES_SENAL and rol_local != rol_senal:
                conflicto = {
                    "id": id_tipo, "tipo": "tipo_equipo", "nombre": nombre,
                    "campo": "rol_senal",
                    "valor_local": rol_local, "valor_importado": rol_senal,
                }
            return id_tipo, conflicto
        rol_final = rol_senal if rol_senal in Modelo.ROLES_SENAL else "DISTRIBUIDOR"
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO tipo_equipo (nombre, rol_senal) VALUES (?,?)",
                (nombre, rol_final))
            conn.commit()
            return cur.lastrowid, None

    @staticmethod
    def _resolver_tipo_conector(nombre, direccion=None, es_referencia_generada=None):
        """Resuelve tipo_conector por nombre, creándolo si no existe (Fase 7).
        Mismo criterio que _resolver_tipo_equipo: si ya existe con un valor
        distinto en `direccion` o `es_referencia_generada`, no se pisa — se
        devuelve el conflicto.
        Retorna (id_tipo_conector, [conflictos])."""
        nombre = _n(nombre)
        if not nombre:
            return None, []
        Modelo.asegurar_columnas_control_idioma()
        rows = Modelo._query(
            "SELECT id_tipo_conector, direccion, es_referencia_generada "
            "FROM tipo_conector WHERE nombre=?", (nombre,))
        if rows:
            id_tc, dir_local, ref_local = rows[0]
            conflictos = []
            if direccion in ("IN", "OUT") and dir_local != direccion:
                conflictos.append({
                    "id": id_tc, "tipo": "tipo_conector", "nombre": nombre,
                    "campo": "direccion",
                    "valor_local": dir_local, "valor_importado": direccion,
                })
            if es_referencia_generada is not None:
                ref_local_bool = bool(ref_local)
                ref_imp_bool = bool(es_referencia_generada)
                if ref_local_bool != ref_imp_bool:
                    conflictos.append({
                        "id": id_tc, "tipo": "tipo_conector", "nombre": nombre,
                        "campo": "es_referencia_generada",
                        "valor_local": ref_local_bool, "valor_importado": ref_imp_bool,
                    })
            return id_tc, conflictos
        dir_final = direccion if direccion in ("IN", "OUT") else "OUT"
        ref_final = 1 if es_referencia_generada else 0
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO tipo_conector (nombre, direccion, es_referencia_generada) "
                "VALUES (?,?,?)", (nombre, dir_final, ref_final))
            conn.commit()
            return cur.lastrowid, []

    @staticmethod
    def _exportar_imagen(id_imagen):
        """Retorna {nombre_archivo, descripcion, base64} o None."""
        if not id_imagen:
            return None
        rows = Modelo.devolver_imagen(id_imagen)
        if not rows:
            return None
        path_archivo, descripcion = rows[0][1], rows[0][2]
        b64 = None
        if path_archivo:
            full_path = os.path.join(IMG_DIR, path_archivo)
            if os.path.isfile(full_path):
                with open(full_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
        return {"nombre_archivo": path_archivo, "descripcion": descripcion, "base64": b64}

    @staticmethod
    def _importar_imagen(img_dict):
        """Reconstruye/reutiliza una fila de `imagen` a partir del dict de
        _exportar_imagen. Si ya existe un archivo con ese nombre y el
        contenido difiere, guarda con sufijo '_importadoN' para no pisar
        una imagen local distinta. Retorna id_imagen o None."""
        if not img_dict or not img_dict.get("nombre_archivo"):
            return None
        nombre = img_dict["nombre_archivo"]
        b64 = img_dict.get("base64")
        descripcion = img_dict.get("descripcion")
        if b64:
            os.makedirs(IMG_DIR, exist_ok=True)
            data = base64.b64decode(b64)
            destino = os.path.join(IMG_DIR, nombre)
            if os.path.isfile(destino):
                with open(destino, "rb") as f:
                    existente = f.read()
                if existente != data:
                    base, ext = os.path.splitext(nombre)
                    i = 1
                    while True:
                        candidato = f"{base}_importado{i}{ext}"
                        destino2 = os.path.join(IMG_DIR, candidato)
                        if not os.path.isfile(destino2):
                            nombre, destino = candidato, destino2
                            break
                        i += 1
                    with open(destino, "wb") as f:
                        f.write(data)
            else:
                with open(destino, "wb") as f:
                    f.write(data)
        rows = Modelo._query("SELECT id_imagen FROM imagen WHERE path_archivo=?", (nombre,))
        if rows:
            return rows[0][0]
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO imagen (path_archivo, descripcion) VALUES (?,?)",
                (nombre, descripcion))
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def _exportar_archivo_binario(nombre_archivo, base_dir):
        """Retorna {nombre_archivo, base64} para un archivo suelto (picon o
        manual PDF, que se guardan solo como nombre de archivo en la fila,
        sin pasar por la tabla `imagen`). None si no hay nombre o falta el
        archivo en disco (en ese caso igual se pierde el contenido, pero al
        menos no rompe la exportación)."""
        nombre_archivo = _n(nombre_archivo)
        if not nombre_archivo:
            return None
        full_path = os.path.join(base_dir, nombre_archivo)
        b64 = None
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        return {"nombre_archivo": nombre_archivo, "base64": b64}

    @staticmethod
    def _importar_archivo_binario(datos, base_dir):
        """Reconstruye un archivo suelto (picon/manual) a partir del dict de
        _exportar_archivo_binario, escribiéndolo en base_dir. Si ya existe un
        archivo con ese nombre y el contenido difiere, guarda con sufijo
        '_importadoN' para no pisar un archivo local distinto. Retorna el
        nombre de archivo final a guardar en la fila (str), o None."""
        if not datos:
            return None
        if isinstance(datos, str):
            # Compatibilidad con exportaciones viejas: solo el nombre, sin
            # contenido embebido (el archivo no viaja, pero el campo no se
            # pierde silenciosamente).
            return _n(datos)
        nombre = _n(datos.get("nombre_archivo"))
        if not nombre:
            return None
        b64 = datos.get("base64")
        if not b64:
            return nombre
        data = base64.b64decode(b64)
        os.makedirs(base_dir, exist_ok=True)
        destino = os.path.join(base_dir, nombre)
        if os.path.isfile(destino):
            with open(destino, "rb") as f:
                existente = f.read()
            if existente != data:
                base, ext = os.path.splitext(nombre)
                i = 1
                while True:
                    candidato = f"{base}_importado{i}{ext}"
                    destino2 = os.path.join(base_dir, candidato)
                    if not os.path.isfile(destino2):
                        nombre, destino = candidato, destino2
                        break
                    i += 1
                with open(destino, "wb") as f:
                    f.write(data)
        else:
            with open(destino, "wb") as f:
                f.write(data)
        return nombre

    @staticmethod
    def exportar_catalogo_equipos(ids=None):
        """Exporta moldes de equipo_catalogo (+conectores +imágenes) a una
        estructura JSON-serializable. ids=None exporta todo el catálogo.
        Las imágenes se deduplican en un pool ("imagenes") por id_imagen;
        molde/conectores solo guardan "imagen_ref" (clave al pool), asi
        una imagen compartida por varios conectores no se repite en base64."""
        Modelo.asegurar_tablas_catalogo()
        pool_imagenes = {}

        def _ref_imagen(id_imagen):
            if not id_imagen:
                return None
            key = str(id_imagen)
            if key not in pool_imagenes:
                pool_imagenes[key] = Modelo._exportar_imagen(id_imagen)
            return key

        if ids:
            placeholders = ",".join("?" * len(ids))
            filas = Modelo._query(
                "SELECT id_equipo_catalogo, nombre_molde, id_tipo_equipo, id_marca, "
                "modelo, id_imagen, path_manual, configuraciones, picon FROM equipo_catalogo "
                f"WHERE id_equipo_catalogo IN ({placeholders})", tuple(ids))
        else:
            filas = Modelo._query(
                "SELECT id_equipo_catalogo, nombre_molde, id_tipo_equipo, id_marca, "
                "modelo, id_imagen, path_manual, configuraciones, picon FROM equipo_catalogo")

        moldes = []
        for r in filas:
            id_cat, nombre_molde, id_tipo, id_marca, modelo, id_imagen, path_manual, configuraciones, picon = r
            nombre_tipo = None
            rol_tipo = None
            if id_tipo:
                t = Modelo.devolver_tipo(id_tipo)
                nombre_tipo = t[0][1] if t else None
                if nombre_tipo:
                    rol_tipo = Modelo.devolver_rol_senal_tipo_equipo(id_tipo)
            nombre_marca = None
            if id_marca:
                mrc = Modelo.devolver_marca(id_marca)
                nombre_marca = mrc[0][1] if mrc else None
            conectores = []
            nombre_por_cc_export = {}
            for c in Modelo.devolver_conectores_de_catalogo(id_cat):
                # c: id_cc, nombre, tipo_nom, id_tipo_conector, id_imagen,
                # img_path, x, y, fila_patchera, clave_funcion_patchera
                direccion_c = None
                es_ref_c = None
                if c[3]:
                    tc_rows = Modelo._query(
                        "SELECT direccion, es_referencia_generada "
                        "FROM tipo_conector WHERE id_tipo_conector=?", (c[3],))
                    if tc_rows:
                        direccion_c, es_ref_c = tc_rows[0]
                        es_ref_c = bool(es_ref_c)
                conectores.append({
                    "nombre": c[1],
                    "tipo_conector": c[2] or None,
                    "direccion": direccion_c,
                    "es_referencia_generada": es_ref_c,
                    "x": c[6], "y": c[7],
                    # Fase E de plan_desarrollo_funcion_patchera.md: se
                    # exporta por CLAVE estable ("BACK_ENTRADA", etc.), no
                    # por id numérico ni por el viejo literal
                    # "A_BACK"/"B_BACK" de fila_patchera — así un molde de
                    # patch module de audio armado acá se importa bien en
                    # otra base sin importar qué convención de nombre use
                    # cada instalación. "fila_patchera" se deja de exportar
                    # (Fase F: dejar de escribir/emitir el campo legado).
                    "funcion_patchera": c[9] if len(c) > 9 else None,
                    "imagen_ref": _ref_imagen(c[4]),
                })
                nombre_por_cc_export[str(c[0])] = c[1]
            reglas_molde = Modelo.listar_reglas_de_molde(id_cat)
            # Se exporta por NOMBRE de conector, no por id_conector_catalogo
            # (que no significa nada en otra instalación) — mismo criterio
            # que ya usa la lista "conectores". Un miembro encadenado
            # (resultado de otra regla del mismo molde) se exporta como
            # {"regla_previa": <índice 0-based dentro de esta misma lista>}
            # en vez de un id, para que sobreviva el viaje a otra base.
            id_regla_a_indice = {r["id_regla"]: i for i, r in enumerate(reglas_molde)}
            reglas = []
            for regla in reglas_molde:
                miembros_exp = []
                for m in regla["miembros"]:
                    if m["tipo"] == "conector_catalogo":
                        nom = nombre_por_cc_export.get(m["ref"])
                        if nom:
                            miembros_exp.append(nom)
                    else:  # regla_catalogo (encadenado)
                        idx = id_regla_a_indice.get(m["ref"])
                        if idx is not None:
                            miembros_exp.append({"regla_previa": idx})
                salidas_exp = [nombre_por_cc_export.get(s) for s in regla["salidas"]]
                salidas_exp = [s for s in salidas_exp if s]
                reglas.append({
                    "nombre": regla["nombre"],
                    "operador": regla["operador"],
                    "activa": regla["activa"],
                    "miembros": miembros_exp,
                    "salidas": salidas_exp,  # [] = todas
                })
            moldes.append({
                "nombre_molde": nombre_molde,
                # v4: "tipo_equipo" pasa a ser {nombre, rol_senal} en vez de
                # sólo el nombre — sin esto, un molde PATCHERA/ENRUTADOR/
                # FUENTE exportado "olvidaba" su rol y caía a DISTRIBUIDOR
                # en cualquier base destino donde ese tipo_equipo todavía no
                # existiera (Fase 7 de plan_desarrollo_hardcodes_idioma.md).
                "tipo_equipo": ({"nombre": nombre_tipo, "rol_senal": rol_tipo}
                                if nombre_tipo else None),
                "marca": nombre_marca,
                "modelo": modelo,
                "path_manual": path_manual,
                "manual": Modelo._exportar_archivo_binario(path_manual, MANUALES_DIR),
                "configuraciones": configuraciones,
                "imagen_ref": _ref_imagen(id_imagen),
                "picon": Modelo._exportar_archivo_binario(picon, PICON_DIR),
                "conectores": conectores,
                "reglas": reglas,
            })
        return {"tipo": "cabledoc_catalogo_equipos", "version": 5,
                "imagenes": pool_imagenes, "moldes": moldes}

    @staticmethod
    def importar_catalogo_equipos(data):
        """Importa moldes desde la estructura de exportar_catalogo_equipos.
        Resuelve marca/tipo_equipo/tipo_conector por nombre (los crea si no
        existen) y reutiliza imágenes ya presentes en /imagen.
        Compatibilidad: "tipo_equipo" puede ser un string (v1-v3, sólo el
        nombre) o un dict {"nombre","rol_senal"} (v4) — en ambos casos, si
        el tipo no existe en la base destino se crea con el rol recibido
        (o 'DISTRIBUIDOR' si es v1-v3 sin rol); si ya existe con un rol
        distinto, NO se pisa, se acumula como conflicto.
        Retorna (n_moldes_creados, n_conectores_creados, conflictos), donde
        conflictos es una lista de dicts (ver _resolver_tipo_equipo /
        _resolver_tipo_conector) para que la UI decida qué hacer — nunca se
        pisa silenciosamente un rol_senal/direccion ya configurado en la
        base destino.
        Fase E de plan_desarrollo_funcion_patchera.md: la función de
        patchera de cada conector se resuelve por CLAVE estable
        ("funcion_patchera": "BACK_ENTRADA", etc. — v5), con compatibilidad
        hacia atrás para exports v≤4 que todavía traían "fila_patchera"
        con el literal de la convención vieja ("A_BACK", etc.)."""
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_columnas_control_idioma()
        moldes = data.get("moldes", []) if isinstance(data, dict) else []
        pool_imagenes = data.get("imagenes", {}) if isinstance(data, dict) else {}
        cache_img = {}   # key del pool -> id_imagen ya importado (evita releer/duplicar)
        conflictos = []

        # Fase E de plan_desarrollo_funcion_patchera.md: resolver la CLAVE
        # de función ("BACK_ENTRADA", etc.) a su id_funcion_patchera en
        # ESTA base — funciona igual sin importar qué convención de nombre
        # use la instalación de origen o la de destino, porque nunca se
        # mira ningún nombre de conector. Compatibilidad con exports viejos
        # (v≤4, campo "fila_patchera" con los literales de la convención
        # anterior): se traducen con el mismo mapeo 1:1 que ya usa la
        # migración de esquema, sin volver a mirar el nombre.
        _cache_id_funcion = {}
        _MAPEO_FILA_LEGADA = {
            "A_BACK": "BACK_ENTRADA", "B_BACK": "BACK_SALIDA",
            "A_FRONT": "FRONT_DERIVACION", "B_FRONT": "FRONT_INSERCION",
        }

        def _resolver_id_funcion_patchera(c):
            clave = c.get("funcion_patchera")
            if not clave:
                clave = _MAPEO_FILA_LEGADA.get(c.get("fila_patchera"))
            if not clave:
                return None
            if clave not in _cache_id_funcion:
                r = Modelo._query(
                    "SELECT id_funcion_patchera FROM funcion_patchera WHERE clave=?",
                    (clave,))
                _cache_id_funcion[clave] = str(r[0][0]) if r else None
            return _cache_id_funcion[clave]

        def _resolver_imagen(entidad):
            # v2: "imagen_ref" (clave al pool) ; v1: "imagen" (dict embebido)
            if "imagen_ref" in entidad:
                key = entidad.get("imagen_ref")
                if not key:
                    return None
                if key not in cache_img:
                    cache_img[key] = Modelo._importar_imagen(pool_imagenes.get(key))
                return cache_img[key]
            return Modelo._importar_imagen(entidad.get("imagen"))

        n_moldes = 0
        n_conectores = 0
        for m in moldes:
            tipo_raw = m.get("tipo_equipo")
            if isinstance(tipo_raw, dict):
                nombre_tipo = tipo_raw.get("nombre")
                rol_tipo = tipo_raw.get("rol_senal")
            else:
                nombre_tipo = tipo_raw  # v1-v3: string plano, sin rol
                rol_tipo = None
            id_tipo, conf_tipo = Modelo._resolver_tipo_equipo(nombre_tipo, rol_tipo)
            if conf_tipo:
                conflictos.append(conf_tipo)
            id_marca = Modelo._resolver_marca(m.get("marca"))
            id_imagen = _resolver_imagen(m)
            # "manual" (v3, embebido en base64) tiene prioridad; si no está
            # presente, cae a "path_manual" (v1/v2, solo el nombre de archivo,
            # sin contenido — el mejor esfuerzo posible con exports viejos).
            nombre_manual = Modelo._importar_archivo_binario(
                m.get("manual"), MANUALES_DIR)
            if not nombre_manual:
                nombre_manual = _n(m.get("path_manual"))
            nombre_picon = Modelo._importar_archivo_binario(
                m.get("picon"), PICON_DIR)
            id_cat = Modelo.alta_catalogo(
                nombre_molde=m.get("nombre_molde"),
                id_tipo_equipo=id_tipo, id_marca=id_marca,
                modelo=m.get("modelo"), id_imagen=id_imagen,
                path_manual=nombre_manual,
                configuraciones=m.get("configuraciones"),
                picon=nombre_picon,
            )
            n_moldes += 1
            for c in m.get("conectores", []):
                id_tc, confs_c = Modelo._resolver_tipo_conector(
                    c.get("tipo_conector"), c.get("direccion"),
                    c.get("es_referencia_generada"))
                conflictos.extend(confs_c)
                id_img_c = _resolver_imagen(c)
                Modelo.agregar_conector_catalogo(
                    id_equipo_catalogo=id_cat, nombre=c.get("nombre"),
                    id_tipo_conector=id_tc, id_imagen=id_img_c,
                    x=c.get("x"), y=c.get("y"),
                    id_funcion_patchera=_resolver_id_funcion_patchera(c),
                )
                n_conectores += 1
            # Reglas lógicas del molde (tablas propias, ver
            # asegurar_tablas_regla_logica_catalogo). Se cargan DESPUÉS de
            # los conectores porque hace falta resolver cada nombre al
            # id_conector_catalogo recién creado. Un miembro encadenado se
            # exportó como {"regla_previa": <índice>}, referenciando otra
            # regla de esta misma lista por posición — se resuelve con
            # ids_creados, que ya tiene todo lo procesado hasta acá (el
            # export sólo genera referencias hacia atrás).
            id_cc_por_nombre = {str(nom).strip().upper(): str(cid)
                                 for cid, nom, *_ in Modelo.devolver_conectores_de_catalogo(id_cat)}
            ids_creados = []
            for idx, regla in enumerate(m.get("reglas", [])):
                miembros_raw = regla.get("miembros", [])
                miembros = []
                for mm in miembros_raw:
                    if isinstance(mm, dict):
                        idx_ref = mm.get("regla_previa")
                        if idx_ref is not None and 0 <= idx_ref < len(ids_creados) and ids_creados[idx_ref]:
                            miembros.append({"tipo": "regla_catalogo", "ref": ids_creados[idx_ref]})
                    else:
                        cid = id_cc_por_nombre.get(str(mm).strip().upper())
                        if cid:
                            miembros.append({"tipo": "conector_catalogo", "ref": cid})
                salidas = [id_cc_por_nombre.get(str(s).strip().upper())
                           for s in regla.get("salidas", [])]
                salidas = [s for s in salidas if s]
                if not miembros:
                    ids_creados.append(None)
                    continue
                id_nuevo = Modelo.guardar_regla_logica_catalogo(
                    None, id_equipo_catalogo=id_cat,
                    nombre=regla.get("nombre") or f"Regla {idx + 1}",
                    operador=regla.get("operador", "AND"),
                    activa=regla.get("activa", True), orden=idx,
                    miembros=miembros, salidas=salidas)
                ids_creados.append(id_nuevo)
        return n_moldes, n_conectores, conflictos

    @staticmethod
    def exportar_catalogo_frames(ids=None):
        """Exporta moldes de frame_catalogo (+slots +imágenes). ids=None
        exporta todo el catálogo de frames."""
        Modelo.asegurar_tablas_catalogo_frame()
        pool_imagenes = {}

        def _ref_imagen(id_imagen):
            if not id_imagen:
                return None
            key = str(id_imagen)
            if key not in pool_imagenes:
                pool_imagenes[key] = Modelo._exportar_imagen(id_imagen)
            return key

        if ids:
            placeholders = ",".join("?" * len(ids))
            filas = Modelo._query(
                "SELECT id_frame_catalogo, nombre_molde, id_marca, modelo, "
                "id_imagen, path_manual, configuraciones, picon FROM frame_catalogo "
                f"WHERE id_frame_catalogo IN ({placeholders})", tuple(ids))
        else:
            filas = Modelo._query(
                "SELECT id_frame_catalogo, nombre_molde, id_marca, modelo, "
                "id_imagen, path_manual, configuraciones, picon FROM frame_catalogo")

        moldes = []
        for r in filas:
            id_cat, nombre_molde, id_marca, modelo, id_imagen, path_manual, configuraciones, picon = r
            nombre_marca = None
            if id_marca:
                mrc = Modelo.devolver_marca(id_marca)
                nombre_marca = mrc[0][1] if mrc else None
            slots = []
            for sc in Modelo.devolver_slots_de_catalogo_frame(id_cat):
                # sc: id_sc, nombre, x, y, ancho, alto
                slots.append({
                    "nombre": sc[1], "x": sc[2], "y": sc[3],
                    "ancho": sc[4], "alto": sc[5],
                })
            moldes.append({
                "nombre_molde": nombre_molde,
                "marca": nombre_marca,
                "modelo": modelo,
                "path_manual": path_manual,
                "manual": Modelo._exportar_archivo_binario(path_manual, MANUALES_DIR),
                "configuraciones": configuraciones,
                "imagen_ref": _ref_imagen(id_imagen),
                "picon": Modelo._exportar_archivo_binario(picon, PICON_DIR),
                "slots": slots,
            })
        return {"tipo": "cabledoc_catalogo_frames", "version": 3,
                "imagenes": pool_imagenes, "moldes": moldes}

    @staticmethod
    def importar_catalogo_frames(data):
        """Importa moldes desde la estructura de exportar_catalogo_frames.
        Retorna (n_moldes_creados, n_slots_creados)."""
        Modelo.asegurar_tablas_catalogo_frame()
        moldes = data.get("moldes", []) if isinstance(data, dict) else []
        pool_imagenes = data.get("imagenes", {}) if isinstance(data, dict) else {}
        cache_img = {}

        def _resolver_imagen(entidad):
            if "imagen_ref" in entidad:
                key = entidad.get("imagen_ref")
                if not key:
                    return None
                if key not in cache_img:
                    cache_img[key] = Modelo._importar_imagen(pool_imagenes.get(key))
                return cache_img[key]
            return Modelo._importar_imagen(entidad.get("imagen"))

        n_moldes = 0
        n_slots = 0
        for m in moldes:
            id_marca = Modelo._resolver_marca(m.get("marca"))
            id_imagen = _resolver_imagen(m)
            nombre_manual = Modelo._importar_archivo_binario(
                m.get("manual"), MANUALES_DIR)
            if not nombre_manual:
                nombre_manual = _n(m.get("path_manual"))
            nombre_picon = Modelo._importar_archivo_binario(
                m.get("picon"), PICON_DIR)
            id_cat = Modelo.alta_catalogo_frame(
                nombre_molde=m.get("nombre_molde"), id_marca=id_marca,
                modelo=m.get("modelo"), id_imagen=id_imagen,
                path_manual=nombre_manual,
                configuraciones=m.get("configuraciones"),
                picon=nombre_picon,
            )
            n_moldes += 1
            for sl in m.get("slots", []):
                Modelo.agregar_slot_catalogo(
                    id_cat, sl.get("nombre"), sl.get("x"), sl.get("y"),
                    sl.get("ancho"), sl.get("alto"))
                n_slots += 1
        return n_moldes, n_slots

    # ── Marcas ────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todas_las_marcas():
        return Modelo._query("SELECT id_marca, nombre FROM marca ORDER BY nombre")

    @staticmethod
    def devolver_marca(id_marca):
        return Modelo._query(
            "SELECT id_marca, nombre FROM marca WHERE id_marca=?", (id_marca,)
        )

    @staticmethod
    def alta_marca(nombre):
        Modelo._exec("INSERT INTO marca (nombre) VALUES (?)", (_n(nombre),))

    @staticmethod
    def modificacion_marca(id_marca, nombre):
        Modelo._exec(
            "UPDATE marca SET nombre=? WHERE id_marca=?", (_n(nombre), id_marca)
        )

    @staticmethod
    def eliminar_marca(id_marca):
        Modelo._exec("DELETE FROM marca WHERE id_marca=?", (id_marca,))

    # ── Tipos de equipo ───────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_tipos():
        return Modelo._query(
            "SELECT id_tipo_equipo, nombre FROM tipo_equipo ORDER BY nombre"
        )

    @staticmethod
    def devolver_tipo(id_tipo):
        return Modelo._query(
            "SELECT id_tipo_equipo, nombre FROM tipo_equipo WHERE id_tipo_equipo=?",
            (id_tipo,),
        )

    @staticmethod
    def devolver_id_tipo_equipo_fantasma():
        """id_tipo_equipo cuyo rol_senal es 'FANTASMA' (placeholder para un
        extremo de cable confirmado desconectado — ver plan_desarrollo_
        fantasma_rapido.md), o None si el catálogo todavía no tiene ninguno
        marcado con ese rol. Se busca por rol_senal (columna estable), no
        por nombre, siguiendo el mismo criterio que el resto de los roles
        de señal desde plan_desarrollo_hardcodes_idioma.md."""
        rows = Modelo._query(
            "SELECT id_tipo_equipo FROM tipo_equipo "
            "WHERE rol_senal='FANTASMA' LIMIT 1"
        )
        return rows[0][0] if rows else None

    @staticmethod
    def alta_tipo(nombre, rol_senal=None):
        """rol_senal es opcional (compatibilidad con el alta simple que ya
        existía); si no se pasa, la columna usa su DEFAULT 'DISTRIBUIDOR'.
        Si se pasa, se valida siempre contra Modelo.ROLES_SENAL (antes sólo
        lo validaba establecer_rol_senal_tipo_equipo(), así que un alta con
        un rol_senal inválido pasado directamente acá no fallaba hasta
        chocar con el CHECK de la tabla — ahora falla temprano y claro).
        Devuelve el id_tipo_equipo recién insertado."""
        if rol_senal is not None:
            if rol_senal not in Modelo.ROLES_SENAL:
                raise ValueError(
                    f"rol_senal inválido: {rol_senal!r} "
                    f"(debe ser uno de {Modelo.ROLES_SENAL})"
                )
            Modelo.asegurar_tablas_senal()
        with Modelo._conn_ctx() as conn:
            if rol_senal is not None:
                cur = conn.execute(
                    "INSERT INTO tipo_equipo (nombre, rol_senal) VALUES (?,?)",
                    (_n(nombre), rol_senal),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO tipo_equipo (nombre) VALUES (?)", (_n(nombre),)
                )
            return cur.lastrowid

    @staticmethod
    def modificacion_tipo(id_tipo, nombre):
        Modelo._exec(
            "UPDATE tipo_equipo SET nombre=? WHERE id_tipo_equipo=?",
            (_n(nombre), id_tipo),
        )

    @staticmethod
    def eliminar_tipo(id_tipo):
        Modelo._exec(
            "DELETE FROM tipo_equipo WHERE id_tipo_equipo=?", (id_tipo,)
        )

    # ── Imágenes ──────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todas_las_imagenes():
        return Modelo._query(
            "SELECT id_imagen, path_archivo, descripcion FROM imagen ORDER BY path_archivo"
        )

    @staticmethod
    def devolver_imagen(id_imagen):
        return Modelo._query(
            "SELECT id_imagen, path_archivo, descripcion FROM imagen WHERE id_imagen=?",
            (id_imagen,),
        )

    @staticmethod
    def alta_imagen(path_archivo, descripcion):
        Modelo._exec(
            "INSERT INTO imagen (path_archivo, descripcion) VALUES (?,?)",
            (_n(path_archivo), _n(descripcion)),
        )

    @staticmethod
    def modificacion_imagen(id_imagen, path_archivo, descripcion):
        Modelo._exec(
            "UPDATE imagen SET path_archivo=?, descripcion=? WHERE id_imagen=?",
            (_n(path_archivo), _n(descripcion), id_imagen),
        )

    @staticmethod
    def eliminar_imagen(id_imagen):
        Modelo._exec("DELETE FROM imagen WHERE id_imagen=?", (id_imagen,))

    @staticmethod
    def path_imagen(id_imagen):
        rows = Modelo._query(
            "SELECT path_archivo FROM imagen WHERE id_imagen=?", (id_imagen,)
        )
        return rows[0][0] if rows else ""

    # ── Vista previa visual de la señal (por CONECTOR de salida) ───────────────
    # Ver plan_vista_previa_visual_senal.md. Todo ligado a id_conector, nunca a
    # id_equipo (sección 0 del plan: un mismo equipo puede tener una salida con
    # imagen manual y otra compuesta al mismo tiempo). Mismo patrón idempotente
    # que asegurar_tablas_regla_logica: las tablas ya están en schema_db.sql
    # para instalaciones nuevas; este método es para bases ya existentes que
    # se actualizan sin recrear la base.
    @staticmethod
    def asegurar_tablas_imagen_visual():
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS imagen_senal_conector ("
            "  id_conector INTEGER PRIMARY KEY,"
            "  id_imagen   INTEGER NOT NULL,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_imagen)   REFERENCES imagen(id_imagen)   ON DELETE CASCADE"
            ")"
        )
        # estrategia_visual: si la tabla ya existe de una versión anterior
        # (CHECK sin 'AUDIO_EMBEBIDO', modo agregado para el panel de
        # vúmetros — ver plan_audio_embebido_vista_previa.md), migrar con
        # el mismo patrón estándar de SQLite para cambiar un CHECK
        # (renombrar → crear la nueva → copiar filas → borrar la vieja)
        # ya usado en asegurar_tablas_regla_logica — un CHECK no se puede
        # tocar con ALTER TABLE ni con un CREATE TABLE IF NOT EXISTS.
        _fila_sql = Modelo._query(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='estrategia_visual'")
        _existe_estrategia_visual = bool(_fila_sql)
        _check_desactualizado = (
            _existe_estrategia_visual and _fila_sql[0][0]
            and "AUDIO_EMBEBIDO" not in _fila_sql[0][0])

        if _check_desactualizado:
            with Modelo._conn_ctx() as conn:
                conn.execute(
                    "ALTER TABLE estrategia_visual RENAME TO estrategia_visual_v2_old")
                conn.execute(
                    "CREATE TABLE estrategia_visual ("
                    "  id_estrategia    INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  id_conector      INTEGER,"
                    "  id_tipo_equipo   INTEGER,"
                    "  patron_conector_salida TEXT,"
                    "  modo             TEXT NOT NULL CHECK (modo IN "
                    "    ('MOSAICO','OVERLAY','KEY','AUDIO_EMBEBIDO')),"
                    "  fecha_ultima_edicion TEXT,"
                    "  FOREIGN KEY(id_conector)    REFERENCES conector(id_conector)       ON DELETE CASCADE,"
                    "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,"
                    "  CHECK ((id_conector IS NULL) <> (id_tipo_equipo IS NULL))"
                    ")"
                )
                conn.execute(
                    "INSERT INTO estrategia_visual (id_estrategia, id_conector, "
                    " id_tipo_equipo, patron_conector_salida, modo, fecha_ultima_edicion) "
                    "SELECT id_estrategia, id_conector, id_tipo_equipo, "
                    "       patron_conector_salida, modo, fecha_ultima_edicion "
                    "FROM estrategia_visual_v2_old"
                )
                conn.execute("DROP TABLE estrategia_visual_v2_old")
        elif not _existe_estrategia_visual:
            Modelo._exec(
                "CREATE TABLE estrategia_visual ("
                "  id_estrategia    INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_conector      INTEGER,"
                "  id_tipo_equipo   INTEGER,"
                "  patron_conector_salida TEXT,"
                "  modo             TEXT NOT NULL CHECK (modo IN "
                "    ('MOSAICO','OVERLAY','KEY','AUDIO_EMBEBIDO')),"
                "  fecha_ultima_edicion TEXT,"
                "  FOREIGN KEY(id_conector)    REFERENCES conector(id_conector)       ON DELETE CASCADE,"
                "  FOREIGN KEY(id_tipo_equipo) REFERENCES tipo_equipo(id_tipo_equipo) ON DELETE CASCADE,"
                "  CHECK ((id_conector IS NULL) <> (id_tipo_equipo IS NULL))"
                ")"
            )
        # (si ya existe con el CHECK actualizado: nada que hacer)
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS estrategia_visual_miembro ("
            "  id_miembro      INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_estrategia   INTEGER NOT NULL,"
            "  id_conector     INTEGER,"
            "  patron_conector TEXT,"
            "  posicion        TEXT NOT NULL,"
            "  orden           INTEGER NOT NULL DEFAULT 0,"
            "  origen          TEXT,"
            "  FOREIGN KEY(id_estrategia) REFERENCES estrategia_visual(id_estrategia) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector)   REFERENCES conector(id_conector) ON DELETE CASCADE"
            ")"
        )
        # Migración defensiva: columna 'origen' agregada para el rol BASE
        # dinámico "<ASIGNADO POR MATRIZ>" (equipos ENRUTADOR/MATRIZ cuya
        # composición KEY debe seguir el ruteo vivo de 'Editar matriz' en
        # vez de una entrada fija) — CREATE TABLE IF NOT EXISTS no
        # retrofittea columnas si la tabla ya existía de antes.
        _cols_evm = [c[1] for c in Modelo._query(
            "PRAGMA table_info(estrategia_visual_miembro)")]
        if "origen" not in _cols_evm:
            Modelo._exec(
                "ALTER TABLE estrategia_visual_miembro ADD COLUMN origen TEXT")

    @staticmethod
    def imagen_senal_de_conector(id_conector):
        """(id_imagen, path_archivo) o None si este conector no tiene
        imagen manual asignada."""
        Modelo.asegurar_tablas_imagen_visual()
        r = Modelo._query(
            "SELECT i.id_imagen, i.path_archivo FROM imagen_senal_conector isc "
            "JOIN imagen i ON i.id_imagen = isc.id_imagen "
            "WHERE isc.id_conector=?", (id_conector,))
        return (str(r[0][0]), r[0][1]) if r else None

    @staticmethod
    def guardar_imagen_senal_conector(id_conector, path_archivo, descripcion=None):
        """Da de alta la imagen en el catálogo genérico `imagen` y la
        asigna a este conector puntual (reemplaza la anterior si había).
        Devuelve el id_imagen nuevo.

        El motor de composición (senal_visual.py) sólo sabe leer PNG
        directamente — a pedido, acá se resuelve en silencio: si el
        archivo no es PNG válido, se convierte automáticamente ANTES de
        guardarlo (ver _normalizar_imagen_a_png), así nunca llega un JPG
        al motor de composición. Si el archivo ni siquiera se puede leer
        como imagen, NO se resuelve en silencio — se levanta
        ImagenInvalidaError con un mensaje claro para que la interfaz lo
        muestre (nunca ocultar un error real, sólo la conversión de
        formato que es inofensiva)."""
        Modelo.asegurar_tablas_imagen_visual()
        path_final = Modelo._normalizar_imagen_a_png(path_archivo)
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO imagen (path_archivo, descripcion) VALUES (?,?)",
                (_n(path_final), _n(descripcion)))
            id_imagen = cur.lastrowid
            conn.execute(
                "INSERT INTO imagen_senal_conector (id_conector, id_imagen, "
                " fecha_ultima_edicion) VALUES (?,?, "
                " STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')) "
                "ON CONFLICT(id_conector) DO UPDATE SET "
                "  id_imagen=excluded.id_imagen, "
                "  fecha_ultima_edicion=excluded.fecha_ultima_edicion",
                (id_conector, id_imagen))
        return str(id_imagen)

    @staticmethod
    def _normalizar_imagen_a_png(path_archivo):
        """Garantiza que el archivo que se va a guardar como imagen de
        señal sea un PNG válido — el motor de composición (senal_visual.py)
        sólo decodifica PNG directamente (ver _superficie_desde_path ahí).

        - Si ya es un PNG válido (se verifica leyendo los bytes, no sólo
          la extensión — un .jpg renombrado a .png también se detecta y
          se convierte igual): se usa tal cual, sin tocar nada.
        - Si es otro formato que se puede decodificar (JPG, BMP, GIF sin
          animar, etc.): se convierte a PNG en silencio (conversión de
          contenedor, no cambia el contenido visual — es el caso que a
          pedido se resuelve sin interrumpir al usuario) y se guarda en
          IMG_DIR. El archivo ORIGINAL del usuario no se toca ni se borra.
        - Si no se puede leer como imagen de ninguna forma (archivo
          corrupto, no es una imagen, etc.): se levanta
          ImagenInvalidaError con un mensaje concreto — este caso NUNCA
          se resuelve en silencio, tiene que llegar a la interfaz."""
        if not path_archivo or not os.path.isfile(path_archivo):
            raise ImagenInvalidaError(
                f"El archivo no existe: {path_archivo!r}")

        if Modelo._es_png_valido(path_archivo):
            return path_archivo

        try:
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
        except Exception as ex:  # entorno sin bindings de GTK disponibles
            raise ImagenInvalidaError(
                "El archivo no es PNG y no se pudo cargar el conversor "
                f"de imágenes para convertirlo automáticamente ({ex}). "
                "Guardá el archivo como PNG y volvé a intentar."
            ) from ex

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path_archivo)
        except Exception as ex:
            raise ImagenInvalidaError(
                f"No se pudo leer {os.path.basename(path_archivo)!r} como "
                f"imagen (formato no soportado o archivo dañado): {ex}"
            ) from ex

        os.makedirs(IMG_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(path_archivo))[0]
        destino = os.path.join(IMG_DIR, f"{base}_convertida.png")
        n = 1
        while os.path.exists(destino):
            destino = os.path.join(IMG_DIR, f"{base}_convertida_{n}.png")
            n += 1
        try:
            pixbuf.savev(destino, "png", [], [])
        except Exception as ex:
            raise ImagenInvalidaError(
                f"Se pudo leer {os.path.basename(path_archivo)!r} pero "
                f"falló al convertirlo a PNG: {ex}"
            ) from ex
        return destino

    @staticmethod
    def _es_png_valido(path_archivo):
        """Chequea la FIRMA de bytes del archivo (no la extensión) para
        saber si ya es un PNG real — un .jpg renombrado a .png tiene que
        detectarse igual y convertirse, no aceptarse por el nombre."""
        try:
            with open(path_archivo, "rb") as f:
                firma = f.read(8)
            return firma == b"\x89PNG\r\n\x1a\n"
        except OSError:
            return False

    @staticmethod
    def quitar_imagen_senal_conector(id_conector):
        Modelo.asegurar_tablas_imagen_visual()
        Modelo._exec(
            "DELETE FROM imagen_senal_conector WHERE id_conector=?", (id_conector,))

    # Sentinel usado como "id_conector" de un miembro de estrategia_visual
    # cuando el rol es dinámico ("<ASIGNADO POR MATRIZ>", ver
    # estrategia_visual_efectiva/guardar_estrategia_visual más abajo) —
    # nunca colisiona con un id_conector real (esos son enteros).
    ID_ASIGNADO_POR_MATRIZ = "MATRIZ"

    @staticmethod
    def estrategia_visual_efectiva(id_conector):
        """Estrategia que gobierna este conector de salida puntual: la
        propia (id_conector) si existe; si no, la de su tipo_equipo cuyo
        patron_conector_salida matchee (por igualdad, mayúsculas/trim,
        mismo criterio que patron_conector en regla_logica) el NOMBRE de
        este conector. Devuelve dict {id_estrategia, modo, miembros:
        [{"id_conector":..,"posicion":..,"orden":..}, ...]} o None.
        Un miembro dinámico ("<ASIGNADO POR MATRIZ>", sólo se guarda en el
        rol BASE de KEY) vuelve con "id_conector": Modelo.ID_ASIGNADO_POR_MATRIZ
        en vez de un id real — sólo para que la UI lo preseleccione; la
        resolución dinámica real vive en senal_visual.py."""
        Modelo.asegurar_tablas_imagen_visual()
        propia = Modelo._query(
            "SELECT id_estrategia, modo FROM estrategia_visual WHERE id_conector=?",
            (id_conector,))
        if propia:
            id_estrategia, modo = propia[0]
        else:
            fila = Modelo._query(
                "SELECT c.id_equipo, c.nombre, e.id_tipo_equipo "
                "FROM conector c JOIN equipo e ON e.id_equipo = c.id_equipo "
                "WHERE c.id_conector=?", (id_conector,))
            if not fila or fila[0][2] is None:
                return None
            _id_equipo, nombre_conector, id_tipo_equipo = fila[0]
            nombre_norm = (nombre_conector or "").strip().upper()
            candidatas = Modelo._query(
                "SELECT id_estrategia, modo FROM estrategia_visual "
                "WHERE id_tipo_equipo=? AND patron_conector_salida IS NOT NULL",
                (id_tipo_equipo,))
            id_estrategia = modo = None
            for cand_id, cand_modo in candidatas:
                patron = Modelo._query(
                    "SELECT patron_conector_salida FROM estrategia_visual "
                    "WHERE id_estrategia=?", (cand_id,))[0][0]
                if (patron or "").strip().upper() == nombre_norm:
                    id_estrategia, modo = cand_id, cand_modo
                    break
            if id_estrategia is None:
                return None
        miembros_raw = Modelo._query(
            "SELECT id_conector, patron_conector, posicion, orden, origen "
            "FROM estrategia_visual_miembro WHERE id_estrategia=? ORDER BY orden",
            (id_estrategia,))
        miembros = []
        for id_conector_m, patron_m, posicion, orden, origen in miembros_raw:
            if origen == "MATRIZ":
                miembros.append({
                    "id_conector": Modelo.ID_ASIGNADO_POR_MATRIZ,
                    "posicion": posicion, "orden": orden})
                continue
            cid_resuelto = id_conector_m
            if cid_resuelto is None and patron_m is not None:
                # miembro de plantilla: resolver el patrón contra los
                # conectores del MISMO equipo que id_conector consultado.
                fila = Modelo._query(
                    "SELECT id_equipo FROM conector WHERE id_conector=?", (id_conector,))
                if fila:
                    eq = fila[0][0]
                    match = Modelo._query(
                        "SELECT id_conector FROM conector WHERE id_equipo=? "
                        "AND UPPER(TRIM(nombre))=?", (eq, (patron_m or "").strip().upper()))
                    if match:
                        cid_resuelto = match[0][0]
            if cid_resuelto is not None:
                miembros.append({
                    "id_conector": str(cid_resuelto), "posicion": posicion, "orden": orden})
        return {"id_estrategia": str(id_estrategia), "modo": modo, "miembros": miembros}

    @staticmethod
    def listar_estrategias_visuales_de_equipo(id_equipo):
        """Lista, para la ficha de equipo, todas las salidas del equipo con
        su estrategia efectiva (propia o heredada) — para mostrar el estado
        actual en la sección 'Señal por conector'."""
        Modelo.asegurar_tablas_imagen_visual()
        salidas = Modelo._query(
            "SELECT c.id_conector, c.nombre FROM conector c "
            "JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE c.id_equipo=? AND UPPER(tc.nombre)='OUT'", (id_equipo,))
        out = []
        for id_conector, nombre in salidas:
            out.append({
                "id_conector": str(id_conector),
                "nombre": nombre,
                "imagen_manual": Modelo.imagen_senal_de_conector(id_conector),
                "estrategia": Modelo.estrategia_visual_efectiva(id_conector),
            })
        return out

    @staticmethod
    def guardar_estrategia_visual(id_estrategia, *, id_conector=None, id_tipo_equipo=None,
                                  patron_conector_salida=None, modo, miembros):
        """Crea o actualiza (si id_estrategia no es None) una estrategia
        completa, reemplazando sus miembros. `miembros`: lista de dicts
        {"tipo":"conector"|"patron", "ref":..., "posicion":..., "orden":...}.
        Exactamente uno de id_conector / id_tipo_equipo debe estar seteado
        (igual convención que guardar_regla_logica)."""
        Modelo.asegurar_tablas_imagen_visual()
        if (id_conector is None) == (id_tipo_equipo is None):
            raise ValueError("guardar_estrategia_visual: exactamente uno de "
                              "id_conector / id_tipo_equipo debe estar seteado")
        if modo not in ("MOSAICO", "OVERLAY", "KEY", "AUDIO_EMBEBIDO"):
            raise ValueError(f"modo de estrategia_visual inválido: {modo!r}")
        with Modelo._conn_ctx() as conn:
            if id_estrategia is None:
                cur = conn.execute(
                    "INSERT INTO estrategia_visual (id_conector, id_tipo_equipo, "
                    " patron_conector_salida, modo, fecha_ultima_edicion) "
                    "VALUES (?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                    (id_conector, id_tipo_equipo, _n(patron_conector_salida), modo))
                id_estrategia = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE estrategia_visual SET modo=?, patron_conector_salida=?, "
                    "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                    "WHERE id_estrategia=?",
                    (modo, _n(patron_conector_salida), id_estrategia))
                conn.execute(
                    "DELETE FROM estrategia_visual_miembro WHERE id_estrategia=?",
                    (id_estrategia,))
            for m in miembros:
                if m["tipo"] == "conector":
                    conn.execute(
                        "INSERT INTO estrategia_visual_miembro "
                        "(id_estrategia, id_conector, posicion, orden) VALUES (?,?,?,?)",
                        (id_estrategia, m["ref"], m["posicion"], m.get("orden", 0)))
                elif m["tipo"] == "matriz":
                    # Rol dinámico "<ASIGNADO POR MATRIZ>": sin id_conector
                    # ni patron_conector — se resuelve en cada composición
                    # contra matriz_ruteo del propio conector de salida
                    # (ver senal_visual.py::_entrada_por_matriz).
                    conn.execute(
                        "INSERT INTO estrategia_visual_miembro "
                        "(id_estrategia, posicion, orden, origen) VALUES (?,?,?,'MATRIZ')",
                        (id_estrategia, m["posicion"], m.get("orden", 0)))
                else:  # patron (miembro de plantilla)
                    conn.execute(
                        "INSERT INTO estrategia_visual_miembro "
                        "(id_estrategia, patron_conector, posicion, orden) VALUES (?,?,?,?)",
                        (id_estrategia, m["ref"], m["posicion"], m.get("orden", 0)))
        return str(id_estrategia)

    @staticmethod
    def eliminar_estrategia_visual(id_estrategia):
        Modelo.asegurar_tablas_imagen_visual()
        Modelo._exec(
            "DELETE FROM estrategia_visual WHERE id_estrategia=?", (id_estrategia,))

    @staticmethod
    def devolver_fecha_ultima_edicion(tabla, pk_col, pk_val):
        """Retorna fecha_ultima_edicion para un registro. Maneja variante con E mayuscula."""
        rows = Modelo._query(f"PRAGMA table_info({tabla})")
        col_fecha = None
        for r in rows:
            if r[1].lower() == "fecha_ultima_edicion":
                col_fecha = r[1]
                break
        if not col_fecha:
            return ""
        result = Modelo._query(
            f"SELECT {col_fecha} FROM {tabla} WHERE {pk_col}=?", (pk_val,)
        )
        return result[0][0] if result and result[0][0] else ""

    # ── Conectores ────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_conectores_de_equipo(id_equipo):
        return Modelo._query(
            "SELECT id_conector, conector_nombre, nombre_tipo_conector "
            "FROM VISTA_CONECTORES WHERE id_equipo=?",
            (id_equipo,),
        )

    @staticmethod
    def devolver_conector(id_conector):
        filas = Modelo._query(
            "SELECT id_conector, conector_nombre, nombre_tipo_conector, "
            "id_tipo_conector, id_equipo, x, y, conector_id_imagen, path_imagen "
            "FROM VISTA_CONECTOR_EDICION WHERE id_conector=?",
            (id_conector,),
        )
        if not filas:
            return filas
        f = list(filas[0])
        # índices: 5=x, 6=y, 8=path_imagen
        x_px, y_px = Modelo._px_punto_o_crudo(f[8] or None, f[5], f[6])
        f[5], f[6] = x_px, y_px
        return [tuple(f)]

    @staticmethod
    def agregar_conector(nombre, id_equipo, id_tipo_conector, id_imagen, x, y,
                         id_funcion_patchera=None):
        Modelo.asegurar_columnas_control_idioma()
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "INSERT INTO conector (nombre, id_equipo, id_tipo_conector, "
            "id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen, "
            "id_funcion_patchera) "
            "VALUES (?,?,?,?,?,?,?)",
            (_n(nombre), _n(id_equipo), _n(id_tipo_conector),
             _n(id_imagen), x_pct, y_pct, _n(id_funcion_patchera)),
        )

    @staticmethod
    def agregar_conector_retorna_id(nombre, id_equipo, id_tipo_conector,
                                    id_imagen, x, y, id_funcion_patchera=None):
        """Igual que agregar_conector pero retorna el id del registro
        creado (mismo patrón que alta_equipo_retorna_id) — usado por el
        alta rápida de extremo FANTASMA, que necesita el id_conector
        recién creado para armar la conexión en el mismo paso."""
        Modelo.asegurar_columnas_control_idioma()
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO conector (nombre, id_equipo, id_tipo_conector, "
                "id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen, "
                "id_funcion_patchera) "
                "VALUES (?,?,?,?,?,?,?)",
                (_n(nombre), _n(id_equipo), _n(id_tipo_conector),
                 _n(id_imagen), x_pct, y_pct, _n(id_funcion_patchera)),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def devolver_id_tipo_conector_por_nombre(nombre):
        """id_tipo_conector cuyo nombre coincide EXACTO (ej. 'IN'/'OUT'),
        o None si no existe. Búsqueda por nombre literal a propósito (no
        por tipo_conector.direccion, que en la migración de hardcodes se
        pobló con un criterio laxo — '%OUT%' en el nombre — y hoy agrupa
        de más bajo 'IN' a varios tipos que no lo son)."""
        rows = Modelo._query(
            "SELECT id_tipo_conector FROM tipo_conector WHERE nombre=? LIMIT 1",
            (nombre,))
        return rows[0][0] if rows else None

    @staticmethod
    def modificacion_conector(id_conector, nombre, id_equipo,
                               id_tipo_conector, id_imagen, x, y):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "UPDATE conector SET nombre=?, id_equipo=?, id_tipo_conector=?, "
            "id_imagen=?, coordenada_x_en_imagen=?, coordenada_y_en_imagen=? "
            "WHERE id_conector=?",
            (_n(nombre), _n(id_equipo), _n(id_tipo_conector),
             _n(id_imagen), x_pct, y_pct, id_conector),
        )

    @staticmethod
    def eliminar_conector(id_conector):
        Modelo._exec("DELETE FROM conector WHERE id_conector=?", (id_conector,))

    # ── Tipos de conector ─────────────────────────────────────────────────────
    @staticmethod
    def devolver_tipos_conectores():
        return Modelo._query(
            "SELECT id_tipo_conector, nombre FROM tipo_conector ORDER BY nombre"
        )

    @staticmethod
    def devolver_tipo_conector(id_tipo_conector):
        return Modelo._query(
            "SELECT id_tipo_conector, nombre FROM tipo_conector "
            "WHERE id_tipo_conector=?",
            (id_tipo_conector,),
        )

    @staticmethod
    def agregar_tipo_conector(nombre):
        Modelo._exec(
            "INSERT INTO tipo_conector (nombre) VALUES (?)", (_n(nombre),)
        )

    @staticmethod
    def modificar_tipo_conector(id_tipo_conector, nombre):
        Modelo._exec(
            "UPDATE tipo_conector SET nombre=? WHERE id_tipo_conector=?",
            (_n(nombre), id_tipo_conector),
        )

    @staticmethod
    def eliminar_tipo_conector(id_tipo_conector):
        Modelo._exec(
            "DELETE FROM tipo_conector WHERE id_tipo_conector=?",
            (id_tipo_conector,),
        )

    # ── Frames ────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_frames():
        return Modelo._query(
            "SELECT id, nombre, marca, modelo, id_marca, "
            "imagen_path, id_imagen, inventario FROM VISTA_FRAMES"
        )

    @staticmethod
    def devolver_frame(id_frame):
        return Modelo._query(
            "SELECT id, nombre, marca, modelo, id_marca, "
            "imagen_path, id_imagen, inventario FROM VISTA_FRAMES WHERE id=?",
            (id_frame,),
        )

    @staticmethod
    def agregar_frame(nombre, num_inventario, id_marca, id_imagen, modelo):
        Modelo._exec(
            "INSERT INTO frame (nombre, num_inventario, id_marca, id_imagen, modelo) "
            "VALUES (?,?,?,?,?)",
            (_n(nombre), _n(num_inventario), _n(id_marca),
             _n(id_imagen), _n(modelo)),
        )

    @staticmethod
    def modificar_frame(id_frame, nombre, num_inventario, id_marca,
                        id_imagen, modelo):
        Modelo._exec(
            "UPDATE frame SET nombre=?, num_inventario=?, id_marca=?, "
            "id_imagen=?, modelo=? WHERE id_frame=?",
            (_n(nombre), _n(num_inventario), _n(id_marca),
             _n(id_imagen), _n(modelo), id_frame),
        )

    @staticmethod
    def eliminar_frame(id_frame):
        Modelo._exec("DELETE FROM frame WHERE id_frame=?", (id_frame,))

    # ── Slots ─────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_slots_del_frame(id_frame):
        return Modelo._query(
            "SELECT id, nombre, nombre_equipo FROM VISTA_SLOTS WHERE id_frame=?",
            (id_frame,),
        )

    @staticmethod
    def devolver_slot(id_slot):
        filas = Modelo._query(
            "SELECT id_slot, slot_nombre, id_equipo, nombre_equipo, "
            "path_imagen, id_imagen, x, y, alto, ancho, id_frame "
            "FROM VISTA_SLOT_EDICION WHERE id_slot=?",
            (id_slot,),
        )
        if not filas:
            return filas
        f = list(filas[0])
        # índices: 4=path_imagen, 6=x, 7=y, 8=alto, 9=ancho
        x, y, ancho, alto = Modelo._px_rect_o_crudo(
            f[4] or None, f[6], f[7], f[9], f[8])
        f[6], f[7], f[8], f[9] = x, y, alto, ancho
        return [tuple(f)]

    @staticmethod
    def agregar_slot(nombre, id_equipo, id_frame, id_imagen, x, y, ancho, alto):
        x_pct, y_pct, w_pct, h_pct = Modelo._pct_rect_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y), _n(ancho), _n(alto))
        Modelo._exec(
            "INSERT INTO slot (nombre, id_equipo, id_frame, id_imagen, "
            "rectangulo_x_en_imagen, rectangulo_y_en_imagen, "
            "rectangulo_ancho_pixeles, rectangulo_alto_pixeles) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (_n(nombre), _n(id_equipo), _n(id_frame), _n(id_imagen),
             x_pct, y_pct, w_pct, h_pct),
        )

    @staticmethod
    def agregar_slot_retorna_id(nombre, id_equipo, id_frame, id_imagen,
                                x, y, ancho, alto):
        x_pct, y_pct, w_pct, h_pct = Modelo._pct_rect_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y), _n(ancho), _n(alto))
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO slot (nombre, id_equipo, id_frame, id_imagen, "
                "rectangulo_x_en_imagen, rectangulo_y_en_imagen, "
                "rectangulo_ancho_pixeles, rectangulo_alto_pixeles) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_n(nombre), _n(id_equipo), _n(id_frame), _n(id_imagen),
                 x_pct, y_pct, w_pct, h_pct),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def modificar_slot(id_slot, nombre, id_equipo, id_frame, id_imagen,
                       x, y, ancho, alto):
        x_pct, y_pct, w_pct, h_pct = Modelo._pct_rect_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y), _n(ancho), _n(alto))
        Modelo._exec(
            "UPDATE slot SET nombre=?, id_equipo=?, id_frame=?, id_imagen=?, "
            "rectangulo_x_en_imagen=?, rectangulo_y_en_imagen=?, "
            "rectangulo_ancho_pixeles=?, rectangulo_alto_pixeles=? "
            "WHERE id_slot=?",
            (_n(nombre), _n(id_equipo), _n(id_frame), _n(id_imagen),
             x_pct, y_pct, w_pct, h_pct, id_slot),
        )

    @staticmethod
    def eliminar_slot(id_slot):
        Modelo._exec("DELETE FROM slot WHERE id_slot=?", (id_slot,))

    # ── Cables ────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_cables():
        return Modelo._query(
            "SELECT c.id_cable, c.codigo, c.longitud, "
            "COALESCE(c.estado, 'VERIFICADO') AS estado, "
            "COUNT(cx.id_conexion) AS n_conexiones "
            "FROM cable c "
            "LEFT JOIN conexion cx ON cx.id_cable = c.id_cable "
            "WHERE c.es_cable_conexion_interna = 0 "
            "GROUP BY c.id_cable "
            "ORDER BY c.codigo"
        )

    @staticmethod
    def devolver_pendientes_cables():
        """Retorna estadísticas de cables incompletos para el panel de pendientes."""
        temporales = Modelo._query(
            "SELECT COUNT(*) FROM cable WHERE estado='TEMPORAL' "
            "AND es_cable_conexion_interna=0"
        )[0][0]
        en_revision = Modelo._query(
            "SELECT COUNT(*) FROM cable WHERE estado='EN_REVISION' "
            "AND es_cable_conexion_interna=0"
        )[0][0]
        un_extremo = Modelo._query(
            "SELECT COUNT(*) FROM ("
            "  SELECT id_cable FROM conexion "
            "  WHERE id_cable IN (SELECT id_cable FROM cable WHERE es_cable_conexion_interna=0) "
            "  GROUP BY id_cable HAVING COUNT(*)=1"
            ")"
        )[0][0]
        sin_conexion = Modelo._query(
            "SELECT COUNT(*) FROM cable c "
            "WHERE es_cable_conexion_interna=0 "
            "AND NOT EXISTS (SELECT 1 FROM conexion cx WHERE cx.id_cable=c.id_cable)"
        )[0][0]
        return {
            "temporales": temporales,
            "en_revision": en_revision,
            "un_extremo": un_extremo,
            "sin_conexion": sin_conexion,
        }

    @staticmethod
    def devolver_pendientes_equipos():
        """Estadísticas de equipos con datos incompletos."""
        sin_conectores = Modelo._query(
            "SELECT COUNT(*) FROM equipo WHERE id_equipo != 0 "
            "AND NOT EXISTS (SELECT 1 FROM conector WHERE id_equipo=equipo.id_equipo)"
        )[0][0]
        sin_imagen = Modelo._query(
            "SELECT COUNT(*) FROM equipo WHERE id_equipo != 0 AND id_imagen IS NULL"
        )[0][0]
        sin_img_conectores = Modelo._query(
            "SELECT COUNT(*) FROM equipo e WHERE id_equipo != 0 "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM conector c "
            "  WHERE c.id_equipo=e.id_equipo AND c.id_imagen IS NOT NULL"
            ")"
        )[0][0]
        return {
            "sin_conectores":    sin_conectores,
            "sin_imagen":        sin_imagen,
            "sin_img_conectores": sin_img_conectores,
        }

    @staticmethod
    def devolver_pendientes_frames():
        """Estadísticas de frames con datos incompletos."""
        sin_slots = Modelo._query(
            "SELECT COUNT(*) FROM frame WHERE "
            "NOT EXISTS (SELECT 1 FROM slot WHERE id_frame=frame.id_frame)"
        )[0][0]
        sin_imagen = Modelo._query(
            "SELECT COUNT(*) FROM frame WHERE id_imagen IS NULL"
        )[0][0]
        sin_rect = Modelo._query(
            "SELECT COUNT(*) FROM frame f WHERE "
            "EXISTS (SELECT 1 FROM slot WHERE id_frame=f.id_frame) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM slot s WHERE s.id_frame=f.id_frame "
            "  AND s.rectangulo_x_en_imagen IS NOT NULL"
            ")"
        )[0][0]
        return {
            "sin_slots":  sin_slots,
            "sin_imagen": sin_imagen,
            "sin_rect":   sin_rect,
        }

    @staticmethod
    def siguiente_codigo_temporal():
        """Genera el siguiente código SIN ETIQUETA NNNN disponible."""
        import re
        rows = Modelo._query(
            "SELECT codigo FROM cable WHERE codigo LIKE 'SIN ETIQUETA ____'"
        )
        nums = []
        for r in rows:
            m = re.search(r"SIN ETIQUETA (\d{4})", r[0])
            if m:
                nums.append(int(m.group(1)))
        siguiente = max(nums) + 1 if nums else 1
        return f"SIN ETIQUETA {siguiente:04d}"

    @staticmethod
    def fusionar_cables(id_cable_principal, id_cable_secundario,
                        codigo_definitivo, estado_final):
        """
        Fusiona dos cables: mueve las conexiones del secundario al principal,
        renombra el principal con el código definitivo y marca el secundario
        como fusionado.
        """
        # Mover conexiones del secundario al principal
        Modelo._exec(
            "UPDATE conexion SET id_cable=? WHERE id_cable=?",
            (id_cable_principal, id_cable_secundario)
        )
        # Actualizar el principal con código y estado definitivos
        Modelo._exec(
            "UPDATE cable SET codigo=?, estado=?, id_cable_fusionado=NULL "
            "WHERE id_cable=?",
            (codigo_definitivo, estado_final, id_cable_principal)
        )
        # Marcar el secundario como fusionado (no se borra, queda como historial)
        Modelo._exec(
            "UPDATE cable SET estado='FUSIONADO', id_cable_fusionado=? "
            "WHERE id_cable=?",
            (id_cable_principal, id_cable_secundario)
        )

    @staticmethod
    def devolver_cable(id_cable):
        return Modelo._query(
            "SELECT c.id_cable, c.codigo, c.id_tipo_cable, tc.nombre, "
            "c.id_tipo_ficha, tf.nombre, c.longitud, c.unidad_longitud, "
            "c.metraje_impreso_primer_extremo, c.unidad_metraje_impreso, "
            "c.metraje_impreso_segundo_extremo, "
            "COALESCE(c.estado,'VERIFICADO'), c.notas_relevamiento "
            "FROM cable c "
            "LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = c.id_tipo_cable "
            "LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = c.id_tipo_ficha "
            "WHERE c.id_cable=?",
            (id_cable,),
        )

    @staticmethod
    def agregar_cable_retorna_id(codigo):
        """Crea un cable con solo el código y retorna su id (para carga rápida)."""
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO cable (codigo, estado) VALUES (?, 'VERIFICADO')",
                (codigo,),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def buscar_cables(texto, limite=30):
        """Busca cables cuyo código contenga 'texto'. Retorna [(id_cable, codigo, estado)]."""
        return Modelo._query(
            "SELECT id_cable, codigo, estado FROM cable "
            "WHERE codigo LIKE ? ORDER BY codigo LIMIT ?",
            (f"%{texto}%", limite),
        )

    @staticmethod
    def conexiones_entre_conectores(id_con_a, id_con_b):
        """Retorna cables que conectan exactamente los dos conectores dados."""
        return Modelo._query(
            "SELECT cn1.id_cable, c.codigo FROM conexion cn1 "
            "JOIN conexion cn2 ON cn2.id_cable=cn1.id_cable "
            "AND cn2.id_conector=? "
            "JOIN cable c ON c.id_cable=cn1.id_cable "
            "WHERE cn1.id_conector=?",
            (id_con_b, id_con_a),
        )

    @staticmethod
    def agregar_cable(codigo, longitud, id_tipo_cable, id_tipo_ficha,
                      unidad_longitud, metraje_ext1, metraje_ext2,
                      unidad_metraje, estado='VERIFICADO',
                      notas_relevamiento=None):
        Modelo._exec(
            "INSERT INTO cable (codigo, longitud, id_tipo_cable, id_tipo_ficha, "
            "unidad_longitud, metraje_impreso_primer_extremo, "
            "metraje_impreso_segundo_extremo, unidad_metraje_impreso, "
            "es_cable_conexion_interna, estado, notas_relevamiento) "
            "VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (_n(codigo), _n(longitud), _n(id_tipo_cable), _n(id_tipo_ficha),
             _n(unidad_longitud), _n(metraje_ext1), _n(metraje_ext2),
             _n(unidad_metraje), estado or 'VERIFICADO',
             _n(notas_relevamiento)),
        )

    @staticmethod
    def modificar_cable(id_cable, codigo, longitud, id_tipo_cable,
                        id_tipo_ficha, unidad_longitud, metraje_ext1,
                        metraje_ext2, unidad_metraje, estado='VERIFICADO',
                        notas_relevamiento=None):
        Modelo._exec(
            "UPDATE cable SET codigo=?, longitud=?, id_tipo_cable=?, "
            "id_tipo_ficha=?, unidad_longitud=?, "
            "metraje_impreso_primer_extremo=?, "
            "metraje_impreso_segundo_extremo=?, "
            "unidad_metraje_impreso=?, estado=?, notas_relevamiento=? "
            "WHERE id_cable=?",
            (_n(codigo), _n(longitud), _n(id_tipo_cable), _n(id_tipo_ficha),
             _n(unidad_longitud), _n(metraje_ext1), _n(metraje_ext2),
             _n(unidad_metraje), estado or 'VERIFICADO',
             _n(notas_relevamiento), id_cable),
        )

    @staticmethod
    def eliminar_cable(id_cable):
        Modelo._exec("DELETE FROM cable WHERE id_cable=?", (id_cable,))

    # ── Override puntual de ancho de banda por cable (plan_riesgo_senal_audio.md) ──
    @staticmethod
    def establecer_ancho_banda_override_cable(id_cable, ancho_banda_mhz):
        Modelo.asegurar_columnas_riesgo_senal()
        Modelo._exec(
            "UPDATE cable SET ancho_banda_mhz_override=? WHERE id_cable=?",
            (ancho_banda_mhz, id_cable))

    @staticmethod
    def devolver_ancho_banda_override_cable(id_cable):
        Modelo.asegurar_columnas_riesgo_senal()
        rows = Modelo._query(
            "SELECT ancho_banda_mhz_override FROM cable WHERE id_cable=?",
            (id_cable,))
        return rows[0][0] if rows else None

    # ── Tipos de cable ────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_tipos_cable():
        return Modelo._query(
            "SELECT id_tipo_cable, nombre FROM tipo_cable ORDER BY nombre"
        )

    @staticmethod
    def devolver_tipo_cable(id_tipo_cable):
        return Modelo._query(
            "SELECT id_tipo_cable, nombre FROM tipo_cable WHERE id_tipo_cable=?",
            (id_tipo_cable,),
        )

    @staticmethod
    def alta_tipo_cable(nombre):
        Modelo._exec("INSERT INTO tipo_cable (nombre) VALUES (?)", (_n(nombre),))

    @staticmethod
    def alta_tipo_cable_retorna_id(nombre):
        with Modelo._conn_ctx() as conn:
            cur = conn.execute("INSERT INTO tipo_cable (nombre) VALUES (?)", (_n(nombre),))
            return cur.lastrowid

    @staticmethod
    def modificacion_tipo_cable(id_tipo_cable, nombre):
        Modelo._exec(
            "UPDATE tipo_cable SET nombre=? WHERE id_tipo_cable=?",
            (_n(nombre), id_tipo_cable),
        )

    @staticmethod
    def eliminar_tipo_cable(id_tipo_cable):
        Modelo._exec(
            "DELETE FROM tipo_cable WHERE id_tipo_cable=?", (id_tipo_cable,)
        )

    # ── Datos de riesgo de señal por tipo de cable (plan_riesgo_senal_audio.md) ──
    @staticmethod
    def devolver_riesgo_tipo_cable(id_tipo_cable):
        """(naturaleza_senal, longitud_maxima_recomendada_balanceado_m,
        longitud_maxima_recomendada_desbalanceado_m, ancho_banda_mhz) o
        None si el tipo no existe."""
        Modelo.asegurar_columnas_riesgo_senal()
        rows = Modelo._query(
            "SELECT naturaleza_senal, longitud_maxima_recomendada_balanceado_m, "
            "longitud_maxima_recomendada_desbalanceado_m, ancho_banda_mhz "
            "FROM tipo_cable WHERE id_tipo_cable=?", (id_tipo_cable,))
        return rows[0] if rows else None

    @staticmethod
    def establecer_riesgo_tipo_cable(id_tipo_cable, naturaleza_senal,
                                      long_max_bal_m, long_max_desbal_m,
                                      ancho_banda_mhz):
        Modelo.asegurar_columnas_riesgo_senal()
        Modelo._exec(
            "UPDATE tipo_cable SET naturaleza_senal=?, "
            "longitud_maxima_recomendada_balanceado_m=?, "
            "longitud_maxima_recomendada_desbalanceado_m=?, "
            "ancho_banda_mhz=? WHERE id_tipo_cable=?",
            (naturaleza_senal or None, long_max_bal_m, long_max_desbal_m,
             ancho_banda_mhz, id_tipo_cable))

    # ── Tipos de ficha ────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_tipos_ficha():
        return Modelo._query(
            "SELECT id_tipo_ficha, nombre FROM tipo_ficha ORDER BY nombre"
        )

    @staticmethod
    def devolver_tipo_ficha(id_tipo_ficha):
        return Modelo._query(
            "SELECT id_tipo_ficha, nombre FROM tipo_ficha WHERE id_tipo_ficha=?",
            (id_tipo_ficha,),
        )

    @staticmethod
    def alta_tipo_ficha(nombre):
        Modelo._exec("INSERT INTO tipo_ficha (nombre) VALUES (?)", (_n(nombre),))

    @staticmethod
    def alta_tipo_ficha_retorna_id(nombre):
        with Modelo._conn_ctx() as conn:
            cur = conn.execute("INSERT INTO tipo_ficha (nombre) VALUES (?)", (_n(nombre),))
            return cur.lastrowid

    @staticmethod
    def modificacion_tipo_ficha(id_tipo_ficha, nombre):
        Modelo._exec(
            "UPDATE tipo_ficha SET nombre=? WHERE id_tipo_ficha=?",
            (_n(nombre), id_tipo_ficha),
        )

    @staticmethod
    def eliminar_tipo_ficha(id_tipo_ficha):
        Modelo._exec(
            "DELETE FROM tipo_ficha WHERE id_tipo_ficha=?", (id_tipo_ficha,)
        )

    # ── Datos de riesgo de señal por tipo de ficha (plan_riesgo_senal_audio.md) ──
    @staticmethod
    def devolver_riesgo_tipo_ficha(id_tipo_ficha):
        """(n_conductores, modo_balance_default, modo_canal_default,
        ancho_banda_mhz) o None si el tipo no existe."""
        Modelo.asegurar_columnas_riesgo_senal()
        rows = Modelo._query(
            "SELECT n_conductores, modo_balance_default, modo_canal_default, "
            "ancho_banda_mhz FROM tipo_ficha WHERE id_tipo_ficha=?",
            (id_tipo_ficha,))
        return rows[0] if rows else None

    @staticmethod
    def establecer_riesgo_tipo_ficha(id_tipo_ficha, n_conductores,
                                      modo_balance_default, modo_canal_default,
                                      ancho_banda_mhz):
        Modelo.asegurar_columnas_riesgo_senal()
        Modelo._exec(
            "UPDATE tipo_ficha SET n_conductores=?, modo_balance_default=?, "
            "modo_canal_default=?, ancho_banda_mhz=? WHERE id_tipo_ficha=?",
            (n_conductores, modo_balance_default or None,
             modo_canal_default or None, ancho_banda_mhz, id_tipo_ficha))

    # ── Formato eléctrico de un conector real (override puntual) ────────────────
    @staticmethod
    def establecer_formato_conector(id_conector, id_tipo_ficha,
                                     modo_balance, modo_canal):
        """id_tipo_ficha: qué ficha es eléctricamente este jack (de ahí sale
        el default de modo_balance/modo_canal/n_conductores). modo_balance/
        modo_canal: override puntual, None = usar el default de la ficha."""
        Modelo.asegurar_columnas_riesgo_senal()
        Modelo._exec(
            "UPDATE conector SET id_tipo_ficha=?, modo_balance=?, modo_canal=? "
            "WHERE id_conector=?",
            (id_tipo_ficha or None, modo_balance or None, modo_canal or None,
             id_conector))

    @staticmethod
    def devolver_formato_conector(id_conector):
        """(id_tipo_ficha, modo_balance, modo_canal) override crudo (sin
        resolver default) de un conector, o None si no existe."""
        Modelo.asegurar_columnas_riesgo_senal()
        rows = Modelo._query(
            "SELECT id_tipo_ficha, modo_balance, modo_canal FROM conector "
            "WHERE id_conector=?", (id_conector,))
        return rows[0] if rows else None

    # ── Conexiones ────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todas_las_conexiones(id_cable=None):
        if id_cable:
            return Modelo._query(
                "SELECT id_conexion, equipo_nombre, conector_nombre, "
                "cable_codigo, tipo_conector, tipo_equipo, "
                "id_cable, id_conector, id_equipo "
                "FROM CONEXIONES WHERE id_cable=? ORDER BY cable_codigo",
                (id_cable,)
            )
        return Modelo._query(
            "SELECT id_conexion, equipo_nombre, conector_nombre, "
            "cable_codigo, tipo_conector, tipo_equipo, "
            "id_cable, id_conector, id_equipo "
            "FROM CONEXIONES ORDER BY cable_codigo"
        )

    @staticmethod
    def devolver_conexion(id_conexion):
        return Modelo._query(
            "SELECT id_conexion, equipo_nombre, conector_nombre, "
            "cable_codigo, tipo_conector, tipo_equipo, "
            "id_cable, id_conector, id_equipo "
            "FROM CONEXIONES WHERE id_conexion=?",
            (id_conexion,),
        )

    @staticmethod
    def devolver_ficha_de_conexion(id_conexion):
        """Nombre del tipo de ficha propio de esta conexion (columna
        conexion.id_tipo_ficha), o None si no está especificado. Usado
        para mostrar algo útil en el listado de Conexiones cuando el
        extremo es suelto (id_conector NULL) y por lo tanto CONEXIONES no
        trae tipo_conector — ver plan_desarrollo_extension_cable.md."""
        rows = Modelo._query(
            "SELECT tf.nombre FROM conexion cx "
            "LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = cx.id_tipo_ficha "
            "WHERE cx.id_conexion=?", (id_conexion,))
        return rows[0][0] if rows and rows[0][0] else None

    @staticmethod
    def devolver_resumen_conexion(id_conexion):
        """(codigo_cable, nombre_ficha) para mostrar en la UI de
        extensiones sin tener que resolver el objeto conexion completo."""
        rows = Modelo._query(
            "SELECT c.codigo, tf.nombre FROM conexion cx "
            "JOIN cable c ON c.id_cable = cx.id_cable "
            "LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = cx.id_tipo_ficha "
            "WHERE cx.id_conexion=?", (id_conexion,))
        return rows[0] if rows else (None, None)

    @staticmethod
    def devolver_cable_de_conexion(id_conexion):
        """id_cable al que pertenece una conexion puntual. Usado por
        'Ver cadena completa' (extension_cable_ui.py) para sembrar la
        resolución de cadena a partir de un extremo ya conocido."""
        rows = Modelo._query(
            "SELECT id_cable FROM conexion WHERE id_conexion=?", (id_conexion,))
        return rows[0][0] if rows else None

    @staticmethod
    def alta_conexion(id_cable, id_conector, es_conexion_interna=0):
        Modelo._exec(
            "INSERT INTO conexion (id_cable, id_conector, es_conexion_interna) "
            "VALUES (?,?,?)",
            (_n(id_cable), _n(id_conector), es_conexion_interna),
        )

    @staticmethod
    def modificacion_conexion(id_conexion, id_cable, id_conector,
                               es_conexion_interna=0):
        Modelo._exec(
            "UPDATE conexion SET id_cable=?, id_conector=?, "
            "es_conexion_interna=? WHERE id_conexion=?",
            (_n(id_cable), _n(id_conector), es_conexion_interna, id_conexion),
        )

    @staticmethod
    def eliminar_conexion(id_conexion):
        Modelo._exec("DELETE FROM conexion WHERE id_conexion=?", (id_conexion,))

    # ── Ficha propia del cable en este punto de conexión (plan_riesgo_senal_audio.md) ──
    @staticmethod
    def establecer_ficha_conexion(id_conexion, id_tipo_ficha):
        """Qué ficha es físicamente el extremo del cable que llega a esta
        conexión puntual (ej. XLR3 macho, TS, etc.) — distinto de
        conector.id_tipo_ficha, que es lo que el JACK del equipo declara
        esperar. None = sin cargar (signal_risk.py cae al chequeo
        anterior, jack contra jack, como fallback)."""
        Modelo.asegurar_columnas_riesgo_senal()
        Modelo._exec(
            "UPDATE conexion SET id_tipo_ficha=? WHERE id_conexion=?",
            (id_tipo_ficha or None, id_conexion))

    @staticmethod
    def devolver_ficha_conexion(id_conexion):
        Modelo.asegurar_columnas_riesgo_senal()
        rows = Modelo._query(
            "SELECT id_tipo_ficha FROM conexion WHERE id_conexion=?",
            (id_conexion,))
        return rows[0][0] if rows else None

    @staticmethod
    def mover_conexion(id_conexion, nuevo_id_conector):
        """Reasigna el conector de una conexión ya existente, reutilizando el
        mismo cable (mismo id_cable) y sin tocar el otro extremo. Se usa para
        'mover' un extremo de un cable ya tendido hacia otro equipo/conector,
        por ejemplo desde el editor de conexiones rápidas."""
        Modelo._exec(
            "UPDATE conexion SET id_conector=? WHERE id_conexion=?",
            (_n(nuevo_id_conector), id_conexion),
        )

    @staticmethod
    def devolver_conexiones_de_equipo(id_equipo):
        """Conexiones de ambos extremos dado un id_equipo."""
        return Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo = ?",
            (id_equipo,),
        )

    @staticmethod
    def devolver_conexiones_de_cable(id_cable):
        """Conexiones de ambos extremos dado un id_cable."""
        return Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_cable = ?",
            (id_cable,),
        )

    @staticmethod
    def devolver_cantidad_conexiones_de_equipo(id_equipo):
        """Cantidad total de filas `conexion` sobre cualquier conector de
        id_equipo, contadas directo contra `conexion`/`conector` — a
        propósito NO pasa por CONEXIONES_AMBOS_EXTREMOS (esa vista exige
        equipo real también del OTRO extremo, así que subcuenta un
        FANTASMA cuyo cable termina en un extremo suelto de
        extension_cable, o cuyo cable quedó incompleto del otro lado).
        Usada por el aviso de huérfano al reconectar en el diagrama
        (plan_desarrollo_fantasma_rapido.md, Parte B — ver
        EdicionConexionesMixin._avisar_si_fantasma_huerfano)."""
        rows = Modelo._query(
            "SELECT COUNT(*) FROM conexion cx "
            "JOIN conector co ON co.id_conector = cx.id_conector "
            "WHERE co.id_equipo=?",
            (id_equipo,),
        )
        return rows[0][0] if rows else 0

    @staticmethod
    def devolver_extremos_de_cable(id_cable):
        """Info cruda (sin pasar por CONEXIONES_AMBOS_EXTREMOS) de las
        conexiones ya cargadas de un cable — una fila por extremo:
        (id_conexion, id_conector, id_tipo_conector, nombre_tipo_conector).
        id_conector/id_tipo_conector/nombre_tipo_conector vienen NULL si es
        un extremo suelto (plan_desarrollo_extension_cable.md, id_conector
        IS NULL). Usada por el alta rápida de extremo FANTASMA para saber
        cuántas puntas tiene ya el cable y, si hay una sola, inferir el
        lado opuesto (ver plan_desarrollo_fantasma_rapido.md)."""
        return Modelo._query(
            "SELECT cx.id_conexion, cx.id_conector, co.id_tipo_conector, "
            "tc.nombre "
            "FROM conexion cx "
            "LEFT JOIN conector co ON co.id_conector = cx.id_conector "
            "LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = co.id_tipo_conector "
            "WHERE cx.id_cable = ?",
            (id_cable,),
        )

    @staticmethod
    def devolver_equipos_conectados_a_equipo(id_equipo):
        return Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo = ?",
            (id_equipo,),
        )

    # ── Patcheras (vista global, sin filtrar por equipo) ────────────────────────
    @staticmethod
    def devolver_slots_patchera_global():
        """Todas las columnas (slots) de equipos con rol_senal='PATCHERA'
        del sistema (Fase 4 de plan_desarrollo_hardcodes_idioma.md — antes
        te.nombre = 'MODULO PATCHERA'), con su ubicación (rack/frame) y el
        id del módulo instalado. Sin filtrar por ningún equipo: es la base
        para la vista global de patcheras."""
        return Modelo._query(
            "SELECT DISTINCT r.id_rack, r.nombre, f.id_frame, f.nombre, "
            "       s.nombre, s.id_equipo "
            "FROM rack r "
            "JOIN posicion_en_rack pr ON pr.id_rack = r.id_rack "
            "JOIN frame f ON f.id_frame = pr.id_frame "
            "JOIN slot s ON s.id_frame = f.id_frame "
            "JOIN equipo e ON e.id_equipo = s.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE te.rol_senal = 'PATCHERA' "
            "ORDER BY r.nombre, f.nombre, s.nombre"
        )

    @staticmethod
    def devolver_conexiones_conectores_patchera_global():
        """Para cada conector con función de patchera asignada (BACK_
        ENTRADA/BACK_SALIDA/FRONT_DERIVACION/FRONT_INSERCION —
        conector.id_funcion_patchera, Fase C de plan_desarrollo_funcion_
        patchera.md, SIN fallback a nombre) de todos los equipos con
        rol_senal='PATCHERA' que tenga un cable conectado, devuelve el
        equipo/conector del otro extremo, junto con su rol_senal (para que
        el caller detecte FANTASMA/PATCHERA sin comparar texto) y la CLAVE
        de función de patchera de ambos extremos (no ya el string de la
        convención vieja). Una sola consulta (sin filtrar por id_equipo)
        para armar la vista global."""
        return Modelo._query(
            "SELECT c1.id_conector, c1.nombre, c1.id_equipo, "
            "       e2.id_equipo, e2.nombre, "
            "       te2.id_tipo_equipo, te2.nombre, "
            "       c2.id_conector, c2.nombre, te2.rol_senal, "
            "       fp1.clave, fp2.clave "
            "FROM conector c1 "
            "JOIN equipo e1 ON e1.id_equipo = c1.id_equipo "
            "JOIN tipo_equipo te1 ON te1.id_tipo_equipo = e1.id_tipo_equipo "
            "JOIN conexion cx1 ON cx1.id_conector = c1.id_conector "
            "JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
            "   AND cx2.id_conector != cx1.id_conector "
            "JOIN conector c2 ON c2.id_conector = cx2.id_conector "
            "JOIN equipo e2 ON e2.id_equipo = c2.id_equipo "
            "JOIN tipo_equipo te2 ON te2.id_tipo_equipo = e2.id_tipo_equipo "
            "LEFT JOIN funcion_patchera fp1 "
            "  ON fp1.id_funcion_patchera = c1.id_funcion_patchera "
            "LEFT JOIN funcion_patchera fp2 "
            "  ON fp2.id_funcion_patchera = c2.id_funcion_patchera "
            "WHERE te1.rol_senal = 'PATCHERA' "
            "AND c1.id_funcion_patchera IS NOT NULL"
        )

    # ── Racks ─────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_los_racks():
        return Modelo._query(
            "SELECT id_rack, numero, nombre, cantidad_maxima FROM rack ORDER BY nombre"
        )

    @staticmethod
    def devolver_rack(id_rack):
        return Modelo._query(
            "SELECT id_rack, numero, nombre, cantidad_maxima FROM rack WHERE id_rack=?",
            (id_rack,),
        )

    @staticmethod
    def alta_rack(numero, nombre, cantidad_maxima):
        Modelo._exec(
            "INSERT INTO rack (numero, nombre, cantidad_maxima) VALUES (?,?,?)",
            (_n(numero), _n(nombre), _n(cantidad_maxima)),
        )

    @staticmethod
    def modificacion_rack(id_rack, numero, nombre, cantidad_maxima):
        Modelo._exec(
            "UPDATE rack SET numero=?, nombre=?, cantidad_maxima=? WHERE id_rack=?",
            (_n(numero), _n(nombre), _n(cantidad_maxima), id_rack),
        )

    @staticmethod
    def eliminar_rack(id_rack):
        Modelo._exec("DELETE FROM rack WHERE id_rack=?", (id_rack,))

    # ── Posiciones en rack ────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_dispositivos_en_racks():
        return Modelo._query(
            "SELECT id, rack, orificio, inventario, dispositivo, UR, "
            "id_rack, id_equipo, id_frame FROM 'RACKS CON EQUIPOS'"
        )

    @staticmethod
    def devolver_dispositivos_de_un_rack(id_rack):
        return Modelo._query(
            "SELECT id, rack, orificio, inventario, dispositivo, UR, "
            "id_rack, id_equipo, id_frame "
            "FROM 'RACKS CON EQUIPOS' WHERE id_rack=?",
            (id_rack,),
        )

    @staticmethod
    def devolver_dispositivo_en_rack(id_posicion):
        return Modelo._query(
            "SELECT id, rack, orificio, inventario, dispositivo, UR, "
            "id_rack, id_equipo, id_frame "
            "FROM 'RACKS CON EQUIPOS' WHERE id=?",
            (id_posicion,),
        )

    @staticmethod
    def alta_dispositivo_en_rack(id_rack, id_equipo, orificio, ur, id_frame):
        Modelo._exec(
            "INSERT INTO posicion_en_rack (id_rack, id_equipo, "
            "orificio_posicion_equipo_en_rack, unidades_de_rack_equipo, id_frame) "
            "VALUES (?,?,?,?,?)",
            (_n(id_rack), _n(id_equipo), _n(orificio), _n(ur), _n(id_frame)),
        )

    @staticmethod
    def modificacion_dispositivo_en_rack(id_posicion, id_rack, id_equipo,
                                          orificio, ur, id_frame):
        Modelo._exec(
            "UPDATE posicion_en_rack SET id_rack=?, id_equipo=?, "
            "orificio_posicion_equipo_en_rack=?, unidades_de_rack_equipo=?, "
            "id_frame=? WHERE id_posicion_en_rack=?",
            (_n(id_rack), _n(id_equipo), _n(orificio), _n(ur),
             _n(id_frame), id_posicion),
        )

    @staticmethod
    def eliminar_dispositivo_en_rack(id_posicion):
        Modelo._exec(
            "DELETE FROM posicion_en_rack WHERE id_posicion_en_rack=?",
            (id_posicion,),
        )

    @staticmethod
    def devolver_rack_de_equipo(id_equipo):
        """Devuelve [(id_rack, nombre_rack)] donde está montado el equipo
        dado, contemplando dos casos:
          1) el equipo está posicionado directamente en un rack
             (posicion_en_rack.id_equipo = id_equipo, sin frame), o
          2) el equipo está dentro de un slot de un frame, y ese frame
             está posicionado en un rack.
        Lista vacía si el equipo no está rackeado (ni directo ni vía frame).
        """
        rows = Modelo._query(
            "SELECT r.id_rack, r.nombre "
            "FROM posicion_en_rack pr "
            "JOIN rack r ON r.id_rack = pr.id_rack "
            "WHERE pr.id_equipo = ? AND pr.id_frame IS NULL",
            (id_equipo,),
        )
        if rows:
            return rows
        return Modelo._query(
            "SELECT r.id_rack, r.nombre "
            "FROM slot s "
            "JOIN posicion_en_rack pr ON pr.id_frame = s.id_frame "
            "AND pr.id_equipo IS NULL "
            "JOIN rack r ON r.id_rack = pr.id_rack "
            "WHERE s.id_equipo = ?",
            (id_equipo,),
        )

    @staticmethod
    def devolver_rack_de_frame(id_frame):
        """Devuelve [(id_rack, nombre_rack)] donde está montado el frame
        dado (posicion_en_rack.id_frame = id_frame). Lista vacía si el
        frame no está rackeado."""
        return Modelo._query(
            "SELECT r.id_rack, r.nombre "
            "FROM posicion_en_rack pr "
            "JOIN rack r ON r.id_rack = pr.id_rack "
            "WHERE pr.id_frame = ?",
            (id_frame,),
        )



    @staticmethod
    def devolver_slots_graficos_de_frame(id_frame):
        """
        Retorna todos los slots de un frame con sus equipos asignados
        y coordenadas del rectángulo en la imagen del FRAME.
        Cols: id_slot, slot_nombre, id_equipo, eq_nombre,
              rect_x, rect_y, rect_ancho, rect_alto, img_frame_path
        """
        filas = Modelo._query(
            "SELECT s.id_slot, s.nombre, s.id_equipo, "
            "COALESCE(e.nombre, '') AS eq_nombre, "
            "COALESCE(s.rectangulo_x_en_imagen, 0) AS x, "
            "COALESCE(s.rectangulo_y_en_imagen, 0) AS y, "
            "COALESCE(s.rectangulo_ancho_pixeles, 50) AS ancho, "
            "COALESCE(s.rectangulo_alto_pixeles, 30) AS alto, "
            "COALESCE(img_f.path_archivo, '') AS img_frame, "
            "COALESCE(img_s.path_archivo, '') AS img_slot "
            "FROM slot s "
            "LEFT JOIN equipo e ON e.id_equipo = s.id_equipo "
            "LEFT JOIN frame f ON f.id_frame = s.id_frame "
            "LEFT JOIN imagen img_f ON img_f.id_imagen = f.id_imagen "
            "LEFT JOIN imagen img_s ON img_s.id_imagen = s.id_imagen "
            "WHERE s.id_frame = ? "
            "ORDER BY s.nombre",
            (id_frame,)
        )
        resultado = []
        for fila in filas:
            f = list(fila)
            # la % está calculada sobre la imagen propia del slot
            # (s.id_imagen, columna img_slot=9) — misma imagen que usan
            # agregar_slot/modificar_slot para convertir; si el slot no
            # tiene imagen propia, se usa la del frame como mejor esfuerzo.
            path_archivo = f[9] or f[8] or None
            x, y, ancho, alto = Modelo._px_rect_o_crudo(
                path_archivo, f[4], f[5], f[6], f[7])
            f[4], f[5], f[6], f[7] = x, y, ancho, alto
            resultado.append(tuple(f[:9]))  # se descarta img_slot (col 9), no formaba parte del contrato original
        return resultado

    # ── Salas ─────────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todas_las_salas():
        return Modelo._query("SELECT id_sala, nombre FROM sala ORDER BY nombre")

    @staticmethod
    def devolver_sala(id_sala):
        return Modelo._query("SELECT id_sala, nombre FROM sala WHERE id_sala=?", (id_sala,))

    @staticmethod
    def alta_sala(nombre):
        Modelo._exec("INSERT INTO sala (nombre) VALUES (?)", (_n(nombre),))

    @staticmethod
    def modificacion_sala(id_sala, nombre):
        Modelo._exec("UPDATE sala SET nombre=? WHERE id_sala=?", (_n(nombre), id_sala))

    @staticmethod
    def eliminar_sala(id_sala):
        Modelo._exec("DELETE FROM sala WHERE id_sala=?", (id_sala,))

    # ── Rack por sala ─────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todos_rack_por_sala():
        return Modelo._query(
            "SELECT rps.id_rack_x_sala, s.nombre, r.nombre "
            "FROM rack_por_sala rps "
            "JOIN sala s ON s.id_sala=rps.id_sala "
            "JOIN rack r ON r.id_rack=rps.id_rack "
            "ORDER BY s.nombre, r.nombre"
        )

    @staticmethod
    def devolver_rack_por_sala(id_):
        return Modelo._query(
            "SELECT rps.id_rack_x_sala, rps.id_sala, rps.id_rack, s.nombre, r.nombre "
            "FROM rack_por_sala rps "
            "JOIN sala s ON s.id_sala=rps.id_sala "
            "JOIN rack r ON r.id_rack=rps.id_rack "
            "WHERE rps.id_rack_x_sala=?", (id_,)
        )

    @staticmethod
    def alta_rack_por_sala(id_sala, id_rack):
        Modelo._exec(
            "INSERT INTO rack_por_sala (id_sala, id_rack) VALUES (?,?)",
            (id_sala, id_rack),
        )

    @staticmethod
    def modificacion_rack_por_sala(id_, id_sala, id_rack):
        Modelo._exec(
            "UPDATE rack_por_sala SET id_sala=?, id_rack=? WHERE id_rack_x_sala=?",
            (id_sala, id_rack, id_),
        )

    @staticmethod
    def eliminar_rack_por_sala(id_):
        Modelo._exec("DELETE FROM rack_por_sala WHERE id_rack_x_sala=?", (id_,))

    # ── Equipos no racqueables por sala ──────────────────────────────────────
    @staticmethod
    def devolver_todos_equipos_no_rack_sala():
        return Modelo._query(
            "SELECT en.id_equiponoraqueable_por_sala, s.nombre, e.nombre "
            "FROM equiponoraqueable_por_sala en "
            "JOIN sala s ON s.id_sala = en.id_sala "
            "JOIN equipo e ON e.id_equipo = en.id_equipo "
            "ORDER BY s.nombre, e.nombre"
        )

    @staticmethod
    def devolver_equipo_no_rack_sala(id_):
        return Modelo._query(
            "SELECT en.id_equiponoraqueable_por_sala, en.id_sala, en.id_equipo, "
            "s.nombre, e.nombre "
            "FROM equiponoraqueable_por_sala en "
            "JOIN sala s ON s.id_sala = en.id_sala "
            "JOIN equipo e ON e.id_equipo = en.id_equipo "
            "WHERE en.id_equiponoraqueable_por_sala=?", (id_,)
        )

    @staticmethod
    def devolver_equipos_no_rack_de_sala(id_sala):
        """Retorna equipos sueltos de una sala (id_equipo, nombre, tipo)."""
        return Modelo._query(
            "SELECT e.id_equipo, e.nombre, COALESCE(te.nombre,'') "
            "FROM equiponoraqueable_por_sala en "
            "JOIN equipo e ON e.id_equipo = en.id_equipo "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE en.id_sala = ? "
            "ORDER BY e.nombre",
            (id_sala,)
        )

    @staticmethod
    def alta_equipo_no_rack_sala(id_sala, id_equipo):
        # Usar INSERT OR REPLACE para actualizar si ya existe
        Modelo._exec(
            "INSERT OR REPLACE INTO equiponoraqueable_por_sala (id_sala, id_equipo) VALUES (?,?)",
            (id_sala, id_equipo),
        )

    @staticmethod
    def modificacion_equipo_no_rack_sala(id_, id_sala, id_equipo):
        Modelo._exec(
            "UPDATE equiponoraqueable_por_sala SET id_sala=?, id_equipo=? "
            "WHERE id_equiponoraqueable_por_sala=?",
            (id_sala, id_equipo, id_),
        )

    @staticmethod
    def eliminar_equipo_no_rack_sala(id_):
        Modelo._exec(
            "DELETE FROM equiponoraqueable_por_sala "
            "WHERE id_equiponoraqueable_por_sala=?", (id_,)
        )

    # ── Patcheras ─────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_equipos_patchera():
        """Todos los equipos cuyo tipo tiene rol_senal='PATCHERA' (antes
        comparaba te.nombre = 'MODULO PATCHERA' — ver Fase 4 de
        plan_desarrollo_hardcodes_idioma.md)."""
        return Modelo._query(
            "SELECT e.id_equipo, e.nombre FROM equipo e "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE te.rol_senal = 'PATCHERA' ORDER BY e.nombre"
        )

    @staticmethod
    def devolver_patcheras_con_estado(id_equipo_seleccionado):
        """
        Para todos los conectores de MODULO PATCHERA devuelve:
        id_conector, nombre_conector, id_equipo, estado
        estado ∈ {'seleccionado', 'ocupado', 'libre'}
        """
        return Modelo._query(
            "SELECT c.id_conector, c.nombre, c.id_equipo, "
            "CASE "
            "  WHEN EXISTS ("
            "    SELECT 1 FROM conexion cx1 "
            "    JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
            "    JOIN conector c2 ON cx2.id_conector = c2.id_conector "
            "    WHERE cx1.id_conector = c.id_conector "
            "    AND c2.id_equipo = ? "
            "  ) THEN 'seleccionado' "
            "  WHEN EXISTS ("
            "    SELECT 1 FROM conexion cx WHERE cx.id_conector = c.id_conector"
            "  ) THEN 'ocupado' "
            "  ELSE 'libre' "
            "END AS estado "
            "FROM conector c "
            "JOIN equipo e ON e.id_equipo = c.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE te.rol_senal = 'PATCHERA'",
            (id_equipo_seleccionado,)
        )


    @staticmethod
    def guardar_posicion_en_diagrama(id_equipo, x, y):
        """INSERT or UPDATE position in diagrama_equipos_posicion_en_imagen."""
        existing = Modelo.devolver_posicion_en_diagrama(id_equipo)
        if existing:
            Modelo._exec(
                "UPDATE diagrama_equipos_posicion_en_imagen "
                "SET x=?, y=? WHERE id_equipo=?",
                (int(x), int(y), id_equipo),
            )
        else:
            Modelo._exec(
                "INSERT INTO diagrama_equipos_posicion_en_imagen "
                "(id_equipo, x, y) VALUES (?, ?, ?)",
                (id_equipo, int(x), int(y)),
            )

    # ── Diagrama Graphviz ─────────────────────────────────────────────────────
    @staticmethod
    def devolver_posicion_en_diagrama(id_equipo):
        return Modelo._query(
            "SELECT id_diagrama_posicion, id_equipo, x, y, "
            "fecha_ultima_edicion, color_equipo, id_conexion, color_conexion "
            "FROM diagrama_equipos_posicion_en_imagen WHERE id_equipo=?",
            (id_equipo,),
        )

    # ── Problemas de equipos ─────────────────────────────────────────────────
    @staticmethod
    def asegurar_tablas_problemas():
        """Crea categoria_problema y problema_equipo si no existen.
        problema_equipo: id_problema (PK autonumérico), id_categoria (FK a
        categoria_problema, puede ser NULL), id_equipo (FK a equipo, NOT
        NULL), gravedad (INTEGER NOT NULL), descripcion (TEXT), fecha (TEXT,
        fecha del problema en sí, distinta de fecha_ultima_edicion que es
        la fecha de la última edición del registro)."""
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS categoria_problema ("
            "  id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre       TEXT,"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS problema_equipo ("
            "  id_problema  INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_categoria INTEGER,"
            "  id_equipo    INTEGER NOT NULL,"
            "  gravedad     INTEGER NOT NULL,"
            "  descripcion  TEXT,"
            "  fecha        TEXT,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_categoria) REFERENCES categoria_problema(id_categoria) ON DELETE SET NULL,"
            "  FOREIGN KEY(id_equipo)    REFERENCES equipo(id_equipo)                ON DELETE CASCADE"
            ")"
        )
        # Migración: asegurar que exista la columna fecha en problema_equipo
        # (instalaciones existentes que ya tenían la tabla sin esta columna)
        with Modelo._conn_ctx() as conn:
            cursor = conn.execute("PRAGMA table_info(problema_equipo)")
            columnas = [col[1] for col in cursor.fetchall()]
            if "fecha" not in columnas:
                conn.execute("ALTER TABLE problema_equipo ADD COLUMN fecha TEXT")
            conn.commit()

    # ── Categorías de problema (catálogo) ────────────────────────────────────
    @staticmethod
    def devolver_todas_las_categorias_problema():
        Modelo.asegurar_tablas_problemas()
        return Modelo._query(
            "SELECT id_categoria, nombre FROM categoria_problema ORDER BY nombre"
        )

    @staticmethod
    def devolver_categoria_problema(id_categoria):
        Modelo.asegurar_tablas_problemas()
        return Modelo._query(
            "SELECT id_categoria, nombre FROM categoria_problema WHERE id_categoria=?",
            (id_categoria,),
        )

    @staticmethod
    def alta_categoria_problema(nombre):
        Modelo.asegurar_tablas_problemas()
        Modelo._exec(
            "INSERT INTO categoria_problema (nombre, fecha_ultima_edicion) "
            "VALUES (?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
            (_n(nombre),),
        )

    @staticmethod
    def modificacion_categoria_problema(id_categoria, nombre):
        Modelo.asegurar_tablas_problemas()
        Modelo._exec(
            "UPDATE categoria_problema SET nombre=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_categoria=?",
            (_n(nombre), id_categoria),
        )

    @staticmethod
    def eliminar_categoria_problema(id_categoria):
        Modelo.asegurar_tablas_problemas()
        Modelo._exec(
            "DELETE FROM categoria_problema WHERE id_categoria=?", (id_categoria,)
        )

    # ── Problemas de un equipo ────────────────────────────────────────────────
    @staticmethod
    def devolver_problemas_de_equipo(id_equipo):
        """Lista los problemas cargados para un equipo.
        Cols: id_problema, fecha, categoria, gravedad, descripcion, resuelto"""
        Modelo.asegurar_tablas_riesgo()
        return Modelo._query(
            "SELECT pe.id_problema, COALESCE(pe.fecha,''), COALESCE(cp.nombre,''), pe.gravedad, "
            "COALESCE(pe.descripcion,''), COALESCE(pe.resuelto,0) "
            "FROM problema_equipo pe "
            "LEFT JOIN categoria_problema cp ON cp.id_categoria = pe.id_categoria "
            "WHERE pe.id_equipo=? "
            "ORDER BY pe.gravedad DESC, pe.id_problema DESC",
            (id_equipo,),
        )

    @staticmethod
    def devolver_problema(id_problema):
        Modelo.asegurar_tablas_riesgo()
        return Modelo._query(
            "SELECT pe.id_problema, pe.id_categoria, COALESCE(cp.nombre,''), "
            "pe.id_equipo, pe.gravedad, pe.descripcion, pe.fecha, "
            "COALESCE(pe.afecta_categoria_equipo,0), COALESCE(pe.resuelto,0), "
            "pe.fecha_resolucion "
            "FROM problema_equipo pe "
            "LEFT JOIN categoria_problema cp ON cp.id_categoria = pe.id_categoria "
            "WHERE pe.id_problema=?",
            (id_problema,),
        )

    @staticmethod
    def devolver_cantidad_problemas_de_equipo(id_equipo):
        Modelo.asegurar_tablas_problemas()
        r = Modelo._query(
            "SELECT COUNT(*) FROM problema_equipo WHERE id_equipo=?", (id_equipo,)
        )
        return r[0][0] if r else 0

    @staticmethod
    def devolver_problemas_para_riesgo():
        """Todos los problemas de todos los equipos, con lo que necesita el
        motor de riesgo (risk_engine.py): id_equipo, gravedad, fecha,
        afecta_categoria_equipo, resuelto. Una sola consulta para todo el
        parque, en vez de una por equipo."""
        Modelo.asegurar_tablas_riesgo()
        return Modelo._query(
            "SELECT id_equipo, gravedad, fecha, "
            "COALESCE(afecta_categoria_equipo,0), COALESCE(resuelto,0) "
            "FROM problema_equipo"
        )

    @staticmethod
    def agregar_problema(id_categoria, id_equipo, gravedad, descripcion=None, fecha=None,
                         afecta_categoria_equipo=0, resuelto=0, fecha_resolucion=None):
        Modelo.asegurar_tablas_riesgo()
        Modelo._exec(
            "INSERT INTO problema_equipo "
            "(id_categoria, id_equipo, gravedad, descripcion, fecha, "
            " afecta_categoria_equipo, resuelto, fecha_resolucion, fecha_ultima_edicion) "
            "VALUES (?,?,?,?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
            (_n(id_categoria), id_equipo, gravedad, _n(descripcion), _n(fecha),
             1 if afecta_categoria_equipo else 0, 1 if resuelto else 0,
             _n(fecha_resolucion)),
        )

    @staticmethod
    def modificacion_problema(id_problema, id_categoria, id_equipo, gravedad,
                              descripcion=None, fecha=None,
                              afecta_categoria_equipo=0, resuelto=0, fecha_resolucion=None):
        Modelo.asegurar_tablas_riesgo()
        Modelo._exec(
            "UPDATE problema_equipo SET id_categoria=?, id_equipo=?, "
            "gravedad=?, descripcion=?, fecha=?, "
            "afecta_categoria_equipo=?, resuelto=?, fecha_resolucion=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_problema=?",
            (_n(id_categoria), id_equipo, gravedad, _n(descripcion), _n(fecha),
             1 if afecta_categoria_equipo else 0, 1 if resuelto else 0,
             _n(fecha_resolucion), id_problema),
        )

    @staticmethod
    def eliminar_problema(id_problema):
        Modelo.asegurar_tablas_problemas()
        Modelo._exec("DELETE FROM problema_equipo WHERE id_problema=?", (id_problema,))

    # ── Señal (contenido que viaja por los cables) ───────────────────────────
    # Fase 1 de plan_entidad_senal.md: modelo + migración, sin motor de
    # propagación todavía (Fase 3) ni UI (Fase 2). Decisión ya tomada con el
    # usuario: senal_en_conector guarda ÚNICAMENTE el valor ACTUAL de señal
    # por conector (sin historial) — UNIQUE(id_conector) garantiza que un
    # conector tenga a lo sumo una fila vigente.
    ROLES_SENAL = ("FUENTE", "DISTRIBUIDOR", "ENRUTADOR", "PROCESADOR", "CONSUMIDOR",
                   "PATCHERA", "FANTASMA", "CONVERSOR_BALANCE", "SUMADOR_CANAL")
    # Los 5 primeros son roles de propagación de señal propiamente dichos
    # (usados por senal_propagation.py); PATCHERA y FANTASMA se agregaron
    # en la Fase 1/4/5 de plan_desarrollo_hardcodes_idioma.md para poder
    # validar tipo_equipo.rol_senal contra el mismo CHECK de 7 valores que
    # ahora tiene la tabla, sin duplicar la lista de valores válidos en dos
    # lugares distintos. La UI de rol de señal (_DialogoTipoEquipo, combo
    # "rol frente a la señal") sigue mostrando sólo los 5 primeros — ver
    # ROLES_SENAL_PROPAGACION. CONVERSOR_BALANCE y SUMADOR_CANAL se
    # agregaron para plan_riesgo_senal_audio.md (sección 4.4): equipos
    # cuyo rol es convertir formato de audio analógico (DI box, sumador,
    # transformador de balance) — signal_risk.py no marca falso-positivo
    # de mismatch de formato en un cable que cuelga de uno de estos.
    ROLES_SENAL_PROPAGACION = ROLES_SENAL[:5]
    ROLES_SENAL_CONVERSION_FORMATO = ("CONVERSOR_BALANCE", "SUMADOR_CANAL")

    @staticmethod
    def asegurar_columnas_control_idioma():
        """Fase 1 de plan_desarrollo_hardcodes_idioma.md: agrega columnas
        de control dedicadas para que la app deje de inferir comportamiento
        (dirección IN/OUT, rol de equipo, fila de patchera, fuente de
        referencia) leyendo texto libre (conector.nombre, tipo_conector.
        nombre, tipo_equipo.nombre) y pase a leer estas columnas:
          - tipo_equipo.rol_senal: ya existe (ver asegurar_tablas_senal);
            se amplía el conjunto de valores válidos a 7 (los 5 de
            Modelo.ROLES_SENAL_PROPAGACION + 'PATCHERA' + 'FANTASMA').
            OJO: NO se recrea la tabla para agregarle un CHECK — se probó
            contra una copia de la base real y romper (DROP+RENAME) rompe
            en el momento las ~10 vistas que referencian tipo_equipo
            (CONEXIONES, VISTA_EQUIPOS, VISTA_EQUIPO_DETALLE, etc. — el
            intento de recreación con CHECK murió con "no such table:
            main.tipo_equipo" al reconstruir la vista CONEXIONES en medio
            del ALTER TABLE RENAME). La validación de los 7 valores queda
            sólo en Python (Modelo.ROLES_SENAL, alta_tipo(),
            establecer_rol_senal_tipo_equipo()), igual de efectiva para
            todo lo que pasa por el Modelo y sin ese riesgo sobre datos
            reales.
          - tipo_conector.direccion ('IN'/'OUT')
          - tipo_conector.es_referencia_generada (0/1, ex REFOUT)
          - conector.fila_patchera ('A_BACK'/'B_BACK'/'A_FRONT'/'B_FRONT')
        Cada bloque puebla su columna a partir del texto/convención actual
        UNA SOLA VEZ (dentro del mismo `if columna no existe todavía`, o
        con el sentinel _migracion_hardcode_idioma para el caso de
        rol_senal que no agrega columna nueva), para no pisar en cada
        arranque un valor que alguien haya corregido a mano después de la
        migración inicial. Idempotente: seguro de llamar en cada arranque
        de la app, mismo patrón que asegurar_tablas_riesgo().
        """
        Modelo.asegurar_tablas_senal()  # asegura que tipo_equipo.rol_senal exista
        with Modelo._conn_ctx() as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS _migracion_hardcode_idioma ("
                "  clave TEXT PRIMARY KEY)")

            def _ya_corrida(clave):
                return bool(cur.execute(
                    "SELECT 1 FROM _migracion_hardcode_idioma WHERE clave=?",
                    (clave,)).fetchone())

            def _marcar(clave):
                cur.execute(
                    "INSERT OR IGNORE INTO _migracion_hardcode_idioma (clave) VALUES (?)",
                    (clave,))

            # ── tipo_conector.direccion / es_referencia_generada ──────────
            cols_tc = [c[1] for c in cur.execute(
                "PRAGMA table_info(tipo_conector)").fetchall()]
            if "direccion" not in cols_tc:
                cur.execute(
                    "ALTER TABLE tipo_conector ADD COLUMN direccion TEXT "
                    "CHECK(direccion IN ('IN','OUT'))")
                # Población única a partir del criterio de texto que se
                # reemplaza ("OUT" in nombre.upper() ya usado en graph_impact.
                # py / pantallas_avanzadas.py): si el nombre del tipo de
                # conector contiene "OUT" es OUT, si no es IN.
                cur.execute(
                    "UPDATE tipo_conector SET direccion = "
                    "CASE WHEN UPPER(nombre) LIKE '%OUT%' THEN 'OUT' ELSE 'IN' END")
                conn.commit()
            if "es_referencia_generada" not in cols_tc:
                cur.execute(
                    "ALTER TABLE tipo_conector ADD COLUMN "
                    "es_referencia_generada INTEGER NOT NULL DEFAULT 0")
                cur.execute(
                    "UPDATE tipo_conector SET es_referencia_generada = 1 "
                    "WHERE nombre = 'REFOUT'")
                conn.commit()

            # ── conector.fila_patchera ──────────────────────────────────
            cols_c = [c[1] for c in cur.execute(
                "PRAGMA table_info(conector)").fetchall()]
            if "fila_patchera" not in cols_c:
                cur.execute(
                    "ALTER TABLE conector ADD COLUMN fila_patchera TEXT "
                    "CHECK(fila_patchera IN "
                    "('A_BACK','B_BACK','A_FRONT','B_FRONT') "
                    "OR fila_patchera IS NULL)")
                # Población única a partir del prefijo de nombre, sólo sobre
                # conectores de equipos cuyo tipo ya tenía rol_senal
                # 'PATCHERA' o (si la migración de rol_senal todavía no
                # corrió en esta misma llamada) nombre 'MODULO PATCHERA' —
                # mismo criterio de texto que PatcherasVista/
                # _calc_conexion_interna usaban.
                cur.execute(
                    "UPDATE conector SET fila_patchera = ("
                    "  CASE"
                    "    WHEN UPPER(nombre) LIKE 'A_BACK%' THEN 'A_BACK'"
                    "    WHEN UPPER(nombre) LIKE 'B_BACK%' THEN 'B_BACK'"
                    "    WHEN UPPER(nombre) LIKE 'A_FRONT%' THEN 'A_FRONT'"
                    "    WHEN UPPER(nombre) LIKE 'B_FRONT%' THEN 'B_FRONT'"
                    "    ELSE NULL"
                    "  END)"
                    " WHERE id_equipo IN ("
                    "  SELECT e.id_equipo FROM equipo e"
                    "  JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo"
                    "  WHERE te.rol_senal = 'PATCHERA' OR UPPER(te.nombre) = 'MODULO PATCHERA')")
                conn.commit()

            # ── tipo_equipo.rol_senal: poblar PATCHERA/FANTASMA una sola vez ──
            if not _ya_corrida("rol_patchera_fantasma"):
                cur.execute(
                    "UPDATE tipo_equipo SET rol_senal='PATCHERA' "
                    "WHERE UPPER(nombre)='MODULO PATCHERA'")
                cur.execute(
                    "UPDATE tipo_equipo SET rol_senal='FANTASMA' "
                    "WHERE UPPER(nombre)='FANTASMA'")
                _marcar("rol_patchera_fantasma")
                conn.commit()

            # ── Fase A de plan_desarrollo_funcion_patchera.md ────────────
            # `fila_patchera` (arriba) fue un primer paso — una columna
            # dedicada en vez de leer el nombre — pero los 4 valores
            # posibles ('A_BACK'/'B_BACK'/'A_FRONT'/'B_FRONT') siguen
            # siendo la convención de nombre de UNA marca de patchera. Un
            # patch module de audio real (ej. equipo "01_25(1)") no tiene
            # ningún "A_BACK": tiene "01_BACK"/"25_BACK" con la MISMA
            # función. Acá se agrega una tabla de funciones ABSTRACTAS
            # (qué rol cumple el conector frente al bypass full-normal,
            # no qué letra tiene) y una columna que apunta a esa tabla,
            # migrando 1:1 desde fila_patchera SIN volver a mirar el
            # nombre del conector — los que ya estaban en NULL (las
            # patcheras de audio) siguen en NULL, se completan a mano
            # vía la UI de la Fase B.
            cur.execute(
                "CREATE TABLE IF NOT EXISTS funcion_patchera ("
                "  id_funcion_patchera INTEGER PRIMARY KEY,"
                "  clave        TEXT UNIQUE NOT NULL,"
                "  nombre_es    TEXT NOT NULL,"
                "  direccion    TEXT NOT NULL CHECK(direccion IN ('IN','OUT')),"
                "  descripcion  TEXT"
                ")"
            )
            _FUNCIONES_PATCHERA = (
                # (id, clave, nombre_es, direccion, descripcion)
                (1, "BACK_ENTRADA", "Trasero — entrada (paso normal)", "IN",
                 "Conector trasero por donde entra la señal de la ruta "
                 "normal (full-normal)."),
                (2, "BACK_SALIDA", "Trasero — salida (paso normal)", "OUT",
                 "Conector trasero hacia donde sale la señal de la ruta "
                 "normal."),
                (3, "FRONT_DERIVACION", "Frontal — derivación (tap)", "OUT",
                 "Jack frontal que deriva/monitorea la señal de "
                 "BACK_ENTRADA sin cortar el paso normal."),
                (4, "FRONT_INSERCION", "Frontal — inserción", "IN",
                 "Jack frontal que inserta una señal externa hacia "
                 "BACK_SALIDA, cortando el paso normal."),
            )
            for fila_fp in _FUNCIONES_PATCHERA:
                cur.execute(
                    "INSERT OR IGNORE INTO funcion_patchera "
                    "(id_funcion_patchera, clave, nombre_es, direccion, descripcion) "
                    "VALUES (?,?,?,?,?)", fila_fp)
            conn.commit()

            _MAPEO_FILA_A_FUNCION = {
                "A_BACK": "BACK_ENTRADA", "B_BACK": "BACK_SALIDA",
                "A_FRONT": "FRONT_DERIVACION", "B_FRONT": "FRONT_INSERCION",
            }
            for tabla in ("conector", "conector_catalogo"):
                cols_t = [c[1] for c in cur.execute(
                    f"PRAGMA table_info({tabla})").fetchall()]
                if "id_funcion_patchera" in cols_t:
                    continue
                cur.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN id_funcion_patchera "
                    f"INTEGER REFERENCES funcion_patchera(id_funcion_patchera)")
                if "fila_patchera" in cols_t:
                    for fila_txt, clave_fn in _MAPEO_FILA_A_FUNCION.items():
                        cur.execute(
                            f"UPDATE {tabla} SET id_funcion_patchera = "
                            "  (SELECT id_funcion_patchera FROM funcion_patchera "
                            "   WHERE clave=?) "
                            f"WHERE fila_patchera=?", (clave_fn, fila_txt))
                conn.commit()
                # UNIQUE(id_equipo, id_funcion_patchera) del plan: SQLite no
                # admite agregar un UNIQUE por ALTER TABLE sin reconstruir la
                # tabla (mismo problema ya documentado arriba para el CHECK
                # de rol_senal) — se logra igual con un índice único parcial,
                # que sí se puede crear sin tocar la tabla. "Parcial" porque
                # NULL no debe chocar entre sí (muchos conectores sin
                # función asignada todavía, ver Fase B).
                id_equipo_col = "id_equipo" if tabla == "conector" else "id_equipo_catalogo"
                cur.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS "
                    f"ux_{tabla}_funcion_patchera "
                    f"ON {tabla}({id_equipo_col}, id_funcion_patchera) "
                    f"WHERE id_funcion_patchera IS NOT NULL")
                conn.commit()

            # ── Fase 2/5 de plan_asistente_diagnostico_fallas.md ─────────
            # "Punto de test": conector físicamente cómodo de verificar con
            # un monitor/breakout portátil durante un diagnóstico de falla
            # — por defecto, cualquier jack frontal de patchera YA lo es
            # conceptualmente (FRONT_DERIVACION/FRONT_INSERCION), así que
            # se puebla solo sin pedirle nada al usuario; cualquier otro
            # conector puntual se puede marcar a mano desde su ficha.
            cols_conector = [c[1] for c in cur.execute(
                "PRAGMA table_info(conector)").fetchall()]
            if "es_punto_test" not in cols_conector:
                cur.execute(
                    "ALTER TABLE conector ADD COLUMN es_punto_test "
                    "INTEGER NOT NULL DEFAULT 0")
                cur.execute(
                    "UPDATE conector SET es_punto_test=1 WHERE id_conector IN ("
                    "  SELECT c.id_conector FROM conector c "
                    "  JOIN funcion_patchera fp "
                    "    ON fp.id_funcion_patchera = c.id_funcion_patchera "
                    "  WHERE fp.clave IN ('FRONT_DERIVACION','FRONT_INSERCION')"
                    ")")
                conn.commit()

            # Historial de sesiones de diagnóstico (mismo patrón que
            # escenario/escenario_cambio).
            cur.execute(
                "CREATE TABLE IF NOT EXISTS diagnostico_sesion ("
                "  id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_conector_sintoma INTEGER NOT NULL,"
                "  descripcion TEXT,"
                "  resultado TEXT,"
                "  id_cable_resultado INTEGER,"
                "  id_equipo_resultado INTEGER,"
                "  fecha_inicio TEXT,"
                "  fecha_fin TEXT,"
                "  FOREIGN KEY(id_conector_sintoma) REFERENCES conector(id_conector) ON DELETE CASCADE,"
                "  FOREIGN KEY(id_cable_resultado) REFERENCES cable(id_cable) ON DELETE SET NULL,"
                "  FOREIGN KEY(id_equipo_resultado) REFERENCES equipo(id_equipo) ON DELETE SET NULL"
                ")"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS diagnostico_paso ("
                "  id_paso INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_sesion INTEGER NOT NULL,"
                "  id_conector_consultado INTEGER NOT NULL,"
                "  respuesta TEXT NOT NULL CHECK(respuesta IN ('SI','NO','NO_SE')),"
                "  orden INTEGER NOT NULL,"
                "  FOREIGN KEY(id_sesion) REFERENCES diagnostico_sesion(id_sesion) ON DELETE CASCADE,"
                "  FOREIGN KEY(id_conector_consultado) REFERENCES conector(id_conector) ON DELETE CASCADE"
                ")"
            )
            conn.commit()

    @staticmethod
    def asegurar_columnas_riesgo_senal():
        """Migración idempotente de plan_riesgo_senal_audio.md — agrega
        las columnas/tabla de los 3 ejes de riesgo de calidad de señal
        (distinto del impacto lógico de graph_impact.py). Todas las
        columnas nacen en NULL/sin populate automático: son datos de
        catálogo (qué tan largo puede ser un cable de tal tipo, cuánto
        ancho de banda tiene una ficha, etc.) que sólo el usuario puede
        cargar con criterio real — no se estima nada acá. Seguro de
        llamar en cada arranque, mismo patrón que asegurar_columnas_
        control_idioma().

        Columnas agregadas:
          - tipo_cable.naturaleza_senal / longitud_maxima_recomendada_
            balanceado_m / longitud_maxima_recomendada_desbalanceado_m /
            ancho_banda_mhz  (riesgo #1 y #2)
          - cable.ancho_banda_mhz_override  (riesgo #2, override puntual)
          - tipo_ficha.n_conductores / modo_balance_default /
            modo_canal_default / ancho_banda_mhz  (riesgo #3, catálogo
            de fichas — compartido entre cable.id_tipo_ficha y el nuevo
            conector.id_tipo_ficha, ver más abajo)
          - conector.id_tipo_ficha  (NUEVO — desviación acordada respecto
            del plan original: conector no tenía FK a tipo_ficha, sólo a
            tipo_conector, que es un catálogo distinto sin formato
            eléctrico. Declara qué ficha es eléctricamente el jack de un
            equipo real, de ahí sale el default de modo_balance/
            modo_canal/n_conductores)
          - conector.modo_balance / modo_canal  (override puntual por
            jack real, riesgo #3)
          - equipo.senal_requerida_mhz  (v2, ancho de banda exigido por
            una fuente — columna agregada ahora porque es barata, el
            algoritmo de propagación queda para v2)
          - unidad_longitud_factor  (tabla chica de conversión a metros,
            sembrada con las unidades de uso común)
        """
        with Modelo._conn_ctx() as conn:
            cur = conn.cursor()

            def _add_col(tabla, col_def, col_nombre=None):
                nombre = col_nombre or col_def.split()[0].strip('"')
                cols = [c[1] for c in cur.execute(
                    f"PRAGMA table_info({tabla})").fetchall()]
                if nombre not in cols:
                    cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {col_def}")

            # ── tipo_cable (riesgo #1 atenuación, #2 ancho de banda) ────
            _add_col("tipo_cable",
                      "naturaleza_senal TEXT "
                      "CHECK(naturaleza_senal IN ('ANALOGICA','DIGITAL','HIBRIDA','DATOS'))")
            _add_col("tipo_cable", "longitud_maxima_recomendada_balanceado_m REAL")
            _add_col("tipo_cable", "longitud_maxima_recomendada_desbalanceado_m REAL")
            _add_col("tipo_cable", "ancho_banda_mhz REAL")

            # ── cable (override puntual de ancho de banda, #2) ──────────
            _add_col("cable", "ancho_banda_mhz_override REAL")

            # ── tipo_ficha (catálogo de fichas, #3 + #2 opcional) ───────
            _add_col("tipo_ficha", "n_conductores INTEGER")
            _add_col("tipo_ficha",
                      "modo_balance_default TEXT "
                      "CHECK(modo_balance_default IN ('BALANCEADO','DESBALANCEADO','NA'))")
            _add_col("tipo_ficha",
                      "modo_canal_default TEXT "
                      "CHECK(modo_canal_default IN ('MONO','ESTEREO','NA'))")
            _add_col("tipo_ficha", "ancho_banda_mhz REAL")

            # ── conector (jack de equipo real: qué ficha es + override) ─
            # id_tipo_ficha: NUEVO respecto del plan original (ver
            # docstring) — sin esto, COALESCE(conector.modo_balance,
            # tipo_ficha.modo_balance_default) no tiene por dónde
            # resolver el default.
            _add_col("conector",
                      "id_tipo_ficha INTEGER "
                      "REFERENCES tipo_ficha(id_tipo_ficha)")
            _add_col("conector",
                      "modo_balance TEXT "
                      "CHECK(modo_balance IN ('BALANCEADO','DESBALANCEADO','NA'))")
            _add_col("conector",
                      "modo_canal TEXT "
                      "CHECK(modo_canal IN ('MONO','ESTEREO','NA'))")

            # ── conexion (ficha PROPIA del cable en ese punto de conexión) ──
            # Descubierto en sesión posterior a la entrega inicial: un
            # cable puede tener fichas DISTINTAS en cada extremo (ej. XLR3
            # macho de un lado, TRS del otro), algo que cable.id_tipo_ficha
            # (un solo valor para todo el cable, campo pre-existente) no
            # puede representar. Se descartó "cable.id_tipo_ficha_extremo_
            # a/b" porque no hay ningún ordinal estable que distinga qué
            # extremo es "A" y cuál es "B" — CONEXIONES_AMBOS_EXTREMOS
            # arma esa etiqueta con un self-join sin ORDER BY, no es
            # determinístico. En cambio, cada fila de `conexion` YA sabe
            # sin ambigüedad a qué conector se conecta ese extremo del
            # cable — ahí es donde corresponde declarar la ficha física
            # real de esa punta. signal_risk.py usa esto para el chequeo
            # ELECTRICO (riesgo #3): ficha propia del cable en esa punta
            # vs. la ficha declarada del jack (conector.id_tipo_ficha) —
            # antes comparaba jack contra jack, que no detecta el caso
            # real (plug de este cable puntual mal insertado en un jack).
            _add_col("conexion",
                      "id_tipo_ficha INTEGER "
                      "REFERENCES tipo_ficha(id_tipo_ficha)")

            # ── equipo (v2 — requerimiento explícito de la fuente) ──────
            _add_col("equipo", "senal_requerida_mhz REAL")

            # ── unidad_longitud_factor (conversión a metros) ────────────
            cur.execute(
                "CREATE TABLE IF NOT EXISTS unidad_longitud_factor ("
                "  unidad TEXT PRIMARY KEY,"
                "  factor_a_metros REAL NOT NULL"
                ")"
            )
            for unidad, factor in (
                ("m", 1.0), ("cm", 0.01), ("mm", 0.001), ("km", 1000.0),
                ("ft", 0.3048), ("in", 0.0254),
            ):
                cur.execute(
                    "INSERT OR IGNORE INTO unidad_longitud_factor "
                    "(unidad, factor_a_metros) VALUES (?,?)", (unidad, factor))

            conn.commit()

    def asegurar_tablas_senal():
        """Crea/migra las tablas necesarias para modelar la señal como
        entidad:
          - senal               : catálogo de identidades de contenido
            (ej. "TELEFE SAT"), independiente del formato técnico.
          - tipo_formato_senal  : catálogo de formatos técnicos (ej. "SDI
            1080i", "IP ST2110"), separado de 'senal' porque la misma señal
            puede cambiar de formato varias veces en su recorrido.
          - senal_en_conector   : qué señal/formato hay en cada conector,
            SOLO el valor actual (sin historial). origen indica si se
            cargó a mano ('MANUAL') o la calculó el motor de propagación
            ('PROPAGADA', Fase 3, todavía no implementado).
          - tipo_equipo.rol_senal : cómo se comporta cada tipo de equipo
            frente a la señal — FUENTE / DISTRIBUIDOR / ENRUTADOR /
            PROCESADOR / CONSUMIDOR (ver Modelo.ROLES_SENAL). Default
            'DISTRIBUIDOR' para no romper tipos ya cargados (es el
            comportamiento más neutro: repite lo que recibe).
        Idempotente: seguro de llamar en cada arranque de la app, mismo
        patrón que asegurar_tablas_riesgo().
        """
        with Modelo._conn_ctx() as conn:
            cols_tipo = [c[1] for c in conn.execute(
                "PRAGMA table_info(tipo_equipo)").fetchall()]
            if "rol_senal" not in cols_tipo:
                conn.execute(
                    "ALTER TABLE tipo_equipo ADD COLUMN rol_senal TEXT "
                    "DEFAULT 'DISTRIBUIDOR'")

            conn.execute(
                "CREATE TABLE IF NOT EXISTS senal ("
                "  id_senal       INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  nombre         TEXT NOT NULL,"
                "  tipo_contenido TEXT,"
                "  descripcion    TEXT,"
                "  fecha_ultima_edicion TEXT"
                ")"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS tipo_formato_senal ("
                "  id_formato     INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  nombre         TEXT NOT NULL,"
                "  fecha_ultima_edicion TEXT"
                ")"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS senal_en_conector ("
                "  id_senal_en_conector INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_conector    INTEGER NOT NULL UNIQUE,"
                "  id_senal       INTEGER NOT NULL,"
                "  id_formato     INTEGER,"
                "  origen         TEXT NOT NULL DEFAULT 'MANUAL' "
                "                 CHECK (origen IN ('MANUAL','PROPAGADA')),"
                "  fecha_ultima_edicion TEXT,"
                "  FOREIGN KEY(id_conector) REFERENCES conector(id_conector)"
                "    ON DELETE CASCADE,"
                "  FOREIGN KEY(id_senal) REFERENCES senal(id_senal)"
                "    ON DELETE CASCADE,"
                "  FOREIGN KEY(id_formato) REFERENCES tipo_formato_senal(id_formato)"
                "    ON DELETE SET NULL"
                ")"
            )
            conn.commit()

    # -- Catálogo: senal (identidades de contenido) --
    @staticmethod
    def devolver_senales():
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT id_senal, nombre, tipo_contenido, descripcion "
            "FROM senal ORDER BY nombre"
        )

    @staticmethod
    def devolver_senal(id_senal):
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT id_senal, nombre, tipo_contenido, descripcion "
            "FROM senal WHERE id_senal=?",
            (id_senal,),
        )

    @staticmethod
    def agregar_senal(nombre, tipo_contenido=None, descripcion=None):
        """Devuelve el id_senal recién insertado (usado por el alta rápida
        desde el combo de la ficha de conector)."""
        Modelo.asegurar_tablas_senal()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO senal (nombre, tipo_contenido, descripcion, "
                "fecha_ultima_edicion) VALUES "
                "(?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (_n(nombre), _n(tipo_contenido), _n(descripcion)),
            )
            return cur.lastrowid

    @staticmethod
    def modificar_senal(id_senal, nombre, tipo_contenido=None, descripcion=None):
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "UPDATE senal SET nombre=?, tipo_contenido=?, descripcion=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_senal=?",
            (_n(nombre), _n(tipo_contenido), _n(descripcion), id_senal),
        )

    @staticmethod
    def eliminar_senal(id_senal):
        Modelo.asegurar_tablas_senal()
        Modelo._exec("DELETE FROM senal WHERE id_senal=?", (id_senal,))

    # -- Catálogo: tipo_formato_senal --
    @staticmethod
    def devolver_formatos_senal():
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT id_formato, nombre FROM tipo_formato_senal ORDER BY nombre"
        )

    @staticmethod
    def agregar_tipo_formato_senal(nombre):
        """Devuelve el id_formato recién insertado (mismo motivo que
        agregar_senal: alta rápida desde combo)."""
        Modelo.asegurar_tablas_senal()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO tipo_formato_senal (nombre, fecha_ultima_edicion) "
                "VALUES (?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (_n(nombre),),
            )
            return cur.lastrowid

    @staticmethod
    def modificar_tipo_formato_senal(id_formato, nombre):
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "UPDATE tipo_formato_senal SET nombre=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_formato=?",
            (_n(nombre), id_formato),
        )

    @staticmethod
    def eliminar_tipo_formato_senal(id_formato):
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "DELETE FROM tipo_formato_senal WHERE id_formato=?", (id_formato,)
        )

    # -- senal_en_conector (valor actual, sin historial) --
    @staticmethod
    def devolver_senal_en_conector(id_conector):
        """Fila (id_senal, nombre_senal, id_formato, nombre_formato, origen)
        vigente en ese conector, o [] si no tiene ninguna cargada."""
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT s.id_senal, s.nombre, f.id_formato, f.nombre, sec.origen "
            "FROM senal_en_conector sec "
            "JOIN senal s ON s.id_senal = sec.id_senal "
            "LEFT JOIN tipo_formato_senal f ON f.id_formato = sec.id_formato "
            "WHERE sec.id_conector=?",
            (id_conector,),
        )

    @staticmethod
    def establecer_senal_en_conector(id_conector, id_senal, id_formato=None,
                                      origen="MANUAL"):
        """Carga o reemplaza la señal vigente de un conector (upsert por
        id_conector, que es UNIQUE). origen: 'MANUAL' (por defecto, carga
        del usuario) o 'PROPAGADA' (reservado para el motor de propagación
        de Fase 3)."""
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "INSERT INTO senal_en_conector "
            "(id_conector, id_senal, id_formato, origen, fecha_ultima_edicion) "
            "VALUES (?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')) "
            "ON CONFLICT(id_conector) DO UPDATE SET "
            "  id_senal=excluded.id_senal, id_formato=excluded.id_formato, "
            "  origen=excluded.origen, "
            "  fecha_ultima_edicion=excluded.fecha_ultima_edicion",
            (id_conector, id_senal, _n(id_formato), origen),
        )

    @staticmethod
    def quitar_senal_en_conector(id_conector):
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "DELETE FROM senal_en_conector WHERE id_conector=?", (id_conector,)
        )

    @staticmethod
    def reporte_formatos_en_uso():
        """Fase 6 de plan_entidad_senal.md: para cada formato técnico,
        cuántos conectores y cuántas señales distintas lo usan hoy.
        Incluye una fila para señales cargadas sin formato especificado
        (id_formato NULL) — útil para ver, por ejemplo, cuánto SDI legacy
        queda frente a IP ST2110 y planificar una migración."""
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT COALESCE(f.nombre, '(sin formato especificado)') AS nombre, "
            "       COUNT(DISTINCT sec.id_conector) AS n_conectores, "
            "       COUNT(DISTINCT sec.id_senal) AS n_senales "
            "FROM senal_en_conector sec "
            "LEFT JOIN tipo_formato_senal f ON f.id_formato = sec.id_formato "
            "GROUP BY sec.id_formato "
            "ORDER BY n_conectores DESC"
        )

    @staticmethod
    def reporte_senales_sin_usar():
        """Señales del catálogo que todavía no están cargadas en ningún
        conector (ni manual ni propagada) — catálogo dado de alta pero
        nunca asignado, candidatas a revisar o dar de baja."""
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT s.id_senal, s.nombre, s.tipo_contenido "
            "FROM senal s "
            "LEFT JOIN senal_en_conector sec ON sec.id_senal = s.id_senal "
            "WHERE sec.id_senal IS NULL "
            "ORDER BY s.nombre"
        )

    @staticmethod
    def reporte_senales_propagadas_sin_origen():
        """Señales con al menos un conector PROPAGADA pero sin NINGÚN
        conector MANUAL que las sostenga — inconsistencia real: suele
        pasar cuando se borra o cambia la carga manual original después
        de haber aplicado una propagación, y quedan filas PROPAGADA
        'colgando' de una fuente que ya no existe. Candidatas a limpiar
        (quitar la señal de esos conectores) o a volver a cargar la
        fuente manual y recalcular."""
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT DISTINCT s.id_senal, s.nombre "
            "FROM senal_en_conector sec "
            "JOIN senal s ON s.id_senal = sec.id_senal "
            "WHERE sec.origen='PROPAGADA' "
            "  AND s.id_senal NOT IN "
            "      (SELECT id_senal FROM senal_en_conector WHERE origen='MANUAL') "
            "ORDER BY s.nombre"
        )

    @staticmethod
    def contar_senales_propagadas():
        """Cantidad de conectores con una señal PROPAGADA vigente hoy —
        usado para confirmar antes de limpiar_senales_propagadas()."""
        Modelo.asegurar_tablas_senal()
        filas = Modelo._query(
            "SELECT COUNT(*) FROM senal_en_conector WHERE origen='PROPAGADA'"
        )
        return filas[0][0] if filas else 0

    @staticmethod
    def limpiar_senales_propagadas():
        """Borra (deja en null) todas las asignaciones de señal con
        origen='PROPAGADA' en senal_en_conector, sin tocar las cargas
        MANUAL. Como senal_en_conector guarda solo el valor vigente por
        conector (id_conector es UNIQUE), borrar la fila equivale a
        dejar ese conector sin señal asignada. Útil para descartar en
        bloque el resultado de una propagación anterior antes de
        recalcular. Devuelve la cantidad de filas borradas."""
        Modelo.asegurar_tablas_senal()
        n = Modelo.contar_senales_propagadas()
        Modelo._exec(
            "DELETE FROM senal_en_conector WHERE origen='PROPAGADA'"
        )
        return n

    @staticmethod
    def buscar_conectores_por_senal(id_senal):
        """Fase 2 (buscador '¿dónde está esta señal?'): todos los
        conectores que hoy tienen cargada esa señal, con el equipo al que
        pertenecen. Cols: id_conector, nombre_conector, id_equipo,
        nombre_equipo, nombre_formato, origen."""
        Modelo.asegurar_tablas_senal()
        return Modelo._query(
            "SELECT c.id_conector, c.nombre, e.id_equipo, e.nombre, "
            "       f.nombre, sec.origen "
            "FROM senal_en_conector sec "
            "JOIN conector c ON c.id_conector = sec.id_conector "
            "LEFT JOIN equipo e ON e.id_equipo = c.id_equipo "
            "LEFT JOIN tipo_formato_senal f ON f.id_formato = sec.id_formato "
            "WHERE sec.id_senal=? "
            "ORDER BY e.nombre, c.nombre",
            (id_senal,),
        )

    # ── Linaje de señal (plan_estado_senal_y_linaje.md, Función 2) ─────────
    # Documenta de qué señal(es) DERIVA una señal (ej. "PROGRAMA CON LOGOS
    # TRANSMISION" deriva de "CLEAN FEED PROGRAMA TRANSMISION" + "COMERCIALES
    # KEY LOGOS" + "COMERCIALES FILL LOGOS"). Es puramente documental: NO
    # alimenta senal_propagation.py (que sigue exigiendo carga manual en
    # PROCESADOR) ni graph_impact.py (que sigue usando regla_logica para
    # calcular cortes) — decisión tomada explícitamente en la entrevista
    # que originó el plan, para no mezclar genealogía de nombres con
    # topología real.

    @staticmethod
    def asegurar_tabla_senal_linaje():
        """Idempotente, mismo patrón que asegurar_tablas_senal(). Se separa
        en su propio método (en vez de sumarla a asegurar_tablas_senal)
        porque es una función que se agregó después, sobre una base que
        puede no tener todavía ninguna señal cargada — así una instalación
        vieja que ya corrió asegurar_tablas_senal() muchas veces no repite
        ningún CREATE TABLE de más al actualizar."""
        Modelo.asegurar_tablas_senal()   # FK a senal — debe existir antes
        with Modelo._conn_ctx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS senal_linaje ("
                "  id_linaje            INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_senal_hijo        INTEGER NOT NULL,"
                "  id_senal_padre       INTEGER NOT NULL,"
                "  nota                 TEXT,"
                "  fecha_ultima_edicion TEXT,"
                "  FOREIGN KEY(id_senal_hijo)  REFERENCES senal(id_senal)"
                "    ON DELETE CASCADE,"
                "  FOREIGN KEY(id_senal_padre) REFERENCES senal(id_senal)"
                "    ON DELETE CASCADE,"
                "  UNIQUE(id_senal_hijo, id_senal_padre)"
                ")"
            )
            conn.commit()

    @staticmethod
    def devolver_padres_de_senal(id_senal_hijo):
        """[(id_linaje, id_senal_padre, nombre_padre, nota), ...] — de qué
        señales deriva la señal dada (un nivel, no recursivo; el árbol
        recursivo lo arma la UI llamando de nuevo por cada padre)."""
        Modelo.asegurar_tabla_senal_linaje()
        return Modelo._query(
            "SELECT sl.id_linaje, sl.id_senal_padre, s.nombre, sl.nota "
            "FROM senal_linaje sl "
            "JOIN senal s ON s.id_senal = sl.id_senal_padre "
            "WHERE sl.id_senal_hijo=? ORDER BY s.nombre",
            (id_senal_hijo,),
        )

    @staticmethod
    def devolver_hijos_de_senal(id_senal_padre):
        """[(id_linaje, id_senal_hijo, nombre_hijo, nota), ...] — en qué
        señales se usa la señal dada como insumo (un nivel)."""
        Modelo.asegurar_tabla_senal_linaje()
        return Modelo._query(
            "SELECT sl.id_linaje, sl.id_senal_hijo, s.nombre, sl.nota "
            "FROM senal_linaje sl "
            "JOIN senal s ON s.id_senal = sl.id_senal_hijo "
            "WHERE sl.id_senal_padre=? ORDER BY s.nombre",
            (id_senal_padre,),
        )

    @staticmethod
    def hay_ciclo_linaje(id_senal_hijo, id_senal_padre) -> bool:
        """True si agregar id_senal_padre como padre de id_senal_hijo
        cerraría un ciclo — es decir, si id_senal_hijo ya es (directa o
        transitivamente) ANCESTRO de id_senal_padre. Recorrido simple
        hacia arriba desde id_senal_padre; el grafo de linaje es chico
        (decenas de señales, no miles), así que no hace falta nada más
        sofisticado que un BFS en Python."""
        Modelo.asegurar_tabla_senal_linaje()
        if str(id_senal_hijo) == str(id_senal_padre):
            return True
        visitados = set()
        pendientes = [str(id_senal_padre)]
        while pendientes:
            actual = pendientes.pop()
            if actual in visitados:
                continue
            visitados.add(actual)
            for _id_lin, id_padre, _nom, _nota in Modelo.devolver_padres_de_senal(actual):
                id_padre = str(id_padre)
                if id_padre == str(id_senal_hijo):
                    return True
                if id_padre not in visitados:
                    pendientes.append(id_padre)
        return False

    @staticmethod
    def agregar_linaje(id_senal_hijo, id_senal_padre, nota=None):
        """Inserta el vínculo padre→hijo (upsert por el UNIQUE compuesto,
        para poder editar solo la nota sin duplicar fila si ya existía).
        No valida ciclos acá — el llamador (UI) debe chequear
        hay_ciclo_linaje() antes, para poder avisarle al usuario en vez
        de fallar en silencio o con una excepción de bajo nivel."""
        Modelo.asegurar_tabla_senal_linaje()
        Modelo._exec(
            "INSERT INTO senal_linaje "
            "(id_senal_hijo, id_senal_padre, nota, fecha_ultima_edicion) "
            "VALUES (?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')) "
            "ON CONFLICT(id_senal_hijo, id_senal_padre) DO UPDATE SET "
            "  nota=excluded.nota, "
            "  fecha_ultima_edicion=excluded.fecha_ultima_edicion",
            (id_senal_hijo, id_senal_padre, _n(nota)),
        )

    @staticmethod
    def quitar_linaje(id_linaje):
        Modelo.asegurar_tabla_senal_linaje()
        Modelo._exec("DELETE FROM senal_linaje WHERE id_linaje=?", (id_linaje,))

    @staticmethod
    def sugerir_padres_de_senal(id_senal_hijo):
        """Algoritmo de sugerencia (sección 3.3 del plan): ubica los
        conectores de SALIDA (OUT) donde esta señal está cargada MANUAL
        — sólo OUT importa: una señal manual en un conector IN significa
        que esa señal está LLEGANDO ahí desde otro lado, no que el
        equipo la produce; sugerirle "padres" a una señal por el sólo
        hecho de estar en una entrada mezclaría insumos hermanos sin
        relación real (ej. CLEAN FEED entrando a un DSK terminaría
        sugiriendo KEY LOGOS/FILL LOGOS como si CLEAN FEED derivara de
        ellas, siendo que las tres son insumos independientes del mismo
        combinador). Mira TODOS los conectores de entrada (IN) del
        equipo dueño de cada conector OUT encontrado, y junta las
        señales (MANUAL o PROPAGADA) que hoy están cargadas ahí.
        Devuelve [(id_senal_padre, nombre_padre), ...] deduplicado y
        ordenado por nombre. Puede devolver [] si la señal hijo todavía
        no está cargada MANUAL en ningún conector de salida — no es un
        error, sólo significa "no hay de dónde sugerir todavía, cargar
        a mano"."""
        Modelo.asegurar_tabla_senal_linaje()
        conectores_hijo = Modelo._query(
            "SELECT sec.id_conector, c.id_equipo FROM senal_en_conector sec "
            "JOIN conector c ON c.id_conector = sec.id_conector "
            "JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE sec.id_senal=? AND sec.origen='MANUAL' "
            "AND UPPER(COALESCE(tc.direccion,'')) = 'OUT'",
            (id_senal_hijo,),
        )
        if not conectores_hijo:
            return []

        ids_equipo = {str(r[1]) for r in conectores_hijo if r[1]}
        if not ids_equipo:
            return []

        placeholders = ",".join("?" * len(ids_equipo))
        filas = Modelo._query(
            "SELECT DISTINCT s.id_senal, s.nombre "
            "FROM conector c "
            "JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "JOIN senal_en_conector sec ON sec.id_conector = c.id_conector "
            "JOIN senal s ON s.id_senal = sec.id_senal "
            "WHERE c.id_equipo IN ({}) "
            "  AND UPPER(COALESCE(tc.direccion,'')) = 'IN' "
            "  AND s.id_senal != ? "
            "ORDER BY s.nombre".format(placeholders),
            tuple(ids_equipo) + (id_senal_hijo,),
        )
        return [(str(r[0]), r[1]) for r in filas]

    @staticmethod
    def aplicar_propagacion_senal(propuestas_aceptadas):
        """Persiste como PROPAGADA cada propuesta aceptada por el usuario
        (ver senal_propagation.PropagadorSenal / _DialogoPropagacionSenal).
        propuestas_aceptadas: iterable de objetos con .id_conector,
        .id_senal, .id_formato, .origen (típicamente PropuestaConector).
        Salvaguarda explícita: nunca pisa una fila que hoy sea MANUAL,
        aunque el motor la haya incluido entre las propuestas (no debería
        pasar si la UI filtra bien, pero se revalida acá por las dudas —
        MANUAL es siempre la carga humana, tiene la última palabra).
        Devuelve la cantidad de filas realmente escritas."""
        Modelo.asegurar_tablas_senal()
        escritas = 0
        for p in propuestas_aceptadas:
            if not p.id_senal or p.origen != "PROPAGADA":
                continue
            actual = Modelo.devolver_senal_en_conector(p.id_conector)
            if actual and actual[0][4] == "MANUAL":
                continue
            Modelo.establecer_senal_en_conector(
                p.id_conector, p.id_senal,
                p.id_formato if p.id_formato else None,
                origen="PROPAGADA",
            )
            escritas += 1
        return escritas

    # -- rol_senal por tipo de equipo --
    @staticmethod
    def devolver_rol_senal_tipo_equipo(id_tipo_equipo):
        """Devuelve el rol_senal cargado, o 'DISTRIBUIDOR' si el tipo
        todavía no tiene uno asignado explícitamente."""
        Modelo.asegurar_tablas_senal()
        filas = Modelo._query(
            "SELECT rol_senal FROM tipo_equipo WHERE id_tipo_equipo=?",
            (id_tipo_equipo,),
        )
        if not filas or not filas[0][0]:
            return "DISTRIBUIDOR"
        return filas[0][0]

    @staticmethod
    def establecer_rol_senal_tipo_equipo(id_tipo_equipo, rol_senal):
        if rol_senal not in Modelo.ROLES_SENAL:
            raise ValueError(
                f"rol_senal inválido: {rol_senal!r} "
                f"(debe ser uno de {Modelo.ROLES_SENAL})"
            )
        Modelo.asegurar_tablas_senal()
        Modelo._exec(
            "UPDATE tipo_equipo SET rol_senal=? WHERE id_tipo_equipo=?",
            (rol_senal, id_tipo_equipo),
        )

    # -- direccion / es_referencia_generada por tipo_conector (Fase 7) --
    @staticmethod
    def establecer_direccion_tipo_conector(id_tipo_conector, direccion):
        if direccion not in ("IN", "OUT"):
            raise ValueError(f"direccion inválida: {direccion!r} (debe ser 'IN' u 'OUT')")
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE tipo_conector SET direccion=? WHERE id_tipo_conector=?",
            (direccion, id_tipo_conector),
        )

    @staticmethod
    def establecer_es_referencia_generada_tipo_conector(id_tipo_conector, valor):
        Modelo.asegurar_columnas_control_idioma()
        Modelo._exec(
            "UPDATE tipo_conector SET es_referencia_generada=? WHERE id_tipo_conector=?",
            (1 if valor else 0, id_tipo_conector),
        )

    # ── Diagramas personalizados (guardados) ────────────────────────────────
    # Feature aparte: diagramas armados a mano por el usuario (equipos +
    # conexiones reales y/o "manuales" no persistidas en la tabla conexion).
    # Tablas propias, sin tocar el esquema/flujo existente.
    @staticmethod
    def asegurar_tablas_diagramas_guardados():
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS diagrama_guardado ("
            "  id_diagrama INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre TEXT NOT NULL,"
            "  descripcion TEXT,"
            "  fecha_creacion TEXT,"
            "  fecha_edicion TEXT"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS diagrama_guardado_nodo ("
            "  id_diagrama_nodo INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_diagrama INTEGER NOT NULL,"
            "  id_equipo INTEGER NOT NULL,"
            "  x REAL, y REAL,"
            "  FOREIGN KEY(id_diagrama) REFERENCES diagrama_guardado(id_diagrama) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS diagrama_guardado_conexion ("
            "  id_diagrama_conexion INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_diagrama INTEGER NOT NULL,"
            "  id_conector_a INTEGER NOT NULL,"
            "  id_conector_b INTEGER NOT NULL,"
            "  es_real INTEGER DEFAULT 0,"
            "  id_cable_real INTEGER,"
            "  etiqueta TEXT,"
            "  FOREIGN KEY(id_diagrama) REFERENCES diagrama_guardado(id_diagrama) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_a) REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_b) REFERENCES conector(id_conector) ON DELETE CASCADE"
            ")"
        )

    @staticmethod
    def devolver_todos_los_diagramas_guardados():
        Modelo.asegurar_tablas_diagramas_guardados()
        return Modelo._query(
            "SELECT d.id_diagrama, d.nombre, COALESCE(d.descripcion,''), "
            "COALESCE(d.fecha_edicion, d.fecha_creacion, ''), "
            "(SELECT COUNT(*) FROM diagrama_guardado_nodo n "
            " WHERE n.id_diagrama=d.id_diagrama) AS n_equipos "
            "FROM diagrama_guardado d ORDER BY d.nombre"
        )

    @staticmethod
    def devolver_diagrama_guardado(id_diagrama):
        Modelo.asegurar_tablas_diagramas_guardados()
        return Modelo._query(
            "SELECT id_diagrama, nombre, COALESCE(descripcion,''), "
            "fecha_creacion, fecha_edicion "
            "FROM diagrama_guardado WHERE id_diagrama=?",
            (id_diagrama,),
        )

    @staticmethod
    def alta_diagrama_guardado(nombre, descripcion):
        Modelo.asegurar_tablas_diagramas_guardados()
        with Modelo._conn() as conn:
            cur = conn.execute(
                "INSERT INTO diagrama_guardado "
                "(nombre, descripcion, fecha_creacion, fecha_edicion) VALUES "
                "(?,?,STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'),"
                "STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (_n(nombre), _n(descripcion)),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def modificar_diagrama_guardado(id_diagrama, nombre, descripcion):
        Modelo.asegurar_tablas_diagramas_guardados()
        Modelo._exec(
            "UPDATE diagrama_guardado SET nombre=?, descripcion=?, "
            "fecha_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_diagrama=?",
            (_n(nombre), _n(descripcion), id_diagrama),
        )

    @staticmethod
    def eliminar_diagrama_guardado(id_diagrama):
        Modelo.asegurar_tablas_diagramas_guardados()
        Modelo._exec(
            "DELETE FROM diagrama_guardado WHERE id_diagrama=?", (id_diagrama,)
        )

    @staticmethod
    def devolver_nodos_de_diagrama_guardado(id_diagrama):
        Modelo.asegurar_tablas_diagramas_guardados()
        return Modelo._query(
            "SELECT id_equipo, x, y FROM diagrama_guardado_nodo "
            "WHERE id_diagrama=?",
            (id_diagrama,),
        )

    @staticmethod
    def devolver_conexiones_de_diagrama_guardado(id_diagrama):
        Modelo.asegurar_tablas_diagramas_guardados()
        return Modelo._query(
            "SELECT id_conector_a, id_conector_b, es_real, id_cable_real, "
            "COALESCE(etiqueta,'') FROM diagrama_guardado_conexion "
            "WHERE id_diagrama=?",
            (id_diagrama,),
        )

    @staticmethod
    def guardar_contenido_diagrama_guardado(id_diagrama, nodos, conexiones):
        """Reemplaza (borra + reinserta) todos los nodos/conexiones de un
        diagrama guardado.
        nodos:      [(id_equipo, x, y), ...]
        conexiones: [(id_conector_a, id_conector_b, es_real, id_cable_real, etiqueta), ...]
        """
        Modelo.asegurar_tablas_diagramas_guardados()
        with Modelo._conn() as conn:
            conn.execute(
                "DELETE FROM diagrama_guardado_nodo WHERE id_diagrama=?",
                (id_diagrama,),
            )
            conn.execute(
                "DELETE FROM diagrama_guardado_conexion WHERE id_diagrama=?",
                (id_diagrama,),
            )
            for id_eq, x, y in nodos:
                conn.execute(
                    "INSERT INTO diagrama_guardado_nodo "
                    "(id_diagrama, id_equipo, x, y) VALUES (?,?,?,?)",
                    (id_diagrama, id_eq, x, y),
                )
            for a, b, real, cable_real, etq in conexiones:
                conn.execute(
                    "INSERT INTO diagrama_guardado_conexion "
                    "(id_diagrama, id_conector_a, id_conector_b, es_real, "
                    "id_cable_real, etiqueta) VALUES (?,?,?,?,?,?)",
                    (id_diagrama, a, b, real, cable_real, etq),
                )
            conn.execute(
                "UPDATE diagrama_guardado SET "
                "fecha_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                "WHERE id_diagrama=?",
                (id_diagrama,),
            )
            conn.commit()

    @staticmethod
    def equipo_de_conector(id_conector):
        rows = Modelo._query(
            "SELECT id_equipo FROM conector WHERE id_conector=?", (id_conector,)
        )
        return str(rows[0][0]) if rows and rows[0][0] is not None else None

    # ── Modo Escenario (Plan: CableDoc_Plan_Escenarios_Diagrama.md) ─────────
    # Ver escenario_engine.py / escenario_ui.py. Sigue el mismo patrón que
    # asegurar_tablas_riesgo() / asegurar_tablas_diagramas_guardados(): un
    # "escenario" agrupa varios cambios (falla de equipo, desconexión de
    # cable, conexión virtual) que se evalúan juntos en un solo cálculo
    # (GraphImpactAnalyzer.simular_escenario) sin tocar la infraestructura
    # real hasta que se confirma "Aplicar". No se persiste el resultado de
    # la simulación (se recalcula al vuelo al abrir el escenario, igual
    # criterio que ya se usa para simular_desconexion/simular_falla_equipo:
    # es barato, no vale la pena guardarlo y arriesgarse a que quede
    # desactualizado si cambia la infraestructura real).
    @staticmethod
    def asegurar_tablas_escenario():
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS escenario ("
            "  id_escenario INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  nombre TEXT NOT NULL,"
            "  descripcion TEXT,"
            "  estado TEXT NOT NULL DEFAULT 'borrador',"  # borrador|simulado|aprobado|aplicado|descartado
            "  fecha_creacion TEXT,"
            "  fecha_ultima_edicion TEXT"
            ")"
        )
        Modelo._exec(
            "CREATE TABLE IF NOT EXISTS escenario_cambio ("
            "  id_cambio INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  id_escenario INTEGER NOT NULL,"
            "  tipo TEXT NOT NULL,"  # falla_equipo|desconexion_cable|conexion_virtual
            "  id_equipo INTEGER,"
            "  id_cable INTEGER,"
            "  id_conector_a INTEGER,"
            "  id_conector_b INTEGER,"
            "  orden INTEGER NOT NULL DEFAULT 0,"
            "  fecha_ultima_edicion TEXT,"
            "  FOREIGN KEY(id_escenario) REFERENCES escenario(id_escenario) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_equipo) REFERENCES equipo(id_equipo) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_cable) REFERENCES cable(id_cable) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_a) REFERENCES conector(id_conector) ON DELETE CASCADE,"
            "  FOREIGN KEY(id_conector_b) REFERENCES conector(id_conector) ON DELETE CASCADE"
            ")"
        )

    @staticmethod
    def crear_escenario(nombre, descripcion=None):
        Modelo.asegurar_tablas_escenario()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO escenario "
                "(nombre, descripcion, estado, fecha_creacion, fecha_ultima_edicion) "
                "VALUES (?,?,'borrador',"
                "STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'),"
                "STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (_n(nombre), _n(descripcion)),
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def devolver_escenario(id_escenario):
        Modelo.asegurar_tablas_escenario()
        r = Modelo._query(
            "SELECT id_escenario, nombre, COALESCE(descripcion,''), estado, "
            "fecha_creacion, fecha_ultima_edicion FROM escenario "
            "WHERE id_escenario=?",
            (id_escenario,),
        )
        return r[0] if r else None

    @staticmethod
    def devolver_todos_los_escenarios():
        Modelo.asegurar_tablas_escenario()
        return Modelo._query(
            "SELECT e.id_escenario, e.nombre, COALESCE(e.descripcion,''), "
            "e.estado, COALESCE(e.fecha_ultima_edicion, e.fecha_creacion, ''), "
            "(SELECT COUNT(*) FROM escenario_cambio c "
            " WHERE c.id_escenario=e.id_escenario) AS n_cambios "
            "FROM escenario e ORDER BY "
            "COALESCE(e.fecha_ultima_edicion, e.fecha_creacion) DESC"
        )

    @staticmethod
    def modificar_escenario(id_escenario, nombre, descripcion):
        Modelo.asegurar_tablas_escenario()
        Modelo._exec(
            "UPDATE escenario SET nombre=?, descripcion=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_escenario=?",
            (_n(nombre), _n(descripcion), id_escenario),
        )

    @staticmethod
    def actualizar_estado_escenario(id_escenario, estado):
        """estado: 'borrador' | 'simulado' | 'aprobado' | 'aplicado' | 'descartado'."""
        Modelo.asegurar_tablas_escenario()
        Modelo._exec(
            "UPDATE escenario SET estado=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_escenario=?",
            (estado, id_escenario),
        )

    @staticmethod
    def eliminar_escenario(id_escenario):
        Modelo.asegurar_tablas_escenario()
        Modelo._exec(
            "DELETE FROM escenario WHERE id_escenario=?", (id_escenario,)
        )

    @staticmethod
    def devolver_cambios_de_escenario(id_escenario):
        Modelo.asegurar_tablas_escenario()
        return Modelo._query(
            "SELECT id_cambio, tipo, id_equipo, id_cable, "
            "id_conector_a, id_conector_b, orden "
            "FROM escenario_cambio WHERE id_escenario=? ORDER BY orden, id_cambio",
            (id_escenario,),
        )

    @staticmethod
    def agregar_cambio_escenario(id_escenario, tipo, id_equipo=None,
                                  id_cable=None, id_conector_a=None,
                                  id_conector_b=None):
        """tipo: 'falla_equipo' | 'desconexion_cable' | 'conexion_virtual'."""
        Modelo.asegurar_tablas_escenario()
        with Modelo._conn_ctx() as conn:
            fila = conn.execute(
                "SELECT COALESCE(MAX(orden), -1) + 1 FROM escenario_cambio "
                "WHERE id_escenario=?", (id_escenario,)
            ).fetchone()
            siguiente_orden = fila[0]
            cur = conn.execute(
                "INSERT INTO escenario_cambio "
                "(id_escenario, tipo, id_equipo, id_cable, id_conector_a, "
                "id_conector_b, orden, fecha_ultima_edicion) VALUES "
                "(?,?,?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
                (id_escenario, tipo, _n(id_equipo), _n(id_cable),
                 _n(id_conector_a), _n(id_conector_b), siguiente_orden),
            )
            conn.execute(
                "UPDATE escenario SET "
                "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                "WHERE id_escenario=?", (id_escenario,)
            )
            conn.commit()
            return cur.lastrowid

    @staticmethod
    def eliminar_cambio_escenario(id_cambio):
        Modelo.asegurar_tablas_escenario()
        Modelo._exec(
            "DELETE FROM escenario_cambio WHERE id_cambio=?", (id_cambio,)
        )

    @staticmethod
    def eliminar_cambios_de_escenario(id_escenario):
        """Vacía todos los cambios de un escenario (usado por 'Descartar
        todo' en la UI, sin borrar el escenario en sí)."""
        Modelo.asegurar_tablas_escenario()
        Modelo._exec(
            "DELETE FROM escenario_cambio WHERE id_escenario=?", (id_escenario,)
        )

    # ── Bitácora de Incidentes + Armado + Zona Caliente (Entrega 1) ──────────
    # Ver plan_bitacora_incidentes_riesgo_analogico.md (especificación) y
    # plan_desarrollo_bitacora_incidentes.md (plan de desarrollo, Fase A/B).
    #
    # Decisión de Fase A sobre cascada de borrado en las tablas pivote
    # (incidente_equipo/incidente_cable/zona_equipo/incidente_zona):
    # ON DELETE CASCADE en AMBOS lados de cada pivote, pero a nivel de LA
    # FILA PIVOTE, no de la entidad dueña. Es decir: borrar un equipo borra
    # sus filas en incidente_equipo/zona_equipo (el vínculo), pero el
    # incidente y la zona siguen existiendo (con un equipo menos asociado).
    # Mismo criterio que problema_equipo, adaptado a que acá ninguna de las
    # dos puntas "posee" a la otra (a diferencia de problema_equipo, que sí
    # pertenece exclusivamente a un equipo).
    @staticmethod
    def asegurar_tablas_bitacora():
        """Crea/migra el esquema de la bitácora de incidentes, zonas
        sospechosas, armado de conectores/cables y configuración del score
        de riesgo analógico. Idempotente: seguro de llamar en cada arranque.
        """
        with Modelo._conn_ctx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS incidente ("
                "  id_incidente INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  fecha_hora   TEXT NOT NULL,"
                "  resumen      TEXT NOT NULL,"
                "  relato       TEXT,"
                "  estado       TEXT NOT NULL DEFAULT 'MITIGADO'"
                "               CHECK (estado IN ('RESUELTO','MITIGADO')),"
                "  fecha_creacion_registro TEXT NOT NULL "
                "               DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime')),"
                "  usuario_carga TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS incidente_equipo ("
                "  id_incidente INTEGER NOT NULL REFERENCES incidente(id_incidente) ON DELETE CASCADE,"
                "  id_equipo    INTEGER NOT NULL REFERENCES equipo(id_equipo)       ON DELETE CASCADE,"
                "  PRIMARY KEY (id_incidente, id_equipo)"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS incidente_cable ("
                "  id_incidente INTEGER NOT NULL REFERENCES incidente(id_incidente) ON DELETE CASCADE,"
                "  id_cable     INTEGER NOT NULL REFERENCES cable(id_cable)         ON DELETE CASCADE,"
                "  PRIMARY KEY (id_incidente, id_cable)"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS zona_sospechosa ("
                "  id_zona INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  nombre  TEXT NOT NULL UNIQUE"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS zona_equipo ("
                "  id_zona   INTEGER NOT NULL REFERENCES zona_sospechosa(id_zona) ON DELETE CASCADE,"
                "  id_equipo INTEGER NOT NULL REFERENCES equipo(id_equipo)        ON DELETE CASCADE,"
                "  PRIMARY KEY (id_zona, id_equipo)"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS incidente_zona ("
                "  id_incidente INTEGER NOT NULL REFERENCES incidente(id_incidente)   ON DELETE CASCADE,"
                "  id_zona      INTEGER NOT NULL REFERENCES zona_sospechosa(id_zona)  ON DELETE CASCADE,"
                "  PRIMARY KEY (id_incidente, id_zona)"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS config_riesgo_analogico ("
                "  clave TEXT PRIMARY KEY,"
                "  valor REAL NOT NULL"
                ")"
            )

            # Columnas de armado (conector y cable) — migración defensiva
            cols_con = [c[1] for c in conn.execute(
                "PRAGMA table_info(conector)").fetchall()]
            if "es_armado_correcto" not in cols_con:
                conn.execute(
                    "ALTER TABLE conector ADD COLUMN es_armado_correcto INTEGER")
            if "detalle_armado" not in cols_con:
                conn.execute(
                    "ALTER TABLE conector ADD COLUMN detalle_armado TEXT")

            cols_cab = [c[1] for c in conn.execute(
                "PRAGMA table_info(cable)").fetchall()]
            if "es_armado_correcto" not in cols_cab:
                conn.execute(
                    "ALTER TABLE cable ADD COLUMN es_armado_correcto INTEGER")
            if "detalle_armado" not in cols_cab:
                conn.execute("ALTER TABLE cable ADD COLUMN detalle_armado TEXT")

            # Armado POR EXTREMO (conexion) — descubierto en sesión
            # posterior: "Armado" a nivel cable completo no distingue cuál
            # de los dos extremos está mal armado (ej. XLR3 bien armado de
            # un lado, TRS mal armado del otro — caso real planteado por
            # el usuario). Mismo criterio ya usado con conexion.id_tipo_
            # ficha: cada fila de conexion sabe sin ambigüedad a qué
            # conector se conecta ese extremo, ahí es donde corresponde
            # el hallazgo. cable.es_armado_correcto se mantiene tal cual
            # (flag rápido para todo el cable, sin tener que abrir cada
            # conexión) — no se retira nada existente.
            cols_cx = [c[1] for c in conn.execute(
                "PRAGMA table_info(conexion)").fetchall()]
            if "es_armado_correcto" not in cols_cx:
                conn.execute(
                    "ALTER TABLE conexion ADD COLUMN es_armado_correcto INTEGER")
            if "detalle_armado" not in cols_cx:
                conn.execute("ALTER TABLE conexion ADD COLUMN detalle_armado TEXT")

            conn.commit()

        # Defaults del score de riesgo analógico (solo si no existen aún,
        # ver riesgo_analogico.py para el uso de cada clave)
        defaults = {
            "ventana_meses_incidentes": 12.0,
            "peso_incidente":            1.0,
            "peso_armado_incorrecto":    1.5,
            "corte_medio":               1.0,
            "corte_alto":                2.5,
        }
        existentes = {r[0] for r in Modelo._query(
            "SELECT clave FROM config_riesgo_analogico")}
        for clave, valor in defaults.items():
            if clave not in existentes:
                Modelo._exec(
                    "INSERT INTO config_riesgo_analogico (clave, valor) VALUES (?,?)",
                    (clave, valor),
                )

    # ── Incidentes: alta / consulta / edición / baja ──────────────────────────
    @staticmethod
    def crear_incidente(fecha_hora, resumen, relato=None, estado="MITIGADO",
                        ids_equipo=(), ids_cable=(), ids_zona=()):
        Modelo.asegurar_tablas_bitacora()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO incidente (fecha_hora, resumen, relato, estado) "
                "VALUES (?,?,?,?)",
                (fecha_hora, resumen, _n(relato), estado or "MITIGADO"),
            )
            id_incidente = cur.lastrowid
            for id_eq in ids_equipo:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_equipo (id_incidente, id_equipo) "
                    "VALUES (?,?)", (id_incidente, id_eq))
            for id_cb in ids_cable:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_cable (id_incidente, id_cable) "
                    "VALUES (?,?)", (id_incidente, id_cb))
            for id_zn in ids_zona:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_zona (id_incidente, id_zona) "
                    "VALUES (?,?)", (id_incidente, id_zn))
            conn.commit()
            return id_incidente

    @staticmethod
    def devolver_incidente(id_incidente):
        """Fila base del incidente, o None si no existe.
        Cols: id_incidente, fecha_hora, resumen, relato, estado,
        fecha_creacion_registro, usuario_carga."""
        Modelo.asegurar_tablas_bitacora()
        r = Modelo._query(
            "SELECT id_incidente, fecha_hora, resumen, relato, estado, "
            "fecha_creacion_registro, usuario_carga "
            "FROM incidente WHERE id_incidente=?", (id_incidente,))
        return r[0] if r else None

    @staticmethod
    def devolver_equipos_de_incidente(id_incidente):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT e.id_equipo, COALESCE(e.nombre,'') FROM incidente_equipo ie "
            "JOIN equipo e ON e.id_equipo = ie.id_equipo "
            "WHERE ie.id_incidente=? ORDER BY e.nombre", (id_incidente,))

    @staticmethod
    def devolver_cables_de_incidente(id_incidente):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT c.id_cable, COALESCE(c.codigo,'') FROM incidente_cable ic "
            "JOIN cable c ON c.id_cable = ic.id_cable "
            "WHERE ic.id_incidente=? ORDER BY c.codigo", (id_incidente,))

    @staticmethod
    def devolver_zonas_de_incidente(id_incidente):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT z.id_zona, z.nombre FROM incidente_zona iz "
            "JOIN zona_sospechosa z ON z.id_zona = iz.id_zona "
            "WHERE iz.id_incidente=? ORDER BY z.nombre", (id_incidente,))

    @staticmethod
    def devolver_todos_los_incidentes(filtro_texto=None, id_equipo=None,
                                      id_cable=None, id_zona=None,
                                      desde=None, hasta=None):
        """Lista de incidentes con filtros opcionales combinables.
        Cols: id_incidente, fecha_hora, resumen, estado."""
        Modelo.asegurar_tablas_bitacora()
        sql = (
            "SELECT DISTINCT i.id_incidente, i.fecha_hora, i.resumen, i.estado "
            "FROM incidente i "
            "LEFT JOIN incidente_equipo ie ON ie.id_incidente = i.id_incidente "
            "LEFT JOIN incidente_cable  ic ON ic.id_incidente = i.id_incidente "
            "LEFT JOIN incidente_zona   iz ON iz.id_incidente = i.id_incidente "
            "WHERE 1=1"
        )
        params = []
        if filtro_texto:
            sql += " AND (i.resumen LIKE ? OR i.relato LIKE ?)"
            params += [f"%{filtro_texto}%", f"%{filtro_texto}%"]
        if id_equipo:
            sql += " AND ie.id_equipo = ?"
            params.append(id_equipo)
        if id_cable:
            sql += " AND ic.id_cable = ?"
            params.append(id_cable)
        if id_zona:
            sql += " AND iz.id_zona = ?"
            params.append(id_zona)
        if desde:
            sql += " AND i.fecha_hora >= ?"
            params.append(desde)
        if hasta:
            sql += " AND i.fecha_hora <= ?"
            params.append(hasta)
        sql += " ORDER BY i.fecha_hora DESC"
        return Modelo._query(sql, tuple(params))

    @staticmethod
    def modificar_incidente(id_incidente, fecha_hora, resumen, relato=None,
                            estado="MITIGADO", ids_equipo=(), ids_cable=(),
                            ids_zona=()):
        """Actualiza los datos del incidente y REEMPLAZA por completo sus
        vínculos a equipos/cables/zonas por los conjuntos dados."""
        Modelo.asegurar_tablas_bitacora()
        with Modelo._conn_ctx() as conn:
            conn.execute(
                "UPDATE incidente SET fecha_hora=?, resumen=?, relato=?, estado=? "
                "WHERE id_incidente=?",
                (fecha_hora, resumen, _n(relato), estado or "MITIGADO", id_incidente),
            )
            conn.execute(
                "DELETE FROM incidente_equipo WHERE id_incidente=?", (id_incidente,))
            conn.execute(
                "DELETE FROM incidente_cable WHERE id_incidente=?", (id_incidente,))
            conn.execute(
                "DELETE FROM incidente_zona WHERE id_incidente=?", (id_incidente,))
            for id_eq in ids_equipo:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_equipo (id_incidente, id_equipo) "
                    "VALUES (?,?)", (id_incidente, id_eq))
            for id_cb in ids_cable:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_cable (id_incidente, id_cable) "
                    "VALUES (?,?)", (id_incidente, id_cb))
            for id_zn in ids_zona:
                conn.execute(
                    "INSERT OR IGNORE INTO incidente_zona (id_incidente, id_zona) "
                    "VALUES (?,?)", (id_incidente, id_zn))
            conn.commit()

    @staticmethod
    def eliminar_incidente(id_incidente):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec("DELETE FROM incidente WHERE id_incidente=?", (id_incidente,))

    # ── Zonas sospechosas (conjunto reutilizable de equipos) ──────────────────
    @staticmethod
    def crear_zona_sospechosa(nombre, ids_equipo=()):
        Modelo.asegurar_tablas_bitacora()
        with Modelo._conn_ctx() as conn:
            cur = conn.execute(
                "INSERT INTO zona_sospechosa (nombre) VALUES (?)", (nombre,))
            id_zona = cur.lastrowid
            for id_eq in ids_equipo:
                conn.execute(
                    "INSERT OR IGNORE INTO zona_equipo (id_zona, id_equipo) "
                    "VALUES (?,?)", (id_zona, id_eq))
            conn.commit()
            return id_zona

    @staticmethod
    def devolver_zonas():
        """Cols: id_zona, nombre, cantidad_equipos."""
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT z.id_zona, z.nombre, COUNT(ze.id_equipo) "
            "FROM zona_sospechosa z "
            "LEFT JOIN zona_equipo ze ON ze.id_zona = z.id_zona "
            "GROUP BY z.id_zona ORDER BY z.nombre"
        )

    @staticmethod
    def devolver_zona(id_zona):
        Modelo.asegurar_tablas_bitacora()
        r = Modelo._query(
            "SELECT id_zona, nombre FROM zona_sospechosa WHERE id_zona=?",
            (id_zona,))
        return r[0] if r else None

    @staticmethod
    def devolver_equipos_de_zona(id_zona):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT e.id_equipo, COALESCE(e.nombre,'') FROM zona_equipo ze "
            "JOIN equipo e ON e.id_equipo = ze.id_equipo "
            "WHERE ze.id_zona=? ORDER BY e.nombre", (id_zona,))

    @staticmethod
    def asignar_equipo_a_zona(id_zona, id_equipo):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec(
            "INSERT OR IGNORE INTO zona_equipo (id_zona, id_equipo) VALUES (?,?)",
            (id_zona, id_equipo))

    @staticmethod
    def quitar_equipo_de_zona(id_zona, id_equipo):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec(
            "DELETE FROM zona_equipo WHERE id_zona=? AND id_equipo=?",
            (id_zona, id_equipo))

    @staticmethod
    def renombrar_zona_sospechosa(id_zona, nombre):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec(
            "UPDATE zona_sospechosa SET nombre=? WHERE id_zona=?",
            (nombre, id_zona))

    @staticmethod
    def eliminar_zona(id_zona):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec("DELETE FROM zona_sospechosa WHERE id_zona=?", (id_zona,))

    # ── Armado de conectores y cables ("mal armado") ───────────────────────────
    @staticmethod
    def establecer_armado_conector(id_conector, es_correcto, detalle=None):
        """es_correcto: None (no verificado) | True/1 (correcto) | False/0 (mal armado)."""
        Modelo.asegurar_tablas_bitacora()
        valor = None if es_correcto is None else (1 if es_correcto else 0)
        Modelo._exec(
            "UPDATE conector SET es_armado_correcto=?, detalle_armado=? "
            "WHERE id_conector=?",
            (valor, _n(detalle), id_conector))

    @staticmethod
    def establecer_armado_cable(id_cable, es_correcto, detalle=None):
        Modelo.asegurar_tablas_bitacora()
        valor = None if es_correcto is None else (1 if es_correcto else 0)
        Modelo._exec(
            "UPDATE cable SET es_armado_correcto=?, detalle_armado=? "
            "WHERE id_cable=?",
            (valor, _n(detalle), id_cable))

    @staticmethod
    def devolver_conectores_mal_armados():
        """Cols: id_conector, id_equipo, nombre_conector, detalle_armado."""
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT id_conector, id_equipo, COALESCE(nombre,''), "
            "COALESCE(detalle_armado,'') "
            "FROM conector WHERE es_armado_correcto = 0"
        )

    @staticmethod
    def devolver_cables_mal_armados():
        """Cols: id_cable, codigo, detalle_armado."""
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT id_cable, COALESCE(codigo,''), COALESCE(detalle_armado,'') "
            "FROM cable WHERE es_armado_correcto = 0"
        )

    # ── Armado POR EXTREMO del cable (conexion) ─────────────────────────────
    @staticmethod
    def establecer_armado_conexion(id_conexion, es_correcto, detalle=None):
        """es_correcto: None (no verificado) | True/1 (correcto) | False/0
        (mal armado). Distinto de establecer_armado_cable: esto es sobre
        UNA punta específica del cable (la que llega a id_conexion), no
        sobre el cable entero."""
        Modelo.asegurar_tablas_bitacora()
        valor = None if es_correcto is None else (1 if es_correcto else 0)
        Modelo._exec(
            "UPDATE conexion SET es_armado_correcto=?, detalle_armado=? "
            "WHERE id_conexion=?",
            (valor, _n(detalle), id_conexion))

    @staticmethod
    def devolver_armado_conexion(id_conexion):
        """(es_armado_correcto, detalle_armado) o (None, None) si no existe."""
        Modelo.asegurar_tablas_bitacora()
        rows = Modelo._query(
            "SELECT es_armado_correcto, detalle_armado FROM conexion "
            "WHERE id_conexion=?", (id_conexion,))
        return (rows[0][0], rows[0][1]) if rows else (None, None)

    @staticmethod
    def devolver_conexiones_mal_armadas():
        """Cols: id_conexion, id_cable, codigo_cable, id_conector,
        nombre_conector, detalle_armado — para riesgo_analogico.py y para
        listar en la UI."""
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT cx.id_conexion, cx.id_cable, COALESCE(c.codigo,''), "
            "cx.id_conector, COALESCE(co.nombre,''), COALESCE(cx.detalle_armado,'') "
            "FROM conexion cx "
            "JOIN cable c ON c.id_cable = cx.id_cable "
            "LEFT JOIN conector co ON co.id_conector = cx.id_conector "
            "WHERE cx.es_armado_correcto = 0"
        )

    # ── Consultas combinadas (incidentes de un equipo/cable/zona) ─────────────
    @staticmethod
    def incidentes_de_equipo(id_equipo, incluir_via_zona=True):
        """Incidentes que mencionan al equipo directamente, y opcionalmente
        también los cargados contra una zona a la que el equipo pertenece.
        Cols: id_incidente, fecha_hora, resumen, estado."""
        Modelo.asegurar_tablas_bitacora()
        sql = (
            "SELECT DISTINCT i.id_incidente, i.fecha_hora, i.resumen, i.estado "
            "FROM incidente i "
            "JOIN incidente_equipo ie ON ie.id_incidente = i.id_incidente "
            "WHERE ie.id_equipo = ?"
        )
        if incluir_via_zona:
            sql = (
                "SELECT DISTINCT i.id_incidente, i.fecha_hora, i.resumen, i.estado "
                "FROM incidente i "
                "WHERE i.id_incidente IN ("
                "  SELECT id_incidente FROM incidente_equipo WHERE id_equipo=?"
                "  UNION "
                "  SELECT iz.id_incidente FROM incidente_zona iz "
                "  JOIN zona_equipo ze ON ze.id_zona = iz.id_zona "
                "  WHERE ze.id_equipo=?"
                ")"
            )
            return Modelo._query(sql + " ORDER BY i.fecha_hora DESC",
                                 (id_equipo, id_equipo))
        return Modelo._query(sql + " ORDER BY i.fecha_hora DESC", (id_equipo,))

    @staticmethod
    def incidentes_de_cable(id_cable):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT i.id_incidente, i.fecha_hora, i.resumen, i.estado "
            "FROM incidente i "
            "JOIN incidente_cable ic ON ic.id_incidente = i.id_incidente "
            "WHERE ic.id_cable=? ORDER BY i.fecha_hora DESC", (id_cable,))

    @staticmethod
    def incidentes_de_zona(id_zona):
        Modelo.asegurar_tablas_bitacora()
        return Modelo._query(
            "SELECT i.id_incidente, i.fecha_hora, i.resumen, i.estado "
            "FROM incidente i "
            "JOIN incidente_zona iz ON iz.id_incidente = i.id_incidente "
            "WHERE iz.id_zona=? ORDER BY i.fecha_hora DESC", (id_zona,))

    # ── Configuración del score de riesgo analógico ────────────────────────────
    @staticmethod
    def devolver_config_riesgo_analogico():
        """dict {clave: valor} — ver defaults en asegurar_tablas_bitacora()."""
        Modelo.asegurar_tablas_bitacora()
        return {r[0]: r[1] for r in Modelo._query(
            "SELECT clave, valor FROM config_riesgo_analogico")}

    @staticmethod
    def establecer_config_riesgo_analogico(clave, valor):
        Modelo.asegurar_tablas_bitacora()
        Modelo._exec(
            "INSERT INTO config_riesgo_analogico (clave, valor) VALUES (?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, valor))

    # ═════════════════════════════════════════════════════════════════════════
    # Extensiones de cable (plan_desarrollo_extension_cable.md)
    # ═════════════════════════════════════════════════════════════════════════
    # Fase 1 (schema/modelo) + Fase 4 (armado/riesgo) del plan. Fase 2 (UI) en
    # extension_cable_ui.py, Fase 3 (propagación/diagrama) queda pendiente —
    # requiere tocar senal_propagation.py / graph_impact.py / pantallas_
    # avanzadas.py, fuera de alcance de esta entrega.
    #
    # Nota de schema: conexion.id_conector YA es NULLABLE en schema_db.sql
    # (sin NOT NULL) — no hizo falta ALTER. Lo que faltaba era el lugar
    # donde cargar el punto intermedio (esta tabla) y el criterio de uso:
    # un extremo "suelto" es una fila de conexion con id_conector IS NULL;
    # Modelo.alta_conexion ya acepta id_conector=None sin cambios (ver _n).
    # Se auditaron los callsites de "id_conector" en modelo.py y cabledoc.py:
    # todos los que importan (fuera de pantallas_avanzadas.py, no auditado
    # acá) usan comparación explícita "is not None" / "is None", no el
    # patrón truthy "if id_conector:" que reintroduciría el bug del
    # sentinel id_conector=0 — no se encontró riesgo en el código auditado.

    @staticmethod
    def asegurar_tablas_extension_cable():
        """Tabla extension_cable: dos extremos sueltos de cable (conexion
        con id_conector NULL) empalmados ficha contra ficha, sin equipo ni
        barril de por medio — ver plan_desarrollo_extension_cable.md §3.1.
        Cardinalidad 1 a 1 (UNIQUE en cada extremo). Idempotente: seguro de
        llamar en cada arranque."""
        with Modelo._conn_ctx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS extension_cable ("
                "  id_extension INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  id_conexion_a INTEGER NOT NULL,"
                "  id_conexion_b INTEGER NOT NULL,"
                "  id_rack INTEGER,"
                "  id_sala INTEGER,"
                "  posicion_libre TEXT,"
                "  es_armado_correcto INTEGER,"
                "  detalle_armado TEXT,"
                "  fecha_ultima_edicion TEXT,"
                "  ultima_auditoria_fecha TEXT,"
                "  FOREIGN KEY(id_conexion_a) REFERENCES conexion(id_conexion) ON DELETE CASCADE,"
                "  FOREIGN KEY(id_conexion_b) REFERENCES conexion(id_conexion) ON DELETE CASCADE,"
                "  FOREIGN KEY(id_rack) REFERENCES rack(id_rack) ON DELETE SET NULL,"
                "  FOREIGN KEY(id_sala) REFERENCES sala(id_sala) ON DELETE SET NULL,"
                "  UNIQUE(id_conexion_a),"
                "  UNIQUE(id_conexion_b)"
                ")"
            )
            conn.commit()

    @staticmethod
    def crear_extremo_suelto(id_cable, id_tipo_ficha=None):
        """Da de alta una conexion con id_conector=NULL (extremo suelto)
        para un cable, lista para usarse en una extensión. Reusa
        alta_conexion (ya soporta id_conector=None) + establecer_ficha_
        conexion para dejar identificada la ficha física de esa punta."""
        Modelo.asegurar_tablas_extension_cable()
        Modelo.alta_conexion(id_cable, None)
        rows = Modelo._query(
            "SELECT id_conexion FROM conexion WHERE id_cable=? "
            "AND id_conector IS NULL ORDER BY id_conexion DESC LIMIT 1",
            (id_cable,))
        id_conexion = rows[0][0] if rows else None
        if id_conexion and id_tipo_ficha:
            Modelo.establecer_ficha_conexion(id_conexion, id_tipo_ficha)
        return id_conexion

    @staticmethod
    def devolver_conexiones_sueltas(id_cable=None, excluir_id_extension=None):
        """Extremos de cable sin conector (id_conector IS NULL) que todavía
        no están usados en ninguna otra extensión — candidatos para armar
        una extensión nueva (o para completar una en edición, si se pasa
        excluir_id_extension con el id de la extensión actual, cuyos
        propios extremos deben seguir apareciendo como disponibles).
        Cols: id_conexion, id_cable, codigo_cable, id_tipo_ficha,
        nombre_tipo_ficha."""
        Modelo.asegurar_tablas_extension_cable()
        sql = (
            "SELECT cx.id_conexion, cx.id_cable, COALESCE(c.codigo,''), "
            "cx.id_tipo_ficha, COALESCE(tf.nombre,'') "
            "FROM conexion cx "
            "JOIN cable c ON c.id_cable = cx.id_cable "
            "LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = cx.id_tipo_ficha "
            "WHERE cx.id_conector IS NULL "
            "AND cx.id_conexion NOT IN ("
            "  SELECT id_conexion_a FROM extension_cable "
            "  WHERE (? IS NULL OR id_extension <> ?) "
            "  UNION "
            "  SELECT id_conexion_b FROM extension_cable "
            "  WHERE (? IS NULL OR id_extension <> ?)"
            ")"
        )
        params = [excluir_id_extension, excluir_id_extension,
                  excluir_id_extension, excluir_id_extension]
        if id_cable:
            sql += " AND cx.id_cable = ?"
            params.append(id_cable)
        sql += " ORDER BY c.codigo"
        return Modelo._query(sql, tuple(params))

    @staticmethod
    def devolver_extension(id_extension):
        """Cols: id_extension, id_conexion_a, id_conexion_b, id_rack,
        id_sala, posicion_libre, es_armado_correcto, detalle_armado."""
        Modelo.asegurar_tablas_extension_cable()
        return Modelo._query(
            "SELECT id_extension, id_conexion_a, id_conexion_b, id_rack, "
            "id_sala, posicion_libre, es_armado_correcto, detalle_armado "
            "FROM extension_cable WHERE id_extension=?", (id_extension,))

    @staticmethod
    def devolver_extension_de_conexion(id_conexion):
        """id_extension que usa esta conexion como extremo A o B, o None si
        la conexion no participa de ninguna extensión."""
        Modelo.asegurar_tablas_extension_cable()
        rows = Modelo._query(
            "SELECT id_extension FROM extension_cable "
            "WHERE id_conexion_a=? OR id_conexion_b=?",
            (id_conexion, id_conexion))
        return rows[0][0] if rows else None

    @staticmethod
    def listar_extensiones():
        """Catálogo general (Catálogos → 'Extensiones de cable'). Cols:
        id_extension, codigo_cable_a, codigo_cable_b, nombre_rack,
        nombre_sala, posicion_libre, es_armado_correcto."""
        Modelo.asegurar_tablas_extension_cable()
        return Modelo._query(
            "SELECT e.id_extension, ca.codigo, cb.codigo, "
            "COALESCE(r.nombre,''), COALESCE(sl.nombre,''), "
            "COALESCE(e.posicion_libre,''), e.es_armado_correcto "
            "FROM extension_cable e "
            "JOIN conexion xa ON xa.id_conexion = e.id_conexion_a "
            "JOIN conexion xb ON xb.id_conexion = e.id_conexion_b "
            "JOIN cable ca ON ca.id_cable = xa.id_cable "
            "JOIN cable cb ON cb.id_cable = xb.id_cable "
            "LEFT JOIN rack r ON r.id_rack = e.id_rack "
            "LEFT JOIN sala sl ON sl.id_sala = e.id_sala "
            "ORDER BY ca.codigo"
        )

    @staticmethod
    def crear_extension(id_conexion_a, id_conexion_b, id_rack=None,
                        id_sala=None, posicion_libre=None):
        Modelo.asegurar_tablas_extension_cable()
        Modelo._exec(
            "INSERT INTO extension_cable "
            "(id_conexion_a, id_conexion_b, id_rack, id_sala, "
            " posicion_libre, fecha_ultima_edicion) "
            "VALUES (?,?,?,?,?, STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime'))",
            (id_conexion_a, id_conexion_b, _n(id_rack), _n(id_sala),
             _n(posicion_libre)))

    @staticmethod
    def editar_extension(id_extension, id_rack=None, id_sala=None,
                         posicion_libre=None):
        """No reasigna los extremos (id_conexion_a/b): para cambiar de
        cable conviene eliminar la extensión y crear una nueva, así no
        quedan conexiones sueltas a medio migrar."""
        Modelo.asegurar_tablas_extension_cable()
        Modelo._exec(
            "UPDATE extension_cable SET id_rack=?, id_sala=?, "
            "posicion_libre=?, "
            "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
            "WHERE id_extension=?",
            (_n(id_rack), _n(id_sala), _n(posicion_libre), id_extension))

    @staticmethod
    def eliminar_extension(id_extension):
        """Solo borra el registro de extensión; las dos conexion (extremos
        sueltos) quedan intactas — vuelven a aparecer como disponibles en
        devolver_conexiones_sueltas() para una extensión nueva."""
        Modelo._exec(
            "DELETE FROM extension_cable WHERE id_extension=?", (id_extension,))

    @staticmethod
    def establecer_armado_extension(id_extension, es_correcto, detalle=None):
        """Mismo mecanismo que establecer_armado_cable/_conexion — la
        extensión es su propio punto de falla (plan_desarrollo_extension_
        cable.md §2: 'una extensión mal armada suma su propio peso al
        score, no se limita a heredar el peso del equipo aguas abajo')."""
        Modelo.asegurar_tablas_extension_cable()
        valor = None if es_correcto is None else (1 if es_correcto else 0)
        Modelo._exec(
            "UPDATE extension_cable SET es_armado_correcto=?, detalle_armado=? "
            "WHERE id_extension=?",
            (valor, _n(detalle), id_extension))

    @staticmethod
    def resolver_cadena_extension(id_cable):
        """Camina la cadena completa de extensiones a partir de un cable,
        en ambos sentidos, hasta llegar a un conector real de equipo (o
        a una punta suelta sin extensión, si la cadena está incompleta).

        Ajuste de usabilidad post-uso real (plan_desarrollo_extension_
        cable.md — Papi reportó no poder seguir "qué está uniendo con
        qué" al armar extensiones en varios pasos): resuelve el
        recorrido real equipo→cable→extensión→cable→...→equipo entero,
        para que 'Ver cadena completa' (extension_cable_ui.py) lo pueda
        mostrar de una sola vez sin que el usuario tenga que
        reconstruirlo mentalmente a partir de fichas sueltas.

        Devuelve una lista ORDENADA de eslabones (dict), alternando
        terminal/cable/extension, del extremo real de un lado al extremo
        real del otro lado:
          {"tipo": "equipo", "equipo": str, "conector": str}
          {"tipo": "cable", "id_cable": int, "codigo": str, "foco": bool}
          {"tipo": "extension", "id_extension": int,
           "posicion": str|None, "armado": int|None}
          {"tipo": "suelto"}  — punta sin conector real ni extensión
                                 (cadena incompleta de ese lado)
          {"tipo": "ciclo"}   — protección ante referencia circular
        "foco" marca el cable de partida (id_cable), para resaltarlo en
        la UI. Devuelve [] si el cable no tiene conexiones cargadas."""
        Modelo.asegurar_tablas_extension_cable()

        def _terminal(id_conexion):
            rows = Modelo._query(
                "SELECT equipo_nombre, conector_nombre FROM CONEXIONES "
                "WHERE id_conexion=?", (id_conexion,))
            if rows and rows[0][0]:
                return {"tipo": "equipo", "equipo": rows[0][0],
                        "conector": rows[0][1]}
            return None

        def _extension_de(id_conexion):
            rows = Modelo._query(
                "SELECT id_extension, id_conexion_a, id_conexion_b, "
                "posicion_libre, es_armado_correcto FROM extension_cable "
                "WHERE id_conexion_a=? OR id_conexion_b=?",
                (id_conexion, id_conexion))
            return rows[0] if rows else None

        def _seguir(id_conexion_inicio, visitados_cable):
            eslabones = []
            cx_actual = id_conexion_inicio
            while True:
                fila = Modelo._query(
                    "SELECT id_conector FROM conexion WHERE id_conexion=?",
                    (cx_actual,))
                id_conector = fila[0][0] if fila else None
                if id_conector:
                    eslabones.append(_terminal(cx_actual) or {"tipo": "suelto"})
                    break
                ext = _extension_de(cx_actual)
                if not ext:
                    eslabones.append({"tipo": "suelto"})
                    break
                id_ext, id_cx_a, id_cx_b, posicion, armado = ext
                otro = id_cx_b if str(id_cx_a) == str(cx_actual) else id_cx_a
                eslabones.append({"tipo": "extension", "id_extension": id_ext,
                                  "posicion": posicion, "armado": armado})
                fila2 = Modelo._query(
                    "SELECT id_cable FROM conexion WHERE id_conexion=?", (otro,))
                id_cable_sig = fila2[0][0] if fila2 else None
                if not id_cable_sig or id_cable_sig in visitados_cable:
                    eslabones.append({"tipo": "ciclo"})
                    break
                visitados_cable.add(id_cable_sig)
                cod = Modelo._query(
                    "SELECT codigo FROM cable WHERE id_cable=?", (id_cable_sig,))
                eslabones.append({"tipo": "cable", "id_cable": id_cable_sig,
                                  "codigo": cod[0][0] if cod else "",
                                  "foco": False})
                extremos = Modelo._query(
                    "SELECT id_conexion FROM conexion WHERE id_cable=? "
                    "ORDER BY id_conexion", (id_cable_sig,))
                candidatos = [r[0] for r in extremos if str(r[0]) != str(otro)]
                if not candidatos:
                    eslabones.append({"tipo": "suelto"})
                    break
                cx_actual = candidatos[0]
            return eslabones

        extremos_inicial = Modelo._query(
            "SELECT id_conexion FROM conexion WHERE id_cable=? "
            "ORDER BY id_conexion", (id_cable,))
        if not extremos_inicial:
            return []
        cx_a = extremos_inicial[0][0]
        cx_b = extremos_inicial[1][0] if len(extremos_inicial) > 1 else None

        lado_izq = _seguir(cx_a, {id_cable}) if cx_a else []
        lado_der = _seguir(cx_b, {id_cable}) if cx_b else []

        cod_inicial = Modelo._query(
            "SELECT codigo FROM cable WHERE id_cable=?", (id_cable,))
        cable_foco = {"tipo": "cable", "id_cable": id_cable,
                     "codigo": cod_inicial[0][0] if cod_inicial else "",
                     "foco": True}

        return list(reversed(lado_izq)) + [cable_foco] + lado_der

    @staticmethod
    def devolver_extensiones_mal_armadas():
        """Cols: id_extension, id_cable_a, codigo_a, id_cable_b, codigo_b,
        detalle_armado — mismo patrón que devolver_conexiones_mal_armadas,
        consumido por riesgo_analogico.py (Fase 4 del plan)."""
        Modelo.asegurar_tablas_extension_cable()
        return Modelo._query(
            "SELECT e.id_extension, xa.id_cable, COALESCE(ca.codigo,''), "
            "xb.id_cable, COALESCE(cb.codigo,''), COALESCE(e.detalle_armado,'') "
            "FROM extension_cable e "
            "JOIN conexion xa ON xa.id_conexion = e.id_conexion_a "
            "JOIN conexion xb ON xb.id_conexion = e.id_conexion_b "
            "JOIN cable ca ON ca.id_cable = xa.id_cable "
            "JOIN cable cb ON cb.id_cable = xb.id_cable "
            "WHERE e.es_armado_correcto = 0"
        )

