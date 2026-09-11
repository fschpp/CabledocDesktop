# Extensiones de cable

## ¿Qué es una extensión?

En la cadena analógica de audio/video es común que un cable no llegue
directo a un equipo, sino que se empalme **ficha contra ficha** con otro
cable — por ejemplo, un XLR macho suelto que se enchufa directamente a la
ficha de otro tramo, sin ningún equipo ni barril de por medio, en algún
punto intermedio del recorrido (detrás de un zócalo, dentro de un rack,
etc.).

Antes de esta funcionalidad, esos tramos intermedios no tenían dónde
cargarse en CableDoc: todo extremo de cable estaba obligado a terminar en
el conector de un equipo real. Una **Extensión** es justamente eso: el
punto donde dos cables se empalman directamente entre sí.

> **Caso real que motivó esta funcionalidad:** `DDA 04 ESTUDIO` (OUT 3) →
> `MONITOR DIRECTOR CAMARA ESTUDIO` (Roland MA-12C), en 3 tramos de cable
> unidos por 2 extensiones. Sin esta funcionalidad, ninguno de los 3
> tramos podía cargarse. Más abajo hay una guía completa, paso a paso,
> cargando exactamente este caso.

### Qué NO es una extensión

- **No es un empalme con barril/coupler físico** — ese es un objeto
  distinto y se sigue cargando como hasta ahora.
- **No sirve para 3 o más cables en un mismo punto** (cajas de empalme).
  Una extensión es siempre 1 a 1: dos fichas, dos cables. Si tenés una
  caja de empalme con varios tramos, consultá con Papi antes de forzar el
  dato en una extensión.

## Cómo cargar una extensión

### Opción 1 — Desde la ficha de un Cable (la forma más rápida)

1. Abrí la ficha del cable que termina en el punto suelto (Cable A).
2. Hacé clic en el botón **🔗 Extender con otro cable**.
3. Elegí el extremo del **Cable A**:
   - Si el cable ya tiene una punta suelta cargada, aparece en la lista
     para elegirla.
   - Si no la tiene todavía, tocá **➕ Crear extremo nuevo…** y elegí qué
     ficha física tiene esa punta (XLR3, TRS, etc.) — o dejalo "sin
     especificar" si todavía no lo relevaste con precisión.
4. Elegí el extremo del **Cable B** de la misma forma. Acá sí podés
   buscar cualquier cable de la base, no solo el que abriste.
5. Completá, si los tenés:
   - **Rack** / **Sala**: dónde físicamente está el empalme.
   - **Posición libre**: texto libre para ubicarlo cuando no hay rack ni
     sala cargados (ej. *"detrás del zócalo 4"*).
6. Marcá el **Armado** de la extensión si ya la revisaste:
   - *No verificado*: todavía no se chequeó.
   - *Correcto*: el empalme está bien armado.
   - *Mal armado*: hay un problema (podés escribir el detalle, ej.
     "empalme sin continuidad de malla").
7. Tocá **Aceptar**.

### Opción 2 — Desde el catálogo general

Menú **Catálogos → 🔗 Extensiones de cable**. Ahí podés:

- Ver todas las extensiones cargadas (con sus dos cables, rack/sala,
  posición y estado de armado).
- Crear una nueva extensión sin partir de la ficha de un cable puntual
  (elegís los dos extremos "desde cero").
- Editar la ubicación/armado de una extensión existente.
- Eliminarla — **esto no borra los cables ni sus fichas**, solo el
  registro de que estaban empalmados; las dos puntas quedan disponibles
  como extremos sueltos para volver a usarse en otra extensión.

> **Importante:** una vez creada la extensión, no se puede "reasignar" a
> otro cable desde la edición. Si te equivocaste de cable, eliminá la
> extensión y cargá una nueva.

## 🔗 Ver cadena completa

