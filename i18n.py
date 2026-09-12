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
    "Equipos — Sin auditar": {
        "en": "Equipment — Not audited",
        "pt": "Equipamentos — Sem auditoria"},
    "Equipos — Sin manual": {
        "en": "Equipment — No manual",
        "pt": "Equipamentos — Sem manual"},
    "Equipos — Sin configuraciones": {
        "en": "Equipment — No configuration",
        "pt": "Equipamentos — Sem configurações"},
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
    "Alta Rápida…":          {"en": "Quick Add…",  "pt": "Adição Rápida…"},
    "Cableado":                 {"en": "Cabling",       "pt": "Cabeamento"},
    "Alta rápida de conexiones…": {
        "en": "Quick connection add…",
        "pt": "Adição rápida de conexões…"},
    "Infraestructura":          {"en": "Infrastructure","pt": "Infraestrutura"},
    "Posición en Racks":        {"en": "Rack Positions","pt": "Posições em Racks"},
    "Equipos sueltos por Sala": {
        "en": "Loose equipment by Room",
        "pt": "Equipamentos soltos por Sala"},
    "Vista gráfica de rack…":{
        "en": "Graphical rack view…",
        "pt": "Vista gráfica de rack…"},
    "Catálogos":                {"en": "Catalogs",      "pt": "Catálogos"},
    "Diagramas":                {"en": "Diagrams",      "pt": "Diagramas"},
    "Imagen con conectores…":{
        "en": "Image with connectors…",
        "pt": "Imagem com conectores…"},
    "Árbol de conexiones…":  {
        "en": "Connection tree…",
        "pt": "Árvore de conexões…"},
    "Vista de patcheras…":   {
        "en": "Patchbay view…",
        "pt": "Vista de patcheras…"},
    "Diagrama de conexiones…":{
        "en": "Connection diagram…",
        "pt": "Diagrama de conexões…"},
    "Idioma":                   {"en": "Language",      "pt": "Idioma"},

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
    "Equipos":              {"en": "Equipment",  "pt": "Equipamentos"},
    "Patcheras":             {"en": "Patchbays",  "pt": "Patcheras"},
    "Diagrama":              {"en": "Diagram",    "pt": "Diagrama"},
    "Cables":                {"en": "Cables",     "pt": "Cabos"},
    "Conexiones":            {"en": "Connections","pt": "Conexões"},
    "Racks":                {"en": "Racks",     "pt": "Racks"},
    "Vista Rack":            {"en": "Rack View",  "pt": "Vista Rack"},
    "Frames":                {"en": "Frames",     "pt": "Frames"},

    # ── Panel de pendientes — etiquetas de métricas ───────────────────────────
    "Temporales":    {"en": "Temporary",      "pt": "Temporários"},
    "En revisión":  {"en": "Under review",   "pt": "Em revisão"},
    "1⃣ 1 extremo":   {"en": "1⃣ 1 end",          "pt": "1⃣ 1 extremo"},
    "Sin conexión": {"en": "No connection",   "pt": "Sem conexão"},
    "Sin conectores":     {"en": "No connectors","pt": "Sem conectores"},
    "Sin imagen":         {"en": "No image",     "pt": "Sem imagem"},
    "Sin imagen c/ conect.": {
        "en": "No image w/ conn.",
        "pt": "Sem imagem c/ conect."},
    "Sin auditar":        {"en": "Not audited",  "pt": "Sem auditoria"},
    "Sin manual":         {"en": "No manual",    "pt": "Sem manual"},
    "Sin config.":        {"en": "No config.",   "pt": "Sem config."},
    "Sin slots":          {"en": "No slots",     "pt": "Sem slots"},
    "Sin imagen":         {"en": "No image",     "pt": "Sem imagem"},
    "Sin slot en imagen": {"en": "No slot in image","pt": "Sem slot na imagem"},

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
    "Idioma seleccionado. Reiniciá la aplicación para aplicar los cambios.": {
        "en": "Language selected. Restart the application to apply changes.",
        "pt": "Idioma selecionado. Reinicie o aplicativo para aplicar as alterações."},

    # ── Mensaje de BD no encontrada ───────────────────────────────────────────
    "Copiá db.db al directorio de la aplicación.": {
        "en": "Copy db.db to the application directory.",
        "pt": "Copie db.db para o diretório do aplicativo."},
}


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def set_lang(codigo: str) -> None:
    """Cambia el idioma activo. Persiste en ~/.config/cabledoc_lang."""
    global _idioma_actual
    if codigo in IDIOMAS_DISPONIBLES:
        _idioma_actual = codigo
        try:
            import os
            cfg = os.path.expanduser("~/.config/cabledoc_lang")
            os.makedirs(os.path.dirname(cfg), exist_ok=True)
            with open(cfg, "w") as f:
                f.write(codigo)
        except Exception:
            pass


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