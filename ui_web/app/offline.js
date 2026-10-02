// Uso sin conexión (A.11): registra el service worker (sw.js) y expone el estado para mostrarlo en el menú.
//   ""           → no disponible (navegador sin service workers, contexto no seguro, o falló el registro): no se muestra nada
//   "preparando" → registrado, todavía guardando archivos
//   "parcial"    → la app está guardada pero falta el motor (Pyodide): se completa con la próxima visita con conexión
//   "listo"      → todo guardado: se puede abrir sin conexión
let estado = "";
const oyentes = [];
export const estadoOffline = () => estado;
export const alCambiarOffline = (f) => { oyentes.push(f); };
export function fijarEstadoOffline(e) { if (e !== estado) { estado = e; oyentes.forEach((f) => f(e)); } }
const desde = (d) => (d.app && d.pyodide ? "listo" : d.app ? "parcial" : "preparando");

// `nav` y `seguro` se inyectan solo en los tests.
export async function registrarOffline(nav = globalThis.navigator, seguro = globalThis.isSecureContext) {
  if (!nav?.serviceWorker || !seguro) return null;
  try {
    nav.serviceWorker.addEventListener("message", (e) => { if (e.data?.tipo === "estado") fijarEstadoOffline(desde(e.data)); });
    const reg = await nav.serviceWorker.register("sw.js");
    fijarEstadoOffline("preparando");
    const activo = (await nav.serviceWorker.ready).active || reg.active;   // espera a que termine de instalarse
    activo?.postMessage({ tipo: "estado" });
    return reg;
  } catch (err) { console.warn("Sin modo offline:", err); return null; }
}
