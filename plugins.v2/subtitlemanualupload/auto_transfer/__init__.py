"""Automatic subtitle matching after transfer events.

Temporary bridge for Phase 1: the package name intentionally matches the
existing ``auto_transfer.py`` module. Until Phase 3 moves that module into this
package, re-export the old module so current imports keep working.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_parent_package = __name__.rsplit(".", 1)[0]
_legacy_path = Path(__file__).resolve().parents[1] / "auto_transfer.py"
_legacy_name = f"{_parent_package}._auto_transfer_legacy"
_spec = importlib.util.spec_from_file_location(_legacy_name, _legacy_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load legacy auto_transfer module from {_legacy_path}")

_module = importlib.util.module_from_spec(_spec)
sys.modules[_legacy_name] = _module
_spec.loader.exec_module(_module)

for _name, _value in vars(_module).items():
    if not _name.startswith("_"):
        globals()[_name] = _value

__all__ = [name for name in globals() if not name.startswith("_")]
