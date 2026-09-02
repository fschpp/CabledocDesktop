"""DibujoMixin — dibujo Cairo del diagrama de conexiones (nodos, aristas, minimapa, conexión interna, conexiones incompletas).

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
import math
import os

from gi.repository import Gdk, GdkPixbuf

from modelo import Modelo
from pantallas_comunes import s, _, _rrect, _rrect_top, _tc, _abrev, _icono_critico_surface


class DibujoMixin:
    def _on_draw(self, da, cr):
        alloc = da.get_allocation()
        W, H  = alloc.width, alloc.height

        # background
        cr.set_source_rgb(*self.C_BG); cr.paint()

        # grid
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

        # world transform
        cr.save()
        cr.translate(self._pan_x, self._pan_y)
        cr.scale(self._zoom, self._zoom)

        # connections first
        # Precompute vertical fan offsets so cables don't overlap on nodes/ports
        fan_offsets  = self._calc_fan_offsets()
        conn_colors  = self._calc_conn_colors()
        jump_points  = (self._calc_jump_points(fan_offsets)
                        if (self._line_jumps and self._estilo_conn != "bezier")
                        else {})
        for conn in self._conns:
            self._draw_conn(cr, conn, fan_offsets, jump_points, conn_colors)
        self._draw_conexiones_incompletas(cr)
        self._draw_conexiones_extension(cr)

        # nodes on top
        for nodo in self._nodos.values():
            self._draw_node(cr, nodo)

        # cable "elástico" en construcción (arrastrando de un puerto a otro)
        if self._wire_from:
            nodo0, cid0, lado0 = self._wire_from
            px, py = self._port_pos(nodo0, cid0, lado0)
            self._draw_wire_en_progreso(cr, px, py, self._wire_mx, self._wire_my)

        # etiquetas de conexiones incompletas: por encima de nodos/iconos/línea
        self._draw_conexiones_incompletas_etiquetas(cr)

        # — Overlay "conexión interna" de módulo patchera —
        self._draw_conexion_interna(cr)

        cr.restore()

        # ── Overlay análisis de impacto ────────────────────────────────────
        self._imp_on_draw_overlay(cr, W, H)

        # ── Overlay Modo Escenario ──────────────────────────────────────────
        self._esc_on_draw_overlay(cr, W, H)

        # ── Overlay leyenda de señal ─────────────────────────────────────────
        self._senal_on_draw_overlay(cr, W, H)

        # ── Overlay vista previa de imagen (mini-ventana, esquina inf. izq.) ─
        self._visp_on_draw_overlay(cr, W, H)

        # ── Overlay de búsqueda ───────────────────────────────────────────────
        self._buscar_draw_overlay(cr, W, H)

        # ── Rubber-band de selección múltiple ────────────────────────────────
        if self._rband_active:
            cr.save()
            cr.translate(self._pan_x, self._pan_y)
            cr.scale(self._zoom, self._zoom)
            rx  = min(self._rband_x0, self._rband_x1)
            ry  = min(self._rband_y0, self._rband_y1)
            rw  = abs(self._rband_x1 - self._rband_x0)
            rh  = abs(self._rband_y1 - self._rband_y0)
            cr.set_source_rgba(0.30, 0.55, 1.0, 0.12)
            cr.rectangle(rx, ry, rw, rh); cr.fill()
            cr.set_source_rgba(0.30, 0.55, 1.0, 0.80)
            cr.set_line_width(1.5 / self._zoom)
            cr.rectangle(rx, ry, rw, rh); cr.stroke()
            cr.restore()

        # ── Minimapa (solo vista global, esquina inferior derecha) ──────────
        self._draw_minimap(cr, W, H)

    def _draw_node(self, cr, nodo):
        x, y, w, h = nodo["x"], nodo["y"], nodo["ancho"], nodo["alto"]
        sel        = (nodo["id"] == self._sel_id or nodo["id"] in self._sel_ids)
        rc, gc, bc = nodo["color"]

        # shadow
        cr.set_source_rgba(0, 0, 0, 0.30)
        _rrect(cr, x+4, y+4, w, h); cr.fill()

        if self._solo_nombre:
            # ── compact mode: only the header bar ────────────────────────────
            rc2, gc2, bc2, ancho_borde = self._riesgo_color_y_borde(
                nodo["id"], rc, gc, bc, 2.0 if sel else 1.0)
            cr.set_source_rgb(rc2*0.85, gc2*0.85, bc2*0.85)
            _rrect(cr, x, y, w, h); cr.fill()
            # border
            cr.set_source_rgb(*self.C_NODE_BSEL if sel else self.C_NODE_B)
            cr.set_line_width(ancho_borde)
            _rrect(cr, x, y, w, h); cr.stroke()
            # name centered in the bar
            cr.set_source_rgb(*self.C_TXT_H)
            cr.select_font_face("Sans", 0, 1); cr.set_font_size(11)
            nom = _abrev(cr, nodo["nombre"], w - 14)
            _tc(cr, nom, x + w/2, y + h*0.52)
            if nodo.get("critico"):
                self._draw_badge_critico(cr, x, y)
            return

        # ── full mode ─────────────────────────────────────────────────────────
        # body
        cr.set_source_rgb(*self.C_NODE_SEL if sel else self.C_NODE)
        _rrect(cr, x, y, w, h); cr.fill()

        # header
        rc2, gc2, bc2, ancho_borde = self._riesgo_color_y_borde(
            nodo["id"], rc, gc, bc, 2.0 if sel else 1.0)
        cr.set_source_rgb(rc2*0.85, gc2*0.85, bc2*0.85)
        _rrect_top(cr, x, y, w, self.HDR_H); cr.fill()

        # header text — equipment name
        cr.set_source_rgb(*self.C_TXT_H)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(11)
        nom = _abrev(cr, nodo["nombre"], w - 14)
        _tc(cr, nom, x + w/2, y + self.HDR_H*0.52)

        # tipo (small, below header — shown in body top area)
        cr.select_font_face("Sans", 2, 0); cr.set_font_size(8)
        cr.set_source_rgba(*self.C_TXT_SUB, 0.85)
        tipo_lbl = _abrev(cr, nodo["tipo"], w - 10)
        _tc(cr, tipo_lbl, x + w/2, y + self.HDR_H + 8)

        # border
        cr.set_source_rgb(*self.C_NODE_BSEL if sel else self.C_NODE_B)
        cr.set_line_width(ancho_borde)
        _rrect(cr, x, y, w, h); cr.stroke()

        if nodo.get("critico"):
            self._draw_badge_critico(cr, x, y)

        # ── ports ────────────────────────────────────────────────────────────
        body_y = y + self.HDR_H + self.PORT_PAD + 10   # +10 for tipo label

        # IN ports (left)
        for idx, (cid, cnm, _) in enumerate(nodo["in"]):
            py = body_y + idx * self.PORT_H + self.PORT_H / 2
            # circle (half outside node) — coloreado por señal si el
            # toggle "📡 Colorear por señal" está activo (Fase 5)
            color_puerto = self._senal_color_puerto(cid, self.C_PORT_IN)
            cr.set_source_rgb(*color_puerto)
            cr.arc(x, py, self.PORT_R, 0, 6.2832); cr.fill()
            cr.set_source_rgb(0, 0, 0)
            cr.set_line_width(0.8)
            cr.arc(x, py, self.PORT_R, 0, 6.2832); cr.stroke()
            # label
            cr.set_source_rgb(*self.C_TXT_PORT)
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(8)
            lbl = _abrev(cr, cnm, w/2 - self.PORT_R - 8)
            lbl_x = x + self.PORT_R + 4
            lbl_y = py - cr.text_extents(lbl).height/2 - cr.text_extents(lbl).y_bearing
            cr.move_to(lbl_x, lbl_y)
            cr.show_text(lbl)
            # plan_estado_senal_y_linaje.md, Función 1: tachar el label si
            # este conector quedó sin señal en una simulación activa
            # (Impacto/Riesgo/Escenario) mientras "Colorear por señal" está
            # prendido — mismo criterio que ya usa _senal_color_puerto para
            # devolver el color neutro en vez del color de señal.
            if self._senal_color_activo and self._senal_puerto_caido(cid):
                ext_lbl = cr.text_extents(lbl)
                self._senal_dibujar_tachado(
                    cr, lbl_x, py, lbl_x + ext_lbl.width, py)

        # OUT ports (right)
        for idx, (cid, cnm, _) in enumerate(nodo["out"]):
            py = body_y + idx * self.PORT_H + self.PORT_H / 2
            # circle
            color_puerto = self._senal_color_puerto(cid, self.C_PORT_OUT)
            cr.set_source_rgb(*color_puerto)
            cr.arc(x+w, py, self.PORT_R, 0, 6.2832); cr.fill()
            cr.set_source_rgb(0, 0, 0)
            cr.set_line_width(0.8)
            cr.arc(x+w, py, self.PORT_R, 0, 6.2832); cr.stroke()
            # right-aligned label
            cr.set_source_rgb(*self.C_TXT_PORT)
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(8)
            lbl = _abrev(cr, cnm, w/2 - self.PORT_R - 8)
            ext = cr.text_extents(lbl)
            lbl_x = x + w - self.PORT_R - 5 - ext.width - ext.x_bearing
            lbl_y = py - ext.height/2 - ext.y_bearing
            cr.move_to(lbl_x, lbl_y)
            cr.show_text(lbl)
            if self._senal_color_activo and self._senal_puerto_caido(cid):
                self._senal_dibujar_tachado(
                    cr, lbl_x, py, lbl_x + ext.width, py)

    def _draw_conn(self, cr, conn, fan_offsets=None, jump_points=None, conn_colors=None):
        src = self._nodos.get(conn["src_eq"])
        dst = self._nodos.get(conn["dst_eq"])
        if not src or not dst: return

        off = fan_offsets.get(conn["id"], [0, 0]) if fan_offsets else [0, 0]
        src_dy, dst_dy = off[0], off[1]

        # Anchor points
        if conn["src_con"] and not self._solo_nombre:
            x0, y0 = self._port_pos(src, conn["src_con"], "out")
        else:
            x0 = src["x"] + src["ancho"]
            y0 = src["y"] + src["alto"] / 2
        y0 += src_dy

        if conn["dst_con"] and not self._solo_nombre:
            x1, y1 = self._port_pos(dst, conn["dst_con"], "in")
        else:
            x1 = dst["x"]
            y1 = dst["y"] + dst["alto"] / 2
        y1 += dst_dy

        sel    = self._sel_id in (conn["src_eq"], conn["dst_eq"])
        estilo = self._estilo_conn
        # Los line jumps no se dibujan en curvas Bézier
        jumps  = (jump_points or {}).get(conn["id"], []) if estilo != "bezier" else []
        JUMP_R = 7   # radius of jump arc in world units

        # Determine line color: per-cable color for selected node, else defaults
        custom_rgb = (conn_colors or {}).get(conn["id"])
        if custom_rgb:
            line_rgba  = (*custom_rgb, 0.92)
            arrow_rgba = (*custom_rgb, 1.0)
            lbl_rgba   = custom_rgb
        elif sel:
            line_rgba  = (*self.C_CONN_SEL, 0.90)
            arrow_rgba = (*self.C_CONN_SEL, 0.95)
            lbl_rgba   = self.C_TXT_CABLE
        else:
            line_rgba  = (*self.C_CONN, 0.55)
            arrow_rgba = (*self.C_CONN, 0.80)
            lbl_rgba   = self.C_TXT_CABLE

        cr.set_source_rgba(*line_rgba)
        cr.set_line_width(2.4 if (sel or custom_rgb) else 1.4)

        # ── helper: draw a polyline with jump arcs cut out ───────────────────
        def draw_segments_with_jumps(pts):
            """Draw polyline pts[] inserting a semicircular bridge at each jump."""
            if not jumps:
                cr.move_to(*pts[0])
                for p in pts[1:]:
                    cr.line_to(*p)
                cr.stroke()
                return

            # Build list of (dist_along_polyline, jump) sorted by position
            # Compute cumulative distances along the polyline
            seg_dists = []   # (cum_start, cum_end, seg_idx)
            cum = 0.0
            for k in range(len(pts)-1):
                dx = pts[k+1][0]-pts[k][0]; dy = pts[k+1][1]-pts[k][1]
                seg_len = math.hypot(dx, dy)
                seg_dists.append((cum, cum+seg_len, k, seg_len))
                cum += seg_len
            total_len = cum

            # For each jump, find which segment it falls on and its distance
            jump_events = []
            for (jx, jy, jang) in jumps:
                for (cs, ce, ki, slen) in seg_dists:
                    if slen < 1e-6: continue
                    px, py = pts[ki]; qx, qy = pts[ki+1]
                    # project jump point onto segment
                    t = ((jx-px)*(qx-px)+(jy-py)*(qy-py)) / (slen*slen)
                    if 0.0 <= t <= 1.0:
                        d = cs + t*slen
                        jump_events.append((d, jx, jy, jang))
                        break
            jump_events.sort(key=lambda e: e[0])

            # Walk the polyline, pausing for each jump arc
            def point_at_dist(d):
                for (cs, ce, ki, slen) in seg_dists:
                    if cs <= d <= ce or ki == len(pts)-2:
                        t = (d-cs)/slen if slen > 1e-6 else 0
                        px, py = pts[ki]; qx, qy = pts[ki+1]
                        return px+t*(qx-px), py+t*(qy-py)
                return pts[-1]

            cursor = 0.0
            started = False
            for (d, jx, jy, jang) in jump_events:
                d_in  = max(0, d - JUMP_R)
                d_out = min(total_len, d + JUMP_R)
                if d_in <= cursor: continue    # overlapping jumps: skip

                # line up to jump entry
                pin = point_at_dist(d_in)
                if not started:
                    cr.move_to(*pts[0]); started = True
                cr.line_to(*pin)
                cr.stroke()

                # semicircular arc over the crossing.
                # `jang` is THIS cable's own path direction at the crossing
                # point (see _calc_jump_points), so pin/pout sit exactly at
                # distance JUMP_R along that direction from (jx,jy).
                # Offsetting by ±90° from the perpendicular bulge angle
                # (jang + π/2) lands the arc's two endpoints exactly on
                # pin and pout, so the semicircle connects seamlessly with
                # the line being interrupted instead of floating off it.
                a0 = jang + math.pi / 2
                cr.set_source_rgba(*line_rgba)
                cr.arc(jx, jy, JUMP_R,
                       a0 - math.pi/2,   # start → coincide con pin/pout
                       a0 + math.pi/2)   # end   → coincide con el otro extremo
                cr.stroke()

                pout = point_at_dist(d_out)
                cr.move_to(*pout)
                started = True
                cursor = d_out

            # remaining path
            if not started:
                cr.move_to(*pts[0])
            for p in pts[1:]:
                cr.line_to(*p)
            cr.stroke()

        # ── path depending on style ──────────────────────────────────────────
        if estilo == "bezier":
            dx = max(abs(x1-x0)*0.5, 90)
            if jumps:
                # sample the bezier and draw with jump cuts
                STEPS = 60
                pts = []
                for i in range(STEPS+1):
                    t = i/STEPS; u = 1-t
                    px = u**3*x0 + 3*u**2*t*(x0+dx) + 3*u*t**2*(x1-dx) + t**3*x1
                    py = u**3*y0 + 3*u**2*t*y0       + 3*u*t**2*y1       + t**3*y1
                    pts.append((px, py))
                draw_segments_with_jumps(pts)
            else:
                cr.move_to(x0, y0)
                cr.curve_to(x0+dx, y0, x1-dx, y1, x1, y1)
                cr.stroke()
            arrow_right  = (x1 >= x0)
            arrow_angle  = 0.0 if arrow_right else math.pi

        elif estilo == "recto":
            mx = (x0 + x1) / 2
            pts = [(x0, y0), (mx, y0), (mx, y1), (x1, y1)]
            draw_segments_with_jumps(pts)
            arrow_right = (x1 >= x0)
            arrow_angle = 0.0 if arrow_right else math.pi

        else:  # directo
            draw_segments_with_jumps([(x0, y0), (x1, y1)])
            arrow_angle = math.atan2(y1-y0, x1-x0)

        # ── arrowhead (filled triangle) ──────────────────────────────────────
        SZ = 9
        tip_x, tip_y = x1, y1
        base_x = tip_x - SZ * math.cos(arrow_angle)
        cr.move_to(tip_x, tip_y)
        cr.line_to(base_x - SZ*0.45*math.sin(arrow_angle),
                   tip_y  + SZ*0.45*math.cos(arrow_angle))
        cr.line_to(base_x + SZ*0.45*math.sin(arrow_angle),
                   tip_y  - SZ*0.45*math.cos(arrow_angle))
        cr.close_path()
        cr.set_source_rgba(*arrow_rgba)
        cr.fill()

        # ── cable label at both endpoints ────────────────────────────────────
        if conn["nombre"]:
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(8)
            lbl = conn["nombre"]
            ext = cr.text_extents(lbl)
            pad = 2

            for lx, ly, align in (
                (x0 + 10, y0 - 9, "left"),
                (x1 - 10, y1 - 9, "right"),
            ):
                if align == "right":
                    tx = lx - ext.width - ext.x_bearing
                else:
                    tx = lx - ext.x_bearing
                ty = ly - ext.height/2 - ext.y_bearing
                cr.set_source_rgba(*self.C_BG, 0.80)
                cr.rectangle(tx + ext.x_bearing - pad,
                             ty + ext.y_bearing - pad,
                             ext.width + 2*pad, ext.height + 2*pad)
                cr.fill()
                cr.set_source_rgba(*lbl_rgba, 0.95)
                cr.move_to(tx, ty)
                cr.show_text(lbl)

    def _draw_badge_critico(self, cr, x, y):
        """Badge 'equipo crítico de la cadena' (ver Modelo.marcar_equipos_
        criticos / botón '⭐ Marcar críticos'): ícono PNG propio (círculo
        dorado con estrella) en la esquina SUPERIOR IZQUIERDA de la
        cabecera del nodo (a propósito en la esquina opuesta a cualquier
        otro badge existente, ej. 'tiene regla lógica', para que no se
        superpongan).

        Antes se dibujaba con el glifo unicode '★', que en algunas
        fuentes/plataformas no tiene glifo y se veía como un cuadrado
        vacío dentro del círculo. Ahora se usa un PNG transparente propio
        (assets/icono_critico.png) para que se vea igual en cualquier
        equipo."""
        diam = 14  # diámetro del badge en px de pantalla
        bx, by = x + 3, y + 3
        surface = _icono_critico_surface()
        if surface is not None:
            iw, ih = surface.get_width(), surface.get_height()
            escala = diam / max(iw, ih)
            cr.save()
            cr.translate(bx, by)
            cr.scale(escala, escala)
            cr.set_source_surface(surface, 0, 0)
            cr.paint()
            cr.restore()
        else:
            # Fallback si el PNG no está disponible: círculo dorado liso
            # (sin glifo de texto, para no repetir el problema original).
            r = diam / 2
            cr.arc(bx + r, by + r, r, 0, 2 * math.pi)
            cr.set_source_rgba(1.0, 0.82, 0.15, 0.95)
            cr.fill()
            cr.set_source_rgba(0, 0, 0, 0.5)
            cr.set_line_width(1)
            cr.arc(bx + r, by + r, r, 0, 2 * math.pi)
            cr.stroke()

    def _draw_wire_en_progreso(self, cr, x0, y0, x1, y1):
        """Curva Bézier "elástica" desde el puerto donde arrancó el
        arrastre hasta la posición actual del cursor (coords mundo) —
        feedback visual mientras se crea una conexión nueva arrastrando de
        un puerto a otro."""
        dx = abs(x1 - x0) * 0.5 + 60
        cr.set_source_rgba(0.98, 0.85, 0.20, 0.95)
        cr.set_line_width(2.2 / self._zoom)
        cr.move_to(x0, y0)
        cr.curve_to(x0 + dx, y0, x1 - dx, y1, x1, y1)
        cr.stroke()
        # puntito en el extremo libre, para que se note dónde "engancha"
        cr.arc(x1, y1, self.PORT_R * 0.8, 0, 6.2832)
        cr.fill()

    def _draw_minimap(self, cr, W, H):
        geo = self._minimap_geom(W, H)
        self._minimap_rect = geo
        if not geo:
            return
        mx, my, mw, mh, mn_x, mn_y, escala, off_x, off_y = geo

        # fondo
        cr.set_source_rgba(0.05, 0.05, 0.07, 0.88)
        _rrect(cr, mx, my, mw, mh, 6); cr.fill()
        cr.set_source_rgba(0.45, 0.48, 0.58, 0.90)
        cr.set_line_width(1.2)
        _rrect(cr, mx, my, mw, mh, 6); cr.stroke()

        # pixeles de equipos (sin cables)
        for nodo in self._nodos.values():
            cx = nodo["x"] + nodo["ancho"] / 2
            cy = nodo["y"] + nodo["alto"]  / 2
            px = off_x + (cx - mn_x) * escala
            py = off_y + (cy - mn_y) * escala
            r, g, b = nodo["color"]
            cr.set_source_rgb(r, g, b)
            cr.rectangle(px - 1.5, py - 1.5, 3, 3)
            cr.fill()

        # rectángulo del viewport actual
        vw0, vh0 = self._s2w(0, 0)
        vw1, vh1 = self._s2w(W, H)
        vx = off_x + (vw0 - mn_x) * escala
        vy = off_y + (vh0 - mn_y) * escala
        vw = (vw1 - vw0) * escala
        vh = (vh1 - vh0) * escala
        cr.set_source_rgba(1.0, 0.85, 0.10, 0.85)
        cr.set_line_width(1.3)
        cr.rectangle(vx, vy, vw, vh); cr.stroke()

        # etiqueta
        cr.set_source_rgba(0.75, 0.78, 0.85, 0.90)
        cr.select_font_face("Sans", 0, 0); cr.set_font_size(9)
        cr.move_to(mx + 6, my + 12)
        cr.show_text("mapa")

    def _minimap_geom(self, W, H):
        """Geometría del minimapa: (mx,my,mw,mh,mn_x,mn_y,escala,off_x,off_y)
        o None si no aplica (vista contextual o sin nodos)."""
        if self._id_inicio is not None or not self._nodos:
            return None
        mw, mh = self.MINIMAP_W, self.MINIMAP_H
        mx = W - mw - self.MINIMAP_MARGIN
        my = H - mh - self.MINIMAP_MARGIN
        if mx < 0 or my < 0:
            return None

        xs  = [n["x"] for n in self._nodos.values()]
        ys  = [n["y"] for n in self._nodos.values()]
        x2s = [n["x"] + n["ancho"] for n in self._nodos.values()]
        y2s = [n["y"] + n["alto"]  for n in self._nodos.values()]
        mn_x, mn_y = min(xs) - 60, min(ys) - 60
        mx_x, mx_y = max(x2s) + 60, max(y2s) + 60
        cw = max(1.0, mx_x - mn_x)
        ch = max(1.0, mx_y - mn_y)
        escala = min(mw / cw, mh / ch)
        off_x  = mx + (mw - cw * escala) / 2
        off_y  = my + (mh - ch * escala) / 2
        return (mx, my, mw, mh, mn_x, mn_y, escala, off_x, off_y)

    def _calc_fan_offsets(self):
        """Return {conn_id: (src_dy, dst_dy)} vertical offsets to fan cables apart.

        In solo-nombre mode all cables of a node share the same X anchor, so we
        spread them vertically.  In full mode we only fan cables that share the
        exact same port (i.e. multiple cables on one connector – rare but
        possible).
        """
        FAN_STEP = 14   # pixels between adjacent cables

        # key → list of conn ids in order of appearance
        from collections import defaultdict
        src_groups = defaultdict(list)
        dst_groups = defaultdict(list)

        for conn in self._conns:
            src = self._nodos.get(conn["src_eq"])
            dst = self._nodos.get(conn["dst_eq"])
            if not src or not dst:
                continue
            if self._solo_nombre:
                src_key = conn["src_eq"]
                dst_key = conn["dst_eq"]
            else:
                src_key = (conn["src_eq"], conn["src_con"])
                dst_key = (conn["dst_eq"], conn["dst_con"])
            src_groups[src_key].append(conn["id"])
            dst_groups[dst_key].append(conn["id"])

        offsets = {}  # conn_id → (src_dy, dst_dy)

        def spread(group_list):
            n = len(group_list)
            total = (n - 1) * FAN_STEP
            for i, cid in enumerate(group_list):
                dy = -total / 2 + i * FAN_STEP
                if cid not in offsets:
                    offsets[cid] = [0, 0]
                offsets[cid][0] = dy   # src_dy

        def spread_dst(group_list):
            n = len(group_list)
            total = (n - 1) * FAN_STEP
            for i, cid in enumerate(group_list):
                dy = -total / 2 + i * FAN_STEP
                if cid not in offsets:
                    offsets[cid] = [0, 0]
                offsets[cid][1] = dy   # dst_dy

        for group in src_groups.values():
            if len(group) > 1:
                spread(group)
        for group in dst_groups.values():
            if len(group) > 1:
                spread_dst(group)

        return offsets

    # ── conexiones incompletas ─────────────────────────────────────────────
    def _calc_jump_points(self, fan_offsets):
        """Return {conn_id: list of (ix, iy, angle)} jump arcs.
        Only cables belonging to the selected node get jump arcs, computed
        against all other cables that cross them."""
        from collections import defaultdict

        # sample all paths
        samples = {}
        for conn in self._conns:
            pts = self._sample_path(conn, fan_offsets)
            if len(pts) >= 2:
                samples[conn["id"]] = pts

        # cables of selected node (they will be drawn "on top" / get arcs)
        if self._sel_id:
            sel_ids = {c["id"] for c in self._conns
                       if c["src_eq"] == self._sel_id or c["dst_eq"] == self._sel_id}
        else:
            sel_ids = set(samples.keys())   # fallback: all cables

        other_ids = [cid for cid in samples if cid not in sel_ids]

        jumps = defaultdict(list)   # conn_id → [(ix, iy, angle)]

        for id_s in sel_ids:
            pts_s = samples.get(id_s)
            if not pts_s: continue
            for id_o in other_ids:
                pts_o = samples.get(id_o)
                if not pts_o: continue
                for si in range(len(pts_s) - 1):
                    for oi in range(len(pts_o) - 1):
                        res = self._seg_intersect(
                            pts_s[si], pts_s[si+1],
                            pts_o[oi], pts_o[oi+1])
                        if res:
                            _, _, ix, iy = res
                            # El arco debe seguir la dirección de ESTE
                            # propio cable (pts_s) en el punto de cruce,
                            # no la del cable que lo cruza. Así pin/pout
                            # (los puntos donde se corta la línea, a
                            # distancia JUMP_R sobre pts_s) caen
                            # exactamente sobre los extremos del
                            # semicírculo dibujado en draw_segments_with_jumps.
                            ddx = pts_s[si+1][0] - pts_s[si][0]
                            ddy = pts_s[si+1][1] - pts_s[si][1]
                            ang = math.atan2(ddy, ddx)
                            jumps[id_s].append((ix, iy, ang))

        # deduplicate nearby points (within 8px)
        result = {}
        for cid, pts in jumps.items():
            deduped = []
            for p in sorted(pts, key=lambda q: q[0]):
                if not deduped or math.hypot(p[0]-deduped[-1][0],
                                             p[1]-deduped[-1][1]) > 8:
                    deduped.append(p)
            result[cid] = deduped
        return result

    @staticmethod
    def _seg_intersect(p1, p2, p3, p4):
        """Return (t, u) params if segments p1-p2 and p3-p4 intersect, else None.
        t ∈ (0,1) means intersection is strictly inside seg1;
        u ∈ (0,1) means inside seg2."""
        x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-9:
            return None
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        u = -((x1-x2)*(y1-y3) - (y1-y2)*(x1-x3)) / denom
        EPS = 0.02
        if EPS < t < 1-EPS and EPS < u < 1-EPS:
            ix = x1 + t*(x2-x1)
            iy = y1 + t*(y2-y1)
            return (t, u, ix, iy)
        return None

    def _calc_conn_colors(self):
        """Return {conn_id: (r,g,b)} for cables connected to the selected node.
        Colors are evenly distributed around the HSV hue wheel, vivid and distinct.
        Se fusiona con self._riesgo_senal_conn_colors() (plan_riesgo_senal_
        audio.md) cuando ese toggle está activo — el color de riesgo tiene
        prioridad sobre el de selección, para que se vea aunque haya un
        nodo seleccionado."""
        import colorsys
        colors = {}
        if self._sel_id:
            sel_conns = [c for c in self._conns
                         if c["src_eq"] == self._sel_id or c["dst_eq"] == self._sel_id]
            n = len(sel_conns)
            for i, conn in enumerate(sel_conns):
                hue = i / n
                r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
                colors[conn["id"]] = (r, g, b)
        colors.update(self._riesgo_senal_conn_colors())
        return colors

    def _sample_path(self, conn, fan_offsets):
        """Return list of (x,y) world points approximating this connection's path."""
        src = self._nodos.get(conn["src_eq"])
        dst = self._nodos.get(conn["dst_eq"])
        if not src or not dst:
            return []
        off = fan_offsets.get(conn["id"], [0, 0]) if fan_offsets else [0, 0]
        src_dy, dst_dy = off[0], off[1]

        if conn["src_con"] and not self._solo_nombre:
            x0, y0 = self._port_pos(src, conn["src_con"], "out")
        else:
            x0 = src["x"] + src["ancho"]
            y0 = src["y"] + src["alto"] / 2
        y0 += src_dy

        if conn["dst_con"] and not self._solo_nombre:
            x1, y1 = self._port_pos(dst, conn["dst_con"], "in")
        else:
            x1 = dst["x"]
            y1 = dst["y"] + dst["alto"] / 2
        y1 += dst_dy

        estilo = self._estilo_conn
        if estilo == "bezier":
            dx = max(abs(x1 - x0) * 0.5, 90)
            pts = []
            STEPS = 40
            for i in range(STEPS + 1):
                t = i / STEPS
                u = 1 - t
                px = u**3*x0 + 3*u**2*t*(x0+dx) + 3*u*t**2*(x1-dx) + t**3*x1
                py = u**3*y0 + 3*u**2*t*y0       + 3*u*t**2*y1       + t**3*y1
                pts.append((px, py))
            return pts
        elif estilo == "recto":
            mx = (x0 + x1) / 2
            return [(x0, y0), (mx, y0), (mx, y1), (x1, y1)]
        else:  # directo
            return [(x0, y0), (x1, y1)]

    def _draw_conexion_interna(self, cr):
        """Dibuja (en coords de mundo, dentro del cr.save()/scale() de
        _on_draw) las líneas punteadas de la conexión interna, si está activa."""
        if not self._conex_interna_activo or not self._conex_interna_estado:
            return
        nodo = self._nodos.get(self._conex_interna_id)
        if not nodo:
            return

        estado = self._conex_interna_estado

        if estado.get("modo") == "ddv":
            self._draw_conexion_interna_ddv(cr, nodo, estado)
            return

        if estado.get("modo") == "matriz":
            self._draw_conexion_interna_matriz(cr, nodo, estado)
            return

        puertos = estado["puertos"]

        cr.save()
        cr.set_dash([7.0, 5.0])
        cr.set_line_width(3.0)
        colores_tramo = {
            ("BACK_ENTRADA", "BACK_SALIDA"):     (1.00, 0.82, 0.15),   # ámbar — bypass directo
            ("BACK_ENTRADA", "FRONT_DERIVACION"): (0.25, 0.85, 0.35),   # verde  — derivación al frente
            ("FRONT_INSERCION", "BACK_SALIDA"):   (0.30, 0.60, 0.98),   # celeste — inserción al frente
        }
        for pref_a, pref_b in estado["tramos"]:
            cid_a, side_a = puertos[pref_a]
            cid_b, side_b = puertos[pref_b]
            x0, y0 = self._port_pos(nodo, cid_a, side_a)
            x1, y1 = self._port_pos(nodo, cid_b, side_b)
            r, g, b = colores_tramo.get((pref_a, pref_b), (1.0, 0.82, 0.15))
            cr.set_source_rgba(r, g, b, 0.95)
            cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
        cr.set_dash([])

        if estado["muerto"]:
            cid_m, side_m = puertos[estado["muerto"]]
            mx, my = self._port_pos(nodo, cid_m, side_m)
            cr.set_source_rgba(0.90, 0.20, 0.20, 0.95)
            cr.set_line_width(2.5)
            s6 = 7
            cr.move_to(mx - s6, my - s6); cr.line_to(mx + s6, my + s6); cr.stroke()
            cr.move_to(mx + s6, my - s6); cr.line_to(mx - s6, my + s6); cr.stroke()
        cr.restore()

    def _draw_conexion_interna_ddv(self, cr, nodo, estado):
        """Líneas punteadas del IN hacia cada OUT con cable (distribuidor DDV)."""
        cid_in, side_in = estado["in_port"]
        x0, y0 = self._port_pos(nodo, cid_in, side_in)

        cr.save()
        cr.set_dash([7.0, 5.0])
        cr.set_line_width(2.5)
        cr.set_source_rgba(0.35, 0.85, 0.95, 0.95)   # celeste — señal distribuida
        for cid_out, side_out in estado["out_ports"]:
            x1, y1 = self._port_pos(nodo, cid_out, side_out)
            cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
        cr.set_dash([])

        # Marca el punto de origen (IN)
        cr.set_source_rgba(0.35, 0.85, 0.95, 1.0)
        cr.arc(x0, y0, 5, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

    def _draw_conexion_interna_matriz(self, cr, nodo, estado):
        """Líneas punteadas de cada entrada usada hacia sus salidas asignadas
        (matriz N×N). Las salidas que comparten la misma entrada comparten
        color de línea."""
        cr.save()
        cr.set_dash([7.0, 5.0])
        cr.set_line_width(2.5)
        for grupo in estado["grupos"]:
            cid_in, side_in = grupo["in_port"]
            x0, y0 = self._port_pos(nodo, cid_in, side_in)
            r, g, b = grupo["color"]
            cr.set_source_rgba(r, g, b, 0.95)
            for cid_out, side_out in grupo["out_ports"]:
                x1, y1 = self._port_pos(nodo, cid_out, side_out)
                cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
        cr.set_dash([])

        for grupo in estado["grupos"]:
            cid_in, side_in = grupo["in_port"]
            x0, y0 = self._port_pos(nodo, cid_in, side_in)
            r, g, b = grupo["color"]
            cr.set_source_rgba(r, g, b, 1.0)
            cr.arc(x0, y0, 5, 0, 2 * math.pi)
            cr.fill()
        cr.restore()

    # ── BUSCADOR ──────────────────────────────────────────────────────────────

    def _dibujar_icono_conexion_incompleta(self, cr, x, y, tam=34):
        """Dibuja el PNG de extremo pendiente; tiene fallback Cairo seguro."""
        if self._icono_conexion_incompleta is None:
            ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "conexion_incompleta.png")
            try:
                self._icono_conexion_incompleta = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    ruta, tam, tam, True)
            except Exception:
                self._icono_conexion_incompleta = False
        if self._icono_conexion_incompleta:
            Gdk.cairo_set_source_pixbuf(
                cr, self._icono_conexion_incompleta, x - tam / 2, y - tam / 2)
            cr.paint()
            return

        # Si una instalación perdió el asset, el diagrama sigue siendo útil.
        cr.save()
        cr.translate(x, y)
        cr.set_source_rgba(1.0, 0.48, 0.08, 0.95)
        cr.move_to(-tam * .34, tam * .38)
        cr.line_to(tam * .34, tam * .38)
        cr.line_to(tam * .20, -tam * .38)
        cr.line_to(-tam * .20, -tam * .38)
        cr.close_path(); cr.fill()
        cr.set_source_rgb(1, 1, 1); cr.set_line_width(2)
        cr.move_to(0, -tam * .22); cr.line_to(0, tam * .12); cr.stroke()
        cr.arc(0, tam * .23, 1.5, 0, math.tau); cr.fill()
        cr.restore()

    def _draw_conexiones_extension(self, cr):
        """Dibuja los tramos de cable que atraviesan extension_cable (Fase
        3 de plan_desarrollo_extension_cable.md): un rombo pequeño en cada
        punto de empalme, para que se vea como un nodo intermedio real en
        el trazado (no como si el cable terminara en la nada), mostrando
        cada tramo físico por separado en vez de colapsar la cadena en un
        único segmento. Capa aparte de _draw_conn — ver
        _construir_conexiones_extension en grafo_diagrama_ui.py — así que
        recalcula las posiciones en cada frame a partir de la posición
        ACTUAL de los dos nodos reales de la cadena (sigue el arrastre de
        nodos igual que las conexiones normales, sin necesitar invalidar
        nada aparte)."""
        cadenas = getattr(self, "_conns_extension", None)
        if not cadenas:
            return

        for cadena in cadenas:
            nodo_a = self._nodos.get(cadena["id_eq_a"])
            nodo_b = self._nodos.get(cadena["id_eq_b"])
            if not nodo_a or not nodo_b:
                continue
            pax, pay = self._port_pos(nodo_a, cadena["con_a"], cadena["lado_a"])
            pbx, pby = self._port_pos(nodo_b, cadena["con_b"], cadena["lado_b"])

            n = len(cadena["cables"])
            puntos = [(pax, pay)]
            for i in range(1, n):
                t = i / n
                puntos.append((pax + (pbx - pax) * t, pay + (pby - pay) * t))
            puntos.append((pbx, pby))

            cr.set_line_width(1.4)
            cr.set_source_rgba(*self.C_CONN, 0.55)
            cr.set_dash([5, 3])
            for i in range(n):
                (x0, y0), (x1, y1) = puntos[i], puntos[i + 1]
                cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
            cr.set_dash([])

            R = 6
            for i, id_ext in enumerate(cadena["extensiones"], start=1):
                x, y = puntos[i]
                cr.save()
                cr.translate(x, y)
                cr.rotate(math.pi / 4)
                cr.rectangle(-R, -R, R * 2, R * 2)
                cr.restore()
                cr.set_source_rgb(*self.C_NODE)
                cr.fill_preserve()
                cr.set_source_rgb(*self.C_NODE_B)
                cr.set_line_width(1.2)
                cr.stroke()

                etiqueta = f"{_('Extensión')} #{id_ext}"
                cr.select_font_face("Sans", 0, 0)
                cr.set_font_size(9)
                cr.set_source_rgb(*self.C_TXT_SUB)
                te = cr.text_extents(etiqueta)
                cr.move_to(x - te.width / 2, y - R - 4)
                cr.show_text(etiqueta)

    def _draw_conexiones_incompletas(self, cr):
        """Extensiones visuales para puertos IN/OUT con cable de una sola punta.

        Dibuja la lista que corresponda según qué modo esté activo: "todas"
        (todos los equipos visibles del diagrama) tiene prioridad si está
        activo — son mutuamente excluyentes por diseño (ver
        _on_toggle_conexiones_incompletas / _on_toggle_todas_conexiones_incompletas)
        — y si no, la variante clásica por equipo seleccionado.
        """
        if self._solo_nombre:
            return
        if self._todas_conexiones_incompletas_activo:
            lista = self._todas_conexiones_incompletas
        elif self._conexiones_incompletas_activo:
            lista = self._conexiones_incompletas
        else:
            return
        if not lista:
            return
        # Primera pasada: líneas punteadas + iconos (por debajo de los nodos,
        # que se dibujan después en el pipeline normal). El escalonado
        # vertical se cuenta por nodo (no globalmente): en el modo "todas"
        # la lista mezcla conexiones de equipos distintos, y lo que importa
        # para separar los extremos es cuántos pendientes tiene ESE equipo,
        # no la posición dentro de la lista completa.
        contador_por_nodo = {}
        geoms = []
        for conn in lista:
            id_eq = conn.get("id_equipo")
            nodo = self._nodos.get(id_eq)
            if not nodo:
                continue
            indice = contador_por_nodo.get(id_eq, 0)
            contador_por_nodo[id_eq] = indice + 1
            lado = conn.get("lado", "in")
            x0, y0 = self._port_pos(nodo, conn["conector"], lado)

            etiqueta = conn["nombre"] or f"Cable {conn['id']}"
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(8)
            ext = cr.text_extents(etiqueta)
            # El tramo sale hacia afuera del equipo: a la izquierda para un
            # puerto IN (aguas arriba) y a la derecha para un puerto OUT
            # (aguas abajo). Se escalonan levemente los extremos para que
            # dos pendientes sobre puertos cercanos no oculten sus iconos
            # ni sus etiquetas. El largo del tramo se adapta al ancho del
            # texto para que la etiqueta siempre entre completa.
            signo = -1 if lado == "in" else 1
            largo = max(115, ext.width + 40)
            x1 = x0 + signo * largo
            y1 = y0 + (indice % 2) * 12 - 6

            cr.save()
            cr.set_source_rgba(1.0, 0.53, 0.10, 0.92)
            cr.set_line_width(2.2)
            cr.set_dash([7, 5], 0)
            cr.move_to(x0, y0); cr.line_to(x1, y1); cr.stroke()
            cr.set_dash([], 0)
            cr.restore()

            self._dibujar_icono_conexion_incompleta(cr, x1, y1)
            geoms.append((etiqueta, ext, x0, y0, x1, y1))

        # Las etiquetas se guardan y se dibujan aparte (ver
        # _draw_conexiones_incompletas_etiquetas), que se llama más tarde en
        # el pipeline —  después de los nodos — para que el texto quede
        # siempre por encima de líneas, iconos PNG y nodos.
        self._conexiones_incompletas_geoms = geoms

    def _draw_conexiones_incompletas_etiquetas(self, cr):
        """Dibuja solo las etiquetas de texto de las conexiones incompletas.

        Se llama después de dibujar los nodos (ver `_on_draw` y las rutinas
        de exportación) para que el texto no quede tapado por nodos, iconos
        PNG ni las líneas punteadas.
        """
        geoms = getattr(self, "_conexiones_incompletas_geoms", None)
        if not geoms:
            return
        for etiqueta, ext, x0, y0, x1, y1 in geoms:
            cr.save()
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(8)
            tx, ty = (x0 + x1) / 2 - ext.width / 2, (y0 + y1) / 2 - 8
            cr.set_source_rgba(*self.C_BG, .92)
            cr.rectangle(tx - 3, ty - ext.height - 3, ext.width + 6, ext.height + 6)
            cr.fill()
            cr.set_source_rgba(1.0, .72, .26, 1.0)
            cr.move_to(tx - ext.x_bearing, ty); cr.show_text(etiqueta)
            cr.restore()
        self._conexiones_incompletas_geoms = []

    def _on_toggle_conexiones_incompletas(self, btn):
        """Activa el complemento visual de cables con una sola punta.

        La vista CONEXIONES contiene una fila por punta real de cable. Un
        cable cuyo id aparece una sola vez está documentado en un extremo,
        pero todavía no tiene registrado el equipo/conector del otro. Se
        buscan tanto entradas como salidas del equipo primario seleccionado:
        el tramo se dibuja hacia afuera del equipo (izquierda para IN,
        derecha para OUT) y termina en el cono de ``extremo pendiente de
        relevar``.
        """
        self._conexiones_incompletas_activo = btn.get_active()
        # Mutuamente excluyente con la variante "todas": activar ésta apaga
        # la otra para no dibujar los mismos tramos dos veces. set_active
        # dispara su propio "toggled", que ya limpia
        # _todas_conexiones_incompletas / _todas_conexiones_incompletas_activo.
        if self._conexiones_incompletas_activo and self._chk_todas_conexiones_incompletas.get_active():
            self._chk_todas_conexiones_incompletas.set_active(False)
        self._actualizar_conexiones_incompletas(mostrar_estado=True)
        self._da.queue_draw()

    def _actualizar_conexiones_incompletas(self, mostrar_estado=False):
        self._conexiones_incompletas = []
        if not self._conexiones_incompletas_activo or not self._sel_id:
            if mostrar_estado and self._conexiones_incompletas_activo:
                self._status("Seleccioná un equipo para ver sus conexiones incompletas.")
            return

        # La consulta parte expresamente de la vista CONEXIONES; el JOIN a
        # tipo_conector aporta la dirección canónica IN/OUT del conector.
        # El conteo correlacionado evita depender de la vista de dos
        # extremos, que por definición no contiene cables incompletos. Ya
        # no se filtra por dirección acá: se buscan tanto entradas como
        # salidas, y el lado (in/out) queda resuelto contra los puertos
        # reales del nodo para decidir hacia qué lado dibujar el tramo.
        filas = Modelo._query(
            "SELECT v.id_cable, v.cable_codigo, v.id_conector "
            "FROM CONEXIONES v "
            "JOIN conector c ON c.id_conector=v.id_conector "
            "WHERE v.id_equipo=? "
            "  AND (SELECT COUNT(*) FROM conexion cx "
            "       WHERE cx.id_cable=v.id_cable)=1 "
            "ORDER BY v.cable_codigo, v.id_cable",
            (self._sel_id,))
        nodo_sel = self._nodos.get(self._sel_id, {})
        ids_in = {cid for cid, _nombre, _orden in nodo_sel.get("in", [])}
        ids_out = {cid for cid, _nombre, _orden in nodo_sel.get("out", [])}
        conexiones = []
        for id_cable, codigo, id_conector in filas:
            cid = str(id_conector)
            if cid in ids_in:
                lado = "in"
            elif cid in ids_out:
                lado = "out"
            else:
                continue
            conexiones.append({
                "id": str(id_cable), "nombre": s(codigo),
                "conector": cid, "lado": lado, "id_equipo": self._sel_id,
            })
        self._conexiones_incompletas = conexiones
        if mostrar_estado:
            cantidad = len(self._conexiones_incompletas)
            self._status(
                f"{cantidad} {'conexión incompleta' if cantidad == 1 else 'conexiones incompletas'} "
                f"en «{self._nodos.get(self._sel_id, {}).get('nombre', self._sel_id)}»")

    def _on_toggle_todas_conexiones_incompletas(self, btn):
        """Variante "todas": igual que `_on_toggle_conexiones_incompletas`
        pero sin depender del equipo seleccionado — recorre TODOS los
        equipos actualmente visibles en el diagrama (`self._nodos`).
        """
        self._todas_conexiones_incompletas_activo = btn.get_active()
        # Mutuamente excluyente con la variante "por equipo seleccionado":
        # ver comentario simétrico en _on_toggle_conexiones_incompletas.
        if self._todas_conexiones_incompletas_activo and self._chk_conexiones_incompletas.get_active():
            self._chk_conexiones_incompletas.set_active(False)
        self._actualizar_todas_conexiones_incompletas(mostrar_estado=True)
        self._da.queue_draw()

    def _actualizar_todas_conexiones_incompletas(self, mostrar_estado=False):
        """Igual que `_actualizar_conexiones_incompletas`, pero calcula la
        lista para TODOS los equipos visibles en el diagrama en una sola
        consulta (con `id_equipo IN (...)`), en vez de uno solo.
        """
        self._todas_conexiones_incompletas = []
        if not self._todas_conexiones_incompletas_activo or not self._nodos:
            if mostrar_estado and self._todas_conexiones_incompletas_activo:
                self._status("No hay equipos visibles en el diagrama.")
            return

        ids_equipos = list(self._nodos.keys())
        placeholders = ",".join("?" * len(ids_equipos))
        # Misma consulta base que la variante por equipo (ver comentario
        # ahí), pero sin fijar id_equipo=? — se trae de una sola vez el
        # universo completo de cables incompletos de los equipos visibles.
        filas = Modelo._query(
            "SELECT v.id_equipo, v.id_cable, v.cable_codigo, v.id_conector "
            "FROM CONEXIONES v "
            "JOIN conector c ON c.id_conector=v.id_conector "
            f"WHERE v.id_equipo IN ({placeholders}) "
            "  AND (SELECT COUNT(*) FROM conexion cx "
            "       WHERE cx.id_cable=v.id_cable)=1 "
            "ORDER BY v.id_equipo, v.cable_codigo, v.id_cable",
            tuple(ids_equipos))

        conexiones = []
        for id_equipo, id_cable, codigo, id_conector in filas:
            id_eq = str(id_equipo)
            nodo_eq = self._nodos.get(id_eq)
            if not nodo_eq:
                continue
            cid = str(id_conector)
            ids_in  = {c for c, _n, _o in nodo_eq.get("in", [])}
            ids_out = {c for c, _n, _o in nodo_eq.get("out", [])}
            if cid in ids_in:
                lado = "in"
            elif cid in ids_out:
                lado = "out"
            else:
                continue
            conexiones.append({
                "id": str(id_cable), "nombre": s(codigo),
                "conector": cid, "lado": lado, "id_equipo": id_eq,
            })
        self._todas_conexiones_incompletas = conexiones
        if mostrar_estado:
            cantidad = len(self._todas_conexiones_incompletas)
            n_equipos = len({c["id_equipo"] for c in conexiones})
            self._status(
                f"{cantidad} {'conexión incompleta' if cantidad == 1 else 'conexiones incompletas'} "
                f"en {n_equipos} {'equipo' if n_equipos == 1 else 'equipos'} del diagrama")


