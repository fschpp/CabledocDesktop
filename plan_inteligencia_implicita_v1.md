# Plan: Inteligencia implícita + linter de topología (v1)

## Contexto

De la charla surgieron dos líneas de trabajo, ambas apoyadas en motores que
**ya existen** (`risk_engine.py`, `graph_impact.py`, `escenario_engine.py`,
el panel "Trabajo pendiente" del dashboard) — no requieren rediseñar nada,
solo cruzar datos que hoy están dispersos:

1. **Priorización automática de criticidad**: hoy `equipo_critico` está
   pensado como marca manual. `escenario_engine.py` ya permite simular la
   falla de cualquier equipo y medir cuánto afecta — corriéndolo para
   *todos* los equipos se obtiene un ranking objetivo, cruzable con el IRF
   (probabilidad × impacto).
2. **Linter de topología**: reglas de diseño que hoy viven en la cabeza de
   Fede (referencia en cascada, salidas loop mal usadas, equipos fuera de
   patchera) se pueden convertir en chequeos automáticos sobre el grafo,
   mostrados como tarjetas nuevas en el panel de pendientes (mismo patrón
   que "🔍 Sin auditar").

## Convenciones de esta entrega

- Cada tarea está pensada para completarse en **un solo turno de
  herramienta** (versión free): un archivo, una función o query, sin
  refactors grandes.
- Checklist previo de siempre: estimar costo → confirmar con Fede →
  confirmar archivos actualizados → avisar si hace falta tocar esquema.
- Validación por tarea: `ast.parse` → `py_compile` → `pyflakes` (sin
  warnings nuevos) → smoke test funcional con fixture SQLite real.
- Cada tarea cierra con su línea en `changelog.txt`.
- Ediciones quirúrgicas (`str_replace`/`edit_file`), no reescrituras
  completas salvo que se pida.

---

## Fase 0 — Confirmar esquema (previa a Fase 2 y Fase 4)

Antes de escribir queries de detección hace falta confirmar tres cosas
puntuales contra `schema_db.sql` / `modelo.py` / datos reales. Sin esto,
las Fases 2 y 4 son especulación.

