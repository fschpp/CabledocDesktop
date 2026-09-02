# CableDoc

**Broadcast cable and infrastructure management software.**

CableDoc is a desktop application for documenting and analyzing the cabling
and signal flow of a real broadcast/AV facility (fully digital video, aging
analog audio chain). It manages the physical infrastructure — equipment,
connectors, cables, connections, racks, frames, slots, patch bays
(`patcheras`), routing matrices, and signal entities — and layers impact
analysis, risk scoring, and fault diagnosis on top of it.

Development is driven by real cases found during on-site cabling surveys,
in particular the diagnosis of recurring audio failures traceable to
weaknesses in the analog chain.

> The application's UI, domain vocabulary, comments, and changelog are
> entirely in **Spanish**, since it is built for and used by a real
> broadcast facility. This README is in English for the repository; the
> application itself remains in Spanish, with English/Portuguese available
> as translated UI languages.

- **Origin**: successor to a VB.NET/WinForms predecessor, fully ported to
  Python/GTK3 (a ~26-page LaTeX/PDF technical write-up comparing both
  architectures lives in `help/`). The `CONEXIONES_AMBOS_EXTREMOS` SQL view
  survives from that era.
- **License**: GNU GPL v2 (see [`LICENSE`](./LICENSE)).
- **Author**: fschpp.

---

## What it does

- **Physical infrastructure documentation**: rooms, racks, frames, slots,
  equipment, connectors, and cables, positioned over reference images —
  including SVG images, which stay crisp at any zoom level. Position data
  is stored as **percentages of image width/height** (not raw pixels), so
  connector/slot positions survive swapping in a differently-sized image.
- **Cable & connector tracking**: full connection graph between equipment,
  including patch panels (`patchera`, with front/back row modeling —
  `A_BACK`/`B_BACK`/`A_FRONT`/`B_FRONT` — and full-normal jack bypass
  behavior), routing matrices (`rol_senal = ENRUTADOR`, with recursive
  resolution across cascaded matrices), and disconnected/"phantom"
  endpoints (`FANTASMA`) for cable ends confirmed absent in the field.
- **Cable extensions**: direct point-to-point cable joins (`Extensión`, as
  opposed to `Empalme`/barrel couplers), with full bidirectional chain
  resolution ("view full chain").
- **Signal chain modeling**: signals (`senal`) traced through connectors,
  with role tagging (`rol_senal`) and a documentation-only lineage graph
  (`senal_linaje`) that records how a signal was derived without feeding
  it into automated impact analysis.
- **"What breaks if I disconnect this?" impact analysis**
  (`graph_impact.py`, `GraphImpactAnalyzer`): propagates the effect of
  removing a cable/connector/equipment across AND/OR logical rules
  (`regla_logica`, e.g. DSK-style gates) and routing matrices, and reports
  exactly which downstream equipment and rules are affected — modeled at
  connector granularity so internal routing (e.g. inside a matrix) is
  simulated accurately.
- **Visual diagrams**: Cairo-rendered rack views, an interactive
  connections diagram (`DiagramaConexiones`) with drag-and-drop cabling,
  auto-layout, incomplete-connection overlays, and free-form custom
  diagrams (`diagrama_personalizado.py`), plus dedicated signal-risk and
  signal-state diagrams.
- **Incident log & analog risk tracking** (`bitacora_ui.py`,
  `riesgo_analogico.py`): records incidents, flags "suspect zones"
  (`zona_sospechosa`), and scores analog-chain risk using configurable,
  linear-decay weighting.
- **Structural signal risk** (`signal_risk.py`, `risk_engine.py` /
  Failure Risk Index): risk scoring based on balance, attenuation, and
  bandwidth characteristics of the signal chain.
- **Fault diagnosis assistant** (`diagnostico_falla.py`,
  `diagnostico_ui.py`): guided troubleshooting based on the documented
  signal chain and logged incidents.
- **Operational scenarios** (`escenario_engine.py`, `escenario_ui.py`):
  model and compare contingency/operational configurations — including
  virtual reconnection — against the documented infrastructure.
