"""CableDoc Web — i18n del shell (plan_pyodide_v1.md, Fase A.2).

Reusa el catálogo de `core/i18n.py` (es/en/pt) y le suma las cadenas que solo
existen en la UI web. Así `core/` no cambia (y `core.zip` tampoco): las claves
nuevas viven acá, en español, igual que en el resto del proyecto.

`diccionario(lang)` devuelve `{clave_es: traduccion}` para ese idioma; el JS
hace `t(clave)` contra ese dict y, si no hay traducción, muestra la clave.
Las claves de `_WEB` pisan a las de `core` si coinciden.
"""
import json

IDIOMAS = {"es": "Español", "en": "English", "pt": "Português"}

_WEB = {
    # Navegación (una entrada por pantalla del plan, fases A.3 a A.11)
    "Inicio":               {"en": "Home",              "pt": "Início"},
    "Equipos":              {"en": "Equipment",         "pt": "Equipamentos"},
    "Cables":               {"en": "Cables",            "pt": "Cabos"},
    "Conexiones":           {"en": "Connections",       "pt": "Conexões"},
    "Ubicaciones":          {"en": "Locations",         "pt": "Localizações"},
    "Análisis":             {"en": "Analysis",          "pt": "Análise"},
    "Escenarios":           {"en": "Scenarios",         "pt": "Cenários"},
    "Búsqueda":             {"en": "Search",            "pt": "Busca"},
    "Datos":                {"en": "Data",              "pt": "Dados"},
    "Diagnóstico técnico":  {"en": "Technical diagnostics", "pt": "Diagnóstico técnico"},
    # Shell
    "Menú":                 {"en": "Menu",              "pt": "Menu"},
    "Idioma":               {"en": "Language",          "pt": "Idioma"},
    "Tema":                 {"en": "Theme",             "pt": "Tema"},
    "Automático":           {"en": "Automatic",         "pt": "Automático"},
    "Claro":                {"en": "Light",             "pt": "Claro"},
    "Oscuro":               {"en": "Dark",              "pt": "Escuro"},
    "Cargando…":            {"en": "Loading…",          "pt": "Carregando…"},
    "Iniciando el motor (Pyodide)…": {"en": "Starting the engine (Pyodide)…", "pt": "Iniciando o motor (Pyodide)…"},
    "Modo solo lectura":    {"en": "Read-only mode",    "pt": "Modo somente leitura"},
    "Saltar al contenido":  {"en": "Skip to content",   "pt": "Ir para o conteúdo"},
    # Base de datos
    "Falta la base de datos": {"en": "No database loaded", "pt": "Falta o banco de dados"},
    "Cargá el archivo db.db para empezar. Queda guardado en este navegador.":
        {"en": "Load the db.db file to get started. It is kept in this browser.",
         "pt": "Carregue o arquivo db.db para começar. Ele fica salvo neste navegador."},
    "Elegir db.db":         {"en": "Choose db.db",      "pt": "Escolher db.db"},
    "Base cargada ({kb} KB)": {"en": "Database loaded ({kb} KB)", "pt": "Banco carregado ({kb} KB)"},
    # Inicio
    "Resumen de la instalación": {"en": "Installation summary", "pt": "Resumo da instalação"},
    "Cables externos":      {"en": "External cables",   "pt": "Cabos externos"},
    "Conectores":           {"en": "Connectors",        "pt": "Conectores"},
    "Salas":                {"en": "Rooms",             "pt": "Salas"},
    "Racks":                {"en": "Racks",             "pt": "Racks"},
    "Frames":               {"en": "Frames",            "pt": "Frames"},
    # Pantallas pendientes
    "Disponible en la etapa {etapa} del plan.":
        {"en": "Available in stage {etapa} of the plan.", "pt": "Disponível na etapa {etapa} do plano."},
    # Equipos (A.3)
    "Buscar equipo, rack, frame…": {"en": "Search equipment, rack, frame…", "pt": "Buscar equipamento, rack, frame…"},
    "Expandir todo":        {"en": "Expand all",        "pt": "Expandir tudo"},
    "Contraer todo":        {"en": "Collapse all",      "pt": "Recolher tudo"},
    "Expandir":             {"en": "Expand",            "pt": "Expandir"},
    "Contraer":             {"en": "Collapse",          "pt": "Recolher"},
    "{n} equipos":          {"en": "{n} equipment",     "pt": "{n} equipamentos"},
    "{n} coincidencias":    {"en": "{n} matches",       "pt": "{n} correspondências"},
    "Sin resultados":       {"en": "No results",        "pt": "Sem resultados"},
    "No hay equipos cargados": {"en": "No equipment loaded", "pt": "Nenhum equipamento carregado"},
    "Sin ubicación":        {"en": "No location",       "pt": "Sem localização"},
    "Equipos sueltos":      {"en": "Loose equipment",   "pt": "Equipamentos soltos"},
    "equipo":               {"en": "equipment",         "pt": "equipamento"},
    # Fichas e imágenes (A.4)
    "Volver a Equipos": {"en": "Back to Equipment", "pt": "Voltar a Equipamentos"},
    "Volver a Cables": {"en": "Back to Cables", "pt": "Voltar a Cabos"},
    "Ubicación": {"en": "Location", "pt": "Localização"},
    "Posición": {"en": "Position", "pt": "Posição"},
    "Rol de señal": {"en": "Signal role", "pt": "Papel do sinal"},
    "Fabricación": {"en": "Manufactured", "pt": "Fabricação"},
    "Equipo usado": {"en": "Used equipment", "pt": "Equipamento usado"},
    "Dimensiones": {"en": "Dimensions", "pt": "Dimensões"},
    "Señal requerida (MHz)": {"en": "Required signal (MHz)", "pt": "Sinal necessário (MHz)"},
    "Manual": {"en": "Manual", "pt": "Manual"},
    "Última edición": {"en": "Last edited", "pt": "Última edição"},
    "Última auditoría": {"en": "Last audit", "pt": "Última auditoria"},
    "Nivel": {"en": "Level", "pt": "Nível"},
    "Probabilidad": {"en": "Probability", "pt": "Probabilidade"},
    "Calculado": {"en": "Calculated", "pt": "Calculado"},
    "Problemas": {"en": "Problems", "pt": "Problemas"},
    "Gravedad": {"en": "Severity", "pt": "Gravidade"},
    "Resuelto": {"en": "Resolved", "pt": "Resolvido"},
    "Abierto": {"en": "Open", "pt": "Aberto"},
    "Sin conectores": {"en": "No connectors", "pt": "Sem conectores"},
    "Ficha": {"en": "Plug", "pt": "Ficha"},
    "Balance": {"en": "Balance", "pt": "Balanceamento"},
    "Canal": {"en": "Channel", "pt": "Canal"},
    "Ruteo de entrada (matriz)": {"en": "Input routing (matrix)", "pt": "Roteamento de entrada (matriz)"},
    "interna": {"en": "internal", "pt": "interna"},
    "Armado": {"en": "Assembly", "pt": "Montagem"},
    "Armado correcto": {"en": "Assembly OK", "pt": "Montagem correta"},
    "Armado incorrecto": {"en": "Incorrect assembly", "pt": "Montagem incorreta"},
    "Extremo suelto": {"en": "Loose end", "pt": "Extremidade solta"},
    "Tipo de cable": {"en": "Cable type", "pt": "Tipo de cabo"},
    "Longitud": {"en": "Length", "pt": "Comprimento"},
    "Metraje impreso": {"en": "Printed length marks", "pt": "Metragem impressa"},
    "Cable interno": {"en": "Internal cable", "pt": "Cabo interno"},
    "Ancho de banda (MHz)": {"en": "Bandwidth (MHz)", "pt": "Largura de banda (MHz)"},
    "Cable fusionado": {"en": "Merged cable", "pt": "Cabo mesclado"},
    "Notas de relevamiento": {"en": "Survey notes", "pt": "Notas de levantamento"},
    "Buscar cable…": {"en": "Search cable…", "pt": "Buscar cabo…"},
    "No hay cables cargados": {"en": "No cables loaded", "pt": "Nenhum cabo carregado"},
    "{n} cables": {"en": "{n} cables", "pt": "{n} cabos"},
    "Mostrando {a} de {b}": {"en": "Showing {a} of {b}", "pt": "Mostrando {a} de {b}"},
    "Sí": {"en": "Yes", "pt": "Sim"},
    "No": {"en": "No", "pt": "Não"},
    "Cargando imagen…": {"en": "Loading image…", "pt": "Carregando imagem…"},
    "Imagen no cargada en este navegador": {"en": "Image not loaded in this browser", "pt": "Imagem não carregada neste navegador"},
    "Conectores fuera de la imagen": {"en": "Connectors outside the image", "pt": "Conectores fora da imagem"},
    "Elegir carpeta": {"en": "Choose folder", "pt": "Escolher pasta"},
    "Elegir archivos": {"en": "Choose files", "pt": "Escolher arquivos"},
    "Subiendo {a} de {b}…": {"en": "Uploading {a} of {b}…", "pt": "Enviando {a} de {b}…"},
    "{n} imágenes guardadas": {"en": "{n} images saved", "pt": "{n} imagens salvas"},
    "{n} ignoradas (no son imágenes)": {"en": "{n} ignored (not images)", "pt": "{n} ignoradas (não são imagens)"},
    "con error": {"en": "failed", "pt": "com erro"},
    "Se guardan en este navegador; no se envían a ningún servidor.": {"en": "They are kept in this browser; nothing is sent to any server.", "pt": "Ficam salvas neste navegador; nada é enviado a nenhum servidor."},
    "(Este navegador no permite guardarlas de forma permanente: se pierden al recargar.)": {"en": "(This browser cannot store them permanently: they are lost on reload.)", "pt": "(Este navegador não permite salvá-las de forma permanente: são perdidas ao recarregar.)"},
    # Conexiones (A.5)
    "Árbol de conexiones": {"en": "Connection tree", "pt": "Árvore de conexões"},
    "Buscar equipo…": {"en": "Search equipment…", "pt": "Buscar equipamento…"},
    "Elegí un equipo para ver a qué otros equipos está conectado.": {"en": "Pick a piece of equipment to see what it is connected to.", "pt": "Escolha um equipamento para ver a quais outros ele está conectado."},
    "Cambiar equipo": {"en": "Change equipment", "pt": "Trocar equipamento"},
    "Expandí un equipo para cargar sus conexiones.": {"en": "Expand a piece of equipment to load its connections.", "pt": "Expanda um equipamento para carregar suas conexões."},
    "Abre los nodos ya cargados": {"en": "Opens the nodes already loaded", "pt": "Abre os nós já carregados"},
    "Cargando conexiones…": {"en": "Loading connections…", "pt": "Carregando conexões…"},
    "«{e}» — {n} conexiones": {"en": "«{e}» — {n} connections", "pt": "«{e}» — {n} conexões"},
    "«{e}» no tiene más conexiones": {"en": "«{e}» has no more connections", "pt": "«{e}» não tem mais conexões"},
    "El equipo no tiene conexiones registradas.": {"en": "This equipment has no connections recorded.", "pt": "O equipamento não tem conexões registradas."},
    "ya desarrollado": {"en": "already expanded", "pt": "já expandido"},
    "Sin equipo": {"en": "No equipment", "pt": "Sem equipamento"},
    "Ver cadena completa": {"en": "View full chain", "pt": "Ver cadeia completa"},
    "Cadena completa": {"en": "Full chain", "pt": "Cadeia completa"},
    "Volver al cable": {"en": "Back to the cable", "pt": "Voltar ao cabo"},
    "Recorrido real de extremo a extremo, siguiendo cada extensión. El cable marcado con 👈 es desde donde abriste esta vista.":
        {"en": "Actual end-to-end path, following each extension. The cable marked with 👈 is the one you opened this view from.",
         "pt": "Percurso real de ponta a ponta, seguindo cada extensão. O cabo marcado com 👈 é o de onde você abriu esta tela."},
    "Cable desde el que abriste esta vista": {"en": "Cable you opened this view from", "pt": "Cabo de onde você abriu esta tela"},
    "Este cable no tiene conexiones cargadas todavía.": {"en": "This cable has no connections loaded yet.", "pt": "Este cabo ainda não tem conexões carregadas."},
    "Extensión": {"en": "Extension", "pt": "Extensão"},
    "correcto": {"en": "correct", "pt": "correto"},
    "MAL ARMADO": {"en": "INCORRECTLY ASSEMBLED", "pt": "MONTAGEM INCORRETA"},
    "no verificado": {"en": "not verified", "pt": "não verificado"},
    "sin posición registrada": {"en": "no position recorded", "pt": "sem posição registrada"},
    "extremo suelto — la cadena termina acá, sin llegar a un equipo": {"en": "loose end — the chain stops here without reaching equipment", "pt": "extremidade solta — a cadeia termina aqui, sem chegar a um equipamento"},
    "referencia circular detectada — revisar extensiones": {"en": "circular reference detected — review the extensions", "pt": "referência circular detectada — revisar as extensões"},
    # Ubicaciones: rack, frame/slots y patcheras (A.6)
    "Volver a Ubicaciones": {"en": "Back to Locations", "pt": "Voltar a Localizações"},
    "Patcheras (vista global)": {"en": "Patch panels (global view)", "pt": "Patch panels (visão global)"},
    "Racks sin sala": {"en": "Racks without a room", "pt": "Racks sem sala"},
    "Sin salas": {"en": "No rooms", "pt": "Sem salas"},
    "Sin racks": {"en": "No racks", "pt": "Sem racks"},
    "Sin frames": {"en": "No frames", "pt": "Sem frames"},
    "{n} posiciones": {"en": "{n} positions", "pt": "{n} posições"},
    "{n} slots": {"en": "{n} slots", "pt": "{n} slots"},
    "{n} frames": {"en": "{n} frames", "pt": "{n} frames"},
    "{n} bandejas": {"en": "{n} shared trays", "pt": "{n} bandejas"},
    "{n} orificios": {"en": "{n} holes", "pt": "{n} furos"},
    "{n} orificios libres": {"en": "{n} free holes", "pt": "{n} furos livres"},
    "1 U = 3 orificios. Hacé clic en un equipo o frame para abrirlo.": {"en": "1 U = 3 holes. Click a piece of equipment or a frame to open it.", "pt": "1 U = 3 furos. Clique num equipamento ou frame para abri-lo."},
    "Fuera del rango del rack (no se dibujan)": {"en": "Beyond the rack's last hole (not drawn)", "pt": "Além do último furo do rack (não desenhados)"},
    "Dispositivos": {"en": "Devices", "pt": "Dispositivos"},
    "Orificios": {"en": "Holes", "pt": "Furos"},
    "Rack vacío": {"en": "Empty rack", "pt": "Rack vazio"},
    "Libre": {"en": "Free", "pt": "Livre"},
    "LIBRE": {"en": "FREE", "pt": "LIVRE"},
    "libre": {"en": "free", "pt": "livre"},
    "Bandeja compartida": {"en": "Shared tray", "pt": "Bandeja compartilhada"},
    "FRENTE": {"en": "FRONT", "pt": "FRENTE"},
    "(vacío)": {"en": "(empty)", "pt": "(vazio)"},
    "Zoom": {"en": "Zoom", "pt": "Zoom"},
    "Acercar": {"en": "Zoom in", "pt": "Aproximar"},
    "Alejar": {"en": "Zoom out", "pt": "Afastar"},
    "Frame sin slots registrados": {"en": "Frame with no slots recorded", "pt": "Frame sem slots registrados"},
    "Este frame no tiene imagen: se dibujan solo los rectángulos de los slots.": {"en": "This frame has no image: only the slot rectangles are drawn.", "pt": "Este frame não tem imagem: só os retângulos dos slots são desenhados."},
    "No se pudo medir la imagen; se dibujan solo los rectángulos de los slots.": {"en": "The image could not be measured; only the slot rectangles are drawn.", "pt": "Não foi possível medir a imagem; só os retângulos dos slots são desenhados."},
    "{racks} racks · {patcheras} patcheras": {"en": "{racks} racks · {patcheras} patch panels", "pt": "{racks} racks · {patcheras} patch panels"},
    "{n} equipos conectados": {"en": "{n} connected devices", "pt": "{n} equipamentos conectados"},
    "{n} fantasma": {"en": "{n} ghost", "pt": "{n} fantasma"},
    "FANTASMA": {"en": "GHOST", "pt": "FANTASMA"},
    "Patchcord frente": {"en": "Front patch cord", "pt": "Patch cord frontal"},
    "Cables entre racks": {"en": "Cables between racks", "pt": "Cabos entre racks"},
    "Fila A: entrada trasera y derivación frontal. Fila B: salida trasera e inserción frontal. Cada color es un equipo; hacé clic en un orificio para abrir el equipo.":
        {"en": "Row A: rear input and front tap. Row B: rear output and front insert. Each colour is a device; click a hole to open it.",
         "pt": "Linha A: entrada traseira e derivação frontal. Linha B: saída traseira e inserção frontal. Cada cor é um equipamento; clique num furo para abri-lo."},
    "No se encontraron patcheras (módulos con rol PATCHERA en un slot de un frame de rack) en el sistema.":
        {"en": "No patch panels found (modules with the PATCHERA role in a slot of a rack frame).", "pt": "Nenhum patch panel encontrado (módulos com a função PATCHERA num slot de um frame de rack)."},
    # Errores
    "Algo salió mal":       {"en": "Something went wrong", "pt": "Algo deu errado"},
    "Detalle técnico":      {"en": "Technical details", "pt": "Detalhes técnicos"},
    "Reintentar":           {"en": "Retry",             "pt": "Tentar novamente"},
    "Error al mostrar la pantalla": {"en": "Could not display the screen", "pt": "Erro ao exibir a tela"},
    "Error del motor Python": {"en": "Python engine error", "pt": "Erro do motor Python"},
    "No se pudo cargar el motor. Revisá la red o corré ui_web/fetch_pyodide.py.":
        {"en": "The engine could not be loaded. Check the network or run ui_web/fetch_pyodide.py.",
         "pt": "Não foi possível carregar o motor. Verifique a rede ou execute ui_web/fetch_pyodide.py."},
    "Pantalla desconocida": {"en": "Unknown screen",    "pt": "Tela desconhecida"},
}


