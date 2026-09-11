# PROGRESS_REFACTOR.md — Refactor de `pantallas_avanzadas.py`

Seguimiento específico del `plan_refactor_pantallas_avanzadas.md`. Documento
separado de `PROGRESS.md` (que sigue el desarrollo funcional general) para no
mezclar dos historiales con ritmos distintos.

---

## Current Focus

Entrega 6 completada (2026-09-01): `DiagramaConexiones` + sus 4 diálogos
auxiliares salieron a `diagrama_conexiones_ui.py`; `pantallas_avanzadas.py`
queda como fachada 100% pura (145 líneas, cero `class`/`def` propios). El
editor legacy `EditorConexiones` ("modo clásico") se **eliminó del proyecto**
en vez de portarse, a pedido explícito de Papi. Con esto el refactor de
`pantallas_avanzadas.py` (11.032 → 145 líneas) queda **completo**: las 6
entregas están hechas. Falta el smoke test real bajo Xvfb contra el checkout
completo de Papi (pendiente, ver Blockers) y correr la validación de la
Entrega 4 contra `database/db.db` real (arrastrada desde esa entrega, nunca
se hizo).

## Todo List

- [x] Entrega 0 — `pantallas_comunes.py`
- [x] Entrega 1 — `arbol_conexiones_ui.py` + `frame_slots_ui.py`
- [x] Entrega 2 — `imagen_conectores_ui.py` + `rack_ui.py`
- [x] Entrega 3 — `patcheras_ui.py`
- [x] Entrega 4 — `editor_masivo_conectores_ui.py` + `editor_masivo_slots_ui.py` (unificados)
- [x] Entrega 5 — `DiagramaConexiones` → 8 mixins nuevos (`grafo_diagrama_ui.py` y compañía)
- [x] Entrega 6 — `diagrama_conexiones_ui.py` (`DiagramaConexiones` + 4 diálogos) +
      eliminación de `EditorConexiones` legacy + `pantallas_avanzadas.py` como
      fachada pura
- [ ] Correr la batería de validación de la Entrega 4 contra `database/db.db`
      **real** de Papi (acá se usó una BD sintética mínima, ver abajo) —
      sigue pendiente, arrastrada desde esa entrega.
- [ ] Smoke test real bajo Xvfb de la Entrega 6 (instanciación de
      `DiagramaConexiones` desde `diagrama_conexiones_ui.py`) contra el
      checkout completo — no se corrió en esta sesión a pedido de Papi
      (entrega de archivos directa, sin smoke test ni zip en el momento).

---

## Estado general

| Entrega | Contenido | Estado |
|---|---|---|
| 0 | `pantallas_comunes.py` (módulo fundacional) | ✅ Entregado y validado |
| 1 | `arbol_conexiones_ui.py` + `frame_slots_ui.py` | ✅ Entregado y validado |
| 2 | `imagen_conectores_ui.py` + `rack_ui.py` | ✅ Entregado, bug crítico corregido, re-validado |
| 3 | `patcheras_ui.py` | ✅ Entregado y validado |
| **4** | `editor_masivo_conectores_ui.py` + `editor_masivo_slots_ui.py` | ✅ **Entregado y validado en este lote — unificado con clase base, bug preexistente de color corregido, smoke test real bajo Xvfb** |
| 5 | `DiagramaConexiones` → 8 mixins nuevos | ✅ Entregado (ver sección propia abajo) |
| **6** | `diagrama_conexiones_ui.py` (`DiagramaConexiones` + 4 diálogos) + eliminación de `EditorConexiones` legacy + fachada pura | ✅ **Entregado en este lote — ver sección propia abajo** |

---

## Historial condensado (Entregas 0-3)

- **Entrega 0**: extraídas a `pantallas_comunes.py` las utilidades sin lógica
  de negocio compartidas por todo el archivo (`s`, `confirmar`,
  `_pixbuf_from_name`, `_ImagenZoom`, `PALETA`, `_tipo_color`, `_rrect`,
  `_rrect_top`, `_arrow`, luego `_tc`/`_abrev` en la Entrega 2). Validado por
  identidad de objeto, no solo import exitoso.
- **Entrega 1**: `arbol_conexiones_ui.py` (`ArbolConexionesEquipo`) +
  `frame_slots_ui.py` (`VistaFrameSlots`). Bug detectado: se habían arrastrado
  por error dos funciones ajenas (`abrir_coords_imagen`,
  `abrir_imagen_conectores`) al extraer el bloque — corregido y re-validado.
