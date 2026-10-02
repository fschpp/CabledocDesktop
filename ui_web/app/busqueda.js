// Búsqueda global (A.9): una caja que busca a la vez en equipos, conectores, cables, salas, racks y frames.
// Rutas: #/busqueda · #/busqueda/<texto> · #/busqueda/<texto>/<tipo> (la ruta se actualiza al tipear, sin recargar la pantalla).
// Datos: bridge.busqueda_indice(), una sola vez por carga de base; el filtro corre en memoria (ver busqueda_modelo.js).
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { TIPOS, prepararIndice, buscar, rutaDe } from "./busqueda_modelo.js";

const DEBOUNCE_MS = 200;
export const MAX_POR_GRUPO = 25;       // en "Todos": cuántas filas por tipo antes de ofrecer "Ver todos"
export const MAX_FILAS = 300;          // en un solo tipo: tope de filas dibujadas

const ICONOS = { sala: "🏢", rack: "🗄️", frame: "▦", equipo: "🖥️", conector: "⏺", cable: "🔌" };
const SINGULAR = { sala: "Sala", rack: "Rack", frame: "Frame", equipo: "Equipo", conector: "Conector", cable: "Cable" };
const PLURAL = { sala: "Salas", rack: "Racks", frame: "Frames", equipo: "Equipos", conector: "Conectores", cable: "Cables" };

// Un solo índice en memoria por carga de base (`gen` lo incrementa el shell con cada evento "state" del worker).
let cache = null;                       // { gen, promesa }
function datos(rpc, gen) {
  if (!cache || cache.gen !== gen) {
    const promesa = rpc.llamar("busqueda_indice").then((d) => prepararIndice(d.items));
    cache = { gen, promesa };
    promesa.catch(() => { if (cache && cache.promesa === promesa) cache = null; });   // un fallo no queda pegado: "Reintentar" vuelve a pedir
  }
  return cache.promesa;
}
export const olvidarIndice = () => { cache = null; };

function fila(it) {
  return h("li", { class: "resultado tipo-" + it.t, "data-tipo": it.t, "data-id": it.i },
    h("span", { class: "resultado-tipo", title: t(SINGULAR[it.t]) }, h("span", { "aria-hidden": "true" }, ICONOS[it.t]), " ", t(SINGULAR[it.t])),
    h("div", { class: "resultado-cuerpo" },
      h("a", { href: rutaDe(it) }, it.l),
      it.int ? h("span", { class: "etiqueta" }, t("interna")) : null,
      it.d.length ? h("div", { class: "sub" }, it.d.join(" · ")) : null));
}

// ctx = { rpc, args, gen }; args = [] | [texto] | [texto, tipo]
export async function vistaBusqueda({ rpc, args = [], gen = 0 }) {
  const items = await datos(rpc, gen);
  const estado = { texto: args[0] ?? "", tipo: TIPOS.includes(args[1]) ? args[1] : "todos" };
  let pendiente = 0;

  const entrada = h("input", { type: "search", id: "busqueda-texto", class: "arbol-filtro", autocomplete: "off", value: estado.texto,
    placeholder: t("Buscar equipos, conectores, cables, racks…"), "aria-label": t("Buscar equipos, conectores, cables, racks…"),
    oninput: () => { clearTimeout(pendiente); pendiente = setTimeout(() => { estado.texto = entrada.value; dibujar(); }, DEBOUNCE_MS); } });
  const chips = h("div", { class: "busqueda-chips", role: "group", "aria-label": t("Tipo de resultado") });
  const resumen = h("p", { class: "sub", "aria-live": "polite", id: "busqueda-estado" });
  const salida = h("div", { class: "busqueda-resultados" });

  // La ruta refleja la búsqueda (se puede copiar el enlace) sin disparar hashchange: no se vuelve a pintar la pantalla.
  function guardarRuta() {
    const q = estado.texto.trim();
    const hash = q ? "#/busqueda/" + encodeURIComponent(q) + (estado.tipo !== "todos" ? "/" + estado.tipo : "") : "#/busqueda";
    try { if (window.location.hash !== hash) window.history.replaceState(null, "", hash); } catch { /* sin history: no es grave */ }
  }

  function dibujar() {
    const r = buscar(items, estado.texto);
    if (r.filtra && estado.tipo !== "todos" && !r.conteo[estado.tipo] && r.conteo.todos) estado.tipo = "todos";   // el tipo elegido quedó vacío: mostrar todo
    guardarRuta();

    chips.replaceChildren(...(r.filtra ? ["todos", ...TIPOS] : []).filter((k) => k === "todos" || r.conteo[k] > 0 || k === estado.tipo).map((k) =>
      h("button", { type: "button", class: "chip", "data-tipo": k, "aria-pressed": String(estado.tipo === k),
        onclick: () => { estado.tipo = k; dibujar(); } },
        (k === "todos" ? t("Todos") : t(PLURAL[k])) + " (" + r.conteo[k].toLocaleString() + ")")));

    if (!r.filtra) {
      resumen.textContent = t("Escribí al menos 2 caracteres para buscar.");
      salida.replaceChildren();
      return;
    }
    resumen.textContent = r.conteo.todos ? t("{n} coincidencias", { n: r.conteo.todos.toLocaleString() }) : t("Sin resultados");

    const tipos = estado.tipo === "todos" ? TIPOS : [estado.tipo], uno = estado.tipo !== "todos";
    const bloques = tipos.filter((k) => r.grupos[k].length).map((k) => {
      const lista = r.grupos[k], tope = uno ? MAX_FILAS : MAX_POR_GRUPO;
      return h("section", { class: "busqueda-grupo", "data-tipo": k },
        h("h3", {}, t(PLURAL[k]), " ", h("span", { class: "sub" }, "(" + lista.length.toLocaleString() + ")")),
        h("ul", { class: "resultados" }, lista.slice(0, tope).map(fila)),
        lista.length > tope
          ? (uno ? h("p", { class: "sub" }, t("Se muestran las primeras {n} coincidencias; afiná la búsqueda para ver el resto.", { n: tope }))
                 : h("button", { type: "button", class: "ver-todos", onclick: () => { estado.tipo = k; dibujar(); } }, t("Ver todos ({n})", { n: lista.length.toLocaleString() })))
          : null);
    });
    salida.replaceChildren(...bloques);
  }

  dibujar();
  return h("section", { class: "ficha busqueda" },
    h("h2", {}, t("Búsqueda")),
    h("p", { class: "sub" }, t("Busca en equipos, conectores, cables, salas, racks y frames. Todas las palabras deben aparecer, en cualquier orden y sin distinguir mayúsculas ni acentos (por ejemplo «sony 3500» o «cam 1 out»).")),
    h("div", { class: "arbol-barra" }, entrada), chips, resumen, salida);
}
