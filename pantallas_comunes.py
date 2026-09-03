#!/usr/bin/env python3
"""
pantallas_comunes.py — CableDoc GTK3

Módulo común, fundacional para el refactor de `pantallas_avanzadas.py`
(ver plan_refactor_pantallas_avanzadas.md, Entrega 0).

Contiene utilidades sin estado de negocio, compartidas por varias pantallas
de `pantallas_avanzadas.py` y por los archivos que la vayan reemplazando en
entregas futuras:

  - Utilidades genéricas: s(), confirmar()
  - Íconos cacheados: _pixbuf_from_name, _icono_buscar_surface,
    _dibujar_icono_buscar, _icono_critico_surface
  - Widget reutilizable _ImagenZoom (visor de imagen con zoom), usado hoy por
    8 pantallas distintas (Coordenadas, ImagenConectores, Patcheras y las 4
    variantes de Editor Masivo)
  - PALETA de colores, usada por Patcheras, DiagramaConexiones y
    EditorMasivoConectoresImagen
  - Helpers de dibujo Cairo sin estado: _rrect, _rrect_top, _arrow,
    _tipo_color (hoy viven pegados a DiagramaConexiones pero son primitivas
    genéricas, no lógica de diagrama)
  - Bootstrap de i18n (_, cargar_idioma_guardado)

Esto es un *move* 1:1 desde pantallas_avanzadas.py: no cambia comportamiento
ni lógica de negocio. Sin este módulo, cada pantalla nueva que reemplace un
pedazo de pantallas_avanzadas.py reintroduciría el mismo bloque de imports o
generaría un import circular entre archivos hermanos.
"""

import os
import re
import sys
import math
import textwrap
import colorsys as _colorsys
import hashlib as _hashlib

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

# Rsvg es opcional: si no está instalado el binding de introspección
# (gir1.2-rsvg-2.0), la app sigue funcionando igual con imágenes raster —
# simplemente _pixbuf_from_name no reconoce .svg y esos archivos no se
# muestran (mismo comportamiento que cualquier formato no soportado).
try:
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    _RSVG_DISPONIBLE = True
except Exception:
    Rsvg = None
    _RSVG_DISPONIBLE = False

_AVISO_RSVG_FALTANTE_EMITIDO = False


def _avisar_rsvg_faltante():
    """Avisa una sola vez por consola cuando un .svg no se puede mostrar
    porque falta el binding de introspección de Rsvg. Antes esto fallaba
    en silencio y la única pista visible era el recuadro negro "Sin
    imagen asignada" en pantalla, indistinguible de un archivo faltante
    o corrupto — muy difícil de diagnosticar a distancia."""
    global _AVISO_RSVG_FALTANTE_EMITIDO
    if not _AVISO_RSVG_FALTANTE_EMITIDO:
        _AVISO_RSVG_FALTANTE_EMITIDO = True
        print("CableDoc: no se puede mostrar la imagen SVG porque falta el "
              "binding de introspección de Rsvg (paquete del sistema "
              "gir1.2-rsvg-2.0 en Debian/Ubuntu, o equivalente). Instalalo "
              "y reiniciá la app para ver los archivos .svg.", file=sys.stderr)


def _svg_viewbox_size(full_path):
    """Último recurso para obtener el tamaño intrínseco de un SVG cuando
    Rsvg.Handle.get_dimensions() devuelve 0x0 — algo frecuente en SVG
    "vectorizados" (trace bitmap / exportadores) que sólo declaran
    viewBox y dejan width/height en '100%' o directamente los omiten, ya
    que get_dimensions() es una API vieja de librsvg que no siempre sabe
    resolver ese caso. Lee el atributo viewBox del propio XML sin
    depender de la versión de Rsvg instalada."""
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            encabezado = f.read(4096)  # <svg ...> siempre está al principio
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


from modelo import IMG_DIR

try:
    from i18n import _, cargar_idioma_guardado
    cargar_idioma_guardado()
except ImportError:
    def _(t): return t
    def cargar_idioma_guardado(): pass


# ── utilidades ────────────────────────────────────────────────────────────────

def s(v):
    return "" if v is None else str(v)


def confirmar(padre, texto):
    """Muestra un diálogo de confirmación y devuelve True si el usuario acepta."""
    dlg = Gtk.MessageDialog(
        transient_for=padre, flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO, text=texto
    )
    respuesta = dlg.run(); dlg.destroy()
    return respuesta == Gtk.ResponseType.YES


