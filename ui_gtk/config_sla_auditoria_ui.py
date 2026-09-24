#!/usr/bin/env python3
"""
config_sla_auditoria_ui.py — Configuración del SLA de auditoría (GTK3)
=======================================================================
E3 de plan_auditoria_fecha_edicion_v1.md. Diálogo chico con un único campo
numérico: los días del SLA de auditoría (config_auditoria.dias_sla_auditoria,
Modelo.devolver_config_auditoria / establecer_config_auditoria, E1). Un
equipo está "vencido" (Modelo.devolver_vencidos_sla_auditoria, E2) cuando su
última auditoría es más vieja que esa cantidad de días, o nunca se auditó.

El plan pedía "un campo numérico en algún diálogo de preferencias
existente", pero la app no tiene un diálogo de preferencias accesible desde
la interfaz (_DialogoConfigRiesgoAnalogico de bitacora_ui.py no está
enganchado a ningún menú), así que este diálogo se abre desde la tarjeta
"Vencidos" del panel "Trabajo pendiente — Auditoría" de la pantalla de
Inicio (cabledoc.py, VentanaPrincipal._abrir_config_sla_auditoria).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.modelo import Modelo

try:
    from core.i18n import _
except ImportError:
    def _(t): return t

DIAS_MIN = 1
DIAS_MAX = 3650


class _DialogoConfigSLAAuditoria(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(title=_("SLA de auditoría"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(380, -1)

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_border_width(10)

        lbl = Gtk.Label(label=_(
            "Un equipo se considera vencido si su última auditoría es más "
            "vieja que esta cantidad de días, o si nunca se auditó."))
        lbl.set_line_wrap(True)
        lbl.set_xalign(0)
        area.pack_start(lbl, False, False, 0)

        fila = Gtk.Box(spacing=8)
        fila.pack_start(Gtk.Label(label=_("Días de SLA:")), False, False, 0)
        actual = Modelo.CONFIG_AUDITORIA_DEFAULTS["dias_sla_auditoria"]
        try:
            actual = float(Modelo.devolver_config_auditoria().get(
                "dias_sla_auditoria", actual))
        except (TypeError, ValueError):
            pass
        adj = Gtk.Adjustment(
            value=min(max(round(actual), DIAS_MIN), DIAS_MAX),
            lower=DIAS_MIN, upper=DIAS_MAX, step_increment=1,
            page_increment=10)
        self.spin_dias = Gtk.SpinButton(adjustment=adj, digits=0)
        self.spin_dias.set_numeric(True)
        fila.pack_start(self.spin_dias, False, False, 0)
        area.pack_start(fila, False, False, 0)

        self.show_all()

    def run_and_destroy(self):
        """Devuelve True si se guardó un valor (para que el llamador
        refresque el panel de Inicio), False si se canceló."""
        guardado = False
        if self.run() == Gtk.ResponseType.OK:
            self.spin_dias.update()   # confirma lo tipeado sin salir del campo
            Modelo.establecer_config_auditoria(
                "dias_sla_auditoria", float(self.spin_dias.get_value_as_int()))
            guardado = True
        self.destroy()
        return guardado


def abrir_config_sla_auditoria(parent=None):
    """Abre el diálogo; devuelve True si se guardó un cambio."""
    return _DialogoConfigSLAAuditoria(parent=parent).run_and_destroy()
