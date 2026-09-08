# CableDoc — Contexto unificado del proyecto

> Documento consolidado a partir de `context.txt` del proyecto y de las memorias registradas en las distintas cuentas/sesiones de trabajo (Fede/Pepe/Pototo/Papi). Actualizado sabiendo que **las 6 etapas del refactor de `pantallas_avanzadas.py` ya fueron completadas**.

---

## 1. Propósito y contexto

CableDoc es una aplicación de escritorio **Python 3 + GTK3 (PyGObject)** para documentar y analizar el cableado y el flujo de señal de una instalación de broadcast/AV real (video full digital, cadena de audio analógica envejecida). Gestiona la infraestructura física: equipos, conectores, cables, conexiones, racks, frames, slots, patcheras (patch bays), matrices y entidades de señal.

El desarrollo está guiado por casos reales encontrados durante relevamientos de campo de cableado, y en particular por el diagnóstico de fallas recurrentes de audio trazables a debilidades de la cadena analógica.

- **Origen**: predecesor en VB.NET/WinForms, portado íntegramente a Python/GTK3 (existe un artículo técnico LaTeX/PDF de ~26 páginas comparando ambas arquitecturas). La vista `CONEXIONES_AMBOS_EXTREMOS` sobrevive de esa era.
- **Licencia**: GNU GPL v2, autor "fschpp".
- **Idioma del código**: español en su totalidad (UI, vocabulario de dominio, changelog, comentarios). Soporta i18n hacia inglés y portugués vía pipeline basado en AST (`auto_wrap.py`, `i18n.py`).
- **Base de datos**: SQLite (`database/db.db`), ~44 tablas, 14 vistas SQL.
- **Renderizado**: Cairo (reemplazó a Graphviz).
- **Motor de grafos**: GraphQLite (extensión SQLite en Rust/C con soporte de consultas Cypher), usado por `graph_impact.py` (clase `GraphImpactAnalyzer`). También existe una vía histórica por Neo4j/`cypher_console.py`.
- **Puerto móvil**: Kivy/Pydroid 3 (Android), reutiliza `modelo.py` e `i18n.py` sin cambios; sincronización desktop↔Google Drive vía rclone, y Android↔Google Drive vía RoundSync.

### Vocabulario de dominio clave

`equipo`, `conector`, `conexion`, `cable`, `sala`, `rack`, `frame`, `slot`, `patchera` (MODULO PATCHERA, PPV/PPA, bandeja, orificio 3/UR), `tipo_equipo` (DDV, MATRIZ, FANTASMA, ENRUTADOR, REFOUT, etc.), `rol_senal` (PATCHERA/ENRUTADOR/FANTASMA/REFOUT), `fila_patchera` (A_BACK/B_BACK/A_FRONT/B_FRONT), `matriz_ruteo`, `senal_en_conector`, `senal_linaje` (documental, no alimenta el motor de impacto), `reglas_por_equipo`/`regla_logica` (compuertas AND/OR, p. ej. DSK), `origen` (MANUAL/PROPAGADA), `bitácora de incidentes`, `zona sospechosa`, `riesgo analógico`, `armado`, IRF (Índice de Riesgo de Falla), `Extensión de cable` (empalme directo punta-a-punta, distinto de "Empalme" = barril/coupler).

### Arquitectura de la UI

Patrón de **composición por mixins**: clases de pantalla grandes como `DiagramaConexiones` se arman a partir de múltiples clases `*Mixin` (`ImpactoMixin`, `RiesgoDiagramaMixin`, `SenalDiagramaMixin`, `GrafoMixin`, `DibujoMixin`, `RuteoInternoMixin`, entre otras).

### Archivos principales

| Archivo | Rol |
|---|---|
| `cabledoc.py` | UI principal / ABM / punto de entrada (históricamente monolítico, ~9.200–11.000 líneas; refactor en curso hacia ~10 módulos de dominio) |
| `pantallas_avanzadas.py` | Pantallas visuales avanzadas, diagramas Cairo, `DiagramaConexiones` (refactor de 6 etapas **completado**, ver §3) |
| `modelo.py` | Capa de datos, clase única `Modelo` (~5.800+ líneas; refactor a mixins planeado) |
| `graph_impact.py` | Análisis de impacto/propagación de fallas (`GraphImpactAnalyzer`, GraphQLite) |
| `senal_propagation.py` | Propagación de señal |
| `riesgo_analogico.py` | Analizador de riesgo analógico (scoring por decaimiento lineal) |
| `risk_engine.py` / `riesgo_diagrama_ui.py` | IRF (Índice de Riesgo de Falla) |
| `senal_visual.py` | Motor de compositing/resolución visual |
| `impacto_ui.py`, `diagrama_personalizado.py`, `acerca_de.py`, `bitacora_ui.py`, `escenario_ui.py`/`escenario_engine.py`, `diagnostico_ui.py`/`diagnostico_falla.py`, `cypher_console.py`, `i18n.py` | Módulos UI/soporte especializados |
| `schema_db.sql` | Esquema de base de datos |

