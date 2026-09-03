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


from modelo import Modelo, IMG_DIR

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


def mostrar_error(padre, texto):
    dlg = Gtk.MessageDialog(
        transient_for=padre, flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK, text=texto
    )
    dlg.run(); dlg.destroy()


def mostrar_info(padre, texto):
    dlg = Gtk.MessageDialog(
        transient_for=padre, flags=0,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK, text=texto
    )
    dlg.run(); dlg.destroy()


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


# ── Clase base para ventanas de listado ────────────────────────────────────────
#
#  Movido desde cabledoc.py (plan_refactor_cabledoc.md, Entrega 1). Move 1:1,
#  sin cambios de comportamiento. VentanaListado y DialogoNombre son la base
#  de prácticamente todos los ABM de la aplicación (Marcas, Tipos, Equipos,
#  Cables, Conectores, etc.), así que van acá junto con el resto de las
#  utilidades sin estado de negocio compartidas entre cabledoc.py y
#  pantallas_avanzadas.py / los archivos que la fueron reemplazando.

def _sort_func_natural(model, a, b, col):
    va = model.get_value(a, col) or ""
    vb = model.get_value(b, col) or ""
    try:
        return (int(va) > int(vb)) - (int(va) < int(vb))
    except ValueError:
        va, vb = va.lower(), vb.lower()
        return (va > vb) - (va < vb)


