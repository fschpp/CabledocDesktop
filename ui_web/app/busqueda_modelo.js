// Modelo de la búsqueda global (A.9): preparación del índice y filtro en memoria. Sin DOM (se prueba aparte).
// El índice lo arma bridge.busqueda_indice(); acá se normaliza una sola vez y cada consulta es un recorrido por la lista.
import { normalizar, tokens } from "./arbol.js";

// Orden de los grupos: el mismo que el árbol de infraestructura (sala → rack → frame → equipo → conector) y al final los cables.
export const TIPOS = ["sala", "rack", "frame", "equipo", "conector", "cable"];

// Completa los items (in situ): `nl` = etiqueta normalizada, `busqueda` = etiqueta + datos + texto extra normalizados.
export function prepararIndice(items) {
  for (const it of items) {
    it.nl = normalizar(it.l);
    it.busqueda = normalizar([it.l, ...(it.d || []), it.x || ""].join(" "));
  }
  return items;
}

// Todas las palabras deben aparecer (en cualquier orden, sin acentos ni mayúsculas). Dentro de cada tipo, primero los que
// empiezan con la primera palabra, luego los que la llevan en el nombre y al final los que solo coinciden por sus datos
// (equipo, marca, extremos…); a igual puntaje se conserva el orden del índice (alfabético).
// → { filtra, conteo: {sala, rack, …, todos}, grupos: {tipo: [item, …]} }   (con filtra=false no hay grupos ni conteo)
export function buscar(items, texto) {
  const toks = tokens(texto);
  const conteo = Object.fromEntries([...TIPOS, "todos"].map((t) => [t, 0]));
  const grupos = Object.fromEntries(TIPOS.map((t) => [t, []]));
  if (!toks.length) return { filtra: false, conteo, grupos };
  const primero = toks[0];
  for (const it of items) {
    if (!toks.every((t) => it.busqueda.includes(t))) continue;
    const puntaje = it.nl.startsWith(primero) ? 0 : toks.every((t) => it.nl.includes(t)) ? 1 : 2;
    (grupos[it.t] ||= []).push({ it, puntaje });
    conteo[it.t] = (conteo[it.t] || 0) + 1;
    conteo.todos++;
  }
  for (const t of Object.keys(grupos)) {
    grupos[t].sort((a, b) => a.puntaje - b.puntaje);          // sort estable: conserva el orden del índice
    grupos[t] = grupos[t].map((x) => x.it);
  }
  return { filtra: true, conteo, grupos };
}

// Ruta de la ficha de cada tipo (las salas no tienen ficha propia: se ven en Ubicaciones).
export const rutaDe = (it) => ({
  sala: "#/ubicaciones", rack: `#/racks/${it.i}`, frame: `#/frames/${it.i}`,
  equipo: `#/equipos/${it.i}`, conector: `#/conectores/${it.i}`, cable: `#/cables/${it.i}`,
})[it.t];
