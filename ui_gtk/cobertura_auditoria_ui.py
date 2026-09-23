#!/usr/bin/env python3
"""
cobertura_auditoria_ui.py — Reporte de cobertura de auditoría por rack (GTK3)
==============================================================================
D2 de plan_auditoria_fecha_edicion_v1.md. Muestra Modelo.devolver_cobertura_
auditoria(dias) (D1, core/modelo.py) como una tabla simple, sin gráficos:
un renglón por rack con cuántos de sus equipos tienen una auditoría de campo
dentro de la ventana elegida, el total y el porcentaje. Es una métrica de
gestión ("% auditado en los últimos N días"), no una lista de trabajo — para
eso están el panel de pendientes y el badge "Editado sin auditar".

  - Reusa VentanaListado (mismo patrón que RiesgoSenalListado, de sólo
    lectura): sin Agregar/Editar/Eliminar, el filtro de texto y el orden por
    columna ya vienen de la clase base.
  - La ventana de días es un combo (30/60/90/180/365, por defecto 90 = el
    default de devolver_cobertura_auditoria). Cambiarlo recalcula al toque.
  - Orden inicial: menor cobertura primero (lo que más urge, arriba).
  - Sólo cuenta equipos rackeados (directos en el rack o módulos de un frame
    rackeado) — los sueltos o sobre mueble no están en D1; se aclara en un
    tooltip del resumen para que el total no se confunda con "todos los
    equipos de la base".

Integración en cabledoc.py: ítem "🕓 Cobertura de auditoría…" del menú
Infraestructura → VentanaPrincipal._abrir_cobertura_auditoria (import
diferido de abrir_cobertura_auditoria, mismo patrón que bitacora_ui).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.modelo import Modelo

try:
    from core.i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import VentanaListado

DIAS_OPCIONES = (30, 60, 90, 180, 365)
DIAS_DEFAULT = 90


def _sort_numerico(model, a, b, col):
    """Orden numérico para las columnas de conteo/porcentaje (el orden
    natural de VentanaListado sólo entiende enteros: '87.5 %' caería a
    comparación de texto y '9.0 %' quedaría después de '87.5 %')."""
    def _num(it):
        try:
            return float((model.get_value(it, col) or "")
                         .replace("%", "").strip())
        except ValueError:
            return -1.0
    va, vb = _num(a), _num(b)
    return (va > vb) - (va < vb)


class CoberturaAuditoriaListado(VentanaListado):
    """Listado de sólo lectura: cobertura de auditoría por rack."""

    def __init__(self, parent=None):
        super().__init__(
            _("Cobertura de auditoría"),
            [_("ID"), _("Rack"), _("Auditados"), _("Total"), _("Cobertura")],
            parent=parent)
        self._dias = DIAS_DEFAULT

        # Sin CRUD propio: el reporte no da de alta/edita/borra nada ni es
        # un selector ("Seleccionar" sólo aplica a modo_seleccion). Se
        # marcan no_show_all para que un show_all() posterior (p. ej. el de
        # run_and_destroy) no los vuelva a mostrar.
        for btn in (self.btn_agregar, self.btn_editar, self.btn_eliminar,
                    self.btn_seleccionar):
            btn.set_no_show_all(True)
            btn.hide()

        # Las tres columnas numéricas ordenan por valor, no por texto.
        for col in (2, 3, 4):
            self.store.set_sort_func(col, _sort_numerico, col)

        # Fila superior: ventana de días + resumen global. Se inserta
        # arriba de todo (antes de la barra de filtro de la clase base).
        fila = Gtk.Box(spacing=8)
        fila.set_margin_start(8)
        fila.set_margin_end(8)
        fila.set_margin_top(6)
        fila.pack_start(Gtk.Label(label=_("Ventana:")), False, False, 0)
        self.combo_dias = Gtk.ComboBoxText()
        for d in DIAS_OPCIONES:
            self.combo_dias.append(str(d), _("Últimos {} días").format(d))
        self.combo_dias.set_active_id(str(DIAS_DEFAULT))
        self.combo_dias.connect("changed", self._on_cambio_dias)
        fila.pack_start(self.combo_dias, False, False, 0)
        self.lbl_resumen = Gtk.Label(xalign=0)
        self.lbl_resumen.set_hexpand(True)
        self.lbl_resumen.set_tooltip_text(_(
            "Sólo cuenta equipos instalados en racks (directos o como "
            "módulo de un frame rackeado)."))
        fila.pack_start(self.lbl_resumen, True, True, 0)
        area = self.get_content_area()
        area.pack_start(fila, False, False, 0)
        area.reorder_child(fila, 0)
        fila.show_all()

        self.cargar_datos()

    def _on_cambio_dias(self, combo):
        id_ = combo.get_active_id()
        if id_:
            self._dias = int(id_)
            self.cargar_datos()

    def cargar_datos(self):
        cobertura = Modelo.devolver_cobertura_auditoria(dias=self._dias)
        # Menor cobertura primero; a igual cobertura, por nombre de rack.
        ordenados = sorted(
            cobertura.items(),
            key=lambda kv: (kv[1]["porcentaje"], (kv[1]["nombre"] or "").lower()))
        filas = [
            [str(id_rack), d["nombre"] or "", str(d["auditados"]),
             str(d["total"]), f"{d['porcentaje']:.1f} %"]
            for id_rack, d in ordenados
        ]
        self._poblar(filas)

        total = sum(d["total"] for d in cobertura.values())
        auditados = sum(d["auditados"] for d in cobertura.values())
        if total:
            pct = 100.0 * auditados / total
            self.lbl_resumen.set_text(
                _("Cobertura global: {} de {} equipos auditados en los "
                  "últimos {} días ({} %)").format(
                    auditados, total, self._dias, f"{pct:.1f}"))
        else:
            self.lbl_resumen.set_text(_("No hay equipos ubicados en racks."))

    # Sin CRUD propio, ver __init__.
    def nuevo(self):
        pass

    def editar(self, id_):
        pass

    def eliminar(self, id_):
        pass


def abrir_cobertura_auditoria(parent=None):
    dlg = CoberturaAuditoriaListado(parent=parent)
    dlg.run()
    dlg.destroy()
