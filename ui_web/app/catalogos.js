// Catálogos básicos (B.2): #/catalogos (marcas) y #/catalogos/<ruta> — marcas, tipos de equipo/conector/cable/ficha,
// señales, formatos de señal e imágenes. Primer ABM real: alta, edición y baja con los diálogos de B.1.
//   · Alta/edición: abrirFormulario con los campos que arma catalogos_modelo.js a partir del esquema del bridge.
//   · Baja: antes de confirmar se muestra a cuántos registros afecta (la mayoría quedan sin valor; algunos se borran con él).
//   · Deshacer: alta → baja del registro (solo si sigue sin uso); edición → los valores anteriores; baja → reinserta el registro
//     con su id, y SOLO si no estaba en uso (lo que lo usaba ya no se puede reconstruir, así que ahí no se ofrece).
// Cada escritura la persiste el worker (syncfs) antes de contestar. La lista se recarga desde el bridge después de cada cambio.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { reportar, ErrorBridge } from "./errores.js";
import { abrirFormulario, confirmar, ofrecerDeshacer, crearPilaDeshacer, ErrorFormulario } from "./formulario.js";
import { CATALOGOS, RUTA_INICIAL, porRuta, TITULO_COLUMNA, camposFormulario, textoCelda, etiquetaFila, filtrarFilas, detalleUsos } from "./catalogos_modelo.js";

const pila = crearPilaDeshacer(10);
const filtros = {};                                   // texto del filtro por catálogo: sobrevive al repintado que dispara un cambio de base

