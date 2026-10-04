// Fichas (A.4): equipo, conector y cable, más la lista de cables que lleva a sus fichas. Son de lectura salvo cable y conexiones (B.3: alta, edición,
// baja y fusión de cables; alta, edición y baja de conexiones — ver cables_abm.js) y equipo y conector (B.4: edición y baja de ambos, alta de
// conectores desde la ficha del equipo — ver equipos_abm.js).
// Cada vista es (ctx) → Node con ctx = { rpc, args, gen }; los datos salen del bridge (equipo_ficha, conector_ficha, cable_ficha, cables_lista).
import { h } from "./dom.js";
import { t, idioma } from "./i18n.js";
import { imagenConConectores } from "./imagen_conectores.js";
import { normalizar } from "./arbol.js";
import { reportar } from "./errores.js";
import { altaCable, cableTemporal, editarCable, eliminarCable, fusionarCables, altaConexion, editarConexion, eliminarConexion } from "./cables_abm.js";
import { alternarSeleccion } from "./cables_modelo.js";
import { editarEquipo, eliminarEquipo, altaConector, editarConector, eliminarConector, extremoDesconectado } from "./equipos_abm.js";

const vacio = (v) => v == null || v === "" || (typeof v === "number" && Number.isNaN(v));
const ruta = (tipo, id) => `#/${tipo}/${encodeURIComponent(id)}`;
export const enlace = (tipo, id, texto) => (id == null ? String(texto ?? "") : h("a", { href: ruta(tipo, id) }, texto || "#" + id));
const num = (v) => Number(v).toLocaleString(idioma(), { maximumFractionDigits: 2 });

// Acción de escritura (B.3): si falla se informa con un aviso en vez de dejar una promesa rechazada.
const seguro = (f) => async (...a) => { try { await f(...a); } catch (err) { reportar(err, "No se pudo completar la acción"); } };
const boton = (texto, accion, onclick, clase = null, etiquetaAria = null) =>
  h("button", { type: "button", class: clase, "data-accion": accion, "aria-label": etiquetaAria, onclick: seguro(onclick) }, texto);

// Argumento de ruta numérico ("12"); null si no lo es.
export const idDeRuta = (args) => (/^\d+$/.test(args?.[0] ?? "") ? Number(args[0]) : null);

export function desconocida(id) {
  return h("section", { class: "pendiente" }, h("h2", {}, t("Pantalla desconocida")), h("p", { class: "sub" }, String(id ?? "")));
}
export const volver = (tipo, texto) => h("p", { class: "volver" }, h("a", { href: "#/" + tipo }, "← " + t(texto)));

// Lista de datos: pares [etiqueta, valor]; omite los vacíos. Un valor puede ser texto o Node.
export function datos(pares) {
  const fil = pares.filter(([, v]) => !vacio(v));
  if (!fil.length) return null;
  return h("dl", { class: "datos" }, fil.map(([k, v]) => [h("dt", {}, t(k)), h("dd", {}, v)]));
}
export const seccion = (titulo, ...hijos) => h("section", { class: "bloque" }, h("h3", {}, t(titulo)), ...hijos);

export function tabla(cabeceras, filas, { clase = "" } = {}) {
  return h("div", { class: "tabla-scroll" }, h("table", { class: "tabla " + clase },
    h("thead", {}, h("tr", {}, cabeceras.map((c) => h("th", {}, t(c))))),
    h("tbody", {}, filas)));
}

// "Equipo B · conector" con enlaces (extremos opuestos de un cable).
const otros = (lista) => lista.map((o, i) => h("span", { class: "otro" }, i ? " · " : "",
  enlace("equipos", o.id_equipo, o.equipo || "?"), " ", h("span", { class: "sub" }, "/"), " ", enlace("conectores", o.id_conector, o.conector || "?")));

function conexionesDe(conexiones, acciones = null) {
  if (!conexiones.length) return h("span", { class: "sub" }, t("Sin conexión"));
  return conexiones.map((c) => h("div", { class: "conexion" },
    enlace("cables", c.id_cable, c.cable), c.es_conexion_interna ? h("span", { class: "etiqueta" }, t("interna")) : null,
    c.otros.length ? [" → ", otros(c.otros)] : null,
    c.es_armado_correcto === 0 ? h("span", { class: "etiqueta mal" }, t("Armado incorrecto")) : null,
    acciones ? acciones(c) : null));
}

