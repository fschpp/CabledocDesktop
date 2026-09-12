#!/usr/bin/env python3
"""
pantallas_diagrama.py — Fase 7: DiagramaConexiones en Kivy.

Equivalente a DiagramaConexiones de pantallas_avanzadas.py (GTK+Cairo).

Simplificaciones respecto al original GTK:
  - Sin análisis de impacto (requiere impacto_ui.py, basado en GTK)
  - Sin line jumps ni fan offsets
  - Sin selección múltiple / rubber band
  - Sin herramientas de alineación
  - Export a PNG via widget.export_to_png()

Lo que sí está implementado:
  - Nodos con puertos IN (izq, azul) y OUT (der, naranja) + etiquetas
  - Conexiones en LÍNEA RECTA, directo entre nodos (no puerto a puerto),
    coloreadas por equipo seleccionado
  - Pan (arrastrás espacio vacío con 1 dedo)
  - Zoom (pellizco con 2 dedos / botones toolbar)
  - Arrastrar nodos + guardar posición en BD
  - Seleccionar nodo → resalta sus conexiones
  - Doble toque → abre diálogo de equipo
  - Expandir vecinos del nodo seleccionado (modo raíz)
  - Encuadrar todo
  - Recargar desde BD
  - "Solo nombre" (compacta nodos a solo la cabecera) — modo por defecto
    en la vista global (sin raíz), para que sea legible en pantalla chica
  - Buscar (filtro de texto)
  - Export PNG

Vista global (sin equipo raíz) — virtualización por viewport
--------------------------------------------------------------
Con muchos equipos, cargar el detalle completo de todos (conectores de
cada uno) generaba ~1 consulta SQL por equipo (patrón N+1), y dibujar
cientos de nodos con puertos era lento e ilegible en un celular de
~360dp de ancho. Ahora:

  1. Se arma un ÍNDICE liviano de TODOS los equipos del grafo con una
     sola consulta bulk (id, nombre, tipo) + una sola consulta bulk de
     posiciones guardadas. Los equipos sin posición guardada se ubican
     con un layout en columnas calculado en Python (sin ir a la BD por
     cada uno).
  2. Sólo se cargan el detalle (conectores/puertos) y se renderizan los
     nodos que caen dentro del viewport visible (+ margen), con un tope
     de MAX_NODOS_GLOBAL (50). Al pasar ese máximo se prioriza lo ya
     cargado + lo más cercano al centro de la pantalla.
  3. Al paneo/zoom, se recalcula qué nodos entran y cuáles salen: los
     que salen de vista se descartan de memoria (no dibujan ni pesan);
     los que entran se cargan con una consulta bulk (no 1 por nodo).
  4. Las conexiones se filtran a las que tienen AMBOS extremos entre los
     nodos activos, y se dibujan como una línea recta simple entre el
     borde de un nodo y el otro (no hasta el puerto exacto), lo que
     además ahorra el cálculo de posición de puerto en cada redraw.
"""

import math
import os
import time
import colorsys
import hashlib

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView
from kivy.graphics import Color, Rectangle, Line, Ellipse, RoundedRectangle
from kivy.core.text import Label as CoreLabel
from kivy.clock import Clock
from kivy.metrics import dp, sp

from widgets_base import (
    mostrar_info, mostrar_error, s, _, confirmar,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from tema import BotonIcono
from modelo import Modelo

try:
    from logger_cabledoc import log_debug
except ImportError:
    def log_debug(mensaje):
        print(mensaje)


# ─── Log de tiempos ──────────────────────────────────────────────────────────
# Detallado: cada query SQL, el layout y el render quedan medidos en log.txt
# (mismo archivo que usa logger_cabledoc, con timestamp de milisegundos) para
# poder ver dónde se va el tiempo y seguir optimizando.

class _Cron:
    """Context manager: mide un bloque y lo loguea con log_debug."""

    def __init__(self, evento, detalle=""):
        self.evento = evento
        self.detalle = detalle

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        dt_ms = (time.perf_counter() - self._t0) * 1000
        extra = f" — {self.detalle}" if self.detalle else ""
        log_debug(f"DIAGRAMA· {self.evento}: {dt_ms:.1f} ms{extra}")


# ─── Constantes visuales ─────────────────────────────────────────────────────

NODE_W   = 220
HDR_H    = 28
PORT_H   = 17
PORT_PAD = 6
PORT_R   = 4

MAX_NODOS_GLOBAL   = 50     # tope de nodos activos en la vista global
MARGEN_VIEWPORT    = 0.6    # margen extra (proporcional al ancho/alto visible)
                             # para precargar nodos justo fuera de pantalla
ZOOM_DEFECTO_GLOBAL = 1.5   # 150%: zoom inicial de la vista global, centrado
SOSTENER_PARA_ARRASTRAR_SEG = 0.55  # mantener presionado un nodo para poder
                                     # arrastrarlo; un toque/drag rápido sólo
                                     # lo selecciona (no lo mueve)

C_BG       = (0.11, 0.12, 0.15)
C_GRID     = (0.16, 0.17, 0.21)
C_NODE     = (0.19, 0.21, 0.26)
C_NODE_SEL = (0.26, 0.29, 0.39)
C_NODE_B   = (0.33, 0.36, 0.46)
C_NODE_BSEL= (0.65, 0.70, 0.95)
C_PORT_IN  = (0.32, 0.62, 0.95)
C_PORT_OUT = (0.95, 0.58, 0.22)
C_CONN     = (0.48, 0.52, 0.62)
C_TXT_H    = (0.94, 0.95, 0.97)
C_TXT_SUB  = (0.58, 0.60, 0.68)
C_TXT_PORT = (0.72, 0.74, 0.80)
C_TXT_CAB  = (0.72, 0.74, 0.44)

PALETA_CONNS = [
    (0.95, 0.32, 0.32), (0.32, 0.95, 0.48), (0.32, 0.65, 0.95),
    (0.95, 0.75, 0.25), (0.80, 0.32, 0.95), (0.25, 0.90, 0.90),
    (0.95, 0.60, 0.25), (0.50, 0.95, 0.30), (0.95, 0.25, 0.65),
    (0.30, 0.50, 0.95),
]


def _tipo_color(tipo):
    h = int(hashlib.md5((tipo or "?").encode()).hexdigest()[:4], 16) % 360
    r, g, b = colorsys.hsv_to_rgb(h / 360, 0.52, 0.58)
    return (r, g, b)


def _abreviar_tex(texto, max_chars=28):
    texto = str(texto or "")
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars - 1] + "…"


# ─── Acceso a datos en bloque (sin N+1) ──────────────────────────────────────
# Reemplaza las viejas llamadas Modelo.devolver_equipo(id) /
# devolver_conectores_de_equipo(id) / devolver_posicion_en_diagrama(id)
# hechas UNA POR CADA equipo (N+1 queries) por consultas bulk con un solo
# WHERE ... IN (...), agrupadas en Python — mismo patrón que _agrupar() en
# la búsqueda global.

def _bulk_info_equipos(eq_ids):
    """id_equipo -> (nombre, tipo). Una sola consulta para todos los ids."""
    eq_ids = [i for i in eq_ids if i not in (None, "", "0")]
    if not eq_ids:
        return {}
    placeholders = ",".join("?" * len(eq_ids))
    rows = Modelo._query(
        f"SELECT eq.id_equipo, eq.nombre, COALESCE(te.nombre,'') "
        f"FROM equipo eq "
        f"LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = eq.id_tipo_equipo "
        f"WHERE eq.id_equipo IN ({placeholders})", tuple(eq_ids))
    return {str(r[0]): (s(r[1]), s(r[2])) for r in rows}


def _bulk_conectores(eq_ids):
    """id_equipo -> {'in': [...], 'out': [...]}. Una sola consulta."""
    eq_ids = [i for i in eq_ids if i not in (None, "", "0")]
    if not eq_ids:
        return {}
    placeholders = ",".join("?" * len(eq_ids))
    rows = Modelo._query(
        f"SELECT c.id_equipo, c.id_conector, c.nombre, "
        f"COALESCE(tc.nombre,'') "
        f"FROM conector c "
        f"LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
        f"WHERE c.id_equipo IN ({placeholders}) ORDER BY c.id_equipo, c.nombre",
        tuple(eq_ids))
    out = {}
    for r in rows:
        id_eq = str(r[0])
        p_in, p_out = out.setdefault(id_eq, ([], []))
        cid = str(r[1]); cnm = s(r[2]); ctp = s(r[3]).upper()
        if "IN" in ctp and "OUT" not in ctp:
            p_in.append((cid, cnm, len(p_in)))
        else:
            p_out.append((cid, cnm, len(p_out)))
    return {k: {"in": v[0], "out": v[1]} for k, v in out.items()}


def _y_bd_a_mundo(y):
    """
    Corrección de eje Y: las posiciones en la tabla
    diagrama_equipos_posicion_en_imagen fueron guardadas originalmente
    con la convención de GTK/Cairo (origen arriba-izquierda, Y crece
    hacia ABAJO). El canvas de Kivy de este diagrama usa la convención
    contraria (Y crece hacia ARRIBA, ver docstring de _CanvasDiagrama).
    Sin esta corrección, todo lo guardado aparece invertido verticalmente.
    Al no haber una altura de referencia fija (el diagrama es un lienzo
    infinito, no una imagen de tamaño conocido), la corrección correcta
    es una simple inversión de signo: preserva el orden/posición relativa
    entre nodos, sólo cambia la dirección del eje.
    """
    return -y


def _y_mundo_a_bd(y):
    """Inversa de _y_bd_a_mundo, para guardar en el mismo formato en que
    se lee (así una lectura posterior no vuelve a invertir por error)."""
    return -y


def _bulk_posiciones(eq_ids):
    """id_equipo -> (x, y) YA CORREGIDAS a convención Kivy (y-arriba).
    Una sola consulta para todos los ids."""
    eq_ids = [i for i in eq_ids if i not in (None, "", "0")]
    if not eq_ids:
        return {}
    placeholders = ",".join("?" * len(eq_ids))
    rows = Modelo._query(
        f"SELECT id_equipo, x, y FROM diagrama_equipos_posicion_en_imagen "
        f"WHERE id_equipo IN ({placeholders}) AND x IS NOT NULL",
        tuple(eq_ids))
    return {str(r[0]): (float(r[1]), _y_bd_a_mundo(float(r[2])))
            for r in rows}


