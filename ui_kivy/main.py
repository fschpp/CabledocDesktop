#!/usr/bin/env python3
"""
CableDoc Kivy - Punto de entrada y ventana principal.

Equivalente a VentanaPrincipal (GTK). Desde la integración de Fase 3
(plan_integracion_cabledoc_v3.md) usa core/modelo.py y core/i18n.py
COMPARTIDOS con el desktop — ya no una copia propia congelada de
modelo.py/i18n.py. Misma base de datos db.db.

FASES 1 a 6 de la migración GTK -> Kivy completas. Implementado:
    - Ventana principal con menú (dropdown), accesos rápidos y paneles de
      "trabajo pendiente" de Cables y Equipos
    - Catálogos: Marcas, Tipos de Equipo, Tipos de Conector,
      Tipos de Cable, Tipos de Ficha, Imágenes
    - Cables (listado completo + alta/edición/fusión)
    - Equipos (ABM completo + Alta Rápida con plantilla de conectores) y
      sus Conectores (ABM + renombrado en lote)
    - Conexiones (Equipo+Conector <-> Cable)
    - Pantallas avanzadas: selector de coordenadas sobre imagen, imagen
      con conectores superpuestos, árbol de conexiones
    - Racks, Posición en Rack, Frames, Slots, Salas, Rack por Sala,
      Equipos sueltos por Sala
    - Vistas gráficas: VistaRack, VistaFrameSlots, PatcherasVista

Lo que falta (fase 7, opcional/prioridad baja, ver README_MIGRACION.md):
    DiagramaConexiones (depende de impacto_ui.py) y los editores masivos de
    coordenadas/conexiones. Los ítems de menú correspondientes están
    presentes pero muestran un aviso "todavía no migrado" en vez de abrir
    la pantalla.

Uso:
    python3 main.py
"""

import os
import sys

# plan_integracion_cabledoc_v3.md, Fase 3: bootstrap de sys.path para que
# `from core.X import Y` resuelva sin importar cómo se lance este archivo
# (python3 ui_kivy/main.py, acceso directo/ícono en Android, etc.) — agrega
# la raíz del repo (padre de ui_kivy/) al principio de sys.path, una sola
# vez. Mismo criterio que ui_gtk/cabledoc.py (Fase 2).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from kivy.config import Config
from kivy.utils import platform

from core.logger_cabledoc import log_debug
log_debug(f"[inmersivo] arrancando main.py — kivy.utils.platform = {platform!r}")

# Deteccion de Pydroid 3: en Android real platform es 'android', pero en Pydroid 3
# puede reportarse como 'linux'. Verificamos tambien la variable de entorno ANDROID_DATA
is_android = platform == "android" or os.environ.get("ANDROID_DATA") is not None
log_debug(f"[inmersivo] is_android = {is_android}")

if is_android:
    # En Android (incluyendo Pydroid 3), Kivy toma la resolución real del
    # dispositivo (p.ej. 720×1600 px). No forzamos width/height: eso
    # rompería el tamaño real de pantalla. Solo pedimos que no rote sola
    # (la UI está pensada para retrato) — si preferís permitir horizontal,
    # borrá esta línea.
    log_debug("[inmersivo] Configurando orientation=portrait")
    Config.set("graphics", "orientation", "portrait")
    log_debug("[inmersivo] orientation configurado OK")
    
    # Modo inmersivo: oculta la barra de estado y los botones de
    # navegación del sistema (atrás/inicio/recientes) para que la app
    # ocupe toda la pantalla, como una app Android moderna. 'auto' deja
    # que SDL2 los muestre de nuevo con un swipe desde el borde y los
    # vuelva a ocultar solo.
    log_debug("[inmersivo] Configurando fullscreen=auto")
    Config.set("graphics", "fullscreen", "auto")
    log_debug("[inmersivo] fullscreen configurado OK")
    
    log_debug("[inmersivo] Configurando borderless=1")
    Config.set("graphics", "borderless", "1")
    log_debug("[inmersivo] borderless configurado OK")
    
    log_debug("[inmersivo] Android detectado (platform=%r, ANDROID_DATA=%r) -> "
             "Config fullscreen=auto, borderless=1, orientation=portrait",
             platform, os.environ.get("ANDROID_DATA", "not set"))
else:
    log_debug("[inmersivo] NO es Android (platform=%r, ANDROID_DATA=%r) -> "
             "NO se pide fullscreen ni se va a intentar el modo inmersivo nativo",
             platform, os.environ.get("ANDROID_DATA", "not set"))
    # En desktop (para probar el layout de celular sin un dispositivo a
    # mano), simulamos el aspect ratio de un teléfono 720×1600.
    Config.set("graphics", "width", "360")
    Config.set("graphics", "height", "800")

log_debug("[inmersivo] A punto de importar kivy.app.App")
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.togglebutton import ToggleButton
from kivy.graphics import Color, Rectangle
from kivy.uix.popup import Popup

# ── Anular cierre de popups por gesto/toque fuera de la ventana ──────────
# Por defecto, Kivy cierra cualquier Popup si el toque inicial no colisiona
# con su contenido (auto_dismiss=True). En Android, un gesto de deslizar
# desde el borde superior de la pantalla hacia abajo entra a la app fuera
# del contenido del popup (que no ocupa el 100% de la pantalla) y dispara
# ese cierre accidental. Se parchea Popup.__init__ para que, salvo que se
# indique explícitamente lo contrario, todos los popups de la app usen
# auto_dismiss=False (se cierran solo con los botones Cancelar/Cerrar/cerrar
# por código, nunca por gestos o toques accidentales).
_popup_init_original = Popup.__init__


def _popup_init_sin_autodismiss(self, **kwargs):
    kwargs.setdefault("auto_dismiss", False)
    _popup_init_original(self, **kwargs)


Popup.__init__ = _popup_init_sin_autodismiss

from core.modelo import Modelo, DB_PATH
log_debug("[init] Modelo importado correctamente")
log_debug(f"[init] Modelo tiene asegurar_columnas_equipo: {hasattr(Modelo, 'asegurar_columnas_equipo')}")
log_debug(f"[init] Modelo tiene asegurar_columnas_auditoria: {hasattr(Modelo, 'asegurar_columnas_auditoria')}")

from core.logger_cabledoc import instalar_hook_excepciones, log_error, log_debug
from widgets_base import (
    mostrar_info, mostrar_error, confirmar, _,
    ALTO_BOTON, ALTO_FILA, FUENTE_NORMAL, FUENTE_CHICA, FUENTE_TITULO,
    set_lang, get_lang, IDIOMAS_DISPONIBLES, fila_cerrar_arriba,
    barra_superior_dialogo,
)
log_debug("[init] Todos los imports de widgets_base completados")
from tema import (
    tema, Tarjeta, Chip, BotonIcono, BotonFAB, BarraSuperior, BarraInferior,
    IconoImg,
    ALTURA_BARRA_INFERIOR, ALTURA_BARRA_SUPERIOR,
)

from pantallas_catalogos import (
    MarcasListado, TiposEquipoListado, TiposConectorListado,
    TiposCableListado, TiposFichaListado,
)
from pantallas_cables import CablesListado
from pantallas_equipos import EquiposListado, DialogoAltaRapidaEquipo, \
    DialogoEquipo
from pantallas_conexiones import ConexionesListado, DialogoConexion
from pantallas_conectores import DialogoConector
from pantallas_imagenes import ImagenesListado
from pantallas_avanzadas import abrir_imagen_conectores, abrir_arbol_conexiones
from pantallas_racks import RacksListado, PosicionEnRackListado, \
    FramesListado, DialogoRack
