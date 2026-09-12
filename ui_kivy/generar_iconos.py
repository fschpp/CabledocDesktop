#!/usr/bin/env python3
"""
generar_iconos.py — Genera los íconos PNG usados en la UI (blanco sobre
fondo transparente, 96x96, dibujados a 4x y reducidos con antialiasing).

Reemplazan a los glifos Unicode (->,  etc.) que no se ven en Pydroid 3.
En tiempo de ejecución, Kivy tiñe estos PNG blancos con `Image.color` del
color que corresponda según el tema (ver tema.py: IconoImg), así un solo
archivo por ícono sirve para modo claro y oscuro.

Se ejecuta una sola vez (los .png quedan versionados en
assets/iconos/); no hace falta correrlo de nuevo salvo que se agregue un
ícono nuevo.
"""

import os
from PIL import Image, ImageDraw

ESCALA = 4
TAM = 96 * ESCALA
GROSOR = 9 * ESCALA
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "assets", "iconos")
os.makedirs(OUT_DIR, exist_ok=True)

BLANCO = (255, 255, 255, 255)


def _lienzo():
    return Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))


def _guardar(img, nombre):
    img = img.resize((96, 96), Image.LANCZOS)
    img.save(os.path.join(OUT_DIR, nombre))


def icono_buscar():
    img = _lienzo(); d = ImageDraw.Draw(img)
    cx, cy, r = TAM * 0.42, TAM * 0.42, TAM * 0.26
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO, width=GROSOR)
    x1, y1 = cx + r * 0.72, cy + r * 0.72
    x2, y2 = TAM * 0.86, TAM * 0.86
    d.line([x1, y1, x2, y2], fill=BLANCO, width=GROSOR)
    _guardar(img, "buscar.png")


def icono_tema():
    img = _lienzo(); d = ImageDraw.Draw(img)
    cx, cy, r = TAM / 2, TAM / 2, TAM * 0.32
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO, width=GROSOR)
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 90, 270, fill=BLANCO)
    _guardar(img, "tema.png")


def icono_menu():
    img = _lienzo(); d = ImageDraw.Draw(img)
    xs = TAM * 0.18, TAM * 0.82
    for frac in (0.30, 0.5, 0.70):
        y = TAM * frac
        d.line([xs[0], y, xs[1], y], fill=BLANCO, width=GROSOR)
    _guardar(img, "menu.png")


def icono_mas_puntos():
    img = _lienzo(); d = ImageDraw.Draw(img)
    r = TAM * 0.06
    for frac in (0.22, 0.5, 0.78):
        cx = TAM * frac
        d.ellipse([cx - r, TAM / 2 - r, cx + r, TAM / 2 + r], fill=BLANCO)
    _guardar(img, "mas.png")


def icono_plus():
    img = _lienzo(); d = ImageDraw.Draw(img)
    m = TAM * 0.22
    d.line([TAM / 2, m, TAM / 2, TAM - m], fill=BLANCO, width=GROSOR)
    d.line([m, TAM / 2, TAM - m, TAM / 2], fill=BLANCO, width=GROSOR)
    _guardar(img, "plus.png")


def icono_inicio():
    img = _lienzo(); d = ImageDraw.Draw(img)
    base_y = TAM * 0.82
    apex = (TAM / 2, TAM * 0.14)
    izq = (TAM * 0.16, TAM * 0.48)
    der = (TAM * 0.84, TAM * 0.48)
    d.line([izq, apex], fill=BLANCO, width=GROSOR)
    d.line([apex, der], fill=BLANCO, width=GROSOR)
    d.line([TAM * 0.22, TAM * 0.44, TAM * 0.22, base_y], fill=BLANCO, width=GROSOR)
    d.line([TAM * 0.78, TAM * 0.44, TAM * 0.78, base_y], fill=BLANCO, width=GROSOR)
    d.line([TAM * 0.22, base_y, TAM * 0.78, base_y], fill=BLANCO, width=GROSOR)
    _guardar(img, "inicio.png")


def icono_equipos():
    img = _lienzo(); d = ImageDraw.Draw(img)
    for i, y0 in enumerate((TAM * 0.16, TAM * 0.42, TAM * 0.68)):
        y1 = y0 + TAM * 0.18
        d.rounded_rectangle([TAM * 0.14, y0, TAM * 0.86, y1],
                            radius=TAM * 0.04, outline=BLANCO, width=GROSOR)
        cx = TAM * 0.24
        r = TAM * 0.025
        cy = (y0 + y1) / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLANCO)
    _guardar(img, "equipos.png")


