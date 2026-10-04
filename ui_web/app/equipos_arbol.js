// Pantalla "Equipos" (A.3; desde A.4 las filas de equipo y conector enlazan a su ficha; desde B.4 con «Nuevo equipo» y «Alta rápida»): árbol Sala → Rack → Frame → Equipo → Conectores con filtro y lista virtualizada.
// Los datos se piden UNA vez al bridge (arbol_equipos) y se guardan en memoria; el filtro y el expandir/contraer
// trabajan sobre esa copia (ver arbol.js). Solo se crean en el DOM las filas que entran en la ventana de scroll.
import { h } from "./dom.js";
import { t, idioma } from "./i18n.js";
import { prepararArbol, abiertosIniciales, aplanar, tokens } from "./arbol.js";
import { reportar } from "./errores.js";
import { altaEquipo, altaRapidaEquipo } from "./equipos_abm.js";       // B.4 (equipos_abm importa olvidarArbol de acá: ciclo sin efecto al cargar, solo se usa al ejecutar)

export const ALTO_FILA = 30;          // px, fijo: permite calcular qué filas se ven sin medir el DOM
const SOBRE = 8;                      // filas extra arriba/abajo para que el scroll rápido no muestre huecos
const DEBOUNCE_MS = 250;

// Un solo árbol en memoria por carga de base: `gen` lo incrementa el shell cada vez que el worker avisa un cambio de base.
let cache = null;                     // { gen, promesa }
// El idioma también invalida: las etiquetas de los grupos (y por lo tanto su texto de búsqueda) salen traducidas.
function datos(rpc, gen) {
  const clave = gen + "|" + idioma();
  if (!cache || cache.gen !== clave) {
    const promesa = rpc.llamar("arbol_equipos").then((d) => ({
      n_equipos: d.n_equipos,
      nodos: prepararArbol(d.nodos, (n) => (n.t === "sueltos" ? t("Equipos sueltos") : t("Sin ubicación")) + ` (${n.n})`),
    }));
    cache = { gen: clave, promesa };
    promesa.catch(() => { if (cache && cache.promesa === promesa) cache = null; });   // un fallo no queda pegado: "Reintentar" vuelve a pedir
  }
  return cache.promesa;
}
export const olvidarArbol = () => { cache = null; };
const seguro = (f) => async () => { try { await f(); } catch (err) { reportar(err, "No se pudo completar la acción"); } };   // B.4: una acción que falla se informa con un aviso

const BADGE_FIJO = new Set(["sala", "rack", "frame"]);
const textoBadge = (n) => (BADGE_FIJO.has(n.t) ? t(n.t) : n.t === "equipo" ? n.b || t("equipo") : n.t === "conector" ? n.b : "");

