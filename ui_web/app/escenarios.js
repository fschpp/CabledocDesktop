// Escenarios (A.8): abrir y evaluar los escenarios guardados en la base. Solo lectura (crear, editar y aplicar es Fase B, B.11).
// Rutas: #/escenarios (lista) · #/escenarios/<id> (cambios + evaluación, que corre sola al abrir: son milisegundos).
// Datos del bridge: escenarios_lista y escenario_evaluar (devuelve también los cambios; escenario_ficha existe para B.11).
import { h } from "./dom.js";
import { t, idioma } from "./i18n.js";
import { enlace, idDeRuta, desconocida, volver, datos, seccion, tabla } from "./fichas.js";

const num = (v, d = 0) => (v == null ? "—" : Number(v).toLocaleString(idioma(), { maximumFractionDigits: d }));
const aviso = (clase, ...hijos) => h("p", { class: "aviso " + clase, role: "status" }, ...hijos);
const celda = (...hijos) => h("td", {}, ...hijos);
const tarjeta = (n, etiqueta, sub) => h("div", { class: "tarjeta" }, h("div", { class: "n" }, n), h("div", { class: "et" }, t(etiqueta)), sub ? h("div", { class: "sub" }, sub) : null);

// Estados posibles de la tabla `escenario` (Modelo.actualizar_estado_escenario).
const ESTADOS = { borrador: "Borrador", simulado: "Simulado", aprobado: "Aprobado", aplicado: "Aplicado", descartado: "Descartado" };
const chipEstado = (e) => h("span", { class: "estado e-" + String(e).replace(/[^a-z]/g, "") }, ESTADOS[e] ? t(ESTADOS[e]) : String(e ?? "—"));

const TIPOS = { falla_equipo: ["🔺", "Falla de equipo"], desconexion_cable: ["✕", "Cable cortado"], conexion_virtual: ["🔗", "Reconexión virtual"] };

// "Equipo / conector" de una punta de reconexión; si el conector ya no existe en la base, no se enlaza a una ficha inexistente.
function punta(c, x) {
  const id = c["id_conector_" + x], nombre = c["conector_" + x];
  if (nombre == null) return h("span", { class: "sub" }, t("Conector {id} (ya no existe)", { id: id ?? "?" }));
  return [enlace("equipos", c["id_equipo_" + x], c["equipo_" + x] || "?"), " ", h("span", { class: "sub" }, "/"), " ", enlace("conectores", id, nombre)];
}

function detalle(c) {
  if (c.tipo === "falla_equipo") return c.equipo == null ? h("span", { class: "sub" }, t("Equipo {id} (ya no existe)", { id: c.id_equipo ?? "?" })) : enlace("equipos", c.id_equipo, c.equipo);
  if (c.tipo === "desconexion_cable") return c.cable == null ? h("span", { class: "sub" }, t("Cable {id} (ya no existe)", { id: c.id_cable ?? "?" })) : enlace("cables", c.id_cable, c.cable);
  if (c.tipo === "conexion_virtual") return [punta(c, "a"), " → ", punta(c, "b")];
  return h("span", { class: "sub" }, String(c.tipo));
}

function tablaCambios(cambios) {
  if (!cambios.length) return aviso("", t("Este escenario no tiene cambios."));
  return tabla(["Tipo", "Detalle"], cambios.map((c) => {
    const [icono, clave] = TIPOS[c.tipo] ?? ["•", c.tipo];
    return h("tr", { "data-tipo": c.tipo }, celda(icono + " " + t(clave)), celda(detalle(c)));
  }));
}

// Resumen de la lista: solo los tipos que tienen cambios ("Fallas: 1 · Reconexiones: 1").
function resumenCambios(e) {
  const partes = [["n_fallas", "Fallas"], ["n_cortes", "Cortes"], ["n_reconexiones", "Reconexiones"]].filter(([k]) => e[k] > 0).map(([k, c]) => t(c) + ": " + num(e[k]));
  return partes.length ? partes.join(" · ") : t("Sin cambios");
}

// ── Lista ────────────────────────────────────────────────────────────────────
async function lista({ rpc }) {
  const items = await rpc.llamar("escenarios_lista");
  return h("section", { class: "ficha escenarios" },
    h("h2", {}, t("Escenarios")),
    h("p", { class: "sub" }, t("Simulaciones de falla guardadas en la base: fallas de equipo, cables cortados y reconexiones de emergencia. Acá se abren y se evalúan; crearlas y editarlas llega con la Fase B.")),
    items.length
      ? [h("p", { class: "sub", "aria-live": "polite" }, t("{n} elementos", { n: items.length.toLocaleString() })),
        tabla(["Nombre", "Estado", "Cambios", "Última edición"], items.map((e) => h("tr", { "data-id": e.id_escenario },
          celda(enlace("escenarios", e.id_escenario, e.nombre || "#" + e.id_escenario), e.descripcion ? h("div", { class: "sub" }, e.descripcion) : null),
          celda(chipEstado(e.estado)), celda(resumenCambios(e)), celda(e.fecha || "")))) ]
      : aviso("", t("No hay escenarios guardados en esta base. Se crean en el escritorio (Modo Escenario).")));
}

