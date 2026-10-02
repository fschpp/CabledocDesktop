// Test del service worker (A.11) y de app/offline.js, en Node sin navegador (mocks de caches/fetch/clients).
// Uso:  node ui_web/tests/test_sw.mjs      (Node 18+; no necesita npm)
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
let n = 0;
const ok = (c, m) => { n++; if (!c) { console.error(`  ✖ [sw] ${m}`); process.exit(1); } };
const SW = readFileSync(path.join(WEB, "sw.js"), "utf8");
const lista = SW.match(/const ARCHIVOS = \[([\s\S]*?)\];/)[1].match(/"([^"]+)"/g).map((s) => s.slice(1, -1));

// ── 1) la lista de precaché coincide con lo que hay en disco ──
const worker = readFileSync(path.join(WEB, "worker.js"), "utf8");
const esperados = new Set(["app.html", "app.css", "index.html", "worker.js"]);
for (const m of worker.matchAll(/fetch\("([^"]+)"\)/g)) esperados.add(m[1]);           // lo que el worker pide al arrancar (core.zip, *.py)
for (const f of readdirSync(path.join(WEB, "app"))) if (/\.(js|css)$/.test(f)) esperados.add("app/" + f);
ok(lista.length === new Set(lista).size, "ARCHIVOS sin duplicados");
ok(lista.every((f) => existsSync(path.join(WEB, f))), "todo lo de ARCHIVOS existe: " + lista.filter((f) => !existsSync(path.join(WEB, f))));
ok([...esperados].every((f) => lista.includes(f)), "falta en ARCHIVOS: " + [...esperados].filter((f) => !lista.includes(f)));
ok(lista.every((f) => esperados.has(f)), "sobra en ARCHIVOS: " + lista.filter((f) => !esperados.has(f)));
for (const css of readFileSync(path.join(WEB, "app.html"), "utf8").matchAll(/href="([^"]+\.css)"/g)) ok(lista.includes(css[1]), "app.html usa " + css[1]);
ok(SW.match(/PYODIDE_VERSION = "([^"]+)"/)[1] === worker.match(/const VERSION = "([^"]+)"/)[1], "misma versión de Pyodide en sw.js y worker.js");

// ── 2) entorno simulado ──
const BASE = "http://localhost:8000/";
const red = { enLinea: true, pedidos: [], lento: 0, falta: new Set(), contenido: (u) => "v1:" + u };
const almacenes = new Map();
const cache = (nombre) => {
  if (!almacenes.has(nombre)) almacenes.set(nombre, new Map());
  const m = almacenes.get(nombre), clave = (r, ign) => { const u = typeof r === "string" ? r : r.url; return ign ? u.split("?")[0] : u; };
  return {
    async put(r, resp) { m.set(clave(r), resp); },
    async match(r, o = {}) { const k = clave(r, o.ignoreSearch); for (const [u, v] of m) if (clave(u, o.ignoreSearch) === k) return v.clone(); return undefined; },
    async keys() { return [...m.keys()].map((u) => ({ url: u })); },
  };
};
const mensajes = [], escuchas = {};
globalThis.caches = {
  open: async (n) => cache(n),
  keys: async () => [...almacenes.keys()],
  delete: async (n) => almacenes.delete(n),
  async match(r, o) { for (const n of almacenes.keys()) { const x = await cache(n).match(r, o); if (x) return x; } return undefined; },
};
globalThis.fetch = async (r) => {
  const url = typeof r === "string" ? r : r.url; red.pedidos.push(url);
  if (red.lento) await new Promise((res) => setTimeout(res, red.lento));
  if (!red.enLinea) throw new TypeError("Failed to fetch");
  if (red.falta.has(url) || [...red.falta].some((p) => url.includes(p))) return new Response("no", { status: 404 });
  return new Response(red.contenido(url), { status: 200 });
};
globalThis.self = {
  registration: { scope: BASE }, skipWaiting: () => { red.salto = true; },
  clients: { matchAll: async () => [{ postMessage: (m) => mensajes.push(m) }], claim: async () => { red.reclamo = true; } },
  addEventListener: (t, f) => { escuchas[t] = f; },
};
await import(pathToFileURL(path.join(WEB, "sw.js")).href);
ok(["install", "activate", "fetch", "message"].every((t) => escuchas[t]), "registra install/activate/fetch/message");

const evento = (extra = {}) => { const e = { esperas: [], waitUntil(p) { this.esperas.push(p); }, respondWith(p) { this.resp = p; }, ...extra }; return e; };
const correr = async (e) => { await Promise.all(e.esperas); return e; };
const pedir = async (url, { method = "GET", headers = {}, mode = "cors" } = {}) => {
  const e = evento({ request: { url, method, mode, headers: new Headers(headers) } });
  escuchas.fetch(e); return e.resp ? await e.resp : undefined;
};
const PY = "http://localhost:8000/pyodide/", NPM = "https://cdn.jsdelivr.net/npm/pyodide@314.0.7/", FULL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const archivosPy = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];