---

## 2. Estado actual del proyecto (consolidado)

*Datos de changelog a agosto 2026:* ~414 equipos, 35 de tipo FANTASMA.

### Subsistemas ya entregados

- **IRF (Índice de Riesgo de Falla)**: `risk_engine.py`, `riesgo_diagrama_ui.py`; tablas `parametro_riesgo`, `riesgo_equipo_cache`.
- **Reglas lógicas** AND/OR por equipo/tipo (compuertas tipo DSK): tablas `regla_logica`, `regla_logica_miembro`, `regla_logica_salida`; integradas a `graph_impact.py`.
- **Tracking de problemas de equipo**: tablas `categoria_problema`, `problema_equipo`.
- **Catálogo con export/import JSON**: formato v2 (pool de imágenes deduplicado) evolucionado a **v4** (tras el refactor de hardcodes, ver abajo).
- **Vista global de patcheras**: todas las columnas de patch del sistema sin necesidad de seleccionar equipo.
- **Diagramas personalizados**: `diagrama_personalizado.py`, tablas `diagrama_guardado/_nodo/_conexion`, mecánica de arrastrar-para-conectar.
- **Ruteo de matrices**: tabla `matriz_ruteo`, `_DialogoRuteoMatriz`, asignaciones persistidas. Modelado a nivel de conector (no de equipo) para simular correctamente cortes internos, incluyendo resolución recursiva para matrices en cascada (`_cables_ruteados_desde`).
- **Exclusión de FANTASMA en impacto**: `equipos_impactados` resta correctamente el set de equipos FANTASMA (bug de "cómputo muerto" corregido: el set se calculaba pero no se restaba).
- **Columnas nuevas en `equipo`**: `fecha_fabricacion`, `es_equipo_usado`, `ultima_auditoria_fecha`, `picon`.
- **Bitácora de incidentes y riesgo analógico** (Entrega 1, fases A–C): tablas `incidente`, `zona_sospechosa`, `config_riesgo_analogico`, columnas de calidad de cableado en `conector`/`cable`; `riesgo_analogico.py` con scoring por decaimiento lineal; UI en `bitacora_ui.py`.
- **FANTASMA — quick action (Parte A, 2026-08-30)**: surgió de una entrevista de relevamiento, no de un bug. Botón "🔌 Marcar extremo desconectado" + mini-diálogo `_DialogoEligeLadoFantasma` en la ficha de cable (deshabilitado si el cable ya tiene 2 puntas); con 1 extremo ya cargado infiere el lado opuesto automáticamente (A↔B, OUT↔IN) sin preguntar, genera el nombre del equipo FANTASMA sin tipeo manual, y crea equipo+conector+conexión en un solo paso sin pedir Marca/Modelo/Inventario/Serie — encadena `_DialogoEquipo`/`_DialogoConector` existentes para ubicación en plano y foto de ficha. 4 métodos nuevos en `modelo.py`, entre ellos `devolver_id_tipo_equipo_fantasma()` (busca por `rol_senal='FANTASMA'`, no por nombre) y `devolver_id_tipo_conector_por_nombre()` (deliberadamente NO usa `tipo_conector.direccion`, ver gotcha de esa columna en "Otros trabajos en curso"). Código validado solo con `ast.parse`/`py_compile` — Xvfb pendiente a pedido explícito del usuario.
- **Extensión de cable — "Ver cadena completa"**: `resolver_cadena_extension(id_cable)` en `modelo.py` recorre la cadena bidireccionalmente; `CadenaExtensionDialog` y `abrir_ver_cadena()` en `extension_cable_ui.py`, accesible desde el listado de extensiones, el detalle de cable y auto-mostrado tras crear/editar. Tutorial `tutorial_extension_cable.md` actualizado con ejemplo real (DDA 04 ESTUDIO → cadena de monitor Roland, cables 3773/3774/3775).
- **Hardcodes/idioma — fases 1, 4 y 7**: reemplazo de inferencia por texto libre con columnas de control dedicadas: `tipo_conector.direccion`, `tipo_conector.es_referencia_generada`, `conector.fila_patchera`, `rol_senal` con CHECK constraint ampliado; además `funcion_patchera` (tabla) + `id_funcion_patchera` (FK en `conector`) y reescritura del bypass de patchera en `senal_propagation.py`. Export de catálogo bump a formato v4.
- **"Acerca de…"**: `acerca_de.py`, módulo standalone.
- **Traducción masiva de UI a inglés/portugués (2026-08-25)**: corregido un diccionario `_PALABRAS_AUTOMATICAS` duplicado/mal cerrado en `i18n.py` que rompía la sintaxis del módulo; agregadas ~150+ traducciones nuevas cubriendo prácticamente todos los archivos `*_ui.py` + `cabledoc.py`/`pantallas_avanzadas.py`/`cypher_console.py`. **Bug bloqueante encontrado y corregido en la misma pasada**: 9-10 archivos (`impacto_ui.py`, `escenario_ui.py`, `riesgo_diagrama_ui.py`, `senal_diagrama_ui.py`, `senal_visual_ui.py`, `diagnostico_ui.py`, `signal_risk_diagrama_ui.py`, `bitacora_ui.py`, `diagrama_personalizado.py`, `cypher_console.py`) usaban `_()` sin importar `i18n`, provocando `NameError` real al abrir esas pantallas — corregido con el patrón try/except de import ya usado en el resto del proyecto. También se agregó **reinicio automático de la app al cambiar de idioma** (`VentanaPrincipal._cambiar_idioma`/`_reiniciar_aplicacion`, vía `GLib.idle_add` + `subprocess.Popen`), reemplazando el reinicio manual que se pedía antes. Sigue vigente el ítem de "on the horizon" de reaplicar el pipeline de i18n a cada feature nueva que se desarrolle de acá en adelante.
- **`pantallas_comunes.py`** (Entrega 0 del refactor de `pantallas_avanzadas.py`): utilidades compartidas, bootstrap de i18n, helpers de íconos, `_ImagenZoom`, `PALETA`, primitivas de dibujo Cairo.

