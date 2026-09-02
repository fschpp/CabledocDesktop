# Alta rápida de conexiones

**Menú Cableado → ⚡ Alta rápida de conexiones…**

Es la forma más rápida de cablear equipos en CableDoc: un canvas en blanco
donde arrastrás los equipos que necesitás, y después arrastrás de un
conector a otro para crear el cable entre ellos.

Desde la sesión del 2026-08-26, esta pantalla **reutiliza el Diagrama de
conexiones** (la misma vista que usás normalmente para ver todo el
cableado ya cargado), en vez de un editor aparte. Arranca **vacía** —sin
ningún equipo dibujado— para que sea rápido armar sólo el pedacito que te
interesa cablear en ese momento, con todas las herramientas del Diagrama
disponibles (zoom, buscador, exportar, impacto, señal, etc.).

> El editor de nodos original ("editor clásico") sigue en el código pero
> quedó **deshabilitado** en el menú — ver el ítem gris "Alta rápida de
> conexiones (editor clásico)…" con el tooltip que lo explica. No hace
> falta usarlo; se documenta acá el reemplazo.

---

## 1. Agregar equipos al canvas

Al abrir la pantalla no hay nada dibujado. Para traer un equipo:

1. Abrí el menú **Ver → 🧩 Panel de equipos (buscar / arrastrar)** (o
   dejalo abierto, queda recordado dentro de la sesión).
2. Escribí nombre, tipo o marca en el buscador del panel lateral.
3. **Arrastrá** la fila del equipo hasta el canvas — queda agregado en el
   punto donde soltaste el mouse.
   - Alternativa sin arrastrar: **doble clic** en la fila agrega el equipo
     centrado en la vista actual.
   - También podés usar **Buscar → ➕ Agregar equipo al diagrama…** para
     el mismo resultado desde un diálogo modal.

Repetí para cada equipo que necesites cablear. Los equipos ya agregados no
se duplican: si volvés a arrastrar uno que ya está en el canvas, sólo lo
selecciona.

---

## 2. Crear una conexión arrastrando de un conector a otro

Con dos o más equipos en el canvas, para cablearlos:

1. Hacé clic y **arrastrá desde el círculo de un conector** (entrada IN a
   la izquierda del nodo, salida OUT a la derecha) del primer equipo.
2. Mientras arrastrás, se dibuja un cable "elástico" amarillo que sigue al
   cursor.
3. Soltá **sobre el conector del otro equipo**.

Al soltar se abre un popup para indicar el cable:

- **Buscar un cable existente** escribiendo su código, y usar **✔ Usar
  seleccionado** (o doble clic en la fila).
- O escribir un código nuevo y usar **✚ Crear cable** para darlo de alta
  en el momento.

Al confirmar, CableDoc crea las dos conexiones (una en cada conector) con
ese cable.

> Si soltás en el vacío (fuera de cualquier conector), o sobre el mismo
> conector del que arrancaste, no pasa nada: se cancela el arrastre sin
> cambios.

### Si el conector de destino ya tenía una conexión

CableDoc avisa antes de pisarla:

```text
El conector de destino ya tiene una conexión
[Equipo] · [Conector] ya está conectado (cable XXXX).
Esa conexión existente se eliminará y se creará la nueva conexión en su
lugar. ¿Continuar?
```

Confirmando, la conexión vieja de ese conector se borra y queda la nueva
en su lugar. El otro extremo del cable reemplazado no se toca.

---

## 3. Completar una conexión incompleta arrastrando (sin buscar/crear cable)

Si venís relevando de a poco y ya tenés cables documentados de un solo
lado (ver **TUTORIAL_conexiones_incompletas.md**), Alta rápida de
conexiones te deja **terminarlos con el mismo gesto de arrastre**, sin
tener que buscar el código del cable a mano:

1. Activá **Ver → Mostrar todas las conexiones incompletas**. Vas a ver
   los tramos naranjas punteados con el cono en la punta pendiente de
   cada equipo que tenga cables a medio documentar.
2. Arrastrá **desde el conector que tiene el cono** (el extremo ya
   documentado) hasta el conector del equipo que en realidad es la otra
   punta.
3. Soltá.

En este caso **no aparece el popup de buscar/crear cable**: CableDoc
reconoce que ese conector ya pertenece a un cable incompleto y reutiliza
directamente ese mismo cable — sólo agrega la conexión que faltaba en el
conector nuevo. El tramo naranja y el cono desaparecen del diagrama
apenas se suelta, porque el cable ya quedó con sus dos puntas.

