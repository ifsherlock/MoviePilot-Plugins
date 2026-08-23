from __future__ import annotations

import shutil
import subprocess
from importlib import util as importlib_util
from typing import Any, Callable, Dict, List, Optional


def check_timeline_fixer_dependencies(
    *,
    sample_rate: int,
    max_offset_seconds: int,
    min_offset_seconds: float,
    shutil_module: Any = shutil,
    importlib_util_module: Any = importlib_util,
    binary_version_func: Optional[Callable[[Optional[str]], str]] = None,
) -> Dict[str, Any]:
    ffmpeg = shutil_module.which("ffmpeg")
    ffprobe = shutil_module.which("ffprobe")
    modules = {
        "numpy": importlib_util_module.find_spec("numpy") is not None,
        "pysubs2": importlib_util_module.find_spec("pysubs2") is not None,
        "webrtcvad": importlib_util_module.find_spec("webrtcvad") is not None,
    }
    required_modules = {key: modules[key] for key in ("numpy", "pysubs2")}
    version = binary_version_func or _binary_version
    return {
        "available": bool(ffmpeg and ffprobe and all(required_modules.values())),
        "ffmpeg": bool(ffmpeg),
        "ffprobe": bool(ffprobe),
        "ffmpeg_path": ffmpeg or "",
        "ffprobe_path": ffprobe or "",
        "ffmpeg_version": version(ffmpeg),
        "ffprobe_version": version(ffprobe),
        "modules": modules,
        "sample_rate": sample_rate,
        "max_offset_seconds": max_offset_seconds,
        "min_offset_seconds": min_offset_seconds,
    }


def _binary_version(path: Optional[str], *, subprocess_module: Any = subprocess) -> str:
    if not path:
        return ""
    try:
        result = subprocess_module.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    first_line = (result.stdout or result.stderr or "").splitlines()
    return first_line[0][:160] if first_line else ""


def missing_dependency_names(status: Dict[str, Any]) -> List[str]:
    missing = []
    if not status.get("ffmpeg"):
        missing.append("ffmpeg")
    if not status.get("ffprobe"):
        missing.append("ffprobe")
    for name, ok in (status.get("modules") or {}).items():
        if name == "webrtcvad":
            continue
        if not ok:
            missing.append(name)
    return missing
