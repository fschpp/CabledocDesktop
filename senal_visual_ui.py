"""
senal_visual_ui.py — Mixin de UI de "Vista previa de imagen" para
DiagramaConexiones
=========================================================================
Implementa la fase de UI de plan_vista_previa_visual_senal.md sobre el
motor senal_visual.VisualizadorSenal. Sigue el mismo patrón de mixin por
herencia múltiple que impacto_ui.ImpactoMixin / escenario_ui.EscenarioMixin
y reutiliza sus helpers de hit-testing de puertos
(_esc_puerto_bajo_cursor) en vez de reescribirlos.

Integración en pantallas_avanzadas.py (agregar junto a la de EscenarioMixin,
ver cabecera de escenario_ui.py para el patrón completo):
  1. from senal_visual_ui import VistaPreviaMixin
     class DiagramaConexiones(ImpactoMixin, RiesgoDiagramaMixin,
                               SenalDiagramaMixin, EscenarioMixin,
                               VistaPreviaMixin, Gtk.Dialog)
  2. self._visp_init(DB_PATH)                       — junto a los otros _*_init
  3. for w in self._visp_crear_items_menu(): menu_senal.append(w)
     (se agrega al submenú "Señal" ya existente, no uno nuevo — ver plan,
     sección 2.5: es una vista más de "qué contenido hay", como colorear
     por señal)
  4. En _on_press():   if self._visp_on_press(da, event): return True
  5. En _on_motion():  if self._visp_on_motion(da, event): return
  6. En _on_draw():    self._visp_on_draw_overlay(cr, W, H)
     (junto a los demás overlays; este panel va en la esquina inferior
     IZQUIERDA, así que no compite por espacio con el minimapa)

Convive con Modo Escenario, Analizar Impacto y Diagnosticar falla — ya
NO se excluyen mutuamente entre sí desde 2026-08-24 (ver _visp_activar,
impacto_ui._imp_on_activar, escenario_ui._esc_activar_modo). Con
"colorear por señal" SÍ convivía desde siempre: ese modo es sólo un
overlay pasivo, no consume clics, así que nunca hubo nada que excluir.

La ÚNICA forma de salir del modo es destildar "🖼 Vista previa de imagen"
en el menú — ni el clic derecho ni cerrar el diálogo de un conector lo
desactivan (antes sí lo hacía el clic derecho; se sacó a pedido).

Nota de alcance (ver plan, fase 6): el CLIC sigue abriendo el diálogo
completo (con los botones de asignar/componer) sólo para el puerto
clickeado — la mini-ventana de hover es sólo lectura, para no recomponer
imágenes en cada movimiento del mouse más de lo necesario (se recalcula
únicamente cuando cambia el conector bajo el cursor, no en cada evento).
"""

from __future__ import annotations

import os
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
gi.require_foreign("cairo")  # necesario para Gdk.cairo_set_source_pixbuf(cr, ...):
                              # sin esto, PyGObject no sabe convertir un
                              # cairo.Context (pycairo) al tipo que Gdk
                              # espera y tira KeyError en tiempo de dibujo
                              # (encontrado al probar la mini-ventana de hover).
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from modelo import Modelo, ImagenInvalidaError
from senal_visual import VisualizadorSenal

try:
    from i18n import _
except ImportError:
    def _(t): return t

# Tamaño/posición de la mini-ventana de vista previa (esquina inferior
# izquierda) — mismo criterio visual que el minimapa (esquina inferior
# derecha, ver pantallas_avanzadas.py::_draw_minimap), pero geometría
# propia porque este panel siempre está visible en modo Vista Previa,
# haya o no nodos/vista global (el minimapa sólo aplica en vista global).
_PANEL_W, _PANEL_H, _PANEL_MARGIN = 220, 150, 14

# plan_estado_senal_y_linaje.md, Función 1: cache del placeholder de
# "barras estáticas" por tamaño (se pide siempre con el mismo area_w/
# area_h del panel, así que alcanza con una entrada — no vale la pena un
# dict por si algún día se pide en más de un tamaño, se cambia ahí nomás).
_cache_barras_estaticas: dict = {}


