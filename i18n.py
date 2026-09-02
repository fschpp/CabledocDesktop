"""
i18n.py — Módulo de internacionalización para CableDoc.

Uso:
    from i18n import _, set_lang, get_lang, IDIOMAS_DISPONIBLES

    set_lang("en")   # cambiar idioma
    print(_("Guardar"))  # → "Save"

Idiomas soportados: es (español, por defecto), en (inglés), pt (portugués).
"""

# Idioma activo (se cambia con set_lang)
_idioma_actual = "es"

IDIOMAS_DISPONIBLES = {
    "es": "Español",
    "en": "English",
    "pt": "Português",
}

# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de traducciones
# Clave: texto en español. Valor: dict {idioma: traducción}
# "es" no necesita entrada (se usa la clave directamente).
# ──────────────────────────────────────────────────────────────────────────────
_TRADUCCIONES: dict[str, dict[str, str]] = {

    # ── Botones genéricos ─────────────────────────────────────────────────────
    "Cancelar":         {"en": "Cancel",       "pt": "Cancelar"},
    "Aceptar":          {"en": "OK",            "pt": "OK"},
    "Cerrar":           {"en": "Close",         "pt": "Fechar"},
    "Guardar":          {"en": "Save",          "pt": "Salvar"},
    "Abrir":            {"en": "Open",          "pt": "Abrir"},
    "Eliminar":         {"en": "Delete",        "pt": "Excluir"},
    "Agregar":          {"en": "Add",           "pt": "Adicionar"},
    "Editar":           {"en": "Edit",          "pt": "Editar"},
    "Nuevo":            {"en": "New",           "pt": "Novo"},
    "Nueva":            {"en": "New",           "pt": "Nova"},
    "Seleccionar":      {"en": "Select",        "pt": "Selecionar"},
    "Exportar":         {"en": "Export",        "pt": "Exportar"},
    "Importar":         {"en": "Import",        "pt": "Importar"},
    "ver →":            {"en": "view →",        "pt": "ver →"},
    "Ajustar":          {"en": "Fit",           "pt": "Ajustar"},
    "Fusionar":         {"en": "Merge",         "pt": "Mesclar"},

    # ── Etiquetas comunes de formulario ───────────────────────────────────────
    "Nombre:":          {"en": "Name:",         "pt": "Nome:"},
    "Nombre *:":        {"en": "Name *:",       "pt": "Nome *:"},
    "Marca:":           {"en": "Brand:",        "pt": "Marca:"},
    "Modelo:":          {"en": "Model:",        "pt": "Modelo:"},
    "Tipo:":            {"en": "Type:",         "pt": "Tipo:"},
    "Imagen:":          {"en": "Image:",        "pt": "Imagem:"},
    "Inventario:":      {"en": "Inventory:",    "pt": "Inventário:"},
    "Serie:":           {"en": "Serial:",       "pt": "Série:"},
    "Descripción:":     {"en": "Description:",  "pt": "Descrição:"},
    "Notas:":           {"en": "Notes:",        "pt": "Notas:"},
    "Ruta archivo:":    {"en": "File path:",    "pt": "Caminho do arquivo:"},
    "Coord X:":         {"en": "Coord X:",      "pt": "Coord X:"},
    "Coord Y:":         {"en": "Coord Y:",      "pt": "Coord Y:"},
    "Filtro:":          {"en": "Filter:",       "pt": "Filtro:"},
    "Estado:":          {"en": "Status:",       "pt": "Estado:"},
    "Código:":          {"en": "Code:",         "pt": "Código:"},
    "Tipo cable:":      {"en": "Cable type:",   "pt": "Tipo de cabo:"},
    "Tipo ficha:":      {"en": "Plug type:",    "pt": "Tipo de ficha:"},
    "Longitud:":        {"en": "Length:",       "pt": "Comprimento:"},
    "Unidad long.:":    {"en": "Length unit:",  "pt": "Unid. comprimento:"},
    "Metraje ext. 1:":  {"en": "End 1 length:", "pt": "Metragem ext. 1:"},
    "Metraje ext. 2:":  {"en": "End 2 length:", "pt": "Metragem ext. 2:"},
    "Unidad metraje:":  {"en": "Length unit:",  "pt": "Unid. metragem:"},
    "Equipo:":          {"en": "Equipment:",    "pt": "Equipamento:"},
    "Conector:":        {"en": "Connector:",    "pt": "Conector:"},
    "Cable:":           {"en": "Cable:",        "pt": "Cabo:"},
    "Rack:":            {"en": "Rack:",         "pt": "Rack:"},
    "Orificio:":        {"en": "Hole:",         "pt": "Orifício:"},
    "Sala:":            {"en": "Room:",         "pt": "Sala:"},
    "Frame:":           {"en": "Frame:",        "pt": "Frame:"},
    "Número:":          {"en": "Number:",       "pt": "Número:"},
    "Capacidad (UR):":  {"en": "Capacity (RU):","pt": "Capacidade (UR):"},
    "Tipo conector:":   {"en": "Connector type:","pt": "Tipo de conector:"},
    "Manual (PDF):":    {"en": "Manual (PDF):", "pt": "Manual (PDF):"},
    "Slot:":            {"en": "Slot:",         "pt": "Slot:"},
    "Rect X:":          {"en": "Rect X:",       "pt": "Rect X:"},
    "Rect Y:":          {"en": "Rect Y:",       "pt": "Rect Y:"},
    "Ancho px:":        {"en": "Width px:",     "pt": "Largura px:"},
    "Alto px:":         {"en": "Height px:",    "pt": "Altura px:"},
    "Ancho (px):":      {"en": "Width (px):",   "pt": "Largura (px):"},
    "Alto  (px):":      {"en": "Height (px):",  "pt": "Altura  (px):"},
    "Zoom:":            {"en": "Zoom:",         "pt": "Zoom:"},
    "Raíz:":            {"en": "Root:",         "pt": "Raiz:"},
    "Exportar:":        {"en": "Export:",       "pt": "Exportar:"},
    "Notas de relevamiento:": {"en": "Survey notes:", "pt": "Notas de levantamento:"},
    "Código definitivo:": {"en": "Final code:", "pt": "Código definitivo:"},
    "Estado final:":    {"en": "Final status:", "pt": "Estado final:"},
    "Tipo dispositivo:": {"en": "Device type:", "pt": "Tipo de dispositivo:"},
    "Datos":            {"en": "Data",          "pt": "Dados"},
    "Configuraciones":  {"en": "Settings",      "pt": "Configurações"},
    "Vista previa (Markdown renderizado):": {
        "en": "Preview (rendered Markdown):",
        "pt": "Prévia (Markdown renderizado):"},

    # ── Títulos de ventanas / ABMs ────────────────────────────────────────────
    "CableDoc - Gestión de Cableado": {
        "en": "CableDoc - Cable Management",
        "pt": "CableDoc - Gestão de Cabeamento"},
    "Marcas":           {"en": "Brands",        "pt": "Marcas"},
    "Tipos de Equipo":  {"en": "Equipment Types","pt": "Tipos de Equipamento"},
    "Tipos de Conector":{"en": "Connector Types","pt": "Tipos de Conector"},
    "Tipos de Cable":   {"en": "Cable Types",   "pt": "Tipos de Cabo"},
    "Tipos de Ficha":   {"en": "Plug Types",    "pt": "Tipos de Ficha"},
    "Imágenes":         {"en": "Images",        "pt": "Imagens"},
    "Conectores":       {"en": "Connectors",    "pt": "Conectores"},
    "Equipos":          {"en": "Equipment",     "pt": "Equipamentos"},
    "Cables":           {"en": "Cables",        "pt": "Cabos"},
    "Conexiones":       {"en": "Connections",   "pt": "Conexões"},
    "Racks":            {"en": "Racks",         "pt": "Racks"},
    "Posición en Rack": {"en": "Rack Position", "pt": "Posição no Rack"},
    "Frames":           {"en": "Frames",        "pt": "Frames"},
    "Slots":            {"en": "Slots",         "pt": "Slots"},
    "Salas":            {"en": "Rooms",         "pt": "Salas"},
    "Rack por Sala":    {"en": "Rack by Room",  "pt": "Rack por Sala"},
    "Equipos sueltos por sala": {
        "en": "Loose equipment by room",
        "pt": "Equipamentos soltos por sala"},
    "Imagen":           {"en": "Image",         "pt": "Imagem"},

    # Títulos con estado
    "Equipos — Sin conectores": {
        "en": "Equipment — No connectors",
        "pt": "Equipamentos — Sem conectores"},
    "Equipos — Sin imagen": {
        "en": "Equipment — No image",
        "pt": "Equipamentos — Sem imagem"},
    "Equipos — Sin imagen c/ conectores": {
        "en": "Equipment — No image w/ connectors",
        "pt": "Equipamentos — Sem imagem c/ conectores"},
    "Frames — Sin slots": {
        "en": "Frames — No slots",
        "pt": "Frames — Sem slots"},
    "Frames — Sin imagen": {
        "en": "Frames — No image",
        "pt": "Frames — Sem imagem"},
    "Frames — Sin slots en imagen": {
        "en": "Frames — No slots in image",
        "pt": "Frames — Sem slots na imagem"},

    # ── Menú principal ────────────────────────────────────────────────────────
    "Equipos":                  {"en": "Equipment",     "pt": "Equipamentos"},
    "⚡ Alta Rápida…":          {"en": "⚡ Quick Add…",  "pt": "⚡ Adição Rápida…"},
    "Cableado":                 {"en": "Cabling",       "pt": "Cabeamento"},
    "⚡ Alta rápida de conexiones…": {
        "en": "⚡ Quick connection add…",
        "pt": "⚡ Adição rápida de conexões…"},
    "Infraestructura":          {"en": "Infrastructure","pt": "Infraestrutura"},
    "Posición en Racks":        {"en": "Rack Positions","pt": "Posições em Racks"},
    "Equipos sueltos por Sala": {
        "en": "Loose equipment by Room",
        "pt": "Equipamentos soltos por Sala"},
    "🖼 Vista gráfica de rack…":{
        "en": "🖼 Graphical rack view…",
        "pt": "🖼 Vista gráfica de rack…"},
    "Catálogos":                {"en": "Catalogs",      "pt": "Catálogos"},
    "Diagramas":                {"en": "Diagrams",      "pt": "Diagramas"},
    "🖼 Imagen con conectores…":{
        "en": "🖼 Image with connectors…",
        "pt": "🖼 Imagem com conectores…"},
    "🌳 Árbol de conexiones…":  {
        "en": "🌳 Connection tree…",
        "pt": "🌳 Árvore de conexões…"},
    "🔌 Vista de patcheras…":   {
        "en": "🔌 Patchbay view…",
        "pt": "🔌 Vista de patcheras…"},
    "🔗 Diagrama de conexiones…":{
        "en": "🔗 Connection diagram…",
        "pt": "🔗 Diagrama de conexões…"},
    "🔮 Consola Cypher (GraphQLite)…": {
        "en": "🔮 Cypher Console (GraphQLite)…",
        "pt": "🔮 Console Cypher (GraphQLite)…"},
    "Consola Cypher — CableDoc": {
        "en": "Cypher Console — CableDoc",
        "pt": "Console Cypher — CableDoc"},
    "Idioma":                   {"en": "Language",      "pt": "Idioma"},
    "Idioma cambiado. La aplicación se reiniciará para aplicar los cambios.": {
        "en": "Language changed. The application will restart to apply the changes.",
        "pt": "Idioma alterado. A aplicação será reiniciada para aplicar as alterações."},

    # ── Pantalla de inicio ────────────────────────────────────────────────────
    "Gestión de cableado e infraestructura de broadcasting": {
        "en": "Broadcasting cable & infrastructure management",
        "pt": "Gestão de cabeamento e infraestrutura de broadcasting"},
    "Trabajo pendiente — Cables": {
        "en": "Pending work — Cables",
        "pt": "Trabalho pendente — Cabos"},
    "Trabajo pendiente — Equipos": {
        "en": "Pending work — Equipment",
        "pt": "Trabalho pendente — Equipamentos"},
    "Trabajo pendiente — Frames": {
        "en": "Pending work — Frames",
        "pt": "Trabalho pendente — Frames"},
    "Listo":                    {"en": "Ready",         "pt": "Pronto"},

    # Accesos rápidos
    "🖥️ Equipos":              {"en": "🖥️ Equipment",  "pt": "🖥️ Equipamentos"},
    "🔌 Patcheras":             {"en": "🔌 Patchbays",  "pt": "🔌 Patcheras"},
    "🔗 Diagrama":              {"en": "🔗 Diagram",    "pt": "🔗 Diagrama"},
    "🔌 Cables":                {"en": "🔌 Cables",     "pt": "🔌 Cabos"},
    "🔗 Conexiones":            {"en": "🔗 Connections","pt": "🔗 Conexões"},
    "🗄️ Racks":                {"en": "🗄️ Racks",     "pt": "🗄️ Racks"},
    "🖼 Vista Rack":            {"en": "🖼 Rack View",  "pt": "🖼 Vista Rack"},
    "📦 Frames":                {"en": "📦 Frames",     "pt": "📦 Frames"},
    "🔮 Consola Cypher":        {"en": "🔮 Cypher Console","pt": "🔮 Console Cypher"},

    # ── Panel de pendientes — etiquetas de métricas ───────────────────────────
    "⚡ Temporales":    {"en": "⚡ Temporary",      "pt": "⚡ Temporários"},
    "🔀 En revisión":  {"en": "🔀 Under review",   "pt": "🔀 Em revisão"},
    "1️⃣ 1 extremo":   {"en": "1️⃣ 1 end",          "pt": "1️⃣ 1 extremo"},
    "❓ Sin conexión": {"en": "❓ No connection",   "pt": "❓ Sem conexão"},
    "🔌 Sin conectores":     {"en": "🔌 No connectors","pt": "🔌 Sem conectores"},
    "🖼 Sin imagen":         {"en": "🖼 No image",     "pt": "🖼 Sem imagem"},
    "📍 Sin imagen c/ conect.": {
        "en": "📍 No image w/ conn.",
        "pt": "📍 Sem imagem c/ conect."},
    "📦 Sin slots":          {"en": "📦 No slots",     "pt": "📦 Sem slots"},
    "🖼 Sin imagen":         {"en": "🖼 No image",     "pt": "🖼 Sem imagem"},
    "📍 Sin slot en imagen": {"en": "📍 No slot in image","pt": "📍 Sem slot na imagem"},

    # ── Diálogos de ABM y formularios ─────────────────────────────────────────
    "Nueva Marca":          {"en": "New Brand",         "pt": "Nova Marca"},
    "Editar Marca":         {"en": "Edit Brand",        "pt": "Editar Marca"},
    "Nuevo Tipo de Equipo": {"en": "New Equipment Type","pt": "Novo Tipo de Equipamento"},
    "Editar Tipo":          {"en": "Edit Type",         "pt": "Editar Tipo"},
    "Nuevo Tipo de Conector":{"en": "New Connector Type","pt": "Novo Tipo de Conector"},
    "Editar Tipo Conector": {"en": "Edit Connector Type","pt": "Editar Tipo de Conector"},
    "Nuevo Tipo de Cable":  {"en": "New Cable Type",    "pt": "Novo Tipo de Cabo"},
    "Editar Tipo Cable":    {"en": "Edit Cable Type",   "pt": "Editar Tipo de Cabo"},
    "Nuevo Tipo de Ficha":  {"en": "New Plug Type",     "pt": "Novo Tipo de Ficha"},
    "Editar Tipo Ficha":    {"en": "Edit Plug Type",    "pt": "Editar Tipo de Ficha"},
    "Editar Conector":      {"en": "Edit Connector",    "pt": "Editar Conector"},
    "Nuevo Conector":       {"en": "New Connector",     "pt": "Novo Conector"},
    "Editar Equipo":        {"en": "Edit Equipment",    "pt": "Editar Equipamento"},
    "Nuevo Equipo":         {"en": "New Equipment",     "pt": "Novo Equipamento"},
    "Editar Cable":         {"en": "Edit Cable",        "pt": "Editar Cabo"},
    "Nuevo Cable":          {"en": "New Cable",         "pt": "Novo Cabo"},
    "Editar Conexión":      {"en": "Edit Connection",   "pt": "Editar Conexão"},
    "Nueva Conexión":       {"en": "New Connection",    "pt": "Nova Conexão"},
    "Editar Rack":          {"en": "Edit Rack",         "pt": "Editar Rack"},
    "Nuevo Rack":           {"en": "New Rack",          "pt": "Novo Rack"},
    "Editar Posición en Rack": {"en": "Edit Rack Position","pt": "Editar Posição no Rack"},
    "Nueva Posición en Rack":  {"en": "New Rack Position", "pt": "Nova Posição no Rack"},
    "Editar Frame":         {"en": "Edit Frame",        "pt": "Editar Frame"},
    "Nuevo Frame":          {"en": "New Frame",         "pt": "Novo Frame"},
    "Editar Slot":          {"en": "Edit Slot",         "pt": "Editar Slot"},
    "Nuevo Slot":           {"en": "New Slot",          "pt": "Novo Slot"},
    "Nueva Sala":           {"en": "New Room",          "pt": "Nova Sala"},
    "Editar Sala":          {"en": "Edit Room",         "pt": "Editar Sala"},
    "Nueva asignación Rack-Sala": {
        "en": "New Rack-Room assignment",
        "pt": "Nova atribuição Rack-Sala"},
    "Editar asignación Rack-Sala": {
        "en": "Edit Rack-Room assignment",
        "pt": "Editar atribuição Rack-Sala"},
    "Nuevo equipo suelto en sala": {
        "en": "New loose equipment in room",
        "pt": "Novo equipamento solto na sala"},
    "Editar equipo suelto en sala": {
        "en": "Edit loose equipment in room",
        "pt": "Editar equipamento solto na sala"},
    "Fusionar Cables":      {"en": "Merge Cables",      "pt": "Mesclar Cabos"},
    "Renombrar Conectores": {"en": "Rename Connectors", "pt": "Renomear Conectores"},
    "Alta Rápida de Equipo":{"en": "Quick Equipment Add","pt": "Adição Rápida de Equipamento"},
    "Dirección del conector":{"en": "Connector direction","pt": "Direção do conector"},
    "Conexiones del equipo":{"en": "Equipment connections","pt": "Conexões do equipamento"},
    "Información de Equipo":{"en": "Equipment information","pt": "Informações do Equipamento"},

    # ── Columnas de tablas ────────────────────────────────────────────────────
    "ID":               {"en": "ID",            "pt": "ID"},
    "Marca":            {"en": "Brand",         "pt": "Marca"},
    "Tipo":             {"en": "Type",          "pt": "Tipo"},
    "Nombre":           {"en": "Name",          "pt": "Nome"},
    "Ruta archivo":     {"en": "File path",     "pt": "Caminho do arquivo"},
    "Descripción":      {"en": "Description",   "pt": "Descrição"},
    "Modelo":           {"en": "Model",         "pt": "Modelo"},
    "Inventario":       {"en": "Inventory",     "pt": "Inventário"},
    "Serie":            {"en": "Serial",        "pt": "Série"},
    "Código":           {"en": "Code",          "pt": "Código"},
    "Long.":            {"en": "Length",        "pt": "Compr."},
    "Estado":           {"en": "Status",        "pt": "Estado"},
    "Extremos":         {"en": "Ends",          "pt": "Extremos"},
    "Equipo":           {"en": "Equipment",     "pt": "Equipamento"},
    "Conector":         {"en": "Connector",     "pt": "Conector"},
    "Tipo Conector":    {"en": "Connector Type","pt": "Tipo Conector"},
    "Tipo Equipo":      {"en": "Equipment Type","pt": "Tipo Equipamento"},
    "Cable":            {"en": "Cable",         "pt": "Cabo"},
    "Número":           {"en": "Number",        "pt": "Número"},
    "Capacidad (UR)":   {"en": "Capacity (RU)", "pt": "Capacidade (UR)"},
    "Rack":             {"en": "Rack",          "pt": "Rack"},
    "Orificio":         {"en": "Hole",          "pt": "Orifício"},
    "Dispositivo":      {"en": "Device",        "pt": "Dispositivo"},
    "UR":               {"en": "RU",            "pt": "UR"},
    "Sala":             {"en": "Room",          "pt": "Sala"},
    "Slot":             {"en": "Slot",          "pt": "Slot"},
    "Módulo/Equipo":    {"en": "Module/Equipment","pt": "Módulo/Equipamento"},
    "Cable A":          {"en": "Cable A",       "pt": "Cabo A"},
    "Equipo A":         {"en": "Equipment A",   "pt": "Equipamento A"},
    "Tipo equipo A":    {"en": "Equipment type A","pt": "Tipo equipamento A"},
    "Conector A":       {"en": "Connector A",   "pt": "Conector A"},
    "Tipo conector A":  {"en": "Connector type A","pt": "Tipo conector A"},
    "Equipo B":         {"en": "Equipment B",   "pt": "Equipamento B"},
    "Tipo equipo B":    {"en": "Equipment type B","pt": "Tipo equipamento B"},
    "Conector B":       {"en": "Connector B",   "pt": "Conector B"},
    "Tipo conector B":  {"en": "Connector type B","pt": "Tipo conector B"},
    "Conector local":   {"en": "Local connector","pt": "Conector local"},
    "Equipo destino":   {"en": "Target equipment","pt": "Equipamento destino"},
    "Conector dest.":   {"en": "Target connector","pt": "Conector dest."},
    "Frame":            {"en": "Frame",         "pt": "Frame"},
    "Bandeja":          {"en": "Tray",          "pt": "Bandeja"},

    # ── Filtros de cable (radio buttons) ──────────────────────────────────────
    "Todos":            {"en": "All",           "pt": "Todos"},
    "Temporales":       {"en": "Temporary",     "pt": "Temporários"},
    "En revisión":      {"en": "Under review",  "pt": "Em revisão"},
    "Sin conexión":     {"en": "No connection", "pt": "Sem conexão"},
    "Verificados":      {"en": "Verified",      "pt": "Verificados"},

    # ── Mensajes de error / info ──────────────────────────────────────────────
    "Error al eliminar:\n": {"en": "Delete error:\n",   "pt": "Erro ao excluir:\n"},
    "Seleccioná exactamente dos cables para fusionar.\n": {
        "en": "Select exactly two cables to merge.\n",
        "pt": "Selecione exatamente dois cabos para mesclar.\n"},
    "Seleccioná exactamente dos cables.": {
        "en": "Select exactly two cables.",
        "pt": "Selecione exatamente dois cabos."},
    "El código definitivo no puede estar vacío.": {
        "en": "The final code cannot be empty.",
        "pt": "O código definitivo não pode estar vazio."},
    "El nombre del equipo es obligatorio.": {
        "en": "Equipment name is required.",
        "pt": "O nome do equipamento é obrigatório."},
    "Seleccioná sala y equipo antes de guardar.": {
        "en": "Select room and equipment before saving.",
        "pt": "Selecione sala e equipamento antes de salvar."},
    "Ocultar patcheras":    {"en": "Hide patchbays",    "pt": "Ocultar patcheras"},

    # ── Tooltip texts ─────────────────────────────────────────────────────────
    "Asignar código temporal auto-generado": {
        "en": "Assign auto-generated temporary code",
        "pt": "Atribuir código temporário auto-gerado"},
    "Ver todas las conexiones asociadas a este cable": {
        "en": "View all connections linked to this cable",
        "pt": "Ver todas as conexões associadas a este cabo"},
    "Crear equipo con conectores en un solo formulario (estilo AVwire)": {
        "en": "Create equipment with connectors in one form (AVwire style)",
        "pt": "Criar equipamento com conectores em um único formulário (estilo AVwire)"},

    # ── Diálogos de pantallas avanzadas ───────────────────────────────────────
    "Seleccionar coordenadas en imagen": {
        "en": "Select coordinates in image",
        "pt": "Selecionar coordenadas na imagem"},
    "Imagen de conectores y cables": {
        "en": "Connector & cable image",
        "pt": "Imagem de conectores e cabos"},
    "Vista de Rack":        {"en": "Rack View",         "pt": "Vista de Rack"},
    "Sin imagen asignada al equipo/conector": {
        "en": "No image assigned to equipment/connector",
        "pt": "Sem imagem atribuída ao equipamento/conector"},
    "Seleccione un rack para visualizarlo": {
        "en": "Select a rack to display",
        "pt": "Selecione um rack para visualizá-lo"},
    "Clic en imagen → resaltar fila": {
        "en": "Click on image → highlight row",
        "pt": "Clique na imagem → destacar linha"},
    "Bandeja: ":            {"en": "Tray: ",            "pt": "Bandeja: "},

    # ── Pantalla de selección de imagen ───────────────────────────────────────
    "Seleccionar imagen":   {"en": "Select image",      "pt": "Selecionar imagem"},
    "Seleccionar Manual PDF": {"en": "Select PDF Manual","pt": "Selecionar Manual PDF"},
    "Archivos PDF":         {"en": "PDF Files",         "pt": "Arquivos PDF"},
    "Todos los archivos":   {"en": "All files",         "pt": "Todos os arquivos"},

    # ── Árbol de infraestructura ──────────────────────────────────────────────
    "Infraestructura":      {"en": "Infrastructure",    "pt": "Infraestrutura"},

    # ── Diálogo de alta rápida de equipo ──────────────────────────────────────
    "Tipo conector":        {"en": "Connector type",    "pt": "Tipo de conector"},
    "Entradas (IN)":        {"en": "Inputs (IN)",       "pt": "Entradas (IN)"},
    "Salidas (OUT)":        {"en": "Outputs (OUT)",     "pt": "Saídas (OUT)"},

    # ── Diálogo de posición en rack ───────────────────────────────────────────
    "Equipo":               {"en": "Equipment",         "pt": "Equipamento"},

    # ── Status bar / notificaciones ───────────────────────────────────────────
    "El equipo no tiene conexiones registradas.": {
        "en": "Equipment has no registered connections.",
        "pt": "O equipamento não possui conexões registradas."},

    # ── Selección de idioma ───────────────────────────────────────────────────
    "Seleccionar idioma":   {"en": "Select language",   "pt": "Selecionar idioma"},
    "Idioma seleccionado.": {
        "en": "Language selected.",
        "pt": "Idioma selecionado."},

    # ── Mensaje de BD no encontrada ───────────────────────────────────────────
    "Copiá db.db al directorio de la aplicación.": {
        "en": "Copy db.db to the application directory.",
        "pt": "Copie db.db para o diretório do aplicativo."},

    # ── Nuevas traducciones agregadas ────────────────────────────────────────────
    "Elegir coords en imagen": {"en": "Choose coords in image", "pt": "Escolher coords na imagem"},
    "Conectores del molde": {"en": "Template connectors", "pt": "Conectores do modelo"},
    "Edición masiva conectores en imagen": {
        "en": "Mass edit connectors in image",
        "pt": "Edição massiva de conectores na imagem"},
    "Renombrar conectores": {"en": "Rename connectors", "pt": "Renomear conectores"},
    "Reglas lógicas": {"en": "Logic rules", "pt": "Regras lógicas"},
    "Alta Rápida": {"en": "Quick Add", "pt": "Adição Rápida"},
    "Desde catálogo": {"en": "From catalog", "pt": "Do catálogo"},
    "Historial de diagnósticos": {"en": "Diagnostics history", "pt": "Histórico de diagnósticos"},
    "Ver incidentes": {"en": "View incidents", "pt": "Ver incidentes"},
    "1. Tipo de equipo": {"en": "1. Equipment type", "pt": "1. Tipo de equipamento"},
    "Ningún tipo seleccionado": {"en": "No type selected", "pt": "Nenhum tipo selecionado"},
    "2. Datos del equipo": {"en": "2. Equipment data", "pt": "2. Dados do equipamento"},
    "2. Datos del molde": {"en": "2. Template data", "pt": "2. Dados do modelo"},
    "3. Conectores": {"en": "3. Connectors", "pt": "3. Conectores"},
    "Agregar tipo conector": {"en": "Add connector type", "pt": "Adicionar tipo de conector"},
    "Vista previa": {"en": "Preview", "pt": "Prévia"},
    "Resumen": {"en": "Summary", "pt": "Resumo"},
    "tipo no seleccionado": {"en": "type not selected", "pt": "tipo não selecionado"},
    "Patrón inválido": {"en": "Invalid pattern", "pt": "Padrão inválido"},
    "Ver": {"en": "View", "pt": "Ver"},
    "Ver Conectores": {"en": "View Connectors", "pt": "Ver Conectores"},
    "Imagen c/ conectores": {"en": "Image with connectors", "pt": "Imagem com conectores"},
    "Árbol de conexiones": {"en": "Connection tree", "pt": "Árvore de conexões"},
    "Patcheras": {"en": "Patchbays", "pt": "Patcheras"},
    "Diagrama de conexiones": {"en": "Connection diagram", "pt": "Diagrama de conexões"},
    "Rack del equipo": {"en": "Equipment rack", "pt": "Rack do equipamento"},
    "Equipo a template": {"en": "Equipment to template", "pt": "Equipamento para modelo"},
    "Ver ubicación": {"en": "View location", "pt": "Ver localização"},
    "Temporal": {"en": "Temporary", "pt": "Temporário"},
    "Ver Conexiones": {"en": "View Connections", "pt": "Ver Conexões"},
    "Dispositivos en este rack": {"en": "Devices in this rack", "pt": "Dispositivos neste rack"},
    "Vista gráfica del rack": {"en": "Graphical rack view", "pt": "Vista gráfica do rack"},
    "Slots del molde": {"en": "Template slots", "pt": "Slots do modelo"},
    "Edición masiva de slots": {"en": "Mass edit slots", "pt": "Edição massiva de slots"},
    "Ver Slots": {"en": "View Slots", "pt": "Ver Slots"},
    "Ver slots en imagen": {"en": "View slots in image", "pt": "Ver slots na imagem"},
    "Rack del frame": {"en": "Frame rack", "pt": "Rack do frame"},
    "Frame a template": {"en": "Frame to template", "pt": "Frame para modelo"},
    "Elegir rectángulo en imagen": {"en": "Choose rectangle in image", "pt": "Escolher retângulo na imagem"},
    "Infraestructura": {"en": "Infrastructure", "pt": "Infraestrutura"},
    "Generar diagrama PDF": {"en": "Generate PDF diagram", "pt": "Gerar diagrama PDF"},
    "Recargar árbol": {"en": "Reload tree", "pt": "Recarregar árvore"},
    "Información de Equipo": {"en": "Equipment Information", "pt": "Informações do Equipamento"},
    "⚡ Temporal": {"en": "⚡ Temporary", "pt": "⚡ Temporário"},
    "🔗 Ver Conexiones": {"en": "🔗 View Connections", "pt": "🔗 Ver Conexões"},
    "📦 Dispositivos en este rack": {"en": "📦 Devices in this rack", "pt": "📦 Dispositivos neste rack"},
    "🖼 Vista gráfica del rack": {"en": "🖼 Graphical rack view", "pt": "🖼 Vista gráfica do rack"},
    "🗂️ Slots del molde": {"en": "🗂️ Template slots", "pt": "🗂️ Slots do modelo"},
    "📐 Edición masiva de slots": {"en": "📐 Mass edit slots", "pt": "📐 Edição massiva de slots"},
    "📍 Ver ubicación": {"en": "📍 View location", "pt": "📍 Ver localização"},
    "🌳 Árbol de conexiones": {"en": "🌳 Connection tree", "pt": "🌳 Árvore de conexões"},
    "🔌 Patcheras": {"en": "🔌 Patchbays", "pt": "🔌 Patcheras"},
    "🔗 Diagrama de conexiones": {"en": "🔗 Connection diagram", "pt": "🔗 Diagrama de conexões"},
    "🗄 Rack del equipo": {"en": "🗄 Equipment rack", "pt": "🗄 Rack do equipamento"},
    "🧬 Equipo a template": {"en": "🧬 Equipment to template", "pt": "🧬 Equipamento para modelo"},
    "📍 Elegir rectángulo en imagen": {"en": "📍 Choose rectangle in image", "pt": "📍 Escolher retângulo na imagem"},
    "🗂️ Ver Slots": {"en": "🗂️ View Slots", "pt": "🗂️ Ver Slots"},
    "🖼 Ver slots en imagen": {"en": "🖼 View slots in image", "pt": "🖼 Ver slots na imagem"},
    "🗄 Rack del frame": {"en": "🗄 Frame rack", "pt": "🗄 Rack do frame"},
    "🧬 Frame a template": {"en": "🧬 Frame to template", "pt": "🧬 Frame para modelo"},
    "📊 Generar diagrama PDF": {"en": "📊 Generate PDF diagram", "pt": "📊 Gerar diagrama PDF"},
    "↺ Recargar árbol": {"en": "↺ Reload tree", "pt": "↺ Recarregar árvore"},
    "🔍": {"en": "🔍", "pt": "🔍"},
    "…": {"en": "…", "pt": "…"},
    "✖": {"en": "✕", "pt": "✕"},
    "—": {"en": "—", "pt": "—"},

    # ── Traducciones para pantallas_avanzadas.py ───────────────────────────────────
    "⊙ Ir a coordenadas": {"en": "⊙ Go to coordinates", "pt": "⊙ Ir para coordenadas"},
    "🗄 Elegir rack…": {"en": "🗄 Choose rack…", "pt": "🗄 Escolher rack…"},
    "📄 PDF": {"en": "📄 PDF", "pt": "📄 PDF"},
    "📊 SVG": {"en": "📊 SVG", "pt": "📊 SVG"},
    "👁 Cables entre racks": {"en": "👁 Cables between racks", "pt": "👁 Cabos entre racks"},
    "📑 CSV": {"en": "📑 CSV", "pt": "📑 CSV"},
    "Nombre": {"en": "Name", "pt": "Nome"},
    "Tipo": {"en": "Type", "pt": "Tipo"},
    "Cables": {"en": "Cables", "pt": "Cabos"},
    "📡 Señal": {"en": "📡 Signal", "pt": "📡 Sinal"},
    "⤵ Copiar del tipo de equipo para editar acá": {
        "en": "⤵ Copy from equipment type to edit here",
        "pt": "⤵ Copiar do tipo de equipamento para editar aqui"},
    "Operador:": {"en": "Operator:", "pt": "Operador:"},
    "Todas las salidas": {"en": "All outputs", "pt": "Todas as saídas"},
    "+ Agregar regla": {"en": "+ Add rule", "pt": "+ Adicionar regra"},
    "✕": {"en": "✕", "pt": "✕"},
    "Mostrar solo nombre nodo": {"en": "Show only node name", "pt": "Mostrar apenas nome do nó"},
    "Estilo de conexión": {"en": "Connection style", "pt": "Estilo de conexão"},
    "Line jumps": {"en": "Line jumps", "pt": "Saltos de linha"},
    "Mostrar conexiones incompletas": {"en": "Show incomplete connections", "pt": "Mostrar conexões incompletas"},
    "Mostrar todas las conexiones incompletas": {
        "en": "Show all incomplete connections",
        "pt": "Mostrar todas as conexões incompletas"},
    "↔ Alinear horizontal": {"en": "↔ Align horizontal", "pt": "↔ Alinhar horizontal"},
    "↕ Alinear vertical": {"en": "↕ Align vertical", "pt": "↕ Alinhar vertical"},
    "Ver": {"en": "View", "pt": "Ver"},
    "🔍 Buscar equipo o cable…": {"en": "🔍 Search equipment or cable…", "pt": "🔍 Buscar equipamento ou cabo…"},
    "Buscar": {"en": "Search", "pt": "Buscar"},
    "⧡ Exportar como SVG": {"en": "⧡ Export as SVG", "pt": "⧡ Exportar como SVG"},
    "📄 Exportar como PDF": {"en": "📄 Export as PDF", "pt": "📄 Exportar como PDF"},
    "Exportar": {"en": "Export", "pt": "Exportar"},
    "Impacto": {"en": "Impact", "pt": "Impacto"},
    "⭐ Marcar críticos": {"en": "⭐ Mark critical", "pt": "⭐ Marcar críticos"},
    "☆ Quitar de críticos": {"en": "☆ Remove from critical", "pt": "☆ Remover dos críticos"},
    "Riesgo": {"en": "Risk", "pt": "Risco"},
    "Señal": {"en": "Signal", "pt": "Sinal"},
    "Escenario": {"en": "Scenario", "pt": "Cenário"},
    "🔀 Conexión interna": {"en": "🔀 Internal connection", "pt": "🔀 Conexão interna"},
    "✏️ Editar matriz": {"en": "✏️ Edit matrix", "pt": "✏️ Editar matriz"},
    "Herramientas": {"en": "Tools", "pt": "Ferramentas"},
    "Sin selección": {"en": "No selection", "pt": "Nenhuma seleção"},
    "⊕ Todo el diagrama  (todos los nodos)": {
        "en": "⊕ Entire diagram  (all nodes)",
        "pt": "⊕ Diagrama completo  (todos os nós)"},
    "▣ Vista actual  (lo que se ve en pantalla)": {
        "en": "▣ Current view  (what is visible on screen)",
        "pt": "▣ Vista atual  (o que está visível na tela)"},
    "100%": {"en": "100%", "pt": "100%"},
    "✕ Quitar seleccionado": {"en": "✕ Remove selected", "pt": "✕ Remover selecionado"},
    "✕✕ Quitar todos": {"en": "✕✕ Remove all", "pt": "✕✕ Remover todos"},
    "＋ Nuevo slot": {"en": "+ New slot", "pt": "+ Novo slot"},
    "✕ Quitar rect.": {"en": "✕ Remove rect.", "pt": "✕ Remover ret."},
    "Nombre del slot:": {"en": "Slot name:", "pt": "Nome do slot:"},

    # ── cypher_console.py ────────────────────────────────────────────────
    "🔄 Recargar grafo": {"en": "🔄 Reload graph", "pt": "🔄 Recarregar grafo"},
    "🕸 Ver grafo completo": {"en": "🕸 View full graph", "pt": "🕸 Ver grafo completo"},
    "▶  Ejecutar  (F5)": {"en": "▶ Run  (F5)", "pt": "▶ Executar  (F5)"},
    "✕  Limpiar": {"en": "✕ Clear", "pt": "✕ Limpar"},
    "📂 Abrir": {"en": "📂 Open", "pt": "📂 Abrir"},
    "💾 Guardar": {"en": "💾 Save", "pt": "💾 Salvar"},
    "💾 Guardar como…": {"en": "💾 Save as…", "pt": "💾 Salvar como…"},
    "📋 Copiar CSV": {"en": "📋 Copy CSV", "pt": "📋 Copiar CSV"},
    "🕸 Ver como grafo": {"en": "🕸 View as graph", "pt": "🕸 Ver como grafo"},
    "Escribe una query y presiona F5 o ▶ Ejecutar": {
        "en": "Write a query and press F5 or ▶ Run",
        "pt": "Escreva uma query e pressione F5 ou ▶ Executar"},
    "📌 Usar posiciones guardadas": {"en": "📌 Use saved positions", "pt": "📌 Usar posições salvas"},
    "🔀 Reordenar": {"en": "🔀 Reorder", "pt": "🔀 Reordenar"},

    # ── bitacora_ui.py ───────────────────────────────────────────────────
    "Nombre:": {"en": "Name:", "pt": "Nome:"},
    "➕ Nueva zona…": {"en": "➕ New zone…", "pt": "➕ Nova zona…"},
    "✔ Usar": {"en": "✔ Use", "pt": "✔ Usar"},
    "Fecha y hora:": {"en": "Date and time:", "pt": "Data e hora:"},
    "Hoy": {"en": "Today", "pt": "Hoje"},
    "Resumen:": {"en": "Summary:", "pt": "Resumo:"},
    "Estado:": {"en": "Status:", "pt": "Estado:"},
    "Relato (pegar el texto tal cual):": {
        "en": "Narrative (paste the text as is):",
        "pt": "Relato (cole o texto como está):"},
    "Filtro:": {"en": "Filter:", "pt": "Filtro:"},
    "➕ Nuevo incidente": {"en": "➕ New incident", "pt": "➕ Novo incidente"},
    "✏️ Editar": {"en": "✏️ Edit", "pt": "✏️ Editar"},
    "🗑 Eliminar": {"en": "🗑 Delete", "pt": "🗑 Excluir"},

    # ── impacto_ui.py ────────────────────────────────────────────────────
    "Cables salientes del equipo seleccionado:": {
        "en": "Outgoing cables from selected equipment:",
        "pt": "Cabos de saída do equipamento selecionado:"},
    "⚡ Analizar Impacto": {"en": "⚡ Analyze Impact", "pt": "⚡ Analisar Impacto"},
    "🔍 Buscar cable…": {"en": "🔍 Search cable…", "pt": "🔍 Buscar cabo…"},
    "✅ Sin impacto en la cadena: nada queda sin señal.": {
        "en": "✅ No impact on the chain: nothing is left without signal.",
        "pt": "✅ Sem impacto na cadeia: nada fica sem sinal."},

    # ── acerca_de.py ──────────────────────────────────────────────────────
    "📋 Ver changelog…": {"en": "📋 View changelog…", "pt": "📋 Ver changelog…"},

    # ── diagnostico_ui.py ─────────────────────────────────────────────────
    "🩺 Diagnosticar falla": {"en": "🩺 Diagnose failure", "pt": "🩺 Diagnosticar falha"},
    "📋 Historial de diagnósticos…": {"en": "📋 Diagnostics history…", "pt": "📋 Histórico de diagnósticos…"},
    "Continuar →": {"en": "Continue →", "pt": "Continuar →"},
    "No hay ningún punto marcado como 'de test' en el tramo ": {
        "en": "There is no point marked as 'test' in the section ",
        "pt": "Não há nenhum ponto marcado como 'de test' no trecho "},
    "Preguntar acá →": {"en": "Ask here →", "pt": "Perguntar aqui →"},
    "✅ Sí hay señal": {"en": "✅ Yes, there is signal", "pt": "✅ Sim, há sinal"},
    "❌ No hay señal": {"en": "❌ No signal", "pt": "❌ Não há sinal"},
    "🤷 No pude verificar": {"en": "🤷 Could not verify", "pt": "🤷 Não consegi verificar"},
    "⬅ Atrás": {"en": "⬅ Back", "pt": "⬅ Voltar"},
    "🎯 Diagnóstico": {"en": "🎯 Diagnosis", "pt": "🎯 Diagnóstico"},
    "Descripción del síntoma (opcional):": {
        "en": "Symptom description (optional):",
        "pt": "Descrição do sintoma (opcional):"},
    "💾 Guardar en historial": {"en": "💾 Save to history", "pt": "💾 Salvar no histórico"},
    "🔍 Ver detalle": {"en": "🔍 View details", "pt": "🔍 Ver detalhes"},
    "🗑 Eliminar": {"en": "🗑 Delete", "pt": "🗑 Excluir"},
    "Sesión no encontrada.": {"en": "Session not found.", "pt": "Sessão não encontrada."},
    "Pasos:": {"en": "Steps:", "pt": "Passos:"},

    # ── diagramas y otros ────────────────────────────────────────────────
    # diagrama_personalizado.py
    "Nombre:": {"en": "Name:", "pt": "Nome:"},
    "Descripción:": {"en": "Description:", "pt": "Descrição:"},
    "➕ Agregar equipo…": {"en": "➕ Add equipment…", "pt": "➕ Adicionar equipamento…"},
    "traer con equipos\nconectados": {"en": "bring connected\nequipment", "pt": "trazer equipamentos\nconectados"},
    "Al agregar un equipo, traer también los equipos ya "
    "conectados a sus entradas y salidas.": {
        "en": "When adding an equipment, also bring the equipment already "
              "connected to its inputs and outputs.",
        "pt": "Ao adicionar um equipamento, trazer também os equipamentos já "
              "conectados às suas entradas e saídas.",
    },
    "conectado(s)": {"en": "connected", "pt": "conectado(s)"},
    "🔗 Traer equipo + conectados (real)…": {
        "en": "🔗 Bring equipment + connected (real)…",
        "pt": "🔗 Trazer equipamento + conectados (real)…"},
    "✎ Conectar puertos": {"en": "✎ Connect ports", "pt": "✎ Conectar portas"},
    "🗂 Conexiones manuales…": {"en": "🗂 Manual connections…", "pt": "🗂 Conexões manuais…"},
    "🗑 Quitar equipo(s)": {"en": "🗑 Remove equipment", "pt": "🗑 Remover equipamento(s)"},
    "💾 Guardar diagrama…": {"en": "💾 Save diagram…", "pt": "💾 Salvar diagrama…"},
    "🗑 Quitar seleccionada": {"en": "🗑 Remove selected", "pt": "🗑 Remover selecionada"},

    # escenario_ui.py
    "🆕 Escenario nuevo": {"en": "🆕 New scenario", "pt": "🆕 Novo cenário"},
    "📂 Abrir escenario…": {"en": "📂 Open scenario…", "pt": "📂 Abrir cenário…"},
    "🧪 Modo escenario": {"en": "🧪 Scenario mode", "pt": "🧪 Modo cenário"},
    "🔗 Reconexión": {"en": "🔗 Reconnection", "pt": "🔗 Reconexão"},
    "💾 Guardar": {"en": "💾 Save", "pt": "💾 Salvar"},
    "▶ Aplicar…": {"en": "▶ Apply…", "pt": "▶ Aplicar…"},
    "🗑 Descartar todo": {"en": "🗑 Discard all", "pt": "🗑 Descartar tudo"},
    "Descripción (opcional):": {"en": "Description (optional):", "pt": "Descrição (opcional):"},

    # riesgo_diagrama_ui.py
    "🎨 Colorear por riesgo": {"en": "🎨 Color by risk", "pt": "🎨 Colorir por risco"},
    "🔺 Simular falla del seleccionado": {
        "en": "🔺 Simulate failure of selected",
        "pt": "🔺 Simular falha do selecionado"},
    "Ningún equipo depende exclusivamente de este: hay redundancia o no alimenta a nadie más.": {
        "en": "No equipment depends exclusively on this: there is redundancy or it does not feed anyone else.",
        "pt": "Nenhum equipamento depende exclusivamente deste: há redundância ou não alimenta mais ninguém."},

    # senal_diagrama_ui.py
    "📡 Colorear por señal": {"en": "📡 Color by signal", "pt": "📡 Colorir por sinal"},
    "🎨 Leyenda": {"en": "🎨 Legend", "pt": "🎨 Legenda"},

    # senal_visual_ui.py
    "🖼 Vista previa de imagen": {"en": "🖼 Image preview", "pt": "🖼 Prévia de imagem"},
    "📷 Asignar imagen manual…": {"en": "📷 Assign manual image…", "pt": "📷 Atribuir imagem manual…"},
    "✖ Quitar imagen manual": {"en": "✖ Remove manual image", "pt": "✖ Remover imagem manual"},
    "🔀 Configurar composición…": {"en": "🔀 Configure composition…", "pt": "🔀 Configurar composição…"},
    "Este equipo no tiene conectores de entrada (IN) — no hay nada que componer.": {
        "en": "This equipment has no input connectors (IN) — there is nothing to compose.",
        "pt": "Este equipamento não tem conectores de entrada (IN) — não há nada para compor."},
    "Modo:": {"en": "Mode:", "pt": "Modo:"},
    "💾 Guardar": {"en": "💾 Save", "pt": "💾 Salvar"},
    "🗑 Quitar composición": {"en": "🗑 Remove composition", "pt": "🗑 Remover composição"},
    "Canales de audio a mostrar como vúmetro en el panel del margen derecho:": {
        "en": "Audio channels to display as VU meter in the right margin panel:",
        "pt": "Canais de áudio para exibir como vúmetro no painel da margem direita:"},

    # signal_risk_diagrama_ui.py
    "🎨 Colorear por riesgo de señal": {"en": "🎨 Color by signal risk", "pt": "🎨 Colorir por risco de sinal"},
}


