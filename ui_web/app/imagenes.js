// Imágenes en el navegador (A.4, camino 2 del plan: D4 "imágenes y picon en OPFS desde JS, servidas por blob URL bajo demanda").
// Las imágenes NO pasan por Pyodide ni por la base: el usuario sube la carpeta data/imagen (y data/picon) y se guardan en OPFS
// (Origin Private File System) con la misma ruta relativa que `imagen.path_archivo`. Para mostrarlas se lee el archivo
// y se crea un blob URL (cacheado). Si OPFS no existe (navegador viejo, pestaña privada, tests) se usa un almacén en memoria.
const RAIZ = "cabledoc-img";
const MIME = { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp", svg: "image/svg+xml", bmp: "image/bmp" };
export const EXT_IMAGEN = Object.keys(MIME);

// Normaliza una ruta de la base ("sub\\foo.PNG", "./foo.png") a segmentos seguros; null si sale de la carpeta o está vacía.
export function segmentos(ruta) {
  const seg = String(ruta ?? "").replace(/\\/g, "/").split("/").filter((s) => s && s !== ".");
  return seg.length && !seg.includes("..") ? seg : null;
}
const clave = (kind, ruta) => { const s = segmentos(ruta); return s ? kind + "/" + s.join("/") : null; };

// ── Almacenes: misma interfaz { guardar(clave, blob), leer(clave) → Blob|null, contar(), vaciar() } ──
export function almacenMemoria() {
  const m = new Map();
  return {
    nombre: "memoria",
    async guardar(k, blob) { m.set(k, blob); },
    async leer(k) { return m.get(k) ?? null; },
    async contar() { return m.size; },
    async vaciar() { m.clear(); },
  };
}

export function almacenOpfs(nav = globalThis.navigator) {
  if (!nav?.storage?.getDirectory) return null;
  const dir = async (partes, crear) => {
    let d = await nav.storage.getDirectory();
    for (const p of [RAIZ, ...partes]) d = await d.getDirectoryHandle(p, { create: crear });
    return d;
  };
  const partir = (k) => { const s = k.split("/"); return [s.slice(0, -1), s.at(-1)]; };
  const contarDir = async (d) => { let n = 0; for await (const [, h] of d.entries()) n += h.kind === "file" ? 1 : await contarDir(h); return n; };
  return {
    nombre: "opfs",
    async guardar(k, blob) {
      const [d, f] = partir(k);
      const fh = await (await dir(d, true)).getFileHandle(f, { create: true });
      const w = await fh.createWritable(); await w.write(blob); await w.close();
    },
    async leer(k) {
      try { const [d, f] = partir(k); return await (await (await dir(d, false)).getFileHandle(f)).getFile(); }
      catch (e) { if (e?.name === "NotFoundError" || e?.name === "TypeMismatchError") return null; throw e; }
    },
    async contar() { try { return await contarDir(await dir([], false)); } catch (e) { if (e?.name === "NotFoundError") return 0; throw e; } },
    async vaciar() { try { await (await nav.storage.getDirectory()).removeEntry(RAIZ, { recursive: true }); } catch (e) { if (e?.name !== "NotFoundError") throw e; } },
  };
}

let almacen = null, crearUrl = (b) => URL.createObjectURL(b), revocar = (u) => URL.revokeObjectURL(u);
const urls = new Map();                         // clave → blob URL (o null si no está)
const oyentes = [];
export const alCambiarImagenes = (f) => { oyentes.push(f); return () => { const i = oyentes.indexOf(f); if (i >= 0) oyentes.splice(i, 1); }; };   // devuelve la baja
export const tipoAlmacen = () => (almacen ??= almacenOpfs() ?? almacenMemoria()).nombre;
// Solo para tests: inyecta el almacén y la fábrica de URLs.
export function configurar({ almacen: a, crearUrl: c, revocar: r } = {}) {
  if (a) almacen = a; if (c) crearUrl = c; if (r) revocar = r;
  urls.clear();
}

// Dado un archivo elegido, decide en qué carpeta y con qué ruta guardarlo.
//   - si vino de una carpeta (webkitRelativePath = "imagen/sub/a.png" o "data/imagen/a.png" o "a.png"):
//     se reconoce el segmento "imagen" o "picon" y lo de adelante es la ruta; sin ese segmento = imagen suelta (kind "imagen").
export function destino(rel) {
  const seg = segmentos(rel); if (!seg) return null;
  const i = seg.findIndex((s) => s.toLowerCase() === "imagen" || s.toLowerCase() === "picon");
  const kind = i >= 0 ? seg[i].toLowerCase() : "imagen";
  const resto = i >= 0 ? seg.slice(i + 1) : (seg.length > 1 ? seg.slice(-1) : seg);   // sin carpeta reconocible: solo el nombre
  if (!resto.length) return null;
  const ext = resto.at(-1).split(".").pop().toLowerCase();
  return EXT_IMAGEN.includes(ext) ? { kind, ruta: resto.join("/") } : null;
}

// Guarda una lista de File. Devuelve { guardadas, ignoradas, errores }. `alAvanzar(hechas, total)` para el indicador.
export async function guardarArchivos(files, alAvanzar = () => {}) {
  const a = (almacen ??= almacenOpfs() ?? almacenMemoria());
  const lista = [...files]; let guardadas = 0, ignoradas = 0; const errores = [];
  for (let n = 0; n < lista.length; n++) {
    const f = lista[n], d = destino(f.webkitRelativePath || f.name);
    if (!d) ignoradas++;
    else {
      try {
        const k = clave(d.kind, d.ruta);
        await a.guardar(k, f);
        const previa = urls.get(k); if (previa) revocar(previa);
        urls.delete(k); guardadas++;
      } catch (e) { errores.push(`${f.name}: ${e?.message || e}`); }
    }
    alAvanzar(n + 1, lista.length);
    if (n % 20 === 19) await new Promise((r) => setTimeout(r, 0));   // cede el hilo para que se pinte el avance
  }
  if (guardadas) oyentes.forEach((f) => f());
  return { guardadas, ignoradas, errores };
}

// Blob URL de una imagen guardada, o null si no está cargada. kind: "imagen" | "picon".
export async function urlImagen(ruta, kind = "imagen") {
  const k = clave(kind, ruta); if (!k) return null;
  if (urls.has(k) && urls.get(k)) return urls.get(k);
  const a = (almacen ??= almacenOpfs() ?? almacenMemoria());
  const blob = await a.leer(k); if (!blob) return null;
  const tipo = MIME[k.split(".").pop().toLowerCase()];
  const u = crearUrl(tipo && blob.type !== tipo ? new Blob([blob], { type: tipo }) : blob);
  urls.set(k, u); return u;
}
export const cantidadGuardadas = async () => (almacen ??= almacenOpfs() ?? almacenMemoria()).contar();
export async function vaciarImagenes() { await (almacen ??= almacenOpfs() ?? almacenMemoria()).vaciar(); urls.forEach((u) => u && revocar(u)); urls.clear(); oyentes.forEach((f) => f()); }
