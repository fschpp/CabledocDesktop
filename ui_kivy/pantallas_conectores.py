"""
CableDoc Kivy - Conectores de un equipo.

Equivalente a ConectoresListado / _DialogoConector /
_DialogoRenombrarConectores de cabledoc.py (GTK).

La selección de coordenadas sobre una imagen ("Elegir coords en
imagen", `abrir_coords_imagen`) pertenece a las "pantallas avanzadas"
(Cairo/DrawingArea en GTK -> Canvas en Kivy) y se migra en la fase 3;
por ahora el botón muestra un aviso y las coordenadas X/Y se pueden
escribir a mano.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, ComboBuscable, grid_formulario, fila_etiqueta, fila_entry,
    fila_auditoria, titulo_con_nombre, mostrar_info, entry_selector, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, seccion_tarjeta,
    fila_botones_pill,
)
from core.modelo import Modelo


class ConectoresListado(ListadoPopup):
    def __init__(self, id_equipo, **kwargs):
        self.id_equipo = id_equipo
        super().__init__(_("Conectores"), [_("ID"), _("Nombre"), _("Tipo")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_conectores_de_equipo(self.id_equipo))

    def nuevo(self):
        DialogoConector(id_equipo=self.id_equipo,
                        on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoConector(id_conector=id_, id_equipo=self.id_equipo,
                        on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_conector(id_)


class DialogoConector(Popup):
    def __init__(self, id_conector=None, id_equipo=None, on_guardado=None,
                **kwargs):
        titulo = _("Editar Conector") if id_conector else _("Nuevo Conector")
        self.id_conector = id_conector
        self.id_equipo = id_equipo or ""
        self.id_imagen = ""
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")

        fila_etiqueta(g, _("Tipo conector:"))
        self.c_tipo = ComboBuscable(datos=Modelo.devolver_tipos_conectores())
        g.add_widget(self.c_tipo)

        fila_etiqueta(g, _("Imagen:"))
        hb_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_imagen = entry_selector()
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=self._sel_imagen)
        hb_img.add_widget(self.e_imagen)
        hb_img.add_widget(btn_img)
        g.add_widget(hb_img)

        fila_etiqueta(g, _("Coordenadas en imagen (X, Y):"))
        hb_xy = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_x = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_y = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        hb_xy.add_widget(self.e_x); hb_xy.add_widget(self.e_y)
        g.add_widget(hb_xy)

        box.add_widget(seccion_tarjeta(_("Datos del conector"), g,
                                       icono="conector"))

        btn_coords = Button(text=_("Elegir coords en imagen"),
                           size_hint_y=None, height=ALTO_BOTON,
                           font_size=FUENTE_CHICA)
        btn_coords.bind(on_release=self._sel_coordenadas)
        box.add_widget(btn_coords)

        if id_conector:
            rows = Modelo.devolver_conector(id_conector)
            if rows:
                r = rows[0]
                self.e_nombre.text = s(r[1])
                self.c_tipo.set_id(s(r[3]))
                self.id_equipo = s(r[4])
                self.e_x.text = s(r[5])
                self.e_y.text = s(r[6])
                self.id_imagen = s(r[7])
                self.e_imagen.text = s(r[8])

        lbl_aud, btn_aud = fila_auditoria("conector", "id_conector", id_conector)
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

        if id_conector:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_imagen(self, *_a):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_img, nombre_img, _fila):
            self.id_imagen = id_img
            self.e_imagen.text = nombre_img

        ImagenesListado(modo_seleccion=True, on_seleccionar=_con_imagen).open()

    def _sel_coordenadas(self, *_a):
        from pantallas_avanzadas import CoordenadasImagenSeleccion

        if not self.id_imagen:
            mostrar_info(_("Primero elegí una imagen (botón «…» junto a "
                          "Imagen) para poder marcar las coordenadas sobre "
                          "ella."))
            return

        def _con_coords(resultado):
            self.e_x.text = resultado["x"]
            self.e_y.text = resultado["y"]

        CoordenadasImagenSeleccion(
            id_imagen=self.id_imagen, solo_xy=True,
            x=self.e_x.text, y=self.e_y.text,
            on_aceptar=_con_coords).open()

    def _guardar(self, *_a):
        nombre = self.e_nombre.text.strip()
        id_tipo_conector = self.c_tipo.get_id()
        x = self.e_x.text.strip()
        y = self.e_y.text.strip()
        if self.id_conector:
            Modelo.modificacion_conector(
                self.id_conector, nombre, self.id_equipo,
                id_tipo_conector or None, self.id_imagen or None, x, y)
        else:
            Modelo.agregar_conector(
                nombre, self.id_equipo, id_tipo_conector or None,
                self.id_imagen or None, x, y)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


class DialogoRenombrarConectores(Popup):
    def __init__(self, id_equipo, on_guardado=None, **kwargs):
        self.id_equipo = id_equipo
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        scroll = ScrollView()
        # cols=1: nombre arriba (referencia) + entry editable abajo. Con
        # cols=2 (label+entry lado a lado) los nombres largos de conector
        # quedaban truncados en 360dp de ancho.
        grid = GridLayout(cols=1, spacing=dp(2), size_hint_y=None,
                         padding=dp(4))
        grid.bind(minimum_height=grid.setter("height"))

        conectores = Modelo.devolver_conectores_de_equipo(id_equipo)
        self.entries = []
        for id_conector, nombre, tipo in conectores:
            lbl = Label(text=s(nombre), halign="left", valign="middle",
                       size_hint_y=None, height=dp(20), font_size=FUENTE_CHICA,
                       color=(0.6, 0.6, 0.6, 1))
            lbl.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
            entry = TextInput(text=s(nombre), multiline=False,
                             size_hint_y=None, height=ALTO_ENTRY,
                             font_size=FUENTE_NORMAL)
            grid.add_widget(lbl)
            grid.add_widget(entry)
            self.entries.append({"id": id_conector, "original": s(nombre),
                                "entry": entry})

        scroll.add_widget(grid)
        box.add_widget(scroll)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        super().__init__(title=_("Renombrar Conectores"), content=box,
                         size_hint=(1, 1), **kwargs)

    def _guardar(self, *_a):
        for item in self.entries:
            nuevo_nombre = item["entry"].text.strip() or item["original"]
            if nuevo_nombre != item["original"]:
                rows = Modelo.devolver_conector(item["id"])
                if rows:
                    r = rows[0]
                    Modelo.modificacion_conector(
                        item["id"], nuevo_nombre, s(r[4]), s(r[3]),
                        s(r[7]), s(r[5]), s(r[6]))
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
