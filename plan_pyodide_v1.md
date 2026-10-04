# Plan: Port de CableDoc (GTK3) a Pyodide / navegador (v1)

## Contexto

Objetivo: correr CableDoc en el navegador reutilizando `core/` (Python puro) sobre
Pyodide y rehaciendo la UI en HTML/JS. Fuente de verdad: `main` de
`github.com/fschpp/CabledocDesktop`. Descartado: wxWidgets-wasm (reescritura
total en C++). Alternativas ya evaluadas: Broadway (`plan_broadway_v1.md`) y
Flask/FastAPI.

Tamaño medido (LOC Python): `core/` 15.433 · `ui_gtk/` 31.623 · `ui_kivy/` 19.741
(fuera de alcance) · `main.py` 1.341.

## Convenciones de esta entrega

- Pre-tarea obligatoria: estimar tokens → OK de Pototo; confirmar archivos al día;
  avisar si hay cambios de estructura de tablas.
- Ediciones quirúrgicas (`str_replace`); `py_compile` antes de entregar; cambios
  documentados en `changelog.txt` (`YYYY-MM-DDTHH:MM archivo (alcance): desc`).
- Actualizar `PROGRESS.md` al cerrar cada hito (regla de `CLAUDE.md`).
- **`core/` sigue siendo compartido con GTK y Kivy**: ningún cambio puede romper
  desktop ni mobile. Todo cambio en `core/` debe ser retrocompatible.
- Nueva carpeta `ui_web/` (HTML/JS + `bridge.py`). No se toca `ui_gtk/` ni `ui_kivy/`.
- "continuar" avanza de tarea en tarea.

## Decisiones de arquitectura

| # | Decisión | Motivo |
|---|---|---|
| D1 | Python corre en un **Web Worker** con Pyodide; la UI en el hilo principal | No bloquear la UI en consultas largas |
| D2 | UI en **JS sin build** (ES modules + Web Components o Preact por CDN); sin framework pesado | Mantenible sin toolchain |
| D3 | API única `bridge.py`: funciones que envuelven `Modelo`/motores y devuelven JSON | Desacopla UI de `Modelo` (clase estática de ~460 métodos) |
| D4 | `.db` en FS de Pyodide con persistencia (IDBFS + `syncfs` tras cada escritura); imágenes y picon en **OPFS** desde JS, servidas por blob URL bajo demanda; manuales fuera del paquete | Sobrevive recargas sin sincronizar decenas de MB en cada commit |
| D5 | Diagramas en **SVG** (interacción y export) y `<canvas>` solo donde el rendimiento lo exija | Reemplaza Cairo; SVG exporta nativo |
| D6 | Import/export del `.db` completo (+ catálogo JSON v2) como mecanismo de respaldo y sync | Sin servidor |
| D7 | Un solo usuario/pestaña escribe a la vez (lock por pestaña) | SQLite en wasm no es multi-escritor |

## Riesgos conocidos

1. `modelo.py` ejecuta `asegurar_directorios()` y `asegurar_base_datos()` al
   importarse y usa `DB_PATH`/`IMG_DIR`/`PICON_DIR`/`MANUALES_DIR` derivados de
   `__file__` (líneas ~15-70). Hay que montarlos en el FS virtual de Pyodide.
2. `Modelo._conn()` abre una conexión por operación (`sqlite3.connect(DB_PATH)`).
   En Pyodide funciona, pero cada `commit` exige persistir (D4).
3. `senal_visual.py` usa Cairo solo para componer PNG (mosaico/overlay/key/audio
   embebido). Reemplazo: Pillow o canvas.
4. Medición de imágenes: ya existe fallback Pillow + regex sin `gi`
   (`_dimensiones_*_sin_gi`). SVG raro sin viewBox cae a `svglib` → no disponible
   en Pyodide; aceptar "sin medida" o medir en JS.
5. Rendimiento: el historial del proyecto muestra que el filtrado de árboles
   requiere cálculo en memoria (4-19 ms vs 10-22 s). Replicar el patrón
   (cache en Python/JS, render solo de lo visible, listas virtualizadas).
6. Tamaño de datos medido (ver 0.1): base chica (950 KB) e imágenes moderadas (~15 MB); el único volumen grande es `manuales/` (509 MB), que no se carga en el navegador.
7. Primera carga ~10 MB (Pyodide); usar service worker para cachear.

## Fase 0 — Prueba de viabilidad (3-5 días, ~150-300k tokens)

Criterio de éxito: abrir el `db.db` real en el navegador, ejecutar `Modelo`,
`GraphImpactAnalyzer` y `risk_engine` con resultados idénticos a desktop.

