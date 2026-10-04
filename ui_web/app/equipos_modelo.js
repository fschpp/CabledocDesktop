// Equipos y conectores (B.4) — lógica pura, sin DOM ni i18n (la traducción entra como parámetro `tr`): cómo se arman los
// formularios a partir del esquema que manda el bridge (equipos_web.py), las filas de la plantilla de la alta rápida y
// los nombres que se usan en avisos y diálogos.
// Las reglas de validación NO se repiten acá: salen del `esquema` de equipo_formulario / conector_formulario (la única
// fuente); la UI solo agrega etiquetas y ayudas.
export { detalleUsos } from "./catalogos_modelo.js";

export const ETIQUETA_CAMPO = {
  nombre: "Nombre", id_tipo_equipo: "Tipo de equipo", id_marca: "Marca", modelo: "Modelo", num_inventario: "N.º de inventario",
  num_serie: "N.º de serie", fecha_fabricacion: "Fecha de fabricación", es_equipo_usado: "Equipo usado",
  es_modulo_de_frame: "Es módulo de frame", critico: "⭐ Equipo crítico de la cadena", ancho_mm: "Ancho (mm)", alto_mm: "Alto (mm)",
  profundidad_mm: "Profundidad (mm)", path_manual: "Manual (ruta del archivo)", configuraciones: "Configuraciones",
  id_tipo_conector: "Tipo de conector", id_tipo_ficha: "Ficha eléctrica", modo_balance: "Balance", modo_canal: "Canal",
  id_senal: "Señal", id_formato: "Formato de señal",
};
const AYUDA_CAMPO = {
  es_modulo_de_frame: "Marcalo si el equipo solo tiene sentido instalado en un slot de un frame (no se ofrece como equipo suelto).",
  critico: "Con al menos un equipo crítico en la base, el factor Impacto del riesgo mide solo contra ese conjunto en vez de todo el parque.",
  fecha_fabricacion: "Texto libre (ej. 2019 o 2019-05).",
  num_inventario: "Texto libre.",
  path_manual: "Solo se guarda la ruta: los manuales no se cargan en el navegador.",
  id_tipo_ficha: "Qué ficha es eléctricamente este conector (de ahí salen el balance y el canal por defecto).",
  modo_balance: "Vacío = el que trae la ficha.", modo_canal: "Vacío = el que trae la ficha.",
  id_formato: "Solo se puede elegir junto con una señal.",
};
// Campos de la alta rápida (el resto se completa editando el equipo).
export const CAMPOS_ALTA_RAPIDA = ["nombre", "id_tipo_equipo", "id_marca", "modelo", "num_inventario", "num_serie"];

// Campos de abrirFormulario() a partir del esquema del bridge. `solo` = lista de nombres a incluir (alta rápida).
export function camposDesdeEsquema(esquema, tr = (x) => x, { solo = null } = {}) {
  return esquema.filter((e) => !solo || solo.includes(e.nombre)).map((e) => {
    const base = { nombre: e.nombre, etiqueta: tr(ETIQUETA_CAMPO[e.nombre] || e.nombre), requerido: e.requerido,
      ayuda: AYUDA_CAMPO[e.nombre] ? tr(AYUDA_CAMPO[e.nombre]) : undefined };
    if (e.tipo === "bool") return { ...base, tipo: "checkbox" };
    if (e.tipo === "select") return { ...base, tipo: "select", opciones: (e.opciones || []).map((o) => ({ valor: o.valor, etiqueta: o.etiqueta })) };
    if (e.tipo === "numero" || e.tipo === "entero") return { ...base, tipo: e.tipo, min: e.minimo };
    if (e.tipo === "texto_largo") return { ...base, tipo: "texto_largo", largoMax: e.largo, filas: 6 };
    return { ...base, tipo: "texto", largoMax: e.largo };
  });
}

// ── Plantilla de conectores de la alta rápida ────────────────────────────────

export const MAX_POR_FILA = 99;                                     // igual que equipos_web.MAX_POR_FILA
export const claveFila = (f) => `q_${f.id_tipo_conector}_${f.direccion}`;     // nombre del campo = clave de error del bridge
export const etiquetaFila = (f) => `${f.direccion} · ${f.tipo_conector}`;

// Un campo numérico por fila (las de la plantilla del tipo, con su cantidad, van primero: así las manda el bridge).
export const camposPlantilla = (filas) => filas.map((f) => ({ nombre: claveFila(f), etiqueta: etiquetaFila(f), tipo: "entero", min: 0, max: MAX_POR_FILA,
  valorInicial: f.cantidad || 0 }));

// De los valores del formulario a la lista que espera equipo_alta_rapida (todas las filas; el bridge ignora las de cantidad 0).
export const conectoresDesdeValores = (filas, valores) => filas.map((f) => ({ id_tipo_conector: f.id_tipo_conector, direccion: f.direccion,
  cantidad: Number(valores[claveFila(f)] ?? 0) || 0 }));

export const totalConectores = (filas, valores) => conectoresDesdeValores(filas, valores).reduce((s, c) => s + c.cantidad, 0);

// Nombres con los que se nombran el equipo y el conector en avisos y diálogos.
export const nombreEquipo = (e) => e?.nombre || "#" + (e?.id_equipo ?? e?.id ?? "?");
export const nombreConector = (c) => c?.nombre || "#" + (c?.id_conector ?? c?.id ?? "?");

// Extremo desconectado (equipo FANTASMA): solo se pregunta el lado cuando no se puede inferir del otro extremo del cable.
// A = la punta que falta es la de un conector OUT (origen); B = la de un conector IN (destino).
export const camposLado = (tr = (x) => x) => [{ nombre: "lado", etiqueta: tr("Lado del extremo desconectado"), tipo: "select", requerido: true,
  ayuda: tr("Se crea un equipo FANTASMA con un conector ya conectado a este cable: OUT en el lado A, IN en el lado B."),
  opciones: [{ valor: "A", etiqueta: tr("Lado A (conector OUT)") }, { valor: "B", etiqueta: tr("Lado B (conector IN)") }] }];

// Los valores del formulario de equipo viajan tal cual. En la alta rápida solo viajan los campos de CAMPOS_ALTA_RAPIDA.
export const soloRapida = (valores) => Object.fromEntries(CAMPOS_ALTA_RAPIDA.map((k) => [k, valores[k] ?? null]));
