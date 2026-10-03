// Formularios (B.1) — lógica pura, sin DOM ni i18n: valores iniciales, normalización, validación y pila de "deshacer".
// Un campo se describe así (solo `nombre` y `tipo` son obligatorios):
//   { nombre, etiqueta, tipo: "texto"|"texto_largo"|"numero"|"entero"|"fecha"|"select"|"checkbox",
//     requerido, valorInicial, ayuda, soloLectura,
//     min, max            (numero/entero: rango; fecha: "AAAA-MM-DD"),
//     largoMax, patron    (texto: largo y RegExp/string; si falla → "Formato no válido", o `patronMensaje`),
//     opciones: [{ valor, etiqueta }]   (select; el valor puede ser número o texto),
//     validar: (valor, valores) => string | null   (regla propia; el string es una clave de i18n) }
// Los mensajes de error se devuelven como { clave, vars }: la traducción la hace la UI con t(clave, vars).

export const TIPOS = ["texto", "texto_largo", "numero", "entero", "fecha", "select", "checkbox"];

// Error que `enviar` puede lanzar para marcar campos concretos (p. ej. "ya existe un equipo con ese nombre").
//   throw new ErrorFormulario("Hay datos que corregir", { nombre: "Ya existe" })
export class ErrorFormulario extends Error {
  constructor(mensaje, campos = {}) { super(mensaje); this.name = "ErrorFormulario"; this.campos = campos; }
}

const esVacio = (v) => v == null || (typeof v === "string" && v.trim() === "");
const RE_NUM = /^-?\d+([.,]\d+)?$/, RE_ENT = /^-?\d+$/;

export function fechaValida(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s ?? ""));
  if (!m) return false;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
}

// Valores que se muestran al abrir: lo recibido en `dados` (aunque sea null → vacío), si no `valorInicial`, si no vacío.
export function valoresIniciales(campos, dados = {}) {
  const out = {};
  for (const c of campos) {
    const v = c.nombre in dados ? dados[c.nombre] : c.valorInicial;
    out[c.nombre] = c.tipo === "checkbox" ? Boolean(v) : v == null ? "" : v;
  }
  return out;
}

// Del valor "crudo" del control al valor para enviar. Vacío → null (texto incluido, para no mezclar "" con NULL en la base).
// Lo que no se puede convertir (un número mal escrito) queda como texto: lo rechaza `validarCampo`.
export function normalizarCampo(c, bruto) {
  if (c.tipo === "checkbox") return Boolean(bruto);
  if (esVacio(bruto)) return null;
  if (c.tipo === "numero" || c.tipo === "entero") {
    const s = String(bruto).trim();
    return (c.tipo === "entero" ? RE_ENT : RE_NUM).test(s) ? Number(s.replace(",", ".")) : s;
  }
  if (c.tipo === "select") {
    const op = (c.opciones || []).find((o) => String(o.valor) === String(bruto));
    return op ? op.valor : bruto;                       // conserva el tipo original (número) de la opción
  }
  return typeof bruto === "string" ? bruto.trim() : bruto;
}

export function validarCampo(c, valor, todos = {}) {
  const vacio = c.tipo === "checkbox" ? valor !== true : valor == null;
  if (vacio) {
    if (c.requerido) return { clave: "Obligatorio" };
  } else {
    const num = c.tipo === "numero" || c.tipo === "entero";
    if (num) {
      if (typeof valor !== "number" || !Number.isFinite(valor)) return { clave: c.tipo === "entero" ? "Debe ser un número entero" : "Debe ser un número" };
      if (c.min != null && valor < c.min) return { clave: "Mínimo {min}", vars: { min: c.min } };
      if (c.max != null && valor > c.max) return { clave: "Máximo {max}", vars: { max: c.max } };
    } else if (c.tipo === "fecha") {
      if (!fechaValida(valor)) return { clave: "Debe ser una fecha válida (AAAA-MM-DD)" };
      if (c.min != null && valor < c.min) return { clave: "Mínimo {min}", vars: { min: c.min } };
      if (c.max != null && valor > c.max) return { clave: "Máximo {max}", vars: { max: c.max } };
    } else if (c.tipo === "select") {
      if (!(c.opciones || []).some((o) => String(o.valor) === String(valor))) return { clave: "Elegí una opción válida" };
    } else if (c.tipo === "texto" || c.tipo === "texto_largo") {
      if (c.largoMax != null && valor.length > c.largoMax) return { clave: "Máximo {n} caracteres", vars: { n: c.largoMax } };
      if (c.patron && !new RegExp(c.patron).test(valor)) return { clave: c.patronMensaje || "Formato no válido" };
    }
  }
  if (c.validar) { const m = c.validar(valor, todos); if (m) return { clave: String(m) }; }
  return null;
}

// Valida todo el formulario. `brutos` = { nombre: valor del control }. Devuelve { valores, errores: { nombre: {clave, vars} }, ok }.
// Los campos de solo lectura se devuelven pero no se validan (el usuario no puede corregirlos).
export function validar(campos, brutos) {
  const valores = {}, errores = {};
  for (const c of campos) valores[c.nombre] = normalizarCampo(c, brutos[c.nombre]);
  for (const c of campos) {
    if (c.soloLectura) continue;
    const e = validarCampo(c, valores[c.nombre], valores);
    if (e) errores[c.nombre] = e;
  }
  return { valores, errores, ok: Object.keys(errores).length === 0 };
}

export const hayCambios = (campos, a, b) => campos.some((c) => String(normalizarCampo(c, a[c.nombre])) !== String(normalizarCampo(c, b[c.nombre])));

// Pila de "deshacer simple": cada entrada es { texto, deshacer: async () => … } que revierte UNA acción ya hecha.
// Si revertir falla, la entrada se conserva (se puede reintentar). Es en memoria: no sobrevive a recargar la pestaña.
export function crearPilaDeshacer(max = 10) {
  const items = [];
  return {
    registrar(texto, deshacer) { items.push({ texto, deshacer }); if (items.length > max) items.shift(); },
    hay: () => items.length > 0,
    ultimo: () => (items.length ? items[items.length - 1].texto : null),
    get largo() { return items.length; },
    vaciar() { items.length = 0; },
    async deshacer() {
      const it = items.pop();
      if (!it) return null;
      try { await it.deshacer(); } catch (err) { items.push(it); throw err; }
      return it.texto;
    },
  };
}
