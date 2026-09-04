# PROGRESS_REFACTOR_CABLEDOC.md — Refactor de `cabledoc.py`

Seguimiento específico de `plan_refactor_cabledoc.md`. Documento separado de
`PROGRESS.md` (desarrollo funcional general) y de `PROGRESS_REFACTOR.md`
(que ya cerró el refactor de `pantallas_avanzadas.py`, 11.032 → 145 líneas),
para no mezclar tres historiales con ritmos distintos.

---

## Current Focus

**Entrega 8 completada en esta sesión** (`catalogos_basicos_ui.py`) — ver
sección propia abajo. Acotación de Fede incorporada: el plan (§4) dejaba
sin destino asignado 4 bloques (`ConexionesDeEquipoVentana`,
`DiagramasGuardadosListado`, `GeneradorDiagrama`, `EquipoInfoExtra` — este
último ni siquiera existía cuando se escribió el plan), y como la Entrega
9 es la última antes del cierre de la Entrega 10, se sumaron a
`catalogos_basicos_ui.py` (único punto restante con perfil "catch-all")
en vez de dejarlos varados — desviación documentada en el docstring del
módulo nuevo y en `changelog.txt`.

**Corrección de estado (2026-09-04):** al ponerme al día con los adjuntos
de esta sesión, encontré que este documento y `changelog.txt` habían
quedado desactualizados respecto del checkout real de Papi: la **Entrega 6
(`senal_catalogo_ui.py`) ya estaba aplicada en el código** (cabledoc.py ya
la reexportaba, 4.986 → 4.150 líneas) pero nunca se registró su entrada de
changelog/PROGRESS — probablemente un corte de sesión. Se agregó la
entrada retroactiva en `changelog.txt` y se marca acá como hecha. A partir
de ahí se completó la **Entrega 7** (`racks_salas_ui.py` +
`frames_slots_ui.py`) en esta sesión — ver sección propia abajo.

Entrega 5 completada: extraído `catalogo_equipos_ui.py` (792 líneas:
`CatalogoEquiposListado`, `_DialogoConflictosImportacion`,
`_DialogoCatalogoEquipo`, `_ConectoresCatalogoListado`,
`_DialogoConectorCatalogo`, `_DialogoInstanciarCatalogo`,
`_DialogoDuplicarMolde`) + `catalogo_equipos_alta_rapida_ui.py` (549 líneas:
`_DialogoAltaRapidaCatalogo`), bloque contiguo "Catálogo de equipos
(moldes)" en el original (líneas 1902-3106, 1.205 líneas) — split en 2
archivos por tamaño, mismo criterio que la Entrega 3. `_DialogoDuplicarMolde`
y `_DialogoAltaRapidaCatalogo` eran justo los dos nombres que la Entrega 3
había dejado pendientes en `cabledoc.py` por pertenecer a este dominio.
`cabledoc.py` reexporta los 8 nombres movidos. Referencias cruzadas a
`MarcasListado`, `TiposEquipoListado`, `TiposConectorListado`,
`ImagenesListado`, `_DialogoRenombrarConectoresCatalogo`,
`_escribir_json_comprimido`, `_leer_json_generico`, `_sel_imagen_desde_abm`
(siguen en `cabledoc.py`) y `_DialogoDireccionConector` (vive en
`equipos_ui.py` desde la Entrega 3) resueltas con import diferido, mismo
patrón que las entregas anteriores; `abrir_coords_imagen`,
`abrir_reglas_logicas_molde` y `abrir_editor_masivo_conectores_catalogo` se
importan a nivel de módulo desde `pantallas_avanzadas`. Import diferido
cruzado entre los dos módulos nuevos: `catalogo_equipos_ui.py` importa
`_DialogoAltaRapidaCatalogo` desde `catalogo_equipos_alta_rapida_ui.py`
dentro de `_alta_rapida()`, y viceversa `_DialogoDuplicarMolde` dentro de
`_duplicar_con_patron()` — mismo patrón usado entre `equipos_ui.py` /
`equipos_alta_rapida_ui.py`. `cabledoc.py`: 6.167 → 4.986 líneas. Validado
con ast.parse, py_compile, pyflakes (cero warnings nuevos reales: sólo
"imported but unused" esperado del patrón de reexport, comparado contra
baseline de `main`), *move* verificado byte a byte contra el bloque
original (diff limpio salvo los imports diferidos agregados), import real
bajo Xvfb con identidad de objeto confirmada para los 8 nombres + la
referencia cruzada `equipos_ui` → `cabledoc` → `CatalogoEquiposListado` /
`_DialogoInstanciarCatalogo`, import limpio de `equipos_ui.py` /
`cables_conexiones_ui.py` / `conectores_ui.py` / `pantallas_avanzadas.py`, y
smoke test funcional bajo Xvfb contra una base de fixture generada desde
`schema_db.sql` (el repo, en esta sesión, no traía `database/db.db`
versionado ni siquiera vacío — ver Blockers) con 1 molde + 2
conectores-molde de fixture insertados por SQL directo: `CatalogoEquiposListado`
cargó la fila del molde, `_DialogoCatalogoEquipo` en modo edición
(`e_nombre.get_text()=="Molde Fixture"`) y en modo alta,
`_DialogoAltaRapidaCatalogo` abrió sin excepciones, `_ConectoresCatalogoListado`
cargó los 2 conectores-molde. Rama: `refactor/etapa5-catalogo-equipos-ui`
(sin commitear — diff entregado para que Fede haga el commit en su
terminal).