- [x] **0.1** Medido (2026-09-30): `db.db` 950 KB · `imagen/` 13 MB (94 archivos) · `picon/` 1,3 MB · `manuales/` 509 MB. Decisión: el `.db` va en el FS de Pyodide con `syncfs` (950 KB, barato); `imagen/` y `picon/` (~15 MB) se guardan en OPFS desde JS y se cargan bajo demanda; **`manuales/` (509 MB) queda fuera del paquete inicial**: se abre/sube archivo por archivo, o se omite en v1.
- [x] **0.2** Verificado en navegador real (Firefox, `http://127.0.0.1:8000`): Pyodide 314.0.7 desde copia local en **1,98 s** (carga en frío total 2,03 s), `core.zip` montado en 0,03 s. Requisito: el worker debe ser **de tipo módulo** (`pyodide.mjs`); los workers clásicos con `importScripts` no funcionan con esta versión.
- [x] **0.3** `core/` montado en `/app/core` del FS virtual: `_REPO_ROOT` resuelve solo a `/app`, así que **no hace falta tocar `modelo.py`**. Solo hay que montar `/app/data` sobre OPFS/IDBFS (ver 0.8). Falta empaquetar como zip para el navegador.
- [x] **0.4** `db.db` real (928 KB) cargado por el usuario en el navegador, abierto con `Modelo`; vistas y triggers funcionan (benchmark completo sin errores).
- [x] **0.5** `gi` falla limpio y `modelo.py` importa sin errores. Pillow 12.2.0 carga en el navegador desde el CDN (`cdn.jsdelivr.net/pyodide/v314.0.7/full/`) por URL del wheel, en 1,7 s; la copia local no lo incluye.
- [x] **0.6** Con el `db.db` real (418 equipos, 2071 conectores, 515 cables, 945 conexiones): `construir_grafo`, 10 simulaciones de falla (impactados/con señal/cables), IRF de todos los equipos, criticidad, 2 linters y una consulta de `conexiones_ambos_extremos` dan **hashes idénticos** en CPython nativo y en Pyodide. Script: `ui_web/tests/bench_core.py`.
- [x] **0.7** Medido en Firefox (2026-09-30): carga en frío 2,04 s · import de `core` 0,17 s · `construir_grafo` 0,057 s · 10 simulaciones 0,13 s · **IRF de todos los equipos 3,2 s** (nativo 1,76 s) · criticidad 0,017 s · linters 0,026-0,075 s · memoria wasm 36 MB. Los 6 hashes comparables son idénticos a CPython nativo.
- [x] **0.8** Persistencia verificada: tras recargar (F5), `db.db` (928 KB) y las 4 marcas de escritura SQLite siguen en IndexedDB sin volver a cargar el archivo. Cada escritura + `syncfs` tarda ~10 ms.

### Decisión de la Fase 0: **GO** (2026-09-30)

Motor idéntico a nativo, rendimiento aceptable (solo el IRF completo, 3,2 s, pide correr en el Worker con indicador de progreso), carga de 2 s y persistencia confirmada. Se pasa a la Fase A.

### Resultados parciales de la Fase 0 (Node headless, esquema vacío, 2026-09-30)

- Importan sin errores: `modelo`, `graph_impact`, `risk_engine`, `escenario_engine`, `senal_propagation`, `signal_risk`, `diagnostico_falla`, `linter_topologia`, `riesgo_analogico`, `i18n`, `senal_visual` (Cairo es import diferido).
- `Modelo` se importa en 0,32 s; `construir_grafo()` y `Escenario.crear_nuevo().evaluar()` corren sobre la base vacía.
- Pendiente (necesita el `db.db` real): 0.1, 0.4, 0.6 (comparar resultados con desktop), 0.7 (rendimiento), 0.8 (persistencia en navegador).
- Script reproducible: `ui_web/tests/fase0_headless.mjs` (`npm i pyodide` y `node fase0_headless.mjs`).

## Fase A — Visor de solo lectura (3-4 semanas, ~0,8-1,2M tokens)

Criterio: consulta completa de la instalación desde el navegador.

- [ ] **A.1** `bridge.py`: capa JSON de lectura (equipos, conectores, cables, conexiones, salas, racks, frames, slots, catálogos). Un método por pantalla; sin exponer `Modelo` crudo.
- [x] **A.2** Shell de la app: navegación, i18n (reusar `core/i18n.py`; idiomas es/en/pt), tema, manejo de errores. Hecho (2026-09-30): `ui_web/app.html` + `app/*.js` (rutas por hash, tabla `VISTAS`), i18n desde Python (`i18n_web.py` = `core/i18n.py` + cadenas web; `core/` y `core.zip` sin cambios), tema auto/claro/oscuro, panel de error con reintento y avisos globales. Probado en Node (jsdom + Pyodide real, 47 chequeos); falta la prueba visual en el navegador.
- [ ] **A.3** Árbol de equipos con filtro (cache en memoria, lista virtualizada).
- [ ] **A.4** Ficha de equipo, cable y conector (datos + imágenes con conectores superpuestos, posiciones en %).
- [ ] **A.5** Árbol de conexiones y cadena completa de extensiones.
- [ ] **A.6** Vista de rack, frame/slots y patcheras (solo lectura, SVG).
- [ ] **A.7** Impacto (`GraphImpactAnalyzer`), IRF (`risk_engine`), diagnóstico de falla, linter de topología.
- [ ] **A.8** Escenarios: abrir y evaluar (`escenario_engine.evaluar()`); sin `aplicar_a_infraestructura` todavía.
- [ ] **A.9** Búsqueda global.
- [ ] **A.10** Export/import de `.db` completo y catálogo JSON v2.
- [ ] **A.11** Service worker para uso offline.