Cuando armás una cadena de varios tramos, es fácil perder de vista "qué
quedó unido con qué" en el medio del proceso — sobre todo si vas cable por
cable, en sesiones separadas. Para eso existe **Ver cadena completa**:
resuelve y muestra el recorrido real de punta a punta, atravesando todas
las extensiones intermedias, hasta llegar al equipo real de cada lado (o
hasta un extremo suelto, si la cadena todavía está incompleta de ese
lado).

**Dónde encontrarla:**

- **Automáticamente**, apenas tocás **Aceptar** al crear o editar una
  extensión — así confirmás en el momento qué quedó armado, sin tener que
  ir a buscarlo después.
- Botón **🔗 Ver cadena completa** en la ficha de cualquier Cable
  (junto a "Extender con otro cable").
- Botón **🔗 Ver cadena completa** en **Catálogos → Extensiones de
  cable**, sobre la extensión seleccionada en la lista.

No hace falta abrirla desde una punta: funciona igual partiendo de
cualquier cable que forme parte de la cadena, sea el primero, el del
medio o el último.

**Cómo leer lo que muestra:**

```
DDA 04 ESTUDIO  —  OUT 3
    │ cable MONITOR C11 DIR CAMARA
🔗 Extensión #3 (detras de escritorio computadoras) — no verificado
    │ cable CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A ADAPTADOR
🔗 Extensión #4 (cerca del monitor de audio director de camara) — no verificado
    │ cable CABLE SN ADAPTADOR XLR3 A PLUG TS
MONITOR DIRECTOR CAMARA ESTUDIO  —  INPUT JACK 3
```

- Las líneas en **negrita** con nombre de equipo son las puntas reales
  (donde el cable termina en un conector de verdad).
- Cada `🔗 Extensión #N` es un empalme ficha-contra-ficha, con su
  ubicación y estado de armado.
- Si en algún momento ves **"⚠ extremo suelto — la cadena termina acá,
  sin llegar a un equipo"**, significa que ese lado todavía no está
  terminado: falta crear la siguiente extensión o conectar esa punta a un
  equipo real.

## Armado y riesgo

Una extensión mal armada es su **propio punto de falla** — no depende de
si el equipo aguas abajo está bien o mal. Si la marcás como *Mal armado*:

- Suma su propio peso al score de riesgo analógico (igual que un
  conector o un cable mal armado).
- Además "calienta" a los dos cables empalmados, para que también
  aparezcan señalados como afectados en los listados/reportes de riesgo
  existentes.

## Ejemplo completo, paso a paso: `DDA 04 ESTUDIO` → Monitor Roland (3 tramos)

Este es el caso real que motivó la funcionalidad, cargado de punta a
punta. Los 3 cables:

| Cable | Extremo real | Extremo suelto (ficha) |
|---|---|---|
| **A** — `MONITOR C11 DIR CAMARA` | `DDA 04 ESTUDIO` → `OUT 3` | XLR3 macho |
| **B** — `CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A ADAPTADOR` | *(ninguno — los dos extremos son sueltos)* | XLR3 hembra en un lado, XLR3 macho en el otro |
| **C** — `CABLE SN ADAPTADOR XLR3 A PLUG TS` | `MONITOR DIRECTOR CAMARA ESTUDIO` → `INPUT JACK 3` | XLR3 hembra |

Van a hacer falta **2 extensiones**: Cable A ↔ Cable B, y Cable B ↔
Cable C. Se supone que el Cable A ya está cargado con su extremo real
conectado a `DDA 04 ESTUDIO OUT 3` (carga normal de conexión, no es parte
de esta guía), y que el Cable C ya está cargado con su extremo real
conectado a `MONITOR DIRECTOR CAMARA ESTUDIO INPUT JACK 3`. El Cable B
puede existir de antemano en la base (sin conexiones todavía) o crearse
sobre la marcha desde el selector — ambos casos funcionan igual.

### Paso 1 — Primera extensión: Cable A ↔ Cable B

1. Abrí la ficha del **Cable A** (`MONITOR C11 DIR CAMARA`) y hacé clic
   en **🔗 Extender con otro cable**.