- **Entrega 2**: `imagen_conectores_ui.py` (`CoordenadasImagenSeleccion` +
  `ImagenConectoresYCables`) + `rack_ui.py` (`VistaRack`). **Bug crítico**
  reportado por Papi con screenshots: Patcheras y Diagrama de conexiones
  dejaron de dibujar texto porque `_tc`/`_abrev` viajaron con `VistaRack` sin
  ser exclusivas de ella. Causa raíz: excepciones dentro de callbacks `draw`
  de GTK quedan silenciadas — ni `ast.parse` ni el import real las detectan.
  A partir de acá, **pyflakes es paso obligatorio** en toda entrega.
- **Entrega 3**: `patcheras_ui.py` (`PatcherasVista`). Sin bugs nuevos;
  7 warnings de pyflakes confirmados 100% preexistentes al move (no tocados,
  fuera de alcance).

Detalle completo de cada punto de validación de estas entregas: ver
`changelog.txt` (entradas `2026-08-27T*` y `2026-08-28T01:30`).

---

## Entrega 4 — `editor_masivo_conectores_ui.py` + `editor_masivo_slots_ui.py`

### Decisión de diseño: unificar con clase base (pedido explícito de Papi)

El plan original trataba esto como un move 1:1 puro (igual que las entregas
1-3). Al analizar el bloque a extraer (líneas 5527-7380 de
`pantallas_avanzadas.py`, 1854 líneas) se confirmó por `diff` que:

- `EditorMasivoConectoresImagen` vs `EditorMasivoConectoresCatalogo`: ~95%
  código idéntico línea por línea. Difieren solo en el origen de datos
  (`conector`/`equipo` vs `conector_catalogo`/`equipo_catalogo`), el método
  de guardado, y que la variante de catálogo hace un `UPDATE` extra del
  `id_imagen` del padre al elegir imagen nueva.
- `EditorMasivoSlotsFrame` vs `EditorMasivoSlotsCatalogo`: mismo patrón, con
  una diferencia estructural real (no solo cosmética): el molde nunca tiene
  columna "Equipo" en la tabla de slots.

Se pidió confirmación explícita antes de arrancar (dos opciones: move 1:1
tal cual el plan, o unificar ya) — Papi eligió unificar.

### Qué se hizo

**`editor_masivo_conectores_ui.py`** (nuevo, 445 líneas):
- `EditorMasivoConectoresBase(Gtk.Dialog)` — UI, overlay Cairo, interacción
  (clic para posicionar, avance automático al siguiente conector sin
  posición, clic derecho para quitar), y guardado, todo común.
- Hooks abstractos por subclase: `_cargar_datos()`, `_guardar_uno(id_con, p)`,
  `_post_sel_imagen(id_img)` (no-op por defecto), `_msg_guardado(n)`.
- `EditorMasivoConectoresImagen` (~35 líneas) y
  `EditorMasivoConectoresCatalogo` (~50 líneas) — solo implementan los hooks.
- `_hex_to_rgb` (helper module-level, sin cambios de contenido).

**`editor_masivo_slots_ui.py`** (nuevo, 512 líneas):
- `EditorMasivoSlotsBase(Gtk.Dialog)` — UI, overlay de rectángulos, arrastre
  para dibujar/mover, tamaño recordado entre slots, alta de slot nuevo desde
  el panel, y guardado.
- Diferencia real resuelta con flag de clase `_MOSTRAR_EQUIPO` (True/False):
  controla en `__init__` los índices de columna del `Gtk.ListStore`
  (`_COL_COLOR`/`_COL_X`/`_COL_Y`/`_COL_W`/`_COL_H`/`_COL_TIENE`), usados de
  forma genérica en el resto de la clase — mismo patrón *data-driven* ya
  usado en el resto del proyecto para evitar `if`s dispersos.
- Hooks abstractos: `_cargar_padre()`, `_cargar_slots()`,
  `_actualizar_imagen_padre(id_img)`, `_guardar_nuevo(...)`,
  `_guardar_existente(...)`.
- `EditorMasivoSlotsFrame` (~45 líneas) y `EditorMasivoSlotsCatalogo`
  (~50 líneas).

