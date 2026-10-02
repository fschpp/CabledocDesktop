// Análisis (A.7): impacto de fallas, IRF, asistente de diagnóstico y linter de topología. Solo lectura.
// Rutas: #/analisis/impacto[/equipo|cable|rack[/<id>]] · #/analisis/riesgo · #/analisis/diagnostico[/equipo/<id> | /<id_conector>] · #/analisis/topologia
// Datos del bridge: impacto_equipo/cable/rack, riesgo_irf, conectores_de_equipo, diagnostico, linter_topologia (más las listas de A.1 para elegir).
import { h } from "./dom.js";
import { t, idioma } from "./i18n.js";
import { normalizar } from "./arbol.js";

const MAX_RESULTADOS = 50;
const ruta = (...p) => "#/" + p.map((x) => encodeURIComponent(x)).join("/");
const esId = (v) => /^\d+$/.test(v ?? "");
const num = (v, d = 1) => (v == null ? "—" : Number(v).toLocaleString(idioma(), { maximumFractionDigits: d }));
const enlace = (href, texto) => h("a", { href }, texto);
const aviso = (clase, ...hijos) => h("p", { class: "aviso " + clase, role: "status" }, ...hijos);

const PESTANAS = [["impacto", "Impacto"], ["riesgo", "Riesgo (IRF)"], ["diagnostico", "Diagnóstico"], ["topologia", "Topología"]];

function marco(activa, ...hijos) {
  return h("section", { class: "ficha analisis" },
    h("h2", {}, t("Análisis")),
    h("nav", { class: "pestanas", "aria-label": t("Análisis") },
      PESTANAS.map(([id, clave]) => h("a", { href: ruta("analisis", id), "aria-current": id === activa ? "page" : null }, t(clave)))),
    ...hijos);
}

function tabla(cabeceras, filas, clase = "") {
  return h("div", { class: "tabla-scroll" }, h("table", { class: "tabla " + clase },
    h("thead", {}, h("tr", {}, cabeceras.map((c) => h("th", {}, t(c))))),
    h("tbody", {}, filas)));
}
const celda = (...hijos) => h("td", {}, ...hijos);
const celdaNum = (v, d = 1) => h("td", { class: "n" }, num(v, d));
const tarjeta = (n, etiqueta, sub) => h("div", { class: "tarjeta" }, h("div", { class: "n" }, n), h("div", { class: "et" }, t(etiqueta)), sub ? h("div", { class: "sub" }, sub) : null);

const nivelClase = (n) => "nivel n-" + normalizar(String(n ?? "")).replace(/[^a-z]/g, "");
const insignia = (nivel) => (nivel ? h("span", { class: nivelClase(nivel) }, t(nivel)) : h("span", { class: "sub" }, "—"));

// Filtro + lista de hasta MAX_RESULTADOS elementos (mismas reglas que "Conexiones": todas las palabras, sin acentos ni mayúsculas).
function selector({ items, texto, nombre, href, sub, placeholder }) {
  const todos = items.map((x) => ({ x, b: normalizar(texto(x)) }));
  const lista = h("ul", { class: "elegir-equipo" }), estado = h("p", { class: "sub", "aria-live": "polite" });
  let pend = 0;
  function pintar() {
    const toks = normalizar(entrada.value).trim().split(/\s+/).filter(Boolean);
    const ok = toks.length ? todos.filter((e) => toks.every((k) => e.b.includes(k))) : todos;
    lista.replaceChildren(...ok.slice(0, MAX_RESULTADOS).map(({ x }) => h("li", {}, enlace(href(x), nombre(x) || "#"), " ", h("span", { class: "sub" }, sub ? sub(x) : ""))));
    estado.textContent = !todos.length ? t("No hay elementos cargados") : !ok.length ? t("Sin resultados")
      : ok.length > MAX_RESULTADOS ? t("Mostrando {a} de {b}", { a: MAX_RESULTADOS, b: ok.length.toLocaleString() }) : t("{n} elementos", { n: ok.length.toLocaleString() });
  }
  const entrada = h("input", { type: "search", class: "arbol-filtro", autocomplete: "off", placeholder: t(placeholder), "aria-label": t(placeholder),
    oninput: () => { clearTimeout(pend); pend = setTimeout(pintar, 200); } });
  pintar();
  return h("div", {}, h("div", { class: "arbol-barra" }, entrada), estado, lista);
}

