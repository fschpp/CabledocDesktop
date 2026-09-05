#!/usr/bin/env python3
"""
CableDoc GTK3 - Gestión de cableado e infraestructura de red
Conversión de VB.NET/WinForms a Python/GTK3 (PyGObject)

Requisitos:
    pip install pygobject          # o: apt install python3-gi
    pip install pillow             # (opcional, para vistas previas de imagen)
    apt install graphviz           # para generación de diagramas (dot)

Uso:
    python3 cabledoc.py

Entrega 10 (plan_refactor_cabledoc.md) cierra el refactor iniciado en la
Entrega 1: este archivo pasó de 9.405 líneas originales a una fachada
delgada de ~1.000 líneas que contiene únicamente `VentanaPrincipal`
(ventana principal y menú de la app), `APP_VERSION`, los helpers de
formularios que no encontraron un dominio propio
(`_escribir_json_comprimido`, `_leer_json_generico`,
`_sel_imagen_desde_abm`), el punto de entrada (`if __name__ ==
"__main__"`), y las reexportaciones de los 12 módulos `*_ui.py` extraídos
en las Entregas 1-10, preservadas para no romper los `from cabledoc import
...` externos que ya dependían de estos nombres. Toda la lógica de negocio
de cada dominio (racks, equipos, conectores, señal, catálogos, etc.) vive
en su módulo dedicado.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib, Pango, GObject, GdkPixbuf
import subprocess
import os
import sys
import shutil
import time
import json
import zipfile
from datetime import datetime

# Versión de la app, formato a.aaammddhhmmss (a = versión mayor).
# Actualizar esta variable con fecha/hora de entrega cada vez que se
# implementa una nueva funcionalidad pedida por el usuario.
APP_VERSION = "1.20260904235900"

from modelo import Modelo, IMG_DIR, DB_PATH, PICON_DIR

# Carpeta de recursos gráficos propios de la aplicación (íconos, logo, etc.)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ICONO_APP_PATH = os.path.join(ASSETS_DIR, "icono_aplicacion.png")
from cypher_console import CypherConsole
from acerca_de import abrir_acerca_de
try:
    from i18n import _, set_lang, get_lang, cargar_idioma_guardado, IDIOMAS_DISPONIBLES
    cargar_idioma_guardado()
except ImportError:
    def _(t): return t
    def set_lang(c): pass
    def get_lang(): return "es"
    def cargar_idioma_guardado(): pass
    IDIOMAS_DISPONIBLES = {"es": "Español"}
from pantallas_avanzadas import (
    abrir_coords_imagen,
    abrir_imagen_conectores,
    abrir_arbol_conexiones,
    abrir_vista_rack,
    abrir_patcheras,
    abrir_vista_frame_slots,
    abrir_reglas_logicas,
    abrir_reglas_logicas_molde,
    abrir_historial_diagnosticos,
    CoordenadasImagenSeleccion,
    ImagenConectoresYCables,
    ArbolConexionesEquipo,
    VistaRack,
    PatcherasVista,
    VistaFrameSlots,
    DiagramaConexiones,
    abrir_diagrama_conexiones,
    abrir_editor_masivo_conectores,
    abrir_editor_masivo_conectores_catalogo,
    abrir_editor_masivo_slots,
    abrir_editor_masivo_slots_catalogo,
)
from diagrama_personalizado import DiagramaPersonalizado

# ─── Utilidades genéricas / base de listados / helpers de formulario ─────────
#
# Movidas a pantallas_comunes.py (plan_refactor_cabledoc.md, Entrega 1):
# s, mostrar_error, mostrar_info, confirmar, _sort_func_natural,
# VentanaListado, DialogoNombre, _grid, _lbl_entry, _entry, _entry_btn,
# _searchable_combo, _get_combo_id, _set_combo_id, _repopulate_combo,
# _pack_ultima_edicion. Se reexportan acá sin cambios para que todo el
# código de este archivo (y los `from cabledoc import ...` externos de
# patcheras_ui.py, rack_ui.py, etc.) siga funcionando idéntico.
from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
    confirmar,
    _sort_func_natural,
    VentanaListado,
    DialogoNombre,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
    _pack_ultima_edicion,
    _parse_float_opt,
    _fmt_float_opt,
)

# ─── Cables y conexiones ──────────────────────────────────────────────────────
#
# Movidas a cables_conexiones_ui.py (plan_refactor_cabledoc.md, Entrega 2):
# CablesListado, _DialogoFusion, _DialogoEligeLadoFantasma, _DialogoCable,
# ConexionesListado, _DialogoConexion. Se reexportan acá sin cambios para que
# todo el código de este archivo (y los `from cabledoc import ...` externos)
# siga funcionando idéntico.
from cables_conexiones_ui import (
    CablesListado,
    _DialogoFusion,
    _DialogoEligeLadoFantasma,
    _DialogoCable,
    ConexionesListado,
    _DialogoConexion,
)

# ─── Equipos — Listado y Ficha completa ───────────────────────────────────────
#
# Movidas a equipos_ui.py (plan_refactor_cabledoc.md, Entrega 3):
# EquiposListado, _DialogoDireccionConector, _DialogoEquipo. Se reexportan
# acá sin cambios para que todo el código de este archivo (y los
# `from cabledoc import ...` externos) siga funcionando idéntico.
from equipos_ui import (
    EquiposListado,
    _DialogoDireccionConector,
    _DialogoEquipo,
)

# ─── Equipos — Alta rápida individual ─────────────────────────────────────────
#
# Movida a equipos_alta_rapida_ui.py (plan_refactor_cabledoc.md, Entrega 3):
# _DialogoAltaRapidaEquipo. Se reexporta acá sin cambios.
from equipos_alta_rapida_ui import _DialogoAltaRapidaEquipo

# ─── Conectores ────────────────────────────────────────────────────────────────
#
# Movidas a conectores_ui.py (plan_refactor_cabledoc.md, Entrega 4):
# ConectoresListado, _DialogoConector, _DialogoRenombrarConectores. Se
# reexportan acá sin cambios para que todo el código de este archivo (y los
# `from cabledoc import ...` externos) siga funcionando idéntico.
from conectores_ui import (
    ConectoresListado,
    _DialogoConector,
    _DialogoRenombrarConectores,
)

# ─── Catálogo de equipos (moldes) ──────────────────────────────────────────────
#
# Movidas a catalogo_equipos_ui.py (plan_refactor_cabledoc.md, Entrega 5):
# CatalogoEquiposListado, _DialogoConflictosImportacion,
# _DialogoCatalogoEquipo, _ConectoresCatalogoListado,
# _DialogoConectorCatalogo, _DialogoInstanciarCatalogo,
# _DialogoDuplicarMolde. Se reexportan acá sin cambios para que todo el
# código de este archivo (y los `from cabledoc import ...` externos) siga
# funcionando idéntico.
from catalogo_equipos_ui import (
    CatalogoEquiposListado,
    _DialogoConflictosImportacion,
    _DialogoCatalogoEquipo,
    _ConectoresCatalogoListado,
    _DialogoConectorCatalogo,
    _DialogoInstanciarCatalogo,
    _DialogoDuplicarMolde,
)

# ─── Catálogo de equipos — Alta rápida de molde ────────────────────────────────
#
# Movida a catalogo_equipos_alta_rapida_ui.py (plan_refactor_cabledoc.md,
# Entrega 5): _DialogoAltaRapidaCatalogo. Se reexporta acá sin cambios.
from catalogo_equipos_alta_rapida_ui import _DialogoAltaRapidaCatalogo

# ─── Señal (catálogos) ────────────────────────────────────────────────────────
#
# Movidas a senal_catalogo_ui.py (plan_refactor_cabledoc.md, Entrega 6):
# _DialogoSenal, SenalesListado, TiposFormatoSenalListado,
# _mostrar_donde_esta_senal, abrir_buscador_senal, _DialogoLinajeSenal,
# _ArbolLinajeSenal, _mostrar_lista_simple, _DialogoPropagacionSenal,
# abrir_propagacion_senal, _DialogoReportesSenal, abrir_reportes_senal,
# abrir_limpiar_senales_propagadas. Se reexportan acá sin cambios para que
# todo el código de este archivo (y los `from cabledoc import ...` externos,
# ej. conectores_ui.py con _DialogoSenal) siga funcionando idéntico.
from senal_catalogo_ui import (
    _DialogoSenal,
    SenalesListado,
    TiposFormatoSenalListado,
    _mostrar_donde_esta_senal,
    abrir_buscador_senal,
    _DialogoLinajeSenal,
    _ArbolLinajeSenal,
    _mostrar_lista_simple,
    _DialogoPropagacionSenal,
    abrir_propagacion_senal,
    _DialogoReportesSenal,
    abrir_reportes_senal,
    abrir_limpiar_senales_propagadas,
)

# ─── Racks / Salas ─────────────────────────────────────────────────────────────
#
# Movidas a racks_salas_ui.py (plan_refactor_cabledoc.md, Entrega 7, parte 1/2):
# RacksListado, _DialogoRack, PosicionEnRackListado, _DialogoPosicionRack,
# SalasListado, _DialogoRackPorSala, RackPorSalaListado,
# _DialogoEquipoNoRackSala, EquiposNoRackSalaListado. Se reexportan acá sin
# cambios para que todo el código de este archivo (y los
# `from cabledoc import ...` externos, ej. pantallas_avanzadas.py con
# RacksListado) siga funcionando idéntico.
from racks_salas_ui import (
    RacksListado,
    _DialogoRack,
    PosicionEnRackListado,
    _DialogoPosicionRack,
    SalasListado,
    _DialogoRackPorSala,
    RackPorSalaListado,
    _DialogoEquipoNoRackSala,
    EquiposNoRackSalaListado,
)

# ─── Frames / Slots (catálogo e instancia) ─────────────────────────────────────
#
# Movidas a frames_slots_ui.py (plan_refactor_cabledoc.md, Entrega 7, parte
# 2/2): CatalogoFramesListado, _DialogoCatalogoFrame, _SlotsCatalogoListado,
# _DialogoSlotCatalogo, _DialogoInstanciarCatalogoFrame, FramesListado,
# _DialogoFrame, SlotsListado, _DialogoSlot. Se reexportan acá sin cambios
# para que todo el código de este archivo (y los `from cabledoc import ...`
# externos, ej. pantallas_avanzadas.py con _DialogoFrame) siga funcionando
# idéntico.
from frames_slots_ui import (
    CatalogoFramesListado,
    _DialogoCatalogoFrame,
    _SlotsCatalogoListado,
    _DialogoSlotCatalogo,
    _DialogoInstanciarCatalogoFrame,
    FramesListado,
    _DialogoFrame,
    SlotsListado,
    _DialogoSlot,
)

# ─── Catálogos básicos ──────────────────────────────────────────────────────────
#
# Movidas a catalogos_basicos_ui.py (plan_refactor_cabledoc.md, Entrega 8):
# MarcasListado, _DialogoTipoEquipo, TiposEquipoListado, TiposConectorListado,
# RiesgoSenalListado, _DialogoTipoCable, TiposCableListado, _DialogoTipoFicha,
# TiposFichaListado, CategoriasProblemaListado, ProblemasEquipoListado,
# _DialogoProblema, ImagenesListado, _DialogoImagen, ConexionesDeEquipoVentana,
# DiagramasGuardadosListado, GeneradorDiagrama, EquipoInfoExtra. Se
# reexportan acá sin cambios para que todo el código de este archivo (y los
# `from cabledoc import ...` externos, ej. catalogo_equipos_ui.py con
# MarcasListado/ImagenesListado) siga funcionando idéntico. Incluye 4
# bloques que el plan (§4) no había asignado a ningún módulo destino
# (ConexionesDeEquipoVentana, DiagramasGuardadosListado, GeneradorDiagrama,
# EquipoInfoExtra) — ver docstring de catalogos_basicos_ui.py para el
# detalle de esta desviación documentada.
from catalogos_basicos_ui import (
    MarcasListado,
    _DialogoTipoEquipo,
    TiposEquipoListado,
    TiposConectorListado,
    RiesgoSenalListado,
    _DialogoTipoCable,
    TiposCableListado,
    _DialogoTipoFicha,
    TiposFichaListado,
    CategoriasProblemaListado,
    ProblemasEquipoListado,
    _DialogoProblema,
    ImagenesListado,
    _DialogoImagen,
    ConexionesDeEquipoVentana,
    DiagramasGuardadosListado,
    GeneradorDiagrama,
    EquipoInfoExtra,
)


# ─── Conectores de catálogo — Renombrado masivo ────────────────────────────────
#
# Movida a catalogo_equipos_ui.py (plan_refactor_cabledoc.md, Entrega 10,
# cierre): _DialogoRenombrarConectoresCatalogo. Era el único bloque de
# dominio que seguía sin mover desde la Entrega 8 (el plan §4 no la
# contemplaba porque no pertenece al bloque "catálogos básicos"). Se
# reexporta acá sin cambios, junto a su único consumidor
# (_DialogoCatalogoEquipo, ya vive en el mismo archivo destino).
from catalogo_equipos_ui import _DialogoRenombrarConectoresCatalogo


# ─── Panel de árbol de infraestructura ───────────────────────────────────────
#
# Movida a panel_arbol_ui.py (plan_refactor_cabledoc.md, Entrega 9):
# PanelArbol. Se reexporta acá sin cambios. Es el orquestador visual que
# referencia diálogos de todos los dominios ya extraídos (Entregas 1-8);
# no tiene consumidores externos fuera de este archivo (confirmado por
# grep) pero se reexporta igual por consistencia con el resto de la
# fachada.
from panel_arbol_ui import PanelArbol

class VentanaPrincipal(Gtk.Window):
    def __init__(self):
        super().__init__(title=_("CableDoc - Gestión de Cableado"))
        self.set_default_size(1024, 768)
        self.maximize()
        # Cargar icono de aplicación desde assets/CableDoc_BNC_*.png
        try:
            icon_path = os.path.join(ASSETS_DIR, "CableDoc_BNC_128x128.png")
            if os.path.exists(icon_path):
                icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
                self.set_icon(icon_pixbuf)
        except Exception:
            pass  # Continuar sin icono si falla
        self.connect("delete-event", Gtk.main_quit)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # ── Barra de menú ──
        menubar = Gtk.MenuBar()
        vbox.pack_start(menubar, False, False, 0)

        def menu(label, items):
            m = Gtk.Menu()
            mi = Gtk.MenuItem(label=label)
            mi.set_submenu(m)
            menubar.append(mi)
            for entry in items:
                lbl, cb = entry[0], entry[1]
                # tercer elemento opcional: (lbl, cb, habilitado) — usado
                # para dejar un ítem visible pero deshabilitado (ver
                # "editor clásico" de Alta rápida de conexiones más abajo).
                habilitado = entry[2] if len(entry) > 2 else True
                tooltip = entry[3] if len(entry) > 3 else None
                if lbl == "---":
                    m.append(Gtk.SeparatorMenuItem())
                else:
                    item = Gtk.MenuItem(label=lbl)
                    item.connect("activate", cb)
                    item.set_sensitive(habilitado)
                    if tooltip:
                        item.set_tooltip_text(tooltip)
                    m.append(item)

        menu(_("Equipos"), [
            (_("Equipos"),          self._abrir_equipos),
            (_("⚡ Alta Rápida…"),  self._alta_rapida_equipo),
            (_("📦 Catálogo de Equipos"), self._abrir_catalogo),
            (_("Frames"),           self._abrir_frames),
            (_("📦 Catálogo de Frames"),  self._abrir_catalogo_frame),
        ])
        menu(_("Cableado"), [
            (_("Cables"), self._abrir_cables),
            (_("Conexiones"), self._abrir_conexiones),
            ("---", None),
            (_("⚡ Alta rápida de conexiones…"), self._abrir_editor_conexiones),
        ])
        menu(_("Infraestructura"), [
            (_("Racks"), self._abrir_racks),
            (_("Posición en Racks"), self._abrir_posicion_racks),
            ("---", None),
            (_("Salas"), self._abrir_salas),
            (_("Rack por Sala"), self._abrir_rack_por_sala),
            (_("Equipos sueltos por Sala"), self._abrir_equipos_no_rack_sala),
            ("---", None),
            (_("🖼 Vista gráfica de rack…"), self._abrir_vista_rack),
        ])
        menu(_("Catálogos"), [
            (_("Marcas"), self._abrir_marcas),
            (_("Tipos de Equipo"), self._abrir_tipos_equipo),
            (_("Tipos de Conector"), self._abrir_tipos_conector),
            (_("Tipos de Cable"), self._abrir_tipos_cable),
            (_("Tipos de Ficha"), self._abrir_tipos_ficha),
            (_("Categorías de Problema"), self._abrir_categorias_problema),
            (_("Imágenes"), self._abrir_imagenes),
            ("---", None),
            (_("📋 Zonas sospechosas (bitácora)"), self._abrir_zonas_sospechosas),
            (_("🔗 Extensiones de cable"), self._abrir_extensiones_cable),
            ("---", None),
            (_("📡 Señales"), self._abrir_senales),
            (_("📡 Formatos de Señal"), self._abrir_formatos_senal),
            (_("📡 Reportes de Señal…"), self._abrir_reportes_senal),
        ])
        menu(_("Diagramas"), [
            (_("🖼 Imagen con conectores…"), self._abrir_imagen_conectores),
            (_("🌳 Árbol de conexiones…"),   self._abrir_arbol_conexiones),
            (_("🔌 Vista de patcheras…"),    self._abrir_patcheras),
            (_("🔌 Vista global de patcheras (todas)…"), self._abrir_patcheras_global),
            (_("🔗 Diagrama de conexiones…"), self._abrir_diagrama),
            ("---", None),
            (_("🗂 Diagramas personalizados…"), self._abrir_diagramas_personalizados),
            (_("🔮 Consola Cypher (GraphQLite)…"), self._abrir_cypher),
            ("---", None),
            (_("📡🔎 Buscador de señal…"), self._abrir_buscador_senal),
            (_("📡🔮 Calcular propagación de señal…"), self._abrir_propagacion_senal),
            (_("📡🧹 Borrar señales propagadas…"), self._abrir_limpiar_senales_propagadas),
        ])

        # ── Menú Idioma ──
        m_lang = Gtk.Menu()
        mi_lang = Gtk.MenuItem(label=_("Idioma"))
        mi_lang.set_submenu(m_lang)
        menubar.append(mi_lang)
        for codigo, nombre in IDIOMAS_DISPONIBLES.items():
            item_lang = Gtk.MenuItem(label=nombre)
            item_lang.connect("activate", self._cambiar_idioma, codigo)
            m_lang.append(item_lang)

        # ── Menú Ayuda ──
        menu(_("Ayuda"), [
            (_("Acerca de…"), self._abrir_acerca_de),
        ])

        # ── Área central con bienvenida ──
        center = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )

        logo = Gtk.Image()
        try:
            pixbuf_logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                ICONO_APP_PATH, 64, 64, True)
            logo.set_from_pixbuf(pixbuf_logo)
        except Exception:
            # Si no se encuentra el ícono, se deja el widget vacío en
            # lugar de fallar el arranque de la pantalla principal.
            pass
        titulo = Gtk.Label()
        titulo.set_markup(
            '<span font="24" weight="bold">CableDoc</span>'
        )
        subtitulo = Gtk.Label(
            label=_("Gestión de cableado e infraestructura de broadcasting")
        )
        subtitulo.get_style_context().add_class("dim-label")

        center.pack_start(logo, False, False, 0)
        center.pack_start(titulo, False, False, 0)
        center.pack_start(subtitulo, False, False, 0)

        # Accesos rápidos
        grid = Gtk.Grid(column_spacing=12, row_spacing=8,
                        halign=Gtk.Align.CENTER, margin_top=24)
        accesos = [
            (_("🖥️ Equipos"), self._abrir_equipos),
            (_("🔌 Patcheras"), self._abrir_patcheras),
            (_("🔗 Diagrama"), self._abrir_diagrama),
            (_("🔌 Cables"), self._abrir_cables),
            (_("🔗 Conexiones"), self._abrir_conexiones),
            (_("🗄️ Racks"), self._abrir_racks),
            (_("🖼 Vista Rack"), self._abrir_vista_rack),
            (_("📦 Frames"), self._abrir_frames),
            (_("🔮 Consola Cypher"), self._abrir_cypher),
        ]
        for i, (lbl, cb) in enumerate(accesos):
            btn = Gtk.Button(label=lbl)
            btn.set_size_request(150, 60)
            btn.connect("clicked", cb)
            grid.attach(btn, i % 3, i // 3, 1, 1)
        center.pack_start(grid, False, False, 0)

        # ── Panel de pendientes de cables ──
        sep_p = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_p.set_margin_top(20); sep_p.set_margin_bottom(8)
        center.pack_start(sep_p, False, False, 0)

        lbl_pend = Gtk.Label()
        lbl_pend.set_markup("<b>" + _("Trabajo pendiente — Cables") + "</b>")
        lbl_pend.set_margin_bottom(6)
        center.pack_start(lbl_pend, False, False, 0)

        self._panel_pendientes = Gtk.Grid(
            column_spacing=10, row_spacing=6,
            halign=Gtk.Align.CENTER,
        )
        center.pack_start(self._panel_pendientes, False, False, 0)
        self._actualizar_panel_pendientes()

        sep_eq = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_eq.set_margin_top(16); sep_eq.set_margin_bottom(8)
        center.pack_start(sep_eq, False, False, 0)

        lbl_pend_eq = Gtk.Label()
        lbl_pend_eq.set_markup("<b>" + _("Trabajo pendiente — Equipos") + "</b>")
        lbl_pend_eq.set_margin_bottom(6)
        center.pack_start(lbl_pend_eq, False, False, 0)

        self._panel_pendientes_eq = Gtk.Grid(
            column_spacing=10, row_spacing=6,
            halign=Gtk.Align.CENTER,
        )
        center.pack_start(self._panel_pendientes_eq, False, False, 0)
        self._actualizar_panel_pendientes_eq()

        sep_fr = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_fr.set_margin_top(16); sep_fr.set_margin_bottom(8)
        center.pack_start(sep_fr, False, False, 0)

        lbl_pend_fr = Gtk.Label()
        lbl_pend_fr.set_markup("<b>" + _("Trabajo pendiente — Frames") + "</b>")
        lbl_pend_fr.set_margin_bottom(6)
        center.pack_start(lbl_pend_fr, False, False, 0)

        self._panel_pendientes_fr = Gtk.Grid(
            column_spacing=10, row_spacing=6,
            halign=Gtk.Align.CENTER,
        )
        center.pack_start(self._panel_pendientes_fr, False, False, 0)
        self._actualizar_panel_pendientes_fr()

        # ── Riesgo de señal (plan_riesgo_senal_audio.md) ──
        sep_rs = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_rs.set_margin_top(16); sep_rs.set_margin_bottom(8)
        center.pack_start(sep_rs, False, False, 0)

        lbl_pend_rs = Gtk.Label()
        lbl_pend_rs.set_markup("<b>" + _("Trabajo pendiente — Riesgo de señal") + "</b>")
        lbl_pend_rs.set_margin_bottom(6)
        center.pack_start(lbl_pend_rs, False, False, 0)

        self._panel_pendientes_rs = Gtk.Grid(
            column_spacing=10, row_spacing=6,
            halign=Gtk.Align.CENTER,
        )
        center.pack_start(self._panel_pendientes_rs, False, False, 0)
        self._actualizar_panel_pendientes_rs()

        # ── Armar layout: árbol izquierda | contenido derecha ──
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        self._panel_arbol = PanelArbol(self)
        paned.pack1(self._panel_arbol, resize=False, shrink=False)
        paned.set_position(270)

        sw_center = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        sw_center.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_center.add(center)
        paned.pack2(sw_center, resize=True, shrink=True)

        vbox.pack_start(paned, True, True, 0)

        # ── Status bar ──
        self.statusbar = Gtk.Statusbar()
        vbox.pack_end(self.statusbar, False, False, 0)
        self.statusbar.push(0, _("Listo"))

        # Asegurar que las columnas de equipo existan
        Modelo.asegurar_columnas_equipo()
        Modelo.asegurar_tablas_catalogo()
        Modelo.asegurar_tablas_catalogo_frame()
        Modelo.asegurar_tablas_problemas()
        Modelo.asegurar_tablas_riesgo()
        Modelo.asegurar_tablas_regla_logica()
        # Fase 1 de plan_desarrollo_hardcodes_idioma.md: columnas de control
        # dedicadas (tipo_equipo.rol_senal ampliado, tipo_conector.direccion/
        # es_referencia_generada, conector.fila_patchera).
        Modelo.asegurar_columnas_control_idioma()
        # plan_riesgo_senal_audio.md: columnas de los 3 ejes de riesgo de
        # calidad de señal (atenuación / ancho de banda / mismatch de
        # formato), separado del impacto lógico de asegurar_tablas_riesgo.
        Modelo.asegurar_columnas_riesgo_senal()

        self.show_all()

    def _actualizar_panel_pendientes(self):
        """Pobla el panel de pendientes con las métricas actuales de cables."""
        g = self._panel_pendientes
        # Limpiar
        for ch in g.get_children():
            g.remove(ch)

        try:
            p = Modelo.devolver_pendientes_cables()
        except Exception:
            return

        items = [
            (_("⚡ Temporales"),    p["temporales"],   "#806000", self._abrir_cables),
            (_("🔀 En revisión"),   p["en_revision"],  "#4a2d8a", self._abrir_cables),
            (_("1️⃣ 1 extremo"),    p["un_extremo"],   "#7a3800", self._abrir_cables),
            (_("❓ Sin conexión"), p["sin_conexion"],  "#7a1a1a", self._abrir_cables),
        ]
        for col, (titulo, valor, color, cb) in enumerate(items):
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vb.set_margin_start(12); vb.set_margin_end(12)
            vb.set_margin_top(8);   vb.set_margin_bottom(8)

            lbl_n = Gtk.Label()
            lbl_n.set_markup(f"<span size='xx-large' weight='bold' foreground='{color}'>{valor}</span>")
            lbl_t = Gtk.Label(label=titulo)
            lbl_t.get_style_context().add_class("dim-label")

            btn_ir = Gtk.Button(label=_("ver →"))
            btn_ir.set_relief(Gtk.ReliefStyle.NONE)
            btn_ir.connect("clicked", lambda b, c=cb: c())

            vb.pack_start(lbl_n, False, False, 0)
            vb.pack_start(lbl_t, False, False, 0)
            vb.pack_start(btn_ir, False, False, 0)
            frame.add(vb)
            g.attach(frame, col, 0, 1, 1)

        g.show_all()

    def _actualizar_panel_pendientes_eq(self):
        """Pobla el panel de pendientes con las métricas de equipos incompletos."""
        g = self._panel_pendientes_eq
        for ch in g.get_children():
            g.remove(ch)
        try:
            p = Modelo.devolver_pendientes_equipos()
        except Exception:
            return
        items = [
            (_("🔌 Sin conectores"),        p["sin_conectores"],    "#7a1a1a",
             lambda: self._abrir_ventana(EquiposListado, filtro_pendiente="sin_conectores")),
            (_("🖼 Sin imagen"),             p["sin_imagen"],        "#7a3800",
             lambda: self._abrir_ventana(EquiposListado, filtro_pendiente="sin_imagen")),
            (_("📍 Sin imagen c/ conect."),  p["sin_img_conectores"],"#4a4a00",
             lambda: self._abrir_ventana(EquiposListado, filtro_pendiente="sin_img_conectores")),
        ]
        for col, (titulo, valor, color, cb) in enumerate(items):
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vb.set_margin_start(12); vb.set_margin_end(12)
            vb.set_margin_top(8);   vb.set_margin_bottom(8)
            lbl_n = Gtk.Label()
            lbl_n.set_markup(f"<span size='xx-large' weight='bold' foreground='{color}'>{valor}</span>")
            lbl_t = Gtk.Label(label=titulo)
            lbl_t.get_style_context().add_class("dim-label")
            btn_ir = Gtk.Button(label=_("ver →"))
            btn_ir.set_relief(Gtk.ReliefStyle.NONE)
            btn_ir.connect("clicked", lambda b, c=cb: c())
            vb.pack_start(lbl_n, False, False, 0)
            vb.pack_start(lbl_t, False, False, 0)
            vb.pack_start(btn_ir, False, False, 0)
            frame.add(vb)
            g.attach(frame, col, 0, 1, 1)
        g.show_all()

    def _actualizar_panel_pendientes_fr(self):
        """Pobla el panel de pendientes con las métricas de frames incompletos."""
        g = self._panel_pendientes_fr
        for ch in g.get_children():
            g.remove(ch)
        try:
            p = Modelo.devolver_pendientes_frames()
        except Exception:
            return
        items = [
            (_("📦 Sin slots"),          p["sin_slots"],  "#7a1a1a",
             lambda: self._abrir_ventana(FramesListado, filtro_pendiente="sin_slots")),
            ("🖼 Sin imagen",         p["sin_imagen"], "#7a3800",
             lambda: self._abrir_ventana(FramesListado, filtro_pendiente="sin_imagen")),
            (_("📍 Sin slot en imagen"), p["sin_rect"],   "#4a4a00",
             lambda: self._abrir_ventana(FramesListado, filtro_pendiente="sin_rect")),
        ]
        for col, (titulo, valor, color, cb) in enumerate(items):
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vb.set_margin_start(12); vb.set_margin_end(12)
            vb.set_margin_top(8);   vb.set_margin_bottom(8)
            lbl_n = Gtk.Label()
            lbl_n.set_markup(f"<span size='xx-large' weight='bold' foreground='{color}'>{valor}</span>")
            lbl_t = Gtk.Label(label=titulo)
            lbl_t.get_style_context().add_class("dim-label")
            btn_ir = Gtk.Button(label=_("ver →"))
            btn_ir.set_relief(Gtk.ReliefStyle.NONE)
            btn_ir.connect("clicked", lambda b, c=cb: c())
            vb.pack_start(lbl_n, False, False, 0)
            vb.pack_start(lbl_t, False, False, 0)
            vb.pack_start(btn_ir, False, False, 0)
            frame.add(vb)
            g.attach(frame, col, 0, 1, 1)
        g.show_all()

    def _actualizar_panel_pendientes_rs(self):
        """Pobla el panel de pendientes con las métricas de riesgo de señal
        (plan_riesgo_senal_audio.md) — 3 ejes separados, no fusionados en
        un score único (misma razón que signal_risk.py: cada uno se
        arregla distinto)."""
        g = self._panel_pendientes_rs
        for ch in g.get_children():
            g.remove(ch)
        try:
            from signal_risk import SignalRiskAnalyzer
            analyzer = SignalRiskAnalyzer(DB_PATH)
            todo = analyzer.calcular_todo()
            n_atenuacion = sum(1 for v in todo["atenuacion"].values() if v.riesgo)
            n_ancho_banda = sum(1 for v in todo["ancho_banda"].values() if v.riesgo)
            n_formato = sum(1 for v in todo["formato"].values() if v.riesgo)
        except Exception:
            return
        items = [
            (_("📉 Atenuación"),      n_atenuacion,  "#7a1a1a", "ATENUACION"),
            (_("🚧 Cuello de botella"), n_ancho_banda, "#7a3800", "ANCHO_BANDA"),
            (_("⚡ Mismatch de formato"), n_formato,     "#4a2d8a", "FORMATO"),
        ]
        for col, (titulo, valor, color, eje) in enumerate(items):
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vb.set_margin_start(12); vb.set_margin_end(12)
            vb.set_margin_top(8);   vb.set_margin_bottom(8)
            lbl_n = Gtk.Label()
            lbl_n.set_markup(f"<span size='xx-large' weight='bold' foreground='{color}'>{valor}</span>")
            lbl_t = Gtk.Label(label=titulo)
            lbl_t.get_style_context().add_class("dim-label")
            btn_ir = Gtk.Button(label=_("ver →"))
            btn_ir.set_relief(Gtk.ReliefStyle.NONE)
            btn_ir.connect("clicked", lambda b, e=eje: self._abrir_riesgo_senal(e))
            vb.pack_start(lbl_n, False, False, 0)
            vb.pack_start(lbl_t, False, False, 0)
            vb.pack_start(btn_ir, False, False, 0)
            frame.add(vb)
            g.attach(frame, col, 0, 1, 1)
        g.show_all()

    def _abrir_riesgo_senal(self, filtro_eje=None):
        dlg = RiesgoSenalListado(parent=self, filtro_eje=filtro_eje)
        dlg.run()
        dlg.destroy()
        self._actualizar_panel_pendientes_rs()

    # ── Métodos para abrir ventanas ──
    def _abrir_ventana(self, cls, *args, **kwargs):
        dlg = cls(*args, parent=self, **kwargs)
        dlg.run()
        dlg.destroy()

    def _abrir_equipos(self, *a):
        self._abrir_ventana(EquiposListado)

    def _alta_rapida_equipo(self, *a):
        dlg = _DialogoAltaRapidaEquipo(parent=self)
        dlg.run_and_destroy()

    def _abrir_catalogo(self, *a):
        self._abrir_ventana(CatalogoEquiposListado)

    def _abrir_catalogo_frame(self, *a):
        self._abrir_ventana(CatalogoFramesListado)

    def _abrir_cables(self, *a):
        self._abrir_ventana(CablesListado)

    def _abrir_conexiones(self, *a):
        self._abrir_ventana(ConexionesListado)

    def _abrir_racks(self, *a):
        self._abrir_ventana(RacksListado)

    def _abrir_frames(self, *a):
        self._abrir_ventana(FramesListado)

    def _abrir_posicion_racks(self, *a):
        self._abrir_ventana(PosicionEnRackListado)

    def _abrir_marcas(self, *a):
        self._abrir_ventana(MarcasListado)

    def _abrir_tipos_equipo(self, *a):
        self._abrir_ventana(TiposEquipoListado)

    def _abrir_tipos_conector(self, *a):
        self._abrir_ventana(TiposConectorListado)

    def _abrir_tipos_cable(self, *a):
        self._abrir_ventana(TiposCableListado)

    def _abrir_tipos_ficha(self, *a):
        self._abrir_ventana(TiposFichaListado)

    def _abrir_categorias_problema(self, *a):
        self._abrir_ventana(CategoriasProblemaListado)

    def _abrir_senales(self, *a):
        self._abrir_ventana(SenalesListado)

    def _abrir_formatos_senal(self, *a):
        self._abrir_ventana(TiposFormatoSenalListado)

    def _abrir_reportes_senal(self, *a):
        abrir_reportes_senal(parent=self)

    def _abrir_zonas_sospechosas(self, *a):
        """Listado general de zonas sospechosas (ver plan_bitacora_
        incidentes_riesgo_analogico.md) — permite crear/editar/eliminar
        zonas y entrar a su bitácora de incidentes sin pasar por un
        equipo o cable puntual."""
        from bitacora_ui import abrir_zonas_sospechosas
        abrir_zonas_sospechosas(parent=self)

    def _abrir_extensiones_cable(self, *a):
        """Catálogo general de extensiones de cable (ver
        plan_desarrollo_extension_cable.md) — permite crear/editar/
        eliminar extensiones (empalmes ficha-contra-ficha sin equipo de
        por medio) sin pasar por la ficha de un cable puntual."""
        from extension_cable_ui import abrir_extensiones_cable
        abrir_extensiones_cable(parent=self)

    def _abrir_buscador_senal(self, *a):
        abrir_buscador_senal(parent=self)

    def _abrir_propagacion_senal(self, *a):
        abrir_propagacion_senal(parent=self)

    def _abrir_limpiar_senales_propagadas(self, *a):
        abrir_limpiar_senales_propagadas(parent=self)

    def _abrir_imagenes(self, *a):
        self._abrir_ventana(ImagenesListado)

    def _abrir_imagen_conectores(self, *a):
        """Pide seleccionar un equipo y abre la vista de imagen con conectores."""
        selector = EquiposListado(parent=self, modo_seleccion=True)
        if selector.run() == Gtk.ResponseType.OK:
            id_eq = selector.resultado_id
            selector.destroy()
            abrir_imagen_conectores(id_eq, parent=self)
        else:
            selector.destroy()

    def _abrir_arbol_conexiones(self, *a):
        """Abre el árbol de conexiones (el usuario elige equipo dentro)."""
        abrir_arbol_conexiones(parent=self)

    def _abrir_patcheras(self, *a):
        """Pide seleccionar equipo y abre la vista de patcheras."""
        sel = EquiposListado(parent=self, modo_seleccion=True)
        if sel.run() == Gtk.ResponseType.OK:
            id_eq  = sel.resultado_id
            nombre = sel.resultado_nombre
            sel.destroy()
            abrir_patcheras(id_eq, nombre_equipo=nombre, parent=self)
        else:
            sel.destroy()

    def _abrir_patcheras_global(self, *a):
        """Abre la vista de patcheras en modo global (todas las patcheras
        del sistema), sin pedir seleccionar un equipo primero."""
        abrir_patcheras(id_equipo=None, parent=self)

    def _abrir_vista_rack(self, *a):
        """Abre la vista gráfica de rack (el usuario elige rack dentro)."""
        abrir_vista_rack(parent=self)

    def _abrir_editor_conexiones(self, *a):
        """'Alta rápida de conexiones': reutiliza la pantalla del Diagrama
        de conexiones (DiagramaConexiones, diagrama_conexiones_ui.py) en
        modo iniciar_vacio, con el panel lateral de búsqueda/arrastre de
        equipos activado. El editor de nodos custom legacy
        (EditorConexiones, "modo clásico") se eliminó del proyecto en la
        Entrega 6 del refactor — estaba deshabilitado en el menú desde que
        esta función pasó a reutilizar DiagramaConexiones."""
        abrir_diagrama_conexiones(id_equipo=None, parent=self, iniciar_vacio=True)

    def _abrir_salas(self, *a):
        SalasListado(parent=self).run_and_destroy()

    def _abrir_rack_por_sala(self, *a):
        RackPorSalaListado(parent=self).run_and_destroy()

    def _abrir_equipos_no_rack_sala(self, *a):
        EquiposNoRackSalaListado(parent=self).run_and_destroy()

    def _abrir_diagrama(self, *a):
        abrir_diagrama_conexiones(parent=self)

    def _abrir_diagramas_personalizados(self, *a):
        self._abrir_ventana(DiagramasGuardadosListado)

    def _cambiar_idioma(self, widget, codigo):
        from i18n import set_lang, IDIOMAS_DISPONIBLES
        set_lang(codigo)
        
        # Mostrar mensaje de confirmación antes de reiniciar
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("Idioma cambiado. La aplicación se reiniciará para aplicar los cambios.")
        )
        dlg.run()
        dlg.destroy()
        
        # Cerrar la ventana principal
        self.destroy()
        
        # Reiniciar la aplicación para aplicar el cambio de idioma
        import subprocess
        import sys
        import os
        subprocess.Popen([sys.executable] + sys.argv, 
                        cwd=os.path.dirname(os.path.abspath(__file__)))
        Gtk.main_quit()

    def _abrir_cypher(self, *a):
        dlg = CypherConsole(self, DB_PATH)
        dlg.run()
        dlg.destroy()

    def _abrir_acerca_de(self, *a):
        abrir_acerca_de(version=APP_VERSION, parent=self)


# ─── Helpers para construcción de formularios ─────────────────────────────────

def _escribir_json_comprimido(ruta, nombre_interno, data):
    """Escribe `data` (dict serializable a JSON) comprimido en un .zip que
    contiene un único archivo `nombre_interno` con el JSON adentro. Usado
    por la exportación de catálogos (equipos/frames): las imágenes/manuales/
    picones embebidos en base64 dentro del JSON comprimen muy bien, así que
    el .zip resultante suele ser bastante más chico que el .json plano."""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(nombre_interno, payload)


def _leer_json_generico(ruta):
    """Lee un archivo de catálogo exportado y devuelve el dict ya parseado.
    Acepta tanto el formato actual (.zip con un único .json adentro) como
    el formato viejo (.json plano sin comprimir), para poder seguir
    importando exportaciones hechas por versiones anteriores del programa."""
    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta, "r") as zf:
            nombres = [n for n in zf.namelist() if n.lower().endswith(".json")]
            if not nombres:
                raise ValueError("El archivo .zip no contiene ningún .json adentro.")
            with zf.open(nombres[0]) as fh:
                return json.load(fh)
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _sel_imagen_desde_abm(parent):
    """Abre ImagenesListado en modo selección y retorna (id_imagen, path) o None."""
    dlg = ImagenesListado(parent=parent, modo_seleccion=True)
    resultado = None
    if dlg.run() == Gtk.ResponseType.OK:
        fila = dlg._fila()
        if fila:
            resultado = (str(fila[0]), s(fila[1]))
    dlg.destroy()
    return resultado


# ─── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import modelo as _modelo
    from modelo import DB_PATH, SCHEMA_SQL_PATH
    # Crea database/, imagen/, manuales/, picon/ si faltan, y crea
    # database/db.db desde schema_db.sql si todavía no existe (instalación
    # nueva). Esto ya se ejecuta al importar modelo.py, pero se vuelve a
    # llamar acá explícitamente para dejar clara la intención en el punto
    # de entrada y por si en el futuro se llama a este bloque sin haber
    # importado el módulo antes.
    _modelo.asegurar_directorios()
    _modelo.asegurar_base_datos()

    if not os.path.exists(DB_PATH):
        dlg = Gtk.MessageDialog(
            flags=0, message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=f"No se encontró el archivo de base de datos:\n{DB_PATH}\n\n"
                 f"Tampoco se encontró {SCHEMA_SQL_PATH} para crearla "
                 f"automáticamente.\n\n"
                 f"Copiá db.db o schema_db.sql al directorio de la aplicación."
        )
        dlg.run(); dlg.destroy()
        sys.exit(1)

    win = VentanaPrincipal()
    Gtk.main()