Entrega 6 completada (confirmación retroactiva): `senal_catalogo_ui.py`
(915 líneas) — `_DialogoSenal`, `SenalesListado`, `TiposFormatoSenalListado`,
`_mostrar_donde_esta_senal`, `abrir_buscador_senal`, `_DialogoLinajeSenal`,
`_ArbolLinajeSenal`, `_mostrar_lista_simple`, `_DialogoPropagacionSenal`,
`abrir_propagacion_senal`, `_DialogoReportesSenal`, `abrir_reportes_senal`,
`abrir_limpiar_senales_propagadas`. `cabledoc.py`: 4.986 → 4.150 líneas.
Confirmado por inspección directa del checkout de Papi al arrancar esta
sesión — el código ya estaba aplicado, pero la entrega nunca se documentó
en `changelog.txt`/PROGRESS (corte de sesión). Entrada retroactiva agregada
en `changelog.txt`; validación detallada (diff byte a byte, import real,
smoke test) no se pudo reconstruir retroactivamente en esta sesión — sólo
se confirmó `ast.parse`/`py_compile` sobre el archivo tal cual estaba en el
checkout, sin cambios.

Entrega 7 completada: `racks_salas_ui.py` (529 líneas: `RacksListado`,
`_DialogoRack`, `PosicionEnRackListado`, `_DialogoPosicionRack`,
`SalasListado`, `_DialogoRackPorSala`, `RackPorSalaListado`,
`_DialogoEquipoNoRackSala`, `EquiposNoRackSalaListado`) +
`frames_slots_ui.py` (890 líneas: `CatalogoFramesListado`,
`_DialogoCatalogoFrame`, `_SlotsCatalogoListado`, `_DialogoSlotCatalogo`,
`_DialogoInstanciarCatalogoFrame`, `FramesListado`, `_DialogoFrame`,
`SlotsListado`, `_DialogoSlot`). El bloque "Racks" (1091-1338) y "Salas"
(2214-2431) no eran contiguos entre sí (entre ellos queda Frames/Slots,
que se extrae al archivo hermano, y `ConexionesDeEquipoVentana`, que
permanece en `cabledoc.py` fuera del alcance de esta entrega) — se unieron
en `racks_salas_ui.py`, mismo criterio de tamaño que las Entregas 3 y 5.
El bloque "Catálogo de frames + Frames + Slots" (1340-2147) sí era
contiguo, sin sorpresas de layout (como la Entrega 4). `cabledoc.py`
reexporta los 18 nombres movidos (9+9). Referencias cruzadas a
`EquiposListado`, `MarcasListado`, `ImagenesListado`,
`_escribir_json_comprimido`, `_leer_json_generico`, `_sel_imagen_desde_abm`
(siguen en `cabledoc.py`/`equipos_ui.py`) resueltas con import diferido,
mismo patrón que las entregas anteriores — incluida la referencia cruzada
entre los dos módulos hermanos de esta misma entrega (`racks_salas_ui.py`
importa `FramesListado` dentro de `_DialogoPosicionRack._sel_frame`), que
también rutea vía `from cabledoc import FramesListado` en vez de un import
directo entre hermanos, siguiendo la convención ya establecida por
`cables_conexiones_ui.py` con `EquiposListado`. `abrir_vista_rack` se
importa a nivel de módulo en ambos archivos nuevos; `abrir_coords_imagen`,
`abrir_vista_frame_slots`, `abrir_editor_masivo_slots` y
`abrir_editor_masivo_slots_catalogo` a nivel de módulo en
`frames_slots_ui.py`. `cabledoc.py`: 4.150 → 2.917 líneas. `APP_VERSION`
→ `1.20260904050000`. Validado con ast.parse + py_compile sobre los 3
archivos, diff línea por línea de cada bloque movido contra su ubicación
original (script propio, idéntico carácter por carácter salvo los imports
diferidos agregados), diff completo de `cabledoc.py` contra el original
(confirma que sólo se tocaron 4 zonas: APP_VERSION, bloque de reexport
nuevo, y los dos bloques removidos), grep de los 16 archivos externos que
hacen `from cabledoc import` (confirma que `RacksListado`/`_DialogoFrame`,
únicos nombres de esta entrega referenciados fuera de `cabledoc.py`, ambos
desde `rack_ui.py`, siguen resolviendo sin cambios) y chequeo manual de
nombres libres por función (script ast propio, sustituto de pyflakes) sin
hallazgos reales. **No se pudo correr** import real bajo Xvfb ni pyflakes
real ni smoke test funcional — este sandbox no tuvo acceso de red en esta
sesión (ver Blockers), a diferencia de las Entregas 1-6. Pendiente que
Fede corra ese checklist en su entorno antes de mergear. Rama: no creada
(sin acceso a GitHub esta sesión) — diff entregado (`cabledoc.py.diff`)
para que Fede haga `git checkout -b`, aplique los 3 archivos y commitee.

