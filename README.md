# CabledocDesktop
Broadcast Cable and Infrastructure managment software

**CableDoc** is a desktop application for documenting and managing the cabling
infrastructure of a broadcast television facility: racks, equipment, frames,
connectors, cables, signal routing, and impact/risk analysis for a mixed
analog/digital signal chain.

Originally a VB.NET/WinForms application, CableDoc has been fully rewritten in
**Python 3** with **GTK3 (PyGObject)** and **SQLite**.

> The application's UI, domain terminology, and internal documentation are in
> **Spanish**, since it is built for and used by a real broadcast facility.
> This README is in English for the repository; screens, field names, and
> in-app help remain in Spanish.

---

## What it does

- **Physical infrastructure documentation**: rooms, racks, frames, slots,
  equipment, connectors, and cables, with position/coordinate data over
  reference images.
- **Cable & connector tracking**: full connection graph between equipment,
  including patch panels (`patcheras`), routers/matrices (`ENRUTADOR`),
  embedders, and other signal-shaping devices.
- **Signal chain modeling**: signals (`senal`) can be traced through
  connectors, with role tagging (`rol_senal`) and a documentation-only
  lineage graph (`senal_linaje`) that records how a signal was derived
  without feeding it into automated impact analysis.
- **"What breaks if I disconnect this?" impact analysis**
  (`graph_impact.py`): propagates the effect of removing a cable/connector/
  equipment across logical rules (`regla_logica`) and routing matrices,
  and reports exactly which downstream equipment and rules are affected.
- **Visual diagrams**: Cairo-rendered rack views, signal-flow diagrams, and
  custom free-form diagrams (`diagrama_personalizado.py`), plus signal-risk
  diagrams and connection trees.
- **Incident log & analog risk tracking** (`bitacora_ui.py`,
  `riesgo_analogico.py`): records incidents, flags "suspect zones"
  (`zona_sospechosa`), and scores analog-chain risk using configurable,
  linear-decay weighting — aimed at facilities with a fully digital video
  path but an aging, incident-prone analog audio chain.
- **Fault diagnosis assistant** (`diagnostico_falla.py`,
  `diagnostico_ui.py`): guided troubleshooting based on the documented
  signal chain and past incidents.
- **Operational scenarios** (`escenario_engine.py`, `escenario_ui.py`):
  model and compare contingency/operational configurations against the
  documented infrastructure.
- **Cypher-style query console** (`cypher_console.py`) for ad-hoc graph
  queries over the documented topology.
- **Multi-language UI layer** (`i18n.py`), with Spanish as the primary,
  fully supported language.

## Architecture

| Layer | Files |
|---|---|
| Entry point / main window | `cabledoc.py` |
| Data access (SQLite) | `modelo.py`, `schema_db.sql` |
| Advanced screens (racks, connectors, patch panels, image coordinates) | `pantallas_avanzadas.py` *(being modularized — see below)* |
| Impact analysis engine | `graph_impact.py` |
| Signal state, propagation & lineage | `senal_estado.py`, `senal_propagation.py`, `senal_visual.py`, `senal_visual_ui.py`, `senal_diagrama_ui.py` |
| Structural / analog signal risk | `signal_risk.py`, `signal_risk_diagrama_ui.py`, `riesgo_analogico.py`, `risk_engine.py`, `riesgo_diagrama_ui.py` |
| Incident log | `bitacora_ui.py` |
| Fault diagnosis | `diagnostico_falla.py`, `diagnostico_ui.py` |
| Operational scenarios | `escenario_engine.py`, `escenario_ui.py` |
| Custom diagrams | `diagrama_personalizado.py` |
| Graph query console | `cypher_console.py` |
| Localization | `i18n.py` |
| About dialog | `acerca_de.py` (renders this `README.md` and `changelog.txt` inside the app) |

`pantallas_avanzadas.py` started as a single ~11,000-line module and is being
incrementally split into focused modules (`rack_ui.py`,
`imagen_conectores_ui.py`, `arbol_conexiones_ui.py`, `frame_slots_ui.py`,
etc.), re-exported through a facade in `pantallas_avanzadas.py` so that
`cabledoc.py` and `diagrama_personalizado.py` require no changes as the
refactor proceeds. Progress is tracked in `PROGRESS_REFACTOR.md` and
`changelog.txt`.

## Requirements

- Python 3
- GTK3 via PyGObject
- SQLite (standard library `sqlite3`)
- [Graphviz](https://graphviz.org/) (`dot`) for certain diagram generation
- Pillow (optional, for image preview support)

```bash
apt install python3-gi gir1.2-gtk-3.0 graphviz
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
cabledoc.py              # Main entry point / main window
modelo.py                 # Data access layer (SQLite)
schema_db.sql             # Full database schema
pantallas_avanzadas.py    # Advanced screens (in active refactor)
graph_impact.py           # "What breaks if I disconnect this?" engine
riesgo_analogico.py       # Analog risk scoring
signal_risk.py            # Structural signal risk
bitacora_ui.py            # Incident log UI
diagnostico_falla.py      # Fault diagnosis assistant
escenario_engine.py       # Operational scenario engine
diagrama_personalizado.py # Free-form diagram editor
i18n.py                   # Localization
assets/                   # App icons and images
database/db.db            # SQLite database (created on first run)
imagen/                   # Stored reference/connector images
manuales/                 # Equipment manuals
picon/                    # Equipment picons/icons
changelog.txt             # Versioned, timestamped change history (Spanish)
PROGRESS_REFACTOR.md       # Refactor delivery tracking
```

## Development notes

- **`pyflakes` is run before every delivery.** It is the only check that
  reliably catches `NameError`s inside GTK draw callbacks — GTK silences
  these at runtime (you get a black surface or a missing node, not a
  crash), so `ast.parse` and import-chain smoke tests alone are not enough.
- **Facade pattern**: as `pantallas_avanzadas.py` is split up, extracted
  modules re-export their public names back through it, so dependent
  modules need zero changes per delivery.
- **`senal_linaje` is documentation-only** by design and intentionally does
  not feed `graph_impact.py` — this separation is a deliberate design
  decision, not an oversight.
- **Anti-hardcoding principle**: signal/connector roles are resolved via
  explicit DB columns and `COALESCE()`-based overrides (the `rol_senal`
  mechanism) rather than by matching hardcoded Spanish/English strings.
- Every delivery updates `PROGRESS_REFACTOR.md` (or `PROGRESS.md`), appends a
  timestamped entry to `changelog.txt`, and bumps `APP_VERSION` in
  `cabledoc.py`.

## License

_Not yet specified._