def diccionario(lang):
    """Traducciones `{clave_es: texto}` de `lang` (core + web). Vacío para 'es'."""
    if lang not in IDIOMAS:
        raise ValueError(f"Idioma no soportado: {lang}")
    if lang == "es":
        return {}
    from core import i18n as base
    out = {k: v[lang] for k, v in base._TRADUCCIONES.items() if lang in v}
    out.update({k: v[lang] for k, v in _WEB.items() if lang in v})
    return out


def diccionario_json(lang):
    """Igual que `diccionario` pero como string JSON (lo que cruza al worker)."""
    return json.dumps({"lang": lang, "idiomas": IDIOMAS, "textos": diccionario(lang)},
                      ensure_ascii=False)


# ── Análisis (A.7): se agrega acá, al final, para no pisar el bloque de otras etapas ──────────────────
_WEB_A7 = {
    "Riesgo (IRF)":         {"en": "Risk (IRF)",          "pt": "Risco (IRF)"},
    "Diagnóstico":          {"en": "Diagnosis",           "pt": "Diagnóstico"},
    "Impacto si falla":     {"en": "Impact if it fails",  "pt": "Impacto se falhar"},
    "Impacto si se corta":  {"en": "Impact if cut",       "pt": "Impacto se cortado"},
    "Diagnosticar falla desde este conector": {"en": "Diagnose a fault from this connector", "pt": "Diagnosticar falha a partir deste conector"},
    "Ver ficha":            {"en": "View record",         "pt": "Ver ficha"},
    "Elegir otro":          {"en": "Choose another",      "pt": "Escolher outro"},
    "Buscar rack…":         {"en": "Search rack…",        "pt": "Buscar rack…"},
    "Rack":                 {"en": "Rack",                "pt": "Rack"},
    "Crítico":              {"en": "Critical",            "pt": "Crítico"},
    "Alto":                 {"en": "High",                "pt": "Alto"},
    "Medio":                {"en": "Medium",              "pt": "Médio"},
    "Bajo":                 {"en": "Low",                 "pt": "Baixo"},
    "alto":                 {"en": "high",                "pt": "alto"},
    "bajo":                 {"en": "low",                 "pt": "baixo"},
    "Todos los niveles":    {"en": "All levels",          "pt": "Todos os níveis"},
    "Prob. / Impacto":      {"en": "Prob. / Impact",      "pt": "Prob. / Impacto"},
    "Edad":                 {"en": "Age",                 "pt": "Idade"},
    "Uso":                  {"en": "Usage",               "pt": "Uso"},
    "Historial":            {"en": "History",             "pt": "Histórico"},
    "No hay elementos cargados": {"en": "No items loaded", "pt": "Nenhum item carregado"},
    "{n} elementos":        {"en": "{n} items",           "pt": "{n} itens"},
    "{n} conexiones":       {"en": "{n} connections",     "pt": "{n} conexões"},
    "{p}% de {n}":          {"en": "{p}% of {n}",         "pt": "{p}% de {n}"},
    "de {n}":               {"en": "of {n}",              "pt": "de {n}"},
    "Equipos sin señal":    {"en": "Equipment without signal", "pt": "Equipamentos sem sinal"},
    "Puntos finales afectados": {"en": "End points affected", "pt": "Pontos finais afetados"},
    "Cables afectados":     {"en": "Cables affected",     "pt": "Cabos afetados"},
    "Punto final":          {"en": "End point",           "pt": "Ponto final"},
    "Causa":                {"en": "Cause",               "pt": "Causa"},
    "Reglas lógicas que dejan de cumplirse": {"en": "Logic rules no longer met", "pt": "Regras lógicas que deixam de ser cumpridas"},
    "Sin impacto: ningún equipo queda sin señal.": {"en": "No impact: no equipment loses signal.", "pt": "Sem impacto: nenhum equipamento perde sinal."},
    "Si falla «{n}» por completo":   {"en": "If “{n}” fails completely", "pt": "Se “{n}” falhar por completo"},
    "Si se corta el cable «{n}»":    {"en": "If cable “{n}” is cut",     "pt": "Se o cabo “{n}” for cortado"},
    "Si se pierde el rack «{n}»":    {"en": "If rack “{n}” is lost",     "pt": "Se o rack “{n}” for perdido"},
    "Elegí un equipo para ver qué otros equipos quedan sin señal si deja de funcionar.":
        {"en": "Pick a piece of equipment to see which others lose signal if it stops working.", "pt": "Escolha um equipamento para ver quais outros ficam sem sinal se ele parar."},
    "Elegí un cable para ver qué equipos quedan sin señal si se corta.":
        {"en": "Pick a cable to see which equipment loses signal if it is cut.", "pt": "Escolha um cabo para ver quais equipamentos ficam sem sinal se ele for cortado."},
    "Elegí un rack para ver qué equipos quedan sin señal si se pierde completo.":
        {"en": "Pick a rack to see which equipment loses signal if it is lost entirely.", "pt": "Escolha um rack para ver quais equipamentos ficam sem sinal se ele for perdido por completo."},
    "Índice de Riesgo de Falla: probabilidad (edad, uso, historial) × impacto (fracción del parque que queda sin señal). Se calcula acá, sin guardar nada en la base.":
        {"en": "Failure Risk Index: probability (age, usage, history) × impact (share of the plant left without signal). Calculated here; nothing is saved to the database.",
         "pt": "Índice de Risco de Falha: probabilidade (idade, uso, histórico) × impacto (fração do parque que fica sem sinal). Calculado aqui, sem gravar nada na base."},
    "Calcular IRF":         {"en": "Calculate IRF",       "pt": "Calcular IRF"},
    "Recalcular":           {"en": "Recalculate",         "pt": "Recalcular"},
    "Calculando… puede tardar unos segundos.": {"en": "Calculating… this may take a few seconds.", "pt": "Calculando… pode levar alguns segundos."},
    "Calculado en {s} s":   {"en": "Calculated in {s} s", "pt": "Calculado em {s} s"},
    "resultado guardado en memoria": {"en": "result kept in memory", "pt": "resultado mantido em memória"},
    "El impacto se mide contra los equipos críticos marcados en el escritorio.":
        {"en": "Impact is measured against the critical equipment marked on the desktop.", "pt": "O impacto é medido contra os equipamentos críticos marcados no desktop."},
    "No se pudo construir el grafo: el impacto usa un valor neutro (50).":
        {"en": "The graph could not be built: impact uses a neutral value (50).", "pt": "Não foi possível construir o grafo: o impacto usa um valor neutro (50)."},
    "Elegí el equipo donde falta la señal y después el conector donde lo notás (el síntoma).":
        {"en": "Pick the equipment missing the signal, then the connector where you notice it (the symptom).", "pt": "Escolha o equipamento sem sinal e depois o conector onde você nota o problema (o sintoma)."},
    "Elegir otro equipo":   {"en": "Choose another equipment", "pt": "Escolher outro equipamento"},
    "Elegir otro conector": {"en": "Choose another connector", "pt": "Escolher outro conector"},
    "¿En qué conector de «{n}» falta la señal?": {"en": "On which connector of “{n}” is the signal missing?", "pt": "Em qual conector de “{n}” falta o sinal?"},
    "Este equipo no tiene conectores.": {"en": "This equipment has no connectors.", "pt": "Este equipamento não tem conectores."},
    "Diagnóstico desde «{n}»": {"en": "Diagnosis from “{n}”", "pt": "Diagnóstico a partir de “{n}”"},
    "Cadena hacia el origen": {"en": "Chain toward the source", "pt": "Cadeia até a origem"},
    "síntoma: sin señal":   {"en": "symptom: no signal",  "pt": "sintoma: sem sinal"},
    "extremo alcanzado: se asume con señal": {"en": "far end reached: assumed to have signal", "pt": "extremo alcançado: assume-se com sinal"},
    "punto de test":        {"en": "test point",          "pt": "ponto de teste"},
    "Hay señal":            {"en": "Has signal",          "pt": "Tem sinal"},
    "No hay señal":         {"en": "No signal",           "pt": "Sem sinal"},
    "No sé":                {"en": "Don't know",          "pt": "Não sei"},
    "Sí, hay señal":        {"en": "Yes, there is signal", "pt": "Sim, há sinal"},
    "¿Hay señal en «{n}»?": {"en": "Is there signal at “{n}”?", "pt": "Há sinal em “{n}”?"},
    "Medilo con un monitor o analizador en ese punto.": {"en": "Check it with a monitor or analyzer at that point.", "pt": "Meça com um monitor ou analisador nesse ponto."},
    "Hay que elegir una entrada": {"en": "An input must be chosen", "pt": "É preciso escolher uma entrada"},
    "El equipo «{n}» tiene {c} entradas. ¿Cuál corresponde a lo que falta?":
        {"en": "“{n}” has {c} inputs. Which one carries what is missing?", "pt": "“{n}” tem {c} entradas. Qual corresponde ao que falta?"},
    "Elegí dónde medir":    {"en": "Choose where to measure", "pt": "Escolha onde medir"},
    "No hay puntos de test marcados en este tramo. Elegí a mano uno de los puntos intermedios:":
        {"en": "There are no test points marked in this stretch. Pick one of the intermediate points by hand:", "pt": "Não há pontos de teste marcados neste trecho. Escolha manualmente um dos pontos intermediários:"},
    "Sospechoso":           {"en": "Suspect",             "pt": "Suspeito"},
    "El problema está dentro del equipo «{n}»: hay señal en «{b}» pero no en «{a}». Revisá su conexión interna o su alimentación.":
        {"en": "The problem is inside “{n}”: there is signal at “{b}” but not at “{a}”. Check its internal connection or power.",
         "pt": "O problema está dentro de “{n}”: há sinal em “{b}”, mas não em “{a}”. Verifique a conexão interna ou a alimentação."},
    "El problema está en el cable (o su conexión) entre «{a}» y «{b}».":
        {"en": "The problem is in the cable (or its connection) between “{a}” and “{b}”.", "pt": "O problema está no cabo (ou na conexão) entre “{a}” e “{b}”."},
    "La cadena tiene un solo punto: no hay nada para acotar.": {"en": "The chain has a single point: nothing to narrow down.", "pt": "A cadeia tem um único ponto: não há nada a delimitar."},
    "Deshacer":             {"en": "Undo",                "pt": "Desfazer"},
    "Reiniciar":            {"en": "Restart",             "pt": "Reiniciar"},
    "Fuera de patchera":    {"en": "Outside patch panel", "pt": "Fora de patch panel"},
    "Fuera de distribuidor": {"en": "Outside distributor", "pt": "Fora de distribuidor"},
    "Loop en uso":          {"en": "Loop in use",         "pt": "Loop em uso"},
    "Referencia en cascada": {"en": "Cascaded reference", "pt": "Referência em cascata"},
    "Equipos con cables documentados, pero ninguno llega a una patchera: cableado directo.":
        {"en": "Equipment with documented cables, none of which reaches a patch panel: direct wiring.", "pt": "Equipamentos com cabos documentados, nenhum chega a um patch panel: cabeamento direto."},
    "Equipos cuyas salidas no entran directo a un distribuidor (ni pasando solo por patcheras).":
        {"en": "Equipment whose outputs do not go straight into a distributor (nor only through patch panels).", "pt": "Equipamentos cujas saídas não entram direto em um distribuidor (nem passando só por patch panels)."},
    "Salidas loop-through con un cable real conectado.": {"en": "Loop-through outputs with a real cable connected.", "pt": "Saídas loop-through com um cabo real conectado."},
    "Equipos que re-emiten la referencia sin ser distribuidores de sincronismo: si caen, arrastran lo que cuelga de ellos.":
        {"en": "Equipment that re-emits the reference without being a sync distributor: if it falls, everything hanging from it falls too.",
         "pt": "Equipamentos que reemitem a referência sem serem distribuidores de sincronismo: se caírem, arrastam o que depende deles."},
    "Salida loop":          {"en": "Loop output",         "pt": "Saída loop"},
    "Salida de referencia": {"en": "Reference output",    "pt": "Saída de referência"},
    "Origen":               {"en": "Source",              "pt": "Origem"},
    "Destinos":             {"en": "Destinations",        "pt": "Destinos"},
    "Tipo de equipo":       {"en": "Equipment type",      "pt": "Tipo de equipamento"},
    "Sin hallazgos.":       {"en": "No findings.",        "pt": "Sem achados."},
    "Reglas de diseño que se revisan solas sobre los datos cargados. Cada lista va ordenada por riesgo.":
        {"en": "Design rules checked automatically against the loaded data. Each list is sorted by risk.", "pt": "Regras de projeto verificadas automaticamente sobre os dados carregados. Cada lista é ordenada por risco."},
    "La base no tiene riesgo calculado: los hallazgos no están priorizados. Calculalo en el escritorio con «Recalcular riesgo».":
        {"en": "The database has no calculated risk: findings are not prioritised. Calculate it on the desktop with “Recalculate risk”.",
         "pt": "A base não tem risco calculado: os achados não estão priorizados. Calcule no desktop com “Recalcular risco”."},
}
_WEB.update(_WEB_A7)


