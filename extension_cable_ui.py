"""
extension_cable_ui.py — UI de Extensiones de Cable (Fase 2)
============================================================================
Fase 2 de plan_desarrollo_extension_cable.md, sobre el esquema y CRUD ya
agregados a modelo.py (Fase 1) y el peso propio en riesgo_analogico.py
(Fase 4). La Fase 3 (nodo intermedio en el diagrama de conexiones, nuevo
tipo de arista en la propagación de señal e impacto) queda pendiente:
requiere tocar pantallas_avanzadas.py / senal_propagation.py /
graph_impact.py y no forma parte de esta entrega.

Una "extensión" es el empalme ficha-contra-ficha de dos extremos sueltos
de cable (conexion con id_conector IS NULL), sin equipo ni barril de por
medio — ver el documento de plan para el caso real que la motivó.

Integración en cabledoc.py:
  - Botón "🔗 Extender con otro cable" en la ficha de Cable (_DialogoCable),
    junto a "🔗 Ver Conexiones" / "⚡ Simular remoción" — llama a
    abrir_extender_cable(parent, id_cable).
  - Entrada de menú "🔗 Extensiones de cable" en Catálogos, mismo patrón
    que "📋 Zonas sospechosas (bitácora)" — llama a
    abrir_extensiones_cable(parent).

Nota de diseño (igual criterio que bitacora_ui.py): para evitar el ciclo
de imports cabledoc.py → extension_cable_ui.py → cabledoc.py, el selector
de cable (CablesListado) se importa en forma diferida, dentro del método
que lo usa.

La sección "Armado" de la ficha de Extensión vive directamente en este
archivo (en _DialogoExtension), igual que ya la tienen _DialogoCable y
_DialogoConexion en cabledoc.py — no se delegó a bitacora_ui.py porque no
hay hoy una "ficha" reusable equivalente para ese propósito.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from modelo import Modelo

try:
    from i18n import _
except ImportError:
    def _(t): return t


def s(v):
    return "" if v is None else str(v)


# ═══════════════════════════════════════════════════════════════════════════
# Selector de tipo de ficha (para crear un extremo suelto nuevo)
# ═══════════════════════════════════════════════════════════════════════════

def _elegir_tipo_ficha(parent=None):
    """Combo simple OK/Cancelar para elegir un tipo de ficha (o ninguno).
    Devuelve id_tipo_ficha (str) o None."""
    dlg = Gtk.Dialog(title="🔌 " + _("Ficha de este extremo"),
                     transient_for=parent, modal=True,
                     destroy_with_parent=True)
    dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                    _("Aceptar"), Gtk.ResponseType.OK)
    area = dlg.get_content_area()
    area.set_border_width(10)
    area.set_spacing(6)
    area.pack_start(Gtk.Label(
        label=_("¿Qué ficha física tiene este extremo suelto del cable?"),
        xalign=0), False, False, 0)
    combo = Gtk.ComboBoxText()
    combo.append("", _("(sin especificar)"))
    for id_tf, nombre in Modelo.devolver_todos_los_tipos_ficha():
        combo.append(str(id_tf), s(nombre))
    combo.set_active(0)
    area.pack_start(combo, False, False, 0)
    dlg.show_all()
    resultado = None
    if dlg.run() == Gtk.ResponseType.OK:
        resultado = combo.get_active_id() or None
    dlg.destroy()
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# Selector de extremo suelto (existente o creado al vuelo)
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoElegirExtremo(Gtk.Dialog):
    """Lista los extremos sueltos disponibles (id_conector IS NULL, no
    usados todavía en otra extensión) y permite elegir uno, o crear uno
    nuevo al vuelo.

    Si `id_cable_fijo` se pasa, el extremo nuevo se crea siempre sobre ese
    cable (caso "Extender con otro cable" desde la ficha de Cable) y la
    lista se filtra a los extremos sueltos de ese mismo cable. Si no se
    pasa, la lista muestra los extremos sueltos de CUALQUIER cable, y
    "crear nuevo" primero pide elegir el cable (caso catálogo general)."""

    _COLUMNAS = ["ID", "Cable", "Ficha"]

    def __init__(self, parent=None, id_cable_fijo=None,
                excluir_id_extension=None, excluir_id_conexion=None):
        super().__init__(title="🔗 " + _("Elegir extremo suelto"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.set_default_size(420, 360)
        self.id_cable_fijo = id_cable_fijo
        self.excluir_id_extension = excluir_id_extension
        self.excluir_id_conexion = excluir_id_conexion
        self.resultado_id_conexion = None
        self.resultado_label = None

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        self.store = Gtk.ListStore(str, str, str)
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.connect("row-activated", lambda *a: self._usar())
        for i, titulo_col in enumerate(self._COLUMNAS):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(i == 1)
            if i == 0:
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        fila_botones = Gtk.Box(spacing=6)
        btn_crear = Gtk.Button(label=_("➕ Crear extremo nuevo…"))
        btn_crear.connect("clicked", lambda _b: self._crear_nuevo())
        fila_botones.pack_start(btn_crear, False, False, 0)
        area.pack_start(fila_botones, False, False, 0)

        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Usar seleccionado"), Gtk.ResponseType.OK)

        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        filas = Modelo.devolver_conexiones_sueltas(
            id_cable=self.id_cable_fijo,
            excluir_id_extension=self.excluir_id_extension)
        for id_cx, id_cable, codigo, id_tf, nombre_tf in filas:
            if self.excluir_id_conexion and str(id_cx) == str(self.excluir_id_conexion):
                continue
            ficha = nombre_tf or _("(ficha sin especificar)")
            self.store.append([s(id_cx), s(codigo), s(ficha)])
        if len(self.store) == 0:
            self.store.append(["", _("(sin extremos sueltos disponibles)"), ""])

    def _fila_seleccionada(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None, None
        id_cx = model.get_value(it, 0)
        if not id_cx:
            return None, None
        return id_cx, f"{model.get_value(it, 1)} [{model.get_value(it, 2)}]"

    def _usar(self):
        id_cx, label = self._fila_seleccionada()
        if not id_cx:
            return
        self.resultado_id_conexion = id_cx
        self.resultado_label = label
        self.response(Gtk.ResponseType.OK)

    def _crear_nuevo(self):
        id_cable = self.id_cable_fijo
        codigo_cable = None
        if not id_cable:
            # Catálogo general: primero hay que elegir sobre qué cable se
            # crea el extremo nuevo. Import diferido — ver nota de diseño
            # en el encabezado del módulo.
            from cabledoc import CablesListado
            dlg_cable = CablesListado(parent=self, modo_seleccion=True)
            if dlg_cable.run() == Gtk.ResponseType.OK:
                id_cable = dlg_cable.resultado_id
                codigo_cable = dlg_cable.resultado_nombre
            dlg_cable.destroy()
            if not id_cable:
                return

        id_tipo_ficha = _elegir_tipo_ficha(parent=self)
        id_conexion = Modelo.crear_extremo_suelto(id_cable, id_tipo_ficha)
        if not id_conexion:
            return
        self._cargar()
        # Preseleccionar la fila recién creada.
        it = self.store.get_iter_first()
        while it is not None:
            if self.store.get_value(it, 0) == s(id_conexion):
                self.tv.get_selection().select_iter(it)
                break
            it = self.store.iter_next(it)


def elegir_extremo(parent=None, id_cable_fijo=None, excluir_id_extension=None,
                   excluir_id_conexion=None):
    """Devuelve (id_conexion, label) o (None, None) si se canceló."""
    dlg = _DialogoElegirExtremo(
        parent=parent, id_cable_fijo=id_cable_fijo,
        excluir_id_extension=excluir_id_extension,
        excluir_id_conexion=excluir_id_conexion)
    resultado = (None, None)
    if dlg.run() == Gtk.ResponseType.OK and dlg.resultado_id_conexion:
        resultado = (dlg.resultado_id_conexion, dlg.resultado_label)
    dlg.destroy()
    return resultado


# ═══════════════════════════════════════════════════════════════════════════
# Ver cadena completa (ajuste de usabilidad post-uso real)
# ═══════════════════════════════════════════════════════════════════════════
# Papi reportó, tras usar la función contra su base real, que no podía
# seguir "qué está uniendo con qué" en cada paso de armar una extensión
# — la queja NO era ninguna de las 2 hipótesis originales (editar ficha
# sin recrear / columnas de género en el catálogo), sino la falta total
# de una vista que muestre el recorrido real completo (equipo origen →
# cable → extensión → cable → ... → equipo destino). Ver PROGRESS.md.

def _formatear_cadena(eslabones):
    """Convierte la lista de eslabones de Modelo.resolver_cadena_extension()
    en líneas de texto con marcado Pango simple, listas para Gtk.Label."""
    esc = GLib.markup_escape_text
    lineas = []
    for elem in eslabones:
        tipo = elem.get("tipo")
        if tipo == "equipo":
            lineas.append(
                f"<b>{esc(elem['equipo'] or '')}</b>  —  {esc(elem['conector'] or '')}")
        elif tipo == "cable":
            marcador = "  👈" if elem.get("foco") else ""
            lineas.append(f"    │ {_('cable')} <i>{esc(elem['codigo'] or '')}</i>{marcador}")
        elif tipo == "extension":
            armado = {1: "✓ " + _("correcto"),
                     0: "⚠ " + _("MAL ARMADO")}.get(elem.get("armado"), _("no verificado"))
            pos = elem.get("posicion") or _("sin posición registrada")
            lineas.append(
                f"<b>🔗 {_('Extensión')} #{elem['id_extension']}</b> "
                f"({esc(pos)}) — {armado}")
        elif tipo == "suelto":
            lineas.append(
                "<span foreground='#a00000'>⚠ " +
                esc(_("extremo suelto — la cadena termina acá, sin llegar a un equipo")) +
                "</span>")
        elif tipo == "ciclo":
            lineas.append(
                "<span foreground='#a00000'>⚠ " +
                esc(_("referencia circular detectada — revisar extensiones")) +
                "</span>")
    return lineas


class CadenaExtensionDialog(Gtk.Dialog):
    """Muestra el recorrido real completo (equipo → cable → extensión →
    cable → ... → equipo) resuelto por Modelo.resolver_cadena_extension().
    Solo lectura — ver es más importante que editar acá."""

    def __init__(self, parent=None, eslabones=None, id_cable_foco=None):
        super().__init__(title="🔗 " + _("Cadena completa"),
                         transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.set_default_size(460, 320)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)

        if not eslabones:
            area.pack_start(Gtk.Label(
                label=_("Este cable no tiene conexiones cargadas todavía."),
                xalign=0), False, False, 0)
        else:
            lbl_intro = Gtk.Label(xalign=0)
            lbl_intro.set_line_wrap(True)
            texto_intro = GLib.markup_escape_text(
                _("Recorrido real de extremo a extremo, siguiendo cada "
                  "extensión. El cable marcado con 👈 es desde donde "
                  "abriste esta vista."))
            lbl_intro.set_markup(f"<small>{texto_intro}</small>")
            area.pack_start(lbl_intro, False, False, 0)

            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw.set_vexpand(True)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.set_border_width(6)
            for linea in _formatear_cadena(eslabones):
                lbl = Gtk.Label(xalign=0)
                lbl.set_line_wrap(True)
                lbl.set_markup(linea)
                box.pack_start(lbl, False, False, 0)
            sw.add(box)
            area.pack_start(sw, True, True, 0)

        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.show_all()


def abrir_ver_cadena(parent=None, id_cable=None):
    """Punto de entrada único para 'Ver cadena completa'. Resuelve y
    muestra el recorrido real completo a partir de un cable cualquiera
    de la cadena — no hace falta que sea una punta.

    Llamado desde: ficha de Cable (cabledoc.py), catálogo
    ExtensionesListado (más abajo), y automáticamente al terminar de
    crear/editar una extensión (_DialogoExtension.run_and_destroy)."""
    if not id_cable:
        return
    eslabones = Modelo.resolver_cadena_extension(id_cable)
    dlg = CadenaExtensionDialog(parent=parent, eslabones=eslabones,
                                id_cable_foco=id_cable)
    dlg.run()
    dlg.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Alta / edición de una extensión
# ═══════════════════════════════════════════════════════════════════════════

class _DialogoExtension(Gtk.Dialog):
    """Alta o edición de una extensión de cable.

    - Alta desde la ficha de Cable (id_cable_a dado): el extremo A se
      elige/crea siempre sobre ese cable puntual; el extremo B puede ser
      de cualquier otro cable.
    - Alta desde el catálogo general (id_cable_a=None): ambos extremos se
      eligen/crean libremente.
    - Edición (id_extension dado): los extremos ya no se pueden reasignar
      (ver Modelo.editar_extension) — solo ubicación y armado.
    """

    def __init__(self, parent=None, id_extension=None, id_cable_a=None):
        titulo = _("Editar Extensión") if id_extension else _("Nueva Extensión de Cable")
        super().__init__(title="🔗 " + titulo, transient_for=parent, modal=True,
                         destroy_with_parent=True)
        self.set_default_size(440, -1)
        self.id_extension = id_extension
        self.id_conexion_a = None
        self.id_conexion_b = None
        self._ok_extremos = bool(id_extension)  # ya definidos si es edición

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)

        if not id_extension:
            frame_ext = Gtk.Frame(label=" " + _("Extremos a empalmar") + " ")
            box_ext = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box_ext.set_border_width(8)

            if id_cable_a:
                # Viene desde "Extender con otro cable": el extremo A ya
                # se sabe QUÉ CABLE es, así que no tiene sentido volver a
                # preguntarlo — solo mostrarlo, con un link chico para
                # cambiarlo si hiciera falta (raro: cable con 2+ puntas
                # sueltas propias).
                self.lbl_a = Gtk.Label(xalign=0)
                self.lbl_a.set_line_wrap(True)
                box_ext.pack_start(self.lbl_a, False, False, 0)
                btn_a = Gtk.Button(label=_("Cambiar extremo…"))
                btn_a.set_relief(Gtk.ReliefStyle.NONE)
                btn_a.connect("clicked", lambda _b: self._elegir("a"))
                box_ext.pack_start(btn_a, False, False, 0)
            else:
                self.lbl_a = Gtk.Label(xalign=0)
                self.lbl_a.set_line_wrap(True)
                btn_a = Gtk.Button(label=_("🔍 Elegir el primer cable…"))
                btn_a.connect("clicked", lambda _b: self._elegir("a"))
                box_ext.pack_start(self.lbl_a, False, False, 0)
                box_ext.pack_start(btn_a, False, False, 0)

            sep = Gtk.Separator()
            box_ext.pack_start(sep, False, False, 4)

            self.lbl_b = Gtk.Label(xalign=0)
            self.lbl_b.set_line_wrap(True)
            btn_b = Gtk.Button(label=_("🔍 Elegir el otro cable…"))
            btn_b.connect("clicked", lambda _b: self._elegir("b"))
            box_ext.pack_start(self.lbl_b, False, False, 0)
            box_ext.pack_start(btn_b, False, False, 0)

            frame_ext.add(box_ext)
            area.pack_start(frame_ext, False, False, 0)

            self.id_cable_a_fijo = id_cable_a
            if id_cable_a:
                self._elegir("a", automatico=True)
            self._refrescar_labels()

        # ── Ubicación física ──
        g = Gtk.Grid(column_spacing=8, row_spacing=6)
        area.pack_start(g, False, False, 6)

        g.attach(Gtk.Label(label=_("Rack:"), xalign=1), 0, 0, 1, 1)
        self.c_rack = Gtk.ComboBoxText()
        self.c_rack.append("", _("(sin asignar)"))
        for id_r, numero, nombre, _cap in Modelo.devolver_todos_los_racks():
            etiqueta = f"{s(nombre)} ({numero})" if numero else s(nombre)
            self.c_rack.append(str(id_r), etiqueta)
        self.c_rack.set_active(0)
        g.attach(self.c_rack, 1, 0, 2, 1)

        g.attach(Gtk.Label(label=_("Sala:"), xalign=1), 0, 1, 1, 1)
        self.c_sala = Gtk.ComboBoxText()
        self.c_sala.append("", _("(sin asignar)"))
        for id_s, nombre in Modelo.devolver_todas_las_salas():
            self.c_sala.append(str(id_s), s(nombre))
        self.c_sala.set_active(0)
        g.attach(self.c_sala, 1, 1, 2, 1)

        g.attach(Gtk.Label(label=_("Posición libre:"), xalign=1), 0, 2, 1, 1)
        self.e_posicion = Gtk.Entry(hexpand=True)
        self.e_posicion.set_placeholder_text(_('ej. "detrás del zócalo 4"'))
        g.attach(self.e_posicion, 1, 2, 2, 1)

        # ── Armado (plan §2: peso propio, independiente del equipo aguas
        # abajo — ver riesgo_analogico.py) ──
        frame_arm = Gtk.Frame(label=" " + _("Armado") + " ")
        g2 = Gtk.Grid(column_spacing=8, row_spacing=6)
        g2.set_border_width(8)
        g2.attach(Gtk.Label(label=_("¿Armado correcto?:"), xalign=1), 0, 0, 1, 1)
        self.c_armado = Gtk.ComboBoxText()
        self.c_armado.append("", _("No verificado"))
        self.c_armado.append("1", _("Correcto"))
        self.c_armado.append("0", _("Mal armado"))
        self.c_armado.set_active(0)
        g2.attach(self.c_armado, 1, 0, 2, 1)
        g2.attach(Gtk.Label(label=_("Detalle:"), xalign=1), 0, 1, 1, 1)
        self.e_detalle = Gtk.Entry(hexpand=True)
        self.e_detalle.set_placeholder_text(
            _('ej. "empalme sin continuidad de malla"'))
        g2.attach(self.e_detalle, 1, 1, 2, 1)
        frame_arm.add(g2)
        area.pack_start(frame_arm, False, False, 0)

        self.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL,
                         _("Aceptar"), Gtk.ResponseType.OK)

        if id_extension:
            self._cargar(id_extension)

        self.show_all()

    def _elegir(self, cual, automatico=False):
        id_cable_fijo = self.id_cable_a_fijo if cual == "a" else None

        if automatico and id_cable_fijo:
            # Resolución automática al abrir "Extender con otro cable":
            # si el cable de origen tiene exactamente una punta suelta
            # (el caso normal), se usa directo, sin mostrar ningún
            # diálogo — es el motivo #1 de queja de usabilidad de esta
            # función. Si no tiene ninguna, se crea una preguntando solo
            # la ficha. Si tiene 2+ (caso raro), se cae al selector
            # manual más abajo.
            sueltas = Modelo.devolver_conexiones_sueltas(id_cable=id_cable_fijo)
            if len(sueltas) == 1:
                self.id_conexion_a = sueltas[0][0]
                self._refrescar_labels()
                return
            if len(sueltas) == 0:
                id_tf = _elegir_tipo_ficha(parent=self)
                id_cx = Modelo.crear_extremo_suelto(id_cable_fijo, id_tf)
                if id_cx:
                    self.id_conexion_a = id_cx
                self._refrescar_labels()
                return
            # 2+ puntas sueltas en el mismo cable: ambiguo, se pide a mano.

        id_conexion, _label = elegir_extremo(
            parent=self, id_cable_fijo=id_cable_fijo,
            excluir_id_conexion=(
                self.id_conexion_b if cual == "a" else self.id_conexion_a))
        if id_conexion:
            if cual == "a":
                self.id_conexion_a = id_conexion
            else:
                self.id_conexion_b = id_conexion
        self._refrescar_labels()

    def _refrescar_labels(self):
        def texto(id_cx, cual):
            if not id_cx:
                return (_("Primer cable: (sin elegir)") if cual == "a"
                        else _("Segundo cable: (sin elegir)"))
            codigo, ficha = Modelo.devolver_resumen_conexion(id_cx)
            ficha = ficha or _("ficha sin especificar")
            etiqueta = _("Primer cable") if cual == "a" else _("Segundo cable")
            return f"{etiqueta}: {codigo} ({ficha})"

        self.lbl_a.set_text(texto(self.id_conexion_a, "a"))
        self.lbl_b.set_text(texto(self.id_conexion_b, "b"))

    def _cargar(self, id_extension):
        rows = Modelo.devolver_extension(id_extension)
        if not rows:
            return
        (id_ext, id_cx_a, id_cx_b, id_rack, id_sala, posicion,
         es_correcto, detalle) = rows[0]
        self.id_conexion_a = id_cx_a
        self.id_conexion_b = id_cx_b
        if id_rack:
            self.c_rack.set_active_id(str(id_rack))
        if id_sala:
            self.c_sala.set_active_id(str(id_sala))
        if posicion:
            self.e_posicion.set_text(s(posicion))
        if es_correcto is not None:
            self.c_armado.set_active_id(str(int(es_correcto)))
        if detalle:
            self.e_detalle.set_text(s(detalle))

    def run_and_destroy(self):
        resp = self.run()
        if resp == Gtk.ResponseType.OK:
            id_rack = self.c_rack.get_active_id() or None
            id_sala = self.c_sala.get_active_id() or None
            posicion = self.e_posicion.get_text().strip() or None
            if self.id_extension:
                Modelo.editar_extension(
                    self.id_extension, id_rack=id_rack, id_sala=id_sala,
                    posicion_libre=posicion)
                id_activo = self.id_extension
            else:
                if not (self.id_conexion_a and self.id_conexion_b):
                    self.destroy()
                    return
                Modelo.crear_extension(
                    self.id_conexion_a, self.id_conexion_b,
                    id_rack=id_rack, id_sala=id_sala,
                    posicion_libre=posicion)
                id_activo = Modelo.devolver_extension_de_conexion(self.id_conexion_a)

            id_arm = self.c_armado.get_active_id()
            es_correcto = None if not id_arm else bool(int(id_arm))
            detalle_arm = self.e_detalle.get_text().strip() or None
            if id_activo:
                Modelo.establecer_armado_extension(id_activo, es_correcto, detalle_arm)

            # Feedback inmediato: mostrar la cadena completa resultante
            # apenas se guarda, para que quede claro qué quedó unido con
            # qué en este paso — ver nota de usabilidad al inicio de la
            # sección "Ver cadena completa" más arriba en este archivo.
            if self.id_conexion_a:
                id_cable_semilla = Modelo.devolver_cable_de_conexion(self.id_conexion_a)
                if id_cable_semilla:
                    abrir_ver_cadena(parent=self, id_cable=id_cable_semilla)
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Catálogo general (Catálogos → "🔗 Extensiones de cable")
# ═══════════════════════════════════════════════════════════════════════════

class ExtensionesListado(Gtk.Dialog):
    """Punto de entrada general: listado + alta/edición/baja, mismo
    patrón visual que ZonasSospechosasListado (bitacora_ui.py)."""

    _COLUMNAS = ["ID", "Cable A", "Cable B", "Rack", "Sala", "Posición", "Armado"]

    def __init__(self, parent=None):
        super().__init__(title="🔗 " + _("Extensiones de cable"),
                         transient_for=parent, destroy_with_parent=True)
        self.set_default_size(640, 420)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        self.store = Gtk.ListStore(str, str, str, str, str, str, str)
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.connect("row-activated", lambda *a: self._editar())
        for i, titulo_col in enumerate(self._COLUMNAS):
            rend = Gtk.CellRendererText(xpad=4)
            col = Gtk.TreeViewColumn(titulo_col, rend, text=i)
            col.set_resizable(True)
            col.set_expand(i in (1, 2))
            if i == 0:
                col.set_visible(False)
            self.tv.append_column(col)
        sw.add(self.tv)
        area.pack_start(sw, True, True, 0)

        fila_botones = Gtk.Box(spacing=6)
        btn_nueva = Gtk.Button(label=_("➕ Nueva extensión…"))
        btn_nueva.connect("clicked", lambda _b: self._nueva())
        btn_editar = Gtk.Button(label=_("✏️ Editar"))
        btn_editar.connect("clicked", lambda _b: self._editar())
        btn_cadena = Gtk.Button(label=_("🔗 Ver cadena completa"))
        btn_cadena.set_tooltip_text(_(
            "Ver el recorrido real completo (equipo → cable → extensión → "
            "cable → ... → equipo) de la extensión seleccionada."))
        btn_cadena.connect("clicked", lambda _b: self._ver_cadena())
        btn_eliminar = Gtk.Button(label=_("🗑 Eliminar"))
        btn_eliminar.connect("clicked", lambda _b: self._eliminar())
        fila_botones.pack_start(btn_nueva, False, False, 0)
        fila_botones.pack_start(btn_editar, False, False, 0)
        fila_botones.pack_start(btn_cadena, False, False, 0)
        fila_botones.pack_start(btn_eliminar, False, False, 0)
        area.pack_start(fila_botones, False, False, 0)

        self.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self._cargar()
        self.show_all()

    def _cargar(self):
        self.store.clear()
        filas = Modelo.listar_extensiones()
        for (id_ext, cod_a, cod_b, rack, sala, posicion,
             es_correcto) in filas:
            armado = {1: _("Correcto"), 0: _("⚠ Mal armado")}.get(
                es_correcto, _("No verificado"))
            self.store.append([s(id_ext), s(cod_a), s(cod_b), s(rack),
                               s(sala), s(posicion), armado])
        if not filas:
            self.store.append(["", _("(sin extensiones cargadas todavía)"),
                               "", "", "", "", ""])

    def _fila_seleccionada(self):
        sel = self.tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return None
        return model.get_value(it, 0) or None

    def _nueva(self):
        dlg = _DialogoExtension(parent=self)
        dlg.run_and_destroy()
        self._cargar()

    def _editar(self):
        id_ext = self._fila_seleccionada()
        if not id_ext:
            return
        dlg = _DialogoExtension(id_extension=id_ext, parent=self)
        dlg.run_and_destroy()
        self._cargar()

    def _ver_cadena(self):
        id_ext = self._fila_seleccionada()
        if not id_ext:
            return
        rows = Modelo.devolver_extension(id_ext)
        if not rows:
            return
        id_cx_a = rows[0][1]
        id_cable = Modelo.devolver_cable_de_conexion(id_cx_a)
        abrir_ver_cadena(parent=self, id_cable=id_cable)

    def _eliminar(self):
        id_ext = self._fila_seleccionada()
        if not id_ext:
            return
        confirmar = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("¿Eliminar la extensión seleccionada?"),
            secondary_text=_(
                "Los dos extremos de cable involucrados no se borran: "
                "quedan disponibles como extremos sueltos para una nueva "
                "extensión."))
        resp = confirmar.run()
        confirmar.destroy()
        if resp == Gtk.ResponseType.YES:
            Modelo.eliminar_extension(id_ext)
            self._cargar()


def abrir_extensiones_cable(parent=None):
    dlg = ExtensionesListado(parent=parent)
    dlg.run()
    dlg.destroy()


def abrir_extender_cable(parent=None, id_cable=None):
    """Punto de entrada desde el botón '🔗 Extender con otro cable' de la
    ficha de Cable (_DialogoCable en cabledoc.py)."""
    dlg = _DialogoExtension(parent=parent, id_cable_a=id_cable)
    dlg.run_and_destroy()
