# Tutorial — "🔌 Marcar extremo desconectado"

Guía rápida de uso de la nueva acción para documentar, en el momento, un
extremo de cable que recorriste y confirmaste que está suelto.

## ¿Qué resuelve?

Antes, documentar un extremo muerto significaba: escribir a mano en un
bloc de notas aparte el nombre `EXTREMO A/B DESCONECTADO <código>`, abrir
"Nuevo equipo", copiar ese nombre, elegir tipo FANTASMA, completar
Marca/Modelo/Inventario/Serie (vacíos, pero había que pasar por ahí),
elegir a mano si el conector era IN u OUT, y recién ahí ir a cargar la
foto y la ubicación. Ahora es un solo botón desde la ficha del cable.

## Paso a paso

1. **Abrí la ficha del cable** que acabás de recorrer (desde el árbol de
   Cables, buscándolo por código, o desde donde ya lo tengas a mano).

2. Vas a ver el botón **"🔌 Marcar extremo desconectado"**, al lado de
   "🔗 Ver cadena completa". Hacé clic ahí.

   - Si el botón está **gris/deshabilitado**, es porque ese cable ya
     tiene sus dos extremos documentados — no hay nada que hacer.

3. **Según cuántas puntas tenga ya cargadas el cable:**

   - **Ninguna punta cargada todavía (primera vez que documentás este
     cable):** se abre un mini-diálogo preguntando qué extremo estás
     marcando:
     - *"Extremo A (queda OUT)"*
     - *"Extremo B (queda IN)"*

     Elegí el que corresponda. Es sólo para el nombre — no hay una
     diferencia física real entre A y B, es la convención que ya venías
     usando.

   - **Ya hay una punta cargada** (sea un equipo real o un fantasma del
     otro lado): **no te pregunta nada.** El sistema infiere solo que
     estás documentando el lado que falta, y le pone el tipo de conector
     opuesto automáticamente.

4. El sistema crea, en un solo paso:
   - El equipo `EXTREMO A/B DESCONECTADO <código del cable>`, tipo
     FANTASMA, con Marca/Modelo/Inventario/Serie vacíos (no se piden).
   - Su conector único (`OUT` o `IN`, según el lado).
   - La conexión entre el cable y ese conector.

   Aparece un aviso confirmando qué se creó.

5. **A continuación se abren, uno detrás del otro, dos diálogos que ya
   conocés** — podés cancelar cualquiera de los dos si no los necesitás
   en ese momento, lo ya creado en el paso 4 queda guardado igual:
   - **Ficha del equipo** — para cargar la imagen del plano y marcar la
     coordenada aproximada de dónde cuelga el cable.
   - **Ficha del conector** — para cargar la foto de la ficha suelta y
     marcar el punto exacto en la foto.

6. Listo. Si documentaste recién la segunda punta de un cable que ya
   tenía la otra en fantasma, **no hace falta ningún paso extra**: la
   conexión entre ambos fantasmas ya quedó armada, y vas a verlo reflejado
   como `VERIFICADO` en el árbol de Cables.

## Cosas para tener en cuenta

- **La foto y la ubicación siguen siendo opcionales al momento de crear.**
  Si cancelás los diálogos del paso 5, podés volver más tarde a la ficha
  del equipo/conector y cargarlas — nada se pierde.
- **El botón no borra ni modifica nada existente.** Si te equivocaste de
  lado (A en vez de B), el equipo ya quedó creado con ese nombre; por
  ahora hay que corregirlo a mano desde su ficha (renombrar) como
  cualquier otro equipo — no hay un "deshacer" específico para esta
  acción todavía.
- **Fantasmas huérfanos:** si más adelante volvés a un extremo que
  marcaste como desconectado y resulta que ahí hay un equipo real, por
  ahora el flujo para reemplazarlo sigue siendo manual (editar la
  conexión al equipo real y borrar el fantasma sobrante) **salvo** que
  la reasignación pase por el flujo de reemplazo de conexiones del
  Diagrama (arrastrar un cable nuevo sobre un conector ya ocupado): en
  ese caso CableDoc ahora detecta solo cuándo el fantasma del otro
  extremo se queda sin ninguna conexión y ofrece borrarlo en el momento
  — ver **TUTORIAL_aviso_fantasma_huerfano.md**.
- **Islas** (cables con las dos puntas en fantasma) siguen
  ubicándose a mano en el diagrama por ahora — sin cambios en este
  tutorial.

## Preguntas frecuentes

**¿Puedo usar esto para un cable que en realidad se conecta pero todavía
no relevé el otro lado?**
No es el caso de uso pensado — esto es específicamente para cuando
*confirmaste* que el extremo está suelto. Si simplemente no llegaste
todavía a recorrer el otro lado, dejá el cable con una sola punta
cargada tal como está: el ícono de "cono" en el diagrama ya te avisa que
falta terminar de seguirlo.

**¿Y si me equivoco y el cable en realidad tiene una extensión (empalme a
otro cable), no un extremo muerto?**
Son cosas distintas: la Extensión de cable (botón "🔗 Extender con otro
cable") es para cuando un cable sigue físicamente en otro cable sin
equipo de por medio. FANTASMA es para cuando confirmaste que ahí no sigue
nada. Si te das cuenta después de haber marcado un fantasma que en
realidad correspondía una extensión, hay que deshacerlo a mano por
ahora (borrar el fantasma, usar "Extender con otro cable" en su lugar).
