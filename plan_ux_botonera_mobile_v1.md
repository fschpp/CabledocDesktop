# Plan UX/UI Mobile — Botonera inferior y navegación (v1)

**Sombrero:** UI/UX mobile + cliente final (usuario de campo con el celular en una mano y un cable en la otra).
**Fuente:** estado real de `fschpp/CabledocDesktop` rama `main` (clonado y relevado para este documento, no el README viejo).
**Alcance:** `ui_kivy/main.py`, `ui_kivy/tema.py` (BarraInferior), y como hallazgo colateral, la toolbar de `ui_kivy/pantallas_diagrama.py`. No toca `core/`.

---

## 0. Qué relevé antes de opinar

Cloné `main` y miré el código real, no solo capturas:

- La barra inferior actual (`main.py`, `CableDocApp.on_start`) tiene 5 ítems fijos:
  **Inicio · Equipos · (+) · Buscar · Más**.
- El botón **+** abre siempre el mismo popup de 3 opciones (Alta rápida de equipo / Nuevo Cable / Nueva Conexión), sin importar en qué pantalla estás parado.
- **"Más"** abre un popup con 8 grupos y **24 ítems** (`_abrir_menu_completo()`): Buscar, Equipos, Cableado, Infraestructura (6 ítems, incluye Planos), Catálogos (6), Diagramas (4), Preferencias, Aplicación — todos con el mismo peso visual, sin orden por frecuencia de uso.
- La pantalla **Inicio** ya tiene: 4 tarjetas de stats (Equipos/Cables/Conexiones/Racks), una grilla de **9 accesos rápidos** (Buscar, Equipos, Cables, Conexiones, Patcheras, Racks, Vista Rack, Frames, Diagrama) y 2 paneles de "trabajo pendiente" (Cables: Temporales/En revisión/1 extremo/Sin conexión; Equipos: 6 métricas más).
- Es decir: **"Equipos" y "Buscar" ya están a un toque desde Inicio**, y además "Buscar" también vive en la barra superior global. La barra inferior les da un lugar fijo y permanente a dos accesos que ya sobran en otros lados, mientras que **Cables** y **Conexiones** —que son justamente los datos que el propio panel de "pendientes" te está gritando que atiendas (18 temporales, cables sin conexión, etc.)— no tienen lugar fijo y quedan a 2 toques (Más → Cableado → Cables).
- Hallazgo colateral, no pedido pero relevante para "botonera": la pantalla `DiagramaConexiones` (la más potente de la app: diagnóstico, riesgo, escenarios, señal) tiene una **toolbar de ~25 botones en una sola fila con scroll horizontal** (Encuadrar, Expandir, Recargar, Solo nombre, Conexión interna, 🩺 Diagnóstico, 📋 Historial, 🧪 Escenario, 🔗 Reconectar, 🆕 Esc., 📂 Abrir, 💾 Guardar, ▶ Aplicar, 🗑 Descartar, 📡 Señal, 🎨 Leyenda, 🎨 Riesgo equipo, 🎨 Riesgo señal, 🔺 Simular falla, 🖼 Vista previa, Zoom, +, −, PNG). Es la misma enfermedad que la del menú "Más", pero peor: acá ni siquiera hay una etiqueta de grupo, es una fila plana.
- Los íconos disponibles hoy en `assets/iconos/` (generados por `generar_iconos.py`) son: `inicio, buscar, equipos, cables, conexiones, patchera, racks, vista_rack, frame, diagrama, imagen, conector, arbol, ubicacion, filtro, editar, eliminar, guardar, cerrar, ver, atras, menu, mas, mas_vertical, plus, chevron_derecha, tema, lupa_check`. No hay ícono propio para "Salas", "Planos" ni para los modos de Diagrama (diagnóstico/riesgo/escenario/señal), que hoy usan emoji Unicode directo en el texto del botón (🩺 🧪 📡 🎨 🔺) — funciona en desktop pero es justo el tipo de glifo que `generar_iconos.py` fue creado para evitar en Pydroid 3 (ver docstring de ese archivo: "Reemplazan a los glifos Unicode... que no se ven en Pydroid 3"). Esto es una inconsistencia entre módulos: `pantallas_diagrama.py` no siguió la misma convención que el resto de la app.

