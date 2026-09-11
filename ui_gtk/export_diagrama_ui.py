"""ExportMixin — exportación del diagrama de conexiones a imagen/PDF (elección de formato, render a archivo, render de la vista actual).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
from gi.repository import Gtk

from pantallas_comunes import _


class ExportMixin:
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
        desc = "SVG vectorial" if ext == "svg" else "PDF"
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

        if fmt == "svg":
            surface = _cairo.SVGSurface(ruta, W, H)
        else:
            surface = _cairo.PDFSurface(ruta, W, H)

        cr = _cairo.Context(surface)

        # Fondo
        cr.set_source_rgb(*self.C_BG)
        cr.paint()

        # Grilla (en coords de mundo desplazadas al origen)
        GRID = 40
        cr.set_source_rgb(*self.C_GRID)
        cr.set_line_width(0.5)
        ox = (-mn_x) % GRID
        oy = (-mn_y) % GRID
        x = ox
        while x < W:
            cr.move_to(x, 0); cr.line_to(x, H); x += GRID
        y = oy
        while y < H:
            cr.move_to(0, y); cr.line_to(W, y); y += GRID
        cr.stroke()

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
        surface.finish()


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
        desc = "SVG vectorial" if ext == "svg" else "PDF"
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
            if ext == "svg":
                surface = _cairo.SVGSurface(ruta, W, H)
            else:
                surface = _cairo.PDFSurface(ruta, W, H)
            cr = _cairo.Context(surface)
            # Fondo
            cr.set_source_rgb(*self.C_BG); cr.paint()
            # Grilla identica a _on_draw
            GRID = 40 * self._zoom
            ox   = self._pan_x % GRID
            oy   = self._pan_y % GRID
            cr.set_source_rgb(*self.C_GRID)
            cr.set_line_width(0.5)
            x = ox
            while x < W:
                cr.move_to(x, 0); cr.line_to(x, H); x += GRID
            y = oy
            while y < H:
                cr.move_to(0, y); cr.line_to(W, y); y += GRID
            cr.stroke()
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
            surface.finish()
            self._status("Exportado: " + os.path.basename(ruta))
        except Exception as exc:
            dlg_err = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error al exportar:\n" + str(exc)
            )
            dlg_err.run(); dlg_err.destroy()


