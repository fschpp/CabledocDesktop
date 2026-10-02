// Ubicaciones (A.6, solo lectura): listado de salas/racks/frames, vista de rack y vista de frame con sus slots, en SVG.
// Réplicas de VistaRack y VistaFrameSlots del desktop. Los datos salen armados del bridge (ubicaciones, rack_vista, frame_vista);
// acá solo se dibuja. Rutas: #/ubicaciones · #/racks/<id> · #/frames/<id> (las patcheras están en patcheras.js).
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { s, abreviar, colorPaleta, enlaceSvg, controlesZoom } from "./svg.js";
import { idDeRuta, desconocida, enlace, datos, seccion, tabla, volver } from "./fichas.js";
import { urlImagen, alCambiarImagenes } from "./imagenes.js";
import { cargadorImagenes } from "./imagen_conectores.js";

const vacio = (v) => v == null || v === "";
const nombreRack = (r) => r.nombre || (r.numero != null ? `${t("Rack")} ${r.numero}` : `${t("Rack")} #${r.id_rack}`);

// ── Listado ──────────────────────────────────────────────────────────────────
export async function vistaUbicaciones({ rpc }) {
  const u = await rpc.llamar("ubicaciones");
  const filaRack = (r) => h("li", {}, h("a", { href: "#/racks/" + r.id_rack }, nombreRack(r)), " ",
    h("span", { class: "sub" }, [`${r.cantidad_maxima ?? 42} U`, t("{n} posiciones", { n: r.n_posiciones })].join(" · ")));
  const lista = (racks) => (racks.length ? h("ul", { class: "ubic-lista" }, racks.map(filaRack)) : h("p", { class: "sub" }, t("Sin racks")));
  return h("section", { class: "ficha ficha-ubicaciones" },
    h("h2", {}, t("Ubicaciones")),
    h("p", { class: "acciones" }, h("a", { href: "#/patcheras" }, "🔌 " + t("Patcheras (vista global)"))),
    seccion("Salas", u.salas.length ? u.salas.map((sala) => h("div", { class: "ubic-sala" }, h("h4", {}, sala.nombre || "#" + sala.id_sala), lista(sala.racks)))
      : h("p", { class: "sub" }, t("Sin salas"))),
    u.racks_sin_sala.length ? seccion("Racks sin sala", lista(u.racks_sin_sala)) : null,
    seccion("Frames", u.frames.length ? h("ul", { class: "ubic-lista" }, u.frames.map((f) => h("li", {},
      h("a", { href: "#/frames/" + f.id_frame }, f.nombre || "#" + f.id_frame), " ",
      h("span", { class: "sub" }, [[f.marca, f.modelo].filter(Boolean).join(" "), t("{n} slots", { n: f.n_slots })].filter(Boolean).join(" · ")),
      f.racks.length ? h("span", { class: "sub" }, " · " + t("Rack") + ": ") : null,
      f.racks.map((r, i) => [i ? ", " : null, enlace("racks", r.id_rack, r.rack || "#" + r.id_rack)])))) : h("p", { class: "sub" }, t("Sin frames"))));
}

// ── Rack ─────────────────────────────────────────────────────────────────────
// Medidas del desktop (VistaRack): una fila por orificio (1 U = 3 orificios).
export const RACK = { U_H: 28, NUM_W: 40, RACK_W: 310 };
const rangoOrificios = (sg) => (sg.u_count === 1 ? `${sg.u_ini}` : `${sg.u_ini}–${sg.u_ini + sg.u_count - 1}`);
const etiquetaTipo = (tipo) => t({ equipo: "Equipo", frame: "Frame", bandeja: "Bandeja", libre: "Libre" }[tipo]);

