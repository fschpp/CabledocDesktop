# ui_web — CableDoc en el navegador (Fase 0)

1. Desde la raíz del repo: `python3 ui_web/build_core_zip.py`
2. (Solo si falta `ui_web/pyodide/`) `python3 ui_web/fetch_pyodide.py` — baja Pyodide del registro npm, no requiere npm.
3. `cd ui_web && python3 -m http.server 8000`
4. Abrir http://localhost:8000
5. Cargar `db.db` → "Benchmark" → "Prueba de escritura" → F5 y mirar el estado.

Fuentes de Pyodide, en orden: `ui_web/pyodide/` (local, sin internet) → jsDelivr npm → jsDelivr oficial.
Pillow solo se puede probar si Pyodide viene de CDN (la copia local no trae paquetes extra).
Los hashes "vs nativo" solo valen para el db.db del 2026-09-28.