from pantallas_salas import (
    SalasListado, RackPorSalaListado, EquiposNoRackSalaListado,
)
from pantallas_planos import PlanosListado, MueblesListado
from pantallas_cobertura_auditoria import abrir_cobertura_auditoria
from pantallas_config_sla_auditoria import abrir_config_sla_auditoria
from pantallas_vistas import VistaRack, PatcherasVista
from pantallas_diagrama import abrir_diagrama_conexiones
# El asistente de diagnóstico ("🩺 Diagnóstico") ya no se abre desde un
# selector del menú global — vive dentro de DiagramaConexiones (tocar un
# puerto con el modo activo), igual que en GTK. abrir_historial_diagnosticos
# se movió con él, a la barra de herramientas del propio diagrama (botón
# "📋 Historial") — ver pantallas_diagrama.py / pantallas_diagnostico.py.
from pantallas_editores_masivos import (
    abrir_editor_masivo_conectores,
    abrir_editor_masivo_slots,
)
from pantallas_busqueda_global import abrir_busqueda_global


def _proximamente(nombre_modulo):
    mostrar_info(
        _("'{}' todavía no está migrado a Kivy en esta fase.\n"
          "Se va a agregar en una próxima iteración.").format(nombre_modulo))


class MenuHamburguesa(BoxLayout):
    """
    Reemplaza a la vieja barra de 5-6 MenuDesplegable en fila (pensada
    para escritorio, no entra en 360dp de ancho). Un solo botón "" abre
    un DropDown vertical con TODOS los grupos apilados, cada uno con su
    título en negrita y sus ítems abajo — scrolleable si no entra en la
    altura de la pantalla.

    grupos: lista de (etiqueta_grupo, [(lbl, callback), ...])
    """

    def __init__(self, grupos, **kwargs):
        super().__init__(size_hint=(None, 1), width=dp(48), **kwargs)
        self.btn = BotonIcono(icono="menu", tamano=dp(40))
        self.add_widget(self.btn)

        self.dropdown = DropDown(auto_width=False)
        self.dropdown.width = dp(280)

        contenido = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(2))
        contenido.bind(minimum_height=contenido.setter("height"))
        # Fondo sólido: el DropDown es transparente por defecto y sus
        # botones se confundían con los de la pantalla de atrás.
        with contenido.canvas.before:
            Color(*tema.c("superficie"))
            self._fondo_rect = Rectangle(pos=contenido.pos, size=contenido.size)
        contenido.bind(pos=self._actualizar_fondo, size=self._actualizar_fondo)

        for etiqueta_grupo, items in grupos:
            contenido.add_widget(Label(
                text=f"[b]{etiqueta_grupo}[/b]", markup=True,
                size_hint_y=None, height=dp(32), font_size=FUENTE_NORMAL,
                halign="left", valign="middle", padding=(dp(10), 0),
                color=tema.c("primario")))
            for lbl, cb in items:
                if lbl == "---":
                    contenido.add_widget(Label(
                        text="-" * 24, size_hint_y=None, height=dp(10),
                        color=tema.c("borde")))
                    continue
                b = Button(text=lbl, size_hint_y=None, height=ALTO_FILA,
                          font_size=FUENTE_CHICA, halign="left",
                          valign="middle")
                b.bind(size=lambda w, *_a: setattr(
                    w, "text_size", (w.width - dp(16), w.height)))
                b.bind(on_release=lambda inst, c=cb:
                      (self.dropdown.dismiss(), c()))
                contenido.add_widget(b)

        # El DropDown en sí no scrollea: si el menú entero es más alto que
        # la pantalla, lo envolvemos en un ScrollView.
        scroll = ScrollView(size_hint=(1, None))
        scroll.add_widget(contenido)
        scroll.height = min(contenido.height, dp(560)) or dp(560)
        self.dropdown.add_widget(scroll)
        # BUG real: `DropDown` no dispara un evento "on_open" (solo
        # "on_select" y "on_dismiss"), así que ese bind nunca se ejecutaba
        # y el ScrollView quedaba con 1dp de alto para siempre: el menú se
        # abría pero no se veía nada -> parecía que el botón no hacía
        # nada. Se recalcula el alto justo antes de abrir, en el toque.
        contenido.bind(minimum_height=lambda *_a: setattr(
            scroll, "height", min(contenido.height, dp(560))))

        def _abrir(*_a):
            scroll.height = min(contenido.height, dp(560))
            self.dropdown.open(self.btn)

        self.btn.bind(on_release=_abrir)

    def _actualizar_fondo(self, widget, *_a):
        self._fondo_rect.pos = widget.pos
        self._fondo_rect.size = widget.size


ANCHO_TARJETA = dp(140)
ALTO_TARJETA = dp(112)


class PanelPendientesCables(ScrollView):
    """Tarjetas con métricas de trabajo pendiente de Cables.

    En celular (360dp de ancho) no entran 4 tarjetas de lectura cómoda en
    una fila, así que el panel es un ScrollView horizontal: cada tarjeta
    tiene ancho fijo y se deslizan con el dedo."""

    def __init__(self, **kwargs):
        super().__init__(do_scroll_x=True, do_scroll_y=False,
                         size_hint_y=None, height=ALTO_TARJETA, bar_width=dp(4),
                         **kwargs)
        self._fila = BoxLayout(orientation="horizontal", spacing=dp(8),
                              size_hint=(None, 1))
        self._fila.bind(minimum_width=self._fila.setter("width"))
        self.add_widget(self._fila)
        self.actualizar()

    def actualizar(self):
        self._fila.clear_widgets()
        try:
            p = Modelo.devolver_pendientes_cables()
        except Exception:
            return
        # Fase B de plan_ux_botonera_mobile_v1.md (§2.2): mismo total
        # (temporales + sin_conexion) que ya calculaba este panel, ahora
        # también espejado como badge sobre "Cables" en la barra
        # inferior — así se ve sin tener que estar parado en Inicio.
        app = App.get_running_app()
        if app is not None and getattr(app, "_barra_inferior", None):
            app._barra_inferior.actualizar_badge(
                "cables", p["temporales"] + p["sin_conexion"])
        items = [
            (_("Temporales"), p["temporales"], "alerta"),
            (_("En revisión"), p["en_revision"], "secundario_txt"),
            (_("1 extremo"), p["un_extremo"], "alerta"),
            (_("Sin conexión"), p["sin_conexion"], "error"),
        ]
        for titulo, valor, clave in items:
            card = Tarjeta(orientation="vertical", padding=dp(10),
                          spacing=dp(2), size_hint=(None, 1),
                          width=ANCHO_TARJETA)
            card.add_widget(Label(text=str(valor), bold=True,
                                  font_size=sp(22), color=tema.c(clave),
                                  size_hint_y=None, height=dp(30)))
            card.add_widget(Label(text=titulo, font_size=FUENTE_CHICA,
                                  color=tema.c("texto_sub"), halign="left",
                                  size_hint_y=None, height=dp(16)))
            btn = Button(text=_("Ver"), size_hint_y=None, height=dp(30),
                        font_size=FUENTE_CHICA)
            btn.bind(on_release=lambda *_a: abrir_cables())
            card.add_widget(btn)
            self._fila.add_widget(card)


