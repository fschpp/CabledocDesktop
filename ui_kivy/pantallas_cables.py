"""
CableDoc Kivy - Módulo de Cables.

Equivalente a CablesListado / _DialogoCable / _DialogoFusion de cabledoc.py
(GTK). Incluye:
    - Filtro rápido por estado (radiobuttons -> ToggleButton en Kivy)
    - Filas coloreadas según estado / cantidad de conexiones
    - Botón "Nuevo Temporal" (código auto-generado)
    - Botón "Fusionar" (selección de un cable en la tabla + selector del
      segundo, ya que Kivy no tiene un equivalente directo a Ctrl+clic
      multi-selección de Gtk.TreeView)
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, ComboBuscable, grid_formulario, fila_etiqueta, fila_entry,
    fila_auditoria, titulo_con_nombre, mostrar_error, mostrar_info, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA, seccion_tarjeta,
    fila_botones_pill,
)
from tema import tema, Chip
from core.modelo import Modelo


_COLORES_ESTADO = {
    "TEMPORAL":    (0.98, 0.90, 0.60, 0.9),
    "EN_REVISION": (0.87, 0.82, 1.0, 0.9),
    "FUSIONADO":   (0.75, 0.75, 0.75, 0.9),
}
_COLOR_SIN_CONEXION = (1.0, 0.80, 0.80, 0.9)
_COLOR_1_EXTREMO = (1.0, 0.85, 0.70, 0.9)


class CablesListado(ListadoPopup):

    def __init__(self, id_equipo=None, **kwargs):
        self._filtro_estado = "TODOS"
        self.id_equipo_filtro = id_equipo
        botones_extra = [
            (_("Nuevo Temporal"), self._nuevo_temporal),
            (_("Fusionar"), self._fusionar),
        ]
        super().__init__(
            _("Cables"),
            [_("ID"), _("Código"), _("Long."), _("Estado"), _("Extremos")],
            botones_extra=botones_extra, **kwargs)
        self.resultado_codigo = None
        self._agregar_filtros_estado()
        self.cargar_datos()

    # ── Filtro por estado ──
    def _agregar_filtros_estado(self):
        # 6 ToggleButton con texto ("En revisión", "Sin conexión"...) no
        # entran legibles en una fila de 360dp: van en scroll horizontal.
        self.box_filtros_extra.height = ALTO_ENTRY
        scroll = ScrollView(size_hint_y=None, height=ALTO_ENTRY,
                           do_scroll_y=False, bar_width=dp(4))
        hb = BoxLayout(size_hint_x=None, height=ALTO_ENTRY, spacing=dp(4))
        hb.bind(minimum_width=hb.setter("width"))
        opciones = [
            (_("Todos"), "TODOS"),
            (_("Temporales"), "TEMPORAL"),
            (_("En revisión"), "EN_REVISION"),
            (_("1 extremo"), "1_EXTREMO"),
            (_("Sin conexión"), "SIN_CONN"),
            (_("Verificados"), "VERIFICADO"),
        ]
        for lbl_txt, valor in opciones:
            tb = ToggleButton(text=lbl_txt, group="filtro_estado_cable",
                             state="down" if valor == "TODOS" else "normal",
                             size_hint_x=None, width=dp(110),
                             font_size=FUENTE_CHICA)
            tb.bind(on_release=lambda inst, v=valor: self._on_filtro_estado(v))
            hb.add_widget(tb)
        scroll.add_widget(hb)
        self.box_filtros_extra.add_widget(scroll)

    def _on_filtro_estado(self, valor):
        self._filtro_estado = valor
        self.cargar_datos()

    def cargar_datos(self):
        if self.id_equipo_filtro:
            todos = Modelo.devolver_cables_de_equipo(self.id_equipo_filtro)
        else:
            todos = Modelo.devolver_todos_los_cables()
        if self._filtro_estado == "TODOS":
            filas = todos
        elif self._filtro_estado == "1_EXTREMO":
            filas = [r for r in todos if int(r[4] or 0) == 1]
        elif self._filtro_estado == "SIN_CONN":
            filas = [r for r in todos if int(r[4] or 0) == 0]
        else:
            filas = [r for r in todos if s(r[3]) == self._filtro_estado]
        self._poblar_coloreado(filas)

    def _poblar_coloreado(self, filas):
        """Como _poblar, pero el color depende del estado/n_conexiones de
        cada fila en vez de un set de ids a resaltar."""
        n = len(self.columnas)
        filas_norm = []
        self._colores_extra = {}
        for r in filas:
            estado = s(r[3])
            n_cx = int(r[4]) if r[4] is not None else 0
            fila = [s(v) for v in list(r)[:n]]
            while len(fila) < n:
                fila.append("")
            filas_norm.append(fila)
            color = _COLORES_ESTADO.get(estado)
            if color is None:
                if n_cx == 0:
                    color = _COLOR_SIN_CONEXION
                elif n_cx == 1:
                    color = _COLOR_1_EXTREMO
            if color is not None:
                self._colores_extra[fila[0]] = color
        self._filas_completas = filas_norm
        self._refiltrar()

    def nuevo(self):
        DialogoCable(on_guardado=self.cargar_datos).open()

    def _nuevo_temporal(self, *_a):
        codigo = Modelo.siguiente_codigo_temporal()
        Modelo.agregar_cable(
            codigo=codigo, longitud=None, id_tipo_cable=None,
            id_tipo_ficha=None, unidad_longitud=None, metraje_ext1=None,
            metraje_ext2=None, unidad_metraje=None, estado="TEMPORAL",
        )
        self.cargar_datos()
        mostrar_info(f"Cable temporal creado: {codigo}\n\n"
                    "Podés editarlo para agregar tipo, notas y conexiones.")

    def editar(self, id_):
        DialogoCable(id_cable=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_cable(id_)

    def _fusionar(self, *_a):
        fila_a = self._fila()
        if not fila_a:
            mostrar_error(_("Seleccioná primero el cable principal en la "
                          "tabla y luego tocá Fusionar."))
            return
        self._abrir_fusion_con_primero(fila_a)

    def _abrir_fusion_con_primero(self, fila_a):
        """Con un cable ya elegido en la tabla, se abre un segundo
        CablesListado en modo selección para elegir el cable B."""
        def _con_b(id_b, nombre_b, _fila_b):
            if str(id_b) == str(fila_a[0]):
                mostrar_error(_("Elegí dos cables distintos."))
                return
            DialogoFusion(fila_a[0], fila_a[1], id_b, nombre_b,
                         on_guardado=self.cargar_datos).open()

        CablesListado(modo_seleccion=True, on_seleccionar=_con_b).open()


class DialogoFusion(Popup):
    """Equivalente a _DialogoFusion (GTK)."""

    def __init__(self, id_a, codigo_a, id_b, codigo_b, on_guardado=None, **kwargs):
        self.id_a = id_a
        self.id_b = id_b
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        info = Label(
            text=(f"[b]Cable principal:[/b] {codigo_a}  (ID {id_a})\n"
                 f"[b]Cable secundario:[/b] {codigo_b}  (ID {id_b})\n\n"
                 "Las conexiones del secundario pasarán al principal.\n"
                 "El secundario quedará marcado como FUSIONADO (no se borra)."),
            markup=True, halign="left", valign="top", size_hint_y=None,
            height=dp(130), font_size=FUENTE_CHICA)
        info.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
        box.add_widget(info)

        g = grid_formulario(cols=1)
        fila_etiqueta(g, _("Código definitivo:"))
        self.e_codigo = fila_entry(g, codigo_a)
        fila_etiqueta(g, _("Estado final:"))
        self.combo_estado = Spinner(text="VERIFICADO",
                                    values=["VERIFICADO", "TEMPORAL"],
                                    size_hint_y=None, height=ALTO_ENTRY,
                                    font_size=FUENTE_NORMAL)
        g.add_widget(self.combo_estado)
        box.add_widget(g)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Confirmar Fusión"),
                            font_size=FUENTE_CHICA)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._confirmar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        super().__init__(title=_("Fusionar Cables"), content=box,
                         size_hint=(1, 1), **kwargs)

    def _confirmar(self, *_a):
        codigo = self.e_codigo.text.strip()
        if not codigo:
            mostrar_error(_("El código definitivo no puede estar vacío."))
            return
        estado = self.combo_estado.text
        Modelo.fusionar_cables(self.id_a, self.id_b, codigo, estado)
        self.dismiss()
        mostrar_info(
            f"Fusión completada.\n"
            f"Cable definitivo: {codigo} (ID {self.id_a})\n"
            f"Cable {self.id_b} marcado como FUSIONADO.")
        if self._on_guardado:
            self._on_guardado()


class DialogoCable(Popup):
    """Equivalente a _DialogoCable (GTK)."""

    def __init__(self, id_cable=None, on_guardado=None, **kwargs):
        self.id_cable = id_cable
        self._on_guardado = on_guardado
        titulo = _("Editar Cable") if id_cable else _("Nuevo Cable")

        # El formulario original (cols=3) tenía 9 campos + notas: apilado
        # en cols=1 no entra completo en 800dp de alto, así que va dentro
        # de un ScrollView con la botonera fija abajo (patrón ya usado en
        # DialogoAltaRapidaEquipo).
        outer = BoxLayout(orientation="vertical")
        scroll_todo = ScrollView()
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10),
                       size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        scroll_todo.add_widget(box)

        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Código:"))
        hb_cod = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_codigo = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        btn_temp = Button(text=_("Temporal"), size_hint_x=None,
                         width=dp(110), font_size=FUENTE_CHICA)
        btn_temp.bind(on_release=self._asignar_temporal)
        hb_cod.add_widget(self.e_codigo)
        hb_cod.add_widget(btn_temp)
        g.add_widget(hb_cod)

        fila_etiqueta(g, _("Estado:"))
        self.combo_estado = Spinner(text="VERIFICADO",
                                    values=["VERIFICADO", "TEMPORAL", "EN_REVISION"],
                                    size_hint_y=None, height=ALTO_ENTRY,
                                    font_size=FUENTE_NORMAL)
        g.add_widget(self.combo_estado)

        fila_etiqueta(g, _("Tipo cable:"))
        self.c_tipo_cable = ComboBuscable(datos=Modelo.devolver_todos_los_tipos_cable())
        g.add_widget(self.c_tipo_cable)

        fila_etiqueta(g, _("Tipo ficha:"))
        self.c_tipo_ficha = ComboBuscable(datos=Modelo.devolver_todos_los_tipos_ficha())
        g.add_widget(self.c_tipo_ficha)

        # Longitud + unidad, y los dos metrajes + su unidad, agrupados de
        # a pares por fila para no ocupar 5 filas completas apiladas.
        fila_etiqueta(g, _("Longitud / Unidad:"))
        hb_long = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_longitud = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_unidad = TextInput(multiline=False, font_size=FUENTE_NORMAL,
                                  size_hint_x=0.5)
        hb_long.add_widget(self.e_longitud); hb_long.add_widget(self.e_unidad)
        g.add_widget(hb_long)

        fila_etiqueta(g, _("Metraje ext. 1 / ext. 2:"))
        hb_met = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_met1 = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        self.e_met2 = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        hb_met.add_widget(self.e_met1); hb_met.add_widget(self.e_met2)
        g.add_widget(hb_met)

        fila_etiqueta(g, _("Unidad metraje:"))
        self.e_unidad_met = fila_entry(g, "")

        box.add_widget(seccion_tarjeta(_("Datos del cable"), g,
                                       icono="cables"))

        if id_cable:
            btn_conex = Button(text=_("Ver Conexiones"),
                              size_hint_y=None, height=ALTO_BOTON,
                              font_size=FUENTE_CHICA)
            btn_conex.bind(on_release=self._ver_conexiones)
            box.add_widget(btn_conex)

        self.tv_notas = TextInput(multiline=True, size_hint_y=None,
                                  height=dp(120), font_size=FUENTE_NORMAL)
        box.add_widget(seccion_tarjeta(_("Notas de relevamiento"),
                                       self.tv_notas))

        if id_cable:
            rows = Modelo.devolver_cable(id_cable)
            if rows:
                r = rows[0]
                self.e_codigo.text = s(r[1])
                self.c_tipo_cable.set_id(s(r[2]))
                self.c_tipo_ficha.set_id(s(r[4]))
                self.e_longitud.text = s(r[6])
                self.e_unidad.text = s(r[7])
                self.e_met1.text = s(r[8])
                self.e_unidad_met.text = s(r[9])
                self.e_met2.text = s(r[10])
                estado = s(r[11]) or "VERIFICADO"
                if estado in self.combo_estado.values:
                    self.combo_estado.text = estado
                notas = s(r[12])
                if notas:
                    self.tv_notas.text = notas

        lbl_aud, btn_aud = fila_auditoria("cable", "id_cable", id_cable)
        if lbl_aud:
            box.add_widget(lbl_aud)

        outer.add_widget(scroll_todo)

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
        outer.add_widget(fila_botones_pill(botones))

        if id_cable:
            titulo = titulo_con_nombre(titulo, self.e_codigo.text)

        super().__init__(title=titulo, content=outer, size_hint=(1, 1),
                         **kwargs)

    def _asignar_temporal(self, *_a):
        self.e_codigo.text = Modelo.siguiente_codigo_temporal()
        self.combo_estado.text = "TEMPORAL"

    def _ver_conexiones(self, *_a):
        # Importación diferida: el módulo de Conexiones se migra en fase 2.
        try:
            from pantallas_conexiones import ConexionesListado
            ConexionesListado(id_cable=self.id_cable).open()
        except ImportError:
            mostrar_info(_("El módulo de Conexiones se migra en la fase 2."))

    def _guardar(self, *_a):
        id_tipo_cable = self.c_tipo_cable.get_id()
        id_tipo_ficha = self.c_tipo_ficha.get_id()
        args = (
            self.e_codigo.text,
            self.e_longitud.text,
            id_tipo_cable or None,
            id_tipo_ficha or None,
            self.e_unidad.text,
            self.e_met1.text,
            self.e_met2.text,
            self.e_unidad_met.text,
            self.combo_estado.text or "VERIFICADO",
            self.tv_notas.text.strip() or None,
        )
        if self.id_cable:
            Modelo.modificar_cable(self.id_cable, *args)
        else:
            Modelo.agregar_cable(*args)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
