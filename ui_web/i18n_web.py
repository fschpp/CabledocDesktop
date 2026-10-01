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
