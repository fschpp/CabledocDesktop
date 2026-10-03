# ui_web — CableDoc en el navegador (Fase 0 + A.1 a A.11 + B.1 + B.2)

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

## Datos: respaldo y catálogos (Fase A.10)

Pantalla `#/datos` (ítem **Datos** del menú). Todo ocurre en el navegador; nada se envía a ningún servidor.

- **Base completa**: «Exportar la base (.db)» baja `cabledoc_AAAAMMDD.db` (el archivo del worker, tal cual). «Importar una base (.db)» **reemplaza** la base de este navegador, previa confirmación. Antes de reemplazar, el archivo se valida en un temporal (`datos_web.validar_db`): cabecera SQLite, `PRAGMA quick_check` y que existan las tablas `equipo`, `conector`, `cable` y `conexion`; si no pasa, la base actual no se toca. Tras importar se persiste en IndexedDB (`syncfs`) y la app se repinta.
- **Catálogos** de equipos y de frames: mismo formato que el desktop (`.zip` con un único `.json`: `cabledoc_catalogo_equipos` v5 / `cabledoc_catalogo_frames`), así que un catálogo exportado por GTK se importa acá y al revés. Se importa con `Modelo.importar_catalogo_*` (acepta también el `.json` plano de versiones viejas). **Importar escribe en la base** (agrega moldes; con confirmación) y persiste. Los conflictos de rol/dirección de tipos que ya existían se cuentan en el aviso: como en el desktop, se conserva el valor local (no hay diálogo para elegir el importado; es B.2/B.6).
- **Archivos nuevos**: `datos_web.py` (se monta en `/app` del worker, como `bridge.py`; archivo a archivo, el worker mueve los bytes), `app/datos.js`, órdenes `datos_*` en `worker.js` y 4 métodos en `app/rpc.js` (`exportarDb`, `importarDb`, `exportarCatalogo`, `importarCatalogo`).
- **Exportar un catálogo no crea tablas**: en una base que nunca tuvo catálogo sale un `.zip` con 0 moldes. Con una base vieja, `Modelo.exportar_catalogo_*` migra el esquema al correr (igual que los motores de A.7); con el `db.db` al día del desktop es un no-op.
- **Las imágenes NO viajan**: ni en el `.db` (guarda solo `imagen.path_archivo`) ni en los catálogos. Las imágenes viven en OPFS (A.4) y `Modelo` solo ve el FS virtual, donde no están, así que `_exportar_imagen` embebe `null` y al importar el catálogo las filas `imagen` se crean sin archivo. Respaldar `data/imagen/` y `data/picon/` (carpeta o zip) y repoblar OPFS queda pendiente.
- Pruebas: `python3 ui_web/tests/test_datos.py` (17 chequeos: validación, formato del zip, exportar sin modificar datos ni crear tablas, importar zip y `.json`, rechazos) y el escenario `datos` de `node tests/test_shell.mjs` (15 chequeos con `datos_web.py` real sobre Pyodide).

## Uso sin conexión (Fase A.11)

`sw.js` es un service worker con alcance `ui_web/`. Se registra desde `app/main.js` (`app/offline.js`) **después** de que el motor Pyodide está listo, para no competir con la primera descarga. Después de la primera visita con conexión, la app abre sin red: `app.html`, los módulos de `app/`, `worker.js`, `core.zip`, los `.py` del bridge y Pyodide.

