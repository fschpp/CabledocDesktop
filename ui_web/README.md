# ui_web — CableDoc en el navegador (Fase 0 + A.1 a A.9)

1. Desde la raíz del repo: `python3 ui_web/build_core_zip.py`
2. (Solo si falta `ui_web/pyodide/`) `python3 ui_web/fetch_pyodide.py` — baja Pyodide del registro npm, no requiere npm.
3. `cd ui_web && python3 -m http.server 8000`
4. Abrir http://localhost:8000
5. Cargar `db.db` → "Benchmark" → "Prueba de escritura" → F5 y mirar el estado.

Fuentes de Pyodide, en orden: `ui_web/pyodide/` (local, sin internet) → jsDelivr npm → jsDelivr oficial.
Pillow solo se puede probar si Pyodide viene de CDN (la copia local no trae paquetes extra).
Los hashes "vs nativo" solo valen para el db.db del 2026-09-28.

## Bridge de lectura (Fase A.1)

`bridge.py` es la API JSON de solo lectura que usará toda la UI web (un método por pantalla). Se monta en `/app/bridge.py` del worker y se llama con `bridge.call(nombre, args_json)`, que siempre devuelve un JSON `{ok, data, ms}` o `{ok:false, error}`.

- Test nativo (no toca `data/database/`): `python3 ui_web/tests/test_bridge.py`
- Smoke en el navegador: cargar `db.db` → sección "4. Bridge" → "Smoke: todas las funciones". Con el db.db del 2026-09-28, `resumen` debe dar 418 equipos, 2071 conectores, 515 cables, 945 conexiones.
- Cualquier función suelta: elegirla en el selector y pasar los argumentos como JSON, ej. `{"id_equipo": 1}`.

## Shell de la app (Fase A.2)

`app.html` es la app (el `index.html` de la Fase 0 queda como página de diagnóstico, enlazada desde el pie del menú). Abrir http://localhost:8000/app.html.

- **Sin build**: módulos ES en `app/` (`main.js` → `shell.js`; `vistas.js` con la tabla `NAV`/`VISTAS`; `rpc.js` cliente del worker; `i18n.js`, `tema.js`, `errores.js`, `dom.js`). `app.css` con los colores como variables.
- **Rutas por hash**: `#/inicio`, `#/equipos`, `#/equipos/12`… Sin `db.db` en el navegador toda ruta muestra la pantalla de carga; al cargarla se repinta sola. Las pantallas de A.5–A.10 son marcadores ("Disponible en la etapa A.x"): para implementarlas se reemplaza la entrada en `VISTAS` por una función `(ctx) → Node` con `ctx = {rpc, args, gen}` (`gen` cambia cada vez que el worker avisa que la base se cargó o cambió: sirve para invalidar cachés).
- **i18n es/en/pt**: el diccionario sale de Python (`i18n_web.py` = `core/i18n.py` + cadenas propias de la web). Las cadenas nuevas se agregan en `_WEB` de `i18n_web.py` (clave en español); `core/` no se toca. El idioma se detecta del navegador y se guarda en localStorage junto con el último diccionario (la pantalla de carga ya sale traducida).
- **Tema** automático/claro/oscuro (`data-theme` en `<html>`, guardado en localStorage).
- **Errores**: una pantalla que falla muestra un panel con detalle técnico y "Reintentar"; los errores globales (`error`, `unhandledrejection`, fallo del worker) salen como aviso. Si el motor no carga, la pantalla inicial lo dice.
- Pruebas: `python3 ui_web/tests/test_i18n_web.py` y, para el shell (jsdom + Pyodide real, sin navegador), `cd ui_web/tests && npm i jsdom pyodide@314.0.7 && node test_shell.mjs`.

## Árbol de equipos (Fase A.3)

Pantalla `#/equipos`: Sala → Rack → Frame → Equipo → Conectores, la misma jerarquía que el panel "Infraestructura" de GTK (sin la sección Cables), más "Equipos sueltos (n)" por sala y "Sin ubicación (n)" al final.