**`pantallas_avanzadas.py`**: bloque de 1854 líneas reemplazado por un
import de fachada con los 10 nombres (incluidas las 2 clases base, por si
algún consumidor futuro quisiera subclasear). 7.380 → 5.550 líneas.
Cero cambios en el resto del archivo ni en lo que consume `cabledoc.py`.

### Bug preexistente encontrado (no introducido por esta entrega)

En `EditorMasivoConectoresImagen`/`Catalogo` originales: `c["color"]`
guardaba la tupla RGB cruda de `PALETA` (floats 0-1, formato Cairo) tanto en
el dict interno como en la columna `background` del `Gtk.ListStore` — GTK
exige ahí un string. El propio `_dibujar_overlay` ya llamaba
`_hex_to_rgb(c["color"])` esperando un string hex. Nunca se había
instanciado esta clase en runtime en ninguna entrega anterior. Se hubiera
roto con `TypeError` al posicionar el primer conector, o `AttributeError`
en `_hex_to_rgb` al dibujar. **Corregido en la base unificada** — se computa
`hex_c` una sola vez y se usa consistentemente.

### Validación (6 puntos + smoke test real de instanciación)

1. `ast.parse` sobre los 3 archivos tocados — OK.
2. `pyflakes` sobre los 2 archivos nuevos — **cero warnings**.
3. `py_compile` sobre los 3 archivos — OK.
4. `diff` línea por línea de cada clase extraída contra el bloque original,
   confirmando que la única lógica que cambió es la generalización hacia la
   base (además del fix de color).
5. **Import real bajo Xvfb** de los 2 archivos nuevos (se instaló
   `gir1.2-gtk-3.0`, no estaba desde el inicio de esta sesión) contra
   `pantallas_comunes.py` real del proyecto.
6. **Smoke test de instanciación real** (primera vez en todo el refactor que
   se llega a este nivel, no solo import): se armó una base SQLite sintética
   con el esquema real (`equipo`, `conector`, `tipo_conector`, `imagen`,
   `frame`, `slot`, `equipo_catalogo`, `conector_catalogo`,
   `frame_catalogo`, `slot_catalogo` + vistas `VISTA_EQUIPOS`,
   `VISTA_CONECTOR_EDICION`, `VISTA_SLOT_EDICION`) con datos de prueba, y se
   instanciaron bajo `Gtk.init()` real las 4 clases concretas —
   `EditorMasivoConectoresImagen`, `EditorMasivoConectoresCatalogo`,
   `EditorMasivoSlotsFrame`, `EditorMasivoSlotsCatalogo` — verificando
   herencia de la base, cantidad de filas cargadas, preservación de
   coordenadas x/y ya posicionadas, título con el nombre del padre correcto,
   y el comportamiento de `_MOSTRAR_EQUIPO`. **16/16 checks OK.** Fue este
   paso el que encontró el bug de color — ni `ast.parse`, ni `pyflakes`, ni
   el import real lo hubieran detectado (solo se dispara al ejecutar el
   constructor con datos).

**Pendiente**: repetir el smoke test contra `database/db.db` **real** de
Papi en vez de la base sintética — no había copia disponible en este
sandbox (misma limitación de siempre, documentada desde la Entrega 0).

### Archivos entregados en este lote

- `editor_masivo_conectores_ui.py` (nuevo)
- `editor_masivo_slots_ui.py` (nuevo)
- `pantallas_avanzadas.py` (modificado — fachada)
- `cabledoc.py` (`APP_VERSION` → `1.20260830210000`)
- `changelog.txt` (actualizado)
- `PROGRESS_REFACTOR.md` (este archivo)

---

## Latest Blockers/Discoveries

- El sandbox de validación **no trae `python3-gi`/`gir1.2-gtk-3.0`
  preinstalado en cada sesión nueva** — hay que reinstalarlo (`apt-get
  install -y python3-gi gir1.2-gtk-3.0`) antes de poder correr cualquier
  smoke test real. Sin red hacia `database/db.db` de Papi tampoco, así que
  los smoke tests de instanciación se hacen contra una BD sintética mínima
  armada a mano con el esquema real — vale como red de seguridad de
  regresión estructural, pero **no reemplaza** probar con datos reales.
