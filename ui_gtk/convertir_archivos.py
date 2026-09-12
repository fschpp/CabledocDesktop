"""
Fase 3.2 de plan_integracion_cabledoc_v3.md: migración ÚNICA de coordenadas
píxel -> porcentaje contra la base de datos real (ver
Modelo.migrar_coordenadas_a_porcentaje en core/modelo.py para el detalle
de la conversión en sí; este script sólo la orquesta de forma segura).

Uso (desde la raíz del repo):
    python3 ui_gtk/convertir_archivos.py            # backup + dry-run + pide confirmación
    python3 ui_gtk/convertir_archivos.py --si        # ídem pero sin preguntar si el dry-run no tuvo errores
    python3 ui_gtk/convertir_archivos.py --forzar    # re-migra aunque _migracion_porcentaje_imagen diga que ya se corrió

Flujo (§7 del plan — este es el paso de mayor riesgo de toda la
integración: reescribe en el lugar coordenada_x/y_en_imagen y
rectangulo_*, sin columna vieja para volver atrás):

    1. Backup de data/database/db.db a data/database/db.db.bak-YYYYmmddHHMMSS
       ANTES de tocar nada. Si el backup falla, se aborta sin migrar.
    2. Dry-run (no escribe nada): calcula todo y muestra el resumen.
    3. Si el dry-run encuentra errores (filas sin imagen asociada, imagen
       que no se encuentra en IMG_DIR, etc.) el script se detiene ahí — no
       tiene sentido migrar una parte y dejar el resto a mano sin que
       quede claro qué faltó. Revisar esas filas y volver a correr.
    4. Si el dry-run no tuvo errores, pide confirmación explícita (salvo
       --si) mostrando cuántas filas se van a modificar y dónde quedó el
       backup.
    5. Aplica de verdad y muestra el resumen final.
    6. Verifica que la base quedó marcada como migrada
       (_migracion_porcentaje_imagen) antes de terminar.
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

# Mismo bootstrap de sys.path que ui_gtk/cabledoc.py (Fase 2): agregar la
# raíz del repo (padre de ui_gtk/) para que `from core.X import Y` resuelva
# sin importar desde dónde se lance este script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.modelo import Modelo, DB_PATH  # noqa: E402  (después del bootstrap)


def _progreso(tabla, id_fila, ok, detalle):
    if not ok:
        print(f"  [ERROR] {tabla} #{id_fila}: {detalle}")


def _ya_migrada():
    """Chequea el flag _migracion_porcentaje_imagen directamente, sin pasar
    por migrar_coordenadas_a_porcentaje(_dry_run=True): ese dry-run NO
    consulta el flag (sólo lo hace la corrida real) y en una base ya
    migrada recalcularía porcentajes sobre valores que ya son porcentaje,
    mostrando un resumen sin sentido ('Migrarían: N') aunque no vaya a
    tocar nada de verdad. Este chequeo evita ese mensaje confuso."""
    with Modelo._conn_ctx() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _migracion_porcentaje_imagen "
            "(clave TEXT PRIMARY KEY, fecha TEXT)")
        return conn.execute(
            "SELECT 1 FROM _migracion_porcentaje_imagen "
            "WHERE clave='coordenadas_a_porcentaje'").fetchone() is not None


def _hacer_backup():
    if not os.path.isfile(DB_PATH):
        print(f"No se encontró la base en {DB_PATH!r} — nada para migrar.")
        sys.exit(1)
    marca = datetime.now().strftime("%Y%m%d%H%M%S")
    destino = f"{DB_PATH}.bak-{marca}"
    shutil.copy2(DB_PATH, destino)
    print(f"Backup creado: {destino}")
    return destino


def main():
    parser = argparse.ArgumentParser(
        description="Migración única de coordenadas píxel -> porcentaje "
                     "(Fase 3.2 de plan_integracion_cabledoc_v3.md).")
    parser.add_argument(
        "--si", action="store_true",
        help="Aplicar sin pedir confirmación interactiva después del "
             "dry-run (igual se hace backup y dry-run primero).")
    parser.add_argument(
        "--forzar", action="store_true",
        help="Volver a migrar aunque la base ya esté marcada como "
             "migrada. Sólo para depuración.")
    args = parser.parse_args()

    print(f"Base de datos: {DB_PATH}")

    if _ya_migrada() and not args.forzar:
        print("La base ya está marcada como migrada "
              "(_migracion_porcentaje_imagen). Nada para hacer — no se "
              "hizo backup porque no hay ninguna escritura pendiente. "
              "Usá --forzar si de verdad querés repetirla.")
        return

    backup_path = _hacer_backup()

    print("\n=== Paso 1/2: dry-run (no escribe nada) ===")
    resumen_dry = Modelo.migrar_coordenadas_a_porcentaje(
        reportar_progreso=_progreso, _dry_run=True, forzar=args.forzar)

    print(f"Migrarían: {resumen_dry['migradas']}  "
          f"Sin cambios: {resumen_dry['sin_cambios']}  "
          f"Errores: {len(resumen_dry['errores'])}")

    if resumen_dry["errores"]:
        print("\nHay errores en el dry-run — NO se va a aplicar nada. "
              "Revisá estas filas a mano antes de reintentar:")
        for tabla, id_fila, mensaje in resumen_dry["errores"]:
            print(f"  - {tabla} #{id_fila}: {mensaje}")
        print(f"\nBackup ya hecho en {backup_path} por las dudas, pero la "
              "base real no fue tocada.")
        sys.exit(2)

    if not args.si:
        respuesta = input(
            f"\n¿Aplicar la migración real ahora? Se van a modificar "
            f"{resumen_dry['migradas']} filas. Backup en {backup_path}. "
            f"[s/N]: ").strip().lower()
        if respuesta != "s":
            print("Cancelado por el usuario. La base real no fue tocada.")
            return

    print("\n=== Paso 2/2: aplicando de verdad ===")
    resumen = Modelo.migrar_coordenadas_a_porcentaje(
        reportar_progreso=_progreso, _dry_run=False, forzar=args.forzar)
    print(f"Migradas: {resumen['migradas']}  "
          f"Sin cambios: {resumen['sin_cambios']}  "
          f"Errores: {len(resumen['errores'])}")

    verificacion = Modelo.migrar_coordenadas_a_porcentaje()
    if verificacion.get("ya_migrada"):
        print("\nVerificado: la base quedó marcada como migrada "
              "(_migracion_porcentaje_imagen).")
    else:
        print("\nATENCIÓN: la base NO quedó marcada como migrada después "
              "de aplicar. Revisar a mano antes de dar esto por cerrado.")

    print(f"\nBackup previo a la migración: {backup_path}")


if __name__ == "__main__":
    main()
