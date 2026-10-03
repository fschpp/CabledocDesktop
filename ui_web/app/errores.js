// Manejo de errores: toasts no bloqueantes, panel de error para pantallas y captura global.
import { h, $ } from "./dom.js";
import { t } from "./i18n.js";

export class ErrorBridge extends Error {          // el bridge respondió {ok:false}; `campos` = {campo: motivo} si fue un error de validación (B.2)
  constructor(fn, mensaje, campos = null) { super(mensaje); this.name = "ErrorBridge"; this.fn = fn; this.campos = campos; }
}
const registro = [];                               // últimos errores (para soporte / diagnóstico)
export const ultimosErrores = () => registro.slice();

export function texto(err) { return err && err.message ? err.message : String(err); }

export function reportar(err, contexto, { toast = true } = {}) {
  registro.push({ ts: new Date().toISOString(), contexto: contexto || null, error: texto(err), stack: err && err.stack || null });
  if (registro.length > 50) registro.shift();
  console.error(contexto || "error", err);
  const cont = $("toasts"); if (!toast || !cont) return;
  const el = h("div", { class: "toast", role: "alert" },
    h("span", {}, (contexto ? t(contexto) + ": " : "") + texto(err)),
    h("button", { type: "button", "aria-label": t("Cerrar"), onclick: () => el.remove() }, "✕"));
  cont.append(el);
  setTimeout(() => el.remove(), 12000);
}

// Panel para mostrar dentro de #contenido cuando una pantalla falla (con detalle técnico y reintento).
export function panelError(err, reintentar, contexto = "Error al mostrar la pantalla") {
  return h("section", { class: "error-panel", role: "alert" },
    h("h2", {}, t("Algo salió mal")),
    h("p", {}, t(contexto)),
    h("details", {}, h("summary", {}, t("Detalle técnico")), h("pre", {}, texto(err) + (err && err.stack ? "\n\n" + err.stack : ""))),
    reintentar ? h("p", {}, h("button", { type: "button", class: "primario", onclick: reintentar }, t("Reintentar"))) : null);
}

export function instalarGlobales() {
  window.addEventListener("error", (e) => reportar(e.error || e.message, "Algo salió mal"));
  window.addEventListener("unhandledrejection", (e) => reportar(e.reason, "Algo salió mal"));
}
