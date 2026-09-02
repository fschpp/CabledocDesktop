# CableDoc — Guía de Funcionalidades Avanzadas

Esta guía cubre las funcionalidades del **Diagrama de Conexiones** y
herramientas relacionadas, una por una. La mayoría vive dentro de la
ventana **Diagramas → 🔗 Diagrama de conexiones…**, en la barra de menú de
esa ventana (Impacto / Riesgo / Señal / Escenario / Herramientas).

> **Nota sobre superposición:** varias de estas funcionalidades responden
> preguntas parecidas pero no iguales. Al final de esta guía hay una tabla
> comparativa para no confundirlas.

---

## 1. Análisis de Impacto

**Menú:** Diagrama de Conexiones → **Impacto** → *"⚡ Analizar Impacto"*

**Pregunta que responde:** *"¿Qué se queda sin señal si corto este cable o
falla este equipo?"*

### Cómo usarlo
1. Elegí el cable a simular de tres formas (la que te resulte más cómoda):
   - Clic en un **equipo** → aparece la lista de cables que salen de él.
   - **"🔍 Buscar cable…"** → buscador por nombre/código.
   - Clic directo sobre una línea del diagrama.
2. El panel **"⚡ ANÁLISIS DE IMPACTO"** muestra si hay impacto, cuántas
   señales se pierden, y qué equipos/cables quedan afectados (se pintan en
   rojo; los que siguen con señal, en verde).
3. **"✕ Salir del análisis"** para volver al modo normal.

### Cómo funciona por dentro
Motor: `graph_impact.py` (`GraphImpactAnalyzer`). Construye un grafo
dirigido equipo→equipo (aristas = cables) en memoria con GraphQLite y hace
un BFS parcial desde las fuentes de señal afectadas. Es el mismo grafo que
reutilizan varias otras funcionalidades de esta guía (Riesgo de Falla,
Escenario, Consola Cypher).

---

## 2. Riesgo de Falla (Índice de Riesgo — IRF)

**Menú:** Diagrama de Conexiones → **Riesgo** → *"🎨 Colorear por riesgo"* /
*"🔺 Simular falla del seleccionado"*

**Pregunta que responde:** *"¿Qué tan grave sería que ESTE equipo falle,
considerando tanto su probabilidad de fallar como el impacto que tendría?"*

### La fórmula
```
Riesgo = max(Probabilidad, P_MIN) × Impacto / 100
```
- **Probabilidad**: antigüedad + condición de uso + historial de problemas
  del equipo.
- **Impacto**: fracción del parque que queda sin señal si este equipo
  falla (reutiliza el mismo motor que el Análisis de Impacto, punto 1).

### Equipos críticos (opcional pero recomendado)
Si marcás un subconjunto de equipos como **"⭐ Marcar críticos"** (selección
por rectángulo o Shift/Ctrl+clic en el diagrama), el Impacto pasa a medirse
**solo contra ese conjunto** — es decir, el riesgo prioriza lo que
realmente te importa (ej. la cadena de aire) en vez de tratar por igual un
monitor de sala de control y el switcher máster. Sin equipos marcados, se
mide contra todo el parque.

### Cómo usarlo
- **"🎨 Colorear por riesgo"**: pinta cada equipo según su nivel de IRF.
- **"🔺 Simular falla del seleccionado"**: seleccioná un equipo y mirá qué
  señales se pierden si falla, sin tener que pasar por el Análisis de
  Impacto de un cable puntual.

### Cómo funciona por dentro
Motor: `risk_engine.py`, sobre `graph_impact.py`.

---

## 3. Riesgo de Señal (predicción desde catálogo)

**Menú:** Diagrama de Conexiones → **Riesgo** → *"🎨 Colorear por riesgo de
señal"*

**Pregunta que responde:** *"¿Esta cadena debería funcionar bien, según lo
que sé de sus componentes (largo de cable, ancho de banda, formato de
audio)?"*

> Esta funcionalidad tiene su propio tutorial detallado — ver
> `TUTORIAL_riesgo_de_senal.md`, Parte 1. Resumen rápido: tres ejes
> independientes (atenuación / cuello de botella / mismatch de formato),
> predichos a partir del catálogo de Tipos de Cable y Tipos de Ficha —
> **requiere que ese catálogo esté cargado** para encontrar algo.