// ── Impacto ──────────────────────────────────────────────────────────────────
const TIPOS = {
  equipo: { etiqueta: "Equipo", lista: "equipos_lista", id: "id_equipo", fn: "impacto_equipo", titulo: "Si falla «{n}» por completo",
    ayuda: "Elegí un equipo para ver qué otros equipos quedan sin señal si deja de funcionar.", placeholder: "Buscar equipo…",
    nombre: (e) => e.nombre, texto: (e) => [e.nombre, e.marca, e.modelo, e.tipo].filter(Boolean).join(" "), sub: (e) => [e.tipo, [e.marca, e.modelo].filter(Boolean).join(" ")].filter(Boolean).join(" · "), ficha: "equipos" },
  cable: { etiqueta: "Cable", lista: "cables_lista", id: "id_cable", fn: "impacto_cable", titulo: "Si se corta el cable «{n}»",
    ayuda: "Elegí un cable para ver qué equipos quedan sin señal si se corta.", placeholder: "Buscar cable…",
    nombre: (k) => k.codigo, texto: (k) => [k.codigo, k.tipo_cable].filter(Boolean).join(" "), sub: (k) => k.tipo_cable || "", ficha: "cables" },
  rack: { etiqueta: "Rack", lista: "racks_lista", id: "id_rack", fn: "impacto_rack", titulo: "Si se pierde el rack «{n}»",
    ayuda: "Elegí un rack para ver qué equipos quedan sin señal si se pierde completo.", placeholder: "Buscar rack…",
    nombre: (r) => r.nombre || "Rack " + r.numero, texto: (r) => [r.nombre, r.numero, r.sala].filter((v) => v != null && v !== "").join(" "), sub: (r) => r.sala || "", ficha: null },
};

function resultadoImpacto(r, T) {
  const nombre = r.origen.nombre || "#" + r.origen.id;
  const sinImpacto = !r.n_impactados && !r.cables_impactados.length;
  return h("div", {},
    h("h3", {}, t(T.titulo, { n: nombre })),
    h("div", { class: "tarjetas" },
      tarjeta(num(r.n_impactados, 0), "Equipos sin señal", t("{p}% de {n}", { p: num(r.porcentaje), n: num(r.total_equipos, 0) })),
      tarjeta(num(r.n_puntos_finales, 0), "Puntos finales afectados", t("de {n}", { n: num(r.total_puntos_finales, 0) })),
      tarjeta(num(r.cables_impactados.length, 0), "Cables afectados")),
    sinImpacto ? aviso("ok", "✔ " + t("Sin impacto: ningún equipo queda sin señal.")) : null,
    r.equipos_impactados.length ? h("section", { class: "bloque" }, h("h3", {}, t("Equipos sin señal")),
      tabla(["Equipo", "Punto final"], r.equipos_impactados.map((e) => h("tr", {},
        celda(enlace(ruta("equipos", e.id_equipo), e.nombre || "#" + e.id_equipo), " ", enlace(ruta("analisis", "impacto", "equipo", e.id_equipo), "📉")),
        celda(e.punto_final ? t("Sí") : ""))))) : null,
    r.cables_impactados.length ? h("section", { class: "bloque" }, h("h3", {}, t("Cables afectados")),
      h("p", { class: "cables-afectados" }, r.cables_impactados.map((c, i) => [i ? " · " : "", enlace(ruta("cables", c.id_cable), c.codigo || "#" + c.id_cable)]))) : null,
    r.causas_regla.length ? h("section", { class: "bloque" }, h("h3", {}, t("Reglas lógicas que dejan de cumplirse")),
      tabla(["Equipo", "Causa"], r.causas_regla.map((c) => h("tr", {}, celda(enlace(ruta("equipos", c.id_equipo), c.nombre)), celda(c.texto))))) : null);
}