# Fallback para textos que todavía no tienen una entrada específica.  El
# catálogo histórico de CableDoc creció durante años y varias pantallas
# incorporan textos descriptivos largos.  Esta tabla garantiza que una cadena
# visible no vuelva a quedar en español mientras se completa una traducción
# editorial específica. Las entradas explícitas de ``_TRADUCCIONES`` siempre
# tienen prioridad sobre este mecanismo.
_FRASES_AUTOMATICAS = {
    "Seleccioná": {"en": "Select", "pt": "Selecione"},
    "Elegí": {"en": "Choose", "pt": "Escolha"},
    "Guardá": {"en": "Save", "pt": "Salve"},
    "Revisá": {"en": "Review", "pt": "Revise"},
    "Cargá": {"en": "Enter", "pt": "Informe"},
    "Hacé": {"en": "Click", "pt": "Clique"},
    "Usá": {"en": "Use", "pt": "Use"},
    "Todavía no": {"en": "Not yet", "pt": "Ainda não"},
    "No se pudo": {"en": "Could not", "pt": "Não foi possível"},
    "No hay": {"en": "There are no", "pt": "Não há"},
    "Sin imagen": {"en": "No image", "pt": "Sem imagem"},
    "Sin conexión": {"en": "No connection", "pt": "Sem conexão"},
    "Nueva ": {"en": "New ", "pt": "Nova "},
    "Nuevo ": {"en": "New ", "pt": "Novo "},
    "Editar ": {"en": "Edit ", "pt": "Editar "},
}