---

## 1. Diagnóstico (cliente + UX mobile)

Si yo fuera el usuario en campo, con una mano ocupada:

1. **La barra inferior no refleja lo que hago todos los días.** Según el propio dashboard de "pendientes" que ya construiste, lo que se revisa a diario es Cables (temporales, sin conexión) y, en segundo lugar, Conexiones. Hoy esos dos están detrás de "Más".
2. **Redundancia que cuesta espacio real.** "Buscar" está en 3 lugares (barra superior derecha, grilla de accesos rápidos, barra inferior) y "Equipos" en 2 (accesos rápidos + barra inferior). En una barra de solo 5 slots, eso es 40-60% del espacio fijo gastado en algo que ya es accesible en 1 toque desde Inicio.
3. **El "+" no sabe dónde estás parado.** Estás editando un Cable y tocás "+": te ofrece "Alta rápida de equipo" primero. Es un menú de app, no un menú de pantalla.
4. **La info de "pendientes" se pierde en cuanto salís de Inicio.** Invertiste en calcular "18 temporales" — pero si estoy en Cables mirando la lista, no hay ningún indicador visual (badge) de que hay temporales pendientes; hay que volver a Inicio para acordarse del número.
5. **"Más" es un cajón de 24 ítems sin jerarquía.** Todo pesa lo mismo: "Salir" tiene el mismo tamaño de fila que "Cables". Un técnico que usa la app todos los días para las mismas 4-5 cosas tiene que escanear la lista entera cada vez.
6. **(Colateral) La toolbar del Diagrama es inusable en pantalla chica tal cual está.** 25 botones en scroll horizontal sin agrupar mezclan "ver" (zoom, encuadrar), "analizar" (diagnóstico, riesgo), "editar" (escenario, reconectar) y "exportar" (PNG) al mismo nivel. Para encontrar "🔺 Simular falla" hay que deslizar el dedo un buen rato contando botones.

---

## 2. Propuesta — Barra inferior (foco principal)

**Principio rector:** la barra inferior son los 5 verbos que el técnico hace *todos los días en el campo*, no un índice reducido del menú. Si algo ya está a 1 toque desde Inicio, no necesita también vivir en la barra fija.

### 2.1 Nueva composición

| Slot | Antes | Propuesto | Por qué |
|---|---|---|---|
| 1 | Inicio | **Inicio** | Se mantiene — es el ancla, vuelve del ahí a cualquier pantalla abierta. |
| 2 | Equipos | **Cables** | Es lo que más rota día a día (temporales, fusiones, verificación) según el propio panel de pendientes. Saca a "Equipos", que ya está a 1 toque desde Inicio. |
| 3 (centro) | + (fijo) | **+ (contextual, ver 2.3)** | Mismo lugar, comportamiento más inteligente. |
| 4 | Buscar | **Conexiones** | Segundo verbo diario (dar de alta/revisar conexión de un cable recién tirado). Saca a "Buscar", redundante con la barra superior. |
| 5 | Más | **Más** | Se mantiene como catch-all, pero reordenado (ver §3). |

**Íconos:** `cables` y `conexiones` ya existen en `assets/iconos/` — cero trabajo de diseño nuevo para este cambio.

### 2.2 Badges de pendientes (bajo costo, alto impacto)

`Modelo.devolver_pendientes_cables()` ya calcula `sin_conexion` y `temporales` — hoy ese cálculo solo se usa en Inicio. Propongo:

- Agregar un badge numérico chico (círculo rojo/alerta con el número) sobre el ícono **Cables** de la barra inferior cuando `temporales + sin_conexion > 0`.
- Mismo patrón, más adelante, sobre **Equipos** en el menú "Más" (sin auditar / sin imagen).
- Técnicamente: `_ItemNav` (en `tema.py`) no soporta hoy un badge — hay que agregarle un `Widget` circular superpuesto vía `FloatLayout`, y `BarraInferior` necesita un método `actualizar_badge(id_item, valor)` que la pantalla Inicio (que ya calcula estos números) pueda llamar tras `cargar_datos()`. Bajo riesgo: es un agregado aislado, no toca lógica existente de `_ItemNav`/`_actualizar_color`.
- Refresco: alcanza con recalcular el badge cada vez que se abre/cierra un Popup relevante (Cables, Conexiones) o con un `Clock.schedule_interval` liviano (p. ej. cada 60s) — no hace falta tiempo real.

