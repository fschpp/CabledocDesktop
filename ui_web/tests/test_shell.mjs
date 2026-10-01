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
const ESCENARIOS = ["completo", "motor_caido", "idioma_cacheado", "rpc", "arbol_modelo", "arbol_vista"];

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
  Object.assign(globalThis, { window, document, location: window.location, localStorage, requestAnimationFrame: window.requestAnimationFrame.bind(window) });
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
  await ir("#/cables");
  ok($("#lateral a[data-id=cables]").getAttribute("aria-current") === "page" && !$("#lateral a[data-id=inicio]").hasAttribute("aria-current"), "aria-current sigue la ruta");
  ok($("#contenido .pendiente").textContent.includes("Disponible en la etapa A.4 del plan."), "pantalla pendiente con su etapa");
  await ir("#/equipos");                    // A.3 con el bridge real: árbol sobre la base de prueba (2 equipos sin ubicación)
  ok($("#contenido .arbol"), "Equipos muestra el árbol");
  const filasA3 = () => [...document.querySelectorAll("#contenido .arbol-fila")].map((f) => f.querySelector(".arbol-etiqueta").textContent);
  ok(filasA3().length === 3 && filasA3()[0] === "Sin ubicación (2)" && filasA3()[1].startsWith("CAM 1 "), "árbol real: grupo + 2 equipos " + filasA3());
  ok($("#contenido .arbol-estado").textContent === "2 equipos", "contador de equipos");
  await ir("#/zzz");
  ok($("#contenido h2").textContent === "Pantalla desconocida", "ruta desconocida");
  await ir("#/equipos/12/extra");
  ok($("#contenido h2").textContent === "Equipos", "ruta con argumentos extra");
  await ir("#/cables");
  // 4) idioma (diccionario desde Python: core + web) y persistencia
  await cambiar("#sel-idioma", "en");
  ok($("#lateral a[data-id=equipos]").textContent.includes("Equipment"), "nav en inglés");
  ok($("#contenido .pendiente").textContent.includes("Available in stage A.4 of the plan."), "pantalla pendiente en inglés (con {etapa})");
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

// ── A.3: árbol de equipos ──
const nodoEq = (i, l, h) => ({ t: "equipo", i, l, b: "CAMARA", ...(h ? { h } : {}) });
function arbolGrande(salas = 20, racks = 10, equipos = 25) {      // 20×10×25 = 5.000 equipos + conectores
  let id = 0;
  const nodos = [];
  for (let s = 0; s < salas; s++) {
    const hs = [];
    for (let r = 0; r < racks; r++) {
      const hr = [];
      for (let e = 0; e < equipos; e++) { id++; hr.push(nodoEq(id, `EQ${id} Sony HDC-${e}`, [{ t: "conector", i: id, l: "OUT 1", b: "BNC" }])); }
      hs.push({ t: "rack", i: r, l: `Rack ${s}-${r}`, b: "", h: hr });
    }
    nodos.push({ t: "sala", i: s, l: `Sala ${s}`, b: "", h: hs });
  }
  nodos.push({ t: "sin_ubicacion", i: null, l: null, b: "", n: 1, h: [nodoEq(++id, "HUERFANO Canon CÁMARA")] });
  return { nodos, n_equipos: id };
}