def generar_imagen_barras_estaticas(ancho: int, alto: int):
    """
    Genera (y cachea en memoria, no en disco) una imagen tipo "barras de
    color SMPTE simplificadas + ruido" para mostrar en vez de la imagen
    real cuando el conector resuelto por VisualizadorSenal está "caído"
    en la simulación activa (Impacto/Riesgo/Escenario) — ver
    _senal_conectores_caidos() en senal_diagrama_ui.py. Es puramente
    decorativo, no representa nada real del equipo.

    Devuelve un cairo.ImageSurface (no un GdkPixbuf.Pixbuf) porque el
    único lugar que la usa (_visp_on_draw_overlay) ya tiene un
    cairo.Context a mano — cr.set_source_surface() es directo, mientras
    que convertir a Pixbuf sólo para volver a pasar por
    Gdk.cairo_set_source_pixbuf() agrega una vuelta innecesaria (y el
    reordenamiento de canales BGRA↔RGBA que eso implicaría a mano).
    """
    ancho, alto = max(1, int(ancho)), max(1, int(alto))
    clave = (ancho, alto)
    if clave in _cache_barras_estaticas:
        return _cache_barras_estaticas[clave]

    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr = cairo.Context(surf)

    # Barras SMPTE simplificadas (7 franjas verticales, colores clásicos)
    colores = [
        (0.75, 0.75, 0.75), (0.75, 0.75, 0.10), (0.10, 0.75, 0.75),
        (0.10, 0.60, 0.10), (0.75, 0.10, 0.75), (0.75, 0.10, 0.10),
        (0.10, 0.10, 0.75),
    ]
    n = len(colores)
    franja_h = alto * 0.72
    for i, (r, g, b) in enumerate(colores):
        cr.set_source_rgb(r, g, b)
        cr.rectangle(i * ancho / n, 0, ancho / n + 1, franja_h)
        cr.fill()
    # franja inferior gris oscuro (como la referencia de negro/blanco de
    # las barras reales, simplificada a un bloque)
    cr.set_source_rgb(0.15, 0.15, 0.15)
    cr.rectangle(0, franja_h, ancho, alto - franja_h)
    cr.fill()

    # Ruido superpuesto — puntitos semitransparentes en posiciones
    # pseudo-deterministas (mismo seed siempre, así el placeholder no
    # "tiembla" entre repintados, que sería más ruido visual del bueno)
    import random
    rnd = random.Random(12345)
    n_puntos = int(ancho * alto * 0.06)
    for _ in range(n_puntos):
        px = rnd.randint(0, ancho - 1)
        py = rnd.randint(0, alto - 1)
        v = rnd.random()
        cr.set_source_rgba(v, v, v, 0.55)
        cr.rectangle(px, py, 1, 1)
        cr.fill()

    # Texto "SIN SEÑAL"
    cr.set_source_rgba(1, 1, 1, 0.92)
    cr.select_font_face("Sans", 0, 1)
    cr.set_font_size(max(9, min(16, ancho * 0.07)))
    texto = "❌ SIN SEÑAL"
    ext = cr.text_extents(texto)
    cr.move_to((ancho - ext.width) / 2 - ext.x_bearing,
               (alto - ext.height) / 2 - ext.y_bearing)
    cr.show_text(texto)

    _cache_barras_estaticas[clave] = surf
    return surf


def _rrect_fallback(cr, x, y, w, h, r):
    """Mismo trazo que self._imp_rrect (rectángulo de esquinas
    redondeadas) — copia mínima acá por si este mixin se usa en una
    pantalla que no incluye ImpactoMixin (mismo criterio defensivo que ya
    usa el resto de estos mixins con getattr/hasattr)."""
    cr.new_sub_path()
    cr.arc(x + w - r, y + r,     r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r,     y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r,     y + r,     r, 3.1416, 4.7124)
    cr.close_path()