const senalTxt = (s) => (s ? [s.senal, s.formato, s.origen].filter(Boolean).join(" · ") : "");

// ── Equipo ───────────────────────────────────────────────────────────────────
export async function fichaEquipo({ rpc, args }) {
  const id = idDeRuta(args); if (id == null) return desconocida(args?.[0]);
  const e = await rpc.llamar("equipo_ficha", { id_equipo: id });
  const dim = [e.ancho_mm, e.alto_mm, e.profundidad_mm].every(vacio) ? null : [e.ancho_mm, e.alto_mm, e.profundidad_mm].map((v) => (vacio(v) ? "?" : num(v))).join(" × ") + " mm";
  const marcadores = e.conectores.map((c, i) => ({ id: c.id_conector, nombre: c.nombre, x: c.x, y: c.y, n: i + 1, path: c.imagen_path || e.imagen_path }));
  // Un bloque de imagen por archivo: primero la del equipo (aunque no tenga marcadores), luego las propias de los conectores.
  const paths = [...new Set([e.imagen_path, ...marcadores.filter((m) => !vacio(m.x)).map((m) => m.path)].filter(Boolean))];

  return h("section", { class: "ficha ficha-equipo" },
    volver("equipos", "Volver a Equipos"),
    h("h2", {}, e.nombre || "#" + e.id_equipo),
    h("p", { class: "sub" }, [e.tipo, [e.marca, e.modelo].filter(Boolean).join(" ")].filter(Boolean).join(" · ")),
    h("p", { class: "acciones" }, h("a", { href: ruta("conexiones", e.id_equipo) }, "🔗 " + t("Árbol de conexiones")),
      " · ", h("a", { href: "#/analisis/impacto/equipo/" + e.id_equipo }, "📉 " + t("Impacto si falla"))),
    h("p", { class: "acciones abm" },
      boton(t("Editar"), "editar", () => editarEquipo(rpc, e.id_equipo)), " ",
      boton("+ " + t("Conector"), "conector", () => altaConector(rpc, e.id_equipo)), " ",
      boton(t("Eliminar"), "eliminar", () => eliminarEquipo(rpc, { id_equipo: e.id_equipo, nombre: e.nombre }), "peligro")),
    datos([["Marca", e.marca], ["Tipo", e.tipo], ["Modelo", e.modelo], ["Inventario", e.num_inventario], ["Serie", e.num_serie],
      ["Rol de señal", e.rol_senal], ["Fabricación", e.fecha_fabricacion], ["Equipo usado", Number(e.es_equipo_usado) ? t("Sí") : null],
      ["Dimensiones", dim], ["Señal requerida (MHz)", e.senal_requerida_mhz], ["Manual", e.path_manual],
      ["Última edición", e.fecha_ultima_edicion], ["Última auditoría", e.ultima_auditoria_fecha]]),
    e.configuraciones ? seccion("Configuraciones", h("pre", { class: "texto" }, e.configuraciones)) : null,

    seccion("Ubicación", e.racks.length || e.slots.length
      ? h("ul", {}, [
        ...e.racks.map((r) => h("li", {}, [r.sala,
          [enlace("racks", r.id_rack, [t("Rack"), r.rack_numero ?? r.rack].filter(Boolean).join(" ") + (r.rack && r.rack_numero != null ? ` (${r.rack})` : ""))],
          vacio(r.orificio) ? null : `${t("Posición")} ${r.orificio}` + (vacio(r.unidades) ? "" : ` (${r.unidades} U)`)].filter(Boolean).flatMap((x, i) => (i ? [" · ", x] : [x])))),
        ...e.slots.map((s) => h("li", {}, `${t("Frame")}: `, enlace("frames", s.id_frame, s.frame || "?"), ` · ${t("Slot")}: ${s.slot || "?"}`))])
      : h("p", { class: "sub" }, t("Sin ubicación"))),

    e.riesgo ? seccion("Riesgo", datos([["Nivel", e.riesgo.nivel], ["Riesgo", vacio(e.riesgo.riesgo) ? null : num(e.riesgo.riesgo)],
      ["Probabilidad", vacio(e.riesgo.probabilidad) ? null : num(e.riesgo.probabilidad)], ["Impacto", vacio(e.riesgo.impacto) ? null : num(e.riesgo.impacto)],
      ["Calculado", e.riesgo.fecha_calculo]])) : null,

    e.problemas.length ? seccion("Problemas", h("ul", {}, e.problemas.map((p) => h("li", { class: Number(p.resuelto) ? "sub" : "" },
      [p.categoria, p.gravedad != null ? `${t("Gravedad")} ${p.gravedad}` : null, p.descripcion, Number(p.resuelto) ? t("Resuelto") : t("Abierto")].filter(Boolean).join(" · "))))) : null,

    paths.length ? seccion("Imagen", paths.map((p) => imagenConConectores({ path: p, marcadores: marcadores.filter((m) => m.path === p && !vacio(m.x)) }))) : null,

    seccion("Conectores", e.conectores.length
      ? tabla(["#", "Nombre", "Tipo", "Ficha", "Señal", "Conexiones"], e.conectores.map((c, i) =>
        h("tr", { "data-conector": c.id_conector },
          h("td", { class: "n" }, i + 1), h("td", {}, enlace("conectores", c.id_conector, c.nombre)), h("td", {}, c.tipo_conector || ""),
          h("td", {}, c.ficha || ""), h("td", {}, senalTxt(c.senal)), h("td", {}, conexionesDe(c.conexiones)))))
      : h("p", { class: "sub" }, t("Sin conectores"))));
}