class PanelPendientesEquipos(ScrollView):
    """Tarjetas con métricas de trabajo pendiente de Equipos (scroll
    horizontal, mismo patrón que PanelPendientesCables)."""

    def __init__(self, **kwargs):
        super().__init__(do_scroll_x=True, do_scroll_y=False,
                         size_hint_y=None, height=ALTO_TARJETA, bar_width=dp(4),
                         **kwargs)
        self._fila = BoxLayout(orientation="horizontal", spacing=dp(8),
                              size_hint=(None, 1))
        self._fila.bind(minimum_width=self._fila.setter("width"))
        self.add_widget(self._fila)
        self.actualizar()

    def actualizar(self):
        self._fila.clear_widgets()
        try:
            p = Modelo.devolver_pendientes_equipos()
        except Exception:
            return
        items = [
            (_("Sin conectores"), p["sin_conectores"], "alerta", "sin_conectores"),
            (_("Sin imagen"), p["sin_imagen"], "alerta", "sin_imagen"),
            (_("Sin img. c/ conect."), p["sin_img_conectores"], "error",
             "sin_img_conectores"),
            (_("Sin auditar"), p["sin_auditar"], "alerta", "sin_auditar"),
            (_("Sin manual"), p["sin_manual"], "secundario_txt", "sin_manual"),
            (_("Sin config."), p["sin_configuraciones"], "secundario_txt",
             "sin_configuraciones"),
        ]
        for titulo, valor, clave, filtro in items:
            card = Tarjeta(orientation="vertical", padding=dp(10),
                          spacing=dp(2), size_hint=(None, 1),
                          width=ANCHO_TARJETA)
            card.add_widget(Label(text=str(valor), bold=True,
                                  font_size=sp(22), color=tema.c(clave),
                                  size_hint_y=None, height=dp(30)))
            card.add_widget(Label(text=titulo, font_size=FUENTE_CHICA,
                                  color=tema.c("texto_sub"), halign="left",
                                  size_hint_y=None, height=dp(16)))
            btn = Button(text=_("Ver"), size_hint_y=None, height=dp(30),
                        font_size=FUENTE_CHICA)
            btn.bind(on_release=abrir_equipos_pendiente(filtro))
            card.add_widget(btn)
            self._fila.add_widget(card)


class PanelPendientesAuditoria(ScrollView):
    """Tarjetas con la cantidad de registros NUNCA auditados, por cada
    tabla auditable (Modelo.devolver_pendientes_auditoria(),
    Modelo.TABLAS_AUDITABLES) — mismo patrón (scroll horizontal) que
    PanelPendientesCables/PanelPendientesEquipos.
    plan_auditoria_fecha_edicion_v1.md, Grupo A (A2).

    Conector y Slot no tienen un listado "todos" accesible desde el
    dashboard (ConectoresListado/SlotsListado requieren un id_equipo/
    id_frame puntual), así que esas dos tarjetas no llevan botón "Ver"."""

    def __init__(self, **kwargs):
        super().__init__(do_scroll_x=True, do_scroll_y=False,
                         size_hint_y=None, height=ALTO_TARJETA, bar_width=dp(4),
                         **kwargs)
        self._fila = BoxLayout(orientation="horizontal", spacing=dp(8),
                              size_hint=(None, 1))
        self._fila.bind(minimum_width=self._fila.setter("width"))
        self.add_widget(self._fila)
        self.actualizar()

    def actualizar(self):
        self._fila.clear_widgets()
        try:
            p = Modelo.devolver_pendientes_auditoria()
        except Exception:
            return
        items = [
            (_("Equipos"), p.get("equipo", 0),
             abrir_equipos_pendiente("sin_auditar")),
            (_("Conectores"), p.get("conector", 0), None),
            (_("Conexiones"), p.get("conexion", 0), abrir_conexiones),
            (_("Cables"), p.get("cable", 0), abrir_cables),
            (_("Racks"), p.get("rack", 0), abrir_racks),
            (_("Frames"), p.get("frame", 0), abrir_frames),
            (_("Slots"), p.get("slot", 0), None),
        ]
        for titulo, valor, cb in items:
            card = Tarjeta(orientation="vertical", padding=dp(10),
                          spacing=dp(2), size_hint=(None, 1),
                          width=ANCHO_TARJETA)
            card.add_widget(Label(text=str(valor), bold=True,
                                  font_size=sp(22), color=tema.c("alerta"),
                                  size_hint_y=None, height=dp(30)))
            card.add_widget(Label(text=titulo, font_size=FUENTE_CHICA,
                                  color=tema.c("texto_sub"), halign="left",
                                  size_hint_y=None, height=dp(16)))
            if cb is not None:
                btn = Button(text=_("Ver"), size_hint_y=None, height=dp(30),
                            font_size=FUENTE_CHICA)
                btn.bind(on_release=cb)
                card.add_widget(btn)
            self._fila.add_widget(card)
        self._agregar_tarjeta_vencidos()

    def _agregar_tarjeta_vencidos(self):
        """Última tarjeta del panel (E4 de plan_auditoria_fecha_edicion_
        v1.md, equivalente a VentanaPrincipal._agregar_tarjeta_sla_auditoria
        de GTK): equipos con la auditoría vencida según el SLA configurado
        (Modelo.devolver_vencidos_sla_auditoria) — a diferencia de las
        tarjetas de arriba ("nunca auditados"), incluye también los
        auditados hace más de dias_sla_auditoria días. "Ver" abre el
        listado de equipos filtrado (sólo si hay vencidos: con 0 no hay
        nada que listar); "SLA" cambia los días y refresca el panel.
        Sin glifos Unicode en los textos (no se ven en Pydroid 3). Si algo
        falla no se agrega la tarjeta (las de arriba siguen)."""
        try:
            n_vencidos = len(Modelo.devolver_vencidos_sla_auditoria())
            dias_sla = Modelo.devolver_config_auditoria().get(
                "dias_sla_auditoria",
                Modelo.CONFIG_AUDITORIA_DEFAULTS["dias_sla_auditoria"])
            titulo = _("Vencidos (SLA {} d)").format(f"{dias_sla:g}")
        except Exception:
            return
        card = Tarjeta(orientation="vertical", padding=dp(10), spacing=dp(2),
                       size_hint=(None, 1), width=ANCHO_TARJETA)
        card.add_widget(Label(text=str(n_vencidos), bold=True,
                              font_size=sp(22), color=tema.c("error"),
                              size_hint_y=None, height=dp(30)))
        card.add_widget(Label(text=titulo, font_size=FUENTE_CHICA,
                              color=tema.c("texto_sub"), halign="left",
                              size_hint_y=None, height=dp(16)))
        botones = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        if n_vencidos:
            btn_ver = Button(text=_("Ver"), font_size=FUENTE_CHICA)
            btn_ver.bind(on_release=abrir_equipos_pendiente("vencidos_sla"))
            botones.add_widget(btn_ver)
        btn_sla = Button(text=_("SLA"), font_size=FUENTE_CHICA)
        btn_sla.bind(on_release=lambda *_a: abrir_config_sla_auditoria(
            on_guardado=self.actualizar))
        botones.add_widget(btn_sla)
        card.add_widget(botones)
        self._fila.add_widget(card)


def abrir_cables(*_a):
    CablesListado().open()


def abrir_equipos(*_a):
    EquiposListado().open()


def abrir_equipos_pendiente(filtro):
    def _abrir(*_a):
        EquiposListado(filtro_pendiente=filtro).open()
    return _abrir


def abrir_conexiones(*_a):
    ConexionesListado().open()


def abrir_imagenes(*_a):
    ImagenesListado().open()


def abrir_imagen_conectores_elegir(*_a):
    def _con_equipo(id_, _nombre, _f):
        abrir_imagen_conectores(id_)
    EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()


def abrir_arbol_conexiones_elegir(*_a):
    def _con_equipo(id_, _nombre, _f):
        abrir_arbol_conexiones(id_)
    EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()


def abrir_racks(*_a):
    RacksListado().open()


def abrir_posicion_racks(*_a):
    PosicionEnRackListado().open()


def abrir_frames(*_a):
    FramesListado().open()


def abrir_salas(*_a):
    SalasListado().open()