class _ImagenSVG:
    """Wrapper liviano para una imagen SVG cargada con Rsvg, pensado para
    duck-tipear como un GdkPixbuf.Pixbuf allí donde el resto del código
    sólo necesita get_width()/get_height() (varias pantallas leen
    `_viz.pixbuf.get_width()` directo). La diferencia real está en
    _ImagenZoom._on_draw: en vez de rasterizar una vez con scale_simple()
    como con GdkPixbuf, cada redibujo vuelve a renderizar el vector con
    Rsvg al tamaño de zoom actual — así el SVG se ve nítido en cualquier
    zoom en vez de pixelarse como pasaría escalando un bitmap."""

    def __init__(self, ruta, handle, ancho, alto):
        self.ruta = ruta
        self.handle = handle
        self._ancho = ancho
        self._alto = alto

    def get_width(self):
        return self._ancho

    def get_height(self):
        return self._alto


def _pixbuf_from_name(nombre_archivo):
    pb, _motivo = _pixbuf_from_name_con_motivo(nombre_archivo)
    return pb


def _pixbuf_from_name_con_motivo(nombre_archivo):
    """Igual que _pixbuf_from_name, pero además devuelve un texto explicando
    por qué falló cuando devuelve None (archivo no encontrado, falta Rsvg,
    SVG sin dimensiones utilizables, error de lectura...). Antes, cualquiera
    de estos motivos terminaba en el mismo recuadro negro genérico "Sin
    imagen asignada", indistinguible entre "no copiaste el archivo" y "no
    está instalado el binding de Rsvg" — un problema real se veía igual que
    un dato faltante, muy difícil de diagnosticar a distancia."""
    if not nombre_archivo:
        return None, None
    nombre_limpio = s(nombre_archivo).strip()
    ruta = os.path.join(IMG_DIR, nombre_limpio)
    if not os.path.exists(ruta):
        return None, _(
            "No se encontró el archivo '{0}' en la carpeta de imágenes "
            "({1}).").format(nombre_limpio, IMG_DIR)
    if ruta.lower().endswith(".svg"):
        if not _RSVG_DISPONIBLE:
            _avisar_rsvg_faltante()
            return None, _(
                "El archivo '{0}' es un SVG, pero en esta instalación "
                "falta el componente para mostrarlos (Rsvg). Instalá "
                "gir1.2-rsvg-2.0 (o el paquete equivalente de tu sistema) "
                "y reiniciá la app.").format(nombre_limpio)
        try:
            handle = Rsvg.Handle.new_from_file(ruta)
            dim = handle.get_dimensions()
            ancho, alto = dim.width, dim.height
            if not ancho or not alto:
                # get_dimensions() (API vieja de librsvg) puede devolver
                # 0x0 en SVG que sólo declaran viewBox — ver
                # _svg_viewbox_size. Sin este fallback, esos SVG se
                # mostraban en negro como "sin imagen" aunque el archivo
                # existiera y fuera válido.
                tam = _svg_viewbox_size(ruta)
                if tam:
                    ancho, alto = tam
            if ancho and alto:
                return _ImagenSVG(ruta, handle, ancho, alto), None
            return None, _(
                "El archivo '{0}' es un SVG válido pero no se le pudo "
                "determinar el ancho/alto (no declara width/height ni un "
                "viewBox utilizable).").format(nombre_limpio)
        except Exception as ex:
            return None, _(
                "No se pudo leer '{0}' como SVG: {1}").format(
                    nombre_limpio, ex)
    try:
        return GdkPixbuf.Pixbuf.new_from_file(ruta), None
    except Exception as ex:
        return None, _(
            "No se pudo leer '{0}' como imagen: {1}").format(
                nombre_limpio, ex)


PALETA = [
    (0.85, 0.15, 0.15), (0.15, 0.72, 0.15), (0.18, 0.42, 0.90),
    (0.92, 0.55, 0.04), (0.65, 0.15, 0.82), (0.04, 0.78, 0.78),
    (0.78, 0.75, 0.04), (0.90, 0.30, 0.65), (0.30, 0.72, 0.38),
    (0.55, 0.30, 0.08), (0.10, 0.52, 0.30), (0.82, 0.10, 0.50),
    (0.28, 0.60, 0.90), (0.75, 0.55, 0.22), (0.50, 0.10, 0.10),
    (0.18, 0.28, 0.72), (0.10, 0.65, 0.55), (0.70, 0.38, 0.82),
    (0.30, 0.50, 0.18), (0.90, 0.18, 0.38),
]

