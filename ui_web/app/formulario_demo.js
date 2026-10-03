// Pantalla de prueba del patrón de formularios (B.1): #/demo-formulario. No está en el menú ni escribe en la base:
// "enviar" simula el motor (ok / error de campo / error general / lento) para probar validación, errores, doble envío y deshacer.
// Se puede borrar cuando exista el primer ABM real (B.2); queda como ejemplo de uso.
import { h } from "./dom.js";
import { abrirFormulario, confirmar, ofrecerDeshacer, crearPilaDeshacer, ErrorFormulario } from "./formulario.js";

const pila = crearPilaDeshacer(5);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

const CAMPOS = [
  { nombre: "nombre", etiqueta: "Nombre", tipo: "texto", requerido: true, largoMax: 30, ayuda: "Hasta 30 caracteres. Probá «repetido» con el modo «error de campo»." },
  { nombre: "cantidad", etiqueta: "Cantidad (entero 1–99)", tipo: "entero", requerido: true, min: 1, max: 99, valorInicial: 1 },
  { nombre: "factor", etiqueta: "Factor (número, acepta coma)", tipo: "numero", min: 0 },
  { nombre: "tipo", etiqueta: "Tipo", tipo: "select", requerido: true, opciones: [{ valor: 1, etiqueta: "DDV" }, { valor: 2, etiqueta: "MATRIZ" }, { valor: 3, etiqueta: "FANTASMA" }] },
  { nombre: "fecha", etiqueta: "Fecha de fabricación", tipo: "fecha", max: "2026-12-31" },
  { nombre: "codigo", etiqueta: "Código (A-123)", tipo: "texto", patron: "^[A-Z]-\\d{3}$", patronMensaje: "Formato esperado: A-123" },
  { nombre: "notas", etiqueta: "Notas", tipo: "texto_largo", largoMax: 200 },
  { nombre: "usado", etiqueta: "Equipo usado", tipo: "checkbox" },
  { nombre: "modo", etiqueta: "Resultado simulado", tipo: "select", requerido: true, valorInicial: "ok",
    opciones: [{ valor: "ok", etiqueta: "Guardar bien" }, { valor: "campo", etiqueta: "Error de campo (nombre repetido)" },
      { valor: "general", etiqueta: "Error general del motor" }, { valor: "lento", etiqueta: "Guardar bien, tras 2 s" }] },
];

export function vistaDemoFormulario() {
  const salida = h("pre", { class: "form-demo-salida", "aria-live": "polite" }, "(todavía no se guardó nada)");
  const deshacer = h("button", { type: "button", disabled: true }, "Deshacer último");
  const refrescar = () => { deshacer.disabled = !pila.hay(); deshacer.textContent = pila.hay() ? "Deshacer: " + pila.ultimo() : "Deshacer último"; };
  deshacer.addEventListener("click", async () => { try { await pila.deshacer(); salida.textContent = "(deshecho)"; } finally { refrescar(); } });

  const abrir = async (valores) => {
    const r = await abrirFormulario({
      titulo: "Formulario de ejemplo", descripcion: "Nada de esto se guarda en la base.", campos: CAMPOS, valores,
      enviar: async (v) => {
        await espera(v.modo === "lento" ? 2000 : 250);
        if (v.modo === "campo" && String(v.nombre).toLowerCase() === "repetido") throw new ErrorFormulario("Hay datos que corregir", { nombre: "Ya existe uno con ese nombre" });
        if (v.modo === "general") throw new Error("el motor Python no respondió (simulado)");
        return { id: Math.floor(Math.random() * 1000), ...v };
      } });
    if (!r) { salida.textContent = "(cancelado)"; return; }
    salida.textContent = JSON.stringify(r.resultado, null, 2);
    ofrecerDeshacer(pila, "Alta de «" + r.resultado.nombre + "»", async () => { await espera(100); refrescar(); });
    refrescar();
  };

  return h("section", { class: "ficha" },
    h("h2", {}, "Formulario de ejemplo (B.1)"),
    h("p", { class: "sub" }, "Página de prueba del patrón de formularios y diálogos de la Fase B. No escribe en la base."),
    h("p", {}, h("button", { type: "button", class: "primario", onclick: () => abrir({ nombre: "" }) }, "Abrir formulario"), " ",
      h("button", { type: "button", onclick: () => abrir({ nombre: "Equipo existente", cantidad: 3, tipo: 2, modo: "ok" }) }, "Abrir con datos"), " ",
      h("button", { type: "button", class: "peligro", onclick: async () => { salida.textContent = (await confirmar({ titulo: "Eliminar", mensaje: "¿Eliminar el cable CBL-001? Esta acción no se puede deshacer.", textoOk: "Eliminar", peligro: true })) ? "(confirmado)" : "(no confirmado)"; } }, "Probar confirmación"), " ",
      deshacer),
    salida);
}
