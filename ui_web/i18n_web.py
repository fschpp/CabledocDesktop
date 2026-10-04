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

# Fase A.9 — búsqueda global (equipos, conectores, cables, salas, racks y frames)
_WEB_A9 = {
    "Buscar equipos, conectores, cables, racks…":
        {"en": "Search equipment, connectors, cables, racks…", "pt": "Buscar equipamentos, conectores, cabos, racks…"},
    "Busca en equipos, conectores, cables, salas, racks y frames. Todas las palabras deben aparecer, en cualquier orden y sin distinguir mayúsculas ni acentos (por ejemplo «sony 3500» o «cam 1 out»).":
        {"en": "Searches equipment, connectors, cables, rooms, racks and frames. Every word must appear, in any order, ignoring case and accents (for example “sony 3500” or “cam 1 out”).",
         "pt": "Busca em equipamentos, conectores, cabos, salas, racks e frames. Todas as palavras devem aparecer, em qualquer ordem, sem distinguir maiúsculas nem acentos (por exemplo «sony 3500» ou «cam 1 out»)."},
    "Escribí al menos 2 caracteres para buscar.":
        {"en": "Type at least 2 characters to search.", "pt": "Digite pelo menos 2 caracteres para buscar."},
    "Tipo de resultado":    {"en": "Result type",         "pt": "Tipo de resultado"},
    "Ver todos ({n})":      {"en": "Show all ({n})",      "pt": "Ver todos ({n})"},
    "Se muestran las primeras {n} coincidencias; afiná la búsqueda para ver el resto.":
        {"en": "Showing the first {n} matches; refine the search to see the rest.",
         "pt": "Mostrando as primeiras {n} correspondências; refine a busca para ver o resto."},
}
_WEB.update(_WEB_A9)

# Fase A.10 — Datos: respaldo del .db y catálogos de equipos/frames
_WEB_A10 = {
    "Trabajando…": {"en": "Working…", "pt": "Trabalhando…"},
    "Primero cargá un db.db": {"en": "Load a db.db first", "pt": "Carregue primeiro um db.db"},
    "Base completa": {"en": "Full database", "pt": "Base completa"},
    "El respaldo es el archivo .db: sirve para llevar la instalación a otra computadora o volver a cargarla acá. Las imágenes no viajan con él.":
        {"en": "The backup is the .db file: use it to move the installation to another computer or to load it back here. Images do not travel with it.",
         "pt": "O backup é o arquivo .db: serve para levar a instalação a outro computador ou carregá-la de novo aqui. As imagens não viajam com ele."},
    "Exportar la base (.db)": {"en": "Export the database (.db)", "pt": "Exportar a base (.db)"},
    "Importar una base (.db)": {"en": "Import a database (.db)", "pt": "Importar uma base (.db)"},
    "Base exportada ({kb} KB).": {"en": "Database exported ({kb} KB).", "pt": "Base exportada ({kb} KB)."},
    "Esto reemplaza la base actual de este navegador por «{nombre}». Exportá la actual antes si la necesitás. ¿Seguir?":
        {"en": "This replaces the current database in this browser with “{nombre}”. Export the current one first if you need it. Continue?",
         "pt": "Isto substitui a base atual deste navegador por «{nombre}». Exporte a atual antes se precisar dela. Continuar?"},
    "Base importada: {equipos} equipos, {conectores} conectores, {cables} cables.":
        {"en": "Database imported: {equipos} equipment, {conectores} connectors, {cables} cables.",
         "pt": "Base importada: {equipos} equipamentos, {conectores} conectores, {cables} cabos."},
    "El archivo no es una base SQLite.": {"en": "The file is not a SQLite database.", "pt": "O arquivo não é uma base SQLite."},
    "La base está dañada (quick_check falló).": {"en": "The database is damaged (quick_check failed).", "pt": "A base está danificada (quick_check falhou)."},
    "No parece una base de CableDoc: falta la tabla «{tabla}».":
        {"en": "This does not look like a CableDoc database: table “{tabla}” is missing.",
         "pt": "Não parece uma base do CableDoc: falta a tabela «{tabla}»."},
    "Formato del escritorio: un .zip con un .json. Las imágenes del catálogo no viajan: se guardan aparte en este navegador.":
        {"en": "Desktop format: a .zip with a .json inside. Catalog images do not travel: they are stored separately in this browser.",
         "pt": "Formato do desktop: um .zip com um .json. As imagens do catálogo não viajam: ficam guardadas à parte neste navegador."},
    "Exportar catálogo de equipos": {"en": "Export equipment catalog", "pt": "Exportar catálogo de equipamentos"},
    "Exportar catálogo de frames": {"en": "Export frame catalog", "pt": "Exportar catálogo de frames"},
    "Importar un catálogo (.zip o .json)": {"en": "Import a catalog (.zip or .json)", "pt": "Importar um catálogo (.zip ou .json)"},
    "Catálogo exportado: {moldes} molde(s).": {"en": "Catalog exported: {moldes} template(s).", "pt": "Catálogo exportado: {moldes} molde(s)."},
    "Importar «{nombre}» agrega moldes a la base de este navegador. ¿Seguir?":
        {"en": "Importing “{nombre}” adds templates to the database in this browser. Continue?",
         "pt": "Importar «{nombre}» adiciona moldes à base deste navegador. Continuar?"},
    "Importados {moldes} molde(s) con {hijos} conector(es) o slot(s).":
        {"en": "Imported {moldes} template(s) with {hijos} connector(s) or slot(s).", "pt": "Importados {moldes} molde(s) com {hijos} conector(es) ou slot(s)."},
    "{conflictos} conflicto(s) de rol o dirección: se conservó el valor local.":
        {"en": "{conflictos} role or direction conflict(s): the local value was kept.", "pt": "{conflictos} conflito(s) de papel ou direção: o valor local foi mantido."},
    "El archivo no es un catálogo de CableDoc válido.": {"en": "The file is not a valid CableDoc catalog.", "pt": "O arquivo não é um catálogo do CableDoc válido."},
}
_WEB.update(_WEB_A10)