- Confirmado (otra vez) que los bugs que solo se disparan en un callback de
  `draw` o en el constructor de un diálogo con datos reales son invisibles
  a `ast.parse`/`pyflakes`/import — el único método que los encuentra es
  instanciar la clase de verdad. A partir de la Entrega 4 esto pasa a ser
  parte del checklist estándar cuando el bloque a mover incluye una clase
  `Gtk.Dialog` completa (no solo funciones/helpers).

---

## Merge previo a Entrega 5 (2026-08-31)

Antes de arrancar la Entrega 5 se hizo un merge de 3 ramas de sesión que habían
divergido del mismo ancestro común (changelog idéntico hasta 2026-08-27):

- `refactor_etapa4_lista` (esta rama — Entregas 0-4 del refactor de
  `pantallas_avanzadas.py`)
- `funcionalidad_empalme_cables` (Extensión de cable, Fases 1/2/4)
- `funcionalidad_fantasmas` (Extensión Fases 1/2/4 + "Ver cadena completa" +
  alta rápida FANTASMA Parte A — rama más nueva, superset de la anterior)

Confirmado por diff que ninguna de las dos ramas de funcionalidad tocó
`pantallas_avanzadas.py` (ambas dejaron eso fuera de alcance a propósito:
Fase 3 de Extensión y Parte B de FANTASMA, ambas pendientes), así que no hubo
conflicto real con el refactor. Resolución: `cabledoc.py`/`modelo.py` desde
`funcionalidad_fantasmas` (superset); `pantallas_avanzadas.py` +
`editor_masivo_*_ui.py` sin cambios desde esta rama; `extension_cable_ui.py`/
`riesgo_analogico.py`/`schema_db.sql` desde `funcionalidad_empalme_cables`.
`changelog.txt` reconstruido intercalando las 3 colas por timestamp sobre el
prefijo común. `APP_VERSION` → `1.20260831190000`.

**Gap detectado, no resuelto:** el changelog de las ramas de funcionalidad
referencia un cambio en `bitacora_ui.py` (2026-08-28T15:00,
`ZonasSospechosasListado`) de una sesión previa a las 3 ramas fusionadas,
cuyo archivo no vino en ninguno de los 3 zips de esta ronda. No se pudo
fusionar. Si Papi no tiene ya ese archivo aplicado localmente, hace falta
rescatarlo de esa entrega anterior.

Validación: `ast.parse` + `py_compile` sobre los 7 `.py` de la base
fusionada, OK. `pyflakes` sobre `cabledoc.py`/`modelo.py`/
`extension_cable_ui.py`/`riesgo_analogico.py`: sin hallazgos nuevos, todos
los warnings preexistentes ya documentados en entregas anteriores. Import
real de `modelo.py` (puro Python, sin GTK) confirmando que los métodos de
Extensión y de FANTASMA conviven sin colisión de nombres. Verificado a mano
que los imports que hace el `cabledoc.py` fusionado desde
`pantallas_avanzadas` (`abrir_editor_masivo_conectores(_catalogo)`,
`abrir_editor_masivo_slots(_catalogo)`) siguen resolviendo contra la fachada
de la Entrega 4 sin cambio de firma. **No se pudo correr smoke test real
bajo Xvfb de la cadena completa** porque `pantallas_avanzadas.py` importa
6 módulos de entregas anteriores del refactor (`arbol_conexiones_ui`,
`frame_slots_ui`, `imagen_conectores_ui`, `rack_ui`, `patcheras_ui`,
`pantallas_comunes`) que no vinieron en el zip de esta entrega (no fueron
tocados en la Entrega 4, así que no se re-entregaron) — recomendado correr
ese smoke test contra el checkout completo real de Papi antes de dar el
merge por definitivamente cerrado.

## Entrega 5 — HECHA (2026-08-31)

Papi confirmó la agrupación propuesta abajo, con una decisión: si
`_calc_conexion_interna` todavía tenía hardcode pendiente de la migración de
idioma, resolverlo de una al extraer `RuteoInternoMixin` en vez de mover el
problema dos veces. Al leer el método (no solo la memoria/changelog) se
confirmó que **ya estaba migrado** — usa `id_funcion_patchera`/
`funcion_patchera` (Fase C de `plan_desarrollo_funcion_patchera.md`), sin
fallback a prefijo de nombre. No hacía falta tocar lógica, se movió tal cual.

Resultado: 8 archivos nuevos, 70 métodos / ~2840 líneas movidas de
`DiagramaConexiones` (move 1:1, sin cambio de lógica):

