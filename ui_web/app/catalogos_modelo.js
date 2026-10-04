// Catálogos básicos (B.2) — lógica pura, sin DOM ni i18n (la traducción entra como parámetro `tr`): qué catálogos hay, qué
// columnas se listan, cómo se arma el formulario a partir del esquema que manda el bridge, el filtro y el detalle de usos.
// Las reglas de validación NO se repiten acá: salen del `esquema` de bridge.catalogo_lista (catalogos_web.py), que es la
// única fuente (la UI solo agrega etiquetas y ayudas).
import { normalizar, tokens } from "./arbol.js";

// `ruta` = segmento de la URL (#/catalogos/<ruta>); `cat` = clave del bridge; `columnas` = campos que se muestran, en orden.
// Los textos son claves de i18n (español); `singular` va dentro de «Alta de {x}», «Editar {x}» y «Eliminar {x}».
export const CATALOGOS = [
  { ruta: "marcas",         cat: "marca",         titulo: "Marcas",              singular: "marca",              columnas: ["nombre"] },
  { ruta: "tipos-equipo",   cat: "tipo_equipo",   titulo: "Tipos de equipo",     singular: "tipo de equipo",     columnas: ["nombre", "rol_senal"] },
  { ruta: "tipos-conector", cat: "tipo_conector", titulo: "Tipos de conector",   singular: "tipo de conector",   columnas: ["nombre", "es_referencia_generada"] },
  { ruta: "tipos-cable",    cat: "tipo_cable",    titulo: "Tipos de cable",      singular: "tipo de cable",
    columnas: ["nombre", "naturaleza_senal", "long_max_balanceado_m", "long_max_desbalanceado_m", "ancho_banda_mhz"] },
  { ruta: "tipos-ficha",    cat: "tipo_ficha",    titulo: "Tipos de ficha",      singular: "tipo de ficha",
    columnas: ["nombre", "n_conductores", "modo_balance_default", "modo_canal_default", "ancho_banda_mhz"] },
  { ruta: "senales",        cat: "senal",         titulo: "Señales",             singular: "señal",              columnas: ["nombre", "tipo_contenido", "descripcion"] },
  { ruta: "formatos-senal", cat: "formato_senal", titulo: "Formatos de señal",   singular: "formato de señal",   columnas: ["nombre"] },
  { ruta: "imagenes",       cat: "imagen",        titulo: "Imágenes",            singular: "imagen",             columnas: ["path_archivo", "descripcion"] },
];
export const RUTA_INICIAL = CATALOGOS[0].ruta;
export const porRuta = (ruta) => CATALOGOS.find((c) => c.ruta === ruta) || null;

// Etiqueta del campo en el formulario y título de su columna en la lista.
export const ETIQUETA_CAMPO = {
  nombre: "Nombre", rol_senal: "Rol frente a la señal",
  es_referencia_generada: "Es referencia generada (fuente incondicional de sync, ej. SPG/wordclock)",
  naturaleza_senal: "Naturaleza de la señal", long_max_balanceado_m: "Long. máx. recomendada — balanceado (m)",
  long_max_desbalanceado_m: "Long. máx. recomendada — desbalanceado (m)", ancho_banda_mhz: "Ancho de banda (MHz)",
  n_conductores: "Cantidad de conductores", modo_balance_default: "Balance por defecto", modo_canal_default: "Canal por defecto",
  tipo_contenido: "Tipo de contenido", descripcion: "Descripción", path_archivo: "Archivo de imagen",
};
export const TITULO_COLUMNA = {
  nombre: "Nombre", rol_senal: "Rol señal", es_referencia_generada: "Referencia generada", naturaleza_senal: "Naturaleza",
  long_max_balanceado_m: "Máx. balanceado (m)", long_max_desbalanceado_m: "Máx. desbalanceado (m)", ancho_banda_mhz: "Ancho de banda (MHz)",
  n_conductores: "Conductores", modo_balance_default: "Balance", modo_canal_default: "Canal",
  tipo_contenido: "Contenido", descripcion: "Descripción", path_archivo: "Archivo",
};
// Ayuda debajo del campo (solo donde el nombre no alcanza).
export const AYUDA_CAMPO = {
  es_referencia_generada: "El análisis de impacto trata cualquier conector de este tipo como fuente de señal, aunque no tenga entradas cableadas.",
  path_archivo: "Nombre del archivo en la carpeta de imágenes (ej. camara.png). Desde acá solo se edita el registro: los archivos se cargan desde las fichas.",
  n_conductores: "Para fichas ambiguas (ej. TRS) estos valores son solo el default: cada conector puede tener su propio ajuste.",
};
// Rol de señal: etiqueta de cada opción (la lista de roles válidos la manda el bridge; un rol sin etiqueta se muestra con su código).
export const ETIQUETA_ROL = {
  DISTRIBUIDOR: "Distribuidor (repite la señal en sus salidas)", FUENTE: "Fuente (genera la señal)",
  ENRUTADOR: "Enrutador (según ruteo de matriz)", PROCESADOR: "Procesador (combina/transforma → señal nueva)",
  CONSUMIDOR: "Consumidor (no tiene salidas de señal)", PATCHERA: "Patchera (bypass físico A/B, no usa ruteo de matriz)",
  CONVERSOR_BALANCE: "Conversor de balance (DI box, transformador — punto de conversión legítimo)",
  SUMADOR_CANAL: "Sumador/divisor de canal (mono↔estéreo — punto de conversión legítimo)",
  DISTRIBUIDOR_FRAME: "Distribuidor de referencia de frame (reparte REF1/REF2 externo a los demás slots del frame)",
  FANTASMA: "Fantasma (extremo desconectado confirmado)",
};
export const VALOR_INICIAL = { rol_senal: "DISTRIBUIDOR" };

