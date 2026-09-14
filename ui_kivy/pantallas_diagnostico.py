"""
CableDoc Kivy - Asistente de diagnóstico de fallas.

Fase 5, ítem 1 del roadmap de paridad de pantallas nuevas — ver
ROADMAP_FASE5_paridad_pantallas.md. Equivalente a diagnostico_ui.py (GTK):
reutiliza sin ningún cambio core/diagnostico_falla.py
(MotorDiagnostico/SesionDiagnostico), que ya es 100% independiente de
GTK/Kivy. La bisección real vive ahí; este archivo sólo la envuelve en
pantallas táctiles.

CORRECCIÓN DE ARQUITECTURA (post primera entrega de este ítem): la
primera versión abría el asistente desde un selector independiente
equipo → conector (abrir_diagnostico_elegir), fuera del diagrama. Eso
estaba mal: el diagnóstico parte de un conector síntoma concreto y va
sugiriendo puntos VECINOS de esa misma cadena de señal para ir
descartando por bisección — no tiene sentido elegir el síntoma "a
ciegas" desde un listado cuando lo natural es tocarlo directamente en
el lugar donde ya se lo está mirando: el diagrama de conexiones. GTK
nunca tuvo un selector aparte por esta misma razón (ver diagnostico_ui.py:
el asistente arranca con un clic sobre un puerto de DiagramaConexiones,
modo activable con un toggle del propio diagrama).

Arquitectura corregida, ahora igual a GTK: `abrir_diagnostico_elegir` se
eliminó. El punto de entrada es `pantallas_diagrama.DiagramaConexiones`
— el botón toggle "🩺 Diagnóstico" de su barra de herramientas activa un
modo en el que tocar un puerto (IN u OUT, ya dibujado — sólo visible
cuando el nodo no está en modo "Solo nombre") abre directamente
`PanelDiagnostico` para ESE conector, vía
`DiagramaConexiones._diag_abrir_puerto()` (ver pantallas_diagrama.py).
Este archivo ya no decide cuándo/cómo se elige el síntoma, sólo expone
`PanelDiagnostico` para que el diagrama lo instancie.

`PanelDiagnostico` recibe `diagrama=` (la instancia de
DiagramaConexiones) para poder panear el canvas hacia cada equipo que se
va sugiriendo a medida que avanza la bisección — igual que
`_panear_a_equipo` en GTK (`_DialogoDiagnostico`). Si se instancia sin
`diagrama` (no debería pasar desde el flujo normal, pero no se exige por
si algún día hace falta un caso de prueba aislado) simplemente no panea
nada.

CORRECCIÓN 2 (este cambio): `PopupDiagnostico` — heredaba de
`kivy.uix.popup.Popup` con `size_hint=(1, 1)` — tapaba la pantalla
COMPLETA con su overlay oscuro. La idea de GTK (`_DialogoDiagnostico`,
un `Gtk.Dialog` chico y explícitamente NO modal, ver diagnostico_ui.py)
es que el asistente se vea flotando sobre el diagrama, que sigue
paneándose/zoomándose solo detrás a medida que se contesta cada
pregunta (`_panear_a_equipo`) — el cliente necesita ver ADÓNDE está
paneando el diagrama en cada paso. Con un Popup fullscreen eso es
imposible: por más que Kivy no lo llame "modal", su overlay cubre y
captura toques en TODA la ventana, así que en la práctica el usuario
sólo veía una pantalla negra con la pregunta, sin ningún diagrama de
referencia atrás. La nota que decía "el diagrama sigue paneable/zoomable
detrás del Popup" (versión anterior de este docstring) era incorrecta —
quedaba tapado igual que si fuera modal.

Fix: `PanelDiagnostico` ya NO es un Popup — es un `BoxLayout` con fondo
propio (tarjeta chica, ancho acotado, alto acotado a una fracción del
canvas, con scroll interno si el contenido no entra) que se agrega
directamente como hijo del `FloatLayout` que ya aloja el canvas del
diagrama y el minimapa (`DiagramaConexiones._canvas_cont`). Un
`FloatLayout` sólo intercepta el toque dentro del rectángulo de cada
hijo — nunca fuera de él — así que el resto de la pantalla (el
diagrama) queda tocable/paneable/zoomable con la tarjeta abierta, igual
que con el diálogo no-modal de GTK, sin necesitar ningún Popup ni ningún
ajuste de modalidad.

No portado de GTK (fuera de alcance de este ítem, no bloquea el resto —
se puede agregar después sin tocar el motor):
  - Convivencia con Vista Previa/Escenario/Impacto: esos mixins de
    diagrama todavía no existen en mobile (ítems 2-4 del roadmap), así
    que no hay con qué excluirse todavía — ver comentario en
    `DiagramaConexiones._diag_activar` (pantallas_diagrama.py) para
    cuándo agregar la exclusión mutua el día que esos modos existan.
  - "Prontuario" filtrado por equipo/cable (abrir_historial_diagnosticos
    con id_equipo/id_cable, como en equipos_ui.py/cables_conexiones_ui.py
    de GTK, llamado desde la ficha de cada entidad): la función ya
    soporta esos filtros, sólo falta agregar el botón en las pantallas
    de ficha de equipo/cable de mobile cuando se ataque ese ítem.
"""

