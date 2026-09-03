#!/usr/bin/env python3
"""
cables_conexiones_ui.py — CableDoc GTK3

Dominio Cables y Conexiones, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 2).

Contiene:
  - CablesListado, _DialogoFusion, _DialogoEligeLadoFantasma, _DialogoCable
  - ConexionesListado, _DialogoConexion

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos seis nombres sin cambios para que
ningún `from cabledoc import X` externo se rompa.

Referencias a clases de otros dominios que todavía viven en `cabledoc.py`
(EquiposListado, _DialogoEquipo, _DialogoConector) se resuelven con import
diferido dentro del método que las usa, siguiendo el mismo patrón que ya
usa el proyecto para evitar ciclos de import (cabledoc.py importa este
módulo a nivel de tope para reexportar sus símbolos).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from modelo import Modelo, DB_PATH

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    mostrar_info,
    VentanaListado,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
    _pack_ultima_edicion,
    _parse_float_opt,
    _fmt_float_opt,
)
from pantallas_avanzadas import abrir_historial_diagnosticos


# ─── Cables ───────────────────────────────────────────────────────────────────

class CablesListado(VentanaListado):
    """
    Listado de cables con:
    - Columnas: ID, Código, Longitud, Estado, Conexiones
    - Filas coloreadas según estado (TEMPORAL=amarillo, EN_REVISION=violeta,
      1 extremo=naranja, sin conexiones=rojo suave)
    - Filtro rápido por estado
    - Botón "Nuevo Temporal" (código auto-generado)
    - Botón "Fusionar" para unir dos cables temporales
    """

    # Colores RGBA por estado
    _COLORES = {
        "TEMPORAL":   Gdk.RGBA(1.0,  0.93, 0.60, 1.0),   # amarillo
        "EN_REVISION":Gdk.RGBA(0.87, 0.82, 1.0,  1.0),   # violeta
        "FUSIONADO":  Gdk.RGBA(0.75, 0.75, 0.75, 1.0),   # gris
        "VERIFICADO": None,                                # sin color
        "1_EXTREMO":  Gdk.RGBA(1.0,  0.85, 0.70, 1.0),   # naranja
        "SIN_CONN":   Gdk.RGBA(1.0,  0.80, 0.80, 1.0),   # rojo suave
    }

    def __init__(self, parent=None, modo_seleccion=False):
        botones_extra = [
            ("⚡ Nuevo Temporal", self._nuevo_temporal),
            ("🔀 Fusionar",       self._fusionar),
            ("🩺 Historial de diagnósticos", self._ver_historial_diagnosticos),
            ("📋 Ver incidentes", self._ver_bitacora_incidentes),
        ]
        super().__init__(
            _("Cables"),
            [_("ID"), _("Código"), _("Long."), _("Estado"), _("Extremos")],
            parent=parent,
            modo_seleccion=modo_seleccion,
            botones_extra=botones_extra,
        )
        self.resultado_codigo = None
        self._filtro_estado = "TODOS"
        self._color_col_agregada = False
        self._agregar_filtros_estado()
        self.cargar_datos()

    def _agregar_filtros_estado(self):
        """Agrega botonera de filtro rápido por estado encima del TreeView."""
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hb.set_margin_start(6); hb.set_margin_end(6)
        hb.set_margin_top(2);   hb.set_margin_bottom(4)
        lbl = Gtk.Label(label=_("Estado:"))
        lbl.set_margin_end(4)
        hb.pack_start(lbl, False, False, 0)
        opciones = [
            (_("Todos"),        "TODOS"),
            (_("Temporales"),   "TEMPORAL"),
            (_("En revisión"),  "EN_REVISION"),
            ("1 extremo",    "1_EXTREMO"),
            (_("Sin conexión"), "SIN_CONN"),
            (_("Verificados"),  "VERIFICADO"),
        ]
        primero = None
        for lbl_txt, valor in opciones:
            rb = Gtk.RadioButton.new_with_label_from_widget(primero, lbl_txt)
            if primero is None:
                primero = rb
            rb.connect("toggled", self._on_filtro_estado, valor)
            hb.pack_start(rb, False, False, 0)
        # Insertar en content_area en posición 1
        # (0 = barra búsqueda, 1 = aquí, 2 = ScrolledWindow con tv, 3 = botones)
        ca = self.get_content_area()
        ca.pack_start(hb, False, False, 0)
        # Reordenar: buscar el ScrolledWindow y poner hb antes
        children = ca.get_children()
        sw_idx = next((i for i, c in enumerate(children)
                       if isinstance(c, Gtk.ScrolledWindow)), 1)
        ca.reorder_child(hb, sw_idx)
        hb.show_all()

    def _on_filtro_estado(self, rb, valor):
        if rb.get_active():
            self._filtro_estado = valor
            self.cargar_datos()

    def _on_seleccionar(self, btn):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[1]
            self.resultado_codigo = f[1]
            self.response(Gtk.ResponseType.OK)

    def cargar_datos(self):
        todos = Modelo.devolver_todos_los_cables()
        # Filtrar según estado seleccionado
        if self._filtro_estado == "TODOS":
            filas = todos
        elif self._filtro_estado == "1_EXTREMO":
            filas = [r for r in todos if int(r[4] or 0) == 1]
        elif self._filtro_estado == "SIN_CONN":
            filas = [r for r in todos if int(r[4] or 0) == 0]
        else:
            filas = [r for r in todos if s(r[3]) == self._filtro_estado]
        # _colorear_filas puebla el store y aplica colores
        self._colorear_filas(filas)

    def _colorear_filas(self, filas):
        """Puebla el store aplicando colores según estado y conexiones."""
        self.store.clear()
        n = len(self.columnas)
        for r in filas:
            # r: (id, codigo, longitud, estado, n_conexiones)
            estado = s(r[3])
            n_cx   = int(r[4]) if r[4] is not None else 0
            
            fila_str = [s(v) for v in list(r)[:n]]
            while len(fila_str) < n:
                fila_str.append("")
                
            color = "#ffffff"
            if estado == "TEMPORAL":
                color = "#fae69a"
            elif estado == "EN_REVISION":
                color = "#ded8ff"
            elif estado == "FUSIONADO":
                color = "#c0c0c0"
            elif n_cx == 0:
                color = "#ffcccc"
            elif n_cx == 1:
                color = "#ffd9b3"
                
            self.store.append(fila_str + [color])

    def nuevo(self):
        dlg = _DialogoCable(parent=self)
        dlg.run_and_destroy()

    def _nuevo_temporal(self, *a):
        """Crea un cable con código temporal auto-generado."""
        codigo = Modelo.siguiente_codigo_temporal()
        Modelo.agregar_cable(
            codigo=codigo,
            longitud=None, id_tipo_cable=None, id_tipo_ficha=None,
            unidad_longitud=None, metraje_ext1=None, metraje_ext2=None,
            unidad_metraje=None, estado="TEMPORAL",
        )
        self.cargar_datos()
        mostrar_info(self, f"Cable temporal creado: {codigo}\n\n"
                          "Podés editarlo para agregar tipo, notas y conexiones.")

    def editar(self, id_):
        dlg = _DialogoCable(id_cable=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_cable(id_)

    def _fusionar(self, *a):
        """Abre el diálogo de fusión de cables."""
        filas_sel = self._filas_seleccionadas()
        if len(filas_sel) < 2:
            mostrar_error(self, "Seleccioná exactamente dos cables para fusionar.\n"
                               "(Usá Ctrl+clic para seleccionar múltiples filas.)")
            return
        if len(filas_sel) > 2:
            mostrar_error(self, "Seleccioná exactamente dos cables.")
            return
        id_a, codigo_a = filas_sel[0][0], filas_sel[0][1]
        id_b, codigo_b = filas_sel[1][0], filas_sel[1][1]
        dlg = _DialogoFusion(id_a, codigo_a, id_b, codigo_b, parent=self)
        dlg.run_and_destroy()
        self.cargar_datos()

    def _ver_historial_diagnosticos(self, *a):
        """'Prontuario' del cable seleccionado — fallas recurrentes en el
        mismo tramo (ver plan_asistente_diagnostico_fallas.md)."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un cable primero.")
            return
        abrir_historial_diagnosticos(DB_PATH, parent=self, id_cable=f[0])

    def _ver_bitacora_incidentes(self, *a):
        """Bitácora de incidentes del cable seleccionado (ver
        plan_bitacora_incidentes_riesgo_analogico.md)."""
        f = self._fila()
        if not f:
            mostrar_error(self, "Seleccioná un cable primero.")
            return
        from bitacora_ui import abrir_bitacora_incidentes
        abrir_bitacora_incidentes(parent=self, id_cable=f[0])

    def _filas_seleccionadas(self):
        """Retorna lista de filas seleccionadas (soporta selección múltiple)."""
        sel = self.tv.get_selection()
        sel.set_mode(Gtk.SelectionMode.MULTIPLE)
        store, paths = sel.get_selected_rows()
        result = []
        for path in paths:
            it = store.get_iter(path)
            row = [store.get_value(it, c) for c in range(len(self.columnas))]
            result.append(row)
        return result


