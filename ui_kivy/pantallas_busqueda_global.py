#!/usr/bin/env python3
"""
pantallas_busqueda_global.py — Búsqueda global.

Equivalente a PanelArbol de cabledoc.py (GTK): árbol jerárquico
    Sala → Rack → Frame → Equipo → Conectores
                    └──→ Equipo directo → Conectores
       └──→ Equipos sueltos → Conectores
    Cables → Conexiones

con filtro de texto (poda ramas que no matchean) y navegación directa
al ABM de cada nodo.

Diferencia respecto al GTK original (panel lateral fijo en un
Gtk.Paned): en mobile no hay espacio para un panel permanente, así que
se implementa como un Popup a pantalla completa, accesible desde el
menú hamburguesa y desde un acceso rápido en la pantalla principal.

Interacción — mismo patrón "mantener presionado" ya usado en el resto
del proyecto (ver MANTENER_PRESIONADO_SEG en widgets_base.py):
  - Toque simple en un nodo con hijos → expande/colapsa.
  - Toque simple en un nodo hoja (sin hijos) → abre su ABM.
  - Mantener presionado en CUALQUIER nodo con ID propio → abre su ABM
    directamente, aunque tenga hijos (reemplaza al "row-activated" /
    doble-clic de GTK).
"""

import time

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.metrics import dp, sp

from widgets_base import (
    DialogoNombre, titulo_con_nombre, ALTO_FILA_COMPACTA, ALTO_BOTON, ALTO_ENTRY,
    FUENTE_NORMAL, FUENTE_CHICA,
    MANTENER_PRESIONADO_SEG, MANTENER_PRESIONADO_TOLERANCIA,
    s, _, fila_cerrar_arriba, barra_superior_dialogo,
)
from core.modelo import Modelo
from core.logger_cabledoc import log_debug

_BADGE_COLOR = {
    "sala":     "#534AB7",
    "rack":     "#185FA5",
    "frame":    "#BA7517",
    "equipo":   "#3B6D11",
    "conector": "#555550",
    "sin_rack": "#888880",
    "cable":    "#8B4513",
    "conexion": "#708090",
    "seccion":  "#444444",
}


def _hex_a_rgba(hex_color):
    hex_color = (hex_color or "#999999").lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b, 1)


# ─── Estructura de árbol ──────────────────────────────────────────────────────

class _NodoGlobal:
    def __init__(self, texto, tipo, id_="", id2="", badge="", bold=False):
        self.texto = texto
        self.tipo = tipo        # sala|rack|frame|equipo|conector|cable|conexion|sin_rack|seccion
        self.id = id_
        self.id2 = id2
        self.badge = badge
        self.bold = bold
        self.hijos = []
        self.expandido = False


def _agrupar(filas, idx_clave):
    """Agrupa una lista de filas (tuplas/listas) en un dict clave->lista,
    usando str(fila[idx_clave]) como clave. Reemplaza el patrón "una
    consulta por nodo padre" por "una sola consulta + agrupado en
    Python", que es la optimización clave de este módulo (ver nota en
    _construir_arbol)."""
    grupos = {}
    for fila in filas:
        clave = str(fila[idx_clave])
        grupos.setdefault(clave, []).append(fila)
    return grupos