def _bulk_conexiones(eq_ids=None):
    """
    Lista de aristas {id, nombre, src_eq, dst_eq}. Una sola consulta
    (CONEXIONES_AMBOS_EXTREMOS ya trae ambos extremos por fila).
    Si eq_ids se pasa, filtra al conjunto (usado en modo raíz); si no,
    trae todo el grafo (modo global).
    """
    if eq_ids is not None:
        eq_ids = [i for i in eq_ids if i not in (None, "", "0")]
        if not eq_ids:
            return []
        placeholders = ",".join("?" * len(eq_ids))
        rows = Modelo._query(
            f"SELECT * FROM CONEXIONES_AMBOS_EXTREMOS "
            f"WHERE id_equipo IN ({placeholders})", tuple(eq_ids))
        validos = set(eq_ids)
    else:
        rows = Modelo._query("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
        validos = None

    edges = []
    seen = set()
    for r in rows:
        id_cb = str(r[11])
        if id_cb in seen:
            continue
        id_ea = str(r[10]); id_eb = str(r[9])
        if validos is not None and (id_ea not in validos or id_eb not in validos):
            continue
        seen.add(id_cb)
        con_a_nom = s(r[3]).upper()
        con_a_id  = str(r[14]);  con_b_id = str(r[13])
        if "OUT" in con_a_nom:
            src_eq, src_con = id_ea, con_a_id
            dst_eq, dst_con = id_eb, con_b_id
        else:
            src_eq, src_con = id_eb, con_b_id
            dst_eq, dst_con = id_ea, con_a_id
        edges.append({
            "id": id_cb, "nombre": s(r[0]),
            "src_eq": src_eq, "src_con": src_con,
            "dst_eq": dst_eq, "dst_con": dst_con,
        })
    return edges


# ─── Widget canvas del diagrama ───────────────────────────────────────────────

class _CanvasDiagrama(StencilView):
    """
    Widget que dibuja el diagrama completo: fondo, grilla, conexiones, nodos.
    Gestiona pan / zoom / arrastre de nodos / selección.

    Hereda de StencilView (en vez de Widget) para que, al hacer zoom/pan,
    el contenido dibujado (nodos, conexiones, texto) quede recortado a los
    límites del propio widget y no se dibuje por encima de la toolbar u
    otros elementos de la interfaz.

    Sistema de coordenadas:
      - «mundo»: x→derecha, y→arriba (Kivy nativo).
      - Posición de pantalla de un punto mundo (wx, wy):
          sx = self.x + self._pan_x + wx * self._zoom
          sy = self.y + self._pan_y + wy * self._zoom
    """

    def __init__(self, popup_ref, **kwargs):
        super().__init__(**kwargs)
        self._popup = popup_ref   # referencia a DiagramaConexiones
        self._nodos = {}          # id -> dict
        self._conns = []          # list of dict
        self._sel_id = None
        self._zoom   = 1.0
        self._pan_x  = 60.0
        self._pan_y  = 60.0
        # Drag de nodo — por defecto, tocar un nodo sólo lo SELECCIONA.
        # El arrastre recién se habilita si el dedo se mantiene quieto
        # sobre el nodo por SOSTENER_PARA_ARRASTRAR_SEG (evita mover un
        # nodo sin querer al tocarlo o al pasar el dedo de largo).
        self._drag_id = None
        self._drag_ox = self._drag_oy = 0.0
        self._drag_armado = False       # True recién tras el mantener-presionado
        self._drag_pend_uid = None      # touch que podría llegar a arrastrar
        self._drag_pend_ev = None       # evento de Clock del mantener-presionado
        # Pan con un dedo
        self._pan_touch_uid = None
        self._pan_sx = self._pan_sy = 0.0
        # Pinch zoom con dos dedos
        self._pinch_touches = {}
        self._pinch_dist0 = None
        self._pinch_zoom0 = None
        # Caché de texturas de texto
        self._tex_cache = {}
        self.bind(pos=lambda *_: self._redraw(),
                  size=lambda *_: self._redraw())

    # ── Conversiones de coordenadas ──────────────────────────────────────────

    def _w2s(self, wx, wy):
        return (self.x + self._pan_x + wx * self._zoom,
                self.y + self._pan_y + wy * self._zoom)

    def _s2w(self, sx, sy):
        return ((sx - self.x - self._pan_x) / self._zoom,
                (sy - self.y - self._pan_y) / self._zoom)

    def viewport_mundo(self, margen=0.0):
        """Rectángulo (x1, y1, x2, y2) en coordenadas mundo que cubre el
        área visible del canvas, expandido un `margen` proporcional al
        tamaño visible (para precargar nodos justo fuera de pantalla)."""
        x1, y1 = self._s2w(self.x, self.y)
        x2, y2 = self._s2w(self.x + self.width, self.y + self.height)
        mw = (x2 - x1) * margen
        mh = (y2 - y1) * margen
        return (x1 - mw, y1 - mh, x2 + mw, y2 + mh)

    def _hit_node(self, wx, wy):
        for nodo in reversed(list(self._nodos.values())):
            if (nodo["x"] <= wx <= nodo["x"] + nodo["ancho"] and
                    nodo["y"] <= wy <= nodo["y"] + nodo["alto"]):
                return nodo
        return None

    def _port_pos(self, nodo, con_id, side):
        """Posición mundo del puerto de un conector (modo raíz, original)."""
        lst = nodo["in"] if side == "in" else nodo["out"]
        top = nodo["y"] + nodo["alto"]
        tipo_h = 10
        for idx, (cid, _n, _i) in enumerate(lst):
            if cid == con_id:
                py = top - HDR_H - tipo_h - PORT_PAD - idx * PORT_H - PORT_H / 2
                px = nodo["x"] if side == "in" else nodo["x"] + nodo["ancho"]
                return px, py
        py = nodo["y"] + nodo["alto"] / 2
        px = nodo["x"] if side == "in" else nodo["x"] + nodo["ancho"]
        return px, py

    # ── Caché de texto ───────────────────────────────────────────────────────

    def _get_tex(self, texto, size=11, bold=False,
                 color=(0.94, 0.95, 0.97, 1)):
        key = (_abreviar_tex(texto, 40), int(size), bold, color)
        if key not in self._tex_cache:
            lbl = CoreLabel(text=_abreviar_tex(texto, 40),
                            font_size=size, bold=bold, color=color)
            lbl.refresh()
            self._tex_cache[key] = lbl.texture
        return self._tex_cache[key]

    def _draw_text_centered(self, texto, cx, cy, size=11, bold=False,
                            color=(0.94, 0.95, 0.97, 1)):
        tex = self._get_tex(texto, size, bold, color)
        if not tex:
            return
        tw, th = tex.size
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(cx - tw / 2, cy - th / 2),
                  size=(tw, th))

    def _draw_text_left(self, texto, lx, cy, size=10,
                        color=(0.72, 0.74, 0.80, 1)):
        tex = self._get_tex(texto, size, False, color)
        if not tex:
            return
        tw, th = tex.size
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(lx, cy - th / 2), size=(tw, th))

    def _draw_text_right(self, texto, rx, cy, size=10,
                         color=(0.72, 0.74, 0.80, 1)):
        tex = self._get_tex(texto, size, False, color)
        if not tex:
            return
        tw, th = tex.size
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(rx - tw, cy - th / 2), size=(tw, th))

    def _draw_text_cable(self, texto, cx, cy, size):
        """Etiqueta de nombre de cable con fondo, para que se lea bien
        aunque quede dibujada sobre un nodo u otra conexión."""
        tex = self._get_tex(_abreviar_tex(texto, 24), size, True,
                            (1, 1, 1, 1))
        if not tex:
            return
        tw, th = tex.size
        pad = 3
        Color(0.08, 0.09, 0.11, 0.80)
        Rectangle(pos=(cx - tw / 2 - pad, cy - th / 2 - pad),
                  size=(tw + 2 * pad, th + 2 * pad))
        Color(*C_TXT_CAB, 1)
        Line(rectangle=(cx - tw / 2 - pad, cy - th / 2 - pad,
                        tw + 2 * pad, th + 2 * pad), width=0.8)
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(cx - tw / 2, cy - th / 2), size=(tw, th))

    # ── Dibujo principal ─────────────────────────────────────────────────────

    def _redraw(self, *_a):
        t0 = time.perf_counter()
        z = self._zoom
        self.canvas.clear()
        W, H = self.size

        # Colores de las conexiones del nodo seleccionado
        conn_colors = self._calc_conn_colors()
        solo_nombre = self._popup._solo_nombre
        # Etiquetas de cable: se acumulan mientras se dibujan las conexiones
        # y se pintan al final (después de los nodos) para que queden
        # siempre por encima del resto de los elementos del diagrama.
        self._pending_labels = []

        with self.canvas:
            # ── Fondo ──────────────────────────────────────────────────────
            Color(*C_BG, 1)
            Rectangle(pos=self.pos, size=self.size)

            # ── Grilla ─────────────────────────────────────────────────────
            GRID = 40 * z
            ox = self.x + self._pan_x % GRID
            oy = self.y + self._pan_y % GRID
            Color(*C_GRID, 1)
            x = ox
            while x < self.x + W:
                Line(points=[x, self.y, x, self.y + H], width=0.5)
                x += GRID
            y = oy
            while y < self.y + H:
                Line(points=[self.x, y, self.x + W, y], width=0.5)
                y += GRID

            # ── Conexiones (línea recta, directo nodo a nodo) ────────────────
            for conn in self._conns:
                self._draw_conn(conn, conn_colors, solo_nombre)

            # ── Nodos ──────────────────────────────────────────────────────
            for nodo in self._nodos.values():
                self._draw_node(nodo, solo_nombre)

            # ── Conexión interna (Módulo Patchera), si está activa ─────────
            self._draw_conexion_interna()

            # ── Etiquetas de cable (por encima de nodos y conexiones) ──────
            for texto, lx, ly, size in self._pending_labels:
                self._draw_text_cable(texto, lx, ly, size)

        log_debug(
            f"DIAGRAMA· render: {(time.perf_counter() - t0) * 1000:.1f} ms"
            f" — {len(self._nodos)} nodos, {len(self._conns)} conexiones")

        minimap = getattr(self._popup, "_minimap", None)
        if minimap is not None and self._popup._id_inicio is None:
            minimap._redraw()

    def _draw_conexion_interna(self):
        """Overlay punteado que muestra el comportamiento interno de un
        módulo patchera (bridge A_BACK-B_BACK, o desvío hacia A_FRONT/
        B_FRONT según qué extremo tenga cable externo conectado)."""
        info = getattr(self._popup, "_interna", None)
        if not info:
            return
        nodo = self._nodos.get(info["nodo_id"])
        if not nodo:
            return
        z = self._zoom
        colores_linea = [(0.95, 0.85, 0.20), (0.30, 0.80, 0.95),
                        (0.95, 0.40, 0.75), (0.50, 0.90, 0.40)]
        color_muerto = (0.55, 0.55, 0.55)

        for i, (punto_a, punto_b) in enumerate(info["segmentos"]):
            cid_a, lado_a = punto_a
            cid_b, lado_b = punto_b
            wx0, wy0 = self._port_pos(nodo, cid_a, lado_a)
            wx1, wy1 = self._port_pos(nodo, cid_b, lado_b)
            x0, y0 = self._w2s(wx0, wy0)
            x1, y1 = self._w2s(wx1, wy1)
            Color(*colores_linea[i % len(colores_linea)], 0.95)
            Line(points=[x0, y0, x1, y1], width=max(1.5, 2.0 * z),
                dash_length=max(4, 6 * z), dash_offset=max(3, 4 * z))

        for cid, lado in info["muertos"]:
            wx, wy = self._port_pos(nodo, cid, lado)
            x, y = self._w2s(wx, wy)
            r = max(5, 7 * z)
            Color(*color_muerto, 0.95)
            Line(points=[x - r, y - r, x + r, y + r], width=max(1.5, 2.0 * z))
            Line(points=[x - r, y + r, x + r, y - r], width=max(1.5, 2.0 * z))

    def _borde_mas_cercano(self, nodo, hacia_x, hacia_y):
        """Punto mundo sobre el borde izq/der del nodo, el más cercano al
        punto (hacia_x, hacia_y) — usado para que la línea recta de la
        conexión salga del lado del nodo que apunta hacia el otro extremo."""
        cx = nodo["x"] + nodo["ancho"] / 2
        cy = nodo["y"] + nodo["alto"] / 2
        if hacia_x >= cx:
            return nodo["x"] + nodo["ancho"], cy
        return nodo["x"], cy

    def _draw_conn(self, conn, conn_colors, solo_nombre):
        src = self._nodos.get(conn["src_eq"])
        dst = self._nodos.get(conn["dst_eq"])
        if not src or not dst:
            return
        z = self._zoom
        modo_raiz = self._popup._id_inicio is not None

        if modo_raiz:
            # ── Modo con equipo raíz: funcionalidad ORIGINAL sin cambios
            #    (Bézier puerto-a-puerto, o borde-a-borde si "Solo nombre") ──
            if solo_nombre:
                x0, y0 = self._w2s(src["x"] + src["ancho"], src["y"] + src["alto"] / 2)
                x1, y1 = self._w2s(dst["x"], dst["y"] + dst["alto"] / 2)
            else:
                wx0, wy0 = self._port_pos(src, conn["src_con"], "out")
                wx1, wy1 = self._port_pos(dst, conn["dst_con"], "in")
                x0, y0 = self._w2s(wx0, wy0)
                x1, y1 = self._w2s(wx1, wy1)
        else:
            # ── Vista global: línea recta directo entre nodos (no puerto a
            #    puerto), sale/llega del borde del nodo más cercano al otro
            #    extremo — más rápida de calcular y más legible con muchos
            #    nodos en pantalla chica. ──
            cx_dst = dst["x"] + dst["ancho"] / 2
            cy_dst = dst["y"] + dst["alto"] / 2
            cx_src = src["x"] + src["ancho"] / 2
            cy_src = src["y"] + src["alto"] / 2
            wx0, wy0 = self._borde_mas_cercano(src, cx_dst, cy_dst)
            wx1, wy1 = self._borde_mas_cercano(dst, cx_src, cy_src)
            x0, y0 = self._w2s(wx0, wy0)
            x1, y1 = self._w2s(wx1, wy1)

        custom = conn_colors.get(conn["id"])
        sel_node = self._sel_id in (conn["src_eq"], conn["dst_eq"])
        if custom:
            rgb = custom
            alpha = 0.92
            lw = max(1.5, 2.2 * z)
        elif sel_node:
            rgb = (0.95, 0.82, 0.28)
            alpha = 0.88
            lw = max(1.5, 2.2 * z)
        else:
            rgb = C_CONN
            alpha = 0.55
            lw = max(0.8, 1.2 * z)

        if modo_raiz:
            # Curva Bézier muestreada (original)
            dx = max(abs(x1 - x0) * 0.5, 80 * z)
            cp1x, cp1y = x0 + dx, y0
            cp2x, cp2y = x1 - dx, y1
            pts = []
            N = 20
            for i in range(N + 1):
                t = i / N
                u = 1 - t
                px = u**3*x0 + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*x1
                py = u**3*y0 + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*y1
                pts.extend([px, py])
            Color(*rgb, alpha)
            Line(points=pts, width=lw)
        else:
            pts = [x0, y0, x1, y1]
            Color(*rgb, alpha)
            Line(points=pts, width=lw)

        # Punta de flecha
        angle = math.atan2(y1 - y0, x1 - x0)
        sz = max(5, 8 * z)
        ax1 = x1 + sz * math.cos(angle + 2.5)
        ay1 = y1 + sz * math.sin(angle + 2.5)
        ax2 = x1 + sz * math.cos(angle - 2.5)
        ay2 = y1 + sz * math.sin(angle - 2.5)
        Color(*rgb, min(1.0, alpha + 0.1))
        Line(points=[ax1, ay1, x1, y1, ax2, ay2], width=lw)

        # Etiqueta(s) del cable (encoladas en self._pending_labels, ver
        # _redraw). Una en cada extremo, tanto en modo raíz como global.
        if conn["nombre"] and z >= 0.5:
            size = max(7, int(8 * z))
            if modo_raiz:
                lx0 = (x0 + pts[2]) / 2
                ly0 = (y0 + pts[3]) / 2 + 10 * z
                self._pending_labels.append((conn["nombre"], lx0, ly0, size))
                lx1 = (x1 + pts[-4]) / 2
                ly1 = (y1 + pts[-3]) / 2 + 10 * z
                self._pending_labels.append((conn["nombre"], lx1, ly1, size))
            else:
                # Recta directa: una etiqueta cerca de cada punta, no sólo
                # en el medio, para poder leer el cable desde cualquiera
                # de los dos equipos que conecta.
                lx0 = x0 + (x1 - x0) * 0.22
                ly0 = y0 + (y1 - y0) * 0.22 + 10 * z
                self._pending_labels.append((conn["nombre"], lx0, ly0, size))
                lx1 = x0 + (x1 - x0) * 0.78
                ly1 = y0 + (y1 - y0) * 0.78 + 10 * z
                self._pending_labels.append((conn["nombre"], lx1, ly1, size))

    def _draw_node(self, nodo, solo_nombre):
        z = self._zoom
        x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
        sx, sy = self._w2s(x, y)
        sw, sh = w * z, h * z
        sel = (nodo["id"] == self._sel_id)
        rc, gc, bc = nodo["color"]

        # Sombra
        Color(0, 0, 0, 0.28)
        Rectangle(pos=(sx + 3 * z, sy - 3 * z), size=(sw, sh))

        # Cuerpo
        Color(*(C_NODE_SEL if sel else C_NODE), 1)
        Rectangle(pos=(sx, sy), size=(sw, sh))

        # Cabecera (borde superior del nodo en Kivy: sy + sh - HDR_H*z)
        hdr_sy = sy + sh - HDR_H * z
        Color(rc * 0.85, gc * 0.85, bc * 0.85, 1)
        Rectangle(pos=(sx, hdr_sy), size=(sw, HDR_H * z))

        # Borde
        Color(*(C_NODE_BSEL if sel else C_NODE_B), 1)
        Line(rectangle=(sx, sy, sw, sh),
             width=max(1.0, (2.0 if sel else 1.0) * z))

        # Nombre en cabecera
        self._draw_text_centered(
            nodo["nombre"], sx + sw / 2, hdr_sy + HDR_H * z / 2,
            size=max(8, int(10 * z)), bold=True, color=(*C_TXT_H, 1))

        if solo_nombre:
            return

        # Subtítulo (tipo de equipo)
        tipo_y = hdr_sy - 8 * z
        if z >= 0.6:
            self._draw_text_centered(
                nodo["tipo"], sx + sw / 2, tipo_y,
                size=max(7, int(8 * z)), color=(*C_TXT_SUB, 0.80))

        # Puertos IN (izquierda) — sólo decorativos, la línea de conexión
        # ya no sale de acá (ver _draw_conn), así que no dependen de
        # tener los datos completos para dibujarse bien.
        top = sy + sh
        tipo_h = 10 * z
        body_top_y = hdr_sy - tipo_h
        for idx, (cid, cnm, _) in enumerate(nodo.get("in", [])):
            py = body_top_y - PORT_PAD * z - idx * PORT_H * z - PORT_H * z / 2
            px = sx
            Color(*C_PORT_IN, 1)
            r = PORT_R * z
            Ellipse(pos=(px - r, py - r), size=(r * 2, r * 2))
            Color(0, 0, 0, 1)
            Line(circle=(px, py, r), width=0.8)
            if z >= 0.5:
                self._draw_text_left(
                    cnm, px + r + 3 * z, py,
                    size=max(7, int(8 * z)), color=(*C_TXT_PORT, 1))

        # Puertos OUT (derecha)
        for idx, (cid, cnm, _) in enumerate(nodo.get("out", [])):
            py = body_top_y - PORT_PAD * z - idx * PORT_H * z - PORT_H * z / 2
            px = sx + sw
            Color(*C_PORT_OUT, 1)
            r = PORT_R * z
            Ellipse(pos=(px - r, py - r), size=(r * 2, r * 2))
            Color(0, 0, 0, 1)
            Line(circle=(px, py, r), width=0.8)
            if z >= 0.5:
                self._draw_text_right(
                    cnm, px - r - 3 * z, py,
                    size=max(7, int(8 * z)), color=(*C_TXT_PORT, 1))

    def _calc_conn_colors(self):
        if not self._sel_id:
            return {}
        sel_conns = [c for c in self._conns
                     if c["src_eq"] == self._sel_id
                     or c["dst_eq"] == self._sel_id]
        colors = {}
        n = len(sel_conns)
        for i, conn in enumerate(sel_conns):
            colors[conn["id"]] = PALETA_CONNS[i % len(PALETA_CONNS)]
        return colors

    # ── Encuadrar todo (nodos activos) ────────────────────────────────────────

    def fit_all(self):
        if not self._nodos:
            return
        xs  = [n["x"] for n in self._nodos.values()]
        ys  = [n["y"] for n in self._nodos.values()]
        x2s = [n["x"] + n["ancho"] for n in self._nodos.values()]
        y2s = [n["y"] + n["alto"] for n in self._nodos.values()]
        self._fit_bbox(min(xs), min(ys), max(x2s), max(y2s))

    def fit_bbox_indice(self, indice):
        """Encuadra usando TODAS las posiciones del índice (vista global),
        no sólo las de los nodos actualmente cargados en memoria."""
        if not indice:
            return
        xs  = [info["x"] for info in indice.values()]
        ys  = [info["y"] for info in indice.values()]
        self._fit_bbox(min(xs), min(ys), max(xs) + NODE_W, max(ys) + HDR_H)

    def _fit_bbox(self, mn_x, mn_y, mx_x, mx_y):
        mn_x -= 40; mn_y -= 40; mx_x += 40; mx_y += 40
        cw = mx_x - mn_x;  ch = mx_y - mn_y
        W, H = self.size
        if W < 10 or H < 10 or cw < 1 or ch < 1:
            return
        z = max(0.05, min(2.0, min(W / cw, H / ch)))
        self._zoom  = z
        self._pan_x = (W - cw * z) / 2 - mn_x * z
        self._pan_y = (H - ch * z) / 2 - mn_y * z
        self._popup._lbl_zoom.text = f"{int(z * 100)}%"
        self._redraw()

    # ── Touch ────────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)

        # Registrar para pinch zoom
        self._pinch_touches[touch.uid] = (touch.x, touch.y)
        if len(self._pinch_touches) == 2:
            pts = list(self._pinch_touches.values())
            self._pinch_dist0 = math.hypot(
                pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
            self._pinch_zoom0 = self._zoom
            self._cancelar_arrastre_pendiente()  # cancelar drag si había
            return True

        wx, wy = self._s2w(touch.x, touch.y)
        hit = self._hit_node(wx, wy)

        if hit:
            if touch.is_double_tap:
                self._abrir_equipo(hit["id"])
                return True
            # Tocar un nodo SIEMPRE lo selecciona de inmediato. El arrastre
            # recién se habilita si el dedo se mantiene quieto encima del
            # nodo por SOSTENER_PARA_ARRASTRAR_SEG — así un toque rápido o
            # un intento de paneo que empieza sobre un nodo no lo mueve.
            if hit["id"] != self._sel_id:
                interna = getattr(self._popup, "_interna", None)
                if interna and interna["nodo_id"] != hit["id"]:
                    self._popup._limpiar_conexion_interna()
            self._sel_id = hit["id"]
            self._drag_ox = wx - hit["x"]
            self._drag_oy = wy - hit["y"]
            self._drag_armado = False
            self._drag_pend_uid = touch.uid
            id_nodo = hit["id"]
            self._drag_pend_ev = Clock.schedule_once(
                lambda *_: self._armar_arrastre(id_nodo, touch.uid),
                SOSTENER_PARA_ARRASTRAR_SEG)
        else:
            if touch.is_double_tap and self._sel_id:
                self._sel_id = None
                self._popup._limpiar_conexion_interna()
                self._redraw()
                return True
            self._pan_touch_uid = touch.uid
            self._pan_sx = touch.x - self._pan_x
            self._pan_sy = touch.y - self._pan_y

        self._redraw()
        return True

    def _armar_arrastre(self, id_nodo, touch_uid):
        """Se dispara tras mantener el dedo quieto sobre un nodo: recién
        ahora un movimiento del dedo lo arrastra."""
        if self._drag_pend_uid == touch_uid and id_nodo in self._nodos:
            self._drag_armado = True
            self._drag_id = id_nodo

    def _cancelar_arrastre_pendiente(self):
        if self._drag_pend_ev:
            self._drag_pend_ev.cancel()
        self._drag_pend_ev = None
        self._drag_pend_uid = None
        self._drag_armado = False
        self._drag_id = None

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False

        # Pinch zoom
        if touch.uid in self._pinch_touches:
            self._pinch_touches[touch.uid] = (touch.x, touch.y)
            if (len(self._pinch_touches) == 2
                    and self._pinch_dist0 and self._pinch_zoom0):
                pts = list(self._pinch_touches.values())
                dist = math.hypot(pts[1][0] - pts[0][0],
                                  pts[1][1] - pts[0][1])
                new_z = max(0.05, min(4.0,
                            self._pinch_zoom0 * dist / self._pinch_dist0))
                self._zoom = new_z
                self._popup._lbl_zoom.text = f"{int(new_z * 100)}%"
                self._redraw()
                return True

        # Arrastrar nodo — sólo si ya se armó con el mantener-presionado.
        if self._drag_armado and self._drag_id and touch.uid == self._drag_pend_uid:
            wx, wy = self._s2w(touch.x, touch.y)
            nd = self._nodos.get(self._drag_id)
            if nd:
                nd["x"] = wx - self._drag_ox
                nd["y"] = wy - self._drag_oy
            self._redraw()
            return True

        # Un movimiento sobre un nodo que todavía no armó el arrastre no
        # hace nada (ni mueve el nodo ni panea) — por diseño, para que
        # tocar-y-arrastrar rápido sólo deje seleccionado el nodo.
        if self._drag_pend_uid == touch.uid:
            return True

        # Pan
        if touch.uid == self._pan_touch_uid:
            self._pan_x = touch.x - self._pan_sx
            self._pan_y = touch.y - self._pan_sy
            self._redraw()
            self._popup._viewport_cambio(permitir_snap=False)
            return True

        return False

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self._pinch_touches.pop(touch.uid, None)
        habia_pinch = self._pinch_dist0 is not None
        if len(self._pinch_touches) < 2:
            self._pinch_dist0 = None

        if touch.uid == self._drag_pend_uid:
            if self._drag_armado and self._drag_id:
                nd = self._nodos.get(self._drag_id)
                if nd and self._popup._id_inicio is None:
                    Modelo.guardar_posicion_en_diagrama(
                        nd["id"], int(nd["x"]), int(_y_mundo_a_bd(nd["y"])))
                    # Reflejar la nueva posición en el índice global para
                    # que no se "salte" al recalcular qué nodos están
                    # visibles. (self._indice guarda en convención mundo.)
                    idx = self._popup._indice.get(nd["id"])
                    if idx:
                        idx["x"], idx["y"] = nd["x"], nd["y"]
            self._cancelar_arrastre_pendiente()

        fue_pan = touch.uid == self._pan_touch_uid
        if fue_pan:
            self._pan_touch_uid = None

        if fue_pan or habia_pinch:
            self._popup._viewport_cambio(inmediato=False, permitir_snap=False)

        return True

    # ── Acciones ─────────────────────────────────────────────────────────────

    def _abrir_equipo(self, eq_id):
        from pantallas_equipos import DialogoEquipo
        DialogoEquipo(id_equipo=eq_id,
                      on_guardado=lambda: None).open()

    def set_zoom(self, z):
        self._zoom = max(0.05, min(4.0, z))
        self._popup._lbl_zoom.text = f"{int(self._zoom * 100)}%"
        self._redraw()
        self._popup._viewport_cambio(inmediato=False, permitir_snap=False)


# ─── Minimapa (vista global) ──────────────────────────────────────────────────

class _MinimapDiagrama(Widget):
    """
    Minimapa en miniatura de TODOS los equipos del grafo (sin dibujar
    cables), pensado para orientarse rápido en pantalla chica y saltar a
    otra zona del diagrama tocando o arrastrando el dedo dentro de él.
    Sólo tiene sentido en la vista global (sin equipo raíz): en modo raíz
    queda oculto.

    Se posiciona superpuesto sobre el canvas (esquina inferior derecha),
    con un cuadro que marca qué parte del diagrama se está viendo ahora.
    Cada equipo se dibuja como una barrita del color de su tipo (mismo
    color que usa el nodo en el diagrama grande), para reconocer de un
    vistazo dónde están agrupados los distintos tipos de equipo.
    """

    MARGEN_PX = 8
    RADIO = dp(10)

    def __init__(self, popup_ref, **kwargs):
        super().__init__(**kwargs)
        self._popup = popup_ref
        self._bbox = None   # (mn_x, mn_y, mx_x, mx_y) del índice completo
        self._arrastrando = False
        self.bind(pos=lambda *_: self._redraw(), size=lambda *_: self._redraw())

    def actualizar_bbox(self):
        """Recalcula el rectángulo que cubre TODOS los nodos del índice
        (excluyendo cables/conexiones, sólo posiciones de equipo). Se
        llama una vez después de cargar/recargar la vista global — no
        hace falta recalcularlo en cada paneo."""
        indice = self._popup._indice
        if not indice:
            self._bbox = None
            self._redraw()
            return
        xs = [i["x"] for i in indice.values()]
        ys = [i["y"] for i in indice.values()]
        self._bbox = (min(xs), min(ys), max(xs) + NODE_W, max(ys) + HDR_H)
        self._redraw()

    def _escala(self):
        mn_x, mn_y, mx_x, mx_y = self._bbox
        ancho_m = max(1.0, mx_x - mn_x)
        alto_m  = max(1.0, mx_y - mn_y)
        pad = self.MARGEN_PX
        return min((self.width - 2 * pad) / ancho_m,
                  (self.height - 2 * pad) / alto_m)

    def _mundo_a_local(self, wx, wy):
        mn_x, mn_y, _, _ = self._bbox
        pad = self.MARGEN_PX
        escala = self._escala()
        return (self.x + pad + (wx - mn_x) * escala,
               self.y + pad + (wy - mn_y) * escala)

    def _local_a_mundo(self, lx, ly):
        mn_x, mn_y, _, _ = self._bbox
        pad = self.MARGEN_PX
        escala = self._escala()
        return (mn_x + (lx - self.x - pad) / escala,
               mn_y + (ly - self.y - pad) / escala)

    def _redraw(self, *_a):
        self.canvas.clear()
        with self.canvas:
            Color(0.07, 0.08, 0.10, 0.90)
            RoundedRectangle(pos=self.pos, size=self.size,
                            radius=[self.RADIO])
            Color(0.40, 0.44, 0.54, 1)
            Line(rounded_rectangle=(*self.pos, *self.size, self.RADIO),
                width=1.2)

        # Etiqueta "mapa" en la esquina superior izquierda.
        tex = CoreLabel(text=_("mapa"), font_size=sp(9),
                        color=(0.75, 0.77, 0.82, 1))
        tex.refresh()
        if tex.texture:
            tw, th = tex.texture.size
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex.texture,
                          pos=(self.x + self.MARGEN_PX,
                              self.y + self.height - th - self.MARGEN_PX + 2),
                          size=(tw, th))

        if not self._bbox:
            return

        indice = self._popup._indice
        with self.canvas:
            # Una barrita por equipo, coloreada por tipo — SIN cables.
            bw = max(1.5, dp(2.2))
            bh = max(3, dp(6))
            for info in indice.values():
                lx, ly = self._mundo_a_local(info["x"] + NODE_W / 2,
                                            info["y"] + HDR_H / 2)
                rc, gc, bc = _tipo_color(info["tipo"])
                Color(rc, gc, bc, 0.95)
                Rectangle(pos=(lx - bw / 2, ly - bh / 2), size=(bw, bh))

            # Rectángulo: qué parte del diagrama se ve ahora mismo.
            x1, y1, x2, y2 = self._popup._canvas.viewport_mundo(0.0)
            lx1, ly1 = self._mundo_a_local(x1, y1)
            lx2, ly2 = self._mundo_a_local(x2, y2)
            Color(0.95, 0.75, 0.20, 0.95)
            Line(rectangle=(min(lx1, lx2), min(ly1, ly2),
                           abs(lx2 - lx1), abs(ly2 - ly1)), width=1.4)

    # ── Tap-and-drag: mientras el dedo se mueve dentro del minimapa, la
    #    ventana principal lo sigue en tiempo real. ──

    def on_touch_down(self, touch):
        if self._popup._id_inicio is not None or self.opacity <= 0:
            return False
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        self._arrastrando = True
        if self._bbox:
            wx, wy = self._local_a_mundo(touch.x, touch.y)
            self._popup._centrar_en(wx, wy)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self or not self._arrastrando:
            return False
        if self._bbox:
            wx, wy = self._local_a_mundo(touch.x, touch.y)
            self._popup._centrar_en(wx, wy)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self._arrastrando = False
        return True


