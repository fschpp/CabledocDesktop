# Aviso de fantasma huérfano al reconectar

Guía rápida de la nueva alerta que aparece en el **Diagrama de
conexiones** cuando, al reconectar un cable, un equipo FANTASMA se queda
sin ningún cable real que documentar.

## ¿Qué resuelve?

Cuando marcás un extremo desconectado (ver
**tutorial_marcar_extremo_desconectado.md**), CableDoc crea un equipo
FANTASMA que existe únicamente para documentar "acá el cable X termina
suelto". Si más adelante ese mismo cable **se reasigna a un destino
real** — por ejemplo, encontraste el otro extremo y lo conectaste a un
equipo de verdad — el fantasma que lo documentaba deja de tener sentido:
ya no hay ningún cable real que justifique su existencia.

Antes, ese fantasma quedaba dando vueltas en la base para siempre, y
había que acordarse de ir a borrarlo a mano. Ahora CableDoc lo detecta
solo y te lo ofrece limpiar en el momento.

## Cuándo aparece

El aviso se dispara **al reconectar un cable pisando una conexión
existente** en el Diagrama de conexiones (el flujo de arrastre descripto
en **TUTORIAL_alta_rapida_conexiones.md**, sección *"Si el conector de
destino ya tenía una conexión"*):

1. Arrastrás un cable nuevo hasta un conector que ya tenía otro cable
   conectado.
2. Confirmás el aviso de "esa conexión existente se eliminará…".
3. CableDoc revisa el **otro extremo** del cable que acabás de
   reemplazar (no el conector donde soltaste, ese ya tiene la conexión
   nueva). Si ese otro extremo es un equipo FANTASMA y, además de esta
   conexión, **no tiene ninguna otra**, aparece:

```text
El equipo fantasma «EXTREMO A DESCONECTADO C-1042» quedó sin conexiones
El cable que documentaba su extremo desconectado se acaba de reasignar
a otro destino. ¿Eliminar el equipo fantasma?
        [No]  [Sí]
```

4. **Sí** → borra el equipo fantasma (y su conector, en cascada, como
   cualquier eliminación de equipo).
5. **No** → no cambia nada; el fantasma queda igual que estaba, para
   revisarlo a mano más adelante si preferís.

## Ejemplo

1. Tenés el cable `C-1042` con un extremo conectado a `DDA 04 ESTUDIO
   OUT 3` y el otro documentado como fantasma
   (`EXTREMO B DESCONECTADO C-1042`), porque en su momento no sabías
   dónde terminaba.
2. Recorriendo la sala encontrás que en realidad `C-1042` llega al
   `MONITOR DIRECTOR CAMARA` — y ese conector ya tiene otro cable viejo
   conectado (`C-0987`), que en realidad correspondía a otra cosa.
3. Arrastrás `C-1042` desde `DDA 04 ESTUDIO OUT 3` hasta el conector del
   `MONITOR DIRECTOR CAMARA`, confirmás que reemplace a `C-0987`.
4. CableDoc revisa el otro extremo de `C-0987` (el que quedó
   desconectado de ese conector) — si es un fantasma sin más
   conexiones, te pregunta si lo borrás. El fantasma de `C-1042`
   (`EXTREMO B DESCONECTADO C-1042`), en cambio, sigue existiendo:
   nadie tocó ese lado en esta operación — hay que borrarlo a mano
   desde su ficha, como hasta ahora.

## Cosas para tener en cuenta

- **El aviso mira el cable que se reemplaza, no el conector donde
  soltaste.** El conector de destino siempre recibe la conexión nueva en
  el mismo paso, así que nunca puede quedar huérfano — el que
  potencialmente pierde su razón de ser es el otro extremo del cable
  viejo que se está desplazando.
- **"Sin conexiones" quiere decir sin ninguna OTRA conexión.** Un
  fantasma con varios cables documentados (caso raro, pero posible) no
  se ofrece borrar aunque uno de sus cables se reasigne — sigue
  documentando los demás.
- **No hay todavía un gesto de "arrastrar un extremo ya conectado a otro
  conector"** (mover una conexión existente de lugar sin pasar por el
  flujo de reemplazo). Por eso este aviso vive específicamente en el
  punto donde hoy se borra una conexión al reconectar — no es un
  chequeo genérico de "cualquier fantasma que quede sin conexiones en
  cualquier operación".
- Borrar el fantasma acá es exactamente lo mismo que borrarlo a mano
  desde su ficha (mismo `Modelo.eliminar_equipo`, mismo cascade sobre su
  conector) — no hay nada especial ni irreversible distinto de un
  borrado de equipo normal.

## Ver también

- **tutorial_marcar_extremo_desconectado.md** — cómo se crean los
  fantasmas que este aviso puede ofrecer limpiar.
- **TUTORIAL_alta_rapida_conexiones.md** — el flujo de arrastre y
  reemplazo de conexiones donde vive este aviso.