def _construir_arbol():
    """Equivalente a PanelArbol._cargar_arbol() + _cargar_seccion_cables()
    (cabledoc.py, GTK).

    OPTIMIZACIÓN — bulk fetch en vez de N+1:
    La primera versión hacía una consulta por cada sala, por cada rack,
    por cada frame, por cada equipo (sus conectores) y por cada cable
    (sus conexiones). Cada llamada a Modelo._query() abre y cierra una
    conexión SQLite nueva (ver Modelo._conn()), así que con cientos de
    equipos y cables el árbol terminaba haciendo miles de conexiones a
    la base — eso era el 12+ segundos medidos en log.txt al abrir el
    popup, no algo relacionado con el tecleo.

    Acá se hace UNA sola consulta por tabla involucrada (racks de todas
    las salas, frames de todos los racks, conectores de todos los
    equipos, conexiones de todos los cables, etc.) y el árbol se arma
    agrupando esas listas en Python con _agrupar(). El resultado es el
    mismo árbol, con ~10 consultas en vez de ~1500."""
    t0 = time.perf_counter()
    raices = []

    n_infra = _NodoGlobal(_("Infraestructura"), "seccion", bold=True)
    n_infra.expandido = True
    raices.append(n_infra)

    # ── Consultas en bloque (una por tabla, no una por nodo padre) ──
    salas = Modelo._query("SELECT id_sala, nombre FROM sala ORDER BY nombre")

    racks_todos = Modelo._query(
        "SELECT r.id_rack, r.nombre, rps.id_sala FROM rack r "
        "JOIN rack_por_sala rps ON rps.id_rack=r.id_rack "
        "ORDER BY r.numero")
    racks_por_sala = _agrupar(racks_todos, 2)

    frames_todos = Modelo._query(
        "SELECT f.id_frame, f.nombre, p.id_rack, "
        "MIN(p.orificio_posicion_equipo_en_rack) AS orif "
        "FROM posicion_en_rack p JOIN frame f ON f.id_frame=p.id_frame "
        "WHERE p.id_frame IS NOT NULL "
        "GROUP BY f.id_frame ORDER BY orif")
    frames_por_rack = _agrupar(frames_todos, 2)

    eq_slots_todos = Modelo._query(
        "SELECT e.id_equipo, e.nombre, te.nombre, sl.id_frame "
        "FROM slot sl JOIN equipo e ON e.id_equipo=sl.id_equipo "
        "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo=e.id_tipo_equipo "
        "WHERE sl.id_equipo IS NOT NULL AND sl.id_equipo!=0 "
        "ORDER BY sl.nombre")
    eq_slots_por_frame = _agrupar(eq_slots_todos, 3)

    eq_directos_todos = Modelo._query(
        "SELECT e.id_equipo, e.nombre, te.nombre, p.id_rack "
        "FROM posicion_en_rack p "
        "JOIN equipo e ON e.id_equipo=p.id_equipo "
        "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo=e.id_tipo_equipo "
        "WHERE p.id_frame IS NULL "
        "AND p.id_equipo IS NOT NULL AND p.id_equipo!=0 "
        "ORDER BY p.orificio_posicion_equipo_en_rack, e.nombre")
    eq_directos_por_rack = _agrupar(eq_directos_todos, 3)

    sueltos_todos = Modelo._query(
        "SELECT e.id_equipo, e.nombre, COALESCE(te.nombre,''), en.id_sala "
        "FROM equiponoraqueable_por_sala en "
        "JOIN equipo e ON e.id_equipo=en.id_equipo "
        "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo=e.id_tipo_equipo "
        "WHERE e.id_equipo NOT IN (SELECT id_equipo FROM posicion_en_rack "
        "  WHERE id_equipo IS NOT NULL AND id_equipo!=0) "
        "AND e.id_equipo NOT IN (SELECT id_equipo FROM slot "
        "  WHERE id_equipo IS NOT NULL AND id_equipo!=0) "
        "ORDER BY e.nombre")
    sueltos_por_sala = _agrupar(sueltos_todos, 3)

    # Conectores de TODOS los equipos en una sola consulta.
    conectores_todos = Modelo._query(
        "SELECT c.id_conector, c.nombre, tc.nombre, c.id_equipo "
        "FROM conector c "
        "LEFT JOIN tipo_conector tc ON tc.id_tipo_conector=c.id_tipo_conector "
        "ORDER BY c.nombre")
    conectores_por_equipo = _agrupar(conectores_todos, 3)

    def _agregar_conectores(nodo_eq, id_eq):
        for id_con, nom_con, tipo_con, _id_eq in conectores_por_equipo.get(
                str(id_eq), []):
            nodo_eq.hijos.append(_NodoGlobal(
                s(nom_con) or f"#{id_con}", "conector", str(id_con),
                str(id_eq), badge=s(tipo_con) or ""))

    for id_sala, nombre_sala in salas:
        n_sala = _NodoGlobal(s(nombre_sala), "sala", str(id_sala),
                             badge="sala", bold=True)
        n_infra.hijos.append(n_sala)

        for id_rack, nombre_rack, _id_sala in racks_por_sala.get(
                str(id_sala), []):
            n_rack = _NodoGlobal(s(nombre_rack), "rack", str(id_rack),
                                 str(id_sala), badge="rack")
            n_sala.hijos.append(n_rack)

            for id_frame, nombre_frame, _id_rack, _orif in frames_por_rack.get(
                    str(id_rack), []):
                n_frame = _NodoGlobal(s(nombre_frame), "frame", str(id_frame),
                                      str(id_rack), badge="frame")
                n_rack.hijos.append(n_frame)

                for id_eq, nom_eq, tipo_eq, _id_frame in eq_slots_por_frame.get(
                        str(id_frame), []):
                    n_eq = _NodoGlobal(s(nom_eq), "equipo", str(id_eq),
                                       str(id_frame),
                                       badge=s(tipo_eq) or "equipo")
                    n_frame.hijos.append(n_eq)
                    _agregar_conectores(n_eq, id_eq)

            for id_eq, nom_eq, tipo_eq, _id_rack in eq_directos_por_rack.get(
                    str(id_rack), []):
                n_eq = _NodoGlobal(s(nom_eq), "equipo", str(id_eq),
                                   str(id_rack), badge=s(tipo_eq) or "equipo")
                n_rack.hijos.append(n_eq)
                _agregar_conectores(n_eq, id_eq)

        sueltos = sueltos_por_sala.get(str(id_sala), [])
        if sueltos:
            n_sueltos = _NodoGlobal(
                _("Equipos sueltos ({})").format(len(sueltos)), "sin_rack",
                str(id_sala), badge="sueltos")
            n_sala.hijos.append(n_sueltos)
            for id_eq, nom_eq, tipo_eq, _id_sala in sueltos:
                n_eq = _NodoGlobal(s(nom_eq), "equipo", str(id_eq),
                                   str(id_sala), badge=s(tipo_eq) or "equipo")
                n_sueltos.hijos.append(n_eq)
                _agregar_conectores(n_eq, id_eq)

    sin_rack = Modelo._query(
        "SELECT e.id_equipo, e.nombre, te.nombre FROM equipo e "
        "LEFT JOIN tipo_equipo te ON te.id_tipo_equipo=e.id_tipo_equipo "
        "WHERE e.id_equipo!=0 "
        "AND e.id_equipo NOT IN (SELECT id_equipo FROM posicion_en_rack "
        "  WHERE id_equipo IS NOT NULL AND id_equipo!=0) "
        "AND e.id_equipo NOT IN (SELECT id_equipo FROM slot "
        "  WHERE id_equipo IS NOT NULL AND id_equipo!=0) "
        "AND e.id_equipo NOT IN (SELECT id_equipo FROM equiponoraqueable_por_sala "
        "  WHERE id_equipo IS NOT NULL) "
        "ORDER BY e.nombre")
    if sin_rack:
        n_sr = _NodoGlobal(_("Sin ubicación ({})").format(len(sin_rack)),
                           "sin_rack", bold=True)
        n_infra.hijos.append(n_sr)
        for id_eq, nom_eq, tipo_eq in sin_rack:
            n_eq = _NodoGlobal(s(nom_eq), "equipo", str(id_eq),
                               badge=s(tipo_eq) or "equipo")
            n_sr.hijos.append(n_eq)
            _agregar_conectores(n_eq, id_eq)

    # ── Cables → Conexiones (una sola consulta para TODAS las conexiones,
    #    en vez de una por cable) ──
    cables = Modelo._query(
        "SELECT id_cable, codigo, COALESCE(estado,'') FROM cable "
        "ORDER BY codigo")
    n_cables = _NodoGlobal(_("Cables ({})").format(len(cables)), "seccion",
                           "cables", bold=True)
    raices.append(n_cables)

    conexiones_todas = Modelo.devolver_todas_las_conexiones()
    conexiones_por_cable = _agrupar(conexiones_todas, 6)  # r[6] = id_cable

    for id_cable, codigo, estado in cables:
        n_cable = _NodoGlobal(s(codigo) or f"#{id_cable}", "cable",
                              str(id_cable), badge=s(estado))
        n_cables.hijos.append(n_cable)
        for r in conexiones_por_cable.get(str(id_cable), []):
            eq_nom = s(r[1]) or "?"
            con_nom = s(r[2]) or "?"
            tipo_con = s(r[4]) or "?"
            n_cable.hijos.append(_NodoGlobal(
                f"{eq_nom} - {con_nom} ({tipo_con})", "conexion", str(r[0])))

    def _contar(nodo):
        return 1 + sum(_contar(h) for h in nodo.hijos)
    total_nodos = sum(_contar(r) for r in raices)
    log_debug(f"[busqueda_global] _construir_arbol: {total_nodos} nodos, "
             f"{len(salas)} salas, {len(cables)} cables, "
             f"{(time.perf_counter() - t0)*1000:.0f} ms (consultas SQL, "
             f"bulk fetch)")

    return raices