export async function vistaCatalogos({ rpc, args }) {
  const def = porRuta(args?.[0] || RUTA_INICIAL);
  if (!def) return h("section", { class: "pendiente" }, h("h2", {}, t("Catálogos")), h("p", { class: "sub" }, t("Catálogo desconocido") + ": " + args[0]));
  let datos = await rpc.llamar("catalogo_lista", { catalogo: def.cat });
  let resaltar = null;

  // El bridge devuelve los errores de validación como ErrorBridge con `campos`; el formulario espera ErrorFormulario.
  const llamarForm = async (fn, a) => {
    try { return await rpc.llamar(fn, a); }
    catch (e) { if (e instanceof ErrorBridge && e.campos && Object.keys(e.campos).length) throw new ErrorFormulario(e.message, e.campos); throw e; }
  };
  const sing = () => t(def.singular);
  const estado = h("p", { class: "sub", role: "status", "aria-live": "polite" });
  const decir = (txt) => { estado.textContent = txt; };

  async function recargar() { datos = await rpc.llamar("catalogo_lista", { catalogo: def.cat }); pintar(); }
  const seguro = (f) => async (...a) => { try { await f(...a); } catch (err) { reportar(err, "No se pudo completar la acción"); } };

  async function alta() {
    const r = await abrirFormulario({
      titulo: t("Alta de {x}", { x: sing() }), campos: camposFormulario(datos.esquema, t),
      enviar: (valores) => llamarForm("catalogo_alta", { catalogo: def.cat, valores }),
    });
    if (!r) return;
    const { id, fila } = r.resultado, nombre = etiquetaFila(def, fila);
    const aviso = t("Se agregó «{nombre}»", { nombre });
    resaltar = id; await recargar(); decir(aviso);
    ofrecerDeshacer(pila, aviso, async () => {
      await rpc.llamar("catalogo_baja", { catalogo: def.cat, id, solo_si_sin_uso: true }); await recargar();
    });
  }

  async function editar(fila) {
    const r = await abrirFormulario({
      titulo: t("Editar {x}", { x: sing() }), campos: camposFormulario(datos.esquema, t, fila), valores: fila,
      enviar: (valores) => llamarForm("catalogo_modificar", { catalogo: def.cat, id: fila.id, valores }),
    });
    if (!r) return;
    const { id, anterior, fila: nueva } = r.resultado, nombre = etiquetaFila(def, nueva);
    const aviso = t("Se modificó «{nombre}»", { nombre });
    resaltar = id; await recargar(); decir(aviso);
    ofrecerDeshacer(pila, aviso, async () => {
      await rpc.llamar("catalogo_modificar", { catalogo: def.cat, id, valores: anterior }); resaltar = id; await recargar();
    });
  }

  async function eliminar(fila) {
    const nombre = etiquetaFila(def, fila), usos = detalleUsos(fila.usos, t);
    const cuerpo = h("div", {},
      h("p", {}, t("¿Eliminar «{nombre}»?", { nombre })),
      usos.length
        ? [h("p", {}, t("Está en uso. Al eliminarlo:")),
           h("ul", { class: "catalogos-usos" }, usos.map((u) => h("li", {}, `${u.n} ${u.tabla} — ` + (u.efecto === "borra" ? t("también se eliminarán") : t("quedarán sin este valor")))))]
        : h("p", { class: "sub" }, t("No está en uso.")));
    if (!(await confirmar({ titulo: t("Eliminar {x}", { x: sing() }), mensaje: cuerpo, textoOk: "Eliminar", peligro: true }))) return;
    const r = await rpc.llamar("catalogo_baja", { catalogo: def.cat, id: fila.id });
    const aviso = t("Se eliminó «{nombre}»", { nombre });
    resaltar = null; await recargar(); decir(aviso);
    if (!r.usos.length) {                                // sin uso: se puede reinsertar tal cual; con uso, lo anulado no vuelve
      ofrecerDeshacer(pila, aviso, async () => {
        await rpc.llamar("catalogo_restaurar", { catalogo: def.cat, id: r.id, valores: r.anterior }); resaltar = r.id; await recargar();
      });
    }
  }

  // ── Dibujo ──
  const cont = h("div", { class: "tabla-scroll" });
  const cuenta = h("span", { class: "sub", "aria-live": "polite" });
  const caja = h("input", { type: "search", autocomplete: "off", "aria-label": t("Filtrar"), placeholder: t("Filtrar") + "…", value: filtros[def.cat] || "",
    oninput: () => { filtros[def.cat] = caja.value; pintar(); } });

  function pintar() {
    const filas = filtrarFilas(datos.filas, caja.value, def);
    cuenta.textContent = caja.value.trim().length >= 2 ? t("{n} de {total}", { n: filas.length, total: datos.filas.length }) : t("{total} registro(s)", { total: datos.filas.length });
    if (!filas.length) { cont.replaceChildren(h("p", { class: "sub" }, datos.filas.length ? t("Ningún registro coincide con el filtro.") : t("Todavía no hay registros."))); return; }
    const filaTabla = (f) => {
      const tr = h("tr", { class: f.id === resaltar ? "resaltada" : null, "data-id": f.id },
        h("td", { class: "n" }, f.id),
        def.columnas.map((c) => h("td", {}, textoCelda(c, f[c], t))),
        h("td", { class: "n", title: f.usos.length ? detalleUsos(f.usos, t).map((u) => `${u.n} ${u.tabla}`).join(", ") : null }, f.n_usos || ""),
        h("td", { class: "acciones" },
          h("button", { type: "button", "data-accion": "editar", "aria-label": t("Editar {x}", { x: etiquetaFila(def, f) }), onclick: seguro(() => editar(f)) }, t("Editar")), " ",
          h("button", { type: "button", class: "peligro", "data-accion": "eliminar", "aria-label": t("Eliminar {x}", { x: etiquetaFila(def, f) }), onclick: seguro(() => eliminar(f)) }, t("Eliminar"))));
      return tr;
    };
    cont.replaceChildren(h("table", { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", {}, t("ID")), def.columnas.map((c) => h("th", {}, t(TITULO_COLUMNA[c] || c))), h("th", {}, t("En uso")), h("th", {}, ""))),
      h("tbody", {}, filas.map(filaTabla))));
    const marcada = cont.querySelector("tr.resaltada");
    if (marcada && typeof marcada.scrollIntoView === "function") marcada.scrollIntoView({ block: "nearest" });
    resaltar = null;
  }

  const nav = h("nav", { class: "catalogos-nav", "aria-label": t("Catálogos") },
    CATALOGOS.map((c) => h("a", { href: "#/catalogos/" + c.ruta, "aria-current": c.ruta === def.ruta ? "page" : null }, t(c.titulo))));
  const nodo = h("section", { class: "ficha catalogos-vista" },
    h("h2", {}, t("Catálogos")), nav,
    h("h3", {}, t(def.titulo)),
    h("div", { class: "catalogos-barra" }, caja, h("button", { type: "button", class: "primario", onclick: seguro(alta) }, "+ " + t("Alta de {x}", { x: sing() })), cuenta),
    estado, cont);
  pintar();
  return nodo;
}
