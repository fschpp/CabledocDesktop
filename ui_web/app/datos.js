// Datos (A.10): respaldo del .db completo y catálogos de equipos/frames (.zip con un .json, el formato del desktop).
// Todo ocurre en este navegador: nada se envía a ningún servidor. Importar un .db REEMPLAZA la base actual.
import { h } from "./dom.js";
import { t } from "./i18n.js";

let aviso = null;                                   // último resultado: sobrevive al repintado que dispara el cambio de base
const hoy = () => new Date().toISOString().slice(0, 10).replaceAll("-", "");

export function descargar(data, nombre, tipo = "application/octet-stream") {
  const url = URL.createObjectURL(new Blob([data], { type: tipo }));
  const a = h("a", { href: url, download: nombre }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function vistaDatos({ rpc }) {
  const msg = h("p", { class: "sub", role: "status", "aria-live": "polite" });
  const mostrar = (txt, error = false) => { aviso = { txt, error }; msg.textContent = txt; msg.classList.toggle("error", error); };
  if (aviso) mostrar(aviso.txt, aviso.error);
  const motivo = (r) => t(r.error, r);               // el bridge devuelve la clave i18n en `error`, con sus parámetros
  const correr = (botones, f) => async (e) => {      // deshabilita mientras corre y muestra cualquier fallo como mensaje
    botones.forEach((b) => (b.disabled = true)); mostrar(t("Trabajando…"));
    try { await f(e); } catch (err) { mostrar(err.message || String(err), true); }
    finally { botones.forEach((b) => (b.disabled = false)); }
  };
  const archivo = (accept, f) => { const i = h("input", { type: "file", accept }); i.onchange = correr([i], async () => { const a = i.files[0]; i.value = ""; if (a) await f(a); }); return i; };

  const bExp = h("button", { type: "button", class: "primario" }, t("Exportar la base (.db)"));
  bExp.onclick = correr([bExp], async () => {
    const r = await rpc.exportarDb(); if (!r.ok) return mostrar(motivo(r), true);
    descargar(r.data, `cabledoc_${hoy()}.db`); mostrar(t("Base exportada ({kb} KB).", { kb: Math.round(r.data.length / 1024) }));
  });
  const iDb = archivo(".db,.sqlite,.sqlite3", async (a) => {
    if (!confirm(t("Esto reemplaza la base actual de este navegador por «{nombre}». Exportá la actual antes si la necesitás. ¿Seguir?", { nombre: a.name }))) return mostrar("");
    const r = await rpc.importarDb(await a.arrayBuffer());
    mostrar(r.ok ? t("Base importada: {equipos} equipos, {conectores} conectores, {cables} cables.", r) : motivo(r), !r.ok);
  });

  const cat = (tipo, et) => {
    const b = h("button", { type: "button" }, t(et));
    b.onclick = correr([b], async () => {
      const r = await rpc.exportarCatalogo(tipo); if (!r.ok) return mostrar(motivo(r), true);
      descargar(r.data, r.nombre, "application/zip"); mostrar(t("Catálogo exportado: {moldes} molde(s).", r));
    });
    return b;
  };
  const iCat = archivo(".zip,.json", async (a) => {
    if (!confirm(t("Importar «{nombre}» agrega moldes a la base de este navegador. ¿Seguir?", { nombre: a.name }))) return mostrar("");
    const r = await rpc.importarCatalogo(await a.arrayBuffer());
    if (!r.ok) return mostrar(motivo(r), true);
    mostrar(t("Importados {moldes} molde(s) con {hijos} conector(es) o slot(s).", r) + (r.conflictos ? " " + t("{conflictos} conflicto(s) de rol o dirección: se conservó el valor local.", r) : ""));
  });

  return h("section", { class: "datos-vista" },
    h("h2", {}, t("Datos")),
    msg,
    h("h3", {}, t("Base completa")),
    h("p", { class: "sub" }, t("El respaldo es el archivo .db: sirve para llevar la instalación a otra computadora o volver a cargarla acá. Las imágenes no viajan con él.")),
    h("p", {}, bExp), h("p", {}, h("label", {}, t("Importar una base (.db)"), " ", iDb)),
    h("h3", {}, t("Catálogos")),
    h("p", { class: "sub" }, t("Formato del escritorio: un .zip con un .json. Las imágenes del catálogo no viajan: se guardan aparte en este navegador.")),
    h("p", {}, cat("equipos", "Exportar catálogo de equipos"), " ", cat("frames", "Exportar catálogo de frames")),
    h("p", {}, h("label", {}, t("Importar un catálogo (.zip o .json)"), " ", iCat)));
}
