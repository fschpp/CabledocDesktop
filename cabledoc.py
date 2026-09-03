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
APP_VERSION = "1.20260903020900"

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

def _parse_float_opt(texto):
    """Convierte un Entry a float o None (campo vacío = sin dato, no 0)."""
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _fmt_float_opt(valor):
    if valor is None:
        return ""
    if float(valor) == int(valor):
        return str(int(valor))
    return str(valor)


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


# ─── Señal (catálogos) ────────────────────────────────────────────────────────
# Fase 2 de plan_entidad_senal.md. Ver también la sección "Señal" agregada a
# _DialogoConector (asignación por conector) y abrir_buscador_senal (¿dónde
# está esta señal?), más abajo en este archivo.

class _DialogoSenal(Gtk.Dialog):
    """Editor de una entidad 'senal' (identidad de contenido, ej. 'TELEFE
    SAT'), separada a propósito del formato técnico (ver tipo_formato_senal)
    porque la misma señal puede viajar en más de un formato a lo largo de
    su recorrido."""

    TIPOS_CONTENIDO = ["VIDEO", "AUDIO", "DATOS", "EMBEBIDO"]

    def __init__(self, titulo, nombre="", tipo_contenido="", descripcion="",
                parent=None):
        super().__init__(title=titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(400, 200)

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = Gtk.Entry(text=nombre, activates_default=True,
                                  hexpand=True)
        g.attach(self.e_nombre, 1, 0, 2, 1)

        _lbl_entry(g, _("Tipo de contenido:"), 1)
        self.c_tipo = Gtk.ComboBoxText.new_with_entry()
        for t in self.TIPOS_CONTENIDO:
            self.c_tipo.append_text(t)
        if tipo_contenido:
            self.c_tipo.get_child().set_text(tipo_contenido)
        self.c_tipo.set_hexpand(True)
        g.attach(self.c_tipo, 1, 1, 2, 1)

        _lbl_entry(g, _("Descripción:"), 2)
        self.e_desc = Gtk.Entry(text=descripcion, hexpand=True)
        g.attach(self.e_desc, 1, 2, 2, 1)

        self.get_content_area().add(g)
        self.show_all()

    @property
    def nombre(self):
        return self.e_nombre.get_text().strip()

    @property
    def tipo_contenido(self):
        return self.c_tipo.get_child().get_text().strip()

    @property
    def descripcion(self):
        return self.e_desc.get_text().strip()


class SenalesListado(VentanaListado):
    """Catálogo de señales (identidades de contenido). Doble función:
    ABM del catálogo, y punto de entrada al buscador '¿dónde está esta
    señal?' vía el botón extra agregado en el constructor."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Señales"),
            [_("ID"), _("Nombre"), _("Tipo contenido"), _("Descripción")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                (_("🔎 ¿Dónde está esta señal?"), self._on_buscar_donde),
                (_("🧬 Linaje…"), self._on_linaje),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_senales())

    def nuevo(self):
        dlg = _DialogoSenal(_("Nueva Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.nombre:
            Modelo.agregar_senal(dlg.nombre, dlg.tipo_contenido, dlg.descripcion)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_senal(id_)
        if not rows: return
        r = rows[0]
        dlg = _DialogoSenal(_("Editar Señal"), nombre=s(r[1]),
                            tipo_contenido=s(r[2]), descripcion=s(r[3]),
                            parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificar_senal(id_, dlg.nombre, dlg.tipo_contenido,
                                   dlg.descripcion)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_senal(id_)

    def _on_buscar_donde(self, btn):
        f = self._fila()
        if not f:
            mostrar_error(self, _("Elegí primero una señal de la lista."))
            return
        _mostrar_donde_esta_senal(id_senal=f[0], nombre_senal=f[1], parent=self)

    def _on_linaje(self, btn):
        f = self._fila()
        if not f:
            mostrar_error(self, _("Elegí primero una señal de la lista."))
            return
        _DialogoLinajeSenal(id_senal=f[0], nombre_senal=f[1], parent=self).run_and_destroy()


class TiposFormatoSenalListado(VentanaListado):
    """Catálogo de formatos técnicos de señal (ej. 'SDI 1080i', 'IP
    ST2110'). Separado del catálogo de 'senal' — ver _DialogoSenal."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Formatos de Señal"), [_("ID"), _("Nombre")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_formatos_senal())

    def nuevo(self):
        dlg = DialogoNombre(_("Nuevo Formato de Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.agregar_tipo_formato_senal(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        formatos = {s(r[0]): s(r[1]) for r in Modelo.devolver_formatos_senal()}
        if id_ not in formatos: return
        dlg = DialogoNombre(_("Editar Formato de Señal"),
                            valor=formatos[id_], parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificar_tipo_formato_senal(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_tipo_formato_senal(id_)


def _mostrar_donde_esta_senal(id_senal, nombre_senal, parent=None):
    """Ventana de solo lectura con todos los conectores (y su equipo) que
    hoy tienen cargada la señal id_senal. Ver Modelo.buscar_conectores_por_senal."""
    filas = Modelo.buscar_conectores_por_senal(id_senal)
    dlg = Gtk.Dialog(
        title=_("¿Dónde está \"{}\"?").format(nombre_senal),
        transient_for=parent, modal=True, destroy_with_parent=True,
    )
    dlg.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
    dlg.set_default_size(640, 420)

    area = dlg.get_content_area()
    area.set_spacing(6)

    hb_top = Gtk.Box(spacing=6, margin_start=10, margin_end=10, margin_top=6)
    btn_linaje = Gtk.Button(label="🧬 " + _("Ver / editar linaje…"))
    btn_linaje.connect(
        "clicked",
        lambda b: _DialogoLinajeSenal(
            id_senal=id_senal, nombre_senal=nombre_senal, parent=dlg
        ).run_and_destroy())
    hb_top.pack_start(btn_linaje, False, False, 0)
    area.pack_start(hb_top, False, False, 0)

    if not filas:
        lbl = Gtk.Label(
            label=_("Esta señal todavía no está cargada en ningún conector."))
        lbl.set_margin_start(16); lbl.set_margin_end(16)
        lbl.set_margin_top(16); lbl.set_margin_bottom(16)
        area.add(lbl)
    else:
        cols = [_("Equipo"), _("Conector"), _("Formato"), _("Origen")]
        store = Gtk.ListStore(str, str, str, str)
        for id_conector, nombre_conector, id_equipo, nombre_equipo, \
                nombre_formato, origen in filas:
            store.append([
                s(nombre_equipo) or f"(equipo #{s(id_equipo)})",
                s(nombre_conector),
                s(nombre_formato) or "—",
                s(origen),
            ])
        tv = Gtk.TreeView(model=store)
        for i, titulo_col in enumerate(cols):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

    dlg.show_all()
    dlg.run()
    dlg.destroy()


def abrir_buscador_senal(parent=None):
    """Punto de entrada del menú 'Diagramas → 🔎 Buscador de señal…': pide
    elegir una señal del catálogo y muestra dónde está cargada hoy."""
    sel = SenalesListado(parent=parent, modo_seleccion=True)
    if sel.run() == Gtk.ResponseType.OK:
        id_senal = sel.resultado_id
        nombre_senal = sel.resultado_nombre
        sel.destroy()
        _mostrar_donde_esta_senal(id_senal, nombre_senal, parent=parent)
    else:
        sel.destroy()


# ── Linaje de señal (plan_estado_senal_y_linaje.md, Función 2) ─────────────

class _DialogoLinajeSenal(Gtk.Dialog):
    """
    Editor de linaje de UNA señal: de qué otra(s) señal(es) deriva
    (padres). No edita hijos acá — para ver/editar el linaje completo
    hacia abajo hay que abrir el diálogo de linaje de la señal hija
    correspondiente (cada señal edita sus propios padres, nunca los
    padres de otra) — es más simple de razonar que un editor bidireccional
    y evita el caso raro de "edito A pero desde la ficha de B".

    Fila = (activo: bool, id_padre: str, nombre_padre: str, nota: str).
    Se precarga con la UNIÓN de:
      - los padres ya guardados (Modelo.devolver_padres_de_senal) — activos
      - los padres SUGERIDOS automáticamente (Modelo.sugerir_padres_de_senal)
        que todavía no estén guardados — también activos, para que el caso
        común (aceptar la sugerencia tal cual) sea "abrir → Aceptar" y nada
        más; el usuario destilda lo que no quiere.
    Al aceptar: guarda (agregar_linaje, que hace upsert) todo lo tildado
    y borra (quitar_linaje) lo que estaba guardado y quedó destildado.
    Antes de guardar un vínculo nuevo corre hay_ciclo_linaje(); si
    cerraría un ciclo, avisa y NO guarda esa fila puntual (no aborta el
    resto del guardado).
    """

    COL_ACTIVO, COL_ID_PADRE, COL_NOMBRE, COL_NOTA = range(4)

    def __init__(self, id_senal, nombre_senal, parent=None):
        super().__init__(title=f"🧬 {_('Linaje de')}: {nombre_senal}",
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(520, 460)
        self.id_senal = str(id_senal)
        self.nombre_senal = nombre_senal
        self._ids_guardados_al_abrir = set()   # para saber qué se destildó

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(10); area.set_margin_end(10)
        area.set_margin_top(8);   area.set_margin_bottom(8)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(_(
            "<b>¿De qué señal(es) deriva «{n}»?</b>\n"
            "<small>Tildadas: se guardan. Doble clic en la nota para "
            "editarla.</small>").format(n=GLib.markup_escape_text(nombre_senal)))
        lbl.set_line_wrap(True)
        area.pack_start(lbl, False, False, 0)

        self._store = Gtk.ListStore(bool, str, str, str)
        self._tv = Gtk.TreeView(model=self._store, headers_visible=True)

        rend_chk = Gtk.CellRendererToggle()
        rend_chk.connect("toggled", self._on_toggle)
        col_chk = Gtk.TreeViewColumn("", rend_chk, active=self.COL_ACTIVO)
        self._tv.append_column(col_chk)

        col_nom = Gtk.TreeViewColumn(
            _("Señal padre"), Gtk.CellRendererText(xpad=4),
            text=self.COL_NOMBRE)
        col_nom.set_expand(True); col_nom.set_resizable(True)
        self._tv.append_column(col_nom)

        rend_nota = Gtk.CellRendererText(xpad=4, editable=True)
        rend_nota.connect("edited", self._on_nota_editada)
        col_nota = Gtk.TreeViewColumn(
            _("Nota (opcional)"), rend_nota, text=self.COL_NOTA)
        col_nota.set_expand(True); col_nota.set_resizable(True)
        self._tv.append_column(col_nota)

        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        hb = Gtk.Box(spacing=6)
        btn_sugerir = Gtk.Button(label="🔄 " + _("Volver a sugerir"))
        btn_sugerir.set_tooltip_text(_(
            "Vuelve a mirar las entradas del equipo por si el cableado "
            "cambió desde que se abrió este diálogo. No borra lo que ya "
            "esté tildado a mano."))
        btn_sugerir.connect("clicked", lambda b: self._cargar(resugerir=True))
        hb.pack_start(btn_sugerir, False, False, 0)

        btn_agregar = Gtk.Button(label="➕ " + _("Agregar señal…"))
        btn_agregar.set_tooltip_text(_(
            "Buscar cualquier señal del catálogo y agregarla como padre "
            "manualmente, aunque no haya sido sugerida."))
        btn_agregar.connect("clicked", self._on_agregar_manual)
        hb.pack_start(btn_agregar, False, False, 0)

        btn_arbol = Gtk.Button(label="🌳 " + _("Ver árbol de linaje"))
        btn_arbol.connect("clicked", self._on_ver_arbol)
        hb.pack_start(btn_arbol, False, False, 0)
        area.pack_start(hb, False, False, 0)

        self._cargar(resugerir=False)
        self.show_all()

    # ── Carga ────────────────────────────────────────────────────────────
    def _cargar(self, resugerir: bool) -> None:
        """resugerir=False: carga inicial (guardados + sugeridos, ambos
        activos). resugerir=True: sólo AGREGA sugerencias nuevas que
        todavía no estén en la lista — no toca lo que el usuario ya
        tildó/destildó/editó a mano."""
        ids_en_store = {r[self.COL_ID_PADRE] for r in self._store}

        if not resugerir:
            self._store.clear()
            ids_en_store = set()
            guardados = Modelo.devolver_padres_de_senal(self.id_senal)
            self._ids_guardados_al_abrir = {str(r[1]) for r in guardados}
            for _id_lin, id_padre, nombre_padre, nota in guardados:
                self._store.append([True, str(id_padre), nombre_padre, nota or ""])
                ids_en_store.add(str(id_padre))

        try:
            sugeridos = Modelo.sugerir_padres_de_senal(self.id_senal)
        except Exception:
            sugeridos = []
        agregados = 0
        for id_padre, nombre_padre in sugeridos:
            id_padre = str(id_padre)
            if id_padre in ids_en_store or id_padre == self.id_senal:
                continue
            self._store.append([True, id_padre, nombre_padre, ""])
            ids_en_store.add(id_padre)
            agregados += 1

        if resugerir and agregados == 0:
            mostrar_info(self, _(
                "No se encontraron sugerencias nuevas (mirando las "
                "entradas del equipo donde esta señal está cargada a "
                "mano)."))

    def _on_toggle(self, cell, path):
        self._store[path][self.COL_ACTIVO] = not self._store[path][self.COL_ACTIVO]

    def _on_nota_editada(self, cell, path, texto_nuevo):
        self._store[path][self.COL_NOTA] = texto_nuevo

    def _on_agregar_manual(self, btn):
        dlg = SenalesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_sel = str(dlg.resultado_id)
            nombre_sel = dlg.resultado_nombre
            if id_sel == self.id_senal:
                mostrar_error(self, _("Una señal no puede ser padre de sí misma."))
            elif any(r[self.COL_ID_PADRE] == id_sel for r in self._store):
                mostrar_info(self, _("Esa señal ya está en la lista."))
            else:
                self._store.append([True, id_sel, nombre_sel, ""])
        dlg.destroy()

    def _on_ver_arbol(self, btn):
        dlg = _ArbolLinajeSenal(self.id_senal, self.nombre_senal, parent=self)
        dlg.run(); dlg.destroy()

    # ── Guardado ─────────────────────────────────────────────────────────
    def run_and_destroy(self) -> bool:
        """Devuelve True si se guardó algo (para que el llamador pueda
        refrescar su propia vista si hace falta)."""
        resp = self.run()
        guardo = False
        if resp == Gtk.ResponseType.OK:
            guardo = self._guardar()
        self.destroy()
        return guardo

    def _guardar(self) -> bool:
        tildados = {}
        for activo, id_padre, _nombre, nota in self._store:
            if activo:
                tildados[id_padre] = nota

        ciclos_bloqueados = []
        for id_padre, nota in tildados.items():
            es_nuevo = id_padre not in self._ids_guardados_al_abrir
            if es_nuevo and Modelo.hay_ciclo_linaje(self.id_senal, id_padre):
                ciclos_bloqueados.append(id_padre)
                continue
            Modelo.agregar_linaje(self.id_senal, id_padre, nota or None)

        # Lo que estaba guardado y quedó destildado (o se bloqueó por
        # ciclo, que no debería pasar nunca porque ya estaba guardado
        # antes sin ciclo — pero por las dudas no se toca acá) se borra.
        for id_padre in self._ids_guardados_al_abrir - set(tildados.keys()):
            padres_actuales = Modelo.devolver_padres_de_senal(self.id_senal)
            for id_lin, id_p, _n, _nota in padres_actuales:
                if str(id_p) == id_padre:
                    Modelo.quitar_linaje(id_lin)

        if ciclos_bloqueados:
            nombres = ", ".join(
                r[self.COL_NOMBRE] for r in self._store
                if r[self.COL_ID_PADRE] in ciclos_bloqueados)
            mostrar_error(self, _(
                "No se guardó el vínculo con: {n}\n"
                "Convertirla en padre cerraría un ciclo (esa señal ya es, "
                "directa o indirectamente, descendiente de «{h}»)."
            ).format(n=nombres, h=self.nombre_senal))

        return True


class _ArbolLinajeSenal(Gtk.Dialog):
    """
    Árbol de solo lectura, lazy-load (mismo patrón que
    pantallas_avanzadas.ArbolConexionesEquipo): raíz = la señal actual,
    con dos ramas expandibles — "⬆ Deriva de" (padres, recursivo hacia
    arriba) y "⬇ Usada en" (hijos, recursivo hacia abajo). Vista gráfica
    queda fuera de esta entrega (plan, sección 3.6) — esto es sólo texto.
    """

    COL_TEXTO, COL_KEY, COL_TIPO, COL_COLOR, COL_WEIGHT, COL_ITALIC = range(6)

    def __init__(self, id_senal, nombre_senal, parent=None):
        super().__init__(title="🧬 " + _("Árbol de linaje: {n}").format(n=nombre_senal),
                         transient_for=parent, destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(520, 560)

        area = self.get_content_area()
        self._store = Gtk.TreeStore(str, str, str, str, int, int)
        self._tv = Gtk.TreeView(model=self._store, headers_visible=False)
        self._tv.set_enable_tree_lines(True)
        rend = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(
            "", rend, text=self.COL_TEXTO, foreground=self.COL_COLOR,
            weight=self.COL_WEIGHT, style=self.COL_ITALIC)
        self._tv.append_column(col)
        self._tv.connect("row-expanded", self._on_expandido)

        sw = Gtk.ScrolledWindow(vexpand=True, margin_start=8, margin_end=8,
                                margin_top=8, margin_bottom=8)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        id_senal = str(id_senal)
        it_raiz = self._store.append(None, [
            f"📡  {nombre_senal}", id_senal, "raiz", "#0a3a6e", 700, 0])

        it_padres = self._store.append(it_raiz, [
            "⬆  " + _("Deriva de…"), "", "grupo_padres", "#8a6a1a", 600, 0])
        self._poblar_nivel(it_padres, Modelo.devolver_padres_de_senal(id_senal),
                           tipo_hijo="senal_padre")

        it_hijos = self._store.append(it_raiz, [
            "⬇  " + _("Usada en…"), "", "grupo_hijos", "#1a6a4a", 600, 0])
        self._poblar_nivel(it_hijos, Modelo.devolver_hijos_de_senal(id_senal),
                           tipo_hijo="senal_hijo")

        path_raiz = self._store.get_path(it_raiz)
        self._tv.expand_row(path_raiz, False)
        self.show_all()

    def _poblar_nivel(self, it_padre, filas, tipo_hijo) -> None:
        if not filas:
            self._store.append(it_padre, [
                "(" + _("ninguna") + ")", "", "vacio", "#888888", 300, 2])
            return
        for _id_lin, id_rel, nombre_rel, nota in filas:
            texto = f"📡  {nombre_rel}"
            if nota:
                texto += f"   —  {nota}"
            it = self._store.append(it_padre, [
                texto, str(id_rel), tipo_hijo, "#1a1a1a", 400, 0])
            # placeholder para poder seguir expandiendo, salvo que esta
            # misma señal ya sea la raíz (evita un loop de un solo paso
            # si alguien la agregó como su propio padre/hijo por error
            # antes de que existiera hay_ciclo_linaje)
            self._store.append(it, ["…", "", "dummy", "#bbbbbb", 300, 2])

    def _on_expandido(self, tv, it, path) -> None:
        tipo = self._store.get_value(it, self.COL_TIPO)
        key  = self._store.get_value(it, self.COL_KEY)
        if tipo not in ("senal_padre", "senal_hijo") or not key:
            return
        it_ch = self._store.iter_children(it)
        if it_ch and self._store.get_value(it_ch, self.COL_TIPO) != "dummy":
            return   # ya se expandió antes, no recargar
        while it_ch:
            self._store.remove(it_ch)
            it_ch = self._store.iter_children(it)
        if tipo == "senal_padre":
            filas = Modelo.devolver_padres_de_senal(key)
        else:
            filas = Modelo.devolver_hijos_de_senal(key)
        self._poblar_nivel(it, filas, tipo_hijo=tipo)


def _mostrar_lista_simple(titulo, encabezado, filas, parent=None):
    """Ventana de solo lectura genérica: una fila de texto por elemento.
    Usada para los sub-reportes de la revisión de propagación (conflictos,
    equipos ambiguos, enrutadores sin matriz) — no necesitan columnas,
    sólo una lista legible."""
    dlg = Gtk.Dialog(title=titulo, transient_for=parent, modal=True,
                     destroy_with_parent=True)
    dlg.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
    dlg.set_default_size(520, 380)
    area = dlg.get_content_area()
    area.set_spacing(6)

    lbl = Gtk.Label(label=encabezado, xalign=0, wrap=True)
    lbl.set_margin_start(10); lbl.set_margin_end(10); lbl.set_margin_top(10)
    area.add(lbl)

    store = Gtk.ListStore(str)
    for f in filas:
        store.append([f])
    tv = Gtk.TreeView(model=store, headers_visible=False)
    tv.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=6), text=0))
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_vexpand(True)
    sw.add(tv)
    area.pack_start(sw, True, True, 0)

    dlg.show_all()
    dlg.run()
    dlg.destroy()


class _DialogoPropagacionSenal(Gtk.Dialog):
    """Fase 3 de plan_entidad_senal.md — revisión del motor de propagación
    (senal_propagation.PropagadorSenal) en modo 'sugerencia': calcula todo
    en memoria, el usuario elige qué aceptar, y sólo entonces se escribe
    en senal_en_conector (Modelo.aplicar_propagacion_senal). Nunca pisa
    una carga MANUAL — ver comentarios en ambos módulos."""

    def __init__(self, parent=None):
        super().__init__(title=_("Propagación de señal — revisión"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aplicar seleccionadas"), Gtk.ResponseType.OK)
        self.set_default_size(720, 520)
        self.resultado = None
        self._filas_por_conector = {}

        area = self.get_content_area()
        area.set_spacing(6)

        self.lbl_resumen = Gtk.Label(xalign=0, wrap=True)
        self.lbl_resumen.set_margin_start(10); self.lbl_resumen.set_margin_top(10)
        area.add(self.lbl_resumen)

        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.set_margin_start(10); barra.set_margin_end(10)
        btn_todo = Gtk.Button(label=_("Marcar todo"))
        btn_todo.connect("clicked", lambda b: self._marcar_todo(True))
        btn_ninguno = Gtk.Button(label=_("Desmarcar todo"))
        btn_ninguno.connect("clicked", lambda b: self._marcar_todo(False))
        self.btn_conflictos = Gtk.Button(label=_("⚠ Ver conflictos"))
        self.btn_conflictos.connect("clicked", self._ver_conflictos)
        self.btn_ambiguos = Gtk.Button(label=_("⚠ Ver equipos ambiguos"))
        self.btn_ambiguos.connect("clicked", self._ver_ambiguos)
        for b in (btn_todo, btn_ninguno, self.btn_conflictos, self.btn_ambiguos):
            barra.pack_start(b, False, False, 0)
        area.pack_start(barra, False, False, 0)

        self.store = Gtk.ListStore(bool, str, str, str, str, str)
        # cols: aplicar?, equipo, conector, señal, formato, id_conector(oculta)
        tv = Gtk.TreeView(model=self.store)
        rend_toggle = Gtk.CellRendererToggle()
        rend_toggle.connect("toggled", self._on_toggle)
        tv.append_column(Gtk.TreeViewColumn(_("Aplicar"), rend_toggle, active=0))
        for i, titulo in enumerate(
                [_("Equipo"), _("Conector"), _("Señal propuesta"), _("Formato")], start=1):
            col = Gtk.TreeViewColumn(titulo, Gtk.CellRendererText(xpad=4), text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

        self.show_all()
        self._calcular()

    def _calcular(self):
        from senal_propagation import PropagadorSenal
        prop = PropagadorSenal(DB_PATH)
        self.resultado = prop.calcular()
        r = self.resultado

        partes = [
            _("{} conectores con señal propuesta para aplicar.")
              .format(len(r.propagadas)),
        ]
        if r.conflictos:
            partes.append(
                _("⚠ {} conectores con señales en conflicto (no se pueden "
                  "aplicar automáticamente, requieren revisión manual).")
                  .format(len(r.conflictos)))
        if r.equipos_distribuidor_ambiguo:
            partes.append(
                _("⚠ {} equipos no se pudieron propagar automáticamente: "
                  "jacks de patchera cuyos 4 conectores no siguen el "
                  "patrón de nombre esperado (A_BACK/B_BACK/A_FRONT/"
                  "B_FRONT — revisar tipeo), u otros equipos marcados "
                  "distribuidor con más de una entrada real.")
                  .format(len(r.equipos_distribuidor_ambiguo)))
        if r.equipos_enrutador_sin_matriz:
            partes.append(
                _("⚠ {} equipos enrutador no tienen matriz de ruteo "
                  "guardada, no se pudo propagar a través de ellos.")
                  .format(len(r.equipos_enrutador_sin_matriz)))
        if not r.convergio:
            partes.append(
                _("⚠ El cálculo no terminó de estabilizar (posible ciclo "
                  "de ruteo) — los resultados pueden ser parciales."))
        self.lbl_resumen.set_text("\n".join(partes))

        self.btn_conflictos.set_sensitive(bool(r.conflictos))
        self.btn_ambiguos.set_sensitive(
            bool(r.equipos_distribuidor_ambiguo or r.equipos_enrutador_sin_matriz))

        self.store.clear()
        self._filas_por_conector = {}
        for p in sorted(r.propagadas,
                        key=lambda p: (p.nombre_equipo or "", p.nombre_conector or "")):
            it = self.store.append([
                True, s(p.nombre_equipo), s(p.nombre_conector),
                s(p.nombre_senal), s(p.nombre_formato) or "—", p.id_conector,
            ])
            self._filas_por_conector[p.id_conector] = it

    def _on_toggle(self, cell, path):
        it = self.store.get_iter(path)
        self.store.set_value(it, 0, not self.store.get_value(it, 0))

    def _marcar_todo(self, valor):
        for row in self.store:
            row[0] = valor

    def _ver_conflictos(self, btn):
        filas = [
            "{} — {} (equipo: {})".format(
                s(p.nombre_conector), _("señales distintas llegan por rutas distintas"),
                s(p.nombre_equipo))
            for p in self.resultado.conflictos
        ]
        _mostrar_lista_simple(
            _("Conflictos detectados"),
            _("Estos conectores reciben más de una señal candidata por "
              "rutas distintas del grafo. No se tocan automáticamente — "
              "revisá el cableado o cargá la señal correcta a mano."),
            filas, parent=self)

    def _ver_ambiguos(self, btn):
        filas = []
        for eid in self.resultado.equipos_distribuidor_ambiguo:
            filas.append(_("Equipo #{} — patchera con nombres de conector "
                           "que no calzan con A_BACK/B_BACK/A_FRONT/"
                           "B_FRONT (revisar tipeo), u otro equipo "
                           "DISTRIBUIDOR con más de una entrada real.")
                         .format(eid))
        for eid in self.resultado.equipos_enrutador_sin_matriz:
            filas.append(_("Equipo #{} — rol ENRUTADOR sin matriz de "
                           "ruteo guardada.").format(eid))
        _mostrar_lista_simple(
            _("Equipos sin propagar"),
            _("Estos equipos no propagaron señal a través suyo por no "
              "poder determinar una correspondencia entrada→salida "
              "confiable. Si alguno es en realidad un amplificador de "
              "distribución simple, revisá que tenga una sola entrada; "
              "si es una patchera o un pasante, es esperable que quede "
              "acá."),
            filas, parent=self)

    def run_and_aplicar(self):
        """Corre el diálogo; si el usuario confirma, aplica las filas
        tildadas y devuelve la cantidad de conectores escritos (None si
        se canceló)."""
        resp = self.run()
        if resp != Gtk.ResponseType.OK:
            self.destroy()
            return None
        aceptadas = []
        by_id = {p.id_conector: p for p in self.resultado.propagadas}
        for row in self.store:
            if row[0]:
                id_conector = row[5]
                p = by_id.get(id_conector)
                if p:
                    aceptadas.append(p)
        escritas = Modelo.aplicar_propagacion_senal(aceptadas)
        self.destroy()
        return escritas


def abrir_propagacion_senal(parent=None):
    """Punto de entrada del menú 'Diagramas → 🔮 Calcular propagación de
    señal…'."""
    try:
        from senal_propagation import PropagadorSenal  # noqa: F401 (chequeo de import)
    except Exception as e:
        mostrar_error(parent, f"{_('Motor de propagación no disponible')}:\n{e}")
        return
    dlg = _DialogoPropagacionSenal(parent=parent)
    escritas = dlg.run_and_aplicar()
    if escritas is not None:
        info = Gtk.MessageDialog(
            transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("Se aplicaron {} señales propagadas.").format(escritas),
        )
        info.run()
        info.destroy()


class _DialogoReportesSenal(Gtk.Dialog):
    """Fase 6 de plan_entidad_senal.md — reportes de señal. Tres pestañas,
    cada una con su propia consulta en Modelo (reporte_formatos_en_uso,
    reporte_senales_sin_usar, reporte_senales_propagadas_sin_origen).
    Todo de solo lectura; no modifica nada."""

    def __init__(self, parent=None):
        super().__init__(title=_("📡 Reportes de señal"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(620, 460)

        nb = Gtk.Notebook()
        nb.append_page(self._tab_formatos(), Gtk.Label(label=_("Formatos en uso")))
        nb.append_page(self._tab_sin_usar(), Gtk.Label(label=_("Señales sin usar")))
        nb.append_page(self._tab_sin_origen(), Gtk.Label(label=_("Propagadas sin origen")))
        self.get_content_area().pack_start(nb, True, True, 0)
        self.show_all()

    def _tabla_simple(self, encabezados, filas):
        store = Gtk.ListStore(*([str] * len(encabezados)))
        for f in filas:
            store.append([s(v) for v in f])
        tv = Gtk.TreeView(model=store)
        for i, tit in enumerate(encabezados):
            col = Gtk.TreeViewColumn(tit, Gtk.CellRendererText(xpad=4), text=i)
            col.set_resizable(True)
            col.set_expand(True)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.add(tv)
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caja.set_margin_start(8); caja.set_margin_end(8)
        caja.set_margin_top(8); caja.set_margin_bottom(8)
        caja.pack_start(sw, True, True, 0)
        return caja

    def _con_encabezado(self, texto, widget):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl = Gtk.Label(label=texto, xalign=0, wrap=True)
        lbl.set_margin_start(8); lbl.set_margin_end(8); lbl.set_margin_top(8)
        caja.pack_start(lbl, False, False, 0)
        caja.pack_start(widget, True, True, 0)
        return caja

    def _tab_formatos(self):
        filas = Modelo.reporte_formatos_en_uso()
        tabla = self._tabla_simple(
            [_("Formato"), _("Conectores"), _("Señales distintas")], filas)
        return self._con_encabezado(
            _("Cuántos conectores y señales distintas usan cada formato "
              "técnico hoy — útil para ver, por ejemplo, cuánto SDI legacy "
              "queda frente a IP y planificar una migración."),
            tabla)

    def _tab_sin_usar(self):
        filas = Modelo.reporte_senales_sin_usar()
        tabla = self._tabla_simple(
            [_("Señal"), _("Tipo de contenido")],
            [(f[1], f[2]) for f in filas])
        return self._con_encabezado(
            _("Señales del catálogo que todavía no están cargadas en "
              "ningún conector (ni manual ni propagada) — dadas de alta "
              "pero nunca asignadas."),
            tabla)

    def _tab_sin_origen(self):
        filas = Modelo.reporte_senales_propagadas_sin_origen()
        tabla = self._tabla_simple([_("Señal")], [(f[1],) for f in filas])
        return self._con_encabezado(
            _("⚠ Señales con al menos un conector PROPAGADA pero sin "
              "ninguna carga MANUAL viva que las sostenga — normalmente "
              "pasa cuando se borró o cambió la fuente manual después de "
              "aplicar una propagación. Revisar: volver a cargar la "
              "fuente y recalcular, o quitar la señal de esos conectores."),
            tabla)


def abrir_reportes_senal(parent=None):
    """Punto de entrada del menú 'Catálogos → 📡 Reportes de señal…'."""
    dlg = _DialogoReportesSenal(parent=parent)
    dlg.run()
    dlg.destroy()


def abrir_limpiar_senales_propagadas(parent=None):
    """Punto de entrada del menú 'Diagramas → 📡🧹 Borrar señales
    propagadas…'. Borra en bloque todas las asignaciones de señal con
    origen='PROPAGADA' (deja esos conectores sin señal asignada), sin
    tocar ninguna carga MANUAL. Pide confirmación mostrando primero la
    cantidad de conectores afectados."""
    n = Modelo.contar_senales_propagadas()
    if n == 0:
        info = Gtk.MessageDialog(
            transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=_("No hay señales propagadas cargadas actualmente."),
        )
        info.run()
        info.destroy()
        return

    confirmar = Gtk.MessageDialog(
        transient_for=parent, modal=True, message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text=_("¿Borrar todas las señales propagadas?"),
    )
    confirmar.format_secondary_text(
        _("Se van a quitar {} asignaciones de señal con origen "
          "PROPAGADA (el conector queda sin señal asignada). Las cargas "
          "MANUAL no se tocan. Esta acción no se puede deshacer.").format(n)
    )
    resp = confirmar.run()
    confirmar.destroy()
    if resp != Gtk.ResponseType.YES:
        return

    borradas = Modelo.limpiar_senales_propagadas()
    info = Gtk.MessageDialog(
        transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=_("Se borraron {} señales propagadas.").format(borradas),
    )
    info.run()
    info.destroy()


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


# ─── Conectores ───────────────────────────────────────────────────────────────

class ConectoresListado(VentanaListado):
    def __init__(self, id_equipo, parent=None, modo_seleccion=False):
        super().__init__(_("Conectores"), [_("ID"), _("Nombre"), _("Tipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.id_equipo = id_equipo
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_conectores_de_equipo(self.id_equipo))

    def nuevo(self):
        dlg = _DialogoConector(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConector(id_conector=id_, id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conector(id_)


class _DialogoConector(Gtk.Dialog):
    def __init__(self, id_conector=None, id_equipo=None, parent=None):
        titulo = _("Editar Conector") if id_conector is not None else _("Nuevo Conector")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(420, 280)
        self.id_conector = id_conector
        self.id_equipo = id_equipo or ""
        self.id_tipo_conector = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Tipo conector:"), 1)
        self.c_tipo = _searchable_combo(g, 1, Modelo.devolver_tipos_conectores())
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)

        self.get_content_area().add(g)

        # Botón selector de coordenadas en imagen
        btn_coords = Gtk.Button(label="📍 " + _("Elegir coords en imagen"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_conector is not None:
            rows = Modelo.devolver_conector(id_conector)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_tipo_conector = s(r[3])
                _set_combo_id(self.c_tipo, self.id_tipo_conector)
                self.id_equipo = s(r[4])
                self.e_x.set_text(s(r[5]))
                self.e_y.set_text(s(r[6]))
                self.id_imagen = s(r[7])
                self.e_imagen.set_text(s(r[8]))

        # ── Señal (Fase 2 de plan_entidad_senal.md) ──
        # Sólo tiene sentido con el conector ya guardado (senal_en_conector
        # referencia id_conector). Un conector nuevo no la muestra todavía;
        # se asigna reabriendo la ficha una vez creado.
        self.c_senal = None
        self.c_formato = None
        if id_conector is not None:
            frame_senal = Gtk.Frame(label=" " + _("Señal") + " ")
            g2 = _grid()
            _lbl_entry(g2, _("Señal:"), 0)
            self.c_senal = _searchable_combo(
                g2, 0, Modelo.devolver_senales(), "+", self._agregar_senal_rapida)
            _lbl_entry(g2, _("Formato:"), 1)
            self.c_formato = _searchable_combo(
                g2, 1, Modelo.devolver_formatos_senal(), "+",
                self._agregar_formato_rapida)
            frame_senal.add(g2)
            self.get_content_area().pack_start(frame_senal, False, False, 6)

            btn_quitar_senal = Gtk.Button(
                label=_("🗑 Quitar señal de este conector"))
            btn_quitar_senal.connect("clicked", self._quitar_senal)
            self.get_content_area().pack_start(btn_quitar_senal, False, False, 0)

            actual = Modelo.devolver_senal_en_conector(id_conector)
            if actual:
                id_senal_act, _n_senal, id_formato_act, _n_formato, _origen = actual[0]
                _set_combo_id(self.c_senal, id_senal_act)
                if id_formato_act:
                    _set_combo_id(self.c_formato, id_formato_act)

        # ── Función de patchera (Fase B de plan_desarrollo_funcion_
        # patchera.md) ──
        # Hasta ahora esto SÓLO se podía cargar en el editor del molde de
        # catálogo (_DialogoConectorCatalogo) — un equipo real ya dado de
        # alta (ej. un patch module de audio con conectores "01_BACK"/
        # "25_BACK" que no siguen la convención A_BACK/B_BACK) no tenía
        # forma de asignarle la función sin editar la base a mano. Mismo
        # criterio que la sección de Señal: sólo tiene sentido con el
        # conector ya guardado, y sólo se muestra si el EQUIPO es de
        # rol_senal PATCHERA (no tiene sentido en cualquier otro tipo).
        self.c_funcion_patchera = None
        if id_conector is not None and self.id_equipo:
            fila_rol = Modelo._query(
                "SELECT te.rol_senal FROM equipo e "
                "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
                "WHERE e.id_equipo=?", (self.id_equipo,))
            es_patchera = bool(fila_rol and fila_rol[0][0] == "PATCHERA")
            if es_patchera:
                frame_pat = Gtk.Frame(label=" " + _("Función de patchera") + " ")
                g3 = _grid()
                _lbl_entry(g3, _("Función:"), 0)
                self.c_funcion_patchera = Gtk.ComboBoxText()
                self.c_funcion_patchera.append("", _("(ninguna)"))
                for f in Modelo.funciones_patchera():
                    self.c_funcion_patchera.append(f["id"], f["nombre_es"])
                g3.attach(self.c_funcion_patchera, 1, 0, 2, 1)
                frame_pat.add(g3)
                self.get_content_area().pack_start(frame_pat, False, False, 6)

                fila_fn = Modelo._query(
                    "SELECT id_funcion_patchera FROM conector WHERE id_conector=?",
                    (id_conector,))
                if fila_fn and fila_fn[0][0]:
                    self.c_funcion_patchera.set_active_id(s(fila_fn[0][0]))

        # ── Formato eléctrico (plan_riesgo_senal_audio.md, riesgo #3) ──
        # Mismo criterio que Señal/Función de patchera: sólo tiene sentido
        # con el conector ya guardado. id_tipo_ficha declara qué ficha es
        # eléctricamente este jack (de ahí sale el default de n_conductores/
        # modo_balance/modo_canal); modo_balance/modo_canal acá son el
        # OVERRIDE puntual (vacío = usar el default de la ficha) — necesario
        # para fichas ambiguas como TRS (sección 4.1 del plan).
        self.c_ficha_riesgo = None
        self.c_modo_balance = None
        self.c_modo_canal = None
        if id_conector is not None:
            frame_riesgo = Gtk.Frame(label=" " + _("Formato eléctrico (riesgo de señal)") + " ")
            g4 = _grid()
            _lbl_entry(g4, _("Ficha (qué es eléctricamente):"), 0)
            self.c_ficha_riesgo = _searchable_combo(
                g4, 0, Modelo.devolver_todos_los_tipos_ficha())
            _lbl_entry(g4, _("Balance (override):"), 1)
            self.c_modo_balance = Gtk.ComboBoxText()
            for m in ("", "BALANCEADO", "DESBALANCEADO", "NA"):
                self.c_modo_balance.append_text(m if m else _("(usar default de la ficha)"))
            g4.attach(self.c_modo_balance, 1, 1, 2, 1)
            _lbl_entry(g4, _("Canal (override):"), 2)
            self.c_modo_canal = Gtk.ComboBoxText()
            for m in ("", "MONO", "ESTEREO", "NA"):
                self.c_modo_canal.append_text(m if m else _("(usar default de la ficha)"))
            g4.attach(self.c_modo_canal, 1, 2, 2, 1)
            frame_riesgo.add(g4)
            self.get_content_area().pack_start(frame_riesgo, False, False, 6)

            formato_actual = Modelo.devolver_formato_conector(id_conector)
            if formato_actual:
                id_tf_act, mbal_act, mcan_act = formato_actual
                if id_tf_act:
                    _set_combo_id(self.c_ficha_riesgo, id_tf_act)
                self.c_modo_balance.set_active(
                    ("", "BALANCEADO", "DESBALANCEADO", "NA").index(mbal_act)
                    if mbal_act in ("BALANCEADO", "DESBALANCEADO", "NA") else 0)
                self.c_modo_canal.set_active(
                    ("", "MONO", "ESTEREO", "NA").index(mcan_act)
                    if mcan_act in ("MONO", "ESTEREO", "NA") else 0)
            else:
                self.c_modo_balance.set_active(0)
                self.c_modo_canal.set_active(0)

        # ── Armado (plan_bitacora_incidentes_riesgo_analogico.md §3.3) ──
        # Independiente del "Formato eléctrico" de arriba: un conector puede
        # ser balanceado por diseño (ej. XLR) y estar igual mal soldado —
        # es la distinción que motivó el caso real del jack TS cableado
        # como si fuera XLR balanceado.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_conector is not None:
            Modelo.asegurar_tablas_bitacora()
            frame_armado = Gtk.Frame(label=" " + _("Armado") + " ")
            g5 = _grid()
            _lbl_entry(g5, _("¿Armado correcto?:"), 0)
            self.c_armado = Gtk.ComboBoxText()
            self.c_armado.append("", _("No verificado"))
            self.c_armado.append("1", _("Correcto"))
            self.c_armado.append("0", _("Mal armado"))
            g5.attach(self.c_armado, 1, 0, 2, 1)
            _lbl_entry(g5, _("Detalle:"), 1)
            self.e_detalle_armado = _entry(g5, 1)
            frame_armado.add(g5)
            self.get_content_area().pack_start(frame_armado, False, False, 6)

            filas_arm = Modelo._query(
                "SELECT es_armado_correcto, detalle_armado FROM conector "
                "WHERE id_conector=?", (id_conector,))
            if filas_arm and filas_arm[0][0] is not None:
                self.c_armado.set_active_id(str(int(filas_arm[0][0])))
            else:
                self.c_armado.set_active_id("")
            if filas_arm and filas_arm[0][1]:
                self.e_detalle_armado.set_text(s(filas_arm[0][1]))

        _pack_ultima_edicion(self, "conector", "id_conector", id_conector)
        self.show_all()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _agregar_senal_rapida(self, btn):
        """Botón '+' junto al combo de señal: alta rápida sin salir de la
        ficha del conector."""
        dlg = _DialogoSenal(_("Nueva Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.nombre:
            id_nuevo = Modelo.agregar_senal(
                dlg.nombre, dlg.tipo_contenido, dlg.descripcion)
            _repopulate_combo(self.c_senal, Modelo.devolver_senales())
            _set_combo_id(self.c_senal, id_nuevo)
        dlg.destroy()

    def _agregar_formato_rapida(self, btn):
        dlg = DialogoNombre(_("Nuevo Formato de Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            id_nuevo = Modelo.agregar_tipo_formato_senal(dlg.valor)
            _repopulate_combo(self.c_formato, Modelo.devolver_formatos_senal())
            _set_combo_id(self.c_formato, id_nuevo)
        dlg.destroy()

    def _quitar_senal(self, btn):
        if self.id_conector is not None:
            Modelo.quitar_senal_en_conector(self.id_conector)
        if self.c_senal is not None:
            self.c_senal.set_active(-1)
            self.c_senal.get_child().set_text("")
        if self.c_formato is not None:
            self.c_formato.set_active(-1)
            self.c_formato.get_child().set_text("")

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            self.id_tipo_conector = _get_combo_id(self.c_tipo)
            x = self.e_x.get_text().strip()
            y = self.e_y.get_text().strip()
            if self.id_conector is not None:
                Modelo.modificacion_conector(
                    self.id_conector, nombre, self.id_equipo,
                    self.id_tipo_conector or None,
                    self.id_imagen or None, x, y
                )
            else:
                Modelo.agregar_conector(
                    nombre, self.id_equipo,
                    self.id_tipo_conector or None,
                    self.id_imagen or None, x, y
                )

            # Señal: sólo aplica si el conector ya existía al abrir la
            # ficha (self.c_senal es None en un conector recién creado
            # en este mismo Aceptar — ver comentario en __init__).
            if self.id_conector is not None and self.c_senal is not None:
                id_senal_sel = _get_combo_id(self.c_senal)
                if id_senal_sel:
                    id_formato_sel = _get_combo_id(self.c_formato) or None
                    Modelo.establecer_senal_en_conector(
                        self.id_conector, id_senal_sel, id_formato_sel)
                else:
                    # combo vacío = el usuario borró la selección a mano
                    # (además del botón "Quitar", que ya escribe en el
                    # momento); nos aseguramos de que quede consistente.
                    Modelo.quitar_senal_en_conector(self.id_conector)

            # Función de patchera: mismo criterio que Señal arriba — sólo
            # aplica si el combo llegó a mostrarse (conector existente +
            # equipo PATCHERA, ver __init__).
            if self.id_conector is not None and self.c_funcion_patchera is not None:
                id_funcion_sel = self.c_funcion_patchera.get_active_id() or None
                Modelo.establecer_funcion_patchera_conector(
                    self.id_conector, id_funcion_sel)

            # Formato eléctrico (plan_riesgo_senal_audio.md)
            if self.id_conector is not None and self.c_ficha_riesgo is not None:
                id_tf_sel = _get_combo_id(self.c_ficha_riesgo) or None
                idx_bal = self.c_modo_balance.get_active()
                idx_can = self.c_modo_canal.get_active()
                modo_bal_sel = ("", "BALANCEADO", "DESBALANCEADO", "NA")[idx_bal] or None
                modo_can_sel = ("", "MONO", "ESTEREO", "NA")[idx_can] or None
                Modelo.establecer_formato_conector(
                    self.id_conector, id_tf_sel, modo_bal_sel, modo_can_sel)

            # Armado (plan_bitacora_incidentes_riesgo_analogico.md)
            if self.id_conector is not None and self.c_armado is not None:
                id_arm = self.c_armado.get_active_id()
                es_correcto = None if not id_arm else bool(int(id_arm))
                detalle_arm = self.e_detalle_armado.get_text().strip() or None
                Modelo.establecer_armado_conector(
                    self.id_conector, es_correcto, detalle_arm)
        self.destroy()


class _DialogoRenombrarConectores(Gtk.Dialog):
    def __init__(self, id_equipo, parent=None):
        super().__init__(
            title=_("Renombrar Conectores"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(600, 500)
        self.id_equipo = id_equipo
        
        # Contenedor principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.get_content_area().add(vbox)
        
        # Obtener conectores del equipo
        conectores = Modelo.devolver_conectores_de_equipo(id_equipo)
        
        # Crear grid para los conectores
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(4)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        
        # Crear lista para guardar los entries
        self.entries = []
        
        for i, (id_conector, nombre, tipo) in enumerate(conectores):
            # Label con el nombre actual
            lbl = Gtk.Label(label=nombre)
            lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1)
            
            # Entry para el nuevo nombre
            entry = Gtk.Entry()
            entry.set_text(nombre)
            entry.set_hexpand(True)
            grid.attach(entry, 1, i, 1, 1)
            
            # Guardar referencia al entry junto con el id_conector y nombre original
            self.entries.append({
                'id': id_conector,
                'original': nombre,
                'entry': entry
            })
        
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
                    # Obtener los otros datos del conector para no perderlos
                    rows = Modelo.devolver_conector(item['id'])
                    if rows:
                        r = rows[0]
                        Modelo.modificacion_conector(
                            item['id'],
                            nuevo_nombre,
                            s(r[4]),  # id_equipo
                            s(r[3]),  # id_tipo_conector
                            s(r[7]),  # id_imagen
                            s(r[5]),  # x
                            s(r[6])   # y
                        )
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


# ─── Catálogo de equipos (moldes) ──────────────────────────────────────────────

class CatalogoEquiposListado(VentanaListado):
    """Listado de moldes de equipo. Cada fila es un 'tipo de equipo' reutilizable
    con marca/modelo/manual/imagen/conectores ya definidos."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Catálogo de Equipos"),
            [_("ID"), _("Molde"), _("Marca"), _("Tipo"), _("Modelo"), _("Conectores")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                ("⚡ Alta Rápida…", self._alta_rapida),
                ("📦 Instanciar…", self._instanciar),
                ("⬆ Exportar…", self._exportar),
                ("⬇ Importar…", self._importar),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_todos_los_catalogos()
        # rows: id, nombre_molde, marca, tipo, modelo, n_conectores
        self._poblar(rows)

    def nuevo(self):
        dlg = _DialogoCatalogoEquipo(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoCatalogoEquipo(id_equipo_catalogo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_catalogo(id_)

    def _alta_rapida(self, *a):
        dlg = _DialogoAltaRapidaCatalogo(parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _instanciar(self, *a):
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un molde del catálogo.")
            return
        dlg = _DialogoInstanciarCatalogo(id_equipo_catalogo=f[0],
                                         nombre_molde=f[1], parent=self)
        dlg.run_and_destroy()

    def _exportar(self, *a):
        """Exporta el molde seleccionado o todo el catálogo a un .zip
        portable que contiene un único JSON adentro (marca/tipo por nombre,
        imágenes/manual/picon embebidos en base64 dentro del JSON, y todo
        eso comprimido en el .zip)."""
        fila = self._fila()
        ids = [fila[0]] if fila else None
        if ids and not confirmar(
                self, f"¿Exportar solo el molde seleccionado «{fila[1]}»?\n\n"
                     "(Cancelá para exportar TODO el catálogo de equipos)"):
            ids = None
        dlg = Gtk.FileChooserDialog(
            title=_("Exportar catálogo de equipos"), parent=self,
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Guardar"), Gtk.ResponseType.OK)
        dlg.set_current_name("catalogo_equipos.zip")
        dlg.set_do_overwrite_confirmation(True)
        filt = Gtk.FileFilter(); filt.set_name("ZIP"); filt.add_pattern("*.zip")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if not ruta.lower().endswith(".zip"):
                ruta += ".zip"
            try:
                data = Modelo.exportar_catalogo_equipos(ids)
                _escribir_json_comprimido(ruta, "catalogo_equipos.json", data)
                mostrar_info(self,
                    f"Catálogo exportado: {len(data['moldes'])} molde(s) → {ruta}")
            except Exception as e:
                mostrar_error(self, f"Error al exportar:\n{e}")
        dlg.destroy()

    def _importar(self, *a):
        """Importa moldes desde un .zip (o un .json plano de una versión
        vieja) exportado por esta misma función, posiblemente de otra
        instalación de CableDoc."""
        dlg = Gtk.FileChooserDialog(
            title=_("Importar catálogo de equipos"), parent=self,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Abrir"), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name("ZIP / JSON")
        filt.add_pattern("*.zip"); filt.add_pattern("*.json")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            try:
                data = _leer_json_generico(ruta)
                if not isinstance(data, dict) or data.get("tipo") != "cabledoc_catalogo_equipos":
                    mostrar_error(self, "El archivo no es un catálogo de equipos válido.")
                else:
                    n_m, n_c, conflictos = Modelo.importar_catalogo_equipos(data)
                    mostrar_info(self, f"Importados {n_m} molde(s) con {n_c} conector(es).")
                    if conflictos:
                        _DialogoConflictosImportacion(conflictos, parent=self).run_and_destroy()
                    self.cargar_datos()
            except Exception as e:
                mostrar_error(self, f"Error al importar:\n{e}")
        dlg.destroy()


class _DialogoConflictosImportacion(Gtk.Dialog):
    """Fase 7 de plan_desarrollo_hardcodes_idioma.md: se muestra después de
    un import de catálogo cuando un tipo_equipo/tipo_conector ya existía en
    la base destino con un rol_senal/direccion/es_referencia_generada
    distinto al importado — el import NUNCA lo pisa solo, siempre queda el
    valor local hasta que el usuario elija explícitamente "usar el
    importado" acá y confirme."""

    _ETIQUETAS_CAMPO = {
        "rol_senal": _("Rol de señal"),
        "direccion": _("Dirección"),
        "es_referencia_generada": _("Es referencia generada"),
    }

    def __init__(self, conflictos, parent=None):
        super().__init__(
            title=_("Conflictos al importar (%d)") % len(conflictos),
            transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cerrar sin cambios"), Gtk.ResponseType.CANCEL,
                         _("Aplicar selección"), Gtk.ResponseType.OK)
        self.set_default_size(720, 380)
        self._conflictos = conflictos

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)

        lbl = Gtk.Label(wrap=True, xalign=0)
        lbl.set_markup(
            "<b>" + _("Estos tipos ya existían en la base destino con un "
                      "valor distinto al importado.") + "</b>\n" +
            _("Por defecto se mantiene el valor local en todos los casos — "
              "tildá \"Usar importado\" sólo en las filas donde corresponda "
              "y presioná \"Aplicar selección\"."))
        area.pack_start(lbl, False, False, 0)

        # store: usar_importado(bool), tipo, nombre, campo, local, importado, id, campo_raw
        self._store = Gtk.ListStore(bool, str, str, str, str, str, int, str)
        for c in conflictos:
            self._store.append([
                False, c["tipo"], c["nombre"],
                self._ETIQUETAS_CAMPO.get(c["campo"], c["campo"]),
                str(c["valor_local"]), str(c["valor_importado"]),
                int(c["id"]), c["campo"],
            ])
        tv = Gtk.TreeView(model=self._store)
        r_toggle = Gtk.CellRendererToggle()
        r_toggle.connect("toggled", self._on_toggle)
        tv.append_column(Gtk.TreeViewColumn(_("Usar importado"), r_toggle, active=0))
        for i, titulo in enumerate(
                [_("Tipo"), _("Nombre"), _("Campo"), _("Valor local"), _("Valor importado")], start=1):
            tv.append_column(Gtk.TreeViewColumn(titulo, Gtk.CellRendererText(), text=i))
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)
        self.show_all()

    def _on_toggle(self, _r, path):
        it = self._store.get_iter(path)
        self._store.set_value(it, 0, not self._store.get_value(it, 0))

    def run_and_destroy(self):
        resp = self.run()
        if resp == Gtk.ResponseType.OK:
            for row in self._store:
                usar_importado, tipo, _nom, _campo_lbl, _loc, importado, id_, campo_raw = row
                if not usar_importado:
                    continue
                if tipo == "tipo_equipo" and campo_raw == "rol_senal":
                    Modelo.establecer_rol_senal_tipo_equipo(id_, importado)
                elif tipo == "tipo_conector" and campo_raw == "direccion":
                    Modelo.establecer_direccion_tipo_conector(id_, importado)
                elif tipo == "tipo_conector" and campo_raw == "es_referencia_generada":
                    Modelo.establecer_es_referencia_generada_tipo_conector(
                        id_, importado == "True")
        self.destroy()


class _DialogoCatalogoEquipo(Gtk.Dialog):
    """Editor del molde: datos generales + lista de conectores-molde con
    posición sobre imagen (idéntico patrón a _DialogoEquipo, simplificado:
    sin inventario/serie/instancia, ya que eso es propio de cada instancia)."""

    def __init__(self, id_equipo_catalogo=None, parent=None):
        titulo = _("Editar Molde") if id_equipo_catalogo else _("Nuevo Molde de Equipo")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(560, 560)
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_marca = ""
        self.id_tipo = ""
        self.id_imagen = ""

        ca = self.get_content_area()
        g = _grid()
        _lbl_entry(g, _("Nombre molde:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Ej: Distribuidor DV700-STL")
        _lbl_entry(g, _("Tipo:"), 1)
        self.c_tipo = _searchable_combo(
            g, 1, Modelo.devolver_todos_los_tipos(), "…", self._sel_tipo_dropdown)
        _lbl_entry(g, _("Marca:"), 2)
        self.c_marca = _searchable_combo(
            g, 2, Modelo.devolver_todas_las_marcas(), "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Modelo:"), 3)
        self.e_modelo = _entry(g, 3)
        _lbl_entry(g, _("Imagen:"), 4)
        self.e_imagen = _entry_btn(g, 4, "…", self._sel_imagen)
        _lbl_entry(g, _("Manual (PDF):"), 5)
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 5, 1, 1)
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 5, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 6)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 6, 1, 1)
        btn_sel_picon = Gtk.Button(label="…")
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 6, 1, 1)
        btn_quitar_picon = Gtk.Button(label="✖")
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 6, 1, 1)
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(120, 120)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 7, 1, 1)
        ca.pack_start(g, False, False, 0)

        hbox_buttons = Gtk.Box(spacing=6)
        hbox_buttons.set_margin_start(12); hbox_buttons.set_margin_end(12)
        hbox_buttons.set_margin_bottom(6)
        if id_equipo_catalogo:
            btn_con = Gtk.Button(label="🔌 " + _("Conectores del molde"))
            btn_con.connect("clicked", self._ver_conectores)
            hbox_buttons.pack_start(btn_con, False, False, 0)

            btn_masivo = Gtk.Button(label="📍 " + _("Edición masiva conectores en imagen"))
            btn_masivo.connect("clicked", self._editar_conectores_masivo)
            hbox_buttons.pack_start(btn_masivo, False, False, 0)

            btn_rename = Gtk.Button(label="🏷 " + _("Renombrar conectores"))
            btn_rename.connect("clicked", self._renombrar_conectores)
            hbox_buttons.pack_start(btn_rename, False, False, 0)

            btn_reglas = Gtk.Button(label="🔀 " + _("Reglas lógicas"))
            btn_reglas.set_tooltip_text(
                _("Definir condiciones AND/OR sobre los conectores de este molde — "
                  "se copian automáticamente a cada equipo que se instancie desde acá"))
            btn_reglas.connect("clicked", self._ver_reglas_logicas_molde)
            hbox_buttons.pack_start(btn_reglas, False, False, 0)
        ca.pack_start(hbox_buttons, False, False, 0)

        if id_equipo_catalogo:
            rows = Modelo.devolver_catalogo(id_equipo_catalogo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_tipo = s(r[2]); _set_combo_id(self.c_tipo, self.id_tipo)
                self.id_marca = s(r[4]); _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[6]))
                self.id_imagen = s(r[7])
                self.e_imagen.set_text(s(r[8]))
                self.e_manual.set_text(s(r[9]))
                if len(r) > 11 and r[11]:
                    self.e_picon.set_text(s(r[11]))

        self._actualizar_picon_preview()
        self.show_all()

    def _sel_tipo_dropdown(self, btn):
        dlg = TiposEquipoListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_tipo, Modelo.devolver_todos_los_tipos())
            _set_combo_id(self.c_tipo, dlg.resultado_id)
        dlg.destroy()

    def _sel_marca_dropdown(self, btn):
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_marca, Modelo.devolver_todas_las_marcas())
            _set_combo_id(self.c_marca, dlg.resultado_id)
        dlg.destroy()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_manual(self, btn):
        from modelo import MANUALES_DIR
        os.makedirs(MANUALES_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar Manual PDF"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(MANUALES_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Archivos PDF"))
        filtro.add_pattern("*.pdf"); filtro.add_pattern("*.PDF")
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(MANUALES_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar: {e}")
                self.e_manual.set_text(fname)
        dialog.destroy()

    def _sel_picon(self, btn):
        os.makedirs(PICON_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(PICON_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filtro.add_pattern(pat)
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(PICON_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la foto: {e}")
                self.e_picon.set_text(fname)
                self._actualizar_picon_preview()
        dialog.destroy()

    def _quitar_picon(self, btn):
        self.e_picon.set_text("")
        self._actualizar_picon_preview()

    def _actualizar_picon_preview(self):
        filename = self.e_picon.get_text().strip()
        if filename:
            ruta = os.path.join(PICON_DIR, filename)
            if os.path.isfile(ruta):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, 120, 120, True)
                    self.img_picon.set_from_pixbuf(pixbuf)
                    return
                except Exception:
                    pass
        self.img_picon.clear()

    def _ver_conectores(self, btn):
        dlg = _ConectoresCatalogoListado(self.id_equipo_catalogo, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_reglas_logicas_molde(self, btn):
        """Abre el editor de reglas lógicas (AND/OR) de este molde."""
        nombre = self.e_nombre.get_text().strip() or f"Molde #{self.id_equipo_catalogo}"
        abrir_reglas_logicas_molde(self.id_equipo_catalogo, nombre, parent=self)

    def _editar_conectores_masivo(self, btn):
        if not self.id_imagen:
            mostrar_error(self, "Asigná una imagen al molde antes de "
                                "usar la edición masiva de conectores.")
            return
        abrir_editor_masivo_conectores_catalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def _renombrar_conectores(self, btn):
        dlg = _DialogoRenombrarConectoresCatalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self)
        dlg.run_and_destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_tipo = _get_combo_id(self.c_tipo)
            id_marca = _get_combo_id(self.c_marca)
            nombre = self.e_nombre.get_text().strip()
            modelo = self.e_modelo.get_text().strip()
            manual = self.e_manual.get_text().strip() or None
            picon = self.e_picon.get_text().strip() or None
            if self.id_equipo_catalogo:
                Modelo.modificacion_catalogo(
                    self.id_equipo_catalogo, nombre, id_tipo or None,
                    id_marca or None, modelo, self.id_imagen or None, manual,
                    picon=picon)
            else:
                nuevo_id = Modelo.alta_catalogo(
                    nombre, id_tipo or None, id_marca or None, modelo,
                    self.id_imagen or None, manual, picon=picon)
                self.id_equipo_catalogo = nuevo_id
        self.destroy()


class _ConectoresCatalogoListado(VentanaListado):
    def __init__(self, id_equipo_catalogo, parent=None):
        super().__init__(_("Conectores del molde"),
                         [_("ID"), _("Nombre"), _("Tipo")], parent=parent,
                         botones_extra=[
                             ("📍 Edición masiva en imagen", self._editar_masivo),
                         ])
        self.id_equipo_catalogo = id_equipo_catalogo
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_conectores_de_catalogo(self.id_equipo_catalogo)
        # rows: id, nombre, tipo_nom, id_tipo_conector, id_imagen, img_path, x, y
        data = [[r[0], r[1], r[2]] for r in rows]
        self._poblar(data)

    def nuevo(self):
        dlg = _DialogoConectorCatalogo(id_equipo_catalogo=self.id_equipo_catalogo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConectorCatalogo(id_conector_catalogo=id_,
                                       id_equipo_catalogo=self.id_equipo_catalogo,
                                       parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conector_catalogo(id_)

    def _editar_masivo(self, btn):
        abrir_editor_masivo_conectores_catalogo(
            id_equipo_catalogo=self.id_equipo_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)
        self.cargar_datos()


class _DialogoConectorCatalogo(Gtk.Dialog):
    def __init__(self, id_conector_catalogo=None, id_equipo_catalogo=None, parent=None):
        titulo = _("Editar Conector Molde") if id_conector_catalogo else _("Nuevo Conector Molde")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(420, 260)
        self.id_conector_catalogo = id_conector_catalogo
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Tipo conector:"), 1)
        self.c_tipo = _searchable_combo(g, 1, Modelo.devolver_tipos_conectores())
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)

        # Fase B de plan_desarrollo_funcion_patchera.md: el combo lee
        # Modelo.funciones_patchera() (tabla, no una lista fija en
        # Python) y muestra el NOMBRE VISIBLE de cada función — el valor
        # que persiste es id_funcion_patchera, independiente de cualquier
        # convención de nombre de conector (a diferencia del extinto
        # "Fila de patchera" A_BACK/B_BACK/A_FRONT/B_FRONT, que forzaba
        # la convención de una sola marca).
        self._es_molde_patchera = False
        if id_equipo_catalogo:
            rows_cat = Modelo.devolver_catalogo(id_equipo_catalogo)
            if rows_cat and rows_cat[0][2]:
                self._es_molde_patchera = (
                    Modelo.devolver_rol_senal_tipo_equipo(rows_cat[0][2]) == "PATCHERA")
        self.c_funcion_patchera = Gtk.ComboBoxText()
        self.c_funcion_patchera.append("", _("(ninguna)"))
        for f in Modelo.funciones_patchera():
            self.c_funcion_patchera.append(f["id"], f["nombre_es"])
        self.c_funcion_patchera.set_active_id("")
        if self._es_molde_patchera:
            _lbl_entry(g, _("Función de patchera:"), 5)
            g.attach(self.c_funcion_patchera, 1, 5, 2, 1)
        self.get_content_area().add(g)

        btn_coords = Gtk.Button(label="📍 " + _("Elegir coords en imagen"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_conector_catalogo:
            rows = Modelo._query(
                "SELECT id_conector_catalogo, nombre, id_tipo_conector, "
                "id_imagen, coordenada_x_en_imagen, coordenada_y_en_imagen, "
                "id_funcion_patchera "
                "FROM conector_catalogo WHERE id_conector_catalogo=?",
                (id_conector_catalogo,))
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                _set_combo_id(self.c_tipo, s(r[2]))
                self.id_imagen = s(r[3])
                x_px, y_px = Modelo._px_punto_o_crudo(
                    Modelo._path_imagen(r[3]), r[4], r[5])
                self.e_x.set_text(s(x_px)); self.e_y.set_text(s(y_px))
                if len(r) > 6 and r[6]:
                    self.c_funcion_patchera.set_active_id(s(r[6]))
                if self.id_imagen:
                    rows_img = Modelo.devolver_imagen(self.id_imagen)
                    if rows_img:
                        self.e_imagen.set_text(s(rows_img[0][1]))

        self.show_all()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(), parent=self)
        if res:
            self.e_x.set_text(res["x"]); self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            id_tipo_conector = _get_combo_id(self.c_tipo)
            x = self.e_x.get_text().strip(); y = self.e_y.get_text().strip()
            id_funcion_patchera = self.c_funcion_patchera.get_active_id() or None
            if self.id_conector_catalogo:
                Modelo.modificacion_conector_catalogo(
                    self.id_conector_catalogo, nombre,
                    id_tipo_conector or None, self.id_imagen or None, x, y,
                    id_funcion_patchera=id_funcion_patchera,
                    _tocar_funcion_patchera=self._es_molde_patchera)
            else:
                Modelo.agregar_conector_catalogo(
                    self.id_equipo_catalogo, nombre,
                    id_tipo_conector or None, self.id_imagen or None, x, y,
                    id_funcion_patchera=id_funcion_patchera)
        self.destroy()


class _DialogoInstanciarCatalogo(Gtk.Dialog):
    """Instancia un equipo real desde un molde: solo pide nombre, serie,
    inventario y posición x/y en planta. Todo lo demás se copia del molde."""

    def __init__(self, id_equipo_catalogo, nombre_molde="", parent=None):
        super().__init__(title=_("Instanciar equipo desde catálogo"),
                         transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📦 " + _("Crear equipo"), Gtk.ResponseType.OK)
        self.set_default_size(420, 260)
        self.id_equipo_catalogo = id_equipo_catalogo
        self.id_equipo_creado = None

        ca = self.get_content_area()
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>Molde:</b> {nombre_molde}")
        lbl.set_margin_start(12); lbl.set_margin_top(10)
        ca.pack_start(lbl, False, False, 0)

        g = _grid()
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del equipo real (requerido)")
        _lbl_entry(g, _("Inventario:"), 1)
        self.e_inventario = _entry(g, 1)
        _lbl_entry(g, _("Serie:"), 2)
        self.e_serie = _entry(g, 2)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)
        ca.pack_start(g, False, False, 0)

        n_con = len(Modelo.devolver_conectores_de_catalogo(id_equipo_catalogo))
        lbl_n = Gtk.Label(xalign=0)
        lbl_n.set_markup(f"<small><i>Se copiarán {n_con} conectores con su posición.</i></small>")
        lbl_n.set_margin_start(12)
        ca.pack_start(lbl_n, False, False, 4)

        self.show_all()

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp != Gtk.ResponseType.OK:
                break
            nombre = self.e_nombre.get_text().strip()
            if not nombre:
                mostrar_error(self, "El nombre del equipo es obligatorio.")
                continue
            self.id_equipo_creado = Modelo.instanciar_desde_catalogo(
                self.id_equipo_catalogo, nombre,
                self.e_inventario.get_text().strip() or None,
                self.e_serie.get_text().strip() or None,
                self.e_x.get_text().strip() or None,
                self.e_y.get_text().strip() or None,
            )
            mostrar_info(self, f"Equipo «{nombre}» creado (ID {self.id_equipo_creado}).")
            break
        self.destroy()


# ─── Equipos ──────────────────────────────────────────────────────────────────

class EquiposListado(VentanaListado):
    # filtro_pendiente: None | 'sin_conectores' | 'sin_imagen' | 'sin_img_conectores'
    def __init__(self, parent=None, modo_seleccion=False, filtro_pendiente=None):
        self._ocultar_patcheras = True   # debe existir antes de super().__init__
        self._filtro_pendiente = filtro_pendiente
        self._ids_resaltar = set()
        titulo = _("Equipos")
        if filtro_pendiente == "sin_conectores":
            titulo = _("Equipos — Sin conectores")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Equipos — Sin imagen")
        elif filtro_pendiente == "sin_img_conectores":
            titulo = _("Equipos — Sin imagen c/ conectores")
        super().__init__(
            titulo,
            [_("ID"), _("Nombre"), _("Marca"), _("Modelo"), _("Inventario"), _("Serie"), _("Tipo"),
             _("Riesgo")],
            parent=parent, modo_seleccion=modo_seleccion
        )
        # Obtener la barra de botones (hbtn) de VentanaListado
        hbtn = None
        for ch in self.get_content_area().get_children():
            if isinstance(ch, Gtk.Box):
                hbtn = ch
                break
        
        # Añadir botón Alta Rápida a la barra de botones
        btn_ar = Gtk.Button(label="⚡ " + _("Alta Rápida"))
        btn_ar.set_tooltip_text(
            _("Crear equipo con conectores en un solo formulario (estilo AVwire)"))
        btn_ar.connect("clicked", self._alta_rapida)
        if hbtn:
            hbtn.pack_start(btn_ar, False, False, 0)
            hbtn.reorder_child(btn_ar, 3)

        btn_cat = Gtk.Button(label="📦 " + _("Desde catálogo"))
        btn_cat.set_tooltip_text(
            _("Crear equipo instanciando un molde del catálogo (nombre/serie/inventario/posición)"))
        btn_cat.connect("clicked", self._desde_catalogo)
        if hbtn:
            hbtn.pack_start(btn_cat, False, False, 0)
            hbtn.reorder_child(btn_cat, 4)

        btn_hist = Gtk.Button(label="🩺 " + _("Historial de diagnósticos"))
        btn_hist.set_tooltip_text(
            _("'Prontuario' del equipo seleccionado — sesiones de "
              "diagnóstico de falla donde resultó sospechoso"))
        btn_hist.connect("clicked", self._ver_historial_diagnosticos)
        if hbtn:
            hbtn.pack_start(btn_hist, False, False, 0)
            hbtn.reorder_child(btn_hist, 5)

        btn_bitacora = Gtk.Button(label="📋 " + _("Ver incidentes"))
        btn_bitacora.set_tooltip_text(
            _("Bitácora de incidentes del equipo seleccionado — fallas "
              "reales registradas, directamente o vía una zona sospechosa "
              "a la que pertenezca"))
        btn_bitacora.connect("clicked", self._ver_bitacora_incidentes)
        if hbtn:
            hbtn.pack_start(btn_bitacora, False, False, 0)
            hbtn.reorder_child(btn_bitacora, 6)
        
        # Añadir checkbox "Ocultar patcheras" a la barra de botones
        self._chk_patchera = Gtk.CheckButton(label=_("Ocultar patcheras"))
        self._chk_patchera.set_active(True)
        self._chk_patchera.connect("toggled", self._on_toggle_patcheras)
        if hbtn:
            hbtn.pack_start(self._chk_patchera, False, False, 0)

        # Botón para recalcular el Índice de Riesgo de Falla (IRF) de
        # todo el parque de equipos (columna "Riesgo")
        btn_riesgo = Gtk.Button(label="🔺 " + _("Recalcular riesgo"))
        btn_riesgo.set_tooltip_text(
            _("Recalcula el Índice de Riesgo de Falla de todos los equipos "
              "(antigüedad, condición de uso, historial de problemas y "
              "criticidad en la cadena de transmisión)."))
        btn_riesgo.connect("clicked", self._recalcular_riesgo)
        if hbtn:
            hbtn.pack_start(btn_riesgo, False, False, 0)

        self.show_all()
        self.btn_seleccionar.set_visible(self.modo_seleccion)
        self.cargar_datos()

    def _on_toggle_patcheras(self, chk):
        self._ocultar_patcheras = chk.get_active()
        self.filtro_model.refilter()

    def cargar_datos(self):
        self._ids_resaltar = set()
        # Fase 4 de plan_desarrollo_hardcodes_idioma.md: el filtro "Ocultar
        # patcheras" ya no busca la palabra "PATCHERA" en la columna Tipo
        # (texto libre) -- usa rol_senal='PATCHERA', igual que
        # devolver_equipos_patchera().
        self._ids_patchera = {str(r[0]) for r in Modelo.devolver_equipos_patchera()}
        color = "#c8a800"
        if self._filtro_pendiente == "sin_conectores":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector WHERE id_equipo=equipo.id_equipo)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_equipo FROM equipo WHERE id_equipo != 0 AND id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_img_conectores":
            rows = Modelo._query(
                "SELECT e.id_equipo FROM equipo e WHERE id_equipo != 0 "
                "AND NOT EXISTS (SELECT 1 FROM conector c "
                "WHERE c.id_equipo=e.id_equipo AND c.id_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        todos = Modelo.devolver_todos_los_equipos()
        todos, color_por_id = self._agregar_columna_riesgo(todos)
        # Fase 4 de plan_desarrollo_hardcodes_idioma.md: ya no se filtra
        # comparando texto ("PATCHERA" in tipo) sino por rol_senal real.
        self._ids_patchera = {str(r[0]) for r in Modelo.devolver_equipos_patchera()}
        self._poblar(todos, ids_resaltar=self._ids_resaltar, color_resaltar=color,
                     color_por_id=color_por_id)
        # Aplicar prefiltro de texto si hay filtro activo
        if self._filtro_pendiente:
            self.entry_filtro.set_text("")
            self.filtro_model.refilter()

    @staticmethod
    def _agregar_columna_riesgo(filas):
        """Agrega el texto de riesgo (ej. '35 · Medio') como última columna
        de cada fila, y arma el mapeo id->color hex para semáforo visual.
        Usa la caché guardada en riesgo_equipo_cache (no recalcula en cada
        apertura del listado; para eso está el botón "🔺 Recalcular riesgo")."""
        from risk_engine import color_de
        cache = Modelo.devolver_riesgo_todos_los_equipos()  # {id_str: (riesgo, nivel)}
        filas_ext = []
        color_por_id = {}
        for f in filas:
            id_str = s(f[0])
            if id_str in cache:
                riesgo, nivel = cache[id_str]
                texto = f"{riesgo:.0f} · {nivel}"
                r, g, b = color_de(riesgo)
                color_por_id[id_str] = "#%02x%02x%02x" % (
                    int(r * 255), int(g * 255), int(b * 255))
            else:
                texto = _("Sin calcular")
            filas_ext.append(list(f) + [texto])
        return filas_ext, color_por_id

    def _recalcular_riesgo(self, *a):
        from risk_engine import RiskEngine
        self.set_sensitive(False)
        try:
            RiskEngine(DB_PATH).calcular_todos()
        except Exception as e:
            mostrar_error(self, f"{_('No se pudo calcular el riesgo')}:\n{e}")
        finally:
            self.set_sensitive(True)
        self.cargar_datos()

    def _filtrar(self, model, iter_, data):
        """Extiende el filtro: texto + patcheras + solo-pendientes."""
        txt = self.entry_filtro.get_text().lower()
        n = len(self.columnas)
        if txt:
            if not any(txt in s(model.get_value(iter_, i)).lower() for i in range(n)):
                return False
        if self._ocultar_patcheras:
            fid = s(model.get_value(iter_, 0))
            if fid in getattr(self, "_ids_patchera", ()):
                return False
        # Si hay filtro pendiente, mostrar SOLO los resaltados
        if self._filtro_pendiente and self._ids_resaltar:
            fid = s(model.get_value(iter_, 0))
            return fid in self._ids_resaltar
        return True

    def nuevo(self):
        dlg = _DialogoEquipo(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoEquipo(id_equipo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_equipo(id_)

    def _alta_rapida(self, *a):
        dlg = _DialogoAltaRapidaEquipo(parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _desde_catalogo(self, *a):
        sel = CatalogoEquiposListado(parent=self, modo_seleccion=True)
        if sel.run() == Gtk.ResponseType.OK:
            id_cat = sel.resultado_id
            nombre_molde = sel.resultado_nombre
            sel.destroy()
            dlg = _DialogoInstanciarCatalogo(
                id_equipo_catalogo=id_cat, nombre_molde=nombre_molde, parent=self)
            dlg.run_and_destroy()
            self.cargar_datos()
        else:
            sel.destroy()

    def _ver_historial_diagnosticos(self, *a):
        """'Prontuario' del equipo seleccionado (ver plan_asistente_
        diagnostico_fallas.md) — sesiones donde este equipo resultó
        sospechoso, para detectar fallas recurrentes."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un equipo primero.")
            return
        abrir_historial_diagnosticos(DB_PATH, parent=self, id_equipo=f[0])

    def _ver_bitacora_incidentes(self, *a):
        """Bitácora de incidentes (ver plan_bitacora_incidentes_riesgo_
        analogico.md) del equipo seleccionado — incluye los cargados vía
        una zona sospechosa a la que pertenezca, no sólo los directos."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un equipo primero.")
            return
        from bitacora_ui import abrir_bitacora_incidentes
        abrir_bitacora_incidentes(parent=self, id_equipo=f[0])



# ─── Alta Rápida de Equipo (estilo AVwire) ───────────────────────────────────

class _DialogoAltaRapidaEquipo(Gtk.Dialog):
    """
    Alta de equipo en un solo formulario:
      • Selector de tipo de equipo (con buscador)
      • Datos básicos (nombre, marca, modelo, inventario, serie)
      • Panel de conectores por plantilla con spinners IN / OUT
      • Vista previa en tiempo real
      • Botón "Guardar y duplicar"
    """

    # Colores por dirección de conector
    _COL_IN    = "#1D9E75"   # verde
    _COL_OUT   = "#534AB7"   # violeta
    _COL_INOUT = "#BA7517"   # naranja

    def __init__(self, parent=None):
        super().__init__(title=_("Alta Rápida de Equipo"),
                         transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(920, 580)
        self.add_buttons("Cancelar",          Gtk.ResponseType.CANCEL,
                         "💾 Guardar",        Gtk.ResponseType.OK,
                         "📋 Guardar y duplicar", Gtk.ResponseType.APPLY)

        # Estado interno
        self.id_tipo   = None
        self.id_marca  = None
        self._conectores_activos = {}   # (id_tipo_con, dir) -> cantidad
        self._todos_tipos_con = []      # [(id, nombre), ...]
        self._duplicar = False

        ca = self.get_content_area()
        ca.set_spacing(0)

        # ── Layout principal: izquierda datos + conectores / derecha preview ──
        hpan = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpan.set_position(600)
        ca.pack_start(hpan, True, True, 0)

        # ════════════════════════════════════
        # PANEL IZQUIERDO
        # ════════════════════════════════════
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_box.set_margin_start(12); left_box.set_margin_end(8)
        left_box.set_margin_top(10);  left_box.set_margin_bottom(8)
        left_scroll.add(left_box)
        hpan.add1(left_scroll)

        # ── Sección 1: Tipo de equipo ──
        lbl_s1 = Gtk.Label()
        lbl_s1.set_markup("<b>" + _("1. Tipo de equipo") + "</b>")
        lbl_s1.set_xalign(0); lbl_s1.set_margin_bottom(4)
        left_box.pack_start(lbl_s1, False, False, 0)

        hb_tipo = Gtk.Box(spacing=6)
        self.e_tipo_search = Gtk.SearchEntry()
        self.e_tipo_search.set_placeholder_text("Buscar tipo de equipo…")
        self.e_tipo_search.set_hexpand(True)
        self.e_tipo_search.connect("search-changed", self._on_tipo_search)
        hb_tipo.pack_start(self.e_tipo_search, True, True, 0)
        btn_tipo_nuevo = Gtk.Button(label="+ " + _("Nuevo tipo"))
        btn_tipo_nuevo.connect("clicked", self._crear_tipo)
        hb_tipo.pack_start(btn_tipo_nuevo, False, False, 0)
        left_box.pack_start(hb_tipo, False, False, 0)

        # Lista de tipos
        sw_tipos = Gtk.ScrolledWindow()
        sw_tipos.set_min_content_height(120)
        sw_tipos.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._store_tipos = Gtk.ListStore(str, str)  # id, nombre
        self._tv_tipos = Gtk.TreeView(model=self._store_tipos)
        self._tv_tipos.set_headers_visible(False)
        self._tv_tipos.set_activate_on_single_click(True)
        col_t = Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=6), text=1)
        self._tv_tipos.append_column(col_t)
        self._tv_tipos.connect("row-activated", self._on_tipo_seleccionado)
        sw_tipos.add(self._tv_tipos)
        left_box.pack_start(sw_tipos, False, False, 0)

        self._lbl_tipo_sel = Gtk.Label()
        self._lbl_tipo_sel.set_markup("<i>" + _("Ningún tipo seleccionado") + "</i>")
        self._lbl_tipo_sel.set_xalign(0)
        self._lbl_tipo_sel.set_margin_top(4); self._lbl_tipo_sel.set_margin_bottom(8)
        left_box.pack_start(self._lbl_tipo_sel, False, False, 0)

        sep1 = Gtk.Separator(); left_box.pack_start(sep1, False, False, 6)

        # ── Sección 2: Datos del equipo ──
        lbl_s2 = Gtk.Label()
        lbl_s2.set_markup("<b>" + _("2. Datos del equipo") + "</b>")
        lbl_s2.set_xalign(0); lbl_s2.set_margin_bottom(4)
        left_box.pack_start(lbl_s2, False, False, 0)

        g = _grid(); g.set_margin_bottom(4)
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del equipo (requerido)")
        self.e_nombre.connect("changed", self._actualizar_preview)
        _lbl_entry(g, _("Marca:"), 1)
        self.e_marca = _entry_btn(g, 1, "…", self._sel_marca)
        _lbl_entry(g, _("Modelo:"), 2)
        self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Inventario:"), 3)
        self.e_inventario = _entry(g, 3)
        _lbl_entry(g, _("Serie:"), 4)
        self.e_serie = _entry(g, 4)
        _lbl_entry(g, _("Foto (Picon):"), 5)
        self.e_picon = _entry_btn(g, 5, "…", self._sel_picon)
        left_box.pack_start(g, False, False, 0)

        sep2 = Gtk.Separator(); left_box.pack_start(sep2, False, False, 6)

        # ── Sección 3: Conectores ──
        lbl_s3 = Gtk.Label()
        lbl_s3.set_markup("<b>" + _("3. Conectores") + "</b>")
        lbl_s3.set_xalign(0); lbl_s3.set_margin_bottom(4)
        left_box.pack_start(lbl_s3, False, False, 0)

        lbl_hint = Gtk.Label()
        lbl_hint.set_markup(
            "<small><i>Ajustá las cantidades de cada conector. "
            "Cantidad 0 = no se crea. La plantilla se guarda por tipo de equipo.</i></small>"
        )
        lbl_hint.set_xalign(0); lbl_hint.set_line_wrap(True)
        lbl_hint.set_margin_bottom(6)
        left_box.pack_start(lbl_hint, False, False, 0)

        # Cabecera de conectores
        hdr_con = Gtk.Box(spacing=0)
        for txt, w, align in [
            (_("Tipo conector"),  1,   0.0),
            (_("Entradas (IN)"),  0,   0.5),
            (_("Salidas (OUT)"),  0,   0.5),
        ]:
            lbl = Gtk.Label(label=txt)
            lbl.set_markup(f"<small><b>{txt}</b></small>")
            lbl.set_xalign(align)
            lbl.set_margin_start(4)
            if w:
                hdr_con.pack_start(lbl, True, True, 0)
            else:
                lbl.set_width_chars(12)
                hdr_con.pack_start(lbl, False, False, 0)
        left_box.pack_start(hdr_con, False, False, 0)

        sep_hdr = Gtk.Separator()
        sep_hdr.set_margin_bottom(2)
        left_box.pack_start(sep_hdr, False, False, 0)

        # Contenedor de filas de conectores (se regenera al cambiar tipo)
        self._con_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left_box.pack_start(self._con_box, False, False, 0)

        # Botón agregar tipo conector manual
        btn_add_con = Gtk.Button(label="➕ " + _("Agregar tipo conector"))
        btn_add_con.connect("clicked", self._agregar_conector_manual)
        btn_add_con.set_margin_top(6)
        left_box.pack_start(btn_add_con, False, False, 0)

        # ════════════════════════════════════
        # PANEL DERECHO — Preview
        # ════════════════════════════════════
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8); right_box.set_margin_end(12)
        right_box.set_margin_top(10);  right_box.set_margin_bottom(8)
        hpan.add2(right_box)

        lbl_prev = Gtk.Label()
        lbl_prev.set_markup("<b>" + _("Vista previa") + "</b>")
        lbl_prev.set_xalign(0)
        right_box.pack_start(lbl_prev, False, False, 0)

        # Tarjeta de preview
        frame_prev = Gtk.Frame()
        frame_prev.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        prev_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prev_inner.set_margin_start(12); prev_inner.set_margin_end(12)
        prev_inner.set_margin_top(10);   prev_inner.set_margin_bottom(10)
        frame_prev.add(prev_inner)
        right_box.pack_start(frame_prev, False, False, 0)

        self._lbl_prev_nombre = Gtk.Label()
        self._lbl_prev_nombre.set_markup("<b>—</b>")
        self._lbl_prev_nombre.set_line_wrap(True)
        prev_inner.pack_start(self._lbl_prev_nombre, False, False, 0)

        self._lbl_prev_tipo = Gtk.Label()
        self._lbl_prev_tipo.set_markup("<i>" + _("tipo no seleccionado") + "</i>")
        self._lbl_prev_tipo.get_style_context().add_class("dim-label")
        prev_inner.pack_start(self._lbl_prev_tipo, False, False, 0)

        self._flow_prev_ports = Gtk.FlowBox()
        self._flow_prev_ports.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow_prev_ports.set_max_children_per_line(3)
        self._flow_prev_ports.set_row_spacing(4)
        self._flow_prev_ports.set_column_spacing(4)
        prev_inner.pack_start(self._flow_prev_ports, False, False, 0)

        self._lbl_prev_resumen = Gtk.Label()
        self._lbl_prev_resumen.get_style_context().add_class("dim-label")
        self._lbl_prev_resumen.set_margin_top(4)
        prev_inner.pack_start(self._lbl_prev_resumen, False, False, 0)

        # Resumen de lo que se creará
        sep_sum = Gtk.Separator(); right_box.pack_start(sep_sum, False, False, 0)

        lbl_sum = Gtk.Label()
        lbl_sum.set_markup("<b>" + _("Resumen") + "</b>")
        lbl_sum.set_xalign(0)
        right_box.pack_start(lbl_sum, False, False, 0)

        self._lbl_sum_detail = Gtk.Label()
        self._lbl_sum_detail.set_xalign(0)
        self._lbl_sum_detail.set_line_wrap(True)
        self._lbl_sum_detail.get_style_context().add_class("dim-label")
        right_box.pack_start(self._lbl_sum_detail, False, False, 0)

        self.show_all()

        # Cargar datos iniciales
        Modelo.asegurar_tabla_plantillas()
        self._todos_tipos_con = Modelo.devolver_tipos_conectores()
        self._poblar_tipos("")

    # ── Tipos de equipo ──────────────────────────────────────────────────────

    def _poblar_tipos(self, filtro):
        self._store_tipos.clear()
        todos = Modelo.devolver_todos_los_tipos()
        fl = filtro.lower()
        for r in todos:
            if not fl or fl in s(r[1]).lower():
                self._store_tipos.append([s(r[0]), s(r[1])])

    def _on_tipo_search(self, entry):
        self._poblar_tipos(entry.get_text())

    def _on_tipo_seleccionado(self, tv, path, col):
        it = self._store_tipos.get_iter(path)
        self.id_tipo = self._store_tipos.get_value(it, 0)
        nombre_tipo  = self._store_tipos.get_value(it, 1)
        self._lbl_tipo_sel.set_markup(
            f"Tipo seleccionado: <b>{nombre_tipo}</b>"
        )
        self._cargar_plantilla(self.id_tipo)
        self._actualizar_preview()

    def _crear_tipo(self, btn):
        dlg = DialogoNombre(_("Nuevo Tipo de Equipo"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_tipo(dlg.valor)
            self._poblar_tipos(self.e_tipo_search.get_text())
            mostrar_info(self, f"Tipo creado: {dlg.valor}")
        dlg.destroy()

    # ── Plantilla de conectores ───────────────────────────────────────────────

    def _cargar_plantilla(self, id_tipo):
        """Carga la plantilla del tipo y construye las filas de spinners."""
        self._conectores_activos = {}
        plantilla = Modelo.devolver_plantillas_conectores(id_tipo)

        # Si no hay plantilla, mostrar todos los tipos con cantidad 0
        if not plantilla:
            filas = [(s(r[0]), s(r[1]), "IN",    0) for r in self._todos_tipos_con] +                     [(s(r[0]), s(r[1]), "OUT",   0) for r in self._todos_tipos_con]
        else:
            # Incluir plantilla + tipos restantes con cantidad 0
            en_plantilla = {(s(r[0]), s(r[2])) for r in plantilla}
            filas = [(s(r[0]), s(r[1]), s(r[2]), int(r[3])) for r in plantilla]
            for r in self._todos_tipos_con:
                for dir_ in ("IN", "OUT"):
                    if (s(r[0]), dir_) not in en_plantilla:
                        filas.append((s(r[0]), s(r[1]), dir_, 0))

        # Inicializar estado activo desde plantilla
        for id_tc, nombre_tc, dir_, qty in filas:
            if qty > 0:
                self._conectores_activos[(id_tc, dir_)] = qty

        self._reconstruir_filas_conectores(filas)

    def _reconstruir_filas_conectores(self, filas):
        """Limpia y reconstruye el panel de conectores."""
        for ch in self._con_box.get_children():
            self._con_box.remove(ch)

        # Ordenar: primero los que tienen cantidad > 0, luego los demás
        filas_sorted = sorted(filas, key=lambda r: (r[3] == 0, r[1], r[2]))

        for id_tc, nombre_tc, dir_, qty in filas_sorted:
            row = self._crear_fila_conector(id_tc, nombre_tc, dir_, qty)
            self._con_box.pack_start(row, False, False, 0)

        self._con_box.show_all()
        self._actualizar_preview()

    def _crear_fila_conector(self, id_tc, nombre_tc, dir_, qty):
        """Crea una fila con nombre del conector, dirección y spinner."""
        hb = Gtk.Box(spacing=6)
        hb.set_margin_start(2); hb.set_margin_end(2)

        # Indicador de dirección (color)
        color = self._COL_IN if dir_ == "IN" else self._COL_OUT
        lbl_dir = Gtk.Label()
        lbl_dir.set_markup(
            f"<span foreground='{color}'><b>{'←' if dir_=='IN' else '→'}</b></span>"
        )
        lbl_dir.set_width_chars(2)
        hb.pack_start(lbl_dir, False, False, 0)

        # Nombre del tipo de conector
        lbl_n = Gtk.Label(label=f"{nombre_tc}")
        lbl_n.set_xalign(0)
        lbl_n.set_hexpand(True)
        if qty == 0:
            lbl_n.get_style_context().add_class("dim-label")
        hb.pack_start(lbl_n, True, True, 0)

        # Dirección texto
        lbl_d = Gtk.Label(label=dir_)
        lbl_d.set_width_chars(4)
        lbl_d.set_xalign(0.5)
        hb.pack_start(lbl_d, False, False, 0)

        # Spinner de cantidad
        adj = Gtk.Adjustment(value=qty, lower=0, upper=99, step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        spin.set_width_chars(4)
        spin.connect("value-changed",
                     self._on_spin_changed, id_tc, dir_, lbl_n)
        hb.pack_start(spin, False, False, 0)

        return hb

    def _on_spin_changed(self, spin, id_tc, dir_, lbl_n):
        qty = int(spin.get_value())
        if qty > 0:
            self._conectores_activos[(id_tc, dir_)] = qty
            lbl_n.get_style_context().remove_class("dim-label")
        else:
            self._conectores_activos.pop((id_tc, dir_), None)
            lbl_n.get_style_context().add_class("dim-label")
        self._actualizar_preview()

    def _agregar_conector_manual(self, btn):
        """Permite agregar un tipo de conector no listado en la plantilla."""
        dlg = TiposConectorListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_tc    = dlg.resultado_id
            nombre   = dlg.resultado_nombre
            # Preguntar dirección
            dlg2 = _DialogoDireccionConector(parent=self)
            if dlg2.run() == Gtk.ResponseType.OK:
                dir_ = dlg2.direccion
                # Verificar que no existe ya
                if (id_tc, dir_) not in {(id_, d)
                        for id_, d in self._conectores_activos}:
                    fila = self._crear_fila_conector(id_tc, nombre, dir_, 1)
                    self._con_box.pack_start(fila, False, False, 0)
                    self._con_box.show_all()
                    self._conectores_activos[(id_tc, dir_)] = 1
                    self._actualizar_preview()
            dlg2.destroy()
        dlg.destroy()

    # ── Preview ───────────────────────────────────────────────────────────────

    def _actualizar_preview(self, *a):
        nombre = self.e_nombre.get_text().strip() or "—"
        self._lbl_prev_nombre.set_markup(f"<b>{nombre}</b>")

        tipo_txt = self._lbl_tipo_sel.get_text().replace(
            "Tipo seleccionado: ", "").strip() or "tipo no seleccionado"
        marca = self.e_marca.get_text().strip()
        sub = tipo_txt + (f" · {marca}" if marca else "")
        self._lbl_prev_tipo.set_markup(f"<i>{sub}</i>")

        # Chips de puertos
        for ch in self._flow_prev_ports.get_children():
            self._flow_prev_ports.remove(ch)

        n_in = 0; n_out = 0
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc),
                "?"
            )
            color = self._COL_IN if dir_ == "IN" else self._COL_OUT
            signo = "←" if dir_ == "IN" else "→"
            lbl = Gtk.Label()
            lbl.set_markup(
                f"<span foreground='{color}'>{signo}</span> "
                f"{nombre_tc}"
                + (f" ×{qty}" if qty > 1 else "")
            )
            lbl.set_margin_start(6); lbl.set_margin_end(6)
            lbl.set_margin_top(3);   lbl.set_margin_bottom(3)
            frame_chip = Gtk.Frame()
            frame_chip.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            frame_chip.add(lbl)
            self._flow_prev_ports.add(frame_chip)
            if dir_ == "IN":
                n_in += qty
            else:
                n_out += qty

        self._flow_prev_ports.show_all()

        total_con = sum(self._conectores_activos.values())
        self._lbl_prev_resumen.set_markup(
            f"<small>{total_con} conectores · {n_in} entradas · {n_out} salidas</small>"
        )
        self._lbl_sum_detail.set_markup(
            f"Se crear\u00e1:\n  \u2022 1 equipo: <b>{nombre}</b>\n"
            f"  \u2022 {total_con} conectores ({n_in} IN, {n_out} OUT)\n"
            "  \u2022 Imagen y coordenadas: completar luego"
        )

    # ── Selectores ────────────────────────────────────────────────────────────

    def _sel_marca(self, btn):
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_marca = dlg.resultado_id
            self.e_marca.set_text(dlg.resultado_nombre)
        dlg.destroy()

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _sel_picon(self, btn):
        os.makedirs(PICON_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(PICON_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filtro.add_pattern(pat)
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(PICON_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la foto: {e}")
                self.e_picon.set_text(fname)
        dialog.destroy()

    def guardar(self):
        """
        Crea el equipo y todos sus conectores.
        Retorna el id_equipo creado, o None si falla validación.
        """
        nombre = self.e_nombre.get_text().strip()
        if not nombre:
            mostrar_error(self, "El nombre del equipo es obligatorio.")
            return None

        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo = self.id_tipo or None,
            id_marca       = self.id_marca or None,
            num_inventario = self.e_inventario.get_text().strip() or None,
            num_serie      = self.e_serie.get_text().strip() or None,
            modelo         = self.e_modelo.get_text().strip() or None,
            nombre         = nombre,
            id_imagen      = None,
            x              = None,
            y              = None,
            picon          = self.e_picon.get_text().strip() or None,
        )

        # Crear conectores
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc), "?"
            )
            for i in range(1, qty + 1):
                sufijo = f" {i:02d}" if qty > 1 else ""
                if nombre_tc.strip().upper() == dir_.strip().upper():
                    nombre_con = f"{dir_}{sufijo}"
                else:
                    nombre_con = f"{dir_} {nombre_tc}{sufijo}"
                Modelo.agregar_conector(
                    nombre           = nombre_con,
                    id_equipo        = id_equipo,
                    id_tipo_conector = id_tc or None,
                    id_imagen        = None,
                    x                = None,
                    y                = None,
                )

        # Guardar plantilla para este tipo
        if self.id_tipo and self._conectores_activos:
            for (id_tc, dir_), qty in self._conectores_activos.items():
                Modelo.guardar_plantilla_conector(
                    self.id_tipo, id_tc, dir_, qty
                )

        return id_equipo

    def _limpiar_para_duplicar(self):
        """Limpia solo los campos que cambian entre unidades del mismo equipo."""
        self.e_nombre.set_text("")
        self.e_inventario.set_text("")
        self.e_serie.set_text("")
        self.e_nombre.grab_focus()

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp == Gtk.ResponseType.APPLY:
                # Guardar y duplicar
                id_eq = self.guardar()
                if id_eq is not None:
                    mostrar_info(self,
                        f"Equipo guardado (ID {id_eq}).\n"
                        "Completá el siguiente equipo del mismo tipo.")
                    self._limpiar_para_duplicar()
                    continue   # volver al loop
            elif resp == Gtk.ResponseType.OK:
                id_eq = self.guardar()
                if id_eq is None:
                    continue   # validación falló, volver al loop
                break
            else:
                break
        self.destroy()


class _DialogoDuplicarMolde(Gtk.Dialog):
    """
    Mini-diálogo para 'Guardar y duplicar' en el catálogo: pide cuántos
    moldes duplicados crear y un patrón de nombre con 'XX' como marcador
    de posición del número (ej: 'EQUIPO_XX' → EQUIPO_01, EQUIPO_02...).
    """

    def __init__(self, nombre_base="", parent=None):
        super().__init__(title=_("Duplicar molde"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📋 " + _("Crear duplicados"), Gtk.ResponseType.OK)
        self.set_default_size(420, 200)
        self.cantidad = 0
        self.patron = ""

        g = _grid()
        _lbl_entry(g, _("Patrón de nombre:"), 0)
        self.e_patron = _entry(g, 0)
        sugerido = (nombre_base + "_XX") if nombre_base else "EQUIPO_XX"
        self.e_patron.set_text(sugerido)
        self.e_patron.set_placeholder_text("Ej: EQUIPO_XX")

        _lbl_entry(g, _("Cantidad:"), 1)
        adj = Gtk.Adjustment(value=2, lower=1, upper=99, step_increment=1)
        self.spin_cant = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        g.attach(self.spin_cant, 1, 1, 2, 1)

        self.get_content_area().add(g)

        lbl_hint = Gtk.Label(xalign=0)
        lbl_hint.set_markup(
            "<small><i>'XX' en el patrón se reemplaza por el número de "
            "secuencia (01, 02, …). Si el patrón no contiene 'XX', se "
            "agrega automáticamente al final.</i></small>")
        lbl_hint.set_line_wrap(True)
        lbl_hint.set_margin_start(12); lbl_hint.set_margin_end(12)
        lbl_hint.set_margin_bottom(8)
        self.get_content_area().pack_start(lbl_hint, False, False, 0)

        self._lbl_preview = Gtk.Label(xalign=0)
        self._lbl_preview.set_margin_start(12); self._lbl_preview.set_margin_bottom(8)
        self.get_content_area().pack_start(self._lbl_preview, False, False, 0)

        self.e_patron.connect("changed", self._actualizar_preview)
        self.spin_cant.connect("value-changed", self._actualizar_preview)

        self.show_all()
        self._actualizar_preview()

    def _actualizar_preview(self, *a):
        nombres = self._generar_nombres()
        if not nombres:
            self._lbl_preview.set_markup("<small><i>" + _("Patrón inválido") + "</i></small>")
            return
        muestra = ", ".join(nombres[:3])
        if len(nombres) > 3:
            muestra += f", … ({len(nombres)} en total)"
        self._lbl_preview.set_markup(f"<small>Se crearán: <b>{muestra}</b></small>")

    def _generar_nombres(self):
        patron = self.e_patron.get_text().strip()
        cantidad = int(self.spin_cant.get_value())
        if not patron or cantidad < 1:
            return []
        if "XX" not in patron:
            patron = patron + "_XX"
        ancho = max(2, len(str(cantidad)))
        return [patron.replace("XX", str(i).zfill(ancho))
                for i in range(1, cantidad + 1)]

    def run_and_destroy(self):
        resultado = None
        if self.run() == Gtk.ResponseType.OK:
            nombres = self._generar_nombres()
            if nombres:
                resultado = nombres
            else:
                mostrar_error(self, "Patrón de nombre o cantidad inválidos.")
        self.destroy()
        return resultado


class _DialogoAltaRapidaCatalogo(Gtk.Dialog):
    """
    Alta rápida de MOLDE de equipo (catálogo), idéntica en estructura a
    _DialogoAltaRapidaEquipo pero:
      • Sin Inventario/Serie (no aplican a un molde reutilizable)
      • Guarda en equipo_catalogo / conector_catalogo
      • 'Guardar y duplicar' pide patrón de nombre + cantidad (EQUIPO_XX)
        y crea N moldes de una vez, cada uno con sus conectores copiados
    """

    _COL_IN    = "#1D9E75"
    _COL_OUT   = "#534AB7"
    _COL_INOUT = "#BA7517"

    def __init__(self, parent=None):
        super().__init__(title=_("Alta Rápida de Molde"),
                         transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(920, 560)
        self.add_buttons("Cancelar",          Gtk.ResponseType.CANCEL,
                         "💾 Guardar",        Gtk.ResponseType.OK,
                         "📋 Guardar y duplicar…", Gtk.ResponseType.APPLY)

        self.id_tipo  = None
        self.id_marca = None
        self._conectores_activos = {}
        self._todos_tipos_con = []

        ca = self.get_content_area()
        ca.set_spacing(0)

        hpan = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpan.set_position(600)
        ca.pack_start(hpan, True, True, 0)

        # ── PANEL IZQUIERDO ──
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_box.set_margin_start(12); left_box.set_margin_end(8)
        left_box.set_margin_top(10);  left_box.set_margin_bottom(8)
        left_scroll.add(left_box)
        hpan.add1(left_scroll)

        lbl_s1 = Gtk.Label()
        lbl_s1.set_markup("<b>" + _("1. Tipo de equipo") + "</b>")
        lbl_s1.set_xalign(0); lbl_s1.set_margin_bottom(4)
        left_box.pack_start(lbl_s1, False, False, 0)

        hb_tipo = Gtk.Box(spacing=6)
        self.e_tipo_search = Gtk.SearchEntry()
        self.e_tipo_search.set_placeholder_text("Buscar tipo de equipo…")
        self.e_tipo_search.set_hexpand(True)
        self.e_tipo_search.connect("search-changed", self._on_tipo_search)
        hb_tipo.pack_start(self.e_tipo_search, True, True, 0)
        btn_tipo_nuevo = Gtk.Button(label="+ " + _("Nuevo tipo"))
        btn_tipo_nuevo.connect("clicked", self._crear_tipo)
        hb_tipo.pack_start(btn_tipo_nuevo, False, False, 0)
        left_box.pack_start(hb_tipo, False, False, 0)

        sw_tipos = Gtk.ScrolledWindow()
        sw_tipos.set_min_content_height(120)
        sw_tipos.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._store_tipos = Gtk.ListStore(str, str)
        self._tv_tipos = Gtk.TreeView(model=self._store_tipos)
        self._tv_tipos.set_headers_visible(False)
        self._tv_tipos.set_activate_on_single_click(True)
        col_t = Gtk.TreeViewColumn("", Gtk.CellRendererText(xpad=6), text=1)
        self._tv_tipos.append_column(col_t)
        self._tv_tipos.connect("row-activated", self._on_tipo_seleccionado)
        sw_tipos.add(self._tv_tipos)
        left_box.pack_start(sw_tipos, False, False, 0)

        self._lbl_tipo_sel = Gtk.Label()
        self._lbl_tipo_sel.set_markup("<i>" + _("Ningún tipo seleccionado") + "</i>")
        self._lbl_tipo_sel.set_xalign(0)
        self._lbl_tipo_sel.set_margin_top(4); self._lbl_tipo_sel.set_margin_bottom(8)
        left_box.pack_start(self._lbl_tipo_sel, False, False, 0)

        sep1 = Gtk.Separator(); left_box.pack_start(sep1, False, False, 6)

        # ── Sección 2: Datos del molde (sin Inventario/Serie) ──
        lbl_s2 = Gtk.Label()
        lbl_s2.set_markup("<b>" + _("2. Datos del molde") + "</b>")
        lbl_s2.set_xalign(0); lbl_s2.set_margin_bottom(4)
        left_box.pack_start(lbl_s2, False, False, 0)

        g = _grid(); g.set_margin_bottom(4)
        _lbl_entry(g, _("Nombre molde *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del molde (requerido)")
        self.e_nombre.connect("changed", self._actualizar_preview)
        _lbl_entry(g, _("Marca:"), 1)
        self.e_marca = _entry_btn(g, 1, "…", self._sel_marca)
        _lbl_entry(g, _("Modelo:"), 2)
        self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Foto (Picon):"), 3)
        self.e_picon = _entry_btn(g, 3, "…", self._sel_picon)
        left_box.pack_start(g, False, False, 0)

        sep2 = Gtk.Separator(); left_box.pack_start(sep2, False, False, 6)

        # ── Sección 3: Conectores ──
        lbl_s3 = Gtk.Label()
        lbl_s3.set_markup("<b>" + _("3. Conectores") + "</b>")
        lbl_s3.set_xalign(0); lbl_s3.set_margin_bottom(4)
        left_box.pack_start(lbl_s3, False, False, 0)

        lbl_hint = Gtk.Label()
        lbl_hint.set_markup(
            "<small><i>Ajustá las cantidades de cada conector. "
            "Cantidad 0 = no se crea. La plantilla se guarda por tipo de equipo.</i></small>"
        )
        lbl_hint.set_xalign(0); lbl_hint.set_line_wrap(True)
        lbl_hint.set_margin_bottom(6)
        left_box.pack_start(lbl_hint, False, False, 0)

        hdr_con = Gtk.Box(spacing=0)
        for txt, w, align in [
            (_("Tipo conector"),  1,   0.0),
            (_("Entradas (IN)"),  0,   0.5),
            (_("Salidas (OUT)"),  0,   0.5),
        ]:
            lbl = Gtk.Label(label=txt)
            lbl.set_markup(f"<small><b>{txt}</b></small>")
            lbl.set_xalign(align)
            lbl.set_margin_start(4)
            if w:
                hdr_con.pack_start(lbl, True, True, 0)
            else:
                lbl.set_width_chars(12)
                hdr_con.pack_start(lbl, False, False, 0)
        left_box.pack_start(hdr_con, False, False, 0)

        sep_hdr = Gtk.Separator()
        sep_hdr.set_margin_bottom(2)
        left_box.pack_start(sep_hdr, False, False, 0)

        self._con_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left_box.pack_start(self._con_box, False, False, 0)

        btn_add_con = Gtk.Button(label="➕ " + _("Agregar tipo conector"))
        btn_add_con.connect("clicked", self._agregar_conector_manual)
        btn_add_con.set_margin_top(6)
        left_box.pack_start(btn_add_con, False, False, 0)

        # ── PANEL DERECHO — Preview ──
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_margin_start(8); right_box.set_margin_end(12)
        right_box.set_margin_top(10);  right_box.set_margin_bottom(8)
        hpan.add2(right_box)

        lbl_prev = Gtk.Label()
        lbl_prev.set_markup("<b>" + _("Vista previa") + "</b>")
        lbl_prev.set_xalign(0)
        right_box.pack_start(lbl_prev, False, False, 0)

        frame_prev = Gtk.Frame()
        frame_prev.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        prev_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prev_inner.set_margin_start(12); prev_inner.set_margin_end(12)
        prev_inner.set_margin_top(10);   prev_inner.set_margin_bottom(10)
        frame_prev.add(prev_inner)
        right_box.pack_start(frame_prev, False, False, 0)

        self._lbl_prev_nombre = Gtk.Label()
        self._lbl_prev_nombre.set_markup("<b>—</b>")
        self._lbl_prev_nombre.set_line_wrap(True)
        prev_inner.pack_start(self._lbl_prev_nombre, False, False, 0)

        self._lbl_prev_tipo = Gtk.Label()
        self._lbl_prev_tipo.set_markup("<i>" + _("tipo no seleccionado") + "</i>")
        self._lbl_prev_tipo.get_style_context().add_class("dim-label")
        prev_inner.pack_start(self._lbl_prev_tipo, False, False, 0)

        self._flow_prev_ports = Gtk.FlowBox()
        self._flow_prev_ports.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow_prev_ports.set_max_children_per_line(3)
        self._flow_prev_ports.set_row_spacing(4)
        self._flow_prev_ports.set_column_spacing(4)
        prev_inner.pack_start(self._flow_prev_ports, False, False, 0)

        self._lbl_prev_resumen = Gtk.Label()
        self._lbl_prev_resumen.get_style_context().add_class("dim-label")
        self._lbl_prev_resumen.set_margin_top(4)
        prev_inner.pack_start(self._lbl_prev_resumen, False, False, 0)

        sep_sum = Gtk.Separator(); right_box.pack_start(sep_sum, False, False, 0)

        lbl_sum = Gtk.Label()
        lbl_sum.set_markup("<b>" + _("Resumen") + "</b>")
        lbl_sum.set_xalign(0)
        right_box.pack_start(lbl_sum, False, False, 0)

        self._lbl_sum_detail = Gtk.Label()
        self._lbl_sum_detail.set_xalign(0)
        self._lbl_sum_detail.set_line_wrap(True)
        self._lbl_sum_detail.get_style_context().add_class("dim-label")
        right_box.pack_start(self._lbl_sum_detail, False, False, 0)

        self.show_all()

        Modelo.asegurar_tabla_plantillas()
        self._todos_tipos_con = Modelo.devolver_tipos_conectores()
        self._poblar_tipos("")

    # ── Tipos de equipo ──────────────────────────────────────────────────────

    def _poblar_tipos(self, filtro):
        self._store_tipos.clear()
        todos = Modelo.devolver_todos_los_tipos()
        fl = filtro.lower()
        for r in todos:
            if not fl or fl in s(r[1]).lower():
                self._store_tipos.append([s(r[0]), s(r[1])])

    def _on_tipo_search(self, entry):
        self._poblar_tipos(entry.get_text())

    def _on_tipo_seleccionado(self, tv, path, col):
        it = self._store_tipos.get_iter(path)
        self.id_tipo = self._store_tipos.get_value(it, 0)
        nombre_tipo  = self._store_tipos.get_value(it, 1)
        self._lbl_tipo_sel.set_markup(f"Tipo seleccionado: <b>{nombre_tipo}</b>")
        self._cargar_plantilla(self.id_tipo)
        self._actualizar_preview()

    def _crear_tipo(self, btn):
        dlg = DialogoNombre(_("Nuevo Tipo de Equipo"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_tipo(dlg.valor)
            self._poblar_tipos(self.e_tipo_search.get_text())
            mostrar_info(self, f"Tipo creado: {dlg.valor}")
        dlg.destroy()

    # ── Plantilla de conectores (idéntico a _DialogoAltaRapidaEquipo) ────────

    def _cargar_plantilla(self, id_tipo):
        self._conectores_activos = {}
        plantilla = Modelo.devolver_plantillas_conectores(id_tipo)
        if not plantilla:
            filas = [(s(r[0]), s(r[1]), "IN",  0) for r in self._todos_tipos_con] + \
                    [(s(r[0]), s(r[1]), "OUT", 0) for r in self._todos_tipos_con]
        else:
            en_plantilla = {(s(r[0]), s(r[2])) for r in plantilla}
            filas = [(s(r[0]), s(r[1]), s(r[2]), int(r[3])) for r in plantilla]
            for r in self._todos_tipos_con:
                for dir_ in ("IN", "OUT"):
                    if (s(r[0]), dir_) not in en_plantilla:
                        filas.append((s(r[0]), s(r[1]), dir_, 0))

        for id_tc, nombre_tc, dir_, qty in filas:
            if qty > 0:
                self._conectores_activos[(id_tc, dir_)] = qty

        self._reconstruir_filas_conectores(filas)

    def _reconstruir_filas_conectores(self, filas):
        for ch in self._con_box.get_children():
            self._con_box.remove(ch)
        filas_sorted = sorted(filas, key=lambda r: (r[3] == 0, r[1], r[2]))
        for id_tc, nombre_tc, dir_, qty in filas_sorted:
            row = self._crear_fila_conector(id_tc, nombre_tc, dir_, qty)
            self._con_box.pack_start(row, False, False, 0)
        self._con_box.show_all()
        self._actualizar_preview()

    def _crear_fila_conector(self, id_tc, nombre_tc, dir_, qty):
        hb = Gtk.Box(spacing=6)
        hb.set_margin_start(2); hb.set_margin_end(2)

        color = self._COL_IN if dir_ == "IN" else self._COL_OUT
        lbl_dir = Gtk.Label()
        lbl_dir.set_markup(
            f"<span foreground='{color}'><b>{'←' if dir_=='IN' else '→'}</b></span>")
        lbl_dir.set_width_chars(2)
        hb.pack_start(lbl_dir, False, False, 0)

        lbl_n = Gtk.Label(label=f"{nombre_tc}")
        lbl_n.set_xalign(0)
        lbl_n.set_hexpand(True)
        if qty == 0:
            lbl_n.get_style_context().add_class("dim-label")
        hb.pack_start(lbl_n, True, True, 0)

        lbl_d = Gtk.Label(label=dir_)
        lbl_d.set_width_chars(4)
        lbl_d.set_xalign(0.5)
        hb.pack_start(lbl_d, False, False, 0)

        adj = Gtk.Adjustment(value=qty, lower=0, upper=99, step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        spin.set_width_chars(4)
        spin.connect("value-changed", self._on_spin_changed, id_tc, dir_, lbl_n)
        hb.pack_start(spin, False, False, 0)

        return hb

    def _on_spin_changed(self, spin, id_tc, dir_, lbl_n):
        qty = int(spin.get_value())
        if qty > 0:
            self._conectores_activos[(id_tc, dir_)] = qty
            lbl_n.get_style_context().remove_class("dim-label")
        else:
            self._conectores_activos.pop((id_tc, dir_), None)
            lbl_n.get_style_context().add_class("dim-label")
        self._actualizar_preview()

    def _agregar_conector_manual(self, btn):
        dlg = TiposConectorListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_tc  = dlg.resultado_id
            nombre = dlg.resultado_nombre
            dlg2 = _DialogoDireccionConector(parent=self)
            if dlg2.run() == Gtk.ResponseType.OK:
                dir_ = dlg2.direccion
                if (id_tc, dir_) not in {(id_, d) for id_, d in self._conectores_activos}:
                    fila = self._crear_fila_conector(id_tc, nombre, dir_, 1)
                    self._con_box.pack_start(fila, False, False, 0)
                    self._con_box.show_all()
                    self._conectores_activos[(id_tc, dir_)] = 1
                    self._actualizar_preview()
            dlg2.destroy()
        dlg.destroy()

    # ── Preview ───────────────────────────────────────────────────────────────

    def _actualizar_preview(self, *a):
        nombre = self.e_nombre.get_text().strip() or "—"
        self._lbl_prev_nombre.set_markup(f"<b>{nombre}</b>")

        tipo_txt = self._lbl_tipo_sel.get_text().replace(
            "Tipo seleccionado: ", "").strip() or "tipo no seleccionado"
        marca = self.e_marca.get_text().strip()
        sub = tipo_txt + (f" · {marca}" if marca else "")
        self._lbl_prev_tipo.set_markup(f"<i>{sub}</i>")

        for ch in self._flow_prev_ports.get_children():
            self._flow_prev_ports.remove(ch)

        n_in = 0; n_out = 0
        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc), "?")
            color = self._COL_IN if dir_ == "IN" else self._COL_OUT
            signo = "←" if dir_ == "IN" else "→"
            lbl = Gtk.Label()
            lbl.set_markup(
                f"<span foreground='{color}'>{signo}</span> {nombre_tc}"
                + (f" ×{qty}" if qty > 1 else ""))
            lbl.set_margin_start(6); lbl.set_margin_end(6)
            lbl.set_margin_top(3);   lbl.set_margin_bottom(3)
            frame_chip = Gtk.Frame()
            frame_chip.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            frame_chip.add(lbl)
            self._flow_prev_ports.add(frame_chip)
            if dir_ == "IN":
                n_in += qty
            else:
                n_out += qty

        self._flow_prev_ports.show_all()

        total_con = sum(self._conectores_activos.values())
        self._lbl_prev_resumen.set_markup(
            f"<small>{total_con} conectores · {n_in} entradas · {n_out} salidas</small>")
        self._lbl_sum_detail.set_markup(
            f"Se creará:\n  • 1 molde: <b>{nombre}</b>\n"
            f"  • {total_con} conectores ({n_in} IN, {n_out} OUT)\n"
            "  • Imagen y coordenadas: completar luego"
        )

    # ── Selectores ────────────────────────────────────────────────────────────

    def _sel_marca(self, btn):
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_marca = dlg.resultado_id
            self.e_marca.set_text(dlg.resultado_nombre)
        dlg.destroy()

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _sel_picon(self, btn):
        os.makedirs(PICON_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(PICON_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filtro.add_pattern(pat)
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(PICON_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la foto: {e}")
                self.e_picon.set_text(fname)
        dialog.destroy()

    def guardar(self, nombre_override=None):
        """
        Crea un molde (equipo_catalogo) y sus conectores (conector_catalogo).
        Si se pasa nombre_override, se usa en lugar del campo Nombre del
        formulario (usado al crear duplicados con patrón de nombre).
        Retorna el id_equipo_catalogo creado, o None si falla validación.
        """
        nombre = (nombre_override if nombre_override is not None
                  else self.e_nombre.get_text().strip())
        if not nombre:
            mostrar_error(self, "El nombre del molde es obligatorio.")
            return None

        id_cat = Modelo.alta_catalogo(
            nombre_molde = nombre,
            id_tipo_equipo = self.id_tipo or None,
            id_marca       = self.id_marca or None,
            modelo         = self.e_modelo.get_text().strip() or None,
            id_imagen      = None,
            picon          = self.e_picon.get_text().strip() or None,
        )

        for (id_tc, dir_), qty in self._conectores_activos.items():
            nombre_tc = next(
                (s(r[1]) for r in self._todos_tipos_con if s(r[0]) == id_tc), "?")
            for i in range(1, qty + 1):
                sufijo = f" {i:02d}" if qty > 1 else ""
                if nombre_tc.strip().upper() == dir_.strip().upper():
                    nombre_con = f"{dir_}{sufijo}"
                else:
                    nombre_con = f"{dir_} {nombre_tc}{sufijo}"
                Modelo.agregar_conector_catalogo(
                    id_equipo_catalogo = id_cat,
                    nombre             = nombre_con,
                    id_tipo_conector   = id_tc or None,
                    id_imagen          = None,
                    x                  = None,
                    y                  = None,
                )

        if self.id_tipo and self._conectores_activos:
            for (id_tc, dir_), qty in self._conectores_activos.items():
                Modelo.guardar_plantilla_conector(self.id_tipo, id_tc, dir_, qty)

        return id_cat

    def _duplicar_con_patron(self):
        """Abre el diálogo de patrón+cantidad y crea N moldes de una vez,
        cada uno con sus propios conectores copiados desde la configuración
        actual del formulario."""
        nombre_base = self.e_nombre.get_text().strip()
        dlg = _DialogoDuplicarMolde(nombre_base=nombre_base, parent=self)
        nombres = dlg.run_and_destroy()
        if not nombres:
            return None
        ids_creados = []
        for nom in nombres:
            id_cat = self.guardar(nombre_override=nom)
            if id_cat is not None:
                ids_creados.append((id_cat, nom))
        return ids_creados

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp == Gtk.ResponseType.APPLY:
                creados = self._duplicar_con_patron()
                if creados:
                    nombres_txt = ", ".join(n for _, n in creados)
                    mostrar_info(self,
                        f"Se crearon {len(creados)} moldes:\n{nombres_txt}")
                    break
                # si canceló el sub-diálogo o falló, seguir en el loop
                continue
            elif resp == Gtk.ResponseType.OK:
                id_cat = self.guardar()
                if id_cat is None:
                    continue
                break
            else:
                break
        self.destroy()


class _DialogoDireccionConector(Gtk.Dialog):
    """Mini-diálogo para elegir IN / OUT al agregar conector manual."""
    def __init__(self, parent=None):
        super().__init__(title=_("Dirección del conector"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "OK", Gtk.ResponseType.OK)
        self.direccion = "IN"
        hb = Gtk.Box(spacing=12)
        hb.set_margin_start(16); hb.set_margin_end(16)
        hb.set_margin_top(12);   hb.set_margin_bottom(12)
        rb_in = Gtk.RadioButton.new_with_label(None, "← Entrada (IN)")
        rb_out = Gtk.RadioButton.new_with_label_from_widget(rb_in, "→ Salida (OUT)")
        rb_in.connect("toggled", lambda b: setattr(self, "direccion", "IN"))
        rb_out.connect("toggled", lambda b: setattr(self, "direccion", "OUT"))
        hb.pack_start(rb_in, False, False, 0)
        hb.pack_start(rb_out, False, False, 0)
        self.get_content_area().pack_start(hb, False, False, 0)
        self.show_all()

class _DialogoEquipo(Gtk.Dialog):
    def __init__(self, id_equipo=None, parent=None):
        titulo = _("Editar Equipo") if id_equipo else _("Nuevo Equipo")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(700, 620)
        self.id_equipo = id_equipo
        self.id_marca = ""
        self.id_tipo = ""
        self.id_imagen = ""

        # Crear contenedor principal vertical
        vbox_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox_main.set_margin_top(6)
        self.get_content_area().add(vbox_main)

        # ── Pestaña Datos (Notebook primero) ──
        nb = Gtk.Notebook()

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(
            g, 1, Modelo.devolver_todas_las_marcas(),
            "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Tipo:"), 2)
        self.c_tipo = _searchable_combo(
            g, 2, Modelo.devolver_todos_los_tipos(),
            "…", self._sel_tipo_dropdown)
        _lbl_entry(g, _("Modelo:"), 3)
        self.e_modelo = _entry(g, 3)
        _lbl_entry(g, _("Inventario:"), 4)
        self.e_inventario = _entry(g, 4)
        _lbl_entry(g, _("Serie:"), 5)
        self.e_serie = _entry(g, 5)
        _lbl_entry(g, _("Imagen:"), 6)
        self.e_imagen = _entry_btn(g, 6, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 7)
        self.e_x = _entry(g, 7)
        _lbl_entry(g, _("Coord Y:"), 8)
        self.e_y = _entry(g, 8)
        _lbl_entry(g, _("Manual (PDF):"), 9)
        # Entry para el manual PDF
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 9, 1, 1)
        # Botón para seleccionar manual
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 9, 1, 1)
        # Botón para ver el PDF
        btn_view_manual = Gtk.Button(label="👁 " + _("Ver"))
        btn_view_manual.connect("clicked", self._ver_manual)
        g.attach(btn_view_manual, 3, 9, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 10)
        # Entry para el nombre de archivo de la foto del equipo (picon)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 10, 1, 1)
        # Botón para seleccionar la foto
        btn_sel_picon = Gtk.Button(label="…")
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 10, 1, 1)
        # Botón para quitar la foto
        btn_quitar_picon = Gtk.Button(label="✖")
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 10, 1, 1)
        # Miniatura de vista previa de la foto
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(140, 140)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 11, 1, 1)
        _lbl_entry(g, _("Fecha de fabricación:"), 12)
        self.e_fecha_fabricacion = _entry(g, 12)
        self.e_fecha_fabricacion.set_placeholder_text("AAAA-MM-DD")
        self.chk_equipo_usado = Gtk.CheckButton(label=_("Equipo usado (no nuevo)"))
        g.attach(self.chk_equipo_usado, 1, 13, 2, 1)

        # ── Sección: Riesgo de falla (IRF) ──
        sep_riesgo = Gtk.Separator()
        g.attach(sep_riesgo, 0, 14, 4, 1)
        lbl_riesgo_titulo = Gtk.Label()
        lbl_riesgo_titulo.set_markup("<b>🔺 " + _("Riesgo de falla") + "</b>")
        lbl_riesgo_titulo.set_xalign(0)
        g.attach(lbl_riesgo_titulo, 0, 15, 4, 1)

        self.lbl_riesgo_score = Gtk.Label(label="—")
        self.lbl_riesgo_score.set_xalign(0)
        g.attach(self.lbl_riesgo_score, 0, 16, 4, 1)

        self.chk_equipo_critico = Gtk.CheckButton(
            label="⭐ " + _("Equipo crítico de la cadena"))
        self.chk_equipo_critico.set_tooltip_text(
            _("Marca este equipo como parte del conjunto curado de equipos "
              "realmente vitales (ej. la cadena de aire). Con al menos un "
              "equipo marcado en toda la base, el factor Impacto del riesgo "
              "prioriza este conjunto en vez de contar todo el parque por "
              "igual. También se puede marcar de a varios desde el "
              "diagrama de conexiones (seleccioná con rectángulo o "
              "Shift/Ctrl+clic y usá '⭐ Marcar críticos')."))
        self.chk_equipo_critico.connect("toggled", self._on_toggle_critico)
        g.attach(self.chk_equipo_critico, 0, 17, 4, 1)

        self.lbl_riesgo_detalle = Gtk.Label(label="")
        self.lbl_riesgo_detalle.set_xalign(0)
        self.lbl_riesgo_detalle.set_line_wrap(True)
        self.lbl_riesgo_detalle.get_style_context().add_class("dim-label")
        g.attach(self.lbl_riesgo_detalle, 0, 18, 4, 2)

        hbox_riesgo = Gtk.Box(spacing=6)
        btn_recalc_riesgo = Gtk.Button(label="🔄 " + _("Recalcular"))
        btn_recalc_riesgo.set_tooltip_text(
            _("Recalcula el riesgo de este equipo (y de todo el parque, ya "
              "que el factor de impacto depende del grafo completo)."))
        btn_recalc_riesgo.connect("clicked", self._recalcular_riesgo)
        hbox_riesgo.pack_start(btn_recalc_riesgo, False, False, 0)
        btn_ver_afectados = Gtk.Button(label="⚡ " + _("Simular remoción"))
        btn_ver_afectados.set_tooltip_text(_(
            "Qué otros equipos y cables quedan sin señal si este equipo "
            "falla (no destructivo, no toca la base)."))
        btn_ver_afectados.connect("clicked", self._ver_equipos_afectados)
        hbox_riesgo.pack_start(btn_ver_afectados, False, False, 0)
        g.attach(hbox_riesgo, 0, 20, 4, 1)

        nb.append_page(g, Gtk.Label(label=_("Datos")))

        # ── Pestaña Configuraciones ──
        box_conf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box_conf.set_margin_start(12)
        box_conf.set_margin_end(12)
        box_conf.set_margin_top(6)
        box_conf.set_margin_bottom(6)
        
        # TextView para edición (arriba)
        self.tv_configuraciones_edit = Gtk.TextView()
        self.tv_configuraciones_edit.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_configuraciones_edit.set_editable(True)
        self.tv_configuraciones_edit.set_hexpand(True)
        
        scrolled_edit = Gtk.ScrolledWindow()
        scrolled_edit.set_hexpand(True)
        scrolled_edit.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_edit.add(self.tv_configuraciones_edit)
        box_conf.pack_start(scrolled_edit, True, True, 0)
        
        # Separador
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box_conf.pack_start(sep, False, False, 0)
        
        # Label para vista previa
        lbl_preview = Gtk.Label(label=_("Vista previa (Markdown renderizado):"))
        lbl_preview.set_xalign(0)
        box_conf.pack_start(lbl_preview, False, False, 0)
        
        # TextView para visualización (abajo)
        self.tv_configuraciones_view = Gtk.TextView()
        self.tv_configuraciones_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_configuraciones_view.set_editable(False)
        self.tv_configuraciones_view.set_cursor_visible(False)
        self.tv_configuraciones_view.set_hexpand(True)
        self.tv_configuraciones_view.set_vexpand(True)
        
        # Crear tags para formato Markdown (una sola vez)
        buffer_view = self.tv_configuraciones_view.get_buffer()
        self.tag_bold = buffer_view.create_tag("bold", weight=700)
        self.tag_italic = buffer_view.create_tag("italic", style=Pango.Style.ITALIC)
        self.tag_mono = buffer_view.create_tag("monospace", family="Monospace")
        self.tag_large = buffer_view.create_tag("large", scale=1.5, weight=700)
        self.tag_xlarge = buffer_view.create_tag("x-large", scale=2.0, weight=700)
        
        scrolled_view = Gtk.ScrolledWindow()
        scrolled_view.set_hexpand(True)
        scrolled_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_view.add(self.tv_configuraciones_view)
        box_conf.pack_start(scrolled_view, True, True, 0)
        
        # Botón para alternar entre edición y visualización
        self.btn_edit_config = Gtk.Button(label="✏️ " + _("Editar"))
        self.btn_edit_config.connect("clicked", self._toggle_edit_configuraciones)
        box_conf.pack_start(self.btn_edit_config, False, False, 0)
        
        # Guardar referencia al TextView de edición para compatibilidad
        self.tv_configuraciones = self.tv_configuraciones_edit
        
        # Guardar referencias a widgets para mostrar/ocultar
        self.scrolled_edit = scrolled_edit
        self.sep_config = sep
        self.lbl_preview = lbl_preview
        self.scrolled_view = scrolled_view
        
        nb.append_page(box_conf, Gtk.Label(label=_("Configuraciones")))

        # Añadir Notebook al contenedor principal (expande para ocupar espacio)
        vbox_main.pack_start(nb, True, True, 0)

        # ── Botones extra abajo del Notebook (2 filas de 5) ──
        vbox_botones = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox_botones.set_margin_start(12)
        vbox_botones.set_margin_end(12)
        vbox_botones.set_margin_bottom(6)

        hbox_fila1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_fila2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_fila3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox_botones.pack_start(hbox_fila1, False, False, 0)
        vbox_botones.pack_start(hbox_fila2, False, False, 0)
        vbox_botones.pack_start(hbox_fila3, False, False, 0)

        if id_equipo:
            btn_con = Gtk.Button(label="🔌 " + _("Ver Conectores"))
            btn_con.connect("clicked", self._ver_conectores)
            hbox_fila1.pack_start(btn_con, False, False, 0)

            btn_img_con = Gtk.Button(label="🖼 " + _("Imagen c/ conectores"))
            btn_img_con.connect("clicked", self._ver_imagen_conectores)
            hbox_fila1.pack_start(btn_img_con, False, False, 0)

            btn_ed_masivo = Gtk.Button(label="📍 " + _("Edición masiva conectores en imagen"))
            btn_ed_masivo.connect("clicked", self._ver_editor_masivo_conectores)
            hbox_fila1.pack_start(btn_ed_masivo, False, False, 0)

            btn_arbol = Gtk.Button(label="🌳 " + _("Árbol de conexiones"))
            btn_arbol.connect("clicked", self._ver_arbol)
            hbox_fila1.pack_start(btn_arbol, False, False, 0)

            btn_patch = Gtk.Button(label="🔌 " + _("Patcheras"))
            btn_patch.connect("clicked", self._ver_patcheras)
            hbox_fila2.pack_start(btn_patch, False, False, 0)

            btn_diag = Gtk.Button(label="🔗 " + _("Diagrama de conexiones"))
            btn_diag.connect("clicked", self._ver_diagrama)
            hbox_fila2.pack_start(btn_diag, False, False, 0)

            btn_rename = Gtk.Button(label="🏷 " + _("Renombrar conectores"))
            btn_rename.connect("clicked", self._renombrar_conectores)
            hbox_fila2.pack_start(btn_rename, False, False, 0)

            btn_rack = Gtk.Button(label="🗄 " + _("Rack del equipo"))
            btn_rack.set_tooltip_text(
                _("Buscar en qué rack está montado este equipo (directo o dentro de un frame) y abrir su vista gráfica"))
            btn_rack.connect("clicked", self._ver_rack)
            hbox_fila2.pack_start(btn_rack, False, False, 0)

            btn_reglas = Gtk.Button(label="🔀 " + _("Reglas lógicas"))
            btn_reglas.set_tooltip_text(
                _("Definir condiciones AND/OR sobre los conectores de entrada "
                  "(ej. \"requiere todas estas entradas para que funcionen las "
                  "salidas\", o \"alcanza con una de estas dos\")"))
            btn_reglas.connect("clicked", self._ver_reglas_logicas)
            hbox_fila2.pack_start(btn_reglas, False, False, 0)

            btn_template = Gtk.Button(label="🧬 " + _("Equipo a template"))
            btn_template.set_tooltip_text(
                _("Crear un molde de catálogo reutilizable a partir de "
                  "este equipo y sus conectores (sin inventario/serie)"))
            btn_template.connect("clicked", self._equipo_a_template)
            hbox_fila3.pack_start(btn_template, False, False, 0)

        btn_coords = Gtk.Button(label="📍 " + _("Ver ubicación"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        hbox_fila3.pack_start(btn_coords, False, False, 0)

        if id_equipo:
            n_problemas = Modelo.devolver_cantidad_problemas_de_equipo(id_equipo)
            etiqueta_problemas = "⚠ Problemas del equipo"
            if n_problemas:
                etiqueta_problemas += f" ({n_problemas})"
            btn_problemas = Gtk.Button(label=etiqueta_problemas)
            btn_problemas.set_tooltip_text(
                _("Ver y cargar los problemas reportados para este equipo "
                  "(categoría, gravedad y descripción)"))
            btn_problemas.connect("clicked", self._ver_problemas)
            hbox_fila3.pack_start(btn_problemas, False, False, 0)

        vbox_main.pack_start(vbox_botones, False, False, 0)

        # Cargar datos si es edición
        if id_equipo:
            rows = Modelo.devolver_equipo(id_equipo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.e_modelo.set_text(s(r[3]))
                self.e_inventario.set_text(s(r[4]))
                self.e_serie.set_text(s(r[5]))
                _set_combo_id(self.c_marca, s(r[6]))
                _set_combo_id(self.c_tipo, s(r[8]))
                self.e_imagen.set_text(s(r[9]))
                self.id_imagen = s(r[10])
                self.e_x.set_text(s(r[11]))
                self.e_y.set_text(s(r[12]))
                self.e_manual.set_text(s(r[13]))
                if r[14]:
                    markdown_text = s(r[14])
                    # Guardar texto sin formato en el editor
                    self.tv_configuraciones_edit.get_buffer().set_text(markdown_text, -1)
                    # Formatear y mostrar en el visor
                    self._render_markdown(markdown_text)
                if len(r) > 15 and r[15]:
                    self.e_picon.set_text(s(r[15]))
                if len(r) > 16 and r[16]:
                    self.e_fecha_fabricacion.set_text(s(r[16]))
                if len(r) > 17 and r[17]:
                    self.chk_equipo_usado.set_active(bool(r[17]))

        self._actualizar_seccion_riesgo()
        self._actualizar_picon_preview()
        _pack_ultima_edicion(self, "equipo", "id_equipo", id_equipo)
        self.show_all()
        
        # Por defecto: mostrar solo el visor (renderizado), ocultar el editor
        self.scrolled_edit.hide()
        self.sep_config.hide()
        self.lbl_preview.hide()

    def _render_markdown(self, markdown_text):
        """Renderiza texto Markdown en self.tv_configuraciones_view."""
        buffer = self.tv_configuraciones_view.get_buffer()
        buffer.set_text(markdown_text)
        
        if not markdown_text.strip():
            return
        
        # Usar tags pre-creados
        tag_bold = self.tag_bold
        tag_italic = self.tag_italic
        tag_mono = self.tag_mono
        tag_large = self.tag_large
        tag_xlarge = self.tag_xlarge
        
        start_iter = buffer.get_start_iter()
        
        # Procesar línea por línea para encabezados
        line_iter = start_iter.copy()
        while line_iter.forward_line():
            line_start = line_iter.copy()
            if not line_iter.forward_to_line_end():
                break
            line_end = line_iter.copy()
            line_text = buffer.get_text(line_start, line_end, False)
            
            stripped = line_text.strip()
            if stripped.startswith('# '):
                tag_start = line_start.copy()
                tag_start.forward_chars(2)
                buffer.apply_tag(tag_xlarge, tag_start, line_end)
            elif stripped.startswith('## '):
                tag_start = line_start.copy()
                tag_start.forward_chars(3)
                buffer.apply_tag(tag_large, tag_start, line_end)
            elif stripped.startswith('### '):
                tag_start = line_start.copy()
                tag_start.forward_chars(4)
                buffer.apply_tag(tag_bold, tag_start, line_end)
        
        # Aplicar formato inline
        self._apply_markdown_tags_global(buffer, tag_bold, r'\*\*(.+?)\*\*', r'__(.+?)__')
        self._apply_markdown_tags_global(buffer, tag_italic, r'\*(.+?)\*', r'(?<!\w)_(.+?)_(?!\w)')
        self._apply_markdown_tags_global(buffer, tag_mono, r'`([^`]+)`')

    def _toggle_edit_configuraciones(self, btn):
        """Alterna entre modo edición y visualización de configuraciones."""
        if self.btn_edit_config.get_label() == "✏️ Editar":
            # Cambiar a modo edición: mostrar editor, ocultar visor
            self.scrolled_edit.show()
            self.sep_config.show()
            self.lbl_preview.show()
            self.scrolled_view.hide()
            self.btn_edit_config.set_label("👁️ Guardar y Ver")
        else:
            # Cambiar a modo visualización: renderizar markdown y mostrar visor
            buf_edit = self.tv_configuraciones_edit.get_buffer()
            start, end = buf_edit.get_bounds()
            markdown_text = buf_edit.get_text(start, end, False)
            
            # Renderizar y mostrar en el visor
            self._render_markdown(markdown_text)
            
            self.scrolled_edit.hide()
            self.sep_config.hide()
            self.lbl_preview.hide()
            self.scrolled_view.show()
            self.btn_edit_config.set_label("✏️ Editar")

    
    def _apply_markdown_tags_global(self, buffer, tag, *patterns):
        """Aplica tags de formato al buffer completo según patrones Markdown."""
        import re
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False)
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                start_offset = start.get_offset() + match.start()
                end_offset = start.get_offset() + match.end()
                start_iter = buffer.get_iter_at_offset(start_offset)
                end_iter = buffer.get_iter_at_offset(end_offset)
                buffer.apply_tag(tag, start_iter, end_iter)

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_manual(self, btn):
        """Seleccionar archivo PDF y copiarlo a manuales/"""
        from modelo import MANUALES_DIR
        import os
        import shutil
        
        # Asegurar que el directorio exista
        os.makedirs(MANUALES_DIR, exist_ok=True)
        
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar Manual PDF"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_default_size(600, 400)
        
        # Filtrar solo archivos PDF
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name(_("Archivos PDF"))
        filter_pdf.add_mime_type("application/pdf")
        filter_pdf.add_pattern("*.pdf")
        filter_pdf.add_pattern("*.PDF")
        dialog.add_filter(filter_pdf)
        
        # Filtrar todos los archivos
        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos los archivos"))
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        # Establecer el directorio manuales como ubicación inicial
        dialog.set_current_folder(MANUALES_DIR)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            source_path = dialog.get_filename()
            if source_path:
                # Extraer nombre de archivo
                filename = os.path.basename(source_path)
                # Crear path destino
                dest_path = os.path.join(MANUALES_DIR, filename)
                
                # Verificar si el archivo ya está en manuales/
                if os.path.abspath(source_path) == os.path.abspath(dest_path):
                    # El archivo ya está en manuales/, solo guardar el nombre
                    self.e_manual.set_text(filename)
                else:
                    # Copiar archivo a manuales/
                    try:
                        shutil.copy2(source_path, dest_path)
                        # Guardar solo el nombre del archivo
                        self.e_manual.set_text(filename)
                    except Exception as e:
                        dlg = Gtk.MessageDialog(
                            transient_for=self,
                            modal=True,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.OK,
                            text=f"Error al copiar el archivo: {e}"
                        )
                        dlg.run()
                        dlg.destroy()
        
        dialog.destroy()

    def _ver_manual(self, btn):
        """Abre el manual PDF con el visor del sistema."""
        import subprocess
        import os
        from modelo import MANUALES_DIR
        
        manual_filename = self.e_manual.get_text().strip()
        if not manual_filename:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="No hay manual PDF seleccionado"
            )
            dlg.run()
            dlg.destroy()
            return
        
        # Construir el path completo al archivo PDF
        manual_path = os.path.join(MANUALES_DIR, manual_filename)
        
        # Verificar que el archivo exista
        if not os.path.isfile(manual_path):
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Archivo no encontrado:\n{manual_path}"
            )
            dlg.run()
            dlg.destroy()
            return
        
        # Abrir con el visor del sistema
        try:
            if os.name == "posix":  # Linux/Mac
                # Probar diferentes comandos para abrir PDF
                for cmd in ["xdg-open", "evince", "okular", "firefox", "google-chrome"]:
                    try:
                        subprocess.Popen([cmd, manual_path],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    raise FileNotFoundError("No se encontró ningún visor de PDF instalado (xdg-open, evince, okular, firefox)")
            elif os.name == "nt":  # Windows
                os.startfile(manual_path)
            else:
                subprocess.Popen(["open", manual_path],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        except Exception as e:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Error al abrir el PDF: {e}"
            )
            dlg.run()
            dlg.destroy()

    def _sel_picon(self, btn):
        """Seleccionar una foto del equipo y copiarla a picon/"""
        os.makedirs(PICON_DIR, exist_ok=True)

        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_default_size(600, 400)

        filter_img = Gtk.FileFilter()
        filter_img.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filter_img.add_pattern(pat)
        dialog.add_filter(filter_img)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos los archivos"))
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        dialog.set_current_folder(PICON_DIR)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            source_path = dialog.get_filename()
            if source_path:
                filename = os.path.basename(source_path)
                dest_path = os.path.join(PICON_DIR, filename)
                try:
                    if os.path.abspath(source_path) != os.path.abspath(dest_path):
                        shutil.copy2(source_path, dest_path)
                    self.e_picon.set_text(filename)
                    self._actualizar_picon_preview()
                except Exception as e:
                    dlg = Gtk.MessageDialog(
                        transient_for=self,
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=f"Error al copiar la foto: {e}"
                    )
                    dlg.run()
                    dlg.destroy()

        dialog.destroy()

    def _quitar_picon(self, btn):
        """Quita la referencia a la foto (no borra el archivo físico)."""
        self.e_picon.set_text("")
        self._actualizar_picon_preview()

    def _actualizar_picon_preview(self):
        """Actualiza la miniatura de vista previa de la foto del equipo."""
        filename = self.e_picon.get_text().strip()
        if filename:
            ruta = os.path.join(PICON_DIR, filename)
            if os.path.isfile(ruta):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, 140, 140, True)
                    self.img_picon.set_from_pixbuf(pixbuf)
                    return
                except Exception:
                    pass
        self.img_picon.clear()

    def _sel_marca_dropdown(self, btn):
        """Abre el ABM de Marcas para buscar/crear y seleccionar una marca."""
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_ = dlg.resultado_id
            # Recargar el combo (por si se creó una marca nueva en el ABM)
            _repopulate_combo(self.c_marca, Modelo.devolver_todas_las_marcas())
            _set_combo_id(self.c_marca, id_)
        dlg.destroy()

    def _sel_tipo_dropdown(self, btn):
        """Abre el ABM de Tipos de Equipo para buscar/crear y seleccionar un tipo."""
        dlg = TiposEquipoListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            id_ = dlg.resultado_id
            # Recargar el combo (por si se creó un tipo nuevo en el ABM)
            _repopulate_combo(self.c_tipo, Modelo.devolver_todos_los_tipos())
            _set_combo_id(self.c_tipo, id_)
        dlg.destroy()

    def _ver_conectores(self, btn):
        dlg = ConectoresListado(id_equipo=self.id_equipo, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_imagen_conectores(self, btn):
        abrir_imagen_conectores(self.id_equipo, parent=self)

    def _ver_editor_masivo_conectores(self, btn):
        def _fn_img(p):
            d = ImagenesListado(parent=p, modo_seleccion=True)
            r = None
            if d.run() == Gtk.ResponseType.OK:
                r = (d.resultado_nombre, d.resultado_id)
            d.destroy()
            return r
        abrir_editor_masivo_conectores(self.id_equipo, parent=self, fn_sel_imagen=_fn_img)

    def _ver_arbol(self, btn):
        abrir_arbol_conexiones(self.id_equipo, parent=self)

    def _ver_patcheras(self, btn):
        nombre = self.e_nombre.get_text().strip()
        abrir_patcheras(self.id_equipo, nombre_equipo=nombre, parent=self)

    def _ver_diagrama(self, btn):
        abrir_diagrama_conexiones(id_equipo=self.id_equipo, parent=self)

    def _renombrar_conectores(self, btn):
        dlg = _DialogoRenombrarConectores(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def _ver_rack(self, btn):
        """Busca el rack donde está montado este equipo (directo o dentro
        de un frame) y abre su vista gráfica. Si no está rackeado,
        muestra un diálogo avisando."""
        filas = Modelo.devolver_rack_de_equipo(self.id_equipo)
        if not filas:
            mostrar_info(self, _("Equipo no rackeado"))
            return
        id_rack = filas[0][0]
        abrir_vista_rack(id_rack=id_rack, parent=self)

    def _ver_reglas_logicas(self, btn):
        """Abre el editor de reglas lógicas (AND/OR) de este equipo."""
        nombre = self.e_nombre.get_text().strip() or f"Equipo #{self.id_equipo}"
        abrir_reglas_logicas(self.id_equipo, nombre, self.id_tipo or None, parent=self)

    def _ver_problemas(self, btn):
        """Abre el listado de problemas cargados para este equipo
        (tabla problema_equipo: categoría, gravedad y descripción)."""
        dlg = ProblemasEquipoListado(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def _actualizar_seccion_riesgo(self):
        """Pinta la sección '🔺 Riesgo de falla' con el último valor
        calculado (cacheado en riesgo_equipo_cache). No recalcula solo:
        para eso está el botón 'Recalcular'."""
        if not self.id_equipo:
            self.lbl_riesgo_score.set_text(
                _("Se calcula una vez guardado el equipo."))
            self.lbl_riesgo_detalle.set_text("")
            self.chk_equipo_critico.set_sensitive(False)
            return
        self.chk_equipo_critico.set_sensitive(True)
        self._cargando_critico = True
        self.chk_equipo_critico.set_active(Modelo.es_equipo_critico(self.id_equipo))
        self._cargando_critico = False
        fila = Modelo.devolver_riesgo_equipo(self.id_equipo)
        if not fila:
            self.lbl_riesgo_score.set_markup(
                "<i>" + _("Todavía no calculado. Usá 'Recalcular'.") + "</i>")
            self.lbl_riesgo_detalle.set_text("")
            return
        probabilidad, impacto, riesgo, nivel, detalle_json, fecha_calculo = fila
        colores_hex = {"Crítico": "#d92626", "Alto": "#e68c1a",
                       "Medio": "#e6c11a", "Bajo": "#26a642"}
        color = colores_hex.get(nivel, "#666666")
        self.lbl_riesgo_score.set_markup(
            f"<span foreground='{color}'><b>{riesgo:.0f}/100 · {nivel}</b></span>"
            f"   (Probabilidad {probabilidad:.0f} × Impacto {impacto:.0f})")
        try:
            det = json.loads(detalle_json) if detalle_json else {}
        except Exception:
            det = {}
        partes = []
        if det.get("edad_anios") is not None:
            partes.append(_("Antigüedad: {a:.1f} años (vida útil {v:.0f})").format(
                a=det["edad_anios"], v=det.get("vida_util_anios") or 0))
        else:
            partes.append(_("Antigüedad: sin fecha de fabricación cargada"))
        partes.append(_("Historial: {n} problema(s) registrados").format(
            n=det.get("cantidad_problemas", 0)))
        if det.get("equipos_impactados") is not None:
            partes.append(_("Si falla, quedan sin señal {e} equipo(s)").format(
                e=det["equipos_impactados"]))
        elif not det.get("grafo_disponible", True):
            partes.append(_("(criticidad de red no disponible en este cálculo)"))
        if det.get("modo_impacto") == "criticos":
            partes.append(_("Impacto medido sobre el conjunto crítico: "
                            "{c} de {t} crítico(s) afectado(s)").format(
                c=det.get("criticos_impactados", 0),
                t=det.get("criticos_totales", 0)))
        partes.append(_("Calculado: {f}").format(f=fecha_calculo or "—"))
        self.lbl_riesgo_detalle.set_text("  ·  ".join(partes))

    def _on_toggle_critico(self, chk):
        if getattr(self, "_cargando_critico", False) or not self.id_equipo:
            return
        Modelo.establecer_equipo_critico(self.id_equipo, chk.get_active())
        self._status_riesgo_critico(chk.get_active())

    def _status_riesgo_critico(self, activo):
        texto = (_("Marcado como equipo crítico de la cadena.") if activo
                 else _("Sacado del conjunto de equipos críticos."))
        self.lbl_riesgo_detalle.set_text(
            texto + " " + _("Usá 'Recalcular' para reflejarlo en el score."))

    def _recalcular_riesgo(self, btn):
        from risk_engine import RiskEngine
        self.set_sensitive(False)
        try:
            RiskEngine(DB_PATH).calcular_todos()
        except Exception as e:
            mostrar_error(self, f"{_('No se pudo calcular el riesgo')}:\n{e}")
        finally:
            self.set_sensitive(True)
        self._actualizar_seccion_riesgo()

    def _ver_equipos_afectados(self, btn):
        """plan_simular_remocion_cadena.md — simula la falla de este
        equipo completo y muestra qué otros equipos/cables quedan sin
        señal, y qué señales con nombre se pierden. Reemplaza la versión
        anterior (que solo listaba equipos) delegando en el mismo helper
        único de impacto_ui.py que usan Cable/Rack/Conexión — antes cada
        uno tenía su propio diálogo ad-hoc con menos información
        (faltaban cables_impactados y señales caídas)."""
        if not self.id_equipo:
            mostrar_error(self, _("Guardá el equipo primero."))
            return
        from impacto_ui import simular_remocion_y_mostrar
        nombre = self.e_nombre.get_text().strip() or f"Equipo {self.id_equipo}"
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {nombre}",
            "simular_falla_equipo", self.id_equipo)

    def _equipo_a_template(self, btn):
        """Crea un molde de catálogo (equipo_catalogo) a partir de este
        equipo: copia tipo, marca, modelo, imagen, manual y configuraciones,
        más sus conectores (nombre, tipo, imagen y coordenadas). NO copia
        inventario ni número de serie, que son propios de esta instancia."""
        if not self.id_equipo:
            return
        nombre_actual = self.e_nombre.get_text().strip() or "Equipo"
        dlg = DialogoNombre(
            _("Equipo a template"), etiqueta=_("Nombre del molde:"),
            valor=f"{nombre_actual} (molde)", parent=self)
        ok = dlg.run() == Gtk.ResponseType.OK
        valor = dlg.valor
        dlg.destroy()
        if not ok or not valor:
            return
        resultado = Modelo.crear_catalogo_desde_equipo(self.id_equipo, valor)
        if resultado:
            id_cat, n_con = resultado
            mostrar_info(self,
                f"Molde «{valor}» creado (ID {id_cat}) con {n_con} conector(es).\n\n"
                "Podés verlo/editarlo en Equipos → 📦 Catálogo de Equipos.")
        else:
            mostrar_error(self, "No se pudo crear el molde.")

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_marca = _get_combo_id(self.c_marca)
            id_tipo  = _get_combo_id(self.c_tipo)
            path_manual = self.e_manual.get_text().strip()
            picon = self.e_picon.get_text().strip()
            fecha_fabricacion = self.e_fecha_fabricacion.get_text().strip()
            es_equipo_usado = self.chk_equipo_usado.get_active()
            # Obtener texto de configuraciones desde el editor
            buf = self.tv_configuraciones_edit.get_buffer()
            start, end = buf.get_bounds()
            configuraciones = buf.get_text(start, end, False).strip()
            
            if self.id_equipo:
                Modelo.modificacion_equipo(
                    self.id_equipo,
                    id_tipo or None, id_marca or None,
                    self.e_inventario.get_text(),
                    self.e_serie.get_text(),
                    self.e_modelo.get_text(),
                    self.e_nombre.get_text(),
                    self.id_imagen or None,
                    self.e_x.get_text(), self.e_y.get_text(),
                    path_manual if path_manual else None,
                    configuraciones if configuraciones else None,
                    picon if picon else None,
                    fecha_fabricacion if fecha_fabricacion else None,
                    es_equipo_usado
                )
            else:
                Modelo.alta_equipo(
                    id_tipo or None, id_marca or None,
                    self.e_inventario.get_text(),
                    self.e_serie.get_text(),
                    self.e_modelo.get_text(),
                    self.e_nombre.get_text(),
                    self.id_imagen or None,
                    self.e_x.get_text(), self.e_y.get_text(),
                    path_manual if path_manual else None,
                    configuraciones if configuraciones else None,
                    picon if picon else None,
                    fecha_fabricacion if fecha_fabricacion else None,
                    es_equipo_usado
                )
        
        # Limpiar buffers de TextView para liberar memoria antes de destruir
        try:
            self.tv_configuraciones_edit.get_buffer().set_text("")
            self.tv_configuraciones_view.get_buffer().set_text("")
        except Exception:
            pass  # Ignorar errores si los widgets ya no existen
        
        self.destroy()


# ─── Cables ───────────────────────────────────────────────────────────────────

class CablesListado(VentanaListado):
    """
    Listado de cables con:
    - Columnas: ID, Código, Longitud, Estado, Conexiones
    - Filas coloreadas según estado (TEMPORAL=amarillo, EN_REVISION=violeta,
      1 extremo=naranja, sin conexiones=rojo suave)
    - Filtro rápido por estado
    - Botón "Nuevo Temporal" (código auto-generado)
    - Botón "Fusionar" para unir dos cables temporales
    """

    # Colores RGBA por estado
    _COLORES = {
        "TEMPORAL":   Gdk.RGBA(1.0,  0.93, 0.60, 1.0),   # amarillo
        "EN_REVISION":Gdk.RGBA(0.87, 0.82, 1.0,  1.0),   # violeta
        "FUSIONADO":  Gdk.RGBA(0.75, 0.75, 0.75, 1.0),   # gris
        "VERIFICADO": None,                                # sin color
        "1_EXTREMO":  Gdk.RGBA(1.0,  0.85, 0.70, 1.0),   # naranja
        "SIN_CONN":   Gdk.RGBA(1.0,  0.80, 0.80, 1.0),   # rojo suave
    }

    def __init__(self, parent=None, modo_seleccion=False):
        botones_extra = [
            ("⚡ Nuevo Temporal", self._nuevo_temporal),
            ("🔀 Fusionar",       self._fusionar),
            ("🩺 Historial de diagnósticos", self._ver_historial_diagnosticos),
            ("📋 Ver incidentes", self._ver_bitacora_incidentes),
        ]
        super().__init__(
            _("Cables"),
            [_("ID"), _("Código"), _("Long."), _("Estado"), _("Extremos")],
            parent=parent,
            modo_seleccion=modo_seleccion,
            botones_extra=botones_extra,
        )
        self.resultado_codigo = None
        self._filtro_estado = "TODOS"
        self._color_col_agregada = False
        self._agregar_filtros_estado()
        self.cargar_datos()

    def _agregar_filtros_estado(self):
        """Agrega botonera de filtro rápido por estado encima del TreeView."""
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hb.set_margin_start(6); hb.set_margin_end(6)
        hb.set_margin_top(2);   hb.set_margin_bottom(4)
        lbl = Gtk.Label(label=_("Estado:"))
        lbl.set_margin_end(4)
        hb.pack_start(lbl, False, False, 0)
        opciones = [
            (_("Todos"),        "TODOS"),
            (_("Temporales"),   "TEMPORAL"),
            (_("En revisión"),  "EN_REVISION"),
            ("1 extremo",    "1_EXTREMO"),
            (_("Sin conexión"), "SIN_CONN"),
            (_("Verificados"),  "VERIFICADO"),
        ]
        primero = None
        for lbl_txt, valor in opciones:
            rb = Gtk.RadioButton.new_with_label_from_widget(primero, lbl_txt)
            if primero is None:
                primero = rb
            rb.connect("toggled", self._on_filtro_estado, valor)
            hb.pack_start(rb, False, False, 0)
        # Insertar en content_area en posición 1
        # (0 = barra búsqueda, 1 = aquí, 2 = ScrolledWindow con tv, 3 = botones)
        ca = self.get_content_area()
        ca.pack_start(hb, False, False, 0)
        # Reordenar: buscar el ScrolledWindow y poner hb antes
        children = ca.get_children()
        sw_idx = next((i for i, c in enumerate(children)
                       if isinstance(c, Gtk.ScrolledWindow)), 1)
        ca.reorder_child(hb, sw_idx)
        hb.show_all()

    def _on_filtro_estado(self, rb, valor):
        if rb.get_active():
            self._filtro_estado = valor
            self.cargar_datos()

    def _on_seleccionar(self, btn):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[1]
            self.resultado_codigo = f[1]
            self.response(Gtk.ResponseType.OK)

    def cargar_datos(self):
        todos = Modelo.devolver_todos_los_cables()
        # Filtrar según estado seleccionado
        if self._filtro_estado == "TODOS":
            filas = todos
        elif self._filtro_estado == "1_EXTREMO":
            filas = [r for r in todos if int(r[4] or 0) == 1]
        elif self._filtro_estado == "SIN_CONN":
            filas = [r for r in todos if int(r[4] or 0) == 0]
        else:
            filas = [r for r in todos if s(r[3]) == self._filtro_estado]
        # _colorear_filas puebla el store y aplica colores
        self._colorear_filas(filas)

    def _colorear_filas(self, filas):
        """Puebla el store aplicando colores según estado y conexiones."""
        self.store.clear()
        n = len(self.columnas)
        for r in filas:
            # r: (id, codigo, longitud, estado, n_conexiones)
            estado = s(r[3])
            n_cx   = int(r[4]) if r[4] is not None else 0
            
            fila_str = [s(v) for v in list(r)[:n]]
            while len(fila_str) < n:
                fila_str.append("")
                
            color = "#ffffff"
            if estado == "TEMPORAL":
                color = "#fae69a"
            elif estado == "EN_REVISION":
                color = "#ded8ff"
            elif estado == "FUSIONADO":
                color = "#c0c0c0"
            elif n_cx == 0:
                color = "#ffcccc"
            elif n_cx == 1:
                color = "#ffd9b3"
                
            self.store.append(fila_str + [color])

    def nuevo(self):
        dlg = _DialogoCable(parent=self)
        dlg.run_and_destroy()

    def _nuevo_temporal(self, *a):
        """Crea un cable con código temporal auto-generado."""
        codigo = Modelo.siguiente_codigo_temporal()
        Modelo.agregar_cable(
            codigo=codigo,
            longitud=None, id_tipo_cable=None, id_tipo_ficha=None,
            unidad_longitud=None, metraje_ext1=None, metraje_ext2=None,
            unidad_metraje=None, estado="TEMPORAL",
        )
        self.cargar_datos()
        mostrar_info(self, f"Cable temporal creado: {codigo}\n\n"
                          "Podés editarlo para agregar tipo, notas y conexiones.")

    def editar(self, id_):
        dlg = _DialogoCable(id_cable=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_cable(id_)

    def _fusionar(self, *a):
        """Abre el diálogo de fusión de cables."""
        filas_sel = self._filas_seleccionadas()
        if len(filas_sel) < 2:
            mostrar_error(self, "Seleccioná exactamente dos cables para fusionar.\n"
                               "(Usá Ctrl+clic para seleccionar múltiples filas.)")
            return
        if len(filas_sel) > 2:
            mostrar_error(self, "Seleccioná exactamente dos cables.")
            return
        id_a, codigo_a = filas_sel[0][0], filas_sel[0][1]
        id_b, codigo_b = filas_sel[1][0], filas_sel[1][1]
        dlg = _DialogoFusion(id_a, codigo_a, id_b, codigo_b, parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _ver_historial_diagnosticos(self, *a):
        """'Prontuario' del cable seleccionado — fallas recurrentes en el
        mismo tramo (ver plan_asistente_diagnostico_fallas.md)."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un cable primero.")
            return
        abrir_historial_diagnosticos(DB_PATH, parent=self, id_cable=f[0])

    def _ver_bitacora_incidentes(self, *a):
        """Bitácora de incidentes del cable seleccionado (ver
        plan_bitacora_incidentes_riesgo_analogico.md)."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un cable primero.")
            return
        from bitacora_ui import abrir_bitacora_incidentes
        abrir_bitacora_incidentes(parent=self, id_cable=f[0])

    def _filas_seleccionadas(self):
        """Retorna lista de filas seleccionadas (soporta selección múltiple)."""
        sel = self.tv.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        store, paths = sel.get_selected_rows()
        result = []
        for path in paths:
            it = store.get_iter(path)
            row = [store.get_value(it, c) for c in range(len(self.columnas))]
            result.append(row)
        return result


class _DialogoFusion(Gtk.Dialog):
    """Diálogo para fusionar dos cables temporales en uno definitivo."""

    def __init__(self, id_a, codigo_a, id_b, codigo_b, parent=None):
        super().__init__(title=_("Fusionar Cables"), transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "✔ Confirmar Fusión", Gtk.ResponseType.OK)
        self.set_default_size(480, 320)
        self.id_a = id_a; self.id_b = id_b

        ca = self.get_content_area()
        ca.set_spacing(8); ca.set_margin_start(12); ca.set_margin_end(12)
        ca.set_margin_top(10); ca.set_margin_bottom(10)

        # Descripción
        info = Gtk.Label()
        info.set_markup(
            f"<b>Cable principal:</b>  {codigo_a}  (ID {id_a})\n"
            f"<b>Cable secundario:</b> {codigo_b}  (ID {id_b})\n\n"
            "Las conexiones del secundario pasarán al principal.\n"
            "El secundario quedará marcado como <i>FUSIONADO</i> (no se borra)."
        )
        info.set_line_wrap(True); info.set_xalign(0)
        ca.pack_start(info, False, False, 0)

        sep = Gtk.Separator(); ca.pack_start(sep, False, False, 4)

        g = _grid()
        _lbl_entry(g, _("Código definitivo:"), 0)
        self.e_codigo = _entry(g, 0)
        self.e_codigo.set_text(codigo_a)
        self.e_codigo.set_placeholder_text("Escribí el código final del cable")

        _lbl_entry(g, _("Estado final:"), 1)
        self.combo_estado = Gtk.ComboBoxText()
        for opt in ["VERIFICADO", "TEMPORAL"]:
            self.combo_estado.append_text(opt)
        self.combo_estado.set_active(0)
        g.attach(self.combo_estado, 1, 1, 2, 1)

        ca.pack_start(g, False, False, 0)
        self.show_all()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            codigo = self.e_codigo.get_text().strip()
            estado = self.combo_estado.get_active_text()
            if not codigo:
                mostrar_error(self, "El código definitivo no puede estar vacío.")
            else:
                Modelo.fusionar_cables(
                    self.id_a, self.id_b, codigo, estado
                )
                mostrar_info(self,
                    f"Fusión completada.\n"
                    f"Cable definitivo: {codigo} (ID {self.id_a})\n"
                    f"Cable {self.id_b} marcado como FUSIONADO.")
        self.destroy()


class _DialogoEligeLadoFantasma(Gtk.Dialog):
    """plan_desarrollo_fantasma_rapido.md — mini-diálogo para elegir qué
    extremo (A/B) del cable se está documentando como desconectado.
    Sólo se muestra cuando el cable no tiene ningún extremo cargado
    todavía; con un extremo ya cargado el lado se infiere solo (ver
    _DialogoCable._marcar_extremo_desconectado)."""

    RESP_A = 1
    RESP_B = 2

    def __init__(self, parent):
        super().__init__(title=_("Marcar extremo desconectado"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Extremo A  (queda OUT)"), self.RESP_A)
        self.add_button(_("Extremo B  (queda IN)"), self.RESP_B)

        ca = self.get_content_area()
        ca.set_margin_start(14); ca.set_margin_end(14)
        ca.set_margin_top(12);   ca.set_margin_bottom(6)
        lbl = Gtk.Label(label=_(
            "¿Qué extremo del cable estás documentando como "
            "desconectado?"))
        lbl.set_line_wrap(True)
        lbl.set_xalign(0)
        ca.pack_start(lbl, False, False, 0)
        self.show_all()


class _DialogoCable(Gtk.Dialog):
    def __init__(self, id_cable=None, parent=None):
        titulo = _("Editar Cable") if id_cable else _("Nuevo Cable")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(500, 480)
        self.id_cable = id_cable
        self.id_tipo_cable = ""
        self.id_tipo_ficha = ""

        ca = self.get_content_area()
        ca.set_margin_start(10); ca.set_margin_end(10)
        ca.set_margin_top(8);    ca.set_margin_bottom(8)

        g = _grid()
        _lbl_entry(g, _("Código:"), 0)
        # Fila código con botón "Generar temporal"
        hb_cod = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.e_codigo = Gtk.Entry(); self.e_codigo.set_hexpand(True)
        btn_temp = Gtk.Button(label=_("⚡ Temporal"))
        btn_temp.set_tooltip_text(_("Asignar código temporal auto-generado"))
        btn_temp.connect("clicked", self._asignar_temporal)
        hb_cod.pack_start(self.e_codigo, True, True, 0)
        hb_cod.pack_start(btn_temp, False, False, 0)
        g.attach(hb_cod, 1, 0, 2, 1)

        _lbl_entry(g, _("Estado:"), 1)
        self.combo_estado = Gtk.ComboBoxText()
        for opt in ["VERIFICADO", "TEMPORAL", "EN_REVISION"]:
            self.combo_estado.append_text(opt)
        self.combo_estado.set_active(0)
        g.attach(self.combo_estado, 1, 1, 2, 1)

        _lbl_entry(g, _("Tipo cable:"), 2)
        self.c_tipo_cable = _searchable_combo(g, 2, Modelo.devolver_todos_los_tipos_cable())
        _lbl_entry(g, _("Tipo ficha:"), 3)
        self.c_tipo_ficha = _searchable_combo(g, 3, Modelo.devolver_todos_los_tipos_ficha())
        _lbl_entry(g, _("Longitud:"), 4)
        self.e_longitud = _entry(g, 4)
        _lbl_entry(g, _("Unidad long.:"), 5)
        self.e_unidad = _entry(g, 5)
        _lbl_entry(g, _("Metraje ext. 1:"), 6)
        self.e_met1 = _entry(g, 6)
        _lbl_entry(g, _("Metraje ext. 2:"), 7)
        self.e_met2 = _entry(g, 7)
        _lbl_entry(g, _("Unidad metraje:"), 8)
        self.e_unidad_met = _entry(g, 8)

        # Override de ancho de banda (plan_riesgo_senal_audio.md, riesgo #2)
        # — sólo para el patchcord puntual que no representa a su tipo
        # nominal; el default sale de tipo_cable.ancho_banda_mhz. Sólo
        # tiene sentido con el cable ya guardado.
        self.e_ancho_banda_override = None
        if id_cable:
            _lbl_entry(g, _("Ancho de banda (override, MHz):"), 9)
            self.e_ancho_banda_override = _entry(g, 9)
            self.e_ancho_banda_override.set_tooltip_text(
                _("Vacío = usar el default de su tipo de cable. Cargar sólo "
                  "si ESTE cable puntual no representa a su tipo nominal "
                  "(ej. un patchcord viejo/degradado)."))
            fila_boton_conex = 10
        else:
            fila_boton_conex = 9

        if id_cable:
            btn_conex = Gtk.Button(label=_("🔗 Ver Conexiones"))
            btn_conex.set_tooltip_text(_("Ver todas las conexiones asociadas a este cable"))
            btn_conex.connect("clicked", self._ver_conexiones)
            g.attach(btn_conex, 1, fila_boton_conex, 2, 1)

            # plan_simular_remocion_cadena.md
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se desconecta "
                "este cable (no destructivo, no toca la base)."))
            btn_remocion.connect("clicked", self._simular_remocion)
            g.attach(btn_remocion, 1, fila_boton_conex + 1, 2, 1)

            # plan_desarrollo_extension_cable.md — empalme ficha-contra-
            # ficha con otro cable, sin equipo ni barril de por medio.
            btn_extender = Gtk.Button(label=_("🔗 Extender con otro cable"))
            btn_extender.set_tooltip_text(_(
                "Cargar un punto donde este cable se empalma directamente "
                "con la ficha de otro cable (tramo intermedio de la cadena "
                "analógica, sin equipo de por medio)."))
            btn_extender.connect("clicked", self._extender_cable)
            g.attach(btn_extender, 1, fila_boton_conex + 2, 2, 1)

            # Ajuste de usabilidad post-uso real: ver de un vistazo el
            # recorrido real completo de este cable, atravesando
            # cualquier extensión de por medio, hasta el equipo real de
            # cada punta (o hasta un extremo suelto si la cadena está
            # incompleta) — ver plan_desarrollo_extension_cable.md.
            btn_cadena = Gtk.Button(label=_("🔗 Ver cadena completa"))
            btn_cadena.set_tooltip_text(_(
                "Ver el recorrido real completo de este cable: equipo → "
                "cable → extensión → cable → ... → equipo, atravesando "
                "cualquier extensión intermedia."))
            btn_cadena.connect("clicked", self._ver_cadena_cable)
            g.attach(btn_cadena, 1, fila_boton_conex + 3, 2, 1)

            # plan_desarrollo_fantasma_rapido.md — alta rápida de un
            # equipo FANTASMA para documentar un extremo de cable
            # confirmado desconectado, sin tipeo manual del nombre ni
            # elección forzada de IN/OUT.
            btn_fantasma = Gtk.Button(label=_("🔌 Marcar extremo desconectado"))
            btn_fantasma.set_tooltip_text(_(
                "Documentar que recorriste este cable hasta el final y "
                "confirmaste que ese extremo está suelto: crea un equipo "
                "FANTASMA con el nombre y el conector ya armados, sin "
                "pedir Marca/Modelo/Inventario/Serie."))
            btn_fantasma.connect("clicked", self._marcar_extremo_desconectado)
            g.attach(btn_fantasma, 1, fila_boton_conex + 4, 2, 1)
            self._btn_fantasma = btn_fantasma
            self._actualizar_estado_btn_fantasma()

        ca.pack_start(g, False, False, 0)

        # ── Armado (plan_bitacora_incidentes_riesgo_analogico.md §3.3) ──
        # A nivel de CABLE completo (a diferencia de la sección "Armado"
        # de _DialogoConector, que es por extremo) — para cuando no está
        # claro cuál de los dos extremos es el problema.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_cable:
            Modelo.asegurar_tablas_bitacora()
            frame_armado = Gtk.Frame(label=" " + _("Armado") + " ")
            g5 = _grid()
            _lbl_entry(g5, _("¿Armado correcto?:"), 0)
            self.c_armado = Gtk.ComboBoxText()
            self.c_armado.append("", _("No verificado"))
            self.c_armado.append("1", _("Correcto"))
            self.c_armado.append("0", _("Mal armado"))
            g5.attach(self.c_armado, 1, 0, 2, 1)
            _lbl_entry(g5, _("Detalle:"), 1)
            self.e_detalle_armado = _entry(g5, 1)
            frame_armado.add(g5)
            ca.pack_start(frame_armado, False, False, 6)

        # Notas de relevamiento
        sep = Gtk.Separator(); ca.pack_start(sep, False, False, 6)
        lbl_notas = Gtk.Label(label=_("Notas de relevamiento:"))
        lbl_notas.set_xalign(0); lbl_notas.set_margin_start(4)
        ca.pack_start(lbl_notas, False, False, 0)
        scroll_n = Gtk.ScrolledWindow()
        scroll_n.set_min_content_height(70)
        self.tv_notas = Gtk.TextView()
        self.tv_notas.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_notas.get_buffer().set_text("")
        scroll_n.add(self.tv_notas)
        ca.pack_start(scroll_n, True, True, 0)

        if id_cable:
            rows = Modelo.devolver_cable(id_cable)
            if rows:
                r = rows[0]
                # 0:id 1:codigo 2:id_tipo_cable 3:nombre_tipo_cable
                # 4:id_tipo_ficha 5:nombre_tipo_ficha 6:longitud
                # 7:unidad_longitud 8:metraje_ext1 9:unidad_metraje
                # 10:metraje_ext2 11:estado 12:notas_relevamiento
                self.e_codigo.set_text(s(r[1]))
                _set_combo_id(self.c_tipo_cable, s(r[2]))
                _set_combo_id(self.c_tipo_ficha, s(r[4]))
                self.e_longitud.set_text(s(r[6]))
                self.e_unidad.set_text(s(r[7]))
                self.e_met1.set_text(s(r[8]))
                self.e_unidad_met.set_text(s(r[9]))
                self.e_met2.set_text(s(r[10]))
                estado = s(r[11]) or "VERIFICADO"
                opciones = ["VERIFICADO", "TEMPORAL", "EN_REVISION"]
                if estado in opciones:
                    self.combo_estado.set_active(opciones.index(estado))
                notas = s(r[12])
                if notas:
                    self.tv_notas.get_buffer().set_text(notas)
                if self.e_ancho_banda_override is not None:
                    ancho_ov = Modelo.devolver_ancho_banda_override_cable(id_cable)
                    self.e_ancho_banda_override.set_text(_fmt_float_opt(ancho_ov))

                if self.c_armado is not None:
                    fila_arm = Modelo._query(
                        "SELECT es_armado_correcto, detalle_armado FROM cable "
                        "WHERE id_cable=?", (id_cable,))
                    if fila_arm and fila_arm[0][0] is not None:
                        self.c_armado.set_active_id(str(int(fila_arm[0][0])))
                    else:
                        self.c_armado.set_active_id("")
                    if fila_arm and fila_arm[0][1]:
                        self.e_detalle_armado.set_text(s(fila_arm[0][1]))

        _pack_ultima_edicion(self, "cable", "id_cable", id_cable)
        self.show_all()

    def _asignar_temporal(self, btn):
        codigo = Modelo.siguiente_codigo_temporal()
        self.e_codigo.set_text(codigo)
        opciones = ["VERIFICADO", "TEMPORAL", "EN_REVISION"]
        self.combo_estado.set_active(opciones.index("TEMPORAL"))

    def _ver_conexiones(self, btn):
        dlg = ConexionesListado(parent=self, id_cable=self.id_cable)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _simular_remocion(self, btn):
        """plan_simular_remocion_cadena.md — delega en el helper único de
        impacto_ui.py (mismo que usan Equipo/Rack/Conexión) para no
        repetir la construcción del analyzer ni el manejo de errores."""
        from impacto_ui import simular_remocion_y_mostrar
        rows = Modelo.devolver_cable(self.id_cable)
        codigo = s(rows[0][1]) if rows else self.id_cable
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {codigo}",
            "simular_desconexion", self.id_cable)

    def _extender_cable(self, btn):
        """plan_desarrollo_extension_cable.md — abre el alta de extensión
        con este cable ya fijado como Extremo A."""
        from extension_cable_ui import abrir_extender_cable
        abrir_extender_cable(parent=self, id_cable=self.id_cable)

    def _ver_cadena_cable(self, btn):
        """Ajuste de usabilidad post-uso real — ver PROGRESS.md."""
        from extension_cable_ui import abrir_ver_cadena
        abrir_ver_cadena(parent=self, id_cable=self.id_cable)

    def _actualizar_estado_btn_fantasma(self):
        """plan_desarrollo_fantasma_rapido.md — deshabilita el botón si el
        cable ya tiene sus dos extremos cargados (no queda ningún lado
        'suelto' para documentar como FANTASMA)."""
        extremos = Modelo.devolver_extremos_de_cable(self.id_cable)
        if len(extremos) >= 2:
            self._btn_fantasma.set_sensitive(False)
            self._btn_fantasma.set_tooltip_text(
                _("Este cable ya tiene sus dos extremos documentados."))

    def _marcar_extremo_desconectado(self, btn):
        """plan_desarrollo_fantasma_rapido.md — alta rápida de un equipo
        FANTASMA para documentar un extremo de este cable confirmado
        desconectado: nombre y conector se generan solos (sin tipeo ni
        elección manual de IN/OUT), reemplazando el alta pesada de
        _DialogoEquipo completo + plantilla de nombre a mano fuera del
        sistema."""
        extremos = Modelo.devolver_extremos_de_cable(self.id_cable)
        if len(extremos) >= 2:
            mostrar_info(self, _(
                "Este cable ya tiene sus dos extremos documentados."))
            return

        # Con un extremo ya cargado, el lado se infiere solo (A↔B, OUT↔IN)
        # — sólo se pregunta cuando no hay ninguna referencia (0 extremos)
        # o cuando el único extremo existente es un extremo "suelto" de
        # una Extensión (sin conector, no se puede inferir el tipo).
        lado = None
        if len(extremos) == 1:
            _id_conexion, _id_conector, _id_tipo_conector, nombre_tipo = extremos[0]
            if nombre_tipo == "OUT":
                lado = "B"
            elif nombre_tipo == "IN":
                lado = "A"

        if lado is None:
            dlg = _DialogoEligeLadoFantasma(self)
            resp = dlg.run()
            dlg.destroy()
            if resp == _DialogoEligeLadoFantasma.RESP_A:
                lado = "A"
            elif resp == _DialogoEligeLadoFantasma.RESP_B:
                lado = "B"
            else:
                return  # canceló

        tipo_conector_nombre = "OUT" if lado == "A" else "IN"

        id_tipo_equipo_fantasma = Modelo.devolver_id_tipo_equipo_fantasma()
        if not id_tipo_equipo_fantasma:
            mostrar_error(self, _(
                "No hay ningún tipo de equipo con rol FANTASMA en el "
                "catálogo. Marcá uno (Equipos → Tipos de equipo) antes "
                "de usar esta acción rápida."))
            return

        id_tipo_conector = Modelo.devolver_id_tipo_conector_por_nombre(
            tipo_conector_nombre)
        if not id_tipo_conector:
            mostrar_error(self, _(
                "No hay ningún tipo de conector llamado '{tipo}' en el "
                "catálogo.").format(tipo=tipo_conector_nombre))
            return

        codigo_cable = self.e_codigo.get_text().strip() or f"#{self.id_cable}"
        nombre_equipo = f"EXTREMO {lado} DESCONECTADO {codigo_cable}"

        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo_fantasma, None, None, None, None, nombre_equipo,
            None, None, None)
        id_conector = Modelo.agregar_conector_retorna_id(
            tipo_conector_nombre, id_equipo, id_tipo_conector, None, None, None)
        Modelo.alta_conexion(self.id_cable, id_conector)

        mostrar_info(self, _(
            "Se creó el equipo '{nombre}' con su conector {tipo} ya "
            "conectado a este cable.\n\nA continuación se abren su ficha "
            "(para la ubicación en el plano) y su conector (para la foto "
            "de la ficha) — cancelá cualquiera de las dos si no las "
            "necesitás ahora.").format(nombre=nombre_equipo,
                                        tipo=tipo_conector_nombre))

        dlg_equipo = _DialogoEquipo(id_equipo=id_equipo, parent=self)
        dlg_equipo.run_and_destroy()

        dlg_conector = _DialogoConector(
            id_conector=id_conector, id_equipo=id_equipo, parent=self)
        dlg_conector.run_and_destroy()

        self._actualizar_estado_btn_fantasma()

    def _get_notas(self):
        buf = self.tv_notas.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip() or None

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_tipo_cable = _get_combo_id(self.c_tipo_cable)
            id_tipo_ficha = _get_combo_id(self.c_tipo_ficha)
            args = (
                self.e_codigo.get_text(),
                self.e_longitud.get_text(),
                id_tipo_cable or None,
                id_tipo_ficha or None,
                self.e_unidad.get_text(),
                self.e_met1.get_text(),
                self.e_met2.get_text(),
                self.e_unidad_met.get_text(),
                self.combo_estado.get_active_text() or "VERIFICADO",
                self._get_notas(),
            )
            if self.id_cable:
                Modelo.modificar_cable(self.id_cable, *args)
                if self.e_ancho_banda_override is not None:
                    Modelo.establecer_ancho_banda_override_cable(
                        self.id_cable, _parse_float_opt(self.e_ancho_banda_override.get_text()))
                if self.c_armado is not None:
                    id_arm = self.c_armado.get_active_id()
                    es_correcto = None if not id_arm else bool(int(id_arm))
                    detalle_arm = self.e_detalle_armado.get_text().strip() or None
                    Modelo.establecer_armado_cable(
                        self.id_cable, es_correcto, detalle_arm)
            else:
                Modelo.agregar_cable(*args)
        self.destroy()


# ─── Conexiones ───────────────────────────────────────────────────────────────

class ConexionesListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False, id_cable=None):
        self.id_cable_filtro = id_cable
        super().__init__(
            _("Conexiones"),
            [_("ID"), _("Equipo"), _("Conector"), _("Tipo Conector"),
             _("Tipo Equipo"), _("Cable")],
            parent=parent, modo_seleccion=modo_seleccion
        )
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_todas_las_conexiones(self.id_cable_filtro)
        # Reordenar columnas para el display:
        # BD: id, equipo, conector, cable, tipo_conector, tipo_equipo, ...
        # Display: ID, Equipo, Conector, TipoConector, TipoEquipo, Cable
        data = []
        for r in rows:
            (id_conexion, equipo_nombre, conector_nombre, cable_codigo,
             tipo_conector, tipo_equipo, _id_cable, id_conector,
             _id_equipo) = r[:9]
            if id_conector is None:
                # Extremo suelto (plan_desarrollo_extension_cable.md): no
                # termina en un conector de equipo — se empalma con otro
                # cable a través de una Extensión. CONEXIONES trae estas
                # columnas en blanco porque hace LEFT JOIN contra
                # conector→equipo; se completa acá en el display, sin
                # tocar esa vista (la comparten otros consumidores, ver
                # PROGRESS.md).
                id_ext = Modelo.devolver_extension_de_conexion(id_conexion)
                equipo_nombre = (
                    _("(extremo suelto — Extensión #{})").format(id_ext)
                    if id_ext else
                    _("(extremo suelto — sin extensión asociada)"))
                ficha = Modelo.devolver_ficha_de_conexion(id_conexion)
                conector_nombre = ficha or _("(ficha sin especificar)")
                tipo_conector = "—"
                tipo_equipo = "—"
            data.append([id_conexion, equipo_nombre, conector_nombre,
                        tipo_conector, tipo_equipo, cable_codigo])
        self._poblar(data)

    def nuevo(self):
        dlg = _DialogoConexion(parent=self, id_cable_predef=self.id_cable_filtro)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConexion(id_conexion=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conexion(id_)


class _DialogoConexion(Gtk.Dialog):
    def __init__(self, id_conexion=None, parent=None, id_cable_predef=None):
        titulo = _("Editar Conexión") if id_conexion else _("Nueva Conexión")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 240)
        self.id_conexion = id_conexion
        self.id_cable = id_cable_predef or ""
        self.id_conector = ""
        self.id_equipo = ""

        g = _grid()
        _lbl_entry(g, _("Equipo:"), 0)
        self.e_equipo = _entry_btn(g, 0, "…", self._sel_equipo)
        _lbl_entry(g, _("Conector:"), 1)
        self.c_conector = _searchable_combo(g, 1, [])
        _lbl_entry(g, _("Cable:"), 2)
        self.e_cable = _entry_btn(g, 2, "…", self._sel_cable)

        # Ficha propia del cable en esta punta (plan_riesgo_senal_audio.md)
        # — distinto de la ficha que declara el jack del equipo. Sólo
        # tiene sentido con la conexión ya guardada.
        self.c_ficha_cable = None
        if id_conexion:
            _lbl_entry(g, _("Ficha del cable en esta punta:"), 3)
            self.c_ficha_cable = _searchable_combo(
                g, 3, Modelo.devolver_todos_los_tipos_ficha())
            self.c_ficha_cable.set_tooltip_text(
                _("Qué ficha es físicamente el extremo del cable que llega "
                  "acá (ej. XLR3 macho, TS) — puede ser distinta de la "
                  "ficha que espera el jack del equipo. Usado por el "
                  "análisis de riesgo de señal para detectar cortocircuito "
                  "por conductores insuficientes."))

        self.get_content_area().add(g)

        # ── Armado POR EXTREMO (plan_bitacora_incidentes_riesgo_analogico.md
        # §3.3, extendido en sesión posterior) — a diferencia de "Armado" en
        # _DialogoCable (todo el cable), esto es sólo la punta que llega a
        # esta conexión puntual. Caso real que lo motivó: un cable con XLR3
        # bien armado de un lado y TRS mal armado (cruce de conductores) del
        # otro — "Armado" a nivel cable no puede distinguir cuál extremo es.
        # Sólo tiene sentido con la conexión ya guardada.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_conexion:
            Modelo.asegurar_tablas_bitacora()
            frame_armado = Gtk.Frame(label=" " + _("Armado de esta punta") + " ")
            g5 = _grid()
            _lbl_entry(g5, _("¿Armado correcto?:"), 0)
            self.c_armado = Gtk.ComboBoxText()
            self.c_armado.append("", _("No verificado"))
            self.c_armado.append("1", _("Correcto"))
            self.c_armado.append("0", _("Mal armado"))
            g5.attach(self.c_armado, 1, 0, 2, 1)
            _lbl_entry(g5, _("Detalle:"), 1)
            self.e_detalle_armado = _entry(g5, 1)
            self.e_detalle_armado.set_placeholder_text(
                _("ej. \"cruce de conductores, pin 2 y 3 al mismo orificio\""))
            frame_armado.add(g5)
            self.get_content_area().pack_start(frame_armado, False, False, 6)

        if id_conexion:
            rows = Modelo.devolver_conexion(id_conexion)
            if rows:
                r = rows[0]
                self.id_equipo = s(r[8])
                self.e_equipo.set_text(s(r[1]))
                # Cargar conectores del equipo para el combo
                _repopulate_combo(self.c_conector, Modelo.devolver_conectores_de_equipo(self.id_equipo))
                _set_combo_id(self.c_conector, s(r[7]))
                self.e_cable.set_text(s(r[3]))
                self.id_cable = s(r[6])
                if self.c_ficha_cable is not None:
                    id_tf_actual = Modelo.devolver_ficha_conexion(id_conexion)
                    if id_tf_actual:
                        _set_combo_id(self.c_ficha_cable, id_tf_actual)
                if self.c_armado is not None:
                    es_correcto, detalle = Modelo.devolver_armado_conexion(id_conexion)
                    self.c_armado.set_active_id(
                        str(int(es_correcto)) if es_correcto is not None else "")
                    if detalle:
                        self.e_detalle_armado.set_text(s(detalle))
        elif id_cable_predef:
            # Cargar nombre del cable predefinido
            c_rows = Modelo.devolver_cable(id_cable_predef)
            if c_rows:
                self.e_cable.set_text(s(c_rows[0][1])) # index 1 es codigo

        # plan_simular_remocion_cadena.md — sólo tiene sentido con la
        # conexión ya guardada (necesita id_conexion para resolver el
        # cable en graph_impact.py).
        if id_conexion:
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se desconecta "
                "esta punta (equivale a cortar el cable entero: el grafo "
                "de señal no modela extremos sueltos). No destructivo."))
            btn_remocion.connect("clicked", self._simular_remocion)
            self.get_content_area().pack_start(btn_remocion, False, False, 4)

        _pack_ultima_edicion(self, "conexion", "id_conexion", id_conexion)
        self.show_all()

    def _simular_remocion(self, btn):
        from impacto_ui import simular_remocion_y_mostrar
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — Conexión #{self.id_conexion}",
            "simular_perdida_conexion", self.id_conexion)

    def _sel_equipo(self, btn):
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.e_equipo.set_text(dlg.resultado_nombre)
            # Re-poblar combo de conectores
            _repopulate_combo(self.c_conector, Modelo.devolver_conectores_de_equipo(self.id_equipo))
            self.c_conector.get_child().set_text("")
        dlg.destroy()

    def _sel_cable(self, btn):
        dlg = CablesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_cable = dlg.resultado_id
            self.e_cable.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_conector = _get_combo_id(self.c_conector)
            if self.id_conexion:
                Modelo.modificacion_conexion(
                    self.id_conexion,
                    self.id_cable or None,
                    id_conector or None, 0
                )
                if self.c_ficha_cable is not None:
                    Modelo.establecer_ficha_conexion(
                        self.id_conexion, _get_combo_id(self.c_ficha_cable) or None)
                if self.c_armado is not None:
                    id_activo = self.c_armado.get_active_id()
                    es_correcto = None if not id_activo else bool(int(id_activo))
                    detalle_arm = self.e_detalle_armado.get_text().strip() or None
                    Modelo.establecer_armado_conexion(self.id_conexion, es_correcto, detalle_arm)
            else:
                Modelo.alta_conexion(
                    self.id_cable or None,
                    id_conector or None, 0
                )
        self.destroy()


# ─── Racks ────────────────────────────────────────────────────────────────────

class RacksListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Racks"), [_("ID"), _("Número"), _("Nombre"), _("Capacidad (UR)")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def _on_seleccionar(self, btn):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[2]  # nombre en columna 2
            self.response(Gtk.ResponseType.OK)

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_racks())

    def nuevo(self):
        dlg = _DialogoRack(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoRack(id_rack=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_rack(id_)


class _DialogoRack(Gtk.Dialog):
    def __init__(self, id_rack=None, parent=None):
        titulo = _("Editar Rack") if id_rack else _("Nuevo Rack")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(380, 220)
        self.id_rack = id_rack

        g = _grid()
        _lbl_entry(g, _("Número:"), 0); self.e_numero = _entry(g, 0)
        _lbl_entry(g, _("Nombre:"), 1); self.e_nombre = _entry(g, 1)
        _lbl_entry(g, _("Capacidad (UR):"), 2); self.e_cap = _entry(g, 2)
        self.get_content_area().add(g)

        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                r = rows[0]
                self.e_numero.set_text(s(r[1]))
                self.e_nombre.set_text(s(r[2]))
                self.e_cap.set_text(s(r[3]))

        # Botón de dispositivos en rack
        if id_rack:
            btn = Gtk.Button(label=_("📦 Dispositivos en este rack"))
            btn.connect("clicked", self._ver_dispositivos)
            self.get_content_area().pack_start(btn, False, False, 0)
            btn_vista = Gtk.Button(label=_("🖼 Vista gráfica del rack"))
            btn_vista.connect("clicked", self._ver_vista_rack)
            self.get_content_area().pack_start(btn_vista, False, False, 0)

            # plan_simular_remocion_cadena.md — corte de energía del rack
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se corta la "
                "energía de todo el rack (equipos directos + equipos "
                "dentro de sus frames). No destructivo."))
            btn_remocion.connect("clicked", self._simular_remocion)
            self.get_content_area().pack_start(btn_remocion, False, False, 0)

        _pack_ultima_edicion(self, "rack", "id_rack", id_rack)
        self.show_all()

    def _ver_dispositivos(self, btn):
        dlg = PosicionEnRackListado(id_rack=self.id_rack, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_vista_rack(self, btn):
        abrir_vista_rack(id_rack=self.id_rack, parent=self)

    def _simular_remocion(self, btn):
        from impacto_ui import simular_remocion_y_mostrar
        nombre = self.e_nombre.get_text().strip() or f"Rack {self.id_rack}"
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {nombre}",
            "simular_perdida_rack", self.id_rack)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            if self.id_rack:
                Modelo.modificacion_rack(
                    self.id_rack,
                    self.e_numero.get_text(),
                    self.e_nombre.get_text(),
                    self.e_cap.get_text()
                )
            else:
                Modelo.alta_rack(
                    self.e_numero.get_text(),
                    self.e_nombre.get_text(),
                    self.e_cap.get_text()
                )
        self.destroy()


# ─── Posición en Rack ─────────────────────────────────────────────────────────

class PosicionEnRackListado(VentanaListado):
    def __init__(self, id_rack=None, parent=None, modo_seleccion=False):
        super().__init__(
            "Posición en Rack",
            ["ID", "Rack", "Orificio", "Inventario", "Dispositivo", "UR"],
            parent=parent, modo_seleccion=modo_seleccion
        )
        self.id_rack = id_rack
        self.cargar_datos()

    def cargar_datos(self):
        if self.id_rack:
            rows = Modelo.devolver_dispositivos_de_un_rack(self.id_rack)
        else:
            rows = Modelo.devolver_todos_dispositivos_en_racks()
        self._poblar(rows)

    def nuevo(self):
        dlg = _DialogoPosicionRack(id_rack=self.id_rack, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoPosicionRack(id_posicion=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_dispositivo_en_rack(id_)


class _DialogoPosicionRack(Gtk.Dialog):
    def __init__(self, id_posicion=None, id_rack=None, parent=None):
        titulo = _("Editar Posición en Rack") if id_posicion else _("Nueva Posición en Rack")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 320)
        self.id_posicion = id_posicion
        self.id_rack = id_rack or ""
        self.id_equipo = ""
        self.id_frame = ""

        g = _grid()
        _lbl_entry(g, _("Rack:"), 0)
        self.e_rack = _entry_btn(g, 0, "…", self._sel_rack,
                                 readonly=bool(id_rack))
        _lbl_entry(g, _("Orificio:"), 1)
        self.e_orificio = _entry(g, 1)
        _lbl_entry(g, _("UR (unidades):"), 2)
        self.e_ur = _entry(g, 2)

        # Radio buttons equipo vs frame
        hb = Gtk.Box(spacing=8)
        self.rb_equipo = Gtk.RadioButton.new_with_label_from_widget(None, _("Equipo"))
        self.rb_frame = Gtk.RadioButton.new_with_label_from_widget(
            self.rb_equipo, _("Frame"))
        hb.pack_start(self.rb_equipo, False, False, 0)
        hb.pack_start(self.rb_frame, False, False, 0)
        g.attach(Gtk.Label(label=_("Tipo dispositivo:"), xalign=1), 0, 3, 1, 1)
        g.attach(hb, 1, 3, 2, 1)

        _lbl_entry(g, _("Equipo:"), 4)
        self.e_equipo = _entry_btn(g, 4, "…", self._sel_equipo)
        _lbl_entry(g, _("Frame:"), 5)
        self.e_frame = _entry_btn(g, 5, "…", self._sel_frame)
        self.get_content_area().add(g)

        # Prellenar rack si viene dado
        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                self.e_rack.set_text(s(rows[0][2]))
                self.e_rack.set_editable(False)

        if id_posicion:
            rows = Modelo.devolver_dispositivo_en_rack(id_posicion)
            if rows:
                r = rows[0]
                # id, rack, orificio, inventario, dispositivo, UR, id_rack, id_equipo, id_frame
                self.e_rack.set_text(s(r[1]))
                self.e_orificio.set_text(s(r[2]))
                self.e_ur.set_text(s(r[5]))
                self.id_rack = s(r[6])
                self.id_equipo = s(r[7])
                self.id_frame = s(r[8])
                if self.id_equipo:
                    self.e_equipo.set_text(s(r[4]))
                    self.rb_equipo.set_active(True)
                else:
                    self.e_frame.set_text(s(r[4]))
                    self.rb_frame.set_active(True)

        _pack_ultima_edicion(self, "posicion_en_rack", "id_posicion_en_rack", id_posicion)
        self.show_all()

    def _sel_rack(self, btn):
        dlg = RacksListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_rack = dlg.resultado_id
            self.e_rack.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_equipo(self, btn):
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.id_frame = ""
            self.e_equipo.set_text(dlg.resultado_nombre)
            self.e_frame.set_text("")
            self.rb_equipo.set_active(True)
        dlg.destroy()

    def _sel_frame(self, btn):
        dlg = FramesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_frame = dlg.resultado_id
            self.id_equipo = ""
            self.e_frame.set_text(dlg.resultado_nombre)
            self.e_equipo.set_text("")
            self.rb_frame.set_active(True)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            equipo = self.id_equipo or None
            frame = self.id_frame or None
            args = (
                self.id_rack or None,
                equipo, self.e_orificio.get_text(),
                self.e_ur.get_text(), frame
            )
            if self.id_posicion:
                Modelo.modificacion_dispositivo_en_rack(self.id_posicion, *args)
            else:
                Modelo.alta_dispositivo_en_rack(*args)
        self.destroy()


# ─── Catálogo de frames (moldes) ───────────────────────────────────────────────

class CatalogoFramesListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Catálogo de Frames"),
            [_("ID"), _("Molde"), _("Marca"), _("Modelo"), _("Slots")],
            parent=parent, modo_seleccion=modo_seleccion,
            botones_extra=[
                ("📦 Instanciar…", self._instanciar),
                ("⬆ Exportar…", self._exportar),
                ("⬇ Importar…", self._importar),
            ],
        )
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_catalogos_frame())

    def nuevo(self):
        dlg = _DialogoCatalogoFrame(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoCatalogoFrame(id_frame_catalogo=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_catalogo_frame(id_)

    def _instanciar(self, *a):
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un molde del catálogo.")
            return
        dlg = _DialogoInstanciarCatalogoFrame(id_frame_catalogo=f[0],
                                              nombre_molde=f[1], parent=self)
        dlg.run_and_destroy()

    def _exportar(self, *a):
        """Exporta el molde seleccionado o todo el catálogo de frames a un
        .zip portable que contiene un único JSON adentro (marca por nombre,
        imágenes/manual/picon embebidos en base64 dentro del JSON)."""
        fila = self._fila()
        ids = [fila[0]] if fila else None
        if ids and not confirmar(
                self, f"¿Exportar solo el molde seleccionado «{fila[1]}»?\n\n"
                     "(Cancelá para exportar TODO el catálogo de frames)"):
            ids = None
        dlg = Gtk.FileChooserDialog(
            title=_("Exportar catálogo de frames"), parent=self,
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Guardar"), Gtk.ResponseType.OK)
        dlg.set_current_name("catalogo_frames.zip")
        dlg.set_do_overwrite_confirmation(True)
        filt = Gtk.FileFilter(); filt.set_name("ZIP"); filt.add_pattern("*.zip")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            if not ruta.lower().endswith(".zip"):
                ruta += ".zip"
            try:
                data = Modelo.exportar_catalogo_frames(ids)
                _escribir_json_comprimido(ruta, "catalogo_frames.json", data)
                mostrar_info(self,
                    f"Catálogo exportado: {len(data['moldes'])} molde(s) → {ruta}")
            except Exception as e:
                mostrar_error(self, f"Error al exportar:\n{e}")
        dlg.destroy()

    def _importar(self, *a):
        """Importa moldes de frame desde un .zip (o un .json plano de una
        versión vieja) exportado por esta misma función, posiblemente de
        otra instalación de CableDoc."""
        dlg = Gtk.FileChooserDialog(
            title=_("Importar catálogo de frames"), parent=self,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        _("Abrir"), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name("ZIP / JSON")
        filt.add_pattern("*.zip"); filt.add_pattern("*.json")
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            ruta = dlg.get_filename()
            try:
                data = _leer_json_generico(ruta)
                if not isinstance(data, dict) or data.get("tipo") != "cabledoc_catalogo_frames":
                    mostrar_error(self, "El archivo no es un catálogo de frames válido.")
                else:
                    n_m, n_s = Modelo.importar_catalogo_frames(data)
                    mostrar_info(self, f"Importados {n_m} molde(s) con {n_s} slot(s).")
                    self.cargar_datos()
            except Exception as e:
                mostrar_error(self, f"Error al importar:\n{e}")
        dlg.destroy()


class _DialogoCatalogoFrame(Gtk.Dialog):
    def __init__(self, id_frame_catalogo=None, parent=None):
        titulo = _("Editar Molde de Frame") if id_frame_catalogo else _("Nuevo Molde de Frame")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(540, 520)
        self.id_frame_catalogo = id_frame_catalogo
        self.id_marca = ""
        self.id_imagen = ""

        ca = self.get_content_area()
        g = _grid()
        _lbl_entry(g, _("Nombre molde:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Ej: PPV 16x16 Canare")
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(
            g, 1, Modelo.devolver_todas_las_marcas(), "…", self._sel_marca_dropdown)
        _lbl_entry(g, _("Modelo:"), 2)
        self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Imagen:"), 3)
        self.e_imagen = _entry_btn(g, 3, "…", self._sel_imagen)
        _lbl_entry(g, _("Manual (PDF):"), 4)
        self.e_manual = Gtk.Entry(hexpand=True)
        g.attach(self.e_manual, 1, 4, 1, 1)
        btn_sel_manual = Gtk.Button(label="…")
        btn_sel_manual.connect("clicked", self._sel_manual)
        g.attach(btn_sel_manual, 2, 4, 1, 1)
        _lbl_entry(g, _("Foto (Picon):"), 5)
        self.e_picon = Gtk.Entry(hexpand=True)
        g.attach(self.e_picon, 1, 5, 1, 1)
        btn_sel_picon = Gtk.Button(label=_("…"))
        btn_sel_picon.connect("clicked", self._sel_picon)
        g.attach(btn_sel_picon, 2, 5, 1, 1)
        btn_quitar_picon = Gtk.Button(label=_("✖"))
        btn_quitar_picon.set_tooltip_text(_("Quitar foto"))
        btn_quitar_picon.connect("clicked", self._quitar_picon)
        g.attach(btn_quitar_picon, 3, 5, 1, 1)
        self.img_picon = Gtk.Image()
        self.img_picon.set_size_request(120, 120)
        frame_picon = Gtk.Frame()
        frame_picon.add(self.img_picon)
        g.attach(frame_picon, 1, 6, 1, 1)
        ca.pack_start(g, False, False, 0)

        hbox_buttons = Gtk.Box(spacing=6)
        hbox_buttons.set_margin_start(12); hbox_buttons.set_margin_end(12)
        hbox_buttons.set_margin_bottom(6)
        if id_frame_catalogo:
            btn_slots = Gtk.Button(label=_("🗂️ Slots del molde"))
            btn_slots.connect("clicked", self._ver_slots)
            hbox_buttons.pack_start(btn_slots, False, False, 0)

            btn_masivo = Gtk.Button(label=_("📐 Edición masiva de slots"))
            btn_masivo.connect("clicked", self._editar_slots_masivo)
            hbox_buttons.pack_start(btn_masivo, False, False, 0)
        ca.pack_start(hbox_buttons, False, False, 0)

        if id_frame_catalogo:
            rows = Modelo.devolver_catalogo_frame(id_frame_catalogo)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_marca = s(r[2]); _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[4]))
                self.id_imagen = s(r[5])
                self.e_imagen.set_text(s(r[6]))
                self.e_manual.set_text(s(r[7]))
                if len(r) > 9 and r[9]:
                    self.e_picon.set_text(s(r[9]))

        self._actualizar_picon_preview()
        self.show_all()

    def _sel_marca_dropdown(self, btn):
        dlg = MarcasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            _repopulate_combo(self.c_marca, Modelo.devolver_todas_las_marcas())
            _set_combo_id(self.c_marca, dlg.resultado_id)
        dlg.destroy()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_manual(self, btn):
        from modelo import MANUALES_DIR
        os.makedirs(MANUALES_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar Manual PDF"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(MANUALES_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Archivos PDF"))
        filtro.add_pattern("*.pdf"); filtro.add_pattern("*.PDF")
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(MANUALES_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar: {e}")
                self.e_manual.set_text(fname)
        dialog.destroy()

    def _sel_picon(self, btn):
        os.makedirs(PICON_DIR, exist_ok=True)
        dialog = Gtk.FileChooserDialog(
            title=_("Seleccionar foto del equipo"), parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder(PICON_DIR)
        filtro = Gtk.FileFilter(); filtro.set_name(_("Imágenes"))
        for pat in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG",
                    "*.gif", "*.GIF", "*.bmp", "*.BMP", "*.webp", "*.WEBP"):
            filtro.add_pattern(pat)
        dialog.add_filter(filtro)
        if dialog.run() == Gtk.ResponseType.OK:
            src = dialog.get_filename()
            if src:
                fname = os.path.basename(src)
                dest = os.path.join(PICON_DIR, fname)
                if os.path.abspath(src) != os.path.abspath(dest):
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e:
                        mostrar_error(self, f"Error al copiar la foto: {e}")
                self.e_picon.set_text(fname)
                self._actualizar_picon_preview()
        dialog.destroy()

    def _quitar_picon(self, btn):
        self.e_picon.set_text("")
        self._actualizar_picon_preview()

    def _actualizar_picon_preview(self):
        filename = self.e_picon.get_text().strip()
        if filename:
            ruta = os.path.join(PICON_DIR, filename)
            if os.path.isfile(ruta):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, 120, 120, True)
                    self.img_picon.set_from_pixbuf(pixbuf)
                    return
                except Exception:
                    pass
        self.img_picon.clear()

    def _ver_slots(self, btn):
        dlg = _SlotsCatalogoListado(self.id_frame_catalogo, parent=self)
        dlg.run(); dlg.destroy()

    def _editar_slots_masivo(self, btn):
        if not self.id_imagen:
            mostrar_error(self, "Asigná una imagen al molde antes de "
                                "usar la edición masiva de slots.")
            return
        abrir_editor_masivo_slots_catalogo(
            id_frame_catalogo=self.id_frame_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_marca = _get_combo_id(self.c_marca)
            nombre = self.e_nombre.get_text().strip()
            modelo = self.e_modelo.get_text().strip()
            manual = self.e_manual.get_text().strip() or None
            picon = self.e_picon.get_text().strip() or None
            if self.id_frame_catalogo:
                Modelo.modificacion_catalogo_frame(
                    self.id_frame_catalogo, nombre, id_marca or None,
                    modelo, self.id_imagen or None, manual, picon=picon)
            else:
                nuevo_id = Modelo.alta_catalogo_frame(
                    nombre, id_marca or None, modelo, self.id_imagen or None, manual,
                    picon=picon)
                self.id_frame_catalogo = nuevo_id
        self.destroy()


class _SlotsCatalogoListado(VentanaListado):
    def __init__(self, id_frame_catalogo, parent=None):
        super().__init__(_("Slots del molde"),
                         [_("ID"), _("Slot"), _("X"), _("Y"), _("Ancho"), _("Alto")],
                         parent=parent,
                         botones_extra=[
                             ("📐 Edición masiva de slots", self._editar_slots_masivo),
                         ])
        self.id_frame_catalogo = id_frame_catalogo
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_slots_de_catalogo_frame(self.id_frame_catalogo))

    def nuevo(self):
        dlg = _DialogoSlotCatalogo(id_frame_catalogo=self.id_frame_catalogo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoSlotCatalogo(id_slot_catalogo=id_,
                                   id_frame_catalogo=self.id_frame_catalogo, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_slot_catalogo(id_)

    def _editar_slots_masivo(self, btn):
        abrir_editor_masivo_slots_catalogo(
            id_frame_catalogo=self.id_frame_catalogo, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)
        self.cargar_datos()


class _DialogoSlotCatalogo(Gtk.Dialog):
    def __init__(self, id_slot_catalogo=None, id_frame_catalogo=None, parent=None):
        titulo = _("Editar Slot Molde") if id_slot_catalogo else _("Nuevo Slot Molde")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(380, 280)
        self.id_slot_catalogo = id_slot_catalogo
        self.id_frame_catalogo = id_frame_catalogo

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Rect X:"), 1); self.e_x = _entry(g, 1)
        _lbl_entry(g, _("Rect Y:"), 2); self.e_y = _entry(g, 2)
        _lbl_entry(g, _("Ancho px:"), 3); self.e_ancho = _entry(g, 3)
        _lbl_entry(g, _("Alto px:"), 4); self.e_alto = _entry(g, 4)
        self.get_content_area().add(g)

        btn_coords = Gtk.Button(label=_("📍 Elegir rectángulo en imagen"))
        btn_coords.connect("clicked", self._sel_rect_imagen)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_slot_catalogo:
            rows = Modelo._query(
                "SELECT id_slot_catalogo, nombre, rectangulo_x_en_imagen, "
                "rectangulo_y_en_imagen, rectangulo_ancho_pixeles, "
                "rectangulo_alto_pixeles FROM slot_catalogo WHERE id_slot_catalogo=?",
                (id_slot_catalogo,))
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                x_px, y_px, ancho_px, alto_px = Modelo._px_rect_o_crudo(
                    Modelo._path_imagen(self._id_imagen_del_molde()),
                    r[2], r[3], r[4], r[5])
                self.e_x.set_text(s(x_px)); self.e_y.set_text(s(y_px))
                self.e_ancho.set_text(s(ancho_px)); self.e_alto.set_text(s(alto_px))

        self.show_all()

    def _id_imagen_del_molde(self):
        """Obtiene el id_imagen del frame_catalogo padre (la imagen sobre la
        que se dibujan los rectángulos de los slots del molde)."""
        rows = Modelo.devolver_catalogo_frame(self.id_frame_catalogo)
        if rows and rows[0][5]:
            return rows[0][5]
        return None

    def _sel_rect_imagen(self, btn):
        id_img = self._id_imagen_del_molde()
        if not id_img:
            mostrar_error(self, "El molde no tiene una imagen asignada.\n"
                                "Asigná una imagen al molde de frame antes de "
                                "elegir el rectángulo del slot.")
            return
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=False,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            ancho=self.e_ancho.get_text(), alto=self.e_alto.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])
            self.e_ancho.set_text(res["ancho"])
            self.e_alto.set_text(res["alto"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            x = self.e_x.get_text().strip(); y = self.e_y.get_text().strip()
            ancho = self.e_ancho.get_text().strip(); alto = self.e_alto.get_text().strip()
            if self.id_slot_catalogo:
                Modelo.modificacion_slot_catalogo(
                    self.id_slot_catalogo, nombre, x, y, ancho, alto)
            else:
                Modelo.agregar_slot_catalogo(
                    self.id_frame_catalogo, nombre, x, y, ancho, alto)
        self.destroy()


class _DialogoInstanciarCatalogoFrame(Gtk.Dialog):
    """Instancia un frame real desde un molde: solo pide nombre e inventario.
    Todo lo demás (marca/modelo/imagen/manual/slots) se copia del molde."""

    def __init__(self, id_frame_catalogo, nombre_molde="", parent=None):
        super().__init__(title=_("Instanciar frame desde catálogo"),
                         transient_for=parent, modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "📦 " + _("Crear frame"), Gtk.ResponseType.OK)
        self.set_default_size(400, 220)
        self.id_frame_catalogo = id_frame_catalogo
        self.id_frame_creado = None

        ca = self.get_content_area()
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>Molde:</b> {nombre_molde}")
        lbl.set_margin_start(12); lbl.set_margin_top(10)
        ca.pack_start(lbl, False, False, 0)

        g = _grid()
        _lbl_entry(g, _("Nombre *:"), 0)
        self.e_nombre = _entry(g, 0)
        self.e_nombre.set_placeholder_text("Nombre del frame real (requerido)")
        _lbl_entry(g, _("Inventario:"), 1)
        self.e_inventario = _entry(g, 1)
        ca.pack_start(g, False, False, 0)

        n_slots = len(Modelo.devolver_slots_de_catalogo_frame(id_frame_catalogo))
        lbl_n = Gtk.Label(xalign=0)
        lbl_n.set_markup(f"<small><i>Se copiarán {n_slots} slots vacíos (sin equipo).</i></small>")
        lbl_n.set_margin_start(12)
        ca.pack_start(lbl_n, False, False, 4)

        self.show_all()

    def run_and_destroy(self):
        while True:
            resp = self.run()
            if resp != Gtk.ResponseType.OK:
                break
            nombre = self.e_nombre.get_text().strip()
            if not nombre:
                mostrar_error(self, "El nombre del frame es obligatorio.")
                continue
            self.id_frame_creado = Modelo.instanciar_frame_desde_catalogo(
                self.id_frame_catalogo, nombre,
                self.e_inventario.get_text().strip() or None,
            )
            mostrar_info(self, f"Frame «{nombre}» creado (ID {self.id_frame_creado}).")
            break
        self.destroy()


# ─── Frames ───────────────────────────────────────────────────────────────────

class FramesListado(VentanaListado):
    # filtro_pendiente: None | 'sin_slots' | 'sin_imagen' | 'sin_rect'
    def __init__(self, parent=None, modo_seleccion=False, filtro_pendiente=None):
        self._filtro_pendiente = filtro_pendiente
        self._ids_resaltar = set()
        titulo = _("Frames")
        if filtro_pendiente == "sin_slots":
            titulo = _("Frames — Sin slots")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Frames — Sin imagen")
        elif filtro_pendiente == "sin_rect":
            titulo = _("Frames — Sin slots en imagen")
        super().__init__(titulo,
                         [_("ID"), _("Nombre"), _("Marca"), _("Modelo"), _("Inventario")],
                         parent=parent, modo_seleccion=modo_seleccion,
                         botones_extra=[
                             ("🖼 Ver slots en imagen", self._ver_slots_imagen),
                             ("📐 Edición masiva de slots", self._editar_slots_masivo),
                             ("📦 Desde catálogo", self._desde_catalogo),
                         ])
        self.cargar_datos()

    def _desde_catalogo(self, *a):
        sel = CatalogoFramesListado(parent=self, modo_seleccion=True)
        if sel.run() == Gtk.ResponseType.OK:
            id_cat = sel.resultado_id
            nombre_molde = sel.resultado_nombre
            sel.destroy()
            dlg = _DialogoInstanciarCatalogoFrame(
                id_frame_catalogo=id_cat, nombre_molde=nombre_molde, parent=self)
            dlg.run_and_destroy()
            self.cargar_datos()
        else:
            sel.destroy()

    def _ver_slots_imagen(self, btn):
        fila = self._fila()
        if fila:
            abrir_vista_frame_slots(id_frame=fila[0], parent=self)

    def _editar_slots_masivo(self, btn):
        fila = self._fila()
        if fila:
            abrir_editor_masivo_slots(
                id_frame=fila[0], parent=self,
                fn_sel_imagen=_sel_imagen_desde_abm)
            self.cargar_datos()

    def cargar_datos(self):
        self._ids_resaltar = set()
        color = "#c8a800"
        if self._filtro_pendiente == "sin_slots":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE "
                "NOT EXISTS (SELECT 1 FROM slot WHERE id_frame=frame.id_frame)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        elif self._filtro_pendiente == "sin_rect":
            rows = Modelo._query(
                "SELECT f.id_frame FROM frame f WHERE "
                "EXISTS (SELECT 1 FROM slot WHERE id_frame=f.id_frame) "
                "AND NOT EXISTS (SELECT 1 FROM slot s WHERE s.id_frame=f.id_frame "
                "AND s.rectangulo_x_en_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
            color = "#c8a800"
        todos = Modelo.devolver_todos_los_frames()
        data = [[r[0], r[1], r[2], r[3], r[7]] for r in todos]
        self._poblar(data, ids_resaltar=self._ids_resaltar, color_resaltar=color)

    def _filtrar(self, model, iter_, data):
        txt = self.entry_filtro.get_text().lower()
        n = len(self.columnas)
        if txt:
            if not any(txt in s(model.get_value(iter_, i)).lower() for i in range(n)):
                return False
        if self._filtro_pendiente and self._ids_resaltar:
            fid = s(model.get_value(iter_, 0))
            return fid in self._ids_resaltar
        return True

    def nuevo(self):
        dlg = _DialogoFrame(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoFrame(id_frame=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_frame(id_)


class _DialogoFrame(Gtk.Dialog):
    def __init__(self, id_frame=None, parent=None):
        titulo = _("Editar Frame") if id_frame else _("Nuevo Frame")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                                destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 300)
        self.id_frame = id_frame
        self.id_marca = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Marca:"), 1)
        self.c_marca = _searchable_combo(g, 1, Modelo.devolver_todas_las_marcas())
        _lbl_entry(g, _("Modelo:"), 2); self.e_modelo = _entry(g, 2)
        _lbl_entry(g, _("Inventario:"), 3); self.e_inv = _entry(g, 3)
        _lbl_entry(g, _("Imagen:"), 4)
        self.e_imagen = _entry_btn(g, 4, "…", self._sel_imagen)
        self.get_content_area().add(g)

        if id_frame:
            btn_slots = Gtk.Button(label=_("🗂️ Ver Slots"))
            btn_slots.connect("clicked", self._ver_slots)
            self.get_content_area().pack_start(btn_slots, False, False, 0)

            btn_vista = Gtk.Button(label=_("🖼 Ver slots en imagen"))
            btn_vista.connect("clicked", self._ver_slots_imagen)
            self.get_content_area().pack_start(btn_vista, False, False, 0)

            btn_rack = Gtk.Button(label=_("🗄 Rack del frame"))
            btn_rack.set_tooltip_text(
                _("Buscar en qué rack está montado este frame y abrir su vista gráfica"))
            btn_rack.connect("clicked", self._ver_rack)
            self.get_content_area().pack_start(btn_rack, False, False, 0)

            btn_template = Gtk.Button(label=_("🧬 Frame a template"))
            btn_template.set_tooltip_text(
                _("Crear un molde de catálogo reutilizable a partir de "
                  "este frame y sus slots (sin inventario)"))
            btn_template.connect("clicked", self._frame_a_template)
            self.get_content_area().pack_start(btn_template, False, False, 0)

        if id_frame:
            rows = Modelo.devolver_frame(id_frame)
            if rows:
                r = rows[0]
                # id, nombre, marca, modelo, id_marca, imagen_path, id_imagen, inventario
                self.e_nombre.set_text(s(r[1]))
                self.id_marca = s(r[4])
                _set_combo_id(self.c_marca, self.id_marca)
                self.e_modelo.set_text(s(r[3]))
                self.e_imagen.set_text(s(r[5]))
                self.id_imagen = s(r[6])
                self.e_inv.set_text(s(r[7]))

        _pack_ultima_edicion(self, "frame", "id_frame", id_frame)
        self.show_all()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _ver_slots(self, btn):
        dlg = SlotsListado(id_frame=self.id_frame, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_slots_imagen(self, btn):
        abrir_vista_frame_slots(id_frame=self.id_frame, parent=self)

    def _ver_rack(self, btn):
        """Busca el rack donde está montado este frame y abre su vista
        gráfica. Si no está rackeado, muestra un diálogo avisando."""
        filas = Modelo.devolver_rack_de_frame(self.id_frame)
        if not filas:
            mostrar_info(self, _("Equipo no rackeado"))
            return
        id_rack = filas[0][0]
        abrir_vista_rack(id_rack=id_rack, parent=self)

    def _frame_a_template(self, btn):
        """Crea un molde de catálogo (frame_catalogo) a partir de este
        frame: copia marca, modelo e imagen, más sus slots (nombre y
        rectángulo x/y/ancho/alto) vacíos en el molde. NO copia el
        inventario, que es propio de esta instancia física."""
        if not self.id_frame:
            return
        nombre_actual = self.e_nombre.get_text().strip() or "Frame"
        dlg = DialogoNombre(
            _("Frame a template"), etiqueta=_("Nombre del molde:"),
            valor=f"{nombre_actual} (molde)", parent=self)
        ok = dlg.run() == Gtk.ResponseType.OK
        valor = dlg.valor
        dlg.destroy()
        if not ok or not valor:
            return
        resultado = Modelo.crear_catalogo_desde_frame(self.id_frame, valor)
        if resultado:
            id_cat, n_slots = resultado
            mostrar_info(self,
                f"Molde «{valor}» creado (ID {id_cat}) con {n_slots} slot(s).\n\n"
                "Podés verlo/editarlo en Frames → 📦 Catálogo de Frames.")
        else:
            mostrar_error(self, "No se pudo crear el molde.")

    def _ver_editor_masivo_slots(self, btn):
        abrir_editor_masivo_slots(
            id_frame=self.id_frame, parent=self,
            fn_sel_imagen=_sel_imagen_desde_abm)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            self.id_marca = _get_combo_id(self.c_marca)
            args = (
                self.e_nombre.get_text(),
                self.e_inv.get_text(),
                self.id_marca or None,
                self.id_imagen or None,
                self.e_modelo.get_text()
            )
            if self.id_frame:
                Modelo.modificar_frame(self.id_frame, *args)
            else:
                Modelo.agregar_frame(*args)
        self.destroy()


# ─── Slots ────────────────────────────────────────────────────────────────────

class SlotsListado(VentanaListado):
    def __init__(self, id_frame, parent=None):
        super().__init__(_("Slots"), [_("ID"), _("Slot"), _("Módulo/Equipo")],
                         parent=parent)
        self.id_frame = id_frame
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_slots_del_frame(self.id_frame))

    def nuevo(self):
        dlg = _DialogoSlot(id_frame=self.id_frame, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoSlot(id_slot=id_, id_frame=self.id_frame, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_slot(id_)


class _DialogoSlot(Gtk.Dialog):
    def __init__(self, id_slot=None, id_frame=None, parent=None):
        titulo = _("Editar Slot") if id_slot else _("Nuevo Slot")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 340)
        self.id_slot = id_slot
        self.id_frame = id_frame or ""
        self.id_equipo = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0); self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Equipo:"), 1)
        self.e_equipo = _entry_btn(g, 1, "…", self._sel_equipo)
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Rect X:"), 3); self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Rect Y:"), 4); self.e_y = _entry(g, 4)
        _lbl_entry(g, _("Ancho px:"), 5); self.e_ancho = _entry(g, 5)
        _lbl_entry(g, _("Alto px:"), 6); self.e_alto = _entry(g, 6)
        self.get_content_area().add(g)

        # Botón selector de rectángulo en imagen (slots usan ancho+alto)
        btn_coords = Gtk.Button(label=_("📍 Elegir rectángulo en imagen"))
        btn_coords.connect("clicked", self._sel_rect_imagen)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_slot:
            rows = Modelo.devolver_slot(id_slot)
            if rows:
                r = rows[0]
                # id_slot, slot_nombre, id_equipo, nombre_equipo,
                # path_imagen, id_imagen, x, y, alto, ancho, id_frame
                self.e_nombre.set_text(s(r[1]))
                self.id_equipo = s(r[2])
                self.e_equipo.set_text(s(r[3]))
                self.e_imagen.set_text(s(r[4]))
                self.id_imagen = s(r[5])
                self.e_x.set_text(s(r[6]))
                self.e_y.set_text(s(r[7]))
                self.e_alto.set_text(s(r[8]))
                self.e_ancho.set_text(s(r[9]))
                self.id_frame = s(r[10])

        _pack_ultima_edicion(self, "slot", "id_slot", id_slot)
        self.show_all()

    def _sel_equipo(self, btn):
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.e_equipo.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_imagen(self, btn):
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_rect_imagen(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=False,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            ancho=self.e_ancho.get_text(), alto=self.e_alto.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])
            self.e_ancho.set_text(res["ancho"])
            self.e_alto.set_text(res["alto"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            args = (
                self.e_nombre.get_text(),
                self.id_equipo or None,
                self.id_frame or None,
                self.id_imagen or None,
                self.e_x.get_text(), self.e_y.get_text(),
                self.e_ancho.get_text(), self.e_alto.get_text()
            )
            if self.id_slot:
                Modelo.modificar_slot(self.id_slot, *args)
            else:
                Modelo.agregar_slot(*args)
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


# ─── Salas ────────────────────────────────────────────────────────────────────

class SalasListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Salas"), [_("ID"), _("Nombre")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_salas())

    def nuevo(self):
        dlg = DialogoNombre(_("Nueva Sala"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            Modelo.alta_sala(dlg.valor)
        dlg.destroy()

    def editar(self, id_):
        rows = Modelo.devolver_sala(id_)
        if not rows: return
        dlg = DialogoNombre(_("Editar Sala"), valor=s(rows[0][1]), parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            Modelo.modificacion_sala(id_, dlg.valor)
        dlg.destroy()

    def eliminar(self, id_):
        Modelo.eliminar_sala(id_)


# ─── Rack por Sala ────────────────────────────────────────────────────────────

class _DialogoRackPorSala(Gtk.Dialog):
    """Diálogo para asignar un rack a una sala."""

    def __init__(self, id_=None, parent=None):
        titulo = _("Editar asignación Rack-Sala") if id_ else _("Nueva asignación Rack-Sala")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(360, -1)
        self.id_ = id_

        ca = self.get_content_area()
        g = _grid()
        ca.pack_start(g, True, True, 0)

        _lbl_entry(g, _("Sala:"), 0)
        self.e_sala = _entry_btn(g, 0, "…", self._sel_sala)
        self._id_sala = None

        _lbl_entry(g, _("Rack:"), 1)
        self.e_rack = _entry_btn(g, 1, "…", self._sel_rack)
        self._id_rack = None

        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(_("Guardar"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        if id_:
            rows = Modelo.devolver_rack_por_sala(id_)
            if rows:
                self._id_sala = str(rows[0][1])
                self._id_rack = str(rows[0][2])
                self.e_sala.set_text(s(rows[0][3]))
                self.e_rack.set_text(s(rows[0][4]))

        _pack_ultima_edicion(self, "rack_por_sala", "id_rack_x_sala", id_)
        self.show_all()

    def _sel_sala(self, btn):
        dlg = SalasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_sala = str(fila[0])
                self.e_sala.set_text(s(fila[1]))
        dlg.destroy()

    def _sel_rack(self, btn):
        dlg = RacksListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_rack = str(fila[0])
                self.e_rack.set_text(s(fila[2]))
        dlg.destroy()

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return
        if not self._id_sala or not self._id_rack:
            return
        if self.id_:
            Modelo.modificacion_rack_por_sala(self.id_, self._id_sala, self._id_rack)
        else:
            Modelo.alta_rack_por_sala(self._id_sala, self._id_rack)


class RackPorSalaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Rack por Sala"), [_("ID"), _("Sala"), _("Rack")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_rack_por_sala())

    def nuevo(self):
        dlg = _DialogoRackPorSala(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoRackPorSala(id_=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_rack_por_sala(id_)


class _DialogoEquipoNoRackSala(Gtk.Dialog):
    """Diálogo para asignar un equipo suelto a una sala."""

    def __init__(self, id_=None, parent=None):
        titulo = _("Editar equipo suelto en sala") if id_ else _("Nuevo equipo suelto en sala")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(380, -1)
        self.id_ = id_

        ca = self.get_content_area()
        g = _grid()
        ca.pack_start(g, True, True, 0)

        _lbl_entry(g, _("Sala:"), 0)
        self.e_sala = _entry_btn(g, 0, "…", self._sel_sala)
        self._id_sala = None

        _lbl_entry(g, _("Equipo:"), 1)
        self.e_equipo = _entry_btn(g, 1, "…", self._sel_equipo)
        self._id_equipo = None

        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(_("Guardar"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        if id_:
            rows = Modelo.devolver_equipo_no_rack_sala(id_)
            if rows:
                self._id_sala   = str(rows[0][1])
                self._id_equipo = str(rows[0][2])
                self.e_sala.set_text(s(rows[0][3]))
                self.e_equipo.set_text(s(rows[0][4]))

        _pack_ultima_edicion(self, "equiponoraqueable_por_sala",
                             "id_equiponoraqueable_por_sala", id_)
        self.show_all()

    def _sel_sala(self, btn):
        dlg = SalasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_sala = str(fila[0])
                self.e_sala.set_text(s(fila[1]))
        dlg.destroy()

    def _sel_equipo(self, btn):
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_equipo = str(fila[0])
                self.e_equipo.set_text(s(fila[1]))
        dlg.destroy()

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            self.destroy()
            return
        if not self._id_sala or not self._id_equipo:
            mostrar_error(self, "Seleccioná sala y equipo antes de guardar.")
            return
        if self.id_:
            Modelo.modificacion_equipo_no_rack_sala(
                self.id_, self._id_sala, self._id_equipo)
        else:
            Modelo.alta_equipo_no_rack_sala(self._id_sala, self._id_equipo)
        self.destroy()

    def run_and_destroy(self):
        self.run()


class EquiposNoRackSalaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Equipos sueltos por sala"),
                         [_("ID"), _("Sala"), _("Equipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_equipos_no_rack_sala())

    def nuevo(self):
        dlg = _DialogoEquipoNoRackSala(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoEquipoNoRackSala(id_=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_equipo_no_rack_sala(id_)


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