- [x] **0.1** — Grep de todos los valores que toma `rol_senal` hoy en la
      BD (`SELECT DISTINCT rol_senal FROM conexion`), para confirmar si
      existe un valor de referencia/sync equivalente al `'PATCHERA'` ya
      conocido.
      **Resultado (2026-09-27, sobre `main` en `00ce421`):**
      - `rol_senal` NO es columna de `conexion`: vive en `tipo_equipo`
        (`SELECT DISTINCT rol_senal FROM conexion` falla con "no such
        column"). El `'PATCHERA'` del plan (3.1, 4.x) es un rol de
        *tipo de equipo*, no de conexión. Fase 3 ya lo resuelve así
        (`Modelo.devolver_equipos_fuera_de_patchera()`, join por
        `tipo_equipo`), pero el texto de 3.1 de este plan quedó impreciso.
      - Valores válidos (`Modelo.ROLES_SENAL`, validados sólo en Python,
        sin CHECK en la tabla): `FUENTE`, `DISTRIBUIDOR` (default),
        `ENRUTADOR`, `PROCESADOR`, `CONSUMIDOR`, `PATCHERA`, `FANTASMA`,
        `CONVERSOR_BALANCE`, `SUMADOR_CANAL`, `DISTRIBUIDOR_FRAME`.
      - NO existe un rol de referencia/sync equivalente a `PATCHERA`. La
        referencia se marca a nivel conector, con columnas que agrega
        `Modelo.asegurar_columnas_control_idioma()` (no están en
        `schema_db.sql`): `tipo_conector.es_referencia_generada` (salida
        de referencia, ex `REFOUT`), `conector.es_entrada_referencia`
        (entrada que hereda referencia del frame) y
        `conector.es_salida_referencia_frame` (salida interna de un
        `DISTRIBUIDOR_FRAME`). Lo más cercano a un rol de sync por equipo
        es `DISTRIBUIDOR_FRAME`.
      - Consecuencia para la Fase 2: 2.1 no puede filtrar por
        `rol_senal` de conexión; tiene que partir de los conectores
        con `es_referencia_generada = 1` (vía su `tipo_conector`) y
        seguir el cable hasta la entrada de referencia destino.
      **Verificado contra la base real (`db.db`, 2026-09-27,
      `integrity_check` ok, abierta en solo lectura):**
      - `SELECT DISTINCT rol_senal FROM conexion` falla: "no such
        column". Confirmado.
      - Roles en uso en `tipo_equipo` (tipos): `DISTRIBUIDOR` 28,
        `PROCESADOR` 9, `FUENTE` 7, `ENRUTADOR` 4, `CONSUMIDOR` 4,
        `PATCHERA` 1, `FANTASMA` 1, `DISTRIBUIDOR_FRAME` 1. Ninguno es
        NULL. No hay `CONVERSOR_BALANCE` ni `SUMADOR_CANAL` en uso.
      - Confirmado que no existe un rol de referencia/sync: lo más
        cercano es `DISTRIBUIDOR_FRAME` (1 tipo, 3 equipos).
      - Las columnas de referencia existen en la base real:
        `conector.es_entrada_referencia` (18 conectores con valor 1),
        `conector.es_salida_referencia_frame` (3) y
        `tipo_conector.es_referencia_generada` (tipo `REFOUT`, 24
        conectores). Además hay una columna `tipo_conector.
        es_entrada_referencia` (todos en 0) que quedó de una versión
        anterior y ya no se usa (ver `asegurar_columnas_control_idioma`).
- [x] **0.2** — Confirmar si `conector`/`tipo_ficha` distingue de alguna
      forma una salida loop-through de una salida normal. Si no existe,
      esta tarea deja documentado que Fase 4 necesita una columna nueva
      antes de poder implementarse.
      **Resultado (2026-09-27) — CORREGIDO tras revisar la base real.**
      La primera versión de esta tarea concluyó "no existe ninguna
      marca de loop-through" mirando sólo el esquema: era incorrecto,
      porque la marca vive en los **datos** (catálogo `tipo_conector`),
      no en una columna. Sobre `db.db`:
      - Existe el tipo de conector `LOOP` (`id_tipo_conector` 12), con
        14 conectores en 4 tipos de equipo: `CONV SDI A HDMI` (8),
        `OTRO` (4), `ANALOGICO DDV` (1), `MONITOR` (1). **Ninguno tiene
        cable** (0 filas en `conexion`).
      - Su `direccion` es `'IN'`. Salió de la semilla por nombre de
        `asegurar_columnas_control_idioma` ("OUT" en el nombre → OUT,
        si no IN), pero un loop-through es una salida. Hay que
        confirmarlo con Fede: si es un error de dato, los motores que
        leen `tipo_conector.direccion` (`graph_impact.py`) los tratan
        como entradas.
      - Hay una segunda convención, en el nombre: 26 conectores de tipo
        `OUT` con "LOOP" en el nombre (16 en `MULTIVIEW`, 6 en
        `DISTRIBUIDOR DE REFERENCIA DE FRAME`, 2 en `WFM`, 1 en
        `MONITOR`, 1 en `CONV HDMI A SDI`; sólo 5 tienen cable) y 4 de
        tipo `REFOUT` (`REF LOOP`, en `SWITCHER`, `WFM` y `OTRO`; ninguno
        cableado).
      - No existe columna de loop: ninguna tabla/columna con "loop",
        "pasa", "thru" ni "bucle" en el nombre; `tipo_ficha`,
        `matriz_ruteo` y `funcion_patchera` no sirven de marca (igual
        que en la primera versión).
      **Conclusión corregida:** el loop hoy se marca de dos maneras
      inconsistentes (tipo `LOOP` con dirección IN, o tipo `OUT` con
      "LOOP" en el nombre). Antes de decidir 4.1 (`conector.es_loop`)
      hay que decidir con Fede si se unifica en una sola convención
      (p. ej. usar el tipo `LOOP` con dirección OUT) o si se agrega la
      columna. Además, con 5 conectores loop cableados en toda la base,
      4.2 hoy encontraría casi nada: conviene ver primero si compensa.
      Sigue en pie el aviso del checklist: confirmar con Fede antes de
      tocar esquema o datos del catálogo.
      **Decisión (Fede, 2026-09-27):** el tipo `LOOP` con dirección `IN`
      es un error de dato: debe ser `OUT`. Corregido en 4.1b (migración
      única). Los moldes (`conector_catalogo`) se resuelven en otro plan.
- [x] **0.3** — Confirmar qué valores de `tipo_equipo` actúan hoy como
      distribuidores de sincronismo legítimos (candidato: DDV), para
      poder armar la lista blanca que usa Fase 2.
      **Resultado (2026-09-27) — CORREGIDO tras revisar la base real.**
      La primera versión decía que desde el código no se podía armar
      la lista; con `db.db` sí se puede, y el candidato del plan (DDV)
      no es un distribuidor de sincronismo en esta base.
      - `DDV` (`id_tipo_equipo` 3, rol `DISTRIBUIDOR`, 30 equipos) sólo
        tiene conectores `IN` (30) y `OUT` (240) de video: **ningún
        conector de referencia marcado**. Distribuye video, no sync.
      - Tipos que tienen conectores `REFOUT` (salida de referencia):
        `SYNC PULSE GENERATOR` (21, `FUENTE`, 10 conectores),
        `DISTRIBUIDOR TRILEVEL` (25, `DISTRIBUIDOR`, 8), `CCU` (29,
        `FUENTE`, 2), `SWITCHER` (7, `ENRUTADOR`, 2), `WFM` (6,
        `CONSUMIDOR`, 1) y `OTRO` (35, `DISTRIBUIDOR`, 1). Además
        `DISTRIBUIDOR DE REFERENCIA DE FRAME` (56, `DISTRIBUIDOR_FRAME`)
        tiene la salida interna del frame.
      - **Lista blanca propuesta (a confirmar con Fede):** `SYNC PULSE
        GENERATOR` (21), `DISTRIBUIDOR TRILEVEL` (25; por nombre y por
        sus 8 `REFOUT` parece el distribuidor de sync trilevel) y
        `DISTRIBUIDOR DE REFERENCIA DE FRAME` (56). Los otros con
        `REFOUT` (`CCU`, `SWITCHER`, `WFM`, `OTRO`) quedan como los
        candidatos a "cascada" (re-emiten referencia: `REF LOOP`,
        `REFERENCE OUT`).
      - Por qué no alcanza un rol: `DISTRIBUIDOR` agrupa 28 tipos (PC,
        KVM, NETWORKING, conversores...), y `FUENTE` incluye a `CCU`.
        La lista tiene que ser por `id_tipo_equipo` (config), o una
        marca en `tipo_equipo` si se prefiere tocar esquema.
      - **Dato clave para la Fase 2:** la referencia casi no está
        cableada. De 24 conectores `REFOUT` sólo 1 tiene cable
        (`REFERENCE OUT` de `CCU 1`), y de 33 entradas de referencia
        (`es_entrada_referencia=1` o tipo `REFIN`) 22 tienen cable. Con
        los datos de hoy, "referencia en cascada" encontraría a lo sumo
        ese caso: primero hay que cargar la referencia real.
      - Ojo: `SYNC PULSE GENERATOR` y `DISTRIBUIDOR TRILEVEL` tienen 0
        `REFOUT` cableados.
      **Cierre de la Fase 0:** 0.1, 0.2 y 0.3 hechas contra la base real.
      Decisiones pendientes de Fede: (1) confirmar la lista blanca de
      0.3; (2) convención de loop y dirección del tipo `LOOP` (0.2).
      Las Fases 1 y 3 no dependen de la Fase 0.

---

## Fase 1 — Ranking automático de criticidad (IRF × blast radius)

Es la de mayor valor con menor esfuerzo: reutiliza `escenario_engine.py`
tal cual está, sin tocarlo.

- [ ] **1.1** — Función `calcular_criticidad_todos(db_path)` (nuevo
      módulo o agregado a `risk_engine.py`): recorre todos los `equipo`,
      simula la falla individual de cada uno vía
      `GraphImpactAnalyzer.simular_escenario()` (sin persistir nada, solo
      en memoria) y devuelve una lista `(id_equipo, blast_radius)`
      ordenada.
- [ ] **1.2** — Cruce con IRF: clasificar cada equipo en un cuadrante
      (probabilidad × impacto) usando el score que ya calcula
      `risk_engine.py`. Devolver algo simple: alto/alto, alto/bajo,
      bajo/alto, bajo/bajo.
- [ ] **1.3** — UI: tarjeta nueva en el panel "Trabajo pendiente —
      Equipos" (`cabledoc.py`, mismo patrón que
      `_actualizar_panel_pendientes_eq`) mostrando el top N de equipos en
      cuadrante alto/alto.

