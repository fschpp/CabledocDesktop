// Test del shell web (Fase A.2) en Node: jsdom + Pyodide real (sin navegador).
// Uso:  cd ui_web/tests && npm i jsdom pyodide@314.0.7 && node test_shell.mjs
// Corre cada escenario en un proceso aparte (los módulos de app/ guardan estado global: idioma, oyentes).
import { JSDOM } from "jsdom";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), WEB = path.resolve(AQUI, "..");
const escenario = process.argv[2];
const ESCENARIOS = ["completo", "motor_caido", "idioma_cacheado", "rpc"];

if (!escenario) {
  let mal = 0;
  for (const e of ESCENARIOS) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), e], { stdio: "inherit" });
    if (r.status !== 0) mal++;
  }
  console.log(mal ? `✖ ${mal} escenario(s) fallaron` : "✔ todos los escenarios OK");
  process.exit(mal ? 1 : 0);
}

// ── Entorno DOM (se instala con instalarDom(); Pyodide debe cargarse ANTES: si ve globalThis.window cree que es un navegador) ──
let window, document, localStorage;
function instalarDom() {
  const dom = new JSDOM(readFileSync(path.join(WEB, "app.html"), "utf8"), { url: "http://localhost/app.html", pretendToBeVisual: true });
  window = dom.window; document = window.document; localStorage = window.localStorage;
  Object.assign(globalThis, { window, document, location: window.location, localStorage });
  Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true });
  localStorage.setItem("cabledoc.lang", "es");   // jsdom dice "en-US"; sin esto el shell autodetecta inglés
}
const $ = (s) => document.querySelector(s);
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));
let n = 0;
const ok = (c, m) => { n++; if (!c) { console.error(`  ✖ [${escenario}] ${m}`); process.exit(1); } };
const cambiar = async (sel, valor) => { const el = $(sel); el.value = valor; el.dispatchEvent(new window.Event("change", { bubbles: true })); await tick(); };
const ir = async (hash) => { window.location.hash = hash; await tick(80); };

// ── rpc falso (misma interfaz que app/rpc.js) ──
function rpcBase() {
  const oy = {}, emitir = (t, d) => (oy[t] || []).forEach((f) => f(d));
  let res, rej; const listo = new Promise((a, b) => { res = a; rej = b; }); listo.catch(() => {});
  return { oy, emitir, res, rej, rpc: { listo, on: (t, f) => (oy[t] ||= []).push(f) } };
}