def abrir_rack_por_sala(*_a):
    RackPorSalaListado().open()


def abrir_equipos_no_rack_sala(*_a):
    EquiposNoRackSalaListado().open()


def abrir_planos(*_a):
    PlanosListado().open()


def abrir_muebles(*_a):
    MueblesListado().open()


def abrir_vista_rack_elegir(*_a):
    VistaRack().open()


def abrir_patcheras_elegir(*_a):
    def _con_equipo(id_, nombre, _f):
        PatcherasVista(id_equipo=id_, nombre_equipo=nombre).open()
    EquiposListado(modo_seleccion=True, on_seleccionar=_con_equipo).open()


def abrir_marcas(*_a):
    MarcasListado().open()


def abrir_tipos_equipo(*_a):
    TiposEquipoListado().open()


def abrir_tipos_conector(*_a):
    TiposConectorListado().open()


def abrir_tipos_cable(*_a):
    TiposCableListado().open()


def abrir_tipos_ficha(*_a):
    TiposFichaListado().open()


class DialogoIdioma(Popup):
    """Popup para elegir el idioma de la aplicación (ToggleButtons,
    uno seleccionado por vez). Requiere reiniciar la app para aplicarse
    del todo (algunos textos ya renderizados no se refrescan en caliente)."""

    def __init__(self, **kwargs):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(14))
        box.add_widget(barra_superior_dialogo(
            _("Seleccionar idioma"), on_atras=lambda: self.dismiss()))
        actual = get_lang()
        for codigo, nombre in IDIOMAS_DISPONIBLES.items():
            b = ToggleButton(text=nombre, group="idioma_app",
                            state="down" if codigo == actual else "normal",
                            size_hint_y=None, height=ALTO_BOTON,
                            font_size=FUENTE_NORMAL)
            b.bind(on_release=lambda inst, c=codigo: self._elegir(c))
            box.add_widget(b)
        box.add_widget(BoxLayout())  # espaciador
        super().__init__(title="", separator_height=0, content=box,
                         size_hint=(1, 1), **kwargs)

    def _elegir(self, codigo):
        set_lang(codigo)
        mostrar_info(_("Idioma seleccionado. Reiniciá la aplicación para "
                      "aplicar los cambios."))


def _abrir_menu_completo():
    """Grupos del menú hamburguesa/'Más' (mismo contenido que antes, ahora
    reutilizado también por el ítem 'Más' de la barra inferior).

    Fase C de plan_ux_botonera_mobile_v1.md (§3, "reordenar, no
    rediseñar"): cambio quirúrgico sobre las mismas tuplas, sin tocar
    `core/` ni firmas.
      1. El grupo "Buscar" (ya iba primero) suma atajos directos a
         Cables/Conexiones — mismas funciones `abrir_cables`/
         `abrir_conexiones` ya importadas, sin duplicar lógica.
      2. "Diagramas" se separa en "Ver" (Imagen con conectores, Árbol,
         Patcheras) vs. "Análisis" (Diagrama de conexiones — la puerta a
         Diagnóstico/Riesgo/Escenario/Señal), en vez de un solo grupo de
         4 ítems con pesos muy distintos.
      3. "Preferencias"/"Aplicación" siguen al final (uso esporádico)."""
    return [
        (_("Buscar"), [
            (_("Búsqueda global…"), lambda: abrir_busqueda_global()),
            (_("Cables"), abrir_cables),
            (_("Conexiones"), abrir_conexiones),
        ]),
        (_("Equipos"), [
            (_("Equipos"), abrir_equipos),
            (_("Alta Rápida…"), lambda: DialogoAltaRapidaEquipo().open()),
            (_("Frames"), abrir_frames),
        ]),
        (_("Cableado"), [
            (_("Cables"), abrir_cables),
            (_("Conexiones"), abrir_conexiones),
            (_("Alta rápida de conexiones…"),
             lambda: __import__(
                 "pantallas_conexiones",
                 fromlist=["abrir_editor_conexiones_rapidas"]
             ).abrir_editor_conexiones_rapidas()),
        ]),
        (_("Infraestructura"), [
            (_("Racks"), abrir_racks),
            (_("Posición en Racks"), abrir_posicion_racks),
            (_("Salas"), abrir_salas),
            (_("Rack por Sala"), abrir_rack_por_sala),
            (_("Equipos sueltos por Sala"), abrir_equipos_no_rack_sala),
            (_("Vista gráfica de rack…"), abrir_vista_rack_elegir),
            (_("Planos"), abrir_planos),
            (_("Muebles"), abrir_muebles),
            (_("Cobertura de auditoría"), abrir_cobertura_auditoria),
        ]),
        (_("Catálogos"), [
            (_("Marcas"), abrir_marcas),
            (_("Tipos de Equipo"), abrir_tipos_equipo),
            (_("Tipos de Conector"), abrir_tipos_conector),
            (_("Tipos de Cable"), abrir_tipos_cable),
            (_("Tipos de Ficha"), abrir_tipos_ficha),
            (_("Imágenes"), abrir_imagenes),
        ]),
        (_("Diagramas — Ver"), [
            (_("Imagen con conectores…"), abrir_imagen_conectores_elegir),
            (_("Árbol de conexiones…"), abrir_arbol_conexiones_elegir),
            (_("Vista de patcheras…"), abrir_patcheras_elegir),
        ]),
        (_("Diagramas — Análisis"), [
            (_("Diagrama de conexiones…"),
             lambda: abrir_diagrama_conexiones()),
        ]),
        (_("Preferencias"), [
            (_("Seleccionar idioma…"), lambda: DialogoIdioma().open()),
            (_("Alternar tema claro/oscuro"), lambda: _alternar_tema_y_refrescar()),
        ]),
        (_("Aplicación"), [
            (_("Salir"), lambda: _confirmar_salir()),
        ]),
    ]


def _confirmar_salir():
    confirmar(
        _("¿Salir de CableDoc?"),
        on_si=lambda: Clock.schedule_once(
            lambda *_a: App.get_running_app().stop(), 0),
    )


class MenuAccion(BoxLayout):
    """Botón de acceso rápido con ícono en tarjeta redondeada + etiqueta
    debajo (grilla estilo 'Accesos rápidos' del mockup)."""

    def __init__(self, icono, etiqueta, callback, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        tarjeta = Tarjeta(clave_color="superficie", size_hint_y=None,
                         height=dp(56))
        boton = BotonIcono(icono=icono, tamano=dp(40),
                          clave_icono="primario")
        boton.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        fl = FloatLayout()
        fl.add_widget(boton)
        boton.bind(on_release=lambda *_a: callback())
        tarjeta.add_widget(fl)
        self.add_widget(tarjeta)
        self.add_widget(Label(text=etiqueta, font_size=FUENTE_CHICA,
                              color=tema.c("texto"), size_hint_y=None,
                              height=dp(16)))


class TarjetaStat(Tarjeta):
    """Tarjeta 'Equipos 142 / Ver todos' del dashboard."""

    def __init__(self, titulo, valor, callback, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(12))
        kwargs.setdefault("spacing", dp(2))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(78))
        super().__init__(**kwargs)
        self.add_widget(Label(text=str(valor), bold=True, font_size=sp(22),
                              color=tema.c("texto"), halign="left",
                              size_hint_y=None, height=dp(28)))
        fila = BoxLayout(size_hint_y=None, height=dp(18))
        fila.add_widget(Label(text=titulo, font_size=FUENTE_CHICA,
                              color=tema.c("texto_sub"), halign="left"))
        fila.add_widget(Label(text=_("Ver todos"), font_size=sp(10),
                              color=tema.c("primario"), halign="right",
                              size_hint_x=None, width=dp(70)))
        self.add_widget(fila)
        # Toda la tarjeta es tocable: se usa on_touch_up con chequeo de
        # colisión en vez de heredar ButtonBehavior (Tarjeta se reutiliza
        # también como contenedor pasivo en otras pantallas).
        self.bind(on_touch_up=lambda w, t: (
            callback() if w.collide_point(*t.pos) and t.grab_current is None
            else None))


