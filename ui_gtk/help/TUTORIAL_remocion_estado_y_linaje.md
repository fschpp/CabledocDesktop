# Simular Remoción, Estado de Señal y Linaje — Guía de uso

Esta guía cubre tres funcionalidades nuevas de CableDoc, agrupadas porque
surgieron de la misma necesidad (saber rápido "¿qué se cae si toco esto?"
sin tener que abrir el diagrama completo) aunque responden preguntas
distintas:

| | **Simular remoción** | **Estado de señal (caída)** | **Linaje de señal** |
|---|---|---|---|
| ¿Qué responde? | "¿Qué se cae si desconecto ESTO?", desde el propio ABM | "De lo que se cae, ¿qué NOMBRES de señal se pierden?" | "¿De qué otra(s) señal(es) deriva esta?" |
| ¿Dónde vive? | Botón "⚡ Simular remoción" en Cable/Equipo/Rack/Conexión | Diagrama de Conexiones (tachado) + Vista Previa (placeholder) | Catálogo de Señales → "🧬 Linaje…" |
| ¿Calcula corte? | Sí (reutiliza el mismo motor de Impacto) | No, sólo LEE el corte ya calculado por otro | No — es documentación, no topología |
| ¿Se persiste? | No, es una simulación puntual | No, sólo mientras el análisis está activo | **Sí** — es el único de los tres que se guarda en la base |

Las tres reutilizan el motor de siempre (`graph_impact.py`), salvo Linaje,
que es documentación pura y no calcula nada.

---

## Parte 1 — Simular remoción

**Dónde:** botón **"⚡ Simular remoción"** en los diálogos de detalle de
**Cable**, **Equipo**, **Rack** y **Conexión**.

**Pregunta que responde:** *"Sin salir de esta ficha, ¿qué otros equipos y
cables quedan sin señal si desconecto/retiro esto?"*

Es la versión rápida del **Análisis de Impacto** (que vive dentro del
Diagrama de Conexiones) para cuando estás editando un elemento puntual y no
querés abrir el diagrama completo sólo para chequear el impacto.

### Cómo usarlo

1. Abrí el ABM del elemento (Cable, Equipo, Rack o Conexión — este último
   sólo si ya está guardado).
2. Botón **"⚡ Simular remoción"**.
3. Se abre una ventana con:
   - **Equipos** que quedan sin señal.
   - **Cables** que quedan sin señal.
   - **Señales** (con nombre) que se pierden — mismo cruce que usa Análisis
     de Impacto en el diagrama.
   - Si hay una **Regla Lógica** (AND/OR) que dejó de cumplirse, aparece
     como advertencia arriba de la lista.
4. Si no hay impacto, dice simplemente **"✅ Sin impacto en la cadena"**.
5. No modifica nada — es 100% simulación, cerrás la ventana y listo.

### Qué significa cada caso

| Elemento | Qué se simula |
|---|---|
| **Cable** | Desconectar ese cable puntual. |
| **Equipo** | Que el equipo entero deje de funcionar (falla total). |
| **Rack** | Corte de energía de **todo el rack** — equipos posicionados directo *más* los equipos que están dentro de frames alojados en ese rack. Se evalúa todo junto (no equipo por equipo), porque una Regla Lógica AND que dependa de dos equipos del mismo rack necesita verse en conjunto. |
| **Conexión** | Desconectar esa punta puntual — equivale a cortar el cable entero, porque el grafo de señal no modela extremos sueltos por separado. |

### Cómo funciona por dentro

Motor: `graph_impact.py` (`GraphImpactAnalyzer`), los mismos métodos que ya
usaba Análisis de Impacto (`simular_desconexion`, `simular_falla_equipo`)
más dos nuevos (`simular_perdida_rack`, `simular_perdida_conexion`) que
delegan en los anteriores en vez de duplicar lógica. UI:
`ImpactoResultadoDialog` en `impacto_ui.py` — un diálogo liviano sin canvas
Cairo, para poder abrirse desde cualquier ABM sin depender del Diagrama de
Conexiones.

---

## Parte 2 — Estado de señal (vivo / caído)

