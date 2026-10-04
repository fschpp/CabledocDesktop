// Service worker (Fase A.11): CableDoc Web se abre sin conexión después de la primera visita.
// Alcance = la carpeta de este archivo (ui_web/). Solo funciona en contexto seguro (https o http://localhost / 127.0.0.1).
//   · Archivos de la app (mismo origen): "red primero" → si hay conexión siempre se sirve la versión nueva (y se guarda);
//     sin conexión, o si la red tarda más de 5 s, se sirve la copia guardada. Así los módulos nunca quedan mezclados entre versiones.
//   · Pyodide (copia local pyodide/ o jsDelivr): "caché primero" — está versionado, no cambia.
//   · La base de datos NO pasa por acá (vive en IndexedDB) ni las imágenes (OPFS + blob URL).
// Si se cambia la versión de Pyodide en worker.js hay que cambiarla también acá (lo verifica tests/test_sw.mjs).
const PYODIDE_VERSION = "314.0.7";
const CACHE_APP = "cabledoc-web-v1";            // subir el número para descartar copias viejas de golpe
const CACHE_PYODIDE = `cabledoc-pyodide-${PYODIDE_VERSION}`;
const TIMEOUT_MS = 5000;
const BASE = self.registration.scope;            // siempre termina en "/"

// Todo lo que la app pide al arrancar o al navegar. tests/test_sw.mjs verifica que coincida con lo que hay en disco.
const ARCHIVOS = [
  "app.html", "app.css", "index.html", "worker.js", "core.zip",
  "bridge.py", "i18n_web.py", "datos_web.py", "catalogos_web.py", "cables_web.py", "equipos_web.py", "bench_web.py",
  "app/analisis.css", "app/busqueda.css",
  "app/analisis.js", "app/arbol.js", "app/busqueda.js", "app/busqueda_modelo.js", "app/cables_abm.js", "app/cables_modelo.js", "app/catalogos.js", "app/catalogos_modelo.js", "app/conexiones.js", "app/datos.js",
  "app/dom.js", "app/equipos_abm.js", "app/equipos_arbol.js", "app/equipos_modelo.js", "app/errores.js", "app/escenarios.js", "app/fichas.js", "app/formulario.js", "app/formulario_demo.js",
  "app/formulario_modelo.js", "app/i18n.js",
  "app/imagen_conectores.js", "app/imagenes.js", "app/main.js", "app/offline.js", "app/patcheras.js", "app/rpc.js",
  "app/shell.js", "app/svg.js", "app/tema.js", "app/ubicaciones.js", "app/vistas.js",
];
// Mismo orden de fuentes que worker.js (copia local → jsDelivr npm → jsDelivr oficial).
const PYODIDE_BASES = ["pyodide/", `https://cdn.jsdelivr.net/npm/pyodide@${PYODIDE_VERSION}/`, `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`]
  .map((b) => new URL(b, BASE).href);
const PYODIDE_ARCHIVOS = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];

const esPyodide = (href) => PYODIDE_BASES.some((b) => href.startsWith(b));
const esperar = (ms) => new Promise((res) => setTimeout(() => res(null), ms));
const OPC = { ignoreSearch: true, ignoreVary: true };

async function guardar(cache, req, resp) { if (resp && resp.ok) await cache.put(req, resp.clone()); return resp; }

async function precachearApp() {
  const cache = await caches.open(CACHE_APP);
  // cache: "reload" salta la caché HTTP del navegador: la copia guardada es la del servidor, no una vieja.
  await Promise.all(ARCHIVOS.map(async (f) => {
    const req = new Request(new URL(f, BASE).href, { cache: "reload" });
    const r = await fetch(req);
    if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
    await cache.put(req, r);
  }));
}

// Mejor esfuerzo: si no hay red o falta una fuente, la instalación sigue y Pyodide se guarda en el primer uso con conexión.
async function precachearPyodide() {
  const cache = await caches.open(CACHE_PYODIDE);
  for (const base of PYODIDE_BASES) {
    const res = await Promise.allSettled(PYODIDE_ARCHIVOS.map(async (f) => {
      const url = new URL(f, base).href, r = await fetch(url);
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      await cache.put(url, r);
    }));
    if (res.every((x) => x.status === "fulfilled")) return true;
  }
  return false;
}

async function estado() {
  const app = !!(await caches.match(new URL("app.html", BASE).href, OPC));
  const cache = await caches.open(CACHE_PYODIDE);
  const pyodide = (await cache.keys()).some((r) => r.url.endsWith("/pyodide.asm.wasm"));
  return { tipo: "estado", app, pyodide };
}
async function avisar() {
  const e = await estado();
  for (const c of await self.clients.matchAll({ includeUncontrolled: true })) c.postMessage(e);
}

async function redPrimero(req) {
  const cache = await caches.open(CACHE_APP);
  const red = fetch(req).then((r) => guardar(cache, req, r));
  red.catch(() => {});                                   // si la copia gana la carrera, que un fallo tardío de la red no quede sin atender
  let r = null;
  try { r = await Promise.race([red, esperar(TIMEOUT_MS)]); } catch { /* sin conexión */ }
  if (r && r.ok) return r;
  const copia = (await cache.match(req, OPC)) || (req.mode === "navigate" ? await cache.match(new URL("app.html", BASE).href, OPC) : null);
  if (copia) return copia;
  return r || red;                                       // sin copia: lo que diga la red (propaga el error si no hay conexión)
}

async function cachePrimero(req) {
  const cache = await caches.open(CACHE_PYODIDE);
  const hit = await cache.match(req, OPC);
  return hit || guardar(cache, req, await fetch(req));
}

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil((async () => { await precachearApp(); await precachearPyodide(); await avisar(); })());
});
self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith("cabledoc-") && k !== CACHE_APP && k !== CACHE_PYODIDE) await caches.delete(k);
    await self.clients.claim();
    await avisar();
  })());
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || req.headers.has("range")) return;
  const href = req.url;
  if (esPyodide(href)) e.respondWith(cachePrimero(req));
  else if (href.startsWith(BASE)) e.respondWith(redPrimero(req));
});
self.addEventListener("message", (e) => {
  if (e.data?.tipo === "estado") e.waitUntil(estado().then((r) => e.source?.postMessage(r)));
});