# Directorio de recursos gráficos propios de la app (íconos, etc. — no
# confundir con IMG_DIR/PICON_DIR/MANUALES_DIR, que son datos del usuario).
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

_ICONO_CRITICO_SURFACE = None
_ICONO_CRITICO_FALLO = False

# Íconos del HUD de búsqueda (lupa, ◀ anterior, ▶ siguiente, ✕ cerrar):
# mismo problema y mismo mecanismo de solución que el badge de crítico
# (ver _icono_critico_surface) — se cachean por nombre de archivo.
_ICONOS_BUSCAR_CACHE = {}
_ICONOS_BUSCAR_ARCHIVOS = {
    "lupa":    "icono_buscar_lupa.png",
    "prev":    "icono_buscar_prev.png",
    "next":    "icono_buscar_next.png",
    "cerrar":  "icono_buscar_cerrar.png",
}


def _icono_buscar_surface(nombre):
    """Devuelve (cacheada) la superficie Cairo de uno de los íconos del HUD
    de búsqueda ('lupa', 'prev', 'next', 'cerrar'). None si no se pudo
    cargar (el llamador debe tener un fallback sin texto)."""
    if nombre in _ICONOS_BUSCAR_CACHE:
        return _ICONOS_BUSCAR_CACHE[nombre]
    archivo = _ICONOS_BUSCAR_ARCHIVOS.get(nombre)
    surface = None
    if archivo:
        ruta = os.path.join(ASSETS_DIR, archivo)
        try:
            import cairo
            surface = cairo.ImageSurface.create_from_png(ruta)
        except Exception:
            surface = None
    _ICONOS_BUSCAR_CACHE[nombre] = surface
    return surface


def _dibujar_icono_buscar(cr, nombre, cx, cy, diam):
    """Dibuja el ícono `nombre` centrado en (cx, cy) con diámetro `diam`,
    en coordenadas de pantalla. Si no se pudo cargar el PNG, no dibuja
    nada (el botón sigue siendo clickeable, solo queda sin glifo, mejor
    que mostrar un cuadrado vacío)."""
    surface = _icono_buscar_surface(nombre)
    if surface is None:
        return
    iw, ih = surface.get_width(), surface.get_height()
    escala = diam / max(iw, ih)
    cr.save()
    cr.translate(cx - iw*escala/2, cy - ih*escala/2)
    cr.scale(escala, escala)
    cr.set_source_surface(surface, 0, 0)
    cr.paint()
    cr.restore()


def _icono_critico_surface():
    """Devuelve (cacheada) la superficie Cairo del ícono PNG de 'equipo
    crítico de la cadena' (assets/icono_critico.png). Reemplaza al glifo
    unicode '★' que no renderizaba en todas las fuentes/plataformas
    (aparecía como un cuadrado vacío). Si el archivo no está disponible,
    devuelve None y el llamador debe hacer un fallback simple con formas."""
    global _ICONO_CRITICO_SURFACE, _ICONO_CRITICO_FALLO
    if _ICONO_CRITICO_SURFACE is not None or _ICONO_CRITICO_FALLO:
        return _ICONO_CRITICO_SURFACE
    ruta = os.path.join(ASSETS_DIR, "icono_critico.png")
    try:
        import cairo
        _ICONO_CRITICO_SURFACE = cairo.ImageSurface.create_from_png(ruta)
    except Exception:
        _ICONO_CRITICO_FALLO = True
        _ICONO_CRITICO_SURFACE = None
    return _ICONO_CRITICO_SURFACE


# ── widget reutilizable: visor de imagen con zoom ─────────────────────────────
#
#  Usa overlay_fn (callable) en lugar de señales GObject personalizadas.
#  En su lugar expone el atributo `overlay_fn` = callable(cr) que los dueños
#  asignan para dibujar encima de la imagen.

