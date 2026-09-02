# Imágenes SVG y coordenadas en porcentaje

## ¿Qué cambió?

Dos cosas relacionadas, en la misma entrega:

1. **Ahora se pueden usar imágenes SVG** para equipos, conectores y
   frames — además de JPG/PNG/GIF/BMP/WebP como hasta ahora. La ventaja
   de un SVG es que se ve nítido en **cualquier nivel de zoom** al
   posicionar conectores o slots, porque no es un mapa de píxeles: se
   vuelve a dibujar como vector cada vez que cambiás el zoom, en vez de
   agrandarse un bitmap y pixelarse.
2. **Las coordenadas de posición (X, Y, ancho, alto) ahora se guardan
   como porcentaje del ancho/alto de la imagen, no como píxel libre.**
   Esto es un cambio interno — la app se ve y se usa exactamente igual,
   hacés clic en la imagen para ubicar un conector o dibujás un
   rectángulo para un slot como siempre. La diferencia está adentro:
   antes, si reemplazabas la imagen de un equipo por una de otro tamaño,
   los conectores quedaban mal ubicados (las coordenadas en píxel ya no
   correspondían). Ahora, al guardarse como porcentaje, la posición
   relativa se mantiene aunque cambies la imagen por una de otra
   resolución.

> No hay ningún botón nuevo para esto — es un cambio de "cómo se guarda
> por dentro", no de "cómo se usa". Lo único que vas a notar es que ahora
> podés elegir un archivo `.svg` donde antes solo aceptaba fotos.

## Usar una imagen SVG

Es el mismo lugar de siempre para cargar la imagen de un equipo,
conector o frame:

1. Abrí la ficha del equipo (o frame) y tocá el botón para asignar/
   cambiar la imagen, o andá a **Catálogos → Imágenes → Nueva**.
2. En el selector de archivos, elegí tu `.svg` igual que elegirías un
   `.jpg` o `.png` — el filtro ya acepta cualquier tipo de imagen, no
   hace falta cambiar nada.
3. Guardá. La imagen queda asociada igual que cualquier otra.
4. Al abrir el posicionador de conectores/slots sobre esa imagen, vas a
   poder acercar el zoom todo lo que quieras sin que se vea pixelada.

**¿Cuándo conviene usar SVG en vez de una foto?** Para diagramas
esquemáticos propios (por ejemplo, un plano de rack dibujado a mano en un
editor vectorial, o el diagrama de un frame con sus slots) — ahí un SVG
da mucha más nitidez que una captura de pantalla o un PNG exportado.
Para fotos reales de equipos (sacadas con el celular, por ejemplo), seguí
usando JPG/PNG como siempre — no hay forma de "vectorizar" una foto.

## Migrar los datos existentes (una sola vez)

Si ya tenías conectores y slots posicionados **antes** de esta entrega,
sus coordenadas están guardadas en píxeles todavía. Hay que correr una
migración **una única vez** para convertirlas a porcentaje. Mientras no
la corras, esos conectores/slots viejos van a mostrarse mal ubicados
(las coordenadas en píxel se van a interpretar como si fueran
porcentaje).

> ⚠️ **Hacé un backup de `database/db.db` antes de correr esto.** La
> migración reescribe el valor guardado en la misma columna — no hay una
> columna vieja para volver atrás si algo sale mal.

Desde una consola de Python en el entorno real de la app (con la carpeta
`imagen/` disponible, porque necesita leer el ancho/alto real de cada
imagen):

```python
from modelo import Modelo

def progreso(tabla, id_fila, ok, detalle):
    if not ok:
        print(f"  [ERROR] {tabla} #{id_fila}: {detalle}")

resumen = Modelo.migrar_coordenadas_a_porcentaje(reportar_progreso=progreso)
print("Migradas:", resumen["migradas"])
print("Errores:", len(resumen["errores"]))
```

- **Es idempotente**: si la corrés dos veces por error, la segunda vez
  no hace nada (queda marcada internamente como ya hecha). Si alguna vez
  necesitás forzar que se vuelva a correr, existe
  `Modelo.migrar_coordenadas_a_porcentaje(forzar=True)` — pero normalmente
  no hace falta.
- **Los errores son esperables y no rompen nada.** El más común es
  "sin imagen asociada": un conector/slot que nunca tuvo una imagen
  asignada no tiene de qué ancho/alto calcular el porcentaje, así que
  queda como estaba (en píxel) hasta que le asignes una imagen — después
  podés volver a correr la migración y ese caso se resuelve solo.
- **Si un punto queda con porcentaje fuera de 0-100** (por ejemplo 105%
  o -3%) es porque ya estaba posicionado fuera del borde de la imagen
  actual antes de migrar — probablemente la imagen se reemplazó por una
  de otro tamaño en algún momento y nadie reacomodó el punto. La
  migración no lo "corrige" ni lo mueve al borde: conserva la posición
  real tal cual estaba. Si aparece alguno así en el reporte de errores/
  revisión, conviene abrir ese conector/slot y reubicarlo a mano.

## Preguntas frecuentes

**¿Tengo que hacer algo especial para los equipos/conectores que cargue
de acá en adelante?**
No. Todo alta o edición nueva ya guarda el porcentaje automáticamente —
la migración es sólo para lo que ya estaba cargado antes de esta
entrega.

**¿Puedo seguir usando fotos JPG/PNG normales?**
Sí, sin ningún cambio. El SVG es una opción más, no un reemplazo.

**Si abro la base de datos directo con un visor de SQLite, ¿qué voy a
ver en las columnas de coordenadas?**
Un número entero de 0 a 100 (o algo fuera de ese rango en los casos
señalados arriba), no un píxel. Son las mismas columnas de siempre
(`coordenada_x_en_imagen`, `rectangulo_ancho_pixeles`, etc.) — no se
agregó ninguna columna nueva, sólo cambió el significado del valor
guardado.

**¿Y si mi imagen SVG no se ve o tira error al elegirla?**
Confirmá que el archivo sea un SVG válido (se abre bien en un navegador).
Si el entorno no tiene instalado el soporte de SVG del sistema
(`gir1.2-rsvg-2.0`), la app simplemente no va a poder mostrar ese
archivo — avisá para revisar la instalación.
