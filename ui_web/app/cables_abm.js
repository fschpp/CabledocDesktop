// ABM de cables y conexiones (B.3): las acciones que usan las fichas y la lista de cables. Cada una abre el diálogo de B.1,
// llama al bridge (cables_web.py; las reglas de validación viven allá), avisa con «Deshacer» y repinta la pantalla.
//   · Cable: alta, alta rápida «temporal», edición, baja y fusión de dos cables.
//   · Conexión (un extremo de un cable): alta, edición y baja; el conector se elige equipo → conector.
// Deshacer (pila en memoria de B.1): alta → baja (solo si sigue sin uso); edición → los valores anteriores; baja → reinserta con el
// mismo id SOLO si no arrastró nada (lo que se llevó la baja ya no se puede reconstruir); fusión → devuelve las mismas conexiones.
// Cada escritura la persiste el worker (syncfs) antes de contestar.
import { h, $ } from "./dom.js";
import { t } from "./i18n.js";
import { ErrorBridge } from "./errores.js";
import { abrirFormulario, confirmar, ofrecerDeshacer, crearPilaDeshacer, ErrorFormulario } from "./formulario.js";
import { camposDesdeEsquema, opcionesConectores, nombreCable, camposFusion, argumentosFusion, sinEquipo, textoAviso, detalleUsos } from "./cables_modelo.js";

const pila = crearPilaDeshacer(10);

// El shell repinta solo si cambió el tamaño de la base: una escritura que no lo cambia no se vería. Repintar a mano = reenviar hashchange.
export const repintar = () => window.dispatchEvent(new window.Event("hashchange"));
export const irA = (hash) => { if (location.hash === hash) repintar(); else location.hash = hash; };

// El bridge devuelve los errores de validación como ErrorBridge con `campos`; el formulario espera ErrorFormulario.
export const conCampos = (rpc) => async (fn, a) => {
  try { return await rpc.llamar(fn, a); }
  catch (e) { if (e instanceof ErrorBridge && e.campos && Object.keys(e.campos).length) throw new ErrorFormulario(e.message, e.campos); throw e; }
};

// Aviso informativo que no bloquea (p. ej. «el conector ya tenía otra conexión»).
export function avisar(texto) {
  const cont = $("toasts"); if (!cont) return;
  const el = h("div", { class: "toast aviso", role: "status" }, h("span", {}, texto), h("button", { type: "button", "aria-label": t("Cerrar"), onclick: () => el.remove() }, "✕"));
  cont.append(el); setTimeout(() => el.remove(), 10000);
}

// Detalle de lo que arrastra una baja, para el diálogo de confirmación.
const listaUsos = (usos, sinUsos = "No tiene conexiones ni otros datos asociados.") => {
  const det = detalleUsos(usos, t);
  return det.length
    ? [h("p", {}, t("Al eliminarlo:")), h("ul", { class: "catalogos-usos" }, det.map((u) => h("li", {}, `${u.n} ${u.tabla} — ` + (u.efecto === "borra" ? t("también se eliminarán") : t("quedarán sin este valor")))))]
    : h("p", { class: "sub" }, t(sinUsos));
};

// ── Cables ───────────────────────────────────────────────────────────────────

export async function altaCable(rpc) {
  const llamar = conCampos(rpc), form = await rpc.llamar("cable_formulario");
  const r = await abrirFormulario({ titulo: t("Nuevo cable"), campos: camposDesdeEsquema(form.esquema, t),
    enviar: (valores) => llamar("cable_alta", { valores }) });
  if (!r) return;
  const { id, codigo } = r.resultado, nombre = codigo || "#" + id;
  ofrecerDeshacer(pila, t("Se agregó el cable «{nombre}»", { nombre }), async () => {
    await rpc.llamar("cable_baja", { id, solo_si_sin_uso: true }); irA("#/cables");
  });
  irA("#/cables/" + id);
}

export async function cableTemporal(rpc) {
  const { id, codigo } = await rpc.llamar("cable_temporal");
  ofrecerDeshacer(pila, t("Cable temporal creado: {codigo}", { codigo }), async () => {
    await rpc.llamar("cable_baja", { id, solo_si_sin_uso: true }); irA("#/cables");
  });
  irA("#/cables/" + id);
}

export async function editarCable(rpc, id) {
  const llamar = conCampos(rpc), form = await rpc.llamar("cable_formulario", { id_cable: id });
  const r = await abrirFormulario({ titulo: t("Editar cable"), campos: camposDesdeEsquema(form.esquema, t, { fila: form.valores }), valores: form.valores,
    enviar: (valores) => llamar("cable_modificar", { id, valores }) });
  if (!r) return;
  const { anterior, codigo } = r.resultado, nombre = codigo || "#" + id;
  ofrecerDeshacer(pila, t("Se modificó el cable «{nombre}»", { nombre }), async () => {
    await rpc.llamar("cable_modificar", { id, valores: anterior }); repintar();
  });
  repintar();
}

