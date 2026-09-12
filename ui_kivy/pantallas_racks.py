"""
CableDoc Kivy - Racks, Posición en Rack, Frames y Slots.

Equivalente a RacksListado/_DialogoRack, PosicionEnRackListado/
_DialogoPosicionRack, FramesListado/_DialogoFrame, SlotsListado/
_DialogoSlot de cabledoc.py (GTK).

El botón "Ver slots en imagen" / "Vista gráfica del rack" pertenece a
las vistas gráficas (VistaRack, VistaFrameSlots) que se migran más
adelante en la fase 4 (dibujan una grilla completa con Cairo, no sobre
una foto); por ahora muestran un aviso. El selector de rectángulo sobre
imagen para Slots (que sí es de la fase 3, ya migrado) está conectado.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, ComboBuscable, grid_formulario, fila_etiqueta, fila_entry,
    etiqueta_ultima_edicion, fila_auditoria, titulo_con_nombre, mostrar_error, mostrar_info, entry_selector,
    s, _, ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, fila_botones_pill,
)
from core.modelo import Modelo


# ═══════════════════════════════════════════════════════════════════════════
# Racks
# ═══════════════════════════════════════════════════════════════════════════

class RacksListado(ListadoPopup):
    def __init__(self, **kwargs):
        super().__init__(_("Racks"),
                         [_("ID"), _("Número"), _("Nombre"), _("Capacidad (UR)")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_racks())

    def nuevo(self):
        DialogoRack(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoRack(id_rack=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_rack(id_)


class DialogoRack(Popup):
    def __init__(self, id_rack=None, on_guardado=None, **kwargs):
        titulo = _("Editar Rack") if id_rack else _("Nuevo Rack")
        self.id_rack = id_rack
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Número:"))
        self.e_numero = fila_entry(g, "")
        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")
        fila_etiqueta(g, _("Capacidad (UR):"))
        self.e_cap = fila_entry(g, "")
        box.add_widget(g)

        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                r = rows[0]
                self.e_numero.text = s(r[1])
                self.e_nombre.text = s(r[2])
                self.e_cap.text = s(r[3])

            # Apilados: los dos textos completos no entran uno junto al
            # otro en 360dp de ancho.
            btn_disp = Button(text=_("Dispositivos en este rack"),
                             size_hint_y=None, height=ALTO_BOTON,
                             font_size=FUENTE_CHICA)
            btn_disp.bind(on_release=self._ver_dispositivos)
            btn_vista = Button(text=_("Vista gráfica del rack"),
                              size_hint_y=None, height=ALTO_BOTON,
                              font_size=FUENTE_CHICA)
            btn_vista.bind(on_release=self._ver_vista_rack)
            box.add_widget(btn_disp)
            box.add_widget(btn_vista)

        lbl_aud, btn_aud = fila_auditoria("rack", "id_rack", id_rack)
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

        if id_rack:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _ver_dispositivos(self, *_a):
        PosicionEnRackListado(id_rack=self.id_rack).open()

    def _ver_vista_rack(self, *_a):
        from pantallas_vistas import VistaRack
        VistaRack(id_rack=self.id_rack).open()

    def _guardar(self, *_a):
        args = (self.e_numero.text, self.e_nombre.text, self.e_cap.text)
        if self.id_rack:
            Modelo.modificacion_rack(self.id_rack, *args)
        else:
            Modelo.alta_rack(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ═══════════════════════════════════════════════════════════════════════════
# Posición en Rack
# ═══════════════════════════════════════════════════════════════════════════

class PosicionEnRackListado(ListadoPopup):
    def __init__(self, id_rack=None, **kwargs):
        self.id_rack = id_rack
        super().__init__(_("Posición en Rack"),
                         [_("ID"), _("Rack"), _("Orificio"), _("Inventario"),
                          _("Dispositivo"), _("UR")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        if self.id_rack:
            rows = Modelo.devolver_dispositivos_de_un_rack(self.id_rack)
        else:
            rows = Modelo.devolver_todos_dispositivos_en_racks()
        self._poblar(rows)

    def nuevo(self):
        DialogoPosicionRack(id_rack=self.id_rack,
                           on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoPosicionRack(id_posicion=id_,
                           on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_dispositivo_en_rack(id_)


class DialogoPosicionRack(Popup):
    def __init__(self, id_posicion=None, id_rack=None, on_guardado=None,
                **kwargs):
        titulo = (_("Editar Posición en Rack") if id_posicion
                 else _("Nueva Posición en Rack"))
        self.id_posicion = id_posicion
        self.id_rack = id_rack or ""
        self.id_equipo = ""
        self.id_frame = ""
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Rack:"))
        hb_rack = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_rack = entry_selector()
        btn_rack = Button(text="…", size_hint_x=None, width=dp(44),
                         font_size=FUENTE_NORMAL)
        btn_rack.bind(on_release=self._sel_rack)
        hb_rack.add_widget(self.e_rack); hb_rack.add_widget(btn_rack)
        g.add_widget(hb_rack)

        fila_etiqueta(g, _("Orificio:"))
        self.e_orificio = fila_entry(g, "")
        fila_etiqueta(g, _("UR (unidades):"))
        self.e_ur = fila_entry(g, "")

        fila_etiqueta(g, _("Tipo dispositivo:"))
        hb_tipo = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.tb_equipo = ToggleButton(text=_("Equipo"), group="tipo_disp",
                                      state="down", font_size=FUENTE_NORMAL)
        self.tb_frame = ToggleButton(text=_("Frame"), group="tipo_disp",
                                     font_size=FUENTE_NORMAL)
        hb_tipo.add_widget(self.tb_equipo); hb_tipo.add_widget(self.tb_frame)
        g.add_widget(hb_tipo)

        fila_etiqueta(g, _("Equipo:"))
        hb_eq = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_equipo = entry_selector()
        btn_eq = Button(text="…", size_hint_x=None, width=dp(44),
                       font_size=FUENTE_NORMAL)
        btn_eq.bind(on_release=self._sel_equipo)
        hb_eq.add_widget(self.e_equipo); hb_eq.add_widget(btn_eq)
        g.add_widget(hb_eq)

        fila_etiqueta(g, _("Frame:"))
        hb_fr = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_frame = entry_selector()
        btn_fr = Button(text="…", size_hint_x=None, width=dp(44),
                       font_size=FUENTE_NORMAL)
        btn_fr.bind(on_release=self._sel_frame)
        hb_fr.add_widget(self.e_frame); hb_fr.add_widget(btn_fr)
        g.add_widget(hb_fr)

        box.add_widget(g)

        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                self.e_rack.text = s(rows[0][2])

        if id_posicion:
            rows = Modelo.devolver_dispositivo_en_rack(id_posicion)
            if rows:
                r = rows[0]
                self.e_rack.text = s(r[1])
                self.e_orificio.text = s(r[2])
                self.e_ur.text = s(r[5])
                self.id_rack = s(r[6])
                self.id_equipo = s(r[7])
                self.id_frame = s(r[8])
                if self.id_equipo:
                    self.e_equipo.text = s(r[4])
                    self.tb_equipo.state = "down"
                else:
                    self.e_frame.text = s(r[4])
                    self.tb_frame.state = "down"

        etq = etiqueta_ultima_edicion("posicion_en_rack", "id_posicion_en_rack",
                                      id_posicion)
        if etq:
            box.add_widget(etq)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        if id_posicion:
            dispositivo = self.e_equipo.text.strip() or self.e_frame.text.strip()
            nombre = " · ".join(
                p for p in (self.e_rack.text.strip(), dispositivo) if p)
            titulo = titulo_con_nombre(titulo, nombre)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_rack(self, *_a):
        def _con_rack(id_, _nombre, fila):
            self.id_rack = id_
            self.e_rack.text = fila[2]
        RacksListado(modo_seleccion=True, on_seleccionar=_con_rack).open()

    def _sel_equipo(self, *_a):
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_, nombre, _f):
            self.id_equipo = id_
            self.id_frame = ""
            self.e_equipo.text = nombre
            self.e_frame.text = ""
            self.tb_equipo.state = "down"
        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()

    def _sel_frame(self, *_a):
        def _con_frame(id_, nombre, _f):
            self.id_frame = id_
            self.id_equipo = ""
            self.e_frame.text = nombre
            self.e_equipo.text = ""
            self.tb_frame.state = "down"
        FramesListado(modo_seleccion=True, on_seleccionar=_con_frame).open()

    def _guardar(self, *_a):
        equipo = self.id_equipo or None
        frame = self.id_frame or None
        args = (self.id_rack or None, equipo, self.e_orificio.text,
               self.e_ur.text, frame)
        if self.id_posicion:
            Modelo.modificacion_dispositivo_en_rack(self.id_posicion, *args)
        else:
            Modelo.alta_dispositivo_en_rack(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ═══════════════════════════════════════════════════════════════════════════
# Frames
# ═══════════════════════════════════════════════════════════════════════════

class FramesListado(ListadoPopup):
    """filtro_pendiente: None | 'sin_slots' | 'sin_imagen' | 'sin_rect'"""

    def __init__(self, filtro_pendiente=None, **kwargs):
        self._filtro_pendiente = filtro_pendiente
        self._ids_resaltar = set()
        titulo = _("Frames")
        if filtro_pendiente == "sin_slots":
            titulo = _("Frames — Sin slots")
        elif filtro_pendiente == "sin_imagen":
            titulo = _("Frames — Sin imagen")
        elif filtro_pendiente == "sin_rect":
            titulo = _("Frames — Sin slots en imagen")

        botones_extra = [
            (_("Ver slots en imagen"), self._ver_slots_imagen),
            (_("Edición masiva slots"), self._editor_masivo_slots),
        ]
        super().__init__(titulo,
                         [_("ID"), _("Nombre"), _("Marca"), _("Modelo"),
                          _("Inventario")],
                         botones_extra=botones_extra, **kwargs)
        self.cargar_datos()

    def _ver_slots_imagen(self, *_a):
        fila = self._fila()
        if fila:
            from pantallas_vistas import VistaFrameSlots
            VistaFrameSlots(id_frame=fila[0]).open()

    def _editor_masivo_slots(self, *_a):
        fila = self._fila()
        if fila:
            from pantallas_editores_masivos import abrir_editor_masivo_slots
            abrir_editor_masivo_slots(id_frame=fila[0])

    def cargar_datos(self):
        self._ids_resaltar = set()
        color = (0.78, 0.65, 0, 0.5)
        if self._filtro_pendiente == "sin_slots":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE "
                "NOT EXISTS (SELECT 1 FROM slot WHERE id_frame=frame.id_frame)")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_imagen":
            rows = Modelo._query(
                "SELECT id_frame FROM frame WHERE id_imagen IS NULL")
            self._ids_resaltar = {str(r[0]) for r in rows}
        elif self._filtro_pendiente == "sin_rect":
            rows = Modelo._query(
                "SELECT f.id_frame FROM frame f WHERE "
                "EXISTS (SELECT 1 FROM slot WHERE id_frame=f.id_frame) "
                "AND NOT EXISTS (SELECT 1 FROM slot s WHERE s.id_frame=f.id_frame "
                "AND s.rectangulo_x_en_imagen IS NOT NULL)")
            self._ids_resaltar = {str(r[0]) for r in rows}
        todos = Modelo.devolver_todos_los_frames()
        data = [[r[0], r[1], r[2], r[3], r[7]] for r in todos]
        self._poblar(data, ids_resaltar=self._ids_resaltar, color_resaltar=color)

    def _refiltrar(self):
        txt = self.entry_filtro.text.lower()
        self.box_filas.clear_widgets()
        self._fila_widget_sel = None
        self._fila_sel_datos = None
        visibles = 0
        for fila in self._filas_completas:
            if txt and not any(txt in v.lower() for v in fila):
                continue
            if self._filtro_pendiente and self._ids_resaltar:
                if fila[0] not in self._ids_resaltar:
                    continue
            self._agregar_widget_fila(fila, visibles)
            visibles += 1
        self._rv_refrescar()

    def nuevo(self):
        DialogoFrame(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoFrame(id_frame=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_frame(id_)


class DialogoFrame(Popup):
    def __init__(self, id_frame=None, on_guardado=None, **kwargs):
        titulo = _("Editar Frame") if id_frame else _("Nuevo Frame")
        self.id_frame = id_frame
        self.id_marca = ""
        self.id_imagen = ""
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")
        fila_etiqueta(g, _("Marca:"))
        self.c_marca = ComboBuscable(datos=Modelo.devolver_todas_las_marcas())
        g.add_widget(self.c_marca)
        fila_etiqueta(g, _("Modelo:"))
        self.e_modelo = fila_entry(g, "")
        fila_etiqueta(g, _("Inventario:"))
        self.e_inv = fila_entry(g, "")
        fila_etiqueta(g, _("Imagen:"))
        hb_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_imagen = entry_selector()
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=self._sel_imagen)
        hb_img.add_widget(self.e_imagen); hb_img.add_widget(btn_img)
        g.add_widget(hb_img)
        box.add_widget(g)

        if id_frame:
            # 3 botones de texto largo no entran en 360dp de ancho:
            # fila con scroll horizontal, igual que en DialogoEquipo.
            from kivy.uix.scrollview import ScrollView
            scroll_btn2 = ScrollView(size_hint_y=None, height=ALTO_BOTON,
                                     do_scroll_y=False, bar_width=dp(4))
            hb_btn2 = BoxLayout(size_hint_x=None, spacing=dp(6),
                               height=ALTO_BOTON, size_hint_y=None)
            hb_btn2.bind(minimum_width=hb_btn2.setter("width"))
            btn_slots = Button(text=_("Ver Slots"), size_hint_x=None,
                              width=dp(140), font_size=FUENTE_CHICA)
            btn_slots.bind(on_release=self._ver_slots)
            btn_vista = Button(text=_("Ver slots en imagen"),
                              size_hint_x=None, width=dp(190),
                              font_size=FUENTE_CHICA)
            btn_vista.bind(on_release=self._ver_slots_imagen)
            btn_masivo = Button(text=_("Edición masiva"),
                               size_hint_x=None, width=dp(170),
                               font_size=FUENTE_CHICA)
            btn_masivo.bind(on_release=self._editor_masivo_slots)
            hb_btn2.add_widget(btn_slots)
            hb_btn2.add_widget(btn_vista)
            hb_btn2.add_widget(btn_masivo)
            scroll_btn2.add_widget(hb_btn2)
            box.add_widget(scroll_btn2)

        if id_frame:
            rows = Modelo.devolver_frame(id_frame)
            if rows:
                r = rows[0]
                self.e_nombre.text = s(r[1])
                self.id_marca = s(r[4])
                self.c_marca.set_id(self.id_marca)
                self.e_modelo.text = s(r[3])
                self.e_imagen.text = s(r[5])
                self.id_imagen = s(r[6])
                self.e_inv.text = s(r[7])

        lbl_aud, btn_aud = fila_auditoria("frame", "id_frame", id_frame)
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

        if id_frame:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_imagen(self, *_a):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_, nombre, _f):
            self.id_imagen = id_
            self.e_imagen.text = nombre
        ImagenesListado(modo_seleccion=True, on_seleccionar=_con_imagen).open()

    def _ver_slots(self, *_a):
        SlotsListado(id_frame=self.id_frame).open()

    def _ver_slots_imagen(self, *_a):
        from pantallas_vistas import VistaFrameSlots
        VistaFrameSlots(id_frame=self.id_frame).open()

    def _editor_masivo_slots(self, *_a):
        from pantallas_editores_masivos import abrir_editor_masivo_slots
        abrir_editor_masivo_slots(id_frame=self.id_frame)

    def _guardar(self, *_a):
        self.id_marca = self.c_marca.get_id()
        args = (self.e_nombre.text, self.e_inv.text, self.id_marca or None,
               self.id_imagen or None, self.e_modelo.text)
        if self.id_frame:
            Modelo.modificar_frame(self.id_frame, *args)
        else:
            Modelo.agregar_frame(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()


# ═══════════════════════════════════════════════════════════════════════════
# Slots
# ═══════════════════════════════════════════════════════════════════════════

class SlotsListado(ListadoPopup):
    def __init__(self, id_frame, **kwargs):
        self.id_frame = id_frame
        super().__init__(_("Slots"), [_("ID"), _("Slot"), _("Módulo/Equipo")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_slots_del_frame(self.id_frame))

    def nuevo(self):
        DialogoSlot(id_frame=self.id_frame, on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoSlot(id_slot=id_, id_frame=self.id_frame,
                   on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_slot(id_)


class DialogoSlot(Popup):
    def __init__(self, id_slot=None, id_frame=None, on_guardado=None, **kwargs):
        titulo = _("Editar Slot") if id_slot else _("Nuevo Slot")
        self.id_slot = id_slot
        self.id_frame = id_frame or ""
        self.id_equipo = ""
        self.id_imagen = ""
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Nombre:"))
        self.e_nombre = fila_entry(g, "")

        fila_etiqueta(g, _("Equipo:"))
        hb_eq = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_equipo = entry_selector()
        btn_eq = Button(text="…", size_hint_x=None, width=dp(44),
                       font_size=FUENTE_NORMAL)
        btn_eq.bind(on_release=self._sel_equipo)
        hb_eq.add_widget(self.e_equipo); hb_eq.add_widget(btn_eq)
        g.add_widget(hb_eq)

        fila_etiqueta(g, _("Imagen:"))
        hb_img = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_imagen = entry_selector()
        btn_img = Button(text="…", size_hint_x=None, width=dp(44),
                        font_size=FUENTE_NORMAL)
        btn_img.bind(on_release=self._sel_imagen)
        hb_img.add_widget(self.e_imagen); hb_img.add_widget(btn_img)
        g.add_widget(hb_img)

        # Rect X/Y y Ancho/Alto agrupados de a dos por fila (campos
        # chicos, entran bien juntos y ahorran espacio vertical).
        fila_etiqueta(g, _("Rectángulo — X, Y (px):"))
        hb_xy = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_x = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_y = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        hb_xy.add_widget(self.e_x); hb_xy.add_widget(self.e_y)
        g.add_widget(hb_xy)

        fila_etiqueta(g, _("Rectángulo — Ancho, Alto (px):"))
        hb_wh = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_ancho = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_alto = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        hb_wh.add_widget(self.e_ancho); hb_wh.add_widget(self.e_alto)
        g.add_widget(hb_wh)
        box.add_widget(g)

        btn_coords = Button(text=_("Elegir rectángulo en imagen"),
                           size_hint_y=None, height=ALTO_BOTON,
                           font_size=FUENTE_CHICA)
        btn_coords.bind(on_release=self._sel_rect_imagen)
        box.add_widget(btn_coords)

        if id_slot:
            rows = Modelo.devolver_slot(id_slot)
            if rows:
                r = rows[0]
                self.e_nombre.text = s(r[1])
                self.id_equipo = s(r[2])
                self.e_equipo.text = s(r[3])
                self.e_imagen.text = s(r[4])
                self.id_imagen = s(r[5])
                self.e_x.text = s(r[6])
                self.e_y.text = s(r[7])
                self.e_alto.text = s(r[8])
                self.e_ancho.text = s(r[9])
                self.id_frame = s(r[10])

        lbl_aud, btn_aud = fila_auditoria("slot", "id_slot", id_slot)
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

        if id_slot:
            titulo = titulo_con_nombre(titulo, self.e_nombre.text)

        super().__init__(title=titulo, content=box, size_hint=(1, 1),
                         **kwargs)

    def _sel_equipo(self, *_a):
        from pantallas_equipos import EquiposListado

        def _con_equipo(id_, nombre, _f):
            self.id_equipo = id_
            self.e_equipo.text = nombre
        EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()

    def _sel_imagen(self, *_a):
        from pantallas_imagenes import ImagenesListado

        def _con_imagen(id_, nombre, _f):
            self.id_imagen = id_
            self.e_imagen.text = nombre
        ImagenesListado(modo_seleccion=True, on_seleccionar=_con_imagen).open()

    def _sel_rect_imagen(self, *_a):
        from pantallas_avanzadas import CoordenadasImagenSeleccion

        if not self.id_imagen:
            mostrar_info(_("Primero elegí una imagen (botón «…» junto a "
                          "Imagen) para poder marcar el rectángulo sobre "
                          "ella."))
            return

        def _con_coords(resultado):
            self.e_x.text = resultado["x"]
            self.e_y.text = resultado["y"]
            self.e_ancho.text = resultado["ancho"]
            self.e_alto.text = resultado["alto"]

        CoordenadasImagenSeleccion(
            id_imagen=self.id_imagen, solo_xy=False,
            x=self.e_x.text, y=self.e_y.text,
            ancho=self.e_ancho.text, alto=self.e_alto.text,
            on_aceptar=_con_coords).open()

    def _guardar(self, *_a):
        args = (self.e_nombre.text, self.id_equipo or None,
               self.id_frame or None, self.id_imagen or None,
               self.e_x.text, self.e_y.text, self.e_ancho.text, self.e_alto.text)
        if self.id_slot:
            Modelo.modificar_slot(self.id_slot, *args)
        else:
            Modelo.agregar_slot(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