### 2.3 FAB (+) contextual — diseño cerrado con Papi (fase 2, no bloqueante)

Hoy `_abrir_menu_rapido()` es una función global fija (mismas 3 opciones siempre). Pasa a ser un **menú que cambia según qué pantalla está más arriba en `Window.children`**, con SIEMPRE forma de menú (aunque tenga una sola opción, por consistencia visual — decisión de Papi).

**Detección:** se reutiliza el mismo mecanismo que ya usa `_ir_a_inicio`/`_mantener_arriba`/`_elevar` para saber qué Popup está al frente. Se implementa como un registro `{clase_popup: [opciones]}` con un fallback genérico, no un if/elif largo, para poder sumar pantallas después sin tocar la lógica de detección.

**Opciones confirmadas por pantalla:**

| Popup activo | Opciones del + | Notas |
|---|---|---|
| Inicio / sin match | Alta rápida de equipo · Nuevo Cable · Nueva Conexión | Igual que hoy — fallback. |
| `EquiposListado` | **Equipo nuevo** (`DialogoEquipo()`, en blanco) · **Alta rápida** (`DialogoAltaRapidaEquipo()`, ya trae la plantilla del tipo si existe) | Son 2 flujos, no 3 — "alta rápida" y "desde plantilla" hoy YA son la misma pantalla (`DialogoAltaRapidaEquipo` carga `Modelo.devolver_plantillas_conectores` automáticamente al elegir el tipo). No hace falta partir nada. |
| `RacksListado` | **Nuevo rack** | Única acción con sentido ahí. |
| `DialogoEquipo` (detalle de un equipo) | **Nuevo conector** (`DialogoConector(id_equipo=self.id_equipo)`, salteando el paso intermedio de entrar a "Ver conectores") | La pestaña "Acciones rápidas" del propio detalle ya cubre navegación (Diagrama, Árbol, Patcheras, Imagen, Conexiones, Cables, Ubicación); lo único que faltaba era *crear* algo nuevo sin rodeo, y conector es el único candidato limpio (Posición en rack no acepta hoy `id_equipo` precargado; Auditado ya tiene su botón propio). Se muestra igual como menú de una opción, no como acción directa, por consistencia con el resto. |
| `ConexionesListado` | **Nueva Conexión** (`DialogoConexion()`, formulario de una sola punta) | Resuelto — en la operación real usualmente no se conocen las dos puntas al momento de cargar (coincide con la categoría "1 extremo" que el propio Inicio ya trackea como pendiente). `EditorConexionesRapidas` (encadenado, carga el par completo) queda disponible desde el menú para cuando sí se tienen ambas puntas a mano, pero no es el default del +. |

**Modo selección — resuelto:** `EquiposListado`/`RacksListado`/`ConexionesListado` también se abren como *selector* dentro de otros diálogos (ej. "elegir equipo…" desde una Conexión abre `EquiposListado(modo_seleccion=True)` encima de todo). Mientras `modo_seleccion=True` esté activo, el **+ se ve en gris y no responde al toque** (`disabled=True` + color atenuado, mismo criterio visual que ya usa la app para botones deshabilitados) — no ofrece ni el menú genérico ni el contextual, porque en ese momento no hay ninguna acción de "crear" que tenga sentido: el usuario está eligiendo un registro existente para otra pantalla, no gestionando esa lista.

### 2.4 Mock rápido (texto)

```
Antes:  [Inicio] [Equipos] [ (+) ] [Buscar] [Más]
Después:[Inicio] [Cables🔴2] [ (+) ] [Conexiones] [Más]
```

---

## 3. Propuesta — Menú "Más" (reordenar, no rediseñar)

Cambio quirúrgico, bajo riesgo, mismo popup/estructura de `_abrir_menu_completo()`:

1. Mover el grupo **Buscar** al principio (ya lo está) pero agregar accesos directos a **Cables** y **Conexiones** dentro del primer grupo también (atajo visual, sin duplicar lógica — son las mismas funciones `abrir_cables`/`abrir_conexiones` ya importadas).
2. Separar visualmente **Diagramas** en dos: "Ver" (Imagen con conectores, Árbol, Patcheras) vs. "Análisis" (Diagrama de conexiones — que es la puerta a Diagnóstico/Riesgo/Escenario/Señal). Hoy están mezclados en un solo grupo de 4 sin indicar que el último es mucho más que los otros tres.
3. Mover **Preferencias** y **Aplicación** al final del todo (ya están, mantener) — son de uso esporádico, correcto que estén al fondo.
4. Nada de esto requiere tocar `core/` ni cambiar firmas: es reordenar tuplas dentro de la lista que ya devuelve `_abrir_menu_completo()`.

---

## 4. Propuesta — "Más" contextual, reutilizado desde la toolbar del Diagrama

No es parte de "la botonera inferior" que pediste originalmente, pero surgió de la misma conversación y termina siendo la solución al hallazgo colateral de §0 (los ~25 botones de `DiagramaConexiones`): **el botón "Más" de la barra inferior ya no es fijo — muestra un menú agrupado que depende de qué pantalla está activa**, reusando el mismo mecanismo que hoy arma `_abrir_menu_mas()` (popup con grupos + `ScrollView`), en vez de inventar un segundo tipo de "más opciones" para el Diagrama.

**Por qué reusar y no construir un dropdown propio dentro de la toolbar (como decía la v1 de este plan):** un solo patrón de "menú con muchas opciones" en toda la app, no dos. Y sirve de una vez para cualquier pantalla futura con el mismo problema (ej. el editor de planos `VistaPlanoInteractivo`, que en el roadmap del proyecto pinta para necesitar algo parecido).

**Alcance real:** repasando el resto de las pantallas, ninguna otra tiene un problema de "demasiadas opciones" hoy (los `ListadoPopup` normales tienen como mucho 2 botones extra). El único caso que justifica esto es `DiagramaConexiones`.

**Categorías confirmadas cuando `DiagramaConexiones` está activo:**
- **Analizar** — Diagnóstico, Historial, Riesgo equipo, Riesgo señal, Simular falla, Señal, Leyenda, Vista previa
- **Escenario** — Modo, Reconectar, Nuevo, Abrir, Guardar, Aplicar, Descartar

("Ver": Encuadrar, Expandir, Recargar, Solo nombre, Zoom, PNG se quedan **inline en la toolbar de arriba**, no bajan al Más — son los de uso constante.)

**No hace falta agregar el menú general (`_abrir_menu_completo()`) al final del "Más" contextual.** La barra superior (con el menú hamburguesa) es global igual que la inferior — `_elevar()` mantiene ambas siempre al frente sin importar qué Popup esté abierto — así que Preferencias/Catálogos/Salir nunca quedan inaccesibles aunque el "Más" de abajo cambie de contenido.

**Toggles y el check ✓:** los ítems que hoy son `ToggleButton` (Diagnóstico, Escenario, Reconectar, Señal, Leyenda, Riesgo equipo, Riesgo señal, Vista previa) se muestran en el menú con un `✓` al lado del texto cuando el modo correspondiente está activo (ej. `🩺 Diagnóstico  ✓`), para no perder la señal visual de "qué está prendido" que hoy dan los toggles resaltados de la toolbar.

**Implementación:** mismo registro `{clase_popup: [(grupo, [ítems])]}` que ya se propuso para el "+" contextual en §2.3 — extendido para que, si el Popup activo es `DiagramaConexiones`, el callback de "Más" arme estos grupos en vez de llamar a `_abrir_menu_completo()`. Los `✓` de estado se recalculan leyendo los mismos flags que ya existen en la instancia (`self._diag_modo`, `self._esc_modo`, `self._senal_color_activo`, etc.) al construir el popup, cada vez que se abre.

- Reemplazar los emoji sueltos en el texto (🩺🧪📡🎨🔺) por íconos PNG generados con `generar_iconos.py`, siguiendo la convención del resto de la app (ver §5 — necesita 4-5 íconos nuevos, a definir con Papi la metáfora visual).
- Esto es una fase propia, más grande que §2/§3, y **no las bloquea**.