def icono_cables():
    img = _lienzo(); d = ImageDraw.Draw(img)
    pts = [(TAM * 0.14, TAM * 0.3), (TAM * 0.40, TAM * 0.3),
          (TAM * 0.40, TAM * 0.7), (TAM * 0.60, TAM * 0.7),
          (TAM * 0.60, TAM * 0.3), (TAM * 0.86, TAM * 0.3)]
    d.line(pts, fill=BLANCO, width=GROSOR, joint="curve")
    for p in (pts[0], pts[-1]):
        r = TAM * 0.05
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], outline=BLANCO,
                  width=int(GROSOR * 0.7))
    _guardar(img, "cables.png")


def icono_conexiones():
    img = _lienzo(); d = ImageDraw.Draw(img)
    r = TAM * 0.16
    c1 = (TAM * 0.34, TAM * 0.5)
    c2 = (TAM * 0.66, TAM * 0.5)
    d.ellipse([c1[0] - r, c1[1] - r, c1[0] + r, c1[1] + r], outline=BLANCO,
             width=GROSOR)
    d.ellipse([c2[0] - r, c2[1] - r, c2[0] + r, c2[1] + r], outline=BLANCO,
             width=GROSOR)
    _guardar(img, "conexiones.png")


def icono_racks():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.rounded_rectangle([TAM * 0.20, TAM * 0.10, TAM * 0.80, TAM * 0.90],
                        radius=TAM * 0.04, outline=BLANCO, width=GROSOR)
    for frac in (0.30, 0.5, 0.70):
        y = TAM * frac
        d.line([TAM * 0.20, y, TAM * 0.80, y], fill=BLANCO,
              width=int(GROSOR * 0.6))
    _guardar(img, "racks.png")