class VentanaListado(Gtk.Dialog):
    """
    Ventana genérica de listado con TreeView, búsqueda y botones CRUD.
    Puede usarse como ventana normal (show_all) o como diálogo modal (run).
    """

    def __init__(self, titulo, columnas, parent=None, modo_seleccion=False,
                 botones_extra=None):
        super().__init__(title=titulo, transient_for=parent,
                         destroy_with_parent=True)
        self.set_default_size(850, 520)
        self.columnas = columnas
        self.modo_seleccion = modo_seleccion
        self.resultado_id = None
        self.resultado_nombre = None

        area = self.get_content_area()
        area.set_spacing(4)

        # ── Barra de búsqueda ──
        hb = Gtk.Box(spacing=6)
        hb.set_margin_start(8); hb.set_margin_end(8)
        hb.set_margin_top(6)
        hb.pack_start(Gtk.Label(label=_("Filtro:")), False, False, 0)
        self.entry_filtro = Gtk.SearchEntry()
        self.entry_filtro.set_hexpand(True)
        self.entry_filtro.connect("search-changed", self._on_filtro)
        hb.pack_start(self.entry_filtro, True, True, 0)
        area.pack_start(hb, False, False, 0)

        # ── TreeView ──
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.set_margin_start(8); sw.set_margin_end(8)
        n_cols = len(self.columnas)
        # Última columna del store: color de fondo (str, oculta)
        self._COL_BG = n_cols
        self.store = Gtk.ListStore(*([str] * n_cols + [str]))
        self.filtro_model = self.store.filter_new()
        self.filtro_model.set_visible_func(self._filtrar)
        self.sort_model = Gtk.TreeModelSort(model=self.filtro_model)
        self.tv = Gtk.TreeView(model=self.sort_model)
        self.tv.set_headers_visible(True)
        self.tv.set_headers_clickable(True)
        self.tv.connect("row-activated", self._on_doble_click)
        for i, titulo_col in enumerate(self.columnas):
            rend = Gtk.CellRendererText(xpad=4)
            rend.set_property("ellipsize", 3)  # Pango.EllipsizeMode.END
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i,
                                     background=self._COL_BG)
            col.set_resizable(True)
            col.set_sort_column_id(i)
            self.store.set_sort_func(i, _sort_func_natural, i)
            col.set_expand(True)
            if i == 0:   # columna ID: oculta por defecto para el usuario
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        # ── Botones ──
        hbtn = Gtk.Box(spacing=6)
        hbtn.set_margin_start(8); hbtn.set_margin_end(8)
        hbtn.set_margin_bottom(6)

        self.btn_agregar = Gtk.Button(label="➕ " + _("Agregar"))
        self.btn_editar = Gtk.Button(label="✏️ " + _("Editar"))
        self.btn_eliminar = Gtk.Button(label="🗑️ " + _("Eliminar"))
        self.btn_seleccionar = Gtk.Button(label="✔ " + _("Seleccionar"))
        self.btn_seleccionar.get_style_context().add_class("suggested-action")

        self.btn_agregar.connect("clicked", self._on_agregar)
        self.btn_editar.connect("clicked", self._on_editar)
        self.btn_eliminar.connect("clicked", self._on_eliminar)
        self.btn_seleccionar.connect("clicked", self._on_seleccionar)

        hbtn.pack_start(self.btn_agregar, False, False, 0)
        hbtn.pack_start(self.btn_editar, False, False, 0)
        hbtn.pack_start(self.btn_eliminar, False, False, 0)

        if botones_extra:
            for lbl, cb in botones_extra:
                b = Gtk.Button(label=lbl)
                b.connect("clicked", cb)
                hbtn.pack_start(b, False, False, 0)

        hbtn.pack_end(self.btn_seleccionar, False, False, 0)
        area.pack_start(hbtn, False, False, 0)

        self.btn_seleccionar.set_visible(self.modo_seleccion)
        self.connect("key-press-event", self._on_tecla)
        self.show_all()
        self.btn_seleccionar.set_visible(self.modo_seleccion)

    # ── Helpers ──
    def _filtrar(self, model, iter_, data):
        txt = self.entry_filtro.get_text().lower()
        if not txt:
            return True
        for i in range(len(self.columnas)):
            if txt in s(model.get_value(iter_, i)).lower():
                return True
        return False

    def _on_filtro(self, entry):
        self.filtro_model.refilter()

    def _fila(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None
        # sort_model → filtro_model → store
        it2 = self.sort_model.convert_iter_to_child_iter(it)
        it3 = self.filtro_model.convert_iter_to_child_iter(it2)
        return [self.store.get_value(it3, i) for i in range(len(self.columnas))]

    def _on_agregar(self, btn):
        self.nuevo(); self.cargar_datos()

    def _on_editar(self, btn):
        f = self._fila()
        if f:
            self.editar(f[0]); self.cargar_datos()

    def _on_eliminar(self, btn):
        f = self._fila()
        if not f:
            return
        if confirmar(self, f"¿Borrar el registro ID={f[0]}?"):
            try:
                self.eliminar(f[0]); self.cargar_datos()
            except Exception as e:
                mostrar_error(self, f"Error al eliminar:\n{e}")

    def _on_seleccionar(self, btn):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[1] if len(f) > 1 else ""
            self.response(Gtk.ResponseType.OK)

    def _on_doble_click(self, tv, path, col):
        if self.modo_seleccion:
            self._on_seleccionar(None)
        else:
            self._on_editar(None)

    def _on_tecla(self, widget, event):
        alt = event.state & Gdk.ModifierType.MOD1_MASK
        if alt and event.keyval == Gdk.KEY_a:
            self._on_agregar(None)
        elif alt and event.keyval == Gdk.KEY_e:
            self._on_editar(None)
        elif alt and event.keyval == Gdk.KEY_r:
            self._on_eliminar(None)
        elif event.keyval == Gdk.KEY_Escape:
            self.hide()

    def _poblar(self, filas, ids_resaltar=None, color_resaltar="#c8a800", color_por_id=None):
        """Pobla el store.
        ids_resaltar: set/list de str ids a colorear con color_resaltar (un
            solo color parejo, uso histórico: "sin conectores", etc.)
        color_por_id: dict {id_str: color_hex} para colorear cada fila con
            un color distinto según su propio valor (ej. semáforo de riesgo:
            verde/amarillo/naranja/rojo). Tiene prioridad sobre
            ids_resaltar si un id aparece en ambos.
        """
        self.store.clear()
        n = len(self.columnas)   # slots disponibles en el ListStore
        ids_set = set(str(i) for i in ids_resaltar) if ids_resaltar else set()
        colores = color_por_id or {}
        for f in filas:
            fila_str = [s(v) for v in list(f)[:n]]
            while len(fila_str) < n:
                fila_str.append("")
            if fila_str[0] in colores:
                bg = colores[fila_str[0]]
            elif ids_set and fila_str[0] in ids_set:
                bg = color_resaltar
            else:
                bg = None
            self.store.append(fila_str + [bg])

    # ── A implementar en subclases ──
    def cargar_datos(self): raise NotImplementedError
    def nuevo(self):        raise NotImplementedError
    def editar(self, id_): raise NotImplementedError
    def eliminar(self, id_): raise NotImplementedError

    def run_and_destroy(self):
        self.show_all()
        self.run()
        self.destroy()


# ─── Diálogo simple de nombre (Marcas, Tipos, etc.) ──────────────────────────

class DialogoNombre(Gtk.Dialog):
    """Diálogo genérico para entidades con un solo campo 'nombre'."""

    def __init__(self, titulo, etiqueta=_("Nombre:"), valor="", parent=None):
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(350, 120)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        grid.set_margin_start(12); grid.set_margin_end(12)
        grid.set_margin_top(12); grid.set_margin_bottom(12)
        grid.attach(Gtk.Label(label=etiqueta, xalign=1), 0, 0, 1, 1)
        self.entry = Gtk.Entry(text=valor, activates_default=True,
                               hexpand=True)
        grid.attach(self.entry, 1, 0, 1, 1)
        self.get_content_area().add(grid)
        self.show_all()

    @property
    def valor(self):
        return self.entry.get_text().strip()


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


# ── Helpers de formularios (Gtk.Grid con label + campo) ────────────────────────
#
#  Movidos desde cabledoc.py (plan_refactor_cabledoc.md, Entrega 1). Move 1:1,
#  sin cambios de comportamiento. Usados por los diálogos de alta/edición de
#  prácticamente todas las entidades (equipos, cables, conectores, frames,
#  slots, etc.) tanto en cabledoc.py como en los archivos ya extraídos de
#  pantallas_avanzadas.py.

def _grid():
    g = Gtk.Grid(column_spacing=8, row_spacing=6,
                 margin_start=12, margin_end=12,
                 margin_top=12, margin_bottom=12)
    return g


def _lbl_entry(grid, texto, fila):
    lbl = Gtk.Label(label=texto, xalign=1)
    grid.attach(lbl, 0, fila, 1, 1)


def _entry(grid, fila):
    e = Gtk.Entry(hexpand=True, activates_default=True)
    grid.attach(e, 1, fila, 2, 1)
    return e


def _entry_btn(grid, fila, btn_label, callback, readonly=False):
    e = Gtk.Entry(hexpand=True)
    if readonly:
        e.set_editable(False)
    btn = Gtk.Button(label=btn_label)
    btn.connect("clicked", callback)
    grid.attach(e, 1, fila, 1, 1)
    grid.attach(btn, 2, fila, 1, 1)
    return e


def _searchable_combo(grid, fila, datos, btn_label=None, callback=None):
    """
    Crea un ComboBox con entrada de texto y autocompletado.
    datos: lista de tuplas (id, nombre)

    Si se pasan btn_label y callback, se agrega un botón al lado del combo
    (por ejemplo "…" para abrir el ABM correspondiente y elegir/crear un
    valor). En ese caso el combo ocupa una sola columna de grilla en lugar
    de dos, dejando la siguiente columna libre para el botón.
    """
    store = Gtk.ListStore(str, str)
    for d in datos:
        store.append([str(d[0]), s(d[1])])

    combo = Gtk.ComboBox.new_with_model_and_entry(store)
    combo.set_entry_text_column(1)
    combo.set_hexpand(True)

    entry = combo.get_child()
    completion = Gtk.EntryCompletion()
    completion.set_model(store)
    completion.set_text_column(1)
    completion.set_inline_completion(True)
    completion.set_popup_completion(True)
    # Filtro que busca en cualquier parte de la cadena
    completion.set_match_func(lambda comp, key, iter, *args: key.lower() in store.get_value(iter, 1).lower())
    entry.set_completion(completion)

    if btn_label is not None and callback is not None:
        grid.attach(combo, 1, fila, 1, 1)
        btn = Gtk.Button(label=btn_label)
        btn.connect("clicked", callback)
        grid.attach(btn, 2, fila, 1, 1)
    else:
        grid.attach(combo, 1, fila, 2, 1)
    return combo


def _get_combo_id(combo):
    it = combo.get_active_iter()
    if it:
        return combo.get_model().get_value(it, 0)
    # Fallback: buscar el texto exacto en el modelo (si el usuario escribió y no seleccionó el iter)
    txt = combo.get_child().get_text().strip()
    if not txt:
        return ""
    model = combo.get_model()
    it_busq = model.get_iter_first()
    while it_busq:
        if s(model.get_value(it_busq, 1)).strip().lower() == txt.lower():
            return model.get_value(it_busq, 0)
        it_busq = model.iter_next(it_busq)
    return ""


def _set_combo_id(combo, id_val):
    if id_val is None:
        return
    model = combo.get_model()
    it = model.get_iter_first()
    while it:
        if str(model.get_value(it, 0)) == str(id_val):
            combo.set_active_iter(it)
            return
        it = model.iter_next(it)


def _repopulate_combo(combo, datos):
    """Limpia y vuelve a cargar los datos de un searchable combo."""
    model = combo.get_model()
    model.clear()
    for d in datos:
        model.append([str(d[0]), s(d[1])])


def _pack_ultima_edicion(dialogo, tabla, pk_col, pk_val):
    """Agrega label 'ULTIMA EDICION: <fecha>' al pie del dialogo si hay fecha."""
    if not pk_val:
        return
    fecha = Modelo.devolver_fecha_ultima_edicion(tabla, pk_col, pk_val)
    if not fecha:
        return
    lbl = Gtk.Label(xalign=1)
    lbl.set_markup(f"<small><i>ULTIMA EDICIÓN: {fecha}</i></small>")
    lbl.set_margin_end(12)
    lbl.set_margin_bottom(6)
    dialogo.get_content_area().pack_end(lbl, False, False, 0)
