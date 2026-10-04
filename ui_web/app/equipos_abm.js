// ABM de equipos y conectores (B.4): las acciones que usan la pantalla de equipos y las fichas de equipo y de conector. Cada una abre el
// diálogo de B.1, llama al bridge (equipos_web.py; las reglas de validación viven allá), avisa con «Deshacer» y repinta la pantalla.
//   · Equipo: alta, alta rápida (datos + plantilla de conectores en dos pasos), edición y baja.
//   · Conector: alta (desde la ficha del equipo), edición y baja.
//   · Extremo desconectado: desde la ficha de un cable, crea un equipo FANTASMA ya conectado a él (con deshacer).
// Editar NO toca la imagen ni las coordenadas (se editan en B.8). Deshacer: alta → baja (solo si sigue sin uso); edición → los
// valores anteriores; baja → reinserta con el mismo id SOLO si no arrastró nada (lo que se llevó no se puede reconstruir).
// Cada escritura la persiste el worker (syncfs) antes de contestar.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { abrirFormulario, confirmar, ofrecerDeshacer, crearPilaDeshacer } from "./formulario.js";
import { repintar as repintarBase, irA as irABase, conCampos, avisar } from "./cables_abm.js";
import { olvidarArbol } from "./equipos_arbol.js";
import {
  camposDesdeEsquema, CAMPOS_ALTA_RAPIDA, camposPlantilla, conectoresDesdeValores, soloRapida, nombreEquipo, nombreConector, detalleUsos, camposLado,
} from "./equipos_modelo.js";

const pila = crearPilaDeshacer(10);

// El árbol de equipos guarda una copia en memoria por carga de base: una escritura que no cambia el tamaño del .db no la invalidaría.
const repintar = () => { olvidarArbol(); repintarBase(); };
const irA = (hash) => { olvidarArbol(); irABase(hash); };

// Detalle de lo que arrastra una baja, para el diálogo de confirmación. `que` = "equipo" | "conector".
function listaUsos(usos, que) {
  const det = detalleUsos(usos, t);
  if (!det.length) return h("p", { class: "sub" }, t(que === "equipo" ? "No tiene conectores, conexiones ni otros datos asociados." : "No tiene conexiones ni otros datos asociados."));
  const anula = que === "equipo" ? "quedarán sin este equipo" : "quedarán sin este conector";
  return [h("p", {}, t("Al eliminarlo:")), h("ul", { class: "catalogos-usos" },
    det.map((u) => h("li", {}, `${u.n} ${u.tabla} — ` + (u.efecto === "borra" ? t("también se eliminarán") : t(anula)))))];
}

// ── Equipos ──────────────────────────────────────────────────────────────────

export async function altaEquipo(rpc) {
  const llamar = conCampos(rpc), form = await rpc.llamar("equipo_formulario");
  const r = await abrirFormulario({ titulo: t("Nuevo equipo"), campos: camposDesdeEsquema(form.esquema, t),
    enviar: (valores) => llamar("equipo_alta", { valores }) });
  if (!r) return;
  const { id, nombre } = r.resultado;
  ofrecerDeshacer(pila, t("Se agregó el equipo «{nombre}»", { nombre }), async () => {
    await rpc.llamar("equipo_baja", { id, solo_si_sin_uso: true }); irA("#/equipos");
  });
  irA("#/equipos/" + id);
}

// Alta rápida en dos pasos: 1) datos del equipo (sin escribir) 2) cuántos conectores de cada tipo (parte de la plantilla del tipo de equipo);
// recién ahí se crea todo, en una sola llamada. Cancelar en cualquiera de los dos pasos no escribe nada.
export async function altaRapidaEquipo(rpc) {
  const llamar = conCampos(rpc), form = await rpc.llamar("equipo_formulario");
  const p1 = await abrirFormulario({ titulo: t("Alta rápida de equipo"), descripcion: t("Primero los datos del equipo; después elegís sus conectores."),
    campos: camposDesdeEsquema(form.esquema, t, { solo: CAMPOS_ALTA_RAPIDA }), textoEnviar: "Siguiente", enviar: async (v) => v });
  if (!p1) return;
  const valores = soloRapida(p1.resultado), nombre = valores.nombre;
  const pl = await rpc.llamar("equipo_plantilla", { id_tipo_equipo: valores.id_tipo_equipo });
  const descripcion = valores.id_tipo_equipo == null
    ? t("Indicá cuántos conectores crear de cada tipo. Sin tipo de equipo no se guarda plantilla.")
    : pl.tiene_plantilla
      ? t("Cantidades de la plantilla de este tipo de equipo. Cambialas si hace falta: lo que elijas queda como plantilla del tipo.")
      : t("Este tipo de equipo todavía no tiene plantilla: indicá cuántos conectores crear de cada tipo y quedará como plantilla.");
  const r = await abrirFormulario({ titulo: t("Conectores de «{nombre}»", { nombre }), descripcion, campos: camposPlantilla(pl.filas), textoEnviar: "Crear equipo",
    enviar: (v) => llamar("equipo_alta_rapida", { valores, conectores: conectoresDesdeValores(pl.filas, v) }) });
  if (!r) return;
  const { id, n_conectores } = r.resultado;
  ofrecerDeshacer(pila, t("Se creó el equipo «{nombre}» con {n} conector(es)", { nombre, n: n_conectores }), async () => {
    await rpc.llamar("equipo_baja", { id, solo_si_sin_uso: true, conectores_propios: n_conectores }); irA("#/equipos");
  });
  irA("#/equipos/" + id);
}

