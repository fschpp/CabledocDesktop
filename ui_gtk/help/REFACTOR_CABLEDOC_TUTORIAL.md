# Tutorial técnico — Refactor de `cabledoc.py` y guía para agregar funcionalidades futuras

**Audiencia:** desarrolladores que van a tocar CableDoc Desktop de acá en
adelante (incluido Fede en 6 meses cuando no se acuerde de esto).

**Objetivo de este documento:** explicar qué se hizo en el refactor
(`plan_refactor_cabledoc.md`, Entregas 1-10, cerrado) y — más importante
para el futuro — dejar por escrito **cómo agregar features nuevas sin que
`cabledoc.py` vuelva a crecer hasta las 9.405 líneas que tenía antes.**

Si estás por escribir código nuevo y no leíste nada más de este repo, leé
al menos la sección 4 ("Cómo agregar una función nueva") antes de tocar
`cabledoc.py`.

---

## 1. Qué problema había

Antes del refactor, `cabledoc.py` era un único archivo de **9.405 líneas**
que contenía absolutamente todo: la ventana principal, y las clases de
UI (listados + diálogos) de cada dominio del sistema — cables, conectores,
equipos, catálogo de equipos, racks, salas, frames, slots, señal,
imágenes, tipos varios, el panel de árbol de navegación, etc.

Esto ya había pasado una vez antes con `pantallas_avanzadas.py` (11.032
líneas → refactor previo, "Entrega 0" de este plan, ya cerrado). El
síntoma es siempre el mismo: cada feature nueva se agrega "donde ya hay
algo parecido", el archivo no para de crecer, y en algún momento se vuelve
imposible de navegar, revisar en un diff, o entender sin scrollear
kilómetros.

## 2. Qué se hizo: 10 entregas, un dominio por archivo

La estrategia fue **extraer clases completas por dominio a archivos
`*_ui.py` separados, sin cambiar ni una línea de lógica** (move puro, no
refactor de comportamiento). `cabledoc.py` pasó a reexportar cada nombre
movido con `from modulo_ui import Nombre`, así que **ningún código
externo que hacía `from cabledoc import X` se rompió** — siguen
resolviendo al mismo objeto de siempre.

| Entrega | Módulo(s) creado(s) | Dominio |
|---|---|---|
| 1 | `pantallas_comunes.py` | Utilidades genéricas de UI (`VentanaListado`, `_grid`, `_searchable_combo`, etc.) — base de todo lo demás |
| 2 | `cables_conexiones_ui.py` | Cables, fusión, conexiones |
| 3 | `equipos_ui.py` + `equipos_alta_rapida_ui.py` | Equipos reales, ficha completa, alta rápida |
| 4 | `conectores_ui.py` | Conectores de equipos reales |
| 5 | `catalogo_equipos_ui.py` + `catalogo_equipos_alta_rapida_ui.py` | Moldes de equipo (catálogo) |
| 6 | `senal_catalogo_ui.py` | Señales, linaje, propagación, reportes |
| 7 | `racks_salas_ui.py` + `frames_slots_ui.py` | Racks, salas, frames, slots |
| 8 | `catalogos_basicos_ui.py` | Marcas, tipos (equipo/conector/cable/ficha), riesgo, problemas, imágenes + 4 bloques "huérfanos" del plan original |
| 9 | `panel_arbol_ui.py` | Orquestador visual del árbol de navegación (Sala→Rack→Frame→Equipo→Conectores) |
| 10 | (cierre, sin módulo nuevo) | Último bloque suelto (`_DialogoRenombrarConectoresCatalogo`) asignado a `catalogo_equipos_ui.py`; `cabledoc.py` documentado como fachada final |

**Resultado:** `cabledoc.py` bajó a **996 líneas**.

### Estado actual de cada archivo (líneas de código)

```
pantallas_comunes.py                942
cables_conexiones_ui.py             915
equipos_ui.py                     1 207
equipos_alta_rapida_ui.py           591
conectores_ui.py                    466
catalogo_equipos_ui.py              912   (incluye _DialogoRenombrarConectoresCatalogo desde Entrega 10)
catalogo_equipos_alta_rapida_ui.py  549
senal_catalogo_ui.py                915
racks_salas_ui.py                   529
frames_slots_ui.py                  890
catalogos_basicos_ui.py           1 084
panel_arbol_ui.py                   951
cabledoc.py                         996   ← fachada
```

Ningún archivo de dominio pasa de ~1.200 líneas. Esa es la señal de que
cuando un archivo se acerca a esa zona, es candidato a splitearse en dos
(ver sección 5, "cuándo splitear").

