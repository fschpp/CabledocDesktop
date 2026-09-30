#!/usr/bin/env python3
"""Empaqueta core/*.py + data/schema_db.sql del repo en ui_web/core.zip.
Uso (desde la raíz del repo):  python3 ui_web/build_core_zip.py
Volver a correrlo cada vez que cambie algo en core/."""
import os, sys, zipfile
root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "ui_web", "core.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(os.path.join(root, "core"))):
        if f.endswith(".py"):
            z.write(os.path.join(root, "core", f), "core/" + f)
    z.write(os.path.join(root, "data", "schema_db.sql"), "data/schema_db.sql")
print("OK", out, round(os.path.getsize(out) / 1024), "KB")
