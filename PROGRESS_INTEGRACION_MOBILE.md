# PROGRESS — Integración CableDoc Desktop (GTK) + Mobile (Kivy)

Sigue a `plan_integracion_cabledoc_v3.md` (adjuntado por Papi, no versionado
en este repo todavía). Ver también `changelog.txt` (entradas 2026-09-11) para
el detalle línea por línea de lo tocado.

## Foco actual

Fase 2 recién cerrada (core/ + ui_gtk/ armados y validados), y GraphQLite/
Consola Cypher eliminados por completo del desktop (pedido explícito de
Papi, fuera del plan original — ver changelog.txt 2026-09-11T05:00). Falta
arrancar Fase 3: poner `ui_kivy/` (el zip de mobile) al día contra este
core real.

## Todo

- [x] Fase 0 — Confirmado punto de corte (main de fschpp/CabledocDesktop,
      commit `a79b615d`, post-Entrega 10 del refactor + fases de Planos +
      Paneles Vectoriales + referencia virtual de frame, todas ya en main).
- [x] Fase 1 — `core/` armado: modelo.py, i18n.py, graph_impact.py (+ patch
      cosmético de graphqlite), risk_engine.py, escenario_engine.py,
      senal_propagation.py, senal_estado.py, riesgo_analogico.py,
      diagnostico_falla.py, signal_risk.py, **+ senal_visual.py** (hallazgo:
      dependencia real de diagnostico_falla.py, no listada en el plan
      original) **+ logger_cabledoc.py** (hallazgo: no existía en desktop,
      es una adición del fork de mobile — ver "Bloqueos" abajo).
- [x] Fase 1 — Fix de rutas de datos en core/modelo.py (DB_PATH etc. subían
      un nivel de menos tras el move a core/).
- [x] Fase 2 — `ui_gtk/` armado: ~45 archivos GTK movidos, imports
      reescritos (incluidos los diferidos/indentados y los 3
      `__import__("modelo")` dinámicos de panel_arbol_ui.py).
- [x] Validación Fase 1-2: ast.parse + py_compile + pyflakes (0 F821 nuevos)
      + smoke test real bajo Xvfb contra fixture de schema_db.sql, con y sin
      graphqlite instalado (ver changelog.txt).
