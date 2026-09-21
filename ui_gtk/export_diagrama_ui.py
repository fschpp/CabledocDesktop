"""ExportMixin — exportación del diagrama de conexiones a imagen/PDF (elección de formato, render a archivo, render de la vista actual).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
import math

from gi.repository import Gtk

from pantallas_comunes import _

# Descripción de cada formato para los títulos de los diálogos.
_DESC_FORMATO = {"svg": "SVG vectorial", "pdf": "PDF", "png": "PNG transparente"}

# PNG: el diagrama se dibuja en unidades de mundo (1 unidad = 1 px a zoom 1).
# Se rasteriza a 2x para que el texto y los cables no se vean pixelados al
# ampliar, pero acotado para diagramas grandes (la vista global puede tener
# cientos de nodos): máx. PNG_MAX_PIXELES en total (ARGB32 = 4 bytes/px) y
# PNG_MAX_LADO por lado (límite de cairo: 32767). Si el diagrama es tan grande
# que ni a 1x entra, la escala baja de 1 (el PNG sale más chico que el mundo).
PNG_ESCALA = 2.0
PNG_MAX_PIXELES = 64_000_000
PNG_MAX_LADO = 30000


class ExportMixin:
    def _exportar_crear_superficie(self, ruta, fmt, W, H):
        """Crea la superficie de Cairo del formato pedido. Devuelve
        (superficie, escala): escala != 1 sólo en PNG (ver PNG_ESCALA); el
        que dibuja tiene que hacer cr.scale(escala, escala). Ninguna
        superficie se pinta de fondo: PNG (ARGB32) arranca en transparente,
        SVG/PDF arrancan vacías."""
        import cairo as _cairo
        if fmt == "svg":
            return _cairo.SVGSurface(ruta, W, H), 1.0
        if fmt == "png":
            esc = min(PNG_ESCALA,
                      math.sqrt(PNG_MAX_PIXELES / max(W * H, 1.0)),
                      PNG_MAX_LADO / max(W, H, 1.0))
            surface = _cairo.ImageSurface(
                _cairo.FORMAT_ARGB32,
                max(1, math.ceil(W * esc)), max(1, math.ceil(H * esc)))
            return surface, esc
        return _cairo.PDFSurface(ruta, W, H), 1.0

    def _exportar_cerrar_superficie(self, surface, ruta, fmt):
        # El PNG se escribe recién ahora (SVG/PDF van escribiendo a `ruta`
        # a medida que se dibuja); hay que hacerlo ANTES de finish().
        if fmt == "png":
            surface.write_to_png(ruta)
        surface.finish()

    def _exportar_elegir(self, fmt):
        if not self._nodos:
            self._status("No hay nodos para exportar.")
            return
        dlg = Gtk.Dialog(
            title="Exportar como " + fmt.upper(),
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dlg.set_default_size(340, 180)
        area = dlg.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12);   area.set_margin_bottom(8)
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<b>¿Qué querés exportar?</b>")
        area.pack_start(lbl, False, False, 0)
        btn_todo  = Gtk.Button(label=_("⊕ Todo el diagrama  (todos los nodos)"))
        btn_vista = Gtk.Button(label=_("▣ Vista actual  (lo que se ve en pantalla)"))
        btn_todo.connect("clicked",  lambda _: dlg.response(1))
        btn_vista.connect("clicked", lambda _: dlg.response(2))
        area.pack_start(btn_todo,  True, True, 0)
        area.pack_start(btn_vista, True, True, 0)
        dlg.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        dlg.show_all()
        resp = dlg.run()
        dlg.destroy()
        if resp == 1:
            self._exportar(fmt)
        elif resp == 2:
            self._exportar_vista(fmt)

    def _exportar(self, fmt):
        import os
        if not self._nodos:
            self._status("No hay nodos para exportar.")
            return

        MARGEN = 40
        xs  = [n["x"]             for n in self._nodos.values()]
        ys  = [n["y"]             for n in self._nodos.values()]
        x2s = [n["x"] + n["ancho"] for n in self._nodos.values()]
        y2s = [n["y"] + n["alto"]  for n in self._nodos.values()]
        mn_x = min(xs)  - MARGEN
        mn_y = min(ys)  - MARGEN
        W    = max(x2s) + MARGEN - mn_x
        H    = max(y2s) + MARGEN - mn_y

        ext  = fmt.lower()
        desc = _DESC_FORMATO.get(ext, ext.upper())
        dlg  = Gtk.FileChooserDialog(
            title="Exportar diagrama como " + desc.upper(),
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        "Exportar", Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        carpeta = os.path.dirname(os.path.abspath(__file__))
        dlg.set_current_folder(carpeta)
        dlg.set_current_name("diagrama_conexiones." + ext)
        filtro = Gtk.FileFilter()
        filtro.set_name("Archivos " + ext.upper() + " (*." + ext + ")")
        filtro.add_pattern("*." + ext)
        dlg.add_filter(filtro)

        if dlg.run() != Gtk.ResponseType.OK:
            dlg.destroy()
            return

        ruta = dlg.get_filename()
        dlg.destroy()
        if not ruta.lower().endswith("." + ext):
            ruta += "." + ext

        try:
            self._exportar_renderizar(ruta, ext, mn_x, mn_y, W, H)
            self._status("Exportado: " + os.path.basename(ruta))
        except Exception as exc:
            import traceback
            dlg_err = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error al exportar:\n" + str(exc)
            )
            dlg_err.run(); dlg_err.destroy()

    def _exportar_renderizar(self, ruta, fmt, mn_x, mn_y, W, H):
        import cairo as _cairo

        surface, escala = self._exportar_crear_superficie(ruta, fmt, W, H)
        cr = _cairo.Context(surface)
        if escala != 1.0:
            cr.scale(escala, escala)

        # Fondo TRANSPARENTE: a propósito no se pinta el color de fondo
        # (C_BG) ni la grilla (C_GRID) que sí se ven en pantalla (_on_draw).
        # La superficie de Cairo (SVG/PDF) arranca sin contenido, así que
        # sólo queda lo dibujado abajo (cables, nodos, etiquetas) y el
        # diagrama se puede pegar sobre cualquier fondo.

        # Trasladar para que (mn_x, mn_y) quede en (0,0)
        cr.save()
        cr.translate(-mn_x, -mn_y)

        # Cables
        fan_offsets = self._calc_fan_offsets()
        conn_colors = self._calc_conn_colors()
        jump_points = (self._calc_jump_points(fan_offsets)
                        if (self._line_jumps and self._estilo_conn != "bezier")
                        else {})
        for conn in self._conns:
            self._draw_conn(cr, conn, fan_offsets, jump_points, conn_colors)
        self._draw_conexiones_incompletas(cr)

        # Nodos
        for nodo in self._nodos.values():
            self._draw_node(cr, nodo)

        # etiquetas de conexiones incompletas: por encima de nodos/iconos/línea
        self._draw_conexiones_incompletas_etiquetas(cr)

        cr.restore()
        self._exportar_cerrar_superficie(surface, ruta, fmt)


    def _exportar_vista(self, fmt):
        import os
        try:
            import cairo as _cairo
        except ImportError:
            import gi; gi.require_version("Gtk","3.0")
        alloc = self._da.get_allocation()
        W = float(alloc.width)
        H = float(alloc.height)
        ext  = fmt.lower()
        desc = _DESC_FORMATO.get(ext, ext.upper())
        dlg  = Gtk.FileChooserDialog(
            title="Exportar vista actual como " + desc.upper(),
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                        "Exportar", Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        carpeta = os.path.dirname(os.path.abspath(__file__))
        dlg.set_current_folder(carpeta)
        dlg.set_current_name("diagrama_vista." + ext)
        filtro = Gtk.FileFilter()
        filtro.set_name("Archivos " + ext.upper() + " (*." + ext + ")")
        filtro.add_pattern("*." + ext)
        dlg.add_filter(filtro)
        if dlg.run() != Gtk.ResponseType.OK:
            dlg.destroy(); return
        ruta = dlg.get_filename()
        dlg.destroy()
        if not ruta.lower().endswith("." + ext):
            ruta += "." + ext
        try:
            import cairo as _cairo
            surface, escala = self._exportar_crear_superficie(ruta, ext, W, H)
            cr = _cairo.Context(surface)
            if escala != 1.0:
                cr.scale(escala, escala)
            # Fondo TRANSPARENTE: no se pinta C_BG ni la grilla C_GRID de
            # _on_draw (ver _exportar_renderizar).
            # Mismo transform world que _on_draw
            cr.save()
            cr.translate(self._pan_x, self._pan_y)
            cr.scale(self._zoom, self._zoom)
            fan_offsets = self._calc_fan_offsets()
            conn_colors = self._calc_conn_colors()
            jump_points = (self._calc_jump_points(fan_offsets)
                            if (self._line_jumps and self._estilo_conn != "bezier")
                            else {})
            for conn in self._conns:
                self._draw_conn(cr, conn, fan_offsets, jump_points, conn_colors)
            self._draw_conexiones_incompletas(cr)
            for nodo in self._nodos.values():
                self._draw_node(cr, nodo)
            # etiquetas de conexiones incompletas: por encima de nodos/iconos/línea
            self._draw_conexiones_incompletas_etiquetas(cr)
            cr.restore()
            self._exportar_cerrar_superficie(surface, ruta, ext)
            self._status("Exportado: " + os.path.basename(ruta))
        except Exception as exc:
            dlg_err = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error al exportar:\n" + str(exc)
            )
            dlg_err.run(); dlg_err.destroy()


