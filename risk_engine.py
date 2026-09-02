"""
risk_engine.py — Índice de Riesgo de Falla (IRF) para CableDoc
================================================================

Calcula, para cada equipo, qué tan riesgoso es que falle:

    Riesgo = max(Probabilidad, P_MIN) × Impacto / 100

  Probabilidad (P, 0-100): estima qué tan propenso es el equipo a fallar,
  combinando antigüedad, condición de uso e historial de problemas.

  Impacto (I, 0-100): fracción del parque que queda sin señal si este
  equipo falla por completo, reutilizando el motor de grafo de
  graph_impact.py (GraphImpactAnalyzer.simular_falla_equipo).

  Si hay un conjunto de "equipos críticos" cargado a mano (tabla
  equipo_critico, ver Modelo.marcar_equipos_criticos — se arma fácilmente
  seleccionando nodos en el diagrama de conexiones, con rectángulo o
  Shift/Ctrl+clic, y usando el botón "⭐ Marcar críticos"), el Impacto se
  mide SOLO contra ese conjunto: qué fracción de los equipos críticos
  queda sin señal (o es el propio equipo). Esto hace que el riesgo priorice
  lo que realmente importa (ej. la cadena de aire) en vez de tratar por
  igual a un monitor de sala de control y al switcher máster. Si la tabla
  está vacía, se calcula como siempre: fracción de TODO el parque que
  queda sin señal, sin distinguir importancia.

Uso:
    engine = RiskEngine(db_path)
    resultados = engine.calcular_todos()   # {id_equipo(str): dict}
    # resultados["42"] = {
    #     "probabilidad": 63.2, "impacto": 81.0, "riesgo": 51.2,
    #     "nivel": "Alto",
    #     "detalle": {
    #         "s_edad": 40.0, "s_uso": 65.0, "s_historial": 72.1,
    #         "edad_anios": 6.4, "vida_util_anios": 8,
    #         "equipos_impactados": 12, "equipos_totales": 414,
    #         "modo_impacto": "criticos", "criticos_impactados": 3,
    #         "criticos_totales": 5,
    #     },
    # }

Si graphqlite no está disponible (o el equipo no tiene cables), el factor
Impacto cae a un valor neutro configurable en vez de romper el cálculo —
así el resto de la app sigue funcionando aunque el análisis de grafo no
esté disponible en el entorno.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, date

from modelo import Modelo

try:
    from graph_impact import GraphImpactAnalyzer
    _GRAPH_DISPONIBLE = True
except Exception:
    _GRAPH_DISPONIBLE = False


# ── Niveles de riesgo (para semáforo en la UI) ──────────────────────────────
NIVELES = [
    (75, "Crítico", (0.85, 0.10, 0.10)),
    (50, "Alto",     (0.90, 0.55, 0.10)),
    (25, "Medio",    (0.90, 0.80, 0.10)),
    (0,  "Bajo",     (0.15, 0.65, 0.20)),
]


def nivel_de(riesgo: float) -> str:
    for umbral, nombre, _color in NIVELES:
        if riesgo >= umbral:
            return nombre
    return "Bajo"


def color_de(riesgo: float) -> tuple:
    for umbral, _nombre, color in NIVELES:
        if riesgo >= umbral:
            return color
    return NIVELES[-1][2]


def _parse_fecha(txt) -> "date | None":
    if not txt:
        return None
    txt = str(txt).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y"):
        try:
            return datetime.strptime(txt[: len(fmt) if fmt != "%Y" else 4], fmt).date()
        except ValueError:
            continue
    return None


class RiskEngine:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._analyzer = GraphImpactAnalyzer(db_path) if _GRAPH_DISPONIBLE else None

    # ──────────────────────────────────────────────────────────────────────
    # Cálculo principal (batch — todos los equipos de una sola pasada)
    # ──────────────────────────────────────────────────────────────────────

    def calcular_todos(self, persistir: bool = True) -> dict:
        params = Modelo.devolver_parametros_riesgo()
        equipos = Modelo.devolver_equipos_para_riesgo()
        # id_equipo, id_categoria, ... -> agrupar problemas por id_equipo
        problemas_por_equipo: dict = {}
        for id_equipo, gravedad, fecha, afecta_cat, resuelto in Modelo.devolver_problemas_para_riesgo():
            problemas_por_equipo.setdefault(str(id_equipo), []).append(
                {"gravedad": gravedad, "fecha": fecha,
                 "afecta_categoria_equipo": bool(afecta_cat),
                 "resuelto": bool(resuelto)}
            )

        grafo_ok = self._construir_grafo_seguro()
        equipos_totales = (
            self._analyzer.totales()[0] if grafo_ok else max(len(equipos), 1)
        )
        criticos = Modelo.devolver_ids_equipos_criticos()

        resultados = {}
        hoy = date.today()

        for id_equipo, id_tipo, fecha_fab, es_usado, vida_util in equipos:
            eq_id = str(id_equipo)
            problemas = problemas_por_equipo.get(eq_id, [])

            s_edad, edad_anios, vida_util_usada = self._score_edad(
                fecha_fab, vida_util, params, hoy)
            s_uso = 65.0 if es_usado else 0.0
            s_historial = self._score_historial(problemas, params, hoy)

            probabilidad = (
                params["w_edad"] * s_edad
                + params["w_uso"] * s_uso
                + params["w_historial"] * s_historial
            )
            probabilidad = min(100.0, max(0.0, probabilidad))

            if grafo_ok:
                impacto, n_impact, det_criticos = self._score_impacto(
                    eq_id, equipos_totales, criticos)
            else:
                impacto, n_impact, det_criticos = 50.0, None, {}  # neutro si no hay grafo

            p_efectivo = max(probabilidad, params["p_min"])
            riesgo = min(100.0, p_efectivo * impacto / 100.0)
            nivel = nivel_de(riesgo)

            detalle = {
                "s_edad": round(s_edad, 1), "s_uso": round(s_uso, 1),
                "s_historial": round(s_historial, 1),
                "edad_anios": round(edad_anios, 1) if edad_anios is not None else None,
                "vida_util_anios": vida_util_usada,
                "cantidad_problemas": len(problemas),
                "equipos_impactados": n_impact,
                "equipos_totales": equipos_totales,
                "grafo_disponible": grafo_ok,
                **det_criticos,
            }

            resultados[eq_id] = {
                "probabilidad": round(probabilidad, 1),
                "impacto": round(impacto, 1),
                "riesgo": round(riesgo, 1),
                "nivel": nivel,
                "detalle": detalle,
            }

        if persistir:
            for eq_id, r in resultados.items():
                Modelo.guardar_riesgo_equipo(
                    int(eq_id), r["probabilidad"], r["impacto"], r["riesgo"],
                    r["nivel"], json.dumps(r["detalle"], ensure_ascii=False),
                )

        return resultados

    def calcular_uno(self, id_equipo, persistir: bool = True) -> dict:
        """Atajo cuando solo interesa un equipo (ej. al abrir su ficha).
        Internamente calcula igual todo el parque porque el factor Impacto
        depende del grafo completo — pero permite no persistir el resto si
        no hace falta."""
        todos = self.calcular_todos(persistir=persistir)
        return todos.get(str(id_equipo))

    # ──────────────────────────────────────────────────────────────────────
    # Sub-cálculos
    # ──────────────────────────────────────────────────────────────────────

    def _construir_grafo_seguro(self) -> bool:
        if self._analyzer is None:
            return False
        try:
            self._analyzer.construir_grafo()
            return True
        except Exception:
            return False

    @staticmethod
    def _score_edad(fecha_fab, vida_util_tipo, params, hoy) -> tuple:
        vida_util = vida_util_tipo if vida_util_tipo else params["vida_util_default_anios"]
        fecha = _parse_fecha(fecha_fab)
        if fecha is None:
            return params["s_edad_sin_dato"], None, vida_util
        edad_anios = (hoy - fecha).days / 365.25
        if edad_anios < 0:
            edad_anios = 0.0
        score = min(100.0, 100.0 * edad_anios / vida_util) if vida_util else 0.0
        return score, edad_anios, vida_util

    @staticmethod
    def _score_historial(problemas, params, hoy) -> float:
        if not problemas:
            return 0.0
        decaimiento = params["decaimiento_meses"]
        raw = 0.0
        for p in problemas:
            gravedad = p["gravedad"] or 0
            fecha = _parse_fecha(p["fecha"])
            if fecha is None:
                peso_temporal = 1.0  # sin fecha: se asume vigente, no se subestima
            else:
                meses = max(0.0, (hoy - fecha).days / 30.44)
                peso_temporal = math.exp(-meses / decaimiento) if decaimiento else 1.0
            multiplicador_categoria = 1.5 if p["afecta_categoria_equipo"] else 1.0
            multiplicador_resuelto = 0.5 if p["resuelto"] else 1.0
            raw += gravedad * peso_temporal * multiplicador_categoria * multiplicador_resuelto
        k = params["k_saturacion"] or 15.0
        return 100.0 * (1.0 - math.exp(-raw / k))

    def _score_impacto(self, eq_id, equipos_totales, criticos) -> tuple:
        """Impacto (0-100).

        Sin equipos críticos cargados (comportamiento "de siempre"):
        fracción de TODO el parque que queda sin señal si este equipo falla.

        Con equipos críticos cargados (Modelo.marcar_equipos_criticos):
        fracción del CONJUNTO CRÍTICO que queda sin señal — el propio
        equipo cuenta como "afectado" si él mismo es crítico, además de
        cualquier otro crítico que dependa de él. Mucho más preciso que
        contar todo el parque por igual: un equipo con pocos vecinos pero
        que alimenta al switcher máster debe pesar más que uno con muchos
        vecinos triviales (monitores de sala, por ejemplo).

        Devuelve (impacto, equipos_impactados_total, detalle_criticos_dict).
        """
        try:
            r = self._analyzer.simular_falla_equipo(eq_id)
        except Exception:
            return 50.0, None, {}  # neutro ante cualquier error puntual del grafo

        n_impact = len(r.equipos_impactados)

        if criticos:
            criticos_afectados = r.equipos_impactados & criticos
            if eq_id in criticos:
                criticos_afectados = criticos_afectados | {eq_id}
            n_criticos_afectados = len(criticos_afectados)
            impacto = 100.0 * n_criticos_afectados / len(criticos)
            detalle = {
                "modo_impacto": "criticos",
                "criticos_impactados": n_criticos_afectados,
                "criticos_totales": len(criticos),
            }
        else:
            frac_equipos = n_impact / equipos_totales if equipos_totales else 0.0
            impacto = 100.0 * frac_equipos
            detalle = {"modo_impacto": "general"}

        return min(100.0, max(0.0, impacto)), n_impact, detalle
