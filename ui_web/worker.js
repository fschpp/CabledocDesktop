// Web Worker (tipo módulo): corre Pyodide + core/ de CableDoc. Fase 0 (plan_pyodide_v1.md).
const VERSION = "314.0.7";
// Orden: copia local (ui_web/pyodide/) → jsDelivr npm → jsDelivr oficial.
const BASES = ["pyodide/", `https://cdn.jsdelivr.net/npm/pyodide@${VERSION}/`, `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/`];
const DBDIR = "/app/data/database", DB = DBDIR + "/db.db", PRUEBA = DBDIR + "/_prueba.db";
let CDN = null, loadPyodide = null;
for (const b of BASES) {
  const url = new URL(b, self.location.href).href;
  try { ({ loadPyodide } = await import(url + "pyodide.mjs")); CDN = url; break; }
  catch (e) { postMessage({ type: "log", msg: `⚠ No se pudo cargar ${url}pyodide.mjs: ${e.message || e}` }); }
}
if (!CDN) { postMessage({ type: "log", msg: "❌ No hay ninguna fuente de Pyodide disponible. Corré ui_web/fetch_pyodide.py o revisá la red." }); throw new Error("sin Pyodide"); }
postMessage({ type: "log", msg: "Pyodide desde: " + CDN });

let py = null;
const log = (msg) => postMessage({ type: "log", msg });
const sync = (populate) => new Promise((res, rej) => py.FS.syncfs(populate, (e) => (e ? rej(e) : res())));
const existe = (p) => { try { py.FS.stat(p); return true; } catch { return false; } };

async function estado() {
  let marcas = 0;
  if (existe(PRUEBA)) {
    marcas = Number(py.runPython(`
import sqlite3
c = sqlite3.connect("${PRUEBA}")
try: n = c.execute("select count(*) from marca").fetchone()[0]
except Exception: n = 0
c.close(); n`));
  }
  postMessage({ type: "state", dbBytes: existe(DB) ? py.FS.stat(DB).size : 0, marcas,
    wasmHeapMB: Math.round(py._module.HEAP8.length / 1048576) });
}

async function init() {
  const t0 = performance.now();
  py = await loadPyodide({ indexURL: CDN });
  log(`Pyodide ${VERSION} listo en ${((performance.now() - t0) / 1000).toFixed(2)} s`);
  const t1 = performance.now();
  const zip = await (await fetch("core.zip")).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/app" });
  py.FS.writeFile("/app/bench_web.py", await (await fetch("bench_web.py")).text());
  py.runPython("import sys; sys.path.insert(0, '/app')");
  log(`core.zip (${Math.round(zip.byteLength / 1024)} KB) montado en ${((performance.now() - t1) / 1000).toFixed(2)} s`);
  py.FS.mkdirTree(DBDIR);
  py.FS.mount(py.FS.filesystems.IDBFS, {}, DBDIR);
  await sync(true);
  log("IndexedDB (IDBFS) montado y leído");
  await estado();
  postMessage({ type: "ready", coldMs: Math.round(performance.now() - t0) });
}

const handlers = {
  async load_db({ buf }) {
    py.FS.writeFile(DB, new Uint8Array(buf));
    const t = performance.now(); await sync(false);
    log(`db.db cargado (${Math.round(buf.byteLength / 1024)} KB) y persistido en ${(performance.now() - t).toFixed(0)} ms`);
    await estado();
  },
  async bench() {
    if (!existe(DB)) return log("⚠ Primero cargá un db.db");
    py.globals.set("_report", (m) => log(m));
    const r = py.runPython(`
import json, bench_web
json.dumps(bench_web.run(_report))`);
    postMessage({ type: "bench", result: JSON.parse(r) });
    await estado();
  },
  async write_test() {
    py.runPython(`
import sqlite3, time
c = sqlite3.connect("${PRUEBA}")
c.execute("create table if not exists marca (ts text)")
c.execute("insert into marca values (?)", (time.strftime("%H:%M:%S"),))
c.commit(); c.close()`);
    const t = performance.now(); await sync(false);
    log(`Escritura SQLite + syncfs en ${(performance.now() - t).toFixed(0)} ms. Recargá la página: el contador debe seguir.`);
    await estado();
  },
  async pillow() {
    const t = performance.now();
    const lock = await (await fetch(new URL("pyodide-lock.json", CDN))).json();
    const file = lock.packages.pillow.file_name;
    const fuentes = /^https?:/.test(file) ? [file] : [
      `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/${file}`,
      new URL(file, CDN).href,
    ];
    let ok = false;
    for (const u of fuentes) {
      try { await py.loadPackage(u); py.runPython("import PIL"); ok = true; log("Pillow cargado desde " + u); break; }
      catch (e) { log("⚠ Pillow no cargó desde " + u + " (" + String(e.message || e).split("\n").pop().slice(0, 120) + ")"); }
    }
    if (!ok) return log("❌ Pillow no disponible. No bloquea el resto: solo se usa para medir imágenes raster.");
    const r = py.runPython(`
from PIL import Image
import io
im = Image.new("RGB", (64, 32), (200, 30, 30)); b = io.BytesIO(); im.save(b, "PNG")
f"Pillow OK: PNG de {len(b.getvalue())} bytes, {Image.open(io.BytesIO(b.getvalue())).size}"`);
    log(`${r} (carga ${(performance.now() - t).toFixed(0)} ms)`);
  },
  async export() {
    if (!existe(DB)) return log("⚠ No hay db.db");
    const data = py.FS.readFile(DB);
    postMessage({ type: "download", name: "db_exportado.db", data }, [data.buffer]);
  },
  async reset() {
    for (const p of [DB, PRUEBA]) if (existe(p)) py.FS.unlink(p);
    await sync(false); log("Base y marcas borradas de IndexedDB"); await estado();
  },
};

onmessage = async (e) => {
  try { await handlers[e.data.cmd](e.data); }
  catch (err) { log("❌ " + (err && err.message || err)); }
  postMessage({ type: "idle" });
};
init().catch((err) => log("❌ init: " + (err && err.message || err)));
