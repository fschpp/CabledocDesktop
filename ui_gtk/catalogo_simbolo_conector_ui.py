#!/usr/bin/env python3
"""
catalogo_simbolo_conector_ui.py — CableDoc GTK3

Pantalla de administración de `catalogo_simbolo_conector` — Fase 0 de
plan_paneles_vectoriales_v3.md. Un símbolo (forma real: XLR, BNC, etc.) por
`tipo_ficha` (qué es un conector eléctricamente — no `tipo_conector`, que es
sólo el rol IN/OUT del jack en el equipo; corrección post-merge del PR #21,
ver modelo.py), reutilizable entre todos los equipos. No depende de ninguna
imagen puntual — la escala real se resuelve en Fase 1 (imagen_conectores_ui.py
/ editor_masivo_conectores_ui.py) a partir de `tamano_relativo` acá + la
calibración mm/px de cada imagen.

Sigue el mismo patrón que TiposCableListado / _DialogoTipoCable en
catalogos_basicos_ui.py: VentanaListado + un Gtk.Dialog propio para el
alta/edición, con combo buscable de tipo_ficha y validación de XML antes
de guardar (nunca se guarda un fragmento que no vaya a poder dibujarse).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import xml.etree.ElementTree as ET

from core.modelo import Modelo

try:
    from core.i18n import _
except ImportError:
    def _(t): return t

from pantallas_comunes import (
    s,
    mostrar_error,
    VentanaListado,
    _grid,
    _searchable_combo,
    _get_combo_id,
    _set_combo_id,
    _parse_float_opt,
    _fmt_float_opt,
    _pack_ultima_edicion,
    _crear_handle_simbolo,
    _dibujar_simbolo_conector,
)


def _validar_fragmento_svg(texto):
    """Valida que `texto` (el contenido interno del símbolo, sin el tag
    <svg> exterior) sea XML bien formado envuelto en un <svg> de prueba.
    Devuelve (True, "") o (False, mensaje_de_error) — nunca levanta
    excepción, para poder llamarse directo desde el botón Aceptar."""
    texto = (texto or "").strip()
    if not texto:
        return False, _("El fragmento SVG no puede estar vacío.")
    try:
        ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{texto}</svg>')
        return True, ""
    except ET.ParseError as e:
        return False, _("XML inválido: {0}").format(e)


class _VistaPreviaSimbolo(Gtk.DrawingArea):
    """Cuadradito de 64x64 que redibuja el símbolo en vivo mientras se edita
    el fragmento — para no tener que guardar a ciegas y abrir un equipo
    real para ver si el símbolo quedó bien."""

    def __init__(self):
        super().__init__()
        self.set_size_request(64, 64)
        self._handle = None
        self.connect("draw", self._on_draw)

    def actualizar(self, svg_fragmento, viewbox, color):
        self._handle = _crear_handle_simbolo(svg_fragmento, viewbox or "0 0 24 24", color)
        self.queue_draw()

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        cr.set_source_rgb(0.15, 0.15, 0.17)
        cr.paint()
        cx, cy = alloc.width / 2.0, alloc.height / 2.0
        radio = min(alloc.width, alloc.height) / 2.0 - 4
        cr.set_source_rgb(0.85, 0.85, 0.9)
        ok = _dibujar_simbolo_conector(cr, self._handle, cx, cy, radio)
        if not ok:
            # mismo criterio que el render real: si no se puede dibujar,
            # mostrar algo que deje claro que no hay vista previa válida —
            # nunca una pantalla en blanco sin explicación.
            cr.set_source_rgb(0.6, 0.15, 0.15)
            cr.arc(cx, cy, radio, 0, 2 * 3.14159265)
            cr.fill()


class _DialogoSimboloConector(Gtk.Dialog):
    def __init__(self, parent=None, fila=None):
        """`fila` = (id, id_tipo_ficha, svg_fragmento, viewbox,
        tamano_relativo, color_sugerido) para editar, o None para alta."""
        titulo = _("Editar símbolo de conector") if fila else _("Nuevo símbolo de conector")
        super().__init__(title=titulo, transient_for=parent, modal=True)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_size(480, 420)

        self._id = fila[0] if fila else None
        self.valor = None  # (id_tipo_ficha, frag, viewbox, tam_rel, color) al aceptar

        g = _grid()
        fila_grid = 0

        g.attach(Gtk.Label(label=_("Ficha (qué es eléctricamente):"), xalign=0),
                  0, fila_grid, 1, 1)
        self.c_tipo = _searchable_combo(g, fila_grid, Modelo.devolver_todos_los_tipos_ficha())
        if fila:
            _set_combo_id(self.c_tipo, fila[1])
        fila_grid += 1

        g.attach(Gtk.Label(label=_("Tamaño relativo (1.0 = XLR):"), xalign=0),
                  0, fila_grid, 1, 1)
        self.e_tamano = Gtk.Entry()
        self.e_tamano.set_text(_fmt_float_opt(fila[4]) if fila else "1.0")
        g.attach(self.e_tamano, 1, fila_grid, 1, 1)
        fila_grid += 1

        g.attach(Gtk.Label(label=_("viewBox:"), xalign=0), 0, fila_grid, 1, 1)
        self.e_viewbox = Gtk.Entry()
        self.e_viewbox.set_text(s(fila[3]) if fila and fila[3] else "0 0 24 24")
        g.attach(self.e_viewbox, 1, fila_grid, 1, 1)
        fila_grid += 1

        g.attach(Gtk.Label(label=_("Color sugerido (opcional, hex):"), xalign=0),
                  0, fila_grid, 1, 1)
        self.e_color = Gtk.Entry()
        self.e_color.set_text(s(fila[5]) if fila and fila[5] else "")
        self.e_color.set_placeholder_text(_("vacío = currentColor"))
        g.attach(self.e_color, 1, fila_grid, 1, 1)
        fila_grid += 1

        self.get_content_area().pack_start(g, False, False, 8)

        lbl_frag = Gtk.Label(
            label=_("Fragmento SVG (sin el tag <svg> exterior — sólo "
                    "<circle>, <path>, etc.):"),
            xalign=0)
        lbl_frag.set_margin_start(8)
        lbl_frag.set_margin_top(8)
        self.get_content_area().pack_start(lbl_frag, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(-1, 140)
        self.tv_frag = Gtk.TextView()
        self.tv_frag.set_monospace(True)
        self.tv_frag.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        if fila and fila[2]:
            self.tv_frag.get_buffer().set_text(fila[2])
        scroll.add(self.tv_frag)

        caja_central = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        caja_central.set_margin_start(8)
        caja_central.set_margin_end(8)
        caja_central.pack_start(scroll, True, True, 0)

        self._preview = _VistaPreviaSimbolo()
        marco_preview = Gtk.Frame()
        marco_preview.add(self._preview)
        caja_central.pack_start(marco_preview, False, False, 0)

        self.get_content_area().pack_start(caja_central, True, True, 4)

        btn_preview = Gtk.Button(label=_("Vista previa"))
        btn_preview.connect("clicked", self._actualizar_preview)
        btn_preview.set_margin_start(8)
        btn_preview.set_margin_top(4)
        self.get_content_area().pack_start(btn_preview, False, False, 0)

        _pack_ultima_edicion(self, "catalogo_simbolo_conector", "id", self._id)

        self.connect("response", self._on_response)
        self.show_all()
        self._actualizar_preview()

    def _texto_fragmento(self):
        buf = self.tv_frag.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _actualizar_preview(self, *_a):
        self._preview.actualizar(
            self._texto_fragmento(),
            s(self.e_viewbox.get_text()) or "0 0 24 24",
            s(self.e_color.get_text()) or None,
        )

    def _on_response(self, dialogo, response_id):
        if response_id != Gtk.ResponseType.OK:
            return
        id_tipo = _get_combo_id(self.c_tipo)
        if not id_tipo:
            mostrar_error(self, _("Elegí una ficha."))
            self.stop_emission_by_name("response")
            return
        frag = self._texto_fragmento()
        ok, error = _validar_fragmento_svg(frag)
        if not ok:
            mostrar_error(self, error)
            self.stop_emission_by_name("response")
            return
        tam_rel = _parse_float_opt(self.e_tamano.get_text())
        if not tam_rel or tam_rel <= 0:
            mostrar_error(self, _("El tamaño relativo tiene que ser mayor a 0."))
            self.stop_emission_by_name("response")
            return
        self.valor = (
            id_tipo, frag.strip(),
            s(self.e_viewbox.get_text()) or "0 0 24 24",
            tam_rel,
            s(self.e_color.get_text()) or None,
        )


class CatalogoSimbolosConectorListado(VentanaListado):
    """Listado de símbolos de conector — Fase 0 de
    plan_paneles_vectoriales_v3.md. Un símbolo activa el render con forma
    real (Fase 1) sólo para conectores de ese tipo cuya imagen de fondo sea
    un SVG; en cualquier otro caso el marcador genérico sigue igual que
    siempre — este catálogo es aditivo, no cambia nada retroactivamente."""

    def __init__(self, parent=None, modo_seleccion=False):
        super().__init__(
            _("Símbolos de Conector (paneles vectoriales)"),
            [_("ID"), _("Ficha"), _("Tamaño relativo"), _("Fragmento (caract.)")],
            parent=parent, modo_seleccion=modo_seleccion)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_simbolos_conector())

    def nuevo(self):
        dlg = _DialogoSimboloConector(parent=self)
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            id_tipo, frag, viewbox, tam_rel, color = dlg.valor
            existente = Modelo.devolver_simbolo_de_tipo_ficha(id_tipo)
            if existente:
                mostrar_error(
                    self,
                    _("Ya existe un símbolo para esa ficha — abrilo para "
                      "editarlo en vez de crear uno nuevo."))
            else:
                Modelo.alta_simbolo_conector(id_tipo, frag, viewbox, tam_rel, color)
        dlg.destroy()
        self.cargar_datos()

    def editar(self, id_):
        fila = Modelo.devolver_simbolo_conector(id_)
        if not fila:
            return
        dlg = _DialogoSimboloConector(parent=self, fila=fila[0])
        if dlg.run() == Gtk.ResponseType.OK and dlg.valor:
            id_tipo, frag, viewbox, tam_rel, color = dlg.valor
            Modelo.modificacion_simbolo_conector(id_, id_tipo, frag, viewbox, tam_rel, color)
        dlg.destroy()
        self.cargar_datos()

    def eliminar(self, id_):
        Modelo.eliminar_simbolo_conector(id_)
        self.cargar_datos()
