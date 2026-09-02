"""
diagnostico_ui.py — Mixin de UI del "Asistente de diagnóstico de falla"
=========================================================================
Implementa la fase de UI de plan_asistente_diagnostico_fallas.md sobre el
motor diagnostico_falla.MotorDiagnostico/SesionDiagnostico. Sigue el mismo
patrón de mixin por herencia múltiple que impacto_ui.ImpactoMixin /
escenario_ui.EscenarioMixin / senal_visual_ui.VistaPreviaMixin.

Integración en pantallas_avanzadas.py (mismo patrón que VistaPreviaMixin,
ver cabecera de senal_visual_ui.py):
  1. from diagnostico_ui import DiagnosticoMixin
     class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin,
                               SenalDiagramaMixin, EscenarioMixin,
                               VistaPreviaMixin, DiagnosticoMixin, Gtk.Dialog)
  2. self._diag_init(DB_PATH)                      — junto a los otros _*_init
  3. for w in self._diag_crear_items_menu(): menu_XXX.append(w)
     (submenú propio "🩺 Diagnóstico" o agregado al de Escenario — a
     definir en la integración final; no compite conceptualmente con
     "Señal" ni "Escenario")
  4. En _on_press():  if self._diag_on_press(da, event): return True
     (antes de _visp_on_press: si los dos modos estuvieran activos a la
     vez por algún bug de wiring, gana diagnóstico — pero en la práctica
     _diag_activar()/_visp_activar() se excluyen mutuamente, ver abajo)

Modo mutuamente excluyente con Escenario/Impacto/Vista Previa (activar
uno apaga los demás, en los dos sentidos — mismo criterio ya establecido
entre esos). Igual que Vista Previa: SÓLO intercepta el clic izquierdo
sobre un puerto — todo lo demás (paneo, minimapa, etc.) sigue andando
igual que si el modo estuviera apagado (ver senal_visual_ui.py, bug ya
corregido ahí, no repetido acá).
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modelo import Modelo
from diagnostico_falla import MotorDiagnostico, SesionDiagnostico

try:
    from i18n import _
except ImportError:
    def _(t): return t


class DiagnosticoMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple."""

    # ── Init ─────────────────────────────────────────────────────────────
    def _diag_init(self, db_path: str) -> None:
        self._diag_db_path = db_path
        self._diag_modo = False
        self._diag_dialogo_activo = False   # ver _diag_on_press

    # ── Ítems de menú ────────────────────────────────────────────────────
    def _diag_crear_items_menu(self) -> list:
        self._diag_btn_modo = Gtk.CheckMenuItem(label=_("🩺 Diagnosticar falla"))
        self._diag_btn_modo.set_tooltip_text(
            "Con el modo activo, clic en el conector donde se reportó la "
            "falla arranca un asistente que va sugiriendo puntos "
            "intermedios para revisar, acotando por bisección hasta el "
            "cable o equipo sospechoso — ver plan_asistente_diagnostico_"
            "fallas.md."
        )
        self._diag_btn_modo.connect("toggled", self._diag_on_toggle_modo)

        btn_historial = Gtk.MenuItem(label=_("📋 Historial de diagnósticos…"))
        btn_historial.set_tooltip_text(
            "Sesiones de diagnóstico ya cerradas — 'prontuario' para "
            "detectar cables/equipos con fallas recurrentes.")
        btn_historial.connect("activate", lambda _w: abrir_historial_diagnosticos(
            self._diag_db_path, parent=self.get_toplevel()))

        return [self._diag_btn_modo, btn_historial]

    def _diag_on_toggle_modo(self, btn) -> None:
        if btn.get_active():
            self._diag_activar()
        else:
            self._diag_desactivar()

    def _diag_activar(self) -> None:
        # Exclusión mutua con Escenario / Impacto — son modos "pesados" de
        # clic-en-el-diagrama que realmente compiten por el gesto (Escenario
        # arrastra selecciones, Impacto también consume todo el área). Con
        # "Vista previa de imagen" NO se excluye a propósito: el cliente
        # necesita seguir viendo la mini-ventana de vista previa (hover) y
        # poder abrir el diálogo de otros conectores mientras diagnostica —
        # los dos modos SÍ pueden convivir porque Vista Previa nunca bloquea
        # el diagrama (ver senal_visual_ui.py) y el diálogo del asistente ya
        # no es modal (ver _DialogoDiagnostico) así que no hay conflicto de
        # foco real entre ambos.
        if getattr(self, "_esc_modo", False):
            self._esc_desactivar_modo()
        if getattr(self, "_imp_modo", False) or getattr(self, "_imp_resultado", None) is not None:
            self._imp_limpiar()
        self._diag_modo = True
        if hasattr(self, "_diag_btn_modo") and not self._diag_btn_modo.get_active():
            self._diag_btn_modo.set_active(True)
        self._da.queue_draw()

    def _diag_desactivar(self) -> None:
        self._diag_modo = False
        if hasattr(self, "_diag_btn_modo") and self._diag_btn_modo.get_active():
            self._diag_btn_modo.set_active(False)
        self._da.queue_draw()

    # ── Clic ─────────────────────────────────────────────────────────────
    def _diag_on_press(self, _da, event) -> bool:
        """Insertar en _on_press(): if self._diag_on_press(da, event): return True

        Igual que Vista Previa: sólo consume el clic izquierdo cuando cae
        justo sobre un puerto — cualquier otro caso se deja pasar (paneo,
        minimapa, selección) en vez de bloquearlo mientras el modo está
        activo. Si ya hay una sesión de diagnóstico en curso (el diálogo
        sigue abierto, ahora no-modal — ver _DialogoDiagnostico), un clic
        en OTRO puerto no abre una segunda sesión: se deja pasar, así cae
        en Vista Previa si ese modo también está activo (permite ir a
        espiar otros conectores mientras se piensa la respuesta)."""
        if not self._diag_modo:
            return False
        if event.button != 1:
            return False
        if self._diag_dialogo_activo:
            return False
        wx, wy = self._s2w(event.x, event.y)
        hit = self._esc_puerto_bajo_cursor(wx, wy) if hasattr(self, "_esc_puerto_bajo_cursor") \
            else None
        if not hit:
            return False
        id_conector, _lado, _id_nodo = hit
        self._diag_dialogo_activo = True
        dlg = _DialogoDiagnostico(self, self._diag_db_path, id_conector)
        try:
            dlg.run()
        finally:
            dlg.destroy()
            self._diag_dialogo_activo = False
        return True


