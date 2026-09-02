"""
riesgo_analogico.py — Motor de agregación de "zona caliente" para CableDoc
============================================================================
Entrega 1 de plan_bitacora_incidentes_riesgo_analogico.md: combina
incidentes registrados (bitácora) + conectores/cables marcados como mal
armados, en un score de riesgo por equipo/cable/zona.

A diferencia de graph_impact.py / signal_risk.py (Entrega 2), este módulo
NO construye ni recorre el grafo de señal: es agregación directa por
equipo/cable/zona, sin propagación. Se mantiene así de simple a propósito
para la Entrega 1 — la Entrega 2 sumará el aporte de signal_risk.py al
mismo score (ver RiesgoAnalogicoAnalyzer.calcular_niveles, TODO marcado).

API pública:
    analyzer = RiesgoAnalogicoAnalyzer()
    niveles = analyzer.calcular_niveles()      # {(tipo, id): NivelRiesgo}
    nivel   = analyzer.nivel_de("equipo", "42")

Fórmula de score (Fase B, ver plan_desarrollo_bitacora_incidentes.md):
    Cada incidente dentro de la ventana configurada aporta
    `peso_incidente * factor_decaimiento`, donde factor_decaimiento baja
    linealmente de 1.0 (incidente de hoy) a 0.0 (incidente en el borde de
    la ventana). Un conector o cable marcado es_armado_correcto=0 aporta
    `peso_armado_incorrecto` una sola vez por equipo/cable/zona afectado.
    El score total define el nivel según los cortes configurados.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from modelo import Modelo


NIVEL_BAJO = "BAJO"
NIVEL_MEDIO = "MEDIO"
NIVEL_ALTO = "ALTO"


@dataclass
class ResultadoRiesgoAnalogico:
    tipo: str            # "equipo" | "cable" | "zona"
    id: str
    score: float
    nivel: str
    detalle: list = field(default_factory=list)   # líneas de texto, causa raíz


def _parsear_fecha(fecha_hora: str):
    """Tolerante a 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS' y variantes."""
    if not fecha_hora:
        return None
    txt = fecha_hora.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    # último intento: solo los primeros 10 caracteres (fecha)
    try:
        return datetime.strptime(txt[:10], "%Y-%m-%d")
    except ValueError:
        return None


