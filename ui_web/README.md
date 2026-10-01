# ui_web — CableDoc en el navegador (Fase 0 + A.1)

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