# ── Escenarios (A.8): se agrega acá, al final, para no pisar el bloque de otras etapas ────────────────
_WEB_A8 = {
    "Volver a Escenarios":  {"en": "Back to Scenarios",   "pt": "Voltar a Cenários"},
    "Simulaciones de falla guardadas en la base: fallas de equipo, cables cortados y reconexiones de emergencia. Acá se abren y se evalúan; crearlas y editarlas llega con la Fase B.":
        {"en": "Failure simulations saved in the database: equipment failures, cut cables and emergency reconnections. Here they can be opened and evaluated; creating and editing them comes with Phase B.",
         "pt": "Simulações de falha salvas no banco: falhas de equipamento, cabos cortados e reconexões de emergência. Aqui podem ser abertas e avaliadas; criá-las e editá-las chega com a Fase B."},
    "No hay escenarios guardados en esta base. Se crean en el escritorio (Modo Escenario).":
        {"en": "There are no scenarios saved in this database. They are created on the desktop (Scenario Mode).",
         "pt": "Não há cenários salvos neste banco. Eles são criados no desktop (Modo Cenário)."},
    "Cambios":              {"en": "Changes",             "pt": "Alterações"},
    "Sin cambios":          {"en": "No changes",          "pt": "Sem alterações"},
    "Creado":               {"en": "Created",             "pt": "Criado"},
    "Detalle":              {"en": "Detail",              "pt": "Detalhe"},
    "Fallas":               {"en": "Failures",            "pt": "Falhas"},
    "Cortes":               {"en": "Cuts",                "pt": "Cortes"},
    "Reconexiones":         {"en": "Reconnections",       "pt": "Reconexões"},
    "Borrador":             {"en": "Draft",               "pt": "Rascunho"},
    "Simulado":             {"en": "Simulated",           "pt": "Simulado"},
    "Aprobado":             {"en": "Approved",            "pt": "Aprovado"},
    "Aplicado":             {"en": "Applied",             "pt": "Aplicado"},
    "Descartado":           {"en": "Discarded",           "pt": "Descartado"},
    "Falla de equipo":      {"en": "Equipment failure",   "pt": "Falha de equipamento"},
    "Cable cortado":        {"en": "Cut cable",           "pt": "Cabo cortado"},
    "Reconexión virtual":   {"en": "Virtual reconnection", "pt": "Reconexão virtual"},
    "Equipo {id} (ya no existe)":   {"en": "Equipment {id} (no longer exists)", "pt": "Equipamento {id} (não existe mais)"},
    "Cable {id} (ya no existe)":    {"en": "Cable {id} (no longer exists)",     "pt": "Cabo {id} (não existe mais)"},
    "Conector {id} (ya no existe)": {"en": "Connector {id} (no longer exists)", "pt": "Conector {id} (não existe mais)"},
    "Este escenario no tiene cambios.": {"en": "This scenario has no changes.", "pt": "Este cenário não tem alterações."},
    "Este escenario ya se aplicó a la infraestructura: la evaluación se calcula sobre el estado actual de la base, que ya incluye esos cambios.":
        {"en": "This scenario was already applied to the infrastructure: the evaluation is calculated on the current state of the database, which already includes those changes.",
         "pt": "Este cenário já foi aplicado à infraestrutura: a avaliação é calculada sobre o estado atual do banco, que já inclui essas alterações."},
    "Este escenario está descartado.": {"en": "This scenario is discarded.", "pt": "Este cenário está descartado."},
    "Resultado de la evaluación": {"en": "Evaluation result", "pt": "Resultado da avaliação"},
    "Sin cambios no hay nada que evaluar.": {"en": "With no changes there is nothing to evaluate.", "pt": "Sem alterações não há nada a avaliar."},
    "No se pudo construir el grafo de conexiones, así que no hay evaluación. Revisá que la base tenga cables y conexiones cargados.":
        {"en": "The connection graph could not be built, so there is no evaluation. Check that the database has cables and connections loaded.",
         "pt": "Não foi possível construir o grafo de conexões, portanto não há avaliação. Verifique se o banco tem cabos e conexões carregados."},
    "Recuperados":          {"en": "Recovered",           "pt": "Recuperados"},
    "Recuperado":           {"en": "Recovered",           "pt": "Recuperado"},
    "Sin señal":            {"en": "No signal",           "pt": "Sem sinal"},
    "Con la reconexión":    {"en": "With the reconnection", "pt": "Com a reconexão"},
    "por la reconexión virtual": {"en": "by the virtual reconnection", "pt": "pela reconexão virtual"},
    "Los equipos que fallan en el escenario no se cuentan como equipos sin señal.":
        {"en": "Equipment that fails in the scenario is not counted as equipment without signal.",
         "pt": "Os equipamentos que falham no cenário não são contados como equipamentos sem sinal."},
    "Con las reconexiones virtuales los equipos sin señal pasan de {a} a {b} ({r} recuperados).":
        {"en": "With the virtual reconnections, equipment without signal goes from {a} to {b} ({r} recovered).",
         "pt": "Com as reconexões virtuais, os equipamentos sem sinal passam de {a} para {b} ({r} recuperados)."},
    "Hay reconexiones con un conector que ya no existe; se ignoraron en el cálculo:":
        {"en": "Some reconnections use a connector that no longer exists; they were ignored in the calculation:",
         "pt": "Há reconexões com um conector que não existe mais; foram ignoradas no cálculo:"},
    "Calculado en {ms} ms. El resultado no se guarda ni cambia el estado del escenario.":
        {"en": "Calculated in {ms} ms. The result is not saved and does not change the scenario status.",
         "pt": "Calculado em {ms} ms. O resultado não é salvo nem altera o estado do cenário."},
}
_WEB.update(_WEB_A8)
