# data/

Esta carpeta NO va al repositorio de git (agregar a `.gitignore`, ver
`plan_integracion_cabledoc_v3.md` §3). Se sincroniza por rclone/Gdrive
entre desktop y mobile (Fase 6 del plan).

- `database/db.db` — la base SQLite real (backup obligatorio antes de
  correr `Modelo.migrar_coordenadas_a_porcentaje()`, ver §7 del plan:
  "El más grande" de los riesgos).
- `imagen/` — fotos/SVGs de equipos, planos, layouts de conectores.
- `manuales/` — PDFs de manuales de equipo.
- `picon/` — picons (fotos chicas) de equipos.
- `schema_db.sql` — SÍ va al repo (es código: fuente de verdad del
  esquema + fixture para tests, ver validación estándar del proyecto).

Esta entrega la deja con `.gitkeep` vacíos: los datos reales de Papi/Fede
no se incluyen en este paquete por ser información de producción de la
instalación real, no artefacto de código.
