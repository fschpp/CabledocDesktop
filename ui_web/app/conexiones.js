// Conexiones (A.5): árbol de conexiones de un equipo (carga perezosa, como ArbolConexionesEquipo del desktop)
// y cadena completa de extensiones de un cable (como CadenaExtensionDialog).
// Rutas: #/conexiones (elegir equipo) · #/conexiones/<id_equipo> (árbol) · #/cadena/<id_cable> (cadena).
// Datos del bridge: equipos_lista, conexiones_equipo (un nivel por llamada) y cadena_extension.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { normalizar } from "./arbol.js";

const num = (v) => (/^\d+$/.test(v ?? "") ? Number(v) : null);
const MAX_RESULTADOS = 50;

// ── Elegir equipo raíz ───────────────────────────────────────────────────────
async function elegirEquipo({ rpc }) {
  const equipos = (await rpc.llamar("equipos_lista")).map((e) => ({
    e, busqueda: normalizar([e.nombre, e.marca, e.modelo, e.tipo].filter(Boolean).join(" ")),
  }));
  const lista = h("ul", { class: "elegir-equipo" }), estado = h("p", { class: "sub", "aria-live": "polite" });
  let pend = 0;
  function pintar() {
    const toks = normalizar(entrada.value).trim().split(/\s+/).filter(Boolean);
    const ok = toks.length ? equipos.filter((x) => toks.every((k) => x.busqueda.includes(k))) : equipos;
    lista.replaceChildren(...ok.slice(0, MAX_RESULTADOS).map(({ e }) => h("li", {},
      h("a", { href: "#/conexiones/" + e.id_equipo }, e.nombre || "#" + e.id_equipo),
      " ", h("span", { class: "sub" }, [e.tipo, [e.marca, e.modelo].filter(Boolean).join(" ")].filter(Boolean).join(" · ")))));
    estado.textContent = !equipos.length ? t("No hay equipos cargados") : !ok.length ? t("Sin resultados")
      : ok.length > MAX_RESULTADOS ? t("Mostrando {a} de {b}", { a: MAX_RESULTADOS, b: ok.length.toLocaleString() }) : t("{n} equipos", { n: ok.length.toLocaleString() });
  }
  const entrada = h("input", { type: "search", class: "arbol-filtro", autocomplete: "off", placeholder: t("Buscar equipo…"), "aria-label": t("Buscar equipo…"),
    oninput: () => { clearTimeout(pend); pend = setTimeout(pintar, 200); } });
  pintar();
  return h("section", { class: "ficha" }, h("h2", {}, t("Árbol de conexiones")),
    h("p", { class: "sub" }, t("Elegí un equipo para ver a qué otros equipos está conectado.")),
    h("div", { class: "arbol-barra" }, entrada), estado, lista);
}

