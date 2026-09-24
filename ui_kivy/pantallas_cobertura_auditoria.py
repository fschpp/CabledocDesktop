"""
pantallas_cobertura_auditoria.py — Reporte de cobertura de auditoría (Kivy)
===========================================================================
D3 de plan_auditoria_fecha_edicion_v1.md. Equivalente a
ui_gtk/cobertura_auditoria_ui.py (D2): muestra Modelo.devolver_cobertura_
auditoria(dias) (D1, core/modelo.py) como una tabla de sólo lectura, un
renglón por rack, ordenada de menor a mayor cobertura.

Adaptaciones mobile respecto de GTK (mismo criterio que el resto de los
listados de esta capa):
  - Reusa ListadoPopup, igual que HistorialDiagnosticosListado/
    EscenariosListado (listados de sólo lectura). Como la fila de botones
    CRUD no tiene nada que hacer acá, se quita entera (en vez de dejar
    una barra vacía de ALTO_BOTON en una pantalla de 360dp).
  - Auditados y Total van juntos en una sola columna ("3 / 4"): con
    Rack + Auditados + Cobertura la tabla entra casi sin scroll horizontal,
    y GTK, con más ancho, las separa en dos columnas.
  - La ventana de días (30/60/90/180/365, por defecto 90) son ToggleButton
    en scroll horizontal — mismo patrón que el filtro de estado de
    CablesListado — en vez del combo de GTK.
  - Sin orden por columna (ListadoPopup no lo tiene): se ordena al cargar,
    menor cobertura primero, y el filtro de texto queda como en el resto.
  - Sólo cuenta equipos rackeados (directos o módulos de un frame
    rackeado): equipos sueltos o sobre mueble no están en D1.

Integración en main.py: ítem "Cobertura de auditoría" del grupo
Infraestructura de _abrir_menu_completo() → abrir_cobertura_auditoria().
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.metrics import dp

from widgets_base import (
    ListadoPopup, _, ALTO_ENTRY, FUENTE_CHICA,
)
from core.modelo import Modelo

DIAS_OPCIONES = (30, 60, 90, 180, 365)
DIAS_DEFAULT = 90
_ALTO_RESUMEN = dp(36)


class CoberturaAuditoriaListado(ListadoPopup):
    """Listado de sólo lectura: cobertura de auditoría por rack."""

    def __init__(self, **kwargs):
        self._dias = DIAS_DEFAULT
        super().__init__(
            _("Cobertura de auditoría"),
            [_("ID"), _("Rack"), _("Auditados"), _("Cobertura")],
            **kwargs)

        # Sin CRUD propio: se quita la fila Agregar/Editar/Eliminar entera
        # (y su alto en box_botones). Mantener presionado una fila o Alt+A/
        # E/R siguen llamando a nuevo/editar/eliminar, que no hacen nada.
        fila_botones = self.btn_agregar.parent
        box_botones = fila_botones.parent if fila_botones else None
        if box_botones is not None:
            box_botones.remove_widget(fila_botones)
            box_botones.height = 0

        self._armar_filtros()
        self.cargar_datos()

    # ── Ventana de días + resumen ──
    def _armar_filtros(self):
        self.box_filtros_extra.height = ALTO_ENTRY + _ALTO_RESUMEN + dp(2)

        scroll = ScrollView(size_hint_y=None, height=ALTO_ENTRY,
                            do_scroll_y=False, bar_width=dp(4))
        hb = BoxLayout(size_hint_x=None, height=ALTO_ENTRY, spacing=dp(4))
        hb.bind(minimum_width=hb.setter("width"))
        hb.add_widget(Label(text=_("Ventana:"), size_hint_x=None,
                            width=dp(70), font_size=FUENTE_CHICA))
        for d in DIAS_OPCIONES:
            tb = ToggleButton(
                text=_("Últimos {} días").format(d),
                group="ventana_cobertura_auditoria",
                state="down" if d == DIAS_DEFAULT else "normal",
                size_hint_x=None, width=dp(120), font_size=FUENTE_CHICA)
            tb.bind(on_release=lambda inst, dias=d: self._on_cambio_dias(dias))
            hb.add_widget(tb)
        scroll.add_widget(hb)
        self.box_filtros_extra.add_widget(scroll)

        self.lbl_resumen = Label(
            text="", size_hint_y=None, height=_ALTO_RESUMEN,
            font_size=FUENTE_CHICA, halign="left", valign="middle")
        self.lbl_resumen.bind(size=lambda w, *_a: setattr(
            w, "text_size", (w.width, w.height)))
        self.box_filtros_extra.add_widget(self.lbl_resumen)

    def _on_cambio_dias(self, dias):
        self._dias = dias
        self.cargar_datos()

    def cargar_datos(self):
        cobertura = Modelo.devolver_cobertura_auditoria(dias=self._dias)
        # Menor cobertura primero; a igual cobertura, por nombre de rack.
        ordenados = sorted(
            cobertura.items(),
            key=lambda kv: (kv[1]["porcentaje"], (kv[1]["nombre"] or "").lower()))
        filas = [
            (str(id_rack), d["nombre"] or "",
             f"{d['auditados']} / {d['total']}", f"{d['porcentaje']:.1f} %")
            for id_rack, d in ordenados
        ]
        self._poblar(filas)

        total = sum(d["total"] for d in cobertura.values())
        auditados = sum(d["auditados"] for d in cobertura.values())
        if total:
            pct = 100.0 * auditados / total
            self.lbl_resumen.text = _(
                "Cobertura global: {} de {} equipos auditados en los "
                "últimos {} días ({} %)").format(
                    auditados, total, self._dias, f"{pct:.1f}")
        else:
            self.lbl_resumen.text = _("No hay equipos ubicados en racks.")

    # Sin CRUD propio, ver __init__.
    def nuevo(self):
        pass

    def editar(self, id_):
        pass

    def eliminar(self, id_):
        pass


def abrir_cobertura_auditoria(*_a):
    CoberturaAuditoriaListado().open()
