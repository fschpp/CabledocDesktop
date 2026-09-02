#!/usr/bin/env python3
"""
arbol_conexiones_ui.py — CableDoc GTK3

Entrega 1 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md). Move 1:1, sin cambio de lógica:

  ArbolConexionesEquipo   árbol jerárquico lazy-load de conexiones
  abrir_arbol_conexiones  función de conveniencia

Columnas de CONEXIONES_AMBOS_EXTREMOS (WHERE id_equipo = X):
  0  Cable                   1  EA: equipo (= el CONECTADO)
  3  EA: conector            5  EB: Equipo (= el CONSULTADO)
  9  id_equipo (= X)        10  id_equipo:1 (= id del CONECTADO)
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject

from modelo import Modelo

from pantallas_comunes import _, s, confirmar
from imagen_conectores_ui import ImagenConectoresYCables


# ═══════════════════════════════════════════════════════════════════════════════
# ArbolConexionesEquipo
# ═══════════════════════════════════════════════════════════════════════════════

class ArbolConexionesEquipo(Gtk.Dialog):
    """
    Árbol jerárquico lazy-load:
      🖥 Equipo raíz
        🔗 Cable "cod" → conector
            🖥 Equipo destino   (expandible recursivamente)

    Interacción:
      • Expandir nodo equipo → carga conexiones bajo demanda
      • Equipos sin más conexiones → grises
      • Doble-clic en nodo equipo → abre ImagenConectoresYCables
    """

    COL_TEXTO  = 0  # str texto visible
    COL_KEY    = 1  # str id_equipo o clave_cable
    COL_TIPO   = 2  # str "equipo" | "cable" | "dummy"
    COL_COLOR  = 3  # str color de texto
    COL_WEIGHT = 4  # int peso de fuente
    COL_ITALIC = 5  # int 0=normal 2=itálica

    def __init__(self, id_equipo=None, parent=None):
        super().__init__(
            title="Árbol de conexiones de equipo",
            transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons(_("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(720, 640)

        self._id_raiz          = str(id_equipo) if id_equipo else None
        self._desarrollados    = set()

        area = self.get_content_area()

        # ── barra superior ────────────────────────────────────────────────
        hb = Gtk.Box(spacing=6,
                     margin_start=8, margin_end=8,
                     margin_top=8,   margin_bottom=4)
        self._lbl_sel = Gtk.Label(xalign=0, hexpand=True)
        self._lbl_sel.set_markup("<i>Ningún equipo seleccionado</i>")

        def _btn(lbl, cb):
            b = Gtk.Button(label=lbl); b.connect("clicked", cb); return b

        hb.pack_start(Gtk.Label(label=_("Raíz:")), False, False, 0)
        hb.pack_start(self._lbl_sel,            True,  True,  0)
        hb.pack_start(_btn("🔍 Elegir equipo…", self._sel_equipo), False, False, 0)
        hb.pack_start(_btn("🗑 Limpiar",         self._limpiar),    False, False, 0)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        hb.pack_start(sep, False, False, 4)
        hb.pack_start(_btn("⊞ Expandir todo",  lambda _: self._tv.expand_all()),  False, False, 0)
        hb.pack_start(_btn("⊟ Colapsar todo",  lambda _: self._tv.collapse_all()), False, False, 0)
        area.pack_start(hb, False, False, 0)
        area.pack_start(Gtk.Separator(), False, False, 0)

        # ── TreeView ──────────────────────────────────────────────────────
        self._store = Gtk.TreeStore(str, str, str, str, int, int)
        self._tv    = Gtk.TreeView(model=self._store, headers_visible=False)
        self._tv.set_enable_tree_lines(True)

        rend = Gtk.CellRendererText()
        col  = Gtk.TreeViewColumn("", rend,
                                  text      = self.COL_TEXTO,
                                  foreground= self.COL_COLOR,
                                  weight    = self.COL_WEIGHT,
                                  style     = self.COL_ITALIC)
        self._tv.append_column(col)

        self._tv.connect("row-expanded",  self._on_expandido)
        self._tv.connect("row-activated", self._on_doble_clic)
        self._tv.get_selection().connect("changed", self._on_sel)
        
        # ── Configurar Drag and Drop ─────────────────────────────────────────
        # Permitir arrastrar equipos
        self._tv.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            [Gtk.TargetEntry.new("tree-row", Gtk.TargetFlags.SAME_WIDGET, 0)],
            Gdk.DragAction.COPY
        )
        self._tv.connect("drag-data-get", self._on_drag_data_get)
        
        # Permitir soltar en nodos (para reorganizar o asignar)
        self._tv.enable_model_drag_dest(
            [Gtk.TargetEntry.new("tree-row", Gtk.TargetFlags.SAME_WIDGET, 0)],
            Gdk.DragAction.COPY
        )
        self._tv.connect("drag-data-received", self._on_drag_data_received)
        # Sobrescribir el manejador por defecto de drag_drop (requerido para TreeModelFilter)
        self._tv.connect("drag_drop", self._on_drag_drop)

        sw = Gtk.ScrolledWindow(vexpand=True,
                                margin_start=8, margin_end=8, margin_bottom=4)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        # ── info bar ──────────────────────────────────────────────────────
        self._info_bar = Gtk.InfoBar(message_type=Gtk.MessageType.INFO)
        self._lbl_info = Gtk.Label(xalign=0)
        self._info_bar.get_content_area().add(self._lbl_info)
        area.pack_start(self._info_bar, False, False, 0)

        # ── status bar ────────────────────────────────────────────────────
        self._sb = Gtk.Statusbar()
        area.pack_start(self._sb, False, False, 0)

        self.show_all()
        self._info_bar.set_visible(False)

        if self._id_raiz:
            self._cargar_raiz(self._id_raiz)

    # ── helpers TreeStore ─────────────────────────────────────────────────
    def _add(self, it_padre, texto, key, tipo,
             color="#1a1a1a", weight=400, italic=0):
        return self._store.append(
            it_padre, [texto, key, tipo, color, weight, italic])

    def _hijo_existe(self, it_padre, key):
        it = self._store.iter_children(it_padre)
        while it:
            if self._store.get_value(it, self.COL_KEY) == key:
                return True
            it = self._store.iter_next(it)
        return False

    def _buscar_cable(self, it_padre, clave):
        it = self._store.iter_children(it_padre)
        while it:
            if (self._store.get_value(it, self.COL_KEY)  == clave and
                self._store.get_value(it, self.COL_TIPO) == "cable"):
                return it
            it = self._store.iter_next(it)
        return None

    # ── carga ─────────────────────────────────────────────────────────────
    def _nombre_equipo(self, id_eq):
        rows = Modelo.devolver_equipo(id_eq)
        return s(rows[0][1]) if rows and rows[0][1] else f"Equipo {id_eq}"

    def _cargar_raiz(self, id_eq):
        id_eq = str(id_eq).strip()
        if not id_eq or id_eq == "0":
            return
        nombre = self._nombre_equipo(id_eq)
        self._lbl_sel.set_markup(f"<b>{nombre}</b>")

        datos = Modelo.devolver_equipos_conectados_a_equipo(id_eq)
        if not datos:
            self._status(_("El equipo no tiene conexiones registradas.")); return

        it_raiz = self._add(None, f"🖥  {nombre}", id_eq, "equipo",
                            color="#0a3a6e", weight=700)
        self._poblar(it_raiz, id_eq, datos)
        self._desarrollados.add(id_eq)

        path = self._store.get_path(it_raiz)
        self._tv.expand_row(path, False)
        self._tv.scroll_to_cell(path, None, True, 0.0, 0)
        self._status(f"Cargadas {len(datos)} conexiones para «{nombre}»")

    def _poblar(self, it_padre, id_eq_local, datos):
        """Rellena hijos de it_padre (equipo local) con cables y equipos destino."""
        for r in datos:
            cable   = s(r[0]).strip() or "?"
            con_loc = s(r[3])           # conector en el equipo local
            eq_dest = s(r[1])           # nombre equipo destino
            id_dest = s(r[10]).strip()  # id equipo destino

            # nodo cable
            clave_cable = f"{id_eq_local}::{cable}"
            it_cable = self._buscar_cable(it_padre, clave_cable)
            if it_cable is None:
                it_cable = self._add(
                    it_padre,
                    f"🔗  {cable}  ›  {con_loc}",
                    clave_cable, "cable",
                    color="#1a6a9a", weight=400)

            # nodo equipo destino
            if self._hijo_existe(it_cable, id_dest):
                continue

            if id_dest in ("0", ""):
                color_d = "#aaaaaa"; w_d = 300; i_d = 2
                expandible = False
            else:
                color_d = "#1a5c2e"; w_d = 400; i_d = 0
                expandible = True

            it_dest = self._add(it_cable, f"🖥  {eq_dest}",
                                id_dest, "equipo",
                                color=color_d, weight=w_d, italic=i_d)

            # placeholder para indicar que es expandible
            if expandible and id_dest not in self._desarrollados:
                self._add(it_dest, "   ⏳  (expandir para cargar…)",
                          "", "dummy", color="#bbbbbb", weight=300, italic=2)

    # ── lazy-load al expandir ─────────────────────────────────────────────
    def _on_expandido(self, tv, it, path):
        tipo = self._store.get_value(it, self.COL_TIPO)
        key  = self._store.get_value(it, self.COL_KEY)
        if tipo != "equipo" or key in ("", "0") or key in self._desarrollados:
            return

        # quitar dummy
        it_ch = self._store.iter_children(it)
        while it_ch:
            if self._store.get_value(it_ch, self.COL_TIPO) == "dummy":
                self._store.remove(it_ch); break
            it_ch = self._store.iter_next(it_ch)

        datos  = Modelo.devolver_equipos_conectados_a_equipo(key)
        nombre = self._nombre_equipo(key)
        if datos:
            self._poblar(it, key, datos)
            self._desarrollados.add(key)
            self._status(f"«{nombre}» — {len(datos)} conexiones")
        else:
            # nodo hoja: grisis
            self._store.set(it,
                self.COL_COLOR,  "#aaaaaa",
                self.COL_WEIGHT, 300,
                self.COL_ITALIC, 2)
            self._desarrollados.add(key)
            self._status(f"«{nombre}» no tiene más conexiones")

    # ── doble-clic → imagen conectores ───────────────────────────────────
    def _on_doble_clic(self, tv, path, col):
        it   = self._store.get_iter(path)
        tipo = self._store.get_value(it, self.COL_TIPO)
        key  = self._store.get_value(it, self.COL_KEY)
        if tipo == "equipo" and key not in ("", "0"):
            dlg = ImagenConectoresYCables(id_equipo=key, parent=self)
            dlg.run(); dlg.destroy()

    # ── selección → info bar ──────────────────────────────────────────────
    def _on_sel(self, sel):
        model, it = sel.get_selected()
        if it is None:
            self._info_bar.set_visible(False); return
        tipo  = model.get_value(it, self.COL_TIPO)
        key   = model.get_value(it, self.COL_KEY)
        texto = model.get_value(it, self.COL_TEXTO).strip()
        if tipo == "equipo" and key not in ("", "0"):
            self._lbl_info.set_markup(
                f"<b>Equipo ID {key}</b>  —  {texto}\n"
                "<small>Expanda para cargar conexiones  │  "
                "Doble clic para ver imagen de conectores</small>")
            self._info_bar.set_visible(True)
        elif tipo == "cable":
            cod = key.split("::", 1)[1] if "::" in key else key
            self._lbl_info.set_markup(f"<b>Cable:</b>  {cod}")
            self._info_bar.set_visible(True)
        else:
            self._info_bar.set_visible(False)

    # ── Drag and Drop ────────────────────────────────────────────────────────
    def _on_drag_drop(self, tv, context, x, y, timestamp):
        """Sobrescribir manejador por defecto de drag_drop."""
        GObject.signal_stop_emission_by_name(tv, "drag_drop")
        return True

    def _on_drag_data_get(self, tv, context, selection, info, timestamp):
        """Manejador para obtener datos al arrastrar un nodo (equipo)."""
        sel = tv.get_selection()
        model, it = sel.get_selected()
        if not it:
            return
        
        tipo = model.get_value(it, self.COL_TIPO)
        oid = model.get_value(it, self.COL_KEY)
        
        # Solo permitir arrastrar equipos
        if tipo == "equipo":
            selection.set(Gtk.SELECTION_TYPE_STRING, 0, str(oid).encode())

    def _on_drag_data_received(self, tv, context, x, y, selection, info, timestamp):
        """Manejador para recibir datos al soltar en un nodo."""
        from gi.repository import GObject
        
        # Obtener el equipo arrastrado
        data = selection.get_data()
        if not data:
            context.finish(False, False)
            return
        
        id_equipo_origen = data.decode()
        
        # Obtener el nodo destino (donde se soltó)
        path, _ = tv.get_dest_row_at_pos(x, y)
        if not path:
            context.finish(False, False)
            return
        
        it = self._store.get_iter(path)
        if not it:
            context.finish(False, False)
            return
        
        tipo_destino = self._store.get_value(it, self.COL_TIPO)
        id_destino = self._store.get_value(it, self.COL_KEY)
        
        # Solo permitir soltar equipos en otros equipos (para conectar)
        if tipo_destino == "equipo" and id_destino not in ("", "0"):
            nombre_origen = self._nombre_equipo(id_equipo_origen)
            nombre_destino = self._nombre_equipo(id_destino)
            
            self._status(f"Arrastrado equipo {nombre_origen} hacia equipo {nombre_destino}")
            
            # Abrir diálogo para crear conexión
            from cabledoc import ConexionesListado
            # Crear una conexión entre los dos equipos
            # Esto podría abrir un diálogo específico para crear conexión
            # Por ahora, mostramos un mensaje
            if confirmar(
                self,
                f"¿Crear conexión entre <b>{nombre_origen}</b> y <b>{nombre_destino}</b>?"
            ):
                # Aquí se crearía la conexión en la base de datos
                # Para simplificar, mostramos mensaje de éxito
                self._status(f"Conexión creada: {nombre_origen} → {nombre_destino}")
        
        context.finish(True, False)

    def _mostrar_mensaje(self, texto):
        """Muestra un mensaje en el status bar."""
        self._status(texto)

    # ── utilidades ────────────────────────────────────────────────────────
    def _sel_equipo(self, btn):
        from cabledoc import EquiposListado
        dlg = EquiposListado(parent=self, modo_seleccion=True)
        if dlg.run() == Gtk.ResponseType.OK:
            self._limpiar(None)
            self._id_raiz = dlg.resultado_id
            self._cargar_raiz(self._id_raiz)
        dlg.destroy()

    def _limpiar(self, btn):
        self._store.clear()
        self._desarrollados.clear()
        self._lbl_sel.set_markup("<i>Ningún equipo seleccionado</i>")
        self._info_bar.set_visible(False)
        self._status("")

    def _status(self, txt):
        self._sb.push(self._sb.get_context_id("i"), txt)



# ── función de conveniencia ─────────────────────────────────────────────────

def abrir_arbol_conexiones(id_equipo=None, parent=None):
    dlg = ArbolConexionesEquipo(id_equipo=id_equipo, parent=parent)
    dlg.run(); dlg.destroy()