async function impacto({ rpc, args }) {
  const [tipo = "equipo", id] = args;
  const T = TIPOS[tipo];
  if (!T) return marco("impacto", aviso("error", t("Pantalla desconocida") + ": " + tipo));
  const barra = h("p", { class: "acciones" }, Object.entries(TIPOS).map(([k, v]) =>
    h("a", { href: ruta("analisis", "impacto", k), class: "chip", "aria-current": k === tipo ? "true" : null }, t(v.etiqueta))));
  if (!esId(id)) {
    const items = await rpc.llamar(T.lista);
    return marco("impacto", barra, h("p", { class: "sub" }, t(T.ayuda)),
      selector({ items, nombre: T.nombre, texto: T.texto, sub: T.sub, placeholder: T.placeholder, href: (x) => ruta("analisis", "impacto", tipo, x[T.id]) }));
  }
  const r = await rpc.llamar(T.fn, { [T.id]: Number(id) });
  return marco("impacto", barra,
    h("p", { class: "volver" }, enlace(ruta("analisis", "impacto", tipo), "← " + t("Elegir otro")),
      T.ficha ? [" · ", enlace(ruta(T.ficha, id), t("Ver ficha"))] : null),
    resultadoImpacto(r, T));
}

// ── Riesgo (IRF) ─────────────────────────────────────────────────────────────
let cacheRiesgo = null;                       // { gen, data }: el cálculo tarda ~3 s; se reusa mientras no cambie la base

function tablaRiesgo(data) {
  const cuerpo = h("div", {});
  const filtroNivel = h("select", { "aria-label": t("Nivel"), onchange: pintar },
    h("option", { value: "" }, t("Todos los niveles")), data.niveles.map((n) => h("option", { value: n.nivel }, t(n.nivel))));
  const filtroTexto = h("input", { type: "search", class: "arbol-filtro", autocomplete: "off", placeholder: t("Buscar equipo…"), "aria-label": t("Buscar equipo…"), oninput: () => { clearTimeout(pend); pend = setTimeout(pintar, 200); } });
  let pend = 0;
  const busq = data.filas.map((f) => normalizar([f.nombre, f.tipo].filter(Boolean).join(" ")));
  function pintar() {
    const toks = normalizar(filtroTexto.value).trim().split(/\s+/).filter(Boolean), niv = filtroNivel.value;
    const ok = data.filas.filter((f, i) => (!niv || f.nivel === niv) && toks.every((k) => busq[i].includes(k)));
    cuerpo.replaceChildren(
      h("p", { class: "sub", "aria-live": "polite" }, ok.length ? t("{n} equipos", { n: ok.length.toLocaleString() }) : t("Sin resultados")),
      ok.length ? tabla(["Equipo", "Tipo", "Probabilidad", "Impacto", "Riesgo", "Nivel", "Prob. / Impacto"], ok.map((f) => {
        const d = f.detalle || {};
        const pista = [t("Edad") + ": " + num(d.s_edad), t("Uso") + ": " + num(d.s_uso), t("Historial") + ": " + num(d.s_historial)].join(" · ");
        const [p, i] = f.cuadrante.split("/");
        return h("tr", {},
          celda(enlace(ruta("equipos", f.id_equipo), f.nombre), " ", enlace(ruta("analisis", "impacto", "equipo", f.id_equipo), "📉")),
          celda(f.tipo || ""), h("td", { class: "n", title: pista }, num(f.probabilidad)), celdaNum(f.impacto),
          h("td", { class: "n riesgo", title: pista }, num(f.riesgo)), celda(insignia(f.nivel)), celda(t(p) + " / " + t(i)));
      }), "tabla-riesgo") : null);
  }
  pintar();
  const porNivel = data.niveles.map((n) => tarjeta(num(data.filas.filter((f) => f.nivel === n.nivel).length, 0), n.nivel));
  return h("div", {},
    h("div", { class: "tarjetas" }, porNivel),
    data.modo_impacto === "criticos" ? h("p", { class: "sub" }, t("El impacto se mide contra los equipos críticos marcados en el escritorio.")) : null,
    data.grafo_disponible === false ? aviso("error", t("No se pudo construir el grafo: el impacto usa un valor neutro (50).")) : null,
    h("div", { class: "arbol-barra" }, filtroNivel, filtroTexto), cuerpo);
}

