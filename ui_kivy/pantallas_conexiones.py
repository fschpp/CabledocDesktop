"""
CableDoc Kivy - Conexiones (Equipo+Conector <-> Cable).

Equivalente a ConexionesListado / _DialogoConexion de cabledoc.py (GTK).
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, ComboBuscable, grid_formulario, fila_etiqueta,
    fila_auditoria, titulo_con_nombre, agregar_mantener_presionado, entry_selector,
    mostrar_info, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, fila_cerrar_arriba,
    barra_superior_dialogo, fila_botones_pill,
)
from core.modelo import Modelo


class ConexionesListado(ListadoPopup):
    def __init__(self, id_cable=None, id_equipo=None, **kwargs):
        self.id_cable_filtro = id_cable
        self.id_equipo_filtro = id_equipo
        super().__init__(
            _("Conexiones"),
            [_("ID"), _("Equipo"), _("Conector"), _("Tipo Conector"),
             _("Tipo Equipo"), _("Cable")],
            **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_todas_las_conexiones(
            self.id_cable_filtro, self.id_equipo_filtro)
        # BD: id, equipo, conector, cable, tipo_conector, tipo_equipo, ...
        # Display: ID, Equipo, Conector, TipoConector, TipoEquipo, Cable
        data = [[r[0], r[1], r[2], r[4], r[5], r[3]] for r in rows]
        self._poblar(data)

    def nuevo(self):
        DialogoConexion(id_cable_predef=self.id_cable_filtro,
                        on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoConexion(id_conexion=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_conexion(id_)


class DialogoConexion(Popup):
    def __init__(self, id_conexion=None, id_cable_predef=None,
                on_guardado=None, **kwargs):
        titulo = _("Editar Conexión") if id_conexion else _("Nueva Conexión")
        self.id_conexion = id_conexion
        self.id_cable = id_cable_predef or ""
        self.id_equipo = ""
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Equipo:"))
        hb_eq = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_equipo = entry_selector()
        btn_eq = Button(text="…", size_hint_x=None, width=dp(44),
                       font_size=FUENTE_NORMAL)
        btn_eq.bind(on_release=self._sel_equipo)
        hb_eq.add_widget(self.e_equipo); hb_eq.add_widget(btn_eq)
        g.add_widget(hb_eq)

        fila_etiqueta(g, _("Conector:"))
        self.c_conector = ComboBuscable(datos=[])
        g.add_widget(self.c_conector)

        fila_etiqueta(g, _("Cable:"))
        hb_cable = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_cable = entry_selector()
        btn_cable = Button(text="…", size_hint_x=None, width=dp(44),
                          font_size=FUENTE_NORMAL)
        btn_cable.bind(on_release=self._sel_cable)
        hb_cable.add_widget(self.e_cable); hb_cable.add_widget(btn_cable)
        g.add_widget(hb_cable)

        box.add_widget(g)

        if id_conexion:
            rows = Modelo.devolver_conexion(id_conexion)
            if rows:
                r = rows[0]
                self.id_equipo = s(r[8])
                self.e_equipo.text = s(r[1])
                self.c_conector.set_datos(
                    Modelo.devolver_conectores_de_equipo(self.id_equipo))
                self.c_conector.set_id(s(r[7]))
                self.e_cable.text = s(r[3])
                self.id_cable = s(r[6])
                # Mantener presionado el nombre → abre su edición directa
                # (equipo o cable), solo tiene sentido si ya hay un
                # registro cargado de cada lado.
                agregar_mantener_presionado(self.e_equipo, self._abrir_equipo)
                agregar_mantener_presionado(self.e_cable, self._abrir_cable)
        elif id_cable_predef:
            c_rows = Modelo.devolver_cable(id_cable_predef)
            if c_rows:
                self.e_cable.text = s(c_rows[0][1])

        lbl_aud, btn_aud = fila_auditoria("conexion", "id_conexion", id_conexion)
        if lbl_aud:
            box.add_widget(lbl_aud)

        botones = []
        if btn_aud:
            botones.append({"texto": _("Auditado"), "icono": "lupa_check",
                           "estilo": "terciario",
                           "on_release": lambda: btn_aud.dispatch("on_release")})
        botones.append({"texto": _("Cancelar"), "icono": "cerrar",
                       "estilo": "secundario",
                       "on_release": lambda: self.dismiss()})
        botones.append({"texto": _("Aceptar"), "icono": "guardar",
                       "estilo": "primario", "on_release": self._guardar})
        box.add_widget(fila_botones_pill(botones))

        if id_conexion:
            nombre = " · ".join(
                p for p in (self.e_equipo.text.strip(), self.e_cable.text.strip())
                if p)
            titulo = titulo_con_nombre(titulo, nombre)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_equipo(self, *_a):
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_, nombre, _f):
            self.id_equipo = id_
            self.e_equipo.text = nombre
            self.c_conector.set_datos(
                Modelo.devolver_conectores_de_equipo(self.id_equipo))
            self.c_conector.entry.text = ""
            self.c_conector.id_seleccionado = ""

        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()

    def _sel_cable(self, *_a):
        from pantallas_cables import CablesListado

        def _con_cable(id_, nombre, _f):
            self.id_cable = id_
            self.e_cable.text = nombre

        CablesListado(modo_seleccion=True, on_seleccionar=_con_cable).open()

    def _abrir_equipo(self):
        if not self.id_equipo:
            return
        from pantallas_equipos import DialogoEquipo
        DialogoEquipo(id_equipo=self.id_equipo,
                     on_guardado=self._refrescar_equipo).open()

    def _abrir_cable(self):
        if not self.id_cable:
            return
        from pantallas_cables import DialogoCable
        DialogoCable(id_cable=self.id_cable,
                    on_guardado=self._refrescar_cable).open()

    def _refrescar_equipo(self):
        rows = Modelo.devolver_equipo(self.id_equipo)
        if rows:
            self.e_equipo.text = s(rows[0][1])

    def _refrescar_cable(self):
        rows = Modelo.devolver_cable(self.id_cable)
        if rows:
            self.e_cable.text = s(rows[0][1])

    def _guardar(self, *_a):
        id_conector = self.c_conector.get_id()
        if self.id_conexion:
            Modelo.modificacion_conexion(
                self.id_conexion, self.id_cable or None, id_conector or None, 0)
        else:
            if self.id_cable:
                existentes = Modelo.devolver_todas_las_conexiones(
                    id_cable=self.id_cable)
                if len(existentes) >= 2:
                    id_cable_lleno = self.id_cable
                    self.dismiss()
                    mostrar_info(
                        _("Se alcanzó el máximo de 2 conexiones para este "
                          "cable.\nEliminá una conexión existente antes de "
                          "agregar otra."))
                    ConexionesListado(id_cable=id_cable_lleno).open()
                    return
            Modelo.alta_conexion(self.id_cable or None, id_conector or None, 0)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ─── Editor rápido de conexiones ──────────────────────────────────────────────

class EditorConexionesRapidas(Popup):
    """
    Alta rápida de conexiones: seleccioná Equipo A → conector A →
    cable → Equipo B → conector B y creá la conexión en un solo formulario.
    Equivalente simplificado de EditorConexiones (GTK canvas-based).
    """

    def __init__(self, **kwargs):
        self.id_equipo_a  = "";  self.id_conector_a = ""
        self.id_equipo_b  = "";  self.id_conector_b = ""
        self.id_cable     = ""

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(barra_superior_dialogo(
            _("Alta rápida de conexiones"), on_atras=lambda: self.dismiss()))

        def fila(lbl_txt, widget_entry, btn_txt, btn_cb):
            # Etiqueta arriba, campo (+ botón "…" si corresponde) abajo:
            # en 360dp de ancho no entra cómodo "Equipo A:" + entry + botón
            # todo en una sola fila.
            box.add_widget(Label(text=lbl_txt, size_hint_y=None,
                                 height=dp(20), font_size=FUENTE_CHICA,
                                 halign="left"))
            h = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
            h.add_widget(widget_entry)
            if btn_txt:
                b = Button(text=btn_txt, size_hint_x=None, width=dp(44),
                          font_size=FUENTE_NORMAL)
                b.bind(on_release=btn_cb)
                h.add_widget(b)
            box.add_widget(h)

        # Equipo A
        self.e_eq_a = entry_selector()
        fila(_("Equipo A:"), self.e_eq_a, "…", lambda *_: self._sel_equipo("a"))
        # Conector A
        from widgets_base import ComboBuscable
        self.c_con_a = ComboBuscable(datos=[])
        fila(_("Conector A:"), self.c_con_a, None, None)
        # Separador
        box.add_widget(Label(size_hint_y=None, height=dp(4)))
        # Cable
        self.e_cable = entry_selector()
        fila(_("Cable:"), self.e_cable, "…", lambda *_: self._sel_cable())
        # Equipo B
        self.e_eq_b = entry_selector()
        fila(_("Equipo B:"), self.e_eq_b, "…", lambda *_: self._sel_equipo("b"))
        # Conector B
        self.c_con_b = ComboBuscable(datos=[])
        fila(_("Conector B:"), self.c_con_b, None, None)

        box.add_widget(BoxLayout())  # espaciador

        self._lbl_msg = Label(text="", size_hint_y=None, height=dp(30),
                              font_size=FUENTE_CHICA, color=(0.4, 0.9, 0.4, 1))
        box.add_widget(self._lbl_msg)

        # Botonera: 2 filas (Crear conexión ocupa toda la fila, Otra
        # conexión / Cerrar debajo) — 3 botones de texto largo no entran
        # en 360dp en una sola fila.
        btn_crear = Button(text=_("Crear conexión"), font_size=FUENTE_NORMAL,
                           size_hint_y=None, height=ALTO_BOTON,
                           background_color=(0.18, 0.52, 0.22, 1))
        btn_crear.bind(on_release=lambda *_: self._crear())
        box.add_widget(btn_crear)

        hb2 = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_otra = Button(text=_("Otra conexión"), font_size=FUENTE_CHICA)
        btn_otra.bind(on_release=lambda *_: self._reset_parcial())
        hb2.add_widget(btn_otra)
        box.add_widget(hb2)

        super().__init__(title="", separator_height=0,
                         content=box, size_hint=(1, 1), **kwargs)

    def _sel_equipo(self, lado):
        from pantallas_equipos import EquiposListado

        def _con_eq(id_, nombre, _f):
            cons = Modelo.devolver_conectores_de_equipo(id_)
            datos = [(str(r[0]), str(r[1])) for r in cons]
            if lado == "a":
                self.id_equipo_a = str(id_)
                self.e_eq_a.text = nombre
                self.c_con_a.repoblar(datos)
                self.id_conector_a = ""
            else:
                self.id_equipo_b = str(id_)
                self.e_eq_b.text = nombre
                self.c_con_b.repoblar(datos)
                self.id_conector_b = ""

        EquiposListado(modo_seleccion=True, on_seleccionar=_con_eq).open()

    def _sel_cable(self):
        from pantallas_cables import CablesListado

        def _con_cable(id_, nombre, _f):
            self.id_cable = str(id_)
            self.e_cable.text = nombre

        CablesListado(modo_seleccion=True, on_seleccionar=_con_cable).open()

    def _crear(self):
        id_con_a = self.c_con_a.get_id()
        id_con_b = self.c_con_b.get_id()
        if not self.id_cable:
            self._lbl_msg.text = _("Seleccioná un cable.")
            self._lbl_msg.color = (0.95, 0.45, 0.25, 1)
            return
        if not id_con_a or not id_con_b:
            self._lbl_msg.text = _("Seleccioná conector A y conector B.")
            self._lbl_msg.color = (0.95, 0.45, 0.25, 1)
            return
        Modelo.alta_conexion(self.id_cable, id_con_a, 0)
        Modelo.alta_conexion(self.id_cable, id_con_b, 0)
        self._lbl_msg.text = _("Conexión creada.")
        self._lbl_msg.color = (0.30, 0.90, 0.45, 1)

    def _reset_parcial(self):
        """Mantiene el cable, limpia connectors para hacer otra conexión."""
        self.c_con_a.repoblar(self.c_con_a._datos_originales if hasattr(
            self.c_con_a, '_datos_originales') else [])
        self.c_con_b.repoblar(self.c_con_b._datos_originales if hasattr(
            self.c_con_b, '_datos_originales') else [])
        self._lbl_msg.text = _("Listo para otra conexión con el mismo cable.")
        self._lbl_msg.color = (0.65, 0.65, 0.95, 1)


def abrir_editor_conexiones_rapidas():
    EditorConexionesRapidas().open()