### Refactor de `pantallas_avanzadas.py` — **COMPLETADO (Etapas 1–6)**

El archivo, originalmente de **~11.032 líneas**, fue dividido en módulos focalizados siguiendo `plan_refactor_pantallas_avanzadas.md`, con patrón de **facade** (las clases extraídas se re-exportan desde `pantallas_avanzadas.py` para que `cabledoc.py` y `diagrama_personalizado.py` no requieran cambios).

- **Entrega 0**: `pantallas_comunes.py` (utilidades compartidas, i18n, íconos, `_ImagenZoom`, `PALETA`, primitivas Cairo).
- **Entregas 1–2**: `arbol_conexiones_ui.py`, `frame_slots_ui.py`, `imagen_conectores_ui.py` (~558 líneas), `rack_ui.py` (~816 líneas). Lección de Entrega 2: helpers Cairo `_tc`/`_abrev` mal co-ubicados con `VistaRack` (también los necesitaban `PatcherasVista` y `DiagramaConexiones`) → movidos a `pantallas_comunes.py`. Bug de pyflakes detectado en esta etapa estableció que **pyflakes es obligatorio** (no lo capturan `ast.parse` ni `py_compile` solos).
- **Entrega 3**: `PatcherasVista` y `abrir_patcheras` extraídos a `patcheras_ui.py`. Archivo reducido de 8.865 a 7.380 líneas.
- **Entrega 4**: `editor_masivo_conectores_ui.py` y `editor_masivo_slots_ui.py`, con clases base abstractas para deduplicar pares ~95% idénticos (equipo real vs. catálogo). Archivo reducido a ~5.550 líneas vía facade.
- **Etapa 5**: ~70 métodos (~2.840 líneas) extraídos de `DiagramaConexiones` a 8 mixins nuevos: `grafo_diagrama_ui.py`, `dibujo_diagrama_ui.py`, `interaccion_diagrama_ui.py`, `edicion_conexiones_diagrama_ui.py`, `layout_diagrama_ui.py`, `busqueda_diagrama_ui.py`, `export_diagrama_ui.py`, `ruteo_interno_diagrama_ui.py`. Archivo reducido de ~11.032 a **~2.712 líneas**. Bug post-entrega: un `@staticmethod` mal atribuido durante la extracción por rangos de líneas terminó como decorador espurio en `_draw_conexion_interna` (`dibujo_diagrama_ui.py`) — corregido, y se hizo verificación carácter por carácter de los 84 métodos de `DiagramaConexiones`.
- **Etapa 6**: ✅ **completada** — cierra el refactor de `pantallas_avanzadas.py` planificado en `plan_refactor_pantallas_avanzadas.md`.