async function riesgo({ rpc, gen }) {
  const area = h("div", {}), estado = h("p", { class: "sub", "aria-live": "polite" });
  const boton = h("button", { type: "button", class: "primario", onclick: calcular }, t("Calcular IRF"));
  function mostrar(data, cacheado) {
    area.replaceChildren(tablaRiesgo(data));
    estado.textContent = t("Calculado en {s} s", { s: num(data.calculo_ms / 1000) }) + (cacheado ? " · " + t("resultado guardado en memoria") : "");
    boton.textContent = t("Recalcular");
  }
  async function calcular() {
    boton.disabled = true; estado.textContent = t("Calculando… puede tardar unos segundos.");
    try {
      const data = await rpc.llamar("riesgo_irf");
      cacheRiesgo = { gen, data }; mostrar(data, false);
    } catch (e) { estado.textContent = ""; throw e; }
    finally { boton.disabled = false; }
  }
  if (cacheRiesgo?.gen === gen) mostrar(cacheRiesgo.data, true);
  return marco("riesgo",
    h("p", { class: "sub" }, t("Índice de Riesgo de Falla: probabilidad (edad, uso, historial) × impacto (fracción del parque que queda sin señal). Se calcula acá, sin guardar nada en la base.")),
    h("p", { class: "acciones" }, boton), estado, area);
}

// ── Diagnóstico de falla ─────────────────────────────────────────────────────
const ESTADO_RESP = { SI: ["con-senal", "Hay señal"], NO: ["sin-senal", "No hay señal"], NO_SE: ["no-se", "No sé"] };

async function elegirEquipoDiag(rpc) {
  const items = await rpc.llamar("equipos_lista");
  return marco("diagnostico",
    h("p", { class: "sub" }, t("Elegí el equipo donde falta la señal y después el conector donde lo notás (el síntoma).")),
    selector({ items, nombre: TIPOS.equipo.nombre, texto: TIPOS.equipo.texto, sub: TIPOS.equipo.sub, placeholder: "Buscar equipo…", href: (e) => ruta("analisis", "diagnostico", "equipo", e.id_equipo) }));
}

async function elegirConectorDiag(rpc, id) {
  const e = await rpc.llamar("conectores_de_equipo", { id_equipo: Number(id) });
  return marco("diagnostico",
    h("p", { class: "volver" }, enlace(ruta("analisis", "diagnostico"), "← " + t("Elegir otro equipo"))),
    h("h3", {}, t("¿En qué conector de «{n}» falta la señal?", { n: e.nombre })),
    e.conectores.length ? h("ul", { class: "elegir-equipo" }, e.conectores.map((c) => h("li", {},
      enlace(ruta("analisis", "diagnostico", c.id_conector), c.nombre || "#" + c.id_conector), " ",
      h("span", { class: "sub" }, [c.tipo_conector, c.n_conexiones ? t("{n} conexiones", { n: c.n_conexiones }) : t("Sin conexión")].filter(Boolean).join(" · ")))))
      : h("p", { class: "sub" }, t("Este equipo no tiene conectores.")));
}