**Dónde:** se ve automáticamente dentro del **Diagrama de Conexiones**,
mientras hay un **Análisis de Impacto**, un **Riesgo de Falla** o un
**Escenario** activo — no es un botón aparte, es un overlay sobre lo que
ya tenías activado.

**Pregunta que responde:** *"De los equipos y cables que se caen, ¿cuáles
tenían un NOMBRE de señal cargado a mano, y ahora se pierde?"*

Antes de esta función, cortar un cable pintaba en rojo los equipos/cables
afectados, pero si tenías **"📡 Colorear por señal"** prendido, los
conectores seguían mostrando su nombre y color de señal como si nada — no
había forma visual de saber que ESA señal en particular se había caído.

### Ejemplo real (el caso que motivó esta función)

El equipo **MDK-111A-M** (un DSK) combina tres entradas:
- `COMERCIALES KEY LOGOS`
- `COMERCIALES FILL LOGOS`
- `CLEAN FEED PROGRAMA TRANSMISION`

...en una salida nueva: `PROGRAMA CON LOGOS TRANSMISION`. Si cortás el
cable que trae `CLEAN FEED PROGRAMA TRANSMISION` (y el equipo tiene su
**Regla Lógica AND** bien configurada — ver la guía de Análisis de Impacto,
punto 2), ahora:

- El puerto **"IN 3 BKGD A"** (donde está cargada esa señal) aparece con el
  nombre **tachado**, en vez de mostrarse como si la señal siguiera viva.
- El color de señal de ese puerto vuelve al celeste/naranja normal de
  IN/OUT — deja de mostrar su color distintivo, porque esa señal ya no
  está ahí.
- La **leyenda** (si está activa) suma la entrada *"❌ caída (análisis
  activo)"*.
- Si tenés la **Vista Previa Visual** abierta sobre ese conector (o
  cualquiera que dependa de él), en vez de la imagen real aparece un
  placeholder de **barras de color + ruido + "❌ SIN SEÑAL"**, con el pie
  *"⚠ señal caída en el análisis activo"*.

### Cómo usarlo

No hay nada que activar aparte de lo que ya usabas:

1. Prendé **"📡 Colorear por señal"** (y la leyenda, si querés verla).
2. Corré **"⚡ Analizar Impacto"**, **"🔺 Simular falla del seleccionado"**
   (Riesgo) o activá el **Modo Escenario**, como siempre.
3. Los puertos afectados se tachan solos — no hay un paso extra.

> **Ojo con Vista Previa:** Vista Previa, Análisis de Impacto y Modo
> Escenario son mutuamente excluyentes por diseño (activar uno apaga los
> otros dos, para no competir por el mismo clic). Eso significa que, hoy,
> el placeholder de Vista Previa **no** se va a ver a la vez que el
> tachado de Impacto en el mismo momento — sí funciona con el diálogo de
> Riesgo ("🔺 Simular falla del seleccionado"), que es modal y no tiene esa
> exclusión. Si esto te resulta limitante en el uso real, es una decisión
> de diseño que se puede reconsiderar — avisá.

### Cómo funciona por dentro

Módulo nuevo `senal_estado.py` (sin GTK): cruza el conjunto de equipos
impactados que ya calculó cualquiera de los tres motores de simulación
contra `senal_en_conector`, y devuelve qué conector tenía qué nombre. Cada
motor (`impacto_ui.py`, `riesgo_diagrama_ui.py`, `escenario_ui.py`) guarda
ese cruce en un cache propio; `senal_diagrama_ui.py` los lee a los tres sin
necesitar saber los detalles de cada uno (`_senal_conectores_caidos()`). Es
puramente de lectura — no recalcula nada ni escribe en la base.

---

## Parte 3 — Linaje de señal

**Dónde:** Diagramas → **"📡 Señales"** → seleccioná una señal → **"🧬
Linaje…"**. También accesible desde **"📡🔎 Buscador de señal…"** → **"🧬
Ver / editar linaje…"**.

