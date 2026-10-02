// Pantallas del shell. Cada vista es (ctx) → Node | Promise<Node>, con ctx = { rpc, args, gen } (gen cambia cada vez que se carga/cambia la base).
// "Inicio", "Equipos" (A.3), fichas (A.4), "Conexiones" (A.5), "Ubicaciones" (A.6), "Análisis" (A.7), "Escenarios" (A.8), "Búsqueda" (A.9), "Datos" (A.10) y la carga de base son reales. `pendiente` queda para marcar etapas futuras (NAV.etapa != null).
import { h } from "./dom.js";
import { t, idioma } from "./i18n.js";
import { vistaEquipos } from "./equipos_arbol.js";
import { fichaEquipo, fichaConector, listaCables } from "./fichas.js";
import { vistaConexiones, vistaCadena } from "./conexiones.js";
import { vistaUbicaciones, vistaRack, vistaFrame } from "./ubicaciones.js";
import { vistaPatcheras } from "./patcheras.js";
import { vistaAnalisis } from "./analisis.js";
import { vistaEscenarios } from "./escenarios.js";
import { vistaBusqueda } from "./busqueda.js";
import { vistaDatos } from "./datos.js";

// Navegación: `etapa` es la tarea del plan que la implementa (null = ya disponible).
export const NAV = [
  { id: "inicio",      clave: "Inicio",      icono: "🏠", etapa: null },
  { id: "equipos",     clave: "Equipos",     icono: "🖥️", etapa: null },
  { id: "cables",      clave: "Cables",      icono: "🔌", etapa: null },
  { id: "conexiones",  clave: "Conexiones",  icono: "🔗", etapa: null },
  { id: "ubicaciones", clave: "Ubicaciones", icono: "🗄️", etapa: null },
  { id: "analisis",    clave: "Análisis",    icono: "📈", etapa: null },
  { id: "escenarios",  clave: "Escenarios",  icono: "🧪", etapa: null },
  { id: "busqueda",    clave: "Búsqueda",    icono: "🔍", etapa: null },
  { id: "datos",       clave: "Datos",       icono: "💾", etapa: null },
];

// Rutas sin ítem propio en el menú resaltan el de su familia.
export const ALIAS_NAV = { conectores: "equipos", cadena: "conexiones", racks: "ubicaciones", frames: "ubicaciones", patcheras: "ubicaciones" };

const TARJETAS = [["equipo", "Equipos"], ["conector", "Conectores"], ["cable", "Cables"], ["conexion", "Conexiones"],
  ["sala", "Salas"], ["rack", "Racks"], ["frame", "Frames"]];

async function inicio({ rpc }) {
  const r = await rpc.llamar("resumen");
  const fmt = (n) => Number(n ?? 0).toLocaleString(idioma());
  return h("section", {},
    h("h2", {}, t("Resumen de la instalación")),
    h("div", { class: "tarjetas" }, TARJETAS.map(([k, et]) =>
      h("div", { class: "tarjeta" },
        h("div", { class: "n" }, fmt(r[k])),
        h("div", { class: "et" }, t(et)),
        k === "cable" ? h("div", { class: "sub" }, t("Cables externos") + ": " + fmt(r.cables_externos)) : null))));
}

// Sin db.db en el navegador todas las rutas muestran esta pantalla (el worker avisa con "state" al cargarla).
function cargarDb({ rpc }) {
  const estado = h("p", { class: "sub", "aria-live": "polite" });
  const entrada = h("input", { type: "file", accept: ".db,.sqlite,.sqlite3", onchange: async (e) => {
    const f = e.target.files[0]; if (!f) return;
    entrada.disabled = true; estado.textContent = t("Cargando…");
    try { rpc.cargarDb(await f.arrayBuffer()); }
    catch (err) { entrada.disabled = false; estado.textContent = ""; throw err; }
  } });
  return h("section", { class: "vacio" },
    h("h2", {}, t("Falta la base de datos")),
    h("p", {}, t("Cargá el archivo db.db para empezar. Queda guardado en este navegador.")),
    h("p", {}, entrada), estado);
}

const pendiente = (item) => () => h("section", { class: "pendiente" },
  h("h2", {}, t(item.clave)),
  h("p", { class: "sub" }, t("Disponible en la etapa {etapa} del plan.", { etapa: item.etapa })));

// #/equipos → árbol; #/equipos/<id> → ficha. #/cables → lista; #/cables/<id> → ficha. #/conectores/<id> → ficha (sin entrada propia en el menú).
// #/conexiones → elegir equipo; #/conexiones/<id> → árbol de conexiones; #/cadena/<id_cable> → cadena de extensiones (resalta Conexiones).
// #/ubicaciones → salas, racks y frames; #/racks/<id> → vista de rack; #/frames/<id> → frame con sus slots; #/patcheras → vista global (resaltan Ubicaciones).
export const VISTAS = { inicio, equipos: (ctx) => (ctx.args?.length ? fichaEquipo(ctx) : vistaEquipos(ctx)), cables: listaCables, conectores: fichaConector, conexiones: vistaConexiones, cadena: vistaCadena, ubicaciones: vistaUbicaciones, racks: vistaRack, frames: vistaFrame, patcheras: vistaPatcheras, ...Object.fromEntries(NAV.filter((n) => n.etapa).map((n) => [n.id, pendiente(n)])) };

VISTAS.analisis = vistaAnalisis;       // A.7: #/analisis/impacto|riesgo|diagnostico|topologia
VISTAS.escenarios = vistaEscenarios;   // A.8: #/escenarios (lista) y #/escenarios/<id> (cambios + evaluación)
VISTAS.datos = vistaDatos;             // A.10: #/datos (respaldo del .db y catálogos)
VISTAS.busqueda = vistaBusqueda;       // A.9: #/busqueda, #/busqueda/<texto> y #/busqueda/<texto>/<tipo>

export function resolverVista(id, ctx) {
  const f = id === "cargar_db" ? cargarDb : VISTAS[id];
  if (!f) return h("section", { class: "pendiente" }, h("h2", {}, t("Pantalla desconocida")), h("p", { class: "sub" }, id));
  return f(ctx);
}