# ─── Popup principal ──────────────────────────────────────────────────────────

class DiagramaConexiones(Popup):
    """
    Equivalente a DiagramaConexiones(GTK). Popup de pantalla completa con
    toolbar + canvas de diagrama de nodos.
    """

    def __init__(self, id_equipo=None, **kwargs):
        self._id_inicio = str(id_equipo) if id_equipo else None
        # Vista global (sin raíz): arranca en modo compacto por defecto,
        # así el diagrama es legible y liviano en pantalla de celular.
        self._solo_nombre = self._id_inicio is None

        # ── Estado de la vista global (índice + virtualización) ────────────
        self._indice = {}        # id -> {"nombre","tipo","x","y"} (TODOS)
        self._edges_idx = []     # aristas del grafo completo
        self._activos = set()    # ids actualmente cargados/dibujados
        self._recalc_ev = None   # evento de Clock pendiente (debounce)

        # ── Conexión interna (Módulo Patchera) — sólo modo equipo ──────────
        self._interna = None     # None | {"nodo_id","segmentos","muertos"}

        # ── Layout ──────────────────────────────────────────────────────────
        root = BoxLayout(orientation="vertical", spacing=0)

        # La toolbar original (selección + 3 botones + toggle + buscador +
        # zoom + PNG, todo en una fila) sumaba muy por encima de 360dp.
        # Se separa en 2 filas: arriba selección+buscador (flexibles),
        # abajo botones de acción y zoom en scroll horizontal.
        tb_top = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4),
                          padding=(dp(4), 0))
        self._lbl_sel = Label(text=_("Sin selección"), size_hint_x=0.4,
                              font_size=FUENTE_CHICA, halign="left",
                              valign="middle", shorten=True,
                              shorten_from="right")
        self._lbl_sel.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        tb_top.add_widget(self._lbl_sel)
        self._entry_busq = TextInput(
            hint_text=_("Buscar equipo…"), multiline=False,
            font_size=FUENTE_CHICA)
        self._entry_busq.bind(text=self._on_buscar)
        tb_top.add_widget(self._entry_busq)
        btn_cerrar_top = BotonIcono(icono="cerrar", clave_icono="texto",
                                   tamano=dp(34))
        btn_cerrar_top.bind(on_release=lambda *_a: self.dismiss())
        tb_top.add_widget(btn_cerrar_top)
        root.add_widget(tb_top)

        tb = ScrollView(size_hint_y=None, height=ALTO_BOTON,
                        do_scroll_y=False, bar_width=dp(4))
        tb_inner = BoxLayout(size_hint_x=None, height=ALTO_BOTON, spacing=dp(4),
                            padding=(dp(4), 0))
        tb_inner.bind(minimum_width=tb_inner.setter("width"))

        for etiq, fn in [
            (_("Encuadrar"), lambda *_: self._encuadrar()),
            (_("Expandir"),  lambda *_: self._expandir()),
            (_("Recargar"),  lambda *_: self._recargar()),
        ]:
            b = Button(text=etiq, size_hint_x=None, width=dp(110),
                      font_size=FUENTE_CHICA)
            b.bind(on_release=fn)
            tb_inner.add_widget(b)

        self._btn_solo = ToggleButton(text=_("Solo nombre"), size_hint_x=None,
                                      width=dp(110), font_size=FUENTE_CHICA,
                                      state="down" if self._solo_nombre else "normal")
        self._btn_solo.bind(on_press=self._toggle_solo)
        tb_inner.add_widget(self._btn_solo)

        self._btn_interna = ToggleButton(
            text=_("Conexión interna"), size_hint_x=None,
            width=dp(150), font_size=FUENTE_CHICA,
            disabled=self._id_inicio is None)
        self._btn_interna.bind(on_press=self._toggle_conexion_interna)
        tb_inner.add_widget(self._btn_interna)

        tb_inner.add_widget(Label(text=_("Zoom:"), size_hint_x=None,
                                  width=dp(44), font_size=FUENTE_CHICA))
        self._lbl_zoom = Label(text="100%", size_hint_x=None, width=dp(48),
                               font_size=FUENTE_CHICA)
        tb_inner.add_widget(self._lbl_zoom)
        for etiq, factor in [("+", 1.25), ("-", 1/1.25)]:
            b = Button(text=etiq, size_hint_x=None, width=dp(38),
                      font_size=FUENTE_NORMAL)
            b.bind(on_release=lambda _b, f=factor:
                   self._canvas.set_zoom(self._canvas._zoom * f))
            tb_inner.add_widget(b)

        btn_png = Button(text="PNG", size_hint_x=None, width=dp(80),
                         font_size=FUENTE_CHICA)
        btn_png.bind(on_release=lambda *_: self._exportar_png())
        tb_inner.add_widget(btn_png)

        tb.add_widget(tb_inner)
        root.add_widget(tb)

        # Canvas del diagrama (ya soporta pinch-to-zoom con 2 dedos y pan
        # con 1 dedo — ver _CanvasDiagrama más abajo, no necesita cambios
        # para celular más allá de lo que ya traía), con el minimapa
        # superpuesto en la esquina inferior derecha (sólo vista global).
        # El botón "Cerrar" va en la barra superior, fuera del canvas, para
        # que nunca quede tapando el minimapa.
        canvas_cont = FloatLayout()
        self._canvas = _CanvasDiagrama(popup_ref=self)
        canvas_cont.add_widget(self._canvas)

        self._minimap = _MinimapDiagrama(
            popup_ref=self, size_hint=(None, None),
            size=(dp(120), dp(120)), opacity=0)

        def _reubicar_minimap(*_a):
            # Acotado a los límites del propio canvas_cont, aunque todavía
            # no tenga su tamaño final asignado (evita que quede fuera de
            # lugar en el primer frame, antes de que Kivy termine el
            # layout).
            mw, mh = self._minimap.size
            cw = max(canvas_cont.width, mw + dp(16))
            ch = max(canvas_cont.height, mh + dp(16))
            self._minimap.pos = (cw - mw - dp(8), dp(8))
        canvas_cont.bind(size=_reubicar_minimap)
        _reubicar_minimap()
        canvas_cont.add_widget(self._minimap)

        root.add_widget(canvas_cont)

        # Status bar
        self._lbl_status = Label(text=_("Cargando…"), size_hint_y=None,
                                 height=dp(22), font_size=sp(10),
                                 color=(0.6, 0.6, 0.6, 1))
        root.add_widget(self._lbl_status)

        super().__init__(title=_("Diagrama de conexiones"),
                         content=root, size_hint=(1, 1), **kwargs)
        self.bind(on_open=lambda *_: Clock.schedule_once(self._cargar_delayed, 0.1))

    def _cargar_delayed(self, *_a):
        self._cargar(self._id_inicio)

    # ── Carga de datos ───────────────────────────────────────────────────────

    def _cargar(self, id_inicio=None):
        t_total0 = time.perf_counter()
        self._canvas._nodos.clear()
        self._canvas._conns.clear()
        self._canvas._sel_id = None
        self._canvas._tex_cache.clear()
        self._indice = {}
        self._edges_idx = []
        self._activos = set()
        self._minimap.opacity = 0 if id_inicio else 1

        if id_inicio:
            self._cargar_modo_raiz(id_inicio)
        else:
            self._cargar_modo_global()

        _log_total = (time.perf_counter() - t_total0) * 1000
        log_debug(f"DIAGRAMA· _cargar total: {_log_total:.1f} ms "
                 f"— modo={'raiz' if id_inicio else 'global'}")

    # ── Modo raíz: equipo + vecinos directos (grafo chico, carga completa) ──

    def _cargar_modo_raiz(self, id_inicio):
        """
        Modo con equipo raíz: FUNCIONALIDAD ORIGINAL, sin cambios respecto
        a como funcionaba antes de optimizar la vista global. Sigue
        haciendo una consulta por equipo (equipo + conectores) — no hace
        falta optimizarlo porque acá el conjunto es chico (el equipo
        elegido + sus vecinos directos), no todo el grafo.
        """
        with _Cron("ids_equipos (raiz)"):
            eq_ids = {str(id_inicio)}
            rows = Modelo._query(
                "SELECT DISTINCT id_equipo, \"id_equipo:1\" "
                "FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo=?",
                (id_inicio,))
            for r in rows:
                eq_ids.add(str(r[1]))

        nodos = self._canvas._nodos
        with _Cron("query_equipos+conectores (1 x equipo, original)",
                  f"n={len(eq_ids)}"):
            for id_eq in eq_ids:
                rows_eq = Modelo.devolver_equipo(id_eq)
                if not rows_eq:
                    continue
                r = rows_eq[0]
                nombre = s(r[1]);  tipo = s(r[7])

                con_rows = Modelo.devolver_conectores_de_equipo(id_eq)
                p_in, p_out = [], []
                for cr in con_rows:
                    cid = str(cr[0]); cnm = s(cr[1]); ctp = s(cr[2]).upper()
                    if "IN" in ctp and "OUT" not in ctp:
                        p_in.append((cid, cnm, len(p_in)))
                    else:
                        p_out.append((cid, cnm, len(p_out)))

                n_rows = max(len(p_in), len(p_out), 1)
                alto = HDR_H + PORT_PAD * 2 + 10 + n_rows * PORT_H

                nodos[id_eq] = {
                    "id": id_eq, "nombre": nombre, "tipo": tipo,
                    "x": 0.0, "y": 0.0, "ancho": NODE_W, "alto": alto,
                    "in": p_in, "out": p_out,
                    "color": _tipo_color(tipo), "has_pos": False,
                }

        with _Cron("query_conexiones (todas, filtradas en Python, original)"):
            conns = self._canvas._conns
            seen = set()
            all_cx = Modelo._query("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
            for r in all_cx:
                id_cb = str(r[11])
                if id_cb in seen:
                    continue
                id_ea = str(r[10])
                id_eb = str(r[9])
                if id_ea not in nodos or id_eb not in nodos:
                    continue
                seen.add(id_cb)
                con_a_nom = s(r[3]).upper()
                con_a_id  = str(r[14])
                con_b_id  = str(r[13])
                if "OUT" in con_a_nom:
                    src_eq, src_con = id_ea, con_a_id
                    dst_eq, dst_con = id_eb, con_b_id
                else:
                    src_eq, src_con = id_eb, con_b_id
                    dst_eq, dst_con = id_ea, con_a_id
                conns.append({
                    "id": id_cb, "nombre": s(r[0]),
                    "src_eq": src_eq, "src_con": src_con,
                    "dst_eq": dst_eq, "dst_con": dst_con,
                })

        with _Cron("layout (estrella)"):
            self._star_layout(list(nodos.values()), id_inicio)

        n_n = len(nodos);  n_c = len(self._canvas._conns)
        self._lbl_status.text = f"{n_n} nodos  ·  {n_c} cables"
        Clock.schedule_once(lambda *_: self._canvas.fit_all(), 0.05)

    # ── Modo global: índice liviano de TODO + virtualización por viewport ──

    def _cargar_modo_global(self):
        with _Cron("ids_equipos (global)"):
            rows = Modelo._query(
                "SELECT DISTINCT id_equipo FROM CONEXIONES_AMBOS_EXTREMOS")
            eq_ids = {str(r[0]) for r in rows}

        with _Cron("query_equipos_bulk", f"n={len(eq_ids)}"):
            info_eq = _bulk_info_equipos(eq_ids)

        with _Cron("query_posiciones_bulk", f"n={len(eq_ids)}"):
            posiciones = _bulk_posiciones(eq_ids)

        with _Cron("query_conexiones_bulk (grafo completo)"):
            self._edges_idx = _bulk_conexiones(None)

        # ── Índice liviano: nombre/tipo/posición para TODOS los equipos,
        #    sin tocar la BD por cada uno (los que no tienen posición
        #    guardada se ubican con un layout en columnas calculado en
        #    memoria, agrupando por tipo). ──
        with _Cron("layout (columnas, indice completo)"):
            con_pos, sin_pos = [], []
            for id_eq in eq_ids:
                if id_eq not in info_eq:
                    continue
                nombre, tipo = info_eq[id_eq]
                entry = {"id": id_eq, "nombre": nombre, "tipo": tipo,
                        "x": 0.0, "y": 0.0}
                if id_eq in posiciones:
                    entry["x"], entry["y"] = posiciones[id_eq]
                    con_pos.append(entry)
                else:
                    sin_pos.append(entry)
                self._indice[id_eq] = entry
            self._column_layout(sin_pos)

        n_total = len(self._indice)
        n_edges = len(self._edges_idx)
        self._lbl_status.text = _(
            "{} equipos en total · {} cables").format(n_total, n_edges)

        self._minimap.actualizar_bbox()
        self._intentar_vista_inicial()

    def _intentar_vista_inicial(self, intento=0):
        """El canvas todavía puede no tener su tamaño final asignado justo
        después de abrirse el popup (layout de Kivy pendiente); reintenta
        unas pocas veces en vez de asumir que 0.05s siempre alcanza."""
        if self._canvas.width > 10 and self._canvas.height > 10:
            self._vista_inicial_global()
        elif intento < 20:
            Clock.schedule_once(
                lambda *_: self._intentar_vista_inicial(intento + 1), 0.05)
        else:
            self._vista_inicial_global()

    def _vista_inicial_global(self):
        """Vista por defecto de la vista global: zoom fijo (150%),
        centrado en el CENTROIDE del diagrama completo (promedio de la
        posición de todos los equipos), en vez de encuadrar todo el grafo
        (que con muchos equipos queda demasiado chico para ser útil en
        celular). Se usa el centroide y no el centro del bbox porque un
        solo equipo con posición guardada muy alejada (outlier) corre el
        centro del bbox a una zona vacía del diagrama; el promedio es
        mucho más robusto a esos casos."""
        if not self._indice:
            return
        n = len(self._indice)
        cx = sum(i["x"] for i in self._indice.values()) / n + NODE_W / 2
        cy = sum(i["y"] for i in self._indice.values()) / n + HDR_H / 2
        self._canvas._zoom = ZOOM_DEFECTO_GLOBAL
        W, H = self._canvas.size
        self._canvas._pan_x = W / 2 - cx * ZOOM_DEFECTO_GLOBAL
        self._canvas._pan_y = H / 2 - cy * ZOOM_DEFECTO_GLOBAL
        self._lbl_zoom.text = f"{int(ZOOM_DEFECTO_GLOBAL * 100)}%"
        self._canvas._redraw()
        self._viewport_cambio(inmediato=True)

    def _centrar_en(self, wx, wy):
        """Mueve la ventana del diagrama (paneo) para centrarla en el
        punto (wx, wy) del mundo, manteniendo el zoom actual. Usado al
        tocar un sector del minimapa."""
        W, H = self._canvas.size
        z = self._canvas._zoom or 1.0
        self._canvas._pan_x = W / 2 - wx * z
        self._canvas._pan_y = H / 2 - wy * z
        self._canvas._redraw()
        self._viewport_cambio(inmediato=True)

    # ── Virtualización: qué nodos están activos según el viewport ──────────

    def _viewport_cambio(self, inmediato=False, permitir_snap=True):
        """Se llama cuando cambia pan/zoom en modo global. Debounce corto
        para no recalcular en cada frame de un gesto largo.

        permitir_snap: si el diagrama puede "saltar" solo a mostrar los
        equipos más cercanos cuando el viewport actual no toca ninguno
        (ver _recalcular_visibles). Ese salto queda reservado para el
        minimapa y la vista inicial — si el usuario arrastra la ventana
        principal a una zona vacía (aunque sea a propósito), el diagrama
        se queda ahí, vacío, en vez de "tirar" solo hacia otro lado."""
        if self._id_inicio is not None:
            return
        if self._recalc_ev:
            self._recalc_ev.cancel()
        demora = 0 if inmediato else 0.18
        self._recalc_ev = Clock.schedule_once(
            lambda *_: self._recalcular_visibles(permitir_snap=permitir_snap),
            demora)

    def _recalcular_visibles(self, permitir_snap=True):
        if not self._indice:
            return
        with _Cron("recalcular_visibles (filtro viewport)",
                  f"indice={len(self._indice)}"):
            x1, y1, x2, y2 = self._canvas.viewport_mundo(MARGEN_VIEWPORT)

            def _en_rect(info, rx1, ry1, rx2, ry2):
                return (info["x"] + NODE_W >= rx1 and info["x"] <= rx2 and
                        info["y"] + HDR_H >= ry1 and info["y"] <= ry2)

            candidatos = [i for i, info in self._indice.items()
                         if _en_rect(info, x1, y1, x2, y2)]

            # Mantener siempre el seleccionado y el que se está arrastrando,
            # aunque haya quedado justo afuera del margen.
            forzados = {i for i in (self._canvas._sel_id, self._canvas._drag_id)
                       if i}

            def _centro_en_rect(info, rx1, ry1, rx2, ry2):
                cx = info["x"] + NODE_W / 2
                cy = info["y"] + HDR_H / 2
                return rx1 <= cx <= rx2 and ry1 <= cy <= ry2

            # OJO: "candidatos" incluye el margen de precarga (más ancho
            # que la pantalla real), así que puede no estar vacío aunque
            # NADA quede realmente visible en pantalla. Por eso el chequeo
            # de "diagrama en blanco" se hace contra el CENTRO de cada
            # nodo dentro del viewport SIN margen (un roce de borde no
            # alcanza para que el usuario perciba algo en pantalla).
            xe1, ye1, xe2, ye2 = self._canvas.viewport_mundo(0.0)
            hay_algo_en_pantalla = any(
                _centro_en_rect(self._indice[i], xe1, ye1, xe2, ye2)
                for i in candidatos)

            # El "salto" a los equipos más cercanos cuando no hay nada en
            # pantalla queda restringido al minimapa y a la vista inicial
            # (permitir_snap=True ahí). Si el usuario arrastra la ventana
            # PRINCIPAL a una zona vacía, aunque sea a propósito, el
            # diagrama se queda ahí — vacío — en vez de saltar solo.
            if not hay_algo_en_pantalla and not forzados and permitir_snap:
                # Nada del grafo cae realmente en pantalla (puede pasar si
                # el centro calculado cae en un hueco entre grupos de
                # nodos, o si se paneó a una zona vacía del diagrama): en
                # vez de dejar el diagrama en blanco, se buscan los
                # equipos más cercanos al centro de la pantalla...
                cx0 = (x1 + x2) / 2;  cy0 = (y1 + y2) / 2

                def _dist0(i):
                    info = self._indice[i]
                    return (info["x"] - cx0) ** 2 + (info["y"] - cy0) ** 2

                candidatos = sorted(self._indice.keys(), key=_dist0)[:MAX_NODOS_GLOBAL]

                # ...y se RE-CENTRA el paneo sobre ESE equipo más cercano
                # (no sobre el promedio del grupo: con nodos tan anchos
                # como el viewport a zoom alto, promediar varias columnas
                # puede volver a caer en un hueco entre ellas). Así queda
                # garantizado al menos un equipo bien centrado en pantalla.
                if candidatos:
                    mas_cercano = self._indice[candidatos[0]]
                    ccx = mas_cercano["x"] + NODE_W / 2
                    ccy = mas_cercano["y"] + HDR_H / 2
                    z = self._canvas._zoom
                    W, H = self._canvas.size
                    self._canvas._pan_x = W / 2 - ccx * z
                    self._canvas._pan_y = H / 2 - ccy * z
                    self._lbl_zoom.text = f"{int(z * 100)}%"
                    x1, y1, x2, y2 = self._canvas.viewport_mundo(MARGEN_VIEWPORT)

            if len(candidatos) + len(forzados - set(candidatos)) > MAX_NODOS_GLOBAL:
                cx = (x1 + x2) / 2;  cy = (y1 + y2) / 2

                def _dist(i):
                    info = self._indice[i]
                    return (info["x"] - cx) ** 2 + (info["y"] - cy) ** 2

                # Priorizar lo que ya estaba activo (evita "parpadeo" de
                # nodos recargándose todo el tiempo), y completar por
                # cercanía al centro de la pantalla.
                ya_activos = [i for i in candidatos if i in self._activos]
                resto = sorted((i for i in candidatos if i not in self._activos),
                              key=_dist)
                elegidos = (ya_activos + resto)[:MAX_NODOS_GLOBAL]
                visibles_ids = set(elegidos) | forzados
                limitado = True
            else:
                visibles_ids = set(candidatos) | forzados
                limitado = len(self._indice) > MAX_NODOS_GLOBAL

            # Con zoom alto se ven pocos nodos (a veces media docena) y
            # sobra mucho del cupo de 50: se completa con los OTROS
            # extremos de los cables que salen de los nodos visibles, así
            # se puede seguir el cable hacia dónde va aunque el equipo del
            # otro lado quede fuera de la pantalla, en vez de "cortarlo".
            cupo_libre = MAX_NODOS_GLOBAL - len(visibles_ids)
            if cupo_libre > 0:
                vecinos = []
                vistos = set(visibles_ids)
                for e in self._edges_idx:
                    si, di = e["src_eq"], e["dst_eq"]
                    if si in visibles_ids and di not in vistos:
                        vecinos.append(di); vistos.add(di)
                    elif di in visibles_ids and si not in vistos:
                        vecinos.append(si); vistos.add(si)
                    if len(vecinos) >= cupo_libre:
                        break
                nuevos_ids = visibles_ids | set(vecinos[:cupo_libre])
            else:
                nuevos_ids = visibles_ids

            if nuevos_ids == self._activos:
                return

            # Sincronizar al índice la posición de los nodos activos que el
            # usuario haya arrastrado en memoria, antes de reconstruirlos.
            for id_eq, nd in self._canvas._nodos.items():
                if id_eq in self._indice:
                    self._indice[id_eq]["x"] = nd["x"]
                    self._indice[id_eq]["y"] = nd["y"]

        with _Cron("query_conectores_bulk (activos)", f"n={len(nuevos_ids)}"):
            info_con = _bulk_conectores(nuevos_ids)

        compacto = self._solo_nombre
        nuevos_nodos = {}
        for id_eq in nuevos_ids:
            info = self._indice.get(id_eq)
            if not info:
                continue
            con = info_con.get(id_eq, {"in": [], "out": []})
            if compacto:
                alto = HDR_H
            else:
                n_rows = max(len(con["in"]), len(con["out"]), 1)
                alto = HDR_H + PORT_PAD * 2 + 10 + n_rows * PORT_H
            nuevos_nodos[id_eq] = {
                "id": id_eq, "nombre": info["nombre"], "tipo": info["tipo"],
                "x": info["x"], "y": info["y"], "ancho": NODE_W, "alto": alto,
                "in": con["in"], "out": con["out"],
                "color": _tipo_color(info["tipo"]), "has_pos": True,
            }

        self._canvas._nodos = nuevos_nodos
        self._activos = nuevos_ids
        self._canvas._conns = [
            e for e in self._edges_idx
            if e["src_eq"] in nuevos_ids and e["dst_eq"] in nuevos_ids]

        n_n = len(nuevos_nodos);  n_c = len(self._canvas._conns)
        n_tot = len(self._indice)
        n_extra = len(nuevos_ids) - len(visibles_ids)
        if limitado:
            self._lbl_status.text = _(
                "{} de {} equipos visibles (paneá para ver más) · "
                "{} cables").format(n_n, n_tot, n_c)
        elif n_extra > 0:
            self._lbl_status.text = _(
                "{} equipos en pantalla + {} conectados fuera de vista · "
                "{} cables").format(len(visibles_ids), n_extra, n_c)
        else:
            self._lbl_status.text = f"{n_n} nodos  ·  {n_c} cables"

        self._canvas._redraw()

    def _encuadrar(self):
        if self._id_inicio is None and self._indice:
            self._canvas.fit_bbox_indice(self._indice)
            self._viewport_cambio(inmediato=True, permitir_snap=False)
        else:
            self._canvas.fit_all()

    def _star_layout(self, nodos, id_inicio):
        """
        Layout del equipo principal en el centro:
          - IZQUIERDA: equipos conectados a las ENTRADAS (puertos IN) del
            equipo principal (equipos que le envían señal).
          - DERECHA: equipos conectados a las SALIDAS (puertos OUT) del
            equipo principal (equipos a los que él les envía señal).
          - En cada lado, una única columna, ordenada de arriba a abajo
            según el orden de los puertos del equipo principal, alineando
            verticalmente cada equipo con su puerto correspondiente.
        """
        centro = self._canvas._nodos.get(id_inicio)
        vecinos = [n for n in nodos if n["id"] != id_inicio]
        CX, CY = 600.0, 400.0
        if centro:
            centro["x"] = CX - NODE_W / 2
            centro["y"] = CY - centro["alto"] / 2
        if not centro or not vecinos:
            return

        # id_conector del principal -> índice de puerto (orden top->bottom)
        idx_in  = {cid: idx for cid, _n, idx in centro["in"]}
        idx_out = {cid: idx for cid, _n, idx in centro["out"]}

        lado_de  = {}   # id_equipo_vecino -> "left" | "right"
        orden_de = {}   # id_equipo_vecino -> índice de puerto del principal

        for c in self._canvas._conns:
            if c["src_eq"] == id_inicio and c["dst_eq"] != id_inicio:
                vecino_id, lado = c["dst_eq"], "right"
                idx = idx_out.get(c["src_con"], 0)
            elif c["dst_eq"] == id_inicio and c["src_eq"] != id_inicio:
                vecino_id, lado = c["src_eq"], "left"
                idx = idx_in.get(c["dst_con"], 0)
            else:
                continue
            if vecino_id not in orden_de or idx < orden_de[vecino_id]:
                lado_de[vecino_id] = lado
                orden_de[vecino_id] = idx

        izquierda = [n for n in vecinos if lado_de.get(n["id"]) == "left"]
        derecha   = [n for n in vecinos if lado_de.get(n["id"]) == "right"]
        sin_lado  = [n for n in vecinos if n["id"] not in lado_de]

        GAP_X = 260.0
        GAP_Y = 26.0
        x_izq = centro["x"] - GAP_X - NODE_W
        x_der = centro["x"] + NODE_W + GAP_X

        def _y_puerto(idx_puerto):
            top = centro["y"] + centro["alto"]
            tipo_h = 10
            return (top - HDR_H - tipo_h - PORT_PAD
                   - idx_puerto * PORT_H - PORT_H / 2)

        def _colocar_columna(lista, x0):
            lista_ordenada = sorted(lista, key=lambda n: orden_de.get(n["id"], 0))
            prev_bottom = None
            for nd in lista_ordenada:
                nd["x"] = x0
                y_obj = _y_puerto(orden_de.get(nd["id"], 0)) - nd["alto"] / 2
                if prev_bottom is not None and y_obj + nd["alto"] + GAP_Y > prev_bottom:
                    y_obj = prev_bottom - GAP_Y - nd["alto"]
                nd["y"] = y_obj
                prev_bottom = y_obj

        _colocar_columna(izquierda, x_izq)
        _colocar_columna(derecha, x_der)

        # Caso raro: equipo del diagrama sin conexión directa detectada al
        # principal (por ejemplo, conexión entre dos vecinos). Se apilan
        # debajo, para no perderlos de vista.
        y_extra = centro["y"] - centro["alto"] - 60
        for i, nd in enumerate(sin_lado):
            nd["x"] = centro["x"]
            nd["y"] = y_extra - i * (nd["alto"] + 20)

    def _column_layout(self, nodos):
        """Ubica en columnas (agrupadas por tipo) los nodos sin posición
        guardada. `nodos` son entradas livianas del índice global (dicts
        con x/y), no requiere ninguna consulta adicional."""
        grupos = {}
        for n in nodos:
            grupos.setdefault(n["tipo"], []).append(n)
        GAP_X = 280;  GAP_Y = HDR_H + 20;  MAX_R = 8
        col = 0
        for _tipo, nlist in sorted(grupos.items()):
            row = 0
            for nd in nlist:
                nd["x"] = 80 + col * GAP_X
                nd["y"] = 3000 - row * GAP_Y
                row += 1
                if row >= MAX_R:
                    row = 0;  col += 1
            col += 1

    # ── Acciones toolbar ──────────────────────────────────────────────────────

    def _recargar(self):
        self._limpiar_conexion_interna()
        self._cargar(self._id_inicio)

    # ── Conexión interna (Módulo Patchera) ─────────────────────────────────

    def _limpiar_conexion_interna(self):
        self._interna = None
        if hasattr(self, "_btn_interna"):
            self._btn_interna.state = "normal"

    def _buscar_puerto(self, nodo, prefijo):
        """(id_conector, lado) del primer puerto cuyo nombre empieza con
        `prefijo` (case-insensitive), buscando en IN y OUT. None si no está."""
        prefijo = prefijo.upper()
        for lst, lado in ((nodo.get("in", []), "in"), (nodo.get("out", []), "out")):
            for cid, cnm, _i in lst:
                if s(cnm).strip().upper().startswith(prefijo):
                    return (cid, lado)
        return None

    def _calcular_conexion_interna(self, nodo):
        """Determina, según qué front tenga cable externo conectado, qué
        líneas punteadas dibujar dentro del módulo patchera. Consulta la
        tabla conexion directo por id_conector (no self._conns, que sólo
        trae cables entre nodos visibles en el diagrama actual)."""
        p_a_back  = self._buscar_puerto(nodo, "A_BACK")
        p_b_back  = self._buscar_puerto(nodo, "B_BACK")
        p_a_front = self._buscar_puerto(nodo, "A_FRONT")
        p_b_front = self._buscar_puerto(nodo, "B_FRONT")
        if not all([p_a_back, p_b_back, p_a_front, p_b_front]):
            return None

        a_conectado = bool(Modelo._query(
            "SELECT 1 FROM conexion WHERE id_conector=? LIMIT 1", (p_a_front[0],)))
        b_conectado = bool(Modelo._query(
            "SELECT 1 FROM conexion WHERE id_conector=? LIMIT 1", (p_b_front[0],)))

        segmentos, muertos = [], []
        if not a_conectado and not b_conectado:
            segmentos.append((p_a_back, p_b_back))
        elif a_conectado and not b_conectado:
            segmentos.append((p_a_back, p_a_front))
            muertos.append(p_b_back)
        elif not a_conectado and b_conectado:
            segmentos.append((p_b_back, p_b_front))
            muertos.append(p_a_back)
        else:
            segmentos.append((p_a_back, p_a_front))
            segmentos.append((p_b_back, p_b_front))

        return {"nodo_id": nodo["id"], "segmentos": segmentos, "muertos": muertos}

    def _toggle_conexion_interna(self, btn):
        if self._id_inicio is None:
            btn.state = "normal"
            mostrar_info(_("La conexión interna sólo está disponible viendo "
                          "el diagrama de un equipo (no en la vista global)."))
            return

        if btn.state != "down":
            self._interna = None
            self._canvas._redraw()
            return

        sel = self._canvas._sel_id
        nodo = self._canvas._nodos.get(sel) if sel else None
        if not nodo or "PATCHERA" not in nodo["tipo"].upper():
            btn.state = "normal"
            self._lbl_status.text = _(
                "Seleccioná primero un equipo tipo Módulo Patchera.")
            return

        if self._solo_nombre:
            self._solo_nombre = False
            self._btn_solo.state = "normal"
            for nd in self._canvas._nodos.values():
                n_rows = max(len(nd["in"]), len(nd["out"]), 1)
                nd["alto"] = HDR_H + PORT_PAD * 2 + 10 + n_rows * PORT_H

        resultado = self._calcular_conexion_interna(nodo)
        if resultado is None:
            btn.state = "normal"
            self._lbl_status.text = _(
                "No se pudo determinar A_BACK/B_BACK/A_FRONT/B_FRONT en "
                "este equipo.")
            return

        self._interna = resultado
        self._lbl_status.text = _("Conexión interna: {}").format(nodo["nombre"])
        self._canvas._redraw()

    def _expandir(self):
        if self._id_inicio is None:
            mostrar_info(_("En la vista global el diagrama ya incluye a "
                          "todos los equipos conectados: paneá o buscá "
                          "para navegarlo."))
            return
        sel = self._canvas._sel_id
        if not sel:
            return
        nodos = self._canvas._nodos
        sel_nodo = nodos.get(sel)
        if not sel_nodo:
            return

        # WHERE id_equipo=sel → en esta vista "sel" siempre queda del lado
        # Extremo B (columnas id_equipo/id_conector/r[7]); el otro equipo
        # queda del lado Extremo A ("id_equipo:1"/"id_conector:1"/r[3]).
        rows = Modelo._query(
            "SELECT * FROM CONEXIONES_AMBOS_EXTREMOS WHERE id_equipo=?",
            (sel,))
        nuevos_ids = {str(r[10]) for r in rows} - set(nodos.keys())
        if not nuevos_ids:
            mostrar_info(_("No hay vecinos nuevos para expandir."))
            return

        # Por cada equipo nuevo, con qué puerto de "sel" se conecta (la
        # primera conexión encontrada define su posición inicial).
        info_por_nuevo = {}
        for r in rows:
            id_otro = str(r[10])
            if id_otro not in nuevos_ids or id_otro in info_por_nuevo:
                continue
            con_sel_nom = s(r[7]).upper()
            con_sel_id = str(r[13])
            con_otro_id = str(r[14])
            lado_sel = "out" if "OUT" in con_sel_nom else "in"
            info_por_nuevo[id_otro] = (con_sel_id, lado_sel, con_otro_id)

        GAP_X = 260.0
        MIN_GAP_Y = 26.0
        tipo_h = 10

        nuevos_izq, nuevos_der = [], []

        for id_eq in nuevos_ids:
            rows_eq = Modelo.devolver_equipo(id_eq)
            if not rows_eq:
                continue
            r = rows_eq[0]
            nombre = s(r[1]);  tipo = s(r[7])

            con_rows = Modelo.devolver_conectores_de_equipo(id_eq)
            p_in, p_out = [], []
            for cr in con_rows:
                cid = str(cr[0]); cnm = s(cr[1]); ctp = s(cr[2]).upper()
                if "IN" in ctp and "OUT" not in ctp:
                    p_in.append((cid, cnm, len(p_in)))
                else:
                    p_out.append((cid, cnm, len(p_out)))

            n_rows_ = max(len(p_in), len(p_out), 1)
            alto = HDR_H + PORT_PAD * 2 + 10 + n_rows_ * PORT_H

            nodo = {
                "id": id_eq, "nombre": nombre, "tipo": tipo,
                "x": 0.0, "y": 0.0, "ancho": NODE_W, "alto": alto,
                "in": p_in, "out": p_out,
                "color": _tipo_color(tipo), "has_pos": False,
            }

            con_sel_id, lado_sel, con_otro_id = info_por_nuevo.get(
                id_eq, (None, "out", None))
            lado_nuevo = "in" if lado_sel == "out" else "out"
            lst_nuevo = nodo["in"] if lado_nuevo == "in" else nodo["out"]
            idx_nuevo = next((i for i, (cid, _n, _i) in enumerate(lst_nuevo)
                              if cid == con_otro_id), 0)

            if con_sel_id:
                _px, py_sel = self._canvas._port_pos(sel_nodo, con_sel_id,
                                                     lado_sel)
            else:
                py_sel = sel_nodo["y"] + sel_nodo["alto"] / 2

            offset = (HDR_H + tipo_h + PORT_PAD
                     + idx_nuevo * PORT_H + PORT_H / 2)
            nodo["y"] = py_sel - alto + offset

            if lado_sel == "out":
                nodo["x"] = sel_nodo["x"] + sel_nodo["ancho"] + GAP_X
                nuevos_der.append(nodo)
            else:
                nodo["x"] = sel_nodo["x"] - NODE_W - GAP_X
                nuevos_izq.append(nodo)

            nodos[id_eq] = nodo

        # Evita que nodos nuevos del mismo lado se superpongan entre sí.
        for grupo in (nuevos_izq, nuevos_der):
            grupo.sort(key=lambda n: -n["y"])
            for i in range(1, len(grupo)):
                prev, actual = grupo[i - 1], grupo[i]
                limite = prev["y"] - actual["alto"] - MIN_GAP_Y
                if actual["y"] > limite:
                    actual["y"] = limite

        # Conexiones nuevas (incluye nuevo↔nuevo y nuevo↔existente); no
        # se tocan las ya cargadas.
        conns = self._canvas._conns
        ya_ids = {c["id"] for c in conns}
        all_cx = Modelo._query("SELECT * FROM CONEXIONES_AMBOS_EXTREMOS")
        for r in all_cx:
            id_cb = str(r[11])
            if id_cb in ya_ids:
                continue
            id_ea = str(r[10]); id_eb = str(r[9])
            if id_ea not in nodos or id_eb not in nodos:
                continue
            con_a_nom = s(r[3]).upper()
            con_a_id = str(r[14]); con_b_id = str(r[13])
            if "OUT" in con_a_nom:
                src_eq, src_con = id_ea, con_a_id
                dst_eq, dst_con = id_eb, con_b_id
            else:
                src_eq, src_con = id_eb, con_b_id
                dst_eq, dst_con = id_ea, con_a_id
            conns.append({
                "id": id_cb, "nombre": s(r[0]),
                "src_eq": src_eq, "src_con": src_con,
                "dst_eq": dst_eq, "dst_con": dst_con,
            })
            ya_ids.add(id_cb)

        n_n = len(nodos);  n_c = len(conns)
        self._lbl_status.text = f"{n_n} nodos  ·  {n_c} cables"
        self._canvas._redraw()

    def _toggle_solo(self, btn):
        self._solo_nombre = btn.state == "down"
        nodos = self._canvas._nodos
        for nodo in nodos.values():
            if self._solo_nombre:
                nodo["alto"] = HDR_H
            else:
                n_rows = max(len(nodo["in"]), len(nodo["out"]), 1)
                nodo["alto"] = HDR_H + PORT_PAD * 2 + 10 + n_rows * PORT_H
        self._canvas._redraw()

    def _on_buscar(self, ti, texto):
        txt = texto.strip().lower()
        if not txt:
            self._lbl_sel.text = _("Sin selección")
            self._canvas._sel_id = None
            self._canvas._redraw()
            return

        if self._id_inicio is not None:
            # Modo raíz: comportamiento ORIGINAL, sin cambios — busca sólo
            # entre los nodos ya cargados (equipo raíz + vecinos).
            for eq_id, nd in self._canvas._nodos.items():
                if (txt in nd["nombre"].lower() or txt in nd["tipo"].lower()):
                    self._canvas._sel_id = eq_id
                    self._canvas.fit_all()
                    self._lbl_sel.text = f"{nd['nombre']}  [{nd['tipo']}]"
                    W, H = self._canvas.size
                    z = self._canvas._zoom
                    cx = nd["x"] + nd["ancho"] / 2
                    cy = nd["y"] + nd["alto"] / 2
                    self._canvas._pan_x = W / 2 - cx * z
                    self._canvas._pan_y = H / 2 - cy * z
                    self._canvas._redraw()
                    return
            return

        # Modo global: busca en el índice completo (equipos fuera de
        # pantalla también), no sólo entre los que están cargados ahora.
        for eq_id, info in self._indice.items():
            if (txt in info["nombre"].lower() or txt in info["tipo"].lower()):
                self._canvas._sel_id = eq_id
                self._lbl_sel.text = f"{info['nombre']}  [{info['tipo']}]"
                W, H = self._canvas.size
                z = self._canvas._zoom or 1.0
                cx = info["x"] + NODE_W / 2
                cy = info["y"] + HDR_H / 2
                self._canvas._pan_x = W / 2 - cx * z
                self._canvas._pan_y = H / 2 - cy * z
                self._canvas._redraw()
                self._viewport_cambio(inmediato=True)
                return

    def _exportar_png(self):
        try:
            import tempfile
            ruta = os.path.join(tempfile.gettempdir(),
                                "diagrama_conexiones.png")
            self._canvas.export_to_png(ruta)
            mostrar_info(_(f"Exportado a:\n{ruta}"))
        except Exception as e:
            mostrar_error(_(f"Error al exportar:\n{e}"))


# ─── Función de conveniencia ──────────────────────────────────────────────────

def abrir_diagrama_conexiones(id_equipo=None):
    DiagramaConexiones(id_equipo=id_equipo).open()
