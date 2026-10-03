// Formularios y diálogos genéricos (B.1). Base de todos los ABM de la Fase B: un <dialog> modal con validación por campo,
// errores del motor mostrados sin cerrar el diálogo, protección contra doble envío, aviso al descartar cambios y "Deshacer".
//
//   const r = await abrirFormulario({ titulo: "Nueva sala", campos: [...], valores: {...},
//     enviar: async (valores) => rpc.llamar("sala_alta", valores) });     // enviar puede lanzar ErrorFormulario(msg, {campo: msg})
//   // r = { resultado } si se guardó, o null si se canceló.
//   if (await confirmar({ mensaje: "¿Eliminar el cable?", peligro: true })) …
//   ofrecerDeshacer(pila, "Cable eliminado", async () => rpc.llamar("cable_restaurar", {...}));
//
// Todo texto va con textContent (vía h()): sin XSS por datos de la base. La lógica sin DOM vive en formulario_modelo.js.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { reportar, texto as textoError } from "./errores.js";
import { ErrorFormulario, valoresIniciales, validar, hayCambios } from "./formulario_modelo.js";

export { ErrorFormulario, crearPilaDeshacer } from "./formulario_modelo.js";

let secuencia = 0;
const msg = (e) => t(e.clave, e.vars);

// <dialog> modal. jsdom (y navegadores muy viejos) no traen showModal: se cae a `open` sin modalidad.
function montarDialogo({ clase, titulo, cuerpo, alCancelar }) {
  const id = "dlg" + ++secuencia, previo = document.activeElement;
  const d = h("dialog", { class: "form-dialogo " + (clase || ""), "aria-labelledby": id + "-t" },
    h("h3", { id: id + "-t" }, titulo), cuerpo);
  d.addEventListener("cancel", (e) => { e.preventDefault(); alCancelar(); });   // Esc
  document.body.append(d);
  if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
  return {
    dialogo: d, id,
    cerrar() {
      if (typeof d.close === "function" && d.open) d.close();
      d.remove();
      if (previo && previo.isConnected && typeof previo.focus === "function") previo.focus({ preventScroll: true });
    },
  };
}

// Un control por tipo de campo. Devuelve { fila, control, leer, error(clave|null) }.
function crearCampo(c, valor, base) {
  const id = base + "-" + c.nombre, idErr = id + "-err", idAyuda = id + "-ayuda";
  const comunes = { id, name: c.nombre, disabled: c.soloLectura, "aria-describedby": [c.ayuda ? idAyuda : null, idErr].filter(Boolean).join(" ") };
  if (c.requerido && c.tipo !== "checkbox") comunes["aria-required"] = "true";
  let control, leer;
  if (c.tipo === "texto_largo") {
    control = h("textarea", { ...comunes, rows: c.filas || 4 }); control.value = valor; leer = () => control.value;
  } else if (c.tipo === "select") {
    const vacio = !c.requerido || valor === "" || valor == null;
    control = h("select", comunes,
      vacio ? h("option", { value: "" }, t("— Elegí —")) : null,
      (c.opciones || []).map((o) => h("option", { value: String(o.valor) }, o.etiqueta ?? String(o.valor))));
    control.value = valor === "" || valor == null ? "" : String(valor); leer = () => control.value;
  } else if (c.tipo === "checkbox") {
    control = h("input", { ...comunes, type: "checkbox" }); control.checked = Boolean(valor); leer = () => control.checked;
  } else {
    const tipo = c.tipo === "fecha" ? "date" : "text";
    control = h("input", { ...comunes, type: tipo, inputmode: c.tipo === "entero" ? "numeric" : c.tipo === "numero" ? "decimal" : null,
      maxlength: c.largoMax && c.tipo === "texto" ? c.largoMax : null, autocomplete: "off", min: c.tipo === "fecha" ? c.min : null, max: c.tipo === "fecha" ? c.max : null });
    control.value = valor; leer = () => control.value;
  }
  const errorEl = h("div", { class: "form-error", id: idErr });
  const etiqueta = c.tipo === "checkbox"
    ? h("label", { class: "form-check", for: id }, control, " ", c.etiqueta ?? c.nombre, c.requerido ? h("span", { class: "form-req", "aria-hidden": "true" }, " *") : null)
    : h("label", { for: id }, c.etiqueta ?? c.nombre, c.requerido ? h("span", { class: "form-req", "aria-hidden": "true" }, " *") : null);
  const fila = h("div", { class: "form-fila", "data-campo": c.nombre },
    c.tipo === "checkbox" ? etiqueta : [etiqueta, control],
    c.ayuda ? h("div", { class: "form-ayuda", id: idAyuda }, c.ayuda) : null, errorEl);
  return {
    fila, control, leer,
    error(texto) {
      errorEl.textContent = texto || "";
      if (texto) { control.setAttribute("aria-invalid", "true"); fila.classList.add("con-error"); }
      else { control.removeAttribute("aria-invalid"); fila.classList.remove("con-error"); }
    },
  };
}