### Cómo funciona por dentro
Motor: `signal_risk.py`. UI del overlay: `signal_risk_diagrama_ui.py`.

---

## 4. Bitácora de Incidentes y Armado

**Menú:** botón **"📋 Ver incidentes"** en el listado de Equipos o de
Cables. Overlay: Diagrama de Conexiones → *"🌡 Zona caliente"*.

**Pregunta que responde:** *"¿Qué pasó realmente acá? ¿Hay un patrón de
fallas repetidas en este equipo, cable o zona del rack?"*

> Esta funcionalidad también tiene tutorial propio — ver
> `TUTORIAL_riesgo_de_senal.md`, Parte 2 (incluye el detalle de "Armado
> por extremo", para cuando una ficha de cable está mal soldada por
> dentro aunque a simple vista parezca correcta).

### Cómo usarlo
1. **"➕ Nuevo incidente"**: cargá fecha/hora, relato (podés pegar el texto
   tal cual como te lo contaron), estado.
2. Podés vincular el incidente a equipos, cables, y/o **zonas sospechosas**
   (**"➕ Nueva zona…"** — un rack o sector físico donde vienen pasando
   cosas raras, sin poder todavía señalar un equipo puntual).
3. El overlay **"🌡 Zona caliente"** en el diagrama pinta según el nivel de
   riesgo acumulado (equipo/cable/zona), con decaimiento por antigüedad —
   un incidente de hace 11 meses pesa casi nada si la ventana configurada
   es de 12 meses.

### Cómo funciona por dentro
Motor: `riesgo_analogico.py`. UI: `bitacora_ui.py`.

---

## 5. Modo Escenario

**Menú:** Diagrama de Conexiones → **Escenario**

**Pregunta que responde:** *"¿Qué pasaría si combino VARIAS fallas/cortes a
la vez, y qué reconexión de emergencia lo resolvería?"* — a diferencia del
Análisis de Impacto (punto 1), que evalúa un solo cable por vez, Escenario
te deja armar una combinación completa antes de mirar el resultado.

### Cómo usarlo
1. **"🆕 Escenario nuevo"** para arrancar en blanco.
2. Sobre el diagrama, marcá:
   - **🔺 Equipos fallados** (clic sobre el nodo)
   - **✕ Cables cortados** (clic sobre la línea)
   - **🔗 Reconexión** — una conexión *virtual* de emergencia (no real
     todavía) para ver si resuelve el problema
3. El resultado se recalcula **en vivo** con cada cambio (todo evaluado
   junto en una sola simulación, no cable por cable) — típicamente 5-25ms,
   así que podés iterar libremente.
4. **"💾 Guardar"** para no perder el escenario armado, o **"📂 Abrir
   escenario…"** para retomar uno guardado.
5. **"🗑 Descartar todo"** para volver a empezar.
6. Solo cuando confirmás **"▶ Aplicar…"** el escenario deja de ser una
   simulación y escribe de verdad en `conexion`/`cable` — es la única
   operación de todo el módulo que toca la infraestructura real, y pide
   confirmación explícita.

### Cómo funciona por dentro
Motor: `escenario_engine.py` (sobre `graph_impact.py`, método
`simular_escenario()`). UI: `escenario_ui.py`. El resultado de la
simulación **no se persiste** — se recalcula al vuelo cada vez, porque es
barato.

---

## 6. Asistente de Diagnóstico de Falla

**Menú:** Diagrama de Conexiones → **Escenario** (mismo submenú, con un
separador) → *"🩺 Diagnóstico"*

**Pregunta que responde:** *"Hay un síntoma real (ej. 'no llega audio a
Master') — ¿cuál es el punto exacto de la cadena donde se corta?"*

### Cómo usarlo
1. Elegí el conector donde aparece el síntoma (ej. la entrada del equipo
   que no recibe señal) y describilo (opcional).
2. El asistente arma la cadena real completa entre el síntoma y la fuente
   (reutiliza el mismo camino que ya calcula Vista Previa de Imagen, punto
   7 — no es un motor de grafo nuevo).
3. Te va sugiriendo, uno por uno, el **próximo punto a testear**
   ("Preguntar acá →"), y vos respondés:
   - **✅ Sí** (hay señal en ese punto)
   - **❌ No** (no hay señal)
   - **🤷 No sé** (todavía no lo revisaste)
4. Con cada respuesta, el asistente hace **bisección** sobre la cadena —
   no tenés que revisar todos los puntos uno por uno, converge mucho más
   rápido que ir de punta a punta.
