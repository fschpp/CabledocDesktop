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
