// i18n del shell. El diccionario sale de Python (ui_web/i18n_web.py: core/i18n.py + cadenas web).
// Las claves son el texto en español; "es" no necesita diccionario. Si falta una clave se muestra tal cual.
export const IDIOMAS = { es: "Español", en: "English", pt: "Português" };
const KEY = "cabledoc.lang", CACHE = "cabledoc.i18n.";
let lang = "es", textos = {};
const oyentes = [];

export const idioma = () => lang;
export function t(clave, vars) {
  let s = textos[clave] ?? clave;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return s;
}
export const alCambiar = (f) => oyentes.push(f);

export function idiomaInicial() {
  try { const g = localStorage.getItem(KEY); if (g in IDIOMAS) return g; } catch { /* sin storage: sigue */ }
  const n = (globalThis.navigator?.language || "es").slice(0, 2);
  return n in IDIOMAS ? n : "es";
}
// Último diccionario visto, para que la pantalla de carga ya salga traducida antes de que arranque Pyodide.
export function cacheado(l) {
  try { return JSON.parse(localStorage.getItem(CACHE + l)); } catch { return null; }
}
export function aplicar(l, tx, { persistir = true } = {}) {
  if (!(l in IDIOMAS)) throw new Error("Idioma no soportado: " + l);
  lang = l; textos = tx || {};
  document.documentElement.lang = l;
  if (persistir) {
    try { localStorage.setItem(KEY, l); if (l !== "es") localStorage.setItem(CACHE + l, JSON.stringify(textos)); } catch { /* cuota/privado */ }
  }
  oyentes.forEach((f) => f());
}
