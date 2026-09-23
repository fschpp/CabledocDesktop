# Plan: portar la Bitácora de Incidentes a Kivy (v1)

Nace de `plan_auditoria_fecha_edicion_v1.md`, grupo C (riesgo por antigüedad
de auditoría): C4 (Kivy) no tenía dónde colgarse — a diferencia de C3 (GTK),
que sólo necesitó un panel nuevo en un diálogo ya existente
(`BitacoraIncidentesListado`), en `ui_kivy/` **no existe ninguna bitácora de
incidentes todavía** (`grep` de "incidente"/"bitacora" en `ui_kivy/*.py` da
cero resultados). Portarla es un proyecto en sí mismo, así que se separa de
`plan_auditoria_fecha_edicion_v1.md` en este plan aparte. C4 queda re-
etiquetada como **K4** acá (ver Grupo K).

## Principio de división

Mismo criterio que `plan_auditoria_fecha_edicion_v1.md`: cada subtarea
resoluble en un solo turno de herramienta de Claude Code (versión free),
tocando 1–3 archivos ya identificados en este plan. A diferencia de aquel
plan, acá **todas** las subtareas son Kivy (no hay contraparte GTK que
portar — GTK ya tiene la bitácora completa desde antes) — la división es
por capa (widget base → diálogos → listado → integración), no por
plataforma.

---

## 0. Lo que ya existe (para no reinventarlo en ninguna subtarea)

| Ya existe | Dónde |
|---|---|
| Schema + CRUD completo de incidentes/zonas (`crear_incidente`, `modificar_incidente`, `eliminar_incidente`, `devolver_todos_los_incidentes`, `devolver_incidente`, `crear_zona_sospechosa`, `renombrar_zona_sospechosa`, `eliminar_zona`, `devolver_zonas`, `devolver_zona`, `asignar_equipo_a_zona`, `quitar_equipo_de_zona`, `devolver_equipos_de_zona`, `devolver_equipos_de_incidente`, `devolver_cables_de_incidente`, `devolver_zonas_de_incidente`) | `core/modelo.py` — compartido, **nada que portar acá** |
| `RiesgoAnalogicoAnalyzer` (score/nivel/detalle "zona caliente"), incluido el componente de antigüedad de auditoría (C1/C2) | `core/riesgo_analogico.py` — puro Python, sin `gi`, usable tal cual desde Kivy |
| `_DialogoZonaSospechosa`, `_DialogoElegirZona`, `_DialogoIncidente`, `BitacoraIncidentesListado`, `abrir_bitacora_incidentes`, `ZonasSospechosasListado`, `abrir_zonas_sospechosas`, `_DialogoConfigRiesgoAnalogico`, `abrir_config_riesgo_analogico` — implementación de referencia completa a espejar | `ui_gtk/bitacora_ui.py` |
| Panel "🌡 Riesgo analógico" agregado a `BitacoraIncidentesListado` (plan_auditoria_fecha_edicion_v1.md, C3) — llama `RiesgoAnalogicoAnalyzer().detalle_de(tipo, id_)` y lista `r.detalle` | `ui_gtk/bitacora_ui.py` |
| `ListadoPopup` — listado genérico con filtro + CRUD, **selección simple** (`modo_seleccion=True`), equivalente táctil de `VentanaListado` (GTK) | `ui_kivy/widgets_base.py` |
| `barra_superior_dialogo`, `grid_formulario`/`fila_etiqueta`/`fila_entry`, `FilaAccion` (fila ícono+título+subtítulo+chevron), `Tarjeta` | `ui_kivy/widgets_base.py` |
| Tab "Acciones rápidas" de `DialogoEquipo`, con `FilaAccion` por cada acceso ("Ver conectores", "Ver patcheras", "Diagrama de conexiones", etc.) — mismo lugar donde cuelga cualquier acceso nuevo por equipo | `ui_kivy/pantallas_equipos.py` (~L789-825) |
| **No existe:** ningún selector múltiple (chips + agregar/quitar) equivalente a `_SelectorMultiple` (GTK) — `ListadoPopup` sólo resuelve selección simple. Bloqueante para K2/K3. |

---