- `grafo_diagrama_ui.py` → `GrafoMixin` (8 métodos)
- `dibujo_diagrama_ui.py` → `DibujoMixin` (22 métodos, el más grande)
- `interaccion_diagrama_ui.py` → `InteraccionMixin` (13 métodos)
- `edicion_conexiones_diagrama_ui.py` → `EdicionConexionesMixin` (4 métodos)
- `layout_diagrama_ui.py` → `LayoutMixin` (9 métodos)
- `busqueda_diagrama_ui.py` → `BusquedaMixin` (4 métodos)
- `export_diagrama_ui.py` → `ExportMixin` (4 métodos)
- `ruteo_interno_diagrama_ui.py` → `RuteoInternoMixin` (6 métodos)

`class DiagramaConexiones(...)` ahora compone 15 mixins en total (7 de
entregas anteriores al refactor de `pantallas_avanzadas.py` + estos 8) antes
de `Gtk.Dialog`. Se agregaron imports diferidos (`from pantallas_avanzadas
import ...`) dentro de los 3 métodos que instancian `_BuscadorDiagrama`,
`_DialogoCableRapido` y `_DialogoRuteoMatriz` — esas 3 clases siguen
viviendo en `pantallas_avanzadas.py`, así que hace falta romper el ciclo de
import, mismo patrón que ya usan los otros mixins del proyecto.

Quedaron en `DiagramaConexiones` (sin extraer, como estaba previsto):
`__init__`, el panel de agregar equipo (`_construir_panel_agregar_equipo` y
compañía — candidato a `PanelAgregarMixin` en una entrega futura si hace
falta separarlo), y un puñado de misceláneos de configuración visual
(`_marcar_criticos`, `_on_estilo_menu_toggled`, `_on_jumps_toggled`,
`_on_toggle_solo_nombre`, `_recargar`, `_status`).

`pantallas_avanzadas.py`: 11.032 (baseline) → **2.712 líneas**. Se limpiaron
los imports que quedaron sin uso tras el move (`os`, `random`, `GdkPixbuf`,
`PALETA`, `_tipo_color`, `_rrect`, `_rrect_top`, `_dibujar_icono_buscar`,
`_icono_critico_surface`, `_tc`, `_abrev`) — `math` se mantuvo porque sigue
usado por otra clase del archivo.

Validado: `ast.parse` + `py_compile` + `pyflakes` en los 9 archivos tocados,
sin hallazgos nuevos (los warnings de `pyflakes` que quedan son
preexistentes, confirmados contra el baseline de la Entrega 4 — imports de
re-exportación vía fachada y un par de detalles menores ya documentados, no
introducidos acá). Verificado a mano que los 70 métodos extraídos aparecen
exactamente una vez cada uno en su archivo correspondiente — las
coincidencias de nombre con métodos de otras clases del proyecto (`_cargar`,
`_on_press`, `_on_motion`, etc. en `EditorConexiones`, `editor_masivo_*_ui.py`,
`extension_cable_ui.py`) son metodos independientes de clases distintas, no
duplicados.

**Pendiente, a cargo de Papi:** smoke test real bajo Xvfb contra el checkout
completo (este sandbox no tiene `arbol_conexiones_ui.py`,
`frame_slots_ui.py`, `imagen_conectores_ui.py`, `rack_ui.py`,
`patcheras_ui.py`, `pantallas_comunes.py` — módulos de entregas anteriores
que no cambiaron en esta entrega y por eso no vinieron en el zip).

`APP_VERSION` → `1.20260831234000` (superado por el fix de abajo).

### Fix post-entrega (2026-09-01): `@staticmethod` mal atribuido

Papi reportó, con captura (diagrama de conexiones abriendo en negro, sin
dibujar nada) y traceback real:

```
TypeError: DibujoMixin._draw_conexion_interna() missing 1 required
positional argument: 'cr'
```

