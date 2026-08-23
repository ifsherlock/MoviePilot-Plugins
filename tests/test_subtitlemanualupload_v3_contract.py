from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v3_manual_strm_config_and_manifest_are_consistent():
    schema = (ROOT / "plugins.v3/subtitlemanualupload/config/config_schema.py").read_text(encoding="utf-8-sig")
    runtime = (ROOT / "plugins.v3/subtitlemanualupload/config/config_runtime.py").read_text(encoding="utf-8-sig")
    factory = (ROOT / "plugins.v3/subtitlemanualupload/runtime/service_factories.py").read_text(encoding="utf-8-sig")
    owner = (ROOT / "plugins.v3/subtitlemanualupload/__init__.py").read_text(encoding="utf-8-sig")
    package = json.loads((ROOT / "plugins.v3/subtitlemanualupload/package.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))

    assert "manual_strm_enabled" in schema
    assert "manual_strm_paths" in schema
    assert '"_manual_strm_enabled"' in runtime
    assert '"_manual_strm_paths"' in runtime
    assert "ManualStrmCatalog" in factory
    assert "MetaInfoPath(path, force_video=True)" in factory
    assert '"origin": "manual_strm"' in (ROOT / "plugins.v3/subtitlemanualupload/catalog/manual_strm.py").read_text(encoding="utf-8-sig")
    assert package["version"] == "1.2.0"
    assert index["SubtitleManualUpload"]["version"] == package["version"]
    assert "manual_strm_enabled" in owner
