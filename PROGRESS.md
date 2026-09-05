# PROGRESS.md — Seguimiento general (fuera del refactor de cabledoc.py)

> Nota: el refactor de `cabledoc.py` (Entregas 1-10) tiene su propio archivo
> de seguimiento, `PROGRESS_REFACTOR_CABLEDOC.md`, y ya está cerrado. Este
> `PROGRESS.md` cubre trabajo de features posteriores a ese cierre, empezando
> por `plan_desarrollo_ubicacion_fisica_planos.md`.

## Current Focus

Implementando `plan_desarrollo_ubicacion_fisica_planos.md` (Planos / Salas /
Racks / Muebles con overlay interactivo). Fase 1 (schema y modelo) ya estaba
mergeada en `main` (PR #12, "Etapa 0 / Fase 1") al empezar esta sesión. Se
entregó la Fase 2 (catálogo simple de planos, sin overlay). Próximo paso:
Fase 3 — selector de polígono sobre imagen en `imagen_conectores_ui.py`.

## Todo List

- [x] Fase 1 — Schema y modelo de datos (`asegurar_tablas_plano()`, CRUD de
      `plano`/`mueble`, `devolver_contenido_plano`,
      `devolver_ubicacion_fisica_de_equipo`) — PR #12, ya en `main`.
- [x] Fase 2 — Catálogo de Planos (sin overlay): `planos_ui.py`
      (`PlanosListado`, `_DialogoPlano`), ítem de menú "🗺 Planos" en
      Infraestructura (`cabledoc.py`). Diff entregado:
      `entrega_fase2_planos.diff`, pendiente de que Fede lo aplique/commitee.
- [ ] Fase 3 — Selector de polígono sobre imagen: extender
      `CoordenadasImagenSeleccion` (`imagen_conectores_ui.py`) con modo
      `solo_poligono`.
- [ ] Fase 4 — Overlay de salas en el plano: `VistaPlanoInteractivo` en
      `planos_ui.py` (modo navegar + editar contorno de sala), selector de
      plano en `_DialogoSala`.
- [ ] Fase 5 — Overlay de racks (puntos): punto de rack editable en
      `VistaPlanoInteractivo`, botón "📍 Ubicar en el plano" en
      `_DialogoRackPorSala`.
- [ ] Fase 6 — Muebles: `MueblesListado`/`_DialogoMueble`, asignación de
      equipos a mueble con filtro `es_modulo_de_frame`.
- [ ] Fase 7 — Equipos sueltos, módulos de frame y herencia de ubicación:
      punto de equipo suelto, checkbox `es_modulo_de_frame` en
      `_DialogoEquipo`, integración completa de
      `devolver_ubicacion_fisica_de_equipo` al visor.
- [ ] Fase 8 — Integración a la ficha de Equipo + limpieza de UI: sacar
      `Imagen`/`Coord X`/`Coord Y` de `_DialogoEquipo`, reemplazar
      "📍 Ver ubicación" por la versión de solo lectura.
- [ ] Fase 9 — Pulido: colores/íconos por tipo de entidad, tooltips,
      zoom-to-fit.

## Latest Blockers/Discoveries

- **PR #12 (Fase 1) no siguió el protocolo de entrega habitual**: solo tocó
  `modelo.py` y `cabledoc.py` (la llamada a `asegurar_tablas_plano()`), sin
  entrada en `changelog.txt`, sin bump de `APP_VERSION` y sin actualizar
  ningún `PROGRESS*.md`. Quedó documentado acá para que el historial no se
  pierda, pero no se retocó `main` para agregarle esos metadatos
  retroactivamente (mismo criterio que la entrada retroactiva de
  `senal_catalogo_ui.py` en `changelog.txt`, Entrega 6 del refactor: se avisa
  del corte, no se reescribe historia).
- **Nombres reales del modelo difieren del boceto del plan**: la tabla se
  llama `equiponoraqueable_por_sala` (no `equipo_no_rack_sala` como en el
  documento), y `plano` referencia una fila de la tabla `imagen` compartida
  vía `id_imagen` en vez de guardar el path como texto plano — confirmado
  contra el código real de `modelo.py` antes de escribir `planos_ui.py`,
  no contra el boceto del `.md`.
- **`schema_db.sql` no se actualizó en la Fase 1** — la migración de tablas
  nuevas/columnas vive enteramente en `Modelo.asegurar_tablas_plano()`
  (patrón `ALTER TABLE ... ADD COLUMN` idempotente), no en el archivo de
  schema versionado. Si en algún momento se decide volcar el schema
  "canónico" a `schema_db.sql`, es un paso aparte, no bloqueante.
- **Smoke test de la Fase 2**: corrido bajo Xvfb contra una copia
  descartable de `database/db.db` (vacía de datos, sin la tabla `plano`
  todavía — se creó recién al llamar `asegurar_tablas_plano()` en el propio
  test). CRUD completo de `PlanosListado`/`_DialogoPlano` verificado
  (alta/edición/eliminación). No se pudo ejercitar el botón "📂 Explorar"
  con un `Gtk.FileChooserDialog` real (modal e interactivo, no simulable
  headless) — cubierto por revisión de código contra `_DialogoImagen`, ya
  validado en la Entrega 8 del refactor. Pendiente para Fede: probar
  "Explorar" a mano con un SVG real.
- **`plano_planta_baja.svg` / `plano_planta_baja.jpg`** (mencionados en el
  plan como referencia real del cliente) no están en este repo/sandbox —
  el smoke test usó un nombre de archivo de fixture (`plano_planta_baja.svg`)
  sin contenido real detrás. No bloqueante para la Fase 2 (solo guarda el
  nombre de archivo), pero relevante para probar overlay real en la Fase 4.