# Fase A.11 — uso sin conexión (service worker)
_WEB_A11 = {
    "Preparando el uso sin conexión…": {"en": "Getting ready for offline use…", "pt": "Preparando o uso offline…"},
    "Sin conexión: falta guardar el motor (se completa en la próxima visita con conexión)":
        {"en": "Offline: the engine is not saved yet (it completes on the next online visit)",
         "pt": "Offline: falta guardar o motor (conclui na próxima visita com conexão)"},
    "Listo para usar sin conexión": {"en": "Ready to use offline", "pt": "Pronto para usar offline"},
}
_WEB.update(_WEB_A11)

# Fase B.1 — formularios y diálogos genéricos (app/formulario*.js)
_WEB_B1 = {
    "Obligatorio": {"en": "Required", "pt": "Obrigatório"},
    "Debe ser un número": {"en": "Must be a number", "pt": "Deve ser um número"},
    "Debe ser un número entero": {"en": "Must be a whole number", "pt": "Deve ser um número inteiro"},
    "Debe ser una fecha válida (AAAA-MM-DD)": {"en": "Must be a valid date (YYYY-MM-DD)", "pt": "Deve ser uma data válida (AAAA-MM-DD)"},
    "Mínimo {min}": {"en": "Minimum {min}", "pt": "Mínimo {min}"},
    "Máximo {max}": {"en": "Maximum {max}", "pt": "Máximo {max}"},
    "Máximo {n} caracteres": {"en": "Maximum {n} characters", "pt": "Máximo de {n} caracteres"},
    "Formato no válido": {"en": "Invalid format", "pt": "Formato inválido"},
    "Elegí una opción válida": {"en": "Choose a valid option", "pt": "Escolha uma opção válida"},
    "— Elegí —": {"en": "— Choose —", "pt": "— Escolha —"},
    "Los campos con * son obligatorios.": {"en": "Fields marked * are required.", "pt": "Os campos com * são obrigatórios."},
    "Hay {n} campo(s) con errores. Revisalos y volvé a intentar.":
        {"en": "{n} field(s) have errors. Review them and try again.", "pt": "{n} campo(s) com erros. Revise-os e tente de novo."},
    "No se pudo guardar: {error}": {"en": "Could not save: {error}", "pt": "Não foi possível salvar: {error}"},
    "No se pudo guardar": {"en": "Could not save", "pt": "Não foi possível salvar"},
    "Guardando…": {"en": "Saving…", "pt": "Salvando…"},
    "¿Descartar los cambios sin guardar?": {"en": "Discard the unsaved changes?", "pt": "Descartar as alterações não salvas?"},
    "Confirmar": {"en": "Confirm", "pt": "Confirmar"},
    "Deshecho: {texto}": {"en": "Undone: {texto}", "pt": "Desfeito: {texto}"},
    "No se pudo deshacer": {"en": "Could not undo", "pt": "Não foi possível desfazer"},
}
_WEB.update(_WEB_B1)