# ─────────────────────────────────────────────────────────────────────────
# Diálogo wizard — dos fases: (1) resolver bifurcaciones si las hay, antes
# de empezar; (2) bisección Sí/No/No sé/Atrás hasta convergencia.
# ─────────────────────────────────────────────────────────────────────────
class _DialogoDiagnostico(Gtk.Dialog):
    def __init__(self, diagrama, db_path, id_conector_sintoma):
        """diagrama: la instancia de DiagramaConexiones (no sólo la
        ventana) — hace falta acceso real a self._nodos/_centrar_en_nodo/
        _da para poder hacer pan hacia el equipo de cada punto que se va
        proponiendo (ver _render_pregunta más abajo)."""
        nombre = Modelo._query(
            "SELECT c.nombre, e.nombre FROM conector c JOIN equipo e "
            "ON e.id_equipo = c.id_equipo WHERE c.id_conector=?",
            (id_conector_sintoma,))
        titulo = f"{nombre[0][1]} / {nombre[0][0]}" if nombre else str(id_conector_sintoma)
        super().__init__(
            title=f"🩺 Diagnóstico de falla — síntoma: {titulo}",
            transient_for=diagrama, modal=False)
        # NO modal (a pedido): con el asistente abierto, el cliente sigue
        # necesitando panear/hacer zoom en el diagrama, y seguir viendo el
        # coloreado por señal y la vista previa mientras contesta — un
        # diálogo modal se lo impedía por completo. set_modal(False) (o,
        # como acá, ni pasarlo) alcanza: Gtk.Dialog.run() sigue bloqueando
        # el código Python hasta que haya una respuesta, pero NO bloquea
        # los demás widgets/ventanas de la aplicación — eso es exactamente
        # lo único que hacía falta cambiar, no hizo falta reescribir el
        # asistente como no bloqueante.
        self.set_destroy_with_parent(True)
        self.set_default_size(460, 380)

        self._diagrama = diagrama
        self._db_path = db_path
        self._id_conector_sintoma = str(id_conector_sintoma)
        self._motor = MotorDiagnostico(db_path)
        self._ramas_elegidas = {}
        self._sesion = None            # SesionDiagnostico, una vez armada la cadena
        self._id_sesion_bd = None      # id de diagnostico_sesion, sólo si se decide guardar
        self._orden_paso = 0
        self._punto_actual = None      # (indice, PasoCadena) pendiente de respuesta

        self._box = self.get_content_area()
        self._box.set_spacing(10)
        self._box.set_border_width(12)
        self._area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._box.pack_start(self._area, True, True, 0)

        self._id_sesion_bd = Modelo.crear_sesion_diagnostico(id_conector_sintoma)

        self.show_all()
        self._avanzar()

    # ── Máquina de estados del wizard ───────────────────────────────────
    def _limpiar_area(self):
        for w in self._area.get_children():
            self._area.remove(w)

    def _avanzar(self):
        """Reconstruye la cadena con las ramas ya elegidas hasta ahora; si
        hay una bifurcación nueva, la pregunta; si no, arranca/continúa la
        bisección."""
        res = self._motor.construir_cadena(
            self._id_conector_sintoma, ramas_elegidas=self._ramas_elegidas)

        if res.categoria_corte == "BIFURCACION":
            self._mostrar_bifurcacion(res)
            return

        # Cadena definitiva (o cortada por un motivo que no es
        # bifurcación) — arranca la sesión de bisección si es la primera
        # vez, o la conserva si ya existía (una rama recién elegida no
        # debería reiniciar las respuestas ya dadas más abajo en la
        # cadena — en la práctica, con cadenas cortas, alcanza con
        # reconstruir; los índices de los pasos YA respondidos siguen
        # correspondiendo al mismo conector real).
        if self._sesion is None:
            if len(res.pasos) < 2:
                self._mostrar_mensaje(
                    "La cadena documentada para este punto es demasiado "
                    "corta para diagnosticar (no hay nada aguas arriba "
                    "para comparar).")
                return
            self._sesion = SesionDiagnostico(res.pasos)
            self._motivo_corte_actual = res.motivo_corte
        else:
            self._sesion.pasos = res.pasos

        self._siguiente_pregunta()

    def _mostrar_bifurcacion(self, res):
        self._limpiar_area()
        bif = res.bifurcacion
        self._area.pack_start(Gtk.Label(
            label=f"El equipo «{bif.nombre_equipo}» combina "
                  f"{len(bif.opciones)} entradas distintas. ¿Cuál de "
                  "ellas corresponde a la señal que falta?",
            xalign=0, wrap=True), False, False, 0)
        combo = Gtk.ComboBoxText()
        for id_conector, nombre in bif.opciones:
            combo.append(id_conector, nombre)
        combo.set_active(0)
        self._area.pack_start(combo, False, False, 0)

        btn = Gtk.Button(label=_("Continuar →"))
        def _elegir(_b):
            self._ramas_elegidas[bif.id_equipo] = combo.get_active_id()
            self._avanzar()
        btn.connect("clicked", _elegir)
        self._area.pack_start(btn, False, False, 0)
        self._area.show_all()

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
        """Sección 6.3 del plan: no hay ningún punto de test cómodo en el
        segmento vigente — se avisa y se deja elegir a mano en vez de
        improvisar con un punto incómodo."""
        self._limpiar_area()
        self._area.pack_start(Gtk.Label(
            label=_("No hay ningún punto marcado como 'de test' en el tramo que queda por revisar. Elegí manualmente por dónde seguir:"),
            xalign=0, wrap=True), False, False, 0)
        combo = Gtk.ComboBoxText()
        for i in range(self._sesion.lo + 1, self._sesion.hi):
            paso = self._sesion.pasos[i]
            combo.append(str(i), f"{paso.nombre_equipo} / {paso.nombre}")
        combo.set_active(0)
        self._area.pack_start(combo, False, False, 0)

        btn = Gtk.Button(label=_("Preguntar acá →"))
        def _elegir(_b):
            idx = int(combo.get_active_id())
            idx, paso = self._sesion.elegir_manual(idx)
            self._punto_actual = (idx, paso)
            self._render_pregunta(paso, manual=True)
        btn.connect("clicked", _elegir)
        self._area.pack_start(btn, False, False, 0)
        self._area.show_all()

    def _render_pregunta(self, paso, manual: bool) -> None:
        self._limpiar_area()
        self._panear_a_equipo(paso.id_equipo)
        restantes = self._sesion.hi - self._sesion.lo
        self._area.pack_start(Gtk.Label(
            label=f"¿Hay señal en «{paso.nombre_equipo} / {paso.nombre}»?",
            xalign=0, wrap=True), False, False, 0)
        sub = "(elegido a mano)" if manual else "punto sugerido por bisección"
        self._area.pack_start(Gtk.Label(
            label=f"{sub} — tramo restante: {restantes} paso(s)",
            xalign=0), False, False, 0)

        fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_si = Gtk.Button(label=_("✅ Sí hay señal"))
        btn_si.connect("clicked", lambda _b: self._responder("SI"))
        fila.pack_start(btn_si, True, True, 0)
        btn_no = Gtk.Button(label=_("❌ No hay señal"))
        btn_no.connect("clicked", lambda _b: self._responder("NO"))
        fila.pack_start(btn_no, True, True, 0)
        self._area.pack_start(fila, False, False, 0)

        fila2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_nose = Gtk.Button(label=_("🤷 No pude verificar"))
        btn_nose.set_tooltip_text(
            "No gasta este paso ni mueve el tramo — el asistente vuelve "
            "a sugerir otro punto del mismo tramo.")
        btn_nose.connect("clicked", lambda _b: self._responder("NO_SE"))
        fila2.pack_start(btn_nose, True, True, 0)
        btn_atras = Gtk.Button(label=_("⬅ Atrás"))
        btn_atras.set_sensitive(bool(self._sesion.historial))
        btn_atras.connect("clicked", lambda _b: self._deshacer())
        fila2.pack_start(btn_atras, True, True, 0)
        self._area.pack_start(fila2, False, False, 0)
        self._area.show_all()

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
            texto = (f"Sospechoso: el equipo «{sin_senal.nombre_equipo}» "
                     f"— revisar su conexión interna o alimentación "
                     f"(entre «{sin_senal.nombre}» y «{con_senal.nombre}»).")
            resultado_tipo = "EQUIPO_SOSPECHOSO"
            id_cable = None
            id_equipo = sin_senal.id_equipo
        else:
            id_cable = self._buscar_cable_entre(sin_senal.id_conector, con_senal.id_conector)
            if id_cable:
                texto = (f"Sospechoso: el cable entre «{sin_senal.nombre_equipo} / "
                         f"{sin_senal.nombre}» y «{con_senal.nombre_equipo} / "
                         f"{con_senal.nombre}».")
            else:
                texto = (f"Sospechoso: el tramo entre «{sin_senal.nombre_equipo} / "
                         f"{sin_senal.nombre}» y «{con_senal.nombre_equipo} / "
                         f"{con_senal.nombre}» (no se encontró un único cable "
                         "directo — revisar ese segmento a mano).")
            resultado_tipo = "CABLE_SOSPECHOSO"
            id_equipo = None

        self._area.pack_start(Gtk.Label(label=_("🎯 Diagnóstico"), xalign=0), False, False, 0)
        lbl = Gtk.Label(label=texto, xalign=0, wrap=True)
        self._area.pack_start(lbl, False, False, 0)

        self._area.pack_start(Gtk.Label(label=_("Descripción del síntoma (opcional):"),
                                        xalign=0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text('ej. "no hay aire", "monitor frizado"...')
        self._area.pack_start(entry, False, False, 0)

        btn_guardar = Gtk.Button(label=_("💾 Guardar en historial"))
        def _guardar(_b):
            if entry.get_text().strip():
                Modelo._exec(
                    "UPDATE diagnostico_sesion SET descripcion=? WHERE id_sesion=?",
                    (entry.get_text().strip(), self._id_sesion_bd))
            Modelo.cerrar_sesion_diagnostico(
                self._id_sesion_bd, resultado_tipo,
                id_cable_resultado=id_cable, id_equipo_resultado=id_equipo)
            btn_guardar.set_sensitive(False)
            btn_guardar.set_label("Guardado ✓")
        btn_guardar.connect("clicked", _guardar)
        self._area.pack_start(btn_guardar, False, False, 0)
        self._area.show_all()

    def _mostrar_mensaje(self, texto: str) -> None:
        self._limpiar_area()
        self._area.pack_start(Gtk.Label(label=texto, xalign=0, wrap=True), False, False, 0)
        self._area.show_all()

    def _panear_a_equipo(self, id_equipo) -> None:
        """Centra el diagrama en el equipo del punto que se acaba de
        proponer para revisar (a pedido: antes había que ir a buscarlo a
        mano en un diagrama grande cada vez que el asistente sugería un
        punto nuevo). Usa el mismo pan+zoom suave que ya usa el buscador
        del diagrama (DiagramaConexiones._centrar_en_nodo) — no hace falta
        ningún cálculo de cámara nuevo."""
        nodo = self._diagrama._nodos.get(id_equipo) if hasattr(self._diagrama, "_nodos") else None
        if nodo is None or not hasattr(self._diagrama, "_centrar_en_nodo"):
            return
        self._diagrama._centrar_en_nodo(nodo)
        self._diagrama._da.queue_draw()

    def _buscar_cable_entre(self, id_conector_a, id_conector_b):
        r = Modelo._query(
            "SELECT cx1.id_cable FROM conexion cx1 JOIN conexion cx2 "
            "ON cx1.id_cable = cx2.id_cable AND cx1.id_conector != cx2.id_conector "
            "WHERE cx1.id_conector=? AND cx2.id_conector=?",
            (id_conector_a, id_conector_b))
        return r[0][0] if r else None


# ─────────────────────────────────────────────────────────────────────────
# Historial de diagnósticos ("prontuario") — no reutiliza VentanaListado
# de cabledoc.py a propósito: cabledoc.py importa DESDE pantallas_
# avanzadas.py (que a su vez importa este módulo), así que este archivo
# nunca puede importar de vuelta desde cabledoc.py sin generar un import
# circular. Se arma un TreeView propio, más chico que VentanaListado
# porque esta pantalla es de sólo lectura salvo por "Eliminar" (no hay
# "Agregar"/"Editar": una sesión sólo se crea completa desde el propio
# asistente).
# ─────────────────────────────────────────────────────────────────────────
def abrir_historial_diagnosticos(db_path, parent=None, id_cable=None, id_equipo=None):
    """Función de conveniencia — pantallas_avanzadas.py y, a través de
    ella, cabledoc.py pueden importar y llamar esto para ofrecer el
    historial filtrado por cable/equipo desde la ficha correspondiente
    (el 'prontuario' pedido por el cliente: fallas recurrentes en un
    mismo punto)."""
    dlg = HistorialDiagnosticosListado(
        db_path, parent=parent, id_cable=id_cable, id_equipo=id_equipo)
    dlg.run()
    dlg.destroy()


class HistorialDiagnosticosListado(Gtk.Dialog):
    _COLUMNAS = ["ID", "Inicio", "Fin", "Equipo síntoma", "Conector síntoma",
                "Descripción", "Resultado", "Sospechoso"]

    def __init__(self, db_path, parent=None, id_cable=None, id_equipo=None):
        titulo = "📋 Historial de diagnósticos"
        if id_cable:
            titulo += f" — cable {id_cable}"
        elif id_equipo:
            titulo += f" — equipo {id_equipo}"
        super().__init__(title=titulo, transient_for=parent, destroy_with_parent=True)
        self.set_default_size(820, 460)
        self._db_path = db_path
        self._id_cable = id_cable
        self._id_equipo = id_equipo

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        self.store = Gtk.ListStore(*([str] * len(self._COLUMNAS)))
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.connect("row-activated", self._on_doble_click)
        for i, titulo_col in enumerate(self._COLUMNAS):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(i not in (0,))
            if i == 0:
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        fila_botones = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_detalle = Gtk.Button(label=_("🔍 Ver detalle"))
        btn_detalle.connect("clicked", lambda _b: self._mostrar_detalle())
        fila_botones.pack_start(btn_detalle, False, False, 0)
        btn_eliminar = Gtk.Button(label=_("🗑 Eliminar"))
        btn_eliminar.connect("clicked", lambda _b: self._eliminar())
        fila_botones.pack_start(btn_eliminar, False, False, 0)
        area.pack_start(fila_botones, False, False, 0)

        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self._cargar()
        self.show_all()

    def _cargar(self) -> None:
        self.store.clear()
        filas = Modelo.historial_diagnosticos(
            id_cable=self._id_cable, id_equipo=self._id_equipo, limite=200)
        etiqueta_resultado = {
            "CABLE_SOSPECHOSO": "Cable", "EQUIPO_SOSPECHOSO": "Equipo",
            "ABANDONADO": "Abandonado",
        }
        for f in filas:
            sospechoso = f["cable_resultado"] or f["equipo_resultado"] or ""
            self.store.append([
                f["id_sesion"], f["fecha_inicio"] or "", f["fecha_fin"] or "",
                f["equipo_sintoma"] or "", f["conector_sintoma"] or "",
                f["descripcion"] or "",
                etiqueta_resultado.get(f["resultado"], f["resultado"] or ""),
                sospechoso,
            ])
        if not filas:
            self.store.append(["", "", "", "", "",
                               "(sin sesiones de diagnóstico registradas todavía)", "", ""])

    def _fila_seleccionada(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None
        id_sesion = model.get_value(it, 0)
        return id_sesion or None

    def _on_doble_click(self, _tv, _path, _col) -> None:
        self._mostrar_detalle()

    def _mostrar_detalle(self) -> None:
        id_sesion = self._fila_seleccionada()
        if not id_sesion:
            return
        dlg = _DialogoDetalleSesion(self, id_sesion)
        dlg.run()
        dlg.destroy()

    def _eliminar(self) -> None:
        id_sesion = self._fila_seleccionada()
        if not id_sesion:
            return
        confirmar = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"¿Eliminar la sesión de diagnóstico #{id_sesion} del historial?")
        resp = confirmar.run()
        confirmar.destroy()
        if resp == Gtk.ResponseType.YES:
            Modelo.eliminar_sesion_diagnostico(id_sesion)
            self._cargar()


class _DialogoDetalleSesion(Gtk.Dialog):
    def __init__(self, parent, id_sesion):
        super().__init__(title=f"Sesión de diagnóstico #{id_sesion}",
                         transient_for=parent, modal=True)
        self.set_default_size(480, 400)
        cabecera, pasos = Modelo.detalle_sesion_diagnostico(id_sesion)

        box = self.get_content_area()
        box.set_spacing(6)
        box.set_border_width(10)

        if cabecera is None:
            box.pack_start(Gtk.Label(label=_("Sesión no encontrada.")), False, False, 0)
            self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
            self.show_all()
            return

        etiqueta_resultado = {
            "CABLE_SOSPECHOSO": "Cable", "EQUIPO_SOSPECHOSO": "Equipo",
            "ABANDONADO": "Abandonado",
        }
        sospechoso = cabecera["cable_resultado"] or cabecera["equipo_resultado"] or "—"
        lineas = [
            f"Síntoma: {cabecera['equipo_sintoma']} / {cabecera['conector_sintoma']}",
            f"Descripción: {cabecera['descripcion'] or '(sin descripción)'}",
            f"Resultado: {etiqueta_resultado.get(cabecera['resultado'], cabecera['resultado'] or '—')} "
            f"— {sospechoso}",
            f"Inicio: {cabecera['fecha_inicio'] or '—'}    Fin: {cabecera['fecha_fin'] or '—'}",
        ]
        for linea in lineas:
            box.pack_start(Gtk.Label(label=linea, xalign=0, wrap=True), False, False, 0)

        box.pack_start(Gtk.Label(label=_("Pasos:"), xalign=0), False, False, 0)
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        store = Gtk.ListStore(str, str, str)
        for p in pasos:
            icono = {"SI": "✅ Sí", "NO": "❌ No", "NO_SE": "🤷 No sé"}.get(p["respuesta"], p["respuesta"])
            store.append([f"{p['equipo']} / {p['conector']}", icono, str(p["orden"] + 1)])
        tv = Gtk.TreeView(model=store)
        for i, titulo in enumerate(["Punto consultado", "Respuesta"]):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo, rend, text=i)
            col.set_expand(i == 0)
            tv.append_column(col)
        sw.add(tv)
        box.pack_start(sw, True, True, 0)

        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self.show_all()