- **Cypher-style graph query console** (`cypher_console.py`) over the
  documented topology, backed by GraphQLite (a Rust/C SQLite extension
  with Cypher support); a historic Neo4j-based path also exists.
- **Catalog with JSON import/export** (equipment/frame/connector
  templates), with a deduplicated image pool.
- **Multi-language UI** (`i18n.py`): Spanish as the primary language, with
  English and Portuguese translations, and an AST-based string-wrapping
  pipeline (`auto_wrap.py`) to keep new code translatable.

## Architecture

The app follows a **mixin composition** pattern for its largest screens:
`DiagramaConexiones`, the interactive connections diagram, is assembled
from several focused `*Mixin` classes rather than one monolithic class.

| Layer | Files |
|---|---|
| Entry point / main window, ABM | `cabledoc.py` |
| Data access (SQLite) | `modelo.py`, `schema_db.sql` |
| Shared screen utilities (i18n bootstrap, icons, Cairo primitives, `PALETA`) | `pantallas_comunes.py` |
| Rack / frame / connector screens | `rack_ui.py`, `frame_slots_ui.py`, `imagen_conectores_ui.py`, `arbol_conexiones_ui.py` |
| Patch panels | `patcheras_ui.py` |
| Bulk editors (connectors / slots, real equipment & catalog) | `editor_masivo_conectores_ui.py`, `editor_masivo_slots_ui.py` |
| Connections diagram + mixins | `diagrama_conexiones_ui.py`, `grafo_diagrama_ui.py`, `dibujo_diagrama_ui.py`, `interaccion_diagrama_ui.py`, `edicion_conexiones_diagrama_ui.py`, `layout_diagrama_ui.py`, `busqueda_diagrama_ui.py`, `export_diagrama_ui.py`, `ruteo_interno_diagrama_ui.py` |
| `pantallas_avanzadas.py` | Pure facade (see below) |
| Impact analysis engine | `graph_impact.py` |
| Signal state, propagation & lineage | `senal_estado.py`, `senal_propagation.py`, `senal_visual.py`, `senal_visual_ui.py`, `senal_diagrama_ui.py` |
| Structural / analog signal risk | `signal_risk.py`, `signal_risk_diagrama_ui.py`, `riesgo_analogico.py`, `risk_engine.py`, `riesgo_diagrama_ui.py` |
| Incident log | `bitacora_ui.py` |
| Cable extensions | `extension_cable_ui.py` |
| Fault diagnosis | `diagnostico_falla.py`, `diagnostico_ui.py` |
| Operational scenarios | `escenario_engine.py`, `escenario_ui.py` |
| Custom diagrams | `diagrama_personalizado.py` |
| Graph query console | `cypher_console.py` |
| Localization | `i18n.py` |
| About dialog | `acerca_de.py` (renders this `README.md` and `changelog.txt` inside the app) |
| One-off migration script | `convertir_archivos.py` (pixel → percentage coordinate migration) |

### `pantallas_avanzadas.py`: from ~11,000-line monolith to a pure facade

`pantallas_avanzadas.py` originally held ~11,032 lines covering every
advanced screen in the app. It has been fully split, over six incremental
deliveries, into the focused modules listed above. **As of the final
delivery, `pantallas_avanzadas.py` defines no classes or functions of its
own** — it only re-exports names (`ArbolConexionesEquipo`, `VistaRack`,
`PatcherasVista`, `VistaFrameSlots`, `DiagramaConexiones` and its helper
dialogs, the bulk editors, etc.) from their new homes, under the exact
names `cabledoc.py` and `diagrama_personalizado.py` used before the
refactor. This facade pattern meant neither of those two consumers needed
any changes across the whole refactor.

The legacy custom-node "classic editor" (`EditorConexiones`), superseded by
reusing `DiagramaConexiones` for quick connection entry, was removed
entirely in the final delivery — it had been disabled in the menu for
several sessions with no other consumer.

## Requirements

