#!/usr/bin/env python3
"""Test nativo de ui_web/i18n_web.py (Fase A.2). No necesita base de datos.

Uso (desde la raíz del repo):  python3 ui_web/tests/test_i18n_web.py
"""
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ui_web"))

import i18n_web as w  # noqa: E402
from core import i18n as base  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    n += 1
    assert cond, msg


# 1) Toda cadena web tiene en y pt, no vacías
for k, v in w._WEB.items():
    for lg in ("en", "pt"):
        ok(v.get(lg, "").strip(), f"falta {lg} en {k!r}")

# 2) Los placeholders {x} coinciden entre la clave y cada traducción
for k, v in w._WEB.items():
    ph = set(re.findall(r"\{(\w+)\}", k))
    for lg in ("en", "pt"):
        ok(set(re.findall(r"\{(\w+)\}", v[lg])) == ph, f"placeholders distintos en {k!r} ({lg})")

# 3) diccionario(): es vacío; en/pt incluyen core + web, y web pisa a core
ok(w.diccionario("es") == {}, "es debe ser vacío (la clave ya está en español)")
for lg in ("en", "pt"):
    d = w.diccionario(lg)
    ok(d["Guardar"] == base._TRADUCCIONES["Guardar"][lg], f"core no llegó ({lg})")
    ok(d["Inicio"] == w._WEB["Inicio"][lg], f"web no llegó ({lg})")
    ok(len(d) >= len(w._WEB), f"diccionario chico ({lg})")
ok(w.diccionario("en")["Inicio"] == "Home", "Inicio→Home")
ok(w.diccionario("pt")["Cables"] == "Cabos", "Cables→Cabos")

# 4) Idioma inválido
try:
    w.diccionario("fr")
    ok(False, "debió fallar con 'fr'")
except ValueError:
    ok(True, "")

# 5) Mismos idiomas que core
ok(set(w.IDIOMAS) == set(base.IDIOMAS_DISPONIBLES), "idiomas distintos a core.i18n")

# 6) JSON válido y con la forma que espera el JS
j = json.loads(w.diccionario_json("pt"))
ok(j["lang"] == "pt" and j["idiomas"]["en"] == "English" and isinstance(j["textos"], dict), "forma JSON")

print(f"OK — {n} chequeos")