Entrega 8 completada: `catalogos_basicos_ui.py` (1.007 líneas de código
movido, ~1.083 con header/docstring/imports) — `MarcasListado`,
`_DialogoTipoEquipo`, `TiposEquipoListado`, `TiposConectorListado`,
`RiesgoSenalListado`, `_DialogoTipoCable`, `TiposCableListado`,
`_DialogoTipoFicha`, `TiposFichaListado`, `CategoriasProblemaListado`,
`ProblemasEquipoListado`, `_DialogoProblema`, `ImagenesListado`,
`_DialogoImagen` (bloque "catálogos chicos" del plan, líneas 244-1031) +
`ConexionesDeEquipoVentana`, `DiagramasGuardadosListado`,
`GeneradorDiagrama`, `EquipoInfoExtra` (bloque "huérfanos", líneas
1135-1350, separados del anterior por `_DialogoRenombrarConectoresCatalogo`
que queda en `cabledoc.py`). Deviación respecto del plan documentada en el
Current Focus de arriba y en el docstring del módulo nuevo: ~1.112 líneas
totales del archivo final vs. ~774 estimadas por el plan §4, por sumar los
4 bloques huérfanos. Referencia cruzada a `_DialogoCable`
(`cables_conexiones_ui.py`) resuelta con import diferido dentro de
`RiesgoSenalListado.editar`, ruteando vía `from cabledoc import
_DialogoCable` — mismo patrón ya establecido por `racks_salas_ui.py` con
`FramesListado`. `cabledoc.py`: 2.917 → 1.949 líneas. `APP_VERSION` →
`1.20260904060000`. Validado con ast.parse + py_compile sobre ambos
archivos, diff byte a byte de cada bloque movido contra el checkout de
`main` en GitHub (idéntico salvo el import diferido agregado; confirma
además que `_DialogoRenombrarConectoresCatalogo` quedó correctamente
excluido del *move*), pyflakes comparado contra baseline de `main` (cero
F821 nuevos, únicas advertencias nuevas son "imported but unused" del
patrón de reexport esperado), import real bajo Xvfb con identidad de
objeto confirmada para los 18 nombres movidos + `_DialogoRenombrarConectoresCatalogo`
(no movido), import limpio de los 13 módulos externos que dependen de
`cabledoc`, y smoke test funcional bajo Xvfb contra una copia descartable
de `database/db.db` (que en esta sesión sí venía versionado en el repo,
con esquema pero sin datos) con 1 fila de fixture por tabla insertada por
SQL directo. Único hallazgo: no se pudo instanciar `EquipoInfoExtra` en
el smoke test porque su `__init__` llama a un diálogo modal (`.run()`)
que bloquea esperando respuesta interactiva — cubierto por el diff byte a
byte y la validación por separado de sus dos dependencias directas. Esta
sesión sí tuvo acceso de red (a diferencia de la Entrega 7): se instalaron
`gir1.2-gtk-3.0`, `python3-gi-cairo`, `xvfb` y `pip graphqlite` sin
problemas. Rama: `refactor/etapa8-catalogos-basicos-ui` (creada localmente
desde `main` de GitHub, sin commitear — diff entregado para que Fede haga
el commit en su terminal).



