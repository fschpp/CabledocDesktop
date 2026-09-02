#!/usr/bin/env python3
"""
rack_ui.py — CableDoc GTK3

Entrega 2 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md). Move 1:1, sin cambio de lógica:

  VistaRack         vista semi-gráfica de un rack (segmentos, slots, frames)
  abrir_vista_rack  función de conveniencia

Columnas de CONEXIONES_AMBOS_EXTREMOS (WHERE id_equipo = X):
  0  Cable                   1  EA: equipo (= el CONECTADO)
  3  EA: conector            5  EB: Equipo (= el CONSULTADO)
  9  id_equipo (= X)        10  id_equipo:1 (= id del CONECTADO)
"""

import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from modelo import Modelo

from pantallas_comunes import _, s, _tc, _abrev


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  VistaRack
# ═══════════════════════════════════════════════════════════════════════════════

class VistaRack(Gtk.Dialog):
    """
    Vista semi-gráfica de un rack.

    Tipos de segmento:
      equipo    → azul claro    (1 dispositivo en esas Us)
      frame     → ámbar claro   (1 frame en esas Us)
      bandeja   → verde claro   (2+ equipos comparten las mismas Us)
      libre     → gris claro    (sin asignación)

    Lógica de bandejas:
      Si varias Us consecutivas tienen exactamente el mismo conjunto de
      dispositivos (≥2), se fusionan en un único rectángulo grande.
      Etiqueta: "Bandeja: eq1, eq2, …, eqN"
    """

    U_H    = 28
    NUM_W  = 40
    RACK_W = 310

    COL_EQUIPO  = (0.78, 0.90, 0.98)
    COL_FRAME   = (1.00, 0.88, 0.68)
    COL_LIBRE   = (0.93, 0.93, 0.93)
    COL_BANDEJA = (0.68, 0.92, 0.68)   # verde claro
    COL_NUM_BG  = (0.82, 0.82, 0.82)
    COL_HEADER  = (0.15, 0.20, 0.35)

    def __init__(self, id_rack=None, parent=None):
        super().__init__(title=_("Vista de Rack"),
                         transient_for=parent,
                         destroy_with_parent=True)
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(440, 720)

        self._id_rack   = id_rack
        self._rack_info = None
        self._segmentos = []
        self._zoom      = 1.0

        area = self.get_content_area()

        # ── Selector ──────────────────────────────────────────────────────
        hb_top = Gtk.Box(spacing=6,
                         margin_start=8, margin_end=8,
                         margin_top=8,   margin_bottom=4)
        self._lbl_rack = Gtk.Label(xalign=0, hexpand=True)
        self._lbl_rack.set_markup("<i>Seleccione un rack…</i>")
        btn_sel = Gtk.Button(label=_("🗄 Elegir rack…"))
        btn_sel.connect("clicked", self._sel_rack)
        hb_top.pack_start(self._lbl_rack, True,  True,  0)
        hb_top.pack_start(btn_sel,        False, False, 0)
        area.pack_start(hb_top, False, False, 0)
        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── Zoom + leyenda ────────────────────────────────────────────────
        hbz = Gtk.Box(spacing=4,
                      margin_start=8, margin_end=8,
                      margin_top=4,   margin_bottom=4)
        self._lbl_zoom = Gtk.Label(label=_("100%"))
        hbz.pack_start(Gtk.Label(label=_("Zoom:")), False, False, 0)
        hbz.pack_start(self._lbl_zoom,            False, False, 0)
        for lbl, fn in [
            ("+",       lambda _: self._set_zoom(self._zoom * 1.20)),
            ("−",       lambda _: self._set_zoom(self._zoom / 1.20)),
            ("1:1",     lambda _: self._set_zoom(1.0)),
            (_("Ajustar"), lambda _: self._zoom_fit()),
        ]:
            b = Gtk.Button(label=lbl); b.connect("clicked", fn)
            hbz.pack_start(b, False, False, 0)

        hbz.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
                       False, False, 6)
        for texto, rgb in [
            (_("Equipo"),  self.COL_EQUIPO),
            (_("Frame"),   self.COL_FRAME),
            (_("Bandeja"), self.COL_BANDEJA),
        ]:
            da_leg = Gtk.DrawingArea()
            da_leg.set_size_request(14, 14)
            c = rgb
            da_leg.connect("draw", lambda w, cr, c=c: (
                cr.set_source_rgb(*c), cr.paint(),
                cr.set_source_rgb(0.4, 0.4, 0.4),
                cr.set_line_width(1),
                cr.rectangle(0, 0, 14, 14), cr.stroke()
            ))
            hbz.pack_start(da_leg,                   False, False, 0)
            hbz.pack_start(Gtk.Label(label=texto),   False, False, 0)
        
        # Botones de exportación
        hbz.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
                       False, False, 6)
        hbz.pack_start(Gtk.Label(label=_("Exportar:")), False, False, 0)
        btn_pdf = Gtk.Button(label=_("📄 PDF"))
        btn_pdf.connect("clicked", self._exportar_pdf)
        hbz.pack_start(btn_pdf, False, False, 0)
        btn_svg = Gtk.Button(label=_("📊 SVG"))
        btn_svg.connect("clicked", self._exportar_svg)
        hbz.pack_start(btn_svg, False, False, 0)

        area.pack_start(hbz, False, False, 0)
        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── DrawingArea ───────────────────────────────────────────────────
        self._sw = Gtk.ScrolledWindow(vexpand=True,
                                      margin_start=8, margin_end=8,
                                      margin_bottom=8)
        self._sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._da = Gtk.DrawingArea()
        self._da.connect("draw",          self._on_draw)
        self._da.set_has_tooltip(True)
        self._da.connect("query-tooltip", self._on_tooltip)
        self._da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                            Gdk.EventMask.POINTER_MOTION_MASK |
                            Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self._da.connect("button-press-event", self._on_click)
        self._da.connect("motion-notify-event", self._on_motion)
        self._da.connect("leave-notify-event", self._on_leave)
        self._cursor_mano = None
        self._sw.add(self._da)
        area.pack_start(self._sw, True, True, 0)

        self._sb = Gtk.Statusbar()
        area.pack_start(self._sb, False, False, 0)

        self.show_all()
        if id_rack:
            self._cargar(id_rack)

    # ── zoom ──────────────────────────────────────────────────────────────
    def _set_zoom(self, z):
        self._zoom = max(0.25, min(4.0, z))
        self._lbl_zoom.set_text(f"{int(self._zoom*100)}%")
        self._actualizar_size()

    def _zoom_fit(self):
        if not self._rack_info:
            return
        alloc = self._sw.get_allocation()
        _, cap = self._rack_info
        zh = alloc.height / ((1 + cap) * self.U_H)
        zw = alloc.width  / (self.NUM_W + self.RACK_W)
        self._set_zoom(min(zh, zw))

    def _actualizar_size(self):
        if self._rack_info:
            z = self._zoom
            _, cap = self._rack_info
            w = int((self.NUM_W + self.RACK_W) * z)
            h = int((1 + cap) * self.U_H * z)
            self._da.set_size_request(w, h)
        self._da.queue_draw()

    # ── selector ──────────────────────────────────────────────────────────
    def _sel_rack(self, btn):
        from cabledoc import RacksListado
        dlg = RacksListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self._cargar(dlg.resultado_id)
        dlg.destroy()

    # ── carga y construcción de segmentos ─────────────────────────────────
    def _cargar(self, id_rack):
        self._id_rack = id_rack
        rows_rack = Modelo.devolver_rack(id_rack)
        if not rows_rack:
            return
        r = rows_rack[0]
        nombre_rack = s(r[2])
        try:
            cap_u = max(1, int(r[3]))    # rack units (cantidad_maxima)
        except (TypeError, ValueError):
            cap_u = 42
        cap = cap_u * 3                  # total orificios (1 U = 3 orificios)
        self._rack_info = (nombre_rack, cap)
        self._cap_u     = cap_u           # guardado solo para el label
        self.set_title(f"Vista de Rack: {nombre_rack}")

        devs = Modelo.devolver_dispositivos_de_un_rack(id_rack)

        # ── Paso 1: u_map[u] = lista de info-dicts ────────────────────────
        u_map = {u: [] for u in range(1, cap + 1)}
        for d in devs:
            try:
                u_ini   = int(d[2]) if d[2] else 0   # ya en orificios
                ur      = int(d[5]) if d[5] else 1   # rack units
                u_count = ur * 3                      # convertir a orificios
            except (TypeError, ValueError):
                continue
            if u_ini < 1 or u_count < 1:
                continue
            info = {
                "nombre":  s(d[4]).strip() or "?",
                "inv":     s(d[3]).strip(),
                "tipo":    "frame" if (d[8] and str(d[8]).strip()
                                       not in ("", "0", "None"))
                           else "equipo",
                "u_ini":   u_ini,
                "u_count": u_count,   # en orificios
                "id_equipo": d[7] if d[7] not in (None, "", "0") else None,
                "id_frame":  d[8] if d[8] not in (None, "", "0") else None,
            }
            for u in range(u_ini, min(u_ini + u_count, cap + 1)):
                u_map[u].append(info)

        # ── Paso 2: estado por unidad ─────────────────────────────────────
        # "libre"   → 0 dispositivos
        # "single"  → 1 dispositivo
        # "bandeja" → ≥2 dispositivos (comparten la misma U física)
        def estado(u):
            n = len(u_map[u])
            if n == 0:
                return "libre"
            if n == 1:
                return "single"
            return "bandeja"

        # ── Paso 3: construir segmentos ───────────────────────────────────
        self._segmentos = []
        procesadas = set()
        u = 1

        while u <= cap:
            if u in procesadas:
                u += 1
                continue

            est = estado(u)

            # ── LIBRE ──────────────────────────────────────────────────────
            if est == "libre":
                self._segmentos.append({
                    "u_ini": u, "u_count": 1,
                    "tipo": "libre", "nombre": "", "inv": "",
                })
                procesadas.add(u)
                u += 1

            # ── BANDEJA (≥2 equipos en la misma U) ────────────────────────
            elif est == "bandeja":
                infos   = u_map[u]
                # clave: conjunto de nombres (para detectar fusiones)
                key     = frozenset(i["nombre"] for i in infos)
                u_end   = u
                while u_end + 1 <= cap:
                    nxt = u_map[u_end + 1]
                    if (len(nxt) >= 2 and
                            frozenset(i["nombre"] for i in nxt) == key):
                        u_end += 1
                    else:
                        break

                # nombres ordenados (sin duplicados)
                nombres = list(dict.fromkeys(i["nombre"] for i in infos))
                # items: uno por dispositivo distinto, con su tipo e id,
                # para poder abrir el detalle correspondiente al hacer clic
                items = []
                vistos = set()
                for i in infos:
                    if i["nombre"] in vistos:
                        continue
                    vistos.add(i["nombre"])
                    id_item = i["id_frame"] if i["tipo"] == "frame" else i["id_equipo"]
                    items.append({
                        "nombre": i["nombre"],
                        "tipo":   i["tipo"],
                        "id":     id_item,
                    })
                self._segmentos.append({
                    "u_ini":   u,
                    "u_count": u_end - u + 1,
                    "tipo":    "bandeja",
                    "nombre":  nombres,   # lista para truncar al dibujar
                    "inv":     "",
                    "items":   items,     # detalle clicable por dispositivo
                })
                for uu in range(u, u_end + 1):
                    procesadas.add(uu)
                u = u_end + 1

            # ── SINGLE (1 equipo/frame) ────────────────────────────────────
            else:
                main    = u_map[u][0]
                u_ini_d = main["u_ini"]
                u_end_d = min(u_ini_d + main["u_count"] - 1, cap)

                # Avanzar sólo mientras la unidad pertenezca a este
                # dispositivo Y no esté ya procesada Y sea "single"
                actual_end = u
                for uu in range(u + 1, u_end_d + 1):
                    if uu in procesadas:
                        break
                    uu_est = estado(uu)
                    if uu_est == "single":
                        # Mismo dispositivo si el nombre coincide
                        if u_map[uu][0]["nombre"] == main["nombre"]:
                            actual_end = uu
                        else:
                            break
                    else:
                        break   # libre o bandeja → no incluir

                self._segmentos.append({
                    "u_ini":   u,
                    "u_count": actual_end - u + 1,
                    "tipo":    main["tipo"],
                    "nombre":  main["nombre"],
                    "inv":     main["inv"],
                    "id":      (main["id_frame"] if main["tipo"] == "frame"
                                else main["id_equipo"]),
                })
                for uu in range(u, actual_end + 1):
                    procesadas.add(uu)
                u = actual_end + 1

        self._segmentos.sort(key=lambda x: x["u_ini"])

        # ── Etiqueta de resumen ───────────────────────────────────────────
        n_eq  = sum(1 for sg in self._segmentos if sg["tipo"] == "equipo")
        n_fr  = sum(1 for sg in self._segmentos if sg["tipo"] == "frame")
        n_ban = sum(1 for sg in self._segmentos if sg["tipo"] == "bandeja")
        n_lib = sum(sg["u_count"]
                    for sg in self._segmentos if sg["tipo"] == "libre")
        partes = [f"<b>{nombre_rack}</b>  ({cap_u} U / {cap} orificios)  —  "]
        partes.append(f"{n_eq} equipos  {n_fr} frames  {n_lib} U libres")
        if n_ban:
            partes.append(
                f"  <span color='#1a7a1a'>■ {n_ban} bandejas</span>"
            )
        self._lbl_rack.set_markup("".join(partes))
        self._actualizar_size()

        ctx = self._sb.get_context_id("i")
        self._sb.push(ctx,
            f"Rack cargado: {len(devs)} asignaciones, "
            f"{n_eq} equipos, {n_fr} frames, {n_ban} bandejas, "
            f"{n_lib} orificios libres  (1 U = 3 orificios)")

    # ── tooltip ───────────────────────────────────────────────────────────
    def _on_tooltip(self, da, x, y, kb, tooltip):
        if not self._rack_info:
            return False
        z  = self._zoom
        UH = self.U_H * z
        NW = self.NUM_W * z
        if x < NW:
            return False
        u = int((y - UH) / UH) + 1
        if u < 1 or u > self._rack_info[1]:
            return False
        for sg in self._segmentos:
            if sg["u_ini"] <= u < sg["u_ini"] + sg["u_count"]:
                if sg["tipo"] == "libre":
                    tooltip.set_text(f"U{u} — LIBRE")
                elif sg["tipo"] == "bandeja":
                    rng  = (f"U{sg['u_ini']}"
                            if sg["u_count"] == 1
                            else f"U{sg['u_ini']}–{sg['u_ini']+sg['u_count']-1}")
                    nombres = sg["nombre"]  # lista
                    tooltip.set_text(
                        rng + "  [Bandeja compartida]\n" +
                        "\n".join(f"  • {n}" for n in nombres)
                    )
                else:
                    rng = (f"U{sg['u_ini']}"
                           if sg["u_count"] == 1
                           else f"U{sg['u_ini']}–{sg['u_ini']+sg['u_count']-1}")
                    txt = f"{rng}\n{sg['nombre']}"
                    if sg["inv"]:
                        txt += f"\nInv: {sg['inv']}"
                    tooltip.set_text(txt)
                return True
        return False

    # ── click → detalle de equipo / frame ───────────────────────────────────
    def _segmento_en_xy(self, x, y):
        """Devuelve el segmento bajo las coordenadas (x, y) del DrawingArea,
        o None si cae fuera del cuerpo del rack (columna de números, etc.)."""
        if not self._rack_info:
            return None
        z  = self._zoom
        UH = self.U_H * z
        NW = self.NUM_W * z
        if x < NW:
            return None
        u = int((y - UH) / UH) + 1
        if u < 1 or u > self._rack_info[1]:
            return None
        for sg in self._segmentos:
            if sg["u_ini"] <= u < sg["u_ini"] + sg["u_count"]:
                return sg
        return None

    def _on_click(self, da, event):
        if event.button != 1:
            return False
        sg = self._segmento_en_xy(event.x, event.y)
        if not sg or sg["tipo"] == "libre":
            return False
        self._abrir_detalle_segmento(sg, event)
        return True

    def _on_motion(self, da, event):
        sg = self._segmento_en_xy(event.x, event.y)
        clicable = bool(sg) and sg["tipo"] != "libre"
        win = da.get_window()
        if not win:
            return False
        if clicable:
            if self._cursor_mano is None:
                self._cursor_mano = Gdk.Cursor.new_from_name(
                    da.get_display(), "pointer")
            win.set_cursor(self._cursor_mano)
        else:
            win.set_cursor(None)
        return False

    def _on_leave(self, da, event):
        win = da.get_window()
        if win:
            win.set_cursor(None)
        return False

    def _abrir_detalle_segmento(self, sg, event=None):
        """Abre la ventana de detalle correspondiente al rectángulo
        clickeado: equipo, frame, o -en el caso de una bandeja con varios
        dispositivos compartiendo la misma U- un menú para elegir cuál."""
        tipo = sg["tipo"]
        if tipo == "bandeja":
            items = sg.get("items") or []
            items = [it for it in items if it.get("id")]
            if not items:
                return
            if len(items) == 1:
                self._abrir_detalle_item(items[0])
                return
            menu = Gtk.Menu()
            for it in items:
                icono = "🖳 " if it["tipo"] == "equipo" else "🗄 "
                mi = Gtk.MenuItem(label=icono + it["nombre"])
                mi.connect("activate",
                          lambda w, it=it: self._abrir_detalle_item(it))
                menu.append(mi)
            menu.show_all()
            if event is not None:
                menu.popup_at_pointer(event)
            else:
                menu.popup(None, None, None, None, 0,
                          Gtk.get_current_event_time())
            return
        if not sg.get("id"):
            return
        self._abrir_detalle_item({
            "tipo": tipo, "id": sg["id"], "nombre": sg.get("nombre"),
        })

    def _abrir_detalle_item(self, item):
        if not item.get("id"):
            return
        from cabledoc import _DialogoEquipo, _DialogoFrame
        if item["tipo"] == "frame":
            dlg = _DialogoFrame(id_frame=item["id"], parent=self)
        else:
            dlg = _DialogoEquipo(id_equipo=item["id"], parent=self)
        dlg.run_and_destroy()
        # refrescar la vista por si el detalle modificó nombre/inventario/etc.
        if self._id_rack:
            self._cargar(self._id_rack)

    # ── dibujo Cairo ──────────────────────────────────────────────────────
    def _on_draw(self, da, cr):
        if not self._rack_info:
            cr.set_source_rgb(0.92, 0.92, 0.92); cr.paint()
            cr.set_source_rgb(0.4, 0.4, 0.4)
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(14)
            cr.move_to(20, 40)
            cr.show_text(_("Seleccione un rack para visualizarlo"))
            return

        z  = self._zoom
        UH = self.U_H   * z
        NW = self.NUM_W * z
        RW = self.RACK_W * z
        nombre_rack, cap = self._rack_info
        total_w = NW + RW
        total_h = UH + cap * UH

        # Fondo blanco
        cr.set_source_rgb(1, 1, 1); cr.paint()

        # ── Header ────────────────────────────────────────────────────────
        cr.set_source_rgb(*self.COL_HEADER)
        cr.rectangle(0, 0, total_w, UH); cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(13 * z)
        _tc(cr, nombre_rack, total_w / 2, UH / 2)
        cr.select_font_face("Sans", 0, 0); cr.set_font_size(8 * z)
        cr.set_source_rgba(1, 1, 1, 0.50)
        ext = cr.text_extents("FRENTE")
        cr.move_to(total_w - ext.width - 6 * z, UH - 4 * z)
        cr.show_text("FRENTE")

        # ── Segmentos ──────────────────────────────────────────────────────
        for sg in self._segmentos:
            u_ini   = sg["u_ini"]
            u_count = sg["u_count"]
            tipo    = sg["tipo"]
            nombre  = sg["nombre"]   # str para equipo/frame/libre, list para bandeja
            inv     = sg.get("inv", "")

            y0 = UH + (u_ini - 1) * UH
            h  = u_count * UH

            # ── Color ──────────────────────────────────────────────────────
            if tipo == "libre":
                bg = self.COL_LIBRE;   fg = (0.50, 0.50, 0.50)
                border = (0.55, 0.55, 0.55)
            elif tipo == "frame":
                bg = self.COL_FRAME;   fg = (0.35, 0.18, 0.00)
                border = (0.65, 0.48, 0.10)
            elif tipo == "bandeja":
                bg = self.COL_BANDEJA; fg = (0.08, 0.38, 0.08)
                border = (0.15, 0.60, 0.15)
            else:   # equipo
                bg = self.COL_EQUIPO;  fg = (0.05, 0.18, 0.42)
                border = (0.30, 0.55, 0.75)

            # ── Columna de números ──────────────────────────────────────────
            for i in range(u_count):
                u_num = u_ini + i
                y_u   = UH + (u_num - 1) * UH

                cr.set_source_rgb(*self.COL_NUM_BG)
                cr.rectangle(0, y_u, NW, UH); cr.fill()

                cr.set_source_rgb(0.55, 0.55, 0.55)
                cr.set_line_width(0.5)
                cr.move_to(0, y_u + UH); cr.line_to(NW, y_u + UH); cr.stroke()

                # Orejita de rail
                ew = 5 * z; eh = UH * 0.35
                ex = NW - ew - 1; ey = y_u + (UH - eh) / 2
                cr.set_source_rgb(0.55, 0.55, 0.60)
                cr.rectangle(ex, ey, ew, eh); cr.fill()
                cr.set_source_rgb(*self.COL_NUM_BG)
                sc = 2.5 * z
                cr.arc(ex + ew/2, ey + eh/2, sc, 0, 6.2832); cr.fill()

                cr.set_source_rgb(0.20, 0.20, 0.20)
                cr.select_font_face("Sans", 0, 0)
                cr.set_font_size(max(8, 10 * z))
                _tc(cr, str(u_num), NW * 0.44, y_u + UH / 2)

            # ── Cuerpo del slot ─────────────────────────────────────────────
            cr.set_source_rgb(*bg)
            cr.rectangle(NW, y0, RW, h); cr.fill()

            # Líneas guía internas (multi-U)
            if u_count > 1 and tipo not in ("libre",):
                alpha_guide = 0.08 if tipo == "bandeja" else 0.06
                cr.set_source_rgba(0, 0, 0, alpha_guide)
                cr.set_line_width(0.5)
                for i in range(1, u_count):
                    yd = y0 + i * UH
                    cr.move_to(NW + 8*z, yd); cr.line_to(NW + RW - 8*z, yd)
                cr.stroke()

            # Borde del slot
            lw = max(1, 2.0 * z) if tipo == "bandeja" else max(1, 1.5 * z)
            cr.set_source_rgb(*border)
            cr.set_line_width(lw)
            cr.rectangle(NW, y0, RW, h); cr.stroke()

            # ── Texto ────────────────────────────────────────────────────────
            cx = NW + RW / 2
            cy = y0 + h / 2

            if tipo == "libre":
                cr.set_source_rgb(*fg)
                cr.select_font_face("Sans", 2, 0)
                cr.set_font_size(max(8, 9 * z))
                _tc(cr, "LIBRE", cx, cy)

            elif tipo == "bandeja":
                nombres_lista = nombre   # list
                cr.set_source_rgb(*fg)
                cr.select_font_face("Sans", 0, 1)
                fs = max(8, min(12 * z, h * 0.30))
                cr.set_font_size(fs)
                ancho_util = RW - 14 * z

                # Construir etiqueta: "Bandeja: eq1, eq2, …"
                prefijo   = _("Bandeja: ")
                separador = ", "
                etiqueta  = prefijo + separador.join(nombres_lista)
                etiqueta  = _abrev(cr, etiqueta, ancho_util)
                _tc(cr, etiqueta, cx, cy)

            else:
                # equipo / frame
                fs = max(8, min(12 * z, h * 0.38))
                cr.set_source_rgb(*fg)
                cr.select_font_face("Sans", 0, 1)
                cr.set_font_size(fs)
                nombre_show = _abrev(cr, nombre, RW - 14 * z)

                if inv and h > 2.2 * fs:
                    _tc(cr, nombre_show, cx, cy - fs * 0.55)
                    cr.select_font_face("Sans", 0, 0)
                    cr.set_font_size(fs * 0.78)
                    cr.set_source_rgba(*fg, 0.72)
                    _tc(cr, _abrev(cr, inv, RW - 14*z), cx, cy + fs * 0.60)
                else:
                    _tc(cr, nombre_show, cx, cy)

        # ── Marco exterior ──────────────────────────────────────────────────
        cr.set_source_rgb(0.15, 0.18, 0.22)
        cr.set_line_width(max(2, 3 * z))
        cr.rectangle(0, 0, total_w, total_h); cr.stroke()

        cr.set_source_rgb(0.30, 0.30, 0.35)
        cr.set_line_width(max(1, 1.5 * z))
        cr.move_to(NW, 0); cr.line_to(NW, total_h); cr.stroke()

    # ── Exportación a PDF/SVG ────────────────────────────────────────────
    def _exportar_pdf(self, btn):
        """Exporta la vista del rack a PDF."""
        if not self._rack_info:
            from cabledoc import mostrar_error
            mostrar_error(self, "Seleccione un rack primero")
            return
        
        import cairo
        from datetime import datetime
        import os
        
        # Crear diálogo para seleccionar archivo
        dialog = Gtk.FileChooserDialog(
            title="Exportar a PDF",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        
        # Filtrar solo PDF
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("Archivos PDF")
        filter_pdf.add_mime_type("application/pdf")
        filter_pdf.add_pattern("*.pdf")
        dialog.add_filter(filter_pdf)
        
        # Nombre de archivo por defecto
        nombre_rack, _ = self._rack_info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dialog.set_current_name(f"rack_{nombre_rack}_{timestamp}.pdf")
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            
            # Obtener tamaño del drawing area
            alloc = self._da.get_allocation()
            width = alloc.width
            height = alloc.height
            
            # Crear surface PDF
            surface = cairo.PDFSurface(filepath, width, height)
            cr = cairo.Context(surface)
            
            # Dibujar el mismo contenido que en _on_draw
            self._draw_on_context(cr, width, height)
            
            surface.finish()
            
            from cabledoc import mostrar_info
            mostrar_info(self, f"Exportado a:\n{os.path.abspath(filepath)}")
        
        dialog.destroy()

    def _exportar_svg(self, btn):
        """Exporta la vista del rack a SVG."""
        if not self._rack_info:
            from cabledoc import mostrar_error
            mostrar_error(self, "Seleccione un rack primero")
            return
        
        import cairo
        from datetime import datetime
        import os
        
        # Crear diálogo para seleccionar archivo
        dialog = Gtk.FileChooserDialog(
            title="Exportar a SVG",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        
        # Filtrar solo SVG
        filter_svg = Gtk.FileFilter()
        filter_svg.set_name("Archivos SVG")
        filter_svg.add_mime_type("image/svg+xml")
        filter_svg.add_pattern("*.svg")
        dialog.add_filter(filter_svg)
        
        # Nombre de archivo por defecto
        nombre_rack, _ = self._rack_info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dialog.set_current_name(f"rack_{nombre_rack}_{timestamp}.svg")
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            
            # Obtener tamaño del drawing area
            alloc = self._da.get_allocation()
            width = alloc.width
            height = alloc.height
            
            # Crear surface SVG
            surface = cairo.SVGSurface(filepath, width, height)
            cr = cairo.Context(surface)
            
            # Dibujar el mismo contenido que en _on_draw
            self._draw_on_context(cr, width, height)
            
            surface.finish()
            
            from cabledoc import mostrar_info
            mostrar_info(self, f"Exportado a:\n{os.path.abspath(filepath)}")
        
        dialog.destroy()

    def _draw_on_context(self, cr, width, height):
        """Dibuja el rack en un contexto Cairo dado (para exportación)."""
        # Guardar el contexto actual para restaurarlo después
        cr.save()
        
        # Escalar al tamaño original del drawing area
        # El _on_draw espera que el contexto esté en las dimensiones originales
        # del DrawingArea
        if width > 0 and height > 0:
            alloc = self._da.get_allocation()
            if alloc.width > 0 and alloc.height > 0:
                cr.scale(width / alloc.width, height / alloc.height)
        
        # Llamar al método de dibujo original (da es None, no se usa)
        self._on_draw(None, cr)
        
        # Restaurar contexto
        cr.restore()


# ── función de conveniencia ────────────────────────────────────────────────────

def abrir_vista_rack(id_rack=None, parent=None):
    dlg = VistaRack(id_rack=id_rack, parent=parent)
    dlg.run(); dlg.destroy()