- Python 3
- GTK3 via PyGObject
- SQLite (standard library `sqlite3`)
- GraphQLite (SQLite extension, Rust/C, Cypher query support) for
  `graph_impact.py`'s graph-based impact analysis
- Pillow (optional, for image preview support)

```bash
apt install python3-gi gir1.2-gtk-3.0
pip install pygobject pillow
```

## Running

```bash
python3 cabledoc.py
```

On first run, if `database/db.db` does not exist yet, it is created
automatically from `schema_db.sql` (schema only, no data), along with the
`imagen/`, `manuales/`, and `picon/` support directories.

## Project structure

```
cabledoc.py                # Main entry point / main window / ABM
modelo.py                  # Data access layer (SQLite), class Modelo
schema_db.sql              # Full database schema (~44 tables, 14 views)
pantallas_avanzadas.py     # Facade re-exporting screens from their modules
diagrama_conexiones_ui.py  # Interactive connections diagram + dialogs
*_diagrama_ui.py           # DiagramaConexiones mixins (drawing, layout, search, ...)
rack_ui.py, patcheras_ui.py, frame_slots_ui.py,
imagen_conectores_ui.py, arbol_conexiones_ui.py  # Individual screens
editor_masivo_*_ui.py      # Bulk connector/slot editors
graph_impact.py            # "What breaks if I disconnect this?" engine
riesgo_analogico.py        # Analog risk scoring
signal_risk.py             # Structural signal risk
risk_engine.py             # Failure Risk Index (IRF)
bitacora_ui.py             # Incident log UI
extension_cable_ui.py      # Cable extension ("view full chain")
diagnostico_falla.py       # Fault diagnosis assistant
escenario_engine.py        # Operational scenario engine
diagrama_personalizado.py  # Free-form diagram editor
cypher_console.py          # Cypher-style graph query console
i18n.py                    # Localization (es / en / pt)
acerca_de.py                # "About" dialog (renders README.md + changelog.txt)
assets/                    # App icons and images
help/                      # User tutorials (Markdown) and technical write-ups (LaTeX/PDF)
database/db.db              # SQLite database (created on first run)
imagen/                    # Stored reference/connector images
manuales/                  # Equipment manuals
picon/                     # Equipment picons/icons
```

## Development notes

- **`pyflakes` is mandatory before any delivery is considered complete.**
  It is the only tool that reliably catches `NameError`s inside GTK draw
  callbacks — GTK silences these at runtime (a black surface or a missing
  node, not a crash), so `ast.parse` / `py_compile` / import-chain smoke
  tests alone are not enough.
- **Facade pattern**: as modules are extracted, they re-export their
  public names back through `pantallas_avanzadas.py`, so dependent modules
  need zero changes per delivery.
- **Anti-hardcoding principle**: behavior is driven by explicit catalog
  columns (`tipo_equipo.rol_senal`, `tipo_conector.direccion`, etc.) with
  `COALESCE()`-based overrides, never by matching equipment/connector
  *names* or IDs in business logic — new equipment/connector types must
  work correctly without any code change.
- **`senal_linaje` is documentation-only by design** and intentionally
  does not feed `graph_impact.py` — this separation is deliberate, not an
  oversight.
- **`FANTASMA` means confirmed absence in the field**, not "unknown" — the
  impact-propagation engine already handles it without special-casing.
- Deferred, in-method imports are the established pattern for breaking
  circular dependencies between `cabledoc.py` ↔ `pantallas_avanzadas.py` ↔
  the `*_ui.py` modules — this must be preserved in any further refactor.
- Every delivery updates `PROGRESS.md` / `PROGRESS_REFACTOR.md`, appends a
  timestamped, one-line-per-change entry to `changelog.txt`, and bumps
  `APP_VERSION` in `cabledoc.py` (format `1.YYYYMMDDHHMMSS`).
- User-facing help lives in `help/TUTORIAL_*.md`, updated alongside each
  user-visible feature.

## License

GNU General Public License v2.0 — see [`LICENSE`](./LICENSE).