**Causa:** bug en el script de extracción de arriba. Al calcular el rango
de líneas de cada método como "desde su `def` hasta la línea anterior al
próximo `def`", cualquier línea de decorador (`@staticmethod`, etc.)
ubicada inmediatamente antes de un `def` quedaba atribuida como línea
final del método *anterior* en el archivo original — no como parte del
método que en realidad decora. Auditado el bloque completo de
`DiagramaConexiones`: sólo había un decorador ahí, el `@staticmethod` de
`_seg_intersect` (más el `@property` de `_DialogoRuteoMatriz`, clase que
nunca se tocó). Ese `@staticmethod` quedó pegado, por el bug, como línea
final de `_sample_path` — que en mi reordenamiento por grupos terminó
justo antes de `_draw_conexion_interna` en `dibujo_diagrama_ui.py` — así
que `_draw_conexion_interna` se llevó un decorador espurio (rompe porque
`self` deja de bindearse implícito y el parámetro `cr` queda sin llenar),
mientras que `_seg_intersect` se quedó sin el suyo.

**Fix**, sólo en `dibujo_diagrama_ui.py`: sacado el `@staticmethod`
espurio de `_draw_conexion_interna`; agregado el `@staticmethod` correcto
a `_seg_intersect`.

**Verificación exhaustiva post-fix:** comparación programática del cuerpo
de los 84 métodos de `DiagramaConexiones` contra su texto exacto en el
`pantallas_avanzadas.py` pre-Entrega-5 — los 81 que no llevan cambio a
propósito coinciden carácter por carácter (los otros 3 sólo difieren por
el import diferido agregado deliberadamente), confirmando que no quedan
más corrupciones de este tipo en ningún otro mixin. Revalidado
`ast.parse` + `py_compile` + `pyflakes` en los 9 archivos, sin hallazgos
nuevos.

**Nota para la próxima extracción de este tipo:** los chequeos estáticos
(`ast.parse`/`py_compile`/`pyflakes`) no detectan este bug — un
`@staticmethod` de más no rompe sintaxis ni genera un import sin usar,
sólo se manifiesta al ejecutar el método real. Antes de dar por buena una
extracción por rango de líneas, conviene auditar decoradores por separado
(buscar todo `^\s*@\w+` en el bloque origen y verificar contra qué `def`
quedó emparejado en el destino) además de correr pyflakes.

`APP_VERSION` final → `1.20260901010000`.

## Entrega 5 — Propuesta original (referencia, ya ejecutada arriba)

`DiagramaConexiones` (líneas 1014-4516 de `pantallas_avanzadas.py`, ~3500
líneas, 91 métodos) ya compone 7 mixins de entregas anteriores al refactor
de `pantallas_avanzadas.py` (`ImpactoMixin`, `RiesgoDiagramaMixin`,
`RiesgoSenalDiagramaMixin`, `SenalDiagramaMixin`, `EscenarioMixin`,
`VistaPreviaMixin`, `DiagnosticoMixin`). Lo que queda es el núcleo propio de
la clase: carga de datos, dibujo Cairo, interacción de mouse/teclado, layout
automático, búsqueda, exportación y ruteo de conexión interna. Propuesta de
8 mixins nuevos (mismo patrón que los 7 existentes — un archivo
`*_mixin.py` o `*_ui.py` por responsabilidad):

1. **`GrafoMixin`** — carga y construcción de nodos/aristas: `_cargar`,
   `_construir_nodo`, `_reconstruir_conexiones`,
   `_conexion_existente_en_puerto`, `_vecinos_de_equipo`,
   `_agregar_vecinos_de`, `_agregar_equipo_por_busqueda`,
   `_agregar_equipo_via_dialogo`.
2. **`DibujoMixin`** — todo el `cr.*` de Cairo: `_on_draw`, `_draw_node`,
   `_draw_conn`, `_draw_badge_critico`, `_draw_wire_en_progreso`,
   `_draw_minimap`, `_minimap_geom`, `_calc_fan_offsets`,
   `_calc_jump_points`, `_seg_intersect`, `_calc_conn_colors`,
   `_sample_path`, `_draw_conexion_interna`, `_draw_conexion_interna_ddv`,
   `_draw_conexion_interna_matriz`, `_dibujar_icono_conexion_incompleta`,
   `_draw_conexiones_incompletas`, `_draw_conexiones_incompletas_etiquetas`.
3. **`InteraccionMixin`** — eventos de mouse/teclado sobre el canvas:
   `_on_press`, `_on_motion`, `_on_release`, `_on_scroll`, `_on_key_global`,
   `_hit_node`, `_hit_puerto`, `_s2w`, `_port_pos`, `_nombre_puerto`,
   `_senal_puerto_bajo_cursor`, `_senal_on_query_tooltip`,
   `_minimap_mover_a`.
