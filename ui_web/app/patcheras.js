// Patcheras (A.6, solo lectura): réplica de PatcherasVista (modo global) del desktop. Un rack por bloque; cada frame de patcheras
// es una franja con una columna por módulo y dos filas de orificios: A = entrada trasera / derivación frontal, B = salida trasera /
// inserción frontal. El punto muestra a qué equipo está cableado por atrás; los patchcords del frente se dibujan encima.
// Los datos vienen armados de bridge.patcheras_global (ver su docstring); acá solo se calcula la geometría y se dibuja.
import { h } from "./dom.js";
import { t } from "./i18n.js";
import { s, abreviar, colorPaleta, enlaceSvg, controlesZoom } from "./svg.js";
import { volver } from "./fichas.js";

// Medidas del desktop (PatcherasVista), a zoom 1.
export const P = { DOT_R: 6, DOT_STEP: 19, ROW_H: 24, HDR_H: 16, LBL_W: 56, STRIP_GAP: 3, RHDR_H: 22, MARGIN: 6, RACK_GAP: 30, TOP: 40 };
const STRIP_H = P.HDR_H + 2 * P.ROW_H;
const GRIS_FANTASMA = "#8C8C99";

// Geometría de todo el dibujo: ancho común, y posición vertical de cada rack. Pura (se prueba sin DOM).
export function geometria(d) {
  const ancho = P.LBL_W + d.max_col * P.DOT_STEP + P.MARGIN * 2;
  let y = P.TOP;
  const racks = d.racks.map((r) => { const alto = P.RHDR_H + P.MARGIN + r.frames.length * (STRIP_H + P.STRIP_GAP); const g = { y, alto, rack: r }; y += alto + P.RACK_GAP; return g; });
  return { ancho, alto: y - P.RACK_GAP + P.MARGIN, racks };
}

// Centro del orificio trasero (fila A o B) de la columna `col` del frame `idFrame` del rack `idRack`; null si no existe.
export function ancla(geo, idRack, idFrame, col, fila) {
  const g = geo.racks.find((x) => x.rack.id_rack === idRack); if (!g) return null;
  const i = g.rack.frames.findIndex((f) => f.id_frame === idFrame); if (i < 0) return null;
  return { x: P.LBL_W + (col - 1) * P.DOT_STEP + P.DOT_STEP / 2, y: g.y + P.RHDR_H + P.MARGIN + i * (STRIP_H + P.STRIP_GAP) + P.HDR_H + (fila === "A" ? 0 : 1) * P.ROW_H + P.ROW_H / 2 };
}

const rid = (v) => (v == null ? "" : String(v));

