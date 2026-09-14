"""
pantallas_escenario.py — "Modo Escenario" en Kivy (Fase 5.3 del roadmap)
=========================================================================
Ver ROADMAP_FASE5_paridad_pantallas.md, ítem 3. Equivalente a
escenario_ui.py (GTK, EscenarioMixin): reutiliza SIN NINGÚN CAMBIO
core/escenario_engine.py (Escenario/CambioPendiente), que ya es 100%
independiente de GTK/Kivy — la simulación en sí vive ahí, este archivo
sólo la envuelve en pantallas táctiles.

Decisión de diseño (quedaba pendiente en el roadmap: "portar el dibujo
1:1 a kivy.graphics, o simplificar a una vista de lista de cambios
propuestos"):

  - El OVERLAY sobre el diagrama (cables cortados con una cruz, líneas
    punteadas de reconexión virtual, resaltado de nodos fallados/
    impactados/recuperados, línea de arrastre en progreso) SÍ se porta
    1:1 a kivy.graphics — es geometría simple (líneas y rectángulos)
    que Kivy dibuja igual de bien que Cairo, y perderla sería una
    regresión real de la función (el valor de "Modo Escenario" es ver
    el resultado dibujado sobre el propio diagrama). Ver
    _CanvasDiagrama._draw_escenario_overlay en pantallas_diagrama.py.

  - El PANEL de resumen en texto (nombre del escenario, contadores,
    resultado del análisis, señales perdidas) NO se porta como texto
    dibujado a mano sobre el canvas (que es lo que hace GTK con Cairo,
    _esc_draw_panel) — en vez de eso es una tarjeta de widgets reales
    (PanelEscenario, BoxLayout con Labels), mismo criterio ya usado por
    PanelDiagnostico frente a _DialogoDiagnostico (ver
    pantallas_diagnostico.py): en una pantalla táctil chica, texto en
    widgets reales escala/se lee mejor que texto dibujado a mano a un
    tamaño de fuente fijo, y no hace falta reinventar wrapping/scroll a
    mano. La tarjeta ancla arriba-derecha (como el panel de GTK),
    mientras que PanelDiagnostico ancla abajo-centro — no compiten por
    el mismo rincón si algún día conviven en pantalla.

  - Los diálogos (nombre de escenario, listado de guardados, mensajes
    de confirmación/aviso) usan los mismos Popups asíncronos que el
    resto de mobile (confirmar/mostrar_info de widgets_base.py) en vez
    de .run() bloqueante — Kivy no tiene equivalente síncrono a
    Gtk.Dialog.run().

Integración en pantallas_diagrama.py (ver ese archivo para el detalle):
  1. DiagramaConexiones.__init__: estado _esc_* + botones de toolbar
     (🧪 Escenario / 🔗 Reconectar / 🆕 / 📂 / 💾 / ▶ / 🗑).
  2. _CanvasDiagrama.on_touch_down/move/up: interceptan el toque cuando
     _esc_modo está activo, ANTES de la lógica normal de selección/
     arrastre de nodo — mismo criterio que el bloque de Diagnóstico.
  3. _CanvasDiagrama._redraw(): llama a _draw_escenario_overlay() al
     final, después de _draw_conexion_interna().
  4. DiagramaConexiones._diag_activar()/_esc_activar_modo(): exclusión
     mutua entre Diagnóstico y Escenario (compiten por el mismo gesto
     de toque sobre el diagrama) — Impacto/Riesgo/Señal (roadmap, ítems
     4-5) todavía no existen en mobile, así que no hay más con qué
     excluirse todavía.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, mostrar_info, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from core.modelo import Modelo


# ─────────────────────────────────────────────────────────────────────────
# Paleta — idéntica a _C_* de escenario_ui.py (GTK), como tuplas (r,g,b)
# sin alfa (el alfa se aplica en cada llamada a Color(), igual que allá).
# Deliberadamente distinta de la paleta de riesgo/impacto (roadmap, ítems
# 4-5, todavía sin portar) para no confundir "esto ya pasó" con "esto es
# hipotético" el día que convivan.
# ─────────────────────────────────────────────────────────────────────────
C_FALLADO    = (0.80, 0.15, 0.55)   # magenta — equipo marcado como fallado
C_IMPACTADO  = (0.85, 0.10, 0.10)   # rojo — consecuencia (queda sin señal)
C_RECUPERADO = (0.15, 0.75, 0.30)   # verde — salvado por una reconexión virtual
C_CORTADO    = (0.55, 0.20, 0.20)   # rojo apagado — cable cortado del escenario
C_VIRTUAL    = (0.95, 0.80, 0.15)   # amarillo — conexión virtual propuesta

# Familias de tipo_conector compatibles entre sí para una reconexión
# virtual (idéntico a _FAM_ENTRADA/_FAM_SALIDA de escenario_ui.py).
_FAM_ENTRADA = {"IN", "REFIN"}
_FAM_SALIDA  = {"OUT", "REFOUT"}


def _esc_tipos_compatibles(tipo_a: str, tipo_b: str) -> bool:
    a, b = (tipo_a or "").upper(), (tipo_b or "").upper()
    return ((a in _FAM_ENTRADA and b in _FAM_SALIDA)
            or (a in _FAM_SALIDA and b in _FAM_ENTRADA))


def _label_wrap(texto, color=(0.91, 0.91, 0.91, 1), bold=False,
                font_size=FUENTE_CHICA):
    """Label de una sola columna con alto automático según el texto —
    mismo idioma que el resto de mobile (ver pantallas_diagnostico.py)."""
    lbl = Label(text=texto, color=color, bold=bold, font_size=font_size,
                halign="left", valign="top", size_hint_y=None)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    lbl.bind(texture_size=lambda w, *_a: setattr(w, "height", w.texture_size[1]))
    return lbl


# ─────────────────────────────────────────────────────────────────────────
# Diálogo de nombre + descripción — equivalente a _dialogo_nombre_escenario
# (GTK), pero asíncrono: el resultado llega por on_aceptar(nombre,
# descripcion) en vez de como valor de retorno de un .run() bloqueante.
# Mismo patrón visual que DialogoNombre (widgets_base.py), con un segundo
# campo de descripción — DialogoNombre no sirve tal cual porque sólo
# soporta un campo.
# ─────────────────────────────────────────────────────────────────────────
class PopupNombreEscenario(Popup):
    def __init__(self, on_aceptar=None, **kwargs):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        box.add_widget(Label(text=_("Nombre:"), size_hint_y=None, height=dp(24),
                             font_size=FUENTE_NORMAL, halign="left"))
        self.entry_nombre = TextInput(multiline=False, size_hint_y=None,
                                      height=ALTO_ENTRY, font_size=FUENTE_NORMAL)
        box.add_widget(self.entry_nombre)

        box.add_widget(Label(text=_("Descripción (opcional):"), size_hint_y=None,
                             height=dp(24), font_size=FUENTE_NORMAL, halign="left"))
        self.entry_desc = TextInput(multiline=False, size_hint_y=None,
                                    height=ALTO_ENTRY, font_size=FUENTE_NORMAL)
        box.add_widget(self.entry_desc)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        super().__init__(title=_("Nombre del escenario"), content=box,
                         size_hint=(1, None), height=dp(280), **kwargs)
        self._on_aceptar = on_aceptar
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._aceptar)
        self.entry_desc.bind(on_text_validate=self._aceptar)

    def _aceptar(self, *_a):
        nombre = self.entry_nombre.text.strip()
        if not nombre:
            return
        descripcion = self.entry_desc.text.strip()
        self.dismiss()
        if self._on_aceptar:
            self._on_aceptar(nombre, descripcion)


# ─────────────────────────────────────────────────────────────────────────
# Listado de escenarios guardados — equivalente a _dialogo_listado_
# escenarios (GTK). Reutiliza ListadoPopup (mismo patrón ya usado por
# HistorialDiagnosticosListado en pantallas_diagnostico.py para un
# listado read-mostly con un botón "abrir" en vez de alta manual).
# ─────────────────────────────────────────────────────────────────────────
class EscenariosListado(ListadoPopup):
    def __init__(self, on_abrir=None, **kwargs):
        self._on_abrir = on_abrir
        super().__init__(
            _("Escenarios guardados"),
            [_("ID"), _("Nombre"), _("Estado"), _("Cambios"), _("Última edición")],
            **kwargs)
        # No hay alta manual desde este listado — un escenario nuevo se
        # crea con "🆕 Escenario" en el diagrama (mismo criterio que
        # HistorialDiagnosticosListado.nuevo con las sesiones de
        # diagnóstico). "Editar" se reetiqueta a "Abrir": mantener
        # presionada una fila (o el botón) carga ese escenario en el
        # diagrama y cierra este listado.
        self.btn_agregar.opacity = 0
        self.btn_agregar.disabled = True
        self.btn_agregar.size_hint_x = None
        self.btn_agregar.width = 0
        self.btn_editar.text = _("Abrir")
        self.cargar_datos()

    def cargar_datos(self):
        # Modelo.devolver_todos_los_escenarios() -> (id, nombre,
        # descripcion, estado, fecha_ultima_edicion_o_creacion, n_cambios)
        filas = Modelo.devolver_todos_los_escenarios()
        datos = [(f[0], f[1], f[3], f[5], f[4]) for f in filas]
        self._poblar(datos)

    def nuevo(self):
        mostrar_info(_(
            'Los escenarios se crean con "🆕 Escenario" en el diagrama '
            "de conexiones, no se pueden dar de alta desde acá."))

    def editar(self, id_):
        self.dismiss()
        if self._on_abrir:
            self._on_abrir(id_)

    def eliminar(self, id_):
        Modelo.eliminar_escenario(id_)


# ─────────────────────────────────────────────────────────────────────────
# Panel flotante de resumen — equivalente a _esc_draw_hint/_esc_draw_panel
# (GTK), con widgets reales en vez de texto dibujado a mano (ver docstring
# del módulo). Mismo mecanismo de tarjeta flotante que PanelDiagnostico
# (canvas.before con fondo/borde redondeado, geometría atada a un
# `contenedor` FloatLayout, blindaje de toques para no perforar el gesto
# hacia el diagrama de abajo), pero anclada arriba-derecha en vez de
# abajo-centro.
# ─────────────────────────────────────────────────────────────────────────
class PanelEscenario(BoxLayout):

    ANCHO = dp(280)
    ALTO_FRAC_MAX = 0.62
    ALTO_MIN = dp(64)
    MARGEN = dp(10)
    _ALTO_CABECERA = dp(26)

    def __init__(self, contenedor, **kwargs):
        self._contenedor = contenedor
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("width", self.ANCHO)
        kwargs.setdefault("spacing", dp(4))
        kwargs.setdefault("padding", dp(10))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.11, 0.10, 0.16, 0.92)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(10)])
            Color(0.55, 0.35, 0.10, 0.95)
            self._borde = Line(
                rounded_rectangle=(*self.pos, *self.size, dp(10)), width=1.3)
        self.bind(pos=self._actualizar_fondo, size=self._actualizar_fondo)

        hdr = BoxLayout(size_hint_y=None, height=self._ALTO_CABECERA)
        self._lbl_titulo = Label(
            text=_("🧪 Escenario"), bold=True, font_size=FUENTE_CHICA,
            color=(0.98, 0.75, 0.25, 1), halign="left", valign="middle",
            shorten=True, shorten_from="right")
        self._lbl_titulo.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        hdr.add_widget(self._lbl_titulo)
        self.add_widget(hdr)

        scroll = ScrollView(do_scroll_x=False)
        self._area = BoxLayout(orientation="vertical", spacing=dp(3),
                               padding=(0, dp(2)), size_hint_y=None)
        self._area.bind(minimum_height=lambda *_a: self._actualizar_alto())
        scroll.add_widget(self._area)
        self.add_widget(scroll)

        if self._contenedor is not None:
            self._contenedor.add_widget(self)
            self._contenedor.bind(size=lambda *_a: self._reposicionar())
        self._actualizar_alto()

    # ── Geometría: tarjeta flotante, arriba-derecha del contenedor (GTK:
    # px=W-PW-10, py=10), con alto acotado a una fracción del disponible
    # y scroll interno si el contenido no entra. ──
    def _actualizar_fondo(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._borde.rounded_rectangle = (*self.pos, *self.size, dp(10))

    def _actualizar_alto(self, *_a):
        disp_h = (self._contenedor.height if self._contenedor else 0) or dp(500)
        alto_max = disp_h * self.ALTO_FRAC_MAX
        deseado = (self._ALTO_CABECERA + self.spacing
                  + self._area.minimum_height + dp(20))
        self.height = max(self.ALTO_MIN, min(deseado, alto_max))
        self._reposicionar()

    def _reposicionar(self, *_a):
        if self._contenedor is None:
            return
        self.width = min(self.ANCHO,
                         max(dp(180), self._contenedor.width - self.MARGEN * 2))
        self.x = self._contenedor.x + self._contenedor.width - self.width - self.MARGEN
        self.y = self._contenedor.y + self._contenedor.height - self.height - self.MARGEN

    def quitar(self) -> None:
        if self.parent is not None:
            self.parent.remove_widget(self)

    # ── Blindaje de toques — idéntico criterio que PanelDiagnostico: un
    # toque sobre el fondo/padding de la tarjeta (fuera de cualquier
    # hijo) no debe perforar hacia el canvas del diagrama, hermano en
    # `contenedor`. ──
    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        return self.collide_point(*touch.pos)

    def on_touch_move(self, touch):
        if super().on_touch_move(touch):
            return True
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if super().on_touch_up(touch):
            return True
        return self.collide_point(*touch.pos)

    # ── Contenido ────────────────────────────────────────────────────────
    def mostrar_hint(self) -> None:
        """Equivalente a _esc_draw_hint (GTK): modo activo, sin cambios
        todavía."""
        self._lbl_titulo.text = _("🧪 MODO ESCENARIO")
        self._area.clear_widgets()
        self._area.add_widget(_label_wrap(_(
            "Tocá un EQUIPO para marcar falla, tocá un CABLE para "
            "cortarlo."), font_size=FUENTE_CHICA))
        self._area.add_widget(_label_wrap(_(
            "🔗 Reconexión: activá el botón y arrastrá de un puerto a "
            "otro."), font_size=sp(10),
            color=(0.85, 0.75, 0.55, 1)))
        self._actualizar_alto()

    def mostrar_resultado(self, esc, resultado, senales_cache) -> None:
        """Equivalente a _esc_draw_panel (GTK)."""
        nombre = esc.nombre if esc.id_escenario is not None else _("(sin guardar)")
        self._lbl_titulo.text = f"🧪 {nombre}"
        self._area.clear_widgets()

        def linea(texto, color=(0.91, 0.91, 0.91, 1), bold=False,
                  font_size=FUENTE_CHICA):
            self._area.add_widget(_label_wrap(
                texto, color=color, bold=bold, font_size=font_size))

        fallados  = [c for c in esc.cambios if c.tipo == "falla_equipo"]
        cortados  = [c for c in esc.cambios if c.tipo == "desconexion_cable"]
        virtuales = [c for c in esc.cambios if c.tipo == "conexion_virtual"]

        if fallados:
            linea(_("🔺 {} equipo(s) fallado(s)").format(len(fallados)), bold=True)
        if cortados:
            linea(_("✕ {} cable(s) cortado(s)").format(len(cortados)), bold=True)
        if virtuales:
            linea(_("🔗 {} reconexión(es) virtual(es)").format(len(virtuales)),
                  bold=True)

        r = resultado
        if r is None:
            linea(_("(calculando…)"), color=(0.7, 0.7, 0.7, 1))
        elif not r.hay_impacto and not r.equipos_impactados_sin_reconexion:
            linea(_("✓ Sin impacto detectado."), color=(0.30, 0.80, 0.35, 1))
        else:
            antes = len(r.equipos_impactados_sin_reconexion)
            despues = len(r.equipos_impactados)
            if virtuales:
                linea(_("Consumidores afectados: {} → {}").format(antes, despues),
                      bold=True)
                if r.equipos_recuperados:
                    linea(_("  ✓ {} recuperado(s) por la reconexión").format(
                        len(r.equipos_recuperados)), color=(0.15, 0.75, 0.30, 1))
            else:
                linea(_("{} equipo(s) quedan sin señal").format(despues), bold=True)

            if r.causas_regla:
                for texto_causa in list(r.causas_regla.values())[:4]:
                    linea(f"⚠ {texto_causa}", color=(0.85, 0.65, 0.15, 1),
                          font_size=sp(10))

        nombres_senal = sorted({
            info["nombre_senal"] for info in senales_cache.values()
            if info.get("nombre_senal")
        })
        if nombres_senal:
            linea(_("📡 {} señal(es) se pierden:").format(len(nombres_senal)),
                  bold=True)
            for nombre_s in nombres_senal[:6]:
                linea(f"  • {nombre_s}", color=(0.85, 0.75, 0.55, 1),
                      font_size=sp(10))
            if len(nombres_senal) > 6:
                linea(_("  … y {} más").format(len(nombres_senal) - 6),
                      color=(0.65, 0.60, 0.50, 1), font_size=sp(10))

        if esc.id_escenario is None:
            linea(_("(guardalo con 💾 para no perderlo)"),
                  color=(0.65, 0.65, 0.70, 1), font_size=sp(10))

        self._actualizar_alto()