5. **"Continuar →"** para avanzar; hay undo si te equivocaste de respuesta.
6. Si la cadena automática no llega hasta el final (matriz sin
   documentar, patchera incompleta, bifurcación, o simplemente no hay
   origen cargado), el asistente te avisa **por qué se cortó** en vez de
   fallar en silencio.
7. **"📋 Historial de diagnósticos"**: queda guardada cada sesión de
   diagnóstico para consulta posterior — útil para detectar fallas
   recurrentes en el mismo tramo.

### Modo exclusivo
Diagnóstico es mutuamente excluyente con Escenario/Impacto/Vista Previa —
activar uno apaga los demás automáticamente, para no mezclar overlays.

### Cómo funciona por dentro
Motor: `diagnostico_falla.py` (`MotorDiagnostico` + `SesionDiagnostico`).
UI: `diagnostico_ui.py`.

---

## 7. Vista Previa Visual de Señal

**Menú:** Diagrama de Conexiones → **Señal** → *"🖼 Vista previa de
imagen"*

**Pregunta que responde:** *"¿Qué IMAGEN corresponde, ahora mismo, a la
salida de este conector?"* (por ejemplo, para ver qué cámara/fuente está
efectivamente en el aire en un punto dado de la cadena, sin ir físicamente
al equipo).

### Cómo usarlo
- **"📷 Asignar imagen manual…"**: cargá a mano qué imagen corresponde a
  un conector de fuente (donde no hay de dónde "heredar" la imagen).
- **"🔀 Configurar composición…"**: para conectores que reciben MÁS de una
  fuente (ej. un mezclador con varias entradas), elegís el modo de
  composición y qué entrada de este equipo ocupa cada miembro.
- **"✖ Quitar imagen manual"** / **"🗑 Quitar composición"** para deshacer.
- El resto de los conectores resuelven su imagen automáticamente,
  siguiendo la cadena hacia atrás (¿qué lo alimenta?) hasta encontrar una
  imagen manual o una composición.

### Cómo funciona por dentro
Motor: `senal_visual.py` (`VisualizadorSenal`) — arma un grafo invertido
"quién alimenta a quién" (mismo criterio que `senal_propagation.py`) y
resuelve la imagen de cualquier conector con una única función recursiva.
UI: `senal_visual_ui.py`. Este mismo grafo invertido es el que reutiliza
el Asistente de Diagnóstico (punto 6).

---

## 8. Propagación y Coloreado de Señal

**Menú principal (fuera del diagrama):** Diagramas → *"📡🔮 Calcular
propagación de señal…"* / *"📡🔎 Buscador de señal…"* / *"📡🧹 Borrar
señales propagadas…"*
**Dentro del diagrama:** Diagrama de Conexiones → **Señal** → *"📡 Colorear
por señal"*

**Pregunta que responde:** *"¿Qué CONTENIDO (nombre de señal) hay en cada
conector, dado lo que cargué a mano en las fuentes?"* — distinto de Vista
Previa (punto 7, que resuelve una IMAGEN) y distinto de Análisis de
Impacto (punto 1, que resuelve alcanzabilidad, no contenido).

### Cómo usarlo
1. Cargá manualmente qué señal sale de cada **fuente** (Diagramas →
   *"📡 Señales"*).
2. **"📡🔮 Calcular propagación de señal…"** corre una sola pasada sobre
   todo el grafo y etiqueta cada conector con la señal que le llega.
3. Con **"📡 Colorear por señal"** activo en el diagrama, cada conector se
   pinta con un color estable por señal (en vez del celeste/naranja fijo
   de IN/OUT); la leyenda **"🎨 Leyenda"** muestra qué color es cada señal.
4. **"📡🔎 Buscador de señal…"** para ubicar rápido dónde está una señal
   puntual sin recorrer el diagrama a mano.
5. **"📡🧹 Borrar señales propagadas…"** si necesitás recalcular desde
   cero (por ejemplo, tras un cambio grande de cableado).

### Cómo funciona por dentro
Motor: `senal_propagation.py` — deliberadamente separado de
`graph_impact.py` porque resuelve un problema distinto (propagación de
una etiqueta de contenido, no alcanzabilidad) y no necesita GraphQLite:
una relajación iterativa tipo Bellman-Ford en Python puro alcanza. UI del
overlay: `senal_diagrama_ui.py`.