> Fusión de tres ramas realizada antes de la Etapa 5, resolviendo `refactor_etapa4_lista`, `funcionalidad_empalme_cables` y `funcionalidad_fantasmas`. **Gap de `bitacora_ui.py` — aclarado (no es una feature faltante, es un archivo perdido):** `ZonasSospechosasListado` **sí fue implementada y validada por completo** el 2026-08-28T15:00 (clase nueva en `bitacora_ui.py` + ítem de menú "📋 Zonas sospechosas (bitácora)" en Catálogos de `cabledoc.py`, `APP_VERSION` → `1.20260828150000`), resolviendo un bug real reportado por Papi (zonas sospechosas creadas sin equipo asociado quedaban invisibles desde la UI, aunque estuvieran correctamente guardadas en `db.db`). El problema es que esa entrega quedó fuera de los tres zips que se fusionaron después — hay que **rescatarla de esa sesión anterior** (2026-08-28), no reimplementarla desde cero. De paso quedó anotado que `_DialogoConfigRiesgoAnalogico`/`abrir_config_riesgo_analogico` (ajuste de ventana de meses/pesos/cortes BAJO-MEDIO-ALTO) sigue sin estar enganchado a ningún menú — candidato natural: un botón dentro de `ZonasSospechosasListado`, cuando se retome.

### Otros trabajos en curso / recientes

- **Diagrama de conexiones (`DiagramaConexiones`)**:
  - Botón de auto-layout ("🧲 Auto-organizar nodos") en modo `iniciar_vacio=True`: separación iterativa de rectángulos (AABB), solo en memoria (`self._nodos`), sin persistencia en DB.
  - Atajo Ctrl+E → "Expandir vecinos", generalizado para operar sobre todos los nodos seleccionados (`self._sel_ids`) con deduplicación de vecinos compartidos.
  - Panel de equipos (`_chk_panel_agregar`) restringido a modo `iniciar_vacio=True`.
  - Rol dinámico `<ASIGNADO POR MATRIZ>` en composiciones visuales modo KEY: el slot BASE sigue el `matriz_ruteo` vivo en cada pasada de composición vía `_entrada_por_matriz()`; condicionado a `rol_senal == 'ENRUTADOR'`, nunca a nombres de tipo hardcodeados ni a la sola presencia de filas en `matriz_ruteo`.
  - Checkbox "Traer con equipos conectados" integrado (tildado por defecto; al agregar un equipo por primera vez trae también sus vecinos IN/OUT ya conectados, mismo patrón visual de apilado que el editor clásico).
  - **"Alta rápida de conexiones" (menú Cableado) migrada del editor de nodos custom `EditorConexiones` a `DiagramaConexiones(iniciar_vacio=True)`** (2026-08-26): panel lateral "Agregar equipo" con búsqueda + drag&drop real (GTK DnD). `EditorConexiones` queda en el código pero deshabilitado en el menú (ítem "editor clásico" con `set_sensitive(False)`), sin decidir todavía si se elimina.
  - **Arrastre de cable puerto-a-puerto: implementado** (`_hit_puerto`, `_crear_conexion_wire`, `_draw_wire_en_progreso`, etc. en `DiagramaConexiones`), reutilizando el popup `_DialogoCableRapido` existente. Código validado solo con `py_compile`/`ast.parse` (Xvfb pendiente a pedido explícito del usuario). **Caso no replicado del editor clásico:** si el puerto de ORIGEN ya tenía una conexión, el editor viejo "movía" ese extremo; la versión nueva siempre AGREGA una conexión nueva al conector de origen — puede duplicar cables en un conector ya ocupado si el arrastre parte de ahí sin querer.
  - **Reutilización automática de cable incompleto al completar con drag&drop**: si "Mostrar todas las conexiones incompletas" está activo y se arrastra desde/hacia un conector con una punta pendiente, se reusa ese `id_cable` en vez de crear uno nuevo. Caso borde (ambos extremos del arrastre tienen conexión incompleta) no se resuelve automático — se avisa por la barra de estado y no se hace nada.
  - **"Mostrar todas las conexiones incompletas"** (checkbox en Ver, además de la variante histórica "por equipo seleccionado", mutuamente excluyentes entre sí): una sola consulta batch sobre todos los equipos visibles del diagrama; escalonado vertical de tramos superpuestos contado por equipo, no global.
  - Plan no implementado: overlay "🚧 Conexiones incompletas" con ícono propio de "destino desconocido" (distinto del checkbox de arriba, que ya dibuja los tramos — este overlay sería una variante visual con ícono dedicado). Preguntas abiertas: ícono (cartel de obra adaptado vs. cono estilo VLC), segmento punteado vs. sólido, y si el alcance queda solo-vista.
