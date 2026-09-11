# Linaje de señal

**Menú Catálogos → 📡 Señales → botón "🧬 Linaje…"**
**o Menú Diagramas → 📡🔎 Buscador de señal… → botón "🧬 Ver / editar linaje…"**

> Documenta `plan_estado_senal_y_linaje.md`, Función 2.

---

## Qué es (y qué NO es)

El linaje de señal registra **de qué otra(s) señal(es) deriva** una
señal del catálogo. Por ejemplo: la señal "PROGRAMA CON LOGOS
TRANSMISIÓN" puede derivar de "CLEAN FEED PROGRAMA TRANSMISIÓN" +
"COMERCIALES KEY LOGOS" + "COMERCIALES FILL LOGOS" — porque esas tres se
combinan en un DSK/mezclador para producir la primera.

Es **puramente documental** — genealogía de nombres, para que quede
escrito en algún lado de dónde "nace" el contenido de una señal cuando
eso no es evidente sólo mirando el cableado. Es una decisión de diseño
explícita, tomada en la entrevista que originó el plan:

> ⚠️ **El linaje NO alimenta ningún cálculo del sistema.** No lo usa
> `senal_propagation.py` (que sigue exigiendo carga manual en el
> conector productor real) ni `graph_impact.py` (que sigue calculando
> cortes por `regla_logica`, topología real de cables). Cargar o dejar
> vacío el linaje de una señal **no cambia en nada** qué se ve caído en
> "⚡ Analizar Impacto", ni qué colorea "🎨 colorear por señal", ni ningún
> otro cálculo del Diagrama de conexiones.

## Su uso "en diagramas": aclaración importante

Por el enunciado de este tutorial conviene ser directo: **el linaje de
señal hoy no está integrado dentro del Diagrama de conexiones ni de
ninguna otra vista visual del cableado.** No hay ningún botón, ícono ni
overlay del linaje dentro de `DiagramaConexiones`, ni al hacer clic
derecho sobre un conector ahí.

Los ÚNICOS dos lugares desde donde se abre el editor de linaje son:

1. **Catálogos → 📡 Señales**, seleccionando una fila y apretando el
   botón extra **"🧬 Linaje…"**.
2. **Diagramas → 📡🔎 Buscador de señal…**, eligiendo una señal del
   catálogo, que abre la ventana **"¿Dónde está ‹nombre›?"** (la lista de
   equipos/conectores donde esa señal está cargada hoy) — esa ventana
   tiene arriba de todo el botón **"🧬 Ver / editar linaje…"**.

El segundo camino está dentro del menú "Diagramas" y muestra información
que sí sale del cableado real (dónde está cargada la señal), pero **no
es un diagrama visual** — es una tabla de solo texto (Equipo / Conector /
Formato / Origen). Si buscabas cómo ver el linaje dibujado sobre el
Diagrama de conexiones o superpuesto a los nodos del canvas, esa función
no existe hoy; lo más cercano es el árbol de texto que se explica en el
punto 4 más abajo.

---

## 1. Abrir el editor de linaje de una señal

**Camino A — desde el catálogo:**
1. Menú **Catálogos → 📡 Señales**.
2. Seleccioná la señal (por ejemplo "PROGRAMA CON LOGOS TRANSMISIÓN").
3. Botón **🧬 Linaje…**.

**Camino B — desde "¿dónde está cargada?":**
1. Menú **Diagramas → 📡🔎 Buscador de señal…**.
2. Elegí la señal en el selector.
3. En la ventana "¿Dónde está…?" que se abre, botón **🧬 Ver / editar
   linaje…** (arriba de todo).

Ambos caminos abren el mismo diálogo: **"Linaje de: ‹nombre de la
señal›"**.

---

## 2. Cómo se precarga la lista (sugerencias automáticas)

Al abrir el diálogo, la lista de "señales padre" se llena con la
**unión** de dos cosas, ambas ya tildadas:

- Los padres que **ya estaban guardados** de una edición anterior.
- Los padres **sugeridos automáticamente**, si todavía no estaban
  guardados.

### Cómo funciona la sugerencia

El algoritmo busca los conectores de **SALIDA (OUT)** donde la señal hija
está cargada **MANUAL** (no propagada) — sólo mira salidas a propósito:
si la señal estuviera cargada en una ENTRADA, eso significaría que está
LLEGANDO desde otro lado, no que el equipo la produce, y sugerir padres
por ese motivo mezclaría insumos hermanos entre sí sin relación real
(ejemplo del propio código: un CLEAN FEED que entra a un DSK terminaría
"sugiriendo" KEY LOGOS/FILL LOGOS como si CLEAN FEED derivara de ellas,
cuando en realidad las tres son insumos independientes del mismo
combinador).

Una vez encontrado ese conector OUT, mira **todas las entradas (IN)** del
mismo equipo y junta las señales (manuales o propagadas) que hoy están
cargadas ahí — esas son las sugerencias de padres.