async function rpcPyodide() {              // rpc real: Pyodide + core.zip + bridge.py + i18n_web.py, igual que worker.js
  const { loadPyodide } = await import("pyodide");
  const py = await loadPyodide();
  const zip = readFileSync(path.join(WEB, "core.zip"));   // ArrayBuffer propio (igual que fetch().arrayBuffer() en el worker)
  py.unpackArchive(zip.buffer.slice(zip.byteOffset, zip.byteOffset + zip.byteLength), "zip", { extractDir: "/app" });
  for (const f of ["bridge.py", "i18n_web.py"]) py.FS.writeFile("/app/" + f, readFileSync(path.join(WEB, f), "utf8"));
  py.runPython("import sys; sys.path.insert(0, '/app')");
  py.FS.mkdirTree("/app/data/database");
  const DB = "/app/data/database/db.db";
  const b = rpcBase();
  const estado = () => b.emitir("state", { type: "state", dbBytes: (() => { try { return py.FS.stat(DB).size; } catch { return 0; } })() });
  const rpc = {
    ...b.rpc,
    async llamar(fn, args = {}) {
      py.globals.set("_fn", fn); py.globals.set("_args", JSON.stringify(args));
      let r;
      try { statSync(DB); r = JSON.parse(py.runPython("import bridge\nbridge.call(_fn, _args)")); }
      catch { r = { ok: false, error: "Primero cargá un db.db" }; }
      if (!r.ok) { const { ErrorBridge } = await import(pathToFileURL(path.join(WEB, "app/errores.js")).href); throw new ErrorBridge(fn, r.error); }
      return r.data;
    },
    async diccionario(lang) { py.globals.set("_lang", lang); return JSON.parse(py.runPython("import i18n_web\ni18n_web.diccionario_json(_lang)")); },
    cargarDb(buf) { py.FS.writeFile(DB, new Uint8Array(buf)); estado(); },
  };
  const statSync = (p) => py.FS.stat(p);
  // "archivo" db.db de prueba: esquema + 2 equipos, hecho con sqlite3 dentro de Pyodide
  py.runPython(`
import sqlite3
c = sqlite3.connect("/tmp/fixture.db"); c.executescript(open("/app/data/schema_db.sql", encoding="utf-8").read())
c.executescript("""INSERT INTO tipo_equipo(id_tipo_equipo,nombre,rol_senal) VALUES (1,'CAMARA','FUENTE');
INSERT INTO equipo(id_equipo,id_tipo_equipo,nombre) VALUES (1,1,'CAM 1'),(2,1,'CAM 2');"""); c.commit(); c.close()`);
  const fixture = py.FS.readFile("/tmp/fixture.db");
  b.res({ type: "ready" });                // el estado inicial lo emite emitirEstado() cuando el shell ya escucha
  return { rpc, b, fixture, py, emitirEstado: estado, fallar: (v) => (rpc.llamar = async (fn) => { const { ErrorBridge } = await import(pathToFileURL(path.join(WEB, "app/errores.js")).href); throw new ErrorBridge(fn, v); }) };
}

