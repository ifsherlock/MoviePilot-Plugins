from __future__ import annotations

try:
    from .online_subtitles.core import *  # noqa: F401,F403
except ImportError:
    import importlib.util
    import types
    import sys
    from pathlib import Path

    package_path = Path(__file__).with_name("online_subtitles")
    package_name = "_subtitlemanualupload_online_subtitles"
    module_path = package_path / "core.py"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules.setdefault(package_name, package)
    spec = importlib.util.spec_from_file_location(f"{package_name}.core", module_path)
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    globals().update(
        {
            name: value
            for name, value in vars(module).items()
            if not (name.startswith("__") and name.endswith("__"))
        }
    )