- **Fusión de rama "avance"**: 10 archivos (incluye `NameError` por imports de i18n faltantes) fusionados con la rama de desarrollo de `pantallas_avanzadas.py`/`cabledoc.py`; 13 archivos afectados validados con `py_compile`/`ast.parse`.
- **Bug crítico de clasificación IN/OUT — corregido (2026-08-25)**: `EditorConexiones._crear_nodo/_vecinos_de_equipo` y `DiagramaConexiones._cargar_nodo/_reconstruir_conexiones` usaban `COALESCE(tc.direccion,'OUT')`, así que cualquier conector sin `direccion` poblada caía por defecto a OUT — las líneas de conexión a puertos IN se dibujaban apuntando al centro del nodo. Fix en 2 pasadas: primero se leyó `tc.direccion` directo con fallback al nombre del *tipo* de conector; como eso no alcanzaba (nombres de tipo como "BNC"/"XLR" rara vez dicen IN/OUT), se agregó un segundo fallback sobre el **nombre del conector individual** con palabras clave multi-idioma (IN/INPUT/ENTRADA/ENTRY/INGRESS vs. OUT/OUTPUT/SALIDA/EXIT/EGRESS). **Importante para código nuevo:** la columna `tipo_conector.direccion` no es 100% confiable todavía — se pobló durante la migración de hardcodes con un criterio laxo (`%OUT%` en el nombre del tipo) que hoy clasifica como `'IN'` varios tipos que no lo son (OTRO, CONECTOR SUPERIOR, GPI/O, etc.). Por eso el alta rápida de FANTASMA (ver abajo) deliberadamente NO usa `direccion` para inferir el lado A/B, solo el nombre exacto del tipo de conector.
- **Vista Previa / Analizar Impacto / Modo Escenario — exclusión mutua resuelta en los 3 sentidos** (cerrado en la fusión de ramas del 2026-08-26, después de haber quedado "a medias" en una sesión anterior): activar cualquiera de los tres ya no apaga a los otros dos — antes sólo se había tocado `impacto_ui._imp_on_activar`; ahora también `senal_visual_ui._visp_activar` y `escenario_ui._esc_activar_modo` dejan de desactivarse entre sí. El orden de prioridad de clic en `_on_press()` de `DiagramaConexiones` (Escenario → Diagnóstico → Vista Previa → Impacto → Señal → buscador) es lo que arbitra cuál gana un clic sobre un puerto cuando dos modos coinciden — no hace falta lógica de exclusión adicional. Caveat pendiente, no bloqueante: el sub-modo "Reconectar virtualmente" de Escenario puede verse interceptado por un clic de Vista Previa si ambos están activos a la vez.
- **Migración de coordenadas de imagen**: evaluación de pasar de coordenadas en píxeles a porcentuales (independientes de resolución, medidas desde arriba-izquierda) — plan no finalizado.
- **Bug de mosaico compuesto**: registros de la tabla `imagen` probablemente aún referencian rutas JPG originales mientras los archivos físicos fueron convertidos a PNG (Cairo solo soporta PNG nativamente vía `create_from_png`).
- **Bug abierto — `VentanaTexto`** (visor de changelog): scrollbars y botón X no funcionales; refactor de `Gtk.Window` a `Gtk.Dialog` quedó a mitad de camino.

---

## 3. Próximos pasos (on the horizon)