## 3. Qué le queda a `cabledoc.py` (y qué NO debería volver a tener)

`cabledoc.py` es ahora una **fachada delgada**. Lo único que le
corresponde tener:

1. **`VentanaPrincipal`** — la ventana principal y el menú de la app. Sus
   métodos son casi todos de una línea: abren una ventana de otro módulo
   (`self._abrir_ventana(RacksListado)`) o delegan a una función `abrir_*`
   importada de `pantallas_avanzadas.py`.
2. **`APP_VERSION`** — se bumpea con cada entrega/feature.
3. **Tres helpers de formulario sin dominio propio**, usados desde varios
   módulos y que no encajaron en ningún dominio específico:
   `_escribir_json_comprimido`, `_leer_json_generico`,
   `_sel_imagen_desde_abm`.
4. **El punto de entrada** (`if __name__ == "__main__":`).
5. **Reexports** — un `from modulo_ui import (...)` por cada módulo de
   dominio, para que el código viejo que hace
   `from cabledoc import NombreDeClase` no se rompa.

**Lo que NO debería volver a aparecer en `cabledoc.py`:**

- Una clase `_Dialogo...` o `...Listado` nueva completa. Eso va en su
  módulo de dominio (ver sección 4).
- Lógica de negocio de cualquier tipo (queries, cálculos, validaciones).
  Eso va en `modelo.py` o en el módulo de dominio correspondiente, nunca
  directo en `cabledoc.py`.
