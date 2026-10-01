// Modelo del árbol de infraestructura (A.3): preparación, filtro en memoria y aplanado a filas. Sin DOM.
// Es el patrón que dejó el historial del desktop (panel_arbol_ui.py): el filtro se calcula sobre la estructura
// en memoria (no sobre widgets) y solo se dibuja lo visible → ms en vez de segundos con miles de nodos.
export const MIN_CARACTERES = 2;      // con 1 solo carácter casi todo matchea y no aporta: no se filtra

// Minúsculas y sin acentos: "camara" encuentra "CÁMARA".
export const normalizar = (s) => String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// Palabras del filtro; todas deben aparecer en la etiqueta (en cualquier orden): "sony 3500" = marca Sony + modelo 3500.
export function tokens(texto) {
  const t = normalizar(texto).trim();
  return t.length < MIN_CARACTERES ? [] : t.split(/\s+/);
}

// Completa los nodos del bridge (in situ): `k` (ruta de índices, única aun si un equipo aparece en dos lugares),
// `l` de los grupos (vía etiquetaGrupo) y `busqueda` (etiqueta normalizada, calculada una sola vez). `h` queda siempre array.
export function prepararArbol(nodos, etiquetaGrupo) {
  const rec = (n, k) => {
    n.k = k;
    if (n.l == null) n.l = etiquetaGrupo(n);
    n.busqueda = normalizar(n.l);
    n.h ||= [];
    n.h.forEach((c, i) => rec(c, k + "." + i));
  };
  nodos.forEach((n, i) => rec(n, String(i)));
  return nodos;
}

// Expandido por defecto (sin filtro): solo la raíz (salas y "sin ubicación").
export const abiertosIniciales = (nodos) => new Set(nodos.map((n) => n.k));

// Aplana el árbol a la lista de filas visibles.
//   estado.abiertos : Set de k abiertos (sin filtro)
//   estado.cerrados : Set de k cerrados a mano (con filtro todo lo que tenga algo visible abajo se abre solo)
// Con filtro, un nodo se ve si él o algún descendiente coincide, y de un nodo solo se muestran los hijos que se ven
// (igual que el desktop). Devuelve { filas: [{ n, nivel, expandible, abierto }], coincidencias }.
export function aplanar(raices, texto, estado) {
  const toks = tokens(texto), filtra = toks.length > 0;
  const filas = [];
  let coincidencias = 0;

  if (!filtra) {
    const rec = (n, nivel) => {
      const abierto = n.h.length > 0 && estado.abiertos.has(n.k);
      filas.push({ n, nivel, expandible: n.h.length > 0, abierto });
      if (abierto) for (const c of n.h) rec(c, nivel + 1);
    };
    raices.forEach((n) => rec(n, 0));
    return { filas, coincidencias };
  }

  const visible = new Map();           // nodo → él o algún descendiente coincide
  const calcular = (n) => {
    const propio = toks.every((t) => n.busqueda.includes(t));
    if (propio) coincidencias++;
    let hijo = false;
    for (const c of n.h) if (calcular(c)) hijo = true;   // sin cortocircuito: hay que visitar todos para contar
    const v = propio || hijo;
    visible.set(n, v);
    return v;
  };
  raices.forEach(calcular);
  const emitir = (n, nivel) => {
    const hijos = n.h.filter((c) => visible.get(c));
    const abierto = hijos.length > 0 && !estado.cerrados.has(n.k);
    filas.push({ n, nivel, expandible: hijos.length > 0, abierto });
    if (abierto) for (const c of hijos) emitir(c, nivel + 1);
  };
  raices.filter((n) => visible.get(n)).forEach((n) => emitir(n, 0));
  return { filas, coincidencias };
}
