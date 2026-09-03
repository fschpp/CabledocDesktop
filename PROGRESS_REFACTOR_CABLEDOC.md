# PROGRESS_REFACTOR_CABLEDOC.md — Refactor de `cabledoc.py`

Seguimiento específico de `plan_refactor_cabledoc.md`. Documento separado de
`PROGRESS.md` (desarrollo funcional general) y de `PROGRESS_REFACTOR.md`
(que ya cerró el refactor de `pantallas_avanzadas.py`, 11.032 → 145 líneas),
para no mezclar tres historiales con ritmos distintos.

---

## Current Focus

Entrega 1 completada: consolidados en `pantallas_comunes.py` los 16 helpers
genéricos/base y de formulario que vivían duplicados/sueltos en
`cabledoc.py` (`s`, `mostrar_error`, `mostrar_info`, `confirmar`,
`_sort_func_natural`, `VentanaListado`, `DialogoNombre`, `_grid`,
`_lbl_entry`, `_entry`, `_entry_btn`, `_searchable_combo`, `_get_combo_id`,
`_set_combo_id`, `_repopulate_combo`, `_pack_ultima_edicion`).
`cabledoc.py` los reexporta con un único `from pantallas_comunes import
(...)`. Validado con ast.parse, pyflakes (diff contra baseline), import real
bajo Xvfb con identidad de objeto confirmada, y smoke test funcional contra
una base SQLite real generada desde `schema_db.sql`. Rama:
`refactor/etapa1-comunes-cabledoc`.

## Todo List

- [x] Entrega 1 — `pantallas_comunes.py` como única fuente de utilidades
      genéricas de UI compartidas (base de todo lo demás)
- [ ] Entrega 2 — `cables_conexiones_ui.py` (desbloquea Extensión de cable)
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
  haga `git push` y abra el PR manualmente.
- `pantallas_comunes.py` ya tenía `s()` y `confirmar()` duplicados (desde la
  Entrega 0 del refactor de `pantallas_avanzadas.py`), confirmado
  byte-idénticos antes de mover el resto — no hizo falta resolver ningún
  divergencia entre versiones.
- El sandbox de validación no tenía `gir1.2-gtk-3.0`, `python3-gi-cairo` ni
  el paquete `graphqlite` (dependencia de `graph_impact.py` vía
  `cypher_console.py`, no listada en `requisitos.txt`) — se instalaron para
  poder correr el import real bajo Xvfb. Papi debería confirmar si
  `graphqlite` debería agregarse a `requisitos.txt` o si es una dependencia
  interna que se instala de otra forma.
- Pendiente arrastrada (no bloqueante para este PR): correr el smoke test
  de la Entrega 1 contra `database/db.db` **real** de Papi en vez de la base
  sintética generada en este sandbox.
