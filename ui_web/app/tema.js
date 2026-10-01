// Tema: "auto" (sigue al sistema), "claro" u "oscuro". Se guarda en localStorage y se aplica con data-theme en <html>.
const KEY = "cabledoc.tema";
export const TEMAS = ["auto", "claro", "oscuro"];
export const ETIQUETAS = { auto: "Automático", claro: "Claro", oscuro: "Oscuro" };
export function temaGuardado() {
  try { const v = localStorage.getItem(KEY); return TEMAS.includes(v) ? v : "auto"; } catch { return "auto"; }
}
export function aplicarTema(tema, { persistir = true } = {}) {
  if (!TEMAS.includes(tema)) tema = "auto";
  const r = document.documentElement;
  if (tema === "auto") r.removeAttribute("data-theme");
  else r.setAttribute("data-theme", tema === "claro" ? "light" : "dark");
  if (persistir) { try { localStorage.setItem(KEY, tema); } catch { /* sin storage */ } }
  return tema;
}