from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from tema import tema, BotonIcono
from widgets_base import (
    ListadoPopup, ComboBuscable, barra_superior_dialogo, fila_botones_pill,
    mostrar_info, _, FUENTE_NORMAL, FUENTE_CHICA, FUENTE_TITULO,
)
from core.modelo import Modelo, DB_PATH
from core.diagnostico_falla import MotorDiagnostico, SesionDiagnostico


def abrir_historial_diagnosticos(*_a, id_cable=None, id_equipo=None):
    HistorialDiagnosticosListado(id_cable=id_cable, id_equipo=id_equipo).open()


def _label_wrap(texto, **kw):
    """Label de una sola columna con alto automático según el texto —
    mismo idioma que fila_auditoria en widgets_base.py: text_size ligado
    al ancho disponible, height ligado a texture_size una vez layouteado."""
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "top")
    kw.setdefault("font_size", FUENTE_NORMAL)
    kw.setdefault("size_hint_y", None)
    lbl = Label(text=texto, **kw)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    lbl.bind(texture_size=lambda w, *_a: setattr(w, "height", w.texture_size[1]))
    return lbl


# ─────────────────────────────────────────────────────────────────────────
# Wizard de bisección — equivalente a _DialogoDiagnostico (GTK). Misma
# máquina de estados: (1) resolver bifurcaciones si las hay, antes de
# empezar; (2) bisección Sí/No/No sé/Atrás hasta convergencia.
#
# Ya NO es un Popup — ver la corrección explicada en el docstring del
# módulo. Es una tarjeta chica (BoxLayout con fondo propio) que se agrega
# como hijo de `contenedor` (el FloatLayout que ya aloja el canvas del
# diagrama y el minimapa), flotando sobre él sin taparlo por completo.
# ─────────────────────────────────────────────────────────────────────────
class PanelDiagnostico(BoxLayout):

    ANCHO_MAX = dp(340)       # ancho máximo de la tarjeta
    ALTO_FRAC_MAX = 0.46      # alto máximo, como fracción del contenedor
    ALTO_MIN = dp(140)        # piso, para que no quede achatada mientras carga
    MARGEN = dp(12)           # margen respecto de los bordes del contenedor
    _ALTO_CABECERA = dp(30)

    def __init__(self, id_conector_sintoma, titulo_sintoma, diagrama=None,
                contenedor=None, **kwargs):
        """diagrama: la instancia de DiagramaConexiones — hace falta
        acceso real a `_centrar_en_equipo` para poder panear el canvas
        hacia el equipo de cada punto que se va proponiendo (ver
        _render_pregunta más abajo), mismo motivo que GTK guarda
        `self._diagrama` en `_DialogoDiagnostico`. Puede quedar en None
        (no panea nada) si algún día hace falta instanciar este panel
        fuera del flujo normal (p. ej. un test aislado).

        contenedor: el FloatLayout donde se superpone la tarjeta (en el
        flujo normal, `DiagramaConexiones._canvas_cont` — el mismo que
        ya contiene `_CanvasDiagrama` y el minimapa). La tarjeta se
        agrega sola a `contenedor` acá adentro; si se omite, el panel se
        arma igual pero no se muestra hasta que alguien lo agregue a
        mano a un padre."""
        self._diagrama = diagrama
        self._contenedor = contenedor
        self._id_conector_sintoma = str(id_conector_sintoma)
        self._titulo_sintoma = titulo_sintoma
        self._motor = MotorDiagnostico(DB_PATH)
        self._ramas_elegidas = {}
        self._sesion = None
        self._motivo_corte_actual = None
        self._orden_paso = 0
        self._punto_actual = None
        # Callback opcional que fija el llamador (ver
        # DiagramaConexiones._diag_abrir_puerto) para enterarse cuando la
        # tarjeta se cierra — reemplaza a `Popup.bind(on_dismiss=...)`.
        self.on_cerrar = None

        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("spacing", dp(6))
        kwargs.setdefault("padding", dp(10))
        super().__init__(**kwargs)

        # ── Fondo tipo tarjeta + sombra + borde de acento — para que se
        # distinga con claridad del canvas del diagrama, que sigue
        # visible (y tocable) alrededor y detrás de ella. ──
        with self.canvas.before:
            Color(0, 0, 0, 0.32)
            self._sombra = RoundedRectangle(
                pos=(self.x + dp(3), self.y - dp(3)), size=self.size,
                radius=[dp(14)])
            self._c_fondo = Color(*tema.c("superficie"))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(14)])
            self._c_borde = Color(*tema.c("primario"))
            self._borde = Line(
                rounded_rectangle=(*self.pos, *self.size, dp(14)), width=1.4)
        self.bind(pos=self._actualizar_fondo, size=self._actualizar_fondo)
        tema.bind(modo=lambda *_a: self._actualizar_colores_tema())

        # ── Cabecera compacta: título + cerrar (reemplaza a
        # barra_superior_dialogo, pensada para Popups a pantalla
        # completa — acá no entra cómoda en una tarjeta chica) ──
        hdr = BoxLayout(size_hint_y=None, height=self._ALTO_CABECERA,
                        spacing=dp(6))
        self._lbl_titulo = Label(
            text=_("🩺 Diagnóstico — {}").format(titulo_sintoma),
            bold=True, font_size=FUENTE_CHICA, color=tema.c("texto"),
            halign="left", valign="middle", shorten=True,
            shorten_from="right")
        self._lbl_titulo.bind(
            size=lambda w, *_a: setattr(w, "text_size", w.size))
        hdr.add_widget(self._lbl_titulo)
        btn_cerrar = BotonIcono(icono="cerrar", clave_icono="texto",
                               tamano=dp(26))
        btn_cerrar.bind(on_release=lambda *_a: self.cerrar())
        hdr.add_widget(btn_cerrar)
        self.add_widget(hdr)

        # ── Cuerpo con scroll propio — la pregunta + botones a veces no
        # entra en el alto máximo acotado de la tarjeta. ──
        scroll = ScrollView(do_scroll_x=False)
        self._area = BoxLayout(orientation="vertical", spacing=dp(10),
                               padding=(0, dp(2)), size_hint_y=None)
        self._area.bind(minimum_height=lambda *_a: self._actualizar_alto())
        scroll.add_widget(self._area)
        self.add_widget(scroll)

        # La sesión se crea en el historial apenas se abre el asistente
        # (igual que en GTK): si se cierra la tarjeta a mitad de camino
        # sin llegar al resultado, la sesión queda con fecha_fin=NULL en
        # vez de perderse — permite ver más adelante "diagnósticos
        # abandonados" en el historial si algún día hace falta.
        self._id_sesion_bd = Modelo.crear_sesion_diagnostico(id_conector_sintoma)

        if self._contenedor is not None:
            self._contenedor.add_widget(self)
            self._contenedor.bind(size=lambda *_a: self._reposicionar())
        self._actualizar_alto()
        Clock.schedule_once(lambda *_a: self._avanzar(), 0)

    # ── Geometría: tarjeta flotante, anclada abajo-centro del
    # contenedor, con alto acotado a una fracción del alto disponible
    # (deja libre la parte superior del canvas — donde queda el equipo
    # que `_centrar_en_equipo` acaba de encuadrar en cada pregunta). ──
    def _actualizar_fondo(self, *_a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._sombra.pos = (self.x + dp(3), self.y - dp(3))
        self._sombra.size = self.size
        self._borde.rounded_rectangle = (*self.pos, *self.size, dp(14))

    def _actualizar_colores_tema(self, *_a):
        self._c_fondo.rgba = tema.c("superficie")
        self._c_borde.rgba = tema.c("primario")
        self._lbl_titulo.color = tema.c("texto")

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
        disp_w = self._contenedor.width or self.ANCHO_MAX
        self.width = min(self.ANCHO_MAX, max(dp(200), disp_w - self.MARGEN * 2))
        self.x = self._contenedor.x + (self._contenedor.width - self.width) / 2
        self.y = self._contenedor.y + self.MARGEN

    def cerrar(self) -> None:
        """Reemplaza a Popup.dismiss(): saca la tarjeta de su contenedor
        y avisa al llamador (ver on_cerrar / DiagramaConexiones.
        _diag_abrir_puerto, que lo usa para volver a permitir abrir otra
        sesión de diagnóstico)."""
        if self.parent is not None:
            self.parent.remove_widget(self)
        if self.on_cerrar:
            self.on_cerrar()

    # ── Blindaje de toques: un BoxLayout normal sólo "consume" el touch
    # si algún hijo lo consumió (botón, TextInput, etc.) — un toque sobre
    # el fondo/padding de la tarjeta (fuera de cualquier hijo) se dejaría
    # pasar al canvas de abajo (_CanvasDiagrama, hermano en `contenedor`)
    # y movería/paearía el diagrama sin querer, justo detrás de la
    # tarjeta. Se pide primero el manejo normal (así los hijos siguen
    # funcionando igual) y, si el toque cae dentro del rectángulo de la
    # tarjeta y nadie lo consumió, igual se lo traga acá — la tarjeta se
    # comporta como una superficie propia, sin perforar el gesto hacia
    # el diagrama, sin necesitar `disabled=True` (que también bloquearía
    # sus propios botones). ──
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

    # ── Helpers de layout ──────────────────────────────────────────────
    def _limpiar_area(self):
        self._area.clear_widgets()

    # ── Máquina de estados del wizard ───────────────────────────────────
    def _avanzar(self):
        """Reconstruye la cadena con las ramas ya elegidas hasta ahora; si
        hay una bifurcación nueva, la pregunta; si no, arranca/continúa la
        bisección."""
        res = self._motor.construir_cadena(
            self._id_conector_sintoma, ramas_elegidas=self._ramas_elegidas)

        if res.categoria_corte == "BIFURCACION":
            self._mostrar_bifurcacion(res)
            return

        if self._sesion is None:
            if len(res.pasos) < 2:
                self._mostrar_mensaje(
                    _("La cadena documentada para este punto es demasiado "
                      "corta para diagnosticar (no hay nada aguas arriba "
                      "para comparar)."))
                return
            self._sesion = SesionDiagnostico(res.pasos)
            self._motivo_corte_actual = res.motivo_corte
        else:
            self._sesion.pasos = res.pasos

        self._siguiente_pregunta()

    def _mostrar_bifurcacion(self, res):
        self._limpiar_area()
        bif = res.bifurcacion
        self._area.add_widget(_label_wrap(
            _("El equipo «{}» combina {} entradas distintas. ¿Cuál de "
              "ellas corresponde a la señal que falta?").format(
                  bif.nombre_equipo, len(bif.opciones)),
            font_size=FUENTE_NORMAL))

        combo = ComboBuscable(datos=[(cid, nombre) for cid, nombre in bif.opciones])
        combo.set_id(bif.opciones[0][0])
        self._area.add_widget(combo)

        def _elegir():
            self._ramas_elegidas[bif.id_equipo] = combo.get_id()
            self._avanzar()

        self._area.add_widget(fila_botones_pill([
            {"texto": _("Continuar →"), "icono": "chevron_derecha",
             "estilo": "primario", "on_release": _elegir},
        ]))

    def _siguiente_pregunta(self):
        if self._sesion.convergido():
            self._mostrar_resultado()
            return

        sig = self._sesion.siguiente_punto()
        if sig is None:
            self._mostrar_seleccion_manual()
            return
        self._punto_actual = sig
        self._render_pregunta(sig[1], manual=False)

    def _mostrar_seleccion_manual(self):
        """No hay ningún punto marcado 'de test' en el tramo vigente — se
        avisa y se deja elegir a mano en vez de improvisar con un punto
        incómodo (mismo criterio que GTK, sección 6.3 del plan)."""
        self._limpiar_area()
        self._area.add_widget(_label_wrap(
            _("No hay ningún punto marcado como 'de test' en el tramo que "
              "queda por revisar. Elegí manualmente por dónde seguir:")))

        opciones = [
            (i, f"{self._sesion.pasos[i].nombre_equipo} / "
                f"{self._sesion.pasos[i].nombre}")
            for i in range(self._sesion.lo + 1, self._sesion.hi)
        ]
        combo = ComboBuscable(datos=opciones)
        if opciones:
            combo.set_id(opciones[0][0])
        self._area.add_widget(combo)

        def _elegir():
            idx_txt = combo.get_id()
            if not idx_txt:
                return
            idx, paso = self._sesion.elegir_manual(int(idx_txt))
            self._punto_actual = (idx, paso)
            self._render_pregunta(paso, manual=True)

        self._area.add_widget(fila_botones_pill([
            {"texto": _("Preguntar acá →"), "icono": "chevron_derecha",
             "estilo": "primario", "on_release": _elegir},
        ]))

    def _panear_a_equipo(self, id_equipo) -> None:
        """Centra el diagrama en el equipo del punto que se acaba de
        proponer para revisar — mismo motivo y mismo nombre que
        `_panear_a_equipo` en GTK (_DialogoDiagnostico): antes había que
        ir a buscarlo a mano en un diagrama grande cada vez que el
        asistente sugería un punto nuevo. Reutiliza el pan+zoom que ya
        expone `DiagramaConexiones._centrar_en_equipo` (mismo mecanismo
        que usa el buscador del propio diagrama)."""
        if self._diagrama is not None:
            self._diagrama._centrar_en_equipo(id_equipo)

    def _render_pregunta(self, paso, manual: bool) -> None:
        self._limpiar_area()
        self._panear_a_equipo(paso.id_equipo)
        restantes = self._sesion.hi - self._sesion.lo
        self._area.add_widget(_label_wrap(
            _("¿Hay señal en «{} / {}»?").format(
                paso.nombre_equipo, paso.nombre),
            font_size=FUENTE_TITULO, bold=True))
        sub = (_("(elegido a mano)") if manual
               else _("punto sugerido por bisección"))
        self._area.add_widget(_label_wrap(
            f"{sub} — {_('tramo restante')}: {restantes} paso(s)",
            font_size=FUENTE_CHICA))

        self._area.add_widget(fila_botones_pill([
            {"texto": _("✅ Sí hay señal"), "estilo": "primario",
             "on_release": lambda: self._responder("SI")},
            {"texto": _("❌ No hay señal"), "estilo": "secundario",
             "on_release": lambda: self._responder("NO")},
        ]))
        botones_fila2 = [
            {"texto": _("🤷 No pude verificar"), "estilo": "terciario",
             "on_release": lambda: self._responder("NO_SE")},
        ]
        if self._sesion.historial:
            botones_fila2.append({
                "texto": _("⬅ Atrás"), "icono": "atras", "estilo": "terciario",
                "on_release": self._deshacer,
            })
        self._area.add_widget(fila_botones_pill(botones_fila2))

    def _responder(self, respuesta: str) -> None:
        idx, paso = self._punto_actual
        self._sesion.responder(idx, respuesta)
        Modelo.agregar_paso_diagnostico(
            self._id_sesion_bd, paso.id_conector, respuesta, self._orden_paso)
        self._orden_paso += 1
        self._siguiente_pregunta()

    def _deshacer(self) -> None:
        if self._sesion.deshacer():
            Modelo.quitar_ultimo_paso_diagnostico(self._id_sesion_bd)
            self._orden_paso = max(0, self._orden_paso - 1)
        self._siguiente_pregunta()

    def _mostrar_resultado(self) -> None:
        self._limpiar_area()
        sin_senal, con_senal = self._sesion.resultado()
        if sin_senal.id_equipo == con_senal.id_equipo:
            texto = _(
                "Sospechoso: el equipo «{}» — revisar su conexión interna "
                "o alimentación (entre «{}» y «{}»).").format(
                    sin_senal.nombre_equipo, sin_senal.nombre, con_senal.nombre)
            resultado_tipo = "EQUIPO_SOSPECHOSO"
            id_cable = None
            id_equipo = sin_senal.id_equipo
        else:
            id_cable = self._buscar_cable_entre(
                sin_senal.id_conector, con_senal.id_conector)
            if id_cable:
                texto = _(
                    "Sospechoso: el cable entre «{} / {}» y «{} / {}».").format(
                        sin_senal.nombre_equipo, sin_senal.nombre,
                        con_senal.nombre_equipo, con_senal.nombre)
            else:
                texto = _(
                    "Sospechoso: el tramo entre «{} / {}» y «{} / {}» (no "
                    "se encontró un único cable directo — revisar ese "
                    "segmento a mano).").format(
                        sin_senal.nombre_equipo, sin_senal.nombre,
                        con_senal.nombre_equipo, con_senal.nombre)
            resultado_tipo = "CABLE_SOSPECHOSO"
            id_equipo = None

        self._area.add_widget(_label_wrap(
            _("🎯 Diagnóstico"), font_size=FUENTE_TITULO, bold=True))
        self._area.add_widget(_label_wrap(texto))

        self._area.add_widget(_label_wrap(
            _("Descripción del síntoma (opcional):"), font_size=FUENTE_CHICA))
        entry = TextInput(multiline=False, font_size=FUENTE_NORMAL,
                          size_hint_y=None, height=dp(42))
        entry.hint_text = _('ej. "no hay aire", "monitor frizado"...')
        self._area.add_widget(entry)

        estado = {"guardado": False}

        def _guardar():
            if estado["guardado"]:
                return
            if entry.text.strip():
                Modelo._exec(
                    "UPDATE diagnostico_sesion SET descripcion=? WHERE id_sesion=?",
                    (entry.text.strip(), self._id_sesion_bd))
            Modelo.cerrar_sesion_diagnostico(
                self._id_sesion_bd, resultado_tipo,
                id_cable_resultado=id_cable, id_equipo_resultado=id_equipo)
            estado["guardado"] = True
            mostrar_info(_("Sesión guardada en el historial."))

        self._area.add_widget(fila_botones_pill([
            {"texto": _("💾 Guardar en historial"), "icono": "guardar",
             "estilo": "primario", "on_release": _guardar},
        ]))

    def _mostrar_mensaje(self, texto: str) -> None:
        self._limpiar_area()
        self._area.add_widget(_label_wrap(texto))

    def _buscar_cable_entre(self, id_conector_a, id_conector_b):
        r = Modelo._query(
            "SELECT cx1.id_cable FROM conexion cx1 JOIN conexion cx2 "
            "ON cx1.id_cable = cx2.id_cable AND cx1.id_conector != cx2.id_conector "
            "WHERE cx1.id_conector=? AND cx2.id_conector=?",
            (id_conector_a, id_conector_b))
        return r[0][0] if r else None


# ─────────────────────────────────────────────────────────────────────────
# Historial de diagnósticos ("prontuario") — equivalente a
# HistorialDiagnosticosListado/_DialogoDetalleSesion (GTK). A diferencia
# del resto de las pantallas de este archivo, SÍ reutiliza ListadoPopup
# (no vale la pena duplicar el RecycleView virtualizado a mano como hace
# GTK con un TreeView propio): "Agregar" se oculta porque una sesión sólo
# se crea completa desde el propio asistente, nunca a mano, y "Editar" se
# reutiliza tal cual para abrir el detalle de sólo lectura (mismo gesto —
# mantener presionado — que ya usa toda la app para "ver más").
# ─────────────────────────────────────────────────────────────────────────
_ETIQUETA_RESULTADO = {
    "CABLE_SOSPECHOSO": "Cable", "EQUIPO_SOSPECHOSO": "Equipo",
    "ABANDONADO": "Abandonado",
}


class HistorialDiagnosticosListado(ListadoPopup):
    def __init__(self, id_cable=None, id_equipo=None, **kwargs):
        self._id_cable = id_cable
        self._id_equipo = id_equipo
        titulo = _("Historial de diagnósticos")
        if id_cable:
            titulo += f" — {_('cable')} {id_cable}"
        elif id_equipo:
            titulo += f" — {_('equipo')} {id_equipo}"
        super().__init__(
            titulo, [_("ID"), _("Inicio"), _("Equipo síntoma"),
                    _("Descripción"), _("Resultado"), _("Sospechoso")],
            **kwargs)
        # No hay alta manual de sesiones — se ocultan Agregar/Editar tal
        # como los rotula ListadoPopup, dejando "Ver detalle" en su lugar
        # (mismo botón físico, reetiquetado — evita duplicar el
        # RecycleView de ListadoPopup sólo para cambiar dos textos).
        self.btn_agregar.opacity = 0
        self.btn_agregar.disabled = True
        self.btn_agregar.size_hint_x = None
        self.btn_agregar.width = 0
        self.btn_editar.text = _("Ver detalle")
        self.cargar_datos()

    def cargar_datos(self):
        filas = Modelo.historial_diagnosticos(
            id_cable=self._id_cable, id_equipo=self._id_equipo, limite=200)
        datos = [
            (f["id_sesion"], f["fecha_inicio"] or "", f["equipo_sintoma"] or "",
             f["descripcion"] or "",
             _ETIQUETA_RESULTADO.get(f["resultado"], f["resultado"] or ""),
             f["cable_resultado"] or f["equipo_resultado"] or "")
            for f in filas
        ]
        self._poblar(datos)

    def nuevo(self):
        mostrar_info(_(
            "Las sesiones de diagnóstico se crean desde el asistente "
            "(🩺 Diagnosticar falla), no se pueden dar de alta a mano acá."))

    def editar(self, id_):
        PopupDetalleSesion(id_).open()

    def eliminar(self, id_):
        Modelo.eliminar_sesion_diagnostico(id_)


class PopupDetalleSesion(Popup):
    def __init__(self, id_sesion, **kwargs):
        cabecera, pasos = Modelo.detalle_sesion_diagnostico(id_sesion)
        super().__init__(title="", separator_height=0, size_hint=(1, 1),
                         **kwargs)
        self._armar(id_sesion, cabecera, pasos)

    def _armar(self, id_sesion, cabecera, pasos):
        raiz = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        raiz.add_widget(barra_superior_dialogo(
            _("Sesión de diagnóstico #{}").format(id_sesion),
            on_atras=lambda: self.dismiss()))

        cuerpo = BoxLayout(orientation="vertical", spacing=dp(6),
                           padding=dp(4), size_hint_y=None)
        cuerpo.bind(minimum_height=cuerpo.setter("height"))

        if cabecera is None:
            cuerpo.add_widget(_label_wrap(_("Sesión no encontrada.")))
        else:
            sospechoso = (cabecera["cable_resultado"]
                         or cabecera["equipo_resultado"] or "—")
            resultado = _ETIQUETA_RESULTADO.get(
                cabecera["resultado"], cabecera["resultado"] or "—")
            lineas = [
                _("Síntoma: {} / {}").format(
                    cabecera["equipo_sintoma"], cabecera["conector_sintoma"]),
                _("Descripción: {}").format(
                    cabecera["descripcion"] or _("(sin descripción)")),
                _("Resultado: {} — {}").format(resultado, sospechoso),
                _("Inicio: {}    Fin: {}").format(
                    cabecera["fecha_inicio"] or "—",
                    cabecera["fecha_fin"] or "—"),
            ]
            for linea in lineas:
                cuerpo.add_widget(_label_wrap(linea))

            cuerpo.add_widget(_label_wrap(
                _("Pasos:"), font_size=FUENTE_CHICA, bold=True))
            iconos_resp = {"SI": "✅ Sí", "NO": "❌ No", "NO_SE": "🤷 No sé"}
            for p in pasos:
                cuerpo.add_widget(_label_wrap(
                    f"{p['orden'] + 1}. {p['equipo']} / {p['conector']} — "
                    f"{iconos_resp.get(p['respuesta'], p['respuesta'])}",
                    font_size=FUENTE_CHICA))

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(cuerpo)
        raiz.add_widget(scroll)
        self.content = raiz
