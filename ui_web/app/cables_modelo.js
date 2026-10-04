// Cables y conexiones (B.3) — lógica pura, sin DOM ni i18n (la traducción entra como parámetro `tr`): cómo se arman los
// formularios a partir del esquema que manda el bridge (cables_web.py), la fusión y el texto de los avisos.
// Las reglas de validación NO se repiten acá: salen del `esquema` de cable_formulario / conexion_formulario (la única
// fuente); la UI solo agrega etiquetas y ayudas.
export { detalleUsos } from "./catalogos_modelo.js";

export const ETIQUETA_CAMPO = {
  codigo: "Código", estado: "Estado", id_tipo_cable: "Tipo de cable", id_tipo_ficha: "Tipo de ficha", longitud: "Longitud",
  unidad_longitud: "Unidad de longitud", metraje_ext1: "Metraje extremo 1", metraje_ext2: "Metraje extremo 2", unidad_metraje: "Unidad de metraje",
  ancho_banda_override: "Ancho de banda (override, MHz)", es_armado_correcto: "¿Armado correcto?", detalle_armado: "Detalle del armado",
  notas_relevamiento: "Notas de relevamiento",
  id_cable: "Cable", id_equipo: "Equipo", id_conector: "Conector",
  principal: "Cable principal", codigo_definitivo: "Código definitivo", estado_final: "Estado final",
};
const ETIQUETA_FICHA_CONEXION = "Ficha del cable en esta punta";
const AYUDA_CAMPO = {
  codigo: "Opcional. Debe ser único. «⚡ Temporal» en la lista genera uno automático (SIN ETIQUETA NNNN).",
  ancho_banda_override: "Vacío = usar el default de su tipo de cable. Cargar solo si ESTE cable no representa a su tipo nominal (ej. un patchcord viejo o degradado).",
  es_armado_correcto: "Vacío = no verificado.",
  id_equipo: "Solo sirve para elegir el conector: no se guarda.",
  id_tipo_ficha_conexion: "Qué ficha es físicamente el extremo del cable que llega acá (ej. XLR3 macho, TS); puede ser distinta de la que espera el jack del equipo.",
};
const VALOR_INICIAL = { estado: "VERIFICADO" };
const TRADUCIR_OPCIONES = new Set(["es_armado_correcto"]);      // estados y nombres de catálogo se muestran tal cual (como en el desktop)

// Campos de abrirFormulario() a partir del esquema. `fila` = valores que se editan (null en un alta).
// `conexion` = el formulario es de una conexión (cambia la etiqueta de id_tipo_ficha). `bloquear` = nombres de campos de solo lectura.
export function camposDesdeEsquema(esquema, tr = (x) => x, { fila = null, conexion = false, bloquear = [], cargarConectores = null } = {}) {
  return esquema.map((e) => {
    const clave = e.nombre === "id_tipo_ficha" && conexion ? "id_tipo_ficha_conexion" : e.nombre;
    const base = { nombre: e.nombre, etiqueta: tr(e.nombre === "id_tipo_ficha" && conexion ? ETIQUETA_FICHA_CONEXION : ETIQUETA_CAMPO[e.nombre] || e.nombre), requerido: e.requerido,
      ayuda: AYUDA_CAMPO[clave] ? tr(AYUDA_CAMPO[clave]) : undefined, soloLectura: bloquear.includes(e.nombre) || undefined };
    if (e.nombre in VALOR_INICIAL && !fila) base.valorInicial = VALOR_INICIAL[e.nombre];
    if (e.tipo === "select") {
      const c = { ...base, tipo: "select", opciones: e.opciones.map((o) => ({ valor: o.valor, etiqueta: TRADUCIR_OPCIONES.has(e.nombre) ? tr(o.etiqueta) : o.etiqueta })) };
      if (e.depende_de && cargarConectores) { c.dependeDe = e.depende_de; c.cargarOpciones = cargarConectores; }
      return c;
    }
    if (e.tipo === "numero" || e.tipo === "entero") return { ...base, tipo: e.tipo, min: e.minimo };
    return { ...base, tipo: e.tipo, largoMax: e.largo };
  });
}

// Texto de una opción de conector: «OUT 1 · BNC (2)» (el número entre paréntesis = conexiones que ya tiene). Igual a cables_web._opciones_conectores.
export const etiquetaConector = (c) => [c.nombre || "#" + c.id_conector, c.tipo_conector].filter(Boolean).join(" · ") + (c.n_conexiones ? ` (${c.n_conexiones})` : "");
export const opcionesConectores = (conectores) => (conectores || []).map((c) => ({ valor: c.id_conector, etiqueta: etiquetaConector(c) }));

// Nombre con el que se nombra un cable en avisos y diálogos.
export const nombreCable = (k) => k?.codigo || "#" + (k?.id_cable ?? k?.id ?? "?");

// Formulario de fusión: el principal se elige entre los dos cables; el código arranca con el del principal (como el desktop).
export function camposFusion(a, b, tr = (x) => x) {
  return [
    { nombre: "id_principal", etiqueta: tr(ETIQUETA_CAMPO.principal), tipo: "select", requerido: true, valorInicial: a.id_cable,
      opciones: [a, b].map((k) => ({ valor: k.id_cable, etiqueta: `${nombreCable(k)} (ID ${k.id_cable})` })),
      ayuda: tr("Las conexiones del otro cable pasan a este. El otro queda marcado como FUSIONADO (no se borra).") },
    { nombre: "codigo", etiqueta: tr(ETIQUETA_CAMPO.codigo_definitivo), tipo: "texto", requerido: true, largoMax: 120, valorInicial: a.codigo || "" },
    { nombre: "estado", etiqueta: tr(ETIQUETA_CAMPO.estado_final), tipo: "select", requerido: true, valorInicial: "VERIFICADO",
      opciones: ["VERIFICADO", "TEMPORAL"].map((e) => ({ valor: e, etiqueta: e })) },
  ];
}

// De los valores del formulario de fusión a los argumentos de cable_fusionar: el secundario es el otro de los dos.
export function argumentosFusion(a, b, valores) {
  const principal = Number(valores.id_principal) === a.id_cable ? a : b, secundario = principal === a ? b : a;
  return { principal, secundario, args: { id_principal: principal.id_cable, id_secundario: secundario.id_cable, codigo: valores.codigo, estado: valores.estado } };
}

// El formulario de conexión incluye `id_equipo` (solo para elegir el conector): no viaja al bridge.
export const sinEquipo = ({ id_equipo, ...resto }) => resto;

// Selección de dos cables para fusionar, en orden de clic (el primero es el principal por defecto). Máximo 2: al marcar un
// tercero sale el más viejo. Devuelve una lista nueva.
export function alternarSeleccion(sel, id) {
  if (sel.includes(id)) return sel.filter((x) => x !== id);
  return [...sel, id].slice(-2);
}

// Texto de un aviso del bridge ({clave, vars}).
export const textoAviso = (a, tr = (x) => x) => tr(a.clave, a.vars);