async function sesionDiagnostico(rpc, idConector) {
  const est = { ramas: {}, respuestas: [], manual: null };
  const cont = h("div", {});
  let datos;
  const nombrePaso = (p) => [enlace(ruta("equipos", p.id_equipo), p.equipo || "#" + p.id_equipo), " / ", enlace(ruta("conectores", p.id_conector), p.nombre)];
  const textoPaso = (p) => `${p.equipo} / ${p.nombre}`;

  async function actualizar(cambio) {           // aplica el cambio de estado y vuelve a consultar; si falla, lo deshace
    const antes = JSON.stringify(est);
    cambio();
    try { datos = await rpc.llamar("diagnostico", { id_conector: idConector, ramas: est.ramas, respuestas: est.respuestas }); }
    catch (e) { Object.assign(est, JSON.parse(antes)); throw e; }
    pintar();
  }
  const responder = (idx, r) => actualizar(() => { est.respuestas.push([idx, r]); est.manual = null; });

  function pintar() {
    const ses = datos.sesion, pasos = datos.pasos, ultima = new Map(ses ? ses.historial.map(([i, r]) => [i, r]) : []);
    const lista = h("ol", { class: "cadena-diag" }, pasos.map((p, i) => {
      const r = ultima.get(i), [clase, texto] = r ? ESTADO_RESP[r] : [null, null];
      const vigente = ses && i >= ses.lo && i <= ses.hi && !ses.convergido;
      return h("li", { class: ["paso", clase, vigente ? "vigente" : null, i === 0 ? "sintoma" : null].filter(Boolean).join(" ") },
        nombrePaso(p),
        i === 0 ? h("span", { class: "etiqueta" }, t("síntoma: sin señal")) : null,
        i === pasos.length - 1 && i > 0 ? h("span", { class: "etiqueta" }, t("extremo alcanzado: se asume con señal")) : null,
        p.es_punto_test ? h("span", { class: "etiqueta" }, "🔎 " + t("punto de test")) : null,
        texto ? h("span", { class: "etiqueta " + clase }, t(texto)) : null);
    }));

    const bloques = [h("p", { class: "sub" }, t("Cadena hacia el origen") + ": " + datos.motivo_corte), lista];

    if (datos.bifurcacion) {
      const b = datos.bifurcacion;
      bloques.push(h("section", { class: "bloque pregunta" },
        h("h3", {}, t("Hay que elegir una entrada")),
        h("p", {}, t("El equipo «{n}» tiene {c} entradas. ¿Cuál corresponde a lo que falta?", { n: b.equipo, c: b.opciones.length })),
        h("p", { class: "acciones" }, b.opciones.map((o) => h("button", { type: "button", onclick: () => actualizar(() => { est.ramas[b.id_equipo] = o.id_conector; est.respuestas = []; est.manual = null; }) }, o.nombre)))));
    }

    if (ses && ses.convergido) {
      const r = ses.resultado, a = r.sin_senal, b = r.con_senal;
      bloques.push(h("section", { class: "bloque resultado" },
        h("h3", {}, "🎯 " + t("Sospechoso")),
        r.sospechoso === "equipo"
          ? h("p", {}, t("El problema está dentro del equipo «{n}»: hay señal en «{b}» pero no en «{a}». Revisá su conexión interna o su alimentación.", { n: a.equipo, a: a.nombre, b: b.nombre }))
          : h("p", {}, t("El problema está en el cable (o su conexión) entre «{a}» y «{b}».", { a: textoPaso(a), b: textoPaso(b) }))));
    } else if (ses) {
      const idx = est.manual ?? ses.siguiente;
      if (idx != null && idx > ses.lo && idx < ses.hi) {
        const p = pasos[idx];
        bloques.push(h("section", { class: "bloque pregunta" },
          h("h3", {}, t("¿Hay señal en «{n}»?", { n: textoPaso(p) })),
          h("p", { class: "sub" }, t("Medilo con un monitor o analizador en ese punto.")),
          h("p", { class: "acciones" },
            h("button", { type: "button", onclick: () => responder(idx, "SI") }, "✔ " + t("Sí, hay señal")),
            h("button", { type: "button", onclick: () => responder(idx, "NO") }, "✖ " + t("No hay señal")),
            h("button", { type: "button", onclick: () => responder(idx, "NO_SE") }, "? " + t("No sé")))));
      } else {
        const medio = []; for (let i = ses.lo + 1; i < ses.hi; i++) medio.push(i);
        bloques.push(h("section", { class: "bloque pregunta" },
          h("h3", {}, t("Elegí dónde medir")),
          h("p", {}, t("No hay puntos de test marcados en este tramo. Elegí a mano uno de los puntos intermedios:")),
          h("p", { class: "acciones" }, medio.map((i) => h("button", { type: "button", onclick: () => actualizar(() => { est.manual = i; }) }, textoPaso(pasos[i]))))));
      }
    } else {
      bloques.push(aviso("", t("La cadena tiene un solo punto: no hay nada para acotar.")));
    }

    if (ses && (ses.historial.length || Object.keys(est.ramas).length)) {
      bloques.push(h("p", { class: "acciones" },
        ses.historial.length ? h("button", { type: "button", onclick: () => actualizar(() => { est.respuestas.pop(); est.manual = null; }) }, "↶ " + t("Deshacer")) : null,
        h("button", { type: "button", onclick: () => actualizar(() => { est.ramas = {}; est.respuestas = []; est.manual = null; }) }, t("Reiniciar"))));
    }
    cont.replaceChildren(...bloques);
  }

  datos = await rpc.llamar("diagnostico", { id_conector: Number(idConector) });
  idConector = Number(idConector);
  const o = datos.pasos[0];
  pintar();
  return marco("diagnostico",
    h("p", { class: "volver" }, enlace(ruta("analisis", "diagnostico", "equipo", o.id_equipo), "← " + t("Elegir otro conector"))),
    h("h3", {}, t("Diagnóstico desde «{n}»", { n: textoPaso(o) })), cont);
}

