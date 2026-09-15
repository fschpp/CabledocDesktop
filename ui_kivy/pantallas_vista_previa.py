"""
pantallas_vista_previa.py — "🖼 Vista previa de imagen" en Kivy
=========================================================================
Última parte pendiente del ítem 4 de ROADMAP_FASE5_paridad_pantallas.md
("Señal"). La parte "colorear diagrama" (SenalDiagramaMixin) ya se portó
en Fase 5.4 — ver pantallas_senal.py. Este archivo es el equivalente a
ui_gtk/senal_visual_ui.py (VistaPreviaMixin + _DialogoVistaPrevia +
_DialogoEstrategiaVisual), sobre el motor sin GTK
core/senal_visual.VisualizadorSenal (sin cambios).

Evaluación de canvas (pregunta abierta que dejó el roadmap para este
ítem): NO hace falta un canvas Kivy nuevo. De las 21 rutinas Cairo del
archivo GTK, ninguna dibuja un diagrama o grafo propio — son:
  (a) el generador de la imagen "barras SMPTE + ruido" que reemplaza a
      la imagen real cuando el conector está caído en un análisis
      activo (puramente decorativo, ver más abajo);
  (b) el panel flotante de vista previa en HOVER (fondo + borde + texto
      + imagen escalada);
  (c) el formulario de composición KEY/OVERLAY/MOSAICO/AUDIO_EMBEBIDO,
      que en GTK ya es sólo layout de widgets — cero Cairo ahí.
Se reutiliza el mismo mecanismo "tocar un puerto en modo X abre un
Popup" que ya usan Diagnóstico/Escenario en pantallas_diagrama.py (ver
_CanvasDiagrama.on_touch_down) — no una pantalla ni un canvas aparte.

Dos simplificaciones respecto al 1:1, ambas por el mismo motivo (un
dispositivo táctil no tiene hover — mismo criterio ya documentado en
pantallas_senal.py para el tooltip de puerto):

  1. GTK tiene DOS niveles: un panel de sólo lectura que aparece al
     pasar el mouse, y el diálogo completo (con botones) recién al
     hacer clic. Acá se colapsa a UN nivel: tocar un puerto en modo
     "🖼 Vista previa" abre directamente PopupVistaPrevia — no hay panel
     flotante intermedio. No se pierde información: lo único que
     mostraba el panel de hover y no el diálogo (el aviso de "señal
     caída") se movió DENTRO de PopupVistaPrevia._refrescar.

  2. El placeholder "❌ SIN SEÑAL" de barras SMPTE + ruido pixel a pixel
     (generar_imagen_barras_estaticas, GTK) se reemplaza acá por un
     Label de aviso en vez de portar la generación de textura a mano a
     kivy.graphics — es decorativo (el propio docstring GTK lo aclara:
     "no representa nada real del equipo"), no vale la pena el costo de
     portarlo pixel a pixel para una pantalla más chica.

Adaptación de formulario (ComboBoxText de GTK → Spinner de Kivy): GTK
identifica cada opción por un id separado de su texto visible
(combo.append(id, texto)), así que dos entradas con el mismo nombre no
colisionan. Spinner sólo tiene "text" — acá se desambiguan agregando el
id entre paréntesis si el nombre se repite (ver _fila_combo_entrada).

Hallazgo para tener en cuenta, no se toca en esta entrega (es de
core/modelo.py, compartido con desktop): Modelo._normalizar_imagen_a_png()
convierte a PNG los archivos no-PNG usando GdkPixbuf (GTK) — en un
dispositivo sin GTK (Pydroid/Android) esa conversión no está disponible.
El método ya degrada de forma segura a ImagenInvalidaError pidiendo
guardar como PNG (no rompe nada), pero en mobile CUALQUIER imagen
no-PNG va a pedir conversión manual del lado del usuario. Como Pillow ya
es dependencia de mobile (requirements-mobile.txt), agregar ahí un
fallback con Pillow sería una mejora de bajo riesgo — queda fuera de
esta entrega por tocar core/modelo.py compartido con desktop, no
ui_kivy/.

Otro hallazgo de esta entrega, sí resuelto acá (ver PopupVistaPrevia.
_refrescar): las imágenes COMPUESTAS se regeneran con el MISMO nombre
de archivo por conector (compuesta_<id_conector>.png, ver
core/senal_visual.py::_componer) — el widget Image de Kivy cachea
texturas por path, así que sin forzar reload() tras cada recomposición
se seguiría viendo la versión vieja aunque el archivo en disco ya haya
cambiado. GTK no tiene este problema porque cada _refrescar() crea un
GdkPixbuf.Pixbuf.new_from_file_at_scale() nuevo, que sí relee el
archivo siempre.
"""