// Devuelve el <svg>. `cruces`: dibujar la curva real de los patchcords que cambian de rack (si no, un cabo corto en cada punta).
export function svgPatcheras(d, { zoom = 1, cruces = false } = {}) {
  const geo = geometria(d), W = geo.ancho, H = geo.alto;
  const svg = s("svg", { class: "pat-svg", viewBox: `0 0 ${W} ${H}`, width: W * zoom, height: H * zoom, role: "img", "aria-label": t("Patcheras") });
  const modulo = new Map(), rackNom = new Map();                    // (rack|frame|col) → nombre del módulo, para los tooltips de los patchcords
  for (const r of d.racks) { rackNom.set(r.id_rack, r.rack); for (const f of r.frames) for (const c of f.columnas) modulo.set(`${r.id_rack}|${f.id_frame}|${c.col}`, c.modulo); }
  const nombreModulo = (p) => modulo.get(`${p.id_rack}|${p.id_frame}|${p.col}`) || "?";

  for (const g of geo.racks) {
    const r = g.rack;
    svg.append(s("rect", { class: "pt-fondo", x: 0, y: g.y, width: W, height: g.alto }), s("rect", { class: "pt-rack-cab", x: 0, y: g.y, width: W, height: P.RHDR_H }),
      s("text", { class: "pt-rack-txt", x: P.MARGIN, y: g.y + P.RHDR_H * 0.72, "font-size": 11, "font-weight": 700 }, `RACK  ${String(r.rack ?? "").toUpperCase()}`));
    r.frames.forEach((f, i) => {
      const y0 = g.y + P.RHDR_H + P.MARGIN + i * (STRIP_H + P.STRIP_GAP), porCol = new Map(f.columnas.map((c) => [c.col, c]));
      svg.append(s("rect", { class: "pt-franja", x: 0, y: y0, width: W, height: STRIP_H }),
        s("text", { class: "pt-frame", x: P.LBL_W * 0.45, y: y0 + STRIP_H / 2, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 9, "font-weight": 700 }, abreviar(f.frame, P.LBL_W - 6, 9)),
        s("title", {}, `${r.rack} · ${f.frame}`));
      for (let c = 1; c <= d.max_col; c++) {                          // números de columna (enlazan al módulo instalado)
        const cx = P.LBL_W + (c - 1) * P.DOT_STEP + P.DOT_STEP / 2, col = porCol.get(c);
        const num = s("text", { class: "pt-num", x: cx, y: y0 + P.HDR_H * 0.72, "text-anchor": "middle", "font-size": 8 }, String(c).padStart(2, "0"));
        svg.append(col ? enlaceSvg("#/equipos/" + col.id_equipo, num, s("title", {}, col.modulo)) : num);
      }
      ["A", "B"].forEach((fila, k) => {
        const ry = y0 + P.HDR_H + k * P.ROW_H + P.ROW_H / 2;
        svg.append(s("text", { class: "pt-fila", x: P.LBL_W * 0.8, y: ry, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 9, "font-weight": 700 }, fila));
        if (k === 0) svg.append(s("line", { class: "pt-sep", x1: P.LBL_W, x2: W - P.MARGIN, y1: y0 + P.HDR_H + P.ROW_H, y2: y0 + P.HDR_H + P.ROW_H }));
        for (let c = 1; c <= d.max_col; c++) {
          const cx = P.LBL_W + (c - 1) * P.DOT_STEP + P.DOT_STEP / 2, col = porCol.get(c), cel = col ? col[fila] : null, est = cel ? cel.estado : "vacio";
          const color = est === "conectado" ? colorPaleta(cel.color) : null, lugar = `${r.rack} · ${f.frame} · ${String(c).padStart(2, "0")}${fila}`;
          const punto = s("g", { class: `pt-punto pt-${est}`, "data-rack": r.id_rack, "data-frame": f.id_frame, "data-col": c, "data-fila": fila },
            color ? s("circle", { class: "pt-halo", cx, cy: ry, r: P.DOT_R * 1.7, fill: color, "fill-opacity": 0.22 }) : null,
            s("circle", { class: "pt-orificio", cx, cy: ry, r: P.DOT_R, fill: color }),
            s("circle", { class: "pt-brillo", cx: cx - P.DOT_R * 0.2, cy: ry - P.DOT_R * 0.3, r: P.DOT_R * 0.38, "fill-opacity": est === "vacio" ? 0.05 : 0.2 }),
            est === "fantasma" ? s("path", { class: "pt-x", d: `M${cx - P.DOT_R * 0.62} ${ry - P.DOT_R * 0.62}L${cx + P.DOT_R * 0.62} ${ry + P.DOT_R * 0.62}M${cx + P.DOT_R * 0.62} ${ry - P.DOT_R * 0.62}L${cx - P.DOT_R * 0.62} ${ry + P.DOT_R * 0.62}` }) : null,
            s("title", {}, est === "conectado" ? `${lugar}: ${cel.nombre} (${cel.conector})` : est === "fantasma" ? `${lugar}: ✖ ${t("FANTASMA")} — ${cel.nombre} (${cel.conector})` : col ? `${lugar}: ${t("libre")}` : lugar));
          svg.append(est !== "vacio" && cel.id_equipo != null ? enlaceSvg("#/equipos/" + cel.id_equipo, punto) : punto);
        }
      });
    });
  }

  // Patchcords del frente: nacen en el borde superior del orificio trasero de su fila. Curva = une dos módulos; cabo = punta libre.
  const dr = P.DOT_R, cabo = (a, color, titulo) => {
    const x1 = a.x, y1 = a.y - dr, x2 = x1 - 12, y2 = y1 - 16;
    return s("g", { class: "pt-cable pt-cabo" }, s("path", { d: `M${x1} ${y1}C${x1} ${y1 - 10} ${x2} ${y2 + 6} ${x2} ${y2}`, fill: "none", stroke: color, "stroke-opacity": 0.9, "stroke-width": 1.6 }),
      s("circle", { cx: x2, cy: y2, r: 2.6, fill: "none", stroke: color, "stroke-width": 1.2 }), s("title", {}, titulo));
  };
  const curva = (a, b, color, pico, titulo) => {
    const x1 = a.x, y1 = a.y - dr, x2 = b.x, y2 = b.y - dr, peak = Math.min(y1, y2) - pico;
    return s("g", { class: "pt-cable pt-curva" }, s("path", { d: `M${x1} ${y1}C${x1} ${peak} ${x2} ${peak} ${x2} ${y2}`, fill: "none", stroke: color, "stroke-opacity": 0.9, "stroke-width": 1.6 }), s("title", {}, titulo));
  };
  for (const j of d.jumpers) {
    const a1 = ancla(geo, j.p1.id_rack, j.p1.id_frame, j.p1.col, j.p1.row); if (!a1) continue;
    const color = j.color != null ? colorPaleta(j.color) : GRIS_FANTASMA, tit = `↔ ${t("Patchcord frente")} → `;
    if (!j.p2) { svg.append(cabo(a1, color, j.fantasma ? `✖ ${t("FANTASMA")} — ${j.texto}` : tit + j.texto)); continue; }
    const a2 = ancla(geo, j.p2.id_rack, j.p2.id_frame, j.p2.col, j.p2.row); if (!a2) continue;
    if (!j.cruza_rack) { svg.append(curva(a1, a2, color, 22, tit + `${nombreModulo(j.p2)} ⇄ ${nombreModulo(j.p1)}`)); continue; }
    if (cruces) svg.append(curva(a1, a2, color, 34, tit + `${nombreModulo(j.p2)} — ${t("Rack")} ${rid(rackNom.get(j.p2.id_rack))} ⇄ ${nombreModulo(j.p1)} — ${t("Rack")} ${rid(rackNom.get(j.p1.id_rack))}`));
    else svg.append(cabo(a1, color, tit + `${nombreModulo(j.p2)} — ${t("Rack")} ${rid(rackNom.get(j.p2.id_rack))}`), cabo(a2, color, tit + `${nombreModulo(j.p1)} — ${t("Rack")} ${rid(rackNom.get(j.p1.id_rack))}`));
  }
  return svg;
}

