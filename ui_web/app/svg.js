// Helpers de SVG compartidos por las vistas de ubicación (A.6): rack, frame/slots y patcheras.
// Todo texto entra como nodo de texto (nunca innerHTML): los nombres vienen de la base.
import { h } from "./dom.js";
import { t } from "./i18n.js";

const NS = "http://www.w3.org/2000/svg";

// Crea un elemento SVG. Igual que h(): atributos null/false se omiten, hijos anidados se aplanan.
export function s(tag, attrs, ...hijos) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null && v !== false) el.setAttribute(k, v === true ? "" : String(v));
  for (const c of hijos.flat(Infinity)) { if (c == null || c === false) continue; el.append(c.nodeType ? c : document.createTextNode(String(c))); }
  return el;
}

// SVG no mide texto sin layout: se recorta por cantidad de caracteres (ancho medio ≈ 0,58 × tamaño de letra).
export function abreviar(texto, anchoPx, fontPx) {
  const txt = String(texto ?? ""), max = Math.max(1, Math.floor(anchoPx / (fontPx * 0.58)));
  return txt.length <= max ? txt : max <= 1 ? "…" : txt.slice(0, max - 1) + "…";
}

// Paleta del desktop (PALETA de pantallas_comunes.py), en hex.
export const PALETA = ["#D82626", "#26B726", "#2D6BE5", "#EA8C0A", "#A526D1", "#0AC6C6", "#C6BF0A", "#E54CA5", "#4CB760", "#8C4C14",
  "#19844C", "#D1197F", "#4799E5", "#BF8C38", "#7F1919", "#2D47B7", "#19A58C", "#B260D1", "#4C7F2D", "#E52D60"];
export const colorPaleta = (i) => PALETA[Number(i) % PALETA.length];

// Enlace dentro de un SVG (href SVG2; los navegadores actuales lo aceptan sin xlink).
export const enlaceSvg = (href, ...hijos) => s("a", { href }, ...hijos);

// Controles de zoom (− / valor / + / 100 %). `alCambiar(z)` vuelve a dibujar; devuelve { barra, zoom() }.
export const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];
export function controlesZoom(alCambiar, inicial = 1) {
  let z = inicial;
  const valor = h("span", { class: "zoom-valor", "aria-live": "polite" }, Math.round(z * 100) + " %");
  const ir = (nz) => { z = nz; valor.textContent = Math.round(z * 100) + " %"; alCambiar(z); };
  const paso = (d) => { const i = ZOOMS.findIndex((x) => x >= z - 1e-9); const j = Math.min(ZOOMS.length - 1, Math.max(0, (i < 0 ? ZOOMS.length - 1 : i) + d)); if (ZOOMS[j] !== z) ir(ZOOMS[j]); };
  const barra = h("div", { class: "zoom-barra", role: "group", "aria-label": t("Zoom") },
    h("button", { type: "button", class: "boton", "data-zoom": "menos", "aria-label": t("Alejar"), onclick: () => paso(-1) }, "−"), valor,
    h("button", { type: "button", class: "boton", "data-zoom": "mas", "aria-label": t("Acercar"), onclick: () => paso(1) }, "+"),
    h("button", { type: "button", class: "boton", "data-zoom": "reset", onclick: () => ir(1) }, "100 %"));
  return { barra, zoom: () => z };
}
