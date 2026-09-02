# Riesgo de Señal y Armado por Extremo — Guía de uso

Esta guía cubre dos funcionalidades nuevas de CableDoc que trabajan juntas
pero responden preguntas distintas:

| | **Riesgo de Señal** | **Armado (por extremo)** |
|---|---|---|
| ¿Qué responde? | "¿Esta cadena *debería* funcionar bien, según lo que sé de sus componentes?" | "¿Alguien *ya abrió* esta ficha y confirmó que está mal armada?" |
| ¿De dónde sale el dato? | Predicción, a partir de catálogo (tipo de cable, tipo de ficha) | Hecho observado, cargado a mano tras inspección física |
| ¿Dónde vive en el código? | `signal_risk.py` | `riesgo_analogico.py` + `bitacora_ui.py` |
| ¿Puede haber falso negativo? | Sí, si el catálogo no está cargado | No — es un hecho constatado |

Ninguna reemplaza a la otra. Un cable puede pasar todos los chequeos de
Riesgo de Señal (porque el catálogo dice que XLR3↔TRS es compatible) y aun
así estar mal armado por dentro — eso solo se sabe abriéndolo.

---

## Parte 1 — Riesgo de Señal (predicción desde catálogo)

### 1.1 Qué mide

Tres ejes **independientes** (nunca se mezclan en un solo puntaje, porque
cada uno se arregla distinto):

1. **Atenuación** — un tramo analógico demasiado largo para su tipo de cable.
2. **Cuello de botella** — un cable con mucho menos ancho de banda que sus
   vecinos en la misma cadena (típicamente, un patchcord viejo colado entre
   equipos modernos).
3. **Mismatch de formato** — incompatibilidad entre los dos extremos de un
   cable: eléctrico (cortocircuito por diferencia de conductores), de
   balance, o de canal.

### 1.2 Paso 1: cargar el catálogo

Sin esto, el analizador no encuentra nada (a propósito: no se auto-estima
ningún valor, solo vos sabés las especificaciones reales de tu equipamiento).

**Catálogos → Tipos de Cable** (nuevo/editar):
- Naturaleza de la señal (analógica / digital / híbrida / datos)
- Longitud máxima recomendada — balanceado y desbalanceado (dos valores
  separados, porque un tramo desbalanceado tolera menos distancia)
- Ancho de banda nominal (MHz)

**Catálogos → Tipos de Ficha** (nuevo/editar):
- Cantidad de conductores (2 = TS, 3 = XLR3/TRS, etc.)
- Balance por defecto (balanceado / desbalanceado / no aplica)
- Canal por defecto (mono / estéreo / no aplica)

> **Nota sobre fichas ambiguas (TRS):** un plug TRS físicamente puede ser
> estéreo desbalanceado *o* mono balanceado — el mismo conector, dos
> significados eléctricos distintos. El valor de "Tipos de Ficha" es solo el
> *default*; si un jack puntual es la excepción, cargale el override ahí
> mismo (ver 1.3).

### 1.3 Paso 2: declarar qué ficha es cada jack real

En la ficha de un equipo (**Editar Conector**), sección **"Formato
eléctrico"**:
- **Ficha (qué es eléctricamente):** a qué tipo de ficha del catálogo
  corresponde este jack.
- **Balance / Canal (override):** solo si este jack puntual no sigue el
  default de su ficha (vacío = usar el default).

### 1.4 Paso 3 (opcional, solo si el cable trae fichas distintas en cada punta)

Un cable puede tener XLR3 macho de un lado y TRS del otro — eso no se puede
declarar en un solo campo. Para ese caso, andá a **Conexiones** → editar la
conexión puntual → **"Ficha del cable en esta punta"**. Sin esto cargado, el
chequeo eléctrico cae a comparar los dos jacks entre sí (más pobre, pero
sigue funcionando).

### 1.5 Dónde ver los resultados

- **Panel principal**, sección "Trabajo pendiente — Riesgo de señal": tres
  contadores (uno por eje), con un botón "ver →" en cada uno.
- **Listado filtrable**: doble click en cualquier fila abre el cable
  directamente para corregirlo.
- **Diagrama de Conexiones** → menú **Riesgo** → *"🎨 Colorear por riesgo de
  señal"*: pinta los cables en naranja (atenuación), ámbar (cuello de
  botella) o rojo (mismatch de formato). Pasa el mouse sobre un cable
  coloreado para ver el detalle.
