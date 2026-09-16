"""
svg_raster_pygame.py — Rasterizado de SVG en el propio dispositivo vía
pygame/SDL_image (motor NanoSVG), como ruta complementaria al pipeline de
cache PNG generado en desktop (Fase 3.3) y al fallback svglib+reportlab+
rlPyCairo ya existente en widgets_base.py (Fase 3.4).

Ver plan_svg_pygame_nanosvg_v1.md para el contexto completo. Resumen de lo
CONFIRMADO en dispositivo real (Pydroid 3, pygame 2.6.1 clásico —no
pygame-ce—, SDL_image (2, 6, 3), 2026-09-16) antes de escribir este módulo:

  - `pygame.image.load()` carga `.svg` directamente (soporte SDL_image
    desde 2.0.2 / pygame desde 2.0) y devuelve un Surface ya rasterizado
    con NanoSVG. Probado OK contra SVG sintético y contra 7 SVG reales
    del proyecto (fondos de equipo/plano + símbolos de conector), sin
    excepciones.
  - Pydroid 3 trae pygame clásico, NO pygame-ce: `pygame.image.
    load_sized_svg` no existe en ese build. Este módulo lo usa si está
    disponible (por si algún entorno sí trae pygame-ce) pero nunca lo
    asume.
  - Para pedir una resolución mayor que el tamaño intrínseco del SVG,
    `transform="scale(N)"` en el nodo raíz NO sirve — SDL_image/NanoSVG
    calculan el tamaño del Surface a partir de width/height (o viewBox si
    faltan), no de transforms. La única forma confirmada es sobreescribir
    width/height directamente en el XML antes de cargarlo; NanoSVG
    reescala el contenido para llenar ese canvas nuevo (transform
    viewBox→viewport estándar). Confirmado con factor x4 exacto y
    proporcional sobre 7 SVG reales distintos.

Pendiente (no cubierto por las pruebas hasta ahora, ver PROGRESS.md):
auditar `catalogo_simbolo_conector.svg_fragmento` reales en busca de
`<text>` (NanoSVG no lo soporta) o gradientes complejos. Esto no bloquea
la existencia del módulo: cualquier fragmento problemático simplemente
hace que `rasterizar_svg_bytes` devuelva None y el llamador cae al
fallback existente (svglib/reportlab o símbolo genérico), nunca rompe la
pantalla.

Importante (plan §3.2): este módulo NUNCA llama pygame.init() completo
(inicializaría video/audio y podría pelear con la ventana real de Kivy).
Sólo importa `pygame` y usa `pygame.image.*`; si algún build de SDL
headless exige un mínimo de inicialización del subsistema de video para
que `pygame.image.load` funcione, ese mínimo se hace encapsulado acá
adentro (driver 'dummy', sin ventana visible), nunca en el arranque de
la app.
"""

import io
import os
import re

from core.logger_cabledoc import log_error, log_debug

# ── Estado cacheado (una sola detección por proceso) ────────────────────────
_PYGAME_MODULO = None          # módulo pygame ya importado, o False si falló
_SVG_DISPONIBLE = None         # None = no probado todavía; True/False después
_DIAG_LOGUEADO = False


def _importar_pygame():
    """Import perezoso y cacheado de pygame. Devuelve el módulo o None si
    no está instalado. Nunca lanza excepción."""
    global _PYGAME_MODULO
    if _PYGAME_MODULO is not None:
        return _PYGAME_MODULO or None
    try:
        import pygame
        _PYGAME_MODULO = pygame
        return pygame
    except Exception as e:
        _PYGAME_MODULO = False
        log_debug(f"svg_raster_pygame: pygame no disponible — "
                  f"{type(e).__name__}: {e}")
        return None


_SVG_MINIMO = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4">'
               b'<rect width="4" height="4" fill="#000"/></svg>')


def _asegurar_subsistema_imagen(pygame):
    """Prueba una carga mínima de SVG. Si pygame.error indica que hace
    falta inicializar el subsistema de video (algunos builds de SDL
    headless lo exigen), inicializa SOLO ese subsistema con driver
    'dummy' — sin ventana visible, sin tocar audio, sin pelear con la
    ventana real de Kivy — y reintenta una vez. Devuelve True/False,
    nunca lanza."""
    try:
        pygame.image.load(io.BytesIO(_SVG_MINIMO))
        return True
    except pygame.error:
        try:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            pygame.display.init()
            pygame.image.load(io.BytesIO(_SVG_MINIMO))
            return True
        except Exception as e:
            log_debug(f"svg_raster_pygame: subsistema de imagen no "
                      f"disponible aun con driver dummy — "
                      f"{type(e).__name__}: {e}")
            return False
    except Exception as e:
        log_debug(f"svg_raster_pygame: fallo inesperado probando carga "
                  f"mínima — {type(e).__name__}: {e}")
        return False


def svg_disponible():
    """True si pygame + SDL_image con soporte SVG están utilizables en
    este entorno. Se calcula una sola vez por proceso, intentando
    rasterizar un SVG mínimo en memoria. Nunca lanza excepción hacia
    afuera — cualquier fallo (pygame no instalado, SDL_image sin soporte
    SVG, subsistema de imagen no inicializable) se traduce en False."""
    global _SVG_DISPONIBLE
    if _SVG_DISPONIBLE is not None:
        return _SVG_DISPONIBLE
    pygame = _importar_pygame()
    if pygame is None:
        _SVG_DISPONIBLE = False
        return False
    try:
        ok = _asegurar_subsistema_imagen(pygame)
        if ok:
            log_debug(
                f"svg_raster_pygame: disponible — pygame "
                f"{pygame.version.ver}, SDL_image "
                f"{pygame.image.get_sdl_image_version()}, "
                f"load_sized_svg={hasattr(pygame.image, 'load_sized_svg')}")
        _SVG_DISPONIBLE = ok
    except Exception as e:
        log_error("svg_raster_pygame.svg_disponible", e)
        _SVG_DISPONIBLE = False
    return _SVG_DISPONIBLE