---

## Fase 2 — Detección: referencia en cascada

Depende de **0.1** y **0.3**. Es el ítem que ya tenía un hueco anotado
("regla_logica REF1→REFOUT automation" en `plan_referencia_virtual_frame.md`).

- [ ] **2.1** — Query/función que devuelva toda conexión de rol
      referencia/sync cuyo `tipo_equipo` de origen no esté en la lista
      blanca de distribuidores (0.3).
- [ ] **2.2** — Para cada hallazgo, cruzar con el blast radius de Fase
      1.1 (reusar la función, no reimplementar) para poder ordenar por
      gravedad real, no solo por existencia de la cascada.
- [ ] **2.3** — UI: tarjeta "⚠️ Referencia en cascada" en el panel de
      pendientes, mismo patrón que las anteriores.

---

## Fase 3 — Detección: equipos fuera de patchera

Sin dependencias — se puede hacer primero si se quiere algo rápido.

- [ ] **3.1** — Query `GROUP BY equipo` sobre `conexion`: equipos que
      nunca tienen una fila con `rol_senal='PATCHERA'`.
- [ ] **3.2** — Cruzar esa lista con el ranking de criticidad de Fase 1
      (un equipo crítico y fuera de patchera es el caso que realmente
      importa priorizar).
- [ ] **3.3** — UI: tarjeta "⚠️ Fuera de patchera" en el panel de
      pendientes.

