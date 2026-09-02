#!/usr/bin/env python3
"""
patcheras_ui.py — CableDoc GTK3

Entrega 3 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md / PROGRESS_REFACTOR.md). Move 1:1, sin
cambio de lógica:

  PatcherasVista    vista de patcheras PPV/PPA (puntos de conexión A_BACK/
                    B_BACK por rack/frame/slot, coloreados según conexión
                    con el equipo consultado)
  abrir_patcheras   función de conveniencia
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk

from modelo import Modelo

from pantallas_comunes import _, s, PALETA, _tc


class PatcherasVista(Gtk.Dialog):
    """
    Vista de patcheras PPV/PPA para un equipo dado.

    Muestra ÚNICAMENTE los racks que tienen frames (PPV/PPA) con equipos
    de tipo MODULO PATCHERA instalados en sus slots.

    Cadena de datos:
      RACK → posicion_en_rack.id_frame → FRAME (PPV/PPA)
           → slot.id_equipo → EQUIPO (MODULO PATCHERA)
           → conector (A_BACK / B_BACK)

    Colores de los puntos (respecto al equipo seleccionado):
      ● VERDE  — conector A_BACK conectado al equipo  (salida / output)
      ● ROJO   — conector B_BACK conectado al equipo  (entrada / input)
      ● OSCURO — no conectado al equipo seleccionado
    """

    # ── Dimensiones (px a zoom=1.0) ──────────────────────────────────────────
    DOT_R     =  6
    DOT_STEP  = 19
    ROW_H     = 24
    HDR_H     = 16
    LBL_W     = 56    # ancho columna etiqueta (nombre frame + "A"/"B")
    STRIP_GAP =  3
    RHDR_H    = 22
    MARGIN    =  6

    # ── Colores ───────────────────────────────────────────────────────────────
    C_BG    = (0.06, 0.06, 0.06)
    C_STRP  = (0.10, 0.10, 0.12)
    C_RHDR  = (0.15, 0.20, 0.30)
    C_GREEN = (0.10, 0.85, 0.20)   # salida (A_BACK)
    C_RED   = (0.90, 0.20, 0.15)   # entrada (B_BACK)
    C_DARK  = (0.18, 0.18, 0.20)   # no conectado
    C_TXT   = (0.82, 0.82, 0.85)
    C_NUM   = (0.38, 0.38, 0.45)
    C_ROW   = (0.55, 0.55, 0.62)
    C_EDGE  = (0.18, 0.20, 0.26)

    # Color del "cabo" (patchcord suelto) cuando el otro extremo es FANTASMA
    C_JUMPER_FANTASMA = (0.55, 0.55, 0.60)

    def __init__(self, id_equipo=None, nombre_equipo="", parent=None):
        self._modo_global = id_equipo is None
        titulo = ("Patcheras — Vista global (todas)" if self._modo_global
                   else f"Patcheras — {nombre_equipo}")
        super().__init__(
            title=titulo,
            transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(1150, 680)

        self._STRIP_H = self.HDR_H + 2 * self.ROW_H   # 64 px
        self._id_equipo = id_equipo
        self._zoom      = 1.0
        self._rack_data = {}   # {rack_nom: {frame_nom: {col: {A:color, B:color}}}}
        self._das       = {}   # {rack_nom: DrawingArea}
        self._color_equipo = {}   # {id_equipo: (r,g,b)} — modo global
        self._jumpers   = {}      # {rack_nom: [ {tipo,p1,p2,color,tooltip} ]} — modo global
        self._jumpers_cross = []  # [ {origen,destino,color} ] — patchcords que cruzan de rack (overlay)

        area = self.get_content_area()

        # ── Barra superior ────────────────────────────────────────────────────
        hb = Gtk.Box(spacing=6,
                     margin_start=8, margin_end=8,
                     margin_top=6,   margin_bottom=4)
        self._lbl_info = Gtk.Label(xalign=0, hexpand=True)
        self._lbl_info.set_markup("<i>Cargando…</i>")
        hb.pack_start(self._lbl_info, True, True, 0)

        self._lbl_zoom = Gtk.Label(label=_("100%"))
        hb.pack_start(Gtk.Label(label=_("Zoom:")), False, False, 0)
        hb.pack_start(self._lbl_zoom, False, False, 0)
        for lbl, fn in [
            ("+",   lambda _: self._set_zoom(self._zoom * 1.20)),
            ("−",   lambda _: self._set_zoom(self._zoom / 1.20)),
            ("1:1", lambda _: self._set_zoom(1.0)),
        ]:
            b = Gtk.Button(label=lbl); b.connect("clicked", fn)
            hb.pack_start(b, False, False, 0)

        hb.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)

        if self._modo_global:
            # Modo global: cada equipo conectado atrás tiene su propio color
            # (se ve en el tooltip); "x" = equipo tipo FANTASMA; las líneas
            # de arriba de cada patchera son los patchcords del frente.
            lbl_leyenda = Gtk.Label()
            lbl_leyenda.set_markup(
                "<i>🎨 color = equipo conectado atrás  ·  ✖ = FANTASMA  ·  "
                "línea superior = patchcord del frente</i>")
            hb.pack_start(lbl_leyenda, False, False, 0)

            hb.pack_start(
                Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
            self._btn_cables_cross = Gtk.ToggleButton(label=_("👁 Cables entre racks"))
            self._btn_cables_cross.set_tooltip_text(
                _("Mostrar momentáneamente los patchcords que cruzan de un "
                  "rack a otro como una curva completa (mientras está "
                  "activo, esos tooltips/clicks quedan tapados por la "
                  "curva; se desactiva solo al volver a apretarlo)"))
            self._btn_cables_cross.connect("toggled", self._toggle_cables_cross_rack)
            hb.pack_start(self._btn_cables_cross, False, False, 0)
        else:
            for texto, rgb in [("Salida (A)", self.C_GREEN),
                                ("Entrada (B)", self.C_RED)]:
                da_l = Gtk.DrawingArea(); da_l.set_size_request(12, 12)
                c = rgb
                da_l.connect("draw", lambda w, cr, c=c:
                             [cr.set_source_rgb(*c),
                              cr.arc(6, 6, 5, 0, 6.2832),
                              cr.fill(), False][-1])
                hb.pack_start(da_l, False, False, 0)
                hb.pack_start(Gtk.Label(label=texto), False, False, 0)
        
        # Botones de exportación
        hb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
        hb.pack_start(Gtk.Label(label=_("Exportar:")), False, False, 0)
        btn_pdf = Gtk.Button(label=_("📄 PDF"))
        btn_pdf.connect("clicked", self._exportar_pdf)
        hb.pack_start(btn_pdf, False, False, 0)
        btn_svg = Gtk.Button(label=_("📊 SVG"))
        btn_svg.connect("clicked", self._exportar_svg)
        hb.pack_start(btn_svg, False, False, 0)
        btn_csv = Gtk.Button(label=_("📑 CSV"))
        btn_csv.set_tooltip_text(
            _("Exportar a CSV el detalle de las conexiones traseras de "
              "TODAS las patcheras del sistema"))
        btn_csv.connect("clicked", self._exportar_csv)
        hb.pack_start(btn_csv, False, False, 0)
        
        area.pack_start(hb, False, False, 0)
        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── Área de racks ────────────────────────────────────────────────────
        self._hbox = Gtk.Box(spacing=4,
                              margin_start=4, margin_end=4, margin_bottom=4)
        sw_outer = Gtk.ScrolledWindow(vexpand=True)
        sw_outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        try:
            # Por defecto GTK3 usa scrollbars "overlay" (finitas, se ocultan
            # solas y sólo aparecen al pasar el mouse por el borde). Se
            # desactiva para que sean las clásicas, siempre visibles.
            sw_outer.set_overlay_scrolling(False)
        except AttributeError:
            pass  # GTK muy viejo: no existe el método, no rompe nada
        sw_outer.add(self._hbox)

        self._overlay_da = None
        if self._modo_global:
            # Capa transparente encima de TODOS los racks, para dibujar los
            # patchcords que cruzan de un rack a otro como una curva real.
            # OCULTA por defecto (set_visible(False) + no_show_all): un
            # widget invisible no recibe eventos de mouse, así que mientras
            # está oculta los tooltips/clicks de los orificios funcionan
            # perfecto. Sólo se muestra momentáneamente con el botón
            # "👁 Cables entre racks" (_toggle_cables_cross_rack).
            overlay = Gtk.Overlay()
            overlay.add(sw_outer)
            self._overlay_da = Gtk.DrawingArea()
            self._overlay_da.set_can_focus(False)
            self._overlay_da.set_hexpand(True)
            self._overlay_da.set_vexpand(True)
            self._overlay_da.set_no_show_all(True)
            self._overlay_da.set_visible(False)
            overlay.add_overlay(self._overlay_da)
            try:
                overlay.set_overlay_pass_through(self._overlay_da, True)
            except AttributeError:
                pass  # GTK < 3.20: sin pass-through (igual queda oculta por defecto)
            self._overlay_da.connect("draw", self._draw_overlay_cross_rack)
            sw_outer.get_hadjustment().connect(
                "value-changed", lambda a: self._overlay_da.queue_draw())
            sw_outer.get_vadjustment().connect(
                "value-changed", lambda a: self._overlay_da.queue_draw())
            area.pack_start(overlay, True, True, 0)
        else:
            area.pack_start(sw_outer, True, True, 0)

        self._sb = Gtk.Statusbar()
        area.pack_start(self._sb, False, False, 0)

        self.show_all()
        self._cargar()

    # ── zoom ──────────────────────────────────────────────────────────────────
    def _set_zoom(self, z):
        self._zoom = max(0.3, min(3.0, z))
        self._lbl_zoom.set_text(f"{int(self._zoom*100)}%")
        for rn, da in self._das.items():
            self._resize(rn, da)
        if self._overlay_da is not None:
            self._overlay_da.queue_draw()

    # ── modo global: mostrar/ocultar momentáneamente los cables cross-rack ──────
    def _toggle_cables_cross_rack(self, btn):
        """Muestra u oculta la capa overlay con la curva real de los
        patchcords que cruzan de un rack a otro. Al ocultarla (estado por
        defecto) el widget queda completamente invisible y no recibe
        eventos de mouse, así que los tooltips/clicks de los orificios
        vuelven a funcionar normalmente sin quedar deshabilitados para
        siempre."""
        if self._overlay_da is None:
            return
        activo = btn.get_active()
        self._overlay_da.set_visible(activo)
        if activo:
            self._overlay_da.queue_draw()

    def _strip_w(self):
        n_cols = max(
            (max(fd.keys(), default=0)
             for rd in self._rack_data.values()
             for fd in rd.values()),
            default=24
        )
        return (self.LBL_W + n_cols * self.DOT_STEP + self.MARGIN * 2) * self._zoom

    def _rack_h(self, rack_nom):
        n = sum(len(fdict) for fdict in self._rack_data.get(rack_nom, {}).values())
        n_frames = len(self._rack_data.get(rack_nom, {}))
        return (self.RHDR_H + self.MARGIN +
                n_frames * (self._STRIP_H + self.STRIP_GAP)) * self._zoom

    def _resize(self, rack_nom, da):
        da.set_size_request(int(self._strip_w()), int(self._rack_h(rack_nom)))
        da.queue_draw()

    # ── color determinístico por equipo (modo global) ───────────────────────────
    def _color_para_equipo(self, id_equipo):
        """Devuelve siempre el mismo color para el mismo id_equipo durante
        toda la vida de esta ventana (un color distinto por cada equipo que
        aparece, tomado de PALETA en orden de aparición)."""
        if id_equipo not in self._color_equipo:
            idx = len(self._color_equipo) % len(PALETA)
            self._color_equipo[id_equipo] = PALETA[idx]
        return self._color_equipo[id_equipo]

    # ── carga ─────────────────────────────────────────────────────────────────
    def _cargar(self):
        if self._modo_global:
            self._cargar_global()
        else:
            self._cargar_por_equipo()

    def _cargar_por_equipo(self):
        import re as _re

        # ── Paso 1: conectores de PATCHERA conectados al equipo ────────
        # Retorna (id_conector_patchera, nombre_conector, clave_funcion) sólo
        # para los conectores traseros (BACK_ENTRADA/BACK_SALIDA) — Fase C de
        # plan_desarrollo_funcion_patchera.md: filtro EXCLUSIVO por
        # conector.id_funcion_patchera, sin fallback a nombre. Un conector
        # sin la función asignada todavía simplemente no aparece acá (queda
        # afuera del dibujo hasta completarse vía Modelo.
        # listar_patcheras_sin_funcion_completa / la ficha del equipo).
        con_rows = Modelo._query(
            "SELECT DISTINCT c2.id_conector, c2.nombre, fp.clave "
            "FROM conexion cx1 "
            "JOIN conector c1 ON cx1.id_conector = c1.id_conector "
            "JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
            "   AND cx2.id_conector != cx1.id_conector "
            "JOIN conector c2 ON cx2.id_conector = c2.id_conector "
            "JOIN equipo e2 ON e2.id_equipo = c2.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e2.id_tipo_equipo "
            "LEFT JOIN funcion_patchera fp "
            "  ON fp.id_funcion_patchera = c2.id_funcion_patchera "
            "WHERE c1.id_equipo = ? "
            "AND te.rol_senal = 'PATCHERA' "
            "AND fp.clave IN ('BACK_ENTRADA','BACK_SALIDA')",
            (self._id_equipo,)
        )
        # {id_conector: "A"|"B"} — agrupación por FUNCIÓN (Fase D de
        # plan_desarrollo_funcion_patchera.md), no por letra de ningún
        # valor guardado: BACK_ENTRADA -> fila "A" (salida/output en esta
        # UI), BACK_SALIDA -> fila "B" (entrada/input). Las etiquetas
        # "A"/"B" siguen siendo sólo texto de esta pantalla, ya no se
        # derivan de ningún string de la base.
        con_conectados = {
            str(r[0]): ("A" if r[2] == "BACK_ENTRADA" else "B")
            for r in con_rows
        }

        # ── Paso 2: racks con frames PPV/PPA que tienen MODULO PATCHERA ───────
        rack_rows = Modelo._query(
            "SELECT DISTINCT r.id_rack, r.nombre "
            "FROM rack r "
            "JOIN posicion_en_rack pr ON pr.id_rack = r.id_rack "
            "JOIN frame f ON f.id_frame = pr.id_frame "
            "JOIN slot s ON s.id_frame = f.id_frame "
            "JOIN equipo e ON e.id_equipo = s.id_equipo "
            "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
            "WHERE te.rol_senal = 'PATCHERA' "
            "ORDER BY r.nombre"
        )

        n_sel = 0
        self._rack_data = {}

        for rack_row in rack_rows:
            id_rack   = rack_row[0]
            rack_nom  = s(rack_row[1])

            # ── Paso 3: frames del rack con MODULO PATCHERA ────────────────
            frame_rows = Modelo._query(
                "SELECT DISTINCT f.id_frame, f.nombre "
                "FROM frame f "
                "JOIN posicion_en_rack pr ON pr.id_frame = f.id_frame "
                "JOIN slot s ON s.id_frame = f.id_frame "
                "JOIN equipo e ON e.id_equipo = s.id_equipo "
                "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
                "WHERE pr.id_rack = ? "
                "AND te.rol_senal = 'PATCHERA' "
                "ORDER BY f.nombre",
                (id_rack,)
            )

            frames_dict = {}
            for fr in frame_rows:
                id_frame   = fr[0]
                frame_nom  = s(fr[1])

                # ── Paso 4: slots del frame con sus conectores traseros
                # (BACK_ENTRADA/BACK_SALIDA) ──
                slot_rows = Modelo._query(
                    "SELECT s.nombre, c.id_conector, c.nombre, e.id_equipo, "
                    "fp.clave "
                    "FROM slot s "
                    "JOIN equipo e ON e.id_equipo = s.id_equipo "
                    "JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo "
                    "JOIN conector c ON c.id_equipo = e.id_equipo "
                    "LEFT JOIN funcion_patchera fp "
                    "  ON fp.id_funcion_patchera = c.id_funcion_patchera "
                    "WHERE s.id_frame = ? "
                    "AND te.rol_senal = 'PATCHERA' "
                    "AND fp.clave IN ('BACK_ENTRADA','BACK_SALIDA') "
                    "ORDER BY s.nombre, c.nombre",
                    (id_frame,)
                )

                # {col_int: {"A": color, "B": color, "id_equipo": id_modulo}}
                frame_cols = {}
                for sr in slot_rows:
                    slot_nom     = s(sr[0])
                    id_con       = str(sr[1])
                    id_eq_modulo = sr[3]
                    clave_fn     = sr[4] if len(sr) > 4 else None

                    # Columna = número en el nombre del slot
                    nums = _re.findall(r'\d+', slot_nom)
                    col  = int(nums[0]) if nums else 0
                    if col == 0:
                        continue

                    # Fase D de plan_desarrollo_funcion_patchera.md:
                    # agrupación por FUNCIÓN, no por letra de ningún string
                    # guardado — el filtro de arriba ya garantiza que
                    # clave_fn sólo puede ser BACK_ENTRADA o BACK_SALIDA acá.
                    row = "A" if clave_fn == "BACK_ENTRADA" else "B"

                    if id_con in con_conectados:
                        color = "green" if row == "A" else "red"
                        n_sel += 1
                    else:
                        color = "dark"

                    frame_cols.setdefault(
                        col, {"A": "dark", "B": "dark", "id_equipo": id_eq_modulo})
                    frame_cols[col][row] = color
                    frame_cols[col]["id_equipo"] = id_eq_modulo

                if frame_cols:
                    frames_dict[frame_nom] = frame_cols

            if frames_dict:
                self._rack_data[rack_nom] = frames_dict

        # ── Resumen ───────────────────────────────────────────────────────────
        n_racks  = len(self._rack_data)
        n_frames = sum(len(v) for v in self._rack_data.values())
        verdes   = sum(
            1 for rd in self._rack_data.values()
            for fd in rd.values()
            for cd in fd.values() if cd.get("A") == "green"
        )
        rojos    = sum(
            1 for rd in self._rack_data.values()
            for fd in rd.values()
            for cd in fd.values() if cd.get("B") == "red"
        )
        self._lbl_info.set_markup(
            f"<b>{n_racks} racks  ·  {n_frames} patcheras</b>  —  "
            f"<span color='#22ee44'>⬤ {verdes} salidas</span>  "
            f"<span color='#ff4444'>⬤ {rojos} entradas</span>"
        )
        self._sb.push(self._sb.get_context_id("i"),
                      f"Cargado: {n_racks} racks, {n_frames} frames PPV/PPA")

        # ── Construir DrawingAreas ────────────────────────────────────────────
        self._construir_drawingareas(
            "No se encontraron racks con patcheras conectadas al equipo.")

    # ── carga: modo global (todas las patcheras del sistema) ────────────────────
    def _cargar_global(self):
        """Arma self._rack_data para TODAS las patcheras del sistema
        (sin filtrar por equipo). Por cada columna (A y B):
          - "A"/"B": estado del conector trasero (A_BACK/B_BACK) —
            {"estado": "vacio"|"conectado"|"fantasma", "id_equipo", "nombre", "color"}
          - "front": ídem pero de los conectores delanteros (A_FRONT/B_FRONT),
            más "es_jumper" (True si el otro extremo es el frente de OTRA
            patchera) y "destino_pos" (rack, frame, col, fila) en ese caso.
        Además arma self._jumpers (los patchcords a dibujar por rack).
        """
        import re as _re

        slot_rows = Modelo.devolver_slots_patchera_global()

        ubicacion_modulo = {}      # id_equipo_modulo -> (rack_nom, frame_nom, col)
        self._rack_data = {}
        self._color_equipo = {}
        self._jumpers = {}

        for id_rack, rack_nom, id_frame, frame_nom, slot_nom, id_eq_modulo in slot_rows:
            rack_nom  = s(rack_nom)
            frame_nom = s(frame_nom)
            if not id_eq_modulo:
                continue
            nums = _re.findall(r'\d+', s(slot_nom))
            col  = int(nums[0]) if nums else 0
            if col == 0:
                continue

            ubicacion_modulo[id_eq_modulo] = (rack_nom, frame_nom, col)
            (self._rack_data.setdefault(rack_nom, {})
                             .setdefault(frame_nom, {})
                             .setdefault(col, {
                "A": {"estado": "vacio", "id_equipo": None,
                      "nombre": None, "conector": None, "color": None},
                "B": {"estado": "vacio", "id_equipo": None,
                      "nombre": None, "conector": None, "color": None},
                "front": {
                    "A": {"estado": "vacio", "id_equipo": None, "nombre": None,
                          "conector": None, "color": None, "es_jumper": False,
                          "destino_pos": None},
                    "B": {"estado": "vacio", "id_equipo": None, "nombre": None,
                          "conector": None, "color": None, "es_jumper": False,
                          "destino_pos": None},
                },
                "id_equipo_modulo": id_eq_modulo,
            }))

        con_rows = Modelo.devolver_conexiones_conectores_patchera_global()

        for (id_con1, nom1, id_eq_modulo, id_eq2, nom_eq2, id_tipo_eq2,
             nom_tipo_eq2, id_con2, nom_con2, rol_senal_eq2,
             clave1, clave2) in con_rows:

            if id_eq_modulo not in ubicacion_modulo:
                continue
            if clave1 is None:
                # Conector sin función de patchera asignada todavía (ver
                # Modelo.listar_patcheras_sin_funcion_completa) — Fase C de
                # plan_desarrollo_funcion_patchera.md: ya no se adivina por
                # nombre, se deja afuera del dibujo hasta completarse.
                continue
            rack_nom, frame_nom, col = ubicacion_modulo[id_eq_modulo]
            celda = self._rack_data[rack_nom][frame_nom][col]

            # Fase D de plan_desarrollo_funcion_patchera.md: agrupación por
            # FUNCIÓN, no por letra de ningún string guardado — fila "A" =
            # {BACK_ENTRADA, FRONT_DERIVACION}, fila "B" = {BACK_SALIDA,
            # FRONT_INSERCION}. Las etiquetas "A"/"B" siguen siendo sólo
            # texto fijo de esta pantalla.
            row = "A" if clave1 in ("BACK_ENTRADA", "FRONT_DERIVACION") else "B"
            # Fase 5 de plan_desarrollo_hardcodes_idioma.md: FANTASMA vía
            # rol_senal en vez de comparar tipo_equipo.nombre == "FANTASMA".
            es_fantasma = (s(rol_senal_eq2).upper() == "FANTASMA")

            if es_fantasma:
                estado, color = "fantasma", None
            else:
                estado = "conectado"
                color  = self._color_para_equipo(id_eq2)

            if clave1 in ("BACK_ENTRADA", "BACK_SALIDA"):
                celda[row] = {"estado": estado, "id_equipo": id_eq2,
                               "nombre": s(nom_eq2), "conector": s(nom_con2),
                               "color": color}

            elif clave1 in ("FRONT_DERIVACION", "FRONT_INSERCION"):
                # Fase 5: PATCHERA vía rol_senal en vez de comparar
                # tipo_equipo.nombre == "MODULO PATCHERA".
                es_jumper = (
                    s(rol_senal_eq2).upper() == "PATCHERA"
                    and clave2 in ("FRONT_DERIVACION", "FRONT_INSERCION")
                    and id_eq2 in ubicacion_modulo
                )
                destino_pos = None
                if es_jumper:
                    d_rack, d_frame, d_col = ubicacion_modulo[id_eq2]
                    d_row = "A" if clave2 in ("BACK_ENTRADA", "FRONT_DERIVACION") else "B"
                    destino_pos = (d_rack, d_frame, d_col, d_row)

                celda["front"][row] = {
                    "estado": estado, "id_equipo": id_eq2, "nombre": s(nom_eq2),
                    "conector": s(nom_con2), "color": color, "es_jumper": es_jumper,
                    "destino_pos": destino_pos,
                }

        # ── Armar los patchcords (jumpers) a dibujar por rack ─────────────────
        visto_curvas = set()
        visto_cross  = set()
        self._jumpers_cross = []
        for rack_nom, frames in self._rack_data.items():
            for frame_nom, cols in frames.items():
                for col, celda in cols.items():
                    for row in ("A", "B"):
                        f = celda["front"][row]
                        if f["estado"] == "vacio":
                            continue
                        origen = (rack_nom, frame_nom, col, row)
                        color  = f["color"] if f["color"] else self.C_JUMPER_FANTASMA

                        if f["es_jumper"] and f["destino_pos"]:
                            destino = f["destino_pos"]
                            if destino[0] == rack_nom:
                                key = frozenset({origen, destino})
                                if key in visto_curvas:
                                    continue
                                visto_curvas.add(key)
                                self._jumpers.setdefault(rack_nom, []).append({
                                    "tipo": "curva",
                                    "p1": (frame_nom, col, row),
                                    "p2": (destino[1], destino[2], destino[3]),
                                    "color": color,
                                    "tooltip": (f"↔ Patchcord frente → {f['nombre']} "
                                                f"({f['conector']})"),
                                })
                            else:
                                # Cruza a otro rack: en la vista EN VIVO se
                                # dibuja como un cabo corto en su propio
                                # rack (cada rack es un Gtk.DrawingArea
                                # independiente; unirlos con una curva real
                                # requeriría una capa superpuesta que en la
                                # práctica termina tapando los tooltips/
                                # clicks de los orificios, así que se
                                # descartó). self._jumpers_cross sí guarda
                                # el par completo para dibujar la curva real
                                # en las exportaciones a PDF/SVG, donde
                                # todos los racks comparten una superficie.
                                key = frozenset({origen, destino})
                                if key not in visto_cross:
                                    visto_cross.add(key)
                                    self._jumpers_cross.append({
                                        "origen":  origen,
                                        "destino": destino,
                                        "color":   color,
                                    })
                                self._jumpers.setdefault(rack_nom, []).append({
                                    "tipo": "cabo",
                                    "p1": (frame_nom, col, row),
                                    "p2": None,
                                    "color": color,
                                    "tooltip": (f"↔ Patchcord frente → {f['nombre']} "
                                                f"({f['conector']}) — Rack {destino[0]}"),
                                })
                        else:
                            texto = (f"✖ FANTASMA — {f['nombre']} ({f['conector']})"
                                      if f["estado"] == "fantasma"
                                      else f"↔ Patchcord frente → {f['nombre']} ({f['conector']})")
                            self._jumpers.setdefault(rack_nom, []).append({
                                "tipo": "cabo",
                                "p1": (frame_nom, col, row),
                                "p2": None,
                                "color": color,
                                "tooltip": texto,
                            })

        # ── Resumen ───────────────────────────────────────────────────────────
        n_racks  = len(self._rack_data)
        n_frames = sum(len(v) for v in self._rack_data.values())
        n_equipos = len(self._color_equipo)
        n_fantasma = sum(
            1 for rd in self._rack_data.values() for fd in rd.values()
            for cd in fd.values()
            for row in ("A", "B") if cd[row]["estado"] == "fantasma"
        )
        self._lbl_info.set_markup(
            f"<b>{n_racks} racks  ·  {n_frames} patcheras</b>  —  "
            f"<span>🎨 {n_equipos} equipos distintos conectados atrás</span>  "
            f"<span>✖ {n_fantasma} fantasma</span>"
        )
        self._sb.push(self._sb.get_context_id("i"),
                      f"Cargado: {n_racks} racks, {n_frames} patcheras (vista global)")

        self._construir_drawingareas(
            "No se encontraron patcheras (MODULO PATCHERA) en el sistema.")

    def _construir_drawingareas(self, texto_vacio):
        """Crea el Gtk.DrawingArea de cada rack (compartido por ambos modos).
        El handler de click se elige según el modo: doble-click con diálogo
        de elección trasera/delantera en modo global, o el click simple
        (abre directo el equipo del front) en el modo por-equipo."""
        for ch in self._hbox.get_children():
            self._hbox.remove(ch)
        self._das.clear()

        click_handler = (self._on_button_press_global if self._modo_global
                          else self._on_click)

        for rack_nom in sorted(self._rack_data.keys()):
            fr = Gtk.Frame()
            _lbl_fr = Gtk.Label(label=f" RACK {rack_nom.upper()} ")
            _lbl_fr.set_markup(f"<b> RACK {rack_nom.upper()} </b>")
            fr.set_label_widget(_lbl_fr)
            fr.set_label_align(0.02, 0.5)

            da = Gtk.DrawingArea()
            da.connect("draw",          lambda w, cr, rn=rack_nom:
                        self._draw_rack(w, cr, rn))
            da.set_has_tooltip(True)
            da.connect("query-tooltip", lambda w, x, y, kb, tt, rn=rack_nom:
                        self._tooltip(w, x, y, kb, tt, rn))
            da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            da.connect("button-press-event", lambda w, ev, rn=rack_nom:
                        click_handler(w, ev, rn))
            self._das[rack_nom] = da
            fr.add(da)
            self._hbox.pack_start(fr, False, False, 4)
            self._resize(rack_nom, da)

        self._hbox.show_all()
        if not self._rack_data:
            self._lbl_info.set_markup(
                f"<span color='gray'><i>{texto_vacio}</i></span>")

        if self._overlay_da is not None:
            self._overlay_da.queue_draw()

    # ── modo global: dibuja los cables cross-rack en el overlay (toggle) ────────
    def _draw_overlay_cross_rack(self, da, cr):
        """Dibuja, en la capa transparente que cubre TODOS los racks (sólo
        visible mientras el botón "👁 Cables entre racks" está activo), una
        curva Bézier real por cada patchcord del frente cuya otra punta
        está en un rack distinto. Las coordenadas de cada punta se
        traducen del sistema de su propio Gtk.DrawingArea al de esta capa
        con translate_coordinates, así que siguen el scroll y el zoom
        correctamente."""
        z  = self._zoom
        dr = self.DOT_R * z
        for j in getattr(self, "_jumpers_cross", []):
            rack1, frame1, col1, row1 = j["origen"]
            rack2, frame2, col2, row2 = j["destino"]
            da1 = self._das.get(rack1)
            da2 = self._das.get(rack2)
            if not da1 or not da2:
                continue
            pos1 = self._anchor_xy(rack1, frame1, col1, row1)
            pos2 = self._anchor_xy(rack2, frame2, col2, row2)
            if pos1 is None or pos2 is None:
                continue

            t1 = da1.translate_coordinates(da, pos1[0], pos1[1] - dr)
            t2 = da2.translate_coordinates(da, pos2[0], pos2[1] - dr)
            if t1 is None or t2 is None:
                continue
            # PyGObject: puede devolver (x,y) o (ok,x,y) según versión
            if len(t1) == 3 and not t1[0]:
                continue
            if len(t2) == 3 and not t2[0]:
                continue
            ox1, oy1 = t1[-2], t1[-1]
            ox2, oy2 = t2[-2], t2[-1]

            color = j["color"]
            cr.set_line_width(max(1, 1.6 * z))
            cr.set_source_rgba(*color, 0.9)
            peak = min(oy1, oy2) - 34 * z
            cr.move_to(ox1, oy1)
            cr.curve_to(ox1, peak, ox2, peak, ox2, oy2)
            cr.stroke()
        return False

    # ── modo global: coordenada de anclaje de un patchcord (frente) ─────────────
    def _anchor_xy(self, rack_nom, frame_nom, col, row):
        """Punto (x,y) en píxeles (zoom aplicado) donde "nace" el patchcord:
        el centro exacto del círculo trasero (A o B) de esa columna, para
        que el cable se vea conectado directamente al orificio coloreado.
        No agrega ninguna fila nueva: reutiliza la posición del círculo que
        ya se dibuja en _draw_rack."""
        z    = self._zoom
        m    = self.MARGIN    * z
        lw   = self.LBL_W    * z
        step = self.DOT_STEP * z
        hh   = self.HDR_H    * z
        rh   = self.ROW_H    * z
        sh   = self._STRIP_H * z
        sg   = self.STRIP_GAP* z
        rhdr = self.RHDR_H   * z

        frames = self._rack_data.get(rack_nom, {})
        frame_names = sorted(frames.keys())
        if frame_nom not in frame_names:
            return None
        s_idx = frame_names.index(frame_nom)
        y0 = rhdr + m + s_idx * (sh + sg)
        cx = lw + (col - 1) * step + step / 2
        row_idx = 0 if row == "A" else 1
        ry = y0 + hh + row_idx * rh + rh / 2
        return (cx, ry)

    # ── tooltip: modo global ─────────────────────────────────────────────────
    def _tooltip_global(self, da, mx, my, kb, tooltip, rack_nom):
        # Orificio trasero (A_BACK / B_BACK) — el patchcord del frente
        # ahora se ancla en el mismo punto (el círculo), así que el
        # tooltip combina la info trasera y la delantera de ese orificio.
        z    = self._zoom
        rhdr = self.RHDR_H   * z
        m    = self.MARGIN   * z
        sh   = self._STRIP_H * z
        sg   = self.STRIP_GAP* z
        lw   = self.LBL_W    * z
        hh   = self.HDR_H    * z
        rh   = self.ROW_H    * z
        step = self.DOT_STEP * z

        y_rel = my - rhdr - m
        if y_rel < 0:
            return False
        strip_idx = int(y_rel / (sh + sg))
        frames = self._rack_data.get(rack_nom, {})
        frame_names = sorted(frames.keys())
        if strip_idx >= len(frame_names):
            return False

        frame_nom  = frame_names[strip_idx]
        y_in_strip = y_rel - strip_idx * (sh + sg)
        if y_in_strip < hh:
            return False

        row_idx = int((y_in_strip - hh) / rh)
        row     = "A" if row_idx == 0 else "B"
        col_idx = int((mx - lw) / step)
        if col_idx < 0:
            return False
        col = col_idx + 1

        cols  = frames[frame_nom]
        celda = cols.get(col)
        if not celda:
            return False

        info = celda[row]
        if info["estado"] == "vacio":
            texto_atras = "⚫ Atrás: sin conexión"
        elif info["estado"] == "fantasma":
            texto_atras = f"✖ Atrás: FANTASMA — {info['nombre']} ({info['conector']})"
        else:
            texto_atras = f"🎨 Atrás: {info['nombre']} — conector: {info['conector']}"

        front = celda["front"][row]
        if front["estado"] == "vacio":
            texto_frente = "Frente: sin patchcord"
        elif front["estado"] == "fantasma":
            texto_frente = f"Frente: ✖ FANTASMA — {front['nombre']} ({front['conector']})"
        else:
            texto_frente = f"Frente: {front['nombre']} — conector: {front['conector']}"

        tooltip.set_text(
            f"{frame_nom}  Columna {col:02d}  Fila {row}\n"
            f"{texto_atras}\n{texto_frente}")
        return True

    # ── tooltip ───────────────────────────────────────────────────────────────
    def _tooltip(self, da, mx, my, kb, tooltip, rack_nom):
        if self._modo_global:
            return self._tooltip_global(da, mx, my, kb, tooltip, rack_nom)
        z   = self._zoom
        rhdr= self.RHDR_H   * z
        m   = self.MARGIN   * z
        sh  = self._STRIP_H * z
        sg  = self.STRIP_GAP* z
        lw  = self.LBL_W    * z
        hh  = self.HDR_H    * z
        rh  = self.ROW_H    * z
        step= self.DOT_STEP * z

        y_rel = my - rhdr - m
        if y_rel < 0:
            return False
        strip_idx = int(y_rel / (sh + sg))
        frames = self._rack_data.get(rack_nom, {})
        frame_names = sorted(frames.keys())
        if strip_idx >= len(frame_names):
            return False

        frame_nom  = frame_names[strip_idx]
        y_in_strip = y_rel - strip_idx * (sh + sg)
        if y_in_strip < hh:
            return False

        row_idx  = int((y_in_strip - hh) / rh)
        row      = "A" if row_idx == 0 else "B"
        col_idx  = int((mx - lw) / step)
        if col_idx < 0:
            return False
        col = col_idx + 1

        cols = frames[frame_nom]
        max_col = max(cols.keys(), default=24)
        if col > max_col:
            return False

        color = cols.get(col, {"A": "dark", "B": "dark"}).get(row, "dark")
        estado = {"green": "🟢 Salida (A_BACK conectado)",
                  "red":   "🔴 Entrada (B_BACK conectado)",
                  "dark":  "⚫ Sin conexión al equipo"}.get(color, "?")
        tooltip.set_text(
            f"{frame_nom}  Columna {col:02d}  Fila {row}\n{estado}")
        return True

    # ── click en un orificio ────────────────────────────────────────────────
    def _on_click(self, da, event, rack_nom):
        """Al clickear un orificio VERDE o ROJO, abre el equipo que está
        patcheado del lado FRONT (A_FRONT/B_FRONT) de esa misma columna,
        es decir, el equipo al que realmente se llega a través del patch."""
        z    = self._zoom
        rhdr = self.RHDR_H   * z
        m    = self.MARGIN   * z
        sh   = self._STRIP_H * z
        sg   = self.STRIP_GAP* z
        lw   = self.LBL_W    * z
        hh   = self.HDR_H    * z
        rh   = self.ROW_H    * z
        step = self.DOT_STEP * z

        mx, my = event.x, event.y

        y_rel = my - rhdr - m
        if y_rel < 0:
            return False
        strip_idx = int(y_rel / (sh + sg))
        frames = self._rack_data.get(rack_nom, {})
        frame_names = sorted(frames.keys())
        if strip_idx >= len(frame_names):
            return False

        frame_nom  = frame_names[strip_idx]
        y_in_strip = y_rel - strip_idx * (sh + sg)
        if y_in_strip < hh:
            return False

        row_idx  = int((y_in_strip - hh) / rh)
        row      = "A" if row_idx == 0 else "B"
        col_idx  = int((mx - lw) / step)
        if col_idx < 0:
            return False
        col = col_idx + 1

        cols = frames[frame_nom]
        max_col = max(cols.keys(), default=24)
        if col > max_col or col not in cols:
            return False

        celda = cols[col]
        color = celda.get(row, "dark")
        if color not in ("green", "red"):
            return False  # sólo los orificios conectados abren un equipo

        id_eq_modulo = celda.get("id_equipo")
        if not id_eq_modulo:
            return False

        self._abrir_equipo_frontal(id_eq_modulo, row, frame_nom, col)
        return True

    def _abrir_equipo_frontal(self, id_eq_modulo, row, frame_nom, col):
        """Busca, a través del cable conectado al conector frontal
        (FRONT_DERIVACION si row=='A', FRONT_INSERCION si row=='B' — Fase
        C de plan_desarrollo_funcion_patchera.md, identificado por
        conector.id_funcion_patchera, sin mirar el nombre) del módulo
        patchera, el equipo del otro extremo y abre su diálogo."""
        clave_fn = "FRONT_DERIVACION" if row == "A" else "FRONT_INSERCION"
        rows = Modelo._query(
            "SELECT eq2.id_equipo, eq2.nombre "
            "FROM conector cf "
            "JOIN funcion_patchera fp ON fp.id_funcion_patchera = cf.id_funcion_patchera "
            "JOIN conexion cx1 ON cx1.id_conector = cf.id_conector "
            "JOIN conexion cx2 ON cx2.id_cable = cx1.id_cable "
            "   AND cx2.id_conector != cx1.id_conector "
            "JOIN conector c2 ON cx2.id_conector = c2.id_conector "
            "JOIN equipo eq2 ON eq2.id_equipo = c2.id_equipo "
            "WHERE cf.id_equipo = ? AND fp.clave = ? "
            "LIMIT 1",
            (id_eq_modulo, clave_fn)
        )

        ctx_id = self._sb.get_context_id("click")
        if not rows:
            self._sb.push(
                ctx_id,
                f"{frame_nom}  Col {col:02d} {row} — sin equipo patcheado "
                f"en el front")
            return

        id_eq_destino, nom_destino = rows[0]
        self._sb.push(
            ctx_id,
            f"{frame_nom}  Col {col:02d} {row} → abriendo {s(nom_destino)}")

        from cabledoc import _DialogoEquipo
        dlg = _DialogoEquipo(id_equipo=id_eq_destino, parent=self)
        dlg.run_and_destroy()

    # ── click: modo global (doble click → elegir trasera/delantera) ─────────────
    def _on_button_press_global(self, da, event, rack_nom):
        """Doble click sobre cualquier orificio trasero (A_BACK/B_BACK):
        pregunta si se quiere abrir la conexión trasera o delantera de esa
        misma columna, y abre el equipo correspondiente."""
        if event.type != Gdk.EventType._2BUTTON_PRESS:
            return False

        z    = self._zoom
        rhdr = self.RHDR_H   * z
        m    = self.MARGIN   * z
        sh   = self._STRIP_H * z
        sg   = self.STRIP_GAP* z
        lw   = self.LBL_W    * z
        hh   = self.HDR_H    * z
        rh   = self.ROW_H    * z
        step = self.DOT_STEP * z

        mx, my = event.x, event.y
        y_rel = my - rhdr - m
        if y_rel < 0:
            return False
        strip_idx = int(y_rel / (sh + sg))
        frames = self._rack_data.get(rack_nom, {})
        frame_names = sorted(frames.keys())
        if strip_idx >= len(frame_names):
            return False

        frame_nom  = frame_names[strip_idx]
        y_in_strip = y_rel - strip_idx * (sh + sg)
        if y_in_strip < hh:
            return False

        row_idx = int((y_in_strip - hh) / rh)
        row     = "A" if row_idx == 0 else "B"
        col_idx = int((mx - lw) / step)
        if col_idx < 0:
            return False
        col = col_idx + 1

        celda = frames[frame_nom].get(col)
        if not celda:
            return False

        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"{frame_nom} — Columna {col:02d}  Fila {row}",
        )
        dlg.format_secondary_text(
            _("¿Abrir la conexión trasera o delantera de este orificio?"))
        dlg.add_button(_("Trasera"), 1)
        dlg.add_button(_("Delantera"), 2)
        dlg.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        resp = dlg.run()
        dlg.destroy()

        if resp == 1:
            elegido, lado = celda[row], "trasera"
        elif resp == 2:
            elegido, lado = celda["front"][row], "delantera"
        else:
            return True

        ctx_id = self._sb.get_context_id("dblclick")
        if not elegido or elegido.get("estado") == "vacio" or not elegido.get("id_equipo"):
            self._sb.push(
                ctx_id,
                f"{frame_nom}  Col {col:02d} {row} — sin conexión {lado}")
            return True

        self._sb.push(
            ctx_id,
            f"{frame_nom}  Col {col:02d} {row} ({lado}) → "
            f"abriendo {elegido['nombre']} ({elegido.get('conector', '')})")

        from cabledoc import _DialogoEquipo
        dlg_eq = _DialogoEquipo(id_equipo=elegido["id_equipo"], parent=self)
        dlg_eq.run_and_destroy()
        return True

    # ── dibujo Cairo ──────────────────────────────────────────────────────────
    def _draw_rack(self, da, cr, rack_nom):
        z     = self._zoom
        m     = self.MARGIN    * z
        lw    = self.LBL_W    * z
        step  = self.DOT_STEP * z
        dr    = self.DOT_R    * z
        rh    = self.ROW_H    * z
        hh    = self.HDR_H    * z
        sh    = self._STRIP_H * z
        sg    = self.STRIP_GAP* z
        rhdr  = self.RHDR_H   * z
        fs_n  = max(7,  int(8  * z))
        fs_l  = max(7,  int(9  * z))
        fs_rh = max(9,  int(11 * z))

        frames    = self._rack_data.get(rack_nom, {})
        max_col   = max(
            (max(cols.keys(), default=0) for cols in frames.values()),
            default=24
        )
        total_w   = self._strip_w()
        total_h   = self._rack_h(rack_nom)

        # Fondo - pintar solo el área del rack, no toda la superficie
        # (importante para exportación donde cr.paint() borraría otros racks)
        cr.set_source_rgb(*self.C_BG)
        cr.rectangle(0, 0, total_w, total_h)
        cr.fill()

        # Header rack
        cr.set_source_rgb(*self.C_RHDR)
        cr.rectangle(0, 0, total_w, rhdr); cr.fill()
        cr.set_source_rgb(*self.C_TXT)
        cr.select_font_face("Sans", 0, 1); cr.set_font_size(fs_rh)
        cr.move_to(m, rhdr * 0.72)
        cr.show_text(f"RACK  {rack_nom.upper()}")

        for s_idx, frame_nom in enumerate(sorted(frames.keys())):
            y0   = rhdr + m + s_idx * (sh + sg)
            cols = frames[frame_nom]

            # Fondo strip
            cr.set_source_rgb(*self.C_STRP)
            cr.rectangle(0, y0, total_w, sh); cr.fill()

            # Nombre frame
            cr.set_source_rgb(*self.C_TXT)
            cr.select_font_face("Sans", 0, 1); cr.set_font_size(fs_l)
            _tc(cr, frame_nom, lw * 0.45, y0 + sh / 2)

            # Números de columna
            cr.select_font_face("Sans", 0, 0); cr.set_font_size(fs_n)
            for c_idx in range(max_col):
                cx = lw + c_idx * step + step / 2
                cr.set_source_rgb(*self.C_NUM)
                _tc(cr, f"{c_idx+1:02d}", cx, y0 + hh * 0.72)

            # Filas A y B
            for row_idx, row_lbl in enumerate(("A", "B")):
                ry = y0 + hh + row_idx * rh + rh / 2

                # Etiqueta fila
                cr.set_source_rgb(*self.C_ROW)
                cr.select_font_face("Sans", 0, 1); cr.set_font_size(fs_l)
                _tc(cr, row_lbl, lw * 0.80, ry)

                # Separador entre A y B
                if row_idx == 0:
                    cr.set_source_rgba(*self.C_EDGE, 1)
                    cr.set_line_width(max(0.5, 0.8 * z))
                    cr.move_to(lw, y0 + hh + rh)
                    cr.line_to(total_w - m, y0 + hh + rh)
                    cr.stroke()

                # Puntos
                for c_idx in range(max_col):
                    cx  = lw + c_idx * step + step / 2
                    col = c_idx + 1
                    es_fantasma = False

                    if self._modo_global:
                        celda = cols.get(col, {}).get(row_lbl)
                        if celda is None:
                            estado, fill_c, glow_c = "vacio", self.C_DARK, None
                        elif celda["estado"] == "conectado":
                            estado = "conectado"
                            fill_c = celda["color"]; glow_c = celda["color"]
                        elif celda["estado"] == "fantasma":
                            estado = "fantasma"
                            fill_c = self.C_DARK; glow_c = None
                            es_fantasma = True
                        else:
                            estado, fill_c, glow_c = "vacio", self.C_DARK, None
                    else:
                        color = cols.get(col, {"A": "dark", "B": "dark"}).get(row_lbl, "dark")
                        if color == "green":
                            estado = "conectado"
                            fill_c = self.C_GREEN; glow_c = self.C_GREEN
                        elif color == "red":
                            estado = "conectado"
                            fill_c = self.C_RED;   glow_c = self.C_RED
                        else:
                            estado, fill_c, glow_c = "vacio", self.C_DARK, None

                    if glow_c:
                        cr.set_source_rgba(*glow_c, 0.22)
                        cr.arc(cx, ry, dr * 1.7, 0, 6.2832); cr.fill()

                    cr.set_source_rgb(*fill_c)
                    cr.arc(cx, ry, dr, 0, 6.2832); cr.fill()

                    # Reflejo especular
                    cr.set_source_rgba(1, 1, 1,
                                       0.20 if estado != "vacio" else 0.05)
                    cr.arc(cx - dr*0.2, ry - dr*0.3, dr*0.38, 0, 6.2832)
                    cr.fill()

                    # Marca "x" para equipo tipo FANTASMA
                    if es_fantasma:
                        cr.set_source_rgb(0.88, 0.88, 0.90)
                        cr.set_line_width(max(1, 1.3 * z))
                        off = dr * 0.62
                        cr.move_to(cx - off, ry - off); cr.line_to(cx + off, ry + off)
                        cr.stroke()
                        cr.move_to(cx + off, ry - off); cr.line_to(cx - off, ry + off)
                        cr.stroke()

            # Borde del strip
            cr.set_source_rgb(*self.C_EDGE)
            cr.set_line_width(max(1, 1.0 * z))
            cr.rectangle(0, y0, total_w, sh); cr.stroke()

        # Patchcords del frente (sólo modo global) — se dibujan encima de
        # todas las franjas, como cables que salen del borde superior de
        # cada columna con conexión delantera.
        if self._modo_global:
            self._draw_patchcords(cr, rack_nom, z)

        # Marco exterior
        cr.set_source_rgb(0.22, 0.25, 0.35)
        cr.set_line_width(max(1, 1.5 * z))
        cr.rectangle(0, 0, total_w, total_h); cr.stroke()

    # ── modo global: dibujo de los patchcords del frente ────────────────────
    def _draw_patchcords(self, cr, rack_nom, z):
        """Dibuja, para cada columna con conexión en el frente (A_FRONT/
        B_FRONT), un cable (patchcord) que nace justo en el borde superior
        del círculo trasero de esa fila (A o B) — el mismo círculo coloreado
        por equipo del punto 1 — para que se vea conectado directamente a
        ese orificio:
          - "curva": ambas puntas del jumper caen en el mismo rack → una
            curva Bézier que las une (arquea por encima de las franjas).
          - "cabo": la otra punta está en otro rack o es un equipo final
            (no otra patchera) → un pequeño cabo con la punta libre,
            coloreado, con tooltip.
        No agrega ninguna fila de orificios nueva (ver _anchor_xy)."""
        dr = self.DOT_R * z
        for j in self._jumpers.get(rack_nom, []):
            frame1, col1, row1 = j["p1"]
            pos1 = self._anchor_xy(rack_nom, frame1, col1, row1)
            if pos1 is None:
                continue
            x1, y1 = pos1[0], pos1[1] - dr   # borde superior del círculo
            color = j["color"]

            cr.set_line_width(max(1, 1.6 * z))
            cr.set_source_rgba(*color, 0.9)

            if j["tipo"] == "curva" and j["p2"]:
                frame2, col2, row2 = j["p2"]
                pos2 = self._anchor_xy(rack_nom, frame2, col2, row2)
                if pos2 is None:
                    continue
                x2, y2 = pos2[0], pos2[1] - dr
                peak = min(y1, y2) - 22 * z
                cr.move_to(x1, y1)
                cr.curve_to(x1, peak, x2, peak, x2, y2)
                cr.stroke()
            else:
                # cabo suelto: sale hacia arriba-izquierda y termina en un
                # pequeño círculo hueco (representa el otro extremo, fuera
                # de este rack o hacia un equipo final)
                x2, y2 = x1 - 12 * z, y1 - 16 * z
                cr.move_to(x1, y1)
                cr.curve_to(x1, y1 - 10 * z, x2, y2 + 6 * z, x2, y2)
                cr.stroke()
                cr.set_line_width(max(1, 1.2 * z))
                cr.arc(x2, y2, 2.6 * z, 0, 6.2832); cr.stroke()

    # ── Exportación a PDF/SVG ────────────────────────────────────────────
    def _exportar_pdf(self, btn):
        """Exporta la vista de patcheras a PDF."""
        from datetime import datetime
        if not self._rack_data:
            from cabledoc import mostrar_error
            mostrar_error(self, "No hay datos de patcheras para exportar")
            return
        
        import cairo
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
        nombre_equipo = self.get_title().replace("Patcheras — ", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dialog.set_current_name(f"patcheras_{nombre_equipo}_{timestamp}.pdf")
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            
            # Exportar
            self._export_to_file(filepath, "pdf")
            
            from cabledoc import mostrar_info
            mostrar_info(self, f"Exportado a:\n{os.path.abspath(filepath)}")
        
        dialog.destroy()

    def _exportar_svg(self, btn):
        """Exporta la vista de patcheras a SVG."""
        from datetime import datetime
        if not self._rack_data:
            from cabledoc import mostrar_error
            mostrar_error(self, "No hay datos de patcheras para exportar")
            return
        
        import cairo
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
        nombre_equipo = self.get_title().replace("Patcheras — ", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dialog.set_current_name(f"patcheras_{nombre_equipo}_{timestamp}.svg")
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            
            # Exportar
            self._export_to_file(filepath, "svg")
            
            from cabledoc import mostrar_info
            mostrar_info(self, f"Exportado a:\n{os.path.abspath(filepath)}")
        
        dialog.destroy()

    def _export_to_file(self, filepath, filetype="pdf"):
        """Exporta a PDF o SVG."""
        import cairo
        import os
        
        # Calcular tamaño total
        if not self._das:
            return
        
        # Guardar el zoom actual y forzar a 1.0 para exportación
        saved_zoom = self._zoom
        self._zoom = 1.0
        
        # Calcular el tamaño de cada rack individualmente con zoom=1.0
        rack_heights = {}
        for rack_nom, da in self._das.items():
            # Calcular el alto de este rack
            rh = self._rack_h(rack_nom)
            rack_heights[rack_nom] = rh
        
        # Ancho máximo (todos deberían ser iguales)
        strip_w = self._strip_w()
        
        # Altura total
        total_height = sum(rack_heights.values())
        
        # Crear superficie
        if filetype == "pdf":
            surface = cairo.PDFSurface(filepath, strip_w, total_height)
        else:
            surface = cairo.SVGSurface(filepath, strip_w, total_height)
        
        cr = cairo.Context(surface)
        
        # Dibujar cada rack en su posición
        y_offset = 0
        rack_y_offset = {}
        for rack_nom, da in self._das.items():
            rack_y_offset[rack_nom] = y_offset

            # Guardar contexto
            cr.save()
            
            # Trasladar al inicio de este rack
            cr.translate(0, y_offset)
            
            # Obtener el alto de este rack
            rack_h = rack_heights[rack_nom]
            
            # Dibujar el rack con zoom=1.0
            self._draw_rack(None, cr, rack_nom)
            
            # Avanzar para el siguiente rack
            y_offset += rack_h
            
            # Restaurar contexto
            cr.restore()

        # Patchcords del frente que cruzan de un rack a otro: ahora que
        # todos los racks están en la misma superficie (uno debajo del
        # otro), se dibujan como una curva real entre las posiciones
        # absolutas de cada punta. En la ventana en vivo esto se muestra
        # como un cabo corto por rack (ver _cargar_global), porque cada
        # rack es un Gtk.DrawingArea independiente.
        if self._modo_global:
            dr = self.DOT_R  # zoom ya forzado a 1.0
            for j in getattr(self, "_jumpers_cross", []):
                rack1, frame1, col1, row1 = j["origen"]
                rack2, frame2, col2, row2 = j["destino"]
                if rack1 not in rack_y_offset or rack2 not in rack_y_offset:
                    continue
                pos1 = self._anchor_xy(rack1, frame1, col1, row1)
                pos2 = self._anchor_xy(rack2, frame2, col2, row2)
                if pos1 is None or pos2 is None:
                    continue
                x1, y1 = pos1[0], pos1[1] - dr + rack_y_offset[rack1]
                x2, y2 = pos2[0], pos2[1] - dr + rack_y_offset[rack2]
                color = j["color"]
                cr.set_line_width(max(1, 1.6))
                cr.set_source_rgba(*color, 0.9)
                peak = min(y1, y2) - 34
                cr.move_to(x1, y1)
                cr.curve_to(x1, peak, x2, peak, x2, y2)
                cr.stroke()
        
        surface.finish()
        
        # Restaurar zoom
        self._zoom = saved_zoom

    # ── Exportación a CSV (conexiones traseras de TODAS las patcheras) ──────
    def _datos_csv_patcheras(self):
        """Arma, sin depender del modo en que esté abierta esta ventana, la
        estructura {rack_nom: {frame_nom: {col: {"A":celda, "B":celda}}}}
        con el estado del conector TRASERO (BACK_ENTRADA/BACK_SALIDA) de
        TODAS las patcheras del sistema. celda = {"estado": "vacio"|
        "conectado"|"fantasma", "nombre": <equipo conectado o None>}."""
        import re as _re

        slot_rows = Modelo.devolver_slots_patchera_global()
        ubicacion = {}
        estructura = {}

        for id_rack, rack_nom, id_frame, frame_nom, slot_nom, id_eq_modulo in slot_rows:
            rack_nom = s(rack_nom); frame_nom = s(frame_nom)
            if not id_eq_modulo:
                continue
            nums = _re.findall(r'\d+', s(slot_nom))
            col  = int(nums[0]) if nums else 0
            if col == 0:
                continue
            ubicacion[id_eq_modulo] = (rack_nom, frame_nom, col)
            (estructura.setdefault(rack_nom, {})
                       .setdefault(frame_nom, {})
                       .setdefault(col, {
                "A": {"estado": "vacio", "nombre": None},
                "B": {"estado": "vacio", "nombre": None},
            }))

        con_rows = Modelo.devolver_conexiones_conectores_patchera_global()
        for (id_con1, nom1, id_eq_modulo, id_eq2, nom_eq2, id_tipo_eq2,
             nom_tipo_eq2, id_con2, nom_con2, rol_senal_eq2,
             clave1, clave2) in con_rows:
            # Fase C de plan_desarrollo_funcion_patchera.md: filtro
            # EXCLUSIVO por función (conector.id_funcion_patchera), sin
            # fallback a nombre.
            if clave1 not in ("BACK_ENTRADA", "BACK_SALIDA"):
                continue
            if id_eq_modulo not in ubicacion:
                continue
            rack_nom, frame_nom, col = ubicacion[id_eq_modulo]
            row = "A" if clave1 == "BACK_ENTRADA" else "B"
            es_fantasma = (s(rol_senal_eq2).upper() == "FANTASMA")
            estructura[rack_nom][frame_nom][col][row] = {
                "estado": "fantasma" if es_fantasma else "conectado",
                "nombre": s(nom_eq2),
            }
        return estructura

    def _exportar_csv(self, btn):
        """Exporta a CSV el detalle de las conexiones traseras de TODAS las
        patcheras del sistema (no sólo las que muestra esta ventana). Una
        fila identifica la patchera (rack/nombre) y luego dos filas, A y B,
        con una columna por posición: VACIO (sin conexión), FANTASMA
        (equipo tipo fantasma) o el nombre del equipo conectado atrás."""
        import csv, os
        from datetime import datetime

        estructura = self._datos_csv_patcheras()
        if not estructura:
            from cabledoc import mostrar_error
            mostrar_error(self, "No hay datos de patcheras para exportar")
            return

        dialog = Gtk.FileChooserDialog(
            title="Exportar a CSV",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                     Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        filtro_csv = Gtk.FileFilter()
        filtro_csv.set_name("Archivos CSV")
        filtro_csv.add_mime_type("text/csv")
        filtro_csv.add_pattern("*.csv")
        dialog.add_filter(filtro_csv)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dialog.set_current_name(f"patcheras_conexiones_traseras_{timestamp}.csv")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            if not filepath.lower().endswith(".csv"):
                filepath += ".csv"

            # ";" como separador y BOM utf-8-sig: se abre bien en Excel en
            # español (donde "," es el separador decimal).
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                for rack_nom in sorted(estructura.keys()):
                    for frame_nom in sorted(estructura[rack_nom].keys()):
                        cols = estructura[rack_nom][frame_nom]
                        max_col = max(cols.keys())

                        w.writerow(["PATCHERA", frame_nom, "RACK", rack_nom])
                        w.writerow([""] + [f"Col {c:02d}" for c in range(1, max_col + 1)])
                        for row in ("A", "B"):
                            fila = [row]
                            for c in range(1, max_col + 1):
                                celda = cols.get(c, {}).get(
                                    row, {"estado": "vacio", "nombre": None})
                                if celda["estado"] == "vacio":
                                    fila.append("VACIO")
                                elif celda["estado"] == "fantasma":
                                    fila.append("FANTASMA")
                                else:
                                    fila.append(celda.get("nombre") or "VACIO")
                            w.writerow(fila)
                        w.writerow([])

            from cabledoc import mostrar_info
            mostrar_info(self, f"Exportado a:\n{os.path.abspath(filepath)}")

        dialog.destroy()


# ── función de conveniencia ────────────────────────────────────────────────────

def abrir_patcheras(id_equipo=None, nombre_equipo="", parent=None):
    """Abre la vista de patcheras. Si id_equipo es None, abre el modo
    global (todas las patcheras del sistema, sin pedir equipo)."""
    dlg = PatcherasVista(id_equipo=id_equipo,
                          nombre_equipo=nombre_equipo, parent=parent)
    dlg.run(); dlg.destroy()