if (escenario === "arbol_modelo") {        // arbol.js puro, sin DOM
  const { prepararArbol, abiertosIniciales, aplanar, normalizar, tokens } = await import(pathToFileURL(path.join(WEB, "app/arbol.js")).href);
  ok(normalizar("CÁMARA Ñandú") === "camara nandu", "normalizar quita acentos y mayúsculas");
  ok(tokens("a").length === 0 && tokens(" sony  3500 ").join() === "sony,3500", "tokens: mínimo 2 caracteres, separa palabras");
  const { nodos } = arbolGrande();
  prepararArbol(nodos, (n) => `Sin ubicación (${n.n})`);
  const ultimo = nodos.at(-1);
  ok(ultimo.l === "Sin ubicación (1)" && ultimo.busqueda === "sin ubicacion (1)" && ultimo.k === "20", "prepararArbol: etiqueta de grupo, búsqueda normalizada y ruta");
  ok(nodos[0].h[0].h[0].h[0].h.length === 0 && nodos[0].h[0].h[0].k === "0.0.0", "las hojas quedan con h=[] y k único");
  const st = { abiertos: abiertosIniciales(nodos), cerrados: new Set() };
  let r = aplanar(nodos, "", st);
  ok(r.filas.length === 20 + 200 + 1 + 1, "sin filtro: 20 salas abiertas + 200 racks + grupo sin ubicación + su equipo; vino " + r.filas.length);
  ok(r.filas[0].nivel === 0 && r.filas[1].nivel === 1 && r.filas[0].abierto && !r.filas[1].abierto && r.filas[1].expandible, "niveles y estado de las filas");
  // filtro
  let t0 = performance.now();
  r = aplanar(nodos, "eq777", st);
  const ms = performance.now() - t0;
  ok(r.coincidencias === 1 && r.filas.length === 3 && r.filas.at(-1).n.l.startsWith("EQ777 "), "filtro: el equipo con sus ancestros (el conector no coincide) " + r.filas.map((f) => f.n.l).join(" | "));
  ok(r.filas[0].abierto && r.filas[1].abierto && !r.filas[2].expandible, "con filtro los ancestros se abren solos y el equipo (sin hijos visibles) queda sin flecha");
  ok(ms < 200, `filtro sobre ~7.000 nodos en ${ms.toFixed(1)} ms (<200)`);
  r = aplanar(nodos, "huerfano camara", st);       // acentos + varias palabras en otro orden
  ok(r.coincidencias === 1 && r.filas.length === 2, "filtro sin acentos y con varias palabras");
  r = aplanar(nodos, "zzzz", st); ok(r.filas.length === 0 && r.coincidencias === 0, "sin coincidencias → vacío");
  r = aplanar(nodos, "x", st); ok(r.filas.length === 222 && r.coincidencias === 0, "con 1 carácter no se filtra");
  // cerrar a mano un ancestro con filtro activo
  const sala = nodos[Math.floor(777 / 250)];
  r = aplanar(nodos, "eq777", { abiertos: st.abiertos, cerrados: new Set([sala.k]) });
  ok(r.filas.length === 1 && r.filas[0].n === sala && !r.filas[0].abierto && r.filas[0].expandible, "con filtro, un ancestro cerrado a mano oculta sus hijos");
  // coincidencia en un nodo intermedio: se ven solo los hijos que coinciden, no todos
  r = aplanar(nodos, "rack 19-9", st);
  ok(r.coincidencias === 1 && r.filas.map((f) => f.n.l).join("|") === "Sala 19|Rack 19-9", "coincide el rack: se ve el rack pero no sus equipos (no coinciden)");
}