class _DialogoFusion(Gtk.Dialog):
    """Diálogo para fusionar dos cables temporales en uno definitivo."""

    def __init__(self, id_a, codigo_a, id_b, codigo_b, parent=None):
        super().__init__(title=_("Fusionar Cables"), transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         "✔ Confirmar Fusión", Gtk.ResponseType.OK)
        self.set_default_size(480, 320)
        self.id_a = id_a; self.id_b = id_b

        ca = self.get_content_area()
        ca.set_spacing(8); ca.set_margin_start(12); ca.set_margin_end(12)
        ca.set_margin_top(10); ca.set_margin_bottom(10)

        # Descripción
        info = Gtk.Label()
        info.set_markup(
            f"<b>Cable principal:</b>  {codigo_a}  (ID {id_a})\n"
            f"<b>Cable secundario:</b> {codigo_b}  (ID {id_b})\n\n"
            "Las conexiones del secundario pasarán al principal.\n"
            "El secundario quedará marcado como <i>FUSIONADO</i> (no se borra)."
        )
        info.set_line_wrap(True); info.set_xalign(0)
        ca.pack_start(info, False, False, 0)

        sep = Gtk.Separator(); ca.pack_start(sep, False, False, 4)

        g = _grid()
        _lbl_entry(g, _("Código definitivo:"), 0)
        self.e_codigo = _entry(g, 0)
        self.e_codigo.set_text(codigo_a)
        self.e_codigo.set_placeholder_text("Escribí el código final del cable")

        _lbl_entry(g, _("Estado final:"), 1)
        self.combo_estado = Gtk.ComboBoxText()
        for opt in ["VERIFICADO", "TEMPORAL"]:
            self.combo_estado.append_text(opt)
        self.combo_estado.set_active(0)
        g.attach(self.combo_estado, 1, 1, 2, 1)

        ca.pack_start(g, False, False, 0)
        self.show_all()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            codigo = self.e_codigo.get_text().strip()
            estado = self.combo_estado.get_active_text()
            if not codigo:
                mostrar_error(self, "El código definitivo no puede estar vacío.")
            else:
                Modelo.fusionar_cables(
                    self.id_a, self.id_b, codigo, estado
                )
                mostrar_info(self,
                    f"Fusión completada.\n"
                    f"Cable definitivo: {codigo} (ID {self.id_a})\n"
                    f"Cable {self.id_b} marcado como FUSIONADO.")
        self.destroy()


