# -*- coding: utf-8 -*-
"""
signal_risk.py — Análisis de riesgo de señal en la cadena (calidad
eléctrica: ¿la señal llega bien?), distinto del impacto lógico que ya
calcula graph_impact.py (¿qué se desconecta?). Ver plans/
plan_riesgo_senal_audio.md.

Implementa los 3 ejes del plan, en su versión v1 (orden de trabajo,
sección 6, punto 3 — la de menor esfuerzo y que ya aporta valor sin
esperar a v2):

  1. Atenuación en tramos analógicos largos — v1: flag POR CABLE
     individual (longitud vs. umbral de su tipo), SIN acumulación de
     longitud a través de toda la cadena. La acumulación real por
     cadena (recorriendo el grafo, cortando en el primer equipo que
     regenera a digital) es v2 y queda para una entrega futura, una
     vez que haya datos reales cargados para medir si vale la pena.
  2. Cuello de botella de ancho de banda — v1: comparación LOCAL contra
     los cables vecinos (los que comparten un equipo con éste), no
     contra un requerimiento explícito de la fuente (eso es v2,
     requiere equipo.senal_requerida_mhz poblado).
  3. Mismatch de formato de audio analógico (balance/canal) entre los
     dos extremos de un mismo cable, más un chequeo eléctrico de
     cantidad de conductores (plug de menos conductores que el jack —
     riesgo real de cortocircuito, no sólo de calidad). Este eje no
     tiene división v1/v2 en el plan: se implementa completo.

Desviación de arquitectura respecto del texto original del plan
(acordada con el usuario antes de implementar): el plan proponía los
defaults de n_conductores/modo_balance_default/modo_canal_default en
tipo_ficha con override en conector, pero `conector` (el jack de un
equipo real) no tenía FK a `tipo_ficha` — sólo a `tipo_conector`, que
es un catálogo distinto (nombre/dirección/es_referencia_generada, no
formato eléctrico). Se agregó `conector.id_tipo_ficha` (nullable) para
que un jack real pueda declarar qué ficha es eléctricamente (XLR3/TRS/
TS/etc.) y de ahí sale el default; el override por conector puntual
(`conector.modo_balance` / `conector.modo_canal`) sigue existiendo tal
cual lo pedía el plan.

Los tres ejes se devuelven SEPARADOS, nunca fusionados en un score
único — mismo criterio del plan: cada uno se arregla distinto y
fusionarlos perdería la causa raíz.

Uso típico:
    analyzer = SignalRiskAnalyzer(DB_PATH)
    resumen = analyzer.resumen_por_cable()   # {id_cable: [(eje, detalle), ...]}
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


# ─── Resultados por eje (dataclasses, ver sección 5.1 del plan) ────────────

@dataclass
class RiesgoAtenuacion:
    id_cable: str
    riesgo: bool
    naturaleza_senal: Optional[str]
    longitud_m: Optional[float]
    umbral_m: Optional[float]
    modo_balance: Optional[str]   # con qué umbral se comparó (balanceado/desbalanceado)
    detalle: str


@dataclass
class RiesgoAnchoBanda:
    id_cable: str
    riesgo: bool
    ancho_banda_mhz: Optional[float]
    ancho_banda_referencia_mhz: Optional[float]  # mejor vecino, para contexto
    id_cable_vecino_referencia: Optional[str]
    detalle: str


@dataclass
class RiesgoFormato:
    id_cable: str
    riesgo: bool
    subtipo: Optional[str]   # 'ELECTRICO' | 'BALANCE' | 'CANAL' | None
    detalle: str


class SignalRiskAnalyzer:
    """Análogo a GraphImpactAnalyzer pero para riesgo de calidad de señal
    en vez de impacto lógico. v1 trabaja mayormente con consultas SQL
    directas (los tres ejes v1 no requieren recorrido de grafo — ver
    docstring del módulo); graph_analyzer queda reservado para v2
    (acumulación de atenuación por cadena, comparación de ancho de banda
    contra requerimiento propagado desde la fuente).
    """

    # Roles de equipo que son puntos de conversión legítimos (sección 4.4
    # del plan) — el analizador no marca mismatch de formato si cualquiera
    # de los dos extremos de un cable cuelga de uno de estos equipos.
    ROLES_CONVERSION = ("CONVERSOR_BALANCE", "SUMADOR_CANAL")

    # Un cable local se considera "cuello de botella" si su ancho de banda
    # efectivo es menor a esta fracción del mejor vecino que comparte
    # equipo con él (v1 — sin requerimiento explícito de la fuente).
    RATIO_CUELLO_DE_BOTELLA = 0.5

    def __init__(self, db_path: str, graph_analyzer=None):
        self._db_path = db_path
        self._graph = graph_analyzer  # reservado para v2, no usado en v1

    # ── infraestructura de conexión ─────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        return db

    # ── helpers de lectura compartidos entre los 3 ejes ─────────────────

    @staticmethod
    def _a_metros(valor, unidad, factores: dict) -> Optional[float]:
        if valor is None:
            return None
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return None
        factor = factores.get((unidad or "m").strip().lower())
        if factor is None:
            # Unidad no cargada en unidad_longitud_factor: se asume ya en
            # metros antes que descartar el dato silenciosamente.
            factor = 1.0
        return valor * factor

    def _factores_longitud(self, cur) -> dict:
        cur.execute("SELECT unidad, factor_a_metros FROM unidad_longitud_factor")
        return {r["unidad"].lower(): r["factor_a_metros"] for r in cur.fetchall()}

    def _formato_por_conector(self, cur) -> dict:
        """id_conector -> {modo_balance, modo_canal, n_conductores}
        resueltos vía COALESCE(override en conector, default de su
        tipo_ficha eléctrica)."""
        cur.execute("""
            SELECT co.id_conector,
                   COALESCE(co.modo_balance, tf.modo_balance_default) AS modo_balance,
                   COALESCE(co.modo_canal,   tf.modo_canal_default)   AS modo_canal,
                   tf.n_conductores AS n_conductores
            FROM conector co
            LEFT JOIN tipo_ficha tf ON tf.id_tipo_ficha = co.id_tipo_ficha
        """)
        return {
            str(r["id_conector"]): {
                "modo_balance": r["modo_balance"],
                "modo_canal": r["modo_canal"],
                "n_conductores": r["n_conductores"],
            }
            for r in cur.fetchall()
        }

    def _extremos_cable(self, cur) -> dict:
        """id_cable -> [(id_conector, id_equipo_o_None, id_conexion), ...]
        — se excluye el conector centinela id_conector=0 (extremo suelto/
        sin equipo, mismo criterio que el resto de la app). id_conexion
        se incluye para poder resolver la ficha PROPIA del cable en ese
        punto exacto (conexion.id_tipo_ficha, distinta de la que declara
        el jack del equipo — ver _ficha_propia_por_conexion)."""
        cur.execute("""
            SELECT cx.id_conexion, cx.id_cable, cx.id_conector, co.id_equipo
            FROM conexion cx
            JOIN conector co ON co.id_conector = cx.id_conector
            WHERE cx.id_conector != 0
        """)
        out: dict = {}
        for r in cur.fetchall():
            out.setdefault(str(r["id_cable"]), []).append((
                str(r["id_conector"]),
                str(r["id_equipo"]) if r["id_equipo"] is not None else None,
                str(r["id_conexion"]),
            ))
        return out

    def _ficha_propia_por_conexion(self, cur) -> dict:
        """id_conexion -> n_conductores de la ficha PROPIA del cable en
        ese punto exacto (conexion.id_tipo_ficha), cuando está cargada.
        Sin esto, el chequeo ELECTRICO cae a comparar jack contra jack
        (ver calcular_mismatches_formato) — dato correcto pero más pobre,
        porque no sabe qué plug tiene realmente ESTE cable puntual."""
        cur.execute("""
            SELECT cx.id_conexion, tf.n_conductores
            FROM conexion cx
            JOIN tipo_ficha tf ON tf.id_tipo_ficha = cx.id_tipo_ficha
        """)
        return {str(r["id_conexion"]): r["n_conductores"] for r in cur.fetchall()}

    def _equipos_conversores(self, cur) -> set:
        cur.execute("""
            SELECT e.id_equipo FROM equipo e
            JOIN tipo_equipo te ON te.id_tipo_equipo = e.id_tipo_equipo
            WHERE te.rol_senal IN ({})
        """.format(",".join("?" * len(self.ROLES_CONVERSION))),
            self.ROLES_CONVERSION)
        return {str(r["id_equipo"]) for r in cur.fetchall()}

    def _modo_balance_por_cable(self, cur, formato: dict, extremos: dict) -> dict:
        """Heurística conservadora para elegir qué umbral de longitud usar
        en el riesgo de atenuación: si CUALQUIERA de los dos extremos
        resuelve a DESBALANCEADO, el cable se trata como desbalanceado
        (umbral más estricto) — más susceptible a ruido, sección 4.3.2."""
        out = {}
        for cid, puntas in extremos.items():
            modos = [formato.get(c, {}).get("modo_balance") for c, _eq, _cx in puntas]
            modos = [m for m in modos if m and m != "NA"]
            if "DESBALANCEADO" in modos:
                out[cid] = "DESBALANCEADO"
            elif modos:
                out[cid] = "BALANCEADO"
            else:
                out[cid] = None
        return out

    @staticmethod
    def _cables_a_evaluar(cur):
        """Cables reales, excluyendo los de conexión interna (jumpers
        internos de patchera, no representan un tramo de instalación)."""
        cur.execute(
            "SELECT id_cable FROM cable "
            "WHERE es_cable_conexion_interna = 0 OR es_cable_conexion_interna IS NULL"
        )
        return [str(r["id_cable"]) for r in cur.fetchall()]

    # ── Riesgo #1 — atenuación en tramos analógicos largos (v1) ─────────

    def calcular_riesgo_atenuacion(self) -> dict:
        """dict id_cable -> RiesgoAtenuacion. v1: flag simple por cable,
        sin acumulación de cadena (ver docstring del módulo)."""
        resultados = {}
        db = self._conn()
        try:
            cur = db.cursor()
            factores = self._factores_longitud(cur)
            formato = self._formato_por_conector(cur)
            extremos = self._extremos_cable(cur)
            modo_balance_por_cable = self._modo_balance_por_cable(cur, formato, extremos)

            cur.execute("""
                SELECT c.id_cable, c.longitud, c.unidad_longitud,
                       c.metraje_impreso_primer_extremo,
                       c.metraje_impreso_segundo_extremo,
                       c.unidad_metraje_impreso,
                       tc.naturaleza_senal,
                       tc.longitud_maxima_recomendada_balanceado_m,
                       tc.longitud_maxima_recomendada_desbalanceado_m
                FROM cable c
                LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = c.id_tipo_cable
                WHERE c.es_cable_conexion_interna = 0 OR c.es_cable_conexion_interna IS NULL
            """)
            for r in cur.fetchall():
                cid = str(r["id_cable"])
                naturaleza = r["naturaleza_senal"]

                if naturaleza != "ANALOGICA":
                    resultados[cid] = RiesgoAtenuacion(
                        cid, False, naturaleza, None, None, None,
                        "No aplica: el tipo de cable no está clasificado "
                        "como ANALOGICA (o no tiene naturaleza_senal cargada).")
                    continue

                longitud_m = self._a_metros(r["longitud"], r["unidad_longitud"], factores)
                if longitud_m is None:
                    m1 = self._a_metros(r["metraje_impreso_primer_extremo"],
                                         r["unidad_metraje_impreso"], factores)
                    m2 = self._a_metros(r["metraje_impreso_segundo_extremo"],
                                         r["unidad_metraje_impreso"], factores)
                    candidatos = [m for m in (m1, m2) if m is not None]
                    longitud_m = max(candidatos) if candidatos else None

                modo_balance = modo_balance_por_cable.get(cid)
                if modo_balance == "DESBALANCEADO":
                    umbral = r["longitud_maxima_recomendada_desbalanceado_m"]
                else:
                    # Balanceado o desconocido: se usa el umbral balanceado
                    # (más permisivo) — no se penaliza por falta de datos.
                    umbral = r["longitud_maxima_recomendada_balanceado_m"]

                if longitud_m is None or umbral is None:
                    resultados[cid] = RiesgoAtenuacion(
                        cid, False, naturaleza, longitud_m, umbral, modo_balance,
                        "Sin datos suficientes (longitud del cable o "
                        "longitud_maxima_recomendada de su tipo sin cargar).")
                    continue

                riesgo = longitud_m > umbral
                resultados[cid] = RiesgoAtenuacion(
                    cid, riesgo, naturaleza, longitud_m, umbral, modo_balance,
                    f"{longitud_m:.1f} m {'supera' if riesgo else 'dentro de'} "
                    f"el umbral recomendado de {umbral:.1f} m "
                    f"({modo_balance or 'balance desconocido'}).")
        finally:
            db.close()
        return resultados

    # ── Riesgo #2 — cuello de botella de ancho de banda (v1, local) ─────

    def calcular_cuellos_de_botella(self) -> dict:
        """dict id_cable -> RiesgoAnchoBanda. v1: compara cada cable
        contra el MEJOR de sus cables vecinos (los que comparten un
        equipo con él); si el propio es marcadamente inferior, se marca
        a SÍ MISMO como probable cuello de botella local — no requiere
        saber qué exige la señal (eso es v2)."""
        resultados = {}
        db = self._conn()
        try:
            cur = db.cursor()
            cur.execute("""
                SELECT c.id_cable,
                       COALESCE(c.ancho_banda_mhz_override, tc.ancho_banda_mhz) AS ancho_efectivo
                FROM cable c
                LEFT JOIN tipo_cable tc ON tc.id_tipo_cable = c.id_tipo_cable
                WHERE c.es_cable_conexion_interna = 0 OR c.es_cable_conexion_interna IS NULL
            """)
            ancho_por_cable = {str(r["id_cable"]): r["ancho_efectivo"] for r in cur.fetchall()}

            extremos = self._extremos_cable(cur)
            cables_por_equipo: dict = {}
            for cid, puntas in extremos.items():
                for _c, eq, _cx in puntas:
                    if eq is not None:
                        cables_por_equipo.setdefault(eq, set()).add(cid)

            for cid, ancho in ancho_por_cable.items():
                if ancho is None:
                    resultados[cid] = RiesgoAnchoBanda(
                        cid, False, None, None, None,
                        "Sin dato de ancho de banda (ni override del cable "
                        "ni default de su tipo_cable).")
                    continue

                vecinos = set()
                for _c, eq, _cx in extremos.get(cid, ()):
                    if eq is not None:
                        vecinos |= cables_por_equipo.get(eq, set())
                vecinos.discard(cid)

                mejor_vecino_id, mejor_vecino_ancho = None, None
                for vid in vecinos:
                    av = ancho_por_cable.get(vid)
                    if av is None:
                        continue
                    if mejor_vecino_ancho is None or av > mejor_vecino_ancho:
                        mejor_vecino_ancho, mejor_vecino_id = av, vid

                if mejor_vecino_ancho is None:
                    resultados[cid] = RiesgoAnchoBanda(
                        cid, False, ancho, None, None,
                        "Sin cables vecinos con ancho de banda cargado "
                        "para comparar.")
                    continue

                riesgo = ancho < mejor_vecino_ancho * self.RATIO_CUELLO_DE_BOTELLA
                detalle = (
                    f"{ancho:.0f} MHz vs. mejor vecino ({mejor_vecino_ancho:.0f} MHz, "
                    f"cable {mejor_vecino_id}) — "
                    + ("muy por debajo, probablemente no pertenece a esta cadena."
                       if riesgo else "dentro de rango razonable.")
                )
                resultados[cid] = RiesgoAnchoBanda(
                    cid, riesgo, ancho, mejor_vecino_ancho, mejor_vecino_id, detalle)
        finally:
            db.close()
        return resultados

    # ── Riesgo #3 — mismatch de formato de audio analógico ──────────────

    def calcular_mismatches_formato(self) -> dict:
        """dict id_cable -> RiesgoFormato. Compara los dos extremos de
        CADA cable (no requiere recorrer cadena): eléctrico (conductores)
        primero por ser el más grave, luego balance, luego canal.

        El chequeo ELECTRICO usa, cuando está cargada, la ficha PROPIA del
        cable en cada punta (conexion.id_tipo_ficha) contra la ficha que
        declara el jack del equipo (conector.id_tipo_ficha) — es el
        chequeo correcto (¿este plug puntual entra bien en este jack?).
        Si no está cargada, cae a comparar los dos jacks entre sí (más
        pobre: no sabe qué trae realmente el cable, pero sigue detectando
        una incompatibilidad de diseño entre ambos extremos)."""
        resultados = {}
        db = self._conn()
        try:
            cur = db.cursor()
            formato = self._formato_por_conector(cur)
            extremos = self._extremos_cable(cur)
            conversores = self._equipos_conversores(cur)
            ficha_propia = self._ficha_propia_por_conexion(cur)

            for cid in self._cables_a_evaluar(cur):
                puntas = extremos.get(cid, [])
                if len(puntas) != 2:
                    resultados[cid] = RiesgoFormato(
                        cid, False, None,
                        "No aplica: el cable no tiene ambos extremos "
                        "conectados a un conector real.")
                    continue

                (c1, eq1, cx1), (c2, eq2, cx2) = puntas
                if (eq1 and eq1 in conversores) or (eq2 and eq2 in conversores):
                    resultados[cid] = RiesgoFormato(
                        cid, False, None,
                        "No aplica: uno de los extremos cuelga de un "
                        "equipo conversor legítimo (CONVERSOR_BALANCE/"
                        "SUMADOR_CANAL).")
                    continue

                f1, f2 = formato.get(c1, {}), formato.get(c2, {})
                mb1, mb2 = f1.get("modo_balance"), f2.get("modo_balance")
                mc1, mc2 = f1.get("modo_canal"), f2.get("modo_canal")

                # Eléctrico: preferir la ficha PROPIA del cable en cada
                # punta (lo que realmente está enchufado) contra el jack;
                # si no está cargada, fallback a jack-contra-jack.
                nc_cable_1 = ficha_propia.get(cx1)
                nc_cable_2 = ficha_propia.get(cx2)
                nc_jack_1, nc_jack_2 = f1.get("n_conductores"), f2.get("n_conductores")

                riesgo_electrico = None  # (nc_a, nc_b, detalle) si corresponde
                if nc_cable_1 is not None and nc_jack_1 is not None and nc_cable_1 != nc_jack_1:
                    riesgo_electrico = (
                        f"El plug del cable en este extremo tiene {nc_cable_1} "
                        f"conductores pero el jack del equipo espera {nc_jack_1} "
                        f"— riesgo de cortocircuito (ring a masa) si el plug es "
                        f"el de menos conductores.")
                elif nc_cable_2 is not None and nc_jack_2 is not None and nc_cable_2 != nc_jack_2:
                    riesgo_electrico = (
                        f"El plug del cable en el otro extremo tiene {nc_cable_2} "
                        f"conductores pero el jack del equipo espera {nc_jack_2} "
                        f"— riesgo de cortocircuito (ring a masa) si el plug es "
                        f"el de menos conductores.")
                elif (nc_cable_1 is None and nc_cable_2 is None
                      and nc_jack_1 is not None and nc_jack_2 is not None
                      and nc_jack_1 != nc_jack_2):
                    # Fallback: sin ficha propia cargada en ninguna punta,
                    # se compara jack contra jack (chequeo más pobre).
                    riesgo_electrico = (
                        f"Sin ficha propia del cable cargada en ninguna punta "
                        f"(dato más preciso disponible en Conexiones → "
                        f"ficha del cable en esta punta) — comparando sólo "
                        f"los jacks de ambos equipos: cantidad de conductores "
                        f"distinta ({nc_jack_1} vs {nc_jack_2}).")

                if riesgo_electrico:
                    resultados[cid] = RiesgoFormato(cid, True, "ELECTRICO", riesgo_electrico)
                    continue

                if mb1 and mb2 and mb1 != "NA" and mb2 != "NA" and mb1 != mb2:
                    resultados[cid] = RiesgoFormato(
                        cid, True, "BALANCE",
                        f"Balance distinto en cada extremo ({mb1} vs {mb2}) "
                        f"sin conversor de por medio — pérdida de nivel y "
                        f"de rechazo de modo común (más ruido/hum).")
                    continue

                if mc1 and mc2 and mc1 != "NA" and mc2 != "NA" and mc1 != mc2:
                    resultados[cid] = RiesgoFormato(
                        cid, True, "CANAL",
                        f"Canal distinto en cada extremo ({mc1} vs {mc2}) — "
                        f"pérdida de un canal, o riesgo de cortocircuito si "
                        f"es un plug mono en jack TRS.")
                    continue

                resultados[cid] = RiesgoFormato(
                    cid, False, None,
                    "Sin mismatch detectado (o datos de formato "
                    "insuficientes en alguno de los extremos).")
        finally:
            db.close()
        return resultados

    # ── combinación de los 3 ejes (sin fusionar en un score único) ──────

    def calcular_todo(self) -> dict:
        return {
            "atenuacion": self.calcular_riesgo_atenuacion(),
            "ancho_banda": self.calcular_cuellos_de_botella(),
            "formato": self.calcular_mismatches_formato(),
        }

    def resumen_por_cable(self) -> dict:
        """dict id_cable -> [(eje, detalle), ...] SOLO para cables con al
        menos un riesgo activo — pensado para el overlay del diagrama y
        el panel de pendientes (Modelo.devolver_pendientes_riesgo_senal)."""
        todo = self.calcular_todo()
        ids = set(todo["atenuacion"]) | set(todo["ancho_banda"]) | set(todo["formato"])
        resumen = {}
        for cid in ids:
            activos = []
            a = todo["atenuacion"].get(cid)
            if a and a.riesgo:
                activos.append(("ATENUACION", a.detalle))
            b = todo["ancho_banda"].get(cid)
            if b and b.riesgo:
                activos.append(("ANCHO_BANDA", b.detalle))
            f = todo["formato"].get(cid)
            if f and f.riesgo:
                activos.append((f.subtipo or "FORMATO", f.detalle))
            if activos:
                resumen[cid] = activos
        return resumen