---

## Fase 4 — Detección: loop usado como distribución

Condicional al resultado de **0.2**.

- [x] **4.1** — Si 0.2 confirma que no hay marca de loop-through hoy:
      agregar columna (ej. `conector.es_loop`) + función `asegurar_*`
      de migración idempotente, siguiendo el patrón ya usado para
      auditoría.
      **Resultado (2026-09-27):** en vez de un booleano `es_loop`, la
      columna es `conector.id_conector_loop_de` (FK a `conector`,
      `ON DELETE SET NULL`): guarda de QUÉ entrada es loop la salida
      (ej. MULTIVIEW 16 in / 16 loop out). Migración:
      `Modelo.asegurar_columna_loop_conector()`. API:
      `establecer_loop_de_conector` / `devolver_loop_de_conector` /
      `devolver_loops_de_conector`. Sin semilla automática y sin UI
      todavía; los moldes (`conector_catalogo`) quedan fuera.
      **4.1c (2026-09-27):** UI para cargar la marca: sección
      "Loop-through" en `_DialogoConector` (combo "Es loop de:"), mismo
      patrón que `es_entrada_referencia`.
- [x] **4.2** — Detección: conectores marcados como loop con más de una
      conexión saliente hacia equipos distintos (en vez de una sola,
      hacia el siguiente eslabón de la cadena).
      **Resultado (2026-09-27):** `Modelo.devolver_loops_como_distribucion()`
      + `linter_topologia.loops_como_distribucion_priorizados()` (ordena por
      riesgo del equipo dueño). Cuenta equipos destino distintos (ignora
      internos/virtuales, extremos sueltos, FANTASMA y el propio equipo;
      una PATCHERA cuenta). Sólo ve loops ya marcados en su ficha (4.1c).

- [x] **4.3** — UI: tarjeta "⚠️ Loop usado como distribución".
      **Resultado (2026-09-28):** tarjeta "⚠️ Loop como distribución" en
      el panel "Trabajo pendiente — Equipos" (`ui_gtk/cabledoc.py`), clave
      `loop_como_distribucion` en `Modelo.devolver_pendientes_equipos()` y
      `filtro_pendiente="loop_como_distribucion"` en `EquiposListado`
      (ids vía `linter_topologia.ids_equipos_loop_como_distribucion_priorizados`,
      ordenados por riesgo). El contador cuenta EQUIPOS distintos (no
      loops), igual que las filas del "ver →". Incluye el bugfix 4.1d:
      `establecer_loop_de_conector` normaliza ids a `int` (la ficha pasa
      `str`; el chequeo de existencia fallaba siempre).

---

## Backlog — ideas discutidas, sin planificar todavía

Quedaron sobre la mesa pero necesitan más definición antes de convertirse
en tareas (o son de prioridad menor por ahora):

- Calibrar los pesos del IRF contra la historia real de `problema_equipo`
  + `fecha_fabricacion` (curva empírica edad → falla, por `tipo_equipo`).
- Riesgo por concentración geográfica: equipos críticos concentrados en
  la misma `sala`/`rack` (riesgo correlacionado, no topológico).
- Puntos de falla a nivel `slot` dentro de una `MATRIZ` (más finos que
  "falla el equipo entero").
- Asignaciones manuales en `matriz_ruteo` como excepciones propensas a
  desincronizarse con la infraestructura real.
- "Racks tipo" implícitos a partir de imágenes repetidas en el pool del
  catálogo (detectar el rack que no sigue el patrón).
- Velocidad de alta de equipos `FANTASMA` como indicador de attrition /
  necesidad de reposición.
- Reconexiones virtuales (`escenario` aplicado) que quedan permanentes o
  se repiten sobre el mismo punto — señal de falla estructural no resuelta.
- Clustering de `problema_equipo` por `tipo_equipo` (no por equipo
  individual) para detectar modelos con falla sistemática.

---

## Orden sugerido

1. **Fase 3** (fuera de patchera) — sin dependencias, la más rápida.
2. **Fase 1** (criticidad automática) — mayor valor, reusa lo existente.
3. **Fase 0 → Fase 2** (referencia en cascada) — mayor impacto de
   seguridad, ya tiene medio camino andado.
4. **Fase 4** (loop) — depende de si hace falta tocar esquema.