// ── Árbol de conexiones ──────────────────────────────────────────────────────
// Equipo → 🔗 cable → equipo del otro extremo → … Cada equipo se desarrolla una sola vez en todo el árbol
// (igual que el desktop: es lo que corta los ciclos); si aparece de nuevo se marca "ya desarrollado" y queda como hoja.
async function arbolEquipo({ rpc, id }) {
  const desarrollados = new Set(), cache = new Map();
  const estado = h("p", { class: "sub", "aria-live": "polite" });
  function cargar(idEq) {                              // un nivel por equipo; un fallo no queda en la caché ("reintentar" vuelve a pedir)
    if (!cache.has(idEq)) {
      const p = rpc.llamar("conexiones_equipo", { id_equipo: idEq });
      cache.set(idEq, p); p.catch(() => cache.delete(idEq));
    }
    return cache.get(idEq);
  }

  // Nodo plegable genérico: li > fila (flecha + contenido) + ul de hijos. `alAbrir` rellena los hijos la primera vez.
  function nodo({ clase, contenido, expandible, alAbrir, abierto = false }) {
    const hijos = h("ul", { class: "cx-hijos", role: "group" });
    const flecha = h("button", { type: "button", class: "arbol-flecha", "aria-label": t("Expandir") }, "▸");
    const li = h("li", { class: "cx-nodo " + clase, role: "treeitem", "aria-expanded": expandible ? "false" : null },
      h("div", { class: "cx-fila" }, expandible ? flecha : h("span", { class: "arbol-flecha vacio", "aria-hidden": "true" }), contenido), hijos);
    let cargado = false, ocupado = false;
    async function poner(abrir) {
      if (!expandible || ocupado) return;
      if (abrir && !cargado) {
        ocupado = true;
        try { await alAbrir(hijos, li, flecha); cargado = true; } finally { ocupado = false; }
      }
      if (li.classList.contains("hoja")) return;       // resultó no tener hijos: no es plegable
      li.setAttribute("aria-expanded", String(abrir));
      li.classList.toggle("abierto", abrir);
      flecha.textContent = abrir ? "▾" : "▸";
      flecha.setAttribute("aria-label", t(abrir ? "Contraer" : "Expandir"));
    }
    flecha.addEventListener("click", () => poner(li.getAttribute("aria-expanded") !== "true"));
    li.poner = poner; li.cargado = () => cargado;
    if (abierto) poner(true);
    return li;
  }

  const etiquetaEquipo = (idEq, nombre, extra) => [
    h("span", { "aria-hidden": "true" }, "🖥 "),
    idEq == null ? h("span", { class: "arbol-etiqueta" }, nombre || t("Sin equipo")) : h("a", { class: "arbol-etiqueta", href: "#/equipos/" + idEq, title: nombre }, nombre || "#" + idEq),
    extra || null];

  function nodoEquipo(idEq, nombre, { raiz = false } = {}) {
    if (idEq == null) return nodo({ clase: "equipo hoja sin-equipo", contenido: etiquetaEquipo(null, nombre), expandible: false });
    if (!raiz && desarrollados.has(idEq)) {
      return nodo({ clase: "equipo hoja repetido", contenido: etiquetaEquipo(idEq, nombre, h("span", { class: "etiqueta" }, t("ya desarrollado"))), expandible: false });
    }
    const n = nodo({
      clase: "equipo" + (raiz ? " raiz" : ""), contenido: etiquetaEquipo(idEq, nombre), expandible: true, abierto: raiz,
      async alAbrir(hijos, li, flecha) {
        desarrollados.add(idEq);
        estado.textContent = t("Cargando conexiones…");
        let d;
        try { d = await cargar(idEq); } catch (err) { desarrollados.delete(idEq); estado.textContent = ""; throw err; }
        if (!d.cables.length) {                       // sin más conexiones: hoja atenuada, igual que el desktop
          li.classList.add("hoja", "sin-conexiones"); flecha.replaceWith(h("span", { class: "arbol-flecha vacio", "aria-hidden": "true" }));
          li.removeAttribute("aria-expanded");
          estado.textContent = raiz ? t("El equipo no tiene conexiones registradas.") : t("«{e}» no tiene más conexiones", { e: d.equipo });
          return;
        }
        for (const k of d.cables) hijos.append(nodoCable(k));
        estado.textContent = t("«{e}» — {n} conexiones", { e: d.equipo, n: d.n_conexiones });
      },
    });
    return n;
  }

  function nodoCable(k) {
    const local = k.conexiones.map((c) => c.conector_local).filter(Boolean)[0];
    return nodo({
      clase: "cable", expandible: true, abierto: true,
      contenido: [h("span", { "aria-hidden": "true" }, "🔗 "),
        h("a", { class: "arbol-etiqueta", href: "#/cables/" + k.id_cable }, k.codigo), local ? h("span", { class: "sub" }, " › " + local) : null,
        h("a", { class: "cx-cadena", href: "#/cadena/" + k.id_cable, title: t("Ver cadena completa"), "aria-label": t("Ver cadena completa") }, "⛓")],
      alAbrir(hijos) {
        for (const c of k.conexiones) hijos.append(nodoEquipo(c.id_equipo_destino, c.equipo_destino));
      },
    });
  }

  const raiz = await cargar(id);                      // falla acá (id inexistente) → panel de error del shell, no un árbol vacío
  const arbol = h("ul", { class: "cx-arbol", role: "tree", "aria-label": t("Árbol de conexiones") });
  // Como en el desktop, "Expandir todo" abre lo ya cargado; no dispara cargas nuevas (recorrería toda la red de conexiones).
  const todos = (abrir) => arbol.querySelectorAll("li.cx-nodo[aria-expanded]").forEach((li) => {
    if (abrir !== (li.getAttribute("aria-expanded") === "true") && (!abrir || li.cargado())) li.poner(abrir);
  });
  arbol.append(nodoEquipo(id, raiz.equipo, { raiz: true }));
  return h("section", { class: "ficha cx-pantalla" },
    h("p", { class: "volver" }, h("a", { href: "#/conexiones" }, "← " + t("Cambiar equipo"))),
    h("h2", {}, t("Árbol de conexiones")),
    h("p", { class: "sub" }, t("Expandí un equipo para cargar sus conexiones.")),
    h("div", { class: "arbol-barra" },
      h("button", { type: "button", id: "cx-expandir", title: t("Abre los nodos ya cargados"), onclick: () => todos(true) }, t("Expandir todo")),
      h("button", { type: "button", id: "cx-contraer", onclick: () => todos(false) }, t("Contraer todo"))),
    estado, arbol);
}