export async function vistaEquipos({ rpc, gen = 0 }) {
  const { nodos, n_equipos } = await datos(rpc, gen);
  const estado = { abiertos: abiertosIniciales(nodos), cerrados: new Set(), texto: "" };
  let filas = [], coincidencias = 0, pendiente = 0;

  const estadoTxt = h("p", { class: "sub arbol-estado", "aria-live": "polite" });
  const entrada = h("input", { type: "search", id: "arbol-filtro", class: "arbol-filtro", autocomplete: "off", placeholder: t("Buscar equipo, rack, frame…"),
    "aria-label": t("Buscar equipo, rack, frame…"), oninput: () => { clearTimeout(pendiente); pendiente = setTimeout(filtrar, DEBOUNCE_MS); } });
  const espaciador = h("div", { class: "arbol-espacio" });
  const ventana = h("div", { class: "arbol-ventana" });
  espaciador.append(ventana);
  const cont = h("div", { class: "arbol", role: "tree", "aria-label": t("Equipos"), tabindex: "0" }, espaciador);

  function recalcular() {
    ({ filas, coincidencias } = aplanar(nodos, estado.texto, estado));
    espaciador.style.height = filas.length * ALTO_FILA + "px";
    const filtra = tokens(estado.texto).length > 0;
    estadoTxt.textContent = !n_equipos ? t("No hay equipos cargados")
      : !filtra ? t("{n} equipos", { n: n_equipos.toLocaleString() })
      : coincidencias ? t("{n} coincidencias", { n: coincidencias.toLocaleString() }) : t("Sin resultados");
    dibujar();
  }

  function alternar(fila) {
    const filtra = tokens(estado.texto).length > 0, k = fila.n.k;
    const set = filtra ? estado.cerrados : estado.abiertos;
    // con filtro "abierto" es lo normal: el set guarda las excepciones (cerrados); sin filtro guarda los abiertos
    if (filtra ? fila.abierto : !fila.abierto) set.add(k); else set.delete(k);
    recalcular();
  }

  function dibujar() {
    const alto = cont.clientHeight || 600;          // jsdom/pantalla oculta: sin layout, usar una ventana razonable
    const desde = Math.max(0, Math.floor(cont.scrollTop / ALTO_FILA) - SOBRE);
    const hasta = Math.min(filas.length, Math.ceil((cont.scrollTop + alto) / ALTO_FILA) + SOBRE);
    ventana.style.transform = `translateY(${desde * ALTO_FILA}px)`;
    ventana.replaceChildren(...filas.slice(desde, hasta).map((f) => {
      const n = f.n, badge = textoBadge(n);
      return h("div", { class: `arbol-fila tipo-${n.t}`, role: "treeitem", "aria-level": f.nivel + 1,
          "aria-expanded": f.expandible ? String(f.abierto) : null, style: `height:${ALTO_FILA}px;padding-left:${0.4 + f.nivel * 1.2}rem`, "data-k": n.k },
        f.expandible
          ? h("button", { type: "button", class: "arbol-flecha", "aria-label": t(f.abierto ? "Contraer" : "Expandir"), onclick: () => alternar(f) }, f.abierto ? "▾" : "▸")
          : h("span", { class: "arbol-flecha vacio", "aria-hidden": "true" }),
        n.t === "equipo" || n.t === "conector"
          ? h("a", { class: "arbol-etiqueta", title: n.l, href: `#/${n.t === "equipo" ? "equipos" : "conectores"}/${n.i}` }, n.l)
          : h("span", { class: "arbol-etiqueta", title: n.l }, n.l),
        badge ? h("span", { class: "arbol-badge" }, badge) : null);
    }));
  }

  let marco = 0;
  cont.addEventListener("scroll", () => { if (!marco) marco = requestAnimationFrame(() => { marco = 0; dibujar(); }); });

  function filtrar() {
    estado.texto = entrada.value; estado.cerrados.clear();
    cont.scrollTop = 0;
    recalcular();
  }
  const todos = (f) => { const rec = (n) => { if (n.h.length) { f(n.k); n.h.forEach(rec); } }; nodos.forEach(rec); };
  const expandir = () => { estado.cerrados.clear(); todos((k) => estado.abiertos.add(k)); recalcular(); };
  const contraer = () => { estado.abiertos.clear(); todos((k) => estado.cerrados.add(k)); recalcular(); };

  recalcular();
  return h("section", { class: "arbol-pantalla" },
    h("h2", {}, t("Equipos")),
    h("p", { class: "acciones abm" },
      h("button", { type: "button", class: "primario", "data-accion": "nuevo", onclick: seguro(() => altaEquipo(rpc)) }, "+ " + t("Nuevo equipo")), " ",
      h("button", { type: "button", "data-accion": "alta-rapida", onclick: seguro(() => altaRapidaEquipo(rpc)) }, "⚡ " + t("Alta rápida"))),
    h("div", { class: "arbol-barra" }, entrada,
      h("button", { type: "button", id: "arbol-expandir", onclick: expandir }, t("Expandir todo")),
      h("button", { type: "button", id: "arbol-contraer", onclick: contraer }, t("Contraer todo"))),
    estadoTxt, cont);
}
