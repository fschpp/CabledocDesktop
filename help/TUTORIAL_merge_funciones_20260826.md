# Funciones incorporadas en el merge del 2026-08-26

Este merge unió dos ramas de desarrollo que habían divergido (ver
`PROGRESS.md` → "Merge de ramas divergentes..." para el detalle técnico
completo) más una feature nueva subida encima. Este tutorial cubre sólo
las funciones **con impacto visible para el usuario**; los fixes internos
(el bug de imports de `i18n.py`, la línea duplicada en el editor clásico)
no cambian nada que se vea en pantalla y no están documentados acá.

---

## 1. Traer equipos conectados al agregar uno nuevo (Alta rápida de conexiones)

**Panel Ver → 🧩 Panel de equipos (buscar / arrastrar)**, dentro de
**Alta rápida de conexiones**.

Al lado del buscador del panel lateral ahora hay un checkbox nuevo:

> ☑ traer con equipos
> conectados

Viene **tildado por defecto**. Con el checkbox tildado, cuando agregás un
equipo **por primera vez** al canvas (por cualquiera de los tres caminos:
arrastrar la fila del panel, doble clic en la fila, o soltar por
drag&drop), CableDoc además agrega automáticamente los equipos que ya
tiene conectados en sus conectores:

- Los conectados a las **entradas (IN)** aparecen apilados a la
  **izquierda** del equipo que acabás de traer.
- Los conectados a las **salidas (OUT)** aparecen apilados a la
  **derecha**.

Ningún equipo se duplica: si un vecino ya estaba en el canvas, se deja
donde está. La barra de estado te confirma cuántos se sumaron, por
ejemplo:

> Equipo agregado: MDK-111A-M (+31 conectado(s))

**Para agregar un equipo solo, sin arrastrar toda su vecindad** —por
ejemplo si estás armando un pedacito puntual del cableado y no querés que
te traiga medio rack— destildá el checkbox antes de agregarlo. Con el
checkbox destildado el comportamiento es el de siempre: sólo se agrega el
equipo elegido.

> 💡 Es un atajo para no tener que agregar el equipo y después usar
> "⊕ Expandir vecinos  (Ctrl+E)" a mano — hace las dos cosas en un solo
> paso, pero sólo la primera vez que el equipo entra al canvas. Si el
> equipo ya está en el canvas y lo volvés a arrastrar o buscar, esto no
> se dispara (para eso seguís teniendo "Expandir vecinos").

---

## 2. Panel de Impacto: la leyenda tacha la señal puntual que cae

**Diagrama de conexiones → ⚡ Analizar Impacto** (sobre un cable), con la
leyenda de colores activa (**Ver → 🎨 Leyenda**).

Antes, cuando una sola señal quedaba caída dentro de un impacto con
varias señales, la leyenda sólo mostraba una entrada genérica "❌ caída"
al final de la lista — no quedaba claro cuál de todas las señales del
recuadro era la afectada.

Ahora cada fila de la leyenda se tacha **individualmente** si esa señal
en particular tiene algún conector afectado por el corte. Si abrís
Impacto sobre un cable y la leyenda está activa, vas a ver de un vistazo
exactamente qué señal(es) se cortan, sin tener que ir fila por fila
comparando contra la lista de "Cables sin señal" del panel.

---

## 3. Vista Previa conviviendo con Impacto y Escenario

**Diagrama de conexiones**, combinando cualquiera de estos tres modos:
**🖼 Vista previa de imagen**, **⚡ Analizar Impacto**, **🎬 Modo
Escenario**.

Antes, activar cualquiera de estos tres apagaba a los otros dos
automáticamente (exclusión mutua). Ahora **conviven los tres al mismo
tiempo**: podés tener Impacto mostrando qué se cae, Vista Previa
mostrando el contenido real del conector, y Escenario armando una
simulación, todo activo a la vez, sin que uno cierre a los otros.

La única forma de salir de Vista Previa sigue siendo destildar
**🖼 Vista previa de imagen** en el menú — ni el clic derecho ni cerrar
un diálogo de conector la cierran sola.

> ⚠️ Caveat conocido, sin resolver todavía: si tenés Escenario en el
> sub-modo "Reconectar virtualmente" **y** Vista Previa activos al mismo
> tiempo, un clic para reconectar puede terminar interceptado por Vista
> Previa en vez de por Escenario. Es un matiz de prioridad de clic entre
> esos dos puntualmente — el resto de las combinaciones no tiene este
> problema.

---

## 4. Precisión del conector culpable extendida a Riesgo y Escenario

**Diagrama de conexiones**, en los botones **"⚡ Simular remoción"** de
**Riesgo de señal** y **Modo Escenario** (y en el diálogo de resultado de
Impacto).

Ya venía funcionando en el overlay de Impacto del diagrama: cuando una
regla lógica de un equipo se rompe por un corte, sólo se marca como
afectado el conector puntual que gobierna esa regla (por ejemplo la
entrada que realmente causó el corte, y la o las salidas que esa regla
gobierna) — no todo el equipo entero, salvo que el equipo haya fallado
por completo.

Ese mismo criterio de precisión ahora está también en los otros tres
lugares donde se simula una remoción: Riesgo de señal, Escenario, y el
diálogo de resultado de Impacto. Antes esos tres podían mostrar más
conectores marcados como afectados de los que realmente correspondían.

---

## 5. Panel de Impacto reordenado

**Diagrama de conexiones → ⚡ Analizar Impacto**.

Con impactos grandes (muchos equipos/cables afectados), el panel
truncaba el texto de "Motivo" y "Señales perdidas" antes de llegar a
mostrarlos completos, porque esas dos secciones se dibujaban DESPUÉS de
las listas de "Equipos sin señal" / "Cables sin señal" (que sí tienen su
propio truncado con "…y N más" cuando no entran).

Ahora "Motivo" y "Señales perdidas" van **primero** en el panel, así que
nunca se cortan en seco — quedan completos siempre, y son las listas de
equipos/cables (que ya tienen su propio manejo de overflow) las que
quedan al final.

> Caso límite que sigue pendiente (no bloqueante): con un impacto MUY
> grande (cientos de equipos), "Cables sin señal" puede terminar
> quedando totalmente afuera del panel visible. La solución de fondo
> (hacer el panel scrolleable en vez de un canvas de tamaño fijo) todavía
> no se decidió si vale la pena.

---

## Si algo no funciona como se espera

- El checkbox "traer con equipos conectados" sólo existe dentro de
  **Alta rápida de conexiones** — el panel de equipos en general no está
  disponible en el Diagrama de conexiones normal (ver
  `TUTORIAL_alta_rapida_conexiones.md`, sección "Diferencia con el
  Diagrama de conexiones normal").
- Si un equipo tiene muchísimos vecinos conectados, "traer con equipos
  conectados" puede llenar el canvas de golpe — usá después
  **🧲 Auto-organizar nodos (sin solape)** (menú Ver, también exclusivo
  de Alta rápida) para acomodarlos sin que se pisen entre sí.
- Estas funciones no se validaron con GTK real en este merge (sin
  Xvfb/Gtk disponible en el entorno donde se hizo) — sólo con
  `py_compile`/`ast.parse` y revisión manual de los símbolos cruzados
  entre archivos. Si algo se ve raro en pantalla, es el primer lugar
  para mirar.
