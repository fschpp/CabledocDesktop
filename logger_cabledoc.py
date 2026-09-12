"""
logger_cabledoc.py — Logueo de errores para diagnóstico.

Crea/agrega a log.txt (misma carpeta que la app) un registro con fecha,
hora, origen y traceback de cada error: crashes no capturados y errores
de la capa de datos (Modelo._query / Modelo._exec).

Uso:
    from logger_cabledoc import log_error, instalar_hook_excepciones
    instalar_hook_excepciones()   # una vez, al arrancar la app
    log_error("Modelo._exec", exc)  # manual, donde se necesite
"""

import os
import sys
import traceback
import threading
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")

_lock = threading.Lock()


def log_error(origen, exc):
    """Agrega una entrada al log.txt: fecha/hora, origen y traceback."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entrada = f"[{ahora}] ({origen})\n{tb}\n"
    try:
        with _lock:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(entrada)
    except Exception:
        pass  # el logueo nunca debe romper la app


def log_debug(mensaje):
    """Agrega una línea de diagnóstico al log.txt (sin traceback, para
    mediciones de tiempo / conteos durante la investigación de
    lentitud). También la imprime por stdout (visible en la consola de
    Pydroid 3)."""
    ahora = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entrada = f"[{ahora}] {mensaje}"
    try:
        print(entrada, flush=True)
    except Exception:
        pass
    try:
        with _lock:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(entrada + "\n")
    except Exception:
        pass


def _excepthook(tipo, valor, tb):
    log_error("No capturado", valor)
    sys.__excepthook__(tipo, valor, tb)


def instalar_hook_excepciones():
    """Instala el logueo de excepciones no capturadas (crashes)."""
    sys.excepthook = _excepthook
