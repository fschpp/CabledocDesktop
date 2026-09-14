"""
CableDoc Kivy - Asistente de diagnóstico de fallas.

Fase 5, ítem 1 del roadmap de paridad de pantallas nuevas — ver
ROADMAP_FASE5_paridad_pantallas.md. Equivalente a diagnostico_ui.py (GTK):
reutiliza sin ningún cambio core/diagnostico_falla.py
(MotorDiagnostico/SesionDiagnostico), que ya es 100% independiente de
GTK/Kivy. La bisección real vive ahí; este archivo sólo la envuelve en
pantallas táctiles.

Entrada distinta a GTK, a propósito: en GTK el asistente arranca con un
clic sobre un puerto de DiagramaConexiones. Acá NO depende de que exista
el diagrama de conexiones en mobile ni de que el usuario esté parado en
él (aunque sí existe, ver pantallas_diagrama.py) — se elige el "conector
síntoma" con el mismo selector en dos pasos (equipo -> conector) que ya
usan abrir_imagen_conectores_elegir/abrir_patcheras_elegir en main.py.
Esto era justamente lo que hacía de Diagnóstico el candidato más simple
para arrancar el roadmap (ver "Orden sugerido" en el roadmap): sin
dibujo custom que portar, sin depender de otras fases mobile pendientes.

No portado de GTK (fuera de alcance de este ítem, no bloquea el resto —
se puede agregar después sin tocar el motor):
  - Paneo automático al equipo sugerido (_panear_a_equipo en GTK): sólo
    tiene sentido si el asistente vive encima del diagrama.
  - Convivencia con Vista Previa/Escenario/Impacto: esos mixins de
    diagrama todavía no existen en mobile (ítems 2-4 del roadmap).
  - Diálogo no-modal: en Kivy los Popup ya no bloquean la ventana
    completa como Gtk.Dialog.run(), así que no hace falta ningún ajuste
    equivalente a set_modal(False).
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from widgets_base import (
    ListadoPopup, ComboBuscable, barra_superior_dialogo, fila_botones_pill,
    mostrar_info, s, _, FUENTE_NORMAL, FUENTE_CHICA, FUENTE_TITULO,
)
from core.modelo import Modelo, DB_PATH
from core.diagnostico_falla import MotorDiagnostico, SesionDiagnostico


# ─────────────────────────────────────────────────────────────────────────
# Punto de entrada: elegir equipo -> conector síntoma, después abrir el
# wizard. Mismo patrón de dos ListadoPopup encadenados que ya usa
# abrir_patcheras_elegir (main.py).
# ─────────────────────────────────────────────────────────────────────────
def abrir_diagnostico_elegir(*_a):
    from pantallas_equipos import EquiposListado

    def _con_equipo(id_equipo, nombre_equipo, _f):
        from pantallas_conectores import ConectoresListado

        def _con_conector(id_conector, nombre_conector, _f2):
            titulo = f"{s(nombre_equipo)} / {s(nombre_conector)}"
            PopupDiagnostico(id_conector, titulo).open()

        ConectoresListado(id_equipo, modo_seleccion=True,
                          on_seleccionar=_con_conector).open()

    EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()


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
# ─────────────────────────────────────────────────────────────────────────
class PopupDiagnostico(Popup):
    def __init__(self, id_conector_sintoma, titulo_sintoma, **kwargs):
        self._id_conector_sintoma = str(id_conector_sintoma)
        self._titulo_sintoma = titulo_sintoma
        self._motor = MotorDiagnostico(DB_PATH)
        self._ramas_elegidas = {}
        self._sesion = None
        self._motivo_corte_actual = None
        self._orden_paso = 0
        self._punto_actual = None

        raiz = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        raiz.add_widget(barra_superior_dialogo(
            _("🩺 Diagnóstico — {}").format(titulo_sintoma),
            on_atras=lambda: self.dismiss()))

        scroll = ScrollView(do_scroll_x=False)
        self._area = BoxLayout(orientation="vertical", spacing=dp(10),
                               padding=dp(4), size_hint_y=None)
        self._area.bind(minimum_height=self._area.setter("height"))
        scroll.add_widget(self._area)
        raiz.add_widget(scroll)

        super().__init__(title="", separator_height=0, content=raiz,
                         size_hint=(1, 1), **kwargs)

        # La sesión se crea en el historial apenas se abre el asistente
        # (igual que en GTK): si se cierra el Popup a mitad de camino sin
        # llegar al resultado, la sesión queda con fecha_fin=NULL en vez
        # de perderse — permite ver más adelante "diagnósticos
        # abandonados" en el historial si algún día hace falta.
        self._id_sesion_bd = Modelo.crear_sesion_diagnostico(id_conector_sintoma)
        self.bind(on_open=lambda *_a: self._avanzar())

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

    def _render_pregunta(self, paso, manual: bool) -> None:
        self._limpiar_area()
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