- **Datos**: `bridge.arbol_equipos()` arma todo el árbol con una consulta por tabla (sin N+1) y la pantalla lo guarda en memoria una sola vez por carga de base (`app/equipos_arbol.js`). Cambiar de idioma lo vuelve a pedir/armar (las etiquetas de grupo salen traducidas).
- **Filtro** (`app/arbol.js`, sin DOM): sobre la copia en memoria, sin tocar el DOM. Todas las palabras deben aparecer en la etiqueta del nodo, en cualquier orden y sin distinguir mayúsculas ni acentos (`sony 3500`, `camara`). La etiqueta del equipo es `nombre marca tipo modelo inventario serie`. Un nodo se ve si coincide él o algún descendiente; con filtro se abren solos los ancestros y de cada nodo solo se muestran los hijos que se ven. Mínimo 2 caracteres, con 250 ms de pausa al tipear.
- **Lista virtualizada**: filas de alto fijo (`ALTO_FILA` = 30 px); el DOM solo contiene las filas de la ventana de scroll (+8 de margen), sin importar cuántos nodos haya.
- Accesibilidad: `role=tree/treeitem`, `aria-level`, `aria-expanded`; la flecha de cada fila es un botón.
- Desde A.4 las filas de equipo y conector enlazan a su ficha (`#/equipos/<id>`, `#/conectores/<id>`).
- Pruebas: `python3 ui_web/tests/test_bridge.py` (arbol_equipos) y `node tests/test_shell.mjs` (escenarios `arbol_modelo`: filtro sobre ~7.000 nodos, y `arbol_vista`: virtualización, scroll, filtro, caché; más el árbol real sobre Pyodide dentro de `completo`).

## Fichas e imágenes (Fase A.4)

Rutas: `#/equipos/<id>` (equipo), `#/conectores/<id>` (conector, resalta "Equipos" en el menú), `#/cables` (lista con filtro; máx. 500 filas a la vez) y `#/cables/<id>` (cable). `app/fichas.js` usa `equipo_ficha`, `conector_ficha`, `cable_ficha` y `cables_lista` del bridge; todo es de solo lectura y los enlaces recorren equipo ⇄ conector ⇄ cable ⇄ extremo opuesto.

- **Imágenes (camino 2 del plan, D4)**: no pasan por Pyodide ni por la base. El usuario sube `data/imagen/` (y opcionalmente `data/picon/`) desde la propia ficha cuando falta una imagen ("Elegir carpeta" / "Elegir archivos"); `app/imagenes.js` las guarda en **OPFS** con la misma ruta relativa que `imagen.path_archivo` y las muestra con blob URL bajo demanda (cacheado; se revoca al reemplazar). Se reconoce el segmento `imagen/` o `picon/` de la ruta elegida; sin él se guarda solo el nombre. Si el navegador no tiene OPFS se usa memoria (se pierden al recargar; la pantalla lo avisa). Nada se envía a ningún servidor.
- **Conectores sobre la imagen** (`app/imagen_conectores.js`): `coordenada_x/y_en_imagen` están guardadas como % (0-100) del ancho/alto (ver `Modelo`), así que el marcador va en `left:x%; top:y%` sin medir la imagen. Los marcadores numerados enlazan al conector; pasar el mouse resalta su fila en la tabla. Los que caen fuera de 0-100 no se dibujan y se listan aparte (el desktop también tiene datos así). Un bloque por archivo de imagen: primero el del equipo, luego los propios de los conectores.
- `A.10` (export/import) debería reutilizar `guardarArchivos`/`vaciarImagenes` para respaldar las imágenes junto con el `.db`.
- Pruebas: `node tests/test_shell.mjs` → escenarios `imagenes` (rutas, OPFS simulado con la lógica real de `almacenOpfs`, caché/revocación, errores parciales) y `fichas` (bridge real sobre Pyodide: enlaces, marcadores, resaltado, idioma, ids inexistentes).

## Conexiones (Fase A.5)

Rutas: `#/conexiones` (elegir equipo, con filtro), `#/conexiones/<id_equipo>` (árbol de conexiones) y `#/cadena/<id_cable>` (cadena completa de extensiones; resalta "Conexiones" en el menú). `app/conexiones.js` usa dos funciones nuevas del bridge, ambas de solo lectura: `conexiones_equipo(id_equipo)` y `cadena_extension(id_cable)`. Las fichas enlazan a ambas pantallas (equipo → árbol, cable → cadena; también el ⛓ de cada cable del árbol).