// Devuelve el <svg> del rack (`rack` = respuesta de rack_vista). Puro: sin red ni estado, para poder probarlo.
export function svgRack(rack, { zoom = 1 } = {}) {
  const { U_H, NUM_W, RACK_W } = RACK, cap = rack.cap, W = NUM_W + RACK_W, H = U_H + cap * U_H;
  const nombre = nombreRack(rack);
  const svg = s("svg", { class: "rack-svg", viewBox: `0 0 ${W} ${H}`, width: W * zoom, height: H * zoom, role: "img", "aria-label": nombre },
    s("rect", { x: 0, y: 0, width: W, height: H, fill: "#fff" }),
    s("rect", { class: "rk-cabecera", x: 0, y: 0, width: W, height: U_H }),
    s("text", { class: "rk-titulo", x: W / 2, y: U_H / 2, "text-anchor": "middle", "dominant-baseline": "central" }, abreviar(nombre, W - 80, 13)),
    s("text", { class: "rk-frente", x: W - 6, y: U_H - 4, "text-anchor": "end" }, t("FRENTE")));
  for (const sg of rack.segmentos) {
    const y0 = U_H + (sg.u_ini - 1) * U_H, alto = sg.u_count * U_H, rango = `${t("Orificio")} ${rangoOrificios(sg)}`;
    for (let i = 0; i < sg.u_count; i++) {                      // columna de números, una celda por orificio
      const y = U_H + (sg.u_ini - 1 + i) * U_H;
      svg.append(s("rect", { class: "rk-num", x: 0, y, width: NUM_W, height: U_H }),
        s("rect", { class: "rk-oreja", x: NUM_W - 6, y: y + U_H * 0.325, width: 5, height: U_H * 0.35 }),
        s("text", { class: "rk-num-txt", x: NUM_W * 0.44, y: y + U_H / 2, "text-anchor": "middle", "dominant-baseline": "central" }, sg.u_ini + i));
    }
    const cuerpo = s("g", { class: `rk-seg rk-${sg.tipo}`, "data-u": sg.u_ini },
      s("rect", { class: "rk-cuerpo", x: NUM_W, y: y0, width: RACK_W, height: alto }));
    if (sg.u_count > 1 && sg.tipo !== "libre") for (let i = 1; i < sg.u_count; i++) cuerpo.append(s("line", { class: "rk-guia", x1: NUM_W + 8, x2: NUM_W + RACK_W - 8, y1: y0 + i * U_H, y2: y0 + i * U_H }));
    const cx = NUM_W + RACK_W / 2, cy = y0 + alto / 2, fs = Math.max(8, Math.min(12, alto * 0.38));
    if (sg.tipo === "libre") {
      cuerpo.append(s("text", { class: "rk-txt", x: cx, y: cy, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 9, "font-style": "italic" }, t("LIBRE")),
        s("title", {}, `${t("Orificio")} ${sg.u_ini} — ${t("LIBRE")}`));
    } else if (sg.tipo === "bandeja") {
      cuerpo.append(s("text", { class: "rk-txt", x: cx, y: cy, "text-anchor": "middle", "dominant-baseline": "central", "font-size": Math.max(8, Math.min(12, alto * 0.3)), "font-weight": 700 },
        abreviar(t("Bandeja") + ": " + sg.nombre.join(", "), RACK_W - 14, 12)),
      s("title", {}, `${rango} [${t("Bandeja compartida")}]\n` + sg.nombre.map((n) => "  • " + n).join("\n")));
    } else {
      const dosLineas = sg.inv && alto > 2.2 * fs;
      cuerpo.append(s("text", { class: "rk-txt", x: cx, y: dosLineas ? cy - fs * 0.55 : cy, "text-anchor": "middle", "dominant-baseline": "central", "font-size": fs, "font-weight": 700 }, abreviar(sg.nombre, RACK_W - 14, fs)));
      if (dosLineas) cuerpo.append(s("text", { class: "rk-txt rk-inv", x: cx, y: cy + fs * 0.6, "text-anchor": "middle", "dominant-baseline": "central", "font-size": fs * 0.78 }, abreviar(sg.inv, RACK_W - 14, fs * 0.78)));
      cuerpo.append(s("title", {}, `${rango}\n${sg.nombre}` + (sg.inv ? `\n${t("Inventario")}: ${sg.inv}` : "")));
    }
    // Equipo y frame enlazan a su ficha / vista; la bandeja se navega desde la tabla de abajo (un enlace por dispositivo).
    const enlazable = (sg.tipo === "equipo" || sg.tipo === "frame") && sg.id != null;
    svg.append(enlazable ? enlaceSvg(`#/${sg.tipo === "frame" ? "frames" : "equipos"}/${sg.id}`, cuerpo) : cuerpo);
  }
  svg.append(s("rect", { class: "rk-marco", x: 0, y: 0, width: W, height: H }), s("line", { class: "rk-marco2", x1: NUM_W, y1: 0, x2: NUM_W, y2: H }));
  return svg;
}

