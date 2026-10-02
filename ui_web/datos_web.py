"""CableDoc Web — respaldo e intercambio de datos (plan_pyodide_v1.md, Fase A.10).

Funciones de archivo a archivo (rutas del FS virtual de Pyodide); el worker mueve los bytes.
  - validar_db(ruta): revisa que un archivo sea una base de CableDoc usable ANTES de reemplazar la actual.
    No importa core/: sirve también cuando todavía no hay base cargada.
  - catalogo_exportar(tipo, destino): catálogo de equipos o de frames → .zip con un único .json
    (mismo formato que ui_gtk/cabledoc._escribir_json_comprimido: 'cabledoc_catalogo_equipos' v5 / 'cabledoc_catalogo_frames').
  - catalogo_importar(ruta): lee ese .zip (o un .json plano) y llama a Modelo.importar_catalogo_*. ESCRIBE en la base.
Todas devuelven un JSON {ok, ...}; los errores de uso salen como {ok: false, error: <clave i18n>}.
"""
import json
import sqlite3
import zipfile
from pathlib import Path

REQUERIDAS = ("equipo", "conector", "cable", "conexion")
CATALOGOS = {"equipos": ("cabledoc_catalogo_equipos", "catalogo_equipos.json", "equipo_catalogo"),
             "frames": ("cabledoc_catalogo_frames", "catalogo_frames.json", "frame_catalogo")}


def validar_db(ruta):
    p = Path(ruta)
    with open(p, "rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            return {"ok": False, "error": "El archivo no es una base SQLite."}
    try:
        con = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return {"ok": False, "error": "La base está dañada (quick_check falló)."}
            tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for t in REQUERIDAS:
                if t not in tablas:
                    return {"ok": False, "error": "No parece una base de CableDoc: falta la tabla «{tabla}».", "tabla": t}
            n = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            return {"ok": True, "equipos": n("equipo"), "conectores": n("conector"), "cables": n("cable")}
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        return {"ok": False, "error": "La base está dañada (quick_check falló).", "detalle": str(e)}


def _M():
    from core.modelo import Modelo
    return Modelo


def _existe_tabla(nombre):
    with _M()._conn_ctx() as conn:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nombre,)).fetchone() is not None


def catalogo_exportar(tipo, destino):
    marca, interno, tabla = CATALOGOS[tipo]
    M = _M()
    if not _existe_tabla(tabla):       # base que nunca tuvo catálogo: no se crean las tablas (solo lectura)
        data = {"tipo": marca, "version": 5, "imagenes": {}, "moldes": []}
    else:
        data = M.exportar_catalogo_equipos() if tipo == "equipos" else M.exportar_catalogo_frames()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(interno, json.dumps(data, ensure_ascii=False, indent=2))
    return json.dumps({"ok": True, "moldes": len(data["moldes"]), "nombre": interno.replace(".json", ".zip")})


def _leer(ruta):
    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta) as zf:
            nombres = [n for n in zf.namelist() if n.lower().endswith(".json")]
            if not nombres:
                raise ValueError("El archivo .zip no contiene ningún .json adentro.")
            return json.loads(zf.read(nombres[0]).decode("utf-8"))
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def catalogo_importar(ruta):
    data = _leer(ruta)
    tipo = data.get("tipo") if isinstance(data, dict) else None
    M = _M()
    if tipo == CATALOGOS["equipos"][0]:
        moldes, hijos, conflictos = M.importar_catalogo_equipos(data)
        return json.dumps({"ok": True, "tipo": "equipos", "moldes": moldes, "hijos": hijos, "conflictos": len(conflictos)}, default=str)
    if tipo == CATALOGOS["frames"][0]:
        moldes, hijos = M.importar_catalogo_frames(data)
        return json.dumps({"ok": True, "tipo": "frames", "moldes": moldes, "hijos": hijos, "conflictos": 0})
    return json.dumps({"ok": False, "error": "El archivo no es un catálogo de CableDoc válido."})