export async function vistaPatcheras({ rpc }) {
  const d = await rpc.llamar("patcheras_global");
  const caja = h("div", { class: "svg-scroll pat-scroll" });
  let cruces = false;
  const pintar = () => caja.replaceChildren(svgPatcheras(d, { zoom: z.zoom(), cruces }));
  const z = controlesZoom(() => pintar());
  const R = d.resumen;
  const chk = h("input", { type: "checkbox", id: "pat-cruces", onchange: (e) => { cruces = e.target.checked; pintar(); } });
  const hay = d.racks.length > 0, hayCruces = d.jumpers.some((j) => j.cruza_rack);
  if (hay) pintar();
  return h("section", { class: "ficha ficha-patcheras" },
    volver("ubicaciones", "Volver a Ubicaciones"),
    h("h2", {}, t("Patcheras")),
    hay ? [
      h("p", { class: "sub pat-resumen" }, [t("{racks} racks · {patcheras} patcheras", { racks: R.racks, patcheras: R.patcheras }), "🎨 " + t("{n} equipos conectados", { n: R.equipos }), "✖ " + t("{n} fantasma", { n: R.fantasma })].join("  ·  ")),
      h("p", { class: "sub" }, t("Fila A: entrada trasera y derivación frontal. Fila B: salida trasera e inserción frontal. Cada color es un equipo; hacé clic en un orificio para abrir el equipo.")),
      h("div", { class: "pat-barra" }, z.barra, hayCruces ? h("label", { class: "pat-cruces" }, chk, " " + t("Cables entre racks")) : null),
      caja,
    ] : h("p", { class: "sub" }, t("No se encontraron patcheras (módulos con rol PATCHERA en un slot de un frame de rack) en el sistema.")));
}
