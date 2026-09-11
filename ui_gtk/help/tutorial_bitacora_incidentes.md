# Tutorial: Bitácora de Incidentes (CableDoc)

La Bitácora de Incidentes permite registrar fallas reales que ocurrieron en
equipos, cables y "zonas sospechosas" (racks o sectores propensos a
problemas), además de marcar conectores/cables/conexiones cuyo armado se
detectó incorrecto. Esta información alimenta el **score de riesgo
analógico**, que clasifica cada equipo/cable/zona en un nivel **BAJO /
MEDIO / ALTO** según la cantidad y antigüedad de los incidentes, y según si
tiene armados marcados como incorrectos.

> 📌 Estado actual: el registro de incidentes, las zonas sospechosas y el
> marcado de armado ya están operativos. El overlay "🌡 Zona caliente" en el
> diagrama y el panel de pendientes en el Home (Fase D del plan) todavía no
> están conectados a la interfaz — el cálculo del score existe en
> `riesgo_analogico.py` pero por ahora solo se consume internamente.

---

## 1. Cómo acceder a la bitácora

Hay dos caminos, según de dónde vengas:

**A) Desde un equipo o cable puntual**
1. Abrí el listado de **Equipos** o de **Cables**.
2. Seleccioná una fila (un equipo o un cable puntual).
3. Hacé clic en el botón **"📋 Ver incidentes"** de la barra de botones.

Se abre la ventana **"📋 Bitácora de incidentes"**, filtrada automáticamente
por ese equipo o cable. Si el equipo pertenece a una **zona sospechosa**,
el listado también incluye los incidentes cargados a nivel de esa zona
(no hace falta que estén cargados equipo por equipo).

**B) Desde una zona sospechosa, sin pasar por ningún equipo**
1. Menú **Catálogos → "📋 Zonas sospechosas (bitácora)"**.
2. Seleccioná la zona en el listado.
3. Hacé clic en **"📋 Ver incidentes"** (o doble clic sobre la fila).

Este segundo camino es el que conviene usar cuando el problema es de toda
una zona y no de un equipo puntual en particular — ver punto 4.

---

## 2. El listado de incidentes

La ventana muestra una tabla con **Fecha**, **Resumen** y **Estado**, y un
campo de **Filtro** arriba que busca en tiempo real a medida que escribís
(sobre fecha, resumen y relato).

Botones disponibles:

- **➕ Nuevo incidente** — abre el formulario de carga.
- **✏️ Editar** — edita el incidente seleccionado (también funciona con
  doble clic sobre la fila).
- **🗑 Eliminar** — borra el incidente seleccionado, previa confirmación.

Si todavía no hay incidentes cargados para ese equipo/cable, la tabla
muestra una única fila: *"(sin incidentes registrados todavía)"*.

---

## 3. Cargar un incidente nuevo

Al hacer clic en **➕ Nuevo incidente** se abre un formulario con:

| Campo | Detalle |
|---|---|
| **Fecha y hora** | Formato `AAAA-MM-DD HH:MM:SS`. El botón **"Hoy"** completa la fecha/hora actual automáticamente. |
| **Resumen** | Texto corto, obligatorio junto con la fecha para poder guardar. |
| **Estado** | `Mitigado (puede volver)` o `Resuelto`. |
| **Relato** | Cuadro de texto libre — pensado para pegar el reporte tal cual llegó (mail, WhatsApp, parte del operador, etc.). Es opcional. |
| **Equipos / Cables / Zonas** | Tres selectores independientes con botones ➕/➖, para asociar el incidente a uno o varios equipos, cables y/o zonas sospechosas a la vez. |