export async function vistaRack({ rpc, args }) {
  const id = idDeRuta(args); if (id == null) return desconocida(args?.[0]);
  const r = await rpc.llamar("rack_vista", { id_rack: id });
  const caja = h("div", { class: "svg-scroll" });
  const z = controlesZoom((zoom) => caja.replaceChildren(svgRack(r, { zoom })));
  caja.replaceChildren(svgRack(r, { zoom: z.zoom() }));
  const R = r.resumen;
  const dispositivo = (sg) => (sg.tipo === "bandeja"
    ? sg.items.map((it, i) => [i ? ", " : null, it.id != null ? enlace(it.tipo === "frame" ? "frames" : "equipos", it.id, it.nombre) : it.nombre])
    : sg.id != null ? enlace(sg.tipo === "frame" ? "frames" : "equipos", sg.id, sg.nombre) : sg.nombre);
  const filas = r.segmentos.filter((sg) => sg.tipo !== "libre").map((sg) => h("tr", { "data-u": sg.u_ini },
    h("td", {}, rangoOrificios(sg)), h("td", {}, etiquetaTipo(sg.tipo)), h("td", {}, dispositivo(sg)), h("td", {}, sg.inv || "")));
  return h("section", { class: "ficha ficha-rack" },
    volver("ubicaciones", "Volver a Ubicaciones"),
    h("h2", {}, nombreRack(r)),
    h("p", { class: "sub" }, [r.salas.map((x) => x.nombre).join(", "), `${r.cap_u} U (${t("{n} orificios", { n: r.cap })})`].filter(Boolean).join(" · ")),
    h("p", { class: "sub rack-resumen" }, [t("{n} equipos", { n: R.equipos }), t("{n} frames", { n: R.frames }), t("{n} bandejas", { n: R.bandejas }), t("{n} orificios libres", { n: R.libres })].join(" · ")),
    h("p", { class: "sub" }, t("1 U = 3 orificios. Hacé clic en un equipo o frame para abrirlo.")),
    r.fuera_de_rango.length ? h("p", { class: "mal", role: "alert" }, t("Fuera del rango del rack (no se dibujan)") + ": " + r.fuera_de_rango.join(", ")) : null,
    z.barra, caja,
    seccion("Dispositivos", filas.length ? tabla(["Orificios", "Tipo", "Dispositivo", "Inventario"], filas) : h("p", { class: "sub" }, t("Rack vacío"))));
}

// ── Frame y slots ────────────────────────────────────────────────────────────
// Mide la imagen (ancho × alto naturales) para que los rectángulos de los slots, guardados en píxeles de la imagen, caigan bien.
function medirReal(url) {
  return new Promise((resolver) => {
    const img = document.createElement("img"), fin = (v) => { clearTimeout(tope); resolver(v); }, tope = setTimeout(() => resolver(null), 5000);
    img.onload = () => fin(img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null);
    img.onerror = () => fin(null);
    img.src = url;
  });
}
let medidor = medirReal;
export function configurarMedidor(f) { medidor = f || medirReal; }   // solo para tests (jsdom no carga imágenes)

// <svg> del frame: imagen (si se midió) y un rectángulo por slot en coordenadas de la imagen. `dim` = { w, h } o null (sin imagen).
export function svgFrame(f, { url = null, dim = null } = {}) {
  const sl = f.slots;
  const W = dim ? dim.w : Math.max(400, ...sl.map((x) => x.x + x.ancho + 20)), H = dim ? dim.h : Math.max(200, ...sl.map((x) => x.y + x.alto + 20));
  const svg = s("svg", { class: "frame-svg", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "xMidYMid meet", role: "img", "aria-label": f.nombre || "Frame" },
    dim && url ? s("image", { href: url, x: 0, y: 0, width: W, height: H }) : s("rect", { class: "fr-fondo", x: 0, y: 0, width: W, height: H }));
  const base = W / 55;                                              // el texto crece con la imagen: una foto de 3000 px se ve a ~1/4 de tamaño
  for (const m of sl) {
    const col = m.color != null ? colorPaleta(m.color) : "#8C8C94", fs = Math.max(6, Math.min(m.alto * 0.38, m.ancho * 0.12, base));
    const titulo = `${m.num}. ${m.nombre || ""} — ${m.equipo || t("(vacío)")}`;
    const g = s("g", { class: "fr-slot", "data-slot": m.id_slot, tabindex: 0 },
      s("rect", { x: m.x, y: m.y, width: m.ancho, height: m.alto, fill: col, "fill-opacity": 0.22, stroke: col, "stroke-width": 3, "vector-effect": "non-scaling-stroke" }),
      s("rect", { class: "fr-borde", x: m.x, y: m.y, width: m.ancho, height: m.alto, "vector-effect": "non-scaling-stroke" }),
      s("text", { class: "fr-nombre", x: m.x + m.ancho / 2, y: m.y + m.alto / 2, "text-anchor": "middle", "dominant-baseline": "central", "font-size": fs, "font-weight": 700, fill: "#111" },
        abreviar(m.equipo || t("(vacío)"), m.ancho - 8, fs)),
      s("rect", { x: m.x + 3, y: m.y + 3, width: Math.max(fs * 1.2, String(m.num).length * fs * 0.7 + 4), height: fs * 1.3, fill: col, "fill-opacity": 0.85 }),
      s("text", { x: m.x + 5, y: m.y + 3 + fs * 0.65, "dominant-baseline": "central", "font-size": fs * 0.85, fill: "#fff" }, m.num),
      s("title", {}, titulo));
    svg.append(m.id_equipo != null ? enlaceSvg("#/equipos/" + m.id_equipo, g) : g);
  }
  return svg;
}