class VistaPreviaMixin:
    """Pegar en DiagramaConexiones vía herencia múltiple."""

    # ── Init ─────────────────────────────────────────────────────────────
    def _visp_init(self, db_path: str) -> None:
        self._visp_db_path = db_path
        self._visp_modo = False
        self._visp_visualizador = VisualizadorSenal(db_path)
        self._visp_hover_id = None
        self._visp_hover_resultado = None
        self._visp_hover_pixbuf = None
        self._visp_panel_rect = None  # geometría del panel, para hit-testing futuro

    # ── Ítems de menú ────────────────────────────────────────────────────
    def _visp_crear_items_menu(self) -> list:
        self._visp_btn_modo = Gtk.CheckMenuItem(label=_("🖼 Vista previa de imagen"))
        self._visp_btn_modo.set_tooltip_text(
            "Con el modo activo, clic en un conector de salida muestra "
            "una imagen representativa de lo que circula por ahí — "
            "asignada a mano en una FUENTE, o compuesta automáticamente "
            "(matriz, mosaico, overlay/key) según lo que la alimenta."
        )
        self._visp_btn_modo.connect("toggled", self._visp_on_toggle_modo)
        return [self._visp_btn_modo]

    def _visp_on_toggle_modo(self, btn) -> None:
        if btn.get_active():
            self._visp_activar()
        else:
            self._visp_desactivar()

    def _visp_activar(self) -> None:
        # Exclusión mutua con "Diagnosticar falla" — NO. Con Escenario/
        # Impacto — TAMPOCO desde 2026-08-24 (a pedido explícito del
        # usuario, ver comentario completo en impacto_ui._imp_on_activar
        # y escenario_ui._esc_activar_modo para el detalle de por qué se
        # sacó y qué trade-off de orden de clic queda). Vista Previa nunca
        # bloquea el resto del diagrama (no consume paneo/minimapa/
        # selección), así que puede convivir con cualquiera de los otros
        # tres modos sin romper nada — el único matiz es que, si el
        # usuario hace clic justo sobre un puerto con más de un modo
        # activo a la vez, gana el que se revisa primero en _on_press()
        # (pantallas_avanzadas.py): hoy el orden es Escenario → Diagnóstico
        # → Vista Previa → Impacto.
        self._visp_modo = True
        if hasattr(self, "_visp_btn_modo") and not self._visp_btn_modo.get_active():
            self._visp_btn_modo.set_active(True)
        self._da.queue_draw()

    def _visp_desactivar(self) -> None:
        self._visp_modo = False
        self._visp_hover_id = None
        self._visp_hover_resultado = None
        self._visp_hover_pixbuf = None
        if hasattr(self, "_visp_btn_modo") and self._visp_btn_modo.get_active():
            self._visp_btn_modo.set_active(False)
        self._da.queue_draw()

    # ── Clic ─────────────────────────────────────────────────────────────
    def _visp_on_press(self, _da, event) -> bool:
        """Insertar en _on_press(): if self._visp_on_press(da, event): return True

        A diferencia de Modo Escenario, este modo NO bloquea el resto de
        los gestos del diagrama mientras está activo — sólo intercepta el
        clic IZQUIERDO cuando cae justo sobre un puerto. Todo lo demás
        (paneo con clic derecho/central, arrastre del minimapa, selección
        de nodos, rubber-band) tiene que seguir funcionando igual que si
        el modo estuviera apagado; por eso acá se devuelve False (no
        consumido) en cualquier caso que no sea "se abrió el diálogo",
        para que el evento siga su curso normal en _on_press().

        El modo NO se desactiva con clic derecho ni al cerrar el diálogo
        — la única forma de salir es destildar "🖼 Vista previa de imagen"
        en el menú (ver _visp_on_toggle_modo)."""
        if not self._visp_modo:
            return False
        if event.button != 1:
            return False   # dejar pasar: paneo con clic derecho/central
        wx, wy = self._s2w(event.x, event.y)
        hit = self._esc_puerto_bajo_cursor(wx, wy) if hasattr(self, "_esc_puerto_bajo_cursor") \
            else None
        if not hit:
            return False   # dejar pasar: minimapa, selección, rubber-band, etc.
        id_conector, _lado, _id_nodo = hit
        self._visp_refrescar_cache(id_conector)
        dlg = _DialogoVistaPrevia(
            self.get_toplevel(), self._visp_visualizador, id_conector,
            on_cambio=lambda: self._visp_refrescar_cache(id_conector))
        dlg.run()
        dlg.destroy()   # .run() NO cierra el diálogo por sí solo (ver informe
                        # de implementación, "Cerrar" quedaba sin efecto)
        return True

    def _visp_refrescar_cache(self, id_conector) -> None:
        """El motor cachea el grafo en memoria por instancia (ver
        senal_visual._cargar) — si se asignó/cambió algo desde el propio
        diálogo, se fuerza una recarga para que la próxima resolución ya
        lo vea, en vez de reabrir el diagrama."""
        self._visp_visualizador = VisualizadorSenal(self._visp_db_path)

    def _visp_on_motion(self, _da, event) -> bool:
        """Insertar AL INICIO de _on_motion(): if self._visp_on_motion(da, event): return

        Actualiza qué conector está bajo el cursor para que
        _visp_on_draw_overlay dibuje su imagen en la mini-ventana. No abre
        ningún diálogo — sólo hover, igual que el minimapa no interfiere
        con el resto de los gestos del diagrama."""
        if not self._visp_modo:
            return False
        wx, wy = self._s2w(event.x, event.y)
        hit = self._esc_puerto_bajo_cursor(wx, wy) if hasattr(self, "_esc_puerto_bajo_cursor") \
            else None
        nuevo_id = str(hit[0]) if hit else None
        if nuevo_id != self._visp_hover_id:
            self._visp_hover_id = nuevo_id
            self._visp_hover_resultado = (
                self._visp_visualizador.resolver(nuevo_id) if nuevo_id else None)
            self._visp_hover_pixbuf = None   # se carga perezosamente al dibujar
            self._da.queue_draw()
        return False   # no consume el evento: otros hovers (tooltips, etc.) siguen andando

    # ── Dibujo: mini-ventana en la esquina inferior izquierda ──────────────
    def _visp_on_draw_overlay(self, cr, W: int, H: int) -> None:
        """Insertar en _on_draw(), junto a los demás overlays (después de
        _senal_on_draw_overlay, antes de _draw_minimap para que ninguno
        tape al otro — este panel va en la esquina OPUESTA, así que en la
        práctica no compiten por espacio)."""
        if not self._visp_modo:
            self._visp_panel_rect = None
            return

        px = _PANEL_MARGIN
        py = H - _PANEL_H - _PANEL_MARGIN
        self._visp_panel_rect = (px, py, _PANEL_W, _PANEL_H)

        rrect = getattr(self, "_imp_rrect", None) or _rrect_fallback

        # fondo, mismo estilo que el minimapa
        cr.set_source_rgba(0.05, 0.05, 0.07, 0.88)
        rrect(cr, px, py, _PANEL_W, _PANEL_H, 6); cr.fill()
        cr.set_source_rgba(0.45, 0.48, 0.58, 0.90)
        cr.set_line_width(1.2)
        rrect(cr, px, py, _PANEL_W, _PANEL_H, 6); cr.stroke()

        # título
        cr.set_source_rgba(0.75, 0.78, 0.85, 0.90)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(10)
        cr.move_to(px + 8, py + 14)
        cr.show_text("🖼 vista previa")

        area_x, area_y = px + 8, py + 20
        area_w, area_h = _PANEL_W - 16, _PANEL_H - 44

        if not self._visp_hover_id or self._visp_hover_resultado is None:
            cr.set_source_rgba(0.55, 0.58, 0.65, 0.85)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(9)
            cr.move_to(area_x, area_y + area_h / 2)
            cr.show_text("Pasá el mouse sobre un conector")
            return

        r = self._visp_hover_resultado

        # plan_estado_senal_y_linaje.md, Función 1: si el conector
        # hoveado (o cualquiera de las fuentes usadas para componer la
        # imagen) quedó "caído" en una simulación activa, mostrar el
        # placeholder de barras estáticas en vez de la imagen real.
        #
        # OJO: se chequea self._visp_hover_id (el conector bajo el mouse)
        # y NO r.id_conector — cuando la resolución hace passthrough
        # simple hacia arriba (sin composición, ver
        # senal_visual._resolver_paso: "origen_conector = self._rev.get(...)")
        # r.id_conector termina siendo el conector donde se ENCONTRÓ la
        # imagen, no el que se está mirando; los saltos intermedios del
        # passthrough no quedan registrados en r.fuentes (eso sólo se
        # llena en _componer(), para el caso de combinación real). Usar
        # el id hoveado es lo que corresponde: "¿lo que estoy mirando
        # está caído?", más allá de dónde haya salido la imagen.
        caidos_fn = getattr(self, "_senal_conectores_caidos", None)
        esta_caido = False
        if caidos_fn is not None:
            caidos = caidos_fn()
            if caidos:
                ids_a_chequear = {str(self._visp_hover_id)} | {str(f) for f in r.fuentes}
                esta_caido = bool(ids_a_chequear & set(caidos.keys()))

        if esta_caido:
            surf_barras = generar_imagen_barras_estaticas(int(area_w), int(area_h))
            cr.set_source_surface(surf_barras, area_x, area_y)
            cr.paint()
            cr.set_source_rgba(0.95, 0.55, 0.20, 0.95)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(8)
            cr.move_to(px + 8, py + _PANEL_H - 8)
            cr.show_text("⚠ señal caída en el análisis activo")
            return

        if r.tiene_imagen and os.path.isfile(r.path):
            if self._visp_hover_pixbuf is None:
                try:
                    self._visp_hover_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        r.path, int(area_w), int(area_h), True)
                except GLib.Error:
                    self._visp_hover_pixbuf = False   # marca "no se pudo cargar"
            if self._visp_hover_pixbuf:
                pb = self._visp_hover_pixbuf
                ox = area_x + (area_w - pb.get_width()) / 2
                oy = area_y + (area_h - pb.get_height()) / 2
                Gdk.cairo_set_source_pixbuf(cr, pb, ox, oy)
                cr.paint()
            else:
                cr.set_source_rgba(0.7, 0.3, 0.3, 0.9)
                cr.move_to(area_x, area_y + 12)
                cr.show_text("no se pudo cargar la imagen")
        else:
            cr.set_source_rgba(0.55, 0.58, 0.65, 0.85)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(9)
            cr.move_to(area_x, area_y + area_h / 2)
            cr.show_text("(sin imagen)")

        # pie: origen + detalle, recortado para no desbordar el panel
        origen_legible = {"MANUAL": "manual", "COMPUESTA": "compuesta",
                          "SIN_IMAGEN": "sin imagen"}.get(r.origen, r.origen)
        pie = f"{origen_legible} — {r.detalle}"
        cr.set_source_rgba(0.75, 0.78, 0.85, 0.90)
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(8)
        max_chars = 42
        if len(pie) > max_chars:
            pie = pie[:max_chars - 1] + "…"
        cr.move_to(px + 8, py + _PANEL_H - 8)
        cr.show_text(pie)