Si abriste la bitácora desde un equipo, cable o **zona** puntual (los tres
caminos del punto 1), ese equipo/cable/zona ya viene precargado en el
selector correspondiente al crear un incidente nuevo — solo hace falta
agregar los adicionales si aplica. Los tres selectores son independientes:
**un incidente se puede guardar con solo una zona asociada, sin ningún
equipo ni cable** (por ejemplo, "se cortó el audio en todo el rack, no se
identificó todavía qué equipo puntual falló").

Para asociar equipos o cables, el botón ➕ de cada selector abre el listado
correspondiente de CableDoc en modo selección; para zonas, abre el
selector de zonas sospechosas (ver punto 4).

Un incidente no queda guardado hasta hacer clic en **Aceptar**, y requiere
como mínimo **fecha** y **resumen** completos — el resto (relato, equipos,
cables, zonas) es opcional.

---

## 4. Zonas sospechosas

Una **zona sospechosa** es un grupo reutilizable de equipos (por ejemplo,
"Rack de continuidad piso 3" o "Sala de máquinas — cadena analógica") al
que se le pueden cargar incidentes en conjunto, sin tener que repetir la
carga equipo por equipo.

### Ver, crear, editar y eliminar zonas — menú Catálogos

Menú **Catálogos → "📋 Zonas sospechosas (bitácora)"** abre el listado
general de zonas, con columnas **ID / Nombre / Equipos** (esta última
muestra cuántos equipos tiene cada zona) y estos botones:

- **➕ Nueva zona…** — abre el diálogo de alta (ver abajo).
- **✏️ Editar** — edita la zona seleccionada.
- **🗑 Eliminar** — borra la zona seleccionada, previa confirmación. Los
  incidentes que la tenían asociada **no se borran**, solo pierden esa
  asociación puntual (si además estaban asociados a un equipo o cable,
  esos vínculos quedan intactos).
- **📋 Ver incidentes** — abre la bitácora filtrada por esa zona (también
  funciona con doble clic sobre la fila). Es el mismo listado que ya
  conocés del punto 2, desde acá con el botón **➕ Nuevo incidente**
  precargando la zona automáticamente.

Este es el lugar recomendado para revisar de un vistazo qué zonas existen
y cuántos incidentes/equipos tiene cada una, sin tener que recordar a qué
equipo puntual pertenecen.

### Elegir o crear una zona al cargar un incidente

Alternativamente, si estás dentro del formulario de un incidente, al
presionar ➕ en el selector de **Zonas** se abre el diálogo **"Elegir zona
sospechosa"**:

- Seleccioná una zona existente de la lista y presioná **"✔ Usar"** (o
  doble clic).
- O hacé clic en **"➕ Nueva zona…"** para crear una zona nueva sin salir
  del flujo: se abre el diálogo de alta, y al aceptar queda
  automáticamente seleccionada.

### Crear/editar una zona directamente

El diálogo **"Nueva zona sospechosa"** (o "Editar zona") pide:

- **Nombre** de la zona.
- Lista de **equipos que componen la zona**, con los mismos botones ➕/➖
  para agregar o quitar equipos (el ➕ abre el listado de equipos en modo
  selección).

Al guardar, los equipos agregados/quitados se sincronizan contra los que
ya tenía la zona (solo se aplican los cambios, no se recrea la lista
completa).

---

## 5. Marcar el "Armado" de un conector, cable o extremo

Independientemente de los incidentes, la bitácora también permite marcar
si un **armado físico** (soldadura/cableado de un conector o cable) está
verificado como correcto o incorrecto. Esto es útil para detectar, por
ejemplo, un jack TS cableado como si fuera un XLR balanceado.

Esta sección aparece **dentro de los diálogos ya existentes**, no en la
bitácora:

- **Ficha de Conector** → sección **"Armado"**, con:
  - **¿Armado correcto?:** `No verificado` / `Correcto` / `Mal armado`.
  - **Detalle:** texto libre para anotar qué se encontró mal.
- **Ficha de Cable** → misma sección **"Armado"**, a nivel del cable
  completo.
- **Ficha de Conexión** (extremo de un cable) → sección
  **"Armado de esta punta"**, para marcar un extremo específico cuando un
  mismo cable tiene un lado bien armado y el otro no (el armado a nivel
  cable completo no puede distinguir cuál extremo es el problemático).

Marcar algo como **"Mal armado"** suma peso al score de riesgo del equipo
o cable correspondiente (ver punto 6), sin necesidad de cargar también un
incidente en la bitácora — son dos fuentes de riesgo independientes que se
combinan.

---

## 6. Cómo se calcula el nivel de riesgo (BAJO / MEDIO / ALTO)

Aunque todavía no hay un overlay visual en el diagrama, vale entender la
lógica porque explica por qué un incidente "viejo" pesa menos que uno
reciente:

- Cada **incidente** dentro de una ventana de tiempo configurable (por
  defecto, últimos 12 meses) aporta un puntaje que **decae linealmente**:
  un incidente de hoy aporta el peso completo, uno justo en el borde de la
  ventana aporta casi cero. Los incidentes más viejos que la ventana no
  cuentan.
- Cada **conector, cable o extremo marcado como "Mal armado"** aporta un
  peso fijo, una sola vez por equipo/cable/zona afectado.
- Un incidente cargado a una **zona** también "calienta" a cada equipo que
  pertenezca a esa zona.
- La suma de todos estos aportes es el **score**. Según dos cortes
  configurables (`corte_medio` y `corte_alto`), el score se traduce en
  nivel `BAJO`, `MEDIO` o `ALTO`.

Estos parámetros (ventana en meses, peso por incidente, peso por armado
incorrecto, y los dos cortes) son ajustables desde un diálogo de
configuración (`_DialogoConfigRiesgoAnalogico` en `bitacora_ui.py`), pero
por ahora ese diálogo no está enganchado a ningún botón o menú de
`cabledoc.py` — es un punto pendiente para cuando se conecte la Fase D
(overlay de zona caliente).

---

## 7. Resumen rápido de flujo

1. Detectaste una falla real en un equipo o cable puntual → abrilo →
   **"📋 Ver incidentes"** → **➕ Nuevo incidente** → completá fecha,
   resumen y (opcional) relato → asociá equipos/cables/zonas adicionales
   si corresponde → **Aceptar**.
2. Detectaste una falla de una **zona** (rack/sector), sin un equipo
   puntual identificado todavía → **Catálogos → "📋 Zonas sospechosas
   (bitácora)"** → elegí (o creá) la zona → **"📋 Ver incidentes"** →
   **➕ Nuevo incidente** → la zona ya viene precargada, no hace falta
   agregar equipo ni cable → **Aceptar**.
3. Detectaste un armado mal hecho en un conector/cable/extremo → abrí su
   ficha → sección **"Armado"** → marcá **"Mal armado"** y describí el
   detalle.
4. Si varios equipos comparten un problema recurrente de zona → creá una
   **zona sospechosa** una vez (desde Catálogos o desde el selector de un
   incidente), agrupando los equipos, y cargá los incidentes futuros sobre
   esa zona en lugar de repetirlos equipo por equipo.
5. ¿Necesitás ver de un vistazo todas las zonas que existen y cuántos
   equipos/incidentes tiene cada una? **Catálogos → "📋 Zonas sospechosas
   (bitácora)"**.
