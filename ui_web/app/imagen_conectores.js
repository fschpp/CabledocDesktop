// Imagen de un equipo con sus conectores superpuestos (A.4). Las coordenadas de la base son % (0-100) del ancho/alto de
// la imagen (ver Modelo: "coordenada_x_en_imagen ahora guarda 0-100"), así que no hace falta medir la imagen: el marcador
// va en left:x% / top:y% de un contenedor que mide lo mismo que la imagen.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { urlImagen, guardarArchivos, alCambiarImagenes, tipoAlmacen } from "./imagenes.js";

const dentro = (m) => Number.isFinite(m.x) && Number.isFinite(m.y) && m.x >= 0 && m.x <= 100 && m.y >= 0 && m.y <= 100;

// Selector para subir data/imagen (y data/picon) al navegador. Se guardan localmente (OPFS), no se envían a ningún lado.
export function cargadorImagenes() {
  const estado = h("span", { class: "sub", "aria-live": "polite" });
  const subir = async (e) => {
    const files = [...e.target.files]; e.target.value = ""; if (!files.length) return;
    estado.textContent = t("Subiendo {a} de {b}…", { a: 0, b: files.length });
    try {
      const r = await guardarArchivos(files, (a, b) => { estado.textContent = t("Subiendo {a} de {b}…", { a, b }); });
      estado.textContent = t("{n} imágenes guardadas", { n: r.guardadas }) + (r.ignoradas ? " · " + t("{n} ignoradas (no son imágenes)", { n: r.ignoradas }) : "")
        + (r.errores.length ? " · " + r.errores.length + " " + t("con error") + ": " + r.errores[0] : "");
    } catch (err) { estado.textContent = String(err?.message || err); }
  };
  return h("div", { class: "cargador-img" },
    h("label", { class: "boton" }, t("Elegir carpeta"), h("input", { type: "file", webkitdirectory: true, multiple: true, hidden: true, "data-carpeta": "1", onchange: subir })),
    h("label", { class: "boton" }, t("Elegir archivos"), h("input", { type: "file", accept: "image/*", multiple: true, hidden: true, "data-archivos": "1", onchange: subir })),
    estado,
    h("p", { class: "sub" }, t("Se guardan en este navegador; no se envían a ningún servidor.") + (tipoAlmacen() === "memoria" ? " " + t("(Este navegador no permite guardarlas de forma permanente: se pierden al recargar.)") : "")));
}

// opts: { path, marcadores: [{ id, nombre, x, y, n }], resaltar?: id }. Devuelve un <figure>.
export function imagenConConectores({ path, marcadores = [], resaltar = null }) {
  const lienzo = h("div", { class: "img-lienzo" });
  const fuera = marcadores.filter((m) => Number.isFinite(m.x) && Number.isFinite(m.y) && !dentro(m));
  const fig = h("figure", { class: "img-conectores" }, lienzo,
    h("figcaption", { class: "sub" }, path),
    fuera.length ? h("p", { class: "sub" }, t("Conectores fuera de la imagen") + ": " + fuera.map((m) => m.nombre).join(", ")) : null);

  async function cargar() {
    lienzo.replaceChildren(h("p", { class: "sub" }, t("Cargando imagen…")));
    let url = null;
    try { url = await urlImagen(path); } catch (e) { lienzo.replaceChildren(h("p", { class: "mal" }, String(e?.message || e))); return; }
    if (!url) { lienzo.replaceChildren(h("div", { class: "img-falta" }, h("p", {}, t("Imagen no cargada en este navegador") + ": " + path), cargadorImagenes())); return; }
    const img = h("img", { src: url, alt: path, draggable: "false" });
    const caja = h("div", { class: "img-caja" }, img, marcadores.filter(dentro).map((m) =>
      h("a", { class: "marcador" + (m.id === resaltar ? " actual" : ""), href: "#/conectores/" + m.id, "data-conector": m.id, title: m.nombre,
          style: `left:${m.x}%;top:${m.y}%`, onmouseenter: () => resaltarFila(fig, m.id, true), onmouseleave: () => resaltarFila(fig, m.id, false) }, m.n ?? "")));
    lienzo.replaceChildren(caja);
  }
  const off = alCambiarImagenes(() => { if (!fig.isConnected) return off(); cargar(); });
  cargar();
  return fig;
}

// Resalta la fila de la tabla (en la misma ficha) del conector bajo el cursor.
function resaltarFila(fig, id, on) {
  const raiz = fig.closest(".ficha"); if (!raiz) return;
  raiz.querySelectorAll(`tr[data-conector="${id}"]`).forEach((tr) => tr.classList.toggle("resaltada", on));
}
