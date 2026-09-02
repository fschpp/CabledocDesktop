"""EdicionConexionesMixin — alta/baja de conexiones (wires) por drag-and-drop entre puertos del diagrama de conexiones.

Entrega 5 del refactor de pantallas_avanzadas.py (ver
plan_refactor_pantallas_avanzadas.md): mixin extraído de DiagramaConexiones
junto con los otros 7 ya existentes (ImpactoMixin, RiesgoDiagramaMixin,
RiesgoSenalDiagramaMixin, SenalDiagramaMixin, EscenarioMixin,
VistaPreviaMixin, DiagnosticoMixin). Move 1:1: métodos idénticos a los que
tenía DiagramaConexiones, sólo re-indentados a su propia clase. No se
modificó ninguna lógica.
"""
from gi.repository import Gtk

from modelo import Modelo
from pantallas_comunes import _


class EdicionConexionesMixin:
    def _confirmar_pisar_conexion_wire(self, conflicto, nodo_destino, nombre_puerto_destino):
        """Avisa que el conector de destino ya tiene una conexión y que, de
        continuar, se eliminará ese extremo para dejar la nueva conexión en
        su lugar. Devuelve True si el usuario confirma."""
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("El conector de destino ya tiene una conexión"),
        )
        dlg.format_secondary_text(
            f"{nodo_destino['nombre']} · {nombre_puerto_destino} "
            + _("ya está conectado (cable {codigo}).").format(codigo=conflicto["nombre"])
            + "\n\n"
            + _("Esa conexión existente se eliminará y se creará la nueva "
                "conexión en su lugar. ¿Continuar?")
        )
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def _eliminar_extremo_conexion_wire(self, conflicto, con_id):
        """Elimina sólo el extremo de la conexión en conflicto que está en
        con_id (el otro extremo del cable no se toca). self._conns sólo
        guarda id_cable/nombre, así que se busca la fila real id_conexion
        directamente en la tabla conexion.

        Aviso de huérfano (plan_desarrollo_fantasma_rapido.md, Parte B):
        tras borrar, se revisa el OTRO extremo del cable en conflicto —
        no con_id. con_id es el puerto que está por recibir la conexión
        nueva (todos los llamadores de este método hacen `alta_conexion`
        sobre con_id justo después), así que ESE lado nunca queda
        huérfano; chequearlo acá sería además inseguro, porque si se
        borrara su equipo, el alta_conexion que sigue en el caller
        fallaría contra un conector recién borrado en cascada. El lado
        que sí puede quedar sin sentido es el otro: si era un equipo
        FANTASMA y esta era su única conexión, el cable que documentaba
        su extremo muerto acaba de reasignarse a un destino real en otro
        lado, así que se ofrece eliminarlo."""
        rows = Modelo._query(
            "SELECT id_conexion FROM conexion WHERE id_conector=? AND id_cable=?",
            (con_id, conflicto["id"]),
        )
        if not rows:
            return
        Modelo.eliminar_conexion(rows[0][0])
        self._avisar_si_fantasma_huerfano(conflicto["id"], con_id)

    def _avisar_si_fantasma_huerfano(self, id_cable, con_id_borrado):
        """Si el cable id_cable quedó con un único extremo real restante
        (con_id_borrado ya no cuenta, se acaba de borrar) y ese extremo
        pertenece a un equipo FANTASMA sin ninguna otra conexión, avisa y
        ofrece eliminarlo (mismo criterio que el aviso original del plan,
        adaptado al único punto del código actual donde se borra un
        extremo de conexión al reconectar — ver docstring de
        _eliminar_extremo_conexion_wire)."""
        filas = Modelo._query(
            "SELECT co.id_equipo, cx.id_conector "
            "FROM conexion cx JOIN conector co ON co.id_conector = cx.id_conector "
            "WHERE cx.id_cable=?",
            (id_cable,),
        )
        restantes = [(str(eq), str(con)) for eq, con in filas
                     if str(con) != str(con_id_borrado)]
        if not restantes:
            return  # el cable ya no tiene ningún extremo real cargado
        id_equipo = restantes[0][0]

        filas_eq = Modelo.devolver_equipo(id_equipo)
        if not filas_eq:
            return
        nombre_equipo   = filas_eq[0][1]
        id_tipo_actual  = filas_eq[0][8]
        id_tipo_fantasma = Modelo.devolver_id_tipo_equipo_fantasma()
        if id_tipo_fantasma is None or str(id_tipo_actual) != str(id_tipo_fantasma):
            return  # no es FANTASMA: comportamiento actual intacto
        if Modelo.devolver_cantidad_conexiones_de_equipo(id_equipo) > 1:
            return  # tiene otra conexión real además de ésta: no está huérfano

        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("El equipo fantasma «{nombre}» quedó sin conexiones").format(
                nombre=nombre_equipo),
        )
        dlg.format_secondary_text(_(
            "El cable que documentaba su extremo desconectado se acaba "
            "de reasignar a otro destino. ¿Eliminar el equipo fantasma?"))
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return

        Modelo.eliminar_equipo(id_equipo)   # cascada: conector → conexion
        self._nodos.pop(id_equipo, None)
        self._sel_ids.discard(id_equipo)
        if self._sel_id == id_equipo:
            self._sel_id = None
        self._reconstruir_conexiones()
        self._status(_("Equipo fantasma eliminado: {nombre}").format(nombre=nombre_equipo))
        self._da.queue_draw()

    def _cable_incompleto_en_puerto(self, con_id):
        """Si "Mostrar todas las conexiones incompletas" está activo y
        con_id tiene un cable con un solo extremo documentado (la punta
        "colgando" que dibuja `_draw_conexiones_incompletas`), devuelve
        (id_cable, codigo) para poder reutilizarlo. None si no aplica.

        Deliberadamente acotado a la variante "todas" (pedido explícito
        del usuario) — no mira `self._conexiones_incompletas` (variante
        por equipo seleccionado), aunque el dato sea el mismo; se puede
        extender más adelante si hace falta."""
        if not self._todas_conexiones_incompletas_activo:
            return None
        for c in self._todas_conexiones_incompletas:
            if c["conector"] == con_id:
                return c["id"], c["nombre"]
        return None

    def _crear_conexion_wire(self, src, dst):
        """Crea una conexión nueva entre dos puertos de equipos distintos,
        soltados vía arrastre. src/dst son (nodo, con_id, lado).

        Si alguno de los dos puertos ya tiene una conexión incompleta
        (cable con una sola punta documentada) y está activa "Mostrar
        todas las conexiones incompletas", se reutiliza ESE cable en vez
        de abrir el popup de buscar/crear cable: la punta que faltaba
        pasa a ser justo el otro extremo del arrastre."""
        nodo_a, cid_a, _lado_a = src
        nodo_b, cid_b, _lado_b = dst
        nombre_a = self._nombre_puerto(nodo_a, cid_a, _lado_a)
        nombre_b = self._nombre_puerto(nodo_b, cid_b, _lado_b)

        incompleta_a = self._cable_incompleto_en_puerto(cid_a)
        incompleta_b = self._cable_incompleto_en_puerto(cid_b)

        if incompleta_a or incompleta_b:
            if incompleta_a and incompleta_b:
                # Caso raro: cada puerto tiene su propio cable incompleto.
                # No hay forma automática de decidir cuál "gana" sin más
                # información del usuario — se avisa y no se hace nada,
                # para no unir por error dos cables incompletos distintos.
                self._status(_(
                    "Ambos conectores tienen su propia conexión "
                    "incompleta; no se puede reutilizar automáticamente. "
                    "Completá primero uno de los dos a mano."))
                return
            if incompleta_a:
                id_cable, codigo = incompleta_a
                nombre_extremo_previo = nombre_a
                con_nuevo, nodo_nuevo, nombre_nuevo = cid_b, nodo_b, nombre_b
            else:
                id_cable, codigo = incompleta_b
                nombre_extremo_previo = nombre_b
                con_nuevo, nodo_nuevo, nombre_nuevo = cid_a, nodo_a, nombre_a

            # El extremo YA documentado del cable incompleto no se toca;
            # sólo se chequea conflicto en el conector nuevo (el otro
            # extremo del arrastre).
            conflicto = self._conexion_existente_en_puerto(con_nuevo)
            if conflicto:
                if not self._confirmar_pisar_conexion_wire(conflicto, nodo_nuevo, nombre_nuevo):
                    return
                self._eliminar_extremo_conexion_wire(conflicto, con_nuevo)

            Modelo.alta_conexion(id_cable, con_nuevo)
            self._reconstruir_conexiones()
            # La conexión ya no es incompleta: refrescar la(s) lista(s) de
            # conexiones incompletas activas para que el tramo/cono
            # desaparezca del diagrama.
            if self._todas_conexiones_incompletas_activo:
                self._actualizar_todas_conexiones_incompletas()
            if self._conexiones_incompletas_activo:
                self._actualizar_conexiones_incompletas()
            self._status(
                _("Conexión completada reutilizando cable {codigo}: ").format(codigo=codigo)
                + f"{nombre_extremo_previo}  →  {nodo_nuevo['nombre']} · {nombre_nuevo}"
            )
            self._da.queue_draw()
            return

        puerto_a = {"id": cid_a, "nombre": nombre_a}
        puerto_b = {"id": cid_b, "nombre": nombre_b}

        # ¿El destino ya está ocupado por otra conexión distinta a esta?
        conflicto = self._conexion_existente_en_puerto(cid_b)
        if conflicto:
            if not self._confirmar_pisar_conexion_wire(conflicto, nodo_b, nombre_b):
                return

        existentes = Modelo.conexiones_entre_conectores(cid_a, cid_b)

        from pantallas_avanzadas import _DialogoCableRapido  # import diferido: evita ciclo con pantallas_avanzadas.py
        dlg = _DialogoCableRapido(
            puerto_a=puerto_a, nodo_a=nodo_a,
            puerto_b=puerto_b, nodo_b=nodo_b,
            existentes=existentes, parent=self,
        )
        resp = dlg.run()
        id_cable = dlg.id_cable_resultado
        dlg.destroy()

        if resp == Gtk.ResponseType.OK and id_cable:
            if conflicto:
                self._eliminar_extremo_conexion_wire(conflicto, cid_b)
            Modelo.alta_conexion(id_cable, cid_a)
            Modelo.alta_conexion(id_cable, cid_b)
            self._reconstruir_conexiones()
            self._status(
                _("Conexión creada: ")
                + f"{nodo_a['nombre']} · {nombre_a}  →  {nodo_b['nombre']} · {nombre_b}"
            )
            self._da.queue_draw()