export function vistaConexiones(ctx) {
  const id = num(ctx.args?.[0]);
  if (ctx.args?.length && id == null) return desconocida(ctx.args[0]);
  return id == null ? elegirEquipo(ctx) : arbolEquipo({ rpc: ctx.rpc, id });
}

function desconocida(id) {
  return h("section", { class: "pendiente" }, h("h2", {}, t("Pantalla desconocida")), h("p", { class: "sub" }, String(id ?? "")));
}

// ── Cadena completa de extensiones ───────────────────────────────────────────
const ARMADO = { 1: ["✓ ", "correcto", ""], 0: ["⚠ ", "MAL ARMADO", "mal"] };

function lineaCadena(x) {
  switch (x.tipo) {
    case "equipo":
      return h("li", { class: "cd-equipo" },
        x.id_equipo != null ? h("a", { href: "#/equipos/" + x.id_equipo }, h("b", {}, x.equipo)) : h("b", {}, x.equipo || ""),
        " — ", x.id_conector != null ? h("a", { href: "#/conectores/" + x.id_conector }, x.conector || "#" + x.id_conector) : (x.conector || ""));
    case "cable":
      return h("li", { class: "cd-cable" + (x.foco ? " foco" : "") }, "│ " + t("cable") + " ",
        h("a", { href: "#/cables/" + x.id_cable }, h("i", {}, x.codigo || "#" + x.id_cable)),
        x.foco ? h("span", { class: "cd-foco", title: t("Cable desde el que abriste esta vista") }, " 👈") : null);
    case "extension": {
      const [pre, txt, clase] = ARMADO[x.armado] || ["", "no verificado", ""];
      return h("li", { class: "cd-extension" }, h("b", {}, `🔗 ${t("Extensión")} #${x.id_extension}`),
        ` (${x.posicion || t("sin posición registrada")}) — `, h("span", { class: clase }, pre + t(txt)));
    }
    case "suelto":
      return h("li", { class: "cd-aviso mal" }, "⚠ " + t("extremo suelto — la cadena termina acá, sin llegar a un equipo"));
    case "ciclo":
      return h("li", { class: "cd-aviso mal" }, "⚠ " + t("referencia circular detectada — revisar extensiones"));
    default:
      return h("li", {}, String(x.tipo));
  }
}

export async function vistaCadena({ rpc, args }) {
  const id = num(args?.[0]);
  if (id == null) return desconocida(args?.[0]);
  const eslabones = await rpc.llamar("cadena_extension", { id_cable: id });
  return h("section", { class: "ficha cadena" },
    h("p", { class: "volver" }, h("a", { href: "#/cables/" + id }, "← " + t("Volver al cable"))),
    h("h2", {}, "🔗 " + t("Cadena completa")),
    eslabones.length
      ? [h("p", { class: "sub" }, t("Recorrido real de extremo a extremo, siguiendo cada extensión. El cable marcado con 👈 es desde donde abriste esta vista.")),
        h("ol", { class: "cd-lista" }, eslabones.map(lineaCadena))]
      : h("p", { class: "sub" }, t("Este cable no tiene conexiones cargadas todavía.")));
}
