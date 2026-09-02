# Conexiones incompletas en el Diagrama de conexiones

Esta función ayuda a detectar cables que están documentados en **un solo
extremo**. Es útil durante un relevamiento: permite ver rápidamente qué
cables ya llegan a una entrada o salen de una salida de un equipo, pero
todavía no tienen cargado el equipo o conector del otro lado.

> La función es sólo visual: no crea conexiones, no modifica cables y no
> inventa un equipo para el extremo que todavía se desconoce.

---

## Qué muestra

En el Diagrama de conexiones, una conexión incompleta aparece como:

- Un tramo de cable **naranja punteado** que sale de una entrada (IN) o de
  una salida (OUT) del equipo. En un puerto IN el tramo se dibuja hacia la
  izquierda (aguas arriba); en un puerto OUT, hacia la derecha (aguas
  abajo).
- La etiqueta con el **código del cable** (`cable_codigo`).
- Un **cono naranja** en el extremo pendiente de documentar.

El cono significa: *este cable está conectado a este puerto, pero su otra
punta todavía no está registrada en CableDoc*.

## Cómo usarla

1. Abrí **Diagramas → Diagrama de conexiones**.
2. Hacé clic sobre el equipo que querés revisar.
3. Abrí el menú **Ver**.
4. Activá **Mostrar conexiones incompletas**.
5. Revisá los tramos naranjas que aparecen del lado de las entradas (IN,
   hacia la izquierda) y de las salidas (OUT, hacia la derecha).

Podés seleccionar otro equipo sin cerrar el modo: el diagrama actualiza los
tramos para el nuevo equipo seleccionado.

Para ocultarlos, desmarcá **Ver → Mostrar conexiones incompletas**.

---

## Ver todas las conexiones incompletas del diagrama a la vez

Si estás haciendo un relevamiento general y no querés ir equipo por
equipo, activá **Ver → Mostrar todas las conexiones incompletas**. Esta
opción hace exactamente lo mismo que la anterior, pero para **todos los
equipos visibles en el diagrama** al mismo tiempo, sin necesidad de
seleccionar ninguno.

- No depende de tener un equipo seleccionado.
- Cada tramo naranja aparece junto al equipo al que realmente pertenece
  ese cable pendiente.
- Es **mutuamente excluyente** con **Mostrar conexiones incompletas** (por
  equipo seleccionado): activar una la apaga automáticamente a la otra,
  para no dibujar el mismo tramo dos veces.

Usala para tener una foto completa del estado de documentación del
diagrama; usá la variante por equipo cuando ya sabés qué equipo te
interesa revisar en detalle.

---

## Qué condiciones debe cumplir un cable

CableDoc lo muestra solamente cuando se cumplen las dos condiciones:

1. El cable está conectado a un conector de tipo **entrada (IN)** o
   **salida (OUT)** del equipo seleccionado.
2. Ese cable tiene exactamente **una sola conexión registrada** en la base.

En otras palabras: el cable debe existir y tener una punta cargada. Un
conector completamente vacío, sin ningún cable asociado, no puede mostrar
un código ni un extremo pendiente; por eso no aparece en esta vista.

## Ejemplo práctico

Durante el relevamiento se carga que el cable `DL0317` llega a `05IN` de una
matriz, pero todavía no se identificó el equipo de origen. Al seleccionar la
matriz y activar la opción, desde `05IN` se verá:

```text
cono naranja ┈ ┈ DL0317 ┈ ┈ ● 05IN [Matriz]
```

Cuando se releve la otra punta y se cree la segunda conexión del cable, el
cono desaparece automáticamente de esta vista: el cable pasará a dibujarse
como una conexión normal entre ambos equipos.

Lo mismo aplica del lado de una salida: si se carga que el cable `DL0450`
sale de `12OUT` de un router pero todavía no se identificó el destino, al
seleccionar el router y activar la opción se verá:

```text
● 12OUT [Router] ┈ ┈ DL0450 ┈ ┈ cono naranja
```

---

## Cómo completar el relevamiento

1. Anotá o buscá físicamente el código mostrado junto al tramo naranja.
2. Identificá el equipo y el conector del otro extremo.
3. Abrí **Conexiones** desde el menú principal.
4. Creá o editá la conexión correspondiente para asociar ese mismo cable al
   conector encontrado.
5. Volvé al Diagrama de conexiones y usá **Ver → Recargar** si el diagrama
   ya estaba abierto.

Al tener dos puntas registradas, el cable deja de ser incompleto y queda
documentado como una línea convencional entre los dos equipos.

## Si no aparece nada

- Confirmá que primero seleccionaste un equipo.
- Confirmá que el cable está conectado a un puerto **IN** u **OUT** real
  del equipo seleccionado.
- Verificá que el cable tenga una sola fila en **Conexiones**. Si ya tiene
  dos, no está incompleto; si no tiene ninguna, todavía no hay nada que el
  diagrama pueda asociar a ese puerto.
- Usá **Ver → Recargar** después de editar conexiones en otra ventana.

## Diferencia con Análisis de Impacto

**Mostrar conexiones incompletas** revisa la calidad de la documentación
física: encuentra extremos de cable pendientes de relevar.

**Impacto** simula qué señales/equipos se afectarían si se corta un cable ya
conectado. Son herramientas complementarias: una ayuda a completar el plano
y la otra a evaluar riesgos operativos.