export async function eliminarCable(rpc, k) {
  const { usos } = await rpc.llamar("cable_usos", { id_cable: k.id_cable }), nombre = nombreCable(k);
  const cuerpo = h("div", {}, h("p", {}, t("¿Eliminar el cable «{nombre}»?", { nombre })), listaUsos(usos));
  if (!(await confirmar({ titulo: t("Eliminar cable"), mensaje: cuerpo, textoOk: "Eliminar", peligro: true }))) return;
  const r = await rpc.llamar("cable_baja", { id: k.id_cable });
  if (!r.usos.length) {                                         // sin nada arrastrado: se puede reinsertar tal cual
    ofrecerDeshacer(pila, t("Se eliminó el cable «{nombre}»", { nombre }), async () => {
      await rpc.llamar("cable_restaurar", { id: r.id, valores: r.anterior, interno: r.interno, id_cable_fusionado: r.id_cable_fusionado }); repintar();
    });
  } else avisar(t("Se eliminó el cable «{nombre}»", { nombre }));
  irA("#/cables");
}

// `a` y `b` = los dos cables elegidos ({id_cable, codigo}); `a` es el principal por defecto.
export async function fusionarCables(rpc, a, b) {
  const llamar = conCampos(rpc);
  let hecho = null;
  const r = await abrirFormulario({ titulo: t("Fusionar cables"), campos: camposFusion(a, b, t),
    descripcion: t("Las conexiones del cable secundario pasarán al principal y el principal tomará el código y el estado que elijas."), textoEnviar: "Confirmar fusión",
    enviar: async (valores) => { const x = argumentosFusion(a, b, valores); hecho = x; return llamar("cable_fusionar", x.args); } });
  if (!r) return;
  const f = r.resultado, nombre = f.codigo, otro = nombreCable(hecho.secundario);          // el principal ya tiene su código definitivo
  ofrecerDeshacer(pila, t("Fusión: «{otro}» pasó a «{nombre}»", { otro, nombre }), async () => {
    await rpc.llamar("cable_fusion_deshacer", { id_principal: f.principal, id_secundario: f.secundario, anterior: f.anterior, conexiones: f.conexiones }); repintar();
  });
  repintar();
}

// ── Conexiones ───────────────────────────────────────────────────────────────

// Carga de las opciones de conector al cambiar el equipo (select encadenado de B.1).
const cargarConectores = (rpc) => async (id_equipo) => (id_equipo == null ? [] : opcionesConectores((await rpc.llamar("conectores_de_equipo", { id_equipo })).conectores));

const mostrarAvisos = (avisos) => (avisos || []).forEach((a) => avisar(textoAviso(a, t)));

// Alta de una conexión. Se puede prefijar el cable (desde su ficha) o el conector (desde su ficha): el prefijado queda fijo.
export async function altaConexion(rpc, { id_cable = null, id_conector = null } = {}) {
  const llamar = conCampos(rpc), form = await rpc.llamar("conexion_formulario", { id_cable, id_conector });
  const bloquear = [id_cable != null ? "id_cable" : null, id_conector != null ? "id_equipo" : null, id_conector != null ? "id_conector" : null].filter(Boolean);
  const r = await abrirFormulario({ titulo: t("Nueva conexión"), campos: camposDesdeEsquema(form.esquema, t, { conexion: true, bloquear, cargarConectores: cargarConectores(rpc) }),
    valores: form.valores, enviar: (valores) => llamar("conexion_alta", sinEquipo(valores)) });
  if (!r) return;
  const { id, avisos } = r.resultado;
  ofrecerDeshacer(pila, t("Se agregó la conexión #{id}", { id }), async () => {
    await rpc.llamar("conexion_baja", { id, solo_si_sin_uso: true }); repintar();
  });
  mostrarAvisos(avisos);
  repintar();
}

export async function editarConexion(rpc, id) {
  const llamar = conCampos(rpc), form = await rpc.llamar("conexion_formulario", { id_conexion: id });
  const r = await abrirFormulario({ titulo: t("Editar conexión"), campos: camposDesdeEsquema(form.esquema, t, { fila: form.valores, conexion: true, cargarConectores: cargarConectores(rpc) }),
    valores: form.valores, enviar: (valores) => llamar("conexion_modificar", { id, valores: sinEquipo(valores) }) });
  if (!r) return;
  const { anterior, avisos } = r.resultado;
  ofrecerDeshacer(pila, t("Se modificó la conexión #{id}", { id }), async () => {
    await rpc.llamar("conexion_modificar", { id, valores: anterior }); repintar();
  });
  mostrarAvisos(avisos);
  repintar();
}

// `etiqueta` = cómo se nombra la conexión en el diálogo (p. ej. «C-001 → CAM 2 / IN 1»).
export async function eliminarConexion(rpc, id, etiqueta) {
  const { usos } = await rpc.llamar("conexion_usos", { id_conexion: id });
  const cuerpo = h("div", {}, h("p", {}, t("¿Quitar la conexión «{etiqueta}»?", { etiqueta })), listaUsos(usos, "No forma parte de ninguna extensión."));
  if (!(await confirmar({ titulo: t("Quitar conexión"), mensaje: cuerpo, textoOk: "Quitar", peligro: true }))) return;
  const r = await rpc.llamar("conexion_baja", { id });
  if (!r.usos.length) {
    ofrecerDeshacer(pila, t("Se quitó la conexión «{etiqueta}»", { etiqueta }), async () => {
      await rpc.llamar("conexion_restaurar", { id: r.id, valores: r.anterior, interno: r.interno }); repintar();
    });
  } else avisar(t("Se quitó la conexión «{etiqueta}»", { etiqueta }));
  repintar();
}