## Todo List

- [x] Entrega 1 — `pantallas_comunes.py` como única fuente de utilidades
      genéricas de UI compartidas (base de todo lo demás)
- [x] Entrega 2 — `cables_conexiones_ui.py` (desbloquea Extensión de cable)
- [x] Entrega 3 — `equipos_ui.py` + `equipos_alta_rapida_ui.py`
- [x] Entrega 4 — `conectores_ui.py`
- [x] Entrega 5 — `catalogo_equipos_ui.py` + `catalogo_equipos_alta_rapida_ui.py`
- [x] Entrega 6 — `senal_catalogo_ui.py`
- [x] Entrega 7 — `racks_salas_ui.py` + `frames_slots_ui.py`
- [x] Entrega 8 — `catalogos_basicos_ui.py` (incluye 4 bloques huérfanos
      del plan: `ConexionesDeEquipoVentana`, `DiagramasGuardadosListado`,
      `GeneradorDiagrama`, `EquipoInfoExtra` — ver desviación documentada
      arriba; `_DialogoRenombrarConectoresCatalogo` queda pendiente de
      asignar destino, no forma parte de esta entrega)
- [ ] Entrega 9 — `panel_arbol_ui.py` (penúltimo a propósito: orquestador
      que referencia diálogos de todos los dominios anteriores)
- [ ] Entrega 10 — Cierre: `cabledoc.py` queda como fachada delgada
      (`VentanaPrincipal` + reexportaciones + entry point), verificar que
      baje de 9.405 a ~700 líneas

## Latest Blockers/Discoveries

- **Acceso de escritura a GitHub**: este sandbox no tiene credenciales para
  pushear a `fschpp/CabledocDesktop` ni abrir PRs vía API. Se resolvió
  trabajando 100% local (rama + commit) y entregando un patch para que Papi
  haga `git push` y abra el PR manualmente. Sigue vigente en la Entrega 2.
- `pantallas_comunes.py` ya tenía `s()` y `confirmar()` duplicados (desde la
  Entrega 0 del refactor de `pantallas_avanzadas.py`), confirmado
  byte-idénticos antes de mover el resto — no hizo falta resolver ningún
  divergencia entre versiones.
- El sandbox de validación no tenía `gir1.2-gtk-3.0`, `python3-gi-cairo` ni
  el paquete `graphqlite` (dependencia de `graph_impact.py` vía
  `cypher_console.py`, no listada en `requisitos.txt`) — se instalaron para
  poder correr el import real bajo Xvfb. Papi debería confirmar si
  `graphqlite` debería agregarse a `requisitos.txt` o si es una dependencia
  interna que se instala de otra forma. Se reinstalaron en la Entrega 2 (no
  persisten entre sesiones del sandbox).
- Pendiente arrastrada (no bloqueante para este PR): correr el smoke test
  de la Entrega 1 contra `database/db.db` **real** de Papi en vez de la base
  sintética generada en este sandbox.
