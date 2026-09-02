from modelo import Modelo

def progreso(tabla, id_fila, ok, detalle):
    if not ok:
        print(f"  [ERROR] {tabla} #{id_fila}: {detalle}")

resumen = Modelo.migrar_coordenadas_a_porcentaje(reportar_progreso=progreso)
print("Migradas:", resumen["migradas"])
print("Errores:", len(resumen["errores"]))
