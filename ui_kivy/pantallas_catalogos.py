"""
CableDoc Kivy - Catálogos simples (Marcas, Tipos de Equipo, Tipos de
Conector, Tipos de Cable, Tipos de Ficha).

Todas estas entidades tienen el mismo patrón: tabla (id, nombre) con alta,
edición y baja mediante un único campo de texto. En GTK cada una era una
clase separada casi idéntica (MarcasListado, TiposEquipoListado, ...);
acá se generan con una única fábrica para evitar repetir código,
preservando los mismos nombres de clase para quien venga del original.
"""

from widgets_base import ListadoPopup, DialogoNombre, titulo_con_nombre, mostrar_error, s, _
from core.modelo import Modelo


def _crear_listado_simple(titulo, columnas, fn_todos, fn_uno, fn_alta,
                          fn_modificar, fn_eliminar, titulo_nuevo,
                          titulo_editar):
    """Fábrica: construye una subclase de ListadoPopup para una entidad
    con un solo campo 'nombre' (Marca, Tipo de Equipo, etc.)."""

    class _ListadoSimple(ListadoPopup):
        def __init__(self, modo_seleccion=False, on_seleccionar=None, **kwargs):
            super().__init__(titulo, columnas, modo_seleccion=modo_seleccion,
                             on_seleccionar=on_seleccionar, **kwargs)
            self.cargar_datos()

        def cargar_datos(self):
            self._poblar(fn_todos())

        def nuevo(self):
            def _guardar(valor):
                fn_alta(valor)
                self.cargar_datos()
            DialogoNombre(titulo_nuevo, on_aceptar=_guardar).open()

        def editar(self, id_):
            rows = fn_uno(id_)
            if not rows:
                return

            def _guardar(valor):
                fn_modificar(id_, valor)
                self.cargar_datos()
            DialogoNombre(titulo_con_nombre(titulo_editar, rows[0][1]),
                         valor=s(rows[0][1]), on_aceptar=_guardar).open()

        def eliminar(self, id_):
            fn_eliminar(id_)

    _ListadoSimple.__name__ = titulo.replace(" ", "") + "Listado"
    return _ListadoSimple


MarcasListado = _crear_listado_simple(
    _("Marcas"), [_("ID"), _("Marca")],
    Modelo.devolver_todas_las_marcas, Modelo.devolver_marca,
    Modelo.alta_marca, Modelo.modificacion_marca, Modelo.eliminar_marca,
    _("Nueva Marca"), _("Editar Marca"),
)

TiposEquipoListado = _crear_listado_simple(
    _("Tipos de Equipo"), [_("ID"), _("Tipo de Equipo")],
    Modelo.devolver_todos_los_tipos, Modelo.devolver_tipo,
    Modelo.alta_tipo, Modelo.modificacion_tipo, Modelo.eliminar_tipo,
    _("Nuevo Tipo de Equipo"), _("Editar Tipo de Equipo"),
)

TiposConectorListado = _crear_listado_simple(
    _("Tipos de Conector"), [_("ID"), _("Tipo de Conector")],
    Modelo.devolver_tipos_conectores, Modelo.devolver_tipo_conector,
    Modelo.agregar_tipo_conector, Modelo.modificar_tipo_conector,
    Modelo.eliminar_tipo_conector,
    _("Nuevo Tipo de Conector"), _("Editar Tipo de Conector"),
)

TiposCableListado = _crear_listado_simple(
    _("Tipos de Cable"), [_("ID"), _("Tipo de Cable")],
    Modelo.devolver_todos_los_tipos_cable, Modelo.devolver_tipo_cable,
    Modelo.alta_tipo_cable, Modelo.modificacion_tipo_cable,
    Modelo.eliminar_tipo_cable,
    _("Nuevo Tipo de Cable"), _("Editar Tipo de Cable"),
)

TiposFichaListado = _crear_listado_simple(
    _("Tipos de Ficha"), [_("ID"), _("Tipo de Ficha")],
    Modelo.devolver_todos_los_tipos_ficha, Modelo.devolver_tipo_ficha,
    Modelo.alta_tipo_ficha, Modelo.modificacion_tipo_ficha,
    Modelo.eliminar_tipo_ficha,
    _("Nuevo Tipo de Ficha"), _("Editar Tipo de Ficha"),
)
