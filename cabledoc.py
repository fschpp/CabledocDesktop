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
APP_VERSION = "1.20260904050000"

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


# ─── Marcas ───────────────────────────────────────────────────────────────────

class MarcasListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Marcas"), [_("ID"), _("Marca")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_marcas())

    def nuevo(self):
        dlg = DialogoNombre(_("Nueva Marca"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_marca(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_marca(id_)
        if not rows: return
        dlg = DialogoNombre(_("Editar Marca"), valor=s(rows[0][1]), parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_marca(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_marca(id_)


# ─── Tipos de equipo ──────────────────────────────────────────────────────────

class _DialogoTipoEquipo(Gtk.Dialog):
    """Editor de tipo_equipo: nombre + rol frente a la señal (ver
    plan_entidad_senal.md). Reemplaza a DialogoNombre solo en este listado
    porque necesita el campo extra rol_senal, que define cómo se comporta
    ese tipo de equipo cuando el motor de propagación de señal recorra el
    grafo (Fase 3, todavía no implementada)."""

    ROLES = [
        ("DISTRIBUIDOR", _("Distribuidor (repite la señal en sus salidas)")),
        ("FUENTE",       _("Fuente (genera la señal)")),
        ("ENRUTADOR",    _("Enrutador (según ruteo de matriz)")),
        ("PROCESADOR",   _("Procesador (combina/transforma → señal nueva)")),
        ("CONSUMIDOR",   _("Consumidor (no tiene salidas de señal)")),
        ("PATCHERA",     _("Patchera (bypass físico A/B, no usa ruteo de matriz)")),
        ("CONVERSOR_BALANCE", _("Conversor de balance (DI box, transformador — punto de conversión legítimo)")),
        ("SUMADOR_CANAL",     _("Sumador/divisor de canal (mono↔estéreo — punto de conversión legítimo)")),
    ]

    def __init__(self, titulo, nombre="", rol_senal="DISTRIBUIDOR", parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(440, 160)

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = Gtk.Entry(text=nombre, activates_default=True,
                                  hexpand=True)
        g.attach(self.e_nombre, 1, 0, 2, 1)

        _lbl_entry(g, _("Rol frente a la señal:"), 1)
        self.c_rol = Gtk.ComboBoxText()
        for clave, etiqueta in self.ROLES:
            self.c_rol.append(clave, etiqueta)
        self.c_rol.set_active_id(rol_senal or "DISTRIBUIDOR")
        self.c_rol.set_hexpand(True)
        g.attach(self.c_rol, 1, 1, 2, 1)

        self.get_content_area().add(g)
        self.show_all()

    @property
    def nombre(self):
        return self.e_nombre.get_text().strip()

    @property
    def rol_senal(self):
        return self.c_rol.get_active_id() or "DISTRIBUIDOR"


class TiposEquipoListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Tipos de Equipo"),
                         [_("ID"), _("Tipo"), _("Rol señal")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        # devolver_todos_los_tipos() no trae rol_senal (columna de la
        # entidad señal, agregada después); se completa acá por fila.
        filas = Modelo.devolver_todos_los_tipos()
        filas_con_rol = [
            (id_, nombre, Modelo.devolver_rol_senal_tipo_equipo(id_))
            for id_, nombre in filas
        ]
        self._poblar(filas_con_rol)

    def nuevo(self):
        dlg = _DialogoTipoEquipo(_("Nuevo Tipo de Equipo"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.nombre:
            Modelo.alta_tipo(dlg.nombre, rol_senal=dlg.rol_senal)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_tipo(id_)
        if not rows: return
        rol_actual = Modelo.devolver_rol_senal_tipo_equipo(id_)
        dlg = _DialogoTipoEquipo(_("Editar Tipo"), nombre=s(rows[0][1]),
                                 rol_senal=rol_actual, parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_tipo(id_, dlg.nombre)
            Modelo.establecer_rol_senal_tipo_equipo(id_, dlg.rol_senal)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_tipo(id_)


# ─── Tipos de conector ────────────────────────────────────────────────────────

class TiposConectorListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Tipos de Conector"), [_("ID"), _("Nombre")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_tipos_conectores())

    def nuevo(self):
        dlg = DialogoNombre(_("Nuevo Tipo de Conector"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.agregar_tipo_conector(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_tipo_conector(id_)
        if not rows: return
        dlg = DialogoNombre(_("Editar Tipo Conector"), valor=s(rows[0][1]), parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificar_tipo_conector(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_tipo_conector(id_)


# ─── Riesgo de señal (plan_riesgo_senal_audio.md) ──────────────────────────────

class RiesgoSenalListado(VentanaListado):
    """Listado de solo-lectura de cables con riesgo de señal activo en
    cualquiera de los 3 ejes de signal_risk.py. Doble click abre el cable
    (mismo editor que CablesListado) para poder corregirlo o cargar el
    dato de catálogo que falta."""

    ETIQUETAS_EJE = {
        "ATENUACION": _("Atenuación"),
        "ANCHO_BANDA": _("Cuello de botella"),
        "ELECTRICO": _("Eléctrico"),
        "BALANCE": _("Balance"),
        "CANAL": _("Canal"),
        "FORMATO": _("Formato"),
    }

    def __init__(self, parent=None, modo_seleccion=False, filtro_eje=None):
        self.filtro_eje = filtro_eje
        titulo = _("Riesgo de señal")
        if filtro_eje == "ATENUACION":
            titulo = _("Riesgo de señal — Atenuación")
        elif filtro_eje == "ANCHO_BANDA":
            titulo = _("Riesgo de señal — Cuellos de botella")
        elif filtro_eje == "FORMATO":
            titulo = _("Riesgo de señal — Mismatch de formato")
        super().__init__(titulo, [_("ID"), _("Cable"), _("Eje(s)"), _("Detalle")],
                         parent=parent, modo_seleccion=modo_seleccion)
        # Sin CRUD propio: este listado no da de alta/borra cables.
        self.btn_agregar.set_visible(False)
        self.btn_eliminar.set_visible(False)
        self.btn_editar.set_label("✏️ " + _("Abrir cable"))
        self.cargar_datos()

    def cargar_datos(self):
        from signal_risk import SignalRiskAnalyzer
        analyzer = SignalRiskAnalyzer(DB_PATH)
        resumen = analyzer.resumen_por_cable()

        es_formato = {"ELECTRICO", "BALANCE", "CANAL"}
        filas = []
        for id_cable, activos in resumen.items():
            if self.filtro_eje == "FORMATO":
                activos = [(e, d) for e, d in activos if e in es_formato]
            elif self.filtro_eje is not None:
                activos = [(e, d) for e, d in activos if e == self.filtro_eje]
            if not activos:
                continue
            fila_cable = Modelo._query(
                "SELECT codigo FROM cable WHERE id_cable=?", (id_cable,))
            codigo = fila_cable[0][0] if fila_cable else f"#{id_cable}"
            ejes_txt = ", ".join(self.ETIQUETAS_EJE.get(e, e) for e, _d in activos)
            detalle_txt = " | ".join(d for _e, d in activos)
            filas.append([str(id_cable), s(codigo), ejes_txt, detalle_txt])

        filas.sort(key=lambda f: f[1])
        self._poblar(filas)

    def editar(self, id_):
        dlg = _DialogoCable(id_cable=int(id_), parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        pass  # sin CRUD propio, ver __init__


# ─── Tipos de cable ───────────────────────────────────────────────────────────

class _DialogoTipoCable(Gtk.Dialog):
    """Editor de tipo de cable, con nombre + los datos de riesgo de señal
    de plan_riesgo_senal_audio.md (naturaleza de la señal, longitud
    máxima recomendada por tipo de balance, ancho de banda nominal).
    Todos los campos de riesgo son opcionales: vacío = sin cargar, el
    analizador (signal_risk.py) simplemente no evalúa ese cable."""

    NATURALEZAS = ["", "ANALOGICA", "DIGITAL", "HIBRIDA", "DATOS"]

    def __init__(self, titulo, nombre="", id_tipo_cable=None, parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(420, 260)
        self._id_tipo_cable = id_tipo_cable

        g = _grid()
        fila = 0
        _lbl_entry(g, _("Nombre:"), fila)
        self.e_nombre = Gtk.Entry(text=nombre, activates_default=True, hexpand=True)
        g.attach(self.e_nombre, 1, fila, 2, 1)
        fila += 1

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        g.attach(sep, 0, fila, 3, 1)
        fila += 1
        lbl_sec = Gtk.Label(xalign=0)
        lbl_sec.set_markup(f"<b>{_('Riesgo de señal')}</b>")
        g.attach(lbl_sec, 0, fila, 3, 1)
        fila += 1

        _lbl_entry(g, _("Naturaleza de la señal:"), fila)
        self.c_naturaleza = Gtk.ComboBoxText()
        for n in self.NATURALEZAS:
            self.c_naturaleza.append_text(n if n else _("(sin clasificar)"))
        g.attach(self.c_naturaleza, 1, fila, 2, 1)
        fila += 1

        _lbl_entry(g, _("Long. máx. recomendada — balanceado (m):"), fila)
        self.e_long_bal = _entry(g, fila)
        fila += 1

        _lbl_entry(g, _("Long. máx. recomendada — desbalanceado (m):"), fila)
        self.e_long_desbal = _entry(g, fila)
        fila += 1

        _lbl_entry(g, _("Ancho de banda nominal (MHz):"), fila)
        self.e_ancho_banda = _entry(g, fila)
        fila += 1

        self.get_content_area().pack_start(g, True, True, 0)

        # Cargar valores de riesgo existentes
        if id_tipo_cable:
            riesgo = Modelo.devolver_riesgo_tipo_cable(id_tipo_cable)
            if riesgo:
                naturaleza, long_bal, long_desbal, ancho = riesgo
                idx = self.NATURALEZAS.index(naturaleza) if naturaleza in self.NATURALEZAS else 0
                self.c_naturaleza.set_active(idx)
                self.e_long_bal.set_text(_fmt_float_opt(long_bal))
                self.e_long_desbal.set_text(_fmt_float_opt(long_desbal))
                self.e_ancho_banda.set_text(_fmt_float_opt(ancho))
            else:
                self.c_naturaleza.set_active(0)
            _pack_ultima_edicion(self, "tipo_cable", "id_tipo_cable", id_tipo_cable)
        else:
            self.c_naturaleza.set_active(0)

        self.show_all()

    @property
    def valor_nombre(self):
        return self.e_nombre.get_text().strip()

    def guardar_riesgo(self, id_tipo_cable):
        idx = self.c_naturaleza.get_active()
        naturaleza = self.NATURALEZAS[idx] if idx >= 0 else ""
        Modelo.establecer_riesgo_tipo_cable(
            id_tipo_cable,
            naturaleza or None,
            _parse_float_opt(self.e_long_bal.get_text()),
            _parse_float_opt(self.e_long_desbal.get_text()),
            _parse_float_opt(self.e_ancho_banda.get_text()),
        )


class TiposCableListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Tipos de Cable"), [_("ID"), _("Tipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_tipos_cable())

    def nuevo(self):
        dlg = _DialogoTipoCable(_("Nuevo Tipo de Cable"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor_nombre:
            nuevo_id = Modelo.alta_tipo_cable_retorna_id(dlg.valor_nombre)
            dlg.guardar_riesgo(nuevo_id)
        dlg.destroy()
        self.cargar_datos()

    def editar(self, id_):
        rows = Modelo.devolver_tipo_cable(id_)
        if not rows: return
        dlg = _DialogoTipoCable(_("Editar Tipo Cable"), nombre=s(rows[0][1]),
                                 id_tipo_cable=id_, parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_tipo_cable(id_, dlg.valor_nombre)
            dlg.guardar_riesgo(id_)
        dlg.destroy()
        self.cargar_datos()

    def eliminar(self, id_):
        Modelo.eliminar_tipo_cable(id_)


# ─── Tipos de ficha ───────────────────────────────────────────────────────────

class _DialogoTipoFicha(Gtk.Dialog):
    """Editor de tipo de ficha, con nombre + los datos de riesgo de señal
    de plan_riesgo_senal_audio.md (n_conductores, modo de balance/canal
    por defecto, ancho de banda). Estos valores son el default que se
    resuelve en cada conector real vía COALESCE(conector.modo_balance,
    tipo_ficha.modo_balance_default) — ver conector.id_tipo_ficha en
    _DialogoConector."""

    MODOS_BALANCE = ["", "BALANCEADO", "DESBALANCEADO", "NA"]
    MODOS_CANAL = ["", "MONO", "ESTEREO", "NA"]

    def __init__(self, titulo, nombre="", id_tipo_ficha=None, parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(420, 280)

        g = _grid()
        fila = 0
        _lbl_entry(g, _("Nombre:"), fila)
        self.e_nombre = Gtk.Entry(text=nombre, activates_default=True, hexpand=True)
        g.attach(self.e_nombre, 1, fila, 2, 1)
        fila += 1

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        g.attach(sep, 0, fila, 3, 1)
        fila += 1
        lbl_sec = Gtk.Label(xalign=0)
        lbl_sec.set_markup(f"<b>{_('Riesgo de señal — formato por defecto')}</b>")
        g.attach(lbl_sec, 0, fila, 3, 1)
        fila += 1

        _lbl_entry(g, _("Cantidad de conductores:"), fila)
        self.e_n_conductores = _entry(g, fila)
        fila += 1

        _lbl_entry(g, _("Balance por defecto:"), fila)
        self.c_balance = Gtk.ComboBoxText()
        for m in self.MODOS_BALANCE:
            self.c_balance.append_text(m if m else _("(sin definir)"))
        g.attach(self.c_balance, 1, fila, 2, 1)
        fila += 1

        _lbl_entry(g, _("Canal por defecto:"), fila)
        self.c_canal = Gtk.ComboBoxText()
        for m in self.MODOS_CANAL:
            self.c_canal.append_text(m if m else _("(sin definir)"))
        g.attach(self.c_canal, 1, fila, 2, 1)
        fila += 1

        _lbl_entry(g, _("Ancho de banda (MHz):"), fila)
        self.e_ancho_banda = _entry(g, fila)
        fila += 1

        nota = Gtk.Label(xalign=0, wrap=True)
        nota.set_markup(
            f"<small><i>{_('Para fichas físicamente ambiguas (ej. TRS, que puede ser estéreo desbalanceado o mono balanceado), estos valores son sólo el default: cada conector real puede tener su propio override en su ficha (ficha de equipo).')}</i></small>")
        g.attach(nota, 0, fila, 3, 1)
        fila += 1

        self.get_content_area().pack_start(g, True, True, 0)

        if id_tipo_ficha:
            riesgo = Modelo.devolver_riesgo_tipo_ficha(id_tipo_ficha)
            if riesgo:
                n_cond, mbal, mcan, ancho = riesgo
                self.e_n_conductores.set_text(str(n_cond) if n_cond is not None else "")
                self.c_balance.set_active(self.MODOS_BALANCE.index(mbal) if mbal in self.MODOS_BALANCE else 0)
                self.c_canal.set_active(self.MODOS_CANAL.index(mcan) if mcan in self.MODOS_CANAL else 0)
                self.e_ancho_banda.set_text(_fmt_float_opt(ancho))
            else:
                self.c_balance.set_active(0)
                self.c_canal.set_active(0)
            _pack_ultima_edicion(self, "tipo_ficha", "id_tipo_ficha", id_tipo_ficha)
        else:
            self.c_balance.set_active(0)
            self.c_canal.set_active(0)

        self.show_all()

    @property
    def valor_nombre(self):
        return self.e_nombre.get_text().strip()

    def guardar_riesgo(self, id_tipo_ficha):
        idx_bal = self.c_balance.get_active()
        idx_can = self.c_canal.get_active()
        n_cond_txt = self.e_n_conductores.get_text().strip()
        n_cond = int(n_cond_txt) if n_cond_txt.isdigit() else None
        Modelo.establecer_riesgo_tipo_ficha(
            id_tipo_ficha,
            n_cond,
            self.MODOS_BALANCE[idx_bal] if idx_bal >= 0 else None,
            self.MODOS_CANAL[idx_can] if idx_can >= 0 else None,
            _parse_float_opt(self.e_ancho_banda.get_text()),
        )


class TiposFichaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Tipos de Ficha"), [_("ID"), _("Tipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_tipos_ficha())

    def nuevo(self):
        dlg = _DialogoTipoFicha(_("Nuevo Tipo de Ficha"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor_nombre:
            nuevo_id = Modelo.alta_tipo_ficha_retorna_id(dlg.valor_nombre)
            dlg.guardar_riesgo(nuevo_id)
        dlg.destroy()
        self.cargar_datos()

    def editar(self, id_):
        rows = Modelo.devolver_tipo_ficha(id_)
        if not rows: return
        dlg = _DialogoTipoFicha(_("Editar Tipo Ficha"), nombre=s(rows[0][1]),
                                 id_tipo_ficha=id_, parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_tipo_ficha(id_, dlg.valor_nombre)
            dlg.guardar_riesgo(id_)
        dlg.destroy()
        self.cargar_datos()

    def eliminar(self, id_):
        Modelo.eliminar_tipo_ficha(id_)


# ─── Categorías de problema (catálogo) ─────────────────────────────────────────

class CategoriasProblemaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Categoría de Problema"), [_("ID"), _("Categoría")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_categorias_problema())

    def nuevo(self):
        dlg = DialogoNombre(_("Nueva Categoría de Problema"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_categoria_problema(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_categoria_problema(id_)
        if not rows: return
        dlg = DialogoNombre(_("Editar Categoría de Problema"), valor=s(rows[0][1]), parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_categoria_problema(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_categoria_problema(id_)


# ─── Problemas de un equipo ─────────────────────────────────────────────────────

class ProblemasEquipoListado(VentanaListado):
    def __init__(self, id_equipo, parent=None, modo_seleccion=False):
        super().__init__(_("Problemas del Equipo"),
                         [_("ID"), _("Fecha"), _("Categoría"), _("Gravedad"), _("Descripción"),
                          _("Resuelto")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.id_equipo = id_equipo
        self.cargar_datos()

    def cargar_datos(self):
        filas = Modelo.devolver_problemas_de_equipo(self.id_equipo)
        # última columna viene como 0/1 -> texto legible
        filas_fmt = [list(f[:-1]) + [_("Sí") if f[-1] else _("No")] for f in filas]
        self._poblar(filas_fmt)

    def nuevo(self):
        dlg = _DialogoProblema(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoProblema(id_problema=id_, id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_problema(id_)


class _DialogoProblema(Gtk.Dialog):
    def __init__(self, id_problema=None, id_equipo=None, parent=None):
        titulo = _("Editar Problema") if id_problema else _("Nuevo Problema")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(440, 380)
        self.id_problema = id_problema
        self.id_equipo = id_equipo
        self.id_categoria = ""

        g = _grid()
        _lbl_entry(g, _("Categoría:"), 0)
        self.c_categoria = _searchable_combo(
            g, 0, Modelo.devolver_todas_las_categorias_problema(),
            "…", self._sel_categoria_dropdown)
        _lbl_entry(g, _("Gravedad (1-5):"), 1)
        self.sp_gravedad = Gtk.SpinButton()
        self.sp_gravedad.set_adjustment(
            Gtk.Adjustment(value=3, lower=1, upper=5, step_increment=1))
        self.sp_gravedad.set_numeric(True)
        g.attach(self.sp_gravedad, 1, 1, 2, 1)
        _lbl_entry(g, _("Fecha:"), 2)
        self.e_fecha = _entry(g, 2)
        self.e_fecha.set_placeholder_text("AAAA-MM-DD")

        self.chk_afecta_categoria = Gtk.CheckButton(
            label=_("Afecta a todos los equipos de este modelo (defecto de lote/diseño)"))
        self.chk_afecta_categoria.set_tooltip_text(
            _("Marcar cuando el problema no es desgaste de esta unidad puntual "
              "sino algo que probablemente se repita en todos los equipos del "
              "mismo modelo. Sube significativamente el riesgo calculado."))
        g.attach(self.chk_afecta_categoria, 0, 3, 3, 1)

        self.chk_resuelto = Gtk.CheckButton(label=_("Resuelto"))
        self.chk_resuelto.connect("toggled", self._on_toggle_resuelto)
        g.attach(self.chk_resuelto, 0, 4, 1, 1)
        self.e_fecha_resolucion = _entry(g, 4)
        self.e_fecha_resolucion.set_placeholder_text(_("Fecha de resolución (AAAA-MM-DD)"))
        self.e_fecha_resolucion.set_sensitive(False)

        self.get_content_area().add(g)

        # Descripción
        sep = Gtk.Separator(); self.get_content_area().pack_start(sep, False, False, 6)
        lbl_desc = Gtk.Label(label=_("Descripción:"))
        lbl_desc.set_xalign(0); lbl_desc.set_margin_start(12)
        self.get_content_area().pack_start(lbl_desc, False, False, 0)
        scroll_d = Gtk.ScrolledWindow()
        scroll_d.set_min_content_height(100)
        scroll_d.set_margin_start(12); scroll_d.set_margin_end(12)
        scroll_d.set_margin_bottom(8)
        self.tv_descripcion = Gtk.TextView()
        self.tv_descripcion.set_wrap_mode(Gtk.WrapMode.WORD)
        scroll_d.add(self.tv_descripcion)
        self.get_content_area().pack_start(scroll_d, True, True, 0)

        if id_problema:
            rows = Modelo.devolver_problema(id_problema)
            if rows:
                r = rows[0]
                # 0:id_problema 1:id_categoria 2:categoria 3:id_equipo
                # 4:gravedad 5:descripcion 6:fecha
                # 7:afecta_categoria_equipo 8:resuelto 9:fecha_resolucion
                self.id_categoria = s(r[1])
                _set_combo_id(self.c_categoria, self.id_categoria)
                self.id_equipo = r[3]
                self.sp_gravedad.set_value(r[4] if r[4] is not None else 3)
                if r[5]:
                    self.tv_descripcion.get_buffer().set_text(s(r[5]))
                if len(r) > 6 and r[6]:
                    self.e_fecha.set_text(s(r[6]))
                if len(r) > 7 and r[7]:
                    self.chk_afecta_categoria.set_active(True)
                if len(r) > 8 and r[8]:
                    self.chk_resuelto.set_active(True)
                    self.e_fecha_resolucion.set_sensitive(True)
                if len(r) > 9 and r[9]:
                    self.e_fecha_resolucion.set_text(s(r[9]))
        else:
            import datetime
            self.e_fecha.set_text(datetime.date.today().strftime("%Y-%m-%d"))

        _pack_ultima_edicion(self, "problema_equipo", "id_problema", id_problema)
        self.show_all()

    def _sel_categoria_dropdown(self, btn):
        dlg = CategoriasProblemaListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_categoria, Modelo.devolver_todas_las_categorias_problema())
            _set_combo_id(self.c_categoria, dlg.resultado_id)
        dlg.destroy()

    def _on_toggle_resuelto(self, chk):
        self.e_fecha_resolucion.set_sensitive(chk.get_active())
        if chk.get_active() and not self.e_fecha_resolucion.get_text().strip():
            import datetime
            self.e_fecha_resolucion.set_text(datetime.date.today().strftime("%Y-%m-%d"))

    def _get_descripcion(self):
        buf = self.tv_descripcion.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip() or None

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_categoria = _get_combo_id(self.c_categoria)
            gravedad = self.sp_gravedad.get_value_as_int()
            descripcion = self._get_descripcion()
            fecha = self.e_fecha.get_text().strip() or None
            afecta_categoria = self.chk_afecta_categoria.get_active()
            resuelto = self.chk_resuelto.get_active()
            fecha_resolucion = (self.e_fecha_resolucion.get_text().strip() or None
                                if resuelto else None)
            if self.id_problema:
                Modelo.modificacion_problema(
                    self.id_problema, id_categoria or None, self.id_equipo,
                    gravedad, descripcion, fecha,
                    afecta_categoria, resuelto, fecha_resolucion)
            else:
                Modelo.agregar_problema(
                    id_categoria or None, self.id_equipo, gravedad, descripcion, fecha,
                    afecta_categoria, resuelto, fecha_resolucion)
        self.destroy()


# ─── Imágenes ─────────────────────────────────────────────────────────────────

class ImagenesListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Imágenes"), [_("ID"), _("Ruta archivo"), _("Descripción")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_imagenes())

    def nuevo(self):
        _DialogoImagen(parent=self).run_and_destroy()
        self.cargar_datos()

    def editar(self, id_):
        dlg = _DialogoImagen(id_imagen=id_, parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def eliminar(self, id_):
        Modelo.eliminar_imagen(id_)


class _DialogoImagen(Gtk.Dialog):
    def __init__(self, id_imagen=None, parent=None):
        super().__init__(title=_("Imagen"), transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(480, 180)
        self.id_imagen = id_imagen

        grid = Gtk.Grid(column_spacing=8, row_spacing=6,
                        margin_start=12, margin_end=12,
                        margin_top=12, margin_bottom=12)

        grid.attach(Gtk.Label(label=_("Ruta archivo:"), xalign=1), 0, 0, 1, 1)
        self.e_path = Gtk.Entry(hexpand=True, activates_default=True)
        grid.attach(self.e_path, 1, 0, 1, 1)

        btn_abrir = Gtk.Button(label="📂 " + _("Explorar"))
        btn_abrir.connect("clicked", self._explorar)
        grid.attach(btn_abrir, 2, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Descripción:"), xalign=1), 0, 1, 1, 1)
        self.e_desc = Gtk.Entry(hexpand=True, activates_default=True)
        grid.attach(self.e_desc, 1, 1, 2, 1)

        self.get_content_area().add(grid)

        if id_imagen:
            rows = Modelo.devolver_imagen(id_imagen)
            if rows:
                self.e_path.set_text(s(rows[0][1]))
                self.e_desc.set_text(s(rows[0][2]))

        _pack_ultima_edicion(self, "imagen", "id_imagen", id_imagen)
        self.show_all()

    def _explorar(self, btn):
        dlg = Gtk.FileChooserDialog(
            title=_("Seleccionar imagen"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Abrir"), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name(_("Imágenes"))
        filt.add_mime_type("image/*")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if ruta:
                # Copiar a subcarpeta imagen/ junto al db. A diferencia de
                # la versión anterior ("copiar sólo si el destino no
                # existe"), acá se pisa el archivo salvo que origen y
                # destino sean literalmente el mismo archivo (ya está
                # dentro de IMG_DIR) — mismo criterio que _sel_picon y el
                # selector de manuales. Con el criterio viejo, si ya
                # había un archivo con ese nombre en IMG_DIR (ej. un
                # intento previo corrupto o vacío), volver a usar
                # "Explorar" con el archivo corregido dejaba el campo con
                # el nombre bien puesto pero el contenido en disco sin
                # actualizar — la imagen quedaba "pisada" por la vieja
                # sin ningún aviso.
                os.makedirs(IMG_DIR, exist_ok=True)
                nombre = os.path.basename(ruta)
                destino = os.path.join(IMG_DIR, nombre)
                if os.path.abspath(ruta) != os.path.abspath(destino):
                    try:
                        import shutil
                        shutil.copy2(ruta, destino)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la imagen: {e}")
                self.e_path.set_text(nombre)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            path = self.e_path.get_text().strip() or None
            desc = self.e_desc.get_text().strip() or None
            # "Explorar" copia el archivo elegido a IMG_DIR y después
            # completa este mismo campo, pero acá se puede escribir/pegar
            # el nombre de archivo a mano sin pasar por esa copia. Si el
            # archivo referenciado no está realmente en IMG_DIR, guardar
            # igual deja la imagen "colgada": cualquier pantalla que la
            # use (ej. abrir un equipo con esta imagen asociada) va a
            # mostrar el recuadro negro "Sin imagen asignada" sin más
            # explicación. Avisamos antes de guardar para que quede claro
            # por qué — pero sin bloquear el guardado, porque cargar el
            # registro antes de tener el archivo copiado es un flujo
            # válido (p.ej. wip).
            if path and not os.path.isfile(os.path.join(IMG_DIR, path)):
                mostrar_error(
                    self,
                    _("El archivo '{0}' no está en la carpeta de imágenes "
                      "({1}). El registro se va a guardar igual, pero la "
                      "imagen va a aparecer en negro (\"Sin imagen\") "
                      "hasta que copies el archivo ahí — usá el botón "
                      "\"Explorar\" en vez de escribir la ruta a mano, o "
                      "copiá el archivo manualmente a esa carpeta.")
                    .format(path, IMG_DIR))
            if self.id_imagen:
                Modelo.modificacion_imagen(self.id_imagen, path, desc)
            else:
                Modelo.alta_imagen(path, desc)
        self.destroy()


class _DialogoRenombrarConectoresCatalogo(Gtk.Dialog):
    """Igual que _DialogoRenombrarConectores pero para los conectores de un
    MOLDE de catálogo (conector_catalogo), no de un equipo real."""

    def __init__(self, id_equipo_catalogo, parent=None):
        super().__init__(
            title=_("Renombrar Conectores del Molde"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(600, 500)
        self.id_equipo_catalogo = id_equipo_catalogo

        # Contenedor principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.get_content_area().add(vbox)

        # Obtener conectores del molde
        # cols: id_conector_catalogo, nombre, tipo_nombre, id_tipo_conector,
        #       id_imagen, img_path, x, y
        conectores = Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo)

        # Crear grid para los conectores
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(4)
        grid.set_vexpand(True)
        grid.set_hexpand(True)

        # Crear lista para guardar los entries
        self.entries = []

        for i, c in enumerate(conectores):
            id_cc, nombre = c[0], c[1]
            # Label con el nombre actual
            lbl = Gtk.Label(label=nombre)
            lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1)

            # Entry para el nuevo nombre
            entry = Gtk.Entry()
            entry.set_text(nombre)
            entry.set_hexpand(True)
            grid.attach(entry, 1, i, 1, 1)

            # Guardar referencia al entry junto con el id y nombre original
            self.entries.append({
                'id': id_cc,
                'original': nombre,
                'entry': entry
            })

        if not conectores:
            lbl_vacio = Gtk.Label(label=_("Este molde todavía no tiene conectores."))
            lbl_vacio.set_xalign(0)
            grid.attach(lbl_vacio, 0, 0, 2, 1)

        # ScrolledWindow para el grid
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        sw.add(grid)
        vbox.pack_start(sw, True, True, 0)

        self.show_all()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            # Guardar los cambios
            for item in self.entries:
                nuevo_nombre = item['entry'].get_text().strip()
                # Si está en blanco, mantener el nombre original
                if not nuevo_nombre:
                    nuevo_nombre = item['original']
                # Solo actualizar si el nombre cambió
                if nuevo_nombre != item['original']:
                    # Obtener los otros datos del conector-molde para no perderlos
                    conectores = Modelo.devolver_conectores_de_catalogo(
                        self.id_equipo_catalogo)
                    fila = next((c for c in conectores if str(c[0]) == str(item['id'])), None)
                    if fila:
                        Modelo.modificacion_conector_catalogo(
                            item['id'],
                            nuevo_nombre,
                            fila[3],  # id_tipo_conector
                            fila[4],  # id_imagen
                            fila[6],  # x
                            fila[7],  # y
                            fila[8] if len(fila) > 8 else None,  # fila_patchera
                        )
        self.destroy()


# ─── Conexiones de equipo / cable (vista informativa) ─────────────────────────

class ConexionesDeEquipoVentana(Gtk.Dialog):
    """Muestra las conexiones de un equipo específico en una tabla."""

    COLS = [_("Cable"), _("Equipo A"), _("Tipo equipo A"), _("Conector A"),
            _("Tipo conector A"), _("Equipo B"), _("Tipo equipo B"),
            _("Conector B"), _("Tipo conector B")]

    def __init__(self, id_equipo, parent=None):
        super().__init__(title=_("Conexiones del equipo"),
                         transient_for=parent,
                         destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1100, 500)
        self.id_equipo = id_equipo

        area = self.get_content_area()

        # Filtro
        hb = Gtk.Box(spacing=6, margin_start=8, margin_end=8, margin_top=6)
        hb.pack_start(Gtk.Label(label=_("Filtro:")), False, False, 0)
        self.entry_filtro = Gtk.SearchEntry(hexpand=True)
        self.entry_filtro.connect("search-changed", self._filtrar)
        hb.pack_start(self.entry_filtro, True, True, 0)
        area.pack_start(hb, False, False, 0)

        sw = Gtk.ScrolledWindow(vexpand=True,
                                margin_start=8, margin_end=8, margin_bottom=8)
        store = Gtk.ListStore(*([str] * len(self.COLS)))
        self.filtro = store.filter_new()
        self.filtro.set_visible_func(self._vis)
        self.store = store
        tv = Gtk.TreeView(model=self.filtro, headers_visible=True)
        for i, h in enumerate(self.COLS):
            rend = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(h, rend, text=i)
            col.set_resizable(True); col.set_expand(True)
            tv.append_column(col)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        rows = Modelo.devolver_conexiones_de_equipo(self.id_equipo)
        for r in rows:
            self.store.append([s(v) for v in r[:9]])

    def _vis(self, model, it, data):
        txt = self.entry_filtro.get_text().lower()
        if not txt: return True
        for i in range(len(self.COLS)):
            if txt in s(model.get_value(it, i)).lower():
                return True
        return False

    def _filtrar(self, e):
        self.filtro.refilter()


# ─── Generación de diagrama Graphviz ─────────────────────────────────────────


# ─── Diagramas personalizados (guardados) ─────────────────────────────────
# Feature aparte: ABM de diagramas armados a mano (ver diagrama_personalizado.py
# y las tablas diagrama_guardado* en modelo.py). No comparte flujo con el
# diagrama global de conexiones.

class DiagramasGuardadosListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Diagramas personalizados"),
            [_("ID"), _("Nombre"), _("Descripción"), _("Última edición"), _("Equipos")],
            parent=parent, modo_seleccion=modo_seleccion,
        )
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_diagramas_guardados())

    def nuevo(self):
        dlg = DiagramaPersonalizado(parent=self)
        dlg.run(); dlg.destroy()

    def editar(self, id_):
        dlg = DiagramaPersonalizado(id_diagrama_guardado=id_, parent=self)
        dlg.run(); dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_diagrama_guardado(id_)


class GeneradorDiagrama:
    """Genera diagramas Graphviz de conexiones entre equipos."""

    @staticmethod
    def generar_dot_equipo(id_equipo):
        cables = {}      # codigo_cable → [equipo_orig, f_orig, equipo_dest, f_dest]
        nodos = {}       # nombre_equipo → {nombre_conector: orden}

        rows = Modelo.devolver_equipos_conectados_a_equipo(id_equipo)
        for r in rows:
            # CONEXIONES_AMBOS_EXTREMOS cols:
            # Cable, Extremo B Equipo, ..conector.., Extremo A equipo, ..conector..
            cable = s(r[0]).replace('"', '').replace('->', ' ')
            eq_a = s(r[1]).replace('"', '').replace('->', ' ')  # Extremo B: Equipo
            con_a = s(r[3]).replace('"', '').replace('->', ' ')  # Extremo B: conector
            eq_b = s(r[5]).replace('"', '').replace('->', ' ')  # Extremo A: equipo
            con_b = s(r[7]).replace('"', '').replace('->', ' ')  # Extremo A: conector

            for eq, con in [(eq_a, con_a), (eq_b, con_b)]:
                if eq not in nodos:
                    nodos[eq] = {}
                if con not in nodos[eq]:
                    nodos[eq][con] = len(nodos[eq])

            if cable not in cables:
                ord_a = nodos[eq_a][con_a]
                ord_b = nodos[eq_b][con_b]
                cables[cable] = [eq_a, f"f{ord_a+1}", eq_b, f"f{ord_b+1}"]

        lines = [
            'digraph g {',
            '  fontname="Helvetica,Arial,sans-serif"',
            '  node [fontname="Helvetica,Arial,sans-serif"]',
            '  edge [fontname="Helvetica,Arial,sans-serif" arrowhead=none]',
            '  graph [rankdir="LR"]',
            '  node [fontsize=14 shape=record]',
        ]
        for eq, conectores in nodos.items():
            partes = f"<f0> {eq}"
            for con, idx in conectores.items():
                partes += f" | <f{idx+1}> {con}"
            lines.append(f'  "{eq}" [label="{partes}"];')
        for cable, info in cables.items():
            lines.append(
                f'  "{info[0]}":{info[1]} -> "{info[2]}":{info[3]}'
                f' [label="{cable}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def generar_y_abrir(id_equipo, parent=None):
        dot_content = GeneradorDiagrama.generar_dot_equipo(id_equipo)
        dot_path = f"diagrama_{id_equipo}.dot"
        pdf_path = dot_path + ".pdf"

        with open(dot_path, "w", encoding="utf-8") as f:
            f.write(dot_content)

        try:
            result = subprocess.run(
                ["dot", "-Tpdf", dot_path, "-o", pdf_path],
                timeout=60, capture_output=True
            )
            if result.returncode == 0:
                subprocess.Popen(
                    ["xdg-open", pdf_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                if parent:
                    mostrar_error(parent,
                        f"Error al generar el diagrama:\n"
                        f"{result.stderr.decode()}\n\n"
                        f"Archivo .dot guardado en: {dot_path}"
                    )
        except FileNotFoundError:
            if parent:
                mostrar_error(parent,
                    "No se encontró el comando 'dot' (Graphviz).\n"
                    "Instalá Graphviz con: sudo apt install graphviz\n\n"
                    f"Archivo .dot guardado en: {dot_path}"
                )
        except subprocess.TimeoutExpired:
            if parent:
                mostrar_error(parent, "Tiempo de espera agotado generando el diagrama.")


# ─── Ventana de información de equipo ────────────────────────────────────────

class EquipoInfoExtra(Gtk.Dialog):
    """Muestra conexiones + genera diagrama para un equipo."""

    def __init__(self, id_equipo, parent=None):
        super().__init__(title="Información de Equipo",
                         transient_for=parent,
                         destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1000, 550)
        self.id_equipo = id_equipo

        area = self.get_content_area()

        # Toolbar
        tb = Gtk.Box(spacing=8, margin_start=8, margin_top=6, margin_bottom=4)
        btn_diag = Gtk.Button(label=_("📊 Generar diagrama PDF"))
        btn_diag.connect("clicked", lambda b: GeneradorDiagrama.generar_y_abrir(
            id_equipo, self))
        tb.pack_start(btn_diag, False, False, 0)
        area.pack_start(tb, False, False, 0)

        area.pack_start(Gtk.Separator(), False, False, 0)

        dlg = ConexionesDeEquipoVentana(id_equipo, parent=self)
        # Reutilizamos el contenido de ConexionesDeEquipoVentana
        # pero incrustado directamente
        conexiones_widget = ConexionesDeEquipoVentana(id_equipo, parent=self)
        # In practice just show the dialog separately
        self.show_all()
        dlg.destroy()
        conexiones_widget.run()
        conexiones_widget.destroy()


# ─── Ventana principal ────────────────────────────────────────────────────────


# ─── Panel de árbol de infraestructura ───────────────────────────────────────

class PanelArbol(Gtk.Box):
    """
    Panel lateral con árbol jerárquico de infraestructura:
      Sala → Rack → Frame → Equipo → Conectores
              └──→ Equipo directo → Conectores
         └──→ Equipos sin rack → Conectores

    Al hacer clic en un nodo se abre el diálogo de edición correspondiente.
    """

    # Columnas del TreeStore
    COL_LABEL  = 0   # str — texto visible
    COL_TIPO   = 1   # str — "sala"|"rack"|"frame"|"equipo"|"conector"|"sin_rack"
    COL_ID     = 2   # str — id del objeto
    COL_ID2    = 3   # str — id auxiliar (id_rack para frame, id_equipo para conector)
    COL_COLOR  = 4   # str — color de la etiqueta de tipo
    COL_BADGE  = 5   # str — texto del badge
    COL_PESO   = 6   # int — Pango weight (700=bold, 400=normal)

    _BADGE_COLOR = {
        "sala":     "#534AB7",
        "rack":     "#185FA5",
        "frame":    "#BA7517",
        "equipo":   "#3B6D11",
        "conector": "#555550",
        "sin_rack": "#888880",
        "cable":    "#8B4513",
        "conexion": "#708090",
        "seccion":  "#444444",
    }

    def __init__(self, ventana_principal):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._vp = ventana_principal
        self.set_size_request(260, -1)

        # ── Cabecera ──
        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hdr.set_margin_start(8); hdr.set_margin_end(8)
        hdr.set_margin_top(6);   hdr.set_margin_bottom(4)

        lbl_titulo = Gtk.Label(xalign=0)
        lbl_titulo.set_markup("<b>Infraestructura</b>")
        hdr.pack_start(lbl_titulo, False, False, 0)

        # Buscador
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_lupa = Gtk.Label(label="🔍")
        self._entry_filtro = Gtk.Entry(placeholder_text="buscar equipo, rack, frame…")
        self._entry_filtro.set_hexpand(True)
        self._entry_filtro.connect("changed", self._on_filtro_changed)
        search_box.pack_start(lbl_lupa, False, False, 0)
        search_box.pack_start(self._entry_filtro, True, True, 0)
        hdr.pack_start(search_box, False, False, 0)

        self._lbl_status = Gtk.Label(xalign=0)
        self._lbl_status.set_no_show_all(False)
        hdr.pack_start(self._lbl_status, False, False, 0)

        self.pack_start(hdr, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        # ── TreeStore: label, tipo, id, id2, color, badge, peso ──
        self._store = Gtk.TreeStore(str, str, str, str, str, str, int)
        self._filter = self._store.filter_new()
        self._filter.set_visible_func(self._row_visible)

        # PRUEBA: Usar el store directamente para drag and drop
        # self._tv = Gtk.TreeView(model=self._filter)
        self._tv = Gtk.TreeView(model=self._store)
        self._tv.set_headers_visible(False)
        self._tv.set_enable_search(False)
        self._tv.set_reorderable(False)  # Importante para drag and drop
        self._tv.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        col = Gtk.TreeViewColumn()
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_expand(True)
        self._tv.append_column(col)
        self._tv.set_hexpand(True)

        # Nombre del nodo — sin truncar
        rend_label = Gtk.CellRendererText()
        col.pack_start(rend_label, True)
        col.add_attribute(rend_label, "text",   self.COL_LABEL)
        col.add_attribute(rend_label, "weight", self.COL_PESO)

        # Badge de tipo (sala / rack / frame / equipo …)
        rend_badge = Gtk.CellRendererText(xpad=4, foreground_set=True)
        col.pack_start(rend_badge, False)
        col.add_attribute(rend_badge, "text",       self.COL_BADGE)
        col.add_attribute(rend_badge, "foreground", self.COL_COLOR)

        self._tv.connect("row-activated", self._on_row_activated)
        
        # ── Configurar Drag and Drop ─────────────────────────────────────
        # Permitir arrastrar equipos sin ubicación a salas
        import sys
        # Abrir archivo de log
        self._drag_drop_log = open("/tmp/cabledoc_drag_drop.log", "w", encoding="utf-8")
        def safe_log(msg):
            try:
                self._drag_drop_log.write(f"{msg}\n")
                self._drag_drop_log.flush()
            except Exception:
                pass
            try:
                print(f"{msg}", flush=True)
            except (BrokenPipeError, OSError):
                # Ignorar errores de pipe roto (cuando timeout termina el proceso)
                pass
            except Exception as e:
                pass
        self._log = safe_log
        
        self._log("\n" + "="*60)
        self._log("DRAG DROP LOG - Ver este archivo: /tmp/cabledoc_drag_drop.log")
        self._log("="*60)
        
        # Configurar drag source usando el STORE original (no el filtro)
        # Esto es necesario porque TreeModelFilter no soporta bien drag and drop
        # Ahora que usamos self._store directamente, configurar drag and drop normal
        self._log("Configurando drag source en TreeView")
        # Usar target STRING para simplificar
        target_entry = Gtk.TargetEntry.new("STRING", Gtk.TargetFlags.SAME_WIDGET, 0)
        self._tv.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            [target_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        )
        self._tv.connect("drag-data-get", self._on_drag_data_get)
        
        self._log("Configurando drag dest en TreeView")
        self._tv.enable_model_drag_dest(
            [target_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        )
        self._tv.connect("drag-data-received", self._on_drag_data_received)
        # Conectar drag-motion para indicar que el destino es válido
        self._tv.connect("drag-motion", self._on_drag_motion_valid)
        self._log("Drag and drop configurado ===")
        
        # Configurar drag and drop manual (para TreeModelFilter) - COMENTADO para usar DnD nativo
        # self._tv.connect("button-press-event", self._on_treeview_button_press)
        # self._tv.connect("button-release-event", self._on_treeview_button_release)
        # self._tv.connect("motion-notify-event", self._on_motion_notify)

        sw = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._tv)
        self.pack_start(sw, True, True, 0)

        # Botón recargar
        btn_reload = Gtk.Button(label=_("↺ Recargar árbol"))
        btn_reload.set_margin_start(6); btn_reload.set_margin_end(6)
        btn_reload.set_margin_top(4);   btn_reload.set_margin_bottom(6)
        btn_reload.connect("clicked", lambda b: self.recargar(forzar_bd=True))
        self.pack_start(btn_reload, False, False, 0)

        self._filtro_texto = ""
        self._arbol_datos = None       # cache en memoria: [nodo_infra, nodo_cables]
        self._filtro_debounce_id = None
        self.recargar(forzar_bd=True)

    # ── Manejadores de eventos para debug ────────────────────────────────────
    def _on_drag_motion_valid(self, tv, context, x, y, timestamp):
        """Manejador para validar movimiento durante drag y configurar destino."""
        # Obtener el nodo bajo el cursor
        result = tv.get_path_at_pos(x, y)
        if result:
            path = result[0]
            self._log(f"[DRAG MOTION] Path válido: {path} en ({x}, {y})")
            # Indicar que el destino es válido
            # Configurar el destino del drag para resaltar
            tv.set_drag_dest_row(path, Gtk.TreeViewDropPosition.INTO_OR_AFTER)
            # Aceptar el drop
            Gdk.drag_status(context, Gdk.DragAction.COPY, timestamp)
            return True
        else:
            self._log(f"[DRAG MOTION] No hay nodo en ({x}, {y})")
            # Rechazar el drop en esta posición
            Gdk.drag_status(context, 0, timestamp)
            return False

    def _on_treeview_button_press(self, tv, event):
        """Manejador para detectar click en TreeView y grabar el punto de inicio del drag."""
        result = tv.get_path_at_pos(event.x, event.y)
        # get_path_at_pos devuelve (path, column, x, y) o None
        if result:
            path = result[0]  # Extraer solo el path
            self._log(f"[BUTTON PRESS] path={path}, button={event.button}")
            # Guardar información para posible drag
            if event.button == 1:  # Botón izquierdo
                self._drag_start_path = path  # Guardar solo el path
                self._drag_start_x = event.x
                self._drag_start_y = event.y
        else:
            self._log(f"[BUTTON PRESS] No path at ({event.x}, {event.y}), button={event.button}")
            self._drag_start_path = None
        return False  # Permitir propagación del evento

    def _on_treeview_button_release(self, tv, event):
        """Manejador para detectar release en TreeView."""
        result = tv.get_path_at_pos(event.x, event.y)
        path = result[0] if result else None
        if path:
            self._log(f"[BUTTON RELEASE] path={path}, button={event.button}")
        else:
            self._log(f"[BUTTON RELEASE] No path at ({event.x}, {event.y}), button={event.button}")
        # Limpiar drag start
        self._drag_start_path = None
        return False  # Permitir propagación del evento

    def _on_motion_notify(self, tv, event):
        """Manejador para detectar movimiento y iniciar drag manualmente."""
        # Verificar si hay un drag en progreso
        if hasattr(self, '_drag_start_path') and self._drag_start_path is not None:
            # Calcular distancia desde el inicio
            dx = abs(event.x - self._drag_start_x)
            dy = abs(event.y - self._drag_start_y)
            # Iniciar drag si se movió suficiente distancia (threshold típico: 5-10 píxeles)
            if dx > 5 or dy > 5:
                self._log(f"[MOTION] Iniciando drag manual desde {self._drag_start_path}")
                # Obtener el iter del path guardado
                it = self._store.get_iter(self._drag_start_path)
                if it:
                    tipo = self._store.get_value(it, self.COL_TIPO)
                    oid = self._store.get_value(it, self.COL_ID)
                    self._log(f"[MOTION] tipo={tipo}, ID={oid}")
                    
                    if tipo == "equipo":
                        # Iniciar drag manualmente
                        self._start_manual_drag(tv, oid, self._drag_start_path)
                        # Limpiar para evitar múltiples drags
                        self._drag_start_path = None
                        return True  # Evento manejado
        return False  # Permitir propagación del evento

    def _start_manual_drag(self, tv, equipo_id, path):
        """Inicia un drag manualmente con el ID del equipo."""
        self._log(f"[MANUAL DRAG] Iniciando drag para equipo {equipo_id}")
        
        # Crear target list
        target_list = Gtk.TargetList.new([
            Gtk.TargetEntry.new("tree-row", Gtk.TargetFlags.SAME_WIDGET, 0)
        ])
        
        # Iniciar el drag
        context = tv.drag_begin(
            target_list,
            Gdk.DragAction.COPY,
            1,  # Botón izquierdo
            (0, 0)  # Hotspot
        )
        
        # Conectar señal drag-data-get al contexto
        context.connect("drag-data-get", self._on_manual_drag_data_get, equipo_id)
        
        self._log(f"[MANUAL DRAG] Drag iniciado para equipo {equipo_id}")

    def _on_manual_drag_data_get(self, context, selection, info, timestamp, equipo_id):
        """Manejador para proporcionar datos durante drag manual."""
        self._log(f"[MANUAL DRAG] drag-data-get llamado para equipo {equipo_id}")
        selection.set(Gtk.SELECTION_TYPE_STRING, 0, str(equipo_id).encode())

    # ── Drag and Drop ─────────────────────────────────────────────────────────
    
    def _on_drag_drop(self, tv, context, x, y, timestamp):
        """Sobrescribir manejador por defecto de drag_drop (requerido para TreeModelFilter)."""
        # Detener la emisión de la señal por defecto
        GObject.signal_stop_emission_by_name(tv, "drag_drop")
        # Devolver True para indicar que manejamos el evento
        return True

    def _on_drag_data_get(self, tv, context, selection, info, timestamp):
        """Manejador para obtener datos al arrastrar un nodo."""
        self._log("\n--- DRAG START ---")
        self._log(f"_on_drag_data_get called")
        # Usar la selección actual del TreeView
        sel = tv.get_selection()
        model, it = sel.get_selected()
        self._log(f"Selection - model: {model}, it: {it}")
        if not it:
            self._log("No selected iter")
            return
        
        # Obtener tipo e ID del iter
        tipo = model.get_value(it, self.COL_TIPO)
        oid = model.get_value(it, self.COL_ID)
        self._log(f"Node - Tipo: {tipo}, ID: {oid}")
        
        # Solo permitir arrastrar equipos (incluyendo los de "Sin ubicación")
        if tipo == "equipo":
            self._log(f"Setting selection data for equipo {oid}")
            # Almacenar el ID del equipo en la selección
            # Usar set_text que automáticamente usa el target STRING
            selection.set_text(str(oid), -1)
        else:
            self._log(f"Not an equipo, type is {tipo}")

    def _on_drag_data_received(self, tv, context, x, y, selection, info, timestamp):
        """Manejador para recibir datos al soltar en un nodo."""
        self._log("\n--- DROP RECEIVED ---")
        self._log(f"[DROP] x={x}, y={y}")
        
        # Obtener el equipo arrastrado
        id_equipo = selection.get_text()
        if not id_equipo:
            data = selection.get_data()
            id_equipo = data.decode() if data else None
        if not id_equipo:
            self._log("No data received")
            context.finish(False, False)
            return
        self._log(f"Equipo arrastrado ID: {id_equipo}")
        
        # Obtener el nodo destino (donde se soltó)
        # get_drag_dest_row() sin parámetros para obtener el destino actual del drag
        result = tv.get_drag_dest_row()
        self._log(f"[DROP] get_drag_dest_row() result: {result}")
        if result:
            path, pos = result
            self._log(f"[DROP] Drag dest row path: {path}, pos: {pos}")
            # Si get_drag_dest_row devolvió path=None, intentar con get_path_at_pos
            if not path:
                result = tv.get_path_at_pos(x, y)
                path = result[0] if result else None
                pos = None
                self._log(f"[DROP] Fallback 1: Path at pos: {path}")
        else:
            # Intentar con get_path_at_pos
            result = tv.get_path_at_pos(x, y)
            path = result[0] if result else None
            pos = None
            self._log(f"[DROP] Fallback 2: Path at pos: {path}")
        
        if not path:
            self._log("[DROP ERROR] No path found at all")
            context.finish(False, False)
            return
        
        # Usar el store directamente (el TreeView ahora usa self._store)
        it = self._store.get_iter(path)
        if not it:
            self._log("No iter found for path")
            context.finish(False, False)
            return
        
        # it ya es del store, no necesitamos convertir
        self._log(f"Iter obtenido para path {path}")
        
        tipo_destino = self._store.get_value(it, self.COL_TIPO)
        id_destino = self._store.get_value(it, self.COL_ID)
        nombre_destino = self._store.get_value(it, self.COL_LABEL)
        self._log(f"Destino - Tipo: {tipo_destino}, ID: {id_destino}, Nombre: {nombre_destino}")
        
        # Obtener nombre del equipo
        eq_row = Modelo.devolver_equipo(id_equipo)
        nombre_equipo = s(eq_row[0][1]) if eq_row and eq_row[0] else f"Equipo {id_equipo}"
        self._log(f"Equipo nombre: {nombre_equipo}")
        
        # Verificar si el equipo ya tiene ubicación
        import sqlite3
        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur = conn.cursor()
        
        # Verificar si está en rack/frame
        cur.execute("SELECT 1 FROM posicion_en_rack WHERE id_equipo = ?", (id_equipo,))
        en_rack = cur.fetchone() is not None
        self._log(f"en_rack: {en_rack}")
        
        # Verificar si está en slot
        cur.execute("SELECT 1 FROM slot WHERE id_equipo = ?", (id_equipo,))
        en_slot = cur.fetchone() is not None
        self._log(f"en_slot: {en_slot}")
        
        # Verificar si está en equiponoraqueable_por_sala
        cur.execute("SELECT 1 FROM equiponoraqueable_por_sala WHERE id_equipo = ?", (id_equipo,))
        en_sala = cur.fetchone() is not None
        self._log(f"en_sala: {en_sala}")
        
        conn.close()
        
        equipo_sin_ubicacion = not en_rack and not en_slot and not en_sala
        self._log(f"equipo_sin_ubicacion: {equipo_sin_ubicacion}")
        
        # Permitir soltar solo equipos sin ubicación
        if tipo_destino == "sala" and equipo_sin_ubicacion:
            self._log(f"Abriendo _DialogoEquipoNoRackSala para sala {id_destino}")
            # Abrir diálogo para agregar equipo suelto a sala
            from cabledoc import _DialogoEquipoNoRackSala
            dlg = _DialogoEquipoNoRackSala(parent=self._vp)
            dlg._id_sala = id_destino
            dlg._id_equipo = id_equipo
            # Prellenar nombres
            dlg.e_sala.set_text(nombre_destino)
            dlg.e_equipo.set_text(nombre_equipo)
            dlg.run_and_destroy()
            self._log(f"Dialogo _DialogoEquipoNoRackSala cerrado")
            self.recargar(forzar_bd=True)
            self._status(f"✅ Equipo {nombre_equipo} asignado a sala {nombre_destino}")
            
        elif tipo_destino == "rack" and equipo_sin_ubicacion:
            self._log(f"Abriendo _DialogoPosicionRack para rack {id_destino}")
            # Abrir diálogo para agregar posición en rack
            dlg = _DialogoPosicionRack(id_rack=id_destino, parent=self._vp)
            dlg.id_equipo = id_equipo
            # Pre-seleccionar el rack
            dlg.e_rack.set_text(nombre_destino)
            # Pre-cargar el equipo que se arrastró
            dlg.e_equipo.set_text(nombre_equipo)
            if dlg.run() == Gtk.ResponseType.OK:
                self._status(f"✅ Equipo {nombre_equipo} asignado a rack {nombre_destino}")
                self.recargar(forzar_bd=True)
            dlg.destroy()
        elif not equipo_sin_ubicacion:
            self._log(f"Equipo ya tiene ubicacion, mostrando mensaje")
            self._status(f"⚠️  El equipo {nombre_equipo} ya tiene una ubicación asignada")
        else:
            self._log(f"Tipo destino no manejado: {tipo_destino}")
        
        context.finish(True, False)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _tlog(self, etapa, extra=""):
        """Log de performance: timestamp + ms transcurridos desde el t0 de esta recarga."""
        ahora = time.perf_counter()
        t0 = getattr(self, "_t0_perf", ahora)
        elapsed_total = (ahora - t0) * 1000
        ultimo = getattr(self, "_t_ultimo_perf", t0)
        elapsed_paso = (ahora - ultimo) * 1000
        self._t_ultimo_perf = ahora
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        msg = f"[PERF {ts}] +{elapsed_paso:7.1f}ms (total {elapsed_total:7.1f}ms)  {etapa}"
        if extra:
            msg += f"  — {extra}"
        print(msg, flush=True)

    MAX_FILAS_CON_FILTRO = 400   # tope de filas insertadas cuando hay filtro activo

    def recargar(self, forzar_bd=False):
        self._t0_perf = time.perf_counter()
        self._t_ultimo_perf = self._t0_perf
        self._tlog("recargar() INICIO",
                   f"filtro='{self._filtro_texto}' forzar_bd={forzar_bd}")
        self._log("\n=== RECARGAR ===")
        # Guardar paths expandidos antes de limpiar
        expandidos = []
        self._tv.map_expanded_rows(lambda tv, path: expandidos.append(path.to_string()))
        self._log(f"Paths expandidos antes: {expandidos}")

        if forzar_bd or self._arbol_datos is None:
            self._arbol_datos = self._cargar_arbol_datos()
            self._tlog("_cargar_arbol_datos() FIN (consultó la BD)")
        else:
            self._tlog("usando caché en memoria (SIN consultar la BD)")

        # Desconectar el modelo del TreeView mientras se reconstruye (evita
        # revalidación/redibujo de GTK en cada append durante la carga completa).
        self._tv.set_model(None)
        try:
            self._store.clear()
            self._renderizar_store_desde_cache()
            self._tlog("_renderizar_store_desde_cache() FIN",
                       f"{self._filas_creadas} filas insertadas, "
                       f"{self._total_matches} matches, tope={self._tope_alcanzado}")
        finally:
            self._tv.set_model(self._store)

        if self._filtro_texto:
            if self._tope_alcanzado:
                self._lbl_status.set_markup(
                    f"<small>Mostrando {self._filas_creadas} de "
                    f"{self._total_matches} coincidencias — "
                    f"seguí escribiendo para acotar…</small>")
            else:
                n = self._total_matches
                self._lbl_status.set_markup(
                    f"<small>{n} coincidencia{'s' if n != 1 else ''}</small>")
            self._tv.expand_all()
            self._tlog("expand_all() FIN — recargar() TOTAL")
            return
        else:
            self._lbl_status.set_text("")

        # Restaurar expansión previa; si no había nada expandido, abrir primer nodo
        if expandidos:
            for path_str in expandidos:
                try:
                    self._tv.expand_row(Gtk.TreePath.new_from_string(path_str), False)
                except Exception:
                    pass
        else:
            # Expandir las dos raíces: Infraestructura (0) y Cables (1)
            self._tv.expand_row(Gtk.TreePath.new_from_string("0"), False)
        self._tlog("recargar() TOTAL")

    def _nodo(self, label, tipo, id_, id2, color, badge, peso, hijos=None):
        return {"vals": [label, tipo, id_, id2, color, badge, peso],
                "hijos": hijos if hijos is not None else []}

    def _renderizar_store_desde_cache(self):
        """Vuelca self._arbol_datos (estructura en memoria) al TreeStore,
        insertando SOLO los nodos visibles (que matchean el filtro o tienen
        algún descendiente que matchea) — nunca inserta un nodo para
        borrarlo después.

        Esa era la causa real de la demora: insertar los ~5000 nodos
        completos en el TreeStore y podar casi todos a continuación generaba
        un churn masivo de objetos GTK/PyGObject que degradaba progresivamente
        (10s → 18s → 22s en llamadas idénticas, aun con el modelo
        desconectado del TreeView). Acá primero se calcula la visibilidad en
        Python puro sobre la caché en memoria (barato, sin GTK), y recién
        después se inserta — una sola vez — lo que corresponde."""
        texto = self._filtro_texto

        visible_cache = {}
        self._total_matches = 0

        def calcular_visibilidad(nodo):
            label = nodo["vals"][0].lower()
            vis_propio = (not texto) or (texto in label)
            if vis_propio and texto:
                self._total_matches += 1
            vis_por_hijo = False
            for hijo in nodo["hijos"]:
                if calcular_visibilidad(hijo):
                    vis_por_hijo = True
            visible = vis_propio or vis_por_hijo
            visible_cache[id(nodo)] = visible
            return visible

        for raiz in self._arbol_datos:
            calcular_visibilidad(raiz)
        self._tlog("calcular_visibilidad() FIN (sin tocar GTK)",
                   f"{self._total_matches} matches directos")

        self._filas_creadas  = 0
        self._tope_alcanzado = False
        limite = self.MAX_FILAS_CON_FILTRO if texto else None

        def volcar(nodo, it_padre):
            if limite is not None and self._filas_creadas >= limite:
                self._tope_alcanzado = True
                return
            it = self._store.append(it_padre, nodo["vals"])
            self._filas_creadas += 1
            for hijo in nodo["hijos"]:
                if limite is not None and self._filas_creadas >= limite:
                    self._tope_alcanzado = True
                    return
                if visible_cache.get(id(hijo), True):
                    volcar(hijo, it)

        for raiz in self._arbol_datos:
            if limite is not None and self._filas_creadas >= limite:
                self._tope_alcanzado = True
                break
            if visible_cache.get(id(raiz), True):
                volcar(raiz, None)

    def _cargar_arbol_datos(self):
        """Lee toda la infraestructura de la BD UNA vez y arma una estructura
        de dicts en memoria (no toca self._store). Se llama solo al abrir
        la ventana, al presionar 'Recargar árbol', o tras un alta/baja/
        modificación — nunca en cada tecla del buscador."""
        import sqlite3

        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur  = conn.cursor()

        hijos_infra = []

        # ── Salas ──
        cur.execute("SELECT id_sala, nombre FROM sala ORDER BY nombre")
        salas = cur.fetchall()
        self._tlog("SQL salas", f"{len(salas)} salas")

        for id_sala, nombre_sala in salas:
            hijos_sala = []

            # Racks de esta sala
            cur.execute("""
                SELECT r.id_rack, r.nombre, r.numero
                FROM rack r
                JOIN rack_por_sala rps ON rps.id_rack = r.id_rack
                WHERE rps.id_sala = ?
                ORDER BY r.numero
            """, (id_sala,))
            racks = cur.fetchall()

            for id_rack, nombre_rack, _nr in racks:
                hijos_rack = []

                # Frames en este rack (via posicion_en_rack)
                cur.execute("""
                    SELECT f.id_frame, f.nombre
                    FROM posicion_en_rack p
                    JOIN frame f ON f.id_frame = p.id_frame
                    WHERE p.id_rack = ? AND p.id_frame IS NOT NULL
                    GROUP BY f.id_frame
                    ORDER BY p.orificio_posicion_equipo_en_rack
                """, (id_rack,))
                frames = cur.fetchall()

                for id_frame, nombre_frame in frames:
                    hijos_frame = []
                    # Equipos en slots de este frame
                    cur.execute("""
                        SELECT e.id_equipo, e.nombre, te.nombre
                        FROM slot sl
                        JOIN equipo e ON e.id_equipo = sl.id_equipo
                        LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                        WHERE sl.id_frame = ? AND sl.id_equipo IS NOT NULL AND sl.id_equipo != 0
                        ORDER BY sl.nombre
                    """, (id_frame,))
                    for id_eq, nom_eq, tipo_eq in cur.fetchall():
                        hijos_frame.append(self._nodo(
                            nom_eq, "equipo", str(id_eq), str(id_frame),
                            self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                            self._conectores_datos(cur, id_eq)))
                    hijos_rack.append(self._nodo(
                        nombre_frame, "frame", str(id_frame), str(id_rack),
                        self._BADGE_COLOR["frame"], "frame", 400, hijos_frame))

                # Equipos directos en rack (sin frame)
                cur.execute("""
                    SELECT e.id_equipo, e.nombre, te.nombre
                    FROM posicion_en_rack p
                    JOIN equipo e ON e.id_equipo = p.id_equipo
                    LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                    WHERE p.id_rack = ? AND p.id_frame IS NULL
                      AND p.id_equipo IS NOT NULL AND p.id_equipo != 0
                    ORDER BY p.orificio_posicion_equipo_en_rack, e.nombre
                """, (id_rack,))
                for id_eq, nom_eq, tipo_eq in cur.fetchall():
                    hijos_rack.append(self._nodo(
                        nom_eq, "equipo", str(id_eq), str(id_rack),
                        self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                        self._conectores_datos(cur, id_eq)))

                hijos_sala.append(self._nodo(
                    nombre_rack, "rack", str(id_rack), str(id_sala),
                    self._BADGE_COLOR["rack"], "rack", 400, hijos_rack))

            # Equipos sueltos de esta sala (equiponoraqueable_por_sala)
            # Excluir equipos que ya están en racks o frames
            cur.execute("""
                SELECT e.id_equipo, e.nombre, COALESCE(te.nombre,'')
                FROM equiponoraqueable_por_sala en
                JOIN equipo e ON e.id_equipo = en.id_equipo
                LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
                WHERE en.id_sala = ?
                AND e.id_equipo NOT IN (
                    SELECT id_equipo FROM posicion_en_rack WHERE id_equipo IS NOT NULL AND id_equipo != 0
                )
                AND e.id_equipo NOT IN (
                    SELECT id_equipo FROM slot WHERE id_equipo IS NOT NULL AND id_equipo != 0
                )
                ORDER BY e.nombre
            """, (id_sala,))
            equipos_sueltos = cur.fetchall()
            if equipos_sueltos:
                hijos_sueltos = []
                for id_eq, nom_eq, tipo_eq in equipos_sueltos:
                    hijos_sueltos.append(self._nodo(
                        nom_eq, "equipo", str(id_eq), str(id_sala),
                        self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                        self._conectores_datos(cur, id_eq)))
                hijos_sala.append(self._nodo(
                    f"Equipos sueltos ({len(equipos_sueltos)})", "sin_rack",
                    str(id_sala), "", self._BADGE_COLOR["sin_rack"], "sueltos", 400,
                    hijos_sueltos))

            hijos_infra.append(self._nodo(
                nombre_sala, "sala", str(id_sala), "",
                self._BADGE_COLOR["sala"], "sala", 700, hijos_sala))

        self._tlog("loop salas/racks/frames/equipos/conectores FIN")

        # ── Equipos sin ubicación (no en rack, slot ni equiponoraqueable_por_sala) ──
        cur.execute("""
            SELECT e.id_equipo, e.nombre, te.nombre
            FROM equipo e
            LEFT JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE e.id_equipo != 0
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM posicion_en_rack
                  WHERE id_equipo IS NOT NULL AND id_equipo != 0
              )
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM slot
                  WHERE id_equipo IS NOT NULL AND id_equipo != 0
              )
              AND e.id_equipo NOT IN (
                  SELECT id_equipo FROM equiponoraqueable_por_sala
                  WHERE id_equipo IS NOT NULL
              )
            ORDER BY e.nombre
        """)
        sin_rack = cur.fetchall()
        if sin_rack:
            hijos_sr = []
            for id_eq, nom_eq, tipo_eq in sin_rack:
                hijos_sr.append(self._nodo(
                    nom_eq, "equipo", str(id_eq), "",
                    self._BADGE_COLOR["equipo"], s(tipo_eq) or "equipo", 400,
                    self._conectores_datos(cur, id_eq)))
            hijos_infra.append(self._nodo(
                "" + _("Sin ubicación") + f" ({len(sin_rack)})", "sin_rack", "", "",
                self._BADGE_COLOR["sin_rack"], "", 700, hijos_sr))

        conn.close()
        self._tlog("_cargar_arbol_datos() sección Infraestructura FIN",
                   f"{len(sin_rack)} sin ubicación")

        nodo_infra = self._nodo(
            _("Infraestructura"), "seccion", "", "",
            self._BADGE_COLOR["seccion"], "", 700, hijos_infra)

        nodo_cables = self._cargar_seccion_cables_datos()
        self._tlog("_cargar_seccion_cables_datos() FIN")

        return [nodo_infra, nodo_cables]

    def _cargar_seccion_cables_datos(self):
        """Devuelve el nodo raíz 'Cables' con sus hijos (cable→conexiones)
        armado con 3 consultas SQL en total (antes: 1 + N conexiones SQLite
        nuevas, una por cada cable — cientos de conexiones por recarga)."""
        import sqlite3
        from collections import defaultdict
        conn = sqlite3.connect(__import__("modelo").DB_PATH)
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM cable")
        total = cur.fetchone()[0]
        self._tlog("_cargar_seccion_cables_datos() SQL count", f"{total} cables")

        cur.execute(
            "SELECT id_cable, codigo, COALESCE(estado,'') FROM cable ORDER BY codigo"
        )
        filas_cable = cur.fetchall()
        self._tlog("_cargar_seccion_cables_datos() SQL lista cables", f"{len(filas_cable)} filas")

        # Todas las conexiones de TODOS los cables en una sola consulta,
        # agrupadas por id_cable en Python (reemplaza al N+1 anterior).
        cur.execute(
            "SELECT id_cable, equipo_nombre, conector_nombre, tipo_conector, id_conexion "
            "FROM CONEXIONES ORDER BY id_cable"
        )
        por_cable = defaultdict(list)
        for id_cable, eq_nom, con_nom, tipo_con, id_conexion in cur.fetchall():
            por_cable[str(id_cable)].append((id_conexion, eq_nom, con_nom, tipo_con))
        self._tlog("_cargar_seccion_cables_datos() SQL conexiones (batch)",
                   f"{sum(len(v) for v in por_cable.values())} conexiones")

        hijos_cables = []
        for id_cable, codigo, estado in filas_cable:
            hijos_conex = []
            for id_conexion, eq_nom, con_nom, tipo_con in por_cable.get(str(id_cable), []):
                conn_label = f"{s(eq_nom) or '?'} - {s(con_nom) or '?'} ({s(tipo_con) or '?'})"
                hijos_conex.append(self._nodo(
                    conn_label, "conexion", str(id_conexion), "",
                    self._BADGE_COLOR["conexion"], "", 300))
            hijos_cables.append(self._nodo(
                s(codigo) or f"#{id_cable}", "cable", str(id_cable), "",
                self._BADGE_COLOR["cable"], estado or "", 400, hijos_conex))

        conn.close()
        self._tlog("_cargar_seccion_cables_datos() loop FIN", f"{len(filas_cable)} cables")

        return self._nodo(
            _("Cables") + f" ({total})", "seccion", "cables", "",
            self._BADGE_COLOR["seccion"], "", 700, hijos_cables)

    def _conectores_datos(self, cur, id_eq):
        cur.execute("""
            SELECT c.id_conector, c.nombre, tc.nombre
            FROM conector c
            LEFT JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector
            WHERE c.id_equipo = ?
            ORDER BY c.nombre
        """, (id_eq,))
        hijos = []
        for id_con, nom_con, tipo_con in cur.fetchall():
            hijos.append(self._nodo(
                nom_con or f"#{id_con}", "conector", str(id_con), str(id_eq),
                self._BADGE_COLOR["conector"], tipo_con or "", 400))
        return hijos

    # ── Filtro ───────────────────────────────────────────────────────────────

    _FILTRO_DEBOUNCE_MS = 300   # pausa de tipeo antes de filtrar
    _FILTRO_MIN_CHARS   = 2     # no filtrar con 1 solo carácter

    def _on_filtro_changed(self, entry):
        # Debounce: cancelar timer pendiente y reprogramar. Así "engin7"
        # tipeado rápido dispara UN solo filtrado, no uno por tecla.
        if self._filtro_debounce_id is not None:
            GLib.source_remove(self._filtro_debounce_id)
            self._filtro_debounce_id = None
        texto = entry.get_text().lower().strip()
        self._filtro_debounce_id = GLib.timeout_add(
            self._FILTRO_DEBOUNCE_MS, self._aplicar_filtro_debounced, texto)

    def _aplicar_filtro_debounced(self, texto):
        self._filtro_debounce_id = None
        # Con 1 solo carácter no filtramos (matchea casi todo, no aporta)
        if texto and len(texto) < self._FILTRO_MIN_CHARS:
            return False
        print(f"\n[PERF ========] filtro aplicado (debounced) → '{texto}'", flush=True)
        self._filtro_texto = texto
        self.recargar()   # sin forzar_bd: usa la caché en memoria, no toca la BD
        return False   # no repetir el GLib.timeout

    def _row_visible(self, model, it, data):
        txt = self._filtro_texto
        if not txt:
            return True
        # La fila es visible si su label o algún descendiente hace match
        label = (model.get_value(it, self.COL_LABEL) or "").lower()
        if txt in label:
            return True
        # Revisar hijos
        child = model.iter_children(it)
        while child:
            if self._row_visible(model, child, data):
                return True
            child = model.iter_next(child)
        return False

    # ── Acción al hacer clic ─────────────────────────────────────────────────

    def _on_row_activated(self, tv, path, col):
        it = self._store.get_iter(path)
        if it is None:
            return
        tipo = self._store.get_value(it, self.COL_TIPO)
        oid  = self._store.get_value(it, self.COL_ID)
        if not oid:
            return

        vp = self._vp
        if tipo == "equipo":
            dlg = _DialogoEquipo(id_equipo=oid, parent=vp)
            dlg.run_and_destroy()
        elif tipo == "sala":
            rows = Modelo.devolver_sala(oid)
            if rows:
                nombre_actual = s(rows[0][1])
                dlg = DialogoNombre(_("Editar Sala"), valor=nombre_actual, parent=vp)
                if dlg.run() == Gtk.ResponseType.OK:
                    Modelo.modificacion_sala(oid, dlg.valor)
                dlg.destroy()
                self.recargar(forzar_bd=True)
        elif tipo == "rack":
            dlg = _DialogoRack(id_rack=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "frame":
            dlg = _DialogoFrame(id_frame=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "conector":
            id_eq = self._store.get_value(it, self.COL_ID2)
            dlg = _DialogoConector(id_conector=oid, id_equipo=id_eq, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "cable":
            dlg = _DialogoCable(id_cable=oid, parent=vp)
            dlg.run_and_destroy()
            self.recargar(forzar_bd=True)
        elif tipo == "conexion":
            dlg = _DialogoConexion(id_conexion=oid, parent=vp)
            dlg.run_and_destroy()

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
