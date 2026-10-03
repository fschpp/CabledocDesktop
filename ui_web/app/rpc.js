// Cliente del Web Worker (Pyodide). Una sola instancia por pestaña.
//   llamar(fn, args)  → data del bridge, o lanza ErrorBridge (con .campos si es de validación) si el bridge devolvió {ok:false}
//   diccionario(lang) → {lang, idiomas, textos}  (no necesita db.db)
//   cargarDb(buf)     → el worker responde con un mensaje "state"
//   exportarDb() / importarDb(buf) / exportarCatalogo(tipo) / importarCatalogo(buf)  (A.10) → {ok, ..., data?: Uint8Array}
import { ErrorBridge } from "./errores.js";

export function crearRpc(url = "worker.js") {
  const w = new Worker(url, { type: "module" });
  let rid = 0, listoRes, listoRej;
  const pend = new Map(), oyentes = {};
  const listo = new Promise((res, rej) => { listoRes = res; listoRej = rej; });
  listo.catch(() => {});                           // el que espera "listo" maneja el error; evita un rechazo huérfano
  const emitir = (tipo, d) => (oyentes[tipo] || []).forEach((f) => f(d));
  const rechazarTodo = (err) => { for (const p of pend.values()) p.rej(err); pend.clear(); };
  const resolver = (d, f) => { const p = pend.get(d.id); if (!p) return; pend.delete(d.id); try { f(p); } catch (e) { p.rej(e); } };

  w.onmessage = (e) => {
    const d = e.data;
    if (d.type === "ready") listoRes(d);
    else if (d.type === "fatal") { const err = new Error(d.msg); listoRej(err); rechazarTodo(err); }
    else if (d.type === "call" || d.type === "i18n") resolver(d, (p) => p.res(JSON.parse(d.result)));
    else if (d.type === "datos") resolver(d, (p) => p.res({ ...JSON.parse(d.result), data: d.data }));
    else if (d.type === "fail") resolver(d, (p) => p.rej(new Error(d.error)));
    emitir(d.type, d);
  };
  w.onerror = (e) => { const err = new Error(e.message || "No se pudo cargar worker.js"); listoRej(err); emitir("error", err); };

  const pedir = (cmd, extra, transfer = []) => new Promise((res, rej) => { const id = ++rid; pend.set(id, { res, rej }); w.postMessage({ cmd, id, ...extra }, transfer); });
  return {
    listo,
    on(tipo, f) { (oyentes[tipo] ||= []).push(f); },
    async llamar(fn, args = {}) {
      const r = await pedir("call", { fn, args });
      if (!r.ok) throw new ErrorBridge(fn, r.error, r.campos || null);
      return r.data;
    },
    diccionario: (lang) => pedir("i18n", { lang }),
    exportarDb: () => pedir("datos_exportar_db"),
    importarDb: (buf) => pedir("datos_importar_db", { buf }, [buf]),
    exportarCatalogo: (tipo) => pedir("datos_catalogo_exportar", { tipo }),
    importarCatalogo: (buf) => pedir("datos_catalogo_importar", { buf }, [buf]),
    cargarDb(buf) { w.postMessage({ cmd: "load_db", buf }, [buf]); },
  };
}