class _DialogoEligeLadoFantasma(Gtk.Dialog):
    """plan_desarrollo_fantasma_rapido.md — mini-diálogo para elegir qué
    extremo (A/B) del cable se está documentando como desconectado.
    Sólo se muestra cuando el cable no tiene ningún extremo cargado
    todavía; con un extremo ya cargado el lado se infiere solo (ver
    _DialogoCable._marcar_extremo_desconectado)."""

    RESP_A = 1
    RESP_B = 2

    def __init__(self, parent):
        super().__init__(title=_("Marcar extremo desconectado"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Extremo A  (queda OUT)"), self.RESP_A)
        self.add_button(_("Extremo B  (queda IN)"), self.RESP_B)

        ca = self.get_content_area()
        ca.set_margin_start(14); ca.set_margin_end(14)
        ca.set_margin_top(12);   ca.set_margin_bottom(6)
        lbl = Gtk.Label(label=_(
            "¿Qué extremo del cable estás documentando como "
            "desconectado?"))
        lbl.set_line_wrap(True)
        lbl.set_xalign(0)
        ca.pack_start(lbl, False, False, 0)
        self.show_all()


class _DialogoCable(Gtk.Dialog):
    def __init__(self, id_cable=None, parent=None):
        titulo = _("Editar Cable") if id_cable else _("Nuevo Cable")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(500, 480)
        self.id_cable = id_cable
        self.id_tipo_cable = ""
        self.id_tipo_ficha = ""

        ca = self.get_content_area()
        ca.set_margin_start(10); ca.set_margin_end(10)
        ca.set_margin_top(8);    ca.set_margin_bottom(8)

        g = _grid()
        _lbl_entry(g, _("Código:"), 0)
        # Fila código con botón "Generar temporal"
        hb_cod = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.e_codigo = Gtk.Entry(); self.e_codigo.set_hexpand(True)
        btn_temp = Gtk.Button(label=_("⚡ Temporal"))
        btn_temp.set_tooltip_text(_("Asignar código temporal auto-generado"))
        btn_temp.connect("clicked", self._asignar_temporal)
        hb_cod.pack_start(self.e_codigo, True, True, 0)
        hb_cod.pack_start(btn_temp, False, False, 0)
        g.attach(hb_cod, 1, 0, 2, 1)

        _lbl_entry(g, _("Estado:"), 1)
        self.combo_estado = Gtk.ComboBoxText()
        for opt in ["VERIFICADO", "TEMPORAL", "EN_REVISION"]:
            self.combo_estado.append_text(opt)
        self.combo_estado.set_active(0)
        g.attach(self.combo_estado, 1, 1, 2, 1)

        _lbl_entry(g, _("Tipo cable:"), 2)
        self.c_tipo_cable = _searchable_combo(g, 2, Modelo.devolver_todos_los_tipos_cable())
        _lbl_entry(g, _("Tipo ficha:"), 3)
        self.c_tipo_ficha = _searchable_combo(g, 3, Modelo.devolver_todos_los_tipos_ficha())
        _lbl_entry(g, _("Longitud:"), 4)
        self.e_longitud = _entry(g, 4)
        _lbl_entry(g, _("Unidad long.:"), 5)
        self.e_unidad = _entry(g, 5)
        _lbl_entry(g, _("Metraje ext. 1:"), 6)
        self.e_met1 = _entry(g, 6)
        _lbl_entry(g, _("Metraje ext. 2:"), 7)
        self.e_met2 = _entry(g, 7)
        _lbl_entry(g, _("Unidad metraje:"), 8)
        self.e_unidad_met = _entry(g, 8)

        # Override de ancho de banda (plan_riesgo_senal_audio.md, riesgo #2)
        # — sólo para el patchcord puntual que no representa a su tipo
        # nominal; el default sale de tipo_cable.ancho_banda_mhz. Sólo
        # tiene sentido con el cable ya guardado.
        self.e_ancho_banda_override = None
        if id_cable:
            _lbl_entry(g, _("Ancho de banda (override, MHz):"), 9)
            self.e_ancho_banda_override = _entry(g, 9)
            self.e_ancho_banda_override.set_tooltip_text(
                _("Vacío = usar el default de su tipo de cable. Cargar sólo "
                  "si ESTE cable puntual no representa a su tipo nominal "
                  "(ej. un patchcord viejo/degradado)."))
            fila_boton_conex = 10
        else:
            fila_boton_conex = 9

        if id_cable:
            btn_conex = Gtk.Button(label=_("🔗 Ver Conexiones"))
            btn_conex.set_tooltip_text(_("Ver todas las conexiones asociadas a este cable"))
            btn_conex.connect("clicked", self._ver_conexiones)
            g.attach(btn_conex, 1, fila_boton_conex, 2, 1)

            # plan_simular_remocion_cadena.md
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se desconecta "
                "este cable (no destructivo, no toca la base)."))
            btn_remocion.connect("clicked", self._simular_remocion)
            g.attach(btn_remocion, 1, fila_boton_conex + 1, 2, 1)

            # plan_desarrollo_extension_cable.md — empalme ficha-contra-
            # ficha con otro cable, sin equipo ni barril de por medio.
            btn_extender = Gtk.Button(label=_("🔗 Extender con otro cable"))
            btn_extender.set_tooltip_text(_(
                "Cargar un punto donde este cable se empalma directamente "
                "con la ficha de otro cable (tramo intermedio de la cadena "
                "analógica, sin equipo de por medio)."))
            btn_extender.connect("clicked", self._extender_cable)
            g.attach(btn_extender, 1, fila_boton_conex + 2, 2, 1)

            # Ajuste de usabilidad post-uso real: ver de un vistazo el
            # recorrido real completo de este cable, atravesando
            # cualquier extensión de por medio, hasta el equipo real de
            # cada punta (o hasta un extremo suelto si la cadena está
            # incompleta) — ver plan_desarrollo_extension_cable.md.
            btn_cadena = Gtk.Button(label=_("🔗 Ver cadena completa"))
            btn_cadena.set_tooltip_text(_(
                "Ver el recorrido real completo de este cable: equipo → "
                "cable → extensión → cable → ... → equipo, atravesando "
                "cualquier extensión intermedia."))
            btn_cadena.connect("clicked", self._ver_cadena_cable)
            g.attach(btn_cadena, 1, fila_boton_conex + 3, 2, 1)

            # plan_desarrollo_fantasma_rapido.md — alta rápida de un
            # equipo FANTASMA para documentar un extremo de cable
            # confirmado desconectado, sin tipeo manual del nombre ni
            # elección forzada de IN/OUT.
            btn_fantasma = Gtk.Button(label=_("🔌 Marcar extremo desconectado"))
            btn_fantasma.set_tooltip_text(_(
                "Documentar que recorriste este cable hasta el final y "
                "confirmaste que ese extremo está suelto: crea un equipo "
                "FANTASMA con el nombre y el conector ya armados, sin "
                "pedir Marca/Modelo/Inventario/Serie."))
            btn_fantasma.connect("clicked", self._marcar_extremo_desconectado)
            g.attach(btn_fantasma, 1, fila_boton_conex + 4, 2, 1)
            self._btn_fantasma = btn_fantasma
            self._actualizar_estado_btn_fantasma()

        ca.pack_start(g, False, False, 0)

        # ── Armado (plan_bitacora_incidentes_riesgo_analogico.md §3.3) ──
        # A nivel de CABLE completo (a diferencia de la sección "Armado"
        # de _DialogoConector, que es por extremo) — para cuando no está
        # claro cuál de los dos extremos es el problema.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_cable:
            Modelo.asegurar_tablas_bitacora()
            frame_armado = Gtk.Frame(label=" " + _("Armado") + " ")
            g5 = _grid()
            _lbl_entry(g5, _("¿Armado correcto?:"), 0)
            self.c_armado = Gtk.ComboBoxText()
            self.c_armado.append("", _("No verificado"))
            self.c_armado.append("1", _("Correcto"))
            self.c_armado.append("0", _("Mal armado"))
            g5.attach(self.c_armado, 1, 0, 2, 1)
            _lbl_entry(g5, _("Detalle:"), 1)
            self.e_detalle_armado = _entry(g5, 1)
            frame_armado.add(g5)
            ca.pack_start(frame_armado, False, False, 6)

        # Notas de relevamiento
        sep = Gtk.Separator(); ca.pack_start(sep, False, False, 6)
        lbl_notas = Gtk.Label(label=_("Notas de relevamiento:"))
        lbl_notas.set_xalign(0); lbl_notas.set_margin_start(4)
        ca.pack_start(lbl_notas, False, False, 0)
        scroll_n = Gtk.ScrolledWindow()
        scroll_n.set_min_content_height(70)
        self.tv_notas = Gtk.TextView()
        self.tv_notas.set_wrap_mode(Gtk.WrapMode.WORD)
        self.tv_notas.get_buffer().set_text("")
        scroll_n.add(self.tv_notas)
        ca.pack_start(scroll_n, True, True, 0)

        if id_cable:
            rows = Modelo.devolver_cable(id_cable)
            if rows:
                r = rows[0]
                # 0:id 1:codigo 2:id_tipo_cable 3:nombre_tipo_cable
                # 4:id_tipo_ficha 5:nombre_tipo_ficha 6:longitud
                # 7:unidad_longitud 8:metraje_ext1 9:unidad_metraje
                # 10:metraje_ext2 11:estado 12:notas_relevamiento
                self.e_codigo.set_text(s(r[1]))
                _set_combo_id(self.c_tipo_cable, s(r[2]))
                _set_combo_id(self.c_tipo_ficha, s(r[4]))
                self.e_longitud.set_text(s(r[6]))
                self.e_unidad.set_text(s(r[7]))
                self.e_met1.set_text(s(r[8]))
                self.e_unidad_met.set_text(s(r[9]))
                self.e_met2.set_text(s(r[10]))
                estado = s(r[11]) or "VERIFICADO"
                opciones = ["VERIFICADO", "TEMPORAL", "EN_REVISION"]
                if estado in opciones:
                    self.combo_estado.set_active(opciones.index(estado))
                notas = s(r[12])
                if notas:
                    self.tv_notas.get_buffer().set_text(notas)
                if self.e_ancho_banda_override is not None:
                    ancho_ov = Modelo.devolver_ancho_banda_override_cable(id_cable)
                    self.e_ancho_banda_override.set_text(_fmt_float_opt(ancho_ov))

                if self.c_armado is not None:
                    fila_arm = Modelo._query(
                        "SELECT es_armado_correcto, detalle_armado FROM cable "
                        "WHERE id_cable=?", (id_cable,))
                    if fila_arm and fila_arm[0][0] is not None:
                        self.c_armado.set_active_id(str(int(fila_arm[0][0])))
                    else:
                        self.c_armado.set_active_id("")
                    if fila_arm and fila_arm[0][1]:
                        self.e_detalle_armado.set_text(s(fila_arm[0][1]))

        _pack_ultima_edicion(self, "cable", "id_cable", id_cable)
        self.show_all()

    def _asignar_temporal(self, btn):
        codigo = Modelo.siguiente_codigo_temporal()
        self.e_codigo.set_text(codigo)
        opciones = ["VERIFICADO", "TEMPORAL", "EN_REVISION"]
        self.combo_estado.set_active(opciones.index("TEMPORAL"))

    def _ver_conexiones(self, btn):
        dlg = ConexionesListado(parent=self, id_cable=self.id_cable)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _simular_remocion(self, btn):
        """plan_simular_remocion_cadena.md — delega en el helper único de
        impacto_ui.py (mismo que usan Equipo/Rack/Conexión) para no
        repetir la construcción del analyzer ni el manejo de errores."""
        from impacto_ui import simular_remocion_y_mostrar
        rows = Modelo.devolver_cable(self.id_cable)
        codigo = s(rows[0][1]) if rows else self.id_cable
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {codigo}",
            "simular_desconexion", self.id_cable)

    def _extender_cable(self, btn):
        """plan_desarrollo_extension_cable.md — abre el alta de extensión
        con este cable ya fijado como Extremo A."""
        from extension_cable_ui import abrir_extender_cable
        abrir_extender_cable(parent=self, id_cable=self.id_cable)

    def _ver_cadena_cable(self, btn):
        """Ajuste de usabilidad post-uso real — ver PROGRESS.md."""
        from extension_cable_ui import abrir_ver_cadena
        abrir_ver_cadena(parent=self, id_cable=self.id_cable)

    def _actualizar_estado_btn_fantasma(self):
        """plan_desarrollo_fantasma_rapido.md — deshabilita el botón si el
        cable ya tiene sus dos extremos cargados (no queda ningún lado
        'suelto' para documentar como FANTASMA)."""
        extremos = Modelo.devolver_extremos_de_cable(self.id_cable)
        if len(extremos) >= 2:
            self._btn_fantasma.set_sensitive(False)
            self._btn_fantasma.set_tooltip_text(
                _("Este cable ya tiene sus dos extremos documentados."))

    def _marcar_extremo_desconectado(self, btn):
        """plan_desarrollo_fantasma_rapido.md — alta rápida de un equipo
        FANTASMA para documentar un extremo de este cable confirmado
        desconectado: nombre y conector se generan solos (sin tipeo ni
        elección manual de IN/OUT), reemplazando el alta pesada de
        _DialogoEquipo completo + plantilla de nombre a mano fuera del
        sistema."""
        extremos = Modelo.devolver_extremos_de_cable(self.id_cable)
        if len(extremos) >= 2:
            mostrar_info(self, _(
                "Este cable ya tiene sus dos extremos documentados."))
            return

        # Con un extremo ya cargado, el lado se infiere solo (A↔B, OUT↔IN)
        # — sólo se pregunta cuando no hay ninguna referencia (0 extremos)
        # o cuando el único extremo existente es un extremo "suelto" de
        # una Extensión (sin conector, no se puede inferir el tipo).
        lado = None
        if len(extremos) == 1:
            _id_conexion, _id_conector, _id_tipo_conector, nombre_tipo = extremos[0]
            if nombre_tipo == "OUT":
                lado = "B"
            elif nombre_tipo == "IN":
                lado = "A"

        if lado is None:
            dlg = _DialogoEligeLadoFantasma(self)
            resp = dlg.run()
            dlg.destroy()
            if resp == _DialogoEligeLadoFantasma.RESP_A:
                lado = "A"
            elif resp == _DialogoEligeLadoFantasma.RESP_B:
                lado = "B"
            else:
                return  # canceló

        tipo_conector_nombre = "OUT" if lado == "A" else "IN"

        id_tipo_equipo_fantasma = Modelo.devolver_id_tipo_equipo_fantasma()
        if not id_tipo_equipo_fantasma:
            mostrar_error(self, _(
                "No hay ningún tipo de equipo con rol FANTASMA en el "
                "catálogo. Marcá uno (Equipos → Tipos de equipo) antes "
                "de usar esta acción rápida."))
            return

        id_tipo_conector = Modelo.devolver_id_tipo_conector_por_nombre(
            tipo_conector_nombre)
        if not id_tipo_conector:
            mostrar_error(self, _(
                "No hay ningún tipo de conector llamado '{tipo}' en el "
                "catálogo.").format(tipo=tipo_conector_nombre))
            return

        codigo_cable = self.e_codigo.get_text().strip() or f"#{self.id_cable}"
        nombre_equipo = f"EXTREMO {lado} DESCONECTADO {codigo_cable}"

        id_equipo = Modelo.alta_equipo_retorna_id(
            id_tipo_equipo_fantasma, None, None, None, None, nombre_equipo,
            None, None, None)
        id_conector = Modelo.agregar_conector_retorna_id(
            tipo_conector_nombre, id_equipo, id_tipo_conector, None, None, None)
        Modelo.alta_conexion(self.id_cable, id_conector)

        mostrar_info(self, _(
            "Se creó el equipo '{nombre}' con su conector {tipo} ya "
            "conectado a este cable.\n\nA continuación se abren su ficha "
            "(para la ubicación en el plano) y su conector (para la foto "
            "de la ficha) — cancelá cualquiera de las dos si no las "
            "necesitás ahora.").format(nombre=nombre_equipo,
                                        tipo=tipo_conector_nombre))

        from cabledoc import _DialogoEquipo, _DialogoConector
        dlg_equipo = _DialogoEquipo(id_equipo=id_equipo, parent=self)
        dlg_equipo.run_and_destroy()

        dlg_conector = _DialogoConector(
            id_conector=id_conector, id_equipo=id_equipo, parent=self)
        dlg_conector.run_and_destroy()

        self._actualizar_estado_btn_fantasma()

    def _get_notas(self):
        buf = self.tv_notas.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip() or None

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_tipo_cable = _get_combo_id(self.c_tipo_cable)
            id_tipo_ficha = _get_combo_id(self.c_tipo_ficha)
            args = (
                self.e_codigo.get_text(),
                self.e_longitud.get_text(),
                id_tipo_cable or None,
                id_tipo_ficha or None,
                self.e_unidad.get_text(),
                self.e_met1.get_text(),
                self.e_met2.get_text(),
                self.e_unidad_met.get_text(),
                self.combo_estado.get_active_text() or "VERIFICADO",
                self._get_notas(),
            )
            if self.id_cable:
                Modelo.modificar_cable(self.id_cable, *args)
                if self.e_ancho_banda_override is not None:
                    Modelo.establecer_ancho_banda_override_cable(
                        self.id_cable, _parse_float_opt(self.e_ancho_banda_override.get_text()))
                if self.c_armado is not None:
                    id_arm = self.c_armado.get_active_id()
                    es_correcto = None if not id_arm else bool(int(id_arm))
                    detalle_arm = self.e_detalle_armado.get_text().strip() or None
                    Modelo.establecer_armado_cable(
                        self.id_cable, es_correcto, detalle_arm)
            else:
                Modelo.agregar_cable(*args)
        self.destroy()