// Tabla que usa el valor → clave de i18n con su nombre en plural.
export const ETIQUETA_USO = {
  equipo: "Equipos", equipo_catalogo: "Moldes de equipo", frame: "Frames", frame_catalogo: "Moldes de frame",
  conector: "Conectores", conector_catalogo: "Moldes de conector", cable: "Cables", conexion: "Conexiones", slot: "Slots",
  plantilla_conector: "Plantillas de conectores", regla_logica: "Reglas lógicas", estrategia_visual: "Estrategias visuales",
  catalogo_simbolo_conector: "Símbolos de conector", senal_en_conector: "Señales asignadas a conectores",
  senal_linaje: "Relaciones de linaje de señal", imagen_senal_conector: "Imágenes de señal de conector",
  extension_cable: "Extensiones de cable", escenario_cambio: "Cambios de escenario", incidente_cable: "Incidentes de cable", diagnostico_sesion: "Sesiones de diagnóstico",   // B.3 (borrar un cable)
  // B.4 (borrar un equipo o un conector: se siguen las cascadas de las claves foráneas)
  posicion_en_rack: "Posiciones en rack",
  problema_equipo: "Problemas del equipo",
  equipo_critico: "Marcas de equipo crítico",
  riesgo_equipo_cache: "Cachés de riesgo",
  diagrama_equipos_posicion_en_imagen: "Posiciones en diagramas",
  diagrama_guardado_nodo: "Nodos de diagramas guardados",
  diagrama_guardado_conexion: "Conexiones de diagramas guardados",
  equiponoraqueable_por_sala: "Equipos no rackeables en sala",
  zona_equipo: "Equipos en zonas",
  equipo_sobre_mueble: "Equipos sobre muebles",
  incidente_equipo: "Incidentes de equipo",
  regla_logica_miembro: "Miembros de reglas lógicas",
  regla_logica_salida: "Salidas de reglas lógicas",
  matriz_ruteo: "Ruteos de matriz",
  estrategia_visual_miembro: "Miembros de estrategias visuales",
  diagnostico_paso: "Pasos de diagnóstico",
};

// Campos de abrirFormulario() a partir del esquema del bridge. `tr` traduce (la UI pasa t). `fila` = registro que se edita
// (null en un alta): sirve para que un valor libre que ya existe (p. ej. un tipo de contenido que el desktop dejó cargado)
// siga siendo elegible al editar aunque no esté entre los sugeridos.
export function camposFormulario(esquema, tr = (x) => x, fila = null) {
  return esquema.map((e) => {
    const base = { nombre: e.nombre, etiqueta: tr(ETIQUETA_CAMPO[e.nombre] || e.nombre), requerido: e.requerido,
      ayuda: AYUDA_CAMPO[e.nombre] ? tr(AYUDA_CAMPO[e.nombre]) : undefined };
    if (e.nombre in VALOR_INICIAL && !fila) base.valorInicial = VALOR_INICIAL[e.nombre];
    if (e.tipo === "bool") return { ...base, tipo: "checkbox" };
    if (e.tipo === "select") {
      return { ...base, tipo: "select", opciones: e.opciones.map((o) => ({ valor: o, etiqueta: e.nombre === "rol_senal" ? tr(ETIQUETA_ROL[o] || o) : o })) };
    }
    if (e.sugeridos) {                                              // texto libre con valores habituales → lista, más el valor actual si es otro
      const valores = [...e.sugeridos], actual = fila?.[e.nombre];
      if (actual != null && actual !== "" && !valores.includes(actual)) valores.push(actual);
      return { ...base, tipo: "select", opciones: valores.map((o) => ({ valor: o, etiqueta: o })) };
    }
    if (e.tipo === "numero" || e.tipo === "entero") return { ...base, tipo: e.tipo, min: e.minimo };
    return { ...base, tipo: e.tipo, largoMax: e.largo };
  });
}

// Texto de una celda de la lista.
export function textoCelda(campo, valor, tr = (x) => x) {
  if (valor == null || valor === "") return "";
  if (typeof valor === "boolean") return valor ? "✓" : "";
  return String(valor);
}

// Nombre con el que se nombra un registro en mensajes y avisos (el primer campo que se lista).
export const etiquetaFila = (def, fila) => String(fila[def.columnas[0]] ?? "#" + fila.id);

// Filtro en memoria: todas las palabras deben aparecer (en cualquier orden, sin acentos ni mayúsculas) en el id o en las
// columnas visibles. Con menos de 2 caracteres no se filtra (mismo criterio que el árbol y la búsqueda).
export function filtrarFilas(filas, texto, def) {
  const toks = tokens(texto);
  if (!toks.length) return filas;
  return filas.filter((f) => {
    const pajar = normalizar([f.id, ...def.columnas.map((c) => f[c])].filter((v) => v != null && typeof v !== "boolean").join(" "));
    return toks.every((t) => pajar.includes(t));
  });
}

// Detalle de usos para la confirmación de borrado: [{ n, tabla (ya traducida), efecto }] en el orden que manda el bridge.
export const detalleUsos = (usos, tr = (x) => x) => (usos || []).map((u) => ({ n: u.n, tabla: tr(ETIQUETA_USO[u.tabla] || u.tabla), efecto: u.efecto }));