- **Árbol** (réplica de `ArbolConexionesEquipo`): equipo → 🔗 cable → equipo del otro extremo → …, con **carga perezosa** (un nivel por llamada, `conexiones_equipo`, que lee `CONEXIONES_AMBOS_EXTREMOS` igual que `Modelo.devolver_equipos_conectados_a_equipo`). Cada equipo se desarrolla una sola vez en todo el árbol; si reaparece queda como hoja marcada "ya desarrollado" (así se cortan los ciclos, igual que el desktop). Un destino con id 0/sin equipo es una hoja atenuada. "Expandir todo" abre solo lo ya cargado (no dispara cargas nuevas). Diferencia con GTK: los cables salen abiertos al cargar el equipo (menos clics); en GTK hay que abrir cada cable. Se agrupa por cable (id), en GTK por código.
- **Cadena** (réplica de `CadenaExtensionDialog`): equipo → cable → extensión → cable → … → equipo, con el cable de partida marcado (👈), el armado de cada extensión (✓ / ⚠ MAL ARMADO / no verificado) y los avisos de extremo suelto y referencia circular. `cadena_extension` reimplementa `Modelo.resolver_cadena_extension` sin `asegurar_tablas_extension_cable()` (que escribe): `test_bridge.py` verifica que da los mismos eslabones. En una base sin tabla `extension_cable` la cadena es solo el cable.
- Pruebas: `test_bridge.py` (paridad con `Modelo`: filas del árbol y eslabones de la cadena, ciclo, extremo suelto, tabla ausente) y escenario `conexiones` de `node tests/test_shell.mjs` (35 chequeos con el bridge real: carga perezosa, ciclo, hoja, contraer/expandir, errores, enlaces, inglés).

## Ubicaciones: rack, frame/slots y patcheras (Fase A.6)

Rutas: `#/ubicaciones` (salas → racks, racks sin sala y frames), `#/racks/<id>`, `#/frames/<id>` y `#/patcheras` (las tres resaltan "Ubicaciones"). Todo en SVG, solo lectura. Datos del bridge: `ubicaciones`, `rack_vista`, `frame_vista` y `patcheras_global`; el JS solo dibuja (`app/ubicaciones.js`, `app/patcheras.js`, helpers en `app/svg.js`).

- **Rack** (réplica de `VistaRack`): una fila por orificio, 1 U = 3 orificios. Equipo (azul), frame (ámbar), bandeja (verde: 2+ dispositivos en los mismos orificios, se funden si se repiten en filas seguidas) y libre (gris). Equipo y frame enlazan a su ficha; las bandejas se navegan desde la tabla de abajo. Un rack sin `cantidad_maxima` se asume de 42 U. Lo que empieza más allá del último orificio se avisa (GTK lo omite sin decir nada).
- **Frame** (réplica de `VistaFrameSlots`): rectángulos de los slots sobre la imagen, en píxeles de la imagen (se mide al cargarla, a diferencia de los conectores, que son %). La imagen es la del frame o, si no tiene, la del primer slot que la tenga; sin imagen cargada (subir `data/imagen`, ver A.4) se dibujan solo los rectángulos. Slot sin medida = 50 × 30. Los slots se numeran por nombre; los que tienen equipo toman un color de la paleta en orden de aparición y los vacíos van en gris.
- **Patcheras** (réplica de `PatcherasVista` en modo global): un bloque por rack, una franja por frame y una columna por módulo (número = el que trae el nombre del slot). Fila A = `BACK_ENTRADA`/`FRONT_DERIVACION`, fila B = `BACK_SALIDA`/`FRONT_INSERCION`, siempre por función de patchera (un conector sin función asignada no se dibuja). El color del orificio es el equipo cableado por atrás (✖ = fantasma). Los patchcords del frente son una curva (une dos módulos del mismo rack) o un cabo suelto; los que cambian de rack son cabos hasta activar "Cables entre racks", que dibuja la curva real. No está el modo "por equipo" ni el color por auditoría ni el export.
- Pruebas: `test_bridge.py` (segmentos y slots contra `Modelo`, patcheras con jumpers/fantasma) y escenario `ubicaciones` de `node tests/test_shell.mjs` (47 chequeos con el bridge real).

## Análisis (Fase A.7)

Pantalla `#/analisis` con cuatro pestañas (`app/analisis.js`, estilos en `app/analisis.css`). Todo es de solo lectura: **no se guarda nada**, ni siquiera el caché de riesgo (`riesgo_equipo_cache`).

