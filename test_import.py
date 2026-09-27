#!/usr/bin/env python3
import sys
import os

# Añadir el path
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

print("Python:", sys.version.split()[0])

try:
    from kivy.config import Config
    from kivy.utils import platform
    print("Kivy platform:", platform)
    print("Kivy Config:", Config)
    
    from kivy import __version__
    print("Kivy version:", __version__)
except Exception as e:
    print("ERROR importing kivy:", e)
    import traceback
    traceback.print_exc()

try:
    from core.logger_cabledoc import log_debug
    log_debug("Test: logger_cabledoc imported successfully")
except Exception as e:
    print("ERROR importing logger_cabledoc:", e)
    import traceback
    traceback.print_exc()

print("Test completed")