import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.spinner import Spinner
from kivy.uix.checkbox import CheckBox
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.metrics import dp

from widgets_base import (
    FileChooserPopup, mostrar_error, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from core.modelo import Modelo, ImagenInvalidaError, DB_PATH
from core.senal_visual import VisualizadorSenal


def _label_multilinea(texto, **kwargs):
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "top")
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("font_size", FUENTE_CHICA)
    lbl = Label(text=texto, **kwargs)
    lbl.bind(width=lambda w, *_a: setattr(w, "text_size", (w.width, None)))
    lbl.bind(texture_size=lambda w, ts: setattr(w, "height", ts[1] + dp(4)))
    return lbl


# ─────────────────────────────────────────────────────────────────────────
# Diálogo de vista previa: imagen resuelta + explicación + accesos a
# asignar/quitar imagen manual y a configurar la composición. Equivalente
# a _DialogoVistaPrevia (GTK), con el panel de hover ya fusionado acá (ver
# docstring del módulo, simplificación 1).
# ─────────────────────────────────────────────────────────────────────────
class PopupVistaPrevia(Popup):

    def __init__(self, id_conector, diagrama=None, **kwargs):
        self._id_conector = id_conector
        self._diagrama = diagrama   # DiagramaConexiones | None — para el
                                     # estado "caído" (_senal_conectores_caidos)
        self._visualizador = VisualizadorSenal(DB_PATH)

        fila = Modelo._query(
            "SELECT c.nombre, e.nombre FROM conector c JOIN equipo e "
            "ON e.id_equipo = c.id_equipo WHERE c.id_conector=?", (id_conector,))
        titulo = f"{s(fila[0][1])} — {s(fila[0][0])}" if fila else f"Conector {id_conector}"

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

        self._caja_img = BoxLayout(size_hint_y=1)
        box.add_widget(self._caja_img)

        self._lbl_detalle = _label_multilinea("")
        box.add_widget(self._lbl_detalle)

        fila_botones = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_asignar = Button(text=_("📷 Asignar imagen manual…"), font_size=FUENTE_CHICA)
        btn_asignar.bind(on_release=self._on_asignar_manual)
        fila_botones.add_widget(btn_asignar)
        btn_quitar = Button(text=_("✖ Quitar imagen manual"), font_size=FUENTE_CHICA)
        btn_quitar.bind(on_release=self._on_quitar_manual)
        fila_botones.add_widget(btn_quitar)
        box.add_widget(fila_botones)

        btn_composicion = Button(text=_("🔀 Configurar composición…"),
                                 size_hint_y=None, height=ALTO_BOTON,
                                 font_size=FUENTE_NORMAL)
        btn_composicion.bind(on_release=self._on_configurar_composicion)
        box.add_widget(btn_composicion)

        btn_cerrar = Button(text=_("Cerrar"), size_hint_y=None, height=ALTO_BOTON,
                            font_size=FUENTE_NORMAL)
        btn_cerrar.bind(on_release=lambda *_a: self.dismiss())
        box.add_widget(btn_cerrar)

        super().__init__(title=f"🖼 {titulo}", content=box, size_hint=(1, 1), **kwargs)
        self._img = None
        self._refrescar()

    def _refrescar(self) -> None:
        self._caja_img.clear_widgets()
        r = self._visualizador.resolver(self._id_conector)

        # plan_estado_senal_y_linaje.md, Función 1 (mismo criterio que
        # GTK): si el conector mirado, o cualquiera de las fuentes usadas
        # para componer la imagen, está "caído" en una simulación activa,
        # avisar en vez de mostrar la imagen (que en ese caso ya no
        # representa nada real).
        caido = False
        caidos_fn = getattr(self._diagrama, "_senal_conectores_caidos", None)
        if caidos_fn is not None:
            caidos = caidos_fn()
            if caidos:
                ids_a_chequear = {str(self._id_conector)} | {str(f) for f in r.fuentes}
                caido = bool(ids_a_chequear & set(caidos.keys()))

        if caido:
            self._caja_img.add_widget(Label(
                text=_("⚠ señal caída en el análisis activo"),
                color=(0.95, 0.55, 0.20, 1), font_size=FUENTE_NORMAL))
        elif r.tiene_imagen and os.path.isfile(r.path):
            self._img = Image(source=r.path, allow_stretch=True, fit_mode="contain")
            # Forzar relectura de disco — ver docstring del módulo: las
            # imágenes COMPUESTAS se regeneran con el mismo nombre de
            # archivo, y Kivy cachea texturas por path.
            self._img.reload()
            self._caja_img.add_widget(self._img)
        else:
            self._caja_img.add_widget(Label(
                text=_("(sin imagen)"), font_size=FUENTE_NORMAL,
                color=(0.6, 0.62, 0.68, 1)))

        origen_legible = {
            "MANUAL": _("Imagen manual"),
            "COMPUESTA": _("Compuesta automáticamente"),
            "SIN_IMAGEN": _("Sin imagen"),
        }.get(r.origen, r.origen)
        self._lbl_detalle.text = f"{origen_legible}: {r.detalle}"

    def _on_asignar_manual(self, *_a) -> None:
        def _elegida(ruta):
            try:
                Modelo.guardar_imagen_senal_conector(self._id_conector, ruta)
            except ImagenInvalidaError as ex:
                mostrar_error(str(ex))
                return
            except Exception as ex:
                mostrar_error(_("No se pudo asignar la imagen: {}").format(ex))
                return
            self._on_cambio()

        FileChooserPopup(
            titulo=_("Elegir imagen (PNG recomendado)"),
            filtros=["*.png", "*.PNG", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG"],
            on_seleccionar=_elegida).open()

    def _on_quitar_manual(self, *_a) -> None:
        Modelo.quitar_imagen_senal_conector(self._id_conector)
        self._on_cambio()

    def _on_configurar_composicion(self, *_a) -> None:
        PopupEstrategiaVisual(
            self._id_conector, on_guardado=self._on_cambio).open()

    def _on_cambio(self) -> None:
        """Equivalente a on_cambio de _DialogoVistaPrevia (GTK): el motor
        cachea el grafo en memoria por instancia (ver senal_visual._cargar)
        — se fuerza una instancia nueva para que la próxima resolución ya
        vea el cambio."""
        self._visualizador = VisualizadorSenal(DB_PATH)
        self._refrescar()


# ─────────────────────────────────────────────────────────────────────────
# Diálogo de composición KEY / OVERLAY / MOSAICO / AUDIO_EMBEBIDO para UN
# conector de salida puntual. Equivalente a _DialogoEstrategiaVisual (GTK)
# — puro formulario, sin ningún dibujo Cairo en el original, portado 1:1
# a widgets Kivy (Spinner en vez de ComboBoxText, CheckBox en vez de
# CheckButton).
# ─────────────────────────────────────────────────────────────────────────
_PISTAS_POSICION = {
    "BASE":  ("BKGD", "BACKGROUND", "BASE", "FONDO"),
    "FILL":  ("FILL", "KEY VIDEO", "VIDEO"),
    "MATTE": ("MATTE", "ALPHA", "KEY ALPHA"),
}

_ETIQUETA_NINGUNA = "(ninguna)"
_ETIQUETA_MATRIZ = "<ASIGNADO POR MATRIZ>"


class PopupEstrategiaVisual(Popup):

    def __init__(self, id_conector_salida, on_guardado=None, **kwargs):
        fila = Modelo._query(
            "SELECT c.id_equipo, c.nombre, e.nombre, e.id_tipo_equipo FROM conector c "
            "JOIN equipo e ON e.id_equipo = c.id_equipo WHERE c.id_conector=?",
            (id_conector_salida,))
        if not fila:
            raise ValueError(f"conector {id_conector_salida} no encontrado")
        id_equipo, nombre_conector, nombre_equipo, id_tipo_equipo = fila[0]

        self._id_conector_salida = str(id_conector_salida)
        self._id_equipo = id_equipo
        self._on_guardado = on_guardado
        self._widgets_rol = {}
        self._checks_overlay = []
        self._checks_mosaico = []
        self._checks_audio = []

        self._entradas = Modelo._query(
            "SELECT c.id_conector, c.nombre FROM conector c "
            "JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE c.id_equipo=? AND UPPER(tc.nombre)='IN' ORDER BY c.nombre",
            (id_equipo,))

        existente = Modelo.estrategia_visual_efectiva(id_conector_salida)
        modo_actual = existente["modo"] if existente else "KEY"
        self._miembros_actuales_iniciales = {
            m["posicion"]: m["id_conector"] for m in (existente or {}).get("miembros", [])}

        rol_senal_equipo = Modelo.devolver_rol_senal_tipo_equipo(id_tipo_equipo)
        self._matriz_disponible_para_base = (
            rol_senal_equipo == "ENRUTADOR"
            or self._miembros_actuales_iniciales.get("BASE") == Modelo.ID_ASIGNADO_POR_MATRIZ)

        titulo = f"🔀 {s(nombre_equipo)} / {s(nombre_conector)}"
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

        if not self._entradas:
            box.add_widget(_label_multilinea(_(
                "Este equipo no tiene conectores de entrada (IN) — no hay "
                "nada que componer.")))
            btn_cerrar = Button(text=_("Cerrar"), size_hint_y=None, height=ALTO_BOTON,
                                font_size=FUENTE_NORMAL)
            btn_cerrar.bind(on_release=lambda *_a: self.dismiss())
            box.add_widget(btn_cerrar)
            super().__init__(title=titulo, content=box, size_hint=(1, 1), **kwargs)
            self._modo_combo = None
            return

        texto_ayuda = _(
            "Elegí el modo y qué entrada de ESTE equipo ocupa cada rol. "
            "'(ninguna)' deja ese rol sin cubrir.")
        if self._matriz_disponible_para_base:
            texto_ayuda += " " + _(
                "En BASE también podés elegir <ASIGNADO POR MATRIZ>: en vez "
                "de una entrada fija, sigue lo que 'Editar matriz' tenga "
                "asignado a esta salida en cada momento.")
        box.add_widget(_label_multilinea(texto_ayuda))

        fila_modo = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        fila_modo.add_widget(Label(text=_("Modo:"), size_hint_x=None, width=dp(64),
                                   font_size=FUENTE_NORMAL))
        self._modo_combo = Spinner(
            text=modo_actual,
            values=("KEY", "OVERLAY", "MOSAICO", "AUDIO_EMBEBIDO"),
            font_size=FUENTE_NORMAL)
        self._modo_combo.bind(text=self._on_modo_changed)
        fila_modo.add_widget(self._modo_combo)
        box.add_widget(fila_modo)

        scroll = ScrollView(do_scroll_x=False)
        self._area_roles = BoxLayout(orientation="vertical", spacing=dp(4),
                                     size_hint_y=None)
        self._area_roles.bind(minimum_height=self._area_roles.setter("height"))
        scroll.add_widget(self._area_roles)
        box.add_widget(scroll)

        self._render_roles(modo_actual, self._miembros_actuales_iniciales)

        fila_botones = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(6))
        btn_guardar = Button(text=_("💾 Guardar"), font_size=FUENTE_CHICA)
        btn_guardar.bind(on_release=self._on_guardar)
        fila_botones.add_widget(btn_guardar)
        if existente:
            btn_quitar = Button(text=_("🗑 Quitar composición"), font_size=FUENTE_CHICA)
            btn_quitar.bind(on_release=self._on_quitar_estrategia)
            fila_botones.add_widget(btn_quitar)
        box.add_widget(fila_botones)

        btn_cancelar = Button(text=_("Cancelar"), size_hint_y=None, height=ALTO_BOTON,
                              font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        box.add_widget(btn_cancelar)

        super().__init__(title=titulo, content=box, size_hint=(1, 1), **kwargs)

    # ── Construcción dinámica del área de roles según el modo elegido ──
    def _render_roles(self, modo, miembros_actuales) -> None:
        self._area_roles.clear_widgets()
        self._widgets_rol = {}
        self._checks_overlay = []
        self._checks_mosaico = []
        self._checks_audio = []

        if modo == "KEY":
            for posicion in ("BASE", "FILL", "MATTE"):
                self._widgets_rol[posicion] = self._fila_combo_entrada(
                    posicion, miembros_actuales.get(posicion),
                    permitir_matriz=(posicion == "BASE"
                                     and self._matriz_disponible_para_base))
        elif modo == "OVERLAY":
            self._widgets_rol["BASE"] = self._fila_combo_entrada(
                "BASE", miembros_actuales.get("BASE"))
            for id_conector, nombre in self._entradas:
                ya_estaba = any(
                    pos.startswith("OVERLAY_") and cid == str(id_conector)
                    for pos, cid in miembros_actuales.items())
                chk = self._fila_checkbox(f"OVERLAY: {s(nombre)}", ya_estaba)
                self._checks_overlay.append((str(id_conector), chk))
        elif modo == "MOSAICO":
            for id_conector, nombre in self._entradas:
                activo = str(id_conector) in miembros_actuales.values()
                chk = self._fila_checkbox(f"Cuadrante: {s(nombre)}", activo)
                self._checks_mosaico.append((str(id_conector), chk))
        elif modo == "AUDIO_EMBEBIDO":
            self._widgets_rol["BASE"] = self._fila_combo_entrada(
                "BASE", miembros_actuales.get("BASE"))
            self._area_roles.add_widget(_label_multilinea(_(
                "Canales de audio a mostrar como vúmetro en el panel del "
                "margen derecho:")))
            for id_conector, nombre in self._entradas:
                ya_estaba = any(
                    pos.startswith("AUDIO_") and cid == str(id_conector)
                    for pos, cid in miembros_actuales.items())
                chk = self._fila_checkbox(f"AUDIO: {s(nombre)}", ya_estaba)
                self._checks_audio.append((str(id_conector), chk))

    def _fila_combo_entrada(self, posicion, id_seleccionado_actual, permitir_matriz=False):
        fila = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        fila.add_widget(Label(text=f"{posicion}:", size_hint_x=None, width=dp(64),
                              font_size=FUENTE_NORMAL))

        # id_por_etiqueta: texto visible del Spinner -> id real ("" para
        # "(ninguna)", Modelo.ID_ASIGNADO_POR_MATRIZ para el rol dinámico).
        # Ver docstring del módulo: Spinner sólo tiene texto, a diferencia
        # de ComboBoxText (GTK) que separa id/texto — nombres repetidos se
        # desambiguan agregando el id entre paréntesis.
        id_por_etiqueta = {_ETIQUETA_NINGUNA: ""}
        valores = [_ETIQUETA_NINGUNA]
        if permitir_matriz:
            valores.append(_ETIQUETA_MATRIZ)
            id_por_etiqueta[_ETIQUETA_MATRIZ] = Modelo.ID_ASIGNADO_POR_MATRIZ

        pistas = _PISTAS_POSICION.get(posicion, ())
        etiqueta_por_defecto = None
        etiquetas_usadas = set(id_por_etiqueta)
        for id_conector, nombre in self._entradas:
            etiqueta = s(nombre)
            if etiqueta in etiquetas_usadas:
                etiqueta = f"{etiqueta} ({id_conector})"
            etiquetas_usadas.add(etiqueta)
            valores.append(etiqueta)
            id_por_etiqueta[etiqueta] = str(id_conector)
            if etiqueta_por_defecto is None and any(
                    p in (nombre or "").strip().upper() for p in pistas):
                etiqueta_por_defecto = etiqueta

        etiqueta_por_id = {v: k for k, v in id_por_etiqueta.items()}
        if id_seleccionado_actual and id_seleccionado_actual in etiqueta_por_id:
            texto_activo = etiqueta_por_id[id_seleccionado_actual]
        elif etiqueta_por_defecto:
            texto_activo = etiqueta_por_defecto
        else:
            texto_activo = _ETIQUETA_NINGUNA

        combo = Spinner(text=texto_activo, values=valores, font_size=FUENTE_NORMAL)
        combo._id_por_etiqueta = id_por_etiqueta   # leído en _id_seleccionado
        fila.add_widget(combo)
        self._area_roles.add_widget(fila)
        return combo

    def _fila_checkbox(self, texto, activo):
        fila = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(6))
        chk = CheckBox(active=activo, size_hint_x=None, width=dp(40))
        fila.add_widget(chk)
        lbl = Label(text=texto, halign="left", valign="middle", font_size=FUENTE_NORMAL)
        lbl.bind(size=lambda w, *_a: setattr(w, "text_size", w.size))
        fila.add_widget(lbl)
        self._area_roles.add_widget(fila)
        return chk

    @staticmethod
    def _id_seleccionado(spinner):
        return spinner._id_por_etiqueta.get(spinner.text) or None

    def _on_modo_changed(self, _spinner, texto) -> None:
        self._render_roles(texto, self._miembros_actuales_iniciales)

    # ── Guardar / quitar ─────────────────────────────────────────────────
    def _on_guardar(self, *_a) -> None:
        modo = self._modo_combo.text
        miembros = []
        if modo == "KEY":
            for posicion in ("BASE", "FILL", "MATTE"):
                sel = self._id_seleccionado(self._widgets_rol[posicion])
                if sel == Modelo.ID_ASIGNADO_POR_MATRIZ:
                    miembros.append({"tipo": "matriz",
                                     "posicion": posicion, "orden": 0})
                elif sel:
                    miembros.append({"tipo": "conector", "ref": int(sel),
                                     "posicion": posicion, "orden": 0})
            if not any(m["posicion"] == "BASE" for m in miembros):
                mostrar_error(_("Key necesita al menos BASE — completá ese rol."))
                return
        elif modo == "OVERLAY":
            sel_base = self._id_seleccionado(self._widgets_rol["BASE"])
            if not sel_base:
                mostrar_error(_("Overlay necesita BASE — completá ese rol."))
                return
            miembros.append({"tipo": "conector", "ref": int(sel_base),
                             "posicion": "BASE", "orden": 0})
            i = 1
            for id_conector, chk in self._checks_overlay:
                if chk.active:
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": f"OVERLAY_{i}", "orden": i})
                    i += 1
        elif modo == "MOSAICO":
            for i, (id_conector, chk) in enumerate(self._checks_mosaico):
                if chk.active:
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": str(i + 1), "orden": i})
            if len(miembros) < 2:
                mostrar_error(_("Mosaico necesita al menos 2 entradas tildadas."))
                return
        elif modo == "AUDIO_EMBEBIDO":
            sel_base = self._id_seleccionado(self._widgets_rol["BASE"])
            if not sel_base:
                mostrar_error(_("Audio embebido necesita BASE — completá ese rol."))
                return
            miembros.append({"tipo": "conector", "ref": int(sel_base),
                             "posicion": "BASE", "orden": 0})
            i = 1
            for id_conector, chk in self._checks_audio:
                if chk.active:
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": f"AUDIO_{i}", "orden": i})
                    i += 1
            if i == 1:
                mostrar_error(_(
                    "Audio embebido necesita al menos un canal de audio tildado."))
                return

        existente = Modelo.estrategia_visual_efectiva(self._id_conector_salida)
        id_estrategia = existente["id_estrategia"] if existente else None
        Modelo.guardar_estrategia_visual(
            id_estrategia, id_conector=int(self._id_conector_salida),
            modo=modo, miembros=miembros)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()

    def _on_quitar_estrategia(self, *_a) -> None:
        existente = Modelo.estrategia_visual_efectiva(self._id_conector_salida)
        if existente:
            Modelo.eliminar_estrategia_visual(existente["id_estrategia"])
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
