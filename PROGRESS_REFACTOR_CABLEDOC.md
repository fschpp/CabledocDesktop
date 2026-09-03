# PROGRESS_REFACTOR_CABLEDOC.md — Refactor de `cabledoc.py`

Seguimiento específico de `plan_refactor_cabledoc.md`. Documento separado de
`PROGRESS.md` (desarrollo funcional general) y de `PROGRESS_REFACTOR.md`
(que ya cerró el refactor de `pantallas_avanzadas.py`, 11.032 → 145 líneas),
para no mezclar tres historiales con ritmos distintos.

---

## Current Focus

Entrega 2 completada: extraído `cables_conexiones_ui.py` (853 líneas) con
`CablesListado`, `_DialogoFusion`, `_DialogoEligeLadoFantasma`,
`_DialogoCable`, `ConexionesListado`, `_DialogoConexion`, movidos 1:1 desde
`cabledoc.py`. `cabledoc.py` reexporta los 6 nombres con un único
`from cables_conexiones_ui import (...)`. Referencias cruzadas a
`EquiposListado`/`_DialogoEquipo`/`_DialogoConector` (siguen en `cabledoc.py`)
resueltas con import diferido dentro de los 2 métodos que las usan, mismo
patrón que ya usa el proyecto para cortar ciclos. Desviación deliberada del
plan: `_parse_float_opt`/`_fmt_float_opt` (usadas tanto dentro del bloque
movido como en otros bloques que quedan en `cabledoc.py`) se consolidaron en
`pantallas_comunes.py` en vez de quedar duplicadas entre los dos módulos
grandes. `cabledoc.py`: 9.079 → 8.217 líneas. Validado con ast.parse,
py_compile, import real bajo Xvfb con identidad de objeto confirmada, import
limpio de los 4 archivos que dependen de `cabledoc` (`bitacora_ui.py`,
`pantallas_avanzadas.py`, `diagrama_personalizado.py`, `cypher_console.py`),
y smoke test funcional bajo Xvfb contra una copia descartable de
`database/db.db` con 2 cables de fixture insertados por SQL directo (la base
del repo no tenía cables/conexiones cargados). Rama:
`refactor/etapa2-cables-conexiones-ui`. `APP_VERSION` → `1.20260903220447`.

## Todo List

- [x] Entrega 1 — `pantallas_comunes.py` como única fuente de utilidades
      genéricas de UI compartidas (base de todo lo demás)
- [x] Entrega 2 — `cables_conexiones_ui.py` (desbloquea Extensión de cable)
- [ ] Entrega 3 — `equipos_ui.py` + `equipos_alta_rapida_ui.py`
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
