#!/usr/bin/env python3
"""
conectores_ui.py — CableDoc GTK3

Dominio Conectores, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 4).

Contiene:
  - ConectoresListado (listado de conectores de un equipo)
  - _DialogoConector (ficha completa de conector)
  - _DialogoRenombrarConectores (renombrado masivo de conectores de un
    equipo real)

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos tres nombres sin cambios.

Referencias a clases de otros dominios que todavía viven en `cabledoc.py`
(ImagenesListado, _DialogoSenal) se resuelven con import diferido dentro
del método que las usa, siguiendo el mismo patrón que ya usa el proyecto
para evitar ciclos.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk

from modelo import Modelo

try:
    from i18n import _
except ImportError:
    def _(t): return t

from pantallas_avanzadas import abrir_coords_imagen

from pantallas_comunes import (
    s,
    VentanaListado,
    DialogoNombre,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _repopulate_combo,
    _pack_ultima_edicion,
)


# ─── Conectores ───────────────────────────────────────────────────────────────

class ConectoresListado(VentanaListado):
    def __init__(self, id_equipo, parent=None, modo_seleccion=False):
        super().__init__(_("Conectores"), [_("ID"), _("Nombre"), _("Tipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.id_equipo = id_equipo
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_conectores_de_equipo(self.id_equipo))

    def nuevo(self):
        dlg = _DialogoConector(id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoConector(id_conector=id_, id_equipo=self.id_equipo, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_conector(id_)


class _DialogoConector(Gtk.Dialog):
    def __init__(self, id_conector=None, id_equipo=None, parent=None):
        titulo = _("Editar Conector") if id_conector is not None else _("Nuevo Conector")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(420, 280)
        self.id_conector = id_conector
        self.id_equipo = id_equipo or ""
        self.id_tipo_conector = ""
        self.id_imagen = ""

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Tipo conector:"), 1)
        self.c_tipo = _searchable_combo(g, 1, Modelo.devolver_tipos_conectores())
        _lbl_entry(g, _("Imagen:"), 2)
        self.e_imagen = _entry_btn(g, 2, "…", self._sel_imagen)
        _lbl_entry(g, _("Coord X:"), 3)
        self.e_x = _entry(g, 3)
        _lbl_entry(g, _("Coord Y:"), 4)
        self.e_y = _entry(g, 4)

        self.get_content_area().add(g)

        # Botón selector de coordenadas en imagen
        btn_coords = Gtk.Button(label="📍 " + _("Elegir coords en imagen"))
        btn_coords.connect("clicked", self._sel_coordenadas)
        self.get_content_area().pack_start(btn_coords, False, False, 0)

        if id_conector is not None:
            rows = Modelo.devolver_conector(id_conector)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self.id_tipo_conector = s(r[3])
                _set_combo_id(self.c_tipo, self.id_tipo_conector)
                self.id_equipo = s(r[4])
                self.e_x.set_text(s(r[5]))
                self.e_y.set_text(s(r[6]))
                self.id_imagen = s(r[7])
                self.e_imagen.set_text(s(r[8]))

        # ── Señal (Fase 2 de plan_entidad_senal.md) ──
        # Sólo tiene sentido con el conector ya guardado (senal_en_conector
        # referencia id_conector). Un conector nuevo no la muestra todavía;
        # se asigna reabriendo la ficha una vez creado.
        self.c_senal = None
        self.c_formato = None
        if id_conector is not None:
            frame_senal = Gtk.Frame(label=" " + _("Señal") + " ")
            g2 = _grid()
            _lbl_entry(g2, _("Señal:"), 0)
            self.c_senal = _searchable_combo(
                g2, 0, Modelo.devolver_senales(), "+", self._agregar_senal_rapida)
            _lbl_entry(g2, _("Formato:"), 1)
            self.c_formato = _searchable_combo(
                g2, 1, Modelo.devolver_formatos_senal(), "+",
                self._agregar_formato_rapida)
            frame_senal.add(g2)
            self.get_content_area().pack_start(frame_senal, False, False, 6)

            btn_quitar_senal = Gtk.Button(
                label=_("🗑 Quitar señal de este conector"))
            btn_quitar_senal.connect("clicked", self._quitar_senal)
            self.get_content_area().pack_start(btn_quitar_senal, False, False, 0)

            actual = Modelo.devolver_senal_en_conector(id_conector)
            if actual:
                id_senal_act, _n_senal, id_formato_act, _n_formato, _origen = actual[0]
                _set_combo_id(self.c_senal, id_senal_act)
                if id_formato_act:
                    _set_combo_id(self.c_formato, id_formato_act)

        # ── Función de patchera (Fase B de plan_desarrollo_funcion_
        # patchera.md) ──
        # Hasta ahora esto SÓLO se podía cargar en el editor del molde de
        # catálogo (_DialogoConectorCatalogo) — un equipo real ya dado de
        # alta (ej. un patch module de audio con conectores "01_BACK"/
        # "25_BACK" que no siguen la convención A_BACK/B_BACK) no tenía
        # forma de asignarle la función sin editar la base a mano. Mismo
        # criterio que la sección de Señal: sólo tiene sentido con el
        # conector ya guardado, y sólo se muestra si el EQUIPO es de
        # rol_senal PATCHERA (no tiene sentido en cualquier otro tipo).
        self.c_funcion_patchera = None
        if id_conector is not None and self.id_equipo:
            fila_rol = Modelo._query(
                "SELECT te.rol_senal FROM equipo e "
                "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
                "WHERE e.id_equipo=?", (self.id_equipo,))
            es_patchera = bool(fila_rol and fila_rol[0][0] == "PATCHERA")
            if es_patchera:
                frame_pat = Gtk.Frame(label=" " + _("Función de patchera") + " ")
                g3 = _grid()
                _lbl_entry(g3, _("Función:"), 0)
                self.c_funcion_patchera = Gtk.ComboBoxText()
                self.c_funcion_patchera.append("", _("(ninguna)"))
                for f in Modelo.funciones_patchera():
                    self.c_funcion_patchera.append(f["id"], f["nombre_es"])
                g3.attach(self.c_funcion_patchera, 1, 0, 2, 1)
                frame_pat.add(g3)
                self.get_content_area().pack_start(frame_pat, False, False, 6)

                fila_fn = Modelo._query(
                    "SELECT id_funcion_patchera FROM conector WHERE id_conector=?",
                    (id_conector,))
                if fila_fn and fila_fn[0][0]:
                    self.c_funcion_patchera.set_active_id(s(fila_fn[0][0]))

        # ── Formato eléctrico (plan_riesgo_senal_audio.md, riesgo #3) ──
        # Mismo criterio que Señal/Función de patchera: sólo tiene sentido
        # con el conector ya guardado. id_tipo_ficha declara qué ficha es
        # eléctricamente este jack (de ahí sale el default de n_conductores/
        # modo_balance/modo_canal); modo_balance/modo_canal acá son el
        # OVERRIDE puntual (vacío = usar el default de la ficha) — necesario
        # para fichas ambiguas como TRS (sección 4.1 del plan).
        self.c_ficha_riesgo = None
        self.c_modo_balance = None
        self.c_modo_canal = None
        if id_conector is not None:
            frame_riesgo = Gtk.Frame(label=" " + _("Formato eléctrico (riesgo de señal)") + " ")
            g4 = _grid()
            _lbl_entry(g4, _("Ficha (qué es eléctricamente):"), 0)
            self.c_ficha_riesgo = _searchable_combo(
                g4, 0, Modelo.devolver_todos_los_tipos_ficha())
            _lbl_entry(g4, _("Balance (override):"), 1)
            self.c_modo_balance = Gtk.ComboBoxText()
            for m in ("", "BALANCEADO", "DESBALANCEADO", "NA"):
                self.c_modo_balance.append_text(m if m else _("(usar default de la ficha)"))
            g4.attach(self.c_modo_balance, 1, 1, 2, 1)
            _lbl_entry(g4, _("Canal (override):"), 2)
            self.c_modo_canal = Gtk.ComboBoxText()
            for m in ("", "MONO", "ESTEREO", "NA"):
                self.c_modo_canal.append_text(m if m else _("(usar default de la ficha)"))
            g4.attach(self.c_modo_canal, 1, 2, 2, 1)
            frame_riesgo.add(g4)
            self.get_content_area().pack_start(frame_riesgo, False, False, 6)

            formato_actual = Modelo.devolver_formato_conector(id_conector)
            if formato_actual:
                id_tf_act, mbal_act, mcan_act = formato_actual
                if id_tf_act:
                    _set_combo_id(self.c_ficha_riesgo, id_tf_act)
                self.c_modo_balance.set_active(
                    ("", "BALANCEADO", "DESBALANCEADO", "NA").index(mbal_act)
                    if mbal_act in ("BALANCEADO", "DESBALANCEADO", "NA") else 0)
                self.c_modo_canal.set_active(
                    ("", "MONO", "ESTEREO", "NA").index(mcan_act)
                    if mcan_act in ("MONO", "ESTEREO", "NA") else 0)
            else:
                self.c_modo_balance.set_active(0)
                self.c_modo_canal.set_active(0)

        # ── Armado (plan_bitacora_incidentes_riesgo_analogico.md §3.3) ──
        # Independiente del "Formato eléctrico" de arriba: un conector puede
        # ser balanceado por diseño (ej. XLR) y estar igual mal soldado —
        # es la distinción que motivó el caso real del jack TS cableado
        # como si fuera XLR balanceado.
        self.c_armado = None
        self.e_detalle_armado = None
        if id_conector is not None:
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
            self.get_content_area().pack_start(frame_armado, False, False, 6)

            filas_arm = Modelo._query(
                "SELECT es_armado_correcto, detalle_armado FROM conector "
                "WHERE id_conector=?", (id_conector,))
            if filas_arm and filas_arm[0][0] is not None:
                self.c_armado.set_active_id(str(int(filas_arm[0][0])))
            else:
                self.c_armado.set_active_id("")
            if filas_arm and filas_arm[0][1]:
                self.e_detalle_armado.set_text(s(filas_arm[0][1]))

        _pack_ultima_edicion(self, "conector", "id_conector", id_conector)
        self.show_all()

    def _sel_imagen(self, btn):
        from cabledoc import ImagenesListado
        dlg = ImagenesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_imagen = dlg.resultado_id
            self.e_imagen.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _agregar_senal_rapida(self, btn):
        """Botón '+' junto al combo de señal: alta rápida sin salir de la
        ficha del conector."""
        from cabledoc import _DialogoSenal
        dlg = _DialogoSenal(_("Nueva Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.nombre:
            id_nuevo = Modelo.agregar_senal(
                dlg.nombre, dlg.tipo_contenido, dlg.descripcion)
            _repopulate_combo(self.c_senal, Modelo.devolver_senales())
            _set_combo_id(self.c_senal, id_nuevo)
        dlg.destroy()

    def _agregar_formato_rapida(self, btn):
        dlg = DialogoNombre(_("Nuevo Formato de Señal"), parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            id_nuevo = Modelo.agregar_tipo_formato_senal(dlg.valor)
            _repopulate_combo(self.c_formato, Modelo.devolver_formatos_senal())
            _set_combo_id(self.c_formato, id_nuevo)
        dlg.destroy()

    def _quitar_senal(self, btn):
        if self.id_conector is not None:
            Modelo.quitar_senal_en_conector(self.id_conector)
        if self.c_senal is not None:
            self.c_senal.set_active(-1)
            self.c_senal.get_child().set_text("")
        if self.c_formato is not None:
            self.c_formato.set_active(-1)
            self.c_formato.get_child().set_text("")

    def _sel_coordenadas(self, btn):
        id_img = self.id_imagen if self.id_imagen else None
        res = abrir_coords_imagen(
            id_imagen=id_img, solo_xy=True,
            x=self.e_x.get_text(), y=self.e_y.get_text(),
            parent=self,
        )
        if res:
            self.e_x.set_text(res["x"])
            self.e_y.set_text(res["y"])

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text().strip()
            self.id_tipo_conector = _get_combo_id(self.c_tipo)
            x = self.e_x.get_text().strip()
            y = self.e_y.get_text().strip()
            if self.id_conector is not None:
                Modelo.modificacion_conector(
                    self.id_conector, nombre, self.id_equipo,
                    self.id_tipo_conector or None,
                    self.id_imagen or None, x, y
                )
            else:
                Modelo.agregar_conector(
                    nombre, self.id_equipo,
                    self.id_tipo_conector or None,
                    self.id_imagen or None, x, y
                )

            # Señal: sólo aplica si el conector ya existía al abrir la
            # ficha (self.c_senal es None en un conector recién creado
            # en este mismo Aceptar — ver comentario en __init__).
            if self.id_conector is not None and self.c_senal is not None:
                id_senal_sel = _get_combo_id(self.c_senal)
                if id_senal_sel:
                    id_formato_sel = _get_combo_id(self.c_formato) or None
                    Modelo.establecer_senal_en_conector(
                        self.id_conector, id_senal_sel, id_formato_sel)
                else:
                    # combo vacío = el usuario borró la selección a mano
                    # (además del botón "Quitar", que ya escribe en el
                    # momento); nos aseguramos de que quede consistente.
                    Modelo.quitar_senal_en_conector(self.id_conector)

            # Función de patchera: mismo criterio que Señal arriba — sólo
            # aplica si el combo llegó a mostrarse (conector existente +
            # equipo PATCHERA, ver __init__).
            if self.id_conector is not None and self.c_funcion_patchera is not None:
                id_funcion_sel = self.c_funcion_patchera.get_active_id() or None
                Modelo.establecer_funcion_patchera_conector(
                    self.id_conector, id_funcion_sel)

            # Formato eléctrico (plan_riesgo_senal_audio.md)
            if self.id_conector is not None and self.c_ficha_riesgo is not None:
                id_tf_sel = _get_combo_id(self.c_ficha_riesgo) or None
                idx_bal = self.c_modo_balance.get_active()
                idx_can = self.c_modo_canal.get_active()
                modo_bal_sel = ("", "BALANCEADO", "DESBALANCEADO", "NA")[idx_bal] or None
                modo_can_sel = ("", "MONO", "ESTEREO", "NA")[idx_can] or None
                Modelo.establecer_formato_conector(
                    self.id_conector, id_tf_sel, modo_bal_sel, modo_can_sel)

            # Armado (plan_bitacora_incidentes_riesgo_analogico.md)
            if self.id_conector is not None and self.c_armado is not None:
                id_arm = self.c_armado.get_active_id()
                es_correcto = None if not id_arm else bool(int(id_arm))
                detalle_arm = self.e_detalle_armado.get_text().strip() or None
                Modelo.establecer_armado_conector(
                    self.id_conector, es_correcto, detalle_arm)
        self.destroy()


class _DialogoRenombrarConectores(Gtk.Dialog):
    def __init__(self, id_equipo, parent=None):
        super().__init__(
            title=_("Renombrar Conectores"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(600, 500)
        self.id_equipo = id_equipo
        
        # Contenedor principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.get_content_area().add(vbox)
        
        # Obtener conectores del equipo
        conectores = Modelo.devolver_conectores_de_equipo(id_equipo)
        
        # Crear grid para los conectores
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(4)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        
        # Crear lista para guardar los entries
        self.entries = []
        
        for i, (id_conector, nombre, tipo) in enumerate(conectores):
            # Label con el nombre actual
            lbl = Gtk.Label(label=nombre)
            lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1)
            
            # Entry para el nuevo nombre
            entry = Gtk.Entry()
            entry.set_text(nombre)
            entry.set_hexpand(True)
            grid.attach(entry, 1, i, 1, 1)
            
            # Guardar referencia al entry junto con el id_conector y nombre original
            self.entries.append({
                'id': id_conector,
                'original': nombre,
                'entry': entry
            })
        
        # ScrolledWindow para el grid
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        sw.add(grid)
        vbox.pack_start(sw, True, True, 0)
        
        self.show_all()
    
    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            # Guardar los cambios
            for item in self.entries:
                nuevo_nombre = item['entry'].get_text().strip()
                # Si está en blanco, mantener el nombre original
                if not nuevo_nombre:
                    nuevo_nombre = item['original']
                # Solo actualizar si el nombre cambió
                if nuevo_nombre != item['original']:
                    # Obtener los otros datos del conector para no perderlos
                    rows = Modelo.devolver_conector(item['id'])
                    if rows:
                        r = rows[0]
                        Modelo.modificacion_conector(
                            item['id'],
                            nuevo_nombre,
                            s(r[4]),  # id_equipo
                            s(r[3]),  # id_tipo_conector
                            s(r[7]),  # id_imagen
                            s(r[5]),  # x
                            s(r[6])   # y
                        )
        self.destroy()