def _contar(sql):
    try:
        r = Modelo._query(sql)
        return r[0][0] if r else 0
    except Exception:
        return 0


class PantallaPrincipal(FloatLayout):
    def __init__(self, **kwargs):
        log_debug("[PantallaPrincipal] Iniciando __init__")
        super().__init__(**kwargs)
        log_debug("[PantallaPrincipal] super().__init__ completado")

        log_debug("[PantallaPrincipal] Llamando Modelo.asegurar_columnas_equipo()")
        Modelo.asegurar_columnas_equipo()
        log_debug("[PantallaPrincipal] Modelo.asegurar_columnas_equipo() completado")
        
        if hasattr(Modelo, 'asegurar_columnas_auditoria'):
            log_debug("[PantallaPrincipal] Llamando Modelo.asegurar_columnas_auditoria()")
            Modelo.asegurar_columnas_auditoria()
            log_debug("[PantallaPrincipal] Modelo.asegurar_columnas_auditoria() completado")
        else:
            log_debug("[PantallaPrincipal] WARNING: Modelo.asegurar_columnas_auditoria NO disponible")

        raiz = BoxLayout(orientation="vertical")
        self.add_widget(raiz)

        # ── Espacio para la barra superior GLOBAL (fija sobre toda la
        # app, ver CableDocApp.on_start) — así el contenido no arranca
        # tapado debajo de ella.
        raiz.add_widget(BoxLayout(size_hint_y=None,
                                  height=ALTURA_BARRA_SUPERIOR))

        # ── Contenido central ──
        scroll = ScrollView()
        centro = BoxLayout(orientation="vertical", spacing=dp(14),
                          padding=dp(14), size_hint_y=None)
        centro.bind(minimum_height=centro.setter("height"))

        centro.add_widget(Label(
            text=_("Resumen de tu infraestructura"),
            color=tema.c("texto_sub"), size_hint_y=None, height=dp(22),
            font_size=FUENTE_CHICA, halign="left", valign="middle"))

        # Stats 2x2
        n_equipos = _contar("SELECT COUNT(*) FROM equipo WHERE id_equipo!=0")
        n_cables = _contar(
            "SELECT COUNT(*) FROM cable WHERE es_cable_conexion_interna=0")
        n_conexiones = _contar("SELECT COUNT(*) FROM conexion")
        n_racks = _contar("SELECT COUNT(*) FROM rack")

        grid_stats = GridLayout(cols=2, spacing=dp(10), size_hint_y=None,
                               height=dp(78) * 2 + dp(10))
        grid_stats.add_widget(TarjetaStat(_("Equipos"), n_equipos, abrir_equipos))
        grid_stats.add_widget(TarjetaStat(_("Cables"), n_cables, abrir_cables))
        grid_stats.add_widget(TarjetaStat(_("Conexiones"), n_conexiones,
                                          abrir_conexiones))
        grid_stats.add_widget(TarjetaStat(_("Racks"), n_racks, abrir_racks))
        centro.add_widget(grid_stats)

        # Accesos rápidos
        centro.add_widget(Label(
            text="[b]" + _("Accesos rápidos") + "[/b]", markup=True,
            size_hint_y=None, height=dp(24), font_size=FUENTE_NORMAL,
            color=tema.c("texto"), halign="left", valign="middle"))
        accesos_items = [
            ("buscar", _("Buscar"), lambda: abrir_busqueda_global()),
            ("equipos", _("Equipos"), abrir_equipos),
            ("cables", _("Cables"), abrir_cables),
            ("conexiones", _("Conexiones"), abrir_conexiones),
            ("patchera", _("Patcheras"), abrir_patcheras_elegir),
            ("racks", _("Racks"), abrir_racks),
            ("vista_rack", _("Vista Rack"), abrir_vista_rack_elegir),
            ("frame", _("Frames"), abrir_frames),
            ("diagrama", _("Diagrama"), lambda: abrir_diagrama_conexiones()),
        ]
        n_filas_accesos = (len(accesos_items) + 2) // 3
        grid_accesos = GridLayout(cols=3, spacing=dp(10), size_hint_y=None,
                                 height=n_filas_accesos * dp(76)
                                       + (n_filas_accesos - 1) * dp(10))
        for icono, lbl, cb in accesos_items:
            grid_accesos.add_widget(MenuAccion(icono, lbl, cb))
        centro.add_widget(grid_accesos)

        centro.add_widget(Label(
            text="[b]" + _("Trabajo pendiente — Cables") + "[/b]",
            markup=True, size_hint_y=None, height=dp(24),
            font_size=FUENTE_NORMAL, color=tema.c("texto"), halign="left"))
        self.panel_pendientes_cables = PanelPendientesCables()
        centro.add_widget(self.panel_pendientes_cables)

        centro.add_widget(Label(
            text="[b]" + _("Trabajo pendiente — Equipos") + "[/b]",
            markup=True, size_hint_y=None, height=dp(24),
            font_size=FUENTE_NORMAL, color=tema.c("texto"), halign="left"))
        self.panel_pendientes_equipos = PanelPendientesEquipos()
        centro.add_widget(self.panel_pendientes_equipos)

        centro.add_widget(Label(
            text="[b]" + _("Trabajo pendiente — Auditoría") + "[/b]",
            markup=True, size_hint_y=None, height=dp(24),
            font_size=FUENTE_NORMAL, color=tema.c("texto"), halign="left"))
        self.panel_pendientes_auditoria = PanelPendientesAuditoria()
        centro.add_widget(self.panel_pendientes_auditoria)

        # Espacio para que la barra inferior global (fija sobre toda la
        # app, ver CableDocApp) no tape el último contenido al scrollear.
        centro.add_widget(BoxLayout(size_hint_y=None,
                                    height=ALTURA_BARRA_INFERIOR + dp(10)))

        scroll.add_widget(centro)
        raiz.add_widget(scroll)




def _construir_barra_superior_global():
    """Barra superior [hamburguesa] [título CableDoc] ... [buscar] [tema],
    para agregar directamente a la Window (ver CableDocApp.on_start) y
    que quede fija/visible en toda la app, igual que la barra inferior."""
    barra = BoxLayout(size_hint=(None, None), height=ALTURA_BARRA_SUPERIOR,
                      spacing=dp(6), padding=(dp(10), dp(6)))
    with barra.canvas.before:
        c_barra = Color(*tema.c("bg"))
        r_barra = Rectangle(pos=barra.pos, size=barra.size)
    barra.bind(pos=lambda w, *_a: setattr(r_barra, "pos", w.pos),
              size=lambda w, *_a: setattr(r_barra, "size", w.size))
    tema.bind(modo=lambda *_a: setattr(c_barra, "rgba", tema.c("bg")))

    menu_hamburguesa = MenuHamburguesa(grupos=_abrir_menu_completo())
    barra.add_widget(menu_hamburguesa)

    lbl_titulo = Label(text="CableDoc", font_size=sp(19), bold=True,
                       color=tema.c("texto"), halign="left", valign="middle")
    lbl_titulo.bind(size=lambda w, *_a: setattr(
        w, "text_size", (w.width, w.height)))
    tema.bind(modo=lambda *_a: setattr(lbl_titulo, "color", tema.c("texto")))
    barra.add_widget(lbl_titulo)

    btn_buscar = BotonIcono(icono="buscar", clave_icono="texto")
    btn_buscar.bind(on_release=lambda *_a: abrir_busqueda_global())
    barra.add_widget(btn_buscar)

    btn_tema = BotonIcono(icono="tema", clave_icono="texto")
    btn_tema.bind(on_release=lambda *_a: _alternar_tema_y_refrescar())
    barra.add_widget(btn_tema)

    def _fijar_en_window(window):
        def _reajustar(*_a):
            barra.size = (window.width, ALTURA_BARRA_SUPERIOR)
            barra.pos = (0, window.height - ALTURA_BARRA_SUPERIOR)
        window.bind(size=_reajustar)
        _reajustar()

    barra.fijar_en_window = _fijar_en_window
    return barra