## Grupo K — Bitácora de incidentes (Kivy)

### K1 — Selector múltiple reutilizable (base del grupo)
- **Toca:** sólo `ui_kivy/widgets_base.py`.
- **Hace:** un widget chico (`SelectorMultiple` o similar) — fila de chips
  con nombre + botón "✖" para quitar, más un botón "➕ Agregar…" que abre
  `ListadoPopup` en `modo_seleccion=True` y agrega el resultado a la lista.
  Expone `ids` (lista de str) y un callback `on_cambio`. Equivalente táctil
  de `_SelectorMultiple` (GTK, `ui_gtk/bitacora_ui.py` L52-114) — mismo
  contrato (lista de ids + nombres para mostrar), UI adaptada a chips en
  vez de `Gtk.ListBox` con botón quitar por fila.
- **Se apoya en:** `ListadoPopup` (ya existe, `modo_seleccion=True`).
- **Prueba:** instanciar con una lista de 2 equipos de fixture, agregar un
  tercero vía el popup, quitar el primero → `ids` queda con los 2
  esperados en cada paso.
- **Depende de:** nada.

### K2 — Zona sospechosa: alta/edición + selector de zona
- **Toca:** archivo nuevo `ui_kivy/pantallas_bitacora.py`.
- **Hace:** `DialogoZonaSospechosa(Popup)` (nombre + `SelectorMultiple` de
  equipos de la zona, usa `Modelo.asignar_equipo_a_zona`/
  `quitar_equipo_de_zona`) y `DialogoElegirZona(Popup)` (listado simple de
  zonas + botón "➕ Nueva…" que abre el anterior) — equivalentes de
  `_DialogoZonaSospechosa` / `_DialogoElegirZona` (GTK, L115-252).
- **Se apoya en:** K1 (para el selector de equipos de la zona) y
  `Modelo.crear_zona_sospechosa`/`devolver_zonas`/`devolver_zona` (ya
  existen).
- **Prueba:** crear una zona con 2 equipos de fixture → aparece en
  `Modelo.devolver_zonas()` con `n_equipos=2`; abrir `DialogoElegirZona` la
  muestra en el listado.
- **Depende de:** K1.

### K3 — Diálogo de incidente (alta/edición)
- **Toca:** `ui_kivy/pantallas_bitacora.py`.
- **Hace:** `DialogoIncidente(Popup)` — formulario fecha/hora, resumen,
  relato, estado (spinner) + tres `SelectorMultiple` (equipos, cables,
  zonas — el de zonas usa `DialogoElegirZona` de K2 como popup de
  agregado). Al guardar llama `Modelo.crear_incidente`/
  `Modelo.modificar_incidente`. Equivalente de `_DialogoIncidente` (GTK,
  L253-401).
- **Se apoya en:** K1 (equipos/cables) y K2 (zonas).
- **Prueba:** crear un incidente con 1 equipo + 1 cable de fixture, sin
  zona → `Modelo.devolver_incidente(id)` y
  `devolver_equipos_de_incidente`/`devolver_cables_de_incidente` devuelven
  exactamente eso.
- **Depende de:** K1, K2.

### K4 — Listado de incidentes + panel "🌡 Riesgo analógico"
- **Toca:** `ui_kivy/pantallas_bitacora.py`.
- **Hace:** `ListadoIncidentes(ListadoPopup)` — subclase de `ListadoPopup`
  (`cargar_datos`/`nuevo`/`editar`/`eliminar` sobre `Modelo.
  devolver_todos_los_incidentes`/`crear_incidente` vía K3/`eliminar_
  incidente`), parametrizable por `id_equipo`/`id_cable`/`id_zona` (mismo
  filtro que `BitacoraIncidentesListado`, GTK L402-521). Arriba del
  listado, un panel de texto con el desglose de
  `RiesgoAnalogicoAnalyzer().detalle_de(tipo, id_)` — **mismo código que
  el panel agregado en `ui_gtk/bitacora_ui.py` por
  `plan_auditoria_fecha_edicion_v1.md` C3**, sin lógica nueva: la línea de
  antigüedad de auditoría ya viene incluida en `r.detalle` gracias a C2,
  igual que en GTK. Esta ficha **es** C4 de aquel plan.