export async function editarEquipo(rpc, id) {
  const llamar = conCampos(rpc), form = await rpc.llamar("equipo_formulario", { id_equipo: id });
  const r = await abrirFormulario({ titulo: t("Editar equipo"), campos: camposDesdeEsquema(form.esquema, t), valores: form.valores,
    enviar: (valores) => llamar("equipo_modificar", { id, valores }) });
  if (!r) return;
  const { anterior, nombre } = r.resultado;
  ofrecerDeshacer(pila, t("Se modificó el equipo «{nombre}»", { nombre }), async () => {
    await rpc.llamar("equipo_modificar", { id, valores: anterior }); repintar();
  });
  repintar();
}

// `e` = { id_equipo, nombre } (lo que ya tiene la ficha).
export async function eliminarEquipo(rpc, e) {
  const { usos } = await rpc.llamar("equipo_usos", { id_equipo: e.id_equipo }), nombre = nombreEquipo(e);
  const cuerpo = h("div", {}, h("p", {}, t("¿Eliminar el equipo «{nombre}»?", { nombre })), listaUsos(usos, "equipo"));
  if (!(await confirmar({ titulo: t("Eliminar equipo"), mensaje: cuerpo, textoOk: "Eliminar", peligro: true }))) return;
  const r = await rpc.llamar("equipo_baja", { id: e.id_equipo });
  if (!r.usos.length) {                                         // sin nada arrastrado: se puede reinsertar tal cual
    ofrecerDeshacer(pila, t("Se eliminó el equipo «{nombre}»", { nombre }), async () => {
      await rpc.llamar("equipo_restaurar", { id: r.id, fila: r.fila }); irA("#/equipos/" + r.id);
    });
  } else avisar(t("Se eliminó el equipo «{nombre}»", { nombre }));
  irA("#/equipos");
}

// ── Conectores ───────────────────────────────────────────────────────────────

export async function altaConector(rpc, id_equipo) {
  const llamar = conCampos(rpc), form = await rpc.llamar("conector_formulario", { id_equipo });
  const r = await abrirFormulario({ titulo: t("Nuevo conector"), descripcion: t("Equipo: {equipo}", { equipo: form.equipo || "#" + id_equipo }),
    campos: camposDesdeEsquema(form.esquema, t), enviar: (valores) => llamar("conector_alta", { id_equipo, valores }) });
  if (!r) return;
  const { id, nombre } = r.resultado;
  ofrecerDeshacer(pila, t("Se agregó el conector «{nombre}»", { nombre }), async () => {
    await rpc.llamar("conector_baja", { id, solo_si_sin_uso: true }); repintar();
  });
  repintar();
}

export async function editarConector(rpc, id) {
  const llamar = conCampos(rpc), form = await rpc.llamar("conector_formulario", { id_conector: id });
  const r = await abrirFormulario({ titulo: t("Editar conector"), descripcion: t("Equipo: {equipo}", { equipo: form.equipo || "#" + form.id_equipo }),
    campos: camposDesdeEsquema(form.esquema, t), valores: form.valores, enviar: (valores) => llamar("conector_modificar", { id, valores }) });
  if (!r) return;
  const { anterior, nombre } = r.resultado;
  ofrecerDeshacer(pila, t("Se modificó el conector «{nombre}»", { nombre }), async () => {
    await rpc.llamar("conector_modificar", { id, valores: anterior }); repintar();
  });
  repintar();
}

// `c` = { id_conector, nombre, id_equipo }. Después de borrarlo se vuelve a la ficha de su equipo.
export async function eliminarConector(rpc, c) {
  const { usos } = await rpc.llamar("conector_usos", { id_conector: c.id_conector }), nombre = nombreConector(c);
  const cuerpo = h("div", {}, h("p", {}, t("¿Eliminar el conector «{nombre}»?", { nombre })), listaUsos(usos, "conector"));
  if (!(await confirmar({ titulo: t("Eliminar conector"), mensaje: cuerpo, textoOk: "Eliminar", peligro: true }))) return;
  const r = await rpc.llamar("conector_baja", { id: c.id_conector });
  const destino = c.id_equipo != null ? "#/equipos/" + c.id_equipo : "#/equipos";
  if (!r.usos.length) {
    ofrecerDeshacer(pila, t("Se eliminó el conector «{nombre}»", { nombre }), async () => {
      await rpc.llamar("conector_restaurar", { id: r.id, fila: r.fila }); irA("#/conectores/" + r.id);
    });
  } else avisar(t("Se eliminó el conector «{nombre}»", { nombre }));
  irA(destino);
}

// ── Extremo desconectado (equipo FANTASMA) ───────────────────────────────────

// `k` = { id_cable, codigo } (lo que ya tiene la ficha del cable). Si el cable ya tiene un extremo con conector IN/OUT el lado se infiere;
// si no, se pregunta. Cancelar no escribe nada. Después se repinta la ficha (la punta nueva aparece como un extremo más).
export async function extremoDesconectado(rpc, k) {
  const est = await rpc.llamar("cable_extremo_formulario", { id_cable: k.id_cable });
  if (!est.puede) { avisar(t(est.motivo)); return; }
  let lado = est.lado;
  if (!lado) {
    const p = await abrirFormulario({ titulo: t("Marcar extremo desconectado"), campos: camposLado(t), textoEnviar: "Crear", enviar: async (v) => v });
    if (!p) return;
    lado = p.resultado.lado;
  }
  const x = await rpc.llamar("cable_extremo_desconectado", { id_cable: k.id_cable, lado });
  ofrecerDeshacer(pila, t("Se creó el extremo desconectado «{nombre}»", { nombre: x.nombre }), async () => {
    await rpc.llamar("cable_extremo_deshacer", { id_equipo: x.id_equipo, id_conexion: x.id_conexion }); repintar();
  });
  repintar();
}
