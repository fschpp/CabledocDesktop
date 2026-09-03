# PROGRESS_REFACTOR_CABLEDOC.md — Refactor de `cabledoc.py`

Seguimiento específico de `plan_refactor_cabledoc.md`. Documento separado de
`PROGRESS.md` (desarrollo funcional general) y de `PROGRESS_REFACTOR.md`
(que ya cerró el refactor de `pantallas_avanzadas.py`, 11.032 → 145 líneas),
para no mezclar tres historiales con ritmos distintos.

---

## Current Focus

Entrega 4 completada: extraído `conectores_ui.py` (466 líneas: `ConectoresListado`,
`_DialogoConector`, `_DialogoRenombrarConectores`), bloque contiguo en el
original (separador `# ─── Conectores ───`) — a diferencia de la Entrega 3,
no hubo que unir rangos no adyacentes. `cabledoc.py` reexporta los 3 nombres
movidos. Referencias cruzadas a `ImagenesListado` y `_DialogoSenal` (siguen
en `cabledoc.py`) resueltas con import diferido, mismo patrón que las
entregas anteriores; `abrir_coords_imagen` (usada en `_sel_coordenadas`) se
importa a nivel de módulo desde `pantallas_avanzadas`, igual que hace
`equipos_ui.py`. El uso interno residual de `_DialogoConector` dentro de
`PanelArbol` (todavía en `cabledoc.py`) sigue funcionando sin cambios porque
el nombre queda importado a nivel de módulo. `cabledoc.py`: 6.568 → 6.167
líneas. Validado con ast.parse, py_compile, pyflakes (cero warnings nuevos:
mismos 5 preexistentes en `main` más "imported but unused" esperado del
patrón de reexport), *move* verificado byte a byte contra el bloque original
(diff limpio salvo los 2 imports diferidos agregados), import real bajo
Xvfb con identidad de objeto confirmada, import limpio de `equipos_ui.py` /
`cables_conexiones_ui.py` / `pantallas_avanzadas.py`, referencia cruzada
`equipos_ui` → `ConectoresListado`/`_DialogoRenombrarConectores` vía
`cabledoc` resuelta al mismo objeto, y smoke test funcional bajo Xvfb contra
una copia descartable de `database/db.db` con 1 equipo PATCHERA + 2
conectores de fixture insertados por SQL directo: `ConectoresListado`
abrió y cargó datos, `_DialogoConector` en modo edición (combo de función de
patchera visible por ser equipo PATCHERA, sección de Armado visible
confirmando que `asegurar_tablas_bitacora()` corrió su `ALTER TABLE` sin
error) y en modo alta, y `_DialogoRenombrarConectores` cargó los 2
conectores fixture. Rama: `refactor/etapa4-conectores-ui` (sin commitear —
diff entregado para que Fede haga el commit en su terminal).

## Todo List

- [x] Entrega 1 — `pantallas_comunes.py` como única fuente de utilidades
      genéricas de UI compartidas (base de todo lo demás)
- [x] Entrega 2 — `cables_conexiones_ui.py` (desbloquea Extensión de cable)
- [x] Entrega 3 — `equipos_ui.py` + `equipos_alta_rapida_ui.py`
- [x] Entrega 4 — `conectores_ui.py`
- [ ] Entrega 5 — `catalogo_equipos_ui.py` + `catalogo_equipos_alta_rapida_ui.py`
- [ ] Entrega 6 — `senal_catalogo_ui.py`
- [ ] Entrega 7 — `racks_salas_ui.py` + `frames_slots_ui.py`
- [ ] Entrega 8 — `catalogos_basicos_ui.py`
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