if (escenario === "arbol_vista") {         // pantalla con rpc falso y jsdom
  instalarDom();
  const { vistaEquipos, ALTO_FILA, olvidarArbol } = await import(pathToFileURL(path.join(WEB, "app/equipos_arbol.js")).href);
  const { aplicar } = await import(pathToFileURL(path.join(WEB, "app/i18n.js")).href);
  aplicar("es", {}, { persistir: false });
  let pedidos = 0;
  const rpc = { llamar: async (fn) => { ok(fn === "arbol_equipos", "pide arbol_equipos"); pedidos++; return arbolGrande(); } };
  const pantalla = await vistaEquipos({ rpc, args: [], gen: 1 });
  document.body.append(pantalla);
  const filas = () => [...pantalla.querySelectorAll(".arbol-fila")];
  const txt = (f) => f.querySelector(".arbol-etiqueta").textContent;
  ok(/^5\D?001 equipos$/.test(pantalla.querySelector(".arbol-estado").textContent), "contador total");
  // virtualización: 222 filas lógicas, pero ~10.000 nodos en total → el DOM solo tiene la ventana
  const arbol = pantalla.querySelector(".arbol"), esp = pantalla.querySelector(".arbol-espacio");
  ok(esp.style.height === 222 * ALTO_FILA + "px", "alto del espaciador = filas × alto fijo, vino " + esp.style.height);
  ok(filas().length > 0 && filas().length < 60, "solo se dibuja la ventana: " + filas().length + " filas de 222");
  ok(txt(filas()[0]) === "Sala 0" && filas()[0].getAttribute("aria-expanded") === "true" && filas()[0].getAttribute("aria-level") === "1", "primera fila: Sala 0 abierta, nivel 1");
  // scroll: dibuja otra ventana
  arbol.scrollTop = 100 * ALTO_FILA; arbol.dispatchEvent(new window.Event("scroll")); await tick(60);
  ok(txt(filas()[0]) !== "Sala 0" && filas().length < 60, "tras el scroll cambia la ventana: " + txt(filas()[0]));
  arbol.scrollTop = 0; arbol.dispatchEvent(new window.Event("scroll")); await tick(60);
  // expandir un rack con su flecha
  const rack = filas().find((f) => txt(f) === "Rack 0-0");
  rack.querySelector("button").click(); await tick();
  ok(esp.style.height === (222 + 25) * ALTO_FILA + "px", "abrir un rack suma sus 25 equipos");
  ok(filas().find((f) => txt(f) === "Rack 0-0").getAttribute("aria-expanded") === "true", "aria-expanded sigue al estado");
  // filtro con debounce
  const entrada = pantalla.querySelector("#arbol-filtro");
  entrada.value = "eq777"; entrada.dispatchEvent(new window.Event("input")); await tick(400);
  ok(filas().map(txt).join("|") === "Sala 3|Rack 3-1|EQ777 Sony HDC-1", "filtro: sala > rack > equipo " + filas().map(txt).join("|"));
  ok(pantalla.querySelector(".arbol-estado").textContent === "1 coincidencias", "contador de coincidencias");
  ok(filas()[2].getAttribute("aria-expanded") === null, "con filtro el equipo no muestra flecha (sus conectores no coinciden)");
  entrada.value = "zzzz"; entrada.dispatchEvent(new window.Event("input")); await tick(400);
  ok(filas().length === 0 && pantalla.querySelector(".arbol-estado").textContent === "Sin resultados", "sin resultados");
  entrada.value = ""; entrada.dispatchEvent(new window.Event("input")); await tick(400);
  ok(filas().length > 0 && /equipos$/.test(pantalla.querySelector(".arbol-estado").textContent), "vaciar el filtro vuelve al árbol");
  // contraer / expandir todo
  pantalla.querySelector("#arbol-contraer").click(); await tick();
  ok(filas().length === 21 && esp.style.height === 21 * ALTO_FILA + "px", "contraer todo: solo las raíces, " + filas().length);
  pantalla.querySelector("#arbol-expandir").click(); await tick();
  ok(esp.style.height === (20 + 200 + 5000 + 5000 + 1 + 1) * ALTO_FILA + "px", "expandir todo: salas, racks, equipos, conectores, grupo y huérfano");
  // caché: misma gen no vuelve a pedir; gen nueva sí
  await vistaEquipos({ rpc, args: [], gen: 1 }); ok(pedidos === 1, "misma versión de base: sin nueva llamada al bridge");
  await vistaEquipos({ rpc, args: [], gen: 2 }); ok(pedidos === 2, "base nueva: vuelve a pedir");
  // un fallo no queda en caché
  olvidarArbol(); let fallar = true; const rpc2 = { llamar: async () => { if (fallar) throw new Error("boom"); return arbolGrande(1, 1, 1); } };
  try { await vistaEquipos({ rpc: rpc2, gen: 9 }); ok(false, "debió fallar"); } catch (e) { ok(e.message === "boom", "el error del bridge sube a la pantalla"); }
  fallar = false; const p2 = await vistaEquipos({ rpc: rpc2, gen: 9 }); ok(p2.querySelector(".arbol-estado").textContent === "2 equipos", "tras un fallo, reintentar vuelve a pedir");
  // base vacía
  olvidarArbol(); const p3 = await vistaEquipos({ rpc: { llamar: async () => ({ nodos: [], n_equipos: 0 }) }, gen: 3 });
  ok(p3.querySelector(".arbol-estado").textContent === "No hay equipos cargados", "base sin equipos");
}

console.log(`  ✔ [${escenario}] ${n} chequeos`);
process.exit(0);
