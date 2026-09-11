#!/usr/bin/env python3
"""
racks_salas_ui.py — CableDoc GTK3

Dominio Racks / Salas, extraído de `cabledoc.py`
(ver plan_refactor_cabledoc.md, Entrega 7, parte 1/2).

Contiene:
  - RacksListado, _DialogoRack
  - PosicionEnRackListado, _DialogoPosicionRack
  - SalasListado, _DialogoSala
  - _DialogoRackPorSala, RackPorSalaListado
  - _DialogoEquipoNoRackSala, EquiposNoRackSalaListado

_DialogoSala es nuevo (Fase 4 de plan_desarrollo_ubicacion_fisica_planos.md,
"Overlay de salas en el plano"): reemplaza el uso del genérico DialogoNombre
para editar Sala, agregando el selector de Plano (sala.id_plano) y el
acceso a VistaPlanoInteractivo (planos_ui.py) para dibujar el contorno
(sala.poligono). Ver el docstring de la clase para el detalle.

_DialogoRackPorSala gana en esta misma línea de trabajo (Fase 5,
"Overlay de racks (puntos)") un botón "📍 Ubicar en el plano" que abre
VistaPlanoInteractivo enfocado en el rack de esta asignación — ver el
docstring de la clase. De paso se corrigió un bug preexistente en esa
misma clase (le faltaba `run_and_destroy`, no relacionado con la Fase 5
salvo que se notó al ejercitar el diálogo bajo GTK real para validar el
botón nuevo).

Es un *move* 1:1 desde cabledoc.py: no cambia comportamiento ni lógica de
negocio. `cabledoc.py` reexporta estos nueve nombres sin cambios.

Separado de `frames_slots_ui.py` (catálogo e instancia de frames/slots)
porque juntos superaban las ~900 líneas objetivo del plan (~1.275 líneas
→ 2 archivos), mismo criterio de tamaño usado en las Entregas 3 y 5. Los
dos bloques no eran contiguos en el original: entre "Posición en Rack" y
"Salas" queda el bloque de Frames/Slots (que se extrae en el otro archivo
de esta misma entrega) y `ConexionesDeEquipoVentana` (que permanece en
`cabledoc.py`, no forma parte de ningún dominio de esta entrega).

Referencias a clases de otros dominios que todavía viven en `cabledoc.py`
(EquiposListado) o que se extraen en el archivo hermano de esta misma
entrega (FramesListado, en `frames_slots_ui.py`) se resuelven con import
diferido dentro del método que las usa, siguiendo el mismo patrón que ya
usa el proyecto para evitar ciclos — incluyendo el patrón ya establecido
de rutear siempre a través de `from cabledoc import X` (nunca importar
directo del módulo de dominio hermano), como ya hace
`cables_conexiones_ui.py` con `EquiposListado`.
"""

import json

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.modelo import Modelo, DB_PATH

try:
    from core.i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    VentanaListado,
    _grid,
    _lbl_entry,
    _entry,
    _entry_btn,
    _pack_ultima_edicion,
)
from pantallas_avanzadas import abrir_vista_rack


# ─── Racks ────────────────────────────────────────────────────────────────────

class RacksListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Racks"), [_("ID"), _("Número"), _("Nombre"), _("Capacidad (UR)")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def _on_seleccionar(self, btn):
        f = self._fila()
        if f:
            self.resultado_id = f[0]
            self.resultado_nombre = f[2]  # nombre en columna 2
            self.response(Gtk.ResponseType.OK)

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_los_racks())

    def nuevo(self):
        dlg = _DialogoRack(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoRack(id_rack=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_rack(id_)


class _DialogoRack(Gtk.Dialog):
    def __init__(self, id_rack=None, parent=None):
        titulo = _("Editar Rack") if id_rack else _("Nuevo Rack")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(380, 220)
        self.id_rack = id_rack

        g = _grid()
        _lbl_entry(g, _("Número:"), 0); self.e_numero = _entry(g, 0)
        _lbl_entry(g, _("Nombre:"), 1); self.e_nombre = _entry(g, 1)
        _lbl_entry(g, _("Capacidad (UR):"), 2); self.e_cap = _entry(g, 2)
        self.get_content_area().add(g)

        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                r = rows[0]
                self.e_numero.set_text(s(r[1]))
                self.e_nombre.set_text(s(r[2]))
                self.e_cap.set_text(s(r[3]))

        # Botón de dispositivos en rack
        if id_rack:
            btn = Gtk.Button(label=_("📦 Dispositivos en este rack"))
            btn.connect("clicked", self._ver_dispositivos)
            self.get_content_area().pack_start(btn, False, False, 0)
            btn_vista = Gtk.Button(label=_("🖼 Vista gráfica del rack"))
            btn_vista.connect("clicked", self._ver_vista_rack)
            self.get_content_area().pack_start(btn_vista, False, False, 0)

            # plan_simular_remocion_cadena.md — corte de energía del rack
            btn_remocion = Gtk.Button(label="⚡ " + _("Simular remoción"))
            btn_remocion.set_tooltip_text(_(
                "Qué equipos y cables quedan sin señal si se corta la "
                "energía de todo el rack (equipos directos + equipos "
                "dentro de sus frames). No destructivo."))
            btn_remocion.connect("clicked", self._simular_remocion)
            self.get_content_area().pack_start(btn_remocion, False, False, 0)

        _pack_ultima_edicion(self, "rack", "id_rack", id_rack)
        self.show_all()

    def _ver_dispositivos(self, btn):
        dlg = PosicionEnRackListado(id_rack=self.id_rack, parent=self)
        dlg.run(); dlg.destroy()

    def _ver_vista_rack(self, btn):
        abrir_vista_rack(id_rack=self.id_rack, parent=self)

    def _simular_remocion(self, btn):
        from impacto_ui import simular_remocion_y_mostrar
        nombre = self.e_nombre.get_text().strip() or f"Rack {self.id_rack}"
        simular_remocion_y_mostrar(
            self, DB_PATH, f"⚡ {_('Simular remoción')} — {nombre}",
            "simular_perdida_rack", self.id_rack)

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            if self.id_rack:
                Modelo.modificacion_rack(
                    self.id_rack,
                    self.e_numero.get_text(),
                    self.e_nombre.get_text(),
                    self.e_cap.get_text()
                )
            else:
                Modelo.alta_rack(
                    self.e_numero.get_text(),
                    self.e_nombre.get_text(),
                    self.e_cap.get_text()
                )
        self.destroy()


# ─── Posición en Rack ─────────────────────────────────────────────────────────

class PosicionEnRackListado(VentanaListado):
    def __init__(self, id_rack=None, parent=None, modo_seleccion=False):
        super().__init__(
            "Posición en Rack",
            ["ID", "Rack", "Orificio", "Inventario", "Dispositivo", "UR"],
            parent=parent, modo_seleccion=modo_seleccion
        )
        self.id_rack = id_rack
        self.cargar_datos()

    def cargar_datos(self):
        if self.id_rack:
            rows = Modelo.devolver_dispositivos_de_un_rack(self.id_rack)
        else:
            rows = Modelo.devolver_todos_dispositivos_en_racks()
        self._poblar(rows)

    def nuevo(self):
        dlg = _DialogoPosicionRack(id_rack=self.id_rack, parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoPosicionRack(id_posicion=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_dispositivo_en_rack(id_)


class _DialogoPosicionRack(Gtk.Dialog):
    def __init__(self, id_posicion=None, id_rack=None, parent=None):
        titulo = _("Editar Posición en Rack") if id_posicion else _("Nueva Posición en Rack")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True,
                               destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 320)
        self.id_posicion = id_posicion
        self.id_rack = id_rack or ""
        self.id_equipo = ""
        self.id_frame = ""

        g = _grid()
        _lbl_entry(g, _("Rack:"), 0)
        self.e_rack = _entry_btn(g, 0, "…", self._sel_rack,
                                 readonly=bool(id_rack))
        _lbl_entry(g, _("Orificio:"), 1)
        self.e_orificio = _entry(g, 1)
        _lbl_entry(g, _("UR (unidades):"), 2)
        self.e_ur = _entry(g, 2)

        # Radio buttons equipo vs frame
        hb = Gtk.Box(spacing=8)
        self.rb_equipo = Gtk.RadioButton.new_with_label_from_widget(None, _("Equipo"))
        self.rb_frame = Gtk.RadioButton.new_with_label_from_widget(
            self.rb_equipo, _("Frame"))
        hb.pack_start(self.rb_equipo, False, False, 0)
        hb.pack_start(self.rb_frame, False, False, 0)
        g.attach(Gtk.Label(label=_("Tipo dispositivo:"), xalign=1), 0, 3, 1, 1)
        g.attach(hb, 1, 3, 2, 1)

        _lbl_entry(g, _("Equipo:"), 4)
        self.e_equipo = _entry_btn(g, 4, "…", self._sel_equipo)
        _lbl_entry(g, _("Frame:"), 5)
        self.e_frame = _entry_btn(g, 5, "…", self._sel_frame)
        self.get_content_area().add(g)

        # Prellenar rack si viene dado
        if id_rack:
            rows = Modelo.devolver_rack(id_rack)
            if rows:
                self.e_rack.set_text(s(rows[0][2]))
                self.e_rack.set_editable(False)

        if id_posicion:
            rows = Modelo.devolver_dispositivo_en_rack(id_posicion)
            if rows:
                r = rows[0]
                # id, rack, orificio, inventario, dispositivo, UR, id_rack, id_equipo, id_frame
                self.e_rack.set_text(s(r[1]))
                self.e_orificio.set_text(s(r[2]))
                self.e_ur.set_text(s(r[5]))
                self.id_rack = s(r[6])
                self.id_equipo = s(r[7])
                self.id_frame = s(r[8])
                if self.id_equipo:
                    self.e_equipo.set_text(s(r[4]))
                    self.rb_equipo.set_active(True)
                else:
                    self.e_frame.set_text(s(r[4]))
                    self.rb_frame.set_active(True)

        _pack_ultima_edicion(self, "posicion_en_rack", "id_posicion_en_rack", id_posicion)
        self.show_all()

    def _sel_rack(self, btn):
        dlg = RacksListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_rack = dlg.resultado_id
            self.e_rack.set_text(dlg.resultado_nombre)
        dlg.destroy()

    def _sel_equipo(self, btn):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_equipo = dlg.resultado_id
            self.id_frame = ""
            self.e_equipo.set_text(dlg.resultado_nombre)
            self.e_frame.set_text("")
            self.rb_equipo.set_active(True)
        dlg.destroy()

    def _sel_frame(self, btn):
        from cabledoc import FramesListado
        dlg = FramesListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self.id_frame = dlg.resultado_id
            self.id_equipo = ""
            self.e_frame.set_text(dlg.resultado_nombre)
            self.e_equipo.set_text("")
            self.rb_frame.set_active(True)
        dlg.destroy()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            equipo = self.id_equipo or None
            frame = self.id_frame or None
            args = (
                self.id_rack or None,
                equipo, self.e_orificio.get_text(),
                self.e_ur.get_text(), frame
            )
            if self.id_posicion:
                Modelo.modificacion_dispositivo_en_rack(self.id_posicion, *args)
            else:
                Modelo.alta_dispositivo_en_rack(*args)
        self.destroy()


# ─── Salas ────────────────────────────────────────────────────────────────────

class SalasListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Salas"), [_("ID"), _("Nombre")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_salas())

    def nuevo(self):
        dlg = _DialogoSala(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoSala(id_sala=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_sala(id_)


class _DialogoSala(Gtk.Dialog):
    """plan_desarrollo_ubicacion_fisica_planos.md, Fase 4: hasta esta fase
    Sala sólo tenía "nombre" y se editaba con el genérico DialogoNombre
    (pantallas_comunes.py). Se reemplaza acá por un diálogo propio que
    agrega el selector de Plano (sala.id_plano) y acceso al contorno
    (sala.poligono).

    El contorno en sí NO se edita con texto en este diálogo: se dibuja a
    mano sobre la imagen del plano en VistaPlanoInteractivo
    (planos_ui.py), reutilizando el modo_poligono de
    CoordenadasImagenSeleccion agregado en la Fase 3
    (imagen_conectores_ui.py). Acá sólo se ofrece el botón de acceso y se
    muestra el estado actual ("sin definir" / "N vértices").

    Referencia cruzada a PlanosListado (planos_ui.py) y VistaPlanoInteractivo
    resuelta con import diferido dentro de los métodos que las usan,
    ruteando a través de `from cabledoc import X` para PlanosListado (mismo
    patrón ya establecido por el resto del archivo) — VistaPlanoInteractivo
    se importa directo de planos_ui porque cabledoc.py no la reexporta
    todavía (no hace falta: sólo se usa acá y desde planos_ui.py mismo)."""

    def __init__(self, id_sala=None, parent=None):
        titulo = _("Editar Sala") if id_sala else _("Nueva Sala")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)
        self.set_default_size(460, 260)
        self.id_sala = id_sala
        self._id_plano = None    # str o None
        self._poligono = None    # JSON string (tal cual en sala.poligono) o None

        g = _grid()
        _lbl_entry(g, _("Nombre:"), 0)
        self.e_nombre = _entry(g, 0)
        _lbl_entry(g, _("Plano:"), 1)
        self.e_plano = _entry_btn(g, 1, "…", self._sel_plano)
        self.get_content_area().add(g)

        self.lbl_contorno = Gtk.Label(xalign=0)
        self.lbl_contorno.set_margin_start(8)
        self.lbl_contorno.set_margin_top(4)
        self.get_content_area().pack_start(self.lbl_contorno, False, False, 0)

        self.btn_contorno = Gtk.Button(
            label="🗺 " + _("Editar contorno en el plano"))
        self.btn_contorno.set_margin_start(8)
        self.btn_contorno.set_margin_top(4)
        self.btn_contorno.connect("clicked", self._editar_contorno)
        self.get_content_area().pack_start(self.btn_contorno, False, False, 0)

        if id_sala:
            rows = Modelo.devolver_sala(id_sala)
            if rows:
                r = rows[0]
                self.e_nombre.set_text(s(r[1]))
                self._id_plano = s(r[2]) or None
                self._poligono = r[3]
                if self._id_plano:
                    filas_plano = Modelo.devolver_plano(int(self._id_plano))
                    if filas_plano:
                        self.e_plano.set_text(s(filas_plano[0][1]))

        _pack_ultima_edicion(self, "sala", "id_sala", id_sala)
        self._actualizar_estado_contorno()
        self.show_all()

    def _sel_plano(self, btn):
        from cabledoc import PlanosListado
        dlg = PlanosListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            nuevo_id_plano = str(dlg.resultado_id)
            if nuevo_id_plano != self._id_plano:
                # el contorno está dibujado sobre la imagen del plano
                # anterior — no tiene sentido conservarlo al cambiar de
                # plano, mismo criterio que plan_desarrollo_ubicacion_
                # fisica_planos.md §3.2 aplica al reemplazar la imagen.
                self._poligono = None
            self._id_plano = nuevo_id_plano
            self.e_plano.set_text(dlg.resultado_nombre)
            self._actualizar_estado_contorno()
        dlg.destroy()

    def _actualizar_estado_contorno(self):
        habilitar = bool(self.id_sala and self._id_plano)
        self.btn_contorno.set_sensitive(habilitar)
        if not self._id_plano:
            texto = _("Asigná un plano para poder dibujar el contorno de "
                      "esta sala.")
        elif not self.id_sala:
            texto = _("Guardá la sala primero; el contorno se dibuja al "
                      "volver a editarla.")
        else:
            try:
                n = len(json.loads(self._poligono)) if self._poligono else 0
            except (ValueError, TypeError):
                n = 0
            texto = (_("Contorno: {0} vértices").format(n) if n >= 3
                     else _("Contorno: sin definir"))
        self.lbl_contorno.set_markup("<small><i>" + texto + "</i></small>")

    def _editar_contorno(self, btn):
        from planos_ui import VistaPlanoInteractivo
        VistaPlanoInteractivo(int(self._id_plano), parent=self,
                             id_sala_foco=self.id_sala).run_and_destroy()
        # releer el contorno recién guardado (o no) para refrescar la
        # etiqueta sin esperar a reabrir todo el diálogo de Sala
        rows = Modelo.devolver_sala(self.id_sala)
        if rows:
            self._poligono = rows[0][3]
        self._actualizar_estado_contorno()

    def run_and_destroy(self):
        if self.run() == Gtk.ResponseType.OK:
            nombre = self.e_nombre.get_text()
            if self.id_sala:
                Modelo.modificacion_sala(self.id_sala, nombre)
                Modelo.actualizar_ubicacion_sala(
                    self.id_sala,
                    int(self._id_plano) if self._id_plano else None,
                    self._poligono)
            else:
                nuevo_id = Modelo.alta_sala_retorna_id(nombre)
                if self._id_plano:
                    Modelo.actualizar_ubicacion_sala(
                        nuevo_id, int(self._id_plano), None)
        self.destroy()


# ─── Rack por Sala ────────────────────────────────────────────────────────────

class _DialogoRackPorSala(Gtk.Dialog):
    """Diálogo para asignar un rack a una sala.

    Botón "📍 Ubicar en el plano" (Fase 5 de
    plan_desarrollo_ubicacion_fisica_planos.md, "Overlay de racks
    (puntos)"): abre VistaPlanoInteractivo (planos_ui.py) enfocado en
    este rack para marcar/mover su punto sobre el plano de la sala.
    Sólo tiene sentido — y sólo se habilita — cuando:
      1. esta asignación YA está guardada (self.id_, no una asignación
         nueva sin guardar todavía: el punto vive en la fila de
         rack_por_sala, no puede haber punto sin fila); y
      2. la sala de esta asignación ya tiene un plano asignado
         (sala.id_plano, ver _DialogoSala en este mismo archivo).
    Referencia cruzada a VistaPlanoInteractivo resuelta con import
    diferido dentro del método que la usa, mismo patrón ya establecido
    por _DialogoSala._editar_contorno en esta clase hermana."""

    def __init__(self, id_=None, parent=None):
        titulo = _("Editar asignación Rack-Sala") if id_ else _("Nueva asignación Rack-Sala")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(360, -1)
        self.id_ = id_
        self._id_plano_de_sala = None

        ca = self.get_content_area()
        g = _grid()
        ca.pack_start(g, True, True, 0)

        _lbl_entry(g, _("Sala:"), 0)
        self.e_sala = _entry_btn(g, 0, "…", self._sel_sala)
        self._id_sala = None

        _lbl_entry(g, _("Rack:"), 1)
        self.e_rack = _entry_btn(g, 1, "…", self._sel_rack)
        self._id_rack = None

        self.lbl_ubicacion = Gtk.Label(xalign=0)
        self.lbl_ubicacion.set_margin_start(8)
        self.lbl_ubicacion.set_margin_top(4)
        ca.pack_start(self.lbl_ubicacion, False, False, 0)

        self.btn_ubicar = Gtk.Button(
            label="📍 " + _("Ubicar en el plano"))
        self.btn_ubicar.set_margin_start(8)
        self.btn_ubicar.set_margin_top(4)
        self.btn_ubicar.set_margin_bottom(4)
        self.btn_ubicar.connect("clicked", self._ubicar_en_plano)
        ca.pack_start(self.btn_ubicar, False, False, 0)

        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(_("Guardar"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        if id_:
            rows = Modelo.devolver_rack_por_sala(id_)
            if rows:
                self._id_sala = str(rows[0][1])
                self._id_rack = str(rows[0][2])
                self.e_sala.set_text(s(rows[0][3]))
                self.e_rack.set_text(s(rows[0][4]))
                self._id_plano_de_sala = rows[0][5]

        _pack_ultima_edicion(self, "rack_por_sala", "id_rack_x_sala", id_)
        self._actualizar_estado_ubicacion()
        self.show_all()

    def _sel_sala(self, btn):
        dlg = SalasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_sala = str(fila[0])
                self.e_sala.set_text(s(fila[1]))
        dlg.destroy()

    def _sel_rack(self, btn):
        dlg = RacksListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_rack = str(fila[0])
                self.e_rack.set_text(s(fila[2]))
        dlg.destroy()

    def _actualizar_estado_ubicacion(self):
        habilitar = bool(self.id_ and self._id_plano_de_sala)
        self.btn_ubicar.set_sensitive(habilitar)
        if not self.id_:
            texto = _("Guardá la asignación primero; la ubicación en el "
                      "plano se marca al volver a editarla.")
        elif not self._id_plano_de_sala:
            texto = _("La sala de esta asignación todavía no tiene un "
                      "plano asignado — asignaselo desde la ficha de "
                      "Sala.")
        else:
            texto = _("Marcá o mové el punto de este rack en el plano "
                      "de su sala con el botón de abajo.")
        self.lbl_ubicacion.set_markup("<small><i>" + texto + "</i></small>")

    def _ubicar_en_plano(self, btn):
        from planos_ui import VistaPlanoInteractivo
        VistaPlanoInteractivo(
            self._id_plano_de_sala, parent=self,
            id_rack_x_sala_foco=self.id_).run_and_destroy()

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            return
        if not self._id_sala or not self._id_rack:
            return
        if self.id_:
            Modelo.modificacion_rack_por_sala(self.id_, self._id_sala, self._id_rack)
        else:
            Modelo.alta_rack_por_sala(self._id_sala, self._id_rack)

    def run_and_destroy(self):
        # Faltaba en esta clase (bug preexistente, no introducido por la
        # Fase 5: RackPorSalaListado.nuevo()/editar() ya llamaban
        # dlg.run_and_destroy() desde antes de esta entrega, lo que
        # levantaba AttributeError al abrir "Nueva"/"Editar" asignación
        # Rack-Sala desde el menú — nunca se había notado porque no
        # tenía smoke test bajo GTK real hasta ahora). Mismo patrón que
        # el resto de los diálogos con guardado vía señal "response"
        # (self.run() bloquea y dispara _on_response en el clic; después
        # se cierra explícitamente).
        self.run()
        self.destroy()


class RackPorSalaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Rack por Sala"), [_("ID"), _("Sala"), _("Rack")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_rack_por_sala())

    def nuevo(self):
        dlg = _DialogoRackPorSala(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoRackPorSala(id_=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_rack_por_sala(id_)


class _DialogoEquipoNoRackSala(Gtk.Dialog):
    """Diálogo para asignar un equipo suelto a una sala.

    Fase 7 de plan_desarrollo_ubicacion_fisica_planos.md ("Equipos
    sueltos, módulos de frame y herencia de ubicación"), mismo criterio
    que _DialogoRackPorSala en la Fase 5:
      - selector "Tipo de montaje" (Piso/Pared), que sólo cambia el
        ícono con el que se dibuja el punto en el overlay del plano
        (VistaPlanoInteractivo._dibujar_overlay) — no hay geometría de
        pared propiamente dicha.
      - el selector de equipo excluye los marcados como
        `es_modulo_de_frame=1` (EquiposListado(excluir_modulos_de_frame=True)):
        un módulo de frame requiere estar instalado en un frame para
        tener ubicación física, no puede marcarse como equipo suelto
        (mismo criterio de exclusión que ya usa _DialogoMueble en la
        Fase 6, ver Modelo.devolver_ubicacion_fisica_de_equipo).
      - botón "📍 Ubicar en el plano", habilitado sólo si esta
        asignación ya está guardada y la sala ya tiene un plano.
    """

    def __init__(self, id_=None, parent=None):
        titulo = _("Editar equipo suelto en sala") if id_ else _("Nuevo equipo suelto en sala")
        super().__init__(title=titulo, transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(380, -1)
        self.id_ = id_
        self._id_plano_de_sala = None

        ca = self.get_content_area()
        g = _grid()
        ca.pack_start(g, True, True, 0)

        _lbl_entry(g, _("Sala:"), 0)
        self.e_sala = _entry_btn(g, 0, "…", self._sel_sala)
        self._id_sala = None

        _lbl_entry(g, _("Equipo:"), 1)
        self.e_equipo = _entry_btn(g, 1, "…", self._sel_equipo)
        self._id_equipo = None

        _lbl_entry(g, _("Tipo de montaje:"), 2)
        self.c_tipo_montaje = Gtk.ComboBoxText()
        self.c_tipo_montaje.append("PISO", "🖴 " + _("Piso"))
        self.c_tipo_montaje.append("PARED", "🧱 " + _("Pared"))
        self.c_tipo_montaje.set_active_id("PISO")
        g.attach(self.c_tipo_montaje, 1, 2, 2, 1)

        self.lbl_ubicacion = Gtk.Label(xalign=0)
        self.lbl_ubicacion.set_margin_start(8)
        self.lbl_ubicacion.set_margin_top(4)
        ca.pack_start(self.lbl_ubicacion, False, False, 0)

        self.btn_ubicar = Gtk.Button(
            label="📍 " + _("Ubicar en el plano"))
        self.btn_ubicar.set_margin_start(8)
        self.btn_ubicar.set_margin_top(4)
        self.btn_ubicar.set_margin_bottom(4)
        self.btn_ubicar.connect("clicked", self._ubicar_en_plano)
        ca.pack_start(self.btn_ubicar, False, False, 0)

        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(_("Guardar"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

        if id_:
            rows = Modelo.devolver_equipo_no_rack_sala(id_)
            if rows:
                self._id_sala   = str(rows[0][1])
                self._id_equipo = str(rows[0][2])
                self.e_sala.set_text(s(rows[0][3]))
                self.e_equipo.set_text(s(rows[0][4]))
                self._id_plano_de_sala = rows[0][5]
                self.c_tipo_montaje.set_active_id(
                    s(rows[0][6]) or "PISO")

        _pack_ultima_edicion(self, "equiponoraqueable_por_sala",
                             "id_equiponoraqueable_por_sala", id_)
        self._actualizar_estado_ubicacion()
        self.show_all()

    def _sel_sala(self, btn):
        dlg = SalasListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_sala = str(fila[0])
                self.e_sala.set_text(s(fila[1]))
        dlg.destroy()

    def _sel_equipo(self, btn):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True,
                             excluir_modulos_de_frame=True)
        if dlg.run() == Gtk.ResponseType.OK:
            fila = dlg._fila()
            if fila:
                self._id_equipo = str(fila[0])
                self.e_equipo.set_text(s(fila[1]))
        dlg.destroy()

    def _actualizar_estado_ubicacion(self):
        habilitar = bool(self.id_ and self._id_plano_de_sala)
        self.btn_ubicar.set_sensitive(habilitar)
        if not self.id_:
            texto = _("Guardá la asignación primero; la ubicación en el "
                      "plano se marca al volver a editarla.")
        elif not self._id_plano_de_sala:
            texto = _("La sala de esta asignación todavía no tiene un "
                      "plano asignado — asignaselo desde la ficha de "
                      "Sala.")
        else:
            texto = _("Marcá o mové el punto de este equipo en el plano "
                      "de su sala con el botón de abajo.")
        self.lbl_ubicacion.set_markup("<small><i>" + texto + "</i></small>")

    def _ubicar_en_plano(self, btn):
        from planos_ui import VistaPlanoInteractivo
        VistaPlanoInteractivo(
            self._id_plano_de_sala, parent=self,
            id_equiponoraqueable_foco=self.id_).run_and_destroy()

    def _on_response(self, dlg, resp):
        if resp != Gtk.ResponseType.OK:
            self.destroy()
            return
        if not self._id_sala or not self._id_equipo:
            mostrar_error(self, "Seleccioná sala y equipo antes de guardar.")
            return
        tipo_montaje = self.c_tipo_montaje.get_active_id() or "PISO"
        if self.id_:
            Modelo.modificacion_equipo_no_rack_sala(
                self.id_, self._id_sala, self._id_equipo, tipo_montaje)
        else:
            Modelo.alta_equipo_no_rack_sala(
                self._id_sala, self._id_equipo, tipo_montaje)
        self.destroy()

    def run_and_destroy(self):
        self.run()


class EquiposNoRackSalaListado(VentanaListado):
    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(_("Equipos sueltos por sala"),
                         [_("ID"), _("Sala"), _("Equipo")],
                         parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todos_equipos_no_rack_sala())

    def nuevo(self):
        dlg = _DialogoEquipoNoRackSala(parent=self)
        dlg.run_and_destroy()

    def editar(self, id_):
        dlg = _DialogoEquipoNoRackSala(id_=id_, parent=self)
        dlg.run_and_destroy()

    def eliminar(self, id_):
        Modelo.eliminar_equipo_no_rack_sala(id_)