// ── Conector ─────────────────────────────────────────────────────────────────
export async function fichaConector({ rpc, args }) {
  const id = idDeRuta(args); if (id == null) return desconocida(args?.[0]);
  const c = await rpc.llamar("conector_ficha", { id_conector: id });
  const r = c.ruteo_entrada;
  const m = c.imagen_path && !vacio(c.coordenada_x_en_imagen) && !vacio(c.coordenada_y_en_imagen)
    ? [{ id: c.id_conector, nombre: c.nombre, x: c.coordenada_x_en_imagen, y: c.coordenada_y_en_imagen, n: "●" }] : [];
  return h("section", { class: "ficha ficha-conector" },
    c.id_equipo != null ? h("p", { class: "volver" }, h("a", { href: ruta("equipos", c.id_equipo) }, "← " + (c.equipo || t("Equipo")))) : volver("equipos", "Volver a Equipos"),
    h("h2", {}, c.nombre || "#" + c.id_conector),
    h("p", { class: "sub" }, [c.equipo, c.tipo_conector].filter(Boolean).join(" · ")),
    h("p", { class: "acciones" }, h("a", { href: "#/analisis/diagnostico/" + c.id_conector }, "🩺 " + t("Diagnosticar falla desde este conector"))),
    h("p", { class: "acciones abm" },
      boton(t("Editar"), "editar", () => editarConector(rpc, c.id_conector)), " ",
      boton(t("Eliminar"), "eliminar", () => eliminarConector(rpc, { id_conector: c.id_conector, nombre: c.nombre, id_equipo: c.id_equipo }), "peligro")),
    datos([["Equipo", c.id_equipo != null ? enlace("equipos", c.id_equipo, c.equipo) : null], ["Tipo", c.tipo_conector], ["Ficha", c.ficha],
      ["Balance", c.modo_balance], ["Canal", c.modo_canal], ["Señal", senalTxt(c.senal)],
      ["Ruteo de entrada (matriz)", r ? [enlace("equipos", r.id_equipo, r.equipo), " / ", enlace("conectores", r.id_conector, r.conector)] : null],
      ["Última edición", c.fecha_ultima_edicion], ["Última auditoría", c.ultima_auditoria_fecha]]),
    seccion("Conexiones", h("p", { class: "acciones" }, boton("+ " + t("Conectar a un cable"), "conectar", () => altaConexion(rpc, { id_conector: c.id_conector }))),
      conexionesDe(c.conexiones, (x) => h("span", { class: "acciones-fila" },
        boton(t("Editar"), "editar-conexion", () => editarConexion(rpc, x.id_conexion), null, t("Editar conexión") + " " + (x.cable || "#" + x.id_cable)), " ",
        boton(t("Quitar"), "quitar-conexion", () => eliminarConexion(rpc, x.id_conexion, `${x.cable || "#" + x.id_cable} → ${c.equipo || ""} / ${c.nombre || ""}`), "peligro",
          t("Quitar conexión") + " " + (x.cable || "#" + x.id_cable))))),
    c.imagen_path ? seccion("Imagen", imagenConConectores({ path: c.imagen_path, marcadores: m, resaltar: c.id_conector })) : null);
}

