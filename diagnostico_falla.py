"""
diagnostico_falla.py — Motor del asistente de diagnóstico de fallas
=====================================================================
Implementa plan_asistente_diagnostico_fallas.md.

Reutiliza el grafo invertido (REV) que ya construye
senal_visual.VisualizadorSenal — el mismo camino REAL entre una fuente y
un conector dado (matriz ruteada, patchera en bypass, DISTRIBUIDOR de una
sola entrada), probado y en producción. Acá no se resuelve hasta una
imagen: se expone la SECUENCIA de conectores del camino, para poder hacer
bisección sobre ella. Ningún motor de grafo nuevo — sólo se le da un uso
distinto al mismo recorrido.

Dos piezas, deliberadamente separadas:
  MotorDiagnostico.construir_cadena()  — arma la lista ordenada de puntos
      entre el síntoma y la fuente (o hasta donde el recorrido automático
      pueda llegar), clasificando por qué se corta si no llega hasta el
      final (fuente / matriz sin documentar / patchera incompleta /
      bifurcación / sin origen).
  SesionDiagnostico                    — sobre esa lista ya armada, hace
      la bisección real: sugiere el próximo punto de test, aplica
      Sí/No/No sé, permite deshacer, informa cuándo convergió.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from senal_visual import VisualizadorSenal


@dataclass
class PasoCadena:
    id_conector: str
    nombre: str
    id_equipo: str
    nombre_equipo: str
    es_punto_test: bool


@dataclass
class OpcionBifurcacion:
    id_equipo: str
    nombre_equipo: str
    opciones: list = field(default_factory=list)   # [(id_conector, nombre), ...]


@dataclass
class ResultadoCadena:
    pasos: list                          # PasoCadena, pasos[0]=síntoma ... pasos[-1]=extremo lejano
    motivo_corte: str                    # texto humano, siempre presente
    categoria_corte: str                 # 'FUENTE'|'MATRIZ_SIN_RUTEO'|'PATCHERA_INCOMPLETA'|
                                          # 'BIFURCACION'|'SIN_ORIGEN'|'BUCLE'
    bifurcacion: Optional[OpcionBifurcacion] = None


class MotorDiagnostico:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._vis = VisualizadorSenal(db_path)

    # ── Construcción de la cadena ────────────────────────────────────────
    def construir_cadena(self, id_conector_sintoma, ramas_elegidas=None) -> ResultadoCadena:
        """
        ramas_elegidas: dict opcional {id_equipo: id_conector_IN_elegido}
        — cuando el asistente ya le preguntó al usuario, en una vuelta
        anterior, cuál entrada seguir en un equipo con varias entradas
        reales (ver OpcionBifurcacion), se pasa acá para que la cadena
        completa se re-arme siguiendo esa elección en vez de volver a
        cortar en el mismo punto. Se recalcula toda la cadena desde cero
        en cada llamado — es barato, las cadenas reales son de pocas
        decenas de pasos como mucho.
        """
        self._vis._cargar()
        ramas_elegidas = dict(ramas_elegidas or {})
        pasos = []
        visitados = set()
        actual = str(id_conector_sintoma)

        while True:
            if actual in visitados:
                return ResultadoCadena(
                    pasos, "Se detectó un bucle de ruteo — revisar la "
                    "configuración de matriz en ese tramo.", "BUCLE")
            visitados.add(actual)
            pasos.append(self._info_paso(actual))

            origen = self._vis._rev.get(actual)
            if origen:
                actual = origen
                continue

            # Sin origen automático — clasificar el motivo del corte.
            id_equipo = self._vis._equipo_de_conector.get(actual)
            rol = self._vis._rol_por_equipo.get(id_equipo, "DISTRIBUIDOR")

            if rol == "FUENTE":
                return ResultadoCadena(
                    pasos, "Se llegó a una fuente documentada — no hay "
                    "nada más aguas arriba para revisar.", "FUENTE")

            if id_equipo in self._vis.equipos_enrutador_sin_matriz:
                return ResultadoCadena(
                    pasos, "La matriz no tiene ruteo asignado para esta "
                    "salida — no se puede seguir automáticamente.",
                    "MATRIZ_SIN_RUTEO")

            if id_equipo in self._vis.equipos_distribuidor_ambiguo and rol == "PATCHERA":
                return ResultadoCadena(
                    pasos, "Esta patchera no tiene las 4 funciones "
                    "asignadas — no se puede seguir automáticamente "
                    "(ver Modelo.listar_patcheras_sin_funcion_completa).",
                    "PATCHERA_INCOMPLETA")

            # ¿Ya se eligió una rama para este equipo en una vuelta anterior?
            if id_equipo in ramas_elegidas:
                actual = ramas_elegidas[id_equipo]
                continue

            # ¿Bifurcación genuina? (equipo con más de una entrada real,
            # sin ninguna regla automática de cuál corresponde — ver plan,
            # sección 3.2, el caso "video ok, audio no").
            ins_reales = self._entradas_reales(id_equipo)
            if len(ins_reales) > 1:
                bif = OpcionBifurcacion(
                    id_equipo, self._nombre_equipo(id_equipo),
                    [(cid, self._vis._nombre_conector.get(cid, cid)) for cid in ins_reales])
                return ResultadoCadena(
                    pasos, f"El equipo «{bif.nombre_equipo}» tiene "
                    f"{len(bif.opciones)} entradas — hace falta indicar "
                    "cuál corresponde a lo que falta.",
                    "BIFURCACION", bifurcacion=bif)

            return ResultadoCadena(
                pasos, "No hay ningún origen documentado para este "
                "punto.", "SIN_ORIGEN")

    def _entradas_reales(self, id_equipo):
        return sorted(
            cid for cid, eq in self._vis._equipo_de_conector.items()
            if eq == id_equipo and self._vis._tipo_conector.get(cid) == "IN")

    def _nombre_equipo(self, id_equipo):
        r = self._query(
            "SELECT nombre FROM equipo WHERE id_equipo=?", (id_equipo,))
        return r[0][0] if r else id_equipo

    def _info_paso(self, id_conector) -> PasoCadena:
        id_equipo = self._vis._equipo_de_conector.get(id_conector)
        r = self._query(
            "SELECT c.nombre, e.nombre, c.es_punto_test, fp.clave "
            "FROM conector c JOIN equipo e ON e.id_equipo = c.id_equipo "
            "LEFT JOIN funcion_patchera fp ON fp.id_funcion_patchera = c.id_funcion_patchera "
            "WHERE c.id_conector=?", (id_conector,))
        if r:
            nombre, nombre_equipo, es_punto_test, clave = r[0]
        else:
            nombre, nombre_equipo, es_punto_test, clave = id_conector, id_equipo, 0, None
        es_punto_test = bool(es_punto_test)

        # Un BACK_ENTRADA/BACK_SALIDA de patchera en bypass NUNCA aparece
        # como nodo propio si se camina por el jack frontal correspondiente
        # (con nada patcheado, el recorrido pasa derecho por atrás — ver
        # graph_impact.py) — pero en la práctica ES el mismo punto físico
        # de la cadena: insertar un monitor portátil en el jack FRONTAL
        # de esa patchera muestra exactamente lo mismo que hay en su
        # conector trasero correspondiente. Sin este ajuste, los puntos de
        # test poblados automáticamente (Fase 2) nunca aparecerían como
        # candidatos de bisección en el caso más común (patchera en
        # bypass, nada patcheado al frente).
        if not es_punto_test and clave in ("BACK_ENTRADA", "BACK_SALIDA"):
            clave_front = "FRONT_DERIVACION" if clave == "BACK_ENTRADA" else "FRONT_INSERCION"
            r2 = self._query(
                "SELECT c2.es_punto_test FROM conector c2 "
                "JOIN funcion_patchera fp2 ON fp2.id_funcion_patchera = c2.id_funcion_patchera "
                "WHERE c2.id_equipo=? AND fp2.clave=?", (id_equipo, clave_front))
            if r2 and r2[0][0]:
                es_punto_test = True

        return PasoCadena(
            id_conector=str(id_conector), nombre=nombre or str(id_conector),
            id_equipo=str(id_equipo) if id_equipo else "",
            nombre_equipo=nombre_equipo or "", es_punto_test=es_punto_test)

    def _query(self, sql, params=()):
        import sqlite3
        db = sqlite3.connect(self._db_path)
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────────
# Bisección sobre una cadena ya construida — sin GTK, fácil de testear.
# ─────────────────────────────────────────────────────────────────────────
class SesionDiagnostico:
    """
    Envoltorio con estado sobre ResultadoCadena.pasos para hacer la
    bisección real. Convención de índices: pasos[0] es el síntoma (por
    definición, ahí NO hay señal — es lo que se reportó), pasos[-1] es el
    extremo más lejano alcanzado (una fuente documentada, o donde se
    cortó la cadena automática). Se asume que ese extremo lejano SÍ tiene
    señal como hipótesis de partida — igual que hace un técnico en la
    vida real, salvo que la bisección termine acotando justo ahí (en cuyo
    caso el resultado sería "revisar la fuente misma", ver resultado()).

    "Hay señal en pasos[i]"    → el problema está más cerca del extremo
                                  lejano (índices mayores que i).
    "No hay señal en pasos[i]" → el problema está más cerca del síntoma
                                  (índices menores o iguales a i).
    """

    def __init__(self, pasos: list):
        if len(pasos) < 2:
            raise ValueError("una cadena de diagnóstico necesita al menos 2 puntos")
        self.pasos = pasos
        self.lo = 0
        self.hi = len(pasos) - 1
        self.historial = []   # [(indice, 'SI'|'NO'|'NO_SE')]

    def convergido(self) -> bool:
        return self.hi - self.lo <= 1

    def siguiente_punto(self):
        """(indice, PasoCadena) del próximo punto a preguntar, o None si
        ya convergió o no hay ningún punto de test en el segmento
        vigente (ver plan, sección 6.3 — se avisa y se deja elegir a
        mano, no se improvisa)."""
        if self.convergido():
            return None
        medio = (self.lo + self.hi) / 2
        candidatos = [i for i in range(self.lo + 1, self.hi)
                      if self.pasos[i].es_punto_test]
        if not candidatos:
            return None
        elegido = min(candidatos, key=lambda i: abs(i - medio))
        return elegido, self.pasos[elegido]

    def elegir_manual(self, indice: int):
        """Para cuando siguiente_punto() no encontró ningún punto de test
        cómodo — el usuario elige a mano un índice del segmento vigente
        (lo, hi) para preguntarle ahí igual, aunque no sea óptimo."""
        if not (self.lo < indice < self.hi):
            raise ValueError(
                f"índice {indice} fuera del segmento vigente ({self.lo}, {self.hi})")
        return indice, self.pasos[indice]

    def responder(self, indice: int, respuesta: str):
        if respuesta not in ("SI", "NO", "NO_SE"):
            raise ValueError(f"respuesta inválida: {respuesta!r}")
        if respuesta == "SI":
            self.hi = indice
        elif respuesta == "NO":
            self.lo = indice
        # 'NO_SE' no mueve lo/hi — sólo queda en el historial (ver plan,
        # sección 6.2): no gasta la pregunta, se puede reintentar con otro
        # punto del mismo segmento.
        self.historial.append((indice, respuesta))

    def deshacer(self) -> bool:
        """Saca el último paso del historial y recalcula lo/hi desde cero
        con lo que queda — barato, dado que las cadenas son chicas."""
        if not self.historial:
            return False
        self.historial.pop()
        self.lo, self.hi = 0, len(self.pasos) - 1
        for indice, respuesta in self.historial:
            if respuesta == "SI":
                self.hi = indice
            elif respuesta == "NO":
                self.lo = indice
        return True

    def resultado(self):
        """Sólo válido si convergido(). Devuelve (paso_sin_senal,
        paso_con_senal) — los dos extremos confirmados que quedaron
        adyacentes. Si son del mismo equipo (una IN y una OUT del mismo
        aparato), el sospechoso es el equipo (revisar conexión interna /
        alimentación); si son de equipos distintos, el sospechoso es el
        cable que los une."""
        if not self.convergido():
            raise RuntimeError("la sesión todavía no convergió")
        return self.pasos[self.lo], self.pasos[self.hi]
