from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _class_name_and_version(path: Path) -> tuple[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    plugin = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    version = next(
        node.value.value
        for node in plugin.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "plugin_version" for target in node.targets)
        and isinstance(node.value, ast.Constant)
    )
    return plugin.name, version


def test_v3_plugins_keep_stable_identity_and_versions():
    assert _class_name_and_version(ROOT / "plugins.v3/autosubv3/__init__.py") == ("AutoSubv3", "4.0.1")
    assert _class_name_and_version(ROOT / "plugins.v3/subtitlemanualupload/__init__.py") == (
        "SubtitleManualUpload",
        "1.2.0",
    )


def test_v3_index_and_v2_opt_out_are_consistent():
    package_v3 = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    package_v2 = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))
    for plugin_id, version in (("AutoSubv3", "4.0.1"), ("SubtitleManualUpload", "1.2.0")):
        assert package_v3[plugin_id]["version"] == version
        assert package_v3[plugin_id]["system_version"] == ">=3.0.0"
        assert f"v{version}" in package_v3[plugin_id]["history"]
        assert package_v2[plugin_id]["v3"] is False


def test_v3_source_uses_sdk_and_unified_media_identity():
    roots = [ROOT / "plugins.v3/autosubv3", ROOT / "plugins.v3/subtitlemanualupload"]
    source = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for root in roots
        for path in root.rglob("*.py")
        if "node_modules" not in path.parts and "dist" not in path.parts
    )
    assert "from app.sdk.config import settings" in source
    assert "from app.sdk.logging import logger" in source
    assert "from app.core.config import settings" not in source
    assert "from app.log import logger" not in source
    resolver = (ROOT / "plugins.v3/subtitlemanualupload/catalog/media_target_resolver.py").read_text(
        encoding="utf-8"
    )
    assert "build_media_key" in resolver
    assert "resolve_media_identity" in resolver
    assert '"media_source"' in resolver
    assert '"media_id"' in resolver
    catalog = (ROOT / "plugins.v3/subtitlemanualupload/catalog/local_media_catalog.py").read_text(
        encoding="utf-8"
    )
    assert "db=None" not in catalog
    history_reader = (
        ROOT / "plugins.v3/subtitlemanualupload/runtime/transfer_history_reader.py"
    ).read_text(encoding="utf-8")
    assert "TransferHistoryOper" in history_reader
    assert "TransferHistory.list_by_page" in history_reader
    assert "_execute_sync_query" not in history_reader


def test_subtitlemanualupload_v2_v3_runtime_boundaries_are_explicit():
    v2_root = ROOT / "plugins.v2/subtitlemanualupload"
    v3_root = ROOT / "plugins.v3/subtitlemanualupload"
    v2_factory = (v2_root / "runtime/service_factories.py").read_text(encoding="utf-8-sig")
    v3_factory = (v3_root / "runtime/service_factories.py").read_text(encoding="utf-8-sig")
    v2_resolver = (v2_root / "catalog/media_target_resolver.py").read_text(encoding="utf-8-sig")
    v3_resolver = (v3_root / "catalog/media_target_resolver.py").read_text(encoding="utf-8-sig")
    v2_catalog = (v2_root / "catalog/local_media_catalog.py").read_text(encoding="utf-8-sig")
    v3_catalog = (v3_root / "catalog/local_media_catalog.py").read_text(encoding="utf-8-sig")

    assert "from app.core.config import settings" in v2_factory
    assert "from app.core.metainfo import MetaInfoPath" in v2_factory
    assert "from app.db.models.transferhistory import TransferHistory" in v2_factory
    assert "transfer_history=TransferHistory" in v2_factory
    assert "db=None" in v2_catalog
    assert "app.sdk" not in v2_factory
    assert "resolve_media_identity" not in v2_resolver
    assert "build_media_key" not in v2_resolver

    assert "from app.sdk.config import settings" in v3_factory
    assert "from app.sdk.media import MetaInfoPath" in v3_factory
    assert "transfer_history=TransferHistoryReader()" in v3_factory
    assert "MetaInfoPath(path, force_video=True)" in v3_factory
    assert "db=None" not in v3_catalog
    assert "resolve_media_identity" in v3_resolver
    assert "build_media_key" in v3_resolver

    manual_strm = v3_root / "catalog/manual_strm.py"
    if manual_strm.exists():
        manual_strm_source = manual_strm.read_text(encoding="utf-8-sig")
        assert "from app.sdk" not in manual_strm_source
        assert "from app.core" not in manual_strm_source


def test_v3_autosub_handles_transfer_event_separately_from_watchdog_startup():
    source = (ROOT / "plugins.v3/autosubv3/__init__.py").read_text(encoding="utf-8-sig")
    assert "def listen_transfer_complete(self, event):" in source
    assert "def _start_file_monitor(self):" in source
    assert "trigger=TriggerType.EVENT.value" in source