**Pregunta que responde:** *"¿De qué otra(s) señal(es) deriva esta?"* —
documentación, no cálculo. Sirve para señales que **mutan** de nombre al
pasar por un equipo (un DSK que combina, un conversor de norma que cambia
de HD a SD, etc.) y donde `senal_propagation.py` exige carga manual a
propósito porque el nombre nuevo no se puede inferir solo.

> **No confundir con Estado de señal (Parte 2):** Linaje es un árbol
> genealógico de NOMBRES, guardado en la base, sin relación con si hay
> algún corte activo en este momento. Estado de señal es al revés: no
> guarda nada, sólo refleja en vivo un corte ya calculado. Podés tener
> linaje cargado sin que eso afecte nunca cómo se calcula un corte, y
> viceversa.

### Ejemplo real

Siguiendo el mismo caso del MDK-111A-M: `PROGRAMA CON LOGOS TRANSMISION`
**deriva de** tres señales:
- `CLEAN FEED PROGRAMA TRANSMISION`
- `COMERCIALES KEY LOGOS`
- `COMERCIALES FILL LOGOS`

### Cómo usarlo

1. Abrí **"🧬 Linaje…"** sobre la señal **hija** (la que "nace" del
   combinador, no las que entran).
2. El diálogo aparece con una lista de **padres sugeridos automáticamente**
   — ya tildados. La sugerencia mira dónde está cargada la señal a mano
   *en un conector de salida*, y junta las señales que hoy están en las
   entradas de ese mismo equipo.
   - Sólo sugiere a partir de conectores de **salida** — una señal cargada
     en una entrada no sugiere nada, porque estar "entrando" no implica
     que el equipo la produzca.
3. Destildá lo que no corresponda, o **"➕ Agregar señal…"** para sumar
   manualmente cualquier otra del catálogo que la sugerencia no haya
   encontrado.
4. Doble clic sobre la columna **Nota** para dejar aclarado el motivo del
   vínculo (ej. *"combinación DSK"*, *"downconvert HD→SD"*) — opcional.
5. **"🔄 Volver a sugerir"** si el cableado cambió desde que abriste el
   diálogo — sólo AGREGA sugerencias nuevas, no toca lo que ya tildaste o
   destildaste a mano.
6. **Aceptar** guarda. Si algo que tildaste cerraría un **ciclo** (por
   ejemplo, intentar que A derive de B cuando B ya deriva de A, directa o
   indirectamente), esa fila puntual no se guarda y aparece un aviso — el
   resto del guardado sigue adelante igual.
7. **"🌳 Ver árbol de linaje"** para navegar hacia arriba (*"⬆ Deriva
   de…"*) y hacia abajo (*"⬇ Usada en…"*) de forma recursiva, expandiendo
   cada rama bajo demanda.

### Qué NO hace (todavía)

- No calcula corte ni alimenta el Análisis de Impacto — es un registro
  aparte, a propósito (ver el recuadro de arriba).
- No hay vista **gráfica** del linaje (tipo diagrama de nodos) — por ahora
  es sólo el árbol de texto del punto 7. Puede sumarse más adelante si
  hace falta.

### Cómo funciona por dentro

Tabla `senal_linaje` (muchos a muchos, con nota libre), CRUD en
`modelo.py`. El algoritmo de sugerencia (`Modelo.sugerir_padres_de_senal`)
y la detección de ciclos (`Modelo.hay_ciclo_linaje`) también viven ahí. UI:
`_DialogoLinajeSenal` (carga) y `_ArbolLinajeSenal` (árbol lazy-load, mismo
patrón que el Árbol de Conexiones de un equipo) en `cabledoc.py`.

---

## Resumen — ¿Cuál uso primero?

- Estás editando un Cable/Equipo/Rack/Conexión puntual y querés un chequeo
  rápido antes de tocar algo: **Simular remoción**.
- Ya estás en el Diagrama de Conexiones con "Colorear por señal" prendido
  y corriste un Análisis de Impacto / Riesgo / Escenario: el **Estado de
  señal** se ve solo, no hay nada que activar aparte.
- Estás documentando por qué una señal se llama distinto después de pasar
  por un equipo (un DSK, un conversor de norma): cargá el **Linaje** una
  sola vez, queda guardado para siempre y no depende de que haya ningún
  corte activo.