// ── 3) instalación con copia local de Pyodide ──
red.falta.add("/pyodide/");                    // sin ui_web/pyodide/: el servidor da 404 → cae a jsDelivr npm
let e = await correr((() => { const x = evento(); escuchas.install(x); return x; })());
ok(red.salto, "install llama a skipWaiting");
for (const f of lista) ok(await caches.match(BASE + f), "precacheado " + f);
ok(archivosPy.every((f) => red.pedidos.includes(NPM + f)), "Pyodide precacheado desde jsDelivr npm cuando no hay copia local");
ok(!red.pedidos.includes(FULL + "pyodide.mjs"), "no sigue a la 3.ª fuente si la 2.ª funcionó");
ok(mensajes.at(-1)?.app === true && mensajes.at(-1)?.pyodide === true, "avisa a la página: app y pyodide listos " + JSON.stringify(mensajes.at(-1)));

// ── 4) activate: limpia cachés viejas y reclama ──
cache("cabledoc-web-v0"); cache("cabledoc-pyodide-313.0.0"); cache("otra-cosa");
await correr((() => { const x = evento(); escuchas.activate(x); return x; })());
ok(!almacenes.has("cabledoc-web-v0") && !almacenes.has("cabledoc-pyodide-313.0.0"), "borra cachés viejas de cabledoc-*");
ok(almacenes.has("otra-cosa") && almacenes.has("cabledoc-web-v1"), "no toca cachés ajenas ni las vigentes");
ok(red.reclamo, "clients.claim()");

// ── 5) fetch: reglas por tipo de pedido ──
ok((await pedir(BASE + "app/shell.js", { method: "POST" })) === undefined, "no intercepta POST");
ok((await pedir(BASE + "core.zip", { headers: { range: "bytes=0-9" } })) === undefined, "no intercepta Range");
ok((await pedir("https://ejemplo.com/x.js")) === undefined, "no intercepta otros orígenes");
red.pedidos.length = 0;
ok((await (await pedir(NPM + "pyodide.asm.wasm")).text()).startsWith("v1:"), "Pyodide: sale de la caché");
ok(red.pedidos.length === 0, "Pyodide: caché primero, sin tocar la red");
red.contenido = (u) => "v2:" + u;
ok((await (await pedir(BASE + "app/shell.js")).text()).startsWith("v2:"), "app: con conexión sirve la versión nueva");
ok((await (await caches.match(BASE + "app/shell.js")).text()).startsWith("v2:"), "app: y la guarda");
red.enLinea = false;
ok((await (await pedir(BASE + "app/shell.js")).text()).startsWith("v2:"), "app: sin conexión sirve la copia");
ok((await (await pedir(BASE + "app/shell.js?x=1")).text()).startsWith("v2:"), "app: la copia ignora el query string");
ok((await (await pedir(BASE, { mode: "navigate" })).text()).includes("app.html"), "navegación sin conexión → app.html");
ok((await (await pedir(BASE + "app.html", { mode: "navigate" })).text()).includes("app.html"), "app.html sin conexión");
let cayo = false; try { await pedir(BASE + "app/inexistente.js"); } catch { cayo = true; }
ok(cayo, "sin copia y sin conexión → el error de red llega a la página");
ok((await (await pedir(NPM + "pyodide.asm.wasm")).text()).startsWith("v1:"), "Pyodide sin conexión: copia");
// servidor con error 500: si hay copia, se prefiere
red.enLinea = true; red.falta.add("app/svg.js");
const r404 = await pedir(BASE + "app/svg.js"); ok((await r404.text()).startsWith("v1:"), "app: respuesta de error del servidor → se sirve la copia");
red.falta.clear();
// red lenta (más de 5 s) con copia → gana la copia (el reloj real se acorta con un mock de setTimeout)
const setT = globalThis.setTimeout; globalThis.setTimeout = (f, ms, ...a) => setT(f, ms === 5000 ? 20 : ms, ...a);
red.lento = 300;
const t0 = Date.now(); const lenta = await pedir(BASE + "app/tema.js");
ok((await lenta.text()).startsWith("v1:") && Date.now() - t0 < 250, "red lenta con copia → sirve la copia sin esperar");
red.lento = 0; globalThis.setTimeout = setT; await new Promise((r) => setTimeout(r, 400));