// ── Cable ────────────────────────────────────────────────────────────────────
export async function fichaCable({ rpc, args }) {
  const id = idDeRuta(args); if (id == null) return desconocida(args?.[0]);
  const k = await rpc.llamar("cable_ficha", { id_cable: id });
  const u = k.unidad_longitud ? " " + k.unidad_longitud : "";
  const metraje = [k.metraje_impreso_primer_extremo, k.metraje_impreso_segundo_extremo];
  return h("section", { class: "ficha ficha-cable" },
    volver("cables", "Volver a Cables"),
    h("h2", {}, k.codigo || "#" + k.id_cable),
    h("p", { class: "sub" }, [k.tipo_cable, k.ficha].filter(Boolean).join(" · ")),
    h("p", { class: "acciones" }, h("a", { href: ruta("cadena", k.id_cable) }, "⛓ " + t("Ver cadena completa")),
      " · ", h("a", { href: "#/analisis/impacto/cable/" + k.id_cable }, "✂ " + t("Impacto si se corta"))),
    h("p", { class: "acciones abm" },
      boton(t("Editar"), "editar", () => editarCable(rpc, k.id_cable)), " ",
      boton("+ " + t("Conexión"), "conexion", () => altaConexion(rpc, { id_cable: k.id_cable })), " ",
      botonExtremo(k, rpc), " ",
      boton(t("Eliminar"), "eliminar", () => eliminarCable(rpc, k), "peligro")),
    datos([["Código", k.codigo], ["Tipo de cable", k.tipo_cable], ["Ficha", k.ficha], ["Longitud", vacio(k.longitud) ? null : num(k.longitud) + u],
      ["Estado", k.estado], ["Metraje impreso", metraje.every(vacio) ? null : metraje.map((v) => (vacio(v) ? "?" : v)).join(" / ") + (k.unidad_metraje_impreso ? " " + k.unidad_metraje_impreso : "")],
      ["Cable interno", Number(k.es_cable_conexion_interna) ? t("Sí") : null], ["Ancho de banda (MHz)", k.ancho_banda_mhz_override],
      ["Cable fusionado", k.id_cable_fusionado != null ? enlace("cables", k.id_cable_fusionado, "#" + k.id_cable_fusionado) : null],
      ["Notas de relevamiento", k.notas_relevamiento], ["Última edición", k.fecha_ultima_edicion], ["Última auditoría", k.ultima_auditoria_fecha]]),
    seccion("Extremos", k.extremos.length
      ? tabla(["Equipo", "Conector", "Tipo", "Ficha", "Armado", ""], k.extremos.map((x) => h("tr", { "data-conexion": x.id_conexion },
        h("td", {}, x.id_conector == null ? h("span", { class: "sub" }, t("Extremo suelto")) : enlace("equipos", x.id_equipo, x.equipo)),
        h("td", {}, x.id_conector == null ? "" : enlace("conectores", x.id_conector, x.conector)),
        h("td", {}, x.tipo_conector || ""), h("td", {}, x.ficha_conexion || ""),
        h("td", {}, x.es_armado_correcto === 0 ? h("span", { class: "etiqueta mal" }, t("Armado incorrecto") + (x.detalle_armado ? ": " + x.detalle_armado : "")) : x.es_armado_correcto === 1 ? t("Armado correcto") : ""),
        h("td", { class: "acciones" },
          boton(t("Editar"), "editar-conexion", () => editarConexion(rpc, x.id_conexion), null, t("Editar conexión") + " #" + x.id_conexion), " ",
          boton(t("Quitar"), "quitar-conexion", () => eliminarConexion(rpc, x.id_conexion, `${k.codigo || "#" + k.id_cable} → ${x.equipo || t("Extremo suelto")}${x.conector ? " / " + x.conector : ""}`), "peligro",
            t("Quitar conexión") + " #" + x.id_conexion)))))
      : h("p", { class: "sub" }, t("Sin conexión"))));
}

// B.4: «Marcar extremo desconectado» (equipo FANTASMA); con los dos extremos ya documentados queda deshabilitado.
function botonExtremo(k, rpc) {
  const b = boton("⚡ " + t("Extremo desconectado"), "extremo", () => extremoDesconectado(rpc, { id_cable: k.id_cable, codigo: k.codigo }));
  if (k.extremos.length >= 2) { b.disabled = true; b.title = t("Este cable ya tiene sus dos extremos documentados."); }
  return b;
}

