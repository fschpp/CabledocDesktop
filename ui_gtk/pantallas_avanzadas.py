#!/usr/bin/env python3
"""
pantallas_avanzadas.py — CableDoc GTK3

Fachada pura (ver plan_refactor_pantallas_avanzadas.md / PROGRESS_REFACTOR.md
/ plans/plan_entrega6_refactor.md). Desde la Entrega 6 este archivo no
define ninguna clase ni función propia: sólo re-exporta, con los mismos
nombres que usaban `cabledoc.py` y `diagrama_personalizado.py` antes del
refactor, las pantallas que ahora viven en sus propios módulos:

  - ArbolConexionesEquipo       → arbol_conexiones_ui.py     (Entrega 1)
  - VistaFrameSlots             → frame_slots_ui.py          (Entrega 1)
  - CoordenadasImagenSeleccion  → imagen_conectores_ui.py    (Entrega 2)
  - ImagenConectoresYCables     → imagen_conectores_ui.py    (Entrega 2)
  - VistaRack                   → rack_ui.py                 (Entrega 2)
  - PatcherasVista               → patcheras_ui.py            (Entrega 3)
  - EditorMasivoConectores*      → editor_masivo_conectores_ui.py (Entrega 4)
  - EditorMasivoSlots*           → editor_masivo_slots_ui.py      (Entrega 4)
  - DiagramaConexiones + diálogos auxiliares (_BuscadorDiagrama,
    _DialogoRuteoMatriz, _DialogoReglasLogicas, _DialogoReglasLogicasMolde,
    _DialogoCableRapido) → diagrama_conexiones_ui.py          (Entrega 6)

El "editor clásico" legacy `EditorConexiones` (alta rápida de conexiones
mediante un editor de nodos custom, previo a que esa función pasara a
reutilizar `DiagramaConexiones`) se eliminó del proyecto en la Entrega 6,
no se portó: estaba deshabilitado en el menú de `cabledoc.py` desde hacía
varias sesiones (ver changelog.txt) y no tenía otro consumidor.

Columnas de CONEXIONES_AMBOS_EXTREMOS (WHERE id_equipo = X):
  0  Cable                   1  EA: equipo (= el CONECTADO)
  3  EA: conector            5  EB: Equipo (= el CONSULTADO)
  9  id_equipo (= X)        10  id_equipo:1 (= id del CONECTADO)
  +15 x  +16 y  +17 path_archivo   (en _CON_IMAGEN, cols 11-14 son id_cable/id_conexion/id_conector/id_conector:1)
"""

from diagnostico_ui import abrir_historial_diagnosticos


# ═══════════════════════════════════════════════════════════════════════════════
# 1-2.  CoordenadasImagenSeleccion + ImagenConectoresYCables
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 2 del refactor (ver plan_refactor_pantallas_avanzadas.md):
# movidas 1:1 a imagen_conectores_ui.py. Se re-importan acá con los mismos
# nombres para no tocar ningún uso interno del resto de este archivo ni
# la fachada que consume cabledoc.py.
from imagen_conectores_ui import (
    CoordenadasImagenSeleccion, abrir_coords_imagen,
    ImagenConectoresYCables, abrir_imagen_conectores,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  ArbolConexionesEquipo
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 1 del refactor (ver plan_refactor_pantallas_avanzadas.md):
# movido 1:1 a arbol_conexiones_ui.py. Se re-importa acá con los mismos
# nombres para no tocar ningún uso interno del resto de este archivo ni
# la fachada que consume cabledoc.py.
from arbol_conexiones_ui import ArbolConexionesEquipo, abrir_arbol_conexiones


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  VistaRack
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 2 del refactor (ver plan_refactor_pantallas_avanzadas.md):
# movido 1:1 a rack_ui.py. Se re-importa acá con los mismos nombres para no
# tocar ningún uso interno del resto de este archivo ni la fachada que
# consume cabledoc.py.
from rack_ui import VistaRack, abrir_vista_rack


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  PatcherasVista
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 3 del refactor (ver plan_refactor_pantallas_avanzadas.md):
# movido 1:1 a patcheras_ui.py. Se re-importa acá con los mismos nombres
# para no tocar ningún uso interno del resto de este archivo ni la fachada
# que consume cabledoc.py.
from patcheras_ui import PatcherasVista, abrir_patcheras


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  VistaFrameSlots
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 1 del refactor (ver plan_refactor_pantallas_avanzadas.md):
# movido 1:1 a frame_slots_ui.py. Se re-importa acá con los mismos nombres
# para no tocar ningún uso interno del resto de este archivo ni la fachada
# que consume cabledoc.py.
from frame_slots_ui import VistaFrameSlots, abrir_vista_frame_slots


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  DiagramaConexiones — node editor
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 6 del refactor (ver PROGRESS_REFACTOR.md /
# plans/plan_entrega6_refactor.md): movido 1:1 a diagrama_conexiones_ui.py,
# junto con los 4 diálogos auxiliares que sólo él consume. Se re-importan
# acá con los mismos nombres — en particular _BuscadorDiagrama,
# _DialogoRuteoMatriz y _DialogoCableRapido, que los mixins de
# DiagramaConexiones (busqueda_diagrama_ui.py, ruteo_interno_diagrama_ui.py,
# edicion_conexiones_diagrama_ui.py) siguen resolviendo vía
# `from pantallas_avanzadas import ...` con import diferido dentro del
# método (mismo patrón de siempre para evitar ciclo de import) — no hizo
# falta tocar esos 3 archivos.
from diagrama_conexiones_ui import (
    DiagramaConexiones, abrir_diagrama_conexiones,
    abrir_reglas_logicas, abrir_reglas_logicas_molde,
    _BuscadorDiagrama, _DialogoRuteoMatriz,
    _DialogoReglasLogicas, _DialogoReglasLogicasMolde,
    _DialogoCableRapido,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  Editores masivos (conectores y slots)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Entrega 4 del refactor (ver PROGRESS_REFACTOR.md):
# EditorMasivoConectoresImagen/Catalogo movidas 1:1 (y unificadas con clase
# base) a editor_masivo_conectores_ui.py.
# EditorMasivoSlotsFrame/Catalogo movidas 1:1 (y unificadas con clase base)
# a editor_masivo_slots_ui.py.
# Se re-importan acá con los mismos nombres para no tocar ningún uso interno
# de este archivo ni la fachada que consume cabledoc.py.
from editor_masivo_conectores_ui import (
    EditorMasivoConectoresBase,
    EditorMasivoConectoresImagen,
    EditorMasivoConectoresCatalogo,
    abrir_editor_masivo_conectores,
    abrir_editor_masivo_conectores_catalogo,
    _hex_to_rgb,
)
from editor_masivo_slots_ui import (
    EditorMasivoSlotsBase,
    EditorMasivoSlotsFrame,
    EditorMasivoSlotsCatalogo,
    abrir_editor_masivo_slots,
    abrir_editor_masivo_slots_catalogo,
)