# Fase B.2 — catálogos básicos (app/catalogos*.js; las reglas de validación vienen de catalogos_web.py)
_WEB_B2 = {
    "Catálogos": {"en": "Catalogs", "pt": "Catálogos"},
    "Catálogo desconocido": {"en": "Unknown catalog", "pt": "Catálogo desconhecido"},
    # Catálogos (título de la pestaña y nombre en singular)
    "Marcas": {"en": "Brands", "pt": "Marcas"},
    "Tipos de equipo": {"en": "Equipment types", "pt": "Tipos de equipamento"},
    "Tipos de conector": {"en": "Connector types", "pt": "Tipos de conector"},
    "Tipos de cable": {"en": "Cable types", "pt": "Tipos de cabo"},
    "Tipos de ficha": {"en": "Plug types", "pt": "Tipos de ficha"},
    "Señales": {"en": "Signals", "pt": "Sinais"},
    "Formatos de señal": {"en": "Signal formats", "pt": "Formatos de sinal"},
    "Imágenes": {"en": "Images", "pt": "Imagens"},
    "marca": {"en": "brand", "pt": "marca"},
    "tipo de equipo": {"en": "equipment type", "pt": "tipo de equipamento"},
    "tipo de conector": {"en": "connector type", "pt": "tipo de conector"},
    "tipo de cable": {"en": "cable type", "pt": "tipo de cabo"},
    "tipo de ficha": {"en": "plug type", "pt": "tipo de ficha"},
    "señal": {"en": "signal", "pt": "sinal"},
    "formato de señal": {"en": "signal format", "pt": "formato de sinal"},
    "imagen": {"en": "image", "pt": "imagem"},
    # Lista, filtro y acciones
    "Alta de {x}": {"en": "Add {x}", "pt": "Cadastrar {x}"},
    "Editar {x}": {"en": "Edit {x}", "pt": "Editar {x}"},
    "Eliminar {x}": {"en": "Delete {x}", "pt": "Excluir {x}"},
    "Editar": {"en": "Edit", "pt": "Editar"},
    "Eliminar": {"en": "Delete", "pt": "Excluir"},
    "Filtrar": {"en": "Filter", "pt": "Filtrar"},
    "{n} de {total}": {"en": "{n} of {total}", "pt": "{n} de {total}"},
    "{total} registro(s)": {"en": "{total} record(s)", "pt": "{total} registro(s)"},
    "Ningún registro coincide con el filtro.": {"en": "No records match the filter.", "pt": "Nenhum registro corresponde ao filtro."},
    "Todavía no hay registros.": {"en": "There are no records yet.", "pt": "Ainda não há registros."},
    "ID": {"en": "ID", "pt": "ID"},
    "En uso": {"en": "In use", "pt": "Em uso"},
    "Se agregó «{nombre}»": {"en": "Added «{nombre}»", "pt": "«{nombre}» adicionado"},
    "Se modificó «{nombre}»": {"en": "Modified «{nombre}»", "pt": "«{nombre}» modificado"},
    "Se eliminó «{nombre}»": {"en": "Deleted «{nombre}»", "pt": "«{nombre}» excluído"},
    "No se pudo completar la acción": {"en": "The action could not be completed", "pt": "Não foi possível concluir a ação"},
    # Confirmación de baja
    "¿Eliminar «{nombre}»?": {"en": "Delete «{nombre}»?", "pt": "Excluir «{nombre}»?"},
    "Está en uso. Al eliminarlo:": {"en": "It is in use. If you delete it:", "pt": "Está em uso. Ao excluí-lo:"},
    "No está en uso.": {"en": "It is not in use.", "pt": "Não está em uso."},
    "también se eliminarán": {"en": "will also be deleted", "pt": "também serão excluídos"},
    "quedarán sin este valor": {"en": "will be left without this value", "pt": "ficarão sem este valor"},
    # Dónde se usa un valor
    "Moldes de equipo": {"en": "Equipment templates", "pt": "Modelos de equipamento"},
    "Moldes de frame": {"en": "Frame templates", "pt": "Modelos de frame"},
    "Moldes de conector": {"en": "Connector templates", "pt": "Modelos de conector"},
    "Slots": {"en": "Slots", "pt": "Slots"},
    "Plantillas de conectores": {"en": "Connector presets", "pt": "Predefinições de conectores"},
    "Reglas lógicas": {"en": "Logic rules", "pt": "Regras lógicas"},
    "Estrategias visuales": {"en": "Visual strategies", "pt": "Estratégias visuais"},
    "Símbolos de conector": {"en": "Connector symbols", "pt": "Símbolos de conector"},
    "Señales asignadas a conectores": {"en": "Signals assigned to connectors", "pt": "Sinais atribuídos a conectores"},
    "Relaciones de linaje de señal": {"en": "Signal lineage links", "pt": "Relações de linhagem de sinal"},
    "Imágenes de señal de conector": {"en": "Connector signal images", "pt": "Imagens de sinal de conector"},
    # Campos del formulario
    "Nombre": {"en": "Name", "pt": "Nome"},
    "Rol frente a la señal": {"en": "Role in the signal path", "pt": "Papel no caminho do sinal"},
    "Es referencia generada (fuente incondicional de sync, ej. SPG/wordclock)":
        {"en": "Is a generated reference (unconditional sync source, e.g. SPG/wordclock)", "pt": "É uma referência gerada (fonte incondicional de sync, ex.: SPG/wordclock)"},
    "Naturaleza de la señal": {"en": "Signal nature", "pt": "Natureza do sinal"},
    "Long. máx. recomendada — balanceado (m)": {"en": "Max. recommended length — balanced (m)", "pt": "Comp. máx. recomendado — balanceado (m)"},
    "Long. máx. recomendada — desbalanceado (m)": {"en": "Max. recommended length — unbalanced (m)", "pt": "Comp. máx. recomendado — desbalanceado (m)"},
    "Ancho de banda (MHz)": {"en": "Bandwidth (MHz)", "pt": "Largura de banda (MHz)"},
    "Cantidad de conductores": {"en": "Number of conductors", "pt": "Número de condutores"},
    "Balance por defecto": {"en": "Default balance", "pt": "Balanceamento padrão"},
    "Canal por defecto": {"en": "Default channel", "pt": "Canal padrão"},
    "Tipo de contenido": {"en": "Content type", "pt": "Tipo de conteúdo"},
    "Descripción": {"en": "Description", "pt": "Descrição"},
    "Archivo de imagen": {"en": "Image file", "pt": "Arquivo de imagem"},
    "El análisis de impacto trata cualquier conector de este tipo como fuente de señal, aunque no tenga entradas cableadas.":
        {"en": "Impact analysis treats any connector of this type as a signal source, even if it has no wired inputs.", "pt": "A análise de impacto trata qualquer conector deste tipo como fonte de sinal, mesmo sem entradas cabeadas."},
    "Nombre del archivo en la carpeta de imágenes (ej. camara.png). Desde acá solo se edita el registro: los archivos se cargan desde las fichas.":
        {"en": "File name in the images folder (e.g. camera.png). Only the record is edited here: files are loaded from the detail pages.", "pt": "Nome do arquivo na pasta de imagens (ex.: camera.png). Aqui só se edita o registro: os arquivos são carregados nas fichas."},
    "Para fichas ambiguas (ej. TRS) estos valores son solo el default: cada conector puede tener su propio ajuste.":
        {"en": "For ambiguous plugs (e.g. TRS) these values are only the default: each connector can have its own setting.", "pt": "Para fichas ambíguas (ex.: TRS) estes valores são apenas o padrão: cada conector pode ter seu próprio ajuste."},
    # Roles de señal
    "Distribuidor (repite la señal en sus salidas)": {"en": "Distributor (repeats the signal on its outputs)", "pt": "Distribuidor (repete o sinal nas saídas)"},
    "Fuente (genera la señal)": {"en": "Source (generates the signal)", "pt": "Fonte (gera o sinal)"},
    "Enrutador (según ruteo de matriz)": {"en": "Router (per matrix routing)", "pt": "Roteador (conforme o roteamento da matriz)"},
    "Procesador (combina/transforma → señal nueva)": {"en": "Processor (combines/transforms → new signal)", "pt": "Processador (combina/transforma → sinal novo)"},
    "Consumidor (no tiene salidas de señal)": {"en": "Consumer (no signal outputs)", "pt": "Consumidor (sem saídas de sinal)"},
    "Patchera (bypass físico A/B, no usa ruteo de matriz)": {"en": "Patch panel (physical A/B bypass, no matrix routing)", "pt": "Patch panel (bypass físico A/B, sem roteamento de matriz)"},
    "Conversor de balance (DI box, transformador — punto de conversión legítimo)":
        {"en": "Balance converter (DI box, transformer — legitimate conversion point)", "pt": "Conversor de balanceamento (DI box, transformador — ponto de conversão legítimo)"},
    "Sumador/divisor de canal (mono↔estéreo — punto de conversión legítimo)":
        {"en": "Channel summer/splitter (mono↔stereo — legitimate conversion point)", "pt": "Somador/divisor de canal (mono↔estéreo — ponto de conversão legítimo)"},
    "Distribuidor de referencia de frame (reparte REF1/REF2 externo a los demás slots del frame)":
        {"en": "Frame reference distributor (shares external REF1/REF2 with the other slots of the frame)", "pt": "Distribuidor de referência de frame (reparte REF1/REF2 externo aos demais slots do frame)"},
    "Fantasma (extremo desconectado confirmado)": {"en": "Ghost (confirmed disconnected end)", "pt": "Fantasma (extremo desconectado confirmado)"},
    # Columnas de la lista
    "Rol señal": {"en": "Signal role", "pt": "Papel do sinal"},
    "Referencia generada": {"en": "Generated reference", "pt": "Referência gerada"},
    "Naturaleza": {"en": "Nature", "pt": "Natureza"},
    "Máx. balanceado (m)": {"en": "Max. balanced (m)", "pt": "Máx. balanceado (m)"},
    "Máx. desbalanceado (m)": {"en": "Max. unbalanced (m)", "pt": "Máx. desbalanceado (m)"},
    "Conductores": {"en": "Conductors", "pt": "Condutores"},
    "Balance": {"en": "Balance", "pt": "Balanceamento"},
    "Canal": {"en": "Channel", "pt": "Canal"},
    "Contenido": {"en": "Content", "pt": "Conteúdo"},
    "Archivo": {"en": "File", "pt": "Arquivo"},
    # Motivos que devuelve el bridge (catalogos_web.py)
    "Ya existe uno con ese nombre": {"en": "One with that name already exists", "pt": "Já existe um com esse nome"},
    "Texto demasiado largo": {"en": "Text is too long", "pt": "Texto longo demais"},
    "No puede ser negativo": {"en": "Cannot be negative", "pt": "Não pode ser negativo"},
    "Debe ser mayor que cero": {"en": "Must be greater than zero", "pt": "Deve ser maior que zero"},
}
_WEB.update(_WEB_B2)