4. **`EdicionConexionesMixin`** — alta/baja de wires por drag: 
   `_confirmar_pisar_conexion_wire`, `_eliminar_extremo_conexion_wire`,
   `_cable_incompleto_en_puerto`, `_crear_conexion_wire`.
5. **`LayoutMixin`** — organización automática: `_auto_layout`,
   `_layout_lados_puertos`, `_fit_all`, `_expandir`,
   `_alinear_horizontal`, `_alinear_vertical`,
   `_auto_posicionar_sin_solape`, `_centrar_zoom_inicial_global`,
   `_centrar_en_nodo`.
6. **`BusquedaMixin`** — `_buscar_abrir_dialogo`, `_buscar_navegar`,
   `_buscar_limpiar`, `_buscar_draw_overlay`.
7. **`ExportMixin`** — `_exportar_elegir`, `_exportar`,
   `_exportar_renderizar`, `_exportar_vista`.
8. **`RuteoInternoMixin`** — conexión interna de equipo (matriz/DDV), la
   parte que además queda pendiente del refactor de hardcodes/idioma
   (`_calc_conexion_interna` sigue con la migración a `pantallas_avanzadas.py`
   pendiente según `plan_desarrollo_hardcodes_idioma.md`): 
   `_toggle_conexion_interna`, `_editar_ruteo_matriz_click`,
   `_editar_ruteo_matriz`, `_calc_conexion_interna_matriz`,
   `_calc_conexion_interna`, `_calc_conexion_interna_ddv`.

Quedarían en la clase base (`DiagramaConexiones` propiamente, junto con
`__init__`): el panel de agregar equipo (`_construir_panel_agregar_equipo` y
compañía — es más UI de diálogo que lógica de diagrama, candidato a
`PanelAgregarMixin` si Papi prefiere separarlo también), los toggles de
conexiones incompletas, y un puñado de métodos misceláneos de configuración
visual (`_marcar_criticos`, `_on_estilo_menu_toggled`, `_on_jumps_toggled`,
`_on_toggle_solo_nombre`, `_recargar`, `_status`).

**Ojo con `RuteoInternoMixin`**: toca directamente el trabajo pendiente de
`_calc_conexion_interna` en `pantallas_avanzadas.py` documentado en la
memoria de hardcodes/idioma — separarlo en su propio mixin antes de terminar
esa migración podría ser el momento correcto para resolverla de una, o
podría ser mejor esperar a que esa migración esté cerrada primero para no
mover código dos veces. Pendiente de decisión.

---

## Entrega 6 — HECHA (2026-09-01)

Plan previo guardado en `plans/plan_entrega6_refactor.md` con dos propuestas
(A: mover sólo el legacy; B: fachada 100% pura). Papi confirmó **Propuesta
B**, con una decisión que no estaba en el plan original: **eliminar
`EditorConexiones` en vez de portarlo** ("no portar").

### Qué se hizo

**`diagrama_conexiones_ui.py`** (nuevo, 1694 líneas): último bloque de
clases propias que quedaba en `pantallas_avanzadas.py`, movido 1:1
(confirmado por `diff` línea por línea contra el original, cero cambios de
lógica):
- `_BuscadorDiagrama`, `_DialogoRuteoMatriz`, `_DialogoReglasLogicas` (+
  `abrir_reglas_logicas`), `_DialogoReglasLogicasMolde` (+
  `abrir_reglas_logicas_molde`) — diálogos auxiliares.
- `DiagramaConexiones` (compone los 15 mixins: 7 de entregas anteriores al
  refactor de `pantallas_avanzadas.py` + 8 de la Entrega 5 de este mismo
  refactor) + `abrir_diagrama_conexiones`.
- `_DialogoCableRapido` — se conserva porque sigue en uso real: lo consume
  tanto `EditorConexiones` (eliminado) como `EdicionConexionesMixin` vía
  import diferido desde `edicion_conexiones_diagrama_ui.py`.
- Auditado el único decorador del bloque (`@property` de
  `_DialogoRuteoMatriz.resultado_mapping`) — quedó bien atribuido, sin
  repetir el bug de decoradores de la Entrega 5.