- **Entrega 2 — hallazgo nuevo:** `_parse_float_opt`/`_fmt_float_opt` no
  estaban contempladas en el plan original como helpers a mover, pero se
  usan tanto dentro del bloque de Cables (ancho de banda override) como en
  bloques que quedan en `cabledoc.py` (TipoCable, Problema). Se movieron a
  `pantallas_comunes.py` para no duplicarlas — documentado como desviación
  deliberada, no como bug.
- **Entrega 2 — hallazgo nuevo:** el `database/db.db` versionado en el repo
  de GitHub está vacío de cables/conexiones (probablemente un fixture de
  esquema, no de datos). El smoke test de esta entrega insertó 2 filas de
  `cable` por SQL directo sobre una copia descartable para poder abrir
  `_DialogoCable` en modo edición y `_DialogoFusion` con datos reales.
  Pendiente arrastrada (igual que en la Entrega 1): correr el smoke test
  contra el `db.db` real de Papi.
- **Entrega 3 — hallazgo nuevo:** los dos bloques que forman `equipos_ui.py`
  (`EquiposListado` y `_DialogoDireccionConector`+`_DialogoEquipo`) no eran
  contiguos en `cabledoc.py` — el diseño del plan (§4) ya anticipaba el split
  en 2 archivos por tamaño, pero no que uno de los dos resultantes se
  armaría concatenando dos rangos de líneas no adyacentes. Se resolvió sin
  tocar `_DialogoDuplicarMolde`/`_DialogoAltaRapidaCatalogo` (quedan en
  `cabledoc.py` para la Entrega 5) ni su orden relativo.
- **Entrega 3 — mismo hallazgo que la Entrega 2:** `database/db.db` del repo
  también está vacío de equipos. Smoke test con 1 fila de fixture insertada
  por SQL directo sobre copia descartable. Pendiente arrastrada: correr
  contra el `db.db` real de Papi (acumulada de las 3 entregas).
- **Entrega 4 — `graphqlite` sí está en PyPI**: a diferencia de lo que se
  sospechaba en la Entrega 1, `pip install graphqlite --break-system-packages`
  funcionó sin problema en este sandbox (`from graphqlite.graph import Graph`
  importó OK). Sigue sin estar listado en `requisitos.txt` — Papi debería
  confirmar si conviene agregarlo ahí para que quede documentado, aunque ya
  no es un hallazgo bloqueante.
- **Entrega 4 — bloque contiguo, sin sorpresas de layout**: a diferencia de
  la Entrega 3, `ConectoresListado`, `_DialogoConector` y
  `_DialogoRenombrarConectores` estaban contiguos en `cabledoc.py` (un solo
  rango de líneas bajo el separador `# ─── Conectores ───`), así que el
  *move* fue directo sin tener que concatenar rangos no adyacentes.
- **Entrega 4 — confirmación de patrón de migración idempotente**: las
  columnas `id_funcion_patchera` (tabla `conector`) y
  `es_armado_correcto`/`detalle_armado` (tabla `conector`, no `conexion` a
  pesar del nombre similar de columnas en esa otra tabla) no estaban en el
  fixture creado desde `schema_db.sql` a pelo, pero se crearon solas al
  llamar a `Modelo.funciones_patchera()` y `Modelo.asegurar_tablas_bitacora()`
  respectivamente durante la apertura del diálogo — sin necesidad de tocar
  nada a mano. Confirma que el patrón `asegurar_columnas_*`/`asegurar_tablas_*`
  autoinvocado desde los métodos que lo necesitan (no sólo desde un setup
  central) sigue funcionando correctamente tras el *move*.
- **Entrega 4 — mismo hallazgo que las Entregas 2 y 3:** `database/db.db` del
  repo sigue vacío de datos. Smoke test con 1 equipo (rol PATCHERA, para
  ejercitar el combo de función de patchera) + 2 conectores de fixture
  insertados por SQL directo sobre copia descartable. Pendiente arrastrada:
  correr contra el `db.db` real de Papi (acumulada de las 4 entregas).