async function diagnostico({ rpc, args }) {
  const [a, b] = args;
  if (a === "equipo" && esId(b)) return elegirConectorDiag(rpc, b);
  if (esId(a)) return sesionDiagnostico(rpc, a);
  return elegirEquipoDiag(rpc);
}

// ── Linter de topología ──────────────────────────────────────────────────────
const destinos = (lista) => (lista || []).map((d, i) => [i ? ", " : "", enlace(ruta("equipos", d.id_equipo), d.nombre || "#" + d.id_equipo)]);
const colEquipoConector = (f) => celda(enlace(ruta("equipos", f.id_equipo), f.equipo), " / ", enlace(ruta("conectores", f.id_conector), f.nombre));
const colRiesgo = (f) => h("td", { class: "n" }, f.riesgo == null ? "—" : num(f.riesgo), " ", f.nivel ? insignia(f.nivel) : "");

const REGLAS = {
  fuera_de_patchera: { titulo: "Fuera de patchera", desc: "Equipos con cables documentados, pero ninguno llega a una patchera: cableado directo.",
    cab: ["Equipo", "Riesgo"], fila: (f) => h("tr", {}, celda(enlace(ruta("equipos", f.id_equipo), f.nombre)), colRiesgo(f)) },
  fuera_de_distribuidor: { titulo: "Fuera de distribuidor", desc: "Equipos cuyas salidas no entran directo a un distribuidor (ni pasando solo por patcheras).",
    cab: ["Equipo", "Riesgo"], fila: (f) => h("tr", {}, celda(enlace(ruta("equipos", f.id_equipo), f.nombre)), colRiesgo(f)) },
  loop_en_uso: { titulo: "Loop en uso", desc: "Salidas loop-through con un cable real conectado.",
    cab: ["Salida loop", "Origen", "Cables", "Destinos", "Riesgo"],
    fila: (f) => h("tr", {}, colEquipoConector(f), celda(f.nombre_origen || ""), h("td", { class: "n" }, num(f.n_cables, 0)), celda(destinos(f.destinos)), colRiesgo(f)) },
  referencia_en_cascada: { titulo: "Referencia en cascada", desc: "Equipos que re-emiten la referencia sin ser distribuidores de sincronismo: si caen, arrastran lo que cuelga de ellos.",
    cab: ["Salida de referencia", "Tipo de equipo", "Cables", "Destinos", "Impacto", "Riesgo"],
    fila: (f) => h("tr", {}, colEquipoConector(f), celda(f.tipo_equipo || ""), h("td", { class: "n" }, num(f.n_cables, 0)), celda(destinos(f.destinos)), celdaNum(f.impacto), colRiesgo(f)) },
};

async function topologia({ rpc }) {
  const d = await rpc.llamar("linter_topologia");
  const total = d.reglas.reduce((s, r) => s + r.hallazgos.length, 0);
  return marco("topologia",
    h("p", { class: "sub" }, t("Reglas de diseño que se revisan solas sobre los datos cargados. Cada lista va ordenada por riesgo.")),
    !d.con_riesgo && total ? aviso("", t("La base no tiene riesgo calculado: los hallazgos no están priorizados. Calculalo en el escritorio con «Recalcular riesgo».")) : null,
    d.reglas.map((r) => {
      const R = REGLAS[r.id];
      return h("section", { class: "bloque regla", "data-regla": r.id },
        h("h3", {}, (r.hallazgos.length ? "⚠️ " : "✔ ") + t(R.titulo) + " (" + r.hallazgos.length + ")"),
        h("p", { class: "sub" }, t(R.desc)),
        r.hallazgos.length ? tabla(R.cab, r.hallazgos.map(R.fila)) : h("p", { class: "sub" }, t("Sin hallazgos.")));
    }));
}

const SUBVISTAS = { impacto, riesgo, diagnostico, topologia };

// ctx = { rpc, args, gen }; args = ["impacto", "equipo", "12"], ["riesgo"], …
export function vistaAnalisis(ctx) {
  const [sub = "impacto", ...resto] = ctx.args ?? [];
  const f = SUBVISTAS[sub];
  if (!f) return marco(null, aviso("error", t("Pantalla desconocida") + ": " + sub));
  return f({ ...ctx, args: resto });
}