# ─── Conexiones ───────────────────────────────────────────────────────────────

class ConexionesListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False, id_cable=None):
        self.id_cable_filtro = id_cable
        super().__init__(
            _("Conexiones"),
            [_("ID"), _("Equipo"), _("Conector"), _("Tipo Conector"),
             _("Tipo Equipo"), _("Cable")],
            parent=parent, modo_seleccion=modo_seleccion
        )
        self.cargar_datos()

    def cargar_datos(self):
        rows = Modelo.devolver_todas_las_conexiones(self.id_cable_filtro)
        # Reordenar columnas para el display:
        # BD: id, equipo, conector, cable, tipo_conector, tipo_equipo, ...
        # Display: ID, Equipo, Conector, TipoConector, TipoEquipo, Cable
        data = []
        for r in rows:
            (id_conexion, equipo_nombre, conector_nombre, cable_codigo,
             tipo_conector, tipo_equipo, _id_cable, id_conector,
             _id_equipo) = r[:9]
            if id_conector is None:
                # Extremo suelto (plan_desarrollo_extension_cable.md): no
                # termina en un conector de equipo — se empalma con otro
                # cable a través de una Extensión. CONEXIONES trae estas
                # columnas en blanco porque hace LEFT JOIN contra
                # conector→equipo; se completa acá en el display, sin
                # tocar esa vista (la comparten otros consumidores, ver
                # PROGRESS.md).
                id_ext = Modelo.devolver_extension_de_conexion(id_conexion)
                equipo_nombre = (
                    _("(extremo suelto — Extensión #{})").format(id_ext)
                    if id_ext else
                    _("(extremo suelto — sin extensión asociada)"))
                ficha = Modelo.devolver_ficha_de_conexion(id_conexion)
                conector_nombre = ficha or _("(ficha sin especificar)")
                tipo_conector = "—"
                tipo_equipo = "—"
            data.append([id_conexion, equipo_nombre, conector_nombre,
                        tipo_conector, tipo_equipo, cable_codigo])
        self._poblar(data)

    def nuevo(self):
        dlg = _DialogoConexion(parent=self, id_cable_predef=self.id_cable_filtro)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConexion(id_conexion=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conexion(id_)


class _DialogoConexion(Gtk.Dialog):
    def __init__(self, id_conexion=None, parent=None, id_cable_predef=None):
        titulo = _("Editar Conexión") if id_conexion else _("Nueva Conexión")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 240)
        self.id_conexion = id_conexion
        self.id_cable = id_cable_predef or ""
        self.id_conector = ""
        self.id_equipo = ""

        g = _grid()
        _lbl_entry(g, _("Equipo:"), 0)
        self.e_equipo = _entry_btn(g, 0, "…", self._sel_equipo)
        _lbl_entry(g, _("Conector:"), 1)
        self.c_conector = _searchable_combo(g, 1, [])
        _lbl_entry(g, _("Cable:"), 2)
        self.e_cable = _entry_btn(g, 2, "…", self._sel_cable)

        # Ficha propia del cable en esta punta (plan_riesgo_senal_audio.md)
        # — distinto de la ficha que declara el jack del equipo. Sólo
        # tiene sentido con la conexión ya guardada.
        self.c_ficha_cable = None
        if id_conexion:
            _lbl_entry(g, _("Ficha del cable en esta punta:"), 3)
            self.c_ficha_cable = _searchable_combo(
                g, 3, Modelo.devolver_todos_los_tipos_ficha())
            self.c_ficha_cable.set_tooltip_text(
                _("Qué ficha es físicamente el extremo del cable que llega "
                  "acá (ej. XLR3 macho, TS) — puede ser distinta de la "
                  "ficha que espera el jack del equipo. Usado por el "
                  "análisis de riesgo de señal para detectar cortocircuito "
                  "por conductores insuficientes."))

        self.get_content_area().add(g)

        # ── Armado POR EXTREMO (plan_bitacora_incidentes_riesgo_analogico.md
        # §3.3, extendido en sesión posterior) — a diferencia de "Armado" en
        # _DialogoCable (todo el cable), esto es sólo la punta que llega a
        # esta conexión puntual. Caso real que lo motivó: un cable con XLR3
        # bien armado de un lado y TRS mal armado (cruce de conductores) del
        # otro — "Armado" a nivel cable no puede distinguir cuál extremo es.
        # Sólo tiene sentido con la conexión ya guardada.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_conexion:
            Modelo.asegurar_tablas_bitacora()
            frame_armado = Gtk.Frame(label=" " + _("Armado de esta punta") + " ")
            g5 = _grid()
            _lbl_entry(g5, _("¿Armado correcto?:"), 0)
            self.c_armado = Gtk.ComboBoxText()
            self.c_armado.append("", _("No verificado"))
            self.c_armado.append("1", _("Correcto"))
            self.c_armado.append("0", _("Mal armado"))
            g5.attach(self.c_armado, 1, 0, 2, 1)
            _lbl_entry(g5, _("Detalle:"), 1)
            self.e_detalle_armado = _entry(g5, 1)
            self.e_detalle_armado.set_placeholder_text(
                _("ej. \"cruce de conductores, pin 2 y 3 al mismo orificio\""))
            frame_armado.add(g5)
            self.get_content_area().pack_start(frame_armado, False, False, 6)

        if id_conexion:
            rows = Modelo.devolver_conexion(id_conexion)
            if rows:
                r = rows[0]
                self.id_equipo = s(r[8])
                self.e_equipo.set_text(s(r[1]))
                # Cargar conectores del equipo para el combo
                _repopulate_combo(self.c_conector, Modelo.devolver_conectores_de_equipo(self.id_equipo))
                _set_combo_id(self.c_conector, s(r[7]))
                self.e_cable.set_text(s(r[3]))
                self.id_cable = s(r[6])
                if self.c_ficha_cable is not None:
                    id_tf_actual = Modelo.devolver_ficha_conexion(id_conexion)
                    if id_tf_actual:
                        _set_combo_id(self.c_ficha_cable, id_tf_actual)
                if self.c_armado is not None:
                    es_correcto, detalle = Modelo.devolver_armado_conexion(id_conexion)
                    self.c_armado.set_active_id(
                        str(int(es_correcto)) if es_correcto is not None else "")
                    if detalle:
                        self.e_detalle_armado.set_text(s(detalle))
        elif id_cable_predef:
            # Cargar nombre del cable predefinido
            c_rows = Modelo.devolver_cable(id_cable_predef)
            if c_rows:
                self.e_cable.set_text(s(c_rows[0][1])) # index 1 es codigo

        # plan_simular_remocion_cadena.md — sólo tiene sentido con la
        # conexión ya guardada (necesita id_conexion para resolver el
        # cable en graph_impact.py).
        if id_conexion:
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se desconecta "
                "esta punta (equivale a cortar el cable entero: el grafo "
                "de señal no modela extremos sueltos). No destructivo."))
            btn_remocion.connect("clicked", self._simular_remocion)
            self.get_content_area().pack_start(btn_remocion, False, False, 4)

        _pack_ultima_edicion(self, "conexion", "id_conexion", id_conexion)
        self.show_all()

    def _simular_remocion(self, btn):
        from impacto_ui import simular_remocion_y_mostrar
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — Conexión #{self.id_conexion}",
            "simular_perdida_conexion", self.id_conexion)

    def _sel_equipo(self, btn):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.e_equipo.set_text(dlg.resultado_nombre)
            # Re-poblar combo de conectores
            _repopulate_combo(self.c_conector, Modelo.devolver_conectores_de_equipo(self.id_equipo))
            self.c_conector.get_child().set_text("")
        dlg.destroy()

    def _sel_cable(self, btn):
        dlg = CablesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_cable = dlg.resultado_id
            self.e_cable.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            id_conector = _get_combo_id(self.c_conector)
            if self.id_conexion:
                Modelo.modificacion_conexion(
                    self.id_conexion,
                    self.id_cable or None,
                    id_conector or None, 0
                )
                if self.c_ficha_cable is not None:
                    Modelo.establecer_ficha_conexion(
                        self.id_conexion, _get_combo_id(self.c_ficha_cable) or None)
                if self.c_armado is not None:
                    id_activo = self.c_armado.get_active_id()
                    es_correcto = None if not id_activo else bool(int(id_activo))
                    detalle_arm = self.e_detalle_armado.get_text().strip() or None
                    Modelo.establecer_armado_conexion(self.id_conexion, es_correcto, detalle_arm)
            else:
                Modelo.alta_conexion(
                    self.id_cable or None,
                    id_conector or None, 0
                )
        self.destroy()