2. Se abre el diálogo **"Nueva Extensión de Cable"**. Como el Cable A
   tiene exactamente una punta suelta, el sistema la resuelve solo — vas
   a ver directamente la etiqueta:
   *"Primer cable: MONITOR C11 DIR CAMARA (XLR3 MALE JACK CABLE)"*, sin
   que te pregunte nada más para ese lado. (Si el cable tuviera 2 o más
   puntas sueltas, ahí sí te pediría elegir cuál con el selector manual.)
3. Para el segundo cable, tocá **🔍 Elegir el otro cable…**.
4. Se abre el selector de cables — buscá y elegí `CABLE AUDIO SN ALARGUE
   DE MONITOR C11 DIR CAMARA A ADAPTADOR` (Cable B).
5. Como el Cable B todavía no tiene ninguna punta suelta cargada, tocá
   **➕ Crear extremo nuevo…**.
6. Se abre **"Ficha de este extremo"**: elegí **XLR3 FEMALE JACK
   CABLE** (tiene que "matchear" con el macho del Cable A) y tocá
   **Aceptar**.
7. Volvés al diálogo de la extensión con ambos extremos ya cargados:
   *"Primer cable: MONITOR C11 DIR CAMARA (XLR3 MALE JACK CABLE)"* /
   *"Segundo cable: CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A
   ADAPTADOR (XLR3 FEMALE JACK CABLE)"*.
8. En **Sala**, elegí `CONTROL ESTUDIO`. Dejá **Rack** sin asignar (este
   empalme no está en un rack).
9. En **Posición libre**, escribí `detras de escritorio computadoras`.
10. En **Armado**, si todavía no lo revisaste a mano, dejalo en *No
    verificado*.
11. Tocá **Aceptar**.
12. Se cierra el diálogo y **se abre automáticamente "Ver cadena
    completa"**, mostrando lo que ya quedó armado:

    ```
    DDA 04 ESTUDIO  —  OUT 3
        │ cable MONITOR C11 DIR CAMARA
    🔗 Extensión #3 (detras de escritorio computadoras) — no verificado
        │ cable CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A ADAPTADOR
    ⚠ extremo suelto — la cadena termina acá, sin llegar a un equipo
    ```

    Esto es esperable: todavía falta la segunda extensión, así que el
    lado del Cable B que va hacia el Roland aparece como "extremo
    suelto". Tocá **Cerrar**.

### Paso 2 — Segunda extensión: Cable B ↔ Cable C

1. Abrí la ficha del **Cable B** (`CABLE AUDIO SN ALARGUE DE MONITOR C11
   DIR CAMARA A ADAPTADOR`) y tocá **🔗 Extender con otro cable**.
2. El Cable B ahora tiene exactamente una punta suelta libre (la que da
   hacia el Roland — la otra ya está tomada por la Extensión #3 del paso
   anterior), así que de nuevo se resuelve sola:
   *"Primer cable: CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A
   ADAPTADOR (XLR3 MALE JACK CABLE)"*.
3. Tocá **🔍 Elegir el otro cable…** y elegí `CABLE SN ADAPTADOR XLR3 A
   PLUG TS` (Cable C).
4. El Cable C ya tiene su extremo suelto cargado (XLR3 hembra), así que
   aparece directo en la lista para elegirlo — no hace falta crear uno
   nuevo. Seleccionalo y tocá **Usar seleccionado**.
5. En **Sala**, elegí `CONTROL ESTUDIO` de nuevo.
6. En **Posición libre**, escribí `cerca del monitor de audio director de
   camara`.
