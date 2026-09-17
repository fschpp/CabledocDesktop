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
- [/] Fase 3.3 — Soporte SVG en Kivy. Código de rasterización ya existe en
      `ui_kivy/widgets_base.py` (`crear_textura_imagen_svg`,
      `crear_textura_simbolo`), pero **no mostraba nada en mobile real**:
      `requirements-mobile.txt` dejaba `svglib`/`reportlab` comentadas como
      "opcionales" (correcto sólo para medir dimensiones vía
      `Modelo._dimensiones_svg_sin_gi`, incorrecto para el rasterizado
      real, que SIEMPRE las necesita). Entrega 2026-09-16 corrige el
      requirements y agrega logging (`log_error`) + mensaje de UI
      distinto para el caso "SVG no se pudo rasterizar" vs "sin imagen
      asignada", que antes eran indistinguibles en pantalla. **HALLAZGO
      NUEVO, sigue bloqueando el cierre de esta fase:** `reportlab` 4.x
      necesita además `rlPyCairo` (→ `pycairo`, extensión C contra
      libcairo del sistema) para el paso `renderPM.drawToFile` — no
      alcanza con `svglib`+`reportlab` solas, como se creía antes. Sigue
      pendiente la prueba de 15 minutos en Pydroid 3 real, ahora con el
      nombre correcto del paquete de riesgo (`rlPyCairo`/`pycairo`, no
      `reportlab`) — ver comentario extendido en requirements-mobile.txt.
      Si `pycairo` no compila en el dispositivo, evaluar como Fase 3.3-bis
      un rasterizador propio basado sólo en Pillow para el subconjunto de
      SVG que exporta la herramienta vectorial del proyecto (no
      implementado, es sólo una opción de respaldo si el camino actual
      no es viable en Android). **Actualización 2026-09-16T06:00 (Fase
      3.5, ver plan_svg_pygame_nanosvg_v1.md y changelog.txt):** agregada
      una ruta alternativa vía `pygame`/SDL_image (NanoSVG,
      `ui_kivy/svg_raster_pygame.py`), probada como PRIMARIA en
      `crear_textura_imagen_svg`/`crear_textura_simbolo`, con la cadena
      svglib/reportlab/rlPyCairo como fallback. A diferencia de
      rlPyCairo, pygame ya fue CONFIRMADO funcionando en Pydroid 3 real
      contra 7 SVG del proyecto, sin compilar nada — esto probablemente
      resuelve el riesgo de pycairo de arriba, pero sigue sin confirmarse
      contra `catalogo_simbolo_conector.svg_fragmento` reales (sólo se
      probó con imágenes de fondo completas + 3 símbolos sueltos, no con
      el formato de fragmento exacto que usa la Fase 3.4) ni contra
      `<text>`/gradientes complejos. No se cierra esta fase todavía por
      eso.
- [ ] Fase 3.4 — Símbolos de conector vectoriales escalados (`mm_por_pixel`,
      depende de que Fase 3.3 esté resuelta).
- [ ] `requirements-mobile.txt` (todavía no existe; se agrega junto con
      `ui_kivy/`).
- [ ] `README.md` de la raíz del repo integrado (arquitectura nueva).
- [x] Fase 4 — Consistencia visual del ABM en mobile (tarjeta + pestañas)
      para Cables/Conectores/Racks/Frames/Slots/Salas. Cables/Conectores/
      Equipos ya envueltos en `seccion_tarjeta()` desde antes; esta entrega
      (2026-09-16) suma los 6 diálogos restantes: `DialogoRack`,
      `DialogoPosicionRack`, `DialogoFrame`, `DialogoSlot` (dos secciones:
      "Datos del slot" + "Rectángulo en imagen") en `ui_kivy/pantallas_
      racks.py`, y `DialogoRackPorSala`, `DialogoEquipoNoRackSala` en
      `ui_kivy/pantallas_salas.py`. Sin tabs — ningún diálogo tuvo
      suficientes secciones lógicas para justificarlas, mismo criterio que
      preveía PLAN_CIERRE_ROADMAP_MOBILE.md (documento de Papi, no
      versionado en este repo). Sin backend nuevo, sólo envoltorio visual.
      Validado: ast.parse + py_compile + pyflakes (contra git stash, cero
      advertencias nuevas en ambos archivos) + smoke test real con Kivy
      2.3.1 bajo Xvfb (fixture SQLite desde schema_db.sql +
      `Modelo.asegurar_tablas_plano()` para la columna `sala.id_plano`
      que la vista de Rack por Sala necesita) — los 6 diálogos abren sin
      excepción y los que se probaron en modo edición (Rack/Posición/
      Frame/Slot/RackPorSala) poblan sus campos igual que antes del
      cambio.