- **Solo en contexto seguro**: `https://` o `http://localhost` / `127.0.0.1`. Por IP de la LAN con `http://` el navegador no permite service workers (la app funciona igual, sin offline). En ventanas privadas de Firefox tampoco.
- **Archivos de la app**: «red primero». Con conexión se sirve siempre la versión del servidor (y se guarda); sin conexión, o si la red tarda más de 5 s, se sirve la copia. Así no hay que borrar nada al actualizar y los módulos nunca quedan mezclados entre versiones. Al instalar se guardan todos de una vez (`ARCHIVOS` en `sw.js`); si uno falta, la instalación falla en vez de dejar un offline roto.
- **Pyodide**: «caché primero» (está versionado). Se guarda al instalar desde la primera fuente que lo tenga completo, en el orden de `worker.js` (`ui_web/pyodide/` → jsDelivr npm → jsDelivr oficial); lo que falte se guarda en el primer uso con conexión.
- **No pasan por el service worker**: la base (IndexedDB) y las imágenes (OPFS + blob URL).
- **El menú muestra el estado** al pie: «Preparando el uso sin conexión…», «Listo para usar sin conexión» o, si falta el motor, «Sin conexión: falta guardar el motor…».
- **Al sumar o quitar un archivo de `app/` o un `.py` del worker hay que tocar `ARCHIVOS` en `sw.js`**; `tests/test_sw.mjs` lo verifica contra el disco. Si se cambia la versión de Pyodide hay que cambiarla en `worker.js` y en `sw.js` (también verificado). Para descartar todas las copias viejas, subir `CACHE_APP`.
- Durante el desarrollo: con DevTools → Application → Service Workers → «Update on reload» / «Bypass for network», o simplemente trabajar con conexión (red primero ya trae lo nuevo).
- Pruebas: `node ui_web/tests/test_sw.mjs` (78 chequeos con `caches`/`fetch`/`clients` simulados, sin npm) y, en `node tests/test_shell.mjs`, el pie de estado del menú (escenario `completo`).

## Formularios y diálogos genéricos (Fase B.1)

Base de todos los ABM de la Fase B. Todavía no escribe en la base (no hay funciones de escritura en el bridge): fija el patrón con el que se van a construir B.2 en adelante. Para probarlo a mano: `#/demo-formulario` (sin ítem en el menú; `app/formulario_demo.js` simula el motor y se puede borrar cuando exista el primer ABM real).

- **`app/formulario_modelo.js`** (sin DOM ni i18n): descripción de campos, `valoresIniciales`, `normalizarCampo`/`validar` y `crearPilaDeshacer`. Tipos: `texto`, `texto_largo`, `numero` (acepta coma), `entero`, `fecha` (AAAA-MM-DD, calendario real), `select` (conserva el tipo del valor de la opción) y `checkbox`. Reglas: `requerido`, `min`/`max`, `largoMax`, `patron` (+ `patronMensaje`), `validar(valor, valores)` propia. **Vacío se envía como `null`** (también el texto), para no mezclar `""` con NULL en la base. Los errores salen como `{clave, vars}`; la traducción la hace la UI.
- **`app/formulario.js`**: `abrirFormulario({titulo, campos, valores, enviar})` → `<dialog>` modal que resuelve `{resultado}` si se guardó o `null` si se canceló. Validación por campo (`aria-invalid`, `aria-describedby`, foco al primero con error); `enviar(valores)` recibe los valores ya normalizados y bloquea los botones mientras corre (sin doble envío). Si `enviar` lanza `ErrorFormulario(mensaje, {campo: texto})` se marca el campo; cualquier otro error sale en un banner dentro del diálogo, que **no se cierra**. Cancelar o Esc con cambios pregunta antes de descartar. Al cerrar devuelve el foco a quien lo abrió.
- **`confirmar({mensaje, textoOk, peligro})`** → `true`/`false`; `mensaje` puede ser un Node (para el resumen de B.11). Con `peligro` el foco inicial queda en «Cancelar».
- **Deshacer simple**: `crearPilaDeshacer(max)` + `ofrecerDeshacer(pila, texto, async () => revertir)` registra la acción y muestra un aviso con «Deshacer» (8 s). Es en memoria (no sobrevive a recargar) y, si revertir falla, la entrada se conserva para reintentar. Cada ABM define qué significa revertir su acción (p. ej. volver a dar de alta lo borrado).
- Sin `si:`/campos condicionales ni subformularios todavía: se agregan cuando un ABM real los pida.
- Pruebas: escenario `formulario` de `node tests/test_shell.mjs` (46 chequeos, solo jsdom: modelo, pila, diálogo, confirmación, deshacer, inglés).

## Catálogos básicos y primeras escrituras (Fase B.2)