# ── Sobreescritura de width/height (única forma confirmada de pedir más
#    resolución — ver docstring del módulo) ─────────────────────────────────

_RE_SVG_TAG_INICIO = re.compile(r"<svg\b", re.IGNORECASE)
_RE_ATTR_WIDTH = re.compile(r'''\s+width\s*=\s*(["\']).*?\1''', re.IGNORECASE)
_RE_ATTR_HEIGHT = re.compile(r'''\s+height\s*=\s*(["\']).*?\1''', re.IGNORECASE)


def _forzar_ancho_alto(svg_bytes, ancho, alto):
    """Sobreescribe (o agrega) width/height en el <svg> raíz con valores
    en px planos. Lanza ValueError si no encuentra un tag <svg> válido —
    el llamador debe atraparlo, es una precondición de formato, no un
    fallo de rasterizado."""
    texto = svg_bytes.decode("utf-8", errors="replace")
    m = _RE_SVG_TAG_INICIO.search(texto)
    if not m:
        raise ValueError("no se encontró tag <svg> en el documento")
    fin_tag = texto.find(">", m.start())
    if fin_tag < 0:
        raise ValueError("tag <svg> sin cierre '>'")
    cabecera = texto[m.start():fin_tag]
    cabecera = _RE_ATTR_WIDTH.sub("", cabecera)
    cabecera = _RE_ATTR_HEIGHT.sub("", cabecera)
    cabecera += f' width="{ancho}" height="{alto}"'
    return (texto[:m.start()] + cabecera + texto[fin_tag:]).encode("utf-8")


def rasterizar_svg_bytes(svg_bytes, ancho_px=None):
    """Rasteriza `svg_bytes` (documento SVG completo, con tag <svg> raíz)
    con pygame/SDL_image (NanoSVG). Si `ancho_px` se especifica, escala
    manteniendo la relación de aspecto del viewBox/width/height original
    — usa `load_sized_svg` si está disponible (pygame-ce) o la
    sobreescritura de width/height confirmada en dispositivo si no.

    Devuelve un `pygame.Surface`, o None ante cualquier fallo (SVG
    inválido, feature no soportada por NanoSVG, pygame no disponible,
    etc.) — nunca lanza excepción. El llamador debe caer a su propio
    fallback (svglib/reportlab, o símbolo/imagen genérica)."""
    if not svg_disponible():
        return None
    pygame = _importar_pygame()
    try:
        if ancho_px is None:
            return pygame.image.load(io.BytesIO(svg_bytes))

        surf_natural = pygame.image.load(io.BytesIO(svg_bytes))
        w0, h0 = surf_natural.get_size()
        if w0 <= 0 or h0 <= 0:
            return None
        alto_px = max(1, round(ancho_px * h0 / w0))

        if hasattr(pygame.image, "load_sized_svg"):
            return pygame.image.load_sized_svg(
                io.BytesIO(svg_bytes), (ancho_px, alto_px))

        svg_reescalado = _forzar_ancho_alto(svg_bytes, ancho_px, alto_px)
        return pygame.image.load(io.BytesIO(svg_reescalado))
    except Exception as e:
        log_error("svg_raster_pygame.rasterizar_svg_bytes", e)
        return None


def rasterizar_svg_bytes_a_png_bytes(svg_bytes, ancho_px=None):
    """Igual que `rasterizar_svg_bytes`, pero devuelve el resultado ya
    codificado como PNG en memoria (bytes), para envolver directamente en
    un `kivy.core.image.Image` sin pasar por disco — mismo patrón que ya
    usa `crear_textura_imagen_svg`/`crear_textura_simbolo` con el buffer
    de reportlab. Devuelve None ante cualquier fallo."""
    surf = rasterizar_svg_bytes(svg_bytes, ancho_px=ancho_px)
    if surf is None:
        return None
    pygame = _importar_pygame()
    try:
        buf = io.BytesIO()
        pygame.image.save(surf, buf, "png")
        return buf.getvalue()
    except Exception as e:
        log_error("svg_raster_pygame.rasterizar_svg_bytes_a_png_bytes", e)
        return None


def rasterizar_svg_a_png(ruta_svg, ruta_png_destino, ancho_px=None):
    """Rasteriza el archivo `ruta_svg` y escribe `ruta_png_destino`. Si
    `ancho_px` se especifica y no hay `load_sized_svg`, aplica la
    sobreescritura de width/height (ver `_forzar_ancho_alto`) calculando
    el factor a partir del tamaño natural del documento. Devuelve False
    (sin excepción) ante cualquier fallo — el llamador cae a su propio
    fallback (contrato del plan §3.2)."""
    try:
        with open(ruta_svg, "rb") as f:
            datos = f.read()
    except OSError as e:
        log_debug(f"svg_raster_pygame: no se pudo leer {ruta_svg} — "
                  f"{type(e).__name__}: {e}")
        return False
    surf = rasterizar_svg_bytes(datos, ancho_px=ancho_px)
    if surf is None:
        return False
    pygame = _importar_pygame()
    try:
        pygame.image.save(surf, ruta_png_destino)
        return True
    except Exception as e:
        log_error("svg_raster_pygame.rasterizar_svg_a_png", e)
        return False