# Fase B.3 — cables y conexiones (app/cables_*.js; las reglas vienen de cables_web.py)
_WEB_B3 = {
    "Nuevo cable": {"en": "New cable", "pt": "Novo cabo"},
    "Editar cable": {"en": "Edit cable", "pt": "Editar cabo"},
    "Eliminar cable": {"en": "Delete cable", "pt": "Excluir cabo"},
    "Nueva conexión": {"en": "New connection", "pt": "Nova conexão"},
    "Editar conexión": {"en": "Edit connection", "pt": "Editar conexão"},
    "Quitar conexión": {"en": "Remove connection", "pt": "Remover conexão"},
    "Quitar": {"en": "Remove", "pt": "Remover"},
    "Conexión": {"en": "Connection", "pt": "Conexão"},
    "Conectar a un cable": {"en": "Connect to a cable", "pt": "Conectar a um cabo"},
    "Fusionar cables": {"en": "Merge cables", "pt": "Mesclar cabos"},
    "Confirmar fusión": {"en": "Confirm merge", "pt": "Confirmar mesclagem"},
    "Elegir para fusionar": {"en": "Select to merge", "pt": "Selecionar para mesclar"},
    "Marcá dos cables para fusionarlos": {"en": "Select two cables to merge them", "pt": "Marque dois cabos para mesclá-los"},
    "Cable principal": {"en": "Main cable", "pt": "Cabo principal"},
    "Código definitivo": {"en": "Final code", "pt": "Código definitivo"},
    "Estado final": {"en": "Final status", "pt": "Estado final"},
    "Correcto": {"en": "Correct", "pt": "Correto"},
    "Mal armado": {"en": "Wrongly wired", "pt": "Mal montado"},
    "¿Armado correcto?": {"en": "Wired correctly?", "pt": "Montagem correta?"},
    "Detalle del armado": {"en": "Wiring details", "pt": "Detalhe da montagem"},
    "Tipo de ficha": {"en": "Plug type", "pt": "Tipo de plugue"},
    "Ficha del cable en esta punta": {"en": "Cable plug at this end", "pt": "Plugue do cabo nesta ponta"},
    "Unidad de longitud": {"en": "Length unit", "pt": "Unidade de comprimento"},
    "Unidad de metraje": {"en": "Footage unit", "pt": "Unidade de metragem"},
    "Metraje extremo 1": {"en": "Footage, end 1", "pt": "Metragem, extremidade 1"},
    "Metraje extremo 2": {"en": "Footage, end 2", "pt": "Metragem, extremidade 2"},
    "Ancho de banda (override, MHz)": {"en": "Bandwidth (override, MHz)", "pt": "Largura de banda (override, MHz)"},
    "Al eliminarlo:": {"en": "If you delete it:", "pt": "Ao excluir:"},
    "No tiene conexiones ni otros datos asociados.": {"en": "It has no connections or other associated data.", "pt": "Não tem conexões nem outros dados associados."},
    "No forma parte de ninguna extensión.": {"en": "It is not part of any extension.", "pt": "Não faz parte de nenhuma extensão."},
    "¿Eliminar el cable «{nombre}»?": {"en": "Delete cable «{nombre}»?", "pt": "Excluir o cabo «{nombre}»?"},
    "¿Quitar la conexión «{etiqueta}»?": {"en": "Remove connection «{etiqueta}»?", "pt": "Remover a conexão «{etiqueta}»?"},
    "Se agregó el cable «{nombre}»": {"en": "Cable «{nombre}» added", "pt": "Cabo «{nombre}» adicionado"},
    "Se modificó el cable «{nombre}»": {"en": "Cable «{nombre}» modified", "pt": "Cabo «{nombre}» modificado"},
    "Se eliminó el cable «{nombre}»": {"en": "Cable «{nombre}» deleted", "pt": "Cabo «{nombre}» excluído"},
    "Cable temporal creado: {codigo}": {"en": "Temporary cable created: {codigo}", "pt": "Cabo temporário criado: {codigo}"},
    "Se agregó la conexión #{id}": {"en": "Connection #{id} added", "pt": "Conexão #{id} adicionada"},
    "Se modificó la conexión #{id}": {"en": "Connection #{id} modified", "pt": "Conexão #{id} modificada"},
    "Se quitó la conexión «{etiqueta}»": {"en": "Connection «{etiqueta}» removed", "pt": "Conexão «{etiqueta}» removida"},
    "Fusión: «{otro}» pasó a «{nombre}»": {"en": "Merge: «{otro}» moved into «{nombre}»", "pt": "Mesclagem: «{otro}» passou para «{nombre}»"},
    "Las conexiones del cable secundario pasarán al principal y el principal tomará el código y el estado que elijas.": {"en": "The secondary cable's connections will move to the main cable, which will take the code and status you choose.", "pt": "As conexões do cabo secundário passarão ao principal, que ficará com o código e o estado escolhidos."},
    "Las conexiones del otro cable pasan a este. El otro queda marcado como FUSIONADO (no se borra).": {"en": "The other cable\"s connections move to this one. The other is marked MERGED (not deleted).", "pt": "As conexões do outro cabo passam para este. O outro fica marcado como MESCLADO (não é excluído)."},
    "Opcional. Debe ser único. «⚡ Temporal» en la lista genera uno automático (SIN ETIQUETA NNNN).": {"en": "Optional. Must be unique. «⚡ Temporary» in the list generates one automatically (SIN ETIQUETA NNNN).", "pt": "Opcional. Deve ser único. «⚡ Temporário» na lista gera um automaticamente (SIN ETIQUETA NNNN)."},
    "Vacío = usar el default de su tipo de cable. Cargar solo si ESTE cable no representa a su tipo nominal (ej. un patchcord viejo o degradado).": {"en": "Empty = use its cable type\"s default. Fill in only if THIS cable does not represent its nominal type (e.g. an old or degraded patchcord).", "pt": "Vazio = usar o padrão do tipo de cabo. Preencher só se ESTE cabo não representa o seu tipo nominal (ex.: um patchcord velho ou degradado)."},
    "Vacío = no verificado.": {"en": "Empty = not verified.", "pt": "Vazio = não verificado."},
    "Solo sirve para elegir el conector: no se guarda.": {"en": "Only used to pick the connector; it is not saved.", "pt": "Serve só para escolher o conector; não é salvo."},
    "Qué ficha es físicamente el extremo del cable que llega acá (ej. XLR3 macho, TS); puede ser distinta de la que espera el jack del equipo.": {"en": "Which plug the cable end physically has here (e.g. XLR3 male, TS); it may differ from what the equipment jack expects.", "pt": "Qual plugue a ponta do cabo tem fisicamente aqui (ex.: XLR3 macho, TS); pode ser diferente do que o jack do equipamento espera."},
    "No se pudieron cargar las opciones": {"en": "Could not load the options", "pt": "Não foi possível carregar as opções"},
    "Ya existe un cable con ese código": {"en": "A cable with that code already exists", "pt": "Já existe um cabo com esse código"},
    "Ya lo usa otro cable (incluido el secundario)": {"en": "Another cable already uses it (including the secondary)", "pt": "Outro cabo já o usa (inclusive o secundário)"},
    "Ese cable ya está conectado a ese conector": {"en": "That cable is already connected to that connector", "pt": "Esse cabo já está conectado a esse conector"},
    "El cable tiene {n} extremos (lo habitual es 2)": {"en": "The cable has {n} ends (2 is usual)", "pt": "O cabo tem {n} extremidades (o habitual é 2)"},
    "El conector ya tiene {n} conexión(es) más": {"en": "The connector already has {n} other connection(s)", "pt": "O conector já tem mais {n} conexão(ões)"},
    "Extensiones de cable": {"en": "Cable extensions", "pt": "Extensões de cabo"},
    "Cambios de escenario": {"en": "Scenario changes", "pt": "Alterações de cenário"},
    "Incidentes de cable": {"en": "Cable incidents", "pt": "Incidentes de cabo"},
    "Sesiones de diagnóstico": {"en": "Diagnostic sessions", "pt": "Sessões de diagnóstico"},
}
_WEB.update(_WEB_B3)