**`EditorConexiones` (editor de nodos custom "modo clásico", ~900 líneas) +
`abrir_editor_conexiones` — ELIMINADOS, no portados.** Confirmado antes de
borrar: el ítem de menú que lo invocaba (`_abrir_editor_conexiones_clasico`
en `cabledoc.py`) estaba deshabilitado desde que "Alta rápida de conexiones"
pasó a reutilizar `DiagramaConexiones` en modo `iniciar_vacio`, y no tenía
otro consumidor en el proyecto.

**`cabledoc.py`**: sacado el import de `abrir_editor_conexiones`, el ítem de
menú "editor clásico" deshabilitado, y el método
`_abrir_editor_conexiones_clasico`; actualizado el docstring de
`_abrir_editor_conexiones` para reflejar la eliminación. `diff` completo
contra el original confirma que sólo se tocaron esas 3 zonas.

**`pantallas_avanzadas.py`**: 2.712 → **145 líneas**, queda como fachada
100% pura (cero `class`/`def` propios, sólo imports/re-exports). Limpieza
adicional, de paso, de imports que ya estaban muertos desde antes de esta
entrega: `GObject`, `IMG_DIR` (import module-level nunca usado en el
archivo), y el bloque de `pantallas_comunes` (`confirmar`,
`_pixbuf_from_name`, `_icono_buscar_surface`, `_ImagenZoom`, `_arrow`) que
sólo usaba el `EditorConexiones` ahora eliminado.

Los 3 imports diferidos que ya existían en los mixins de la Entrega 5
(`from pantallas_avanzadas import _BuscadorDiagrama/_DialogoRuteoMatriz/
_DialogoCableRapido`, en `busqueda_diagrama_ui.py`,
`ruteo_interno_diagrama_ui.py`, `edicion_conexiones_diagrama_ui.py`) **no
se tocaron** — siguen resolviendo sin cambios porque `pantallas_avanzadas.py`
re-exporta esos 3 nombres desde `diagrama_conexiones_ui.py`.

### Validación

1. `ast.parse` + `py_compile` sobre los 3 archivos tocados/nuevos — OK.
2. `pyflakes` sobre `diagrama_conexiones_ui.py` y `pantallas_avanzadas.py` —
   sin hallazgos nuevos; el ruido de "imported but unused" en
   `pantallas_avanzadas.py` es el mismo patrón esperado de fachada que ya
   tenían las Entregas 1-4 (pyflakes no entiende re-exports).
3. `pyflakes` sobre `cabledoc.py` comparado línea por línea contra el
   original: los 5 warnings que quedan son idénticos, preexistentes, sólo
   desplazados por las líneas removidas — nada introducido por esta
   entrega.
4. `diff` línea por línea del bloque movido a `diagrama_conexiones_ui.py`
   contra su ubicación original en `pantallas_avanzadas.py` — idéntico
   carácter por carácter.
5. `diff` completo de `cabledoc.py` contra el original subido — confirma
   que sólo se tocaron las 3 zonas relacionadas al editor clásico.
6. Auditoría de decoradores en el bloque movido (lección de la Entrega 5) —
   sin corrupciones.

**Pendiente, a pedido explícito de Papi en esta sesión:** no se corrió
smoke test real bajo Xvfb (aunque el sandbox sí tenía `Xvfb` instalado esta
vez) ni se armó zip de entrega — los archivos se entregaron directamente
para agilizar, y el cierre (changelog/versión/PROGRESS/zip) se hizo después
en un segundo paso. Smoke test de instanciación real de `DiagramaConexiones`
queda para la próxima sesión, contra el checkout completo de Papi (este
sandbox no tiene los ~13 módulos de entregas anteriores no tocados en ésta:
`arbol_conexiones_ui.py`, `frame_slots_ui.py`, `imagen_conectores_ui.py`,
`rack_ui.py`, `patcheras_ui.py`, `pantallas_comunes.py`, los 8 mixins de la
Entrega 5, `editor_masivo_*_ui.py`, `diagnostico_ui.py`, etc.).

`APP_VERSION` → `1.20260901020000`.

### Archivos entregados en este lote

- `diagrama_conexiones_ui.py` (nuevo)
- `pantallas_avanzadas.py` (modificado — fachada pura)
- `cabledoc.py` (modificado — editor clásico eliminado; `APP_VERSION` →
  `1.20260901020000`)
- `changelog.txt` (actualizado)
- `PROGRESS_REFACTOR.md` (este archivo)
- `plans/plan_entrega6_refactor.md` (plan previo a la implementación)