export async function vistaFrame({ rpc, args }) {
  const id = idDeRuta(args); if (id == null) return desconocida(args?.[0]);
  const f = await rpc.llamar("frame_vista", { id_frame: id });
  const lienzo = h("div", { class: "frame-lienzo" });
  const dim = f.ancho_mm || f.alto_mm || f.profundidad_mm ? [f.ancho_mm, f.alto_mm, f.profundidad_mm].map((v) => (vacio(v) ? "?" : v)).join(" × ") + " mm" : null;
  let vivo = true;
  async function cargar() {
    if (!f.slots.length) return;
    let url = null, medida = null;
    if (f.imagen_path) {
      lienzo.replaceChildren(h("p", { class: "sub" }, t("Cargando imagen…")));
      try { url = await urlImagen(f.imagen_path); } catch (e) { lienzo.replaceChildren(h("p", { class: "mal" }, String(e?.message || e))); return; }
      if (url) medida = await medidor(url);
    }
    if (!vivo) return;
    lienzo.replaceChildren(
      !f.imagen_path ? h("p", { class: "sub" }, t("Este frame no tiene imagen: se dibujan solo los rectángulos de los slots."))
        : !url ? h("div", { class: "img-falta" }, h("p", {}, t("Imagen no cargada en este navegador") + ": " + f.imagen_path), cargadorImagenes())
          : !medida ? h("p", { class: "mal" }, t("No se pudo medir la imagen; se dibujan solo los rectángulos de los slots.")) : null,
      svgFrame(f, { url: medida ? url : null, dim: medida }));
  }
  const off = alCambiarImagenes(() => { if (!lienzo.isConnected) { vivo = false; return off(); } cargar(); });
  cargar();
  const resaltar = (idSlot, on) => lienzo.querySelectorAll(`.fr-slot[data-slot="${idSlot}"]`).forEach((g) => g.classList.toggle("resaltado", on));
  const filas = f.slots.map((m) => h("tr", { "data-slot": m.id_slot, onmouseenter: () => resaltar(m.id_slot, true), onmouseleave: () => resaltar(m.id_slot, false) },
    h("td", {}, h("span", { class: "swatch", style: `background:${m.color != null ? colorPaleta(m.color) : "#8C8C94"}` }), " ", m.num),
    h("td", {}, m.nombre || ""), h("td", {}, m.id_equipo != null ? enlace("equipos", m.id_equipo, m.equipo || "#" + m.id_equipo) : h("span", { class: "sub" }, t("(vacío)")))));
  return h("section", { class: "ficha ficha-frame" },
    volver("ubicaciones", "Volver a Ubicaciones"),
    h("h2", {}, f.nombre || "#" + f.id_frame),
    datos([["Marca", f.marca], ["Modelo", f.modelo], ["Inventario", f.inventario], ["Dimensiones", dim],
      ["Rack", f.racks.length ? f.racks.map((r, i) => [i ? ", " : null, enlace("racks", r.id_rack, r.rack || "#" + r.id_rack),
        vacio(r.orificio) ? "" : ` (${t("Posición")} ${r.orificio}${vacio(r.unidades) ? "" : `, ${r.unidades} U`})`]) : null]]),
    f.slots.length ? [lienzo, seccion("Slots", tabla(["#", "Slot", "Equipo"], filas))] : h("p", { class: "sub" }, t("Frame sin slots registrados")));
}