# Fase B.4 — equipos y conectores (app/equipos_*.js; las reglas vienen de equipos_web.py)
_WEB_B4 = {
    "Nuevo equipo": {"en": "New equipment", "pt": "Novo equipamento"},
    "Alta rápida": {"en": "Quick add", "pt": "Cadastro rápido"},
    "Alta rápida de equipo": {"en": "Quick add equipment", "pt": "Cadastro rápido de equipamento"},
    "Editar equipo": {"en": "Edit equipment", "pt": "Editar equipamento"},
    "Eliminar equipo": {"en": "Delete equipment", "pt": "Excluir equipamento"},
    "Nuevo conector": {"en": "New connector", "pt": "Novo conector"},
    "Editar conector": {"en": "Edit connector", "pt": "Editar conector"},
    "Eliminar conector": {"en": "Delete connector", "pt": "Excluir conector"},
    "Siguiente": {"en": "Next", "pt": "Próximo"},
    "Crear equipo": {"en": "Create equipment", "pt": "Criar equipamento"},
    "Primero los datos del equipo; después elegís sus conectores.": {"en": "First the equipment data; then you choose its connectors.", "pt": "Primeiro os dados do equipamento; depois você escolhe os conectores."},
    "Conectores de «{nombre}»": {"en": "Connectors of «{nombre}»", "pt": "Conectores de «{nombre}»"},
    "Equipo: {equipo}": {"en": "Equipment: {equipo}", "pt": "Equipamento: {equipo}"},
    "Indicá cuántos conectores crear de cada tipo. Sin tipo de equipo no se guarda plantilla.": {"en": "Enter how many connectors to create of each type. Without an equipment type no template is saved.", "pt": "Informe quantos conectores criar de cada tipo. Sem tipo de equipamento nenhum modelo é salvo."},
    "Cantidades de la plantilla de este tipo de equipo. Cambialas si hace falta: lo que elijas queda como plantilla del tipo.": {"en": "Quantities from this equipment type's template. Change them if needed: what you choose becomes the type's template.", "pt": "Quantidades do modelo deste tipo de equipamento. Altere se precisar: o que você escolher passa a ser o modelo do tipo."},
    "Este tipo de equipo todavía no tiene plantilla: indicá cuántos conectores crear de cada tipo y quedará como plantilla.": {"en": "This equipment type has no template yet: enter how many connectors to create of each type and it will become the template.", "pt": "Este tipo de equipamento ainda não tem modelo: informe quantos conectores criar de cada tipo e ele passará a ser o modelo."},
    "Se agregó el equipo «{nombre}»": {"en": "Equipment «{nombre}» added", "pt": "Equipamento «{nombre}» adicionado"},
    "Se creó el equipo «{nombre}» con {n} conector(es)": {"en": "Equipment «{nombre}» created with {n} connector(s)", "pt": "Equipamento «{nombre}» criado com {n} conector(es)"},
    "Se modificó el equipo «{nombre}»": {"en": "Equipment «{nombre}» modified", "pt": "Equipamento «{nombre}» modificado"},
    "Se eliminó el equipo «{nombre}»": {"en": "Equipment «{nombre}» deleted", "pt": "Equipamento «{nombre}» excluído"},
    "Se agregó el conector «{nombre}»": {"en": "Connector «{nombre}» added", "pt": "Conector «{nombre}» adicionado"},
    "Se modificó el conector «{nombre}»": {"en": "Connector «{nombre}» modified", "pt": "Conector «{nombre}» modificado"},
    "Se eliminó el conector «{nombre}»": {"en": "Connector «{nombre}» deleted", "pt": "Conector «{nombre}» excluído"},
    "¿Eliminar el equipo «{nombre}»?": {"en": "Delete equipment «{nombre}»?", "pt": "Excluir o equipamento «{nombre}»?"},
    "¿Eliminar el conector «{nombre}»?": {"en": "Delete connector «{nombre}»?", "pt": "Excluir o conector «{nombre}»?"},
    "No tiene conectores, conexiones ni otros datos asociados.": {"en": "It has no connectors, connections or other associated data.", "pt": "Não tem conectores, conexões nem outros dados associados."},
    "quedarán sin este equipo": {"en": "will be left without this equipment", "pt": "ficarão sem este equipamento"},
    "quedarán sin este conector": {"en": "will be left without this connector", "pt": "ficarão sem este conector"},
    "Hay datos que corregir": {"en": "There is data to fix", "pt": "Há dados a corrigir"},
    "Fila repetida": {"en": "Duplicate row", "pt": "Linha repetida"},
    "Máximo 99 por fila": {"en": "Maximum 99 per row", "pt": "Máximo 99 por linha"},
    "Elegí una señal para usar un formato": {"en": "Choose a signal to use a format", "pt": "Escolha um sinal para usar um formato"},
    "N.º de inventario": {"en": "Inventory no.", "pt": "N.º de inventário"},
    "N.º de serie": {"en": "Serial no.", "pt": "N.º de série"},
    "Fecha de fabricación": {"en": "Manufacture date", "pt": "Data de fabricação"},
    "Es módulo de frame": {"en": "Is a frame module", "pt": "É módulo de frame"},
    "⭐ Equipo crítico de la cadena": {"en": "⭐ Critical equipment in the chain", "pt": "⭐ Equipamento crítico da cadeia"},
    "Ancho (mm)": {"en": "Width (mm)", "pt": "Largura (mm)"},
    "Alto (mm)": {"en": "Height (mm)", "pt": "Altura (mm)"},
    "Profundidad (mm)": {"en": "Depth (mm)", "pt": "Profundidade (mm)"},
    "Manual (ruta del archivo)": {"en": "Manual (file path)", "pt": "Manual (caminho do arquivo)"},
    "Tipo de conector": {"en": "Connector type", "pt": "Tipo de conector"},
    "Ficha eléctrica": {"en": "Electrical plug", "pt": "Ficha elétrica"},
    "Formato de señal": {"en": "Signal format", "pt": "Formato de sinal"},
    "Marcalo si el equipo solo tiene sentido instalado en un slot de un frame (no se ofrece como equipo suelto).": {"en": "Check it if the equipment only makes sense installed in a frame slot (it is not offered as loose equipment).", "pt": "Marque se o equipamento só faz sentido instalado em um slot de um frame (não é oferecido como equipamento solto)."},
    "Con al menos un equipo crítico en la base, el factor Impacto del riesgo mide solo contra ese conjunto en vez de todo el parque.": {"en": "With at least one critical equipment in the database, the risk Impact factor is measured only against that set instead of the whole inventory.", "pt": "Com pelo menos um equipamento crítico na base, o fator Impacto do risco é medido só contra esse conjunto em vez de todo o parque."},
    "Texto libre (ej. 2019 o 2019-05).": {"en": "Free text (e.g. 2019 or 2019-05).", "pt": "Texto livre (ex.: 2019 ou 2019-05)."},
    "Texto libre.": {"en": "Free text.", "pt": "Texto livre."},
    "Solo se guarda la ruta: los manuales no se cargan en el navegador.": {"en": "Only the path is saved: manuals are not loaded in the browser.", "pt": "Só o caminho é salvo: os manuais não são carregados no navegador."},
    "Qué ficha es eléctricamente este conector (de ahí salen el balance y el canal por defecto).": {"en": "Which plug this connector electrically is (the default balance and channel come from it).", "pt": "Que ficha é eletricamente este conector (dela saem o balanço e o canal padrão)."},
    "Vacío = el que trae la ficha.": {"en": "Empty = the one the plug type brings.", "pt": "Vazio = o que a ficha traz."},
    "Solo se puede elegir junto con una señal.": {"en": "It can only be chosen together with a signal.", "pt": "Só pode ser escolhido junto com um sinal."},
    "Posiciones en rack": {"en": "Rack positions", "pt": "Posições em rack"},
    "Problemas del equipo": {"en": "Equipment problems", "pt": "Problemas do equipamento"},
    "Marcas de equipo crítico": {"en": "Critical equipment marks", "pt": "Marcas de equipamento crítico"},
    "Cachés de riesgo": {"en": "Risk caches", "pt": "Caches de risco"},
    "Posiciones en diagramas": {"en": "Diagram positions", "pt": "Posições em diagramas"},
    "Nodos de diagramas guardados": {"en": "Saved diagram nodes", "pt": "Nós de diagramas salvos"},
    "Conexiones de diagramas guardados": {"en": "Saved diagram connections", "pt": "Conexões de diagramas salvos"},
    "Equipos no rackeables en sala": {"en": "Non-rackable equipment in rooms", "pt": "Equipamentos não rackeáveis em sala"},
    "Equipos en zonas": {"en": "Equipment in zones", "pt": "Equipamentos em zonas"},
    "Equipos sobre muebles": {"en": "Equipment on furniture", "pt": "Equipamentos sobre móveis"},
    "Incidentes de equipo": {"en": "Equipment incidents", "pt": "Incidentes de equipamento"},
    "Miembros de reglas lógicas": {"en": "Logic rule members", "pt": "Membros de regras lógicas"},
    "Salidas de reglas lógicas": {"en": "Logic rule outputs", "pt": "Saídas de regras lógicas"},
    "Ruteos de matriz": {"en": "Matrix routings", "pt": "Roteamentos de matriz"},
    "Miembros de estrategias visuales": {"en": "Visual strategy members", "pt": "Membros de estratégias visuais"},
    "Pasos de diagnóstico": {"en": "Diagnostic steps", "pt": "Passos de diagnóstico"},
    "Extremo desconectado": {"en": "Disconnected end", "pt": "Extremidade desconectada"},
    "Marcar extremo desconectado": {"en": "Mark disconnected end", "pt": "Marcar extremidade desconectada"},
    "Lado del extremo desconectado": {"en": "Side of the disconnected end", "pt": "Lado da extremidade desconectada"},
    "Lado A (conector OUT)": {"en": "Side A (OUT connector)", "pt": "Lado A (conector OUT)"},
    "Lado B (conector IN)": {"en": "Side B (IN connector)", "pt": "Lado B (conector IN)"},
    "Se crea un equipo FANTASMA con un conector ya conectado a este cable: OUT en el lado A, IN en el lado B.": {"en": "A GHOST equipment is created with a connector already connected to this cable: OUT on side A, IN on side B.", "pt": "É criado um equipamento FANTASMA com um conector já ligado a este cabo: OUT no lado A, IN no lado B."},
    "Se creó el extremo desconectado «{nombre}»": {"en": "Disconnected end «{nombre}» created", "pt": "Extremidade desconectada «{nombre}» criada"},
    "Crear": {"en": "Create", "pt": "Criar"},
    "Este cable ya tiene sus dos extremos documentados.": {"en": "This cable already has both ends documented.", "pt": "Este cabo já tem as duas extremidades documentadas."},
    "No hay ningún tipo de equipo con rol FANTASMA en el catálogo. Marcá uno (Catálogos → Tipos de equipo) antes de usar esta acción.": {"en": "There is no equipment type with the GHOST role in the catalog. Mark one (Catalogs → Equipment types) before using this action.", "pt": "Não há nenhum tipo de equipamento com o papel FANTASMA no catálogo. Marque um (Catálogos → Tipos de equipamento) antes de usar esta ação."},
}
_WEB.update(_WEB_B4)
