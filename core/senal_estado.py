"""
senal_estado.py — Estado vivo/caído de señal nombrada
========================================================
plan_estado_senal_y_linaje.md, Función 1.

Puente de lectura entre los motores de simulación de corte
(graph_impact.GraphImpactAnalyzer: simular_desconexion / simular_falla_equipo
/ simular_escenario, los tres devuelven un conjunto `equipos_impactados`) y
el nombre de señal cargado a mano en senal_en_conector.py (senal_propagation
se detiene a propósito en los equipos rol_senal='PROCESADOR', exigiendo esa
carga manual — ver senal_propagation.py).

Deliberadamente NO calcula nada de corte por sí mismo: sólo cruza un
conjunto de ids de equipo ya calculado (por cualquiera de los tres motores)
contra qué conectores de esos equipos tienen hoy una señal con nombre
cargada. Es un cálculo en memoria, no persistente — nada de esto se escribe
en la base; existe solo mientras la simulación que lo pidió sigue activa en
pantalla (ver impacto_ui.py / riesgo_diagrama_ui.py / escenario_ui.py).

Granularidad: por EQUIPO para `equipos_impactados`/`equipos_adicionales` (un
equipo entero cae ahí sólo cuando genuinely perdió TODA su señal — ej. está
aguas abajo de un corte, o falló por completo en simular_falla_equipo/
simular_escenario); por CONECTOR puntual para `conectores_adicionales` (el
caso de un equipo con una regla lógica propia rota: sólo su entrada
culpable y su salida gobernada están realmente afectadas, el resto de sus
conectores puede seguir con señal real — ver
GraphImpactAnalyzer.conectores_regla_caida, bugfix 2026-08-24).
"""

import sqlite3


def senales_caidas_por_equipos(db_path: str, equipos_impactados,
                                equipos_adicionales=None,
                                conectores_adicionales=None) -> dict:
    """
    Dado un iterable de ids de equipo (viene de
    ResultadoImpacto.equipos_impactados / ResultadoImpactoEquipo.../
    ResultadoEscenario.equipos_impactados — cualquiera de los tres, mismo
    shape), devuelve:

        { id_conector(str): {
              "id_senal": str, "nombre_senal": str,
              "id_equipo": str, "origen": "MANUAL"|"PROPAGADA",
          }, ... }

    para cada conector de esos equipos que tiene hoy una señal cargada en
    senal_en_conector (manual o propagada — a los fines de "¿qué nombre
    quedó huérfano?" da igual el origen).

    equipos_adicionales: otros ids de equipo a sumar tal cual (ej. el
    equipo que falló DIRECTAMENTE en simular_falla_equipo/
    simular_escenario, que a propósito no viene incluido en
    equipos_impactados — ver comentario en graph_impact.py). Ahí sí
    corresponde barrer el equipo entero: si falló por completo, todos
    sus conectores perdieron señal real.

    conectores_adicionales: ids de CONECTOR puntuales a sumar sin
    importar el equipo al que pertenezcan (ej.
    ResultadoImpacto.conectores_regla_caida — la entrada culpable y la
    salida gobernada de una regla lógica rota, o los dos extremos del
    cable recién cortado vía GraphImpactAnalyzer.conectores_del_cable).
    A diferencia de equipos_adicionales, este NO arrastra el resto de
    los conectores del equipo — bugfix 2026-08-24: antes se usaba
    equipos_adicionales=causas_regla.keys() acá, y terminaba marcando
    "caídos" conectores del mismo equipo que en realidad seguían con
    señal real (ej. las otras dos entradas de un combinador de 3
    entradas cuando sólo se cortó una).

    Devuelve {} si no hay equipos ni conectores para cruzar, o si la
    tabla senal_en_conector no existe todavía en esta base (instalación
    vieja que nunca corrió Modelo.asegurar_tablas_senal()) — no es un
    error, sólo "no hay nada que cruzar".
    """
    equipos_efectivos = {str(e) for e in (equipos_impactados or ())}
    equipos_efectivos |= {str(e) for e in (equipos_adicionales or ())}
    conectores_efectivos = {
        str(c) for c in (conectores_adicionales or ()) if c is not None}

    if not equipos_efectivos and not conectores_efectivos:
        return {}

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        clausulas = []
        params = []
        if equipos_efectivos:
            placeholders = ",".join("?" * len(equipos_efectivos))
            clausulas.append(f"c.id_equipo IN ({placeholders})")
            params += list(equipos_efectivos)
        if conectores_efectivos:
            placeholders = ",".join("?" * len(conectores_efectivos))
            clausulas.append(f"sec.id_conector IN ({placeholders})")
            params += list(conectores_efectivos)
        where_sql = " OR ".join(clausulas)

        try:
            cur = db.execute(
                f"SELECT sec.id_conector, sec.id_senal, s.nombre, "
                f"       c.id_equipo, sec.origen "
                f"FROM senal_en_conector sec "
                f"JOIN senal s ON s.id_senal = sec.id_senal "
                f"JOIN conector c ON c.id_conector = sec.id_conector "
                f"WHERE {where_sql}",
                tuple(params),
            )
        except sqlite3.OperationalError:
            # senal_en_conector no existe en esta base — nada que cruzar.
            return {}

        resultado = {}
        for row in cur.fetchall():
            resultado[str(row["id_conector"])] = {
                "id_senal":     str(row["id_senal"]),
                "nombre_senal": row["nombre"],
                "id_equipo":    str(row["id_equipo"]),
                "origen":       row["origen"],
            }
        return resultado
    finally:
        db.close()


def nombres_senal_caidos(db_path: str, equipos_impactados,
                          equipos_adicionales=None,
                          conectores_adicionales=None) -> list:
    """Envoltorio de conveniencia: sólo los nombres de señal (distintos,
    ordenados), para los llamadores que quieren una lista de texto en vez
    del dict por conector (ej. el panel de impacto_ui.py, y el diálogo
    liviano de plan_simular_remocion_cadena.md)."""
    caidos = senales_caidas_por_equipos(
        db_path, equipos_impactados, equipos_adicionales, conectores_adicionales)
    nombres = {info["nombre_senal"] for info in caidos.values() if info["nombre_senal"]}
    return sorted(nombres)