- [ ] Fase 5 — Roadmap de paridad de pantallas nuevas (Diagnóstico, Riesgo
      analógico, Señal, Escenarios, Ubicación física en planos). Fases
      5.1-5.4 y el fix de integración de Vista Previa ya mergeados a
      `main` (ver changelog.txt 2026-09-16) — este checklist no se había
      actualizado en su momento, corregido acá. Sigue: Fase 5.2 (Riesgo,
      `riesgo_diagrama_ui.py`/`signal_risk_diagrama_ui.py`, sin empezar
      en `ui_kivy/`) y, por tamaño/riesgo, Ubicación física en planos
      (`ui_gtk/planos_ui.py`, sin empezar en mobile).
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
- **2026-09-16, reporte de Papi: "el mobile no muestra los SVG".**
  Investigado sobre `main` (`5ac63de`, ya con Fase 3.4/símbolos vectoriales
  mergeada). La funcionalidad SÍ está implementada en
  `ui_kivy/widgets_base.py` (`crear_textura_imagen_svg`/
  `crear_textura_simbolo`, ya con su propia caché), pero nunca pudo
  funcionar en un dispositivo real: `requirements-mobile.txt` dejaba
  `svglib`/`reportlab` comentadas, tratándolas como el "último recurso"
  que sólo hace falta para el caso raro de medir dimensiones sin
  viewBox/width/height — eso es cierto para *medir* (`Modelo.
  _dimensiones_svg_sin_gi`), pero el *rasterizado* real (kivy.core.image
  no soporta SVG en absoluto) pasa siempre por esas dos librerías, sin
  atajo. Resultado en cualquier instalación siguiendo el requirements tal
  cual: el `except Exception` de ambas funciones atrapaba el `ImportError`
  en silencio, la textura quedaba `None`, y la UI mostraba el mismo cartel
  genérico "Sin imagen asignada al equipo/conector" que si el equipo
  nunca hubiera tenido imagen — indistinguible para Papi/Fede del caso
  real de "no hay imagen". Se corrigió: (1) `requirements-mobile.txt`
  ahora declara `svglib`/`reportlab` como obligatorias, no opcionales;
  (2) ambas funciones de rasterizado llaman a `core.logger_cabledoc.
  log_error` en su except, dejando rastro real en `log.txt`;
  (3) `VisorImagenZoom` distingue en el mensaje de UI "sin imagen
  asignada" de "no se pudo mostrar la imagen SVG (revisar log.txt)".
  **Hallazgo adicional, no trivial:** probando el pipeline completo en
  este sandbox de escritorio, `svglib`+`reportlab` solas NO alcanzan —
  `reportlab` 4.x removió su backend de rasterización propio y
  `renderPM.drawToFile` ahora exige el paquete `rlPyCairo` (que a su vez
  compila `pycairo` contra libcairo del sistema). Se agregó `rlPyCairo` a
  `requirements-mobile.txt`, pero **queda sin confirmar si `pycairo`
  compila en Pydroid 3 real** (Android normalmente no trae libcairo-dev
  accesible a pip) — es la prueba de 15 minutos que este documento ya
  pedía, ahora con el nombre correcto del paquete de riesgo. Ver Fase 3.3
  arriba y el comentario extendido en requirements-mobile.txt.