// ── Lista de cables ──────────────────────────────────────────────────────────
const MAX_FILAS = 500;
let filtroCables = "";                                     // sobrevive al repintado que sigue a cada escritura (B.3)
export async function listaCables({ rpc, args }) {
  const id = idDeRuta(args); if (id != null) return fichaCable({ rpc, args });
  if (args?.length) return desconocida(args[0]);
  const cables = (await rpc.llamar("cables_lista")).map((k) => ({ k, busqueda: normalizar([k.codigo, k.tipo_cable, k.ficha, k.estado].filter(Boolean).join(" ")) }));
  const porId = new Map(cables.map(({ k }) => [k.id_cable, k]));
  const cuerpo = h("tbody"), estado = h("p", { class: "sub", "aria-live": "polite" });
  let pend = 0, seleccion = [];                            // seleccion: ids marcados para fusionar, en orden de clic (máx. 2)
  const btnFusion = h("button", { type: "button", "data-accion": "fusionar", disabled: true, onclick: seguro(() => fusionarCables(rpc, porId.get(seleccion[0]), porId.get(seleccion[1]))) });
  function sincronizarSeleccion() {
    cuerpo.querySelectorAll("input[type=checkbox]").forEach((cb) => { cb.checked = seleccion.includes(Number(cb.dataset.id)); });
    btnFusion.disabled = seleccion.length !== 2;
    btnFusion.textContent = t("Fusionar") + ` (${seleccion.length}/2)`;
    btnFusion.title = seleccion.length === 2 ? "" : t("Marcá dos cables para fusionarlos");
  }
  function pintar() {
    const toks = normalizar(entrada.value).trim().split(/\s+/).filter(Boolean);
    const ok = toks.length ? cables.filter((c) => toks.every((x) => c.busqueda.includes(x))) : cables;
    cuerpo.replaceChildren(...ok.slice(0, MAX_FILAS).map(({ k }) => h("tr", {},
      h("td", {}, h("input", { type: "checkbox", "data-id": k.id_cable, "aria-label": t("Elegir para fusionar") + " " + (k.codigo || "#" + k.id_cable),
        onchange: () => { seleccion = alternarSeleccion(seleccion, k.id_cable); sincronizarSeleccion(); } })),
      h("td", {}, enlace("cables", k.id_cable, k.codigo)), h("td", {}, k.tipo_cable || ""), h("td", {}, k.ficha || ""),
      h("td", { class: "n" }, vacio(k.longitud) ? "" : num(k.longitud) + (k.unidad_longitud ? " " + k.unidad_longitud : "")), h("td", {}, k.estado || ""), h("td", { class: "n" }, k.n_conexiones))));
    estado.textContent = !cables.length ? t("No hay cables cargados") : !ok.length ? t("Sin resultados")
      : ok.length > MAX_FILAS ? t("Mostrando {a} de {b}", { a: MAX_FILAS, b: ok.length.toLocaleString() }) : t("{n} cables", { n: ok.length.toLocaleString() });
    sincronizarSeleccion();
  }
  const entrada = h("input", { type: "search", class: "arbol-filtro", autocomplete: "off", placeholder: t("Buscar cable…"), "aria-label": t("Buscar cable…"), value: filtroCables,
    oninput: () => { filtroCables = entrada.value; clearTimeout(pend); pend = setTimeout(pintar, 200); } });
  pintar();
  return h("section", { class: "ficha" }, h("h2", {}, t("Cables")),
    h("p", { class: "acciones abm" }, boton("+ " + t("Nuevo cable"), "nuevo", () => altaCable(rpc), "primario"), " ", boton("⚡ " + t("Temporal"), "temporal", () => cableTemporal(rpc)), " ", btnFusion),
    h("div", { class: "arbol-barra" }, entrada), estado,
    h("div", { class: "tabla-scroll" }, h("table", { class: "tabla" },
      h("thead", {}, h("tr", {}, h("th", { "aria-label": t("Fusionar"), title: t("Marcá dos cables para fusionarlos") }, "⇄"), ["Código", "Tipo de cable", "Ficha", "Longitud", "Estado", "Conexiones"].map((c) => h("th", {}, t(c))))), cuerpo)));
}