## Fase B — ABM completo (6-10 semanas, ~1,5-2,5M tokens)

Criterio: todo lo que hoy se edita por diálogos GTK (~82 diálogos) se edita en web.

- [x] **B.1** Patrón de formulario/diálogo genérico reutilizable (validación, errores, deshacer simple).
- [x] **B.2** Catálogos básicos (marcas, tipos de equipo/conector/cable/ficha, señales, imágenes).
- [x] **B.3** Cables (alta/edición/fusión) y conexiones. Hecho (2026-10-03): `ui_web/cables_web.py` + `app/cables_abm.js`/`cables_modelo.js`, acciones en las fichas de cable y conector y en la lista de cables; detalle en `ui_web/README.md`.
- [x] **B.4** Equipos (ABM, alta rápida con plantilla de conectores) y conectores. Hecho (2026-10-04): `ui_web/equipos_web.py` + `app/equipos_abm.js`/`equipos_modelo.js`, acciones en el árbol de equipos y en las fichas de equipo, conector y cable (incluye «Marcar extremo desconectado», equipo FANTASMA); detalle en `ui_web/README.md`.
- [ ] **B.5** Racks, salas, frames, slots y posición en rack.
- [ ] **B.6** Catálogo de equipos y alta rápida de catálogo.
- [ ] **B.7** Editores masivos (conectores, slots, conexiones).
- [ ] **B.8** Imágenes: subir, asignar, posicionar conectores (selector de coordenadas sobre imagen).
- [ ] **B.9** Patcheras (módulos, PPV/PPA, bandeja, orificios) y ruteo de matriz (`matriz_ruteo`).
- [ ] **B.10** Reglas lógicas AND/OR, problemas, bitácora, auditoría (SLA, cobertura).
- [ ] **B.11** Escenarios: crear/editar y `aplicar_a_infraestructura` con diálogo de confirmación (transacción única).
- [ ] **B.12** Política de escritura: lock de pestaña (D7) y aviso de "base modificada en otra pestaña".

## Fase C — Diagramas editables (5-8 semanas, ~1,2-2M tokens)

Criterio: paridad con los diagramas Cairo de desktop (~8.000 LOC de UI).

- [ ] **C.1** Motor de layout de `DiagramaConexiones` (reusar lógica de `layout_diagrama_ui.py`, portar dibujo a SVG).
- [ ] **C.2** Interacción: zoom/pan, selección múltiple, arrastre de cables (drag-to-connect).
- [ ] **C.3** Capas: impacto, riesgo, señal, ruteo interno, auditoría, búsqueda (los mixins de `ui_gtk/`).
- [ ] **C.4** Diagramas personalizados (`diagrama_guardado*`).
- [ ] **C.5** Vista de señal y `senal_visual` (composición de imágenes).
- [ ] **C.6** Export a SVG/PNG/PDF.
- [ ] **C.7** Planos (`planos_ui`) y dibujo (`dibujo_diagrama_ui`).

## Fuera de alcance (v1)

- `ui_kivy/` y sincronización con Drive (rclone/RoundSync).
- Consola Cypher/Neo4j (ya retirada del desktop).
- Multiusuario concurrente.

## Criterios de corte

- Tras la Fase 0: si el rendimiento o la persistencia no alcanzan → volver a Broadway o Flask.
- Tras la Fase A: evaluar si el visor solo cubre la necesidad antes de invertir en B y C.

## Estimación total

| Fase | Tiempo | Tokens (aprox.) |
|---|---|---|
| 0 | 3-5 días | 150-300k |
| A | 3-4 semanas | 0,8-1,2M |
| B | 6-10 semanas | 1,5-2,5M |
| C | 5-8 semanas | 1,2-2M |
| **Total** | **4-6 meses** | **3-6M** |

Cifras gruesas: dependen del tamaño real del `.db` y de cuánta lógica de negocio
vive dentro de los diálogos GTK.

## Próximo paso

Tarea 0.1 (medir el `db.db` real). Requiere que Pototo confirme el costo estimado.
