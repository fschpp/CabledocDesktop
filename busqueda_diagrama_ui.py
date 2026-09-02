"""BusquedaMixin — búsqueda de nodos dentro del diagrama de conexiones (diálogo, navegación entre resultados, overlay).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
from gi.repository import Gtk

from pantallas_comunes import _rrect, _dibujar_icono_buscar


class BusquedaMixin:
    def _buscar_abrir_dialogo(self):
        """Abre el diálogo de búsqueda y resalta los resultados en el diagrama."""
        from pantallas_avanzadas import _BuscadorDiagrama  # import diferido: evita ciclo con pantallas_avanzadas.py
        dlg = _BuscadorDiagrama(parent=self, nodos=self._nodos, conns=self._conns)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK and dlg.resultado_ids:
            self._buscar_ids   = dlg.resultado_ids
            self._buscar_idx   = 0
            self._buscar_texto = dlg.texto_buscado
            self._buscar_navegar(0)   # centra en el primero
        elif resp == Gtk.ResponseType.REJECT:
            # "Limpiar" en el diálogo
            self._buscar_limpiar()
        dlg.destroy()

    def _buscar_navegar(self, delta: int):
        """Avanza/retrocede entre los resultados y centra la vista."""
        if not self._buscar_ids:
            return
        self._buscar_idx = (self._buscar_idx + delta) % len(self._buscar_ids)
        eq_id = self._buscar_ids[self._buscar_idx]
        nodo  = self._nodos.get(eq_id)
        if nodo:
            self._centrar_en_nodo(nodo)
        self._da.queue_draw()

    def _buscar_limpiar(self):
        self._buscar_ids  = []
        self._buscar_idx  = -1
        self._buscar_texto = ""
        self._da.queue_draw()

    def _buscar_draw_overlay(self, cr, W: int, H: int):
        """Dibuja el resaltado de los nodos encontrados y el HUD de navegación."""
        if not self._buscar_ids:
            return

        # ── Resaltado de nodos en coordenadas de mundo ────────────────────────
        cr.save()
        cr.translate(self._pan_x, self._pan_y)
        cr.scale(self._zoom, self._zoom)

        for i, eq_id in enumerate(self._buscar_ids):
            nodo = self._nodos.get(eq_id)
            if not nodo:
                continue
            x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
            activo = (i == self._buscar_idx)

            if activo:
                # Halo exterior pulsante (naranja brillante)
                cr.set_source_rgba(1.0, 0.70, 0.0, 0.30)
                _rrect(cr, x - 12, y - 12, w + 24, h + 24); cr.fill()
                # Borde grueso amarillo-naranja
                cr.set_source_rgba(1.0, 0.85, 0.0, 1.0)
                cr.set_line_width(4.0)
                _rrect(cr, x - 4, y - 4, w + 8, h + 8); cr.stroke()
                # Relleno tenue
                cr.set_source_rgba(1.0, 0.90, 0.0, 0.18)
                _rrect(cr, x, y, w, h); cr.fill()
            else:
                # Resultado secundario: borde fino naranja apagado
                cr.set_source_rgba(1.0, 0.65, 0.20, 0.70)
                cr.set_line_width(2.0)
                _rrect(cr, x - 2, y - 2, w + 4, h + 4); cr.stroke()

        cr.restore()

        # ── HUD de navegación (coords de pantalla) ────────────────────────────
        n_total  = len(self._buscar_ids)
        n_actual = self._buscar_idx + 1
        texto_q  = self._buscar_texto[:30] + ("…" if len(self._buscar_texto) > 30 else "")
        texto_hud = f'"{texto_q}"  —  {n_actual} / {n_total}'

        # Medir ancho del HUD (+ lugar para el ícono de lupa a la izquierda)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(13)
        ext      = cr.text_extents(texto_hud)
        lupa_w   = 22
        pw       = lupa_w + ext.width + 32
        ph       = 36
        px       = (W - pw) / 2
        py       = H - ph - 48    # justo encima del statusbar

        # Fondo redondeado
        cr.set_source_rgba(0.08, 0.08, 0.12, 0.92)
        _rrect(cr, px, py, pw, ph, 10); cr.fill()
        cr.set_source_rgba(1.0, 0.80, 0.10, 0.90)
        cr.set_line_width(1.5)
        _rrect(cr, px, py, pw, ph, 10); cr.stroke()

        # Ícono de lupa (antes emoji 🔍, sin glifo en algunas fuentes)
        _dibujar_icono_buscar(cr, "lupa", px + 16 + lupa_w/2, py + ph/2, 15)

        # Texto
        cr.set_source_rgba(1.0, 0.92, 0.70, 1.0)
        cr.move_to(px + 20 + lupa_w, py + ph * 0.66)
        cr.show_text(texto_hud)

        # Botones ◀ ▶ ✕ en el HUD
        bw, bh = 26, 22
        btn_y  = py + (ph - bh) / 2

        # ◀ prev (antes glifo unicode '◀', ahora ícono PNG propio)
        bx_prev = px + pw + 6
        cr.set_source_rgba(0.25, 0.35, 0.60, 0.90)
        _rrect(cr, bx_prev, btn_y, bw, bh, 5); cr.fill()
        _dibujar_icono_buscar(cr, "prev", bx_prev + bw/2, btn_y + bh/2, 14)
        self._buscar_btn_prev = (bx_prev, btn_y, bw, bh)

        # ▶ next (antes glifo unicode '▶', ahora ícono PNG propio)
        bx_next = bx_prev + bw + 4
        cr.set_source_rgba(0.25, 0.35, 0.60, 0.90)
        _rrect(cr, bx_next, btn_y, bw, bh, 5); cr.fill()
        _dibujar_icono_buscar(cr, "next", bx_next + bw/2, btn_y + bh/2, 14)
        self._buscar_btn_next = (bx_next, btn_y, bw, bh)

        # ✕ limpiar (antes glifo unicode '✕', ahora ícono PNG propio)
        bx_x = bx_next + bw + 4
        cr.set_source_rgba(0.50, 0.15, 0.15, 0.90)
        _rrect(cr, bx_x, btn_y, bw, bh, 5); cr.fill()
        _dibujar_icono_buscar(cr, "cerrar", bx_x + bw/2, btn_y + bh/2, 13)
        self._buscar_btn_x = (bx_x, btn_y, bw, bh)


