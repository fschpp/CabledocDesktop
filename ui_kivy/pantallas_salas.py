"""
CableDoc Kivy - Salas, Rack por Sala, Equipos sueltos por Sala.

Equivalente a SalasListado, RackPorSalaListado/_DialogoRackPorSala,
EquiposNoRackSalaListado/_DialogoEquipoNoRackSala de cabledoc.py (GTK).

Salas es un catálogo simple (mismo patrón que Marcas/Tipos), así que se
genera con la fábrica de pantallas_catalogos.py.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, grid_formulario, fila_etiqueta, etiqueta_ultima_edicion,
    titulo_con_nombre,
    mostrar_error, entry_selector, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL,
)
from pantallas_catalogos import _crear_listado_simple
from core.modelo import Modelo

SalasListado = _crear_listado_simple(
    _("Salas"), [_("ID"), _("Nombre")],
    Modelo.devolver_todas_las_salas, Modelo.devolver_sala,
    Modelo.alta_sala, Modelo.modificacion_sala, Modelo.eliminar_sala,
    _("Nueva Sala"), _("Editar Sala"),
)


# ═══════════════════════════════════════════════════════════════════════════
# Rack por Sala
# ═══════════════════════════════════════════════════════════════════════════

class RackPorSalaListado(ListadoPopup):
    def __init__(self, **kwargs):
        super().__init__(_("Rack por Sala"), [_("ID"), _("Sala"), _("Rack")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_rack_por_sala())

    def nuevo(self):
        DialogoRackPorSala(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoRackPorSala(id_=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_rack_por_sala(id_)


class DialogoRackPorSala(Popup):
    def __init__(self, id_=None, on_guardado=None, **kwargs):
        titulo = (_("Editar asignación Rack-Sala") if id_
                 else _("Nueva asignación Rack-Sala"))
        self.id_ = id_
        self.id_sala = None
        self.id_rack = None
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Sala:"))
        hb_sala = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_sala = entry_selector()
        btn_sala = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_sala.bind(on_release=self._sel_sala)
        hb_sala.add_widget(self.e_sala); hb_sala.add_widget(btn_sala)
        g.add_widget(hb_sala)

        fila_etiqueta(g, _("Rack:"))
        hb_rack = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_rack = entry_selector()
        btn_rack = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_rack.bind(on_release=self._sel_rack)
        hb_rack.add_widget(self.e_rack); hb_rack.add_widget(btn_rack)
        g.add_widget(hb_rack)
        box.add_widget(g)

        if id_:
            rows = Modelo.devolver_rack_por_sala(id_)
            if rows:
                self.id_sala = str(rows[0][1])
                self.id_rack = str(rows[0][2])
                self.e_sala.text = s(rows[0][3])
                self.e_rack.text = s(rows[0][4])

        etq = etiqueta_ultima_edicion("rack_por_sala", "id_rack_x_sala", id_)
        if etq:
            box.add_widget(etq)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Guardar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        if id_:
            nombre = " · ".join(
                p for p in (self.e_sala.text.strip(), self.e_rack.text.strip())
                if p)
            titulo = titulo_con_nombre(titulo, nombre)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_sala(self, *_a):
        def _con_sala(id_, nombre, _f):
            self.id_sala = id_
            self.e_sala.text = nombre
        SalasListado(modo_seleccion=True, on_seleccionar=_con_sala).open()

    def _sel_rack(self, *_a):
        from pantallas_racks import RacksListado

        def _con_rack(id_, _nombre, fila):
            self.id_rack = id_
            self.e_rack.text = fila[2]
        RacksListado(modo_seleccion=True, on_seleccionar=_con_rack).open()

    def _guardar(self, *_a):
        if not self.id_sala or not self.id_rack:
            mostrar_error(_("Elegí una sala y un rack antes de guardar."))
            return
        if self.id_:
            Modelo.modificacion_rack_por_sala(self.id_, self.id_sala, self.id_rack)
        else:
            Modelo.alta_rack_por_sala(self.id_sala, self.id_rack)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ═══════════════════════════════════════════════════════════════════════════
# Equipos sueltos por Sala
# ═══════════════════════════════════════════════════════════════════════════

class EquiposNoRackSalaListado(ListadoPopup):
    def __init__(self, **kwargs):
        super().__init__(_("Equipos sueltos por sala"),
                         [_("ID"), _("Sala"), _("Equipo")], **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_equipos_no_rack_sala())

    def nuevo(self):
        DialogoEquipoNoRackSala(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoEquipoNoRackSala(id_=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_equipo_no_rack_sala(id_)


class DialogoEquipoNoRackSala(Popup):
    def __init__(self, id_=None, on_guardado=None, **kwargs):
        titulo = (_("Editar equipo suelto en sala") if id_
                 else _("Nuevo equipo suelto en sala"))
        self.id_ = id_
        self.id_sala = None
        self.id_equipo = None
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Sala:"))
        hb_sala = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_sala = entry_selector()
        btn_sala = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_sala.bind(on_release=self._sel_sala)
        hb_sala.add_widget(self.e_sala); hb_sala.add_widget(btn_sala)
        g.add_widget(hb_sala)

        fila_etiqueta(g, _("Equipo:"))
        hb_eq = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_equipo = entry_selector()
        btn_eq = Button(text="…", size_hint_x=None, width=dp(44),
                       font_size=FUENTE_NORMAL)
        btn_eq.bind(on_release=self._sel_equipo)
        hb_eq.add_widget(self.e_equipo); hb_eq.add_widget(btn_eq)
        g.add_widget(hb_eq)
        box.add_widget(g)

        if id_:
            rows = Modelo.devolver_equipo_no_rack_sala(id_)
            if rows:
                self.id_sala = str(rows[0][1])
                self.id_equipo = str(rows[0][2])
                self.e_sala.text = s(rows[0][3])
                self.e_equipo.text = s(rows[0][4])

        etq = etiqueta_ultima_edicion("equiponoraqueable_por_sala",
                                      "id_equiponoraqueable_por_sala", id_)
        if etq:
            box.add_widget(etq)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Guardar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        if id_:
            nombre = " · ".join(
                p for p in (self.e_sala.text.strip(), self.e_equipo.text.strip())
                if p)
            titulo = titulo_con_nombre(titulo, nombre)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_sala(self, *_a):
        def _con_sala(id_, nombre, _f):
            self.id_sala = id_
            self.e_sala.text = nombre
        SalasListado(modo_seleccion=True, on_seleccionar=_con_sala).open()

    def _sel_equipo(self, *_a):
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_, nombre, _f):
            self.id_equipo = id_
            self.e_equipo.text = nombre
        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()

    def _guardar(self, *_a):
        if not self.id_sala or not self.id_equipo:
            mostrar_error(_("Elegí una sala y un equipo antes de guardar."))
            return
        if self.id_:
            Modelo.modificacion_equipo_no_rack_sala(
                self.id_, self.id_sala, self.id_equipo)
        else:
            Modelo.alta_equipo_no_rack_sala(self.id_sala, self.id_equipo)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
