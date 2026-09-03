# PROGRESS_REFACTOR_CABLEDOC.md — Refactor de `cabledoc.py`

Seguimiento específico de `plan_refactor_cabledoc.md`. Documento separado de
`PROGRESS.md` (desarrollo funcional general) y de `PROGRESS_REFACTOR.md`
(que ya cerró el refactor de `pantallas_avanzadas.py`, 11.032 → 145 líneas),
para no mezclar tres historiales con ritmos distintos.

---

## Current Focus

Entrega 3 completada: extraídos `equipos_ui.py` (1.207 líneas: `EquiposListado`,
`_DialogoDireccionConector`, `_DialogoEquipo`) y `equipos_alta_rapida_ui.py`
(591 líneas: `_DialogoAltaRapidaEquipo`), tal como estaba diseñado en
`plan_refactor_cabledoc.md` §4 (split en 2 archivos porque juntos superaban
las ~900 líneas objetivo). Los bloques de `EquiposListado` y de
`_DialogoDireccionConector`+`_DialogoEquipo` no eran contiguos en el
original — entre ellos quedan en `cabledoc.py` `_DialogoDuplicarMolde` y
`_DialogoAltaRapidaCatalogo` (dominio de catálogo de equipos, Entrega 5) —
así que se unieron en `equipos_ui.py` sin tocar esas dos clases.
`cabledoc.py` reexporta los 4 nombres movidos. Referencias cruzadas a
`CatalogoEquiposListado`, `_DialogoInstanciarCatalogo`, `ImagenesListado`,
`MarcasListado`, `TiposEquipoListado`, `ConectoresListado`,
`_DialogoRenombrarConectores`, `ProblemasEquipoListado`, `TiposConectorListado`
(siguen en `cabledoc.py`) resueltas con import diferido; ídem la referencia
cruzada entre los dos módulos nuevos (`_DialogoDireccionConector` ↔
`_DialogoAltaRapidaEquipo`). `cabledoc.py`: 8.217 → 6.568 líneas. Validado con
ast.parse, py_compile, import real bajo Xvfb con identidad de objeto
confirmada (incluida la referencia cruzada entre módulos nuevos), import
limpio de los 4 archivos que dependen de `cabledoc`, y smoke test funcional
bajo Xvfb contra una copia descartable de `database/db.db` con 1 equipo de
fixture insertado por SQL directo. Rama: `refactor/etapa3-equipos-ui`.
`APP_VERSION` → `1.20260903223802`.

## Todo List

- [x] Entrega 1 — `pantallas_comunes.py` como única fuente de utilidades
      genéricas de UI compartidas (base de todo lo demás)
- [x] Entrega 2 — `cables_conexiones_ui.py` (desbloquea Extensión de cable)
- [x] Entrega 3 — `equipos_ui.py` + `equipos_alta_rapida_ui.py`
- [ ] Entrega 4 — `conectores_ui.py`
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