- **Extensión de cable**: implementar las 5 fases planificadas completas (schema, CRUD, UI, propagación, render en diagrama, bitácora, peso de riesgo). Smoke test obligatorio en el entorno real antes de cerrar la ronda de "Ver cadena completa".
- **FANTASMA**: limpieza de huérfanos (prompt de confirmación al reconectar equipo real) — planeado, no implementado.
- **Hardcodes/idioma**: fases 2, 3, 5, 6, 8, 9 pendientes (cubren `graph_impact.py`, `pantallas_avanzadas.py`, `senal_propagation.py`, migración REFOUT/FANTASMA, UI de matriz de ruteo, cambios visuales/color, validación final). Revisión de `_calc_conexion_interna` pendiente.
- **Refactor de `modelo.py`**: conversión de métodos `@staticmethod`, división de la clase única `Modelo` en mixins.
- **Refactor de `cabledoc.py`**: división en ~10 módulos de dominio; `cables_conexiones_ui.py` priorizado como próxima entrega para habilitar el desarrollo de Extensión en un archivo más chico.
- **Gap de `bitacora_ui.py`**: resolver la ausencia de `ZonasSospechosasListado` en los branches fusionados.
- **Riesgo estructural de señal**: Entrega 2 del sistema de incidentes/riesgo — integrar `plan_riesgo_senal_audio.md`, conectando `riesgo_analogico.py` con `signal_risk.py` (balance/atenuación/ancho de banda).
- **Generalización de patcheras**: `rol_patchera` a nivel catálogo (`tipo_conector`), `orden_patchera` en `conector`; generalizar UI de ruteo de matriz a todo equipo con `rol_senal == 'ENRUTADOR'`.
- **Equipos críticos**: tabla/UI `equipo_critico` (multi-selección en diagrama → marcar crítico → afecta el denominador del IRF en `risk_engine.py`).
- Completar arrastre de cable puerto-a-puerto en `DiagramaConexiones`.
- Implementar overlay "🚧 Conexiones incompletas" (pendiente de definiciones de Pepe/Fede).
- Completar export de `picon` al JSON de catálogo.
- Fix `VentanaTexto` → `Gtk.Dialog` (scrollbars + botón cerrar).
- Feature de propagación semántica de señales (combiners/DSK generan señales nombradas; un corte upstream propaga la pérdida semánticamente).
- Feature `<ASIGNADO POR MATRIZ>` — extender a otras estrategias visuales (columna `via_matriz` en `estrategia_visual_miembro`).
- Revisión PDF de CableDoc desde perspectiva de usuario final (no técnica, foco operativo) — solicitada, no entregada aún.
- Reaplicar el pipeline de i18n a las features nuevas desarrolladas sin traducciones (workflow recurrente, no tarea única).

---

## 4. Aprendizajes y principios clave

**Anti-hardcodes / catálogo como fuente de verdad**
- Nunca hardcodear nombres o IDs de tipo de equipo (p. ej. "SWITCHER", "KUMO") en lógica de negocio. Usar siempre `tipo_equipo.rol_senal == 'ENRUTADOR'` vía `Modelo.devolver_rol_senal_tipo_equipo()` para identificar equipos router/matriz — aplica universalmente.
- Comportamiento nuevo se declara en catálogo (`tipo_conector`, `tipo_equipo`), no se infiere de nombres o aritmética. Nuevos tipos de patchera deben poder agregarse solo desde el ABM.
- El mecanismo `rol_senal` es el modelo a extender, no a esquivar — usar columnas explícitas en DB con resolución por `COALESCE()`, no comparar campos de texto libre contra strings hardcodeadas en español/inglés.
- Conectores TRS no son clasificables por tipo físico solo (estéreo-desbalanceado vs. mono-balanceado depende de la implementación por equipo) → requiere columnas de override por instancia.
- Conectores REFIN se tratan equivalentes a IN en el editor de reglas lógicas.

**Semántica de dominio**
- FANTASMA = ausencia confirmada en campo, no "desconocido" ni "fuera de alcance". Análogo a un "miembro fantasma". La propagación ya lo maneja correctamente — no requiere casos especiales adicionales.
- Extensión ≠ Empalme: "Empalme" ya se usa para casos de barril/coupler en el modelo de datos; la nueva entidad para conexión directa punta-a-punta debe usar terminología "Extensión".
- El bypass de patchera modela comportamiento de jack full-normal: A_BACK↔B_BACK activo cuando no hay cables en el frente, roto cuando A_FRONT o B_FRONT tiene cable — implementado vía `_calc_conexion_interna`, no heurísticas de prefijo de nombre.
- `id_conector=0` es un sentinel real en la base de datos (representa cable desconectado). `if id_conector:` evalúa `False` para ese valor — todo chequeo de ID de conector debe usar `if id_conector is not None`.
- Módulos de patchera deben modelarse como 4 nodos de puerto distintos (no un solo paso-directo), o el análisis de impacto de señal falla silenciosamente.
- Conflictos entre `matriz_ruteo` y `reglas_por_equipo` pueden causar silenciosamente que equipo aguas abajo aparezca como "sin señal" — chequear ante resultados inesperados de análisis de impacto.
- `senal_linaje` es solo documental y **no** alimenta el motor de impacto (`graph_impact.py`) — esta separación debe preservarse.