7. Dejá **Armado** en *No verificado* (o marcalo si ya lo revisaste).
8. Tocá **Aceptar**.
9. Se abre **"Ver cadena completa"** de nuevo, ahora mostrando el
   recorrido entero, de punta a punta:

    ```
    DDA 04 ESTUDIO  —  OUT 3
        │ cable MONITOR C11 DIR CAMARA
    🔗 Extensión #3 (detras de escritorio computadoras) — no verificado
        │ cable CABLE AUDIO SN ALARGUE DE MONITOR C11 DIR CAMARA A ADAPTADOR
    🔗 Extensión #4 (cerca del monitor de audio director de camara) — no verificado
        │ cable CABLE SN ADAPTADOR XLR3 A PLUG TS
    MONITOR DIRECTOR CAMARA ESTUDIO  —  INPUT JACK 3
    ```

    Ya no hay ningún "extremo suelto": los 3 tramos quedaron unidos de
    `DDA 04 ESTUDIO` hasta el Roland. Tocá **Cerrar** — la carga está
    completa.

### Después de cargarla

- Podés volver a ver esta misma cadena en cualquier momento con **🔗 Ver
  cadena completa**, desde cualquiera de los 3 cables o desde el
  catálogo de Extensiones — no hace falta recordar por cuál empezar.
- Si más adelante revisás físicamente el empalme y confirmás que está
  bien (o mal) armado, editá la extensión correspondiente desde
  **Catálogos → Extensiones de cable** y actualizá el campo **Armado**.

## Fase 3 — Propagación de señal, impacto y diagrama

Las extensiones ya no son un dato "aislado": ahora forman parte de la
cadena real a los efectos de tres funcionalidades existentes, cruzando
el empalme como un tramo más.

### En el Diagrama de conexiones

Cuando los dos equipos reales de una cadena (el primero y el último, los
que sí tienen conector) están cargados en el canvas, el diagrama dibuja
el recorrido completo con un **rombo pequeño en cada punto de
extensión**, en vez de mostrar el cable "de un tirón" o directamente no
mostrarlo:

```
[DDA 04 ESTUDIO] ┄┄┄◇┄┄┄◇┄┄┄ [MONITOR DIRECTOR CAMARA]
                Ext.#3   Ext.#4
```

Cada tramo entre rombos es un cable físico distinto (se ven los 3 tramos
por separado, no un salto único de punta a punta), y cada rombo muestra
su etiqueta `Extensión #N` al pasar el mouse cerca. Si alguno de los dos
extremos reales de la cadena todavía no está en el canvas, esa cadena
simplemente no se dibuja todavía — agregá el equipo que falta y
aparece sola.

> **Limitación conocida:** esta capa es sólo visual por ahora. Los
> tramos vía extensión todavía no participan de riesgo, escenarios,
> búsqueda ni exportación del diagrama — sólo se ven en pantalla.

### En "Simular remoción" (impacto)

El motor de impacto (`graph_impact.py`) ahora atraviesa las extensiones
igual que atraviesa un conector o un equipo intermedio: si cortás
cualquiera de los cables de una cadena empalmada, el cálculo de impacto
sigue correctamente hasta el otro extremo real, en vez de detenerse en
el primer empalme. El punto de extensión en sí no aparece como "equipo
impactado" en los resultados (no es un equipo), pero sí se reporta
correctamente el equipo real del otro lado y los demás cables de la
cadena.

### En la propagación de señal (rol IN/OUT)

El motor de propagación de señal (`senal_propagation.py`) también sigue
la cadena a través de las extensiones: si un equipo real de un extremo
tiene un rol de señal asignado, la propuesta de propagación llega
correctamente hasta el equipo real del otro extremo, atravesando los
tramos y empalmes intermedios.

## Qué todavía no hace esta funcionalidad

- **Los tramos vía extensión, en el diagrama, no participan todavía de
  riesgo, escenarios, búsqueda ni exportación** — sólo se dibujan (ver
  limitación de la sección anterior). Impacto y propagación de señal sí
  los atraviesan a nivel de cálculo, aunque el diagrama no lo refleje en
  esas otras capas todavía.
- **Un incidente de bitácora todavía no se puede asociar directo a una
  extensión** (solo a equipo, cable o zona). Si el problema es
  específicamente el empalme, anotalo en el detalle de armado de la
  extensión, o cargá el incidente contra uno de los dos cables.

Esto está anotado como trabajo pendiente y se agregará en una próxima
entrega.
