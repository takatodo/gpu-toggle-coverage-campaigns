import sys as _sys
from pathlib import Path as _Path

_here = str(_Path(__file__).resolve().parent)
if _here not in _sys.path:
    _sys.path.insert(0, _here)