**Modelado de grafo / impacto**
- Modelos de grafo a nivel de equipo (nodo único) fallan para dispositivos con ruteo interno — MATRIZ requiere modelado a nivel de conector, no de equipo, para simular flujo de señal con precisión.
- Resolución recursiva necesaria cuando la salida de una MATRIZ alimenta la entrada de otra (no alcanza con lookup de un solo nivel).
- `simular_falla_equipo()` y `simular_desconexion()` tienen semánticas distintas — cambios en una no necesariamente aplican a la otra (la primera corta todas las conexiones a la vez, por lo que el ruteo interno es irrelevante en ese escenario).
- `equipos_impactados` excluye intencionalmente el equipo cuya propia regla lógica se cayó; el campo `conectores_regla_caida` (a nivel conector) en los dataclasses de resultado es la forma correcta de resaltar el culpable específico sin contaminar incorrectamente otros conectores del mismo equipo.
- Nodos mock usan claves de texto estables (`mock:<clave_nodo>:<clave_puerto>`) independientes de IDs autoincrementales, para sobrevivir ciclos de borrado+reinserción.
- "Cómputo muerto" (dead computation) es un bug silencioso a auditar: un valor correctamente calculado pero nunca conectado al resultado final (ocurrió con el set de equipos FANTASMA en `equipos_impactados`).

**Refactor / extracción de código**
- Patrón facade: módulos extraídos re-exportan sus nombres a través del archivo original, para que los imports externos (`from cabledoc import X`, `from pantallas_avanzadas import X`) sigan funcionando sin cambios.
- Extracción basada en rangos de líneas es frágil: puede mal-atribuir decoradores (p. ej. `@staticmethod`) al método incorrecto — la verificación post-extracción contra el fuente es esencial.
- Diferencias de comportamiento genuinas entre clases similares deben preservarse en subclases, no forzarse a una base compartida — documentar asimetrías en docstrings y changelog.
- Deduplicación de pares de clases ~95% idénticas: unificar con clase base + hooks, no copiar-pegar.
- Los imports diferidos dentro del cuerpo de métodos (para instanciar `_BuscadorDiagrama`, `_DialogoCableRapido`, `_DialogoRuteoMatriz`, etc.) son el patrón establecido del proyecto para romper dependencias circulares entre `cabledoc.py` ↔ `pantallas_avanzadas.py` ↔ `*_ui.py` — debe preservarse en cualquier refactor.
- Helpers compartidos deben auditarse por uso cruzado oculto entre clases antes de moverlos junto con la clase con la que conviven físicamente en el archivo original.
- `senal_linaje` y otras separaciones de responsabilidad deliberadas no deben "arreglarse" sin entender el motivo original.

**Validación**
- **pyflakes es obligatorio, no opcional** — es la única herramienta que detecta `NameError` dentro de callbacks de dibujo de GTK, que GTK silencia (produce superficies negras / nodos faltantes en vez de un crash). Ni `ast.parse` ni pruebas de import chain bajo Xvfb lo detectan.
- Checklist de validación por entrega (más estricta, post-incidente Entrega 2): `ast.parse` → `pyflakes` (cero warnings) → `py_compile` → diff línea a línea → import real bajo Xvfb → instanciación de clases GTK contra SQLite sintético (obligatoria para cualquier `Gtk.Dialog` completo).
- Stack mínimo vigente: `ast.parse` + `python3 -m py_compile` para sintaxis; Xvfb con render GTK real para runtime — **Fede corre los smoke tests de Xvfb por su cuenta y no quiere que Claude los intente.**
- Smoke testing en el entorno real es requerido antes de cerrar cualquier ronda de feature o iniciar la siguiente entrega de refactor — la validación de sandbox es necesaria pero no suficiente.
- GraphQLite no es instalable fuera del entorno local del usuario, por lo que las pruebas end-to-end deben correrse en la máquina real.

**Base de datos**
- Migraciones idempotentes: patrón `asegurar_tablas_*` / `ALTER TABLE ... IF NOT EXISTS`.
- `_conn_ctx()` para escrituras, `_query()` para lecturas.
- `with Modelo._conn() as conn:` **no** cierra la conexión en Python (solo hace commit/rollback) — usar un `_conn_ctx()` propiamente implementado como context manager.
- No hay acceso a la base real (`database/db.db`) desde el sandbox — las pruebas con datos reales las corre el usuario en su entorno.
- Testing siempre sobre una **copia** de `database/db.db`, nunca el archivo real.