class RiesgoAnalogicoAnalyzer:
    """Calcula el score/nivel de "zona caliente" por equipo, cable y zona
    sospechosa, a partir de la bitácora de incidentes y las marcas de
    armado incorrecto. Sin estado persistente entre llamadas — cada
    invocación de calcular_niveles() vuelve a leer la base."""

    def __init__(self):
        self._cache: dict[tuple, ResultadoRiesgoAnalogico] = {}

    # ── API pública ──────────────────────────────────────────────────────
    def calcular_niveles(self) -> dict:
        """Recalcula todo y devuelve {(tipo, id_str): ResultadoRiesgoAnalogico}
        solo para las entradas con score > 0 (sin factores de riesgo, no
        aparecen — evita ensuciar el overlay con equipos "neutros")."""
        cfg = Modelo.devolver_config_riesgo_analogico()
        ventana_meses = cfg.get("ventana_meses_incidentes", 12.0)
        peso_incidente = cfg.get("peso_incidente", 1.0)
        peso_armado = cfg.get("peso_armado_incorrecto", 1.5)
        corte_medio = cfg.get("corte_medio", 1.0)
        corte_alto = cfg.get("corte_alto", 2.5)

        ahora = datetime.now()
        ventana_dias = ventana_meses * 30.44  # aproximación suficiente

        acumulado: dict[tuple, dict] = {}   # (tipo,id) -> {"score":..., "detalle":[...]}

        def sumar(tipo, id_, score, linea_detalle):
            clave = (tipo, str(id_))
            entry = acumulado.setdefault(clave, {"score": 0.0, "detalle": []})
            entry["score"] += score
            entry["detalle"].append(linea_detalle)

        # ── Incidentes (equipo directo, cable directo, y vía zona) ─────────
        incidentes = Modelo._query(
            "SELECT id_incidente, fecha_hora, resumen FROM incidente"
        )
        for id_inc, fecha_hora, resumen in incidentes:
            fecha = _parsear_fecha(fecha_hora)
            if fecha is None:
                factor = 1.0   # sin fecha parseable: no penalizar, contar entero
            else:
                antiguedad_dias = (ahora - fecha).days
                if antiguedad_dias < 0 or antiguedad_dias > ventana_dias:
                    if antiguedad_dias > ventana_dias:
                        continue   # fuera de ventana: no cuenta
                    antiguedad_dias = 0
                factor = max(0.0, 1.0 - antiguedad_dias / ventana_dias)

            aporte = peso_incidente * factor
            linea = f"Incidente {fecha_hora} — {resumen}"

            for id_eq, _nom in Modelo.devolver_equipos_de_incidente(id_inc):
                sumar("equipo", id_eq, aporte, linea)
            for id_cb, _cod in Modelo.devolver_cables_de_incidente(id_inc):
                sumar("cable", id_cb, aporte, linea)
            for id_zn, _nom in Modelo.devolver_zonas_de_incidente(id_inc):
                sumar("zona", id_zn, aporte, linea)
                # Un incidente de zona también "calienta" a cada equipo
                # de esa zona, para que el overlay del diagrama (que
                # pinta equipos, no zonas) los pueda marcar.
                for id_eq2, _n2 in Modelo.devolver_equipos_de_zona(id_zn):
                    sumar("equipo", id_eq2, aporte, linea + " (vía zona)")

        # ── Armado incorrecto ───────────────────────────────────────────────
        for id_con, id_eq, nombre_con, detalle in Modelo.devolver_conectores_mal_armados():
            linea = f"Conector «{nombre_con}» mal armado" + (f": {detalle}" if detalle else "")
            sumar("equipo", id_eq, peso_armado, linea)

        for id_cb, codigo, detalle in Modelo.devolver_cables_mal_armados():
            linea = f"Cable «{codigo}» mal armado" + (f": {detalle}" if detalle else "")
            sumar("cable", id_cb, peso_armado, linea)

        # Armado POR EXTREMO (conexion) — descubierto en sesión posterior a
        # esta entrega: "Armado" a nivel cable completo no distingue cuál
        # extremo específico está mal armado (ej. XLR3 bien armado de un
        # lado, TRS mal armado del otro). Mismo peso que el armado a nivel
        # cable, aditivo: si además está marcado el cable entero, se suman
        # ambos factores (mismo criterio que el resto de este método, cada
        # factor encontrado aporta su peso por separado, sin deduplicar).
        for id_cx, id_cb, codigo, id_con, nombre_con, detalle in Modelo.devolver_conexiones_mal_armadas():
            extremo = f" (extremo hacia «{nombre_con}»)" if nombre_con else ""
            linea = (f"Cable «{codigo}» mal armado{extremo}"
                      + (f": {detalle}" if detalle else ""))
            sumar("cable", id_cb, peso_armado, linea)

        # Extensiones de cable mal armadas (plan_desarrollo_extension_
        # cable.md §2 y §3.3): una extensión mal armada es un punto de
        # falla propio, independiente de los dos cables que empalma — NO
        # se limita a heredar el peso de conector/cable/equipo aguas
        # abajo. Se registra en su propio bucket ("extension") para que
        # nivel_de("extension", id) / detalle_de(...) puedan consultarse
        # puntualmente el día que exista un nodo de extensión en el
        # diagrama (Fase 3, pendiente), y ADEMÁS suma el mismo peso a cada
        # uno de los dos cables empalmados, para que el overlay actual
        # (que solo pinta equipo/cable/zona) ya pueda marcarlos como
        # afectados sin esperar a esa Fase 3.
        # Nota de diseño (plan §5, pendiente de confirmar con cliente):
        # por ahora reusa el mismo parámetro configurable peso_armado_
        # incorrecto que ya pesa a conector/cable — no se creó un
        # parámetro separado; si el cliente pide diferenciarlo, agregar
        # una clave nueva (ej. "peso_armado_incorrecto_extension") en
        # config_riesgo_analogico y usarla acá en su lugar.
        for (id_ext, id_cb_a, codigo_a, id_cb_b, codigo_b,
             detalle) in Modelo.devolver_extensiones_mal_armadas():
            linea = (f"Extensión entre «{codigo_a}» y «{codigo_b}» mal armada"
                      + (f": {detalle}" if detalle else ""))
            sumar("extension", id_ext, peso_armado, linea)
            sumar("cable", id_cb_a, peso_armado, linea)
            sumar("cable", id_cb_b, peso_armado, linea)

        # ── Nivel final ──────────────────────────────────────────────────────
        # TODO (Entrega 2): sumar acá la salida de signal_risk.py antes de
        # decidir el nivel, sin perder el detalle de causa raíz ya acumulado.
        resultado = {}
        for (tipo, id_), datos in acumulado.items():
            score = datos["score"]
            if score >= corte_alto:
                nivel = NIVEL_ALTO
            elif score >= corte_medio:
                nivel = NIVEL_MEDIO
            else:
                nivel = NIVEL_BAJO
            resultado[(tipo, id_)] = ResultadoRiesgoAnalogico(
                tipo=tipo, id=id_, score=round(score, 3),
                nivel=nivel, detalle=datos["detalle"],
            )

        self._cache = resultado
        return resultado

    def nivel_de(self, tipo: str, id_) -> "str | None":
        """Consulta puntual sin recalcular todo si ya se llamó a
        calcular_niveles() antes en esta instancia."""
        if not self._cache:
            self.calcular_niveles()
        r = self._cache.get((tipo, str(id_)))
        return r.nivel if r else None

    def detalle_de(self, tipo: str, id_) -> "ResultadoRiesgoAnalogico | None":
        if not self._cache:
            self.calcular_niveles()
        return self._cache.get((tipo, str(id_)))
