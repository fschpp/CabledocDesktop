"""
acerca_de.py — Diálogo "Acerca de..." de CableDoc Desktop.
Módulo independiente: solo depende de GTK3 y la librería estándar
(no importa modelo.py, i18n.py ni ningún otro archivo del proyecto).
"""
import os
import re
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Pango, GdkPixbuf
try:
    from i18n import _, cargar_idioma_guardado
    cargar_idioma_guardado()
except ImportError:
    def _(t): return t
    def cargar_idioma_guardado(): pass
_DIR = os.path.dirname(os.path.abspath(__file__))
README_PATH    = os.path.join(_DIR, "README.md")
CHANGELOG_PATH = os.path.join(_DIR, "changelog.txt")
ICONO_APP_PATH = os.path.join(_DIR, "assets", "icono_aplicacion.png")


def _leer_texto(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        return f"(No se pudo leer {os.path.basename(path)}: {exc})"


def _renderizar_markdown(tv, texto):
    """Renderizado simple de Markdown (encabezados, negrita, itálica,
    código, viñetas) suficiente para un README.md típico."""
    buf = tv.get_buffer()
    buf.set_text(texto)
    if not texto.strip():
        return

    tag_h1   = buf.create_tag("h1", scale=1.7, weight=700)
    tag_h2   = buf.create_tag("h2", scale=1.35, weight=700)
    tag_h3   = buf.create_tag("h3", scale=1.12, weight=700)
    tag_bold = buf.create_tag("bold", weight=700)
    tag_ital = buf.create_tag("italic", style=Pango.Style.ITALIC)
    tag_mono = buf.create_tag("mono", family="Monospace",
                              background="#eeeeee")
    tag_bul  = buf.create_tag("bullet", left_margin=18)

    it = buf.get_start_iter()
    while True:
        line_start = it.copy()
        it.forward_to_line_end()
        line_end = it.copy()
        line = buf.get_text(line_start, line_end, False)
        stripped = line.strip()
        if stripped.startswith("### "):
            s2 = line_start.copy(); s2.forward_chars(4)
            buf.apply_tag(tag_h3, s2, line_end)
        elif stripped.startswith("## "):
            s2 = line_start.copy(); s2.forward_chars(3)
            buf.apply_tag(tag_h2, s2, line_end)
        elif stripped.startswith("# "):
            s2 = line_start.copy(); s2.forward_chars(2)
            buf.apply_tag(tag_h1, s2, line_end)
        elif stripped.startswith(("- ", "* ")):
            buf.apply_tag(tag_bul, line_start, line_end)
        if not it.forward_line():
            break

    start = buf.get_start_iter(); end = buf.get_end_iter()
    full = buf.get_text(start, end, False)
    for pattern, tag in (
        (r"\*\*(.+?)\*\*", tag_bold),
        (r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", tag_ital),
        (r"`([^`]+)`", tag_mono),
    ):
        for m in re.finditer(pattern, full):
            s_it = buf.get_iter_at_offset(m.start())
            e_it = buf.get_iter_at_offset(m.end())
            buf.apply_tag(tag, s_it, e_it)


class VentanaTexto(Gtk.Window):
    """Ventana simple de solo lectura para mostrar un archivo de texto plano."""

    def __init__(self, titulo, texto, parent=None):
        super().__init__(title=titulo)
        self.set_default_size(700, 550)
        if parent is not None:
            self.set_transient_for(parent)
        self.connect("delete-event", lambda w, e: self.destroy())

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD)
        tv.set_monospace(True)
        tv.set_left_margin(8);  tv.set_right_margin(8)
        tv.set_top_margin(8);   tv.set_bottom_margin(8)
        tv.get_buffer().set_text(texto)
        sw.add(tv)
        self.add(sw)
        self.show_all()


class DialogoAcercaDe(Gtk.Dialog):
    def __init__(self, version="", parent=None,
                 readme_path=README_PATH, changelog_path=CHANGELOG_PATH):
        super().__init__(title="Acerca de…", transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(640, 620)
        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self._changelog_path = changelog_path

        area = self.get_content_area()
        area.set_spacing(4)
        area.set_margin_start(14); area.set_margin_end(14)
        area.set_margin_top(12);   area.set_margin_bottom(10)

        img_logo = Gtk.Image()
        try:
            pixbuf_logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                ICONO_APP_PATH, 96, 96, True)
            img_logo.set_from_pixbuf(pixbuf_logo)
            img_logo.set_halign(Gtk.Align.CENTER)
            area.pack_start(img_logo, False, False, 4)
        except Exception:
            pass

        lbl_titulo = Gtk.Label(xalign=0.5)
        lbl_titulo.set_markup(
            "<span size='xx-large' weight='bold'>Cabledoc Desktop</span>")
        area.pack_start(lbl_titulo, False, False, 0)

        lbl_sub = Gtk.Label(xalign=0.5)
        lbl_sub.set_markup(
            "<i>Software de documentación de cableado e infraestructura "
            "para broadcasting</i>")
        lbl_sub.set_line_wrap(True)
        lbl_sub.set_justify(Gtk.Justification.CENTER)
        area.pack_start(lbl_sub, False, False, 4)

        lbl_meta = Gtk.Label(xalign=0.5)
        lbl_meta.set_markup(
            "Copyright fschpp 2023\n"
            "Licencia:  GNU General Public License version 2 (GPL v2)\n"
            f"Versión: {version}"
        )
        lbl_meta.set_justify(Gtk.Justification.CENTER)
        area.pack_start(lbl_meta, False, False, 6)

        area.pack_start(Gtk.Separator(), False, False, 6)

        lbl_readme = Gtk.Label(xalign=0)
        lbl_readme.set_markup("<b>README</b>")
        area.pack_start(lbl_readme, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        tv_readme = Gtk.TextView()
        tv_readme.set_editable(False)
        tv_readme.set_cursor_visible(False)
        tv_readme.set_wrap_mode(Gtk.WrapMode.WORD)
        tv_readme.set_left_margin(6); tv_readme.set_right_margin(6)
        _renderizar_markdown(tv_readme, _leer_texto(readme_path))
        sw.add(tv_readme)
        area.pack_start(sw, True, True, 4)

        btn_changelog = Gtk.Button(label=_("📋 Ver changelog…"))
        btn_changelog.connect("clicked", self._on_changelog)
        area.pack_start(btn_changelog, False, False, 4)

        self.show_all()

    def _on_changelog(self, btn):
        texto = _leer_texto(self._changelog_path)
        VentanaTexto("Changelog — CableDoc", texto, parent=self)


def abrir_acerca_de(version="", parent=None):
    dlg = DialogoAcercaDe(version=version, parent=parent)
    dlg.run()
    dlg.destroy()