**GTK / UI**
- `Gtk.ListStore.append()` falla silenciosamente si la fila tiene más valores que columnas definidas.
- `Gtk.Label(markup=...)` como argumento de constructor no soportado en versiones viejas de PyGObject — usar `set_markup()`.
- `flags=` en el constructor de `Gtk.Dialog` está deprecado — usar `modal=True, destroy_with_parent=True`.
- `get_action_area()` deprecado — agregar botones a `get_content_area()`.
- `Cairo.select_font_face()` weight solo admite 0 (NORMAL) o 1 (BOLD), no valores tipo CSS.
- Bug de color RGB en `Gtk.ListStore`: tuplas Cairo (floats 0–1) fallan en columnas `background` que requieren strings hex.
- `Gdk.Event.new()` no es confiable para eventos de mouse sintéticos en PyGObject — usar `_MockEvent` con atributos Python planos.
- `Gtk.Window` para ventanas secundarias es poco confiable para scrollbars/comportamiento de cierre — preferir `Gtk.Dialog`.
- Performance de `TreeView`: insertar y podar nodos en cada tecleo genera churn masivo → filtrar en Python sobre un cache en memoria e insertar solo los nodos visibles una vez (4–19ms vs. 10–22s). La cadena `TreeModelSort` debe reconstruirse completa en el coloreado de filas: store → filtro_model → sort_model → tv.
- Llamadas por-nodo para chequear flags (p. ej. `tiene_regla_logica_efectiva`) deben reemplazarse por consultas batch (p. ej. `equipos_con_regla_logica_activa()`) para evitar regresiones de varios segundos al cargar el diagrama.

---

## 5. Enfoque de trabajo (approach & patterns)

- Comunicación **concisa y directa, en español**.
- Preferencia por recibir **archivos modificados individuales** antes que documentación — changelog/progress son secundarios, solo si hay tiempo dentro de la sesión.
- **Archivos individuales**, no archivos zip, como entregable (establecido después de la Etapa 5).
- Alcance explícito: no tocar archivos fuera de lo pedido.
- Sesiones de roleplay analista/cliente para relevar requisitos antes de implementar — Claude debe leer el código primero para no preguntar cosas ya respondibles desde el código.
- Planes de desarrollo como documentos markdown estructurados antes de implementar (convención `plan_*.md`), guardados en `plans/`.
- Progreso trackeado en `PROGRESS.md` / `PROGRESS_REFACTOR.md`; cambios documentados en `changelog.txt` con timestamp ISO, una línea por cambio (formato `YYYY-MM-DDTHH:MM archivo (scope): descripción`).
- `APP_VERSION` en `cabledoc.py` (formato `1.YYYYMMDDHHMMSS`) se actualiza en cada entrega.
- "Continuar" como palabra clave para avanzar procesos multi-paso sin repetir contexto.
- Un ítem de refactor riesgoso por sesión.
- Ayuda documentada en `help/TUTORIAL_*.md`, actualizada junto con cada feature de cara al usuario.
- Entregas de refactor solo con los archivos tocados (para no pisar desarrollo paralelo en la máquina real del usuario); riesgo de que los archivos en vivo sean más nuevos/grandes que los últimos subidos — requiere ediciones puntuales o confirmación explícita de superset.

---

## 6. Herramientas y recursos

- **Lenguaje/stack**: Python 3, GTK3/PyGObject, Cairo, SQLite.
- **Grafos**: GraphQLite (extensión SQLite Rust/C con Cypher); histórico Neo4j vía `cypher_console.py`.
- **Validación**: `ast.parse`, `pyflakes` (obligatorio), `python3 -m py_compile`, `sqlite3` CLI, Xvfb + GTK real (en el entorno del usuario; no disponible en sandbox).
- **i18n**: `auto_wrap.py` (wrapper de strings basado en AST), `i18n.py` (diccionarios por idioma).
- **Sync**: rclone (desktop → Google Drive), RoundSync (Android → Google Drive).
- **Móvil**: puerto Kivy/Pydroid 3 (Android), pyjnius para modo inmersivo.
- **Calidad de código**: jscpd para detección de clones (`jscpd --min-lines 8 --min-tokens 50 --reporters json --output . .`).
- **Documentación técnica**: LaTeX/pdflatex.
- **Tracking**: `PROGRESS.md`, `PROGRESS_REFACTOR.md`, `changelog.txt`.
- **Documentos de planificación**: `plan_refactor_pantallas_avanzadas.md` *(✅ completado, etapas 1–6)*, `plan_refactor_cabledoc.py`, `plan_refactor_modelo.md`, `plan_desarrollo_extension_cable.md`, `plan_desarrollo_fantasma_rapido.md`, `plan_desarrollo_hardcodes_idioma.md` (9 fases, 1/4/7 completadas), `plan_desarrollo_funcion_patchera.md`, `plan_riesgo_senal_audio.md`, `informe_hardcodes_idioma.md`.
- **Entrega de archivos**: individuales a `/mnt/user-data/outputs/` (no zips, salvo pedido explícito).