def icono_frame():
    img = _lienzo(); d = ImageDraw.Draw(img)
    m = TAM * 0.14
    d.rectangle([m, m, TAM - m, TAM - m], outline=BLANCO, width=GROSOR)
    mid = TAM / 2
    d.line([m, mid, TAM - m, mid], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([mid, m, mid, TAM - m], fill=BLANCO, width=int(GROSOR * 0.7))
    _guardar(img, "frame.png")


def icono_diagrama():
    img = _lienzo(); d = ImageDraw.Draw(img)
    pts = {
        "a": (TAM * 0.22, TAM * 0.24), "b": (TAM * 0.78, TAM * 0.24),
        "c": (TAM * 0.50, TAM * 0.62), "d": (TAM * 0.50, TAM * 0.88),
    }
    d.line([pts["a"], pts["c"]], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([pts["b"], pts["c"]], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([pts["c"], pts["d"]], fill=BLANCO, width=int(GROSOR * 0.7))
    r = TAM * 0.09
    for p in pts.values():
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=BLANCO)
    _guardar(img, "diagrama.png")


def icono_patchera():
    img = _lienzo(); d = ImageDraw.Draw(img)
    r = TAM * 0.06
    for fy in (0.28, 0.5, 0.72):
        for fx in (0.20, 0.40, 0.60, 0.80):
            cx, cy = TAM * fx, TAM * fy
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO,
                      width=int(GROSOR * 0.6))
    _guardar(img, "patchera.png")


def icono_vista_rack():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.rounded_rectangle([TAM * 0.18, TAM * 0.10, TAM * 0.82, TAM * 0.90],
                        radius=TAM * 0.04, outline=BLANCO, width=GROSOR)
    d.rectangle([TAM * 0.28, TAM * 0.20, TAM * 0.72, TAM * 0.36],
               outline=BLANCO, width=int(GROSOR * 0.6))
    d.rectangle([TAM * 0.28, TAM * 0.44, TAM * 0.72, TAM * 0.60],
               outline=BLANCO, width=int(GROSOR * 0.6))
    _guardar(img, "vista_rack.png")


def icono_atras():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.line([TAM * 0.62, TAM * 0.20, TAM * 0.30, TAM * 0.5], fill=BLANCO,
          width=GROSOR)
    d.line([TAM * 0.30, TAM * 0.5, TAM * 0.62, TAM * 0.80], fill=BLANCO,
          width=GROSOR)
    _guardar(img, "atras.png")


def icono_editar():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.line([TAM * 0.20, TAM * 0.80, TAM * 0.62, TAM * 0.38], fill=BLANCO,
          width=GROSOR)
    d.line([TAM * 0.62, TAM * 0.38, TAM * 0.80, TAM * 0.20], fill=BLANCO,
          width=int(GROSOR * 0.8))
    d.line([TAM * 0.18, TAM * 0.82, TAM * 0.28, TAM * 0.72], fill=BLANCO,
          width=int(GROSOR * 0.8))
    _guardar(img, "editar.png")


def icono_eliminar():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.rectangle([TAM * 0.28, TAM * 0.30, TAM * 0.72, TAM * 0.86],
               outline=BLANCO, width=GROSOR)
    d.line([TAM * 0.18, TAM * 0.22, TAM * 0.82, TAM * 0.22], fill=BLANCO,
          width=GROSOR)
    d.line([TAM * 0.40, TAM * 0.14, TAM * 0.60, TAM * 0.14], fill=BLANCO,
          width=GROSOR)
    _guardar(img, "eliminar.png")


def icono_guardar():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.line([TAM * 0.18, TAM * 0.52, TAM * 0.40, TAM * 0.76], fill=BLANCO,
          width=GROSOR)
    d.line([TAM * 0.40, TAM * 0.76, TAM * 0.84, TAM * 0.24], fill=BLANCO,
          width=GROSOR)
    _guardar(img, "guardar.png")


def icono_cerrar():
    img = _lienzo(); d = ImageDraw.Draw(img)
    m = TAM * 0.24
    d.line([m, m, TAM - m, TAM - m], fill=BLANCO, width=GROSOR)
    d.line([TAM - m, m, m, TAM - m], fill=BLANCO, width=GROSOR)
    _guardar(img, "cerrar.png")


def icono_imagen():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.rounded_rectangle([TAM * 0.14, TAM * 0.20, TAM * 0.86, TAM * 0.80],
                        radius=TAM * 0.05, outline=BLANCO, width=GROSOR)
    cx, cy, r = TAM * 0.34, TAM * 0.40, TAM * 0.07
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO,
             width=int(GROSOR * 0.7))
    d.line([TAM * 0.20, TAM * 0.72, TAM * 0.42, TAM * 0.52,
           TAM * 0.58, TAM * 0.64, TAM * 0.72, TAM * 0.48,
           TAM * 0.82, TAM * 0.60], fill=BLANCO, width=int(GROSOR * 0.7),
          joint="curve")
    _guardar(img, "imagen.png")


def icono_conector():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.rounded_rectangle([TAM * 0.30, TAM * 0.14, TAM * 0.70, TAM * 0.56],
                        radius=TAM * 0.05, outline=BLANCO, width=GROSOR)
    d.line([TAM * 0.40, TAM * 0.14, TAM * 0.40, TAM * 0.02], fill=BLANCO,
          width=int(GROSOR * 0.7))
    d.line([TAM * 0.60, TAM * 0.14, TAM * 0.60, TAM * 0.02], fill=BLANCO,
          width=int(GROSOR * 0.7))
    d.line([TAM * 0.50, TAM * 0.56, TAM * 0.50, TAM * 0.90], fill=BLANCO,
          width=GROSOR)
    _guardar(img, "conector.png")


def icono_ver():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.arc([TAM * 0.10, TAM * 0.10, TAM * 0.90, TAM * 0.70], 200, 340,
         fill=BLANCO, width=GROSOR)
    d.arc([TAM * 0.10, TAM * 0.30, TAM * 0.90, TAM * 0.90], 20, 160,
         fill=BLANCO, width=GROSOR)
    cx, cy, r = TAM / 2, TAM * 0.5, TAM * 0.12
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO, width=GROSOR)
    _guardar(img, "ver.png")


def icono_ubicacion():
    img = _lienzo(); d = ImageDraw.Draw(img)
    cx, top, r = TAM / 2, TAM * 0.14, TAM * 0.26
    cy = top + r
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO, width=GROSOR)
    d.polygon([(cx - r * 0.55, cy + r * 0.55), (cx + r * 0.55, cy + r * 0.55),
              (cx, TAM * 0.88)], fill=BLANCO)
    _guardar(img, "ubicacion.png")


