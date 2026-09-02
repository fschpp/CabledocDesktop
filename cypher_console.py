"""
cypher_console.py — Consola Cypher interactiva para CableDoc
=============================================================
Diálogo GTK3 que permite ejecutar queries Cypher sobre el grafo
de equipos y cables construido con GraphQLite.

Uso desde cabledoc.py o pantallas_avanzadas.py:
    from cypher_console import CypherConsole
    dlg = CypherConsole(parent_window, db_path)
    dlg.run()
    dlg.destroy()

O como ventana independiente:
    CypherConsole(None, DB_PATH).run()
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

try:
    from i18n import _, set_lang, get_lang, cargar_idioma_guardado, IDIOMAS_DISPONIBLES
    cargar_idioma_guardado()
except ImportError:
    def _(t): return t
    def set_lang(c): pass
    def get_lang(): return "es"
    def cargar_idioma_guardado(): pass
    IDIOMAS_DISPONIBLES = {"es": "Español"}

import os
import math
import random
import re
import time
import logging
import traceback
import shutil
import tempfile

from graph_impact import GraphImpactAnalyzer          # reutiliza el grafo
from graphqlite.graph import Graph

# Directorio por defecto para guardar/cargar archivos .cypher
# Vive junto a los demás archivos de la aplicación
CYPHER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cypher")

# Directorio de logs, junto a los demás archivos de la aplicación
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def _crear_logger() -> logging.Logger:
    """
    Logger dedicado a la Consola Cypher, para poder diagnosticar problemas
    como consultas que tardan mucho o cuelgan la interfaz.

    Escribe a cypher_console.log (junto a la app) Y a la consola (stdout),
    con timestamps, para poder correlacionar "hasta dónde llegó" antes de
    que la interfaz deje de responder. Si no se puede crear el archivo
    (permisos, disco, etc.) sigue funcionando solo con el handler de
    consola, no rompe la app.
    """
    logger = logging.getLogger("cabledoc.cypher_console")
    if logger.handlers:
        return logger   # ya configurado (evita duplicar handlers)
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = logging.FileHandler(
            os.path.join(LOG_DIR, "cypher_console.log"), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


log = _crear_logger()


def _log_espacio_libre(etiqueta: str) -> None:
    """
    Registra el espacio libre en disco en TODAS las ubicaciones donde algo
    en la app (o en GTK/GLib por debajo) podría llegar a escribir archivos
    temporales o de caché:
      • carpeta de la app (db.db, cypher_console.log, tmp_sqlite/, exports)
      • carpeta temporal (tempfile.gettempdir() — ya redirigida a
        tmp_sqlite/ por graph_impact.py, pero se deja el chequeo por si
        algo la resetea)
      • home del usuario (~/.cache, ~/.local/share, dconf, etc. — GTK/GLib
        escriben ahí para íconos, clipboard, historial, etc.)
      • XDG_RUNTIME_DIR (/run/user/<uid> típicamente — SIEMPRE es tmpfs en
        Linux, y lo usa dbus/gvfs/portapapeles/gtk; si se llena, cualquier
        operación de GTK puede fallar con "no space left on device" sin
        que tenga nada que ver con SQLite ni con la consulta ejecutada)
      • directorio de trabajo actual (os.getcwd() — ahí caen los .dot/.pdf
        que genera GeneradorDiagrama y las exportaciones SVG/PDF)
      • raíz del sistema de archivos (/ — para descartar que el disco
        real, y no una carpeta temporal en particular, sea el que está
        lleno)

    Esto ayuda a correlacionar un error de "espacio en disco" con la
    ubicación real que se quedó sin lugar, en vez de asumir que siempre es
    la misma (la app puede escribir en varios lugares distintos).
    """
    candidatos = [
        ("carpeta app",       os.path.dirname(os.path.abspath(__file__))),
        ("carpeta temporal",  tempfile.gettempdir()),
        ("home del usuario",  os.path.expanduser("~")),
        ("directorio actual (cwd)", os.getcwd()),
        ("raíz del sistema (/)", os.path.abspath(os.sep)),
    ]
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        candidatos.append(("XDG_RUNTIME_DIR (tmpfs de GTK/dbus)", xdg_runtime))

    for nombre, ruta in candidatos:
        try:
            total, usado, libre = shutil.disk_usage(ruta)
            log.info(
                "%s — espacio libre en %s (%s): %.2f GB de %.2f GB",
                etiqueta, nombre, ruta, libre / 2**30, total / 2**30,
            )
        except Exception as exc:
            log.warning("%s — no se pudo leer espacio libre de %s: %s",
                        etiqueta, ruta, exc)


def _log_detalle_excepcion(exc: Exception) -> None:
    """
    Registra detalles finos de la excepción que a veces no aparecen en el
    traceback estándar, pero son justo lo que hace falta para saber DÓNDE
    se quedó sin espacio: errno, strerror y sobre todo `filename` — cuando
    Python abre/escribe un archivo y falla, ese atributo trae la ruta
    exacta del archivo que se estaba escribiendo. Si el error viene de
    dentro de SQLite/GraphQLite (una extensión en C) puede no traer
    filename, pero el tipo de excepción (module.Clase) igual ayuda a saber
    si es un sqlite3.OperationalError, un OSError de Python, etc.
    """
    tipo = f"{type(exc).__module__}.{type(exc).__name__}"
    errno_    = getattr(exc, "errno", None)
    filename  = getattr(exc, "filename", None)
    strerror  = getattr(exc, "strerror", None)
    log.error(
        "DETALLE EXCEPCIÓN — tipo=%s errno=%s strerror=%s filename=%s",
        tipo, errno_, strerror, filename,
    )

# Patrón para detectar relaciones de largo variable en una query Cypher,
# ej: [:CABLE*1..8], [:CABLE*..5], [:CABLE*3]. Estos patrones son la causa
# más común de que una consulta "cuelgue" la interfaz: la cantidad de
# caminos a recorrer puede crecer exponencialmente con la cantidad de
# saltos, sobre todo en grafos con ciclos o nodos muy conectados.
_RE_PATH_VARIABLE = re.compile(
    r"\[[^\]]*?\*\s*(\d*)\s*(?:\.\.\s*(\d*))?[^\]]*?\]"
)


def _detectar_paths_variables(query: str):
    """
    Devuelve una lista de (patrón_encontrado, saltos_max) por cada relación
    de largo variable (ej: '*1..8') presente en la query. saltos_max es
    None si no hay límite superior explícito (ej: '*', '*3..' sin tope),
    lo cual es el caso más riesgoso porque la exploración no está acotada.
    """
    hallazgos = []
    for m in _RE_PATH_VARIABLE.finditer(query):
        minimo, maximo = m.group(1), m.group(2)
        try:
            if maximo is not None:
                # Hay "..": con tope si trae dígitos ("*1..8"), sin tope
                # si no ("*2.." — riesgo alto, no está limitado por arriba).
                saltos_max = int(maximo) if maximo else None
            elif minimo:
                # Sin "..": salto exacto ("*3" == "*3..3")
                saltos_max = int(minimo)
            else:
                # Solo "*", sin números en absoluto: totalmente sin acotar
                saltos_max = None
        except ValueError:
            saltos_max = None
        hallazgos.append((m.group(0).strip(), saltos_max))
    return hallazgos


# ─────────────────────────────────────────────────────────────────────────────
# Snippets de ejemplo con descripción
# ─────────────────────────────────────────────────────────────────────────────

SNIPPETS = [
    ("── EQUIPOS ──", None),
    ("Todos los equipos",
     "MATCH (n:Equipo)\nRETURN n.id, n.nombre\nORDER BY n.nombre"),
    ("Equipos con salidas (OUT)",
     "MATCH (n:Equipo)\nWHERE EXISTS((n)-[:CABLE]->())\nRETURN n.id, n.nombre"),
    ("Equipos sin entradas (fuentes)",
     "MATCH (n:Equipo)\nWHERE NOT EXISTS(()-[:CABLE]->(n))\nRETURN n.id, n.nombre\nORDER BY n.nombre"),
    ("Buscar equipo por nombre",
     "MATCH (n:Equipo)\nWHERE toLower(n.nombre) CONTAINS 'monitor'\nRETURN n.id, n.nombre"),
    ("Equipos con más salidas",
     "MATCH (n:Equipo)-[:CABLE]->()\nRETURN n.nombre, count(*) AS salidas\nORDER BY salidas DESC\nLIMIT 10"),

    ("── CABLES ──", None),
    ("Todos los cables",
     "MATCH (a:Equipo)-[r:CABLE]->(b:Equipo)\nRETURN r.cable_id, r.nombre, a.nombre AS origen, b.nombre AS destino\nORDER BY r.nombre"),
    ("Cables de un equipo (salientes)",
     "MATCH (a:Equipo {id: '65'})-[r:CABLE]->(b:Equipo)\nRETURN r.cable_id, r.nombre, b.nombre AS destino"),
    ("Cables entrantes a un equipo",
     "MATCH (a:Equipo)-[r:CABLE]->(b:Equipo {id: '65'})\nRETURN r.cable_id, r.nombre, a.nombre AS origen"),
    ("Buscar cable por código",
     "MATCH (a:Equipo)-[r:CABLE]->(b:Equipo)\nWHERE r.nombre CONTAINS 'VL00'\nRETURN r.cable_id, r.nombre, a.nombre AS origen, b.nombre AS destino"),

    ("── CADENAS ──", None),
    ("Cadena completa desde un equipo",
     "MATCH (inicio:Equipo {id: '60'})-[:CABLE*]->(destino:Equipo)\nRETURN DISTINCT destino.id, destino.nombre"),
    ("Camino entre dos equipos",
     "MATCH (a:Equipo {id: '60'})-[:CABLE*1..8]->(b:Equipo {id: '191'})\nRETURN a.nombre, b.nombre"),
    ("Equipos a N saltos de distancia",
     "MATCH (inicio:Equipo {id: '60'})-[:CABLE*1..2]->(destino:Equipo)\nRETURN DISTINCT destino.id, destino.nombre"),
    ("Cadenas que pasan por un equipo",
     "MATCH (a:Equipo)-[:CABLE*]->(medio:Equipo {id: '65'})-[:CABLE*]->(b:Equipo)\nRETURN DISTINCT a.nombre AS origen, b.nombre AS destino\nLIMIT 20"),

    ("── ANÁLISIS ──", None),
    ("Equipos hoja (sin salidas)",
     "MATCH (n:Equipo)\nWHERE NOT EXISTS((n)-[:CABLE]->())\nRETURN n.id, n.nombre\nORDER BY n.nombre"),
    ("Equipos aislados (sin conexiones)",
     "MATCH (n:Equipo)\nWHERE NOT EXISTS((n)-[:CABLE]-()) AND NOT EXISTS(()-[:CABLE]-(n))\nRETURN n.id, n.nombre"),
    ("BFS desde un equipo",
     "RETURN bfs('60')"),
    ("Equipos con más entradas",
     "MATCH ()-[:CABLE]->(n:Equipo)\nRETURN n.nombre, count(*) AS entradas\nORDER BY entradas DESC\nLIMIT 10"),
    ("Ciclos (equipos que se alcanzan a sí mismos)",
     "MATCH (n:Equipo)-[:CABLE*2..]->(n)\nRETURN DISTINCT n.id, n.nombre"),

    ("── MODIFICAR (con cuidado) ──", None),
    ("SET: marcar equipo",
     "MATCH (n:Equipo {id: '65'})\nSET n.marcado = true\nRETURN n.nombre, n.marcado"),
    ("SET: quitar marca",
     "MATCH (n:Equipo)\nWHERE n.marcado = true\nREMOVE n.marcado\nRETURN n.nombre"),
    ("CREATE: nodo temporal",
     "CREATE (n:Equipo {id: 'TMP1', nombre: 'Equipo Temporal', tipo: 'TEST'})\nRETURN n.nombre"),
    ("MERGE: nodo o actualizar",
     "MERGE (n:Equipo {id: 'TMP1'})\nSET n.visitado = true\nRETURN n.nombre, n.visitado"),
    ("DELETE: borrar nodo temporal",
     "MATCH (n:Equipo {id: 'TMP1'})\nDETACH DELETE n\nRETURN count(n) AS borrados"),
    ("CREATE edge entre dos equipos",
     "MATCH (a:Equipo {id: '60'}), (b:Equipo {id: '191'})\nCREATE (a)-[:CABLE {cable_id: 'SIM01', nombre: 'SIMULADO'}]->(b)\nRETURN 'edge creado'"),
    ("DELETE edge simulado",
     "MATCH (a:Equipo {id: '60'})-[r:CABLE {cable_id: 'SIM01'}]->(b)\nDELETE r\nRETURN 'edge borrado'"),
    ("UNWIND: procesar lista",
     "UNWIND ['60', '65', '191'] AS eid\nMATCH (n:Equipo {id: eid})\nRETURN eid, n.nombre"),
    ("WITH: pipeline",
     "MATCH (n:Equipo)-[:CABLE]->(m:Equipo)\nWITH n, count(m) AS salidas\nWHERE salidas >= 2\nRETURN n.nombre, salidas\nORDER BY salidas DESC"),
]

# Funciones/keywords para autocompletado
KEYWORDS = [
    "MATCH", "OPTIONAL MATCH", "WHERE", "RETURN", "WITH", "UNWIND",
    "CREATE", "MERGE", "SET", "REMOVE", "DELETE", "DETACH DELETE",
    "ORDER BY", "LIMIT", "SKIP", "DISTINCT", "AS", "IN", "NOT", "AND", "OR",
    "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END",
    "CONTAINS", "STARTS WITH", "ENDS WITH",
    "count", "collect", "sum", "avg", "min", "max",
    "toLower", "toUpper", "toString", "toInteger", "toFloat",
    "bfs", "dfs",
    ":Equipo", ":CABLE",
    "n.id", "n.nombre", "r.cable_id", "r.nombre",
    "a.nombre", "b.nombre",
]


# ─────────────────────────────────────────────────────────────────────────────
# Ventana principal de la consola
# ─────────────────────────────────────────────────────────────────────────────

class CypherConsole(Gtk.Dialog):

    def __init__(self, parent, db_path: str):
        super().__init__(
            title=_("Consola Cypher — CableDoc"),
            transient_for=parent,
            flags=0,
        )
        self.set_default_size(1100, 700)
        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)

        self._db_path = db_path
        self._graph: Graph | None = None
        self._historial: list[str] = []
        self._hist_idx = -1
        self._archivo_actual: str | None = None   # ruta del archivo abierto

        log.info("=" * 70)
        log.info("CONSOLA CYPHER: abierta (db_path=%s)", db_path)
        self.connect("destroy", lambda *_: log.info("CONSOLA CYPHER: cerrada"))

        self._build_ui()
        self._cargar_grafo()

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(0)

        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_wide_handle(True)
        area.pack_start(hpaned, True, True, 0)

        # Panel izquierdo: snippets
        hpaned.pack1(self._build_panel_snippets(), resize=False, shrink=False)

        # Panel derecho: editor + resultados
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hpaned.pack2(right, resize=True, shrink=True)

        # Barra de estado del grafo
        self._lbl_estado = Gtk.Label()
        self._lbl_estado.set_xalign(0)
        self._lbl_estado.set_margin_start(8)
        self._lbl_estado.set_margin_top(4)
        self._lbl_estado.set_margin_bottom(4)
        right.pack_start(self._lbl_estado, False, False, 0)

        sep = Gtk.Separator()
        right.pack_start(sep, False, False, 0)

        # Split editor / resultados
        vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        vpaned.set_wide_handle(True)
        right.pack_start(vpaned, True, True, 0)

        vpaned.pack1(self._build_panel_editor(), resize=False, shrink=False)
        vpaned.pack2(self._build_panel_resultados(), resize=True, shrink=True)
        vpaned.set_position(200)

        self.show_all()

    def _build_panel_snippets(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_size_request(230, -1)

        lbl = Gtk.Label()
        lbl.set_markup("<b>  Ejemplos</b>")
        lbl.set_xalign(0)
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(4)
        box.pack_start(lbl, False, False, 0)

        store = Gtk.ListStore(str, str)   # label, query (vacío si es cabecera)
        for label, query in SNIPPETS:
            store.append([label, query or ""])

        tv = Gtk.TreeView(model=store)
        tv.set_headers_visible(False)
        tv.set_activate_on_single_click(False)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererText()
        cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        col.pack_start(cell, True)

        def cell_data(col, cell, model, it, _):
            label = model[it][0]
            query = model[it][1]
            if not query:  # es cabecera de sección
                cell.set_property("markup", f"<small><b>{label}</b></small>")
                cell.set_property("sensitive", False)
            else:
                cell.set_property("markup", f"<small>{label}</small>")
                cell.set_property("sensitive", True)
        col.set_cell_data_func(cell, cell_data)
        tv.append_column(col)

        tv.connect("row-activated", self._on_snippet_activado)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(tv)
        box.pack_start(sw, True, True, 0)

        # Botón recargar grafo
        btn_reload = Gtk.Button(label=_("🔄 Recargar grafo"))
        btn_reload.set_margin_start(6); btn_reload.set_margin_end(6)
        btn_reload.set_margin_top(4); btn_reload.set_margin_bottom(4)
        btn_reload.connect("clicked", lambda _: self._cargar_grafo())
        box.pack_start(btn_reload, False, False, 0)

        # Botón ver grafo completo (todos los nodos/aristas cargados en memoria)
        btn_ver_grafo = Gtk.Button(label=_("🕸 Ver grafo completo"))
        btn_ver_grafo.set_tooltip_text(
            "Muestra gráficamente todos los equipos (nodos) y cables (aristas)\n"
            "que están cargados actualmente en el grafo GraphQLite en memoria."
        )
        btn_ver_grafo.set_margin_start(6); btn_ver_grafo.set_margin_end(6)
        btn_ver_grafo.set_margin_bottom(6)
        btn_ver_grafo.connect("clicked", self._ver_grafo_completo)
        box.pack_start(btn_ver_grafo, False, False, 0)

        return box

    def _build_panel_editor(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6); box.set_margin_end(6)
        box.set_margin_top(6)

        # Toolbar del editor
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_spacing(4)

        lbl = Gtk.Label()
        lbl.set_markup("<b>Query Cypher</b>")
        tb.pack_start(lbl, False, False, 0)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        btn_run = Gtk.Button(label=_("▶  Ejecutar  (F5)"))
        btn_run.get_style_context().add_class("suggested-action")
        btn_run.connect("clicked", lambda _: self._ejecutar())
        tb.pack_start(btn_run, False, False, 0)

        btn_limpiar = Gtk.Button(label=_("✕  Limpiar"))
        btn_limpiar.connect("clicked", lambda _: self._buf.set_text(""))
        tb.pack_start(btn_limpiar, False, False, 0)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        # Archivo
        btn_abrir = Gtk.Button(label=_("📂 Abrir"))
        btn_abrir.set_tooltip_text("Abrir archivo .cypher  (Ctrl+O)")
        btn_abrir.connect("clicked", lambda _: self._archivo_abrir())
        tb.pack_start(btn_abrir, False, False, 0)

        btn_guardar = Gtk.Button(label=_("💾 Guardar"))
        btn_guardar.set_tooltip_text("Guardar en el archivo actual  (Ctrl+S)")
        btn_guardar.connect("clicked", lambda _: self._archivo_guardar())
        tb.pack_start(btn_guardar, False, False, 0)

        btn_guardar_como = Gtk.Button(label=_("💾 Guardar como…"))
        btn_guardar_como.set_tooltip_text("Guardar con nuevo nombre  (Ctrl+Shift+S)")
        btn_guardar_como.connect("clicked", lambda _: self._archivo_guardar_como())
        tb.pack_start(btn_guardar_como, False, False, 0)

        self._lbl_archivo = Gtk.Label(label="")
        self._lbl_archivo.set_markup("<small><i>sin archivo</i></small>")
        self._lbl_archivo.set_xalign(0)
        self._lbl_archivo.set_ellipsize(3)   # END
        self._lbl_archivo.set_max_width_chars(30)
        tb.pack_start(self._lbl_archivo, False, False, 4)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        # Historial
        btn_prev = Gtk.Button(label="◀")
        btn_prev.set_tooltip_text("Query anterior (↑)")
        btn_prev.connect("clicked", lambda _: self._hist_navegar(-1))
        tb.pack_start(btn_prev, False, False, 0)

        btn_next = Gtk.Button(label="▶")
        btn_next.set_tooltip_text("Query siguiente (↓)")
        btn_next.connect("clicked", lambda _: self._hist_navegar(1))
        tb.pack_start(btn_next, False, False, 0)

        box.pack_start(tb, False, False, 0)

        # Editor con resaltado de palabras clave básico
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(120)

        self._editor = Gtk.TextView()
        self._editor.set_monospace(True)
        self._editor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._editor.set_left_margin(8)
        self._editor.set_right_margin(8)
        self._editor.set_top_margin(6)
        self._buf = self._editor.get_buffer()

        # Tags de color para resaltado
        self._tag_kw   = self._buf.create_tag("kw",   foreground="#5599ff", weight=Pango.Weight.BOLD)
        self._tag_str  = self._buf.create_tag("str",  foreground="#cc8833")
        self._tag_num  = self._buf.create_tag("num",  foreground="#44aa44")
        self._tag_prop = self._buf.create_tag("prop", foreground="#aa44cc")

        self._buf.connect("changed", self._on_buf_changed)

        # F5 ejecuta
        self._editor.connect("key-press-event", self._on_key_press)

        sw.add(self._editor)
        box.pack_start(sw, True, True, 0)

        # Texto inicial
        self._buf.set_text(
            "MATCH (a:Equipo)-[r:CABLE]->(b:Equipo)\n"
            "RETURN r.nombre AS cable, a.nombre AS origen, b.nombre AS destino\n"
            "ORDER BY r.nombre\nLIMIT 20"
        )

        return box

    def _build_panel_resultados(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6); box.set_margin_end(6)
        box.set_margin_bottom(6)

        # Header de resultados
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hdr.set_spacing(6)
        hdr.set_margin_top(4)

        self._lbl_resultados = Gtk.Label()
        self._lbl_resultados.set_markup("<b>Resultados</b>")
        self._lbl_resultados.set_xalign(0)
        hdr.pack_start(self._lbl_resultados, True, True, 0)

        btn_copiar = Gtk.Button(label=_("📋 Copiar CSV"))
        btn_copiar.set_tooltip_text("Copiar resultados al portapapeles como CSV")
        btn_copiar.connect("clicked", self._on_copiar_csv)
        hdr.pack_end(btn_copiar, False, False, 0)

        btn_grafo_resultado = Gtk.Button(label=_("🕸 Ver como grafo"))
        btn_grafo_resultado.set_tooltip_text(
            "Grafica las entidades detectadas en el resultado actual\n"
            "(nodos devueltos con RETURN n, o columnas de id/nombre de equipo)."
        )
        btn_grafo_resultado.connect("clicked", self._ver_grafo_resultado)
        hdr.pack_end(btn_grafo_resultado, False, False, 0)

        box.pack_start(hdr, False, False, 0)

        # Stack: tabla | error | vacío
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Vista de tabla
        self._sw_tabla = Gtk.ScrolledWindow()
        self._sw_tabla.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._tv_resultado = Gtk.TreeView()
        self._tv_resultado.set_rubber_banding(True)
        self._tv_resultado.set_activate_on_single_click(False)
        self._tv_resultado.connect("row-activated", self._on_fila_activada)
        self._tv_resultado.set_tooltip_text(
            "Doble clic para abrir el ABM del equipo o cable de la fila"
        )
        sel = self._tv_resultado.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        self._sw_tabla.add(self._tv_resultado)
        self._stack.add_named(self._sw_tabla, "tabla")

        # Vista de error
        self._tv_error = Gtk.TextView()
        self._tv_error.set_editable(False)
        self._tv_error.set_monospace(True)
        self._tv_error.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._tv_error.set_left_margin(8)
        self._tv_error.override_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.9, 0.3, 0.3, 1.0)
        )
        sw_err = Gtk.ScrolledWindow()
        sw_err.add(self._tv_error)
        self._stack.add_named(sw_err, "error")

        # Vista vacía
        lbl_vacio = Gtk.Label(label=_("Escribe una query y presiona F5 o ▶ Ejecutar"))
        lbl_vacio.set_sensitive(False)
        self._stack.add_named(lbl_vacio, "vacio")
        self._stack.set_visible_child_name("vacio")

        box.pack_start(self._stack, True, True, 0)

        return box

    # ── Carga del grafo ───────────────────────────────────────────────────────

    def _cargar_grafo(self):
        """
        Construye el grafo en el hilo principal (requerido por SQLite).
        Usa GLib.idle_add para diferir la construccion al siguiente ciclo GTK,
        lo que permite que el label "Cargando..." se muestre primero.
        """
        log.info("GRAFO: solicitada (re)carga desde %s", self._db_path)
        self._lbl_estado.set_markup(
            "<span foreground='#aaaaaa'>⏳ Cargando grafo desde la BD…</span>"
        )
        GLib.idle_add(self._cargar_grafo_sync)

    def _cargar_grafo_sync(self):
        """Construye el grafo en el hilo principal (idle callback)."""
        t0 = time.monotonic()
        _log_espacio_libre("GRAFO: antes de construir")
        try:
            analyzer = GraphImpactAnalyzer(self._db_path)
            analyzer.construir_grafo()
            self._graph    = analyzer._g
            self._analyzer = analyzer
            n_eq  = len(analyzer._equipos)
            n_cab = len(analyzer._cables)
            elapsed = time.monotonic() - t0
            log.info(
                "GRAFO: cargado OK en %.3fs | equipos=%d cables=%d",
                elapsed, n_eq, n_cab,
            )
            self._lbl_estado.set_markup(
                f"<span foreground='#44aa44'>✓ Grafo cargado — "
                f"<b>{n_eq}</b> equipos  ·  <b>{n_cab}</b> cables</span>"
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            log.error(
                "GRAFO: error cargando tras %.3fs: %s\n%s",
                elapsed, exc, traceback.format_exc(),
            )
            _log_detalle_excepcion(exc)
            _log_espacio_libre("GRAFO: justo después del error")
            self._lbl_estado.set_markup(
                f"<span foreground='#cc3333'>✗ Error cargando grafo: {exc}</span>"
            )
        return False  # no repetir idle_add

    # ── Ejecución de query ────────────────────────────────────────────────────

    def _ejecutar(self):
        if self._graph is None:
            log.warning("EJECUTAR: ignorado, el grafo todavía no está cargado.")
            self._mostrar_error("El grafo aún no está cargado. Espera un momento.")
            return

        start_it = self._buf.get_start_iter()
        end_it   = self._buf.get_end_iter()
        query    = self._buf.get_text(start_it, end_it, False).strip()

        if not query:
            return

        # Agregar al historial
        if not self._historial or self._historial[-1] != query:
            self._historial.append(query)
        self._hist_idx = len(self._historial)

        # ── Diagnóstico previo: patrones de camino de largo variable ──
        # (ej: [:CABLE*1..8]) son la causa más común de que la consulta
        # tarde muchísimo o "cuelgue" la interfaz, porque graphqlite la
        # corre de forma síncrona en el mismo hilo de GTK: mientras dure,
        # la interfaz no puede procesar eventos ni repintarse.
        hallazgos = _detectar_paths_variables(query)
        if hallazgos:
            n_eq  = len(self._analyzer._equipos) if self._analyzer else "?"
            n_cab = len(self._analyzer._cables)  if self._analyzer else "?"
            log.warning(
                "EJECUTAR: la query tiene camino(s) de largo variable %s "
                "sobre un grafo de %s equipos / %s cables. Esto puede "
                "crecer exponencialmente en grafos con ciclos o nodos muy "
                "conectados y colgar la interfaz (GraphQLite corre "
                "síncrono en el hilo de GTK).",
                [h for h, _ in hallazgos], n_eq, n_cab,
            )
            if not self._confirmar_ejecucion_riesgosa(hallazgos):
                log.info("EJECUTAR: el usuario canceló la ejecución riesgosa.")
                return

        log.info(
            "EJECUTAR: iniciando query (%d caracteres). Primeros 200: %r",
            len(query), query[:200].replace("\n", " ⏎ "),
        )
        log.debug("EJECUTAR: texto completo de la query:\n%s", query)

        # Deshabilitar el botón mientras corre, para que no se dispare dos
        # veces (GraphQLite no soporta cancelar una consulta en curso).
        self._lbl_resultados.set_markup(
            "<b>Resultados</b>  <small><i>— ejecutando… (mirá cypher_console.log "
            "si la interfaz deja de responder)</i></small>"
        )
        # Forzar repintado antes de bloquear el hilo con la consulta.
        while Gtk.events_pending():
            Gtk.main_iteration()

        t0 = time.monotonic()
        _log_espacio_libre("EJECUTAR: antes de correr la query")
        try:
            filas = self._graph.query(query)
            elapsed = time.monotonic() - t0
            log.info(
                "EJECUTAR: query terminó OK en %.3fs | filas=%d",
                elapsed, len(filas) if filas is not None else 0,
            )
            self._mostrar_tabla(filas, query)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            log.error(
                "EJECUTAR: query terminó con ERROR tras %.3fs: %s\n%s",
                elapsed, exc, traceback.format_exc(),
            )
            _log_detalle_excepcion(exc)
            _log_espacio_libre("EJECUTAR: justo después del error")

            mensaje = str(exc)
            texto_err = mensaje.lower()
            es_disco_lleno = (
                getattr(exc, "errno", None) == 28   # ENOSPC
                or "no space left" in texto_err
                or ("disk" in texto_err and ("full" in texto_err or "space" in texto_err))
                or ("espacio" in texto_err and "disco" in texto_err)
            )
            if es_disco_lleno:
                filename = getattr(exc, "filename", None)
                log.error(
                    "EJECUTAR: detectado error de espacio en disco "
                    "(filename=%s) — revisá el detalle de la excepción y el "
                    "log de espacio libre justo arriba para ver EXACTAMENTE "
                    "qué ubicación se quedó sin lugar (puede no ser la "
                    "carpeta temporal: también puede ser el disco real, el "
                    "home del usuario, o XDG_RUNTIME_DIR usado por GTK).",
                    filename,
                )
                mensaje += (
                    "\n\n⚠ Error de espacio en disco"
                    + (f" al escribir: {filename}" if filename else "")
                    + ".\nRevisá el archivo "
                    f"{os.path.join(LOG_DIR, 'cypher_console.log')} "
                    "(línea 'DETALLE EXCEPCIÓN' y las líneas de espacio "
                    "libre justo antes) para ver qué carpeta se quedó sin "
                    "lugar exactamente — puede no ser la temporal.\n"
                    "Si la consulta usaba un camino de largo variable "
                    "(ej: [:CABLE*1..8]), probá con un rango más chico "
                    "(ej: *1..3)."
                )
            self._mostrar_error(mensaje)

    def _confirmar_ejecucion_riesgosa(self, hallazgos) -> bool:
        """
        Diálogo de advertencia antes de correr una query con caminos de
        largo variable (ej: *1..8). Devuelve True si el usuario confirma.
        """
        patrones  = ", ".join(p for p, _ in hallazgos)
        saltos    = [h for _, h in hallazgos if h]
        max_salto = max(saltos) if saltos else None

        texto = (
            f"Esta consulta usa camino(s) de largo variable: {patrones}\n\n"
            "En un grafo con ciclos o equipos muy conectados, la cantidad "
            "de caminos a explorar puede crecer exponencialmente. "
            "GraphQLite corre la consulta de forma síncrona, así que "
            "mientras dure la interfaz va a quedar sin responder y no hay "
            "forma de cancelarla una vez iniciada.\n\n"
        )
        if max_salto:
            texto += f"Salto máximo detectado: {max_salto}.\n\n"
        texto += "¿Ejecutar de todos modos?"

        dlg = Gtk.MessageDialog(
            transient_for=self, flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO, text=texto,
        )
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def _mostrar_tabla(self, filas: list[dict], query: str):
        # Limpiar columnas anteriores
        for col in self._tv_resultado.get_columns():
            self._tv_resultado.remove_column(col)

        if not filas:
            self._lbl_resultados.set_markup(
                "<b>Resultados</b>  <small><i>— 0 filas</i></small>"
            )
            store = Gtk.ListStore(str)
            store.append(["(sin resultados)"])
            col = Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0)
            self._tv_resultado.set_model(store)
            self._tv_resultado.append_column(col)
            self._stack.set_visible_child_name("tabla")
            return

        # Determinar columnas
        columnas = list(filas[0].keys())
        n = len(columnas)

        # Crear ListStore con todo strings (para simplicidad de display)
        store = Gtk.ListStore(*([str] * n))
        for fila in filas:
            row = []
            for k in columnas:
                v = fila.get(k)
                if v is None:
                    row.append("null")
                elif isinstance(v, dict):
                    # Nodo devuelto completo — mostrar sus props relevantes
                    props = v.get("properties", v)
                    nom = props.get("nombre") or props.get("id") or str(v)
                    row.append(f"[{nom}]")
                elif isinstance(v, list):
                    row.append(", ".join(str(x) for x in v))
                elif isinstance(v, float):
                    row.append(f"{v:.4f}")
                else:
                    row.append(str(v))
            store.append(row)

        self._tv_resultado.set_model(store)

        for i, col_name in enumerate(columnas):
            renderer = Gtk.CellRendererText()
            renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            renderer.set_property("xpad", 6)
            tv_col = Gtk.TreeViewColumn(col_name, renderer, text=i)
            tv_col.set_resizable(True)
            tv_col.set_min_width(80)
            tv_col.set_sort_column_id(i)
            self._tv_resultado.append_column(tv_col)

        # Guardar filas crudas para doble clic → ABM
        self._filas_actuales    = filas
        self._columnas_actuales = columnas

        # Detectar tipo de entidad y mostrar hint en el label
        hint = ""
        if filas:
            ent = _detectar_entidad(filas[0])
            if ent:
                iconos = {"equipo": "🖥️", "cable": "🔌", "conexion": "🔗"}
                hint = (f"  <small><i>· doble clic para abrir "
                        f"{iconos.get(ent[0], '')} {ent[0]}</i></small>")

        n_filas = len(filas)
        self._lbl_resultados.set_markup(
            f"<b>Resultados</b>  <small><i>— {n_filas} fila{'s' if n_filas != 1 else ''}</i></small>{hint}"
        )
        self._stack.set_visible_child_name("tabla")

    def _on_fila_activada(self, tv, path, _col):
        """Doble clic en fila de resultados: detecta entidad y abre su ABM."""
        filas = getattr(self, "_filas_actuales", [])
        if not filas or path is None:
            return
        idx = path.get_indices()[0]
        if idx >= len(filas):
            return
        entidad = _detectar_entidad(filas[idx])
        if entidad is None:
            return
        self._abrir_abm(*entidad)

    def _abrir_abm(self, tipo: str, eid: str):
        """Abre el diálogo ABM de cabledoc.py para la entidad dada."""
        try:
            import cabledoc as _cd
        except ImportError:
            self._mostrar_dlg_info(
                f"Entidad: {tipo}  id={eid}\n"
                "(cabledoc.py no disponible en modo standalone)"
            )
            return

        try:
            if tipo == "equipo":
                _cd._DialogoEquipo(id_equipo=eid, parent=self).run_and_destroy()
            elif tipo == "cable":
                _cd._DialogoCable(id_cable=eid, parent=self).run_and_destroy()
            elif tipo == "conexion":
                _cd._DialogoConexion(id_conexion=eid, parent=self).run_and_destroy()
        except Exception as exc:
            self._mostrar_dlg_info(f"Error abriendo ABM de {tipo} {eid}:\n{exc}")

    def _mostrar_dlg_info(self, msg: str):
        dlg = Gtk.MessageDialog(
            transient_for=self, flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=msg,
        )
        dlg.run(); dlg.destroy()

    def _mostrar_error(self, msg: str):
        self._tv_error.get_buffer().set_text(f"⚠  Error:\n\n{msg}")
        self._stack.set_visible_child_name("error")
        self._lbl_resultados.set_markup("<b>Resultados</b>  <small><i>— error</i></small>")

    # ── Historial ─────────────────────────────────────────────────────────────

    def _hist_navegar(self, delta: int):
        if not self._historial:
            return
        self._hist_idx = max(0, min(len(self._historial) - 1,
                                     self._hist_idx + delta))
        self._buf.set_text(self._historial[self._hist_idx])

    # ── Archivo ───────────────────────────────────────────────────────────────

    def _archivo_dir(self) -> str:
        """Devuelve el directorio cypher/ de la aplicación, creándolo si no existe."""
        os.makedirs(CYPHER_DIR, exist_ok=True)
        return CYPHER_DIR

    def _archivo_actualizar_label(self):
        """Muestra el nombre del archivo actual en la toolbar."""
        if self._archivo_actual:
            nombre = os.path.basename(self._archivo_actual)
            self._lbl_archivo.set_markup(f"<small><i>{nombre}</i></small>")
            self._lbl_archivo.set_tooltip_text(self._archivo_actual)
        else:
            self._lbl_archivo.set_markup("<small><i>sin archivo</i></small>")
            self._lbl_archivo.set_tooltip_text("")

    def _archivo_abrir(self):
        """Abre un archivo .cypher desde el sistema de archivos."""
        dlg = Gtk.FileChooserDialog(
            title="Abrir consulta Cypher",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Abrir", Gtk.ResponseType.OK)
        dlg.set_current_folder(self._archivo_dir())
        filtro = Gtk.FileFilter()
        filtro.set_name("Archivos Cypher (*.cypher, *.cql, *.txt)")
        for p in ("*.cypher", "*.cql", "*.txt"):
            filtro.add_pattern(p)
        dlg.add_filter(filtro)
        filtro_all = Gtk.FileFilter()
        filtro_all.set_name("Todos los archivos")
        filtro_all.add_pattern("*")
        dlg.add_filter(filtro_all)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            dlg.destroy()
            try:
                with open(ruta, "r", encoding="utf-8") as fh:
                    contenido = fh.read()
                self._buf.set_text(contenido)
                self._archivo_actual = ruta
                self._archivo_actualizar_label()
            except Exception as exc:
                self._mostrar_error("Error al abrir " + ruta + ":\n" + str(exc))
        else:
            dlg.destroy()

    def _archivo_guardar(self):
        """Guarda en el archivo actual; si no hay uno, abre Guardar como."""
        if self._archivo_actual:
            self._archivo_escribir(self._archivo_actual)
        else:
            self._archivo_guardar_como()

    def _archivo_guardar_como(self):
        """Guarda con un nombre nuevo elegido por el usuario."""
        dlg = Gtk.FileChooserDialog(
            title="Guardar consulta Cypher",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Guardar", Gtk.ResponseType.OK)
        dlg.set_current_folder(self._archivo_dir())
        dlg.set_do_overwrite_confirmation(True)
        if self._archivo_actual:
            dlg.set_current_name(os.path.basename(self._archivo_actual))
        else:
            start = self._buf.get_start_iter()
            end   = self._buf.get_iter_at_offset(40)
            frag  = self._buf.get_text(start, end, False).strip()
            frag  = "".join(c if c.isalnum() or c in " _-" else "_" for c in frag)
            dlg.set_current_name((frag[:30].strip("_ ") or "consulta") + ".cypher")
        filtro = Gtk.FileFilter()
        filtro.set_name("Archivos Cypher (*.cypher)")
        filtro.add_pattern("*.cypher")
        dlg.add_filter(filtro)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            dlg.destroy()
            if not ruta.lower().endswith((".cypher", ".cql", ".txt")):
                ruta += ".cypher"
            self._archivo_escribir(ruta)
        else:
            dlg.destroy()

    def _archivo_escribir(self, ruta):
        """Escribe el contenido del editor al archivo indicado."""
        start = self._buf.get_start_iter()
        end   = self._buf.get_end_iter()
        texto = self._buf.get_text(start, end, False)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(texto)
            self._archivo_actual = ruta
            self._archivo_actualizar_label()
        except Exception as exc:
            self._mostrar_error("Error al guardar " + ruta + ":\n" + str(exc))

    def _on_copiar_csv(self, _):
        model = self._tv_resultado.get_model()
        cols  = getattr(self, "_columnas_actuales", [])
        if not model or not cols:
            return
        lineas = [",".join(f'"{c}"' for c in cols)]
        for row in model:
            lineas.append(",".join(f'"{row[i]}"' for i in range(len(cols))))
        texto = "\n".join(lineas)
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(texto, -1)

    # ── Vista gráfica del grafo ───────────────────────────────────────────────

    def _ver_grafo_completo(self, _btn=None):
        """Abre la vista gráfica con TODOS los equipos/cables cargados en el grafo."""
        analyzer = getattr(self, "_analyzer", None)
        if analyzer is None or not analyzer.esta_construido():
            self._mostrar_dlg_info(
                "El grafo aún no está cargado.\nEsperá un momento o presioná "
                "'🔄 Recargar grafo'."
            )
            return

        nodos = dict(analyzer._equipos)
        aristas = [
            (src, dst, analyzer._cables.get(cid, cid))
            for cid, (src, dst) in analyzer._cable_endpoints.items()
        ]

        if not nodos:
            self._mostrar_dlg_info("No hay equipos cargados para graficar.")
            return

        posiciones = _cargar_posiciones_guardadas()

        dlg = VistaGrafoSimple(
            nodos, aristas,
            titulo=f"Grafo completo  —  {len(nodos)} equipos, {len(aristas)} cables",
            parent=self, tipo_nodo="equipo",
            posiciones_guardadas=posiciones,
        )
        dlg.run()
        dlg.destroy()

    def _ver_grafo_resultado(self, _btn=None):
        """Abre la vista gráfica con las entidades detectadas en el último resultado."""
        filas    = getattr(self, "_filas_actuales", None)
        columnas = getattr(self, "_columnas_actuales", None)
        if not filas:
            self._mostrar_dlg_info(
                "Ejecutá una query primero (F5) para poder graficar su resultado."
            )
            return

        analyzer = getattr(self, "_analyzer", None)
        nombre_a_id = {}
        if analyzer is not None:
            nombre_a_id = {
                str(nom).strip().lower(): eid
                for eid, nom in analyzer._equipos.items()
            }

        nodos, aristas = _extraer_grafo_de_resultado(filas, columnas, nombre_a_id)
        if not nodos:
            self._mostrar_dlg_info(
                "No se detectaron nodos graficables en este resultado.\n\n"
                "Probá con una query que devuelva nodos completos (RETURN n),\n"
                "o columnas con id/nombre de equipo (ej: n.id, n.nombre,\n"
                "a.nombre AS origen, b.nombre AS destino)."
            )
            return

        dlg = VistaGrafoSimple(
            nodos, aristas,
            titulo=f"Grafo del resultado  —  {len(nodos)} nodos, {len(aristas)} relaciones",
            parent=self, tipo_nodo="auto",
            posiciones_guardadas=_cargar_posiciones_guardadas(),
        )
        dlg.run()
        dlg.destroy()

    # ── Snippet ───────────────────────────────────────────────────────────────

    def _on_snippet_activado(self, tv, path, _col):
        model = tv.get_model()
        query = model[path][1]
        if query:
            self._buf.set_text(query)
            self._editor.grab_focus()

    # ── Resaltado de sintaxis (básico) ────────────────────────────────────────

    def _on_buf_changed(self, buf):
        # Limpiar tags anteriores
        start = buf.get_start_iter()
        end   = buf.get_end_iter()
        for tag in (self._tag_kw, self._tag_str, self._tag_num, self._tag_prop):
            buf.remove_tag(tag, start, end)

        texto = buf.get_text(start, end, False)

        import re
        # Keywords Cypher
        kw_pattern = re.compile(
            r'\b(MATCH|OPTIONAL\s+MATCH|WHERE|RETURN|WITH|UNWIND|CREATE|MERGE|'
            r'SET|REMOVE|DELETE|DETACH|ORDER\s+BY|LIMIT|SKIP|DISTINCT|AS|IN|'
            r'NOT|AND|OR|EXISTS|CASE|WHEN|THEN|ELSE|END|CONTAINS|STARTS\s+WITH|'
            r'ENDS\s+WITH|TRUE|FALSE|NULL|count|collect|sum|avg|min|max|'
            r'toLower|toUpper|toString|toInteger|toFloat|bfs|dfs)\b',
            re.IGNORECASE
        )
        for m in kw_pattern.finditer(texto):
            it_s = buf.get_iter_at_offset(m.start())
            it_e = buf.get_iter_at_offset(m.end())
            buf.apply_tag(self._tag_kw, it_s, it_e)

        # Strings entre comillas simples
        for m in re.finditer(r"'[^']*'", texto):
            it_s = buf.get_iter_at_offset(m.start())
            it_e = buf.get_iter_at_offset(m.end())
            buf.apply_tag(self._tag_str, it_s, it_e)

        # Números
        for m in re.finditer(r'\b\d+(\.\d+)?\b', texto):
            it_s = buf.get_iter_at_offset(m.start())
            it_e = buf.get_iter_at_offset(m.end())
            buf.apply_tag(self._tag_num, it_s, it_e)

        # Propiedades (n.nombre, r.cable_id, etc.)
        for m in re.finditer(r'\b\w+\.\w+\b', texto):
            it_s = buf.get_iter_at_offset(m.start())
            it_e = buf.get_iter_at_offset(m.end())
            buf.apply_tag(self._tag_prop, it_s, it_e)

    # ── Teclado ───────────────────────────────────────────────────────────────

    def _on_key_press(self, widget, event):
        ctrl  = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)

        # F5 → ejecutar
        if event.keyval == Gdk.KEY_F5:
            self._ejecutar()
            return True
        # Ctrl+Enter → ejecutar
        if ctrl and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._ejecutar()
            return True
        # Ctrl+S → guardar  /  Ctrl+Shift+S → guardar como
        if ctrl and event.keyval in (Gdk.KEY_s, Gdk.KEY_S):
            if shift:
                self._archivo_guardar_como()
            else:
                self._archivo_guardar()
            return True
        # Ctrl+O → abrir
        if ctrl and event.keyval in (Gdk.KEY_o, Gdk.KEY_O):
            self._archivo_abrir()
            return True
        # Alt+Up/Down → historial
        if event.state & Gdk.ModifierType.MOD1_MASK:
            if event.keyval == Gdk.KEY_Up:
                self._hist_navegar(-1); return True
            if event.keyval == Gdk.KEY_Down:
                self._hist_navegar(1);  return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada standalone (para pruebas sin cabledoc.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from modelo import DB_PATH

    Gtk.init([])
    dlg = CypherConsole(None, DB_PATH)
    dlg.connect("response", lambda *_: Gtk.main_quit())
    dlg.connect("destroy",  lambda *_: Gtk.main_quit())
    Gtk.main()


# ─────────────────────────────────────────────────────────────────────────────
# Detección de entidad y apertura de ABM al hacer doble clic en una fila
# ─────────────────────────────────────────────────────────────────────────────

def _detectar_entidad(fila_cruda: dict) -> "tuple[str, str] | None":
    """
    Dado un dict de valores crudos de una fila de resultado Cypher,
    intenta detectar qué entidad representa y devuelve (tipo, id_str).

    Estrategias de detección (en orden de prioridad):
      1. Columna exacta reconocida: n.id, r.cable_id, a.id, b.id ...
      2. Objeto nodo completo con labels: {'labels': ['Equipo'], 'properties': {...}}
      3. Objeto relación completa con type: {'type': 'CABLE', 'properties': {...}}
      4. Columna llamada 'id' o 'cable_id' sola

    Retorna: ('equipo', '42') | ('cable', '17') | ('conexion', '5') | None
    """
    keys = list(fila_cruda.keys())

    # ── 1. Columnas escalares reconocidas ─────────────────────────────────────
    # Equipo: n.id, a.id, b.id, equipo_id, id_equipo, etc.
    for k in keys:
        kl = k.lower().replace(" ", "").replace("_", "")
        v  = fila_cruda[k]
        if v is None or v == "null":
            continue
        # Nodo id de equipo
        if k in ("n.id", "a.id", "b.id", "equipo.id") or kl in ("nid", "aid", "bid", "equipoid", "idequipo"):
            return ("equipo", str(v))
        # Cable id
        if k in ("r.cable_id", "cable_id", "r.cableid") or kl in ("rcableid", "cableid", "idcable"):
            return ("cable", str(v))
        # Conexion id
        if k in ("r.conexion_id", "conexion_id", "id_conexion") or kl in ("conexionid", "idconexion"):
            return ("conexion", str(v))

    # ── 2. Objetos completos (RETURN n / RETURN r) ────────────────────────────
    for k in keys:
        v = fila_cruda[k]
        if not isinstance(v, dict):
            continue
        labels = v.get("labels", [])
        tipo   = v.get("type", "")
        props  = v.get("properties", {})

        if "Equipo" in labels:
            eid = props.get("id") or v.get("id")
            if eid is not None:
                return ("equipo", str(eid))

        if tipo == "CABLE":
            cid = props.get("cable_id") or props.get("id")
            if cid is not None:
                return ("cable", str(cid))

    # ── 3. Columnas genéricas como último recurso ─────────────────────────────
    for k in keys:
        v = fila_cruda[k]
        if v is None or v == "null":
            continue
        kl = k.lower().replace(" ", "").replace("_", "")
        if kl == "id":
            # Ambiguo — no abrimos nada sin saber el tipo
            pass

    return None


def _cargar_posiciones_guardadas() -> dict:
    """
    Lee TODAS las posiciones x,y guardadas en
    diagrama_equipos_posicion_en_imagen (la misma tabla que usa
    DiagramaConexiones al arrastrar nodos) en una sola consulta.
    Devuelve {id_equipo_str: (x, y)}. Si la tabla no existe o falla,
    devuelve un dict vacío (no rompe la vista de grafo).
    """
    try:
        from modelo import Modelo
        filas = Modelo._query(
            "SELECT id_equipo, x, y FROM diagrama_equipos_posicion_en_imagen "
            "WHERE x IS NOT NULL AND y IS NOT NULL"
        )
    except Exception:
        return {}
    resultado = {}
    for id_eq, x, y in filas:
        try:
            resultado[str(id_eq)] = (float(x), float(y))
        except (TypeError, ValueError):
            continue
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Extracción heurística de un grafo (nodos/aristas) a partir de un resultado
# Cypher crudo, para poder graficarlo con VistaGrafoSimple.
# ─────────────────────────────────────────────────────────────────────────────

_COLS_IGNORADAS = {
    "count", "salidas", "entradas", "cantidad", "borrados", "visitado",
    "marcado",
}


def _extraer_grafo_de_resultado(filas: list, columnas: list,
                                 nombre_a_id: dict | None = None):
    """
    Heurística: recorre cada fila del resultado agrupando las columnas por
    "entidad" (todo lo que comparte el mismo prefijo antes del punto, p.ej.
    n.id/n.nombre, a.id/a.nombre; o un alias directo sin punto como
    "origen"/"destino"/"equipo"). Cada entidad se identifica por su columna
    *.id si está presente (eso permite abrir el ABM con doble clic); si no
    hay id pero sí un nombre, se intenta resolver contra `nombre_a_id`
    (equipos reales ya cargados) para no duplicar el mismo equipo como dos
    nodos distintos según el alias con el que aparezca en cada fila.

    Si una fila aporta 2+ entidades, se conectan en cadena (arista entre
    entidad i e i+1, con la primera columna tipo r.*/cable como etiqueta);
    si aporta 1 sola, queda como nodo aislado.

    Devuelve (nodos: dict[str,str], aristas: list[(id_a, id_b, etiqueta)]).
    """
    nombre_a_id = nombre_a_id or {}
    nodos: dict = {}
    aristas: list = []

    ALIAS_NODO = ("origen", "destino", "equipo", "medio", "inicio")

    for fila in filas:
        entidades = {}        # base -> {"id": str|None, "nombre": str|None}
        orden_bases = []
        etiqueta_arista = ""

        for k in columnas:
            v = fila.get(k)

            # ── Objetos completos (RETURN n / RETURN r) ──
            if isinstance(v, dict):
                labels = v.get("labels", [])
                tipo   = v.get("type", "")
                props  = v.get("properties", v)
                if labels:
                    ent = entidades.setdefault(k, {"id": None, "nombre": None})
                    if k not in orden_bases:
                        orden_bases.append(k)
                    ent["id"]     = str(props.get("id", v.get("id", k)))
                    ent["nombre"] = str(props.get("nombre", ent["id"]))
                elif tipo:
                    etiqueta_arista = str(
                        props.get("nombre") or props.get("cable_id") or tipo
                    )
                continue

            if v is None or v == "null":
                continue

            kl = k.strip().lower().replace(" ", "")
            if kl in _COLS_IGNORADAS:
                continue

            if "." in kl:
                base, campo = kl.split(".", 1)
            else:
                base, campo = kl, ""

            # Columnas de la relación (cable) → etiqueta de la arista, no nodo
            if base == "r" or ("cable" in kl and campo != "id"):
                if campo in ("nombre", "cable_id", "codigo") or kl in ("cable", "codigo"):
                    etiqueta_arista = etiqueta_arista or str(v)
                    continue

            campo_es_id     = campo == "id"
            campo_es_nombre = campo == "nombre" or campo == ""
            es_alias_nodo   = base in ALIAS_NODO or any(
                t in base for t in ("nombre", "origen", "destino", "equipo"))

            if not (campo_es_id or campo_es_nombre):
                continue
            if campo == "" and not es_alias_nodo:
                # columna suelta sin punto que no parece un equipo (ej:
                # una columna de agregación no listada arriba) → ignorar
                continue

            ent = entidades.setdefault(base, {"id": None, "nombre": None})
            if base not in orden_bases:
                orden_bases.append(base)
            if campo_es_id:
                ent["id"] = str(v)
            else:
                ent["nombre"] = str(v)

        entidades_fila = []
        for base in orden_bases:
            ent    = entidades[base]
            nombre = ent.get("nombre") or ent.get("id") or base
            nid    = ent.get("id")
            if not nid:
                nid = nombre_a_id.get(str(nombre).strip().lower())
            if not nid:
                nid = f"{base}:{nombre}"
            nid = str(nid)
            nodos[nid] = nombre
            if nid not in entidades_fila:
                entidades_fila.append(nid)

        if len(entidades_fila) >= 2:
            for i in range(len(entidades_fila) - 1):
                aristas.append(
                    (entidades_fila[i], entidades_fila[i + 1], etiqueta_arista))
        elif len(entidades_fila) == 1:
            nodos.setdefault(entidades_fila[0], nodos[entidades_fila[0]])

    return nodos, aristas


# ─────────────────────────────────────────────────────────────────────────────
# VistaGrafoSimple — visualización de grafo dirigido fuerza-dirigida (liviana)
# ─────────────────────────────────────────────────────────────────────────────

class VistaGrafoSimple(Gtk.Dialog):
    """
    Ventana con un lienzo Cairo que dibuja un grafo dirigido simple:
    nodos = círculos con etiqueta, aristas = flechas entre ellos.

    Layout: fuerza-dirigida (Fruchterman-Reingold simplificado), calculado
    una vez al abrir. Los nodos se pueden reacomodar arrastrándolos.

    Controles:
      • Arrastrar nodo         — reposicionar
      • Rueda del ratón        — zoom (centrado en el cursor)
      • Botón medio/derecho    — pan
      • Clic en nodo           — selecciona y resalta sus aristas
      • Doble clic en nodo     — abre el ABM del equipo (si el id es numérico)
      • Botón "🔀 Reordenar"   — vuelve a correr el layout desde cero
    """

    NODE_R   = 13
    C_BG     = (0.10, 0.11, 0.14)
    C_NODE   = (0.20, 0.45, 0.75)
    C_NODE_S = (0.95, 0.70, 0.15)
    C_EDGE   = (0.45, 0.48, 0.55)
    C_EDGE_S = (0.95, 0.75, 0.20)
    C_TXT    = (0.95, 0.95, 0.95)
    C_LBL    = (0.75, 0.75, 0.45)

    def __init__(self, nodos: dict, aristas: list, titulo="Grafo",
                 parent=None, tipo_nodo="equipo", posiciones_guardadas=None):
        super().__init__(
            title=titulo, transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons("Cerrar", Gtk.ResponseType.CLOSE)
        self.set_default_size(1000, 700)

        self._nodos_data   = nodos          # {id: nombre}
        self._aristas_data = aristas        # [(id_a, id_b, etiqueta)]
        self._tipo_nodo    = tipo_nodo      # "equipo" | "auto" (heurística por id)

        # Posiciones reales guardadas en diagrama_equipos_posicion_en_imagen,
        # filtradas a los nodos que efectivamente están en este grafo.
        self._posiciones_guardadas = {
            nid: pos for nid, pos in (posiciones_guardadas or {}).items()
            if nid in nodos
        }

        # posiciones {id: [x, y]}
        self._pos   = {}
        self._zoom  = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        self._sel_id     = None
        self._drag_id    = None
        self._drag_ox    = 0.0
        self._drag_oy    = 0.0
        self._panning    = False
        self._pan_mx = self._pan_my = 0.0
        self._pan_ox = self._pan_oy = 0.0

        area = self.get_content_area()

        # ── Toolbar ──
        tb = Gtk.Box(spacing=6, margin_start=6, margin_end=6,
                     margin_top=4, margin_bottom=4)
        n_guardadas = len(self._posiciones_guardadas)
        info_txt = f"{len(nodos)} nodos  ·  {len(aristas)} aristas"
        if n_guardadas:
            info_txt += f"  ·  {n_guardadas} con posición guardada"
        self._lbl_info = Gtk.Label(xalign=0, hexpand=True)
        self._lbl_info.set_text(info_txt)
        tb.pack_start(self._lbl_info, True, True, 0)

        self._chk_guardadas = None
        if n_guardadas:
            self._chk_guardadas = Gtk.CheckButton(label=_("📌 Usar posiciones guardadas"))
            self._chk_guardadas.set_active(True)
            self._chk_guardadas.set_tooltip_text(
                "Usa la posición x,y que ya tienen guardada estos equipos\n"
                "(la misma que se ve/edita en 'Diagrama de conexiones') como\n"
                "ancla del layout; el resto de los nodos se acomoda alrededor."
            )
            self._chk_guardadas.connect("toggled", lambda b: self._recalcular_layout())
            tb.pack_start(self._chk_guardadas, False, False, 0)

        btn_reorder = Gtk.Button(label=_("🔀 Reordenar"))
        btn_reorder.set_tooltip_text("Recalcula el layout fuerza-dirigido")
        btn_reorder.connect("clicked", lambda b: self._recalcular_layout())
        tb.pack_start(btn_reorder, False, False, 0)

        for lbl, fn in [
            ("⊞ Encuadrar", lambda _: self._fit_all()),
            ("1:1",         lambda _: self._set_zoom(1.0)),
        ]:
            b = Gtk.Button(label=lbl); b.connect("clicked", fn)
            tb.pack_start(b, False, False, 0)

        area.pack_start(tb, False, False, 0)
        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── Canvas ──
        self._da = Gtk.DrawingArea()
        self._da.set_hexpand(True); self._da.set_vexpand(True)
        self._da.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK   |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.SCROLL_MASK
        )
        self._da.connect("draw",                 self._on_draw)
        self._da.connect("button-press-event",   self._on_press)
        self._da.connect("motion-notify-event",  self._on_motion)
        self._da.connect("button-release-event", self._on_release)
        self._da.connect("scroll-event",         self._on_scroll)
        self._da.set_tooltip_text(
            "Clic: seleccionar  ·  doble clic: abrir equipo  ·  "
            "arrastrar nodo: mover  ·  arrastrar fondo: pan  ·  rueda: zoom"
        )
        area.pack_start(self._da, True, True, 0)

        self._sb = Gtk.Statusbar()
        area.pack_start(self._sb, False, False, 0)

        self.show_all()
        self._recalcular_layout()

    # ── layout fuerza-dirigido (Fruchterman-Reingold simplificado) ────────────

    # Distancia mínima que se garantiza entre centros de nodos (post-proceso
    # de anti-solapamiento), en unidades de mundo.
    MIN_SEP_FACTOR = 5.2   # múltiplo de NODE_R

    def _recalcular_layout(self):
        ids = list(self._nodos_data.keys())
        n   = len(ids)
        if n == 0:
            self._da.queue_draw()
            return

        min_sep = self.NODE_R * self.MIN_SEP_FACTOR

        usar_guardadas = bool(
            self._chk_guardadas is not None and self._chk_guardadas.get_active()
        )
        anclados = set(self._posiciones_guardadas.keys()) if usar_guardadas else set()

        # El lienzo de trabajo crece con la cantidad de nodos para que el
        # algoritmo tenga margen real donde separarlos (si no, con áreas
        # chicas la repulsión no alcanza a vencer la atracción de las
        # aristas y quedan amontonados).
        lado = max(700.0, min_sep * math.sqrt(n) * 1.6)

        # Centro de referencia: si hay nodos anclados, centrar el lienzo en
        # su posición real (así los nodos libres se acomodan alrededor de
        # las coordenadas ya conocidas, en vez de en un origen arbitrario).
        if anclados:
            xs = [self._posiciones_guardadas[a][0] for a in anclados]
            ys = [self._posiciones_guardadas[a][1] for a in anclados]
            bb_w = max(xs) - min(xs)
            bb_h = max(ys) - min(ys)
            cx = (max(xs) + min(xs)) / 2
            cy = (max(ys) + min(ys)) / 2
            lado = max(lado, bb_w + min_sep * 4, bb_h + min_sep * 4)
        else:
            cx = cy = lado / 2

        self._pos = {}
        for nid in ids:
            if nid in anclados:
                x, y = self._posiciones_guardadas[nid]
                self._pos[nid] = [float(x), float(y)]
            else:
                self._pos[nid] = [
                    random.uniform(cx - lado / 2, cx + lado / 2),
                    random.uniform(cy - lado / 2, cy + lado / 2),
                ]

        if n == 1:
            self._fit_all()
            self._da.queue_draw()
            return

        edges = [(a, b) for a, b, _ in self._aristas_data
                 if a in self._pos and b in self._pos]

        area = lado * lado
        # Constante de espaciado ideal de Fruchterman-Reingold, agrandada
        # (factor > 1) para que los nodos queden más separados entre sí.
        k = math.sqrt(area / n) * 1.7
        iteraciones = min(260, max(80, 18000 // n))

        for it in range(iteraciones):
            disp = {nid: [0.0, 0.0] for nid in ids}

            # repulsión (todos contra todos — n limitado en la práctica)
            for i in range(n):
                a = ids[i]
                ax, ay = self._pos[a]
                for j in range(i + 1, n):
                    b = ids[j]
                    bx, by = self._pos[b]
                    dx, dy = ax - bx, ay - by
                    dist = max(0.05, math.hypot(dx, dy))
                    force = (k * k) / dist
                    fx, fy = dx / dist * force, dy / dist * force
                    disp[a][0] += fx; disp[a][1] += fy
                    disp[b][0] -= fx; disp[b][1] -= fy

            # atracción a lo largo de las aristas
            for a, b in edges:
                ax, ay = self._pos[a]
                bx, by = self._pos[b]
                dx, dy = ax - bx, ay - by
                dist = max(0.05, math.hypot(dx, dy))
                force = (dist * dist) / k
                fx, fy = dx / dist * force, dy / dist * force
                disp[a][0] -= fx; disp[a][1] -= fy
                disp[b][0] += fx; disp[b][1] += fy

            # aplicar desplazamiento con "temperatura" decreciente
            # (los nodos anclados no se mueven: actúan de referencia fija)
            temp = (lado * 0.1) * (1 - it / iteraciones)
            for nid in ids:
                if nid in anclados:
                    continue
                dx, dy = disp[nid]
                dist = max(0.05, math.hypot(dx, dy))
                lim = min(dist, max(temp, 0.5))
                x, y = self._pos[nid]
                x += dx / dist * lim
                y += dy / dist * lim
                self._pos[nid] = [x, y]

        # ── Post-proceso anti-solapamiento ──
        # El FR clásico no garantiza una distancia mínima entre nodos; acá
        # se resuelven las colisiones remanentes empujando los pares que
        # quedaron demasiado cerca, hasta asegurar min_sep entre todos
        # (los nodos anclados no se mueven, se empuja solo al otro).
        self._resolver_colisiones(ids, min_sep, anclados)

        self._fit_all()
        self._da.queue_draw()

    def _resolver_colisiones(self, ids, min_sep, anclados=None, pasadas=40):
        anclados = anclados or set()
        n = len(ids)
        for _ in range(pasadas):
            hubo_choque = False
            for i in range(n):
                a = ids[i]
                ax, ay = self._pos[a]
                for j in range(i + 1, n):
                    b = ids[j]
                    bx, by = self._pos[b]
                    dx, dy = ax - bx, ay - by
                    dist = math.hypot(dx, dy)
                    if dist < min_sep:
                        a_fijo = a in anclados
                        b_fijo = b in anclados
                        if a_fijo and b_fijo:
                            continue   # no se puede resolver, se acepta
                        hubo_choque = True
                        if dist < 1e-4:
                            ang = random.uniform(0, 2 * math.pi)
                            dx, dy = math.cos(ang), math.sin(ang)
                            dist = 1e-4
                        ux, uy = dx / dist, dy / dist
                        if a_fijo:
                            empuje = min_sep - dist
                            bx -= ux * empuje; by -= uy * empuje
                        elif b_fijo:
                            empuje = min_sep - dist
                            ax += ux * empuje; ay += uy * empuje
                        else:
                            empuje = (min_sep - dist) / 2
                            ax += ux * empuje; ay += uy * empuje
                            bx -= ux * empuje; by -= uy * empuje
                        self._pos[a] = [ax, ay]
                        self._pos[b] = [bx, by]
            if not hubo_choque:
                break

    # ── coordenadas ────────────────────────────────────────────────────────

    def _s2w(self, sx, sy):
        return (sx - self._pan_x) / self._zoom, (sy - self._pan_y) / self._zoom

    def _hit_node(self, wx, wy):
        r = self.NODE_R
        for nid, (x, y) in self._pos.items():
            if (wx - x) ** 2 + (wy - y) ** 2 <= r * r:
                return nid
        return None

    # ── zoom / encuadre ────────────────────────────────────────────────────

    def _set_zoom(self, z, cx=None, cy=None):
        alloc = self._da.get_allocation()
        if cx is None: cx = alloc.width / 2
        if cy is None: cy = alloc.height / 2
        old_z = self._zoom
        new_z = max(0.05, min(6.0, z))
        self._pan_x = cx - (cx - self._pan_x) * (new_z / old_z)
        self._pan_y = cy - (cy - self._pan_y) * (new_z / old_z)
        self._zoom = new_z
        self._da.queue_draw()

    def _fit_all(self):
        if not self._pos:
            return
        alloc = self._da.get_allocation()
        if alloc.width < 10 or alloc.height < 10:
            GLib.idle_add(self._fit_all)
            return
        xs = [p[0] for p in self._pos.values()]
        ys = [p[1] for p in self._pos.values()]
        mn_x, mn_y = min(xs) - 60, min(ys) - 60
        mx_x, mx_y = max(xs) + 60, max(ys) + 60
        cw, ch = max(1.0, mx_x - mn_x), max(1.0, mx_y - mn_y)
        z = max(0.05, min(2.5, min(alloc.width / cw, alloc.height / ch)))
        self._zoom  = z
        self._pan_x = (alloc.width  - cw * z) / 2 - mn_x * z
        self._pan_y = (alloc.height - ch * z) / 2 - mn_y * z
        self._da.queue_draw()

    # ── dibujo ─────────────────────────────────────────────────────────────

    def _on_draw(self, da, cr):
        alloc = da.get_allocation()
        W, H  = alloc.width, alloc.height

        cr.set_source_rgb(*self.C_BG); cr.paint()

        cr.save()
        cr.translate(self._pan_x, self._pan_y)
        cr.scale(self._zoom, self._zoom)

        # aristas
        for a, b, lbl in self._aristas_data:
            pa, pb = self._pos.get(a), self._pos.get(b)
            if not pa or not pb:
                continue
            sel = self._sel_id in (a, b)
            self._dibujar_arista(cr, pa, pb, lbl, sel)

        # nodos
        for nid, (x, y) in self._pos.items():
            self._dibujar_nodo(cr, nid, x, y)

        cr.restore()

    def _dibujar_arista(self, cr, pa, pb, lbl, sel):
        r = self.NODE_R
        ax, ay = pa; bx, by = pb
        dx, dy = bx - ax, by - ay
        dist = max(0.01, math.hypot(dx, dy))
        ux, uy = dx / dist, dy / dist
        x0, y0 = ax + ux * r, ay + uy * r
        x1, y1 = bx - ux * r, by - uy * r

        color = self.C_EDGE_S if sel else self.C_EDGE
        cr.set_source_rgba(*color, 0.95 if sel else 0.55)
        cr.set_line_width(2.4 if sel else 1.3)
        cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()

        # punta de flecha
        ang = math.atan2(y1 - y0, x1 - x0)
        sz = 8
        a1, a2 = ang + 2.6, ang - 2.6
        cr.move_to(x1, y1)
        cr.line_to(x1 + sz * math.cos(a1), y1 + sz * math.sin(a1))
        cr.line_to(x1 + sz * math.cos(a2), y1 + sz * math.sin(a2))
        cr.close_path()
        cr.set_source_rgba(*color, 0.95)
        cr.fill()

        if lbl:
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(9)
            ext = cr.text_extents(lbl)
            cr.set_source_rgba(*self.C_BG, 0.85)
            cr.rectangle(mx - ext.width/2 - 2, my - ext.height - 2,
                        ext.width + 4, ext.height + 4)
            cr.fill()
            cr.set_source_rgba(*self.C_LBL, 0.95)
            cr.move_to(mx - ext.width/2 - ext.x_bearing, my - 2)
            cr.show_text(lbl)

    def _dibujar_nodo(self, cr, nid, x, y):
        r = self.NODE_R
        sel = (nid == self._sel_id)
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.arc(x + 2, y + 2, r, 0, 2 * math.pi); cr.fill()

        color = self.C_NODE_S if sel else self.C_NODE
        cr.set_source_rgb(*color)
        cr.arc(x, y, r, 0, 2 * math.pi); cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.85 if sel else 0.35)
        cr.set_line_width(2.5 if sel else 1.2)
        cr.arc(x, y, r, 0, 2 * math.pi); cr.stroke()

        nombre = self._nodos_data.get(nid, nid)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(9)
        etiqueta = nombre if len(nombre) <= 14 else nombre[:13] + "…"
        ext = cr.text_extents(etiqueta)
        cr.set_source_rgba(*self.C_BG, 0.85)
        cr.rectangle(x - ext.width/2 - 3, y + r + 3,
                    ext.width + 6, ext.height + 6)
        cr.fill()
        cr.set_source_rgb(*self.C_TXT)
        cr.move_to(x - ext.width/2 - ext.x_bearing, y + r + ext.height + 6)
        cr.show_text(etiqueta)

    # ── interacción ────────────────────────────────────────────────────────

    def _on_press(self, da, event):
        wx, wy = self._s2w(event.x, event.y)
        if event.button == 1:
            hit = self._hit_node(wx, wy)
            if hit is not None:
                self._sel_id = hit
                if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
                    self._abrir_abm(hit)
                else:
                    self._drag_id = hit
                    px, py = self._pos[hit]
                    self._drag_ox, self._drag_oy = wx - px, wy - py
                nom = self._nodos_data.get(hit, hit)
                self._status(f"Nodo: {nom}  (id {hit})")
            else:
                self._sel_id = None
                self._drag_id = None
        elif event.button in (2, 3):
            self._panning = True
            self._pan_mx, self._pan_my = event.x, event.y
            self._pan_ox, self._pan_oy = self._pan_x, self._pan_y
        self._da.queue_draw()

    def _on_motion(self, da, event):
        btn1 = bool(event.state & Gdk.ModifierType.BUTTON1_MASK)
        if self._drag_id and btn1:
            wx, wy = self._s2w(event.x, event.y)
            self._pos[self._drag_id] = [wx - self._drag_ox, wy - self._drag_oy]
            self._da.queue_draw()
        elif self._panning:
            self._pan_x = self._pan_ox + (event.x - self._pan_mx)
            self._pan_y = self._pan_oy + (event.y - self._pan_my)
            self._da.queue_draw()

    def _on_release(self, da, event):
        self._drag_id = None
        self._panning = False

    def _on_scroll(self, da, event):
        factor = 1.15 if event.direction == Gdk.ScrollDirection.UP else 1 / 1.15
        self._set_zoom(self._zoom * factor, event.x, event.y)

    def _abrir_abm(self, nid):
        """Doble clic: intenta abrir el ABM del equipo si el id es numérico."""
        if not str(nid).isdigit():
            return
        try:
            import cabledoc as _cd
        except ImportError:
            return
        try:
            _cd._DialogoEquipo(id_equipo=nid, parent=self).run_and_destroy()
        except Exception as exc:
            self._status(f"No se pudo abrir el equipo {nid}: {exc}")

    def _status(self, txt):
        self._sb.push(self._sb.get_context_id("i"), txt)
