from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_timeline_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "plugins.v2" / "subtitlemanualupload" / "timeline_fixer.py"
    module_name = "subtitlemanualupload_timeline_fixer_testpkg"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_max_offset_defaults_and_caps():
    module = load_timeline_module()

    assert module._normalize_max_offset(None) == 120
    assert module._normalize_max_offset(-1) == 120
    assert module._normalize_max_offset("45") == 45
    assert module._normalize_max_offset(700) == 300


def test_dependency_status_treats_webrtcvad_as_optional(monkeypatch):
    module = load_timeline_module()

    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}" if name in {"ffmpeg", "ffprobe"} else None)
    monkeypatch.setattr(
        module.importlib_util,
        "find_spec",
        lambda name: None if name == "webrtcvad" else object(),
    )
    monkeypatch.setattr(module, "_binary_version", lambda path: "version")

    status = module.check_timeline_fixer_dependencies()

    assert status["available"] is True
    assert status["modules"]["webrtcvad"] is False
    assert "webrtcvad" not in module._missing_dependency_names(status)


def test_alignment_confidence_rejects_over_configured_max_and_flags_over_120():
    module = load_timeline_module()

    confidence, risks = module._alignment_confidence(
        offset_seconds=121.0,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.1,
        active_ratio=0.2,
        max_offset_seconds=120,
    )
    assert confidence == "rejected"
    assert "offset_over_configured_max" in risks
    assert "offset_over_120s" in risks

    confidence, risks = module._alignment_confidence(
        offset_seconds=121.0,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.1,
        active_ratio=0.2,
        max_offset_seconds=300,
    )
    assert confidence == "low"
    assert "offset_over_120s" in risks
