# ui_web — CableDoc en el navegador (Fase 0 + A.1 + A.2 + A.3)

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
- **Rutas por hash**: `#/inicio`, `#/equipos`, `#/equipos/12`… Sin `db.db` en el navegador toda ruta muestra la pantalla de carga; al cargarla se repinta sola. Las pantallas de A.4–A.10 son marcadores ("Disponible en la etapa A.x"): para implementarlas se reemplaza la entrada en `VISTAS` por una función `(ctx) → Node` con `ctx = {rpc, args, gen}` (`gen` cambia cada vez que el worker avisa que la base se cargó o cambió: sirve para invalidar cachés).
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
- Todavía no abre fichas: eso es A.4 (las filas de equipo/conector enlazarán a `#/equipos/<id>`).
- Pruebas: `python3 ui_web/tests/test_bridge.py` (arbol_equipos) y `node tests/test_shell.mjs` (escenarios `arbol_modelo`: filtro sobre ~7.000 nodos, y `arbol_vista`: virtualización, scroll, filtro, caché; más el árbol real sobre Pyodide dentro de `completo`).