if (escenario === "completo") {
  const E = await rpcPyodide();
  instalarDom();
  const { iniciar } = await import(pathToFileURL(path.join(WEB, "app/shell.js")).href);
  const p = iniciar(E.rpc); E.emitirEstado(); await p; await tick();
  // 1) sin base: pantalla de carga en cualquier ruta
  ok($("#app") && !$("#splash"), "el shell reemplaza al splash");
  ok($("#contenido h2").textContent === "Falta la base de datos", "sin db → pantalla de carga");
  ok($("#lateral a[data-id=inicio]").getAttribute("aria-current") === "page", "Inicio activo por defecto");
  ok($("#contenido input[type=file]"), "hay selector de archivo");
  // 2) cargar la base → Inicio con conteos reales
  E.rpc.cargarDb(E.fixture.buffer.slice(E.fixture.byteOffset, E.fixture.byteOffset + E.fixture.byteLength)); await tick(300);
  ok($("#contenido h2").textContent === "Resumen de la instalación", "con db → Inicio");
  const num = (et) => [...document.querySelectorAll(".tarjeta")].find((c) => c.querySelector(".et").textContent === et)?.querySelector(".n").textContent;
  ok(num("Equipos") === "2", "Equipos = 2, vino " + num("Equipos"));
  ok($("#db-info").textContent.startsWith("Base cargada ("), "pie con tamaño de base");
  // 3) navegación
  await ir("#/equipos");
  ok($("#lateral a[data-id=equipos]").getAttribute("aria-current") === "page" && !$("#lateral a[data-id=inicio]").hasAttribute("aria-current"), "aria-current sigue la ruta");
  ok($("#contenido .pendiente").textContent.includes("Disponible en la etapa A.3 del plan."), "pantalla pendiente con su etapa");
  await ir("#/zzz");
  ok($("#contenido h2").textContent === "Pantalla desconocida", "ruta desconocida");
  await ir("#/equipos/12/extra");
  ok($("#contenido h2").textContent === "Equipos", "ruta con argumentos extra");
  // 4) idioma (diccionario desde Python: core + web) y persistencia
  await cambiar("#sel-idioma", "en");
  ok($("#lateral a[data-id=equipos]").textContent.includes("Equipment"), "nav en inglés");
  ok($("#contenido .pendiente").textContent.includes("Available in stage A.3 of the plan."), "pantalla pendiente en inglés (con {etapa})");
  ok(localStorage.getItem("cabledoc.lang") === "en" && document.documentElement.lang === "en", "idioma persistido y <html lang>");
  ok($("#sel-idioma").value === "en", "el selector conserva el idioma");
  await ir("#/inicio");
  ok($("#contenido h2").textContent === "Installation summary", "Inicio en inglés");
  await cambiar("#sel-idioma", "pt");
  ok($("#lateral a[data-id=cables]").textContent.includes("Cabos"), "nav en portugués");
  await cambiar("#sel-idioma", "es");
  ok($("#lateral a[data-id=cables]").textContent.includes("Cables") && document.documentElement.lang === "es", "vuelve a español");
  // 5) tema
  await cambiar("#sel-tema", "oscuro"); ok(document.documentElement.getAttribute("data-theme") === "dark" && localStorage.getItem("cabledoc.tema") === "oscuro", "tema oscuro");
  await cambiar("#sel-tema", "claro"); ok(document.documentElement.getAttribute("data-theme") === "light", "tema claro");
  await cambiar("#sel-tema", "auto"); ok(!document.documentElement.hasAttribute("data-theme"), "tema auto quita data-theme");
  // 6) error en una pantalla: panel con detalle y reintento
  E.fallar("Boom de prueba");
  await ir("#/equipos"); await ir("#/inicio");
  ok($("#contenido .error-panel h2").textContent === "Algo salió mal", "panel de error");
  ok($("#contenido .error-panel pre").textContent.includes("Boom de prueba"), "detalle técnico visible");
  ok(!document.querySelector("#toasts .toast"), "el error de pantalla no duplica toast");
  // 7) errores globales → toast
  window.dispatchEvent(new window.ErrorEvent("error", { error: new Error("global de prueba"), message: "global de prueba" }));
  ok($("#toasts .toast").textContent.includes("global de prueba"), "toast por error global");
  $("#toasts .toast button").click(); ok(!$("#toasts .toast"), "toast se cierra");
  // 8) menú móvil
  $("#btn-menu").click(); ok(document.body.classList.contains("menu-abierto") && $("#btn-menu").getAttribute("aria-expanded") === "true", "abre el menú");
  await ir("#/cables"); ok(!document.body.classList.contains("menu-abierto"), "navegar cierra el menú");
}

if (escenario === "motor_caido") {
  instalarDom(); const { iniciar } = await import(pathToFileURL(path.join(WEB, "app/shell.js")).href);
  const b = rpcBase(); const p = iniciar(b.rpc);
  b.rej(new Error("fallo simulado")); await p; await tick();
  ok($("#splash") && !$("#app"), "el splash sigue visible");
  ok($("#splash").textContent.includes("No se pudo cargar el motor") && $("#splash pre").textContent.includes("fallo simulado"), "mensaje + detalle del fallo");
}

if (escenario === "idioma_cacheado") {
  instalarDom(); const { iniciar } = await import(pathToFileURL(path.join(WEB, "app/shell.js")).href);
  localStorage.setItem("cabledoc.lang", "en");
  localStorage.setItem("cabledoc.i18n.en", JSON.stringify({ "Iniciando el motor (Pyodide)…": "Starting the engine (Pyodide)…" }));
  const b = rpcBase(); const p = iniciar(b.rpc); await tick();
  ok($("#splash-txt").textContent === "Starting the engine (Pyodide)…", "el splash sale traducido desde la caché");
  ok(document.documentElement.lang === "en", "<html lang> desde el arranque");
  b.oy.state?.forEach((f) => f({ dbBytes: 0 }));
  b.res({ type: "ready" });
  const llamadas = []; b.rpc.diccionario = async (l) => { llamadas.push(l); return { textos: { Inicio: "Home" } }; };
  await p; await tick();
  ok(llamadas.join() === "en", "tras ready pide el diccionario vigente");
  ok($("#lateral a[data-id=inicio]").textContent.includes("Home"), "nav con el diccionario nuevo");
  ok($("#sel-idioma").value === "en", "selector en inglés");
}