def _ir_a_inicio():
    """Callback del ícono 'Inicio' de la barra inferior: cierra
    cualquier pantalla abierta (todas son Popups apilados sobre la
    Window) y deja ver de nuevo el dashboard de PantallaPrincipal."""
    from kivy.core.window import Window
    for w in list(Window.children):
        if isinstance(w, Popup):
            w.dismiss()


def _ir_a_inicio_confirmando():
    """Callback de 'Inicio' en la barra inferior (agregado_extra.txt,
    propuesta 1). `_ir_a_inicio` es destructivo A PROPÓSITO (hace
    dismiss() de todos los Popups apilados) y por eso sigue igual para
    quien lo llama sin querer preguntar (p.ej. cambio de tema). Acá,
    si hay más de un Popup apilado (señal de que el usuario está en
    medio de un flujo — p.ej. un formulario de conexión abierto encima
    de un equipo — y no sólo mirando un listado), se pide confirmación
    antes de barrer todo."""
    from kivy.core.window import Window
    apilados = sum(1 for w in Window.children if isinstance(w, Popup))
    if apilados <= 1:
        _ir_a_inicio()
        return
    confirmar(_("Hay pantallas abiertas y puede haber cambios sin "
                "guardar.\n¿Salir igual?"), on_si=_ir_a_inicio)


def _alternar_tema_y_refrescar():
    """Cambia claro/oscuro y cierra cualquier pantalla abierta.

    Solo las barras globales (superior/inferior) están 'vivas' y se
    repintan solas al cambiar el tema — el resto de las pantallas
    (listados, diálogos de edición, etc.) arman sus colores UNA VEZ al
    construirse y no se actualizan retroactivamente. Sin este cierre,
    alternar el tema con una pantalla abierta se veía "a medias": la
    barra superior/inferior cambiaba al toque pero el contenido debajo
    quedaba con los colores viejos. Cerrar y volver al dashboard evita
    ese estado mixto — cualquier pantalla que se abra después ya nace
    con los colores correctos."""
    tema.alternar()
    _ir_a_inicio()


def _popup_activo():
    """Fase D de plan_ux_botonera_mobile_v1.md (§2.3): el Popup más
    arriba en `Window.children` — mismo criterio que ya usa `_elevar`
    para saber qué mantener al frente (ver `CableDocApp.on_start`).
    `Window.children` está ordenado de adelante hacia atrás, así que
    alcanza con el primer `Popup` real (la barra inferior/superior no
    lo son, quedan afuera solas). Import local de `Window`, mismo
    criterio que ya usa `_ir_a_inicio` en este archivo."""
    from kivy.core.window import Window
    for w in Window.children:
        if isinstance(w, Popup):
            return w
    return None


def _opciones_fab_default():
    return [
        (_("Alta rápida de equipo"), lambda: DialogoAltaRapidaEquipo().open()),
        (_("Nuevo Cable"), lambda: abrir_cables()),
        (_("Nueva Conexión"), lambda: __import__(
            "pantallas_conexiones",
            fromlist=["abrir_editor_conexiones_rapidas"]
        ).abrir_editor_conexiones_rapidas()),
    ]


def _opciones_fab_para(popup):
    """Registro `{clase: [opciones]}` para el '+' contextual — Fase D
    de plan_ux_botonera_mobile_v1.md (§2.3, tabla ya cerrada con Papi).
    `isinstance` en vez de un dict `{clase: ...}` indexado por tipo
    exacto porque algunos listados (`EquiposListado`) también se abren
    en `modo_seleccion=True` desde otros diálogos — ese caso se filtra
    antes de llamar a esta función (ver `_abrir_menu_rapido`), no acá,
    para no mezclar "qué pantalla es" con "en qué modo está"."""
    if isinstance(popup, DialogoEquipo):
        # Antes que EquiposListado/RacksListado (no hay solapamiento de
        # tipos acá, pero el orden documenta la prioridad si algún día
        # lo hay): el detalle de un equipo es lo más específico.
        return [
            (_("Nuevo conector"),
             lambda: DialogoConector(id_equipo=popup.id_equipo).open()),
        ]
    if isinstance(popup, EquiposListado):
        return [
            (_("Equipo nuevo"), lambda: DialogoEquipo().open()),
            (_("Alta rápida…"), lambda: DialogoAltaRapidaEquipo().open()),
        ]
    if isinstance(popup, RacksListado):
        return [(_("Nuevo rack"), lambda: DialogoRack().open())]
    if isinstance(popup, ConexionesListado):
        return [(_("Nueva Conexión"), lambda: DialogoConexion().open())]
    return _opciones_fab_default()


def _abrir_menu_rapido():
    """Popup de alta rápida — disparado por el '+' central de la barra
    de navegación inferior (visible en toda la app). Fase D de
    plan_ux_botonera_mobile_v1.md (§2.3): el contenido depende de qué
    pantalla está activa (`_popup_activo`); sin match (Inicio incluido)
    cae al mismo menú de siempre (`_opciones_fab_default`).

    El propio '+' ya queda deshabilitado (grisado, sin responder al
    toque) mientras hay un listado en `modo_seleccion=True` —
    `CableDocApp.on_start` lo actualiza en cada cambio de
    `Window.children`, ver `_refrescar_fab_por_popup_activo` — así que
    si esta función se llega a llamar en ese estado no debería pasar
    nunca; el chequeo de acá es sólo un cinturón de seguridad, no el
    mecanismo principal."""
    popup = _popup_activo()
    if getattr(popup, "modo_seleccion", False):
        return
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(14))
    opciones = _opciones_fab_para(popup)
    popup_menu = Popup(title=_("Alta rápida"), content=box,
                       auto_dismiss=True,   # menú chico: toque afuera cierra
                       size_hint=(0.85, min(0.22 + 0.12 * len(opciones), 0.5)))
    for lbl, cb in opciones:
        b = Button(text=lbl, size_hint_y=None, height=ALTO_BOTON,
                  font_size=FUENTE_NORMAL)
        b.bind(on_release=lambda *_a, c=cb: (popup_menu.dismiss(), c()))
        box.add_widget(b)
    popup_menu.open()


