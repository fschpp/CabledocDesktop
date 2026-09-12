"""
CableDoc Kivy - Catálogo de Imágenes.

Equivalente a ImagenesListado / _DialogoImagen de cabledoc.py (GTK).
"""

import os
import shutil

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

from widgets_base import (
    ListadoPopup, FileChooserPopup, grid_formulario, fila_etiqueta,
    etiqueta_ultima_edicion, titulo_con_nombre, s, _,
    ALTO_BOTON, ALTO_ENTRY, FUENTE_NORMAL, FUENTE_CHICA,
)
from modelo import Modelo, IMG_DIR


class ImagenesListado(ListadoPopup):
    def __init__(self, **kwargs):
        super().__init__(_("Imágenes"),
                         [_("ID"), _("Ruta archivo"), _("Descripción")],
                         **kwargs)
        self.cargar_datos()

    def cargar_datos(self):
        self._poblar(Modelo.devolver_todas_las_imagenes())

    def nuevo(self):
        DialogoImagen(on_guardado=self.cargar_datos).open()

    def editar(self, id_):
        DialogoImagen(id_imagen=id_, on_guardado=self.cargar_datos).open()

    def eliminar(self, id_):
        Modelo.eliminar_imagen(id_)


class DialogoImagen(Popup):
    def __init__(self, id_imagen=None, on_guardado=None, **kwargs):
        self.id_imagen = id_imagen
        self._on_guardado = on_guardado

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        g = grid_formulario(cols=1)

        fila_etiqueta(g, _("Ruta archivo:"))
        hb = BoxLayout(size_hint_y=None, height=ALTO_ENTRY, spacing=dp(4))
        self.e_path = TextInput(multiline=False, font_size=FUENTE_NORMAL)
        btn_explorar = Button(text=_("Explorar"), size_hint_x=None,
                             width=dp(110), font_size=FUENTE_CHICA)
        btn_explorar.bind(on_release=self._explorar)
        hb.add_widget(self.e_path)
        hb.add_widget(btn_explorar)
        g.add_widget(hb)

        fila_etiqueta(g, _("Descripción:"))
        self.e_desc = TextInput(multiline=False, size_hint_y=None,
                                height=ALTO_ENTRY, font_size=FUENTE_NORMAL)
        g.add_widget(self.e_desc)
        box.add_widget(g)

        if id_imagen:
            rows = Modelo.devolver_imagen(id_imagen)
            if rows:
                self.e_path.text = s(rows[0][1])
                self.e_desc.text = s(rows[0][2])

        etq = etiqueta_ultima_edicion("imagen", "id_imagen", id_imagen)
        if etq:
            box.add_widget(etq)

        hb_btn = BoxLayout(size_hint_y=None, height=ALTO_BOTON, spacing=dp(8))
        btn_cancelar = Button(text=_("Cancelar"), font_size=FUENTE_NORMAL)
        btn_aceptar = Button(text=_("Aceptar"), font_size=FUENTE_NORMAL)
        btn_cancelar.bind(on_release=lambda *_a: self.dismiss())
        btn_aceptar.bind(on_release=self._guardar)
        hb_btn.add_widget(btn_cancelar)
        hb_btn.add_widget(btn_aceptar)
        box.add_widget(hb_btn)

        titulo = _("Editar Imagen") if id_imagen else _("Nueva Imagen")
        if id_imagen:
            titulo = titulo_con_nombre(titulo, self.e_path.text)

        super().__init__(title=titulo, content=box,
                         size_hint=(1, 1), **kwargs)

    def _explorar(self, *_a):
        def _elegida(ruta):
            os.makedirs(IMG_DIR, exist_ok=True)
            nombre = os.path.basename(ruta)
            destino = os.path.join(IMG_DIR, nombre)
            if not os.path.exists(destino):
                try:
                    shutil.copy2(ruta, destino)
                except Exception:
                    pass
            self.e_path.text = nombre

        FileChooserPopup(titulo=_("Seleccionar imagen"),
                         filtros=["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp"],
                         on_seleccionar=_elegida).open()

    def _guardar(self, *_a):
        path = self.e_path.text.strip() or None
        desc = self.e_desc.text.strip() or None
        if self.id_imagen:
            Modelo.modificacion_imagen(self.id_imagen, path, desc)
        else:
            Modelo.alta_imagen(path, desc)
        self.dismiss()
        if self._on_guardado:
            self._on_guardado()