- **Entrega 5 — hallazgo nuevo, distinto a las Entregas 2-4:** el clon de
  `main` usado en esta sesión no traía `database/db.db` versionado en
  absoluto (ni siquiera el fixture de esquema vacío de las entregas
  anteriores). Se generó una base descartable ejecutando `schema_db.sql`
  completo por `sqlite3` directo (vía `sqlite3.Connection.executescript` de
  Python, ya que el binario `sqlite3` de línea de comandos tampoco estaba
  instalado en el sandbox), y se insertaron 1 `tipo_equipo` (rol
  ENRUTADOR)/1 `marca`/1 `tipo_conector`/1 `equipo_catalogo` ("Molde
  Fixture")/2 `conector_catalogo` por SQL directo para poder ejercitar
  `_DialogoCatalogoEquipo` en modo edición y `_ConectoresCatalogoListado`
  con datos reales. No cambia la validación de fondo (mismo patrón:
  fixture descartable, nunca la base real de Papi) pero sí el punto de
  partida — Papi debería confirmar si `database/db.db` dejó de versionarse
  a propósito (por ejemplo al pasar a sync vía rclone/RoundSync con Google
  Drive como fuente de verdad) o si es un descuido del repo en GitHub.
- **Entrega 5 — confirmación del split anticipado en la Entrega 3:** los dos
  nombres que quedaron pendientes en `cabledoc.py` en la Entrega 3
  (`_DialogoDuplicarMolde` y `_DialogoAltaRapidaCatalogo`) resultaron ser,
  efectivamente, parte del mismo bloque contiguo "Catálogo de equipos
  (moldes)" de esta entrega — no hubo sorpresas de layout como en la
  Entrega 3, el bloque completo (1.205 líneas) estaba de corrido bajo un
  único separador.
- **Entrega 6 — hallazgo de esta sesión (documentación desincronizada):**
  al arrancar esta sesión, `PROGRESS_REFACTOR_CABLEDOC.md` marcaba la
  Entrega 6 como "en progreso" y `changelog.txt` no tenía ninguna entrada
  posterior a la Entrega 5, pero el checkout de Papi ya tenía
  `senal_catalogo_ui.py` completo y `cabledoc.py` ya la reexportaba
  (4.986 → 4.150 líneas). Se verificó por inspección directa de los
  archivos antes de dar por buena cualquiera de las dos fuentes. Lección
  para las próximas sesiones: **siempre confirmar el estado real del
  checkout (grep de imports + `wc -l`) contra lo que dicen estos
  documentos antes de asumir en qué entrega hay que seguir** — la
  documentación puede quedar atrás del código si una sesión se corta
  antes de cerrar sus propios archivos de seguimiento.
- **Entrega 7 — sin acceso de red en esta sesión:** a diferencia de las
  Entregas 1-6, este sandbox no tuvo egress habilitado, así que no se
  pudo instalar `gir1.2-gtk-3.0`/`python3-gi-cairo` ni `pyflakes`, y por lo
  tanto no se corrió el import real bajo Xvfb ni el smoke test funcional
  para esta entrega. Se compensó con `ast.parse` + `py_compile` + un
  chequeo manual de nombres libres por función (script ast propio,
  sustituto aproximado de pyflakes F821) sobre los 3 archivos tocados, más
  el diff byte a byte de cada bloque movido. Sin hallazgos. **Pendiente
  no bloqueante:** correr el checklist completo de validación (import real
  + Xvfb + smoke test contra `database/db.db` real) en un entorno con red,
  antes de mergear esta entrega.
- **Entrega 7 — mismo criterio de bloques no contiguos que la Entrega 3:**
  el plan (§4) agrupaba "Racks/Frames" como un solo dominio a splitear por
  tamaño en `racks_salas_ui.py` + `frames_slots_ui.py`, pero no anticipaba
  que dentro de "Racks/Frames" los sub-bloques "Racks" y "Salas" (que van
  juntos en `racks_salas_ui.py`) no fueran contiguos entre sí en el
  original — separados por el bloque completo de Frames/Slots y por
  `ConexionesDeEquipoVentana`. Se resolvió igual que en la Entrega 3:
  concatenando los dos rangos no adyacentes en un único archivo, sin tocar
  el orden relativo interno de cada uno.