# ─────────────────────────────────────────────────────────────────────────
# Diálogo de vista previa: muestra la imagen resuelta + explicación, y
# permite asignar/editar la imagen manual o la composición de ESTE
# conector puntual sin salir del diagrama.
# ─────────────────────────────────────────────────────────────────────────
class _DialogoVistaPrevia(Gtk.Dialog):
    def __init__(self, parent, visualizador: VisualizadorSenal, id_conector, on_cambio=None):
        nombre = Modelo._query(
            "SELECT c.nombre, e.nombre FROM conector c JOIN equipo e "
            "ON e.id_equipo = c.id_equipo WHERE c.id_conector=?", (id_conector,))
        titulo = f"{nombre[0][1]} — {nombre[0][0]}" if nombre else f"Conector {id_conector}"
        super().__init__(title=f"🖼 {titulo}", transient_for=parent, modal=True)
        self.set_default_size(420, 420)
        self._visualizador = visualizador
        self._id_conector = id_conector
        self._on_cambio = on_cambio

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_border_width(10)

        self._img_widget = Gtk.Image()
        box.pack_start(self._img_widget, True, True, 0)

        self._lbl_detalle = Gtk.Label(xalign=0)
        self._lbl_detalle.set_line_wrap(True)
        box.pack_start(self._lbl_detalle, False, False, 0)

        fila_botones = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_asignar = Gtk.Button(label=_("📷 Asignar imagen manual…"))
        btn_asignar.connect("clicked", self._on_asignar_manual)
        fila_botones.pack_start(btn_asignar, True, True, 0)
        btn_quitar = Gtk.Button(label=_("✖ Quitar imagen manual"))
        btn_quitar.connect("clicked", self._on_quitar_manual)
        fila_botones.pack_start(btn_quitar, True, True, 0)
        box.pack_start(fila_botones, False, False, 0)

        btn_composicion = Gtk.Button(label=_("🔀 Configurar composición…"))
        btn_composicion.set_tooltip_text(
            "Para una salida que combina varias entradas de este mismo "
            "equipo (mosaico tipo multiviewer, overlay con transparencia, "
            "key BASE+FILL+MATTE tipo DSK, o audio embebido con panel de "
            "vúmetros) — ver plan_vista_previa_visual_senal.md, sección 2.1.")
        btn_composicion.connect("clicked", self._on_configurar_composicion)
        box.pack_start(btn_composicion, False, False, 0)

        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self._refrescar()
        self.show_all()

    def _refrescar(self) -> None:
        r = self._visualizador.resolver(self._id_conector)
        if r.tiene_imagen and os.path.isfile(r.path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    r.path, 380, 260, True)
                self._img_widget.set_from_pixbuf(pixbuf)
            except GLib.Error:
                self._img_widget.set_from_icon_name(
                    "image-missing", Gtk.IconSize.DIALOG)
        else:
            self._img_widget.set_from_icon_name(
                "image-missing", Gtk.IconSize.DIALOG)
        origen_legible = {
            "MANUAL": "Imagen manual",
            "COMPUESTA": "Compuesta automáticamente",
            "SIN_IMAGEN": "Sin imagen",
        }.get(r.origen, r.origen)
        self._lbl_detalle.set_text(f"{origen_legible}: {r.detalle}")

    def _on_asignar_manual(self, _btn) -> None:
        dlg = Gtk.FileChooserDialog(
            title="Elegir imagen (PNG recomendado)",
            transient_for=self.get_toplevel(), action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        filtro = Gtk.FileFilter()
        filtro.set_name("Imágenes")
        for pat in ("*.png", "*.PNG", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG"):
            filtro.add_pattern(pat)
        dlg.add_filter(filtro)
        resp = dlg.run()
        path = dlg.get_filename() if resp == Gtk.ResponseType.OK else None
        dlg.destroy()
        if not path:
            return
        try:
            # Modelo.guardar_imagen_senal_conector convierte a PNG en
            # silencio si hace falta (JPG, etc. — ver
            # Modelo._normalizar_imagen_a_png) — eso no requiere avisar,
            # el contenido visual no cambia. Lo que SÍ tiene que llegar a
            # la interfaz es cuando el archivo directamente no se puede
            # usar como imagen: antes ese error sólo se veía en la
            # consola (recién aparecía más tarde, al componer), ahora se
            # detecta acá mismo, al momento de asignarla, y se avisa.
            Modelo.guardar_imagen_senal_conector(self._id_conector, path)
        except ImagenInvalidaError as ex:
            self._avisar_error(str(ex))
            return
        except Exception as ex:
            self._avisar_error(f"No se pudo asignar la imagen: {ex}")
            return
        if self._on_cambio:
            self._on_cambio()
        self._refrescar()

    def _avisar_error(self, texto: str) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
            text="No se pudo asignar la imagen")
        dlg.format_secondary_text(texto)
        dlg.run()
        dlg.destroy()

    def _on_quitar_manual(self, _btn) -> None:
        Modelo.quitar_imagen_senal_conector(self._id_conector)
        if self._on_cambio:
            self._on_cambio()
        self._refrescar()

    def _on_configurar_composicion(self, _btn) -> None:
        dlg = _DialogoEstrategiaVisual(self.get_toplevel(), self._id_conector)
        resp = dlg.run()
        cambio = (resp == Gtk.ResponseType.OK)
        dlg.destroy()
        if cambio:
            if self._on_cambio:
                self._on_cambio()
            self._refrescar()


# ─────────────────────────────────────────────────────────────────────────
# Diálogo de configuración de estrategia de composición (MOSAICO / OVERLAY
# / KEY) para UN conector de salida puntual. Ver plan_vista_previa_visual_
# senal.md, secciones 2.1/2.5 y decisión #3 de la sección 6 (default por
# coincidencia de nombre, siempre editable).
# ─────────────────────────────────────────────────────────────────────────
_PISTAS_POSICION = {
    "BASE":  ("BKGD", "BACKGROUND", "BASE", "FONDO"),
    "FILL":  ("FILL", "KEY VIDEO", "VIDEO"),
    "MATTE": ("MATTE", "ALPHA", "KEY ALPHA"),
}


class _DialogoEstrategiaVisual(Gtk.Dialog):
    def __init__(self, parent, id_conector_salida):
        fila = Modelo._query(
            "SELECT c.id_equipo, c.nombre, e.nombre, e.id_tipo_equipo FROM conector c "
            "JOIN equipo e ON e.id_equipo = c.id_equipo WHERE c.id_conector=?",
            (id_conector_salida,))
        if not fila:
            raise ValueError(f"conector {id_conector_salida} no encontrado")
        id_equipo, nombre_conector, nombre_equipo, id_tipo_equipo = fila[0]

        super().__init__(
            title=f"🔀 Composición — {nombre_equipo} / {nombre_conector}",
            transient_for=parent, modal=True)
        self.set_default_size(480, 440)
        self._id_conector_salida = str(id_conector_salida)
        self._id_equipo = id_equipo

        # Candidatos: todos los conectores IN de este mismo equipo,
        # EXCEPTO la propia salida (que obviamente no puede alimentarse a
        # sí misma).
        self._entradas = Modelo._query(
            "SELECT c.id_conector, c.nombre FROM conector c "
            "JOIN tipo_conector tc ON tc.id_tipo_conector = c.id_tipo_conector "
            "WHERE c.id_equipo=? AND UPPER(tc.nombre)='IN' ORDER BY c.nombre",
            (id_equipo,))

        existente = Modelo.estrategia_visual_efectiva(id_conector_salida)
        modo_actual = existente["modo"] if existente else "KEY"
        miembros_actuales = {
            m["posicion"]: m["id_conector"] for m in (existente or {}).get("miembros", [])}

        # BASE dinámico "<ASIGNADO POR MATRIZ>" (sólo tiene sentido en KEY):
        # se ofrece cuando el equipo tiene rol_senal='ENRUTADOR' (criterio
        # canónico ya usado en el resto del proyecto para identificar
        # matrices — ver equipos_enrutador_sin_matriz en senal_visual.py —
        # NUNCA se hardcodea un nombre/tipo de equipo puntual como "SWITCHER"
        # o "KUMO"), o cuando ya estaba elegido de antes (para no perder la
        # selección si mientras tanto cambiara el rol del tipo de equipo).
        rol_senal_equipo = Modelo.devolver_rol_senal_tipo_equipo(id_tipo_equipo)
        self._matriz_disponible_para_base = (
            rol_senal_equipo == "ENRUTADOR"
            or miembros_actuales.get("BASE") == Modelo.ID_ASIGNADO_POR_MATRIZ)

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_border_width(10)

        if not self._entradas:
            box.pack_start(Gtk.Label(
                label=_("Este equipo no tiene conectores de entrada (IN) — no hay nada que componer."),
                xalign=0), False, False, 0)
            self.add_button("Cerrar", Gtk.ResponseType.CANCEL)
            self.show_all()
            self._modo_combo = None
            return

        texto_ayuda = (
            "Elegí el modo y qué entrada de ESTE equipo ocupa cada "
            "rol. Los combos ofrecen las entradas del equipo; "
            "'(ninguna)' deja ese rol sin cubrir.")
        if self._matriz_disponible_para_base:
            texto_ayuda += (
                " En BASE también podés elegir <ASIGNADO POR MATRIZ>: en "
                "vez de una entrada fija, sigue lo que 'Editar matriz' "
                "tenga asignado a esta salida en cada momento.")
        box.pack_start(Gtk.Label(
            label=texto_ayuda, xalign=0, wrap=True),
            False, False, 0)

        fila_modo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        fila_modo.pack_start(Gtk.Label(label=_("Modo:")), False, False, 0)
        self._modo_combo = Gtk.ComboBoxText()
        for id_modo, etiqueta in (
                ("KEY", "KEY"), ("OVERLAY", "OVERLAY"), ("MOSAICO", "MOSAICO"),
                ("AUDIO_EMBEBIDO", "AUDIO EMBEBIDO")):
            self._modo_combo.append(id_modo, etiqueta)
        self._modo_combo.set_active_id(modo_actual)
        self._modo_combo.connect("changed", self._on_modo_changed)
        fila_modo.pack_start(self._modo_combo, False, False, 0)
        box.pack_start(fila_modo, False, False, 0)

        self._area_roles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self._area_roles, True, True, 0)

        self._miembros_actuales_iniciales = miembros_actuales
        self._render_roles(modo_actual, miembros_actuales)

        fila_botones = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_guardar = Gtk.Button(label=_("💾 Guardar"))
        btn_guardar.connect("clicked", self._on_guardar)
        fila_botones.pack_start(btn_guardar, True, True, 0)
        if existente:
            btn_quitar = Gtk.Button(label=_("🗑 Quitar composición"))
            btn_quitar.connect("clicked", self._on_quitar_estrategia)
            fila_botones.pack_start(btn_quitar, True, True, 0)
        box.pack_start(fila_botones, False, False, 0)

        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.show_all()

    # ── Construcción dinámica del área de roles según el modo elegido ──
    def _render_roles(self, modo, miembros_actuales) -> None:
        for child in self._area_roles.get_children():
            self._area_roles.remove(child)
        self._widgets_rol = {}   # posicion -> Gtk.ComboBoxText | Gtk.CheckButton

        if modo == "KEY":
            for posicion in ("BASE", "FILL", "MATTE"):
                self._widgets_rol[posicion] = self._fila_combo_entrada(
                    posicion, miembros_actuales.get(posicion),
                    permitir_matriz=(posicion == "BASE"
                                      and self._matriz_disponible_para_base))
        elif modo == "OVERLAY":
            self._widgets_rol["BASE"] = self._fila_combo_entrada(
                "BASE", miembros_actuales.get("BASE"))
            # Overlays: una fila por cada entrada disponible, con checkbox
            # ("¿participa?") — el orden de aparición define el z-order.
            self._checks_overlay = []
            for id_conector, nombre in self._entradas:
                fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                chk = Gtk.CheckButton(label=f"OVERLAY: {nombre}")
                ya_estaba = str(id_conector) in miembros_actuales.values() and \
                    any(pos.startswith("OVERLAY_") and cid == str(id_conector)
                        for pos, cid in miembros_actuales.items())
                chk.set_active(ya_estaba)
                fila.pack_start(chk, True, True, 0)
                self._checks_overlay.append((str(id_conector), chk))
                self._area_roles.pack_start(fila, False, False, 0)
        elif modo == "MOSAICO":
            self._checks_mosaico = []
            for id_conector, nombre in self._entradas:
                fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                chk = Gtk.CheckButton(label=f"Cuadrante: {nombre}")
                chk.set_active(str(id_conector) in miembros_actuales.values())
                fila.pack_start(chk, True, True, 0)
                self._checks_mosaico.append((str(id_conector), chk))
                self._area_roles.pack_start(fila, False, False, 0)
        elif modo == "AUDIO_EMBEBIDO":
            self._widgets_rol["BASE"] = self._fila_combo_entrada(
                "BASE", miembros_actuales.get("BASE"))
            self._area_roles.pack_start(Gtk.Label(
                label=_("Canales de audio a mostrar como vúmetro en el panel del margen derecho:"),
                xalign=0, wrap=True), False, False, 0)
            # Canales de audio: una fila por cada entrada disponible, con
            # checkbox ("¿se usa como fuente de audio?") — mismo patrón
            # que OVERLAY, el orden de aparición define el número de
            # canal mostrado en el panel (1, 2, 3...).
            self._checks_audio = []
            for id_conector, nombre in self._entradas:
                fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                chk = Gtk.CheckButton(label=f"AUDIO: {nombre}")
                ya_estaba = any(
                    pos.startswith("AUDIO_") and cid == str(id_conector)
                    for pos, cid in miembros_actuales.items())
                chk.set_active(ya_estaba)
                fila.pack_start(chk, True, True, 0)
                self._checks_audio.append((str(id_conector), chk))
                self._area_roles.pack_start(fila, False, False, 0)
        self._area_roles.show_all()

    def _fila_combo_entrada(self, posicion, id_seleccionado_actual, permitir_matriz=False):
        fila = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        fila.pack_start(Gtk.Label(label=f"{posicion}:", width_chars=8, xalign=0),
                        False, False, 0)
        combo = Gtk.ComboBoxText()
        combo.append("", "(ninguna)")
        if permitir_matriz:
            # Rol dinámico: en vez de una entrada fija, sigue en vivo lo
            # que 'Editar matriz' tenga asignado a ESTA salida. Sólo se
            # ofrece para BASE en KEY, y sólo si el equipo usa ruteo de
            # matriz (ver __init__, self._matriz_disponible_para_base).
            combo.append(Modelo.ID_ASIGNADO_POR_MATRIZ, "<ASIGNADO POR MATRIZ>")
        pistas = _PISTAS_POSICION.get(posicion, ())
        id_por_default = None
        for id_conector, nombre in self._entradas:
            combo.append(str(id_conector), nombre)
            if id_por_default is None and any(
                    p in (nombre or "").strip().upper() for p in pistas):
                id_por_default = str(id_conector)
        activo = id_seleccionado_actual or id_por_default or ""
        combo.set_active_id(activo)
        fila.pack_start(combo, True, True, 0)
        self._area_roles.pack_start(fila, False, False, 0)
        return combo

    def _on_modo_changed(self, combo) -> None:
        self._render_roles(combo.get_active_id(), self._miembros_actuales_iniciales)

    # ── Guardar / quitar ─────────────────────────────────────────────────
    def _on_guardar(self, _btn) -> None:
        modo = self._modo_combo.get_active_id()
        miembros = []
        if modo == "KEY":
            for posicion in ("BASE", "FILL", "MATTE"):
                sel = self._widgets_rol[posicion].get_active_id()
                if sel == Modelo.ID_ASIGNADO_POR_MATRIZ:
                    miembros.append({"tipo": "matriz",
                                     "posicion": posicion, "orden": 0})
                elif sel:
                    miembros.append({"tipo": "conector", "ref": int(sel),
                                     "posicion": posicion, "orden": 0})
            if not any(m["posicion"] == "BASE" for m in miembros):
                self._avisar("Key necesita al menos BASE — completá ese rol.")
                return
        elif modo == "OVERLAY":
            sel_base = self._widgets_rol["BASE"].get_active_id()
            if not sel_base:
                self._avisar("Overlay necesita BASE — completá ese rol.")
                return
            miembros.append({"tipo": "conector", "ref": int(sel_base),
                             "posicion": "BASE", "orden": 0})
            i = 1
            for id_conector, chk in self._checks_overlay:
                if chk.get_active():
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": f"OVERLAY_{i}", "orden": i})
                    i += 1
        elif modo == "MOSAICO":
            for i, (id_conector, chk) in enumerate(self._checks_mosaico):
                if chk.get_active():
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": str(i + 1), "orden": i})
            if len(miembros) < 2:
                self._avisar("Mosaico necesita al menos 2 entradas tildadas.")
                return
        elif modo == "AUDIO_EMBEBIDO":
            sel_base = self._widgets_rol["BASE"].get_active_id()
            if not sel_base:
                self._avisar("Audio embebido necesita BASE — completá ese rol.")
                return
            miembros.append({"tipo": "conector", "ref": int(sel_base),
                             "posicion": "BASE", "orden": 0})
            i = 1
            for id_conector, chk in self._checks_audio:
                if chk.get_active():
                    miembros.append({"tipo": "conector", "ref": int(id_conector),
                                     "posicion": f"AUDIO_{i}", "orden": i})
                    i += 1
            if i == 1:
                self._avisar(
                    "Audio embebido necesita al menos un canal de audio tildado.")
                return

        existente = Modelo.estrategia_visual_efectiva(self._id_conector_salida)
        id_estrategia = existente["id_estrategia"] if existente else None
        Modelo.guardar_estrategia_visual(
            id_estrategia, id_conector=int(self._id_conector_salida),
            modo=modo, miembros=miembros)
        self.response(Gtk.ResponseType.OK)

    def _on_quitar_estrategia(self, _btn) -> None:
        existente = Modelo.estrategia_visual_efectiva(self._id_conector_salida)
        if existente:
            Modelo.eliminar_estrategia_visual(existente["id_estrategia"])
        self.response(Gtk.ResponseType.OK)

    def _avisar(self, texto) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK, text=texto)
        dlg.run()
        dlg.destroy()
