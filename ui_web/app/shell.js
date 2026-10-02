// Shell de la app (A.2): barra superior, navegación por hash (#/equipos/12), idioma, tema y errores.
// `iniciar(rpc)` recibe el cliente del worker, así se puede probar con un rpc falso.
import { h, $ } from "./dom.js";
import { t, idioma, IDIOMAS, idiomaInicial, cacheado, aplicar, alCambiar } from "./i18n.js";
import { TEMAS, ETIQUETAS, temaGuardado, aplicarTema } from "./tema.js";
import { reportar, panelError, instalarGlobales, texto } from "./errores.js";
import { NAV, ALIAS_NAV, resolverVista } from "./vistas.js";
import { estadoOffline, alCambiarOffline } from "./offline.js";

export function parseRuta(hash = location.hash) {
  const [id, ...args] = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  return { id: id || "inicio", args };
}

export async function iniciar(rpc) {
  const estado = { dbBytes: null, iniciado: false, gen: 0 };   // gen: versión de la base, para invalidar cachés de las pantallas
  let token = 0;

  instalarGlobales();
  aplicarTema(temaGuardado(), { persistir: false });
  const l0 = idiomaInicial();
  aplicar(l0, (l0 !== "es" && cacheado(l0)) || {}, { persistir: false });
  const splash = $("splash-txt"); if (splash) splash.textContent = t("Iniciando el motor (Pyodide)…");

  rpc.on("state", (d) => {
    const antes = estado.dbBytes; estado.dbBytes = d.dbBytes; estado.gen++;
    if (!estado.iniciado) return;
    const info = $("db-info"); if (info) info.textContent = textoBase();
    if (antes !== d.dbBytes) mostrarVista();       // base cargada o cambiada: repintar la pantalla actual
  });
  rpc.on("error", (err) => reportar(err, "Error del motor Python"));

  const TEXTO_OFFLINE = { preparando: "Preparando el uso sin conexión…", parcial: "Sin conexión: falta guardar el motor (se completa en la próxima visita con conexión)", listo: "Listo para usar sin conexión" };
  const textoOffline = () => { const e = estadoOffline(); return e ? t(TEXTO_OFFLINE[e]) : ""; };
  alCambiarOffline(() => { const el = $("offline-info"); if (el) el.textContent = textoOffline(); });
  const textoBase = () => (estado.dbBytes ? t("Base cargada ({kb} KB)", { kb: Math.round(estado.dbBytes / 1024) }) : "");

  function marcarActivo() {
    const { id: ruta } = parseRuta(), id = ALIAS_NAV[ruta] || ruta;
    document.querySelectorAll("#lateral a[data-id]").forEach((a) =>
      id === a.dataset.id ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    document.body.dataset.ruta = ruta;               // la caja de la barra se oculta en Búsqueda (la pantalla ya tiene la suya)
  }

  async function cambiarIdioma(l) {
    try {
      if (l === "es") return aplicar("es", {});
      aplicar(l, (await rpc.diccionario(l)).textos);
    } catch (err) { reportar(err, "Error del motor Python"); }
  }

  function montarShell() {
    const selIdioma = h("select", { id: "sel-idioma", onchange: (e) => cambiarIdioma(e.target.value) },
      Object.entries(IDIOMAS).map(([c, n]) => h("option", { value: c, selected: c === idioma() }, n)));
    const selTema = h("select", { id: "sel-tema", onchange: (e) => aplicarTema(e.target.value) },
      TEMAS.map((c) => h("option", { value: c, selected: c === temaGuardado() }, t(ETIQUETAS[c]))));
    const menu = h("button", { id: "btn-menu", type: "button", "aria-label": t("Menú"), "aria-expanded": "false", "aria-controls": "lateral",
      onclick: () => { const ab = document.body.classList.toggle("menu-abierto"); menu.setAttribute("aria-expanded", String(ab)); } }, "☰");
    // Búsqueda global (A.9): Enter lleva a #/busqueda/<texto>; la tecla "/" enfoca la caja desde cualquier pantalla.
    const caja = h("input", { type: "search", id: "barra-busqueda", autocomplete: "off", placeholder: t("Buscar equipos, conectores, cables, racks…"), "aria-label": t("Búsqueda") });
    const buscar = h("form", { id: "barra-buscar", role: "search", onsubmit: (e) => {
      e.preventDefault();
      const q = caja.value.trim(); caja.value = "";
      window.location.hash = q ? "#/busqueda/" + encodeURIComponent(q) : "#/busqueda";
    } }, caja);
    const app = h("div", { id: "app" },
      h("a", { class: "saltar", href: "#contenido" }, t("Saltar al contenido")),
      h("header", { id: "barra" }, menu, h("h1", {}, "CableDoc"), buscar,
        h("label", {}, t("Idioma"), selIdioma), h("label", {}, t("Tema"), selTema)),
      h("nav", { id: "lateral", "aria-label": t("Menú") },
        NAV.map((n) => h("a", { href: "#/" + n.id, "data-id": n.id }, h("span", { "aria-hidden": "true" }, n.icono), t(n.clave))),
        h("div", { class: "sep" }),
        h("div", { class: "aparte", id: "db-info" }, textoBase()),
        h("div", { class: "aparte", id: "offline-info", role: "status" }, textoOffline()),
        h("a", { href: "index.html", class: "aparte" }, "🛠 " + t("Diagnóstico técnico"))),
      h("main", { id: "contenido", tabindex: "-1" }));
    const previo = $("app") || $("splash"); previo ? previo.replaceWith(app) : document.body.prepend(app);
    marcarActivo();
  }

  async function mostrarVista() {
    const miToken = ++token, { id, args } = parseRuta(), main = $("contenido");
    if (!main) return;
    main.replaceChildren(h("p", { class: "sub" }, t("Cargando…")));
    try {
      const nodo = await resolverVista(estado.dbBytes ? id : "cargar_db", { rpc, args, gen: estado.gen });
      if (miToken === token) main.replaceChildren(nodo);
    } catch (err) {
      if (miToken !== token) return;
      reportar(err, "Error al mostrar la pantalla", { toast: false });
      main.replaceChildren(panelError(err, mostrarVista));
    }
  }

  document.addEventListener("keydown", (e) => {     // "/" → buscar (salvo que ya se esté escribiendo en un campo)
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || !estado.iniciado) return;
    const el = e.target, tag = el?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
    const campo = $("busqueda-texto") || $("barra-busqueda");
    if (campo) { e.preventDefault(); campo.focus(); }
  });

  alCambiar(() => { if (estado.iniciado) { montarShell(); mostrarVista(); } });
  window.addEventListener("hashchange", () => {
    document.body.classList.remove("menu-abierto");
    marcarActivo(); mostrarVista();
    const m = $("contenido"); if (m) m.focus({ preventScroll: true });
  });

  try { await rpc.listo; }
  catch (err) {
    if (splash) splash.replaceChildren(h("div", {}, t("No se pudo cargar el motor. Revisá la red o corré ui_web/fetch_pyodide.py."), h("pre", {}, texto(err))));
    return;
  }
  if (idioma() !== "es") {                          // reemplaza el diccionario cacheado por el vigente
    try { aplicar(idioma(), (await rpc.diccionario(idioma())).textos); } catch (err) { reportar(err, "Error del motor Python"); }
  }
  estado.iniciado = true;
  montarShell(); mostrarVista();
}