---

## 9. Consola Cypher

**Menú:** Diagramas → *"🔮 Consola Cypher (GraphQLite)…"*

**Pregunta que responde:** cualquiera que se pueda expresar como una
consulta sobre el grafo de equipos/cables — para casos que no tienen un
reporte prearmado.

### Cómo usarlo
1. Escribí una query Cypher en el editor.
2. **F5** o **"▶ Ejecutar"** para correrla.
3. Hay ejemplos agrupados por categoría a la izquierda (── EQUIPOS ──,
   ── CABLES ──, ── CADENAS ──, ── ANÁLISIS ──, ── MODIFICAR (con
   cuidado) ──) para copiar y adaptar.
4. **"🔀 Reordenar"** / **"⊞ Encuadrar"** para trabajar cómodo con el
   resultado si es un grafo visual.

### Qué se puede consultar
Nodos `Equipo` y aristas `CABLE` (con propiedades como `cable_id`,
`nombre`, y — desde la integración con Riesgo de Señal — `naturaleza_senal`
y `ancho_banda_mhz`). Ejemplo:
```cypher
MATCH ()-[r:CABLE]->() WHERE r.naturaleza_senal='ANALOGICA' RETURN r
```

### Cómo funciona por dentro
Sobre el mismo grafo GraphQLite que construye `graph_impact.py` — no es
un motor aparte, es una ventana para interrogarlo directamente.

---

## 10. Lienzo Libre de Diagrama (Diagramas Personalizados)

**Menú:** Diagramas → *"🗂 Diagramas personalizados…"*

**Pregunta que responde:** *"Quiero armar un diagrama a medida (para
imprimir, para explicarle algo a alguien, para planificar) que no tiene
por qué reflejar el cableado real completo."*

Es una funcionalidad **aparte** del Diagrama de Conexiones global — no
comparte flujo con él, aunque reutiliza la misma ventana (pan/zoom, drag
de nodos, exportar SVG/PDF, buscador) por herencia.

### Cómo usarlo
1. **"➕ Agregar equipo…"** para traer equipos al lienzo, de a uno.
2. **"🔗 Traer equipo + conectados (real)…"** para traer un equipo junto
   con sus conexiones reales existentes, de una sola vez.
3. **"✎ Conectar puertos"** para armar conexiones **manuales** — estas NO
   se guardan en la tabla `conexion` real, son solo para este diagrama.
4. **"🗂 Conexiones manuales…"** para ver/editar las que ya armaste.
5. **"🗑 Quitar equipo(s)"** / **"🗑 Quitar seleccionada"** para deshacer.
6. **"💾 Guardar diagrama…"** con nombre y descripción — queda disponible
   para reabrir después desde el listado de Diagramas Personalizados.

### Cómo funciona por dentro
`diagrama_personalizado.py`, hereda la ventana `DiagramaConexiones` de
`pantallas_avanzadas.py` y agrega la carga/guardado propios (tablas
`diagrama_guardado` / `diagrama_guardado_nodo` / `diagrama_guardado_conexion`).

---

## Tabla comparativa — no confundir

| Funcionalidad | Pregunta que responde | Fuente del dato |
|---|---|---|
| Impacto | ¿Qué se cae si corto ESTE cable? | Grafo, calculado |
| Riesgo de Falla (IRF) | ¿Qué tan grave sería que ESTE equipo falle? | Antigüedad/uso/historial + grafo |
| Riesgo de Señal | ¿Esta cadena debería funcionar bien? | Catálogo (predicción) |
| Bitácora/Armado | ¿Qué pasó realmente acá? | Hechos reportados/observados |
| Escenario | ¿Qué pasa si combino VARIAS fallas a la vez? | Grafo, simulación en vivo |
| Diagnóstico de falla | ¿Dónde exactamente se corta ESTE síntoma real? | Bisección guiada sobre la cadena real |
| Vista Previa Visual | ¿Qué IMAGEN sale de este conector ahora? | Cadena real + imágenes cargadas |
| Propagación de Señal | ¿Qué CONTENIDO (nombre) hay en este conector? | Cadena real + señales cargadas a mano |
| Consola Cypher | Lo que necesites preguntarle al grafo | Grafo, consulta libre |
| Diagramas Personalizados | Armar una vista a medida, no necesariamente real | Mixto (real + manual) |