- [x] Eliminación de GraphQLite/Consola Cypher del desktop (pedido explícito
      de Papi, fuera del plan original — cambia el criterio de
      plan_integracion_cabledoc_v3.md §3/§6, que sólo preveía "envolver" el
      import): core/graph_impact.py sin ninguna dependencia de graphqlite
      (self._g reemplazado por self._grafo_construido: bool),
      ui_gtk/cypher_console.py eliminado del repo, ui_gtk/cabledoc.py sin
      el import/menú/botón/método que lo abría, i18n.py sin sus ~17 claves,
      docs (README/tutoriales/context.md/PROGRESS.md) actualizados. Esto
      **resuelve** el blocker de abajo ("cypher_console.py importa
      graphqlite sin guard") — se deja el texto original del blocker sin
      borrar, marcado como resuelto, por trazabilidad.
- [ ] `data/.gitignore` — decidir con Papi/Fede si se agrega en este mismo
      commit o aparte (no se tocó `.gitignore` en esta entrega).
- [ ] Fase 3.1 — Auditar el contrato exacto de coordenadas en modelo.py
      (qué métodos devuelven % crudo vs. ya convertido a píxel) función por
      función, con el repo completo a mano — identificado pero no trazado
      todavía, es el primer paso antes de tocar `ui_kivy/`.
- [ ] Fase 3.2 — Correr `Modelo.migrar_coordenadas_a_porcentaje()` una sola
      vez contra la base real, CON BACKUP PREVIO (el riesgo más grande del
      plan, §7).
- [ ] Fase 3 — Mover `pantallas_*.py`/`widgets_base.py`/`tema.py`/`main.py`
      del zip de mobile a `ui_kivy/`, reescribir sus imports de `modelo`/
      `i18n` a `core.modelo`/`core.i18n`, y ADAPTAR el código que hoy asume
      contrato viejo de coordenadas (mobile todavía trae su propio
      modelo.py de 1.365 líneas, muy atrás del de core/ — hay que revisar
      cada pantalla que dibuja/edita posiciones sobre imagen).
- [ ] Fase 3.3 — Soporte SVG en Kivy (validar `svglib`+`reportlab` en
      Pydroid 3 con una prueba chica de 15 minutos antes de comprometerse
      al flujo completo — no asumir que instala limpio).
- [ ] Fase 3.4 — Símbolos de conector vectoriales escalados (`mm_por_pixel`,
      depende de que Fase 3.3 esté resuelta).
- [ ] `requirements-mobile.txt` (todavía no existe; se agrega junto con
      `ui_kivy/`).
- [ ] `README.md` de la raíz del repo integrado (arquitectura nueva).
- [ ] Fase 4 — Consistencia visual del ABM en mobile (tarjeta + pestañas)
      para Cables/Conectores/Racks/Frames/Slots/Salas.
- [ ] Fase 5 — Roadmap de paridad de pantallas nuevas (Diagnóstico, Riesgo
      analógico, Señal, Escenarios, Ubicación física en planos).
- [ ] Fase 6/7 — Sync + pruebas cruzadas end-to-end.

## Latest Blockers/Discoveries

- **`logger_cabledoc.py` no existía en desktop.** Es una adición propia del
  fork de `modelo.py` de mobile (`log_error` en `Modelo._query`/`_exec`).
  Se trajo a `core/` por ser genérico y libre de GTK/Kivy, pero
  `core/modelo.py` (versión real de desktop) **no llama a `log_error` en
  ningún lado todavía** — esa integración de logging de errores se perdería
  si mobile pasa a usar el `modelo.py` real sin más. Decisión pendiente:
  ¿agregar las 2 llamadas a `log_error` dentro de `core/modelo.py`
  (`_query`/`_exec`), mismo patrón que tenía mobile? Es un cambio chico y
  aislado, pero toca el archivo de 7.294 líneas más sensible del proyecto —
  se prefiere confirmarlo con Papi antes de tocarlo sin que estuviera
  pedido explícitamente.
- **`senal_visual.py` es dependencia real de `diagnostico_falla.py`**
  (`VisualizadorSenal`), libre de GTK, y el plan original no lo había
  listado en el árbol de `core/`. Se agregó sin pedir confirmación por ser
  de bajo riesgo (mismo criterio "GTK-free confirmado por grep" que ya
  usaba el plan para los otros 7 motores).
- **Fix de rutas real, no cosmético puro**, en `core/modelo.py`: mover
  `modelo.py` a `core/` sin ajustar `DB_PATH`/`IMG_DIR`/etc. hubiera roto
  la resolución de `data/` en cualquier instalación real (el plan lo
  clasificaba como "cambio cosmético", pero sin este ajuste puntual la app
  no encuentra la base de datos). Documentado en detalle en changelog.txt.
- **`cypher_console.py` importa `graphqlite` a nivel de módulo, sin guard**
  (a diferencia de `graph_impact.py`, que sí lo tiene ahora). Como
  `ui_gtk/cabledoc.py` importa `cypher_console` incondicionalmente al
  arrancar, **hoy por hoy el desktop completo requiere graphqlite instalado
  para poder abrir, no sólo para usar la Consola Cypher** — a pesar de que
  el plan (§1) dice que esa ventana "ya tiene su propio chequeo de
  'componente no disponible' al abrir la ventana". Ese chequeo existe para
  cuando SE ABRE la ventana, pero no cubre el import a nivel de módulo. No
  se tocó (cypher_console.py está fuera del alcance de core/ y de mobile
  por decisión explícita de Papi), pero vale la pena que Fede lo sepa: si
  algún día se quiere instalar el desktop en una máquina sin graphqlite,
  esto rompe el arranque completo, no sólo la Consola Cypher.
  **[RESUELTO 2026-09-11T05:00]** Papi pidió eliminar directamente
  `cypher_console.py` y toda dependencia de graphqlite del desktop, en vez
  de sólo aislar el import — ver changelog.txt de esa fecha. El desktop ya
  no requiere graphqlite bajo ninguna circunstancia.
- Repo de origen: `fschpp/CabledocDesktop` commit `a79b615d93164c8123db67d13
  8484766c0cb44ef` (2026-09-10 23:53 -03:00). Zip de mobile: adjuntado por
  Papi en esta sesión (README interno dice "Estado: Fase 6 completa
  (PatcherasVista)" — CRUD completo + 3 vistas gráficas migradas, más
  avanzado de lo que plan_integracion_cabledoc_v3.md daba por sentado al
  citar sólo el README viejo del mobile en su §1).