- **Consola Cypher**: las aristas `CABLE` exponen `naturaleza_senal` y
  `ancho_banda_mhz`, consultables directo (`MATCH ()-[r:CABLE]->() WHERE
  r.naturaleza_senal='ANALOGICA' RETURN r`).

### 1.6 Ancho de banda: cuándo usar el override del cable

`Catálogos → Tipos de Cable` define el ancho de banda *nominal* de un tipo.
Si tenés un cable puntual que no representa bien a su tipo (un patchcord
viejo, degradado), no cambies el catálogo entero — editá ese cable puntual
(**Editar Cable → Ancho de banda, override**).

---

## Parte 2 — Armado (hallazgo real de inspección física)

### 2.1 Qué es y en qué se diferencia de Riesgo de Señal

Esto **no predice nada** — es un lugar para anotar lo que *encontraste* al
abrir una ficha: cruce de conductores, orden de pines invertido, dos cables
soldados al mismo orificio, etc. El ejemplo típico: un cable XLR3↔TRS donde,
a simple vista, ambas fichas parecen bien armadas — pero al abrir una de las
dos, el técnico ve que dos conductores quedaron unidos al mismo pin.

### 2.2 Los tres niveles de "Armado" (no confundirlos)

| Nivel | Dónde se carga | Cuándo usarlo |
|---|---|---|
| **Por extremo** (`conexion`) | Editar Conexión → "Armado de esta punta" | **Preferido.** Sabés exactamente cuál de las dos puntas del cable está mal. |
| **Cable completo** | Editar Cable → sección "Armado" | No estás seguro de cuál extremo es, o preferís un chequeo rápido sin abrir la conexión puntual. |
| **Conector del equipo** | Editar Conector → sección "Armado" | El problema es el jack del *equipo*, no la ficha del *cable* que se enchufa en él (son piezas físicas distintas). |

Los tres son independientes y se **suman** (no se pisan): si marcás mal
armado tanto el cable completo como uno de sus extremos, ambos hallazgos
quedan registrados y ambos suman al puntaje de riesgo.

### 2.3 Cómo cargar un hallazgo por extremo (caso recomendado)

1. Abrí el cable → **🔗 Ver Conexiones**.
2. Doble click en la conexión del extremo que abriste físicamente.
3. Sección **"Armado de esta punta"**:
   - **¿Armado correcto?:** No verificado / Correcto / Mal armado
   - **Detalle:** texto libre — anotá qué encontraste
     (ej. *"cruce de conductores, pin 2 y 3 al mismo orificio"*)
4. Guardar.

Este hallazgo queda ligado a esa conexión puntual. Si más adelante movés el
cable a otro equipo, **no se pierde** — el vínculo con el conector es solo
de referencia histórica.

### 2.4 Dónde impacta

`riesgo_analogico.py` combina automáticamente:
- Incidentes de la bitácora (con decaimiento por antigüedad — un incidente
  de hace 11 meses pesa casi nada si la ventana configurada es 12 meses).
- Armado incorrecto, en cualquiera de los tres niveles de la tabla de 2.2.

Esto sube el **nivel de riesgo** (Bajo/Medio/Alto) del cable, visible en el
overlay del diagrama y en los reportes de bitácora existentes
(`bitacora_ui.py`).

### 2.5 Tipos de falla frecuentes (para el campo Detalle)

No hay un combo cerrado para esto — es texto libre — pero como referencia,
las categorías típicas de una ficha mal armada son:

- **Cruce de conductores**: dos cables terminan soldados al mismo pin/orificio.
- **Orden de pines invertido**: hot/cold (o L/R) cruzados.
- **Cortocircuito interno**: dos conductores en contacto que no deberían.
- **Soldadura fría**: contacto intermitente, falla difícil de reproducir en banco.

---

## Resumen — ¿Cuál uso primero?

- Si estás documentando el equipamiento **antes** de que pase nada (carga de
  catálogo, planificación): **Riesgo de Señal**.
- Si estás en el rack, **abriste una ficha** y viste algo mal: **Armado**
  (preferentemente por extremo, en Conexiones).
- Si algo falló en el aire y no sabés todavía la causa: cargalo primero como
  **Incidente** en la bitácora (`bitacora_ui.py`) — si después de investigar
  resulta ser una ficha mal armada, complementá con el Armado correspondiente.