if (escenario === "rpc") {                // app/rpc.js contra un Worker simulado (mismo protocolo que worker.js)
  instalarDom();
  const enviados = []; let w;
  globalThis.Worker = class { constructor(url, o) { w = this; this.url = url; this.o = o; } postMessage(m) { enviados.push(m); } };
  const { crearRpc } = await import(pathToFileURL(path.join(WEB, "app/rpc.js")).href);
  const { ErrorBridge } = await import(pathToFileURL(path.join(WEB, "app/errores.js")).href);
  const r = crearRpc("worker.js");
  ok(w.url === "worker.js" && w.o.type === "module", "worker de tipo módulo");
  const estados = []; r.on("state", (d) => estados.push(d.dbBytes));
  w.onmessage({ data: { type: "state", dbBytes: 7 } }); ok(estados[0] === 7, "reenvía eventos a los oyentes");
  w.onmessage({ data: { type: "ready", coldMs: 1 } }); ok((await r.listo).coldMs === 1, "listo se resuelve con ready");
  // llamar: ok
  let p = r.llamar("resumen", { a: 1 });
  ok(enviados.at(-1).cmd === "call" && enviados.at(-1).fn === "resumen" && enviados.at(-1).args.a === 1, "mensaje call");
  w.onmessage({ data: { type: "call", id: enviados.at(-1).id, result: JSON.stringify({ ok: true, data: { equipo: 3 }, ms: 1 }) } });
  ok((await p).equipo === 3, "devuelve data");
  // llamar: el bridge dice ok:false → ErrorBridge con fn
  p = r.llamar("equipo_ficha", { id_equipo: 9 });
  w.onmessage({ data: { type: "call", id: enviados.at(-1).id, result: JSON.stringify({ ok: false, error: "KeyError: 9" }) } });
  try { await p; ok(false, "debió rechazar"); } catch (e) { ok(e instanceof ErrorBridge && e.fn === "equipo_ficha" && e.message === "KeyError: 9", "ErrorBridge"); }
  // fallo del handler del worker → rechaza con el mensaje
  p = r.llamar("x"); w.onmessage({ data: { type: "fail", id: enviados.at(-1).id, error: "boom" } });
  try { await p; ok(false, "debió rechazar"); } catch (e) { ok(e.message === "boom", "fail rechaza la promesa"); }
  // diccionario
  p = r.diccionario("pt"); ok(enviados.at(-1).cmd === "i18n" && enviados.at(-1).lang === "pt", "mensaje i18n");
  w.onmessage({ data: { type: "i18n", id: enviados.at(-1).id, result: JSON.stringify({ lang: "pt", textos: { Inicio: "Início" } }) } });
  ok((await p).textos.Inicio === "Início", "devuelve diccionario");
  // cargarDb transfiere el buffer
  r.cargarDb(new ArrayBuffer(4)); ok(enviados.at(-1).cmd === "load_db" && enviados.at(-1).buf.byteLength === 4, "load_db");
  // fatal: rechaza lo pendiente
  p = r.llamar("y"); w.onmessage({ data: { type: "fatal", msg: "sin Pyodide" } });
  try { await p; ok(false, "debió rechazar"); } catch (e) { ok(e.message === "sin Pyodide", "fatal rechaza pendientes"); }
  // fatal antes de ready: listo rechaza
  const r2 = crearRpc(); w.onmessage({ data: { type: "fatal", msg: "x" } });
  try { await r2.listo; ok(false, "debió rechazar"); } catch (e) { ok(e.message === "x", "fatal rechaza listo"); }
}

console.log(`  ✔ [${escenario}] ${n} chequeos`);
process.exit(0);