- Un dominio nuevo completo (por ejemplo, si mañana aparece "gestión de
  fibra óptica" como feature grande) — eso nace directo en su propio
  `*_ui.py`, nunca arrancás escribiéndolo en `cabledoc.py` "para
  ordenarlo después".

## 4. Cómo agregar una función nueva sin recargar `cabledoc.py`

Esta es la parte que importa para el futuro. Seguí este flujo:

### Paso 1 — Identificá el dominio

¿La función nueva es sobre cables? ¿Sobre equipos? ¿Sobre racks? Buscá en
la tabla de la sección 2 cuál `*_ui.py` ya es dueño de ese dominio.

- **Si el dominio ya existe** → el código nuevo va en ese archivo.
- **Si es un dominio genuinamente nuevo** (no hay módulo dueño) → creás un
  archivo nuevo `nombre_del_dominio_ui.py` desde el principio. No lo
  escribas "provisoriamente" en `cabledoc.py`.

### Paso 2 — Si es una clase nueva (listado o diálogo)

Se escribe directo en el archivo del dominio, no en `cabledoc.py`. Ejemplo:
si agregás un "Historial de mantenimiento" para equipos, la clase
`_DialogoHistorialMantenimiento` va en `equipos_ui.py`, no acá.

### Paso 3 — Si necesitás una clase de OTRO dominio (referencia cruzada)

Es la situación más común y la que en el pasado hacía que todo terminara
mezclado en un solo archivo. La solución ya usada en las 10 entregas es
**import diferido dentro del método que la usa**, apuntando siempre a
`cabledoc` como punto de reexport (nunca al módulo de dominio directo,
para evitar ciclos):

```python
# Ejemplo real (catalogo_equipos_ui.py necesita MarcasListado,
# que vive en catalogos_basicos_ui.py):

def _sel_marca(self, btn):
    from cabledoc import MarcasListado   # import diferido, NO al tope del archivo
    sel = MarcasListado(parent=self, modo_seleccion=True)
    ...
```

**Por qué así y no `from catalogos_basicos_ui import MarcasListado` directo:**
porque `cabledoc.py` es el único punto que garantiza no generar ciclos de
import entre módulos de dominio. Rutear siempre a través de `cabledoc`
mantiene ese contrato sin que cada módulo tenga que saber la ubicación
física de la clase de otro.

**Excepción:** si dos módulos son *hermanos* de la misma entrega/dominio
(ej. `catalogo_equipos_ui.py` y `catalogo_equipos_alta_rapida_ui.py`), está
bien que se importen directo entre sí dentro de un método, siguiendo el
mismo patrón de import diferido — no hace falta pasar por `cabledoc` en
ese caso puntual.

### Paso 4 — Si la función abre una ventana desde el menú principal

El método en `VentanaPrincipal` (`cabledoc.py`) debe quedar en una línea,
delegando:

```python
def _abrir_historial_mantenimiento(self, *a):
    self._abrir_ventana(HistorialMantenimientoListado)
```

`HistorialMantenimientoListado` se importa arriba del todo en
`cabledoc.py` junto con el resto del bloque de reexport de su módulo de
dominio (agregala a la tupla de imports existente de ese módulo, o creá
un bloque nuevo con su comentario si es un dominio nuevo).

### Paso 5 — Nunca hardcodees tipos de equipo/rol en la lógica nueva

Regla ya establecida del proyecto, vale para todo código nuevo: nunca
compares contra nombres de equipo o tipo por string (`"SWITCHER"`,
`"KUMO"`, etc.). Siempre:

```python
if tipo_equipo.rol_senal == 'ENRUTADOR':   # correcto
```

usando `Modelo.devolver_rol_senal_tipo_equipo()` para resolverlo. Esto no
es específico del refactor de `cabledoc.py`, pero es la regla más
violada cuando alguien copia y pega código viejo sin revisar.

### Paso 6 — Actualizá `changelog.txt`, `PROGRESS.md`/`PROGRESS_REFACTOR*.md` y `APP_VERSION`

Mismo formato que siempre:

```
YYYY-MM-DDTHH:MM archivo.py (Clase/método): descripción de qué cambió y por qué.
```

`APP_VERSION` en `cabledoc.py` se bumpea con formato `1.YYYYMMDDHHMMSS`
en cada entrega, aunque el cambio no haya tocado `cabledoc.py`
directamente (es la versión de toda la app).

## 5. Cuándo splitear un módulo de dominio en dos

Si un `*_ui.py` empieza a acercarse a las ~1.200 líneas (el techo que
tocaron `equipos_ui.py` y `catalogos_basicos_ui.py` en este refactor), es
momento de splitearlo, con el mismo criterio usado en las Entregas 3, 5 y
7:

1. Identificá un sub-dominio lógico dentro del archivo que pueda vivir
   aparte (ej. "alta rápida" separado de la "ficha completa", como se hizo
   con `equipos_ui.py` / `equipos_alta_rapida_ui.py`).
2. El archivo nuevo lleva el mismo docstring de cabecera explicando de
   dónde viene y por qué se separó.
3. Las referencias cruzadas entre los dos archivos hermanos se resuelven
   con import diferido apuntando directo entre ellos (no hace falta pasar
   por `cabledoc` para hermanos del mismo split), tal como se explicó en
   el Paso 3 de la sección anterior.
4. `cabledoc.py` reexporta ambos, sin cambios en el resto del código.

## 6. Checklist de validación para cualquier cambio futuro en estos módulos

Este es el mismo checklist que se corrió en las 10 entregas — aplicalo
también a features nuevas, no sólo a refactors:

1. **Sintaxis:** `python3 -m ast` (o simplemente `ast.parse`) +
   `py_compile` sobre cada archivo tocado.
2. **Nombres libres / imports rotos:** `pyflakes archivo.py`. En
   `cabledoc.py` vas a ver un montón de falsos positivos
   ("imported but unused") porque **todo lo que reexporta aparece como no
   usado dentro del propio archivo** — es esperado, no es un bug. Lo que
   importa es que no aparezcan **F821** (nombre no definido) nuevos.
3. **Import real bajo Xvfb:** que el módulo se pueda importar de verdad
   con GTK cargado, no sólo que el AST sea válido:
   ```bash
   xvfb-run -a python3 -c "import cabledoc"
   ```
4. **Identidad de objeto** si moviste algo que ya existía: confirmar que
   `cabledoc.NombreMovido is modulo_nuevo.NombreMovido` — si son el mismo
   objeto, ningún consumidor externo se rompió.
5. **Grep de consumidores externos:**
   ```bash
   grep -rn "from cabledoc import" --include="*.py" .
   ```
   y confirmar que todos siguen resolviendo.
6. **Smoke test funcional** contra una base de fixture (el repo no trae
   `database/db.db` versionado con datos — armalo con `schema_db.sql` +
   unas filas insertadas por SQL directo si no tenés la base real a mano).

## 7. Resumen en una frase

**Cada dominio vive en su propio `*_ui.py`. `cabledoc.py` sólo orquesta
(`VentanaPrincipal`), reexporta, y arranca la app — nunca vuelve a
acumular clases de dominio.** Si en algún momento dudás dónde poner algo
nuevo, la pregunta correcta no es "¿dónde hay espacio en `cabledoc.py`?"
sino "¿qué módulo de dominio es dueño de esto, o necesito crear uno
nuevo?".

---

*Ver también: `plan_refactor_cabledoc.md` (plan original de las 10
entregas) y `PROGRESS_REFACTOR_CABLEDOC.md` (bitácora detallada de cada
entrega, con hallazgos y decisiones de diseño documentadas).*