def _abrir_menu_mas():
    """Popup contextual — disparado por 'Más' en la barra de navegación
    inferior: 'Cerrar ventana actual' + los grupos que exponga la
    pantalla activa (`grupos_menu_mas`). El menú completo NO se repite
    acá: vive en el hamburguesa de la barra superior."""
    box_outer = BoxLayout(orientation="vertical")
    scroll = ScrollView()
    contenido = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(2), padding=(0, dp(6)))
    contenido.bind(minimum_height=contenido.setter("height"))
    scroll.add_widget(contenido)
    box_outer.add_widget(scroll)

    # Fase E de plan_ux_botonera_mobile_v1.md (§4): "Más" deja de repetir
    # el menú completo (Catálogos, Preferencias, Salir, etc.) — eso ya
    # vive en el menú hamburguesa de la barra superior, también global
    # y siempre al frente. Acá sólo va lo CONTEXTUAL: si la pantalla de
    # más arriba expone `grupos_menu_mas()` (hoy `DiagramaConexiones`),
    # sus grupos; si no, sólo "Cerrar ventana actual". Duck typing en
    # vez de isinstance para que una pantalla futura (p.ej. el editor de
    # planos) se sume sin tocar este archivo.
    objetivo_cierre = _popup_activo()
    _f = getattr(objetivo_cierre, "grupos_menu_mas", None)
    grupos_ctx = _f() if callable(_f) else []
    n_filas = 1 + sum(len(items) + 1 for _t, items in grupos_ctx)

    # auto_dismiss=True EXPLÍCITO: Popup.__init__ está parcheado arriba
    # para que ningún popup se cierre por toque afuera (gesto accidental
    # de Android sobre pantallas/diálogos). Los menús chicos son la
    # excepción: tocar fuera los cierra, como cualquier menú.
    popup = Popup(title=_("Más"), content=box_outer, auto_dismiss=True,
                  size_hint=(0.9, min(0.85, 0.16 + 0.075 * n_filas)))

    # agregado_extra.txt: ítem fijo "Cerrar ventana actual" — salida
    # segura que cierra SOLO la pantalla de más arriba (no todo el stack
    # como 'Inicio'). El objetivo se captura ACÁ, antes de abrir este
    # menú: cuando el usuario toca el ítem, este Popup todavía está en
    # `Window.children` (animación de cierre) y `_popup_activo()` lo
    # devolvería a sí mismo. Sin pantalla abierta (parado en el
    # dashboard) queda deshabilitado, no oculto, para no mover el resto.
    b_cerrar = Button(text=_("Cerrar ventana actual"), size_hint_y=None,
                      height=ALTO_FILA, font_size=FUENTE_CHICA,
                      halign="left", valign="middle",
                      disabled=objetivo_cierre is None)
    b_cerrar.bind(size=lambda w, *_a: setattr(
        w, "text_size", (w.width - dp(16), w.height)))
    b_cerrar.bind(on_release=lambda *_a: (
        popup.dismiss(), objetivo_cierre.dismiss()))
    contenido.add_widget(b_cerrar)

    for etiqueta_grupo, items in grupos_ctx:
        contenido.add_widget(Label(
            text=f"[b]{etiqueta_grupo}[/b]", markup=True,
            size_hint_y=None, height=dp(32), font_size=FUENTE_NORMAL,
            halign="left", valign="middle", padding=(dp(10), 0),
            color=tema.c("primario")))
        for item in items:
            # (texto, callback) o (texto, callback, icono, clave_color)
            lbl, cb = item[0], item[1]
            icono = item[2] if len(item) > 2 else None
            clave = item[3] if len(item) > 3 else "texto"
            if lbl == "---":
                contenido.add_widget(Label(
                    text="-" * 24, size_hint_y=None, height=dp(10),
                    color=tema.c("borde")))
                continue
            b = Button(text=lbl, size_hint_y=None, height=ALTO_FILA,
                      font_size=FUENTE_CHICA, halign="left", valign="middle")
            b.bind(size=lambda w, *_a: setattr(
                w, "text_size", (w.width - dp(16), w.height)))
            if icono:
                # Ícono PNG a la izquierda (no emoji: no se ven en Pydroid
                # 3, ver generar_iconos.py); el texto se corre con padding.
                b.padding = (dp(46), 0)
                img = IconoImg(icono, clave_color=clave,
                               size_hint=(None, None),
                               size=(dp(22), dp(22)))
                b.add_widget(img)
                b.bind(pos=lambda w, *_a, i=img: setattr(
                           i, "pos", (w.x + dp(14), w.center_y - dp(11))),
                       size=lambda w, *_a, i=img: setattr(
                           i, "pos", (w.x + dp(14), w.center_y - dp(11))))
            b.bind(on_release=lambda inst, c=cb: (popup.dismiss(), c()))
            contenido.add_widget(b)

    popup.open()


_listener_ui_android = None  # referencia viva: pyjnius la pierde si se recolecta


def _ocultar_barras_sistema_android(origen="?"):
    """Refuerza el modo inmersivo en Android (oculta barra de estado y
    los botones de navegación del sistema) usando la API nativa de
    Android vía pyjnius.

    CAUSA RAÍZ (confirmada con log.txt del dispositivo real): Kivy
    corre el código Python en un hilo llamado "SDLThread", pero Android
    exige que cualquier llamada que toque la jerarquía de vistas
    (`setSystemUiVisibility`, `setOnSystemUiVisibilityChangeListener`,
    etc.) se haga desde el hilo de UI original ("SDLActivity"). Llamar
    esas APIs directamente tira
    `CalledFromWrongThreadException` — silenciosa para el usuario
    porque quedaba atrapada por el try/except, pero visible en el log
    como traceback de "_ocultar_barras_sistema_android". Por eso a
    veces "funcionaba" (cuando el listener —que Android sí invoca en el
    hilo de UI— alcanzaba a quedar registrado a tiempo) y a veces no.

    Arreglo: todo el trabajo real se despacha con
    `android.runnable.run_on_ui_thread`, que en vez de ejecutar la
    función en el momento, le pide a Android que la corra en el hilo
    correcto. Por eso esta función ya no devuelve nada útil ni permite
    saber el resultado de forma síncrona: todo el diagnóstico queda en
    el log.txt, con un prefijo [hilo UI] para las líneas que sí
    corrieron ya en el hilo correcto.

    Si algo no está disponible (no es Android, no hay pyjnius, la
    actividad no expone esta API, etc.) no hace nada — nunca debe
    romper el arranque.

    `origen`: string libre para identificar en el log.txt desde dónde
    se llamó (on_start, resize, listener, reintento diferido, etc.).
    """
    log_debug(f"[inmersivo] _ocultar_barras_sistema_android(origen={origen}) "
             f"platform={platform!r}")
    if platform != "android":
        log_debug("[inmersivo] platform != 'android' -> no hago nada")
        return
    try:
        log_debug("[inmersivo] importando jnius y android.runnable...")
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread
        log_debug("[inmersivo] imports OK, despachando al hilo de UI...")
    except Exception as e:
        log_debug(f"[inmersivo] fallo el import (jnius/android.runnable): "
                 f"{e!r}")
        log_error("_ocultar_barras_sistema_android (import)", e)
        return

    @run_on_ui_thread
    def _aplicar_en_hilo_ui():
        try:
            log_debug(f"[hilo UI] aplicando modo inmersivo (origen={origen})")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            View = autoclass("android.view.View")
            activity = PythonActivity.mActivity
            if activity is None:
                log_debug("[hilo UI] activity es None -> no puedo continuar")
                return
            window = activity.getWindow()
            decor_view = window.getDecorView()

            visibilidad_previa = decor_view.getSystemUiVisibility()
            log_debug(f"[hilo UI] systemUiVisibility ANTES = "
                     f"{visibilidad_previa} (bin={bin(visibilidad_previa)})")

            flags = (
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )
            decor_view.setSystemUiVisibility(flags)

            visibilidad_post = decor_view.getSystemUiVisibility()
            log_debug(f"[hilo UI] systemUiVisibility DESPUÉS = "
                     f"{visibilidad_post} (bin={bin(visibilidad_post)}) "
                     f"{'OK, coincide' if visibilidad_post == flags else 'NO coincide'}")

            global _listener_ui_android
            if _listener_ui_android is None:
                log_debug("[hilo UI] registrando "
                         "OnSystemUiVisibilityChangeListener")

                class _ListenerUI(PythonJavaClass):
                    __javainterfaces__ = [
                        "android/view/View$OnSystemUiVisibilityChangeListener"]

                    @java_method("(I)V")
                    def onSystemUiVisibilityChange(self, visibility):
                        # Android invoca este callback en el hilo de UI,
                        # así que acá SÍ es seguro llamar setSystemUiVisibility
                        # directamente (confirmado en el log real: nunca
                        # tira CalledFromWrongThreadException desde acá).
                        log_debug(f"[listener] visibility={visibility} "
                                 f"(bin={bin(visibility)}) -> reaplico flags")
                        try:
                            decor_view.setSystemUiVisibility(flags)
                        except Exception as e2:
                            log_debug(f"[listener] error reaplicando: {e2!r}")

                _listener_ui_android = _ListenerUI()
                decor_view.setOnSystemUiVisibilityChangeListener(
                    _listener_ui_android)
                log_debug("[hilo UI] listener registrado OK")
            else:
                log_debug("[hilo UI] listener ya estaba registrado")
        except Exception as e:
            log_debug(f"[hilo UI] excepción aplicando modo inmersivo: {e!r}")
            log_error("_ocultar_barras_sistema_android (hilo UI)", e)

    _aplicar_en_hilo_ui()
    log_debug(f"[inmersivo] _aplicar_en_hilo_ui() despachada (origen={origen})")