class _ImagenZoom(Gtk.Box):
    """
    Visor de imagen escalable dentro de un ScrolledWindow.
    Uso:
        viz = _ImagenZoom()
        viz.set_pixbuf(pb)
        viz.overlay_fn = lambda cr: draw_stuff(cr, viz.zoom)
        viz.da.connect("button-press-event", on_click)
    """

    def __init__(self, eventos_extra=0):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pixbuf     = None
        self.zoom       = 1.0
        self.overlay_fn = None      # callable(cr) — dibuja sobre la imagen
        self._motivo_sin_imagen = None

        # ── barra de zoom ──
        hbz = Gtk.Box(spacing=4,
                      margin_start=4, margin_end=4,
                      margin_top=4,  margin_bottom=4)
        self._lbl_zoom = Gtk.Label(label=_("100%"))
        hbz.pack_start(Gtk.Label(label=_("Zoom:")), False, False, 0)
        hbz.pack_start(self._lbl_zoom,           False, False, 0)
        for label, fn in [
            ("+",       lambda _: self.set_zoom(self.zoom * 1.25)),
            ("−",       lambda _: self.set_zoom(self.zoom / 1.25)),
            ("1:1",     lambda _: self.set_zoom(1.0)),
            (_("Ajustar"), lambda _: self._zoom_fit()),
        ]:
            b = Gtk.Button(label=label)
            b.connect("clicked", fn)
            hbz.pack_start(b, False, False, 0)
        self.pack_start(hbz, False, False, 0)

        # ── ScrolledWindow + DrawingArea ──
        self._sw = Gtk.ScrolledWindow()
        self._sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.da  = Gtk.DrawingArea()
        self.da.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK    |
            Gdk.EventMask.BUTTON_RELEASE_MASK  |
            Gdk.EventMask.POINTER_MOTION_MASK  |
            Gdk.EventMask.SCROLL_MASK          |
            eventos_extra
        )
        self.da.connect("draw",         self._on_draw)
        self.da.connect("scroll-event", self._on_scroll)
        self._sw.add(self.da)
        self.pack_start(self._sw, True, True, 0)

    # ── público ───────────────────────────────────────────────────────────
    def set_pixbuf(self, pb):
        self.pixbuf = pb
        if pb is not None:
            self._motivo_sin_imagen = None
        self._update_size()

    def set_motivo_sin_imagen(self, texto):
        """Guarda por qué no se pudo cargar la imagen (ver
        _pixbuf_from_name_con_motivo) para mostrarlo en el recuadro negro
        en vez del texto genérico "Sin imagen asignada" — así un archivo
        faltante, un SVG mal formado y una dependencia no instalada se
        pueden distinguir a simple vista, sin abrir una terminal."""
        self._motivo_sin_imagen = texto
        self.da.queue_draw()

    def set_zoom(self, z):
        self.zoom = max(0.1, min(8.0, z))
        self._lbl_zoom.set_text(f"{int(self.zoom * 100)}%")
        self._update_size()

    def scroll_to_img(self, ix, iy):
        wx, wy   = self.i2w(ix, iy)
        ha       = self._sw.get_hadjustment()
        va       = self._sw.get_vadjustment()
        alloc    = self._sw.get_allocation()
        ha.set_value(max(0, wx - alloc.width  / 2))
        va.set_value(max(0, wy - alloc.height / 2))

    # ── transformaciones ──────────────────────────────────────────────────
    def i2w(self, ix, iy):
        return ix * self.zoom, iy * self.zoom

    def w2i(self, wx, wy):
        return int(wx / self.zoom), int(wy / self.zoom)

    # ── privado ───────────────────────────────────────────────────────────
    def _update_size(self):
        if self.pixbuf:
            w = int(self.pixbuf.get_width()  * self.zoom)
            h = int(self.pixbuf.get_height() * self.zoom)
        else:
            w, h = 600, 400
        self.da.set_size_request(w, h)
        self.da.queue_draw()

    def _zoom_fit(self):
        if not self.pixbuf:
            return
        alloc = self._sw.get_allocation()
        if alloc.width < 2 or alloc.height < 2:
            return
        zw = alloc.width  / self.pixbuf.get_width()
        zh = alloc.height / self.pixbuf.get_height()
        self.set_zoom(min(zw, zh))

    def _on_draw(self, da, cr):
        # fondo blanco — antes era gris oscuro (0.25,0.25,0.25); con SVG
        # de fondo transparente (como los planos vectorizados, que sólo
        # traen los trazos) ese gris se veía por detrás de todo el dibujo.
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

        if not self.pixbuf:
            cr.set_source_rgb(0.40, 0.40, 0.40)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(14)
            cr.move_to(20, 40)
            if self._motivo_sin_imagen:
                cr.show_text(_("Sin imagen:"))
                cr.set_font_size(12)
                # texto largo: cortar en varias líneas simples para que no
                # se salga del recuadro visible
                for i, linea in enumerate(textwrap.wrap(
                        self._motivo_sin_imagen, 70)):
                    cr.move_to(20, 60 + i * 18)
                    cr.show_text(linea)
            else:
                cr.show_text(_("Sin imagen asignada al equipo/conector"))
            return

        # imagen escalada — SVG se re-renderiza como vector en cada
        # redibujo, directo al tamaño de zoom actual vía el viewport de
        # Rsvg.render_document (nítido a cualquier zoom); raster se
        # rasteriza una vez al tamaño actual con scale_simple, como antes.
        if isinstance(self.pixbuf, _ImagenSVG):
            ancho_zoom = self.pixbuf.get_width()  * self.zoom
            alto_zoom  = self.pixbuf.get_height() * self.zoom
            viewport = Rsvg.Rectangle()
            viewport.x, viewport.y = 0, 0
            viewport.width, viewport.height = ancho_zoom, alto_zoom
            self.pixbuf.handle.render_document(cr, viewport)
        else:
            scaled = self.pixbuf.scale_simple(
                int(self.pixbuf.get_width()  * self.zoom),
                int(self.pixbuf.get_height() * self.zoom),
                GdkPixbuf.InterpType.BILINEAR,
            )
            Gdk.cairo_set_source_pixbuf(cr, scaled, 0, 0)
            cr.paint()

        # overlay del dueño
        if callable(self.overlay_fn):
            self.overlay_fn(cr)

    def _on_scroll(self, da, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.set_zoom(self.zoom * 1.15)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.set_zoom(self.zoom / 1.15)


# ── helpers de dibujo Cairo genéricos (sin estado) ────────────────────────────
#
#  Primitivas puras usadas hoy por DiagramaConexiones y por PatcherasVista /
#  EditorMasivoConectoresImagen (vía PALETA); no contienen lógica de negocio
#  de diagrama, por eso se extraen acá y no a un mixin de diagrama.

def _tipo_color(tipo):
    """Deterministic header color from equipment type name."""
    h = int(_hashlib.md5((tipo or "?").encode()).hexdigest()[:4], 16) % 360
    r, g, b = _colorsys.hsv_to_rgb(h / 360, 0.52, 0.58)
    return (r, g, b)


def _rrect(cr, x, y, w, h, r=7):
    """Cairo rounded rectangle path."""
    cr.new_sub_path()
    cr.arc(x+r, y+r,   r, math.pi,       3*math.pi/2)
    cr.arc(x+w-r, y+r, r, 3*math.pi/2,   0)
    cr.arc(x+w-r, y+h-r, r, 0,           math.pi/2)
    cr.arc(x+r, y+h-r, r, math.pi/2,     math.pi)
    cr.close_path()


def _rrect_top(cr, x, y, w, h, r=7):
    """Rounded top, flat bottom (for node header)."""
    cr.new_sub_path()
    cr.arc(x+r, y+r,   r, math.pi,       3*math.pi/2)
    cr.arc(x+w-r, y+r, r, 3*math.pi/2,   0)
    cr.line_to(x+w, y+h)
    cr.line_to(x,   y+h)
    cr.close_path()


def _arrow(cr, x1, y1, x2, y2, size=7):
    """Draw a small arrowhead at (x2,y2) pointing from (x1,y1)."""
    angle = math.atan2(y2-y1, x2-x1)
    a1 = angle + 2.5
    a2 = angle - 2.5
    cr.move_to(x2, y2)
    cr.line_to(x2 + size*math.cos(a1), y2 + size*math.sin(a1))
    cr.move_to(x2, y2)
    cr.line_to(x2 + size*math.cos(a2), y2 + size*math.sin(a2))
    cr.stroke()


# ── helpers de texto Cairo (module-level para no repetir) ─────────────────────
# Corrección post-Entrega 2 (ver PROGRESS_REFACTOR.md): estos dos vivían sueltos
# junto a la sección de VistaRack en el pantallas_avanzadas.py original, pero
# los usan también PatcherasVista, DiagramaConexiones (ambos siguen en
# pantallas_avanzadas.py) y VistaFrameSlots (frame_slots_ui.py, Entrega 1) —
# son utilidades genéricas de dibujo Cairo, sin lógica de negocio, así que
# corresponden acá igual que _rrect/_tipo_color/_arrow.

def _tc(cr, texto, cx, cy):
    """Dibuja `texto` centrado en (cx, cy)."""
    if not texto:
        return
    ext = cr.text_extents(texto)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing,
               cy - ext.height / 2 - ext.y_bearing)
    cr.show_text(texto)


def _abrev(cr, texto, max_w):
    """Devuelve texto truncado con '…' si supera max_w px."""
    if not texto:
        return ""
    if cr.text_extents(texto).width <= max_w:
        return texto
    for i in range(len(texto) - 1, 0, -1):
        t = texto[:i] + "…"
        if cr.text_extents(t).width <= max_w:
            return t
    return "…"
