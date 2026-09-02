"""
escenario_engine.py — "Modo Escenario" para CableDoc
=====================================================
Mismo rol que risk_engine.py: orquesta Modelo (persistencia) +
GraphImpactAnalyzer (motor de grafo), sin saber nada de GTK/Cairo — la UI
vive en escenario_ui.py::EscenarioMixin.

Ver CableDoc_Plan_Escenarios_Diagrama.md, secciones 2 y 3, para el diseño
completo. Resumen:

  Escenario = una lista de "cambios" (falla de equipo | desconexión de
  cable | conexión virtual de reconexión de emergencia) que se editan en
  memoria y se persisten incrementalmente en las tablas `escenario` /
  `escenario_cambio` (Modelo.agregar_cambio_escenario / eliminar_cambio_
  escenario), y se evalúan TODOS JUNTOS en un solo cálculo llamando a
  GraphImpactAnalyzer.simular_escenario() — no se persiste el resultado de
  la simulación, se recalcula al vuelo (mismo criterio que el resto del
  motor de impacto: es barato, ~5-25ms según el propio historial de
  cambios del proyecto).

  "Aplicar a la infraestructura real" (Escenario.aplicar_a_infraestructura)
  es la única operación de este módulo que escribe en `conexion`/`cable`
  reales, y sólo corre tras una confirmación explícita en la UI, dentro de
  una única transacción (ver sección 4.6 del plan).

Uso típico (ver escenario_ui.py para el flujo completo):

    esc = Escenario(db_path, id_escenario=None, nombre="Falla del switcher")
    esc.guardar()                              # crea la fila en `escenario`
    esc.agregar_falla_equipo("42")
    esc.agregar_conexion_virtual("2213", "515")
    resultado = esc.evaluar()                  # ResultadoEscenario
    ...
    resumen = esc.resumen_aplicar()            # qué se va a DELETE/INSERT
    # ... diálogo de confirmación con `resumen` ...
    esc.aplicar_a_infraestructura()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from modelo import Modelo
from graph_impact import GraphImpactAnalyzer, ResultadoEscenario


# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CambioPendiente:
    """Un cambio dentro de un escenario, en memoria (espejo de una fila de
    escenario_cambio; id_cambio es None si todavía no se persistió)."""
    id_cambio:     Optional[int]
    tipo:          str          # 'falla_equipo' | 'desconexion_cable' | 'conexion_virtual'
    id_equipo:     Optional[str] = None
    id_cable:      Optional[str] = None
    id_conector_a: Optional[str] = None
    id_conector_b: Optional[str] = None

    def etiqueta(self, analyzer: "GraphImpactAnalyzer") -> str:
        """Texto legible para listar el cambio en el panel/diálogo."""
        if self.tipo == "falla_equipo":
            nombre = analyzer.nombre_equipo(self.id_equipo) if analyzer.esta_construido() else self.id_equipo
            return f"🔺 Falla de equipo: {nombre}"
        if self.tipo == "desconexion_cable":
            nombre = analyzer.nombre_cable(self.id_cable) if analyzer.esta_construido() else self.id_cable
            return f"✕ Cable cortado: {nombre}"
        if self.tipo == "conexion_virtual":
            return f"🔗 Reconexión virtual: conector {self.id_conector_a} → {self.id_conector_b}"
        return f"({self.tipo})"


class Escenario:
    """
    Ciclo de vida:
        Escenario.crear_nuevo(db_path, nombre, descripcion)  — alta + carga
        Escenario(db_path, id_escenario=N)                   — abrir uno guardado
        .agregar_falla_equipo / .agregar_desconexion_cable /
            .agregar_conexion_virtual                        — editar (persiste al toque)
        .quitar_cambio(cambio)                                — sacar un cambio
        .evaluar()                                            — ResultadoEscenario
        .resumen_aplicar() / .aplicar_a_infraestructura()      — "Aplicar…"
    """

    def __init__(self, db_path: str, id_escenario: Optional[int] = None):
        self._db_path = db_path
        self.id_escenario = id_escenario
        self.nombre = ""
        self.descripcion = ""
        self.estado = "borrador"
        self.cambios: list[CambioPendiente] = []
        self._analyzer = GraphImpactAnalyzer(db_path)
        if id_escenario is not None:
            self.recargar()

    # ── Alta / carga ─────────────────────────────────────────────────────────

    @classmethod
    def crear_nuevo(cls, db_path: str, nombre: str, descripcion: str = "") -> "Escenario":
        id_esc = Modelo.crear_escenario(nombre, descripcion)
        return cls(db_path, id_escenario=id_esc)

    def recargar(self) -> None:
        """Relee nombre/descripción/estado/cambios desde la BD (descarta
        cualquier edición en memoria no persistida — en la práctica no
        debería haber ninguna, porque agregar_*/quitar_cambio persisten al
        toque)."""
        if self.id_escenario is None:
            return
        fila = Modelo.devolver_escenario(self.id_escenario)
        if fila:
            _, self.nombre, self.descripcion, self.estado, _fc, _fe = fila
        self.cambios = [
            CambioPendiente(
                id_cambio=c[0], tipo=c[1],
                id_equipo=str(c[2]) if c[2] is not None else None,
                id_cable=str(c[3]) if c[3] is not None else None,
                id_conector_a=str(c[4]) if c[4] is not None else None,
                id_conector_b=str(c[5]) if c[5] is not None else None,
            )
            for c in Modelo.devolver_cambios_de_escenario(self.id_escenario)
        ]

    def renombrar(self, nombre: str, descripcion: str = "") -> None:
        self.nombre, self.descripcion = nombre, descripcion
        if self.id_escenario is not None:
            Modelo.modificar_escenario(self.id_escenario, nombre, descripcion)

    def guardar_como(self, nombre: str, descripcion: str = "") -> int:
        """Persiste un escenario que hasta ahora sólo vivía en memoria
        (id_escenario is None — se puede armar y probar un escenario sin
        nombre antes de decidir guardarlo). Si ya estaba guardado, es
        equivalente a renombrar(). Devuelve el id_escenario."""
        if self.id_escenario is not None:
            self.renombrar(nombre, descripcion)
            return self.id_escenario
        self.id_escenario = Modelo.crear_escenario(nombre, descripcion)
        self.nombre, self.descripcion = nombre, descripcion
        for c in self.cambios:
            c.id_cambio = Modelo.agregar_cambio_escenario(
                self.id_escenario, c.tipo, id_equipo=c.id_equipo,
                id_cable=c.id_cable, id_conector_a=c.id_conector_a,
                id_conector_b=c.id_conector_b)
        return self.id_escenario

    def eliminar(self) -> None:
        if self.id_escenario is not None:
            Modelo.eliminar_escenario(self.id_escenario)
        self.cambios = []

    # ── Edición de cambios (persisten de inmediato, ver docstring de clase) ──

    def _ya_existe(self, tipo: str, **claves) -> bool:
        return any(
            c.tipo == tipo and all(getattr(c, k) == v for k, v in claves.items())
            for c in self.cambios
        )

    def agregar_falla_equipo(self, id_equipo) -> Optional[CambioPendiente]:
        id_equipo = str(id_equipo)
        if self._ya_existe("falla_equipo", id_equipo=id_equipo):
            return None
        id_cambio = None
        if self.id_escenario is not None:
            id_cambio = Modelo.agregar_cambio_escenario(
                self.id_escenario, "falla_equipo", id_equipo=id_equipo)
        cambio = CambioPendiente(id_cambio, "falla_equipo", id_equipo=id_equipo)
        self.cambios.append(cambio)
        return cambio

    def agregar_desconexion_cable(self, id_cable) -> Optional[CambioPendiente]:
        id_cable = str(id_cable)
        if self._ya_existe("desconexion_cable", id_cable=id_cable):
            return None
        id_cambio = None
        if self.id_escenario is not None:
            id_cambio = Modelo.agregar_cambio_escenario(
                self.id_escenario, "desconexion_cable", id_cable=id_cable)
        cambio = CambioPendiente(id_cambio, "desconexion_cable", id_cable=id_cable)
        self.cambios.append(cambio)
        return cambio

    def agregar_conexion_virtual(self, id_conector_a, id_conector_b) -> Optional[CambioPendiente]:
        id_conector_a, id_conector_b = str(id_conector_a), str(id_conector_b)
        if id_conector_a == id_conector_b:
            return None  # no tiene sentido conectar un puerto consigo mismo
        id_cambio = None
        if self.id_escenario is not None:
            id_cambio = Modelo.agregar_cambio_escenario(
                self.id_escenario, "conexion_virtual",
                id_conector_a=id_conector_a, id_conector_b=id_conector_b)
        cambio = CambioPendiente(id_cambio, "conexion_virtual",
                                  id_conector_a=id_conector_a, id_conector_b=id_conector_b)
        self.cambios.append(cambio)
        return cambio

    def quitar_cambio(self, cambio: CambioPendiente) -> None:
        if cambio.id_cambio is not None:
            Modelo.eliminar_cambio_escenario(cambio.id_cambio)
        if cambio in self.cambios:
            self.cambios.remove(cambio)

    def cambio_en_equipo(self, id_equipo) -> Optional[CambioPendiente]:
        id_equipo = str(id_equipo)
        return next((c for c in self.cambios
                     if c.tipo == "falla_equipo" and c.id_equipo == id_equipo), None)

    def cambio_en_cable(self, id_cable) -> Optional[CambioPendiente]:
        id_cable = str(id_cable)
        return next((c for c in self.cambios
                      if c.tipo == "desconexion_cable" and c.id_cable == id_cable), None)

    def vaciar(self) -> None:
        """Quita TODOS los cambios (botón 'Descartar todo'), sin borrar el
        escenario en sí."""
        if self.id_escenario is not None:
            Modelo.eliminar_cambios_de_escenario(self.id_escenario)
        self.cambios = []

    # ── Evaluación (motor de grafo) ──────────────────────────────────────────

    def asegurar_grafo(self) -> bool:
        if self._analyzer.esta_construido():
            return True
        try:
            self._analyzer.construir_grafo()
            return True
        except Exception:
            return False

    def invalidar_grafo(self) -> None:
        """Llamar tras aplicar_a_infraestructura() o cualquier otro cambio
        externo a la BD real, para forzar reconstrucción en la próxima
        evaluación."""
        self._analyzer.invalidar()

    @property
    def analyzer(self) -> GraphImpactAnalyzer:
        return self._analyzer

    def _sets_actuales(self):
        cables = {c.id_cable for c in self.cambios
                  if c.tipo == "desconexion_cable" and c.id_cable}
        equipos = {c.id_equipo for c in self.cambios
                   if c.tipo == "falla_equipo" and c.id_equipo}
        virtuales = [(c.id_conector_a, c.id_conector_b) for c in self.cambios
                     if c.tipo == "conexion_virtual" and c.id_conector_a and c.id_conector_b]
        return cables, equipos, virtuales

    def evaluar(self) -> Optional[ResultadoEscenario]:
        """Corre GraphImpactAnalyzer.simular_escenario() con los cambios
        actuales. None si el grafo no se pudo construir (graphqlite no
        disponible, BD sin tablas de conexión, etc.) — la UI debe mostrar
        un aviso en ese caso, no romper."""
        if not self.asegurar_grafo():
            return None
        cables, equipos, virtuales = self._sets_actuales()
        return self._analyzer.simular_escenario(
            cables_cortados=cables, equipos_fallados=equipos,
            conexiones_virtuales=virtuales)

    # ── Aplicar a la infraestructura real ────────────────────────────────────

    def resumen_aplicar(self) -> dict:
        """Arma, SIN tocar la base, el resumen de qué se va a hacer si se
        confirma 'Aplicar a infraestructura' — para el diálogo de
        confirmación (sección 4.6 del plan). No incluye las fallas de
        equipo: son sólo para la simulación, no tienen una operación real
        equivalente en el modelo de datos actual (no hay un campo
        'apagado' de equipo)."""
        self.asegurar_grafo()
        cables_a_desconectar = []
        reconexiones = []
        for c in self.cambios:
            if c.tipo == "desconexion_cable" and c.id_cable:
                nombre = (self._analyzer.nombre_cable(c.id_cable)
                          if self._analyzer.esta_construido() else c.id_cable)
                cables_a_desconectar.append((c.id_cable, nombre))
            elif c.tipo == "conexion_virtual" and c.id_conector_a and c.id_conector_b:
                reconexiones.append((c.id_conector_a, c.id_conector_b))
        return {
            "cables_a_desconectar": cables_a_desconectar,
            "reconexiones": reconexiones,
        }

    def aplicar_a_infraestructura(self) -> dict:
        """
        Aplica los cambios reales, dentro de UNA transacción explícita:
          - desconexion_cable: borra (DELETE) todas las filas de `conexion`
            de ese cable — el cable en sí no se borra (queda como
            historial, mismo criterio que fusionar_cables/eliminar_conexion
            en el resto de la app), sólo queda sin extremos conectados.
          - conexion_virtual: da de alta un cable nuevo (código automático
            vía Modelo.siguiente_codigo_temporal(), mismo mecanismo que ya
            usa EditorConexiones) y dos filas en `conexion`, una por cada
            conector.
          - falla_equipo: no se aplica (ver resumen_aplicar).
        Marca el escenario como 'aplicado' e invalida el grafo (la
        infraestructura real cambió). Devuelve un resumen de lo hecho.
        """
        resumen = {"cables_desconectados": [], "cables_creados": [],
                   "conexiones_creadas": []}
        with Modelo._conn_ctx() as conn:
            for c in self.cambios:
                if c.tipo == "desconexion_cable" and c.id_cable:
                    filas = conn.execute(
                        "SELECT id_conexion FROM conexion WHERE id_cable=?",
                        (c.id_cable,)).fetchall()
                    for (id_conexion,) in filas:
                        conn.execute(
                            "DELETE FROM conexion WHERE id_conexion=?", (id_conexion,))
                    resumen["cables_desconectados"].append(c.id_cable)

                elif c.tipo == "conexion_virtual" and c.id_conector_a and c.id_conector_b:
                    codigo = Modelo.siguiente_codigo_temporal()
                    cur = conn.execute(
                        "INSERT INTO cable (codigo, estado) VALUES (?, 'VERIFICADO')",
                        (codigo,))
                    id_cable_nuevo = cur.lastrowid
                    conn.execute(
                        "INSERT INTO conexion (id_cable, id_conector, "
                        "es_conexion_interna) VALUES (?,?,0)",
                        (id_cable_nuevo, c.id_conector_a))
                    conn.execute(
                        "INSERT INTO conexion (id_cable, id_conector, "
                        "es_conexion_interna) VALUES (?,?,0)",
                        (id_cable_nuevo, c.id_conector_b))
                    resumen["cables_creados"].append((id_cable_nuevo, codigo))
                    resumen["conexiones_creadas"].append(
                        (c.id_conector_a, c.id_conector_b))

            if self.id_escenario is not None:
                conn.execute(
                    "UPDATE escenario SET estado='aplicado', "
                    "fecha_ultima_edicion=STRFTIME('%Y-%m-%d %H:%M:%S','now','localtime') "
                    "WHERE id_escenario=?", (self.id_escenario,))

        self.estado = "aplicado"
        self.invalidar_grafo()
        return resumen