# ─── Fila del árbol (toque = expandir/hoja, mantener presionado = ABM) ────────

_ANCHO_INDENT = dp(16)      # por nivel de profundidad
_ANCHO_TOGGLE = dp(28)      # botón +/-
_ANCHO_LABEL = dp(200)      # ancho fijo del texto principal (se corta si es más largo)
_ANCHO_BADGE_MIN = dp(46)   # ancho mínimo de la categoría


class _FilaArbolGlobal(ButtonBehavior, BoxLayout):
    """Fila de ancho FIJO (no elástico): así el árbol completo puede ser
    más ancho que la pantalla en niveles profundos, y el ScrollView padre
    (do_scroll_x=True) permite panear horizontalmente para verlo. El label
    principal tiene un ancho fijo con text_size ligado, así shorten/halign
    realmente recortan el texto en vez de dejarlo "flotar" y superponerse
    a la categoría (badge)."""

    def __init__(self, nodo, profundidad, on_toggle, on_tap, on_mantener,
                **kwargs):
        super().__init__(orientation="horizontal", size_hint=(None, None),
                         height=ALTO_FILA_COMPACTA, spacing=dp(2), **kwargs)
        self.nodo = nodo
        self._on_tap = on_tap
        self._on_mantener = on_mantener
        self._ev_mantener = None
        self._mantener_disparado = False
        self._touch_inicio = None

        ancho_indent = dp(profundidad * 16)
        self.add_widget(BoxLayout(size_hint=(None, None),
                                  width=ancho_indent, height=ALTO_FILA_COMPACTA))

        if nodo.hijos:
            simbolo = "-" if nodo.expandido else "+"
            btn_t = Button(text=simbolo, size_hint=(None, None),
                          width=_ANCHO_TOGGLE, height=ALTO_FILA_COMPACTA,
                          font_size=FUENTE_CHICA)
            btn_t.bind(on_release=lambda *_a: on_toggle(nodo))
            self.add_widget(btn_t)
        else:
            self.add_widget(BoxLayout(size_hint=(None, None),
                                      width=_ANCHO_TOGGLE, height=ALTO_FILA_COMPACTA))

        lbl = Label(text=nodo.texto, halign="left", valign="middle",
                   bold=nodo.bold, font_size=FUENTE_CHICA,
                   shorten=True, shorten_from="right",
                   size_hint=(None, None), width=_ANCHO_LABEL,
                   height=ALTO_FILA_COMPACTA)
        lbl.text_size = (_ANCHO_LABEL, ALTO_FILA_COMPACTA)
        self.add_widget(lbl)

        ancho_badge = 0
        if nodo.badge:
            ancho_badge = max(_ANCHO_BADGE_MIN, dp(len(nodo.badge) * 6 + 8))
            color = _hex_a_rgba(_BADGE_COLOR.get(nodo.tipo))
            lbl_badge = Label(
                text=nodo.badge, size_hint=(None, None),
                width=ancho_badge, height=ALTO_FILA_COMPACTA,
                font_size=sp(10), color=color,
                halign="left", valign="middle", shorten=True,
                shorten_from="right")
            lbl_badge.text_size = (ancho_badge, ALTO_FILA_COMPACTA)
            self.add_widget(lbl_badge)

        _ESPACIADO = dp(2)  # debe coincidir con spacing= pasado al __init__
        n_huecos = 3 if ancho_badge else 2  # cantidad de widgets - 1
        self.width = (ancho_indent + _ANCHO_TOGGLE + _ANCHO_LABEL +
                     ancho_badge + _ESPACIADO * n_huecos)

    # ── Gesto "mantener presionado" (mismo patrón que _FilaRV) ──
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._mantener_disparado = False
            self._touch_inicio = (touch.x, touch.y)
            self._ev_mantener = Clock.schedule_once(
                self._disparar_mantener, MANTENER_PRESIONADO_SEG)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._ev_mantener is not None and self._touch_inicio is not None:
            dx = abs(touch.x - self._touch_inicio[0])
            dy = abs(touch.y - self._touch_inicio[1])
            if dx > MANTENER_PRESIONADO_TOLERANCIA or dy > MANTENER_PRESIONADO_TOLERANCIA:
                Clock.unschedule(self._ev_mantener)
                self._ev_mantener = None
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._ev_mantener is not None:
            Clock.unschedule(self._ev_mantener)
            self._ev_mantener = None
        return super().on_touch_up(touch)

    def _disparar_mantener(self, *_a):
        self._ev_mantener = None
        self._mantener_disparado = True
        if self._on_mantener:
            self._on_mantener(self.nodo)

    def on_release(self):
        if self._mantener_disparado:
            self._mantener_disparado = False
            return
        if self._on_tap:
            self._on_tap(self.nodo)


