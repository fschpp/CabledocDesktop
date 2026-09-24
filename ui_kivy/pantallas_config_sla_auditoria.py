"""
pantallas_config_sla_auditoria.py — Configuración del SLA de auditoría (Kivy)
==============================================================================
E4 de plan_auditoria_fecha_edicion_v1.md. Equivalente a
ui_gtk/config_sla_auditoria_ui.py (E3): diálogo chico con un único campo
numérico, los días del SLA de auditoría (config_auditoria.dias_sla_auditoria,
Modelo.devolver_config_auditoria / establecer_config_auditoria, E1). Un
equipo está "vencido" (Modelo.devolver_vencidos_sla_auditoria, E2) cuando su
última auditoría es más vieja que esa cantidad de días, o nunca se auditó.

Adaptaciones mobile respecto de GTK:
  - El SpinButton de GTK pasa a un TextInput numérico (input_filter="int"):
    SpinnerCantidad de widgets_base tiene tope 99 y el SLA llega a 3650.
    Como el TextInput no acota solo, el rango 1–3650 se valida al aceptar
    y se avisa con mostrar_error (en GTK el spin lo acota en silencio).
  - Se abre desde la tarjeta "Vencidos" del panel "Trabajo pendiente —
    Auditoría" de Inicio (main.py, PanelPendientesAuditoria), igual que en
    GTK: la app no tiene un diálogo de preferencias accesible desde la UI.
  - Los mismos límites DIAS_MIN/DIAS_MAX que el módulo GTK, duplicados a
    propósito: ese módulo importa Gtk y no se puede importar desde Kivy.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.metrics import dp

from widgets_base import (
    barra_superior_dialogo, fila_cancelar_aceptar, mostrar_error, _,
    ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from core.modelo import Modelo

DIAS_MIN = 1
DIAS_MAX = 3650


class DialogoConfigSLAAuditoria(Popup):
    """on_guardado(): se llama sólo si se guardó un valor (para que el
    llamador refresque el panel de Inicio); Cancelar no llama nada."""

    def __init__(self, on_guardado=None, **kwargs):
        self._on_guardado = on_guardado

        actual = Modelo.CONFIG_AUDITORIA_DEFAULTS["dias_sla_auditoria"]
        try:
            actual = float(Modelo.devolver_config_auditoria().get(
                "dias_sla_auditoria", actual))
        except (TypeError, ValueError):
            pass
        actual = min(max(round(actual), DIAS_MIN), DIAS_MAX)

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        box.add_widget(barra_superior_dialogo(
            _("SLA de auditoría"), on_atras=lambda: self.dismiss()))

        lbl = Label(
            text=_("Un equipo se considera vencido si su última auditoría "
                   "es más vieja que esta cantidad de días, o si nunca se "
                   "auditó."),
            halign="left", valign="top", size_hint_y=None, height=dp(96),
            font_size=FUENTE_CHICA)
        lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
        box.add_widget(lbl)

        box.add_widget(Label(text=_("Días de SLA:"), size_hint_y=None,
                             height=dp(24), font_size=FUENTE_NORMAL,
                             halign="left"))
        self.e_dias = TextInput(text=str(actual), multiline=False,
                                input_filter="int", size_hint_y=None,
                                height=ALTO_ENTRY, font_size=FUENTE_NORMAL)
        self.e_dias.bind(on_text_validate=self._guardar)
        box.add_widget(self.e_dias)

        box.add_widget(BoxLayout())  # espaciador
        box.add_widget(fila_cancelar_aceptar(
            on_cancelar=lambda: self.dismiss(), on_aceptar=self._guardar))

        super().__init__(title="", separator_height=0, content=box,
                         size_hint=(1, 1), **kwargs)

    def _guardar(self, *_a):
        try:
            dias = int(self.e_dias.text.strip())
        except ValueError:
            dias = None
        if dias is None or not (DIAS_MIN <= dias <= DIAS_MAX):
            mostrar_error(_("Ingresá un número entero de días entre {} "
                            "y {}.").format(DIAS_MIN, DIAS_MAX))
            return
        Modelo.establecer_config_auditoria("dias_sla_auditoria", float(dias))
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


def abrir_config_sla_auditoria(on_guardado=None):
    DialogoConfigSLAAuditoria(on_guardado=on_guardado).open()