También funciona al revés: arrastrando desde el conector "sano" del otro
equipo hacia el conector con el cono da el mismo resultado.

- Si el conector nuevo (al que soltaste) ya tenía otra conexión, se avisa
  y se puede reemplazar, igual que en el punto 2.
- Si **ambos** conectores del arrastre tienen, cada uno, su propia
  conexión incompleta, CableDoc no puede decidir solo cuál de los dos
  cables reutilizar — muestra un aviso en la barra de estado y no hace
  ningún cambio. En ese caso, completá primero uno de los dos a mano
  (con el flujo normal del punto 2, o editando la conexión) y repetí el
  arrastre para el otro.

> Este atajo aplica sólo con **Mostrar todas las conexiones incompletas**
> activo (no con la variante "por equipo seleccionado" del mismo menú).

---

## 4. Resto de las herramientas disponibles

Por ser la misma pantalla que el Diagrama de conexiones, también tenés
disponibles mientras armás la conexión rápida:

- **⊞ Encuadrar todo / ⊕ Expandir vecinos / ↺ Recargar** (menú Ver).
  Expandir vecinos tiene atajo **Ctrl+E**, y si tenés varios nodos
  seleccionados a la vez (rubber-band o Shift/Ctrl+clic) expande los
  vecinos de todos ellos en la misma pasada, no sólo del último que
  clickeaste — cada uno se acomoda alrededor de su propio nodo.
- **🔍 Buscar equipo o cable…** (menú Buscar).
- Selección múltiple (rubber-band, Ctrl/Shift+clic) y **↔ Alinear
  horizontal / ↕ Alinear vertical**.
- **🧲 Auto-organizar nodos (sin solape)** (menú Ver): exclusivo de Alta
  rápida de conexiones, no aparece en el Diagrama de conexiones normal.
  Reacomoda todos los equipos del canvas para que ninguno quede pisando a
  otro — útil después de arrastrar varios equipos a un espacio chico, o
  si agregaste alguno con doble clic y quedó tapando a otro que ya
  estaba centrado en la misma vista. No reordena por tipo ni sigue las
  conexiones (para eso está "⊕ Expandir vecinos"): sólo separa lo
  mínimo necesario, respetando la ubicación general que ya armaste.
  **No guarda las posiciones en la base de datos** — es sólo para
  ordenar la vista durante esta sesión de edición; se guardan recién
  cuando movés un nodo puntualmente a mano (como cualquier drag normal).
- **Doble clic** sobre la cabecera de un equipo abre su ficha completa
  (`_DialogoEquipo`) sin salir del canvas.
- Exportar a SVG/PDF, Impacto, Riesgo, Señal, Escenario, Diagnóstico: todo
  el resto del menú del Diagrama de conexiones funciona igual acá.

## Diferencia con el Diagrama de conexiones normal

Son la misma pantalla y el mismo código. Las diferencias son:

- **Punto de partida** — **Diagrama de conexiones** (menú Ver principal):
  abre con todos los equipos que ya tienen conexiones cargadas (vista
  global) o con el equipo/vecinos de contexto, según desde dónde se lo
  abra. **Alta rápida de conexiones**: abre **vacío**, pensado para
  traer sólo los equipos puntuales que vas a cablear ahora, sin el
  ruido del resto del sistema ya documentado.
- **🧩 Panel de equipos (buscar / arrastrar)** — sólo está disponible en
  Alta rápida de conexiones. En el Diagrama de conexiones normal el
  canvas ya viene poblado con lo existente, así que no se ofrece esta
  vía de agregar equipos sueltos; el ítem de menú directamente no
  aparece ahí (menú Ver).
- **🧲 Auto-organizar nodos (sin solape)** — también exclusivo de Alta
  rápida de conexiones (ver más arriba).

## Si algo no funciona como se espera

- El arrastre de conector a conector no hace nada visible en modo
  **"Mostrar solo nombre nodo"** (menú Ver): en ese modo compacto no se
  dibujan los círculos de los conectores, así que no hay nada de qué
  arrastrar. Desactivá ese modo para cablear.
- Si el popup de cable no aparece al soltar y tampoco se ve ningún
  cambio, confirmá que soltaste justo sobre el círculo del conector (no
  al lado) y sobre un **equipo distinto** al de origen — soltar en el
  mismo equipo no crea nada.
- Si esperabas que se reutilizara un cable incompleto y en cambio se
  abrió el popup normal, confirmá que **Mostrar todas las conexiones
  incompletas** esté tildado y que el conector de origen (o destino)
  todavía figure con el cono naranja en el diagrama.
