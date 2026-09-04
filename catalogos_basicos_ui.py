#!/usr/bin/env python3
"""
catalogos_basicos_ui.py — CableDoc GTK3

Dominio Catálogos básicos, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 8).

Contiene:
  - MarcasListado, _DialogoTipoEquipo, TiposEquipoListado
  - TiposConectorListado, RiesgoSenalListado
  - _DialogoTipoCable, TiposCableListado
  - _DialogoTipoFicha, TiposFichaListado
  - CategoriasProblemaListado, ProblemasEquipoListado, _DialogoProblema
  - ImagenesListado, _DialogoImagen
  - ConexionesDeEquipoVentana
  - DiagramasGuardadosListado, GeneradorDiagrama
  - EquipoInfoExtra

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos dieciocho nombres sin cambios para
que ningún `from cabledoc import X` externo se rompa.

Nota — desviación respecto del plan (§4): el plan original sólo asignaba
a este módulo los "catálogos chicos" (Marcas/TipoEquipo/TipoConector/
RiesgoSenal/TipoCable + TipoFicha/Problemas + Imágenes, ~774 líneas
estimadas). Quedaban 4 bloques sin destino asignado en el plan:
`ConexionesDeEquipoVentana`, `DiagramasGuardadosListado`,
`GeneradorDiagrama` (huérfanos en el relevamiento original de §3) y
`EquipoInfoExtra` (ni siquiera existía cuando se escribió el plan — se
agregó al código después). Como el cierre de la Entrega 10 exige que
`cabledoc.py` quede en ~700 líneas y la Entrega 9 (`panel_arbol_ui.py`)
es la última antes de ese cierre, la Entrega 8 es el único punto que
queda con perfil de "catch-all" para absorber esos 4 bloques — se suman
acá en vez de dejarlos varados. Resultado: ~1.112 líneas en vez de las
~774 estimadas por el plan.

Referencias a clases de otros dominios que ya viven en otros módulos
extraídos (`_DialogoCable`, en `cables_conexiones_ui.py`) se resuelven
con import diferido dentro del método que las usa, siguiendo el patrón
ya establecido por el proyecto de rutear siempre a través de
`from cabledoc import X` (nunca importar directo del módulo de dominio
hermano), igual que ya hace `racks_salas_ui.py` con `FramesListado`.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import os
import subprocess

from modelo import Modelo, DB_PATH, IMG_DIR

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    VentanaListado,
    DialogoNombre,
    _grid,
    _lbl_entry,
    _entry,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
    _searchable_combo,
    _parse_float_opt,
    _fmt_float_opt,
    _pack_ultima_edicion,
)
from diagrama_personalizado import DiagramaPersonalizado


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
        from cabledoc import _DialogoCable
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