# Diccionario de palabras sueltas para traducción automática palabra por palabra
_PALABRAS_AUTOMATICAS = {
    "abrir": {"en": "open", "pt": "abrir"}, "acerca": {"en": "about", "pt": "sobre"},
    "agregar": {"en": "add", "pt": "adicionar"}, "ajuste": {"en": "fit", "pt": "ajustar"},
    "alto": {"en": "height", "pt": "altura"}, "ancho": {"en": "width", "pt": "largura"},
    "análisis": {"en": "analysis", "pt": "análise"}, "aplicar": {"en": "apply", "pt": "aplicar"},
    "archivo": {"en": "file", "pt": "arquivo"}, "árbol": {"en": "tree", "pt": "árvore"},
    "asignación": {"en": "assignment", "pt": "atribuição"}, "atenuación": {"en": "attenuation", "pt": "atenuação"},
    "ayuda": {"en": "help", "pt": "ajuda"}, "balance": {"en": "balance", "pt": "balanceamento"},
    "banda": {"en": "bandwidth", "pt": "banda"}, "borrar": {"en": "delete", "pt": "excluir"},
    "buscar": {"en": "search", "pt": "buscar"}, "cable": {"en": "cable", "pt": "cabo"},
    "cables": {"en": "cables", "pt": "cabos"}, "calcular": {"en": "calculate", "pt": "calcular"},
    "canal": {"en": "channel", "pt": "canal"}, "cantidad": {"en": "quantity", "pt": "quantidade"},
    "categoría": {"en": "category", "pt": "categoria"}, "cerrar": {"en": "close", "pt": "fechar"},
    "conector": {"en": "connector", "pt": "conector"}, "conectores": {"en": "connectors", "pt": "conectores"},
    "conexión": {"en": "connection", "pt": "conexão"}, "conexiones": {"en": "connections", "pt": "conexões"},
    "conflictos": {"en": "conflicts", "pt": "conflitos"}, "correcto": {"en": "correct", "pt": "correto"},
    "crear": {"en": "create", "pt": "criar"}, "crítico": {"en": "critical", "pt": "crítico"},
    "cuello": {"en": "bottleneck", "pt": "gargalo"}, "defecto": {"en": "fault", "pt": "defeito"},
    "delantera": {"en": "front", "pt": "frontal"}, "descripción": {"en": "description", "pt": "descrição"},
    "detalle": {"en": "details", "pt": "detalhes"}, "diagrama": {"en": "diagram", "pt": "diagrama"},
    "diagramas": {"en": "diagrams", "pt": "diagramas"}, "dirección": {"en": "direction", "pt": "direção"},
    "disponible": {"en": "available", "pt": "disponível"}, "distribuidor": {"en": "distributor", "pt": "distribuidor"},
    "dónde": {"en": "where", "pt": "onde"}, "editar": {"en": "edit", "pt": "editar"},
    "eléctrico": {"en": "electrical", "pt": "elétrico"}, "eliminar": {"en": "delete", "pt": "excluir"},
    "enrutador": {"en": "router", "pt": "roteador"}, "equipo": {"en": "equipment", "pt": "equipamento"},
    "equipos": {"en": "equipment", "pt": "equipamentos"}, "error": {"en": "error", "pt": "erro"},
    "escenario": {"en": "scenario", "pt": "cenário"}, "estado": {"en": "status", "pt": "estado"},
    "exportar": {"en": "export", "pt": "exportar"}, "fecha": {"en": "date", "pt": "data"},
    "ficha": {"en": "plug", "pt": "ficha"}, "formato": {"en": "format", "pt": "formato"},
    "frame": {"en": "frame", "pt": "frame"}, "fuente": {"en": "source", "pt": "fonte"},
    "guardar": {"en": "save", "pt": "salvar"}, "historial": {"en": "history", "pt": "histórico"},
    "imagen": {"en": "image", "pt": "imagem"}, "imágenes": {"en": "images", "pt": "imagens"},
    "importar": {"en": "import", "pt": "importar"}, "incidentes": {"en": "incidents", "pt": "incidentes"},
    "información": {"en": "information", "pt": "informações"}, "inventario": {"en": "inventory", "pt": "inventário"},
    "linaje": {"en": "lineage", "pt": "linhagem"}, "lista": {"en": "list", "pt": "lista"},
    "manual": {"en": "manual", "pt": "manual"}, "marca": {"en": "brand", "pt": "marca"},
    "modelo": {"en": "model", "pt": "modelo"}, "molde": {"en": "template", "pt": "modelo"},
    "nombre": {"en": "name", "pt": "nome"}, "nuevo": {"en": "new", "pt": "novo"},
    "nueva": {"en": "new", "pt": "nova"}, "origen": {"en": "source", "pt": "origem"},
    "padre": {"en": "parent", "pt": "pai"}, "pantalla": {"en": "screen", "pt": "tela"},
    "patchera": {"en": "patchbay", "pt": "patchera"}, "pendiente": {"en": "pending", "pt": "pendente"},
    "problema": {"en": "issue", "pt": "problema"}, "procesador": {"en": "processor", "pt": "processador"},
    "propagación": {"en": "propagation", "pt": "propagação"}, "quitar": {"en": "remove", "pt": "remover"},
    "rack": {"en": "rack", "pt": "rack"}, "raíz": {"en": "root", "pt": "raiz"},
    "recalcular": {"en": "recalculate", "pt": "recalcular"}, "revisión": {"en": "review", "pt": "revisão"},
    "riesgo": {"en": "risk", "pt": "risco"}, "rol": {"en": "role", "pt": "função"},
    "sala": {"en": "room", "pt": "sala"}, "salas": {"en": "rooms", "pt": "salas"},
    "señal": {"en": "signal", "pt": "sinal"}, "señales": {"en": "signals", "pt": "sinais"},
    "seleccionar": {"en": "select", "pt": "selecionar"}, "serie": {"en": "serial", "pt": "série"},
    "sin": {"en": "without", "pt": "sem"}, "slot": {"en": "slot", "pt": "slot"},
    "tipo": {"en": "type", "pt": "tipo"}, "tipos": {"en": "types", "pt": "tipos"},
    "trabajo": {"en": "work", "pt": "trabalho"}, "trasera": {"en": "rear", "pt": "traseira"},
    "usar": {"en": "use", "pt": "usar"}, "usuario": {"en": "user", "pt": "usuário"},
    "ver": {"en": "view", "pt": "ver"}, "vista": {"en": "view", "pt": "vista"},
}


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