> Si la señal hija todavía no está cargada MANUAL en ningún conector de
> salida, no hay de dónde sugerir: la lista sale vacía y hay que cargar
> los padres a mano (ver punto 3). No es un error.

El caso normal de uso es simplemente: **abrir el diálogo → revisar que
las sugerencias tengan sentido → Aceptar**. Si alguna sugerencia no
corresponde, destildala antes de aceptar.

### Volver a sugerir

Si el cableado cambió después de abrir el diálogo (por ejemplo cargaste
una entrada nueva mientras lo tenías abierto), el botón **🔄 Volver a
sugerir** vuelve a correr el algoritmo y **sólo agrega** sugerencias
nuevas que todavía no estén en la lista — no toca nada de lo que ya
tildaste, destildaste o editaste a mano.

---

## 3. Agregar un padre manualmente

Si la señal padre que buscás no aparece sugerida (por ejemplo porque
todavía no está cargada MANUAL en ninguna salida, o porque el vínculo es
conceptual y no tiene por qué reflejarse en el cableado actual), usá el
botón **➕ Agregar señal…**: abre el catálogo completo de señales para
elegir cualquiera y sumarla a la lista, tildada.

Restricciones al agregar:
- Una señal **no puede ser padre de sí misma**.
- Si la señal elegida ya está en la lista, se avisa y no se duplica.

---

## 4. Notas por vínculo

Cada fila de padre tiene una columna de **nota** editable — doble clic
sobre la celda para escribir un comentario libre (por ejemplo "vía DSK 2,
key invertida"). Es opcional y se guarda junto con el vínculo.

---

## 5. Guardar

Al apretar **Aceptar**:
- Todo lo que quedó **tildado** se guarda (upsert: si el vínculo ya
  existía, sólo actualiza la nota).
- Todo lo que **estaba guardado y quedó destildado** se borra.

### Protección contra ciclos

Antes de guardar cada vínculo nuevo, el sistema chequea que agregarlo no
cierre un ciclo (que la señal hija termine siendo, directa o
indirectamente, ancestro de su propio padre nuevo). Si un vínculo
cerraría un ciclo:
- **Ese vínculo puntual no se guarda.**
- El resto de los vínculos tildados **sí se guardan normalmente** — el
  chequeo es por fila, no aborta todo el guardado.
- Se muestra un aviso con el nombre de la señal en conflicto.

---

## 6. Ver el árbol completo de linaje

Botón **🌳 Ver árbol de linaje** (dentro del editor) abre una ventana de
**solo lectura** con la señal actual como raíz y dos ramas:

- **⬆ Deriva de…** — los padres, recursivo hacia arriba.
- **⬇ Usada en…** — en qué otras señales se usa ésta como insumo
  (hijos), recursivo hacia abajo.

Es un árbol de **texto**, con carga perezosa (lazy-load): cada rama
arranca colapsada con un placeholder "…", y se completa recién al
expandirla — así una señal con un árbol grande no tarda en abrirse. Cada
nodo muestra el nombre de la señal y, si tiene, su nota entre guiones.

Este árbol se puede abrir directamente sobre cualquier señal desde el
catálogo (**Catálogos → 📡 Señales → 🧬 Linaje… → 🌳 Ver árbol de
linaje**) — no hace falta pasar por el editor de padres si sólo querés
consultar, sin editar.

---

## 7. Modelo de datos, por si hace falta consultarlo directo

Tabla `senal_linaje`, un vínculo por fila (`id_senal_hijo`,
`id_senal_padre`, `nota` opcional, `fecha_ultima_edicion`), con
`UNIQUE(id_senal_hijo, id_senal_padre)` — no puede haber dos vínculos
iguales, sólo se actualiza la nota si ya existía. Los métodos relevantes
están en `modelo.py` (`Modelo.devolver_padres_de_senal`,
`devolver_hijos_de_senal`, `hay_ciclo_linaje`, `agregar_linaje`,
`quitar_linaje`, `sugerir_padres_de_senal`), y la tabla se crea sola
(idempotente) la primera vez que se usa cualquiera de esos métodos — no
hace falta ninguna migración manual.

---

## Si algo no funciona como se espera

- Si no ves el botón "🧬 Linaje…" en el catálogo de Señales, confirmá que
  estás en **Catálogos → 📡 Señales**, no en "📡 Formatos de Señal"
  (catálogo distinto, sin linaje).
- Si "🔄 Volver a sugerir" no trae nada nuevo, es porque el algoritmo
  sólo mira salidas (OUT) con carga **MANUAL** — una señal propagada
  automáticamente en una salida no cuenta para sugerir.
- Recordá: cargar o vaciar el linaje **no cambia nada** en Impacto,
  Escenario, Riesgo de señal ni en ningún overlay del Diagrama de
  conexiones — es sólo documentación. Si buscás algo que sí afecte esos
  cálculos, lo que corresponde tocar es la carga real de señal en los
  conectores (MANUAL/PROPAGADA), no el linaje.