export function abrirFormulario({ titulo, descripcion, campos, valores = {}, enviar, textoEnviar = "Guardar", textoCancelar = "Cancelar" }) {
  return new Promise((resolver) => {
    const inicial = valoresIniciales(campos, valores), base = "frm" + ++secuencia;
    const ui = Object.fromEntries(campos.map((c) => [c.nombre, crearCampo(c, inicial[c.nombre], base)]));
    const leerTodo = () => Object.fromEntries(campos.map((c) => [c.nombre, ui[c.nombre].leer()]));
    let enviando = false, terminado = false;

    const general = h("div", { class: "form-general", role: "alert" });
    const btnOk = h("button", { type: "submit", class: "primario" }, t(textoEnviar));
    const btnNo = h("button", { type: "button", onclick: () => cancelar() }, t(textoCancelar));
    const form = h("form", { novalidate: true, class: "form-cuerpo", onsubmit: (e) => { e.preventDefault(); intentar(); } },
      descripcion ? h("p", { class: "sub" }, descripcion) : null,
      general, campos.map((c) => ui[c.nombre].fila),
      campos.some((c) => c.requerido) ? h("p", { class: "form-nota sub" }, t("Los campos con * son obligatorios.")) : null,
      h("div", { class: "form-botones" }, btnNo, btnOk));
    const dlg = montarDialogo({ clase: "formulario", titulo, cuerpo: form, alCancelar: () => cancelar() });

    const cerrar = (res) => { if (terminado) return; terminado = true; dlg.cerrar(); resolver(res); };
    const bloquear = (si) => { enviando = si; btnOk.disabled = btnNo.disabled = si; form.setAttribute("aria-busy", String(si));
      btnOk.textContent = si ? t("Guardando…") : t(textoEnviar); };
    const mostrarErrores = (errores) => {                      // errores: { campo: texto ya traducido }
      for (const c of campos) ui[c.nombre].error(errores[c.nombre] || null);
      const primero = campos.find((c) => errores[c.nombre]);
      if (primero) ui[primero.nombre].control.focus();
      return Object.keys(errores).length;
    };

    function cancelar() {
      if (enviando || terminado) return;
      if (hayCambios(campos, leerTodo(), inicial) && !globalThis.confirm(t("¿Descartar los cambios sin guardar?"))) return;
      cerrar(null);
    }

    async function intentar() {
      if (enviando || terminado) return;
      general.textContent = "";
      const v = validar(campos, leerTodo());
      if (!v.ok) {
        const n = mostrarErrores(Object.fromEntries(Object.entries(v.errores).map(([k, e]) => [k, msg(e)])));
        general.textContent = t("Hay {n} campo(s) con errores. Revisalos y volvé a intentar.", { n });
        return;
      }
      mostrarErrores({});
      bloquear(true);
      try {
        const resultado = await enviar(v.valores);
        cerrar({ resultado });
      } catch (err) {
        if (terminado) return;
        bloquear(false);
        const delCampo = err instanceof ErrorFormulario ? Object.fromEntries(Object.entries(err.campos || {}).filter(([k]) => k in ui).map(([k, m]) => [k, t(String(m))])) : {};
        if (Object.keys(delCampo).length) mostrarErrores(delCampo);
        general.textContent = t("No se pudo guardar: {error}", { error: textoError(err) });
        reportar(err, "No se pudo guardar", { toast: false });
        if (!Object.keys(delCampo).length) btnOk.focus();
      }
    }

    const primero = campos.find((c) => !c.soloLectura);
    if (primero) ui[primero.nombre].control.focus();
  });
}

// Confirmación (p. ej. antes de borrar o de "aplicar a la infraestructura"). `mensaje` puede ser texto o un Node (resumen).
// Con `peligro` el foco inicial queda en "Cancelar". Resuelve true/false.
export function confirmar({ titulo = "Confirmar", mensaje, textoOk = "Aceptar", textoCancelar = "Cancelar", peligro = false }) {
  return new Promise((resolver) => {
    let terminado = false;
    const fin = (v) => { if (terminado) return; terminado = true; dlg.cerrar(); resolver(v); };
    const btnOk = h("button", { type: "button", class: peligro ? "peligro" : "primario", onclick: () => fin(true) }, t(textoOk));
    const btnNo = h("button", { type: "button", onclick: () => fin(false) }, t(textoCancelar));
    const cuerpo = h("div", { class: "form-cuerpo" }, h("div", { class: "form-mensaje" }, typeof mensaje === "string" ? t(mensaje) : mensaje),
      h("div", { class: "form-botones" }, btnNo, btnOk));
    const dlg = montarDialogo({ clase: "confirmacion", titulo: t(titulo), cuerpo, alCancelar: () => fin(false) });
    (peligro ? btnNo : btnOk).focus();
  });
}

// Registra la acción en la pila y muestra un aviso con el botón "Deshacer" (8 s). Si revertir falla, lo informa y la entrada se conserva.
export function ofrecerDeshacer(pila, textoAccion, deshacer) {
  pila.registrar(textoAccion, deshacer);
  const cont = document.getElementById("toasts"); if (!cont) return null;
  const span = h("span", {}, textoAccion);
  const btn = h("button", { type: "button", onclick: async () => {
    btn.disabled = true;
    try { const hecho = await pila.deshacer(); span.textContent = t("Deshecho: {texto}", { texto: hecho ?? textoAccion }); btn.remove(); setTimeout(() => el.remove(), 4000); }
    catch (err) { btn.disabled = false; reportar(err, "No se pudo deshacer"); }
  } }, t("Deshacer"));
  const el = h("div", { class: "toast ok", role: "status" }, span, btn,
    h("button", { type: "button", "aria-label": t("Cerrar"), onclick: () => el.remove() }, "✕"));
  cont.append(el);
  setTimeout(() => { if (btn.isConnected) el.remove(); }, 8000);
  return el;
}