// ── 6) mensaje "estado" ──
const respuestas = [];
const m = evento({ data: { tipo: "estado" }, source: { postMessage: (x) => respuestas.push(x) } }); escuchas.message(m); await correr(m);
ok(respuestas[0]?.tipo === "estado" && respuestas[0].app && respuestas[0].pyodide, "responde el estado");

// ── 7) instalación sin Pyodide disponible: la app igual se instala (parcial) ──
almacenes.clear(); mensajes.length = 0; red.enLinea = true; red.contenido = (u) => "v1:" + u;
red.falta = new Set(["/pyodide/", "pyodide@314.0.7/", "pyodide/v314.0.7/full/"]);
await correr((() => { const x = evento(); escuchas.install(x); return x; })());
ok(mensajes.at(-1)?.app === true && mensajes.at(-1)?.pyodide === false, "sin ninguna fuente de Pyodide: app sí, pyodide no");
// una fuente a medias (falta un archivo) → pasa a la siguiente
almacenes.clear(); red.falta = new Set(["/pyodide/", "npm/pyodide@314.0.7/python_stdlib.zip"]); red.pedidos.length = 0;
await correr((() => { const x = evento(); escuchas.install(x); return x; })());
ok(archivosPy.every((f) => red.pedidos.includes(FULL + f)) && mensajes.at(-1).pyodide === true, "fuente incompleta → usa la siguiente");
// falla un archivo de la app → la instalación falla (no queda un offline roto)
almacenes.clear(); red.falta = new Set(["app/dom.js"]);
let fallo = false; try { await correr((() => { const x = evento(); escuchas.install(x); return x; })()); } catch { fallo = true; }
ok(fallo, "si falta un archivo de la app la instalación falla");

// ── 8) offline.js ──
const { registrarOffline, estadoOffline, alCambiarOffline, fijarEstadoOffline } = await import(pathToFileURL(path.join(WEB, "app/offline.js")).href);
ok((await registrarOffline({}, true)) === null && estadoOffline() === "", "navegador sin service workers: no hace nada");
ok((await registrarOffline({ serviceWorker: {} }, false)) === null && estadoOffline() === "", "contexto no seguro: no hace nada");
const vistos = []; alCambiarOffline((x) => vistos.push(x));
const oyentes = []; const pedidosEstado = [];
const activo = { postMessage: (x) => pedidosEstado.push(x) };
const nav = { serviceWorker: { addEventListener: (t, f) => oyentes.push(f), register: async (u) => ({ url: u, active: null }), ready: Promise.resolve({ active: activo }) } };
const reg = await registrarOffline(nav, true);
ok(reg.url === "sw.js" && estadoOffline() === "preparando" && pedidosEstado[0]?.tipo === "estado", "registra sw.js, queda 'preparando' y pide el estado");
oyentes[0]({ data: { tipo: "estado", app: true, pyodide: false } }); ok(estadoOffline() === "parcial", "app sin pyodide → parcial");
oyentes[0]({ data: { tipo: "estado", app: true, pyodide: true } }); ok(estadoOffline() === "listo", "todo → listo");
oyentes[0]({ data: { tipo: "otra" } }); ok(estadoOffline() === "listo", "mensajes ajenos se ignoran");
ok(vistos.join() === "preparando,parcial,listo", "los oyentes ven cada cambio una sola vez: " + vistos);
fijarEstadoOffline("listo"); ok(vistos.length === 3, "mismo estado no re-notifica");
const malo = { serviceWorker: { addEventListener() {}, register: async () => { throw new Error("SecurityError"); } } };
const aviso = console.warn; console.warn = () => {};
ok((await registrarOffline(malo, true)) === null, "un fallo de registro no rompe la app"); console.warn = aviso;

console.log(`  ✔ [sw] ${n} chequeos`);
