# Plan: explotar `ultima_auditoria_fecha` y `fecha_ultima_edicion` (v1)

Sigue a `ui_gtk/help/TUTORIAL_colorear_por_auditoria.md` (el toggle de color
por auditoría, ya en `main` — PR #64). Junta las 6 ideas que surgieron al
revisar esa entrega y las parte en subtareas chicas.

## Principio de división

Cada subtarea de este plan tiene que poder resolverse en **un solo turno de
herramienta de Claude Code** (versión free: contexto y cantidad de llamadas
a herramientas acotados). Eso impone dos reglas duras:

1. **Tocar 1–3 archivos como mucho**, casi siempre ya identificados acá
   (no debería hacer falta que la sesión explore el repo para encontrarlos
   — ese trabajo ya está hecho en este plan).
2. **GTK y Kivy son SIEMPRE subtareas separadas**, nunca "y lo mismo en
   Kivy" al final de la misma tarea. Es la lección de esta misma sesión:
   hacer conexiones+patcheras×GTK+Kivy en un solo turno funcionó, pero fue
   un turno mucho más grande de lo que le pediría a alguien con menos
   contexto/tool-calls disponibles.

Las tareas están agrupadas por función (A–F). **Entre grupos, son
independientes entre sí** — se pueden encargar en cualquier orden, incluso
en paralelo por sesiones distintas. Dentro de un grupo puede haber una
tarea "base" (típicamente Modelo/core) de la que dependen 1–2 tareas de UI;
eso se marca explícito en cada ficha. Ninguna tarea de UI depende de otro
grupo.

Cada ficha sigue el mismo formato: qué hace, qué archivo(s) toca, en qué se
apoya (siempre algo que YA EXISTE, nunca otra tarea de este plan salvo que
se diga lo contrario), y cómo se prueba sin necesitar la base real (mismo
criterio que se usó en todo este hilo: Xvfb + una base de fixture chica).

---

## 0. Lo que ya existe (para no reinventarlo en ninguna subtarea)

| Ya existe | Dónde |
|---|---|
| `Modelo.color_escala_auditoria(fecha)` — escala de color fija, claro→oscuro | `core/modelo.py` |
| `Modelo.devolver_fechas_auditoria_equipos()` — `{id_equipo: fecha}` en una consulta | `core/modelo.py` |
| `Modelo.marcar_auditado(tabla, pk_col, pk_val)` / `devolver_fecha_ultima_auditoria(...)` | `core/modelo.py` |
| `Modelo.TABLAS_AUDITABLES` — equipo, conector, conexion, cable, rack, frame, slot | `core/modelo.py` |
| `Modelo.devolver_pendientes_auditoria()` — cuenta **nunca auditados** por tabla — **completa, pero no la llama ningún archivo de UI todavía** | `core/modelo.py` |
| Patrón de config clave/valor (`config_riesgo_analogico`, tabla `clave TEXT PRIMARY KEY, valor REAL`, con defaults sembrados en `asegurar_tablas_bitacora()`) — mismo patrón a reusar para cualquier config nueva | `core/modelo.py` (~L7908) |
| Decaimiento por antigüedad ya resuelto para riesgo (`factor_decaimiento`, `ventana_meses_incidentes`) — patrón a reusar, no a reinventar | `core/riesgo_analogico.py` |
| Toggle "🕓 Colorear por auditoría" (conexiones GTK/Kivy) y "🕓 Auditoría" (patcheras GTK/Kivy) | `ui_gtk/auditoria_diagrama_ui.py`, `ui_kivy/pantallas_diagrama.py`, `ui_gtk/patcheras_ui.py`, `ui_kivy/pantallas_vistas.py` |
| Exportación de diagrama con fondo transparente + PNG | `ui_gtk/export_diagrama_ui.py` |

---

## Grupo A — Panel de pendientes de auditoría

Idea 3 del resumen. La más barata de todas: la función que cuenta ya
existe, sólo falta mostrarla.

### A1 — GTK: sección "Auditoría" en el panel de Inicio
- **Toca:** `ui_gtk/cabledoc.py` — ahí ya viven, calcados uno del otro,
  "Trabajo pendiente — Cables", "— Equipos", "— Frames" y "— Riesgo de
  señal" (cada uno: un `Gtk.Grid` + una función `_actualizar_panel_
  pendientes_xx()`). Agregar el quinto panel, "— Auditoría", copiando ese
  mismo patrón.
- **Se apoya en:** `Modelo.devolver_pendientes_auditoria()` (ya existe,
  sólo hay que llamarla).
- **Hace:** una fila/sección más con el conteo de "nunca auditados" por
  tabla (al menos equipo; el resto es directo si da el tiempo) y un botón
  que abre el listado ya filtrado.
- **Prueba:** fixture con 2 equipos auditados y 1 sin auditar → el panel
  muestra "1 pendiente"; click abre el listado con exactamente ese equipo.
- **Depende de:** nada.

### A2 — Kivy: misma sección en la pantalla Inicio mobile
- **Toca:** `ui_kivy/main.py` — mismo panel "Trabajo pendiente" pero del
  lado mobile.
- **Se apoya en:** lo mismo que A1.
- **Independiente de A1** (no comparten código de UI).

---

## Grupo B — "Editado sin volver a auditar"

Idea 1. Un equipo con `fecha_ultima_edicion > ultima_auditoria_fecha` es
una bandera que hoy no existe en ningún lado: alguien cambió el dato en el
sistema sin confirmar que la realidad física lo acompaña.

### B1 — Modelo: función de detección (base del grupo)
- **Toca:** sólo `core/modelo.py`.
- **Hace:** `Modelo.devolver_editados_sin_auditar(tabla="equipo")` — filas
  donde `fecha_ultima_edicion` es más nueva que `ultima_auditoria_fecha`
  (o esta última es NULL). Devuelve algo simple: lista de ids, o dict
  `id → {fecha_edicion, fecha_auditoria}`.
- **Prueba:** 3 filas de fixture (editado-después / auditado-después /
  nunca auditado) → sólo las dos primeras categorías aparecen, con los
  datos correctos.
- **Depende de:** nada.

### B2 — GTK: badge en el listado de Equipos
- **Toca:** el archivo del listado/tabla de Equipos en `ui_gtk/` (una
  columna o ícono nuevo, no una pantalla nueva).
- **Se apoya en:** B1.
- **Depende de:** B1 (no se puede hacer sin la función de datos).

### B3 — Kivy: mismo badge en el listado de Equipos mobile
- **Toca:** el archivo del listado de Equipos en `ui_kivy/`.
- **Se apoya en:** B1.
- **Depende de:** B1. **Independiente de B2** (UI separada).

---

## Grupo C — Eje de riesgo "antigüedad de auditoría"

Idea 2. Sumar la falta de auditoría como un componente más del score de
riesgo ya existente, reusando el decaimiento que `riesgo_analogico.py` ya
resolvió para incidentes.

### C1 — core: función de cálculo aislada (base del grupo)
- **Toca:** sólo `core/riesgo_analogico.py`.
- **Hace:** una función que devuelve el componente "antigüedad de
  auditoría" (0..1 o el rango que use el resto del motor) para un
  `id_equipo`, con la MISMA fórmula de decaimiento que ya usan los
  incidentes (ventana configurable, no una constante nueva de cero).
  **A propósito NO se integra al score total todavía** — sólo se define y
  se prueba sola, para que la tarea quede chica.
- **Prueba:** un equipo auditado hoy da 0 (o el mínimo); uno nunca
  auditado da el máximo; uno a mitad de la ventana da un valor
  intermedio coherente.
- **Depende de:** nada.

### C2 — core: integrar el componente al score total + peso configurable
- **Toca:** `core/riesgo_analogico.py` (fórmula del total) y la siembra de
  defaults de `config_riesgo_analogico` en `core/modelo.py` (una clave
  nueva, ej. `peso_antiguedad_auditoria`, mismo patrón que
  `peso_incidente`).
- **Se apoya en:** C1.
- **Depende de:** C1.

### C3 — GTK: mostrar el componente en el desglose de riesgo
- **Toca:** el tooltip/panel donde hoy se desglosa el riesgo por eje en
  `ui_gtk/` (agregar una línea, no una pantalla nueva).
- **Depende de:** C2 (necesita que el componente ya esté en el score).

### C4 — Kivy: mismo desglose mobile
- **Toca:** el equivalente en `ui_kivy/`.
- **Depende de:** C2. **Independiente de C3.**

---

## Grupo D — Reporte de cobertura de auditoría por sala/rack

Idea 4. Mirar el sistema completo con una métrica de gestión ("% auditado
en los últimos N días"), no equipo por equipo.

### D1 — Modelo: consulta de cobertura agregada (base del grupo)
- **Toca:** sólo `core/modelo.py`.
- **Hace:** `Modelo.devolver_cobertura_auditoria(dias=90)` — por sala (o
  por rack, lo que salga más directo de la consulta existente de
  ubicación de equipos): total de equipos, cuántos auditados dentro de
  `dias`, porcentaje.
- **Prueba:** fixture con 2 salas, distinta proporción de equipos
  auditados recientes en cada una → los porcentajes calculados a mano
  coinciden.
- **Depende de:** nada.

### D2 — GTK: pantalla/diálogo de reporte
- **Toca:** un archivo nuevo y chico en `ui_gtk/` (una tabla simple,
  sala/rack + porcentaje + contador, sin gráficos).
- **Se apoya en:** D1.
- **Depende de:** D1.

### D3 — Kivy: misma pantalla mobile
- **Toca:** un archivo nuevo en `ui_kivy/`.
- **Depende de:** D1. **Independiente de D2.**

---

## Grupo E — SLA de auditoría (vencidos según política)

Idea 5, la más ambiciosa de las seis — por eso la que más se beneficia de
ir en subtareas chicas. Sin infraestructura de notificaciones push (la app
es de escritorio/mobile local, no hay servidor); "alerta" acá significa
"contador/color distinto en las pantallas que ya existen", no un push.

### E1 — Modelo+schema: config del SLA (base del grupo)
- **Toca:** sólo `core/modelo.py`.
- **Hace:** tabla `config_auditoria` — **mismo DDL y mismo patrón que
  `config_riesgo_analogico`** (`clave TEXT PRIMARY KEY, valor REAL`, con
  un default sembrado, ej. `dias_sla_auditoria: 90.0`), más
  `devolver_config_auditoria()` / `establecer_config_auditoria(clave,
  valor)` calcados de `devolver_config_riesgo_analogico` /
  `establecer_config_riesgo_analogico`. Un solo valor global para
  arrancar (no por tipo de equipo — eso, si hace falta, es una vuelta
  aparte más adelante).
- **Prueba:** sin config previa, `devolver_config_auditoria()` trae el
  default; `establecer_config_auditoria("dias_sla_auditoria", 60.0)` lo
  actualiza y la siguiente lectura lo refleja.
- **Depende de:** nada.

### E2 — Modelo: función de "vencidos según SLA"
- **Toca:** sólo `core/modelo.py`.
- **Hace:** `Modelo.devolver_vencidos_sla_auditoria()` — equipos donde
  `ultima_auditoria_fecha` es más vieja que `dias_sla_auditoria` (leído de
  E1), o nunca auditados.
- **Se apoya en:** E1.
- **Depende de:** E1.

### E3 — GTK: contador de vencidos en el panel de Inicio + UI para
cambiar el SLA
- **Toca:** el mismo panel de A1 (agregar una fila más, no una pantalla
  nueva) + un campo numérico en algún diálogo de preferencias existente
  para `establecer_config_auditoria`.
- **Se apoya en:** E2 (y comparte pantalla con A1, aunque no requiere que
  A1 esté hecho — si A1 no existe todavía, esta tarea agrega la sección de
  auditoría al panel ella misma).
- **Depende de:** E2.

### E4 — Kivy: mismo en mobile
- **Toca:** el equivalente de E3 en `ui_kivy/`.
- **Depende de:** E2. **Independiente de E3.**

### E5 — (opcional) Tercer tono en la escala de color para "vencido SLA"
- **Toca:** `core/modelo.py` (`color_escala_auditoria` u otra función
  nueva al lado) + los 4 puntos donde ya se usa (`auditoria_diagrama_ui.py`,
  `pantallas_diagrama.py`, `patcheras_ui.py`, `pantallas_vistas.py`) —
  **cambia sólo el color, no la estructura del toggle que ya existe.**
- **Se apoya en:** E1/E2 y en el toggle ya construido (PR #64).
- **Depende de:** E2. Es la única tarea de este plan que toca los 4
  archivos del toggle a la vez — si se quiere más chica, partirla en 4
  (una por archivo) como se hizo con el toggle original.

---

## Grupo F — Estado de auditoría en la exportación del diagrama

Idea 6. La más autocontenida de todas: no toca `core/modelo.py`.

### F1 — GTK: pie de página con la fecha de exportación cuando el toggle
está activo
- **Toca:** `ui_gtk/export_diagrama_ui.py` (una línea de texto dibujada
  al pie del PNG/SVG/PDF exportado, sólo cuando
  `self._auditoria_color_activo` es `True` — el mixin ya existe).
- **Se apoya en:** `AuditoriaDiagramaMixin` (PR #64) y `ExportMixin` (ya
  existente).
- **Prueba:** exportar con el toggle apagado → sin cambios (regresión);
  con el toggle prendido → el archivo exportado trae el texto.
- **Depende de:** nada nuevo (ambos mixins ya están en `main`).
- No hay F2 (Kivy): el diagrama de conexiones mobile no tiene exportación
  a archivo hoy, así que no hay dónde agregar el pie de página todavía.

---

## Resumen

| ID | Grupo | Qué hace | Toca | Depende de |
|---|---|---|---|---|
| A1 | Panel pendientes | Sección Auditoría en Inicio (GTK) | 1 archivo `ui_gtk/` | — |
| A2 | Panel pendientes | Ídem, Kivy | 1 archivo `ui_kivy/` | — |
| B1 | Editado sin auditar | `devolver_editados_sin_auditar` | `core/modelo.py` | — |
| B2 | Editado sin auditar | Badge en listado Equipos (GTK) | 1 archivo `ui_gtk/` | B1 |
| B3 | Editado sin auditar | Ídem, Kivy | 1 archivo `ui_kivy/` | B1 |
| C1 | Riesgo | Componente de cálculo aislado | `core/riesgo_analogico.py` | — |
| C2 | Riesgo | Wiring al score total + peso | `core/riesgo_analogico.py` + `core/modelo.py` | C1 |
| C3 | Riesgo | Desglose visual (GTK) | 1 archivo `ui_gtk/` | C2 |
| C4 | Riesgo | Ídem, Kivy | 1 archivo `ui_kivy/` | C2 |
| D1 | Cobertura | `devolver_cobertura_auditoria` | `core/modelo.py` | — |
| D2 | Cobertura | Pantalla de reporte (GTK) | 1 archivo nuevo `ui_gtk/` | D1 |
| D3 | Cobertura | Ídem, Kivy | 1 archivo nuevo `ui_kivy/` | D1 |
| E1 | SLA | Tabla + config del SLA | `core/modelo.py` | — |
| E2 | SLA | `devolver_vencidos_sla_auditoria` | `core/modelo.py` | E1 |
| E3 | SLA | Contador + UI de config (GTK) | 1–2 archivos `ui_gtk/` | E2 |
| E4 | SLA | Ídem, Kivy | 1–2 archivos `ui_kivy/` | E2 |
| E5 | SLA | 3er tono de color "vencido SLA" | 4 archivos del toggle | E2 |
| F1 | Exportación | Pie de página en export (GTK) | `ui_gtk/export_diagrama_ui.py` | — |

18 subtareas. Las de la columna "Depende de: —" (A1, A2, B1, C1, D1, E1,
F1 — 7 en total) se pueden encarar en cualquier momento, sin esperar nada.

## Orden sugerido (no obligatorio)

Por costo/beneficio, no por dependencia — las dependencias reales están
en la tabla de arriba:

1. **A1 + A2** — más baratas de todo el plan, la función ya existe.
2. **B1 → B2 / B3** — chico y el hallazgo (editado sin auditar) es de los
   más accionables.
3. **F1** — autocontenida, no toca `core/modelo.py`.
4. **D1 → D2 / D3** — útil para reportar hacia afuera del equipo técnico.
5. **E1 → E2 → E3 / E4 → (E5 opcional)** — la más grande, dejarla para el
   final o repartirla en varias sesiones.
6. **C1 → C2 → C3 / C4** — la que más entrelaza con código existente
   (motor de riesgo), conviene encararla con el resto del plan ya
   asentado.