- **Se apoya en:** `ListadoPopup`, K3, `RiesgoAnalogicoAnalyzer` (ya
  existe en `core/`, sin cambios).
- **Prueba:** fixture con 2 incidentes de un equipo, uno de ellos con el
  equipo sin auditar hace tiempo → el listado muestra los 2 incidentes y
  el panel de riesgo incluye la línea "Sin auditar hace N día(s)" o
  "Nunca auditado" según corresponda (mismo criterio que la prueba de C2).
- **Depende de:** K3.

### K5 — Listado de zonas sospechosas (entrada independiente)
- **Toca:** `ui_kivy/pantallas_bitacora.py`.
- **Hace:** `ListadoZonasSospechosas(ListadoPopup)` — punto de entrada
  general (no colgado de un equipo/cable puntual), con botón "📋 Ver
  incidentes" por zona que abre K4 filtrado por `id_zona`. Equivalente de
  `ZonasSospechosasListado` (GTK, L528-641).
- **Se apoya en:** K2, K4.
- **Depende de:** K4.

### K6 — Integración: botón "📋 Ver incidentes" en Equipos y Cables
- **Toca:** `ui_kivy/pantallas_equipos.py` (tab "Acciones rápidas" de
  `DialogoEquipo`, ~L799-821 — agregar una `FilaAccion` más a la lista
  `acciones`) y el archivo equivalente de detalle de Cable en
  `ui_kivy/pantallas_cables.py` (confirmar en esta misma subtarea el
  nombre exacto de la clase/tab, análoga a `DialogoEquipo`).
- **Hace:** cada botón abre K4 (`ListadoIncidentes`) filtrado por
  `id_equipo`/`id_cable` — mismo patrón que el botón "📋 Ver incidentes"
  ya integrado en `ui_gtk/equipos_ui.py`/`ui_gtk/cables_conexiones_ui.py`.
- **Se apoya en:** K4.
- **Depende de:** K4.

### K7 — (opcional) Configuración del score de riesgo analógico
- **Toca:** archivo de preferencias/config ya existente en `ui_kivy/` (a
  identificar en esta misma subtarea — revisar si hay una pantalla de
  Ajustes/Preferencias general, o si conviene un `Popup` propio colgado
  de otro punto de entrada) + `ui_kivy/pantallas_bitacora.py`.
- **Hace:** formulario para `Modelo.devolver_config_riesgo_analogico`/
  `establecer_config_riesgo_analogico` (incluida la nueva clave
  `peso_antiguedad_auditoria` de C2), calcado de
  `_DialogoConfigRiesgoAnalogico` (GTK, L688-733).
- **Se apoya en:** nada nuevo (`Modelo` ya expone todo).
- **Depende de:** nada — independiente del resto del grupo, se puede
  encarar en paralelo. Marcado opcional porque el score ya funciona con
  sus defaults sin esta pantalla; sólo bloquea poder *ajustar* los pesos
  desde mobile.

---

## Resumen

| ID | Qué hace | Toca | Depende de |
|---|---|---|---|
| K1 | Selector múltiple reutilizable | `ui_kivy/widgets_base.py` | — |
| K2 | Zona sospechosa: alta/edición + selector | `ui_kivy/pantallas_bitacora.py` (nuevo) | K1 |
| K3 | Diálogo de incidente | `ui_kivy/pantallas_bitacora.py` | K1, K2 |
| K4 | Listado de incidentes + panel de riesgo (= C4) | `ui_kivy/pantallas_bitacora.py` | K3 |
| K5 | Listado de zonas sospechosas | `ui_kivy/pantallas_bitacora.py` | K4 |
| K6 | Integración en Equipos/Cables | `pantallas_equipos.py` + `pantallas_cables.py` | K4 |
| K7 | (opcional) Config del score | archivo de config a identificar + `pantallas_bitacora.py` | — |

7 subtareas, todas en cadena salvo K7 (independiente). Orden obligatorio
por dependencia: **K1 → K2 → K3 → K4 → (K5 y K6 en paralelo)**; K7 en
cualquier momento.