# ─── Popup principal ──────────────────────────────────────────────────────────

class BusquedaGlobalPopup(Popup):
    """Búsqueda global: árbol Sala→Rack→Frame→Equipo→Conector,
    más Cables→Conexión, con filtro de texto (poda ramas sin match)."""

    # Con un filtro muy amplio (p.ej. una sola letra común) el árbol
    # completo puede matchear cientos de nodos; crear esa cantidad de
    # widgets de golpe es lo que tardaba 15+ segundos en el dispositivo
    # real (ver log.txt: 891 filas ≈ 15.3s). Por eso se limita cuántas
    # filas se crean por reconstrucción cuando hay un filtro activo.
    MAX_FILAS_CON_FILTRO = 150

    def __init__(self, **kwargs):
        self._raices = []
        self._filtro = ""
        self._visible_cache = {}
        self._ev_filtro = None
        self._total_matches = 0

        box = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))

        hb_f = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        hb_f.add_widget(Label(text=_("Buscar:"), size_hint_x=None, width=dp(64),
                              font_size=FUENTE_CHICA, halign="left"))
        self.entry_filtro = TextInput(
            multiline=False, font_size=FUENTE_NORMAL,
            hint_text=_("Buscar equipo, rack, frame, cable…"))
        self.entry_filtro.bind(text=self._on_filtro_changed)
        hb_f.add_widget(self.entry_filtro)
        btn_reload = Button(text=_("Recargar"), size_hint_x=None, width=dp(90),
                            font_size=FUENTE_CHICA)
        btn_reload.bind(on_release=lambda *_a: self.recargar())
        hb_f.add_widget(btn_reload)
        box.add_widget(hb_f)

        box.add_widget(Label(
            text=_("Toque: expandir/abrir hoja  ·  "
                  "Mantener presionado: abrir ABM"),
            size_hint_y=None, height=dp(18), font_size=sp(10),
            color=(0.6, 0.6, 0.6, 1)))

        # do_scroll_x=True: las filas tienen ancho FIJO (ver
        # _FilaArbolGlobal) y box_arbol se dimensiona a su minimum_width,
        # así que cuando la profundidad del árbol hace que una fila sea
        # más ancha que la pantalla, se puede panear horizontalmente en
        # vez de que el texto se aplaste o se superponga a la categoría.
        self.scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        self.box_arbol = BoxLayout(orientation="vertical",
                                   size_hint=(None, None), spacing=dp(1))
        self.box_arbol.bind(minimum_height=self.box_arbol.setter("height"),
                            minimum_width=self.box_arbol.setter("width"))
        self.scroll.add_widget(self.box_arbol)
        box.add_widget(self.scroll)

        self.lbl_status = Label(text="", size_hint_y=None, height=dp(18),
                                font_size=sp(10), color=(0.55, 0.55, 0.55, 1),
                                halign="left")
        box.add_widget(self.lbl_status)

        outer = BoxLayout(orientation="vertical")
        outer.add_widget(barra_superior_dialogo(
            _("Búsqueda global"), on_atras=lambda: self.dismiss()))
        outer.add_widget(box)
        super().__init__(title="", separator_height=0, content=outer,
                         size_hint=(1, 1), **kwargs)
        self.bind(on_dismiss=self._cancelar_debounce)
        self.recargar()

    def _cancelar_debounce(self, *_a):
        if self._ev_filtro is not None:
            Clock.unschedule(self._ev_filtro)
            self._ev_filtro = None

    # ── Carga ──
    def recargar(self):
        t0 = time.perf_counter()
        self._raices = _construir_arbol()
        log_debug(f"[busqueda_global] recargar(): armado de nodos en "
                 f"{(time.perf_counter() - t0)*1000:.0f} ms")
        self._rebuild()

    # ── Filtro (equivalente a _podar_arbol / _row_visible de GTK) ──
    #
    # Dos optimizaciones respecto a la primera versión, necesarias porque
    # con el árbol completo (todas las salas/racks/frames/equipos/
    # conectores + cables/conexiones) tipear letra a letra se volvía
    # extremadamente lento:
    #
    #   1. Debounce: no se reconstruye en cada tecla, se espera
    #      FILTRO_DEBOUNCE_SEG desde la última tecla. Escribir rápido ya
    #      no dispara un rebuild por carácter.
    #   2. Cache de visibilidad: antes, _nodo_visible(nodo) recorría todo
    #      el subárbol de `nodo` cada vez que se llamaba, y se llamaba una
    #      vez por cada hijo de cada nodo renderizado → costo cuadrático
    #      con árboles grandes. Ahora se calcula una sola vez por
    #      reconstrucción, de abajo hacia arriba, y se guarda en
    #      self._visible_cache (por id() de nodo) — costo lineal.
    FILTRO_DEBOUNCE_SEG = 0.3

    def _on_filtro_changed(self, _inst, texto):
        log_debug(f"[busqueda_global] tecla → '{texto}' "
                 f"(reprograma debounce)")
        if self._ev_filtro is not None:
            Clock.unschedule(self._ev_filtro)
        self._ev_filtro = Clock.schedule_once(
            lambda *_a: self._aplicar_filtro(texto), self.FILTRO_DEBOUNCE_SEG)

    def _aplicar_filtro(self, texto):
        t0 = time.perf_counter()
        self._ev_filtro = None
        self._filtro = texto.lower().strip()
        self._rebuild()
        log_debug(f"[busqueda_global] _aplicar_filtro('{texto}'): "
                 f"total {(time.perf_counter() - t0)*1000:.0f} ms")

    def _calcular_visibilidad(self, nodo):
        """Llena self._visible_cache para nodo y todo su subárbol en una
        sola pasada bottom-up. Retorna si nodo es visible. También cuenta
        en self._total_matches los nodos que matchean directamente (no
        solo por tener un descendiente que matchea), para poder avisar
        "mostrando X de Y resultados" cuando se aplica el tope de filas."""
        vis_propio = (not self._filtro) or (self._filtro in nodo.texto.lower())
        if vis_propio and self._filtro:
            self._total_matches += 1
        vis_por_hijo = False
        for h in nodo.hijos:
            if self._calcular_visibilidad(h):
                vis_por_hijo = True
        visible = vis_propio or vis_por_hijo
        self._visible_cache[id(nodo)] = visible
        return visible

    def _nodo_visible(self, nodo):
        return self._visible_cache.get(id(nodo), True)

    # ── Render ──
    def _rebuild(self):
        t0 = time.perf_counter()
        n_widgets_antes = len(self.box_arbol.children)
        self.box_arbol.clear_widgets()
        t_clear = time.perf_counter()

        self._visible_cache = {}
        self._total_matches = 0
        for raiz in self._raices:
            self._calcular_visibilidad(raiz)
        t1 = time.perf_counter()

        self._filas_creadas = 0
        self._tope_alcanzado = False
        expandir_todo = bool(self._filtro)
        limite = self.MAX_FILAS_CON_FILTRO if expandir_todo else None
        for raiz in self._raices:
            if self._nodo_visible(raiz):
                self._render_nodo(raiz, 0, expandir_todo, limite)
        t2 = time.perf_counter()

        if self._tope_alcanzado:
            self.lbl_status.text = _(
                "Mostrando {} de {} coincidencias — seguí escribiendo para "
                "acotar.").format(self._filas_creadas, self._total_matches)
        elif self._filtro:
            self.lbl_status.text = _("{} coincidencias.").format(
                self._total_matches)
        else:
            self.lbl_status.text = _("Cargado.")

        log_debug(f"[busqueda_global] _rebuild: filtro='{self._filtro}' "
                 f"clear_widgets({n_widgets_antes})={(t_clear-t0)*1000:.0f}ms "
                 f"visibilidad={(t1-t_clear)*1000:.0f}ms "
                 f"render={(t2-t1)*1000:.0f}ms "
                 f"({self._filas_creadas} filas creadas, "
                 f"{self._total_matches} matches, "
                 f"tope={self._tope_alcanzado}) "
                 f"total={(t2-t0)*1000:.0f}ms")

    def _render_nodo(self, nodo, profundidad, forzar_expandido=False,
                     limite=None):
        if limite is not None and self._filas_creadas >= limite:
            self._tope_alcanzado = True
            return
        fila = _FilaArbolGlobal(nodo, profundidad, self._toggle,
                                self._on_tap, self._activar)
        self.box_arbol.add_widget(fila)
        self._filas_creadas += 1
        if nodo.expandido or forzar_expandido:
            for h in nodo.hijos:
                if limite is not None and self._filas_creadas >= limite:
                    self._tope_alcanzado = True
                    return
                if self._nodo_visible(h):
                    self._render_nodo(h, profundidad + 1, forzar_expandido,
                                      limite)

    def _toggle(self, nodo):
        if nodo.hijos:
            nodo.expandido = not nodo.expandido
            self._rebuild()

    def _on_tap(self, nodo):
        if not nodo.hijos and nodo.id:
            self._activar(nodo)
        elif nodo.hijos:
            self._toggle(nodo)

    # ── Acción según tipo (equivalente a PanelArbol._on_row_activated) ──
    def _activar(self, nodo):
        tipo, oid = nodo.tipo, nodo.id
        if not oid or tipo in ("seccion", "sin_rack"):
            return

        if tipo == "equipo":
            from pantallas_equipos import DialogoEquipo
            DialogoEquipo(id_equipo=oid, on_guardado=self.recargar).open()

        elif tipo == "sala":
            rows = Modelo.devolver_sala(oid)
            if rows:
                def _guardar(valor, _oid=oid):
                    Modelo.modificacion_sala(_oid, valor)
                    self.recargar()
                DialogoNombre(titulo_con_nombre(_("Editar Sala"), rows[0][1]),
                             valor=s(rows[0][1]), on_aceptar=_guardar).open()

        elif tipo == "rack":
            from pantallas_racks import DialogoRack
            DialogoRack(id_rack=oid, on_guardado=self.recargar).open()

        elif tipo == "frame":
            from pantallas_racks import DialogoFrame
            DialogoFrame(id_frame=oid, on_guardado=self.recargar).open()

        elif tipo == "conector":
            from pantallas_conectores import DialogoConector
            DialogoConector(id_conector=oid, id_equipo=nodo.id2,
                           on_guardado=self.recargar).open()

        elif tipo == "cable":
            from pantallas_cables import DialogoCable
            DialogoCable(id_cable=oid, on_guardado=self.recargar).open()

        elif tipo == "conexion":
            from pantallas_conexiones import DialogoConexion
            DialogoConexion(id_conexion=oid, on_guardado=self.recargar).open()


def abrir_busqueda_global():
    BusquedaGlobalPopup().open()