class CableDocApp(App):
    title = "CableDoc - Gestión de Cableado"

    def build(self):
        log_debug("[inmersivo] === CableDocApp.build() ===")
        log_debug(f"[build] DB_PATH existe: {os.path.exists(DB_PATH)}")
        if not os.path.exists(DB_PATH):
            log_error("[build] ERROR: DB_PATH no existe!")
            mostrar_error(
                f"No se encontró el archivo de base de datos:\n{DB_PATH}\n\n"
                f"Copiá db.db al directorio 'database/' de la aplicación.")
        try:
            log_debug("[build] Creando PantallaPrincipal...")
            return PantallaPrincipal()
        except Exception as e:
            log_error("CableDocApp.build", e)
            raise

    def on_start(self):
        log_debug("[inmersivo] === CableDocApp.on_start() ===")
        _ocultar_barras_sistema_android(origen="on_start")
        # SDL2 termina de inicializar la superficie nativa en Android
        # DESPUÉS de que corre este método, así que un solo pedido acá
        # puede perderse — se reintenta unas cuantas veces más con
        # Clock mientras arranca la app.
        for demora in (0.3, 1.0, 2.0):
            Clock.schedule_once(
                lambda *_a, d=demora: _ocultar_barras_sistema_android(
                    origen=f"reintento diferido {d}s"), demora)

        # ── Barra de navegación inferior GLOBAL ──
        # Se agrega directamente a la Window (no como hijo de
        # PantallaPrincipal) para que quede visible/tocable por encima
        # de cualquier pantalla abierta como Popup (Equipos, Cables,
        # diálogos, etc.) — así "toda la app" comparte la misma barra
        # fija, con el '+' de alta rápida integrado en el medio.
        from kivy.core.window import Window

        # Cualquier cambio de tamaño de la Window (el teclado en
        # pantalla se ve como uno) puede hacer que Android vuelva a
        # mostrar sus barras — se re-ocultan cada vez.
        Window.bind(on_resize=lambda *_a: _ocultar_barras_sistema_android(
            origen=f"Window.on_resize({_a})"))

        # Fase A de plan_ux_botonera_mobile_v1.md: "Equipos" y "Buscar" ya
        # están a 1 toque desde Inicio (grilla de accesos rápidos + barra
        # superior global) — la barra fija de 5 slots pasa a reflejar los
        # 2 verbos de mayor rotación diaria según el propio panel de
        # "pendientes" de Inicio (Cables: temporales/sin conexión;
        # Conexiones: alta con 1 punta). Íconos "cables"/"conexiones" ya
        # existen en assets/iconos/, sin trabajo de diseño nuevo.
        self._barra_inferior = BarraInferior([
            ("inicio", _("Inicio"), _ir_a_inicio_confirmando),
            ("cables", _("Cables"), abrir_cables),
            ("plus", None, _abrir_menu_rapido),
            ("conexiones", _("Conexiones"), abrir_conexiones),
            ("mas", _("Más"), _abrir_menu_mas),
        ], activo=0)
        self._barra_inferior.fijar_en_window(Window)
        Window.add_widget(self._barra_inferior)

        # Fase B de plan_ux_botonera_mobile_v1.md (§2.2): el badge de
        # "Cables" ya se recalcula cada vez que Inicio renderiza su
        # panel de pendientes (PanelPendientesCables.actualizar), pero
        # eso no cubre quedarse un rato largo en otra pantalla sin pasar
        # por Inicio — refresco liviano cada 60s, según lo que el propio
        # plan deja como alternativa aceptable a instrumentar cada punto
        # de cierre de Cables/Conexiones uno por uno.
        def _refrescar_badge_cables(*_a):
            try:
                p = Modelo.devolver_pendientes_cables()
            except Exception:
                return
            self._barra_inferior.actualizar_badge(
                "cables", p["temporales"] + p["sin_conexion"])
        _refrescar_badge_cables()
        Clock.schedule_interval(_refrescar_badge_cables, 60)

        # ── Barra superior GLOBAL (título CableDoc + buscar + tema) ──
        # Mismo criterio que la inferior: vive pegada a la Window para
        # quedar visible/tocable con cualquier pantalla abierta encima
        # (p.ej. Editar Equipo).
        self._barra_superior = _construir_barra_superior_global()
        self._barra_superior.fijar_en_window(Window)
        Window.add_widget(self._barra_superior)

        # Cada Popup que se abre se agrega a la Window por encima de
        # todo (incluidas estas barras); las re-elevamos al frente cada
        # vez para que se sigan viendo y respondiendo al toque. Kivy
        # chequea los widgets de Window en orden y el ítem tocado
        # dentro de una barra siempre "gana" (collide_point) aunque
        # haya un Popup abierto detrás — el Popup solo intercepta lo
        # que quede fuera del área de las barras.
        def _mantener_arriba(*_a):
            Clock.schedule_once(_elevar, 0)

        def _elevar(*_a):
            frente = set(Window.children[:2])
            if frente != {self._barra_inferior, self._barra_superior}:
                for w in (self._barra_inferior, self._barra_superior):
                    if w in Window.children:
                        Window.remove_widget(w)
                Window.add_widget(self._barra_inferior)
                Window.add_widget(self._barra_superior)
            # Fase D de plan_ux_botonera_mobile_v1.md (§2.3, "modo
            # selección — resuelto"): mismo punto de enganche que ya
            # reelevaba las barras ante cualquier cambio de
            # Window.children — se aprovecha para apagar/prender el '+'
            # según si el Popup activo es un selector
            # (EquiposListado/RacksListado/ConexionesListado con
            # modo_seleccion=True abiertos encima de otro diálogo).
            self._barra_inferior.fijar_fab_disabled(
                getattr(_popup_activo(), "modo_seleccion", False))

        Window.bind(children=_mantener_arriba)

    def on_resume(self):
        log_debug("[inmersivo] === CableDocApp.on_resume() ===")
        # Android suele volver a mostrar la barra de navegación al
        # reanudar la app desde segundo plano; la re-ocultamos.
        _ocultar_barras_sistema_android(origen="on_resume")
        return True


if __name__ == "__main__":
    log_debug("[main] Iniciando aplicacion...")
    instalar_hook_excepciones()
    log_debug("[main] instalar_hook_excepciones() completado")
    try:
        log_debug("[main] Llamando CableDocApp().run()...")
        CableDocApp().run()
        log_debug("[main] CableDocApp().run() finalizado")
    except Exception as e:
        log_error("[main] Excepcion en CableDocApp().run()", e)
        raise
