"""
CableDoc - Capa de acceso a datos (modelo.py)
Equivalente Python de Modelo.vb (VB.NET/SQLite)
Usa parámetros en las consultas para evitar inyección SQL.
"""

import re
import sqlite3
import os

from logger_cabledoc import log_error

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "db.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagen")
MANUALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manuales")
PICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picon")

# Asegurar que los directorios existan
os.makedirs(MANUALES_DIR, exist_ok=True)
os.makedirs(PICON_DIR, exist_ok=True)


def _n(val):
    """Convierte cadena vacía a None (NULL en SQLite)."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s == "" else s


class DimensionesImagenError(Exception):
    """Se levanta cuando no se pueden determinar el ancho/alto (px) de una
    imagen — necesarios para convertir entre coordenadas en píxeles y en
    porcentaje (ver Modelo._dimensiones_imagen). Misma excepción/mismo rol
    que en core/modelo.py (desktop): a propósito NO hereda de ValueError
    genérico, para poder distinguirla y mostrarla tal cual al usuario."""


class Modelo:
    # ── Coordenadas en imagen: píxeles ↔ porcentaje (SIN columnas nuevas) ───
    #
    # Mismo contrato que core/modelo.py (desktop): las columnas existentes
    # coordenada_x_en_imagen/coordenada_y_en_imagen (conector, equipo) y
    # rectangulo_x_en_imagen/rectangulo_y_en_imagen/rectangulo_ancho_pixeles/
    # rectangulo_alto_pixeles (slot) guardan un ENTERO de 0 a 100 (porcentaje
    # del ancho/alto de la imagen) — es la MISMA base SQLite que sincroniza
    # con el desktop (rclone/RoundSync), así que el significado del valor
    # guardado tiene que ser idéntico en los dos lados o los puntos quedan
    # mal ubicados sin ningún aviso. El resto de las pantallas de mobile
    # sigue trabajando en PÍXELES como siempre — la conversión es invisible
    # fuera de este archivo, igual que en desktop.
    #
    # Única diferencia real con desktop: acá no hay gi/GdkPixbuf/Rsvg
    # (bindings de GTK, no existen en Android/Pydroid), así que
    # _dimensiones_imagen() usa kivy.core.image.Image para rasters
    # (PNG/JPG/GIF/BMP/...) y el mismo truco de leer el viewBox a mano para
    # SVG (Kivy no rasteriza SVG nativamente; esto sólo resuelve el
    # ancho/alto para la conversión de coordenadas, no el renderizado del
    # SVG en sí — ver Fase 3.3 del plan para eso).

    _CACHE_DIMENSIONES_IMAGEN = {}

    @staticmethod
    def _svg_viewbox_size(full_path):
        """Último recurso para el tamaño intrínseco de un SVG que sólo
        declara viewBox y deja width/height en '100%' o los omite. Lee el
        viewBox directo del XML — no depende de ninguna librería de
        renderizado SVG (ni gi/Rsvg del desktop, ni nada en Kivy, que no
        soporta SVG nativamente). Copia textual del homónimo en
        core/modelo.py — se duplica a propósito porque mobile no puede
        importar de core/ (entornos y dependencias distintas)."""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                encabezado = f.read(4096)
            m = re.search(r'viewBox\s*=\s*["\']([^"\']+)["\']', encabezado)
            if m:
                partes = m.group(1).replace(",", " ").split()
                if len(partes) == 4:
                    ancho, alto = float(partes[2]), float(partes[3])
                    if ancho > 0 and alto > 0:
                        return ancho, alto
        except Exception:
            pass
        return None

    @staticmethod
    def _dimensiones_imagen(path_archivo):
        """Devuelve (ancho_px, alto_px) de la imagen ubicada en IMG_DIR
        bajo el nombre `path_archivo`. Rasters (PNG/JPG/GIF/BMP/...) vía
        kivy.core.image.Image (sin necesidad de una ventana/contexto GL
        real para sólo leer el tamaño); SVG vía el viewBox leído a mano
        (Kivy no lo soporta nativamente).

        Cachea por (path_archivo, mtime), igual que el desktop, para no
        releer el archivo del disco en cada conversión.

        Levanta DimensionesImagenError si el archivo no existe, no se
        puede leer, o no se pudo determinar su tamaño."""
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
            if es_svg:
                tam = Modelo._svg_viewbox_size(full_path)
                if not tam:
                    raise DimensionesImagenError(
                        f"No se pudo leer el viewBox de {path_archivo!r} "
                        "(SVG sin viewBox declarado o no parseable).")
                ancho, alto = tam
            else:
                # Import diferido (mismo patrón que el `import gi` de
                # core/modelo.py): así este módulo se puede importar en
                # scripts/tests que no corren dentro de una app Kivy real
                # sin que falle acá arriba.
                from kivy.core.image import Image as CoreImage
                imagen = CoreImage(full_path)
                ancho, alto = imagen.size
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
        punto cae fuera de la imagen). None si valor_px es None."""
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
        ancho_img, alto_img = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._px_a_pct(x_px, ancho_img),
                Modelo._px_a_pct(y_px, alto_img),
                Modelo._px_a_pct(ancho_px, ancho_img),
                Modelo._px_a_pct(alto_px, alto_img))

    @staticmethod
    def _rect_pct_a_px(path_archivo, x_pct, y_pct, ancho_pct, alto_pct):
        ancho_img, alto_img = Modelo._dimensiones_imagen(path_archivo)
        return (Modelo._pct_a_px(x_pct, ancho_img),
                Modelo._pct_a_px(y_pct, alto_img),
                Modelo._pct_a_px(ancho_pct, ancho_img),
                Modelo._pct_a_px(alto_pct, alto_img))

    @staticmethod
    def _pct_punto_o_none(path_archivo, x_px, y_px):
        """Wrapper de _punto_px_a_pct que nunca levanta: si no se pueden
        determinar las dimensiones de la imagen (falta el archivo, sin
        id_imagen, etc.) devuelve (None, None) en vez de interrumpir el
        alta/edición — se guarda NULL y se puede completar después."""
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
        convertir (imagen no disponible en este momento) devuelve el valor
        CRUDO tal cual está guardado, en vez de None — así una pantalla
        que sólo lee sigue mostrando *algo* razonable en vez de perder el
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
    def _path_imagen(id_imagen):
        """path_archivo de la fila `imagen` con ese id, o None."""
        if not id_imagen:
            return None
        r = Modelo._query(
            "SELECT path_archivo FROM imagen WHERE id_imagen=?", (id_imagen,))
        return r[0][0] if r else None

    @staticmethod
    def _conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _query(sql, params=()):
        try:
            with Modelo._conn() as conn:
                cur = conn.execute(sql, params)
                return [list(row) for row in cur.fetchall()]
        except Exception as e:
            log_error(f"Modelo._query: {sql[:120]}", e)
            raise

    @staticmethod
    def _exec(sql, params=()):
        try:
            with Modelo._conn() as conn:
                conn.execute(sql, params)
                conn.commit()
        except Exception as e:
            log_error(f"Modelo._exec: {sql[:120]}", e)
            raise

    # ── Equipos ──────────────────────────────────────────────────────────────
    @staticmethod
    def asegurar_columnas_equipo():
        """Asegura que las columnas path_manual y configuraciones existan en la tabla equipo."""
        with Modelo._conn() as conn:
            # Verificar si path_manual existe
            cursor = conn.execute("PRAGMA table_info(equipo)")
            columnas = [col[1] for col in cursor.fetchall()]
            
            if "path_manual" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN path_manual TEXT")
            
            if "configuraciones" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN configuraciones TEXT")

            if "picon" not in columnas:
                conn.execute("ALTER TABLE equipo ADD COLUMN picon TEXT")

            conn.commit()

    # ── Auditoría (ultima_auditoria_fecha) ──────────────────────────────────
    # Tablas "importantes" sobre las que se puede confirmar que el estado
    # observado en terreno es válido (equipo, conector, conexión, cable,
    # rack, frame, slot). El dict es una whitelist: tabla -> columna PK.
    TABLAS_AUDITABLES = {
        "equipo":   "id_equipo",
        "conector": "id_conector",
        "conexion": "id_conexion",
        "cable":    "id_cable",
        "rack":     "id_rack",
        "frame":    "id_frame",
        "slot":     "id_slot",
    }

    @staticmethod
    def asegurar_columnas_auditoria():
        """Agrega la columna ultima_auditoria_fecha a todas las tablas
        auditables que todavía no la tengan (idempotente, se llama al
        arrancar la app)."""
        with Modelo._conn() as conn:
            for tabla in Modelo.TABLAS_AUDITABLES:
                cursor = conn.execute(f"PRAGMA table_info({tabla})")
                columnas = [col[1] for col in cursor.fetchall()]
                if "ultima_auditoria_fecha" not in columnas:
                    conn.execute(
                        f"ALTER TABLE {tabla} ADD COLUMN ultima_auditoria_fecha TEXT")
            conn.commit()

    @staticmethod
    def marcar_auditado(tabla, pk_col, pk_val):
        """Confirma que el estado observado de un registro es válido ahora
        mismo: graba la fecha/hora actual en ultima_auditoria_fecha."""
        if tabla not in Modelo.TABLAS_AUDITABLES:
            raise ValueError(f"Tabla no auditable: {tabla}")
        import datetime
        ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        Modelo._exec(
            f"UPDATE {tabla} SET ultima_auditoria_fecha=? WHERE {pk_col}=?",
            (ahora, pk_val))
        return ahora

    @staticmethod
    def devolver_fecha_ultima_auditoria(tabla, pk_col, pk_val):
        if not pk_val or tabla not in Modelo.TABLAS_AUDITABLES:
            return ""
        rows = Modelo._query(
            f"SELECT ultima_auditoria_fecha FROM {tabla} WHERE {pk_col}=?",
            (pk_val,))
        return rows[0][0] if rows and rows[0][0] else ""

    @staticmethod
    def marcar_auditadas_conexiones_de_equipo(id_equipo, fecha=None):
        """Marca como auditadas (misma fecha) todas las conexiones cuyo
        conector pertenece al equipo dado. Devuelve (fecha, cantidad)."""
        import datetime
        fecha = fecha or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Modelo._conn() as conn:
            cur = conn.execute(
                "UPDATE conexion SET ultima_auditoria_fecha=? "
                "WHERE id_conector IN "
                "(SELECT id_conector FROM conector WHERE id_equipo=?)",
                (fecha, id_equipo))
            conn.commit()
            cantidad = cur.rowcount
        return fecha, cantidad

    @staticmethod
    def devolver_pendientes_auditoria():
        """Cantidad de registros nunca auditados, por tabla auditable."""
        resultado = {}
        for tabla in Modelo.TABLAS_AUDITABLES:
            try:
                filtro = " WHERE id_equipo != 0" if tabla == "equipo" else ""
                sep = " AND" if filtro else " WHERE"
                resultado[tabla] = Modelo._query(
                    f"SELECT COUNT(*) FROM {tabla}{filtro}"
                    f"{sep} (ultima_auditoria_fecha IS NULL "
                    f"OR ultima_auditoria_fecha = '')"
                )[0][0]
            except Exception:
                resultado[tabla] = 0
        return resultado

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
    def devolver_equipos_tarjetas():
        """Datos para el listado de Equipos en tarjetas (fotos picon +
        resumen). Cols: id, nombre, marca, modelo, tipo, picon,
        n_conectores, n_conexiones, n_patcheras, auditado (0/1)."""
        return Modelo._query(
            "SELECT eq.id_equipo, eq.nombre, COALESCE(m.nombre,''), "
            "COALESCE(eq.modelo,''), COALESCE(te.nombre,''), "
            "COALESCE(eq.picon,''), "
            "(SELECT COUNT(*) FROM conector c "
            " WHERE c.id_equipo=eq.id_equipo) AS n_con, "
            "(SELECT COUNT(*) FROM conexion cx "
            " JOIN conector c2 ON c2.id_conector=cx.id_conector "
            " WHERE c2.id_equipo=eq.id_equipo) AS n_cx, "
            "(SELECT COUNT(DISTINCT e2.id_equipo) FROM conector c1 "
            " JOIN conexion cx1 ON cx1.id_conector=c1.id_conector "
            " JOIN conexion cx2 ON cx2.id_cable=cx1.id_cable "
            "   AND cx2.id_conector!=cx1.id_conector "
            " JOIN conector c2b ON c2b.id_conector=cx2.id_conector "
            " JOIN equipo e2 ON e2.id_equipo=c2b.id_equipo "
            " JOIN tipo_equipo te2 ON te2.id_tipo_equipo=e2.id_tipo_equipo "
            " WHERE c1.id_equipo=eq.id_equipo "
            " AND te2.nombre='MODULO PATCHERA') AS n_patch, "
            "CASE WHEN eq.ultima_auditoria_fecha IS NOT NULL "
            "AND eq.ultima_auditoria_fecha!='' THEN 1 ELSE 0 END AS auditado "
            "FROM equipo eq "
            "LEFT JOIN marca m ON m.id_marca = eq.id_marca "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo "
            "WHERE eq.id_equipo != 0 "
            "ORDER BY eq.nombre"
        )

    @staticmethod
    def devolver_ubicaciones_equipos():
        """id_equipo (str) -> 'Rack · Unidad N' (o nombre de Sala si está
        suelto). Tres consultas en bloque (rack directo, rack vía frame/
        slot, sala suelta) en vez de una por equipo — evita N+1 con
        cientos de equipos en el listado."""
        ubic = {}
        for id_eq, rack_nom, ur in Modelo._query(
                "SELECT pr.id_equipo, r.nombre, pr.unidades_de_rack_equipo "
                "FROM posicion_en_rack pr "
                "JOIN rack r ON r.id_rack=pr.id_rack "
                "WHERE pr.id_equipo IS NOT NULL AND pr.id_equipo!=0"):
            rack_nom = _n(rack_nom) or ""
            texto = f"{rack_nom} · Unidad {ur}" if ur else rack_nom
            if texto:
                ubic[str(id_eq)] = texto
        for id_eq, rack_nom in Modelo._query(
                "SELECT sl.id_equipo, r.nombre "
                "FROM slot sl "
                "JOIN posicion_en_rack pr ON pr.id_frame = sl.id_frame "
                "JOIN rack r ON r.id_rack = pr.id_rack "
                "WHERE sl.id_equipo IS NOT NULL AND sl.id_equipo!=0"):
            ubic.setdefault(str(id_eq), _n(rack_nom) or "")
        for id_eq, sala_nom in Modelo._query(
                "SELECT en.id_equipo, s.nombre "
                "FROM equiponoraqueable_por_sala en "
                "JOIN sala s ON s.id_sala=en.id_sala"):
            ubic.setdefault(str(id_eq), _n(sala_nom) or "")
        return ubic

    @staticmethod
    def devolver_id_todos_los_equipos():
        return Modelo._query("SELECT id_equipo FROM equipo")

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
            "eq.path_manual, eq.configuraciones, eq.picon "
            "FROM equipo eq "
            "LEFT JOIN marca m ON m.id_marca = eq.id_marca "
            "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo "
            "LEFT JOIN imagen im ON im.id_imagen = eq.id_imagen "
            "WHERE eq.id_equipo = ?",
            (id_equipo,),
        )
        if not filas:
            return filas
        f = filas[0]
        # índices: 9=imagen_path, 11=coordenada_x, 12=coordenada_y
        x_px, y_px = Modelo._px_punto_o_crudo(f[9] or None, f[11], f[12])
        f[11], f[12] = x_px, y_px
        return [f]

    @staticmethod
    def alta_equipo(id_tipo_equipo, id_marca, num_inventario, num_serie,
                    modelo, nombre, id_imagen, x, y, path_manual=None,
                    configuraciones=None, picon=None):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "INSERT INTO equipo (id_tipo_equipo, id_marca, num_inventario, "
            "num_serie, modelo, nombre, id_imagen, "
            "coordenada_x_en_imagen, coordenada_y_en_imagen, path_manual, "
            "configuraciones, picon) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
             _n(num_serie), _n(modelo), _n(nombre),
             _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones),
             _n(picon)),
        )

    @staticmethod
    def modificacion_equipo(id_equipo, id_tipo_equipo, id_marca,
                            num_inventario, num_serie, modelo, nombre,
                            id_imagen, x, y, path_manual=None,
                            configuraciones=None, picon=None):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "UPDATE equipo SET id_tipo_equipo=?, id_marca=?, "
            "num_inventario=?, num_serie=?, modelo=?, nombre=?, "
            "id_imagen=?, coordenada_x_en_imagen=?, "
            "coordenada_y_en_imagen=?, path_manual=?, configuraciones=?, "
            "picon=? WHERE id_equipo=?",
            (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
             _n(num_serie), _n(modelo), _n(nombre),
             _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones),
             _n(picon), id_equipo),
        )

    @staticmethod
    def eliminar_equipo(id_equipo):
        Modelo._exec("DELETE FROM equipo WHERE id_equipo=?", (id_equipo,))

    @staticmethod
    def alta_equipo_retorna_id(id_tipo_equipo, id_marca, num_inventario,
                               num_serie, modelo, nombre, id_imagen, x, y, path_manual=None, configuraciones=None):
        """Igual que alta_equipo pero retornael id del registro creado."""
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        with Modelo._conn() as conn:
            cur = conn.execute(
                "INSERT INTO equipo (id_tipo_equipo, id_marca, num_inventario, "
                "num_serie, modelo, nombre, id_imagen, "
                "coordenada_x_en_imagen, coordenada_y_en_imagen, path_manual, configuraciones) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (_n(id_tipo_equipo), _n(id_marca), _n(num_inventario),
                 _n(num_serie), _n(modelo), _n(nombre),
                 _n(id_imagen), x_pct, y_pct, _n(path_manual), _n(configuraciones)),
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
    def alta_tipo(nombre):
        Modelo._exec("INSERT INTO tipo_equipo (nombre) VALUES (?)", (_n(nombre),))

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
        f = filas[0]
        # índices: 5=x, 6=y, 8=path_imagen
        x_px, y_px = Modelo._px_punto_o_crudo(f[8] or None, f[5], f[6])
        f[5], f[6] = x_px, y_px
        return [f]

    @staticmethod
    def agregar_conector(nombre, id_equipo, id_tipo_conector, id_imagen, x, y):
        x_pct, y_pct = Modelo._pct_punto_o_none(
            Modelo._path_imagen(id_imagen), _n(x), _n(y))
        Modelo._exec(
            "INSERT INTO conector (nombre, id_equipo, id_tipo_conector, "
            "id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen) "
            "VALUES (?,?,?,?,?,?)",
            (_n(nombre), _n(id_equipo), _n(id_tipo_conector),
             _n(id_imagen), x_pct, y_pct),
        )

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
        f = filas[0]
        # índices: 4=path_imagen, 6=x, 7=y, 8=alto, 9=ancho
        x, y, ancho, alto = Modelo._px_rect_o_crudo(
            f[4] or None, f[6], f[7], f[9], f[8])
        f[6], f[7], f[8], f[9] = x, y, alto, ancho
        return [f]

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
        with Modelo._conn() as conn:
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
    def devolver_cables_de_equipo(id_equipo):
        """Cables que tienen al menos una conexión con el equipo dado."""
        return Modelo._query(
            "SELECT c.id_cable, c.codigo, c.longitud, "
            "COALESCE(c.estado, 'VERIFICADO') AS estado, "
            "(SELECT COUNT(*) FROM conexion cx2 WHERE cx2.id_cable=c.id_cable) "
            "AS n_conexiones "
            "FROM cable c "
            "WHERE c.es_cable_conexion_interna = 0 "
            "AND EXISTS ("
            "  SELECT 1 FROM conexion cx "
            "  JOIN conector cn ON cn.id_conector = cx.id_conector "
            "  WHERE cx.id_cable = c.id_cable AND cn.id_equipo = ?"
            ") "
            "ORDER BY c.codigo",
            (id_equipo,),
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
        sin_auditar = Modelo._query(
            "SELECT COUNT(*) FROM equipo WHERE id_equipo != 0 "
            "AND (ultima_auditoria_fecha IS NULL OR ultima_auditoria_fecha = '')"
        )[0][0]
        sin_manual = Modelo._query(
            "SELECT COUNT(*) FROM equipo WHERE id_equipo != 0 "
            "AND (path_manual IS NULL OR TRIM(path_manual) = '')"
        )[0][0]
        sin_configuraciones = Modelo._query(
            "SELECT COUNT(*) FROM equipo WHERE id_equipo != 0 "
            "AND (configuraciones IS NULL OR TRIM(configuraciones) = '')"
        )[0][0]
        return {
            "sin_conectores":     sin_conectores,
            "sin_imagen":         sin_imagen,
            "sin_img_conectores": sin_img_conectores,
            "sin_auditar":        sin_auditar,
            "sin_manual":         sin_manual,
            "sin_configuraciones": sin_configuraciones,
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
        with Modelo._conn() as conn:
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

    # ── Conexiones ────────────────────────────────────────────────────────────
    @staticmethod
    def devolver_todas_las_conexiones(id_cable=None, id_equipo=None):
        if id_cable:
            return Modelo._query(
                "SELECT id_conexion, equipo_nombre, conector_nombre, "
                "cable_codigo, tipo_conector, tipo_equipo, "
                "id_cable, id_conector, id_equipo "
                "FROM CONEXIONES WHERE id_cable=? ORDER BY cable_codigo",
                (id_cable,)
            )
        if id_equipo:
            return Modelo._query(
                "SELECT id_conexion, equipo_nombre, conector_nombre, "
                "cable_codigo, tipo_conector, tipo_equipo, "
                "id_cable, id_conector, id_equipo "
                "FROM CONEXIONES WHERE id_equipo=? ORDER BY cable_codigo",
                (id_equipo,)
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
    def devolver_equipos_conectados_a_equipo(id_equipo):
        return Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo = ?",
            (id_equipo,),
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
        for f in filas:
            # la % está calculada sobre la imagen propia del slot
            # (img_slot, columna 9) — misma imagen que usan
            # agregar_slot/modificar_slot para convertir; si el slot no
            # tiene imagen propia, se usa la del frame como mejor esfuerzo
            # (mismo criterio que core/modelo.py, desktop).
            path_archivo = f[9] or f[8] or None
            x, y, ancho, alto = Modelo._px_rect_o_crudo(
                path_archivo, f[4], f[5], f[6], f[7])
            f[4], f[5], f[6], f[7] = x, y, ancho, alto
            resultado.append(f[:9])  # se descarta img_slot (col 9), no forma parte del contrato original
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
        """Todos los equipos de tipo MODULO PATCHERA (id, nombre)."""
        return Modelo._query(
            "SELECT e.id_equipo, e.nombre FROM equipo e "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE te.nombre = 'MODULO PATCHERA' ORDER BY e.nombre"
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
            "WHERE te.nombre = 'MODULO PATCHERA'",
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