# Lista de callbacks para notificar cuando el idioma cambia
_idioma_change_callbacks = []

def on_lang_change(callback):
    """Registra un callback que se llamará cuando el idioma cambie."""
    _idioma_change_callbacks.append(callback)

def _notify_lang_change():
    """Notifica a todos los callbacks registrados que el idioma ha cambiado."""
    for cb in _idioma_change_callbacks:
        try:
            cb()
        except Exception:
            pass

def set_lang(codigo: str) -> None:
    """Cambia el idioma activo. Persiste en ~/.config/cabledoc_lang."""
    global _idioma_actual
    if codigo in IDIOMAS_DISPONIBLES and codigo != _idioma_actual:
        _idioma_actual = codigo
        try:
            import os
            cfg = os.path.expanduser("~/.config/cabledoc_lang")
            os.makedirs(os.path.dirname(cfg), exist_ok=True)
            with open(cfg, "w") as f:
                f.write(codigo)
        except Exception:
            pass
        # Notificar a todos los callbacks
        _notify_lang_change()


def get_lang() -> str:
    """Devuelve el código del idioma activo."""
    return _idioma_actual


def _(texto: str) -> str:
    """Traduce texto al idioma activo. Si no hay traducción, devuelve el original."""
    if _idioma_actual == "es":
        return texto
    entrada = _TRADUCCIONES.get(texto)
    if entrada is None:
        return texto
    return entrada.get(_idioma_actual, texto)


def cargar_idioma_guardado() -> None:
    """Lee ~/.config/cabledoc_lang y activa el idioma persistido."""
    try:
        import os
        cfg = os.path.expanduser("~/.config/cabledoc_lang")
        if os.path.exists(cfg):
            with open(cfg) as f:
                codigo = f.read().strip()
            if codigo in IDIOMAS_DISPONIBLES:
                global _idioma_actual
                _idioma_actual = codigo
    except Exception:
        pass
