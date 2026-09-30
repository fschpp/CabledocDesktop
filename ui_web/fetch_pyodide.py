#!/usr/bin/env python3
"""Baja Pyodide del registro npm y deja los archivos mínimos en ui_web/pyodide/.
Uso: python3 ui_web/fetch_pyodide.py   (no requiere npm)"""
import io, os, sys, tarfile, urllib.request
VERSION = "314.0.7"
URL = f"https://registry.npmjs.org/pyodide/-/pyodide-{VERSION}.tgz"
dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyodide")
os.makedirs(dest, exist_ok=True)
data = urllib.request.urlopen(URL).read()
want = {"pyodide.js", "pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "package.json"}
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
    for m in t.getmembers():
        n = os.path.basename(m.name)
        if m.isfile() and n in want:
            open(os.path.join(dest, n), "wb").write(t.extractfile(m).read())
print("OK ->", dest, sorted(os.listdir(dest)))