- **Impacto** (`#/analisis/impacto/equipo|cable|rack[/<id>]`): `GraphImpactAnalyzer` (`simular_falla_equipo`, `simular_desconexion`, `simular_perdida_rack`). Muestra equipos sin señal (con % del parque y puntos finales afectados), cables afectados y reglas lógicas que dejan de cumplirse. Las fichas de equipo y cable enlazan acá.
- **Riesgo (IRF)** (`#/analisis/riesgo`): `RiskEngine.calcular_todos(persistir=False)`, sin guardar. Tarda ~3 s con la base real: no corre solo, hay botón "Calcular IRF" y el resultado queda en memoria mientras no cambie la base (`ctx.gen`). Filtro por nivel y por texto; el tooltip de probabilidad/riesgo muestra edad, uso e historial.
- **Diagnóstico** (`#/analisis/diagnostico[/equipo/<id> | /<id_conector>]`): `MotorDiagnostico` + `SesionDiagnostico`. El bridge es **sin estado**: la UI manda `ramas` (bifurcaciones elegidas) y `respuestas` (`[[indice, "SI"|"NO"|"NO_SE"], ...]`) y recibe la cadena y la sesión rearmadas; "Deshacer" es reenviar sin la última respuesta. Sin puntos de test marcados en el tramo, la UI deja elegir a mano (como `elegir_manual` del desktop). La ficha del conector enlaza acá.
- **Topología** (`#/analisis/topologia`): las 4 reglas de `linter_topologia.py` (fuera de patchera, fuera de distribuidor, loop en uso, referencia en cascada). Se ordenan por el riesgo **cacheado en la base**; si la base no lo trae, la pantalla avisa que los hallazgos no están priorizados (recalcularlo es una escritura: Fase B).

Funciones nuevas del bridge: `impacto_equipo`, `impacto_cable`, `impacto_rack`, `riesgo_irf`, `conectores_de_equipo`, `diagnostico`, `linter_topologia`. Los ids de los motores de `core/` (str) se convierten a int en la frontera.

Nota sobre "solo lectura": con una base vieja, los motores de `core/` migran el esquema al correr (columnas nuevas, tablas auxiliares vacías, semilla de `parametro_riesgo`). Con el `db.db` del desktop, que ya está al día, es un no-op; los datos nunca se modifican (`test_analisis.py` lo verifica).

Pruebas: `python3 ui_web/tests/test_analisis.py` (bridge, topología de 7 equipos) y el escenario `analisis` de `node tests/test_shell.mjs` (62 chequeos con el bridge real sobre Pyodide: navegación, impacto, IRF, bisección completa con deshacer/reiniciar, linter, enlaces desde las fichas, inglés).

## Escenarios (Fase A.8)

Pantalla `#/escenarios` (`app/escenarios.js`; los estilos están en `app/analisis.css`). Es de solo lectura: se **abren y evalúan** los escenarios que el escritorio guardó en la base (tablas `escenario` y `escenario_cambio`). Crear, editar y aplicar a la infraestructura es B.11.

- **Lista** (`#/escenarios`): nombre, estado (borrador / simulado / aprobado / aplicado / descartado), resumen de cambios por tipo y fecha de la última edición, del más reciente al más viejo (`escenarios_lista`).
- **Ficha y evaluación** (`#/escenarios/<id>`): los cambios (falla de equipo, cable cortado, reconexión virtual) con enlaces a equipos, cables y conectores, y el resultado de `Escenario.evaluar()` (`escenario_evaluar`): todos los cambios juntos en un solo cálculo, como el desktop. Corre sola al abrir (milisegundos). Con reconexiones virtuales muestra el comparativo **antes → después** y los equipos recuperados; sin ellas, los equipos sin señal, puntos finales y cables afectados, y las reglas lógicas que dejan de cumplirse. Los equipos que fallan en el escenario no cuentan como "sin señal" (igual que el motor).
- **Bridge** (`bridge.py`): `escenarios_lista`, `escenario_ficha` (datos + cambios con nombres, sin evaluar; la usa `escenario_evaluar` y queda lista para B.11) y `escenario_evaluar`. Usa el motor real `core/escenario_engine.py`; `core/` y `core.zip` no cambian.
- **Solo lectura de verdad**: las tablas se leen con `_rows_opt` (una base que nunca las creó muestra la lista vacía y **no** se crean: `Modelo.asegurar_tablas_escenario` escribiría). Evaluar no guarda el resultado, no cambia el estado del escenario y la reconexión virtual **no** crea cables (eso lo hace `aplicar_a_infraestructura`, B.11).
- Un escenario `aplicado` se evalúa sobre el estado actual de la base, que ya incluye sus cambios (la pantalla lo avisa). Si una reconexión apunta a un conector que ya no existe, el motor la ignora y la pantalla lo informa sin romper el resto.