// ── Evaluación ───────────────────────────────────────────────────────────────
function resultado(r) {
  if (!r.grafo_disponible) return aviso("error", t("No se pudo construir el grafo de conexiones, así que no hay evaluación. Revisá que la base tenga cables y conexiones cargados."));
  if (!r.cambios.length) return aviso("", t("Sin cambios no hay nada que evaluar."));
  const recon = r.hay_reconexion;
  const sinImpacto = !r.n_despues && !r.cables_impactados.length;
  return h("div", { class: "resultado-escenario" },
    h("div", { class: "tarjetas" },
      tarjeta(recon ? num(r.n_antes) + " → " + num(r.n_despues) : num(r.n_despues), "Equipos sin señal", t("{p}% de {n}", { p: num(r.porcentaje_despues, 1), n: num(r.total_equipos) })),
      recon ? tarjeta(num(r.n_recuperados), "Recuperados", t("por la reconexión virtual")) : null,
      tarjeta(num(r.n_puntos_finales), "Puntos finales afectados", t("de {n}", { n: num(r.total_puntos_finales) })),
      tarjeta(num(r.cables_impactados.length), "Cables afectados")),
    h("p", { class: "sub" }, t("Los equipos que fallan en el escenario no se cuentan como equipos sin señal.")),
    recon ? aviso(r.n_despues < r.n_antes ? "ok" : "", t("Con las reconexiones virtuales los equipos sin señal pasan de {a} a {b} ({r} recuperados).", { a: num(r.n_antes), b: num(r.n_despues), r: num(r.n_recuperados) })) : null,
    sinImpacto ? aviso("ok", "✔ " + t("Sin impacto: ningún equipo queda sin señal.")) : null,
    r.conectores_invalidos.length ? aviso("error", t("Hay reconexiones con un conector que ya no existe; se ignoraron en el cálculo:"), h("ul", {}, r.conectores_invalidos.map((c) =>
      h("li", {}, punta(c, "a"), " → ", punta(c, "b"))))) : null,
    r.equipos.length ? seccion("Equipos sin señal",
      tabla(recon ? ["Equipo", "Punto final", "Con la reconexión"] : ["Equipo", "Punto final"], r.equipos.map((e) => h("tr", { "data-estado": e.estado },
        celda(enlace("equipos", e.id_equipo, e.nombre), " ", h("a", { href: "#/analisis/impacto/equipo/" + e.id_equipo, title: t("Impacto si falla"), "aria-label": t("Impacto si falla") }, "📉")),
        celda(e.punto_final ? t("Sí") : ""),
        recon ? celda(e.estado === "recuperado" ? "✔ " + t("Recuperado") : t("Sin señal")) : null)))) : null,
    r.cables_impactados.length ? seccion("Cables afectados",
      h("p", { class: "cables-afectados" }, r.cables_impactados.map((c, i) => [i ? " · " : "", enlace("cables", c.id_cable, c.codigo)]))) : null,
    r.causas_regla.length ? seccion("Reglas lógicas que dejan de cumplirse",
      tabla(["Equipo", "Causa"], r.causas_regla.map((c) => h("tr", {}, celda(enlace("equipos", c.id_equipo, c.nombre)), celda(c.texto))))) : null);
}

async function ficha({ rpc }, id) {
  const r = await rpc.llamar("escenario_evaluar", { id_escenario: id });
  const e = r.escenario;
  return h("section", { class: "ficha escenario" },
    volver("escenarios", "Volver a Escenarios"),
    h("h2", {}, e.nombre || "#" + e.id_escenario, " ", chipEstado(e.estado)),
    datos([["Descripción", e.descripcion], ["Creado", e.fecha_creacion], ["Última edición", e.fecha_ultima_edicion]]),
    e.estado === "aplicado" ? aviso("", t("Este escenario ya se aplicó a la infraestructura: la evaluación se calcula sobre el estado actual de la base, que ya incluye esos cambios.")) : null,
    e.estado === "descartado" ? aviso("", t("Este escenario está descartado.")) : null,
    seccion("Cambios", tablaCambios(r.cambios)),
    seccion("Resultado de la evaluación", resultado(r),
      h("p", { class: "sub" }, t("Calculado en {ms} ms. El resultado no se guarda ni cambia el estado del escenario.", { ms: num(r.calculo_ms, 1) }))));
}

// ctx = { rpc, args, gen }; args = [] o ["12"]
export function vistaEscenarios(ctx) {
  if (!ctx.args?.length) return lista(ctx);
  const id = idDeRuta(ctx.args);
  return id == null ? desconocida(ctx.args[0]) : ficha(ctx, id);
}