Pantalla `#/catalogos` (ítem **Catálogos** del menú) con una pestaña por catálogo: marcas, tipos de equipo, tipos de conector, tipos de cable, tipos de ficha, señales, formatos de señal e imágenes (`#/catalogos/marcas|tipos-equipo|tipos-conector|tipos-cable|tipos-ficha|senales|formatos-senal|imagenes`). Es el primer ABM real: alta, edición y baja con los diálogos de B.1.

- **Escritura en el bridge**: `catalogos_web.py` (archivo nuevo, se monta en `/app` del worker y `bridge.py` lo importa al final) agrega `catalogo_lista` (lectura) y `catalogo_alta`, `catalogo_modificar`, `catalogo_baja`, `catalogo_restaurar`. Cada catálogo se describe una sola vez en `_CATALOGOS` (campos, validación, tablas que lo usan y qué les pasa al borrarlo); la UI arma el formulario con el `esquema` que devuelve `catalogo_lista`, así que **las reglas viven solo en Python**. Las escrituras llaman a los mismos métodos de `Modelo` que el desktop (ej. `establecer_rol_senal_tipo_equipo` recalcula la referencia virtual de los frames); la única excepción es `catalogo_restaurar`, que necesita fijar el id.
- **Persistencia (D4)**: `bridge.call` abre la respuesta de una escritura con `{"escribio": true` y `worker.js` hace `syncfs` a IndexedDB **antes** de contestar, y después emite un `state` (el shell lo toma como cambio de la base e invalida cachés). También se persiste si la escritura falla de forma inesperada (pudo quedar a medias); no se persiste cuando el error es de validación o un id inexistente (`sin_cambios`).
- **Errores por campo**: el bridge devuelve `{ok:false, error, campos:{campo: motivo}}`; `rpc.llamar` lo lanza como `ErrorBridge` con `.campos` y la pantalla lo convierte en `ErrorFormulario`, que marca el campo sin cerrar el diálogo. Las claves de los motivos están en `i18n_web.py` (`_WEB_B2`).
- **Nombres repetidos**: se rechazan (sin distinguir mayúsculas ni espacios de más) en todos los catálogos salvo imágenes. **Diferencia con el desktop**, que sí los permite. Una fila que ya está duplicada se puede seguir editando mientras no se le cambie el nombre.
- **Baja**: no hay baja lógica; las FK de la base anulan (`SET NULL`) o arrastran (`CASCADE`) lo que usaba el valor. Antes de confirmar, el diálogo dice cuántos registros de qué tabla quedan sin el valor y cuáles se eliminan con él (ej. borrar un tipo de equipo borra sus reglas lógicas y plantillas de conectores). La columna «En uso» de la lista muestra el total, con el detalle en el tooltip.
- **Deshacer** (pila en memoria de B.1): alta → baja del registro, solo si sigue sin uso; edición → vuelve a los valores anteriores; baja → reinserta con el mismo id **solo si no estaba en uso** (lo que lo usaba ya no se puede reconstruir, así que ahí no se ofrece).
- **Tipos de equipo**: el rol frente a la señal ofrece los 10 roles de `Modelo.ROLES_SENAL` (el desktop muestra 9: no ofrece FANTASMA). Al editar solo se llama a `establecer_rol_senal_tipo_equipo` si el rol cambió. No incluye `vida_util_anios` ni `es_distribuidor_sync`: el desktop tampoco los edita desde este diálogo.
- **Tipos de contenido de señal**: es texto libre en la base; la UI ofrece VIDEO/AUDIO/DATOS/EMBEBIDO y, al editar, conserva un valor distinto que ya exista.
- **Imágenes**: solo se edita el registro (`path_archivo`, `descripcion`). No sube archivos ni avisa si el archivo falta (el desktop sí): los archivos se cargan desde las fichas (A.4); la subida y el selector de coordenadas son B.8.
- Pruebas: `python3 ui_web/tests/test_catalogos.py` (95 chequeos: paridad con `Modelo`, FK, validación, contrato de `bridge.call`, base vieja sin tablas de señal, `integrity_check`) y, en `node tests/test_shell.mjs`, los escenarios `catalogos_modelo` (puro, 18) y `catalogos` (pantalla con el bridge real sobre Pyodide, 49). El `syncfs` del worker no se prueba en Node: va en el smoke del navegador.