def icono_arbol():
    img = _lienzo(); d = ImageDraw.Draw(img)
    # nodo raíz arriba, dos ramas hacia abajo — jerarquía simple
    raiz = (TAM * 0.28, TAM * 0.18)
    hijo1 = (TAM * 0.28, TAM * 0.50)
    nieto1 = (TAM * 0.62, TAM * 0.38)
    nieto2 = (TAM * 0.62, TAM * 0.62)
    hijo2 = (TAM * 0.28, TAM * 0.82)
    d.line([raiz, hijo1], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([hijo1, nieto1], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([hijo1, nieto2], fill=BLANCO, width=int(GROSOR * 0.7))
    d.line([raiz, hijo2], fill=BLANCO, width=int(GROSOR * 0.7))
    r = TAM * 0.07
    for p in (raiz, hijo1, nieto1, nieto2, hijo2):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=BLANCO)
    _guardar(img, "arbol.png")


def icono_chevron_derecha():
    img = _lienzo(); d = ImageDraw.Draw(img)
    d.line([TAM * 0.38, TAM * 0.20, TAM * 0.68, TAM * 0.5], fill=BLANCO,
          width=GROSOR)
    d.line([TAM * 0.68, TAM * 0.5, TAM * 0.38, TAM * 0.80], fill=BLANCO,
          width=GROSOR)
    _guardar(img, "chevron_derecha.png")


def icono_mas_vertical():
    img = _lienzo(); d = ImageDraw.Draw(img)
    r = TAM * 0.06
    for frac in (0.22, 0.5, 0.78):
        cy = TAM * frac
        d.ellipse([TAM / 2 - r, cy - r, TAM / 2 + r, cy + r], fill=BLANCO)
    _guardar(img, "mas_vertical.png")


def _fondo_input_pill():
    """Imagen 9-patch (blanca, esquinas redondeadas) usada como
    background_normal/active de TextInput — ver tema.py. TextInput
    inserta los glifos de texto dinámicamente en su propio
    canvas.before; dibujar el fondo con instrucciones de canvas propias
    (Color/RoundedRectangle) terminaba pintándose ENCIMA del texto en
    vez de detrás. Usar una imagen como `background_normal` evita el
    problema por completo (pasa a ser parte del pipeline nativo de
    TextInput, en la capa correcta)."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 199, 199], radius=28, fill=(255, 255, 255, 255))
    img.save(os.path.join(OUT_DIR, "_input_pill.png"))


def icono_lupa_check():
    img = _lienzo(); d = ImageDraw.Draw(img)
    cx, cy, r = TAM * 0.42, TAM * 0.42, TAM * 0.26
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLANCO, width=GROSOR)
    x1, y1 = cx + r * 0.72, cy + r * 0.72
    x2, y2 = TAM * 0.86, TAM * 0.86
    d.line([x1, y1, x2, y2], fill=BLANCO, width=GROSOR)
    # tilde adentro del círculo, un poco más fino para que quepa
    gt = int(GROSOR * 0.55)
    d.line([cx - r * 0.5, cy, cx - r * 0.12, cy + r * 0.38], fill=BLANCO,
          width=gt)
    d.line([cx - r * 0.12, cy + r * 0.38, cx + r * 0.55, cy - r * 0.35],
          fill=BLANCO, width=gt)
    _guardar(img, "lupa_check.png")


def icono_filtro():
    """Embudo (funnel) — botón que despliega el panel de filtros
    (categorías + checkboxes) del listado de Equipos."""
    img = _lienzo(); d = ImageDraw.Draw(img)
    puntos = [
        (TAM * 0.16, TAM * 0.20), (TAM * 0.84, TAM * 0.20),
        (TAM * 0.58, TAM * 0.52), (TAM * 0.58, TAM * 0.84),
        (TAM * 0.42, TAM * 0.72), (TAM * 0.42, TAM * 0.52),
    ]
    d.polygon(puntos, outline=BLANCO)
    d.line(puntos + [puntos[0]], fill=BLANCO, width=GROSOR, joint="curve")
    _guardar(img, "filtro.png")


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("icono_"):
            fn()
    _fondo_input_pill()
    print("Iconos generados en", OUT_DIR)
    print(sorted(os.listdir(OUT_DIR)))