---

## 5. Íconos nuevos a generar (si se aprueba §4, no necesario para §2/§3)

| Nombre propuesto | Uso |
|---|---|
| `diagnostico` | Modo diagnóstico de fallas |
| `escenario` | Modo escenario / simulación |
| `senal` | Colorear por señal / leyenda |
| `riesgo` | Colorear por riesgo (equipo y señal comparten el mismo glifo, distinto color) |
| `rayo` / `simular` | Simular falla |
| `salas` (opcional) | Si se agrega "Salas" a algún acceso directo — hoy no tiene ícono propio |
| `plano` (opcional) | Ídem para "Planos" |

Se generan una sola vez con `generar_iconos.py` (mismo mecanismo que ya existe), quedan versionados en `assets/iconos/`.

---

## 6. Fases de entrega (siguiendo el workflow ya establecido del proyecto)

| Fase | Alcance | Riesgo | Rama sugerida |
|---|---|---|---|
| **A** | Swap de ítems en `BarraInferior` (Cables/Conexiones en vez de Equipos/Buscar) — cambio de una lista de tuplas en `main.py` | Muy bajo | `ux-botonera-inferior-v1` |
| **B** | Badge de pendientes sobre "Cables" (`tema.py` + `main.py`) | Bajo (aditivo, no toca lógica existente) | mismo branch que A |
| **C** | Reordenar/agrupar `_abrir_menu_completo()` (§3) | Muy bajo | mismo branch que A |
| **D** | FAB contextual (§2.3) | Medio (depende de inspeccionar `Window.children`, ya hay precedente) | branch separado, después de validar A-C con Papi |
| **E** | "Más" contextual para Diagrama (Analizar/Escenario) + checks de estado + íconos nuevos (§4-§5) | Medio-alto (25 botones, muchos modos con exclusión mutua entre sí — ver comentarios `_esc_modo`/`_diag_modo`/`_senal_color_activo` en el código) | branch propio, `diagrama-mas-contextual` |

Cada fase sigue el pipeline ya establecido: `ast.parse`/`py_compile` → `pyflakes` contra baseline → smoke test `xvfb-run` → `git apply --check` en clon limpio, con su entrada de `changelog.txt` y bump de versión.

---

## 7. Preguntas abiertas para resolver con Papi antes de codear

1. ¿"Cables" y "Conexiones" en la barra inferior, o preferís mantener "Equipos" y solo sacar "Buscar" (cambio más chico, menos disruptivo para quien ya se acostumbró)?
2. Badge de pendientes: ¿solo en Cables, o también querés uno en "Más" (para no perder de vista Equipos sin auditar/sin imagen)?
3. FAB contextual (§2.3): ¿vale la pena la complejidad ahora, o lo dejamos en el roadmap y priorizamos A-C primero?
4. §2.3 ya no tiene preguntas abiertas — quedó cerrado en la conversación (2 opciones para Equipos, `DialogoConexion` para "Nueva Conexión", + en gris/deshabilitado durante `modo_seleccion=True`).
5. Metáfora visual para los íconos nuevos de §5 (por ejemplo: ¿"riesgo" es un triángulo de alerta o un semáforo?) — mejor definirlo antes de generar los PNG.

---

## 8. Riesgos

- **Costumbre del usuario:** sacar "Equipos" de la barra fija puede resultar raro las primeras veces si es el flujo más usado en la práctica real (esto lo sabe mejor Papi que un relevamiento de código — de ahí la pregunta 1).
- **Los popups son fullscreen y se apilan sobre `Window`:** cualquier cambio a `BarraInferior` hereda el mismo parche de "colchón anti-solapamiento" (`tema.py`, `_popup_open_con_colchon`) — no debería romperse, pero conviene el smoke test visual real, no solo `pyflakes`.
- **Íconos nuevos (§5) son trabajo de diseño, no solo de código** — conviene timeboxear esa parte aparte para no demorar las fases A-C, que son de bajísimo riesgo y ya dan una mejora perceptible.