Pruebas: `python3 ui_web/tests/test_escenarios.py` (bridge: lista, ficha, 5 escenarios evaluados, coherencia con `Escenario.evaluar()`, solo lectura) y el escenario `escenarios` de `node tests/test_shell.mjs` (35 chequeos con el bridge real sobre Pyodide: lista, fichas, avisos, enlaces, errores de ruta, inglés y portugués).

## Búsqueda global (Fase A.9)

Pantalla `#/busqueda` (ítem **Búsqueda** del menú) y una caja en la barra superior de todas las pantallas: Enter lleva a `#/busqueda/<texto>`; la tecla `/` enfoca la caja desde cualquier pantalla (si ya se está escribiendo en un campo, no se roba). Busca a la vez en **equipos, conectores, cables, salas, racks y frames**. Solo lectura.

- **Datos**: `bridge.busqueda_indice()` devuelve una lista plana (una fila por entidad: `t` tipo, `i` id, `l` etiqueta, `d` datos que se muestran, `x` texto que solo se busca). La pantalla la pide **una vez por carga de base** y el filtro corre en memoria (`app/busqueda_modelo.js`, sin DOM); no hay consultas por tecla.
- **Qué se busca en cada tipo**: equipo = nombre, tipo, marca, modelo, inventario y serie (los mismos campos que la etiqueta del árbol de A.3 y del panel de GTK/Kivy: `sony 3500` o un número de serie encuentran el equipo); conector = nombre, tipo de conector y equipo (`cam 1 out`); cable = código, estado, tipo y, de cada extremo, `equipo conector` (en el desktop un cable aparece si matchea alguna de sus conexiones); sala = nombre; rack = nombre y sus salas; frame = nombre, marca/modelo, inventario y su rack. Los conectores del equipo 0 («sin equipo») no entran; los cables internos sí (como en el árbol del desktop) y se marcan «interna».
- **Reglas** (las mismas del filtro del árbol): todas las palabras deben aparecer, en cualquier orden, sin distinguir mayúsculas ni acentos; mínimo 2 caracteres; pausa de 200 ms al tipear. Dentro de cada tipo van primero los que **empiezan** con la primera palabra, luego los que la llevan en el nombre y al final los que coinciden solo por sus datos (equipo, marca, extremos…); a igual puntaje, orden alfabético.
- **Presentación**: grupos en el orden del árbol (Salas, Racks, Frames, Equipos, Conectores, Cables) y chips por tipo con su cantidad (los tipos sin resultados no se ofrecen). En «Todos» se muestran 25 filas por tipo con «Ver todos (n)»; en un tipo, hasta 300 filas. Cada resultado enlaza a su ficha (`#/equipos/<id>`, `#/conectores/<id>`, `#/cables/<id>`, `#/racks/<id>`, `#/frames/<id>`); las salas no tienen ficha y enlazan a `#/ubicaciones`.
- **Ruta**: la búsqueda queda en la URL (`#/busqueda/sony%203500`, con tipo `#/busqueda/mon/equipo`) y se actualiza al tipear **sin repintar** la pantalla, así que se puede copiar el enlace.
- Los nombres de la base se insertan como texto (nunca como HTML).
- Pruebas: `python3 ui_web/tests/test_busqueda.py` (índice contra una base armada con `schema_db.sql`: tipos, exclusiones, extremos de cable, coherencia con `arbol_equipos`, solo lectura) y, en `node tests/test_shell.mjs`, los escenarios `busqueda_modelo` (filtro puro, 20.000 items) y `busqueda` (pantalla y caja de la barra con el bridge real: acentos, orden, chips, tope por grupo, ruta, tecla `/`, caché por carga de base, es/en/pt, error del bridge).
- No incluido (queda para etapas siguientes): señales y escenarios como resultados, resaltado de las palabras encontradas, búsqueda en notas/observaciones.
